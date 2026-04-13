# review-slides

> **Context:** This skill operates in `earlbear-clis/deck-cli/`. Decks are built via the `ebdeck` CLI (a shell wrapper at `deck-cli/bin/ebdeck` that auto-bootstraps its own venv on first run). After generating or modifying decks, run `ebdeck gallery build` to update the HTML gallery, then `ebdeck publish --site ../earlbear-sites --name <deck-name>` to drop the gallery into earlbear-sites so `make dist` there picks it up and encrypts it.
>
> **Prerequisite:** ebdeck must be on your PATH. Add `earlbear-clis/deck-cli/bin` to your PATH, or symlink `deck-cli/bin/ebdeck` into `~/bin`. First invocation auto-bootstraps a hidden venv (~10s); subsequent invocations are instant.

Visual quality review of generated slide decks. Converts slides to PNGs, evaluates each slide against a human-centered design checklist, and reports issues with specific fix recommendations.

## Trigger

When the user asks to review, evaluate, check, or QA a generated deck. Also run automatically after `/generate-deck` if the user opts in.

## Workflow

### Step 1: Convert to PNGs

Use LibreOffice (via Docker) or the tool's built-in export to convert the PPTX to individual PNG images:

```bash
# For any PPTX file:
docker run --rm -v "$(pwd)":/data \
  ghcr.io/linuxserver/libreoffice:latest \
  libreoffice --headless --convert-to png --outdir /data/review /data/path/to/deck.pptx

# Or use Marp's PNG export:
docker compose run --rm marp-png  # if target exists
```

If LibreOffice isn't available, use the python-pptx approach to extract slide dimensions and describe layouts textually.

### Step 2: Visual Review

Read each PNG image and evaluate against the checklist below. For each slide, report:
- **Pass/Fail** for each criterion
- **Specific issue** if failing
- **Suggested fix** (referencing the content YAML or generator code)

### Design Quality Checklist

#### Critical Issues (must fix)
- [ ] **Blank slide**: Slide is completely empty or shows only a background
- [ ] **Raw code/markup visible**: Frontmatter, CSS, HTML tags, or markdown syntax rendered as visible text (e.g., `layout: 'center' class: 'text-center'`)
- [ ] **Missing background**: Slide has no background color/gradient when one is expected (white slide in a dark theme)
- [ ] **Broken layout**: Content overlaps, text cut off, elements outside visible area
- [ ] **Invisible text**: Text color matches background color, making it unreadable

#### Spacing & Layout
- [ ] **Excessive whitespace**: More than 40% of slide area is empty below the content
- [ ] **Content crowding**: Text or elements too close together, no breathing room
- [ ] **Inconsistent margins**: Padding/margins vary between slides of the same layout type
- [ ] **Vertical alignment**: Content should be vertically centered or top-aligned consistently
- [ ] **Horizontal alignment**: Elements should align to a consistent left margin

#### Typography
- [ ] **Font consistency**: Same font family used across all slides (heading vs body)
- [ ] **Size hierarchy**: H1 > H2 > body text > captions — clear visual hierarchy
- [ ] **Readability**: Body text at least 16pt equivalent, adequate contrast ratio
- [ ] **Line spacing**: Bullets have enough spacing to not feel cramped

#### Color & Brand
- [ ] **Brand consistency**: Colors match the brand.yaml palette
- [ ] **Contrast**: Text has sufficient contrast against background (WCAG AA minimum)
- [ ] **Accent usage**: Accent color used sparingly for emphasis, not for large areas
- [ ] **Dark/light mode coherence**: If using dark backgrounds, ALL text on those slides is light

#### Content Quality
- [ ] **Bullet count**: Max 4-5 bullets per slide (investor deck best practice)
- [ ] **Bullet length**: Each bullet under ~15 words
- [ ] **Metrics format**: Numbers are large and prominent, labels secondary
- [ ] **Speaker notes present**: Every content slide has speaker notes
- [ ] **Title present**: Every slide has a clear title (except section dividers)

#### Slide-Type Specific
- [ ] **Title slide**: Company name prominent, tagline visible, no clutter
- [ ] **Section divider**: Clean, minimal, strong contrast
- [ ] **Metrics slide**: Cards evenly spaced, values visually dominant
- [ ] **Closing slide**: Contact info visible, consistent with title slide style

### Step 3: Generate Report

Output a summary table:

```
Slide | Layout  | Status | Issues
------|---------|--------|--------
1     | title   | ✓ Pass |
2     | section | ✗ Fail | Raw frontmatter visible as text
3     | content | ⚠ Warn | 6 bullets (max 5 recommended)
...
```

Then list critical issues first, followed by warnings.

### Step 4: Suggest Fixes

For each issue, provide:
1. Which file to edit (`content/*.yaml`, `poc-*/generate.js`, `brand.yaml`)
2. The specific change needed
3. Which make target to re-run

## Notes

- This checklist is a living document. Add new criteria when new failure modes are discovered.
- The raw-markup-as-text issue (screenshot from Slidev) is the #1 most common failure — always check for it.
- Compare across all three tools when reviewing — if an issue only appears in one tool, the fix is in that tool's generator, not the content YAML.
- Blank first slides are almost always a Slidev frontmatter issue.
