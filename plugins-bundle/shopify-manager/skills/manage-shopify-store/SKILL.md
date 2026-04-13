---
name: manage-shopify-store
description: Route to the right workflow for managing the EarlBear Shopify store via the ebshop CLI
type: user-invocable
---

# Manage Shopify Store

> **Context:** This skill routes to the right workflow for managing the EarlBear Shopify store. It covers product management, customer insights, analytics, content, promotions, and store configuration — all via the `ebshop` CLI.

## When to trigger

User says things like:
- "manage the shopify store", "update products"
- "add a new product", "analyze sales", "create a discount"
- "update the store theme", "check inventory"
- "what's selling", "who are our top customers"

## Intent Router

| Intent | Action |
|--------|--------|
| Add/update/delete products | Go to **Product Management** |
| Analyze sales, revenue, trends | Go to **Analytics & Insights** |
| View/manage customers | Go to **Customer Management** |
| Create/manage discounts | Go to **Promotions** |
| Update pages, blog, navigation | Go to **Content Management** |
| Manage inventory levels | Go to **Inventory** |
| Theme/checkout customization | Go to **Store Appearance** |
| Manage collections | Go to **Collection Management** |
| International/multi-market | Go to **International** |
| Seed test data | Use `/seed-shopify-store` |
| Setup/auth issues | Use `/setup-shopify` |
| CLI command reference | Use `/leveraging-shopify-cli` |

---

## Product Management

### Add a new product

```bash
# Create the product
./bin/ebshop product create \
  --title "New Product Name" \
  --vendor "EarlBear" \
  --product-type "Whole Bean Coffee" \
  --tags "coffee,new-arrival" \
  --description "<p>Product description with HTML.</p>" \
  --status active

# Upload an image
./bin/ebshop file upload --url "https://example.com/image.jpg" --alt "Product image"

# Add to a collection
./bin/ebshop collection add-products <COLLECTION_ID> --product-ids "<PRODUCT_ID>"

# Set a metafield
./bin/ebshop metafield set --owner-id <PRODUCT_ID> --namespace custom --key origin --value "Colombia" --type single_line_text_field
```

### Update a product

```bash
./bin/ebshop product update <ID> --title "Updated Name" --tags "updated,featured"
./bin/ebshop product update <ID> --status draft    # Unpublish
./bin/ebshop product update <ID> --status active   # Republish
```

### Audit the catalog

```bash
./bin/ebshop product list --format table                    # Overview
./bin/ebshop product list --status draft                    # Draft (not live)
./bin/ebshop product list --status archived                 # Archived
./bin/ebshop product list --json id,title,status,total_variants,total_inventory  # Inventory scan
```

---

## Analytics & Insights

### Revenue summary

```bash
./bin/ebshop analytics summary                     # Last 30 days
./bin/ebshop analytics summary --days 7            # Last week
./bin/ebshop analytics summary --days 90           # Last quarter
```

### Top products

```bash
./bin/ebshop analytics top-products --limit 10     # Best sellers (30 days)
./bin/ebshop analytics top-products --days 7        # This week's best sellers
```

### Top customers

```bash
./bin/ebshop analytics top-customers --limit 10    # Highest spenders
./bin/ebshop analytics top-customers --days 90     # Quarter view
```

### Deep dive on a product

```bash
./bin/ebshop product view <ID>                     # Full details
./bin/ebshop product variants <ID>                 # Pricing + inventory per variant
./bin/ebshop inventory product <ID>                # Stock across all locations
```

---

## Customer Management

### Find and view customers

```bash
./bin/ebshop customer list --format table
./bin/ebshop customer search --query "john@example.com"
./bin/ebshop customer view <ID>
./bin/ebshop customer orders <ID>                  # Order history
```

### Segment by tags

```bash
./bin/ebshop customer tags <ID> --add "vip"
./bin/ebshop customer tags <ID> --add "wholesale"
./bin/ebshop customer tags <ID> --remove "trial"
```

### Create a customer

```bash
./bin/ebshop customer create --email "new@example.com" --first-name "Jane" --last-name "Doe" --tags "retail"
```

---

## Promotions

### Create discounts

```bash
# Percentage discount
./bin/ebshop discount create --title "Summer Sale" --type percentage --value 20 --code "SUMMER20"

# Fixed amount
./bin/ebshop discount create --title "$5 Off" --type fixed_amount --value 5 --code "FIVEOFF"

# Check existing
./bin/ebshop discount list --format table
```

### Gift cards

```bash
./bin/ebshop gift-card create --initial-value 50 --note "Staff appreciation"
./bin/ebshop gift-card list --format table
./bin/ebshop gift-card disable <ID>
```

---

## Content Management

### Pages

```bash
./bin/ebshop page list --format table
./bin/ebshop page create --title "About Us" --body-html "<h1>Our Story</h1><p>...</p>" --published
./bin/ebshop page update <ID> --body-html "<h1>Updated content</h1>"
./bin/ebshop page delete <ID>
```

### Blog articles

```bash
./bin/ebshop blog list                             # Find blog ID
./bin/ebshop blog articles <BLOG_ID>               # List articles
./bin/ebshop blog create-article <BLOG_ID> \
  --title "New Post" \
  --body-html "<p>Article content</p>" \
  --tags "coffee,guide" \
  --published
```

### Navigation menus

```bash
./bin/ebshop navigation list
./bin/ebshop navigation view <ID>
./bin/ebshop navigation create --title "Footer Menu"
./bin/ebshop navigation update <ID> --title "Updated Menu"
```

---

## Inventory

### Check stock

```bash
./bin/ebshop inventory locations                   # All locations
./bin/ebshop inventory product <PRODUCT_ID>        # Stock per variant per location
./bin/ebshop inventory levels <INVENTORY_ITEM_ID>  # Levels for a specific item
```

### Adjust stock

```bash
./bin/ebshop inventory adjust <ITEM_ID> --location-id <LOC_ID> --delta 50 --reason "Restock"
./bin/ebshop inventory adjust <ITEM_ID> --location-id <LOC_ID> --delta -3 --reason "Damaged"
./bin/ebshop inventory set <ITEM_ID> --location-id <LOC_ID> --quantity 100
```

---

## Store Appearance

### Themes

```bash
./bin/ebshop theme list                            # Current themes
./bin/ebshop theme view <ID>                       # Theme details
./bin/ebshop theme assets <ID>                     # All template files
./bin/ebshop theme publish <ID>                    # Make a theme live
```

### Checkout branding

```bash
./bin/ebshop checkout-branding view                # Current settings
./bin/ebshop checkout-branding update --primary-color "#8B4513"
```

### Script tags (storefront JS)

```bash
./bin/ebshop script-tag list
./bin/ebshop script-tag create --src "https://cdn.example.com/analytics.js"
./bin/ebshop script-tag delete <ID>
```

---

## Collection Management

```bash
./bin/ebshop collection list --format table
./bin/ebshop collection create --title "Summer Picks"
./bin/ebshop collection products <ID>              # Products in collection
./bin/ebshop collection add-products <ID> --product-ids "gid1,gid2,gid3"
./bin/ebshop collection remove-products <ID> --product-ids "gid1"
```

---

## International

### Markets

```bash
./bin/ebshop market list
./bin/ebshop market view <ID>
./bin/ebshop market create --name "Canada" --countries "CA"
```

### Translations

```bash
./bin/ebshop translation list --resource-id <PRODUCT_GID> --locale fr
./bin/ebshop translation set --resource-id <PRODUCT_GID> --locale fr --key title --value "Mélange Signature"
```

### Locales

```bash
./bin/ebshop locale list
./bin/ebshop locale enable --locale fr
./bin/ebshop locale disable --locale fr
```

---

## Common Workflows

### Launch a new product end-to-end

1. Create the product: `product create --title ... --status draft`
2. Upload image: `file upload --url ... --alt ...`
3. Set metafields: `metafield set --owner-id ... --namespace custom --key origin --value ...`
4. Add to collection: `collection add-products <COLL_ID> --product-ids <PROD_ID>`
5. Set inventory: `inventory set <ITEM_ID> --location-id <LOC_ID> --quantity 50`
6. Go live: `product update <ID> --status active`

### Run a flash sale

1. Create discount: `discount create --title "FLASH24H" --type percentage --value 30 --code "FLASH24H"`
2. Update collection title: `collection update <ID> --title "Flash Sale - 30% Off"`
3. Check results: `analytics summary --days 1`
4. Remove discount: `discount delete <ID>`

### Investigate low sales

1. Check revenue: `analytics summary --days 30`
2. Top products: `analytics top-products --days 30`
3. Check inventory: `inventory product <ID>` (is it out of stock?)
4. Check discoverability: `collection products <ID>` (is it in a collection?)
5. Check customer base: `analytics top-customers --days 30`
