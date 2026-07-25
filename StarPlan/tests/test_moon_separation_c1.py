"""
StarPlan Loop - C-1 Regression Test: Moon Separation Coordinate Frame Fix

Validates that observability_plan computes moon-target angular separation
in the same AltAz frame (observer's local sky), NOT cross-frame ICRS-vs-GCRS.

Reference case:
  Target:   M31 (RA=10.6847 deg, Dec=41.2689 deg, ICRS)
  Location: 四门塔 (36.49N, 117.18E, 300m)
  Time:     2026-10-17 23:13 CST (UTC+8) => 15:13 UTC

  Old buggy result (ICRS vs GCRS separation): ~33.6 deg
  Correct result (AltAz vs AltAz separation):  ~105.6 deg

The test independently computes the expected value using raw Astropy,
then verifies the pipeline output matches within tolerance.

No API key required. Runs offline with Astropy ephemeris (built-in).
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astropy.coordinates import AltAz, EarthLocation, SkyCoord, get_body
from astropy.time import Time
import astropy.units as u


# ── Constants ─────────────────────────────────────────

# M31 (Andromeda Galaxy) coordinates from built_in_catalog_v1
M31_RA_DEG = 10.6847
M31_DEC_DEG = 41.2689

# 四门塔 observing site
SITE_LAT = 36.49
SITE_LON = 117.18
SITE_ELEV_M = 300.0
SITE_TZ_HOURS = 8  # Asia/Shanghai

# Reference time: 2026-10-17 23:13 CST
REF_LOCAL_TIME = datetime(2026, 10, 17, 23, 13, 0)
REF_UTC_TIME = REF_LOCAL_TIME - timedelta(hours=SITE_TZ_HOURS)

# Expected separation (approximate, from manual AltAz computation)
EXPECTED_SEP_DEG = 105.6
# Tolerance: allow +-3 deg for ephemeris/catalog precision differences
TOLERANCE_DEG = 3.0

# The old buggy value — must NOT be close to this
BUGGY_SEP_DEG = 33.6


# ── Independent reference computation ─────────────────

def _compute_reference_separation() -> float:
    """
    Independently compute the AltAz angular separation between M31 and Moon
    at the reference time/location using raw Astropy. This is the ground truth.
    """
    obs_loc = EarthLocation(
        lat=SITE_LAT * u.deg,
        lon=SITE_LON * u.deg,
        height=SITE_ELEV_M * u.m,
    )
    astropy_t = Time(REF_UTC_TIME, scale="utc")
    altaz_frame = AltAz(obstime=astropy_t, location=obs_loc)

    # Target in AltAz
    target_icrs = SkyCoord(ra=M31_RA_DEG * u.deg, dec=M31_DEC_DEG * u.deg, frame="icrs")
    target_altaz = target_icrs.transform_to(altaz_frame)

    # Moon in AltAz
    moon_gcrs = get_body("moon", astropy_t, obs_loc)
    moon_altaz = moon_gcrs.transform_to(altaz_frame)

    # Same-frame separation (the correct way)
    sep = target_altaz.separation(moon_altaz).deg
    return float(sep)


def _compute_buggy_separation() -> float:
    """
    Reproduce the OLD BUG: cross-frame separation between ICRS target and
    GCRS moon. This should give ~33.6 deg (the wrong answer).
    """
    obs_loc = EarthLocation(
        lat=SITE_LAT * u.deg,
        lon=SITE_LON * u.deg,
        height=SITE_ELEV_M * u.m,
    )
    astropy_t = Time(REF_UTC_TIME, scale="utc")

    target_icrs = SkyCoord(ra=M31_RA_DEG * u.deg, dec=M31_DEC_DEG * u.deg, frame="icrs")
    moon_gcrs = get_body("moon", astropy_t, obs_loc)

    # Cross-frame separation (the BUG)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sep = target_icrs.separation(moon_gcrs).deg
    return float(sep)


# ── Tests ─────────────────────────────────────────────

class TestMoonSeparationReference:
    """Verify our independent reference computation is sane."""

    def test_reference_separation_near_expected(self):
        """The AltAz separation should be close to ~105.6 deg."""
        sep = _compute_reference_separation()
        assert abs(sep - EXPECTED_SEP_DEG) < TOLERANCE_DEG, (
            f"Reference AltAz separation {sep:.2f} deg deviates from "
            f"expected {EXPECTED_SEP_DEG} deg by more than {TOLERANCE_DEG} deg"
        )

    def test_buggy_separation_is_wrong(self):
        """The old cross-frame method should give ~33.6 deg (the wrong value)."""
        sep = _compute_buggy_separation()
        assert abs(sep - BUGGY_SEP_DEG) < 5.0, (
            f"Buggy separation {sep:.2f} deg not near expected buggy value "
            f"{BUGGY_SEP_DEG} deg — ephemeris may have changed"
        )

    def test_correct_and_buggy_differ_significantly(self):
        """The correct and buggy values must differ by >60 deg."""
        correct = _compute_reference_separation()
        buggy = _compute_buggy_separation()
        assert abs(correct - buggy) > 60.0, (
            f"Correct ({correct:.2f}) and buggy ({buggy:.2f}) values are too close; "
            f"the bug may not be reproducible with current ephemeris"
        )


class TestPipelineMoonSeparation:
    """Verify compute_observability outputs correct moon separation."""

    @pytest.fixture(scope="class")
    def pipeline_result(self):
        """Run the full observability pipeline for M31 at 四门塔 on 2026-10-17."""
        from starplan_skills.observability_plan import compute_observability

        location = {
            "latitude": SITE_LAT,
            "longitude": SITE_LON,
            "elevation_m": SITE_ELEV_M,
            "timezone": "Asia/Shanghai",
        }
        result = compute_observability(
            ra_deg=M31_RA_DEG,
            dec_deg=M31_DEC_DEG,
            target_name="M31",
            location=location,
            date_range=["2026-10-17", "2026-10-17"],
        )
        return result

    def test_moon_separation_not_buggy(self, pipeline_result):
        """No hourly data point should have moon_sep near the old buggy ~33.6 deg."""
        for h in pipeline_result.hourly_data:
            if h.moon_separation_deg is not None:
                assert abs(h.moon_separation_deg - BUGGY_SEP_DEG) > 30.0, (
                    f"At {h.time}: moon_separation_deg={h.moon_separation_deg} "
                    f"is suspiciously close to the old buggy value {BUGGY_SEP_DEG}"
                )

    def test_moon_separation_in_physical_range(self, pipeline_result):
        """All moon separations should be in [0, 180] and most should be >60 deg."""
        seps = [
            h.moon_separation_deg
            for h in pipeline_result.hourly_data
            if h.moon_separation_deg is not None
        ]
        assert len(seps) > 0, "No hourly data with moon separation found"
        for s in seps:
            assert 0 <= s <= 180, f"Moon separation {s} out of physical range"
        # For this case, the moon should be far from M31 all night
        assert min(seps) > 60.0, (
            f"Minimum moon separation {min(seps):.2f} deg is too small; "
            f"possible coordinate frame issue"
        )

    def test_closest_time_to_reference(self, pipeline_result):
        """
        Find the hourly data point closest to 23:13 local and verify its
        moon_separation_deg matches our independent reference computation.
        """
        # Find closest data point
        best = None
        best_dt = float("inf")
        for h in pipeline_result.hourly_data:
            if h.moon_separation_deg is None:
                continue
            # h.time is a datetime object; make naive for comparison
            t = h.time.replace(tzinfo=None) if h.time.tzinfo else h.time
            dt = abs((t - REF_LOCAL_TIME).total_seconds())
            if dt < best_dt:
                best_dt = dt
                best = h

        assert best is not None, "No valid hourly data point found"

        # Compare with independent reference
        ref_sep = _compute_reference_separation()
        assert abs(best.moon_separation_deg - ref_sep) < 1.0, (
            f"Pipeline moon_sep={best.moon_separation_deg:.2f} at {best.time} "
            f"differs from reference {ref_sep:.2f} by more than 1 deg"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
