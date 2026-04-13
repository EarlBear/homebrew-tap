# python-pptx Nuances

## Style: Natural & Organic

Uses the `nature` style variant from brand.yaml. Forest greens with gold accent.

## Rendering Pipeline

1. `generate.py` reads brand.yaml + content YAML
2. Builds slides programmatically using the python-pptx API
3. Outputs a native `.pptx` file directly — no browser rendering

## Key Advantages

- **Native editable PPTX** — text is selectable, shapes are movable, fonts are embedded
- **Fastest generation** — ~1 second, no Chromium/browser overhead
- **Full PowerPoint compatibility** — opens in PowerPoint, Google Slides, Keynote
- Users can manually edit the output after generation

## Coordinate System

- python-pptx uses **inches** for positioning (via `Inches()` helper)
- Slide dimensions: 13.333" x 7.5" (widescreen 16:9)
- All element positions are absolute — there's no CSS flexbox/grid
- Coordinates are (left, top, width, height)

## Layout Implementation

Each layout type has its own renderer function:

- `slide_title()` — dark background, centered text, accent bar at bottom
- `slide_section()` — dark background, centered heading with underline
- `slide_content()` — light background, left-aligned title with accent bar, bullet points with dot markers
- `slide_metrics()` — light background, 2x2 card grid with accent left border
- `slide_closing()` — matches title slide style

## Styling Details

- Background colors set via `slide.background.fill.solid()`
- Text styling via `paragraph.font` properties (size, color, bold, name)
- Shapes use `MSO_SHAPE.ROUNDED_RECTANGLE` for cards, `MSO_SHAPE.RECTANGLE` for bars
- Accent bars are thin rectangles (0.06" height) positioned manually
- Bullet dots are small colored squares (0.12" x 0.12")

## Color Handling

- Colors must be `RGBColor` objects created from hex strings
- The `hex_to_rgb()` helper strips `#` prefix and converts
- Each style variant overrides `primary` and `accent` from brand.yaml

## Common Pitfalls

- **No CSS** — can't use flexbox, grid, or responsive layouts. All positioning is manual math
- **EMU precision** — `Inches()` converts to EMU (English Metric Units). Fractional inches work fine
- **Font availability** — if a font isn't installed on the rendering machine, PowerPoint substitutes. Since we generate in Docker (no fonts installed), stick to system fonts or accept substitution
- **Markdown in content** — `**bold**` markers in bullet text must be stripped manually (the `clean = bullet.replace("**", "")` pattern)
- **Speaker notes** — accessed via `slide.notes_slide.notes_text_frame.text`
- **Blank layout** — we use `prs.slide_layouts[6]` (Blank) to avoid default placeholder shapes
