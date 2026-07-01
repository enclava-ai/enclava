# Phase 5: SPA Navigation and API Client Plumbing - Context

**Gathered:** 2026-07-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace internal full-page reloads/new-tab navigation and raw client-component backend fetches with project-native routing and `apiClient`. This phase does not rewrite server route-handler fetches or documentation code samples.

</domain>

<decisions>
## Implementation Decisions

### Navigation
- **D-01:** Internal routes should use Next `Link` or `useRouter().push()`.
- **D-02:** Keep `window.open` only for genuinely external URLs or intentionally external new-tab flows.
- **D-03:** Avoid regressions that lose SPA state or open stray tabs for internal product flows.

### API calls
- **D-04:** Real client-component calls to backend APIs should use `apiClient` from `@/lib/api-client`.
- **D-05:** Do not rewrite `frontend/src/app/api/**/route.ts` server proxies as client API calls.
- **D-06:** Do not rewrite documentation/example `fetch` snippets; mark them with `// api-sample` when needed for guardrail exemption.

### Guardrails
- **D-07:** Add guardrails for native dialogs and disallowed client fetch calls with explicit route-handler and documentation exceptions.
- **D-08:** CI grep should be the authoritative backstop for text patterns that AST linting may miss.

### the agent's Discretion
- Exact `apiClient` helper additions as long as consumers avoid duplicated auth/error handling.
- Whether guardrails live in an existing script directory or a new `scripts/` helper.

</decisions>

<specifics>
## Specific Ideas

The implementation plan estimates roughly 17 `window.location` usages, 3 `window.open` usages, and roughly 11 real client-side `fetch(` calls, but agents should verify the current tree because the worktree already contains unrelated changes.

</specifics>

<canonical_refs>
## Canonical References

### Source implementation plan
- `design-proposal/IMPLEMENTATION_PLAN.md` - WP4 and WP10 fetch/native-dialog guardrail scope.

### Codebase context
- `.planning/codebase/ARCHITECTURE.md` - frontend `apiClient` boundary and proxy architecture.
- `.planning/codebase/CONVENTIONS.md` - import aliases and API-client convention.
- `.planning/codebase/TESTING.md` - frontend lint gate.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/lib/api-client.ts` is the shared browser API client.
- Next App Router supports `Link` and `useRouter` for in-app navigation.

### Established Patterns
- Server proxy routes live under `frontend/src/app/api`.
- Client components commonly live under `frontend/src/app` pages and `frontend/src/components`.

### Integration Points
- Guardrail script should exclude `frontend/src/app/api/**/route.ts` for fetch checks.
- Documentation examples such as integration guides may intentionally show public external API usage.

</code_context>

<deferred>
## Deferred Ideas

Toast consolidation and confirmation dialogs are deferred to Phase 6. Accessibility spot-checks of changed controls are finalized in Phase 7.

</deferred>

---

*Phase: 05-spa-api-plumbing*
*Context gathered: 2026-07-01*
