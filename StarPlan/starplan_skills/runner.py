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
    print(f"  [OK] Outreach pack{qwen_tag}: {outreach.outreach_pack_md_path}")
    if outreach.qwen_validation_issues:
        for issue in outreach.qwen_validation_issues:
            print(f"    [!] {issue}")

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
    _write_model_call_log(run_dir, starplan_input, resolved, obs_result, outreach=outreach)

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
    outreach=None,
    nl_parsed: bool = False,
) -> None:
    """Write model_call_log.jsonl recording pipeline steps and Qwen usage."""
    import os
    tz = timezone(timedelta(hours=8))
    log_entries: list[dict] = []

    # Record NL parse step if applicable
    if nl_parsed:
        log_entries.append({
            "timestamp": datetime.now(tz).isoformat(),
            "step": "nl_parse",
            "type": "model_call",
            "model_used": "Qwen3.7-Max",
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
    qwen_used = outreach.qwen_used if outreach else False
    validation_issues = outreach.qwen_validation_issues if outreach else []
    log_entries.append({
        "timestamp": datetime.now(tz).isoformat(),
        "step": "outreach_pack",
        "type": "model_assisted" if qwen_used else "deterministic_tool",
        "qwen_used": qwen_used,
        "model_used": "Qwen3.7-Max" if qwen_used else None,
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

    print(f"[NL] Parsing natural language input...")
    print(f"  Input: {user_text[:100]}{'...' if len(user_text) > 100 else ''}")

    starplan_input = parse_natural_language(user_text)

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

    tool_executors = {
        "target_resolve": _exec_target_resolve,
        "resolve_location": _exec_resolve_location,
        "observability_plan": _exec_observability_plan,
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

    verification = {
        "untraceable_numbers": untraceable,
        "coordinate_warning": coord_warning,
        "tools_called": [tc["tool"] for tc in result.get("tool_call_log", [])],
        "passed": (not untraceable) and (not coord_warning),
    }

    if untraceable:
        print(f"  [!] 幻觉核查：发现 {len(untraceable)} 个无法溯源到工具输出的数值: {untraceable[:10]}")
    else:
        print(f"  [OK] 幻觉核查：最终总结中的数值均可溯源到工具输出")
    if coord_warning:
        print(f"  [!] {coord_warning}")
    else:
        print(f"  [OK] 坐标来源核查：经纬度来自 resolve_location 工具")

    # Save conversation log + verification
    with open(run_dir / "chat_conversation.json", "w", encoding="utf-8") as f:
        json.dump({
            "user_input": user_text,
            "messages": result.get("messages", []),
            "tool_call_log": result.get("tool_call_log", []),
            "final_content": final_content,
            "hallucination_verification": verification,
        }, f, ensure_ascii=False, indent=2, default=str)

    print(f"  [OK] Qwen final response ({len(final_content)} chars)")
    print(f"  [OK] Tool calls: {len(result.get('tool_call_log', []))}")
    print(f"  [OK] Run dir: {run_dir}")

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "mode": "chat",
        "final_content": final_content,
        "tool_call_log": result.get("tool_call_log", []),
        "messages": result.get("messages", []),
        "hallucination_verification": verification,
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
