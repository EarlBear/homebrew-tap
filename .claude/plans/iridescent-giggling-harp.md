# Plugin Install Automation — PyAutoGUI Image-Match Plan

## Context

`scripts/install-plugin.sh` needs to install EarlBear plugins in Claude Desktop
without hardcoded grid coordinates. The current approach (fixed x,y per plugin)
breaks whenever Anthropic changes the plugin grid layout.

**PyAutoGUI's `locateAllOnScreen()`** solves this: given a reference image of a
`+` button, it finds *all* matching buttons on screen and returns their positions.
We can then pick the one closest to the target plugin's card title.

Progress so far (from live testing):
- Search box focus works: click `756,157` → type slug → results filter ✓
- `AXFocusedUIElement` always returns `missing value` for Claude Desktop web content (Electron limitation)
- Personal tab click at `360,103` missed — needs re-calibration
- Modal stays open through Tab presses (user confirmed)

---

## Approach: Image-match the + button after filtering

### Why this works better than coordinates

1. Type slug into search → only 1 result appears (the matching plugin)
2. The `+` button for that single result is now the *only* `+` on screen
3. `locateOnScreen(plus_button_template.png)` finds it regardless of position
4. Click it — done

No grid layout dependency at all.

### Steps

```
open modal
  → click search box (756,157 — stable, top of modal)
  → switch to Personal tab
  → type slug (e.g. "jira-manager")
  → wait for single result
  → pyautogui.locateOnScreen(PLUS_BTN_TEMPLATE, confidence=0.85)
  → click result center (divide 2x coords by 2 for cliclick, or use pyautogui.click directly)
  → Escape to close modal
```

---

## Implementation

### 1. One-time: create reference image `scripts/assets/plus-button.png`

Take a screenshot with the modal open, crop just the `+` button from a plugin card.

```bash
# Capture + crop the + button from a plugin card
screencapture -x /tmp/ref-full.png
python3 - << 'EOF'
from PIL import Image
img = Image.open('/tmp/ref-full.png')
# Crop the + button region (2x coords — measure from screenshot)
# The + button is a small circle ~30x30px (60x60 2x pixels) at the right of each card
plus = img.crop((PLUS_X*2 - 30, PLUS_Y*2 - 30, PLUS_X*2 + 30, PLUS_Y*2 + 30))
plus.save('scripts/assets/plus-button.png')
EOF
```

### 2. Python helper: `scripts/find-and-click.py`

```python
#!/usr/bin/env python3
"""find-and-click.py <template.png> [confidence=0.85]
Finds template on screen and clicks the first match.
Returns 0 on success, 1 if not found.
"""
import sys, subprocess
import pyautogui

template = sys.argv[1]
confidence = float(sys.argv[2]) if len(sys.argv) > 2 else 0.85

# pyautogui.locateOnScreen returns 2x pixel coords on Retina
match = pyautogui.locateOnScreen(template, confidence=confidence)
if match is None:
    print(f"[find-and-click] NOT FOUND: {template}", file=sys.stderr)
    sys.exit(1)

# Center of match in 2x pixels → divide by 2 for logical coords
cx = int((match.left + match.width / 2) / 2)
cy = int((match.top + match.height / 2) / 2)
print(f"[find-and-click] Found at logical ({cx},{cy}), clicking...")
subprocess.run(['/opt/homebrew/bin/cliclick', f'c:{cx},{cy}'])
sys.exit(0)
```

### 3. `install-plugin.sh` rewrite using image match

```bash
install_plugin() {
  local slug="$1"
  log "Installing ${slug}..."

  nav_to_customize
  open_browse_plugins   # opens on Anthropic & Partners tab

  # Switch to Personal tab
  activate_claude
  click "$COORD_PERSONAL_TAB"
  sleep 0.8

  # Focus search box and type slug
  activate_claude
  click "756,157"        # search box — stable (top of modal white input)
  sleep 0.3
  osascript -e "tell application \"System Events\" to keystroke \"${slug}\""
  sleep 1.2             # wait for filter
  screenshot "/tmp/install-${slug}-filtered.png"

  # Find and click the + button via image match
  activate_claude
  if python3 scripts/find-and-click.py scripts/assets/plus-button.png 0.80; then
    log "Clicked + button for ${slug}"
    sleep 2.0
  else
    log "ERROR: could not find + button for ${slug} — check /tmp/install-${slug}-filtered.png"
    key 53   # Escape
    return 1
  fi

  verify_install "$slug"
  activate_claude; key 53   # Escape
  log "✓ Done: ${slug}"
}
```

---

## Dependencies

```bash
pip3 install pyautogui pyscreeze pillow opencv-python
# or
pip3 install pyautogui opencv-python   # pyscreeze pulled in automatically
```

Add to `scripts/install-plugin.sh` prereq check:
```bash
python3 -c "import pyautogui, cv2" 2>/dev/null || \
  fail "Missing: pip3 install pyautogui opencv-python"
```

---

## Retina Gotcha

`locateOnScreen()` returns 2x (physical) pixel coordinates on Retina.  
Divide by 2 before using with `cliclick` (which takes logical coordinates).  
If using `pyautogui.click()` directly instead of cliclick, use the raw 2x coords — PyAutoGUI handles the scaling internally (though it has bugs; cliclick is more reliable).

---

## Personal Tab Coordinate

Current `COORD_PERSONAL_TAB="725,200"` was calibrated for the old Cowork window layout. With the new navigation (Cmd+N → click Customize icon), the modal opens at a different position. Need to re-measure.

From live testing screenshot analysis:
- Modal x range: 246–1266 logical
- Tab pills visible at y≈103 in the screenshot (modal starts at y≈74)
- "Personal" tab is the second pill — at approximately x≈360, y≈103

Update `COORD_PERSONAL_TAB="360,103"` in the script.

---

## Critical Files

| File | Change |
|------|--------|
| `scripts/install-plugin.sh` | Update `COORD_PERSONAL_TAB`, add image-match install flow |
| `scripts/find-and-click.py` | **New** — PyAutoGUI image-match helper |
| `scripts/assets/plus-button.png` | **New** — reference image of + button |

---

## Verification

```bash
# 1. Install deps
pip3 install pyautogui opencv-python

# 2. Capture reference + button image (modal must be open on Personal tab)
bash scripts/install-plugin.sh calibrate
# → screenshot at /tmp/calibrate-personal.png
# → crop + button manually or with a helper script

# 3. Test find-and-click standalone
python3 scripts/find-and-click.py scripts/assets/plus-button.png
# → should print "Found at logical (X,Y), clicking..."

# 4. Full install
bash scripts/install-plugin.sh jira-manager
# → /tmp/install-jira-manager-post.png shows installed state

# 5. Install all
bash scripts/install-plugin.sh all

# 6. Re-record step 3 GIF
make screenshot-cowork-step STEP=3

# 7. Rebuild and smoke test
make dev
```
