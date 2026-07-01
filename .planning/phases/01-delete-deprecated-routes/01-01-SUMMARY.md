---
phase: 01-delete-deprecated-routes
plan: "01"
subsystem: ui
tags: [nextjs, app-router, cleanup, rag]

requires: []
provides:
  - Deprecated frontend route pages removed
  - Sole-use frontend RAG debug proxy routes removed
affects: [frontend-routes, frontend-api-proxies, phase-01-delete-deprecated-routes]

tech-stack:
  added: []
  patterns:
    - Scoped route cleanup through source deletion and grep verification

key-files:
  created: []
  modified:
    - frontend/src/app/debug/page.tsx
    - frontend/src/app/rag-demo/page.tsx
    - frontend/src/app/test-auth/page.tsx
    - frontend/src/app/api/rag/debug/collections/route.ts
    - frontend/src/app/api/rag/debug/search/route.ts

key-decisions:
  - "Removed only deprecated frontend route surfaces and sole-use frontend proxies."
  - "Preserved active product routes, backend connector code, and backend RAG debug endpoints."

patterns-established:
  - "Deprecated route cleanup is verified by disk absence, git index absence, and targeted reference scans."

requirements-completed: [CLN-01]

duration: 5 min
completed: 2026-07-01
---

# Phase 1 Plan 01: Delete Deprecated Routes Summary

**Deprecated App Router pages and sole-use frontend RAG debug proxies were removed without touching active routes or backend functionality.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-01T13:21:30Z
- **Completed:** 2026-07-01T13:26:21Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Removed tracked `/debug`, `/rag-demo`, and `/test-auth` page files.
- Removed the frontend-only `/api/rag/debug/collections` and `/api/rag/debug/search` proxy route files after confirming there were no active callers.
- Removed empty legacy route/API directories where present, including empty chatbot/zammad directories.

## Task Commits

1. **Task 1: Delete tracked deprecated route pages** - `6552b23` (refactor)
2. **Task 2: Delete sole-use RAG demo proxies and empty deprecated directories** - `bc463a7` (refactor)

## Files Created/Modified

- `frontend/src/app/debug/page.tsx` - Deleted deprecated debug dashboard route.
- `frontend/src/app/rag-demo/page.tsx` - Deleted deprecated RAG demo route.
- `frontend/src/app/test-auth/page.tsx` - Deleted deprecated authentication test route.
- `frontend/src/app/api/rag/debug/collections/route.ts` - Deleted sole-use frontend RAG collections proxy.
- `frontend/src/app/api/rag/debug/search/route.ts` - Deleted sole-use frontend RAG search proxy.

## Decisions Made

- Kept deletion scope to the planned route/proxy paths plus empty deprecated directories.
- Did not remove active `frontend/src/app/rag`, dashboard, settings, connector, or backend code.

## Verification

- `test ! -e` passed for all five deleted route/proxy files.
- `git ls-files` returned no output for all five deleted route/proxy files after task commits.
- `rg -n "/api/rag/debug|rag/debug" frontend/src` returned no output after proxy deletion.
- `find frontend/src/app/chatbot frontend/src/app/zammad frontend/src/app/api/chatbot frontend/src/app/api/v1/chatbot frontend/src/app/api/v1/zammad -type f 2>/dev/null` returned no output.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 01-02 reference reconciliation and frontend lint/type/build verification.

---
*Phase: 01-delete-deprecated-routes*
*Completed: 2026-07-01*
