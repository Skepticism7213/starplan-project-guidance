"""
StarPlan Loop - Skill 2: observability_plan

Computes target observability for a given location and date range using
deterministic astronomy tools (Astropy + astroplan).

Outputs:
  - Hourly altitude/azimuth/airmass data
  - Twilight times
  - Moon information and impact assessment
  - Recommended observing window with reasoning
  - Eliminated windows with constraint violations
  - Risk flags
  - Alternative suggestions when target is not observable

All numerical results come from Astropy/astroplan computations, never from
a language model. This is the core "工具算" principle.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from astropy.coordinates import AltAz, EarthLocation, SkyCoord, get_body
from astropy.time import Time
import astropy.units as u

from .config import load_constraints
from .schemas import (
    AlternativeSuggestion,
    EliminatedWindow,
    HourlyData,
    MoonInfo,
    ObservabilityResult,
    ObservingConstraint,
    RecommendedWindow,
    RiskFlag,
    TimeWindow,
    TwilightInfo,
)


# ── Helpers ──────────────────────────────────────────

def _tz_offset_hours(tz_name: str) -> float:
    """Return UTC offset in hours for a timezone name."""
    # Simple mapping for common Chinese timezones; extend as needed
    tz_map = {"Asia/Shanghai": 8.0, "Asia/Tokyo": 9.0, "UTC": 0.0}
    return tz_map.get(tz_name, 8.0)


def _make_location(lat: float, lon: float, elev: float) -> EarthLocation:
    """Create an Astropy EarthLocation."""
    return EarthLocation(lat=lat * u.deg, lon=lon * u.deg, height=elev * u.m)


def _make_target(ra_deg: float, dec_deg: float) -> SkyCoord:
    """Create an Astropy SkyCoord for a fixed target."""
    return SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs")


def _astropy_time(dt: datetime) -> Time:
    """Convert a Python datetime to Astropy Time."""
    return Time(dt, scale="utc")


# ── Core computation ─────────────────────────────────

def compute_observability(
    ra_deg: float,
    dec_deg: float,
    target_name: str,
    location: dict,
    date_range: list[str],
    equipment: Optional[str] = None,
    constraints: Optional[dict] = None,
    run_dir: Optional[Path] = None,
) -> ObservabilityResult:
    """
    Compute target observability and generate an observation plan.

    Args:
        ra_deg: Right ascension in degrees (J2000).
        dec_deg: Declination in degrees (J2000).
        target_name: Standard target name.
        location: Dict with keys: latitude, longitude, elevation_m, timezone.
        date_range: [start_date, end_date] as YYYY-MM-DD strings.
        equipment: Equipment type string.
        constraints: Optional constraint overrides.
        run_dir: Directory for saving output files.

    Returns:
        ObservabilityResult with all computed data.
    """
    # Load constraint config
    cfg = load_constraints()
    alt_cfg = cfg.get("altitude", {})
    am_cfg = cfg.get("airmass", {})
    tw_cfg = cfg.get("twilight", {})
    moon_cfg = cfg.get("moon", {})
    risk_cfg = cfg.get("risk_rules", {})

    # Apply user constraint overrides
    min_alt = alt_cfg.get("min_altitude_deg", 30.0)
    max_am = am_cfg.get("max_airmass", 2.0)
    if constraints:
        min_alt = constraints.get("min_altitude_deg", min_alt)
        max_am = constraints.get("max_airmass", max_am)

    # Parse location
    lat = location["latitude"]
    lon = location["longitude"]
    elev = location.get("elevation_m", 0)
    tz_name = location.get("timezone", "Asia/Shanghai")
    tz_hours = _tz_offset_hours(tz_name)
    tz = timezone(timedelta(hours=tz_hours))

    obs_loc = _make_location(lat, lon, elev)
    target = _make_target(ra_deg, dec_deg)

    # Parse dates
    d_start = datetime.strptime(date_range[0], "%Y-%m-%d")
    d_end = datetime.strptime(date_range[-1], "%Y-%m-%d")

    # Use the first date for computation (MVP: single-night analysis)
    obs_date = d_start

    # Compute sunset / twilight for the observing night
    # We compute for the afternoon of obs_date → morning of obs_date+1
    sunset_utc, tw_civil_end, tw_naut_end, tw_astro_end = _compute_twilight(
        obs_loc, obs_date, tz_hours
    )
    sunrise_utc, tw_astro_start = _compute_morning_twilight(
        obs_loc, obs_date + timedelta(days=1), tz_hours
    )

    twilight = TwilightInfo(
        sunset=_to_local(sunset_utc, tz) if sunset_utc else None,
        civil_twilight_end=_to_local(tw_civil_end, tz) if tw_civil_end else None,
        nautical_twilight_end=_to_local(tw_naut_end, tz) if tw_naut_end else None,
        astronomical_twilight_end=_to_local(tw_astro_end, tz) if tw_astro_end else None,
        sunrise=_to_local(sunrise_utc, tz) if sunrise_utc else None,
        astronomical_twilight_start=_to_local(tw_astro_start, tz) if tw_astro_start else None,
    )

    # Define observing night window: from astronomical twilight end to morning twilight start
    if tw_astro_end and tw_astro_start:
        night_start = tw_astro_end
        night_end = tw_astro_start
    elif sunset_utc and sunrise_utc:
        # Fallback: use sunset to sunrise
        night_start = sunset_utc + timedelta(minutes=30)
        night_end = sunrise_utc - timedelta(minutes=30)
    else:
        night_start = _local_to_utc(
            obs_date.replace(hour=20, minute=0), tz_hours
        )
        night_end = _local_to_utc(
            (obs_date + timedelta(days=1)).replace(hour=4, minute=0), tz_hours
        )

    # Compute hourly data through the night
    hourly_data: list[HourlyData] = []
    time_points: list[Time] = []
    altitudes: list[float] = []
    azimuths: list[float] = []
    airmasses: list[Optional[float]] = []

    # Generate time grid: every 15 minutes through the night
    t_current = night_start
    step = timedelta(minutes=15)
    while t_current <= night_end:
        astropy_t = _astropy_time(t_current)
        altaz_frame = AltAz(obstime=astropy_t, location=obs_loc)
        target_altaz = target.transform_to(altaz_frame)

        alt = float(target_altaz.alt.deg)
        az = float(target_altaz.az.deg)
        am = float(target_altaz.secz) if alt > 0 else None

        # Sun altitude
        sun_coord = get_body("sun", astropy_t, obs_loc)
        sun_altaz = sun_coord.transform_to(altaz_frame)
        sun_alt = float(sun_altaz.alt.deg)

        # Moon data
        moon_coord = get_body("moon", astropy_t, obs_loc)
        moon_altaz = moon_coord.transform_to(altaz_frame)
        moon_alt = float(moon_altaz.alt.deg)
        moon_sep = float(target.separation(moon_coord).deg)

        hourly_data.append(
            HourlyData(
                time=_to_local(t_current, tz),
                altitude_deg=round(alt, 2),
                azimuth_deg=round(az, 2),
                airmass=round(am, 3) if am and am < 38 else None,
                sun_altitude_deg=round(sun_alt, 2),
                moon_altitude_deg=round(moon_alt, 2),
                moon_separation_deg=round(moon_sep, 2),
            )
        )

        time_points.append(astropy_t)
        altitudes.append(alt)
        azimuths.append(az)
        airmasses.append(am)

        t_current += step

    # Moon info summary
    moon_alts = [h.moon_altitude_deg for h in hourly_data if h.moon_altitude_deg is not None]
    moon_seps = [h.moon_separation_deg for h in hourly_data if h.moon_separation_deg is not None]

    # Moon phase (approximate from elongation)
    mid_time = _astropy_time(night_start + (night_end - night_start) / 2)
    sun_coord = get_body("sun", mid_time, obs_loc)
    moon_coord = get_body("moon", mid_time, obs_loc)
    sun_moon_sep = float(sun_coord.separation(moon_coord).deg)
    moon_phase = (1 - np.cos(np.radians(sun_moon_sep))) / 2  # 0=new, 1=full

    moon_info = MoonInfo(
        phase_fraction=round(moon_phase, 3),
        moonrise=None,  # Computed separately if needed
        moonset=None,
        peak_altitude_deg=round(max(moon_alts), 2) if moon_alts else None,
        min_separation_deg=round(min(moon_seps), 2) if moon_seps else None,
        impact_assessment=_assess_moon_impact(moon_phase, min(moon_seps) if moon_seps else 0, moon_cfg),
    )

    # Analyze windows: find contiguous periods where target is above min_altitude
    visibility_windows: list[TimeWindow] = []
    eliminated_windows: list[EliminatedWindow] = []
    risk_flags: list[RiskFlag] = []

    # Find visible periods (altitude >= min_alt and airmass acceptable)
    in_window = False
    window_start = None
    window_peak_alt = 0

    for i, h in enumerate(hourly_data):
        is_good = h.altitude_deg >= min_alt and (h.airmass is None or h.airmass <= max_am)

        if is_good and not in_window:
            in_window = True
            window_start = h.time
            window_peak_alt = h.altitude_deg
        elif is_good and in_window:
            window_peak_alt = max(window_peak_alt, h.altitude_deg)
        elif not is_good and in_window:
            in_window = False
            visibility_windows.append(
                TimeWindow(
                    start=window_start,
                    end=hourly_data[i - 1].time,
                    duration_minutes=(hourly_data[i - 1].time - window_start).total_seconds() / 60,
                )
            )
        elif not is_good and not in_window:
            # Record why this period is eliminated
            if h.altitude_deg < min_alt:
                eliminated_windows.append(
                    EliminatedWindow(
                        window=TimeWindow(
                            start=h.time,
                            end=h.time + timedelta(minutes=15),
                            duration_minutes=15,
                        ),
                        reason=f"目标高度角 {h.altitude_deg:.1f}° 低于最小要求 {min_alt}°",
                        violated_constraint="min_altitude",
                    )
                )
            elif h.airmass and h.airmass > max_am:
                eliminated_windows.append(
                    EliminatedWindow(
                        window=TimeWindow(
                            start=h.time,
                            end=h.time + timedelta(minutes=15),
                            duration_minutes=15,
                        ),
                        reason=f"大气质量 {h.airmass:.2f} 超过最大允许值 {max_am}",
                        violated_constraint="max_airmass",
                    )
                )

    # Close any open window at end of night
    if in_window and window_start:
        visibility_windows.append(
            TimeWindow(
                start=window_start,
                end=hourly_data[-1].time,
                duration_minutes=(hourly_data[-1].time - window_start).total_seconds() / 60,
            )
        )

    # Determine if target is observable
    is_observable = len(visibility_windows) > 0

    # Find recommended window (longest visible window)
    recommended_window: Optional[RecommendedWindow] = None
    if visibility_windows:
        best = max(visibility_windows, key=lambda w: w.duration_minutes)
        # Find peak altitude in this window
        peak_alt = 0
        peak_am = 1.0
        for h in hourly_data:
            if best.start <= h.time <= best.end:
                if h.altitude_deg > peak_alt:
                    peak_alt = h.altitude_deg
                    peak_am = h.airmass if h.airmass else 1.0

        recommended_window = RecommendedWindow(
            window=best,
            peak_altitude_deg=round(peak_alt, 2),
            peak_airmass=round(peak_am, 3),
            reason=(
                f"推荐时段内目标高度角峰值 {peak_alt:.1f}°，"
                f"大气质量 {peak_am:.2f}，"
                f"持续约 {best.duration_minutes:.0f} 分钟，"
                f"满足高度角 ≥ {min_alt}° 且大气质量 ≤ {max_am} 的约束"
            ),
        )

    # Generate risk flags
    risk_flags = _compute_risk_flags(hourly_data, moon_info, min_alt, risk_cfg)

    # Generate alternative suggestions if not observable
    alternative_suggestions: list[AlternativeSuggestion] = []
    if not is_observable:
        alternative_suggestions = _generate_alternatives(
            target_name, obs_date, hourly_data, min_alt
        )

    # Save CSV and curve if run_dir provided
    csv_path = None
    curve_path = None
    if run_dir:
        csv_path = str(run_dir / "observability.csv")
        curve_path = str(run_dir / "visibility_curve.png")
        _save_csv(hourly_data, csv_path)
        _save_curve(hourly_data, target_name, min_alt, curve_path, tz_name)

    return ObservabilityResult(
        is_observable=is_observable,
        target_name=target_name,
        location_name=location.get("name", f"{lat},{lon}"),
        date_range=[datetime.strptime(d, "%Y-%m-%d").date() for d in date_range],
        visibility_windows=visibility_windows,
        recommended_window=recommended_window,
        eliminated_windows=eliminated_windows,
        hourly_data=hourly_data,
        twilight=twilight,
        moon_info=moon_info,
        alternative_suggestions=alternative_suggestions,
        risk_flags=risk_flags,
        observability_csv_path=csv_path,
        visibility_curve_path=curve_path,
    )


# ── Twilight computation ─────────────────────────────

def _local_hour_to_utc(obs_date: datetime, local_hour: float, tz_hours: float) -> datetime:
    """Convert a local hour offset (from midnight of obs_date) to a UTC datetime.

    Correctly handles day rollover: local_hour=25 means 01:00 the next day.
    """
    local_dt = obs_date + timedelta(hours=local_hour)
    return (local_dt - timedelta(hours=tz_hours)).replace(tzinfo=timezone.utc)


def _compute_twilight(
    obs_loc: EarthLocation, obs_date: datetime, tz_hours: float
) -> tuple:
    """Compute evening sunset and twilight times.

    Scans sun altitude from 14:00 to 25:00 local time (covers afternoon
    through ~01:00 the next day) to find sunset and twilight crossings.
    """
    results = [None, None, None, None]  # sunset, civil, nautical, astronomical
    prev_utc = None
    prev_alt = None

    for hour in range(14, 26):  # 14:00 local to 02:00 next day local
        t = _local_hour_to_utc(obs_date, hour, tz_hours)
        astropy_t = _astropy_time(t)
        altaz_frame = AltAz(obstime=astropy_t, location=obs_loc)
        sun = get_body("sun", astropy_t, obs_loc)
        sun_altaz = sun.transform_to(altaz_frame)
        sun_alt = float(sun_altaz.alt.deg)

        if prev_alt is not None:
            if prev_alt > 0 >= sun_alt and results[0] is None:
                results[0] = t  # sunset
            if prev_alt > -6 >= sun_alt and results[1] is None:
                results[1] = t  # civil twilight end
            if prev_alt > -12 >= sun_alt and results[2] is None:
                results[2] = t  # nautical twilight end
            if prev_alt > -18 >= sun_alt and results[3] is None:
                results[3] = t  # astronomical twilight end

        prev_utc = t
        prev_alt = sun_alt

    return tuple(results)


def _compute_morning_twilight(
    obs_loc: EarthLocation, next_date: datetime, tz_hours: float
) -> tuple:
    """Compute morning sunrise and astronomical twilight start.

    Scans sun altitude from 20:00 prev day to 31:00 (07:00 next day) local.
    Uses obs_date as the base date; local_hour >= 24 rolls into next day.
    """
    sunrise = None
    astro_start = None
    # obs_date here is actually obs_date+1 day, so we offset back by using
    # the previous day as base for local hours < 24.
    base_date = next_date - timedelta(days=1)
    prev_alt = None

    for hour in range(20, 32):  # 20:00 to 08:00 next day (local hours from base_date)
        t = _local_hour_to_utc(base_date, hour, tz_hours)
        astropy_t = _astropy_time(t)
        altaz_frame = AltAz(obstime=astropy_t, location=obs_loc)
        sun = get_body("sun", astropy_t, obs_loc)
        sun_altaz = sun.transform_to(altaz_frame)
        sun_alt = float(sun_altaz.alt.deg)

        if prev_alt is not None:
            if prev_alt < -18 <= sun_alt and astro_start is None:
                astro_start = t  # astronomical twilight start (morning)
            if prev_alt < 0 <= sun_alt and sunrise is None:
                sunrise = t  # sunrise

        prev_alt = sun_alt

    return sunrise, astro_start


# ── Utility functions ────────────────────────────────

def _local_to_utc(local_dt: datetime, tz_hours: float) -> datetime:
    """Convert local datetime to UTC."""
    utc_dt = local_dt - timedelta(hours=tz_hours)
    return utc_dt.replace(tzinfo=timezone.utc)


def _to_local(utc_dt: datetime, tz: timezone) -> datetime:
    """Convert UTC datetime to local timezone (returned as naive datetime).

    Returns a naive datetime with local time values so that:
    - String formatting (strftime) shows local time correctly
    - Matplotlib plots local time on axes without auto-converting to UTC
    """
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    local_dt = utc_dt.astimezone(tz)
    return local_dt.replace(tzinfo=None)


def _assess_moon_impact(
    phase: float, min_separation: float, moon_cfg: dict
) -> str:
    """Assess moon impact on deep-sky observation."""
    levels = moon_cfg.get("impact_levels", {})

    if phase < 0.3 and min_separation > 45:
        return "none"
    if phase < 0.5 and min_separation > 30:
        return "low"
    if phase < 0.7 and min_separation > 20:
        return "moderate"
    if phase < 0.9 and min_separation > 10:
        return "high"
    return "severe"


def _compute_risk_flags(
    hourly_data: list[HourlyData],
    moon_info: MoonInfo,
    min_alt: float,
    risk_cfg: dict,
) -> list[RiskFlag]:
    """Compute risk flags based on observed data and risk rules."""
    flags: list[RiskFlag] = []
    alt_cfg = risk_cfg.get("low_altitude", {})
    moon_cfg = risk_cfg.get("moonlight", {})

    # Check if target ever drops below warning altitude
    min_observed_alt = min((h.altitude_deg for h in hourly_data), default=999)
    if min_observed_alt < alt_cfg.get("critical_threshold_deg", 15):
        flags.append(RiskFlag(
            risk_type="low_altitude",
            severity="critical",
            description=f"目标最低高度角 {min_observed_alt:.1f}° 低于临界值 {alt_cfg.get('critical_threshold_deg', 15)}°",
        ))
    elif min_observed_alt < alt_cfg.get("warning_threshold_deg", 30):
        flags.append(RiskFlag(
            risk_type="low_altitude",
            severity="warning",
            description=f"目标最低高度角 {min_observed_alt:.1f}° 低于警告值 {alt_cfg.get('warning_threshold_deg', 30)}°",
        ))

    # Moon risk
    if moon_info.impact_assessment in ("high", "severe"):
        flags.append(RiskFlag(
            risk_type="moonlight",
            severity="critical",
            description=f"月光影响等级: {moon_info.impact_assessment}（月相 {moon_info.phase_fraction:.2f}，最近角距 {moon_info.min_separation_deg:.1f}°）",
        ))
    elif moon_info.impact_assessment == "moderate":
        flags.append(RiskFlag(
            risk_type="moonlight",
            severity="warning",
            description=f"月光影响等级: moderate（月相 {moon_info.phase_fraction:.2f}，最近角距 {moon_info.min_separation_deg:.1f}°）",
        ))

    return flags


def _generate_alternatives(
    target_name: str,
    obs_date: datetime,
    hourly_data: list[HourlyData],
    min_alt: float,
) -> list[AlternativeSuggestion]:
    """Generate alternative suggestions when target is not observable."""
    suggestions: list[AlternativeSuggestion] = []

    # Suggest waiting for a better season
    max_alt = max((h.altitude_deg for h in hourly_data), default=0)
    suggestions.append(
        AlternativeSuggestion(
            suggestion_type="alternative_date",
            description=(
                f"{target_name} 在 {obs_date.strftime('%Y-%m-%d')} 最高高度仅 {max_alt:.1f}°，"
                f"不满足 {min_alt}° 要求。建议等待目标进入更好观测季节。"
            ),
            target_name=target_name,
        )
    )

    # Suggest well-placed seasonal alternatives based on month
    month = obs_date.month
    seasonal_targets = {
        (1, 2, 3): [("M42", "猎户座大星云"), ("M45", "昴星团")],
        (4, 5, 6): [("M51", "涡状星系"), ("M101", "风车星系")],
        (7, 8, 9): [("M13", "武仙座球状星团"), ("M57", "环状星云")],
        (10, 11, 12): [("M31", "仙女座星系"), ("M33", "三角座星系")],
    }
    for months, targets in seasonal_targets.items():
        if month in months:
            for name, cn_name in targets:
                if name != target_name:
                    suggestions.append(
                        AlternativeSuggestion(
                            suggestion_type="alternative_target",
                            description=f"当季更适合观测的目标：{name}（{cn_name}）",
                            target_name=name,
                            suggested_date=obs_date.date(),
                        )
                    )
            break

    return suggestions


# ── Output writers ───────────────────────────────────

def _save_csv(hourly_data: list[HourlyData], path: str) -> None:
    """Save hourly observability data to CSV."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "time", "altitude_deg", "azimuth_deg", "airmass",
            "sun_altitude_deg", "moon_altitude_deg", "moon_separation_deg",
        ])
        for h in hourly_data:
            writer.writerow([
                h.time.isoformat(),
                h.altitude_deg,
                h.azimuth_deg,
                h.airmass if h.airmass else "",
                h.sun_altitude_deg,
                h.moon_altitude_deg if h.moon_altitude_deg else "",
                h.moon_separation_deg if h.moon_separation_deg else "",
            ])


def _save_curve(
    hourly_data: list[HourlyData],
    target_name: str,
    min_alt: float,
    path: str,
    tz_name: str,
) -> None:
    """Save altitude vs time curve to PNG."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Configure CJK font support (Windows / macOS / Linux fallbacks)
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "PingFang SC", "Noto Sans CJK SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    times = [h.time for h in hourly_data]
    alts = [h.altitude_deg for h in hourly_data]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(times, alts, "b-o", markersize=3, label=target_name)
    ax.axhline(y=min_alt, color="r", linestyle="--", alpha=0.7, label=f"最小高度角 {min_alt}°")
    ax.axhline(y=0, color="k", linestyle="-", alpha=0.3)
    ax.set_xlabel(f"时间 ({tz_name})")
    ax.set_ylabel("高度角 (°)")
    ax.set_title(f"{target_name} 高度角-时间曲线")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Format x-axis time labels
    import matplotlib.dates as mdates
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.autofmt_xdate()

    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
