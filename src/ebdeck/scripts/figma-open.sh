#!/usr/bin/env bash
# Open Figma Desktop and optionally navigate to a specific file.
#
# Usage:
#   ./scripts/figma-open.sh                           # Just launch Figma
#   ./scripts/figma-open.sh "figma://file/ABC123"     # Open specific file
#   ./scripts/figma-open.sh --new-slides              # Create new Figma Slides file
#
# After opening, use figma-run-plugin.sh to trigger the plugin.

set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

echo -e "${CYAN}━━━ Figma Launcher ━━━${NC}"

# Check if Figma is installed
if ! [ -d "/Applications/Figma.app" ]; then
    echo -e "${YELLOW}Figma Desktop not found at /Applications/Figma.app${NC}"
    echo "Install from: https://www.figma.com/downloads/"
    exit 1
fi

# Launch or activate Figma
osascript -e 'tell application "Figma" to activate'
echo -e "${GREEN}✓ Figma activated${NC}"

# Wait for Figma to be frontmost
sleep 2

if [ "${1:-}" = "--new-slides" ]; then
    echo "Opening new Figma Slides file..."
    # Use Cmd+N to create new file, then the user selects Slides
    osascript <<'EOF'
tell application "System Events"
    tell process "Figma"
        set frontmost to true
        delay 1
        -- Cmd+N for new file
        keystroke "n" using command down
    end tell
end tell
EOF
    echo -e "${GREEN}✓ New file dialog opened${NC}"
    echo -e "${YELLOW}  → Select 'Presentation' to create a Figma Slides file${NC}"

elif [ -n "${1:-}" ]; then
    echo "Opening: $1"
    open "$1"
    echo -e "${GREEN}✓ File opened${NC}"

else
    echo -e "${GREEN}✓ Figma is ready${NC}"
fi

echo ""
echo -e "${CYAN}Next steps:${NC}"
echo "  1. Open or create a Figma Slides file"
echo "  2. Run: ./scripts/figma-run-plugin.sh"
