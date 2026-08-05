"""Chat artifact parity regression (2026-08-05 batch).

The chat tool executor previously called compute_observability without
run_dir, so chat run dirs lacked observability.csv and visibility_curve.png
— both declared in skills.yaml's orchestrator artifact list and privacy.py's
export whitelist. These tests pin the fix:

1. Chat runs now persist a non-empty CSV (with header) and a real PNG.
2. Adding non-null path fields to the captured obs dump must NOT break the
   finalizer's Claim-scope rebuild — delivery still passes.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch


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


def _fake_chat_four_tools(tool_executors):
    """Well-behaved model: call all four tools in order."""
    tool_log = []

    target = json.loads(tool_executors["target_resolve"](target_name="M31"))
    tool_log.append({"tool": "target_resolve"})

    loc = json.loads(tool_executors["resolve_location"](location_name="济南_四门塔"))
    tool_log.append({"tool": "resolve_location"})

    tool_executors["observability_plan"](
        ra_deg=target["ra_deg"],
        dec_deg=target["dec_deg"],
        target_name=target["standard_name"],
        location_name="济南四门塔",
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


def _run_chat(tmp_path) -> tuple[dict, Path]:
    from starplan_skills import runner

    run_dir = tmp_path / "chat_artifacts"
    run_dir.mkdir(parents=True, exist_ok=True)

    def fake_get_run_dir(run_id: str) -> Path:
        return run_dir

    def fake_call(**kwargs):
        _write_model_event(kwargs.get("log_path"))
        return _fake_chat_four_tools(kwargs["tool_executors"])

    with patch("starplan_skills.runner.get_run_dir", side_effect=fake_get_run_dir), \
         patch("starplan_skills.qwen_client.call_qwen_chat", side_effect=fake_call):
        result = runner.run_starplan_chat(
            "帮我规划10月17号在济南四门塔观测M31",
            run_id="chat_artifacts_regression",
        )
    return result, run_dir


def test_chat_run_persists_csv_and_curve(tmp_path):
    """Chat runs must produce the same data artifacts as the structured path."""
    result, run_dir = _run_chat(tmp_path)
    assert result["public_output_validation"] == "passed", result

    csv_path = run_dir / "observability.csv"
    assert csv_path.exists(), "chat run must persist observability.csv"
    lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) > 1, "CSV must contain a header plus data rows"
    header = lines[0].lower()
    assert "altitude" in header, f"unexpected CSV header: {lines[0]}"

    png_path = run_dir / "visibility_curve.png"
    assert png_path.exists(), "chat run must persist visibility_curve.png"
    magic = png_path.read_bytes()[:8]
    assert magic == b"\x89PNG\r\n\x1a\n", "curve file is not a valid PNG"
    assert png_path.stat().st_size > 1000, "PNG suspiciously small"


def test_chat_delivery_unaffected_by_artifact_paths(tmp_path):
    """Non-null csv/curve paths in the obs dump must not break Claim scope
    rebuild or delivery: pack rendered, outcome consistent."""
    result, run_dir = _run_chat(tmp_path)

    assert result["hallucination_blocked"] in (True, False)
    assert (run_dir / "claims.json").exists()
    assert (run_dir / "outreach_pack.md").exists()
    assert (run_dir / "rendered_document.json").exists()

    outcome = json.loads((run_dir / "run_outcome.json").read_text(encoding="utf-8"))
    assert outcome["validation_status"] == "passed"
    assert outcome["delivery_status"] in ("template", "delivered")
    assert outcome["business_status"] == "observable"
