---
sketch: 001
name: workflow-ux-options
question: "Should workflows feel like an operations console, a step builder, or a schedule board?"
winner: null
tags: [workflows, automation, scheduling, agents]
---

# Sketch 001: Workflow UX Options

## Design Question

Should workflows in Enclava be centered around operations monitoring, authoring a step sequence, or managing scheduled automations?

## How to View

Open `.planning/sketches/001-workflow-ux-options/index.html` in a browser.

## Variants

- **A: Operations Console** - workflows as running automations with status, next run, run history, and incident-style detail.
- **B: Step Builder** - workflows as a readable trigger-plus-steps composition surface with a properties panel.
- **C: Schedule Board** - workflows as recurring jobs and event triggers with calendar/queue emphasis.

## What to Look For

- Whether the first screen answers "what is running, what failed, and what happens next."
- Whether building/editing feels clear without becoming an n8n-style canvas.
- Whether schedules feel first-class enough for nightly agent/RAG use cases.
