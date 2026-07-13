-- Event stream + cost-over-time mart.
--
-- The Drive corpus is an allowlist-built event append-log (events.ndjson) with a cumulative
-- cost/count block on each event. Until now that log was file-only; this migration gives it a
-- home in the DB so the dashboard can show a per-session cost timeline ("cost as of event N").
--
-- Portable (runs on local Docker Postgres AND Supabase) — no Supabase-only constructs.
--
-- ORDERING HAZARD (same as 005): the loader (refresh-from-drive) sends every EventRecord field
-- as an upsert column, so this migration MUST be applied to local PG AND Supabase (via the
-- Supabase MCP apply_migration) BEFORE a CLI carrying the event loader runs. Schema first.

create table if not exists public.cc_events (
  session_id uuid not null references public.cc_sessions on delete cascade,
  seq int not null,                      -- 0-based order within the session's event log
  kind text not null,                    -- session_start | tool_call | subagent_run | skill_use | metrics_snapshot
  ts timestamptz,
  tool text,
  agent text,
  skill text,
  is_error boolean default false,
  input_bytes bigint default 0,
  result_bytes bigint default 0,
  -- Cumulative aggregates AS OF this event (from the event log's `cum` block).
  cum_tool_calls int default 0,
  cum_subagent_runs int default 0,
  cum_skill_uses int default 0,
  cum_errors int default 0,
  cum_input_tokens bigint default 0,
  cum_output_tokens bigint default 0,
  cum_est_cost_usd numeric(12,6) default 0,
  employee_id text,
  machine text,
  refreshed_at timestamptz default now(),
  primary key (session_id, seq)
);

create index if not exists idx_cc_events_session_ts on public.cc_events (session_id, ts);
create index if not exists idx_cc_events_kind on public.cc_events (kind);

-- Cost-over-time mart: the cumulative cost curve per session, one row per event that has a
-- cumulative cost. The dashboard reads this to draw "spend over the session timeline".
create table if not exists public.mart_event_cost (
  session_id uuid not null,
  seq int not null,
  ts timestamptz,
  employee_id text,
  cum_tool_calls int default 0,
  cum_input_tokens bigint default 0,
  cum_output_tokens bigint default 0,
  cum_est_cost_usd numeric(12,6) default 0,
  refreshed_at timestamptz default now(),
  primary key (session_id, seq)
);

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
end;
$$;

revoke execute on function public.refresh_cc_marts() from public;
