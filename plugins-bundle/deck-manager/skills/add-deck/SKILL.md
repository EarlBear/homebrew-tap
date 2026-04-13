# Add Deck

> **Context:** This skill adds a new deck type. Decks are generated from YAML content via the `ebdeck` CLI (which orchestrates Docker containers for Marp, Slidev, python-pptx) and published as a self-contained HTML gallery into `earlbear-sites/decks/<name>/` via `ebdeck publish --site ../earlbear-sites --name <name>`. From there `make dist` in earlbear-sites picks up the gallery and encrypts it. The existing `pitch-deck` (investor pitch) is the reference implementation.
>
> **Prerequisite:** ebdeck must be on your PATH. Add `earlbear-clis/deck-cli/bin` to your PATH, or symlink `deck-cli/bin/ebdeck` into `~/bin`. First invocation auto-bootstraps a hidden venv (~10s); subsequent invocations are instant.

## When to trigger

User says things like:
- "add a deck", "new deck", "create a new presentation"
- "make a customer onboarding deck", "build a sales deck"
- "I want another deck type"

## Current structure

```
earlbear-clis/deck-cli/
├── content/
│   └── investor-pitch.yaml    # Content for the pitch deck
├── brand.yaml                 # Default brand config
├── brands/                    # 12 brand variants
├── Makefile                   # ebdeck install/test/lint/clean targets
├── pyproject.toml             # ebdeck Python package
├── src/ebdeck/                # CLI source (typer + docker compose orchestration)
├── docker-compose.yaml        # Marp, Slidev, python-pptx services
├── poc-marp/                  # Marp renderer
├── poc-slidev/                # Slidev renderer
├── poc-pptx/                  # python-pptx renderer
└── scripts/
    ├── permutations.sh        # All brands × all tools
    ├── generate-thumbnails.py # PPTX → PNG
    └── build-gallery.py       # HTML gallery with inline thumbnails
```

Published to: `earlbear-sites/decks/<name>/gallery.html` (via `ebdeck publish`), which `make dist` in earlbear-sites then encrypts and exposes at `dist/public/decks/<name>/gallery.html`.

## Workflow

### Step 1: Gather info

Ask the user:
1. **What type of deck?** (e.g., sales, onboarding, product overview, team intro)
2. **Who is the audience?** This determines `audience_questions` on each slide
3. **How many slides?** Typical: 8-15
4. **Which brands?** Usually all 12, but could be a subset
5. **Name?** Kebab-case for the content file (e.g., `customer-onboarding`, `sales-pitch`)

### Step 2: Create content YAML

Create `earlbear-clis/deck-cli/content/{name}.yaml` following the same schema as `investor-pitch.yaml`:

```yaml
meta:
  title: "Deck Title"
  date: "2026-03-27"
  audience: "Target audience"
  version: "1.0"

slides:
  - layout: title
    title: "Main Title"
    subtitle: "Subtitle"
    notes: "Speaker notes"
    audience_questions:
      Role:
        - "Question this slide answers"

  - layout: content
    title: "Slide Title"
    bullets:
      - "Bullet point"
    notes: "Notes"
    audience_questions:
      Role:
        - "Question"
```

**Content tenet:** Every slide must answer a question. Always include `audience_questions`.

You can also use the `/generate-deck` skill which interactively creates the content YAML.

### Step 3: Generate the deck

```bash
# Single tool, default brand
ebdeck build pptx --content {name}.yaml

# All 3 tools, default brand
ebdeck build all --content {name}.yaml

# All 12 brands × 3 tools = 36 permutations
ebdeck permutations --content {name}.yaml
```

### Step 4: Generate gallery

```bash
ebdeck gallery thumbnails
ebdeck gallery build
```

This produces `earlbear-clis/deck-cli/dist/gallery.html` — a self-contained HTML gallery with base64-embedded thumbnails.

### Step 5: Publish to earlbear-sites

From `earlbear-clis/deck-cli/`, drop the built gallery + brand permutations into the sibling earlbear-sites checkout:

```bash
ebdeck publish --site ../earlbear-sites --name {name}
```

This creates `earlbear-sites/decks/{name}/` containing `gallery.html` plus one subdir per brand permutation. `earlbear-sites/Makefile`'s `dist-collect` target auto-discovers every `decks/*/` dir, and `earlbear-sites/scripts/generate-index.sh` auto-discovers every `decks/*/gallery.html` and emits a catalog card — no per-deck wiring required.

### Step 6: Build and test in earlbear-sites

```bash
cd ../earlbear-sites
make dist
make dist-validate
make dist-preview
```

### Step 7: Review (optional)

Run `/review-slides` to check visual quality of the generated decks.

### Step 8: Commit

Remind the user to commit:
- The new content YAML in `earlbear-clis/deck-cli/content/{name}.yaml`
- The `earlbear-sites/decks/{name}/` directory (gallery.html + brand subdirs)

## Key constraints

- **Content YAML is the source of truth.** Never manually create PPTX files.
- **Every slide needs `audience_questions`.** Forces clarity on who each slide is for.
- **Gallery must be self-contained HTML.** The `build-gallery.py` script already produces base64-embedded thumbnails — no separate image files.
- **No binary files in dist/public/.** PPTXs, ZIPs, and PNGs are NOT published. They stay in `earlbear-clis/deck-cli/dist/` for local use. Future: authenticated download links.
- **Brand system is shared.** All deck types use the same 12 brand variants.
- **File naming:** `earlbear-clis/deck-cli/content/{descriptive-name}.yaml` (kebab-case)
