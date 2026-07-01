# Ingested Constraints

**Source:** `design-proposal/IMPLEMENTATION_PLAN.md`
**Synthesized:** 2026-07-01

## Technical Constraints

- Frontend implementation must stay within Next.js App Router, React, Tailwind, Radix/shadcn-style primitives, and existing project utilities.
- Tailwind colors must preserve the `hsl(var(--x) / <alpha-value>)` pattern so opacity modifiers work.
- Existing frontend code should use `@/lib/api-client` for browser API calls.
- Frontend linting is the primary configured quality gate; no full frontend test runner is currently configured.
- `app/api/**/route.ts` server proxies are not client fetch violations.
- Documentation code samples containing `fetch` should remain examples and can be marked with `// api-sample`.

## Sequencing Constraints

- Deprecated route deletion precedes the color sweep.
- Token and primitive work precedes shell, sweep, and consumer-facing UX work.
- Shell/navigation work owns nav files and `app/layout.tsx`.
- WP3 sweep agents must not edit shell files owned by WP2.
- Legacy palette cleanup happens only after WP3a-WP3e report a zero root grep.
- Accessibility should run late enough to audit the output of earlier phases.

## Scope Boundaries

- The visual mock is not an implementation source for nav labels, grouping, or responsive behavior.
- This milestone does not add new backend product capabilities.
- This milestone does not replace the whole component library.
- This milestone does not introduce a new frontend testing stack unless downstream planning explicitly chooses to do so for guardrail validation.
