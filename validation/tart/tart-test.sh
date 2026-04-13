#!/usr/bin/env bash
# tart-test.sh — full clean-room brew install test in a macOS VM.
# Requires: tart (brew install cirruslabs/cli/tart), Apple Silicon.

set -euo pipefail

TAP_REPO="${TAP_REPO:-https://github.com/bytesofpurpose/homebrew-earlbear}"
VM_NAME="earlbear-test-$(date +%s)"
BASE_IMAGE="${TART_BASE_IMAGE:-ghcr.io/cirruslabs/macos-sequoia-base:latest}"

GREEN='\033[0;32m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'

cleanup() {
    echo -e "${BLUE}==> Destroying VM: $VM_NAME${NC}"
    tart delete "$VM_NAME" 2>/dev/null || true
}
trap cleanup EXIT

echo -e "${BLUE}==> Cloning base VM image: $VM_NAME${NC}"
tart clone "$BASE_IMAGE" "$VM_NAME"

echo -e "${BLUE}==> Starting VM...${NC}"
tart run "$VM_NAME" --no-graphics &
VM_PID=$!

echo -e "${BLUE}==> Waiting for VM to boot (~30s)...${NC}"
sleep 35

echo -e "${BLUE}==> Installing Homebrew + tap in VM...${NC}"
tart exec "$VM_NAME" -- /bin/bash -s <<EOF
set -e
# Install Homebrew
NONINTERACTIVE=1 /bin/bash -c "\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
eval "\$(/opt/homebrew/bin/brew shellenv)"

# Tap earlbear
brew tap bytesofpurpose/earlbear "$TAP_REPO"

# Install everything
brew install earlbear
EOF

echo -e "${BLUE}==> Running smoke tests in VM...${NC}"
tart exec "$VM_NAME" -- /bin/bash -s < validation/smoke/smoke-test.sh

echo -e "${GREEN}✓ Tart VM validation passed${NC}"
