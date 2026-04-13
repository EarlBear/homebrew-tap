# Claude Desktop Internals: Cowork VM Architecture

Inspected: 2026-04-13 | macOS 26.3.1 | Claude Desktop (Electron, app.asar)

---

## What is Cowork?

**Cowork** is Claude Desktop's built-in Linux VM environment where Claude Code sessions run. It is distinct from the chat interface — when you open a Claude Code session, it runs *inside a Linux VM* on your Mac, with your local filesystem mounted read-only. Claude talks to the VM via MCP tools.

### Cowork vs. regular Claude

| | Regular Claude (chat) | Claude Code (cowork) |
|---|---|---|
| Runtime | Electron renderer process on macOS | Linux VM via Apple Virtualization.framework |
| File access | None (you paste content) | Mount points into your filesystem |
| Tool execution | MCP tools via network/IPC | Bash tool runs inside the Linux VM |
| Plugins | MCP servers on your Mac | Binaries pre-installed into the VM |
| Persistence | Conversation history | `sessiondata.img` per session |

### Architecture

```
Claude Desktop (Electron, macOS)
  └── coworkd daemon (manages VM lifecycle)
       └── Apple Virtualization.framework XPC
            └── claudevm.bundle (Linux ARM64 VM)
                 ├── rootfs.img (10GB, Debian-based)
                 ├── sessiondata.img (112MB, per-session data)
                 └── claude (ARM64 ELF v2.1.92) ← Claude Code CLI
```

The VM has a static IP (`172.16.10.3` on a private vmnet). SSH is blocked — the only way in is via the coworkd MCP interface.

---

## How Cowork Plugins Work

Source: `/Applications/Claude.app/Contents/Resources/cowork-plugin-shim.sh` (shipped with Claude Desktop, well-commented).

### Plugin structure

A cowork-compatible plugin is a directory with:

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json          # manifest: name, confirm rules, etc.
└── bin/
    ├── my-cli-aarch64-linux  # ARM64 binary (Apple Silicon VM)
    └── my-cli-x86_64-linux   # x86_64 binary (Intel VM)
```

Plugins ship **pre-compiled binaries** for each arch. There is no `brew install` or `apt-get` at runtime. The VM's Linux environment runs the binary directly.

### The shim pattern

Each plugin entry point is a ~8-line bash shim:

```bash
#!/bin/bash
set -euo pipefail
_mnt="${BASH_SOURCE[0]}"
while [[ "$_mnt" != "/" && "$(basename "$_mnt")" != "mnt" ]]; do
  _mnt="$(dirname "$_mnt")"
done
source "$_mnt/.cowork-lib/shim.sh"
cowork_require_token MY_PLUGIN_TOKEN   # optional: fail if credential missing
cowork_gate "$@"                       # optional: confirm dangerous ops
cowork_exec my-cli "$@"               # arch dispatch + exec
```

Claude Desktop mounts the shim library read-only at `/sessions/<vm>/mnt/.cowork-lib/shim.sh`. The shim walks up from its own `BASH_SOURCE` to find it — no env var, so the agent cannot redirect to a fake library.

### The three shim helpers

**`cowork_require_token ENV_VAR`**
Fails with exit 2 ("not connected") if the named env var is unset. Used for OAuth tokens injected by Claude Desktop when the user connects the plugin.

**`cowork_gate ARGV...`**
Classifies `$@` against `plugin.json → .confirm` rules. If argv matches a declared dangerous op, it blocks on the renderer permission bridge (polls up to 100s) before returning. The user sees a confirmation card in Claude Desktop.

**`cowork_exec PREFIX ARGV...`**
Finds `bin/<prefix>-aarch64-linux*` or `bin/<prefix>-x86_64-linux*` based on `uname -m` and `exec`s it. This is the arch dispatch layer — you ship both binaries, the shim picks the right one.

### plugin.json confirm rules

```json
{
  "name": "my-plugin",
  "confirm": [
    { "op": "send_email",    "match": "gmail send" },
    { "op": "delete_file",   "match": "rm",           "flag": "--force" },
    { "op": "publish",       "match": "release create","unless_flag": "--draft" }
  ]
}
```

Rules are checked in order, first match wins. `match` is a contiguous token subsequence. `flag` requires the flag to be present. `unless_flag` skips confirmation when the flag is present (e.g. `--draft` is safe, publishing live is not).

---

## Building Cowork-Compatible Skills for EarlBear

### The problem with `brew install`

**`brew install` does NOT work for cowork plugin delivery.** Homebrew is available in the VM (Claude Code uses it to install `gh` and other tools), but:

1. Plugin binaries need to be available *before* any session runs — the VM doesn't run setup scripts per-plugin
2. Network access inside the VM is restricted (egress is gated by `cowork-egress-blocked` in the Electron app)
3. `brew install` takes minutes; plugins need to be instant

### The right approach: pre-compiled binaries

Compile your CLI for both `aarch64-linux` (Apple Silicon) and `x86_64-linux` (Intel) and ship them as plugin binaries. The `cowork_exec` shim dispatches to the right one.

```
earlbear-jira-plugin/
├── .claude-plugin/
│   └── plugin.json
└── bin/
    ├── ebjira-aarch64-linux   # cross-compiled from earlbear-clis/jira-cli
    └── ebjira-x86_64-linux
```

For Python CLIs (like `ebdeck`): use PyInstaller to produce a single-file binary, then cross-compile for each arch. Alternatively, package a minimal Python runtime with the binary.

### Credential injection

Cowork plugins receive credentials via env vars injected by Claude Desktop (user connects the plugin in Settings → Plugins). Declare what token your plugin needs in `plugin.json` and check for it with `cowork_require_token`.

Our existing `~/.config/earlbear/.env` pattern does NOT work inside the VM — the config dir is not mounted. Credentials must come through the plugin OAuth flow.

### Testing cowork-compatible plugins

**Today (Tier 5 — apple/container):** Our `make validate-cowork` builds the devcontainer and smoke-tests binaries. This validates the *Linux binary* works but not the full cowork shim/permission bridge.

**Future (Tier 6 — Claude cowork VM):** A true cowork integration test would:
1. Install the plugin into Claude Desktop
2. Open a Claude Code cowork session
3. Assert the CLI is callable via `mcp__cowork__launch_code_session` + Bash tool

This requires Claude Desktop's MCP stack to be running and is not automatable as a shell script today.

---

## How We Inspected It

### Step 1 — Running processes

```bash
ps aux | grep -i "container\|docker\|vm\|sandbox\|virt" | grep -v grep
```

Revealed `com.apple.Virtualization.VirtualMachine` XPC processes owned by the current user, and the Claude renderer with `--standard-schemes=operon-artifact,cowork-artifact,app`.

### Step 2 — i18n strings (easiest readable source)

```bash
grep -i "cowork" /Applications/Claude.app/Contents/Resources/en-US.json
```

i18n files are not minified — fastest way to discover feature vocabulary. Revealed "Delete Cowork VM Bundle and Restart…", "coworkd.log", "Enable Cowork VM Debug Logging", etc.

### Step 3 — Unpack the Electron asar bundle

```bash
npx asar list /Applications/Claude.app/Contents/Resources/app.asar | grep -i cowork
npx asar extract /Applications/Claude.app/Contents/Resources/app.asar /tmp/claude-extracted
```

Found `/.vite/build/coworkArtifact.js` — a dedicated JS bundle for the cowork renderer.

### Step 4 — Mine identifiers from minified JS

```bash
grep -o '"cowork[^"]*"' /tmp/claude-extracted/.vite/build/index.js | sort -u
grep -o 'vmBundle[^,;)]*\|coworkd\|Virtualization' /tmp/claude-extracted/.vite/build/index.js | sort -u
```

Found: `coworkd`, `vmBundle`, `cowork_vm_cli`, `coworkd.log`, and all MCP tool names.

### Step 5 — Application Support

```bash
ls ~/Library/Application\ Support/Claude/
ls -lh ~/Library/Application\ Support/Claude/vm_bundles/claudevm.bundle/
```

| File | Size | Purpose |
|---|---|---|
| `rootfs.img` | 10GB | Linux root filesystem |
| `rootfs.img.zst` | 2.0GB | Compressed baseline |
| `sessiondata.img` | 112MB | Per-session persistent data |
| `efivars.fd` | 128KB | EFI variable store |
| `vmIP` | 11B | `172.16.10.3` |

### Step 6 — Shipped Linux binary

```bash
file ~/Library/Application\ Support/Claude/claude-code-vm/2.1.92/claude
# → ELF 64-bit LSB executable, ARM aarch64
```

Claude Desktop ships a native ARM64 Linux build of the Claude Code CLI, copied into the VM. Version `2.1.92` as of inspection.

### Step 7 — The plugin shim

```bash
cat /Applications/Claude.app/Contents/Resources/cowork-plugin-shim.sh
```

Well-commented source for the cowork plugin library. Documents the full plugin protocol: binary layout, arch dispatch, permission bridge, confirm rules. See the "How Cowork Plugins Work" section above.

---

## Relationship to Our Devcontainer

Our `devcontainer/` + `make validate-cowork` are **separate** from Claude's internal VM:

| | Claude's cowork VM | Our devcontainer |
|---|---|---|
| Runtime | Apple Virtualization.framework via `coworkd` | `apple/container` CLI |
| Image | `claudevm.bundle` (shipped with Claude Desktop) | `devcontainer/Dockerfile` |
| Purpose | Claude Code sessions inside Claude Desktop | EarlBear tooling environment |
| Access | Via MCP (`mcp__cowork__*` tools) | `container exec` / `container run` |
| Installs tooling via | Pre-compiled binaries in plugin `bin/` | Homebrew formulas |
