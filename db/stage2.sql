-- ============================================================
-- 星碑 · 第二阶段（周目 / 世代 / 转世冷却）
-- 建议按 db/parts/ 里的 1~5 分段执行；本文件是一次性全量版
-- 定界符：$fn$ $del$ $do$ $dp$ $rl$ $rs$ $rc$
-- ============================================================

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


-- ---------- 2. 刻碑 / 改碑（清掉旧签名，只留 7 参新版） ----------
do $dp$
declare r record;
begin
  for r in
    select p.oid::regprocedure as sig
      from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public' and p.proname = 'stela_post'
       and p.pronargs <> 7
  loop
    execute format('drop function if exists %s', r.sig);
  end loop;
  for r in
    select p.oid::regprocedure as sig
      from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public' and p.proname = 'stela_del'
       and p.pronargs = 2 and p.proargtypes[0] <> 'text'::regtype
  loop
    execute format('drop function if exists %s', r.sig);
  end loop;
end
$dp$;

create or replace function public.stela_post(
  p_device     text,
  p_cycle      integer,
  p_nick       text,
  p_word       text,
  p_times      integer default 1,
  p_subject    text default null,
  p_generation integer default 1
) returns jsonb
language plpgsql
security definer
set search_path = public
as $fn$
declare
  v_nick text;
  v_word text;
  v_json jsonb;
begin
  v_nick := btrim(coalesce(p_nick, ''));
  v_word := btrim(coalesce(p_word, ''));
  if p_device is null or char_length(btrim(p_device)) < 6 then
    raise exception 'BAD_DEVICE' using errcode = '22023';
  end if;
  if p_cycle is null or p_cycle < 0 or p_cycle > 2 then
    raise exception 'BAD_CYCLE' using errcode = '22023';
  end if;
  if char_length(v_nick) < 2 or char_length(v_nick) > 8 then
    raise exception 'NICK_LEN' using errcode = '22023';
  end if;
  if char_length(v_word) < 1 or char_length(v_word) > 10 then
    raise exception 'WORD_LEN' using errcode = '22023';
  end if;
  if (v_nick || ' ' || v_word) ~* '(https?://|www\.|\.com|\.cn|微信|v信|vx|威信|加我|扫码|二维码|[0-9]{7,})' then
    raise exception 'BAD_CONTENT' using errcode = '22023';
  end if;
  if v_nick || v_word ~* '垃圾|废物|傻逼|傻b|智障|去死|滚开|妈的|操你|狗东西|贱货|婊|死全家|脑残|弱智|自杀|约炮|色情|赌博' then
    raise exception 'BAD_CONTENT' using errcode = '22023';
  end if;

  insert into public.stela as s
    (device, cycle, generation, nick, word, times, subject, updated_at)
  values
    (p_device, p_cycle, greatest(coalesce(p_generation, 1), 1), v_nick, v_word,
     greatest(coalesce(p_times, 1), 1), p_subject, now())
  on conflict (device, cycle, generation) do update
    set nick       = excluded.nick,
        word       = excluded.word,
        times      = greatest(s.times, excluded.times),
        subject    = coalesce(excluded.subject, s.subject),
        updated_at = now()
  returning to_jsonb(s.*) into v_json;

  return v_json;
end
$fn$;

revoke all on function public.stela_post(text, integer, text, text, integer, text, integer) from public;
grant execute on function public.stela_post(text, integer, text, text, integer, text, integer) to anon, authenticated;


-- ---------- 3. 删碑（只能删自己设备的） ----------
create or replace function public.stela_del(p_id text, p_device text)
returns jsonb
language plpgsql
security definer
set search_path = public
as $del$
declare
  n integer;
begin
  delete from public.stela where id::text = btrim(p_id) and device = p_device;
  get diagnostics n = row_count;
  return jsonb_build_object('deleted', n);
end
$del$;

revoke all on function public.stela_del(text, text) from public;
grant execute on function public.stela_del(text, text) to anon, authenticated;


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


-- ---------- 5. 上锁 / 查冷却 / 转世领新世 ----------
create or replace function public.rebirth_lock(p_device text, p_subject text, p_days integer default 5)
returns jsonb
language plpgsql
security definer
set search_path = public
as $rl$
declare
  v_at timestamptz;
begin
  if p_device is null or p_subject is null then
    raise exception 'BAD_ARGS' using errcode = '22023';
  end if;
  insert into public.rebirth as r (device, subject, generation, unlock_at, updated_at)
  values (p_device, p_subject, 1, now() + make_interval(days => greatest(coalesce(p_days, 5), 1)), now())
  on conflict (device, subject) do update
    set unlock_at  = now() + make_interval(days => greatest(coalesce(p_days, 5), 1)),
        updated_at = now()
  returning r.unlock_at into v_at;

  return jsonb_build_object('unlock_at', v_at, 'server_now', now());
end
$rl$;

create or replace function public.rebirth_state(p_device text, p_subject text)
returns jsonb
language plpgsql
security definer
set search_path = public
as $rs$
declare
  v_gen integer;
  v_at  timestamptz;
begin
  select generation, unlock_at into v_gen, v_at
    from public.rebirth
   where device = p_device and subject = p_subject;
  if not found then
    return jsonb_build_object('generation', 0, 'unlock_at', null, 'server_now', now());
  end if;
  return jsonb_build_object('generation', v_gen, 'unlock_at', v_at, 'server_now', now());
end
$rs$;

create or replace function public.rebirth_claim(p_device text, p_subject text)
returns jsonb
language plpgsql
security definer
set search_path = public
as $rc$
declare
  v_gen integer;
  v_at  timestamptz;
begin
  select generation, unlock_at into v_gen, v_at
    from public.rebirth
   where device = p_device and subject = p_subject
   for update;
  if not found then
    return jsonb_build_object('generation', 0, 'error', 'NOT_LOCKED');
  end if;
  if v_at is null or v_at > now() then
    return jsonb_build_object('generation', 0, 'error', 'COOLING',
                              'unlock_at', v_at, 'server_now', now());
  end if;
  v_gen := v_gen + 1;
  update public.rebirth
     set generation = v_gen, unlock_at = null, updated_at = now()
   where device = p_device and subject = p_subject;
  return jsonb_build_object('generation', v_gen, 'server_now', now());
end
$rc$;

revoke all on function public.rebirth_lock(text, text, integer) from public;
revoke all on function public.rebirth_state(text, text) from public;
revoke all on function public.rebirth_claim(text, text) from public;
grant execute on function public.rebirth_lock(text, text, integer) to anon, authenticated;
grant execute on function public.rebirth_state(text, text) to anon, authenticated;
grant execute on function public.rebirth_claim(text, text) to anon, authenticated;


-- ---------- 6. 周目上限修正（旧约束只允许 cycle 0/1） ----------
do $ck$
declare r record;
begin
  for r in
    select conname from pg_constraint
     where conrelid = 'public.stela'::regclass
       and contype = 'c'
       and pg_get_constraintdef(oid) ilike '%cycle%'
  loop
    execute format('alter table public.stela drop constraint %I', r.conname);
  end loop;
end
$ck$;

alter table public.stela
  add constraint stela_cycle_chk check (cycle between 0 and 2);
