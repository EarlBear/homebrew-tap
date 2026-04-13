# Add Backlog Item

> **Context:** This skill creates Jira issues via the Jira MCP tools. It discovers project metadata dynamically, applies keyword heuristics to suggest issue types, gathers details interactively, and creates well-formatted tickets. Supports single items and batch creation.
>
> **Prerequisite:** Jira MCP must be configured. If `mcp__jira__get_projects` fails or is unavailable, tell the user to run `/setup-jira` first.

## When to trigger

User says things like:
- "add to backlog", "add backlog item"
- "create a jira ticket", "make a ticket for this"
- "track this in jira"
- "create stories for all artifacts"
- "log a bug for..."

## Workflow

Track all steps as tasks using TaskCreate/TaskUpdate.

### Step 1: Discover Jira context

1. Call `mcp__jira__get_projects` to list available projects.
2. If multiple projects exist, present them via AskUserQuestion: "Which project should this go in? [list project keys and names]"
3. If only one project, confirm it: "I'll create this in PROJECT_KEY (Project Name). Sound good?"
4. Call `mcp__jira__get_create_meta` for the chosen project to discover:
   - Available issue types (Epic, Story, Task, Bug, Sub-task, etc.)
   - Required fields for each issue type
   - Allowed values for constrained fields (priority, labels, etc.)

**Note:** Some Jira tiers (especially Free) may not have all issue types. Never assume Epic, Story, Task, or Bug exist — always check what `get_create_meta` returns and work with what's available.

### Step 1b: Check for duplicates (idempotency)

Before creating, search for existing issues that match. This makes the skill safe to re-run:

```
project = PROJECT_KEY AND summary ~ "keyword from summary" ORDER BY created DESC
```

If a match is found, report it and ask: "This looks like it already exists as PROJECT-123. Update it, skip it, or create a new one?"

In batch mode, automatically skip items that already have a matching issue (match on summary keywords). Report skipped items at the end.

### Step 2: Determine issue type (heuristic + confirmation)

Apply keyword heuristics to the user's description to suggest an issue type:

**Issue type hierarchy (EarlBear convention):**

| Type | Purpose | Examples |
|------|---------|---------|
| **Epic** | Core business function / recurring habit. Epics are **ongoing** — they group related stories around a theme that the team regularly invests in. | "Client Discovery", "Outreach Pipeline", "Store Analysis", "Sales Enablement", "Platform & Infrastructure" |
| **Story** | A discrete capability that delivers user value. Written as "As a [persona], I want [capability] so that [outcome]." **Default for most items.** | "As a sales rep, I want a top-3 issues report so that I can personalize outreach" |
| **Task** | Internal/infra work with no direct user-facing outcome. | "Configure CI pipeline", "Set up Supabase MCP" |
| **Bug** | Something broken that needs fixing. | "Crawler hangs on stores with infinite scroll" |

**Default to Story.** Epics are only for broad, ongoing business functions — not for individual features. Features encompass many stories with a unifying thread. Epics combine features.

Present the suggestion via AskUserQuestion:

> This sounds like a **Story**. Is that right, or should it be a [list other available types]?

If the suggested type is not available in the project (discovered in Step 1), fall back to the closest available type and explain why.

### Step 3: Gather details via AskUserQuestion

Collect the following, suggesting defaults based on context when possible:

1. **Summary** — Suggest one based on the user's description. Keep it concise (<80 chars). Ask for confirmation:
   > How about: "Add StatiCrypt password rotation logging"? Or suggest your own.

2. **Priority** — Suggest based on language urgency ("critical"/"urgent" = High, "nice to have"/"eventually" = Low, default = Medium):
   > I'd suggest **Medium** priority. Want to change it?

3. **Acceptance criteria** — Ask: "What does done look like?" Format the response as a checklist.

4. **Labels** — Suggest relevant ones based on context. Common labels for this repo:
   - `artifact` — Claude artifact related
   - `deck` — Deck generator related
   - `wireframe` — Wireframe related
   - `infra` — Infrastructure, Docker, CI/CD, publishing
   - `enhancement` — Improvement to existing feature
   > Suggested labels: `infra`, `enhancement`. Add, remove, or change?

5. **Epic link** — If creating a Story or Task, ask if it belongs to an existing Epic. Search with `mcp__jira__search_issues` using JQL:
   ```
   project = PROJECT_KEY AND issuetype = Epic ORDER BY updated DESC
   ```
   Present results: "Should this belong to an existing Epic? [list epics] Or no epic?"

   If Epic type is not available in the project, skip this step entirely.

### Step 4: Format and create

**For Stories**, write the summary as a proper user story:

> As a [persona], I want [capability] so that [outcome].

Examples:
- "As a sales rep, I want a per-store top 3 issues report so that I can personalize outreach emails"
- "As a prospect researcher, I want a theme divergence scorer so that I can prioritize high-investment stores"

The description body uses **Jira wiki markup** (not Markdown):

```
h3. User Story
As a [persona], I want [capability] so that [outcome].

h3. Acceptance Criteria
- First criterion
- Second criterion
- Third criterion

h3. Context
Additional context, motivation, or links.

h3. Related
- Link to relevant file or docs
```

Key Jira wiki markup rules:
- `h3.` for headers (not `###`)
- `*bold*` for emphasis (not `**bold**`)
- `{noformat}...{noformat}` for code blocks (not triple backticks)
- `-` for bullet lists (not `*`)

Call `mcp__jira__create_issue` with:
- `projectKey` — from Step 1
- `issueType` — from Step 2 (use the exact type name returned by `get_create_meta`)
- `summary` — from Step 3
- `description` — formatted wiki markup from above
- `priority` — from Step 3 (use exact priority name from `get_create_meta`)
- `labels` — from Step 3 (as array)
- `parent` — Epic key from Step 3, if specified (use the field name discovered from `get_create_meta` — may be `parent`, `customfield_*`, or `epic` depending on Jira version)

**Never hardcode project keys, field IDs, or issue type IDs.** Always use values discovered dynamically from `get_create_meta` and `get_projects`.

### Step 5: Sync to Supabase

After creating the Jira issue, update the corresponding Supabase row (if one exists) with the Jira link:

```sql
UPDATE artifacts SET jira_issue_key = 'PROJECT-123', jira_issue_url = 'https://...browse/PROJECT-123'
WHERE slug = 'artifact-slug';
```

Use `mcp__plugin_supabase_supabase__execute_sql` to run this. If no matching Supabase row exists, skip this step silently.

Also update `scripts/jira-card-mapping.json` with the new mapping entry.

**Preview check:** After creating the Jira issue and syncing to Supabase, check if the artifact has a preview. If not, suggest running `/manage-previews` to add one. Artifacts without previews should not move to "active" status.

**Add production URL comment:** If the artifact has a published location (e.g., `https://bytesofpurpose.github.io/earlbear/artifacts/artifact-tracker/`), add a comment to the Jira issue with the link. Check existing comments first to avoid duplicates.

**Tech designs and strategies are artifacts:** Items under Tech Designs or Business Strategies Epics should always get a Supabase row. Tag them with `tech-design` or `strategy` in the `tags` array. These represent the working-backwards vision and should appear on the artifact tracker board.

### Step 6: Report + follow-up

After successful creation, report:

> Created **PROJECT-123**: "Summary text"
> URL: https://yourcompany.atlassian.net/browse/PROJECT-123
> Type: Story | Priority: Medium | Labels: artifact
> Supabase: synced (jira_issue_key updated)

Then ask:

> Want to create another related item? Or should I link this to an existing issue?

## Batch mode

When the user says something like "create stories for all artifacts" or "make tickets for each deck type":

1. Identify the items to create (e.g., list artifacts in `../earlbear-sites/claude-artifacts/`, list deck content files in `../earlbear-clis/deck-generator/content/`)
2. Present the batch plan via AskUserQuestion:
   > I found 5 artifacts. I'll create a Story for each:
   > 1. "Import artifact-tracker to catalog" (artifact, enhancement)
   > 2. "Import competitive-analysis to catalog" (artifact, enhancement)
   > ...
   > Proceed with all 5, or want to adjust any?
3. On confirmation, create issues one at a time, reporting each key as it's created
4. At the end, summarize all created issues in a table

## Project & team context

Before creating issues, inspect the project to understand the current state:

1. **List existing Epics** — search for Epics in the project to suggest the right parent:
   ```
   project = EARL AND issuetype = Epic ORDER BY summary ASC
   ```
   Current Epics (as of 2026-03-27):
   - EARL-26: Launch EarlBear (umbrella initiative)
   - EARL-27: Outreach Pipeline
   - EARL-28: Client Discovery
   - EARL-29: Store Analysis
   - EARL-30: Sales Enablement
   - EARL-31: Platform & Infrastructure

2. **Team mapping** — Jira display names differ from artifact tracker names:
   | Artifact Tracker | Jira Display Name | Role |
   |-----------------|-------------------|------|
   | `omar` | Omar Eid | Technical lead |
   | `saad` | duke | Store analysis |
   | `mazen` | mazen | Outreach & sales |

   When setting assignee, use `mcp__jira__get_users` to discover account IDs dynamically. Never hardcode account IDs.

3. **Priority mapping:**
   | Artifact Tracker | Jira Priority |
   |-----------------|---------------|
   | `high` | Highest |
   | `med` | Medium |
   | `low` | Low |

## Divergence detection

When the user says "check sync" or "detect divergence", compare Supabase artifact rows against Jira issues:

1. Fetch all artifacts from Supabase (`mcp__plugin_supabase_supabase__execute_sql`)
2. For each artifact with a `jira_issue_key`, fetch the Jira issue
3. Compare: priority, status, assignee
4. Report mismatches as a table
5. Offer to sync (update Jira from Supabase, or Supabase from Jira)

## Key constraints

- **Idempotent.** Always search for existing issues before creating. In batch mode, skip items that already exist. This makes the skill safe to re-run.
- **Stories by default.** Most backlog items are Stories with "As a... I want... So that..." format. Only use Task for internal/infra work.
- **Sync to Supabase.** After creating a Jira issue, update the matching Supabase row and `scripts/jira-card-mapping.json` with the issue key/URL.
- **Dynamic discovery only.** Never hardcode project keys, issue type IDs, field IDs, or priority values. Always read them from `get_projects`, `get_create_meta`, and `get_field_options`.
- **Graceful degradation.** If an issue type isn't available (e.g., no Epic on Free tier), explain and fall back to the closest available type.
- **Jira wiki markup, not Markdown.** Jira Cloud uses wiki markup in descriptions. Markdown will render as plain text.
- **Prerequisite check.** If any `mcp__jira__*` call fails with a connection error, stop and tell the user to run `/setup-jira`.
- **No secrets in output.** Never echo Jira API tokens or credentials. If troubleshooting auth, point the user to `.env`.
- **Labels are optional.** Not all Jira projects have labels configured. If `create_issue` rejects labels, retry without them and note the limitation.
