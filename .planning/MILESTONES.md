# Milestones

## v1.1 Workflow Automation (Active: 2026-07-05)

**Source:** `.planning/WORKFLOWS_IMPLEMENTATION_PLAN.md`
**Phases planned:** 8 phases, 22 plans

**Primary goals:**

- Turn workflows into a durable automation layer around Enclava modules and agents.
- Add Operations Console, Step Builder, and Schedule Board workflow UX.
- Persist workflow definitions, versions, triggers, runs, step runs, artifacts, and events.
- Add manual execution, scheduled execution, run detail, retries, cancellation, budget caps, audit, and redaction.
- Prove Nightly RAG Summary as the first end-to-end workflow.
- Integrate connector sync and Extract template execution as workflow steps.
- Add advanced controls only after the core engine is proven.
- Harden with observability, tests, docs, container rebuilds, and smoke checks.

**Status:** Active. Start with `$gsd-discuss-phase 1`.

## v1.0 Frontend UX Overhaul (Shipped: 2026-07-01)

**Phases completed:** 7 phases, 20 plans, 32 tasks

**Key accomplishments:**

- Deprecated App Router pages and sole-use frontend RAG debug proxies were removed without touching active routes or backend functionality.
- Deprecated route references were absent from active frontend source, and lint/build passed after route deletion.
- Slate Mono theme tokens and alpha-capable status mappings are now available to downstream UI work.
- Reusable status, confirmation, header, empty-state, and skeleton primitives are now available for downstream UX phases.
- The design-system foundation passes source, lint, and production build checks; the standalone TypeScript config deprecation issue remains unrelated.
- The authenticated app now renders through a responsive shell with a desktop sidebar, mobile drawer, and shared navigation model.
- The LLM interface now lives under Settings, with compatibility redirects preserving old route behavior.
- The app shell and LLM IA changes have passed source, lint, and build verification.
- Admin, audit, pricing, user, connector, usage, and API-key stats surfaces now use semantic color tokens instead of legacy palette classes.
- RAG and Extract surfaces now use semantic color tokens for status, dropzones, skeletons, and destructive actions.
- The dashboard now follows the new trust, spend, requests, reliability, attention, and connect information architecture, and owned settings/playground files are color-clean.
- Agents, LLM, connectors, plugins, auth, public, chat, and shared UI scoped surfaces are now free of legacy and raw palette color utilities.
- Legacy Empire/Enclava palette compatibility is removed, and the frontend now has a repeatable hardcoded-color guardrail.
- Internal product navigation no longer uses full-page browser redirects in the scoped Phase 5 navigation paths.
- Real client-component JSON calls in the planned surfaces now use `apiClient`, and the frontend has a plumbing guardrail for future regressions.
- The frontend now uses one shared toast system, and third-party toast providers/dependencies are removed.
- Native destructive confirmations now use themed confirmation flows instead of browser dialogs.
- Major page-level loading states now use shared skeleton primitives, while inline busy states keep compact spinners.
- High-traffic zero states now use `EmptyState` with clearer copy and primary actions.
- Targeted icon-only controls and toast feedback now have accessible names and live-region semantics.

**Known deferred items:**

- TypeScript 6 config modernization for `target=ES5` and `baseUrl`.
- Authenticated runtime keyboard/screen-reader checks once credentials or E2E fixtures exist.
- Visual regression screenshot coverage for high-traffic routes.
- Reliable dashboard spend source wiring.

---
