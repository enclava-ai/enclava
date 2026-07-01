# Document Classification: design-proposal/IMPLEMENTATION_PLAN.md

**Classified:** 2026-07-01
**Source:** `design-proposal/IMPLEMENTATION_PLAN.md`
**Type:** SPEC
**Precedence:** SPEC
**Mode:** bootstrap-with-existing-intel

## Classification Rationale

The document is an implementation specification for a frontend UX milestone. It contains binding design and information architecture decisions, explicit work packages, dependency waves, files to edit, definitions of done, and verification expectations. It references `design-proposal/PROPOSAL.md` and `design-proposal/palette-explorer.html` as supporting context.

## Extracted Scope

- Replace the ad-hoc Enclava frontend visual system with a Slate Mono semantic token layer.
- Add shared UX primitives for status, confirmation, page headers, empty states, and skeletons.
- Remove deprecated/dev-only routes before styling sweeps touch dead code.
- Move LLM IA under Settings with compatibility redirects from `/llm`.
- Replace the top-bar navigation with a desktop sidebar and mobile drawer while preserving the current nav model.
- Sweep `empire-*` and raw Tailwind palette utilities from the frontend.
- Rework dashboard IA around privacy trust, spend, request volume, reliability, attention items, and developer connection details.
- Replace raw client `fetch`, internal `window.location`, and internal `window.open` usages with project-native helpers.
- Consolidate toast providers and replace native browser dialogs.
- Improve loading states, empty states, accessibility, and CI/editor guardrails.

## Binding Decisions

- Visual direction is Slate Mono: neutral-first surfaces with cyan as a quiet accent.
- `design-proposal/palette-explorer.html` is visual reference only, not an IA or behavior source of truth.
- `frontend/src/components/ui/navigation.tsx` remains the authoritative source for nav grouping until WP2 extracts it into shared shell components.
- LLM route moves from `/llm` to `/settings/llm`; `/llm` remains as a query-preserving compatibility redirect.
- Deprecated routes `app/chatbot`, `app/zammad`, `app/debug`, `app/test-auth`, and `app/rag-demo` must be deleted before color sweeps.
- Status severity and entity category are distinct: severity uses `StatusBadge`; categories use neutral outline badges.
- Client-side components must not introduce raw `fetch` calls; use `apiClient`.
- Internal app navigation must use Next routing primitives rather than `window.location` or `window.open`.

## Work Package Map

- WP-D: Deprecated route cleanup.
- WP0: Design tokens and Tailwind status vocabulary.
- WP1: Shared UI primitives.
- WP2: App shell, mobile drawer, and LLM route move.
- WP3a-WP3e: Color-literal sweep by directory, including dashboard rework.
- WP4: SPA navigation and client fetch fixes.
- WP5: Toast consolidation.
- WP6: Confirm dialogs.
- WP7: Loading skeletons.
- WP8: Empty states.
- WP9: Accessibility pass.
- WP10: Guardrails.

## Related Existing Intel

- `.planning/codebase/STACK.md` confirms Next.js, React, Tailwind, Radix UI, lucide-react, and npm as the relevant frontend stack.
- `.planning/codebase/ARCHITECTURE.md` confirms frontend providers, shared components, and `apiClient` boundaries.
- `.planning/codebase/STRUCTURE.md` confirms frontend file locations named by the plan.
- `.planning/codebase/CONVENTIONS.md` confirms Tailwind class usage, `cn`, `@/lib/api-client`, and frontend lint conventions.
- `.planning/codebase/TESTING.md` confirms frontend linting is available but no full frontend test runner is configured.
