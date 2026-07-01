# Phase 5 Validation

## Per-Plan Gates

Plan 05-01 must run:

- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- navigation grep for disallowed internal full reload/new-tab patterns

Plan 05-02 must run:

- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `cd frontend && npm run check:plumbing`
- client fetch grep with documented exceptions

## Navigation Scan

```bash
rg -n "window\\.location\\.href\\s*=\\s*['\"]\\/|location\\.(assign|replace)\\(\\s*['\"]\\/|window\\.open\\(\\s*['\"]\\/" frontend/src --glob '*.{ts,tsx}'
```

Expected result after 05-01: no matches.

## Client Fetch Scan

The guardrail should fail on real client-component `fetch(` calls but exempt:

- `frontend/src/app/api/**`
- `frontend/src/lib/api-client.ts`
- `frontend/src/lib/token-manager.ts`
- `frontend/src/lib/proxy-auth.ts`
- `frontend/src/lib/file-download.ts`
- `frontend/src/lib/url-utils.ts`
- `frontend/src/components/extract/IntegrationGuide.tsx` sample snippets

## Known Limitation

Standalone TypeScript currently reports TypeScript 6 deprecations for `target=ES5` and `baseUrl`. Phase 5 should document this if it remains unchanged.

---
*Phase: 05-spa-api-plumbing*
