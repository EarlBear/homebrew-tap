# run-figma-plugin

> **Context:** This skill operates in `earlbear-clis/deck-cli/`. Decks are built via the `ebdeck` CLI (a shell wrapper at `deck-cli/bin/ebdeck` that auto-bootstraps its own venv on first run). After generating or modifying decks, run `ebdeck gallery build` to update the HTML gallery, then `ebdeck publish --site ../earlbear-sites --name <deck-name>` to drop the gallery into earlbear-sites so `make dist` there picks it up and encrypts it.
>
> **Prerequisite:** ebdeck must be on your PATH. Add `earlbear-clis/deck-cli/bin` to your PATH, or symlink `deck-cli/bin/ebdeck` into `~/bin`. First invocation auto-bootstraps a hidden venv (~10s); subsequent invocations are instant.

Open Figma, launch the Earlbear Deck Generator plugin, and help the user generate slides from content + brand YAML. Assumes the plugin has already been imported (if not, redirect to `/setup-figma-plugin`).

## Trigger

When the user asks to generate slides in Figma, run the Figma plugin, or create a Figma presentation. Also triggered when the user selects "Figma Slides" as the output tool in `/generate-deck`.

## Workflow

### Step 1: Pre-flight Checks

Verify the plugin is ready:

```bash
# Check build artifacts exist
ls poc-figma/dist/main.js poc-figma/dist/ui.html
```

If missing, rebuild:
```bash
ebdeck figma build-local
```

### Step 2: Prepare Content

Determine which content and brand files to use. Either:

**A) Use existing content YAML:**
```bash
ls content/   # Show available content files
```
Ask which file to use if multiple exist.

**B) Generate new content first:**
If the user wants a new deck, redirect to `/generate-deck` with Figma as the target tool — it will generate the content YAML, then return here for the Figma step.

### Step 3: Open Figma and Launch Plugin

Use the automation script:

```bash
# If user has a specific Figma Slides file URL:
./scripts/figma-open.sh "figma://file/<file-key>"

# Or just open Figma:
./scripts/figma-open.sh
```

Then launch the plugin:

```bash
# Re-run last plugin (if already run once):
./scripts/figma-run-plugin.sh --rerun

# Or find it in the menu:
./scripts/figma-run-plugin.sh
```

**If AppleScript automation fails** (common with Electron apps), guide the user:
1. Open Figma Desktop
2. Open or create a **Figma Slides** file (File → New → Presentation)
3. Go to: **Plugins → Development → Earlbear Deck Generator**

### Step 4: Incremental Clipboard — Content YAML

The plugin needs two YAML inputs pasted one at a time. Use the helper script or do it manually.

**Option A — Interactive (both at once with pauses):**
```bash
./scripts/figma-copy-yaml.sh both <content-file>.yaml <brand-file>.yaml
```
This copies content to clipboard, waits for the user to paste, then copies brand.

**Option B — Manual one at a time:**

First, copy content YAML to clipboard:
```bash
cat content/<filename>.yaml | pbcopy
```
Tell the user: **"Content YAML is on your clipboard. Paste it into the Content YAML field with Cmd+V."**

Wait for the user to confirm they've pasted it.

### Step 5: Incremental Clipboard — Brand YAML

Then copy brand YAML to clipboard:
```bash
cat <brand-file>.yaml | pbcopy
```
Tell the user: **"Brand YAML is on your clipboard. Paste it into the Brand YAML field with Cmd+V."**

Wait for the user to confirm, then tell them to **click Generate Slides**.

**IMPORTANT:** These must be done sequentially — only one thing can be on the clipboard at a time. Always wait for the user to confirm they've pasted before copying the next file.

### Step 6: Generate and Wait

1. User clicks **Generate Slides**
2. The progress bar will show each slide being created
3. Wait for the success message with the slide count

### Step 7: Post-Generation

After slides are generated:

1. Ask the user if the slides look correct
2. If issues, check:
   - Are brand colors applied? (compare to `styles.figma` in the brand file)
   - Are all layouts rendering? (title, section, content, metrics, closing)
   - Are fonts loading? (should be heading + body fonts from brand.yaml)
3. If the user wants to regenerate:
   - Edit the content YAML
   - Delete the existing slides in Figma (select all → delete)
   - Re-run the plugin with updated content

Optionally, suggest running `/review-slides` if the user wants a quality check (note: review-slides works on PPTX files, not Figma directly — the user would need to export from Figma first).

## Shortcuts Reference

| Action | Method |
|--------|--------|
| Re-run last plugin | `Cmd+Option+P` in Figma or `./scripts/figma-run-plugin.sh --rerun` |
| Copy content to clipboard | `./scripts/figma-copy-yaml.sh content <file>.yaml` |
| Copy brand to clipboard | `./scripts/figma-copy-yaml.sh brand <file>.yaml` |
| Interactive both (with pauses) | `./scripts/figma-copy-yaml.sh both <content> <brand>` |
| Open Figma | `./scripts/figma-open.sh` |
| Open specific file | `./scripts/figma-open.sh "figma://file/<key>"` |
| New Slides file | `./scripts/figma-open.sh --new-slides` |

## Important Notes

- The plugin ONLY works in **Figma Slides** files — if the user is in a regular Figma Design file, the plugin won't appear in the menu
- If the plugin hasn't been imported yet, redirect to `/setup-figma-plugin` first
- Each "Generate" run **appends** slides to the current file — if re-generating, remind the user to delete existing slides first
- The plugin reads YAML from the UI text fields, not from files — content must be copy/pasted
- AppleScript automation is best-effort. Always have manual fallback instructions ready.
- The `Cmd+Option+P` shortcut re-runs the last plugin — very useful for iterative development
