# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 - Frontend UX Overhaul

**Shipped:** 2026-07-01  
**Phases:** 7 | **Plans:** 20 | **Sessions:** 1

### What Was Built

- Removed deprecated frontend routes, sole-use proxies, and obsolete references before sweeping active UI.
- Added Slate Mono semantic tokens, status roles, and shared primitives for status, confirmation, headers, empty states, and skeletons.
- Replaced the top-nav shell with a responsive sidebar/mobile drawer and moved LLM configuration under Settings.
- Migrated scoped frontend surfaces away from legacy/raw color utilities and added `check:colors`.
- Reworked dashboard IA and centralized planned client calls through `apiClient` with `check:plumbing`.
- Consolidated toast and confirmation flows, replaced native dialogs, and added final loading, empty-state, and accessibility polish.

### What Worked

- Deleting dead routes first kept later color and plumbing sweeps focused on active code.
- Shared primitives landed before broad consumer edits, which reduced repeated design decisions.
- Script guardrails made regression checks cheap and repeatable across the later phases.
- Phase-level review documents kept deferred runtime limitations explicit instead of blocking source-verifiable progress.

### What Was Inefficient

- `npx tsc --noEmit` stayed blocked throughout the milestone by TypeScript 6 config deprecations, reducing type-check signal.
- Authenticated runtime and visual checks could not be executed without credentials, fixtures, or a screenshot harness.
- Some planning artifacts used mixed metadata depth, so milestone audit relied more on verification reports than summary frontmatter.

### Patterns Established

- Use semantic Tailwind roles and project status tokens instead of raw color utilities.
- Use `StatusBadge` for severity/state and neutral `Badge` variants for categories.
- Use shared skeleton primitives for initial page/list loading and keep spinners for inline busy states.
- Use `EmptyState` for high-traffic zero states with outcome copy and a primary action.
- Use project `useToast`, `useConfirm`, `apiClient`, `check:colors`, and `check:plumbing` for frontend UX work.

### Key Lessons

1. Put guardrails near the work that created the risk; color and plumbing scripts paid off immediately in later phases.
2. Treat source-verifiable accessibility improvements and browser runtime checks as separate gates when credentials are unavailable.
3. Archive phase history at milestone close so active planning files stay small enough for fast future context loading.

### Cost Observations

- Model mix: not measured.
- Sessions: 1.
- Notable: Plan-sized commits made review and rollback boundaries clear despite a large frontend sweep.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | 1 | 7 | Established a full frontend UX overhaul loop with planning, per-phase verification, guardrails, audit, and archive. |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | lint, build, source scans, guardrail scripts | Source/build verified; runtime auth checks deferred | 2 guardrail scripts |

### Top Lessons

1. Frontend-wide UX changes need executable guardrails, not just documentation.
2. Milestone completion should archive requirements and roadmap detail while keeping deferred technical debt visible.
