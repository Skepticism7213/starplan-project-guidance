"""observability_plan 边界案例回归测试（WARNING-1 / WARNING-2）。

WARNING-1：极昼（高纬度夏季太阳整夜不落）不得判为可观测。
WARNING-2：纬度受限目标（永远低于最低高度）应给 alternative_location，而非 alternative_date。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starplan_skills.target_resolve import resolve_target
from starplan_skills.observability_plan import compute_observability

JN = dict(name='四门塔', latitude=36.49, longitude=117.18, elevation_m=300, timezone='Asia/Shanghai')
HIGH_LAT = dict(name='高纬测试', latitude=70.0, longitude=117.0, elevation_m=0, timezone='Asia/Shanghai')


def _compute(target, loc, dr, eq='binoculars'):
    r = resolve_target(target)
    assert r.confidence > 0, f"target {target} not resolved"
    return compute_observability(
        ra_deg=r.ra_deg, dec_deg=r.dec_deg, target_name=r.standard_name,
        location=loc, date_range=dr, equipment=eq,
        target_magnitude=r.visual_magnitude,
        target_angular_size_arcmin=r.angular_size_arcmin,
    )


def test_warning1_polar_day_not_observable():
    """WARNING-1：高纬度极昼时太阳整夜不落，即使目标高度合适也不得判为可观测。"""
    obs = _compute('M31', HIGH_LAT, ['2026-06-21', '2026-06-21'])
    assert obs.is_observable is False
    # 回退夜间窗口内太阳全程在地平线上
    if obs.hourly_data:
        assert all(h.sun_altitude_deg > 0 for h in obs.hourly_data)
    # Phase D (C-06): reason must be no_astronomical_night, NOT moonlight
    assert obs.not_observable_reason == "no_astronomical_night", (
        f"Polar day should give no_astronomical_night, got {obs.not_observable_reason}"
    )


def test_warning2_latitude_limited_gives_location_not_date():
    """WARNING-2：纬度受限目标（永远低于最低高度）应建议换地点，而非改期。"""
    obs = _compute('M70', JN, ['2026-07-10', '2026-07-10'], 'small_telescope')
    assert obs.is_observable is False
    types = [s.suggestion_type for s in obs.alternative_suggestions]
    assert 'alternative_location' in types
    assert 'alternative_date' not in types


def test_date_limited_still_gives_alternative_date():
    """对照：原理上可观测但当日被太阳/月光阻挡的目标，仍应建议改期。"""
    obs = _compute('M42', JN, ['2026-07-25', '2026-07-25'])
    assert obs.is_observable is False
    types = [s.suggestion_type for s in obs.alternative_suggestions]
    assert 'alternative_date' in types
    assert 'alternative_location' not in types


def test_normal_observable_no_regression():
    """回归基线：正常可观测目标在修复后仍正常工作。"""
    obs = _compute('M31', JN, ['2026-10-17', '2026-10-17'])
    assert obs.is_observable is True
    assert obs.recommended_window is not None
    assert abs(obs.recommended_window.peak_altitude_deg - 85.0) < 1.0


def test_sun_guard_does_not_over_exclude_dark_slots():
    """WARNING-1 补充：正常暗夜下，推荐窗口内太阳远低于阈值，太阳判据不会误伤有效时段。"""
    obs = _compute('M31', JN, ['2026-10-17', '2026-10-17'])
    assert obs.is_observable is True
    assert obs.recommended_window is not None
    rw = obs.recommended_window
    window_slots = [h for h in obs.hourly_data if rw.window.start <= h.time <= rw.window.end]
    assert window_slots, "recommended window should contain hourly slots"
    # 推荐窗口内太阳全程低于天文暮光阈值，说明太阳判据未误伤有效暗夜时段
    assert all(h.sun_altitude_deg < -18.0 for h in window_slots)
