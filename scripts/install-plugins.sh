#!/usr/bin/env bash
# install-plugins.sh — add the EarlBear plugin marketplace from GitHub and
# install the company Claude plugins from it. Safe to run again: plugins that
# are already installed are updated, nothing is installed twice.
#
# Usage: install-plugins.sh            (takes no arguments)
#
# The marketplace is the private GitHub repo EarlBear/marketplace-claude-plugins
# (its marketplace name is earlbear-claude-plugins). Adding it clones the repo,
# so this Mac needs GitHub access to EarlBear: an SSH key or a git credential
# helper for github.com.
#
# Older releases of the earlbear-plugins formula registered a stale copy of the
# plugins, kept inside the Homebrew install, under the same marketplace name.
# This script swaps that copy for the GitHub marketplace. A developer's own
# checkout of the marketplace, registered under the same name, is left alone.

# No `set -e`: one plugin failing must not stop the rest.
set -uo pipefail

MARKETPLACE_REPO="EarlBear/marketplace-claude-plugins"
MARKETPLACE_NAME="earlbear-claude-plugins"

# Every plugin listed in the marketplace's .claude-plugin/marketplace.json on
# main, as of 2026-11-16. When the marketplace adds or removes a plugin, update
# this list to match.
PLUGINS=(
    discover-earlbear-plugins
    deck-manager
    wireframe-manager
    artifact-manager
    jira-manager
    product-manager
    shopify-manager
    cloud-agent-manager
    earlbear-docs-manager
    dev-tools-manager
    marketplace-manager
    domain-manager
    transcript-manager
    routine-manager
    routine-developer
    store-auditor
    business-objective-manager
    store-healer
    synthetic-store
    living-artifacts-manager
    tap-manager
)

GREEN='\033[0;32m'; YELLOW='\033[0;33m'; BLUE='\033[0;34m'; NC='\033[0m'

if [ "$#" -gt 0 ]; then
    echo -e "${YELLOW}Note: install-plugins.sh no longer takes a marketplace path; ignoring '$1'.${NC}"
fi

if ! command -v claude >/dev/null 2>&1; then
    echo -e "${YELLOW}claude CLI not found. Install Claude Code, then run this script again.${NC}"
    exit 1
fi

# Run the claude CLI as a fresh session, even when called from inside one.
claude_cli() { env -u CLAUDECODE claude "$@"; }

lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

# Print the source, repo and path of the marketplace registered under
# MARKETPLACE_NAME, one key=value per line (nothing if none is registered).
registered_marketplace() {
    claude_cli plugin marketplace list --json 2>/dev/null | awk -v name="$MARKETPLACE_NAME" '
        /"name":/ { inside = ($0 ~ "\"" name "\"") }
        inside && /"(source|repo|path)":/ {
            line = $0
            gsub(/^[ \t]*"|",?[ \t]*$/, "", line)
            sub(/": "/, "=", line)
            print line
        }
        inside && /}/ { inside = 0 }'
}

add_github_marketplace() {
    if claude_cli plugin marketplace add "$MARKETPLACE_REPO"; then
        return 0
    fi
    echo ""
    echo -e "${YELLOW}⚠ Could not add the marketplace from GitHub ($MARKETPLACE_REPO).${NC}"
    echo "  It is a private repo: check that this Mac can clone it, for example:"
    echo "    git ls-remote git@github.com:$MARKETPLACE_REPO.git"
    echo "  Then run this script again, or by hand:"
    echo "    claude plugin marketplace add $MARKETPLACE_REPO"
    return 1
}

echo -e "${BLUE}EarlBear Plugin Installer${NC}"
echo "Marketplace: $MARKETPLACE_NAME (github.com/$MARKETPLACE_REPO)"
echo ""

# ── 1. Make sure the marketplace is the GitHub one ───────────────────────────
entry="$(registered_marketplace)"
source_kind="$(printf '%s\n' "$entry" | sed -n 's/^source=//p')"
source_repo="$(printf '%s\n' "$entry" | sed -n 's/^repo=//p')"
source_path="$(printf '%s\n' "$entry" | sed -n 's/^path=//p')"

if [ -z "$source_kind" ]; then
    add_github_marketplace || exit 1
elif [ "$source_kind" = "github" ] && [ "$(lower "$source_repo")" = "$(lower "$MARKETPLACE_REPO")" ]; then
    echo "Marketplace already added from GitHub; refreshing it."
    claude_cli plugin marketplace update "$MARKETPLACE_NAME" \
        || echo -e "${YELLOW}⚠ Refresh failed; installing from the copy already on disk.${NC}"
else
    case "$source_path" in
        *earlbear-plugins*/libexec/marketplace*) stale=1 ;;   # old Homebrew copy
        *) if [ -n "$source_path" ] && [ ! -d "$source_path" ]; then stale=1; else stale=0; fi ;;
    esac
    if [ "$stale" = "1" ]; then
        echo "Replacing the old local copy ($source_path) with the GitHub marketplace."
        claude_cli plugin marketplace remove "$MARKETPLACE_NAME" || true
        add_github_marketplace || exit 1
    else
        echo -e "${YELLOW}Note: $MARKETPLACE_NAME is already added from ${source_path:-$source_repo}.${NC}"
        echo "  Leaving it as is and installing from it. To use GitHub instead:"
        echo "    claude plugin marketplace remove $MARKETPLACE_NAME"
        echo "    claude plugin marketplace add $MARKETPLACE_REPO"
    fi
fi
echo -e "${GREEN}✓ Marketplace ready${NC}"
echo ""

# ── 2. Install (or update) each plugin ───────────────────────────────────────
failed=()
for plugin in "${PLUGINS[@]}"; do
    id="${plugin}@${MARKETPLACE_NAME}"
    if output="$(claude_cli plugin install "$id" 2>&1)"; then
        case "$output" in
            *"already installed"*)
                claude_cli plugin update "$id" >/dev/null 2>&1 || true
                echo -e "  ${GREEN}✓ ${plugin} (already installed, checked for updates)${NC}" ;;
            *)
                echo -e "  ${GREEN}✓ ${plugin}${NC}" ;;
        esac
    else
        failed+=("$plugin")
        echo -e "  ${YELLOW}⚠ ${plugin} install failed — run: claude plugin install ${id}${NC}"
        printf '%s\n' "$output" | tail -1 | sed 's/^/      /'
    fi
done

echo ""
if [ "${#failed[@]}" -gt 0 ]; then
    echo -e "${YELLOW}⚠ ${#failed[@]} of ${#PLUGINS[@]} plugins did not install: ${failed[*]}${NC}"
else
    echo -e "${GREEN}✓ All ${#PLUGINS[@]} plugins installed${NC}"
fi
echo "  Restart Claude Code to load them. Check with: claude plugin list"
