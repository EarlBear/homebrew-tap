---
name: conform-store
description: Terraform-style declarative Shopify store management — discover drift, plan changes, apply, and validate convergence against manifest.yaml
type: user-invocable
---

# Conform Store

> **Context:** Declarative store management — Terraform-style. The manifest (`manifests/shopify/manifest.yaml`) is the desired state; the live Shopify store is the current state. This skill bridges the gap by discovering drift, planning changes, applying them, and validating convergence.

## When to trigger

User says things like:
- "conform the store", "sync store to manifest"
- "is the store in sync?", "what's drifted?"
- "apply the manifest", "make the store match the manifest"
- "store conformance check", "terraform the store"

## Prerequisites

- Shopify credentials configured in `.env` (run `/setup-shopify` first)
- `./bin/ebshop shop health` returns `"status": "ok"`
- Docker running (for `bin/ebshop` wrapper)
- Manifest exists: `manifests/shopify/manifest.yaml`

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `/seed-shopify-store` | Initial population — run before first conformance check |
| `/customize-theme` | Deep theme work — use when theme needs more than settings tweaks |
| `/manage-shopify-store` | Ad-hoc operations — use for one-off changes outside the manifest |
| `/leveraging-shopify-cli` | CLI reference — command syntax and quirks |

---

## Phase 1: Discover

Read current store state via the ebshop CLI. Capture output as JSON for structured comparison.

```bash
# Products
./bin/ebshop product list --limit 250 --format json

# Collections
./bin/ebshop collection list --limit 250 --format json

# Customers
./bin/ebshop customer list --limit 250 --format json

# Discounts
./bin/ebshop discount list --format json

# Pages
./bin/ebshop page list --format json

# Blog articles
./bin/ebshop blog list --format json
# Then for each blog:
./bin/ebshop blog articles <BLOG_ID> --format json

# Theme
./bin/ebshop theme list --format json
# Get active theme settings:
./bin/ebshop theme assets <ACTIVE_THEME_ID> --format json

# Navigation
./bin/ebshop navigation list --format json

# Inventory locations
./bin/ebshop inventory locations --format json

# Checkout branding
./bin/ebshop checkout-branding view --format json
```

**Tip:** Run all discovery commands before doing any analysis. Capture the full picture first.

---

## Phase 2: Diff

Compare live state against `manifests/shopify/manifest.yaml`. Read the manifest and match each section.

### Matching rules

| Section | Match Key | Fields to Compare |
|---------|-----------|-------------------|
| Products | `title` | vendor, product_type, tags, description, status, image presence |
| Collections | collection name | products assigned (by title) |
| Customers | `email` | first_name, last_name, tags |
| Discounts | `code` | title, type, value |
| Pages | `title` | body_html (structural comparison, not exact) |
| Blog articles | `title` | tags, body_html (structural) |
| Theme settings | setting key path | color values, font names, layout values |
| Navigation | menu name | items (title + link) |
| Checkout | setting key | colors, font |

### Diff output format

Generate a conformance report:

```
=== Conformance Report ===

Products:       12 match, 0 missing, N extra
Collections:     5 match, 0 missing, N extra
Customers:       8 match, 0 missing, N extra
Discounts:       4 match, 0 missing, 0 extra
Pages:           4 match, 0 missing, 0 extra
Blog articles:   4 match, 0 missing, 0 extra
Theme:           N drifted settings (list them)
Navigation:      main_menu: N items match, N missing; footer_menu: N items match, N missing
Checkout:        N drifted settings / not configured (requires Plus plan)

Overall: X drifts detected
```

### Classifying items

- **Match:** Live entity exists and all compared fields align with manifest
- **Missing:** In manifest but not in store — needs creation
- **Extra:** In store but not in manifest — flag for review (do NOT auto-delete)
- **Drifted:** Exists in both but fields differ — needs update

### HTML content comparison

For pages and blog articles, compare structure not exact HTML. Ignore whitespace differences, attribute ordering, and minor formatting. Flag only meaningful content changes (different text, missing sections, wrong headings).

---

## Phase 3: Plan

Generate an execution plan listing every change. Group by action type.

### Plan output format

```
=== Conformance Plan ===

N actions planned:

[CREATE] Product "Cold Brew Coarse Grind" — missing from store
[UPDATE] Product "EarlBear Signature Blend" — tags mismatch (expected: "coffee,whole-bean,medium-roast,signature", got: "coffee,whole-bean")
[CREATE] Collection "New Arrivals" — missing from store
[UPDATE] Collection "Whole Bean Coffee" — missing product "Decaf Swiss Water Process"
[UPDATE] Theme setting colors.primary — expected "#5C3D2E", got "#000000"
[CREATE] Navigation item "Gift Sets" in main_menu/Shop
[CREATE] Page "FAQ" — missing from store
[REVIEW] 16 extra products not in manifest (likely archived Shopify defaults)
[SKIP]   Checkout branding — requires Shopify Plus plan
```

### Action types

| Action | Meaning |
|--------|---------|
| `CREATE` | Entity missing from store, will be created |
| `UPDATE` | Entity exists but fields differ, will be updated |
| `DELETE` | Entity in store but not in manifest — only if explicitly confirmed |
| `REVIEW` | Extra entities flagged for human review, no auto-action |
| `SKIP` | Cannot be applied via API (manual admin action needed) |
| `LINK` | Collection-product association needs updating |

### Confirm before apply

Always present the plan and ask for confirmation before proceeding to Phase 4. The user may choose to:
- Apply all changes
- Apply selectively (e.g., "just products and collections, skip theme")
- Abort

---

## Phase 4: Apply

Execute the approved plan using ebshop CLI commands. Run one action at a time and report results.

### Command mapping

| Action | CLI Command |
|--------|-------------|
| Create product | `./bin/ebshop product create --title "..." --vendor "..." --product-type "..." --tags "..." --description "..." --status active` |
| Update product | `./bin/ebshop product update <ID> --tags "..." --description "..."` |
| Attach product image | `./bin/ebshop product attach-image <PRODUCT_ID> --url "<drive_url>" --alt "..."` |
| Create collection | `./bin/ebshop collection create --title "..."` |
| Add products to collection | `./bin/ebshop collection add-products <COLLECTION_ID> --product-ids "<PRODUCT_GID>"` |
| Remove products from collection | `./bin/ebshop collection remove-products <COLLECTION_ID> --product-ids "<PRODUCT_GID>"` |
| Create customer | `./bin/ebshop customer create --email "..." --first-name "..." --last-name "..." --tags "..."` |
| Update customer tags | `./bin/ebshop customer tags <ID> --add "..."` |
| Create discount | `./bin/ebshop discount create --title "..." --type percentage --value 20 --code "..."` |
| Create page | `./bin/ebshop page create --title "..." --body-html "..." --published` |
| Create blog article | `./bin/ebshop blog create-article <BLOG_ID> --title "..." --body-html "..." --tags "..." --published` |
| Update theme setting | `./bin/ebshop theme update-asset <THEME_ID> --key "config/settings_data.json" --value "..."` |
| Create navigation item | `./bin/ebshop navigation update <MENU_ID> --add-item "..."` |
| Update navigation item | `./bin/ebshop navigation update <MENU_ID> --update-item "..."` |

### Apply order

Apply changes in dependency order:

1. **Products** first (collections reference them)
2. **Collections** second (need product GIDs)
3. **Collection-product links** third
4. **Customers** (independent)
5. **Discounts** (independent)
6. **Pages** (independent)
7. **Blog articles** (need blog ID)
8. **Navigation** (references pages/collections)
9. **Theme settings** last (visual, safe to do last)
10. **Checkout branding** (may require Plus plan — skip if unavailable)

### Error handling

- If a create fails because the entity already exists, treat as idempotent — fetch the existing entity and update instead
- If an update fails, log the error and continue with the next action
- Collect all errors and present a summary at the end

---

## Phase 5: Validate

Re-run conformance diff and integration tests to verify convergence.

```bash
# 1. Re-run conformance diff — should show 100%
make shopify-cli-conform

# 2. Run integration tests — should show all pass
make shopify-cli-integ

# 3. Export current state for comparison
make shopify-cli-export

# 4. Generate store diagram — visual sanity check
make shopify-cli-diagram
```

### Validation output

```
=== Post-Conformance Validation ===

Products:       12 match, 0 missing, 16 extra (pre-existing, reviewed)
Collections:     5 match, 0 missing, 3 extra (reviewed)
Customers:       8 match, 0 missing, 0 extra
Discounts:       4 match, 0 missing, 0 extra
Pages:           4 match, 0 missing, 0 extra
Blog articles:   4 match, 0 missing, 0 extra
Theme:           0 drifted settings
Navigation:      fully aligned
Checkout:        skipped (requires Plus)

Conformance score: 100% (0 actionable drifts remaining)
```

If drifts remain, list them with explanations (e.g., "Theme font not available in Dawn — requires custom theme").

## Phase 6: Regression Test (Post-Conform)

After applying changes, walk through these checks together to confirm the store looks and behaves as expected.

### Visual checks (browser)

Open `https://earlbear-dev.myshopify.com` and verify:

| Check | What to look for |
|-------|-----------------|
| **Hero banner** | Shows "EarlBear" heading with tagline, not snowboard content |
| **Featured collection** | Displays Signature Blends or All Products, not "Snowboard" |
| **Product cards** | Show EarlBear coffee products with AI-generated images |
| **Collection list** | Shows EarlBear collections (Signature Blends, Single Origin, etc.) |
| **Navigation** | Main menu has Shop dropdown, About, Blog, Contact |
| **Footer** | Shows EarlBear brand info, footer menu links work |
| **Product page** | Click a product — image loads, price shows, add to cart works |
| **Mobile** | Resize browser — layout is clean, nav collapses properly |

### API checks (CLI)

```bash
# Store is reachable
./bin/ebshop shop health

# Products look right
./bin/ebshop product list --limit 5 --format table

# Collections have products assigned
./bin/ebshop collection products <COLLECTION_GID> --limit 5

# Product images are attached
./bin/ebshop product images <PRODUCT_GID>

# Discounts are active
./bin/ebshop discount list --format table

# Theme is configured
./bin/ebshop theme list

# Navigation menus exist
./bin/ebshop navigation list
```

### Automated regression

```bash
# Full integration test suite
make shopify-cli-integ

# Conformance diff (expect 100%)
make shopify-cli-conform

# Generate diagram for review
python3 scripts/shopify-conform.py diagram --output docs/store-diagram.md
```

### If regression finds issues

Issues found post-conform are **bugs in the conformance pipeline** — not separate work. Every issue traces back to one of:

| Root cause | Fix location | Example |
|-----------|-------------|---------|
| **Manifest gap** | `manifests/shopify/manifest.yaml` | Missing navigation item, wrong collection assignment |
| **CLI bug** | `../earlbear-clis/shopify-cli/src/ebshop/commands/*.py` | Command doesn't handle a field correctly |
| **Conform script gap** | `scripts/shopify-conform.py` | Diff doesn't check a section, plan misses an action |
| **Seed script gap** | `scripts/seed-shopify-store.py` | Seeder doesn't create something the manifest declares |
| **API gotcha** | `CLAUDE.md` gotchas + design doc | Shopify API changed behavior, needs documenting |
| **Theme drift** | `scripts/update-theme-earlbear.py` | Theme settings don't match manifest theme section |

**The goal is zero issues after conformance.** If conformance reports 100% but the store looks wrong, the conformance check itself is incomplete — fix the check, not the store manually. This keeps the pipeline trustworthy.

After fixing the root cause, re-run the full cycle:
```bash
make shopify-cli-conform    # Should show 100%
make shopify-cli-integ      # Should show all pass
```

---

## Conflict Resolution

When the manifest and live store disagree, use this decision table:

| Scenario | Winner | Rationale |
|----------|--------|-----------|
| Product in manifest, missing from store | **Manifest** — create it | Manifest is desired state |
| Product in store, missing from manifest | **Store** — flag for review | Could be intentionally added outside manifest; never auto-delete products |
| Field mismatch (tags, description, vendor) | **Manifest** — update store | Manifest is source of truth for declared fields |
| Product has extra fields not in manifest (e.g., metafields added manually) | **Store** — preserve | Manifest only declares what it declares; extra fields are additive |
| Collection has extra products not in manifest | **Store** — preserve | Manifest lists minimum products; extras may be intentional |
| Collection missing products from manifest | **Manifest** — add them | Manifest declares required membership |
| Theme setting differs | **Manifest** — update | Brand consistency; use `/customize-theme` for deeper changes |
| Navigation item missing | **Manifest** — create | Manifest defines the navigation structure |
| Navigation has extra items | **Store** — flag for review | May be intentionally added |
| Discount expired or deleted | **Manifest** — recreate | Manifest declares active discount codes |
| Page content differs | **Manifest** — update | Manifest is source of truth for page content |
| Checkout branding differs | **Skip** | Requires Shopify Plus; note in report |

### Key principle

**Manifest is additive, not destructive.** The manifest declares what MUST exist. It does not declare what must NOT exist. Extra items in the store are flagged for review but never automatically deleted. Deletions require explicit human confirmation.

---

## Manual Actions Log

Some operations cannot be performed via the API. Log these for manual execution in Shopify Admin:

| Operation | Why Manual | Admin Path |
|-----------|-----------|------------|
| Delete a collection | API may not support delete for all collection types | Products > Collections > Select > Delete |
| Checkout branding | Requires Shopify Plus plan | Settings > Checkout > Customize |
| Gift card creation | Requires specific API permissions | Products > Gift cards |
| Store settings (currency, timezone) | Not available via Admin API | Settings > General |
| Quick filters on board | Shopify Admin UI only | N/A |

---

## Common Workflows

### First-time conformance (after seeding)

```
1. Run /seed-shopify-store (populates baseline data)
2. Run /conform-store (discovers, diffs — should show minimal drift)
3. Fix any drift from seed gaps
4. Validate to 100%
```

### After manifest update

```
1. Edit manifests/shopify/manifest.yaml
2. Run /conform-store — Phase 1+2 only (discover + diff)
3. Review the plan
4. Apply approved changes
5. Validate
```

### Routine drift check

```
1. Run /conform-store — Phases 1+2 only
2. If 0 drifts: done
3. If drifts found: investigate cause, update manifest or store as appropriate
```

### Theme conformance specifically

For deep theme work beyond simple settings, use `/customize-theme` instead. This skill handles theme *settings* (colors, fonts, layout values in `settings_data.json`). `/customize-theme` handles theme *evaluation*, *selection*, and *Liquid template customization*.
