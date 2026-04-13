#!/usr/bin/env python3
"""
Build a self-contained HTML gallery from generated thumbnails.

Reads dist/thumbnails/ + brands/*.yaml → outputs dist/gallery.html
with base64-embedded images, CSS grid, filtering, and lightbox.

Usage: python build-gallery.py
"""

import os
import sys
import glob
import base64
import json
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

DIST_DIR = os.environ.get("DIST_DIR", "/data/dist")
BRANDS_DIR = os.environ.get("BRANDS_DIR", "/data/brands")
THUMB_DIR = os.path.join(DIST_DIR, "thumbnails")
OUTPUT_DIR = os.path.join(DIST_DIR, "output")
GALLERY_PATH = os.path.join(DIST_DIR, "gallery.html")


def load_brand_colors(brand_name):
    if not yaml:
        return {}
    for ext in [".yaml", ".yml"]:
        path = os.path.join(BRANDS_DIR, brand_name + ext)
        if os.path.exists(path):
            with open(path) as f:
                data = yaml.safe_load(f)
            return data.get("colors", {})
    return {}


def img_to_base64(path):
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return "data:image/png;base64," + data


def scan_thumbnails():
    decks = []
    brands = set()
    tools = set()

    for brand_dir in sorted(glob.glob(os.path.join(THUMB_DIR, "*"))):
        if not os.path.isdir(brand_dir):
            continue
        brand = os.path.basename(brand_dir)
        brands.add(brand)

        for tool_dir in sorted(glob.glob(os.path.join(brand_dir, "*"))):
            if not os.path.isdir(tool_dir):
                continue
            tool = os.path.basename(tool_dir)
            tools.add(tool)

            slides = sorted(glob.glob(os.path.join(tool_dir, "slide-*.png")))
            if not slides:
                continue

            pptx_files = glob.glob(os.path.join(OUTPUT_DIR, brand, tool, "*.pptx"))
            pptx_name = os.path.basename(pptx_files[0]) if pptx_files else "deck.pptx"
            colors = load_brand_colors(brand)

            decks.append({
                "brand": brand,
                "tool": tool,
                "slides": [img_to_base64(s) for s in slides],
                "num_slides": len(slides),
                "pptx_name": pptx_name,
                "colors": {
                    "primary": colors.get("primary", "#333"),
                    "secondary": colors.get("secondary", "#666"),
                    "accent": colors.get("accent", "#999"),
                    "background": colors.get("background", "#fff"),
                },
            })

    return decks, sorted(brands), sorted(tools)


# ── HTML template ──────────────────────────────────────────────
# Uses __PLACEHOLDER__ tokens instead of f-strings to avoid
# conflict with JavaScript template literals (both use ${}).

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Earlbear Deck Gallery — __DATE__</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background: #0D0B0A;
  color: #E8E4DF;
  min-height: 100vh;
}

header {
  padding: 32px 40px 24px;
  border-bottom: 1px solid #2A2420;
}

header h1 {
  font-family: Georgia, 'Playfair Display', serif;
  font-size: 1.8em;
  color: #C8A97E;
  font-weight: 400;
}

header .meta {
  color: #8C7A6B;
  font-size: 0.85em;
  margin-top: 4px;
}

.filters {
  padding: 16px 40px;
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
  border-bottom: 1px solid #2A2420;
  background: #141210;
  position: sticky;
  top: 0;
  z-index: 10;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-group label {
  font-size: 0.75em;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #8C7A6B;
  margin-right: 4px;
}

.chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.8em;
  cursor: pointer;
  border: 1px solid #3A2A22;
  background: transparent;
  color: #C8A97E;
  transition: all 0.15s;
  user-select: none;
}

.chip.active {
  background: #C8A97E;
  color: #0D0B0A;
  border-color: #C8A97E;
}

.chip:hover { border-color: #C8A97E; }

.chip-clear {
  font-size: 0.75em;
  color: #8C7A6B;
  cursor: pointer;
  margin-left: 4px;
}
.chip-clear:hover { color: #C8A97E; }

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
  padding: 24px 40px;
}

.card {
  background: #1A1614;
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  border: 1px solid #2A2420;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  border-color: #C8A97E;
}

.card img {
  width: 100%;
  display: block;
  aspect-ratio: 16/9;
  object-fit: cover;
  background: #0D0B0A;
}

.card-info {
  padding: 12px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-brand {
  font-family: Georgia, serif;
  font-size: 1em;
  color: #E8E4DF;
}

.card-tool {
  font-size: 0.7em;
  padding: 3px 10px;
  border-radius: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}

.card-tool.marp { background: #3A2A22; color: #C8A97E; }
.card-tool.slidev { background: #1A1A2E; color: #D4A574; }
.card-tool.pptx { background: #2A2018; color: #B8860B; }

.color-swatches {
  display: flex;
  gap: 4px;
  padding: 0 16px 12px;
}

.swatch {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 1px solid #3A2A22;
}

.lightbox {
  display: none;
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.92);
  z-index: 100;
  justify-content: center;
  align-items: center;
  flex-direction: column;
}

.lightbox.active { display: flex; }

.lightbox-close {
  position: absolute;
  top: 20px;
  right: 28px;
  font-size: 2em;
  color: #8C7A6B;
  cursor: pointer;
  background: none;
  border: none;
  z-index: 101;
}

.lightbox-close:hover { color: #C8A97E; }

.lightbox-title {
  font-family: Georgia, serif;
  font-size: 1.2em;
  color: #C8A97E;
  margin-bottom: 16px;
}

.lightbox-img {
  max-width: 85vw;
  max-height: 70vh;
  border-radius: 8px;
  box-shadow: 0 0 40px rgba(0,0,0,0.5);
}

.lightbox-nav {
  display: flex;
  gap: 16px;
  margin-top: 16px;
  align-items: center;
}

.lightbox-nav button {
  background: #2A2420;
  border: 1px solid #3A2A22;
  color: #C8A97E;
  padding: 8px 20px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.9em;
}

.lightbox-nav button:hover { background: #3A2A22; }

.lightbox-counter {
  color: #8C7A6B;
  font-size: 0.85em;
}

.empty-state {
  text-align: center;
  padding: 80px 40px;
  color: #8C7A6B;
  font-size: 1.1em;
}
</style>
</head>
<body>

<header>
  <h1>Earlbear Deck Gallery</h1>
  <div class="meta">__DATE__ &middot; __NUM_DECKS__ decks &middot; __NUM_BRANDS__ brands &middot; __NUM_TOOLS__ tools</div>
</header>

<div class="filters">
  <div class="filter-group">
    <label>Brand</label>
    __BRAND_CHIPS__
    <span class="chip-clear" onclick="clearFilter('brand')" style="display:none" id="clear-brand">&times; clear</span>
  </div>
  <div class="filter-group">
    <label>Tool</label>
    __TOOL_CHIPS__
    <span class="chip-clear" onclick="clearFilter('tool')" style="display:none" id="clear-tool">&times; clear</span>
  </div>
</div>

<div class="grid" id="grid"></div>
<div class="empty-state" id="empty" style="display:none">No decks match the current filters.</div>

<div class="lightbox" id="lightbox" onclick="closeLightbox(event)">
  <button class="lightbox-close" onclick="closeLightbox()">&times;</button>
  <div class="lightbox-title" id="lb-title"></div>
  <img class="lightbox-img" id="lb-img" src="" alt="">
  <div class="lightbox-nav">
    <button onclick="prevSlide(event)">&larr; Prev</button>
    <span class="lightbox-counter" id="lb-counter"></span>
    <button onclick="nextSlide(event)">Next &rarr;</button>
  </div>
</div>

<script>
const DECKS = __DECKS_JSON__;

const ALL_BRANDS = __BRANDS_JSON__;
const ALL_TOOLS = __TOOLS_JSON__;

// Empty sets = show all; once user clicks, only selected items show
let activeFilters = {
  brand: new Set(),
  tool: new Set()
};

let currentDeck = null;
let currentSlide = 0;

function renderGrid() {
  const grid = document.getElementById('grid');
  grid.innerHTML = '';
  let visible = 0;

  DECKS.forEach((deck, i) => {
    const brandOk = activeFilters.brand.size === 0 || activeFilters.brand.has(deck.brand);
    const toolOk = activeFilters.tool.size === 0 || activeFilters.tool.has(deck.tool);
    if (!brandOk || !toolOk) return;
    visible++;

    const card = document.createElement('div');
    card.className = 'card';
    card.onclick = () => openLightbox(i);

    const swatches = ['primary','secondary','accent','background']
      .map(k => '<div class="swatch" style="background:' + deck.colors[k] + '"></div>')
      .join('');

    card.innerHTML =
      '<img src="' + deck.slides[0] + '" alt="' + deck.brand + ' ' + deck.tool + '" loading="lazy">' +
      '<div class="card-info">' +
        '<span class="card-brand">' + deck.brand + '</span>' +
        '<span class="card-tool ' + deck.tool + '">' + deck.tool + '</span>' +
      '</div>' +
      '<div class="color-swatches">' + swatches + '</div>';

    grid.appendChild(card);
  });

  document.getElementById('empty').style.display = visible === 0 ? 'block' : 'none';
}

function toggleFilter(el) {
  const type = el.dataset.filter;
  const val = el.dataset.value;
  if (activeFilters[type].has(val)) {
    activeFilters[type].delete(val);
    el.classList.remove('active');
  } else {
    activeFilters[type].add(val);
    el.classList.add('active');
  }
  // Show/hide clear button
  var clearBtn = document.getElementById('clear-' + type);
  if (clearBtn) clearBtn.style.display = activeFilters[type].size > 0 ? 'inline' : 'none';
  renderGrid();
}

function clearFilter(type) {
  activeFilters[type].clear();
  document.querySelectorAll('.chip[data-filter="' + type + '"]').forEach(function(c) {
    c.classList.remove('active');
  });
  var clearBtn = document.getElementById('clear-' + type);
  if (clearBtn) clearBtn.style.display = 'none';
  renderGrid();
}

function openLightbox(deckIndex) {
  currentDeck = deckIndex;
  currentSlide = 0;
  showSlide();
  document.getElementById('lightbox').classList.add('active');
}

function closeLightbox(e) {
  if (e && e.target !== e.currentTarget && !e.target.classList.contains('lightbox-close')) return;
  document.getElementById('lightbox').classList.remove('active');
}

function showSlide() {
  const deck = DECKS[currentDeck];
  document.getElementById('lb-img').src = deck.slides[currentSlide];
  document.getElementById('lb-title').textContent = deck.brand + ' / ' + deck.tool;
  document.getElementById('lb-counter').textContent = 'Slide ' + (currentSlide + 1) + ' of ' + deck.slides.length;
}

function prevSlide(e) {
  if (e) e.stopPropagation();
  const deck = DECKS[currentDeck];
  currentSlide = (currentSlide - 1 + deck.slides.length) % deck.slides.length;
  showSlide();
}

function nextSlide(e) {
  if (e) e.stopPropagation();
  const deck = DECKS[currentDeck];
  currentSlide = (currentSlide + 1) % deck.slides.length;
  showSlide();
}

document.addEventListener('keydown', (e) => {
  if (!document.getElementById('lightbox').classList.contains('active')) return;
  if (e.key === 'Escape') closeLightbox();
  if (e.key === 'ArrowLeft') prevSlide();
  if (e.key === 'ArrowRight') nextSlide();
});

renderGrid();
</script>
</body>
</html>"""


def build_html(decks, brands, tools):
    today = date.today().isoformat()

    brand_chips = "".join(
        f'<span class="chip" data-filter="brand" data-value="{b}" onclick="toggleFilter(this)">{b}</span>'
        for b in brands
    )
    tool_chips = "".join(
        f'<span class="chip" data-filter="tool" data-value="{t}" onclick="toggleFilter(this)">{t}</span>'
        for t in tools
    )

    html = HTML_TEMPLATE
    html = html.replace("__DATE__", today)
    html = html.replace("__NUM_DECKS__", str(len(decks)))
    html = html.replace("__NUM_BRANDS__", str(len(brands)))
    html = html.replace("__NUM_TOOLS__", str(len(tools)))
    html = html.replace("__BRAND_CHIPS__", brand_chips)
    html = html.replace("__TOOL_CHIPS__", tool_chips)
    html = html.replace("__DECKS_JSON__", json.dumps(decks))
    html = html.replace("__BRANDS_JSON__", json.dumps(brands))
    html = html.replace("__TOOLS_JSON__", json.dumps(tools))

    return html


def main():
    decks, brands, tools = scan_thumbnails()

    if not decks:
        print("No thumbnails found. Run thumbnail generation first.")
        sys.exit(1)

    html = build_html(decks, brands, tools)

    os.makedirs(os.path.dirname(GALLERY_PATH), exist_ok=True)
    with open(GALLERY_PATH, "w") as f:
        f.write(html)

    size_kb = os.path.getsize(GALLERY_PATH) / 1024
    print(f"Gallery generated: {GALLERY_PATH}")
    print(f"  Decks: {len(decks)}")
    print(f"  Brands: {', '.join(brands)}")
    print(f"  Tools: {', '.join(tools)}")
    print(f"  Size: {size_kb:.0f} KB")


if __name__ == "__main__":
    main()
