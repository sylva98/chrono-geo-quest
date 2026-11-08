-- 第 1 步 / 共 3 步：星碑表加列与唯一键、转世表
-- 全选复制 → SQL Editor 清空粘贴 → Run

-- ---------- 1. 星碑表：加「世」与科目，重建唯一键 ----------
alter table public.stela add column if not exists generation integer not null default 1;
alter table public.stela add column if not exists subject text;
alter table public.stela add column if not exists updated_at timestamptz not null default now();

do $do$
declare r record;
begin
  for r in
    select conname from pg_constraint
    where conrelid = 'public.stela'::regclass and contype = 'u'
  loop
    execute format('alter table public.stela drop constraint %I', r.conname);
  end loop;
  for r in
    select indexname from pg_indexes
    where schemaname = 'public' and tablename = 'stela'
      and indexdef like '%UNIQUE%' and indexname not like '%_pkey'
  loop
    execute format('drop index if exists public.%I', r.indexname);
  end loop;
end
$do$;

alter table public.stela drop constraint if exists stela_unique_per_life;
alter table public.stela
  add constraint stela_unique_per_life unique (device, cycle, generation);

alter table public.stela enable row level security;

drop policy if exists stela_read on public.stela;
create policy stela_read on public.stela
  for select to anon, authenticated using (true);


-- ---------- 4. 转世冷却表 ----------
create table if not exists public.rebirth (
  device     text not null,
  subject    text not null,
  generation integer not null default 1,
  unlock_at  timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (device, subject)
);

alter table public.rebirth add column if not exists generation integer not null default 1;
alter table public.rebirth add column if not exists unlock_at timestamptz;

alter table public.rebirth enable row level security;
revoke all on table public.rebirth from anon, authenticated;
