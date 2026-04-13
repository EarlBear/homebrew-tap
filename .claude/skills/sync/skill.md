# /sync

Sync the latest CLI source from sibling repos into `src/` and run a quick audit.

## Usage

```
/sync
```

## Steps

### 1. Check sibling repos exist

```bash
ls ../earlbear-clis/jira-cli/ ../earlbear-clis/deck-cli/ ../earlbear/bin/agent-cli \
   ../earlbear-claude-plugin-marketplace/plugins/
```

If any are missing, report which ones and ask the user to check `EARLBEAR_ROOT` in the Makefile.

### 2. Run sync

```bash
make sync-sources
```

### 3. Report what changed

```bash
git diff --stat src/ plugins-bundle/
```

Summarize which CLIs changed (lines added/removed per directory). If nothing changed, say so.

### 4. Run audit tier

```bash
make validate-audit
```

If audit fails, report the error. Do NOT auto-fix Ruby style issues — show the user what brew audit says and ask if they want you to fix it.

### 5. Stage changed files (do NOT commit automatically)

Show the user `git status` output. Ask if they want to commit now with a suggested message like:

```
chore: sync sources from sibling repos (DATE)
```
