# Classification: Workflows Implementation Plan

Source: `.planning/WORKFLOWS_IMPLEMENTATION_PLAN.md`
Type: SPEC
Precedence: SPEC
Classified: 2026-07-05

## Summary

The document defines a full implementation strategy for Enclava workflows as a governed automation layer around existing platform capabilities. It distinguishes workflows from agents, defines UX direction, backend architecture, data models, APIs, step types, security boundaries, testing strategy, rollout risks, and phased execution.

## Extracted Requirements

- Workflows must support manual and scheduled runs.
- Workflows must be durable, persisted, auditable, permissioned, and budget-aware.
- Agents must remain executable steps inside workflows rather than becoming the orchestration layer.
- The default workflow UX must prioritize operations visibility before authoring complexity.
- The builder must use a typed linear step list in the first release, not a freeform canvas.
- Workflow runs must expose run history, step timeline, logs/events, artifacts, retry, cancellation, and redacted inputs/outputs.
- Scheduling must be timezone-aware, previewable, idempotent, and resistant to duplicate due-run creation.
- Workflow APIs must be dedicated authenticated internal APIs rather than relying on the generic module execute endpoint.
- Workflow implementation must preserve security boundaries by avoiding arbitrary code execution and raw secret storage.

## Extracted Phase Strategy

- Product contract and scaffold.
- Persistence, CRUD, permissions, and audit.
- Manual execution engine.
- Scheduler and operations console.
- Builder, templates, and validation.
- Connector and Extract integration.
- Advanced control flow and triggers.
- Hardening, observability, and release readiness.

## Conflict Notes

No contradictions found against the existing shipped v1.0 frontend UX milestone. The existing project state explicitly awaited the next milestone, so this source can seed v1.1.
