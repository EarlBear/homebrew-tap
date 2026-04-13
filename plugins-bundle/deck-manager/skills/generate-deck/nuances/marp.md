# Marp Nuances

## Style: Warm & Earthy

Uses the `warm` style variant from brand.yaml.

## Rendering Pipeline

1. `generate.js` reads brand.yaml + content YAML
2. Outputs a Marp-flavored Markdown file with inline `<style>` block
3. Marp CLI (inside Docker) renders via headless Chromium → PDF or PPTX

## Key Formatting Rules

- Slides are separated by `---` on its own line
- Slide layout class is set via `<!-- _class: layoutname -->` HTML comment BEFORE the slide content
- Speaker notes use HTML comments: `<!-- note text -->`
- The `<style>` block at the top applies to ALL slides — it's not per-slide
- Marp uses CSS for all theming — colors from brand.yaml are injected as literal CSS values

## PPTX Caveats

- **Marp PPTX is image-based** — each slide is rendered as an image, NOT editable text/shapes
- Good for visual fidelity (what you see in PDF = what you get in PPTX)
- Bad if the user needs to edit text in PowerPoint after generation
- If editability matters, recommend python-pptx instead

## PDF Export

- PDF export is the highest-fidelity output from Marp
- Fonts render correctly via Google Fonts CDN
- `--allow-local-files` flag is required for local image assets

## Layout Classes

- `title` — gradient background, centered, large heading
- `section` — dark background, centered heading with accent underline
- `content` — light background, left-aligned heading + bullet list
- `metrics` — light background, CSS grid of metric cards
- `closing` — gradient background, centered heading + subtitle

## Common Pitfalls

- Forgetting `<!-- _class: X -->` makes slides use default styling
- Markdown inside HTML blocks (like `<div>`) won't be parsed — use raw HTML there
- The `---` separator must have blank lines around it or Marp may not split slides correctly
- Chromium in Docker needs `--no-sandbox` flag (already handled in Dockerfile)
