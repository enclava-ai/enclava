---
phase: 3
slug: app-shell-navigation
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-01
---

# Phase 3 - Validation Strategy

## Automated Checks

- `rg -n 'href: "/llm"|replace\\('/llm|router\\.replace\\('/llm|href="/llm"' frontend/src`
- `test -f frontend/src/app/settings/llm/page.tsx`
- `test -f frontend/src/app/llm/page.tsx`
- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `cd frontend && npx tsc --noEmit` with unrelated TypeScript 6 blocker documented if it persists.

## Acceptance

- Desktop and mobile nav use the same model in code.
- `/llm` redirects to `/settings/llm` preserving query params.
- `/settings/llm/providers` and `/prompt-templates` redirect directly to `/settings/llm?...`.
- No deprecated `/debug`, `/rag-demo`, or `/test-auth` routes are reintroduced.
