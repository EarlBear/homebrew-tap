#!/usr/bin/env bash
# Trigger the Earlbear Deck Generator plugin in Figma.
#
# This script:
#   1. Ensures Figma is frontmost
#   2. Uses Cmd+Option+P (re-run last plugin) or navigates the plugin menu
#   3. Copies YAML to clipboard for easy pasting into the plugin UI
#
# Usage:
#   ./scripts/figma-run-plugin.sh                                    # Just trigger plugin
#   ./scripts/figma-run-plugin.sh --content content/investor-pitch.yaml  # Copy content YAML to clipboard
#   ./scripts/figma-run-plugin.sh --rerun                            # Re-run last plugin (Cmd+Option+P)
#
# Prerequisites:
#   - Figma Desktop is open with a Slides file
#   - Plugin has been imported via: Plugins > Development > Import plugin from manifest

set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
DIM='\033[2m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${CYAN}━━━ Figma Plugin Runner ━━━${NC}"

# Check Figma is running
if ! pgrep -x "Figma" > /dev/null; then
    echo -e "${YELLOW}Figma is not running. Starting it...${NC}"
    open -a Figma
    sleep 3
fi

# Parse args
MODE="menu"
CONTENT_FILE=""
BRAND_FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --rerun)
            MODE="rerun"
            shift
            ;;
        --content)
            CONTENT_FILE="$2"
            shift 2
            ;;
        --brand)
            BRAND_FILE="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

# Copy YAML to clipboard if requested
if [ -n "$CONTENT_FILE" ]; then
    CONTENT_PATH="${PROJECT_DIR}/${CONTENT_FILE}"
    if [ -f "$CONTENT_PATH" ]; then
        cat "$CONTENT_PATH" | pbcopy
        echo -e "${GREEN}✓ Content YAML copied to clipboard${NC}"
        echo -e "${DIM}  ${CONTENT_FILE}${NC}"
        echo -e "${YELLOW}  → Paste into the 'Content YAML' field in the plugin UI${NC}"
        echo ""
    else
        echo -e "${YELLOW}Content file not found: ${CONTENT_PATH}${NC}"
    fi
fi

if [ -n "$BRAND_FILE" ]; then
    BRAND_PATH="${PROJECT_DIR}/${BRAND_FILE}"
    if [ -f "$BRAND_PATH" ]; then
        echo -e "${DIM}Brand YAML ready at: ${BRAND_FILE}${NC}"
        echo -e "${YELLOW}  → After pasting content, run:${NC}"
        echo -e "${YELLOW}    cat ${BRAND_PATH} | pbcopy${NC}"
        echo -e "${YELLOW}    Then paste into the 'Brand YAML' field${NC}"
        echo ""
    fi
fi

# Bring Figma to front
osascript -e 'tell application "Figma" to activate'
sleep 1

if [ "$MODE" = "rerun" ]; then
    echo "Re-running last plugin (Cmd+Option+P)..."
    osascript <<'EOF'
tell application "System Events"
    tell process "Figma"
        set frontmost to true
        delay 0.5
        keystroke "p" using {command down, option down}
    end tell
end tell
EOF
    echo -e "${GREEN}✓ Re-run triggered${NC}"
else
    echo "Opening plugin menu..."
    # Navigate: Plugins menu via keyboard
    # Figma Desktop on macOS has Plugins in the menu bar
    osascript <<'EOF'
tell application "System Events"
    tell process "Figma"
        set frontmost to true
        delay 0.5
        -- Try the macOS menu bar approach
        try
            click menu item "Earlbear Deck Generator" of menu "Plugins" of menu bar 1
        on error
            -- Fallback: use Cmd+/ (quick actions) and type the plugin name
            keystroke "/" using command down
            delay 0.5
            keystroke "Earlbear Deck Generator"
            delay 0.5
            keystroke return
        end try
    end tell
end tell
EOF
    echo -e "${GREEN}✓ Plugin launched${NC}"
fi

echo ""
echo -e "${CYAN}Plugin UI should now be open in Figma.${NC}"
if [ -n "$CONTENT_FILE" ]; then
    echo -e "Content YAML is on your clipboard — ${GREEN}Cmd+V${NC} to paste."
fi
