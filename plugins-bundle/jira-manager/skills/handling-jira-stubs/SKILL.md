---
name: handling-jira-stubs
description: Classify and process stub Jira tickets — tickets with clear titles but insufficient description to plan or produce the work. Use as Wave S of a grooming campaign or when a stub is discovered mid-session. Drives a scoping conversation with the user and moves stubs in/out of a dedicated per-project Stubs Epic.
allowed-tools: Bash(./bin/ebjira *), Bash(cd *), Bash(git *), Read, Write, Edit, Grep, Glob
---

# Handling Jira Stubs

Sibling skill to `creating-jira-issues` (single ticket creation) and
`grooming-jira-issues` (campaign-level). This skill handles the narrow case of
**stub tickets** — tickets that have a clear title and type but not enough
description to plan or produce the work.

See `docs/grooming/proposal-stub-handling.md` for the full design rationale.

## The model in one paragraph

Every project gets **one dedicated `🦴 Stubs` Epic** (label `epic:stubs`). A
stub sits under its original parent while it's actively being considered. When
it's clearly not ready — no scope, no inputs, no owner — it gets **re-parented
under the Stubs Epic**. Scoping a stub = re-parenting it **out** of the Stubs
Epic to a real parent (and fleshing out the description). Retiring = closing
with `Won't Do`. The Stubs Epic is hidden from planning boards via a one-time
JQL board filter. That's the entire lifecycle — no labels, no custom fields, no
workflow states.

## When to use

- **Wave S of a grooming campaign** — between Wave 0 (summary refresh) and Wave 1
  (reshape). The stub sweep classifies every thin ticket before structural work starts.
- **One-off mid-session** — you're scoping a parent Epic and notice a child ticket
  with a one-sentence description. Run the single-stub path.
- **After creating a backlog of placeholder tickets** — e.g., you brainstormed 10
  Deliverables from a strategy session and now need to turn them into real work.

### When NOT to use

- **The ticket has an attachment that IS the deliverable.** E.g., a Deliverable in
  Review with an HTML template attached is not a stub — the content lives in the
  attachment. (This is the EARL-107 pattern — see the proposal.)
- **The ticket is an Epic.** Epics are thin by design; they're containers, not work.
- **Mid-sprint on an in-progress ticket.** Stub handling is a planning-queue activity,
  not an in-flight one.

## Stub definition (objective criteria)

A ticket is a stub when **all** of the following are true:

1. `len(description.strip()) < 200` characters
2. No `## User Story` heading (Stories only)
3. No `## Acceptance Criteria` heading, no Given/When/Then markers, no checklist
4. No attachments that represent the deliverable
5. `type` is not `Epic` and not `Sub-task` of a parent with AC
6. Parent is not already the `🦴 Stubs` Epic (those are already classified)

The lint rule `stub-ticket` (warn severity) flags any non-exempt ticket matching
the definition **whose parent is not the project's Stubs Epic**. Once re-parented
under the Stubs Epic, the ticket is considered "classified" and the rule goes
silent — the Stubs Epic itself is the queue.

## Lifecycle = parent reassignment

There are exactly three states and they're all expressed via `parent`:

| State | Where it lives | How it got there |
|---|---|---|
| **Active** | Under its real parent Epic | Default — has enough scope to be worked |
| **Deferred** | Under the `🦴 Stubs` Epic | Re-parented during stub sweep (or mid-session) |
| **Retired** | Closed, resolution `Won't Do` | Won't be done — parent irrelevant |

Scoping a deferred stub = fleshing out the description AND re-parenting it back
to its real parent Epic in the same commit. The move out of the Stubs Epic is
the "scoped" signal — no label needed.

## Creating the Stubs Epic per project

Each project needs a one-time Stubs Epic. Run from `/Users/omareid/Workspace/git/earlbear-clis`:

```bash
./bin/ebjira issue create \
  --project <PROJ> \
  --type Epic \
  --summary "🦴 Stubs" \
  --description "Homogeneous container for thin placeholder tickets awaiting scoping. Every child is a stub (no user story, no GWT, no attachments, <200 char body). Lifecycle: scope-or-retire. Hidden from planning boards via JQL filter. See the handling-jira-stubs skill in earlbear-clis/.claude/skills/ for the full model." \
  --labels epic:stubs \
  --priority Lowest
```

Record the returned key — you'll reference it in every re-parent commit and in
the board filter setup.

For EARL, the Stubs Epic is **EARL-196**.

## Board filter setup (manual, one-time per project)

The Stubs Epic must be hidden from planning boards so it doesn't pollute sprint
planning or backlog views. Jira boards don't support a programmatic filter tweak
via our CLI — this is a **manual UI step** done once per project by whoever owns
the board.

1. Open the project board → `Configure board` → `Filter query`.
2. Append: `AND parent != <stubs-epic-key>` (e.g., `AND parent != EARL-196`).
3. Save. Verify a deferred stub no longer appears.

Document the filter edit in the project's README or CLAUDE.md so re-applying it
after board recreation isn't lost. This is **not** automated — treat it as
onboarding for a new project's grooming setup.

## Classification decision tree (scope / defer / retire / dequeue)

For each stub candidate, walk the tree in order. Stop at the first match.

1. **Does the ticket have an attachment, rich comments, or a draft in Review?**
   → **Dequeue.** It's not a stub. Exempt it and move on. (EARL-107 pattern.)

2. **Is there any realistic chance this ticket will ever be picked up?** (ask the
   user if unclear)
   → No → **Retire.** Close with `Won't Do`. Don't bother re-parenting.

3. **Does the stub depend on another unscoped stub or artifact, OR is there not
   enough context for a productive 5-minute scoping conversation?**
   → Yes → **Defer.** Re-parent under the `🦴 Stubs` Epic. Come back when
   upstream context exists.

4. **Is there enough context (parent epic, strategy doc, sibling tickets) for a
   productive 5-minute scoping conversation with the user?**
   → Yes → **Scope.** Queue for the scoping conversation template below. On
   approval, update description AND re-parent to real Epic in the same two-commit dance.

## Scoping conversation template

Runnable by an agent reading the backlog + ticket YAML. Use when a stub is
classified `Scope`.

### Step 1: Read context

```bash
# Pull the ticket YAML
cat "$CONTENT_DIR/jira/EARL/**/EARL-NNN.yaml"
# Read the target parent epic (the real one, not Stubs)
cat "$CONTENT_DIR/jira/EARL/epics/EARL-PARENT.yaml"
# List sibling tickets under the target parent
./bin/ebjira issue list --jql "parent = EARL-PARENT" --format table
```

### Step 2: Draft the agent's best guess

Before asking the user anything, state the agent's current interpretation of the
stub in one sentence. This forces the agent to commit to a reading the user can
correct, instead of asking open-ended questions.

### Step 3: Ask the 5-question template

```
Scoping stub: EARL-NNN — {summary}
Type: {type}  Current parent: {parent} ({parent_summary})
Target parent: EARL-PARENT ({target_parent_summary})
Siblings under target (first 5):
  - {sib}: {sib_summary}
  - ...

My best guess at intent:
  "{one-sentence interpretation}"

Please answer (skip what you don't know — skipped items become needs-human markers):

1. GOAL — In one sentence, what's the end state? What exists when this is done?
2. CONSUMER — Who uses the output? (agent, team member, external prospect)
3. ACCEPTANCE — 2–3 things that must be true to call it done? (rough bullets OK)
4. BLOCKERS — Anything required before work can start? (other tickets, decisions)
5. SIZE — Gut feel: hours, days, or weeks?
```

### Step 4: Draft the promoted description

Using the answers, draft the filled-in description:

- **Story** → As-a + GWT per `creating-jira-issues` template
- **Deliverable** → Problem statement + Acceptance Criteria bullets + Definition of Done
- **Task** → Problem + steps + done criteria

For any skipped question, insert a `<!-- needs-human: {question} -->` marker in
the draft. **Never invent an answer.** If more than one question was skipped, the
ticket stays deferred (keep parent = Stubs Epic) — do not push a half-scope.

### Step 5: Surface the draft for approval

Show the full draft to the user. On approval:

1. Edit the YAML description
2. **Re-parent**: change `parent:` from the Stubs Epic key back to the real Epic key
3. Two-commit dance: intent → push → re-pull → sync commit
4. Re-lint to confirm the stub-ticket rule no longer fires

## Single-stub path (mid-session)

When you find one stub outside a campaign, run the classification tree + scoping
template directly, commit with `stub(PROJ): scope EARL-NNN ({brief})`, and move on.
No sweep table needed for a single ticket.

## Wave S path (campaign sweep)

When running as Wave S of a grooming campaign:

1. **Run the stub lint rule** (warn severity):
   ```bash
   ./bin/ebjira lint issues -p EARL --rule stub-ticket --format json > /tmp/stubs.json
   ```
   The rule flags stub-shaped tickets whose parent is not the project's Stubs
   Epic. Until the rule is implemented, produce the candidate list manually by
   scanning YAMLs for short descriptions without AC.

2. **Classify every stub into scope / defer / retire / dequeue** in a single pass.
   Commit the classification table at `docs/grooming/stub-sweep-<date>.md` before
   acting. Get user sign-off on the table.

3. **Wave S.1 — Defer + Retire batch.** These are cheap and don't require user
   conversation.
   - Defer: re-parent to the Stubs Epic in a single batch commit.
   - Retire: close with `Won't Do` in a single batch commit.
   ```
   stub(EARL): re-parent N stubs under 🦴 Stubs epic EARL-196
   stub(EARL): retire N stubs
   ```

4. **Wave S.2 — Scope batch.** One micro-conversation per stub. Re-parent out of
   Stubs Epic + flesh description in one commit per stub:
   ```
   stub(EARL): scope EARL-105 (Top 3 Issues Report)
   ```

5. **Progress check.** After Wave S, re-run lint. Every stub-shaped ticket should
   now either be closed, parented under the Stubs Epic, or have a real description.
   Scoped stubs re-enter normal grooming at Wave 2.

## Commit message convention

Mirror the `groom(PROJ):` prefix from `grooming-jira-issues` with `stub(PROJ):`.
This lets `git log --grep "^stub("` recover the stub-handling audit trail.

| Action | Message |
|---|---|
| Create Stubs Epic | `stub(EARL): create 🦴 Stubs epic (EARL-196)` |
| Classification table | `stub(EARL): sweep classification table — N scope, M defer, K retire` |
| Batch defer | `stub(EARL): re-parent N stubs under 🦴 Stubs epic EARL-196` |
| Batch retire | `stub(EARL): retire N stubs (EARL-XXX, ...)` |
| Single scope | `stub(EARL): scope EARL-105 (Top 3 Issues Report)` — includes re-parent out of Stubs Epic |
| Dequeue false positive | `stub(EARL): dequeue EARL-107 — has attachment, not a stub` |

When running Wave S inside a campaign, keep `stub(EARL):` as the prefix rather
than folding into `groom(EARL): wave s ...` — the distinct prefix keeps stub
history greppable independent of any single campaign.

## Anti-patterns (do not violate)

- **Don't invent requirements during scoping.** If the user skips a question,
  use a `needs-human` marker and leave the ticket under the Stubs Epic. The
  whole point of the skill is that stubs are under-specified; making up specs
  defeats it.
- **Don't batch-scope silently.** Wave S.2 is one micro-conversation per stub.
  You can batch the defers and retires, but scoping requires the user in the loop
  for each ticket. (Same rule as Wave 2 rewrites in `grooming-jira-issues`.)
- **Don't reshape stubs into As-a/GWT from thin air.** If the description is
  "HTML email template" and you write three GWT scenarios from your imagination,
  you've created false ground truth. Demote to Wave S instead.
- **Don't skip the dequeue check.** Tickets in Review, with attachments, or with
  AI-drafted content are not stubs. Missing this produces false positives and
  undoes real work. Always check `attachments`, `status`, and recent comments
  before classifying.
- **Don't mix stub classification with reshape.** Wave S runs before Wave 1 for
  a reason: scoped stubs re-enter the normal grooming flow with real content.
  Reshaping a stub produces a structurally-correct empty shell.
- **Don't retire without asking.** Retirement is terminal-ish (we close with
  Won't Do). If you're not sure, defer to the Stubs Epic — it's reversible with a
  single `parent:` edit.
- **Don't scope downstream stubs first.** If EARL-B depends on EARL-A and both
  are stubs, scope A first. Scoping B first will produce a draft that has to be
  re-done when A lands.

## Constraints

- **Lifecycle = parent, not label or status.** The Stubs Epic is the queue.
  Don't propose new Jira workflow states or `stub:*` labels for this.
- **Opt-in per project.** Each project needs its own Stubs Epic created
  explicitly. Don't assume all projects want stubs managed this way.
- **Sub-tasks are usually exempt.** A thin sub-task under a scoped parent is
  fine — the parent carries the AC. Only flag sub-tasks when the parent is
  also thin.
- **Epics are exempt, always.** Epics (including the Stubs Epic itself) are
  vision containers by design.
- **Board filter is manual.** Every project with a Stubs Epic needs the JQL
  filter applied in the Jira UI once. Not automated.

## Checklist for every stub-handling session

- [ ] Verified the project's Stubs Epic exists (create if missing)
- [ ] Verified the board filter excludes the Stubs Epic (one-time setup)
- [ ] Pulled latest Jira state (`./bin/ebjira sync pull`)
- [ ] Classified every candidate into scope / defer / retire / dequeue
- [ ] Checked for attachments and Review status before classifying
- [ ] Surfaced the classification table to the user before acting
- [ ] For each Scope: ran the 5-question template, got real answers (not invented)
- [ ] For each skipped question: inserted `<!-- needs-human: -->` marker
- [ ] Two-commit dance for each re-parent (intent → push → sync)
- [ ] Re-lint passes after the sweep
- [ ] Commits use `stub(PROJ):` prefix
