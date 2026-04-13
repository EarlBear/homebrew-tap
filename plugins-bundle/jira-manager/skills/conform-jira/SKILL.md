# Conform Jira

> Ensure the live Jira project matches the declarative manifest. Detect drift, preview changes, apply, and regenerate diagrams. Run this after editing the manifest or as a periodic health check.
>
> **Manifest location:** `manifests/jira/manifest.yaml`
> **Design doc:** `docs/design-jira-manifest.md`
> **Edit the manifest:** Use `/manage-jira-manifest` to change the desired state. This skill enforces it.

## When to Trigger

User says: "conform Jira", "apply manifest", "check Jira drift", "sync Jira with manifest", "make Jira match", "Jira health check", "are statuses configured", "is the workflow set up"

Also run proactively:
- After any `/manage-jira-manifest` edit
- As part of `/refine-working-model` health checks
- Before deploying the cloud agent (ensure agent's JQL matches reality)

## Procedure

### Step 1: Diff (always start here)

```bash
bin/ebjira manifest diff --project EARL
```

Read the output. Three possible outcomes:

**Clean (0 differences):**
> Jira matches the manifest. Nothing to do.

Skip to Step 3 (diagrams) if you want fresh docs.

**Drift detected:**
Review each difference. The diff shows:
- `+ missing_in_jira` — manifest wants it, Jira doesn't have it (will be created)
- `- extra_in_jira` — Jira has it, manifest doesn't (will NOT be deleted unless `--allow-delete`)
- `~ workflow_drift` — workflow exists but transitions don't match

**Breaking changes:**
If the diff flags statuses with issues in them:
```
WARNING: Status "Drafting" has 3 issues. Removing requires migration.
```
Do NOT proceed without migrating issues first:
```bash
bin/ebjira bulk transition --jql 'project = EARL AND status = "Drafting"' --to "In Progress" --dry-run
bin/ebjira bulk transition --jql 'project = EARL AND status = "Drafting"' --to "In Progress"
```

### Step 2: Apply

```bash
# Preview what would happen (no changes made)
bin/ebjira manifest apply --project EARL --dry-run

# Apply with confirmation prompts
bin/ebjira manifest apply --project EARL

# Apply without prompts (use after reviewing diff)
bin/ebjira manifest apply --project EARL --yes
```

**What apply does:**
- Creates missing statuses
- Creates missing issue types
- Creates missing components
- Creates workflow + transitions if missing
- Creates workflow scheme + assigns to project if missing
- Never deletes anything without `--allow-delete`

**Verify after apply:**
```bash
bin/ebjira manifest diff --project EARL
```
Should now show 0 differences.

### Step 3: Regenerate Diagrams

```bash
bin/ebjira manifest diagram --output-dir docs/diagrams/
```

Generates four Mermaid files:
- `docs/diagrams/workflow.md` — state diagram of statuses + transitions
- `docs/diagrams/issue-types.md` — issue type hierarchy
- `docs/diagrams/components.md` — component map
- `docs/diagrams/agent-flow.md` — Earl's operating model

These are **auto-generated** — never hand-edit them.

### Step 4: Commit Together

If any changes were made (apply or diagrams), commit everything:

```bash
git add manifests/jira/manifest.yaml docs/diagrams/
git commit -m "Conform Jira to manifest + regenerate diagrams"
```

The manifest and generated diagrams should always be committed in the same changeset.

## Quick Reference

| Intent | Command |
|--------|---------|
| Check drift | `bin/ebjira manifest diff --project EARL` |
| Preview apply | `bin/ebjira manifest apply --project EARL --dry-run` |
| Apply changes | `bin/ebjira manifest apply --project EARL --yes` |
| Export Jira snapshot | `bin/ebjira manifest export --project EARL` |
| Regenerate diagrams | `bin/ebjira manifest diagram --output-dir docs/diagrams/` |
| Migrate issues off old status | `bin/ebjira bulk transition --jql '...' --to "NewStatus"` |

## Manual Steps (Jira UI Required)

These three operations cannot be automated via CLI and require the Jira web UI:

| Operation | Where in Jira UI | When needed |
|-----------|-----------------|-------------|
| **Create workflow** | Settings → Issues → Workflows → Add workflow | First-time setup or adding a new workflow (Free tier limitation — Standard+ unlocks API) |
| **Board column mapping** | Board → Settings (gear icon) → Columns → drag statuses to columns | After adding new statuses to the workflow |
| **Board permissions** | Board → Settings → Permissions | When changing who can view/edit the board |

After completing manual steps, run `bin/ebjira manifest diff` to verify conformance.

**URLs for EARL project:**
- Workflows: https://earlbear.atlassian.net/jira/settings/issues/workflows
- Board settings: https://earlbear.atlassian.net/jira/software/c/projects/EARL/boards/34/settings
- Board view: https://earlbear.atlassian.net/jira/software/c/projects/EARL/boards/34

## What This Skill Does NOT Do

- **Edit the manifest** — use `/manage-jira-manifest` to change desired state
- **Create issues** — use `/add-backlog-item` for that
- **Delete Jira config** — requires explicit `--allow-delete` flag, never automatic
