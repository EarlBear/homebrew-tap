-- Blog comments — a Figma-style, fragment-anchored comment thread for the INTERNAL blog
-- (blog.internal.earlbear.com, behind Cloudflare Access). A comment anchors to an element
-- that already has a URL fragment (a heading slug id, a DecisionTable row #d1, a diagram
-- [data-flow]/[data-node]) so re-attach is a getElementById lookup, not fuzzy text matching.
-- The internal blog reads/writes these live over Supabase Realtime (postgres_changes) with a
-- minted @earlbear.com JWT; the public (external) build has no comments at all — no server,
-- no CF Access, RLS denies anon. See docs/comments-design.md (id blog-comments).
--
-- Portable (runs on local Docker Postgres AND Supabase): pure DDL — no Supabase-only
-- constructs, no cross-table DML. RLS + the realtime publication live in
-- 015_blog_comments_prod.sql (cloud only, skipped by scripts/db.sh migrate). This keeps the
-- C13 portable-SQL guard (scripts/check-portable-sql.sh) green.
--
-- ORDERING HAZARD (same as 005-008): apply this migration to local PG AND Supabase (via the
-- Supabase MCP apply_migration) BEFORE any client insert runs against it. Schema first.
--
-- Namespaced blog_comments — the shared project already has an unrelated earl_review_comments.

create table if not exists public.blog_comments (
  id           uuid primary key default gen_random_uuid(),
  post_slug    text not null,                       -- the post the comment lives on
  env          text not null default 'internal'     -- partition: local scratch vs the deployed
    check (env in ('local', 'internal')),           --   review pool; external build has none
  anchor_id    text not null,                        -- the element fragment id (or data-* value)
  anchor_kind  text not null                         -- what kind of element it anchors to
    check (anchor_kind in ('heading', 'decision', 'diagram', 'node', 'entity')),
  quoted_text  text,                                 -- display snapshot of the anchored text +
                                                     --   a drift signal; NOT a re-anchoring key
  body         text not null,
  author_email text not null,                        -- pinned to the verified JWT email (in _prod)
  parent_id    uuid references public.blog_comments(id) on delete cascade,  -- threading (replies)
  resolved     boolean not null default false,
  created_at   timestamptz not null default now()
);

-- Read/subscribe path: comments for one post in one environment.
create index if not exists idx_blog_comments_post_env
  on public.blog_comments (post_slug, env);
-- Marker lookup: comments anchored to a specific element.
create index if not exists idx_blog_comments_post_env_anchor
  on public.blog_comments (post_slug, env, anchor_id);
-- Thread assembly: a comment's replies.
create index if not exists idx_blog_comments_parent
  on public.blog_comments (parent_id);
