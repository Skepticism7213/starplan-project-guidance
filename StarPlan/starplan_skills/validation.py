"""
StarPlan Loop - Validation utilities.

Provides cross-check functions to verify that computed astronomical
values are consistent with expected ranges and tool outputs.
"""

from __future__ import annotations

from .schemas import ObservabilityResult, ResolvedTarget


def validate_target(resolved: ResolvedTarget) -> list[str]:
    """Validate a resolved target against basic sanity checks."""
    issues: list[str] = []

    if not resolved.standard_name:
        issues.append("Target name is empty")
    if resolved.ra_deg < 0 or resolved.ra_deg > 360:
        issues.append(f"RA out of range: {resolved.ra_deg}")
    if resolved.dec_deg < -90 or resolved.dec_deg > 90:
        issues.append(f"Dec out of range: {resolved.dec_deg}")
    if resolved.confidence < 0.5:
        issues.append(f"Low confidence: {resolved.confidence}")

    return issues


def validate_observability(obs: ObservabilityResult) -> list[str]:
    """Validate observability results against basic sanity checks."""
    issues: list[str] = []

    if not obs.hourly_data:
        issues.append("No hourly data computed")
        return issues

    # Check altitude range
    alts = [h.altitude_deg for h in obs.hourly_data]
    if max(alts) > 90.1:
        issues.append(f"Altitude exceeds 90°: {max(alts)}")
    if min(alts) < -90.1:
        issues.append(f"Altitude below -90°: {min(alts)}")

    # Check that recommended window is within visible period
    if obs.recommended_window and obs.visibility_windows:
        rw = obs.recommended_window.window
        in_any = False
        for vw in obs.visibility_windows:
            if vw.start <= rw.start and rw.end <= vw.end:
                in_any = True
                break
        if not in_any:
            issues.append("Recommended window not within any visibility window")

    # Check twilight consistency
    if obs.twilight.sunset and obs.twilight.astronomical_twilight_end:
        if obs.twilight.astronomical_twilight_end < obs.twilight.sunset:
            issues.append("Astronomical twilight end before sunset")

    return issues


def validate_traceability(
    obs: ObservabilityResult,
    constraints: dict,
) -> list[str]:
    """Validate that all key values are traceable to tool output."""
    issues: list[str] = []

    # Check that recommended window altitude matches hourly data
    if obs.recommended_window:
        peak = obs.recommended_window.peak_altitude_deg
        hourly_peaks = [h.altitude_deg for h in obs.hourly_data]
        if hourly_peaks and abs(peak - max(hourly_peaks)) > 1.0:
            issues.append(
                f"Recommended peak {peak}° differs from hourly data max {max(hourly_peaks)}°"
            )

    return issues
