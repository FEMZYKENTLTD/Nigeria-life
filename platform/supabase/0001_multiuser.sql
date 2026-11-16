-- ============================================================================
-- Nigeria Life Intelligence Engine — multi-user migration (idempotent)
--
-- Run in Supabase SQL editor (or via the Supabase API) AFTER the engine has
-- booted once against this database (it creates its own tables). The engine
-- connects with the postgres role, which bypasses RLS — RLS here protects
-- the *direct* Supabase surface (anon key / PostgREST): a user's own client
-- can read only their own projects, and direct writes are admin-only.
-- ============================================================================

-- 1. Profiles (the engine also auto-creates this; keep in sync) -------------
create table if not exists public.profiles (
  id text primary key,
  email text unique,
  display_name text not null default '',
  role text not null default 'member',
  created_at timestamptz not null default now(),
  last_seen_at timestamptz
);

-- 2. Project ownership -------------------------------------------------------
alter table public.projects add column if not exists owner_id text;
create index if not exists ix_projects_owner_id on public.projects (owner_id);

-- 3. Access helpers (security definer: may read profiles even under RLS) ----
create or replace function public.is_admin() returns boolean
language sql stable security definer
as $$
  select exists (
    select 1 from public.profiles
    where id = auth.uid()::text and role = 'admin'
  );
$$;

create or replace function public.can_see_project(p text) returns boolean
language sql stable security definer
as $$
  select exists (
    select 1 from public.projects
    where id = p and (owner_id = auth.uid()::text or public.is_admin())
  );
$$;

-- 4. RLS: profiles -----------------------------------------------------------
alter table public.profiles enable row level security;
drop policy if exists profiles_select on public.profiles;
create policy profiles_select on public.profiles for select
  using (id = auth.uid()::text or public.is_admin());
drop policy if exists profiles_insert on public.profiles;
create policy profiles_insert on public.profiles for insert
  with check (id = auth.uid()::text);
drop policy if exists profiles_update on public.profiles;
create policy profiles_update on public.profiles for update
  using (id = auth.uid()::text)
  with check (id = auth.uid()::text and role = 'member'); -- no self-promotion

-- 5. RLS: projects -----------------------------------------------------------
alter table public.projects enable row level security;
drop policy if exists projects_select on public.projects;
create policy projects_select on public.projects for select
  using (owner_id = auth.uid()::text or public.is_admin());
drop policy if exists projects_admin on public.projects;
create policy projects_admin on public.projects for all
  using (public.is_admin()) with check (public.is_admin());

-- 6. RLS: every project-scoped table (direct or via task/session) ------------
do $$
declare
  t text;
begin
  -- direct project_id
  foreach t in array array[
    'sources','unresolved_questions','research_tasks','decisions','page_records',
    'evidence','screenshots','observations','features','browser_profiles',
    'research_sessions','knowledge_entries','reports','github_state',
    'activity_logs','agent_runs','collection_scopes','api_connectors',
    'data_assets','fetch_cache'
  ] loop
    if to_regclass('public.' || t) is not null then
      execute format('alter table public.%I enable row level security', t);
      execute format('drop policy if exists %I_select on public.%I', t, t);
      execute format(
        'create policy %I_select on public.%I for select
         using (public.can_see_project(project_id))', t, t);
      execute format('drop policy if exists %I_admin on public.%I', t, t);
      execute format(
        'create policy %I_admin on public.%I for all
         using (public.is_admin()) with check (public.is_admin())', t, t);
    end if;
  end loop;

  -- via task → project
  if to_regclass('public.subtasks') is not null then
    alter table public.subtasks enable row level security;
    drop policy if exists subtasks_select on public.subtasks;
    create policy subtasks_select on public.subtasks for select
      using (exists (
        select 1 from public.research_tasks rt
        where rt.id = subtasks.task_id and public.can_see_project(rt.project_id)));
    drop policy if exists subtasks_admin on public.subtasks;
    create policy subtasks_admin on public.subtasks for all
      using (public.is_admin()) with check (public.is_admin());
  end if;

  -- via session (or task) → project
  if to_regclass('public.execution_logs') is not null then
    alter table public.execution_logs enable row level security;
    drop policy if exists execution_logs_select on public.execution_logs;
    create policy execution_logs_select on public.execution_logs for select
      using (
        (session_id <> '' and exists (
          select 1 from public.research_sessions rs
          where rs.id = execution_logs.session_id
            and public.can_see_project(rs.project_id)))
        or
        (task_id <> '' and exists (
          select 1 from public.research_tasks rt
          where rt.id = execution_logs.task_id
            and public.can_see_project(rt.project_id))));
    drop policy if exists execution_logs_admin on public.execution_logs;
    create policy execution_logs_admin on public.execution_logs for all
      using (public.is_admin()) with check (public.is_admin());
  end if;

  -- global read-only telemetry
  if to_regclass('public.browser_health') is not null then
    alter table public.browser_health enable row level security;
    drop policy if exists browser_health_select on public.browser_health;
    create policy browser_health_select on public.browser_health for select
      using (auth.uid() is not null);
  end if;
end $$;
