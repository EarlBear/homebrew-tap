-- 021_instagram_read_lockdown_prod.sql (Supabase-only: RLS/roles)
--
-- Follow-up to 013_advisor_hardening_prod, which dropped the instagram anon-WRITE policies but left
-- the anon-READ policies in place. Those remaining policies are:
--
--   instagram_posts     — "anon read posts"     for SELECT to public using (true)
--   instagram_sync_log  — "anon read sync log"  for SELECT to public using (true)
--
-- i.e. an unauthenticated `using(true)` read of the entire Instagram feed + its sync log. The
-- Supabase advisor does not flag these (a SELECT `using(true)` is excluded from rls_policy_always_true),
-- so they survived the 013 sweep — but on review the IG tables are NOT meant to be publicly readable.
-- No frontend reads them (the blog/gtm apps make zero calls to either table); the Instagram sync runs
-- server-side with the service-role key, which is RLS-exempt and therefore unaffected by dropping anon
-- access. So the anon read surface is gap, not a feature — close it.
--
-- Drop the two anon-read policies and revoke the anon SELECT grant. No replacement policy: the only
-- legitimate reader is the RLS-exempt service role (and, if a gated in-app IG view is ever built, it
-- would get its own `@earlbear.com` authenticated policy then — added deliberately, not left open by
-- default). RLS stays enabled on both tables, so with no policy anon now reads nothing (fail-closed).
--
-- Portable/_prod split: this is _prod-only (policies reference the Supabase `anon` role, which a local
-- Postgres does not have). There is no portable half — the tables already exist and no schema changes.

drop policy if exists "anon read posts"    on public.instagram_posts;
drop policy if exists "anon read sync log" on public.instagram_sync_log;

revoke select on public.instagram_posts    from anon;
revoke select on public.instagram_sync_log from anon;
