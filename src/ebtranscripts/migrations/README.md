# ebtranscripts migrations

Two modes, one dialect (standard Postgres) — see `docs/database-design.md`. Migrations are
split by portability (per the `portable-sql` skill):

- **Portable** (`NNN_*.sql`) — schema + marts logic. Standard Postgres, runs in **both**
  local Docker Postgres and Supabase.
- **Prod-only** (`NNN_*_prod.sql`) — Supabase roles + RLS. Applied **only** to Supabase; the
  local runner (`scripts/db.sh migrate`) skips them.

## Local mode (Docker Postgres)

```bash
./scripts/db.sh up        # start container
./scripts/db.sh migrate   # apply portable migrations (skips *_prod.sql)
```
Then point the CLI at it with `EBT_LOCAL_DB_URL` (see `scripts/db.sh url`). No cloud creds.

## Cloud mode (Supabase)

Applied to the "Artifacts" project (`ldvaleamtfocaueqebvy`) via the Supabase MCP
`apply_migration` — portable files **plus** `*_prod.sql`.

## The files, in order

1. `001_cc_core.sql` *(portable)* — the `cc_sessions` / `cc_tool_calls` / `cc_subagent_runs`
   / `cc_skill_uses` tables. Derived telemetry only; never raw content.
2. `002_cc_marts.sql` *(portable)* — `mart_workflow_metrics`, `mart_funnel_daily`,
   `mart_recent_sessions`, and `refresh_cc_marts()`. The funnel joins the real business
   tables (`leads`, `sme_reviews`, `shopify_intakes`, `earl_reviews`) by day. EXECUTE on the
   refresh function is revoked from PUBLIC (covers local); the anon/authenticated revoke is
   in the `_prod` file.
3. `003_cc_rls_prod.sql` *(Supabase-only)* — RLS + anon read policies on the marts and
   published `cc_sessions` rows; detail tables have no anon policy.
4. `004_cc_marts_model.sql` *(portable)* — adds `model` to the workflow-metrics mart grain
   (day+stage+model) and updates `refresh_cc_marts()`.

`refresh_cc_marts()` — the one shared aggregation — contains **zero** Supabase-only
references, so the marts compute identically in both modes.

## Verified (via MCP SQL, no fake data written to business tables)

- All three migrations apply cleanly.
- Inserting a synthetic `cc_sessions` row + refreshing populates
  `mart_workflow_metrics` and `mart_funnel_daily` correctly; the funnel also reflects
  real business-table dates (confirming the joins use real column names).
- Idempotency: re-inserting the same session with `on_conflict` produces no duplicates.
- Security advisor clean for our objects after revoking PUBLIC execute on
  `refresh_cc_marts()`.
- Synthetic test data removed afterward; `cc_*` tables left empty.

## Not yet exercised (needs credentials)

The CLI's live `push` (service-role REST upsert) requires
`SUPABASE_PROJECT_URL` + `SUPABASE_SERVICE_ROLE_KEY` in `~/.config/earlbear/.env`. The
push module's SQL shape (upsert target tables + `on_conflict` keys) matches this schema
and was validated directly via SQL; the end-to-end `sync` against a real key is proven in
the M10 POC.
