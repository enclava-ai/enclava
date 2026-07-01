# Ingest Synthesis: Frontend UX Overhaul

**Synthesized:** 2026-07-01
**Mode:** bootstrap-with-existing-intel
**Docs ingested:** 1

## Summary

`design-proposal/IMPLEMENTATION_PLAN.md` defines a frontend UX milestone for Enclava. It is implementation-ready: it provides work packages, dependency waves, binding design decisions, verification requirements, and explicit exclusions. Existing `.planning/codebase/` intel confirms the plan fits the repository's stack and file layout.

Because `.planning/` existed only as codebase intelligence and did not contain `PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, or `STATE.md`, this ingest bootstraps the core GSD project artifacts instead of attempting a merge into absent milestone files.

## Scope To Carry Forward

- UX visual system migration to Slate Mono semantic tokens.
- Shared UI primitives that unblock all downstream UX work.
- Desktop sidebar and mobile drawer navigation.
- LLM route move under Settings with compatibility redirects.
- Full frontend color literal and legacy palette cleanup.
- Dashboard IA rework.
- SPA navigation and client API-client cleanup.
- Toast and confirmation UX consolidation.
- Loading, empty, accessibility, and guardrail improvements.

## Requirements Created

Requirements are grouped into:

- Cleanup and route hygiene.
- Design system.
- Navigation and information architecture.
- Color migration and dashboard.
- Client plumbing.
- Feedback and confirmation UX.
- Loading and empty states.
- Accessibility and guardrails.

## Phase Strategy

The roadmap preserves the proposal's sequencing while collapsing work packages into executable GSD phases:

- Phase 1 maps to WP-D.
- Phase 2 maps to WP0 and WP1.
- Phase 3 maps to WP2.
- Phase 4 maps to WP3 and color guardrails/WP0-cleanup.
- Phase 5 maps to WP4 and fetch/navigation guardrails.
- Phase 6 maps to WP5 and WP6.
- Phase 7 maps to WP7, WP8, WP9, and final guardrail verification.

## Conflict Outcome

No blockers were detected. No warnings were detected. The only notable routing condition is that `.planning/` existed without core project files; this was handled as a bootstrap from existing codebase intel rather than a merge.
