"""
Phase A: Delivery Contract Gate Tests (C-01 + C-02 verification).

7 fault injection tests + 2 bidirectional coverage tests.
All tests use a pre-built M31 observable run to avoid slow computation.

Requirement: every fault must produce passed=False (→ BLOCKED in runner).
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from starplan_skills.expression_validator import validate_delivery_contract
from starplan_skills.rendering import RenderedDocument
from starplan_skills.claims import AllowedClaimsBuilder


# ── Fixture: build a valid M31 run once per module ──

_RUN_DIR: Path | None = None
_RENDERED_DOC: RenderedDocument | None = None
_CLAIMS_BUILDER: AllowedClaimsBuilder | None = None


def _build_valid_run():
    """Build a complete valid M31 observable run for testing."""
    global _RUN_DIR, _RENDERED_DOC, _CLAIMS_BUILDER
    if _RUN_DIR is not None:
        return

    from starplan_skills.target_resolve import resolve_target
    from starplan_skills.observability_plan import compute_observability
    from starplan_skills.outreach_pack import generate_outreach_pack

    t = resolve_target("M31")
    loc = {"name": "Jinan", "latitude": 36.65, "longitude": 117.0, "elevation": 50}
    obs = compute_observability(
        t.ra_deg, t.dec_deg, t.standard_name, loc, ["2026-10-17", "2026-10-17"]
    )
    run_dir = Path(tempfile.mkdtemp(prefix="starplan_gate_"))
    generate_outreach_pack(t, obs, "astronomy club", "binoculars", run_dir=run_dir, use_qwen=False)

    rd_data = json.loads((run_dir / "rendered_document.json").read_text(encoding="utf-8"))
    rendered_doc = RenderedDocument.from_dict(rd_data)

    cb = AllowedClaimsBuilder(t, obs, "Jinan", "astronomy club", "binoculars")
    cb.build()

    _RUN_DIR = run_dir
    _RENDERED_DOC = rendered_doc
    _CLAIMS_BUILDER = cb


def _fresh_run_dir() -> Path:
    """Copy the valid run to a fresh temp dir for destructive testing."""
    _build_valid_run()
    dst = Path(tempfile.mkdtemp(prefix="starplan_fault_"))
    shutil.copytree(_RUN_DIR, dst, dirs_exist_ok=True)
    return dst


# ── Baseline: valid run passes ──


class TestDeliveryContractBaseline:
    """Verify the valid run passes the delivery contract."""

    def test_valid_run_passes(self):
        _build_valid_run()
        result = validate_delivery_contract(_RUN_DIR, _RENDERED_DOC, _CLAIMS_BUILDER)
        assert result.passed, f"Valid run should pass: {[e.message for e in result.errors]}"


# ── 7 Fault Injection Tests ──


class TestDeliveryContractGate:
    """7 fault injection tests: each must produce passed=False (BLOCKED)."""

    def test_missing_trace_blocked(self):
        """D1: delete render_trace.json → blocked."""
        run_dir = _fresh_run_dir()
        (run_dir / "render_trace.json").unlink()
        result = validate_delivery_contract(run_dir, _RENDERED_DOC, _CLAIMS_BUILDER)
        assert not result.passed
        assert any("render_trace.json" in e.message for e in result.errors)

    def test_corrupt_json_blocked(self):
        """D2: write invalid JSON to render_trace.json → blocked."""
        run_dir = _fresh_run_dir()
        (run_dir / "render_trace.json").write_text("{invalid json!!!", encoding="utf-8")
        result = validate_delivery_contract(run_dir, _RENDERED_DOC, _CLAIMS_BUILDER)
        assert not result.passed
        assert any("not valid JSON" in e.message for e in result.errors)

    def test_fake_claim_id_blocked(self):
        """D3: inject a fake claim_id into rendered_document → blocked."""
        run_dir = _fresh_run_dir()
        # Modify the rendered_document to reference a non-existent claim
        rd_data = json.loads((run_dir / "rendered_document.json").read_text(encoding="utf-8"))
        rd_data["body_blocks"][0]["claim_ids"] = ["fake.nonexistent.claim"]
        fake_doc = RenderedDocument.from_dict(rd_data)
        result = validate_delivery_contract(run_dir, fake_doc, _CLAIMS_BUILDER)
        assert not result.passed
        assert any("unknown claim_id" in e.message for e in result.errors)

    def test_deleted_claim_blocked(self):
        """D3: reference a PROHIBITED claim → blocked."""
        run_dir = _fresh_run_dir()
        # Use a claim_id that exists but is PROHIBITED
        rd_data = json.loads((run_dir / "rendered_document.json").read_text(encoding="utf-8"))
        # Find a prohibited claim from the builder
        prohibited_ids = [c.claim_id for c in _CLAIMS_BUILDER.claims
                         if c.claim_type.value == "prohibited"]
        if prohibited_ids:
            rd_data["body_blocks"][0]["claim_ids"] = [prohibited_ids[0]]
            fake_doc = RenderedDocument.from_dict(rd_data)
            result = validate_delivery_contract(run_dir, fake_doc, _CLAIMS_BUILDER)
            assert not result.passed
            # get_claim() only searches allowed claims, so prohibited shows as unknown
            assert any(
                "PROHIBITED" in e.message or "unknown claim_id" in e.message
                for e in result.errors
            )
        else:
            pytest.skip("No prohibited claims in registry")

    def test_wrong_variant_blocked(self):
        """D3: use a variant not in the claim's allowed_variant_ids → blocked."""
        run_dir = _fresh_run_dir()
        rd_data = json.loads((run_dir / "rendered_document.json").read_text(encoding="utf-8"))
        # Set a variant that exists in templates but is NOT in the claim's allowlist
        rd_data["body_blocks"][0]["variant_id"] = "target_name_not_obs_v1"
        fake_doc = RenderedDocument.from_dict(rd_data)
        result = validate_delivery_contract(run_dir, fake_doc, _CLAIMS_BUILDER)
        assert not result.passed
        assert any("variant" in e.message.lower() for e in result.errors)

    def test_hash_mismatch_blocked(self):
        """D4: modify final_text without updating hash → blocked."""
        run_dir = _fresh_run_dir()
        rd_data = json.loads((run_dir / "rendered_document.json").read_text(encoding="utf-8"))
        # Tamper with final_text (hash is computed property, so from_dict will
        # recompute it — but the TRACE file still has the old hash)
        # Instead, tamper with the trace file directly
        trace = json.loads((run_dir / "render_trace.json").read_text(encoding="utf-8"))
        if trace["sentences"]:
            trace["sentences"][0]["text_hash"] = "deadbeef0000"
        (run_dir / "render_trace.json").write_text(
            json.dumps(trace, ensure_ascii=False), encoding="utf-8"
        )
        result = validate_delivery_contract(run_dir, _RENDERED_DOC, _CLAIMS_BUILDER)
        assert not result.passed
        assert any("hash" in e.message.lower() for e in result.errors)

    def test_extra_fact_blocked(self):
        """D5: insert an extra fact line into Markdown not in trace → blocked."""
        run_dir = _fresh_run_dir()
        md_path = run_dir / "outreach_pack.md"
        md_content = md_path.read_text(encoding="utf-8")
        # Insert a fake fact line
        md_content += "\n- This is a fabricated fact not in any trace\n"
        md_path.write_text(md_content, encoding="utf-8")
        result = validate_delivery_contract(
            run_dir, _RENDERED_DOC, _CLAIMS_BUILDER, final_markdown=md_content
        )
        assert not result.passed
        assert any("not in trace" in e.message for e in result.errors)


# ── Bidirectional Coverage Tests ──


class TestBidirectionalCoverage:
    """Verify 100% bidirectional coverage for observable and not-observable."""

    def test_observable_bidirectional(self):
        """M31 observable: every trace entry in MD, every MD fact in trace."""
        _build_valid_run()
        md = (_RUN_DIR / "outreach_pack.md").read_text(encoding="utf-8")
        result = validate_delivery_contract(
            _RUN_DIR, _RENDERED_DOC, _CLAIMS_BUILDER, final_markdown=md
        )
        # Filter only bidirectional errors (step 5)
        bidir_errors = [e for e in result.errors if e.step == 5]
        assert not bidir_errors, (
            f"Bidirectional coverage failed: {[e.message for e in bidir_errors[:5]]}"
        )

    def test_not_observable_bidirectional(self):
        """M42 not-observable: every trace entry in MD, every MD fact in trace."""
        from starplan_skills.target_resolve import resolve_target
        from starplan_skills.observability_plan import compute_observability
        from starplan_skills.outreach_pack import generate_outreach_pack

        t = resolve_target("M42")
        loc = {"name": "Jinan", "latitude": 36.65, "longitude": 117.0, "elevation": 50}
        obs = compute_observability(
            t.ra_deg, t.dec_deg, t.standard_name, loc, ["2026-07-25", "2026-07-25"]
        )
        run_dir = Path(tempfile.mkdtemp(prefix="starplan_notobs_"))
        generate_outreach_pack(t, obs, "astronomy club", "binoculars", run_dir=run_dir, use_qwen=False)

        rd_data = json.loads((run_dir / "rendered_document.json").read_text(encoding="utf-8"))
        rendered_doc = RenderedDocument.from_dict(rd_data)
        cb = AllowedClaimsBuilder(t, obs, "Jinan", "astronomy club", "binoculars")
        cb.build()

        md = (run_dir / "outreach_pack.md").read_text(encoding="utf-8")
        result = validate_delivery_contract(run_dir, rendered_doc, cb, final_markdown=md)
        bidir_errors = [e for e in result.errors if e.step == 5]
        assert not bidir_errors, (
            f"Not-observable bidirectional failed: {[e.message for e in bidir_errors[:5]]}"
        )
