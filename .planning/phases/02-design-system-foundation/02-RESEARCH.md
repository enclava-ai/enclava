# Phase 2 Research: Design System Foundation

## RESEARCH COMPLETE

**Phase:** 2 - Design System Foundation
**Date:** 2026-07-01
**Purpose:** Identify the exact token and primitive work needed before downstream UX phases.

## Live Code Findings

### Token layer

- `frontend/src/app/globals.css` owns CSS custom properties for light and dark themes.
- `frontend/tailwind.config.js` maps those variables into Tailwind theme colors.
- Current Tailwind color mappings use `hsl(var(--x))`, which prevents opacity modifiers like `bg-primary/20` from resolving correctly under Tailwind's alpha placeholder model.
- Existing `--chart-*` and `--font-*` variables are present and must be preserved.
- Legacy `enclava` and `empire` palettes are still mapped in Tailwind and used elsewhere; Phase 2 keeps them for compatibility and Phase 4 removes usage plus definitions.

### Primitive layer

- `frontend/src/components/ui` follows shadcn-style wrappers with named exports and `cn()`.
- `button.tsx`, `badge.tsx`, `card.tsx`, `alert-dialog.tsx`, `input.tsx`, and `skeleton.tsx` are the main local building blocks.
- Radix Alert Dialog and lucide-react are already installed, so no dependency changes are needed.

## Implementation Risks

- **Opacity regression:** Tailwind mappings must use `hsl(var(--x) / <alpha-value>)` for semantic colors while keeping legacy palette definitions available.
- **Contrast regression:** Solid destructive/danger colors need a separate foreground from soft badge foregrounds.
- **Premature migration:** App-wide status/color consumer migration belongs to Phase 4; Phase 2 should add targets, not sweep every caller.
- **Preview-route regression:** Do not add committed preview routes under deleted paths or new dev-only app routes.

## Recommended Plan Split

### Plan 02-01: Tokens and Tailwind status mappings

Update `globals.css` and `tailwind.config.js` with Slate Mono tokens, alpha-capable mappings, and solid/soft status roles. Preserve font/chart variables and legacy palettes for now.

### Plan 02-02: Shared UI primitives

Add `StatusBadge`, `ConfirmDialog`, `PageHeader`, `EmptyState`, and composed skeleton primitives. Extend `Badge` with semantic soft variants.

### Plan 02-03: Foundation verification

Run lint/build/reference checks, verify no preview routes were added, and document the known standalone TypeScript 6 deprecation blocker if it persists.

## Validation Architecture

- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `cd frontend && npx tsc --noEmit` for import/type signal, with the existing TypeScript 6 config deprecation issue documented if still present.
- Source greps for token mappings and forbidden preview routes.

## Notes for Downstream Phases

- Consumers should prefer `StatusBadge` for severity/status display.
- Category or type labels should remain neutral badges unless they represent status.
- `ConfirmDialog` should replace native confirmation flows in Phase 6.
- Skeleton primitives should replace high-impact spinners in Phase 7.
