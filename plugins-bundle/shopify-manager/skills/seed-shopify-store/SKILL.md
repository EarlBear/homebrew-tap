---
name: seed-shopify-store
description: Populate a Shopify dev store with realistic EarlBear test data including products, customers, orders, collections, and images
type: user-invocable
---

# Seed Shopify Store

> **Context:** This skill populates a Shopify dev store with realistic EarlBear test data — products, customers, orders, collections, discounts, pages, blog articles, and metafields. It includes an interactive artwork workflow where the user (an AI designer) generates product images, hero banners, and lifestyle shots.

## When to trigger

User says things like:
- "seed the shopify store", "add test data to shopify"
- "populate the dev store", "create sample products"
- "generate product images for shopify", "need artwork for the store"

## Prerequisites

- Shopify credentials configured in `.env` (run `/setup-shopify` first)
- `./bin/ebshop shop health` returns `"status": "ok"`
- Docker running (for `bin/ebshop` wrapper)

## Workflow Overview

```
Phase 1: Generate + upload images (via ebimg) — or skip with --skip-images
Phase 2: Seed data (automated) — products (with images attached inline), customers, collections, etc.
Phase 3: Verify (automated) — smoke test the seeded store
```

**Key change:** Product images are now attached inline during product creation. The seed script reads `drive_url` values from `manifest.yaml` and calls `product attach-image` immediately after creating each product. There is no separate "upload images" phase.

Use `--skip-images` to skip image attachment (faster iteration):

```bash
python3 scripts/seed-shopify-store.py --skip-images
```

## Phase 1: Generate + Upload Images (optional)

Generate and upload images before seeding so that `drive_url` values are in the manifest. The seed script reads these and attaches images inline during product creation.

```bash
./bin/ebimg setup              # One-time: install extension + verify API key
./bin/ebimg generate --missing # Generate only missing images
./bin/ebimg upload             # Upload to Google Drive (writes drive_url back to manifest)
./bin/ebimg status             # Check progress
```

Skip this phase if you just want data without images — use `--skip-images` in Phase 2.

## Phase 2: Seed Data

Run the seed script. It's idempotent — safe to re-run. Products are created with images attached inline (if `drive_url` exists in the manifest):

```bash
make shopify-cli-seed-dry     # Preview first
make shopify-cli-seed          # Create 63 items (with images)
```

To skip image attachment for faster iteration:
```bash
python3 scripts/seed-shopify-store.py --skip-images
```

This creates:
- 12 products (6 coffees, 6 accessories) — with images attached inline if drive_urls are available
- 5 collections
- 8 customers
- 4 discounts
- 4 pages
- 4 blog articles
- 6 metafields
- 8 draft orders (completed to real orders)

## Artwork Generation (if not using ebimg)

If generating images manually instead of via `ebimg`, use the prompts below with the Gemini CLI + nanobanana extension or another image generator.

### Setup (one-time)

1. Get an API key at https://aistudio.google.com/apikey
2. Add to `.env`: `NANOBANANA_API_KEY=your_key_here`
3. Run `./bin/ebimg setup` to install the nanobanana extension

### Manual generation (interactive)

If the user is an **AI designer** generating images with other tools (Midjourney, DALL-E, Ideogram), present the tables below. For each image, provide the slug and AI generation prompt.

### Product Images (12 images)

| Slug | Product | Dimensions | Description for AI Image Generation |
|------|---------|-----------|-------------------------------------|
| `product-signature-blend` | EarlBear Signature Blend | 1200x1200 | A premium bag of whole bean coffee on a rustic wooden surface. The bag is kraft paper with a minimalist EarlBear bear logo. Warm, earthy tones. Morning light streaming in. Studio product photography style. |
| `product-ethiopian-yirgacheffe` | Dark Roast Ethiopian Yirgacheffe | 1200x1200 | A dark matte black coffee bag with gold Ethiopian-inspired geometric patterns. Whole beans scattered artfully around the base. Dark, moody lighting. Single-origin premium feel. |
| `product-colombian-supremo` | Light Roast Colombian Supremo | 1200x1200 | A bright, clean coffee bag in warm cream tones with a Colombian mountain landscape illustration. Light roast beans visible through a window in the bag. Bright, airy photography. |
| `product-decaf-swiss-water` | Decaf Swiss Water Process | 1200x1200 | A serene, calming coffee bag in soft blue-green tones. Swiss mountain silhouette on the label. A steaming cup of coffee beside it. Evening/twilight mood. Gentle, peaceful composition. |
| `product-espresso-blend` | EarlBear Espresso Blend | 1200x1200 | A bold, dark coffee bag with espresso crema dripping artistically down the side. Rich brown and gold colors. An espresso portafilter in the background, slightly out of focus. Dramatic lighting. |
| `product-cold-brew-grind` | Cold Brew Coarse Grind | 1200x1200 | A refreshing cold brew coffee bag in cool blue tones. Condensation droplets on a glass of cold brew beside it. Ice cubes visible. Summer vibes. Clean, modern product photography. |
| `product-pour-over-dripper` | Ceramic Pour-Over Dripper | 1200x1200 | A handcrafted ceramic pour-over dripper in warm earth tones (terracotta/sage) sitting on a wooden counter. Hot water being poured in a slow spiral. Steam rising. Cozy kitchen setting. |
| `product-french-press` | Stainless Steel French Press 32oz | 1200x1200 | A gleaming stainless steel French press on a marble countertop. Rich dark coffee visible through the glass. Morning newspaper and a croissant in the background. Clean, aspirational lifestyle shot. |
| `product-burr-grinder` | Burr Grinder Hand Crank | 1200x1200 | A compact wooden and steel hand coffee grinder being held over a pour-over setup. Fresh grounds falling out. Walnut wood handle detail. Warm, tactile, artisanal feel. Close-up product shot. |
| `product-travel-mug` | EarlBear Insulated Travel Mug 16oz | 1200x1200 | A matte black insulated travel mug with subtle EarlBear logo, sitting on a car dashboard with a blurred autumn road through the windshield. Adventure/travel mood. Warm golden hour light. |
| `product-gooseneck-kettle` | Gooseneck Kettle 1L | 1200x1200 | An elegant matte black gooseneck electric kettle on a clean white countertop. The LED temperature display glowing softly. Water being poured in a precise thin stream. Minimalist, modern. |
| `product-subscription` | Coffee Subscription Monthly | 1200x1200 | A beautifully wrapped subscription box being opened, revealing 2-3 bags of EarlBear coffee. Tissue paper, a handwritten note card, and a small tasting guide visible. Gift/unboxing moment. Warm, inviting. |

### Hero Banners (3 images)

| Slug | Placement | Dimensions | Description for AI Image Generation |
|------|-----------|-----------|-------------------------------------|
| `hero-homepage` | Homepage hero | 1920x800 | A wide panoramic shot of a cozy coffee bar with warm lighting. Bags of EarlBear coffee on wooden shelves. A barista pouring a latte in the foreground. Earth tones, inviting atmosphere. Text space on the left third. |
| `hero-collection-beans` | Coffee collection header | 1920x600 | Overhead flat-lay of various whole bean coffees spread across a dark wooden table. Different roast levels visible (light to dark). Small bowls, scoops, and burlap texture. Rich, editorial photography. |
| `hero-collection-equipment` | Equipment collection header | 1920x600 | A beautifully arranged coffee brewing station — pour-over, French press, grinder, kettle all in a row on a clean marble counter. Morning light from a window. Clean, organized, aspirational. |

### Lifestyle Images (4 images)

| Slug | Usage | Dimensions | Description for AI Image Generation |
|------|-------|-----------|-------------------------------------|
| `lifestyle-morning-ritual` | About/Story page | 1200x800 | A person (hands only visible) wrapping both hands around a warm ceramic mug. Steam rising. A cozy blanket, a book, and morning window light. Intimate, warm, hygge feeling. |
| `lifestyle-brewing` | How to Brew page | 1200x800 | Close-up of a pour-over in progress — water spiraling over grounds in a ceramic dripper. The stream of brewed coffee falling into a glass carafe below. Sharp focus on the water stream. |
| `lifestyle-origin-farm` | Sourcing page | 1200x800 | A lush green coffee farm on a hillside. Coffee cherries on the branch, red and ripe. A farmer's hands picking cherries. Warm tropical light. Documentary/editorial style. |
| `lifestyle-friends-coffee` | Blog/social | 1200x800 | Three friends laughing together at a small cafe table, each with a different EarlBear coffee drink. Natural, candid feel. Diverse group. Warm afternoon light. Genuine joy. |

### Brand Assets (2 images)

| Slug | Usage | Dimensions | Description for AI Image Generation |
|------|-------|-----------|-------------------------------------|
| `brand-logo-dark` | Dark backgrounds | 800x800 | The EarlBear logo — a friendly, minimalist bear silhouette holding a coffee cup. Clean vector style. White on transparent. The bear should look approachable and warm, not fierce. |
| `brand-logo-light` | Light backgrounds | 800x800 | Same EarlBear bear logo but in dark brown/espresso color on transparent background. Suitable for kraft paper bags and light websites. |

### Total: 21 images needed

| Category | Count | Status |
|----------|-------|--------|
| Product images | 12 | Pending |
| Hero banners | 3 | Pending |
| Lifestyle images | 4 | Pending |
| Brand assets | 2 | Pending |
| **Total** | **21** | |

## Phase 3: Verify

After seeding data and uploading images:

```bash
make shopify-cli-smoke          # Full smoke test (20 checks)
./bin/ebshop product list --format table   # Verify products
./bin/ebshop file list --limit 20          # Verify uploaded files
./bin/ebshop analytics summary             # Should show orders now
```

## Quick Commands

```bash
make shopify-cli-seed-dry      # Preview seed (no changes)
make shopify-cli-seed           # Seed store data (idempotent)
make shopify-cli-smoke          # Verify everything works
```
