-- 第 3 步 / 共 3 步：上锁 / 查冷却 / 转世领新世
-- 全选复制 → Run

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
