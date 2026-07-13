-- PROD-ONLY (Supabase). Extends the column-locked INSERT grant from 015_blog_comments_prod.sql
-- so `authenticated` may also write the RANGE-anchor columns added in 016_blog_comments_range.sql.
--
-- Nothing else changes: the RLS policies (read/insert-no-spoof/update-own) from 015 already
-- cover 'range' rows unchanged — they gate on author_email + the @earlbear.com domain, not on
-- anchor_kind. The realtime publication + replica identity from 015 also already cover these
-- rows (same table). This file ONLY re-issues the INSERT column grant with the 5 new columns.
--
-- Still author-supplied only: id/created_at stay defaulted (never granted), and the new
-- reconcile-managed columns (content_hash/post_commit) ARE client-supplied at insert time (the
-- client stamps the SHA + hash it saw); the build-time reconcile later rewrites them via the
-- service role, not `authenticated`, so they are NOT added to the UPDATE grant.
--
-- PROD-ONLY (references the authenticated role) — skipped by db.sh migrate. Portable additive
-- DDL is in 016_blog_comments_range.sql.

-- Re-issue the INSERT grant with the range columns appended. (Postgres has no "add a column to
-- an existing column grant" — you re-grant the full intended set; it's cumulative/idempotent.)
grant insert (
  post_slug, env, anchor_id, anchor_kind, quoted_text, body, author_email, parent_id,
  prefix, suffix, context_anchor, post_commit, content_hash
) on public.blog_comments to authenticated;

-- UPDATE grant is deliberately unchanged (body, resolved only). A comment author edits their
-- text or resolves the thread; they do NOT hand-edit the anchor's stored context. Re-anchoring
-- (rewriting content_hash/post_commit/context_anchor after a content edit) is the build-time
-- reconcile's job, run with the service role — never `authenticated` from the browser.
