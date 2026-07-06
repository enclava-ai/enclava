# Phase 8 Plan 08-03 Summary: Workflow Release Closeout

## Completed

- Added `docs/workflows/release.md` as the operator-facing workflow release checklist.
- Corrected the broad workflow test command in the 08-03 plan and release checklist so shell glob expansion happens inside the backend test container.
- Ran the broad workflow backend suite, frontend workflow guardrails, production build, and final rebuilt-container live smokes.
- Updated requirements, roadmap, project state, and Phase 8 verification artifacts for milestone audit/completion.

## Verification

- Initial broad backend command with an unexpanded host-side glob failed before collecting tests; the command was corrected to run through `sh -lc` inside the container.
- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test sh -lc 'pytest --no-cov -q tests/unit/services/test_workflow_*.py tests/e2e/test_workflow_uat.py'` - 100 passed, 74 warnings.
- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test black --check tests/unit/services/test_workflow_release_criteria.py tests/e2e/test_workflow_uat.py` - passed.
- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test isort --check-only tests/unit/services/test_workflow_release_criteria.py tests/e2e/test_workflow_uat.py` - passed.
- `cd frontend && npm run check:workflows` - passed.
- `cd frontend && npm run lint` - passed.
- `cd frontend && npm run check:colors` - passed.
- `cd frontend && npm run check:plumbing` - passed.
- `cd frontend && npm run build` - passed with the existing `NEXT_PUBLIC_BASE_URL not set in production` warning.
- `git diff --check -- . ':!CLAUDE.md' ':!design-proposal'` - passed.
- `sudo docker compose up -d --build` - rebuilt backend, migrate, and frontend images and restarted live services.
- `sudo docker compose up -d --force-recreate enclava-nginx` - recreated nginx.
- `curl --retry 10 --retry-delay 2 --retry-connrefused -fsS http://localhost:1080/health` - passed after transient startup 502s while services warmed up.
- `curl --retry 10 --retry-delay 2 --retry-connrefused -fsSI http://localhost:1080/workflows` - returned HTTP 200.
- Authenticated live smoke through nginx:
  - `GET /api/workflows?resource=admin_metrics` returned scheduler lag, stale lock, run, failure-rate, and cost metrics.
  - `POST /api/workflows` with `recover_stale_locks` returned a structured success result.
  - `POST /api/workflows` with `apply_retention` and `dry_run: true` returned a structured success result.

## Residual Notes

- Backend test output still includes existing Pydantic and Starlette deprecation warnings.
- Frontend build still emits the existing `NEXT_PUBLIC_BASE_URL not set in production` warning.
- Frontend workflow release coverage is a source-wiring guard; component/browser workflow tests remain deferred.
