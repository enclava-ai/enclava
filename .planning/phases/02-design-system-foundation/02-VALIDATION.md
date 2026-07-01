---
phase: 2
slug: design-system-foundation
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-01
---

# Phase 2 - Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | ESLint, TypeScript compiler, Next.js build, source greps |
| Config file | `frontend/eslint.config.mjs`, `frontend/tsconfig.json`, `frontend/next.config.js`, `frontend/tailwind.config.js` |
| Quick run command | `rg -n "success-soft|warning-soft|danger-soft|info-soft|<alpha-value>" frontend/src/app/globals.css frontend/tailwind.config.js` |
| Full suite command | `cd frontend && npm run lint && npx tsc --noEmit && npm run build` |
| Estimated runtime | ~180 seconds |

## Sampling Rate

- After token edits: run source grep for alpha-capable mappings and status tokens.
- After primitive edits: run `cd frontend && npm run lint`.
- Before phase verification: run lint, standalone `tsc`, build, and preview-route absence checks.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Automated Command | Status |
|---------|------|------|-------------|-------------------|--------|
| 2-01-01 | 01 | 1 | DS-01 | `rg -n "Slate Mono|--success-soft|--danger-soft" frontend/src/app/globals.css` | pending |
| 2-01-02 | 01 | 1 | DS-02, DS-04 | `rg -n "<alpha-value>|success.*soft|danger.*soft|empire|enclava" frontend/tailwind.config.js` | pending |
| 2-02-01 | 02 | 2 | DS-03 | `test -f frontend/src/components/ui/status-badge.tsx && test -f frontend/src/components/ui/confirm-dialog.tsx` | pending |
| 2-02-02 | 02 | 2 | DS-03 | `cd frontend && npm run lint` | pending |
| 2-03-01 | 03 | 3 | DS-01..DS-04 | `cd frontend && npm run build` | pending |

## Manual-Only Verifications

None required for this foundation phase. Visual follow-up happens through later phase UI review and consumer migration.

## Validation Sign-Off

- [x] All tasks have automated verify or existing infrastructure coverage.
- [x] No preview routes are required.
- [x] No watch-mode commands.
- [x] Feedback latency < 180s.
