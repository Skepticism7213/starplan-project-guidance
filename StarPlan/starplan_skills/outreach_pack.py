"""
StarPlan Loop - Skill 3: outreach_pack (stub for MVP)

Generates outreach activity packs from verified fact cards and
calculation results. In the MVP phase, this uses template-based
generation. Full Qwen-powered generation is planned for Week 3.

Core principle: Never fill in numerical values that are not in the
fact cards. Mark unconfirmed items instead.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from .schemas import (
    ActivityScheduleItem,
    EquipmentItem,
    FactCard,
    ObservabilityResult,
    OutreachPack,
    ResolvedTarget,
)


def generate_outreach_pack(
    target: ResolvedTarget,
    obs_result: ObservabilityResult,
    audience: str,
    equipment: str,
    goal: str = "校园科普观测",
    run_dir: Optional[Path] = None,
) -> OutreachPack:
    """
    Generate an outreach activity pack based on verified facts.

    Args:
        target: Resolved target information.
        obs_result: Observability computation results.
        audience: Target audience description.
        equipment: Available equipment.
        goal: Activity goal.
        run_dir: Output directory for the markdown file.

    Returns:
        OutreachPack with schedule, talking points, checklist, etc.
    """
    # Build fact cards from target + obs_result
    fact_cards = _build_fact_cards(target, obs_result)

    # Generate activity schedule based on recommended window
    schedule = _build_schedule(obs_result, audience)

    # Generate talking points based on target type and audience
    talking_points = _build_talking_points(target, audience, fact_cards)

    # Equipment checklist
    equipment_checklist = _build_equipment_checklist(equipment, target, obs_result)

    # Safety notes
    safety_notes = [
        "夜间活动请注意人身安全，避免单独行动",
        "使用红色手电筒保护暗适应视力",
        "注意保暖，10 月夜间气温可能降至 10°C 以下",
        "请勿使用激光笔直接指向天空有人区域",
    ]

    # Manual check items
    manual_check_items = [
        f"确认目标坐标来源: {target.source}",
        f"确认推荐时段的天文暮光时间是否准确",
        "确认活动地点夜间开放且安全",
        "确认设备电池充足、三脚架稳固",
    ]

    # Unconfirmed items (things we can't verify from data alone)
    unconfirmed_items: list[str] = []
    if not target.visual_magnitude:
        unconfirmed_items.append(f"目标 {target.standard_name} 的视星等数据缺失，无法确认目视难度")
    if not target.angular_size_arcmin:
        unconfirmed_items.append(f"目标 {target.standard_name} 的角大小数据缺失，无法确认设备匹配度")

    # Generate markdown file
    md_path = None
    if run_dir:
        md_path = str(run_dir / "outreach_pack.md")
        _write_outreach_markdown(
            target, obs_result, schedule, talking_points,
            equipment_checklist, safety_notes, manual_check_items,
            unconfirmed_items, audience, md_path,
        )

    return OutreachPack(
        target_name=target.standard_name,
        audience=audience,
        activity_schedule=schedule,
        talking_points=talking_points,
        equipment_checklist=equipment_checklist,
        safety_notes=safety_notes,
        manual_check_items=manual_check_items,
        unconfirmed_items=unconfirmed_items,
        outreach_pack_md_path=md_path,
    )


def _build_fact_cards(target: ResolvedTarget, obs: ObservabilityResult) -> list[FactCard]:
    """Build fact cards from target and observability data."""
    cards = [
        FactCard(key="standard_name", value=target.standard_name, source=target.source),
        FactCard(key="target_type", value=target.target_type, source=target.source),
        FactCard(key="coordinates", value=f"RA={target.ra_deg:.4f}°, Dec={target.dec_deg:.4f}°", source=target.source),
    ]
    if target.visual_magnitude is not None:
        cards.append(FactCard(key="visual_magnitude", value=f"{target.visual_magnitude:.1f}", source=target.source))
    if target.angular_size_arcmin:
        cards.append(FactCard(
            key="angular_size",
            value=f"{target.angular_size_arcmin[0]:.1f}' × {target.angular_size_arcmin[1]:.1f}'",
            source=target.source,
        ))
    if target.constellation:
        cards.append(FactCard(key="constellation", value=target.constellation, source=target.source))
    if obs.recommended_window:
        cards.append(FactCard(
            key="peak_altitude",
            value=f"{obs.recommended_window.peak_altitude_deg:.1f}°",
            source="astroplan/astropy",
        ))
    return cards


def _build_schedule(obs: ObservabilityResult, audience: str) -> list[ActivityScheduleItem]:
    """Build activity schedule from observability results."""
    schedule: list[ActivityScheduleItem] = []

    if obs.twilight.astronomical_twilight_end:
        tw_end = obs.twilight.astronomical_twilight_end.strftime("%H:%M")
        schedule.append(ActivityScheduleItem(
            time_label=tw_end,
            activity="天文暮光结束，开始准备设备",
            notes="等待天空完全变暗",
        ))

    if obs.recommended_window:
        w = obs.recommended_window.window
        start_str = w.start.strftime("%H:%M")
        end_str = w.end.strftime("%H:%M")
        schedule.append(ActivityScheduleItem(
            time_label=start_str,
            activity=f"开始观测 {obs.target_name}",
            notes=f"推荐观测时段，峰值高度角 {obs.recommended_window.peak_altitude_deg:.1f}°",
        ))
        schedule.append(ActivityScheduleItem(
            time_label=f"{start_str} ~ {end_str}",
            activity="观测进行中",
            notes="引导成员使用星桥法寻找目标",
        ))
        schedule.append(ActivityScheduleItem(
            time_label=end_str,
            activity="推荐时段结束",
            notes="目标高度角逐渐降低",
        ))

    if obs.twilight.astronomical_twilight_start:
        tw_start = obs.twilight.astronomical_twilight_start.strftime("%H:%M")
        schedule.append(ActivityScheduleItem(
            time_label=tw_start,
            activity="天文暮光开始，活动结束",
            notes="收拾设备，合影留念",
        ))

    return schedule


def _build_talking_points(
    target: ResolvedTarget, audience: str, fact_cards: list[FactCard]
) -> list[str]:
    """Build talking points based on target type and audience."""
    points: list[str] = []

    if target.target_type == "deep_sky":
        points.append(f"今晚我们要观测的是 {target.standard_name}")
        if target.constellation:
            points.append(f"它位于 {target.constellation} 星座方向")
        if target.visual_magnitude is not None:
            points.append(f"它的视星等约为 {target.visual_magnitude:.1f}")
        if target.angular_size_arcmin:
            points.append(f"它在天空中的角大小约为 {target.angular_size_arcmin[0]:.1f} 角分")
        points.append("使用双筒望远镜可以看到一团模糊的光斑")
        points.append("这是由数十亿颗恒星组成的庞大星系/星云")
    elif target.target_type == "star":
        points.append(f"今晚我们要观测的恒星是 {target.standard_name}")
        if target.constellation:
            points.append(f"它位于 {target.constellation} 星座")
        if target.visual_magnitude is not None:
            points.append(f"它的视星等约为 {target.visual_magnitude:.1f}")

    if "新成员" in audience or "新手" in audience:
        points.append("建议大家先用肉眼熟悉星空，找到目标所在的大致方向")
        points.append("使用星桥法：从已知的亮星出发，逐步找到目标")

    return points


def _build_equipment_checklist(
    equipment: str, target: ResolvedTarget, obs: ObservabilityResult
) -> list[EquipmentItem]:
    """Build equipment checklist."""
    items: list[EquipmentItem] = []

    if equipment == "binoculars":
        items.append(EquipmentItem(item="双筒望远镜（7×50 或 10×50 推荐）", quantity="每组 1 台"))
        items.append(EquipmentItem(item="三脚架或望远镜支架", quantity="每组 1 个", notes="双筒手持容易抖动"))
    elif equipment == "small_telescope":
        items.append(EquipmentItem(item="小型天文望远镜（口径 ≥ 80mm）", quantity="每组 1 台"))
        items.append(EquipmentItem(item="目镜（低倍率广角推荐）", quantity="2-3 个"))
    elif equipment == "naked_eye":
        items.append(EquipmentItem(item="无需特殊设备", quantity="—"))

    items.append(EquipmentItem(item="活动星图或手机星图 App", quantity="每组 1 个"))
    items.append(EquipmentItem(item="红色手电筒", quantity="每组 1 个", notes="保护暗适应视力"))
    items.append(EquipmentItem(item="保暖衣物", quantity="每人", notes="夜间气温可能较低"))
    items.append(EquipmentItem(item="记录本和笔", quantity="每组 1 套"))
    items.append(EquipmentItem(item="防蚊液", quantity="适量", notes="户外使用"))

    return items


def _write_outreach_markdown(
    target, obs, schedule, talking_points, equipment_checklist,
    safety_notes, manual_check_items, unconfirmed_items, audience, path: str,
) -> None:
    """Write the outreach pack as a markdown file."""
    lines: list[str] = []
    lines.append(f"# {target.standard_name} 观测活动包")
    lines.append(f"")
    lines.append(f"**受众**: {audience}  ")
    lines.append(f"**日期**: {obs.date_range[0]}  ")
    lines.append(f"**地点**: {obs.location_name}  ")
    lines.append(f"**可观测**: {'是' if obs.is_observable else '否'}")
    lines.append("")

    if obs.recommended_window:
        w = obs.recommended_window.window
        lines.append(f"## 推荐观测时段")
        lines.append(f"")
        lines.append(f"- **时间**: {w.start.strftime('%H:%M')} ~ {w.end.strftime('%H:%M')}")
        lines.append(f"- **峰值高度角**: {obs.recommended_window.peak_altitude_deg:.1f}°")
        lines.append(f"- **理由**: {obs.recommended_window.reason}")
        lines.append("")

    lines.append("## 活动流程")
    lines.append("")
    for item in schedule:
        notes_str = f"（{item.notes}）" if item.notes else ""
        lines.append(f"- **{item.time_label}**: {item.activity}{notes_str}")
    lines.append("")

    lines.append("## 讲解要点")
    lines.append("")
    for tp in talking_points:
        lines.append(f"- {tp}")
    lines.append("")

    lines.append("## 设备清单")
    lines.append("")
    for eq in equipment_checklist:
        notes_str = f"（{eq.notes}）" if eq.notes else ""
        lines.append(f"- {eq.item} × {eq.quantity}{notes_str}")
    lines.append("")

    lines.append("## 安全提示")
    lines.append("")
    for sn in safety_notes:
        lines.append(f"- {sn}")
    lines.append("")

    lines.append("## 人工核对项")
    lines.append("")
    for mc in manual_check_items:
        lines.append(f"- [ ] {mc}")
    lines.append("")

    if unconfirmed_items:
        lines.append("## 待确认项")
        lines.append("")
        for ui in unconfirmed_items:
            lines.append(f"- ⚠️ {ui}")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
