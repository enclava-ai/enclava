---
phase: 03-app-shell-navigation
slug: app-shell-navigation
status: approved
shadcn_initialized: true
preset: local-shadcn-style
created: 2026-07-01
---

# Phase 3 - UI Design Contract

## Design System

| Property | Value |
|----------|-------|
| Tool | local shadcn-style primitives |
| Preset | Slate Mono shell |
| Component library | Radix Dialog/Dropdown via local wrappers |
| Icon library | lucide-react |
| Font | existing Enclava font variables |

## Shell Contract

- Desktop authenticated users get a persistent left sidebar at `lg` and above.
- Mobile/tablet users get a topbar with a menu button that opens a left drawer.
- The drawer and desktop sidebar render the same nav model.
- Topbar keeps page title/breadcrumb context, theme toggle, and user menu.
- The product shell must not wrap unauthenticated marketing/login/register routes in an oversized sidebar.

## Spacing Scale

| Token | Value | Usage |
|-------|-------|-------|
| sm | 8px | Nav item gaps, icon gaps |
| md | 16px | Sidebar padding, topbar horizontal padding |
| lg | 24px | Main page padding |
| xl | 32px | Desktop content gap |

Exceptions: none.

## Typography

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Nav label | 14px | 500 | 1.25 |
| Section label | 11px | 600 | 1.25 |
| Topbar title | 16px | 600 | 1.25 |
| Brand | 15px | 700 | 1.2 |

## Color

| Role | Value | Usage |
|------|-------|-------|
| Shell surface | `bg-card` | Sidebar and topbar |
| Divider | `border-border` | Shell borders |
| Active nav | `bg-accent-soft text-primary` | Active item |
| Muted nav | `text-muted-foreground` | Inactive item |

Accent reserved for: active nav state, focus ring, and compact brand mark.

## Copywriting Contract

| Element | Copy |
|---------|------|
| Mobile drawer trigger | `Open navigation` accessible label |
| Drawer title | `Navigation` |
| Settings child | `LLM` under Settings |
| Compatibility route | no visible copy; immediate redirect |

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS
- [x] Dimension 2 Visuals: PASS
- [x] Dimension 3 Color: PASS
- [x] Dimension 4 Typography: PASS
- [x] Dimension 5 Spacing: PASS
- [x] Dimension 6 Registry Safety: PASS

**Approval:** approved 2026-07-01
