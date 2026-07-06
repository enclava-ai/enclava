# Phase 8 Verification: Hardening, Observability, and Release

## Scope

Phase 8 hardened workflow operations, added stale-lock recovery, retention, admin metrics, release/UAT coverage, operator docs, and final rebuilt-stack smoke checks.

## Automated Evidence

- Workflow hardening suite from 08-01: `tests/unit/services/test_workflow_maintenance.py`, `tests/unit/services/test_workflow_operations_api.py`, and `tests/unit/services/test_workflow_scheduler.py` passed with 16 tests.
- Release criteria and UAT suite from 08-02: `tests/unit/services/test_workflow_release_criteria.py` and `tests/e2e/test_workflow_uat.py` passed with 5 tests.
- Final broad workflow suite from 08-03:

```bash
sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test sh -lc 'pytest --no-cov -q tests/unit/services/test_workflow_*.py tests/e2e/test_workflow_uat.py'
```

Result: 100 passed, 74 warnings.

## Frontend Evidence

- `cd frontend && npm run check:workflows` - passed.
- `cd frontend && npm run lint` - passed.
- `cd frontend && npm run check:colors` - passed.
- `cd frontend && npm run check:plumbing` - passed.
- `cd frontend && npm run build` - passed with the existing `NEXT_PUBLIC_BASE_URL not set in production` warning.

## Live Stack Evidence

- `sudo docker compose up -d --build` rebuilt backend, migrate, and frontend images.
- `sudo docker compose up -d --force-recreate enclava-nginx` recreated nginx.
- `curl --retry 10 --retry-delay 2 --retry-connrefused -fsS http://localhost:1080/health` returned a healthy app response after transient startup 502s.
- `curl --retry 10 --retry-delay 2 --retry-connrefused -fsSI http://localhost:1080/workflows` returned HTTP 200.
- Authenticated workflow operations through nginx returned structured success responses for admin metrics, stale-lock recovery, and retention dry-run.

## Release Readiness

- `WF-OBS-01` is covered by admin metrics and Operations Console exposure.
- `WF-TEST-01` is covered by workflow backend unit/service tests and release criteria tests.
- `WF-TEST-02` is covered by the frontend workflow source-wiring guard.
- `WF-TEST-03` is covered by deterministic Nightly RAG Summary UAT.
- `WF-REL-01` is covered by rebuilt containers and live smoke checks.

## Known Residuals

- Component/browser workflow tests remain deferred until the frontend has a real test harness.
- The runner and scheduler remain in-process with Postgres durability; a distributed worker pool remains deferred.
- Existing Pydantic/Starlette deprecation warnings remain outside the workflow release scope.
