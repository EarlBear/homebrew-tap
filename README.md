# homebrew-earlbear

EarlBear Homebrew tap — install all EarlBear CLI tools on a Mac in one command.

## Quick start

```bash
brew tap bytesofpurpose/earlbear https://github.com/bytesofpurpose/homebrew-earlbear
brew install earlbear      # installs everything
earlbear-setup             # configure credentials
```

## Individual formulas

```bash
brew install bytesofpurpose/earlbear/ebjira    # Jira CLI
brew install bytesofpurpose/earlbear/ebdocs    # Google Docs CLI
brew install bytesofpurpose/earlbear/ebshop    # Shopify CLI
brew install bytesofpurpose/earlbear/ebdeck    # Deck generator
brew install bytesofpurpose/earlbear/agent-cli # Cloud agent admin
brew install bytesofpurpose/earlbear/earlbear-plugins  # Claude plugins
```

## Credentials

All CLIs read from `~/.config/earlbear/.env`. Run `earlbear-setup` to configure,
or copy `.env.example` manually:

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
