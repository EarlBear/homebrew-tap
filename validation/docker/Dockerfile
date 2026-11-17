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
# Replaces both the GitHub URL and the sha256 (whether placeholder zeros or real hash).
# The tag is read from the formulas and the URL match takes any tag (vX.Y.Z), so a new
# release needs no edit here. The tarball keeps the tag in its name because Homebrew
# reads the formula version from the file name.
RUN cd /home/linuxbrew && \
    TAG=$(sed -n 's|.*homebrew-tap/archive/refs/tags/\(v[0-9][0-9.]*[0-9]\)\.tar\.gz.*|\1|p' tap/Formula/*.rb | head -1) && \
    test -n "$TAG" && echo "Formulas point at tag $TAG" && \
    tar -czf "tap-$TAG.tar.gz" -C /home/linuxbrew tap && \
    LOCAL_URL="file:///home/linuxbrew/tap-$TAG.tar.gz" && \
    LOCAL_SHA=$(sha256sum "/home/linuxbrew/tap-$TAG.tar.gz" | awk '{print $1}') && \
    for f in /home/linuxbrew/tap/Formula/*.rb; do \
      sed -i \
        -e "s|url \"https://github.com/EarlBear/homebrew-tap/archive/refs/tags/v[0-9][0-9.]*\.tar\.gz\"|url \"$LOCAL_URL\"|g" \
        "$f"; \
      awk -v sha="$LOCAL_SHA" -v url="$LOCAL_URL" \
        'index($0, url){found=1} \
         found && /^  sha256 "[0-9a-f]{64}"/{sub(/"[0-9a-f]{64}"/, "\"" sha "\""); found=0} \
         {print}' "$f" > "$f.tmp" && mv "$f.tmp" "$f"; \
    done && \
    cd /home/linuxbrew/tap && \
    git add Formula/ && \
    git commit -m "patch local urls" && \
    echo "Patched formulas with local URL sha256=$LOCAL_SHA"

# Bring Homebrew itself up to date once. The image's Homebrew can be older than the
# formula and bottle data it downloads, and then installs fail on code it does not know
# (seen 2026-11-16: "Unexpected method 'postflight_steps' called on Cask docker-desktop").
RUN brew update

# Tap locally (brew tap requires a git repo)
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew tap earlbear/tap /home/linuxbrew/tap

# Install ebdeck (Python venv formula — no Docker required)
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install earlbear/tap/ebdeck

# Install ebtranscripts (Python venv formula — no Docker required)
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install earlbear/tap/ebtranscripts

# Install earlbear-plugins (shell script formula — installs the plugin installer only)
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install earlbear/tap/earlbear-plugins && \
    test -x "$(brew --prefix earlbear-plugins)/libexec/install-plugins.sh" && \
    echo "✓ earlbear-plugins installer present"

# Install the Docker-wrapped formulas. They have no post_install: the wrapper
# builds its Docker image on first run, so no Docker daemon is needed here.
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install earlbear/tap/ebjira 2>&1 && \
    test -x "$(brew --prefix)/bin/ebjira" && echo "✓ ebjira wrapper installed"

RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install earlbear/tap/ebdocs 2>&1 && \
    test -x "$(brew --prefix)/bin/ebdocs" && echo "✓ ebdocs wrapper installed"

RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install earlbear/tap/ebshop 2>&1 && \
    test -x "$(brew --prefix)/bin/ebshop" && echo "✓ ebshop wrapper installed"

# Install agent-cli (shell script, depends on ebjira)
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install earlbear/tap/agent-cli 2>&1 && \
    echo "✓ agent-cli installed"

# Install earlbear meta-formula (all deps already installed above)
RUN HOMEBREW_NO_AUTO_UPDATE=1 brew install earlbear/tap/earlbear 2>&1 && \
    echo "✓ earlbear meta-formula installed"

# Smoke tests
RUN ebdeck --help && echo "✓ ebdeck smoke test passed"
RUN test -x "$(brew --prefix)/bin/ebdocs" && echo "✓ ebdocs binary present"
RUN test -x "$(brew --prefix)/bin/ebshop" && echo "✓ ebshop binary present"
RUN test -x "$(brew --prefix)/bin/agent-cli" && echo "✓ agent-cli binary present"
RUN test -x "$(brew --prefix)/bin/earlbear-setup" && echo "✓ earlbear-setup binary present"

RUN echo "✓ Docker validation complete"
