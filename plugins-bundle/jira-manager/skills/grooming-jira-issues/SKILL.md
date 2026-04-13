---
name: grooming-jira-issues
description: Run a structured grooming campaign over the Jira backlog — detect structural and content gaps with `ebjira lint`, triage findings into reshape / rewrite / migrate classes, and drain them in waves without thrashing. Use after a format rule change, before a planning cycle, or whenever a backlog audit surfaces >20 findings.
allowed-tools: Bash(./bin/ebjira *), Bash(./bin/ebdocs *), Bash(cd *), Bash(git *), Read, Write, Edit, Grep, Glob
---

# Grooming Jira Issues

This skill is the **campaign-level companion** to `creating-jira-issues`. Where that skill covers creating one issue correctly, this one covers fixing many existing issues without thrashing.

**When to run a campaign:**
- After a rule change (e.g., adopting As-a/GWT story format) leaves the backlog out of compliance
- Before a planning cycle, so the backlog is honest before sprint planning
- After an audit reveals >20 findings
- Quarterly hygiene

**When NOT to run a campaign:**
- Mid-sprint — changes will conflict with active work
- During a freeze
- While linter rules are still in flux — fixing false positives mid-sweep invalidates the snapshot

## Lint scope rules (read before every campaign)

The structure lint rule must match project tenets. Getting scope wrong produces dozens of false positives and invalidates the baseline.

| Issue type | As-a/GWT required? | Rationale |
|---|---|---|
| **Story** | **Yes** | CLAUDE.md tenet #10 — only Stories carry As-a/Given-When-Then |
| Feature | No — exempt | Features are capability containers, not user-facing increments |
| Deliverable | No — exempt | Deliverables are bounded outputs (docs, reports), not stories |
| Epic | No — exempt | Epics are freeform vision containers |
| Task, Sub-task, Bug | No — exempt | Use their own shapes (checklist, repro steps, etc.) |

Before starting Phase 1, open `jira-cli/src/ebjira/commands/lint.py` and verify `EXEMPT_TYPES` matches the table above. If it doesn't, **fix it first, in a pre-campaign commit**, then snapshot. Do not start the campaign with a known-wrong linter.

**Cautionary tale (2026-04-08)**: A campaign started with baseline = 49 findings. Triage classified 11 Features as "reshape" (Wave 1). When Wave 1 began, the reshaping revealed the Features were flagged only because they lacked `## User Story` / GWT — a Story-only rule the linter was wrongly applying to Features + Deliverables. Stopping mid-campaign and re-baselining collapsed the baseline 49 → 6 (all Stories). 43 false positives eliminated. The fix was a two-line change to `EXEMPT_TYPES`. Cost: one wasted triage pass. Lesson: verify lint scope **before** Phase 1.

## Known Jira workflow + transitions (EARL)

Jira workflow names are project-specific and often counterintuitive. Hardcoded assumptions about transition names break silently when a workflow is edited. This section embeds the verified EARL workflow graph and CLI usage as a fast path so campaigns don't have to rediscover them every run.

**CLI usage.** `./bin/ebjira issue transition` takes the **target status name** (or a transition ID) as a positional arg — not a `--name` flag. The CLI matches the target status and picks the right transition internally.

```bash
./bin/ebjira issue transition EARL-98 Planning           # correct — positional target status
./bin/ebjira issue transition EARL-98 "In Progress"      # quote if multi-word
./bin/ebjira issue transition EARL-98 --comment "..."    # optional comment folds in
```

The CLI also has `--comment` on the transition command, which adds a comment in the same API call. Prefer this over a separate `issue comment` call when the comment is about the transition itself.

**Workflow graph (verified 2026-04-08).** EARL uses a multi-step workflow and many transitions are **not reachable in one hop** — e.g., `Open` has no direct transition to `Planning`. You must walk the graph.

| From | Available transitions | Target |
|---|---|---|
| `Open` | `Picked` | `Prioritized` |
| `Prioritized` | `Started` | `Planning` |
| `Prioritized` | `De-prioritized` | `Open` |
| `Planning` | (forward transitions toward In Progress, etc.) | … |

**Counterintuitive naming:** the transition named `Started` in EARL does NOT move an issue to `In Progress` — it moves `Prioritized → Planning`. Don't trust transition names; trust target statuses.

**Two-hop example.** Moving an `Open` ticket to `Planning` during a grooming sweep requires two calls:

```bash
./bin/ebjira issue transition EARL-141 Prioritized   # Open → Prioritized (via Picked)
./bin/ebjira issue transition EARL-141 Planning     # Prioritized → Planning (via Started)
```

Wrap the two calls in a helper if a chunk touches many `Open` tickets.

**Self-healing fallback.** If a transition call errors with `transition not found` or the graph above no longer matches what Jira returns, **STOP**. Run `./bin/ebjira issue transitions <ANY-EARL-KEY>` (plural command — lists available transitions from the ticket's current status) to rediscover, then update this section in the **same commit** as any campaign work that touched the stale graph. Do not paper over the mismatch.

This section is **EARL-specific**. Other Jira projects will have different workflow graphs and need their own discovery pass.

## The 9 phases

### Phase 0: Verify lint scope

Before snapshotting, open `jira-cli/src/ebjira/commands/lint.py` and confirm `EXEMPT_TYPES` matches the "Lint scope rules" table above (Stories only for As-a/GWT; Feature, Deliverable, Epic, Task, Sub-task, Bug all exempt).

```bash
grep "EXEMPT_TYPES" jira-cli/src/ebjira/commands/lint.py
```

If the set is wrong, fix it in a pre-campaign commit, rebuild the image (`make ebjira-build`), then proceed to Phase 1. **Do not snapshot with a known-wrong linter** — it will produce false positives that waste a full triage pass. See the 2026-04-08 cautionary tale above.

### Phase 1: Snapshot the baseline

```bash
mkdir -p docs/grooming
./bin/ebjira lint issues -p EARL --format json > docs/grooming/sweep-$(date +%Y-%m-%d).json
git add docs/grooming/ && git commit -m "groom(EARL): baseline snapshot"
```

The snapshot is the "before" picture. Progress is measured against it. Never delete a snapshot mid-campaign.

### Phase 1.5: Wave 0 — refresh stale AI summaries

Every grooming campaign starts by refreshing `summary_ai` so triage reads one-paragraph summaries instead of full descriptions. See `docs/grooming/plan-ai-summaries.md` for the design.

```bash
./bin/ebjira lint issues -p EARL --rule stale-summary --format json > /tmp/stale.json
```

For each stale issue:
1. Read the YAML's `summary` + `description`
2. Generate a 2–3 sentence summary written for an agent skimming the backlog
3. `./bin/ebjira issue summarize --key EARL-N --text "..."`

Commit in batches of 10–20: `groom(EARL): refresh N stale summaries`. The lint rule re-runs clean when done. `summary_ai` is local-only — never pushed to Jira.

### Phase 2: Triage every finding into one of three classes

Use the table from `creating-jira-issues` Step 8. Bulk-classify the entire snapshot in one pass. Surface the full classification list to the user **before acting on anything**.

| Class | Signal | Cost | Wave |
|---|---|---|---|
| **Reshape** | Content is good, structure missing. Label paragraphs, bare enumerations, arrow flows. | Cheap (mechanical) | Wave 1 |
| **Rewrite** | Genuine work, sparse description. Need to write user story from context. | Medium (needs scoping) | Wave 2 |
| **Migrate** | Reference content masquerading as ticket. Tech designs, strategies, artifacts. | Expensive (Drive doc + close ticket) | Wave 3 |

The classification output should be a markdown table grouped by class, committed at `docs/grooming/triage-<date>.md`. **User signs off on the table before any wave starts.** Surprises after batch-acting are hard to unwind.

### Phase 3: Wave 1 — drain reshapes (cheap, mechanical)

Reshapes are the cheapest unit of work and build momentum. Process in batches of 5–10:

```bash
# For each issue in the wave:
# 1. Read the YAML, identify structural transforms
# 2. Edit in place — promote labels to ##, convert (1)..(N) to bullets, wrap in As-a/GWT
# 3. Re-lint at warn+ severity to confirm clean

./bin/ebjira lint issues -p EARL --key EARL-152 --severity warn --format table

# 4. Push the whole batch
./bin/ebjira sync push -p EARL --key EARL-152 --key EARL-153 --dry-run
./bin/ebjira sync push -p EARL --key EARL-152 --key EARL-153

# 5. Round-trip verify
./bin/ebjira sync pull --jql 'key in (EARL-152, EARL-153)'
./bin/ebjira lint issues -p EARL --key EARL-152 --severity warn

# 6. ONE commit per wave batch — not per issue
cd $CONTENT_DIR
git add -A jira/
git commit -m "groom(EARL): wave 1 batch N — reshape EARL-152, EARL-153"
```

**Constraint**: never invent requirements during reshape. If a GWT scenario needs new behavior to make sense, leave a `<!-- needs-human: ... -->` marker, demote the issue to Wave 2 (rewrite class), and stop.

### Phase 4: Wave 2 — drain rewrites (needs user input)

Rewrites are blocked on the user. For each:

1. Read the parent epic and any sibling issues to gather context
2. Draft a candidate user story + 2–4 GWT scenarios
3. **Surface the draft to the user** with the source context — get sign-off before writing
4. Apply the draft, push, round-trip, commit (one commit per rewrite — these are higher-touch)

Don't batch rewrites silently. Each one is its own micro-conversation.

### Phase 5: Wave 3 — drain migrations (heavy, batched per source)

Migrations move content from Jira to Drive and close the originating ticket. **Decide topology once** at the start of the campaign and stick to it for every migration.

**Topology decision (locked for EARL):**
- **One folder per agent** under `gdocs/tech-designs/`. Examples:
  - `gdocs/tech-designs/ecomm-agent/`
  - `gdocs/tech-designs/shopify-agent/`
  - `gdocs/tech-designs/discovery-agent/`
- Matches the agent team mental model from EARL-192 Vision
- Cross-agent docs go in `gdocs/tech-designs/_shared/`
- Each doc gets `specifies:` frontmatter pointing at any remaining implementation tickets

**Per-migration steps:**

1. Group findings by source epic. Migrate one source group at a time.
2. Decide if the original ticket has any remaining work after content moves out:
   - **All content was reference material** → migrate content, close/delete the ticket
   - **Some implementation work remains** → migrate content, keep a small Story that `specifies:` the new doc
3. Create the Drive doc(s) with full frontmatter (`tags`, `agent_hints`, `specifies`)
4. Update `links.yaml` at the content repo root with the Jira → Drive mappings
5. Push the Drive docs (`./bin/ebdocs sync push`)
6. Update or close the Jira tickets via the two-commit dance
7. **One commit per source-epic migration**, not per ticket

### Phase 6: Per-wave progress check

After each wave batch lands:

```bash
./bin/ebjira lint issues -p EARL --format json > /tmp/sweep-now.json
python3 -c "
import json
b = json.load(open('docs/grooming/sweep-<baseline-date>.json'))
n = json.load(open('/tmp/sweep-now.json'))
print(f'Baseline: {len(b)} issues with findings')
print(f'Current:  {len(n)} issues with findings')
print(f'Drained:  {len(b) - len(n)}')
"
```

Report progress in the wave commit message: `groom(EARL): wave 1 batch 2 — reshape 5 stories — 49 → 41 findings`.

### Phase 7: Stopping conditions

Don't groom forever. Stop when remaining findings are:

- **(a)** Blocked on user input (rewrites still awaiting scope)
- **(b)** Intentionally exempt (info-level only — e.g., arrow-flow inside a Given clause is fine)
- **(c)** Parked for a future deliverable (the work is real but not in scope this campaign)

Document the stop point in `docs/grooming/stop-<date>.md`:

```markdown
# Grooming campaign stop — 2026-04-07

## Remaining findings: N

- **Blocked on user input (M):** EARL-141 (scope), EARL-XYZ (parent epic decision), …
- **Intentionally exempt (M):** EARL-156 (info-level arrow-flow inside Given clause)
- **Parked (M):** EARL-XYZ (waiting for Drive migration topology of agent X)

## Next campaign should pick up at: …
```

### Phase 8: Close the campaign

When the stop point is documented:

1. Tag the campaign in git: `git tag groom-2026-04-07`
2. Update `docs/grooming/README.md` (or create) with a campaign log entry: dates, baseline count, ending count, what's parked
3. Keep the snapshot files — they're the audit trail
4. **Re-confirm the linter is in a stable state** before the next campaign starts

### Phase 9: Commit message convention

Every commit during a campaign uses the `groom(<project>):` prefix:

- `groom(EARL): baseline snapshot`
- `groom(EARL): wave 1 batch 1 — reshape 3 stories — 49 → 46 findings`
- `groom(EARL): wave 2 — rewrite EARL-141 (Automated store setup pipeline)`
- `groom(EARL): wave 3 batch 1 — migrate 5 ecomm-agent tech designs to Drive`
- `groom(EARL): campaign close — stopped at 8 parked findings`

`git log --grep "^groom(EARL)"` becomes the campaign log.

## Wave granularity rule

**3 waves per campaign**, not finer:

| Wave | What | Why this granularity |
|---|---|---|
| 1 | All reshapes (any type) | Reshapes share the same mechanical pattern — batch them by mechanic, not by type |
| 2 | All rewrites | Each is a micro-conversation; treating them as a separate wave forces you to slow down |
| 3 | All migrations | Migrations need topology decisions; one wave keeps that decision consistent |

Finer-grained waves (per-type, per-epic) create overhead without changing the work. The wave boundary should be a **methodology change**, not a content change.

## Constraints (do not violate)

- **No mid-campaign linter rule changes.** If you fix a false positive mid-sweep, the snapshot is invalidated. Stop the campaign, fix the linter, re-snapshot, restart.
- **No silent batch actions.** Triage list and migration topology must be user-approved before any wave starts.
- **No reshape becomes rewrite without user input.** If you find a "reshape" needs new requirements to make sense, demote it to Wave 2 — don't invent.
- **No migration without `specifies:` linkback** for any remaining implementation work. Otherwise the connection from Drive to Jira is lost.
- **Never delete the snapshot files** until the campaign is closed and tagged.

## Exit criteria

The campaign is **done** when one of these is true:

- Lint sweep returns 0 issues with findings (rare — usually some are parked)
- All remaining findings are documented in `stop-<date>.md` under categories (a)/(b)/(c)
- The user signs off on the stop point

Then tag, log, and close.
