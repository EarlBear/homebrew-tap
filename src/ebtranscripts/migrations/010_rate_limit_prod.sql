-- PROD-ONLY (Supabase). Rate-limit the write surface (the scan_requests queue) — defense-in-
-- depth per Supabase's "Securing your API" guidance. A PostgREST pre-request hook caps modifying
-- requests per client IP and returns HTTP 420 over quota. Only POST/PUT/PATCH/DELETE are
-- rate-limited (GET/HEAD run read-only and can't write the counter).
--
-- The hook function lives in the `private` schema so PostgREST does NOT expose it as an RPC
-- endpoint (a public.* SECURITY DEFINER function is callable via /rest/v1/rpc — the Supabase
-- security advisor flags that, and a client could spam it to fill the counter). The request
-- roles get USAGE on `private` + EXECUTE on the function so the hook runs; `private.rate_limits`
-- itself is never in the exposed schema, so it's not REST-readable.
--
-- Reads the real client IP from Cloudflare's `cf-connecting-ip` header; caps at 30 writes / 5min
-- per IP (lower than the docs' 100 — this is an internal tool). Note: on a request the main query
-- then rejects (e.g. an anon write with no grant), the whole transaction — including the hook's
-- counter INSERT — rolls back, so only SUCCESSFUL writes (an authenticated @earlbear.com insert)
-- accumulate. That's the intent: the limiter protects the authenticated write path; anon writes
-- are already hard-denied by RLS (009).
--
-- PROD-ONLY (SECURITY DEFINER function + authenticator role) — skipped by db.sh migrate.

create schema if not exists private;

create table if not exists private.rate_limits (
  ip         inet,
  request_at timestamptz not null default now()
);
create index if not exists rate_limits_ip_request_at_idx on private.rate_limits (ip, request_at desc);

create or replace function private.check_request()
  returns void
  language plpgsql
  security definer
  set search_path = public, private
  as $$
declare
  req_method text := current_setting('request.method', true);
  raw_ip text := coalesce(
    current_setting('request.headers', true)::json ->> 'cf-connecting-ip',
    split_part(current_setting('request.headers', true)::json ->> 'x-forwarded-for', ',', 1)
  );
  req_ip inet;
  recent integer;
begin
  if req_method is null or req_method in ('GET', 'HEAD', 'OPTIONS') then
    return;
  end if;
  if raw_ip is null or raw_ip = '' then
    return; -- e.g. the service-role MCP writer (no CF IP header) — trusted, not throttled
  end if;
  begin
    req_ip := raw_ip::inet;
  exception when others then
    return; -- unparseable IP → don't block
  end;

  select count(*) into recent
  from private.rate_limits
  where ip = req_ip and request_at between now() - interval '5 minutes' and now();

  if recent > 30 then
    raise sqlstate 'PGRST' using
      message = json_build_object('message', 'Rate limit exceeded, try again shortly')::text,
      detail  = json_build_object('status', 420, 'status_text', 'Enhance Your Calm')::text;
  end if;

  insert into private.rate_limits (ip, request_at) values (req_ip, now());
end;
$$;

-- The request roles need USAGE on the private schema + EXECUTE on the hook, or PostgREST rejects
-- EVERY request with "permission denied for function check_request". SECURITY DEFINER still runs
-- it as owner, so this doesn't widen privilege; `private.rate_limits` stays out of the exposed
-- (public) schema, so it's not REST-readable.
grant usage on schema private to anon, authenticated;
grant execute on function private.check_request() to anon, authenticated;

-- Wire it as the PostgREST pre-request hook (runs before every Data API request).
alter role authenticator set pgrst.db_pre_request = 'private.check_request';
notify pgrst, 'reload config';
