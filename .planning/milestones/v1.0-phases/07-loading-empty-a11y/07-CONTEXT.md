# Phase 7: Loading, Empty, and Accessibility Polish - Context

**Gathered:** 2026-07-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Perform the final UX polish pass after the main systems have landed: replace major full-page spinners, improve high-traffic empty states, run accessibility checks, and document conventions so the cleanup holds.

</domain>

<decisions>
## Implementation Decisions

### Loading states
- **D-01:** Replace full-page initial-load spinners with structure-preserving skeletons where the final layout shape is known.
- **D-02:** Keep spinners only for inline busy states such as button submissions and small refresh indicators.
- **D-03:** Spinner colors, where still used, must use semantic tokens.

### Empty states
- **D-04:** Target RAG, Agents, API keys, Connectors, Budgets, and other high-traffic zero states.
- **D-05:** Empty states should explain value, provide a primary action, and optionally link to docs.
- **D-06:** Copy should be active and user-oriented.

### Accessibility
- **D-07:** Status must not be conveyed by color alone.
- **D-08:** Icon-only controls need accessible labels.
- **D-09:** Toast/async status regions should use `aria-live` where appropriate.
- **D-10:** Sidebar, drawer, dialogs, dropdowns, and focus states need keyboard verification.
- **D-11:** Spot-check contrast for text on new tokens, especially muted text and destructive actions.

### Documentation
- **D-12:** Update project guidance with token usage, status/category distinction, guardrail expectations, and no raw client fetch/native dialog conventions.

### the agent's Discretion
- Exact skeleton shapes and empty-state copy if they meet the domain intent.
- Whether accessibility checks use axe/Lighthouse, manual keyboard passes, or both depending on local tooling availability.

</decisions>

<specifics>
## Specific Ideas

The source plan lists Dashboard, Users, RAG, and Login as accessibility scan targets. If local tooling is unavailable, record that and perform manual checks with lint/type verification.

</specifics>

<canonical_refs>
## Canonical References

### Source implementation plan
- `design-proposal/IMPLEMENTATION_PLAN.md` - WP7, WP8, WP9, and final WP10 documentation expectations.
- `design-proposal/PROPOSAL.md` - UX problem analysis and writing guidance.

### Codebase context
- `.planning/codebase/STRUCTURE.md` - high-traffic page and component locations.
- `.planning/codebase/TESTING.md` - available linting and lack of configured frontend test runner.
- `.planning/codebase/CONVENTIONS.md` - frontend style and project guidance patterns.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 2 should provide `EmptyState` and skeleton components.
- Existing `Skeleton` primitive may already exist under `frontend/src/components/ui`.

### Established Patterns
- `CLAUDE.md` is the main project guidance file named by GSD config.
- Frontend lint is available through `cd frontend && npm run lint`.

### Integration Points
- Accessibility changes can touch shell, dialogs, dropdowns, theme toggle, table actions, and status displays from earlier phases.
- Guardrail documentation should match scripts and ESLint rules added in Phases 4 and 5.

</code_context>

<deferred>
## Deferred Ideas

Automated visual regression and a fully configured frontend component/E2E test runner are tracked as v2 requirements.

</deferred>

---

*Phase: 07-loading-empty-a11y*
*Context gathered: 2026-07-01*
