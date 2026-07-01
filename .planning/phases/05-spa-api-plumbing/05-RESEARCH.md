# Phase 5 Research: SPA Navigation and API Client Plumbing

**Gathered:** 2026-07-01

## Source References

- `design-proposal/IMPLEMENTATION_PLAN.md` WP4 and WP10 define routing, API client, and guardrail cleanup.
- `.planning/phases/05-spa-api-plumbing/05-CONTEXT.md` defines phase boundaries and exceptions.
- `.planning/codebase/ARCHITECTURE.md` and `.planning/codebase/CONVENTIONS.md` establish `apiClient` as the browser API boundary.
- Phase 4 added `frontend/scripts/check-no-hardcoded-colors.sh`, establishing `frontend/scripts/` as the guardrail location.

## Baseline Findings

Navigation scan found:

- Internal full-page redirect after login: `frontend/src/app/login/page.tsx`.
- Query cleanup using `window.location.href` in `frontend/src/app/admin/connectors/page.tsx`, despite already having `useSearchParams`.
- Active plugin path detection using `window.location.pathname` in `frontend/src/components/plugins/PluginNavigation.tsx`.
- External OAuth redirect in `frontend/src/components/connectors/AddConnectorDialog.tsx`; this should remain a full-page provider redirect and become a documented guardrail exception.
- Multiple `window.location.origin` usages for example URLs, callback URLs, host derivation, and file-download helpers; these are not internal navigation.

Client fetch scan found:

- Real client component calls in `frontend/src/components/settings/ConfidentialityDashboard.tsx`, `frontend/src/components/ui/user-menu.tsx`, and `frontend/src/components/admin/UserManagement.tsx`.
- Documentation/sample code in `frontend/src/components/extract/IntegrationGuide.tsx`.
- Route-handler fetches under `frontend/src/app/api/**`.
- Helper/internal fetches in `frontend/src/lib/api-client.ts`, `frontend/src/lib/token-manager.ts`, `frontend/src/lib/url-utils.ts`, `frontend/src/lib/file-download.ts`, and `frontend/src/lib/proxy-auth.ts`.

Native dialog scan found existing `confirm()` usage in admin, budgets, connectors, plugin manager, and user-management surfaces. Replacement belongs to Phase 6, but Phase 5 guardrail work should leave an obvious path for Phase 6 enforcement.

## Risks

- Replacing the login full reload must not race auth state propagation. Use `router.replace("/dashboard")` after `login()` resolves and keep the existing short delay if needed.
- OAuth provider redirects are intentionally external and should not be converted to Next router navigation.
- `apiClient` imports `token-manager`; token refresh fetches must remain outside `apiClient` to avoid circular behavior.
- File downloads and sample snippets may need fetch-specific behavior that `apiClient` does not provide.

## Planning Implications

- Split navigation cleanup from fetch/guardrail cleanup to keep behavior changes reviewable.
- Add `apiClient.patch` before converting client code that already expects PATCH semantics.
- Guardrails should scan UI/client source and exclude route handlers, API client internals, token refresh internals, file-download helpers, proxy helpers, and documented samples.

---
*Phase: 05-spa-api-plumbing*
