# Phase 4: Color Sweep and Dashboard - Context

**Gathered:** 2026-07-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Remove legacy and raw color usage across `frontend/src`, migrate status semantics to shared components, rework the dashboard IA, clean up temporary legacy palette definitions, and add hardcoded-color guardrails. This phase should run after shell/navigation ownership has landed.

</domain>

<decisions>
## Implementation Decisions

### Sweep strategy
- **D-01:** Run a root baseline grep before starting and ensure every hit belongs to a planned bucket.
- **D-02:** Sweep by directory group to reduce collisions: admin/audit; RAG/Extract; dashboard/settings/playground; agents/LLM/connectors/plugins/auth; catch-all.
- **D-03:** Shell files owned by Phase 3 are out of scope unless Phase 3 has already completed and the owner explicitly hands them off.

### Mapping
- **D-04:** Replace body text legacy accent usage with `text-foreground` or `text-muted-foreground`.
- **D-05:** Replace accent/icon usage with `text-primary` where it is truly an accent.
- **D-06:** Replace legacy card/surface backgrounds with `bg-card` or `bg-muted` based on hierarchy.
- **D-07:** Replace border literals with `border-border`, `border-primary/20`, or semantic status borders as appropriate.
- **D-08:** Status severity uses `StatusBadge` and `statusForValue()`.
- **D-09:** Audit entity categories use neutral outline badges, not status colors.

### Dashboard
- **D-10:** Dashboard IA should answer: is data private, what is it costing, what needs attention.
- **D-11:** Dashboard should include trust line, three KPIs, usage chart, attention list, and slim connect strip.
- **D-12:** Remove vanity or duplicate dashboard widgets that belong on dedicated pages.

### Guardrails
- **D-13:** After sweeps report zero, remove legacy `empire`/`enclava` Tailwind and CSS definitions.
- **D-14:** Add a reliable grep/script guardrail for color and legacy token patterns.

### the agent's Discretion
- Exact dashboard chart component and layout details if the IA and visual direction are preserved.
- Whether color guardrails are introduced in this phase or split into a focused plan within the same phase.

</decisions>

<specifics>
## Specific Ideas

The plan's WP3 mapping table is canonical. Audit action types are severities; audit entity types are categories. Do not merge these concepts to make the code shorter.

</specifics>

<canonical_refs>
## Canonical References

### Source implementation plan
- `design-proposal/IMPLEMENTATION_PLAN.md` - WP3, WP0 cleanup, and WP10 color guardrails.
- `design-proposal/PROPOSAL.md` - problem analysis and dashboard IA rationale.
- `design-proposal/palette-explorer.html` - dashboard and visual reference.

### Codebase context
- `.planning/codebase/STRUCTURE.md` - frontend directories and high-impact files.
- `.planning/codebase/CONVENTIONS.md` - Tailwind class composition patterns.
- `.planning/codebase/TESTING.md` - frontend lint gate and test-runner limitations.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 2 primitives should provide `StatusBadge`, badge variants, and semantic tokens.
- `frontend/src/app/dashboard/page.tsx` is the main IA rework target.

### Established Patterns
- Tailwind class strings appear directly in JSX; root grep checks are necessary because type checks will not catch color semantics.

### Integration Points
- `frontend/tailwind.config.js` and `frontend/src/app/globals.css` keep temporary legacy definitions until final cleanup.
- `CLAUDE.md` may need updates for guardrail conventions in Phase 7 as well.

</code_context>

<deferred>
## Deferred Ideas

Raw fetch and internal navigation cleanup are deferred to Phase 5. Toast/dialog migration is deferred to Phase 6. Full accessibility audit is deferred to Phase 7.

</deferred>

---

*Phase: 04-color-sweep*
*Context gathered: 2026-07-01*
