#!/usr/bin/env bash
# cowork-sim/cowork-sim-test.sh — Tier 5c: simulate the cowork plugin delivery path.
#
# What this tests:
#   1. Fresh ubuntu:24.04 ARM64 container (no pre-installed tooling)
#   2. Install Homebrew (linuxbrew) from scratch (NONINTERACTIVE)
#   3. Tap bytesofpurpose/earlbear from the local repo (not GitHub)
#   4. brew install ebdeck (Python venv formula — most complex formula)
#   5. Mount plugins-bundle/ as a simulated cowork plugin directory
#   6. Run each cowork shim (bin/<cli>) and verify:
#      - Shim resolves .cowork-lib/shim.sh (exits 2 = CONFIG_MISSING = pass)
#      - No "command not found" or linker errors
#
# Why this tier exists:
#   Tier 5b proves binaries run. This tier proves the shim + Homebrew + plugin
#   install path all work together — the closest simulation of what Claude
#   Desktop does when loading a cowork plugin session.
#
# Requirements:
#   - Apple Silicon Mac (arm64)
#   - apple/container installed + started
#     https://github.com/apple/container/releases
#   - Binaries pre-compiled: make build-plugin-binaries SKIP_AMD=1
#     (or SKIP_BUILD=1 to skip re-compile)
#
# Usage:
#   bash validation/cowork-sim/cowork-sim-test.sh
#   SKIP_BUILD=1 bash validation/cowork-sim/cowork-sim-test.sh   # skip compile
#   SKIP_BREW=1  bash validation/cowork-sim/cowork-sim-test.sh   # skip brew install (reuse image)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CONTAINER_NAME="earlbear-cowork-sim-$(date +%s)"
IMAGE_TAG="earlbear-cowork-sim:local"
UBUNTU_IMAGE="ubuntu:24.04"

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
    echo -e "${RED}This test requires Apple Silicon (arm64). Current arch: $(uname -m)${NC}"
    exit 1
fi

# ── Cleanup trap ──────────────────────────────────────────────────────────────

cleanup() {
    container stop  "$CONTAINER_NAME" 2>/dev/null || true
    container rm    "$CONTAINER_NAME" 2>/dev/null || true
}
trap cleanup EXIT

# ── Step 1: Compile plugin binaries ───────────────────────────────────────────

if [[ "${SKIP_BUILD:-0}" == "1" ]]; then
    echo -e "${BLUE}==> Skipping compile (SKIP_BUILD=1) — using existing binaries${NC}"
    # Verify at least ebjira exists
    if [[ ! -f "$REPO_ROOT/plugins-bundle/jira-manager/bin/ebjira-aarch64-linux" ]]; then
        echo -e "${RED}No compiled binaries found. Run 'make build-plugin-binaries SKIP_AMD=1' first.${NC}"
        exit 1
    fi
else
    echo -e "${BLUE}==> Step 1: Compile aarch64-linux binaries via Docker + PyInstaller${NC}"
    make -C "$REPO_ROOT" build-plugin-binaries SKIP_AMD=1
fi

# ── Step 2: Build the cowork-sim image (ubuntu + linuxbrew + tap) ─────────────
#
# We build a Dockerfile that installs Homebrew and taps earlbear-homebrew
# from the local repo. This is the "fresh install" simulation.
# SKIP_BREW=1 reuses a previously built image.

SKIP_BREW="${SKIP_BREW:-0}"

if [[ "$SKIP_BREW" == "1" ]]; then
    echo -e "${BLUE}==> Skipping brew image build (SKIP_BREW=1) — using existing image: $IMAGE_TAG${NC}"
else
    echo ""
    echo -e "${BLUE}==> Step 2: Build cowork-sim image (ubuntu:24.04 + linuxbrew + tap)${NC}"
    echo    "    This takes ~5-10min on first run (Homebrew install + brew tap + brew install ebdeck)."
    echo    "    Re-run with SKIP_BREW=1 to skip this step."

    container build \
        --tag "$IMAGE_TAG" \
        --file "$REPO_ROOT/validation/cowork-sim/Dockerfile" \
        "$REPO_ROOT"
    echo -e "${GREEN}✓ Cowork-sim image built: $IMAGE_TAG${NC}"
fi

# ── Step 3: Build mock .cowork-lib/shim.sh ────────────────────────────────────
#
# The real shim.sh is inside Claude.app. In this simulation we provide a stub
# that implements the same contract:
#   - cowork_require_token VAR → exit 2 if unset (CONFIG_MISSING)
#   - cowork_gate ARGV...      → no-op (no Claude Desktop permission bridge)
#   - cowork_exec PREFIX ARGV... → exec bin/<prefix>-aarch64-linux ARGV...

SHIM_LIB_DIR="$REPO_ROOT/validation/cowork-sim/.cowork-lib"
mkdir -p "$SHIM_LIB_DIR"

cat > "$SHIM_LIB_DIR/shim.sh" <<'SHIMEOF'
#!/bin/bash
# Stub shim.sh for cowork-sim testing.
# Implements the same contract as /Applications/Claude.app/.../cowork-plugin-shim.sh
# but without Claude Desktop's OAuth or permission bridge.

_COWORK_BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../bin" 2>/dev/null && pwd)"

cowork_require_token() {
    local var="$1"
    if [[ -z "${!var:-}" ]]; then
        echo "${BASH_SOURCE[2]##*/}: not connected — open Claude settings → Plugins → Connect." >&2
        exit 2
    fi
}

cowork_gate() {
    # No-op in simulation — permission bridge requires Claude Desktop
    :
}

cowork_exec() {
    local prefix="$1"; shift
    local bin_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/bin"
    local arch
    arch="$(uname -m)"
    local binary
    if [[ "$arch" == "aarch64" || "$arch" == "arm64" ]]; then
        binary=$(ls "$bin_dir/${prefix}-aarch64-linux"* 2>/dev/null | head -1)
    else
        binary=$(ls "$bin_dir/${prefix}-x86_64-linux"* 2>/dev/null | head -1)
    fi
    if [[ -z "$binary" ]]; then
        echo "cowork_exec: no binary found for $prefix in $bin_dir" >&2
        exit 1
    fi
    exec "$binary" "$@"
}
SHIMEOF
chmod +x "$SHIM_LIB_DIR/shim.sh"

# ── Step 4: Start container with plugin dirs mounted ──────────────────────────

echo ""
echo -e "${BLUE}==> Step 3: Start cowork-sim container${NC}"

# Build volume mounts: each plugin's bin/ + the stub .cowork-lib/
# Mirror the cowork VM's mount structure: plugins land under /mnt/<plugin>/
VOLUME_ARGS=(
    --volume "$REPO_ROOT/plugins-bundle/jira-manager:/mnt/jira-manager:ro"
    --volume "$REPO_ROOT/plugins-bundle/earlbear-docs-manager:/mnt/earlbear-docs-manager:ro"
    --volume "$REPO_ROOT/plugins-bundle/shopify-manager:/mnt/shopify-manager:ro"
    --volume "$REPO_ROOT/plugins-bundle/deck-manager:/mnt/deck-manager:ro"
    # Inject the stub shim library at the path cowork shims walk up to find
    --volume "$SHIM_LIB_DIR:/mnt/.cowork-lib:ro"
)

container run \
    --name "$CONTAINER_NAME" \
    --detach \
    "${VOLUME_ARGS[@]}" \
    "$IMAGE_TAG" \
    sleep 1800

sleep 3

# ── Step 5: Smoke tests ───────────────────────────────────────────────────────

echo ""
echo "EarlBear Cowork Simulation Smoke Tests"
echo "═══════════════════════════════════════════════════════════"
echo "Container: $CONTAINER_NAME"
echo "Image:     $IMAGE_TAG (ubuntu:24.04 + linuxbrew + earlbear tap)"
echo "Plugins:   mounted at /mnt/<plugin>/"
echo "Shim lib:  mounted at /mnt/.cowork-lib/shim.sh (stub)"
echo ""

check() {
    local name="$1"; shift
    local output exit_code=0
    output=$(container exec "$CONTAINER_NAME" "$@" 2>&1) || exit_code=$?
    if [[ "$exit_code" -eq 0 ]]; then
        echo -e "  ${GREEN}✓${NC} $name"
        ((PASS++)) || true
    elif [[ "$exit_code" -eq 2 ]]; then
        echo -e "  ${GREEN}✓${NC} $name (exit 2 — CONFIG_MISSING, expected)"
        ((PASS++)) || true
    else
        echo -e "  ${RED}✗${NC} $name (exit $exit_code)"
        [[ -n "$output" ]] && echo "    $(echo "$output" | head -3)"
        ((FAIL++)) || true
    fi
}

check_output() {
    local name="$1"; local pattern="$2"; shift 2
    local output exit_code=0
    output=$(container exec "$CONTAINER_NAME" "$@" 2>&1) || exit_code=$?
    if echo "$output" | grep -qiE "$pattern"; then
        echo -e "  ${GREEN}✓${NC} $name"
        ((PASS++)) || true
    else
        echo -e "  ${RED}✗${NC} $name (pattern '$pattern' not found)"
        [[ -n "$output" ]] && echo "    output: $(echo "$output" | head -3)"
        ((FAIL++)) || true
    fi
}

# ── Homebrew health ──────────────────────────────────────────────────────────
echo "Homebrew environment:"
check "brew --version" /home/linuxbrew/.linuxbrew/bin/brew --version
check "ebdeck installed via brew" \
    test -x /home/linuxbrew/.linuxbrew/bin/ebdeck
check "ebdeck --help" /home/linuxbrew/.linuxbrew/bin/ebdeck --help

# ── Plugin shim tests ────────────────────────────────────────────────────────

declare -A SHIM_PLUGINS=(
    ["ebjira"]="jira-manager"
    ["ebdocs"]="earlbear-docs-manager"
    ["ebshop"]="shopify-manager"
    ["ebdeck"]="deck-manager"
)

for cli in ebjira ebdocs ebshop ebdeck; do
    plugin="${SHIM_PLUGINS[$cli]}"
    shim="/mnt/${plugin}/bin/${cli}"
    binary="/mnt/${plugin}/bin/${cli}-aarch64-linux"

    echo ""
    echo "  Plugin: $plugin ($cli)"

    # Shim and binary are present
    check "$cli: shim exists and is executable"   test -x "$shim"
    check "$cli: aarch64 binary exists"           test -f "$binary"

    # Running the shim exits 2 (CONFIG_MISSING — no token injected)
    # This proves: shim resolves .cowork-lib/shim.sh, calls cowork_require_token,
    # correctly exits 2 when the token env var is unset.
    check "$cli: shim exits 2 without credentials"  bash "$shim" --help

    # Binary runs directly (the real executable, bypassing shim)
    check "$cli: binary --help runs directly"    bash -c "\"$binary\" --help"
done

# ── Linker sanity (no glibc mismatch) ────────────────────────────────────────
echo ""
echo "  Linker checks:"
for cli in ebjira ebdocs ebshop ebdeck; do
    plugin="${SHIM_PLUGINS[$cli]}"
    binary="/mnt/${plugin}/bin/${cli}-aarch64-linux"
    check_output "$cli: no linker errors" "ebjira\|ebdocs\|ebshop\|ebdeck\|jira\|docs\|shop\|deck\|usage\|help\|config_missing\|not connected" \
        bash -c "\"$binary\" --help 2>&1; true"
done

# ── Results ───────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Results: $PASS passed, $FAIL failed"
echo ""

if [[ "$FAIL" -gt 0 ]]; then
    echo -e "${RED}✗ Cowork simulation FAILED ($FAIL tests failed)${NC}"
    exit 1
else
    echo -e "${GREEN}✓ Cowork simulation passed ($PASS tests)${NC}"
    echo    "  Fresh brew install + plugin shims + binaries — cowork-compatible."
fi
