# Phase 4 Validation

## Per-Plan Gates

Each sweep plan must run:

- `cd frontend && npm run lint`
- a scoped color grep for its owned paths
- source checks for expected `StatusBadge` or semantic-token replacements where status UI was touched

## Root Color Pattern

Use this root scan to reconcile remaining work:

```bash
rg -n "empire-|enclava-|#[0-9A-Fa-f]{3,8}|\\b(red|green|blue|yellow|orange|purple|pink|indigo|cyan|teal|emerald|amber|slate|gray|zinc|neutral|stone|rose|violet|sky|lime)-[0-9]{2,3}\\b" frontend/src --glob '*.{ts,tsx,css}'
```

During plans 04-01 through 04-04, remaining hits outside the current ownership bucket are expected.

## Final Gates

Plan 04-05 must run:

- root color scan over `frontend/src`
- guardrail script over `frontend/src`
- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `cd frontend && npx tsc --noEmit` and document the known TypeScript 6 config limitation if still present

## Expected Known Limitation

Standalone TypeScript currently reports TypeScript 6 deprecations for `target=ES5` and `baseUrl`. Phase 4 should not silently change compiler behavior unless required by the guardrail implementation.

---
*Phase: 04-color-sweep*
