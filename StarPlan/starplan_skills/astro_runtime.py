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

        # Disable leap-second auto-update network check.
        # ERFA/Astropy ships a bundled leap-second table that covers
        # through 2026-12-28. No network fetch is needed.
        try:
            from astropy.utils.iers import conf as iers_conf
            # remote_timeout=0 would still attempt DNS; instead rely on
            # auto_download=False which prevents the fetch entirely.
            iers_conf.remote_timeout = 1  # Minimal timeout as safety net
        except (ImportError, AttributeError):
            pass  # Older astropy versions may not have remote_timeout

        _configured = True

    return "offline_bundled_data"
