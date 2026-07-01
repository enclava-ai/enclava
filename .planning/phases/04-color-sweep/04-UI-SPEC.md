---
phase: 04-color-sweep
slug: color-sweep
status: approved
shadcn_initialized: true
preset: Slate Mono product surfaces
created: 2026-07-01
---

# Phase 4 - UI Design Contract

## Design System

| Property | Value |
|----------|-------|
| Tool | local shadcn-style primitives |
| Component library | existing Radix/local wrappers |
| Icon library | lucide-react |
| Status primitive | `StatusBadge` and semantic Badge variants |
| Color tokens | Phase 2 Slate Mono semantic tokens |

## Color Contract

- Replace legacy `empire-*` and `enclava-*` UI classes with semantic tokens.
- Replace raw palette utilities with semantic roles where they express surface, text, border, focus, accent, or status.
- Severity states use `StatusBadge` or `success/warning/danger/info` token classes.
- Entity/category labels use neutral outline badges unless the value is truly a severity.
- Legacy palette definitions stay until the final plan reports zero UI usage, then they are removed.

## Dashboard Contract

Dashboard answers three questions:

1. Is data private and protected?
2. What is it costing and how much is being used?
3. What needs attention?

Required dashboard sections:

| Section | Requirement |
|---------|-------------|
| Trust line | Confidentiality status, provider health, and policy signal in one compact row. |
| KPI row | Spend, requests, and reliability/error-rate cards. |
| Usage chart | Simple token/request/cost trend visualization using semantic colors. |
| Attention list | Prioritized operational items with status text, not color-only dots. |
| Connect strip | Slim developer connection details for API/Open WebUI/Continue-style setup. |

## Copywriting Contract

- Prefer short operational labels: `Protected`, `Spend`, `Requests`, `Reliability`, `Needs attention`, `Connect`.
- Avoid decorative marketing copy inside product surfaces.
- Empty states explain what is missing and provide one obvious next action where applicable.

## Layout Contract

- Preserve dense product-tool ergonomics.
- Avoid nested cards and decorative page-section cards.
- Cards remain individual repeated items or genuinely framed metrics.
- Fixed-format widgets use stable dimensions so charts/status rows do not shift.

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS
- [x] Dimension 2 Visuals: PASS
- [x] Dimension 3 Color: PASS
- [x] Dimension 4 Typography: PASS
- [x] Dimension 5 Spacing: PASS
- [x] Dimension 6 Registry Safety: PASS

**Approval:** approved 2026-07-01
