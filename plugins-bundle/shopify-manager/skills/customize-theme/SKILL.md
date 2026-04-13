---
name: customize-theme
description: Evaluate, select, and customize Shopify themes — configure existing themes, switch themes, or build custom Liquid templates
type: user-invocable
---

# Customize Theme

> **Context:** This skill provides a decision framework for evaluating, selecting, and customizing Shopify store themes. It helps determine whether to configure an existing theme, switch to a different one, or build a custom theme — then executes the chosen approach via the `ebshop` CLI and REST API.

## When to trigger

User says things like:
- "customize the theme", "update store appearance"
- "the store looks wrong", "theme needs work"
- "should we use a different theme?", "is our theme good enough?"
- "build a custom theme", "evaluate themes"
- "make the store look like our brand"

## Prerequisites

- `ebshop` CLI working (`./bin/ebshop shop health`)
- Store credentials in `.env`
- Brand identity defined in `manifests/shopify/manifest.yaml`

---

## Phase 1: Discover Current State

### 1a. Audit the active theme

```bash
# What themes are available?
./bin/ebshop theme list

# What's the active theme?
./bin/ebshop theme list | python3 -c "
import sys, json
themes = json.load(sys.stdin)
for t in themes:
    if t.get('role') == 'main':
        print(f\"Active: {t['name']} (ID: {t['id']})\")"

# What sections does it have?
./bin/ebshop theme assets <THEME_ID> | python3 -c "
import sys, json
assets = json.load(sys.stdin)
sections = [a['key'] for a in assets if a['key'].startswith('sections/')]
print(f'{len(sections)} sections:')
for s in sorted(sections): print(f'  {s}')"

# Read current settings
./bin/ebshop theme assets <THEME_ID> --key "config/settings_data.json"
```

### 1b. Identify the base theme

Common Shopify free themes and their strengths:

| Theme | Best For | Sections | Key Features |
|-------|----------|----------|-------------|
| **Dawn** | General stores, highly customizable | 30+ | Most popular, best documented, image-banner hero, featured-collection, multicolumn |
| **Horizon** | Minimal/editorial, few products | 10-15 | Clean, modern, fewer sections but more opinionated design |
| **Taste** | Food & beverage | 25+ | Built for F&B, warm aesthetics, recipe sections |
| **Craft** | Artisan/handmade goods | 25+ | Storytelling focus, maker-friendly layouts |
| **Refresh** | Health & wellness | 20+ | Clean, airy, wellness-focused sections |
| **Sense** | Beauty & cosmetics | 25+ | Rich media, ingredient spotlights |
| **Ride** | Active/outdoor | 20+ | Bold imagery, adventure-focused |
| **Studio** | Art & design | 20+ | Gallery-focused, creative layouts |
| **Publisher** | Content-heavy, blogs | 20+ | Editorial, strong blog integration |
| **Spotlight** | Single product stores | 15+ | Product showcase, minimal navigation |
| **Trade** | B2B / wholesale | 20+ | Quick order, bulk pricing, business-focused |
| **Colorblock** | Fashion | 25+ | Vibrant, editorial, lookbook sections |

### 1c. Read brand identity from manifest

```bash
python3 -c "
import yaml
with open('manifests/shopify/manifest.yaml') as f:
    m = yaml.safe_load(f)
bi = m.get('brand_identity', {})
print('Brand:', bi.get('name'))
print('Tagline:', bi.get('tagline'))
print('Personality:', bi.get('personality'))
print('Colors:', json.dumps(bi.get('colors', {}), indent=2))
print('Typography:', json.dumps(bi.get('typography', {}), indent=2))
print('Photography:', bi.get('photography', {}).get('mood'))
"
```

---

## Phase 2: Evaluate — Does the Current Theme Fit?

Score the active theme against the brand on this checklist:

| Criteria | Question | Score (0-3) |
|----------|----------|-------------|
| **Hero/Banner** | Does the hero section support our imagery and messaging? | |
| **Product Grid** | Does the product card layout match our aesthetic? | |
| **Collection Pages** | Can collections showcase our brand story? | |
| **Color Customization** | Can we set brand colors in theme settings? | |
| **Typography** | Does the font selection match our brand personality? | |
| **Blog/Content** | Does the blog layout support our content strategy? | |
| **Mobile Experience** | Does it feel premium on mobile? | |
| **Performance** | Is Lighthouse score acceptable (>80)? | |
| **Photography** | Do image sections complement our photography style? | |
| **Navigation** | Can we configure menus for our catalog structure? | |

**Scoring guide:**
- **0** = Theme fundamentally can't do this
- **1** = Possible but requires Liquid code changes
- **2** = Supported via theme settings but needs workarounds
- **3** = Perfect fit, just needs configuration

**Decision matrix:**

| Total Score | Recommendation |
|-------------|----------------|
| **25-30** | **Configure existing** — theme is a great fit, just update settings |
| **18-24** | **Switch theme** — a better free/paid theme exists for this brand |
| **10-17** | **Custom theme** — significant customization needed, consider forking |
| **0-9** | **Custom build** — the brand has unique UX requirements no theme covers |

---

## Phase 3: Decision — Three Paths

### Path A: Configure Existing Theme (Score 25-30)

This is the most common and fastest path. Dawn, for example, supports extensive configuration via `settings_data.json` without touching Liquid code.

**What you can configure via settings_data.json:**
- Hero banner (image, heading, subheading, button text/link)
- Featured collections (which collection, how many products)
- Collection list (which collections to showcase)
- Rich text sections (about us, brand story)
- Image-with-text sections (side-by-side content)
- Newsletter signup
- Footer (menus, social links, payment icons)
- Colors (primary, secondary, background, text)
- Typography (headings font, body font, font sizes)
- Logo and favicon

**Workflow:**
1. Read current `config/settings_data.json`
2. Map brand identity to theme settings
3. Update section content (hero text, collection references)
4. Upload modified settings via REST API
5. Preview and verify

```bash
# Update theme settings
./bin/ebshop theme update-asset <THEME_ID> \
  --key "config/settings_data.json" \
  --value-file /tmp/updated-settings.json

# Update checkout branding from manifest (reads brand_identity.colors)
./bin/ebshop checkout-branding update --from-manifest

# Or with explicit overrides
./bin/ebshop checkout-branding update --from-manifest --font "Lato"

# Or fully manual
./bin/ebshop checkout-branding update --primary-color "#5C3D2E" --accent-color "#2D5F4A"
```

### Path B: Switch to a Different Theme (Score 18-24)

When another free or paid theme is a better fit for the brand.

**Workflow:**
1. Research themes (web search for "best Shopify themes for [industry]")
2. Check the Shopify Theme Store: https://themes.shopify.com/
3. Install the theme (via Shopify Admin UI — API can't install themes from the store)
4. Configure via settings_data.json (same as Path A)
5. Publish the new theme

```bash
# After installing via Shopify Admin, list to find the new theme ID
./bin/ebshop theme list

# Configure it (same process as Path A)
./bin/ebshop theme assets <NEW_THEME_ID>

# Publish when ready
./bin/ebshop theme publish <NEW_THEME_ID>
```

**Theme recommendations by industry:**
- **Coffee/F&B:** Taste, Craft, Dawn (configured warm)
- **Fashion/Apparel:** Colorblock, Sense, Dawn
- **Tech/SaaS:** Dawn, Spotlight, Horizon
- **Art/Creative:** Studio, Publisher, Craft
- **B2B/Wholesale:** Trade, Dawn (configured professional)
- **Health/Wellness:** Refresh, Sense, Dawn

### Path C: Custom Theme (Score <18)

When the brand needs unique interactions no existing theme provides. See sub-skill **[Building a Custom Theme](#building-a-custom-theme)** below for the full implementation guide.

**When custom is justified:**
- Unique product configuration (build-your-own, subscriptions with complex rules)
- AI-powered recommendations/quiz integrated into storefront
- Multi-brand storefront with dynamic theming
- Highly interactive product visualization (3D, AR)
- Complex B2B flows (quote requests, approval chains)
- Brand requires unique page layouts that no section supports

**When custom is NOT justified:**
- "I want slightly different spacing" — use CSS overrides via `assets/custom.css`
- "The footer doesn't look right" — configure settings_data.json
- "I want a different font" — use theme typography settings
- "The hero image is wrong" — update the image-banner section
- "I need a new section type" — create a single custom section (not a whole theme)

### Path C2: Targeted Customization (Middle ground)

When you need 1-3 custom sections but the rest of the theme works. This is the **sweet spot** for most brands.

**Examples:**
- Custom "Our Story" section with parallax scrolling
- Product quiz recommender section
- Subscription builder section
- Custom social proof / testimonial carousel

**Workflow:**
1. Keep the existing theme (e.g., Dawn)
2. Add custom sections to `sections/` directory
3. Register them in the theme's schema
4. Optionally add custom CSS/JS in `assets/`

```bash
# Upload a custom section
./bin/ebshop theme update-asset <THEME_ID> \
  --key "sections/custom-brand-story.liquid" \
  --value-file /path/to/custom-brand-story.liquid

# Upload custom CSS
./bin/ebshop theme update-asset <THEME_ID> \
  --key "assets/custom-brand.css" \
  --value-file /path/to/custom-brand.css
```

**Cost estimate:**
- Custom theme from scratch: 100-300+ hours
- Forked theme with modifications: 20-80 hours
- Targeted custom sections (1-3): 5-20 hours
- Theme settings configuration only: 1-2 hours

---

## Phase 4: Apply Changes

### For Path A (Configure existing)

The primary mechanism is updating `config/settings_data.json`:

```bash
# 1. Download current settings
./bin/ebshop theme assets <THEME_ID> --key "config/settings_data.json" > /tmp/current-settings.json

# 2. Modify with Python/jq (see section-specific guides below)

# 3. Upload updated settings
./bin/ebshop theme update-asset <THEME_ID> \
  --key "config/settings_data.json" \
  --value-file /tmp/updated-settings.json

# 4. Update checkout (reads colors from manifest automatically)
./bin/ebshop checkout-branding update --from-manifest
```

### Dawn Section Configuration Guide

**Hero (image-banner):**
```json
{
  "type": "image-banner",
  "settings": {
    "image": "shopify://shop_images/<uploaded-image>.jpg",
    "image_overlay_opacity": 40,
    "heading": "Brand Name",
    "subheading": "Your tagline here",
    "button_label": "Shop Now",
    "button_link": "shopify://collections/all"
  }
}
```

**Featured Collection:**
```json
{
  "type": "featured-collection",
  "settings": {
    "collection": "signature-blends",
    "heading": "Our Signature Blends",
    "products_to_show": 4,
    "columns_desktop": 4,
    "image_ratio": "square",
    "show_secondary_image": true,
    "show_vendor": false,
    "show_rating": false,
    "enable_quick_add": true
  }
}
```

**Collection List:**
```json
{
  "type": "collection-list",
  "settings": {
    "heading": "Explore Our Collections",
    "image_ratio": "square",
    "columns_desktop": 3
  },
  "blocks": {
    "collection_1": { "type": "featured_collection", "settings": { "collection": "signature-blends" } },
    "collection_2": { "type": "featured_collection", "settings": { "collection": "single-origin" } },
    "collection_3": { "type": "featured_collection", "settings": { "collection": "brewing-equipment" } }
  }
}
```

**Rich Text (About Us):**
```json
{
  "type": "rich-text",
  "settings": {
    "heading": "About EarlBear",
    "text": "<p>Artisan coffee, crafted with care. We source the finest beans...</p>",
    "color_scheme": "background-1"
  }
}
```

**Newsletter Signup:**
```json
{
  "type": "newsletter",
  "settings": {
    "heading": "Join the EarlBear Family",
    "subheading": "Get 10% off your first order and be the first to know about new roasts."
  }
}
```

---

## Phase 5: Validate

After applying changes, verify the theme looks correct:

1. **Visual check** — Open the store in a browser and verify:
   - Hero shows correct brand imagery and text
   - Featured products are from the right collection
   - Colors match brand identity
   - Footer has correct info
   - Mobile layout is clean

2. **Lighthouse audit** — Run performance check:
   ```bash
   # If chrome-devtools MCP is available:
   # Navigate to store URL, run lighthouse audit
   ```

3. **Product page check** — Verify product images display correctly:
   ```bash
   ./bin/ebshop product list --limit 3 --format table
   # Open a few product URLs in browser
   ```

4. **Checkout branding check:**
   ```bash
   ./bin/ebshop checkout-branding view
   # Verify primary color matches brand
   ```

---

## Decision Log

After completing theme work, document the decision:

| Field | Value |
|-------|-------|
| **Date** | |
| **Store** | |
| **Decision** | Configure existing / Switch theme / Custom |
| **Theme** | Name + version |
| **Score** | /30 |
| **Rationale** | Why this path was chosen |
| **Changes Made** | What was configured |
| **Time Spent** | |

---

---

## Building a Custom Theme

> Sub-skill for Path C — full guide to designing, developing, and deploying a custom Shopify theme.

### Theme Architecture

Every Shopify theme follows this file structure:

```
theme/
├── config/
│   ├── settings_schema.json    # Theme-level settings (colors, fonts, logo)
│   └── settings_data.json      # Current values for settings + section arrangement
├── layout/
│   ├── theme.liquid            # Main layout wrapper (head, body, footer)
│   ├── password.liquid         # Password page layout
│   └── gift_card.liquid        # Gift card layout
├── templates/
│   ├── index.json              # Homepage template (references sections)
│   ├── product.json            # Product page template
│   ├── collection.json         # Collection page template
│   ├── page.json               # Static pages template
│   ├── blog.json               # Blog listing template
│   ├── article.json            # Blog article template
│   ├── cart.json               # Cart template
│   ├── 404.json                # 404 error template
│   └── customers/
│       ├── account.json        # Customer account
│       ├── login.json          # Login page
│       └── order.json          # Order detail
├── sections/
│   ├── header.liquid           # Site header (nav, logo, cart icon)
│   ├── footer.liquid           # Site footer
│   ├── announcement-bar.liquid # Top banner
│   ├── image-banner.liquid     # Hero section
│   ├── featured-collection.liquid
│   ├── rich-text.liquid
│   ├── image-with-text.liquid
│   ├── newsletter.liquid
│   ├── main-product.liquid     # Product page main section
│   ├── main-collection-product-grid.liquid
│   └── ... (custom sections)
├── snippets/
│   ├── card-product.liquid     # Reusable product card
│   ├── icon-*.liquid           # SVG icons
│   └── price.liquid            # Price display snippet
├── assets/
│   ├── base.css                # Core styles
│   ├── global.js               # Core JavaScript
│   └── component-*.css         # Per-component styles
└── locales/
    ├── en.default.json         # English translations
    └── fr.json                 # French translations (etc.)
```

### Liquid Template Language — Quick Reference

Liquid is Shopify's templating language. Key concepts:

**Output:**
```liquid
{{ product.title }}
{{ product.price | money }}
{{ "hello" | capitalize }}
```

**Logic:**
```liquid
{% if product.available %}
  <button>Add to Cart</button>
{% else %}
  <p>Sold out</p>
{% endif %}

{% for product in collection.products %}
  <div>{{ product.title }}</div>
{% endfor %}
```

**Objects available in templates:**
- `shop` — store name, URL, currency
- `product` — current product (on product pages)
- `collection` — current collection
- `cart` — shopping cart
- `customer` — logged-in customer
- `page_title`, `page_description` — SEO
- `content_for_header` — required Shopify scripts
- `content_for_layout` — section content placeholder
- `section.settings` — current section's settings
- `section.blocks` — current section's blocks

**Section schema (makes sections configurable in theme editor):**
```liquid
{% schema %}
{
  "name": "Custom Hero",
  "settings": [
    {
      "type": "image_picker",
      "id": "image",
      "label": "Hero image"
    },
    {
      "type": "text",
      "id": "heading",
      "label": "Heading",
      "default": "Welcome"
    },
    {
      "type": "color",
      "id": "text_color",
      "label": "Text color",
      "default": "#ffffff"
    },
    {
      "type": "url",
      "id": "button_link",
      "label": "Button link"
    }
  ],
  "presets": [
    {
      "name": "Custom Hero"
    }
  ]
}
{% endschema %}
```

**Section setting types:** `text`, `textarea`, `richtext`, `image_picker`, `url`, `color`, `range`, `select`, `checkbox`, `number`, `font_picker`, `collection`, `product`, `blog`, `page`, `link_list`, `video_url`, `html`, `liquid`

### Development Workflow

**Prerequisites:**
```bash
# Install Shopify CLI (Node.js required)
npm install -g @shopify/cli@latest

# Authenticate
shopify auth login --store earlbear-dev.myshopify.com
```

**Local development:**
```bash
# Pull existing theme as starting point
shopify theme pull --store earlbear-dev --theme <THEME_ID> --path ./theme-dev

# Start dev server (hot reload, live preview)
shopify theme dev --store earlbear-dev --path ./theme-dev
# Opens browser at http://127.0.0.1:9292 with live preview

# Run linter (catches Liquid errors, performance issues, accessibility)
shopify theme check --path ./theme-dev

# Push changes to theme
shopify theme push --store earlbear-dev --path ./theme-dev --theme <THEME_ID>
```

**Forking Dawn (recommended starting point):**
```bash
# Clone Dawn from GitHub
git clone https://github.com/Shopify/dawn.git theme-dev
cd theme-dev

# Remove Dawn's git history, start fresh
rm -rf .git
git init

# Start customizing
shopify theme dev --store earlbear-dev
```

### Custom Section Development Guide

**Step 1: Design the section**
- What content does it display?
- What should be configurable in the theme editor?
- What blocks (repeatable sub-elements) does it need?
- Mobile vs desktop layout?

**Step 2: Write the Liquid template**
```liquid
{%- comment -%} sections/brand-story.liquid {%- endcomment -%}

<section class="brand-story section-{{ section.id }}">
  <div class="brand-story__container page-width">
    {% if section.settings.heading != blank %}
      <h2 class="brand-story__heading">{{ section.settings.heading }}</h2>
    {% endif %}

    <div class="brand-story__content">
      {% if section.settings.image != blank %}
        <div class="brand-story__image">
          {{ section.settings.image | image_url: width: 800 | image_tag:
            loading: 'lazy',
            widths: '400, 600, 800',
            class: 'brand-story__img'
          }}
        </div>
      {% endif %}

      <div class="brand-story__text">
        {{ section.settings.text }}
      </div>
    </div>

    {% if section.blocks.size > 0 %}
      <div class="brand-story__values">
        {% for block in section.blocks %}
          <div class="brand-story__value" {{ block.shopify_attributes }}>
            <h3>{{ block.settings.title }}</h3>
            <p>{{ block.settings.description }}</p>
          </div>
        {% endfor %}
      </div>
    {% endif %}
  </div>
</section>

{% schema %}
{
  "name": "Brand Story",
  "settings": [
    { "type": "text", "id": "heading", "label": "Heading", "default": "Our Story" },
    { "type": "image_picker", "id": "image", "label": "Story image" },
    { "type": "richtext", "id": "text", "label": "Story text" }
  ],
  "blocks": [
    {
      "type": "value",
      "name": "Brand Value",
      "settings": [
        { "type": "text", "id": "title", "label": "Value title" },
        { "type": "text", "id": "description", "label": "Description" }
      ]
    }
  ],
  "presets": [{ "name": "Brand Story" }],
  "max_blocks": 6
}
{% endschema %}
```

**Step 3: Add styles (CSS)**
```css
/* assets/section-brand-story.css */
.brand-story {
  padding: 4rem 0;
}
.brand-story__container {
  max-width: var(--page-width);
  margin: 0 auto;
  padding: 0 1.5rem;
}
.brand-story__content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2rem;
  align-items: center;
}
.brand-story__values {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
  margin-top: 3rem;
}
@media (max-width: 749px) {
  .brand-story__content {
    grid-template-columns: 1fr;
  }
}
```

**Step 4: Load the CSS conditionally**
In `layout/theme.liquid`, add:
```liquid
{%- if request.page_type == 'index' -%}
  {{ 'section-brand-story.css' | asset_url | stylesheet_tag }}
{%- endif -%}
```

Or inline in the section itself:
```liquid
{{ 'section-brand-story.css' | asset_url | stylesheet_tag }}
```

**Step 5: Deploy via CLI or ebshop**
```bash
# Via Shopify CLI (full theme push)
shopify theme push --store earlbear-dev --path ./theme-dev

# Via ebshop (individual asset upload)
./bin/ebshop theme update-asset <THEME_ID> \
  --key "sections/brand-story.liquid" \
  --value-file ./theme-dev/sections/brand-story.liquid

./bin/ebshop theme update-asset <THEME_ID> \
  --key "assets/section-brand-story.css" \
  --value-file ./theme-dev/assets/section-brand-story.css
```

### Theme Settings Schema Design

The `config/settings_schema.json` defines the theme editor's "Theme settings" panel:

```json
[
  {
    "name": "theme_info",
    "theme_name": "EarlBear Custom",
    "theme_version": "1.0.0",
    "theme_author": "EarlBear",
    "theme_documentation_url": "https://github.com/earlbear/theme",
    "theme_support_url": "https://earlbear.com/support"
  },
  {
    "name": "Colors",
    "settings": [
      { "type": "color", "id": "colors_primary", "label": "Primary", "default": "#5C3D2E" },
      { "type": "color", "id": "colors_secondary", "label": "Secondary", "default": "#C4956A" },
      { "type": "color", "id": "colors_accent", "label": "Accent", "default": "#2D5F4A" },
      { "type": "color", "id": "colors_background", "label": "Background", "default": "#F5F0EB" },
      { "type": "color", "id": "colors_text", "label": "Text", "default": "#2C2C2C" }
    ]
  },
  {
    "name": "Typography",
    "settings": [
      { "type": "font_picker", "id": "type_header_font", "label": "Heading font", "default": "assistant_n4" },
      { "type": "font_picker", "id": "type_body_font", "label": "Body font", "default": "assistant_n4" },
      { "type": "range", "id": "heading_scale", "label": "Heading size scale", "min": 80, "max": 150, "step": 5, "default": 100, "unit": "%" }
    ]
  },
  {
    "name": "Layout",
    "settings": [
      { "type": "range", "id": "page_width", "label": "Page width", "min": 1000, "max": 1600, "step": 100, "default": 1200, "unit": "px" },
      { "type": "range", "id": "spacing_sections", "label": "Space between sections", "min": 0, "max": 100, "step": 4, "default": 36, "unit": "px" }
    ]
  },
  {
    "name": "Social media",
    "settings": [
      { "type": "text", "id": "social_instagram_link", "label": "Instagram" },
      { "type": "text", "id": "social_twitter_link", "label": "X (Twitter)" },
      { "type": "text", "id": "social_facebook_link", "label": "Facebook" }
    ]
  }
]
```

### Theme Quality Checklist

Before publishing a custom theme:

- [ ] **Accessibility:** All images have alt text, color contrast ratio >= 4.5:1, keyboard navigable, screen reader tested
- [ ] **Performance:** Lighthouse score > 80, lazy-loaded images, minimal JS, CSS below 100KB
- [ ] **Responsive:** Tested at 320px, 768px, 1024px, 1440px widths
- [ ] **Browser support:** Chrome, Safari, Firefox, Edge (latest 2 versions)
- [ ] **Content flexibility:** Sections work with 0 items, 1 item, and max items
- [ ] **i18n ready:** All strings use `{{ 'key' | t }}` not hardcoded text
- [ ] **SEO:** Proper heading hierarchy (h1 -> h2 -> h3), structured data on product pages, meta tags
- [ ] **Cart/checkout:** Add to cart works, cart updates, checkout redirects correctly
- [ ] **Password page:** Works correctly (for unpublished stores)
- [ ] **Theme check passes:** `shopify theme check` reports 0 errors
- [ ] **Preview in editor:** All sections appear in customizer with correct controls

### Shopify Theme Resources

| Resource | URL |
|----------|-----|
| Dawn source code | https://github.com/Shopify/dawn |
| Liquid reference | https://shopify.dev/docs/api/liquid |
| Theme architecture | https://shopify.dev/docs/themes/architecture |
| Section schema | https://shopify.dev/docs/themes/architecture/sections/section-schema |
| Theme check (linter) | https://shopify.dev/docs/themes/tools/theme-check |
| Shopify CLI themes | https://shopify.dev/docs/api/shopify-cli/theme |
| Dawn design decisions | https://github.com/Shopify/dawn/discussions |
| Theme Store requirements | https://shopify.dev/docs/themes/store/requirements |
| Performance best practices | https://shopify.dev/docs/themes/best-practices/performance |
| Accessibility guidelines | https://shopify.dev/docs/themes/best-practices/accessibility |

---

## Integration with Other Skills

| Skill | When to use |
|-------|-------------|
| `/manage-shopify-store` | General store operations (products, orders, etc.) |
| `/seed-shopify-store` | Populate store with test data before theming |
| `/leveraging-shopify-cli` | CLI command reference |
| `/setup-shopify` | Initial store + credential setup |
| `/conform-store` (future) | Declarative store state management from manifest |
