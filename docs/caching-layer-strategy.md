# Caching & Layer Strategy

How the EarlBear validation infrastructure avoids slow re-setup on every run.
Applies to Tier 3 (Tart macOS VM) and Tier 5c (cowork-sim container).

---

## The problem

Two tiers have slow, unchanging setup steps:

| Tier | Slow step | Time | Changes when |
|---|---|---|---|
| 3 (Tart VM) | Install Homebrew into macOS VM | ~5min | Never (until macOS image upgrades) |
| 5c (cowork-sim) | Install Homebrew (linuxbrew) into ubuntu container | ~2min | Never (until apt deps or Homebrew version changes) |

Running these steps on every test iteration wastes time and defeats fast feedback.

---

## The solution: stable base + fast sim layer

Each tier is split into two layers:

```
Base layer   ← slow, stable, built once
Sim layer    ← fast, rebuilt when formulas change
```

The base is never rebuilt unless its specific inputs change. The sim layer
rebuilds in ~1-2min when formulas or tap configuration changes.

---

## Tier 3: Tart macOS VM snapshot

### What exists

| Artifact | Name | What's in it |
|---|---|---|
| Raw base image | `ghcr.io/cirruslabs/macos-sequoia-base@sha256:2344190...` | Clean macOS (no Homebrew) — 6GB OCI image, pulled once |
| Brew snapshot | `earlbear-brew-base` (local tart VM) | Raw base + Homebrew installed |
| Test VM | `earlbear-test-<timestamp>` | Brew snapshot + local tap patched + earlbear installed (ephemeral) |

### How it works

```
make tart-pull           # one-time: pull 6GB OCI base image → local tart cache
make tart-build-base     # one-time: clone base → boot VM → install Homebrew → tart rename → earlbear-brew-base
make validate-vm         # every run: clone earlbear-brew-base → rsync tap → patch → brew install → smoke tests → delete VM
```

`tart clone` from a local image takes ~5s. The test VM is always deleted on exit
(cleanup trap). The snapshot is permanent until you delete it or run `tart-build-base` again.

### What gets rebuilt when

| Change | Action needed |
|---|---|
| Formula `*.rb` changed | Just run `make validate-vm` — rsync + patch runs fresh every time |
| Pinned `BASE_IMAGE` sha256 digest upgraded | `make tart-pull` → `make tart-build-base` (rebuilds snapshot from new base) |
| Homebrew itself is broken/corrupted in snapshot | `make tart-build-base` (rebuilds snapshot) |

### Escape hatches

```bash
USE_BASE_SNAPSHOT=0 make validate-vm   # ignore snapshot, clone from raw base (~10min extra)
SKIP_DELETE=1 make validate-vm         # keep test VM alive after test for debugging
```

### Disk usage

| Artifact | Size | Lives at |
|---|---|---|
| Raw OCI base image | ~6GB | `~/.tart/cache/` |
| `earlbear-brew-base` snapshot | ~28GB | `~/.tart/vms/earlbear-brew-base/` |
| Test VM (ephemeral) | ~28GB | `~/.tart/vms/earlbear-test-*/` — deleted on exit |

Total committed disk: ~34GB. The test VM is ephemeral — it's only allocated during
the ~7min test window and deleted when done.

---

## Tier 5c: cowork-sim container layers

### What exists

| Image | Tag | What's in it |
|---|---|---|
| Ubuntu base | `ubuntu:24.04` | Pulled automatically by container runtime |
| Linuxbrew base | `earlbear-cowork-base:local` | ubuntu + apt deps + Homebrew (linuxbrew) |
| Sim image | `earlbear-cowork-sim:local` | Linuxbrew base + local tap patched + brew install ebdeck + earlbear-plugins |

### How it works

```
make cowork-sim-build-base    # one-time: build earlbear-cowork-base:local (~2min)
make validate-cowork-sim      # every run: build sim layer on top of base (~1-2min) → run tests
SKIP_BREW=1 make validate-cowork-sim  # skip sim rebuild entirely, reuse existing image (~30s)
```

The sim layer (`Dockerfile`) uses `FROM earlbear-cowork-base:local` so the ~2min
linuxbrew install is never repeated. Only the tap + brew install steps run on rebuild.

### What gets rebuilt when

| Change | Action needed |
|---|---|
| Formula `*.rb` changed | Run `make validate-cowork-sim` (rebuilds sim layer, ~1-2min) |
| `Dockerfile.base` changed (apt deps, Homebrew version) | `make cowork-sim-build-base` → `make validate-cowork-sim` |
| No formula change, just re-running tests | `SKIP_BREW=1 make validate-cowork-sim` (~30s) |

### The shim heredoc

`validation/cowork-sim/.cowork-lib/shim.sh` is **generated at test runtime** from
a heredoc in `cowork-sim-test.sh`. The file is gitignored. To change the shim
contract, edit the heredoc in `cowork-sim-test.sh` — not the generated file.

### Escape hatches

```bash
SKIP_BREW=1 make validate-cowork-sim    # reuse existing sim image, skip rebuild
SKIP_BUILD=1 make validate-cowork-sim   # also skip PyInstaller binary compile
```

---

## Build cache vs. stored images

The `apple/container` runtime uses a **buildkit** container to cache intermediate
build layers. This is separate from the final stored images:

```
buildkit container  ← intermediate layer cache, grows to 20-30GB over time, disposable
stored images       ← earlbear-cowork-base:local, earlbear-cowork-sim:local (these persist)
```

`make clean-container-cache` stops and removes the buildkit container, freeing 20-30GB.
The stored images are **not affected** — `SKIP_BREW=1` still works after cleanup.

The next build after cleanup re-creates buildkit fresh and may take a few extra minutes
to warm layer cache, but nothing is re-downloaded.

```bash
make clean-container-cache   # free 20-30GB of build cache; safe to run any time
container system df          # check current disk usage breakdown
```

---

## Summary: what to run after a fresh clone

```bash
# One-time setup — build the slow bases
brew install gitleaks                # for pre-commit secrets scan
make install-hooks                   # install pre-commit hook
make cowork-sim-build-base           # linuxbrew base for Tier 5c (~2min)
make tart-pull                       # pull macOS base OCI image (~6GB, once)
make tart-build-base                 # Homebrew VM snapshot for Tier 3 (~10min)

# Normal iteration loop
make validate-audit                  # Tier 1: ~30s
make validate-docker                 # Tier 2: ~5min
SKIP_BREW=1 make validate-cowork-sim # Tier 5c: ~30s (reuse existing image)
make validate-vm                     # Tier 3: ~7min (uses snapshot)
```

---

## Upgrading pinned images

### Tart macOS base image

```bash
make tart-pull
# Check new digest:
tart list
# Update BASE_IMAGE sha256 digest in:
#   validation/tart/tart-test.sh
#   validation/tart/tart-build-base.sh
# Rebuild snapshot:
make tart-build-base
```

Both `tart-test.sh` and `tart-build-base.sh` must pin the **same digest** — if they
diverge, the snapshot was built from a different base than the test uses.

### Linuxbrew base image

No pinned digest — `ubuntu:24.04` is pulled by the container runtime. To upgrade:
```bash
container image rm earlbear-cowork-base:local
make cowork-sim-build-base
```
