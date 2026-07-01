# Phase 4 Research: Color Sweep and Dashboard

**Gathered:** 2026-07-01

## Source References

- `design-proposal/IMPLEMENTATION_PLAN.md` WP3 defines the sweep split and mapping table.
- `design-proposal/PROPOSAL.md` defines the dashboard IA and hardcoded-color problem statement.
- Phase 2 provides semantic tokens, `StatusBadge`, and Badge variants.
- Phase 3 owns `frontend/src/components/ui/navigation.tsx` and `frontend/src/app/layout.tsx`; Phase 4 should not refactor shell ownership.

## Baseline Findings

Root grep shows remaining hits across:

- Admin/audit/API-key surfaces: `app/admin/**`, `components/admin/**`, `app/audit/**`, `app/dashboard/api-keys/[id]/stats/page.tsx`.
- RAG/Extract surfaces: `app/rag/page.tsx`, `components/rag/**`, `components/extract/**`.
- Dashboard/settings/playground surfaces: `app/dashboard/page.tsx`, `app/analytics/page.tsx`, `app/budgets/page.tsx`, `app/settings/page.tsx`, `components/settings/**`, `components/playground/**`.
- Agents/LLM/connectors/plugins/auth/catch-all: `components/agent/**`, `components/llm/**`, `components/connectors/**`, `components/plugins/**`, `app/login`, `app/register`, `app/page.tsx`, `components/auth/**`, `components/chat/**`, selected `components/ui/**`.
- Final cleanup targets: `frontend/tailwind.config.js`, `frontend/src/app/globals.css`, and a new guardrail script.

## Mapping Table

| Existing usage | Replacement |
|----------------|-------------|
| `text-empire-gold` as body text | `text-foreground` |
| `text-empire-gold/60`, `/80` | `text-muted-foreground` |
| `text-empire-gold` as accent/icon | `text-primary` |
| `bg-empire-darker/50`, `bg-empire-dark/50` | `bg-card` or `bg-muted` based on hierarchy |
| `border-empire-gold/20` | `border-border` or `border-primary/20` |
| `bg-empire-gold` button | standard Button or `bg-primary text-primary-foreground` |
| red/green/yellow/blue status badges | `StatusBadge` or semantic soft status tokens |
| category colors | neutral outline `Badge` |
| hardcoded skeleton grays | `Skeleton`/`bg-muted` |

## Ownership Decisions

- Plan 04-01 owns `frontend/src/app/dashboard/api-keys/[id]/stats/page.tsx`; Plan 04-03 must exclude it.
- Plan 04-04 owns `frontend/src/app/settings/llm/**`; Plan 04-03 must exclude moved LLM settings files.
- Plan 04-05 owns deletion of legacy palette definitions only after 04-01 through 04-04 pass their greps.
- API route strings such as `enclava-backend` are not palette classes and must not become false positives in the final guardrail.

## Risks

- Large mechanical sweeps can accidentally change domain semantics. Status severity and entity category mappings must stay distinct.
- Dashboard changes are structural, so they need build/lint verification beyond grep cleanup.
- Final guardrails need careful exclusions so they catch UI color regressions without flagging server proxy URLs.

---
*Phase: 04-color-sweep*
