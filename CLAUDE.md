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
| `earlbear-plugins` | Shell script | Installs the plugins from the GitHub marketplace; needs `claude` on PATH and GitHub access to EarlBear |
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
make validate-wrappers # Tier 0: the Docker wrappers' own logic, offline (seconds)
make validate-audit    # Tier 1: brew audit/style in Docker (~30s)
make validate-docker   # Tier 2: brew install in Docker (~5min)
make validate-smoke    # Tier 4: every installed command answers --help with its own name (~1min; longer on first run while Docker images build)
make validate-vm       # Tier 3: Tart macOS VM — clean-room from local source (~15min, ~10min with snapshot)
                       #   prereqs (one-time): brew install cirruslabs/cli/tart
                       #                       brew install hudochenkov/sshpass/sshpass
                       #                       make tart-pull       (~6GB image download)
                       #   optional speedup:   make tart-build-base (~10min once, saves ~5min per run)
make tart-build-base   # Build Homebrew-pre-installed VM snapshot (one-time; speeds up validate-vm by ~5min)
make validate-cowork       # Tier 5: cowork devcontainer via apple/container (~10min, Apple Silicon + macOS 26+)
make cowork-sim-build-base # Build linuxbrew base image for cowork-sim (~2min one-time; speeds up rebuilds)
make validate-cowork-sim   # Tier 5c: fresh brew + plugin shims in ubuntu:24.04 ARM64 (~10min, SKIP_BREW=1: ~2min)

# 4. Build cowork plugin wheels (pure-Python — no cross-compilation, no GLIBC issues)
make build-plugin-wheels            # all CLIs (~2min, requires Docker for clean build env)
make build-plugin-ebjira            # single CLI wheel bundle
# Output: cowork-payload/<plugin>/wheels/<cli>-bundle.zip

# 5. Validate plugin wheels run in the cowork VM environment
make validate-plugin-wheels         # build wheels + run in ubuntu:24.04 ARM64 (~5min)
SKIP_BUILD=1 make validate-plugin-wheels  # re-run against existing wheels (~1min)

# 6. Release (tag + GitHub Release + upload plugin wheels as assets)
make bump-and-release VERSION=1.0.1
make release-plugin-wheels          # upload wheels to an existing tag's release

# Wheel bundles (<cli>-bundle.zip) are committed next to the cowork shims, in Git LFS
# (see .gitattributes). Some are tens of MB with their dependencies.
```

## Validation tiers

| Tier | Target | Time | What it catches |
|---|---|---|---|
| 0 | `make validate-wrappers` | seconds | The Docker wrappers' own logic (which Jira settings reach the ebjira container), with stand-in `brew` and `docker` |
| 1 | `make validate-audit` | ~30s | Ruby syntax, Homebrew policy violations |
| 2 | `make validate-docker` | ~5min | Packaging bugs, bad install paths (Linux x86_64) |
| 3 | `make validate-vm` | ~15min (~10min with snapshot) | Full clean-room install on real macOS from **local source** (rsync + sha256 patch, Apple Silicon; prereqs: `tart` + `sshpass` + `make tart-pull`; optional speedup: `make tart-build-base`) |
| 4 | `make validate-smoke` | ~1min (first run longer: Docker images build) | Every command each formula installs answers `--help` with exit 0 and its own name (no settings, no Keychain) |
| 5 | `make validate-cowork` | ~10min | Cowork devcontainer: install paths, runtime env (Apple Silicon + macOS 26+) |
| 5b | `make validate-plugin-wheels` | ~5min (SKIP_BUILD=1: ~1min) | Build pure-Python wheel bundles for all 4 CLIs → pip-install in ubuntu:24.04 ARM64 → assert `--help` exits cleanly. Single CLI: `CLI=ebjira make validate-plugin-wheels`. (Apple Silicon + Docker + apple/container) |
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

Wheel bundles (`cowork-payload/**/wheels/*-bundle.zip`) and the old compiled
binaries (`cowork-payload/**/bin/*-linux`) are stored in **Git LFS**. The wheel
rule is in `.gitattributes`. Never commit raw binaries to git objects.

- Verify before staging: `git lfs status` — LFS-tracked files show `(LFS: ...)`, not raw size.
- New binary file types must be added to `.gitattributes` before first commit.
- Generated scratch files (e.g. `validation/cowork-sim/.cowork-lib/`) are
  gitignored — never commit files that are regenerated at test runtime.

**`brew tap` + git-lfs gotcha:** `brew tap` sanitizes its subprocess env, so
`GIT_LFS_SKIP_SMUDGE` and `GIT_CONFIG_PARAMETERS` are ignored. If `filter.lfs.required=true`
is in the global gitconfig and `git-lfs` is not on brew's internal PATH, the tap clone fails
hard. See `earlbear-apps/docs/known-issues.md` for the full workaround used in `install.sh`.

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
- `src/ebtranscripts/` ← `../earlbear-clis/transcripts-cli/`
- `src/agent-cli/agent-cli.sh` ← `../earlbear-claude-agent/bin/agent-cli`

The Claude plugins are **not** copied here. The `earlbear-plugins` formula installs only
`scripts/install-plugins.sh`, which adds the private GitHub marketplace
`EarlBear/marketplace-claude-plugins` and installs every plugin its
`.claude-plugin/marketplace.json` lists, so the script needs no edit when a plugin is added or
removed. The formula has no post_install (Homebrew's sandbox blocks `~/.claude` and GitHub keys
there), so a person runs the script after `brew install`, as the caveats say.

`cowork-payload/<plugin>/` holds what the Claude Desktop cowork VM needs and the marketplace
does not ship: the `bin/<cli>` shims, the old `*-linux` builds, and the
`wheels/<cli>-bundle.zip` files that `make build-plugin-wheels` writes. It is not a Claude
plugin folder (there is no `plugin.json`); the plugins themselves come from the marketplace.

Do not hand-edit files in `src/` — edit source in the respective repos and re-sync.

`wrappers/` contains Homebrew-specific wrapper scripts that are NOT in the source repos.
Edit wrapper scripts directly in `wrappers/{cli}/wrapper.sh` — these are version-controlled here.
The formula `install` block copies both `src/{cli}/*` (Dockerfile + source) and `wrappers/{cli}/wrapper.sh`.
