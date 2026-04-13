# Figma Slides — Polished & Interactive

Style variant: `brand.styles.figma`

## How It Works

Unlike the other three tools, Figma Slides does NOT run in Docker. It's a Figma plugin that the user runs inside Figma Desktop.

**Flow:** Content YAML + Brand YAML → pasted into plugin UI → Plugin API creates slides in Figma

## Rendering Details

- **Canvas:** 1920×1080px (Figma Slides default, 16:9)
- **Positioning:** Absolute pixel coordinates (not inches like python-pptx, not CSS like Marp/Slidev)
- **Colors:** Figma uses `{r, g, b}` in 0-1 range, not hex strings — the plugin converts automatically
- **Fonts:** Loaded via `figma.loadFontAsync()` — must be available in user's Figma account. Falls back to Inter.
- **Shapes:** `figma.createRectangle()` for backgrounds, accent bars, metric cards
- **Text:** `figma.createText()` for all text elements

## Key Differences from Other Tools

| Aspect | Marp/Slidev/python-pptx | Figma Slides |
|--------|------------------------|--------------|
| Build | `ebdeck build <target>` | `ebdeck figma build` (build only) |
| Run | Docker container | User runs plugin in Figma |
| Input | File paths (CLI args) | Pasted YAML in plugin UI |
| Output | .pptx / .pdf file | Native Figma document |
| Editable | python-pptx only | Fully editable (native Figma) |
| Automation | `make permutations` | Manual per-deck |

## Content YAML Notes

The same content YAML schema works for all four tools. No Figma-specific fields needed.

Supported layouts: `title`, `section`, `content`, `metrics`, `closing` — same as all other tools.

## Gotchas

- **Slides file required:** Plugin only works in Figma Slides files (editorType: `["slides"]`). Will not appear in regular Figma Design or FigJam files.
- **Appends, doesn't replace:** Each "Generate" run appends slides. User must delete existing slides before re-generating.
- **No image support:** The `image` field in content YAML is ignored — Figma plugins can't load local filesystem images. Future enhancement: support image URLs or base64.
- **Font fallback:** If brand fonts (Playfair Display, Source Sans Pro) aren't in the user's Figma account, text renders in Inter. This changes the visual feel significantly.
- **No speaker notes:** Figma Slides doesn't have a speaker notes API equivalent — the `notes` field in content YAML is ignored.
- **No gradient fills:** `hero_gradient` in brand.yaml is kept for schema consistency but Figma uses solid fills. The plugin uses `primary_override` for dark backgrounds instead.
- **Bold markers:** `**bold**` markers in bullets are stripped to plain text (same as python-pptx).

## When to Recommend Figma

Recommend Figma Slides when the user:
- Wants to **edit slides visually** after generation (drag, resize, restyle)
- Needs to **collaborate in real-time** with others on the deck
- Is already working in **Figma's ecosystem** (design team, brand assets in Figma)
- Wants **pixel-perfect control** over the final output
- Plans to **present directly** from Figma Slides (built-in presenter mode)

Do NOT recommend when:
- User needs **automated batch generation** (use python-pptx or Marp)
- User needs **PDF output** (use Marp)
- User doesn't have **Figma Desktop** installed
- User needs **PowerPoint-compatible** output (use python-pptx)
