# Leveraging the ebshop CLI

> Use this skill when working with Shopify stores — products, orders, customers, inventory, collections, themes, pages, blogs, discounts, metafields, or webhooks. The ebshop CLI is the preferred way to interact with the Shopify Admin API.

## Quick Reference

```bash
# Store info
ebshop shop info                                          # Store details (name, plan, currency, domain)
ebshop shop health                                        # Connectivity check
ebshop shop policies                                      # Privacy, terms, refund, shipping policies

# Products
ebshop product list                                       # All products
ebshop product list --status active --vendor "EarlBear"   # Filter by status + vendor
ebshop product list --limit 50                            # Limit results
ebshop product view 123                                   # By numeric ID
ebshop product view gid://shopify/Product/123             # By full GID
ebshop product view "premium-coffee"                      # By handle (auto-detected)
ebshop product create --title "New Blend" --vendor "EarlBear" --status draft
ebshop product update 123 --title "Renamed" --tags "sale,featured"
ebshop product delete 123
ebshop product variants 123                               # List variants (price, SKU, inventory)
ebshop product images 123                                 # List product images

# Orders
ebshop order list                                         # Recent orders
ebshop order list --status open --financial-status paid    # Filter
ebshop order view 456                                     # Full order with line items
ebshop order fulfill 456 --tracking-number "1Z999" --tracking-company "UPS" --notify
ebshop order cancel 456 --reason "Customer request" --refund --restock
ebshop order notes 456                                    # Order timeline events

# Customers
ebshop customer list                                      # All customers
ebshop customer view 789                                  # Full customer details
ebshop customer search --query "john@example.com"         # Search by name/email/phone
ebshop customer create --email "new@example.com" --first-name "John" --last-name "Doe"
ebshop customer update 789 --tags "vip,wholesale"
ebshop customer orders 789                                # Customer's order history
ebshop customer tags 789 --add "vip"                      # Add tags
ebshop customer tags 789 --remove "trial"                 # Remove tags

# Collections
ebshop collection list
ebshop collection view 101                                # By ID
ebshop collection view "summer-sale"                      # By handle
ebshop collection create --title "New Arrivals"
ebshop collection update 101 --title "Updated Name"
ebshop collection products 101                            # Products in collection
ebshop collection add-products 101 --product-ids "1,2,3"
ebshop collection remove-products 101 --product-ids "1"

# Inventory
ebshop inventory levels 555                               # Levels for an inventory item across locations
ebshop inventory locations                                # All store locations
ebshop inventory adjust 555 --location-id 1 --delta 10 --reason "Restock"
ebshop inventory adjust 555 --location-id 1 --delta -2 --reason "Damaged"
ebshop inventory set 555 --location-id 1 --quantity 100
ebshop inventory product 123                              # Inventory for all variants of a product

# Analytics (computed from recent orders)
ebshop analytics summary                                  # Revenue, order count, avg order value
ebshop analytics summary --days 7                         # Last 7 days
ebshop analytics top-products --days 30 --limit 5         # Best sellers
ebshop analytics top-customers --days 30 --limit 5        # Top spenders

# Themes
ebshop theme list                                         # All themes (main, unpublished, demo)
ebshop theme view 201                                     # Theme details
ebshop theme assets 201                                   # List theme assets (files)
ebshop theme get-asset 201 --key "templates/index.json"   # Read a single asset's content
ebshop theme update-asset 201 --key "templates/index.json" --value '...'  # Write asset content
ebshop theme publish 201                                  # Make theme live

# Pages
ebshop page list                                          # Online Store pages
ebshop page view 301
ebshop page create --title "About Us" --body-html "<h1>About</h1><p>We are EarlBear.</p>"
ebshop page update 301 --title "Updated About"
ebshop page delete 301

# Blogs
ebshop blog list                                          # All blogs
ebshop blog view 401                                      # Blog details
ebshop blog articles 401                                  # Articles in blog
ebshop blog create-article 401 --title "New Post" --body-html "<p>Content</p>" --tags "coffee,guide"

# Discounts
ebshop discount list
ebshop discount view 501
ebshop discount create --title "SUMMER20" --type percentage --value 20 --code "SUMMER20"
ebshop discount create --title "$10 Off" --type fixed_amount --value 10 --code "TENOFF"
ebshop discount delete 501

# Metafields (custom data on any resource)
ebshop metafield list --owner-type product --owner-id 123
ebshop metafield list --owner-type shop                   # Shop-level metafields (no --owner-id needed)
ebshop metafield list --owner-type customer --owner-id 789 --namespace "loyalty"
ebshop metafield get gid://shopify/Metafield/999
ebshop metafield set --owner-id 123 --namespace "custom" --key "origin" --value "Colombia" --type single_line_text_field
ebshop metafield delete gid://shopify/Metafield/999

# Webhooks
ebshop webhook list
ebshop webhook create --topic orders/create --address "https://hooks.example.com/orders"
ebshop webhook create --topic products/update --address "https://hooks.example.com/products"
ebshop webhook delete 601

# Auth
ebshop auth status                                        # Check credentials + API connectivity
ebshop auth login                                         # OAuth flow to get access token (opens browser)
```

## Output Formats

Every command supports `--format` and `--json`:

```bash
# Default: JSON (agent consumption)
ebshop product list --limit 3
# [{"id": "gid://shopify/Product/1", "title": "T-Shirt", "status": "ACTIVE"}]

# Field selection — only return specific keys
ebshop product list --json id,title,status

# Human-readable table
ebshop product list --format table
# ID   TITLE     STATUS   VENDOR    VARIANTS
# 1    T-Shirt   ACTIVE   EarlBear  3

# Plain — one value per line, pipe-friendly
ebshop product list --format plain
# gid://shopify/Product/1
# gid://shopify/Product/2
```

Shorthand flags: `-f` for `--format`, `--json` for field selection.

## Discovery Pattern

```bash
ebshop --help                     # All 13 command groups
ebshop product --help             # Commands within a group
ebshop product list --help        # Options for a specific command
ebshop --help-json                # Full command tree as JSON (for agents)
ebshop --version                  # {"name": "ebshop", "version": "0.1.0"}
```

## GraphQL vs REST

Most commands use the **GraphQL Admin API**. A few use **REST** as fallback:

| API | Groups |
|-----|--------|
| GraphQL | shop, product, order, customer, collection, inventory, analytics, discount, metafield, webhook |
| REST | page, blog |
| Mixed | theme (list=GraphQL, view/assets/publish=REST) |

## ID Handling

Shopify GraphQL uses global IDs (`gid://shopify/Product/123`). Commands accept either format:

```bash
ebshop product view 123                           # Numeric — auto-converted
ebshop product view gid://shopify/Product/123     # Full GID — passed through
```

For `product view`, non-numeric strings are treated as handles:

```bash
ebshop product view "premium-coffee"              # Looked up by handle
```

## Rate Limits

Shopify GraphQL uses cost-based rate limiting:
- **Standard plans**: 50 points/second, 1000-point bucket
- **Advanced**: 100 pts/sec
- **Plus**: 500 pts/sec

The client tracks available points from `extensions.cost.throttleStatus` in every response. If you're hitting limits, reduce `--limit` values or add delays between commands.

## Common Workflows

### Analyze a store

```bash
ebshop shop info                                  # Store overview
ebshop analytics summary --days 30                # Revenue + order stats
ebshop analytics top-products --limit 10          # Best sellers
ebshop product list --limit 50 --json id,title,status,vendor  # Product catalog
ebshop inventory locations                        # Fulfillment locations
```

### Audit product catalog

```bash
ebshop product list --status draft                # Draft products (not live)
ebshop product list --status archived             # Archived products
ebshop product list --json id,title,status,total_variants  # Quick inventory scan
```

### Customer insights

```bash
ebshop analytics top-customers --days 90          # Top spenders (90 days)
ebshop customer search --query "vip"              # Search by tag/name/email
ebshop customer orders 789                        # Specific customer's history
```

### Manage discounts

```bash
ebshop discount list --format table               # Active discounts
ebshop discount create --title "FLASH50" --type percentage --value 50 --code "FLASH50"
ebshop discount delete 501                        # Remove expired discount
```

### Checkout branding from manifest

`checkout-branding update --from-manifest` reads `brand_identity.colors` from `manifest.yaml` and applies them to the Shopify checkout (primary, secondary, accent colors). This avoids manually passing `--primary-color`, `--secondary-color`, etc. The manifest is mounted into Docker automatically (see below).

## Docker Nuances

Same dual execution model as ebjira/ebdocs:

```
bin/ebshop product list --limit 10
  -> docker run --rm --env-file .env ebshop product list --limit 10
       -> Python CLI inside container -> Shopify GraphQL API
            -> JSON to stdout
```

- **Rebuild after code changes:** `make ebshop-build`
- **Force rebuild:** `make ebshop-rebuild`
- **Clean before rebuild:** `make ebshop-clean` (removes egg-info, pycache)
- **Credentials from `.env`** via Docker `--env-file`. Container never stores credentials.
- **Manifest mounted automatically** — `bin/ebshop` honors `$MANIFEST_FILE` (or falls back to `../earlbear/manifests/shopify/manifest.yaml`), mounts it read-only at `/app/assets/manifest.yaml` inside the container, and sets `MANIFEST_FILE=/app/assets/manifest.yaml`. This enables `--from-manifest` flags inside the container. earlbear-clis itself ships no brand manifest.

In the cloud agent, ebshop is installed directly via `pip install -e shopify-cli/` (no Docker).

## API Nuances

### Webhook topic format

Shopify GraphQL expects SCREAMING_SNAKE_CASE topics (`ORDERS_CREATE`), but the conventional format is slash-separated (`orders/create`). The `webhook create` command accepts slash format and converts automatically.

### Analytics are computed, not API-fetched

The `analytics` commands fetch recent orders and aggregate locally. Shopify doesn't expose a general analytics API via GraphQL. For precise analytics, use the Shopify Admin dashboard.

### Metafield owner types

Supported owner types for `metafield list`: `product`, `order`, `customer`, `collection`, `shop`. For `shop`, no `--owner-id` is needed.

### Theme asset read/write

`theme get-asset` reads a single asset's content by key (e.g., `templates/index.json`). `theme update-asset` writes content back. Both use the REST Asset API. Useful for programmatic theme customization without downloading the full theme.

### Theme operations use REST

Theme `view`, `assets`, `get-asset`, `update-asset`, and `publish` use the REST Admin API because GraphQL theme support is limited.

### Page and blog operations use REST

Online Store pages and blogs are not well-supported in the GraphQL Admin API. All page/blog commands use REST endpoints.

## Authentication

Credentials come from the **earlbear-shopify-app-cli** sibling repo (Shopify app managed via Shopify CLI).

| Variable | Required | Description |
|----------|----------|-------------|
| `SHOPIFY_STORE_URL` | Yes | e.g. `h2c5zf-0b.myshopify.com` |
| `SHOPIFY_ACCESS_TOKEN` | Yes | Access token (starts with `shpat_`) — extracted from app's Prisma session |
| `SHOPIFY_CLIENT_ID` | No | From `shopify.app.toml` in app repo |
| `SHOPIFY_API_VERSION` | No | Default: `2026-01` |

**Getting the token:**
```bash
# 1. Run Shopify app dev server (interactive — does OAuth in browser):
cd /Users/omareid/Workspace/git/earlbear-cli && make dev

# 2. After OAuth completes, sync credentials to earlbear:
make ebshop-sync-creds    # pulls from app repo's Prisma DB into .env
# OR from the app repo:
cd /Users/omareid/Workspace/git/earlbear-cli && make sync-env
```

**Checking status:**
```bash
ebshop auth status    # Shows credentials, API connectivity, store info
./bin/ebshop shop health  # Quick connectivity check
```

**Viewing credentials:**
```bash
make ebshop-show-token    # JSON: shop, token, scopes
make ebshop-show-env      # .env format
```

Access tokens do not expire unless the app is uninstalled. See `/setup-shopify` for full setup walkthrough.

## Error Handling

```bash
# GraphQL errors -> stderr as JSON, exit code 1
$ ebshop product view 999999
{"error": "SHOPIFY_200", "message": "Product not found", "status": 1}

# Config errors -> stderr as JSON, exit code 2
$ ebshop shop health
{"error": "CONFIG_MISSING", "message": "Missing required config: SHOPIFY_STORE_URL, SHOPIFY_ACCESS_TOKEN"}
```

## Troubleshooting — When to Trigger Credential Setup

### Error: `CONFIG_MISSING: Missing required config: SHOPIFY_STORE_URL, SHOPIFY_ACCESS_TOKEN`

Shopify credentials aren't in `.env`. The user needs to run the Shopify app and sync credentials.

**Action:**
```bash
# 1. Start the Shopify app dev server (interactive — does OAuth in browser):
cd /Users/omareid/Workspace/git/earlbear-cli && make dev

# 2. After OAuth completes, sync credentials to earlbear:
cd /Users/omareid/Workspace/git/earlbear && make ebshop-sync-creds
```

If the app repo doesn't exist yet:
```bash
cd /Users/omareid/Workspace/git
git clone git@github.com:omars-lab/earlbear-shopify-app-cli.git earlbear-cli
cd earlbear-cli && npm install && make dev
```

### Error: `401 Unauthorized` after working previously

The access token was invalidated (app uninstalled, app deleted, or store ownership change).

**Action:** Re-run `make dev` in the app repo to re-do OAuth, then `make ebshop-sync-creds`.

### Error: `CONFIG_MISSING: .env file not found`

No `.env` at repo root. Copy from example: `cp .env.example .env`, then run `make ebshop-sync-creds`.

### Quick diagnostic

```bash
./bin/ebshop shop health    # Exit 0 = working, exit 2 = config missing
make ebshop-show-token      # Show what's in the app repo's session DB
```

## Seeding a Dev Store

```bash
make ebshop-seed-dry    # Preview what will be created (no changes)
make ebshop-seed        # Seed real data (idempotent — safe to re-run)
```

Seeds 63 items: 12 products (with images), 5 collections, 8 customers, 4 discounts, 4 pages, 4 blog articles, 6 metafields, and 8 completed orders. All EarlBear coffee-themed.

## All Command Groups (26 total)

| Group | Commands | API |
|-------|----------|-----|
| **auth** | login, status | OAuth |
| **shop** | info, health, policies | GraphQL + REST |
| **product** | list, view, create, update, delete, variants, images | GraphQL |
| **order** | list, view, fulfill, cancel, notes | GraphQL |
| **customer** | list, view, search, create, update, orders, tags | GraphQL |
| **collection** | list, view, create, update, products, add-products, remove-products | GraphQL |
| **inventory** | levels, locations, adjust, set, product | GraphQL |
| **analytics** | summary, top-products, top-customers | GraphQL (computed) |
| **theme** | list, view, assets, get-asset, update-asset, publish | GraphQL + REST |
| **page** | list, view, create, update, delete | REST |
| **blog** | list, view, articles, create-article | REST |
| **discount** | list, view, create, delete | GraphQL |
| **metafield** | list, get, set, delete | GraphQL |
| **webhook** | list, create, delete | GraphQL |
| **navigation** | list, view, create, update, delete | GraphQL |
| **file** | list, view, upload, delete | GraphQL |
| **script-tag** | list, create, delete | GraphQL |
| **checkout-branding** | view, update | GraphQL |
| **draft-order** | list, view, create, complete, delete | GraphQL |
| **fulfillment-order** | list, accept, reject | GraphQL |
| **return** | list, view, create | GraphQL |
| **shipping** | zones, rates | GraphQL |
| **market** | list, view, create | GraphQL |
| **translation** | list, set, delete | GraphQL |
| **locale** | list, enable, disable | GraphQL |
| **gift-card** | list, view, create, disable | GraphQL |

## Gotchas & Troubleshooting

### Error: "Context can't be blank" on discount create

The `discountCodeBasicCreate` mutation in API version `2026-01` requires three fields that used to be optional:

```bash
# WRONG -- missing required fields
ebshop discount create --title "SAVE10" --type percentage --value 10 --code "SAVE10"

# The CLI handles this internally -- just make sure you're on the latest build:
make ebshop-rebuild
```

If you see this error after a rebuild, the mutation body is missing `startsAt`, `customerSelection`, or `combinesWith`. Check `commands/discount.py`.

### Error: field not found for `totalCount`, `ordersCount`, or `totalSpentV2`

These fields were renamed in `2026-01`:
- `totalCount` -> `totalVariants` (on Product)
- `ordersCount` -> `numberOfOrders` (on Customer)
- `totalSpentV2` -> `amountSpent` (on Customer)

If you see null values for variant counts or customer stats, your GraphQL query is using the old field name. Update the query and the Pydantic model alias.

### Error: field not found for `note` on DraftOrder

The `note` field was removed from `DraftOrder` in `2026-01`. Remove it from queries and mutations. Use `customAttributes` instead.

### Error: field not found for `privacyPolicy` on Shop

Policy fields were moved off the `Shop` type. Use REST `GET /admin/api/2026-01/policies.json` instead. The `shop policies` command already does this.

### Error: "Variable $input of type ProductInput" on product update

The `productUpdate` mutation changed its input type from `ProductInput` to `ProductUpdateInput` in `2026-01`. Update the mutation variable declaration.

### Pydantic validation errors on otherwise valid responses

Shopify returns `null` for empty strings (notes, descriptions, authors, addresses). Model fields must use `str | None = ""` or `str | None = None`. If you add a new model field that could be empty, type it as optional.

### `themes { nodes { ... } }` returns an error

The `themes` connection requires `first` parameter: `themes(first: 50) { nodes { ... } }`.

### Product images not appearing after `file upload`

`fileCreate` uploads to Shopify Files but does NOT attach images to products. Use `product attach-image --url <url>` to associate an image with a product via `productCreateMedia`.

### OAuth login fails silently / redirect error

Check these exact settings in the Dev Dashboard:
OAuth is handled by the **earlbear-shopify-app-cli** sibling repo via `make dev`. The app is configured with `embedded = false` and `redirect_urls = ["http://localhost:19456/callback"]` in `shopify.app.toml`. After OAuth, extract the token with `make ebshop-sync-creds`.

### Rate limit errors on large queries

Shopify uses cost-based rate limiting (not request count). Reduce `--limit` values or simplify queries. Check `extensions.cost.throttleStatus.currentlyAvailable` in responses. Standard plans: 50 pts/sec, 1000-point bucket.

### `401 Unauthorized` after working previously

Access tokens are invalidated if:
- The app is uninstalled from the store
- The app is deleted from the Partners Dashboard
- Store ownership changes

Regenerate by running `make dev` in the app repo to re-do OAuth, then `make ebshop-sync-creds` to update `.env`.

## Extending the CLI

Same pattern as ebjira — one file per command group in `shopify-cli/src/ebshop/commands/`:

1. Create `commands/newgroup.py` with a Typer sub-app
2. Register in `main.py` inside `_register_commands()`
3. Add Pydantic models in `models/newgroup.py`
4. Add tests in `tests/test_newgroup.py`
5. Update `tests/test_discoverability.py` (ALL_GROUPS + GROUP_SUBCOMMANDS)
6. Rebuild: `make ebshop-build`

Use `get_client().graphql()` for single queries, `graphql_paginated()` for connections, and `rest_get()`/`rest_post()` for REST fallback.
