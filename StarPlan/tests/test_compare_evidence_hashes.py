"""Regression tests for semantic cross-environment evidence comparison."""

from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import build_evidence_pack
from scripts.build_evidence_pack import _sanitize_value
from scripts.compare_evidence_hashes import _check_case, _value_snapshot


def test_json_snapshot_ignores_key_order_and_integral_float_format(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(
        json.dumps({"constraints": {"max_airmass": 2}, "target": "M31"}),
        encoding="utf-8",
    )
    second.write_text(
        '{"target":"M31","constraints":{"max_airmass":2.0}}',
        encoding="utf-8",
    )

    assert _value_snapshot(first, "json") == _value_snapshot(second, "json")


def test_claim_snapshot_ignores_artifact_hash_chain_but_keeps_claim_values(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    base = {
        "schema_version": "2.0",
        "claims": [
            {
                "claim_id": "target.name",
                "value": "M31",
                "source_hash": "source-a",
            }
        ],
        "prohibited": [],
        "registry_hash": "registry-a",
        "source_artifact_hashes": {
            "target": "target-a",
            "observability": "obs-a",
            "context": "context-a",
        },
        "derivation_rules_hash": "rules-a",
        "template_set_hash": "templates-a",
    }
    changed_hashes = {
        **base,
        "registry_hash": "registry-b",
        "source_artifact_hashes": {
            "target": "target-a",
            "observability": "obs-b",
            "context": "context-a",
        },
        "claims": [{**base["claims"][0], "source_hash": "source-b"}],
    }
    changed_value = {
        **changed_hashes,
        "claims": [{**changed_hashes["claims"][0], "value": "M42"}],
    }
    first.write_text(json.dumps(base), encoding="utf-8")
    second.write_text(json.dumps(changed_hashes), encoding="utf-8")
    assert _value_snapshot(first, "claims") == _value_snapshot(second, "claims")

    second.write_text(json.dumps(changed_value), encoding="utf-8")
    assert _value_snapshot(first, "claims") != _value_snapshot(second, "claims")


def test_evidence_sanitizer_replaces_local_run_paths():
    value = {
        "path": r"C:\Users\alice\project\StarPlan\runs\case\plan.json",
        "nested": [r"C:\Users\alice\project\StarPlan\runs\case\outreach.md"],
    }
    sanitized = _sanitize_value(
        value,
        {r"C:\Users\alice\project\StarPlan\runs\case": "StarPlan/runs/case"},
    )
    assert sanitized == {
        "path": "StarPlan/runs/case/plan.json",
        "nested": ["StarPlan/runs/case/outreach.md"],
    }


def test_missing_manifest_artifact_fails_closed(tmp_path):
    case = {
        "case_id": "synthetic",
        "sha256_prefix": {"input.json": "deadbeefdeadbeef"},
    }

    missing, strict, value, notes = _check_case(case, tmp_path, None)

    assert any("input.json" in item for item in missing)
    assert strict == []
    assert value == []


def test_evidence_builder_rejects_missing_expected_artifact(tmp_path, monkeypatch):
    runs_dir = tmp_path / "runs"
    evidence_dir = tmp_path / "evidence"
    run_dir = runs_dir / "canonical"
    run_dir.mkdir(parents=True)
    (run_dir / "input.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(build_evidence_pack, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(build_evidence_pack, "EVIDENCE_DIR", evidence_dir)

    result = build_evidence_pack._copy_case(
        {
            "case_id": "synthetic",
            "run_id": "canonical",
            "second_run_id": None,
            "title": "synthetic",
            "files": ["input.json", "claims.json"],
        },
        force=False,
    )

    assert result["status"] == "missing_artifact"
    assert result["missing"] == ["claims.json"]
