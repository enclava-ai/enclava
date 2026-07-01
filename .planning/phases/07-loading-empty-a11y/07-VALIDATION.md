# Phase 7 Validation

## Per-Plan Gates

Plan 07-01 must run:

- `cd frontend && npm run lint`
- targeted page-level spinner scan returns no matches:

```bash
rg -n "h-12 w-12 border-b-2 border-primary|flex items-center justify-center min-h-\\[400px\\]" frontend/src/components/auth/ProtectedRoute.tsx frontend/src/app/page.tsx frontend/src/app/admin/page.tsx frontend/src/app/settings/llm/providers/page.tsx frontend/src/app/admin/api-keys/page.tsx frontend/src/app/admin/users/page.tsx frontend/src/app/budgets/page.tsx
```

Plan 07-02 must run:

- `cd frontend && npm run lint`
- empty-state adoption scan shows the target files import `EmptyState`:

```bash
rg -n "EmptyState" frontend/src/app/admin/api-keys/page.tsx frontend/src/app/admin/connectors/page.tsx frontend/src/app/budgets/page.tsx frontend/src/components/rag/collection-manager.tsx frontend/src/components/rag/document-browser.tsx frontend/src/components/agent/AgentConfigManager.tsx
```

Plan 07-03 must run:

- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- icon-only/accessibility scan over touched files is reviewed:

```bash
rg -n "size=\"icon\"|className=\"h-8 w-8 p-0\"|ToastViewport|aria-live|aria-label|sr-only" frontend/src/app/admin frontend/src/components/rag frontend/src/components/ui/toaster.tsx frontend/src/components/connectors/ConnectorCard.tsx frontend/src/components/admin/UserManagement.tsx
```

## Known Limitation

Standalone TypeScript currently reports TypeScript 6 deprecations for `target=ES5` and `baseUrl`. Phase 7 should document this if it remains unchanged.

---
*Phase: 07-loading-empty-a11y*
