-- PROD-ONLY (Supabase). Clear the pre-existing security-advisor findings on the agent-tracker +
-- instagram subsystems (unrelated to the cc_*/mart telemetry — these objects come from the early
-- 2026-03/04 migrations). Grouped by finding, lowest-risk first. Each change was checked against how
-- the object is actually used before writing it (the readers/writers use the service-role key, which
-- bypasses RLS, so none of these changes break a live reader — verified 2026-07-09).
--
-- PROD-ONLY (references roles + Supabase-managed objects) — skipped by db.sh migrate + the portable
-- guard (the _prod.sql suffix). These objects don't exist on a bare local Postgres.

-- ── 1) function_search_path_mutable (WARN ×4) — pin search_path ──────────────────────────────────
-- A mutable search_path lets a caller's search_path influence unqualified name resolution inside the
-- function. Pinning it removes that. The two trigger-ish/trivial functions get '' (force
-- fully-qualified); the insert_agent_* functions (the SECURITY DEFINER controlled write path, gated
-- by a p_secret arg) get `= public` so any unqualified table refs in their bodies still resolve —
-- pinning to public still satisfies the advisor (search_path is no longer role-mutable). The full
-- argument signatures are required (these functions are overloaded by arity).
alter function public.set_updated_at()     set search_path = '';
alter function public.current_user_email() set search_path = '';
alter function public.insert_agent_run(
  p_secret text, p_run_date date, p_started_at timestamptz, p_ended_at timestamptz,
  p_duration_minutes integer, p_issues_queued integer, p_issues_worked integer, p_issues_passed integer,
  p_issues_failed integer, p_issues_reworked integer, p_rework_cycles_total integer,
  p_checklist_pass_rate numeric, p_checkin_issue_key text, p_issues_touched jsonb, p_observations jsonb,
  p_errors jsonb, p_tools_used jsonb, p_jira_comments_posted integer, p_attachments_uploaded integer,
  p_web_searches integer, p_transitions jsonb, p_agent_version text
) set search_path = public;
alter function public.insert_agent_issue_run(
  p_secret text, p_run_id uuid, p_issue_key text, p_summary text, p_kind text, p_action text,
  p_result text, p_version integer, p_from_status text, p_to_status text, p_duration_seconds integer,
  p_tools_used jsonb, p_web_searches integer, p_research_links jsonb, p_checklist_criteria_passed integer,
  p_checklist_criteria_total integer, p_checklist_failures jsonb, p_attachment_filename text,
  p_attachment_size_bytes integer, p_jira_comments_posted integer, p_feedback_points_received integer,
  p_feedback_points_addressed integer, p_feedback_source text, p_labels_added jsonb, p_error_type text,
  p_error_message text, p_research_log_posted boolean, p_completion_comment_posted boolean,
  p_feedback_response_posted boolean
) set search_path = public;

-- ── 2) security_definer_view (ERROR ×3) — flip to security_invoker ──────────────────────────────
-- These are read-only aggregate reporting views over agent_runs/agent_issue_runs (cost summary,
-- GA-readiness, rework tracker). As SECURITY DEFINER they run with the owner's (postgres) rights,
-- bypassing the caller's RLS. Their only real reader (ebjira) uses the SERVICE-ROLE key, which
-- bypasses RLS anyway — so flipping to security_invoker doesn't affect it. For any anon/authenticated
-- caller the views now correctly respect RLS on the underlying tables (which are RLS-on/no-policy →
-- deny), which is the secure outcome the advisor wants.
alter view public.v_cost_summary  set (security_invoker = true);
alter view public.v_ga_readiness  set (security_invoker = true);
alter view public.v_rework_tracker set (security_invoker = true);

-- ── 3) rls_policy_always_true (WARN ×2) — the instagram anon-WRITE policies ──────────────────────
-- instagram_posts / instagram_sync_log each have a `for ALL to anon using(true) with check(true)`
-- policy — an unrestricted anon write surface. The Instagram sync runs server-side with the
-- service-role key (RLS-exempt), so anon does NOT need write access. Drop the permissive anon
-- ALL policies and revoke anon writes; the service role keeps full access by bypassing RLS.
drop policy if exists "anon write posts"    on public.instagram_posts;
drop policy if exists "anon write sync log" on public.instagram_sync_log;
revoke insert, update, delete on public.instagram_posts    from anon;
revoke insert, update, delete on public.instagram_sync_log from anon;

-- ── 4) public_bucket_allows_listing (WARN) — the instagram-media bucket ──────────────────────────
-- The public bucket has a broad SELECT policy on storage.objects that lets clients LIST every file
-- (public buckets serve object URLs directly and don't need a listing policy). Drop the broad
-- listing policy; direct object-URL access still works for a public bucket.
drop policy if exists "public read instagram media" on storage.objects;

-- ── 5) auth_rls_initplan (PERF WARN ×5) — optimize the mart policies (from 011) ──────────────────
-- The @earlbear.com mart policies call auth.jwt() directly, which Postgres re-evaluates PER ROW.
-- Wrapping it as (select auth.jwt()) makes it a one-time InitPlan — same result, evaluated once.
-- Recreate each of the 5 mart SELECT policies with the wrapped form (behaviour identical; this is a
-- pure performance fix on the policies this project owns). The scan-fleet policies (009) have the
-- same pattern and can get the same treatment separately.
drop policy if exists mart_workflow_metrics_read on public.mart_workflow_metrics;
create policy mart_workflow_metrics_read on public.mart_workflow_metrics for select to authenticated
  using (((select auth.jwt()) ->> 'email') like '%@earlbear.com');
drop policy if exists mart_funnel_daily_read on public.mart_funnel_daily;
create policy mart_funnel_daily_read on public.mart_funnel_daily for select to authenticated
  using (((select auth.jwt()) ->> 'email') like '%@earlbear.com');
drop policy if exists mart_recent_sessions_read on public.mart_recent_sessions;
create policy mart_recent_sessions_read on public.mart_recent_sessions for select to authenticated
  using (((select auth.jwt()) ->> 'email') like '%@earlbear.com');
drop policy if exists mart_event_cost_read on public.mart_event_cost;
create policy mart_event_cost_read on public.mart_event_cost for select to authenticated
  using (((select auth.jwt()) ->> 'email') like '%@earlbear.com');
drop policy if exists mart_agent_reporting_read on public.mart_agent_reporting;
create policy mart_agent_reporting_read on public.mart_agent_reporting for select to authenticated
  using (((select auth.jwt()) ->> 'email') like '%@earlbear.com');

-- ── 6) anon UPLOAD to the instagram-media bucket (beyond the advisor — real storage-abuse hole) ──
-- Not advisor-flagged, but the storage.objects policy "anon upload instagram media" lets ANY holder
-- of the publishable key INSERT arbitrary files into the public instagram-media bucket (with check
-- bucket_id only — no size/type/owner limit) → hosting arbitrary content on our domain. No code in
-- any repo uploads as anon; the IG sync uploads server-side with the service-role key (RLS-exempt,
-- unaffected). Drop the anon upload policy.
drop policy if exists "anon upload instagram media" on storage.objects;
