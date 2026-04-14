# Tart macOS VM Validation (Tier 3)

Full clean-room `brew install` test using a real macOS VM on Apple Silicon.
Tests **local source** (your uncommitted changes), not the published GitHub tag.

## One-time setup

```bash
# 1. Install tart
brew install cirruslabs/cli/tart

# 2. Install sshpass (for non-interactive SSH to VM)
brew install hudochenkov/sshpass/sshpass

# 3. Pull the base macOS image (~6GB, cached after first pull)
make tart-pull
```

## Run

```bash
make validate-vm
# or directly:
bash validation/tart/tart-test.sh
```

Takes ~15 minutes on Apple Silicon (VM boot ~1min, Homebrew install ~10min,
smoke tests ~30s).

## What it does

1. **Preflight** — assert `tart` + `sshpass` installed, Apple Silicon
2. **Clone** base macOS image into a temp VM (`earlbear-test-<timestamp>`)
3. **Start VM** in background (no graphics)
4. **Wait for SSH** — poll up to 120s for SSH to be ready (default creds: `admin`/`admin`)
5. **rsync local repo** into VM at `~/tap-src/` (excludes `.git/`, `dist/`, `*.pyc`, compiled binaries)
6. **In VM via SSH heredoc:**
   - `git init ~/tap-src` — brew tap requires git history
   - Build local tarball + patch formula URLs/sha256 (same awk pattern as `validation/docker/Dockerfile`)
   - `brew tap bytesofpurpose/earlbear ~/tap-src`
   - `brew install --build-from-source bytesofpurpose/earlbear/earlbear`
7. **Smoke tests** — pipe `validation/smoke/smoke-test.sh` over SSH
8. **Cleanup** — `tart stop` + `tart delete` (in EXIT trap)

## How local-source patching works

The formula `url` field points to the GitHub release tarball. To test locally,
the script:

1. Builds a tarball from `~/tap-src/` inside the VM
2. Computes its `sha256sum`
3. Patches each `Formula/*.rb` to use `file:///Users/admin/tap-v1.0.0.tar.gz` + the new sha256
4. Commits the patched formulas so `brew tap` is happy

This is identical to what `validation/docker/Dockerfile` does — the same awk
pattern that only patches the formula-level sha256 (not resource sha256s).

## Debugging

Keep the VM alive after the test to SSH in manually:

```bash
SKIP_DELETE=1 make validate-vm
# After test:
ssh -o StrictHostKeyChecking=no admin@$(tart ip earlbear-test-<timestamp>)
# Password: admin
# Cleanup when done:
tart delete earlbear-test-<timestamp>
```

List running VMs:
```bash
tart list
```

## Environment overrides

| Var | Default | Purpose |
|---|---|---|
| `TART_BASE_IMAGE` | `ghcr.io/cirruslabs/macos-sequoia-base:latest` | Override base macOS image |
| `SKIP_DELETE` | `0` | Keep VM alive after test for debugging |
