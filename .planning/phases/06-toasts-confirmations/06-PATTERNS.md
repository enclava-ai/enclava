# Phase 6 Patterns

## Toasts

- `@/hooks/use-toast` remains the import path for app code, but it should read the shared `ToastProvider` state.
- Use object-style calls:

```ts
toast({
  title: "Saved",
  description: "Changes were saved successfully.",
})
```

- Use `variant: "destructive"` for errors.
- Remove `react-hot-toast` and `sonner` imports/providers after call sites migrate.
- Keep a single mounted `Toaster` inside `ToastProvider`.

## Confirmations

- Mount `ConfirmProvider` high enough in `frontend/src/app/layout.tsx` to cover app pages and components.
- Use `const confirm = useConfirm()` in client components.
- For destructive actions:

```ts
const confirmed = await confirm({
  title: "Delete item?",
  description: "This action cannot be undone.",
  confirmText: "Delete",
  destructive: true,
})
if (!confirmed) return
```

- Use `requireText` only for especially irreversible or high-blast-radius flows.
- Preserve existing async handler behavior after confirmation.

## Guardrails

- After confirms are replaced, default plumbing checks should include native-dialog detection.
- Keep explicit exceptions for route handlers and helper internals from Phase 5.

---
*Phase: 06-toasts-confirmations*
