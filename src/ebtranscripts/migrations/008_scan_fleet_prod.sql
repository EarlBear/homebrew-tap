-- PROD-ONLY (Supabase). RLS + the Realtime publication for the scan fleet. References the
-- Supabase anon role + row-level security, which don't exist on bare local Postgres, so the
-- local runner (scripts/db.sh migrate) skips *_prod.sql; only Supabase applies it. The
-- portable schema lives in 008_scan_fleet.sql.
--
-- Posture: the whole dashboard sits behind Cloudflare Access, and the anon key is read-only
-- by RLS. Anon may SELECT all fleet tables (the public tally + domain metrics) and INSERT a
-- 'queued' scan_request it cannot self-promote. Every write to scan_runs/scan_events (and all
-- queue status transitions) comes from the reporting MCP server's SERVICE-ROLE writer key,
-- which bypasses RLS — the key lives only in the operator's shell env, never in the frontend.

alter table public.scan_sites    enable row level security;
alter table public.scan_requests enable row level security;
alter table public.scan_runs     enable row level security;
alter table public.scan_events   enable row level security;

-- Anon may READ the whole fleet (public tally behind CF Access). Follows the anon-read policy
-- style from 003_cc_rls_prod.sql.
create policy scan_sites_read    on public.scan_sites    for select to anon using (true);
create policy scan_requests_read on public.scan_requests for select to anon using (true);
create policy scan_runs_read     on public.scan_runs     for select to anon using (true);
create policy scan_events_read   on public.scan_events   for select to anon using (true);

-- Anon may INSERT into scan_requests ONLY, and only a 'queued' row it cannot pre-claim. No
-- anon UPDATE/DELETE policy anywhere → anon can never advance or bind a row; only the
-- service-role writer transitions queued→scanning→done.
create policy scan_requests_anon_insert on public.scan_requests
  for insert to anon
  with check (
    status = 'queued'
    and run_id is null
    and started_at is null
    and finished_at is null
  );

-- Column-level lockdown: even under the row policy, anon may supply only these four columns.
-- (id is identity-generated; requested_at defaults; everything else defaults null.)
revoke all on public.scan_requests from anon;
grant  select on public.scan_requests to anon;
grant  insert (target_url, page_url, status, requested_by) on public.scan_requests to anon;

-- Realtime: the dashboard subscribes to postgres_changes on these tables. Add each to the
-- supabase_realtime publication (idempotency-guarded — re-adding a member errors), and set
-- REPLICA IDENTITY FULL so UPDATE/DELETE payloads carry the full row (default identity ships
-- only the PK on UPDATE — the fleet needs the changed count_*/status/metric columns).
do $$
begin
  alter publication supabase_realtime add table public.scan_sites;
exception when duplicate_object then null;
end $$;
do $$
begin
  alter publication supabase_realtime add table public.scan_requests;
exception when duplicate_object then null;
end $$;
do $$
begin
  alter publication supabase_realtime add table public.scan_runs;
exception when duplicate_object then null;
end $$;
do $$
begin
  alter publication supabase_realtime add table public.scan_events;
exception when duplicate_object then null;
end $$;

alter table public.scan_sites    replica identity full;
alter table public.scan_requests replica identity full;
alter table public.scan_runs     replica identity full;
alter table public.scan_events   replica identity full;
