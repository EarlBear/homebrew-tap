-- 022_artifact_tables_anon_write_lockdown_prod.sql (Supabase-only: RLS/roles)
--
-- Closes a systemic anon-WRITE hole on the dashboard-created Artifact business tables.
--
-- THE VULNERABILITY
-- Ten tables (below) each have RLS enabled with `owner insert/update/delete` policies gated on
-- `created_by = public.current_user_email()`. That function derives identity from a CLIENT-SET
-- request header and falls back to a hardcoded address:
--
--     current_user_email() :=
--       COALESCE(NULLIF(current_setting('request.headers', true)::json->>'x-user-email',''),
--                'omar@earlbear.com')
--
-- So the "owner" check is trivially spoofable: any holder of the public publishable key can set
-- `x-user-email` to any value (or omit it and be treated as omar@earlbear.com) and the policy's
-- `with_check (created_by = current_user_email())` passes — because the caller controls both sides.
-- Combined with the standing anon INSERT/UPDATE/DELETE grants, an anonymous browser caller can
-- insert/update/delete rows as any owner across all ten tables, including real business data
-- (`leads`, `shopify_intakes`). This is the same class of always-permissive anon-write that
-- 013_advisor_hardening dropped for the Instagram tables, and 021 for the IG anon-read.
--
-- (Reads are already fail-closed on 9/10 — RLS on with no SELECT policy denies anon reads. The
-- exception is `artifacts`, which has its own SELECT policy; its read posture is out of scope here
-- and tracked separately. This migration changes WRITE access only.)
--
-- THE FIX
-- Drop the three `owner` write policies and revoke INSERT/UPDATE/DELETE from anon + authenticated on
-- each table. RLS stays enabled, so with no write policy the tables become writable only by the
-- RLS-exempt service role (the intended writer for server-managed business data). No replacement
-- policy: a legitimate authenticated write path, if built, must use a REAL verified identity
-- (auth.jwt()->>'email'), not the spoofable header — added deliberately, not left open by default.
--
-- IMPACT (verified against earlbear-sites + the demo apps, 2026-07-10):
--   SAFE — no live browser writer (server/service-role written, or writes a different sandbox
--   project, or unimplemented): earl_reviews, earl_review_audit (edge fn update-earl-review,
--   service role) · sme_reviews, sme_review_items, sme_reviewers (server-only / no live writer)
--   · shopify_intakes (the intake demo writes `intakes` on the SANDBOX project
--   rkezgpfemeecygmiyixa, not this shared table).
--
--   BREAKS a direct anon-key write path (these app features stop writing once anon-write is
--   revoked, UNLESS the live deployment already routes them through the service-key proxy
--   earlbear-sites/functions/api/proxy.js, which is RLS-exempt):
--     • leads              — the public landing waitlist form (earlbear-landing App.tsx) does a
--                            direct anon POST /rest/v1/leads. Real business/PII capture.
--     • artifacts          — artifact-tracker "add artifact" INSERT (also has a public
--                            is_published SELECT policy; read side unchanged by this migration).
--     • prompt_annotations — the gallery PromptModal INSERT + PATCH(resolve).
--     • earl_review_comments — the sme-review portal comment INSERT.
--   These four must move to a real authenticated path (service-key proxy, or a verified
--   auth.jwt() identity) to keep working. Locking them here is deliberate: a spoofable-header
--   write is worse than a broken write.
--
-- Portable/_prod split: _prod-only (references the Supabase anon/authenticated roles; a local
-- single-user Postgres has neither). No portable half — these tables are dashboard-created and are
-- not defined in this migration lineage (the marts only reference them via to_regclass guards); no
-- schema change here, RLS/grants only.

-- ── artifacts ──────────────────────────────────────────────────────────────────────────────────
drop policy if exists "owner insert" on public.artifacts;
drop policy if exists "owner update" on public.artifacts;
drop policy if exists "owner delete" on public.artifacts;
revoke insert, update, delete on public.artifacts from anon, authenticated;

-- ── earl_reviews ───────────────────────────────────────────────────────────────────────────────
drop policy if exists "owner insert" on public.earl_reviews;
drop policy if exists "owner update" on public.earl_reviews;
drop policy if exists "owner delete" on public.earl_reviews;
revoke insert, update, delete on public.earl_reviews from anon, authenticated;

-- ── earl_review_comments ───────────────────────────────────────────────────────────────────────
drop policy if exists "owner insert" on public.earl_review_comments;
drop policy if exists "owner update" on public.earl_review_comments;
drop policy if exists "owner delete" on public.earl_review_comments;
revoke insert, update, delete on public.earl_review_comments from anon, authenticated;

-- ── earl_review_audit ──────────────────────────────────────────────────────────────────────────
drop policy if exists "owner insert" on public.earl_review_audit;
drop policy if exists "owner update" on public.earl_review_audit;
drop policy if exists "owner delete" on public.earl_review_audit;
revoke insert, update, delete on public.earl_review_audit from anon, authenticated;

-- ── leads ──────────────────────────────────────────────────────────────────────────────────────
drop policy if exists "owner insert" on public.leads;
drop policy if exists "owner update" on public.leads;
drop policy if exists "owner delete" on public.leads;
revoke insert, update, delete on public.leads from anon, authenticated;

-- ── prompt_annotations ─────────────────────────────────────────────────────────────────────────
drop policy if exists "owner insert" on public.prompt_annotations;
drop policy if exists "owner update" on public.prompt_annotations;
drop policy if exists "owner delete" on public.prompt_annotations;
revoke insert, update, delete on public.prompt_annotations from anon, authenticated;

-- ── shopify_intakes ────────────────────────────────────────────────────────────────────────────
drop policy if exists "owner insert" on public.shopify_intakes;
drop policy if exists "owner update" on public.shopify_intakes;
drop policy if exists "owner delete" on public.shopify_intakes;
revoke insert, update, delete on public.shopify_intakes from anon, authenticated;

-- ── sme_review_items ───────────────────────────────────────────────────────────────────────────
drop policy if exists "owner insert" on public.sme_review_items;
drop policy if exists "owner update" on public.sme_review_items;
drop policy if exists "owner delete" on public.sme_review_items;
revoke insert, update, delete on public.sme_review_items from anon, authenticated;

-- ── sme_reviewers ──────────────────────────────────────────────────────────────────────────────
drop policy if exists "owner insert" on public.sme_reviewers;
drop policy if exists "owner update" on public.sme_reviewers;
drop policy if exists "owner delete" on public.sme_reviewers;
revoke insert, update, delete on public.sme_reviewers from anon, authenticated;

-- ── sme_reviews ────────────────────────────────────────────────────────────────────────────────
drop policy if exists "owner insert" on public.sme_reviews;
drop policy if exists "owner update" on public.sme_reviews;
drop policy if exists "owner delete" on public.sme_reviews;
revoke insert, update, delete on public.sme_reviews from anon, authenticated;
