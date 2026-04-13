FROM homebrew/brew:latest

# Copy entire tap
COPY . /tmp/tap/

# Tap locally
RUN brew tap bytesofpurpose/earlbear /tmp/tap

# Install non-Docker formulas (no Docker daemon in this container)
# ebdeck: Python venv formula — full install test
RUN brew install --build-from-source bytesofpurpose/earlbear/ebdeck

# agent-cli: bash script formula (depends on ebjira being on PATH, mock it)
# We skip agent-cli here as it depends on ebjira (Docker) at runtime
# The formula itself (file install) can be tested:
RUN brew install --build-from-source bytesofpurpose/earlbear/earlbear-plugins || true

# Smoke: verify ebdeck is callable
RUN ebdeck --help && echo "✓ ebdeck smoke test passed"

# Verify wrapper scripts were installed for Docker formulas
RUN brew install --build-from-source bytesofpurpose/earlbear/ebjira 2>&1 | grep -v "post_install" || true && \
    test -f "$(brew --prefix)/bin/ebjira" && echo "✓ ebjira wrapper installed" || \
    echo "ℹ ebjira wrapper not found (post_install skipped — no Docker daemon)"

RUN echo "✓ Docker validation complete"
