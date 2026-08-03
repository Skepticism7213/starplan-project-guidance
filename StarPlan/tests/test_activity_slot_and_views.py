"""P1 Batch D tests: realistic activity slot + three audience views + youth policy.

Acceptance criteria covered:
- M31 gets a 60-120 min realistic activity slot inside the science window.
- M42 (not observable) gets NO fake activity slot.
- organizer/facilitator/learner views share the same Claim IDs for facts.
- youth_activity_policy_v1 adds supervision/consent items for minor audiences,
  and the runner/validator rebuild stays consistent (no saved-registry drift).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from starplan_skills.observability_plan import select_activity_slot
from starplan_skills.schemas import (
    ActivityPreferences,
    MoonInfo,
    ObservabilityResult,
    RecommendedWindow,
    TimeWindow,
    TwilightInfo,
)


CASE_M31 = {
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
}


def _obs_with_window(start, end) -> ObservabilityResult:
    return ObservabilityResult(
        is_observable=True,
        target_name="M31",
        location_name="四门塔景区观星点",
        date_range=[date(2026, 10, 17)],
        recommended_window=RecommendedWindow(
            window=TimeWindow(start=start, end=end, duration_minutes=(end - start).total_seconds() / 60),
            peak_altitude_deg=72.5,
            peak_airmass=1.05,
            reason="test",
        ),
        twilight=TwilightInfo(
            astronomical_twilight_end=start - timedelta(minutes=15),
            astronomical_twilight_start=end + timedelta(minutes=30),
        ),
        moon_info=MoonInfo(phase_fraction=0.3, min_separation_deg=60.0, impact_assessment="low"),
    )


class TestActivitySlotPolicy:
    def test_default_90min_slot_inside_science_window(self):
        start = datetime(2026, 10, 17, 19, 13)
        end = datetime(2026, 10, 18, 4, 28)
        obs = _obs_with_window(start, end)
        slot = select_activity_slot(obs.recommended_window, obs.twilight)
        assert slot is not None
        assert slot.duration_minutes == 90
        assert slot.start == start
        assert slot.end == start + timedelta(minutes=90)
        assert slot.setup_start == start - timedelta(minutes=15)
        assert slot.cleanup_end == slot.end + timedelta(minutes=15)
        assert slot.rule_version == "activity_slot_policy_v1"

    def test_preferred_start_used_when_it_fits(self):
        start = datetime(2026, 10, 17, 19, 13)
        end = datetime(2026, 10, 18, 4, 28)
        obs = _obs_with_window(start, end)
        pref = {"duration_minutes": 90, "preferred_start": "2026-10-17T20:30:00"}
        slot = select_activity_slot(obs.recommended_window, obs.twilight, pref)
        assert slot is not None
        assert slot.start == datetime(2026, 10, 17, 20, 30)
        assert slot.end == datetime(2026, 10, 17, 22, 0)

    def test_latest_end_clamps_start_backward(self):
        start = datetime(2026, 10, 17, 19, 13)
        end = datetime(2026, 10, 18, 4, 28)
        obs = _obs_with_window(start, end)
        pref = {
            "duration_minutes": 120,
            "preferred_start": "2026-10-17T23:00:00",
            "latest_end": "2026-10-17T22:00:00",
        }
        slot = select_activity_slot(obs.recommended_window, obs.twilight, pref)
        assert slot is not None
        assert slot.start == datetime(2026, 10, 17, 20, 0)
        assert slot.end == datetime(2026, 10, 17, 22, 0)

    def test_no_slot_when_window_too_short(self):
        start = datetime(2026, 10, 17, 19, 13)
        end = datetime(2026, 10, 17, 20, 0)  # 47 min < 60 min minimum
        obs = _obs_with_window(start, end)
        slot = select_activity_slot(obs.recommended_window, obs.twilight)
        assert slot is None

    def test_no_slot_without_recommended_window(self):
        obs = ObservabilityResult(
            is_observable=False,
            target_name="M42",
            location_name="四门塔景区观星点",
            date_range=[date(2026, 7, 25)],
            twilight=TwilightInfo(),
            moon_info=MoonInfo(phase_fraction=0.8),
        )
        assert select_activity_slot(obs.recommended_window, obs.twilight) is None


def _run_case(tmp_path, extra=None):
    from starplan_skills import runner

    run_dir = tmp_path / "run"
    data = dict(CASE_M31)
    if extra:
        data.update(extra)

    def fake_get_run_dir(run_id: str) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    with patch("starplan_skills.runner.get_run_dir", side_effect=fake_get_run_dir), \
         patch("starplan_skills.outreach_pack._qwen_available", return_value=False):
        result = runner.run_starplan(data, run_id="batch_d_test")
    return result, run_dir


class TestRunnerBatchD:
    def test_case1_gets_realistic_slot_and_three_views(self, tmp_path):
        extra = {
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
        result, run_dir = _run_case(tmp_path, extra)
        assert result["validation_status"] == "passed", result
        assert result["plan"]["activity_slot"] is not None
        assert result["plan"]["activity_slot"]["duration_minutes"] == 90
        assert (run_dir / "outreach_pack.md").exists()
        assert (run_dir / "outreach_pack_facilitator.md").exists()
        assert (run_dir / "outreach_pack_learner.md").exists()
        assert (run_dir / "rendered_document_learner.json").exists()
        assert (run_dir / "render_trace_learner.json").exists()

        md = (run_dir / "outreach_pack.md").read_text(encoding="utf-8")
        # Schedule must use the realistic slot, not the 9-hour science window.
        assert "活动观测部分预计于" in md or "活动观测部分结束" in md
        assert "20:43" in md  # 19:13 + 90 min

    def test_views_share_numeric_claims(self, tmp_path):
        extra = {
            "audience_profile": {
                "age_band": "high_school",
                "experience_level": "beginner",
                "requested_views": ["organizer", "learner"],
            }
        }
        _, run_dir = _run_case(tmp_path, extra)

        def claim_ids(trace_path):
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            return {
                cid
                for entry in trace["sentences"]
                for cid in entry.get("claim_ids", [])
            }

        organizer = claim_ids(run_dir / "render_trace.json")
        learner = claim_ids(run_dir / "render_trace_learner.json")
        for cid in (
            "target.standard_name",
            "target.visual_magnitude",
            "obs.recommended_window",
            "obs.peak_altitude",
            "activity.slot_start",
            "activity.slot_end",
        ):
            assert cid in organizer, f"organizer missing {cid}"
            assert cid in learner, f"learner missing {cid}"
        # learner excludes equipment/manual sections by design
        assert "equipment.binoculars" not in learner

    def test_youth_policy_applies_and_delivery_passes(self, tmp_path):
        extra = {
            "audience_profile": {
                "age_band": "kids",
                "experience_level": "beginner",
                "requested_views": ["organizer"],
            }
        }
        result, run_dir = _run_case(tmp_path, extra)
        assert result["validation_status"] == "passed", result
        assert result["outreach_pack"]["youth_policy_applied"] is True
        claims = json.loads((run_dir / "claims.json").read_text(encoding="utf-8"))
        ids = {c["claim_id"] for c in claims["claims"]}
        assert "safety.youth_supervision" in ids
        assert "manual_check.youth_consent" in ids
        md = (run_dir / "outreach_pack.md").read_text(encoding="utf-8")
        assert "监护人" in md
        # No PII collection fields in the schema/output
        assert "身份证" not in md and "手机号" not in md

    def test_m42_has_no_fake_activity_slot(self, tmp_path):
        from starplan_skills import runner

        run_dir = tmp_path / "run_m42"
        data = {
            "target": "M42",
            "location": "济南_四门塔",
            "location_detail": {
                "name": "四门塔景区观星点",
                "city": "济南",
                "latitude": 36.49,
                "longitude": 117.18,
                "elevation_m": 300,
                "timezone": "Asia/Shanghai",
            },
            "date_range": ["2026-07-25", "2026-07-25"],
            "audience": "天文社新成员",
            "equipment": "binoculars",
            "goal": "校园科普观测",
            "audience_profile": {
                "age_band": "high_school",
                "experience_level": "beginner",
                "requested_views": ["organizer", "learner"],
            },
        }

        def fake_get_run_dir(run_id: str) -> Path:
            run_dir.mkdir(parents=True, exist_ok=True)
            return run_dir

        with patch("starplan_skills.runner.get_run_dir", side_effect=fake_get_run_dir), \
             patch("starplan_skills.outreach_pack._qwen_available", return_value=False):
            result = runner.run_starplan(data, run_id="batch_d_m42")
        assert result["validation_status"] == "passed"
        assert result["plan"]["activity_slot"] is None
        assert result["outreach_pack"]["pack_type"] == "not_observable"
        assert not (run_dir / "outreach_pack_learner.md").exists()

    def test_adult_audience_without_profile_stays_organizer_only(self, tmp_path):
        result, run_dir = _run_case(tmp_path)
        assert result["validation_status"] == "passed"
        assert not (run_dir / "outreach_pack_learner.md").exists()
        assert result["outreach_pack"]["youth_policy_applied"] is False
