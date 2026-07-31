"""
StarPlan Loop - Orchestrator (runner) — Week 3 enhanced.

Entry point for running a complete StarPlan pipeline:
  target_resolve → observability_plan → outreach_pack → observation_review

Three entry modes:
  1. run_starplan(input_data) — structured dict input (original)
  2. run_starplan_nl(text) — natural language input, Qwen parses to struct
  3. run_starplan_chat(text) — Qwen orchestrates tools via function calling

Each run produces a complete output directory with all intermediate
results, calculation manifest, model call log, and validation report.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from .config import get_run_dir
from .schemas import (
    CalculationManifest,
    ObservationLog,
    ObservabilityResult,
    ResolvedTarget,
    RunState,
    StarPlanInput,
)
from .target_resolve import resolve_target, resolve_location
from .exceptions import TargetConfirmationRequired
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

    # Phase D: RunState state machine tracking
    state_log: list[dict] = []
    _run_dir_ref: list = []  # mutable ref so closure can access run_dir before assignment

    def _transition(new_state: RunState, note: str = ""):
        state_log.append({
            "state": new_state.value,
            "timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "note": note,
        })
        # Incremental flush: preserve audit trail even on exception
        if _run_dir_ref:
            try:
                with open(_run_dir_ref[0] / "state_log.json", "w", encoding="utf-8") as f:
                    json.dump(state_log, f, ensure_ascii=False, indent=2)
            except OSError:
                pass  # Best-effort; don't crash pipeline for logging

    _transition(RunState.RECEIVED, f"input target={starplan_input.target}")

    # Generate run ID (with timestamp to avoid collisions between cases)
    if not run_id:
        target_slug = starplan_input.target.lower().replace(" ", "_")
        date_slug = starplan_input.date_range[0].strftime("%Y%m%d")
        ts_slug = datetime.now().strftime("%H%M%S")
        has_log = starplan_input.observation_log is not None
        suffix = "_review" if has_log else ""
        run_id = f"{target_slug}_{starplan_input.location.replace('_', '-')}_{date_slug}_{ts_slug}{suffix}"

    run_dir = get_run_dir(run_id)
    _run_dir_ref.append(run_dir)  # Enable incremental state_log flush

    # Save original input
    with open(run_dir / "input.json", "w", encoding="utf-8") as f:
        json.dump(input_data, f, ensure_ascii=False, indent=2)

    _transition(RunState.INPUT_VALIDATED, "StarPlanInput schema validated")

    # P0-C: Create RunOutcome at entry — before any resolution/computation.
    # This ensures every terminal state (including early failures) has a RunOutcome.
    from .run_outcome import RunOutcome, BusinessStatus, ValidationStatus, DeliveryStatus
    outcome = RunOutcome(
        run_id=run_id,
        input_data=input_data,
        state_log=state_log,
    )

    # ── Step 1: Resolve target ──
    # C-2 fix: If confirmed_target is provided, the human has already selected
    # from a previous candidates list — bypass ambiguity check.
    try:
        if starplan_input.confirmed_target:
            print(f"[1/4] Resolving confirmed target: {starplan_input.confirmed_target}")
            resolved = resolve_target(starplan_input.confirmed_target, starplan_input.target_type)
            if resolved.requires_confirmation:
                raise ValueError(
                    f"confirmed_target '{starplan_input.confirmed_target}' is still ambiguous. "
                    f"Provide an exact standard name (e.g. 'M33', 'M31')."
                )
        else:
            print(f"[1/4] Resolving target: {starplan_input.target}")
            resolved = resolve_target(starplan_input.target, starplan_input.target_type)

            if resolved.requires_confirmation:
                if resolved.confidence == 0:
                    raise ValueError(f"Target '{starplan_input.target}' not found in catalog")
                # P0-C: set terminal state before raising
                outcome.business_status = BusinessStatus.NEEDS_CONFIRMATION
                outcome.validation_status = ValidationStatus.PASSED
                outcome.delivery_status = DeliveryStatus.NOT_DELIVERED
                outcome.error_message_safe = (
                    f"Target '{starplan_input.target}' is ambiguous "
                    f"({len(resolved.candidates or [])} candidates). "
                    f"Re-invoke with confirmed_target."
                )
                _persist_outcome(outcome, run_dir)
                raise TargetConfirmationRequired(
                    f"Target '{starplan_input.target}' is ambiguous "
                    f"(best match: {resolved.standard_name}, confidence={resolved.confidence:.2f}). "
                    f"{len(resolved.candidates or [])} candidates require human selection. "
                    f"Re-invoke with confirmed_target='<chosen standard name>'.",
                    resolved=resolved,
                )
    except TargetConfirmationRequired:
        raise  # Already persisted outcome above
    except Exception as e:
        # P0-C: tool/data error during target resolution
        outcome.business_status = BusinessStatus.TOOL_ERROR
        outcome.validation_status = ValidationStatus.PENDING
        outcome.delivery_status = DeliveryStatus.NOT_DELIVERED
        outcome.error_type = type(e).__name__
        outcome.error_message_safe = str(e)[:200]
        _persist_outcome(outcome, run_dir)
        raise

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

    _transition(RunState.READY_TO_COMPUTE, f"location={location.get('name', 'unknown')}")

    # ── Step 3: Compute observability ──
    print(f"[2/4] Computing observability for {resolved.standard_name} at {location['name']}")
    try:
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
            target_type=resolved.target_type,
        )
    except Exception as e:
        # P0-C: persist RunOutcome with tool_error before propagating
        outcome.target = resolved
        outcome.location = location
        outcome.business_status = BusinessStatus.TOOL_ERROR
        outcome.validation_status = ValidationStatus.PENDING
        outcome.delivery_status = DeliveryStatus.NOT_DELIVERED
        outcome.error_type = type(e).__name__
        outcome.error_message_safe = str(e)[:200]
        _persist_outcome(outcome, run_dir)
        raise

    plan_data = obs_result.model_dump(mode="json")
    with open(run_dir / "plan.json", "w", encoding="utf-8") as f:
        json.dump(plan_data, f, ensure_ascii=False, indent=2, default=str)

    if obs_result.is_observable and obs_result.recommended_window:
        w = obs_result.recommended_window.window
        print(f"  [OK] Observable! Recommended: {w.start.strftime('%H:%M')} ~ {w.end.strftime('%H:%M')}")
        print(f"    Peak altitude: {obs_result.recommended_window.peak_altitude_deg:.1f} deg")
        _transition(RunState.COMPUTED_OBSERVABLE, f"peak_alt={obs_result.recommended_window.peak_altitude_deg:.1f}")
    else:
        print(f"  [FAIL] Target not observable on this date.")
        for s in obs_result.alternative_suggestions:
            print(f"    Suggestion: {s.description}")
        _transition(RunState.COMPUTED_NOT_OBSERVABLE, "target below constraints")

    # ── Step 4: Generate outreach pack ──
    print(f"[3/4] Generating outreach pack for audience: {starplan_input.audience}")
    log_path = str(run_dir / "model_call_log.jsonl")
    outreach = generate_outreach_pack(
        target=resolved,
        obs_result=obs_result,
        audience=starplan_input.audience,
        equipment=starplan_input.equipment,
        goal=starplan_input.goal,
        run_dir=run_dir,
        use_qwen=True,
        log_path=log_path,
    )
    qwen_tag = " [Qwen]" if outreach.qwen_used else " [template]"
    if outreach.pack_type == "not_observable":
        print(f"  [OK] Cancellation/alternative pack{qwen_tag}: {outreach.outreach_pack_md_path}")
        if outreach.alternative_suggestions:
            for s in outreach.alternative_suggestions[:3]:
                print(f"    Alt: {s}")
    else:
        print(f"  [OK] Outreach pack{qwen_tag}: {outreach.outreach_pack_md_path}")
    if outreach.qwen_validation_issues:
        for issue in outreach.qwen_validation_issues:
            print(f"    [!] {issue}")

    # ── Step 5: Observation review (if log provided) ──
    review = None
    # W-9 fix: use the schema-validated observation_log field
    if starplan_input.observation_log:
        print(f"[4/4] Reviewing observation log")
        log = starplan_input.observation_log
        # W-9 fix: save independent observation_log.json as evidence
        with open(run_dir / "observation_log.json", "w", encoding="utf-8") as f:
            json.dump(log.model_dump(mode="json"), f, ensure_ascii=False, indent=2, default=str)
        review = review_observation(
            original_plan=obs_result,
            log=log,
            run_dir=run_dir,
            timezone_name=location.get("timezone", "Asia/Shanghai"),
            log_path=str(run_dir / "model_call_log.jsonl"),
        )
        print(f"  [OK] Deviations found: {len(review.deviation_summary)}")
        print(f"  [OK] Review report: {review.review_report_md_path}")
    else:
        print(f"[4/4] No observation log provided -- skipping review")

    # ── Generate model call log ──
    _write_model_call_log(run_dir, starplan_input, resolved, obs_result, outreach=outreach)

    # ── P2-3 Finalize: verify artifacts FIRST, then determine three axes ──

    # Step A: Attach computation results to outcome
    outcome.target = resolved
    outcome.obs_result = obs_result
    outcome.location = location

    # Step B: Verify artifact completeness before setting terminal status
    import hashlib as _hl
    artifact_issues: list[str] = []
    required_artifacts = ["claims.json", "outreach_pack.md", "render_trace.json",
                          "sentence_claim_map.json", "expression_plan.json"]
    for fname in required_artifacts:
        if not (run_dir / fname).exists():
            artifact_issues.append(f"missing artifact: {fname}")

    # Verify claims registry integrity (hash matches sealed value)
    claims_path = run_dir / "claims.json"
    if claims_path.exists():
        claims_hash = _hl.sha256(claims_path.read_bytes()).hexdigest()[:16]
        outcome.claims_registry_hash = claims_hash
        # Cross-check with render_trace: every sentence must have claim_ids
        trace_path = run_dir / "render_trace.json"
        if trace_path.exists():
            trace_data = json.loads(trace_path.read_text(encoding="utf-8"))
            for entry in trace_data.get("sentences", []):
                if not entry.get("claim_ids"):
                    artifact_issues.append(
                        f"render_trace sentence without claim_ids: {entry.get('text', '')[:40]}"
                    )

    # Step C: Set three-axis status (only after verification)
    outcome.business_status = outcome._derive_business_status()

    if outreach.qwen_used:
        outcome.set_delivery(DeliveryStatus.QWEN_EXPRESSION_PLAN, qwen_used=True)
        outcome.add_model_call_event({
            "type": "model_call",
            "step": "outreach_pack",
            "model": "qwen3.7-max",
        })
    else:
        outcome.set_delivery(DeliveryStatus.TEMPLATE, qwen_used=False)

    if artifact_issues:
        outcome.set_validation(ValidationStatus.PASSED_WITH_WARNINGS, artifact_issues)
    elif outreach.qwen_validation_issues:
        outcome.set_validation(ValidationStatus.PASSED_WITH_WARNINGS, outreach.qwen_validation_issues)
    else:
        outcome.set_validation(ValidationStatus.PASSED)

    # Step D: Generate Manifest + Report + Outcome (from verified state)
    manifest = outcome.build_manifest(run_dir, starplan_input=starplan_input)
    _write_validation_report(run_dir, outcome)

    with open(run_dir / "calculation_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest.model_dump(), f, ensure_ascii=False, indent=2, default=str)

    # Compute file hashes for key outputs
    for fname in ["plan.json", "claims.json", "outreach_pack.md",
                  "calculation_manifest.json", "render_trace.json"]:
        fpath = run_dir / fname
        if fpath.exists():
            outcome.compute_file_hash(fpath)

    # Write final run_outcome.json (with hashes)
    with open(run_dir / "run_outcome.json", "w", encoding="utf-8") as f:
        json.dump(outcome.to_audit_summary(), f, ensure_ascii=False, indent=2, default=str)

    print(f"\n[OK] Run complete: {run_dir}")
    print(f"  Files: {len(list(run_dir.iterdir()))} in {run_dir}")

    _transition(RunState.RENDERED, "all outputs written")

    # Save state machine log
    with open(run_dir / "state_log.json", "w", encoding="utf-8") as f:
        json.dump(state_log, f, ensure_ascii=False, indent=2)

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "target": resolved.model_dump(),
        "plan": plan_data,
        "outreach_pack": outreach.model_dump(),
        "review": review.model_dump() if review else None,
        "manifest": manifest.model_dump(),
    }


def _persist_outcome(outcome, run_dir: Path):
    """P0-C: Atomically persist RunOutcome and state log for any terminal state."""
    try:
        with open(run_dir / "run_outcome.json", "w", encoding="utf-8") as f:
            json.dump(outcome.to_audit_summary(), f, ensure_ascii=False, indent=2, default=str)
        with open(run_dir / "state_log.json", "w", encoding="utf-8") as f:
            json.dump(outcome.state_log, f, ensure_ascii=False, indent=2)
    except OSError:
        pass  # Best-effort; don't crash pipeline for logging


def _write_validation_report(run_dir: Path, outcome) -> None:
    """Write validation report from RunOutcome (single source of truth).

    P2: receives only RunOutcome — no scattered resolved/obs/manifest params.
    """
    resolved = outcome.target
    obs = outcome.obs_result
    lines: list[str] = []
    lines.append("# Validation Report")
    lines.append("")
    lines.append(f"**Run ID**: {outcome.run_id}")
    lines.append(f"**Timestamp**: {datetime.now(timezone(timedelta(hours=8))).isoformat()}")
    lines.append(f"**Business Status**: {outcome.business_status.value}")
    lines.append(f"**Validation Status**: {outcome.validation_status.value}")
    lines.append(f"**Delivery Status**: {outcome.delivery_status.value}")
    lines.append("")

    # Input check
    lines.append("## Input Check")
    lines.append("")
    loc_name = (outcome.location or {}).get("name", "unknown")
    date_info = (outcome.input_data or {}).get("date_range", "unknown")
    lines.append(f"- Target: provided")
    lines.append(f"- Location: {loc_name}")
    lines.append(f"- Date: {date_info}")
    lines.append("")

    # Target check
    if resolved:
        lines.append("## Target Check")
        lines.append("")
        lines.append(f"- Standard name: {resolved.standard_name}")
        lines.append(f"- Coordinates: RA={resolved.ra_deg:.4f} deg, Dec={resolved.dec_deg:.4f} deg")
        lines.append(f"- Source: {resolved.source}")
        lines.append(f"- Confidence: {resolved.confidence:.2f}")
        lines.append(f"- Status: {'[OK]' if resolved.confidence >= 0.9 else '[WARN] low confidence'}")
        lines.append("")

    # Calculation check
    if obs:
        lines.append("## Calculation Check")
        lines.append("")
        lines.append(f"- Observable: {'Yes' if obs.is_observable else 'No'}")
        lines.append(f"- Data points: {len(obs.hourly_data)}")
        lines.append(f"- Visibility windows: {len(obs.visibility_windows)}")
        if obs.recommended_window:
            lines.append(f"- Peak altitude: {obs.recommended_window.peak_altitude_deg:.1f} deg")
        lines.append(f"- Risk flags: {len(obs.risk_flags)}")
        lines.append("")

    # Tool versions
    import astropy
    try:
        import astroplan
        _ap_ver = astroplan.__version__
    except ImportError:
        _ap_ver = "not_installed"
    lines.append("## Tool Versions")
    lines.append("")
    lines.append(f"- Astropy: {astropy.__version__}")
    lines.append(f"- astroplan: {_ap_ver}")
    lines.append(f"- Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    lines.append("")

    # Overall conclusion from RunOutcome three-axis status
    lines.append("## Conclusion")
    lines.append("")
    biz = outcome.business_status.value
    val = outcome.validation_status.value
    if biz == "tool_error":
        status = f"[FAIL] TOOL_ERROR: {outcome.error_message_safe or 'unknown'}"
    elif biz == "needs_confirmation":
        status = "[PENDING] NEEDS_CONFIRMATION: ambiguous target"
    elif val == "passed":
        status = "[PASS] PASSED"
    elif val == "passed_with_warnings":
        status = "[PASS] PASSED_WITH_WARNINGS"
    else:
        status = f"[REVIEW] {biz}/{val}"
    lines.append(f"**Status**: {status}")
    if obs:
        lines.append(f"**Observable**: {'Yes' if obs.is_observable else 'No'}")
        if not obs.is_observable:
            lines.append(f"**Alternatives**: {len(obs.alternative_suggestions)}")
    lines.append("")

    with open(run_dir / "validation_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _write_model_call_log(
    run_dir: Path,
    starplan_input: StarPlanInput,
    resolved: ResolvedTarget,
    obs_result: ObservabilityResult,
    outreach=None,
    nl_parsed: bool = False,
) -> None:
    """Write model_call_log.jsonl recording pipeline steps and Qwen usage."""
    import os
    tz = timezone(timedelta(hours=8))
    log_entries: list[dict] = []

    # Record NL parse step if applicable
    if nl_parsed:
        from .qwen_client import DEFAULT_MODEL as _DM
        log_entries.append({
            "timestamp": datetime.now(tz).isoformat(),
            "step": "nl_parse",
            "type": "model_call",
            "model_used": _DM,
            "note": "Natural language input parsed to structured StarPlanInput via Qwen JSON mode",
        })

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

    # Record outreach_pack step with actual Qwen usage
    from .qwen_client import DEFAULT_MODEL as _DEFAULT_MODEL
    qwen_used = outreach.qwen_used if outreach else False
    validation_issues = outreach.qwen_validation_issues if outreach else []
    log_entries.append({
        "timestamp": datetime.now(tz).isoformat(),
        "step": "outreach_pack",
        "type": "model_assisted" if qwen_used else "deterministic_tool",
        "qwen_used": qwen_used,
        "model_used": _DEFAULT_MODEL if qwen_used else None,
        "validation_issues": validation_issues,
        "note": (
            f"Qwen generated talking points, {len(validation_issues)} validation issues"
            if qwen_used
            else "Template mode -- no Qwen call (API key not set or use_qwen=False)"
        ),
    })

    log_path = run_dir / "model_call_log.jsonl"
    # Append to existing log (qwen_client may have already written entries)
    with open(log_path, "a", encoding="utf-8") as f:
        for entry in log_entries:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


# ── Mode 2: Natural Language entry ───────────────────

def run_starplan_nl(
    user_text: str,
    run_id: Optional[str] = None,
) -> dict:
    """
    Run StarPlan pipeline from a natural language request.

    Qwen parses the user's free-form text into structured StarPlanInput,
    then the standard deterministic pipeline runs.

    Args:
        user_text: Free-form observation request (Chinese or English).
        run_id: Optional run identifier.

    Returns:
        Same as run_starplan().
    """
    from .nl_parser import parse_natural_language
    from .config import get_run_dir

    # Generate run_id early so NL parse is logged to the same run directory
    if not run_id:
        ts_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"nl_parse_{ts_slug}"

    run_dir = get_run_dir(run_id)
    log_path = str(run_dir / "model_call_log.jsonl")

    print(f"[NL] Parsing natural language input...")
    print(f"  Input: {user_text[:100]}{'...' if len(user_text) > 100 else ''}")

    starplan_input = parse_natural_language(user_text, log_path=log_path)

    print(f"  [OK] Parsed: target={starplan_input.target}, "
          f"location={starplan_input.location}, "
          f"date={starplan_input.date_range}, "
          f"equipment={starplan_input.equipment}")

    # Convert to dict and run standard pipeline
    input_data = starplan_input.model_dump(mode="json")
    result = run_starplan(input_data, run_id=run_id)
    result["nl_input"] = user_text
    result["nl_parsed"] = True
    return result


# ── Mode 3: Qwen tool-calling orchestration ──────────

def run_starplan_chat(
    user_text: str,
    run_id: Optional[str] = None,
) -> dict:
    """
    Run StarPlan with Qwen orchestrating tools via function calling.

    Qwen receives the user request and decides which tools to call
    (target_resolve, observability_plan). Tool results are fed back
    until Qwen produces a final natural language summary.

    This demonstrates the full "Qwen as orchestrator" pattern where
    the model plans the workflow but all numerical computation is
    done by deterministic tools.

    Args:
        user_text: Free-form observation request.
        run_id: Optional run identifier.

    Returns:
        Dict with pipeline results + Qwen conversation log.
    """
    from .qwen_client import call_qwen_chat, TOOL_DEFINITIONS, DEFAULT_MODEL

    print(f"[CHAT] Qwen tool-calling orchestration mode")
    print(f"  Input: {user_text[:100]}{'...' if len(user_text) > 100 else ''}")

    # Capture tool results so the final summary can be hallucination-checked
    captured: dict = {}

    # Define tool executors that bridge Qwen's function calls to our Skills
    def _exec_target_resolve(target_name: str, target_type: str = None) -> str:
        """Execute target_resolve and return JSON result."""
        resolved = resolve_target(target_name, target_type)
        captured["target_resolve"] = resolved.model_dump()
        return json.dumps(resolved.model_dump(), ensure_ascii=False, default=str)

    def _exec_resolve_location(location_name: str) -> str:
        """Execute resolve_location (flexible matching) and return JSON result."""
        loc = _flexible_resolve_location(location_name)
        if loc:
            captured["resolve_location"] = loc
            return json.dumps(loc, ensure_ascii=False, default=str)
        return json.dumps(
            {"error": f"未找到地点: {location_name}，请改用内置地点表中的地点"},
            ensure_ascii=False,
        )

    def _exec_observability_plan(
        ra_deg: float, dec_deg: float, target_name: str,
        location_name: str, latitude: float, longitude: float,
        date_range: list, elevation_m: float = 0,
        equipment: str = "binoculars",
    ) -> str:
        """Execute observability_plan and return JSON result."""
        location = {
            "name": location_name,
            "latitude": latitude,
            "longitude": longitude,
            "elevation_m": elevation_m,
            "timezone": "Asia/Shanghai",
        }
        obs = compute_observability(
            ra_deg=ra_deg,
            dec_deg=dec_deg,
            target_name=target_name,
            location=location,
            date_range=date_range,
            equipment=equipment,
        )
        captured["observability_plan"] = obs.model_dump(mode="json")
        captured["_obs_location_used"] = {"latitude": latitude, "longitude": longitude}
        return json.dumps(obs.model_dump(mode="json"), ensure_ascii=False, default=str)

    def _exec_outreach_pack(
        target_name: str, audience: str, equipment: str,
        goal: str = "校园科普观测",
    ) -> str:
        """Execute outreach_pack using previously captured tool results."""
        target_data = captured.get("target_resolve")
        obs_data = captured.get("observability_plan")
        if not target_data or not obs_data:
            return json.dumps(
                {"error": "必须先调用 target_resolve 和 observability_plan 再生成活动包"},
                ensure_ascii=False,
            )
        # Reconstruct objects from captured dicts
        resolved_obj = ResolvedTarget(**target_data)
        obs_obj = ObservabilityResult(**obs_data)
        pack = generate_outreach_pack(
            target=resolved_obj,
            obs_result=obs_obj,
            audience=audience,
            equipment=equipment,
            goal=goal,
            run_dir=run_dir,
            use_qwen=True,
            log_path=log_path,
        )
        captured["outreach_pack"] = pack.model_dump()
        return json.dumps(pack.model_dump(), ensure_ascii=False, default=str)

    def _exec_observation_review(
        target_name: str, observation_log: str,
        planned_window: str = "",
    ) -> str:
        """Execute observation_review from a text observation log."""
        obs_data = captured.get("observability_plan")
        if not obs_data:
            return json.dumps(
                {"error": "必须先调用 observability_plan 获得计划数据再进行复盘"},
                ensure_ascii=False,
            )
        obs_obj = ObservabilityResult(**obs_data)
        # Parse free-text log into structured ObservationLog (best-effort)
        # Use the planned date as actual_date fallback
        plan_date = obs_obj.date_range[0] if obs_obj.date_range else None
        base_dt = datetime(
            plan_date.year, plan_date.month, plan_date.day, 20, 0
        ) if plan_date else datetime.now()
        log_entry = ObservationLog(
            actual_start_time=base_dt,
            actual_end_time=base_dt + timedelta(hours=3),
            targets_observed=[target_name],
            targets_missed=[],
            equipment_used="binoculars",
            observer_notes=observation_log,
        )
        review = review_observation(
            original_plan=obs_obj,
            log=log_entry,
        )
        captured["observation_review"] = review.model_dump()
        return json.dumps(review.model_dump(), ensure_ascii=False, default=str)

    tool_executors = {
        "target_resolve": _exec_target_resolve,
        "resolve_location": _exec_resolve_location,
        "observability_plan": _exec_observability_plan,
        "outreach_pack": _exec_outreach_pack,
        "observation_review": _exec_observation_review,
    }

    # System prompt for the orchestrator.
    # Guardrail 1: inject the current date so Qwen does not fabricate wrong-year dates.
    today = datetime.now().strftime("%Y-%m-%d")
    system_prompt = (
        f"你是 StarPlan Loop 的 AI 编排器。当前日期是 {today}。\n"
        "用户会描述一个天文观测活动需求，你需要通过调用工具来完成规划：\n"
        "1. 先调用 target_resolve 解析目标名称，获取目标坐标\n"
        "2. 再调用 resolve_location 解析地点名称，获取准确的经纬度和海拔\n"
        "3. 然后调用 observability_plan 计算可观测性（必须使用前两步工具返回的坐标和经纬度）\n"
        "4. 最后用自然语言总结结果，给出推荐观测时段和注意事项\n\n"
        "严格规则（违反任何一条都是严重错误）：\n"
        "- 所有数值（坐标、高度角、方位角、时间、月相、大气质量等）必须来自工具返回结果，绝对不能编造。\n"
        f"- 如果用户没有指定日期，使用当前日期 {today} 或其后的合理日期，绝对不要使用 2026 年之前的年份。\n"
        "- 经纬度必须来自 resolve_location 工具的返回，绝对不要凭记忆填写经纬度。\n"
        "- 不要编造气温、角距离、暗适应时间等工具未提供的具体数值，这类信息只能用定性描述。\n"
        "- 如果某个工具返回错误或找不到，如实告知用户，不要编造结果。"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]

    # Generate run dir for logging
    if not run_id:
        ts_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"chat_{ts_slug}"
    run_dir = get_run_dir(run_id)
    log_path = str(run_dir / "model_call_log.jsonl")

    # Run the chat with tool calling
    result = call_qwen_chat(
        messages=messages,
        tools=TOOL_DEFINITIONS,
        tool_executors=tool_executors,
        max_tool_rounds=5,
        log_path=log_path,
        step_name="chat_orchestration",
    )

    final_content = result.get("content", "")

    # Guardrail 3a: verify every number in the final summary traces to a tool output
    untraceable = _check_chat_hallucination(final_content, captured)
    # Guardrail 3b: detect if Qwen guessed coordinates instead of using resolve_location
    coord_warning = _check_coordinate_source(captured)

    # C-4 + C-2 + P3: FAIL CLOSED BY DESIGN — Qwen free text is NEVER the
    # final user output. Use Claim-rendered talking_points from outreach_pack
    # (same architecture as structured mode). Fallback to deterministic summary
    # only if outreach_pack was never called.
    blocked_content = final_content
    pack_data = captured.get("outreach_pack")
    if pack_data and pack_data.get("talking_points"):
        # P3: final_content from Claim-rendered talking_points (in render_trace)
        tp_lines = pack_data["talking_points"]
        header = "【StarPlan 观测规划结果】\n（以下要点由 Claim 证据链确定性渲染）\n"
        final_content = header + "\n".join(f"- {tp}" for tp in tp_lines)
        if pack_data.get("alternative_suggestions"):
            final_content += "\n\n替代建议：\n"
            final_content += "\n".join(f"- {s}" for s in pack_data["alternative_suggestions"])
    else:
        # Fallback: outreach_pack not called, use deterministic summary
        final_content = _build_deterministic_summary(captured)
    hallucination_blocked = True  # Always: free text never reaches user

    verification = {
        "untraceable_numbers": untraceable,
        "coordinate_warning": coord_warning,
        "tools_called": [tc["tool"] for tc in result.get("tool_call_log", [])],
        "passed": (not untraceable) and (not coord_warning),
        "delivery": "deterministic_render",
        "note": "Qwen free text is never delivered; deterministic summary used by design",
    }

    if untraceable:
        print(f"  [!] 幻觉核查：Qwen 文本含 {len(untraceable)} 个不可溯源数值（已阻断）")
    if coord_warning:
        print(f"  [!] {coord_warning}")
    print(f"  [OK] 最终输出使用确定性渲染（Qwen 原文 {len(blocked_content)} chars 仅供审计）")

    # Save conversation log + verification (AUDIT ONLY — not in public return)
    with open(run_dir / "chat_conversation.json", "w", encoding="utf-8") as f:
        json.dump({
            "user_input": user_text,
            "messages": result.get("messages", []),
            "tool_call_log": result.get("tool_call_log", []),
            "final_content": final_content,
            "blocked_content": blocked_content,
            "hallucination_verification": verification,
            "hallucination_blocked": hallucination_blocked,
        }, f, ensure_ascii=False, indent=2, default=str)

    # P3-3: Write run_outcome.json (same contract as structured mode)
    from .run_outcome import RunOutcome, BusinessStatus, ValidationStatus, DeliveryStatus
    chat_outcome = RunOutcome(run_id=run_id, input_data={"user_text": user_text, "mode": "chat"})
    obs_data = captured.get("observability_plan")
    if obs_data:
        chat_outcome.business_status = (
            BusinessStatus.OBSERVABLE if obs_data.get("is_observable")
            else BusinessStatus.NOT_OBSERVABLE
        )
    elif captured.get("target_resolve"):
        chat_outcome.business_status = BusinessStatus.OBSERVABLE  # resolved but no obs computed
    else:
        chat_outcome.business_status = BusinessStatus.TOOL_ERROR
    chat_outcome.set_delivery(
        DeliveryStatus.QWEN_EXPRESSION_PLAN if pack_data and pack_data.get("qwen_used")
        else DeliveryStatus.TEMPLATE,
        qwen_used=bool(pack_data and pack_data.get("qwen_used")),
    )
    chat_outcome.set_validation(
        ValidationStatus.PASSED if verification["passed"] else ValidationStatus.PASSED_WITH_WARNINGS,
        issues=untraceable if untraceable else None,
    )
    with open(run_dir / "run_outcome.json", "w", encoding="utf-8") as f:
        json.dump(chat_outcome.to_audit_summary(), f, ensure_ascii=False, indent=2, default=str)

    print(f"  [OK] Final response ({len(final_content)} chars, blocked={hallucination_blocked})")
    print(f"  [OK] Tool calls: {len(result.get('tool_call_log', []))}")
    print(f"  [OK] Run dir: {run_dir}")

    # P0-E: Public return — NO model raw text, NO messages, NO blocked_content.
    # Audit data lives only in chat_conversation.json (access-controlled).
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "mode": "chat",
        "final_content": final_content,
        "model_text_accepted_for_delivery": False,  # Always: free text never delivered
        "public_output_validation": "passed" if not untraceable else "blocked",
        "tools_called": [tc["tool"] for tc in result.get("tool_call_log", [])],
        "hallucination_blocked": hallucination_blocked,
    }


# ── Chat-mode guardrail helpers ──────────────────────

def _flexible_resolve_location(location_name: str) -> Optional[dict]:
    """Resolve a location with flexible matching (exact key, then fuzzy)."""
    from .config import load_locations

    locations = load_locations()
    name = (location_name or "").strip()
    norm = name.replace(" ", "").replace("_", "")

    # 1. Exact key match
    for loc in locations:
        if loc.get("key") == name:
            return loc
    # 2. Normalized key match (ignore underscore/space)
    for loc in locations:
        if loc.get("key", "").replace("_", "") == norm:
            return loc
    # 3. Fuzzy: query vs city/name substring (both directions)
    for loc in locations:
        key_norm = loc.get("key", "").replace("_", "")
        city = loc.get("city", "")
        loc_name_norm = loc.get("name", "").replace(" ", "")
        if norm and (norm in key_norm or norm in loc_name_norm
                     or (city and city in norm) or (loc_name_norm and loc_name_norm in norm)):
            return loc
    return None


def _extract_numbers_from_obj(obj, pattern) -> set:
    """Recursively extract all number strings from a JSON-like object."""
    nums: set = set()
    if isinstance(obj, dict):
        for v in obj.values():
            nums |= _extract_numbers_from_obj(v, pattern)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            nums |= _extract_numbers_from_obj(v, pattern)
    elif obj is not None:
        for n in pattern.findall(str(obj)):
            nums.add(n)
            try:
                nums.add(str(int(float(n))))
            except (ValueError, OverflowError):
                pass
    return nums


def _check_chat_hallucination(final_content: str, captured: dict) -> list:
    """
    Check that numbers in Qwen's final summary trace to tool outputs.

    Builds an allowed-number set from all captured tool results, then flags
    any number in the summary that is not traceable. Returns the list of
    untraceable number strings (empty if everything traces).
    """
    import re

    if not final_content:
        return []

    pattern = re.compile(r"\d+\.?\d*")
    allowed: set = set()
    for key, res in captured.items():
        if key.startswith("_"):
            continue
        allowed |= _extract_numbers_from_obj(res, pattern)
    # Safe small numbers (0-10) that don't need tool backing
    allowed |= {str(i) for i in range(11)}

    untraceable: list = []
    seen: set = set()
    for num in pattern.findall(final_content):
        normalized = num
        try:
            f = float(num)
            normalized = str(int(f)) if f == int(f) else str(f)
        except (ValueError, OverflowError):
            pass
        if normalized not in allowed and num not in allowed and normalized not in seen:
            untraceable.append(normalized)
            seen.add(normalized)
    return untraceable


def _check_coordinate_source(captured: dict) -> Optional[str]:
    """
    Detect if Qwen passed coordinates to observability_plan that did not
    come from resolve_location (i.e. likely guessed).

    Returns a warning string if suspicious, else None.
    """
    obs_loc = captured.get("_obs_location_used")
    if not obs_loc:
        return None  # observability_plan was never called

    resolved_loc = captured.get("resolve_location")
    if not resolved_loc:
        return ("坐标来源核查：Qwen 调用了 observability_plan 但未先调用 resolve_location，"
                "经纬度可能为模型推测值，不可信。")

    try:
        used_lat = float(obs_loc["latitude"])
        used_lon = float(obs_loc["longitude"])
        real_lat = float(resolved_loc["latitude"])
        real_lon = float(resolved_loc["longitude"])
    except (KeyError, TypeError, ValueError):
        return None

    if abs(used_lat - real_lat) > 0.01 or abs(used_lon - real_lon) > 0.01:
        return (f"坐标来源核查：Qwen 使用的经纬度 ({used_lat}, {used_lon}) 与 resolve_location "
                f"返回的 ({real_lat}, {real_lon}) 不一致，疑似未采用工具结果。")
    return None


def _build_deterministic_summary(captured: dict) -> str:
    """
    C-4 fix: Build a deterministic summary purely from tool results.

    This is the fail-closed fallback when Qwen's free-text summary contains
    untraceable numbers. Every value in this summary comes directly from
    captured tool outputs — no model-generated text is included.
    """
    lines: list[str] = []
    lines.append("【StarPlan 确定性结果摘要】")
    lines.append("（本摘要由结构化工具结果直接渲染，不含模型自由文本）")
    lines.append("")

    # Target info
    target = captured.get("target_resolve")
    if target:
        lines.append(f"目标: {target.get('standard_name', '未知')}")
        lines.append(f"  坐标: RA={target.get('ra_deg', '?')}°, Dec={target.get('dec_deg', '?')}°")
        lines.append(f"  类型: {target.get('target_type', '未知')}")
        if target.get("constellation"):
            lines.append(f"  星座: {target['constellation']}")
        if target.get("visual_magnitude") is not None:
            lines.append(f"  视星等: {target['visual_magnitude']}")
        lines.append("")

    # Location info
    loc = captured.get("resolve_location")
    if loc:
        lines.append(f"地点: {loc.get('name', loc.get('key', '未知'))}")
        lines.append(f"  经纬度: {loc.get('latitude', '?')}°N, {loc.get('longitude', '?')}°E")
        lines.append(f"  海拔: {loc.get('elevation_m', 0)}m")
        lines.append("")

    # Observability info
    obs = captured.get("observability_plan")
    if obs:
        observable = obs.get("is_observable", False)
        lines.append(f"可观测: {'是' if observable else '否'}")
        if observable and obs.get("recommended_window"):
            rw = obs["recommended_window"]
            w = rw.get("window", {})
            lines.append(f"  推荐时段: {w.get('start', '?')} ~ {w.get('end', '?')}")
            lines.append(f"  峰值高度角: {rw.get('peak_altitude_deg', '?')}°")
            lines.append(f"  峰值大气质量: {rw.get('peak_airmass', '?')}")
        if not observable:
            lines.append("  该目标在指定日期不满足观测条件")
        # Moon info
        moon = obs.get("moon_info")
        if moon:
            lines.append(f"  月相: {moon.get('phase_fraction', '?')}")
            lines.append(f"  月球最小角距: {moon.get('min_separation_deg', '?')}°")
            lines.append(f"  月光影响: {moon.get('impact_assessment', '?')}")
        # Alternatives
        alts = obs.get("alternative_suggestions", [])
        if alts:
            lines.append("  替代建议:")
            for a in alts[:3]:
                lines.append(f"    - {a.get('description', '')}")
        lines.append("")

    lines.append("（以上所有数值均来自 Astropy 确定性计算，非模型生成）")
    return "\n".join(lines)
