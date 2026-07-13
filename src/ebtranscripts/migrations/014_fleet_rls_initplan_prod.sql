-- PROD-ONLY (Supabase). Perf: optimize the scan-fleet RLS policies' auth.jwt() calls.
--
-- The fleet policies (009_scan_fleet_identity_prod.sql) call auth.jwt() bare, which Postgres
-- re-evaluates PER ROW. Wrapping it as (select auth.jwt()) makes it a one-time InitPlan — same
-- result, evaluated once for the whole query. This clears the advisor's auth_rls_initplan PERF WARN
-- on scan_sites / scan_requests / scan_runs / scan_events. Behaviour is IDENTICAL (same predicate,
-- same @earlbear.com gate) — this is the same optimization migration 013 applied to the marts.
--
-- Each policy is dropped + recreated with its EXACT predicate, only the auth.jwt() calls wrapped.
-- The insert policy's column-lock check (requested_by / status / run_id / *_at) is preserved verbatim.
--
-- PROD-ONLY (references the anon/authenticated roles + policies) — skipped by db.sh migrate + the
-- portable guard (the _prod.sql suffix).

-- Reads: @earlbear.com only (authenticated role + the email claim), auth.jwt() → (select auth.jwt()).
drop policy if exists scan_sites_read on public.scan_sites;
create policy scan_sites_read on public.scan_sites for select to authenticated
  using (((select auth.jwt()) ->> 'email') like '%@earlbear.com');

drop policy if exists scan_requests_read on public.scan_requests;
create policy scan_requests_read on public.scan_requests for select to authenticated
  using (((select auth.jwt()) ->> 'email') like '%@earlbear.com');

drop policy if exists scan_runs_read on public.scan_runs;
create policy scan_runs_read on public.scan_runs for select to authenticated
  using (((select auth.jwt()) ->> 'email') like '%@earlbear.com');

drop policy if exists scan_events_read on public.scan_events;
create policy scan_events_read on public.scan_events for select to authenticated
  using (((select auth.jwt()) ->> 'email') like '%@earlbear.com');

-- Insert: a logged-in @earlbear.com user may INSERT a queued row it can't pre-claim, and
-- requested_by MUST equal their own verified email. Same predicate as 009, auth.jwt() wrapped.
drop policy if exists scan_requests_authed_insert on public.scan_requests;
create policy scan_requests_authed_insert on public.scan_requests for insert to authenticated
  with check (
    ((select auth.jwt()) ->> 'email') like '%@earlbear.com'
    and requested_by = ((select auth.jwt()) ->> 'email')
    and status = 'queued'
    and run_id is null
    and started_at is null
    and finished_at is null
  );
