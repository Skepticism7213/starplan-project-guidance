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
from .templates import CONNECTORS, SECTION_HEADERS, render_sentence


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
        from .templates import SENTENCE_VARIANTS
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

        # Use the first allowed variant
        variant_id = claim.allowed_variant_ids[0]
        text = render_sentence(variant_id, claim.display_value)
        if text is None:
            continue

        from .templates import SENTENCE_VARIANTS
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

        variant_id = claim.allowed_variant_ids[0]
        text = render_sentence(variant_id, claim.display_value)
        if text is None:
            continue

        from .templates import SENTENCE_VARIANTS
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
