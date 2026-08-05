"""P2 QoderWork/MCP adapter tests.

Acceptance criteria:
- MCP stdio handshake (initialize / notifications/initialized / ping) works.
- tools/list exposes the unified entry plus the four core Skills.
- UTF-8 Chinese input round-trips through the JSON-RPC stream (no mojibake).
- stdout carries ONLY JSON-RPC lines even when runner prints progress
  diagnostics (MCP stdio framing requirement).
- starplan.run through the MCP layer produces the same public contract as the
  direct runner entry (validation_status/delivery_status/plan/outreach/review).
- Unknown tools and runtime failures fail closed with structured errors.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_SCRIPT = PROJECT_ROOT / "scripts" / "starplan_mcp_server.py"


def _server_env(tmp_path: Path) -> dict:
    env = os.environ.copy()
    env.pop("DASHSCOPE_API_KEY", None)
    env["STARPLAN_MODEL_MODE"] = "offline"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["ASTROPY_CACHE_DIR"] = str(tmp_path / "astropy_cache")
    return env


def _spawn_server(tmp_path: Path) -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, "-X", "utf8", str(SERVER_SCRIPT)],
        cwd=str(PROJECT_ROOT),
        env=_server_env(tmp_path),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None and proc.stdout is not None
    return proc


def _rpc(proc: subprocess.Popen, msg: dict) -> dict:
    assert proc.stdin is not None and proc.stdout is not None
    line = json.dumps(msg, ensure_ascii=False) + "\n"
    proc.stdin.write(line.encode("utf-8"))
    proc.stdin.flush()
    raw = proc.stdout.readline()
    assert raw, "server closed stdout without a response"
    return json.loads(raw.decode("utf-8"))


def _stop_server(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def _load_server_module():
    spec = importlib.util.spec_from_file_location("starplan_mcp_server", SERVER_SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestMcpStdioProtocol:
    def test_initialize_tools_list_and_ping(self, tmp_path):
        proc = _spawn_server(tmp_path)
        try:
            init = _rpc(proc, {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1.0"},
                },
            })
            assert init["result"]["serverInfo"]["name"] == "starplan"
            assert init["result"]["protocolVersion"] == "2024-11-05"

            listing = _rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            names = [t["name"] for t in listing["result"]["tools"]]
            assert "starplan.run" in names
            assert "starplan.run_loop" in names
            for skill in (
                "skill.target_resolve",
                "skill.resolve_location",
                "skill.observability_plan",
                "skill.outreach_pack",
                "skill.observation_review",
            ):
                assert skill in names

            pong = _rpc(proc, {"jsonrpc": "2.0", "id": 3, "method": "ping"})
            assert pong["result"] == {}
        finally:
            _stop_server(proc)

    def test_utf8_chinese_target_round_trip(self, tmp_path):
        proc = _spawn_server(tmp_path)
        try:
            _rpc(proc, {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}},
            })
            resp = _rpc(proc, {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "skill.target_resolve",
                    "arguments": {"target_name": "毕宿五"},
                },
            })
            assert resp.get("result", {}).get("isError") is False
            text = resp["result"]["content"][0]["text"]
            data = json.loads(text)
            assert data["standard_name"] == "Aldebaran"
            assert "毕宿五" in data["aliases"]
        finally:
            _stop_server(proc)

    def test_stdout_contains_only_json_lines_during_full_run(self, tmp_path):
        """Runner progress prints must not corrupt the JSON-RPC stream."""
        proc = _spawn_server(tmp_path)
        try:
            _rpc(proc, {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}},
            })
            input_data = {
                "target": "M31",
                "location": "济南_四门塔",
                "location_detail": {
                    "name": "四门塔景区观星点",
                    "city": "济南",
                    "latitude": 36.49,
                    "longitude": 117.18,
                    "elevation_m": 300,
                    "timezone": "Asia/Shanghai",
                },
                "date_range": ["2026-10-17", "2026-10-17"],
                "audience": "天文社新成员",
                "equipment": "binoculars",
                "goal": "校园科普观测",
                "activity_preferences": {
                    "duration_minutes": 90,
                    "setup_minutes": 15,
                    "cleanup_minutes": 15,
                },
                "audience_profile": {
                    "age_band": "high_school",
                    "experience_level": "beginner",
                    "requested_views": ["organizer", "facilitator", "learner"],
                },
            }
            resp = _rpc(proc, {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "starplan.run", "arguments": {"input": input_data}},
            })
            assert resp.get("result", {}).get("isError") is False, resp
            data = json.loads(resp["result"]["content"][0]["text"])
            assert data["validation_status"] == "passed"
            # Offline mode delivers via the deterministic template path.
            assert data["delivery_status"] in ("delivered", "template")
            assert data["plan_summary"]["is_observable"] is True
            assert data["outreach_pack"]["qwen_used"] is False
            assert data["review"] is None
            assert data["run_dir"]

            # Any diagnostic text from runner must have gone to stderr, not
            # stdout. The response above parsed as JSON only because the
            # stream was clean; sending another request proves the framing
            # survives after a full pipeline run too.
            pong = _rpc(proc, {"jsonrpc": "2.0", "id": 3, "method": "ping"})
            assert pong["result"] == {}
        finally:
            _stop_server(proc)
            if proc.stderr is not None:
                stderr = proc.stderr.read().decode("utf-8", errors="replace")
                assert "astronomy_runtime=" in stderr

    def test_unknown_tool_fails_closed(self, tmp_path):
        proc = _spawn_server(tmp_path)
        try:
            _rpc(proc, {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}},
            })
            resp = _rpc(proc, {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "skill.not_exist", "arguments": {}},
            })
            assert resp["result"]["isError"] is True
            payload = json.loads(resp["result"]["content"][0]["text"])
            assert "Unknown tool" in payload["error"]
        finally:
            _stop_server(proc)


class TestMcpHandleUnit:
    def test_starplan_run_via_handle_matches_public_contract(self, tmp_path):
        mod = _load_server_module()
        input_data = {
            "target": "M31",
            "location": "济南_四门塔",
            "location_detail": {
                "name": "四门塔景区观星点",
                "city": "济南",
                "latitude": 36.49,
                "longitude": 117.18,
                "elevation_m": 300,
                "timezone": "Asia/Shanghai",
            },
            "date_range": ["2026-10-17", "2026-10-17"],
            "audience": "天文社新成员",
            "equipment": "binoculars",
            "goal": "校园科普观测",
            "activity_preferences": {
                "duration_minutes": 90,
                "setup_minutes": 15,
                "cleanup_minutes": 15,
            },
            "audience_profile": {
                "age_band": "high_school",
                "experience_level": "beginner",
                "requested_views": ["organizer", "facilitator", "learner"],
            },
        }

        def fake_get_run_dir(run_id: str) -> Path:
            target = tmp_path / (run_id or "mcp_handle_test")
            target.mkdir(parents=True, exist_ok=True)
            return target

        with patch("starplan_skills.runner.get_run_dir", side_effect=fake_get_run_dir), \
             patch("starplan_skills.outreach_pack._qwen_available", return_value=False):
            resp = mod._handle({
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "starplan.run", "arguments": {"input": input_data}},
            })

        assert resp is not None
        assert resp["id"] == 7
        assert resp["result"]["isError"] is False
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["validation_status"] == "passed"
        assert data["delivery_status"] in ("delivered", "template")
        assert data["plan_summary"]["is_observable"] is True
        assert sorted(data["outreach_pack"]["rendered_views"].keys()) == [
            "facilitator", "learner", "organizer",
        ]
        assert data["review"] is None
        assert data["run_dir"].startswith(str(tmp_path))

    def test_run_loop_summary_with_mocked_runner(self, tmp_path):
        mod = _load_server_module()
        next_path = tmp_path / "next_activity_input.json"
        next_path.write_text(
            json.dumps({"target": "M31", "date_range": ["2026-10-18", "2026-10-18"]}),
            encoding="utf-8",
        )

        def fake_run_starplan(input_data, run_id=None):
            if run_id is None:
                return {
                    "run_id": "first",
                    "validation_status": "passed",
                    "plan": {"activity_slot": {"start": "2026-10-17T19:13:00"}},
                    "review": {
                        "next_input_path": str(next_path),
                        "revised_plan_diff": [{"cause_id": "cause.team_late"}],
                    },
                }
            return {
                "run_id": "first_next",
                "validation_status": "passed",
                "plan": {"activity_slot": {"start": "2026-10-18T19:30:00"}},
            }

        with patch.object(mod, "run_starplan", side_effect=fake_run_starplan):
            resp = mod._handle({
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {
                    "name": "starplan.run_loop",
                    "arguments": {"input": {"target": "M31"}},
                },
            })

        assert resp["result"]["isError"] is False
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["first_run_id"] == "first"
        assert data["second_run_id"] == "first_next"
        assert data["next_input_path"] == str(next_path)
        assert data["activity_slot_before"]["start"] == "2026-10-17T19:13:00"
        assert data["activity_slot_after"]["start"] == "2026-10-18T19:30:00"
        assert data["revised_plan_diff"] == [{"cause_id": "cause.team_late"}]

    def test_malformed_json_returns_parse_error(self, tmp_path):
        proc = _spawn_server(tmp_path)
        try:
            assert proc.stdin is not None and proc.stdout is not None
            proc.stdin.write(b"this is not json\n")
            proc.stdin.flush()
            raw = proc.stdout.readline()
            resp = json.loads(raw.decode("utf-8"))
            assert resp["error"]["code"] == -32700
        finally:
            _stop_server(proc)
