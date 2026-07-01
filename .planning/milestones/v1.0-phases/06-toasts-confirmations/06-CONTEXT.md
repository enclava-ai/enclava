# Phase 6: Toasts and Confirmations - Context

**Gathered:** 2026-07-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Consolidate frontend toast behavior to one provider/API and replace native browser `confirm()`/`alert()` flows with themed dialogs and toast feedback. This phase consumes the Phase 2 `ConfirmDialog` and toast conventions.

</domain>

<decisions>
## Implementation Decisions

### Toasts
- **D-01:** Standardize on the existing shadcn-style `@/hooks/use-toast` system named in the source plan.
- **D-02:** Remove extra mounted providers for `react-hot-toast` and `sonner` after call sites migrate.
- **D-03:** Migrate `toast.success()` and `toast.error()` style calls to the selected object-style toast API.
- **D-04:** Remove unused toast dependencies from `frontend/package.json` when no imports remain.

### Confirmations
- **D-05:** Replace frontend native `confirm()` calls with `ConfirmDialog` or `useConfirm()`.
- **D-06:** Replace native `alert()` success/error notifications with themed toasts.
- **D-07:** Destructive irreversible actions should require typed confirmation where the source plan calls it out.
- **D-08:** Destructive actions use the solid danger/destructive token pair, not soft badge colors.

### the agent's Discretion
- Exact copy for confirmation dialogs, as long as action consequences are clear.
- Whether each migration is grouped by domain area or by primitive type.

</decisions>

<specifics>
## Specific Ideas

Known high-impact targets include user deletion, API key revocation, budget deletion, connector removal, plugin actions, and admin pricing/API key pages.

</specifics>

<canonical_refs>
## Canonical References

### Source implementation plan
- `design-proposal/IMPLEMENTATION_PLAN.md` - WP5 and WP6.

### Codebase context
- `.planning/codebase/STRUCTURE.md` - frontend component and page locations.
- `.planning/codebase/ARCHITECTURE.md` - frontend provider composition in layout.
- `.planning/codebase/CONVENTIONS.md` - frontend notification and logging guidance.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 2 should provide `ConfirmDialog` and/or `useConfirm`.
- Existing toast contexts/providers are mounted through the app layout/provider tree.

### Established Patterns
- Frontend package dependencies live in `frontend/package.json` and `frontend/package-lock.json`.
- UI dialogs should use existing Radix/shadcn-style primitives.

### Integration Points
- `frontend/src/app/layout.tsx` is likely touched for provider consolidation.
- Admin, plugin, budget, connector, and API key surfaces likely contain destructive flows.

</code_context>

<deferred>
## Deferred Ideas

Final accessibility scan of dialogs and live regions is deferred to Phase 7.

</deferred>

---

*Phase: 06-toasts-confirmations*
*Context gathered: 2026-07-01*
