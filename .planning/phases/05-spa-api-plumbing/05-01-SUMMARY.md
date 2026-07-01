---
phase: 05-spa-api-plumbing
plan: "01"
subsystem: frontend-routing
tags: [navigation, app-router, spa]

requires:
  - phase: 04-color-sweep
    provides: Completed frontend color sweep and app shell
provides:
  - Internal login redirect via App Router
  - Connector OAuth callback query cleanup via App Router
  - Plugin active path detection via `usePathname`
affects: [auth-ui, connectors-ui, plugins-ui]

tech-stack:
  added: []
  patterns:
    - `router.replace()` for imperative internal route replacement
    - `usePathname()` for active route state

key-files:
  created: []
  modified:
    - frontend/src/app/login/page.tsx
    - frontend/src/app/admin/connectors/page.tsx
    - frontend/src/components/plugins/PluginNavigation.tsx

key-decisions:
  - "Kept OAuth provider authorization as an intentional external browser redirect."
  - "Used App Router query replacement for connector callback cleanup rather than direct history mutation."

patterns-established:
  - "Internal product navigation should use App Router primitives; external provider redirects remain browser-level redirects."

requirements-completed: [PLUMB-01]

duration: 3 min
completed: 2026-07-01
---

# Phase 5 Plan 01: SPA Navigation Summary

**Internal product navigation no longer uses full-page browser redirects in the scoped Phase 5 navigation paths.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-07-01T14:36:00Z
- **Completed:** 2026-07-01T14:39:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Replaced login success `window.location.href = "/dashboard"` with `router.replace("/dashboard")`.
- Replaced connector OAuth callback query cleanup with `router.replace()` and `useSearchParams()`.
- Replaced plugin active path reads from `window.location.pathname` with `usePathname()`.
- Preserved the connector OAuth provider redirect as an external full-page redirect.

## Verification

- Navigation scan for internal `window.location.href`, `location.assign/replace`, and `window.open` route patterns returned no matches.
- `cd frontend && npm run lint` exited 0.
- `cd frontend && npm run build` exited 0.

## Deviations from Plan

None.

## Issues Encountered

- Build still prints the existing `NEXT_PUBLIC_BASE_URL not set in production - URLs may be incorrect` warning.

## User Setup Required

None.

## Next Phase Readiness

Ready for Plan 05-02 client fetch conversion and plumbing guardrails.

---
*Phase: 05-spa-api-plumbing*
*Completed: 2026-07-01*
