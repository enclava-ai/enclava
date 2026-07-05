# Ingest Decisions: Workflow Automation

Source: `.planning/WORKFLOWS_IMPLEMENTATION_PLAN.md`
Ingested: 2026-07-05

## Decisions

### WF-DEC-01: Workflows are orchestration, agents are workers

Workflows own durable automation state: triggers, schedules, runs, retries, artifacts, budget policy, and audit. Agents remain executable reasoning/action steps inside workflows.

### WF-DEC-02: Operations Console is the default UX

The Workflows route should open on operational visibility rather than a builder. Users should immediately see running workflows, failures, last run, next run, and health.

### WF-DEC-03: Step Builder is linear and typed in v1

The first workflow authoring experience should use a trigger plus ordered typed steps with a properties panel. Freeform visual DAG/canvas behavior is deferred.

### WF-DEC-04: Dedicated workflow APIs are required

Production workflow behavior should use authenticated internal APIs under `/api-internal/v1/workflows`. The generic module execute endpoint is not sufficient for scheduled, auditable, permissioned runs.

### WF-DEC-05: Postgres is the source of truth

Workflow definitions, versions, triggers, runs, step runs, artifacts, and events should be persisted. In-memory workflow state is only acceptable for transient worker-local behavior.

### WF-DEC-06: Start with in-process scheduler and runner

Use a Postgres-backed in-process scheduler and runner first. Escalate to Redis/Celery/RQ or a dedicated worker process only when run volume or horizontal scaling requires it.

### WF-DEC-07: Scheduling is timezone-aware and idempotent

Store run timestamps in UTC, store trigger timezone as an IANA string, preview upcoming run times, and use idempotency keys plus DB locks to prevent duplicate scheduled runs.

### WF-DEC-08: No arbitrary code execution in v1

Workflow steps must be platform-defined and typed. Users should not be able to execute arbitrary code or paste raw secrets into workflow definitions.
