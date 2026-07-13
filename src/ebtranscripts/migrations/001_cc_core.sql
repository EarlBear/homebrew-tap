-- ebtranscripts core tables: derived Claude Code session telemetry.
-- Prefixed cc_ to avoid colliding with the existing agent_runs/agent_logs. Never holds
-- raw content — only derived metrics and bounded, redacted excerpts.

create table if not exists public.cc_sessions (
  session_id uuid primary key,
  project_slug text not null,
  cwd text,
  git_branch text,
  stage text not null default 'other',
  started_at timestamptz,
  ended_at timestamptz,
  duration_seconds int,
  model text,
  claude_version text,
  num_turns int default 0,
  num_user_msgs int default 0,
  num_assistant_msgs int default 0,
  input_tokens bigint default 0,
  output_tokens bigint default 0,
  cache_read_tokens bigint default 0,
  cache_creation_tokens bigint default 0,
  est_cost_usd numeric(10,4) default 0,
  tool_call_count int default 0,
  subagent_count int default 0,
  skill_use_count int default 0,
  error_count int default 0,
  first_prompt_excerpt text,
  is_published boolean not null default false,
  transcript_url text,
  sanitizer_version text not null,
  extractor_version text not null,
  pushed_at timestamptz not null default now()
);

create table if not exists public.cc_tool_calls (
  session_id uuid not null references public.cc_sessions on delete cascade,
  tool_use_id text not null,
  msg_uuid text,
  ts timestamptz,
  tool_name text not null,
  is_sidechain boolean default false,
  input_summary text,
  input_bytes int default 0,
  result_bytes int default 0,
  is_error boolean default false,
  duration_ms int,
  primary key (session_id, tool_use_id)
);

create table if not exists public.cc_subagent_runs (
  session_id uuid not null references public.cc_sessions on delete cascade,
  task_tool_use_id text not null,
  agent_name text,
  description_excerpt text,
  started_at timestamptz,
  ended_at timestamptz,
  duration_seconds int,
  input_tokens bigint default 0,
  output_tokens bigint default 0,
  tool_call_count int default 0,
  success boolean,
  primary key (session_id, task_tool_use_id)
);

create table if not exists public.cc_skill_uses (
  session_id uuid not null references public.cc_sessions on delete cascade,
  msg_uuid text not null,
  ts timestamptz,
  skill_name text not null,
  source text check (source in ('skill-tool','slash-command')),
  args_excerpt text,
  primary key (session_id, msg_uuid)
);

create index if not exists cc_sessions_stage_started_idx
  on public.cc_sessions (stage, started_at);
create index if not exists cc_tool_calls_session_idx
  on public.cc_tool_calls (session_id);
create index if not exists cc_subagent_runs_session_idx
  on public.cc_subagent_runs (session_id);
create index if not exists cc_skill_uses_session_idx
  on public.cc_skill_uses (session_id);

comment on table public.cc_sessions is
  'Derived Claude Code session telemetry. Written by ebtranscripts via service_role. Redacted excerpts only, never raw content.';
