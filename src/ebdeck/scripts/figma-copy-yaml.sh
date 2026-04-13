#!/usr/bin/env bash
# Incrementally copy content and brand YAML to clipboard for the Figma plugin.
#
# Usage:
#   ./scripts/figma-copy-yaml.sh content                          # Copy default content
#   ./scripts/figma-copy-yaml.sh brand                            # Copy default brand
#   ./scripts/figma-copy-yaml.sh content investor-pitch.yaml      # Copy specific content
#   ./scripts/figma-copy-yaml.sh brand brands/matcha.yaml         # Copy specific brand
#   ./scripts/figma-copy-yaml.sh both                             # Interactive: content then brand

set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

copy_content() {
    local file="${1:-investor-pitch.yaml}"
    local path="${PROJECT_DIR}/content/${file}"

    # If a full path was given (e.g., content/foo.yaml), handle it
    if [[ "$file" == content/* ]]; then
        path="${PROJECT_DIR}/${file}"
        file="${file#content/}"
    fi

    if [ ! -f "$path" ]; then
        echo -e "${YELLOW}Content file not found: ${path}${NC}"
        echo "Available:"
        ls "${PROJECT_DIR}/content/"*.yaml 2>/dev/null | xargs -I{} basename {} | sed 's/^/  /'
        return 1
    fi

    cat "$path" | pbcopy
    echo -e "${GREEN}✓ Content YAML copied to clipboard${NC}"
    echo -e "${DIM}  ${file}${NC}"
    echo -e "  → Paste into ${BOLD}Content YAML${NC} field with ${GREEN}Cmd+V${NC}"
}

copy_brand() {
    local file="${1:-brand.yaml}"
    local path

    if [[ "$file" == */* ]]; then
        path="${PROJECT_DIR}/${file}"
    elif [[ "$file" == "brand.yaml" ]]; then
        path="${PROJECT_DIR}/brand.yaml"
    else
        path="${PROJECT_DIR}/brands/${file}"
    fi

    if [ ! -f "$path" ]; then
        echo -e "${YELLOW}Brand file not found: ${path}${NC}"
        echo "Available:"
        echo "  brand.yaml (default)"
        ls "${PROJECT_DIR}/brands/"*.yaml 2>/dev/null | xargs -I{} basename {} | sed 's/^/  brands\//'
        return 1
    fi

    cat "$path" | pbcopy
    echo -e "${GREEN}✓ Brand YAML copied to clipboard${NC}"
    echo -e "${DIM}  ${file}${NC}"
    echo -e "  → Paste into ${BOLD}Brand YAML${NC} field with ${GREEN}Cmd+V${NC}"
}

case "${1:-both}" in
    content)
        copy_content "${2:-investor-pitch.yaml}"
        ;;
    brand)
        copy_brand "${2:-brand.yaml}"
        ;;
    both)
        CONTENT_FILE="${2:-investor-pitch.yaml}"
        BRAND_FILE="${3:-brand.yaml}"

        echo -e "${CYAN}━━━ Step 1: Content YAML ━━━${NC}"
        copy_content "$CONTENT_FILE"
        echo ""
        read -p "  Press Enter after pasting into Figma... "
        echo ""

        echo -e "${CYAN}━━━ Step 2: Brand YAML ━━━${NC}"
        copy_brand "$BRAND_FILE"
        echo ""
        echo -e "  After pasting, click ${GREEN}Generate Slides${NC}"
        ;;
    *)
        echo "Usage: $0 {content|brand|both} [filename]"
        echo ""
        echo "Examples:"
        echo "  $0 content                         # Default content"
        echo "  $0 brand brands/matcha.yaml         # Specific brand"
        echo "  $0 both investor-pitch.yaml brand.yaml  # Both, interactive"
        exit 1
        ;;
esac
