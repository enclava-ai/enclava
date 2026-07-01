# Phase 3 Research: App Shell and LLM IA

## RESEARCH COMPLETE

**Phase:** 3 - App Shell and LLM IA
**Date:** 2026-07-01

## Findings

- `frontend/src/components/ui/navigation.tsx` owns the current authoritative nav model, including core items, module-driven items, plugin pages, settings children, and active-state checks.
- `frontend/src/app/layout.tsx` currently renders a top navigation and a centered container around all pages.
- `frontend/src/app/llm/page.tsx` is the current LLM page. It can move to `frontend/src/app/settings/llm/page.tsx`.
- `frontend/src/app/settings/llm/providers/page.tsx` and `frontend/src/app/prompt-templates/page.tsx` currently redirect to `/llm?...`; they need to target `/settings/llm?...` directly.

## Risks

- Moving the LLM route without preserving query params would break inbound tab links.
- Rebuilding nav from the mock would lose module/plugin/admin logic.
- Applying the app shell to unauthenticated pages could make login/register awkward.

## Recommended Plan Split

1. Extract/render a sidebar/drawer shell from the current nav model.
2. Move LLM under Settings and add query-preserving compatibility redirects.
3. Verify nav parity, active states, redirects, lint, and build.
