#!/usr/bin/env bash
# earlbear-setup — interactive credential wizard.
# Writes ~/.config/earlbear/.env one service at a time.

set -euo pipefail

CONFIG_DIR="${EARLBEAR_CONFIG_DIR:-$HOME/.config/earlbear}"
ENV_FILE="$CONFIG_DIR/.env"

GREEN='\033[0;32m'; YELLOW='\033[0;33m'; BLUE='\033[0;34m'; NC='\033[0m'

mkdir -p "$CONFIG_DIR"

echo -e "${BLUE}EarlBear Credential Setup${NC}"
echo "Writing to: $ENV_FILE"
echo ""

if [ -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}⚠  $ENV_FILE already exists. Values will be appended/updated.${NC}"
    echo ""
fi

ask() {
    local key="$1" prompt="$2" default="${3:-}"
    local current
    current=$(grep -s "^${key}=" "$ENV_FILE" | cut -d= -f2- || true)
    if [ -n "$current" ]; then
        read -rp "  $prompt [current: ${current:0:8}...]: " val
        val="${val:-$current}"
    elif [ -n "$default" ]; then
        read -rp "  $prompt [default: $default]: " val
        val="${val:-$default}"
    else
        read -rp "  $prompt: " val
    fi
    # Write or update the key in the file
    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        # Update existing
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
        else
            sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
        fi
    else
        echo "${key}=${val}" >> "$ENV_FILE"
    fi
}

touch "$ENV_FILE"
chmod 600 "$ENV_FILE"

echo -e "${BLUE}── Jira (ebjira) ──────────────────────────────────────────${NC}"
ask JIRA_BASE_URL      "Jira base URL (e.g. https://your-org.atlassian.net)"
ask JIRA_USER_EMAIL    "Jira user email"
ask JIRA_API_TOKEN     "Jira API token (https://id.atlassian.com/manage-profile/security/api-tokens)"
ask JIRA_PROJECT       "Jira project key" "EARL"
echo ""

echo -e "${BLUE}── Google Docs (ebdocs) ───────────────────────────────────${NC}"
echo "  Auth option: OAuth refresh token (recommended)"
ask GOOGLE_OAUTH_CLIENT_ID     "Google OAuth client ID"
ask GOOGLE_OAUTH_CLIENT_SECRET "Google OAuth client secret"
ask GOOGLE_OAUTH_REFRESH_TOKEN "Google OAuth refresh token"
ask GOOGLE_DRIVE_FOLDER_ID     "Google Drive folder ID"
echo ""

echo -e "${BLUE}── Shopify (ebshop) ───────────────────────────────────────${NC}"
ask SHOPIFY_STORE_URL    "Shopify store URL (e.g. https://your-store.myshopify.com)"
ask SHOPIFY_ACCESS_TOKEN "Shopify access token"
ask SHOPIFY_API_VERSION  "Shopify API version" "2026-01"
echo ""

echo -e "${BLUE}── Supabase (optional) ────────────────────────────────────${NC}"
ask SUPABASE_PROJECT_URL      "Supabase project URL (or press Enter to skip)"
ask SUPABASE_ANON_KEY         "Supabase anon key (or press Enter to skip)"
ask SUPABASE_SERVICE_ROLE_KEY "Supabase service role key (or press Enter to skip)"
echo ""

echo -e "${GREEN}✓ Credentials written to $ENV_FILE${NC}"
echo "  Protect it: chmod 600 $ENV_FILE (already set)"
echo ""
echo "  Test CLIs:"
echo "    ebjira project list"
echo "    ebdocs auth status"
echo "    ebshop shop info"
