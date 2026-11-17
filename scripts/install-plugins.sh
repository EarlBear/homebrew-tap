#!/usr/bin/env bash
# install-plugins.sh — add the EarlBear plugin marketplace from GitHub and
# install every Claude plugin it lists. Safe to run again: plugins that are
# already installed are updated, nothing is installed twice.
#
# Usage: install-plugins.sh            (takes no arguments)
#
# The marketplace is the private GitHub repo EarlBear/marketplace-claude-plugins
# (its marketplace name is earlbear-claude-plugins). Adding it clones the repo,
# so this Mac needs GitHub access to EarlBear: an SSH key or a git credential
# helper for github.com.
#
# The plugin names are read from the marketplace's own
# .claude-plugin/marketplace.json once it is added, so this script never needs
# editing when the marketplace adds or removes a plugin.
#
# Older releases of the earlbear-plugins formula registered a stale copy of the
# plugins, kept inside the Homebrew install, under the same marketplace name.
# This script swaps that copy for the GitHub marketplace. A developer's own
# checkout of the marketplace, registered under the same name, is left alone.
#
# Exit codes: 0 when every plugin installed, 1 when the marketplace could not
# be added or read, 2 when some plugins did not install.

# No `set -e`: one plugin failing must not stop the rest.
set -uo pipefail

MARKETPLACE_REPO="EarlBear/marketplace-claude-plugins"
MARKETPLACE_NAME="earlbear-claude-plugins"

GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'

if [ "$#" -gt 0 ]; then
    echo -e "${YELLOW}Note: install-plugins.sh takes no arguments; ignoring: $*${NC}"
fi

if ! command -v claude >/dev/null 2>&1; then
    echo -e "${YELLOW}claude CLI not found. Install Claude Code, then run this script again.${NC}"
    exit 1
fi

# Run the claude CLI as a fresh session, even when called from inside one.
claude_cli() { env -u CLAUDECODE claude "$@"; }

lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

# Print the source, repo, url, path and installLocation of the marketplace
# registered under MARKETPLACE_NAME, one key=value per line (nothing if none is
# registered). `claude plugin marketplace list --json` prints one flat object
# per marketplace, one key per line.
registered_marketplace() {
    claude_cli plugin marketplace list --json 2>/dev/null | awk -v name="$MARKETPLACE_NAME" '
        /"name":/ { inside = ($0 ~ "\"" name "\"") }
        inside && /"(source|repo|url|path|installLocation)":/ {
            line = $0
            gsub(/^[ \t]*"|",?[ \t]*$/, "", line)
            sub(/": "/, "=", line)
            print line
        }
        inside && /}/ { inside = 0 }'
}

field() { printf '%s\n' "$1" | sed -n "s/^$2=//p"; }

# Print the name of every plugin in a marketplace.json, one per line: the
# "name" of each object in the top-level "plugins" array, and nothing else (not
# the marketplace's own name or its owner's). A small JSON scanner, so it works
# whatever the file's layout, with only the awk every Mac and Linux has.
plugin_names() {
    awk '
        { buf = buf $0 "\n" }
        END {
            n = length(buf); depth = 0; i = 1
            while (i <= n) {
                c = substr(buf, i, 1)
                if (c == "\"") {
                    s = ""; j = i + 1
                    while (j <= n) {
                        d = substr(buf, j, 1)
                        if (d == "\\") { s = s substr(buf, j, 2); j += 2; continue }
                        if (d == "\"") break
                        s = s d; j++
                    }
                    i = j + 1
                    k = i
                    while (k <= n && substr(buf, k, 1) ~ /[ \t\r\n]/) k++
                    if (substr(buf, k, 1) == ":") { key[depth] = s; i = k + 1; continue }
                    if (depth == 3 && type[1] == "{" && key[1] == "plugins" &&
                        type[2] == "[" && type[3] == "{" && key[3] == "name") print s
                    continue
                }
                if (c == "{" || c == "[") { depth++; type[depth] = c; key[depth] = "" }
                else if (c == "}" || c == "]") depth--
                i++
            }
        }' "$1"
}

add_github_marketplace() {
    if claude_cli plugin marketplace add "$MARKETPLACE_REPO"; then
        return 0
    fi
    echo ""
    echo -e "${RED}✗ Could not add the marketplace from GitHub ($MARKETPLACE_REPO).${NC}"
    echo "  It is a private repo: check that this Mac can clone it over SSH or HTTPS:"
    echo "    git ls-remote git@github.com:$MARKETPLACE_REPO.git"
    echo "    git ls-remote https://github.com/$MARKETPLACE_REPO.git"
    echo "  For HTTPS without an SSH key: gh auth login, then gh auth setup-git."
    echo "  Then run this script again, or by hand:"
    echo "    claude plugin marketplace add $MARKETPLACE_REPO"
    return 1
}

echo -e "${BLUE}EarlBear Plugin Installer${NC}"
echo "Marketplace: $MARKETPLACE_NAME (github.com/$MARKETPLACE_REPO)"
echo ""

# ── 1. Make sure the marketplace is the GitHub one ───────────────────────────
entry="$(registered_marketplace)"
source_kind="$(field "$entry" source)"
source_repo="$(field "$entry" repo)"
source_where="$(field "$entry" path)"
[ -n "$source_where" ] || source_where="$(field "$entry" url)"
[ -n "$source_where" ] || source_where="$source_repo"

if [ -z "$source_kind" ]; then
    add_github_marketplace || exit 1
elif [ "$source_kind" = "github" ] && [ "$(lower "$source_repo")" = "$(lower "$MARKETPLACE_REPO")" ]; then
    echo "Marketplace already added from GitHub; refreshing it."
    claude_cli plugin marketplace update "$MARKETPLACE_NAME" \
        || echo -e "${YELLOW}⚠ Refresh failed; installing from the copy already on disk.${NC}"
else
    source_path="$(field "$entry" path)"
    case "$source_path" in
        *earlbear-plugins*/libexec/marketplace*) stale=1 ;;   # old Homebrew copy
        *) if [ -n "$source_path" ] && [ ! -d "$source_path" ]; then stale=1; else stale=0; fi ;;
    esac
    if [ "$stale" = "1" ]; then
        echo "Replacing the old local copy ($source_path) with the GitHub marketplace."
        claude_cli plugin marketplace remove "$MARKETPLACE_NAME" || true
        add_github_marketplace || exit 1
    else
        echo -e "${YELLOW}Note: $MARKETPLACE_NAME is already added from ${source_where}.${NC}"
        echo "  Leaving it as is and installing from it. To use GitHub instead:"
        echo "    claude plugin marketplace remove $MARKETPLACE_NAME"
        echo "    claude plugin marketplace add $MARKETPLACE_REPO"
    fi
fi

# ── 2. Read the plugin list from the marketplace itself ──────────────────────
location="$(field "$(registered_marketplace)" installLocation)"
manifest="$location/.claude-plugin/marketplace.json"
if [ -z "$location" ] || [ ! -f "$manifest" ]; then
    echo -e "${RED}✗ Could not find the marketplace's plugin list at ${manifest}.${NC}"
    echo "  Check with: claude plugin marketplace list"
    exit 1
fi

PLUGINS=()
while IFS= read -r name; do
    case "$name" in
        ""|*[!A-Za-z0-9._-]*) echo -e "${YELLOW}⚠ Skipping an odd plugin name in the list: '$name'${NC}" ;;
        *) PLUGINS+=("$name") ;;
    esac
done < <(plugin_names "$manifest")

if [ "${#PLUGINS[@]}" -eq 0 ]; then
    echo -e "${RED}✗ No plugins found in $manifest.${NC}"
    echo "  The file may be damaged or in a format this script does not know."
    exit 1
fi
echo -e "${GREEN}✓ Marketplace ready: ${#PLUGINS[@]} plugins listed${NC}"
echo ""

# ── 3. Install (or update) each plugin ───────────────────────────────────────
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
    echo "  Fix the cause above, then run this script again."
    exit 2
fi
echo -e "${GREEN}✓ All ${#PLUGINS[@]} plugins installed${NC}"
echo "  Restart Claude Code to load them. Check with: claude plugin list"
