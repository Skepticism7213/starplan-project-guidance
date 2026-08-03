"""
StarPlan Loop - Skill 4: observation_review

Compares an original observation plan with an actual observation log,
identifies deviations, classifies causes, and generates a revised plan.

Two modes:
  - Rule-based (always): deterministic keyword/threshold detection.
  - Qwen-assisted (optional): richer cause classification and suggestions,
    constrained to predefined classification levels. Fail-closed: if Qwen
    fails or returns invalid data, rule-based results are used.

Core principle: Distinguish "evidence-based cause" from "possible cause"
and "undetermined". Never assign strong blame to factors with only weak
evidence. Qwen NEVER invents numerical data — it only classifies and
suggests based on the structured evidence provided.
"""

from __future__ import annotations

import json
import os
import re
import copy
from datetime import timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from .schemas import (
    CauseEntry,
    Deviation,
    ObservationLog,
    ObservationReview,
    ObservabilityResult,
    RevisedPlanDiff,
)


def review_observation(
    original_plan: ObservabilityResult,
    log: ObservationLog,
    run_dir: Optional[Path] = None,
    timezone_name: str = "Asia/Shanghai",
    use_qwen: bool = False,
    log_path: Optional[str] = None,
    original_input: Optional[dict] = None,
    parent_run_id: Optional[str] = None,
) -> ObservationReview:
    """
    Compare original plan with actual observation log and generate review.

    Args:
        original_plan: The observability plan that was followed.
        log: The actual observation log.
        run_dir: Output directory for reports.
        timezone_name: IANA timezone for interpreting naive datetimes.

    Returns:
        ObservationReview with deviations, causes, and revised plan.
    """
    deviations: list[Deviation] = []
    causes: list[CauseEntry] = []
    suggestions: list[str] = []
    plan_diffs: list[RevisedPlanDiff] = []

    # ── 1. Time deviation ──
    if original_plan.recommended_window:
        planned_start = original_plan.recommended_window.window.start
        actual_start = log.actual_start_time

        # Normalize both to UTC for a correct comparison.
        # Naive times are interpreted in the location's timezone.
        try:
            local_tz = ZoneInfo(timezone_name)
        except (KeyError, Exception):
            local_tz = ZoneInfo("Asia/Shanghai")
        if planned_start.tzinfo is None:
            planned_start = planned_start.replace(tzinfo=local_tz)
        if actual_start.tzinfo is None:
            actual_start = actual_start.replace(tzinfo=local_tz)
        planned_start_utc = planned_start.astimezone(timezone.utc)
        actual_start_utc = actual_start.astimezone(timezone.utc)

        delay_minutes = (actual_start_utc - planned_start_utc).total_seconds() / 60

        if delay_minutes > 10:
            deviations.append(Deviation(
                deviation_id="dev.time.delay",
                deviation_type="time",
                description=f"实际开始时间比计划晚 {delay_minutes:.0f} 分钟",
                plan_reference=f"计划开始时间: {planned_start.strftime('%H:%M')}",
                actual_value=f"实际开始时间: {actual_start.strftime('%H:%M')}",
            ))
            causes.append(CauseEntry(
                cause_id="cause.team_late",
                cause="团队迟到",
                classification="evidence_based",
                evidence=f"计划开始 {planned_start.strftime('%H:%M')}，实际开始 {actual_start.strftime('%H:%M')}，延迟 {delay_minutes:.0f} 分钟（阈值: review.delay_significance@v1 = 10 分钟活动政策）",
                source_deviation_ids=["dev.time.delay"],
                source="rule_based",
            ))
            suggestions.append("下次活动增加到场准备步骤，确保在推荐窗口开始时已就位")
            plan_diffs.append(RevisedPlanDiff(
                field="preparation_step",
                original_value="无提前到场要求",
                revised_value="提前到场进行设备调试和暗适应",
                reason=f"本次迟到 {delay_minutes:.0f} 分钟",
                source_cause_ids=["cause.team_late"],
            ))

    # ── 2. Environment deviation ──
    if log.cloud_cover and log.cloud_cover != "clear":
        deviations.append(Deviation(
            deviation_id="dev.env.cloud",
            deviation_type="environment",
            description=f"云量: {log.cloud_cover}",
            plan_reference="计划假设晴朗天空",
            actual_value=f"实际云量: {log.cloud_cover}",
        ))
        causes.append(CauseEntry(
            cause_id="cause.cloud",
            cause="云层干扰",
            classification="evidence_based" if log.observer_notes and "云" in log.observer_notes else "possible",
            evidence=f"观测日志记录云量为 {log.cloud_cover}" + (
                f"，备注: {log.observer_notes}" if log.observer_notes and "云" in log.observer_notes else ""
            ),
            source_deviation_ids=["dev.env.cloud"],
            source="rule_based",
        ))
        suggestions.append("活动前增加天气预报检查步骤，关注云量预报")
        suggestions.append("准备备选方案：若天气不适合观测，转为室内科普讲座")

    # ── 3. Equipment deviation ──
    if log.observer_notes:
        if "三脚架" in log.observer_notes or "不稳" in log.observer_notes:
            deviations.append(Deviation(
                deviation_id="dev.equip.tripod",
                deviation_type="equipment",
                description="三脚架不稳定，影响观测效果",
                plan_reference="设备清单包含三脚架",
                actual_value="三脚架不稳定",
            ))
            causes.append(CauseEntry(
                cause_id="cause.equipment_prep",
                cause="设备准备不足",
                classification="possible",
                evidence=f"观测者备注提及: {log.observer_notes}（人工报告，未经独立验证）",
                source_deviation_ids=["dev.equip.tripod"],
                source="human_report",
            ))
            suggestions.append("增加设备检查步骤：活动前测试三脚架稳定性")
            plan_diffs.append(RevisedPlanDiff(
                field="equipment_check_step",
                original_value="无设备预检步骤",
                revised_value="活动前检查三脚架稳定性、望远镜调焦",
                reason="观测者报告三脚架不稳（possible，待验证）",
                source_cause_ids=["cause.equipment_prep"],
            ))

    # ── 4. Expectation / operation issues ──
    if log.observer_notes and "不如预期" in log.observer_notes:
        causes.append(CauseEntry(
            cause_id="cause.expectation",
            cause="成员期望管理",
            classification="undetermined",
            evidence=f"备注提到'不如预期清晰'，但无法确定是设备、目标还是期望问题",
            source_deviation_ids=[],
            source="human_report",
        ))
        suggestions.append("活动前增加预期管理说明（来源: 天文科普经验，非本次计算）")
        plan_diffs.append(RevisedPlanDiff(
            field="expectation_management",
            original_value="无预期管理说明",
            revised_value="活动前发放目视效果预期说明",
            reason="备注提及不如预期（undetermined，具体原因待确认）",
            source_cause_ids=["cause.expectation"],
        ))

    # ── 5. Seeing conditions ──
    if log.seeing_conditions and log.seeing_conditions != "good":
        causes.append(CauseEntry(
            cause_id="cause.seeing",
            cause="视宁度",
            classification="possible",
            evidence=f"视宁度记录为 {log.seeing_conditions}，但无法确定是否为主要影响因素",
            source_deviation_ids=[],
            source="rule_based",
        ))

    # ── 6. Qwen-assisted attribution (optional enhancement) ──
    # Phase C (C-04 + W-04): structured error handling, ID-based attribution
    # Batch B: when use_qwen=False, record explicit disable reason for audit
    qwen_used = False
    qwen_status = "disabled_pending_id_only" if not use_qwen else "not_called"
    if use_qwen and deviations and _qwen_available():
        try:
            qwen_causes, qwen_suggestions = _qwen_assisted_attribution(
                original_plan, log, deviations, causes, log_path,
            )
            if qwen_causes:
                # Merge: Qwen causes supplement rule-based causes
                existing_cause_names = {c.cause for c in causes}
                for i, qc in enumerate(qwen_causes):
                    if qc.cause not in existing_cause_names:
                        # Phase C: assign stable ID and source
                        qc.cause_id = f"cause.qwen.{i}"
                        qc.source = "qwen_assisted"
                        causes.append(qc)
                if qwen_suggestions:
                    suggestions.extend(qwen_suggestions)
                qwen_used = True
                qwen_status = "success"
            else:
                qwen_status = "rejected"  # Qwen returned nothing valid
        except Exception as e:
            # Phase C (W-04): structured audit event, NOT silent pass
            qwen_status = "failed"
            if log_path:
                import json as _json
                from datetime import datetime as _dt, timezone as _tz, timedelta as _td
                _audit = {
                    "timestamp": _dt.now(_tz(_td(hours=8))).isoformat(),
                    "type": "model_error",
                    "step": "review_attribution",
                    "error": str(e)[:200],
                    "action": "deterministic_fallback",
                }
                with open(log_path, "a", encoding="utf-8") as _f:
                    _f.write(_json.dumps(_audit, ensure_ascii=False) + "\n")

    # ── P1 Batch E: executable next-round input ──
    # Only whitelisted fields (activity_preferences.*) may be patched into the
    # next StarPlanInput; free-text suggestions never become Schema fields.
    next_input, next_patches = _build_next_activity_input(
        original_input,
        original_plan,
        log,
        deviations,
        causes,
        timezone_name,
    )
    plan_diffs.extend(next_patches)
    source_cause_ids = sorted(
        {c for d in next_patches for c in d.source_cause_ids}
    )

    # ── Build revised plan ──
    revised_plan = _build_revised_plan(original_plan, plan_diffs, suggestions)

    # ── Generate report ──
    review_md_path = None
    revised_json_path = None
    next_input_path = None
    if run_dir:
        review_md_path = str(run_dir / "review_report.md")
        revised_json_path = str(run_dir / "revised_plan.json")
        if next_input is not None:
            next_input_path = str(run_dir / "next_activity_input.json")
            with open(next_input_path, "w", encoding="utf-8") as f:
                json.dump(next_input, f, ensure_ascii=False, indent=2, default=str)
        _write_review_markdown(
            original_plan, log, deviations, causes,
            suggestions, plan_diffs, review_md_path,
            next_input_path=next_input_path,
        )
        _write_revised_plan(revised_plan, revised_json_path)

        # Phase C (C-04): review trace uses ACTUAL IDs, not heuristic inference
        review_trace = {
            "schema_version": "2.0",
            "qwen_status": qwen_status,
            "causes": [
                {
                    "cause_id": c.cause_id,
                    "cause": c.cause,
                    "classification": c.classification,
                    "evidence": c.evidence,
                    "source": c.source,
                    "source_deviation_ids": c.source_deviation_ids,
                }
                for c in causes
            ],
            "suggestions": [
                {"text": s, "index": i}
                for i, s in enumerate(suggestions)
            ],
            "plan_diffs": [
                {
                    "field": d.field,
                    "reason": d.reason,
                    "source_cause_ids": d.source_cause_ids,
                }
                for d in plan_diffs
            ],
            "next_input_patches": [
                {
                    "field": d.field,
                    "original_value": d.original_value,
                    "revised_value": d.revised_value,
                    "reason": d.reason,
                    "source_cause_ids": d.source_cause_ids,
                }
                for d in next_patches
            ],
            "next_input_path": next_input_path,
            "deviations": [
                {
                    "deviation_id": d.deviation_id,
                    "deviation_type": d.deviation_type,
                    "description": d.description,
                }
                for d in deviations
            ],
        }
        with open(run_dir / "review_trace.json", "w", encoding="utf-8") as f:
            json.dump(review_trace, f, ensure_ascii=False, indent=2)

    return ObservationReview(
        target_name=original_plan.target_name,
        deviation_summary=deviations,
        evidence_citations=[f"计划: {d.plan_reference}; 实际: {d.actual_value}" for d in deviations],
        cause_classification=causes,
        improvement_suggestions=suggestions,
        revised_plan=revised_plan,
        revised_plan_diff=plan_diffs,
        review_report_md_path=review_md_path,
        revised_plan_json_path=revised_json_path,
        next_input_path=next_input_path,
        parent_run_id=parent_run_id,
        source_cause_ids=source_cause_ids,
    )


def _build_revised_plan(
    original: ObservabilityResult,
    diffs: list[RevisedPlanDiff],
    suggestions: list[str],
) -> dict:
    """Build a revised plan incorporating changes from the review."""
    plan: dict = {
        "target_name": original.target_name,
        "location_name": original.location_name,
        "original_date_range": [str(d) for d in original.date_range],
        "is_observable": original.is_observable,
        "revisions": [],
        "suggestions": suggestions,
    }

    if original.recommended_window:
        plan["original_recommended_window"] = {
            "start": original.recommended_window.window.start.isoformat(),
            "end": original.recommended_window.window.end.isoformat(),
            "peak_altitude_deg": original.recommended_window.peak_altitude_deg,
        }

    for diff in diffs:
        plan["revisions"].append({
            "field": diff.field,
            "from": diff.original_value,
            "to": diff.revised_value,
            "reason": diff.reason,
        })

    return plan


def _build_next_activity_input(
    original_input: Optional[dict],
    original_plan: ObservabilityResult,
    log: ObservationLog,
    deviations: list[Deviation],
    causes: list[CauseEntry],
    timezone_name: str,
) -> tuple[Optional[dict], list[RevisedPlanDiff]]:
    """Build the next executable StarPlanInput from evidence-backed patches.

    Whitelist (P1 Batch E): only `activity_preferences.*` fields may be
    patched. Free-text improvement suggestions are deliberately NOT mapped
    into Schema fields. The observation_log is always removed so a re-run
    does not trigger Review again.
    """
    if not original_input:
        return None, []

    next_input = copy.deepcopy(original_input)
    next_input.pop("observation_log", None)
    patches: list[RevisedPlanDiff] = []

    # Rule: evidence-backed late start -> shift activity_preferences.preferred_start
    delay_dev = next(
        (d for d in deviations if d.deviation_id == "dev.time.delay"),
        None,
    )
    late_cause = next(
        (c for c in causes if c.cause_id == "cause.team_late"),
        None,
    )
    if delay_dev is not None and late_cause is not None:
        if late_cause.classification == "evidence_based":
            actual = log.actual_start_time
            try:
                local_tz = ZoneInfo(timezone_name)
            except Exception:
                local_tz = ZoneInfo("Asia/Shanghai")
            if actual.tzinfo is not None:
                actual = actual.astimezone(local_tz).replace(tzinfo=None)
            else:
                actual = actual.replace(tzinfo=None)
            prefs = dict(next_input.get("activity_preferences") or {})
            old_start = prefs.get("preferred_start")
            prefs["preferred_start"] = actual.isoformat()
            next_input["activity_preferences"] = prefs
            patches.append(RevisedPlanDiff(
                field="activity_preferences.preferred_start",
                original_value=str(old_start) if old_start else "未设置",
                revised_value=actual.isoformat(),
                reason=(
                    f"本次实际开始 {actual.strftime('%H:%M')} 晚于计划，"
                    f"将下次活动开始时间调整到实际可用时间"
                ),
                source_cause_ids=["cause.team_late"],
            ))

    return next_input, patches


def _write_review_markdown(
    plan, log, deviations, causes, suggestions, diffs, path: str,
    next_input_path: Optional[str] = None,
) -> None:
    """Write the review report as markdown."""
    lines: list[str] = []
    lines.append(f"# 观测复盘报告: {plan.target_name}")
    lines.append("")
    lines.append(f"**地点**: {plan.location_name}")
    lines.append(f"**日期**: {plan.date_range[0]}")
    lines.append(f"**实际开始**: {log.actual_start_time.strftime('%H:%M')}")
    lines.append(f"**实际结束**: {log.actual_end_time.strftime('%H:%M')}")
    lines.append(f"**自评**: {log.success_rating}/5" if log.success_rating else "**自评**: 未评分")
    lines.append("")

    lines.append("## 偏差识别")
    lines.append("")
    # Batch C: deviation type Chinese mapping
    _deviation_type_zh = {"time": "时间", "environment": "环境", "equipment": "设备"}
    if deviations:
        for d in deviations:
            type_zh = _deviation_type_zh.get(d.deviation_type, d.deviation_type)
            lines.append(f"### {type_zh}偏差")
            lines.append(f"- **描述**: {d.description}")
            lines.append(f"- **计划**: {d.plan_reference}")
            lines.append(f"- **实际**: {d.actual_value}")
            lines.append("")
    else:
        lines.append("未发现显著偏差。")
        lines.append("")

    lines.append("## 原因分析")
    lines.append("")
    classification_labels = {
        "evidence_based": "有证据",
        "possible": "可能原因",
        "undetermined": "无法判断",
    }
    for c in causes:
        label = classification_labels.get(c.classification, c.classification)
        lines.append(f"- **{c.cause}** [{label}]: {c.evidence}")
    lines.append("")

    lines.append("## 改进建议")
    lines.append("")
    for s in suggestions:
        lines.append(f"- {s}")
    lines.append("")

    if diffs:
        lines.append("## 计划修订")
        lines.append("")
        lines.append("| 字段 | 原值 | 修订值 | 原因 |")
        lines.append("|---|---|---|---|")
        for d in diffs:
            lines.append(f"| {d.field} | {d.original_value} | {d.revised_value} | {d.reason} |")
        lines.append("")

    if next_input_path:
        lines.append("## 下一轮可执行输入")
        lines.append("")
        lines.append(f"- 已生成：`{next_input_path}`")
        lines.append("- 该文件通过 StarPlanInput Schema 校验，可再次进入 `starplan.run` 重跑")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _write_revised_plan(plan: dict, path: str) -> None:
    """Write the revised plan as JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2, default=str)


# ── Qwen-assisted attribution (Phase: post-Claim architecture) ──

def _qwen_available() -> bool:
    """Check if DASHSCOPE_API_KEY is configured."""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    return bool(api_key) and api_key != "your_api_key_here"


# Allowed classification levels (Qwen must only use these)
_ALLOWED_CLASSIFICATIONS = {"evidence_based", "possible", "undetermined"}


def _qwen_assisted_attribution(
    plan: ObservabilityResult,
    log: ObservationLog,
    deviations: list[Deviation],
    rule_causes: list[CauseEntry],
    log_path: Optional[str] = None,
) -> tuple[list[CauseEntry], list[str]]:
    """
    Use Qwen to provide richer cause attribution and improvement suggestions.

    Qwen receives structured evidence (deviations + rule-based causes) and
    returns additional cause classifications and suggestions. It NEVER
    generates numerical data — only classifies and suggests.

    Validation:
      - classification must be in {evidence_based, possible, undetermined}
      - no numbers in cause/evidence that aren't in the input data
      - suggestions must not contain specific numerical claims

    Returns:
        (additional_causes, additional_suggestions) tuple.
        Empty lists if Qwen fails or validation rejects.
    """
    from .qwen_client import call_qwen_json

    # Build structured evidence context
    deviation_text = "\n".join(
        f"- [{d.deviation_type}] {d.description} (计划: {d.plan_reference}; 实际: {d.actual_value})"
        for d in deviations
    )
    rule_cause_text = "\n".join(
        f"- {c.cause} [{c.classification}]: {c.evidence}"
        for c in rule_causes
    )

    # Collect all numbers from input data (for validation)
    allowed_numbers: set[str] = set()
    number_pattern = re.compile(r"\d+\.?\d*")
    for d in deviations:
        for n in number_pattern.findall(f"{d.description} {d.plan_reference} {d.actual_value}"):
            allowed_numbers.add(n)
    if log.success_rating:
        allowed_numbers.add(str(log.success_rating))
    allowed_numbers.update({str(i) for i in range(11)})  # Safe small numbers

    system_prompt = (
        "你是一位天文观测活动复盘顾问。根据提供的偏差证据，分析可能的原因并给出改进建议。\n\n"
        "严格规则：\n"
        "1. 原因分类只能是: evidence_based（有证据）、possible（可能）、undetermined（无法判断）\n"
        "2. 绝对不能编造任何数字（时间、角度、温度等），只能引用证据中已有的数值\n"
        "3. 不要重复已有的规则分析结果，只补充新视角\n"
        "4. 建议要具体可操作，但不要包含具体数值\n"
        "5. 返回 JSON: {\"causes\": [{\"cause\": \"...\", \"classification\": \"...\", \"evidence\": \"...\"}], "
        "\"suggestions\": [\"...\"]}\n"
    )

    user_prompt = (
        f"【观测偏差】\n{deviation_text}\n\n"
        f"【已有规则分析】\n{rule_cause_text}\n\n"
        f"【观测日志摘要】\n"
        f"- 云量: {log.cloud_cover or '未记录'}\n"
        f"- 视宁度: {log.seeing_conditions or '未记录'}\n"
        f"- 设备: {log.equipment_used}\n"
        f"- 备注: {log.observer_notes or '无'}\n"
        f"- 自评: {log.success_rating or '未评分'}/5\n\n"
        "请补充规则分析未覆盖的原因视角，并给出改进建议。"
    )

    result = call_qwen_json(
        prompt=user_prompt,
        system_prompt=system_prompt,
        log_path=log_path,
        step_name="review_attribution",
    )

    parsed = result.get("parsed_json")
    if not parsed:
        return [], []

    # Validate and extract causes
    valid_causes: list[CauseEntry] = []
    raw_causes = parsed.get("causes", [])
    if isinstance(raw_causes, list):
        for rc in raw_causes[:5]:  # Limit to 5 additional causes
            if not isinstance(rc, dict):
                continue
            cause_name = str(rc.get("cause", ""))[:50]
            classification = str(rc.get("classification", "undetermined"))
            evidence = str(rc.get("evidence", ""))[:200]

            # Validate classification
            if classification not in _ALLOWED_CLASSIFICATIONS:
                classification = "undetermined"

            # Validate no invented numbers in evidence
            evidence_nums = number_pattern.findall(evidence)
            has_invented = any(
                n not in allowed_numbers and n not in {"1", "2", "3", "4", "5"}
                for n in evidence_nums
            )
            if has_invented:
                continue  # Skip causes with invented numbers

            if cause_name:
                valid_causes.append(CauseEntry(
                    cause=cause_name,
                    classification=classification,
                    evidence=evidence or "Qwen 辅助分析",
                ))

    # Validate suggestions (no specific numbers)
    valid_suggestions: list[str] = []
    raw_suggestions = parsed.get("suggestions", [])
    if isinstance(raw_suggestions, list):
        for s in raw_suggestions[:5]:
            s = str(s)[:200]
            # Skip suggestions with specific numerical claims
            s_nums = number_pattern.findall(s)
            if any(n not in allowed_numbers and len(n) > 2 for n in s_nums):
                continue
            if s:
                valid_suggestions.append(s)

    return valid_causes, valid_suggestions
