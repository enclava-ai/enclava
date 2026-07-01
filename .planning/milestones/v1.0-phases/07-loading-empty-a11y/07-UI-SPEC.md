---
phase: 07-loading-empty-a11y
status: approved
created: 2026-07-01
---

# Phase 7 UI Design Contract

## Loading States

- Page-level initial loads must preserve the eventual layout shape.
- Use `PageSkeleton` for mixed dashboard/page layouts, `CardGridSkeleton` for card grids, and `TableSkeleton` for table-first screens.
- Keep spinners only for inline busy states: button submission, refresh icon animation, upload progress, and row-level processing.
- Skeletons must use existing semantic token classes from the shared primitives, not raw palette utilities.

## Empty States

- Use `EmptyState` for high-traffic zero-data screens.
- Each empty state needs:
  - a relevant lucide icon
  - a short title that names the next useful outcome
  - one sentence of value-oriented body copy
  - a primary action wired to the existing create/upload dialog or route
  - optional docs link only when a stable project docs URL is already known
- Avoid one-line "No data found" states except filtered search results, where the copy should tell the user to adjust filters.

## Accessibility

- Icon-only controls must have an accessible name through `aria-label` or a visible/sr-only text label.
- Status indicators must include text, not only color or icon shape.
- Toast and async status regions should expose polite live-region semantics.
- Keyboard traversal must continue to work for sidebar, drawer, dropdown menus, dialogs, and destructive confirmations.
- Focus styles must use existing `ring`/`focus-visible` tokens.

## Copy

- Prefer active onboarding language:
  - "Create your first API key"
  - "Start tracking spend"
  - "Upload documents to build a searchable knowledge base"
- Avoid passive or vague copy:
  - "No data"
  - "No items found"
  - "Nothing here"

## Verification

- `npm run lint`
- `npm run build`
- Phase 7 scans from `07-VALIDATION.md`
- Manual source-level keyboard/a11y checklist documented in `07-VERIFICATION.md`

---
*UI contract: approved*
