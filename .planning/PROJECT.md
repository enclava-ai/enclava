# Enclava

## What This Is

Enclava is a confidential AI platform with a FastAPI backend, Next.js frontend, dynamic modules, RAG, LLM provider orchestration, plugin support, connectors, usage tracking, admin controls, and a polished enterprise frontend foundation. The next milestone turns workflows into a first-class automation capability for scheduled and manual confidential AI operations.

## Core Value

Users can run confidential AI automations that are scheduled, auditable, observable, budget-aware, and clear to operate.

## Current State

**Shipped milestone:** v1.0 Frontend UX Overhaul, completed 2026-07-01.

**Active milestone:** v1.1 Workflow Automation, created 2026-07-05 from `.planning/WORKFLOWS_IMPLEMENTATION_PLAN.md`.

**Delivered in v1.0:**
- Deprecated frontend routes and sole-use proxies were removed.
- Slate Mono semantic tokens, status roles, and shared primitives are available.
- The authenticated app uses a desktop sidebar and mobile drawer from one nav model.
- LLM configuration lives under `/settings/llm`, with `/llm` compatibility redirects.
- Frontend color usage was migrated away from legacy palettes and raw UI color utilities.
- Dashboard IA now emphasizes trust, spend, requests, reliability, attention, connection, and module health.
- Internal browser navigation and planned real client JSON calls use project-native router/API paths.
- Toast and confirmation flows are consolidated around project primitives.
- Major loading and empty states use shared skeleton and `EmptyState` primitives.
- Accessibility labels, live-region feedback, and frontend UX guardrail documentation are in place.

**Current workflow baseline:**
- `backend/app/modules/workflow/main.py` exists as a module stub with basic status and echo-style execute behavior.
- Workflow module metadata and permissions exist, but there is no real workflow engine, persistence, scheduling, dedicated UI route, or production run API yet.
- Workflow UX sketches and a full implementation plan exist under `.planning/`.

**Archive references:**
- `.planning/milestones/v1.0-ROADMAP.md`
- `.planning/milestones/v1.0-REQUIREMENTS.md`
- `.planning/milestones/v1.0-MILESTONE-AUDIT.md`

## Active Milestone Goals

v1.1 Workflow Automation should deliver workflows as a governed automation layer around existing Enclava capabilities.

Primary goals:

- Add a Workflows product route with Operations Console as the default view.
- Add durable workflow definitions, versions, triggers, runs, step runs, artifacts, and events.
- Add dedicated authenticated internal workflow APIs.
- Add manual workflow execution and persisted run detail.
- Add timezone-aware scheduling with preview, idempotency, misfire policy, and concurrency policy.
- Add typed workflow builder, step catalog, validation, and templates.
- Prove the first end-to-end use case: Nightly RAG Summary.
- Add connector and Extract workflow steps after the core engine is reliable.
- Add advanced controls only after core use cases justify them.
- Harden with tests, observability, recovery, docs, container rebuild, and smoke checks.

## Requirements

### Validated

- v1.0: Deprecated frontend routes and references are removed before UX sweeps touch dead code.
- v1.0: Slate Mono semantic tokens and shared primitives work in both themes.
- v1.0: Top navigation is replaced by an authoritative sidebar/mobile drawer shell.
- v1.0: LLM configuration lives under Settings with query-preserving compatibility redirects.
- v1.0: Legacy `empire-*`/`enclava-*` styling and covered raw UI palette utilities are removed from `frontend/src`.
- v1.0: Dashboard IA is reworked around trust, spend, request volume, reliability, attention items, and developer connection details.
- v1.0: Internal full-page navigation and raw client fetches in planned surfaces use project-native routing and `apiClient`.
- v1.0: Toasts are consolidated and native confirmation/alert flows are replaced.
- v1.0: Major full-page spinners and weak empty states are replaced with designed alternatives.
- v1.0: Accessibility labels, async feedback semantics, and guardrails against UX regressions are documented and verified.

### Active

See `.planning/REQUIREMENTS.md` for v1.1 requirements.

Primary active requirement groups:

- Product model and UX.
- Definition lifecycle and persistence.
- Execution engine.
- Scheduling and operations.
- Builder and templates.
- Connector and Extract integrations.
- Security, governance, observability, and release readiness.

### Out of Scope

- Building a general-purpose Airflow, Temporal, Zapier, or n8n replacement.
- Making a freeform workflow canvas part of the first useful workflow release.
- Arbitrary user code execution.
- Raw secret storage inside workflow definitions.
- Nested workflows, loops, human approvals, external webhooks, and broad API/event triggers before the core engine is proven.
- Replacing Tailwind, Radix, shadcn-style primitives, or the existing v1.0 frontend foundation.

## Context

The frontend now has a stronger foundation for future work: semantic Tailwind tokens, shared status/confirmation/header/empty/skeleton primitives, one shell navigation model, one toast path, themed confirmation flows, `apiClient` enforcement for planned client calls, and scripts for color/plumbing guardrails.

Known deferred items from v1.0:
- Standalone `npx tsc --noEmit` fails on TypeScript 6 deprecation diagnostics for `target=ES5` and `baseUrl`.
- Authenticated runtime keyboard and screen-reader checks need credentials or E2E fixtures.
- Visual regression coverage needs a screenshot harness.
- Dashboard spend still needs a reliable frontend cost source.

Workflow context:
- Workflows should be the orchestration and governance unit.
- Agents should remain reasoning/action workers.
- The first vertical slice should be Nightly RAG Summary.
- Production workflow behavior should not depend on the generic module execute endpoint.

## Constraints

- **Stack:** Continue using FastAPI, SQLAlchemy/Alembic, Postgres, Next.js App Router, React, Tailwind, Radix/shadcn-style primitives, lucide-react, and existing project utilities.
- **Theme system:** Preserve the `hsl(var(--x) / <alpha-value>)` Tailwind token pattern.
- **Routing:** Keep the existing nav model authoritative unless a future milestone explicitly changes IA.
- **Frontend UX:** Use shared primitives and guardrails documented in `CLAUDE.md`.
- **Workflow storage:** Persist workflow state in Postgres; in-memory state is not sufficient for production runs.
- **Scheduling:** Store run timestamps in UTC and trigger timezones as IANA strings.
- **Security:** Do not support arbitrary user code or raw secret storage in workflow definitions.
- **Verification:** Frontend UX changes should run `npm run check:colors`, `npm run check:plumbing`, `npm run lint`, and `npm run build` from `frontend/`.
- **Containers:** Rebuild containers and smoke-check the running version after app implementation changes.
- **Safety:** Do not read or commit `.env` secret values; do not revert unrelated dirty worktree changes.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use Slate Mono as the UX palette | It keeps the cyan identity while reducing the cyberpunk/neon feel. | Good - shipped in v1.0 |
| Treat the mock as visual-only | The mock's nav grouping and mobile behavior were intentionally not authoritative. | Good - avoided scope drift |
| Move LLM under Settings | LLM configuration is a settings concern and already has provider children beneath settings. | Good - shipped with redirects |
| Split status into solid and soft token pairs | Solid fills need AA text contrast; badges need subtle theme-aware tints. | Good - used by shared status UI |
| Use `StatusBadge` for severity and neutral `Badge` for categories | Status and category semantics should not be conflated. | Good - documented for future work |
| Use `apiClient` for client calls | Centralized auth/error behavior prevents drift. | Good - guardrail-backed |
| Add grep/script guardrails | The cleanup should fail fast if legacy patterns return. | Good - `check:colors` and `check:plumbing` pass |
| Keep spinners for inline busy states only | Page-level loads need structure, but action-level loading benefits from compact busy affordances. | Good - applied in Phase 7 |
| Use themed confirmations instead of native dialogs | Destructive actions need brand-consistent, accessible, consequence-aware confirmation. | Good - guardrail-backed |
| Workflows orchestrate; agents execute | Scheduling, retries, checkpoints, artifacts, budget, and audit are workflow concerns. | Active - v1.1 |
| Default Workflows UX is Operations Console | Operators need status, failures, last run, and next run before authoring tools. | Active - v1.1 |
| Step Builder starts linear and typed | Typed ordered steps cover the core use cases without a clunky canvas. | Active - v1.1 |
| Workflow production APIs are dedicated internal APIs | Generic module execute lacks real user context, schedule state, run state, and audit semantics. | Active - v1.1 |
| Postgres is workflow source of truth | Scheduled and long-running automations must survive process restarts. | Active - v1.1 |
| Start with in-process scheduler/runner | It keeps operational complexity lower while durable state lives in Postgres. | Active - v1.1 |
| Recover stale workflow locks conservatively | Current runtime cannot safely resume arbitrary partially completed side-effecting steps. | Active - stale locks fail the run and require normal retry |
| Retain durable workflow history indefinitely | Definitions, versions, runs, step runs, approvals, and audit logs are the production record. | Active - retention only prunes verbose events and artifact payloads |
| Keep admin metrics in Operations Console | Operators need lag, stale lock, failure, duration, and cost signals without a separate dashboard. | Active - metrics load only for workflow managers |
| Use frontend workflow surface guard for v1.1 release coverage | The repo does not yet have a component or browser test harness, so a no-dependency source wiring guard gives runnable release coverage without adding brittle late-milestone infrastructure. | Active - future component/browser tests remain deferred |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each milestone:**
1. Move shipped requirements to Validated.
2. Update Current State and deferred items.
3. Review decisions and mark outcomes.
4. Define the next Active requirements when a new milestone starts.

---
*Last updated: 2026-07-06 after completing Phase 8 Plan 08-02*
