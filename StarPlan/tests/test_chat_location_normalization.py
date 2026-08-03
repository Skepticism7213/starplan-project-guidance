"""Chat-mode regression tests from the 2026-08-03 live Qwen review.

- C-6a: Qwen passes the raw user location phrase ("济南四门塔") to
  observability_plan while resolve_location returns a normalized name
  ("四门塔景区观星点"). The runner must normalize so the saved Claim
  scope matches the finalizer's rebuilt registry.
- C-6b: the runner must allow enough tool rounds for one-tool-per-round
  models (4 skills + final answer).
- I-5: procedural schedule claims must not allow schedule_obs_start_v1.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from starplan_skills.claims import AllowedClaimsBuilder
from starplan_skills.schemas import (
    MoonInfo,
    ObservabilityResult,
    RecommendedWindow,
    ResolvedTarget,
    TimeWindow,
    TwilightInfo,
)


def _write_model_event(log_path):
    if not log_path:
        return
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "type": "model_call",
            "step": "chat_orchestration_round0",
            "model": "qwen-test",
        }, ensure_ascii=False) + "\n")


def _fake_chat_with_raw_location(tool_executors, kwargs_capture):
    """Execute all four tools sequentially; pass raw location to observability."""
    kwargs_capture["max_tool_rounds"] = kwargs_capture.get(
        "max_tool_rounds", None
    )
    tool_log = []

    t_raw = tool_executors["target_resolve"](target_name="M31")
    target = json.loads(t_raw)
    tool_log.append({"tool": "target_resolve"})

    l_raw = tool_executors["resolve_location"](location_name="济南_四门塔")
    loc = json.loads(l_raw)
    tool_log.append({"tool": "resolve_location"})

    obs_raw = tool_executors["observability_plan"](
        ra_deg=target["ra_deg"],
        dec_deg=target["dec_deg"],
        target_name=target["standard_name"],
        location_name="济南四门塔",  # raw user phrase, NOT the normalized name
        latitude=loc["latitude"],
        longitude=loc["longitude"],
        elevation_m=loc.get("elevation_m", 0),
        date_range=["2026-10-17", "2026-10-17"],
        equipment="binoculars",
    )
    tool_log.append({"tool": "observability_plan"})

    tool_executors["outreach_pack"](
        target_name="M31", audience="天文社新成员", equipment="binoculars"
    )
    tool_log.append({"tool": "outreach_pack"})

    return {
        "content": "已完成规划。",
        "messages": [],
        "tool_call_log": tool_log,
        "finish_reason": "stop",
    }


def test_chat_normalizes_location_and_delivers(tmp_path):
    """Real Qwen input shape (raw location) must not block delivery."""
    from starplan_skills import runner

    run_dir = tmp_path / "chat_location"
    kwargs_capture: dict = {}

    def fake_get_run_dir(run_id: str) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def fake_call(**kwargs):
        kwargs_capture.update(kwargs)
        _write_model_event(kwargs.get("log_path"))
        return _fake_chat_with_raw_location(kwargs["tool_executors"], kwargs_capture)

    with patch("starplan_skills.runner.get_run_dir", side_effect=fake_get_run_dir), \
         patch("starplan_skills.qwen_client.call_qwen_chat", side_effect=fake_call):
        result = runner.run_starplan_chat(
            "帮我规划10月17号在济南四门塔观测M31",
            run_id="chat_location_regression",
        )

    assert result["public_output_validation"] == "passed", result
    assert result["model_call_count"] == 1
    assert (run_dir / "claims.json").exists()
    assert (run_dir / "outreach_pack.md").exists()
    outcome = json.loads((run_dir / "run_outcome.json").read_text(encoding="utf-8"))
    assert outcome["validation_status"] == "passed"
    assert outcome["delivery_status"] == "template"


def test_chat_round_limit_is_six_or_more(tmp_path):
    """C-6b: the orchestrator must allow 4 tool rounds + final answer."""
    from starplan_skills import runner

    run_dir = tmp_path / "chat_rounds"
    kwargs_capture: dict = {}

    def fake_get_run_dir(run_id: str) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def fake_call(**kwargs):
        kwargs_capture.update(kwargs)
        _write_model_event(kwargs.get("log_path"))
        return _fake_chat_with_raw_location(kwargs["tool_executors"], kwargs_capture)

    with patch("starplan_skills.runner.get_run_dir", side_effect=fake_get_run_dir), \
         patch("starplan_skills.qwen_client.call_qwen_chat", side_effect=fake_call):
        runner.run_starplan_chat("帮我规划10月17号在济南四门塔观测M31", run_id="chat_rounds_regression")

    assert kwargs_capture["max_tool_rounds"] >= 6


def _sample_builder() -> AllowedClaimsBuilder:
    target = ResolvedTarget(
        standard_name="M31",
        aliases=["仙女座星系"],
        target_type="deep_sky",
        ra_deg=10.6847,
        dec_deg=41.2688,
        visual_magnitude=3.4,
        angular_size_arcmin=[178.0, 63.0],
        constellation="Andromeda",
        source="built_in_catalog_v1",
        confidence=0.98,
    )
    window = TimeWindow(
        start=datetime(2026, 10, 17, 20, 30),
        end=datetime(2026, 10, 17, 23, 0),
        duration_minutes=150,
    )
    obs = ObservabilityResult(
        is_observable=True,
        target_name="M31",
        location_name="四门塔景区观星点",
        date_range=[date(2026, 10, 17)],
        recommended_window=RecommendedWindow(
            window=window, peak_altitude_deg=72.5, peak_airmass=1.05, reason="test"
        ),
        twilight=TwilightInfo(astronomical_twilight_end=datetime(2026, 10, 17, 19, 15)),
        moon_info=MoonInfo(phase_fraction=0.35, min_separation_deg=45.2, impact_assessment="low"),
    )
    builder = AllowedClaimsBuilder(target, obs, "四门塔景区观星点", "天文社新成员", "binoculars")
    builder.build()
    return builder


def test_schedule_claims_variant_allowlist_tightened():
    """I-5: schedule.obs_guide must not allow '开始观测' template."""
    builder = _sample_builder()
    guide = builder.get_claim("schedule.obs_guide")
    assert guide is not None
    assert guide.allowed_variant_ids == ["schedule_proc_v1"]
    assert "schedule_obs_start_v1" not in guide.allowed_variant_ids

    for cid in ("schedule.obs_progress", "schedule.obs_end", "schedule.obs_descend"):
        claim = builder.get_claim(cid)
        assert claim is not None
        assert "schedule_obs_start_v1" not in claim.allowed_variant_ids
    cleanup = builder.get_claim("schedule.cleanup")
    assert cleanup is not None
    assert "schedule_twilight_end_v1" in cleanup.allowed_variant_ids
    assert "schedule_obs_start_v1" not in cleanup.allowed_variant_ids
