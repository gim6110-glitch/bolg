-- Prevent public API clients from reading guest password hashes.
revoke select on public.hub_resources from authenticated;
grant select (id,space,kind,category,title,summary,body,subject,grade,tags,external_url,file_path,file_name,file_mime,file_size,visibility,status,author_id,author_name,created_at,updated_at)
on public.hub_resources to authenticated;
-- Lock down private helper functions; no ability to call through REST (not in exposed schema).
revoke all on function hub_private.verify_guest_password(uuid,text) from public, anon, authenticated;
revoke all on function hub_private.touch_resource() from public, anon, authenticated;