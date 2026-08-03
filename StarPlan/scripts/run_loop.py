#!/usr/bin/env python3
"""StarPlan Loop CLI: run a case -> review -> re-run with next input.

Usage:
    python scripts/run_loop.py examples/case_03_observation_review.json

This is the explicit P1 Batch E entry point. It never auto-recurses inside
run_starplan; the second run reads `next_activity_input.json` produced by the
review and calls the runner again, then writes a before/after comparison.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from starplan_skills.runner import run_starplan


def _slot_summary(plan: dict) -> dict:
    slot = plan.get("activity_slot") or {}
    return {
        "start": slot.get("start"),
        "end": slot.get("end"),
        "setup_start": slot.get("setup_start"),
        "cleanup_end": slot.get("cleanup_end"),
        "duration_minutes": slot.get("duration_minutes"),
    }


def _schedule_lines(md_path: Path) -> list[str]:
    if not md_path.exists():
        return []
    lines = []
    in_schedule = False
    for line in md_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_schedule = stripped in ("## 活动流程", "## 建议安排")
            continue
        if in_schedule and stripped.startswith("- "):
            lines.append(stripped[2:])
    return lines


def run_loop(case_file: Path) -> dict:
    with open(case_file, "r", encoding="utf-8") as f:
        input_data = json.load(f)

    first = run_starplan(input_data)
    first_dir = Path(first["run_dir"])

    review = first.get("review")
    next_path = None
    if review and review.get("next_input_path"):
        next_path = Path(review["next_input_path"])

    second = None
    second_dir = None
    if next_path and next_path.exists():
        with open(next_path, "r", encoding="utf-8") as f:
            next_input = json.load(f)
        second = run_starplan(next_input, run_id=f"{first['run_id']}_next")
        second_dir = Path(second["run_dir"])

    # Write before/after comparison into the second run dir (or first if no re-run)
    out_dir = second_dir or first_dir
    report_path = out_dir / "loop_before_after.md"
    lines = [
        "# StarPlan Loop Before/After 对比",
        "",
        f"- 第一次运行（计划+复盘）: `{first['run_id']}` → {first_dir}",
        f"- 复盘运行: `{first['run_id']}`（review）",
        f"- 下一轮输入: `{next_path}`（存在且通过 Schema 校验）" if next_path else "- 下一轮输入: 未生成（原始输入缺失或证据不足）",
    ]
    if second:
        lines += [
            f"- 第二次运行（执行下一轮输入）: `{second['run_id']}` → {second_dir}",
            f"- 第二次运行验证状态: {second.get('validation_status')} / {second.get('delivery_status')}",
            "",
        ]
    else:
        lines += ["- 第二次运行: 未执行", ""]

    if review:
        lines.append("## 证据驱动的修订（复盘）")
        lines.append("")
        lines.append("| 字段 | 原值 | 修订值 | 原因 | 来源 Cause |")
        lines.append("|---|---|---|---|---|")
        for d in review.get("revised_plan_diff", []):
            lines.append(
                f"| {d.get('field')} | {d.get('original_value')} | "
                f"{d.get('revised_value')} | {d.get('reason')} | "
                f"{', '.join(d.get('source_cause_ids', []))} |"
            )
        lines.append("")

    before_plan = first.get("plan") or {}
    lines.append("## 活动时段变化")
    lines.append("")
    lines.append("| 项目 | 原计划 | 修订后 |")
    lines.append("|---|---|---|")
    after_plan = second.get("plan") if second else {}
    for key, label in (
        ("start", "活动开始"),
        ("end", "活动结束"),
        ("setup_start", "准备开始"),
        ("cleanup_end", "收尾结束"),
        ("duration_minutes", "时长(分钟)"),
    ):
        b = _slot_summary(before_plan).get(key)
        a = _slot_summary(after_plan).get(key) if second else "—"
        lines.append(f"| {label} | {b} | {a} |")
    lines.append("")

    lines.append("## 活动流程变化")
    lines.append("")
    before_sched = _schedule_lines(first_dir / "outreach_pack.md")
    after_sched = _schedule_lines(out_dir / "outreach_pack.md") if second else []
    if before_sched:
        lines.append("**原计划流程**：")
        lines.append("")
        lines.extend(f"- {s}" for s in before_sched)
        lines.append("")
    if after_sched and after_sched != before_sched:
        lines.append("**修订后流程**：")
        lines.append("")
        lines.extend(f"- {s}" for s in after_sched)
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[LOOP] First run : {first['run_id']}")
    if second:
        print(f"[LOOP] Second run: {second['run_id']} ({second.get('validation_status')})")
    print(f"[LOOP] Report    : {report_path}")
    return {
        "first_run_id": first["run_id"],
        "second_run_id": second["run_id"] if second else None,
        "report_path": str(report_path),
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_loop.py <case_json_file>")
        return 1
    case_file = PROJECT_ROOT / sys.argv[1]
    if not case_file.exists():
        print(f"Error: File not found: {case_file}")
        return 1
    run_loop(case_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
