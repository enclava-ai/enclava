# Enclava

## What This Is

Enclava is a confidential AI platform with a FastAPI backend, Next.js frontend, dynamic modules, RAG, LLM provider orchestration, plugin support, connectors, usage tracking, and admin controls. This planning cycle focuses on making the existing frontend feel like a professional enterprise tool rather than changing the backend product model.

## Core Value

Users can manage confidential AI workflows through a trustworthy, coherent, accessible interface that preserves privacy, cost, and operational clarity.

## Current Milestone: v1.0 Frontend UX Overhaul

**Goal:** Replace the fragmented frontend visual and interaction layer with a consistent Slate Mono design system, navigation shell, and UX guardrails.

**Target features:**
- Slate Mono semantic tokens and shared UI primitives.
- Deprecated-route cleanup before visual sweeps.
- Sidebar and mobile drawer navigation with LLM under Settings.
- Frontend-wide color-literal cleanup and dashboard IA rework.
- SPA navigation, `apiClient`, toast, confirmation, loading, empty-state, accessibility, and guardrail improvements.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- Existing platform capabilities include authentication, dashboard/admin UI, Agents, RAG, Extract, LLM settings, API keys, connectors, plugins, usage, and budget/admin surfaces as mapped in `.planning/codebase/`.

### Active

<!-- Current scope. Building toward these. -->

- [ ] Remove deprecated frontend routes and references before UX sweeps touch dead code.
- [ ] Establish a Slate Mono semantic token and shared primitive layer for both themes.
- [ ] Replace top navigation with an authoritative sidebar/mobile drawer shell and move LLM under Settings.
- [ ] Remove hardcoded color palettes and legacy `empire-*`/`enclava-*` styling from `frontend/src`.
- [ ] Rework dashboard IA around trust, spend, request volume, reliability, attention items, and developer connection details.
- [ ] Replace internal full-page navigation and raw client fetches with project-native routing and `apiClient`.
- [ ] Consolidate toasts and replace native confirmation/alert flows.
- [ ] Replace major full-page spinners and weak empty states with designed alternatives.
- [ ] Improve accessibility and add guardrails against UX regressions.

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- New backend product capabilities - this milestone is frontend UX and client integration cleanup.
- New information architecture from the visual mock - the current nav model is authoritative except for the explicit LLM move under Settings.
- Replacing the UI library or styling framework - the plan extends existing Tailwind/Radix/shadcn-style conventions.
- Full frontend test-stack adoption - lint/type/grep guardrails are required; a new runner can be considered later.

## Context

The frontend already has the right foundation: tokenized Tailwind theme variables, shared UI primitives, `apiClient`, Next.js App Router pages, and provider contexts. The UX problem is drift: legacy fixed dark-theme colors, raw palette utilities, inconsistent status semantics, missing mobile navigation, multiple toast systems, browser-native dialogs, full-page spinners, weak empty states, and insufficient accessibility checks.

The milestone is sourced from `design-proposal/IMPLEMENTATION_PLAN.md`, with supporting rationale in `design-proposal/PROPOSAL.md` and visual reference in `design-proposal/palette-explorer.html`.

## Constraints

- **Stack:** Continue using Next.js App Router, React, Tailwind, Radix/shadcn-style primitives, lucide-react, and existing project utilities.
- **Theme system:** Preserve the `hsl(var(--x) / <alpha-value>)` Tailwind token pattern.
- **Routing:** Keep the existing nav model authoritative; only move LLM to `/settings/llm` as specified.
- **Sequencing:** Delete deprecated routes before color sweeps; build tokens/primitives before consumer work; run accessibility late.
- **Verification:** Frontend work must pass `npm run lint`, frontend type checks, both theme checks, and desktop/mobile visual checks for touched screens.
- **Safety:** Do not read or commit `.env` secret values; do not revert unrelated dirty worktree changes.

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use Slate Mono as the UX palette | It keeps the cyan identity while reducing the cyberpunk/neon feel. | Pending |
| Treat the mock as visual-only | The mock's nav grouping and mobile behavior are intentionally not authoritative. | Pending |
| Move LLM under Settings | LLM configuration is a settings concern and already has provider children beneath settings. | Pending |
| Split status into solid and soft token pairs | Solid fills need AA text contrast; badges need subtle theme-aware tints. | Pending |
| Use `StatusBadge` for severity and neutral `Badge` for categories | Status and category semantics should not be conflated. | Pending |
| Use `apiClient` for client calls | Centralized auth/error behavior prevents drift. | Pending |
| Add grep/ESLint guardrails | The cleanup should fail fast if legacy patterns return. | Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `$gsd-transition`):
1. Requirements invalidated? Move to Out of Scope with reason.
2. Requirements validated? Move to Validated with phase reference.
3. New requirements emerged? Add to Active.
4. Decisions to log? Add to Key Decisions.
5. "What This Is" still accurate? Update if drifted.

**After each milestone** (via `$gsd-complete-milestone`):
1. Full review of all sections.
2. Core Value check - still the right priority?
3. Audit Out of Scope - reasons still valid?
4. Update Context with current state.

---
*Last updated: 2026-07-01 after ingesting `design-proposal/IMPLEMENTATION_PLAN.md`*
