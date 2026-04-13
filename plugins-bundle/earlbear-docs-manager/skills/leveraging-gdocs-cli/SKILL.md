# Leveraging the ebdocs CLI

> Use this skill when working with Google Docs — creating documents, sharing, commenting, exporting, linking docs to Jira issues, inserting tables/images, or generating deep links. The ebdocs CLI is the preferred way to interact with Google Docs from agents and humans.

## Prerequisites

- Docker installed (local) or `pip install -e gdocs-cli/[dev]` (cloud agent)
- `.env` configured with Google OAuth or Service Account credentials
- See `docs/sop-google-docs-auth.md` for full setup

## When to Trigger

- User asks to create a Google Doc (report, playbook, design doc, SOP)
- User asks to share a doc with the team
- User asks to link a doc to a Jira issue
- User asks to export a doc as PDF, DOCX, HTML, or TXT
- User asks to add comments or review feedback on a doc
- User asks to insert a table, image, or diagram into a doc
- User asks for a deep link to a specific section, comment, or text in a doc
- Agent needs to produce a deliverable (kind:report, kind:playbook, kind:sop)

## Quick Reference — All 23 Commands

### doc (14 commands)

```bash
# Create
ebdocs doc create --title "Q4 Report" --from-markdown report.md       # From markdown file
ebdocs doc create --title "Sprint Retro" --template TEMPLATE_DOC_ID   # Copy from template
ebdocs doc create --title "Design Doc" --folder-id FOLDER_ID          # Into specific folder

# Read / Write
ebdocs doc read DOC_ID                                                 # Read as JSON (metadata + markdown)
ebdocs doc read DOC_ID --format plain                                  # Read as raw markdown
ebdocs doc write DOC_ID --from-markdown content.md                     # Replace entire body from file
ebdocs doc write DOC_ID --content "# New Section" --append             # Append markdown to end

# List / Delete
ebdocs doc list                                                        # List docs in configured folder
ebdocs doc list --limit 10 --format table                              # Limit + table format
ebdocs doc delete DOC_ID --confirm                                     # Move to trash (requires --confirm)

# Deep Linking
ebdocs doc headings DOC_ID                                             # All headings with anchor URLs
ebdocs doc links DOC_ID                                                # Unified: headings + comments + bookmarks
ebdocs doc highlight DOC_ID --text "62% of stores"                     # Chrome text fragment link
ebdocs doc highlight DOC_ID --text "Dawn" --prefix "Migrate to"        # With disambiguation context

# Bookmarks
ebdocs doc bookmarks DOC_ID                                            # List all bookmarks with URLs
ebdocs doc bookmark-add DOC_ID --name "findings" --at-heading "Key Findings"
ebdocs doc bookmark-add DOC_ID --name "rec-1" --at-text "Migrate to Dawn"
ebdocs doc bookmark-add DOC_ID --name "intro" --at-index 42

# Images
ebdocs doc image DOC_ID --url "https://mermaid.ink/svg/..." --width 468   # From public URL
ebdocs doc image-upload DOC_ID --file diagram.png --width 468             # Upload local file

# Tables
ebdocs doc table DOC_ID --content "Name|Age\nAlice|30\nBob|25"         # Pipe-delimited
ebdocs doc table DOC_ID --from-csv data.csv                            # From CSV file
ebdocs doc table DOC_ID --rows 3 --cols 2                              # Empty table

# Validation
ebdocs doc lint /content/gdocs/vision/foo.md                           # Run validator against a local md without pushing (no Drive id)
ebdocs doc lint /content/gdocs/vision/foo.md --format table            # Human-readable local lint report
ebdocs doc validate DOC_ID                                             # Run rendering invariants against the live doc
ebdocs doc validate DOC_ID --source /content/gdocs/vision/foo.md       # + source-vs-rendered cross-checks (8 checks)
ebdocs doc validate DOC_ID --format table                              # Human-readable report
```

`validate` runs against a **live Drive doc by id** — it fetches the rendered state and checks for rendering drift. `lint` runs against a **local markdown file** without ever touching Drive: it parses the md with `markdown_to_requests` (same converter `sync push` uses), builds a synthetic doc structure from the parsed requests, and runs the same `collect_doc_issues` validator against it. Use `lint` during authoring and in pre-commit hooks; use `validate` after a push to confirm the rendered doc matches expectations.

Both commands catch the known rendering bugs we have fought: headings absorbed into lists, list presets flipped by adjacency, EARL-NNN mentions that failed to auto-linkify, missing mermaid images (degraded-to-code-block advisory), missing code block tables, heading outline drift, transitive list merges across sections, em-dashes in body prose, task list checkboxes rendered literally. Exit code is 0 if every check passes, 1 on any error-severity issue — use in scripts or CI.

`sync push` runs that same validation against every pushed doc by default and exits non-zero on any failure, so automation can gate on the exit code without remembering a flag. Pass `--no-strict` only to skip validation for scratch docs.

### Doc theme

Every pushed doc gets a branded theme applied as a post-push pass: body font, heading fonts, sizes, colors, paragraph spacing, table styling. The theme is defined in `.claude/skills/authoring-drive-docs/theme.yaml` (single source of truth), mounted into the container by `bin/ebdocs` and loaded at push time. To change fonts or colors, edit `theme.yaml` and re-push — no code change needed.

### share (3 commands)

```bash
ebdocs share add DOC_ID --email omar@earlbear.com --role writer        # Share with user
ebdocs share add DOC_ID --email reviewer@co.com --role commenter --message "Please review"
ebdocs share remove DOC_ID --email omar@earlbear.com                   # Revoke access
ebdocs share list DOC_ID                                               # List all permissions
```

Roles: `reader`, `writer`, `commenter`.

### comment (3 commands)

```bash
# Add — returns a direct link to the comment
ebdocs comment add DOC_ID --text "Needs revision on section 3"
ebdocs comment add DOC_ID --text "Clarify this claim" --quoted-text "62% of stores"

# List — each comment includes a URL (?disco=COMMENT_ID)
ebdocs comment list DOC_ID
ebdocs comment list DOC_ID --include-resolved

# Resolve
ebdocs comment resolve DOC_ID COMMENT_ID
```

Comment URLs use the `?disco=COMMENT_ID` format: `https://docs.google.com/document/d/DOC_ID/edit?disco=COMMENT_ID`. These URLs scroll directly to the comment in the doc.

### export (2 commands)

```bash
ebdocs export download DOC_ID --format pdf --output report.pdf         # Download as PDF
ebdocs export download DOC_ID --format docx --output report.docx       # Download as DOCX
ebdocs export download DOC_ID --format html                            # HTML to stdout
ebdocs export download DOC_ID --format txt                             # Plain text to stdout
ebdocs export url DOC_ID                                               # Print the doc's edit URL
```

Supported formats: `pdf`, `docx`, `html`, `txt`. Binary formats (pdf, docx) default to file output; text formats (html, txt) default to stdout.

### link (1 command)

```bash
ebdocs link jira DOC_ID --issue CH-42                                # Link doc to Jira issue
ebdocs link jira DOC_ID --issue CH-42 --comment "Design doc for auth"
```

Posts a comment on the Jira issue containing the Google Docs URL. Requires ebjira CLI (`bin/ebjira`) to be built.

### auth (2 commands)

```bash
ebdocs auth status                                                     # Verify credentials + API access
ebdocs auth login                                                      # One-time OAuth consent flow
```

## Google Docs API Capability Matrix

### Supported

| Feature | CLI Command / Markdown Syntax |
|---------|-------------------------------|
| Headings (H1-H3) with anchor links | `# H1`, `## H2`, `### H3` |
| Bold, italic, bold+italic | `**bold**`, `*italic*`, `***both***` |
| Ordered / unordered / nested lists | `1.`, `-`, indent with spaces |
| Inline code (monospace) | `` `code` `` |
| Fenced code blocks | ` ```language ... ``` ` |
| Links / hyperlinks | `[text](url)` |
| Horizontal rules | `---` |
| Tables | `doc table` or markdown pipe tables in `doc write` |
| Table of Contents | `[TOC]` |
| Page breaks | `---pagebreak---` |
| Footnotes | `[^1]` with `[^1]: text` definition |
| Images (public URL) | `doc image --url` |
| Images (local file upload) | `doc image-upload --file` |
| Bookmarks (named anchors) | `doc bookmark-add` |
| Comments with direct links | `comment add` returns `?disco=ID` URL |
| Chrome text fragment highlights | `doc highlight` returns `#:~:text=` URL |
| PDF / DOCX / HTML / TXT export | `export download` |
| Drive folder placement | `GOOGLE_DRIVE_FOLDER_ID` env var or `--folder-id` |
| Permission management | `share add`, `share remove`, `share list` |

### NOT Supported (Google Docs API Limitation)

These features exist in the Google Docs web UI but cannot be created via the API:

| Feature | Workaround |
|---------|------------|
| Smart chips (Date, People, File, Calendar, Place, Vote, Stopwatch, Timer) | Use plain text or links |
| Building blocks (Meeting notes, Email draft, Task tracker, Decision log) | These are templates — replicate with tables |
| Dropdown menus | Use a table with options listed |
| Variables | Use find-and-replace or template docs |
| Drawing / Chart (inline) | Render as image, upload via `doc image-upload` |
| eSignature | Use DocuSign or similar |
| Audio buttons | Not possible via API |
| AI summary (Gemini) | Not available via API |

## Deep Linking

The CLI generates four types of deep links into Google Docs. Use these in Jira comments, Slack messages, or other docs to point people at specific content.

### Heading Anchors

```bash
ebdocs doc headings DOC_ID --format table
# LEVEL  TEXT              URL
# 1      Executive Summary https://docs.google.com/document/d/.../edit#heading=h.abc123
# 2      Key Findings      https://docs.google.com/document/d/.../edit#heading=h.def456
```

These anchor links work in any browser and scroll directly to the section.

### Unified Link View

```bash
ebdocs doc links DOC_ID --format table
# TYPE      LABEL                          URL
# h1        Executive Summary              .../edit#heading=h.abc123
# h2        Key Findings                   .../edit#heading=h.def456
# comment   "62% of stores..." -> Verify   .../edit?disco=AAA123
# bookmark  findings                       .../edit#bookmark=kix.bbb456
```

Combines headings, open comments, and bookmarks into one view. Great for building a Jira comment with links to specific parts of a doc.

### Chrome Text Fragment Highlights

```bash
# Simple: highlight exact text
ebdocs doc highlight DOC_ID --text "62% of stores report improved conversion"

# With context for disambiguation
ebdocs doc highlight DOC_ID --text "Dawn" --prefix "Migrate to" --suffix "theme"
```

Generates `#:~:text=` URLs. When opened in Chrome/Edge, the browser scrolls to and highlights the matched text in yellow. Works in any Chromium browser.

### Bookmarks (Named Anchors)

```bash
# Create a bookmark at a heading
ebdocs doc bookmark-add DOC_ID --name "findings" --at-heading "Key Findings"

# Create a bookmark at specific text
ebdocs doc bookmark-add DOC_ID --name "recommendation-1" --at-text "Migrate to Dawn"

# Create at exact character index
ebdocs doc bookmark-add DOC_ID --name "intro" --at-index 42

# List existing bookmarks
ebdocs doc bookmarks DOC_ID
```

Bookmarks are named anchors stored in the document. Unlike text fragment highlights, bookmarks are persistent — they survive text edits. The URLs use the format `#bookmark=kix.RANGE_ID`.

### Comment URLs

Every `comment add` and `comment list` call returns a direct URL:

```
https://docs.google.com/document/d/DOC_ID/edit?disco=COMMENT_ID
```

Opening this URL scrolls to the comment and opens the comment thread. Use `--quoted-text` to anchor a comment to specific text in the document.

## Tables

### Pipe-delimited content

```bash
ebdocs doc table DOC_ID --content "Name|Role|Team\nOmar|CEO|Leadership\nSaad|CTO|Leadership"
```

The first row becomes the header. Subsequent rows are data.

### From CSV file

```bash
ebdocs doc table DOC_ID --from-csv metrics.csv
```

Reads a standard CSV file. The first row is treated as headers.

### Empty table skeleton

```bash
ebdocs doc table DOC_ID --rows 3 --cols 2
```

Creates an empty table with placeholder column headers ("Column 1", "Column 2", ...).

### Markdown pipe tables in doc write

Pipe tables in markdown content passed to `doc write` or `doc create --from-markdown` are also rendered as native Google Docs tables:

```markdown
| Metric | Q3 | Q4 |
|--------|----|----|
| Revenue | $1.2M | $1.8M |
| Users | 12K | 18K |
```

### How tables work internally

Tables use a two-pass approach:
1. `insertTable` creates the table structure (rows x cols).
2. The doc is re-fetched to discover cell indices.
3. `insertText` fills each cell's content (in reverse index order to avoid drift).

## Images

### From public URL

```bash
ebdocs doc image DOC_ID --url "https://example.com/chart.png" --width 468
ebdocs doc image DOC_ID --url "https://mermaid.ink/svg/..." --width 468 --height 300
```

The URL must be publicly accessible — Google's servers fetch the image. Supports PNG, JPG, SVG, GIF.

### Upload local file

```bash
ebdocs doc image-upload DOC_ID --file diagram.png --width 468
ebdocs doc image-upload DOC_ID --file chart.svg --width 400 --keep-file
```

Workflow: uploads to Drive, makes it public, inserts into doc, deletes the Drive file (unless `--keep-file`). Supports PNG, JPG, JPEG, SVG, GIF, WebP.

### Mermaid diagram workflow

```bash
# 1. Render Mermaid diagram locally
mmdc -i architecture.mmd -o architecture.png -w 1200

# 2. Upload and embed in doc
ebdocs doc image-upload DOC_ID --file architecture.png --width 468

# Alternative: use mermaid.ink for public URL (no local render needed)
ebdocs doc image --url "https://mermaid.ink/svg/$(base64 -i architecture.mmd)" --width 468
```

Width/height are in points (72 pts = 1 inch). A full-width image in a standard doc is ~468 pts.

## Authentication

### Credentials

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_OAUTH_CLIENT_ID` | Yes (OAuth) | OAuth client ID from GCP |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Yes (OAuth) | OAuth client secret |
| `GOOGLE_OAUTH_REFRESH_TOKEN` | Yes (OAuth) | From `ebdocs auth login` |
| `GOOGLE_DRIVE_FOLDER_ID` | Recommended | Shared Drive folder for all docs |
| `GOOGLE_SERVICE_ACCOUNT_KEY` | Alternative | Path to SA JSON key file |

**OAuth is recommended.** Service account key creation may be blocked by org policy (`iam.disableServiceAccountKeyCreation`). OAuth tokens never expire unless revoked.

### First-Time Login (Docker-based, interactive terminal)

The OAuth login flow runs inside the **ebdocs Docker container** with port 9877 forwarded to the host. It prints a URL — the user opens it in a browser, approves, and the redirect comes back to `http://localhost:9877`. This **will not work inside Claude Code** — it requires an interactive terminal.

Tell the user:
> Open a **separate terminal** (or use `!` prefix in Claude Code) and run:
> ```bash
> cd /Users/omareid/Workspace/git/earlbear
> make ebdocs-login
> ```
> A URL will be printed. Open it in your browser and approve. The refresh token is printed when complete. Add it to `.env` as `GOOGLE_OAUTH_REFRESH_TOKEN=<token>`.

After the refresh token is saved, all subsequent `ebdocs` commands work headlessly — no browser needed. The refresh token never expires unless revoked.

**Using a downloaded JSON credentials file:** Pass a Google OAuth client secret JSON from GCP directly:

```bash
make ebdocs-login CLIENT_SECRET_FILE=~/Downloads/client_secret_xxxxx.apps.googleusercontent.com.json
```

The script extracts credentials from the JSON, runs the consent flow inside Docker, and prints the full matched set (client ID + secret + refresh token). Copy all three into `.env`.

**How it works:** The `scripts/gdocs-oauth-login.sh` script:
1. Reads credentials from the JSON file, env vars, or `.env`
2. Builds the `ebdocs` Docker image if needed
3. Runs `docker run -p 9877:9877 --entrypoint python ebdocs` with the OAuth flow
4. `InstalledAppFlow.run_local_server(port=9877, host='0.0.0.0')` listens inside Docker
5. Port forwarding makes `localhost:9877` reachable from the host browser
6. After consent, the refresh token is printed to stdout

No host Python installs required — everything runs in Docker.

**Important:** Refresh tokens are bound to the client ID that created them. Never mix a refresh token from one client ID with a different client ID/secret. If switching accounts, replace all three `GOOGLE_OAUTH_*` values in `.env`.

**Always validate before saving:** After login, verify the credential triple works:

```bash
curl -s -X POST https://oauth2.googleapis.com/token \
  -d "client_id=...&client_secret=...&refresh_token=...&grant_type=refresh_token"
```

A successful response returns an `access_token`. `unauthorized_client` = token from wrong client. `invalid_client` = secret was reset in GCP, re-download the JSON.

### Verify credentials

```bash
ebdocs auth status
# {"auth_mode": "oauth", "email": "omar@earlbear.com", "api_access": true}
```

## Makefile Targets

```bash
make ebdocs-build              # Build ebdocs Docker image
make ebdocs-rebuild            # Rebuild (no cache)
make ebdocs-test               # Run tests in Docker
make ebdocs-lint               # Lint code in Docker
make ebdocs-clean              # Clean build artifacts (egg-info, pycache)
make ebdocs-help               # Show ebdocs command tree

make ebdocs-login              # One-time OAuth consent (SEPARATE TERMINAL!)
make ebdocs-smoke              # Quick end-to-end smoke test (needs creds)
make ebdocs-reference          # Create reference doc exercising all features (needs creds)
```

**Important:** `make ebdocs-login` MUST run in a separate terminal — it opens a browser. After OAuth, the script automatically updates `.env` with all three `GOOGLE_OAUTH_*` variables.

## Troubleshooting — When to Trigger Login

### Error: `CONFIG_MISSING: Missing required config: GOOGLE_OAUTH_REFRESH_TOKEN`

The Google OAuth refresh token is not set in `.env`. This means first-time setup hasn't been done.

**Action:** Tell the user to run OAuth login:
```bash
# If they have a downloaded client secret JSON:
make ebdocs-login CLIENT_SECRET_FILE=~/Downloads/client_secret_xxxxx.apps.googleusercontent.com.json

# If GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET are already in .env:
make ebdocs-login
```
This runs inside Docker, opens a browser for consent, and **automatically updates `.env`** with the refresh token.

### Error: `CONFIG_MISSING: Missing required config: GOOGLE_OAUTH_CLIENT_ID`

No Google OAuth credentials at all. The user needs to:
1. Create OAuth credentials in [GCP Console](https://console.cloud.google.com/apis/credentials) → Create Credentials → OAuth client ID → Desktop app
2. Download the JSON file
3. Run `make ebdocs-login CLIENT_SECRET_FILE=path/to/downloaded.json`

### Error: `AUTH_FAILED: Token refresh failed: invalid_grant`

The refresh token was revoked or the client ID/secret changed. Re-run `make ebdocs-login` to get a fresh token.

### Error: `Access blocked: ... has not completed the Google verification process`

The GCP project is in testing mode and the user's email isn't listed as a test user. Fix in [GCP OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent) → Test users → Add the user's email.

### Quick diagnostic

```bash
# Check what's configured
./bin/ebdocs auth status

# Exit code 0 = working, exit code 2 = config missing, exit code 1 = API error
```

If `auth status` shows `CONFIG_MISSING`, the user needs `make ebdocs-login`. If it shows `auth_mode: oauth` and `api_access: true`, credentials are working.

## Regression Testing

### Reference document

```bash
make ebdocs-reference
```

Creates a Google Doc that exercises every CLI feature: headings, bold/italic text, lists, code blocks, tables, images, footnotes, page breaks, TOC, bookmarks, comments, and sharing. Use this to visually verify rendering after code changes.

### Smoke test

```bash
make ebdocs-smoke
```

Quick end-to-end test: creates a doc, writes content, reads it back, adds a comment, lists docs, verifies output, and cleans up. Requires valid credentials in `.env`. Use this as a fast sanity check before pushing changes.

## Output Formats

Every command supports `--format` and `--json`:

```bash
# Default: JSON (agent consumption)
ebdocs doc list
# [{"id": "1abc...", "title": "Q4 Report", "url": "https://docs.google.com/..."}]

# Field selection — only return specific keys
ebdocs doc list --json id,title

# Human-readable table
ebdocs doc list --format table
# ID              TITLE           MODIFIED
# 1abc...         Q4 Report       2026-03-28

# Plain — one value per line, pipe-friendly
ebdocs doc list --format plain
# 1abc...
# 2def...
```

Shorthand flags: `-f` for `--format`, `-j` for `--json`.

## Discovery Pattern

The CLI is self-documenting at every level:

```bash
ebdocs --help                     # All command groups
ebdocs doc --help                 # Commands within a group
ebdocs doc create --help          # Options for a specific command (with examples)
ebdocs --help-json                # Full command tree as JSON (for programmatic parsing)
ebdocs --version                  # Version info as JSON
```

Always start with `--help` when unsure. The `--help-json` flag is particularly useful for agents.

## Common Workflows

### Create a doc from markdown and share with team

```bash
# Create
DOC_ID=$(ebdocs doc create --title "Sprint Retrospective" --from-markdown retro.md --json id | jq -r '.id')

# Share with founders
ebdocs share add "$DOC_ID" --email omar@earlbear.com --role writer
ebdocs share add "$DOC_ID" --email cofounder@earlbear.com --role writer

# Link to Jira
ebdocs link jira "$DOC_ID" --issue CH-55
```

### Export a doc as PDF

```bash
# Download locally
ebdocs export download DOC_ID --format pdf --output report.pdf

# Get the doc URL (for linking in Jira/Slack)
ebdocs export url DOC_ID
```

### Add review comments with deep links

```bash
# Add anchored comment (attached to specific text)
ebdocs comment add DOC_ID --text "This claim needs a source" --quoted-text "62% of stores"

# Get all linkable elements for a Jira comment
ebdocs doc links DOC_ID --format table

# Generate highlight link for Slack
ebdocs doc highlight DOC_ID --text "Migrate to Dawn" --format plain
```

### Insert a table from CSV data

```bash
# Export metrics, insert as table
ebdocs doc table DOC_ID --from-csv quarterly-metrics.csv

# Quick inline table
ebdocs doc table DOC_ID --content "Status|Count\nDone|12\nIn Progress|5\nBlocked|2"
```

### Embed a Mermaid architecture diagram

```bash
# Render locally then upload
mmdc -i arch.mmd -o arch.png -w 1200
ebdocs doc image-upload DOC_ID --file arch.png --width 468

# Or use public URL (no local render)
ebdocs doc image DOC_ID --url "https://mermaid.ink/svg/..." --width 468
```

## Earl-Specific Workflow: Agent Deliverables

When the agent produces deliverables (kind:report, kind:playbook, kind:sop), the workflow is:

```bash
# 1. Create the doc with markdown content
DOC_ID=$(ebdocs doc create --title "EarlBear Brand Playbook" --from-markdown playbook.md --json id | jq -r '.id')

# 2. Share with the Drive folder (auto if GOOGLE_DRIVE_FOLDER_ID is set)
# The doc is created inside the shared folder — all founders have access

# 3. Link to Jira issue
ebdocs link jira "$DOC_ID" --issue CH-42

# 4. Update Supabase catalog (if applicable)
# The agent updates the artifacts table with the Google Doc URL
```

The `doc create` command automatically places docs in the `GOOGLE_DRIVE_FOLDER_ID` folder when that env var is set. This means all founders see the doc immediately — no manual sharing needed.

## Publishing a new doc to Drive

End-to-end workflow for taking a fresh markdown file in `earlbear-content` and publishing it as a Google Doc via `ebdocs sync`. The local `.md` is the source of truth; Drive is a rendered view.

### 1. Write the markdown

Create the file under `gdocs/<section>/<slug>.md` in the `earlbear-content` repo (e.g. `gdocs/vision/north-star.md`, `gdocs/playbooks/q2-launch.md`). Follow the `authoring-drive-docs` skill for the full formatting rules. Key things to remember inline:

- Blank line **before** every `###` heading (otherwise it gets absorbed into the previous paragraph).
- `EARL-NNN` references auto-linkify to Jira — write them as bare text, not markdown links.
- Nest bullets with **2-space** indent (not 4, not tabs).
- Mermaid diagrams go in fenced ```` ```mermaid ```` blocks.

### 2. Pre-render mermaid diagrams (host-side)

Mermaid CLI (`mmdc`) is **not** installed in the ebdocs container. Render diagrams on the host before pushing:

```bash
python docs/scripts/render_mermaid.py /Users/omareid/Workspace/git/earlbear-content/gdocs/<section>/<slug>.md
```

This writes `.assets/mermaid-<hash>.png` next to the doc. `sync push` reads those cached PNGs at push time. The `.md` file itself is **never modified** by the renderer. If you skip this step and a cached PNG is missing, the diagram falls back to a text error in the published doc.

### 3. Preview locally (optional)

For docs with code blocks or complex formatting, preview the rendered output without a Docker round-trip:

```bash
./bin/ebdocs sync preview /content/gdocs/<section>/<slug>.md
```

Shows syntax-highlighted terminal output of how the doc will render.

### 4. Create the local yaml stub (and cross-link to Jira)

```bash
./bin/ebdocs sync create /content/gdocs/<section>/<slug>.md \
    --folder <section> \
    --title "Human Readable Title" \
    --jira EARL-<num> \
    --jira EARL-<other>
```

- `--folder` is the Drive `folder_path` the doc lands under.
- `--jira` is **repeatable** — each instance is added to `links.yaml`.
- This step writes the local yaml stub but does not yet create the Drive doc.

### 5. Push to Drive

```bash
./bin/ebdocs sync push --file /content/gdocs/<section>/<slug>.md
```

The response includes the created Drive document ID. Construct the URL as:

```
https://docs.google.com/document/d/<id>/edit
```

### 6. Cross-link from Jira

Post the Drive URL as a comment on each related issue (this is `ebjira`, not `ebdocs`):

```bash
./bin/ebjira issue comment EARL-<num> "Doc published: https://docs.google.com/document/d/<id>/edit"
```

Note the **positional** `BODY` argument — there is no `--body` flag.

### 7. Commit the local files

The `.md`, the `.yaml`, and any `.assets/*.png` files should all be committed to `earlbear-content` so both the intent and the rendered state are versioned in git history.

### Important details

- **Container path scope:** The ebdocs container can only see paths under `/content`, which is the `earlbear-content` repo root mounted at `/content`. Always pass `/content/gdocs/...` as the path arg, not the host path.
- **Tree scope:** `sync push` now scans the **entire** `gdocs/` tree, not just `knowledge-base/`. Docs under `gdocs/vision/`, `gdocs/drafts/`, `gdocs/playbooks/`, etc. all work.
- **Weird Docs API errors about indices:** See `docs/gdocs-sync-gotchas.md` for known landmines and their fixes.
- **Force re-push without content changes:** Clear the `content_hash` field in the doc's yaml file and run `sync push` again.

### Related

- `authoring-drive-docs` skill — full markdown authoring rules for Drive docs.
- `docs/gdocs-sync-gotchas.md` — troubleshooting for sync push failures.

## Docker Nuances

The CLI runs inside a Docker container. The `bin/ebdocs` wrapper handles this transparently:

```
bin/ebdocs doc list
  -> docker run --rm --env-file .env ebdocs doc list
       -> Python CLI inside container -> Google Docs/Drive API
            -> JSON to stdout
```

Key implications:

- **Rebuild after code changes:** `make ebdocs-build` (or `docker build -t ebdocs gdocs-cli/`). The wrapper auto-builds on first run if the image is missing, but not on code changes.
- **Force rebuild:** `make ebdocs-rebuild` (uses `--no-cache`).
- **Credentials come from `.env`** via Docker's `--env-file`. The container never stores credentials.
- **Service account key file** is volume-mounted from the host path in `GOOGLE_SERVICE_ACCOUNT_KEY`.
- **No persistent state.** Each invocation is a fresh `docker run --rm`.
- **File access:** `--from-markdown`, `--from-csv`, and `--file` paths must be accessible inside the container. The wrapper mounts the current directory.
- **Cloud agent:** Uses `pip install -e gdocs-cli/[dev]` directly — no Docker needed. Credentials come from cloud environment variables.

## API Nuances

### Google Docs uses character-level index tracking

The Docs API `batchUpdate` operates on character indices, not paragraphs or lines. Every insert/delete shifts all subsequent indices. The `doc write` command handles this internally — it calculates the correct insertion point. When building raw `batchUpdate` requests, process them in reverse order (highest index first) to avoid index drift.

### Drive folder placement

When `GOOGLE_DRIVE_FOLDER_ID` is set, `doc create` uses the Drive API to place the new doc directly in the shared folder. Without it, docs land in the authenticated user's root Drive. Override per-command with `--folder-id`.

### Export formats

Supported export MIME types: `pdf`, `docx`, `txt`, `html`. The `export download` command accepts these as `--format` values. Binary formats (pdf, docx) default to file output; text formats (html, txt) default to stdout.

### Two-pass table insertion

Tables cannot be populated in a single API call. The `doc table` command uses two passes: (1) `insertTable` creates the structure, (2) re-fetch the doc to discover cell indices, then `insertText` fills cells in reverse order to avoid index drift.

### Image upload lifecycle

`doc image-upload` does: upload to Drive, make public, insert into doc, delete Drive file. The image is embedded in the doc, so the Drive file is disposable. Use `--keep-file` if you need the Drive file for other purposes.

## Error Handling

Errors are emitted as JSON to **stderr** with exit code **1**:

```bash
$ ebdocs doc read INVALID_ID
{"error": "GOOGLE_404", "message": "Document not found: INVALID_ID", "status": 1}
$ echo $?
1
```

Config errors (missing `.env`, missing credentials) exit with code **2**:

```bash
$ ebdocs doc list
{"error": "CONFIG_MISSING", "message": "Missing required config: GOOGLE_OAUTH_REFRESH_TOKEN"}
$ echo $?
2
```

Parse stdout (data) and stderr (errors) separately:

```bash
result=$(ebdocs doc list 2>/dev/null) && echo "OK: $result" || echo "FAIL"
```

## File Structure

One file per command group in `gdocs-cli/src/ebdocs/commands/`. Each file exports a Typer sub-app:

```
gdocs-cli/src/ebdocs/
  commands/
    doc.py            -> doc_app (create, read, write, list, headings, links,
                                  highlight, bookmarks, bookmark-add, image,
                                  image-upload, table, delete)
    share.py          -> share_app (add, remove, list)
    comment.py        -> comment_app (add, list, resolve)
    export.py         -> export_app (download, url)
    link.py           -> link_app (jira)
    auth.py           -> auth_app (login, status)
  models/
    doc.py            -> DocSummary, DocDetail, Comment, Permission
    common.py         -> Shared models
  markdown.py         -> markdown_to_requests(), docs_to_markdown(), parse_pipe_table()
  client.py           -> DocsClient (google-api-python-client)
  output.py           -> Format enum, output_result()
  config.py           -> Environment variable loading
  auth.py             -> load_credentials(), run_oauth_login_flow()
  main.py             -> Root app, registers all sub-apps
```

### Conventions

- Every command supports `--format` and `--json` options.
- Use `get_client()` singleton — never instantiate `DocsClient` directly.
- Use `output_result()` for all output — never `print()` directly (except `output_error()`).
- Typer `Annotated` syntax for all options/arguments.
- Markdown content is converted to Docs API `batchUpdate` requests via `markdown_to_requests()`.
- All index-manipulating operations process in reverse order to avoid drift.
