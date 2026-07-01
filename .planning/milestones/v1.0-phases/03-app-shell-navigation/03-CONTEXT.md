# Phase 3: App Shell and LLM IA - Context

**Gathered:** 2026-07-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the top-bar navigation shell with a desktop sidebar and mobile drawer while preserving the current navigation model. Move the LLM page under Settings and maintain compatibility redirects. This phase owns shell files and route movement; color sweep phases must not edit shell ownership boundaries concurrently.

</domain>

<decisions>
## Implementation Decisions

### Navigation model
- **D-01:** Reuse the existing `components/ui/navigation.tsx` logic as authoritative.
- **D-02:** Preserve core items, module/plugin items, Settings children, admin/permission gating, and active-state semantics.
- **D-03:** The mock is styling reference only and must not define nav labels, grouping, or responsive behavior.

### Shell
- **D-04:** Desktop navigation uses a left sidebar.
- **D-05:** Mobile navigation uses a working drawer exposing the same nav model.
- **D-06:** Topbar carries breadcrumb/title affordance, theme toggle, and mobile drawer trigger.
- **D-07:** User menu moves to the sidebar or equivalent persistent shell area if that matches implementation.

### LLM route move
- **D-08:** Move `frontend/src/app/llm/page.tsx` to `frontend/src/app/settings/llm/page.tsx`.
- **D-09:** Add query-preserving redirect from `/llm` to `/settings/llm`.
- **D-10:** Update redirects in `settings/llm/providers` and `prompt-templates` to target `/settings/llm?tab=...` directly.
- **D-11:** Grep for remaining string links to `/llm` and eliminate unintended old references.

### the agent's Discretion
- Exact component split names, as long as shell ownership and nav parity are clear.
- Whether the compatibility redirect is implemented through Next config or a route stub, provided query parameters survive.

</decisions>

<specifics>
## Specific Ideas

Use active nav styling from the Slate Mono direction: quiet neutral shell, `bg-accent-soft`, `text-primary`, and a subtle active rail or equivalent.

</specifics>

<canonical_refs>
## Canonical References

### Source implementation plan
- `design-proposal/IMPLEMENTATION_PLAN.md` - WP2 and binding LLM IA decision.
- `design-proposal/palette-explorer.html` - visual shell styling reference only.

### Codebase context
- `.planning/codebase/STRUCTURE.md` - frontend route and component locations.
- `.planning/codebase/ARCHITECTURE.md` - frontend root layout and provider composition.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/components/ui/navigation.tsx` contains current nav logic.
- `frontend/src/app/layout.tsx` owns global shell/provider composition.
- `frontend/src/components/ui/theme-toggle.tsx` already exists.

### Established Patterns
- App Router pages move by moving route directories.
- Frontend components use project path aliases.

### Integration Points
- `frontend/next.config.js` may be the best place for a permanent `/llm` redirect.
- `frontend/src/app/settings/llm/providers/page.tsx` and `frontend/src/app/prompt-templates/page.tsx` are known redirect stubs from the source plan.

</code_context>

<deferred>
## Deferred Ideas

Non-shell color sweeps, dashboard IA, toast consolidation, and skeleton/empty-state work are deferred to later phases.

</deferred>

---

*Phase: 03-app-shell-navigation*
*Context gathered: 2026-07-01*
