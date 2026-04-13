# generate-deck

> **Context:** This skill operates in `earlbear-clis/deck-cli/`. Decks are built via the `ebdeck` CLI (a shell wrapper at `deck-cli/bin/ebdeck` that auto-bootstraps its own venv on first run). After generating or modifying decks, run `ebdeck gallery build` to update the HTML gallery, then `ebdeck publish --site ../earlbear-sites --name <deck-name>` to drop the gallery into earlbear-sites so `make dist` there picks it up and encrypts it.
>
> **Prerequisite:** ebdeck must be on your PATH. Add `earlbear-clis/deck-cli/bin` to your PATH, or symlink `deck-cli/bin/ebdeck` into `~/bin`. First invocation auto-bootstraps a hidden venv (~10s); subsequent invocations are instant.

Interactive deck generation skill. Gathers requirements via questions, generates content YAML, and renders presentation using the appropriate tool.

## Trigger

When the user asks to create, generate, or build a presentation, deck, pitch, or slides.

## Workflow

### Step 1: Gather Requirements

Use AskUserQuestion to collect the following. Skip questions where context is already clear from the conversation.

**Question 1 — Deck Type:**
- Investor Pitch (Series A, B, etc.)
- Sales / Customer Pitch
- Product Overview / Demo
- Company Update / Board Deck

**Question 2 — Output Tool:**
- Marp (Warm & Earthy style — CSS-rendered, exports PDF/PPTX)
- Slidev (Modern & Tech-Forward — dark theme, exports PPTX)
- python-pptx (Natural & Organic — native editable PPTX)
- Figma Slides (Polished & Interactive — native Figma, fully editable, requires Figma Desktop)

**Question 3 — Brand Overrides (if any):**
Ask if they want to use the default brand.yaml or customize colors/fonts for this deck.

### Step 2: Gather Content

Use AskUserQuestion to collect key content details based on deck type. For an investor pitch, ask about:
- Company name, one-liner, industry
- Key metrics (ARR, customers, growth, team size)
- The ask (raising amount, use of funds)
- Any specific slides to include or exclude

### Step 3: Read Brand Guidelines

Read `brand.yaml` from the project root. This contains:
- Company info (name, tagline, description)
- Color palette (primary, secondary, accent, background, surface, text colors)
- Font selections (heading, body, mono)
- Logo paths
- Slide defaults (aspect ratio, footer text)
- Style variants (warm, modern, nature, figma) — each tool uses a different variant

If brand.yaml is missing key information the user mentioned (e.g., they specified colors not in the file), update brand.yaml first.

### Step 4: Generate Content YAML

Generate a content YAML file in `content/` following this schema:

```yaml
metadata:
  title: "Deck Title"
  date: "YYYY-MM-DD"
  audience: "Target Audience"
  version: "1.0"

slides:
  - layout: title          # Full-bleed title slide
    title: "Company Name"
    subtitle: "Tagline"
    notes: "Speaker notes"

  - layout: section        # Section divider
    title: "Section Name"

  - layout: content        # Standard bullets
    title: "Slide Title"
    bullets:
      - "Bullet point 1"
      - "**Bold label** — detail text"
    notes: "Speaker notes"
    image: "assets/image.png"  # optional

  - layout: metrics        # 2x2 metric cards (max 4)
    title: "Key Metrics"
    metrics:
      - label: "Metric Name"
        value: "$1.8M"
        detail: "Context line"

  - layout: closing        # Final slide
    title: "Closing Message"
    subtitle: "contact@email.com"
```

Available layouts: `title`, `section`, `content`, `metrics`, `closing`.

### Step 5: Render

**For Docker-based tools** (Marp, Slidev, python-pptx):

Run the appropriate ebdeck subcommand. ebdeck orchestrates docker-compose services — rendering still happens in Docker containers with volume mounts.

```bash
ebdeck build marp-pptx --content <filename>.yaml    # Marp → PPTX
ebdeck build slidev-pptx --content <filename>.yaml  # Slidev → PPTX (slower, ~35s)
ebdeck build pptx --content <filename>.yaml         # python-pptx → native PPTX

# Optional PDF:
ebdeck build marp-pdf --content <filename>.yaml
```

Output lands in `poc-<tool>/output/`.

**For Figma Slides:**

Hand off to the `/run-figma-plugin` skill, which will:
1. Copy the content + brand YAML to clipboard
2. Open Figma Desktop
3. Launch the plugin
4. Guide the user to paste YAML and click Generate

If the plugin hasn't been imported yet, redirect to `/setup-figma-plugin` first.

### Step 6: Open & Review

**For Docker tools** — open the generated file:
```bash
open poc-<tool>/output/deck.pptx
```

**For Figma** — slides are already visible in Figma after generation.

Ask if they want adjustments to content, styling, or layout.

## Important Notes

- Read the per-tool nuance files in `.claude/skills/generate-deck/nuances/` before generating — each tool has specific formatting requirements.
- Content YAML is the single source of truth — all three tools read the same format.
- Brand guidelines in `brand.yaml` should be read every time, not assumed from memory.
- Prefer PPTX output over PDF unless the user requests PDF.
- Speaker notes should be included on every slide — they're valuable for the presenter.
- For investor decks: keep slides concise, data-driven, max 4 bullets per slide, use metrics layout for numbers.
- For metrics layout: max 4 metrics per slide for clean 2x2 grid.
- The content YAML filename should be descriptive (e.g., `series-a-pitch.yaml`, `q1-board-update.yaml`).
