---
phase: 07
slug: advanced-control-flow-and-triggers
status: approved
shadcn_initialized: true
preset: enclava-v1
created: 2026-07-05
---

# Phase 07 - UI Design Contract

Visual and interaction contract for minimal branch semantics in the existing workflow builder.

## Design System

| Property | Value |
|----------|-------|
| Tool | shadcn-style local primitives |
| Preset | Enclava Slate Mono semantic tokens |
| Component library | Radix-backed local components |
| Icon library | lucide-react |
| Font | Existing app font stack |

## Spacing Scale

Declared values must remain on the existing Tailwind scale.

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Icon gaps, branch badges, compact metadata |
| sm | 8px | Field spacing, branch row controls |
| md | 16px | Properties panel groups, validation blocks |
| lg | 24px | Builder section gaps |
| xl | 32px | Main two-column layout gap |

Exceptions: none.

## Typography

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Body | existing `text-sm` | 400 | default |
| Label | existing `text-sm` | 500 | default |
| Panel heading | existing `text-sm` | 600 | default |
| Page heading | existing `text-2xl` | 600-700 | default |

Do not add viewport-scaled type. Letter spacing stays normal.

## Color

Use semantic tokens only.

| Role | Value | Usage |
|------|-------|-------|
| Dominant | existing background/card tokens | Builder surface and properties panel |
| Secondary | muted/accent soft tokens | Selected step state, branch metadata chips |
| Accent | primary/status tokens | Focus states, active branch status, valid indicators |
| Warning | warning tokens | Branch validation warnings and skipped path hints |
| Destructive | danger tokens | Invalid config and remove-step actions only |

Accent reserved for selected step state, focus rings, and status badges. No new palette.

## Copywriting Contract

| Element | Copy |
|---------|------|
| Step display name | Branch |
| Catalog description | Choose which later steps to skip based on a previous output. |
| Properties heading | Branch rule |
| Source field | Input step |
| Path field | Path |
| Operator field | Operator |
| Value field | Value |
| Matched path label | When matched |
| Not matched path label | When not matched |
| Target field | Skip steps |
| Validation error shape | `Branch "{key}" references an earlier step` |
| Empty target message | `No later steps available` |

Avoid instructional paragraphs. Helper text can be one short sentence only when an empty or invalid target list would otherwise be unclear.

## Layout Contract

### Builder Step List

- Branches appear as normal ordered step rows.
- Show branch type with `StatusBadge`, matching current step row patterns.
- Add only compact branch metadata where useful: source step/path, operator, and count of skipped target steps.
- Do not draw connectors, arrows between cards, mini maps, graph previews, or canvas-style nodes.

### Properties Panel

- Preserve the existing right-side properties panel width and sticky behavior.
- Branch properties use grouped form controls:
  - source input: input step select plus path input.
  - rule: operator select plus value input when the operator requires a value.
  - outcomes: matched label, not-matched label, skipped target steps.
- Target step selection must only present later steps.
- On mobile, controls stack vertically with stable button/input widths.

### Run Detail

- Branch step output should render inside the existing timeline payload preview.
- If a branch skipped steps, skipped step rows remain visible with `Skipped` status and a concise reason.
- Branch event text should be compact, for example `Branch matched: high priority`.

## Interaction Contract

- Selecting a branch step updates the properties panel without navigation.
- Changing the input step should clear invalid path/target choices only when those choices are no longer valid.
- Operator changes should preserve value only when the new operator uses a value.
- Branch targets cannot include the branch step itself or earlier steps.
- Publish remains blocked by backend validation errors.
- Save draft remains allowed with incomplete branch fields.

## Accessibility

- All branch controls need labels tied to inputs.
- Target step controls must be keyboard reachable and not rely on color alone.
- Icon-only controls keep `title` and `sr-only` labels.
- Validation summary should continue to focus/select the branch step with the error.
- Skipped status in run detail must be textual, not color-only.

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| Local shadcn-style primitives | Button, Input, Select, Textarea if needed, StatusBadge | Existing frontend lint/build gates |
| Third-party components | none | not applicable |

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS
- [x] Dimension 2 Visuals: PASS
- [x] Dimension 3 Color: PASS
- [x] Dimension 4 Typography: PASS
- [x] Dimension 5 Spacing: PASS
- [x] Dimension 6 Registry Safety: PASS

**Approval:** approved 2026-07-05
