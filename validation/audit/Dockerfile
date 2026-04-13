FROM homebrew/brew:latest

# Copy tap into image
COPY . /tmp/tap/

# Run brew audit and style check on all formulas
RUN brew tap bytesofpurpose/earlbear /tmp/tap 2>/dev/null || true && \
    echo "==> Running brew style..." && \
    brew style /tmp/tap/Formula/*.rb && \
    echo "==> Running brew audit..." && \
    brew audit --skip-style /tmp/tap/Formula/*.rb && \
    echo "✓ All formulas pass audit and style"
