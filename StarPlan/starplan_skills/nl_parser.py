"""
StarPlan Loop - Natural Language Parser (Week 3).

Uses Qwen to convert free-form user requests into structured StarPlanInput.
Example:
    "我们天文社想下周六在北京清华看仙女座星系，用双筒望远镜，给新成员科普"
    → StarPlanInput(target="M31", location="北京_清华", date_range=[...], ...)

Core principle: Qwen parses intent and extracts parameters.
It does NOT invent astronomical data — all coordinates and calculations
come from deterministic tools downstream.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Optional

from .qwen_client import call_qwen_json, DEFAULT_MODEL
from .schemas import StarPlanInput, LocationDetail, ObservingConstraint

# System prompt for NL parsing
_PARSE_SYSTEM_PROMPT = """\
你是 StarPlan Loop 的自然语言解析器。你的任务是把用户的观测活动需求
解析为结构化的 JSON 参数。

你必须提取以下字段：
- target: 观测目标名称（中文、英文、Messier 编号均可）
- target_type: 目标类型提示（deep_sky / star / planet / asterism），不确定填 null
- location: 地点标识符，格式为"城市_地点"，如"济南_四门塔"、"北京_清华"
- location_detail: 如果用户提供了具体经纬度，填写 {name, city, latitude, longitude, elevation_m, timezone}，否则填 null
- date_range: 观测日期范围 [开始, 结束]，格式 YYYY-MM-DD。如果用户说"下周六"等相对日期，根据当前日期推算
- audience: 受众描述，如"天文社新成员"、"小学生"
- equipment: 设备类型，必须是以下之一：naked_eye / binoculars / small_telescope / large_telescope
- goal: 活动目标，默认"校园科普观测"
- constraints: 可选约束 {min_altitude_deg, max_airmass, prefer_early_night, max_moon_illumination}，用户未提及填 null

重要规则：
1. 只提取用户明确表达或可合理推断的信息
2. 不确定的字段填 null，不要编造
3. 设备类型必须映射到四个标准值之一
4. 日期必须是具体的 YYYY-MM-DD 格式
5. 只返回 JSON，不要输出任何其他文字
"""

# Available location keys for validation
_KNOWN_LOCATIONS = [
    "济南_四门塔", "济南_山东大学", "北京_清华", "南京_紫金山",
    "上海_佘山", "昆明_云南大学", "西安_交大", "成都_川大",
]

# Equipment mapping from Chinese to standard keys
_EQUIPMENT_MAP = {
    "肉眼": "naked_eye",
    "双筒": "binoculars",
    "双筒望远镜": "binoculars",
    "小型望远镜": "small_telescope",
    "小望远镜": "small_telescope",
    "望远镜": "small_telescope",
    "大型望远镜": "large_telescope",
    "大望远镜": "large_telescope",
}


def parse_natural_language(
    user_input: str,
    reference_date: Optional[date] = None,
    model: str = DEFAULT_MODEL,
    log_path: Optional[str] = None,
) -> StarPlanInput:
    """
    Parse a natural language observation request into StarPlanInput.

    Args:
        user_input: Free-form user request in Chinese or English.
        reference_date: Reference date for relative date expressions.
                       Defaults to today.
        model: Qwen model to use.
        log_path: Path for model call logging.

    Returns:
        Validated StarPlanInput.

    Raises:
        ValueError: If parsing fails or required fields are missing.
    """
    if not user_input or not user_input.strip():
        raise ValueError("用户输入不能为空")

    ref = reference_date or date.today()

    prompt = (
        f"当前日期: {ref.isoformat()}\n\n"
        f"用户需求:\n{user_input}\n\n"
        f"请解析为 JSON。"
    )

    result = call_qwen_json(
        prompt=prompt,
        model=model,
        system_prompt=_PARSE_SYSTEM_PROMPT,
        log_path=log_path,
        step_name="nl_parse",
    )

    parsed = result.get("parsed_json")
    if parsed is None:
        raise ValueError(
            f"Qwen 未能返回有效 JSON。原始响应: {result.get('content', '')[:300]}"
        )

    # Post-process and validate
    parsed = _post_process(parsed, ref)

    # Validate with Pydantic
    try:
        starplan_input = StarPlanInput(**parsed)
    except Exception as e:
        raise ValueError(f"解析结果未通过 Schema 验证: {e}\n原始 JSON: {json.dumps(parsed, ensure_ascii=False, indent=2)}")

    return starplan_input


def _post_process(parsed: dict, ref_date: date) -> dict:
    """Post-process Qwen output: normalize equipment, validate location, etc."""

    # Normalize equipment
    equipment = parsed.get("equipment", "")
    if equipment in _EQUIPMENT_MAP:
        parsed["equipment"] = _EQUIPMENT_MAP[equipment]
    elif equipment not in ("naked_eye", "binoculars", "small_telescope", "large_telescope"):
        # Try fuzzy match
        for cn, en in _EQUIPMENT_MAP.items():
            if cn in equipment:
                parsed["equipment"] = en
                break
        else:
            parsed["equipment"] = "binoculars"  # Safe default

    # Validate location against known locations
    location = parsed.get("location", "")
    if location and location not in _KNOWN_LOCATIONS:
        # Try to match partial
        for known in _KNOWN_LOCATIONS:
            if location in known or known in location:
                parsed["location"] = known
                break

    # Ensure date_range is list of strings
    date_range = parsed.get("date_range")
    if date_range:
        if isinstance(date_range, str):
            parsed["date_range"] = [date_range, date_range]
        elif isinstance(date_range, list) and len(date_range) == 1:
            parsed["date_range"] = [date_range[0], date_range[0]]

    # Ensure required fields have defaults
    if not parsed.get("audience"):
        parsed["audience"] = "天文社新成员"
    if not parsed.get("goal"):
        parsed["goal"] = "校园科普观测"

    # Remove null constraints
    if parsed.get("constraints") is None:
        parsed.pop("constraints", None)

    # Remove null location_detail
    if parsed.get("location_detail") is None:
        parsed.pop("location_detail", None)

    # Remove null target_type
    if parsed.get("target_type") is None:
        parsed.pop("target_type", None)

    return parsed
