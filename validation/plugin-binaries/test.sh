#!/usr/bin/env bash
# plugin-binaries/test.sh — end-to-end validation for cowork plugin binaries.
#
# Full loop: compile via Docker PyInstaller → run in ubuntu:24.04 ARM64
# container → assert binary executes cleanly. Matches the environment of the
# Claude Desktop cowork VM (Ubuntu ARM64).
#
# Requirements:
#   - Apple Silicon Mac (arm64)
#   - Docker (for PyInstaller cross-compile)
#   - apple/container installed + started (for the run step)
#     https://github.com/apple/container/releases
#
# Usage:
#   bash validation/plugin-binaries/test.sh
#   SKIP_BUILD=1 bash validation/plugin-binaries/test.sh  # reuse existing binary

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CONTAINER_NAME="earlbear-plugin-test-$(date +%s)"
UBUNTU_IMAGE="ubuntu:24.04"

GREEN='\033[0;32m'; RED='\033[0;31m'; BLUE='\033[0;34m'; YELLOW='\033[0;33m'; NC='\033[0m'

PASS=0; FAIL=0

# ── Preflight ─────────────────────────────────────────────────────────────────

if [[ "$(uname -m)" != "arm64" ]]; then
    echo -e "${RED}This test requires Apple Silicon (arm64). Current arch: $(uname -m)${NC}"
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo -e "${RED}Docker not found — required for PyInstaller cross-compile step.${NC}"
    exit 1
fi

if ! command -v container >/dev/null 2>&1; then
    echo -e "${YELLOW}apple/container CLI not found.${NC}"
    echo "Install from: https://github.com/apple/container/releases"
    echo "Then run: container system start"
    exit 1
fi

# ── Cleanup trap ──────────────────────────────────────────────────────────────

cleanup() {
    container stop  "$CONTAINER_NAME" 2>/dev/null || true
    container rm    "$CONTAINER_NAME" 2>/dev/null || true
}
trap cleanup EXIT

# ── Step 1: Compile ───────────────────────────────────────────────────────────

BINARY="$REPO_ROOT/plugins-bundle/jira-manager/bin/ebjira-aarch64-linux"

if [[ "${SKIP_BUILD:-0}" == "1" ]]; then
    echo -e "${BLUE}==> Skipping compile (SKIP_BUILD=1) — using existing binary${NC}"
    if [[ ! -f "$BINARY" ]]; then
        echo -e "${RED}Binary not found: $BINARY${NC}"
        echo "Run without SKIP_BUILD=1 to compile it first."
        exit 1
    fi
else
    echo -e "${BLUE}==> Step 1: Compile ebjira-aarch64-linux via Docker + PyInstaller${NC}"
    make -C "$REPO_ROOT" build-plugin-ebjira SKIP_AMD=1
    if [[ ! -f "$BINARY" ]]; then
        echo -e "${RED}Compile step succeeded but binary not found at: $BINARY${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Binary compiled: $BINARY ($(du -h "$BINARY" | cut -f1))${NC}"
fi

# ── Step 2: Run in ubuntu:24.04 ARM64 container ───────────────────────────────

echo ""
echo -e "${BLUE}==> Step 2: Run binary in ubuntu:24.04 ARM64 container${NC}"
echo    "    (Same base as Claude Desktop cowork VM)"

# Mount the bin/ directory directly into the container at /plugin/bin so we
# can exec the binary without needing `container cp` (not supported in all
# apple/container versions).
PLUGIN_BIN_DIR="$(dirname "$BINARY")"

container run \
    --name "$CONTAINER_NAME" \
    --detach \
    --volume "$PLUGIN_BIN_DIR:/plugin/bin:ro" \
    "$UBUNTU_IMAGE" \
    sleep 300

sleep 2

# ── Step 3: Verify ────────────────────────────────────────────────────────────

echo ""
echo "EarlBear Plugin Binary Smoke Tests (ubuntu:24.04 ARM64)"
echo "────────────────────────────────────────────────────────"

check() {
    local name="$1"; shift
    local output exit_code=0
    output=$(container exec "$CONTAINER_NAME" "$@" 2>&1) || exit_code=$?
    if [[ "$exit_code" -eq 0 ]]; then
        echo -e "  ${GREEN}✓${NC} $name"
        ((PASS++)) || true
    elif [[ "$exit_code" -eq 2 ]]; then
        # Exit 2 = CONFIG_MISSING (no credentials in test env) — expected
        echo -e "  ${GREEN}✓${NC} $name (CONFIG_MISSING — expected in test env)"
        ((PASS++)) || true
    else
        echo -e "  ${RED}✗${NC} $name (exit $exit_code)"
        [[ -n "$output" ]] && echo "    output: $(echo "$output" | head -5)"
        ((FAIL++)) || true
    fi
}

# Binary is present and executable
check "binary is executable"         test -x /plugin/bin/ebjira-aarch64-linux

# Runs without crashing (--help exits 0; missing credentials exits 2 — both pass)
check "ebjira --help runs"           /plugin/bin/ebjira-aarch64-linux --help

# Verify it's the right binary (output should mention ebjira)
output=$(container exec "$CONTAINER_NAME" /plugin/bin/ebjira-aarch64-linux --help 2>&1 || true)
if echo "$output" | grep -qi "ebjira\|jira\|usage"; then
    echo -e "  ${GREEN}✓${NC} --help output mentions ebjira/jira"
    ((PASS++)) || true
else
    echo -e "  ${RED}✗${NC} --help output doesn't look like ebjira"
    echo "    output: $(echo "$output" | head -3)"
    ((FAIL++)) || true
fi

# No dynamic linker errors (would show up in output)
if echo "$output" | grep -qi "no such file\|cannot open shared\|dynamic linker\|Segmentation"; then
    echo -e "  ${RED}✗${NC} binary has runtime linker/crash errors"
    echo "    output: $(echo "$output" | head -3)"
    ((FAIL++)) || true
else
    echo -e "  ${GREEN}✓${NC} no linker or crash errors"
    ((PASS++)) || true
fi

# ── Results ───────────────────────────────────────────────────────────────────

echo ""
echo "────────────────────────────────────────────────────────"
echo "Results: $PASS passed, $FAIL failed"
echo ""

if [[ "$FAIL" -gt 0 ]]; then
    echo -e "${RED}✗ Plugin binary validation FAILED ($FAIL tests failed)${NC}"
    exit 1
else
    echo -e "${GREEN}✓ Plugin binary validation passed ($PASS tests)${NC}"
    echo -e "  Binary runs cleanly in ubuntu:24.04 ARM64 — cowork VM compatible."
fi
