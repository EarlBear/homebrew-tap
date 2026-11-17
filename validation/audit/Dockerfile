FROM --platform=linux/amd64 homebrew/brew:latest

# Update Homebrew and fetch its formula index before the tap is copied in. The index is
# large (about 35 MB), so this layer stays cached and a re-run only re-checks the formulas.
RUN brew update

# Copy tap into image
COPY --chown=linuxbrew:linuxbrew . /tmp/tap/

# brew tap only accepts a git repo, and .dockerignore leaves .git out, so make one here.
RUN cd /tmp/tap && \
    git init -q && \
    git -c user.email=audit@docker -c user.name=audit add -A && \
    git -c user.email=audit@docker -c user.name=audit commit -q -m "tap snapshot"

# Run brew style and audit (no network fetch needed for these). The tap must succeed:
# without it brew audit cannot find any earlbear/tap formula. Homebrew 7 refuses to load
# formulas from a tap nobody has trusted, so trust it right after tapping.
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew tap earlbear/tap /tmp/tap && \
    brew trust earlbear/tap && \
    echo "==> Running brew style..." && \
    brew style /tmp/tap/Formula/*.rb && \
    echo "==> Running brew audit..." && \
    HOMEBREW_NO_AUTO_UPDATE=1 brew audit --skip-style earlbear/tap/ebjira \
               earlbear/tap/ebdocs \
               earlbear/tap/ebshop \
               earlbear/tap/ebdeck \
               earlbear/tap/agent-cli \
               earlbear/tap/earlbear-plugins \
               earlbear/tap/earlbear && \
    echo "✓ All formulas pass audit and style"
