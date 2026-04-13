# Leveraging the ebjira CLI

> Use this skill when working with Jira issues, projects, sprints, or any Jira administration tasks. The ebjira CLI is the preferred way to interact with Jira — use it instead of the Jira MCP server.

## Quick Reference

```bash
# Issues
ebjira issue list --project EARL                          # List project issues
ebjira issue list --project EARL --status "In Progress"   # Filter by status
ebjira issue list --jql "assignee = currentUser()"        # Raw JQL
ebjira issue view CH-42                                 # Full issue details
ebjira issue create --project EARL --type Task --summary "Fix login bug"
ebjira issue update CH-42 --summary "New title" --priority High
ebjira issue delete CH-42 --delete-subtasks
ebjira issue transition CH-42 "Done"
ebjira issue transitions CH-42                          # List available transitions
ebjira issue comment CH-42 "Looks good, merging now"
ebjira issue meta EARL                                    # Issue types + required fields

# Issue Types
ebjira issuetype list                                     # All issue types
ebjira issuetype list --project EARL                      # Project-scoped
ebjira issuetype view 10001
ebjira issuetype create --name "Design" --type standard
ebjira issuetype create --name "Sub-bug" --type subtask
ebjira issuetype update 10001 --name "Renamed"
ebjira issuetype alternatives 10001                       # Check before deleting
ebjira issuetype delete 10001 --alternative-id 10002

# Projects
ebjira project list
ebjira project view EARL
ebjira project components EARL
ebjira project versions EARL
ebjira project roles EARL
ebjira project statuses EARL

# Epics
ebjira epic list --project EARL
ebjira epic children CH-10
ebjira epic create --project EARL --summary "New Epic"
ebjira epic update CH-10 --summary "Renamed Epic"
ebjira epic delete CH-10
ebjira epic move CH-10 CH-42 CH-43                  # Move issues into epic

# Boards
ebjira board list
ebjira board view 1
ebjira board issues 1
ebjira board backlog 1
ebjira board config 1
ebjira board columns 1                                    # View board columns
ebjira board set-columns 1 --columns '...'                # Configure board columns

# Components
ebjira component list --project EARL
ebjira component create --project EARL --name "frontend"
ebjira component update 10001 --name "renamed"
ebjira component delete 10001

# Workflows
ebjira workflow list
ebjira workflow view 10001
ebjira workflow create --name "Custom Flow" --statuses "Open,In Progress,Done"
ebjira workflow update 10001 --name "Renamed Flow"
ebjira workflow delete 10001
ebjira workflow transitions 10001                         # List workflow transitions

# Workflow Schemes
ebjira workflowscheme list
ebjira workflowscheme view 10001
ebjira workflowscheme create --name "Custom Scheme"
ebjira workflowscheme update 10001 --name "Renamed"
ebjira workflowscheme assign 10001 --project EARL         # Assign scheme to project

# Issue Type Schemes
ebjira issuetypescheme list
ebjira issuetypescheme create --name "Custom Scheme" --issuetypes 10001,10002
ebjira issuetypescheme update 10001 --name "Renamed"
ebjira issuetypescheme assign 10001 --project EARL        # Assign scheme to project

# Issue Links
ebjira issuelink types                                    # List link types (blocks, relates to, etc.)
ebjira issuelink create CH-42 CH-43 --type "blocks"   # Create a link
ebjira issuelink delete 12345                             # Delete a link

# Bulk Operations
ebjira bulk transition --jql "project = EARL AND status = 'In Progress'" "Done"
ebjira bulk update --jql "project = EARL AND labels = old-label" --labels new-label

# Cache (local ID cache for fast lookups)
ebjira cache refresh --project EARL                         # Rebuild cache from Jira
ebjira cache show                                           # Show cached IDs
ebjira cache lookup --type "Story"                          # Lookup cached ID

# Log (agent run logs from Supabase)
ebjira log recent                                           # Recent CLI log entries
ebjira log errors                                           # Recent errors
ebjira log run <run-id>                                     # Details for a specific run
ebjira log issue CH-42                                    # Logs for a specific issue
ebjira log stats                                            # Usage statistics
ebjira log runs                                             # Agent run summaries
ebjira log cost                                             # Cost breakdown

# Fields
ebjira field list
ebjira field options --project EARL --issuetype 10001

# Attachments
ebjira attachment get 12345
ebjira attachment add CH-42 /path/to/file.pdf
ebjira attachment add CH-42 "base64string..." --base64 --filename report.pdf
ebjira attachment delete 12345

# Users
ebjira user search "omar"
ebjira user list
ebjira user me
ebjira user groups

# Server
ebjira server info
ebjira server health

# Manifest (declarative project config)
ebjira manifest diff --project EARL                       # Compare manifest.yaml vs live Jira
ebjira manifest apply --project EARL                      # Push manifest changes to Jira
ebjira manifest export --project EARL                     # Snapshot live Jira → manifest.yaml
ebjira manifest diagram                                   # Generate Mermaid diagrams from manifest

# Seed (declarative issue inventory — assets/jira/manifests/issues.yaml)
ebjira seed export --project EARL                         # Export all issues as hierarchical YAML
ebjira seed diff --project EARL                           # Compare issues.yaml vs live Jira
ebjira seed apply --project EARL                          # Create/update issues from YAML
ebjira seed apply --project EARL --dry-run                # Preview without applying
ebjira seed validate                                      # Check YAML for errors
```

## Declarative Issue Management (Seed YAML)

The seed file (`assets/jira/manifests/issues.yaml`) is the single editable view of all project issues. Edit inline, then `seed apply` syncs to Jira.

### Emoji Tag Reference

| Emoji | Field | Example | Notes |
|-------|-------|---------|-------|
| 🎫 | Key | `[[🎫:CH-42]]` | `NEW` to create. Auto-updates after apply. |
| 🏷️ | Type | `[[🏷️:Deliverable]]` | Story, Feature, Deliverable, Task, Bug |
| 📦 | Component | `[[📦:store-analyzer]]` | Which app/system |
| 👤 | Assignee | `[[👤:omar]]` | Short name: omar, sa'd, mazen |
| ⬆️ | Priority | `[[⬆️:Highest]]` | Highest, High, Medium, Low, Lowest |
| 🔖 | Labels | `[[🔖:ai-eligible,kind:report]]` | Comma-separated |
| 📊 | Status | `[[📊:Open]]` | Only shown when not Prioritized. Omit = don't change. |
| 🛑 | Blocked by | `[[🛑:CH-129,CH-136]]` | Creates "Blocks" issue links |
| 🔗 | Relates to | `[[🔗:CH-132]]` | Creates "Relates" issue links |
| 📝 | Description | `[[📝:text]]` | Multi-line. Cleaned from YAML after apply. |
| ✅ | Acceptance criteria | `[[✅:text]]` | Cleaned from YAML after apply. |

Summary is always the **untagged text at the end** of the line.

### Creating Issues

```yaml
# New issue under an existing epic
  Tech Designs [[🎫:CH-127]]:
    - [[🎫:NEW]] [[🏷️:Deliverable]] [[📦:earlbear-platform]] [[👤:omar]] [[⬆️:Highest]] [[🔖:kind:report]] My New Tech Design

# New epic with children
  My New Epic [[🎫:NEW]]:
    - [[🎫:NEW]] [[🏷️:Story]] [[📦:earlbear-platform]] [[👤:omar]] [[⬆️:High]] First story in new epic
    - [[🎫:NEW]] [[🏷️:Feature]] [[📦:earlbear-platform]] [[👤:sa'd]] [[⬆️:Medium]] Feature under new epic
```

After `seed apply`: `[[🎫:NEW]]` → `[[🎫:CH-XXX]]` automatically in the file.

### Adding Descriptions (Verbose Mode for New Issues)

```yaml
    - [[🎫:NEW]] [[🏷️:Deliverable]] [[📦:earlbear-platform]] [[👤:omar]] [[⬆️:Highest]] My Design Doc
      [[📝:This is the description. Can span multiple lines.]]
      [[📝:- Bullet point 1]]
      [[📝:- Bullet point 2]]
      [[✅:(1) First acceptance criterion]]
      [[✅:(2) Second acceptance criterion]]
```

After `seed apply`: description + AC pushed to Jira as rendered ADF, then `📝`/`✅` lines **removed from YAML** (description now lives in Jira).

### Moving Issues Between Epics

Cut and paste an issue line from one epic to another in the YAML:

```yaml
  # Before: issue under Business Strategies
  Business Strategies [[🎫:CH-128]]:
    - [[🎫:CH-129]] [[🏷️:Deliverable]] ... Ecomm Agent — Tech Design

  # After: moved to Tech Designs
  Tech Designs [[🎫:CH-127]]:
    - [[🎫:CH-129]] [[🏷️:Deliverable]] ... Ecomm Agent — Tech Design
```

`seed apply` detects the parent mismatch and re-parents in Jira.

### Changing Status (Moving to Backlog, In Progress, etc.)

```yaml
# Move to backlog (Open)
- [[🎫:CH-151]] [[🏷️:Task]] ... [[📊:Open]] Investigate Calendar

# Move to In Progress
- [[🎫:CH-154]] [[🏷️:Feature]] ... [[📊:In Progress]] Give Watson deck tooling

# No status tag = don't change status (leave as-is)
- [[🎫:CH-152]] [[🏷️:Story]] ... Tag-to-assign
```

`seed apply` transitions the issue via the Jira workflow API.

### Changing Priority, Type, Assignee

Just edit the tag inline:

```yaml
# Change priority from Highest to Low
- [[🎫:CH-151]] [[🏷️:Task]] ... [[⬆️:Low]] Investigate Calendar

# Reclassify type from Story to Deliverable
- [[🎫:CH-106]] [[🏷️:Deliverable]] ... Credibility Statement

# Reassign
- [[🎫:CH-99]] [[🏷️:Task]] ... [[👤:omar]] Self-Healing Site Rules
```

### Adding Dependencies

```yaml
# CH-137 is blocked by CH-146 and CH-129
- [[🎫:CH-137]] ... [[🛑:CH-146,CH-129]] Health Dashboard

# CH-147 relates to CH-132
- [[🎫:CH-147]] ... [[🔗:CH-132]] Partner Strategy
```

`seed apply` creates the issue links in Jira. Existing links are not duplicated.

### Appending to Existing Descriptions

Use the CLI directly (not the seed file) for appending:

```bash
ebjira issue update CH-129 --description "### New Section\n- New point" --append
```

`--append` fetches existing description, appends new content, renders as ADF.

### Clickable Issue Keys (VS Code / Cursor)

Install [Regex Robin](https://marketplace.visualstudio.com/items?itemName=DanLevett.regex-robin) extension. The repo's `.vscode/settings.json` makes every `CH-XXX` CMD+clickable → opens in Jira. See `docs/sop-editor-jira-links.md`.

### File Locations

```
assets/jira/manifests/
├── manifest.yaml      # Project config (types, statuses, workflows, components, board)
├── issues.yaml        # Issue inventory (this file — hierarchical YAML)
└── card-mapping.json  # Slug → Jira key mapping (used by /sync-catalog)
```

## Local Dev Workflow (Issue-Aware)

Work off Jira issues with branches, commits, and transitions linked automatically.

### Pick an issue and start

```bash
# See what's ready to work on
ebjira dev list
#  KEY       TYPE        PRIORITY  ASSIGNEE  SUMMARY
#  CH-154  Feature     Highest   omar      Give Watson deck generation tooling
#  CH-156  Story       Highest   omar      Watson Planning Mode

# Start working — creates branch + transitions to In Progress
ebjira dev start CH-154
# → Creates branch: feature/CH-154-give-watson-deck-generation-tooling
# → Transitions CH-154 to In Progress
```

### Work and commit

```bash
# Normal coding...
git add .

# Commit with auto-prefixed issue key
ebjira dev commit "Add Marp template support for deck generation"
# → git commit -m "CH-154: Add Marp template support for deck generation"

# Check what you're working on
ebjira dev status
# → {"key": "CH-154", "branch": "feature/CH-154-...", "status": "In Progress"}
```

### Finish and push

```bash
# Push branch, add GitHub link to Jira, transition to Ready For Review
ebjira dev finish
# → git push -u origin feature/CH-154-...
# → Adds remote link on CH-154 (shows as web panel in Jira)
# → Adds comment: "Development Complete — Branch: <link>"
# → Transitions CH-154 to Ready For Review

# Or skip push / skip transition
ebjira dev finish --no-push          # Just transition, don't push
ebjira dev finish --no-transition    # Just push, don't transition
```

### Branch naming convention

```
feature/CH-42-summary-slug       # Features, stories
feature/CH-150-google-api-fix    # Bug fixes too
```

The issue key in the branch name lets `dev status`, `dev finish`, and `dev commit` auto-detect which issue you're on.

## Output Formats

Every command supports `--format` and `--json`:

```bash
# Default: JSON (agent consumption)
ebjira issue list --project EARL
# [{"key": "CH-42", "summary": "Fix login", "status": "In Progress"}]

# Field selection — only return specific keys
ebjira issue list --project EARL --json key,summary,status

# Human-readable table
ebjira issue list --project EARL --format table
# KEY       STATUS         ASSIGNEE  SUMMARY
# CH-42   In Progress    omar      Fix login

# Plain — one value per line, pipe-friendly
ebjira issue list --project EARL --format plain
# CH-42
# CH-43
```

Shorthand flags: `-f` for `--format`, `-j` for `--json`.

When piping to other tools, use `--format plain` for line-oriented output or default JSON for `jq` processing:

```bash
ebjira issue list --project EARL | jq '.[].key'
ebjira issue list --project EARL --format plain | xargs -I{} ebjira issue view {}
```

## Discovery Pattern

The CLI is self-documenting at every level:

```bash
ebjira --help                     # All command groups
ebjira issue --help               # Commands within a group
ebjira issue list --help          # Options for a specific command (with examples)
ebjira --help-json                # Full command tree as JSON (for programmatic parsing)
ebjira --version                  # Version info as JSON
```

Always start with `--help` when unsure. Every command includes usage examples in its help text.

The `--help-json` flag is particularly useful for agents — it dumps the entire command tree with all options, types, defaults, and descriptions as structured JSON.

## Search and JQL

`ebjira issue list` builds JQL automatically from filter flags:

```bash
# These filter flags combine with AND:
ebjira issue list \
  --project EARL \
  --status "In Progress" \
  --type Story \
  --assignee currentUser \
  --label backend \
  --sprint "Sprint 5" \
  --limit 50
# Generates: project = "EARL" AND status = "In Progress" AND issuetype = "Story"
#            AND assignee = currentUser() AND labels = "backend"
#            AND sprint = "Sprint 5" ORDER BY updated DESC
```

For anything more complex, pass raw JQL with `--jql` (overrides all other filters):

```bash
ebjira issue list --jql 'project = EARL AND status changed AFTER -7d ORDER BY priority DESC'
ebjira issue list --jql 'assignee = currentUser() AND resolution = Unresolved'
ebjira issue list --jql 'labels in (urgent, blocker) AND sprint in openSprints()'
```

The `--label` flag is repeatable — each adds a separate `labels = "X"` clause (AND logic).

Default sort is `ORDER BY updated DESC`. Default limit is 25; override with `--limit`.

## Issue Type Management

The original motivation for building this CLI. Full lifecycle:

```bash
# 1. List current issue types
ebjira issuetype list --format table

# 2. Create a new issue type
ebjira issuetype create --name "Design Task" --type standard --description "For design work"
# Returns: {"id": "10042", "name": "Design Task", ...}

# 3. Create a subtask type
ebjira issuetype create --name "Design Subtask" --type subtask

# 4. Update it
ebjira issuetype update 10042 --name "Design" --description "Updated description"

# 5. Before deleting, check what alternatives exist (for migrating existing issues)
ebjira issuetype alternatives 10042

# 6. Delete with migration
ebjira issuetype delete 10042 --alternative-id 10001
```

To see which issue types a project accepts:

```bash
ebjira issuetype list --project EARL
ebjira issue meta EARL              # Also shows required fields per type
```

## Common Workflows

### Create an issue, transition it, add a comment

```bash
# Create
ebjira issue create --project EARL --type Story \
  --summary "Add dark mode" \
  --description "Users want dark mode support" \
  --priority Medium \
  --labels feature --labels frontend

# Check what transitions are available
ebjira issue transitions CH-99

# Move to In Progress
ebjira issue transition CH-99 "In Progress"

# Add a comment
ebjira issue comment CH-99 "Started working on this"

# Transition to Done with a comment
ebjira issue transition CH-99 "Done" --comment "Shipped in v2.1"
```

### Explore a project

```bash
ebjira project view EARL                              # Project details
ebjira project statuses EARL                          # Statuses per issue type
ebjira project components EARL                        # Components
ebjira issue meta EARL                                # Issue types + create metadata
ebjira issue list --project EARL --limit 100          # All recent issues
ebjira epic list --project EARL                       # Epics
ebjira epic children CH-10                          # Issues under an epic
```

### Bulk-read with field selection

```bash
# Get just keys and summaries for scripting
ebjira issue list --project EARL --limit 100 --json key,summary

# Get assignee workload
ebjira issue list --project EARL --status "In Progress" --json key,assignee,summary
```

### Manage workflows and schemes

```bash
# View current workflows
ebjira workflow list --format table

# Create a custom workflow
ebjira workflow create --name "AI Draft Flow" --statuses "Prioritized,In Progress,Blocked,Ready For Review,Done"

# Create a workflow scheme and assign to project
ebjira workflowscheme create --name "EarlBear Scheme"
ebjira workflowscheme assign 10001 --project EARL

# Create an issue type scheme and assign to project
ebjira issuetypescheme create --name "EarlBear Types" --issuetypes 10001,10002,10003
ebjira issuetypescheme assign 10001 --project EARL

# Manage components
ebjira component create --project EARL --name "discovery-toolkit" --description "Finding stores"
ebjira component list --project EARL --format table
```

### Bulk operations

```bash
# Transition all issues matching a JQL query
ebjira bulk transition --jql "project = EARL AND status = 'Prioritized' AND labels = batch-1" "In Progress"

# Bulk update fields
ebjira bulk update --jql "project = EARL AND component = old-name" --labels migrated
```

### Link issues

```bash
# See available link types
ebjira issuelink types

# Create a "blocks" link
ebjira issuelink create CH-42 CH-43 --type "blocks"

# Remove a link
ebjira issuelink delete 12345
```

### Attach a file from the host machine

```bash
# Encode the file, then pass as base64 (because the CLI runs in Docker)
base64 < report.pdf | ebjira attachment add CH-42 "$(cat -)" --base64 --filename report.pdf

# Or more practically with a variable:
B64=$(base64 < report.pdf)
ebjira attachment add CH-42 "$B64" --base64 --filename report.pdf
```

## Docker Nuances

The CLI runs inside a Docker container. The `bin/ebjira` wrapper handles this transparently:

```
bin/ebjira issue list --project EARL
  -> docker run --rm --env-file .env ebjira issue list --project EARL
       -> Python CLI inside container -> Jira REST API
            -> JSON to stdout
```

Key implications:

- **File paths in `attachment add` are container-local.** A path like `/tmp/file.pdf` refers to the container filesystem, not the host. Use `--base64 --filename` to pass host file content.
- **Rebuild after code changes:** `make ebjira-build` (or `docker build -t ebjira jira-cli/`). The wrapper auto-builds on first run if the image is missing, but not on code changes.
- **Force rebuild:** `make ebjira-rebuild` (uses `--no-cache`).
- **Credentials come from `.env`** via Docker's `--env-file`. The container never stores credentials.
- **No persistent state.** Each invocation is a fresh `docker run --rm`.

## API Nuances

### Search endpoint

The CLI uses the enhanced `/rest/api/3/search/jql` endpoint (POST), not the classic `/rest/api/3/search` (GET) which returns **410 Gone** (deprecated by Atlassian).

The enhanced endpoint **requires an explicit `fields` parameter** in the POST body. If omitted, you get an empty `fields` object in each issue. The `issue list` command handles this automatically.

The enhanced endpoint uses **token-based pagination** (`nextPageToken`), not offset-based (`startAt`/`total`). The client's `search_jql_all()` method handles multi-page result sets transparently.

### Descriptions and comments use ADF

Jira Cloud v3 API uses **Atlassian Document Format (ADF)**, not plain text or HTML:

```json
{
  "type": "doc",
  "version": 1,
  "content": [
    {
      "type": "paragraph",
      "content": [{"type": "text", "text": "Your text here"}]
    }
  ]
}
```

The `issue create`, `issue update`, and `issue comment` commands accept plain text strings and wrap them in ADF automatically. If you need rich formatting (headings, lists, links), pass a `--fields` JSON string with the full ADF structure:

```bash
ebjira issue create --project EARL --type Task --summary "Rich desc" \
  --fields '{"description": {"type": "doc", "version": 1, "content": [{"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Overview"}]}, {"type": "bulletList", "content": [{"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Item 1"}]}]}]}]}}'
```

### Authentication

Uses HTTP Basic Auth with email + API token. Credentials are read from environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `JIRA_BASE_URL` | Yes | e.g. `https://yoursite.atlassian.net` |
| `JIRA_USER_EMAIL` | Yes | Atlassian account email |
| `JIRA_API_TOKEN` | Yes | API token from https://id.atlassian.com/manage-profile/security/api-tokens |

### Path helpers

The client exposes two path builders: `client.platform("/issue/CH-42")` for REST API v3, and `client.agile("/board/1")` for Agile API 1.0. Commands use these to build correct paths.

## Error Handling

Errors are emitted as JSON to **stderr** with exit code **1**:

```bash
$ ebjira issue view CH-999
{"error": "JIRA_404", "message": "Issue CH-999 not found", "status": 1}
$ echo $?
1
```

Config errors (missing `.env`, missing credentials) exit with code **2**:

```bash
$ ebjira issue list
{"error": "CONFIG_MISSING", "message": "Missing required config: JIRA_API_TOKEN"}
$ echo $?
2
```

Parse stdout (data) and stderr (errors) separately. In bash:

```bash
result=$(ebjira issue view CH-42 2>/dev/null) && echo "OK: $result" || echo "FAIL"
```

## Extending the CLI

### File structure

One file per command group in `jira-cli/src/ebjira/commands/`. Each file exports a Typer sub-app (28 groups):

```
jira-cli/src/ebjira/
  commands/
    issue.py            -> issue_app
    issuetype.py        -> issuetype_app
    issuetypescheme.py  -> issuetypescheme_app
    project.py          -> project_app
    sprint.py           -> sprint_app
    board.py            -> board_app
    epic.py             -> epic_app
    field.py            -> field_app
    filter.py           -> filter_app
    workflow.py         -> workflow_app
    workflowscheme.py   -> workflowscheme_app
    status.py           -> status_app
    component.py        -> component_app
    issuelink.py        -> issuelink_app
    bulk.py             -> bulk_app
    cache.py            -> cache_app
    log.py              -> log_app
    attachment.py       -> attachment_app
    user.py             -> user_app
    server.py           -> server_app
    dashboard.py        -> dashboard_app
    worklog.py          -> worklog_app
    label.py            -> label_app
    priority.py         -> priority_app
    resolution.py       -> resolution_app
    model.py            -> model_app
    report.py           -> report_app
    ...
  models/
    issue.py          -> IssueSummary, IssueDetail, Transition
    common.py         -> IssueType, Attachment, ...
    ...
  client.py           -> JiraClient (httpx-based)
  output.py           -> Format enum, output_result()
  config.py           -> Environment variable loading
  main.py             -> Root app, registers all sub-apps
```

### Adding a new command group

1. Create `commands/newgroup.py`:

```python
from __future__ import annotations
from typing import Annotated, Optional
import typer
from ebjira.client import get_client
from ebjira.output import Format, output_result

newgroup_app = typer.Typer(no_args_is_help=True)

@newgroup_app.command("list")
def list_items(
    format: Annotated[Format, typer.Option("--format", "-f")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j")] = None,
) -> None:
    """List all items."""
    client = get_client()
    data = client.get(client.platform("/newgroup"))
    output_result(data, format=format, json_fields=json_fields)
```

2. Register in `main.py` inside `_register_commands()`:

```python
from ebjira.commands.newgroup import newgroup_app
app.add_typer(newgroup_app, name="newgroup", help="Manage new things")
```

3. Add Pydantic models in `models/newgroup.py` if the response needs parsing.

4. Rebuild: `make ebjira-build`.

### Conventions

- Every command supports `--format` and `--json` options.
- Use `get_client()` singleton — never instantiate `JiraClient` directly.
- Use `client.platform()` for v3 paths, `client.agile()` for Agile paths.
- Use `output_result()` for all output — never `print()` directly (except `output_error()`).
- Use `client.get_paginated()` for offset-based pagination, `client.get_agile_paginated()` for Agile endpoints, `client.search_jql_all()` for JQL search.
- Commands accept plain text for descriptions/comments and wrap in ADF internally.
- Typer `Annotated` syntax for all options/arguments.
