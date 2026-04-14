# Plan: Tart macOS Clean-Room Validation (Tier 3)

## Context

`make validate-vm` (Tier 3) exists as a skeleton but is not usable for pre-release
validation because it taps from the public GitHub repo rather than local source.
This means uncommitted formula changes are invisible to the test — defeating the
purpose of a clean-room regression check.

The Docker Tier 2 test already solves this for Linux: it copies the repo into the
image, initialises a local git repo, builds a tarball, patches formula URLs/sha256,
then `brew tap` from that local path. The Tart test needs the same local-source
approach, adapted for macOS.

**Key constraint:** Getting local files into a Tart VM has two viable options:
- `--dir` mount (Virtio FS): instant, zero-copy, but can trigger macOS security
  prompts in automated pipelines on some image builds
- SSH + rsync: reliable, no security prompts, ~5-10s for a 50MB repo

The `ghcr.io/cirruslabs/macos-sequoia-base` image uses `admin`/`admin` credentials
and SSH is enabled by default. `tart ip <vm>` returns the IP. This is the safer
choice for an unattended test.

---

## What Changes

### 1. Rewrite `validation/tart/tart-test.sh`

Replace the current skeleton with a fully working script:

**Flow:**
1. Preflight: assert `tart` is installed, assert Apple Silicon
2. Clone base image → temp VM name (same as today)
3. `tart run --no-graphics` in background (same as today)
4. Wait for VM boot + SSH ready (poll `ssh ... exit 0` up to 60s)
5. **rsync local repo into VM** via SSH:
   ```bash
   rsync -az --exclude='.git' --exclude='src/*/dist' --exclude='*.pyc' \
     -e "ssh -o StrictHostKeyChecking=no -o PasswordAuthentication=yes" \
     "$REPO_ROOT/" admin@$VM_IP:~/tap-src/
   ```
   Uses `sshpass -p admin` for non-interactive password auth.
6. In VM via SSH heredoc:
   - `cd ~/tap-src && git init && git add -A && git commit -m "tap snapshot"`
   - Build local tarball + patch formula URLs/sha256 (same awk pattern as Docker Tier 2)
   - `brew tap bytesofpurpose/earlbear ~/tap-src`
   - `brew install --build-from-source bytesofpurpose/earlbear/earlbear`
7. Run smoke tests in VM (pipe `validation/smoke/smoke-test.sh` over SSH)
8. Cleanup: `tart delete $VM_NAME` (in EXIT trap)

**New env vars / overrides:**
| Var | Default | Purpose |
|---|---|---|
| `TART_BASE_IMAGE` | `ghcr.io/cirruslabs/macos-sequoia-base:latest` | Override base image |
| `SKIP_DELETE` | `0` | Set to `1` to keep VM alive after test (debugging) |

### 2. Add `make tart-pull` target

One-time setup: pull the ~6GB base image and print disk usage.

```makefile
tart-pull: ## Pull the Tart macOS base image (~6GB, one-time setup)
    tart pull ghcr.io/cirruslabs/macos-sequoia-base:latest
    @echo "✓ Base image pulled. Run 'make validate-vm' to use it."
```

### 3. Add `sshpass` preflight check

`sshpass` is needed for non-interactive SSH password auth. The script checks for
it and prints install instructions if missing:

```bash
command -v sshpass >/dev/null || {
    echo "sshpass not found. Install: brew install hudochenkov/sshpass/sshpass"
    exit 1
}
```

### 4. Update `validation/tart/README.md`

Add:
- One-time setup section: `brew install cirruslabs/cli/tart`, `brew install hudochenkov/sshpass/sshpass`, `make tart-pull`
- How local-source patching works (same as Docker Tier 2)
- `SKIP_DELETE=1` usage for debugging

### 5. Update `CLAUDE.md`

- Add `make tart-pull` to the one-time setup section
- Update Tier 3 description to note it tests local source (not GitHub)
- Add `sshpass` to prerequisites

### 6. Update `living-artifacts.yaml`

The existing `validation/tart/**` trigger already fires when tart-test.sh changes.
No new trigger needed — just verify the existing reminder still makes sense after
the rewrite.

---

## Critical Files

| File | Action |
|---|---|
| `validation/tart/tart-test.sh` | Full rewrite — local rsync + sha256 patch + SSH smoke test |
| `validation/tart/README.md` | Add one-time setup, local-source explanation, SKIP_DELETE |
| `Makefile` | Add `tart-pull` target; update `.PHONY` |
| `CLAUDE.md` | Add `tart-pull` to setup, update Tier 3 description |

All files are in `/Users/omareid/Workspace/git/earlbear-homebrew/`.

---

## Key design decisions

**Why rsync over SSH instead of `--dir` mount?**
The `--dir` Virtio FS mount can trigger macOS "network volume" security prompts in
automated pipelines. SSH+rsync is more reliable for unattended runs and matches
how CI systems (GitHub Actions, Cirrus CI) typically operate with Tart VMs.

**Why patch URLs/sha256 the same way as Docker Tier 2?**
Consistency. The awk pattern is already tested and understood. Reusing it means
the macOS test validates the same formula content as the Linux Docker test.

**Why `sshpass` instead of SSH keys?**
The base image ships with `admin`/`admin` — no key injection mechanism. `sshpass`
is the standard approach for Tart automation with default images. It's a one-time
`brew install`.

---

## Sequencing

1. Rewrite `tart-test.sh` (core change)
2. Update `README.md` with setup instructions
3. Add `make tart-pull` to `Makefile`
4. Update `CLAUDE.md`

---

## Verification

```bash
# One-time setup (if not done)
brew install cirruslabs/cli/tart
brew install hudochenkov/sshpass/sshpass
make tart-pull   # ~6GB download, once

# Run Tier 3 (tests local source, ~15min)
make validate-vm

# Debug: keep VM alive after test
SKIP_DELETE=1 make validate-vm
# Then SSH in manually: ssh admin@$(tart ip earlbear-test-<timestamp>)

# Verify the formula URL patching worked
# (Should see `file:///Users/admin/tap-v1.0.0.tar.gz` in the brew install output)
```

Expected output:
```
==> Tier 3: macOS VM clean-room install
==> Cloning base VM image: earlbear-test-1234567890
==> Starting VM...
==> Waiting for SSH (~30s)...
==> rsync tap source into VM...
==> Patching formula URLs + installing...
==> Running smoke tests...
  ✓ ebdeck --help
  ✓ ebjira (CONFIG_MISSING — expected)
  ✓ ebdocs (CONFIG_MISSING — expected)
  ✓ ebshop (CONFIG_MISSING — expected)
  ✓ agent-cli help
  ✓ earlbear-setup exists
Results: 6 passed, 0 failed
✓ Tart VM validation passed
```
