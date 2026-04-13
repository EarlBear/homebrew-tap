---
name: introduce
description: Entry point for the EarlBear plugin marketplace — lists all plugins with descriptions, repos, and invoke patterns
type: user-invocable
---

# EarlBear Plugin Marketplace

This is the entry point for the EarlBear plugin marketplace. Each plugin encapsulates a domain of the EarlBear platform. Install all plugins with `make install` from the marketplace root, then invoke any skill using the `/<plugin-name>:<skill-name>` pattern.

## All Plugins

| Plugin | Description | Repo(s) |
|--------|-------------|---------|
| `deck-manager` | Generate, review, and publish presentation decks using Marp, Slidev, python-pptx, and Figma Slides | `earlbear-clis` |
| `wireframe-manager` | Build, review, and QA the 12-theme EarlBear landing page wireframes | `earlbear-sites` |
| `artifact-manager` | Import Claude artifacts from share URLs and publish the encrypted site catalog to GitHub Pages | `earlbear-sites` |
| `jira-manager` | Jira backlog management — add items, conform the board, manage manifests, and set up the EARL project | `earlbear-clis`, `earlbear` |
| `shopify-manager` | Shopify storefront management — products, customers, inventory, themes, and declarative store conformance | `earlbear` |
| `cloud-agent-manager` | Cloud agent operations — manage, run, debug, and extend Watson (Earl), the EarlBear autonomous Claude Code agent | `earlbear` |
| `earlbear-docs-manager` | Decision docs and CLI leverage — capture use cases, write living docs, and get the most from the EarlBear CLIs | `earlbear-clis`, `earlbear` |
| `discover-earlbear-plugins` | This plugin — the entry point for the EarlBear plugin marketplace | all repos |

## Invoke Pattern

Each plugin exposes an `introduce` skill that lists its capabilities. Use:

```
/deck-manager:introduce
/wireframe-manager:introduce
/artifact-manager:introduce
/jira-manager:introduce
/shopify-manager:introduce
/cloud-agent-manager:introduce
/earlbear-docs-manager:introduce
/discover-earlbear-plugins:introduce
```

## Installation

From the marketplace root:

```bash
make install
```

This installs all plugins into the Claude Code configuration for the current repo.
