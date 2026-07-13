-- PROD-ONLY (Supabase). Move ALL dashboard marts from anon `using(true)` to IDENTITY-BASED RLS.
--
-- Before: the three original marts (workflow_metrics, funnel_daily, recent_sessions) granted anon
-- SELECT `using(true)` (003_cc_rls_prod.sql) — the whole rollup was readable by anyone holding the
-- public publishable/anon key. The two newer marts (event_cost, agent_reporting, added by the
-- portable 006/007) shipped with RLS *off* and no policy at all, which under PostgREST leaves them
-- readable by the anon role's baseline table grant — same effective exposure. The security-posture
-- skill flags `using(true)` (and RLS-off tables) as the team's known weak spot: Cloudflare Access
-- gates the *page load*, not a copied-key REST call replayed from outside the gate (see the
-- every-key-in-the-system catalog).
--
-- After: exactly the scan-fleet treatment from 009_scan_fleet_identity_prod.sql. The dashboard's
-- live build mints a short-lived AUTHENTICATED-role Supabase JWT from the verified Cloudflare
-- Access identity (via the /api/auth-token Function), so RLS can see the logged-in user and
-- enforce "@earlbear.com only" in the DB — not just at the edge. A leaked publishable key alone
-- now reads NOTHING from any mart.
--
-- The build-time snapshot reads these marts with the SERVICE/SECRET key, which is RLS-exempt —
-- unchanged by this migration (that is the `build:static` path; its output ships zero key).
--
-- PROD-ONLY (references the anon/authenticated roles + policies) — skipped by db.sh migrate and by
-- check-portable-sql.sh (the *_prod.sql suffix). The portable table DDL lives in 002/004/006/007.

-- 1) Drop the permissive anon SELECT policies from 003_cc_rls_prod.sql (the three original marts).
--    (The two newer marts had no policy — nothing to drop there; `if exists` keeps this idempotent.)
drop policy if exists cc_marts_wm_read on public.mart_workflow_metrics;
drop policy if exists cc_marts_fn_read on public.mart_funnel_daily;
drop policy if exists cc_marts_rs_read on public.mart_recent_sessions;

-- 2) Ensure RLS is ON for every mart. The three originals already have it; the two newer marts
--    (event_cost, agent_reporting) shipped with it OFF — turn it on so the policies below govern
--    access instead of the anon role's baseline grant. (Idempotent — enabling twice is a no-op.)
alter table public.mart_workflow_metrics enable row level security;
alter table public.mart_funnel_daily     enable row level security;
alter table public.mart_recent_sessions  enable row level security;
alter table public.mart_event_cost       enable row level security;
alter table public.mart_agent_reporting  enable row level security;

-- 3) Read: only a logged-in @earlbear.com user (authenticated role + the email claim from the
--    minted JWT). auth.jwt() reads the request's verified JWT; anon (no token) matches nothing.
--    `if not exists` is not available for CREATE POLICY, so drop-then-create keeps re-runs clean.
drop policy if exists mart_workflow_metrics_read on public.mart_workflow_metrics;
create policy mart_workflow_metrics_read on public.mart_workflow_metrics for select to authenticated
  using ((auth.jwt() ->> 'email') like '%@earlbear.com');

drop policy if exists mart_funnel_daily_read on public.mart_funnel_daily;
create policy mart_funnel_daily_read on public.mart_funnel_daily for select to authenticated
  using ((auth.jwt() ->> 'email') like '%@earlbear.com');

drop policy if exists mart_recent_sessions_read on public.mart_recent_sessions;
create policy mart_recent_sessions_read on public.mart_recent_sessions for select to authenticated
  using ((auth.jwt() ->> 'email') like '%@earlbear.com');

drop policy if exists mart_event_cost_read on public.mart_event_cost;
create policy mart_event_cost_read on public.mart_event_cost for select to authenticated
  using ((auth.jwt() ->> 'email') like '%@earlbear.com');

drop policy if exists mart_agent_reporting_read on public.mart_agent_reporting;
create policy mart_agent_reporting_read on public.mart_agent_reporting for select to authenticated
  using ((auth.jwt() ->> 'email') like '%@earlbear.com');

-- 4) Grants: revoke SELECT from anon (a copied publishable key is now inert against the marts),
--    grant SELECT to authenticated (the minted-JWT read path). Service role bypasses RLS by
--    design — the snapshot builder's secret-key read is unaffected and needs no grant here.
revoke select on public.mart_workflow_metrics from anon;
revoke select on public.mart_funnel_daily     from anon;
revoke select on public.mart_recent_sessions  from anon;
revoke select on public.mart_event_cost       from anon;
revoke select on public.mart_agent_reporting  from anon;

grant select on public.mart_workflow_metrics to authenticated;
grant select on public.mart_funnel_daily     to authenticated;
grant select on public.mart_recent_sessions  to authenticated;
grant select on public.mart_event_cost       to authenticated;
grant select on public.mart_agent_reporting  to authenticated;

-- 5) Lock down the cc_events BASE table. The portable 006_cc_events.sql creates it with RLS OFF
--    (portable migrations never touch RLS — that is a *_prod concern). On Supabase that leaves the
--    raw event stream (session_id + cumulative cost/token columns) anon-readable via PostgREST —
--    the Supabase advisor flags it rls_disabled_in_public + sensitive_columns_exposed. Match its
--    sibling cc_* base tables (cc_tool_calls / cc_subagent_runs / cc_skill_uses), which are RLS-ON
--    with NO policy: enabling RLS without a policy denies anon/authenticated entirely; only the
--    RLS-exempt service role (the loader/snapshot key) reads it, and the dashboard reads the
--    derived mart_event_cost (gated above), never cc_events directly.
alter table public.cc_events enable row level security;
