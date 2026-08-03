"""R1-R3 closure tests through public/runtime boundaries."""

from __future__ import annotations

import copy
import inspect
import json
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from starplan_skills.claims import AllowedClaimsBuilder
from starplan_skills.observation_review import review_observation
from starplan_skills.run_outcome import DeliveryStatus, RunOutcome
from starplan_skills.schemas import (
    MoonInfo,
    ObservabilityResult,
    RecommendedWindow,
    ResolvedTarget,
    TimeWindow,
    TwilightInfo,
)


def _fake_chat(tool_executors, include_pack: bool = False, include_review: bool = False):
    """Execute legal tool arguments and return a model-like chat response."""
    tool_log = []

    target_raw = tool_executors["target_resolve"](target_name="M31")
    target = json.loads(target_raw)
    tool_log.append({"tool": "target_resolve"})

    loc_raw = tool_executors["resolve_location"](location_name="济南_四门塔")
    loc = json.loads(loc_raw)
    tool_log.append({"tool": "resolve_location"})

    obs_raw = tool_executors["observability_plan"](
        ra_deg=target["ra_deg"],
        dec_deg=target["dec_deg"],
        target_name=target["standard_name"],
        location_name=loc["name"],
        latitude=loc["latitude"],
        longitude=loc["longitude"],
        elevation_m=loc.get("elevation_m", 0),
        date_range=["2026-10-17", "2026-10-17"],
        equipment="binoculars",
    )
    tool_log.append({"tool": "observability_plan"})

    if include_pack:
        tool_executors["outreach_pack"](
            target_name="M31", audience="天文社新成员", equipment="binoculars"
        )
        tool_log.append({"tool": "outreach_pack"})
    if include_review:
        tool_executors["observation_review"](
            target_name="M31", observation_log="本次活动记录"
        )
        tool_log.append({"tool": "observation_review"})

    return {
        "content": "M31 的虚构总结：角距离 999 度，绝不应交付。",
        "messages": [],
        "tool_call_log": tool_log,
        "finish_reason": "stop",
    }


def _run_fake_chat(tmp_path: Path, *, fault: str | None = None, include_pack: bool = False):
    from starplan_skills import runner

    run_dir = tmp_path / "chat_run"

    def fake_get_run_dir(run_id: str) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    original_generate = runner.generate_outreach_pack

    def wrapped_generate(*args, **kwargs):
        if fault == "pack_exception":
            raise RuntimeError("injected pack exception")
        pack = original_generate(*args, **kwargs)
        if fault == "missing_claims":
            (run_dir / "claims.json").unlink()
        elif fault == "missing_rendered_document":
            (run_dir / "rendered_document.json").unlink()
        elif fault == "corrupt_trace":
            (run_dir / "render_trace.json").write_text("{broken", encoding="utf-8")
        return pack

    def fake_call(**kwargs):
        return _fake_chat(kwargs["tool_executors"], include_pack=include_pack)

    with patch("starplan_skills.runner.get_run_dir", side_effect=fake_get_run_dir), \
         patch("starplan_skills.qwen_client.call_qwen_chat", side_effect=fake_call), \
         patch("starplan_skills.runner.generate_outreach_pack", side_effect=wrapped_generate):
        result = runner.run_starplan_chat("规划一次 M31 观测", run_id="chat_fault")
    return result, run_dir


@pytest.mark.parametrize(
    "fault",
    ["pack_exception", "missing_claims", "missing_rendered_document", "corrupt_trace"],
)
def test_chat_faults_are_blocked_without_facts(tmp_path, fault):
    result, run_dir = _run_fake_chat(tmp_path, fault=fault)
    outcome = json.loads((run_dir / "run_outcome.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "calculation_manifest.json").read_text(encoding="utf-8"))
    assert result["public_output_validation"] == "blocked"
    assert outcome["validation_status"] == "blocked"
    assert outcome["delivery_status"] == "not_delivered"
    assert manifest["validation_status"] == "blocked"
    assert "M31" not in result["final_content"]
    assert "999" not in result["final_content"]
    assert "validation_report.md" in result["final_content"]


def test_chat_contract_exception_is_blocked(tmp_path):
    from starplan_skills import runner

    run_dir = tmp_path / "chat_run"

    def fake_get_run_dir(run_id: str) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def fake_call(**kwargs):
        return _fake_chat(kwargs["tool_executors"], include_pack=False)

    with patch("starplan_skills.runner.get_run_dir", side_effect=fake_get_run_dir), \
         patch("starplan_skills.qwen_client.call_qwen_chat", side_effect=fake_call), \
         patch(
             "starplan_skills.expression_validator.validate_delivery_contract",
             side_effect=RuntimeError("injected contract exception"),
         ):
        result = runner.run_starplan_chat("规划一次 M31 观测", run_id="chat_contract_exception")

    outcome = json.loads((run_dir / "run_outcome.json").read_text(encoding="utf-8"))
    assert result["public_output_validation"] == "blocked"
    assert outcome["delivery_status"] == "not_delivered"
    assert "M31" not in result["final_content"]


def test_chat_normal_path_delivers_only_claim_rendered_content(tmp_path):
    result, run_dir = _run_fake_chat(tmp_path)
    manifest = json.loads((run_dir / "calculation_manifest.json").read_text(encoding="utf-8"))
    outcome = json.loads((run_dir / "run_outcome.json").read_text(encoding="utf-8"))
    assert result["public_output_validation"] == "passed"
    assert "999" not in result["final_content"]
    assert "M31" in result["final_content"]
    assert manifest["validation_status"] == "passed"
    assert outcome["delivery_status"] == "template"
    assert (run_dir / "validation_report.md").exists()


def test_chat_review_tool_explicitly_disables_qwen(tmp_path):
    from starplan_skills import runner

    run_dir = tmp_path / "chat_run"

    def fake_get_run_dir(run_id: str) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def fake_call(**kwargs):
        return _fake_chat(kwargs["tool_executors"], include_review=True)

    with patch("starplan_skills.runner.get_run_dir", side_effect=fake_get_run_dir), \
         patch("starplan_skills.qwen_client.call_qwen_chat", side_effect=fake_call), \
         patch("starplan_skills.runner.review_observation", wraps=runner.review_observation) as review_mock:
        runner.run_starplan_chat("规划一次 M31 观测并复盘", run_id="chat_review")

    kwargs = review_mock.call_args.kwargs
    assert kwargs["use_qwen"] is False
    assert kwargs["run_dir"] == run_dir
    assert kwargs["log_path"] == str(run_dir / "model_call_log.jsonl")
    assert kwargs["timezone_name"] == "Asia/Shanghai"


def test_chat_round_limit_is_fail_closed(tmp_path):
    from starplan_skills import runner

    run_dir = tmp_path / "chat_run"

    def fake_get_run_dir(run_id: str) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def fake_call(**kwargs):
        result = _fake_chat(kwargs["tool_executors"], include_pack=False)
        result["finish_reason"] = "max_rounds"
        return result

    with patch("starplan_skills.runner.get_run_dir", side_effect=fake_get_run_dir), \
         patch("starplan_skills.qwen_client.call_qwen_chat", side_effect=fake_call):
        result = runner.run_starplan_chat("规划一次 M31 观测", run_id="chat_round_limit")

    outcome = json.loads((run_dir / "run_outcome.json").read_text(encoding="utf-8"))
    assert result["public_output_validation"] == "blocked"
    assert outcome["delivery_status"] == "not_delivered"
    assert "M31" not in result["final_content"]


def _sample_builder() -> AllowedClaimsBuilder:
    target = ResolvedTarget(
        standard_name="M31", aliases=["仙女座星系"], target_type="deep_sky",
        ra_deg=10.6847, dec_deg=41.2687, visual_magnitude=3.4,
        angular_size_arcmin=[178.0, 63.0], constellation="Andromeda",
        source="built_in_catalog_v1", confidence=0.98,
    )
    window = TimeWindow(
        start=datetime(2026, 10, 17, 20, 30),
        end=datetime(2026, 10, 17, 23, 0),
        duration_minutes=150,
    )
    obs = ObservabilityResult(
        is_observable=True, target_name="M31", location_name="Jinan",
        date_range=[date(2026, 10, 17)],
        recommended_window=RecommendedWindow(
            window=window, peak_altitude_deg=72.5, peak_airmass=1.05, reason="test"
        ),
        twilight=TwilightInfo(astronomical_twilight_end=datetime(2026, 10, 17, 19, 15)),
        moon_info=MoonInfo(phase_fraction=0.35, min_separation_deg=45.2, impact_assessment="low"),
    )
    builder = AllowedClaimsBuilder(target, obs, "Jinan", "astronomy club", "binoculars")
    builder.build()
    return builder


@pytest.mark.parametrize("tamper", ["value", "hash", "delete", "extra", "invalid_json"])
def test_saved_claim_registry_tampering_blocks(tmp_path, tamper):
    builder = _sample_builder()
    builder.save(tmp_path)
    path = tmp_path / "claims.json"
    if tamper == "value":
        data = json.loads(path.read_text(encoding="utf-8"))
        data["claims"][0]["display_value"] = "tampered"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    elif tamper == "hash":
        data = json.loads(path.read_text(encoding="utf-8"))
        data["registry_hash"] = "deadbeef"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    elif tamper == "delete":
        path.unlink()
    elif tamper == "extra":
        data = json.loads(path.read_text(encoding="utf-8"))
        extra = copy.deepcopy(data["claims"][0])
        extra["claim_id"] = "extra.injected"
        data["claims"].append(extra)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    else:
        path.write_text("{invalid", encoding="utf-8")
    assert builder.verify_saved_registry(path)


def test_review_default_is_deterministic():
    assert inspect.signature(review_observation).parameters["use_qwen"].default is False


def test_model_evidence_counts_actual_calls(tmp_path):
    log_path = tmp_path / "model_call_log.jsonl"
    log_path.write_text(
        json.dumps({"type": "model_call", "step": "round0", "model": "qwen-test"}) + "\n"
        + json.dumps({"type": "model_call", "step": "round1", "model": "qwen-test"}) + "\n",
        encoding="utf-8",
    )
    outcome = RunOutcome("model-evidence")
    outcome.import_model_call_events(log_path)
    outcome.set_delivery(DeliveryStatus.TEMPLATE, qwen_used=False)
    assert outcome.model_called is True
    assert outcome.model_output_accepted is False
    assert len(outcome.model_call_events) == 2
    assert outcome.to_audit_summary()["model_call_count"] == 2


def test_model_evidence_zero_and_accepted_states(tmp_path):
    empty = RunOutcome("model-zero")
    empty.import_model_call_events(tmp_path / "missing.jsonl")
    assert empty.model_called is False
    assert empty.to_audit_summary()["model_call_count"] == 0

    path = tmp_path / "one.jsonl"
    path.write_text(json.dumps({"type": "model_call", "step": "expression_plan"}), encoding="utf-8")
    accepted = RunOutcome("model-one")
    accepted.import_model_call_events(path)
    accepted.set_delivery(DeliveryStatus.QWEN_EXPRESSION_PLAN, qwen_used=True)
    assert accepted.model_called is True
    assert accepted.model_output_accepted is True
    assert accepted.to_audit_summary()["model_call_count"] == 1


def test_direct_observability_skill_offline_subprocess(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.pop("DASHSCOPE_API_KEY", None)
    env["STARPLAN_MODEL_MODE"] = "offline"
    env["PYTHONPATH"] = str(project_root)
    env["HTTP_PROXY"] = "http://127.0.0.1:1"
    env["HTTPS_PROXY"] = "http://127.0.0.1:1"
    code = (
        "from starplan_skills.observability_plan import compute_observability; "
        "r=compute_observability(10.6847,41.2687,'M31',"
        "{'name':'Jinan','latitude':36.65,'longitude':117.0,'elevation_m':50,'timezone':'Asia/Shanghai'},"
        "['2026-10-17','2026-10-17']); print(r.target_name)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=project_root, env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "M31" in result.stdout
