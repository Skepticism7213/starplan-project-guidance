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

    # P1 Batch D: when a realistic activity slot exists, the schedule shows
    # setup -> observing -> cleanup instead of the full science window.
    slot = claims_builder.obs.activity_slot
    if slot is not None:
        setup_claim = claims_builder.get_claim("activity.setup_start")
        start_claim = claims_builder.get_claim("activity.slot_start")
        end_claim = claims_builder.get_claim("activity.slot_end")
        cleanup_claim = claims_builder.get_claim("activity.cleanup_end")
        name_claim = claims_builder.get_claim("target.standard_name")

        if setup_claim:
            items.append(RenderedScheduleItem(
                time_label=setup_claim.display_value,
                activity="到达场地，设备调试与准备",
                notes="",
                claim_ids=["activity.setup_start"],
                variant_ids=["activity_setup_v1"],
            ))
        if start_claim and name_claim:
            items.append(RenderedScheduleItem(
                time_label=start_claim.display_value,
                activity=f"开始观测 {name_claim.display_value}",
                notes="",
                claim_ids=["activity.slot_start", "target.standard_name"],
                variant_ids=["activity_slot_start_v1"],
            ))
        if start_claim and end_claim:
            items.append(RenderedScheduleItem(
                time_label=f"{start_claim.display_value} ~ {end_claim.display_value}",
                activity="观测进行中",
                notes="",
                claim_ids=["activity.slot_start", "activity.slot_end"],
                variant_ids=["schedule_proc_v1"],
            ))
        if end_claim:
            items.append(RenderedScheduleItem(
                time_label=end_claim.display_value,
                activity="活动观测部分结束",
                notes="",
                claim_ids=["activity.slot_end"],
                variant_ids=["activity_slot_end_v1"],
            ))
        if cleanup_claim:
            items.append(RenderedScheduleItem(
                time_label=cleanup_claim.display_value,
                activity="收拾设备、点名、合影",
                notes="",
                claim_ids=["activity.cleanup_end"],
                variant_ids=["activity_cleanup_v1"],
            ))
        return items

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
        safety_ids = [
            "safety.night_group", "safety.red_flashlight",
            "safety.weather_clothing", "safety.laser_caution",
        ]
        if claims_builder.youth_policy_applied:
            safety_ids += [
                "safety.youth_supervision",
                "safety.youth_rollcall",
                "safety.youth_consent",
            ]
        result.safety = render_flat_section(claims_builder, safety_ids, "safety")
        manual_check_ids = [
            "manual_check.coordinate_source", "manual_check.twilight_accuracy",
            "manual_check.site_access", "manual_check.equipment_battery",
        ]
        if claims_builder.youth_policy_applied:
            manual_check_ids += [
                "manual_check.youth_consent",
                "manual_check.youth_rollcall",
            ]
        result.manual_checks = render_flat_section(
            claims_builder, manual_check_ids, "manual_check",
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
        manual_ids = [
            "manual_check.reschedule_verify",
            "manual_check.alt_equipment",
            "manual_check.notify_members",
        ]
        if claims_builder.youth_policy_applied:
            manual_ids += [
                "manual_check.youth_consent",
                "manual_check.youth_rollcall",
            ]
        result.manual_checks = render_flat_section(claims_builder, manual_ids, "manual_check")

    return result


# ── Phase A: RenderedDocument — final document-level structure ──
# Every user-visible atomic text is a RenderedBlock with full provenance.
# The Markdown serializer ONLY accepts RenderedDocument; it never touches
# target/obs objects directly. This closes C-01 (100% Claim-to-render mapping).

import hashlib as _hashlib


@dataclass
class RenderedBlock:
    """A single atomic unit of user-visible text with full claim provenance.

    final_text is the EXACT text the user sees (without Markdown formatting
    markers like #, **, -). text_hash is sha256[:12] of final_text.
    """

    block_id: str
    section: str
    final_text: str
    claim_ids: list[str]
    variant_id: str
    render_mode: str = "claim_variant"

    @property
    def text_hash(self) -> str:
        return _hashlib.sha256(self.final_text.encode("utf-8")).hexdigest()[:12]


@dataclass
class RenderedDocument:
    """Complete rendered document with every atomic text traced to Claims.

    This is the ONLY structure from which the final Markdown and render_trace
    are generated. No fact text may bypass this structure.
    """

    title_block: RenderedBlock
    metadata_blocks: list[RenderedBlock] = field(default_factory=list)
    body_blocks: list[RenderedBlock] = field(default_factory=list)

    @property
    def all_blocks(self) -> list[RenderedBlock]:
        """All blocks in document order (title + metadata + body)."""
        return [self.title_block] + self.metadata_blocks + self.body_blocks

    @property
    def sections_ordered(self) -> list[str]:
        """Unique section names in stable document order."""
        seen: list[str] = []
        for b in self.all_blocks:
            if b.section not in seen:
                seen.append(b.section)
        return seen

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        def _block_dict(b: RenderedBlock) -> dict:
            return {
                "block_id": b.block_id,
                "section": b.section,
                "final_text": b.final_text,
                "claim_ids": b.claim_ids,
                "variant_id": b.variant_id,
                "render_mode": b.render_mode,
                "text_hash": b.text_hash,
            }
        return {
            "schema_version": "2.0",
            "title_block": _block_dict(self.title_block),
            "metadata_blocks": [_block_dict(b) for b in self.metadata_blocks],
            "body_blocks": [_block_dict(b) for b in self.body_blocks],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RenderedDocument":
        """Reconstruct from a serialized dict.

        W-04 fix: the stored text_hash field is verified, not ignored.
        If the field is missing or does not match sha256(final_text)[:12],
        reconstruction raises ValueError so callers fail closed (BLOCKED).
        Tampering with final_text was already caught by bidirectional
        trace coverage; this closes the hash-field-only tamper path.
        """
        def _block_from_dict(d: dict) -> RenderedBlock:
            block = RenderedBlock(
                block_id=d["block_id"],
                section=d["section"],
                final_text=d["final_text"],
                claim_ids=d["claim_ids"],
                variant_id=d["variant_id"],
                render_mode=d.get("render_mode", "claim_variant"),
            )
            saved_hash = d.get("text_hash")
            if saved_hash is None:
                raise ValueError(
                    f"RenderedBlock '{d.get('block_id')}' is missing the "
                    f"required text_hash field (evidence chain incomplete)"
                )
            if saved_hash != block.text_hash:
                raise ValueError(
                    f"RenderedBlock '{d.get('block_id')}' text_hash mismatch: "
                    f"saved={saved_hash}, recomputed={block.text_hash} "
                    f"(serialized document was tampered with)"
                )
            return block
        return cls(
            title_block=_block_from_dict(data["title_block"]),
            metadata_blocks=[_block_from_dict(b) for b in data.get("metadata_blocks", [])],
            body_blocks=[_block_from_dict(b) for b in data.get("body_blocks", [])],
        )


# Fixed section ordering for deterministic output (closes W-03)
_SECTION_ORDER = [
    "metadata", "recommended_window", "schedule", "talking_points",
    "equipment", "safety", "manual_check", "unconfirmed",
    "blocking", "alternatives", "actions",
]

# P1 Batch D: per-view section allowlists. organizer = None means all sections.
# Views change only presentation; every block still maps to the same Claims.
_VIEW_SECTIONS: dict[str, Optional[set[str]]] = {
    "organizer": None,
    "facilitator": {
        "metadata", "recommended_window", "schedule", "talking_points",
        "equipment", "safety", "manual_check", "blocking", "alternatives",
    },
    "learner": {
        "metadata", "recommended_window", "schedule", "talking_points",
        "safety", "blocking", "alternatives",
    },
}


def _make_block(
    block_id: str, section: str, final_text: str,
    claim_ids: list[str], variant_id: str,
    render_mode: str = "claim_variant",
) -> RenderedBlock:
    """Helper to create a RenderedBlock."""
    return RenderedBlock(
        block_id=block_id, section=section, final_text=final_text,
        claim_ids=claim_ids, variant_id=variant_id, render_mode=render_mode,
    )


def render_document(
    claims_builder: AllowedClaimsBuilder,
    sections: FullSectionRenderResult,
    audience: str = "general",
    equipment: str = "binoculars",
    qwen_used: bool = False,
    view: str = "organizer",
) -> RenderedDocument:
    """Assemble the final RenderedDocument from Claim-rendered sections.

    This is the SINGLE document-level entry point. It wraps the section
    render results into RenderedBlocks with full provenance, including
    metadata blocks that were previously hard-coded in Markdown writers.

    Args:
        claims_builder: The run's Claim Registry (for meta Claims).
        sections: Pre-rendered section results from render_all_sections().
        audience: Audience description.
        equipment: Equipment type.
        qwen_used: Whether Qwen ExpressionPlan was accepted.

    Returns:
        RenderedDocument ready for serialization and trace generation.
    """
    obs = claims_builder.obs
    is_observable = obs.is_observable

    # ── Title block ──
    title_claim = claims_builder.get_claim("meta.title")
    if title_claim:
        title_text = title_claim.display_value
        title_claims = ["meta.title"]
    else:
        # Defensive fallback (should not happen after claims.py update)
        name = claims_builder.target.standard_name
        title_text = f"{name} 观测活动包" if is_observable else f"{name} 观测取消/改期通知"
        title_claims = ["target.standard_name"]
    title_block = _make_block("meta.title", "metadata", title_text, title_claims, "meta_passthrough_v1")

    # ── Metadata blocks ──
    metadata_blocks: list[RenderedBlock] = []

    meta_items = [
        ("meta.audience", f"受众: {audience}", "meta_passthrough_v1"),
        ("meta.date", f"日期: {obs.date_range[0]}" if obs.date_range else "日期: 未指定", "meta_passthrough_v1"),
        ("meta.location", f"地点: {obs.location_name}", "meta_passthrough_v1"),
        ("meta.observable_status", f"可观测: {'是' if is_observable else '否'}", "meta_passthrough_v1"),
    ]
    # Generation method depends on qwen_used (determined after Qwen phase)
    if qwen_used:
        gen_text = "讲解生成: Qwen 模型（经 Claim 验证）"
        gen_claim = "meta.generation_method.qwen"
    else:
        gen_text = "讲解生成: 确定性模板"
        gen_claim = "meta.generation_method.template"
    meta_items.append((gen_claim, gen_text, "meta_passthrough_v1"))

    for claim_id, text, variant in meta_items:
        # Verify claim exists in registry; use it if so
        claim = claims_builder.get_claim(claim_id)
        cids = [claim_id] if claim else [claim_id]  # ID recorded even if late-added
        metadata_blocks.append(_make_block(claim_id, "metadata", text, cids, variant))

    # ── Body blocks ──
    body_blocks: list[RenderedBlock] = []

    if is_observable:
        # Recommended window
        if obs.recommended_window:
            w = obs.recommended_window.window
            rw_time = f"时间: {w.start.strftime('%H:%M')} ~ {w.end.strftime('%H:%M')}"
            rw_peak = f"峰值高度角: {obs.recommended_window.peak_altitude_deg:.1f}°"
            rw_reason = f"理由: {obs.recommended_window.reason}"
            body_blocks.append(_make_block(
                "obs.recommended_window_time", "recommended_window", rw_time,
                ["obs.recommended_window"], "recommended_window_time_v1",
            ))
            body_blocks.append(_make_block(
                "obs.peak_altitude", "recommended_window", rw_peak,
                ["obs.peak_altitude"], "recommended_window_peak_v1",
            ))
            body_blocks.append(_make_block(
                "obs.recommended_window_reason", "recommended_window", rw_reason,
                ["obs.recommended_window"], "recommended_window_reason_v1",
            ))

        # Schedule
        for i, si in enumerate(sections.schedule):
            text = f"{si.time_label}: {si.activity}" if si.time_label else si.activity
            if si.notes:
                text += f"（{si.notes}）"
            body_blocks.append(_make_block(
                f"schedule.{i}", "schedule", text,
                si.claim_ids, si.variant_ids[0] if si.variant_ids else "schedule_proc_v1",
            ))

        # Talking points
        for i, s in enumerate(sections.talking_points):
            body_blocks.append(_make_block(
                f"talking_points.{i}", "talking_points", s.text,
                s.claim_ids, s.variant_id,
            ))

        # Equipment (quantity + notes included in final_text)
        for i, ei in enumerate(sections.equipment):
            text = f"{ei.item} x {ei.quantity}"
            if ei.notes:
                text += f"（{ei.notes}）"
            body_blocks.append(_make_block(
                f"equipment.{i}", "equipment", text,
                ei.claim_ids, ei.variant_ids[0] if ei.variant_ids else "equipment_item_v1",
            ))

        # Safety
        for i, s in enumerate(sections.safety):
            body_blocks.append(_make_block(
                f"safety.{i}", "safety", s.text, s.claim_ids, s.variant_id,
            ))

        # Manual checks
        for i, s in enumerate(sections.manual_checks):
            body_blocks.append(_make_block(
                f"manual_check.{i}", "manual_check", s.text, s.claim_ids, s.variant_id,
            ))

        # Unconfirmed
        for i, s in enumerate(sections.unconfirmed):
            body_blocks.append(_make_block(
                f"unconfirmed.{i}", "unconfirmed", s.text, s.claim_ids, s.variant_id,
            ))

    else:
        # Not-observable: blocking + alternatives + schedule + manual checks
        for i, s in enumerate(sections.blocking):
            body_blocks.append(_make_block(
                f"blocking.{i}", "blocking", s.text, s.claim_ids, s.variant_id,
            ))
        for i, s in enumerate(sections.alternatives):
            body_blocks.append(_make_block(
                f"alternatives.{i}", "alternatives", s.text, s.claim_ids, s.variant_id,
            ))
        for i, si in enumerate(sections.schedule):
            text = f"{si.time_label}: {si.activity}" if si.time_label else si.activity
            if si.notes:
                text += f"（{si.notes}）"
            body_blocks.append(_make_block(
                f"schedule.{i}", "schedule", text,
                si.claim_ids, si.variant_ids[0] if si.variant_ids else "schedule_proc_v1",
            ))
        for i, s in enumerate(sections.manual_checks):
            body_blocks.append(_make_block(
                f"manual_check.{i}", "manual_check", s.text, s.claim_ids, s.variant_id,
            ))

    # P1 Batch D: filter blocks by view. All remaining blocks keep the same
    # claim_ids/variants, so facts are identical across views by construction.
    allowed_sections = _VIEW_SECTIONS.get(view)
    if allowed_sections is not None:
        body_blocks = [b for b in body_blocks if b.section in allowed_sections]

    return RenderedDocument(
        title_block=title_block,
        metadata_blocks=metadata_blocks,
        body_blocks=body_blocks,
    )


def serialize_document_md(doc: RenderedDocument, is_observable: bool = True) -> str:
    """Serialize a RenderedDocument to Markdown.

    This function ONLY reads from RenderedDocument blocks. It NEVER accesses
    target, obs_result, or any schema object directly. All fact text is already
    in the blocks' final_text fields.

    The Markdown formatting markers (#, **, -) are layout, not facts. The
    atomic fact content is block.final_text.
    """
    lines: list[str] = []

    # Title
    lines.append(f"# {doc.title_block.final_text}")
    lines.append("")

    # Metadata
    for block in doc.metadata_blocks:
        lines.append(f"**{block.final_text.split(':')[0]}**: {block.final_text.split(':', 1)[1].strip()}  "
                     if ":" in block.final_text else f"**{block.final_text}**  ")
    lines.append("")

    if is_observable:
        # Recommended window
        rw_blocks = [b for b in doc.body_blocks if b.section == "recommended_window"]
        if rw_blocks:
            lines.append("## 推荐观测时段")
            lines.append("")
            for b in rw_blocks:
                lines.append(f"- **{b.final_text.split(':')[0]}**: {b.final_text.split(':', 1)[1].strip()}")
            lines.append("")

        # Schedule
        sched_blocks = [b for b in doc.body_blocks if b.section == "schedule"]
        if sched_blocks:
            lines.append("## 活动流程")
            lines.append("")
            for b in sched_blocks:
                lines.append(f"- {b.final_text}")
            lines.append("")

        # Talking points
        tp_blocks = [b for b in doc.body_blocks if b.section == "talking_points"]
        if tp_blocks:
            lines.append("## 讲解要点")
            lines.append("")
            for b in tp_blocks:
                lines.append(f"- {b.final_text}")
            lines.append("")

        # Equipment
        eq_blocks = [b for b in doc.body_blocks if b.section == "equipment"]
        if eq_blocks:
            lines.append("## 设备清单")
            lines.append("")
            for b in eq_blocks:
                lines.append(f"- {b.final_text}")
            lines.append("")

        # Safety
        safety_blocks = [b for b in doc.body_blocks if b.section == "safety"]
        if safety_blocks:
            lines.append("## 安全提示")
            lines.append("")
            for b in safety_blocks:
                lines.append(f"- {b.final_text}")
            lines.append("")

        # Manual checks
        mc_blocks = [b for b in doc.body_blocks if b.section == "manual_check"]
        if mc_blocks:
            lines.append("## 人工核对项")
            lines.append("")
            for b in mc_blocks:
                lines.append(f"- [ ] {b.final_text}")
            lines.append("")

        # Unconfirmed
        uc_blocks = [b for b in doc.body_blocks if b.section == "unconfirmed"]
        if uc_blocks:
            lines.append("## 待确认项")
            lines.append("")
            for b in uc_blocks:
                lines.append(f"- {b.final_text}")
            lines.append("")

    else:
        # Not-observable layout
        blocking_blocks = [b for b in doc.body_blocks if b.section == "blocking"]
        alt_blocks = [b for b in doc.body_blocks if b.section == "alternatives"]
        sched_blocks = [b for b in doc.body_blocks if b.section == "schedule"]
        mc_blocks = [b for b in doc.body_blocks if b.section == "manual_check"]

        if blocking_blocks:
            lines.append("## 说明要点")
            lines.append("")
            for b in blocking_blocks:
                lines.append(f"- {b.final_text}")
            lines.append("")

        if alt_blocks:
            lines.append("## 替代建议")
            lines.append("")
            for b in alt_blocks:
                lines.append(f"- {b.final_text}")
            lines.append("")

        if sched_blocks:
            lines.append("## 建议安排")
            lines.append("")
            for b in sched_blocks:
                lines.append(f"- {b.final_text}")
            lines.append("")

        if mc_blocks:
            lines.append("## 人工核对项")
            lines.append("")
            for b in mc_blocks:
                lines.append(f"- [ ] {b.final_text}")
            lines.append("")

    return "\n".join(lines)
