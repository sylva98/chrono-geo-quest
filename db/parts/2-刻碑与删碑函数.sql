-- 第 2 步 / 共 3 步：刻碑、删碑函数（会清掉旧签名）
-- 全选复制 → Run

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
