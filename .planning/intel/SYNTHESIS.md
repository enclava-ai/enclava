# Ingest Synthesis: Workflow Automation

**Synthesized:** 2026-07-05
**Mode:** merge-into-existing-planning
**Docs ingested:** 1

## Summary

`.planning/WORKFLOWS_IMPLEMENTATION_PLAN.md` defines a complete product and engineering milestone for implementing Enclava workflows. The plan fits the current project state because v1.0 has shipped, the root roadmap was awaiting the next milestone, and the existing codebase already contains a thin workflow module stub that can become the adapter for a real workflow service.

The milestone should implement workflows as a durable automation layer around platform modules. Agents remain reasoning/action workers. Workflows own orchestration concerns: schedule state, run state, retries, artifacts, permissions, audit, cost controls, and operational visibility.

## Scope To Carry Forward

- A new `Workflows` product surface in the app navigation.
- Operations Console as the default workflow UX.
- Step Builder as the workflow authoring/editing mode.
- Schedule Board as the recurring automation view.
- Dedicated workflow backend services, models, migrations, and internal APIs.
- Manual and scheduled workflow triggers.
- Typed linear steps for the first implementation.
- MVP steps for RAG query, agent run, in-app notification, and simple no-results skip logic.
- Run history, run detail, timeline events, artifacts, retries, cancellation, and redacted IO.
- Timezone-aware scheduling with preview, idempotency, locking, and misfire policy.
- Permissions, audit hooks, budget caps, usage attribution, and secret redaction.
- Connector and Extract steps after the core engine is working.
- Advanced control flow, approvals, API/event triggers, and hardening after MVP.

## Requirements Created

Requirements are grouped into:

- Product model and UX.
- Definition lifecycle and persistence.
- Execution engine.
- Scheduling and operations.
- Builder and templates.
- Step integrations.
- Security, governance, and observability.
- Testing and release readiness.

## Phase Strategy

The roadmap converts the implementation plan into eight executable GSD phases:

1. Product Contract and Scaffold.
2. Persistence, API, Permissions, and Audit.
3. Manual Execution Engine.
4. Scheduler and Operations Console.
5. Builder, Templates, and Validation.
6. Connector and Extract Integration.
7. Advanced Control Flow and Triggers.
8. Hardening, Observability, and Release.

The first end-to-end user outcome is Nightly RAG Summary because it proves scheduling, checkpointing, agent/RAG execution, artifacts, budget controls, and operations visibility.

## Conflict Outcome

No blockers were detected. No warnings were detected. The ingest updates the root planning files from "awaiting next milestone" to active milestone v1.1 Workflow Automation.
