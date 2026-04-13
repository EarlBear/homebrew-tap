FROM --platform=linux/amd64 homebrew/brew:latest

# Copy tap into image
COPY . /tmp/tap/

# Run brew style and audit (no network fetch needed for these)
RUN brew tap bytesofpurpose/earlbear /tmp/tap 2>/dev/null || true && \
    echo "==> Running brew style..." && \
    brew style /tmp/tap/Formula/*.rb && \
    echo "==> Running brew audit..." && \
    brew audit --skip-style bytesofpurpose/earlbear/ebjira \
               bytesofpurpose/earlbear/ebdocs \
               bytesofpurpose/earlbear/ebshop \
               bytesofpurpose/earlbear/ebdeck \
               bytesofpurpose/earlbear/agent-cli \
               bytesofpurpose/earlbear/earlbear-plugins \
               bytesofpurpose/earlbear/earlbear && \
    echo "✓ All formulas pass audit and style"
