---
phase: 07
slug: advanced-control-flow-and-triggers
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-05
---

# Phase 07 - Validation Strategy

Per-phase validation contract for feedback sampling during 07-01 execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest, ESLint, Next build |
| Config file | `backend/pyproject.toml`, `frontend/eslint.config.mjs`, `frontend/package.json` |
| Quick run command | `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov -q tests/unit/services/test_workflow_branch_steps.py tests/unit/services/test_workflow_builder_api.py` |
| Full suite command | `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov -q tests/unit/services/test_workflow_branch_steps.py tests/unit/services/test_workflow_step_handlers.py tests/unit/services/test_workflow_run_api.py tests/unit/services/test_workflow_builder_api.py && cd frontend && npm run lint && npm run check:colors && npm run check:plumbing && npm run build` |
| Estimated runtime | ~90 seconds |

## Sampling Rate

- After backend runtime/catalog/validation changes: run the quick backend command.
- After frontend branch editor changes: run `cd frontend && npm run lint`.
- After the full 07-01 plan: run the full suite command.
- Before live smoke: `git diff --check -- . ':!CLAUDE.md' ':!design-proposal'`.
- Max feedback latency: 120 seconds.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | WF-UX-01, WF-RUN-03 | T-07-01 / T-07-02 | Branch skips are forward-only, persisted, and visible in run detail | unit | `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov -q tests/unit/services/test_workflow_branch_steps.py` | yes | pending |
| 07-01-02 | 01 | 1 | WF-SEC-01, WF-SEC-02 | T-07-01 / T-07-03 | Invalid branch targets/operators are rejected before publish | unit | `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov -q tests/unit/services/test_workflow_builder_api.py` | yes | pending |
| 07-01-03 | 01 | 1 | WF-UX-01, WF-RUN-03 | T-07-02 | Branch editor serializes typed config without graph/canvas UI | frontend | `cd frontend && npm run lint && npm run build` | yes | pending |

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Branch builder readability | WF-UX-01 | No component test runner exists yet | Open `/workflows/new`, add Branch, verify compact controls do not overflow on desktop/mobile. |

## Validation Sign-Off

- [x] All tasks have automated verification or an explicit manual-only reason.
- [x] Sampling continuity has no 3 consecutive tasks without automated verification.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency target is under 120 seconds.

**Approval:** approved 2026-07-05
