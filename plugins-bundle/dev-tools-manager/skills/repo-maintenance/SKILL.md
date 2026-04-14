---
name: repo-maintenance
description: Audit and clean up any EarlBear repo — stale agent worktrees, git hooks, and required Makefile targets. Run periodically or after a batch of agent sessions.
type: skill
allowed-tools: Bash(git *), Bash(make *), Bash(ls *), Bash(du *), Bash(mkdir *), Bash(chmod *), Read, Edit, Write, Glob
---

# Repo Maintenance

Audits the current repo for stale agent worktrees, missing git hooks, and
missing standard Makefile targets. Cleans or scaffolds what's needed.

## When to run

- After a batch of Claude agent sessions (worktrees accumulate)
- On a fresh clone (hooks not installed)
- When `make help` is missing expected targets
- Periodically — monthly or whenever disk feels tight

## Step 1 — Audit worktrees

```bash
git worktree list
```

Agent worktrees live at `.claude/worktrees/agent-*`. They are safe to remove
once the agent session is done — they hold no uncommitted work that isn't
already in a branch or discarded.

**Clean stale worktrees:**
```bash
make clean-worktrees     # earlbear repo only — the only repo that spawns agent worktrees
```

If the repo has no `clean-worktrees` target, run manually:
```bash
git worktree list | awk '/\.claude\/worktrees\/agent-/{print $1}' | \
  xargs -I{} git worktree remove --force {}
git worktree prune
```

## Step 2 — Verify git hooks

Each repo should have hooks pointing at a `.githooks/` directory:

```bash
git config core.hooksPath   # should return ".githooks" or ".githooks/"
```

If missing or wrong:
```bash
make install-hooks
```

All EarlBear repos have `make install-hooks`. It sets `core.hooksPath` and
`chmod +x`s the hooks. Hooks installed:

| Repo | pre-commit | pre-push |
|---|---|---|
| `earlbear` | gitleaks staged scan | gitleaks full scan |
| `earlbear-homebrew` | gitleaks + large-file guard (>500KB non-LFS) | gitleaks full scan |
| `earlbear-sites` | gitleaks staged scan | gitleaks full scan |
| `earlbear-clis` | gitleaks staged scan + tests | gitleaks full scan |
| `earlbear-claude-plugin-marketplace` | gitleaks staged scan | gitleaks full scan |

## Step 3 — Required Makefile targets per repo type

Every EarlBear repo must have these targets. If missing, add them.

### All repos

| Target | Purpose |
|---|---|
| `make help` | Print all targets with descriptions |
| `make install-hooks` | Install git hooks |
| `make secret-scan` | Full gitleaks scan |
| `make secret-scan-staged` | Staged-only scan (used by pre-commit hook) |
| `make clean` | Remove build artifacts |

### Repos with agent worktrees (`earlbear` only)

| Target | Purpose |
|---|---|
| `make clean-worktrees` | Remove all `.claude/worktrees/agent-*` worktrees |

### Repos with Docker/container builds (`earlbear-homebrew`)

| Target | Purpose |
|---|---|
| `make clean-container-cache` | Remove buildkit container (frees 20-30GB) |
| `make cowork-sim-build-base` | Build linuxbrew base image (one-time) |
| `make tart-build-base` | Build macOS VM snapshot with Homebrew (one-time) |

## Step 4 — Check for stale branches

```bash
git branch -vv | grep ': gone]'   # branches whose remote is deleted
```

Clean with:
```bash
git fetch --prune
git branch -vv | grep ': gone]' | awk '{print $1}' | xargs git branch -d
```

## Full audit command sequence

```bash
# 1. Stale worktrees (earlbear only)
make clean-worktrees

# 2. Hooks
git config core.hooksPath || make install-hooks

# 3. Stale branches
git fetch --prune
git branch -vv | grep ': gone]'

# 4. Disk (homebrew only — buildkit cache)
make clean-container-cache   # only if disk is tight; safe to run any time
```

## EarlBear repo map (post-org-migration)

| Local dir | GitHub remote | Purpose |
|---|---|---|
| `earlbear/` | `EarlBear/landing` | CLIs, cloud agent, MCP, agent skills |
| `earlbear-clis/` | `EarlBear/clis` | Python CLI source (ebjira/ebdocs/ebshop/ebdeck) |
| `earlbear-sites/` | `EarlBear/sites` | Frontend/visual assets, dist pipeline |
| `earlbear-homebrew/` | `EarlBear/homebrew-tap` | Homebrew formulas + validation |
| `earlbear-claude-plugin-marketplace/` | `EarlBear/marketplace-claude-plugins` | Claude plugin marketplace |

Brew tap name: `earlbear/tap` (maps to `EarlBear/homebrew-tap`).
gh-pages URL: `earlbear.github.io/landing/` (served from `EarlBear/landing` gh-pages branch).
