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

## Casks

| Cask | Source repo | Notes |
|---|---|---|
| `earlbear-installer` | `EarlBear/apps` (private) | One-click setup wizard; DMG released from that repo |

To update the cask after a new installer release: see `/release` skill Path B, or run:
```bash
# Download new DMG, compute sha256, patch Casks/earlbear-installer.rb
curl -sL https://github.com/EarlBear/apps/releases/download/installer-vX.Y.Z/EarlBear-Installer-X.Y.Z.dmg \
  -o /tmp/installer.dmg && shasum -a 256 /tmp/installer.dmg
# Then edit Casks/earlbear-installer.rb: version + sha256
```

## Credentials convention

All CLIs read from `~/.config/earlbear/.env`. Override with `EARLBEAR_CONFIG_DIR`.

## Development workflow

```bash
# 0. One-time repo setup (after cloning)
make install-hooks           # install pre-commit: gitleaks secrets scan + large-file guard
brew install gitleaks        # required by the pre-commit hook

# 1. Sync latest source from sibling repos
make sync-sources

# 2. Edit Formula/*.rb or src/*/wrapper.sh

# 3. Validate
make validate-audit    # Tier 1: brew audit/style in Docker (~30s)
make validate-docker   # Tier 2: brew install in Docker (~5min)
make validate-smoke    # Tier 4: smoke test local install (~10s)
make validate-vm       # Tier 3: Tart macOS VM — clean-room from local source (~15min, ~10min with snapshot)
                       #   prereqs (one-time): brew install cirruslabs/cli/tart
                       #                       brew install hudochenkov/sshpass/sshpass
                       #                       make tart-pull       (~6GB image download)
                       #   optional speedup:   make tart-build-base (~10min once, saves ~5min per run)
make tart-build-base   # Build Homebrew-pre-installed VM snapshot (one-time; speeds up validate-vm by ~5min)
make validate-cowork       # Tier 5: cowork devcontainer via apple/container (~10min, Apple Silicon + macOS 26+)
make cowork-sim-build-base # Build linuxbrew base image for cowork-sim (~2min one-time; speeds up rebuilds)
make validate-cowork-sim   # Tier 5c: fresh brew + plugin shims in ubuntu:24.04 ARM64 (~10min, SKIP_BREW=1: ~2min)

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
| 3 | `make validate-vm` | ~15min (~10min with snapshot) | Full clean-room install on real macOS from **local source** (rsync + sha256 patch, Apple Silicon; prereqs: `tart` + `sshpass` + `make tart-pull`; optional speedup: `make tart-build-base`) |
| 4 | `make validate-smoke` | ~10s | Binaries callable, exit codes correct |
| 5 | `make validate-cowork` | ~10min | Cowork devcontainer: install paths, runtime env (Apple Silicon + macOS 26+) |
| 5b | `make validate-plugin-binaries` | ~20min (SKIP_BUILD=1: ~2min) | Compile all 4 CLIs via PyInstaller → run each in ubuntu:24.04 ARM64 → assert `--help` exits cleanly. Single CLI: `CLI=ebjira make validate-plugin-binaries`. (Apple Silicon + Docker + apple/container) |
| 5c | `make validate-cowork-sim` | ~10min (SKIP_BREW=1: ~3min) | Fresh ubuntu:24.04 + linuxbrew install + tap earlbear + brew install ebdeck → mount plugin dirs → run cowork shims → assert exits 2 (CONFIG_MISSING). Closest automated simulation of cowork plugin delivery. (Apple Silicon + apple/container) |

## Skills

Five skills cover the common tap operations. Invoke with `/skill-name`.

| Skill | Description |
|---|---|
| `/add-formula` | Scaffold a new formula (Docker-wrapped, Python venv, or script). Includes templates, PyPI resource lookup steps, and gotchas from ebdeck. |
| `/release` | Full release flow: sync sources → validate → tag → push → patch sha256. |
| `/sync` | Sync `src/` from sibling repos, report what changed, run audit tier. |
| `/inspect-claude-internals` | Inspect a macOS Electron app (Claude Desktop or similar) to discover VM/container architecture, MCP tools, and plugin binary layout. Writes findings to `docs/<app>-internals.md`. |
| `/make-cowork-plugin` | Convert an EarlBear Claude plugin to work inside the Claude Desktop cowork VM. Covers binary packaging (PyInstaller), the cowork shim pattern, confirm rules, credential injection, and `make build-plugin-*` targets. |
| `/add-cli` | End-to-end guide for adding a new Python CLI: source sync, formula, cowork plugin, Makefile targets, all validation tiers, and release wiring in one pass. |

## Repo tenets

### No large files in git objects

Compiled binaries (`plugins-bundle/**/bin/*-linux`) are stored in **Git LFS**,
tracked via `.gitattributes`. Never commit raw binaries to git objects.

- Verify before staging: `git lfs status` — LFS-tracked files show `(LFS: ...)`, not raw size.
- New binary file types must be added to `.gitattributes` before first commit.
- Generated scratch files (e.g. `validation/cowork-sim/.cowork-lib/`) are
  gitignored — never commit files that are regenerated at test runtime.

### Cache slow setup; isolate what changes

Long-running tiers split into a stable **base** + a fast **sim** layer:

| Base | What's in it | Rebuilt when |
|---|---|---|
| `earlbear-brew-base:local` (Tart VM) | macOS base + Homebrew installed | Pinned `BASE_IMAGE` digest changes |
| `earlbear-cowork-base:local` (container) | ubuntu:24.04 + linuxbrew | apt deps or Homebrew version changes |
| `earlbear-cowork-sim:local` (container) | base + tap + brew install | Formula changes |

The sim/test layer is always rebuilt when formulas change; bases are never rebuilt
unless their specific inputs change. `SKIP_BREW=1` / `USE_BASE_SNAPSHOT=0` provide
escape hatches when you need to override caching.

### Common setup — build the bases first

After a fresh clone or after upgrading a pinned image:
```bash
make cowork-sim-build-base   # linuxbrew base for Tier 5c (~2min, one-time)
make tart-build-base         # Homebrew VM snapshot for Tier 3 (~10min, one-time)
```

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
