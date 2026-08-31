# Manage Jira Manifest

> **Context:** The Jira project manifest (`manifests/jira/manifest.yaml`) is the single source of truth for EARL project configuration -- issue types, statuses, workflow, components, labels, board layout, and agent operating model. All changes to Jira configuration flow through this file. See `docs/design-jira-manifest.md` for the full design rationale.
>
> **Key file:** `manifests/jira/manifest.yaml`
> **Enforce it:** Use `/conform-jira` to diff, apply, and generate diagrams. This skill is for editing the manifest itself.

## When to trigger

User says things like:
- "add a status", "add a component", "change workflow", "edit manifest"
- "export Jira config", "snapshot Jira state", "bootstrap manifest"
- "update Jira config", "new issue type", "new deliverable kind"

**If the user wants to check drift or apply changes to Jira**, use `/conform-jira` instead.

## Router

| Intent | Phrases | Procedure |
|--------|---------|-----------|
| **Update Config** | "add status", "add component", "change workflow", "edit manifest" | [1. Update Manifest](#1-update-manifest) |
| **Export** | "export", "snapshot", "capture Jira state" | [2. Export Jira State](#2-export-jira-state) |
| **Bootstrap** | "bootstrap", "set up from scratch", "initialize manifest" | [3. Bootstrap from Scratch](#3-bootstrap-from-scratch) |
| **Epics registry** | "add epic to manifest", "reconcile epics", "epic list drift", "sync epics block" | [4. Epics registry](#4-epics-registry) |

If the intent is ambiguous, ask the user to clarify before proceeding.

---

## 1. Update Manifest

When the user wants to change Jira configuration, follow this workflow:

### Step 1: Edit the manifest

Edit `manifests/jira/manifest.yaml` with the requested change. Common changes:

**Add a status:**
```yaml
statuses:
  # ... existing statuses ...
  - name: New Status
    category: IN_PROGRESS  # One of: TODO, IN_PROGRESS, DONE
```
Then add transitions involving the new status in `workflow.transitions:`.

**IMPORTANT — Workflow + board column changes require 3 steps:**

1. **Create the status via CLI:** `ebjira status create --name "Planning" --category IN_PROGRESS`
2. **Add to workflow via Jira UI:** Project Settings → Workflow → edit the EARL Workflow → add the status + transitions. The workflow update API (`/workflows/update`) is unreliable and frequently returns 400.
3. **Map to board column via Jira UI:** Board Settings → Columns → drag the new status into the column.

The manifest captures the *desired* state. The CLI can create statuses globally, but adding them to the project workflow and board columns requires the Jira UI. After UI changes, verify with:
```bash
ebjira project statuses EARL    # Confirm status is in project
ebjira board columns 34         # Confirm status is mapped to column
```

**Add a component:**
```yaml
components:
  # ... existing components ...
  - name: new-component
    description: What this component represents
```

**Add a deliverable kind:**
```yaml
labels:
  deliverable_kinds:
    # ... existing kinds ...
    - "kind:new-kind"
```

**Change workflow transitions:**
```yaml
workflow:
  transitions:
    # ... existing transitions ...
    - from: Source Status
      to: Target Status
```

### Step 2: Preview changes

```bash
bin/ebjira manifest diff --project EARL
```

Show the diff to the user and confirm before proceeding.

### Step 3: Push to Jira

```bash
bin/ebjira manifest apply --project EARL
```

### Step 4: Regenerate diagrams

```bash
bin/ebjira manifest diagram --output-dir docs/diagrams/
```

### Step 5: Commit together

Stage and commit the manifest and generated diagrams in a single commit. The manifest and diagrams must always be committed together to stay in sync.

---

## 2. Export Jira State

Snapshot the current Jira configuration to a YAML file.

```bash
bin/ebjira manifest export --project EARL --output /tmp/jira-snapshot.yaml
```

**Use cases:**
- Investigate drift after manual Jira UI changes
- Compare against the current manifest: read both files and diff them
- Back up before major changes
- Initial bootstrap for a new project

After exporting, review the output with the user. If it should become the new manifest, copy it to `manifests/jira/manifest.yaml` after review.

---

## 3. Bootstrap from Scratch

For setting up the manifest on a new project or re-initializing from current Jira state:

```bash
# Export current Jira state
bin/ebjira manifest export --project EARL --output manifests/jira/manifest.yaml

# Review the generated manifest with the user
# Make any adjustments to the YAML

# Apply to ensure Jira matches the reviewed manifest
bin/ebjira manifest apply --project EARL --yes

# Generate diagrams
bin/ebjira manifest diagram --output-dir docs/diagrams/
```

---

## 4. Epics registry

The manifest carries an `epics:` block — a **flat name/key registry**, one entry per epic:

```yaml
epics:
  - key: EARL-1
    summary: Client Discovery
  - key: EARL-2
    summary: Store Analysis
  # ...
```

Its job is to give the rest of the manifest stable, human-readable handles for epics. For example the `agent:` section references it by key:

```yaml
agent:
  checkin_epic: EARL-31   # resolves against the epics registry above
```

**This block is NOT where the epic taxonomy lives.** It only mirrors each epic's key and summary.

### The manifest ↔ taxonomy boundary

Two things about an epic that look like they belong here actually live elsewhere:

- The **emoji prefix** in an epic's `summary` (📦 / 🏢 / 📝 / 🗺️ / 📅 / 🗑️ / 🦴 / 🤖)
- The epic's **`epic:*` classification label** (`epic:deliverable`, `epic:function`, `epic:initiative`, …)

Both live **per-epic** in `/Users/omareid/Workspace/git-earlbear/earlbear-content/jira/EARL/epics/<KEY>.yaml`, and are governed by the separate **`/managing-epic-taxonomy`** skill (the source of truth for *which* categories exist, their emoji, their labels, and mutual-exclusivity rules). The `epics:` registry here just mirrors the resulting keys + summaries (emoji prefix included, since it is part of the summary text).

- To add/remove/modify an epic **category** (emoji, label, decision tree) → use **`/managing-epic-taxonomy`**, then reflect the changed summaries here.
- To keep the manifest registry in step with what epics live in Jira → use the reconcile workflow below.

### Reconcile the registry against live Jira

The **source of truth for what epics exist** is Jira itself:

```bash
ebjira epic list --project EARL
```

After manual Jira changes (epics created, renamed, re-emoji'd, retired), reconcile the `epics:` block **by hand** so each entry matches live 1:1:

1. Run `ebjira epic list --project EARL`.
2. Hand-edit the `epics:` block so every entry's `key` + `summary` (**including the emoji prefix**) matches the live epic exactly:
   - **Add** entries for epics present in Jira but missing from the block.
   - **Update** summaries that have drifted (renames, re-classifications).
   - **Mirror the emoji prefix** as it appears in the live summary.
   - Remove entries for epics that no longer exist (confirm with the user first).

> **Why by hand:** `bin/ebjira manifest diff` cannot currently see the gallery manifest — the Docker wrapper does not mount the gallery repo, so `manifest diff`/`apply` do not operate on this `epics:` block. Reconcile the epics list manually against `ebjira epic list` output rather than relying on `manifest diff`.

### Where the canonical manifest physically lives

The canonical manifest for project **EARL** is:

```
/Users/omareid/Workspace/git-earlbear/earlbear-gallery/manifests/jira/manifest.yaml
```

The relative path `manifests/jira/manifest.yaml` used throughout this skill resolves there when commands are run from the **earlbear-gallery** repo root.

---

## Important Notes

- **The manifest is a living document.** It is listed in `CLAUDE.md`'s living documents table. Update it whenever statuses, types, components, workflow, labels, board config, or agent config changes.
- **Never edit Jira config directly via the UI** when it is managed by the manifest. Three operations still require the UI: (1) workflow creation (Free tier limitation), (2) board column mapping (no write API), (3) board permissions. After any UI change, run `/conform-jira` to verify the manifest still matches.
- **The `retired.statuses` section** tracks old statuses for migration awareness. When retiring a status, move it there instead of deleting it from the manifest entirely.
- **Breaking changes** (removing statuses that have issues assigned) require `--allow-delete` and an explicit migration plan.
- **Diagrams and manifest travel together.** Always commit generated diagrams alongside the manifest change that produced them.

## Integration with Other Skills

- **`/conform-jira`** — enforces the manifest (diff, apply, diagrams). Use it after editing the manifest here.
- `/refine-working-model` should run `manifest diff` as part of its process health check phase
- `/manage-cloud-agent setup` references the manifest's `agent` section for JQL queues and allowed transitions
- `/add-backlog-item` can read the manifest for valid issue types, components, and labels
- **`/managing-epic-taxonomy`** — owns the epic taxonomy (emoji prefixes + `epic:*` labels in `earlbear-content/jira/EARL/epics/<KEY>.yaml`). This skill's `epics:` registry only mirrors keys + summaries; changes to categories start there. See [4. Epics registry](#4-epics-registry).

> **Sibling skills** listed here live at `earlbear-claude-plugin-marketplace/plugins/jira-manager/skills/<name>/SKILL.md` (bundled at `earlbear-homebrew/plugins-bundle/jira-manager/skills/<name>/SKILL.md`) and are invoked as `/<name>`.
