# Phase 4 Context: Scheduler and Operations Console

## Current State

- Phase 3 added durable manual workflow runs, step execution, retry, cancellation, redaction, budget counters, internal run APIs, and a direct-linked run detail page.
- Workflow triggers already persist `trigger_type`, `cron_expression`, `timezone`, `misfire_policy`, `enabled`, `next_run_at`, and `last_fire_at`.
- Workflow runtime already supports queued run creation, claiming, execution, events, artifacts, and detail serialization.
- FastAPI lifespan already starts and stops an asyncio connector scheduler in `backend/app/tasks/connector_sync.py`; Phase 4 should reuse this lightweight pattern.
- Frontend navigation exposes module-backed routes through `MODULE_NAV_MAP` in `frontend/src/components/ui/navigation.tsx`; `workflow` is not mapped yet.

## Phase 4 Goal

Scheduled workflows run reliably, and users can operate workflows from a health-first console.

## Design Direction

- Keep Postgres as the source of truth for scheduler state.
- Use a lightweight in-process scheduler/worker loop first; do not introduce Celery/Temporal/Airflow-style infrastructure in this phase.
- Split backend scheduling from frontend operations UX:
  - 04-01: scheduler, preview, due-run creation, idempotency, worker loop, backend APIs.
  - 04-02: Workflows route, navigation entry, overview operations console, health summaries.
  - 04-03: schedule board, upcoming runs, enable/disable controls, schedule health states.
- Add `croniter` for cron calculation rather than hand-rolling cron semantics.

## Key Requirements

- WF-UX-03: Workflows route opens on an Operations Console showing active workflows, failures, latest run, next run, owner, health, and actions.
- WF-UX-05: Schedule management exposes upcoming runs, missed/failed schedule health, and next-run previews.
- WF-SCHED-01: Scheduled workflows support cron plus IANA timezone configuration and preview upcoming run times before publish.
- WF-SCHED-02: Scheduled run creation is idempotent and avoids duplicates across restart or multiple scheduler ticks.
- WF-SCHED-03: Scheduler supports misfire and concurrency policy.
- WF-SCHED-04: Operations Console highlights failed, running, disabled, and next-due workflow states without requiring the builder.

## Constraints

- Existing workflow module smoke behavior must continue passing.
- Existing direct-linked run detail page must remain valid.
- No primary Workflows navigation entry should appear until `/workflows` exists in 04-02.
- Rebuild containers after implementation changes and verify the latest stack is running.

## Deferred Beyond Phase 4

- Step builder/property editor remains Phase 5.
- Connector and Extract workflow step types remain Phase 6.
- Branches, approvals, external API/event triggers, and distributed worker pools remain later phases.

---
*Created: 2026-07-05*
