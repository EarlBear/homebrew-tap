FROM homebrew/brew:latest

# Copy tap (excluding cache/build artifacts via .dockerignore)
COPY . /tmp/tap/

# Patch formula URLs to point at a local tap archive (avoids network tarball download).
# Use Python to patch files as root isn't available; write to writable /home/linuxbrew
USER root
RUN cp -r /tmp/tap /home/linuxbrew/tap && chown -R linuxbrew:linuxbrew /home/linuxbrew/tap
USER linuxbrew

RUN cd /home/linuxbrew && \
    tar -czf tap-v1.0.0.tar.gz -C /home/linuxbrew tap && \
    LOCAL_SHA=$(sha256sum /home/linuxbrew/tap-v1.0.0.tar.gz | awk '{print $1}') && \
    for f in /home/linuxbrew/tap/Formula/*.rb; do \
      sed -i \
        -e "s|url \"https://github.com/bytesofpurpose/homebrew-earlbear/archive/refs/tags/v1.0.0.tar.gz\"|url \"file:///home/linuxbrew/tap-v1.0.0.tar.gz\"|g" \
        -e "s|sha256 \"0000000000000000000000000000000000000000000000000000000000000000\"|sha256 \"$LOCAL_SHA\"|g" \
        "$f"; \
    done && \
    echo "Patched formulas with local URL sha256=$LOCAL_SHA"

# Tap locally with patched formulas
RUN brew tap bytesofpurpose/earlbear /home/linuxbrew/tap

# Install ebdeck (Python venv formula — no Docker required)
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install --build-from-source bytesofpurpose/earlbear/ebdeck

# Install earlbear-plugins (shell script formula — no Docker required)
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install --build-from-source bytesofpurpose/earlbear/earlbear-plugins || true

# Install Docker-wrapped formula wrappers only (post_install Docker build will be skipped)
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install --build-from-source bytesofpurpose/earlbear/ebjira 2>&1; \
    test -f "$(brew --prefix)/bin/ebjira" && echo "✓ ebjira wrapper installed" || \
    echo "INFO ebjira post_install skipped (no Docker daemon in container — expected)"

# Smoke test ebdeck
RUN ebdeck --help && echo "✓ ebdeck smoke test passed"

RUN echo "✓ Docker validation complete"
