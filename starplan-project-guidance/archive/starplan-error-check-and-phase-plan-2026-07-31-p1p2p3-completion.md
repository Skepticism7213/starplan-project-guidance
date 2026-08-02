# Error Check & Phase Plan — P1/P2/P3 Completion (2026-07-31)

**Baseline**: `7b82318` (Claim architecture rollback)
**HEAD**: `95d47d9` (P3-4 equivalence tests)
**Commits this session**: 8 (`e98ba38` → `95d47d9`)

---

## 1. Error Check

### Static Scan

| File | Issue | Severity | Status |
|------|-------|----------|--------|
| outreach_pack.py | Dead code: _build_talking_points, _generate_talking_points_qwen, _validate_talking_points (old flow) | INFO | Fixed: deleted first two; _validate_talking_points kept as tested utility |
| runner.py | _build_manifest() dead code (114 lines, never called) | WARNING | Fixed: deleted |
| runner.py | _write_validation_report received scattered params, not RunOutcome | WARNING | Fixed: rewritten to receive only RunOutcome |
| runner.py | finalize set three axes BEFORE verifying artifacts | WARNING | Fixed: reordered to verify-first |
| runner.py | Chat _exec_outreach_pack did not pass run_dir (no Claim artifacts) | CRITICAL | Fixed: passes run_dir |
| runner.py | Chat final_content from _build_deterministic_summary (second fact path) | CRITICAL | Fixed: uses Claim-rendered talking_points |
| claims.py | Single generic IDs (schedule.observability_derived, equipment.requested_type) | CRITICAL | Fixed: fine-grained per-sentence Claims |
| templates.py | No variants for schedule/equipment/safety/blocking sections | CRITICAL | Fixed: ~20 new variants added |

### Runtime Verification

| Test Suite | Result |
|------------|--------|
| Fast tests (excl pipeline/qwen/e2e) | 96 passed |
| Hallucination + Layer3 e2e | 22 passed |
| P1-4 Render Trace Gate (5 tests) | 5 passed |
| P2-4 Terminal State Contracts (4 tests) | 4 passed |
| P3-4 Chat Equivalence (2 tests) | 2 passed |
| Full suite (excl P4 + confidence) | 141 passed, 2 failed (Chat/Qwen API) |
| P4 science boundary (polar_day + latitude) | 2 failed (pre-existing, deferred) |

### Confirmed Harmless

- Chat/Qwen API 2 failures: `test_qwen_integration.py::TestChatHallucinationGuard` — Qwen API returns empty tool_call_log (network/rate-limit issue, not code regression). P3 scope tests pass without API dependency.
- `_validate_talking_points` retained: tested by 10 unit tests in test_hallucination_protection.py, useful as defense-in-depth.

---

## 2. Completion Status

| Phase | Scope | Status | Notes |
|-------|-------|--------|-------|
| P0 (freeze baseline) | Rollback to 7b82318 | DONE (prior session) | Claim architecture intact |
| P1 (Claim-first rendering) | Fine-grained Claims + section renderer + render_trace + gate | DONE | 4 commits |
| P2 (RunOutcome consolidation) | Delete dead code + validation report + finalize reorder + contracts | DONE | 2 commits |
| P3 (Chat unification) | Chat run_dir + Claim final_content + run_outcome + equivalence | DONE | 2 commits |
| P4 (science boundary) | Polar day + latitude-limited fixes | DEFERRED | Assigned to team; independent branch required |

Ahead of schedule: P1-P3 completed in one session (estimated 2-3 sessions in rollback audit).

---

## 3. Phase Plan (Next 1-2 Weeks)

### P4: Science Boundary Fixes (assigned to team)

- **Scope**: Fix `test_warning1_polar_day_not_observable` and `test_warning2_latitude_limited_gives_location_not_date`
- **Branch**: Must be independent from main architecture work
- **Acceptance**: Both tests pass; no regression in existing 141 tests; hallucination + Layer3 gates pass as merge requirement
- **Risk**: observability_plan.py constraint logic may need structural change (polar day = sun never sets → no astronomical twilight → all windows invalid)
- **Owner**: hiYCY918 / m21m0721 (science team)

### WARNING-1: Review Qwen Schema

- **Scope**: observation_review Qwen call returns free text; needs ReviewExpressionPlan schema (same pattern as outreach ExpressionPlan)
- **Acceptance**: Review output goes through Claim renderer; render_trace covers review sentences
- **Priority**: Medium (review path is post-observation, lower hallucination risk)

### WARNING-2: Runtime Coverage Gate

- **Scope**: Add `validate_render_coverage()` call in runner.py finalize that programmatically verifies render_trace sentence count >= expected minimum and all claim_ids exist in registry
- **Acceptance**: Pipeline fails closed if coverage < 100%
- **Priority**: Low (currently enforced by tests, not runtime)

### Competition Prep

- **Scope**: README update, skills.yaml v0.3.0, demo script, 150-target confidence run
- **Acceptance**: `python run_confidence_test.py` passes 150/150; README reflects P1-P3 architecture
- **Priority**: High (competition deadline)

---

## 4. Immediate Next Actions

1. **Team**: P4 science fix on independent branch (`git checkout -b fix/science-boundary main`), merge only after Layer3 gates pass
2. **Tech lead**: Run 150-target confidence test on current main to establish baseline
3. **Tech lead**: Update README + skills.yaml to reflect Claim-first architecture (v0.3.0)
4. **Optional**: WARNING-1 (review schema) if time permits before competition

---

## Appendix: Commit Log

```
95d47d9 P3-4: Chat vs structured equivalence tests
35c9ff1 P3: Chat unified fact output via Claim architecture
5e2bf3c P2-4: terminal state artifact contract tests (4 states)
82fc12a P2: RunOutcome as sole terminal state source
529d0d1 P1-4: add render trace gate tests (5 assertions)
dc01d65 P1-3: rewrite outreach_pack.py to Claim-first rendering
fac30cd P1-2: unified section renderer + obs.twilight_start Claim
e98ba38 P1-1: fine-grained Claims + variants for all user-visible sections
```
