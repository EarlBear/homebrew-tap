-- PROD-ONLY (Supabase). Identity-based RLS + Realtime for blog_comments (015_blog_comments.sql).
--
-- The internal blog mints a short-lived AUTHENTICATED-role Supabase JWT from the verified
-- Cloudflare Access identity (via the /api/auth-token Function, the shared cf-supabase-auth
-- package), so RLS can see the logged-in user and enforce "@earlbear.com only" in the DB — not
-- just at the CF Access edge. Every write pins author_email to the verified JWT email (no
-- spoofing). The public (external) build never reaches this table: it has no server, no CF
-- Access, and anon (no token) matches nothing here.
--
-- PROD-ONLY (references the authenticated role + policies) — skipped by db.sh migrate. Keeps
-- the C13 portable-SQL guard green (the portable table DDL is in 015_blog_comments.sql).

-- 1) RLS on. No anon policy at all — anon (no token) reads/writes nothing.
alter table public.blog_comments enable row level security;

-- 2) Read: only a logged-in @earlbear.com user. auth.jwt() reads the request's verified JWT.
--    (select auth.jwt()) form so the planner evaluates it once per query, not per row — the
--    same initplan optimization applied to the fleet/marts in 013/014.
create policy blog_comments_read on public.blog_comments for select to authenticated
  using (((select auth.jwt()) ->> 'email') like '%@earlbear.com');

-- 3) Insert: a logged-in @earlbear.com user may add a comment, and author_email MUST equal
--    their own verified email (can't post as someone else). env is bounded to the enum; the
--    client sets it per environment (local scratch vs the deployed internal review pool) and
--    always filters its reads/subscriptions to its own env, so the two pools stay separate.
create policy blog_comments_insert on public.blog_comments for insert to authenticated
  with check (
    (((select auth.jwt()) ->> 'email') like '%@earlbear.com')
    and author_email = ((select auth.jwt()) ->> 'email')
    and env in ('local', 'internal')
  );

-- 4) Update: an author may edit/resolve their OWN comment. (Team-resolve — any @earlbear.com
--    toggling `resolved` on another's comment — is intentionally NOT granted here; revisit if
--    the team wants it. The column grant below limits an update to body/resolved only.)
create policy blog_comments_update_own on public.blog_comments for update to authenticated
  using (author_email = ((select auth.jwt()) ->> 'email'))
  with check (author_email = ((select auth.jwt()) ->> 'email'));

-- No DELETE policy for authenticated: comments are not hard-deleted from the client. (A
-- service-role cleanup or a future soft-delete flag handles removal.)

-- 5) Column-locked grants. authenticated may insert only the author-supplied columns (never
--    id/created_at — those default) and update only body/resolved.
revoke all on public.blog_comments from anon;
revoke all on public.blog_comments from authenticated;
grant  select on public.blog_comments to authenticated;
grant  insert (post_slug, env, anchor_id, anchor_kind, quoted_text, body, author_email, parent_id)
       on public.blog_comments to authenticated;
grant  update (body, resolved) on public.blog_comments to authenticated;

-- 6) Realtime: the blog subscribes to postgres_changes on blog_comments (filtered to the
--    current post_slug + env). Add to the supabase_realtime publication (idempotency-guarded)
--    and set REPLICA IDENTITY FULL so UPDATE/DELETE payloads carry the full row (a resolve
--    toggle needs the row, not just the PK). Realtime is authorized by the SELECT policy above.
do $$
begin
  alter publication supabase_realtime add table public.blog_comments;
exception when duplicate_object then null;
end $$;

alter table public.blog_comments replica identity full;
