#!/usr/bin/env python3
"""StarPlan MCP server (stdio, stdlib-only) for QoderWork / Qoder / any MCP client.

This is the P2 thin adapter: it only converts MCP tool calls into the existing
StarPlan Skills/runner. It contains NO duplicated astronomy, Claim, rendering
or review logic — everything is delegated to `starplan_skills`.

Supported tools:
  - starplan.run          unified closed-loop entry (plan + pack + review + next input)
  - starplan.run_loop     first run -> next_activity_input.json -> second run
  - skill.target_resolve
  - skill.resolve_location
  - skill.observability_plan
  - skill.outreach_pack
  - skill.observation_review

Transport: MCP stdio (JSON-RPC 2.0, one message per line).
Usage:
    python scripts/starplan_mcp_server.py
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from starplan_skills.astro_runtime import configure_astronomy_runtime
from starplan_skills.runner import run_starplan

SERVER_NAME = "starplan"
SERVER_VERSION = "0.9.0"
PROTOCOL_VERSION = "2024-11-05"

configure_astronomy_runtime()


@contextlib.contextmanager
def _stdout_to_stderr():
    """Redirect runner diagnostics away from MCP's JSON-RPC stdout channel.

    The StarPlan skills/runner print progress lines to stdout (e.g.
    ``astronomy_runtime=...``, ``[1/4] Resolving target ...``).  MCP stdio
    framing allows ONLY JSON-RPC 2.0 messages on stdout; any stray text
    breaks the client.  We therefore capture those lines and forward them to
    stderr so they remain visible in server logs without corrupting the
    protocol stream.
    """
    original = sys.stdout
    buffer = io.StringIO()
    try:
        sys.stdout = buffer
        yield buffer
    finally:
        sys.stdout = original
        text = buffer.getvalue()
        if text:
            sys.stderr.write(text)
            sys.stderr.flush()


# ── Tool schemas (concise JSON Schema) ──────────────────────────

_TOOLS: list[dict[str, Any]] = [
    {
        "name": "starplan.run",
        "description": (
            "StarPlan 统一入口：目标解析→可观测性计算→现实活动时段→科普活动包"
            "（组织者/讲解员/学习者三视图、未成年人安全）→可选观测日志复盘与"
            "可执行下一轮输入。所有科学数值由确定性天文工具产生，模型不得编造。"
            "返回 run_id/run_dir/validation_status/plan/outreach_pack/review。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "input": {
                    "type": "object",
                    "description": "统一 StarPlanInput：target, location 或 location_detail, date_range, audience, equipment, goal, constraints, activity_preferences, audience_profile, observation_log",
                },
                "run_id": {"type": "string"},
            },
            "required": ["input"],
        },
    },
    {
        "name": "starplan.run_loop",
        "description": (
            "完整闭环：运行一次含 observation_log 的任务→生成 next_activity_input.json"
            "→用下一轮输入二次运行→返回 before/after 摘要（含活动时段变化与 cause_id）。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"input": {"type": "object"}},
            "required": ["input"],
        },
    },
    {
        "name": "skill.target_resolve",
        "description": "将中文名/英文名/Messier/NGC 解析为标准目标、坐标、类型与置信度；歧义时返回候选列表。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_name": {"type": "string"},
                "target_type": {"type": "string"},
            },
            "required": ["target_name"],
        },
    },
    {
        "name": "skill.resolve_location",
        "description": "将地点名称解析为内置地点表的经纬度、海拔与时区。不要凭记忆猜经纬度。",
        "inputSchema": {
            "type": "object",
            "properties": {"location_name": {"type": "string"}},
            "required": ["location_name"],
        },
    },
    {
        "name": "skill.observability_plan",
        "description": (
            "按目标坐标、地点、日期、设备计算可观测性：科学可见窗口、现实活动时段"
            "activity_slot、暮光、月光影响、风险与备选方案。数值全部由 Astropy/astroplan 确定性计算。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_name": {"type": "string"},
                "ra_deg": {"type": "number"},
                "dec_deg": {"type": "number"},
                "location": {
                    "description": "内置地点 key（如 济南_四门塔）或完整地点 dict",
                },
                "date_range": {"type": "array", "items": {"type": "string"}},
                "equipment": {"type": "string"},
                "constraints": {"type": "object"},
                "activity_preferences": {"type": "object"},
            },
            "required": ["target_name", "ra_deg", "dec_deg", "location", "date_range"],
        },
    },
    {
        "name": "skill.outreach_pack",
        "description": "从已验证目标与可观测性结果生成科普活动包（三视图 + 未成年人安全策略）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "object"},
                "obs_result": {"type": "object"},
                "audience": {"type": "string"},
                "equipment": {"type": "string"},
                "goal": {"type": "string"},
                "requested_views": {"type": "array", "items": {"type": "string"}},
                "youth_policy": {"type": "boolean"},
            },
            "required": ["target", "obs_result", "audience", "equipment"],
        },
    },
    {
        "name": "skill.observation_review",
        "description": "对比原计划与实际观测日志，输出偏差、证据归因、修订计划与可执行下一轮输入。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "original_plan": {"type": "object"},
                "observation_log": {"type": "object"},
                "original_input": {"type": "object"},
            },
            "required": ["original_plan", "observation_log"],
        },
    },
]


# ── Tool implementations (thin delegation only) ─────────────────

def _tool_target_resolve(args: dict) -> dict:
    from starplan_skills.target_resolve import resolve_target

    return resolve_target(
        args["target_name"],
        args.get("target_type"),
    ).model_dump(mode="json")


def _tool_resolve_location(args: dict) -> dict:
    from starplan_skills.target_resolve import resolve_location

    loc = resolve_location(args["location_name"])
    if loc:
        return loc
    from starplan_skills.runner import _flexible_resolve_location

    loc = _flexible_resolve_location(args["location_name"])
    if loc:
        return loc
    raise ValueError(f"未找到地点: {args['location_name']}，请使用内置地点表或提供 location_detail")


def _tool_observability_plan(args: dict) -> dict:
    from starplan_skills.observability_plan import compute_observability

    loc = args["location"]
    if isinstance(loc, str):
        resolved = _tool_resolve_location({"location_name": loc})
    elif isinstance(loc, dict):
        resolved = loc
    else:
        raise ValueError("location 必须是内置地点 key 或地点 dict")
    result = compute_observability(
        ra_deg=args["ra_deg"],
        dec_deg=args["dec_deg"],
        target_name=args["target_name"],
        location=resolved,
        date_range=args["date_range"],
        equipment=args.get("equipment"),
        constraints=args.get("constraints"),
        activity_preferences=args.get("activity_preferences"),
    )
    return result.model_dump(mode="json")


def _tool_outreach_pack(args: dict) -> dict:
    from starplan_skills.outreach_pack import generate_outreach_pack
    from starplan_skills.schemas import ObservabilityResult, ResolvedTarget

    run_dir = PROJECT_ROOT / "runs" / f"mcp_outreach_{int(time.time())}"
    run_dir.mkdir(parents=True, exist_ok=True)
    pack = generate_outreach_pack(
        target=ResolvedTarget(**args["target"]),
        obs_result=ObservabilityResult(**args["obs_result"]),
        audience=args["audience"],
        equipment=args["equipment"],
        goal=args.get("goal", "校园科普观测"),
        run_dir=run_dir,
        requested_views=args.get("requested_views"),
        youth_policy=args.get("youth_policy"),
    )
    data = pack.model_dump()
    data["run_dir"] = str(run_dir)
    return data


def _tool_observation_review(args: dict) -> dict:
    from starplan_skills.observation_review import review_observation
    from starplan_skills.schemas import ObservationLog, ObservabilityResult

    run_dir = PROJECT_ROOT / "runs" / f"mcp_review_{int(time.time())}"
    run_dir.mkdir(parents=True, exist_ok=True)
    review = review_observation(
        original_plan=ObservabilityResult(**args["original_plan"]),
        log=ObservationLog(**args["observation_log"]),
        run_dir=run_dir,
        original_input=args.get("original_input"),
    )
    data = review.model_dump()
    data["run_dir"] = str(run_dir)
    return data


def _run_loop_summary(input_data: dict) -> dict:
    """First run -> next input -> second run (no implicit recursion in runner)."""
    first = run_starplan(input_data)
    review = first.get("review") or {}
    next_path = review.get("next_input_path")
    second = None
    if next_path and Path(next_path).exists():
        with open(next_path, "r", encoding="utf-8") as f:
            next_input = json.load(f)
        second = run_starplan(next_input, run_id=f"{first['run_id']}_next")
    return {
        "first_run_id": first["run_id"],
        "first_validation": first.get("validation_status"),
        "next_input_path": next_path,
        "second_run_id": second["run_id"] if second else None,
        "second_validation": second.get("validation_status") if second else None,
        "revised_plan_diff": review.get("revised_plan_diff", []),
        "activity_slot_before": (first.get("plan") or {}).get("activity_slot"),
        "activity_slot_after": (second.get("plan") or {}).get("activity_slot") if second else None,
    }


def _call_tool(name: str, args: dict) -> dict:
    # Every delegated skill/runner call may print progress to stdout; keep
    # the MCP protocol channel clean (diagnostics go to stderr instead).
    with _stdout_to_stderr():
        if name == "starplan.run":
            result = run_starplan(args.get("input") or {}, args.get("run_id"))
            plan = result.get("plan") or {}
            outreach = result.get("outreach_pack")
            review = result.get("review")
            return {
                "run_id": result["run_id"],
                "run_dir": result["run_dir"],
                "validation_status": result.get("validation_status"),
                "delivery_status": result.get("delivery_status"),
                "plan_summary": {
                    "is_observable": plan.get("is_observable"),
                    "recommended_window": plan.get("recommended_window"),
                    "activity_slot": plan.get("activity_slot"),
                    "not_observable_reason": plan.get("not_observable_reason"),
                    "alternative_suggestions": plan.get("alternative_suggestions"),
                },
                "outreach_pack": {
                    "talking_points": (outreach or {}).get("talking_points"),
                    "rendered_views": (outreach or {}).get("rendered_views"),
                    "youth_policy_applied": (outreach or {}).get("youth_policy_applied"),
                    "qwen_used": (outreach or {}).get("qwen_used"),
                    "activity_schedule": (outreach or {}).get("activity_schedule"),
                    "safety_notes": (outreach or {}).get("safety_notes"),
                    "manual_check_items": (outreach or {}).get("manual_check_items"),
                },
                "review": {
                    "deviation_summary": (review or {}).get("deviation_summary"),
                    "cause_classification": (review or {}).get("cause_classification"),
                    "revised_plan_diff": (review or {}).get("revised_plan_diff"),
                    "next_input_path": (review or {}).get("next_input_path"),
                } if review else None,
            }
        if name == "starplan.run_loop":
            return _run_loop_summary(args.get("input") or {})
        if name == "skill.target_resolve":
            return _tool_target_resolve(args)
        if name == "skill.resolve_location":
            return _tool_resolve_location(args)
        if name == "skill.observability_plan":
            return _tool_observability_plan(args)
        if name == "skill.outreach_pack":
            return _tool_outreach_pack(args)
        if name == "skill.observation_review":
            return _tool_observation_review(args)
        raise ValueError(f"Unknown tool: {name}")


# ── JSON-RPC 2.0 / MCP stdio loop ──────────────────────────────

def _rpc_error(code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": None, "error": {"code": code, "message": message}}


def _handle(msg: dict) -> Optional[dict]:
    method = msg.get("method")
    msg_id = msg.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": _TOOLS}}
    if method == "resources/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"resources": []}}
    if method == "resources/templates/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"resourceTemplates": []}}
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name", "")
        arguments = params.get("arguments") or {}
        try:
            result = _call_tool(name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2, default=str)}
                    ],
                    "isError": False,
                },
            }
        except Exception as exc:  # fail-closed: return structured error text
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {"error": str(exc)[:500], "error_type": type(exc).__name__},
                                ensure_ascii=False,
                            ),
                        }
                    ],
                    "isError": True,
                },
            }
    if msg_id is None:
        return None
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps(_rpc_error(-32700, "Parse error")) + "\n")
            sys.stdout.flush()
            continue
        try:
            response = _handle(msg)
        except Exception as exc:  # defensive; never crash the server
            response = {
                "jsonrpc": "2.0",
                "id": msg.get("id"),
                "error": {"code": -32603, "message": f"Internal error: {exc}"},
            }
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
