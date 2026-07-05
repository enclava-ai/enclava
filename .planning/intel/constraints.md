# Ingest Constraints: Workflow Automation

Source: `.planning/WORKFLOWS_IMPLEMENTATION_PLAN.md`
Ingested: 2026-07-05

## Constraints

- Do not build an Airflow, Temporal, Zapier, or n8n replacement in the first implementation.
- Do not make a visual DAG/canvas part of the MVP.
- Do not support loops, nested workflows, human approvals, webhooks, API triggers, or arbitrary user code in the first useful release.
- Do not rely on the generic module execute endpoint for production workflow operations.
- Do not persist raw secrets in workflow definitions.
- Store run timestamps in UTC and schedule timezone separately.
- Scheduled workflow creation must be idempotent.
- Published workflow versions must be immutable.
- Archived workflows must not delete historical runs by default.
- The Workflows nav item should appear only after the route exists and the module is enabled.
- Reuse existing frontend primitives, error utilities, toast/confirmation flows, and semantic token conventions from v1.0.
- Rebuild containers after runnable app code changes, but not for documentation-only planning updates.
