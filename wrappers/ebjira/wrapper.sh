#!/usr/bin/env bash
# ebjira — wrapper installed by the Homebrew formula.
# Proxies commands into the ebjira Docker container.
#
# Credentials: reads from $EARLBEAR_CONFIG_DIR/.env (default ~/.config/earlbear/.env)
# Run `earlbear-setup` or create the file manually before first use.

set -euo pipefail

EARLBEAR_CONFIG_DIR="${EARLBEAR_CONFIG_DIR:-$HOME/.config/earlbear}"
ENV_FILE="$EARLBEAR_CONFIG_DIR/.env"

# Ensure .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo '{"error": "CONFIG_MISSING", "message": "~/.config/earlbear/.env not found. Run: earlbear-setup"}' >&2
    exit 2
fi

# Build image if it doesn't exist — Dockerfile is in the formula libexec
FORMULA_LIBEXEC="$(brew --cellar ebjira)/$(brew list --versions ebjira | awk '{print $2}')/libexec/ebjira"
if ! docker image inspect ebjira >/dev/null 2>&1; then
    echo '{"status": "building", "message": "Building ebjira Docker image (first run)..."}' >&2
    docker build -t ebjira -q "$FORMULA_LIBEXEC" >&2
fi

# Resolve sync/content mount
JIRA_SYNC_DIR_VAL=$(grep -s '^JIRA_SYNC_DIR=' "$ENV_FILE" | cut -d= -f2- || true)
CONTENT_DIR_VAL=$(grep -s '^CONTENT_DIR=' "$ENV_FILE" | cut -d= -f2- || true)

SYNC_MOUNT=()
if [ -n "$JIRA_SYNC_DIR_VAL" ]; then
    mkdir -p "$JIRA_SYNC_DIR_VAL"
    SYNC_MOUNT+=(-v "$JIRA_SYNC_DIR_VAL:/sync" -e "JIRA_SYNC_DIR=/sync")
fi
if [ -n "$CONTENT_DIR_VAL" ]; then
    mkdir -p "$CONTENT_DIR_VAL/jira"
    SYNC_MOUNT+=(-v "$CONTENT_DIR_VAL:/content" -e "CONTENT_DIR=/content")
fi
if [ ${#SYNC_MOUNT[@]} -eq 0 ]; then
    DIST_DIR="$EARLBEAR_CONFIG_DIR/dist"
    mkdir -p "$DIST_DIR"
    SYNC_MOUNT=(-v "$DIST_DIR:/app/dist")
fi

# Jira settings already set in the environment win over the file. agent-cli reads the token from
# the Keychain and exports it, so without this a token kept only in the Keychain never reached the
# container. `-e NAME` with no value makes Docker copy it from this environment, so the token is
# not on the command line where `ps` would show it.
PASS_ENV=()
for var in JIRA_BASE_URL JIRA_USER_EMAIL JIRA_PROJECT JIRA_API_TOKEN; do
    if [ -n "${!var:-}" ]; then
        PASS_ENV+=(-e "$var")
    fi
done

exec docker run --rm \
    --env-file "$ENV_FILE" \
    ${PASS_ENV[@]+"${PASS_ENV[@]}"} \
    "${SYNC_MOUNT[@]}" \
    ebjira \
    "$@"
