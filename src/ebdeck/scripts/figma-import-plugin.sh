#!/usr/bin/env bash
# Guide the user through importing the Figma plugin from manifest.json.
#
# This is a ONE-TIME setup step. After import, the plugin persists in
# Figma's development plugins list and can be re-run with figma-run-plugin.sh.
#
# Usage:
#   ./scripts/figma-import-plugin.sh
#
# What it does:
#   1. Builds the plugin (if not already built)
#   2. Opens Figma
#   3. Copies the manifest.json path to clipboard
#   4. Opens the "Import plugin from manifest" dialog
#   5. Guides the user to paste the path

set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MANIFEST_PATH="${PROJECT_DIR}/poc-figma/manifest.json"
DIST_DIR="${PROJECT_DIR}/poc-figma/dist"

echo -e "${CYAN}━━━ Figma Plugin Setup ━━━${NC}"
echo ""

# Step 0: Check Accessibility permissions for keystroke automation
check_accessibility() {
    # Try a harmless keystroke test — if it fails, we lack Accessibility access
    if ! osascript -e 'tell application "System Events" to key code 0 with option down' 2>/dev/null; then
        return 1
    fi
    return 0
}

# Detect which terminal is running
TERMINAL_APP=""
if [ -n "${TERM_PROGRAM:-}" ]; then
    case "$TERM_PROGRAM" in
        iTerm.app)  TERMINAL_APP="iTerm2" ;;
        Apple_Terminal) TERMINAL_APP="Terminal" ;;
        vscode)     TERMINAL_APP="Visual Studio Code" ;;
        *)          TERMINAL_APP="$TERM_PROGRAM" ;;
    esac
fi

AUTOMATION_AVAILABLE=true
if ! check_accessibility; then
    AUTOMATION_AVAILABLE=false
    echo -e "${YELLOW}⚠  Accessibility permission not granted for ${TERMINAL_APP:-your terminal}.${NC}"
    echo -e "   Keystroke automation requires Accessibility access."
    echo ""
    echo -e "${BOLD}Opening System Settings → Privacy & Security → Accessibility...${NC}"
    open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
    echo ""
    echo -e "  ${BOLD}To enable:${NC}"
    echo -e "    1. Click ${GREEN}+${NC} in the Accessibility list"
    echo -e "    2. Add ${GREEN}${TERMINAL_APP:-your terminal app}${NC}"
    echo -e "    3. Toggle ${GREEN}ON${NC}"
    echo -e "    4. ${RED}Restart ${TERMINAL_APP:-your terminal}${NC} (permissions don't apply to existing sessions)"
    echo -e "    5. Re-run: ${DIM}./scripts/figma-import-plugin.sh${NC}"
    echo ""
    echo -e "  ${DIM}(Continuing without automation — manual instructions below)${NC}"
    echo ""
else
    echo -e "${GREEN}✓ Accessibility permissions OK${NC}"
    echo ""
fi

# Step 1: Check if plugin is built
if [ ! -f "${DIST_DIR}/main.js" ] || [ ! -f "${DIST_DIR}/ui.html" ]; then
    echo -e "${YELLOW}Plugin not built yet. Building...${NC}"
    cd "$PROJECT_DIR"
    make figma-build-local 2>&1 || {
        echo -e "${RED}Build failed. Run 'make figma-install' first, then retry.${NC}"
        exit 1
    }
    echo ""
fi

echo -e "${GREEN}✓ Plugin built${NC}"
echo -e "${DIM}  dist/main.js + dist/ui.html${NC}"
echo ""

# Step 2: Verify manifest
if [ ! -f "$MANIFEST_PATH" ]; then
    echo -e "${RED}manifest.json not found at: ${MANIFEST_PATH}${NC}"
    exit 1
fi
echo -e "${GREEN}✓ manifest.json found${NC}"
echo -e "${DIM}  ${MANIFEST_PATH}${NC}"
echo ""

# Step 3: Copy manifest path to clipboard
echo "$MANIFEST_PATH" | pbcopy
echo -e "${GREEN}✓ Manifest path copied to clipboard${NC}"
echo ""

# Step 4: Open Figma
echo -e "${BOLD}Opening Figma...${NC}"
osascript -e 'tell application "Figma" to activate'
sleep 2
echo -e "${GREEN}✓ Figma activated${NC}"
echo ""

# Step 5: Try to open the import dialog
if [ "$AUTOMATION_AVAILABLE" = true ]; then
    echo -e "${BOLD}Attempting to open 'Import plugin from manifest' dialog...${NC}"
    if osascript <<'EOF' 2>/dev/null; then
tell application "System Events"
    tell process "Figma"
        set frontmost to true
        delay 1
        -- Try the macOS menu bar: Plugins > Development > Import plugin from manifest...
        try
            click menu item "Import plugin from manifest…" of menu "Development" of menu item "Development" of menu "Plugins" of menu bar 1
        on error
            -- Fallback: use Quick Actions (Cmd+/)
            keystroke "/" using command down
            delay 0.8
            keystroke "Import plugin from manifest"
            delay 1
            keystroke return
        end try
    end tell
end tell
EOF
        echo -e "${GREEN}✓ Import dialog triggered${NC}"
    else
        echo -e "${YELLOW}⚠  Could not trigger import dialog automatically${NC}"
    fi
fi

echo ""
echo -e "${CYAN}━━━ Import the Plugin ━━━${NC}"
echo ""
echo -e "  ${BOLD}If the file picker opened:${NC}"
echo -e "    1. Press ${GREEN}Cmd+Shift+G${NC} to open 'Go to folder'"
echo -e "    2. Press ${GREEN}Cmd+V${NC} to paste the manifest path"
echo -e "    3. Click ${GREEN}Open${NC}"
echo ""
echo -e "  ${BOLD}If it didn't open:${NC}"
echo -e "    1. In Figma, go to: ${GREEN}Plugins → Development → Import plugin from manifest...${NC}"
echo -e "    2. Navigate to: ${DIM}${MANIFEST_PATH}${NC}"
echo -e "    3. Or press ${GREEN}Cmd+Shift+G${NC} and paste (path is on clipboard)"
echo ""
echo -e "${CYAN}━━━ After Import ━━━${NC}"
echo ""
echo -e "  The plugin will appear under ${GREEN}Plugins → Development → Earlbear Deck Generator${NC}"
echo -e "  To run it: open a Figma Slides file, then use the plugin menu or run:"
echo -e "    ${DIM}./scripts/figma-run-plugin.sh${NC}"
echo ""
echo -e "  ${YELLOW}This import is a one-time step. The plugin persists across sessions.${NC}"
