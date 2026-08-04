"""Batch A: Offline runtime policy test.

Verifies that the normal README entry points (run_case.py) complete within
30 seconds under:
  - Fresh Astropy cache (no user IERS/leap-second data)
  - No network access (unreachable proxy)
  - No DASHSCOPE_API_KEY

Current failure evidence: without product-level IERS configuration, astropy
attempts to download IERS-B data and hangs until TCP timeout (45-90s observed).

Expected behavior after fix: runner calls configure_astronomy_runtime() before
any Time/EarthLocation usage; cases complete in <30s with bundled data.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = PROJECT_ROOT / "scripts"
EXAMPLES = PROJECT_ROOT / "examples"

# 30-second hard limit per P0 acceptance criteria
TIMEOUT_SECONDS = 30


def _offline_env(tmp_cache: str) -> dict:
    """Build an environment that simulates no network and no existing cache."""
    env = os.environ.copy()
    # Fresh astropy cache — no pre-existing IERS data
    env["XDG_CACHE_HOME"] = tmp_cache
    env["ASTROPY_CACHE_DIR"] = os.path.join(tmp_cache, "astropy")
    # Block network via unreachable proxy
    env["HTTP_PROXY"] = "http://127.0.0.1:1"
    env["HTTPS_PROXY"] = "http://127.0.0.1:1"
    env["http_proxy"] = "http://127.0.0.1:1"
    env["https_proxy"] = "http://127.0.0.1:1"
    env["NO_PROXY"] = ""
    env["no_proxy"] = ""
    # No API key — Qwen calls must be skipped or fail safely
    env.pop("DASHSCOPE_API_KEY", None)
    # Ensure Python can find the project
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    return env


def _run_case_offline(case_file: Path, timeout: int = TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    """Run a case via run_case.py in an offline subprocess with fresh cache."""
    with tempfile.TemporaryDirectory(prefix="starplan_offline_") as tmp_cache:
        env = _offline_env(tmp_cache)
        cmd = [sys.executable, str(SCRIPTS / "run_case.py"), str(case_file)]
        start = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=env,
                cwd=str(PROJECT_ROOT),
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = time.monotonic() - start
            pytest.fail(
                f"TIMEOUT: {case_file.name} did not complete within {timeout}s "
                f"(elapsed={elapsed:.1f}s). This indicates IERS/leap-second "
                f"network wait in the normal entry path.\n"
                f"Partial stdout: {(exc.stdout or b'')[:500]}\n"
                f"Partial stderr: {(exc.stderr or b'')[:500]}"
            )
        return result


class TestOfflineRuntimePolicy:
    """Normal entry must not depend on network or pre-existing Astropy cache."""

    def test_m31_offline_completes_within_timeout(self):
        """Case 1 (M31 observable) must reach terminal state in <30s offline."""
        case_file = EXAMPLES / "case_01_m31_jinan.json"
        assert case_file.exists(), f"Missing example: {case_file}"

        result = _run_case_offline(case_file)

        # Must exit cleanly (terminal state reached)
        assert result.returncode == 0, (
            f"M31 case failed (rc={result.returncode}).\n"
            f"stdout: {result.stdout[-1000:]}\n"
            f"stderr: {result.stderr[-1000:]}"
        )
        # Must not contain IERS download errors
        combined = (result.stdout + result.stderr).lower()
        assert "iers" not in combined or "download" not in combined, (
            f"IERS download issue detected in output:\n{result.stderr[-500:]}"
        )

    def test_m42_offline_completes_within_timeout(self):
        """Case 2 (M42 unfavorable) must reach terminal state in <30s offline."""
        case_file = EXAMPLES / "case_02_unfavorable_window.json"
        assert case_file.exists(), f"Missing example: {case_file}"

        result = _run_case_offline(case_file)

        assert result.returncode == 0, (
            f"M42 case failed (rc={result.returncode}).\n"
            f"stdout: {result.stdout[-1000:]}\n"
            f"stderr: {result.stderr[-1000:]}"
        )
        combined = (result.stdout + result.stderr).lower()
        assert "iers" not in combined or "download" not in combined, (
            f"IERS download issue detected in output:\n{result.stderr[-500:]}"
        )

    def test_runtime_policy_logged_in_output(self):
        """After fix, output should contain astronomy_runtime=offline_bundled_data."""
        case_file = EXAMPLES / "case_01_m31_jinan.json"
        result = _run_case_offline(case_file)

        # This assertion will fail before the fix is applied —
        # the marker is only emitted after configure_astronomy_runtime() is called.
        assert result.returncode == 0, f"Case fails: {result.stderr[-500:]}"
        assert "astronomy_runtime=offline_bundled_data" in result.stdout, (
            "Expected runtime policy marker 'astronomy_runtime=offline_bundled_data' "
            "in stdout. The runner must call configure_astronomy_runtime() and log "
            "the active policy.\n"
            f"stdout tail: {result.stdout[-500:]}"
        )


# Inline script for the R-06 leap-second check. Runs in a FRESH interpreter
# because astropy's _LEAP_SECONDS_CHECK is process-wide one-shot state.
_LEAP_CHECK_SCRIPT = r"""
import sys, warnings
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, {project_root!r})

from starplan_skills.astro_runtime import configure_astronomy_runtime
configure_astronomy_runtime()

import astropy.time.core as tc
assert tc._LEAP_SECONDS_CHECK == tc._LeapSecondsCheck.DONE, (
    "leap-second check flag not pre-marked DONE: %r" % tc._LEAP_SECONDS_CHECK
)

# Instrument update_leap_seconds: any call means the path was NOT skipped.
calls = []
_orig = tc.update_leap_seconds
def _spy(*a, **k):
    calls.append(1)
    return _orig(*a, **k)
tc.update_leap_seconds = _spy

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    from astropy.time import Time
    t1 = Time("2026-10-17 12:00:00", scale="utc")
    t2 = Time("2026-07-25 18:30:00", scale="utc")
    _ = (t1.ut1, t2.ut1)  # force scales that consume leap seconds

assert len(calls) == 0, "update_leap_seconds was called %d time(s)" % len(calls)
leap_warns = [w for w in caught if "leap" in str(w.message).lower()]
assert not leap_warns, "leap-second warning emitted: %s" % leap_warns[0].message
print("LEAP_POLICY_OK")
""".format(project_root=str(PROJECT_ROOT))


class TestLeapSecondPolicyR06:
    """R-06: the one-time leap-second auto-update path must be skipped."""

    def test_leap_second_update_never_runs(self):
        """After configure_astronomy_runtime(), Time creation must not
        trigger update_leap_seconds() nor emit any leap-second warning."""
        with tempfile.TemporaryDirectory(prefix="starplan_leap_") as tmp_cache:
            env = _offline_env(tmp_cache)
            try:
                result = subprocess.run(
                    [sys.executable, "-c", _LEAP_CHECK_SCRIPT],
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                    env=env,
                    cwd=str(PROJECT_ROOT),
                )
            except subprocess.TimeoutExpired:
                pytest.fail("Leap-second policy check hung (possible network wait)")

        assert result.returncode == 0, (
            f"Leap policy script failed (rc={result.returncode}).\n"
            f"stdout: {result.stdout[-500:]}\nstderr: {result.stderr[-500:]}"
        )
        assert "LEAP_POLICY_OK" in result.stdout, (
            f"Leap policy marker missing.\n"
            f"stdout: {result.stdout[-500:]}\nstderr: {result.stderr[-500:]}"
        )
