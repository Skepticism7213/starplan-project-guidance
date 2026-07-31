"""
StarPlan Loop - Skill 3: outreach_pack (Week 3: Qwen-enhanced)

Generates outreach activity packs from verified fact cards and
calculation results.

Two modes:
  - Template mode (default fallback): deterministic, no model call.
  - Qwen mode: Qwen generates richer talking points from fact cards,
    with a validation layer that rejects any numerical value not
    traceable to a fact card or tool output.

Core principle: Never fill in numerical values that are not in the
fact cards. Mark unconfirmed items instead.

P1-P8 fix log (2026-07-30):
  P1: equipment passed into Qwen prompt to constrain device descriptions.
  P2/P6: untraceable qualitative claims auto-flagged as unconfirmed.
  P3/P4: safety notes dynamically generated from observation date (season-aware).
  P5: circumpolar stars use "整夜可见" instead of misleading "升到最高点".
  P7: moon risk (phase, impact, risk_flags) injected into prompt and template.
  P8: template uses precise type label (星系/星云/星团) instead of "星系/星云".
"""

from __future__ import annotations

import os
import re
from datetime import date
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


# ── P3/P4 fix: dynamic season/temperature safety note ──

def _season_safety_note(obs_date: date) -> str:
    """Generate a season-appropriate temperature safety note from the observation date."""
    month = obs_date.month
    if month in (12, 1, 2):
        return "注意防寒保暖，冬季夜间气温可能降至 0°C 以下，请穿戴厚外套、帽子和手套"
    elif month in (3, 4, 5):
        return "春季夜间气温仍较低（约 5-15°C），建议携带外套"
    elif month in (6, 7, 8):
        return "夏季夜间较为温暖，但仍建议携带薄外套；注意防蚊虫"
    else:  # 9, 10, 11
        return "注意保暖，秋季夜间气温可能降至 10°C 以下，建议携带外套"


# ── P8 fix: precise deep-sky type label ──

_DEEP_SKY_TYPE_MAP = {
    "M31": "星系", "M33": "星系", "M51": "星系", "M81": "星系", "M101": "星系",
    "M42": "星云", "M8": "星云", "M17": "星云", "M27": "星云", "M57": "星云",
    "NGC 7000": "星云", "NGC 6960": "星云",
    "M13": "球状星团", "M3": "球状星团", "M5": "球状星团", "M22": "球状星团",
    "M45": "疏散星团", "M44": "疏散星团", "M67": "疏散星团",
}

def _target_type_label(target: ResolvedTarget) -> str:
    """Return a precise Chinese type label for the target."""
    if target.target_type == "star":
        return "恒星"
    if target.target_type == "deep_sky":
        # Try catalog-based lookup
        name_upper = target.standard_name.upper().replace(" ", " ")
        for key, label in _DEEP_SKY_TYPE_MAP.items():
            if key.upper() == name_upper:
                return label
        # Heuristic fallback based on common naming patterns
        if target.standard_name.startswith("M") or target.standard_name.startswith("NGC"):
            return "深空天体"
        return "深空天体"
    if target.target_type == "planet":
        return "行星"
    if target.target_type == "asterism":
        return "星群"
    return "天体"


# ── P5 fix: detect circumpolar targets ──

def _is_circumpolar(target: ResolvedTarget, latitude: float) -> bool:
    """Check if a target is circumpolar (never sets) for the given latitude."""
    # A target is circumpolar if its declination > 90 - latitude (northern hemisphere)
    # or declination < -(90 - |latitude|) for southern hemisphere
    if latitude > 0:
        return target.dec_deg > (90.0 - latitude)
    else:
        return target.dec_deg < -(90.0 + latitude)


# ── P1 fix: equipment description for prompt ──

_EQUIPMENT_DESC = {
    "naked_eye": "肉眼（无光学设备）",
    "binoculars": "双筒望远镜（7×50 或 10×50）",
    "small_telescope": "小型天文望远镜（口径 80-150mm）",
    "large_telescope": "大型天文望远镜（口径 > 200mm）",
}


def generate_outreach_pack(
    target: ResolvedTarget,
    obs_result: ObservabilityResult,
    audience: str,
    equipment: str,
    goal: str = "校园科普观测",
    run_dir: Optional[Path] = None,
    use_qwen: bool = True,
    log_path: Optional[str] = None,
) -> OutreachPack:
    """
    Generate an outreach activity pack based on verified facts.
    """
    # C-3 fix: If target is NOT observable, generate a cancellation/alternative pack.
    if not obs_result.is_observable:
        return _generate_not_observable_pack(
            target=target,
            obs_result=obs_result,
            audience=audience,
            equipment=equipment,
            goal=goal,
            run_dir=run_dir,
        )

    # Build fact cards from target + obs_result
    fact_cards = _build_fact_cards(target, obs_result)

    # Generate activity schedule based on recommended window
    schedule = _build_schedule(obs_result, audience)

    # Generate talking points: try Qwen first, fall back to template
    qwen_used = False
    qwen_validation_issues: list[str] = []
    if use_qwen and _qwen_available():
        try:
            talking_points, qwen_validation_issues = _generate_talking_points_qwen(
                target, obs_result, audience, equipment, fact_cards, log_path,
            )
            qwen_used = True
        except Exception as e:
            talking_points = _build_talking_points(target, obs_result, audience, equipment, fact_cards)
            qwen_validation_issues = [f"Qwen 调用失败，回退到模板: {e}"]
    else:
        talking_points = _build_talking_points(target, obs_result, audience, equipment, fact_cards)

    # Equipment checklist
    equipment_checklist = _build_equipment_checklist(equipment, target, obs_result)

    # P3/P4 fix: dynamic safety notes based on observation date
    obs_date = obs_result.date_range[0]
    safety_notes = [
        "夜间活动请注意人身安全，避免单独行动",
        "使用红色手电筒保护暗适应视力",
        _season_safety_note(obs_date),
        "请勿使用激光笔直接指向天空有人区域",
    ]

    # Manual check items
    manual_check_items = [
        f"确认目标坐标来源: {target.source}",
        "确认推荐时段的天文暮光时间是否准确",
        "确认活动地点夜间开放且安全",
        "确认设备电池充足、三脚架稳固",
    ]

    # Unconfirmed items (things we can't verify from data alone)
    unconfirmed_items: list[str] = []
    if not target.visual_magnitude:
        unconfirmed_items.append(f"目标 {target.standard_name} 的视星等数据缺失，无法确认目视难度")
    if not target.angular_size_arcmin:
        unconfirmed_items.append(f"目标 {target.standard_name} 的角大小数据缺失，无法确认设备匹配度")

    # P7 fix: surface moon risk in unconfirmed/warning items
    if obs_result.moon_info and obs_result.moon_info.impact_assessment in ("high", "severe"):
        unconfirmed_items.append(
            f"⚠️ 月光影响等级: {obs_result.moon_info.impact_assessment}"
            f"（月相 {obs_result.moon_info.phase_fraction:.2f}，"
            f"最近角距 {obs_result.moon_info.min_separation_deg:.1f}°），"
            f"深空目标实际可见度可能严重下降，建议现场评估后决定是否继续"
        )

    # Append Qwen validation issues to unconfirmed items
    if qwen_validation_issues:
        unconfirmed_items.extend(qwen_validation_issues)

    # Generate markdown file
    md_path = None
    if run_dir:
        md_path = str(run_dir / "outreach_pack.md")
        _write_outreach_markdown(
            target, obs_result, schedule, talking_points,
            equipment_checklist, safety_notes, manual_check_items,
            unconfirmed_items, audience, md_path, qwen_used=qwen_used,
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
        qwen_used=qwen_used,
        qwen_validation_issues=qwen_validation_issues,
    )


def _generate_not_observable_pack(
    target: ResolvedTarget,
    obs_result: ObservabilityResult,
    audience: str,
    equipment: str,
    goal: str,
    run_dir: Optional[Path] = None,
) -> OutreachPack:
    """C-3 fix: Generate a cancellation/reschedule/alternative pack."""
    talking_points = _build_not_observable_talking_points(target, obs_result, audience)
    alt_suggestions = [s.description for s in obs_result.alternative_suggestions]
    schedule = _build_not_observable_schedule(obs_result, alt_suggestions)

    manual_check_items = [
        f"确认 {target.standard_name} 在改期日期是否可观测（重新运行 StarPlan）",
        "确认替代目标的设备匹配度",
        "通知参与成员活动调整安排",
    ]

    md_path = None
    if run_dir:
        md_path = str(run_dir / "outreach_pack.md")
        _write_not_observable_markdown(
            target, obs_result, schedule, talking_points,
            alt_suggestions, manual_check_items, audience, md_path,
        )

    return OutreachPack(
        target_name=target.standard_name,
        audience=audience,
        pack_type="not_observable",
        activity_schedule=schedule,
        talking_points=talking_points,
        equipment_checklist=[],
        safety_notes=[],
        manual_check_items=manual_check_items,
        unconfirmed_items=[],
        alternative_suggestions=alt_suggestions,
        outreach_pack_md_path=md_path,
        qwen_used=False,
        qwen_validation_issues=[],
    )


def _not_observable_reason_text(reason: Optional[str]) -> str:
    """Human-readable phrase for why the target is not observable."""
    return {
        "latitude": "在本地高度角永远不足（纬度受限，改期无效）",
        "moonlight": "当晚月光影响严重，遮挡了观测窗口",
        "altitude": "夜间最高高度角过低",
    }.get(reason or "altitude", "夜间最高高度角过低")


def _build_not_observable_talking_points(
    target: ResolvedTarget,
    obs: ObservabilityResult,
    audience: str,
) -> list[str]:
    """Build talking points for a not-observable target."""
    points: list[str] = []
    reason = getattr(obs, "not_observable_reason", None)
    points.append(
        f"{target.standard_name} 在 {obs.date_range[0]} 当晚不满足观测条件"
        f"（{_not_observable_reason_text(reason)}），本次观测活动取消或改期"
    )

    if target.target_type == "deep_sky":
        if target.constellation:
            points.append(f"{target.standard_name} 位于 {target.constellation} 星座方向")
        if target.visual_magnitude is not None:
            points.append(f"它的视星等约为 {target.visual_magnitude:.1f}，属于深空天体")
        if reason == "moonlight":
            points.append("该目标本身高度角合适，但当晚月光过强，不适合观测")
        else:
            points.append("该目标在当前季节处于太阳方向附近/地平线以下，无法在夜间观测")
    elif target.target_type == "star":
        if target.constellation:
            points.append(f"{target.standard_name} 是 {target.constellation} 座的恒星")
        points.append("该恒星在当前季节的夜间不可见")

    if obs.alternative_suggestions:
        alt_names = [
            s.target_name for s in obs.alternative_suggestions
            if s.target_name and s.target_name != target.standard_name
        ]
        if alt_names:
            points.append(f"当季更适合观测的替代目标：{'、'.join(alt_names)}")
        if reason == "moonlight":
            points.append("建议将活动改期到月光较弱的日期（如新月前后）再举行")
        else:
            points.append("建议将活动改期到目标进入最佳观测季节时再举行")

    if "新成员" in audience or "新手" in audience:
        points.append("可以利用本次集会时间进行室内天文知识讲座或星图认读练习")

    return points


def _build_not_observable_schedule(
    obs: ObservabilityResult,
    alt_suggestions: list[str],
) -> list[ActivityScheduleItem]:
    """Build a 'what to do instead' schedule for a not-observable night."""
    schedule: list[ActivityScheduleItem] = []
    schedule.append(ActivityScheduleItem(
        time_label="活动调整",
        activity="原定观测活动取消/改期",
        notes="目标不满足观测条件",
    ))
    if alt_suggestions:
        schedule.append(ActivityScheduleItem(
            time_label="替代方案",
            activity="考虑替代目标或改期",
            notes="；".join(alt_suggestions[:3]),
        ))
    schedule.append(ActivityScheduleItem(
        time_label="建议",
        activity="室内替代活动：天文讲座 / 星图认读 / 观测计划讨论",
        notes="保持成员参与热情",
    ))
    return schedule


def _write_not_observable_markdown(
    target, obs, schedule, talking_points,
    alt_suggestions, manual_check_items, audience, path: str,
) -> None:
    """Write a not-observable pack as markdown."""
    lines: list[str] = []
    lines.append(f"# {target.standard_name} 观测取消/改期通知")
    lines.append("")
    lines.append(f"**受众**: {audience}  ")
    lines.append(f"**原定日期**: {obs.date_range[0]}  ")
    lines.append(f"**地点**: {obs.location_name}  ")
    lines.append(f"**状态**: 目标不可观测，活动取消/改期  ")
    lines.append(f"**生成方式**: 模板（不可观测场景不调用 Qwen）")
    lines.append("")
    lines.append("## 不可观测原因")
    lines.append("")
    lines.append(
        f"- {target.standard_name} 在 {obs.date_range[0]} 当晚不满足最低观测条件："
        f"{_not_observable_reason_text(getattr(obs, 'not_observable_reason', None))}"
    )
    if obs.risk_flags:
        for rf in obs.risk_flags:
            lines.append(f"- 风险: {rf.description}")
    lines.append("")
    if alt_suggestions:
        lines.append("## 替代建议")
        lines.append("")
        for s in alt_suggestions:
            lines.append(f"- {s}")
        lines.append("")
    lines.append("## 说明要点")
    lines.append("")
    for tp in talking_points:
        lines.append(f"- {tp}")
    lines.append("")
    lines.append("## 建议安排")
    lines.append("")
    for item in schedule:
        notes_str = f"（{item.notes}）" if item.notes else ""
        lines.append(f"- **{item.time_label}**: {item.activity}{notes_str}")
    lines.append("")
    lines.append("## 人工核对项")
    lines.append("")
    for mc in manual_check_items:
        lines.append(f"- [ ] {mc}")
    lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


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
        cards.append(FactCard(
            key="peak_airmass",
            value=f"{obs.recommended_window.peak_airmass:.2f}",
            source="astroplan/astropy",
        ))
        w = obs.recommended_window.window
        cards.append(FactCard(
            key="recommended_window",
            value=f"{w.start.strftime('%H:%M')} ~ {w.end.strftime('%H:%M')}",
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
    target: ResolvedTarget,
    obs_result: ObservabilityResult,
    audience: str,
    equipment: str,
    fact_cards: list[FactCard],
) -> list[str]:
    """Build talking points based on target type, audience, and equipment (template mode)."""
    points: list[str] = []
    type_label = _target_type_label(target)  # P8 fix
    equip_desc = _EQUIPMENT_DESC.get(equipment, equipment)

    if target.target_type == "deep_sky":
        points.append(f"今晚我们要观测的是 {target.standard_name}（{_target_type_label(target)}）")
        if target.constellation:
            points.append(f"它位于 {target.constellation} 星座方向")
        if target.visual_magnitude is not None:
            points.append(f"它的视星等约为 {target.visual_magnitude:.1f}")
        if target.angular_size_arcmin:
            points.append(f"它在天空中的角大小约为 {target.angular_size_arcmin[0]:.1f} 角分")
        # P1 fix: equipment-aware description
        if equipment == "naked_eye":
            points.append("在暗夜环境下，肉眼可以看到一个模糊的光点")
        elif equipment == "binoculars":
            points.append(f"使用{equip_desc}可以看到一团模糊的光斑")
        elif equipment in ("small_telescope", "large_telescope"):
            points.append(f"使用{equip_desc}可以观察到更多结构细节")
        # P8 fix: precise type
        if type_label == "星系":
            points.append("这是由数十亿颗恒星组成的庞大星系")
        elif type_label == "星云":
            points.append("这是由气体和尘埃组成的星际云团，是恒星诞生的摇篮")
        elif type_label == "球状星团":
            points.append("这是由数十万颗古老恒星紧密聚集而成的球状星团")
        elif type_label == "疏散星团":
            points.append("这是由年轻恒星松散聚集而成的疏散星团")
        else:
            points.append("这是一个位于太阳系之外的深空天体")
    elif target.target_type == "star":
        points.append(f"今晚我们要观测的恒星是 {target.standard_name}")
        if target.constellation:
            points.append(f"它位于 {target.constellation} 星座")
        if target.visual_magnitude is not None:
            points.append(f"它的视星等约为 {target.visual_magnitude:.1f}")
        # P5 fix: circumpolar awareness
        latitude = 36.49  # default Jinan; ideally from obs_result location
        if _is_circumpolar(target, latitude):
            points.append("作为拱极星，它整夜可见且高度角几乎不变，是辨认方向的天然路标")

    # P7 fix: moon risk warning in template talking points
    if obs_result.moon_info and obs_result.moon_info.impact_assessment in ("high", "severe"):
        mi = obs_result.moon_info
        points.append(
            f"注意：今晚月光影响等级为 {mi.impact_assessment}"
            f"（月相 {mi.phase_fraction:.2f}），深空目标的可见度会明显下降，"
            f"请做好心理准备并优先观测亮目标"
        )

    if "新成员" in audience or "新手" in audience:
        points.append("建议大家先用肉眼熟悉星空，找到目标所在的大致方向")
        points.append("使用星桥法：从已知的亮星出发，逐步找到目标")

    return points


# ── Qwen-enhanced talking points (Week 3) ────────────

def _qwen_available() -> bool:
    """Check if DASHSCOPE_API_KEY is configured and usable."""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    return bool(api_key) and api_key != "your_api_key_here"


def _generate_talking_points_qwen(
    target: ResolvedTarget,
    obs_result: ObservabilityResult,
    audience: str,
    equipment: str,  # P1 fix: added
    fact_cards: list[FactCard],
    log_path: Optional[str] = None,
) -> tuple[list[str], list[str]]:
    """
    Use Qwen to generate richer talking points grounded in fact cards.
    """
    from .qwen_client import call_qwen_json

    # Build fact card context string
    fact_context = "\n".join(
        f"- {card.key}: {card.value} (来源: {card.source})"
        for card in fact_cards
    )

    # Build recommended window info
    window_info = ""
    if obs_result.recommended_window:
        w = obs_result.recommended_window.window
        window_info = (
            f"\n推荐观测时段: {w.start.strftime('%H:%M')} ~ {w.end.strftime('%H:%M')}"
            f"\n峰值高度角: {obs_result.recommended_window.peak_altitude_deg:.1f}°"
            f"\n大气质量: {obs_result.recommended_window.peak_airmass:.2f}"
        )

    # P1 fix: equipment constraint
    equip_desc = _EQUIPMENT_DESC.get(equipment, equipment)
    equipment_constraint = (
        f"\n\n【设备约束】\n"
        f"本次活动使用的设备是：{equip_desc}。\n"
        f"讲解中描述观测效果时必须匹配该设备能力，不得描述该设备无法达到的效果。"
    )

    # P7 fix: moon risk injection
    moon_constraint = ""
    if obs_result.moon_info and obs_result.moon_info.impact_assessment in ("high", "severe"):
        mi = obs_result.moon_info
        moon_constraint = (
            f"\n\n【月光风险警告】\n"
            f"今晚月光影响等级为 {mi.impact_assessment}（月相 {mi.phase_fraction:.2f}，"
            f"月球与目标最近角距 {mi.min_separation_deg:.1f}°）。\n"
            f"讲解中必须提醒受众：月光会严重影响深空目标可见度，"
            f"不得描述'观测条件完美/理想'等正面措辞。"
        )

    # P5 fix: circumpolar note
    circumpolar_note = ""
    latitude = 36.49
    if _is_circumpolar(target, latitude):
        circumpolar_note = (
            "\n\n【特殊天体提示】\n"
            "该目标为拱极星，整夜高度角几乎不变（不存在升落），"
            "不要使用'升到最高点''升起''落下'等表述。"
        )

    # P2/P6 fix: grounding constraint for qualitative claims
    grounding_rule = (
        "\n6. 不要添加事实卡中未提供的定性天文知识（如'恒星诞生区''最近的星系'等），"
        "除非事实卡明确包含该信息。如需使用，请在该条末尾加注'（待核实）'。"
    )

    system_prompt = (
        "你是一位天文科普讲解员，负责为校园天文观测活动撰写讲解要点。\n"
        "严格规则：\n"
        "1. 你只能使用【事实卡】中提供的数值，绝对不能编造任何数字。\n"
        "2. 如果事实卡没有提供某项数据，不要提及具体数值，可以用定性描述。\n"
        "3. 讲解要生动有趣，适合目标受众，但科学准确性是第一位的。\n"
        "4. 每条讲解要点一句话，控制在 6-10 条。\n"
        "5. 返回 JSON 格式: {\"talking_points\": [\"要点1\", \"要点2\", ...]}\n"
        f"{grounding_rule}"
    )

    user_prompt = (
        f"【事实卡】\n{fact_context}\n"
        f"{window_info}\n\n"
        f"【目标信息】\n"
        f"- 标准名称: {target.standard_name}\n"
        f"- 类型: {target.target_type}（{_target_type_label(target)}）\n"
        f"- 星座: {target.constellation or '未知'}\n\n"
        f"【受众】{audience}\n"
        f"{equipment_constraint}"
        f"{moon_constraint}"
        f"{circumpolar_note}\n\n"
        f"请基于以上事实卡撰写讲解要点。记住：不要编造任何数值！"
    )

    result = call_qwen_json(
        prompt=user_prompt,
        system_prompt=system_prompt,
        log_path=log_path,
        step_name="outreach_talking_points",
    )

    # Extract talking points from JSON response
    parsed = result.get("parsed_json")
    if parsed and isinstance(parsed.get("talking_points"), list):
        raw_points = parsed["talking_points"]
    else:
        # Fallback: try to extract from content text (P9 fix: strip JSON wrapper)
        content = result.get("content", "")
        # Try to find JSON array in content
        import json as _json
        try:
            # Attempt to parse the whole content as JSON
            maybe_json = _json.loads(content)
            if isinstance(maybe_json, dict) and "talking_points" in maybe_json:
                raw_points = maybe_json["talking_points"]
            elif isinstance(maybe_json, list):
                raw_points = maybe_json
            else:
                raise ValueError("not a list")
        except (_json.JSONDecodeError, ValueError):
            # Strip common JSON wrapper artifacts before line-splitting
            cleaned = content.strip()
            cleaned = re.sub(r'^\s*\{?\s*"talking_points"\s*:\s*\[?\s*', '', cleaned)
            cleaned = re.sub(r'\s*\]?\s*\}?\s*$', '', cleaned)
            raw_points = [
                line.strip().strip('- "').strip().rstrip('",')
                for line in cleaned.split("\n")
                if line.strip() and not line.strip().startswith('{') and not line.strip().startswith('}')
            ]
        if not raw_points:
            raise RuntimeError("Qwen returned empty talking points")

    # Validate: check all numbers trace to fact cards
    validated_points, issues = _validate_talking_points(raw_points, fact_cards)

    # P2/P6 fix: flag untraceable qualitative claims
    qualitative_issues = _check_qualitative_grounding(validated_points, fact_cards, target)
    issues.extend(qualitative_issues)

    return validated_points, issues


def _check_qualitative_grounding(
    talking_points: list[str],
    fact_cards: list[FactCard],
    target: ResolvedTarget,
) -> list[str]:
    """P2/P6 fix: detect untraceable qualitative astronomical claims."""
    issues: list[str] = []
    # Patterns that indicate claims requiring fact-card backing
    ungrounded_patterns = [
        (r"恒星诞生|恒星形成|恒星摇篮|star.?forming", "恒星诞生区/恒星形成区"),
        (r"最近的|最近的大型|nearest", "距离/最近声明"),
        (r"最亮的|最暗的|最大的|最小的", "极值声明"),
        (r"数十亿|数万亿|百万", "数量级声明"),
    ]
    # Build a text blob of all fact card values for checking
    fact_text = " ".join(c.value for c in fact_cards).lower()

    for point in talking_points:
        for pattern, claim_type in ungrounded_patterns:
            if re.search(pattern, point, re.IGNORECASE):
                # Check if the claim has any basis in fact cards
                # (most won't, since fact cards are numerical)
                issues.append(
                    f"[溯源待核实] 讲解要点含未经事实卡验证的定性声明"
                    f"（{claim_type}）: \"{point[:60]}...\""
                )
                break  # one issue per point is enough

    return issues


def _validate_talking_points(
    talking_points: list[str],
    fact_cards: list[FactCard],
) -> tuple[list[str], list[str]]:
    """
    Validate that all numerical values in talking points are traceable
    to fact cards. This is the hallucination protection layer.
    """
    allowed_numbers: set[str] = set()
    number_pattern = re.compile(r"\d+\.?\d*")

    for card in fact_cards:
        nums = number_pattern.findall(card.value)
        for n in nums:
            allowed_numbers.add(n)
            try:
                allowed_numbers.add(str(int(float(n))))
            except (ValueError, OverflowError):
                pass

    safe_numbers = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "0"}
    allowed_numbers.update(safe_numbers)

    validated: list[str] = []
    issues: list[str] = []

    for point in talking_points:
        found_nums = number_pattern.findall(point)
        untraceable = []
        for num in found_nums:
            normalized = num
            try:
                f = float(num)
                normalized = str(int(f)) if f == int(f) else str(f)
            except (ValueError, OverflowError):
                pass
            if normalized not in allowed_numbers and num not in allowed_numbers:
                untraceable.append(num)

        if untraceable:
            issues.append(
                f"[幻觉防护] 移除含不可溯源数值的讲解要点: "
                f"\"{point[:50]}...\" (数值: {', '.join(untraceable)})"
            )
        else:
            validated.append(point)

    return validated, issues


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
    qwen_used: bool = False,
) -> None:
    """Write the outreach pack as a markdown file."""
    lines: list[str] = []
    lines.append(f"# {target.standard_name} 观测活动包")
    lines.append("")
    lines.append(f"**受众**: {audience}  ")
    lines.append(f"**日期**: {obs.date_range[0]}  ")
    lines.append(f"**地点**: {obs.location_name}  ")
    lines.append(f"**可观测**: {'是' if obs.is_observable else '否'}  ")
    lines.append(f"**讲解生成**: {'Qwen 模型（经事实卡验证）' if qwen_used else '模板'}")
    lines.append("")

    if obs.recommended_window:
        w = obs.recommended_window.window
        lines.append("## 推荐观测时段")
        lines.append("")
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
