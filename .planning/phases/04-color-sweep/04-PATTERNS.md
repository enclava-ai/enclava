# Phase 4 Patterns

## Semantic Color Replacement

- Use `text-foreground` for primary body text.
- Use `text-muted-foreground` for secondary copy.
- Use `text-primary` for accent icons or links only when they are intentionally accented.
- Use `bg-card` for cards and panels.
- Use `bg-muted` for nested surfaces, bars, empty placeholders, and skeleton-like fills.
- Use `border-border` for normal borders and `border-primary/20` for subtle accent borders.
- Use `focus-visible:ring-ring` or local component defaults for focus treatment.

## Status Treatment

- Use `StatusBadge` for values such as healthy, active, successful, error, failed, pending, warning, disabled, enabled, and syncing.
- Use `statusForValue()` where backend strings are heterogeneous.
- Use `Badge variant="outline"` or `Badge variant="secondary"` for categories such as entity type, provider, model, connector type, or role.
- Do not encode audit entity categories as success/warning/danger.

## Progress and Charts

- Track fills should use `bg-muted`.
- Primary quantitative fills should use `bg-primary`.
- Success/error split bars can use semantic `bg-success` and `bg-danger`.
- Avoid raw palette bars unless the color is represented by a semantic token.

## Loading and Empty

- Replace legacy colored spinners touched during the sweep with `Loader2 className="... text-primary"` or a Phase 2 skeleton where the surrounding work already owns the loading shape.
- Full loading/empty-state migration remains Phase 7; avoid broad skeleton rewrites in Phase 4 unless needed to eliminate a hardcoded color in the touched component.

## Guardrail Scope

The final guardrail should scan UI source for:

- legacy Tailwind palette classes in `className`-like strings,
- `empire-*` and `enclava-*` UI class names,
- raw hex color literals in UI source.

It should avoid false positives for:

- server route-handler backend host strings such as `enclava-backend`,
- documentation/examples that are not UI classes,
- CSS custom property definitions that are part of semantic token declarations.

---
*Phase: 04-color-sweep*
