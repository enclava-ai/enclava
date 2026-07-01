---
phase: 1
slug: delete-deprecated-routes
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-01
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | ESLint, TypeScript compiler, Next.js build |
| **Config file** | `frontend/eslint.config.mjs`, `frontend/tsconfig.json`, `frontend/next.config.js` |
| **Quick run command** | `rg -n "chatbot|zammad|/debug|test-auth|rag-demo" frontend/src` |
| **Full suite command** | `cd frontend && npm run lint && npx tsc --noEmit && npm run build` |
| **Estimated runtime** | ~180 seconds |

---

## Sampling Rate

- **After every task commit:** Run `rg -n "chatbot|zammad|/debug|test-auth|rag-demo" frontend/src` and targeted `test ! -e` checks for deleted routes.
- **After every plan wave:** Run `cd frontend && npm run lint`.
- **Before `$gsd-verify-work`:** Run `cd frontend && npm run lint && npx tsc --noEmit && npm run build`.
- **Max feedback latency:** 180 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | CLN-01 | T1-01 | Only deprecated frontend route files are deleted | source | `git ls-files frontend/src/app/debug/page.tsx frontend/src/app/rag-demo/page.tsx frontend/src/app/test-auth/page.tsx` | ✅ | ⬜ pending |
| 1-01-02 | 01 | 1 | CLN-01 | T1-02 | Sole-use demo proxies removed without backend connector deletion | source | `test ! -e frontend/src/app/api/rag/debug` | ✅ | ⬜ pending |
| 1-02-01 | 02 | 2 | CLN-02 | T2-01 | No live frontend route/link/import references remain | source | `rg -n "chatbot|zammad|/debug|test-auth|rag-demo" frontend/src` | ✅ | ⬜ pending |
| 1-02-02 | 02 | 2 | CLN-03 | T2-02 | Frontend import graph and build remain valid | build | `cd frontend && npm run lint && npx tsc --noEmit && npm run build` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have automated verify or existing infrastructure coverage.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency < 180s.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-07-01
