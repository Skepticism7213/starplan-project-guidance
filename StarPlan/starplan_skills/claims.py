"""
StarPlan Loop - Claim Registry (Phase B: hallucination prevention architecture).

Builds the AllowedClaimsBuilder: reads ResolvedTarget + ObservabilityResult,
generates a frozen set of Claims that are the ONLY facts eligible to appear
in user-visible output. Each claim has a stable ID, type, scope, source
references, and a source hash for tamper detection.

Core invariant: Qwen never produces final fact text. It only selects/orders
pre-approved claims from this registry, and the program renders deterministically.

See: starplan-hallucination-prevention-architecture.md
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Optional

from .schemas import (
    Claim,
    ClaimType,
    NUMERIC_DISPLAY_RULES,
    ObservabilityResult,
    ResolvedTarget,
    ValidityScope,
)


# ── Derivation rule versions ─────────────────────────
# Each derived_fact claim records which rule version produced it.
# When a rule changes, bump the version so old claims are invalidated.

DERIVATION_RULES = {
    "visibility.naked_eye": "v1",       # mag <= 6.0 → naked eye visible
    "visibility.binoculars": "v1",      # mag <= 10.0 → binoculars visible
    "visibility.beginner_friendly": "v1",  # mag <= 8.0 and angular_size > 5'
    "equipment.match": "v1",            # equipment vs magnitude/size
    "moon_impact.level": "v1",          # moon illumination → impact level
    "season.observable": "v1",          # target above horizon in given season
}


class AllowedClaimsBuilder:
    """Builds the Claim Registry for a single run.

    Usage:
        builder = AllowedClaimsBuilder(target, obs_result, location_id, audience, equipment)
        claims = builder.build()
        builder.save(run_dir)  # writes claims.json
    """

    def __init__(
        self,
        target: ResolvedTarget,
        obs_result: ObservabilityResult,
        location_id: str,
        audience: str = "general",
        equipment: str = "binoculars",
    ):
        self.target = target
        self.obs = obs_result
        self.location_id = location_id
        self.audience = audience
        self.equipment = equipment
        self._claims: list[Claim] = []
        self._claim_ids: set[str] = set()
        self._prohibited: list[Claim] = []

        # Fix the validity scope for this run
        obs_date = str(obs_result.date_range[0]) if obs_result.date_range else None
        self._scope = ValidityScope(
            target=target.standard_name,
            location_id=location_id,
            date=obs_date,
            timezone="Asia/Shanghai",
            business_branch="observable" if obs_result.is_observable else "not_observable",
        )

    @property
    def claims(self) -> list[Claim]:
        """All registered claims (including prohibited)."""
        return self._claims + self._prohibited

    @property
    def allowed_claims(self) -> list[Claim]:
        """Claims eligible for user-visible output (excludes prohibited)."""
        return self._claims

    @property
    def claim_ids(self) -> set[str]:
        """Set of all allowed claim IDs."""
        return self._claim_ids

    def build(self) -> list[Claim]:
        """Build the complete claim registry. Returns allowed claims."""
        self._claims = []
        self._claim_ids = set()
        self._prohibited = []

        self._build_target_claims()
        self._build_observability_claims()
        self._build_derived_visibility_claims()
        self._build_moon_claims()
        self._build_prohibited_claims()

        return self._claims

    def save(self, run_dir: Path) -> str:
        """Save claims.json to the run directory. Returns the file path."""
        claims_data = {
            "schema_version": "1.0",
            "run_scope": self._scope.model_dump(),
            "claims": [c.model_dump() for c in self._claims],
            "prohibited": [c.model_dump() for c in self._prohibited],
            "registry_hash": self._compute_registry_hash(),
        }
        path = run_dir / "claims.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(claims_data, f, ensure_ascii=False, indent=2)
        return str(path)

    def get_claim(self, claim_id: str) -> Optional[Claim]:
        """Look up a claim by ID."""
        for c in self._claims:
            if c.claim_id == claim_id:
                return c
        return None

    def get_prohibited_claim(self, claim_id: str) -> Optional[Claim]:
        """Look up a prohibited claim by ID (for validator step 6)."""
        for c in self._prohibited:
            if c.claim_id == claim_id:
                return c
        return None

    def is_prohibited(self, claim_id: str) -> bool:
        """Check if a claim_id is in the prohibited set."""
        return any(c.claim_id == claim_id for c in self._prohibited)

    def _compute_registry_hash(self) -> str:
        """Compute a sha256 hash over all claims for tamper detection."""
        content = json.dumps(
            [c.model_dump() for c in self._claims + self._prohibited],
            sort_keys=True, ensure_ascii=False,
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def _add_claim(self, claim: Claim) -> None:
        """Register a claim, ensuring no duplicate IDs."""
        if claim.claim_id in self._claim_ids:
            raise ValueError(f"Duplicate claim_id: {claim.claim_id}")
        self._claims.append(claim)
        self._claim_ids.add(claim.claim_id)

    def _add_prohibited(self, claim: Claim) -> None:
        """Register a prohibited claim."""
        self._prohibited.append(claim)

    # ── Target claims (observed_fact from catalog) ──

    def _build_target_claims(self) -> None:
        """Build claims from the resolved target (catalog data)."""
        t = self.target
        src = f"target_resolve.{t.source}"
        src_hash = self._hash_source(t.model_dump())

        # Standard name
        self._add_claim(Claim(
            claim_id="target.standard_name",
            claim_type=ClaimType.OBSERVED_FACT,
            subject=f"{t.standard_name}@{self.location_id}@{self._scope.date}",
            predicate="standard_name",
            text_value=t.standard_name,
            display_value=t.standard_name,
            validity_scope=self._scope,
            source_refs=[src],
            source_hash=src_hash,
            allowed_variant_ids=["target_name_v1", "target_name_v2"],
        ))

        # Target type
        self._add_claim(Claim(
            claim_id="target.type",
            claim_type=ClaimType.OBSERVED_FACT,
            subject=f"{t.standard_name}@{self.location_id}@{self._scope.date}",
            predicate="target_type",
            text_value=t.target_type,
            display_value=self._display_target_type(t.target_type),
            validity_scope=self._scope,
            source_refs=[src],
            source_hash=src_hash,
            allowed_variant_ids=["target_type_v1"],
        ))

        # Coordinates
        self._add_claim(Claim(
            claim_id="target.coordinates",
            claim_type=ClaimType.OBSERVED_FACT,
            subject=f"{t.standard_name}@{self.location_id}@{self._scope.date}",
            predicate="coordinates",
            canonical_value=t.ra_deg,
            text_value=f"RA={t.ra_deg:.4f}°, Dec={t.dec_deg:.4f}°",
            display_value=f"RA={t.ra_deg:.4f}°, Dec={t.dec_deg:.4f}°",
            validity_scope=self._scope,
            source_refs=[src],
            source_hash=src_hash,
            allowed_variant_ids=["coordinates_v1"],
        ))

        # Constellation
        if t.constellation:
            self._add_claim(Claim(
                claim_id="target.constellation",
                claim_type=ClaimType.OBSERVED_FACT,
                subject=f"{t.standard_name}@{self.location_id}@{self._scope.date}",
                predicate="constellation",
                text_value=t.constellation,
                display_value=t.constellation,
                validity_scope=self._scope,
                source_refs=[src],
                source_hash=src_hash,
                allowed_variant_ids=["constellation_v1", "constellation_v2"],
            ))

        # Visual magnitude
        if t.visual_magnitude is not None:
            rules = NUMERIC_DISPLAY_RULES["visual_magnitude"]
            self._add_claim(Claim(
                claim_id="target.visual_magnitude",
                claim_type=ClaimType.OBSERVED_FACT,
                subject=f"{t.standard_name}@{self.location_id}@{self._scope.date}",
                predicate="visual_magnitude",
                canonical_value=t.visual_magnitude,
                unit="mag",
                display_value=f"{t.visual_magnitude:.{rules['precision']}f}",
                display_tolerance=rules["tolerance"],
                validity_scope=self._scope,
                source_refs=[src],
                source_hash=src_hash,
                allowed_variant_ids=["magnitude_v1", "magnitude_v2"],
            ))
        else:
            # Missing magnitude → unconfirmed
            self._add_claim(Claim(
                claim_id="target.visual_magnitude",
                claim_type=ClaimType.UNCONFIRMED,
                subject=f"{t.standard_name}@{self.location_id}@{self._scope.date}",
                predicate="visual_magnitude",
                text_value="数据缺失",
                display_value="待确认（视星等数据缺失）",
                validity_scope=self._scope,
                source_refs=[src],
                allowed_variant_ids=["unconfirmed_v1"],
            ))

        # Angular size
        if t.angular_size_arcmin:
            self._add_claim(Claim(
                claim_id="target.angular_size",
                claim_type=ClaimType.OBSERVED_FACT,
                subject=f"{t.standard_name}@{self.location_id}@{self._scope.date}",
                predicate="angular_size",
                canonical_value=t.angular_size_arcmin[0],
                unit="arcmin",
                display_value=f"{t.angular_size_arcmin[0]:.1f}' × {t.angular_size_arcmin[1]:.1f}'",
                validity_scope=self._scope,
                source_refs=[src],
                source_hash=src_hash,
                allowed_variant_ids=["angular_size_v1"],
            ))
        else:
            self._add_claim(Claim(
                claim_id="target.angular_size",
                claim_type=ClaimType.UNCONFIRMED,
                subject=f"{t.standard_name}@{self.location_id}@{self._scope.date}",
                predicate="angular_size",
                text_value="数据缺失",
                display_value="待确认（角大小数据缺失）",
                validity_scope=self._scope,
                source_refs=[src],
                allowed_variant_ids=["unconfirmed_v1"],
            ))

    # ── Observability claims (observed_fact from deterministic computation) ──

    def _build_observability_claims(self) -> None:
        """Build claims from observability computation results."""
        obs = self.obs
        src = "observability_plan.astropy"
        src_hash = self._hash_source(obs.model_dump(mode="json"))

        # Observable status
        self._add_claim(Claim(
            claim_id="obs.is_observable",
            claim_type=ClaimType.OBSERVED_FACT,
            subject=f"{obs.target_name}@{self.location_id}@{self._scope.date}",
            predicate="is_observable",
            text_value="yes" if obs.is_observable else "no",
            display_value="可观测" if obs.is_observable else "不可观测",
            validity_scope=self._scope,
            source_refs=[src],
            source_hash=src_hash,
            allowed_variant_ids=["observable_status_v1"],
        ))

        if not obs.is_observable:
            return  # No further obs claims for not-observable branch

        # Peak altitude
        if obs.recommended_window:
            rules = NUMERIC_DISPLAY_RULES["altitude_deg"]
            self._add_claim(Claim(
                claim_id="obs.peak_altitude",
                claim_type=ClaimType.OBSERVED_FACT,
                subject=f"{obs.target_name}@{self.location_id}@{self._scope.date}",
                predicate="peak_altitude",
                canonical_value=obs.recommended_window.peak_altitude_deg,
                unit="deg",
                display_value=f"{obs.recommended_window.peak_altitude_deg:.{rules['precision']}f}°",
                display_tolerance=rules["tolerance"],
                validity_scope=self._scope,
                source_refs=[src],
                source_hash=src_hash,
                allowed_variant_ids=["peak_altitude_v1", "peak_altitude_v2"],
            ))

            # Peak airmass
            rules_am = NUMERIC_DISPLAY_RULES["airmass"]
            self._add_claim(Claim(
                claim_id="obs.peak_airmass",
                claim_type=ClaimType.OBSERVED_FACT,
                subject=f"{obs.target_name}@{self.location_id}@{self._scope.date}",
                predicate="peak_airmass",
                canonical_value=obs.recommended_window.peak_airmass,
                display_value=f"{obs.recommended_window.peak_airmass:.{rules_am['precision']}f}",
                display_tolerance=rules_am["tolerance"],
                validity_scope=self._scope,
                source_refs=[src],
                source_hash=src_hash,
                allowed_variant_ids=["airmass_v1"],
            ))

            # Recommended window
            w = obs.recommended_window.window
            self._add_claim(Claim(
                claim_id="obs.recommended_window",
                claim_type=ClaimType.OBSERVED_FACT,
                subject=f"{obs.target_name}@{self.location_id}@{self._scope.date}",
                predicate="recommended_window",
                text_value=f"{w.start.strftime('%H:%M')} ~ {w.end.strftime('%H:%M')}",
                display_value=f"{w.start.strftime('%H:%M')} ~ {w.end.strftime('%H:%M')}",
                validity_scope=self._scope,
                source_refs=[src],
                source_hash=src_hash,
                allowed_variant_ids=["window_v1", "window_v2"],
            ))

        # Twilight info
        if obs.twilight.astronomical_twilight_end:
            tw = obs.twilight.astronomical_twilight_end.strftime("%H:%M")
            self._add_claim(Claim(
                claim_id="obs.twilight_end",
                claim_type=ClaimType.OBSERVED_FACT,
                subject=f"{obs.target_name}@{self.location_id}@{self._scope.date}",
                predicate="astronomical_twilight_end",
                text_value=tw,
                display_value=tw,
                validity_scope=self._scope,
                source_refs=[src],
                source_hash=src_hash,
                allowed_variant_ids=["twilight_v1"],
            ))

    # ── Derived visibility claims (versioned rules) ──

    def _build_derived_visibility_claims(self) -> None:
        """Build derived_fact claims using versioned derivation rules."""
        t = self.target
        rule_ver = DERIVATION_RULES

        # Naked eye visibility
        if t.visual_magnitude is not None:
            if t.visual_magnitude <= 6.0:
                self._add_claim(Claim(
                    claim_id="derived.visibility.naked_eye",
                    claim_type=ClaimType.DERIVED_FACT,
                    subject=f"{t.standard_name}@{self.location_id}@{self._scope.date}",
                    predicate="naked_eye_visible",
                    text_value="yes",
                    display_value="肉眼可见",
                    validity_scope=self._scope,
                    source_refs=["target_resolve.visual_magnitude"],
                    derivation_rule=f"visibility.naked_eye@{rule_ver['visibility.naked_eye']}",
                    allowed_variant_ids=["naked_eye_v1", "naked_eye_v2"],
                ))
            else:
                self._add_claim(Claim(
                    claim_id="derived.visibility.naked_eye",
                    claim_type=ClaimType.DERIVED_FACT,
                    subject=f"{t.standard_name}@{self.location_id}@{self._scope.date}",
                    predicate="naked_eye_visible",
                    text_value="no",
                    display_value="肉眼不可见，需要望远镜辅助",
                    validity_scope=self._scope,
                    source_refs=["target_resolve.visual_magnitude"],
                    derivation_rule=f"visibility.naked_eye@{rule_ver['visibility.naked_eye']}",
                    allowed_variant_ids=["not_naked_eye_v1"],
                ))

            # Binoculars visibility
            if t.visual_magnitude <= 10.0:
                self._add_claim(Claim(
                    claim_id="derived.visibility.binoculars",
                    claim_type=ClaimType.DERIVED_FACT,
                    subject=f"{t.standard_name}@{self.location_id}@{self._scope.date}",
                    predicate="binoculars_visible",
                    text_value="yes",
                    display_value="双筒望远镜可见",
                    validity_scope=self._scope,
                    source_refs=["target_resolve.visual_magnitude"],
                    derivation_rule=f"visibility.binoculars@{rule_ver['visibility.binoculars']}",
                    allowed_variant_ids=["binoculars_v1"],
                ))

            # Beginner friendly
            if t.visual_magnitude <= 8.0 and t.angular_size_arcmin and t.angular_size_arcmin[0] > 5.0:
                self._add_claim(Claim(
                    claim_id="derived.visibility.beginner_friendly",
                    claim_type=ClaimType.DERIVED_FACT,
                    subject=f"{t.standard_name}@{self.location_id}@{self._scope.date}",
                    predicate="beginner_friendly",
                    text_value="yes",
                    display_value="适合新手观测",
                    validity_scope=self._scope,
                    source_refs=["target_resolve.visual_magnitude", "target_resolve.angular_size"],
                    derivation_rule=f"visibility.beginner_friendly@{rule_ver['visibility.beginner_friendly']}",
                    allowed_variant_ids=["beginner_v1"],
                ))
        else:
            # Cannot determine visibility without magnitude → unconfirmed
            self._add_claim(Claim(
                claim_id="derived.visibility.naked_eye",
                claim_type=ClaimType.UNCONFIRMED,
                subject=f"{t.standard_name}@{self.location_id}@{self._scope.date}",
                predicate="naked_eye_visible",
                text_value="无法判定（视星等缺失）",
                display_value="待确认（无法判定肉眼可见性）",
                validity_scope=self._scope,
                source_refs=[],
                allowed_variant_ids=["unconfirmed_v1"],
            ))

        # Equipment match
        self._build_equipment_match_claim()

    def _build_equipment_match_claim(self) -> None:
        """Derive equipment suitability claim."""
        t = self.target
        rule_ver = DERIVATION_RULES["equipment.match"]

        if t.visual_magnitude is None:
            self._add_claim(Claim(
                claim_id="derived.equipment.match",
                claim_type=ClaimType.UNCONFIRMED,
                subject=f"{t.standard_name}@{self.location_id}@{self._scope.date}",
                predicate="equipment_match",
                text_value="无法判定（视星等缺失）",
                display_value="待确认（无法判定设备匹配度）",
                validity_scope=self._scope,
                source_refs=[],
                allowed_variant_ids=["unconfirmed_v1"],
            ))
            return

        mag = t.visual_magnitude
        equip = self.equipment
        match_map = {
            "naked_eye": (None, 6.0),
            "binoculars": (None, 10.0),
            "small_telescope": (None, 12.0),
            "large_telescope": (None, 15.0),
        }
        _, limit = match_map.get(equip, (None, 10.0))
        matched = mag <= limit

        self._add_claim(Claim(
            claim_id="derived.equipment.match",
            claim_type=ClaimType.DERIVED_FACT,
            subject=f"{t.standard_name}@{self.location_id}@{self._scope.date}",
            predicate="equipment_match",
            text_value="yes" if matched else "no",
            display_value=f"当前设备（{self._display_equipment(equip)}）{'适合' if matched else '可能不足以'}观测此目标",
            validity_scope=self._scope,
            source_refs=["target_resolve.visual_magnitude", "input.equipment"],
            derivation_rule=f"equipment.match@{rule_ver}",
            allowed_variant_ids=["equipment_match_v1"] if matched else ["equipment_mismatch_v1"],
        ))

    # ── Moon claims ──

    def _build_moon_claims(self) -> None:
        """Build moon-related claims."""
        obs = self.obs
        if not obs.is_observable:
            return

        moon = obs.moon_info
        src = "observability_plan.moon"
        src_hash = self._hash_source(moon.model_dump())

        # Moon phase
        rules = NUMERIC_DISPLAY_RULES["moon_phase"]
        self._add_claim(Claim(
            claim_id="moon.phase",
            claim_type=ClaimType.OBSERVED_FACT,
            subject=f"{obs.target_name}@{self.location_id}@{self._scope.date}",
            predicate="moon_phase",
            canonical_value=moon.phase_fraction,
            display_value=f"{moon.phase_fraction:.{rules['precision']}f}",
            display_tolerance=rules["tolerance"],
            validity_scope=self._scope,
            source_refs=[src],
            source_hash=src_hash,
            allowed_variant_ids=["moon_phase_v1"],
        ))

        # Moon separation
        if moon.min_separation_deg is not None:
            rules_sep = NUMERIC_DISPLAY_RULES["moon_separation_deg"]
            self._add_claim(Claim(
                claim_id="moon.separation",
                claim_type=ClaimType.OBSERVED_FACT,
                subject=f"{obs.target_name}@{self.location_id}@{self._scope.date}",
                predicate="min_moon_separation",
                canonical_value=moon.min_separation_deg,
                unit="deg",
                display_value=f"{moon.min_separation_deg:.{rules_sep['precision']}f}°",
                display_tolerance=rules_sep["tolerance"],
                validity_scope=self._scope,
                source_refs=[src],
                source_hash=src_hash,
                allowed_variant_ids=["moon_sep_v1"],
            ))

        # Moon impact assessment (derived)
        rule_ver = DERIVATION_RULES["moon_impact.level"]
        self._add_claim(Claim(
            claim_id="moon.impact",
            claim_type=ClaimType.DERIVED_FACT,
            subject=f"{obs.target_name}@{self.location_id}@{self._scope.date}",
            predicate="moon_impact",
            text_value=moon.impact_assessment,
            display_value=self._display_moon_impact(moon.impact_assessment),
            validity_scope=self._scope,
            source_refs=[src],
            derivation_rule=f"moon_impact.level@{rule_ver}",
            allowed_variant_ids=["moon_impact_v1"],
        ))

    # ── Prohibited claims ──

    def _build_prohibited_claims(self) -> None:
        """Build the prohibited set: facts that must NEVER appear in output."""
        # Distance in light-years: not in our catalog, Qwen often hallucinates this
        self._add_prohibited(Claim(
            claim_id="prohibited.distance_lightyears",
            claim_type=ClaimType.PROHIBITED,
            subject=f"{self.target.standard_name}@{self.location_id}@{self._scope.date}",
            predicate="distance_lightyears",
            text_value="FORBIDDEN: distance in light-years not in catalog",
            display_value="[禁止] 距离（光年）不在数据源中",
            validity_scope=self._scope,
            source_refs=[],
        ))

        # Physical nature details not in catalog (e.g., "旋涡星系" for M31)
        # These are scientifically true but NOT in our data source
        self._add_prohibited(Claim(
            claim_id="prohibited.physical_nature",
            claim_type=ClaimType.PROHIBITED,
            subject=f"{self.target.standard_name}@{self.location_id}@{self._scope.date}",
            predicate="physical_nature_detail",
            text_value="FORBIDDEN: detailed physical nature not in catalog",
            display_value="[禁止] 详细物理性质不在数据源中",
            validity_scope=self._scope,
            source_refs=[],
        ))

        # Temperature/weather predictions (not from our tools)
        self._add_prohibited(Claim(
            claim_id="prohibited.weather_prediction",
            claim_type=ClaimType.PROHIBITED,
            subject=f"{self.target.standard_name}@{self.location_id}@{self._scope.date}",
            predicate="weather_prediction",
            text_value="FORBIDDEN: weather/temperature predictions not from tools",
            display_value="[禁止] 天气/气温预测不来自工具",
            validity_scope=self._scope,
            source_refs=[],
        ))

        # Dark adaptation time (specific minutes)
        self._add_prohibited(Claim(
            claim_id="prohibited.dark_adaptation_minutes",
            claim_type=ClaimType.PROHIBITED,
            subject=f"{self.target.standard_name}@{self.location_id}@{self._scope.date}",
            predicate="dark_adaptation_minutes",
            text_value="FORBIDDEN: specific dark adaptation time not from tools",
            display_value="[禁止] 具体暗适应时间不来自工具",
            validity_scope=self._scope,
            source_refs=[],
        ))

    # ── Helpers ──

    @staticmethod
    def _hash_source(data: dict) -> str:
        """Compute a short sha256 hash of source data for tamper detection."""
        content = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _display_target_type(t: str) -> str:
        """Map target_type enum to Chinese display."""
        mapping = {
            "deep_sky": "深空天体",
            "star": "恒星",
            "planet": "行星",
            "asterism": "星群",
        }
        return mapping.get(t, t)

    @staticmethod
    def _display_equipment(e: str) -> str:
        """Map equipment enum to Chinese display."""
        mapping = {
            "naked_eye": "肉眼",
            "binoculars": "双筒望远镜",
            "small_telescope": "小型天文望远镜",
            "large_telescope": "大型天文望远镜",
        }
        return mapping.get(e, e)

    @staticmethod
    def _display_moon_impact(level: str) -> str:
        """Map moon impact level to Chinese display."""
        mapping = {
            "none": "月光无影响",
            "low": "月光影响较小",
            "moderate": "月光有一定影响",
            "high": "月光影响较大",
            "severe": "月光影响严重",
            "unknown": "月光影响待评估",
        }
        return mapping.get(level, f"月光影响: {level}")
