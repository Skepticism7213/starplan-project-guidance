#!/usr/bin/env python3
"""Build the P3 three-case evidence pack from canonical runs.

The pack is the submission-ready snapshot of the three typical tasks:
  case_01  M31 normal observability (Jinan, 2026-10-17)
  case_02  M42 not-observable + verified alternatives (Jinan, 2026-07-25)
  case_03  M31 review loop -> next_activity_input -> second run

`runs/` is gitignored, so this script copies the whitelisted artifacts into
`evidence/case_XX/`, writes SHA-256 hashes into `evidence/evidence_manifest.json`,
keeps human-confirmation templates stable across rebuilds, and (for case_03)
generates `loop_before_after.md` from the first review run and the second run.

Usage:
    python scripts/build_evidence_pack.py [--force]

Exit codes:
    0  pack rebuilt successfully (warnings may still be printed)
    1  a canonical run directory is missing or no files could be copied
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STARPLAN_ROOT = REPO_ROOT / "StarPlan"
RUNS_DIR = STARPLAN_ROOT / "runs"
EVIDENCE_DIR = REPO_ROOT / "evidence"


CASES = [
    {
        "case_id": "case_01_m31_normal",
        "run_id": "m31_济南-四门塔_20261017_170745",
        "second_run_id": None,
        "title": "M31 正常可观测活动（济南四门塔，2026-10-17）",
        "files": [
            "input.json",
            "resolved_target.json",
            "plan.json",
            "observability.csv",
            "visibility_curve.png",
            "claims.json",
            "expression_plan.json",
            "render_trace.json",
            "rendered_document.json",
            "sentence_claim_map.json",
            "outreach_pack.md",
            "outreach_pack_facilitator.md",
            "outreach_pack_learner.md",
            "validation_report.md",
            "calculation_manifest.json",
            "model_call_log.jsonl",
            "state_log.json",
            "run_outcome.json",
        ],
    },
    {
        "case_id": "case_02_m42_unfavorable",
        "run_id": "m42_济南-四门塔_20260725_172320",
        "second_run_id": None,
        "title": "M42 不适合观测及备选方案（济南四门塔，2026-07-25）",
        "files": [
            "input.json",
            "resolved_target.json",
            "plan.json",
            "observability.csv",
            "visibility_curve.png",
            "claims.json",
            "expression_plan.json",
            "render_trace.json",
            "rendered_document.json",
            "sentence_claim_map.json",
            "outreach_pack.md",
            "validation_report.md",
            "calculation_manifest.json",
            "model_call_log.jsonl",
            "state_log.json",
            "run_outcome.json",
        ],
    },
    {
        "case_id": "case_03_m31_review_loop",
        "run_id": "m31_济南-四门塔_20261017_184517_review",
        "second_run_id": "m31_review_20261017_184517_next",
        "title": "M31 复盘闭环：观测日志 → 证据归因 → 可执行下一轮 → 二次运行",
        "files": [
            "input.json",
            "observation_log.json",
            "resolved_target.json",
            "plan.json",
            "observability.csv",
            "visibility_curve.png",
            "claims.json",
            "expression_plan.json",
            "render_trace.json",
            "rendered_document.json",
            "sentence_claim_map.json",
            "outreach_pack.md",
            "outreach_pack_facilitator.md",
            "outreach_pack_learner.md",
            "review_report.md",
            "review_trace.json",
            "revised_plan.json",
            "next_activity_input.json",
            "validation_report.md",
            "calculation_manifest.json",
            "model_call_log.jsonl",
            "state_log.json",
            "run_outcome.json",
        ],
    },
]


_HUMAN_CONFIRMATION_TEMPLATE = """# 人工确认清单：{title}

- 案例：{case_id}
- 来源运行：`StarPlan/runs/{run_id}`
- 确认性质：□ 真实观测记录　□ 模拟/演示输入（桌面演练）　□ 混合（请说明）
- 确认日期：____
- 确认人：____（项目负责人 / 独立复核人）

## 确认项（逐项打勾）

- [ ] 输入与本次活动实际一致（目标、地点、日期、设备、受众）
- [ ] 输出中的坐标、窗口、活动时段与确定性计算一致，无模型编造
- [ ] 不可观测案例的 `not_observable_reason` 与备选方案已人工核对
- [ ] 复盘案例的偏差、归因、修订与观测日志一致
- [ ] `validation_report.md` / `run_outcome.json` 状态为 passed
- [ ] 产物目录与文件名齐全（见 evidence_manifest.json 哈希）
- [ ] 未成年人场景已确认监护人许可 / 成人陪同 / 点名流程（如适用）

## 备注

- 人工发现或补充：____
- 签名：____
"""


def _sha16(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _copy_case(case: dict, force: bool) -> dict:
    case_dir = EVIDENCE_DIR / case["case_id"]
    case_dir.mkdir(parents=True, exist_ok=True)
    run_dir = RUNS_DIR / case["run_id"]
    if not run_dir.is_dir():
        print(f"[WARN] missing run dir: {run_dir}")
        return {"case_id": case["case_id"], "status": "missing_run"}

    copied: list[str] = []
    hashes: dict[str, str] = {}
    for name in case["files"]:
        src = run_dir / name
        if not src.is_file():
            print(f"[WARN] missing artifact {name} in {run_dir}")
            continue
        dst = case_dir / name
        shutil.copy2(src, dst)
        hashes[name] = _sha16(dst)
        copied.append(name)

    # Second-run artifacts for case_03 (kept only when present).
    second = case.get("second_run_id")
    if second:
        second_dir = RUNS_DIR / second
        if second_dir.is_dir():
            for name, out_name in (
                ("plan.json", "second_plan.json"),
                ("run_outcome.json", "second_run_outcome.json"),
            ):
                src = second_dir / name
                if src.is_file():
                    dst = case_dir / out_name
                    shutil.copy2(src, dst)
                    hashes[out_name] = _sha16(dst)
                    copied.append(out_name)
            _write_loop_before_after(case, run_dir, second_dir, case_dir)
        else:
            print(f"[WARN] missing second run dir for {case['case_id']}: {second}")

    # Keep an existing human confirmation; create the template once.
    confirm = case_dir / "human_confirmation.md"
    if not confirm.exists() or force:
        confirm.write_text(
            _HUMAN_CONFIRMATION_TEMPLATE.format(
                title=case["title"], case_id=case["case_id"], run_id=case["run_id"]
            ),
            encoding="utf-8",
        )
    return {
        "case_id": case["case_id"],
        "title": case["title"],
        "run_id": case["run_id"],
        "second_run_id": second,
        "status": "ok" if copied else "no_files",
        "file_count": len(copied),
        "files": copied,
        "sha256_prefix": hashes,
    }


def _write_loop_before_after(case: dict, first_dir: Path, second_dir: Path, case_dir: Path) -> None:
    def _plan(run_dir: Path) -> dict:
        path = run_dir / "plan.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def _review(run_dir: Path) -> dict:
        path = run_dir / "review_trace.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    first = _plan(first_dir)
    second = _plan(second_dir)
    review = _review(first_dir)
    before_slot = (first.get("activity_slot") or {}).get("start", "N/A")
    after_slot = (second.get("activity_slot") or {}).get("start", "N/A")
    cause_ids = [c.get("cause_id", "") for c in review.get("causes", [])]

    lines = [
        "# 循环 before/after 对比",
        "",
        f"- 案例：{case['title']}",
        f"- 第一轮（含观测日志）：`StarPlan/runs/{first_dir.name}`",
        f"- 第二轮（next_activity_input.json 重跑）：`StarPlan/runs/{second_dir.name}`",
        f"- 归因原因：{', '.join(cause_ids) if cause_ids else 'N/A'}",
        "",
        "## 活动时段变化",
        "",
        "| 字段 | 第一轮 | 第二轮 |",
        "|---|---|---|",
        f"| activity_slot.start | {before_slot} | {after_slot} |",
    ]
    for diff in review.get("plan_diffs", []):
        field = diff.get("field", "")
        reason = diff.get("reason", "")
        causes = ", ".join(diff.get("source_cause_ids", []))
        lines.append(f"- 修订 {field}：{reason}（来源：{causes}）")
    if not review.get("plan_diffs"):
        lines.append("- 无修订字段。")

    (case_dir / "loop_before_after.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the P3 evidence pack")
    parser.add_argument("--force", action="store_true", help="overwrite human confirmation templates")
    args = parser.parse_args()

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    results = [_copy_case(case, args.force) for case in CASES]
    failed = [r for r in results if r.get("status") != "ok"]
    if failed:
        print("[FAIL] cases with missing artifacts:")
        for r in failed:
            print(f"  - {r['case_id']}: {r.get('status')}")
        return 1

    manifest = {
        "schema_version": "1.0",
        "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "repository": "https://github.com/Skepticism7213/starplan-project-guidance",
        "model_mode": "offline_deterministic",
        "cases": results,
    }
    manifest_path = EVIDENCE_DIR / "evidence_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] evidence pack written to {EVIDENCE_DIR}")
    for r in results:
        print(f"  - {r['case_id']}: {r['file_count']} files")
    print(f"[OK] manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
