---
name: creating-jira-issues
description: Systematic workflow for creating Jira issues — search for duplicates and overlaps before creating anything, pick the right issue type, place it under the right parent, and sync to local content repo. Use when creating Jira epics, stories, tasks, or subtasks so the backlog stays clean.
allowed-tools: Bash(./bin/ebjira *), Bash(cd *), Read, Write, Edit, Grep, Glob
---

# Creating Jira Issues

Before creating any Jira issue, **search the existing backlog for overlap**. Most "new" work is actually an existing issue that needs re-scoping, re-parenting, or a description update. Creating duplicate issues fragments the backlog and makes it hard to reason about what's actually planned.

## Mental model: two layers

The EarlBear ecosystem has two distinct layers of content:

- **Jira = work tracking.** Mutable, time-bound, small. "What are we doing, who owns it, is it done?"
- **Drive docs (`earlbear-content/gdocs/`) = reference content.** Stable, long-lived, can be large. "How do we think about X, what's the canonical approach?"

**Before creating a Jira issue, ask: is this actually work, or is it reference content?**

- If the "issue" is really a playbook, spec, checklist, or framework that other work will reference repeatedly → **it belongs in a Drive doc, not a Jira ticket.** Create/update the doc first, then (only if there's actual implementation work) create a Jira issue that `specifies` the doc.
- If the "issue" is a bounded unit of work with an end state → Jira ticket. Keep the description to problem statement + acceptance criteria. Don't dump reference content into it.

## The Rules

1. **Search before creating.** If you're about to create more than one issue, search is mandatory. Repurpose over recreate.
2. **Work vs reference content.** If the thing you want to create is really reference material, put it in `earlbear-content/gdocs/knowledge-base/` and only create a Jira ticket for actual implementation work.
3. **Pick the right type for the hierarchy.** Jira only allows `Epic → Story/Task/Bug/Deliverable → Subtask`. Nothing at the middle level can parent anything else at the middle level.
3a. **Size your deliverables.** Large deliverables (multiple user-facing capabilities) → create as Epic with Stories underneath. Small deliverables (single bounded output) → create as Deliverable with Sub-tasks underneath. See the sizing rule in Step 3 below.
3b. **Classify your epics.** Every Epic must have an emoji prefix in the summary AND a label, picked from 6 mutually-exclusive categories: 📦 Deliverable, 🏢 Function, 📅 Initiative, 🗑️ Bin, 🦴 Stubs, 🤖 Generated. See the Epic Classification section in Step 3 below. Never manually create 🤖 Generated epics.
4. **Place under a parent from day one.** Orphan issues are invisible in roadmaps.
5. **Sync locally after creating.** The content repo is the audit trail — pull after every batch of changes.
6. **Use dry-run for re-parenting.** Always preview `sync push --dry-run` before applying.
7. **Jira never references local files.** Comments, descriptions — if you need to point humans at the canonical content, link to the Drive doc URL, never the local `gdocs/...` path.
8. **Link docs → tickets via `specifies`, not tickets → docs.** If a ticket has a canonical spec in the knowledge base, the doc's frontmatter should list the ticket in its `specifies:` field. No "related docs" list in the Jira description.
9. **Keep ticket descriptions lean.** Problem statement, acceptance criteria, links. If the description is growing past a screenful of text, that's a signal the content should be a Drive doc with the ticket referencing it.
10. **Stories use As-a + Given/When/Then format.** See the Story Format section below. This is mandatory for Story issue types.

## Step 1: Search existing backlog

Before creating anything, read the already-synced Jira content in `earlbear-content/jira/EARL/` and search for overlap.

```bash
# Make sure local state is current
./bin/ebjira sync pull --project EARL
```

Then search the content repo by keyword:

```bash
# From earlbear-content/
grep -l -i "knowledge base\|reference docs\|playbook" jira/EARL/epics/
grep -l -i "ecommerce fundamentals\|ABCD" jira/EARL/stories/
```

For broader searches, use the Explore agent with "very thorough" level to scan all YAML files for keyword matches in summaries, descriptions, and comments.

**What you are looking for:**
- Direct duplicates (same summary, near-identical description)
- Adjacent issues that cover part of the scope
- Issues in the wrong epic that should be re-parented
- Issues with stale descriptions that need refreshing instead of net-new creation

## Step 2: Decide — create, re-parent, or update?

Based on what the search turned up:

| Situation | Action |
|---|---|
| Exact match exists, right parent, right type | Update description/acceptance criteria only |
| Exact match exists, wrong parent | Re-parent it (see Step 5) |
| Partial match, different scope | Create new, but reference the related issue in description |
| No match | Create new (Step 3) |
| Multiple small issues that should be one | Consolidate: re-parent children, update one as canonical, delete/close the rest |

**Surface the overlap to the user before acting on it.** Do not silently merge or delete issues.

## Step 3: Pick the right type and parent

Jira hierarchy (this project):

```
Epic
├── Story / Feature / Deliverable / Task / Bug
│   └── Sub-task
```

**Nothing at the middle level can parent anything at the middle level.** Stories can't have Story children. Deliverables can't have Story children. Everything in the middle is a sibling of everything else in the middle.

### Epic classification (mandatory)

Every Epic must be classified into exactly one of 5 categories. The category sets both an **emoji prefix in the summary** (visible everywhere) and a **label** (filterable via JQL).

| Category | Emoji | Label | What it is |
|---|---|---|---|
| **Deliverable** | 📦 | `epic:deliverable` | Finite project with a concrete end state |
| **Function** | 🏢 | `epic:function` | Ongoing organizational capability or business activity |
| **Initiative** | 📅 | `epic:initiative` | Time-bound strategic push with a thesis but no fixed end state |
| **Bin** | 🗑️ | `epic:bin` | Human-curated dumping ground for **heterogeneous** accumulated artifacts (mixed shapes — junk drawer) |
| **Stubs** | 🦴 | `epic:stubs` | **Homogeneous** container for thin placeholder tickets awaiting scoping. Every child is a stub. Hidden from boards. |
| **Generated** | 🤖 | `epic:generated` | **Agent-generated** container for automated outputs |

**Decision tree (use in order):**

1. Is there a concrete end state? ("When X, Y, Z are done, this Epic closes") → **📦 Deliverable**
2. Is this an organizational capability or recurring business activity the team operates continuously? → **🏢 Function**
3. Is this a time-bound strategic push with a thesis but no fixed end state? → **📅 Initiative**
4. Is this a homogeneous container of thin placeholder tickets awaiting scoping? → **🦴 Stubs**
5. Is this a place where humans drop heterogeneous accumulated artifacts (logs, feedback) without work tracking? → **🗑️ Bin**
6. Is this a container for automated agent output, where items are auto-created? → **🤖 Generated**

**Critical rules:**

- **Categories are mutually exclusive.** Pick exactly one — the strongest match. If two seem to apply, the description isn't sharp enough; refine it until one clearly wins.
- **Always include the emoji in the summary at creation time.** Don't add it after — the emoji-less version causes pull churn. Example: create as `📦 Knowledge Base`, not `Knowledge Base` (then add the emoji later).
- **Always set the label at creation time.** Use `--labels epic:deliverable` (or whichever category) when creating via `ebjira issue create`.
- **Don't manually create 🤖 Generated Epics.** They're auto-created by the agent infrastructure (e.g., Watson creating its own Check-In epic). If you find yourself wanting to manually create one, you should be writing the agent that generates it instead.
- **Use the `managing-epic-taxonomy` skill to add/remove/modify categories.** Don't edit the taxonomy directly without going through that skill — it ensures CLAUDE.md, this skill, and existing epics all stay in sync.

**Examples from the current backlog:**

- 📦 Deliverable: Knowledge Base, Internal Agents, Launch EarlBear, Automated Store Development
- 🏢 Function: Client Discovery, Store Analysis, Outreach Pipeline, Sales Enablement, Platform & Infrastructure
- 📅 Initiative: Launch EarlBear, Tech Designs, Business Strategies, Proof of Concepts
- 🤖 Generated: Check-In / Check-Out (Watson auto-creates a daily subtask)

### Deliverable sizing rule (mandatory)

**Before creating a Deliverable, decide: is this large or small?**

- **Large deliverable** (contains multiple user-facing capabilities, each a separate `As a [role], I want ...`) → **create as an Epic**, not a Deliverable. Put Stories underneath for each capability. Each Story can have Sub-tasks for its implementation steps.
- **Small deliverable** (single bounded output, produced by a small number of implementation steps) → **create as a Deliverable**, with Sub-tasks directly underneath.

**Decision test:** "Can I list multiple user-facing capabilities that each deserve their own `As a [role], I want...` story?"
- Yes → this is actually an Epic. Create it as an Epic.
- No → it's a real Deliverable. Create it as Deliverable + Sub-tasks.

### Examples of sizing

| Thing | Size | Type | Children |
|---|---|---|---|
| Shopify Agent (discovery, execution, monitoring, rollback) | Large | Epic | Stories (one per capability) |
| Ecomm Agent (crawl, score, hypothesize) | Large | Epic | Stories (one per capability) |
| Knowledge Base (fundamentals, anatomy, playbook, SEO, ...) | Large | Epic | Stories (one per topic) |
| Website Example Catalog (single curated list) | Small | Deliverable | Sub-tasks (curate, screenshot, publish) |
| Pitch Email draft | Small | Deliverable | Sub-tasks (draft, review, send) |
| Vision Document | Small | Deliverable | Sub-tasks (research, write, circulate) |

### Common mistakes

- **Creating a Story and planning to parent other Stories under it.** Stories can't parent Stories. Either make it an Epic from the start, or use labels for grouping.
- **Creating a giant Deliverable with 20 implementation steps.** That's an Epic in disguise. Convert it.
- **Creating an Epic for a single artifact.** That's a Deliverable. Don't over-structure.
- **Mixing reference content with work tracking.** See Rule #2 — if it's a playbook/spec/framework, put it in `earlbear-content/gdocs/` instead of Jira.

Before creating, know:
- **Type:** Epic, Story, Task, Bug, Sub-task, Feature, Deliverable
- **Parent:** an existing Epic key (required unless this IS an epic)
- **Priority:** Highest, High, Medium, Low, Lowest
- **Component:** check `jira/EARL/.pull-metadata.json` or `./bin/ebjira project components EARL`
- **Summary:** imperative mood, specific (not "Improve X", say "Add strikethrough price on PDP")

## Story format (mandatory for Story issue type)

**Every Jira Story must follow the As-a + Given/When/Then format.** This is tenet #10 from `earlbear-content/CLAUDE.md`.

### Summary line

```
As a [role], I want to [goal] so that [value]
```

Examples:
- ✅ `As an Ecomm Analyst agent, I want a canonical ABCD audit framework so that my recommendations are grounded in proven principles`
- ✅ `As a store owner, I want the Shopify Agent to auto-create discount codes during slow periods so that I can recover revenue without manual intervention`
- ❌ `Ecommerce Fundamentals Knowledge Pack` (not a user story — describes an artifact, not a capability)
- ❌ `Fix checkout bug` (this is a Bug, not a Story — use Bug type instead)

### Description template

```markdown
## User Story

As a [role],
I want [capability]
so that [business value].

## Acceptance Criteria

### Descriptive title of the happy path [EARL-NNN]
Given [precondition / initial state]
When [action / event]
Then [expected outcome]
And [additional observable outcome]

### Descriptive title of an edge case [EARL-NNN]
Given [...]
When [...]
Then [...]
```

### Rules for acceptance criteria

- **Use descriptive titles, not numbered scenarios.** `### Framework covers all four pillars [EARL-185]` — not `### Scenario 1`.
- **Always include the story's Jira key in brackets at the end of each scenario title.** This makes scenarios greppable by key when they get moved, split, or referenced from other docs. When you create a new story, put `[NEW]` in the brackets and replace it with the real key after creation.
- **Given/When/Then are verifiable states or actions.** Not opinions, not aspirations. "Given the store is analyzed, When the agent generates a report, Then the report contains a shopability score between 0 and 100" — not "Then the report is good."
- **One scenario per testable outcome.** Don't cram multiple flows into one scenario.
- **Each story should have 2-4 scenarios minimum.** Cover: happy path, at least one edge/error case, and at least one "traceability" scenario (how we'd know this was done).
- **Use `And` to chain multiple Thens or Givens** within a scenario, not to mash scenarios together.

### Applies to

- ✅ **Story** — mandatory
- ✅ **Feature / Deliverable** — use the same format (these are story-like in this project)
- ❌ **Epic** — epics are thematic containers, not user-facing work. Epic descriptions can be freeform vision statements.
- ❌ **Task** — internal/tech work. Use problem statement + acceptance criteria (no As-a line needed).
- ❌ **Sub-task** — implementation details. Reference the parent story's criteria.
- ❌ **Bug** — problem + reproduction + expected behavior. Not a user story.

### Example — full story

**Summary:** `As an Ecomm Analyst agent, I want a canonical ABCD audit framework so that my store analyses are grounded in proven principles`

**Description:**
```markdown
## User Story

As an Ecomm Analyst agent,
I want a canonical ABCD (Acquisition, Browsing, Cart, Dead Ends) audit framework
so that my store analyses are grounded in proven principles instead of first-principles guessing.

## Acceptance Criteria

### Framework is accessible as a Drive doc [EARL-185]
Given the ABCD framework is migrated to gdocs/knowledge-base/ecommerce-fundamentals/abcd-of-ecommerce.md
When an agent reads the doc's frontmatter
Then the agent_hints field provides 2-3 sentence summaries
And the tags field enables discovery via label matching
And the specifies field lists implementation tickets

### Framework covers all four pillars [EARL-185]
Given an Ecomm Analyst is auditing a Shopify store
When the agent walks the ABCD checklist
Then Acquisition has concrete signals to score (value prop, trust, conversion path)
And Browsing has concrete signals (navigation, filtering, search, product discovery)
And Cart has concrete signals (friction, clarity, urgency)
And Dead Ends has concrete signals (404s, empty search, out-of-stock handling)

### Framework output is actionable [EARL-185]
Given an agent completes an ABCD audit
When the agent produces a report
Then each scored pillar includes 1-3 specific recommended actions
And each action includes expected impact (conversion uplift estimate)
And each action maps to a Shopify Agent capability (ebshop command)
```

## Step 4: Create

```bash
./bin/ebjira issue create \
  --project EARL \
  --type Story \
  --summary "Your specific title" \
  --description "Clear problem statement. What, why, acceptance criteria." \
  --parent EARL-184 \
  --priority High
```

The response includes the new key (e.g. `EARL-192`). Record it.

For **batch creation** of multiple related issues, chain with `&&` or create a small shell loop — but do a fresh search for each one to avoid creating issues that overlap each other.

## Step 4.5: Transition through the workflow

New issues are created in `Open`. The EARL workflow uses **non-obvious transition names** — the target status is not the same as the transition name, and most target statuses require walking through 1–2 intermediate steps. Don't assume a status is missing just because no direct transition matches it.

### EARL workflow graph

```
Open  ──Picked──▶  Prioritized  ──Started──▶  Planning  ──Plan complete──▶  In Progress  ──Submit──▶  Review  ──Approve──▶  Done
                          ▲                        │
                          └────De-prioritized──────┘
```

| From status | Transition name | To status |
|---|---|---|
| Open | Picked | Prioritized |
| Prioritized | Started | **Planning** |
| Prioritized | De-prioritized | Open |
| Planning | (varies) | In Progress |

**Key gotcha**: to reach `Planning`, you must first `Picked` (Open→Prioritized), then `Started` (Prioritized→Planning). There is no direct `Open → Planning` transition.

### How to discover transitions

`./bin/ebjira issue transitions <KEY>` lists **only the transitions available from the current status**. To find a path to a target status, walk the graph:

```bash
./bin/ebjira issue transitions EARL-194           # see what's available now
./bin/ebjira issue transition EARL-194 Picked     # advance one step
./bin/ebjira issue transitions EARL-194           # see what's now available
./bin/ebjira issue transition EARL-194 Started    # advance to Planning
```

If a user asks for a status (e.g. "move it to Planning") and the immediate transition list doesn't show it, **don't assume the status doesn't exist** — walk the graph above. Only ask the user for clarification if you reach a dead end after walking all reachable states.

### Don't transition via YAML

The `status:` field in the local YAML is read-only from the sync's perspective — `sync push` does not move issues through transitions. Always use `./bin/ebjira issue transition` for status changes, then `sync pull` to refresh local state.

## Step 5: Re-parent existing issues (the two-commit dance)

When consolidating overlap, re-parent via the content repo, not direct CLI calls. This captures intent in git before the push.

```bash
# 1. Make sure local is current
./bin/ebjira sync pull --project EARL

# 2. Edit the YAML — change the 'parent:' field
# jira/EARL/stories/EARL-101.yaml:
#   parent: EARL-185    (was EARL-2)

# 3. Pre-push commit captures INTENT
cd earlbear-content
git add -p jira/
git commit -m "intent: re-parent EARL-101 under EARL-185 (Knowledge Base consolidation)"

# 4. Preview the push
cd earlbear-clis
./bin/ebjira sync push --project EARL --dry-run

# 5. Push for real
./bin/ebjira sync push --project EARL

# 6. Re-pull and commit POST-SYNC state
./bin/ebjira sync pull --project EARL
cd earlbear-content
git add -A jira/
git commit -m "sync: re-parented EARL-101 to EARL-185"
```

**Why the two-commit dance?** If the push partially fails or Jira rejects/transforms something (e.g. type hierarchy violations), `git diff HEAD~2 HEAD~1` shows exactly what you meant to do vs what actually landed.

## Step 6: Common failures and how to avoid them

### "Given parent work item does not belong to appropriate hierarchy"

You tried to parent a Story under another Story (or similar). Fix:

```bash
# Convert the intended parent to an Epic
./bin/ebjira issue update EARL-185 --fields '{"issuetype": {"name": "Epic"}}'

# Then retry the re-parent via sync push
```

After converting a Story to an Epic, the next `sync pull` will write the new YAML under `epics/` but **the old file in `stories/` is not auto-deleted**. You must `rm stories/EARL-185.yaml` and `git add -A` to capture the rename.

### Partial push failure

`sync push` processes issues in alphabetical order and may fail mid-batch. Re-run to retry the unpushed ones:

```bash
./bin/ebjira sync push --project EARL --dry-run  # shows what's still pending
./bin/ebjira sync push --project EARL
```

### Forgot to search first, created a duplicate

Don't delete the duplicate immediately. Check which one has comments, attachments, or inbound links first, then migrate content from the doomed one to the canonical one, then delete:

```bash
./bin/ebjira issue view EARL-DUPE              # inspect
./bin/ebjira issue delete EARL-DUPE --confirm  # only after migration
```

## Step 7: Cross-link to knowledge base if applicable

If the new issue relates to content that lives in a Drive doc (via `earlbear-content/gdocs/`), add the cross-link:

```bash
./bin/ebdocs sync link --jira EARL-192 --doc gdocs/knowledge-base/runbooks/some-guide
```

This updates `links.yaml` at the content repo root. Optionally post a Jira comment with the Drive link so humans browsing Jira can follow it:

```bash
./bin/ebjira issue comment EARL-192 "Reference: https://docs.google.com/document/d/..."
```

## Step 8: Grooming existing issues — the lint → triage → reshape loop

Use this loop when an audit (or `ebjira lint`) surfaces issues with structural gaps. The goal is to bring existing tickets into compliance with the rules above without inventing requirements.

> **Running a full backlog sweep?** This step covers the **per-issue** loop. For **campaign-level** grooming (snapshots, waves, migration topology, stop conditions), use the companion skill `grooming-jira-issues/SKILL.md`.

### Detect

```bash
./bin/ebjira lint issues --project EARL --rule structure --format table
./bin/ebjira lint issues --project EARL --key EARL-156 --format table  # single issue
```

The structure rule detects: `missing-user-story`, `missing-gwt`, `wall-of-paragraphs`, `label-paragraph`, `bare-enumeration`, `arrow-flow`. Each finding is annotated with `severity` (`error` / `warn` / `info`) and an excerpt to locate it.

### Triage — every finding maps to one of three actions

Before reshaping, classify each flagged issue. Do this **before** touching the YAML.

| Class | Signal | Action |
|---|---|---|
| **Reshape in place** | Description has good content, just no headings/bullets/As-a wrapper. Examples: prose with `Label:` paragraphs, bare `(1)..(8)` enumerations, arrow flows in prose. | Promote labels to `##` headings, convert enumerations to `-` lists, wrap in As-a + GWT. **Preserve every original requirement.** |
| **Rewrite** | The story is genuine work-tracking but the description is sparse / missing the user-story framing. The work is real, the words just need to be written. | Write the As-a line and GWT scenarios from the existing context (parent epic, comments, related issues). Confirm with the user before pushing — this is the only class where new prose is created. |
| **Migrate to Drive** | The "ticket" is reference content masquerading as work — names like "Customer Personas", "Credibility Statement", "Email Follow-Up Timeline", or "Tech Design / Strategy" Deliverables. These describe an artifact, not a capability. | Move the content to `earlbear-content/gdocs/knowledge-base/...`. If implementation work remains, create a small Story that `specifies` the doc and close/delete the original ticket. **Never reshape these into As-a/GWT — that's forcing a square peg.** |

**Rule of thumb**: if you can't write a credible `As a [role], I want [capability] so that [value]` line from the existing description, the issue is probably reference content (migrate) or needs scope clarification (rewrite with the user), not a reshape.

### Reshape (the EARL-156 pattern)

For issues classed as "reshape in place":

1. **Read the YAML** at `$CONTENT_DIR/jira/<PROJECT>/<type>/<KEY>.yaml`. Note every requirement before touching anything. The `summary_ai:` block (if present) is auto-managed by `ebjira issue summarize` — never hand-edit it; reshaping `summary` or `description` will mark it stale and the next grooming Wave 0 will refresh it.
2. **Identify the structural transformations:**
   - `Label:` paragraphs → `## Label` headings
   - `(1)..(N)` or numbered prose → `-` markdown bullets
   - Arrow-flow prose (`A → B → C`) → bullet list (or fenced ```mermaid``` block if it's a real diagram)
   - Wall of paragraphs → grouped sections under `##` headings
3. **Wrap in the canonical template** (see "Story format" above): `## User Story` block + `## Acceptance Criteria` with descriptive `### scenario [EARL-NNN]` titles. Derive scenarios from the existing prose — do not invent requirements that weren't in the source.
4. **Preserve auxiliary content** in named sections (`## Context`, `## Workflow change`, `## Recommendation`, etc.) above the Acceptance Criteria. Don't delete content because it doesn't fit GWT.
5. **Re-lint locally** at `--severity warn` to confirm zero blocking findings. Info-level findings (e.g. arrow-flow) are acceptable when intentional.
6. **Two-commit dance** as in Step 5: pre-push intent commit → `sync push --dry-run` → `sync push` → re-pull → post-sync commit.
7. **Round-trip verify**: pull the issue back and re-run lint. If structure survives, the reshape is durable.

### Constraints (do not violate)

- **Never invent requirements during reshape.** If a GWT scenario can't be derived from the existing description without adding new behavior, leave a `<!-- needs-human: ... -->` marker and stop. Don't push.
- **Don't reshape Deliverables that are really Drive content.** Tech Design / Strategy / Vision Deliverables have lint findings because they shouldn't be Jira tickets at all. Migrate them, don't dress them up.
- **Don't reshape Tasks, Bugs, Sub-tasks.** The story format only applies to Stories (and story-like Features/Deliverables). The lint command exempts Sub-tasks and Bugs already.
- **Don't batch-reshape silently.** Surface the triage classification to the user (which issues are reshape, which are migrate, which are rewrite) and get sign-off on the migration list before mass changes.

## Checklist for every issue creation session

- [ ] Pulled latest Jira state (`./bin/ebjira sync pull`)
- [ ] Searched for overlap by keyword (grep + Explore agent for broad searches)
- [ ] Surfaced overlap findings to the user before acting
- [ ] Decided create vs re-parent vs update for each candidate
- [ ] Confirmed hierarchy is legal (Epic parent for Stories, etc.)
- [ ] Used dry-run before any `sync push`
- [ ] Did the two-commit dance for re-parenting
- [ ] Cross-linked to Drive docs via `links.yaml` if applicable
- [ ] Final `sync pull` + commit to capture post-sync state
