---
phase: 02-design-system-foundation
slug: design-system-foundation
status: approved
shadcn_initialized: true
preset: local-shadcn-style
created: 2026-07-01
---

# Phase 2 - UI Design Contract

> Visual and interaction contract for the design-system foundation. This phase creates reusable primitives and semantic tokens only; broad screen migration belongs to later phases.

## Design System

| Property | Value |
|----------|-------|
| Tool | shadcn-style local primitives |
| Preset | existing Enclava Tailwind/Radix stack |
| Component library | Radix UI primitives plus local `components/ui` wrappers |
| Icon library | lucide-react |
| Font | existing `--font-sans`, `--font-display`, and `--font-mono` variables |

## Spacing Scale

Declared values use Tailwind's 4px-based scale.

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Icon gaps, compact inline padding |
| sm | 8px | Small component gaps, badge internals |
| md | 16px | Default content spacing |
| lg | 24px | Card/header spacing |
| xl | 32px | Page section spacing |
| 2xl | 48px | Empty-state and skeleton vertical spacing |
| 3xl | 64px | Page-level spacing when needed |

Exceptions: none.

## Typography

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Body | 14px | 400 | 1.5 |
| Label | 12px | 600 | 1.25 |
| Heading | 24px | 700 | 1.2 |
| Display | 30px | 700 | 1.15 |

## Color

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | Slate Mono background/card tokens | Backgrounds and surfaces |
| Secondary (30%) | Muted/accent/border tokens | Cards, separators, controls |
| Accent (10%) | Cyan primary token | Primary actions, focus rings, selected state |
| Destructive | Danger/destructive solid pair | Destructive actions only |

Accent reserved for: primary action buttons, focus rings, active/select states, and sparse emphasis. Status chips must use soft status pairs, not primary.

## Copywriting Contract

| Element | Copy |
|---------|------|
| Primary CTA | Specific verb + noun, such as "Create key" or "Upload document" |
| Empty state heading | Short noun phrase, such as "No documents yet" |
| Empty state body | One sentence explaining why the state is empty and the next action |
| Error state | Problem plus recovery path |
| Destructive confirmation | Action-specific copy with optional required confirmation text |

## Component Contracts

| Component | Contract |
|-----------|----------|
| `StatusBadge` | Icon + text, soft status colors, `statusForValue()` domain mapping |
| `ConfirmDialog` | Declarative dialog plus `useConfirm()` provider/hook, destructive actions use solid danger tokens |
| `PageHeader` | Title, optional description, optional right-aligned actions |
| `EmptyState` | Optional icon, title, description, action, docs link |
| Skeletons | Composed `PageSkeleton`, `CardGridSkeleton`, and `TableSkeleton` wrappers |
| `Badge` | Existing variants preserved; semantic soft variants added |

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | local existing wrappers only | not required |
| third party | none | not applicable |

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS
- [x] Dimension 2 Visuals: PASS
- [x] Dimension 3 Color: PASS
- [x] Dimension 4 Typography: PASS
- [x] Dimension 5 Spacing: PASS
- [x] Dimension 6 Registry Safety: PASS

**Approval:** approved 2026-07-01
