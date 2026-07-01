# Phase 7 Research: Loading, Empty, and Accessibility Polish

## Scope

Phase 7 is the final frontend UX polish pass for the current milestone. It should reuse the shared primitives created earlier instead of adding another UI pattern:

- `frontend/src/components/ui/skeleton.tsx`
- `frontend/src/components/ui/skeletons.tsx`
- `frontend/src/components/ui/empty-state.tsx`
- `frontend/src/components/ui/status-badge.tsx`
- `frontend/src/components/ui/toaster.tsx`

## Source Findings

The implementation proposal maps this phase to WP7, WP8, WP9, and the final WP10 documentation work:

- WP7 replaces full-page initial-load spinners with structure-preserving skeletons.
- WP8 turns one-line empty states into onboarding moments.
- WP9 adds labels, live regions, status text, and keyboard/focus checks.
- WP10 documents conventions and guardrail expectations in project guidance.

Current scans found:

- Full-page spinners still exist in auth redirects and high-traffic admin pages, including `ProtectedRoute`, root `app/page.tsx`, admin redirect pages, API keys, budgets, admin users, and related page-level loading branches.
- Empty states for API keys, budgets, RAG collections/documents, connectors, and agents are still mostly bespoke Card blocks rather than the shared `EmptyState` primitive.
- RAG document action buttons and several admin action buttons are icon-only without accessible names.
- `ToastViewport` has no explicit `aria-live` contract.
- `CLAUDE.md` documents `apiClient` but not the final token/status/guardrail conventions delivered by this milestone.

## Implementation Strategy

1. Replace page-level initial-load spinners with `PageSkeleton`, `CardGridSkeleton`, or `TableSkeleton` according to final layout shape.
2. Convert high-traffic empty states to `EmptyState` with a relevant icon, value-oriented copy, and a primary action.
3. Add accessible labels to icon-only controls touched by the phase, add live-region semantics to toast/async status surfaces, and document the final frontend conventions.

## Risks

- Some loading indicators are valid inline busy states. Do not remove button-level spinners, row refresh indicators, or upload progress indicators.
- Several high-traffic pages are large. Keep edits local to loading, empty-state, and accessibility branches instead of refactoring data fetching or page architecture.
- Authenticated browser scans are not available without credentials; verification should record this and use lint/build plus source-level scans.

## Validation Architecture

- Source scans should prove no targeted page-level `h-12 w-12 border-b-2 border-primary` spinners remain in Phase 7 target files.
- Source scans should prove the planned empty-state target files import and render `EmptyState`.
- Source scans should prove no targeted icon-only buttons remain without accessible text or `aria-label`.
- `cd frontend && npm run lint` and `cd frontend && npm run build` remain the executable frontend gates.
- `cd frontend && npx tsc --noEmit` remains a known TypeScript 6 config limitation unless the project config is modernized.

---
*Phase: 07-loading-empty-a11y*
