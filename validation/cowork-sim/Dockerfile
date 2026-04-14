FROM ubuntu:24.04
# cowork-sim/Dockerfile — Tier 5c: cowork simulation image.
#
# Builds ubuntu:24.04 + Homebrew + earlbear tap + installs all non-Docker formulas.
# Used by validation/cowork-sim/cowork-sim-test.sh to simulate:
#   "fresh cowork container → brew install → mount plugins → run shims"
#
# Build context: repo root
#   container build -f validation/cowork-sim/Dockerfile -t earlbear-cowork-sim:local .

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    git curl build-essential procps file \
    python3 python3-venv python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Create linuxbrew user (Homebrew requires non-root on Linux)
RUN useradd -m -s /bin/bash linuxbrew && \
    echo 'linuxbrew ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# Copy tap source into image (build from local repo, no GitHub auth)
COPY --chown=linuxbrew:linuxbrew . /tmp/tap-src/

USER linuxbrew
WORKDIR /home/linuxbrew

# Install Homebrew
RUN NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

ENV PATH="/home/linuxbrew/.linuxbrew/bin:/home/linuxbrew/.linuxbrew/sbin:$PATH"

# Stage tap as a local git repo (brew tap requires git history)
RUN cp -r /tmp/tap-src /home/linuxbrew/tap && \
    cd /home/linuxbrew/tap && \
    git init && \
    git config user.email "build@container" && \
    git config user.name "Container Build" && \
    git add -A && \
    git commit -m "tap snapshot"

# Build local archive + patch formula URLs/sha256s (same pattern as devcontainer/Dockerfile)
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

# Tap from local git repo
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew tap bytesofpurpose/earlbear /home/linuxbrew/tap

# Install all non-Docker formulas:
#   - ebdeck: Python venv CLI (tests the most complex formula)
#   - earlbear-plugins: Claude plugin bundle (install-plugins.sh)
#   Docker-wrapped CLIs (ebjira, ebdocs, ebshop) are NOT installed here
#   because there's no Docker daemon — they're tested via the plugin binary path.
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install --build-from-source \
    bytesofpurpose/earlbear/ebdeck \
    bytesofpurpose/earlbear/earlbear-plugins

WORKDIR /workspace
