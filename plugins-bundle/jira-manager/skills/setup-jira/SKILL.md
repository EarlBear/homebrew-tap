# Setup Jira MCP

> **Context:** This skill installs the Jira MCP server (`@rokealvo/jira-mcp`) in project scope so Claude Code can read and write Jira issues, comments, transitions, and more. Credentials are stored in `.env` (never committed).
>
> **Why not the official Atlassian MCP?** The official server (`https://mcp.atlassian.com/v1/mcp`) requires Atlassian Rovo, which is only available on paid Cloud plans (Standard+) and requires a business domain email. `@rokealvo/jira-mcp` works with any Jira tier (including Free), supports Server/Data Center, and needs only a personal API token.

## When to trigger

User says things like:
- "setup jira", "install jira mcp"
- "connect to jira", "add jira integration"
- "I want to use jira with claude"

## What it provides

Once installed, Claude Code gains 16 Jira tools:

| Tool | Description |
|------|-------------|
| `search_issues` | JQL search |
| `get_issue` | Fetch issue details |
| `create_issue` | Create new issues |
| `update_issue` | Modify issue fields |
| `add_comment` | Comment on issues |
| `get_transitions` | List available status transitions |
| `transition_issue` | Move issue to new status |
| `get_epic_children` | List issues under an epic |
| `add_attachment` | Attach files to issues |
| `get_create_meta` | Get project/issue type metadata |
| `get_field_options` | List allowed values for fields |
| `get_projects` | List accessible projects |
| `get_users` | Search Jira users |
| `get_server_info` | Server version and info |
| `delete_issue` | Delete an issue |

## Prerequisites

- An Atlassian account with Jira access
- A Jira API token (free to create)
- The Jira instance base URL (e.g., `https://yourcompany.atlassian.net`)

## Workflow

### Step 1: Check existing setup

Check if Jira MCP is already configured:

```bash
cat .claude/settings.json 2>/dev/null | grep -A5 '"jira"' || echo "Not configured yet"
```

If already configured, ask the user if they want to reconfigure or if they're done.

### Step 2: Gather credentials

Check `.env` for existing Jira credentials:

```bash
grep '^JIRA_' .env 2>/dev/null
```

If credentials are missing or incomplete, walk the user through each one:

**JIRA_BASE_URL** — The Jira instance URL:
> What's your Jira URL? It looks like `https://yourcompany.atlassian.net` for Cloud or `https://jira.yourcompany.com` for Server/Data Center.

**JIRA_USER_EMAIL** — The Atlassian account email:
> What email do you use to log into Jira?

**JIRA_API_TOKEN** — An API token (not your password):
> You need a Jira API token. Here's how to create one:
>
> 1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
> 2. Click **Create API token**
> 3. Give it a label like "Claude Code"
> 4. Copy the token (you won't see it again)
>
> Paste the token here.

For Jira Server/Data Center using Personal Access Tokens (PATs), the user should also set `JIRA_AUTH_TYPE=bearer` in `.env`.

### Step 3: Write credentials to .env

Append or update the Jira credentials in `.env`. **Never echo the token to the terminal** — write directly to the file.

```bash
# Only add keys that are missing — don't duplicate
grep -q '^JIRA_BASE_URL=' .env 2>/dev/null || echo 'JIRA_BASE_URL=' >> .env
grep -q '^JIRA_USER_EMAIL=' .env 2>/dev/null || echo 'JIRA_USER_EMAIL=' >> .env
grep -q '^JIRA_API_TOKEN=' .env 2>/dev/null || echo 'JIRA_API_TOKEN=' >> .env
```

Use `sed` to set values (or the Edit tool for `.env`).

### Step 4: Install the MCP server

Run the Makefile target:

```bash
make mcp-jira
```

This runs `claude mcp add -s project` with credentials from `.env`, installing `@rokealvo/jira-mcp` via npx.

**CLI gotcha:** The `claude mcp add` `-e` flag uses variadic parsing — it consumes all subsequent positional arguments. The server name **must come before** `-e` flags:

```bash
# CORRECT — name before -e:
claude mcp add -s project jira -e KEY=val -- npx -y @rokealvo/jira-mcp

# WRONG — name after -e (treated as env var):
claude mcp add -s project -e KEY=val jira -- npx -y @rokealvo/jira-mcp
```

### Step 5: Verify

After installation, confirm the MCP is registered in `.mcp.json` (project root):

```bash
cat .mcp.json | python3 -m json.tool | grep -A10 '"jira"'
```

**Note:** Project-scoped MCP servers are stored in `.mcp.json` at repo root (not `.claude/settings.json`). This file contains credentials in plain text and is gitignored.

Then tell the user:

> Jira MCP is installed. Restart Claude Code (or start a new conversation) for the tools to become available. You can then ask me things like:
>
> - "Search for open bugs in PROJECT"
> - "Create a ticket for..."
> - "What's the status of PROJ-123?"
> - "Move PROJ-456 to Ready For Review"

### Step 6: Troubleshooting

If `make mcp-jira` fails:

| Problem | Fix |
|---------|-----|
| Missing credentials | Check `.env` has all three `JIRA_*` vars set |
| `npx` not found | Install Node.js (brew install node) |
| `claude` not found | Install Claude Code CLI |
| Auth failures at runtime | Verify API token is valid and not expired |
| Wrong Jira URL | Ensure no trailing slash, include `https://` |
| `-e` flag eats the server name | Put the name **before** `-e` flags (see Step 4) |

## Security notes

- **Credentials live in `.env`** which is gitignored. Never commit them.
- **API tokens** can be revoked at any time from https://id.atlassian.com/manage-profile/security/api-tokens
- **Scope is project-local** — the MCP config is in `.mcp.json` at repo root (gitignored), not global.
- The token grants the same permissions as your Jira account. Use a service account with limited permissions if you want tighter access control.
