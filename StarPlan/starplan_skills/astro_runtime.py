"""StarPlan Loop - Astronomy runtime policy.

Configures Astropy to use bundled/offline IERS and leap-second data,
ensuring the product works without network access or pre-existing user cache.

This module provides a single idempotent entry point that must be called
before any Astropy Time, EarthLocation, or coordinate transform usage.
It replaces the test-only conftest.py settings with a product-level policy.

Design constraints:
  - Idempotent: safe to call multiple times (e.g., runner + cross_validate).
  - No global warnings suppression: only specific, documented warnings are
    handled at the call site if proven harmless.
  - No configuration framework: just the minimal Astropy policy settings.
  - Logs the active policy so users can distinguish normal computation
    from a network hang.
"""

from __future__ import annotations

import threading

_configured = False
_lock = threading.Lock()


def configure_astronomy_runtime() -> str:
    """Set Astropy IERS/leap-second policy for offline deterministic operation.

    Must be called before the first use of astropy.time.Time,
    astropy.coordinates.EarthLocation, or any AltAz transform.

    Returns:
        Policy identifier string: "offline_bundled_data".

    Side effects:
        - Disables IERS auto-download (uses Astropy's bundled IERS-B table).
        - Sets auto_max_age=None so predictive values beyond 30 days are
          accepted without raising ValueError.
        - Disables leap-second auto-update network checks.
    """
    global _configured
    if _configured:
        return "offline_bundled_data"

    with _lock:
        if _configured:
            return "offline_bundled_data"

        import astropy.utils.iers as iers

        # Use bundled IERS data; do not attempt network download.
        # This is the same policy proven in conftest.py since 2026-07-20,
        # now elevated to product runtime.
        iers.conf.auto_download = False

        # Accept predictive IERS values regardless of age.
        # Without this, astropy raises ValueError for dates >30 days
        # beyond the last downloaded IERS-A table when offline.
        # The bundled IERS-B data is sufficient for our date range (2026).
        iers.conf.auto_max_age = None

        # R-06 fix: disable the one-time leap-second auto-update check.
        #
        # Mechanism (verified against astropy 8.0.1 source): the first
        # Time creation triggers astropy.time.core._check_leapsec(), which
        # calls update_leap_seconds() -> LeapSeconds.auto_open(). That
        # routine applies a freshness window (expires > today + 150 days
        # when auto_max_age=None) and walks bundled, cached and remote
        # leap-second tables. Around 2026-08 the bundled table no longer
        # satisfies the window, so the walk touches the download cache and
        # emitted "leap-second auto-update failed: PermissionError" warnings
        # on Windows machines with cache ACL issues (recheck report R-06),
        # in BOTH offline and online runs.
        #
        # Scientific safety: leap seconds never change retroactively. None
        # has been introduced since 2017-01-01 and none is announced for
        # the project's date range, so ERFA's bundled table is correct for
        # every date this product computes. Skipping the update only avoids
        # fetching a newer table — it cannot alter past leap seconds.
        try:
            import astropy.time.core as _time_core
            _time_core._LEAP_SECONDS_CHECK = _time_core._LeapSecondsCheck.DONE
        except (ImportError, AttributeError):
            # Unknown future astropy layout: fall back to default behavior
            # rather than crash. IERS policy above still applies.
            pass

        _configured = True

    return "offline_bundled_data"
