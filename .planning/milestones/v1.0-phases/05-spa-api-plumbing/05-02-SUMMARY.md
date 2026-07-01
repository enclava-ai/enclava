---
phase: 05-spa-api-plumbing
plan: "02"
subsystem: frontend-api-plumbing
tags: [api-client, fetch, guardrails, routing]

requires:
  - phase: 05-spa-api-plumbing
    provides: SPA navigation cleanup
provides:
  - `apiClient.patch`
  - Client fetch conversion for confidentiality, user menu, and user management surfaces
  - Client plumbing guardrail script
affects: [api-client, settings-ui, user-menu, admin-users, frontend-guardrails]

tech-stack:
  added: []
  patterns:
    - `apiClient` for real client-component JSON calls
    - shell guardrail with route/helper/sample exceptions

key-files:
  created:
    - frontend/scripts/check-client-plumbing.sh
  modified:
    - frontend/package.json
    - frontend/src/lib/api-client.ts
    - frontend/src/components/settings/ConfidentialityDashboard.tsx
    - frontend/src/components/ui/user-menu.tsx
    - frontend/src/components/admin/UserManagement.tsx

key-decisions:
  - "Kept route-handler fetches, API client internals, token refresh, file downloads, proxy helpers, and integration samples as explicit guardrail exceptions."
  - "Added an opt-in native-dialog scan for Phase 6 without failing Phase 5 on confirmation flows Phase 6 owns."

patterns-established:
  - "Use `cd frontend && npm run check:plumbing` to catch internal browser navigation and raw client fetch regressions."

requirements-completed: [PLUMB-02, PLUMB-03, GUARD-02]

duration: 4 min
completed: 2026-07-01
---

# Phase 5 Plan 02: API Client and Plumbing Guardrail Summary

**Real client-component JSON calls in the planned surfaces now use `apiClient`, and the frontend has a plumbing guardrail for future regressions.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-07-01T14:39:00Z
- **Completed:** 2026-07-01T14:43:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added `apiClient.patch` for existing PATCH call sites.
- Converted confidentiality report, password change, and admin user-management fetches to `apiClient`.
- Removed duplicated token/header handling from converted client components.
- Added `frontend/scripts/check-client-plumbing.sh` and `npm run check:plumbing`.
- Verified guardrail failure samples for internal browser navigation and raw client fetch usage.
- Added opt-in native dialog detection for Phase 6 follow-up.

## Verification

- `cd frontend && npm run check:plumbing` exited 0.
- Navigation scan for internal browser navigation patterns returned no matches.
- Client fetch scan with documented route/helper/sample exceptions returned no matches.
- Temporary `window.location.href = "/dashboard"` sample was detected by the guardrail.
- Temporary `fetch("/api/example")` sample was detected by the guardrail.
- Opt-in native dialog scan reports the existing Phase 6-owned dialogs.
- `cd frontend && npm run lint` exited 0.
- `cd frontend && npm run build` exited 0.
- `cd frontend && npx tsc --noEmit` still fails only on known TypeScript 6 config deprecations for `target=ES5` and `baseUrl`.

## Deviations from Plan

None.

## Issues Encountered

- Build still prints the existing `NEXT_PUBLIC_BASE_URL not set in production - URLs may be incorrect` warning.
- Standalone TypeScript still reports TS5107 and TS5101 deprecations from the existing TypeScript 6 configuration.

## User Setup Required

None.

## Next Phase Readiness

Ready for Phase 5 code review and verification before Phase 6.

---
*Phase: 05-spa-api-plumbing*
*Completed: 2026-07-01*
