"""Unit tests for the OpenAI-compatible (Bailian) client adapter.

Covers the P2 fixes from the 2026-08-03 live review:
- STARPLAN_QWEN_BASE_URL switches call_qwen/call_qwen_json/call_qwen_chat
  to the compatible-mode chat/completions endpoint.
- STARPLAN_QWEN_MODEL overrides the effective model.
- Timeout and bounded retries are applied; 4xx errors are NOT retried.
- The native DashScope path remains the default when the base URL is unset.
"""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

from starplan_skills import qwen_client as qc


class _FakeResp:
    """Minimal urllib response wrapper for mocked urlopen."""

    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _choice(content: str = "", tool_calls=None, finish: str = "stop") -> dict:
    msg: dict = {"role": "assistant"}
    if content:
        msg["content"] = content
    if tool_calls is not None:
        msg["tool_calls"] = tool_calls
    return {"choices": [{"message": msg, "finish_reason": finish}]}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Ensure the compatible endpoint is off unless a test turns it on."""
    monkeypatch.delenv("STARPLAN_QWEN_BASE_URL", raising=False)
    monkeypatch.delenv("STARPLAN_QWEN_MODEL", raising=False)
    monkeypatch.delenv("STARPLAN_QWEN_TIMEOUT", raising=False)
    monkeypatch.delenv("STARPLAN_QWEN_RETRIES", raising=False)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test-key")
    # These tests mock the HTTP layer; they are NOT real network calls, so
    # they must remain runnable under the offline CI tripwire.
    monkeypatch.setattr(qc, "_OFFLINE", False)


def _enable_compatible(monkeypatch, url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"):
    monkeypatch.setenv("STARPLAN_QWEN_BASE_URL", url)


class TestCompatibleJsonCall:
    def test_json_call_parses_content(self, monkeypatch, tmp_path):
        _enable_compatible(monkeypatch)
        captured = {}

        def fake_urlopen(request, timeout=None):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return _FakeResp(_choice(content='{"status": "ok", "number": 42}'))

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        log_path = str(tmp_path / "model_call_log.jsonl")
        result = qc.call_qwen_json(
            "返回 JSON",
            system_prompt="只返回 JSON",
            log_path=log_path,
            step_name="unit_json",
        )
        assert result["parsed_json"] == {"status": "ok", "number": 42}
        assert captured["url"].endswith("/chat/completions")
        assert captured["body"]["model"] == qc.DEFAULT_MODEL
        # Single audit entry per call
        lines = Path(log_path).read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["type"] == "model_call"

    def test_model_env_override(self, monkeypatch):
        _enable_compatible(monkeypatch)
        monkeypatch.setenv("STARPLAN_QWEN_MODEL", "qwen3.7-plus")
        captured = {}

        def fake_urlopen(request, timeout=None):
            captured["model"] = json.loads(request.data.decode("utf-8"))["model"]
            return _FakeResp(_choice(content="{}"))

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        qc.call_qwen_json("x")
        assert captured["model"] == "qwen3.7-plus"

    def test_timeout_from_env(self, monkeypatch):
        _enable_compatible(monkeypatch)
        monkeypatch.setenv("STARPLAN_QWEN_TIMEOUT", "42")
        captured = {}

        def fake_urlopen(request, timeout=None):
            captured["timeout"] = timeout
            return _FakeResp(_choice(content="{}"))

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        qc.call_qwen("hi")
        assert captured["timeout"] == 42


class TestCompatibleChatLoop:
    def test_tool_loop_executes_tools_and_finishes(self, monkeypatch):
        _enable_compatible(monkeypatch)
        tool_calls = [{
            "id": "call_1",
            "type": "function",
            "function": {"name": "get_weather", "arguments": '{"city": "北京"}'},
        }]
        responses = [
            _choice(tool_calls=tool_calls, finish="tool_calls"),
            _choice(content="完成"),
        ]
        state = {"idx": 0}

        def fake_urlopen(request, timeout=None):
            data = json.loads(request.data.decode("utf-8"))
            assert data["tools"], "tools must be forwarded in compatible mode"
            resp = responses[state["idx"]]
            state["idx"] += 1
            return _FakeResp(resp)

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        executed = {}
        result = qc.call_qwen_chat(
            messages=[{"role": "user", "content": "查天气"}],
            tools=[{"type": "function", "function": {"name": "get_weather"}}],
            tool_executors={"get_weather": lambda city: json.dumps({"weather": city})},
            max_tool_rounds=5,
        )
        assert result["finish_reason"] == "stop"
        assert result["content"] == "完成"
        assert len(result["tool_call_log"]) == 1
        assert result["tool_call_log"][0]["tool"] == "get_weather"
        # assistant + tool messages must have been appended
        roles = [m["role"] for m in result["messages"]]
        assert roles == ["user", "assistant", "tool"]

    def test_retry_on_500_then_success(self, monkeypatch):
        _enable_compatible(monkeypatch)
        monkeypatch.setenv("STARPLAN_QWEN_RETRIES", "2")
        attempts = {"n": 0}

        def fake_urlopen(request, timeout=None):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise urllib.error.HTTPError(request.full_url, 500, "boom", {}, io.BytesIO(b"{}"))
            return _FakeResp(_choice(content="ok"))

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        result = qc.call_qwen("hi")
        assert result["content"] == "ok"
        assert attempts["n"] == 2

    def test_no_retry_on_403(self, monkeypatch):
        _enable_compatible(monkeypatch)
        monkeypatch.setenv("STARPLAN_QWEN_RETRIES", "3")
        attempts = {"n": 0}

        def fake_urlopen(request, timeout=None):
            attempts["n"] += 1
            raise urllib.error.HTTPError(request.full_url, 403, "denied", {}, io.BytesIO(b"{}"))

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        result = qc.call_qwen("hi")
        assert result["finish_reason"] == "error"
        assert "403" in (result.get("error") or "")
        assert attempts["n"] == 1


class TestNativePathFallback:
    def test_native_dashscope_used_when_compatible_disabled(self, monkeypatch):
        """Without STARPLAN_QWEN_BASE_URL the original Generation path stays."""
        calls = {}

        class _FakeMessage:
            content = "OK"
            tool_calls = None
            finish_reason = "stop"

        class _FakeChoice:
            message = _FakeMessage()
            finish_reason = "stop"

        class _FakeOutput:
            choices = [_FakeChoice()]

        class _FakeResponse:
            status_code = 200
            output = _FakeOutput()
            message = None

        def fake_generation_call(**kwargs):
            calls["kwargs"] = kwargs
            return _FakeResponse()

        monkeypatch.setattr("dashscope.Generation.call", fake_generation_call)
        result = qc.call_qwen("hi", model="qwen3.7-max")
        assert result["content"] == "OK"
        assert calls["kwargs"]["model"] == "qwen3.7-max"
        assert "timeout" in calls["kwargs"]
