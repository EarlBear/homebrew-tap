# Refresh Living Docs

> Detect stale documentation across the EarlBear project. Run after adding CLI commands, Makefile targets, or before committing large changes.

## Two layers of living-docs validation

EarlBear has **two complementary layers** that catch documentation drift:

1. **`Stop` hook (automatic, just-in-time)** — Fires at the end of every Claude Code turn. Reads `.claude/hooks/living-artifacts.yaml`, checks which files changed in the working tree (`git diff --name-only HEAD` + untracked), and emits a markdown checklist reminding Claude to verify related artifacts before handing back to the user. Lightweight, turn-scoped, reminder-only (never blocks). Config lives in `.claude/hooks/living-artifacts.yaml`; script is `.claude/hooks/check-living-artifacts.py`. Installed in all three repos (earlbear, earlbear-clis, earlbear-claude-agent) with repo-specific trigger maps.

2. **`/refresh-living-docs` (on-demand deep validator)** — This skill. Runs `scripts/refresh-living-docs.py` which does regex/AST drift detection across the full tree: CLI command tree vs CLAUDE.md, Makefile targets vs Quick Start, living-docs table vs disk, skills vs SKILL.md files, agent repo sync. Use when you want a full audit, not just the last turn's edits — e.g., before a release, after a big refactor, or when the hook reminds you that many files changed at once.

**When to use which:** Trust the Stop hook for per-turn reminders; run `/refresh-living-docs` when you want to verify the whole tree is consistent (and before committing a change that touches many living docs).

## When to Run

- After adding or removing CLI commands (ebshop, ebjira, ebdocs)
- After adding or removing Makefile targets
- After adding or removing living documents from CLAUDE.md
- After updating the agent repo (earlbear-claude-agent)
- Before committing large structural changes
- As a periodic health check

## Usage

```bash
python3 scripts/refresh-living-docs.py
```

Or via Makefile:

```bash
make refresh-docs
```

## What It Checks

### 1. CLI Commands (ebshop, ebjira, ebdocs)

Runs `--help-json` for each CLI and compares the command tree against:
- **CLAUDE.md** — the `Command groups:` lines listing groups and subcommands
- **test_discoverability.py** — the `ALL_GROUPS` and `GROUP_SUBCOMMANDS` constants

Detects: missing groups, missing subcommands, stale references to commands that no longer exist.

### 2. Makefile Targets

Parses `## ` comment targets from the Makefile and compares against the CLAUDE.md Quick Start section.

Detects: targets present in the Makefile but missing from Quick Start documentation.

### 3. Living Documents Table

For each file path listed in the CLAUDE.md living documents table, verifies the file exists on disk. Skips cross-repo references (e.g., `earlbear-claude-agent:` prefixed entries).

Detects: broken file paths, deleted documents still referenced.

### 4. Skill References

Checks that every skill listed in the CLAUDE.md Skills section has a corresponding `SKILL.md` file on disk.

Detects: skills referenced in CLAUDE.md that don't have a SKILL.md file.

### 5. Agent Repo Sync

If `../earlbear-claude-agent/` exists, runs `sync-from-earlbear.sh --dry-run` to check if CLI files are out of sync.

Detects: drift between this repo and the agent repo's copy of CLI code.

## How to Fix Each Type of Drift

| Drift Type | Fix |
|-----------|-----|
| Missing CLI group in CLAUDE.md | Add the group to the `Command groups:` line in CLAUDE.md |
| Missing subcommand in CLAUDE.md | Add the subcommand to the group's parenthetical list |
| Stale CLI reference in CLAUDE.md | Remove the group/subcommand that no longer exists |
| Missing group in test_discoverability.py | Add to `ALL_GROUPS` and `GROUP_SUBCOMMANDS` |
| Stale group in test_discoverability.py | Remove from `ALL_GROUPS` and `GROUP_SUBCOMMANDS` |
| Missing Makefile target in Quick Start | Add the target to the Quick Start code block in CLAUDE.md |
| Broken living document path | Update or remove the row from the living documents table |
| Missing skill SKILL.md | Create the skill file or remove the skill entry from CLAUDE.md |
| Agent repo out of sync | Run `cd ../earlbear-claude-agent && ./sync-from-earlbear.sh` |

## Reference

- CLAUDE.md Tenet 2: "Living documents -- keep these updated"
- Living documents table: CLAUDE.md lines 15-69
- CLI command group listings: CLAUDE.md `### Jira CLI`, `### Google Docs CLI`, `### Shopify CLI` sections
