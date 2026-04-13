# Sync Catalog

> Bidirectional sync between Supabase (vision catalog) and Jira (work tracker). Light and frequent -- run before planning or after a batch of work completes. Separate from `/refine-working-model` (heavy, infrequent).

## Philosophy

- **Supabase = top-down vision.** What should exist, dependencies, layers, catalog display.
- **Jira = bottom-up work.** What's being built, status, assignee, workflow.
- **Split authority:** each system is canonical for different fields (see table below).

## Phase 1: Pull

```bash
# Jira: all EARL issues
ebjira issue list --project EARL --limit 100 --json key,summary,issue_type,status,priority,labels,assignee,components

# Supabase: all artifacts (use Supabase MCP execute_sql on project ldvaleamtfocaueqebvy)
SELECT slug, display_name, jira_issue_key, status, priority, owners, deps, tags, layer, category
FROM artifacts ORDER BY sort_order;
```

Load slug-to-key mapping from `manifests/jira/card-mapping.json`.

If either source fails, stop and direct user to `/setup-jira` or `/setup-supabase`.

## Phase 2: Detect Divergence

Match pairs via `jira_issue_key` in Supabase and slug mapping in `jira-card-mapping.json`.

Check for:
- **Status divergence** -- Jira vs Supabase (use status mapping below)
- **Priority divergence** -- Jira vs Supabase (use priority mapping below)
- **Owner divergence** -- Jira assignee vs Supabase owners (use owner mapping below)
- **Missing in Jira** -- Supabase artifact has no `jira_issue_key`
- **Missing in Supabase** -- Jira issue has no corresponding artifact row
- **Layer vs component mismatch** -- Supabase `layer` should align with Jira component
- **Dependency gaps** -- Supabase `deps` not reflected as Jira issue links

Skip issues with Jira status "Done" -- don't sync completed work backward.

## Phase 3: Propose Sync Plan

Present a table grouped by sync direction before applying anything:

| Direction | Fields | Action |
|-----------|--------|--------|
| **Jira -> Supabase** | status, priority, owners | UPDATE artifacts via `execute_sql` |
| **Supabase -> Jira** | deps (as issue links), tags (as labels) | UPDATE via `ebjira` CLI |
| **New in Jira** | Issues without Supabase row | CREATE artifact row (no href, is_published=false) |
| **New in Supabase** | Artifacts without Jira issue | Flag for review (may need `/add-backlog-item`) |

**Ask for confirmation before Phase 4.**

## Phase 4: Apply

```bash
# Jira -> Supabase: update status/priority/owners
# Use Supabase MCP execute_sql:
UPDATE artifacts SET status = 'active', priority = 'high', owners = ARRAY['omar'], updated_at = now()
WHERE jira_issue_key = 'EARL-6';

# Supabase -> Jira: add labels
ebjira issue update EARL-6 --labels tag1,tag2

# New Jira issue -> Supabase: insert stub row
INSERT INTO artifacts (slug, display_name, description, category, icon, href, jira_issue_key, jira_issue_url, is_published)
VALUES ('new-slug', 'Display Name', 'Description', 'artifact', '&#128736;', '', 'EARL-99',
        'https://earlbear.atlassian.net/browse/EARL-99', false);
```

### Seeding Files Update

After applying changes, update **all three seeding files** to stay in sync:

**1. `manifests/jira/card-mapping.json`** — slug ↔ Jira key mapping:

```bash
# Read current mapping
cat manifests/jira/card-mapping.json

# After creating new Jira issues or Supabase artifacts, merge new entries:
# Read, add new entries, write back. Never drop existing entries.
```

**2. Supabase `artifacts` table** — if a new Jira issue needs a catalog entry:

```sql
-- New Jira issue discovered (bottom-up work) -> create Supabase stub
-- No href yet (no preview artifact), is_published=false until a preview exists
INSERT INTO artifacts (slug, display_name, description, category, icon, href,
  jira_issue_key, jira_issue_url, status, priority, owners, is_published)
VALUES ('new-slug', 'Display Name', 'Description from Jira', 'artifact',
  '&#128736;', '', 'EARL-99', 'https://earlbear.atlassian.net/browse/EARL-99',
  'todo', 'high', ARRAY['omar'], false);
```

**3. `scripts/generate-index.sh`** — usually doesn't need changes since the index.html fetches from Supabase at runtime. But if you add a new **artifact category** (not just a new card), check whether `generate-index.sh` needs a new static section.

### Coverage Gaps

**New in Supabase (vision without work):**
A Supabase artifact with no `jira_issue_key` means someone defined a vision item but no Jira issue exists to track the work. Action:
- Review the artifact — is this real work we want to do?
- If yes: use `/add-backlog-item` to create the Jira issue, then update `jira-card-mapping.json` and the Supabase row's `jira_issue_key`
- If no: flag it for review, leave as-is

**New in Jira (work without vision):**
A Jira issue with no Supabase artifact means bottom-up work was discovered. Action:
- Create a stub Supabase row with `is_published=false` (no preview URL yet)
- Add to `jira-card-mapping.json`
- The item won't appear in the public catalog until someone sets `is_published=true` and adds an `href`

**Closed/Done in Jira:**
Skip during sync. Don't push status back to "done" in Supabase if the artifact might need vision-level updates later. Only sync active work.

## Mapping Tables

### Status

Board columns: Open | Prioritized | Planning | In Progress | Blocked | Review | Done

| Jira | Supabase | Notes |
|------|----------|-------|
| Open | todo | Newly created, not yet prioritized |
| Prioritized | todo | Ready-to-work queue |
| Planning | planning | Being scoped/designed — preview being written |
| In Progress | active | Implementation underway |
| ~~Blocked~~ | ~~blocked~~ | Removed — use flag/label instead |
| Review | review | Draft complete, awaiting human review |
| Done | done | |

### Priority

| Jira | Supabase |
|------|----------|
| Highest | high |
| High | high |
| Medium | med |
| Low | low |
| Lowest | low |

### Owners

| Jira (assignee) | Supabase (owners) |
|-----------------|-------------------|
| Omar Eid | omar |
| duke | saad |
| mazen | mazen |

## Canonical Authority

| Field | Canonical Source | Sync Direction |
|-------|-----------------|----------------|
| status | Jira | Jira -> Supabase |
| priority | Jira | Jira -> Supabase |
| owners/assignee | Jira | Jira -> Supabase |
| issue_type, components, labels | Jira | Read-only |
| icon, href, badge_text | Supabase | Supabase-only |
| tags | Supabase | Supabase -> Jira (as labels) |
| layer | Supabase | Supabase-only |
| sort_order, is_published | Supabase | Supabase-only |
| deps | Supabase | Supabase -> Jira (as issue links) |

## Phase 5: Backfill New Jira Items to Supabase

When new Jira issues are found without Supabase rows:

1. **Infer artifact metadata from Jira** — use the issue summary, description, type, and parent Epic to generate:
   - `slug` (kebab-case from summary)
   - `display_name` (from summary)
   - `description` (from Jira description first paragraph, or summary if empty)
   - `category`: always `artifact`
   - `icon`: based on issue type (`&#128220;` for Deliverable/tech design, `&#128640;` for Feature, `&#128218;` for Story, `&#128736;` for Task)
   - `badge_text`: based on tags — `tech design` for Tech Designs epic children, `strategy` for Business Strategies epic children, issue type name otherwise
   - `tags`: infer from parent Epic (`tech-design`, `strategy`, `agent`, etc.)
   - `deps`: look for related artifacts by keyword matching in the summary
   - `layer`: `deliverable` for most new items
   - `href`: `artifacts/artifact-tracker/` (all point to the tracker board until they get their own HTML artifact)

2. **Tech Designs and Strategies are artifacts** — every item under the Tech Designs (EARL-127) or Business Strategies (EARL-128) epics should become a Supabase row. These represent the working-backwards vision.

3. **Set `is_published = true`** for backfilled items — they should appear on the tracker board immediately.

4. **Use UPSERT** (`ON CONFLICT (slug) DO UPDATE`) to make backfill idempotent.

## Phase 6: Add Production URLs to Jira

For Jira issues that correspond to published artifacts, add a comment with the production URL:

```bash
# For issues linked to the artifact tracker:
curl -X POST .../rest/api/3/issue/EARL-XX/comment \
  -d '{"body": "Artifact preview: https://bytesofpurpose.github.io/earlbear/artifacts/artifact-tracker/ (encrypted)"}'
```

Only add if no such comment already exists (check existing comments first for idempotency).

**When an artifact gets its own HTML file** (not just a tracker card), update the comment with the specific URL.

## Handling Jira Reorganization

Jira keys can change when the project is reorganized (issues moved between projects, bulk operations, etc.). When keys diverge:

1. Fetch all Jira issues and match to Supabase by **summary similarity**, not by key
2. Update `jira_issue_key` and `jira_issue_url` in Supabase
3. Update `manifests/jira/card-mapping.json`
4. This is a normal part of the workflow — don't treat it as an error

## Constraints

- **Idempotent.** Re-running after a clean sync produces "0 mismatches found". To enforce this:
  - Before INSERT into Supabase, check `SELECT 1 FROM artifacts WHERE jira_issue_key = 'EARL-X'` — skip if exists
  - Before INSERT into jira-card-mapping.json, check if slug already has an entry — skip if exists
  - Before updating Supabase status/priority/owners, compare current values — skip if already matching
  - "Prioritized" in Jira maps to "todo" in Supabase
- **Non-destructive.** Always asks before writing. Never auto-overwrites. Never deletes rows.
- **Dynamic discovery.** Use the ID cache (`.jira-cache.json` via `ebjira cache show`) for account IDs and status IDs. Refresh cache with `ebjira cache refresh` if stale.
- **No secrets in output.** Never echo API tokens or credentials.

## Source of Truth

| What | Where |
|------|-------|
| Supabase schema | `docs/design-supabase-catalog.md` |
| Slug-to-key mapping | `manifests/jira/card-mapping.json` |
| Work taxonomy | `docs/design-work-taxonomy.md` |
| Backlog creation | `.claude/skills/add-backlog-item/SKILL.md` |
