-- PROD-ONLY (Supabase). Author soft-delete grant for blog_comments (see 020_blog_comments_soft_delete.sql).
--
-- The author-only UPDATE policy (blog_comments_update_own, from 015) already restricts an update to
-- rows where author_email = the verified JWT email — so an author, and only an author, can flip
-- their own `deleted` flag. All that's missing is the COLUMN in the update grant: 015 locked
-- authenticated to update (body, resolved) only. Widen it to (body, resolved, deleted).
--
-- Reads are intentionally UNCHANGED: a deleted comment stays SELECT-able so its thread survives
-- (replies aren't orphaned) and the client can render a "[deleted]" tombstone. Soft-delete =
-- hidden by the client, not removed by the DB. No DELETE policy is added — hard deletion remains a
-- service-role-only operation.
--
-- PROD-ONLY (references the authenticated role) — skipped by db.sh migrate; the portable column
-- add is in 020_blog_comments_soft_delete.sql. Additive grant; re-runnable.

-- Re-grant the update column set INCLUDING deleted. (grant is additive/idempotent; naming the full
-- set keeps this file self-describing rather than depending on the prior grant's exact columns.)
grant update (body, resolved, deleted) on public.blog_comments to authenticated;
