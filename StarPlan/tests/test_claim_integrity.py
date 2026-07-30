"""
P0-A: Claim Integrity Tampering Tests.

Verifies that the sealed Claim Registry detects all four classes of tampering:
  1. Claim value mutation (display_value or canonical changed after build)
  2. Source data drift (live target/obs object modified after construction)
  3. Derivation rule version change (DERIVATION_RULES modified after build)
  4. Template modification (SENTENCE_VARIANTS content changed after build)

Each test must FAIL before the P0-A fix and PASS after.
"""

import sys
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starplan_skills.claims import AllowedClaimsBuilder, DERIVATION_RULES
from starplan_skills.expression_validator import validate_expression_plan
from starplan_skills.schemas import (
    ExpressionPlan,
    MoonInfo,
    ObservabilityResult,
    RecommendedWindow,
    ResolvedTarget,
    SelectedClaim,
    TimeWindow,
    TwilightInfo,
)


# ── Fixtures ──

@pytest.fixture
def target():
    return ResolvedTarget(
        standard_name="M31",
        aliases=["仙女座星系"],
        target_type="deep_sky",
        ra_deg=10.6847,
        dec_deg=41.2687,
        visual_magnitude=3.4,
        angular_size_arcmin=[178.0, 63.0],
        constellation="Andromeda",
        source="built_in_catalog_v1",
        confidence=0.98,
    )


@pytest.fixture
def obs_result():
    w = TimeWindow(start=datetime(2026, 10, 17, 20, 30), end=datetime(2026, 10, 17, 23, 0), duration_minutes=150)
    return ObservabilityResult(
        is_observable=True,
        target_name="M31",
        location_name="济南_四门塔",
        date_range=[date(2026, 10, 17)],
        recommended_window=RecommendedWindow(window=w, peak_altitude_deg=72.5, peak_airmass=1.05, reason="test"),
        twilight=TwilightInfo(astronomical_twilight_end=datetime(2026, 10, 17, 19, 15)),
        moon_info=MoonInfo(phase_fraction=0.35, min_separation_deg=45.2, impact_assessment="low"),
    )


@pytest.fixture
def builder(target, obs_result):
    b = AllowedClaimsBuilder(target, obs_result, "济南_四门塔", "天文社新成员", "binoculars")
    b.build()
    return b


# ── Test 1: Claim value mutation ──

class TestClaimValueTampering:
    """Modifying a claim after build() must be detected."""

    def test_modify_display_value(self, builder):
        """Change display_value of a claim; verify_integrity must fail."""
        claim = builder.get_claim("target.visual_magnitude")
        assert claim is not None
        claim.display_value = "99.9"  # tamper

        violations = builder.verify_integrity()
        assert len(violations) > 0
        assert any("hash mismatch" in v.lower() or "modified" in v.lower() for v in violations)

    def test_modify_text_value(self, builder):
        """Change text_value; must also be detected."""
        claim = builder.get_claim("target.standard_name")
        assert claim is not None
        claim.text_value = "M999"  # tamper

        violations = builder.verify_integrity()
        assert len(violations) > 0

    def test_validator_blocks_tampered_registry(self, builder):
        """ExpressionPlan validation must fail on tampered registry."""
        claim = builder.get_claim("target.visual_magnitude")
        claim.display_value = "99.9"  # tamper

        plan = ExpressionPlan(
            schema_version="1.0",
            selected_claims=[
                SelectedClaim(claim_id="target.standard_name", sentence_variant_id="target_name_v1"),
            ],
        )
        result = validate_expression_plan(plan, builder, expected_scope_target="M31")
        assert not result.passed
        assert any("integrity" in e.step_name.lower() or "Integrity" in e.message for e in result.errors)


# ── Test 2: Source data drift ──

class TestSourceDataDrift:
    """Modifying the live source object after construction must be detected."""

    def test_target_magnitude_drift(self, builder, target):
        """Change target.visual_magnitude after builder construction."""
        # The builder holds a reference to target; mutate it
        target.visual_magnitude = 99.9

        violations = builder.verify_integrity()
        assert len(violations) > 0
        assert any("source drift" in v.lower() or "Target" in v for v in violations)

    def test_obs_result_drift(self, builder, obs_result):
        """Change obs_result after builder construction."""
        obs_result.is_observable = False  # mutate

        violations = builder.verify_integrity()
        assert len(violations) > 0
        assert any("source drift" in v.lower() or "Observability" in v for v in violations)


# ── Test 3: Derivation rule change ──

class TestDerivationRuleTampering:
    """Modifying DERIVATION_RULES after build must be detected."""

    def test_rule_version_bump(self, builder):
        """Bump a rule version; verify_integrity must detect it."""
        original = DERIVATION_RULES["visibility.naked_eye"]
        DERIVATION_RULES["visibility.naked_eye"] = "v999"  # tamper
        try:
            violations = builder.verify_integrity()
            assert len(violations) > 0
            assert any("rule" in v.lower() or "Derivation" in v for v in violations)
        finally:
            DERIVATION_RULES["visibility.naked_eye"] = original  # restore


# ── Test 4: Template modification ──

class TestTemplateTampering:
    """Modifying template content is detectable via saved hash."""

    def test_template_hash_in_save(self, builder, tmp_path):
        """save() records template_set_hash; modifying templates changes it."""
        from starplan_skills.templates import SENTENCE_VARIANTS

        # Save original
        builder.save(tmp_path)
        import json
        original_data = json.loads((tmp_path / "claims.json").read_text(encoding="utf-8"))
        original_template_hash = original_data["template_set_hash"]

        # Tamper with a template
        key = list(SENTENCE_VARIANTS.keys())[0]
        original_template = SENTENCE_VARIANTS[key]["template"]
        SENTENCE_VARIANTS[key]["template"] = "TAMPERED TEMPLATE"
        try:
            # Re-save and check hash changed
            builder.save(tmp_path)
            tampered_data = json.loads((tmp_path / "claims.json").read_text(encoding="utf-8"))
            assert tampered_data["template_set_hash"] != original_template_hash
        finally:
            SENTENCE_VARIANTS[key]["template"] = original_template  # restore


# ── Test 5: Normal operation — hash stability ──

class TestHashStability:
    """Normal builds produce stable hashes; order doesn't matter."""

    def test_repeated_build_same_hash(self, target, obs_result):
        """Two builds from same input produce the same sealed hash."""
        b1 = AllowedClaimsBuilder(target, obs_result, "济南_四门塔", "天文社新成员", "binoculars")
        b1.build()
        b2 = AllowedClaimsBuilder(target, obs_result, "济南_四门塔", "天文社新成员", "binoculars")
        b2.build()
        assert b1.registry_hash == b2.registry_hash

    def test_clean_registry_passes_integrity(self, builder):
        """Untampered registry passes verify_integrity with zero violations."""
        violations = builder.verify_integrity()
        assert violations == []

    def test_sealed_hash_not_dynamic(self, builder):
        """registry_hash returns sealed value, not a fresh computation."""
        h1 = builder.registry_hash
        # Mutate a claim
        claim = builder.get_claim("target.standard_name")
        claim.text_value = "HACKED"
        # Sealed hash must NOT change (it's frozen)
        h2 = builder.registry_hash
        assert h1 == h2, "registry_hash must be sealed, not dynamic"
        # But verify_integrity must detect the mutation
        assert len(builder.verify_integrity()) > 0
