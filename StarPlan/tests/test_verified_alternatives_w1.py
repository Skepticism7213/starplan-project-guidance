"""W-1 fix regression: alternative targets must be verified by computation.

Before the fix, _generate_alternatives used a hardcoded seasonal table
(8 targets by month) and presented them as DERIVED_FACT without ever
computing their observability. This could recommend targets that are
actually unusable — most sharply, faint deep-sky objects into a
moonlight-blocked night.

Contract after the fix:
  1. Alternative targets come from a two-stage search over the full
     built-in catalog (coarse batched screen + full verification).
  2. Every suggested target genuinely passes the same constraints at
     the same location/date (independently re-checked here).
  3. Moonlight blocking drops faint DSOs at the coarse stage.
  4. Internal candidate verification never recurses into alternatives.
  5. Results are deterministic.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starplan_skills.astro_runtime import configure_astronomy_runtime

configure_astronomy_runtime()

from astropy.coordinates import EarthLocation
import astropy.units as u

from starplan_skills.observability_plan import (
    _coarse_screen_candidates,
    compute_observability,
    _MOONLIGHT_DSO_MAG_LIMIT,
)

LOCATION = {
    "name": "四门塔景区观星点",
    "city": "济南",
    "latitude": 36.49,
    "longitude": 117.18,
    "elevation_m": 300,
    "timezone": "Asia/Shanghai",
}

OBS_LOC = EarthLocation(
    lat=LOCATION["latitude"] * u.deg,
    lon=LOCATION["longitude"] * u.deg,
    height=LOCATION["elevation_m"] * u.m,
)

# Night window for 2026-07-25 in Jinan (UTC datetimes, matching pipeline)
NIGHT_START = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)  # 20:00 local
NIGHT_END = datetime(2026, 7, 25, 20, 0, tzinfo=timezone.utc)    # 04:00 local


class TestCoarseScreenMoonlight:
    """Moonlight blocking must drop faint deep-sky candidates."""

    def test_moonlight_filter_keeps_only_bright_objects(self):
        """With reason='moonlight', shortlist contains only stars or
        DSOs brighter than the magnitude limit."""
        shortlist = _coarse_screen_candidates(
            original_name="M42",
            night_start=NIGHT_START,
            night_end=NIGHT_END,
            obs_loc=OBS_LOC,
            min_alt=30.0,
            not_observable_reason="moonlight",
            max_candidates=10,
        )
        assert len(shortlist) > 0
        for e in shortlist:
            if e["target_type"] != "star":
                mag = e.get("visual_magnitude")
                assert mag is not None and mag <= _MOONLIGHT_DSO_MAG_LIMIT, (
                    f"Faint DSO {e['standard_name']} (mag={mag}) must not "
                    f"survive the moonlight coarse filter"
                )

    def test_no_moonlight_allows_faint_dso(self):
        """Altitude-blocked nights (no moonlight) may include faint DSOs."""
        shortlist = _coarse_screen_candidates(
            original_name="M42",
            night_start=NIGHT_START,
            night_end=NIGHT_END,
            obs_loc=OBS_LOC,
            min_alt=30.0,
            not_observable_reason="altitude",
            max_candidates=10,
        )
        assert len(shortlist) > 0
        names = [e["standard_name"] for e in shortlist]
        assert "M42" not in names, "original target must be excluded"

    def test_original_target_excluded(self):
        shortlist = _coarse_screen_candidates(
            original_name="M31",
            night_start=NIGHT_START,
            night_end=NIGHT_END,
            obs_loc=OBS_LOC,
            min_alt=30.0,
            not_observable_reason=None,
            max_candidates=20,
        )
        names = [e["standard_name"] for e in shortlist]
        assert "M31" not in names


class TestVerifiedAlternativesContract:
    """End-to-end contract: suggested targets are really observable."""

    def _case2_result(self):
        import json
        case_file = Path(__file__).resolve().parent.parent / \
            "examples" / "case_02_unfavorable_window.json"
        data = json.loads(case_file.read_text(encoding="utf-8"))
        from starplan_skills.runner import run_starplan
        return run_starplan(data, run_id="w1_contract_test")

    def test_alternatives_independently_observable(self):
        """Every suggested alternative must pass a fresh full computation."""
        r = self._case2_result()
        alts = [
            s for s in r["plan"]["alternative_suggestions"]
            if s["suggestion_type"] == "alternative_target"
        ]
        assert len(alts) >= 1
        from starplan_skills.target_resolve import resolve_target
        for s in alts:
            t = resolve_target(s["target_name"])
            obs = compute_observability(
                t.ra_deg, t.dec_deg, t.standard_name,
                LOCATION, ["2026-07-25", "2026-07-25"],
                equipment="binoculars", _allow_alternatives=False,
            )
            assert obs.is_observable, (
                f"Suggested alternative {s['target_name']} is not observable"
            )

    def test_suggestion_carries_computed_evidence(self):
        """Descriptions must contain real peak altitude and window."""
        r = self._case2_result()
        alts = [
            s for s in r["plan"]["alternative_suggestions"]
            if s["suggestion_type"] == "alternative_target"
        ]
        assert alts
        for s in alts:
            d = s["description"]
            assert "已验证" in d
            assert "最高高度" in d and "°" in d
            assert "推荐窗口" in d and "–" in d

    def test_deterministic_suggestions(self):
        """Two identical runs must suggest the same targets in same order."""
        r1 = self._case2_result()
        r2 = self._case2_result()
        n1 = [s["target_name"] for s in r1["plan"]["alternative_suggestions"]
              if s["suggestion_type"] == "alternative_target"]
        n2 = [s["target_name"] for s in r2["plan"]["alternative_suggestions"]
              if s["suggestion_type"] == "alternative_target"]
        assert n1 == n2


class TestRecursionGuard:
    """Internal candidate verification must not regenerate alternatives."""

    def test_allow_alternatives_false_suppresses_suggestions(self):
        """M42 on 2026-07-25 is not observable; with the recursion guard
        the result must carry zero alternative suggestions."""
        from starplan_skills.target_resolve import resolve_target
        t = resolve_target("M42")
        obs = compute_observability(
            t.ra_deg, t.dec_deg, "M42", LOCATION,
            ["2026-07-25", "2026-07-25"],
            equipment="binoculars", _allow_alternatives=False,
        )
        assert not obs.is_observable
        assert obs.alternative_suggestions == [], (
            "Recursion guard failed: candidate verification generated "
            "its own alternatives"
        )
