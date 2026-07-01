# Phase 5 Code Review

**Reviewed:** 2026-07-01  
**Scope:** SPA navigation cleanup, client fetch conversion, `apiClient.patch`, and plumbing guardrail.

## Findings

No open blocking findings.

## Review Notes

- Login success now uses `router.replace("/dashboard")` instead of assigning `window.location.href`.
- Connector OAuth callback query cleanup uses App Router replacement and preserves the intentional external OAuth provider redirect.
- Plugin active path state uses `usePathname()` instead of reading `window.location.pathname`.
- `UserMenu`, `UserManagement`, and `ConfidentialityDashboard` planned client fetches now use `apiClient`.
- `apiClient.patch` supports existing connector PATCH call sites.
- `check-client-plumbing.sh` fails on internal browser navigation and raw client fetch regressions while excluding route handlers, API-client internals, token refresh, file downloads, proxy helpers, and integration samples.

## Residual Risk

- `ConfidentialityDashboard` already referenced `/api/v1/tee/confidentiality-report`, but no matching backend/frontend route was found in a narrowed search. Phase 5 centralized the call through `apiClient`; it did not establish that endpoint.
- Native `confirm()` dialogs still exist and are explicitly owned by Phase 6. The new guardrail can detect them with `--include-dialogs`, but the default Phase 5 check does not fail on them yet.
- Standalone `npx tsc --noEmit` remains blocked by existing TypeScript 6 deprecation diagnostics in `frontend/tsconfig.json`.

## Verification Reviewed

- `cd frontend && npm run check:plumbing` exited 0.
- Independent internal navigation scan returned no matches.
- Independent client fetch scan with documented exceptions returned no matches.
- Temporary internal `window.location.href = "/dashboard"` sample was detected.
- Temporary client `fetch("/api/example")` sample was detected.
- `cd frontend && npm run lint` exited 0.
- `cd frontend && npm run build` exited 0.
- `cd frontend && npx tsc --noEmit` reported only the known `target=ES5` and `baseUrl` deprecation diagnostics.

---
*Phase: 05-spa-api-plumbing*
*Review type: code*
