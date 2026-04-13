#!/usr/bin/env bash
# cowork-test.sh — regression test for the EarlBear cowork devcontainer.
# Builds the devcontainer image using apple/container, runs smoke tests inside
# it via `container exec`, then cleans up.
#
# Requirements:
#   - Apple Silicon Mac running macOS 26+
#   - apple/container installed: https://github.com/apple/container/releases
#   - container system started: container system start
#
# Usage:
#   bash validation/cowork/cowork-test.sh
#   SKIP_BUILD=1 bash validation/cowork/cowork-test.sh   # reuse existing image

set -euo pipefail

IMAGE_TAG="earlbear-cowork-test:local"
CONTAINER_NAME="earlbear-cowork-$(date +%s)"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

GREEN='\033[0;32m'; RED='\033[0;31m'; BLUE='\033[0;34m'; YELLOW='\033[0;33m'; NC='\033[0m'

PASS=0; FAIL=0

# ── Preflight ─────────────────────────────────────────────────────────────────

if ! command -v container >/dev/null 2>&1; then
    echo -e "${YELLOW}apple/container CLI not found.${NC}"
    echo "Install from: https://github.com/apple/container/releases"
    echo "Then run: container system start"
    exit 1
fi

if [[ "$(uname -m)" != "arm64" ]]; then
    echo -e "${RED}apple/container requires Apple Silicon (arm64). Current arch: $(uname -m)${NC}"
    exit 1
fi

# ── Cleanup trap ──────────────────────────────────────────────────────────────

cleanup() {
    echo -e "${BLUE}==> Cleaning up container: $CONTAINER_NAME${NC}"
    container stop "$CONTAINER_NAME" 2>/dev/null || true
    container rm   "$CONTAINER_NAME" 2>/dev/null || true
}
trap cleanup EXIT

# ── Build ─────────────────────────────────────────────────────────────────────

if [[ "${SKIP_BUILD:-0}" == "1" ]]; then
    echo -e "${BLUE}==> Skipping build (SKIP_BUILD=1) — using existing image: $IMAGE_TAG${NC}"
else
    echo -e "${BLUE}==> Building cowork devcontainer image (~10min first run)...${NC}"
    container build \
        --tag "$IMAGE_TAG" \
        --file "$REPO_ROOT/devcontainer/Dockerfile" \
        "$REPO_ROOT"
    echo -e "${GREEN}✓ Image built: $IMAGE_TAG${NC}"
fi

# ── Start persistent container ────────────────────────────────────────────────

echo -e "${BLUE}==> Starting container: $CONTAINER_NAME${NC}"
# Run a persistent sleep so we can exec individual test commands without
# paying per-VM startup cost for each check.
container run \
    --name "$CONTAINER_NAME" \
    --detach \
    "$IMAGE_TAG" \
    sleep 3600

sleep 3

# ── Test helpers ──────────────────────────────────────────────────────────────

check() {
    local name="$1"; shift
    local output exit_code=0
    output=$(container exec "$CONTAINER_NAME" "$@" 2>&1) || exit_code=$?
    if [[ "$exit_code" -eq 0 ]]; then
        echo -e "  ${GREEN}✓${NC} $name"
        ((PASS++)) || true
    elif [[ "$exit_code" -eq 2 ]]; then
        # Exit 2 = CONFIG_MISSING — expected when no .env is mounted
        echo -e "  ${GREEN}✓${NC} $name (CONFIG_MISSING — expected)"
        ((PASS++)) || true
    else
        echo -e "  ${RED}✗${NC} $name (exit $exit_code)"
        [[ -n "$output" ]] && echo "    $(echo "$output" | head -3)"
        ((FAIL++)) || true
    fi
}

# ── Smoke tests ───────────────────────────────────────────────────────────────

echo ""
echo "EarlBear Cowork Devcontainer Smoke Tests"
echo "────────────────────────────────────────"

# Homebrew runtime
check "brew --version"                brew --version

# ebdeck — primary cowork CLI
check "ebdeck --help"                 ebdeck --help
check "ebdeck binary at brew bin"     test -x /home/linuxbrew/.linuxbrew/bin/ebdeck

# earlbear-plugins formula
check "brew list earlbear-plugins"    brew list --formula bytesofpurpose/earlbear/earlbear-plugins
check "install-plugins.sh at libexec" \
    test -f /home/linuxbrew/.linuxbrew/opt/earlbear-plugins/libexec/install-plugins.sh
check "install-plugins.sh executable" \
    test -x /home/linuxbrew/.linuxbrew/opt/earlbear-plugins/libexec/install-plugins.sh
check "marketplace.json present" \
    test -f /home/linuxbrew/.linuxbrew/opt/earlbear-plugins/libexec/marketplace/.claude-plugin/marketplace.json

# Structural invariants
check "PATH includes linuxbrew bin" \
    bash -c 'echo "$PATH" | grep -q /home/linuxbrew/.linuxbrew/bin'
check "WORKDIR is /workspace"         bash -c 'test "$(pwd)" = /workspace'

# Python toolchain (ebdeck venv dependency)
check "python3.11 available"          python3.11 --version
check "ebdeck Python package importable" \
    bash -c '/home/linuxbrew/.linuxbrew/opt/ebdeck/libexec/venv/bin/python -c "import ebdeck"'

# ── Results ───────────────────────────────────────────────────────────────────

echo ""
echo "────────────────────────────────────────"
echo "Results: $PASS passed, $FAIL failed"
echo ""

if [[ "$FAIL" -gt 0 ]]; then
    echo -e "${RED}✗ Cowork validation FAILED ($FAIL tests failed)${NC}"
    exit 1
else
    echo -e "${GREEN}✓ Cowork devcontainer validation passed ($PASS tests)${NC}"
fi
