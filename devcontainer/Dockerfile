FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive

# Base dependencies for Homebrew
RUN apt-get update && apt-get install -y \
    git curl build-essential procps file \
    python3 python3-venv python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Create linuxbrew user (Homebrew installer requires non-root on Linux)
RUN useradd -m -s /bin/bash linuxbrew && \
    echo 'linuxbrew ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# Copy tap source into image (no GitHub auth required — build from repo root)
# container build -f devcontainer/Dockerfile -t earlbear-cowork:local .
COPY --chown=linuxbrew:linuxbrew . /tmp/tap-src/

USER linuxbrew
WORKDIR /home/linuxbrew

# Install Homebrew
RUN NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

ENV PATH="/home/linuxbrew/.linuxbrew/bin:/home/linuxbrew/.linuxbrew/sbin:$PATH"

# Stage tap: copy local source, init as git repo (required by brew tap)
RUN cp -r /tmp/tap-src /home/linuxbrew/tap && \
    cd /home/linuxbrew/tap && \
    git init && \
    git config user.email "build@container" && \
    git config user.name "Container Build" && \
    git add -A && \
    git commit -m "tap snapshot"

# Build local archive, compute sha256, patch formula URLs + sha256s
# Uses the same awk pattern as validation/docker/Dockerfile to only patch
# the formula-level sha256 (not resource sha256s).
RUN cd /home/linuxbrew && \
    tar -czf tap-v1.0.0.tar.gz -C /home/linuxbrew tap && \
    LOCAL_SHA=$(sha256sum /home/linuxbrew/tap-v1.0.0.tar.gz | awk '{print $1}') && \
    for f in /home/linuxbrew/tap/Formula/*.rb; do \
      sed -i \
        -e "s|url \"https://github.com/bytesofpurpose/homebrew-earlbear/archive/refs/tags/v1.0.0.tar.gz\"|url \"file:///home/linuxbrew/tap-v1.0.0.tar.gz\"|g" \
        "$f"; \
      awk -v sha="$LOCAL_SHA" \
        '/url "file:\/\/\/home\/linuxbrew\/tap-v1\.0\.0\.tar\.gz"/{found=1} \
         found && /^  sha256 "[0-9a-f]{64}"/{sub(/"[0-9a-f]{64}"/, "\"" sha "\""); found=0} \
         {print}' "$f" > "$f.tmp" && mv "$f.tmp" "$f"; \
    done && \
    cd /home/linuxbrew/tap && \
    git add Formula/ && \
    git commit -m "patch local urls"

# Tap from local git repo (no network auth required)
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew tap bytesofpurpose/earlbear /home/linuxbrew/tap

# Install non-Docker formulas only (no Docker daemon in cowork container)
# - ebdeck: Python venv orchestrator (the primary cowork tool)
# - earlbear-plugins: Claude plugin bundle
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install --build-from-source \
    bytesofpurpose/earlbear/ebdeck \
    bytesofpurpose/earlbear/earlbear-plugins

WORKDIR /workspace
