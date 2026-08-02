"""
Tests for Phase B: Claim Registry (AllowedClaimsBuilder).

Verifies:
  - Claims are built correctly from target + observability data
  - Claim types are assigned correctly (observed_fact / derived_fact / unconfirmed / prohibited)
  - Prohibited claims exist for known hallucination vectors
  - claims.json is saved correctly
  - Template rendering works with claim display_values
"""

import json
import tempfile
from datetime import date, datetime
from pathlib import Path

import pytest

from starplan_skills.claims import AllowedClaimsBuilder, DERIVATION_RULES
from starplan_skills.schemas import (
    Claim,
    ClaimType,
    HourlyData,
    MoonInfo,
    ObservabilityResult,
    RecommendedWindow,
    ResolvedTarget,
    TimeWindow,
    TwilightInfo,
    ValidityScope,
)
from starplan_skills.templates import (
    SENTENCE_VARIANTS,
    render_sentence,
    validate_variant_id,
)


# ── Fixtures ──

@pytest.fixture
def sample_target():
    """M31-like target with full data."""
    return ResolvedTarget(
        standard_name="M31",
        aliases=["仙女座星系", "Andromeda Galaxy"],
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
def sample_target_no_mag():
    """Target with missing magnitude (triggers unconfirmed)."""
    return ResolvedTarget(
        standard_name="NGC7000",
        aliases=["北美洲星云"],
        target_type="deep_sky",
        ra_deg=315.0,
        dec_deg=44.0,
        visual_magnitude=None,
        angular_size_arcmin=None,
        constellation="Cygnus",
        source="built_in_catalog_v1",
        confidence=0.95,
    )


@pytest.fixture
def observable_result():
    """Observable result with recommended window."""
    w_start = datetime(2026, 10, 17, 20, 30)
    w_end = datetime(2026, 10, 17, 23, 0)
    return ObservabilityResult(
        is_observable=True,
        target_name="M31",
        location_name="济南_四门塔",
        date_range=[date(2026, 10, 17)],
        visibility_windows=[TimeWindow(start=w_start, end=w_end, duration_minutes=150)],
        recommended_window=RecommendedWindow(
            window=TimeWindow(start=w_start, end=w_end, duration_minutes=150),
            peak_altitude_deg=72.5,
            peak_airmass=1.05,
            reason="高度角最高时段",
        ),
        hourly_data=[],
        twilight=TwilightInfo(
            astronomical_twilight_end=datetime(2026, 10, 17, 19, 15),
            astronomical_twilight_start=datetime(2026, 10, 18, 5, 30),
        ),
        moon_info=MoonInfo(
            phase_fraction=0.35,
            min_separation_deg=45.2,
            impact_assessment="low",
        ),
    )


@pytest.fixture
def not_observable_result():
    """Not-observable result."""
    return ObservabilityResult(
        is_observable=False,
        target_name="M42",
        location_name="北京",
        date_range=[date(2026, 7, 25)],
        visibility_windows=[],
        recommended_window=None,
        hourly_data=[],
        twilight=TwilightInfo(),
        moon_info=MoonInfo(phase_fraction=0.8),
    )


# ── Tests: Claim building ──

class TestAllowedClaimsBuilder:
    def test_builds_claims_for_observable(self, sample_target, observable_result):
        builder = AllowedClaimsBuilder(
            target=sample_target,
            obs_result=observable_result,
            location_id="济南_四门塔",
            audience="天文社新成员",
            equipment="binoculars",
        )
        claims = builder.build()
        assert len(claims) > 0
        # All claims should have valid IDs
        for c in claims:
            assert c.claim_id
            assert c.claim_type != ClaimType.PROHIBITED

    def test_claim_ids_unique(self, sample_target, observable_result):
        builder = AllowedClaimsBuilder(
            target=sample_target,
            obs_result=observable_result,
            location_id="济南_四门塔",
        )
        claims = builder.build()
        ids = [c.claim_id for c in claims]
        assert len(ids) == len(set(ids)), "Duplicate claim IDs found"

    def test_target_claims_are_observed_fact(self, sample_target, observable_result):
        builder = AllowedClaimsBuilder(
            target=sample_target,
            obs_result=observable_result,
            location_id="济南_四门塔",
        )
        builder.build()
        name_claim = builder.get_claim("target.standard_name")
        assert name_claim is not None
        assert name_claim.claim_type == ClaimType.OBSERVED_FACT
        assert name_claim.display_value == "M31"

    def test_observability_claims_present(self, sample_target, observable_result):
        builder = AllowedClaimsBuilder(
            target=sample_target,
            obs_result=observable_result,
            location_id="济南_四门塔",
        )
        builder.build()
        alt_claim = builder.get_claim("obs.peak_altitude")
        assert alt_claim is not None
        assert alt_claim.canonical_value == 72.5
        assert "72.5" in alt_claim.display_value

    def test_derived_naked_eye_claim(self, sample_target, observable_result):
        """M31 mag=3.4 → naked eye visible."""
        builder = AllowedClaimsBuilder(
            target=sample_target,
            obs_result=observable_result,
            location_id="济南_四门塔",
        )
        builder.build()
        claim = builder.get_claim("derived.visibility.naked_eye")
        assert claim is not None
        assert claim.claim_type == ClaimType.DERIVED_FACT
        assert claim.text_value == "yes"
        assert "naked_eye" in claim.derivation_rule

    def test_derived_beginner_friendly(self, sample_target, observable_result):
        """M31 mag=3.4, size=178' → beginner friendly."""
        builder = AllowedClaimsBuilder(
            target=sample_target,
            obs_result=observable_result,
            location_id="济南_四门塔",
        )
        builder.build()
        claim = builder.get_claim("derived.visibility.beginner_friendly")
        assert claim is not None
        assert claim.text_value == "yes"

    def test_missing_magnitude_creates_unconfirmed(self, sample_target_no_mag, not_observable_result):
        """Missing magnitude → unconfirmed claims."""
        builder = AllowedClaimsBuilder(
            target=sample_target_no_mag,
            obs_result=not_observable_result,
            location_id="北京",
        )
        builder.build()
        mag_claim = builder.get_claim("target.visual_magnitude")
        assert mag_claim is not None
        assert mag_claim.claim_type == ClaimType.UNCONFIRMED
        assert "待确认" in mag_claim.display_value

    def test_prohibited_claims_exist(self, sample_target, observable_result):
        """Prohibited set must include known hallucination vectors."""
        builder = AllowedClaimsBuilder(
            target=sample_target,
            obs_result=observable_result,
            location_id="济南_四门塔",
        )
        builder.build()
        prohibited_ids = [c.claim_id for c in builder._prohibited]
        assert "prohibited.distance_lightyears" in prohibited_ids
        assert "prohibited.physical_nature" in prohibited_ids
        assert "prohibited.weather_prediction" in prohibited_ids

    def test_not_observable_skips_obs_claims(self, sample_target, not_observable_result):
        """Not-observable branch should not have peak_altitude claims."""
        builder = AllowedClaimsBuilder(
            target=sample_target,
            obs_result=not_observable_result,
            location_id="北京",
        )
        builder.build()
        assert builder.get_claim("obs.peak_altitude") is None
        status = builder.get_claim("obs.is_observable")
        assert status is not None
        assert status.text_value == "no"

    def test_validity_scope_correct(self, sample_target, observable_result):
        builder = AllowedClaimsBuilder(
            target=sample_target,
            obs_result=observable_result,
            location_id="济南_四门塔",
        )
        builder.build()
        claim = builder.get_claim("target.standard_name")
        assert claim.validity_scope.target == "M31"
        assert claim.validity_scope.location_id == "济南_四门塔"
        assert claim.validity_scope.date == "2026-10-17"
        assert claim.validity_scope.business_branch == "observable"


# ── Tests: claims.json serialization ──

class TestClaimsSave:
    def test_save_creates_file(self, sample_target, observable_result):
        builder = AllowedClaimsBuilder(
            target=sample_target,
            obs_result=observable_result,
            location_id="济南_四门塔",
        )
        builder.build()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = builder.save(Path(tmpdir))
            assert Path(path).exists()
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            assert data["schema_version"] == "1.1"
            assert len(data["claims"]) > 0
            assert len(data["prohibited"]) > 0
            assert "registry_hash" in data

    def test_registry_hash_stable(self, sample_target, observable_result):
        """Same input → same hash (deterministic)."""
        b1 = AllowedClaimsBuilder(sample_target, observable_result, "济南_四门塔")
        b1.build()
        b2 = AllowedClaimsBuilder(sample_target, observable_result, "济南_四门塔")
        b2.build()
        assert b1._compute_registry_hash() == b2._compute_registry_hash()


# ── Tests: Template rendering ──

class TestTemplateRendering:
    def test_all_variant_ids_in_library(self, sample_target, observable_result):
        """Every allowed_variant_id in claims must exist in SENTENCE_VARIANTS."""
        builder = AllowedClaimsBuilder(
            target=sample_target,
            obs_result=observable_result,
            location_id="济南_四门塔",
        )
        builder.build()
        for claim in builder.allowed_claims:
            for vid in claim.allowed_variant_ids:
                assert vid in SENTENCE_VARIANTS, (
                    f"Claim '{claim.claim_id}' references variant '{vid}' "
                    f"not in SENTENCE_VARIANTS"
                )

    def test_render_sentence_basic(self):
        result = render_sentence("target_name_v1", "M31")
        assert result == "本次活动我们要观测的是 M31"

    def test_render_sentence_unknown_variant(self):
        result = render_sentence("nonexistent_v99", "test")
        assert result is None

    def test_validate_variant_id(self):
        assert validate_variant_id("target_name_v1", ["target_name_v1", "target_name_v2"])
        assert not validate_variant_id("target_name_v1", ["target_name_v2"])
        assert not validate_variant_id("fake_v1", ["fake_v1"])
