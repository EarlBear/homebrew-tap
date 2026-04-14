---
name: introduce
description: Self-description of the dev-tools-manager plugin — what it does and when to use it
type: skill
---

# Introduce: dev-tools-manager

The `dev-tools-manager` plugin provides developer tooling for EarlBear repos — secret scanning, git hook configuration, and security hygiene.

## Skills

| Skill | Trigger |
|---|---|
| `/secret-scan` | Scan the repo for leaked secrets, install gitleaks if missing, configure git hooks |
| `/repo-maintenance` | Audit and clean stale agent worktrees, verify git hooks, check required Makefile targets |

## When to use this plugin

- Setting up a fresh clone of any EarlBear repo (configure git hooks)
- Before committing or pushing sensitive changes
- After rotating secrets (full repo scan)
- When a teammate reports a potential leak
- After a batch of Claude agent sessions (clean up stale worktrees)
- Periodically to audit repo health across the org

## Applies to all repos

`dev-tools-manager` is not tied to a specific EarlBear repo. The `secret-scan` skill works in `earlbear`, `earlbear-clis`, `earlbear-sites`, and any other repo with a Makefile `secret-scan` target.
