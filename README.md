# homebrew-earlbear

EarlBear Homebrew tap — install all EarlBear CLI tools on a Mac in one command.

## Quick start

```bash
# If you have this repo cloned locally (works whether repo is public or private):
brew tap bytesofpurpose/earlbear /path/to/homebrew-earlbear
brew install bytesofpurpose/earlbear/ebdeck
```

## Private repo access

The repo is currently private. Three ways to tap it:

**Option A — Local clone (recommended for team members)**

```bash
# Clone the repo once
git clone git@github.com:bytesofpurpose/homebrew-earlbear.git ~/homebrew-earlbear

# Tap from the local path — works without any GitHub auth
brew tap bytesofpurpose/earlbear ~/homebrew-earlbear
brew install bytesofpurpose/earlbear/ebdeck
```

To update formulas later:
```bash
cd ~/homebrew-earlbear && git pull
brew upgrade bytesofpurpose/earlbear/ebdeck
```

**Option B — SSH (requires SSH key with repo access)**

```bash
brew tap bytesofpurpose/earlbear git@github.com:bytesofpurpose/homebrew-earlbear.git
brew install bytesofpurpose/earlbear/ebdeck
```

**Option C — HTTPS with PAT (requires GitHub token with `repo` scope)**

```bash
# Set token in env or embed in URL (never commit the token)
HOMEBREW_GITHUB_API_TOKEN=ghp_... brew tap bytesofpurpose/earlbear \
  https://github.com/bytesofpurpose/homebrew-earlbear
brew install bytesofpurpose/earlbear/ebdeck
```

> If the repo is ever made public, `brew tap bytesofpurpose/earlbear https://github.com/bytesofpurpose/homebrew-earlbear` will work without any auth.

## Individual formulas

| Formula | Status | Purpose |
|---|---|---|
| `ebdeck` | ✓ validated | Deck generator (Python + Docker) |
| `ebjira` | ✓ validated | Jira CLI (Docker-wrapped) |
| `earlbear-plugins` | ✓ validated | Claude plugin bundle |
| `ebdocs` | in progress | Google Docs CLI |
| `ebshop` | in progress | Shopify CLI |
| `agent-cli` | in progress | Cloud agent admin |

```bash
brew install bytesofpurpose/earlbear/ebdeck
brew install bytesofpurpose/earlbear/ebjira
brew install bytesofpurpose/earlbear/earlbear-plugins
```

## Credentials

All CLIs read from `~/.config/earlbear/.env`. Copy the example to get started:

```bash
cp $(brew --prefix)/share/earlbear/.env.example ~/.config/earlbear/.env
# edit ~/.config/earlbear/.env with your credentials
```

## Recipe catalog

| Recipe | Location | Platform | Purpose |
|---|---|---|---|
| Homebrew formulas | `Formula/` | macOS | Install CLIs via `brew install` |
| Devcontainer | `devcontainer/` | Linux (Claude cowork) | Claude Code sandbox with EarlBear tooling |
| Validation | `validation/` | Docker / Tart VM | Regression test suite |

## Cowork devcontainer (Claude Code sandbox)

The `devcontainer/` directory provides a pre-built Linux environment with EarlBear tools installed, intended for use as a Claude Code cowork session.

**Requirements:** Apple Silicon, macOS 26+, [apple/container](https://github.com/apple/container/releases)

```bash
# 1. Install apple/container
#    Download the installer from https://github.com/apple/container/releases
#    Run the .pkg installer, then:
container system start

# 2. Build the cowork image (from repo root — takes ~10min first time)
container build -f devcontainer/Dockerfile -t earlbear-cowork:local .

# 3. Run a cowork session
container run --rm -it \
  --volume ~/.config/earlbear:/home/linuxbrew/.config/earlbear:ro \
  earlbear-cowork:local \
  bash

# 4. Or run the full regression test
make validate-cowork
```

Inside the container, `ebdeck` and `earlbear-plugins` are pre-installed. Credentials are mounted read-only from `~/.config/earlbear/.env` on your Mac.

## Development

```bash
# Sync latest source from sibling repos
make sync-sources

# Run validation suite
make validate-audit    # ~30s  — brew audit/style in Docker
make validate-docker   # ~5min — brew install in Docker (Linux x86_64)
make validate-smoke    # ~10s  — smoke test local installs
make validate-cowork   # ~10min — cowork devcontainer (Apple Silicon + macOS 26+)

# Release
make bump-and-release VERSION=1.0.1
```
