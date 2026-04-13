# Refine Working Model

> Primary TPM skill for EarlBear. Owns the delivery process end-to-end: work taxonomy, delivery SOPs, domain model evolution, capacity planning, dependency tracking, process health, and guided Jira setup. Use this skill to classify work, analyze process health, evolve the model, or apply changes.

> **This skill vs `/sync-catalog`:** This skill evolves the domain model (types, SOPs, statuses, components) — heavy, infrequent, design-focused. For lightweight Jira <-> Supabase sync, use `/sync-catalog` instead.

## Two Systems, Two Perspectives

- **Supabase is vision-focused (top-down):** The artifact catalog represents what SHOULD exist — the aspirational product vision. Tags, layers, dependencies, and display metadata live here.
- **Jira is work-focused (bottom-up):** Where actual work gets done. Issue types, statuses, assignees, components. May discover work bottom-up that needs to flow back to the vision.
- **They sync but serve different purposes.** A Supabase artifact without a Jira issue is "vision without execution." A Jira issue without a Supabase artifact is "work without vision." Both gaps should be flagged.
- **After refining the working model**, run `/sync-catalog` to propagate structural changes (new types, reclassifications, components) to the catalog.

## Skill Phases

Track every phase with TaskCreate/TaskUpdate. Create deps between phases.

```
Phase 1: ANALYZE     -> Read Jira state, check process health
Phase 2: DIAGNOSE    -> Detect misclassifications, missing metadata, SOP gaps, bottlenecks
Phase 3: RECOMMEND   -> Propose changes (issue reclassification, new types, SOP updates)
Phase 4: APPLY       -> CLI automation + guided UI walkthrough (self-healing)
Phase 5: VERIFY      -> Confirm changes, regenerate ERD, update status tracker
Phase 6: DOCUMENT    -> Update SOPs, Jira guide, architecture diagrams
Phase 6.5: SYNC      -> Run /sync-catalog to propagate model changes to Supabase
Phase 7: AGENT SYNC  -> Manually update agent repo docs if working model changed
Phase 8: TEST AGENT  -> Run /manage-cloud-agent test to verify agent picks up changes
```

Always update `docs/working-model-status.md` at the end of each run.

**Phase 8 detail:** After syncing model changes to the agent repo, run the agent smoke test to verify Earl handles the updated model correctly. Use `/manage-cloud-agent test` — it creates a test Deliverable, triggers the agent, and verifies the output (Google Doc created, checklist validated, paper trail posted).

**Phase 7 detail — doc ownership model:**

The agent repo (`earlbear-claude-agent`) **owns its own copies** of working model docs. The earlbear repo has copies for human reference, but they are NOT the agent's source of truth. This prevents rsync from clobbering changes made in either repo.

| File | Earlbear repo (human reference) | Agent repo (agent's source of truth) |
|------|------|------|
| `docs/earlbear-agent-responsibilities.md` | Has copy | **Owns** |
| `docs/draft-checklists.yaml` | Has copy | **Owns** |
| `docs/design-work-taxonomy.md` | Has copy | **Owns** |
| `docs/delivery-sops.md` | Has copy | **Owns** |
| `CLAUDE.md` | Has own | **Owns its own** (agent-specific) |
| `jira-cli/`, `gdocs-cli/`, `shopify-cli/` | References (in earlbear-clis repo) | Synced from earlbear-clis via sync-from-earlbear.sh |

**When the working model changes in the earlbear repo:**

1. Make the change in the earlbear repo (this repo)
2. Manually apply the same change in the agent repo: `cd ../earlbear-claude-agent && edit docs/...`
3. Commit and push the agent repo
4. The cloud agent picks up the change on its next run

**When the agent repo diverges** (e.g., agent discovers a gotcha, you tweak tenets):

That's fine — the agent repo's copy is canonical for the agent. Optionally backport learnings to the earlbear repo.

**CLI code lives in the `earlbear-clis` repo** — both the earlbear repo and the agent repo consume it. When CLI code changes:

```bash
# 1. Edit + commit in earlbear-clis repo
cd ../earlbear-clis && # ... edit ...

# 2. Sync to agent repo
cd ../earlbear-claude-agent && ./sync-from-earlbear.sh --cli-only
```

## 1. Work Taxonomy (brief)

Issue types: Story (customer capability), Feature (backend capability), Deliverable (artifact to produce), Task (generic action), Bug (broken thing), Subtask (child work).

Classification test (apply in order, first yes wins):
1. Broken? -> Bug
2. Specific artifact? -> Deliverable
3. Changes customer experience? -> Story
4. Enables stories? -> Feature
5. None? -> Task

Full definitions: `docs/design-work-taxonomy.md`
Draft checklists: `docs/draft-checklists.yaml`

## 2. Delivery SOPs (brief)

Each work type has its own SOP with Mermaid sequence diagram, definition of done, and roles.

Full SOPs: `docs/delivery-sops.md`

Key flows:
- **Story**: PM creates -> Dev implements -> Reviewer approves -> Done
- **Feature**: PM creates -> Dev builds + tests -> Code review -> Done
- **Deliverable (AI)**: PM creates + ai-eligible -> AI drafts -> AI validates checklist -> Human reviews -> Done
- **Deliverable (Human)**: PM creates -> Human produces -> Review -> Done
- **Task**: Prioritized -> In Progress -> Done
- **Bug**: Report -> Reproduce -> Fix -> Verify -> Done

## 3. Domain Model Analysis

```bash
ebjira model analyze --project EARL    # Current state + recommendations
ebjira model diff --project EARL       # Changes needed
ebjira report health --project EARL    # Overall health dashboard
```

Detection heuristics: see `docs/design-work-taxonomy.md` (Decision 8)

## 4. Apply Changes

### CLI-automatable
```bash
ebjira model apply --project EARL              # All safe changes
ebjira model apply --components-only           # Just components
ebjira model apply --reclassify-only           # Just reclassification
```

### CLI-automatable (Waves 1-4 additions)
```bash
ebjira workflow create --name "Custom Flow" --statuses "..."   # Create workflows
ebjira workflow update 10001 --name "Renamed"                  # Update workflows
ebjira workflow delete 10001                                   # Delete workflows
ebjira workflowscheme create --name "Scheme"                   # Create workflow schemes
ebjira workflowscheme assign 10001 --project EARL              # Assign scheme to project
ebjira issuetypescheme create --name "Types" --issuetypes ...  # Create issue type schemes
ebjira issuetypescheme assign 10001 --project EARL             # Assign scheme to project
ebjira component create --project EARL --name "frontend"       # Create components
ebjira bulk transition --jql "..." "Done"                      # Bulk transitions
ebjira bulk update --jql "..." --labels new-label              # Bulk updates
ebjira issuelink create EARL-42 EARL-43 --type "blocks"        # Link issues
ebjira epic create --project EARL --summary "New Epic"         # Create epics
ebjira board columns 1                                         # View board columns
ebjira board set-columns 1 --columns '...'                     # Configure columns
```

### UI-required (workflow + board column changes)

**Adding a status to the project workflow requires Jira UI.** The workflow CRUD API is unreliable. Steps:

1. **Create status via CLI:** `ebjira status create --name "Planning" --category IN_PROGRESS`
2. **Add to workflow via Jira UI:** Project Settings → Workflow → edit EARL Workflow → add status + transitions
3. **Map to board column via Jira UI:** Board Settings → Columns → drag status into column
4. **Verify via CLI:** `ebjira project statuses EARL` + `ebjira board columns 34`
5. **Update manifest:** add status to `statuses:`, `workflow.statuses:`, `workflow.transitions:`, `board.columns:`
6. **Refresh cache:** `ebjira cache refresh --project EARL`
7. **Re-export seed:** `ebjira seed export --project EARL`

**Current workflow:** Open → Prioritized → Planning → In Progress → Review → Done

Use the guided walkthrough protocol for UI steps:
1. Try browser automation (mcp__claude-in-chrome__*)
2. Fall back to screenshot-based guidance
3. Verify each step via CLI
4. Self-heal if page doesn't match expectations

## 5. Capacity & Workload

Query current workload distribution:
```bash
ebjira issue list --project EARL --json key,assignee,status,issuetype --limit 100
```

Balance rules:
- No person should have 3+ items In Progress simultaneously
- AI handles ai-eligible Deliverables
- Rebalance across Omar, Duke, Mazen when skewed

## 6. Dependency Tracking

Identify cross-epic, cross-component dependencies:
```bash
# Issues that block others
ebjira issue list --jql 'project = EARL AND issueFunction in linkedIssuesOf("project = EARL", "blocks")'
```

When blocked: move to Blocked, create blocking work if needed, link issues.

Critical path: the longest chain of dependencies determines the earliest completion date.

## 7. Process Health

Run periodically (weekly or before planning):
```bash
ebjira report health --project EARL
ebjira report type-summary --project EARL
ebjira report epic-summary --project EARL
ebjira report ai-dashboard --project EARL
```

Red flags:
- 3+ Deliverables In Progress with ai-eligible -> AI throughput saturated
- 5+ issues in Ready For Review -> review bottleneck
- Issues Blocked 7+ days -> blocked work not being unblocked
- All issues in Prioritized -> nothing has started

## 8. Retrospective-Driven Evolution

When an SOP doesn't work:
1. Note the friction point
2. After sprint/milestone, review friction points
3. Update `docs/delivery-sops.md`
4. Update this skill if classification or guardrails change
5. Update `docs/working-model-status.md` with the change

## 9. Onboarding

Point new team members to:
1. `docs/jira-guide.md` -- full Jira setup with clickable Mermaid
2. `docs/delivery-sops.md` -- how work flows
3. `docs/design-work-taxonomy.md` -- why it's set up this way

## Source of Truth

| What | Where |
|------|-------|
| Design decisions (14) | `docs/design-work-taxonomy.md` |
| Delivery SOPs | `docs/delivery-sops.md` |
| Draft checklists | `docs/draft-checklists.yaml` |
| Jira ramp-up guide | `docs/jira-guide.md` |
| Process status | `docs/working-model-status.md` |
| ERD (live) | `docs/jira-issue-types-erd.md` |
| Architecture | `docs/ebjira-architecture.md` |
