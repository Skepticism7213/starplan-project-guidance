"""
StarPlan Loop - W-10: Qwen Integration Tests

End-to-end tests that verify the Qwen-dependent paths actually work:
  - NL parsing produces a valid StarPlanInput
  - Outreach pack Qwen mode generates validated talking points
  - Chat mode tool-calling reaches a final summary with hallucination check
  - model_call_log.jsonl records Qwen calls

Requirements:
  - DASHSCOPE_API_KEY must be set (in .env or environment).
  - Network access to Alibaba Cloud Bailian API.

These tests are SKIPPED (not failed) when the API key is unavailable,
so they are safe to include in a full pytest run.

No astronomical computation is tested here (covered by other test files).
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starplan_skills.qwen_client import call_qwen, call_qwen_json, DEFAULT_MODEL


# ── Skip condition ────────────────────────────────────

def _qwen_available() -> bool:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    key = os.getenv("DASHSCOPE_API_KEY", "")
    return bool(key) and not key.startswith("sk-在此") and key != "your_api_key_here"


def _model_mode_offline() -> bool:
    """R-01 fix: STARPLAN_MODEL_MODE=offline must take priority over .env Key.

    qwen_client._assert_online() raises a tripwire for any network call in
    offline mode, so these integration tests must skip (not fail) when the
    offline gate is active — even on machines that have a valid Key.
    """
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    return os.getenv("STARPLAN_MODEL_MODE", "online") == "offline"


requires_qwen = pytest.mark.skipif(
    (not _qwen_available()) or _model_mode_offline(),
    reason=(
        "Qwen integration tests skipped: DASHSCOPE_API_KEY missing or "
        "STARPLAN_MODEL_MODE=offline (offline gate must not touch network)"
    ),
)


# ── Test: basic connectivity ──────────────────────────

@requires_qwen
class TestQwenConnectivity:
    """Verify the API key works and models respond."""

    def test_single_turn_call(self):
        """call_qwen returns non-empty content."""
        result = call_qwen("回复'OK'两个字母即可。", step_name="test_connectivity")
        assert result.get("content"), "Qwen returned empty content"
        assert len(result["content"]) > 0

    def test_json_mode(self):
        """call_qwen_json returns parseable JSON."""
        result = call_qwen_json(
            prompt='返回 JSON: {"status": "ok", "number": 42}',
            system_prompt="只返回 JSON，不要其他文字。",
            step_name="test_json_mode",
        )
        parsed = result.get("parsed_json")
        assert parsed is not None, f"JSON parse failed, content: {result.get('content', '')[:100]}"
        assert parsed.get("status") == "ok"


# ── Test: NL parsing end-to-end ───────────────────────

@requires_qwen
class TestNLParsing:
    """Verify run_starplan_nl parses natural language to valid input."""

    def test_nl_parse_produces_valid_input(self):
        """NL parser extracts target, location, date from free text."""
        from starplan_skills.nl_parser import parse_natural_language

        text = "我想在10月17号晚上带天文社新成员去济南四门塔看仙女座星系，用双筒望远镜"
        result = parse_natural_language(text)

        assert result.target, "target should not be empty"
        assert "M31" in result.target or "仙女座" in result.target
        assert result.location, "location should not be empty"
        assert len(result.date_range) >= 1

    def test_nl_parse_logs_to_file(self, tmp_path):
        """NL parse writes a model_call entry to the specified log_path."""
        from starplan_skills.nl_parser import parse_natural_language

        log_file = tmp_path / "model_call_log.jsonl"
        text = "帮我看看M42在7月25号济南能不能观测"
        parse_natural_language(text, log_path=str(log_file))

        assert log_file.exists(), "log file was not created"
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert "nl_parse" in entry.get("step", "") or "model_call" in entry.get("type", "")


# ── Test: outreach Qwen mode ──────────────────────────

@requires_qwen
class TestOutreachQwenMode:
    """Verify outreach pack Qwen generation + hallucination validation."""

    def test_qwen_generates_talking_points(self):
        """Qwen mode produces validated talking points for M31."""
        from starplan_skills.target_resolve import resolve_target
        from starplan_skills.observability_plan import compute_observability
        from starplan_skills.outreach_pack import generate_outreach_pack

        target = resolve_target("M31")
        obs = compute_observability(
            ra_deg=target.ra_deg,
            dec_deg=target.dec_deg,
            target_name="M31",
            location={
                "name": "四门塔",
                "latitude": 36.49,
                "longitude": 117.18,
                "elevation_m": 300,
                "timezone": "Asia/Shanghai",
            },
            date_range=["2026-10-17", "2026-10-17"],
            equipment="binoculars",
        )
        pack = generate_outreach_pack(
            target=target,
            obs_result=obs,
            audience="天文社新成员",
            equipment="binoculars",
            use_qwen=True,
        )
        assert pack.qwen_used is True, "Qwen should have been used"
        assert len(pack.talking_points) >= 3, "Should have at least 3 talking points"
        # All talking points should have passed validation (no untraceable numbers)
        # If validation removed some, that's fine — but we should still have content


# ── Test: chat mode hallucination guardrail ────────────

@requires_qwen
class TestChatHallucinationGuard:
    """Verify chat mode runs tools and applies hallucination check.

    Phase B (W-02): updated to current public API contract.
    """

    def test_chat_reaches_final_summary(self):
        """Chat mode calls tools and produces a Claim-rendered summary."""
        from starplan_skills.runner import run_starplan_chat

        result = run_starplan_chat(
            "帮我规划10月17号在济南四门塔观测M31",
            run_id="test_chat_integration",
        )
        assert result.get("final_content"), "Should have final content"
        # Phase B: public API uses tools_called (list of strings)
        tools = result.get("tools_called", [])
        assert len(tools) >= 2, f"Should call at least 2 tools, got {tools}"

        # Phase B: model text is NEVER accepted for delivery
        assert result.get("model_text_accepted_for_delivery") is False

        # Phase B: model_call_count should be > 0 (W-01)
        assert result.get("model_call_count", 0) > 0, "Should record model calls"

        # Phase B: public output validation
        assert result.get("public_output_validation") in ("passed", "blocked")

    def test_chat_tools_include_resolve_and_plan(self):
        """Chat mode calls target_resolve and observability_plan."""
        from starplan_skills.runner import run_starplan_chat

        result = run_starplan_chat(
            "我想看仙女座星系，在济南四门塔，10月17号",
            run_id="test_chat_tools",
        )
        # Phase B: use tools_called from public return
        tools_called = result.get("tools_called", [])
        assert "target_resolve" in tools_called
        assert "observability_plan" in tools_called

    def test_chat_produces_claim_artifacts(self):
        """Phase B: Chat run produces full Claim artifacts (same as structured)."""
        from pathlib import Path
        from starplan_skills.runner import run_starplan_chat

        result = run_starplan_chat(
            "帮我规划10月17号在济南四门塔观测M31",
            run_id="test_chat_artifacts",
        )
        run_dir = Path(result["run_dir"])
        # Phase B: Chat must produce same artifacts as structured mode
        assert (run_dir / "claims.json").exists(), "Chat must produce claims.json"
        assert (run_dir / "render_trace.json").exists(), "Chat must produce render_trace.json"
        assert (run_dir / "rendered_document.json").exists(), "Chat must produce rendered_document.json"
        assert (run_dir / "run_outcome.json").exists(), "Chat must produce run_outcome.json"
        assert (run_dir / "outreach_pack.md").exists(), "Chat must produce outreach_pack.md"

    def test_chat_blocked_content_not_in_output(self):
        """Phase B: Qwen raw text (blocked_content) must not leak into final_content."""
        from pathlib import Path
        import json
        from starplan_skills.runner import run_starplan_chat

        result = run_starplan_chat(
            "帮我规划10月17号在济南四门塔观测M31",
            run_id="test_chat_leak",
        )
        run_dir = Path(result["run_dir"])
        # Read blocked_content from audit log
        conv = json.loads((run_dir / "chat_conversation.json").read_text(encoding="utf-8"))
        blocked = conv.get("blocked_content", "")
        final = result["final_content"]
        # If blocked content is substantial, verify no 20-char substring leaks
        if len(blocked) > 40:
            for i in range(0, min(len(blocked), 100) - 20, 10):
                snippet = blocked[i:i + 20]
                assert snippet not in final, f"Blocked content leaked: '{snippet}'"
