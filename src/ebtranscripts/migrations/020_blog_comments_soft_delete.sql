-- Blog comments — author SOFT-DELETE. Portable. Additive to 015-019.
--
-- 015 deliberately shipped NO client DELETE ("comments are not hard-deleted from the client … a
-- future soft-delete flag handles removal"). This is that flag: an author can mark their OWN
-- comment deleted; the row STAYS in the table (thread history intact, replies never orphaned) and
-- the client renders it as a tombstone / hides its body. No hard DELETE, no cascade.
--
-- Portable additive DDL (add a column with a default). Safe on a live table: existing rows get
-- deleted=false; blog_comments is empty at apply time anyway. The prod-only grant that lets an
-- author flip this column lives in 020_blog_comments_soft_delete_prod.sql (RLS/role-scoped).

alter table public.blog_comments
  add column if not exists deleted boolean not null default false;
