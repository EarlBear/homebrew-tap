---
name: introduce
description: Introduce the shopify-manager plugin and its capabilities
type: user-invocable
---

# Introduce Shopify Manager

The **shopify-manager** plugin covers the full EarlBear Shopify storefront lifecycle in the `earlbear` repo — from seeding test data and declarative store conformance to ad-hoc product management and theme customization, all via the `ebshop` CLI.

## Skills

| Skill | Invoke | Purpose |
|---|---|---|
| `manage-shopify-store` | `/shopify-manager:manage-shopify-store` | Route to the right workflow for managing the live store — products, customers, analytics, inventory, discounts, content, and store appearance via `ebshop` CLI |
| `seed-shopify-store` | `/shopify-manager:seed-shopify-store` | Populate a Shopify dev store with realistic EarlBear test data — products, customers, orders, collections, discounts, pages, blog articles, and metafields |
| `conform-store` | `/shopify-manager:conform-store` | Terraform-style declarative store management — discover drift against `manifests/shopify/manifest.yaml`, plan changes, apply, and validate convergence |
| `customize-theme` | `/shopify-manager:customize-theme` | Evaluate, select, and customize Shopify themes — configure existing themes, switch themes, or build custom Liquid templates |

## Prerequisites

- Shopify credentials configured in `.env` (run `/setup-shopify` first if not done)
- `./bin/ebshop shop health` returns `"status": "ok"`
- Docker running (for `bin/ebshop` wrapper)

## Typical flows

**First-time store setup:**
1. `/shopify-manager:seed-shopify-store` — populate with test data
2. `/shopify-manager:conform-store` — verify alignment with manifest
3. `/shopify-manager:customize-theme` — apply brand identity to theme

**Ongoing store management:**
- `/shopify-manager:manage-shopify-store` — day-to-day operations
- `/shopify-manager:conform-store` — routine drift check after manifest changes
