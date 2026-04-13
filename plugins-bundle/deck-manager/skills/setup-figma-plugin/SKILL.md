# setup-figma-plugin

> **Context:** This skill operates in `earlbear-clis/deck-cli/`. Decks are built via the `ebdeck` CLI (a shell wrapper at `deck-cli/bin/ebdeck` that auto-bootstraps its own venv on first run). After generating or modifying decks, run `ebdeck gallery build` to update the HTML gallery, then `ebdeck publish --site ../earlbear-sites --name <deck-name>` to drop the gallery into earlbear-sites so `make dist` there picks it up and encrypts it.
>
> **Prerequisite:** ebdeck must be on your PATH. Add `earlbear-clis/deck-cli/bin` to your PATH, or symlink `deck-cli/bin/ebdeck` into `~/bin`. First invocation auto-bootstraps a hidden venv (~10s); subsequent invocations are instant.

Walk the user through building, importing, and first-run testing of the Earlbear Figma Slides plugin. This is a one-time setup — after import, the plugin persists in Figma.

## Trigger

When the user asks to set up, install, configure, or import the Figma plugin. Also use when the user hasn't set up the plugin yet and wants to use Figma for deck generation.

## Workflow

### Step 0: Grant Accessibility Permissions (one-time macOS setup)

The import and run scripts use AppleScript to automate Figma interactions (opening menus, sending keystrokes). macOS requires explicit Accessibility permission for the terminal app.

1. Open the Accessibility settings:
```bash
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
```

2. In **System Settings → Privacy & Security → Accessibility**:
   - Click the **+** button
   - Add the user's terminal app (iTerm2, Terminal, VS Code, etc.)
   - Toggle it **ON**

3. **Restart the terminal app** — permissions don't take effect for existing sessions

4. Verify it works:
```bash
osascript -e 'tell application "System Events" to keystroke "a" using command down' 2>&1 && echo "✓ Accessibility works" || echo "✗ Still no access"
```

If the user declines or can't grant Accessibility, that's fine — all scripts gracefully fall back to manual instructions. It just means the AppleScript automation won't send keystrokes.

### Step 1: Build the Plugin

Build the plugin and verify artifacts exist.

```bash
# Docker build (no local Node.js needed):
ebdeck figma build

# Or local build:
ebdeck figma install && ebdeck figma build-local
```

Verify output:
- Docker: `poc-figma/output/main.js` and `poc-figma/output/ui.html`
- Local: `poc-figma/dist/main.js` and `poc-figma/dist/ui.html`

If using Docker build, copy artifacts to `dist/` so the manifest can find them:
```bash
cp poc-figma/output/* poc-figma/dist/
```

### Step 2: Import Plugin into Figma

Run the import helper script:
```bash
./scripts/figma-import-plugin.sh
```

This script:
1. Checks the plugin is built
2. Copies the `manifest.json` path to clipboard
3. Opens Figma Desktop
4. Attempts to open the "Import plugin from manifest" dialog via AppleScript

**If the dialog opens automatically:**
1. Press `Cmd+Shift+G` to open "Go to folder"
2. Press `Cmd+V` to paste the manifest path (already on clipboard)
3. Click "Open"

**If it doesn't open (AppleScript can't reach in-app menus):**
Guide the user manually:
1. In Figma, click the hamburger menu (top-left)
2. Go to: **Plugins → Development → Import plugin from manifest...**
3. Navigate to the manifest file or press `Cmd+Shift+G` and paste

Tell the user the full manifest path:
```
<project-root>/poc-figma/manifest.json
```

### Step 3: Verify Import

After import, confirm the plugin appears:
1. Open any Figma Slides file (or create one: File → New → Presentation)
2. Go to: **Plugins → Development → Earlbear Deck Generator**
3. The plugin UI should appear with two YAML text areas and a "Generate Slides" button

If the plugin doesn't appear:
- Ensure Figma is set to a **Slides** file (not Design or FigJam) — the plugin's `editorType` is `["slides"]`
- Check that `poc-figma/dist/main.js` and `poc-figma/dist/ui.html` exist
- Try re-importing the manifest

### Step 4: First-Run Test

Help the user do a test run with sample data:

1. Read the content YAML from the project:
```bash
cat content/investor-pitch.yaml | pbcopy
```
Tell the user to paste it into the "Content YAML" field.

2. Read the brand YAML:
```bash
cat brand.yaml | pbcopy
```
Tell the user to paste it into the "Brand YAML" field.

3. Click "Generate Slides"

4. Verify:
   - Progress bar advances
   - Slides appear in the Figma canvas
   - Correct number of slides matches the content YAML
   - Colors match the brand's `styles.figma` variant
   - Text is readable and properly positioned

### Step 5: Confirm Setup Complete

Tell the user:
- The import is **one-time** — the plugin persists across Figma sessions
- To re-run later: use `./scripts/figma-run-plugin.sh` or `Cmd+Option+P` in Figma
- To rebuild after code changes: `ebdeck figma build` then re-run (Figma reloads from disk)
- For the full deck generation flow with Figma: use `/run-figma-plugin`

## Important Notes

- The plugin ONLY works in **Figma Slides** files, not regular Figma Design or FigJam files
- The `manifest.json` points to `dist/main.js` and `dist/ui.html` — these must exist before import
- If the user is on a Figma Organization or Enterprise plan, they can publish the plugin privately for the whole team (Plugins → Manage plugins → Publish → Organization)
- AppleScript automation is best-effort — Figma's in-app menus are Electron-rendered and not always accessible to macOS accessibility APIs. Fall back to manual guidance when needed.
- Brand fonts (Playfair Display, Source Sans Pro) must be available in the user's Figma account for full fidelity. The plugin falls back to Inter if fonts are missing.
