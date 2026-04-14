# /make-cowork-plugin

Guide for converting an EarlBear Claude plugin to work inside the Claude Desktop cowork VM.

## Terminology (important — don't conflate these)

| Term | What it means |
|---|---|
| **Claude plugin** | A `.claude-plugin/` package that adds skills + MCP tools to Claude. Lives in the marketplace. |
| **Skill** | A prompt file inside a plugin (`skills/<name>.md`) that gives Claude domain knowledge and a workflow. Skills are just prompts — they don't execute code directly. |
| **CLI** | A binary (`ebjira`, `ebdeck`, etc.) that a skill tells Claude to call via the Bash tool. |
| **Cowork VM** | The Linux ARM64 VM that Claude Code sessions run inside. No Docker daemon. No Homebrew at install time. |
| **Cowork shim** | A bash wrapper in `plugin/bin/<cli-name>` that handles arch dispatch + credential injection + permission gating before calling the real binary. |

**The key constraint**: On macOS, skills call CLIs that are brew-installed. Inside the cowork VM, there is no `brew install` at plugin load time. The CLI binary must be **shipped inside the plugin** in `bin/`.

---

## Plugin structure (cowork-compatible)

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json          # name, description, version, confirm rules
├── bin/
│   ├── my-cli               # cowork shim (bash, ~8 lines)
│   ├── my-cli-aarch64-linux # compiled binary for Apple Silicon VM
│   └── my-cli-x86_64-linux  # compiled binary for Intel VM
├── skills/
│   └── my-skill.md          # prompt file (same as today)
└── README.md
```

**Current EarlBear plugins** (`jira-manager`, `deck-manager`, etc.) have no `bin/` — skills assume the CLI is on PATH via Homebrew. This works on macOS but breaks in the cowork VM.

---

## plugin.json

```json
{
  "name": "jira-manager",
  "description": "Create and manage Jira issues via ebjira CLI.",
  "version": "1.0.0",
  "author": { "name": "Omar Eid" },
  "license": "MIT",
  "confirm": [
    { "op": "create_issue",  "match": "issue create" },
    { "op": "delete_issue",  "match": "issue delete" },
    { "op": "close_sprint",  "match": "sprint close" }
  ]
}
```

`confirm` rules gate dangerous operations through Claude Desktop's permission bridge. The user sees a confirmation card before the op runs. Rules are checked in order, first match wins.

| Field | Type | Meaning |
|---|---|---|
| `op` | string | Human-readable operation name shown in the permission card |
| `match` | string | Space-separated token subsequence to match in argv |
| `flag` | string | Op only triggers if this flag is also present |
| `unless_flag` | string | Op is skipped (no confirmation) if this flag is present |

---

## The cowork shim (`bin/my-cli`)

Every binary entry point is a short bash shim — Claude Desktop mounts the shim library at a known path inside the VM and the shim walks to it:

```bash
#!/bin/bash
set -euo pipefail
_mnt="${BASH_SOURCE[0]}"
while [[ "$_mnt" != "/" && "$(basename "$_mnt")" != "mnt" ]]; do
  _mnt="$(dirname "$_mnt")"
done
source "$_mnt/.cowork-lib/shim.sh"

# Optional: fail fast if OAuth token not injected
cowork_require_token JIRA_API_TOKEN

# Gate dangerous operations through permission bridge
cowork_gate "$@"

# Arch dispatch: picks bin/ebjira-aarch64-linux or bin/ebjira-x86_64-linux
cowork_exec ebjira "$@"
```

### The three shim helpers (source: `cowork-plugin-shim.sh` in Claude.app)

**`cowork_require_token ENV_VAR`**
Exits 2 ("not connected — go to Settings → Plugins → Connect") if the named env var is unset. Use this for any CLI that needs credentials injected by Claude Desktop's OAuth flow.

**`cowork_gate ARGV...`**
Matches argv against `plugin.json → .confirm` rules. If matched, blocks until the user approves or denies in Claude Desktop (polls up to 100s). Returns 0 on allow, exits 2 on deny.

**`cowork_exec PREFIX ARGV...`**
Finds `bin/<prefix>-aarch64-linux*` or `bin/<prefix>-x86_64-linux*` based on `uname -m` and `exec`s it. The glob `*linux*` allows suffixes like `-linux-musl`, `-linux-gnu`, `-unknown-linux-musl`.

---

## Packaging the CLI binary

This is the hard part. The binary must run inside the VM with zero external dependencies.

### Option A — PyInstaller (Python CLIs like ebdeck)

PyInstaller bundles the Python interpreter + all pip dependencies into a single self-contained binary. No pip, no Python required at runtime.

```bash
# Install cross-compilation deps
pip install pyinstaller

# Build for ARM64 (run on Apple Silicon or use cross-compilation)
pyinstaller --onefile \
  --name ebdeck-aarch64-linux \
  src/ebdeck/main.py

# Build for x86_64
# (requires an x86_64 Linux machine or Docker cross-build)
pyinstaller --onefile \
  --name ebdeck-x86_64-linux \
  src/ebdeck/main.py
```

**Result**: `dist/ebdeck-aarch64-linux` (~15-50MB), zero runtime deps.

**Cross-compilation**: PyInstaller cannot cross-compile in one step. Use:
- Docker: `docker run --platform linux/amd64 python:3.11 pyinstaller --onefile ...`
- GitHub Actions matrix with `runs-on: ubuntu-latest` (x86_64) and `runs-on: ubuntu-24.04-arm` (aarch64)

### Option B — Static binary (Go CLIs or Rust)

If the CLI is written in Go or Rust, compile with static linking:

```bash
# Go
GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build -o bin/my-cli-aarch64-linux .
GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -o bin/my-cli-x86_64-linux .

# Rust
cargo build --release --target aarch64-unknown-linux-musl
cargo build --release --target x86_64-unknown-linux-musl
```

The musl target suffix (`-linux-musl`) is matched by the `cowork_exec` glob. Zero `.so` dependencies.

### Option C — Bundle .so files (last resort)

If static linking isn't feasible, ship shared libraries alongside the binary and use a wrapper that sets `LD_LIBRARY_PATH`. Fragile — only use if A and B don't work.

### What CANNOT work in the cowork VM

- **Docker-wrapped CLIs** (`ebjira`, `ebdocs`, `ebshop` in current form) — there is no Docker daemon in the VM. These must be rewritten as native binaries.
- **Homebrew formulas** — `brew install` is not run at plugin load time.
- **`~/.config/earlbear/.env`** — the user's config dir is not mounted. Credentials must come via OAuth token injection (see below).

---

## Credential injection

On macOS, our CLIs read from `~/.config/earlbear/.env`. This path doesn't exist in the cowork VM.

Claude Desktop injects credentials as environment variables when the user connects a plugin in **Settings → Plugins → [Plugin Name] → Connect**. Declare what you need in the shim with `cowork_require_token`:

```bash
cowork_require_token JIRA_API_TOKEN      # Jira PAT
cowork_require_token GOOGLE_CLIENT_ID    # Google OAuth
```

In the binary itself, read from the env var instead of `.env`:

```python
# Instead of: config = load_dotenv("~/.config/earlbear/.env")
jira_token = os.environ.get("JIRA_API_TOKEN") or die("JIRA_API_TOKEN not set")
```

The plugin manifest declares what OAuth scopes are needed — Claude Desktop handles the OAuth flow and injects the token before calling the shim.

---

## Step-by-step: convert an existing EarlBear plugin

Using `jira-manager` as the example:

### 1. Add `confirm` rules to `plugin.json`

Identify which `ebjira` subcommands are destructive. Add confirm rules:

```json
"confirm": [
  { "op": "create_issue",  "match": "issue create" },
  { "op": "transition",    "match": "issue transition", "unless_flag": "--dry-run" },
  { "op": "delete_sprint", "match": "sprint delete" }
]
```

### 2. Write the shim (`bin/ebjira`)

```bash
#!/bin/bash
set -euo pipefail
_mnt="${BASH_SOURCE[0]}"
while [[ "$_mnt" != "/" && "$(basename "$_mnt")" != "mnt" ]]; do
  _mnt="$(dirname "$_mnt")"
done
source "$_mnt/.cowork-lib/shim.sh"
cowork_require_token JIRA_API_TOKEN
cowork_gate "$@"
cowork_exec ebjira "$@"
```

```bash
chmod +x bin/ebjira
```

### 3. Build and validate the binaries

Use the Makefile targets — they handle `binutils`, `apt-get`, `pip install .`, and output to the right place:

```bash
# Build aarch64-linux only (Apple Silicon VM — the common case)
make build-plugin-ebjira SKIP_AMD=1

# Build both arches
make build-plugin-ebjira

# Output: plugins-bundle/jira-manager/bin/ebjira-aarch64-linux (~19MB)
#         plugins-bundle/jira-manager/bin/ebjira-x86_64-linux  (~19MB)
```

Then prove the binary runs in the same environment as the cowork VM (Ubuntu 24.04 ARM64):

```bash
# Full loop: compile → run in ubuntu:24.04 ARM64 container → assert --help exits cleanly
make validate-plugin-binaries

# Re-run just the container test against an already-compiled binary (~30s)
SKIP_BUILD=1 make validate-plugin-binaries
```

`make validate-plugin-binaries` is the definitive proof that the binary will work in the cowork VM. It runs `ebjira-aarch64-linux --help` inside a live `ubuntu:24.04` ARM64 container (via apple/container) and asserts no linker errors, no crashes.

### 4. Update the skill to use env vars

In `skills/manage-jira.md`, replace any reference to `.env` file setup with:
> Credentials are injected via JIRA_API_TOKEN env var (Claude Desktop OAuth). If not connected, `ebjira` will print "not connected — go to Settings → Plugins → jira-manager → Connect".

### 5. Test in Claude Desktop (manual — Tier 6)

Open a Claude Code cowork session, install the plugin, and run a skill that calls `ebjira`. Verify the permission card appears for destructive ops.

This is the only step that can't be automated today — it requires Claude Desktop's MCP stack to be running. `make validate-plugin-binaries` is the closest automated equivalent.

---

## Makefile targets

### Build

```bash
make build-plugin-binaries          # all four CLIs, both arches (~20min)
make build-plugin-ebjira            # single CLI, both arches (~5min)
make build-plugin-ebdocs
make build-plugin-ebshop
make build-plugin-ebdeck

SKIP_ARM=1 make build-plugin-ebjira # aarch64 only (Apple Silicon VM)
SKIP_AMD=1 make build-plugin-ebjira # x86_64 only
```

**How it works**: `apt-get install binutils` + `pip install .` (resolves `pyproject.toml` deps) → PyInstaller bundles the installed console script + all deps into a single `--onefile` binary. No standalone `main.py` needed.

**Output**: `plugins-bundle/<plugin>/bin/<cli>-aarch64-linux` and `<cli>-x86_64-linux`

After running, commit `plugins-bundle/<plugin>/bin/` to ship the binaries with the plugin.

### Validate

```bash
make validate-plugin-binaries       # compile ebjira + run in ubuntu:24.04 ARM64 (~8min)
SKIP_BUILD=1 make validate-plugin-binaries  # re-run container test only (~30s)
```

This is the authoritative test that the binary is cowork-VM-compatible. It runs `ebjira-aarch64-linux --help` inside a live `ubuntu:24.04` ARM64 container (apple/container) and checks for clean exit, correct output, no linker errors.

---

## Reference

- `docs/claude-app-internals.md` — full cowork VM architecture, inspection methodology
- `/Applications/Claude.app/Contents/Resources/cowork-plugin-shim.sh` — shim library source (well-commented)
- `plugins-bundle/jira-manager/` — existing plugin to convert
- `src/ebjira/` — CLI source to compile
