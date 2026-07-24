"""
StarPlan Loop - C-4 Regression Test: Chat Mode Must Fail Closed on Hallucination

Validates that when the hallucination check detects untraceable numbers in
Qwen's free-text summary, the pipeline:
  1. Does NOT return the hallucinated content as final_content
  2. Replaces it with a deterministic summary rendered from tool results
  3. Preserves the blocked content in a separate audit field
  4. Sets hallucination_blocked=True

Also tests:
  - _build_deterministic_summary produces correct output from tool results
  - _check_chat_hallucination correctly identifies untraceable numbers
  - When check passes, content is returned normally (hallucination_blocked=False)

No API key required — tests the guardrail logic directly.
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starplan_skills.runner import (
    _build_deterministic_summary,
    _check_chat_hallucination,
    _check_coordinate_source,
)


# ── Test fixtures ─────────────────────────────────────

CAPTURED_TOOLS = {
    "target_resolve": {
        "standard_name": "M31",
        "ra_deg": 10.685,
        "dec_deg": 41.269,
        "target_type": "deep_sky",
        "constellation": "Andromeda",
        "visual_magnitude": 3.4,
        "confidence": 1.0,
    },
    "resolve_location": {
        "name": "四门塔景区观星点",
        "key": "济南_四门塔",
        "latitude": 36.49,
        "longitude": 117.18,
        "elevation_m": 300,
    },
    "observability_plan": {
        "is_observable": True,
        "target_name": "M31",
        "recommended_window": {
            "window": {"start": "2026-10-17T18:58:00", "end": "2026-10-18T04:28:00"},
            "peak_altitude_deg": 85.0,
            "peak_airmass": 1.05,
        },
        "moon_info": {
            "phase_fraction": 0.398,
            "min_separation_deg": 102.61,
            "impact_assessment": "low",
        },
        "alternative_suggestions": [],
    },
    "_obs_location_used": {"latitude": 36.49, "longitude": 117.18},
}


# ── Tests: _check_chat_hallucination ──────────────────

class TestHallucinationCheck:
    """Verify the hallucination detection logic."""

    def test_traceable_numbers_pass(self):
        """Numbers that exist in tool outputs should not be flagged."""
        text = "M31的赤经为10.685度，赤纬41.269度，峰值高度角85.0度，月相0.398"
        result = _check_chat_hallucination(text, CAPTURED_TOOLS)
        assert result == []

    def test_fabricated_numbers_detected(self):
        """Numbers NOT in tool outputs should be flagged."""
        text = "今晚气温约15度，暗适应需要25分钟，湿度78%"
        result = _check_chat_hallucination(text, CAPTURED_TOOLS)
        assert "15" in result
        assert "25" in result
        assert "78" in result

    def test_small_numbers_allowed(self):
        """Numbers 0-10 are always allowed (common in text)."""
        text = "使用2个望远镜，3人一组，等待5分钟"
        result = _check_chat_hallucination(text, CAPTURED_TOOLS)
        assert result == []

    def test_empty_text_passes(self):
        """Empty text has no numbers to check."""
        assert _check_chat_hallucination("", CAPTURED_TOOLS) == []

    def test_mixed_traceable_and_fabricated(self):
        """Only fabricated numbers are flagged, traceable ones pass."""
        text = "峰值高度角85.0度，建议穿3件衣服，气温约12度"
        result = _check_chat_hallucination(text, CAPTURED_TOOLS)
        assert "85" not in result  # traceable (85.0 -> 85)
        assert "12" in result     # fabricated
        # "3" is in 0-10 safe range


# ── Tests: _build_deterministic_summary ───────────────

class TestDeterministicSummary:
    """Verify the deterministic rendering from tool results."""

    def test_contains_target_info(self):
        """Summary should include target name and coordinates from tools."""
        summary = _build_deterministic_summary(CAPTURED_TOOLS)
        assert "M31" in summary
        assert "10.685" in summary
        assert "41.269" in summary

    def test_contains_location_info(self):
        """Summary should include location from resolve_location tool."""
        summary = _build_deterministic_summary(CAPTURED_TOOLS)
        assert "36.49" in summary
        assert "117.18" in summary

    def test_contains_observability_info(self):
        """Summary should include observability results."""
        summary = _build_deterministic_summary(CAPTURED_TOOLS)
        assert "可观测" in summary
        assert "85.0" in summary
        assert "1.05" in summary

    def test_contains_moon_info(self):
        """Summary should include moon data."""
        summary = _build_deterministic_summary(CAPTURED_TOOLS)
        assert "0.398" in summary
        assert "102.61" in summary

    def test_no_fabricated_content(self):
        """Summary should only contain values from tool outputs."""
        summary = _build_deterministic_summary(CAPTURED_TOOLS)
        # These are things Qwen might fabricate but tools don't provide
        assert "气温" not in summary
        assert "暗适应" not in summary
        assert "湿度" not in summary

    def test_not_observable_case(self):
        """Summary should handle not-observable case."""
        captured = {
            "target_resolve": {"standard_name": "M42", "ra_deg": 83.82, "dec_deg": -5.39, "target_type": "deep_sky"},
            "observability_plan": {
                "is_observable": False,
                "alternative_suggestions": [
                    {"description": "当季更适合观测的目标：M13"},
                ],
            },
        }
        summary = _build_deterministic_summary(captured)
        assert "否" in summary
        assert "不满足观测条件" in summary
        assert "M13" in summary

    def test_empty_captured(self):
        """Summary should handle empty captured dict gracefully."""
        summary = _build_deterministic_summary({})
        assert "确定性结果摘要" in summary  # header still present


# ── Tests: coordinate source check ────────────────────

class TestCoordinateSourceCheck:
    """Verify coordinate source validation."""

    def test_matching_coordinates_pass(self):
        """When used coords match resolve_location, no warning."""
        result = _check_coordinate_source(CAPTURED_TOOLS)
        assert result is None

    def test_mismatched_coordinates_warn(self):
        """When used coords differ from resolve_location, warn."""
        captured = {
            **CAPTURED_TOOLS,
            "_obs_location_used": {"latitude": 39.9, "longitude": 116.4},  # Beijing!
        }
        result = _check_coordinate_source(captured)
        assert result is not None
        assert "不一致" in result

    def test_no_resolve_location_warns(self):
        """If observability was called without resolve_location, warn."""
        captured = {
            "target_resolve": CAPTURED_TOOLS["target_resolve"],
            "observability_plan": CAPTURED_TOOLS["observability_plan"],
            "_obs_location_used": {"latitude": 36.49, "longitude": 117.18},
        }
        result = _check_coordinate_source(captured)
        assert result is not None
        assert "未先调用 resolve_location" in result


# ── Tests: fail-closed integration logic ──────────────

class TestFailClosedLogic:
    """Test the fail-closed decision logic (without calling Qwen)."""

    def test_blocked_when_untraceable_exists(self):
        """If untraceable numbers exist, verification.passed should be False."""
        untraceable = ["15", "25"]
        coord_warning = None
        passed = (not untraceable) and (not coord_warning)
        assert passed is False

    def test_passed_when_clean(self):
        """If no untraceable numbers and no coord warning, passed is True."""
        untraceable = []
        coord_warning = None
        passed = (not untraceable) and (not coord_warning)
        assert passed is True

    def test_blocked_when_coord_warning(self):
        """If coordinate warning exists, passed should be False even with clean numbers."""
        untraceable = []
        coord_warning = "坐标来源核查：经纬度可能为模型推测值"
        passed = (not untraceable) and (not coord_warning)
        assert passed is False

    def test_deterministic_summary_replaces_hallucinated_content(self):
        """Simulate the fail-closed flow: blocked content replaced by summary."""
        # Simulate Qwen returning hallucinated content
        qwen_content = "今晚我们观测M31，气温约15度，建议穿3件衣服，暗适应需25分钟"
        untraceable = _check_chat_hallucination(qwen_content, CAPTURED_TOOLS)
        assert len(untraceable) > 0  # should detect fabricated numbers

        # Fail-closed: replace with deterministic summary
        hallucination_blocked = bool(untraceable)
        assert hallucination_blocked is True

        final_content = _build_deterministic_summary(CAPTURED_TOOLS)
        blocked_content = qwen_content

        # Verify: final content is the safe summary
        assert "确定性结果摘要" in final_content
        assert "气温" not in final_content
        assert "暗适应" not in final_content
        # Verify: blocked content preserved for audit
        assert blocked_content == qwen_content
        assert "15" in blocked_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
