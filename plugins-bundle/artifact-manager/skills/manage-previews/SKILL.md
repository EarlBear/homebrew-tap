# /manage-previews — Manage Artifact Previews

> **Context:** Previews are the working-backwards vision for each artifact — they show what the artifact will look like when built. Every artifact in the tracker should have a preview before it moves to "active" status. Previews are stored in Supabase (`preview_type`, `preview_label`, `preview_content` columns) and rendered in the encrypted artifact tracker page.
>
> **Prerequisite:** Supabase MCP must be configured. Run `/setup-supabase` if not.

## When to trigger

- "manage previews", "update previews", "add preview"
- "which artifacts are missing previews?"
- "write a preview for [artifact]"
- "show me the preview for [artifact]"

## Preview types

| Type | Renderer | Best For |
|------|----------|----------|
| `code` | `CodePreview` (monospace, scrollable) | Config snippets, schemas, sample outputs, outlines, checklists |
| `email` | `EmailPreview` | Email templates with subject/body |
| `sequence` | `SequencePreview` | Multi-step drip sequences, timelines |
| `personas` | `PersonasPreview` | Persona profiles with discovery methods |
| `catalog` | `CatalogPreview` | Curated lists, package contents |
| `visual` | *(future)* | Screenshots, mockups, diagrams |

## Workflow

### Step 1: Audit preview coverage

Query Supabase for artifacts missing previews:

```sql
SELECT slug, display_name, layer FROM artifacts
WHERE preview_type IS NULL AND is_published = true
ORDER BY sort_order;
```

Report: "X/Y artifacts have previews. Missing: [list]"

### Step 2: For each missing preview

Use AskUserQuestion:
1. What type of preview? (code/email/sequence/personas/catalog)
2. What label? (e.g., "Sample Output", "Config Schema", "Post Outline")
3. Draft the content — or ask the user to describe what the artifact will produce, and generate a working-backwards preview

### Step 3: Write to Supabase

```sql
UPDATE artifacts
SET preview_type = 'code',
    preview_label = 'Sample Output',
    preview_content = '...'
WHERE slug = 'artifact-slug';
```

Use `mcp__plugin_supabase_supabase__execute_sql` to run the update.

### Step 4: Verify

Refresh the artifact tracker page and click the card to see the preview panel.

## Editing existing previews

When the user says "update the preview for [artifact]":

1. Fetch current: `SELECT preview_type, preview_label, preview_content FROM artifacts WHERE slug = '...'`
2. Show current preview to user
3. Ask what to change
4. UPDATE via Supabase MCP

## Preview as living spec convention

Every artifact should have a preview before moving to "active" in Jira. The preview IS the spec. When running `/validate-catalog` (from the earlbear repo), check for missing previews and report them.

## Key constraints

- **All preview content is behind encryption** — only visible after StatiCrypt password entry
- **Previews are stored in Supabase** — no build step needed to update them
- **`code` type is the default** — most previews are code/config/outline snippets
- **Keep previews concise** — they're working-backwards visions, not full implementations
- **Escape single quotes** in SQL — use `''` (double single quote) for apostrophes
