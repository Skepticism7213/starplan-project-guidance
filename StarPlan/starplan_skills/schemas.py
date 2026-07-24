"""
StarPlan Loop - Unified input/output schemas for all 4 core Skills.

Uses Pydantic v2 for validation, serialization, and JSON Schema generation.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ──────────────────────────────────────────────
# Common types
# ──────────────────────────────────────────────

class LocationDetail(BaseModel):
    """Observation site coordinates and metadata."""

    name: str = Field(description="Site name, e.g. '四门塔景区'")
    city: str = Field(description="City name, e.g. '济南'")
    latitude: float = Field(description="Latitude in decimal degrees (positive = N)")
    longitude: float = Field(description="Longitude in decimal degrees (positive = E)")
    elevation_m: float = Field(default=0, description="Elevation in metres")
    timezone: str = Field(default="Asia/Shanghai", description="IANA timezone string")


class ObservingConstraint(BaseModel):
    """Optional user-defined observing constraints."""

    min_altitude_deg: float = Field(default=30.0, description="Minimum target altitude in degrees")
    max_airmass: float = Field(default=2.0, description="Maximum acceptable airmass")
    prefer_early_night: bool = Field(default=False, description="Prefer windows before local midnight")
    max_moon_illumination: Optional[float] = Field(default=None, description="Maximum moon illumination fraction (0-1)")


# ──────────────────────────────────────────────
# Unified input
# ──────────────────────────────────────────────

class StarPlanInput(BaseModel):
    """Unified input schema for starplan.run."""

    target: str = Field(description="Target name (Chinese, English, Messier, NGC, etc.)")
    target_type: Optional[str] = Field(
        default=None,
        description="Optional target type hint: deep_sky, star, planet, asterism",
    )
    confirmed_target: Optional[str] = Field(
        default=None,
        description="Explicitly confirmed standard target name (e.g. 'M33'). "
        "When provided, indicates a human has already selected from candidates; "
        "the pipeline bypasses the ambiguity check and uses this name directly.",
    )
    location: str = Field(description="Location identifier, e.g. '济南_四门塔'")
    location_detail: Optional[LocationDetail] = Field(
        default=None,
        description="Explicit coordinates; if omitted, resolved from built-in location table",
    )
    date_range: list[date] = Field(
        description="Observing date range [start, end] in YYYY-MM-DD",
        min_length=1,
        max_length=2,
    )
    audience: str = Field(description="Target audience, e.g. '天文社新成员'")
    equipment: str = Field(description="Equipment type: naked_eye, binoculars, small_telescope, large_telescope")
    goal: str = Field(default="校园科普观测", description="Activity goal description")
    constraints: Optional[ObservingConstraint] = Field(default=None, description="Custom observing constraints")

    @field_validator("date_range")
    @classmethod
    def validate_date_range(cls, v: list[date]) -> list[date]:
        if len(v) == 1:
            return [v[0], v[0]]
        if v[0] > v[1]:
            raise ValueError("date_range start must be <= end")
        return v

    @field_validator("equipment")
    @classmethod
    def validate_equipment(cls, v: str) -> str:
        allowed = {"naked_eye", "binoculars", "small_telescope", "large_telescope"}
        if v not in allowed:
            raise ValueError(f"equipment must be one of {allowed}, got '{v}'")
        return v


# ──────────────────────────────────────────────
# Skill 1: target_resolve
# ──────────────────────────────────────────────

class TargetCandidate(BaseModel):
    """A candidate target when name resolution is ambiguous."""

    standard_name: str
    target_type: str
    ra_deg: float
    dec_deg: float
    source: str
    confidence: float


class ResolvedTarget(BaseModel):
    """Output of target_resolve."""

    standard_name: str = Field(description="Standard target name (e.g. 'M31')")
    aliases: list[str] = Field(default_factory=list, description="Known aliases")
    target_type: str = Field(description="Target type: deep_sky, star, planet, asterism")
    ra_deg: float = Field(description="Right ascension in degrees (J2000)")
    dec_deg: float = Field(description="Declination in degrees (J2000)")
    visual_magnitude: Optional[float] = Field(default=None, description="Visual magnitude")
    angular_size_arcmin: Optional[list[float]] = Field(default=None, description="Angular size [major, minor] in arcmin")
    constellation: Optional[str] = Field(default=None, description="Constellation name")
    source: str = Field(description="Data source identifier (e.g. 'built_in_catalog_v1')")
    confidence: float = Field(ge=0, le=1, description="Match confidence (0-1)")
    candidates: Optional[list[TargetCandidate]] = Field(
        default=None, description="Candidate list when ambiguous"
    )
    requires_confirmation: bool = Field(
        default=False, description="Whether human confirmation is needed"
    )


# ──────────────────────────────────────────────
# Skill 2: observability_plan
# ──────────────────────────────────────────────

class TimeWindow(BaseModel):
    """A contiguous time interval."""

    start: datetime
    end: datetime
    duration_minutes: float


class RecommendedWindow(BaseModel):
    """The recommended observing window with reasoning."""

    window: TimeWindow
    peak_altitude_deg: float
    peak_airmass: float
    reason: str = Field(description="Why this window is recommended")


class EliminatedWindow(BaseModel):
    """A time window that was eliminated with reasoning."""

    window: TimeWindow
    reason: str = Field(description="Why this window was eliminated")
    violated_constraint: str = Field(description="Which constraint was violated")


class HourlyData(BaseModel):
    """Per-hour computed data."""

    time: datetime
    altitude_deg: float
    azimuth_deg: float
    airmass: Optional[float] = None
    sun_altitude_deg: float
    moon_altitude_deg: Optional[float] = None
    moon_separation_deg: Optional[float] = None


class TwilightInfo(BaseModel):
    """Sunset and twilight times."""

    sunset: Optional[datetime] = None
    civil_twilight_end: Optional[datetime] = None
    nautical_twilight_end: Optional[datetime] = None
    astronomical_twilight_end: Optional[datetime] = None
    sunrise: Optional[datetime] = None
    astronomical_twilight_start: Optional[datetime] = None


class MoonInfo(BaseModel):
    """Moon-related information."""

    phase_fraction: float = Field(description="Illuminated fraction (0=new, 1=full)")
    moonrise: Optional[datetime] = None
    moonset: Optional[datetime] = None
    peak_altitude_deg: Optional[float] = Field(default=None, description="Moon peak altitude during the night")
    min_separation_deg: Optional[float] = Field(default=None, description="Minimum angular separation from target")
    impact_assessment: str = Field(
        default="unknown",
        description="Impact level: none, low, moderate, high, severe",
    )


class RiskFlag(BaseModel):
    """A risk identified during observability analysis."""

    risk_type: str = Field(description="Type: low_altitude, moonlight, twilight, airmass, weather_note")
    severity: str = Field(description="Severity: info, warning, critical")
    description: str
    affected_window: Optional[TimeWindow] = None


class AlternativeSuggestion(BaseModel):
    """Suggestion for alternative time or target."""

    suggestion_type: str = Field(description="Type: alternative_date, alternative_target")
    description: str
    target_name: Optional[str] = None
    suggested_date: Optional[date] = None


class ObservabilityResult(BaseModel):
    """Output of observability_plan."""

    is_observable: bool
    target_name: str
    location_name: str
    date_range: list[date]
    visibility_windows: list[TimeWindow] = Field(default_factory=list)
    recommended_window: Optional[RecommendedWindow] = None
    eliminated_windows: list[EliminatedWindow] = Field(default_factory=list)
    hourly_data: list[HourlyData] = Field(default_factory=list)
    twilight: TwilightInfo
    moon_info: MoonInfo
    alternative_suggestions: list[AlternativeSuggestion] = Field(default_factory=list)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    observability_csv_path: Optional[str] = None
    visibility_curve_path: Optional[str] = None


# ──────────────────────────────────────────────
# Skill 3: outreach_pack
# ──────────────────────────────────────────────

class FactCard(BaseModel):
    """A verified astronomical fact card entry."""

    key: str = Field(description="Fact key, e.g. 'distance', 'visual_magnitude'")
    value: str = Field(description="Human-readable value")
    source: str = Field(description="Data source")


class ActivityScheduleItem(BaseModel):
    """A step in the activity schedule."""

    time_label: str = Field(description="Relative or absolute time, e.g. '20:00' or '活动开始后30分钟'")
    activity: str
    notes: Optional[str] = None


class EquipmentItem(BaseModel):
    """An equipment checklist entry."""

    item: str
    quantity: str = "1"
    required: bool = True
    notes: Optional[str] = None


class OutreachPack(BaseModel):
    """Output of outreach_pack."""

    target_name: str
    audience: str
    pack_type: str = Field(
        default="observation",
        description="Pack type: 'observation' (normal) or 'not_observable' "
        "(cancellation/reschedule/alternative pack)",
    )
    activity_schedule: list[ActivityScheduleItem] = Field(default_factory=list)
    talking_points: list[str] = Field(default_factory=list)
    equipment_checklist: list[EquipmentItem] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    manual_check_items: list[str] = Field(default_factory=list)
    unconfirmed_items: list[str] = Field(default_factory=list)
    alternative_suggestions: list[str] = Field(
        default_factory=list,
        description="Alternative target/date suggestions when target is not observable",
    )
    outreach_pack_md_path: Optional[str] = None
    qwen_used: bool = False
    qwen_validation_issues: list[str] = Field(default_factory=list)


# ──────────────────────────────────────────────
# Skill 4: observation_review
# ──────────────────────────────────────────────

class ObservationLog(BaseModel):
    """Actual observation log entry."""

    actual_start_time: datetime
    actual_end_time: datetime
    targets_observed: list[str]
    targets_missed: list[str] = Field(default_factory=list)
    equipment_used: str
    cloud_cover: Optional[str] = Field(default=None, description="clear / partly_cloudy / overcast")
    seeing_conditions: Optional[str] = Field(default=None, description="good / fair / poor")
    observer_notes: Optional[str] = None
    success_rating: Optional[int] = Field(default=None, ge=1, le=5)


class Deviation(BaseModel):
    """A single deviation between plan and actual."""

    deviation_type: str = Field(description="time, environment, equipment, operation")
    description: str
    plan_reference: str = Field(description="What the plan said")
    actual_value: str = Field(description="What actually happened")


class CauseEntry(BaseModel):
    """A classified cause for a deviation."""

    cause: str
    classification: str = Field(description="evidence_based, possible, undetermined")
    evidence: str = Field(description="Evidence citation from plan or log")


class RevisedPlanDiff(BaseModel):
    """Field-level difference between original and revised plan."""

    field: str
    original_value: str
    revised_value: str
    reason: str


class ObservationReview(BaseModel):
    """Output of observation_review."""

    target_name: str
    deviation_summary: list[Deviation] = Field(default_factory=list)
    evidence_citations: list[str] = Field(default_factory=list)
    cause_classification: list[CauseEntry] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)
    revised_plan: Optional[dict] = None
    revised_plan_diff: list[RevisedPlanDiff] = Field(default_factory=list)
    review_report_md_path: Optional[str] = None
    revised_plan_json_path: Optional[str] = None


# ──────────────────────────────────────────────
# Run manifest
# ──────────────────────────────────────────────

class ToolVersions(BaseModel):
    """Versions of tools used in a run."""

    astropy_version: str
    astroplan_version: str
    python_version: str


class ModelInfo(BaseModel):
    """Qwen model information."""

    provider: str = "阿里云百炼"
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    called: bool = Field(
        default=False,
        description="Whether the model was actually invoked during this run",
    )


class CalculationManifest(BaseModel):
    """The evidence file for each run — records everything needed for reproducibility."""

    run_id: str
    timestamp: datetime
    input: dict
    target: dict
    location: dict
    tools: ToolVersions
    model: ModelInfo
    constraints_applied: dict
    intermediate_files: list[str] = Field(default_factory=list)
    manual_overrides: list[str] = Field(default_factory=list)
    validation_status: str = "pending"
    validation_issues: list[str] = Field(
        default_factory=list,
        description="Issues found during validation (empty if all passed)",
    )
    qwen_used: bool = Field(
        default=False,
        description="Whether Qwen was actually used for outreach pack generation",
    )
