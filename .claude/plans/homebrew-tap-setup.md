# Plan: earlbear-homebrew tap

## Context

EarlBear has four inter-related repos on a developer's Mac:

- `earlbear-clis` — four Python CLIs: `ebjira`, `ebdocs`, `ebshop` (Docker-wrapped), `ebdeck` (host Python venv)
- `earlbear` — `agent-cli` and `ebimg` (standalone bash/Python scripts that wrap `ebjira`)
- `earlbear-sites` — frontend build tooling, no CLIs to install
- `earlbear-claude-plugin-marketplace` — Claude skills, installed via `claude plugin install`

Setting up a new developer machine (or a new team member) currently means: cloning repos, building Docker images, symlinking wrappers, configuring hooks, and installing plugins — all by hand. This repo (`earlbear-homebrew`) becomes a **self-contained Homebrew tap** that automates the Mac setup in a single `brew install` sequence.

**Key decisions:**
- Mac only (Docker for Mac). No Linuxbrew.
- Formulas are self-contained: they bundle wrapper scripts + Dockerfiles so a full clone of `earlbear-clis` is not required at runtime.
- Secrets: document options only for now (see § Secrets Strategy).
- Validation: three-tier regression suite (formula audit, Docker clean-install, Tart macOS VM).

---

## Repo naming

GitHub repo must be named `homebrew-earlbear` (Homebrew tap naming convention).
Local path: `/Users/omareid/Workspace/git/earlbear-homebrew` (already exists, empty).

Users tap with:
```bash
brew tap earlbear/tap https://github.com/EarlBear/homebrew-tap
```

---

## Recipe catalog

The repo hosts **three distinct kinds of recipes**, each with its own directory and purpose:

| Recipe type | Directory | Platform | Purpose |
|---|---|---|---|
| Homebrew formulas | `Formula/` | macOS (dev laptop) | Install CLIs via `brew install` |
| Devcontainer | `devcontainer/` | Linux (Claude cowork sandbox) | Claude Code cowork environment with all EarlBear tooling pre-installed |
| Validation | `validation/` | Any Docker host / Apple Silicon | Regression tests — audit, clean-install, smoke tests |

### Formula catalog (Mac)

| Formula | Mechanism | Target user |
|---|---|---|
| `ebjira` | Docker image + wrapper script | Any EarlBear dev |
| `ebdocs` | Docker image + wrapper script | Any EarlBear dev |
| `ebshop` | Docker image + wrapper script | Any EarlBear dev |
| `ebdeck` | Python venv (`Language::Python::Virtualenv`) | Deck authors |
| `agent-cli` | Bash script; depends on `ebjira` | Agent operators |
| `earlbear-plugins` | Shell script; runs `claude plugin` commands | Claude Code users |
| `earlbear` (meta) | Depends on all above + setup wizard | New developer onboarding |

`ebimg` is out of scope — requires `gemini` CLI + nanobanana extension with no stable versioned release.

### Devcontainer catalog (cowork)

| Recipe | File | Purpose |
|---|---|---|
| Base devcontainer | `devcontainer/Dockerfile` | Ubuntu + brew + python@3.11 + docker CLI (no daemon) |
| devcontainer config | `devcontainer/devcontainer.json` | Claude Code cowork JSON pointing at the Dockerfile |
| Post-create install | `devcontainer/install.sh` | Runs `brew install earlbear` inside container after creation |

Note: The cowork container can't run Docker-in-Docker for the `ebjira`/`ebdocs`/`ebshop` formulas. Those formulas will install wrappers but the Docker images won't build inside the container. The devcontainer is primarily useful for `ebdeck`, `agent-cli`, `earlbear-plugins`, and tooling that doesn't need Docker at runtime.

### Validation catalog (regression)

| Test tier | Directory | What it validates |
|---|---|---|
| Formula audit | `validation/audit/` | `brew audit`, `brew style`, `brew readall` — syntax + policy |
| Docker clean-install | `validation/docker/` | `brew install` in Linux Homebrew container (catches packaging bugs) |
| Tart macOS VM | `validation/tart/` | Full `brew install` in clean macOS VM — closest to real user experience |
| Smoke tests | `validation/smoke/` | Post-install: run each CLI with `--help`, verify exit 0 |

---

## Directory structure

```
earlbear-homebrew/
├── .claude/
│   └── plans/
│       └── homebrew-tap-setup.md         ← this file
│
├── Formula/                              ← Mac: Homebrew .rb formulas
│   ├── ebjira.rb
│   ├── ebdocs.rb
│   ├── ebshop.rb
│   ├── ebdeck.rb
│   ├── agent-cli.rb
│   ├── earlbear-plugins.rb
│   └── earlbear.rb
│
├── src/                                  ← Source bundled into formulas
│   ├── ebjira/
│   │   ├── Dockerfile                    ← copied from earlbear-clis/jira-cli/
│   │   ├── wrapper.sh                    ← adapted from earlbear-clis/bin/ebjira
│   │   └── pyproject.toml               ← copied from earlbear-clis/jira-cli/
│   ├── ebdocs/
│   │   ├── Dockerfile
│   │   ├── wrapper.sh
│   │   └── pyproject.toml
│   ├── ebshop/
│   │   ├── Dockerfile
│   │   ├── wrapper.sh
│   │   └── pyproject.toml
│   ├── ebdeck/
│   │   └── (full deck-cli src — pyproject.toml, src/, etc.)
│   └── agent-cli/
│       └── agent-cli.sh
│
├── plugins-bundle/                       ← Snapshot of marketplace plugins
│   └── (copied from earlbear-claude-plugin-marketplace/plugins/)
│
├── scripts/
│   ├── install-plugins.sh                ← registers marketplace + installs all plugins
│   └── setup-env.sh                      ← interactive ~/.config/earlbear/.env wizard
│
├── devcontainer/                         ← Cowork: Claude Code devcontainer
│   ├── Dockerfile                        ← Ubuntu base + brew + python@3.11
│   ├── devcontainer.json                 ← cowork config
│   └── install.sh                        ← post-create: brew install earlbear (partial)
│
├── validation/                           ← Regression testing
│   ├── Makefile                          ← All test targets
│   ├── audit/
│   │   ├── Dockerfile                    ← FROM homebrew/brew; runs brew audit/style
│   │   └── run-audit.sh
│   ├── docker/
│   │   ├── Dockerfile                    ← FROM homebrew/brew; full brew install test
│   │   └── run-install-test.sh
│   ├── tart/
│   │   ├── README.md                     ← How to set up Tart + macOS VM image
│   │   ├── tart-test.sh                  ← Provisions VM, runs install, reports, destroys
│   │   └── vm-setup.sh                   ← One-time: pull ghcr.io/cirruslabs/macos-sequoia-base
│   └── smoke/
│       └── smoke-test.sh                 ← Post-install CLI smoke tests
│
├── Makefile                              ← Top-level: sync, release, validate
├── .gitleaks.toml
├── .gitattributes                        ← LF for .sh and .rb
├── CLAUDE.md
└── README.md
```

---

## Formula design: Docker-wrapped CLIs (ebjira / ebdocs / ebshop)

Each formula follows this pattern:

```ruby
class Ebjira < Formula
  desc "EarlBear Jira CLI — Docker-wrapped ebjira"
  homepage "https://github.com/EarlBear/homebrew-tap"
  url "https://github.com/EarlBear/homebrew-tap/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "..."
  license "MIT"

  depends_on "docker"

  def install
    (libexec/"ebjira").install "src/ebjira/Dockerfile"
    (libexec/"ebjira").install Dir["src/ebjira/src"]   # Python source for image build
    bin.install "src/ebjira/wrapper.sh" => "ebjira"
  end

  def post_install
    system "docker", "build", "-t", "ebjira", libexec/"ebjira"
  end

  test do
    assert_predicate bin/"ebjira", :executable?
    assert_match "CONFIG_MISSING", shell_output("#{bin}/ebjira issue list 2>&1", 2)
  end
end
```

**Wrapper script adaptation** (repo-independent):
1. Read `.env` from `${EARLBEAR_CONFIG_DIR:-~/.config/earlbear}/.env`
2. Auto-build image if missing (same as original)
3. Mount volumes via env vars (`JIRA_SYNC_DIR`, `MANIFEST_FILE`, etc.) not hardcoded repo paths

---

## Formula design: ebdeck (Python venv)

```ruby
class Ebdeck < Formula
  include Language::Python::Virtualenv

  desc "EarlBear deck generator CLI"
  depends_on "python@3.11"
  depends_on "docker"

  # Resources generated with: brew update-python-resources ebdeck
  resource "typer" do ... end
  resource "rich" do ... end
  resource "pyyaml" do ... end

  def install
    libexec.install "src/ebdeck"
    virtualenv_install_with_resources using: "python@3.11"
    bin.install_symlink libexec/"bin/ebdeck"
  end

  test do
    assert_match "ebdeck", shell_output("#{bin}/ebdeck --help")
  end
end
```

---

## Formula design: earlbear-plugins

```ruby
class EarlbearPlugins < Formula
  desc "EarlBear Claude plugin marketplace — installs all earlbear Claude skills"

  def install
    libexec.install "scripts/install-plugins.sh"
    (libexec/"marketplace").install Dir["plugins-bundle/*"]
  end

  def post_install
    # Requires `claude` on PATH — not a Homebrew dep (Claude Code isn't a formula)
    if which("claude")
      system "#{libexec}/install-plugins.sh", libexec/"marketplace"
    else
      opoo "claude CLI not found — run `#{libexec}/install-plugins.sh` after installing Claude Code"
    end
  end
end
```

---

## Formula design: earlbear (meta)

```ruby
class Earlbear < Formula
  desc "EarlBear — install all CLI tools and Claude plugins in one command"

  depends_on "earlbear/tap/ebjira"
  depends_on "earlbear/tap/ebdocs"
  depends_on "earlbear/tap/ebshop"
  depends_on "earlbear/tap/ebdeck"
  depends_on "earlbear/tap/agent-cli"
  depends_on "earlbear/tap/earlbear-plugins"

  def install
    bin.install "scripts/setup-env.sh" => "earlbear-setup"
  end

  def caveats
    <<~EOS
      Configure credentials:
        earlbear-setup

      Or manually create: ~/.config/earlbear/.env
      See: https://github.com/EarlBear/homebrew-tap#credentials
    EOS
  end
end
```

---

## Devcontainer design (cowork)

`devcontainer/Dockerfile`:
```dockerfile
FROM ubuntu:24.04

# Install Homebrew + python@3.11 + git + curl
RUN apt-get update && apt-get install -y git curl build-essential python3.11 python3.11-venv && \
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

ENV PATH="/home/linuxbrew/.linuxbrew/bin:$PATH"

# Tap earlbear and install non-Docker formulas
# (ebjira/ebdocs/ebshop skipped — no Docker daemon in cowork)
RUN brew tap earlbear/tap https://github.com/EarlBear/homebrew-tap && \
    brew install earlbear/tap/ebdeck \
                 earlbear/tap/agent-cli \
                 earlbear/tap/earlbear-plugins

WORKDIR /workspace
```

`devcontainer/devcontainer.json`:
```json
{
  "name": "EarlBear Cowork",
  "build": { "dockerfile": "Dockerfile" },
  "mounts": [
    "source=${localEnv:HOME}/.config/earlbear,target=/root/.config/earlbear,type=bind,readonly"
  ],
  "remoteEnv": {
    "EARLBEAR_CONFIG_DIR": "/root/.config/earlbear"
  }
}
```

The `~/.config/earlbear/.env` is bind-mounted read-only so credentials flow in from the host without being baked into the image.

---

## Validation / regression suite

### Tier 1: Formula audit (fast, ~30s, no Mac needed)

Uses `homebrew/brew` Docker image to check Ruby syntax, policy compliance, and formula structure.

`validation/audit/Dockerfile`:
```dockerfile
FROM homebrew/brew:latest
COPY Formula/ /tmp/tap/Formula/
RUN brew audit --strict /tmp/tap/Formula/*.rb && \
    brew style /tmp/tap/Formula/*.rb && \
    echo "✓ All formulas pass audit"
```

`make validate-audit`:
```makefile
validate-audit: ## Run brew audit + style check in Docker
    docker build -t earlbear-audit -f validation/audit/Dockerfile .
    docker run --rm earlbear-audit
```

### Tier 2: Docker clean-install (medium, ~5min, no Mac VM needed)

Runs `brew install` from scratch in a `homebrew/brew` Linux container. Catches packaging bugs: missing files in `src/`, broken `bin.install` paths, bad sha256.

`validation/docker/Dockerfile`:
```dockerfile
FROM homebrew/brew:latest

# Point brew at the local tap dir (mounted at build time)
COPY . /tmp/tap/
RUN brew tap earlbear/tap /tmp/tap

# Install non-Docker formulas (Docker daemon not available in container)
RUN brew install --build-from-source earlbear/tap/ebdeck
RUN brew install --build-from-source earlbear/tap/agent-cli

# Smoke test
RUN ebdeck --help && echo "✓ ebdeck OK"
RUN agent-cli help && echo "✓ agent-cli OK"
```

`make validate-docker`:
```makefile
validate-docker: ## Full brew install test in Docker (non-Docker formulas only)
    docker build -t earlbear-install-test -f validation/docker/Dockerfile .
    docker run --rm earlbear-install-test
    @echo "✓ Docker install test passed"
```

### Tier 3: Tart macOS VM (thorough, ~15min, Apple Silicon required)

Provisions a clean macOS VM via [Tart](https://github.com/cirruslabs/tart), runs the full `brew install earlbear` (including Docker formulas since the VM has Docker for Mac), runs smoke tests, then destroys the VM.

`validation/tart/tart-test.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

VM_NAME="earlbear-test-$(date +%s)"
BASE_IMAGE="ghcr.io/cirruslabs/macos-sequoia-base:latest"

echo "==> Pulling base VM image..."
tart pull "$BASE_IMAGE" 2>/dev/null || true

echo "==> Creating clean test VM: $VM_NAME"
tart clone "$BASE_IMAGE" "$VM_NAME"
tart run "$VM_NAME" &
VM_PID=$!

# Wait for SSH
sleep 30

echo "==> Installing Homebrew + tap in VM..."
tart exec "$VM_NAME" -- /bin/bash -c "
  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"
  brew tap earlbear/tap https://github.com/EarlBear/homebrew-tap
  brew install earlbear
"

echo "==> Running smoke tests in VM..."
tart exec "$VM_NAME" -- /bin/bash -c "
  bash /tmp/tap/validation/smoke/smoke-test.sh
"

echo "==> Destroying VM..."
kill $VM_PID 2>/dev/null || true
tart delete "$VM_NAME"

echo "✓ Tart VM validation passed"
```

`make validate-vm`:
```makefile
validate-vm: ## Full brew install test in clean macOS Tart VM (Apple Silicon required)
    @command -v tart >/dev/null || { echo "Install tart: brew install cirruslabs/cli/tart"; exit 1; }
    bash validation/tart/tart-test.sh
```

### Tier 4: Smoke tests (post-install, run anywhere)

`validation/smoke/smoke-test.sh` — runs after install in any environment:
```bash
#!/usr/bin/env bash
# Run each installed CLI with --help and verify exit 0
# No credentials needed — just checks that binaries are on PATH and callable.
set -euo pipefail

PASS=0; FAIL=0

check() {
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "  ✓ $name"
    ((PASS++))
  else
    echo "  ✗ $name (exit $?)"
    ((FAIL++))
  fi
}

check "ebdeck --help"       ebdeck --help
check "agent-cli help"      agent-cli help
check "ebjira --help"       ebjira --help        # expects CONFIG_MISSING, not crash
check "ebdocs --help"       ebdocs --help
check "ebshop --help"       ebshop --help

echo ""
echo "Smoke tests: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
```

### Top-level Makefile validation targets

```makefile
validate-audit:  ## Tier 1 — brew audit + style in Docker (~30s)
validate-docker: ## Tier 2 — full brew install in Docker (~5min)
validate-vm:     ## Tier 3 — full brew install in Tart macOS VM (~15min, Apple Silicon)
validate-smoke:  ## Tier 4 — smoke test locally installed formulas (~10s)
validate:        ## Run all tiers (audit + docker + smoke; skip vm unless CI=1)
    @$(MAKE) validate-audit
    @$(MAKE) validate-docker
    @$(MAKE) validate-smoke
    @if [ "${CI:-0}" = "1" ]; then $(MAKE) validate-vm; fi
```

---

## Env file convention (repo-independent)

Since formulas are self-contained, the old `.env` at repo root breaks. New convention:

```
~/.config/earlbear/
├── .env                    ← all credentials (all CLIs read from here)
├── .env.example            ← installed by earlbear formula
└── manifests/
    └── shopify/
        └── manifest.yaml   ← mounted by ebshop (MANIFEST_FILE env var)
```

Each wrapper reads `${EARLBEAR_CONFIG_DIR:-~/.config/earlbear}/.env`. The `earlbear-setup` wizard scaffolds this interactively on first install.

---

## Secrets strategy (options documented — not yet implemented)

### Option A: 1Password CLI (`op`) — Recommended when team grows
- Secrets in shared 1Password vault; `.env.tpl` committed: `JIRA_API_TOKEN={{ op://EarlBear/Jira/api_token }}`
- `op inject -i ~/.config/earlbear/.env.tpl -o ~/.config/earlbear/.env` once per session
- **Pros:** Zero manual sharing; audit trail; per-person revocation
- **Cons:** Requires 1Password Teams plan; `op` CLI dependency

### Option B: macOS Keychain
- `security add-generic-password -s earlbear-jira -a jira_token -w <token>`
- Wrappers call `security find-generic-password -s earlbear-jira -w` at runtime
- **Pros:** No third-party dep; natively encrypted; offline
- **Cons:** Not shareable; Mac-only; manual per-dev entry

### Option C: `age`-encrypted .env in repo
- Each dev: `age-keygen > ~/.age/earlbear.key`; admin adds pub keys to `.env.enc`
- `age -d -i ~/.age/earlbear.key .env.enc > ~/.config/earlbear/.env`
- **Pros:** Version-controlled; auditable; no SaaS
- **Cons:** Key distribution bootstrap; manual re-encrypt on rotation

### Option D: Static shared .env (current state — default for now)
- Admin sends `.env` via Signal/1Password share; devs drop at `~/.config/earlbear/.env`
- **Pros:** Zero tooling; works today
- **Cons:** No revocation; copy proliferation; no audit trail

**Recommendation:** Option D now with `~/.config/earlbear/.env` as canonical location. Migrate to Option A when ≥2 developers.

---

## Versioning strategy

```makefile
sync-sources: ## Copy latest source from sibling repos into src/
    rsync -av --delete ../earlbear-clis/jira-cli/   src/ebjira/
    rsync -av --delete ../earlbear-clis/gdocs-cli/  src/ebdocs/
    rsync -av --delete ../earlbear-clis/shopify-cli/ src/ebshop/
    rsync -av --delete ../earlbear-clis/deck-cli/   src/ebdeck/
    rsync -av ../earlbear/bin/agent-cli             src/agent-cli/agent-cli.sh
    rsync -av --delete ../earlbear-claude-plugin-marketplace/plugins/ plugins-bundle/

bump-and-release: ## Tag a new release (updates sha256 in formulas, pushes tag)
    @read -p "Version (e.g. 1.0.1): " v && \
    ./scripts/bump-version.sh "$$v" && \
    git tag -a "v$$v" -m "Release v$$v" && \
    git push origin main "v$$v"
```

---

## Implementation steps

1. **Repo init** — `git init`, `.gitattributes` (LF on .sh/.rb), `.gitleaks.toml`, `CLAUDE.md`, `README.md`
2. **src/ scaffold** — `make sync-sources` to copy Dockerfiles + wrappers from sibling repos
3. **Adapt wrappers** — rewrite `$REPO_ROOT/.env` → `${EARLBEAR_CONFIG_DIR:-~/.config/earlbear}/.env` in all three Docker wrapper scripts
4. **Write formulas** — `Formula/{ebjira,ebdocs,ebshop,ebdeck,agent-cli,earlbear-plugins,earlbear}.rb`
5. **Plugin bundle** — `rsync` marketplace plugins into `plugins-bundle/`
6. **setup-env.sh wizard** — interactive credential collector → writes `~/.config/earlbear/.env`
7. **Devcontainer** — `devcontainer/Dockerfile` + `devcontainer.json` (Ubuntu + brew + non-Docker formulas)
8. **Validation suite** — `validation/audit/`, `validation/docker/`, `validation/tart/`, `validation/smoke/`
9. **Makefile** — `sync-sources`, `bump-and-release`, `validate*` targets
10. **Local test** — `make validate-audit && make validate-docker && make validate-smoke`
11. **GitHub repo** — create `EarlBear/homebrew-tap` (private), push, verify `brew tap` works
12. **CLAUDE.md** — document recipe catalog table, update workflow, secrets options, validation tiers

---

## Verification (end-to-end)

```bash
# Step 1: Tier 1 — audit (no Mac VM needed)
make validate-audit

# Step 2: Tier 2 — Docker install (non-Docker formulas)
make validate-docker

# Step 3: Tier 4 — smoke test local install
brew tap earlbear/tap /Users/omareid/Workspace/git/earlbear-homebrew
brew install --build-from-source earlbear/tap/earlbear
make validate-smoke

# Step 4: Tier 3 — full VM test (once tap is pushed to GitHub)
make validate-vm

# Verify plugins
env -u CLAUDECODE claude plugin list | grep earlbear
```
