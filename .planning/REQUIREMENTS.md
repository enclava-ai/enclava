# Requirements: Enclava Workflow Automation

**Defined:** 2026-07-05
**Milestone:** v1.1 Workflow Automation
**Source:** `.planning/WORKFLOWS_IMPLEMENTATION_PLAN.md`
**Core Value:** Users can run confidential AI automations that are scheduled, auditable, observable, budget-aware, and clear to operate.

## v1.1 Requirements

### Product Model and UX

- [ ] **WF-UX-01**: Workflows are modeled as durable automations that coordinate triggers, steps, runtime policy, ownership, run state, artifacts, permissions, budget, and audit.
- [ ] **WF-UX-02**: Agents are executable steps inside workflows and do not own schedule, retry, approval, artifact, or workflow-level audit state.
- [ ] **WF-UX-03**: The primary Workflows route opens on an Operations Console that shows active workflows, failures, latest run, next run, owner, health, and primary actions.
- [ ] **WF-UX-04**: Workflow authoring uses a typed trigger-plus-ordered-steps builder with a properties panel and validation summary.
- [ ] **WF-UX-05**: Schedule management exposes upcoming runs, missed/failed schedule health, and next-run previews.

### Definition Lifecycle and Persistence

- [ ] **WF-DATA-01**: Workflow definitions, versions, triggers, runs, step runs, artifacts, and events are persisted through migrations and SQLAlchemy models.
- [ ] **WF-DATA-02**: Published workflow versions are immutable, and historical runs retain the version they executed.
- [ ] **WF-DATA-03**: Workflow lifecycle supports draft, publish, enable, disable, archive, and safe deletion behavior.
- [ ] **WF-DATA-04**: Workflow APIs use authenticated internal endpoints under `/api-internal/v1/workflows`.
- [ ] **WF-DATA-05**: Workflow module status remains compatible with the existing module system while real business behavior moves into workflow services.

### Execution Engine

- [ ] **WF-RUN-01**: Users can manually run a published workflow and inspect persisted run state after backend restart.
- [ ] **WF-RUN-02**: Workflow runner safely claims queued runs, executes steps in order, persists state transitions, and records structured errors.
- [ ] **WF-RUN-03**: Run detail exposes metadata, step timeline, events, redacted inputs/outputs, artifacts, retry, and cancellation controls.
- [ ] **WF-RUN-04**: Step retry, timeout, cancellation checks, and failure handling are enforced consistently.
- [ ] **WF-RUN-05**: MVP step types include `rag.query`, `agent.run`, `notify.in_app`, and a simple no-results skip condition.

### Scheduling and Operations

- [ ] **WF-SCHED-01**: Scheduled workflows support cron plus IANA timezone configuration and preview upcoming run times before publish.
- [ ] **WF-SCHED-02**: Scheduled run creation is idempotent and avoids duplicates across backend restart or multiple scheduler ticks.
- [ ] **WF-SCHED-03**: Scheduler supports misfire policy and concurrency policy for skipped, catch-up, or queue-after-current behavior.
- [ ] **WF-SCHED-04**: Operations Console highlights failed, running, disabled, and next-due workflow states without requiring the builder.

### Builder, Templates, and Validation

- [ ] **WF-BUILD-01**: The step registry exposes available step types, config schemas, input/output schemas, permissions, retry support, and cost hints to the frontend.
- [ ] **WF-BUILD-02**: Builder validates required trigger and step fields before publish and shows actionable per-step errors.
- [ ] **WF-BUILD-03**: Templates exist for Nightly RAG Summary, Connector Intake Triage, and Weekly Extraction Report.
- [ ] **WF-BUILD-04**: The first end-to-end template is Nightly RAG Summary with schedule, RAG query, no-results skip, agent summary, artifact, and notification behavior.

### Integrations

- [ ] **WF-INT-01**: Connector sync can be used as a workflow step and returns newly ingested records for downstream steps.
- [ ] **WF-INT-02**: Extract template execution can be used as a workflow step and saves outputs as workflow artifacts.
- [ ] **WF-INT-03**: Workflow artifacts support summary, JSON, extraction result, notification, and file-reference style outputs.

### Security, Governance, and Observability

- [ ] **WF-SEC-01**: Workflow lifecycle and run actions enforce workflow permissions and step-level permissions.
- [ ] **WF-SEC-02**: Workflow lifecycle changes, schedule changes, run requests, cancellations, retries, and approvals are audited.
- [ ] **WF-SEC-03**: Workflow and run budget caps prevent unbounded spend and attribute usage to workflow runs and steps where possible.
- [ ] **WF-SEC-04**: Sensitive fields, credentials, headers, and raw document content are redacted from logs and persisted previews.
- [ ] **WF-OBS-01**: Admin/operator views expose failed workflows, long-running workflows, scheduler lag, stale locks, failure rates, and top workflows by cost.

### Release Readiness

- [ ] **WF-TEST-01**: Backend tests cover validation, versioning, permissions, scheduling, idempotency, run state transitions, retries, budget caps, redaction, artifacts, and APIs.
- [ ] **WF-TEST-02**: Frontend tests cover route visibility, overview states, list filtering, run actions, builder validation, schedule preview, run timeline, and artifact preview.
- [ ] **WF-TEST-03**: End-to-end UAT covers Nightly RAG Summary, schedule preview, due run creation, failure/retry, disable behavior, and version history.
- [ ] **WF-REL-01**: Containers are rebuilt after app implementation changes and smoke checks confirm the latest workflow UI/API are running.

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
| WF-UX-01 | Phase 1 | Planned |
| WF-UX-02 | Phase 1 | Planned |
| WF-UX-03 | Phase 4 | Planned |
| WF-UX-04 | Phase 5 | Planned |
| WF-UX-05 | Phase 4 | Planned |
| WF-DATA-01 | Phase 2 | Planned |
| WF-DATA-02 | Phase 2 | Planned |
| WF-DATA-03 | Phase 2 | Planned |
| WF-DATA-04 | Phase 2 | Planned |
| WF-DATA-05 | Phase 1 | Planned |
| WF-RUN-01 | Phase 3 | Planned |
| WF-RUN-02 | Phase 3 | Planned |
| WF-RUN-03 | Phase 3 | Planned |
| WF-RUN-04 | Phase 3 | Planned |
| WF-RUN-05 | Phase 3 | Planned |
| WF-SCHED-01 | Phase 4 | Planned |
| WF-SCHED-02 | Phase 4 | Planned |
| WF-SCHED-03 | Phase 4 | Planned |
| WF-SCHED-04 | Phase 4 | Planned |
| WF-BUILD-01 | Phase 5 | Planned |
| WF-BUILD-02 | Phase 5 | Planned |
| WF-BUILD-03 | Phase 5 | Planned |
| WF-BUILD-04 | Phase 5 | Planned |
| WF-INT-01 | Phase 6 | Planned |
| WF-INT-02 | Phase 6 | Planned |
| WF-INT-03 | Phase 6 | Planned |
| WF-SEC-01 | Phase 2 | Planned |
| WF-SEC-02 | Phase 2 | Planned |
| WF-SEC-03 | Phase 3 | Planned |
| WF-SEC-04 | Phase 3 | Planned |
| WF-OBS-01 | Phase 8 | Planned |
| WF-TEST-01 | Phase 8 | Planned |
| WF-TEST-02 | Phase 8 | Planned |
| WF-TEST-03 | Phase 8 | Planned |
| WF-REL-01 | Phase 8 | Planned |

---
*Requirements created: 2026-07-05 from `.planning/WORKFLOWS_IMPLEMENTATION_PLAN.md`*
