---
name: managing-epic-taxonomy
description: Add, remove, rename, or reclassify epic categories in the taxonomy. Ensures mutual exclusivity, visual distinctness, downstream sync, and proper backfill of existing epics. Use when modifying the epic taxonomy itself or auditing existing classifications.
allowed-tools: Bash(./bin/ebjira *), Bash(cd *), Read, Write, Edit, Grep, Glob
---

# Managing the Epic Taxonomy

This skill is the **only** sanctioned way to change the epic classification taxonomy. The taxonomy is a load-bearing convention: it shows up in epic summaries (emoji prefix), Jira labels, three different doc locations, and the day-to-day mental model people use to triage work. A sloppy edit fragments the backlog and silently breaks the decision tree.

If you are about to add, remove, rename, or reclassify a category — or just want to audit the current state — read this whole file first, then pick a workflow.

---

## 1. The current taxonomy (canonical)

This table is the single source of truth. When the taxonomy changes, **this table must be updated as part of the same change** along with all downstream artifacts listed in section 5.

| Category | Emoji | Label | Purpose |
|---|---|---|---|
| Deliverable | 📦 | `epic:deliverable` | Finite project with a concrete end state. Has a definition of done. Eventually closes. |
| Function | 🏢 | `epic:function` | Ongoing organizational capability or business activity. Never closes. Holds the recurring work of "running X". |
| Initiative | 📅 | `epic:initiative` | Time-bound strategic push. Has a thesis and a window of focus, but no fixed end state — spawns deliverables as the direction crystallizes, or pivots/dies. The calendar emoji emphasizes the temporal nature: initiatives have a window, not permanence. |
| Bin | 🗑️ | `epic:bin` | Human-curated dumping ground for **heterogeneous** accumulated artifacts (mixed shapes — logs, loose ideas, feedback inbox) that don't yet warrant their own structure. Explicitly low-rigor. Contrast with Stubs, which is homogeneous. |
| Stubs | 🦴 | `epic:stubs` | Homogeneous container for thin placeholder tickets awaiting scoping. Every child is the same shape: a stub (no user story, no GWT, no attachments, <200 char body). Lifecycle = scope-or-retire. Hidden from planning boards via JQL filter. |
| Generated | 🤖 | `epic:generated` | Agent-auto-created container. **Never** created by humans. Used by automation when it needs an epic to attach generated stories to. |

**Rules that always apply:**

- Categories are **mutually exclusive**. Every epic belongs to exactly one. The decision tree in section 4 must produce a single answer for any epic.
- Every epic carries **both** signals: the emoji prefix in its `summary` field, AND the matching label in its `labels` list. These must agree.
- Humans never create 🤖 Generated epics. Only agents do, and only when they need a parent for auto-generated work.

---

## 2. The 5 workflows

Pick the workflow that matches what the user is asking for. If unclear, ask.

### Workflow A — Add a new category

Use when the user proposes a new epic category.

1. **Capture the proposal.** Get from the user:
   - Proposed name (one word, capitalized)
   - One-sentence purpose
   - 2–3 example epics that would live here
2. **Run the mutual-exclusivity test (section 4).** Walk the decision tree against the user's examples. If any example resolves to an existing category, the new category overlaps. Tell the user which existing category covers it and ask them to either refine the proposal or pick the existing one. **Do not proceed until the new category is clearly disjoint from all existing ones.**
3. **Propose 3–5 candidate emojis.** Use the criteria in section 3. Show them inline so the user can see them rendered. Briefly note why each one was chosen and which existing emoji it is most likely to be confused with.
4. **User picks one emoji.** If they reject all five, propose another batch. Do not accept an emoji that fails any criterion in section 3.
5. **Propose the label.** Format: `epic:<lowercase-name>`. Confirm with the user.
6. **Coordinated edit.** In a single logical change, update all files in the section 5 checklist. The canonical table in this very skill file must be updated too.
7. **Do NOT touch existing epics.** Adding a category does not reclassify anything. Existing epics keep their current category. If the user wants to move some epics into the new category, that is a separate "Reclassify a single epic" workflow run per epic.
8. **Commit with intent message.** First commit: `taxonomy: add <Name> category (<emoji> epic:<name>)`. No sync push needed since no Jira state changed.

### Workflow B — Remove a category

1. **Confirm the target.** Ask the user which category to remove and why.
2. **Scan existing epics.** Run:
   ```bash
   cd /Users/omareid/workplace/git/earlbear-content
   grep -l "epic:<target>" jira/EARL/epics/*.yaml
   ```
   List every match.
3. **If any matches exist, require a migration target.** Ask the user which existing category each epic should map to. Default is "all to the same target", but allow per-epic overrides. Do not proceed without an answer for every match.
4. **Pre-push intent commit.** Commit the migration plan as a doc edit (e.g. update this skill's table to mark the category as REMOVED-PENDING-SYNC). Message: `taxonomy: remove <Name> category — migrate N epics to <Target>`.
5. **Apply migration to local YAMLs.** For each affected epic:
   - Replace the emoji prefix in `summary`
   - Replace `epic:<old>` with `epic:<new>` in `labels`
6. **Push to Jira via the sync workflow** (see `creating-jira-issues` skill). Then pull back so any Jira-side metadata (updated timestamps etc.) lands locally.
7. **Post-sync commit.** Commit the updated YAMLs and the final taxonomy doc edits removing the category entirely. Message: `taxonomy: remove <Name> — post-sync`.
8. **Update all section 5 doc artifacts** to drop the category in the post-sync commit.

### Workflow C — Rename a category (e.g. Theme → Initiative)

This is the highest-risk workflow because it touches the most artifacts.

1. **Confirm scope.** Get from the user:
   - Old name → new name
   - Is the emoji also changing? (old emoji → new emoji)
   - Is the label also changing? (`epic:old` → `epic:new`)
2. **Scan existing epics.** Find every YAML using either the old emoji prefix or the old label:
   ```bash
   cd /Users/omareid/workplace/git/earlbear-content
   grep -l "epic:<old>" jira/EARL/epics/*.yaml
   grep -l "<old-emoji>" jira/EARL/epics/*.yaml
   ```
   The two lists should match. If they don't, you've found existing inconsistencies — surface them and resolve before proceeding (run the audit workflow on those files first).
3. **Pre-push intent commit.** Update the canonical table in this skill plus the other section 5 doc artifacts to reflect the rename. Message: `taxonomy: rename <Old> → <New> (intent)`.
4. **Apply to YAMLs.** For each affected epic:
   - In `summary`: replace the leading emoji (old → new) if emoji is changing
   - In `labels`: replace `epic:<old>` with `epic:<new>` if label is changing
5. **Sync push to Jira.** Use the standard sync workflow.
6. **Post-sync commit.** Commit the rewritten YAMLs. Message: `taxonomy: rename <Old> → <New> — post-sync`.
7. **Run the audit workflow** (workflow E) to confirm zero stragglers reference the old emoji or old label anywhere.

### Workflow D — Reclassify a single epic

Use when a specific epic is in the wrong category.

1. **Get the epic key and target category.** Validate the target category exists in the canonical table (section 1). If not, refuse and offer the "add a new category" workflow.
2. **Locate the YAML.** `jira/EARL/epics/<KEY>.yaml`
3. **Read it.** Confirm the current emoji prefix and label match each other (otherwise this epic was already inconsistent — note it).
4. **Edit:**
   - `summary`: swap the leading emoji
   - `labels`: replace the old `epic:*` with the new one (do not touch other labels)
5. **Pre-push intent commit.** Message: `EARL-XXX: reclassify <Old> → <New>`.
6. **Sync push** to Jira via the standard workflow.
7. **Post-sync commit** with any Jira-side changes that came back on pull.

### Workflow E — Audit existing classifications

Run this whenever the taxonomy changes, and periodically as hygiene.

1. **List all epic YAMLs.**
   ```bash
   ls /Users/omareid/workplace/git/earlbear-content/jira/EARL/epics/*.yaml
   ```
2. **For each file, check:**
   - `summary` starts with one of the canonical emojis from section 1
   - `labels` contains exactly one `epic:*` label
   - The emoji and the label correspond to the **same** category (no 📦 with `epic:function`)
   - The category exists in the canonical table (no orphan emojis or labels from removed/renamed categories)
3. **Build an inconsistency report** with one row per problem:
   - File path
   - Current summary prefix
   - Current `epic:*` label(s)
   - Diagnosis (missing prefix / missing label / mismatch / unknown category / removed category)
4. **Present the report to the user.** Do not auto-fix. Each row likely needs the user to pick a target category, after which you can run workflow D per epic.

---

## 3. Emoji selection criteria

When proposing emojis for a new (or renamed) category, every candidate must pass **all** of these:

1. **Visually distinct from every existing taxonomy emoji.** Hold the candidate next to the section 1 table. If two emojis read as similar at a glance (same dominant color, same silhouette, same metaphor family), reject. Example failure: 📦 (box) vs 📫 (mailbox) — both small brown rectangles.
2. **Renders cross-platform.** Must be a single Unicode codepoint (or stable ZWJ sequence) that renders on macOS, iOS, GitHub web, Slack, and Linux terminals. Avoid recent additions (anything from the last ~2 Unicode releases) and skin-tone modifiers.
3. **Single glyph, no variation selectors that change meaning.** Avoid emojis whose presentation flips between text-style and emoji-style depending on platform.
4. **Semantic match.** A reader who has never seen the taxonomy should be able to guess the category from the emoji alone with ≥50% accuracy. If you have to explain it, pick a different one.
5. **Not already used elsewhere in the EarlBear ecosystem.** Quick check: grep `earlbear-content/CLAUDE.md` and the workstream emojis in NotePlan plans. Avoid colliding with workstream icons.
6. **Not an obvious "joke" emoji.** No 💩, no 🦄, no party hats. The taxonomy is operational infrastructure.

When you present candidates, format them as a small table:

| Candidate | Reads as | Closest existing | Risk |
|---|---|---|---|
| 📅 | calendar / time-bound | (none) | low |
| 🎯 | target / goal | 📦 (both "outcome-y") | medium |
| ... | ... | ... | ... |

---

## 4. Mutual exclusivity test (the decision tree)

Apply this tree to any epic — proposed or existing — to determine its single category. If the tree produces more than one answer, the taxonomy is broken and must be fixed before adding the new category.

```
Was this epic created by an agent without a human in the loop?
├── YES → 🤖 Generated. STOP.
└── NO → continue

Is this a container whose children are ALL thin placeholder tickets awaiting
scoping (homogeneous — every child has no user story, no GWT, no attachments,
lifecycle = scope-or-retire)?
├── YES → 🦴 Stubs. STOP.
└── NO → continue

Is this a curated dumping ground for HETEROGENEOUS accumulated artifacts —
mixed shapes like logs, loose ideas, feedback inbox — that don't yet warrant
their own structure? (Junk drawer, not stub pool.)
├── YES → 🗑️ Bin. STOP.
└── NO → continue

Does this have a concrete definition of done — a state where you'd close it?
├── YES → 📦 Deliverable. STOP.
└── NO → continue

Is this the recurring "running of" some ongoing capability or business area
that will exist as long as the org exists?
├── YES → 🏢 Function. STOP.
└── NO → continue

Is this a strategic direction or thesis we're exploring, expected to spawn
deliverables over time but with no fixed end state?
├── YES → 📅 Initiative. STOP.
└── NO → the taxonomy does not cover this epic. Either it's miscategorized,
         or you have a genuine gap that justifies a new category.
```

**Test for a proposed new category:** run every existing epic, plus the user's example epics for the new category, through this tree with the new category inserted at the most natural point. If any existing epic now resolves to two answers, the new category overlaps and must be refined or rejected.

---

## 5. Downstream artifacts checklist

**Every** taxonomy change must update these files in lockstep. Missing one creates drift.

- [ ] `/Users/omareid/workplace/git/earlbear-content/CLAUDE.md` — tenet #10, the full definition with decision tree
- [ ] `/Users/omareid/Workspace/git/earlbear-clis/CLAUDE.md` — short reference (around line 90 / tenet #8)
- [ ] `/Users/omareid/Workspace/git/earlbear-clis/.claude/skills/creating-jira-issues/SKILL.md` — Step 3 epic classification decision tree
- [ ] `/Users/omareid/Workspace/git/earlbear-clis/.claude/skills/managing-epic-taxonomy/SKILL.md` — **this file**, the canonical table in section 1 and the decision tree in section 4
- [ ] `/Users/omareid/workplace/git/earlbear-content/jira/EARL/epics/*.yaml` — only when categories are removed, renamed, or reclassified (not when adding)

After editing, grep for the old strings across both repos to confirm zero stragglers:

```bash
grep -rn "epic:<old>" /Users/omareid/workplace/git/earlbear-content /Users/omareid/Workspace/git/earlbear-clis
grep -rn "<old-emoji>" /Users/omareid/workplace/git/earlbear-content /Users/omareid/Workspace/git/earlbear-clis
```

Both should return nothing (except this skill's "Common mistakes" section, if it references the old name historically).

---

## 6. The two-commit dance

For any workflow that touches Jira state (B, C, D), use two commits:

1. **Pre-push intent commit.** Contains the doc edits and the local YAML edits describing what is about to happen. Message starts with the workflow verb: `taxonomy: rename ...` or `EARL-XXX: reclassify ...`. This commit lives locally so that if the sync fails, the intent is recoverable.
2. **Sync push.** Use the standard `creating-jira-issues` sync workflow to push the YAMLs to Jira and pull back any server-side updates.
3. **Post-sync commit.** Captures whatever the sync brought back (timestamps, server-assigned fields). Message ends with `— post-sync`.

For workflow A (add) and workflow E (audit), only doc edits change, so a single commit is sufficient. Use message `taxonomy: add <Name>` or `taxonomy: audit — N inconsistencies found`.

**Never** combine intent and post-sync into one commit. The split is what lets future readers tell "what we meant to do" from "what Jira agreed to".

---

## 7. Common mistakes

- **Adding an overlapping category.** The most common failure. Always run section 4 against existing epics, not just the new examples. If any existing epic could plausibly move to the new category, the categories overlap.
- **Picking a visually similar emoji.** 📦 / 📫 / 📭 all look the same at small sizes. 📅 / 📆 / 🗓️ all read as "calendar grid". Hold candidates next to the existing set in the actual font you'll see them in (GitHub, Jira, terminal).
- **Forgetting one of the doc locations.** The three CLAUDE.md / skill locations drift constantly because there's no automated check. Use the section 5 checklist literally — open each file, confirm the change is present.
- **Skipping the existing-epic backfill on rename or remove.** If you rename Theme → Initiative in docs but leave epic YAMLs with 🎨 and `epic:theme`, the audit workflow will flag them but day-to-day users will see broken classifications until someone notices.
- **Manually creating a 🤖 Generated epic.** Don't. That category exists exclusively for agents. If you find yourself reaching for it, you actually want one of the other four.
- **Combining intent and post-sync commits.** Hides what changed locally vs what Jira accepted.
- **Editing the canonical table in section 1 without updating section 4 and section 5 artifacts.** They are one change, not three.
- **Touching unrelated `epic:*` labels.** Only swap the one classification label. Leave all other labels (priority, area, etc.) alone.
