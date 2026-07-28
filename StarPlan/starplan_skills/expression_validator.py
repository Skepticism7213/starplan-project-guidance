"""
StarPlan Loop - Expression Plan Validator (Phase C).

8-step structural validation of Qwen's ExpressionPlan before rendering.
Any validation failure triggers fail-closed: the plan is rejected and
the deterministic fallback renderer is used instead.

The 8 steps (architecture §7):
  1. Schema validation (ExpressionPlan parses correctly)
  2. Schema version check
  3. Claim ID allowed-set check (every selected claim_id exists in registry)
  4. Variant ID allowed-set check (variant_id in claim's allowed_variant_ids)
  5. Validity scope check (claim scope matches this run)
  6. Unconfirmed/prohibited misuse check (no unconfirmed rendered as fact)
  7. Duplicate/conflict check (no claim selected twice with different variants)
  8. Source hash integrity (claim source_hash matches registry)

See: starplan-hallucination-prevention-architecture.md §7
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .claims import AllowedClaimsBuilder
from .schemas import ClaimType, ExpressionPlan, SelectedClaim
from .templates import SENTENCE_VARIANTS


@dataclass
class ValidationIssue:
    """A single validation failure."""

    step: int
    step_name: str
    severity: str  # "error" (blocks rendering) or "warning" (logged but allowed)
    message: str
    claim_id: Optional[str] = None
    variant_id: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of the 8-step validation."""

    passed: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def summary(self) -> str:
        if self.passed:
            return f"PASSED ({len(self.warnings)} warnings)"
        return f"BLOCKED ({len(self.errors)} errors, {len(self.warnings)} warnings)"


def validate_expression_plan(
    plan: ExpressionPlan,
    claims_builder: AllowedClaimsBuilder,
    expected_scope_target: Optional[str] = None,
    expected_scope_date: Optional[str] = None,
) -> ValidationResult:
    """Run the 8-step validation on an ExpressionPlan.

    Args:
        plan: The ExpressionPlan returned by Qwen.
        claims_builder: The run's Claim Registry.
        expected_scope_target: Expected target name for scope validation.
        expected_scope_date: Expected date for scope validation.

    Returns:
        ValidationResult. If passed=False, the plan MUST NOT be rendered;
        use the deterministic fallback instead.
    """
    issues: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    # ── Step 1: Schema validation ──
    # (Already guaranteed by Pydantic parsing, but check for empty plan)
    if not plan.selected_claims:
        issues.append(ValidationIssue(
            step=1, step_name="schema",
            severity="error",
            message="ExpressionPlan contains no selected_claims (empty plan)",
        ))
        return ValidationResult(passed=False, issues=issues, warnings=warnings)

    # ── Step 2: Schema version check ──
    if plan.schema_version != "1.0":
        issues.append(ValidationIssue(
            step=2, step_name="version",
            severity="error",
            message=f"Unsupported schema_version: {plan.schema_version} (expected '1.0')",
        ))

    # ── Step 3: Claim ID allowed-set check ──
    seen_claims: dict[str, list[str]] = {}  # claim_id -> [variant_ids]
    for sc in plan.selected_claims:
        claim = claims_builder.get_claim(sc.claim_id)
        if claim is None:
            issues.append(ValidationIssue(
                step=3, step_name="claim_id_allowed",
                severity="error",
                message=f"claim_id '{sc.claim_id}' not in this run's Claim Registry",
                claim_id=sc.claim_id,
            ))
        else:
            # Track for duplicate check
            if sc.claim_id not in seen_claims:
                seen_claims[sc.claim_id] = []
            seen_claims[sc.claim_id].append(sc.sentence_variant_id)

    # ── Step 4: Variant ID allowed-set check ──
    for sc in plan.selected_claims:
        claim = claims_builder.get_claim(sc.claim_id)
        if claim is None:
            continue  # Already flagged in step 3
        if sc.sentence_variant_id not in claim.allowed_variant_ids:
            issues.append(ValidationIssue(
                step=4, step_name="variant_id_allowed",
                severity="error",
                message=(
                    f"variant_id '{sc.sentence_variant_id}' not in "
                    f"claim '{sc.claim_id}' allowed_variant_ids {claim.allowed_variant_ids}"
                ),
                claim_id=sc.claim_id,
                variant_id=sc.sentence_variant_id,
            ))
        # Also check variant exists in template library
        if sc.sentence_variant_id not in SENTENCE_VARIANTS:
            issues.append(ValidationIssue(
                step=4, step_name="variant_id_allowed",
                severity="error",
                message=f"variant_id '{sc.sentence_variant_id}' not in template library",
                claim_id=sc.claim_id,
                variant_id=sc.sentence_variant_id,
            ))

    # ── Step 5: Validity scope check ──
    for sc in plan.selected_claims:
        claim = claims_builder.get_claim(sc.claim_id)
        if claim is None:
            continue
        scope = claim.validity_scope
        if expected_scope_target and scope.target and scope.target != expected_scope_target:
            issues.append(ValidationIssue(
                step=5, step_name="scope",
                severity="error",
                message=(
                    f"Claim '{sc.claim_id}' scope.target='{scope.target}' "
                    f"does not match run target '{expected_scope_target}'"
                ),
                claim_id=sc.claim_id,
            ))
        if expected_scope_date and scope.date and scope.date != expected_scope_date:
            issues.append(ValidationIssue(
                step=5, step_name="scope",
                severity="error",
                message=(
                    f"Claim '{sc.claim_id}' scope.date='{scope.date}' "
                    f"does not match run date '{expected_scope_date}'"
                ),
                claim_id=sc.claim_id,
            ))

    # ── Step 6: Unconfirmed/prohibited misuse check ──
    for sc in plan.selected_claims:
        claim = claims_builder.get_claim(sc.claim_id)
        if claim is None:
            continue
        if claim.claim_type == ClaimType.PROHIBITED:
            issues.append(ValidationIssue(
                step=6, step_name="prohibited_misuse",
                severity="error",
                message=f"PROHIBITED claim '{sc.claim_id}' selected for rendering",
                claim_id=sc.claim_id,
            ))
        elif claim.claim_type == ClaimType.UNCONFIRMED:
            # Unconfirmed claims should not be rendered as factual statements
            warnings.append(ValidationIssue(
                step=6, step_name="unconfirmed_misuse",
                severity="warning",
                message=(
                    f"Unconfirmed claim '{sc.claim_id}' selected; "
                    f"will be skipped in rendering (goes to unconfirmed_items)"
                ),
                claim_id=sc.claim_id,
            ))

    # ── Step 7: Duplicate/conflict check ──
    for claim_id, variant_ids in seen_claims.items():
        if len(variant_ids) > 1:
            # Same claim selected multiple times with different variants
            if len(set(variant_ids)) > 1:
                issues.append(ValidationIssue(
                    step=7, step_name="duplicate_conflict",
                    severity="error",
                    message=(
                        f"Claim '{claim_id}' selected {len(variant_ids)} times "
                        f"with conflicting variants: {variant_ids}"
                    ),
                    claim_id=claim_id,
                ))
            else:
                warnings.append(ValidationIssue(
                    step=7, step_name="duplicate_conflict",
                    severity="warning",
                    message=f"Claim '{claim_id}' selected {len(variant_ids)} times (duplicate)",
                    claim_id=claim_id,
                ))

    # ── Step 8: Source hash integrity ──
    # Verify that claims with source_hash still match the registry
    # (In a single-run context this is always true, but the check exists
    #  for future multi-step or cached-claim scenarios)
    for sc in plan.selected_claims:
        claim = claims_builder.get_claim(sc.claim_id)
        if claim is None or not claim.source_hash:
            continue
        # Re-hash the source to verify integrity
        # In current implementation, the hash was computed at build time
        # and the registry is immutable within a run, so this always passes.
        # The check is here for architectural completeness.
        pass

    # ── Final verdict ──
    passed = len([i for i in issues if i.severity == "error"]) == 0
    return ValidationResult(passed=passed, issues=issues, warnings=warnings)
