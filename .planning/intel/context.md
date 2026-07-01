# Ingested Context

**Source:** `design-proposal/IMPLEMENTATION_PLAN.md`
**Supporting docs:** `design-proposal/PROPOSAL.md`, `design-proposal/palette-explorer.html`
**Synthesized:** 2026-07-01

## Problem Statement

The frontend has a token system, but much of the UI bypasses it with legacy `empire-*` classes and raw Tailwind palette utilities. This causes poor light-mode behavior, inconsistent status semantics, theme-blind surfaces, and a visual style that reads less professional than the product's confidential AI positioning.

The UX audit also found broader usability issues: missing mobile navigation, internal navigation that leaves the SPA, multiple toast systems, native browser dialogs, full-page spinners, weak empty states, and insufficient accessibility coverage.

## Current Codebase Fit

Existing codebase intelligence confirms:

- The frontend is a Next.js App Router application under `frontend/src/app`.
- Shared UI primitives live under `frontend/src/components/ui`.
- Shared browser API behavior is centralized in `frontend/src/lib/api-client.ts`.
- Frontend styling uses Tailwind with a tokenized shadcn-style theme.
- Radix UI and lucide-react are already available for dialogs, drawer/sheet-style primitives, and icons.
- `npm run lint` is available as the frontend quality gate.

## Milestone Shape

The incoming plan is best represented as a single UX-improvement milestone with seven dependency-aware phases:

1. Delete deprecated routes.
2. Build the design-system foundation.
3. Rebuild app shell navigation and move LLM IA.
4. Sweep hardcoded colors and rework dashboard.
5. Fix client navigation and API plumbing.
6. Consolidate toasts and confirmation flows.
7. Polish loading, empty, and accessibility states.
