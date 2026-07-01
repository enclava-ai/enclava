# Roadmap: Enclava Frontend UX Overhaul

## Overview

This milestone turns the existing Enclava frontend into a coherent professional product surface. It starts by removing deprecated routes, builds the shared token and primitive foundation, replaces the shell navigation, sweeps hardcoded color patterns, then finishes with client-plumbing, feedback, loading, empty-state, accessibility, and guardrail work.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work.
- Decimal phases (2.1, 2.2): Urgent insertions if needed.

- [x] **Phase 1: Delete Deprecated Routes** - Remove dead/dev-only frontend routes and references before visual sweeps touch deleted code. (completed 2026-07-01)
- [x] **Phase 2: Design System Foundation** - Add Slate Mono tokens, status vocabulary, and shared UX primitives. (completed 2026-07-01)
- [x] **Phase 3: App Shell and LLM IA** - Replace top navigation with sidebar/drawer shell and move LLM under Settings. (completed 2026-07-01)
- [x] **Phase 4: Color Sweep and Dashboard** - Remove hardcoded color systems and rework the dashboard IA. (completed 2026-07-01)
- [x] **Phase 5: SPA Navigation and API Client Plumbing** - Replace internal full reloads/new tabs and raw client fetches. (completed 2026-07-01)
- [x] **Phase 6: Toasts and Confirmations** - Consolidate feedback systems and replace native dialogs. (completed 2026-07-01)
- [ ] **Phase 7: Loading, Empty, and Accessibility Polish** - Improve skeletons, empty states, accessibility, and final conventions.

## Phase Details

### Phase 1: Delete Deprecated Routes

**Goal**: Remove dead/dev-only route surfaces so later styling and guardrail work operates on the code that will remain.
**Depends on**: Nothing (first phase)
**Requirements**: [CLN-01, CLN-02, CLN-03]
**Success Criteria** (what must be TRUE):

  1. Deleted route directories and sole-use components are gone.
  2. Navigation, links, imports, and route proxies no longer reference deleted routes.
  3. Frontend lint/build checks do not fail because of dangling deleted-route imports.

**Plans**: 2 plans
Plans:
**Wave 1**

- [x] 01-01: Delete deprecated routes, API proxies, and sole-use components.

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02: Remove inbound references and verify the frontend remains import-clean.

### Phase 2: Design System Foundation

**Goal**: Establish the semantic token and primitive layer that downstream UX work can consume.
**Depends on**: Phase 1
**Requirements**: [DS-01, DS-02, DS-03, DS-04]
**Success Criteria** (what must be TRUE):

  1. Slate Mono light and dark tokens render through the existing Tailwind token system.
  2. Status utilities support both solid and soft pairs with working opacity modifiers.
  3. Shared primitives compile and are available without shipping preview-only routes.
  4. Legacy palette definitions remain only as temporary compatibility until Phase 4 removes usages.

**Plans**: 3 plans
Plans:
**Wave 1**

- [x] 02-01: Implement Slate Mono tokens and Tailwind status mappings.

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02: Build shared UI primitives and helper mappings.

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 02-03: Verify foundation behavior in both themes and document usage conventions.

### Phase 3: App Shell and LLM IA

**Goal**: Replace the current top-nav shell with desktop sidebar and mobile drawer navigation while keeping the authoritative nav model intact.
**Depends on**: Phase 2
**Requirements**: [NAV-01, NAV-02, NAV-03, NAV-04]
**Success Criteria** (what must be TRUE):

  1. Desktop sidebar and mobile drawer expose the same authorized navigation model.
  2. LLM settings live at `/settings/llm`, and `/llm?tab=...` redirects with the query string intact.
  3. Existing thin redirect routes target `/settings/llm?...` directly.
  4. Active states, keyboard focus, and responsive layout work in both themes.

**Plans**: 3 plans
Plans:
**Wave 1**

- [x] 03-01: Extract/preserve the nav model and build sidebar/topbar/mobile drawer components.

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-02: Move the LLM route under Settings and add compatibility redirects.

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 03-03: Integrate the shell in layout and verify desktop/mobile navigation parity.

### Phase 4: Color Sweep and Dashboard

**Goal**: Remove frontend hardcoded color systems, apply semantic status treatment, rework the dashboard, and add color guardrails.
**Depends on**: Phase 3
**Requirements**: [COL-01, COL-02, COL-03, COL-04, COL-05, GUARD-01]
**Success Criteria** (what must be TRUE):

  1. `empire-*` and `enclava-*` usages are gone from `frontend/src`.
  2. Raw palette utilities covered by the proposal are replaced with semantic tokens.
  3. Status severity and category labels use the correct shared components.
  4. Dashboard implements the new trust/spend/requests/reliability/attention/connect IA.
  5. Root greps and color guardrails pass after legacy palette cleanup.

**Plans**: 5 plans
Plans:
**Wave 1**

- [x] 04-01: Sweep admin, audit, pricing, user, and API key surfaces.

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 04-02: Sweep RAG, Extract, and related domain components.

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 04-03: Rework dashboard and sweep dashboard/settings/playground surfaces.

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 04-04: Sweep agents, LLM, connectors, plugins, auth, and catch-all surfaces.

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 04-05: Remove legacy palette definitions and add hardcoded-color guardrails.

### Phase 5: SPA Navigation and API Client Plumbing

**Goal**: Preserve SPA behavior and centralize real client API calls through `apiClient`.
**Depends on**: Phase 4
**Requirements**: [PLUMB-01, PLUMB-02, PLUMB-03, GUARD-02]
**Success Criteria** (what must be TRUE):

  1. Internal navigation uses Next `Link` or router APIs rather than `window.location` or internal `window.open`.
  2. Real client-component backend calls use `apiClient`.
  3. Server route-handler fetches and documentation examples are exempted intentionally.
  4. Guardrails catch native dialogs and disallowed client fetch calls without false positives for documented exceptions.

**Plans**: 2 plans

Plans:

- [x] 05-01: Replace internal `window.location` and `window.open` navigation.
- [x] 05-02: Replace real client fetches with `apiClient` and add plumbing guardrails.

### Phase 6: Toasts and Confirmations

**Goal**: Make feedback and destructive-action flows consistent, themed, and accessible.
**Depends on**: Phase 5
**Requirements**: [FDBK-01, FDBK-02, FDBK-03]
**Success Criteria** (what must be TRUE):

  1. Only one toast provider is mounted in the app shell.
  2. Toast call sites use the selected project toast API.
  3. Native `confirm()` and `alert()` calls in frontend `.tsx` are replaced by themed dialogs or toasts.
  4. Irreversible destructive flows require appropriate confirmation text where applicable.

**Plans**: 2 plans

Plans:

- [x] 06-01: Consolidate toast providers, dependencies, and call sites.
- [x] 06-02: Replace native confirmation and alert flows with `ConfirmDialog` or `useConfirm`.

### Phase 7: Loading, Empty, and Accessibility Polish

**Goal**: Improve perceived quality and accessibility after the main UI systems have landed.
**Depends on**: Phase 6
**Requirements**: [STATE-01, STATE-02, A11Y-01, A11Y-02, GUARD-03]
**Success Criteria** (what must be TRUE):

  1. Major initial-load full-page spinners are replaced with skeletons where appropriate.
  2. High-traffic zero states provide clear value, primary action, and optional docs path.
  3. Statuses are not color-only, icon-only controls are labeled, and async/toast regions announce changes.
  4. Sidebar, drawer, dialogs, dropdowns, and focus states pass a keyboard spot-check.
  5. `CLAUDE.md` or equivalent project guidance documents the token/status/guardrail conventions.

**Plans**: 3 plans

Plans:

**Wave 1**

- [x] 07-01: Replace high-impact full-page spinners with skeleton loaders.

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 07-02: Add designed empty states to high-traffic zero-state screens.

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 07-03: Run accessibility pass and document final UX guardrail conventions.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Delete Deprecated Routes | 2/2 | Complete    | 2026-07-01 |
| 2. Design System Foundation | 3/3 | Complete    | 2026-07-01 |
| 3. App Shell and LLM IA | 3/3 | Complete    | 2026-07-01 |
| 4. Color Sweep and Dashboard | 5/5 | Complete    | 2026-07-01 |
| 5. SPA Navigation and API Client Plumbing | 2/2 | Complete    | 2026-07-01 |
| 6. Toasts and Confirmations | 2/2 | Complete    | 2026-07-01 |
| 7. Loading, Empty, and Accessibility Polish | 3/3 | In review | - |

---
*Roadmap created: 2026-07-01 from `design-proposal/IMPLEMENTATION_PLAN.md`*
