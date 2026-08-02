"""
StarPlan test configuration.

Disables astropy IERS auto-download to prevent flaky failures when
network is unavailable and the local IERS cache has expired.
Astropy will use its bundled IERS data instead (sufficient for
the date range used in tests: 2026).
"""

import astropy.utils.iers as iers

# Prevent network-dependent IERS download during tests.
# Without this, tests fail with ValueError when the IERS cache
# expires and the machine has no internet access.
iers.conf.auto_download = False
iers.conf.auto_max_age = None
