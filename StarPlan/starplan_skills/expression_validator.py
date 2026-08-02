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
        # Check prohibited set first (specific diagnostic)
        if claims_builder.is_prohibited(sc.claim_id):
            issues.append(ValidationIssue(
                step=3, step_name="claim_id_allowed",
                severity="error",
                message=f"PROHIBITED claim '{sc.claim_id}' selected — forbidden for this run",
                claim_id=sc.claim_id,
            ))
            continue
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

    # ── Step 8: Registry integrity (P0-A) ──
    # Delegates to the builder's verify_integrity() which checks:
    #   1. Claims hash vs sealed hash (claim mutation)
    #   2. Source snapshots vs live objects (source drift)
    #   3. Derivation rules unchanged
    #   4. Template set unchanged
    # Any violation is a blocking error — no rendering allowed.
    integrity_violations = claims_builder.verify_integrity()
    for violation in integrity_violations:
        issues.append(ValidationIssue(
            step=8, step_name="integrity",
            severity="error",
            message=f"Integrity violation: {violation}",
            claim_id=None,
        ))

    # ── Final verdict ──
    passed = len([i for i in issues if i.severity == "error"]) == 0
    return ValidationResult(passed=passed, issues=issues, warnings=warnings)


# ── Phase A: Post-render Delivery Contract Validation ──
# Closes C-01 (#4 bidirectional acceptance) and C-02 (#1 #2 fail-closed gate).
# Called by runner.py finalize BEFORE setting terminal status.


def validate_delivery_contract(
    run_dir,
    rendered_document,
    claims_builder,
    final_markdown: str | None = None,
    blocked_content: str | None = None,
) -> ValidationResult:
    """Validate the delivery contract for a completed render.

    This is the POST-render gate: verifies that the final delivered document
    is fully traced to Claims with bidirectional coverage. Any failure means
    the run must be BLOCKED (not delivered).

    Checks (Phase A):
      D1. Required artifacts exist (claims.json, outreach_pack.md,
          render_trace.json, sentence_claim_map.json, expression_plan.json)
      D2. render_trace.json is valid JSON with expected schema
      D3. Every block's claim_ids exist in registry and are not PROHIBITED;
          variant_id is in the claim's allowed_variant_ids
      D4. Every block's text_hash matches sha256[:12] of final_text
      D5. Bidirectional coverage: every trace entry appears in final Markdown;
          every atomic fact line in Markdown appears in trace
      D6. Blocked content (Qwen raw text) does not leak into final Markdown
      D7. sentence_claim_map.json is consistent with trace

    Args:
        run_dir: Path to the run directory.
        rendered_document: The RenderedDocument that was serialized.
        claims_builder: The run's Claim Registry.
        final_markdown: The actual Markdown string written to file.
            If None, reads from run_dir/outreach_pack.md.
        blocked_content: Qwen's raw free text (must NOT appear in output).

    Returns:
        ValidationResult. If passed=False, caller MUST set BLOCKED.
    """
    import hashlib
    import json
    from pathlib import Path

    from .schemas import ClaimType

    run_dir = Path(run_dir)
    issues: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    # ── D1: Required artifacts exist ──
    required_artifacts = [
        "claims.json", "outreach_pack.md", "render_trace.json",
        "sentence_claim_map.json", "expression_plan.json",
    ]
    for fname in required_artifacts:
        if not (run_dir / fname).exists():
            issues.append(ValidationIssue(
                step=1, step_name="artifact_exists",
                severity="error",
                message=f"Required artifact missing: {fname}",
            ))

    # If critical artifacts missing, cannot proceed with further checks
    if issues:
        return ValidationResult(passed=False, issues=issues, warnings=warnings)

    # ── D2: render_trace.json is valid JSON ──
    trace_path = run_dir / "render_trace.json"
    try:
        trace_data = json.loads(trace_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        issues.append(ValidationIssue(
            step=2, step_name="trace_valid_json",
            severity="error",
            message=f"render_trace.json is not valid JSON: {e}",
        ))
        return ValidationResult(passed=False, issues=issues, warnings=warnings)

    trace_sentences = trace_data.get("sentences", [])
    if not trace_sentences:
        issues.append(ValidationIssue(
            step=2, step_name="trace_valid_json",
            severity="error",
            message="render_trace.json contains no sentences",
        ))

    # ── D3: Claim IDs exist and variants are allowed ──
    for block in rendered_document.all_blocks:
        for cid in block.claim_ids:
            claim = claims_builder.get_claim(cid)
            if claim is None:
                issues.append(ValidationIssue(
                    step=3, step_name="claim_exists",
                    severity="error",
                    message=f"Block '{block.block_id}' references unknown claim_id '{cid}'",
                    claim_id=cid,
                ))
            elif claim.claim_type == ClaimType.PROHIBITED:
                issues.append(ValidationIssue(
                    step=3, step_name="claim_not_prohibited",
                    severity="error",
                    message=f"Block '{block.block_id}' references PROHIBITED claim '{cid}'",
                    claim_id=cid,
                ))
            elif block.variant_id and block.variant_id not in claim.allowed_variant_ids:
                # Only check if variant is non-empty and claim has specific allowlist
                if claim.allowed_variant_ids and block.variant_id not in claim.allowed_variant_ids:
                    issues.append(ValidationIssue(
                        step=3, step_name="variant_allowed",
                        severity="error",
                        message=(
                            f"Block '{block.block_id}' uses variant '{block.variant_id}' "
                            f"not in claim '{cid}' allowed_variant_ids"
                        ),
                        claim_id=cid,
                        variant_id=block.variant_id,
                    ))

    # ── D4: Hash integrity ──
    for block in rendered_document.all_blocks:
        expected_hash = hashlib.sha256(block.final_text.encode("utf-8")).hexdigest()[:12]
        if block.text_hash != expected_hash:
            issues.append(ValidationIssue(
                step=4, step_name="hash_integrity",
                severity="error",
                message=(
                    f"Block '{block.block_id}' hash mismatch: "
                    f"stored={block.text_hash}, computed={expected_hash}"
                ),
            ))

    # Also verify trace entries match document blocks
    doc_hashes = {b.text_hash for b in rendered_document.all_blocks}
    for entry in trace_sentences:
        if entry.get("text_hash") not in doc_hashes:
            issues.append(ValidationIssue(
                step=4, step_name="trace_hash_consistency",
                severity="error",
                message=(
                    f"Trace entry '{entry.get('sentence_id')}' hash "
                    f"'{entry.get('text_hash')}' not in RenderedDocument"
                ),
            ))

    # ── D5: Bidirectional coverage ──
    if final_markdown is None:
        md_path = run_dir / "outreach_pack.md"
        if md_path.exists():
            final_markdown = md_path.read_text(encoding="utf-8")
        else:
            final_markdown = ""

    if final_markdown:
        # Extract atomic fact lines from Markdown (strip formatting markers)
        md_facts = _extract_atomic_facts(final_markdown)
        trace_texts = {entry.get("text", "") for entry in trace_sentences}

        # Forward: every trace text must appear in Markdown facts
        for entry in trace_sentences:
            text = entry.get("text", "")
            if text and text not in md_facts:
                issues.append(ValidationIssue(
                    step=5, step_name="bidirectional_trace_to_md",
                    severity="error",
                    message=(
                        f"Trace entry '{entry.get('sentence_id')}' text not found "
                        f"in final Markdown: '{text[:60]}...'"
                    ),
                ))

        # Backward: every Markdown fact must appear in trace
        for fact in md_facts:
            if fact not in trace_texts:
                issues.append(ValidationIssue(
                    step=5, step_name="bidirectional_md_to_trace",
                    severity="error",
                    message=f"Markdown fact not in trace: '{fact[:60]}...'",
                ))

    # ── D6: Blocked content leakage ──
    if blocked_content and final_markdown:
        # Check if any substantial substring of blocked content appears
        # Use 20-char windows to detect leakage
        check_len = min(len(blocked_content), 200)
        for i in range(0, check_len - 20, 10):
            snippet = blocked_content[i:i + 20]
            if snippet in final_markdown:
                issues.append(ValidationIssue(
                    step=6, step_name="blocked_leakage",
                    severity="error",
                    message=f"Blocked Qwen content leaked into final Markdown: '{snippet}...'",
                ))
                break  # One leak is enough to block

    # ── D7: sentence_claim_map consistency ──
    sc_map_path = run_dir / "sentence_claim_map.json"
    if sc_map_path.exists():
        try:
            sc_map = json.loads(sc_map_path.read_text(encoding="utf-8"))
            for block in rendered_document.all_blocks:
                if block.final_text in sc_map:
                    if sc_map[block.final_text] != block.claim_ids:
                        warnings.append(ValidationIssue(
                            step=7, step_name="sc_map_consistency",
                            severity="warning",
                            message=(
                                f"sentence_claim_map mismatch for block '{block.block_id}': "
                                f"map={sc_map[block.final_text]}, doc={block.claim_ids}"
                            ),
                        ))
        except (json.JSONDecodeError, UnicodeDecodeError):
            warnings.append(ValidationIssue(
                step=7, step_name="sc_map_consistency",
                severity="warning",
                message="sentence_claim_map.json is not valid JSON (non-blocking)",
            ))

    # ── Final verdict ──
    passed = len([i for i in issues if i.severity == "error"]) == 0
    return ValidationResult(passed=passed, issues=issues, warnings=warnings)


def _extract_atomic_facts(markdown: str) -> set[str]:
    """Extract atomic fact texts from Markdown, stripping formatting markers.

    Removes: # headers, ** bold markers, - list markers, [ ] checkboxes,
    empty lines, and pure section headers (## ...).
    Returns the set of atomic fact strings that should match trace entries.
    """
    facts: set[str] = set()
    for line in markdown.split("\n"):
        stripped = line.strip()
        # Skip empty lines
        if not stripped:
            continue
        # Skip pure section headers (## ...) but keep title (# ...)
        if stripped.startswith("## "):
            continue
        # Title line: strip "# "
        if stripped.startswith("# "):
            facts.add(stripped[2:].strip())
            continue
        # List items: strip "- " or "- [ ] "
        if stripped.startswith("- [ ] "):
            facts.add(stripped[6:].strip())
            continue
        if stripped.startswith("- "):
            content = stripped[2:].strip()
            # Strip bold markers for metadata lines: **key**: value
            if content.startswith("**") and "**:" in content:
                # e.g. "**受众**: 天文社团" -> "受众: 天文社团"
                content = content.replace("**", "")
            facts.add(content)
            continue
        # Metadata lines without list marker: **key**: value
        if stripped.startswith("**") and "**" in stripped[2:]:
            facts.add(stripped.replace("**", "").strip())
            continue
        # Fallback: add as-is
        facts.add(stripped)
    return facts
