# Phase 5 Patterns

## Internal Navigation

- Use `router.push()` or `router.replace()` for imperative internal route changes.
- Use `Link` for rendered internal links.
- Use `usePathname()` for active route detection instead of reading `window.location.pathname`.
- Use `useSearchParams()` plus `router.replace()` for query cleanup after local callbacks.
- Keep `window.location.assign()` or `window.location.href` only for external provider redirects, such as OAuth authorization URLs.

## API Client

- Use `apiClient.get/post/put/patch/delete` for real browser calls to JSON backend/proxy endpoints.
- Let `apiClient` attach auth headers; do not duplicate token/header setup at call sites.
- Preserve route-handler `fetch()` calls under `frontend/src/app/api/**`.
- Preserve `apiClient` implementation fetches, token refresh internals, file download helpers, proxy helpers, and documentation/sample snippets.
- Add small helper methods to `apiClient` only when they remove duplicated call-site behavior.

## Guardrails

- Reuse `frontend/scripts/` for shell guardrails and expose them through `frontend/package.json`.
- Navigation guardrail should fail on internal `window.location.href = "/..."`, `location.assign("/...")`, and `window.open("/...")` patterns.
- Fetch guardrail should fail on client-component `fetch(` usage outside documented exception paths.
- Native dialog guardrail should be present or planned for Phase 6, but Phase 5 must not block on existing dialogs that Phase 6 explicitly owns.

## Verification

- Run `cd frontend && npm run lint`.
- Run `cd frontend && npm run build`.
- Run relevant guardrail scripts after each plan.
- Run `cd frontend && npx tsc --noEmit` at phase close and document the known TypeScript 6 config limitation if unchanged.

---
*Phase: 05-spa-api-plumbing*
