-- Learning Hub v1: isolated tables/policies, no changes to existing applications.
create schema if not exists hub_private;
revoke all on schema hub_private from public, anon;
grant usage on schema hub_private to authenticated;

create or replace function hub_private.is_admin()
returns boolean language sql stable security definer
set search_path = '' as $$
  select exists (
    select 1 from auth.users u
    join auth.identities i on i.user_id = u.id
    where u.id = (select auth.uid())
      and lower(u.email) = 'gim6110@gmail.com'
      and u.email_confirmed_at is not null
      and i.provider = 'google'
  );
$$;
revoke all on function hub_private.is_admin() from public, anon;
grant execute on function hub_private.is_admin() to authenticated;

create or replace function public.hub_am_i_admin()
returns boolean language sql stable security invoker
set search_path = '' as $$
  select hub_private.is_admin();
$$;
revoke all on function public.hub_am_i_admin() from public, anon;
grant execute on function public.hub_am_i_admin() to authenticated;

create table if not exists public.hub_resources (
  id uuid primary key default gen_random_uuid(),
  space text not null check(space in ('school','personal')),
  kind text not null check(kind in ('document','simulator','link','video','note')),
  category text not null default '기타' check(char_length(category) between 1 and 50),
  title text not null check(char_length(title) between 1 and 160),
  summary text not null default '' check(char_length(summary) <= 1500),
  body text not null default '' check(char_length(body) <= 50000),
  subject text not null default '' check(char_length(subject) <= 80),
  grade text not null default '' check(char_length(grade) <= 40),
  tags text[] not null default '{}',
  external_url text,
  file_path text,
  file_name text,
  file_mime text,
  file_size bigint check(file_size is null or file_size between 0 and 52428800),
  visibility text not null default 'public' check(visibility in ('public','private')),
  status text not null default 'published' check(status in ('published','hidden')),
  author_id uuid not null references auth.users(id) on delete cascade,
  author_name text not null default '방문자' check(char_length(author_name) between 1 and 80),
  guest_password_hash text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint hub_resource_url check (
    external_url is null or external_url ~* '^https?://[^[:space:]]+$'
  ),
  constraint hub_resource_file_path check (
    file_path is null or file_path like author_id::text || '/' || id::text || '/%'
  )
);
create index if not exists hub_resources_browse_idx on public.hub_resources(space, created_at desc);
create index if not exists hub_resources_author_idx on public.hub_resources(author_id);
create index if not exists hub_resources_tags_idx on public.hub_resources using gin(tags);

create or replace function hub_private.touch_resource()
returns trigger language plpgsql set search_path = '' as $$
begin
  if new.id is distinct from old.id or new.author_id is distinct from old.author_id
     or new.created_at is distinct from old.created_at
     or new.guest_password_hash is distinct from old.guest_password_hash then
    raise exception 'Protected fields cannot be changed';
  end if;
  new.updated_at := now();
  return new;
end
$$;
drop trigger if exists hub_touch_resource on public.hub_resources;
create trigger hub_touch_resource before update on public.hub_resources
for each row execute function hub_private.touch_resource();

create table if not exists public.hub_download_requests (
  id uuid primary key default gen_random_uuid(),
  resource_id uuid not null references public.hub_resources(id) on delete cascade,
  requester_id uuid not null references auth.users(id) on delete cascade,
  status text not null default 'pending' check(status in ('pending','approved','rejected')),
  created_at timestamptz not null default now(),
  decided_at timestamptz,
  unique(resource_id,requester_id)
);
create index if not exists hub_requests_pending_idx on public.hub_download_requests(status,created_at);

create table if not exists public.hub_favorites (
  user_id uuid not null references auth.users(id) on delete cascade,
  resource_id uuid not null references public.hub_resources(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id,resource_id)
);
create table if not exists public.hub_page_notes (
  user_id uuid not null references auth.users(id) on delete cascade,
  resource_id uuid not null references public.hub_resources(id) on delete cascade,
  page_number integer not null check (page_number between 1 and 10000),
  note text not null default '' check(char_length(note)<=5000),
  bookmarked boolean not null default false,
  updated_at timestamptz not null default now(),
  primary key(user_id,resource_id,page_number)
);
create table if not exists hub_private.guest_attempts (
  resource_id uuid not null references public.hub_resources(id) on delete cascade,
  actor_id uuid not null,
  attempts integer not null default 0,
  window_start timestamptz not null default now(),
  primary key(resource_id,actor_id)
);

alter table public.hub_resources enable row level security;
alter table public.hub_download_requests enable row level security;
alter table public.hub_favorites enable row level security;
alter table public.hub_page_notes enable row level security;

create policy hub_resource_read on public.hub_resources for select to authenticated
using (
  (status = 'published' and visibility = 'public')
  or author_id = (select auth.uid())
  or (select hub_private.is_admin())
);
create policy hub_resource_add_google on public.hub_resources for insert to authenticated
with check (
  author_id = (select auth.uid())
  and coalesce((auth.jwt()->>'is_anonymous')::boolean,false) = false
  and guest_password_hash is null
  and status = 'published'
);
create policy hub_resource_edit_google on public.hub_resources for update to authenticated
using (
  (author_id = (select auth.uid()) and guest_password_hash is null
   and coalesce((auth.jwt()->>'is_anonymous')::boolean,false) = false)
  or (select hub_private.is_admin())
)
with check (
  (author_id = (select auth.uid()) and guest_password_hash is null
   and coalesce((auth.jwt()->>'is_anonymous')::boolean,false) = false)
  or (select hub_private.is_admin())
);
create policy hub_resource_delete_google on public.hub_resources for delete to authenticated
using (
  (author_id = (select auth.uid()) and guest_password_hash is null
   and coalesce((auth.jwt()->>'is_anonymous')::boolean,false) = false)
  or (select hub_private.is_admin())
);

create policy hub_request_read on public.hub_download_requests for select to authenticated
using (requester_id=(select auth.uid()) or (select hub_private.is_admin()));
create policy hub_request_create on public.hub_download_requests for insert to authenticated
with check (
  requester_id=(select auth.uid()) and status='pending' and decided_at is null
  and exists(select 1 from public.hub_resources r where r.id=resource_id)
);
create policy hub_request_admin_update on public.hub_download_requests for update to authenticated
using ((select hub_private.is_admin()))
with check ((select hub_private.is_admin()));
create policy hub_request_admin_delete on public.hub_download_requests for delete to authenticated
using ((select hub_private.is_admin()));

create policy hub_favorite_self on public.hub_favorites for all to authenticated
using (user_id=(select auth.uid()))
with check (user_id=(select auth.uid()));
create policy hub_note_self on public.hub_page_notes for all to authenticated
using (user_id=(select auth.uid()))
with check (user_id=(select auth.uid()));

-- Return false and commit the failed-attempt counter, rather than raising a
-- transaction-rollback exception when a password is incorrect.
create or replace function hub_private.verify_guest_password(p_id uuid,p_password text)
returns boolean language plpgsql volatile security definer
set search_path = '' as $$
declare
  v_hash text;
  v_attempts integer;
  v_window timestamptz;
  v_uid uuid := auth.uid();
begin
  if v_uid is null then return false; end if;
  select guest_password_hash into v_hash from public.hub_resources
    where id=p_id for update;
  if v_hash is null then return false; end if;
  select attempts,window_start into v_attempts,v_window
    from hub_private.guest_attempts
    where resource_id=p_id and actor_id=v_uid for update;
  if v_window > now()-interval '15 minutes' and v_attempts >= 5 then
    return false;
  end if;
  if extensions.crypt(coalesce(p_password,''),v_hash)=v_hash then
    delete from hub_private.guest_attempts
      where resource_id=p_id and actor_id=v_uid;
    return true;
  end if;
  insert into hub_private.guest_attempts(resource_id,actor_id,attempts,window_start)
    values(p_id,v_uid,1,now())
    on conflict(resource_id,actor_id) do update
    set attempts=case
      when hub_private.guest_attempts.window_start < now()-interval '15 minutes'
        then 1 else hub_private.guest_attempts.attempts+1 end,
        window_start=case
      when hub_private.guest_attempts.window_start < now()-interval '15 minutes'
        then now() else hub_private.guest_attempts.window_start end;
  return false;
end
$$;

create or replace function public.hub_guest_create(
  p_space text, p_kind text, p_category text, p_title text,
  p_summary text, p_body text, p_subject text, p_grade text,
  p_tags text[], p_external_url text, p_visibility text,
  p_author_name text, p_password text
) returns uuid language plpgsql security definer
set search_path = '' as $$
declare v_id uuid;
begin
  if auth.uid() is null or
     coalesce((auth.jwt()->>'is_anonymous')::boolean,false) is not true
     then raise exception 'Guest session is required'; end if;
  if char_length(coalesce(p_password,'')) < 8 or char_length(p_password)>100
     then raise exception 'Password must be between 8 and 100 characters'; end if;
  if (select count(*) from public.hub_resources
       where author_id=auth.uid() and created_at > now()-interval '1 hour')>=10
     then raise exception 'Guest posting limit reached'; end if;
  insert into public.hub_resources
    (space,kind,category,title,summary,body,subject,grade,tags,
     external_url,visibility,author_id,author_name,guest_password_hash)
  values(p_space,p_kind,p_category,p_title,coalesce(p_summary,''),
    coalesce(p_body,''),coalesce(p_subject,''),coalesce(p_grade,''),
    coalesce(p_tags,'{}'),nullif(p_external_url,''),p_visibility,auth.uid(),
    coalesce(nullif(p_author_name,''),'게스트'),
    extensions.crypt(p_password,extensions.gen_salt('bf',10)))
  returning id into v_id;
  return v_id;
end
$$;

create or replace function public.hub_guest_edit(
  p_id uuid, p_password text, p_space text, p_kind text,
  p_category text, p_title text, p_summary text, p_body text,
  p_subject text, p_grade text, p_tags text[],
  p_external_url text, p_visibility text, p_author_name text,
  p_file_path text default null, p_file_name text default null,
  p_file_mime text default null, p_file_size bigint default null
) returns jsonb language plpgsql security definer
set search_path = '' as $$
begin
  if auth.uid() is null then return '{"ok":false,"error":"로그인이 필요합니다."}'::jsonb; end if;
  if not hub_private.verify_guest_password(p_id,p_password) then
    return '{"ok":false,"error":"비밀번호가 다르거나 잠시 잠금 상태입니다."}'::jsonb;
  end if;
  update public.hub_resources set
    space=p_space,kind=p_kind,category=p_category,title=p_title,
    summary=coalesce(p_summary,''),body=coalesce(p_body,''),
    subject=coalesce(p_subject,''),grade=coalesce(p_grade,''),
    tags=coalesce(p_tags,'{}'),external_url=nullif(p_external_url,''),
    visibility=p_visibility,
    author_name=coalesce(nullif(p_author_name,''),'게스트'),
    file_path=coalesce(p_file_path,file_path),
    file_name=coalesce(p_file_name,file_name),
    file_mime=coalesce(p_file_mime,file_mime),
    file_size=coalesce(p_file_size,file_size)
  where id=p_id and guest_password_hash is not null;
  return '{"ok":true}'::jsonb;
end
$$;
create or replace function public.hub_guest_delete(p_id uuid,p_password text)
returns jsonb language plpgsql security definer
set search_path = '' as $$
begin
  if auth.uid() is null then return '{"ok":false,"error":"로그인이 필요합니다."}'::jsonb; end if;
  if not hub_private.verify_guest_password(p_id,p_password) then
    return '{"ok":false,"error":"비밀번호가 다르거나 잠시 잠금 상태입니다."}'::jsonb;
  end if;
  delete from public.hub_resources where id=p_id and guest_password_hash is not null;
  return '{"ok":true}'::jsonb;
end
$$;

revoke all on function public.hub_guest_create(text,text,text,text,text,text,text,text,text[],text,text,text,text) from public,anon;
revoke all on function public.hub_guest_edit(uuid,text,text,text,text,text,text,text,text,text,text[],text,text,text,text,text,text,bigint) from public,anon;
revoke all on function public.hub_guest_delete(uuid,text) from public,anon;
grant execute on function public.hub_guest_create(text,text,text,text,text,text,text,text,text[],text,text,text,text,text) to authenticated;
grant execute on function public.hub_guest_edit(uuid,text,text,text,text,text,text,text,text,text,text[],text,text,text,text,text,text,text,bigint) to authenticated;
grant execute on function public.hub_guest_delete(uuid,text) to authenticated;

insert into storage.buckets(id,name,public,file_size_limit)
values('hub-private-files','hub-private-files',false,52428800)
on conflict(id) do nothing;
create policy hub_storage_read on storage.objects for select to authenticated
using (
 bucket_id='hub-private-files' and
 (
   (storage.foldername(name))[1]=(select auth.uid())::text
   or (select hub_private.is_admin())
   or exists(
     select 1 from public.hub_resources r
     where r.file_path=storage.objects.name
       and r.status='published' and r.visibility='public'
   )
 )
);
create policy hub_storage_upload on storage.objects for insert to authenticated
with check (
 bucket_id='hub-private-files'
 and (storage.foldername(name))[1]=(select auth.uid())::text
 and exists(
   select 1 from public.hub_resources r
   where r.id::text=(storage.foldername(name))[2]
     and r.author_id=(select auth.uid())
 )
);
create policy hub_storage_remove on storage.objects for delete to authenticated
using (
 bucket_id='hub-private-files'
 and ((storage.foldername(name))[1]=(select auth.uid())::text
      or (select hub_private.is_admin()))
);

grant select,insert,update,delete on public.hub_resources to authenticated;
grant select,insert,update,delete on public.hub_download_requests to authenticated;
grant select,insert,update,delete on public.hub_favorites to authenticated;
grant select,insert,update,delete on public.hub_page_notes to authenticated;
