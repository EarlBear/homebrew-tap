# /inspect-claude-internals

Inspect the internals of a macOS Electron app (Claude Desktop or similar) to discover its runtime architecture — what VM/container technology it uses, what daemons it ships, what MCP tools it exposes, and how its cowork/sandbox system works.

**Output**: Creates or updates `docs/<app-name>-internals.md` in the current repo with findings.

## Usage

```
/inspect-claude-internals [app-name]
```

If `app-name` is omitted, defaults to `Claude` (`/Applications/Claude.app`).

## Steps

### 1. Running processes

```bash
ps aux | grep -i "container\|docker\|vm\|sandbox\|virt\|<app-name>" | grep -v grep
```

Look for:
- VM/virtualization XPC processes (`com.apple.Virtualization.VirtualMachine`)
- Renderer process command-line flags (`--standard-schemes`, `--secure-schemes`)
- Custom URL schemes registered (e.g. `cowork-artifact:`, `operon-artifact:`)
- Daemon processes with app-specific names

### 2. i18n strings — easiest readable source

```bash
find /Applications/<App>.app/Contents/Resources -name "en-US.json" | \
  xargs grep -i "<feature>" 2>/dev/null
```

i18n JSON files are **not minified**. They contain human-readable feature names, error messages, and settings labels. This is the fastest way to discover feature vocabulary before diving into minified JS.

### 3. Find and unpack the asar bundle

```bash
# List files without extracting
npx asar list /Applications/<App>.app/Contents/Resources/app.asar | grep -i "<feature>"

# Extract for deeper inspection
npx asar extract /Applications/<App>.app/Contents/Resources/app.asar /tmp/<app>-extracted
```

Electron apps store all frontend code in `app.asar`. After extraction look in `.vite/build/` for the minified JS bundles.

### 4. Mine identifiers from minified JS

```bash
# Quoted string identifiers (most reliable)
grep -o '"<feature>[^"]*"' /tmp/<app>-extracted/.vite/build/index.js | sort -u

# Unquoted references (daemons, class names)
grep -o '<daemon>[^,;)]*\|<ClassName>' /tmp/<app>-extracted/.vite/build/index.js | sort -u
```

Key things to look for:
- Daemon names (e.g. `coworkd`)
- VM/bundle identifiers (e.g. `vmBundle`, `vmImage`)
- Log file names (e.g. `coworkd.log`, `cowork-service.log`) — reveal the daemon name
- MCP tool names (e.g. `mcp__cowork__launch_code_session`)
- Settings file names (e.g. `cowork_settings.json`, `cowork_account_settings.json`)

### 5. Application Support directory

```bash
ls ~/Library/Application\ Support/<App>/
```

Look for:
- `vm_bundles/` — VM disk images
- `*-vm/` — VM version directories
- `sessions/` or `*-sessions/` — per-session data
- Log files

For each VM bundle found:
```bash
ls -lh ~/Library/Application\ Support/<App>/vm_bundles/*.bundle/
```

Inspect metadata files (`vmIP`, `gvisorMacAddress`, `machineIdentifier`) and measure image sizes.

### 6. Inspect shipped binaries

```bash
file ~/Library/Application\ Support/<App>/<version>/<binary>
```

If it's an ELF binary, it's a Linux executable shipped to run inside a VM. Note the arch (ARM64 = Apple Silicon native), dynamic linker path, and whether it's stripped.

### 7. Network access (optional)

```bash
# Read VM IP from metadata
cat ~/Library/Application\ Support/<App>/vm_bundles/*.bundle/vmIP

# Try SSH (often blocked)
ssh -o ConnectTimeout=3 root@<vmIP> "uname -a" 2>&1
```

Direct SSH is usually blocked. If it times out, the VM is accessible only through the app's MCP/IPC interface.

---

## Output format

Write findings to `docs/<app-name>-internals.md` covering:

1. **Architecture diagram** — how the components connect
2. **VM bundle on disk** — file listing with sizes and purposes
3. **Shipped binaries** — ELF/native binaries found in Application Support
4. **MCP tools** — any `mcp__<feature>__*` tool names found
5. **URL schemes** — custom Electron URL schemes registered
6. **Relationship to our tooling** — how this affects our devcontainer/test approach
7. **Third regression tier?** — assess whether a VM-internal test tier is needed

See `docs/claude-app-internals.md` for the reference output from inspecting Claude Desktop.

---

## Key findings from Claude Desktop (reference)

Claude Desktop ships its **own Linux VM system** — independent of Docker and apple/container:

```
Claude Desktop (Electron)
  └── coworkd daemon
       └── Apple Virtualization.framework (XPC)
            └── claudevm.bundle (10GB rootfs.img)
                 └── claude (ARM64 ELF, v2.1.92) — Claude Code CLI for Linux
```

- VM IP: `172.16.10.3` (private vmnet, SSH blocked)
- Cowork exposed via MCP: `mcp__cowork__launch_code_session`, `mcp__cowork__present_files`, etc.
- `cowork-artifact:` URL scheme serves VM content into the Electron renderer
- Our `devcontainer/` uses `apple/container` — entirely separate from Claude's internal VM
- A "Tier 6" test (run commands inside Claude's VM via MCP) is theoretically possible but requires Claude Desktop's MCP stack to be running — not a pure shell script test
