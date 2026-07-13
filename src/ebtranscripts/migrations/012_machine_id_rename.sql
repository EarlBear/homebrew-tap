-- Rename employee_id → machine_id across the cc_* tables + the workflow-metrics mart.
--
-- The identity stamped by identity.py is now the hardware SERIAL NUMBER (a machine, not a person —
-- it replaced whoami:hostname to be stable across renames and to stop leaking a username). So the
-- column name `employee_id` is now misleading: it holds a machine identifier. Rename it to
-- `machine_id` everywhere it lives so the schema tells the truth.
--
-- Portable (runs on local Docker Postgres AND Supabase) — `alter table … rename column` is plain
-- SQL, no Supabase-only constructs. RENAME COLUMN preserves the mart_workflow_metrics primary key
-- (day, stage, model, employee_id → …, machine_id) automatically, so no PK rebuild is needed.
--
-- ORDERING HAZARD (same as 005/006/007): the push loader sends every SessionRecord field as an
-- upsert column, so a CLI carrying the renamed field (SessionRecord.machine_id) must NOT run against
-- a DB that still has the old column, and vice versa. Apply this migration to local PG AND Supabase
-- BEFORE rolling the CLI that renames the field. Schema first, then the code roll.
--
-- refresh_cc_marts() is redefined below with machine_id in place of employee_id (its body is
-- otherwise copied verbatim from 007 — the C13 portability guard depends on the $funnel$ block's
-- exact shape; only the employee_id→machine_id identifiers changed).

alter table public.cc_sessions          rename column employee_id to machine_id;
alter table public.cc_events             rename column employee_id to machine_id;
alter table public.mart_workflow_metrics rename column employee_id to machine_id;
alter table public.mart_event_cost       rename column employee_id to machine_id;

-- The employee attribution index → machine index (rename for clarity; idempotent guard).
alter index if exists idx_cc_sessions_employee rename to idx_cc_sessions_machine;

create or replace function public.refresh_cc_marts()
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  delete from public.mart_workflow_metrics;
  insert into public.mart_workflow_metrics
    (day, stage, model, machine_id, sessions, subagent_runs, tool_calls, skill_uses,
     input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens,
     est_cost_usd, error_count)
  select
    coalesce(started_at::date, pushed_at::date) as day,
    stage,
    coalesce(model, 'unknown') as model,
    coalesce(machine_id, 'unknown') as machine_id,
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

  -- Funnel mart. Copied VERBATIM from 007_agent_reporting.sql — the cross-table guard in
  -- scripts/check-portable-sql.sh (claim C13) depends on the exact `execute $funnel$…$funnel$`
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

  delete from public.mart_event_cost;
  insert into public.mart_event_cost
    (session_id, seq, ts, machine_id, cum_tool_calls, cum_input_tokens,
     cum_output_tokens, cum_est_cost_usd)
  select
    session_id, seq, ts, machine_id, cum_tool_calls, cum_input_tokens,
    cum_output_tokens, cum_est_cost_usd
  from public.cc_events
  where cum_est_cost_usd is not null;

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
