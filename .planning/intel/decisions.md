# Ingested Decisions

**Source:** `design-proposal/IMPLEMENTATION_PLAN.md`
**Synthesized:** 2026-07-01

## Locked For This Milestone

- Use the Slate Mono palette as the frontend visual direction.
- Preserve the existing shadcn-style token architecture and extend it with semantic status tokens rather than replacing the styling stack.
- Split status roles into solid and soft token pairs. Solid pairs are for filled actions such as destructive buttons; soft pairs are for badges and subtle tints.
- Preserve existing `--chart-*` and `--font-*` CSS variables while editing color tokens.
- Keep the legacy `empire` and `enclava` Tailwind/CSS definitions only until color sweep phases report zero usages, then remove them.
- Build shared primitives before consumers: `StatusBadge`, `ConfirmDialog`, `PageHeader`, `EmptyState`, and composed skeleton loaders.
- Treat `StatusBadge` as the canonical severity indicator and keep category labels visually neutral.
- Delete deprecated frontend routes before sweeping colors.
- Move LLM under Settings at `/settings/llm`; preserve `/llm` as a query-preserving compatibility redirect.
- Repoint existing inbound redirects to `/settings/llm?...` rather than double-hopping through `/llm`.
- Use the current navigation model as authoritative; use the visual mock only for styling.
- Desktop navigation becomes a left sidebar; mobile navigation must use a working drawer.
- Replace raw client fetches with `apiClient`; exclude server route handlers and documentation examples.
- Replace native browser confirms/alerts with themed confirmation dialogs and toasts.
- Consolidate toast usage to the existing shadcn-style `@/hooks/use-toast` system.
- Add guardrails so hardcoded color classes, legacy palette names, native dialogs, and disallowed client fetches do not return.

## Flexible During Implementation

- Exact dashboard chart implementation may follow available data and current component patterns as long as the proposed IA is preserved.
- The exact visual treatment of skeletons and empty states can use local UI conventions if they satisfy the stated UX requirements.
- Guardrails may combine ESLint and script-based checks, with CI grep acting as the authoritative backstop.
- Phase-level plan split can be adjusted by downstream planning as long as dependency order remains intact.
