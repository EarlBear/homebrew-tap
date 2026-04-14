#!/usr/bin/env bash
# tart-build-base.sh — build a Tart VM snapshot with Homebrew pre-installed.
#
# Creates earlbear-brew-base:local from the pinned macOS base image.
# This snapshot has Homebrew already installed so that validate-vm
# (tart-test.sh) can skip the ~5min `brew install` step on every run.
#
# Usage:
#   make tart-build-base      # one-time, or after upgrading the pinned image
#
# The snapshot is cloned by tart-test.sh when USE_BASE_SNAPSHOT=1 (default).
# To bypass the snapshot and start from the raw base image:
#   USE_BASE_SNAPSHOT=0 make validate-vm

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SNAPSHOT_NAME="earlbear-brew-base"
BASE_IMAGE="${TART_BASE_IMAGE:-ghcr.io/cirruslabs/macos-sequoia-base@sha256:2344190688dffe76ad38ebe375671759d9accee2821f36bcc0203cca1e90fced}"
BUILD_VM="earlbear-brew-base-build-$(date +%s)"
VM_USER="admin"
VM_PASS="admin"

GREEN='\033[0;32m'; RED='\033[0;31m'; BLUE='\033[0;34m'; YELLOW='\033[0;33m'; NC='\033[0m'

_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o IdentitiesOnly=yes -o ConnectTimeout=10"

ssh_cmd() {
    sshpass -p "$VM_PASS" ssh $_SSH_OPTS "${VM_USER}@${VM_IP}" "$@"
}

ssh_script() {
    sshpass -p "$VM_PASS" ssh $_SSH_OPTS "${VM_USER}@${VM_IP}" /bin/bash -s
}

cleanup() {
    # Only runs on failure — if rename succeeded, trap is cleared before cleanup fires.
    echo -e "${BLUE}==> Destroying build VM: $BUILD_VM${NC}"
    tart stop  "$BUILD_VM" 2>/dev/null || true
    tart delete "$BUILD_VM" 2>/dev/null || true
}
trap cleanup EXIT

# ── Preflight ─────────────────────────────────────────────────────────────────

if [[ "$(uname -m)" != "arm64" ]]; then
    echo -e "${RED}tart requires Apple Silicon. Current: $(uname -m)${NC}"
    exit 1
fi

# ── Remove existing snapshot ──────────────────────────────────────────────────

if tart list 2>/dev/null | grep -q "$SNAPSHOT_NAME"; then
    echo -e "${YELLOW}==> Removing existing snapshot: $SNAPSHOT_NAME${NC}"
    tart delete "$SNAPSHOT_NAME" 2>/dev/null || true
fi

# ── Clone base image → build VM ───────────────────────────────────────────────

echo -e "${BLUE}==> Cloning base image for build VM: $BUILD_VM${NC}"
tart clone "$BASE_IMAGE" "$BUILD_VM"

echo -e "${BLUE}==> Starting build VM...${NC}"
tart run "$BUILD_VM" --no-graphics &
VM_PID=$!

# Wait for IP
VM_IP=""
for i in $(seq 1 30); do
    VM_IP=$(tart ip "$BUILD_VM" 2>/dev/null || true)
    [[ -n "$VM_IP" ]] && break
    sleep 2
done
if [[ -z "$VM_IP" ]]; then
    echo -e "${RED}Could not get VM IP after 60s${NC}"
    exit 1
fi
echo -e "${GREEN}    VM IP: $VM_IP${NC}"

# Wait for SSH
echo -e "${BLUE}==> Waiting for SSH...${NC}"
SSH_READY=0
for i in $(seq 1 40); do
    if sshpass -p "$VM_PASS" ssh \
        -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o LogLevel=ERROR -o IdentitiesOnly=yes -o ConnectTimeout=5 \
        "${VM_USER}@${VM_IP}" "exit 0" 2>/dev/null; then
        SSH_READY=1; break
    fi
    sleep 3
done
[[ "$SSH_READY" -eq 0 ]] && { echo -e "${RED}SSH not ready after 120s${NC}"; exit 1; }
echo -e "${GREEN}    SSH ready${NC}"

# ── Install Homebrew in build VM ─────────────────────────────────────────────

echo -e "${BLUE}==> Installing Homebrew (~5min)...${NC}"

ssh_script <<'REMOTE'
set -e
NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
eval "$(/opt/homebrew/bin/brew shellenv)"
# Verify brew is functional
brew --version
echo "✓ Homebrew installed"
REMOTE

echo -e "${GREEN}    Homebrew installed${NC}"

# ── Stop VM and snapshot ──────────────────────────────────────────────────────

echo -e "${BLUE}==> Stopping build VM...${NC}"
tart stop "$BUILD_VM" 2>/dev/null || true
# Wait for it to fully stop
sleep 5

echo -e "${BLUE}==> Saving snapshot: $SNAPSHOT_NAME${NC}"
# Rename the build VM to the snapshot name.
# Disable the cleanup trap first so it doesn't delete the renamed VM.
trap - EXIT
tart rename "$BUILD_VM" "$SNAPSHOT_NAME"

# Verify snapshot exists
if tart list 2>/dev/null | grep -q "$SNAPSHOT_NAME"; then
    echo -e "${GREEN}✓ Snapshot saved: $SNAPSHOT_NAME${NC}"
    echo -e "${GREEN}  validate-vm will use this snapshot (clones in ~5s, skips Homebrew install)${NC}"
    echo -e "${GREEN}  Rebuild when: pinned BASE_IMAGE digest changes${NC}"
else
    echo -e "${RED}Snapshot not found after rename — check tart list${NC}"
    exit 1
fi
