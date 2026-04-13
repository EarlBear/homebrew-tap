# earlbear-homebrew

EarlBear Homebrew tap — Mac installer for all EarlBear CLI tooling.

## Recipe catalog

| Recipe type | Directory | Platform | Purpose |
|---|---|---|---|
| Homebrew formulas | `Formula/` | macOS (dev laptop) | Install CLIs via `brew install` |
| Devcontainer | `devcontainer/` | Linux (Claude cowork) | Claude Code sandbox with EarlBear tooling |
| Validation | `validation/` | Docker / Tart VM | Regression test suite |

## Formulas

| Formula | Mechanism | Notes |
|---|---|---|
| `ebjira` | Docker image + wrapper | Requires Docker for Mac |
| `ebdocs` | Docker image + wrapper | Requires Docker for Mac |
| `ebshop` | Docker image + wrapper | Requires Docker for Mac |
| `ebdeck` | Python venv (`Language::Python::Virtualenv`) | `python@3.11` dep |
| `agent-cli` | Bash script | Depends on `ebjira` formula |
| `earlbear-plugins` | Shell script | Requires `claude` CLI on PATH |
| `earlbear` | Meta (all deps) | One-liner setup entry point |

## Credentials convention

All CLIs read from `~/.config/earlbear/.env`. Override with `EARLBEAR_CONFIG_DIR`.

## Development workflow

```bash
# 1. Sync latest source from sibling repos
make sync-sources

# 2. Edit Formula/*.rb or src/*/wrapper.sh

# 3. Validate
make validate-audit    # Tier 1: brew audit/style in Docker (~30s)
make validate-docker   # Tier 2: brew install in Docker (~5min)
make validate-smoke    # Tier 4: smoke test local install (~10s)
make validate-vm       # Tier 3: Tart macOS VM — full clean-room (~15min)

# 4. Release
make bump-and-release VERSION=1.0.1
```

## Validation tiers

| Tier | Target | Time | What it catches |
|---|---|---|---|
| 1 | `make validate-audit` | ~30s | Ruby syntax, Homebrew policy violations |
| 2 | `make validate-docker` | ~5min | Packaging bugs, bad install paths |
| 3 | `make validate-vm` | ~15min | Full clean-room install on real macOS |
| 4 | `make validate-smoke` | ~10s | Binaries callable, exit codes correct |

## Secrets strategy

See plan: `.claude/plans/homebrew-tap-setup.md` § Secrets strategy.
Current recommendation: static `~/.config/earlbear/.env` (Option D).
Migrate to 1Password CLI (Option A) when team grows to ≥2 developers.

## Source sync

`src/` is populated by `make sync-sources` from sibling repos:
- `src/ebjira/` ← `../earlbear-clis/jira-cli/`
- `src/ebdocs/` ← `../earlbear-clis/gdocs-cli/`
- `src/ebshop/` ← `../earlbear-clis/shopify-cli/`
- `src/ebdeck/` ← `../earlbear-clis/deck-cli/`
- `src/agent-cli/` ← `../earlbear/bin/agent-cli`
- `plugins-bundle/` ← `../earlbear-claude-plugin-marketplace/plugins/`

Do not hand-edit files in `src/` — edit source in the respective repos and re-sync.
