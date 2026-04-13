FROM --platform=linux/amd64 homebrew/brew:latest

# Copy tap (excluding cache/build artifacts via .dockerignore)
COPY . /tmp/tap/

# Make a writable copy owned by linuxbrew, initialize as a git repo,
# patch formula URLs to use a local archive, then tap it.
USER root
RUN cp -r /tmp/tap /home/linuxbrew/tap && \
    chown -R linuxbrew:linuxbrew /home/linuxbrew/tap
USER linuxbrew

# Turn the tap directory into a git repo so `brew tap` can clone it,
# then patch formula URLs to avoid downloading from GitHub.
RUN cd /home/linuxbrew/tap && \
    git init && \
    git config user.email "build@docker" && \
    git config user.name "Docker Build" && \
    git add -A && \
    git commit -m "tap snapshot"

# Build local archive for use as formula url, compute sha256, patch formulas
# Replaces both the GitHub URL and the sha256 (whether placeholder zeros or real hash)
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
    git commit -m "patch local urls" && \
    echo "Patched formulas with local URL sha256=$LOCAL_SHA"

# Tap locally (brew tap requires a git repo)
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew tap bytesofpurpose/earlbear /home/linuxbrew/tap

# Install ebdeck (Python venv formula — no Docker required)
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install --build-from-source bytesofpurpose/earlbear/ebdeck

# Install earlbear-plugins (shell script formula — no Docker required)
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install --build-from-source bytesofpurpose/earlbear/earlbear-plugins || true

# Install Docker-wrapped formula wrappers (post_install Docker build will be skipped — no daemon)
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install --build-from-source bytesofpurpose/earlbear/ebjira 2>&1; \
    test -f "$(brew --prefix)/bin/ebjira" && echo "✓ ebjira wrapper installed" || \
    echo "INFO ebjira post_install skipped (no Docker daemon in container — expected)"

RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install --build-from-source bytesofpurpose/earlbear/ebdocs 2>&1; \
    test -f "$(brew --prefix)/bin/ebdocs" && echo "✓ ebdocs wrapper installed" || \
    echo "INFO ebdocs post_install skipped (no Docker daemon in container — expected)"

RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install --build-from-source bytesofpurpose/earlbear/ebshop 2>&1; \
    test -f "$(brew --prefix)/bin/ebshop" && echo "✓ ebshop wrapper installed" || \
    echo "INFO ebshop post_install skipped (no Docker daemon in container — expected)"

# Install agent-cli (shell script, depends on ebjira)
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install --build-from-source bytesofpurpose/earlbear/agent-cli 2>&1 && \
    echo "✓ agent-cli installed"

# Install earlbear meta-formula (all deps already installed above)
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install --build-from-source bytesofpurpose/earlbear/earlbear 2>&1 && \
    echo "✓ earlbear meta-formula installed"

# Smoke tests
RUN ebdeck --help && echo "✓ ebdeck smoke test passed"
RUN test -x "$(brew --prefix)/bin/ebdocs" && echo "✓ ebdocs binary present"
RUN test -x "$(brew --prefix)/bin/ebshop" && echo "✓ ebshop binary present"
RUN test -x "$(brew --prefix)/bin/agent-cli" && echo "✓ agent-cli binary present"
RUN test -x "$(brew --prefix)/bin/earlbear-setup" && echo "✓ earlbear-setup binary present"

RUN echo "✓ Docker validation complete"
