# Phase 2 Pattern Map: Design System Foundation

**Phase:** 2 - Design System Foundation
**Generated:** 2026-07-01

## Pattern Summary

The frontend uses local shadcn-style UI primitives in `frontend/src/components/ui`, Tailwind classes composed with `cn()`, and CSS variables defined in `frontend/src/app/globals.css`. Phase 2 should extend these local patterns instead of introducing a new component system.

## Files and Closest Analogs

### Theme tokens

**Targets:**
- `frontend/src/app/globals.css`
- `frontend/tailwind.config.js`

**Pattern:** HSL channel triplets in CSS variables mapped through Tailwind theme colors. New semantic mappings should use `hsl(var(--x) / <alpha-value>)`.

### Badge primitives

**Targets:**
- `frontend/src/components/ui/badge.tsx`
- `frontend/src/components/ui/status-badge.tsx`

**Pattern:** `cva` variants and `cn()` class composition. Preserve existing `Badge` API while adding soft status variants.

### Dialog primitives

**Targets:**
- `frontend/src/components/ui/alert-dialog.tsx`
- `frontend/src/components/ui/confirm-dialog.tsx`

**Pattern:** Wrap existing Radix Alert Dialog primitives. Use local `Button`, `Input`, and semantic token classes.

### Layout and empty/loading primitives

**Targets:**
- `frontend/src/components/ui/page-header.tsx`
- `frontend/src/components/ui/empty-state.tsx`
- `frontend/src/components/ui/skeletons.tsx`

**Pattern:** Named exports, typed props, Tailwind classes, direct imports from existing local primitives.

## Defer Boundaries

- Do not migrate app-wide hardcoded colors in Phase 2.
- Do not remove `empire`/`enclava` Tailwind palettes until Phase 4.
- Do not move navigation or LLM routes until Phase 3.
- Do not replace native dialogs/toasts until Phase 6.
