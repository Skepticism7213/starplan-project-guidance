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

import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Optional

from dotenv import load_dotenv

load_dotenv()

# P1-B: Explicit offline mode. When STARPLAN_MODEL_MODE=offline, all model
# calls raise immediately — even if DASHSCOPE_API_KEY is present in .env.
# This guarantees the offline CI cannot make real network requests.
MODEL_MODE = os.getenv("STARPLAN_MODEL_MODE", "online")
_OFFLINE = MODEL_MODE == "offline"


def _assert_online():
    """Raise if offline mode is active. Called at the top of every call function."""
    if _OFFLINE:
        raise RuntimeError(
            "STARPLAN_MODEL_MODE=offline: network model call attempted. "
            "This is a tripwire — offline CI must not reach the network."
        )

# ── Runtime model/endpoint configuration (env-overridable) ──
#
# 百炼 API Key 常只授权 OpenAI 兼容端点下的特定模型（例如
# qwen3.7-plus / qwen3.8-max），原生 DashScope 端点会返回 403/400。
# 通过环境变量启用兼容端点：
#   STARPLAN_QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
#   STARPLAN_QWEN_MODEL=qwen3.7-plus
#   STARPLAN_QWEN_TIMEOUT=60
#   STARPLAN_QWEN_RETRIES=1
# 配置在每次调用时读取，支持运行期修改。


def _api_key() -> str:
    """Return the configured DASHSCOPE_API_KEY (raises if missing)."""
    _check_api_key()
    return os.getenv("DASHSCOPE_API_KEY", "")


def _resolve_model(model: Optional[str]) -> str:
    """Resolve the effective model: explicit arg > STARPLAN_QWEN_MODEL > default."""
    return (
        model
        or os.getenv("STARPLAN_QWEN_MODEL", "").strip()
        or DEFAULT_MODEL
    )


def _compatible_base_url() -> str:
    """OpenAI-compatible endpoint base URL, or '' when disabled."""
    return os.getenv("STARPLAN_QWEN_BASE_URL", "").strip().rstrip("/")


def _compatible_timeout() -> int:
    """Per-call timeout in seconds (default 60)."""
    raw = os.getenv("STARPLAN_QWEN_TIMEOUT", "60") or "60"
    try:
        return max(int(raw), 1)
    except ValueError:
        return 60


def _compatible_retries() -> int:
    """Retry count for transient failures (default 1)."""
    raw = os.getenv("STARPLAN_QWEN_RETRIES", "1") or "1"
    try:
        return max(int(raw), 0)
    except ValueError:
        return 1


def _compatible_enabled() -> bool:
    return bool(_compatible_base_url())


def _compatible_chat(
    messages: list[dict],
    tools: Optional[list[dict]] = None,
    max_tokens: int = 4096,
) -> dict:
    """POST to the OpenAI-compatible chat/completions endpoint."""
    import json as _json
    import urllib.request as _urlreq

    url = f"{_compatible_base_url()}/chat/completions"
    payload: dict[str, Any] = {
        "model": _resolve_model(None),
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools
    req = _urlreq.Request(
        url,
        data=_json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        },
    )
    with _urlreq.urlopen(req, timeout=_compatible_timeout()) as resp:
        return _json.loads(resp.read().decode("utf-8"))


def _compatible_chat_with_retry(
    messages: list[dict],
    tools: Optional[list[dict]] = None,
    max_tokens: int = 4096,
) -> dict:
    """Call the compatible endpoint with bounded retries on 5xx/network errors."""
    import urllib.error as _urlerr

    last_error: Optional[Exception] = None
    for attempt in range(_compatible_retries() + 1):
        try:
            return _compatible_chat(messages, tools=tools, max_tokens=max_tokens)
        except _urlerr.HTTPError as exc:
            last_error = exc
            if exc.code >= 500 and attempt < _compatible_retries():
                continue
            raise
        except Exception as exc:  # network/timeout — retry once
            last_error = exc
            if attempt < _compatible_retries():
                continue
            raise
    raise last_error  # pragma: no cover — loop always returns or raises


def _parse_compatible_choice(data: dict, model: str) -> dict:
    """Normalize an OpenAI-compatible response choice to the internal dict."""
    choice = data["choices"][0]
    msg = choice.get("message", {})
    return {
        "content": msg.get("content") or "",
        "model": model,
        "tool_calls": msg.get("tool_calls"),
        "finish_reason": choice.get("finish_reason", "stop"),
    }


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
            "name": "resolve_location",
            "description": (
                "将地点名称（如'济南四门塔'、'北京清华'）解析为标准观测地点，"
                "返回地点的经纬度、海拔和时区。"
                "调用 observability_plan 之前必须先调用本工具获取准确经纬度，"
                "绝对不要凭记忆猜测经纬度。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location_name": {
                        "type": "string",
                        "description": "地点名称，如'济南四门塔'、'北京清华'、'南京紫金山'",
                    },
                },
                "required": ["location_name"],
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
    {
        "type": "function",
        "function": {
            "name": "outreach_pack",
            "description": (
                "根据已验证的目标信息和可观测性计算结果，生成科普观测活动包。"
                "包含活动流程、讲解要点、设备清单、安全提示和人工核对项。"
                "讲解要点中的数值必须可溯源到 Claim Registry，不可编造。"
                "必须在 target_resolve 和 observability_plan 之后调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_name": {
                        "type": "string",
                        "description": "标准目标名称（来自 target_resolve 结果）",
                    },
                    "audience": {
                        "type": "string",
                        "description": "受众描述，如'天文社新成员'、'小学生'",
                    },
                    "equipment": {
                        "type": "string",
                        "enum": ["naked_eye", "binoculars", "small_telescope", "large_telescope"],
                        "description": "设备类型",
                    },
                    "goal": {
                        "type": "string",
                        "description": "活动目标，默认'校园科普观测'",
                    },
                },
                "required": ["target_name", "audience", "equipment"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "observation_review",
            "description": (
                "对已完成的观测活动进行回顾评估。"
                "输入观测日志（实际天气、参与人数、观测效果等），"
                "输出评估报告：目标达成度、改进建议、下次活动优化方案。"
                "用于 4-Skill 闭环的最后一步。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_name": {
                        "type": "string",
                        "description": "观测目标名称",
                    },
                    "observation_log": {
                        "type": "string",
                        "description": "观测日志文本，包含实际天气、参与情况、观测效果等",
                    },
                    "planned_window": {
                        "type": "string",
                        "description": "原计划观测时段（来自 observability_plan）",
                    },
                },
                "required": ["target_name", "observation_log"],
            },
        },
    },
]


# ── Core API functions ───────────────────────────────

def call_qwen(
    prompt: str,
    model: Optional[str] = None,
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
    _assert_online()
    _check_api_key()
    model = _resolve_model(model)

    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    if _compatible_enabled():
        try:
            data = _compatible_chat_with_retry(messages, tools=tools)
            result = _parse_compatible_choice(data, model)
        except Exception as e:
            result = {
                "content": "",
                "model": model,
                "tool_calls": None,
                "finish_reason": "error",
                "error": str(e)[:300],
            }
    else:
        from dashscope import Generation

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "result_format": "message",
        }
        if tools:
            kwargs["tools"] = tools
        try:
            response = Generation.call(**kwargs, timeout=_compatible_timeout())
        except TypeError:
            # Older dashscope releases may not accept the timeout kwarg.
            response = Generation.call(**kwargs)
        result = _parse_response(response, model)

    if log_path:
        _log_call(log_path, step_name, prompt, result, model)

    return result


def call_qwen_json(
    prompt: str,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    log_path: Optional[str] = None,
    step_name: str = "qwen_json",
) -> dict:
    """
    Call Qwen with JSON output mode for structured data extraction.

    The model is instructed to return valid JSON only.
    """
    json_system = (
        "你必须且只能返回合法的 JSON 对象，不要输出任何 JSON 之外的文字、"
        "解释或 markdown 代码块标记。"
    )
    if system_prompt:
        json_system = system_prompt + "\n\n" + json_system

    result = call_qwen(
        prompt=prompt,
        model=model,
        system_prompt=json_system,
        log_path=log_path,
        step_name=step_name,
    )

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

    return result


def call_qwen_chat(
    messages: list[dict],
    model: Optional[str] = None,
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
    _assert_online()
    _check_api_key()
    model = _resolve_model(model)

    tool_call_log: list[dict] = []
    tz = timezone(timedelta(hours=8))

    for round_idx in range(max_tool_rounds):
        if _compatible_enabled():
            try:
                data = _compatible_chat_with_retry(messages, tools=tools)
                result = _parse_compatible_choice(data, model)
            except Exception as e:
                return {
                    "content": "",
                    "model": model,
                    "tool_calls": None,
                    "finish_reason": "error",
                    "error": str(e)[:300],
                    "tool_call_log": tool_call_log,
                    "messages": messages,
                }
        else:
            from dashscope import Generation

            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "result_format": "message",
            }
            if tools:
                kwargs["tools"] = tools
            try:
                response = Generation.call(**kwargs, timeout=_compatible_timeout())
            except TypeError:
                # Older dashscope releases may not accept the timeout kwarg.
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
    """Append a call log entry to the JSONL file (Phase E: enhanced audit)."""
    tz = timezone(timedelta(hours=8))
    content = result.get("content") or ""

    # Truncate FIRST, then hash the stored text (auditors can recompute)
    prompt_stored = prompt_preview[:300]
    content_stored = content[:300]
    prompt_hash = hashlib.sha256(prompt_stored.encode("utf-8")).hexdigest()[:16]
    response_hash = hashlib.sha256(content_stored.encode("utf-8")).hexdigest()[:16]

    entry = {
        "timestamp": datetime.now(tz).isoformat(),
        "step": step_name,
        "type": "model_call",
        "model": model,
        "prompt_preview": prompt_stored,
        "prompt_hash": prompt_hash,
        "content_preview": content_stored,
        "response_hash": response_hash,
        "finish_reason": result.get("finish_reason", "unknown"),
        "has_tool_calls": result.get("tool_calls") is not None,
        "error": result.get("error"),
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
