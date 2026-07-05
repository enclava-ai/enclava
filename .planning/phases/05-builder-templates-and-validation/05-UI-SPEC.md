# Phase 5 UI Spec: Workflow Builder

## Purpose

Provide a compact builder for common workflow authoring without turning Workflows into a canvas product. The user should be able to create a draft, configure trigger and steps, see validation issues, publish, enable, and return to operations.

## Approved Direction

- Keep `/workflows` operations-first.
- Add builder entry routes:
  - `/workflows/new`
  - `/workflows/[workflowId]/edit`
- Builder layout:
  - Top band: workflow name, status, template/source label, and actions.
  - Trigger strip: Manual or Schedule controls, cron, timezone, preview.
  - Main area: ordered step list and right properties panel.
  - Bottom action bar: validation summary, Save draft, Publish, Enable, Run test when safe.

## Layout Contract

### Desktop

- Outer page uses the same constrained app content width as existing Workflows surfaces.
- Use a two-column grid for the main builder:
  - left/center: step sequence, min width 0, flexible.
  - right: properties panel, 360-420px, sticky within viewport where feasible.
- Do not put page sections inside a parent card.
- Cards are allowed for individual repeated step rows and template cards only, with `rounded-md`.

### Mobile

- Stack trigger, step list, properties, and action bar vertically.
- Properties panel appears below selected step.
- Button rows wrap; no text may overflow button bounds.
- Step row controls use icon buttons with accessible labels and title attributes.

## Components

- Use `Button` with lucide icons for create, save, publish, enable, preview, add step, remove step, move up/down, duplicate, and refresh.
- Use `Select` for trigger type, timezone, step type, agent, RAG collection, misfire policy, concurrency policy, and redaction policy.
- Use `Input` for name, cron, numeric limits, budget, retry attempts, and step key.
- Use `Textarea` for description and prompt templates.
- Use `Switch` or `Checkbox` only for binary runtime toggles.
- Use `StatusBadge` for draft/active/disabled, validation state, enabled/unavailable step types, and publish status.
- Use existing `ConfirmDialog` for publish/enable actions and any run-now action that can spend budget.

## Copy Contract

- Labels are short and operational:
  - `Name`
  - `Trigger`
  - `Schedule`
  - `Timezone`
  - `Steps`
  - `Properties`
  - `Validation`
  - `Save draft`
  - `Publish`
  - `Enable`
  - `Run test`
- Validation messages should point to the exact field:
  - `Step "summarize" is missing agent_id`
  - `Schedule trigger requires timezone`
  - `connector.sync is available in Phase 6`
- Avoid instructional paragraphs. Empty states may use one short sentence.

## Visual Contract

- Use existing semantic tokens only.
- No new dominant palette.
- Validation severity:
  - errors: existing danger tokens.
  - warnings/unavailable future steps: warning/neutral tokens.
  - valid: success token.
- Keep typography compact:
  - page title: existing Workflows `text-2xl`.
  - panel headings: `text-sm font-semibold`.
  - helper/meta text: `text-xs` or `text-sm text-muted-foreground`.
- Letter spacing stays normal.

## Interaction Contract

- Selecting a step updates the properties panel without navigation.
- Add-step opens a catalog picker or compact menu filtered to enabled step types by default.
- Disabled future step types may be shown in templates but cannot be added to a publishable workflow.
- Schedule preview updates only from the explicit preview action or successful validation, not on every keystroke.
- Save draft is allowed with validation warnings, but publish requires no blocking validation errors.
- Enable requires a published workflow and uses the existing lifecycle confirm pattern.

## Accessibility

- Step rows must be keyboard selectable.
- Icon-only controls require `title` and `sr-only` text.
- Validation summary links or buttons should focus the matching trigger/step properties.
- Status must not rely on color only; use text labels.
- Confirmation dialogs must focus correctly and return focus to the triggering action.

## Non-Goals

- No canvas, pan/zoom, minimap, node graph, or drag-only editing.
- No full tutorial text inside the builder.
- No landing/marketing page for workflows.
