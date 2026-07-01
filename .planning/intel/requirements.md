# Ingested Requirements

**Source:** `design-proposal/IMPLEMENTATION_PLAN.md`
**Synthesized:** 2026-07-01

## Functional Requirements

- The frontend uses a semantic Slate Mono token layer in both light and dark mode.
- Status colors use a consistent semantic role model with solid and soft pairs.
- Shared UI primitives exist for status badges, confirmation dialogs, page headers, empty states, and skeleton loaders.
- Deprecated routes and route-specific components are removed before downstream styling work.
- The LLM settings page lives at `/settings/llm`, with `/llm` redirect compatibility.
- Desktop users can navigate through a sidebar; mobile users can navigate through a drawer.
- Color literals and legacy `empire-*`/`enclava-*` styling are removed across `frontend/src`.
- The dashboard presents the new information architecture from the proposal.
- Internal navigation remains within the SPA.
- Client components use `apiClient` for backend calls.
- Toasts use a single provider and API.
- Destructive actions use themed confirmation dialogs.
- Full-page spinners are replaced with layout-preserving skeletons where appropriate.
- Key empty states explain value and provide a primary action.
- Status and icon-only UI meets the accessibility expectations in the plan.
- Guardrails prevent reintroduction of disallowed styling, dialog, navigation, and fetch patterns.

## Verification Requirements

- `cd frontend && npm run lint` passes.
- TypeScript type checking passes for the frontend.
- Both light and dark themes are visually verified on touched screens.
- Desktop and mobile widths are visually verified for touched workflows.
- `/llm?tab=providers` redirects to `/settings/llm?tab=providers`.
- Root greps over `frontend/src` return zero for legacy color tokens after the sweep is complete.
- CI/editor guardrails fail on deliberate examples of banned hardcoded colors, legacy palette names, native dialogs, and disallowed client fetch calls.
