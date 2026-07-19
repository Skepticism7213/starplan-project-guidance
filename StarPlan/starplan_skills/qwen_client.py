"""
StarPlan Loop - Qwen client stub.

Placeholder for Alibaba Cloud DashScope / Qwen integration.
Full implementation planned for Week 3.

Current functionality: basic API call wrapper with logging.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# Model configuration
QWEN_MODELS = {
    "max": "qwen3.7-max",
    "plus": "qwen3.7-plus",
}
DEFAULT_MODEL = QWEN_MODELS["max"]


def call_qwen(
    prompt: str,
    model: str = DEFAULT_MODEL,
    system_prompt: Optional[str] = None,
    tools: Optional[list[dict]] = None,
    log_path: Optional[str] = None,
) -> dict:
    """
    Call Qwen model via DashScope API.

    Args:
        prompt: User prompt.
        model: Model identifier.
        system_prompt: Optional system prompt.
        tools: Optional tool definitions for function calling.
        log_path: Path to append call log entry.

    Returns:
        Dict with content, model, tool_calls, etc.
    """
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        raise RuntimeError(
            "DASHSCOPE_API_KEY not set. "
            "Copy .env.example to .env and fill in your key."
        )

    try:
        import dashscope
        from dashscope import Generation

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": model,
            "messages": messages,
            "result_format": "message",
        }
        if tools:
            kwargs["tools"] = tools

        response = Generation.call(**kwargs)

        result = {
            "content": response.output.choices[0].message.content if response.output else "",
            "model": model,
            "tool_calls": None,
            "finish_reason": response.output.choices[0].finish_reason if response.output else "unknown",
        }

        # Extract tool calls if present
        if response.output and hasattr(response.output.choices[0].message, "tool_calls"):
            result["tool_calls"] = response.output.choices[0].message.tool_calls

        # Log the call
        if log_path:
            _log_call(log_path, prompt, result, model)

        return result

    except ImportError:
        raise RuntimeError("dashscope package not installed. Run: pip install dashscope")
    except Exception as e:
        raise RuntimeError(f"Qwen API call failed: {e}")


def _log_call(log_path: str, prompt: str, result: dict, model: str) -> None:
    """Append a call log entry to the JSONL file."""
    tz = timezone(timedelta(hours=8))
    entry = {
        "timestamp": datetime.now(tz).isoformat(),
        "model": model,
        "prompt_preview": prompt[:200],
        "content_preview": result["content"][:200] if result["content"] else "",
        "finish_reason": result["finish_reason"],
        "has_tool_calls": result["tool_calls"] is not None,
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
