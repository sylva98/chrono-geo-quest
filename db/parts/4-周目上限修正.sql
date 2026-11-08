-- 第 4 步 / 共 4 步：修正周目上限
-- 旧约束把 cycle 限制成 0 和 1，导致第三周目（无我篇）刻不了碑
-- 全选复制 → SQL Editor 清空粘贴 → Run

do $ck$
declare r record;
begin
  for r in
    select conname
      from pg_constraint
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

-- 顺手清掉我联调时留下的测试碑（昵称就这几个，你自己的碑不会碰到）
delete from public.stela
 where nick in ('转世员', '联调员', '测试碑');
