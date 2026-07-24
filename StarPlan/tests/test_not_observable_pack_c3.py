"""
StarPlan Loop - C-3 Regression Test: Not-Observable Target Must Not Get Observation Pack

Validates that when a target is not observable (e.g. M42 in July), the
outreach_pack generates a cancellation/alternative pack instead of an
observation activity pack containing "今晚我们观测 M42".

Reference case:
  Target:   M42 (Orion Nebula)
  Location: 四门塔 (36.49N, 117.18E, 300m)
  Date:     2026-07-25
  Expected: is_observable=False, pack_type="not_observable",
            talking points do NOT contain observation language,
            alternative suggestions present (M13, M57).

No API key required.
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starplan_skills.runner import run_starplan
from starplan_skills.schemas import OutreachPack


# ── Shared test input ─────────────────────────────────

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

M42_NOT_OBSERVABLE = {**BASE_INPUT, "target": "M42", "date_range": ["2026-07-25", "2026-07-25"]}
M31_OBSERVABLE = {**BASE_INPUT, "target": "M31", "date_range": ["2026-10-17", "2026-10-17"]}


# ── Fixtures ──────────────────────────────────────────

@pytest.fixture(scope="module")
def m42_result():
    """Run pipeline for M42 (not observable in July)."""
    return run_starplan(M42_NOT_OBSERVABLE, run_id="test_c3_m42_fixture")


@pytest.fixture(scope="module")
def m31_result():
    """Run pipeline for M31 (observable in October)."""
    return run_starplan(M31_OBSERVABLE, run_id="test_c3_m31_fixture")


# ── Tests: not-observable pack ────────────────────────

class TestNotObservablePack:
    """Verify M42 in July gets a cancellation pack, not an observation pack."""

    def test_pack_type_is_not_observable(self, m42_result):
        """The outreach pack should have pack_type='not_observable'."""
        outreach = m42_result.get("outreach_pack")
        assert outreach is not None
        assert outreach["pack_type"] == "not_observable"

    def test_no_observation_language(self, m42_result):
        """Talking points must NOT contain '今晚我们' observation language."""
        outreach = m42_result.get("outreach_pack")
        assert outreach is not None
        forbidden_phrases = ["今晚我们要观测", "今晚我们将", "通过今晚对", "开始观测"]
        all_text = " ".join(outreach["talking_points"])
        for phrase in forbidden_phrases:
            assert phrase not in all_text, (
                f"Found forbidden observation language '{phrase}' in not-observable pack"
            )

    def test_contains_cancellation_language(self, m42_result):
        """Talking points should explain the target is not observable."""
        outreach = m42_result.get("outreach_pack")
        assert outreach is not None
        all_text = " ".join(outreach["talking_points"])
        assert "不满足观测条件" in all_text or "取消" in all_text or "改期" in all_text

    def test_has_alternative_suggestions(self, m42_result):
        """The pack should include alternative target suggestions."""
        outreach = m42_result.get("outreach_pack")
        assert outreach is not None
        assert len(outreach["alternative_suggestions"]) >= 1
        # Should mention M13 or M57 as alternatives
        all_alts = " ".join(outreach["alternative_suggestions"])
        assert "M13" in all_alts or "M57" in all_alts

    def test_alternatives_exclude_target_itself(self, m42_result):
        """Alternative target names in talking points should not include M42."""
        outreach = m42_result.get("outreach_pack")
        assert outreach is not None
        for tp in outreach["talking_points"]:
            if "替代目标" in tp:
                # M42 should not be listed as an alternative to itself
                assert "M42" not in tp or "M13" in tp

    def test_markdown_file_is_cancellation_notice(self, m42_result):
        """The generated markdown should be a cancellation notice, not observation pack."""
        outreach = m42_result.get("outreach_pack")
        assert outreach is not None
        md_path_str = outreach.get("outreach_pack_md_path")
        assert md_path_str is not None
        md_path = Path(md_path_str)
        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "取消" in content or "改期" in content
        assert "今晚我们要观测" not in content
        assert "今晚我们将" not in content

    def test_qwen_not_called_for_not_observable(self, m42_result):
        """Not-observable packs should use template, not Qwen (no API dependency)."""
        outreach = m42_result.get("outreach_pack")
        assert outreach is not None
        assert outreach["qwen_used"] is False


# ── Tests: observable pack unchanged ──────────────────

class TestObservablePackUnchanged:
    """Verify M31 in October still gets a normal observation pack."""

    def test_pack_type_is_observation(self, m31_result):
        """Normal observable target should have pack_type='observation'."""
        outreach = m31_result.get("outreach_pack")
        assert outreach is not None
        assert outreach["pack_type"] == "observation"

    def test_has_observation_talking_points(self, m31_result):
        """Observable pack should contain observation-oriented content."""
        outreach = m31_result.get("outreach_pack")
        assert outreach is not None
        all_text = " ".join(outreach["talking_points"])
        assert "M31" in all_text
        assert len(outreach["talking_points"]) >= 3

    def test_has_equipment_checklist(self, m31_result):
        """Observable pack should have equipment checklist."""
        outreach = m31_result.get("outreach_pack")
        assert outreach is not None
        assert len(outreach["equipment_checklist"]) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
