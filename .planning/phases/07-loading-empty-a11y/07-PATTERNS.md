# Phase 7 Pattern Map

## Shared Primitives

- `frontend/src/components/ui/skeletons.tsx`
  - `PageSkeleton` renders a title block, card grid, and table skeleton for mixed dashboards.
  - `CardGridSkeleton` renders repeated card placeholders and accepts `cards`.
  - `TableSkeleton` renders a bordered table-like placeholder and accepts `rows` and `columns`.
- `frontend/src/components/ui/empty-state.tsx`
  - `EmptyState` accepts `icon`, `title`, `description`, `action`, `docsHref`, and `docsLabel`.
  - Actions should be passed as real `Button` elements so existing dialogs/routes stay intact.
- `frontend/src/components/ui/toaster.tsx`
  - `ToastViewport` is the correct place to add live-region semantics for toasts.

## Existing Loading Patterns

- `frontend/src/app/admin/connectors/page.tsx` already uses `Skeleton` cards for connector loading.
- `frontend/src/components/rag/collection-manager.tsx` already uses card skeleton shapes but hand-rolls the placeholders.
- Several pages still use centered `animate-spin` blocks as their only initial-load UI. These should be replaced by skeleton primitives.

## Existing Empty-State Patterns

- API keys, budgets, connectors, RAG collections, RAG documents, and agents already have the right primary actions wired.
- The implementation should preserve those existing handlers:
  - `setShowCreateDialog(true)` for API keys, budgets, and agents.
  - `setIsAddDialogOpen(true)` for connectors.
  - `setShowCreateDialog(true)` inside RAG collections.
  - Existing upload/select workflow for RAG documents.

## Accessibility Patterns

- `frontend/src/components/ui/theme-toggle.tsx` uses sr-only text inside an icon-only button.
- `frontend/src/app/dashboard/page.tsx` uses sr-only text for "Copy API URL".
- Follow those patterns for RAG document view/download/reprocess/delete, collection delete, admin row menus, and refresh icon buttons.

---
*Phase: 07-loading-empty-a11y*
