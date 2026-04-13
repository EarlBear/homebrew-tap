#!/usr/bin/env bash
# ebdocs — wrapper installed by the Homebrew formula.
# Proxies commands into the ebdocs Docker container.
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

# Build image if it doesn't exist
FORMULA_LIBEXEC="$(brew --cellar ebdocs)/$(brew list --versions ebdocs | awk '{print $2}')/libexec/ebdocs"
if ! docker image inspect ebdocs >/dev/null 2>&1; then
    echo '{"status": "building", "message": "Building ebdocs Docker image (first run)..."}' >&2
    docker build -t ebdocs -q "$FORMULA_LIBEXEC" >&2
fi

# Resolve sync/content mount
EBDOCS_SYNC_DIR_VAL=$(grep -s '^EBDOCS_SYNC_DIR=' "$ENV_FILE" | cut -d= -f2- || true)
CONTENT_DIR_VAL=$(grep -s '^CONTENT_DIR=' "$ENV_FILE" | cut -d= -f2- || true)

SYNC_MOUNT=()
if [ -n "$EBDOCS_SYNC_DIR_VAL" ]; then
    mkdir -p "$EBDOCS_SYNC_DIR_VAL"
    SYNC_MOUNT+=(-v "$EBDOCS_SYNC_DIR_VAL:/sync" -e "EBDOCS_SYNC_DIR=/sync")
fi
if [ -n "$CONTENT_DIR_VAL" ]; then
    mkdir -p "$CONTENT_DIR_VAL/gdocs"
    SYNC_MOUNT+=(-v "$CONTENT_DIR_VAL:/content" -e "CONTENT_DIR=/content")
fi

# Theme file (optional)
THEME_MOUNT=()
THEME_SRC="$EARLBEAR_CONFIG_DIR/theme.yaml"
if [ -f "$THEME_SRC" ]; then
    THEME_MOUNT=(-v "$THEME_SRC:/etc/ebdocs/theme.yaml:ro" -e "EBDOCS_THEME_FILE=/etc/ebdocs/theme.yaml")
fi

exec docker run --rm \
    --env-file "$ENV_FILE" \
    "${SYNC_MOUNT[@]+"${SYNC_MOUNT[@]}"}" \
    "${THEME_MOUNT[@]+"${THEME_MOUNT[@]}"}" \
    ebdocs \
    "$@"
