# Workflow Release UAT

This document maps the workflow release criteria to runnable checks. It is intentionally release-focused: it verifies the wiring and critical behavior needed to ship the first useful workflow automation release.

## Automated Checks

Backend release criteria:

```bash
sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov -q tests/unit/services/test_workflow_release_criteria.py tests/e2e/test_workflow_uat.py
```

Frontend workflow surface guard:

```bash
cd frontend && npm run check:workflows
```

The frontend guard is a wiring check, not a component or browser test suite. A full React component/E2E harness is still deferred because the frontend currently has no configured Jest, Vitest, or Playwright runner.

## Criteria Map

| Requirement | Automated coverage |
| --- | --- |
| `WF-TEST-01` | `test_workflow_release_criteria.py` covers version snapshots, permissions, scheduling idempotency, state transitions, retry, cancel, budget caps, redaction, artifacts, and representative API-backed runtime behavior. |
| `WF-TEST-02` | `npm run check:workflows` verifies workflow route visibility, overview filters/states, list actions, builder validation/publish/enable/run paths, schedule preview wiring, run actions, timeline rendering, and artifact preview code paths. |
| `WF-TEST-03` | `test_workflow_uat.py` covers Nightly RAG Summary template creation, validation, publish, manual run artifact, daily 02:00 schedule preview, due scheduled run creation, forced RAG failure, retry recovery, disable behavior, and version history. |
| `WF-REL-01` | Release verification must rebuild containers and smoke the live workflow UI/API after implementation changes. |

## Core UAT Scenarios

1. Create Nightly RAG Summary from template, publish, run manually, and verify a summary artifact.
2. Configure the daily `0 2 * * *` schedule, preview next runs, enable the workflow, and verify a queued scheduled run when the trigger is due.
3. Force a RAG step failure, verify the failed run, retry it, and execute the retry successfully.
4. Disable the workflow and verify the scheduler no longer creates a due run.
5. Edit the workflow draft, publish version 2, and verify the original run still references version 1.

## Live Release Smoke

After app changes, always rebuild and recreate the live stack:

```bash
sudo docker compose up -d --build
sudo docker compose up -d --force-recreate enclava-nginx
curl -fsS http://localhost:1080/health
curl -fsSI http://localhost:1080/workflows
```

For an authenticated admin smoke, confirm:

- `GET /api/workflows?resource=admin_metrics` returns scheduler lag, stale locks, failure rate, long-running count, and top workflow cost fields.
- `POST /api/workflows` with `{"action":"recover_stale_locks"}` returns a structured recovery result.
- `POST /api/workflows` with `{"action":"apply_retention","dry_run":true}` returns counts without deleting durable workflow history.
