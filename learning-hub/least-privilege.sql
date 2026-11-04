-- Least-privilege correction: RLS does not protect TRUNCATE, TRIGGER or REFERENCES grants.
revoke all on table public.hub_resources, public.hub_download_requests, public.hub_favorites, public.hub_page_notes from public, anon, authenticated;
grant insert,update,delete on public.hub_resources to authenticated;
grant select(id,space,kind,category,title,summary,body,subject,grade,tags,external_url,file_path,file_name,file_mime,file_size,visibility,status,author_id,author_name,guest_protected,created_at,updated_at) on public.hub_resources to authenticated;
grant select,insert,update,delete on public.hub_download_requests to authenticated;
grant select,insert,update,delete on public.hub_favorites to authenticated;
grant select,insert,update,delete on public.hub_page_notes to authenticated;