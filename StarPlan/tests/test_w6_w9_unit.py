"""
StarPlan Loop - W-6~W-9 Regression Tests (pytest)

Covers:
  W-8: Timezone support (zoneinfo, DST, invalid tz rejection)
  W-6: Moon constraint logic (OR semantics, moon below horizon)
  W-7: Config consistency (buffer_minutes, nights_computed field)
  W-9: observation_log in unified Schema (extra=forbid, validation)
"""
import json
import sys
from datetime import datetime, date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starplan_skills.observability_plan import _tz_offset_hours, compute_observability
from starplan_skills.schemas import StarPlanInput, ObservationLog


# ── W-8: Timezone ──────────────────────────────────

class TestW8Timezone:
    def test_shanghai(self):
        assert _tz_offset_hours("Asia/Shanghai") == 8.0

    def test_tokyo(self):
        assert _tz_offset_hours("Asia/Tokyo") == 9.0

    def test_utc(self):
        assert _tz_offset_hours("UTC") == 0.0

    def test_new_york_summer_dst(self):
        offset = _tz_offset_hours("America/New_York", datetime(2026, 7, 25))
        assert abs(offset - (-4.0)) < 0.01

    def test_new_york_winter(self):
        offset = _tz_offset_hours("America/New_York", datetime(2026, 1, 15))
        assert abs(offset - (-5.0)) < 0.01

    def test_invalid_timezone_raises(self):
        with pytest.raises(ValueError, match="Invalid IANA timezone"):
            _tz_offset_hours("Mars/Olympus")

    def test_london_summer_bst(self):
        offset = _tz_offset_hours("Europe/London", datetime(2026, 7, 1))
        assert abs(offset - 1.0) < 0.01


# ── W-6: Moon constraint logic ─────────────────────

class TestW6MoonLogic:
    """Test moon constraint via compute_observability with controlled inputs."""

    def _run_obs(self, constraints=None, date_str="2026-10-17"):
        location = {
            "name": "test", "latitude": 36.49, "longitude": 117.18,
            "elevation_m": 300, "timezone": "Asia/Shanghai",
        }
        return compute_observability(
            ra_deg=10.68, dec_deg=41.27, target_name="M31",
            location=location, date_range=[date_str, date_str],
            equipment="binoculars", constraints=constraints,
        )

    def test_default_moon_logic_runs(self):
        result = self._run_obs()
        assert result.is_observable is True
        assert result.moon_info.impact_assessment in (
            "none", "low", "moderate", "high", "severe"
        )

    def test_strict_moon_illumination_reduces_windows(self):
        strict = self._run_obs(constraints={"max_moon_illumination": 0.01})
        normal = self._run_obs(constraints={"max_moon_illumination": 0.99})
        strict_count = len(strict.visibility_windows)
        normal_count = len(normal.visibility_windows)
        assert strict_count <= normal_count

    def test_moon_eliminated_window_has_constraint_label(self):
        strict = self._run_obs(constraints={"max_moon_illumination": 0.01})
        moon_eliminated = [
            w for w in strict.eliminated_windows
            if w.violated_constraint in ("moon_illumination", "moon_separation")
        ]
        if strict.moon_info.phase_fraction > 0.01:
            assert len(moon_eliminated) > 0

    def test_moon_below_horizon_no_impact(self):
        result = self._run_obs()
        moon_alts = [h.moon_altitude_deg for h in result.hourly_data
                     if h.moon_altitude_deg is not None]
        if moon_alts and max(moon_alts) <= 0:
            assert result.moon_info.impact_assessment == "none"


# ── W-7: Config consistency ────────────────────────

class TestW7Config:
    def _run_obs(self, date_range=None):
        location = {
            "name": "test", "latitude": 36.49, "longitude": 117.18,
            "elevation_m": 300, "timezone": "Asia/Shanghai",
        }
        if date_range is None:
            date_range = ["2026-10-17", "2026-10-17"]
        return compute_observability(
            ra_deg=10.68, dec_deg=41.27, target_name="M31",
            location=location, date_range=date_range,
            equipment="binoculars",
        )

    def test_buffer_applied(self):
        result = self._run_obs()
        if result.twilight.astronomical_twilight_end and result.hourly_data:
            astro_end = result.twilight.astronomical_twilight_end
            first_time = result.hourly_data[0].time
            delta_min = (first_time - astro_end).total_seconds() / 60
            assert delta_min >= 14

    def test_nights_computed_field(self):
        result = self._run_obs()
        assert result.nights_computed == 1

    def test_multi_day_still_single_night(self):
        result = self._run_obs(date_range=["2026-10-17", "2026-10-19"])
        assert result.nights_computed == 1

    def test_equipment_annotation_in_reason(self):
        location = {
            "name": "test", "latitude": 36.49, "longitude": 117.18,
            "elevation_m": 300, "timezone": "Asia/Shanghai",
        }
        result = compute_observability(
            ra_deg=10.68, dec_deg=41.27, target_name="M31",
            location=location, date_range=["2026-10-17", "2026-10-17"],
            equipment="naked_eye", target_magnitude=5.0,
        )
        if result.is_observable and result.recommended_window:
            assert "超出" in result.recommended_window.reason or "极限星等" in result.recommended_window.reason


# ── W-9: observation_log Schema ────────────────────

class TestW9Schema:
    def _base_input(self):
        return {
            "target": "M31",
            "location": "济南_四门塔",
            "date_range": ["2026-10-17"],
            "audience": "天文社新成员",
            "equipment": "binoculars",
        }

    def test_valid_input_no_log(self):
        inp = StarPlanInput(**self._base_input())
        assert inp.observation_log is None

    def test_valid_input_with_log(self):
        data = self._base_input()
        data["observation_log"] = {
            "actual_start_time": "2026-10-17T19:30:00+08:00",
            "actual_end_time": "2026-10-17T22:30:00+08:00",
            "targets_observed": ["M31"],
            "equipment_used": "binoculars",
            "success_rating": 3,
        }
        inp = StarPlanInput(**data)
        assert inp.observation_log is not None
        assert inp.observation_log.success_rating == 3

    def test_extra_field_rejected(self):
        data = self._base_input()
        data["unknown_field"] = "x"
        with pytest.raises(Exception, match="extra_forbidden|Extra inputs"):
            StarPlanInput(**data)

    def test_invalid_log_missing_field(self):
        data = self._base_input()
        data["observation_log"] = {
            "actual_end_time": "2026-10-17T22:30:00+08:00",
            "targets_observed": ["M31"],
            "equipment_used": "binoculars",
        }
        with pytest.raises(Exception):
            StarPlanInput(**data)

    def test_invalid_log_rating_out_of_range(self):
        data = self._base_input()
        data["observation_log"] = {
            "actual_start_time": "2026-10-17T19:30:00+08:00",
            "actual_end_time": "2026-10-17T22:30:00+08:00",
            "targets_observed": ["M31"],
            "equipment_used": "binoculars",
            "success_rating": 6,
        }
        with pytest.raises(Exception):
            StarPlanInput(**data)

    def test_case_03_file_parses(self):
        case_path = Path(__file__).resolve().parent.parent / "examples" / "case_03_observation_review.json"
        with open(case_path, encoding="utf-8") as f:
            data = json.load(f)
        inp = StarPlanInput(**data)
        assert inp.observation_log is not None
        assert inp.observation_log.targets_observed == ["M31"]
