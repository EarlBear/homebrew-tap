FROM earlbear-cowork-base:local
# cowork-sim/Dockerfile — Tier 5c: cowork simulation image.
#
# Builds on top of earlbear-cowork-base:local (ubuntu + linuxbrew, ~2min base).
# Adds: local tap + sha256 patch + brew install ebdeck + earlbear-plugins.
#
# Used by validation/cowork-sim/cowork-sim-test.sh to simulate:
#   "fresh cowork container → brew install → mount plugins → run shims"
#
# Build context: repo root
#   container build -f validation/cowork-sim/Dockerfile -t earlbear-cowork-sim:local .
#
# One-time base setup:
#   container build -f validation/cowork-sim/Dockerfile.base -t earlbear-cowork-base:local .
#   (or: make cowork-sim-build-base)
#
# Incremental rebuild (formula change, no Homebrew reinstall):
#   make validate-cowork-sim          # rebuilds sim layer only (~1-2min)
#   SKIP_BREW=1 make validate-cowork-sim  # skip image build entirely

# Copy tap source into image (build from local repo, no GitHub auth)
COPY --chown=linuxbrew:linuxbrew . /tmp/tap-src/

USER linuxbrew
WORKDIR /home/linuxbrew

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
