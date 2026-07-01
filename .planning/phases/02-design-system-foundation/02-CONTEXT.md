# Phase 2: Design System Foundation - Context

**Gathered:** 2026-07-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Create the shared semantic token and primitive foundation for the UX overhaul. This phase adds Slate Mono theme tokens, Tailwind status color mappings, and shared UI primitives. It should not perform the app-wide color sweep except for changes required to make the foundation compile.

</domain>

<decisions>
## Implementation Decisions

### Tokens
- **D-01:** Use Slate Mono as the chosen palette.
- **D-02:** Preserve existing `--chart-*` and `--font-*` variables while editing theme colors.
- **D-03:** Use HSL channel triplets and `hsl(var(--x) / <alpha-value>)` Tailwind mappings so opacity modifiers work.
- **D-04:** Split each status role into solid and soft pairs: solid for filled actions, soft for badges/tints.
- **D-05:** `--destructive` aliases the solid danger pair.

### Primitives
- **D-06:** Add `StatusBadge`, `ConfirmDialog`, `PageHeader`, `EmptyState`, and composed skeleton primitives.
- **D-07:** `StatusBadge` uses soft token classes and includes icon plus text.
- **D-08:** `statusForValue()` maps domain strings to `success`, `warning`, `danger`, `info`, or `neutral`.
- **D-09:** Extend existing `Badge` variants with semantic soft styles while preserving existing variants.

### Compatibility
- **D-10:** Keep legacy `empire` and `enclava` definitions until Phase 4 removes usage, then cleanup.
- **D-11:** Do not scaffold committed preview routes; use throwaway local harnesses only if needed.

### the agent's Discretion
- Exact component prop signatures as long as they compile and satisfy downstream needs.
- Whether `ConfirmDialog` context/hook lives in the same file or a colocated provider file.

</decisions>

<specifics>
## Specific Ideas

The implementation plan includes exact light and dark Slate Mono token values. Downstream agents should use those values unless the codebase already contains a corrected equivalent from in-progress user changes.

</specifics>

<canonical_refs>
## Canonical References

### Source implementation plan
- `design-proposal/IMPLEMENTATION_PLAN.md` - WP0 and WP1.
- `design-proposal/PROPOSAL.md` - rationale for semantic tokens, status roles, and Slate Mono.
- `design-proposal/palette-explorer.html` - visual reference only.

### Codebase context
- `.planning/codebase/STACK.md` - Tailwind, React, Radix UI, lucide-react dependencies.
- `.planning/codebase/STRUCTURE.md` - UI primitive locations.
- `.planning/codebase/CONVENTIONS.md` - Tailwind and `cn` usage patterns.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/app/globals.css` owns CSS variables.
- `frontend/tailwind.config.js` maps variables into Tailwind colors.
- `frontend/src/components/ui` contains shadcn-style primitives to extend.
- `frontend/src/lib/utils.ts` provides the `cn` helper.

### Established Patterns
- Shared primitives are imported through `@/components/ui/...`.
- Tailwind classes are composed inline and with `cn`.

### Integration Points
- Later phases will consume `StatusBadge`, `ConfirmDialog`, `PageHeader`, `EmptyState`, and skeletons.

</code_context>

<deferred>
## Deferred Ideas

App-wide consumer migration, dashboard rework, and final removal of legacy palette definitions are deferred to Phase 4.

</deferred>

---

*Phase: 02-design-system-foundation*
*Context gathered: 2026-07-01*
