#!/usr/bin/env bash
# tart-test.sh — Tier 3: full clean-room brew install test in a macOS VM.
#
# Uses SSH + rsync to inject the local repo into the VM, patches formula URLs
# to use a local tarball (same pattern as validation/docker/Dockerfile), then
# runs `brew install earlbear` and the smoke test suite.
#
# Why local source matters: tests uncommitted formula changes, not GitHub HEAD.
#
# Requirements:
#   - Apple Silicon Mac
#   - tart: brew install cirruslabs/cli/tart
#   - sshpass: brew install hudochenkov/sshpass/sshpass
#   - Base image: make tart-pull  (~6GB, one-time)
#
# Usage:
#   make validate-vm
#   # or:
#   bash validation/tart/tart-test.sh
#
#   SKIP_DELETE=1 bash validation/tart/tart-test.sh   # keep VM alive for debugging
#
# Debugging:
#   After SKIP_DELETE=1, SSH in manually:
#   ssh -o StrictHostKeyChecking=no admin@$(tart ip <vm-name>)  # password: admin

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VM_NAME="earlbear-test-$(date +%s)"
BASE_IMAGE="${TART_BASE_IMAGE:-ghcr.io/cirruslabs/macos-sequoia-base:latest}"
SKIP_DELETE="${SKIP_DELETE:-0}"
VM_USER="admin"
VM_PASS="admin"

GREEN='\033[0;32m'; RED='\033[0;31m'; BLUE='\033[0;34m'; YELLOW='\033[0;33m'; NC='\033[0m'

# ── Preflight ─────────────────────────────────────────────────────────────────

if [[ "$(uname -m)" != "arm64" ]]; then
    echo -e "${RED}Tart requires Apple Silicon (arm64). Current: $(uname -m)${NC}"
    exit 1
fi

if ! command -v tart >/dev/null 2>&1; then
    echo -e "${YELLOW}tart not found.${NC}"
    echo "Install: brew install cirruslabs/cli/tart"
    echo "Then pull base image: make tart-pull"
    exit 1
fi

if ! command -v sshpass >/dev/null 2>&1; then
    echo -e "${YELLOW}sshpass not found — required for non-interactive SSH to VM.${NC}"
    echo "Install: brew install hudochenkov/sshpass/sshpass"
    exit 1
fi

if ! tart list 2>/dev/null | grep -q "$(basename "$BASE_IMAGE" | cut -d: -f1)" && \
   ! tart list 2>/dev/null | grep -q "macos-sequoia-base"; then
    echo -e "${YELLOW}Base image not found locally. Run: make tart-pull${NC}"
    # Non-fatal: tart clone will pull on demand (slow but works)
fi

# ── Cleanup trap ──────────────────────────────────────────────────────────────

cleanup() {
    if [[ "$SKIP_DELETE" == "1" ]]; then
        echo -e "${YELLOW}==> SKIP_DELETE=1 — VM kept alive: $VM_NAME${NC}"
        echo -e "${YELLOW}    SSH: ssh -o StrictHostKeyChecking=no ${VM_USER}@\$(tart ip $VM_NAME)${NC}"
        echo -e "${YELLOW}    Password: $VM_PASS${NC}"
        echo -e "${YELLOW}    Cleanup: tart delete $VM_NAME${NC}"
        tart stop "$VM_NAME" 2>/dev/null || true
    else
        echo -e "${BLUE}==> Destroying VM: $VM_NAME${NC}"
        tart stop  "$VM_NAME" 2>/dev/null || true
        tart delete "$VM_NAME" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# ── SSH helper (non-interactive, password via sshpass) ────────────────────────

ssh_cmd() {
    sshpass -p "$VM_PASS" ssh \
        -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile=/dev/null \
        -o LogLevel=ERROR \
        -o ConnectTimeout=10 \
        "${VM_USER}@${VM_IP}" "$@"
}

ssh_script() {
    # Pipe a local script over SSH (stdin)
    sshpass -p "$VM_PASS" ssh \
        -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile=/dev/null \
        -o LogLevel=ERROR \
        -o ConnectTimeout=10 \
        "${VM_USER}@${VM_IP}" /bin/bash -s
}

rsync_to_vm() {
    sshpass -p "$VM_PASS" rsync -az \
        --exclude='.git/' \
        --exclude='src/*/dist/' \
        --exclude='src/*/build/' \
        --exclude='*.pyc' \
        --exclude='__pycache__/' \
        --exclude='plugins-bundle/*/bin/*-linux' \
        -e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR" \
        "$@"
}

# ── Step 1: Clone base image ───────────────────────────────────────────────────

echo -e "${BLUE}==> Cloning base VM image: $VM_NAME${NC}"
tart clone "$BASE_IMAGE" "$VM_NAME"

# ── Step 2: Start VM ──────────────────────────────────────────────────────────

echo -e "${BLUE}==> Starting VM (background)...${NC}"
tart run "$VM_NAME" --no-graphics &
VM_PID=$!

# ── Step 3: Wait for SSH ──────────────────────────────────────────────────────

echo -e "${BLUE}==> Waiting for VM IP...${NC}"
VM_IP=""
for i in $(seq 1 30); do
    VM_IP=$(tart ip "$VM_NAME" 2>/dev/null || true)
    [[ -n "$VM_IP" ]] && break
    sleep 2
done
if [[ -z "$VM_IP" ]]; then
    echo -e "${RED}Could not get VM IP after 60s${NC}"
    exit 1
fi
echo -e "${GREEN}    VM IP: $VM_IP${NC}"

echo -e "${BLUE}==> Waiting for SSH to be ready (up to 120s)...${NC}"
SSH_READY=0
for i in $(seq 1 40); do
    if sshpass -p "$VM_PASS" ssh \
        -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile=/dev/null \
        -o LogLevel=ERROR \
        -o ConnectTimeout=5 \
        "${VM_USER}@${VM_IP}" "exit 0" 2>/dev/null; then
        SSH_READY=1
        break
    fi
    sleep 3
done
if [[ "$SSH_READY" -eq 0 ]]; then
    echo -e "${RED}SSH not ready after 120s${NC}"
    exit 1
fi
echo -e "${GREEN}    SSH ready${NC}"

# ── Step 4: rsync local repo into VM ──────────────────────────────────────────

echo -e "${BLUE}==> Syncing local tap source into VM (~5-10s)...${NC}"
ssh_cmd "mkdir -p ~/tap-src"
rsync_to_vm "$REPO_ROOT/" "${VM_USER}@${VM_IP}:~/tap-src/"
echo -e "${GREEN}    Synced${NC}"

# ── Step 5: Install Homebrew + tap + install ───────────────────────────────────

echo -e "${BLUE}==> Installing Homebrew + earlbear tap (this takes ~10min)...${NC}"

ssh_script <<'REMOTE'
set -e

# Install Homebrew if not already present
if ! command -v brew >/dev/null 2>&1; then
    NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

eval "$(/opt/homebrew/bin/brew shellenv)"
export HOMEBREW_NO_AUTO_UPDATE=1

# Turn tap-src into a git repo (brew tap requires git history)
cd ~/tap-src
git init -q
git config user.email "build@tart"
git config user.name "Tart Build"
git add -A
git commit -q -m "tap snapshot"

# Build local tarball + patch formula URLs/sha256
# (Same awk pattern as validation/docker/Dockerfile — only patches formula-level
# sha256, not resource sha256s)
cd ~
tar -czf tap-v1.0.0.tar.gz -C ~ tap-src
LOCAL_SHA=$(shasum -a 256 ~/tap-v1.0.0.tar.gz | awk '{print $1}')
echo "Local tarball sha256: $LOCAL_SHA"

for f in ~/tap-src/Formula/*.rb; do
    sed -i '' \
        "s|url \"https://github.com/bytesofpurpose/homebrew-earlbear/archive/refs/tags/v1.0.0.tar.gz\"|url \"file:///Users/admin/tap-v1.0.0.tar.gz\"|g" \
        "$f"
    awk -v sha="$LOCAL_SHA" \
        '/url "file:\/\/\/Users\/admin\/tap-v1\.0\.0\.tar\.gz"/{found=1}
         found && /^  sha256 "[0-9a-f]{64}"/{sub(/"[0-9a-f]{64}"/, "\"" sha "\""); found=0}
         {print}' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done

cd ~/tap-src
git add Formula/
git commit -q -m "patch local urls"

# Tap from local git repo
brew tap bytesofpurpose/earlbear ~/tap-src

# Install earlbear meta-formula (pulls in all non-Docker formulas)
brew install --build-from-source bytesofpurpose/earlbear/earlbear

echo "✓ Homebrew install complete"
REMOTE

echo -e "${GREEN}    Install complete${NC}"

# ── Step 6: Smoke tests ───────────────────────────────────────────────────────

echo -e "${BLUE}==> Running smoke tests in VM...${NC}"
echo ""

# Add brew to PATH for the smoke test session
{
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"'
    cat "$REPO_ROOT/validation/smoke/smoke-test.sh"
} | ssh_script

echo ""
echo -e "${GREEN}✓ Tart VM validation passed${NC}"
