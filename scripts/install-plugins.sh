#!/usr/bin/env bash
# install-plugins.sh — register earlbear marketplace and install all plugins.
# Usage: install-plugins.sh <marketplace-path>

set -euo pipefail

MARKETPLACE_PATH="${1:-$(dirname "$0")/../plugins-bundle}"
MARKETPLACE_PATH="$(cd "$MARKETPLACE_PATH" && pwd)"

GREEN='\033[0;32m'; YELLOW='\033[0;33m'; BLUE='\033[0;34m'; NC='\033[0m'

echo -e "${BLUE}EarlBear Plugin Installer${NC}"
echo "Marketplace: $MARKETPLACE_PATH"
echo ""

# Register marketplace (idempotent)
env -u CLAUDECODE claude plugin marketplace add "$MARKETPLACE_PATH" 2>/dev/null || true
echo -e "${GREEN}✓ Marketplace registered${NC}"

# Install each plugin
PLUGINS=(
    discover-earlbear-plugins
    deck-manager
    wireframe-manager
    artifact-manager
    jira-manager
    shopify-manager
    cloud-agent-manager
    earlbear-docs-manager
    dev-tools-manager
)

for plugin in "${PLUGINS[@]}"; do
    echo -e "  Installing ${plugin}..."
    if env -u CLAUDECODE claude plugin install "${plugin}@earlbear-claude-plugins" 2>/dev/null; then
        echo -e "  ${GREEN}✓ ${plugin}${NC}"
    else
        echo -e "  ${YELLOW}⚠ ${plugin} install failed — run: claude plugin install ${plugin}@earlbear-claude-plugins${NC}"
    fi
done

echo ""
echo -e "${GREEN}✓ Plugin installation complete${NC}"
echo "  Verify: claude plugin list | grep earlbear"
