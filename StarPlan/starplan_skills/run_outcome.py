"""
StarPlan Loop - RunOutcome (Phase E: single source of truth for run results).

A single RunOutcome object from which manifest, validation report, user output,
and test summary are ALL rendered. This eliminates the scattered construction
of manifest/validation/output that previously lived in runner.py.

Key design:
  - business_status: what happened astronomically (observable / not_observable /
    data_insufficient / tool_error / needs_confirmation)
  - validation_status: did the output pass structural validation (passed /
    passed_with_warnings / blocked / pending)
  - delivery_status: how was the output delivered (qwen_expression_plan /
    deterministic_fallback / template)

These three are INDEPENDENT. A run can be business=observable +
validation=blocked + delivery=deterministic_fallback.

See: starplan-hallucination-prevention-architecture.md §9
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional

from .schemas import (
    CalculationManifest,
    ModelInfo,
    ObservabilityResult,
    ResolvedTarget,
    RunState,
    ToolVersions,
)


class BusinessStatus(str, Enum):
    """What happened astronomically."""
    PENDING = "pending"                  # Run started but not yet resolved
    OBSERVABLE = "observable"
    NOT_OBSERVABLE = "not_observable"
    DATA_INSUFFICIENT = "data_insufficient"
    TOOL_ERROR = "tool_error"
    NEEDS_CONFIRMATION = "needs_confirmation"


class ValidationStatus(str, Enum):
    """Did the output pass structural validation."""
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    BLOCKED = "blocked"
    PENDING = "pending"


class DeliveryStatus(str, Enum):
    """How was the outreach expression delivered."""
    QWEN_EXPRESSION_PLAN = "qwen_expression_plan"
    DETERMINISTIC_FALLBACK = "deterministic_fallback"
    TEMPLATE = "template"
    NOT_DELIVERED = "not_delivered"      # Failed before any output was produced


class RunOutcome:
    """Single source of truth for a completed run.

    All outputs (manifest, validation report, user-facing pack) are rendered
    from this object. No scattered construction.

    P0-C: can be created at run entry (before target resolution) with
    target/obs_result/location as None, then filled incrementally.
    """

    def __init__(
        self,
        run_id: str,
        target: Optional[ResolvedTarget] = None,
        obs_result: Optional[ObservabilityResult] = None,
        location: Optional[dict] = None,
        input_data: Optional[dict] = None,
        state_log: Optional[list[dict]] = None,
    ):
        self.run_id = run_id
        self.target = target
        self.obs_result = obs_result
        self.location = location or {}
        self.input_data = input_data or {}
        self.state_log = state_log or []

        # Derived statuses (P0-C: start as PENDING, updated as pipeline progresses)
        self.business_status = self._derive_business_status()
        self.validation_status = ValidationStatus.PENDING
        self.delivery_status = DeliveryStatus.NOT_DELIVERED

        # Evidence
        self.qwen_used = False
        # Compatibility alias: true only when a Qwen ExpressionPlan passed
        # validation and was adopted for rendering.
        self.model_output_accepted = False
        self.model_call_events: list[dict] = []
        self.runtime_policy: Optional[str] = None
        self.stage_timings_ms: dict[str, float] = {}
        self.claims_registry_hash: Optional[str] = None
        self.validation_issues: list[str] = []
        self.file_hashes: dict[str, str] = {}
        self.error_type: Optional[str] = None
        self.error_message_safe: Optional[str] = None

    def _derive_business_status(self) -> BusinessStatus:
        """Derive business status from observability result.

        P0-C: None means pipeline hasn't reached computation yet → PENDING.
        TOOL_ERROR is set explicitly by the runner on actual failure.
        """
        if self.obs_result is None:
            return BusinessStatus.PENDING
        if self.obs_result.is_observable:
            return BusinessStatus.OBSERVABLE
        if not self.obs_result.hourly_data:
            return BusinessStatus.DATA_INSUFFICIENT
        return BusinessStatus.NOT_OBSERVABLE

    def set_validation(self, status: ValidationStatus, issues: list[str] = None):
        """Set validation outcome."""
        self.validation_status = status
        if issues:
            self.validation_issues = issues

    def set_delivery(self, status: DeliveryStatus, qwen_used: bool = False):
        """Set delivery method."""
        self.delivery_status = status
        self.qwen_used = qwen_used
        self.model_output_accepted = qwen_used

    def add_model_call_event(self, event: dict):
        """Record a model call event for evidence chain."""
        if event.get("type") == "model_call":
            self.model_call_events.append(event)

    def import_model_call_events(self, log_path: str | Path | None) -> list[str]:
        """Import real ``type=model_call`` entries from the JSONL audit log."""
        if not log_path:
            return []
        path = Path(log_path)
        # Re-import is authoritative; never retain events from an older log.
        self.model_call_events = []
        if not path.exists():
            return ["model_call_log.jsonl missing"]
        warnings: list[str] = []
        imported: list[dict] = []
        try:
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as exc:
                    warnings.append(f"model_call_log.jsonl line {line_no} is invalid JSON: {exc}")
                    continue
                if isinstance(entry, dict) and entry.get("type") == "model_call":
                    imported.append(entry)
        except (OSError, UnicodeDecodeError) as exc:
            warnings.append(f"model_call_log.jsonl could not be read: {exc}")
            return warnings
        self.model_call_events = imported
        return warnings

    @property
    def model_called(self) -> bool:
        return bool(self.model_call_events)

    def set_runtime_policy(self, policy: str | None) -> None:
        self.runtime_policy = policy

    def record_stage_timing(self, name: str, elapsed_ms: float) -> None:
        self.stage_timings_ms[name] = round(float(elapsed_ms), 3)

    def compute_file_hash(self, file_path: Path) -> str:
        """Compute and store sha256 hash of a file."""
        content = file_path.read_bytes()
        h = hashlib.sha256(content).hexdigest()[:16]
        self.file_hashes[file_path.name] = h
        return h

    def build_manifest(
        self,
        run_dir: Path,
        starplan_input=None,
    ) -> CalculationManifest:
        """Build the CalculationManifest from this RunOutcome.

        Key rules:
          - model.called is derived from model_call_events (not hardcoded)
          - validation_status is never hardcoded to "passed"
          - schema_version is always set
        """
        import astropy
        import sys

        try:
            import astroplan
            astroplan_ver = astroplan.__version__
        except ImportError:
            astroplan_ver = "not_installed"

        from .qwen_client import DEFAULT_MODEL

        tz = timezone(timedelta(hours=8))

        # model_used derived from actual events
        has_model_calls = self.model_called
        model_name = next(
            (e.get("model") for e in reversed(self.model_call_events) if e.get("model")),
            None,
        )
        if has_model_calls:
            model_info = ModelInfo(
                provider="阿里云百炼",
                model_name=model_name or DEFAULT_MODEL,
                called=True,
            )
        else:
            model_info = ModelInfo(
                provider="阿里云百炼",
                model_name=None,
                called=False,
            )

        # validation_status from RunOutcome (never hardcoded, never overridden)
        vs_map = {
            ValidationStatus.PASSED: "passed",
            ValidationStatus.PASSED_WITH_WARNINGS: "passed_with_warnings",
            ValidationStatus.BLOCKED: "blocked",
            ValidationStatus.PENDING: "pending",
        }
        validation_status = vs_map[self.validation_status]

        # P0-C: no override — not_observable is a business status, not validation.
        # business_status and validation_status remain orthogonal.

        # Handle None target (early failure before resolution)
        target_data = {
            "standard_name": self.target.standard_name if self.target else None,
            "ra_deg": self.target.ra_deg if self.target else None,
            "dec_deg": self.target.dec_deg if self.target else None,
            "source": self.target.source if self.target else None,
        }

        return CalculationManifest(
            schema_version="1.0",
            run_id=self.run_id,
            timestamp=datetime.now(tz),
            input=self.input_data,
            target=target_data,
            location=self.location,
            tools=ToolVersions(
                astropy_version=astropy.__version__,
                astroplan_version=astroplan_ver,
                python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            ),
            model=model_info,
            constraints_applied={
                "astronomy_runtime_policy": self.runtime_policy or "unknown",
                "refraction_policy": "astropy_default (pressure=0, no atmospheric refraction)",
            },
            intermediate_files=[f.name for f in run_dir.iterdir() if f.is_file()],
            manual_overrides=[],
            validation_status=validation_status,
            validation_issues=self.validation_issues,
            qwen_used=self.qwen_used,
        )

    def to_audit_summary(self) -> dict:
        """Produce a compact audit summary for the evidence chain."""
        return {
            "run_id": self.run_id,
            "business_status": self.business_status.value,
            "validation_status": self.validation_status.value,
            "delivery_status": self.delivery_status.value,
            "qwen_used": self.qwen_used,
            "model_called": self.model_called,
            "model_output_accepted": self.model_output_accepted,
            "model_call_count": len(self.model_call_events),
            "model_call_steps": [
                e.get("step") for e in self.model_call_events if e.get("step")
            ],
            "claims_registry_hash": self.claims_registry_hash,
            "file_hashes": self.file_hashes,
            "validation_issues_count": len(self.validation_issues),
            "state_transitions": len(self.state_log),
            "astronomy_runtime": self.runtime_policy,
            "stage_timings_ms": self.stage_timings_ms,
        }
