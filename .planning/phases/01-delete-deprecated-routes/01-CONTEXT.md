# Phase 1: Delete Deprecated Routes - Context

**Gathered:** 2026-07-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Remove deprecated and dev-only frontend routes before any downstream styling or guardrail sweep touches dead code. This phase is limited to deleting route surfaces, sole-use components, obsolete frontend proxies, and inbound references. Broader UX restyling starts in later phases.

</domain>

<decisions>
## Implementation Decisions

### Deprecated routes
- **D-01:** Delete `frontend/src/app/chatbot`, `frontend/src/app/zammad`, `frontend/src/app/debug`, `frontend/src/app/test-auth`, and `frontend/src/app/rag-demo` if present.
- **D-02:** Delete sole-use frontend components and hooks tied only to those routes.
- **D-03:** Delete obsolete chatbot/zammad frontend API proxies when they are only used by deleted routes.

### References
- **D-04:** Grep for `chatbot`, `zammad`, `/debug`, `test-auth`, and `rag-demo` in `frontend/src` and remove dead nav entries, links, imports, and route references.
- **D-05:** Preserve backend connector functionality for zammad-style connector concepts if it exists outside the deleted standalone page; this phase is not a backend connector deletion.

### the agent's Discretion
- Exact deletion order and local verification commands.
- Whether to split proxy deletion and component deletion into separate commits during implementation.

</decisions>

<specifics>
## Specific Ideas

The source plan notes that the backend chatbot API was already removed, so frontend cleanup should not resurrect chatbot behavior or style deleted code.

</specifics>

<canonical_refs>
## Canonical References

### Source implementation plan
- `design-proposal/IMPLEMENTATION_PLAN.md` - WP-D and execution wave ordering.

### Codebase context
- `.planning/codebase/STRUCTURE.md` - Frontend app, component, and API proxy locations.
- `.planning/codebase/ARCHITECTURE.md` - Frontend API proxy boundary and module/provider context.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/app` contains route directories to remove.
- `frontend/src/components` contains route-specific components that may become unreachable after route deletion.

### Established Patterns
- Next.js App Router route directories map directly to URL paths.
- Frontend imports commonly use `@/*` aliases.

### Integration Points
- `frontend/src/components/ui/navigation.tsx` may contain links to routes deleted here.
- `frontend/src/app/api` may contain proxy routes tied to removed pages.

</code_context>

<deferred>
## Deferred Ideas

Styling cleanup, navigation shell rewrite, and guardrail enforcement are deferred to later phases.

</deferred>

---

*Phase: 01-delete-deprecated-routes*
*Context gathered: 2026-07-01*
