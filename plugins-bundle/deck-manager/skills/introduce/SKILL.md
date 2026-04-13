---
name: introduce
description: Introduce the deck-manager plugin and its capabilities
type: user-invocable
---

# Introduce Deck Manager

The **deck-manager** plugin covers the full presentation deck lifecycle in `earlbear-clis/deck-cli/` — from generating content YAML to rendering via four tools, reviewing visual quality, and publishing to earlbear-sites.

## Skills

| Skill | Invoke | Purpose |
|---|---|---|
| `generate-deck` | `/deck-manager:generate-deck` | Interactively gather requirements, generate content YAML, and render a deck via Marp, Slidev, python-pptx, or Figma Slides |
| `add-deck` | `/deck-manager:add-deck` | Scaffold a new deck type — create the content YAML, build all brand permutations, generate the HTML gallery, and publish to earlbear-sites |
| `review-slides` | `/deck-manager:review-slides` | Convert PPTX to PNGs and run a checklist-driven visual quality review; report critical issues with specific fix recommendations |
| `slide-design-review` | `/deck-manager:slide-design-review` | Principal-designer review using golden-ratio dimension analysis — evaluate hierarchy, typography scale, spacing, and brand cohesion; map fixes to renderer code |
| `run-figma-plugin` | `/deck-manager:run-figma-plugin` | Open Figma Desktop, launch the Earlbear Deck Generator plugin, and guide clipboard-based YAML input to generate slides |
| `setup-figma-plugin` | `/deck-manager:setup-figma-plugin` | One-time setup: build the plugin, import the manifest into Figma, and verify with a first-run test |

## Prerequisites

`ebdeck` must be on your PATH. Add `earlbear-clis/deck-cli/bin` to your PATH or symlink `deck-cli/bin/ebdeck` into `~/bin`. First run auto-bootstraps a venv (~10s).

## Typical flow

1. `/deck-manager:generate-deck` — pick tool, gather content, render
2. `/deck-manager:review-slides` or `/deck-manager:slide-design-review` — quality check
3. `/deck-manager:add-deck` — publish to earlbear-sites via `ebdeck publish`
