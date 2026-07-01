# Phase 1 Pattern Map: Delete Deprecated Routes

**Phase:** 1 - Delete Deprecated Routes
**Generated:** 2026-07-01

## Pattern Summary

The frontend uses Next.js App Router filesystem routes. Removing a route means deleting its `frontend/src/app/<route>/page.tsx` directory tree. There is no separate route registry for App Router pages. Shared navigation is manually declared in `frontend/src/components/ui/navigation.tsx`, so any deprecated-route nav references must be removed there if found.

## Files and Closest Analogs

### Route pages

**Targets:**
- `frontend/src/app/debug/page.tsx`
- `frontend/src/app/rag-demo/page.tsx`
- `frontend/src/app/test-auth/page.tsx`

**Role:** Top-level app routes.

**Pattern:** Delete the route directory. Verify no imports or links reference the route path.

**Closest existing analog:** Active routes under `frontend/src/app/dashboard/page.tsx`, `frontend/src/app/rag/page.tsx`, and `frontend/src/app/settings/page.tsx` remain because they are user-facing product routes.

### Frontend debug proxy routes

**Targets:**
- `frontend/src/app/api/rag/debug/collections/route.ts`
- `frontend/src/app/api/rag/debug/search/route.ts`

**Role:** Next.js API route proxies used by the RAG demo route.

**Pattern:** Delete sole-use proxy routes when their only frontend caller is deleted. Preserve backend internal APIs unless explicitly scoped elsewhere.

**Closest existing analog:** Legitimate active proxy routes under `frontend/src/app/api/*/route.ts` remain when used by active UI flows.

### Navigation

**Potential target:**
- `frontend/src/components/ui/navigation.tsx`

**Role:** Manually declared product navigation.

**Pattern:** Remove explicit nav item objects pointing at deleted routes. Do not restructure shell navigation in Phase 1; Phase 3 owns the shell rewrite.

**Research finding:** No active nav references to `chatbot`, `zammad`, `/debug`, `test-auth`, or `rag-demo` were found at planning time.

## Deletion Safety Rules

- Keep `frontend/src/components/connectors/*` unless it is proven sole-use for `app/zammad`.
- Keep backend connector/module code; Phase 1 is frontend-route cleanup.
- Do not delete `frontend/src/app/api/rag/debug/*` if a non-deleted active route still imports or fetches it at execution time; otherwise delete it with `rag-demo`.
- Do not change styling, tokens, sidebar shell, LLM route movement, or guardrails in this phase.
