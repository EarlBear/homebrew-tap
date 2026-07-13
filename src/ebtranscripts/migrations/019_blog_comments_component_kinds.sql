-- Blog comments — add the component/table/row/cell anchor_kinds. Portable. Additive to 015-018.
--
-- Broadens what a comment can anchor to beyond prose + DecisionTable rows + diagram nodes/edges:
-- now ANY table + its rows and cells, any rich component box (a Callout, a ComparisonMatrix, the
-- "Questions this post answers" aside), and list items inside them. A build-time rehype stamper
-- (integrations/rehype-block-ids.mjs) gives each an eb-<hash> content-hash id + a data-anchor-kind
-- attribute; the client allowlist (src/data/comments.ts) reads that kind; the check-anchor-ids
-- build hook fails if any such element lacks its id. See docs/comments-design.md.
--
-- Portable additive DDL (widen a CHECK). Safe on a live table: adding accepted values never
-- rejects an existing row; blog_comments is empty at apply time. No grant change (anchor_kind is
-- already in the INSERT grant).

do $$
begin
  alter table public.blog_comments drop constraint if exists blog_comments_anchor_kind_check;
  alter table public.blog_comments add constraint blog_comments_anchor_kind_check
    check (anchor_kind in (
      'heading', 'decision', 'diagram', 'node', 'entity', 'prose', 'range', 'edge',
      'component', 'table', 'row', 'cell'
    ));
end $$;
