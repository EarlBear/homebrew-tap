# Import Claude Artifact

> **Context:** This skill imports HTML artifacts from Claude conversations into the earlbear-sites repo. Artifacts are stored in `claude-artifacts/{name}/` and automatically included in `dist/public/` with StatiCrypt encryption when `make dist` runs. Tech design documents and strategy documents can also be artifacts — they get their own HTML file and appear in the catalog.
>
> **Lifecycle (earlbear-sites scope):** Import HTML → Supabase row (draft) → Preview → Publish → commit
>
> **Note on dual writes:** The public catalog (`dist/public/index.html`) is purely static — `generate-index.sh` bakes cards at `make dist` time with no runtime Supabase fetch. Supabase powers only the internal artifact tracker page. This skill writes to both the filesystem AND Supabase independently (no transaction, no rollback). Drift is possible if one write fails. This is an acceptable risk for now — imports are infrequent and caught at `make dist` + visual review. Revisit if import failures or catalog mismatches become recurring.
>
> **Jira cross-cutting:** Steps that create/update Jira tickets live in the earlbear repo (not here). Offer them as optional and skip cleanly if the user isn't operating on a Jira-integrated ticket.

## When to trigger

User says things like:
- "help me import a claude artifact"
- "I have an HTML artifact to add"
- "import this artifact"
- "import this tech design"
- "make this design doc an artifact"
- "add a claude artifact to the catalog"
- "I built an HTML page in Claude I want to host"

## Workflow

Track all steps as tasks using TaskCreate/TaskUpdate.

### Step 1: Gather info

Ask the user:
1. **What is the artifact?** Get a short description (1-2 sentences) of what the HTML artifact does/shows.
2. **What should we name it?** Suggest a kebab-case name based on the description (e.g., `competitive-analysis`, `product-roadmap`, `brand-overview`). The name becomes the directory name and URL path (`/artifacts/{name}/`).
3. **Where is the HTML file?** Ask for the file path to the HTML artifact. This could be:
   - A local file path (e.g., `~/Downloads/artifact.html`)
   - Pasted HTML content (save it to a temp file)

### Step 2: Extract the rebuild prompt

Before importing, guide the user to go back to the Claude conversation where they built the artifact and run this prompt:

```
I want to be able to give Claude Code a markdown prompt that allows it to understand the essential context we've been discussing and rebuild this site with all the mechanisms we captured, with the theme/approach/etc. I want to be able to copy a single markdown block and give it to Claude Code. Can you produce that block?
```

Ask the user to paste the resulting markdown block. This becomes `prompt.md` — the artifact's rebuild instructions.

### Step 3: Import with the helper script

Use `scripts/import-artifact.sh` which handles HTML copying, JSX→HTML wrapping, and prompt placement:

```bash
# HTML artifact with prompt
./scripts/import-artifact.sh {name} /path/to/artifact.html /path/to/prompt.md

# JSX/TSX artifact (auto-wrapped with React CDN + Babel)
./scripts/import-artifact.sh {name} /path/to/component.jsx /path/to/prompt.md

# Without prompt (add later)
./scripts/import-artifact.sh {name} /path/to/artifact.html
```

The script will:
- Create `claude-artifacts/{name}/`
- Copy or wrap the source file as `artifact.html`
- Copy `prompt.md` (or create a placeholder)
- For `.jsx`/`.tsx` files: strip imports, wrap in self-contained HTML with React 18 + Babel CDN

### Step 4: Verify the artifact

1. Open it locally: `open claude-artifacts/{name}/artifact.html`
2. List it: `make artifact-list`

### Step 5: Create Supabase catalog entry

Insert a row into the `artifacts` table via Supabase MCP (`mcp__plugin_supabase_supabase__execute_sql`):

```sql
INSERT INTO artifacts (slug, display_name, description, category, icon, href, badge_text, sort_order, is_published)
VALUES (
  '{name}',
  '{display_name}',
  '{description from prompt.md first line, stripped of #}',
  'artifact',
  '{icon}',
  'artifacts/{name}/',
  'artifact',
  (SELECT COALESCE(MAX(sort_order), 0) + 1 FROM artifacts),
  false
);
```

Field guidance:
- **slug**: The kebab-case `{name}` used for the directory.
- **display_name**: A human-readable title derived from the description (e.g., "Competitive Analysis").
- **description**: The first line of `prompt.md`, stripped of `#` prefix.
- **icon**: Ask the user which emoji/icon to use. Default to `&#9889;` (lightning bolt) if they skip.
- **is_published**: Always `false` initially — the artifact should have a preview before publishing.

### Step 6: Create Jira issue (optional — earlbear repo)

**Skip this step unless the user is operating on a Jira-integrated ticket.**

The Jira skills (`/add-backlog-item`, `/conform-jira`, etc.) live in the sibling `../earlbear` repo. If the user wants a Jira Story for this artifact, tell them to `cd ../earlbear && claude` and invoke `/add-backlog-item` there with a summary like:

> **Summary:** Import artifact: {display_name}
> **Description:** New artifact imported to `../earlbear-sites/claude-artifacts/{name}/`. Needs preview and publishing.

If the user declines or the Jira integration isn't set up, skip cleanly.

### Step 7: Add preview (recommended before publishing)

Direct the user to run `/manage-previews` to add a working-backwards preview for the artifact. The preview should be added before the artifact is published so the catalog entry has visual context.

Tell the user:
- The artifact's `is_published` is currently `false` (draft)
- A preview makes the catalog entry meaningful — run `/manage-previews` to add one
- Once the preview is ready, proceed to Step 8 to publish

### Step 8: Publish (set is_published = true)

Once the preview is in place, update the Supabase row to make the artifact visible in the catalog:

```sql
UPDATE artifacts SET is_published = true WHERE slug = '{name}';
```

Then optionally run `/validate-catalog` from the earlbear repo to confirm the artifact appears correctly in the Supabase catalog.

### Step 9: Test in dist pipeline

```bash
# Clean previous dist
rm -rf dist/

# Run full pipeline
make dist
```

Verify:
- The artifact appears in `dist/public/artifacts/{name}/index.html`
- The artifact card appears in `dist/public/index.html` (grep for the name)
- The artifact HTML is encrypted (grep for "staticrypt")
- The index.html is NOT encrypted

### Step 10: Report

Tell the user:
- Artifact imported to `claude-artifacts/{name}/`
- Supabase catalog entry created (is_published: true/false)
- Jira issue created (if applicable)
- It will appear at `{site-url}/artifacts/{name}/` after publishing
- The artifact is password-protected (same StatiCrypt password as everything else)
- To rebuild the artifact later, use the prompt in `prompt.md`
- Remind them to commit the new artifact

## Directory structure

```
claude-artifacts/
├── {artifact-name}/
│   ├── artifact.html          # The HTML artifact file
│   └── prompt.md              # Rebuild prompt (first line = # Title for catalog)
├── {another-artifact}/
│   ├── artifact.html
│   └── prompt.md
```

## How it integrates

- `make dist-collect` copies each `artifact.html` → `dist/public/artifacts/{name}/index.html`
- `make dist-encrypt` encrypts all HTML in dist/public/ except the root index.html
- `scripts/generate-index.sh` auto-discovers artifacts in `dist/public/artifacts/` and reads descriptions from `claude-artifacts/{name}/prompt.md` (first line, stripped of `#`)
- `make artifact-list` shows all imported artifacts
- The unencrypted catalog (`dist/public/index.html`) shows each artifact as a card with a lock icon

## Rebuilding an artifact

If the user wants to modify/rebuild an artifact:
1. Read `claude-artifacts/{name}/prompt.md` for the rebuild context
2. Generate new HTML based on the prompt and user's changes
3. Save to `claude-artifacts/{name}/artifact.html`
4. Run `make dist` to rebuild dist/public/
