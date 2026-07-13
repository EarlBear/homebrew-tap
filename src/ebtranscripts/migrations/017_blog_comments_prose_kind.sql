-- Blog comments — add the 'prose' anchor_kind (B3). Portable. Additive to 015/016.
--
-- Latent-gap fix: the shipped client (src/data/comments.ts, from the B3 rehype block-id work)
-- sends anchor_kind='prose' when a comment attaches to a rehype-id'd prose block (an eb-<hash>
-- <p>/<li>/<blockquote>). But the check constraint from 015 never included 'prose', so such an
-- insert would fail. It stayed latent only because blog_comments is empty (the prose path was
-- never exercised against prod). This widens the enum so B3 works.
--
-- Two distinct prose-ish kinds now coexist, and they re-anchor DIFFERENTLY — which is why they
-- are separate values, not merged:
--   'prose' (B3) — a stable build-time block id (eb-<hash>). Re-attach = getElementById. Cheap,
--                  exact, no fuzzy search. The whole-element fast path.
--   'range' (B4) — a free-text selection with no pre-existing id. Re-attach = fuzzy-match the
--                  saved context (prefix/suffix/context_anchor). The durable-but-searching path.
--
-- Portable additive DDL (widen a CHECK). Safe on a live table: adding an accepted value never
-- rejects an existing row; blog_comments is empty regardless. No grant change needed — the
-- INSERT column grant already covers anchor_kind.

do $$
begin
  alter table public.blog_comments drop constraint if exists blog_comments_anchor_kind_check;
  alter table public.blog_comments add constraint blog_comments_anchor_kind_check
    check (anchor_kind in ('heading', 'decision', 'diagram', 'node', 'entity', 'prose', 'range'));
end $$;
