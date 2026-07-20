"""
StarPlan Loop - Qwen client (Week 3: full implementation).

Provides:
  - call_qwen: single-turn API call with optional tools
  - call_qwen_chat: multi-turn conversation with automatic tool-call loop
  - call_qwen_json: structured JSON output mode
  - Tool definitions for StarPlan Skills (function calling schema)

All calls are logged to model_call_log.jsonl for auditability.
Qwen is used ONLY for natural language understanding, orchestration,
and outreach expression. It NEVER generates astronomical numerical values.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Optional

from dotenv import load_dotenv

load_dotenv()

# ── Model configuration ──────────────────────────────

QWEN_MODELS = {
    "max_preview": "qwen3.8-max-preview",
    "max": "qwen3.7-max",
    "plus": "qwen3.7-plus",
}
DEFAULT_MODEL = QWEN_MODELS["max"]

# ── Tool definitions for function calling ────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "target_resolve",
            "description": (
                "将用户输入的天体名称（中文、英文、Messier 编号、NGC 编号或别名）"
                "解析为标准天文目标，返回标准名称、坐标、类型和置信度。"
                "当名称有歧义时返回候选列表。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_name": {
                        "type": "string",
                        "description": "目标名称，如 'M31'、'仙女座星系'、'Andromeda Galaxy'",
                    },
                    "target_type": {
                        "type": "string",
                        "enum": ["deep_sky", "star", "planet", "asterism"],
                        "description": "可选的目标类型提示，用于消歧",
                    },
                },
                "required": ["target_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "observability_plan",
            "description": (
                "根据目标坐标、观测地点、日期和设备约束，计算目标的可观测性。"
                "返回可见窗口、高度角/方位角/大气质量数据、暮光时间、月光影响、"
                "推荐观测时段（含理由）和备选方案。"
                "所有数值由 Astropy/astroplan 确定性计算，不由模型生成。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ra_deg": {"type": "number", "description": "赤经（度，J2000）"},
                    "dec_deg": {"type": "number", "description": "赤纬（度，J2000）"},
                    "target_name": {"type": "string", "description": "标准目标名称"},
                    "location_name": {"type": "string", "description": "地点名称"},
                    "latitude": {"type": "number", "description": "纬度（度）"},
                    "longitude": {"type": "number", "description": "经度（度）"},
                    "elevation_m": {"type": "number", "description": "海拔（米）"},
                    "date_range": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "日期范围 [开始, 结束]，格式 YYYY-MM-DD",
                    },
                    "equipment": {
                        "type": "string",
                        "enum": ["naked_eye", "binoculars", "small_telescope", "large_telescope"],
                        "description": "设备类型",
                    },
                },
                "required": ["ra_deg", "dec_deg", "target_name", "location_name",
                             "latitude", "longitude", "date_range"],
            },
        },
    },
]


# ── Core API functions ───────────────────────────────

def call_qwen(
    prompt: str,
    model: str = DEFAULT_MODEL,
    system_prompt: Optional[str] = None,
    tools: Optional[list[dict]] = None,
    log_path: Optional[str] = None,
    step_name: str = "qwen_call",
) -> dict:
    """
    Single-turn Qwen API call.

    Args:
        prompt: User prompt.
        model: Model identifier.
        system_prompt: Optional system prompt.
        tools: Optional tool definitions for function calling.
        log_path: Path to append call log entry.
        step_name: Pipeline step name for logging.

    Returns:
        Dict with content, model, tool_calls, finish_reason.
    """
    _check_api_key()

    from dashscope import Generation

    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "result_format": "message",
    }
    if tools:
        kwargs["tools"] = tools

    response = Generation.call(**kwargs)
    result = _parse_response(response, model)

    if log_path:
        _log_call(log_path, step_name, prompt, result, model)

    return result


def call_qwen_json(
    prompt: str,
    model: str = DEFAULT_MODEL,
    system_prompt: Optional[str] = None,
    log_path: Optional[str] = None,
    step_name: str = "qwen_json",
) -> dict:
    """
    Call Qwen with JSON output mode for structured data extraction.

    The model is instructed to return valid JSON only.
    """
    _check_api_key()

    from dashscope import Generation

    json_system = (
        "你必须且只能返回合法的 JSON 对象，不要输出任何 JSON 之外的文字、"
        "解释或 markdown 代码块标记。"
    )
    if system_prompt:
        json_system = system_prompt + "\n\n" + json_system

    messages = [
        {"role": "system", "content": json_system},
        {"role": "user", "content": prompt},
    ]

    response = Generation.call(
        model=model,
        messages=messages,
        result_format="message",
    )
    result = _parse_response(response, model)

    # Parse JSON from content
    content = result.get("content", "")
    # Strip markdown code fences if present
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        result["parsed_json"] = json.loads(content)
    except json.JSONDecodeError:
        result["parsed_json"] = None
        result["json_error"] = f"Failed to parse JSON from response: {content[:200]}"

    if log_path:
        _log_call(log_path, step_name, prompt, result, model)

    return result


def call_qwen_chat(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    tools: Optional[list[dict]] = None,
    tool_executors: Optional[dict[str, Callable]] = None,
    max_tool_rounds: int = 5,
    log_path: Optional[str] = None,
    step_name: str = "qwen_chat",
) -> dict:
    """
    Multi-turn conversation with automatic tool-call execution loop.

    When the model returns tool_calls, this function:
      1. Executes each tool via tool_executors[name](**args)
      2. Appends tool results to messages
      3. Calls the model again
      4. Repeats until the model returns a final text response or max rounds reached

    Args:
        messages: Conversation messages (system + user + assistant + tool).
        model: Model identifier.
        tools: Tool definitions.
        tool_executors: Map of tool name -> callable(**kwargs) -> str.
        max_tool_rounds: Maximum tool-call round-trips.
        log_path: Path for call logging.
        step_name: Pipeline step name.

    Returns:
        Dict with final content, full message history, and tool call log.
    """
    _check_api_key()

    from dashscope import Generation

    tool_call_log: list[dict] = []
    tz = timezone(timedelta(hours=8))

    for round_idx in range(max_tool_rounds):
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "result_format": "message",
        }
        if tools:
            kwargs["tools"] = tools

        response = Generation.call(**kwargs)
        result = _parse_response(response, model)

        if log_path:
            _log_call(log_path, f"{step_name}_round{round_idx}", 
                      str(messages[-1].get("content", ""))[:200], result, model)

        # If no tool calls, we're done
        if not result.get("tool_calls"):
            result["tool_call_log"] = tool_call_log
            result["messages"] = messages
            return result

        # Execute tool calls
        assistant_msg = {
            "role": "assistant",
            "content": result.get("content", ""),
            "tool_calls": result["tool_calls"],
        }
        messages.append(assistant_msg)

        for tc in result["tool_calls"]:
            func_name = tc["function"]["name"]
            try:
                func_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                func_args = {}

            tool_result_str = ""
            if tool_executors and func_name in tool_executors:
                try:
                    tool_result_str = tool_executors[func_name](**func_args)
                except Exception as e:
                    tool_result_str = json.dumps({"error": str(e)}, ensure_ascii=False)
            else:
                tool_result_str = json.dumps(
                    {"error": f"Unknown tool: {func_name}"}, ensure_ascii=False
                )

            tool_call_log.append({
                "timestamp": datetime.now(tz).isoformat(),
                "round": round_idx,
                "tool": func_name,
                "arguments": func_args,
                "result_preview": tool_result_str[:500],
            })

            messages.append({
                "role": "tool",
                "content": tool_result_str,
                "name": func_name,
            })

    # Max rounds reached
    return {
        "content": "[达到最大工具调用轮次]",
        "model": model,
        "tool_calls": None,
        "finish_reason": "max_rounds",
        "tool_call_log": tool_call_log,
        "messages": messages,
    }


# ── Helpers ──────────────────────────────────────────

def _check_api_key() -> None:
    """Verify DASHSCOPE_API_KEY is set."""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        raise RuntimeError(
            "DASHSCOPE_API_KEY not set. "
            "Copy .env.example to .env and fill in your key."
        )


def _parse_response(response: Any, model: str) -> dict:
    """Parse a DashScope Generation response into a standard dict."""
    result: dict[str, Any] = {
        "content": "",
        "model": model,
        "tool_calls": None,
        "finish_reason": "unknown",
    }

    if response.status_code != 200:
        result["finish_reason"] = "error"
        result["error"] = f"API error {response.status_code}: {response.message}"
        return result

    if response.output and response.output.choices:
        choice = response.output.choices[0]
        result["content"] = choice.message.content or ""
        result["finish_reason"] = choice.finish_reason or "unknown"

        # Extract tool calls
        if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                }
                for tc in choice.message.tool_calls
            ]

    return result


def _log_call(
    log_path: str,
    step_name: str,
    prompt_preview: str,
    result: dict,
    model: str,
) -> None:
    """Append a call log entry to the JSONL file."""
    tz = timezone(timedelta(hours=8))
    entry = {
        "timestamp": datetime.now(tz).isoformat(),
        "step": step_name,
        "type": "model_call",
        "model": model,
        "prompt_preview": prompt_preview[:300],
        "content_preview": (result.get("content") or "")[:300],
        "finish_reason": result.get("finish_reason", "unknown"),
        "has_tool_calls": result.get("tool_calls") is not None,
        "error": result.get("error"),
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
