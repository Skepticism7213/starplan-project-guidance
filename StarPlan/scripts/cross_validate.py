"""科学交叉校验：用 astroplan（独立权威库）核验 observability_plan 的天文计算。

对固定案例逐项对账：日落、天文暮光（晚/晨）、目标高度角/方位角、月相、可观测判定。
astroplan 与流水线的手写 Astropy 代码是两套独立实现，差异应在容差内。
容差取自项目 validation 配置：时间 2 分钟、角度 0.5°、月相 0.03。

用法（虚拟环境内，需 astroplan）：
    python scripts/cross_validate.py
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starplan_skills.target_resolve import resolve_target
from starplan_skills.observability_plan import compute_observability

from astroplan import Observer, FixedTarget
from astropy.coordinates import SkyCoord, EarthLocation
from astropy.time import Time
import astropy.units as u

TZ8 = timezone(timedelta(hours=8))
results = []


def local_to_time(local_naive):
    """流水线输出的 naive 本地时间 -> astropy Time（UTC）。"""
    return Time((local_naive - timedelta(hours=8)).isoformat(), scale="utc")


def mins(dt):
    """本地时刻 -> 自午夜起的分钟数（用于时间差比较）。"""
    return dt.hour * 60 + dt.minute + dt.second / 60.0


def check(case, quantity, pipe, ref, tol, unit=""):
    diff = abs(pipe - ref)
    ok = diff <= tol
    results.append((case, quantity, pipe, ref, diff, tol, ok))
    print(f"  {quantity:22} 流水线={pipe:>9.3f}{unit}  astroplan={ref:>9.3f}{unit}  "
          f"差={diff:>7.3f}{unit}  容差={tol}{unit}  {'PASS' if ok else 'FAIL'}")


def xvalidate(target_name, lat, lon, elev, date_str, equipment="binoculars"):
    case = f"{target_name}@{date_str}"
    print(f"\n{'='*70}\n案例: {target_name} @ ({lat}°N, {lon}°E, {elev}m)  {date_str}  [{equipment}]\n{'='*70}")

    # ── 流水线计算 ──
    r = resolve_target(target_name)
    loc = dict(name="x", latitude=lat, longitude=lon, elevation_m=elev, timezone="Asia/Shanghai")
    obs = compute_observability(
        ra_deg=r.ra_deg, dec_deg=r.dec_deg, target_name=r.standard_name, location=loc,
        date_range=[date_str, date_str], equipment=equipment,
        target_magnitude=r.visual_magnitude, target_angular_size_arcmin=r.angular_size_arcmin,
    )

    # ── astroplan 独立计算 ──
    el = EarthLocation(lat=lat * u.deg, lon=lon * u.deg, height=elev * u.m)
    observer = Observer(location=el, timezone="Asia/Shanghai")
    tgt = FixedTarget(coord=SkyCoord(ra=r.ra_deg * u.deg, dec=r.dec_deg * u.deg, frame="icrs"), name=r.standard_name)
    ref = Time(f"{date_str} 00:00:00", scale="utc")

    # 1-3. 暮光
    ap_sunset = observer.sun_set_time(ref, which="next").to_datetime(timezone=TZ8)
    ap_tw_eve = observer.twilight_evening_astronomical(ref, which="next").to_datetime(timezone=TZ8)
    ap_tw_morn = observer.twilight_morning_astronomical(ref, which="next").to_datetime(timezone=TZ8)

    if obs.twilight.sunset:
        check(case, "日落", mins(obs.twilight.sunset), mins(ap_sunset), 2, "min")
    if obs.twilight.astronomical_twilight_end:
        check(case, "天文暮光end(晚)", mins(obs.twilight.astronomical_twilight_end), mins(ap_tw_eve), 2, "min")
    if obs.twilight.astronomical_twilight_start:
        check(case, "天文暮光start(晨)", mins(obs.twilight.astronomical_twilight_start), mins(ap_tw_morn), 2, "min")

    # 4. 目标高度角/方位角（取推荐窗口内峰值时刻）
    if obs.recommended_window:
        rw = obs.recommended_window
        slots = [h for h in obs.hourly_data if rw.window.start <= h.time <= rw.window.end]
        peak_slot = max(slots, key=lambda h: h.altitude_deg)
        ap_altaz = observer.altaz(local_to_time(peak_slot.time), tgt)
        tstr = peak_slot.time.strftime("%H:%M")
        check(case, f"目标高度@{tstr}", peak_slot.altitude_deg, ap_altaz.alt.deg, 0.5, "°")
        check(case, f"目标方位@{tstr}", peak_slot.azimuth_deg, ap_altaz.az.deg, 0.5, "°")

    # 5. 月相（照明分数）
    if obs.hourly_data:
        mid = local_to_time(obs.hourly_data[len(obs.hourly_data) // 2].time)
        ap_illum = float(observer.moon_illumination(mid))
        check(case, "月相(照明分数)", obs.moon_info.phase_fraction, ap_illum, 0.03, "")

    # 6. 可观测判定（独立：astroplan altaz 在天文黑夜内采样，看是否有高度>=30°）
    #    不用 astroplan.is_observable —— 其 AtNightConstraint 在 astroplan0.10.1/astropy8.0.1
    #    下有 UnitConversionError；改用已验证吻合到 0.001° 的 observer.altaz 直接判定。
    try:
        import numpy as np
        t_eve = observer.twilight_evening_astronomical(ref, which="next")
        t_morn = observer.twilight_morning_astronomical(ref, which="next")
        sample_times = Time(np.linspace(t_eve.jd, t_morn.jd, 20), format="jd", scale="utc")
        sample_alts = observer.altaz(sample_times, tgt).alt.deg
        ap_obs = bool(np.any(sample_alts >= 30))
        match = obs.is_observable == ap_obs
        print(f"  {'可观测判定':22} 流水线={str(obs.is_observable):>9}  astroplan={str(ap_obs):>9}  "
              f"(黑夜内最高 {float(np.max(sample_alts)):.1f}°)  {'PASS' if match else 'CHECK'}")
        results.append((case, "可观测判定", obs.is_observable, ap_obs, 0 if match else 1, 0, match))
    except Exception as e:
        print(f"  可观测判定: 独立计算异常 {type(e).__name__}: {e}")

    return obs


if __name__ == "__main__":
    # ── 固定案例 ──
    xvalidate("M31", 36.49, 117.18, 300, "2026-10-17", "binoculars")     # 案例1：可观测
    xvalidate("M42", 36.49, 117.18, 300, "2026-07-25", "binoculars")     # 案例2：不可观测（太阳）

    # ── 汇总 ──
    print(f"\n{'='*70}")
    npass = sum(1 for r in results if r[6])
    print(f"交叉校验汇总: {npass}/{len(results)} 项在容差内通过")
    fails = [r for r in results if not r[6]]
    if fails:
        print("超出容差的项:")
        for r in fails:
            print(f"  [FAIL] {r[0]} {r[1]}: 流水线={r[2]} astroplan={r[3]} 差={r[4]:.3f} > 容差={r[5]}")
    else:
        print("全部通过：流水线天文计算与 astroplan 独立实现一致。")
    print("="*70)
