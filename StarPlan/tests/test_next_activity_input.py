"""P1 Batch E tests: executable next-round input + before/after re-run.

Acceptance criteria:
- next_activity_input.json passes StarPlanInput Schema.
- A second runner run succeeds and does NOT trigger Review again.
- At least one time/activity field visibly changes (activity_slot start).
- Removing the delay evidence removes the preferred_start patch.
- Only whitelisted fields (activity_preferences.*) are patchable.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from starplan_skills.observation_review import review_observation
from starplan_skills.schemas import ObservationLog, StarPlanInput


LOCATION = {
    "name": "四门塔景区观星点",
    "city": "济南",
    "latitude": 36.49,
    "longitude": 117.18,
    "elevation_m": 300,
    "timezone": "Asia/Shanghai",
}


def _make_obs():
    from starplan_skills.observability_plan import compute_observability
    from starplan_skills.target_resolve import resolve_target

    target = resolve_target("M31")
    return compute_observability(
        ra_deg=target.ra_deg,
        dec_deg=target.dec_deg,
        target_name="M31",
        location=LOCATION,
        date_range=["2026-10-17", "2026-10-17"],
        equipment="binoculars",
    )


def _base_input() -> dict:
    return {
        "target": "M31",
        "location": "济南_四门塔",
        "location_detail": dict(LOCATION),
        "date_range": ["2026-10-17", "2026-10-17"],
        "audience": "天文社新成员",
        "equipment": "binoculars",
        "goal": "校园科普观测",
        "activity_preferences": {
            "duration_minutes": 90,
            "setup_minutes": 15,
            "cleanup_minutes": 15,
        },
    }


def _log(actual_start: str) -> ObservationLog:
    return ObservationLog(
        actual_start_time=actual_start,
        actual_end_time="2026-10-17T22:00:00",
        targets_observed=["M31"],
        targets_missed=[],
        equipment_used="binoculars",
        cloud_cover="clear",
        seeing_conditions="good",
        observer_notes="正常",
        success_rating=4,
    )


class TestNextInputGeneration:
    def test_delay_patches_preferred_start_and_passes_schema(self, tmp_path):
        obs = _make_obs()
        planned = obs.recommended_window.window.start
        actual = planned + timedelta(minutes=30)
        review = review_observation(
            original_plan=obs,
            log=_log(actual.isoformat()),
            run_dir=tmp_path,
            original_input=_base_input(),
            parent_run_id="run-parent-1",
        )

        assert review.next_input_path is not None
        assert review.parent_run_id == "run-parent-1"
        assert "cause.team_late" in review.source_cause_ids
        data = json.loads(Path(review.next_input_path).read_text(encoding="utf-8"))
        # Schema-valid and re-runnable
        parsed = StarPlanInput(**data)
        assert parsed.date_range[0].isoformat() == "2026-10-17"
        # observation_log removed so a re-run does not re-trigger review
        assert "observation_log" not in data
        assert data["activity_preferences"]["preferred_start"] == actual.isoformat()
        # Free-text suggestions must NOT appear as schema fields
        assert "suggestions" not in data and "revisions" not in data

    def test_no_delay_means_no_patch(self, tmp_path):
        obs = _make_obs()
        planned = obs.recommended_window.window.start
        original = _base_input()
        review = review_observation(
            original_plan=obs,
            log=_log(planned.isoformat()),
            run_dir=tmp_path,
            original_input=original,
        )
        assert review.next_input_path is not None
        data = json.loads(Path(review.next_input_path).read_text(encoding="utf-8"))
        assert "preferred_start" not in data.get("activity_preferences", {})
        # equality with original after removing observation_log
        expected = dict(original)
        expected.pop("observation_log", None)
        assert data == expected
        assert review.source_cause_ids == []

    def test_notes_alone_do_not_create_patch(self, tmp_path):
        """Observer notes mentioning lateness are not evidence by themselves."""
        obs = _make_obs()
        planned = obs.recommended_window.window.start
        log = _log(planned.isoformat())
        log.observer_notes = "大家迟到了30分钟"  # text only, structured time says on time
        review = review_observation(
            original_plan=obs,
            log=log,
            run_dir=tmp_path,
            original_input=_base_input(),
        )
        data = json.loads(Path(review.next_input_path).read_text(encoding="utf-8"))
        assert "preferred_start" not in data.get("activity_preferences", {})

    def test_missing_original_input_skips_next_input(self, tmp_path):
        obs = _make_obs()
        planned = obs.recommended_window.window.start
        review = review_observation(
            original_plan=obs,
            log=_log((planned + timedelta(minutes=20)).isoformat()),
            run_dir=tmp_path,
            original_input=None,
        )
        assert review.next_input_path is None


class TestSecondRun:
    def test_second_run_uses_next_input_and_changes_slot(self, tmp_path):
        from starplan_skills import runner

        run1_dir = tmp_path / "run1"
        run2_dir = tmp_path / "run2"
        first_input = _base_input()
        first_input["observation_log"] = {
            "actual_start_time": "2026-10-17T19:45:00",
            "actual_end_time": "2026-10-17T22:00:00",
            "targets_observed": ["M31"],
            "targets_missed": [],
            "equipment_used": "binoculars",
            "cloud_cover": "clear",
            "seeing_conditions": "good",
            "observer_notes": "正常",
            "success_rating": 4,
        }

        def fake_get_run_dir(run_id: str) -> Path:
            target = run1_dir if run_id == "loop_first" else run2_dir
            target.mkdir(parents=True, exist_ok=True)
            return target

        with patch("starplan_skills.runner.get_run_dir", side_effect=fake_get_run_dir), \
             patch("starplan_skills.outreach_pack._qwen_available", return_value=False):
            first = runner.run_starplan(first_input, run_id="loop_first")

        assert first["validation_status"] == "passed"
        review = first["review"]
        assert review is not None and review["next_input_path"] is not None
        next_input = json.loads(
            Path(review["next_input_path"]).read_text(encoding="utf-8")
        )
        StarPlanInput(**next_input)  # schema gate

        with patch("starplan_skills.runner.get_run_dir", side_effect=fake_get_run_dir), \
             patch("starplan_skills.outreach_pack._qwen_available", return_value=False):
            second = runner.run_starplan(next_input, run_id="loop_second")

        assert second["validation_status"] == "passed"
        assert second["review"] is None, "re-run must not trigger Review again"
        before = first["plan"]["activity_slot"]
        after = second["plan"]["activity_slot"]
        assert after["start"] != before["start"]
        # preferred_start 19:45 is honored when it fits inside the science window
        assert after["start"].startswith("2026-10-17T19:45:00")
        assert after["end"] != before["end"]


class TestRunLoopScript:
    def test_run_loop_produces_before_after_report(self):
        project_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env.pop("DASHSCOPE_API_KEY", None)
        env["STARPLAN_MODEL_MODE"] = "offline"
        env["PYTHONPATH"] = str(project_root)
        result = subprocess.run(
            [sys.executable, str(project_root / "scripts" / "run_loop.py"),
             "examples/case_03_observation_review.json"],
            cwd=str(project_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert result.returncode == 0, result.stderr[-1000:]
        report = None
        for p in (project_root / "runs").rglob("loop_before_after.md"):
            report = p
        assert report is not None, "loop_before_after.md not generated"
        content = report.read_text(encoding="utf-8")
        assert "第二次运行" in content
        assert "活动开始" in content
        assert "cause.team_late" in content
