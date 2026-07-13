-- PROD-ONLY (Supabase). This migration references the Supabase roles anon/authenticated
-- and RLS, which do not exist on bare local Postgres — so the local runner skips *_prod.sql
-- and only Supabase applies it. Portable schema + marts logic live in the non-_prod files.
--
-- RLS: the public dashboard (anon key) may read the marts and published sessions only.
-- Detail tables have no anon policy. Service-role writes bypass RLS.

alter table public.cc_sessions enable row level security;
alter table public.cc_tool_calls enable row level security;
alter table public.cc_subagent_runs enable row level security;
alter table public.cc_skill_uses enable row level security;
alter table public.mart_workflow_metrics enable row level security;
alter table public.mart_funnel_daily enable row level security;
alter table public.mart_recent_sessions enable row level security;

-- Anon may read marts.
create policy cc_marts_wm_read on public.mart_workflow_metrics for select to anon using (true);
create policy cc_marts_fn_read on public.mart_funnel_daily for select to anon using (true);
create policy cc_marts_rs_read on public.mart_recent_sessions for select to anon using (true);

-- Anon may read only published session rows; nothing on the detail tables.
create policy cc_sessions_published_read on public.cc_sessions
  for select to anon using (is_published = true);

-- Belt-and-suspenders: also revoke the marts-refresh function from the Supabase roles
-- (the portable migrations already revoke it from PUBLIC, which covers this on local).
revoke execute on function public.refresh_cc_marts() from anon, authenticated;
