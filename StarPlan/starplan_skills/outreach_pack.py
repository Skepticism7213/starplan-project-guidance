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
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from .claims import AllowedClaimsBuilder
from .expression_validator import validate_expression_plan
from .rendering import (
    render_deterministic_fallback,
    render_from_expression_plan,
    render_not_observable_fallback,
)
from .schemas import (
    ActivityScheduleItem,
    EquipmentItem,
    ExpressionPlan,
    FactCard,
    ObservabilityResult,
    OutreachPack,
    ResolvedTarget,
    SelectedClaim,
)


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

    Args:
        target: Resolved target information.
        obs_result: Observability computation results.
        audience: Target audience description.
        equipment: Available equipment.
        goal: Activity goal.
        run_dir: Output directory for the markdown file.
        use_qwen: If True and DASHSCOPE_API_KEY is set, use Qwen to
                 generate richer talking points. Falls back to template.
        log_path: Path for model call logging.

    Returns:
        OutreachPack with schedule, talking points, checklist, etc.
    """
    # C-3 fix: If target is NOT observable, generate a cancellation/alternative
    # pack instead of an observation activity pack.
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

    # Phase B: Build Claim Registry (runs alongside FactCards during transition)
    claims_builder = AllowedClaimsBuilder(
        target=target,
        obs_result=obs_result,
        location_id=obs_result.location_name,
        audience=audience,
        equipment=equipment,
    )
    claims_builder.build()
    if run_dir:
        claims_builder.save(run_dir)

    # Generate activity schedule based on recommended window
    schedule = _build_schedule(obs_result, audience)

    # Generate talking points: Phase C ExpressionPlan protocol
    # Qwen selects claims → validator checks → program renders deterministically
    qwen_used = False
    qwen_validation_issues: list[str] = []
    sentence_claim_map: dict = {}

    if use_qwen and _qwen_available():
        try:
            plan, plan_issues = _generate_expression_plan_qwen(
                target, obs_result, audience, claims_builder, log_path,
            )
            if plan is not None:
                # Validate the ExpressionPlan (8-step)
                vresult = validate_expression_plan(
                    plan, claims_builder,
                    expected_scope_target=target.standard_name,
                    expected_scope_date=str(obs_result.date_range[0]) if obs_result.date_range else None,
                )
                if vresult.passed:
                    # Render deterministically from claims
                    render_result = render_from_expression_plan(plan, claims_builder, audience)
                    talking_points = render_result.talking_points
                    sentence_claim_map = render_result.sentence_claim_map
                    qwen_used = True
                    qwen_validation_issues = [w.message for w in vresult.warnings]
                else:
                    # Validation failed → fail-closed fallback
                    render_result = render_deterministic_fallback(
                        claims_builder, audience,
                        reason=f"ExpressionPlan validation failed: {vresult.summary}",
                    )
                    talking_points = render_result.talking_points
                    sentence_claim_map = render_result.sentence_claim_map
                    qwen_validation_issues = [
                        f"[fail-closed] {e.message}" for e in vresult.errors
                    ]
            else:
                # Qwen returned invalid data → fail-closed
                render_result = render_deterministic_fallback(
                    claims_builder, audience,
                    reason="Qwen returned invalid ExpressionPlan",
                )
                talking_points = render_result.talking_points
                sentence_claim_map = render_result.sentence_claim_map
                qwen_validation_issues = plan_issues
        except Exception as e:
            # Qwen call failed → fail-closed fallback
            render_result = render_deterministic_fallback(
                claims_builder, audience,
                reason=f"Qwen 调用异常: {e}",
            )
            talking_points = render_result.talking_points
            sentence_claim_map = render_result.sentence_claim_map
            qwen_validation_issues = [f"[fail-closed] Qwen 调用失败，回退到确定性渲染: {e}"]
    else:
        # No Qwen → deterministic fallback
        render_result = render_deterministic_fallback(
            claims_builder, audience,
            reason="template_mode (Qwen not available or disabled)",
        )
        talking_points = render_result.talking_points
        sentence_claim_map = render_result.sentence_claim_map

    # Equipment checklist
    equipment_checklist = _build_equipment_checklist(equipment, target, obs_result)

    # Safety notes (temperature hint based on actual observation month)
    obs_month = None
    if obs_result.date_range:
        try:
            obs_month = int(str(obs_result.date_range[0]).split("-")[1])
        except (IndexError, ValueError):
            pass

    if obs_month in (11, 12, 1, 2):
        temp_note = "注意保暖，冬季夜间气温可能降至 0°C 以下"
    elif obs_month in (3, 4, 10):
        temp_note = "注意保暖，春/秋夜间气温可能降至 10°C 以下"
    elif obs_month in (5, 9):
        temp_note = "夜间气温适宜，但仍建议携带薄外套"
    else:
        temp_note = "夏季夜间注意防蚊，适当补充水分"

    safety_notes = [
        "夜间活动请注意人身安全，避免单独行动",
        "使用红色手电筒保护暗适应视力",
        temp_note,
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
    """
    C-3 fix: Generate a cancellation/reschedule/alternative pack when the
    target is NOT observable on the requested date.

    This pack explains why the target cannot be observed, provides educational
    context about the target, and suggests alternatives — instead of generating
    an observation activity pack that contradicts the observability result.
    """
    # Build talking points explaining the situation
    talking_points = _build_not_observable_talking_points(target, obs_result, audience)

    # Build alternative suggestions list
    alt_suggestions = [s.description for s in obs_result.alternative_suggestions]

    # Build a "what to do instead" schedule
    schedule = _build_not_observable_schedule(obs_result, alt_suggestions)

    # Manual check items for rescheduling
    manual_check_items = [
        f"确认 {target.standard_name} 在改期日期是否可观测（重新运行 StarPlan）",
        "确认替代目标的设备匹配度",
        "通知参与成员活动调整安排",
    ]

    # Generate markdown
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


def _build_not_observable_talking_points(
    target: ResolvedTarget,
    obs: ObservabilityResult,
    audience: str,
) -> list[str]:
    """Build talking points for a not-observable target (educational, not observational)."""
    points: list[str] = []

    # Explain why not observable
    points.append(
        f"{target.standard_name} 在 {obs.date_range[0]} 当晚不满足观测条件"
        f"（最高高度角过低），本次观测活动取消或改期"
    )

    # Educational content about the target (still useful for the audience)
    if target.target_type == "deep_sky":
        if target.constellation:
            points.append(f"{target.standard_name} 位于 {target.constellation} 星座方向")
        if target.visual_magnitude is not None:
            points.append(f"它的视星等约为 {target.visual_magnitude:.1f}，属于深空天体")
        points.append("该目标在当前季节处于太阳方向附近/地平线以下，无法在夜间观测")
    elif target.target_type == "star":
        if target.constellation:
            points.append(f"{target.standard_name} 是 {target.constellation} 座的恒星")
        points.append("该恒星在当前季节的夜间不可见")

    # Alternative suggestions
    if obs.alternative_suggestions:
        alt_names = [
            s.target_name for s in obs.alternative_suggestions
            if s.target_name and s.target_name != target.standard_name
        ]
        if alt_names:
            points.append(f"当季更适合观测的替代目标：{'、'.join(alt_names)}")
        points.append("建议将活动改期到目标进入最佳观测季节时再举行")

    # Audience-specific note
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
        activity=f"原定观测活动取消/改期",
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
    """Write a not-observable pack as markdown (cancellation/alternative notice)."""
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
    lines.append(f"- {target.standard_name} 在 {obs.date_range[0]} 当晚最高高度角过低，不满足最低观测条件")
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


# ── Qwen-enhanced talking points (Week 3) ────────────

def _qwen_available() -> bool:
    """Check if DASHSCOPE_API_KEY is configured and usable."""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    return bool(api_key) and api_key != "your_api_key_here"


def _generate_talking_points_qwen(
    target: ResolvedTarget,
    obs_result: ObservabilityResult,
    audience: str,
    fact_cards: list[FactCard],
    log_path: Optional[str] = None,
) -> tuple[list[str], list[str]]:
    """
    Use Qwen to generate richer talking points grounded in fact cards.

    Returns:
        (talking_points, validation_issues) tuple.
        If validation finds untraceable numbers, those points are removed
        and issues are reported.
    """
    from .qwen_client import call_qwen_json, DEFAULT_MODEL

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

    system_prompt = (
        "你是一位天文科普讲解员，负责为校园天文观测活动撰写讲解要点。\n"
        "严格规则：\n"
        "1. 你只能使用【事实卡】中提供的数值，绝对不能编造任何数字。\n"
        "2. 如果事实卡没有提供某项数据，不要提及具体数值，可以用定性描述。\n"
        "3. 讲解要生动有趣，适合目标受众，但科学准确性是第一位的。\n"
        "4. 每条讲解要点一句话，控制在 6-10 条。\n"
        "5. 返回 JSON 格式: {\"talking_points\": [\"要点1\", \"要点2\", ...]}"
    )

    user_prompt = (
        f"【事实卡】\n{fact_context}\n"
        f"{window_info}\n\n"
        f"【目标信息】\n"
        f"- 标准名称: {target.standard_name}\n"
        f"- 类型: {target.target_type}\n"
        f"- 星座: {target.constellation or '未知'}\n\n"
        f"【受众】{audience}\n\n"
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
        # Fallback: try to extract from content text
        content = result.get("content", "")
        raw_points = [line.strip("- ").strip() for line in content.split("\n") if line.strip()]
        if not raw_points:
            raise RuntimeError("Qwen returned empty talking points")

    # Validate: check all numbers trace to fact cards
    validated_points, issues = _validate_talking_points(raw_points, fact_cards)

    return validated_points, issues


def _validate_talking_points(
    talking_points: list[str],
    fact_cards: list[FactCard],
) -> tuple[list[str], list[str]]:
    """
    Validate that all numerical values AND text facts in talking points
    are traceable to fact cards. This is the hallucination protection layer.

    Strategy:
      - Extract all numbers (int/float) from each talking point via regex.
      - Build a set of "allowed numbers" from fact card values.
      - If a talking point contains a number NOT in the allowed set,
        flag it and remove the point.
      - Additionally check text fact claims (distance, physical nature,
        visibility) against fact card data.

    Returns:
        (validated_points, issues) tuple.
    """
    # Build allowed number set from fact cards
    allowed_numbers: set[str] = set()
    number_pattern = re.compile(r"\d+\.?\d*")

    # Extract fact card info for text validation
    fact_keys = {card.key: card.value for card in fact_cards}
    target_type = fact_keys.get("target_type", "")
    magnitude_str = fact_keys.get("visual_magnitude", "")
    target_mag = None
    if magnitude_str:
        try:
            target_mag = float(magnitude_str)
        except ValueError:
            pass

    for card in fact_cards:
        # Extract all numbers from the fact card value
        nums = number_pattern.findall(card.value)
        for n in nums:
            allowed_numbers.add(n)
            # Also add integer version (e.g., "3" from "3.0")
            try:
                allowed_numbers.add(str(int(float(n))))
            except (ValueError, OverflowError):
                pass

    # Common safe numbers that don't need fact card backing
    # (e.g., "一" in Chinese doesn't produce digits, but "1" in "10°C" is from template)
    safe_numbers = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "0"}
    allowed_numbers.update(safe_numbers)

    # Text fact patterns that require validation
    # Distance claims (e.g., "254万光年", "1500光年") — not in fact cards, always suspect
    distance_pattern = re.compile(r"[\d.]+\s*(万)?光年")
    # Physical nature claims that must match target_type
    nature_claims = {
        "恒星诞生区": ["deep_sky"],
        "恒星形成区": ["deep_sky"],
        "行星状星云": ["deep_sky"],
        "超新星遗迹": ["deep_sky"],
        "球状星团": ["deep_sky"],
        "疏散星团": ["deep_sky"],
        "旋涡星系": ["deep_sky"],
        "椭圆星系": ["deep_sky"],
        "双星系统": ["star"],
        "红巨星": ["star"],
        "白矮星": ["star"],
        "中子星": ["star"],
    }

    validated: list[str] = []
    issues: list[str] = []

    for point in talking_points:
        point_issues = []

        # ── Number validation (original logic) ──
        found_nums = number_pattern.findall(point)
        untraceable = []
        for num in found_nums:
            # Normalize: remove trailing zeros after decimal
            normalized = num
            try:
                f = float(num)
                normalized = str(int(f)) if f == int(f) else str(f)
            except (ValueError, OverflowError):
                pass

            if normalized not in allowed_numbers and num not in allowed_numbers:
                untraceable.append(num)

        if untraceable:
            point_issues.append(f"不可溯源数值: {', '.join(untraceable)}")

        # ── Text fact validation (new) ──
        # Check distance claims (not backed by any fact card)
        if distance_pattern.search(point):
            point_issues.append("含距离描述(光年)，事实卡无此数据")

        # Check physical nature claims against target_type
        for claim, valid_types in nature_claims.items():
            if claim in point and target_type and target_type not in valid_types:
                point_issues.append(
                    f"文本事实'{claim}'与目标类型'{target_type}'不符"
                )

        # Check "肉眼可见" claim against magnitude
        if "肉眼可见" in point and target_mag is not None and target_mag > 6.0:
            point_issues.append(
                f"声称'肉眼可见'但视星等={target_mag}，通常肉眼极限为6等"
            )

        if point_issues:
            issues.append(
                f"[幻觉防护] 移除讲解要点: \"{point[:50]}...\" "
                f"({'；'.join(point_issues)})"
            )
        else:
            validated.append(point)

    return validated, issues


# ── Phase C: ExpressionPlan protocol ─────────────────

def _generate_expression_plan_qwen(
    target: ResolvedTarget,
    obs_result: ObservabilityResult,
    audience: str,
    claims_builder: AllowedClaimsBuilder,
    log_path: Optional[str] = None,
) -> tuple[Optional[ExpressionPlan], list[str]]:
    """
    Ask Qwen to produce an ExpressionPlan: select and order claims.

    Qwen does NOT generate any factual text. It only chooses which claims
    to present, which sentence variant to use, and the ordering/tone.
    The program then renders deterministically from the Claim Registry.

    Returns:
        (ExpressionPlan or None, issues) tuple.
        None means Qwen failed to produce a valid plan.
    """
    from .qwen_client import call_qwen_json

    # Build the claim catalog for Qwen to choose from
    claim_catalog_lines: list[str] = []
    for claim in claims_builder.allowed_claims:
        variants_str = ", ".join(claim.allowed_variant_ids)
        claim_catalog_lines.append(
            f"  - claim_id: \"{claim.claim_id}\" | "
            f"type: {claim.claim_type.value} | "
            f"display: \"{claim.display_value}\" | "
            f"variants: [{variants_str}]"
        )
    claim_catalog = "\n".join(claim_catalog_lines)

    system_prompt = (
        "你是 StarPlan 的表达编排器。你的唯一任务是从【Claim 目录】中选择要展示的条目，"
        "并为每条选择一个句式变体（variant_id）。\n\n"
        "严格规则：\n"
        "1. 你只能选择目录中存在的 claim_id，绝对不能编造新的 claim_id。\n"
        "2. 你只能选择该 claim 列出的 variant_id，绝对不能编造新的 variant_id。\n"
        "3. 你不能输出任何事实性文字、数值或描述。你只输出选择结果。\n"
        "4. 选择 5-10 条 claim，按讲解逻辑排序。\n"
        "5. 返回严格 JSON 格式（见下方 schema）。\n\n"
        "返回 JSON schema:\n"
        "{\n"
        '  "schema_version": "1.0",\n'
        '  "selected_claims": [\n'
        '    {"claim_id": "...", "sentence_variant_id": "..."}\n'
        "  ],\n"
        '  "section_order": ["target", "observability", "risk", "actions"],\n'
        '  "tone": "beginner_friendly",\n'
        '  "connector_ids": []\n'
        "}\n"
    )

    user_prompt = (
        f"【Claim 目录】（共 {len(claims_builder.allowed_claims)} 条）\n"
        f"{claim_catalog}\n\n"
        f"【受众】{audience}\n"
        f"【目标】{target.standard_name}\n"
        f"【可观测】{'是' if obs_result.is_observable else '否'}\n\n"
        "请从上述目录中选择适合该受众的 claim，组成讲解要点。"
        "记住：只输出 JSON 选择结果，不要输出任何事实文字！"
    )

    result = call_qwen_json(
        prompt=user_prompt,
        system_prompt=system_prompt,
        log_path=log_path,
        step_name="expression_plan",
    )

    # Parse the ExpressionPlan from Qwen's response
    parsed = result.get("parsed_json")
    if not parsed:
        return None, [f"[fail-closed] Qwen 未返回有效 JSON: {result.get('json_error', 'unknown')}"]

    try:
        plan = ExpressionPlan(**parsed)
        return plan, []
    except Exception as e:
        return None, [f"[fail-closed] ExpressionPlan 解析失败: {e}"]


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
    lines.append(f"")
    lines.append(f"**受众**: {audience}  ")
    lines.append(f"**日期**: {obs.date_range[0]}  ")
    lines.append(f"**地点**: {obs.location_name}  ")
    lines.append(f"**可观测**: {'是' if obs.is_observable else '否'}  ")
    lines.append(f"**讲解生成**: {'Qwen 模型（经事实卡验证）' if qwen_used else '模板'}")
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
