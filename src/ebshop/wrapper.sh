#!/usr/bin/env bash
# ebshop — wrapper installed by the Homebrew formula.
# Proxies commands into the ebshop Docker container.
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
FORMULA_LIBEXEC="$(brew --cellar ebshop)/$(brew list --versions ebshop | awk '{print $2}')/libexec/ebshop"
if ! docker image inspect ebshop >/dev/null 2>&1; then
    echo '{"status": "building", "message": "Building ebshop Docker image (first run)..."}' >&2
    docker build -t ebshop -q "$FORMULA_LIBEXEC" >&2
fi

# Mount manifest
MANIFEST_FILE="${MANIFEST_FILE:-$EARLBEAR_CONFIG_DIR/manifests/shopify/manifest.yaml}"
MOUNT_ARGS=()
if [ -f "$MANIFEST_FILE" ]; then
    MOUNT_ARGS=(-v "$MANIFEST_FILE:/app/assets/manifest.yaml:ro" -e "MANIFEST_FILE=/app/assets/manifest.yaml")
fi

exec docker run --rm \
    --env-file "$ENV_FILE" \
    "${MOUNT_ARGS[@]}" \
    ebshop \
    "$@"
