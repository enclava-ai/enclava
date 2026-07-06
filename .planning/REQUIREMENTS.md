# Requirements: Enclava Workflow Automation

**Defined:** 2026-07-05
**Milestone:** v1.1 Workflow Automation
**Source:** `.planning/WORKFLOWS_IMPLEMENTATION_PLAN.md`
**Core Value:** Users can run confidential AI automations that are scheduled, auditable, observable, budget-aware, and clear to operate.

## v1.1 Requirements

### Product Model and UX

- [x] **WF-UX-01**: Workflows are modeled as durable automations that coordinate triggers, steps, runtime policy, ownership, run state, artifacts, permissions, budget, and audit.
- [x] **WF-UX-02**: Agents are executable steps inside workflows and do not own schedule, retry, approval, artifact, or workflow-level audit state.
- [x] **WF-UX-03**: The primary Workflows route opens on an Operations Console that shows active workflows, failures, latest run, next run, owner, health, and primary actions.
- [x] **WF-UX-04**: Workflow authoring uses a typed trigger-plus-ordered-steps builder with a properties panel and validation summary.
- [x] **WF-UX-05**: Schedule management exposes upcoming runs, missed/failed schedule health, and next-run previews.

### Definition Lifecycle and Persistence

- [x] **WF-DATA-01**: Workflow definitions, versions, triggers, runs, step runs, artifacts, and events are persisted through migrations and SQLAlchemy models.
- [x] **WF-DATA-02**: Published workflow versions are immutable, and historical runs retain the version they executed.
- [x] **WF-DATA-03**: Workflow lifecycle supports draft, publish, enable, disable, archive, and safe deletion behavior.
- [x] **WF-DATA-04**: Workflow APIs use authenticated internal endpoints under `/api-internal/v1/workflows`.
- [x] **WF-DATA-05**: Workflow module status remains compatible with the existing module system while real business behavior moves into workflow services.

### Execution Engine

- [x] **WF-RUN-01**: Users can manually run a published workflow and inspect persisted run state after backend restart.
- [x] **WF-RUN-02**: Workflow runner safely claims queued runs, executes steps in order, persists state transitions, and records structured errors.
- [x] **WF-RUN-03**: Run detail exposes metadata, step timeline, events, redacted inputs/outputs, artifacts, retry, and cancellation controls.
- [x] **WF-RUN-04**: Step retry, timeout, cancellation checks, and failure handling are enforced consistently.
- [x] **WF-RUN-05**: MVP step types include `rag.query`, `agent.run`, `notify.in_app`, and a simple no-results skip condition.

### Scheduling and Operations

- [x] **WF-SCHED-01**: Scheduled workflows support cron plus IANA timezone configuration and preview upcoming run times before publish.
- [x] **WF-SCHED-02**: Scheduled run creation is idempotent and avoids duplicates across backend restart or multiple scheduler ticks.
- [x] **WF-SCHED-03**: Scheduler supports misfire policy and concurrency policy for skipped, catch-up, or queue-after-current behavior.
- [x] **WF-SCHED-04**: Operations Console highlights failed, running, disabled, and next-due workflow states without requiring the builder.

### Builder, Templates, and Validation

- [x] **WF-BUILD-01**: The step registry exposes available step types, config schemas, input/output schemas, permissions, retry support, and cost hints to the frontend.
- [x] **WF-BUILD-02**: Builder validates required trigger and step fields before publish and shows actionable per-step errors.
- [x] **WF-BUILD-03**: Templates exist for Nightly RAG Summary, Connector Intake Triage, and Weekly Extraction Report.
- [x] **WF-BUILD-04**: The first end-to-end template is Nightly RAG Summary with schedule, RAG query, no-results skip, agent summary, artifact, and notification behavior.

### Integrations

- [x] **WF-INT-01**: Connector sync can be used as a workflow step and returns newly ingested records for downstream steps.
- [x] **WF-INT-02**: Extract template execution can be used as a workflow step and saves outputs as workflow artifacts.
- [x] **WF-INT-03**: Workflow artifacts support summary, JSON, extraction result, notification, and file-reference style outputs.

### Security, Governance, and Observability

- [x] **WF-SEC-01**: Workflow lifecycle and run actions enforce workflow permissions and step-level permissions.
- [x] **WF-SEC-02**: Workflow lifecycle changes, schedule changes, run requests, cancellations, retries, and approvals are audited.
- [x] **WF-SEC-03**: Workflow and run budget caps prevent unbounded spend and attribute usage to workflow runs and steps where possible.
- [x] **WF-SEC-04**: Sensitive fields, credentials, headers, and raw document content are redacted from logs and persisted previews.
- [x] **WF-OBS-01**: Admin/operator views expose failed workflows, long-running workflows, scheduler lag, stale locks, failure rates, and top workflows by cost.

### Release Readiness

- [x] **WF-TEST-01**: Backend tests cover validation, versioning, permissions, scheduling, idempotency, run state transitions, retries, budget caps, redaction, artifacts, and APIs.
- [x] **WF-TEST-02**: Frontend tests cover route visibility, overview states, list filtering, run actions, builder validation, schedule preview, run timeline, and artifact preview.
- [x] **WF-TEST-03**: End-to-end UAT covers Nightly RAG Summary, schedule preview, due run creation, failure/retry, disable behavior, and version history.
- [x] **WF-REL-01**: Containers are rebuilt after app implementation changes and smoke checks confirm the latest workflow UI/API are running.

## Deferred Beyond First Useful Release

- Freeform DAG/canvas authoring.
- Arbitrary loops.
- Nested workflows.
- Arbitrary user code execution.
- External webhook calls without outbound security policy.
- API/event triggers before idempotency and auth semantics are finalized.
- Human approval flow before pause/resume and approval permissions are implemented.
- Dedicated distributed worker pool unless run volume requires it.

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| WF-UX-01 | Phase 1 | Complete |
| WF-UX-02 | Phase 1 | Complete |
| WF-UX-03 | Phase 4 | Complete |
| WF-UX-04 | Phase 5 | Complete |
| WF-UX-05 | Phase 4 | Complete |
| WF-DATA-01 | Phase 2 | Complete |
| WF-DATA-02 | Phase 2 | Complete |
| WF-DATA-03 | Phase 2 | Complete |
| WF-DATA-04 | Phase 2 | Complete |
| WF-DATA-05 | Phase 1 | Complete |
| WF-RUN-01 | Phase 3 | Complete |
| WF-RUN-02 | Phase 3 | Complete |
| WF-RUN-03 | Phase 3 | Complete |
| WF-RUN-04 | Phase 3 | Complete |
| WF-RUN-05 | Phase 3 | Complete |
| WF-SCHED-01 | Phase 4 | Complete |
| WF-SCHED-02 | Phase 4 | Complete |
| WF-SCHED-03 | Phase 4 | Complete |
| WF-SCHED-04 | Phase 4 | Complete |
| WF-BUILD-01 | Phase 5 | Complete |
| WF-BUILD-02 | Phase 5 | Complete |
| WF-BUILD-03 | Phase 5 | Complete |
| WF-BUILD-04 | Phase 5 | Complete |
| WF-INT-01 | Phase 6 | Complete |
| WF-INT-02 | Phase 6 | Complete |
| WF-INT-03 | Phase 6 | Complete |
| WF-SEC-01 | Phase 2 | Complete |
| WF-SEC-02 | Phase 2 | Complete |
| WF-SEC-03 | Phase 3 | Complete |
| WF-SEC-04 | Phase 3 | Complete |
| WF-OBS-01 | Phase 8 | Complete |
| WF-TEST-01 | Phase 8 | Complete |
| WF-TEST-02 | Phase 8 | Complete |
| WF-TEST-03 | Phase 8 | Complete |
| WF-REL-01 | Phase 8 | Complete |

---
*Requirements completed: 2026-07-06 after Phase 8 release closeout*
