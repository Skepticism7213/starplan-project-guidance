"""
StarPlan Loop - Skill 3: outreach_pack (P1: Claim-first rendering)

Generates outreach activity packs exclusively from the Claim Registry.
Every user-visible sentence is produced by Claim + sentence_variant_id
via the unified section renderer. No free text concatenation.

Two modes for talking points:
  - Qwen mode: Qwen selects/orders Claims (ExpressionPlan), program renders.
  - Template mode (fallback): deterministic priority-order rendering.

Core invariant: Never fill in numerical values that are not in the
Claim Registry. Mark unconfirmed items instead.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

from .claims import AllowedClaimsBuilder
from .expression_validator import validate_expression_plan
from .rendering import (
    FullSectionRenderResult,
    RenderedDocument,
    RenderResult,
    render_all_sections,
    render_deterministic_fallback,
    render_document,
    render_from_expression_plan,
    serialize_document_md,
)
from .schemas import (
    ActivityScheduleItem,
    EquipmentItem,
    ExpressionPlan,
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
    use_qwen: bool = True,
    log_path: Optional[str] = None,
    timing_sink: Optional[dict[str, float]] = None,
    timezone_name: str = "Asia/Shanghai",
) -> OutreachPack:
    """
    Generate an outreach activity pack based on verified Claims.

    All user-visible text is rendered from the Claim Registry via the
    unified section renderer. Qwen's role is limited to selecting and
    ordering Claims (ExpressionPlan); it never produces final text.
    """
    claim_started = time.perf_counter()
    # Build Claim Registry FIRST
    claims_builder = AllowedClaimsBuilder(
        target=target,
        obs_result=obs_result,
        location_id=obs_result.location_name,
        audience=audience,
        equipment=equipment,
        timezone_name=timezone_name,
    )
    claims_builder.build()
    if run_dir:
        claims_builder.save(run_dir)
    if timing_sink is not None:
        timing_sink["outreach_pack_claim_build"] = (time.perf_counter() - claim_started) * 1000

    # Not-observable branch
    if not obs_result.is_observable:
        return _generate_not_observable_pack(
            target=target,
            obs_result=obs_result,
            audience=audience,
            equipment=equipment,
            goal=goal,
            run_dir=run_dir,
            claims_builder=claims_builder,
            timing_sink=timing_sink,
        )

    # ── Talking points: ExpressionPlan protocol ──
    qwen_used = False
    qwen_validation_issues: list[str] = []
    talking_points_result: RenderResult | None = None

    model_started = time.perf_counter()
    if use_qwen and _qwen_available():
        try:
            plan, plan_issues = _generate_expression_plan_qwen(
                target, obs_result, audience, claims_builder, log_path,
            )
            if plan is not None:
                vresult = validate_expression_plan(
                    plan, claims_builder,
                    expected_scope_target=target.standard_name,
                    expected_scope_date=str(obs_result.date_range[0]) if obs_result.date_range else None,
                    claims_path=(run_dir / "claims.json") if run_dir else None,
                )
                if vresult.passed:
                    talking_points_result = render_from_expression_plan(
                        plan, claims_builder, audience,
                    )
                    qwen_used = True
                    qwen_validation_issues = [w.message for w in vresult.warnings]
                else:
                    talking_points_result = render_deterministic_fallback(
                        claims_builder, audience,
                        reason=f"ExpressionPlan validation failed: {vresult.summary}",
                    )
                    qwen_validation_issues = [
                        f"[fail-closed] {e.message}" for e in vresult.errors
                    ]
            else:
                talking_points_result = render_deterministic_fallback(
                    claims_builder, audience,
                    reason="Qwen returned invalid ExpressionPlan",
                )
                qwen_validation_issues = plan_issues
        except Exception as e:
            talking_points_result = render_deterministic_fallback(
                claims_builder, audience,
                reason=f"Qwen 调用异常: {e}",
            )
            qwen_validation_issues = [f"[fail-closed] Qwen 调用失败，回退到确定性渲染: {e}"]
    else:
        talking_points_result = render_deterministic_fallback(
            claims_builder, audience,
            reason="template_mode (Qwen not available or disabled)",
        )
    if timing_sink is not None:
        timing_sink["outreach_pack_model_call"] = (
            (time.perf_counter() - model_started) * 1000
            if use_qwen and _qwen_available() else 0.0
        )

    # ── Render ALL sections from Claims ──
    render_started = time.perf_counter()
    sections = render_all_sections(
        claims_builder, audience, equipment, talking_points_result,
    )

    # Phase A: assemble RenderedDocument (single source for Markdown + trace)
    rendered_doc = render_document(
        claims_builder, sections, audience, equipment, qwen_used=qwen_used,
    )

    # Convert to OutreachPack schema
    talking_points = [s.text for s in sections.talking_points]
    schedule = [
        ActivityScheduleItem(
            time_label=si.time_label,
            activity=si.activity,
            notes=si.notes,
        )
        for si in sections.schedule
    ]
    equipment_checklist = [
        EquipmentItem(item=ei.item, quantity=ei.quantity, notes=ei.notes)
        for ei in sections.equipment
    ]
    safety_notes = [s.text for s in sections.safety]
    manual_check_items = [s.text for s in sections.manual_checks]
    unconfirmed_items = [s.text for s in sections.unconfirmed]
    # Phase A (C-01): qwen_validation_issues NO LONGER appended directly to
    # unconfirmed_items. They are recorded in the OutreachPack schema field
    # for audit but do not enter the Claim-traced document.

    # Generate outputs from RenderedDocument
    md_path = None
    if run_dir:
        md_path = str(run_dir / "outreach_pack.md")
        md_content = serialize_document_md(rendered_doc, is_observable=True)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        # Write render_trace.json from RenderedDocument (Phase A: final text hash)
        _write_render_trace_from_document(rendered_doc, run_dir)
        # Save RenderedDocument for runner.py delivery contract validation
        with open(run_dir / "rendered_document.json", "w", encoding="utf-8") as f:
            json.dump(rendered_doc.to_dict(), f, ensure_ascii=False, indent=2)
        # Backward-compat: sentence_claim_map.json
        sc_map = {b.final_text: b.claim_ids for b in rendered_doc.all_blocks}
        with open(run_dir / "sentence_claim_map.json", "w", encoding="utf-8") as f:
            json.dump(sc_map, f, ensure_ascii=False, indent=2)
        # expression_plan.json
        expr_plan = {
            "schema_version": "1.0",
            "mode": "qwen_expression_plan" if qwen_used else "deterministic_fallback",
            "selected_claims": [
                {"claim_id": s.claim_ids[0], "sentence_variant_id": s.variant_id}
                for s in sections.talking_points if s.claim_ids
            ],
            "section_order": ["target", "observability", "risk", "actions"],
            "tone": "beginner_friendly" if "新成员" in audience else "general",
            "connector_ids": [],
        }
        with open(run_dir / "expression_plan.json", "w", encoding="utf-8") as f:
            json.dump(expr_plan, f, ensure_ascii=False, indent=2)
    if timing_sink is not None:
        timing_sink["outreach_pack_render"] = (time.perf_counter() - render_started) * 1000

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
    claims_builder: Optional[AllowedClaimsBuilder] = None,
    timing_sink: Optional[dict[str, float]] = None,
) -> OutreachPack:
    """Generate a cancellation/alternative pack when target is NOT observable.

    All text comes from render_all_sections (blocking path).
    """
    if claims_builder is None:
        # Should not happen in normal flow, but defensive
        return OutreachPack(
            target_name=target.standard_name,
            audience=audience,
            pack_type="not_observable",
            activity_schedule=[],
            talking_points=["目标不可观测，活动取消"],
            equipment_checklist=[],
            safety_notes=[],
            manual_check_items=[],
            unconfirmed_items=[],
            alternative_suggestions=[],
            outreach_pack_md_path=None,
            qwen_used=False,
            qwen_validation_issues=[],
        )

    # Render all sections (not-observable path)
    render_started = time.perf_counter()
    sections = render_all_sections(claims_builder, audience, equipment)

    # Phase A: assemble RenderedDocument
    rendered_doc = render_document(
        claims_builder, sections, audience, equipment, qwen_used=False,
    )

    # Compose talking points from blocking + alternatives
    talking_points = (
        [s.text for s in sections.blocking]
        + [s.text for s in sections.alternatives]
    )
    schedule = [
        ActivityScheduleItem(
            time_label=si.time_label or "活动调整",
            activity=si.activity,
            notes=si.notes,
        )
        for si in sections.schedule
    ]
    manual_check_items = [s.text for s in sections.manual_checks]
    alt_suggestions = [s.text for s in sections.alternatives]

    # Generate outputs from RenderedDocument
    md_path = None
    if run_dir:
        md_path = str(run_dir / "outreach_pack.md")
        md_content = serialize_document_md(rendered_doc, is_observable=False)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        _write_render_trace_from_document(rendered_doc, run_dir)
        # Save RenderedDocument for runner.py delivery contract validation
        with open(run_dir / "rendered_document.json", "w", encoding="utf-8") as f:
            json.dump(rendered_doc.to_dict(), f, ensure_ascii=False, indent=2)
        # Backward-compat files
        sc_map = {b.final_text: b.claim_ids for b in rendered_doc.all_blocks}
        with open(run_dir / "sentence_claim_map.json", "w", encoding="utf-8") as f:
            json.dump(sc_map, f, ensure_ascii=False, indent=2)
        expression_plan = {
            "schema_version": "1.0",
            "mode": "deterministic_not_observable",
            "selected_claims": [
                {"claim_id": s.claim_ids[0], "sentence_variant_id": s.variant_id}
                for s in (sections.blocking + sections.alternatives) if s.claim_ids
            ],
            "section_order": ["target", "observability", "actions"],
            "tone": "general",
            "connector_ids": [],
        }
        with open(run_dir / "expression_plan.json", "w", encoding="utf-8") as f:
            json.dump(expression_plan, f, ensure_ascii=False, indent=2)
    if timing_sink is not None:
        timing_sink["outreach_pack_model_call"] = 0.0
        timing_sink["outreach_pack_render"] = (time.perf_counter() - render_started) * 1000

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


# ── Render trace (Phase A: from RenderedDocument) ──


def _write_render_trace_from_document(doc: RenderedDocument, run_dir: Path) -> None:
    """Write render_trace.json from the final RenderedDocument.

    Phase A (C-01 fix): trace is generated from the SAME RenderedDocument
    that produces the Markdown. text_hash corresponds to the exact atomic
    text the user sees. Section order is deterministic (closes W-03).

    Schema per entry:
      sentence_id, text_hash, text, claim_ids, variant_id, section, render_mode
    """
    trace_entries = []
    for i, block in enumerate(doc.all_blocks):
        trace_entries.append({
            "sentence_id": f"s{i:03d}",
            "text_hash": block.text_hash,
            "text": block.final_text,
            "claim_ids": block.claim_ids,
            "variant_id": block.variant_id,
            "section": block.section,
            "render_mode": block.render_mode,
        })

    trace_doc = {
        "schema_version": "2.0",
        "sentence_count": len(trace_entries),
        "sections": doc.sections_ordered,
        "sentences": trace_entries,
    }
    with open(run_dir / "render_trace.json", "w", encoding="utf-8") as f:
        json.dump(trace_doc, f, ensure_ascii=False, indent=2)


# ── Qwen ExpressionPlan (unchanged) ─────────────────


def _qwen_available() -> bool:
    """Check if DASHSCOPE_API_KEY is configured and usable."""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    return bool(api_key) and api_key != "your_api_key_here"


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


# Phase A: _write_outreach_markdown and _write_not_observable_markdown DELETED.
# Markdown is now generated exclusively by rendering.serialize_document_md()
# from a RenderedDocument. No direct fact interpolation from target/obs.


# ── Legacy utility (defense-in-depth, tested independently) ──


def _validate_talking_points(
    talking_points: list[str],
    fact_cards: list[FactCard],
) -> tuple[list[str], list[str]]:
    """
    Validate that all numerical values in talking points are traceable
    to fact cards. Defense-in-depth layer (not called in Claim-first flow).

    Returns:
        (validated_points, issues) tuple.
    """
    allowed_numbers: set[str] = set()
    number_pattern = re.compile(r"\d+\.?\d*")

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
        nums = number_pattern.findall(card.value)
        for n in nums:
            allowed_numbers.add(n)
            try:
                allowed_numbers.add(str(int(float(n))))
            except (ValueError, OverflowError):
                pass

    safe_numbers = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "0"}
    allowed_numbers.update(safe_numbers)

    distance_pattern = re.compile(r"[\d.]+\s*(万)?光年")
    nature_claims = {
        "恒星诞生区": ["deep_sky"], "恒星形成区": ["deep_sky"],
        "行星状星云": ["deep_sky"], "超新星遗迹": ["deep_sky"],
        "球状星团": ["deep_sky"], "疏散星团": ["deep_sky"],
        "旋涡星系": ["deep_sky"], "椭圆星系": ["deep_sky"],
        "双星系统": ["star"], "红巨星": ["star"],
        "白矮星": ["star"], "中子星": ["star"],
    }

    validated: list[str] = []
    issues: list[str] = []

    for point in talking_points:
        point_issues = []

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
            point_issues.append(f"不可溯源数值: {', '.join(untraceable)}")

        if distance_pattern.search(point):
            point_issues.append("含距离描述(光年)，事实卡无此数据")

        for claim_text, valid_types in nature_claims.items():
            if claim_text in point and target_type and target_type not in valid_types:
                point_issues.append(
                    f"文本事实'{claim_text}'与目标类型'{target_type}'不符"
                )

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
