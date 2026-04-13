# Setup Supabase MCP

> **Context:** This skill installs the Supabase MCP server so Claude Code can manage Supabase tables, rows, storage, and more. Two installation methods: hosted HTTP (recommended, OAuth-based) or npm stdio (service key-based). Credentials for the catalog page are stored in `.env` (never committed).
>
> **Why Supabase?** Supabase provides the Postgres database backing the artifact catalog (`index.html`). The MCP server lets Claude Code create tables, query data, and manage schema directly — no need to leave the conversation.
>
> **Design doc:** See `docs/design-supabase-catalog.md` for security model, RLS policies, and architecture decisions.

## When to trigger

User says things like:
- "setup supabase", "configure supabase"
- "install supabase mcp", "connect to supabase"
- "I want to use supabase with claude"

## What it provides

Once installed, Claude Code gains Supabase tools for:

| Capability | Description |
|------------|-------------|
| Table management | Create, alter, and drop tables |
| Row operations | Insert, update, delete, and query rows |
| Schema inspection | List tables, columns, and constraints |
| SQL execution | Run arbitrary SQL against the project database |
| Storage | Manage buckets and files |
| Auth | Manage users and policies |

## Prerequisites

- Node.js + npx available locally
- A Supabase account (free tier works)
- A Supabase project with API keys

## Workflow

### Step 1: Check existing setup

Check if Supabase MCP is already configured:

```bash
cat .mcp.json 2>/dev/null | python3 -m json.tool | grep -A10 '"supabase"' || echo "Not configured yet"
```

If already configured, ask the user if they want to reconfigure or if they're done.

### Step 2: Guide Supabase project creation (if needed)

If the user doesn't have a Supabase project yet:

> 1. Go to https://supabase.com and sign in (or create an account)
> 2. Click **New Project** and give it a name (e.g., "earlbear")
> 3. Choose a region close to you and set a database password
> 4. Once created, go to **Settings > API** to find your keys

They need three values from **Settings > API**:

- **Project URL** — e.g., `https://xyz.supabase.co`
- **`service_role` key** — secret, full database access (for MCP server)
- **`anon` key** — public, respects Row Level Security (for `index.html` client-side fetching)

### Step 3: Store credentials in .env

Check `.env` for existing Supabase credentials:

```bash
grep '^SUPABASE_' .env 2>/dev/null
```

If credentials are missing or incomplete, walk the user through each one. Append or update in `.env` — **never echo secrets to the terminal**.

```bash
# Only add keys that are missing — don't duplicate
grep -q '^SUPABASE_PROJECT_URL=' .env 2>/dev/null || echo 'SUPABASE_PROJECT_URL=' >> .env
grep -q '^SUPABASE_SERVICE_ROLE_KEY=' .env 2>/dev/null || echo 'SUPABASE_SERVICE_ROLE_KEY=' >> .env
grep -q '^SUPABASE_ANON_KEY=' .env 2>/dev/null || echo 'SUPABASE_ANON_KEY=' >> .env
```

Use `sed` or the Edit tool to set the actual values.

Remind the user:
> `.env` is gitignored — your credentials will never be committed. The `anon` key is safe to embed in client-side HTML (it's public and respects RLS policies). The `service_role` key is SECRET and must never be exposed in browser code.

### Step 4: Install the MCP server

**Option A: Hosted HTTP (recommended)** — Uses Supabase's hosted MCP endpoint with OAuth. No service key needed for the MCP itself.

```bash
claude mcp add --scope project --transport http supabase "https://mcp.supabase.com/mcp?project_ref=YOUR_PROJECT_REF"
```

The `project_ref` is the subdomain of your Supabase URL (e.g., if URL is `https://ldvaleamtfocaueqebvy.supabase.co`, the ref is `ldvaleamtfocaueqebvy`). This authenticates via OAuth — no credentials in `.mcp.json`.

**Option B: npm stdio** — Uses the `@supabase/mcp-server-supabase` npm package with service key auth.

```bash
make mcp-supabase
```

This runs `claude mcp add -s project` with credentials from `.env`, installing via npx.

**CLI gotcha:** The `claude mcp add` `-e` flag uses variadic parsing — the server name **must come before** `-e` flags:

```bash
# CORRECT — name before -e:
claude mcp add -s project supabase -e SUPABASE_PROJECT_URL="..." -e SUPABASE_SERVICE_ROLE_KEY="..." -- npx -y @supabase/mcp-server-supabase
```

**Note:** Even with Option A (hosted), you still need `SUPABASE_ANON_KEY` in `.env` for the `generate-index.sh` catalog page — the MCP doesn't replace the client-side fetch.

### Step 5: Verify

After installation, confirm the MCP is registered in `.mcp.json` (project root):

```bash
cat .mcp.json | python3 -m json.tool | grep -A10 '"supabase"'
```

**Note:** Project-scoped MCP servers are stored in `.mcp.json` at repo root (not `.claude/settings.json`). This file contains credentials in plain text and is gitignored.

Try calling a Supabase MCP tool (e.g., list tables) to confirm connectivity. If it works, tell the user:

> Supabase MCP is installed. Restart Claude Code (or start a new conversation) for the tools to become available. You can then ask me things like:
>
> - "List all tables in my Supabase project"
> - "Create the artifacts table"
> - "Query all published artifacts"
> - "Add a new row to the artifacts table"

### Step 6: Create the artifacts table

After the MCP is working, use it to create the `artifacts` table. This table backs the `index.html` catalog — each row is one card in the artifact catalog.

```sql
CREATE TABLE artifacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug text UNIQUE NOT NULL,
  display_name text NOT NULL,
  description text NOT NULL,
  category text NOT NULL CHECK (category IN ('deck', 'wireframe', 'artifact')),
  icon text NOT NULL,
  href text NOT NULL,
  badge_text text,
  jira_issue_key text,
  jira_issue_url text,
  sort_order integer DEFAULT 0,
  is_published boolean DEFAULT true,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- RLS policies
ALTER TABLE artifacts ENABLE ROW LEVEL SECURITY;

-- Public read access (for index.html anon key fetch)
CREATE POLICY "Public read" ON artifacts FOR SELECT USING (true);

-- Public insert (for "+" modal on catalog page)
CREATE POLICY "Public insert" ON artifacts FOR INSERT WITH CHECK (true);
```

Run this SQL via the Supabase MCP tools. Confirm the table was created by listing tables afterward.

### Step 7: Troubleshooting

If `make mcp-supabase` fails:

| Problem | Fix |
|---------|-----|
| Missing credentials | Check `.env` has `SUPABASE_PROJECT_URL` and `SUPABASE_SERVICE_ROLE_KEY` set |
| `npx` not found | Install Node.js (`brew install node`) |
| `claude` not found | Install Claude Code CLI |
| Auth failures at runtime | Verify `service_role` key is correct (not the `anon` key) |
| Wrong project URL | Ensure it's `https://xyz.supabase.co` with no trailing slash |
| `-e` flag eats the server name | Put the name **before** `-e` flags (see Step 4) |

## Security notes

- **Credentials live in `.env`** which is gitignored. Never commit them.
- **`service_role` key** is SECRET — it bypasses Row Level Security and has full database access. Never expose it in browser code or client-side HTML.
- **`anon` key** is PUBLIC — it respects RLS policies and is safe to embed in `index.html` for client-side fetching.
- **Scope is project-local** — the MCP config is in `.mcp.json` at repo root (gitignored), not global.
- **Use `make mcp-supabase`** (not manual `claude mcp add`) to ensure credentials are read from `.env` consistently.
