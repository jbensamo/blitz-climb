-- Blitz Climb — progress storage.
-- Paste this whole file into the Supabase dashboard: SQL Editor -> New query -> Run.
-- Safe to re-run.

create table if not exists public.progress (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  data       jsonb       not null,
  updated_at timestamptz not null default now()
);

-- RLS is the ONLY thing standing between the public anon key (which ships in the
-- app's HTML, by design) and this data. It must stay enabled.
alter table public.progress enable row level security;

drop policy if exists "progress: own row" on public.progress;
create policy "progress: own row"
  on public.progress
  for all
  to authenticated
  using      (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Belt and braces: no anonymous access at all.
revoke all on public.progress from anon;
grant select, insert, update, delete on public.progress to authenticated;

-- Verify (expect rowsecurity = true):
--   select relname, relrowsecurity from pg_class where relname = 'progress';
