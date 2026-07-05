# Ingest Context: Workflow Automation

Source: `.planning/WORKFLOWS_IMPLEMENTATION_PLAN.md`
Ingested: 2026-07-05

## Product Context

Enclava currently has a frontend UX foundation from v1.0 and a backend workflow module stub. The next milestone should turn workflows into a product capability for confidential AI automation.

The key distinction is:

- Agents are configured AI workers with model, tools, knowledge, and behavior.
- Workflows are durable orchestration definitions with triggers, steps, policies, run state, audit, and artifacts.

The core user examples are:

- Every night at 2am, summarize new RAG data.
- Sync connector intake, triage new items, and notify the owner.
- Run a weekly extraction report over selected documents.
- Generate an admin operations digest.
- Later, pause for human approval before sensitive actions.

## Current Codebase Fit

Current known implementation surface:

- `backend/app/modules/workflow/main.py` is a stub module with in-memory counters and echo-style execution.
- `backend/app/modules/workflow/module.yaml` advertises workflow capabilities and permissions.
- `backend/app/modules/factory.py` wires the workflow module after RAG and Agent.
- `frontend/src/components/ui/navigation.tsx` maps module navigation for RAG and Extract, but not Workflows.

The milestone should keep the module as an adapter, move real behavior into workflow services, and add a dedicated authenticated internal API under `/api-internal/v1/workflows`.

## UX Direction

The workflow product should combine the sketch variants:

- Default: Operations Console.
- Edit mode: Step Builder.
- Secondary view: Schedule Board.

The first screen should answer "what is running, what failed, and what runs next." Authoring should use a typed linear step list before any canvas or DAG experience.

## First Vertical Slice

Nightly RAG Summary is the recommended first user-visible slice:

1. Scheduled trigger at 02:00 in a selected timezone.
2. Query documents added since the last successful run.
3. Skip cleanly if there is no new data.
4. Run an agent or summarizer.
5. Save a summary artifact.
6. Notify configured users or expose the artifact in run detail.

This slice proves the core workflow value without requiring advanced branching, webhooks, or approvals.
