# Phase 8 Plan 08-02 Summary: Workflow Release Coverage

## Completed

- Added release-focused backend tests for workflow version immutability, owner/manage permissions, redaction, artifacts, budget failure, retry lineage, cancellation, and scheduler idempotency.
- Added deterministic Nightly RAG Summary UAT coverage for template creation, validation, publish, manual execution, schedule preview, due-run creation, disable behavior, failure/retry, and version history.
- Added a no-dependency frontend workflow surface guard at `frontend/scripts/check-workflow-surface.mjs` and exposed it through `npm run check:workflows`.
- Documented release UAT mapping, automated checks, frontend guard limitations, manual smoke expectations, and required rebuild commands in `docs/workflows/uat.md`.

## Verification

- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov -q tests/unit/services/test_workflow_release_criteria.py tests/e2e/test_workflow_uat.py` - 5 passed.
- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test black --check tests/unit/services/test_workflow_release_criteria.py tests/e2e/test_workflow_uat.py` - passed.
- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test isort --check-only tests/unit/services/test_workflow_release_criteria.py tests/e2e/test_workflow_uat.py` - passed.
- `cd frontend && npm run check:workflows` - passed.
- `cd frontend && npm run lint` - passed.
- `cd frontend && npm run check:colors` - passed.
- `cd frontend && npm run check:plumbing` - passed.
- `cd frontend && npm run build` - passed with the existing `NEXT_PUBLIC_BASE_URL not set in production` warning.
- `git diff --check -- . ':!CLAUDE.md' ':!design-proposal'` - passed.
- `sudo docker compose up -d --build` - rebuilt backend, frontend, and migration images.
- `sudo docker compose up -d --force-recreate enclava-nginx` - recreated nginx.
- `curl -fsS http://localhost:1080/health` - returned healthy app response.
- `curl -fsSI http://localhost:1080/workflows` - returned HTTP 200.
- Authenticated live smoke through nginx:
  - `GET /api/workflows?resource=admin_metrics` returned scheduler lag, stale lock, run, failure-rate, and cost metrics.
  - `POST /api/workflows` with `recover_stale_locks` returned a structured success result.
  - `POST /api/workflows` with `apply_retention` and `dry_run: true` returned a structured success result.

## Notes

- The frontend guard checks source wiring for routes, menus, proxy actions, workflow API methods, builder paths, operations console controls, schedule board actions, run detail, and artifact preview behavior. It is not a component/browser test harness.
- No production workflow behavior changed in this plan; the implementation is tests, release guard, documentation, and package script wiring.
