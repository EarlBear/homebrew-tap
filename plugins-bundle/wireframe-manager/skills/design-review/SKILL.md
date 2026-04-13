---
name: design-review
description: Run a principal product designer-level visual design review of all 12 theme wireframes. Captures screenshots via Docker, evaluates typography, aesthetics, spacing, emotional warmth, and human feel. Documents findings as actionable markdown tasks and iterates until a principal designer would approve.
user_invocable: true
---

# Design Review Skill

> **Context:** This skill operates in the `wireframes/` directory. After making changes, run `make wire-export` to export static builds, then `make dist` to rebuild `dist/public/` with encryption.

Run a comprehensive design review of all EarlBear wireframe themes from the perspective of a principal product designer.

## Workflow

### Step 1: Generate timestamp and capture screenshots

```bash
export RUN_ID=$(date -u +"%Y-%m-%dT%H-%M")
docker compose --profile qa run --rm -e RUN_ID=$RUN_ID screenshots
```

This creates `qa-feedback/${RUN_ID}-screenshots/` with:
- `index-desktop.png` — theme picker overview
- `{theme}-desktop.png` and `{theme}-mobile.png` — full-page overviews for all 12 themes
- `{theme}/hero.png`, `{theme}/how-it-works.png`, etc. — **section-level crops at 1:1 viewport scale** for desktop

### Step 2: Review screenshots

**CRITICAL: Review section-level crops, not just full-page overviews.** Full-page screenshots compress the entire page into a small image where layout bugs (text wrapping, overflow, alignment) are invisible. The section-level crops show each section at actual viewport scale — this is where you catch real issues like:
- Text wrapping word-by-word in narrow containers
- Grid columns collapsing unexpectedly
- Alignment/spacing issues between elements
- Accent colors that don't contrast enough at real size

For each theme, review **both** the full-page overview (for overall flow and rhythm) and the individual section crops (for detail quality).

Evaluate each theme against the **Design Review Checklist** below. Think like a principal product designer — someone who cares about:

**Typography**
- Are the correct theme-specific fonts rendering? (not falling back to system fonts)
- Is heading/body hierarchy clear and intentional?
- Is there variety in font weights (700 headings → 600 labels → 400 body → 300 descriptions)?
- Do font sizes feel proportional and readable at all viewport sizes?
- Do fonts match the theme's mood? (e.g., Playfair Display for formal, Space Grotesk for tech-forward, DM Serif Display for warm)

**Contrast & Readability**
- Is hero text legible on the gradient background? (light themes need text-shadow or darker gradients)
- Are card surfaces visually distinct from their background? (light themes need adaptive shadows)
- Is muted text still readable (not too faint)?
- Do accent colors pop against their backgrounds? (watch for near-invisible accents like silver on white)
- Does the hero-to-body transition feel smooth? (gradient fade between dark hero and light body)

**Spacing & Layout**
- Is there adequate breathing room between sections (96px+ on desktop)?
- Does card internal padding feel generous (not cramped)?
- Do mobile layouts stack cleanly without horizontal overflow?
- Is vertical rhythm consistent?
- Do timeline connectors have appropriate spacing on mobile (shorter than desktop)?

**Visual Variety** (the "template test")
- Do sections use varied layouts? (timeline, editorial 2-col, grid, full-width)
- Are there decorative accent lines/dividers breaking visual monotony?
- Do testimonials have large decorative quote marks?
- Is there visual staggering (e.g., offset card heights) to break grid uniformity?
- Does the page have background texture/pattern on light themes for warmth?

**Visual Depth & Cards**
- Do cards have appropriate shadow/depth for the theme mode (light vs dark)?
- Does the highlighted Pricing card clearly stand out (scale, border, shadow)?
- Do hover states feel intentional and smooth?

**Aesthetic & Human Feel** (the "does this feel AI-generated?" test)
- Does the page feel crafted, not templated?
- Is there emotional warmth and personality, or does it feel sterile/corporate?
- Do colors feel cohesive and intentional, not random?
- Would a human designer be proud to show this to a client?
- Does the typography create rhythm (light descriptions, bold labels, elegant headings)?
- Do light themes have subtle texture/noise to avoid flat solid backgrounds?
- Do dark themes feel luxurious rather than just dark?

**Theme Differentiation**
- Does each theme feel distinct from the others?
- Are similar themes sufficiently differentiated? Known pairs to watch:
  - Latte vs Customer (both warm light — Customer should lean coral, Latte warm brown)
  - Customer vs Summer (both orange — Summer saturated/vibrant, Customer coral/terracotta)
  - Matcha vs Spring (both green — Matcha bold gold/zen, Spring lighter/airier/blossom)
  - Espresso vs Autumn (both dark brown — Autumn lighter browns, Espresso darker luxury)
- Does the theme's mood match its intended audience/context?
- Do different font pairings reinforce distinctness?

**Responsive**
- Does the hamburger menu work on mobile (animated toggle, slide-down drawer)?
- Do nav links close the drawer on click?
- Are touch targets large enough (48px+)?
- Does text remain readable at mobile sizes?
- Do timeline/grid layouts stack cleanly?

**Index/Theme-Picker Page**
- Does the index page match the design quality of the theme pages?
- Are theme cards informative (preview wireframe, swatches, font name, mood)?
- Does the page have proper visual hierarchy (header, stats, categories)?

**Feedback System**
- Is the feedback bar visible and unobtrusive?
- Does the cursor change to comment bubble icon in feedback mode?
- Are feedback pins, form, and bar using theme-independent colors (blue overlay)?

### Step 3: Document findings

Create a review file at `qa-feedback/${RUN_ID}-review-round-{N}.md` with this structure:

```markdown
# Design QA Review — Round {N}

**Date**: {YYYY-MM-DD}
**Reviewer**: Claude (Principal Product Designer lens)
**Scope**: All 12 themes, desktop + mobile viewports
**Build**: {description of what changed since last round}

---

## Action Items

### Critical
- [ ] {description of issue — what's wrong, why it matters, suggested fix}
- [x] {completed item from previous round} @done({ISO timestamp})

### Moderate
- [ ] {issue}

### Enhancement
- [ ] {nice-to-have improvement}

---

## Per-Theme Notes

### {Theme Name} ({light/dark}, {category})
![Desktop](./{RUN_ID}-screenshots/{theme}-desktop.png)

- {observation}
- [ ] {theme-specific action item}
- [x] {completed theme-specific item} @done({timestamp})

**Verdict**: {pass / needs work / strong}

---

## Summary

**Completed**: {X} of {Y} action items
**Remaining**: {Z} items ({breakdown by severity})
**Next**: {what Round N+1 should focus on}
```

### Key rules for documenting feedback:

1. **Every finding that needs action is a `- [ ]` task** — not prose, not a table row
2. **When a task is completed, mark it `- [x]` and append `@done({ISO timestamp})`**
3. **Screenshots are referenced with `![](./TIMESTAMP-screenshots/file.png)`** — the screenshot dir shares the timestamp prefix with the review file
4. **Per-theme notes include both observations (plain `-`) and action items (`- [ ]`)**
5. **Carry forward uncompleted `- [ ]` items** from previous rounds into the new round's Action Items section
6. **Previous round files are never modified** after a new round is created — they're the historical record

### Step 4: Act on findings

Implement the fixes identified in the review, prioritizing Critical > Moderate > Enhancement.

### Step 5: Re-screenshot and review

After fixes are applied:
1. Rebuild: `docker compose build frontend && docker compose up -d --force-recreate frontend`
2. Go back to Step 1 with a new timestamp
3. Create a new round review file
4. Mark completed items from the previous round as `- [x] ... @done()`
5. Repeat until a principal product designer would approve

### Completion criteria

The review loop is done when:
- All Critical items are `- [x]` @done
- All Moderate items are `- [x]` @done or explicitly deferred with rationale
- Enhancement items are documented for future work
- Each theme's verdict is "pass" or "strong"

## File structure

```
qa-feedback/
├── 2026-03-26T14-30-review-round-1.md
├── 2026-03-26T14-30-screenshots/
│   ├── index-desktop.png
│   ├── espresso-desktop.png
│   ├── espresso-mobile.png
│   └── ... (25 total)
├── 2026-03-26T15-00-review-round-2.md
├── 2026-03-26T15-00-screenshots/
│   └── ...
```

## Docker commands

```bash
# Capture screenshots (creates timestamped dir)
export RUN_ID=$(date -u +"%Y-%m-%dT%H-%M")
docker compose --profile qa run --rm -e RUN_ID=$RUN_ID screenshots

# Rebuild frontend after fixes
docker compose build frontend && docker compose up -d --force-recreate frontend

# Full rebuild (all services)
docker compose up --build -d
```
