# Workflow Release Checklist

This checklist closes the first useful Workflows release. It assumes the release
includes durable workflow definitions, versions, triggers, runs, step runs,
events, artifacts, approvals, scheduling, typed builder authoring, operations
views, runtime maintenance, and release UAT coverage.

## Shipped Surface

- Operations Console at `/workflows` with workflow health, filters, run actions,
  schedule board access, and admin metrics for workflow managers.
- Typed workflow builder with trigger configuration, ordered step forms,
  validation, draft save, publish, enable/disable, schedule preview, and run-now
  actions.
- Runtime support for manual, scheduled, API, and event-triggered runs with
  persisted state, retry, cancellation, approval pause/resume, branch skips,
  budget checks, redacted previews, and artifacts.
- Step support for RAG query, agent run, in-app notification, no-results skip,
  connector sync, Extract template execution, branch, and approval request.
- Templates for Nightly RAG Summary, Connector Intake Triage, and Weekly
  Extraction Report.

## Automated Verification

Run the workflow backend release suite:

```bash
sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test sh -lc 'pytest --no-cov -q tests/unit/services/test_workflow_*.py tests/e2e/test_workflow_uat.py'
```

Run formatting checks for the final release/UAT tests:

```bash
sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test black --check tests/unit/services/test_workflow_release_criteria.py tests/e2e/test_workflow_uat.py
sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test isort --check-only tests/unit/services/test_workflow_release_criteria.py tests/e2e/test_workflow_uat.py
```

Run frontend release guardrails:

```bash
cd frontend && npm run check:workflows
cd frontend && npm run lint
cd frontend && npm run check:colors
cd frontend && npm run check:plumbing
cd frontend && npm run build
```

## Rebuild And Live Smoke

After app implementation changes, always rebuild containers and recreate nginx:

```bash
sudo docker compose up -d --build
sudo docker compose up -d --force-recreate enclava-nginx
curl -fsS http://localhost:1080/health
curl -fsSI http://localhost:1080/workflows
```

Then perform authenticated workflow API smokes through nginx:

- `GET /api/workflows?resource=admin_metrics` returns scheduler lag, stale
  locks, failure rate, long-running count, and top workflow cost fields.
- `POST /api/workflows` with `{"action":"recover_stale_locks"}` returns a
  structured recovery result.
- `POST /api/workflows` with `{"action":"apply_retention","dry_run":true}`
  returns counts without deleting durable workflow history.

## Operational Checks

- Review failed and long-running workflow signals in the Operations Console.
- Use stale-lock recovery only after inspecting stuck runs; recovery marks
  expired running runs failed and does not replay partially completed work.
- Keep retention dry-run first. Retention prunes verbose events and artifact
  payload/storage URI data only; definitions, versions, runs, step runs,
  approvals, and audit logs remain durable.
- Confirm schedule previews before publishing or enabling scheduled workflows,
  especially when changing cron or timezone values.

## Deferred Limits

- The frontend release guard is a source-wiring check, not a browser or React
  component test harness.
- The scheduler and runner remain in-process with Postgres-backed durability;
  a distributed worker pool is deferred until run volume requires it.
- Freeform canvas authoring, arbitrary loops, nested workflows, arbitrary user
  code, and unauthenticated public webhooks remain out of scope for this
  release.
