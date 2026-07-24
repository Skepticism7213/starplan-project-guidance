"""
StarPlan Loop - C-2 Regression Test: Ambiguous Target Must Halt Pipeline

Validates that run_starplan() raises TargetConfirmationRequired when
target_resolve returns requires_confirmation=True with confidence > 0,
instead of silently proceeding with the best guess.

Reference case:
  Input:    "三角座" (Triangulum)
  Expected: resolve_target returns M33 with confidence ~0.85,
            requires_confirmation=True, candidates include M33.
  Old bug:  Pipeline printed a warning but continued, auto-selecting M33.
  Fix:      Pipeline raises TargetConfirmationRequired, halting execution.

Also tests:
  - confirmed_target bypass works (human already chose)
  - confidence=0 still raises ValueError (not found)
  - Normal unambiguous targets (M31) are unaffected

No API key required.
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starplan_skills.target_resolve import resolve_target
from starplan_skills.exceptions import TargetConfirmationRequired
from starplan_skills.runner import run_starplan


# ── Shared test input template ────────────────────────

BASE_INPUT = {
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
    "constraints": {
        "min_altitude_deg": 30,
        "max_airmass": 2.0,
        "prefer_early_night": False,
        "max_moon_illumination": None,
    },
}


# ── Tests: target_resolve behavior ────────────────────

class TestResolveTargetAmbiguity:
    """Verify target_resolve correctly flags ambiguous inputs."""

    def test_triangulum_is_ambiguous(self):
        """'三角座' should return requires_confirmation=True with candidates."""
        result = resolve_target("三角座")
        assert result.requires_confirmation is True
        assert result.confidence > 0
        assert result.confidence < 0.9
        assert result.candidates is not None
        assert len(result.candidates) >= 1

    def test_triangulum_candidates_include_m33(self):
        """M33 (Triangulum Galaxy) should be among the candidates."""
        result = resolve_target("三角座")
        candidate_names = [c.standard_name for c in result.candidates]
        assert "M33" in candidate_names

    def test_m31_is_unambiguous(self):
        """'M31' should resolve cleanly without confirmation."""
        result = resolve_target("M31")
        assert result.requires_confirmation is False
        assert result.confidence >= 0.9
        assert result.standard_name == "M31"

    def test_nonexistent_target_zero_confidence(self):
        """A completely unknown name should have confidence=0."""
        result = resolve_target("不存在的天体XYZ123")
        assert result.requires_confirmation is True
        assert result.confidence == 0


# ── Tests: pipeline halts on ambiguity ────────────────

class TestPipelineHaltsOnAmbiguity:
    """Verify run_starplan raises TargetConfirmationRequired for ambiguous targets."""

    def test_ambiguous_target_raises_exception(self):
        """run_starplan with '三角座' must raise TargetConfirmationRequired."""
        input_data = {**BASE_INPUT, "target": "三角座"}
        with pytest.raises(TargetConfirmationRequired) as exc_info:
            run_starplan(input_data, run_id="test_c2_ambiguous")

        # Exception should carry the resolved target with candidates
        exc = exc_info.value
        assert exc.resolved is not None
        assert exc.resolved.requires_confirmation is True
        assert len(exc.candidates) >= 1

    def test_exception_message_is_informative(self):
        """The exception message should mention the target and candidate count."""
        input_data = {**BASE_INPUT, "target": "三角座"}
        with pytest.raises(TargetConfirmationRequired) as exc_info:
            run_starplan(input_data, run_id="test_c2_msg")

        msg = str(exc_info.value)
        assert "三角座" in msg
        assert "ambiguous" in msg.lower() or "歧义" in msg
        assert "confirmed_target" in msg

    def test_format_candidates_helper(self):
        """The exception's format_candidates() should produce a readable list."""
        input_data = {**BASE_INPUT, "target": "三角座"}
        with pytest.raises(TargetConfirmationRequired) as exc_info:
            run_starplan(input_data, run_id="test_c2_fmt")

        formatted = exc_info.value.format_candidates()
        assert "M33" in formatted
        assert "1." in formatted  # numbered list

    def test_not_found_raises_valueerror_not_confirmation(self):
        """confidence=0 (not found) should raise ValueError, not TargetConfirmationRequired."""
        input_data = {**BASE_INPUT, "target": "不存在的天体XYZ123"}
        with pytest.raises(ValueError, match="not found"):
            run_starplan(input_data, run_id="test_c2_notfound")


# ── Tests: confirmed_target bypass ────────────────────

class TestConfirmedTargetBypass:
    """Verify that confirmed_target allows the pipeline to proceed."""

    def test_confirmed_target_proceeds(self):
        """With confirmed_target='M33', pipeline should run without exception."""
        input_data = {**BASE_INPUT, "target": "三角座", "confirmed_target": "M33"}
        # Should not raise — M33 is a valid unambiguous target
        result = run_starplan(input_data, run_id="test_c2_confirmed")
        assert result is not None
        assert "plan" in result or "target" in result

    def test_confirmed_target_still_ambiguous_raises(self):
        """If confirmed_target itself is ambiguous, raise ValueError."""
        input_data = {**BASE_INPUT, "target": "三角座", "confirmed_target": "三角座"}
        with pytest.raises(ValueError, match="still ambiguous"):
            run_starplan(input_data, run_id="test_c2_confirmed_ambig")

    def test_normal_target_unaffected(self):
        """M31 (unambiguous) should work normally without confirmed_target."""
        input_data = {**BASE_INPUT, "target": "M31"}
        result = run_starplan(input_data, run_id="test_c2_normal")
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
