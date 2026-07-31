# StarPlan Project Guidance Repository

## Purpose

This repository stores the planning, transfer, prompt, review, and competition-preparation materials for the StarPlan Loop project.

The project targets Challenge Cup Track 3, Direction 3: “星语·面向 AI 的天文实训”. The current product direction is a Qwen-callable Skills package for the closed loop:

```text
observation request
-> deterministic astronomy calculation
-> observation plan and outreach pack
-> observation log
-> evidence-based review
-> revised next plan
```

## Source Of Truth

Use the documents in `starplan-project-guidance/` in this order:

1. `starplan-loop-project-plan.md` is the current project scope and delivery baseline.
2. `starplan-loop-competition-enhancements.md` contains optional competition-strengthening ideas and their priorities.
3. `qwen-project-kickoff-prompt.md` is the startup instruction for Qwen/QoderWork.
4. `starplan-qoderwork-transfer-log.md` is the implementation handoff context aligned to the current plan.
5. `starplan-transfer-log-diff.md` records the changes made while aligning the handoff context.
6. `starplan-loop-kickoff-report.md` is supporting kickoff analysis and should not override the project plan.
7. `starplan-error-check-and-phase-plan.md` is the template for the mandatory end-of-work error-check and phase-plan report (see Working Rules).

If two documents conflict, follow the project plan and record the difference in the transfer diff log before changing downstream material.

## Working Rules

- Keep the MVP limited to four core Skills: `target_resolve`, `observability_plan`, `outreach_pack`, and `observation_review`.
- Treat Qwen as the language, orchestration, and explanation layer. Do not let the model invent astronomical numerical results.
- Use deterministic astronomy tools for coordinates, altitude, azimuth, airmass, twilight, and moon-impact calculations.
- Preserve input, intermediate results, tool/model versions, validation results, and human confirmations for every reproducible case.
- Keep planets, live services, Stellarium/Aladin integration, horizon obstruction models, telescope control, and complex frontend work as post-MVP extensions unless the project plan is explicitly revised.
- Prefer focused Markdown edits and keep source references, licenses, and unknown competition requirements explicit.
- Never add API keys, tokens, passwords, or private user data to this repository.
- When adding or changing a project decision, update the project plan first, then update the transfer log and diff log as needed.

## Collaboration And Branch Discipline

- Before editing, fetch the remote and update from the latest `origin/main`. Confirm that the working base contains the current remote commit; if fetch or update cannot be verified, stop and record the blocker instead of editing from a stale checkout.
- Before pushing, inspect `git status`, review the complete diff, and verify the branch relationship with `git rev-list --left-right --count origin/main...HEAD`. Do not push a history that silently drops commits already on `origin/main`.
- Completing the hallucination-prevention architecture in project-plan Phase 3 is the current blocking priority. Until its acceptance gates pass, do not overwrite or bypass `claims.py`, `rendering.py`, `expression_validator.py`, `runner.py`, `outreach_pack.py`, `run_outcome.py`, the sentence-template library, or Layer 3/adversarial tests.
- Scientific validation and astronomy-correctness fixes must start from the latest `main` on a dedicated branch. Keep those changes narrowly scoped, run the hallucination and Layer 3 gates as merge requirements, and merge them only after the trusted-output architecture is complete or after explicit project-owner approval.
- When a merge or rebase conflicts with protected architecture files, stop and reconcile the conflict line by line. Never accept an entire incoming or local file merely to clear the conflict, and never restore an older tree over newer trusted-output work.
- If a collaborator needs to continue science work before the architecture gate is complete, preserve it on a separate branch and report the base commit, changed files, tests, and intended later merge point in the mandatory end-of-work report.

## Mandatory End-Of-Work Report

After completing any meaningful unit of work (a finished feature, a fixed bug batch, a completed project phase, or before handing off to another person/agent), the working agent MUST produce an "error check and phase plan" report — even if the user did not explicitly ask for one. This applies to every agent working on this repository, including other collaborators' agents.

The report must be saved as a UTF-8 Markdown file in `starplan-project-guidance/` and follow the structure of the template `starplan-error-check-and-phase-plan.md`. It must contain at least:

1. **Error check** — a static + runtime scan result for the touched code and data: list every issue found by severity (CRITICAL / WARNING / INFO), state whether each was fixed or confirmed harmless, and confirm the affected cases still compile and run without errors.
2. **Completion status** — what was done, mapped against the project plan's phase schedule, noting anything ahead of or behind schedule.
3. **Phase plan** — concrete next steps for the coming week(s) with acceptance criteria, blocking items, and risks.
4. **Immediate next actions** — the smallest set of things the team or next agent should do first.

Do not claim work is finished until this report exists and the relevant cases pass. Commit and push the report together with the code changes; do not let reports or code accumulate unpushed.

## Documentation Style

- Write project materials in UTF-8 Markdown.
- Use concrete acceptance criteria instead of vague wording such as “improve” or “make complete”.
- Separate confirmed facts, assumptions, proposed work, and items awaiting team confirmation.
- Keep examples reproducible and label simulated or placeholder data clearly.

