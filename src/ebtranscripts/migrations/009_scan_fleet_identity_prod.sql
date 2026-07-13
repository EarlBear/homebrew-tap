-- PROD-ONLY (Supabase). Move the scan fleet from anon `using(true)` to IDENTITY-BASED RLS.
--
-- Before: the fleet tables granted anon SELECT `using(true)` — the whole tally was readable by
-- anyone holding the (public) anon key. The security-posture skill flags `using(true)` as the
-- team's known weak spot. Now that the dashboard mints a short-lived AUTHENTICATED-role Supabase
-- JWT from the verified Cloudflare Access identity (via the /api/auth-token Function), RLS can
-- see the logged-in user and enforce "@earlbear.com only" in the DB — not just at the edge.
--
-- The reporting MCP server keeps writing scan_runs/scan_events with the SERVICE key, which is
-- RLS-exempt — unchanged. Realtime (postgres_changes) is authorized against the new
-- authenticated SELECT policies, so the live fleet keeps working over the minted JWT.
--
-- PROD-ONLY (references the anon/authenticated roles + policies) — skipped by db.sh migrate.

-- 1) Drop the permissive anon policies from 008_scan_fleet_prod.sql.
drop policy if exists scan_sites_read        on public.scan_sites;
drop policy if exists scan_requests_read     on public.scan_requests;
drop policy if exists scan_runs_read         on public.scan_runs;
drop policy if exists scan_events_read       on public.scan_events;
drop policy if exists scan_requests_anon_insert on public.scan_requests;

-- 2) Read: only a logged-in @earlbear.com user (authenticated role + the email claim from the
--    minted JWT). auth.jwt() reads the request's verified JWT; anon (no token) matches nothing.
create policy scan_sites_read on public.scan_sites for select to authenticated
  using ((auth.jwt() ->> 'email') like '%@earlbear.com');
create policy scan_requests_read on public.scan_requests for select to authenticated
  using ((auth.jwt() ->> 'email') like '%@earlbear.com');
create policy scan_runs_read on public.scan_runs for select to authenticated
  using ((auth.jwt() ->> 'email') like '%@earlbear.com');
create policy scan_events_read on public.scan_events for select to authenticated
  using ((auth.jwt() ->> 'email') like '%@earlbear.com');

-- 3) Request a review: a logged-in @earlbear.com user may INSERT a queued row, and the
--    requested_by MUST equal their own verified email (can't spoof another user). Still no
--    UPDATE/DELETE for authenticated users — only the service-role writer advances a row.
create policy scan_requests_authed_insert on public.scan_requests for insert to authenticated
  with check (
    (auth.jwt() ->> 'email') like '%@earlbear.com'
    and requested_by = (auth.jwt() ->> 'email')
    and status = 'queued'
    and run_id is null
    and started_at is null
    and finished_at is null
  );

-- 4) Re-grant the column-locked INSERT to the authenticated role (008 granted it to anon).
--    requested_by is now required (the policy checks it), so include it in the grant.
revoke all on public.scan_requests from anon;
revoke all on public.scan_requests from authenticated;
grant  select on public.scan_requests to authenticated;
grant  insert (target_url, page_url, status, requested_by) on public.scan_requests to authenticated;
grant  select on public.scan_sites  to authenticated;
grant  select on public.scan_runs   to authenticated;
grant  select on public.scan_events to authenticated;
