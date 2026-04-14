#!/usr/bin/env bash
# plugin-binaries/test.sh — end-to-end validation for cowork plugin binaries.
#
# Full loop: compile all 4 CLIs via Docker PyInstaller → run in ubuntu:24.04 ARM64
# container → assert each binary executes cleanly. Matches the environment of the
# Claude Desktop cowork VM (Ubuntu ARM64).
#
# Requirements:
#   - Apple Silicon Mac (arm64)
#   - Docker (for PyInstaller cross-compile)
#   - apple/container installed + started (for the run step)
#     https://github.com/apple/container/releases
#
# Usage:
#   bash validation/plugin-binaries/test.sh              # all 4 CLIs (~20min compile)
#   SKIP_BUILD=1 bash validation/plugin-binaries/test.sh # reuse existing binaries (~2min)
#   CLI=ebjira bash validation/plugin-binaries/test.sh   # single CLI (~5min compile)

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

# ── CLI definitions ───────────────────────────────────────────────────────────
# Each entry: "plugin-dir:cli-name:expected-help-grep"
# expected-help-grep is a case-insensitive pattern to confirm --help output looks right.

declare -A CLI_PLUGINS=(
    ["ebjira"]="jira-manager"
    ["ebdocs"]="earlbear-docs-manager"
    ["ebshop"]="shopify-manager"
    ["ebdeck"]="deck-manager"
)
declare -A CLI_HELPGREP=(
    ["ebjira"]="ebjira\|jira\|usage"
    ["ebdocs"]="ebdocs\|docs\|usage"
    ["ebshop"]="ebshop\|shopify\|usage"
    ["ebdeck"]="ebdeck\|deck\|usage"
)

# Which CLIs to build (all by default; override with CLI=ebjira for a single one)
TARGET_CLI="${CLI:-}"

# ── Step 1: Compile ───────────────────────────────────────────────────────────

if [[ "${SKIP_BUILD:-0}" == "1" ]]; then
    echo -e "${BLUE}==> Skipping compile (SKIP_BUILD=1) — using existing binaries${NC}"
else
    echo -e "${BLUE}==> Step 1: Compile aarch64-linux binaries via Docker + PyInstaller${NC}"
    if [[ -n "$TARGET_CLI" ]]; then
        make -C "$REPO_ROOT" "build-plugin-${TARGET_CLI}" SKIP_AMD=1
    else
        make -C "$REPO_ROOT" build-plugin-binaries SKIP_AMD=1
    fi
fi

# Verify at least one binary was produced
CLIS_TO_TEST=("${!CLI_PLUGINS[@]}")
if [[ -n "$TARGET_CLI" ]]; then
    CLIS_TO_TEST=("$TARGET_CLI")
fi

for cli in "${CLIS_TO_TEST[@]}"; do
    plugin="${CLI_PLUGINS[$cli]}"
    binary="$REPO_ROOT/plugins-bundle/$plugin/bin/${cli}-aarch64-linux"
    if [[ ! -f "$binary" ]]; then
        echo -e "${RED}Binary not found: $binary${NC}"
        echo "Run without SKIP_BUILD=1 to compile it, or run 'make build-plugin-${cli} SKIP_AMD=1'."
        exit 1
    fi
    echo -e "${GREEN}✓ Found: $binary ($(du -h "$binary" | cut -f1))${NC}"
done

# ── Step 2: Run all binaries in ubuntu:24.04 ARM64 container ──────────────────

echo ""
echo -e "${BLUE}==> Step 2: Run binaries in ubuntu:24.04 ARM64 container${NC}"
echo    "    (Same base as Claude Desktop cowork VM)"

# Build --volume mounts for all plugin bin/ directories (deduplicated)
declare -A MOUNTED_DIRS
VOLUME_ARGS=()
for cli in "${CLIS_TO_TEST[@]}"; do
    plugin="${CLI_PLUGINS[$cli]}"
    bin_dir="$REPO_ROOT/plugins-bundle/$plugin/bin"
    if [[ -z "${MOUNTED_DIRS[$bin_dir]+x}" ]]; then
        MOUNTED_DIRS[$bin_dir]=1
        VOLUME_ARGS+=(--volume "${bin_dir}:/plugin/${plugin}/bin:ro")
    fi
done

container run \
    --name "$CONTAINER_NAME" \
    --detach \
    "${VOLUME_ARGS[@]}" \
    "$UBUNTU_IMAGE" \
    sleep 600

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

for cli in "${CLIS_TO_TEST[@]}"; do
    plugin="${CLI_PLUGINS[$cli]}"
    binary_path="/plugin/${plugin}/bin/${cli}-aarch64-linux"
    helpgrep="${CLI_HELPGREP[$cli]}"

    echo ""
    echo "  ── $cli ──"

    # Binary is present and executable
    check "$cli: binary is executable"  test -x "$binary_path"

    # Runs without crashing (--help exits 0; missing credentials exits 2 — both pass)
    check "$cli: --help runs"           "$binary_path" --help

    # Verify help output looks right
    output=$(container exec "$CONTAINER_NAME" "$binary_path" --help 2>&1 || true)
    if echo "$output" | grep -qiE "$helpgrep"; then
        echo -e "  ${GREEN}✓${NC} $cli: --help output looks correct"
        ((PASS++)) || true
    else
        echo -e "  ${RED}✗${NC} $cli: --help output doesn't look right"
        echo "    output: $(echo "$output" | head -3)"
        ((FAIL++)) || true
    fi

    # No dynamic linker errors
    if echo "$output" | grep -qi "no such file\|cannot open shared\|dynamic linker\|Segmentation"; then
        echo -e "  ${RED}✗${NC} $cli: binary has runtime linker/crash errors"
        echo "    output: $(echo "$output" | head -3)"
        ((FAIL++)) || true
    else
        echo -e "  ${GREEN}✓${NC} $cli: no linker or crash errors"
        ((PASS++)) || true
    fi
done

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
    echo -e "  All binaries run cleanly in ubuntu:24.04 ARM64 — cowork VM compatible."
fi
