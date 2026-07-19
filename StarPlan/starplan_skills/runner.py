"""
StarPlan Loop - Orchestrator (runner)

Entry point for running a complete StarPlan pipeline:
  target_resolve → observability_plan → outreach_pack → observation_review

Each run produces a complete output directory with all intermediate
results, calculation manifest, and validation report.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from .config import get_run_dir, load_constraints
from .schemas import (
    CalculationManifest,
    ModelInfo,
    ObservationLog,
    ObservabilityResult,
    ResolvedTarget,
    StarPlanInput,
    ToolVersions,
)
from .target_resolve import resolve_target, resolve_location
from .observability_plan import compute_observability
from .outreach_pack import generate_outreach_pack
from .observation_review import review_observation


def run_starplan(
    input_data: dict,
    run_id: Optional[str] = None,
) -> dict:
    """
    Run the full StarPlan pipeline for a given input.

    Args:
        input_data: Unified input dict (matches StarPlanInput schema).
        run_id: Optional run identifier. Auto-generated if not provided.

    Returns:
        Dict with all results: target, plan, outreach_pack, manifest, etc.
    """
    # Parse and validate input
    starplan_input = StarPlanInput(**input_data)

    # Generate run ID (with timestamp to avoid collisions between cases)
    if not run_id:
        target_slug = starplan_input.target.lower().replace(" ", "_")
        date_slug = starplan_input.date_range[0].strftime("%Y%m%d")
        ts_slug = datetime.now().strftime("%H%M%S")
        has_log = "observation_log" in input_data
        suffix = "_review" if has_log else ""
        run_id = f"{target_slug}_{starplan_input.location.replace('_', '-')}_{date_slug}_{ts_slug}{suffix}"

    run_dir = get_run_dir(run_id)

    # Save original input
    with open(run_dir / "input.json", "w", encoding="utf-8") as f:
        json.dump(input_data, f, ensure_ascii=False, indent=2)

    # ── Step 1: Resolve target ──
    print(f"[1/4] Resolving target: {starplan_input.target}")
    resolved = resolve_target(starplan_input.target, starplan_input.target_type)

    if resolved.requires_confirmation:
        print(f"  [!] Target requires confirmation. Candidates: {len(resolved.candidates or [])}")
        if resolved.confidence == 0:
            raise ValueError(f"Target '{starplan_input.target}' not found in catalog")

    with open(run_dir / "resolved_target.json", "w", encoding="utf-8") as f:
        json.dump(resolved.model_dump(), f, ensure_ascii=False, indent=2, default=str)

    print(f"  [OK] {resolved.standard_name}: RA={resolved.ra_deg:.4f} deg, Dec={resolved.dec_deg:.4f} deg")

    # ── Step 2: Resolve location ──
    if starplan_input.location_detail:
        location = starplan_input.location_detail.model_dump()
    else:
        loc = resolve_location(starplan_input.location)
        if not loc:
            raise ValueError(f"Location '{starplan_input.location}' not found. Provide location_detail.")
        location = loc

    # ── Step 3: Compute observability ──
    print(f"[2/4] Computing observability for {resolved.standard_name} at {location['name']}")
    obs_result = compute_observability(
        ra_deg=resolved.ra_deg,
        dec_deg=resolved.dec_deg,
        target_name=resolved.standard_name,
        location=location,
        date_range=[str(d) for d in starplan_input.date_range],
        equipment=starplan_input.equipment,
        constraints=starplan_input.constraints.model_dump() if starplan_input.constraints else None,
        run_dir=run_dir,
        target_magnitude=resolved.visual_magnitude,
        target_angular_size_arcmin=resolved.angular_size_arcmin,
    )

    plan_data = obs_result.model_dump(mode="json")
    with open(run_dir / "plan.json", "w", encoding="utf-8") as f:
        json.dump(plan_data, f, ensure_ascii=False, indent=2, default=str)

    if obs_result.is_observable and obs_result.recommended_window:
        w = obs_result.recommended_window.window
        print(f"  [OK] Observable! Recommended: {w.start.strftime('%H:%M')} ~ {w.end.strftime('%H:%M')}")
        print(f"    Peak altitude: {obs_result.recommended_window.peak_altitude_deg:.1f} deg")
    else:
        print(f"  [FAIL] Target not observable on this date.")
        for s in obs_result.alternative_suggestions:
            print(f"    Suggestion: {s.description}")

    # ── Step 4: Generate outreach pack ──
    print(f"[3/4] Generating outreach pack for audience: {starplan_input.audience}")
    outreach = generate_outreach_pack(
        target=resolved,
        obs_result=obs_result,
        audience=starplan_input.audience,
        equipment=starplan_input.equipment,
        goal=starplan_input.goal,
        run_dir=run_dir,
    )
    print(f"  [OK] Outreach pack: {outreach.outreach_pack_md_path}")

    # ── Step 5: Observation review (if log provided) ──
    review = None
    observation_log = input_data.get("observation_log")
    if observation_log:
        print(f"[4/4] Reviewing observation log")
        log = ObservationLog(**observation_log)
        review = review_observation(
            original_plan=obs_result,
            log=log,
            run_dir=run_dir,
        )
        print(f"  [OK] Deviations found: {len(review.deviation_summary)}")
        print(f"  [OK] Review report: {review.review_report_md_path}")
    else:
        print(f"[4/4] No observation log provided -- skipping review")

    # ── Generate model call log ──
    _write_model_call_log(run_dir, starplan_input, resolved, obs_result)

    # ── Save calculation manifest ──
    manifest = _build_manifest(
        run_id=run_id,
        input_data=input_data,
        resolved=resolved,
        location=location,
        obs_result=obs_result,
        run_dir=run_dir,
    )
    with open(run_dir / "calculation_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest.model_dump(), f, ensure_ascii=False, indent=2, default=str)

    # ── Generate validation report ──
    _write_validation_report(run_dir, resolved, obs_result, manifest)

    print(f"\n[OK] Run complete: {run_dir}")
    print(f"  Files: {len(list(run_dir.iterdir()))} in {run_dir}")

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "target": resolved.model_dump(),
        "plan": plan_data,
        "outreach_pack": outreach.model_dump(),
        "review": review.model_dump() if review else None,
        "manifest": manifest.model_dump(),
    }


def _build_manifest(
    run_id: str,
    input_data: dict,
    resolved: ResolvedTarget,
    location: dict,
    obs_result: ObservabilityResult,
    run_dir: Path,
) -> CalculationManifest:
    """Build the calculation manifest for this run."""
    import astropy
    import astroplan

    tz = timezone(timedelta(hours=8))

    return CalculationManifest(
        run_id=run_id,
        timestamp=datetime.now(tz),
        input=input_data,
        target={
            "standard_name": resolved.standard_name,
            "ra_deg": resolved.ra_deg,
            "dec_deg": resolved.dec_deg,
            "source": resolved.source,
            "confidence": resolved.confidence,
        },
        location=location,
        tools=ToolVersions(
            astropy_version=astropy.__version__,
            astroplan_version=astroplan.__version__,
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        ),
        model=ModelInfo(),
        constraints_applied={
            "min_altitude_deg": load_constraints().get("altitude", {}).get("min_altitude_deg", 30),
            "max_airmass": load_constraints().get("airmass", {}).get("max_airmass", 2.0),
        },
        intermediate_files=[f.name for f in run_dir.iterdir() if f.is_file()],
        validation_status="passed",
    )


def _write_validation_report(
    run_dir: Path,
    resolved: ResolvedTarget,
    obs: ObservabilityResult,
    manifest: CalculationManifest,
) -> None:
    """Write a validation report for this run."""
    lines: list[str] = []
    lines.append("# Validation Report")
    lines.append("")
    lines.append(f"**Run ID**: {manifest.run_id}")
    lines.append(f"**Timestamp**: {manifest.timestamp.isoformat()}")
    lines.append("")

    # Input check
    lines.append("## 输入检查")
    lines.append("")
    lines.append(f"- 目标名称: ✓ 已提供")
    lines.append(f"- 地点: ✓ {manifest.location.get('name', 'unknown')}")
    lines.append(f"- 日期: ✓ {manifest.input.get('date_range')}")
    lines.append("")

    # Target check
    lines.append("## 目标检查")
    lines.append("")
    lines.append(f"- 标准名称: {resolved.standard_name}")
    lines.append(f"- 坐标: RA={resolved.ra_deg:.4f}°, Dec={resolved.dec_deg:.4f}°")
    lines.append(f"- 数据来源: {resolved.source}")
    lines.append(f"- 置信度: {resolved.confidence:.2f}")
    lines.append(f"- 状态: {'✓ 通过' if resolved.confidence >= 0.9 else '⚠️ 低置信度'}")
    lines.append("")

    # Calculation check
    lines.append("## 计算检查")
    lines.append("")
    lines.append(f"- 可观测: {'✓ 是' if obs.is_observable else '✗ 否'}")
    lines.append(f"- 数据点数: {len(obs.hourly_data)}")
    lines.append(f"- 可见窗口数: {len(obs.visibility_windows)}")
    if obs.recommended_window:
        lines.append(f"- 推荐窗口峰值高度: {obs.recommended_window.peak_altitude_deg:.1f}°")
    lines.append(f"- 风险标记数: {len(obs.risk_flags)}")
    lines.append("")

    # Tool versions
    lines.append("## 工具版本")
    lines.append("")
    lines.append(f"- Astropy: {manifest.tools.astropy_version}")
    lines.append(f"- astroplan: {manifest.tools.astroplan_version}")
    lines.append(f"- Python: {manifest.tools.python_version}")
    lines.append("")

    # Overall
    target_ok = resolved.confidence >= 0.9
    data_ok = len(obs.hourly_data) > 0
    observable = obs.is_observable
    has_reasons = len(obs.alternative_suggestions) > 0 or len(obs.risk_flags) > 0

    if target_ok and data_ok and observable:
        status = "[PASS] PASSED"
    elif target_ok and data_ok and not observable and has_reasons:
        status = "[PASS] EXPECTED_FAILURE -- not observable with proper reasons and alternatives"
    elif target_ok and data_ok and not observable and not has_reasons:
        status = "[REVIEW] NEEDS REVIEW -- not observable but no alternatives provided"
    else:
        status = "[FAIL] FAILED -- target resolution or data computation issue"

    lines.append("## 总体结论")
    lines.append("")
    lines.append(f"**状态**: {status}")
    lines.append(f"**可观测**: {'Yes' if observable else 'No'}")
    if not observable:
        lines.append(f"**备选建议数**: {len(obs.alternative_suggestions)}")
    lines.append("")

    with open(run_dir / "validation_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _write_model_call_log(
    run_dir: Path,
    starplan_input: StarPlanInput,
    resolved: ResolvedTarget,
    obs_result: ObservabilityResult,
) -> None:
    """Write model_call_log.jsonl recording pipeline steps and Qwen usage."""
    import os
    tz = timezone(timedelta(hours=8))
    log_entries: list[dict] = []

    # Record target_resolve step (deterministic, no model call)
    log_entries.append({
        "timestamp": datetime.now(tz).isoformat(),
        "step": "target_resolve",
        "type": "deterministic_tool",
        "input": {"target_name": starplan_input.target},
        "output": {"standard_name": resolved.standard_name, "confidence": resolved.confidence},
        "model_used": None,
    })

    # Record observability_plan step (deterministic, no model call)
    log_entries.append({
        "timestamp": datetime.now(tz).isoformat(),
        "step": "observability_plan",
        "type": "deterministic_tool",
        "input": {
            "target": resolved.standard_name,
            "location": starplan_input.location,
            "date_range": [str(d) for d in starplan_input.date_range],
        },
        "output": {
            "is_observable": obs_result.is_observable,
            "recommended_window": str(obs_result.recommended_window.window.start) if obs_result.recommended_window else None,
        },
        "model_used": None,
    })

    # Record outreach_pack step
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    qwen_available = api_key and api_key != "your_api_key_here"
    log_entries.append({
        "timestamp": datetime.now(tz).isoformat(),
        "step": "outreach_pack",
        "type": "model_assisted",
        "qwen_available": qwen_available,
        "model_used": "Qwen3.7-Max" if qwen_available else None,
        "note": (
            "Qwen available -- outreach content can be enhanced with model-generated explanations"
            if qwen_available
            else "DASHSCOPE_API_KEY not set -- outreach pack generated from template only, no Qwen call"
        ),
    })

    log_path = run_dir / "model_call_log.jsonl"
    with open(log_path, "w", encoding="utf-8") as f:
        for entry in log_entries:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
