---
phase: 06-connector-and-extract-integration
type: ui-spec
created: 2026-07-05
status: active
---

# Phase 6 UI Spec

## UX Direction

Keep workflow authoring linear, compact, and operational. Connector and Extract support should feel like adding normal platform actions, not configuring a separate workflow product.

## Builder Additions

### Connector Step Editor

For `connector.sync`, add a typed properties panel section:

- Connector select:
  - Label: `Connector`
  - Options from the authenticated connector list.
  - Empty state text inside the select/list can be terse; do not add explanatory panels.
- Since mode select:
  - `Connector checkpoint` default.
  - `Last successful workflow run`.
  - `Full sync` only if backend supports forcing it safely.
- Max records number input:
  - Default `50`.
  - Clamp to a backend-safe maximum.
- Retry attempts using existing `RetryField`.

Validation behavior:

- Missing connector id focuses the connector select.
- Backend disabled/permission errors appear in the existing validation summary and step error area.

### Extract Step Editor

For `extract.run_template`, add a typed properties panel section:

- Extract template select:
  - Options from `extractApi.listTemplates()`.
- Document source select:
  - `Previous step` for outputs like `sync_connector.items`.
  - `RAG collection` for scheduled report workflows.
- Previous step select:
  - Shows earlier workflow steps when document source is previous step.
  - Default to the immediately preceding step when possible.
- Collection select:
  - Reuses existing RAG collection options when document source is RAG collection.
- Connector filter select:
  - Optional; include `Any connector` plus connector options.
- Since mode select:
  - `Last successful workflow run`.
  - `All matching documents`.
- Context JSON textarea:
  - Optional and compact.
  - Keep raw JSON only for this advanced field.
- Retry attempts using existing `RetryField`.

Validation behavior:

- Missing template id focuses the template select.
- Missing document source target focuses previous step or collection select.
- Invalid JSON context is blocked by backend validation with a path-specific error.

## Template Picker

Once runtime support lands:

- Connector Intake Triage card switches from unavailable to available after `connector.sync` support.
- Weekly Extraction Report card switches from unavailable to available after `extract.run_template` support.
- Cards should keep current compact metadata: trigger type, step count, category, tags.
- Do not add a marketing-style template gallery.

## Run Detail Artifacts

Enhance `WorkflowRunTimeline` artifact display:

- Keep the existing artifact list.
- For JSON-like artifacts, show a collapsible or bounded `<pre>` preview of redacted artifact data.
- For Extract artifacts, show:
  - template id
  - job id
  - document count
  - validation issue count
  - compact JSON preview
- Do not make artifacts look like nested cards inside cards; use the existing bordered run detail sections.

## Operations Console

No new top-level workflow navigation is required in Phase 6.

The existing operations console should benefit automatically from:

- Template cards becoming available.
- Runs showing connector/extract step failures and artifacts.
- Existing health states surfacing failed runs.

## Responsive Requirements

- Step editors stack fields on mobile.
- Select trigger text must truncate without forcing layout overflow.
- Artifact previews must have bounded height with scrolling.
- Sticky bottom action bar remains unchanged.
