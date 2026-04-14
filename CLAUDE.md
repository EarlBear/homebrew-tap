# earlbear-homebrew

EarlBear Homebrew tap — Mac installer for all EarlBear CLI tooling.

## Recipe catalog

| Recipe type | Directory | Platform | Purpose |
|---|---|---|---|
| Homebrew formulas | `Formula/` | macOS (dev laptop) | Install CLIs via `brew install` |
| CLI source (synced) | `src/` | — | Copied from sibling repos by `make sync-sources` |
| Wrapper scripts | `wrappers/` | macOS | Homebrew-specific Docker wrappers (not in source repos) |
| Devcontainer | `devcontainer/` | Linux ARM64 (Claude cowork) | Claude Code sandbox with EarlBear tooling — tested by Tier 5 |
| Validation | `validation/` | Docker / Tart VM / apple/container | Regression test suite (5 tiers) |

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
make validate-cowork   # Tier 5: cowork devcontainer via apple/container (~10min, Apple Silicon + macOS 26+)

# 4. Build cowork plugin binaries (cross-compile CLIs for the cowork VM)
make build-plugin-binaries          # all CLIs, both arches (~20min, requires Docker)
make build-plugin-ebjira            # single CLI
SKIP_ARM=1 make build-plugin-ebjira # x86_64 only (faster on Intel CI)

# 5. Validate plugin binaries run in the cowork VM environment
make validate-plugin-binaries       # compile ebjira + run in ubuntu:24.04 ARM64 (~8min)
SKIP_BUILD=1 make validate-plugin-binaries  # re-run against existing binary (~1min)

# 6. Release (tag + GitHub Release + upload plugin binaries as assets)
make bump-and-release VERSION=1.0.1
make release-plugin-binaries        # upload binaries to an existing tag's release

# Plugin binaries are stored in Git LFS.
# After cloning: git lfs pull   (hydrates binaries from LFS storage)
# Verify LFS status: make lfs-status
```

## Validation tiers

| Tier | Target | Time | What it catches |
|---|---|---|---|
| 1 | `make validate-audit` | ~30s | Ruby syntax, Homebrew policy violations |
| 2 | `make validate-docker` | ~5min | Packaging bugs, bad install paths (Linux x86_64) |
| 3 | `make validate-vm` | ~15min | Full clean-room install on real macOS (Apple Silicon) |
| 4 | `make validate-smoke` | ~10s | Binaries callable, exit codes correct |
| 5 | `make validate-cowork` | ~10min | Cowork devcontainer: install paths, runtime env (Apple Silicon + macOS 26+) |
| 5b | `make validate-plugin-binaries` | ~8min | Compile ebjira via PyInstaller → run in ubuntu:24.04 ARM64 → assert `--help` exits cleanly (Apple Silicon + Docker + apple/container) |

## Skills

Five skills cover the common tap operations. Invoke with `/skill-name`.

| Skill | Description |
|---|---|
| `/add-formula` | Scaffold a new formula (Docker-wrapped, Python venv, or script). Includes templates, PyPI resource lookup steps, and gotchas from ebdeck. |
| `/release` | Full release flow: sync sources → validate → tag → push → patch sha256. |
| `/sync` | Sync `src/` from sibling repos, report what changed, run audit tier. |
| `/inspect-claude-internals` | Inspect a macOS Electron app (Claude Desktop or similar) to discover VM/container architecture, MCP tools, and plugin binary layout. Writes findings to `docs/<app>-internals.md`. |
| `/make-cowork-plugin` | Convert an EarlBear Claude plugin to work inside the Claude Desktop cowork VM. Covers binary packaging (PyInstaller), the cowork shim pattern, confirm rules, credential injection, and `make build-plugin-*` targets. |

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

`wrappers/` contains Homebrew-specific wrapper scripts that are NOT in the source repos.
Edit wrapper scripts directly in `wrappers/{cli}/wrapper.sh` — these are version-controlled here.
The formula `install` block copies both `src/{cli}/*` (Dockerfile + source) and `wrappers/{cli}/wrapper.sh`.
