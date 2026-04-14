# Tier 6: Claude Desktop Cowork VM Integration Test

**Status**: Manual today — no automated path exists.

---

## What Tier 6 tests

Tiers 1–5b validate that:
- Formulas install correctly (Tiers 1–4)
- The devcontainer builds and tools are reachable (Tier 5)
- Plugin binaries execute in `ubuntu:24.04` ARM64 (Tier 5b)

Tier 6 validates the **end-to-end plugin delivery path inside the actual Claude Desktop cowork VM**:
- The plugin is mounted into the VM correctly
- The cowork shim (`bin/ebjira`) resolves `.cowork-lib/shim.sh`
- `cowork_require_token` exits 2 with the right message when not connected
- `cowork_gate` blocks and shows a permission card for a destructive op
- `cowork_exec` dispatches to `ebjira-aarch64-linux` (not the x86_64 build)
- The binary runs and responds to `--help` inside the VM

---

## Why it can't be automated today

The cowork VM is only accessible via three MCP tools exposed by Claude Desktop:

| MCP tool | Purpose |
|---|---|
| `mcp__cowork__launch_code_session` | Open a Claude Code session inside the VM |
| `mcp__cowork__present_files` | Present files from the VM to the renderer |
| `mcp__cowork__request_cowork_directory` | Request a directory path inside the VM |

There is no `mcp__cowork__exec` or shell access from outside. To run a command inside the VM you must be **inside a Claude Code cowork session** using the Bash tool. That requires Claude Desktop's full MCP stack to be running — it cannot be driven by a standalone shell script.

---

## Manual test procedure

Prerequisites:
- Claude Desktop installed and running
- Plugin repo cloned with `git lfs pull` (so binaries are present)
- Plugin installed in Claude Desktop: **Settings → Plugins → + Add → [path to plugins-bundle/jira-manager]**

### Step 1 — Open a cowork session

In Claude Desktop, open a new Claude Code session (the cowork VM starts automatically).

### Step 2 — Verify the shim resolves

```bash
# In the cowork session's Bash tool:
which ebjira
# Expected: /sessions/<vm>/mnt/<plugin>/bin/ebjira  (or similar mount path)
```

### Step 3 — Verify `cowork_require_token` behaviour

```bash
ebjira --help
# Expected: exits 2, prints:
# "jira-manager: not connected. Open Claude settings → Plugins → jira-manager → Connect."
```

### Step 4 — Connect the plugin

In Claude Desktop: **Settings → Plugins → jira-manager → Connect** → enter your Jira API token.

### Step 5 — Verify `--help` now works

```bash
ebjira --help
# Expected: exits 0, shows the ebjira help text
```

### Step 6 — Verify `cowork_gate` shows a permission card

```bash
ebjira issue create --project TEST --summary "Tier 6 test issue"
# Expected: Claude Desktop shows a confirmation card:
#   "create_issue: ebjira issue create"
#   [Allow] [Deny]
# Click Deny. Expected: command exits 2.
```

### Step 7 — Verify arch dispatch

```bash
file $(which ebjira-aarch64-linux 2>/dev/null || ls /sessions/*/mnt/*/bin/ebjira-aarch64-linux 2>/dev/null | head -1)
# Expected: ELF 64-bit LSB executable, ARM aarch64
```

---

## What would make this automatable

A path to Tier 6 automation exists if any of the following become available:

1. **`mcp__cowork__exec`** — a new MCP tool that runs a command inside the VM and returns stdout/stderr. Claude Desktop would need to expose this.

2. **Cowork session scripting** — if `claude --cowork-session bash -c "..."` were supported as a CLI invocation, we could drive it from a shell script.

3. **VM SSH access** — the VM IP is `172.16.10.3` but SSH is blocked. If an SSH key could be injected at VM startup, `ssh root@172.16.10.3 "ebjira --help"` would work.

Until one of these exists, Tier 6 remains a manual checklist run against a real Claude Desktop install.

---

## Relationship to other tiers

| Tier | What it proves | Automated? |
|---|---|---|
| 5b | Binary runs in `ubuntu:24.04` ARM64 — same base as cowork VM | Yes — `make validate-plugin-binaries` |
| 6 | Shim resolves, token gate works, permission card shows, arch dispatch correct | No — manual |

Tier 5b catches the most likely failure (binary won't run due to glibc mismatch or linker error). Tier 6 catches shim protocol issues and Claude Desktop integration. In practice, if 5b passes and the shim script is correct, 6 should pass.
