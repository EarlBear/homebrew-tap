# Developing CLIs with Parallel Agents

> Use this skill when building a new CLI tool or extending an existing one. Provides a battle-tested methodology for designing, building, testing, and documenting CLIs using parallel Claude Code agents. Derived from the ebjira CLI build (28 command groups, 120+ commands, built in waves with up to 6 parallel agents).

## Methodology Overview

```
Phase 1: Research (3 parallel agents)
  |-- Agent: Analyze existing tools / MCP servers
  |-- Agent: Research target API surface
  |-- Agent: Evaluate CLI frameworks
  v
Phase 2: Design Doc (sequential)
  v
Phase 3: Foundation (sequential, Wave 0)
  |-- pyproject.toml, config, client, output, models, main, Dockerfile, wrapper
  v
Phase 4: Command Groups (parallel agents in worktrees, Wave 1+2)
  |-- Agent A: issue commands
  |-- Agent B: project commands
  |-- Agent C: epic + attachment commands
  |-- Agent D: user + server commands
  |-- Agent E: field commands
  |-- Agent F: issuetype commands
  v
Phase 5: Audit & Fix (focused agents)
  |-- Pagination audit
  |-- API compatibility fixes
  v
Phase 6: Testing (parallel)
  |-- Regression tests
  |-- Discoverability tests (crawl --help tree)
  v
Phase 7: Documentation & Skills
  |-- Usage skill (companion /leveraging-X skill)
  |-- Design doc updates
  |-- CLAUDE.md updates
```

## Tenets

### 1. Docker-first with thin wrappers

CLIs run inside Docker containers. A thin shell wrapper (10-15 lines of bash) sits at `bin/{cli-name}` and does three things: (a) verifies `.env` exists, (b) auto-builds the image on first run, (c) `exec docker run --rm --env-file .env {image} "$@"`. This means:

- **No host language runtime required.** Users don't need Python, Node, or Go installed.
- **Credentials never baked into the image.** Always injected at runtime via `--env-file`.
- **Reproducible builds.** `docker build` is the only build step. No virtualenvs, no `pip install`.
- **Rebuild after code changes.** The Docker COPY layer caches — run `make {cli}-rebuild` or `docker build --no-cache` after editing source.
- **File paths are container-local.** Commands that accept file paths (uploads, exports) need special handling — use `--base64` flags or volume mounts.
- **Keep images small.** Use `python:3.11-slim` (not full). Separate deps COPY (cache layer) from source COPY.

### 2. Auth strategy matches the API

Not all APIs authenticate the same way. Choose the right pattern based on the target API and implement it in the foundation (Wave 0) — every command depends on it.

#### Auth Pattern Decision Tree

| API Auth Type | CLI Pattern | Login/Logout? | Token Storage | Docker Implication |
|--------------|-------------|---------------|---------------|-------------------|
| **Static API token** (Jira, Supabase, Stripe) | Env var in `.env`, injected via `--env-file` | No — token doesn't expire | `.env` file on host | Simple: `--env-file .env` |
| **OAuth 2.0 with refresh** (Google, GitHub, Slack) | `auth login` opens browser, stores refresh token | Yes — `auth login`, `auth logout`, `auth status` | Host-mounted volume for token file | Complex: needs volume mount + browser |
| **OAuth 2.0 device flow** (headless/CI) | `auth login --device` displays code, user visits URL | Yes — same commands | Same token file | Works in containers without browser |
| **Service account / key file** (Google Cloud, AWS) | JSON key file path in env var | No — key doesn't expire | `.env` points to key file, volume-mounted | Mount key file: `-v $KEY_FILE:/app/key.json` |

#### Static Token Auth (simple case, like ebjira)

Token goes in `.env`, injected at runtime. No login command needed.

```python
# config.py
@dataclass
class Config:
    base_url: str = ""
    api_token: str = ""

# client.py — auth in constructor
self._client = httpx.Client(
    auth=(config.email, config.api_token),  # Basic auth
    # OR: headers={"Authorization": f"Bearer {config.api_token}"}
)
```

#### OAuth 2.0 Auth (complex case, like Google Docs)

Requires an `auth` command group, persistent token storage, and automatic refresh.

**`auth` command group (`commands/auth.py`):**

```python
auth_app = typer.Typer(no_args_is_help=True)

@auth_app.command()
def login(device: bool = False):
    """Authenticate with the API. Opens a browser for consent.

    Use --device for headless environments (CI, SSH, containers).
    """
    if device:
        # Device authorization grant — display URL + code, poll for token
        device_resp = httpx.post(DEVICE_AUTH_URL, data={...})
        print(f"Visit: {device_resp['verification_uri']}")
        print(f"Enter code: {device_resp['user_code']}")
        # Poll until user authorizes
        token = _poll_for_token(device_resp["device_code"])
    else:
        # Authorization code grant — start local server, open browser
        # 1. Start temporary HTTP server on localhost:PORT
        # 2. Open browser to consent URL with redirect_uri=localhost:PORT
        # 3. Browser redirects back with auth code
        # 4. Exchange auth code for access + refresh tokens
        token = _browser_oauth_flow()

    _save_token(token)
    output_result({"status": "authenticated", "email": token.get("email", "")})

@auth_app.command()
def logout():
    """Revoke credentials and delete stored tokens."""
    token = _load_token()
    if token:
        httpx.post(REVOKE_URL, data={"token": token["refresh_token"]})
    _delete_token()
    output_result({"status": "logged_out"})

@auth_app.command()
def status():
    """Check authentication status and token validity."""
    token = _load_token()
    if not token:
        output_result({"authenticated": False, "message": "Not logged in. Run: cli auth login"})
        return
    # Validate token is still good
    try:
        _refresh_if_needed(token)
        output_result({"authenticated": True, "email": token.get("email", "")})
    except AuthError:
        output_result({"authenticated": False, "message": "Token expired. Run: cli auth login"})
```

**Token storage:**

```python
# auth.py — token persistence
import json
from pathlib import Path

TOKEN_DIR = Path.home() / ".config" / "{cli-name}"
TOKEN_FILE = TOKEN_DIR / "token.json"

def _save_token(token: dict) -> None:
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(token))
    TOKEN_FILE.chmod(0o600)  # Owner-only read/write

def _load_token() -> dict | None:
    if TOKEN_FILE.is_file():
        return json.loads(TOKEN_FILE.read_text())
    return None

def _delete_token() -> None:
    TOKEN_FILE.unlink(missing_ok=True)
```

**Auto-refresh in client.py:**

```python
class ApiClient:
    def __init__(self) -> None:
        token = _load_token()
        if not token:
            output_error("AUTH_REQUIRED", "Not authenticated. Run: cli auth login")
        self._token = token
        self._client = httpx.Client(timeout=30.0)

    def _get_headers(self) -> dict:
        self._token = _refresh_if_needed(self._token)
        return {"Authorization": f"Bearer {self._token['access_token']}"}

    def get(self, url, **kwargs):
        resp = self._client.get(url, headers=self._get_headers(), **kwargs)
        if resp.status_code == 401:
            # Token was revoked server-side
            output_error("AUTH_EXPIRED", "Session expired. Run: cli auth login")
        return self._handle_response(resp)

def _refresh_if_needed(token: dict) -> dict:
    """Refresh access token if expired. Returns updated token."""
    import time
    if token.get("expires_at", 0) > time.time() + 60:  # 60s buffer
        return token
    resp = httpx.post(TOKEN_URL, data={
        "grant_type": "refresh_token",
        "refresh_token": token["refresh_token"],
        "client_id": CLIENT_ID,
    })
    new_token = resp.json()
    new_token["refresh_token"] = token["refresh_token"]  # Preserve if not rotated
    new_token["expires_at"] = time.time() + new_token["expires_in"]
    _save_token(new_token)
    return new_token
```

**Docker implications for OAuth CLIs:**

The token file lives on the **host** (not in the container). The thin wrapper must volume-mount it:

```bash
# bin/{cli-name} — OAuth-aware thin wrapper
TOKEN_DIR="$HOME/.config/{cli-name}"
mkdir -p "$TOKEN_DIR"

exec docker run --rm \
    --env-file "$ENV_FILE" \
    -v "$TOKEN_DIR:/root/.config/{cli-name}" \  # Mount token storage
    {image} "$@"
```

For `auth login` (browser flow), the container also needs to expose a port for the OAuth redirect:

```bash
# Special case: auth login needs port mapping
if [ "$1" = "auth" ] && [ "$2" = "login" ] && [ "$3" != "--device" ]; then
    exec docker run --rm \
        --env-file "$ENV_FILE" \
        -v "$TOKEN_DIR:/root/.config/{cli-name}" \
        -p 8085:8085 \  # OAuth redirect port
        {image} "$@"
else
    exec docker run --rm \
        --env-file "$ENV_FILE" \
        -v "$TOKEN_DIR:/root/.config/{cli-name}" \
        {image} "$@"
fi
```

Or use `--device` flow (no browser needed) which is more Docker-friendly:

```bash
$ ./bin/gdocs auth login --device
Visit: https://accounts.google.com/o/oauth2/device
Enter code: ABCD-EFGH
Waiting for authorization...
{"status": "authenticated", "email": "omar@earlbear.com"}
```

**Client credentials for OAuth CLIs:**

OAuth requires a `client_id` (and sometimes `client_secret`). These are **not user secrets** — they identify the app, not the user. Options:

| Approach | Where | When |
|----------|-------|------|
| Hardcoded in source | `auth.py` | Public apps (like `gh` CLI) where client_id is not sensitive |
| Env var in `.env` | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Private/internal apps |
| JSON key file | `--credentials-file path` | GCP service accounts |

For Google APIs specifically, you'll create OAuth credentials in the Google Cloud Console and store the client_id/secret in `.env`.

### 3. Agent-first output

JSON is the default output format. Structured errors go to stderr. `--help` at every level. `--help-json` for programmatic introspection. Exit codes are meaningful (0=success, 1=API error, 2=config error). Data goes to stdout, diagnostics to stderr — agents can reliably parse stdout.

### 4. Usage logging mode

CLIs should support a **logging mode** that records every command invocation to an external store (Supabase, a database, or a JSONL file). This is critical for:

- **Agent observability:** when an autonomous agent runs the CLI hundreds of times, you need to see what happened without reading git diffs
- **Debugging failures:** which command failed, what args did it have, what was the error?
- **Performance monitoring:** which commands are slow, which are called most?

**Implementation pattern:**

```python
# In output.py or a new logging.py module
import os, time, json, httpx

LOG_MODE = os.environ.get("CLI_LOG_MODE")  # "supabase", "jsonl", or unset
LOG_URL = os.environ.get("SUPABASE_PROJECT_URL")
LOG_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
LOG_FILE = os.environ.get("CLI_LOG_FILE", ".cli-log.jsonl")
RUN_ID = os.environ.get("CLI_RUN_ID", "")

def log_command(cli: str, command: str, args: str, exit_code: int,
                response_size: int, duration_ms: int, error: str | None = None,
                issue_key: str | None = None):
    if not LOG_MODE:
        return
    entry = {
        "run_id": RUN_ID, "cli": cli, "command": command, "args": args,
        "exit_code": exit_code, "response_size": response_size,
        "duration_ms": duration_ms, "error_message": error, "issue_key": issue_key,
    }
    if LOG_MODE == "supabase" and LOG_URL and LOG_KEY:
        httpx.post(f"{LOG_URL}/rest/v1/agent_logs",
                    headers={"apikey": LOG_KEY, "Authorization": f"Bearer {LOG_KEY}",
                             "Content-Type": "application/json"},
                    json=entry)
    elif LOG_MODE == "jsonl":
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
```

**Activation:** The agent's environment sets `CLI_LOG_MODE=supabase` and `CLI_RUN_ID=run-2026-03-29-08`. Human developers don't set it — logging is off by default. The thin wrapper can inject it:

```bash
# In bin/{cli-name} — only when AGENT_MODE is set
if [ -n "${AGENT_MODE:-}" ]; then
    extra_env="-e CLI_LOG_MODE=supabase -e CLI_RUN_ID=${CLI_RUN_ID:-}"
fi
exec docker run --rm --env-file "$ENV_FILE" $extra_env {image} "$@"
```

**Where logs go — NOT in git:**

| Data | Where | Why |
|------|-------|-----|
| CLI command logs | Supabase `agent_logs` table | Queryable, no git bloat |
| Run summaries | Supabase `agent_runs` table | Aggregated metrics |
| Artifacts + research | Git branch `.earl/` directory | Valuable output |
| Verbose responses | Supabase or /dev/null | Too large for git, too noisy for Jira |

Git repos have soft limits (~1GB recommended, 5GB warning on GitHub). CLI logs in git would bloat the repo fast — 1000 runs * 100KB/run = 100MB of logs. Supabase is the right home for operational data.

### 3. One file per command group

Each command group is a self-contained Typer sub-app in `commands/{group}.py`. This is what makes parallel development possible — agents never edit the same file (except `main.py` registration, which is a one-liner merge).

### 4. Plan first, confirm with user, then build

Present the wave breakdown and agent assignments to the user before coding. Use `EnterPlanMode` for complex builds. Use `TaskCreate`/`TaskUpdate` throughout to give the user live progress visibility.

## Phase 1: Research (Parallel)

Spawn 3 agents in parallel to answer orthogonal questions:

| Agent | Question | Output |
|-------|----------|--------|
| API Surface | What endpoints exist? How many? What are the most valuable groups? | Categorized endpoint inventory with priorities |
| Existing Tools | What do current tools (MCP servers, existing CLIs) cover? What gaps exist? | Gap analysis: covered vs. missing |
| Framework Eval | Which CLI framework best fits? (Typer vs. Click vs. argparse vs. Go cobra) | Decision table with rationale |

**Key principle:** Each agent researches independently, then you synthesize into a design doc. Do not start coding until research is complete.

### Framework Decision Criteria

| Criterion | Why It Matters |
|-----------|----------------|
| Type-hint-driven | Reduces boilerplate, auto-generates help |
| Hierarchical subcommands | `cli noun verb` pattern needs nested groups |
| Built-in help generation | Agents discover via `--help` at every level |
| JSON output support | Agent-first means structured output by default |
| Error handling | Structured errors to stderr, clean exit codes |

**Recommended stack for Python CLIs:**

- **Typer** -- type-hint CLI framework (built on Click)
- **httpx** -- modern HTTP client with connection pooling
- **Rich** -- tables, JSON pretty-printing (bundled with Typer)
- **Pydantic** -- response models for type-safe JSON output

## Phase 2: Design Doc + Architecture Diagrams

Create **two documents** before writing any code:

1. **Design doc** (`docs/design-{cli-name}.md`) -- the textual plan and contract for agents
2. **Architecture diagram doc** (`docs/{cli-name}-architecture.md`) -- Mermaid diagrams showing system structure, data flow, command hierarchy, and component relationships

The design doc is the *what* and *why*. The architecture doc is the *how it fits together* — visual, scannable, always up to date with the code.

### Design Doc Required Sections

1. **Problem statement** -- what exists today, what is missing
2. **Goals** -- numbered, prioritized
3. **Technology decision** -- framework choice with rationale table
4. **Architecture** -- containerized execution diagram, file layout
5. **Command inventory** -- every command, its API endpoint, grouped by phase
6. **Help system design** -- progressive discovery, `--help-json` introspection
7. **Output strategy** -- default JSON, table, plain formats with examples
8. **Error handling** -- structured errors to stderr, exit codes
9. **Config loading** -- env vars, precedence, validation
10. **Parallel agent strategy** -- wave breakdown, agent assignments, prompt template
11. **Makefile integration** -- build, test, lint targets
12. **Open questions** -- deferred decisions

### Design Doc Template

```markdown
# Design: {Project Name} CLI (`{cli-name}`)

## Problem
[What exists, what is missing, why a CLI]

## Goals
1. [Primary goal]
2. [Secondary goal]
3. Agent-first design -- JSON output by default, discoverable --help

## Decision: {Language} + {Framework}
| Choice | Rationale |
|--------|-----------|
| ... | ... |

## Architecture
### Containerized Execution
[Diagram: wrapper -> docker run -> CLI -> API -> stdout]

### File Layout
[Directory tree]

## Command Groups -- Full Inventory
### Phase 1: [category]
| Command | API Endpoint |
|---------|--------------|
| ... | ... |

## Help System Design
[Progressive discovery examples]

## Implementation Plan
### Wave 0 -- Foundation (sequential)
### Wave 1 -- [Category] (N parallel agents)
### Wave 2 -- [Category] (N parallel agents)

### Agent Prompt Template
[The template each agent receives]

## Makefile Integration
## Open Questions
```

### Architecture Diagram Doc (`docs/{cli-name}-architecture.md`)

Create a companion doc with Mermaid diagrams alongside the design doc. This is the visual reference that keeps the team (and future agents) oriented. It must contain:

1. **System context diagram** -- where the CLI sits (user → wrapper → container → API)
2. **Component diagram** -- internal modules (main.py, client.py, output.py, commands/, models/)
3. **Command hierarchy** -- full tree of `cli noun verb` commands
4. **Data flow** -- how a request flows from CLI invocation to JSON output
5. **Module dependency graph** -- which modules import what (no circular deps)
6. **Pagination strategy diagram** -- which endpoints use which pagination pattern

#### Required Mermaid Diagrams

```markdown
## System Context
(flowchart showing: User/Agent → bin/wrapper → Docker → Typer CLI → HTTP Client → REST API)

## Component Architecture
(block diagram showing internal modules and their relationships)

## Command Hierarchy
(mindmap or tree of all command groups and their subcommands)

## Request Flow
(sequence diagram: CLI → config → client → API → response → model → output)

## Module Dependencies
(graph showing import relationships between modules)
```

**When to update:** Any time you add a command group, change the client interface, modify output formatting, or restructure modules. The architecture doc is a living document — listed in CLAUDE.md's living docs table.

### Task Tracking

Use `TaskCreate` and `TaskUpdate` throughout the build to track progress and give the user visibility. Create tasks at the start of each phase and mark them complete as you go.

**Wave 0 task pattern:**
```
Task 1: Scaffold pyproject.toml and package init
Task 2: Implement config.py
Task 3: Implement client.py
Task 4: Implement output.py
Task 5: Implement base Pydantic models
Task 6: Implement main.py
Task 7: Add Makefile targets
Task 8: Create architecture diagram doc
```

**Wave 1+ task pattern (one task per agent):**
```
Task 9: Build issue command group (6 parallel agents)
Task 10: Build project command group
...
```

Mark each task `in_progress` when starting, `completed` when done. This gives the user a live progress view and helps you track what's left.

### Planning Phase

Before jumping into code, present the plan to the user for alignment. Use `EnterPlanMode` if the task is complex. The plan should show:

1. **Wave breakdown** with agent assignments
2. **Dependency graph** -- what blocks what
3. **Estimated command count** per wave
4. **Risk areas** -- which commands are tricky (pagination, file uploads, etc.)

Get explicit user confirmation before proceeding to Wave 0. The plan is the moment to catch misunderstandings (wrong framework, missing command groups, architectural disagreements) before 6 agents start building in parallel.

## Phase 3: Foundation (Sequential -- Wave 0)

**This phase MUST be sequential.** These files are shared interfaces that every parallel agent will depend on. If the foundation has bugs or unclear APIs, every agent will independently work around them differently, creating a mess.

### Foundation Files (build in this order)

| Order | File | Purpose | Key Design Decisions |
|-------|------|---------|---------------------|
| 1 | `pyproject.toml` | Package config, entry point, dependencies | Pin dependency versions |
| 2 | `config.py` | Env var loading, validation, singleton | Dataclass, `get_config()` singleton, `validate()` returns missing fields |
| 3 | `client.py` | HTTP client, auth, pagination, error handling | Singleton via `get_client()`, path helpers (`platform()`, `agile()`), multiple pagination strategies |
| 4 | `output.py` | Format dispatcher (json/table/plain), field selection | `output_result()` is the only way to emit data, `output_error()` for errors to stderr |
| 5 | `models/` | Pydantic response models | `populate_by_name=True` for Jira's camelCase fields, `Field(alias=...)` |
| 6 | `main.py` | Root Typer app, `--help-json`, command registration | `_register_commands()` function, `--help-json` callback, global error handler |
| 7 | `Dockerfile` | Container image | Separate COPY for deps (cache layer) vs source |
| 8 | `bin/{cli-name}` | Thin shell wrapper | Auto-builds image, injects `--env-file .env`, `exec docker run --rm` |

### Foundation Code Patterns

**Config singleton** (`config.py`):

```python
@dataclass
class AppConfig:
    base_url: str = ""
    api_token: str = ""
    # ... all env vars as fields

    def validate(self) -> list[str]:
        """Return list of missing required fields."""
        missing = []
        if not self.base_url:
            missing.append("BASE_URL")
        return missing

_config: AppConfig | None = None

def get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = load_config()
    return _config
```

**HTTP client singleton** (`client.py`):

```python
class ApiClient:
    def __init__(self) -> None:
        config = get_config()
        missing = config.validate()
        if missing:
            output_error("CONFIG_MISSING", f"Missing: {', '.join(missing)}")
        self._client = httpx.Client(
            base_url=config.base_url,
            auth=(config.user_email, config.api_token),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30.0,
        )

    def get(self, path, params=None): ...
    def post(self, path, json=None): ...
    def put(self, path, json=None): ...
    def delete(self, path, params=None): ...

    def get_paginated(self, path, results_key="values", params=None, max_results=None):
        """Offset-based pagination (startAt/maxResults)."""
        ...

    def platform(self, path: str) -> str:
        """Build API v3 path: /rest/api/3{path}"""
        return f"/rest/api/3{path}"

_client: ApiClient | None = None

def get_client() -> ApiClient:
    global _client
    if _client is None:
        _client = ApiClient()
    return _client
```

**Output dispatcher** (`output.py`):

```python
class Format(str, Enum):
    json = "json"
    table = "table"
    plain = "plain"

def output_result(data, format=Format.json, json_fields=None, columns=None):
    """The ONLY way to emit data. JSON to stdout."""
    if json_fields:
        data = _pick_fields(data, json_fields.split(","))
    if format == Format.json:
        print(json.dumps(data, indent=2, default=str))
    elif format == Format.table:
        _output_table(data, columns)
    elif format == Format.plain:
        _output_plain(data)

def output_error(error: str, message: str, status: int = 1):
    """Errors to stderr as JSON, then exit."""
    print(json.dumps({"error": error, "message": message}), file=sys.stderr)
    raise SystemExit(status)
```

**Root app** (`main.py`):

```python
app = typer.Typer(name="mycli", help="...", no_args_is_help=True, pretty_exceptions_enable=False)

def _register_commands() -> None:
    from myapp.commands.issue import issue_app
    app.add_typer(issue_app, name="issue", help="Manage issues")
    # ... one line per command group

_register_commands()

def main() -> None:
    try:
        app()
    except ApiError as e:
        output_error(f"API_{e.status_code}", e.message)
    except KeyboardInterrupt:
        raise SystemExit(130)
```

**Thin shell wrapper** (`bin/{cli-name}`):

```bash
#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo '{"error": "CONFIG_MISSING", "message": ".env not found"}' >&2
    exit 2
fi

# Auto-build on first run
if ! docker image inspect mycli >/dev/null 2>&1; then
    echo '{"status": "building", "message": "Building image..."}' >&2
    docker build -t mycli -q "$REPO_ROOT/cli-dir" >&2
fi

exec docker run --rm --env-file "$ENV_FILE" mycli "$@"
```

**Dockerfile:**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir ".[dev]"
COPY src/ src/
COPY tests/ tests/
RUN pip install --no-cache-dir ".[dev]"
ENTRYPOINT ["mycli"]
```

### Validation Before Proceeding

Before spawning parallel agents, verify the foundation works end-to-end:

```bash
# Build the image
docker build -t mycli cli-dir/

# Verify entry point
docker run --rm --env-file .env mycli --help
docker run --rm --env-file .env mycli --version
docker run --rm --env-file .env mycli --help-json

# Verify error handling
docker run --rm mycli --help  # Should fail with CONFIG_MISSING
```

## Phase 4: Command Groups (Parallel Agents in Worktrees)

### Partitioning Rules

1. **One file per command group.** Each command group is a self-contained Typer sub-app in `commands/{group}.py`.
2. **3-8 commands per agent.** Too few wastes agent overhead. Too many creates merge conflicts.
3. **Group by API domain, not by verb.** `issue list/view/create/update/delete` goes to one agent, not separate agents for all `list` commands.
4. **Pair small groups.** If a command group has only 1-2 commands, pair it with a related group (e.g., `epic` + `attachment`, `user` + `server`).
5. **Max 6 parallel agents.** Beyond this, merge conflicts and coordination overhead outweigh speed gains.

### Worktree Isolation

Each agent works in an isolated git worktree to avoid file conflicts:

```bash
# Create worktrees for each agent
git worktree add ../mycli-agent-a -b agent/issue-commands
git worktree add ../mycli-agent-b -b agent/project-commands
git worktree add ../mycli-agent-c -b agent/epic-attachment-commands
# ...
```

Each agent creates files only in its assigned scope:
- `commands/{assigned_group}.py`
- `models/{assigned_group}.py`
- `tests/test_{assigned_group}.py`
- One line added to `main.py` `_register_commands()` (merge later)

### Agent Prompt Template

Use this template for each parallel agent. Fill in the bracketed sections.

```
You are building the `{command_group}` command group for the {cli_name} CLI.

## Foundation Code

The foundation is already built at `{cli_dir}/src/{package}/`. Read these files first:
- `client.py` — use `get_client()` for all API calls. Never instantiate the client directly.
- `output.py` — use `output_result(data, format, json_fields)` for ALL output. Never print() directly.
- `config.py` — use `get_config()` for settings. Credentials come from env vars.
- `models/` — add Pydantic models here. Use `Field(alias="camelCase")` and `populate_by_name=True`.
- `main.py` — register your sub-app here after building it.

## Your Task

1. Create `commands/{file}.py` with a Typer sub-app named `{group}_app`
2. Implement these commands:
{command_list_with_api_endpoints}
3. Create Pydantic models in `models/{file}.py` for API responses
4. Register the sub-app in `main.py`:
   ```python
   from {package}.commands.{file} import {group}_app
   app.add_typer({group}_app, name="{group}", help="{description}")
   ```

## Conventions (MUST follow)

- Every command supports `--format json|table|plain` (default: json) and `--json` field selection
- Use `Annotated[Type, typer.Option(...)]` syntax for all options
- Use `client.platform("/path")` for REST API paths, `client.agile("/path")` for Agile paths
- Use `client.get_paginated()` for list endpoints with offset pagination
- Use `client.get_agile_paginated()` for Agile endpoints (isLast-based)
- Add docstrings with examples to every command
- Errors are raised as exceptions — the root app catches them
- Module docstring with usage examples at top of file

## Command Pattern

Every command follows noun-verb: `{cli_name} {group} {verb}`

```python
from __future__ import annotations
from typing import Annotated, Optional
import typer
from {package}.client import get_client
from {package}.output import Format, output_result

{group}_app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")

FormatOption = Annotated[Format, typer.Option("--format", "-f", help="Output format.")]
JsonOption = Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")]

@{group}_app.command("list")
def list_{group}s(
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """List all {group}s.

    Examples:
        $ {cli_name} {group} list
        $ {cli_name} {group} list --format table
    """
    client = get_client()
    data = client.get_paginated(client.platform("/{endpoint}"))
    output_result(data, format=format, json_fields=json_fields)
```

## API Endpoints

{endpoint_table}
```

### Merging Agent Work

After all agents complete:

1. **Copy new files first** (no conflict risk) -- new command files, new test files.
2. **Merge shared files carefully** -- `models/common.py`, `main.py`, `client.py` may be modified by multiple agents. Use the Edit tool to merge additions from each wave into the canonical copy. Do NOT overwrite — merge.
3. **Fix `main.py` registration** -- combine all agents' `_register_commands()` additions into one file.
4. **Run full test suite in Docker** -- `make {cli}-test` (e.g., `make jira-cli-test`). This is the **merge gate**. All tests must pass in the Docker container before committing. Never validate with local `pip install`.
5. **Smoke test** -- `docker build`, `cli --help`, verify all groups appear.

### Parallel Agent Gotchas

- **Agents can't see each other.** Each worktree is isolated. If Wave 1 adds a model and Wave 2 adds a different model to the same file, only one survives a naive copy. Always merge shared files with the Edit tool.
- **Agents can't run Docker.** Worktree agents don't have Docker access. They can only write code and unit tests. Docker validation happens in the parent after merge.
- **Don't let agents modify CLAUDE.md or living docs.** These should only be updated by the parent after all waves are merged and validated.
- **Test counts lie in isolation.** A wave's 26 tests may pass alone but fail after merge if imports or models clash. The full-suite Docker run is the only trustworthy signal.

## Phase 5: Audit and Fix (Focused Agents)

After the parallel build, dedicate focused agents to cross-cutting concerns that span all command groups.

### Pagination Audit

Spawn one agent to audit every command that returns lists:

```
Audit all commands in {cli_dir}/src/{package}/commands/ for correct pagination.

For each list/search command:
1. Identify which pagination pattern the API endpoint uses:
   - Offset-based (startAt/maxResults/total) -> use client.get_paginated()
   - Token-based (nextPageToken/isLast) -> use client.search_jql_all() or custom
   - Agile-style (isLast flag, no total) -> use client.get_agile_paginated()
   - No pagination (returns all results) -> use client.get() directly
2. Verify the command uses the correct pagination method
3. Verify --limit is passed through correctly
4. Fix any mismatches

Common mistakes:
- Using get_paginated() for token-based APIs (search/jql)
- Using get() for endpoints that paginate (silently truncates at page 1)
- Not passing max_results through to pagination methods
```

### API Compatibility Audit

```
Test every command against the live API. For each command:
1. Run with --help to verify it works
2. Run a basic invocation (list with defaults, view with a known ID)
3. Document any API errors (404, 403, field name mismatches)
4. Fix response parsing issues (missing fields, wrong aliases)
```

## Phase 6: Testing (Parallel)

### Discoverability Tests

The most important test for a CLI: can agents find and use every command?

```python
"""Discoverability tests — verify the entire --help tree is navigable."""

import subprocess

def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "run", "--rm", "mycli", *args],
        capture_output=True, text=True, timeout=30,
    )

def test_root_help():
    """Root --help lists all command groups."""
    result = run_cli("--help")
    assert result.returncode == 0
    for group in ["issue", "project", "sprint", "board", "field", "user"]:
        assert group in result.stdout, f"Missing group: {group}"

def test_all_groups_have_help():
    """Every command group responds to --help."""
    result = run_cli("--help")
    # Parse group names from help output
    groups = [line.split()[0] for line in result.stdout.splitlines()
              if line.strip() and not line.startswith(" ") and not line.startswith("Usage")]
    for group in groups:
        sub = run_cli(group, "--help")
        assert sub.returncode == 0, f"{group} --help failed"

def test_help_json_complete():
    """--help-json includes all registered commands."""
    result = run_cli("--help-json")
    assert result.returncode == 0
    import json
    tree = json.loads(result.stdout)
    assert "commands" in tree
    # Verify known command groups exist
    for group in ["issue", "project"]:
        assert group in tree["commands"]
```

### Regression Tests

For each command group, test:
1. **Happy path** -- basic invocation returns valid JSON
2. **Field selection** -- `--json key,summary` filters output
3. **Format modes** -- `--format table` and `--format plain` do not crash
4. **Error handling** -- invalid IDs return structured error to stderr, exit code 1
5. **Pagination** -- `--limit` is respected

### Test Organization

```
tests/
  test_issue.py        # One test file per command group
  test_project.py
  test_sprint.py
  test_discover.py     # Discoverability tests (crawl --help tree)
  conftest.py          # Shared fixtures, docker helpers
```

## Phase 7: Documentation and Skills

### Companion Usage Skill

After building the CLI, create a `/leveraging-{cli-name}` skill that teaches agents (and humans) how to use it. This skill should contain:

1. **Quick reference** -- every command with a one-liner example
2. **Output formats** -- JSON (default), table, plain, field selection
3. **Discovery pattern** -- `--help` at every level, `--help-json` for agents
4. **Common workflows** -- multi-step recipes (create -> transition -> comment)
5. **Docker nuances** -- file paths are container-local, rebuild after changes
6. **API nuances** -- pagination quirks, ADF format, deprecated endpoints
7. **Error handling** -- stderr vs stdout, exit codes
8. **Extending the CLI** -- how to add a new command group

### Living Documentation Updates

After the CLI is built, update in the same changeset:
- **Design doc** -- mark completed phases, update open questions
- **CLAUDE.md** -- add CLI section with architecture, quick start, gotchas
- **.env.example** -- add any new env vars (without values)
- **Makefile** -- add build, test, lint, help targets

## Phase 8: Manifest-Driven Conformance

When a CLI manages an external system (Jira, Shopify, Supabase, etc.), add a **declarative manifest** that defines the desired state and scripts to enforce it.

### The Manifest Pattern

```
{cli-name}/manifest.yaml       # Desired state (single source of truth)
scripts/{system}-conform.py    # Discover → diff → plan → apply
scripts/{system}-integration-test.py  # Verify live state matches manifest
```

### Manifest File (`manifest.yaml`)

YAML file at the CLI root that declares all configuration for the managed system. Sections vary by system but follow a common structure:

```yaml
version: "1"
project:
  key: PROJ
  name: My Project
  site: https://example.com

# Infrastructure sections (statuses, types, components, etc.)
statuses: [...]
workflow: {name, transitions: [...]}
components: [...]

# Operational sections (agent config, board layout, labels)
agent: {jql_queries, allowed_transitions, ...}
board: {columns: [...], quick_filters: [...]}

# Retired items (for migration tracking)
retired:
  statuses: [Old Status 1, Old Status 2]
```

### Conform Script (`scripts/{system}-conform.py`)

Three subcommands: `discover`, `diff`, `plan`

```bash
# Discover: snapshot current live state
python scripts/jira-conform.py discover --project EARL

# Diff: compare manifest vs live state
python scripts/jira-conform.py diff --project EARL

# Plan: produce an apply plan (like terraform plan)
python scripts/jira-conform.py plan --project EARL --output plan.json
```

The conform script should:
- Be **read-only by default** (discover and diff never mutate)
- Detect **breaking changes** (items with dependencies that would break)
- Produce **human-readable output** for review
- Support **--dry-run** on any mutating operation

### Integration Test Script (`scripts/{system}-integration-test.py`)

Tests that verify the live system matches the manifest. ~10 tests per manifest section.

```bash
python scripts/jira-integration-test.py --project EARL
```

Test categories:
1. **Infrastructure tests** — statuses exist, types exist, components exist
2. **Workflow tests** — transitions are valid, scheme is assigned
3. **Conformance tests** — no drift from manifest
4. **Health tests** — API connectivity, permissions, rate limits

### Two Companion Skills

Split the responsibility cleanly:
- `/manage-{system}-manifest` — **edit** the desired state (add status, change workflow)
- `/conform-{system}` — **enforce** it (diff, apply, diagrams, regression tests)

### CLI Commands

The CLI should have a `manifest` command group:

```bash
{cli} manifest diff      # Compare manifest vs live state
{cli} manifest apply     # Make live state match manifest
{cli} manifest export    # Snapshot live state to YAML
{cli} manifest diagram   # Generate Mermaid diagrams from manifest
```

### When to Use This Pattern

Use manifest-driven conformance when your CLI manages:
- A **stateful external system** (Jira project, Shopify store, Supabase schema)
- Configuration that **drifts** (someone changes it via UI, another team modifies it)
- Setup that should be **reproducible** (new project, disaster recovery, testing)
- Config that **generates documentation** (diagrams, ERDs, guides)

### Examples in EarlBear

| System | Manifest | Conform Script | Integration Tests | Skills |
|--------|----------|---------------|-------------------|--------|
| Jira | `manifests/jira/manifest.yaml` | `scripts/jira-conform.py` | `scripts/jira-integration-test.py` | `/manage-jira-manifest` + `/conform-jira` |
| Shopify | `manifests/shopify/manifest.yaml` | `scripts/shopify-conform.py` | `scripts/shopify-integration-test.py` | `/manage-shopify-store` + `/conform-store` |

## Architecture Patterns

### Containerized CLI

```
User/Agent
    |
    v
bin/{cli-name}          <-- Thin shell wrapper (15 lines)
    |                       - Ensures .env exists
    |                       - Auto-builds Docker image on first run
    |                       - exec docker run --rm --env-file .env {image} "$@"
    v
Docker Container
    |
    v
Python CLI (Typer)      <-- Entry point from pyproject.toml [project.scripts]
    |
    v
HTTP Client (httpx)     <-- Singleton, auth from env vars
    |
    v
REST API                <-- JSON responses
    |
    v
stdout (JSON)           <-- Structured data for agents
stderr (JSON errors)    <-- Structured errors, never to stdout
```

**Why containerize?**
- No host Python pollution
- Consistent across machines
- Credentials injected via `--env-file`, never baked into image
- Rebuild is just `docker build`

### One-File-Per-Command-Group

Each command group is a self-contained module:
- Exports a single `{group}_app = typer.Typer(no_args_is_help=True)`
- Contains all commands for that noun
- Imports only from `client`, `output`, and `models`
- Registered in `main.py` with one `app.add_typer()` call

This pattern makes parallel development possible -- agents never edit the same file (except `main.py` registration, which is a one-liner merge).

### Agent-First Output

| Principle | Implementation |
|-----------|---------------|
| JSON by default | `Format.json` is the default for `--format` |
| Structured errors to stderr | `output_error()` writes JSON to stderr, exits with code 1 |
| Field selection | `--json key,summary,status` filters output fields |
| Programmatic introspection | `--help-json` dumps full command tree as JSON |
| Exit codes are meaningful | 0 = success, 1 = API error, 2 = config error, 130 = interrupt |
| Data on stdout, diagnostics on stderr | Agents can parse stdout reliably |

### Singleton Pattern

Both `config` and `client` use the singleton pattern with explicit `reset_*()` functions for testing:

```python
_instance: Thing | None = None

def get_thing() -> Thing:
    global _instance
    if _instance is None:
        _instance = Thing()
    return _instance

def reset_thing() -> None:
    global _instance
    _instance = None
```

This ensures consistent state across commands in the same invocation while allowing tests to reset between cases.

## Anti-Patterns

### Do Not Skip the Foundation

**Wrong:** Start with parallel agents from day one, let each agent figure out the client, output format, and error handling independently.

**Right:** Build config, client, output, models, and main.py sequentially. Validate end-to-end. Only then spawn parallel agents.

**Why:** Without a foundation, 6 agents will create 6 different HTTP clients, 6 output formats, and 6 error handling strategies. Merging becomes a rewrite.

### Do Not Put Too Many Commands in One Agent

**Wrong:** Give one agent all 80 commands.

**Right:** 3-8 commands per agent, grouped by API domain.

**Why:** Each agent should finish in one session. Overloaded agents lose context, skip testing, and produce inconsistent code.

### Do Not Forget Discoverability Testing

**Wrong:** Test individual commands but never test `--help` navigation.

**Right:** Crawl from root `--help` through every subcommand. Verify `--help-json` includes all commands.

**Why:** A command that works but does not appear in `--help` is invisible to agents. A broken `--help` at any level blocks discovery of everything below it.

### Do Not Mix Pagination Strategies

**Wrong:** Use `get_paginated()` everywhere and hope it works.

**Right:** Audit each API endpoint's pagination style. Use the matching client method.

**Why:** APIs use different pagination patterns. Offset-based (`startAt`/`total`), token-based (`nextPageToken`), and flag-based (`isLast`) all require different handling. Using the wrong one silently returns only page 1.

### Do Not Print Directly

**Wrong:** `print(json.dumps(result))` scattered across commands.

**Right:** Always use `output_result()` for data and `output_error()` for errors.

**Why:** Centralized output means you can add features (color, paging, field selection) in one place. Direct prints bypass format selection and break piping.

### Do Not Store Secrets in the Image

**Wrong:** `ENV API_TOKEN=xyz` in Dockerfile, or `.env` COPY'd into image.

**Right:** Inject via `docker run --env-file .env` at runtime.

**Why:** Docker images are cached and shareable. Baked-in secrets leak.

### Do Not Edit main.py in Parallel

**Wrong:** Every agent modifies `main.py` to register their command group.

**Right:** Each agent adds their registration line, but merging `main.py` is done once at the end by a single coordinator.

**Why:** `main.py` is the one file every agent touches. Handle it as a known merge point, not a race condition.
