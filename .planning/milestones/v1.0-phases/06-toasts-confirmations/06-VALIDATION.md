# Phase 6 Validation

## Per-Plan Gates

Plan 06-01 must run:

- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- provider/import scans for `react-hot-toast` and `sonner`

Plan 06-02 must run:

- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `cd frontend && npm run check:plumbing`
- native dialog scan returns no matches

## Toast Scans

```bash
rg -n "react-hot-toast|sonner|HotToaster|Sonner|toast\\.(success|error)" frontend/src frontend/package.json frontend/package-lock.json
```

Expected after 06-01: no matches.

## Native Dialog Scan

```bash
rg -n "\\b(window\\.)?(confirm|alert|prompt)\\s*\\(" frontend/src --glob '*.{ts,tsx}'
```

Expected after 06-02: no matches.

## Known Limitation

Standalone TypeScript currently reports TypeScript 6 deprecations for `target=ES5` and `baseUrl`. Phase 6 should document this if it remains unchanged.

---
*Phase: 06-toasts-confirmations*
