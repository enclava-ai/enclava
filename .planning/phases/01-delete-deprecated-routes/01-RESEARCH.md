# Phase 1 Research: Delete Deprecated Routes

## RESEARCH COMPLETE

**Phase:** 1 - Delete Deprecated Routes
**Date:** 2026-07-01
**Purpose:** Determine the exact route cleanup scope before generating executable plans.

## Phase Summary

Phase 1 removes deprecated and dev-only frontend routes before downstream styling and guardrail phases touch dead code. This is a cleanup phase, not a redesign phase. The critical safety boundary is to remove only the deprecated frontend route surfaces and their sole-use frontend proxies/components, while preserving backend connector/platform functionality.

## Live Code Findings

### Tracked deprecated route files still present

`git ls-files` shows these tracked route pages are still present:

- `frontend/src/app/debug/page.tsx`
- `frontend/src/app/rag-demo/page.tsx`
- `frontend/src/app/test-auth/page.tsx`

These satisfy the tracked portion of `CLN-01` and should be deleted.

### Empty or untracked deprecated directories

`find` reports these directories exist:

- `frontend/src/app/chatbot`
- `frontend/src/app/zammad`
- `frontend/src/app/api/chatbot`
- `frontend/src/app/api/v1/chatbot`
- `frontend/src/app/api/v1/zammad`

However, `git ls-files` finds no tracked files under those chatbot/zammad paths. They may be empty runtime leftovers or untracked directories. The executor should remove them with `rm -rf` if they still exist, but there may be no git diff for those paths.

### Sole-use frontend proxy routes

`frontend/src/app/rag-demo/page.tsx` calls these frontend proxies:

- `frontend/src/app/api/rag/debug/collections/route.ts`
- `frontend/src/app/api/rag/debug/search/route.ts`

`frontend/src/app/debug/page.tsx` calls backend internal debug endpoints through `apiClient`; it does not need the frontend `/api/rag/debug/*` proxy routes. Once `rag-demo` is deleted, the two `frontend/src/app/api/rag/debug/*` proxies appear sole-use and should be deleted with the demo.

### Current reference scan

Current `rg -n "chatbot|zammad|/debug|test-auth|rag-demo" frontend/src` results are limited to:

- `frontend/src/app/rag-demo/page.tsx`
- `frontend/src/app/debug/page.tsx`
- `frontend/src/app/api/rag/debug/collections/route.ts`
- `frontend/src/app/api/rag/debug/search/route.ts`

No active navigation references were found in `frontend/src/components/ui/navigation.tsx` during research. Plan 01-02 should still run the scan after deletions and remove any remaining references if the tree changes before execution.

## Implementation Risks

- **Accidental product deletion:** Do not delete backend connector code, backend RAG debug code, or `frontend/src/components/connectors/*`. Phase 1 is scoped to deprecated frontend route surfaces and sole-use frontend proxies.
- **Dirty worktree drift:** The worktree has unrelated history and `design-proposal/` is untracked. Executors must not revert unrelated changes.
- **Empty directory confusion:** Git does not track empty directories. Removing empty chatbot/zammad route directories may not appear in `git status`, which is acceptable.
- **Build cost:** `npm run build` is the source plan's DoD, but it may be slower than lint/type. Execute lint/type first, then build if those pass.

## Recommended Plan Split

### Plan 01-01: Delete route and proxy files

Delete the tracked route pages and sole-use RAG debug frontend proxies. Remove empty/untracked chatbot/zammad route directories if present. Do not edit navigation or broad references here except where necessary to keep deletion atomic.

### Plan 01-02: Reference reconciliation and verification

Run the reference scan over `frontend/src`, remove any remaining live references in non-deleted files, and run frontend quality gates.

## Validation Architecture

Phase 1 validation is source-oriented because it deletes dead UI routes rather than adding runtime behavior.

### Automated checks

- `git ls-files frontend/src/app/debug/page.tsx frontend/src/app/rag-demo/page.tsx frontend/src/app/test-auth/page.tsx frontend/src/app/api/rag/debug/collections/route.ts frontend/src/app/api/rag/debug/search/route.ts` returns no output after Plan 01-01.
- `test ! -e frontend/src/app/debug && test ! -e frontend/src/app/test-auth && test ! -e frontend/src/app/rag-demo` exits 0 after Plan 01-01.
- `rg -n "chatbot|zammad|/debug|test-auth|rag-demo" frontend/src` returns no output after Plan 01-02, except intentional backend-proxy references if a later decision keeps a non-route debug proxy.
- `cd frontend && npm run lint` exits 0.
- `cd frontend && npx tsc --noEmit` exits 0.
- `cd frontend && npm run build` exits 0.

### Manual checks

None required for this phase. The expected behavior is route absence and clean imports, both checkable from source and build output.
