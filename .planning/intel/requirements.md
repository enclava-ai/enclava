# Ingest Requirements: Workflow Automation

Source: `.planning/WORKFLOWS_IMPLEMENTATION_PLAN.md`
Ingested: 2026-07-05

## Requirements

- Workflows must expose a navigable product route when the module is enabled.
- Workflow UX must default to operations visibility and include run status, last run, next run, failures, and primary actions.
- Workflow builder must support trigger configuration, ordered typed steps, validation, save draft, publish, enable, and test/run actions.
- Workflow definitions must be versioned so historical runs remain tied to immutable published versions.
- Workflow data must persist in Postgres with migrations and SQLAlchemy models.
- Workflow services must support CRUD, validation, publish, enable, disable, archive, manual run creation, run query, events, and artifacts.
- Workflow runner must claim queued runs safely, execute steps, persist state transitions, enforce retries/timeouts/cancellation checks, and redact sensitive IO.
- Workflow scheduler must create due runs from cron/timezone triggers without duplicates and recover after restart according to misfire policy.
- Workflow step registry must expose step schemas to the UI and validate step config before publish.
- MVP step types must include RAG query, agent run, in-app notification, and no-results skip behavior.
- Later step types must include connector sync, Extract template execution, artifacts, approvals, webhooks, API triggers, and nested workflows only when safety requirements are met.
- Workflow actions must enforce permissions, audit lifecycle/run actions, respect budget caps, and attribute usage to workflow runs and steps where possible.
- Workflow tests must cover validation, state transitions, scheduling, idempotency, retries, permissions, budget caps, redaction, API behavior, frontend states, and end-to-end user flows.
