# Phase 3 Pattern Map: App Shell and LLM IA

## Existing Patterns

- Client navigation logic uses `usePathname`, `useAuth`, `useModules`, and `usePlugin`.
- Route moves are App Router filesystem changes.
- Redirect stubs currently use `useRouter().replace()` in client pages.
- Existing UI primitives include `Dialog`, `DropdownMenu`, `ThemeToggle`, and `UserMenu`.

## Implementation Pattern

- Keep nav model logic in `components/ui/navigation.tsx`.
- Export/render a shell component that accepts `children` so `layout.tsx` can delegate shell structure without duplicating nav logic.
- Keep Settings children as explicit child items; update LLM href to `/settings/llm`.
- Use a route stub at `/llm` to preserve compatibility and query strings with `useSearchParams()`.

## Defer Boundaries

- Do not sweep non-shell colors.
- Do not consolidate toasts.
- Do not migrate raw client fetches.
