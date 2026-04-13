# slide-design-review

> **Context:** This skill operates in `earlbear-clis/deck-cli/`. Decks are built via the `ebdeck` CLI (a shell wrapper at `deck-cli/bin/ebdeck` that auto-bootstraps its own venv on first run). After generating or modifying decks, run `ebdeck gallery build` to update the HTML gallery, then `ebdeck publish --site ../earlbear-sites --name <deck-name>` to drop the gallery into earlbear-sites so `make dist` there picks it up and encrypts it.
>
> **Prerequisite:** ebdeck must be on your PATH. Add `earlbear-clis/deck-cli/bin` to your PATH, or symlink `deck-cli/bin/ebdeck` into `~/bin`. First invocation auto-bootstraps a hidden venv (~10s); subsequent invocations are instant.

Review generated slide decks through the lens of a principal presentation designer. Evaluate visual hierarchy, spacing, typography scale, brand cohesion, and audience impact. Produce actionable fixes mapped to specific renderer code.

## Trigger

When the user shares screenshots of generated slides and asks for design feedback, quality review, or spacing/sizing fixes. Also after `/generate-deck` or `/run-figma-plugin` when the user wants to polish the output.

## Workflow

### Step 1: Run Dimension Calculator

Before reviewing, run the golden-ratio dimension calculator to establish baseline recommendations:

```bash
# Full analysis with audit of current layout.ts values
SKILL_DIR=$(ls -d ~/.claude/plugins/cache/earlbear-claude-plugins/deck-manager/*/skills/slide-design-review 2>/dev/null | tail -1)
bash "$SKILL_DIR/slide-dimensions.sh" --audit

# Or compute hierarchy from a specific title size
bash "$SKILL_DIR/slide-dimensions.sh" --title-size 96
```

This outputs several sections. Here's how to interpret and apply each:

**Golden Section Lines** — The horizontal line (y=667 for 1080p) is where the eye naturally rests. On hero/title slides, the title baseline should sit at or above this line. Content below it feels "sinking."

**Optical Center** — (960, 413) for 1080p. This is where centered titles should sit — NOT mathematical center (960, 540). Mathematical center feels low. Place hero text so its vertical center aligns with ~y=413.

**Recommended Margins** — The script suggests pure golden-ratio margins (~226px sides). These are often too aggressive for content-heavy slides. **Practical rule**: use 60-70% of the suggested value for content slides, full value for hero/title slides that have less content.

**Font Size Hierarchy** — The most actionable output. Each level is the previous divided by φ (1.618). This creates natural visual hierarchy. When auditing: if two adjacent levels are too close in size (ratio < 1.3), hierarchy breaks down. If too far apart (ratio > 2.0), the smaller text feels orphaned.

**Metric Card Suggestions** — Recommended card dimensions for a 2×2 grid. Card width:height ratio of ~2.3:1 works well for metric cards (wide enough for values, not too tall).

**Spacing Suggestions** — Title-to-content gap should be hero_size × φ. Bullet spacing should be bullet_size × 2.5. These create rhythm without cramping.

**Audit** — Compares current `layout.ts` constants to golden-ratio recommendations. `✓` means aligned, `△` means divergent. Not every value needs to match exactly — use judgment. The hierarchy _ratios_ matter more than absolute values.

### Step 2: Capture Context

Before reviewing, understand:
- Which tool generated the slides (Marp, Slidev, python-pptx, Figma)
- The brand variant in use (check `styles.*` in the brand file)
- The target audience (investor, customer, internal)
- The slide canvas size (1920×1080 for Figma, 13.333"×7.5" for python-pptx)

### Step 3: Principal Designer Review

Evaluate each slide screenshot against the checklist below. Think like a principal presentation designer at a top-tier design firm — someone who has designed hundreds of investor decks and knows what commands attention in a boardroom.

### Design Review Checklist

#### Visual Hierarchy (most critical)
- [ ] **Title dominance**: Title should be the largest, most prominent element. At 10 feet away, can you read it?
- [ ] **Size contrast ratio**: Title should be 2-3× the size of body text. If title is 48pt, body should be 18-22pt, not 28pt
- [ ] **Information layering**: Eye should flow: Title → Key data/visual → Supporting text → Footer
- [ ] **Metric prominence**: On metric slides, the VALUE ($1.8M) should be the hero — at least 60pt, ideally 72-96pt
- [ ] **Single focal point**: Each slide should have ONE thing that commands attention first

#### Typography & Scale
- [ ] **Font size minimums**: Body text ≥ 18pt, bullets ≥ 20pt, slide titles ≥ 40pt, hero titles ≥ 64pt
- [ ] **Weight contrast**: Bold for titles/labels, Regular for body — never all-bold or all-regular
- [ ] **Line spacing**: 1.3-1.5× line height for body text. Bullets need breathing room (≥ 48px between items)
- [ ] **Font pairing**: Serif headings + sans-serif body is classic. Verify the pairing feels intentional, not accidental
- [ ] **Text width**: Lines should be 50-75 characters max. Full-width text walls are unreadable

#### Spacing & Composition
- [ ] **The 40% rule**: Content should occupy 40-60% of the slide area. Less = too sparse, more = too cramped
- [ ] **Vertical centering**: Content block should feel optically centered (slightly above mathematical center)
- [ ] **Consistent margins**: Same padding on all sides (or intentionally asymmetric). Currently: check left/right/top/bottom
- [ ] **Breathing room around title**: At least 60-80px between title and first content element
- [ ] **Footer isolation**: Footer should feel detached from content — at least 100px gap above
- [ ] **Card spacing**: Cards in grids should have equal gaps. Cards shouldn't touch edges

#### Color & Brand
- [ ] **Contrast ratio**: Light text on dark ≥ 4.5:1 (WCAG AA). Dark text on light ≥ 4.5:1
- [ ] **Accent restraint**: Accent color used for 1-2 elements per slide, not everywhere
- [ ] **Background consistency**: Same background color across slides of the same type
- [ ] **Dark slide mood**: Dark backgrounds should feel luxurious, not oppressive. Need enough contrast in the dark palette

#### Slide-Type Specific

**Title/Hero slides:**
- [ ] Company name should be enormous (72-96pt minimum)
- [ ] Tagline should be clearly secondary (50-60% of title size)
- [ ] Accent bar/divider adds polish but shouldn't compete with text
- [ ] Vertical position should be optical center (40% from top, not 50%)

**Content/Bullet slides:**
- [ ] Title anchors the top-left with authority
- [ ] Bullets start with generous top margin below title (not crammed)
- [ ] Bullet markers (dots/squares) are subtle, not competing with text
- [ ] Text doesn't run to the right edge — leave 15-20% right margin

**Metric/Card slides:**
- [ ] Values are the HERO — largest element on the slide (72pt+)
- [ ] Labels are clearly secondary (18-20pt)
- [ ] Detail text is tertiary (14-16pt, muted color)
- [ ] Cards feel like distinct containers with clear boundaries
- [ ] Grid is optically centered (slightly above mathematical center)

**Section dividers:**
- [ ] Minimal — just the section title, centered, with generous whitespace
- [ ] Strong contrast between text and background

**Closing slides:**
- [ ] Match the energy of the title slide
- [ ] CTA/contact info is readable but not overwhelming

### Step 4: Generate Findings

For each issue found, report:

```
Severity | Slide Type | Issue | Fix
---------|-----------|-------|-----
Critical | content   | Bullets too small (18pt), need 22pt+ | Update FONT_BULLET in layout.ts
Moderate | metrics   | Value font (52pt) not heroic enough, need 72pt | Update FONT_METRIC_VALUE
Enhancement | title  | Accent bar could be thicker for more presence | Update ACCENT_BAR_H
```

Severities:
- **Critical**: Fundamentally breaks readability or hierarchy. Must fix.
- **Moderate**: Noticeable to a designer, affects polish. Should fix.
- **Enhancement**: Nice-to-have refinement. Could fix.

### Step 5: Map Fixes to Code

For each finding, provide the specific file and constant/value to change:
- Layout constants: `poc-figma/src/utils/layout.ts`
- Per-layout rendering: `poc-figma/src/renderers/<layout>.ts`
- Font sizes: `FONT_*` constants in layout.ts
- Spacing: `MARGIN_*`, `CARD_*`, `*_GAP` constants
- Colors: brand.yaml `styles.figma` overrides

### Step 6: Apply Fixes and Re-review

After fixes are applied:
1. Rebuild: `ebdeck figma build-local`
2. Delete old slides in Figma
3. Re-run plugin
4. Take new screenshots
5. Re-review against the same checklist
6. Repeat until all Critical and Moderate items are resolved

#### Readability at Presentation Distance
- [ ] **10-foot rule for titles**: At 10 feet from a 55" screen, title must be legible. On 1920×1080, this means ≥48pt for slide titles, ≥72pt for hero titles
- [ ] **20-foot rule for body**: Body text must be legible at 20 feet in a conference room. On 1920×1080, this means ≥28pt for body/bullets
- [ ] **Pixel height check**: Text should be ≥3% of slide height for readability. On 1080p: 3% = 32px ≈ 24pt minimum for any non-caption text
- [ ] **Content-to-canvas ratio**: Content block should occupy 40-65% of slide height. If bullets + title only fill 30%, text is too small or spacing too tight
- [ ] **Fill factor**: Count the vertical pixels used by content (title + gaps + bullets + footer). Divide by 1080. If < 0.4, content needs to be larger or more spread out
- [ ] **Contrast at distance**: Muted/caption text that looks fine on a monitor may vanish on a projector. Muted text should be ≥40% opacity relative to primary text

#### Proportional Harmony & Golden Ratio
- [ ] **Golden ratio (1:1.618)**: Title-to-body size ratio should approximate the golden ratio. If title is 48pt, body should be ~30pt (48/1.618). If hero is 96pt, subtitle should be ~60pt or less.
- [ ] **Content placement**: The golden section of a 1080px slide is at ~668px from top (1080/1.618). Key focal elements (title on hero slides) should sit at or above this line.
- [ ] **Card proportions**: Card width-to-height should feel balanced. Ideal ratios: 3:1 for metric cards (wide), 4:3 for content cards.
- [ ] **Margin ratios**: Side margins should relate to top/bottom. A common ratio: side margins = 1.5× top margin.
- [ ] **White space distribution**: Follow the rule of thirds — divide the slide into a 3×3 grid. Key content should align with grid intersections.

## Tool-Specific Fix Mapping

Different tools require different fix approaches. Always identify which tool generated the slides before prescribing fixes.

### Figma Slides Plugin (`poc-figma/`)
Fixes go to TypeScript source files. Changes require rebuild (`ebdeck figma build-local`) and plugin re-run.
- **Layout constants**: `poc-figma/src/utils/layout.ts` — `FONT_*`, `MARGIN_*`, `CARD_*`, `SLIDE_*`
- **Per-layout rendering**: `poc-figma/src/renderers/<layout>.ts` — positioning logic, element creation
- **Font handling**: `poc-figma/src/utils/fonts.ts` — font loading, fallback logic
- **Colors**: `brand.yaml` → `styles.figma` overrides
- **Coordinate system**: 1920×1080px, absolute positioning, coordinates relative to slide after `appendChild()`

### python-pptx (`poc-pptx/`)
Fixes go to Python source. Changes require Docker rebuild (`ebdeck build images --no-cache`).
- **Positioning**: `poc-pptx/generate.py` — all positioning in `Inches()`, slide is 13.333"×7.5"
- **Font sizes**: `Pt()` values in renderer functions
- **Colors**: `hex_to_rgb()` + `RGBColor` — uses `brand.styles.nature`

### Marp (`poc-marp/`)
Fixes go to CSS theme generation in JavaScript. Changes require Docker rebuild.
- **Styling**: `poc-marp/generate.js` → `buildThemeCSS()` — inline CSS
- **Layout**: CSS classes per slide type — uses `brand.styles.warm`

### Slidev (`poc-slidev/`)
Fixes go to Markdown + CSS generation. Changes require Docker rebuild.
- **Styling**: `poc-slidev/generate.js` — global `<style>` block at EOF
- **Layout**: Per-slide frontmatter + HTML/Markdown — uses `brand.styles.modern`

## Important Notes

- **Presentation context matters**: Slides are projected on screens or shared on video calls. What looks fine at 100% zoom may be unreadable at presentation distance. When in doubt, go BIGGER.
- **Investor decks are data-forward**: Metrics should hit you in the face. If the value isn't the first thing your eye lands on, the hierarchy is wrong.
- **Less is more**: A slide with 3 well-spaced bullets beats 6 cramped ones. If content doesn't fit, split into two slides.
- **The squint test**: Squint at the slide. You should still be able to identify the title and primary content. If everything blurs together, the hierarchy needs work.
- **The golden ratio test**: Does the title/body size ratio approximate 1.618? Does the primary content sit at or above the golden section line (62% up from bottom)?
- **Consistency across slides**: Same font sizes, same margins, same bullet style across all slides of the same type. Inconsistency looks amateur.
- **Always identify the tool first**: The fix path is completely different for Figma (TypeScript constants) vs python-pptx (Python Inches) vs Marp/Slidev (CSS). Don't prescribe CSS fixes for a Figma issue.
