FROM --platform=linux/amd64 homebrew/brew:latest

# Copy tap into image
COPY . /tmp/tap/

# Run brew style and audit (no network fetch needed for these)
RUN brew tap earlbear/tap /tmp/tap 2>/dev/null || true && \
    echo "==> Running brew style..." && \
    brew style /tmp/tap/Formula/*.rb && \
    echo "==> Running brew audit..." && \
    brew audit --skip-style earlbear/tap/ebjira \
               earlbear/tap/ebdocs \
               earlbear/tap/ebshop \
               earlbear/tap/ebdeck \
               earlbear/tap/agent-cli \
               earlbear/tap/earlbear-plugins \
               earlbear/tap/earlbear && \
    echo "✓ All formulas pass audit and style"
