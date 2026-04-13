# homebrew-earlbear

EarlBear Homebrew tap — install all EarlBear CLI tools on a Mac in one command.

## Quick start

```bash
brew tap bytesofpurpose/earlbear https://github.com/bytesofpurpose/homebrew-earlbear
brew install bytesofpurpose/earlbear/ebdeck
```

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

## Development

```bash
# Sync latest source from sibling repos
make sync-sources

# Run validation suite
make validate-audit    # ~30s  — brew audit/style in Docker
make validate-docker   # ~5min — brew install in Docker
make validate-smoke    # ~10s  — smoke test local installs

# Release
make bump-and-release
```
