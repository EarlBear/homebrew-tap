# /add-cli

End-to-end guide for adding a new Python CLI to the EarlBear ecosystem: source,
formula, cowork plugin, test harness, and release wiring — all in one pass.

## When to use

Use this skill when you have a new Python CLI in `earlbear-clis/` (or are about
to write one) and you want it to be:

- Installable on macOS via `brew install bytesofpurpose/earlbear/<cli>`
- Callable inside Claude Desktop cowork sessions via a pre-compiled plugin binary
- Covered by all validation tiers (audit → Docker → smoke → plugin binary → cowork)

---

## Before you start

Answer these questions. They determine the formula type and plugin shape:

| Question | Determines |
|---|---|
| Is the CLI a Docker-wrapped binary or native Python? | Formula type: `docker` vs `python-venv` |
| Does the CLI need credentials at runtime? | Which `cowork_require_token` env var name to use |
| Which subcommands are destructive (create / delete / publish)? | `confirm` rules in plugin.json |
| What is the CLI's PyPI package name (from `pyproject.toml`)? | Resource blocks in the formula |

---

## Step 1 — Source setup (earlbear-clis)

The CLI source lives in `../earlbear-clis/<cli>-cli/`. It must have:

- `pyproject.toml` with a `[project.scripts]` entry point, e.g.:
  ```toml
  [project.scripts]
  ebfoo = "ebfoo.main:app"
  ```
- A `hatch` or `setuptools` build backend

If you're writing the CLI from scratch, follow the `ebjira` or `ebdeck` pattern
in `../earlbear-clis/`.

---

## Step 2 — Sync source into earlbear-homebrew

Add a rsync block to `Makefile` → `sync-sources` target (keeping the existing
`--exclude='*/bin/'` pattern):

```makefile
rsync -a --delete \
    --exclude='tests/' --exclude='.venv/' --exclude='__pycache__/' \
    --exclude='*.pyc' --exclude='dist/' \
    $(EARLBEAR_ROOT)/earlbear-clis/<cli>-cli/ src/<cli>/
```

Then update the Source sync table in `CLAUDE.md`:
```
- `src/<cli>/` ← `../earlbear-clis/<cli>-cli/`
```

Run:
```bash
make sync-sources
ls src/<cli>/pyproject.toml   # verify sync worked
```

---

## Step 3 — Write the formula

Use `/add-formula <cli>` for step-by-step formula creation (templates,
PyPI resource lookup, gotchas). The add-formula skill handles the full
`Formula/<cli>.rb` authoring workflow.

**After formula is written:**

```bash
make validate-audit    # Tier 1: Ruby syntax + Homebrew policy
make validate-docker   # Tier 2: brew install in Docker (~5min)
```

Add the formula to `validation/docker/Dockerfile`:
```dockerfile
RUN brew install bytesofpurpose/earlbear/<cli>
RUN test -x $(brew --prefix)/bin/<cli>   # smoke test
```

Add to `validation/smoke/smoke-test.sh`:
```bash
assert_binary "<cli>"
```

---

## Step 4 — Add to the earlbear meta-formula

`Formula/earlbear.rb` is the one-liner setup entry point. Add the new CLI as a
dependency:

```ruby
depends_on "bytesofpurpose/earlbear/<cli>"
```

---

## Step 5 — Create the cowork plugin

Use `/make-cowork-plugin` for the full cowork binary + shim workflow. Summary:

### 5a. Create the plugin directory in the marketplace

In `../earlbear-claude-plugin-marketplace/plugins/<plugin-name>/`:

```
<plugin-name>/
├── .claude-plugin/
│   └── plugin.json
├── bin/
│   └── <cli>       # cowork shim (bash wrapper)
└── skills/
    └── <skill>.md
```

### 5b. Write plugin.json

```json
{
  "name": "<plugin-name>",
  "description": "<cli> — <short description>",
  "version": "1.0.0",
  "author": { "name": "Omar Eid" },
  "license": "MIT",
  "confirm": [
    { "op": "create_<thing>", "match": "<thing> create" },
    { "op": "delete_<thing>", "match": "<thing> delete" }
  ]
}
```

Derive `confirm` rules from the CLI's command tree:
```bash
<cli> --help-json 2>/dev/null | jq '.commands[].name'
# or walk `<cli> <subcommand> --help` manually for each group
```

Gate any subcommand that writes, modifies, or deletes real data.

### 5c. Write the cowork shim (`bin/<cli>`)

```bash
#!/bin/bash
set -euo pipefail
_mnt="${BASH_SOURCE[0]}"
while [[ "$_mnt" != "/" && "$(basename "$_mnt")" != "mnt" ]]; do
  _mnt="$(dirname "$_mnt")"
done
source "$_mnt/.cowork-lib/shim.sh"
cowork_require_token <ENV_VAR_NAME>   # omit if no credentials needed
cowork_gate "$@"
cowork_exec <cli> "$@"
```

```bash
chmod +x bin/<cli>
```

Common credential env var names used across EarlBear plugins:
| CLI | Env var |
|---|---|
| ebjira | `JIRA_API_TOKEN` |
| ebdocs | `GOOGLE_OAUTH_TOKEN` |
| ebshop | `SHOPIFY_ACCESS_TOKEN` |
| ebdeck | (none — reads files from filesystem) |

---

## Step 6 — Add Makefile build target

In `Makefile`, add:

```makefile
build-plugin-<cli>: ## Build <cli> binaries for cowork (aarch64 + x86_64, ~5min)
	$(call build-cli,<cli>,<plugin-name>)
```

And add to `build-plugin-binaries`:
```makefile
build-plugin-binaries: build-plugin-ebjira build-plugin-ebdocs build-plugin-ebshop build-plugin-ebdeck build-plugin-<cli> ## Build all cowork plugin binaries
```

Build and verify:
```bash
make build-plugin-<cli>
# Output: plugins-bundle/<plugin-name>/bin/<cli>-aarch64-linux (~15-50MB)
#         plugins-bundle/<plugin-name>/bin/<cli>-x86_64-linux
```

---

## Step 7 — Expand validate-plugin-binaries

Edit `validation/plugin-binaries/test.sh` to add the new CLI's binary to the
test loop. Follow the existing pattern — the test:
1. Runs `<cli>-aarch64-linux --help` inside `ubuntu:24.04` ARM64
2. Asserts exit 0 (or 2 for CONFIG_MISSING — which is a pass)
3. Checks output mentions the CLI name
4. Checks for no linker errors

```bash
make validate-plugin-binaries
```

---

## Step 8 — Sync to plugins-bundle and commit

```bash
make sync-sources   # pulls plugin structure from marketplace repo (preserves bin/)
git add plugins-bundle/<plugin-name>/
git add src/<cli>/
git add Formula/<cli>.rb
git add Makefile
git add validation/docker/Dockerfile validation/smoke/smoke-test.sh
git add validation/plugin-binaries/test.sh
git commit -m "feat(<cli>): add formula + cowork plugin + validation"
```

Stage binaries with LFS automatically:
```bash
git add plugins-bundle/<plugin-name>/bin/<cli>-aarch64-linux
git add plugins-bundle/<plugin-name>/bin/<cli>-x86_64-linux
# git LFS intercepts these via .gitattributes pattern `plugins-bundle/**/bin/*-linux`
git commit -m "feat(<cli>): add cowork plugin binaries (LFS)"
git push origin main   # pushes LFS objects automatically
```

---

## Step 9 — Update docs

**`README.md`** — add to formula status table:
```markdown
| `<cli>` | python-venv | ✓ validated |
```

**`CLAUDE.md`** — add to Source sync table:
```markdown
- `src/<cli>/` ← `../earlbear-clis/<cli>-cli/`
```

**`CLAUDE.md`** — add to Formulas table (if a new type or notable):
```markdown
| `<cli>` | Python venv | <description> |
```

---

## Validation checklist

Run these in order before releasing:

```bash
make validate-audit              # Tier 1 — Ruby syntax (~30s)
make validate-docker             # Tier 2 — brew install in Docker (~5min)
make validate-smoke              # Tier 4 — local smoke test (~10s)
make build-plugin-<cli>          # compile both arches
make validate-plugin-binaries    # Tier 5b — binary runs in ubuntu:24.04 ARM64
make validate-vm                 # Tier 3 — full clean-room macOS install (Apple Silicon, ~15min)
```

Then release:
```bash
make bump-and-release VERSION=x.y.z
```

---

## Living artifacts to update

Whenever you add a new CLI, these files become stale and should be updated:

| File | What to update |
|---|---|
| `Makefile` | `sync-sources` block + `build-plugin-<cli>` target + `build-plugin-binaries` aggregate |
| `Formula/<cli>.rb` | New formula |
| `Formula/earlbear.rb` | New `depends_on` entry |
| `validation/docker/Dockerfile` | New `brew install` + smoke test line |
| `validation/smoke/smoke-test.sh` | New `assert_binary` line |
| `validation/plugin-binaries/test.sh` | New CLI in the test loop |
| `plugins-bundle/<plugin-name>/` | Shim + binaries + plugin.json |
| `README.md` | Formula status table |
| `CLAUDE.md` | Source sync table + Formulas table |
