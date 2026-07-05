# Roadmap: Enclava Workflow Automation

## Overview

This milestone turns Enclava workflows from a module stub and product concept into a governed automation feature. It starts by locking the product contract and scaffold, then builds persisted workflow definitions, manual execution, scheduling, operations UX, builder UX, platform integrations, advanced controls, and production hardening.

The first vertical slice is Nightly RAG Summary: a scheduled workflow that finds new RAG data, skips cleanly when no data changed, invokes an agent or summarizer, stores an artifact, and exposes run history.

## Milestones

- **v1.0 Frontend UX Overhaul** - Phases 1-7, shipped 2026-07-01. Full archive: `.planning/milestones/v1.0-ROADMAP.md`.
- **v1.1 Workflow Automation** - Phases 1-8, active, created 2026-07-05 from `.planning/WORKFLOWS_IMPLEMENTATION_PLAN.md`.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work.
- Decimal phases (2.1, 2.2): Urgent insertions if needed.

- [x] **Phase 1: Product Contract and Scaffold** - Lock MVP boundaries, schemas, module adapter direction, step registry shell, and template seeds. (completed 2026-07-05)
- [ ] **Phase 2: Persistence, API, Permissions, and Audit** - Add durable workflow data model, lifecycle service, internal APIs, permissions, and audit hooks.
- [ ] **Phase 3: Manual Execution Engine** - Implement persisted manual runs, ordered step execution, MVP step types, run detail, artifacts, retries, cancellation, budget checks, and redaction.
- [ ] **Phase 4: Scheduler and Operations Console** - Add timezone-aware scheduling, due-run creation, idempotency, misfire/concurrency policy, operations console, schedule board, and health states.
- [ ] **Phase 5: Builder, Templates, and Validation** - Build the typed step builder, step catalog forms, schedule preview validation, templates, draft/publish flow, and Nightly RAG Summary template.
- [ ] **Phase 6: Connector and Extract Integration** - Add connector sync and Extract template step types with artifact handling and module-specific run summaries.
- [ ] **Phase 7: Advanced Control Flow and Triggers** - Add only proven advanced controls: branches, approvals, pause/resume, and API/event trigger foundations.
- [ ] **Phase 8: Hardening, Observability, and Release** - Add recovery, scale, retention, admin metrics, E2E/UAT coverage, docs, container rebuilds, and release smoke checks.

## Phase Details

### Phase 1: Product Contract and Scaffold

**Goal**: Convert the workflow plan into implementation contracts without changing shipped behavior.
**Depends on**: Nothing (first phase)
**Requirements**: [WF-UX-01, WF-UX-02, WF-DATA-05]
**Success Criteria** (what must be TRUE):

  1. MVP and deferred boundaries are explicit in code-facing schemas and docs.
  2. Workflow definition Pydantic schemas validate representative samples.
  3. Step registry and workflow service interfaces exist without changing existing module smoke behavior.
  4. First templates are defined as data contracts for Nightly RAG Summary, Connector Intake Triage, and Weekly Extraction Report.

**Plans**: 2 plans
Plans:
**Wave 1**

- [ ] 01-01: Add workflow domain schemas, runtime policy types, state enums, and sample definitions.

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 01-02: Add service interfaces, step registry shell, template seeds, and module adapter integration points.

### Phase 2: Persistence, API, Permissions, and Audit

**Goal**: Users can create, edit, publish, enable, disable, archive, and list workflow definitions with durable storage.
**Depends on**: Phase 1
**Requirements**: [WF-DATA-01, WF-DATA-02, WF-DATA-03, WF-DATA-04, WF-SEC-01, WF-SEC-02]
**Success Criteria** (what must be TRUE):

  1. Alembic migrations add workflow definitions, versions, triggers, runs, step runs, artifacts, and events.
  2. Workflow service supports CRUD, validation, publish, enable, disable, archive, and list/detail queries.
  3. Dedicated internal workflow APIs enforce authenticated user context and permissions.
  4. Lifecycle actions write audit records.

**Plans**: 3 plans
Plans:
**Wave 1**

- [ ] 02-01: Add workflow persistence models and migration.

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 02-02: Implement workflow lifecycle service, validation, publish/version semantics, and permission checks.

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 02-03: Add internal workflow API router and lifecycle audit hooks.

### Phase 3: Manual Execution Engine

**Goal**: Users can manually run a published workflow and inspect the persisted run.
**Depends on**: Phase 2
**Requirements**: [WF-RUN-01, WF-RUN-02, WF-RUN-03, WF-RUN-04, WF-RUN-05, WF-SEC-03, WF-SEC-04]
**Success Criteria** (what must be TRUE):

  1. Manual run creation produces queued/running/succeeded/failed workflow run records.
  2. Runner claims runs safely, executes ordered steps, persists step state, and survives backend restart with persisted history.
  3. MVP steps for RAG query, agent run, in-app notification, and no-results skip are implemented.
  4. Run detail exposes timeline, events, artifacts, redacted IO, retry, cancellation, duration, errors, and budget use.

**Plans**: 3 plans
Plans:
**Wave 1**

- [ ] 03-01: Implement run creation, runner claim loop, state transitions, and event/artifact persistence.

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 03-02: Implement MVP step handlers for RAG query, agent run, notification, and no-results skip.

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 03-03: Add run detail APIs, retry/cancel behavior, budget checks, redaction, and frontend run timeline.

### Phase 4: Scheduler and Operations Console

**Goal**: Scheduled workflows run reliably, and users can operate workflows from a health-first console.
**Depends on**: Phase 3
**Requirements**: [WF-UX-03, WF-UX-05, WF-SCHED-01, WF-SCHED-02, WF-SCHED-03, WF-SCHED-04]
**Success Criteria** (what must be TRUE):

  1. Cron plus IANA timezone schedules preview next run times before publish.
  2. Scheduler creates due runs once per trigger fire time using locks and idempotency keys.
  3. Misfire and concurrency policy are persisted and enforced.
  4. Workflows route exposes operations console, workflow list, health states, next run, last run, failures, and schedule board.

**Plans**: 3 plans
Plans:
**Wave 1**

- [ ] 04-01: Implement scheduler service, schedule preview, due-run polling, idempotency, locks, and misfire policy.

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 04-02: Build Workflows route, navigation entry, operations console, workflow list, and health summaries.

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 04-03: Add schedule board, upcoming runs, disable/enable flows, and schedule health states.

### Phase 5: Builder, Templates, and Validation

**Goal**: Users can author the common workflows without editing JSON.
**Depends on**: Phase 4
**Requirements**: [WF-UX-04, WF-BUILD-01, WF-BUILD-02, WF-BUILD-03, WF-BUILD-04]
**Success Criteria** (what must be TRUE):

  1. Step catalog API exposes schemas, labels, permissions, retry support, and cost hints.
  2. Builder supports trigger configuration, ordered typed steps, properties panel, validation summary, save draft, publish, enable, and run test where safe.
  3. Nightly RAG Summary can be created from template and manually/scheduled run end to end.
  4. Connector Intake Triage and Weekly Extraction Report templates exist even if later integration steps are disabled until Phase 6.

**Plans**: 3 plans
Plans:
**Wave 1**

- [ ] 05-01: Expose step catalog schemas and validation endpoints.

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 05-02: Build Step Builder UI, trigger forms, step forms, validation summary, draft save, publish, and enable flows.

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 05-03: Add templates and complete Nightly RAG Summary authoring and test path.

### Phase 6: Connector and Extract Integration

**Goal**: Workflows coordinate existing platform modules beyond RAG and Agent.
**Depends on**: Phase 5
**Requirements**: [WF-INT-01, WF-INT-02, WF-INT-03]
**Success Criteria** (what must be TRUE):

  1. Connector sync can run as a workflow step and returns newly ingested records to downstream steps.
  2. Extract template execution can run as a workflow step and stores output as artifacts.
  3. Connector Intake Triage and Weekly Extraction Report run end to end.
  4. Module-specific step failures appear in run detail with actionable errors.

**Plans**: 2 plans
Plans:
**Wave 1**

- [ ] 06-01: Add connector sync step type, UI config, errors, and artifact outputs.

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 06-02: Add Extract template step type, UI config, artifact views, and weekly report workflow.

### Phase 7: Advanced Control Flow and Triggers

**Goal**: Add only the advanced workflow behavior proven necessary by real use cases.
**Depends on**: Phase 6
**Requirements**: [WF-UX-01, WF-RUN-03, WF-SEC-01, WF-SEC-02]
**Success Criteria** (what must be TRUE):

  1. Minimal conditional branching works without introducing a full canvas engine.
  2. Approval requests can pause and resume runs with authorized approval or rejection.
  3. Approval actions are audited and visible in run detail.
  4. API/event trigger foundations exist only with clear auth and idempotency semantics.

**Plans**: 3 plans
Plans:
**Wave 1**

- [ ] 07-01: Add minimal branch semantics and readable branch UI.

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 07-02: Add approval request step, pause/resume run state, approval permissions, and audit.

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 07-03: Add API/event trigger foundations with auth, idempotency, and docs surface.

### Phase 8: Hardening, Observability, and Release

**Goal**: Make workflows dependable enough for production use.
**Depends on**: Phase 7
**Requirements**: [WF-OBS-01, WF-TEST-01, WF-TEST-02, WF-TEST-03, WF-REL-01]
**Success Criteria** (what must be TRUE):

  1. Tests cover backend validation, state transitions, scheduling, idempotency, permissions, budget caps, redaction, APIs, and frontend workflow states.
  2. E2E/UAT covers Nightly RAG Summary, schedule preview, due run creation, failures/retries, disabling, and version history.
  3. Admin/operator metrics expose scheduler lag, stale locks, failure rate, long-running workflows, and top workflows by cost.
  4. Containers are rebuilt after app changes and smoke checks prove the latest version is running.

**Plans**: 3 plans
Plans:
**Wave 1**

- [ ] 08-01: Add recovery, stale-lock handling, retention policy, admin metrics, and operational docs.

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 08-02: Add backend, frontend, and E2E/UAT coverage for workflow release criteria.

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 08-03: Rebuild containers, run release smoke checks, close docs, and prepare milestone completion.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Product Contract and Scaffold | 2/2 | Complete | 2026-07-05 |
| 2. Persistence, API, Permissions, and Audit | 0/3 | Planned | - |
| 3. Manual Execution Engine | 0/3 | Planned | - |
| 4. Scheduler and Operations Console | 0/3 | Planned | - |
| 5. Builder, Templates, and Validation | 0/3 | Planned | - |
| 6. Connector and Extract Integration | 0/2 | Planned | - |
| 7. Advanced Control Flow and Triggers | 0/3 | Planned | - |
| 8. Hardening, Observability, and Release | 0/3 | Planned | - |

## Archives

- `.planning/milestones/v1.0-ROADMAP.md`
- `.planning/milestones/v1.0-REQUIREMENTS.md`
- `.planning/milestones/v1.0-MILESTONE-AUDIT.md`
- `.planning/milestones/v1.0-phases/`

---
*Roadmap created: 2026-07-05 from `.planning/WORKFLOWS_IMPLEMENTATION_PLAN.md`*
