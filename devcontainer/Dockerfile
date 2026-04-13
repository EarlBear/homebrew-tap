FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive

# Base dependencies for Homebrew
RUN apt-get update && apt-get install -y \
    git curl build-essential procps file \
    python3.11 python3.11-venv python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Create linuxbrew user (Homebrew installer requires non-root on Linux)
RUN useradd -m -s /bin/bash linuxbrew && \
    echo 'linuxbrew ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

USER linuxbrew
WORKDIR /home/linuxbrew

# Install Homebrew
RUN NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

ENV PATH="/home/linuxbrew/.linuxbrew/bin:/home/linuxbrew/.linuxbrew/sbin:$PATH"

# Tap earlbear
ARG TAP_REPO=https://github.com/bytesofpurpose/homebrew-earlbear
RUN brew tap bytesofpurpose/earlbear "$TAP_REPO"

# Install non-Docker formulas only (no Docker daemon in cowork container)
# - ebdeck: Python venv orchestrator
# - agent-cli: bash wrapper (depends on ebjira being available at runtime)
# - earlbear-plugins: Claude plugin installer
RUN brew install --build-from-source \
    bytesofpurpose/earlbear/ebdeck \
    bytesofpurpose/earlbear/earlbear-plugins

WORKDIR /workspace
