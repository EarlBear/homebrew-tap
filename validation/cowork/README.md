# Tier 5 — Cowork Devcontainer Validation

Regression test for the EarlBear cowork devcontainer using
[apple/container](https://github.com/apple/container).

## Requirements

- Apple Silicon Mac
- macOS 26+
- apple/container installed and running

## Install apple/container

1. Download the installer from https://github.com/apple/container/releases
2. Run the `.pkg` installer
3. Start the system service:

```bash
container system start
```

## Run the test

```bash
make validate-cowork
```

Or directly:

```bash
bash validation/cowork/cowork-test.sh

# Reuse an existing built image (skip the ~10min build):
SKIP_BUILD=1 bash validation/cowork/cowork-test.sh
```

## How it works

`apple/container` uses standard **Dockerfile syntax** — `container build` is a
drop-in for `docker build`. It runs each container as a **lightweight ARM64 VM**
via Apple's Virtualization framework rather than a shared kernel, giving stronger
isolation.

Key points:
- `BUILDING.md` in the apple/container repo is about compiling the `container`
  tool itself from source — not about image format. Images are standard OCI/Dockerfile.
- No Docker daemon or Docker Desktop required. `container` is fully independent.
- Base images are pulled from standard OCI registries (Docker Hub, etc.).
- No docker-compose equivalent — individual `container run` commands only.

## What the test validates

The test builds `devcontainer/Dockerfile` from repo root (build context must be
`..` relative to `devcontainer/` so the `COPY . /tmp/tap-src/` step works), then
runs 11 smoke checks inside the container via `container exec`:

| Check | What it verifies |
|---|---|
| `brew --version` | Homebrew installed and functional |
| `ebdeck --help` | Primary cowork CLI works |
| ebdeck binary at brew bin | Install path correct |
| `brew list earlbear-plugins` | Formula recorded as installed |
| `install-plugins.sh` at libexec | Correct path (not `share/earlbear/`) |
| `install-plugins.sh` executable | Post-create hook can run |
| `marketplace.json` present | Plugin bundle intact |
| PATH contains linuxbrew bin | Shell environment correct |
| WORKDIR is `/workspace` | Container starts in right directory |
| `python3.11 --version` | Homebrew-managed Python available |
| `ebdeck` Python package importable | venv wired correctly |

## Tap strategy

The Dockerfile uses the same local-archive + awk sha256-patch approach as
Tier 2 (`validation/docker/Dockerfile`) — no GitHub auth required:

1. `COPY . /tmp/tap-src/` — bring tap source into the build context
2. Init tap dir as a git repo (required by `brew tap`)
3. Build a local `.tar.gz` archive, compute its sha256
4. `sed` patches formula URLs from GitHub → `file:///` local path
5. `awk` patches only the formula-level sha256 (not resource sha256s)
6. `brew tap` from the local git repo

This means the cowork image builds offline and against the exact local state
of the repo, not a published GitHub release.
