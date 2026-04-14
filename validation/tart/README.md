# Tart macOS VM Validation (Tier 3)

Full clean-room `brew install` test using a real macOS VM on Apple Silicon.
Tests **local source** (your uncommitted changes), not the published GitHub tag.

## One-time setup

```bash
# 1. Install tart
brew install cirruslabs/cli/tart

# 2. Install sshpass (for non-interactive SSH to VM)
brew install hudochenkov/sshpass/sshpass

# 3. Pull the base macOS image (~6GB, cached locally after this — never re-downloaded)
make tart-pull

# 4. (Optional but recommended) Build the Homebrew snapshot — saves ~5min per validate-vm run
make tart-build-base
```

## Image caching — no re-download per run

`tart clone` copies from the **local cached image** (~5s). The ~6GB download only
happens once via `make tart-pull`. Subsequent `make validate-vm` runs clone from
the local cache.

The script pins to a specific image digest so it never pulls unexpectedly:
```
ghcr.io/cirruslabs/macos-sequoia-base@sha256:2344190...
```

To upgrade the pinned image:
```bash
make tart-pull          # pulls latest (~6GB if changed)
tart list               # find the new sha256 digest
# Update BASE_IMAGE digest in validation/tart/tart-test.sh AND tart-build-base.sh
```

## Homebrew snapshot — skip the ~5min brew install

`make tart-build-base` creates `earlbear-brew-base:local` — a VM snapshot with
Homebrew pre-installed. When this snapshot exists, `make validate-vm` clones from
it instead of the raw base image, skipping the Homebrew install step:

```
Without snapshot:  VM boot ~1min + Homebrew install ~5min + tap+install ~5min + tests ~30s = ~12min
With snapshot:     VM boot ~1min + tap+install ~5min + tests ~30s = ~7min
```

Rebuild the snapshot when you upgrade the pinned `BASE_IMAGE` digest.

```bash
make tart-build-base           # (~10min, once)
make validate-vm               # now uses snapshot automatically
USE_BASE_SNAPSHOT=0 make validate-vm  # bypass snapshot (raw base)
```

## Run

```bash
make validate-vm
# or directly:
bash validation/tart/tart-test.sh
```

Takes ~12 minutes with the Homebrew snapshot, ~15 minutes from scratch.

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
