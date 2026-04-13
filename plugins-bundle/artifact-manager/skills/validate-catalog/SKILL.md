# /validate-catalog — Validate Artifact Catalog

> **Context:** Validates the artifact catalog end-to-end: Supabase data integrity, index.html rendering, Jira link correctness, and visual layout. Run before publishing (`/publish`) or after any change to the catalog pipeline.
>
> **Prerequisite:** Supabase MCP and Jira MCP must be configured. Run `/setup-supabase` and `/setup-jira` if not.

## When to trigger

- "validate catalog", "check catalog", "regression test catalog"
- "pre-publish check", "validate before deploy"
- Before running `/publish`
- After modifying `generate-index.sh`, artifact tracker HTML, or Supabase schema

## Validation checklist

### Step 1: Supabase data integrity

Use `mcp__plugin_supabase_supabase__execute_sql` to run these checks:

```sql
-- Count published artifacts
SELECT count(*) FROM artifacts WHERE is_published = true;

-- Check for missing required fields
SELECT slug, display_name FROM artifacts
WHERE display_name IS NULL OR description IS NULL OR icon IS NULL OR href IS NULL OR category IS NULL;

-- Check for duplicate slugs (should be impossible with UNIQUE constraint but verify)
SELECT slug, count(*) FROM artifacts GROUP BY slug HAVING count(*) > 1;

-- Check all Jira links are present
SELECT slug, display_name FROM artifacts WHERE jira_issue_key IS NULL;

-- Verify sort_order has no gaps
SELECT slug, sort_order FROM artifacts ORDER BY sort_order;
```

Report: total count, any missing fields, any orphaned rows.

### Step 2: REST API fetch test

Simulate what `index.html` does — fetch via anon key:

```bash
source .env && curl -s "${SUPABASE_PROJECT_URL}/rest/v1/artifacts?is_published=eq.true&order=sort_order" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY" | python3 -c "
import sys,json
rows = json.load(sys.stdin)
print(f'Fetched {len(rows)} artifacts via anon key')
for r in rows:
    issues = []
    if not r.get('display_name'): issues.append('missing name')
    if not r.get('icon'): issues.append('missing icon')
    if not r.get('href'): issues.append('missing href')
    if issues:
        print(f'  WARN: {r[\"slug\"]}: {', '.join(issues)}')
"
```

### Step 3: generate-index.sh output validation

```bash
source .env && bash scripts/generate-index.sh > /tmp/catalog-test.html
# Verify keys are embedded
grep -c "SUPABASE_PROJECT_URL" /tmp/catalog-test.html  # should be 0 (substituted)
grep -c "ldvaleamtfocaueqebvy" /tmp/catalog-test.html  # should be > 0 (actual URL)
grep -c "sb_publishable_" /tmp/catalog-test.html        # should be > 0 (anon key)
# Verify no shell variable leaks
grep -c '${' /tmp/catalog-test.html                     # should be 0 in non-JS sections
```

### Step 4: Jira link validation

For each artifact with a `jira_issue_key`, verify the Jira issue exists:

```bash
source .env
# Fetch all artifacts with Jira links from Supabase
# For each, curl the Jira API to verify the issue exists
# Report any broken links (404) or summary mismatches
```

**Jira key staleness check:** Jira keys can change when the project is reorganized. If a key returns 404:
1. Search Jira by summary to find the new key
2. Update the Supabase row and `manifests/jira/card-mapping.json`
3. Report the key change

**Production URL check:** For each Jira issue, check if it has a comment with the artifact production URL. If not, flag it for adding (via `/sync-catalog` Phase 6).

### Step 5: Visual layout check (manual + screenshot)

Open the pages via a local HTTP server and verify:

1. **Catalog page** (`dist/public/index.html`):
   - All cards render (count matches Supabase)
   - Jira badges visible and clickable
   - "+" button present at end of grid
   - No overlapping elements
   - Loading state works (disable network, reload)
   - Error state works (use wrong URL)

2. **Artifact tracker** (`../earlbear-sites/claude-artifacts/artifact-tracker/artifact.html`):
   - Board layout renders with cards in correct layers
   - Jira badges don't overlap card content (check bottom spacing)
   - Tags render below description
   - Owner dots visible
   - Dependency lines trace correctly on hover/pin

### Step 6: Insert test (+ modal simulation)

```bash
# Test INSERT via anon key
source .env && curl -s -X POST "${SUPABASE_PROJECT_URL}/rest/v1/artifacts" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d '{"slug":"__test__","display_name":"Test","description":"Validation test","category":"artifact","icon":"&#128270;","href":"test/","sort_order":999}' \
  | python3 -c "import sys,json; print('INSERT:', json.load(sys.stdin)[0]['slug'])"

# Clean up
# Use Supabase MCP: DELETE FROM artifacts WHERE slug = '__test__';
```

### Step 6b: Preview coverage check

```sql
-- Check preview coverage
SELECT slug, display_name FROM artifacts
WHERE preview_type IS NULL AND is_published = true;
```

Report: "Previews: X/Y published artifacts have previews. Missing: [list]"
Artifacts without previews should not be published — recommend setting `is_published = false` until a preview is added via `/manage-previews`.

### Step 7: Cross-system divergence check

Run `/sync-catalog` in check-only mode — compare Supabase vs Jira for priority, status, and assignee mismatches.

## Report format

```
Catalog Validation Report
=========================
Supabase:  24 published, 0 missing fields, 0 duplicates
REST API:  24 fetched via anon key OK
index.html: Generated OK, keys embedded, no leaks
Jira:      24/24 links valid
Previews:  X/Y published artifacts have previews
Insert:    Anon INSERT OK, cleaned up
Sync:      0 divergences (or list mismatches)
Visual:    [Manual — checked / not checked]

Result: PASS / FAIL (with details)
```

## Key constraints

- **Non-destructive** — only reads data, test inserts are cleaned up immediately
- **Idempotent** — safe to run multiple times
- **Run before /publish** — catches issues before they reach GitHub Pages
- **Report divergences** — highlights Supabase/Jira mismatches for `/sync-catalog` to fix
