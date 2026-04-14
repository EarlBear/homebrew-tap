# Validation Infrastructure Requirements

Requirements and use cases for the EarlBear Homebrew tap validation system.
Captured from design decisions made during implementation.

---

## Core requirement

> Every formula change must be testable against **local source** before it reaches
> GitHub — not just against the last published tag.

This drives all tier design decisions. The Docker Tier 2 and Tart Tier 3 tests
both inject the local repo and patch formula URLs/sha256s for this reason.

---

## Use cases

### UC-1: Pre-commit formula validation
**Who:** Developer editing a formula or pyproject.toml resource list  
**Need:** Catch Ruby syntax errors, packaging bugs, or bad install paths before
committing — without pushing to GitHub first  
**Satisfied by:** Tier 1 (audit) + Tier 2 (Docker install)  
**Time budget:** < 5min for fast feedback

### UC-2: macOS clean-room regression
**Who:** Developer before cutting a release  
**Need:** Prove every formula installs and every CLI is callable on a fresh macOS
machine with no pre-existing tooling — the exact experience of a new user running
`brew install earlbear`  
**Satisfied by:** Tier 3 (Tart macOS VM)  
**Time budget:** ~15min acceptable, once before release  
**Requirement:** Tests **local source**, not the published tag

### UC-3: Local smoke test after brew install
**Who:** Developer after locally installing formulas  
**Need:** Quick sanity check that binaries are on PATH and respond correctly  
**Satisfied by:** Tier 4 (smoke-test.sh)  
**Time budget:** < 30s

### UC-4: Cowork devcontainer regression
**Who:** Developer after changing the devcontainer or earlbear-plugins formula  
**Need:** Prove the cowork devcontainer image builds and the Claude Code
environment inside it has the expected tools, paths, and env vars  
**Satisfied by:** Tier 5 (validate-cowork via apple/container)  
**Time budget:** ~10min

### UC-5: Cowork plugin binary compatibility
**Who:** Developer after building or updating a cowork plugin CLI binary  
**Need:** Prove the compiled binary runs in the cowork VM environment (Ubuntu 24.04
ARM64) without linker errors or missing shared libraries  
**Satisfied by:** Tier 5b (validate-plugin-binaries)  
**Time budget:** ~2min with SKIP_BUILD=1 (reuse existing binary)

### UC-6: Cowork plugin end-to-end simulation
**Who:** Developer before releasing a new plugin binary  
**Need:** Prove the full cowork plugin delivery path works: fresh brew install +
plugin shim resolves `.cowork-lib/shim.sh` + `cowork_require_token` exits 2
(CONFIG_MISSING) when no token injected  
**Satisfied by:** Tier 5c (validate-cowork-sim)  
**Time budget:** ~3min with SKIP_BREW=1 + SKIP_BUILD=1

### UC-7: Manual Claude Desktop integration test
**Who:** Developer doing a release or testing a new plugin  
**Need:** Prove the full Claude Desktop cowork plugin path: shim resolves, permission
card shows for destructive ops, OAuth token injection works  
**Satisfied by:** Tier 6 (manual — see docs/tier-6-cowork-vm-test.md)  
**Time budget:** ~10min, manual

---

## Performance requirements

| Tier | Max acceptable time | Why |
|---|---|---|
| 1 (audit) | 30s | Run on every save / pre-commit |
| 2 (Docker) | 5min | Run before every commit to a formula |
| 4 (smoke) | 30s | Run after every local brew install |
| 3 (Tart VM) | 15min | Run before every release |
| 5 (cowork devcontainer) | 10min | Run when devcontainer or earlbear-plugins changes |
| 5b (plugin binaries) | 2min (SKIP_BUILD=1) | Run after every binary build |
| 5c (cowork-sim) | 3min (SKIP_BREW=1 + SKIP_BUILD=1) | Run before every plugin release |

---

## Caching requirements

Long-running tiers must support incremental re-runs so developers don't pay
full setup cost on every iteration:

| Tier | What to cache | How |
|---|---|---|
| 3 (Tart VM) | macOS base image with Homebrew pre-installed | `make tart-build-base` → `earlbear-brew-base:local` image |
| 3 (Tart VM) | Base macOS image (~6GB OCI) | `make tart-pull` (one-time), pinned to sha256 digest |
| 5 (cowork devcontainer) | Devcontainer image | `SKIP_BUILD=1` reuses existing `earlbear-cowork-test:local` |
| 5c (cowork-sim) | Linuxbrew base image | `make cowork-sim-build-base` → `earlbear-cowork-base:local` |
| 5c (cowork-sim) | Sim image (brew install) | `SKIP_BREW=1` reuses existing `earlbear-cowork-sim:local` |
| 5b (plugin binaries) | Compiled binaries | `SKIP_BUILD=1` reuses binaries in `plugins-bundle/*/bin/` |

**Tart VM caching rationale:**  
`tart clone` is fast (~5s) but the Homebrew install step inside the VM takes ~5min.
A pre-baked `earlbear-brew-base:local` image with Homebrew installed saves this
time on every `make validate-vm` run. The base only needs rebuilding when the
pinned macOS image digest is upgraded.

**Dockerfile layer caching rationale:**  
Linuxbrew install is slow (~2min) and never changes. Splitting the cowork-sim
Dockerfile into `earlbear-cowork-base:local` (linuxbrew only) + `earlbear-cowork-sim:local`
(tap + brew install) means `SKIP_BREW=1` is effectively always fast once the base
is built.

---

## Local source requirement (detail)

All tiers that run `brew install` must test **local source**, not the published
GitHub tag. This is implemented by:

1. Copying the repo into the test environment (Docker COPY, rsync over SSH)
2. `git init` the copy (brew tap requires git history)
3. Building a local tarball: `tar -czf tap-v1.0.0.tar.gz ...`
4. Computing `sha256sum` of the tarball
5. Patching each `Formula/*.rb`:
   - Replace GitHub URL with `file:///path/to/tap-v1.0.0.tar.gz`
   - Replace formula-level `sha256` with computed hash
   - **Do NOT** touch resource sha256s (PyPI package hashes)
6. `git commit` the patched formulas
7. `brew tap earlbear/tap /path/to/tap`

The awk pattern used for step 5 is identical across all tiers:
```awk
/url "file:\/\/\/.*.tar.gz"/{found=1}
found && /^  sha256 "[0-9a-f]{64}"/{sub(/"[0-9a-f]{64}"/, "\"" sha "\""); found=0}
{print}
```

---

## Exit code convention

All test scripts follow the same convention for exit codes:

| Exit code | Meaning | Counts as |
|---|---|---|
| 0 | Success | Pass |
| 2 | CONFIG_MISSING (no credentials, no `.env`) | Pass — expected in test env |
| 1 | Unexpected error | Fail |
| other | Unexpected error | Fail |

This convention matches the EarlBear CLI contract: all CLIs exit 2 when
credentials are missing (not 1), so smoke tests can distinguish "no credentials"
(expected) from "binary crashed" (unexpected).
