#!/usr/bin/env python3
"""Compare a second-environment run against the committed evidence pack.

Second-environment runs get NEW run IDs and timestamps, so byte comparison
must be layered:

  STRICT   files that must be byte-identical (deterministic content, no
           timestamps / absolute paths / timing fields).
  TOLERANT files that legitimately differ across machines (timestamps,
           absolute run paths, stage timings, matplotlib rendering bytes).
  VALUE    files whose scientific/status fields must match even when the
           bytes differ (plan.json windows, run_outcome.json statuses,
           review_trace.json causes/diffs).

Usage:
    python scripts/compare_evidence_hashes.py --case case_01_m31_normal --run-dir <new_run_dir>
    python scripts/compare_evidence_hashes.py --case case_03_m31_review_loop \
        --run-dir <new_review_run_dir> --second-run-dir <new_second_run_dir>

Exit codes:
    0  all checks passed
    1  STRICT mismatch or missing STRICT file
    2  VALUE mismatch (science/status fields differ)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EVIDENCE_DIR = REPO_ROOT / "evidence"
MANIFEST_PATH = EVIDENCE_DIR / "evidence_manifest.json"


# Files that must be byte-identical across environments.
STRICT_FILES = {
    "input.json",
    "observation_log.json",
    "resolved_target.json",
    "claims.json",
    "expression_plan.json",
    "render_trace.json",
    "rendered_document.json",
    "sentence_claim_map.json",
    "outreach_pack.md",
    "outreach_pack_facilitator.md",
    "outreach_pack_learner.md",
    "revised_plan.json",
    "next_activity_input.json",
}

# Files whose bytes may differ but whose key fields must match.
VALUE_FILES = {
    "plan.json": "plan",
    "run_outcome.json": "run_outcome",
    "review_trace.json": "review_trace",
    "second_plan.json": "plan",
    "second_run_outcome.json": "run_outcome",
}

# Files where byte differences are expected and only a manual/numerical
# spot-check (or none) is required.
TOLERANT_FILES = {
    "observability.csv": "计算产物：建议抽查首末行/峰值高度（astropy 小版本可能改变浮点格式）",
    "visibility_curve.png": "图表字节（matplotlib/字体版本可能不同），人工目视核对曲线",
    "model_call_log.jsonl": "含时间戳",
    "state_log.json": "含时间戳",
    "calculation_manifest.json": "含 run_id / 时间戳 / 工具版本",
    "validation_report.md": "含 Run ID / 时间戳 / 工具版本",
    "review_report.md": "含本机绝对产物路径",
}


def _sha16(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _value_snapshot(path: Path, kind: str) -> Any:
    data = _load_json(path)
    if kind == "plan":
        return {
            key: data.get(key)
            for key in (
                "is_observable",
                "not_observable_reason",
                "recommended_window",
                "activity_slot",
                "alternative_suggestions",
                "blocking_reasons",
            )
        }
    if kind == "run_outcome":
        return {
            key: data.get(key)
            for key in (
                "business_status",
                "validation_status",
                "delivery_status",
                "qwen_used",
                "model_called",
                "model_output_accepted",
                "model_call_count",
            )
        }
    if kind == "review_trace":
        return {
            key: data.get(key)
            for key in (
                "deviations",
                "causes",
                "suggestions",
                "plan_diffs",
                "next_input_patches",
            )
        }
    raise ValueError(f"unknown value kind: {kind}")


def _local_path(run_dir: Path, entry_name: str, second_dir: Path | None) -> Path | None:
    if entry_name == "second_plan.json":
        return (second_dir / "plan.json") if second_dir else None
    if entry_name == "second_run_outcome.json":
        return (second_dir / "run_outcome.json") if second_dir else None
    return run_dir / entry_name


def _check_case(case: dict, run_dir: Path, second_dir: Path | None) -> tuple[list[str], list[str], list[str]]:
    strict_fail: list[str] = []
    value_fail: list[str] = []
    notes: list[str] = []
    hashes = case.get("sha256_prefix", {})

    for name, expected in hashes.items():
        local = _local_path(run_dir, name, second_dir)
        if local is None:
            notes.append(f"  [WARN] {name}: 缺少 second-run 目录，未对比")
            continue
        if not local.is_file():
            if name in STRICT_FILES:
                strict_fail.append(f"{name} (missing)")
            else:
                notes.append(f"  [WARN] {name}: 新环境缺少文件 {local}")
            continue

        actual = _sha16(local)
        if actual == expected:
            notes.append(f"  [OK]   {name}: {actual}")
            continue

        if name in STRICT_FILES:
            strict_fail.append(f"{name} (expected {expected}, got {actual})")
        elif name in VALUE_FILES:
            kind = VALUE_FILES[name]
            try:
                if _value_snapshot(local, kind) != _value_snapshot(EVIDENCE_DIR / case["case_id"] / name, kind):
                    value_fail.append(f"{name} (关键字段不一致，见 value diff)")
                else:
                    notes.append(f"  [OK]   {name}: 字节不同但关键字段一致 ({actual})")
            except Exception as exc:
                value_fail.append(f"{name} (无法解析: {exc})")
        else:
            reason = TOLERANT_FILES.get(name, "未知差异")
            notes.append(f"  [DIFF] {name}: 字节不同（预期内：{reason}） expected={expected} actual={actual}")
    return strict_fail, value_fail, notes


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare a new run against the evidence manifest")
    parser.add_argument("--case", required=True, help="case id, e.g. case_01_m31_normal")
    parser.add_argument("--run-dir", required=True, help="new run directory (first/review run)")
    parser.add_argument("--second-run-dir", help="new second run directory (case_03 only)")
    args = parser.parse_args()

    if not MANIFEST_PATH.is_file():
        print(f"[FAIL] manifest not found: {MANIFEST_PATH}")
        return 1
    manifest = _load_json(MANIFEST_PATH)
    case = next((c for c in manifest["cases"] if c["case_id"] == args.case), None)
    if case is None:
        print(f"[FAIL] unknown case: {args.case}")
        return 1

    run_dir = Path(args.run_dir)
    second_dir = Path(args.second_run_dir) if args.second_run_dir else None
    if not run_dir.is_dir():
        print(f"[FAIL] run dir not found: {run_dir}")
        return 1
    if case.get("second_run_id") and second_dir is None:
        print("[WARN] case_03 需要 --second-run-dir 才能对比 second_plan/second_run_outcome")

    print(f"对比案例：{case['case_id']}（{case['title']}）")
    print(f"新环境运行目录：{run_dir}")
    strict_fail, value_fail, notes = _check_case(case, run_dir, second_dir)

    print("\n逐文件结果：")
    for line in notes:
        print(line)

    print("\n结论：")
    if strict_fail:
        print(f"  [FAIL] STRICT 不一致（{len(strict_fail)}）：")
        for item in strict_fail:
            print(f"    - {item}")
    if value_fail:
        print(f"  [FAIL] 科学/状态字段不一致（{len(value_fail)}）：")
        for item in value_fail:
            print(f"    - {item}")
    if not strict_fail and not value_fail:
        print("  [OK] STRICT 文件一致；VALUE 文件关键字段一致；TOLERANT 差异均为预期内。")

    if strict_fail:
        return 1
    if value_fail:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
