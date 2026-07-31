"""
StarPlan Loop - Deterministic Renderer (Phase C).

Renders user-visible text from Claims + ExpressionPlan ONLY.
No free text from Qwen ever reaches the user through this path.

Core invariant: every rendered sentence maps back to one or more Claim IDs.
The renderer fills {display_value} slots from the Claim's display_value field,
using approved sentence variant templates from the template library.

See: starplan-hallucination-prevention-architecture.md §6
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .claims import AllowedClaimsBuilder
from .schemas import Claim, ClaimType, ExpressionPlan, SelectedClaim
from .templates import SENTENCE_VARIANTS, render_sentence


def _audience_key(audience: str) -> str:
    """Determine audience level from audience description string."""
    if "新" in audience or "入门" in audience or "小学" in audience:
        return "beginner"
    return "general"


def _pick_variant_for_audience(allowed_ids: list[str], audience: str) -> str:
    """Pick the best variant from allowed_ids for the given audience.

    Prefers variants tagged for the audience level; falls back to first allowed.
    """
    key = _audience_key(audience)
    for vid in allowed_ids:
        info = SENTENCE_VARIANTS.get(vid, {})
        if key in info.get("audience", []):
            return vid
    # Fallback: first allowed variant
    return allowed_ids[0] if allowed_ids else ""


@dataclass
class RenderedSentence:
    """A single rendered sentence with its claim provenance."""

    text: str
    claim_ids: list[str]
    variant_id: str
    section: str


@dataclass
class RenderResult:
    """Complete render output with full provenance tracking."""

    sentences: list[RenderedSentence] = field(default_factory=list)
    sections_used: list[str] = field(default_factory=list)
    claims_rendered: list[str] = field(default_factory=list)
    claims_skipped: list[str] = field(default_factory=list)
    fallback_used: bool = False
    fallback_reason: str = ""

    @property
    def talking_points(self) -> list[str]:
        """Extract just the text lines (compatible with OutreachPack.talking_points)."""
        return [s.text for s in self.sentences]

    @property
    def sentence_claim_map(self) -> dict[str, list[str]]:
        """Map each sentence to its source claim IDs (for audit)."""
        return {s.text: s.claim_ids for s in self.sentences}


def render_from_expression_plan(
    plan: ExpressionPlan,
    claims_builder: AllowedClaimsBuilder,
    audience: str = "general",
) -> RenderResult:
    """Render talking points from a validated ExpressionPlan.

    This is the PRIMARY render path when Qwen returns a valid ExpressionPlan.
    Every sentence is deterministically rendered from Claim display_values
    using approved templates. Qwen's role is limited to selecting and ordering.

    Args:
        plan: Validated ExpressionPlan from Qwen.
        claims_builder: The run's Claim Registry.
        audience: Audience level for variant filtering.

    Returns:
        RenderResult with sentences and full provenance.
    """
    result = RenderResult()
    audience_key = "beginner" if ("新" in audience or "入门" in audience) else "general"

    for selected in plan.selected_claims:
        claim = claims_builder.get_claim(selected.claim_id)
        if claim is None:
            result.claims_skipped.append(selected.claim_id)
            continue

        # Skip unconfirmed claims in main text (they go to unconfirmed_items)
        if claim.claim_type == ClaimType.UNCONFIRMED:
            result.claims_skipped.append(selected.claim_id)
            continue

        # Render using the selected variant
        text = render_sentence(selected.sentence_variant_id, claim.display_value)
        if text is None:
            result.claims_skipped.append(selected.claim_id)
            continue

        # Determine section from template
        variant_info = SENTENCE_VARIANTS.get(selected.sentence_variant_id, {})
        section = variant_info.get("section", "target")

        result.sentences.append(RenderedSentence(
            text=text,
            claim_ids=[claim.claim_id],
            variant_id=selected.sentence_variant_id,
            section=section,
        ))
        result.claims_rendered.append(claim.claim_id)
        if section not in result.sections_used:
            result.sections_used.append(section)

    return result


def render_deterministic_fallback(
    claims_builder: AllowedClaimsBuilder,
    audience: str = "general",
    reason: str = "",
) -> RenderResult:
    """Render a complete deterministic output WITHOUT any Qwen involvement.

    This is the FAIL-CLOSED fallback: used when Qwen fails, returns invalid
    data, or validation rejects the ExpressionPlan. The output is fully
    deterministic and traceable.

    Selects claims in a fixed priority order and renders them with the
    first available variant for each.

    Args:
        claims_builder: The run's Claim Registry.
        audience: Audience level.
        reason: Why the fallback was triggered (for audit).

    Returns:
        RenderResult with fallback_used=True.
    """
    result = RenderResult(fallback_used=True, fallback_reason=reason)

    # Fixed priority order for deterministic output
    priority_order = [
        "target.standard_name",
        "target.type",
        "target.constellation",
        "target.visual_magnitude",
        "target.angular_size",
        "obs.is_observable",
        "obs.peak_altitude",
        "obs.recommended_window",
        "obs.twilight_end",
        "derived.visibility.naked_eye",
        "derived.visibility.binoculars",
        "derived.visibility.beginner_friendly",
        "derived.equipment.match",
        "moon.impact",
        "moon.separation",
    ]

    for claim_id in priority_order:
        claim = claims_builder.get_claim(claim_id)
        if claim is None:
            continue
        if claim.claim_type in (ClaimType.UNCONFIRMED, ClaimType.PROHIBITED):
            continue
        if not claim.allowed_variant_ids:
            continue

        # Use audience-aware variant selection
        variant_id = _pick_variant_for_audience(claim.allowed_variant_ids, audience)
        if not variant_id:
            continue
        text = render_sentence(variant_id, claim.display_value)
        if text is None:
            continue

        variant_info = SENTENCE_VARIANTS.get(variant_id, {})
        section = variant_info.get("section", "target")

        result.sentences.append(RenderedSentence(
            text=text,
            claim_ids=[claim.claim_id],
            variant_id=variant_id,
            section=section,
        ))
        result.claims_rendered.append(claim.claim_id)
        if section not in result.sections_used:
            result.sections_used.append(section)

    return result


def render_not_observable_fallback(
    claims_builder: AllowedClaimsBuilder,
    audience: str = "general",
) -> RenderResult:
    """Render talking points for the not-observable branch.

    Uses only target identity claims (no observability data since there is none).
    """
    result = RenderResult(fallback_used=True, fallback_reason="not_observable_branch")

    # For not-observable, only render target identity + status
    not_obs_order = [
        "target.standard_name",
        "target.type",
        "target.constellation",
        "target.visual_magnitude",
        "obs.is_observable",
    ]

    for claim_id in not_obs_order:
        claim = claims_builder.get_claim(claim_id)
        if claim is None:
            continue
        if claim.claim_type in (ClaimType.PROHIBITED, ClaimType.UNCONFIRMED):
            continue
        if not claim.allowed_variant_ids:
            continue

        # Use not-observable-specific variant for target name to avoid
        # observation language like "今晚我们要观测的是"
        if claim_id == "target.standard_name":
            variant_id = "target_name_not_obs_v1"
        else:
            variant_id = _pick_variant_for_audience(claim.allowed_variant_ids, audience)
        if not variant_id:
            continue
        text = render_sentence(variant_id, claim.display_value)
        if text is None:
            continue

        variant_info = SENTENCE_VARIANTS.get(variant_id, {})
        section = variant_info.get("section", "target")

        result.sentences.append(RenderedSentence(
            text=text,
            claim_ids=[claim.claim_id],
            variant_id=variant_id,
            section=section,
        ))
        result.claims_rendered.append(claim.claim_id)

    return result


# ── P1-2: Unified Section Renderer ──────────────────
# All user-visible text is rendered from Claims + variants.
# outreach_pack.py only organizes layout from these results.


@dataclass
class RenderedScheduleItem:
    """A schedule item with full claim provenance."""

    time_label: str
    activity: str
    notes: str
    claim_ids: list[str]
    variant_ids: list[str]
    section: str = "schedule"


@dataclass
class RenderedEquipmentItem:
    """An equipment item with full claim provenance."""

    item: str
    quantity: str
    notes: str
    claim_ids: list[str]
    variant_ids: list[str]
    section: str = "equipment"


@dataclass
class FullSectionRenderResult:
    """Complete render output for all pack sections."""

    talking_points: list[RenderedSentence] = field(default_factory=list)
    schedule: list[RenderedScheduleItem] = field(default_factory=list)
    equipment: list[RenderedEquipmentItem] = field(default_factory=list)
    safety: list[RenderedSentence] = field(default_factory=list)
    manual_checks: list[RenderedSentence] = field(default_factory=list)
    unconfirmed: list[RenderedSentence] = field(default_factory=list)
    blocking: list[RenderedSentence] = field(default_factory=list)
    alternatives: list[RenderedSentence] = field(default_factory=list)

    @property
    def all_sentences(self) -> list[RenderedSentence]:
        """All rendered sentences across all sections (for render_trace)."""
        items: list[RenderedSentence] = []
        items.extend(self.talking_points)
        items.extend(self.safety)
        items.extend(self.manual_checks)
        items.extend(self.unconfirmed)
        items.extend(self.blocking)
        items.extend(self.alternatives)
        for si in self.schedule:
            text = f"{si.time_label}: {si.activity}"
            if si.notes:
                text += f" ({si.notes})"
            items.append(RenderedSentence(
                text=text,
                claim_ids=si.claim_ids,
                variant_id=si.variant_ids[0] if si.variant_ids else "",
                section="schedule",
            ))
        for ei in self.equipment:
            text = ei.item
            if ei.notes:
                text += f" ({ei.notes})"
            items.append(RenderedSentence(
                text=text,
                claim_ids=ei.claim_ids,
                variant_id=ei.variant_ids[0] if ei.variant_ids else "",
                section="equipment",
            ))
        return items


# Equipment quantity/notes metadata (layout constants, not factual assertions)
_EQUIPMENT_META: dict[str, tuple[str, str]] = {
    "equipment.binoculars": ("每组 1 台", ""),
    "equipment.tripod": ("每组 1 个", "双筒手持容易抖动"),
    "equipment.small_telescope": ("每组 1 台", ""),
    "equipment.eyepiece": ("2-3 个", ""),
    "equipment.none_needed": ("—", ""),
    "equipment.star_chart": ("每组 1 个", ""),
    "equipment.red_flashlight": ("每组 1 个", "保护暗适应视力"),
    "equipment.warm_clothes": ("每人", "根据当地天气预报准备"),
    "equipment.notebook": ("每组 1 套", ""),
    "equipment.repellent": ("适量", "户外使用"),
}

_EQUIPMENT_ORDER: dict[str, list[str]] = {
    "binoculars": [
        "equipment.binoculars", "equipment.tripod",
        "equipment.star_chart", "equipment.red_flashlight",
        "equipment.warm_clothes", "equipment.notebook", "equipment.repellent",
    ],
    "small_telescope": [
        "equipment.small_telescope", "equipment.eyepiece",
        "equipment.star_chart", "equipment.red_flashlight",
        "equipment.warm_clothes", "equipment.notebook", "equipment.repellent",
    ],
    "naked_eye": [
        "equipment.none_needed",
        "equipment.star_chart", "equipment.red_flashlight",
        "equipment.warm_clothes", "equipment.notebook", "equipment.repellent",
    ],
}


def render_schedule_section(
    claims_builder: AllowedClaimsBuilder,
    audience: str = "general",
) -> list[RenderedScheduleItem]:
    """Render the activity schedule from obs Claims + procedural Claims."""
    items: list[RenderedScheduleItem] = []

    # 1. Twilight end -> prepare
    tw_end = claims_builder.get_claim("obs.twilight_end")
    if tw_end:
        items.append(RenderedScheduleItem(
            time_label=tw_end.display_value,
            activity="天文暮光结束，开始准备设备",
            notes="",
            claim_ids=["obs.twilight_end"],
            variant_ids=["schedule_prep_v1"],
        ))

    # 2-5. Observation window items
    window_claim = claims_builder.get_claim("obs.recommended_window")
    name_claim = claims_builder.get_claim("target.standard_name")
    peak_claim = claims_builder.get_claim("obs.peak_altitude")

    if window_claim and name_claim:
        w_text = window_claim.display_value
        start_time = w_text.split("~")[0].strip() if "~" in w_text else w_text
        end_time = w_text.split("~")[1].strip() if "~" in w_text else ""

        # Start observation
        activity = render_sentence("schedule_obs_start_v1", name_claim.display_value)
        notes = ""
        n_claims = ["target.standard_name", "obs.recommended_window"]
        n_variants = ["schedule_obs_start_v1"]
        if peak_claim:
            notes = render_sentence("schedule_obs_peak_v1", peak_claim.display_value) or ""
            n_claims.append("obs.peak_altitude")
            n_variants.append("schedule_obs_peak_v1")
        items.append(RenderedScheduleItem(
            time_label=start_time,
            activity=activity or f"开始观测 {name_claim.display_value}",
            notes=notes,
            claim_ids=n_claims,
            variant_ids=n_variants,
        ))

        # In progress
        progress = claims_builder.get_claim("schedule.obs_progress")
        if progress:
            items.append(RenderedScheduleItem(
                time_label=w_text,
                activity=progress.display_value,
                notes="",
                claim_ids=["schedule.obs_progress", "obs.recommended_window"],
                variant_ids=["schedule_proc_v1"],
            ))

        # End + descend note
        end_claim = claims_builder.get_claim("schedule.obs_end")
        descend = claims_builder.get_claim("schedule.obs_descend")
        if end_claim:
            items.append(RenderedScheduleItem(
                time_label=end_time,
                activity=end_claim.display_value,
                notes=descend.display_value if descend else "",
                claim_ids=["schedule.obs_end"] + (["schedule.obs_descend"] if descend else []),
                variant_ids=["schedule_proc_v1"],
            ))

    # 6. Twilight start -> cleanup
    tw_start = claims_builder.get_claim("obs.twilight_start")
    cleanup = claims_builder.get_claim("schedule.cleanup")
    if tw_start:
        items.append(RenderedScheduleItem(
            time_label=tw_start.display_value,
            activity="天文暮光开始，活动结束",
            notes=cleanup.display_value if cleanup else "",
            claim_ids=["obs.twilight_start"] + (["schedule.cleanup"] if cleanup else []),
            variant_ids=["schedule_twilight_end_v1"] + (["schedule_proc_v1"] if cleanup else []),
        ))

    return items


def render_equipment_section(
    claims_builder: AllowedClaimsBuilder,
    equipment: str = "binoculars",
) -> list[RenderedEquipmentItem]:
    """Render equipment checklist from equipment Claims."""
    items: list[RenderedEquipmentItem] = []
    order = _EQUIPMENT_ORDER.get(equipment, _EQUIPMENT_ORDER["binoculars"])

    for claim_id in order:
        claim = claims_builder.get_claim(claim_id)
        if claim is None:
            continue
        text = render_sentence("equipment_item_v1", claim.display_value)
        if text is None:
            continue
        qty, notes = _EQUIPMENT_META.get(claim_id, ("", ""))
        items.append(RenderedEquipmentItem(
            item=text, quantity=qty, notes=notes,
            claim_ids=[claim_id], variant_ids=["equipment_item_v1"],
        ))

    return items


def render_flat_section(
    claims_builder: AllowedClaimsBuilder,
    claim_ids: list[str],
    section: str,
) -> list[RenderedSentence]:
    """Render a flat list of sentences from Claims (safety, manual_check, etc.)."""
    sentences: list[RenderedSentence] = []
    for claim_id in claim_ids:
        claim = claims_builder.get_claim(claim_id)
        if claim is None:
            continue
        if not claim.allowed_variant_ids:
            continue
        variant_id = claim.allowed_variant_ids[0]
        text = render_sentence(variant_id, claim.display_value)
        if text is None:
            continue
        sentences.append(RenderedSentence(
            text=text, claim_ids=[claim_id],
            variant_id=variant_id, section=section,
        ))
    return sentences


def render_blocking_section(
    claims_builder: AllowedClaimsBuilder,
    audience: str = "general",
) -> tuple[list[RenderedSentence], list[RenderedSentence]]:
    """Render not-observable blocking points and alternatives.

    Returns (blocking_points, alternative_points).
    """
    blocking: list[RenderedSentence] = []
    alternatives: list[RenderedSentence] = []

    # Primary reason
    reason = claims_builder.get_claim("blocking.reason")
    if reason:
        text = render_sentence("blocking_reason_v1", reason.display_value)
        if text:
            blocking.append(RenderedSentence(
                text=text, claim_ids=["blocking.reason"],
                variant_id="blocking_reason_v1", section="blocking",
            ))

    # Constraint detail
    detail = claims_builder.get_claim("blocking.constraint_detail")
    if detail:
        text = render_sentence("blocking_constraint_v1", detail.display_value)
        if text:
            blocking.append(RenderedSentence(
                text=text, claim_ids=["blocking.constraint_detail"],
                variant_id="blocking_constraint_v1", section="blocking",
            ))

    # Educational context (target identity)
    for cid, vid in [("target.constellation", "constellation_v1"),
                     ("target.visual_magnitude", "magnitude_v1")]:
        claim = claims_builder.get_claim(cid)
        if claim and claim.claim_type != ClaimType.UNCONFIRMED:
            text = render_sentence(vid, claim.display_value)
            if text:
                blocking.append(RenderedSentence(
                    text=text, claim_ids=[cid],
                    variant_id=vid, section="blocking",
                ))

    # Alternatives
    alt = claims_builder.get_claim("blocking.alternatives")
    if alt:
        text = render_sentence("blocking_alt_v1", alt.display_value)
        if text:
            alternatives.append(RenderedSentence(
                text=text, claim_ids=["blocking.alternatives"],
                variant_id="blocking_alt_v1", section="blocking",
            ))

    # Reschedule
    resched = claims_builder.get_claim("blocking.reschedule_action")
    if resched:
        text = render_sentence("blocking_reschedule_v1", resched.display_value)
        if text:
            alternatives.append(RenderedSentence(
                text=text, claim_ids=["blocking.reschedule_action"],
                variant_id="blocking_reschedule_v1", section="blocking",
            ))

    # Indoor (beginner only)
    if "新" in audience or "入门" in audience:
        indoor = claims_builder.get_claim("blocking.indoor_activity")
        if indoor:
            text = render_sentence("blocking_indoor_v1", indoor.display_value)
            if text:
                alternatives.append(RenderedSentence(
                    text=text, claim_ids=["blocking.indoor_activity"],
                    variant_id="blocking_indoor_v1", section="blocking",
                ))

    return blocking, alternatives


def render_all_sections(
    claims_builder: AllowedClaimsBuilder,
    audience: str = "general",
    equipment: str = "binoculars",
    talking_points_result: RenderResult | None = None,
) -> FullSectionRenderResult:
    """Render ALL pack sections from the Claim Registry.

    Single entry point for user-visible content. outreach_pack.py calls
    this and organizes results into OutreachPack schema + markdown.
    """
    result = FullSectionRenderResult()

    # Talking points
    if talking_points_result:
        result.talking_points = talking_points_result.sentences
    else:
        fb = render_deterministic_fallback(claims_builder, audience)
        result.talking_points = fb.sentences

    is_observable = claims_builder.obs.is_observable

    if is_observable:
        result.schedule = render_schedule_section(claims_builder, audience)
        result.equipment = render_equipment_section(claims_builder, equipment)
        result.safety = render_flat_section(
            claims_builder,
            ["safety.night_group", "safety.red_flashlight",
             "safety.weather_clothing", "safety.laser_caution"],
            "safety",
        )
        result.manual_checks = render_flat_section(
            claims_builder,
            ["manual_check.coordinate_source", "manual_check.twilight_accuracy",
             "manual_check.site_access", "manual_check.equipment_battery"],
            "manual_check",
        )
        result.unconfirmed = render_flat_section(
            claims_builder,
            ["unconfirmed.magnitude_missing", "unconfirmed.angular_size_missing"],
            "actions",
        )
    else:
        blocking, alternatives = render_blocking_section(claims_builder, audience)
        result.blocking = blocking
        result.alternatives = alternatives
        # Not-observable schedule
        for cid in ["schedule.cancel", "schedule.alt_consider", "schedule.indoor"]:
            claim = claims_builder.get_claim(cid)
            if claim:
                result.schedule.append(RenderedScheduleItem(
                    time_label="", activity=claim.display_value, notes="",
                    claim_ids=[cid], variant_ids=["schedule_proc_v1"],
                ))
        result.manual_checks = render_flat_section(
            claims_builder,
            ["manual_check.reschedule_verify", "manual_check.alt_equipment",
             "manual_check.notify_members"],
            "manual_check",
        )

    return result
