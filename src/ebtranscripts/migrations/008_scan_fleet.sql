-- Shopify sites scan fleet — first-class site entity + a request queue + a Supabase mirror of
-- the reporting file-contract (runs + events). The gtm dashboard's /sites page reads these
-- live over Supabase Realtime (postgres_changes) to show a queued/scanning/done tally and
-- per-DOMAIN metrics (sessions seen, total issues, runs, last scanned), and /reports can
-- optionally read a run from here.
--
-- Portable (runs on local Docker Postgres AND Supabase): pure DDL — no Supabase-only
-- constructs, no cross-table DML. RLS + the realtime publication live in
-- 008_scan_fleet_prod.sql (cloud only, skipped by scripts/db.sh migrate). This keeps the
-- C13 portable-SQL guard (scripts/check-portable-sql.sh) green.
--
-- ORDERING HAZARD (same as 005/006/007): apply this migration to local PG AND Supabase (via
-- the Supabase MCP apply_migration) BEFORE any writer (the reporting MCP server's Supabase
-- sink) runs against it. Schema first.

-- 1) scan_sites — the first-class site, natural key = normalized host (lowercase, no scheme,
--    no leading www, no trailing slash). Carries DOMAIN-LEVEL metrics that the reporting MCP
--    server rolls up across every run of the host (updated on end_review): the distinct
--    session ids seen, and running totals of issues/positives/frictions/etc.
create table if not exists public.scan_sites (
  host                text primary key,
  target_url          text not null,               -- canonical home URL as first discovered
  site_name           text,
  platform            text not null default 'shopify',
  discovered_at       timestamptz not null default now(),
  notes               text,
  priority            int  not null default 0,      -- higher = review sooner
  -- domain-level rollup (summed across all runs of this host):
  runs_total          int  not null default 0,
  sessions            jsonb not null default '[]',  -- distinct CLAUDE_CODE_SESSION_ID values seen
  sessions_total      int  not null default 0,
  issues_total        int  not null default 0,
  positives_total     int  not null default 0,
  frictions_total     int  not null default 0,
  metrics_total       int  not null default 0,
  journey_steps_total int  not null default 0,
  last_scanned_at     timestamptz,
  last_run_id         text,
  last_status         text,
  updated_at          timestamptz not null default now()
);

-- 2) scan_requests — the queue. The dashboard anon-INSERTs a 'queued' row (RLS-locked in the
--    _prod file); the reporting MCP server (service-role) advances it queued→scanning→done.
create table if not exists public.scan_requests (
  id           bigint generated always as identity primary key,
  target_url   text not null,
  page_url     text,                                -- optional specific page to review
  site_host    text,                                -- plain column (see scan_runs note): no FK
  status       text not null default 'queued'
    check (status in ('queued', 'scanning', 'done', 'failed')),
  requested_at timestamptz not null default now(),
  requested_by text,                                -- CF Access email, or 'anon'
  started_at   timestamptz,
  finished_at  timestamptz,
  run_id       text                                 -- links to scan_runs.run_id once scanning
);
create index if not exists idx_scan_requests_status on public.scan_requests (status);
create index if not exists idx_scan_requests_requested_at on public.scan_requests (requested_at desc);

-- 3) scan_runs — mirrors the /reports RunIndexEntry (index.json rows). Counts are flattened
--    typed columns (one per COUNT_TYPE in the MCP server) so tally SQL and Realtime UPDATE
--    payloads carry them without unpacking JSONB. Irregular fields stay JSONB.
-- NOTE: site_host is a plain (indexed) column, NOT a foreign key. The reporting MCP server
-- writes scan_sites and scan_runs as independent best-effort async upserts with no ordering
-- guarantee, so a FK would intermittently reject a run whose site upsert is still in flight.
-- A momentarily-dangling host is harmless (the site row lands moments later; the /sites page
-- joins by host in the client). Same reasoning for scan_requests.site_host.
create table if not exists public.scan_runs (
  run_id             text primary key,               -- e.g. rev-20260708-1432-ab12
  site_host          text,
  target_url         text not null,
  site_name          text,
  status             text not null default 'active'
    check (status in ('active', 'completed', 'abandoned')),
  started_at         timestamptz not null default now(),
  ended_at           timestamptz,
  last_event_at      timestamptz not null default now(),
  count_issue        int not null default 0,
  count_positive     int not null default 0,
  count_friction     int not null default 0,
  count_journey_step int not null default 0,
  count_metric       int not null default 0,
  count_progress     int not null default 0,
  verdict            text,                            -- from review_completed
  summary            jsonb,                           -- { top_issues, top_positives, journey_steps_to_checkout }
  env                jsonb,                           -- { pid, cwd, node, session_id }
  reviewer           text,
  file               text                             -- runs/<run_id>.jsonl (parity with the file contract)
);
create index if not exists idx_scan_runs_started_at on public.scan_runs (started_at desc);
create index if not exists idx_scan_runs_site_host on public.scan_runs (site_host);

-- 4) scan_events — one row per JSONL event line. (run_id, seq) PK makes the MCP upsert
--    idempotent on retry. The envelope + the fields any page filters/sorts on are promoted to
--    typed columns; the rest of the type-specific body rides in `payload` JSONB (mirrors the
--    ReportEvent discriminated union in src/data/agentReports.ts).
-- run_id is a plain column (no FK): events and their run row are independent async upserts.
create table if not exists public.scan_events (
  run_id         text not null,
  seq            int  not null,
  schema_version int  not null default 1,
  ts             timestamptz not null default now(),
  type           text not null,                       -- review_started|issue|positive|friction|journey_step|metric|progress|review_completed
  severity       text,                                -- issue
  category       text,
  page_url       text,
  title          text,
  payload        jsonb not null default '{}',         -- detail, evidence, media, metric/value/unit, step/action/outcome, ...
  primary key (run_id, seq)
);
create index if not exists idx_scan_events_run on public.scan_events (run_id, seq);
create index if not exists idx_scan_events_type on public.scan_events (type);
