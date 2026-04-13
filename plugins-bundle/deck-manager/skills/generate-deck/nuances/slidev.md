# Slidev Nuances

## Style: Modern & Tech-Forward

Uses the `modern` style variant from brand.yaml. Dark theme with red accent.

## Rendering Pipeline

1. `generate.js` reads brand.yaml + content YAML
2. Outputs a Slidev-flavored Markdown file
3. `@slidev/cli` (inside Docker) spins up Vite dev server, renders via Playwright → PPTX

## Key Formatting Rules — CRITICAL

Slidev's Markdown format is deceptively similar to Marp but has important differences:

### Frontmatter Structure

- The **first** `---...---` block is BOTH global config AND the first slide's frontmatter
- Do NOT add a separate global config block — it creates a blank slide 1
- Subsequent slides start with `---` followed by optional frontmatter then `---`

```markdown
---
title: 'Global Title'
layout: cover
---

# First Slide Content (this IS slide 1)

---
layout: center
---

# Second Slide
```

### Slides Without Frontmatter

For slides that don't need layout overrides, use just `---` as a separator with NO closing `---`:

```markdown
---

# Slide With Default Layout

- bullet 1
```

NOT:

```markdown
---
---

# This creates problems
```

### Global Styles

Place the `<style>` block at the **very end** of the file. Do NOT put it after the first frontmatter block — that renders it as visible content on slide 1.

## PPTX Caveats

- Like Marp, Slidev PPTX is **image-based** (slides rendered as screenshots)
- Export uses Playwright Chromium — `playwright-chromium` must be installed in Docker image
- Export is the **slowest** of all three tools (~35s vs 1-5s for others)
- The `npx @slidev/cli` has overhead on each run (downloads/resolves packages)
- "Failed to resolve dependency" warnings are normal and don't affect output

## Layout Names (Slidev built-in)

- `cover` — centered content, supports `background` gradient
- `center` — vertically + horizontally centered
- `default` — top-left aligned (used for content/metrics)
- `section` — Slidev's section layout (we use `center` instead for better control)

## Common Pitfalls

- **Blank first slide**: Caused by putting `<style>` or content between global frontmatter and first slide separator
- **Double frontmatter `--- ---`**: Creates an empty frontmatter block that Slidev may interpret as an extra slide
- **UnoCSS classes**: Slidev uses UnoCSS, so Tailwind-style classes (mt-4, grid, etc.) work but require the engine
- **Theme `none`**: We use no theme to avoid conflicts with our custom styles
