-- Agent-reporting rollup mart.
--
-- The reporting-manager plugin (earlbear-claude-plugin-marketplace) bundles an MCP server
-- whose reporting tools appear in the session transcript as tool_use blocks named
-- `mcp__plugin_reporting-manager_reporting__<tool>`. The existing extractor already records
-- every tool_use in cc_tool_calls (tool_name, is_error) with NO extractor change — so this
-- migration only adds a mart that rolls those calls up per session + tool, and the dashboard
-- cross-checks the count against the reports persisted to ~/.claude/agent-reports.
--
-- Portable (runs on local Docker Postgres AND Supabase) — no Supabase-only constructs. Only
-- cc_tool_calls / cc_sessions (portable cc_ tables) are referenced by the new rollup, so it
-- needs no cross-table guard.
--
-- ORDERING HAZARD (same as 005/006): apply this migration to local PG AND Supabase (via the
-- Supabase MCP apply_migration) BEFORE a CLI carrying this schema runs. Schema first.

create table if not exists public.mart_agent_reporting (
  session_id uuid not null,
  day date,
  tool_name text not null,
  calls int not null default 0,
  errors int not null default 0,
  refreshed_at timestamptz default now(),
  primary key (session_id, tool_name)
);

create index if not exists idx_mart_agent_reporting_day on public.mart_agent_reporting (day);

create or replace function public.refresh_cc_marts()
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  delete from public.mart_workflow_metrics;
  insert into public.mart_workflow_metrics
    (day, stage, model, employee_id, sessions, subagent_runs, tool_calls, skill_uses,
     input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens,
     est_cost_usd, error_count)
  select
    coalesce(started_at::date, pushed_at::date) as day,
    stage,
    coalesce(model, 'unknown') as model,
    coalesce(employee_id, 'unknown') as employee_id,
    count(*),
    coalesce(sum(subagent_count), 0),
    coalesce(sum(tool_call_count), 0),
    coalesce(sum(skill_use_count), 0),
    coalesce(sum(input_tokens), 0),
    coalesce(sum(output_tokens), 0),
    coalesce(sum(cache_read_tokens), 0),
    coalesce(sum(cache_creation_tokens), 0),
    coalesce(sum(est_cost_usd), 0),
    coalesce(sum(error_count), 0)
  from public.cc_sessions
  group by 1, 2, 3, 4;

  -- Funnel mart. The four business tables (leads, sme_reviews, shopify_intakes,
  -- earl_reviews) exist only in Supabase prod; on a fresh local Postgres they are absent.
  -- We CANNOT guard them with a plain `where to_regclass(...) is not null` predicate: the
  -- planner resolves every table name in a statement before any WHERE runs, so a static
  -- reference to a missing `public.leads` still raises UndefinedTable at plan time. Instead
  -- the full (business-joined) funnel insert is built as dynamic SQL and only EXECUTEd when
  -- all four tables exist (prod); name resolution then happens at EXECUTE time. When any is
  -- absent (local) we run a cc-only funnel insert with the business columns zeroed. This
  -- keeps ONE portable refresh_cc_marts() that runs identically in both modes (the dual-mode
  -- invariant in docs/database-design.md): locally the business funnel columns are just
  -- empty (no leads on a laptop), in prod they populate. See docs/decisions.md (2026-07-07).
  -- NOTE: this block is copied VERBATIM from 005_cc_identity.sql — the cross-table guard
  -- in scripts/check-portable-sql.sh (claim C13) depends on the exact `execute $funnel$…$funnel$`
  -- shape and the matching to_regclass guards; do not alter it here.
  delete from public.mart_funnel_daily;
  if to_regclass('public.leads') is not null
     and to_regclass('public.sme_reviews') is not null
     and to_regclass('public.shopify_intakes') is not null
     and to_regclass('public.earl_reviews') is not null
  then
    execute $funnel$
      insert into public.mart_funnel_daily
        (day, leads_found, reviews_completed, customers_onboarded, enhancements_shipped,
         cc_sessions, cc_est_cost_usd)
      select
        d.day,
        coalesce(l.leads_found, 0),
        coalesce(r.reviews_completed, 0),
        coalesce(i.customers_onboarded, 0),
        coalesce(e.enhancements_shipped, 0),
        coalesce(c.cc_sessions, 0),
        coalesce(c.cc_est_cost_usd, 0)
      from (
        select distinct day from (
          select created_at::date as day from public.leads
          union select submitted_at::date from public.sme_reviews
          union select created_at::date from public.shopify_intakes
          union select queued_at::date from public.earl_reviews
          union select coalesce(started_at::date, pushed_at::date) from public.cc_sessions
        ) days where day is not null
      ) d
      left join (
        select created_at::date as day, count(*) as leads_found
        from public.leads group by 1
      ) l on l.day = d.day
      left join (
        select submitted_at::date as day, count(*) as reviews_completed
        from public.sme_reviews group by 1
      ) r on r.day = d.day
      left join (
        select created_at::date as day, count(*) as customers_onboarded
        from public.shopify_intakes group by 1
      ) i on i.day = d.day
      left join (
        select queued_at::date as day, count(*) as enhancements_shipped
        from public.earl_reviews where status = 'shipped' group by 1
      ) e on e.day = d.day
      left join (
        select coalesce(started_at::date, pushed_at::date) as day,
               count(*) as cc_sessions, coalesce(sum(est_cost_usd), 0) as cc_est_cost_usd
        from public.cc_sessions group by 1
      ) c on c.day = d.day
    $funnel$;
  else
    -- Local mode: no business tables. The funnel still reports the cc-derived columns per
    -- day (session count + cost); the business columns are zero because those events don't
    -- exist off-prod. This is a plain, always-resolvable statement (only cc_sessions).
    insert into public.mart_funnel_daily
      (day, leads_found, reviews_completed, customers_onboarded, enhancements_shipped,
       cc_sessions, cc_est_cost_usd)
    select
      coalesce(started_at::date, pushed_at::date) as day,
      0, 0, 0, 0,
      count(*) as cc_sessions,
      coalesce(sum(est_cost_usd), 0) as cc_est_cost_usd
    from public.cc_sessions
    where coalesce(started_at::date, pushed_at::date) is not null
    group by 1;
  end if;

  delete from public.mart_recent_sessions;
  insert into public.mart_recent_sessions
    (session_id, stage, title, started_at, duration_seconds, total_tokens,
     est_cost_usd, tool_call_count, subagent_count, transcript_url)
  select
    session_id, stage, first_prompt_excerpt, started_at, duration_seconds,
    input_tokens + output_tokens, est_cost_usd, tool_call_count, subagent_count,
    transcript_url
  from public.cc_sessions
  where is_published = true;

  -- Cost-over-time mart: the cumulative cost curve, from the event stream. Only cc_events
  -- (a portable cc_ table) is referenced, so no cross-table guard is needed here.
  delete from public.mart_event_cost;
  insert into public.mart_event_cost
    (session_id, seq, ts, employee_id, cum_tool_calls, cum_input_tokens,
     cum_output_tokens, cum_est_cost_usd)
  select
    session_id, seq, ts, employee_id, cum_tool_calls, cum_input_tokens,
    cum_output_tokens, cum_est_cost_usd
  from public.cc_events
  where cum_est_cost_usd is not null;

  -- Agent-reporting rollup: per session + reporting tool, how many times it was called and
  -- how many errored. Matches the reporting-manager plugin's namespaced MCP tool prefix
  -- `mcp__plugin_reporting-manager_reporting__*` (the `\` escapes the LIKE wildcards `_`).
  -- Only cc_tool_calls / cc_sessions are referenced (portable cc_ tables), so no cross-table
  -- guard is needed. The dashboard cross-checks these counts against the reports persisted on
  -- disk to catch dropped reports.
  delete from public.mart_agent_reporting;
  insert into public.mart_agent_reporting
    (session_id, day, tool_name, calls, errors)
  select
    tc.session_id,
    coalesce(s.started_at::date, s.pushed_at::date) as day,
    tc.tool_name,
    count(*) as calls,
    count(*) filter (where tc.is_error) as errors
  from public.cc_tool_calls tc
  join public.cc_sessions s on s.session_id = tc.session_id
  where tc.tool_name like 'mcp\_\_plugin\_reporting-manager\_reporting\_\_%'
  group by tc.session_id, coalesce(s.started_at::date, s.pushed_at::date), tc.tool_name;
end;
$$;

revoke execute on function public.refresh_cc_marts() from public;
