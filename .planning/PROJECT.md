# Enclava

## What This Is

Enclava is a confidential AI platform with a FastAPI backend, Next.js frontend, dynamic modules, RAG, LLM provider orchestration, plugin support, connectors, usage tracking, and admin controls. The frontend now has a coherent enterprise product surface built on semantic tokens, shared UI primitives, a responsive app shell, centralized client API plumbing, themed feedback flows, and UX guardrails.

## Core Value

Users can manage confidential AI workflows through a trustworthy, coherent, accessible interface that preserves privacy, cost, and operational clarity.

## Current State

**Shipped milestone:** v1.0 Frontend UX Overhaul, completed 2026-07-01.

**Delivered:**
- Deprecated frontend routes and sole-use proxies were removed.
- Slate Mono semantic tokens, status roles, and shared primitives are available.
- The authenticated app uses a desktop sidebar and mobile drawer from one nav model.
- LLM configuration lives under `/settings/llm`, with `/llm` compatibility redirects.
- Frontend color usage was migrated away from legacy palettes and raw UI color utilities.
- Dashboard IA now emphasizes trust, spend, requests, reliability, attention, connection, and module health.
- Internal browser navigation and planned real client JSON calls use project-native router/API paths.
- Toast and confirmation flows are consolidated around project primitives.
- Major loading and empty states use shared skeleton and `EmptyState` primitives.
- Accessibility labels, live-region feedback, and frontend UX guardrail documentation are in place.

**Archive references:**
- `.planning/milestones/v1.0-ROADMAP.md`
- `.planning/milestones/v1.0-REQUIREMENTS.md`
- `.planning/milestones/v1.0-MILESTONE-AUDIT.md`

## Next Milestone Goals

No next milestone is defined yet. Candidate follow-up areas from v1.0 deferred items:
- Modernize `frontend/tsconfig.json` for TypeScript 6 so `npx tsc --noEmit` can become a hard gate.
- Add frontend component or E2E test infrastructure for authenticated workflows.
- Add visual regression screenshots for high-traffic routes.
- Connect dashboard spend to a reliable frontend cost source.

## Requirements

### Validated

- v1.0: Deprecated frontend routes and references are removed before UX sweeps touch dead code.
- v1.0: Slate Mono semantic tokens and shared primitives work in both themes.
- v1.0: Top navigation is replaced by an authoritative sidebar/mobile drawer shell.
- v1.0: LLM configuration lives under Settings with query-preserving compatibility redirects.
- v1.0: Legacy `empire-*`/`enclava-*` styling and covered raw UI palette utilities are removed from `frontend/src`.
- v1.0: Dashboard IA is reworked around trust, spend, request volume, reliability, attention items, and developer connection details.
- v1.0: Internal full-page navigation and raw client fetches in planned surfaces use project-native routing and `apiClient`.
- v1.0: Toasts are consolidated and native confirmation/alert flows are replaced.
- v1.0: Major full-page spinners and weak empty states are replaced with designed alternatives.
- v1.0: Accessibility labels, async feedback semantics, and guardrails against UX regressions are documented and verified.

### Active

None. Start the next requirements cycle with `$gsd-new-milestone`.

### Out of Scope

- New backend product capabilities - v1.0 was a frontend UX and client integration cleanup.
- New information architecture from the visual mock beyond the explicit LLM move - the current nav model remains authoritative.
- Replacing Tailwind, Radix, or shadcn-style primitives - the current stack is adequate and now better standardized.
- Full frontend test-stack adoption - deferred to a future milestone because v1.0 used lint, build, and grep guardrails.

## Context

The frontend now has a stronger foundation for future work: semantic Tailwind tokens, shared status/confirmation/header/empty/skeleton primitives, one shell navigation model, one toast path, themed confirmation flows, `apiClient` enforcement for planned client calls, and scripts for color/plumbing guardrails.

Known deferred items:
- Standalone `npx tsc --noEmit` fails on TypeScript 6 deprecation diagnostics for `target=ES5` and `baseUrl`.
- Authenticated runtime keyboard and screen-reader checks need credentials or E2E fixtures.
- Visual regression coverage needs a screenshot harness.
- Dashboard spend still needs a reliable frontend cost source.

## Constraints

- **Stack:** Continue using Next.js App Router, React, Tailwind, Radix/shadcn-style primitives, lucide-react, and existing project utilities.
- **Theme system:** Preserve the `hsl(var(--x) / <alpha-value>)` Tailwind token pattern.
- **Routing:** Keep the existing nav model authoritative unless a future milestone explicitly changes IA.
- **Frontend UX:** Use shared primitives and guardrails documented in `CLAUDE.md`.
- **Verification:** Frontend UX changes should run `npm run check:colors`, `npm run check:plumbing`, `npm run lint`, and `npm run build` from `frontend/`.
- **Safety:** Do not read or commit `.env` secret values; do not revert unrelated dirty worktree changes.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use Slate Mono as the UX palette | It keeps the cyan identity while reducing the cyberpunk/neon feel. | Good - shipped in v1.0 |
| Treat the mock as visual-only | The mock's nav grouping and mobile behavior were intentionally not authoritative. | Good - avoided scope drift |
| Move LLM under Settings | LLM configuration is a settings concern and already has provider children beneath settings. | Good - shipped with redirects |
| Split status into solid and soft token pairs | Solid fills need AA text contrast; badges need subtle theme-aware tints. | Good - used by shared status UI |
| Use `StatusBadge` for severity and neutral `Badge` for categories | Status and category semantics should not be conflated. | Good - documented for future work |
| Use `apiClient` for client calls | Centralized auth/error behavior prevents drift. | Good - guardrail-backed |
| Add grep/script guardrails | The cleanup should fail fast if legacy patterns return. | Good - `check:colors` and `check:plumbing` pass |
| Keep spinners for inline busy states only | Page-level loads need structure, but action-level loading benefits from compact busy affordances. | Good - applied in Phase 7 |
| Use themed confirmations instead of native dialogs | Destructive actions need brand-consistent, accessible, consequence-aware confirmation. | Good - guardrail-backed |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each milestone:**
1. Move shipped requirements to Validated.
2. Update Current State and deferred items.
3. Review decisions and mark outcomes.
4. Define the next Active requirements when a new milestone starts.

---
*Last updated: 2026-07-01 after v1.0 milestone completion*
