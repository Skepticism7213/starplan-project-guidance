"""
StarPlan Loop - Skill 4: observation_review (stub for MVP)

Compares an original observation plan with an actual observation log,
identifies deviations, classifies causes, and generates a revised plan.

Core principle: Distinguish "evidence-based cause" from "possible cause"
and "undetermined". Never assign strong blame to factors with only weak
evidence.
"""

from __future__ import annotations

import json
from datetime import timedelta, timezone
from pathlib import Path
from typing import Optional

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
) -> ObservationReview:
    """
    Compare original plan with actual observation log and generate review.

    Args:
        original_plan: The observability plan that was followed.
        log: The actual observation log.
        run_dir: Output directory for reports.

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
        # Naive times are assumed to be local (Asia/Shanghai, +08:00).
        local_tz = timezone(timedelta(hours=8))
        if planned_start.tzinfo is None:
            planned_start = planned_start.replace(tzinfo=local_tz)
        if actual_start.tzinfo is None:
            actual_start = actual_start.replace(tzinfo=local_tz)
        planned_start_utc = planned_start.astimezone(timezone.utc)
        actual_start_utc = actual_start.astimezone(timezone.utc)

        delay_minutes = (actual_start_utc - planned_start_utc).total_seconds() / 60

        if delay_minutes > 10:
            deviations.append(Deviation(
                deviation_type="time",
                description=f"实际开始时间比计划晚 {delay_minutes:.0f} 分钟",
                plan_reference=f"计划开始时间: {planned_start.strftime('%H:%M')}",
                actual_value=f"实际开始时间: {actual_start.strftime('%H:%M')}",
            ))
            causes.append(CauseEntry(
                cause="团队迟到",
                classification="evidence_based",
                evidence=f"计划开始 {planned_start.strftime('%H:%M')}，实际开始 {actual_start.strftime('%H:%M')}，延迟 {delay_minutes:.0f} 分钟",
            ))
            suggestions.append('下次活动增加"提前30分钟到场"步骤，确保在推荐窗口开始时已就位')
            plan_diffs.append(RevisedPlanDiff(
                field="preparation_step",
                original_value="无提前到场要求",
                revised_value="提前 30 分钟到场进行设备调试和暗适应",
                reason=f"本次迟到 {delay_minutes:.0f} 分钟，错过了早期高高度窗口",
            ))

    # ── 2. Environment deviation ──
    if log.cloud_cover and log.cloud_cover != "clear":
        deviations.append(Deviation(
            deviation_type="environment",
            description=f"云量: {log.cloud_cover}",
            plan_reference="计划假设晴朗天空",
            actual_value=f"实际云量: {log.cloud_cover}",
        ))
        causes.append(CauseEntry(
            cause="云层干扰",
            classification="evidence_based" if log.observer_notes and "云" in log.observer_notes else "possible",
            evidence=f"观测日志记录云量为 {log.cloud_cover}" + (
                f"，备注: {log.observer_notes}" if log.observer_notes and "云" in log.observer_notes else ""
            ),
        ))
        suggestions.append("活动前增加天气预报检查步骤，关注云量预报")
        suggestions.append("准备备选方案：若云量 > 50%，转为室内科普讲座")

    # ── 3. Equipment deviation ──
    if log.observer_notes:
        if "三脚架" in log.observer_notes or "不稳" in log.observer_notes:
            deviations.append(Deviation(
                deviation_type="equipment",
                description="三脚架不稳定，影响观测效果",
                plan_reference="设备清单包含三脚架",
                actual_value="三脚架不稳定",
            ))
            causes.append(CauseEntry(
                cause="设备准备不足",
                classification="evidence_based",
                evidence=f"观测者备注: {log.observer_notes}",
            ))
            suggestions.append("增加设备检查步骤：活动前测试三脚架稳定性")
            plan_diffs.append(RevisedPlanDiff(
                field="equipment_check_step",
                original_value="无设备预检步骤",
                revised_value="活动前 30 分钟检查三脚架稳定性、望远镜调焦",
                reason="本次三脚架不稳影响观测",
            ))

    # ── 4. Expectation / operation issues ──
    if log.observer_notes and "不如预期" in log.observer_notes:
        causes.append(CauseEntry(
            cause="成员期望管理",
            classification="undetermined",
            evidence=f"备注提到'不如预期清晰'，但无法确定是设备、目标还是期望问题",
        ))
        suggestions.append("活动前增加'预期管理'说明：深空目标目视效果通常为模糊光斑，非照片般清晰")
        plan_diffs.append(RevisedPlanDiff(
            field="expectation_management",
            original_value="无预期管理说明",
            revised_value="活动前发放'目视效果预期说明'，附真实目视照片对比",
            reason="新成员对深空目标目视效果期望过高",
        ))

    # ── 5. Seeing conditions ──
    if log.seeing_conditions and log.seeing_conditions != "good":
        causes.append(CauseEntry(
            cause="视宁度",
            classification="possible",
            evidence=f"视宁度记录为 {log.seeing_conditions}，但无法确定是否为主要影响因素",
        ))

    # ── Build revised plan ──
    revised_plan = _build_revised_plan(original_plan, plan_diffs, suggestions)

    # ── Generate report ──
    review_md_path = None
    revised_json_path = None
    if run_dir:
        review_md_path = str(run_dir / "review_report.md")
        revised_json_path = str(run_dir / "revised_plan.json")
        _write_review_markdown(
            original_plan, log, deviations, causes,
            suggestions, plan_diffs, review_md_path,
        )
        _write_revised_plan(revised_plan, revised_json_path)

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


def _write_review_markdown(
    plan, log, deviations, causes, suggestions, diffs, path: str,
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
    if deviations:
        for d in deviations:
            lines.append(f"### {d.deviation_type}偏差")
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
        for d in diffs:
            lines.append(f"| 字段 | 原值 | 修订值 | 原因 |")
            lines.append(f"|---|---|---|---|")
            lines.append(f"| {d.field} | {d.original_value} | {d.revised_value} | {d.reason} |")
            lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _write_revised_plan(plan: dict, path: str) -> None:
    """Write the revised plan as JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2, default=str)
