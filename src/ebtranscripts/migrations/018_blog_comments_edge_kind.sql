-- Blog comments — add the 'edge' anchor_kind. Portable. Additive to 015/016/017.
--
-- Lets a comment anchor to a DIAGRAM EDGE (an arrow in a FlowDiagram), alongside 'node'. The
-- diagram engine now stamps every edge with a stable data-edge id (from__to, NOT the label), so
-- an edge is a fixed, fragment-anchored target — re-attach is a querySelector by data-edge, no
-- range/fuzzy machinery. Adding or renaming a label never changes the id, so a comment on an
-- arrow survives text being added to it later (the durability property the design calls for).
--
-- Portable additive DDL (widen a CHECK). Safe on a live table: adding an accepted value never
-- rejects an existing row; blog_comments is empty at apply time. No grant change (anchor_kind is
-- already in the INSERT grant).

do $$
begin
  alter table public.blog_comments drop constraint if exists blog_comments_anchor_kind_check;
  alter table public.blog_comments add constraint blog_comments_anchor_kind_check
    check (anchor_kind in ('heading', 'decision', 'diagram', 'node', 'entity', 'prose', 'range', 'edge'));
end $$;
