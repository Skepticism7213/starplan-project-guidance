"""
StarPlan Loop - Sentence Variant Template Library (Phase B).

Approved sentence templates for deterministic rendering. Each template:
  - Has a unique variant_id referenced by Claim.allowed_variant_ids
  - Contains a {display_value} slot filled ONLY from the Claim's display_value
  - Is categorized by audience level (beginner / general)
  - Has been audited to contain NO unverified factual assertions

The renderer (Phase C) fills slots from Claims only. No free text from Qwen
ever passes through these templates unfiltered.

Template format:
  VARIANT_ID -> {
      "template": "... {display_value} ...",
      "audience": ["beginner", "general"],
      "section": "target" | "observability" | "risk" | "actions",
      "note": "audit note",
  }
"""

from __future__ import annotations

# ── Sentence variant registry ────────────────────────
# Key: variant_id (must match Claim.allowed_variant_ids)
# Value: template dict with "template", "audience", "section"

SENTENCE_VARIANTS: dict[str, dict] = {
    # ── Target section ──

    "target_name_v1": {
        "template": "今晚我们要观测的是 {display_value}",
        "audience": ["beginner", "general"],
        "section": "target",
        "note": "Basic target introduction",
    },
    "target_name_v2": {
        "template": "本次活动的观测目标是 {display_value}",
        "audience": ["general"],
        "section": "target",
        "note": "Formal target introduction",
    },
    "target_name_not_obs_v1": {
        "template": "本次活动原定目标为 {display_value}",
        "audience": ["beginner", "general"],
        "section": "target",
        "note": "Not-observable branch: past-tense intro, no observation language",
    },
    "target_type_v1": {
        "template": "它是一个{display_value}",
        "audience": ["beginner", "general"],
        "section": "target",
        "note": "Target type description",
    },
    "constellation_v1": {
        "template": "它位于 {display_value} 星座方向",
        "audience": ["beginner", "general"],
        "section": "target",
        "note": "Constellation location",
    },
    "constellation_v2": {
        "template": "在星图上，它处于 {display_value} 座的天区",
        "audience": ["general"],
        "section": "target",
        "note": "Alternative constellation phrasing",
    },
    "magnitude_v1": {
        "template": "它的视星等约为 {display_value}",
        "audience": ["beginner", "general"],
        "section": "target",
        "note": "Visual magnitude",
    },
    "magnitude_v2": {
        "template": "亮度方面，视星等为 {display_value} 等",
        "audience": ["general"],
        "section": "target",
        "note": "Alternative magnitude phrasing",
    },
    "angular_size_v1": {
        "template": "它在天空中的角大小约为 {display_value}",
        "audience": ["beginner", "general"],
        "section": "target",
        "note": "Angular size",
    },
    "coordinates_v1": {
        "template": "其坐标为 {display_value}（J2000 历元）",
        "audience": ["general"],
        "section": "target",
        "note": "Coordinates with epoch",
    },

    # ── Derived visibility section ──

    "naked_eye_v1": {
        "template": "这个目标{display_value}",
        "audience": ["beginner", "general"],
        "section": "observability",
        "note": "Naked eye visible — no additional assertion about ease of finding",
    },
    "naked_eye_v2": {
        "template": "在良好的天空条件下，{display_value}",
        "audience": ["beginner"],
        "section": "observability",
        "note": "Naked eye with condition caveat",
    },
    "not_naked_eye_v1": {
        "template": "这个目标{display_value}",
        "audience": ["beginner", "general"],
        "section": "observability",
        "note": "Not naked eye visible",
    },
    "binoculars_v1": {
        "template": "使用双筒望远镜，{display_value}",
        "audience": ["beginner", "general"],
        "section": "observability",
        "note": "Binoculars visibility — no clarity promise",
    },
    "beginner_v1": {
        "template": "这个目标{display_value}",
        "audience": ["beginner"],
        "section": "observability",
        "note": "Beginner friendly — no extra recommendation without rule Claim",
    },
    "equipment_match_v1": {
        "template": "{display_value}",
        "audience": ["beginner", "general"],
        "section": "observability",
        "note": "Equipment suitability",
    },
    "equipment_mismatch_v1": {
        "template": "{display_value}",
        "audience": ["beginner", "general"],
        "section": "observability",
        "note": "Equipment insufficient — advice is a separate procedural Claim, not embedded here",
    },

    # ── Observability section ──

    "observable_status_v1": {
        "template": "经过计算，该目标在当晚{display_value}",
        "audience": ["beginner", "general"],
        "section": "observability",
        "note": "Observable status",
    },
    "peak_altitude_v1": {
        "template": "目标最高将升到 {display_value} 的高度",
        "audience": ["beginner", "general"],
        "section": "observability",
        "note": "Peak altitude",
    },
    "peak_altitude_v2": {
        "template": "当晚峰值高度角为 {display_value}",
        "audience": ["general"],
        "section": "observability",
        "note": "Peak altitude technical",
    },
    "airmass_v1": {
        "template": "对应的大气质量约为 {display_value}",
        "audience": ["general"],
        "section": "observability",
        "note": "Airmass value",
    },
    "window_v1": {
        "template": "推荐观测时段为 {display_value}",
        "audience": ["beginner", "general"],
        "section": "observability",
        "note": "Recommended window",
    },
    "window_v2": {
        "template": "本次约束下的推荐观测时间是 {display_value}",
        "audience": ["beginner"],
        "section": "observability",
        "note": "Window beginner phrasing — not 'best', just recommended under constraints",
    },
    "twilight_v1": {
        "template": "天文暮光于 {display_value} 结束",
        "audience": ["beginner", "general"],
        "section": "observability",
        "note": "Twilight end time — no assertion about sky darkness",
    },

    # ── Moon section ──

    "moon_phase_v1": {
        "template": "当晚月相照明比例为 {display_value}",
        "audience": ["general"],
        "section": "risk",
        "note": "Moon phase fraction",
    },
    "moon_sep_v1": {
        "template": "月球与目标的最小角距离为 {display_value}",
        "audience": ["general"],
        "section": "risk",
        "note": "Moon-target separation",
    },
    "moon_impact_v1": {
        "template": "综合评估：{display_value}",
        "audience": ["beginner", "general"],
        "section": "risk",
        "note": "Moon impact assessment",
    },

    # ── Unconfirmed section ──

    "unconfirmed_v1": {
        "template": "⚠️ {display_value}",
        "audience": ["beginner", "general"],
        "section": "actions",
        "note": "Unconfirmed item marker",
    },
    "unconfirmed_mag_v1": {
        "template": "目标 {display_value} 的视星等数据缺失，无法确认目视难度",
        "audience": ["beginner", "general"],
        "section": "actions",
        "note": "Missing magnitude warning; display_value = target name",
    },
    "unconfirmed_size_v1": {
        "template": "目标 {display_value} 的角大小数据缺失，无法确认设备匹配度",
        "audience": ["beginner", "general"],
        "section": "actions",
        "note": "Missing angular size warning; display_value = target name",
    },

    # ── Schedule section (procedural timeline items) ──

    "schedule_proc_v1": {
        "template": "{display_value}",
        "audience": ["beginner", "general"],
        "section": "schedule",
        "note": "Procedural schedule item passthrough; text approved at Claim registration",
    },
    "schedule_prep_v1": {
        "template": "{display_value} 天文暮光结束，开始准备设备",
        "audience": ["beginner", "general"],
        "section": "schedule",
        "note": "Twilight end triggers prep; display_value = twilight end time from obs Claim",
    },
    "schedule_obs_start_v1": {
        "template": "开始观测 {display_value}",
        "audience": ["beginner", "general"],
        "section": "schedule",
        "note": "Observation start; display_value = target name",
    },
    "schedule_obs_peak_v1": {
        "template": "推荐观测时段，峰值高度角 {display_value}",
        "audience": ["beginner", "general"],
        "section": "schedule",
        "note": "Peak altitude note; display_value = altitude with unit from obs Claim",
    },
    "schedule_twilight_end_v1": {
        "template": "{display_value} 天文暮光开始，活动结束",
        "audience": ["beginner", "general"],
        "section": "schedule",
        "note": "Twilight start triggers cleanup; display_value = twilight start time",
    },

    # ── Equipment section ──

    "equipment_item_v1": {
        "template": "{display_value}",
        "audience": ["beginner", "general"],
        "section": "equipment",
        "note": "Equipment item passthrough; text approved at Claim registration",
    },

    # ── Safety section ──

    "safety_instruction_v1": {
        "template": "{display_value}",
        "audience": ["beginner", "general"],
        "section": "safety",
        "note": "Safety instruction passthrough; text approved at Claim registration",
    },

    # ── Manual check section ──

    "manual_check_v1": {
        "template": "{display_value}",
        "audience": ["beginner", "general"],
        "section": "manual_check",
        "note": "Manual check item passthrough; text approved at Claim registration",
    },
    "manual_check_source_v1": {
        "template": "确认目标坐标来源: {display_value}",
        "audience": ["beginner", "general"],
        "section": "manual_check",
        "note": "Coordinate source verification; display_value = source identifier",
    },

    # ── Blocking / not-observable section ──

    "blocking_reason_v1": {
        "template": "{display_value}",
        "audience": ["beginner", "general"],
        "section": "blocking",
        "note": "Primary blocking reason; display_value = full reason sentence from Claim",
    },
    "blocking_constraint_v1": {
        "template": "具体约束: {display_value}",
        "audience": ["general"],
        "section": "blocking",
        "note": "Constraint detail from eliminated window reason text",
    },
    "blocking_below_horizon_v1": {
        "template": "{display_value}",
        "audience": ["beginner", "general"],
        "section": "blocking",
        "note": "Target below horizon; display_value = full sentence with max altitude",
    },
    "blocking_alt_v1": {
        "template": "当季更适合观测的替代目标：{display_value}",
        "audience": ["beginner", "general"],
        "section": "blocking",
        "note": "Alternative targets; display_value = comma-separated target names",
    },
    "blocking_reschedule_v1": {
        "template": "{display_value}",
        "audience": ["beginner", "general"],
        "section": "blocking",
        "note": "Reschedule suggestion passthrough",
    },
    "blocking_indoor_v1": {
        "template": "{display_value}",
        "audience": ["beginner"],
        "section": "blocking",
        "note": "Indoor activity suggestion for beginner audiences; procedural passthrough",
    },
}


# ── Connector templates (approved transitions between sections) ──

CONNECTORS: dict[str, dict] = {
    "then_v1": {
        "template": "接下来，",
        "note": "Simple transition",
    },
    "also_v1": {
        "template": "另外，",
        "note": "Additional info transition",
    },
    "however_v1": {
        "template": "不过需要注意，",
        "note": "Caution transition",
    },
    "therefore_v1": {
        "template": "因此，",
        "note": "Conclusion transition",
    },
}


# ── Section headers (approved) ──

SECTION_HEADERS: dict[str, str] = {
    "target": "关于目标",
    "observability": "观测条件",
    "risk": "风险提示",
    "actions": "行动建议",
}


def get_variant(variant_id: str) -> dict | None:
    """Look up a sentence variant by ID."""
    return SENTENCE_VARIANTS.get(variant_id)


def get_connector(connector_id: str) -> dict | None:
    """Look up a connector by ID."""
    return CONNECTORS.get(connector_id)


def render_sentence(variant_id: str, display_value: str) -> str | None:
    """Render a sentence from a variant template and a claim's display_value.

    Returns None if the variant_id is not found.
    """
    variant = SENTENCE_VARIANTS.get(variant_id)
    if variant is None:
        return None
    return variant["template"].replace("{display_value}", display_value)


def validate_variant_id(variant_id: str, allowed_ids: list[str]) -> bool:
    """Check that a variant_id exists in the library AND is in the claim's allowed list."""
    return variant_id in SENTENCE_VARIANTS and variant_id in allowed_ids
