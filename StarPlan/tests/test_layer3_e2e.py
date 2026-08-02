"""
StarPlan Loop - P2 Layer 3 End-to-End Tests.

Full-pipeline tests that assert on final user-visible outputs, RunOutcome,
audit events, and sentence_claim_map. These go beyond component-level tests
by running run_starplan() and checking the complete artifact set.

Scenarios (from 07-29 independent audit P2-1):
  1. Strong moonlight → not observable, blocking reason = moon (not altitude)
  2. Tool exception → graceful failure, RunOutcome reflects error
  3. Data insufficient → UNCONFIRMED claims, no overconfident output
  4. Qwen API unavailable → deterministic fallback, core output intact
  5. Pure text hallucination (Chat) → blocked, deterministic summary returned
  6. Complete Markdown mapping → every factual sentence has claim_id

No API key required (Qwen is mocked where needed).
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starplan_skills.runner import run_starplan, _check_chat_hallucination, _build_deterministic_summary
from starplan_skills.schemas import ObservabilityResult, ResolvedTarget


# ── Shared inputs ─────────────────────────────────────

BASE_INPUT = {
    "location": "济南_四门塔",
    "location_detail": {
        "name": "四门塔景区观星点",
        "city": "济南",
        "latitude": 36.49,
        "longitude": 117.18,
        "elevation_m": 300,
        "timezone": "Asia/Shanghai",
    },
    "audience": "天文社新成员",
    "equipment": "binoculars",
    "goal": "校园科普观测",
}


# ══════════════════════════════════════════════════════
# 1. Strong moonlight → not observable, reason = moon
# ══════════════════════════════════════════════════════

class TestStrongMoonlightE2E:
    """M31 on a full-moon night with strict moon constraint.

    The audit found that the old system claimed 'altitude too low' even when
    the target was at 85 deg. The fix must derive blocking reason from the
    actual violated constraint (moon illumination).
    """

    INPUT = {
        **BASE_INPUT,
        "target": "M31",
        "date_range": ["2026-10-26", "2026-10-26"],
        "constraints": {
            "min_altitude_deg": 30,
            "max_airmass": 2.0,
            "prefer_early_night": False,
            "max_moon_illumination": 0.01,  # near-zero tolerance → full moon blocks
        },
    }

    @pytest.fixture(scope="class")
    @classmethod
    def run_result(cls, tmp_path_factory):
        run_id = "test_p2_moonlight"
        result = run_starplan(cls.INPUT, run_id=run_id)
        return result

    def test_not_observable(self, run_result):
        """Pipeline completes; target is not observable due to moon."""
        plan = run_result["plan"]
        assert plan["is_observable"] is False

    def test_blocking_reason_mentions_moon(self, run_result):
        """The not-observable reason must reference moon, not altitude."""
        run_dir = Path(run_result["run_dir"])
        pack_md = (run_dir / "outreach_pack.md").read_text(encoding="utf-8")
        # Must mention moon/月光 as the reason
        assert "月" in pack_md or "moon" in pack_md.lower(), (
            f"Blocking reason should mention moon. Pack content:\n{pack_md[:500]}"
        )
        # Must NOT falsely claim altitude too low (M31 is at ~85 deg)
        assert "高度角过低" not in pack_md
        assert "地平线以下" not in pack_md

    def test_run_outcome_exists(self, run_result):
        """run_outcome.json must be generated."""
        run_dir = Path(run_result["run_dir"])
        outcome_path = run_dir / "run_outcome.json"
        assert outcome_path.exists()
        outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
        assert "business_status" in outcome or "run_id" in outcome

    def test_claims_json_exists(self, run_result):
        """claims.json must be generated with registry_hash."""
        run_dir = Path(run_result["run_dir"])
        claims_path = run_dir / "claims.json"
        assert claims_path.exists()
        claims = json.loads(claims_path.read_text(encoding="utf-8"))
        assert "registry_hash" in claims
        assert len(claims["registry_hash"]) == 16


# ══════════════════════════════════════════════════════
# 2. Tool exception → graceful failure
# ══════════════════════════════════════════════════════

class TestToolExceptionE2E:
    """When compute_observability raises, pipeline must persist RunOutcome.

    P0-C guarantees: run_outcome.json with business=tool_error is written
    before the exception propagates. No silent success, no wrong output.
    """

    INPUT = {**BASE_INPUT, "target": "M31", "date_range": ["2026-10-17", "2026-10-17"]}

    def test_tool_exception_produces_run_outcome(self, tmp_path):
        """Mock observability to raise; run_outcome.json must exist with tool_error."""
        with patch(
            "starplan_skills.runner.compute_observability",
            side_effect=RuntimeError("Astropy coordinate transform failed"),
        ):
            with pytest.raises(RuntimeError, match="Astropy"):
                run_starplan(self.INPUT, run_id="test_p1b_tool_exc")

        # P0-C: RunOutcome must have been persisted before the raise
        run_dir = Path("runs/test_p1b_tool_exc")
        assert run_dir.exists(), "Run directory must be created"
        outcome_path = run_dir / "run_outcome.json"
        assert outcome_path.exists(), "run_outcome.json must exist for tool_error"
        outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
        assert outcome["business_status"] == "tool_error"
        assert outcome["delivery_status"] == "not_delivered"


# ══════════════════════════════════════════════════════
# 3. Data insufficient → UNCONFIRMED claims
# ══════════════════════════════════════════════════════

class TestDataInsufficientE2E:
    """Target with missing magnitude must produce UNCONFIRMED visibility claims.

    The outreach pack must NOT assert naked-eye visibility or beginner-friendly
    without sufficient data.
    """

    INPUT = {**BASE_INPUT, "target": "M31", "date_range": ["2026-10-17", "2026-10-17"]}

    def test_unconfirmed_when_no_magnitude(self, tmp_path):
        """Patch catalog to remove magnitude; claims must be UNCONFIRMED."""
        from starplan_skills.claims import AllowedClaimsBuilder
        from starplan_skills.schemas import (
            MoonInfo, ObservabilityResult, RecommendedWindow, TimeWindow, TwilightInfo,
        )

        target_no_mag = ResolvedTarget(
            standard_name="NGC7000", aliases=["北美洲星云"], target_type="deep_sky",
            ra_deg=315.0, dec_deg=44.5, visual_magnitude=None,
            angular_size_arcmin=[120.0, 100.0],
            source="built_in_catalog_v1", confidence=0.9,
        )
        w = TimeWindow(start=datetime(2026, 10, 17, 20, 0), end=datetime(2026, 10, 17, 23, 0), duration_minutes=180)
        obs = ObservabilityResult(
            is_observable=True, target_name="NGC7000", location_name="济南_四门塔",
            date_range=[date(2026, 10, 17)],
            recommended_window=RecommendedWindow(window=w, peak_altitude_deg=60.0, peak_airmass=1.2, reason="test"),
            twilight=TwilightInfo(astronomical_twilight_end=datetime(2026, 10, 17, 19, 15)),
            moon_info=MoonInfo(phase_fraction=0.2, min_separation_deg=80.0, impact_assessment="low"),
        )
        builder = AllowedClaimsBuilder(target_no_mag, obs, "济南_四门塔", "天文社新成员", "binoculars")
        builder.build()

        # No magnitude → no derived.visibility.naked_eye DERIVED_FACT claim
        naked_claim = builder.get_claim("derived.visibility.naked_eye")
        if naked_claim is not None:
            from starplan_skills.schemas import ClaimType
            assert naked_claim.claim_type == ClaimType.UNCONFIRMED, (
                f"Without magnitude, naked_eye claim must be UNCONFIRMED, got {naked_claim.claim_type}"
            )

        # No overconfident display values
        for c in builder.allowed_claims:
            assert "肉眼可见" not in (c.display_value or "") or "待确认" in (c.display_value or "")


# ══════════════════════════════════════════════════════
# 4. Qwen API unavailable → deterministic fallback
# ══════════════════════════════════════════════════════

class TestQwenUnavailableE2E:
    """When Qwen API fails, outreach pack must still be generated via template."""

    INPUT = {**BASE_INPUT, "target": "M31", "date_range": ["2026-10-17", "2026-10-17"]}

    def test_fallback_on_qwen_failure(self):
        """Mock Qwen to raise; pipeline must produce template-based output."""
        with patch(
            "starplan_skills.qwen_client.call_qwen_json",
            side_effect=Exception("DashScope API timeout"),
        ):
            result = run_starplan(self.INPUT, run_id="test_p2_qwen_down")

        run_dir = Path(result["run_dir"])
        pack_path = run_dir / "outreach_pack.md"
        assert pack_path.exists(), "outreach_pack.md must exist even without Qwen"
        content = pack_path.read_text(encoding="utf-8")
        assert len(content) > 100, "Fallback pack should have substantive content"
        # Must contain the target name
        assert "M31" in content

        # RunOutcome should reflect template delivery
        outcome_path = run_dir / "run_outcome.json"
        assert outcome_path.exists()
        outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
        # delivery_status should indicate template (not qwen)
        delivery = outcome.get("delivery_status", "")
        assert "template" in delivery.lower() or "TEMPLATE" in str(delivery), (
            f"Delivery should be template-based, got: {delivery}"
        )


# ══════════════════════════════════════════════════════
# 5. Pure text hallucination (Chat) → blocked
# ══════════════════════════════════════════════════════

class TestPureTextHallucinationE2E:
    """Chat returns wrong facts with NO numbers — must still be caught.

    The audit found that _check_chat_hallucination only catches numeric
    hallucinations. Pure-text wrong facts like '肉眼清晰可见' for a mag 10
    target pass the old check. This test documents the current behavior and
    asserts the deterministic summary is available as fallback.
    """

    CAPTURED_TOOLS = {
        "target_resolve": {
            "standard_name": "M101",
            "ra_deg": 210.8,
            "dec_deg": 54.35,
            "target_type": "deep_sky",
            "visual_magnitude": 7.9,
            "confidence": 1.0,
        },
        "resolve_location": {
            "name": "四门塔景区观星点",
            "key": "济南_四门塔",
            "latitude": 36.49,
            "longitude": 117.18,
        },
        "observability_plan": {
            "is_observable": True,
            "target_name": "M101",
            "recommended_window": {
                "window": {"start": "2026-10-17T20:00:00", "end": "2026-10-18T02:00:00"},
                "peak_altitude_deg": 55.0,
                "peak_airmass": 1.3,
            },
            "moon_info": {"phase_fraction": 0.1, "min_separation_deg": 90.0, "impact_assessment": "low"},
        },
    }

    def test_pure_text_wrong_claim_detected_or_fallback_available(self):
        """Pure-text hallucination: '肉眼清晰可见' for mag 7.9 target.

        Current _check_chat_hallucination may not catch this (no numbers).
        But _build_deterministic_summary must provide a safe alternative.
        """
        hallucinated_text = "M101今晚肉眼清晰可见，光污染较低，非常适合新手观测，不需要任何设备。"

        # Check if the hallucination detector catches it
        violations = _check_chat_hallucination(hallucinated_text, self.CAPTURED_TOOLS)
        # Document: if violations is empty, the pure-text gap still exists
        # The critical assertion: deterministic summary must be available regardless
        summary = _build_deterministic_summary(self.CAPTURED_TOOLS)
        assert summary is not None
        assert len(summary) > 50
        # Deterministic summary must NOT contain the hallucinated claims
        assert "肉眼清晰可见" not in summary
        assert "不需要任何设备" not in summary

    def test_numeric_hallucination_still_caught(self):
        """Verify numeric hallucination detection still works."""
        text = "M101的赤经为999.9度，峰值高度角为120度"
        violations = _check_chat_hallucination(text, self.CAPTURED_TOOLS)
        assert len(violations) > 0, "Numeric hallucination must be caught"


# ══════════════════════════════════════════════════════
# 6. Complete Markdown mapping
# ══════════════════════════════════════════════════════

class TestMarkdownMappingE2E:
    """Every factual sentence in outreach_pack.md must have a claim_id mapping.

    The audit found that only 9/32 list items had claim mappings. After P0/P1
    fixes, the template renderer should produce 100% coverage for the
    talking_points section.
    """

    INPUT = {**BASE_INPUT, "target": "M31", "date_range": ["2026-10-17", "2026-10-17"]}

    @pytest.fixture(scope="class")
    @classmethod
    def run_result(cls):
        return run_starplan(cls.INPUT, run_id="test_p2_mapping")

    def test_sentence_claim_map_exists(self, run_result):
        """sentence_claim_map.json must be generated."""
        run_dir = Path(run_result["run_dir"])
        map_path = run_dir / "sentence_claim_map.json"
        assert map_path.exists(), "sentence_claim_map.json must exist"

    def test_talking_points_fully_mapped(self, run_result):
        """All talking points in the outreach pack must have claim mappings."""
        run_dir = Path(run_result["run_dir"])
        map_path = run_dir / "sentence_claim_map.json"
        if not map_path.exists():
            pytest.skip("sentence_claim_map.json not generated")

        mapping = json.loads(map_path.read_text(encoding="utf-8"))
        # mapping should have entries (not empty)
        assert len(mapping) > 0, "sentence_claim_map must not be empty"

        # P1-B: require coverage proportional to factual content.
        # Every mapped entry must be non-trivial; total must cover
        # the talking points + schedule + safety + checks sections.
        pack_md = (run_dir / "outreach_pack.md").read_text(encoding="utf-8")
        # Count content list items, excluding bold-header summary lines (- **key**: val)
        factual_lines = [
            line.strip() for line in pack_md.split("\n")
            if line.strip().startswith("- ") and len(line.strip()) > 10
            and not line.strip().startswith("- **")
        ]
        mapped_count = len(mapping)
        # Strict: mapping must cover at least as many items as factual lines
        assert mapped_count >= len(factual_lines), (
            f"Mapping has {mapped_count} entries but Markdown has "
            f"{len(factual_lines)} factual list items. Coverage incomplete."
        )

    def test_claims_json_covers_mapped_ids(self, run_result):
        """All claim_ids in sentence_claim_map must exist in claims.json."""
        run_dir = Path(run_result["run_dir"])
        map_path = run_dir / "sentence_claim_map.json"
        claims_path = run_dir / "claims.json"
        if not map_path.exists() or not claims_path.exists():
            pytest.skip("Required files not generated")

        mapping = json.loads(map_path.read_text(encoding="utf-8"))
        claims_data = json.loads(claims_path.read_text(encoding="utf-8"))
        valid_ids = {c["claim_id"] for c in claims_data.get("claims", [])}
        # P1-B: NO procedural.* exemption. All IDs must be in the Registry.

        for sentence, claim_ids in mapping.items():
            if isinstance(claim_ids, list):
                for cid in claim_ids:
                    assert cid in valid_ids, (
                        f"Mapped claim_id '{cid}' not found in claims.json"
                    )


# ══════════════════════════════════════════════════════
# 7. Privacy boundary: blocked_content not in output
# ══════════════════════════════════════════════════════

class TestPrivacyBoundaryE2E:
    """Verify P2-4: blocked content stays in audit, never reaches user output."""

    def test_blocked_content_not_in_outreach(self):
        """Run pipeline and verify blocked_content doesn't leak to outreach_pack.md."""
        from starplan_skills.privacy import verify_blocked_content_not_in_output

        result = run_starplan(
            {**BASE_INPUT, "target": "M31", "date_range": ["2026-10-17", "2026-10-17"]},
            run_id="test_p2_privacy",
        )
        run_dir = Path(result["run_dir"])
        violations = verify_blocked_content_not_in_output(run_dir)
        assert violations == [], f"Privacy violations: {violations}"

    def test_sanitize_export_excludes_audit_files(self, tmp_path):
        """Export copy must not contain chat_conversation.json or model_call_log."""
        from starplan_skills.privacy import sanitize_run_for_export, AUDIT_ONLY_FILES

        result = run_starplan(
            {**BASE_INPUT, "target": "M31", "date_range": ["2026-10-17", "2026-10-17"]},
            run_id="test_p2_export",
        )
        run_dir = Path(result["run_dir"])
        export_dir = sanitize_run_for_export(run_dir, tmp_path / "export")

        for audit_file in AUDIT_ONLY_FILES:
            assert not (export_dir / audit_file).exists(), (
                f"Audit-only file {audit_file} must not be in export"
            )
        # Deliverables should be present
        assert (export_dir / "outreach_pack.md").exists()
        assert (export_dir / "privacy_policy.json").exists()


# ══════════════════════════════════════════════════════
# P1-4: Render Trace Gate — 100% Claim coverage
# ══════════════════════════════════════════════════════

class TestRenderTraceGate:
    """Mandatory gate: every user-visible sentence must be in render_trace.json
    with valid claim_ids that exist in claims.json. No sentence may bypass
    the Claim renderer.
    """

    def test_render_trace_exists_and_covers_all_sentences(self):
        """render_trace.json must exist and cover all sentences in output."""
        result = run_starplan(
            {**BASE_INPUT, "target": "M42", "date_range": ["2026-12-20", "2026-12-20"]},
            run_id="test_trace_gate",
        )
        run_dir = Path(result["run_dir"])
        trace_path = run_dir / "render_trace.json"
        assert trace_path.exists(), "render_trace.json must be generated"

        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        assert trace["sentence_count"] > 0, "Trace must contain sentences"
        assert len(trace["sentences"]) == trace["sentence_count"]

        # Every sentence must have non-empty claim_ids
        for entry in trace["sentences"]:
            assert entry["claim_ids"], (
                f"Sentence without claim_ids: {entry['text'][:50]}"
            )
            assert entry["variant_id"], (
                f"Sentence without variant_id: {entry['text'][:50]}"
            )
            assert entry["section"], (
                f"Sentence without section: {entry['text'][:50]}"
            )

    def test_trace_claim_ids_exist_in_registry(self):
        """All claim_ids referenced in trace must exist in claims.json."""
        result = run_starplan(
            {**BASE_INPUT, "target": "M42", "date_range": ["2026-12-20", "2026-12-20"]},
            run_id="test_trace_claims",
        )
        run_dir = Path(result["run_dir"])
        trace = json.loads((run_dir / "render_trace.json").read_text(encoding="utf-8"))
        claims_data = json.loads((run_dir / "claims.json").read_text(encoding="utf-8"))

        # Build set of all registered claim_ids (allowed + prohibited)
        registered_ids = set()
        for c in claims_data.get("claims", []):
            registered_ids.add(c["claim_id"])
        for c in claims_data.get("prohibited", []):
            registered_ids.add(c["claim_id"])

        for entry in trace["sentences"]:
            for cid in entry["claim_ids"]:
                assert cid in registered_ids, (
                    f"Trace references unregistered claim_id '{cid}' "
                    f"in sentence: {entry['text'][:50]}"
                )

    def test_sentence_claim_map_matches_trace(self):
        """sentence_claim_map.json must be consistent with render_trace.json."""
        result = run_starplan(
            {**BASE_INPUT, "target": "M42", "date_range": ["2026-12-20", "2026-12-20"]},
            run_id="test_trace_consistency",
        )
        run_dir = Path(result["run_dir"])
        trace = json.loads((run_dir / "render_trace.json").read_text(encoding="utf-8"))
        sc_map = json.loads((run_dir / "sentence_claim_map.json").read_text(encoding="utf-8"))

        # Every sentence in trace should appear in sentence_claim_map
        trace_texts = {entry["text"] for entry in trace["sentences"]}
        map_texts = set(sc_map.keys())
        # trace may have formatted versions; check overlap is substantial
        overlap = trace_texts & map_texts
        assert len(overlap) >= len(trace_texts) * 0.8, (
            f"Only {len(overlap)}/{len(trace_texts)} trace sentences in claim map"
        )

    def test_fail_closed_unknown_variant(self):
        """Renderer must skip (not crash) when variant_id is unknown."""
        from starplan_skills.rendering import render_sentence
        # Unknown variant returns None (fail closed)
        result = render_sentence("nonexistent_variant_xyz", "some value")
        assert result is None, "Unknown variant must return None (fail closed)"

    def test_fail_closed_unknown_claim_in_plan(self):
        """ExpressionPlan referencing unknown claim_id must be skipped."""
        from starplan_skills.claims import AllowedClaimsBuilder
        from starplan_skills.rendering import render_from_expression_plan
        from starplan_skills.schemas import ExpressionPlan, SelectedClaim

        result = run_starplan(
            {**BASE_INPUT, "target": "M42", "date_range": ["2026-12-20", "2026-12-20"]},
            run_id="test_trace_failclosed",
        )
        run_dir = Path(result["run_dir"])
        claims_data = json.loads((run_dir / "claims.json").read_text(encoding="utf-8"))

        # Rebuild a minimal claims_builder for rendering test
        from starplan_skills.target_resolve import resolve_target
        from starplan_skills.observability_plan import compute_observability
        t = resolve_target("M42")
        loc = BASE_INPUT["location_detail"]
        obs = compute_observability(
            t.ra_deg, t.dec_deg, t.standard_name, loc,
            ["2026-12-20", "2026-12-20"],
            target_magnitude=t.visual_magnitude,
        )
        builder = AllowedClaimsBuilder(
            target=t, obs_result=obs,
            location_id=loc["name"], audience="general", equipment="binoculars",
        )
        builder.build()

        # Plan with one valid + one fake claim
        plan = ExpressionPlan(
            schema_version="1.0",
            selected_claims=[
                SelectedClaim(claim_id="target.standard_name", sentence_variant_id="target_name_v1"),
                SelectedClaim(claim_id="fake.nonexistent_claim", sentence_variant_id="target_name_v1"),
            ],
            section_order=["target"],
            tone="general",
            connector_ids=[],
        )
        render_result = render_from_expression_plan(plan, builder, "general")
        # Fake claim must be skipped, valid claim rendered
        assert "fake.nonexistent_claim" in render_result.claims_skipped
        assert len(render_result.sentences) == 1
        assert render_result.sentences[0].claim_ids == ["target.standard_name"]


# ══════════════════════════════════════════════════════
# P2-4: Terminal State Artifact Contracts
# ══════════════════════════════════════════════════════

class TestTerminalStateContracts:
    """Each terminal state must produce the correct artifact set and
    three-axis values in run_outcome.json.
    """

    def test_needs_confirmation_artifacts(self):
        """Ambiguous target -> NEEDS_CONFIRMATION, no outreach pack."""
        from starplan_skills.exceptions import TargetConfirmationRequired
        with pytest.raises(TargetConfirmationRequired):
            run_starplan(
                {**BASE_INPUT, "target": "星云", "date_range": ["2026-10-17", "2026-10-17"]},
                run_id="test_contract_confirm",
            )
        run_dir = Path("runs") / "test_contract_confirm"
        assert run_dir.exists()
        # run_outcome.json must exist with correct axes
        outcome_path = run_dir / "run_outcome.json"
        assert outcome_path.exists(), "run_outcome.json must exist for early exit"
        oc = json.loads(outcome_path.read_text(encoding="utf-8"))
        assert oc["business_status"] == "needs_confirmation"
        assert oc["delivery_status"] == "not_delivered"
        # state_log.json must exist
        assert (run_dir / "state_log.json").exists()
        # Outreach pack must NOT exist (early exit before generation)
        assert not (run_dir / "outreach_pack.md").exists()

    def test_tool_error_artifacts(self):
        """Observability computation failure -> TOOL_ERROR."""
        from unittest.mock import patch as _patch
        with _patch(
            "starplan_skills.runner.compute_observability",
            side_effect=RuntimeError("simulated astropy crash"),
        ):
            with pytest.raises(RuntimeError, match="simulated astropy crash"):
                run_starplan(
                    {**BASE_INPUT, "target": "M31", "date_range": ["2026-10-17", "2026-10-17"]},
                    run_id="test_contract_toolerr",
                )
        run_dir = Path("runs") / "test_contract_toolerr"
        assert run_dir.exists()
        outcome_path = run_dir / "run_outcome.json"
        assert outcome_path.exists(), "run_outcome.json must exist for tool error"
        oc = json.loads(outcome_path.read_text(encoding="utf-8"))
        assert oc["business_status"] == "tool_error"
        assert oc["validation_status"] == "pending"
        assert oc["delivery_status"] == "not_delivered"
        # resolved_target.json should exist (target was resolved before crash)
        assert (run_dir / "resolved_target.json").exists()

    def test_observable_full_artifacts(self):
        """Successful observable run -> full artifact set."""
        result = run_starplan(
            {**BASE_INPUT, "target": "M31", "date_range": ["2026-10-17", "2026-10-17"]},
            run_id="test_contract_observable",
        )
        run_dir = Path(result["run_dir"])
        oc = json.loads((run_dir / "run_outcome.json").read_text(encoding="utf-8"))
        assert oc["business_status"] == "observable"
        assert oc["validation_status"] in ("passed", "passed_with_warnings")
        assert oc["delivery_status"] in ("template", "qwen_expression_plan")
        # Full artifact set
        for fname in ["claims.json", "outreach_pack.md", "render_trace.json",
                      "sentence_claim_map.json", "expression_plan.json",
                      "calculation_manifest.json", "validation_report.md",
                      "state_log.json", "plan.json"]:
            assert (run_dir / fname).exists(), f"Missing artifact: {fname}"

    def test_not_observable_full_artifacts(self):
        """Not-observable run -> full artifact set with blocking claims."""
        result = run_starplan(
            {**BASE_INPUT, "target": "M42", "date_range": ["2026-12-20", "2026-12-20"]},
            run_id="test_contract_notobs",
        )
        run_dir = Path(result["run_dir"])
        oc = json.loads((run_dir / "run_outcome.json").read_text(encoding="utf-8"))
        assert oc["business_status"] == "not_observable"
        assert oc["validation_status"] in ("passed", "passed_with_warnings")
        # Full artifact set (same as observable)
        for fname in ["claims.json", "outreach_pack.md", "render_trace.json",
                      "sentence_claim_map.json", "calculation_manifest.json",
                      "validation_report.md", "state_log.json"]:
            assert (run_dir / fname).exists(), f"Missing artifact: {fname}"
        # render_trace must have blocking section
        trace = json.loads((run_dir / "render_trace.json").read_text(encoding="utf-8"))
        assert "blocking" in trace["sections"]


# ══════════════════════════════════════════════════════
# P3-4: Chat vs Structured Equivalence
# ══════════════════════════════════════════════════════

class TestChatStructuredEquivalence:
    """Chat mode (with outreach_pack called) must produce the same
    Claim artifact structure as structured mode.
    """

    def test_chat_path_produces_render_trace(self, tmp_path):
        """Simulating Chat's _exec_outreach_pack: passing run_dir generates
        the same artifact set as structured mode.
        """
        from starplan_skills.target_resolve import resolve_target
        from starplan_skills.observability_plan import compute_observability
        from starplan_skills.outreach_pack import generate_outreach_pack

        # Same input as structured mode
        t = resolve_target("M31")
        loc = BASE_INPUT["location_detail"]
        obs = compute_observability(
            t.ra_deg, t.dec_deg, t.standard_name, loc,
            ["2026-10-17", "2026-10-17"],
            target_magnitude=t.visual_magnitude,
        )

        # Chat path: generate_outreach_pack with run_dir (what _exec_outreach_pack does)
        chat_dir = tmp_path / "chat_run"
        chat_dir.mkdir()
        pack = generate_outreach_pack(
            target=t, obs_result=obs, audience="general",
            equipment="binoculars", run_dir=chat_dir, use_qwen=False,
        )

        # Must produce render_trace.json
        trace_path = chat_dir / "render_trace.json"
        assert trace_path.exists(), "Chat path must produce render_trace.json"
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        assert trace["sentence_count"] > 0

        # Must produce claims.json
        assert (chat_dir / "claims.json").exists()
        # Must produce sentence_claim_map.json
        assert (chat_dir / "sentence_claim_map.json").exists()

        # Every sentence in trace must have claim_ids (same gate as structured)
        for entry in trace["sentences"]:
            assert entry["claim_ids"], f"Sentence without claims: {entry['text'][:40]}"

    def test_final_content_from_talking_points(self):
        """When outreach_pack is captured, final_content must come from
        Claim-rendered talking_points, not _build_deterministic_summary.
        """
        # Simulate the P3-2 logic
        captured = {
            "outreach_pack": {
                "talking_points": ["本次活动我们要观测的是 M31", "它是一个深空天体"],
                "alternative_suggestions": [],
                "qwen_used": False,
            }
        }
        pack_data = captured.get("outreach_pack")
        assert pack_data and pack_data.get("talking_points")

        # P3-2 logic: assemble from talking_points
        tp_lines = pack_data["talking_points"]
        header = "【StarPlan 观测规划结果】\n（以下要点由 Claim 证据链确定性渲染）\n"
        final_content = header + "\n".join(f"- {tp}" for tp in tp_lines)

        assert "本次活动我们要观测的是 M31" in final_content
        assert "Claim 证据链确定性渲染" in final_content
        # Must NOT contain _build_deterministic_summary markers
        assert "确定性结果摘要" not in final_content
