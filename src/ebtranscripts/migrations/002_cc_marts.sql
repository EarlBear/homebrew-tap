-- Pre-aggregated marts — the only cc_ surface the public dashboard reads. Rebuilt in full
-- by refresh_cc_marts() (data is tiny). Joins the real business tables verified via MCP:
--   leads(created_at), shopify_intakes(created_at, validation_pass),
--   sme_reviews(verdict, submitted_at), earl_reviews(status, queued_at),
--   agent_runs(run_date, total_cost_usd).

create table if not exists public.mart_workflow_metrics (
  day date not null,
  stage text not null,
  sessions int default 0,
  subagent_runs int default 0,
  tool_calls int default 0,
  skill_uses int default 0,
  input_tokens bigint default 0,
  output_tokens bigint default 0,
  cache_read_tokens bigint default 0,
  cache_creation_tokens bigint default 0,
  est_cost_usd numeric(12,4) default 0,
  error_count int default 0,
  refreshed_at timestamptz default now(),
  primary key (day, stage)
);

create table if not exists public.mart_funnel_daily (
  day date primary key,
  leads_found int default 0,
  reviews_completed int default 0,
  customers_onboarded int default 0,
  enhancements_shipped int default 0,
  cc_sessions int default 0,
  cc_est_cost_usd numeric(12,4) default 0,
  refreshed_at timestamptz default now()
);

create table if not exists public.mart_recent_sessions (
  session_id uuid primary key,
  stage text,
  title text,
  started_at timestamptz,
  duration_seconds int,
  total_tokens bigint,
  est_cost_usd numeric(10,4),
  tool_call_count int,
  subagent_count int,
  transcript_url text,
  refreshed_at timestamptz default now()
);

create or replace function public.refresh_cc_marts()
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  -- Per-stage per-day execution rollup from the cc_ tables.
  delete from public.mart_workflow_metrics;
  insert into public.mart_workflow_metrics
    (day, stage, sessions, subagent_runs, tool_calls, skill_uses,
     input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens,
     est_cost_usd, error_count)
  select
    coalesce(started_at::date, pushed_at::date) as day,
    stage,
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
  group by 1, 2;

  -- Daily business funnel, joined by day across the real business tables + cc rollup.
  -- The business tables (leads, sme_reviews, shopify_intakes, earl_reviews) live only in
  -- Supabase prod; on a fresh local Postgres they are absent. A plain `where to_regclass(...)`
  -- guard would NOT help — the planner resolves every table name before any WHERE runs, so a
  -- static reference to a missing table raises UndefinedTable at plan time. So the full
  -- business-joined insert is built as dynamic SQL and only EXECUTEd when all four tables
  -- exist (prod); otherwise (local) a cc-only insert runs with the business columns zeroed.
  -- Keeps ONE portable refresh_cc_marts() identical in both modes. See docs/decisions.md
  -- (2026-07-07) and docs/database-design.md.
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

  -- Recent published sessions only.
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
end;
$$;

-- Functions are granted to PUBLIC by default, which would let anon call this via REST.
-- Revoke PUBLIC too so only the service-role (bypasses grants) can rebuild the marts.
revoke execute on function public.refresh_cc_marts() from public;
