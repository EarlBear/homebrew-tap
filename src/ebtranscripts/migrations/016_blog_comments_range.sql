-- Blog comments — RANGE anchoring (Axis B4). Additive to 015_blog_comments.sql.
--
-- 015 let you comment only on elements that ALREADY have a URL fragment (a heading slug,
-- a DecisionTable row, a diagram node) — re-attach was a getElementById lookup, never fuzzy
-- text matching. That constraint was the whole simplification. Then someone wanted to
-- comment on a *sentence* that isn't a fragment-anchored element. This migration adds the
-- durable "range" anchor: highlight arbitrary prose, stamp a real id, and keep enough
-- context to re-find that passage after the content is edited (a typo fix, a word added).
--
-- Three-layer durability (see docs/comments-design.md, Axis B4). This migration is layer 1,
-- the VERSION PIN + the stored context the other two layers read:
--   1. Version pin      — post_commit (git SHA of the post when the comment was made) +
--                         content_hash (hash of the anchored block's text at that time).
--   2. Build-time reconcile (self-heal) — code, migration 019; reads these columns.
--   3. Runtime fuzzy re-anchor — code; reads prefix/suffix/context_anchor.
-- quoted_text stays what it already was: a DISPLAY snapshot + drift signal, NOT a matcher.
--
-- Portable (runs on local Docker Postgres AND Supabase): pure additive DDL — add columns,
-- widen a check constraint, add an index. No Supabase-only constructs. The grant that lets
-- `authenticated` INSERT the new columns lives in 016_blog_comments_range_prod.sql (cloud
-- only), keeping the C13 portable-SQL guard green.
--
-- ORDERING HAZARD (same as 015): apply to local PG AND Supabase (Supabase MCP
-- apply_migration) BEFORE any client writes a 'range' comment. Schema first.
--
-- SAFE ON A LIVE TABLE: every column is nullable (existing fragment-anchored rows keep
-- NULL range fields), and widening a CHECK to accept an additional value never rejects an
-- existing row. blog_comments is empty at apply time regardless.

-- 1) Range context columns — all nullable (a fragment-anchored comment leaves them NULL).
--    These store TEXT + CONTEXT, never offsets/line-numbers/start-stop markers (those don't
--    survive an edit). The runtime matcher fuzzy-finds context_anchor, then disambiguates
--    with prefix/suffix when a passage repeats.
alter table public.blog_comments
  add column if not exists prefix         text,   -- ~32 chars of text immediately BEFORE the selection
  add column if not exists suffix         text,   -- ~32 chars of text immediately AFTER the selection
  add column if not exists context_anchor text,   -- the enclosing block's text (the fuzzy-match haystack)
  add column if not exists post_commit    text,   -- git SHA of the post's source when the comment was made
  add column if not exists content_hash   text;   -- hash of context_anchor at comment time (drift detector)

-- 2) Widen anchor_kind to accept 'range' alongside the fragment kinds. Drop + re-add the
--    named check so the constraint definition stays a single source of truth (idempotent:
--    guarded so a re-run doesn't error on the already-widened constraint).
do $$
begin
  alter table public.blog_comments drop constraint if exists blog_comments_anchor_kind_check;
  alter table public.blog_comments add constraint blog_comments_anchor_kind_check
    -- 'prose' (B3) is included here too so a replay of this file in any order converges to the
    -- same enum (017 also adds it). See 017_blog_comments_prose_kind.sql for the B3-vs-B4 note.
    check (anchor_kind in ('heading', 'decision', 'diagram', 'node', 'entity', 'prose', 'range'));
end $$;

-- 3) Reconcile lookup: the build-time self-heal (layer 2) scans a post's range comments by
--    (post_slug, env) — already indexed by 015 — but also needs to find rows whose
--    content_hash no longer matches the current block. A partial index on the range rows
--    keeps that scan cheap without bloating the fragment-anchored common case.
create index if not exists idx_blog_comments_range_reconcile
  on public.blog_comments (post_slug, env, content_hash)
  where anchor_kind = 'range';
