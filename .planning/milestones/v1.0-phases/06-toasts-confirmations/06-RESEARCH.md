# Phase 6 Research: Toasts and Confirmations

**Gathered:** 2026-07-01

## Source References

- `design-proposal/IMPLEMENTATION_PLAN.md` WP5 and WP6 define toast and native-dialog cleanup.
- `.planning/phases/06-toasts-confirmations/06-CONTEXT.md` locks the selected toast API and confirmation requirements.
- Phase 2 provides `frontend/src/components/ui/confirm-dialog.tsx`.
- Phase 5 provides `frontend/scripts/check-client-plumbing.sh` with opt-in native-dialog detection.

## Baseline Findings

Toast scan found three systems:

- Mounted providers in `frontend/src/app/layout.tsx`: shadcn-style `Toaster`, `react-hot-toast` `HotToaster`, and `sonner` `Sonner`.
- Shared provider in `frontend/src/contexts/ToastContext.tsx`.
- Call-site hook in `frontend/src/hooks/use-toast.ts` currently owns local state per caller, while `components/ui/toaster.tsx` also reads that local hook. This means provider-mounted toasts are not sharing caller state.

Third-party toast imports remain in:

- `frontend/src/app/settings/llm/page.tsx` via `react-hot-toast`.
- `frontend/src/components/llm/UsageTab.tsx` via `react-hot-toast`.
- `frontend/src/app/admin/users/page.tsx` via `sonner`.
- `frontend/src/app/admin/connectors/page.tsx` via `sonner`.

Native dialog scan found `confirm()` usage in:

- `frontend/src/app/budgets/page.tsx`
- `frontend/src/app/admin/api-keys/page.tsx`
- `frontend/src/app/admin/connectors/page.tsx`
- `frontend/src/app/admin/pricing/page.tsx`
- `frontend/src/app/admin/users/page.tsx`
- `frontend/src/components/admin/UserManagement.tsx`
- `frontend/src/components/plugins/PluginManager.tsx`

## Risks

- Toast consolidation must make existing `@/hooks/use-toast` callers share the mounted provider state.
- Removing third-party toast packages must update both `package.json` and `package-lock.json`.
- Confirmation migrations touch destructive admin flows; copy should clearly state the consequence and preserve existing handler behavior.
- `ConfirmProvider` must wrap all call sites before `useConfirm()` is used.

## Planning Implications

- Plan 06-01 should fix shared toast state, migrate third-party toast call sites, remove extra providers, and uninstall unused toast packages.
- Plan 06-02 should mount `ConfirmProvider`, replace all native confirms, and turn the Phase 5 native-dialog detector into an enforced guardrail.

---
*Phase: 06-toasts-confirmations*
