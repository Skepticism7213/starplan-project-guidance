"""I-3 fix regression: MoonInfo.moonrise/moonset must be computed, not None.

Before the fix, MoonInfo.moonrise/moonset were hardcoded to None.
Now they are deterministically computed (Astropy-only numeric search)
within the night window, with documented semantics:
  - naive local time of the event inside the window
  - None when the event does not occur inside the window

Verification approach: independent altitude sampling around the reported
event time (must cross zero with the correct sign direction).
"""

import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starplan_skills.astro_runtime import configure_astronomy_runtime

configure_astronomy_runtime()

from starplan_skills.target_resolve import resolve_target
from starplan_skills.observability_plan import compute_observability

from astropy.coordinates import AltAz, EarthLocation, get_body
from astropy.time import Time
import astropy.units as u


LOCATION = {
    "name": "四门塔景区观星点",
    "city": "济南",
    "latitude": 36.49,
    "longitude": 117.18,
    "elevation_m": 300,
    "timezone": "Asia/Shanghai",
}

_OBS_CACHE = None


def _get_obs():
    """Compute the M31/2026-10-17 case once for the module."""
    global _OBS_CACHE
    if _OBS_CACHE is None:
        t = resolve_target("M31")
        _OBS_CACHE = compute_observability(
            t.ra_deg, t.dec_deg, "M31", LOCATION,
            ["2026-10-17", "2026-10-17"], equipment="binoculars",
        )
    return _OBS_CACHE


def _moon_alt_at(local_naive):
    """Independent moon altitude check at a naive local time (UTC+8)."""
    el = EarthLocation(
        lat=LOCATION["latitude"] * u.deg,
        lon=LOCATION["longitude"] * u.deg,
        height=LOCATION["elevation_m"] * u.m,
    )
    utc = Time((local_naive - timedelta(hours=8)).isoformat(), scale="utc")
    frame = AltAz(obstime=utc, location=el)
    return float(get_body("moon", utc, el).transform_to(frame).alt.deg)


class TestMoonRiseSetComputed:
    """moonrise/moonset must be real computed values with correct semantics."""

    def test_moonset_is_computed_for_2026_10_17(self):
        """Case date 2026-10-17: moon sets during the night window."""
        obs = _get_obs()
        mi = obs.moon_info
        assert mi.moonset is not None, (
            "moonset must be computed for 2026-10-17 (moon sets ~21:49 local)"
        )

    def test_moonset_crosses_zero_downward(self):
        """At reported moonset: alt ~0, positive before, negative after."""
        obs = _get_obs()
        moonset = obs.moon_info.moonset
        assert moonset is not None
        at_set = _moon_alt_at(moonset)
        before = _moon_alt_at(moonset - timedelta(minutes=5))
        after = _moon_alt_at(moonset + timedelta(minutes=5))
        assert abs(at_set) < 0.05, f"altitude at moonset should be ~0, got {at_set}"
        assert before > 0, f"moon should be up 5 min before set, alt={before}"
        assert after < 0, f"moon should be down 5 min after set, alt={after}"

    def test_moonrise_none_means_already_up(self):
        """If moonrise is None, the moon must already be up at window start.

        For 2026-10-17 the moon is up from the beginning of the night
        window (first-quarter moon setting at ~21:49), so moonrise=None
        is the CORRECT semantics — but it must be verifiably correct,
        not a hardcoded leftover.
        """
        obs = _get_obs()
        mi = obs.moon_info
        if mi.moonrise is None:
            # Verify via the hourly grid: first sample has moon above horizon
            first = obs.hourly_data[0]
            assert first.moon_altitude_deg is not None
            assert first.moon_altitude_deg > 0, (
                "moonrise=None requires the moon already up at window start, "
                f"but first sample moon altitude is {first.moon_altitude_deg}"
            )
        else:
            # If a rise is reported, it must cross zero upward
            before = _moon_alt_at(mi.moonrise - timedelta(minutes=5))
            after = _moon_alt_at(mi.moonrise + timedelta(minutes=5))
            assert before < 0 and after > 0

    def test_values_are_deterministic(self):
        """Two identical runs must produce identical moonrise/moonset."""
        t = resolve_target("M31")
        obs2 = compute_observability(
            t.ra_deg, t.dec_deg, "M31", LOCATION,
            ["2026-10-17", "2026-10-17"], equipment="binoculars",
        )
        obs1 = _get_obs()
        assert obs1.moon_info.moonrise == obs2.moon_info.moonrise
        assert obs1.moon_info.moonset == obs2.moon_info.moonset

    def test_m42_case_also_computes_moon_events(self):
        """M42/2026-07-25 (not-observable case) also gets real moon data."""
        t = resolve_target("M42")
        obs = compute_observability(
            t.ra_deg, t.dec_deg, "M42", LOCATION,
            ["2026-07-25", "2026-07-25"], equipment="binoculars",
        )
        mi = obs.moon_info
        # Either an event is computed, or None is justified by the grid
        if mi.moonrise is None and mi.moonset is None:
            alts = [h.moon_altitude_deg for h in obs.hourly_data
                    if h.moon_altitude_deg is not None]
            # No events only valid if moon stays on one side of horizon
            assert all(a > 0 for a in alts) or all(a <= 0 for a in alts)
