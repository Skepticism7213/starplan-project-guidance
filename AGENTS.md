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

## Documentation Style

- Write project materials in UTF-8 Markdown.
- Use concrete acceptance criteria instead of vague wording such as “improve” or “make complete”.
- Separate confirmed facts, assumptions, proposed work, and items awaiting team confirmation.
- Keep examples reproducible and label simulated or placeholder data clearly.

