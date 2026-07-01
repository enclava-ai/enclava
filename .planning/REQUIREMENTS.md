# Requirements: Enclava Frontend UX Overhaul

**Defined:** 2026-07-01
**Core Value:** Users can manage confidential AI workflows through a trustworthy, coherent, accessible interface that preserves privacy, cost, and operational clarity.

## v1 Requirements

### Cleanup and Route Hygiene

- [x] **CLN-01**: Deprecated frontend routes `chatbot`, `zammad`, `debug`, `test-auth`, and `rag-demo` are removed with sole-use components and obsolete API proxies.
- [ ] **CLN-02**: Navigation, links, imports, and references no longer point to deleted routes.
- [ ] **CLN-03**: The frontend build/lint surface has no dangling imports from deleted route code.

### Design System Foundation

- [ ] **DS-01**: Light and dark theme tokens implement the Slate Mono palette while preserving existing chart and font variables.
- [ ] **DS-02**: Tailwind theme colors use the alpha-capable `hsl(var(--x) / <alpha-value>)` pattern and expose solid and soft status roles.
- [ ] **DS-03**: Shared primitives exist for `StatusBadge`, `ConfirmDialog`, `PageHeader`, `EmptyState`, and composed skeletons.
- [ ] **DS-04**: Legacy palette cleanup is sequenced so `empire` and `enclava` definitions remain only until all usage is removed.

### Navigation and Information Architecture

- [ ] **NAV-01**: The current navigation model is extracted or preserved as the authoritative source for sidebar and drawer rendering.
- [ ] **NAV-02**: Desktop users can navigate through a left sidebar and mobile users can navigate through a drawer exposing the same nav items.
- [ ] **NAV-03**: LLM settings live at `/settings/llm`, `/llm` redirects with query parameters preserved, and inbound redirects target `/settings/llm?...` directly.
- [ ] **NAV-04**: Shell navigation active states, focus states, and keyboard behavior work in both themes and responsive widths.

### Color Migration and Dashboard

- [ ] **COL-01**: `empire-*` and `enclava-*` usage is removed across `frontend/src`.
- [ ] **COL-02**: Raw Tailwind palette utilities for text, backgrounds, borders, gradients, rings, and dividers are replaced with semantic tokens where covered by the proposal.
- [ ] **COL-03**: Status severities use `StatusBadge`; category labels use neutral badge treatments.
- [ ] **COL-04**: Dashboard IA is reworked around trust status, spend, requests, reliability, attention items, and developer connection details.
- [ ] **COL-05**: Final root greps over `frontend/src` return zero for legacy palette and disallowed hardcoded color patterns.

### Client Plumbing

- [ ] **PLUMB-01**: Internal route navigation uses Next.js `Link` or router APIs rather than `window.location` or `window.open`.
- [ ] **PLUMB-02**: Real client-component backend calls use `apiClient` instead of raw `fetch`.
- [ ] **PLUMB-03**: Server route-handler fetches and documentation code-sample fetches remain explicitly exempt and documented.

### Feedback and Confirmation UX

- [ ] **FDBK-01**: The frontend mounts one toast provider and uses one toast API.
- [ ] **FDBK-02**: Existing `react-hot-toast` and `sonner` call sites are migrated or removed.
- [ ] **FDBK-03**: Destructive and confirmation flows use the themed `ConfirmDialog` or `useConfirm` path instead of native `confirm()` or `alert()`.

### Loading and Empty States

- [ ] **STATE-01**: Major initial-load full-page spinners are replaced with structure-preserving skeletons.
- [ ] **STATE-02**: High-traffic empty states provide explanatory copy and a primary action.

### Accessibility and Guardrails

- [ ] **A11Y-01**: Status is not conveyed by color alone, and icon-only controls have accessible labels.
- [ ] **A11Y-02**: Sidebar, drawer, dialogs, dropdowns, focus rings, and async/toast regions pass a keyboard and accessibility spot-check.
- [ ] **GUARD-01**: ESLint or script guardrails catch hardcoded colors and legacy palette names.
- [ ] **GUARD-02**: Guardrails catch native dialogs and disallowed client fetch calls while preserving documented exceptions.
- [ ] **GUARD-03**: Project guidance documents the design token, status, and guardrail conventions.

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Frontend Testing

- **TEST-01**: Add a configured frontend component or E2E test runner for regression coverage.
- **TEST-02**: Add automated visual regression coverage for high-traffic frontend routes.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Backend product features | This milestone is a frontend UX and client integration cleanup. |
| Mock-driven IA changes beyond the stated LLM move | The implementation plan says the current nav model is authoritative. |
| Replacing Tailwind/Radix/shadcn-style primitives | Existing stack is adequate and already mapped by codebase intel. |
| Full frontend test-stack adoption | Useful later, but not required to execute this milestone safely. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CLN-01 | Phase 1 | Complete |
| CLN-02 | Phase 1 | Pending |
| CLN-03 | Phase 1 | Pending |
| DS-01 | Phase 2 | Pending |
| DS-02 | Phase 2 | Pending |
| DS-03 | Phase 2 | Pending |
| DS-04 | Phase 2 | Pending |
| NAV-01 | Phase 3 | Pending |
| NAV-02 | Phase 3 | Pending |
| NAV-03 | Phase 3 | Pending |
| NAV-04 | Phase 3 | Pending |
| COL-01 | Phase 4 | Pending |
| COL-02 | Phase 4 | Pending |
| COL-03 | Phase 4 | Pending |
| COL-04 | Phase 4 | Pending |
| COL-05 | Phase 4 | Pending |
| PLUMB-01 | Phase 5 | Pending |
| PLUMB-02 | Phase 5 | Pending |
| PLUMB-03 | Phase 5 | Pending |
| FDBK-01 | Phase 6 | Pending |
| FDBK-02 | Phase 6 | Pending |
| FDBK-03 | Phase 6 | Pending |
| STATE-01 | Phase 7 | Pending |
| STATE-02 | Phase 7 | Pending |
| A11Y-01 | Phase 7 | Pending |
| A11Y-02 | Phase 7 | Pending |
| GUARD-01 | Phase 4 | Pending |
| GUARD-02 | Phase 5 | Pending |
| GUARD-03 | Phase 7 | Pending |

**Coverage:**

- v1 requirements: 29 total
- Mapped to phases: 29
- Unmapped: 0

---
*Requirements defined: 2026-07-01*
*Last updated: 2026-07-01 after ingesting `design-proposal/IMPLEMENTATION_PLAN.md`*
