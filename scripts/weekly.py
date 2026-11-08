#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chrono-geo-quest 玩家周报生成器

数据来源：Supabase `stela`（星碑）表 —— 目前服务端唯一记录玩家身份的地方。
用法：python3 scripts/weekly.py
产出：reports/weekly-<日期>.html + reports/snapshots/<日期>.json
"""
import json, os, sys, urllib.request, datetime, collections, pathlib

SB = "https://kykpowxzhtkxjkcflfuq.supabase.co/rest/v1"
KEY = "sb_publishable_VtZvQFyVdWWhZGAVMUFagA_9oM9THXQ"
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "reports"
SNAP = OUT / "snapshots"

CYCLE_NAME = ["时空纪元", "修仙记", "无我篇"]
CYCLE_TOP = ["星光神域", "道祖", "无我境"]
CYCLE_KICK = ["神格觉醒", "飞升", "无我境"]
SUB_NAME = {"geo": "地理", "hist": "历史", "bio": "生物", "poem": "诗歌"}
SUB_ORDER = ["geo", "hist", "bio", "poem"]


def get(path):
    req = urllib.request.Request(SB + path, headers={
        "apikey": KEY, "Authorization": "Bearer " + KEY})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def fetch():
    rows = get("/stela?select=id,device,cycle,generation,nick,word,times,subject,updated_at"
               "&order=updated_at.desc&limit=500")
    return rows


def load_prev(today):
    if not SNAP.exists():
        return None
    files = sorted([p for p in SNAP.glob("*.json") if p.stem < today])
    if not files:
        return None
    return json.loads(files[-1].read_text())


def build(rows, prev, today):
    by_dev = collections.defaultdict(list)
    for r in rows:
        by_dev[r["device"]].append(r)

    players = []
    for dev, rs in by_dev.items():
        rs.sort(key=lambda x: (x.get("cycle") or 0))
        top = max(r.get("cycle") or 0 for r in rs)
        # 取该玩家最高周目那条碑的昵称（最新的名字）
        latest = max(rs, key=lambda x: x["updated_at"])
        subjects = sorted({r.get("subject") or "?" for r in rs})
        players.append({
            "device": dev,
            "nick": latest["nick"],
            "word": latest["word"],
            "cycle": top,
            "cycleName": CYCLE_NAME[top] if top < 3 else "?",
            "topEra": CYCLE_TOP[top] if top < 3 else "?",
            "kicker": CYCLE_KICK[top] if top < 3 else "?",
            "generation": max((r.get("generation") or 1) for r in rs),
            "steles": len(rs),
            "subjects": subjects,
            "times": max((r.get("times") or 1) for r in rs),
            "last": max(r["updated_at"] for r in rs),
        })

    players.sort(key=lambda p: (-p["cycle"], p["last"]), reverse=False)
    players.sort(key=lambda p: (-p["cycle"], p["last"]))

    # 科目视图
    sub_rows = []
    for sid in SUB_ORDER:
        ps = [p for p in players if sid in p["subjects"]]
        sub_rows.append({
            "id": sid, "name": SUB_NAME[sid], "players": ps,
            "count": len(ps),
            "maxCycle": max([p["cycle"] for p in ps], default=-1),
        })

    funnel = [sum(1 for p in players if p["cycle"] >= c) for c in (0, 1, 2)]

    # 与上期对比
    delta = {"new": [], "lost": [], "up": []}
    if prev:
        old = {p["device"]: p for p in prev.get("players", [])}
        new = {p["device"]: p for p in players}
        delta["new"] = [new[d] for d in new if d not in old]
        delta["lost"] = [old[d] for d in old if d not in new]
        delta["up"] = [new[d] for d in new if d in old and new[d]["cycle"] > old[d]["cycle"]]

    return {
        "date": today,
        "players": players,
        "subjects": [{"id": s["id"], "name": s["name"], "count": s["count"]} for s in sub_rows],
        "funnel": funnel,
        "delta": delta,
    }


def fmt_time(iso):
    try:
        dt = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone(datetime.timezone(datetime.timedelta(hours=8))).strftime("%m-%d %H:%M")
    except Exception:
        return iso[:16]


def render(d, prev_date):
    total = len(d["players"])
    funnel, delta = d["funnel"], d["delta"]

    def badge(cyc):
        cls = ["c0", "c1", "c2"][cyc] if cyc < 3 else "c0"
        return f'<span class="tag {cls}">{CYCLE_NAME[cyc]}</span>'

    rows = ""
    for p in d["players"]:
        subs = " ".join(f'<span class="sub">{SUB_NAME.get(s, s)}</span>' for s in p["subjects"])
        rows += f"""<tr>
          <td class="nick">{p['nick']}</td>
          <td>{badge(p['cycle'])}</td>
          <td class="era">{p['topEra']}<i>第 21 境</i></td>
          <td>{subs}</td>
          <td class="num">{p['steles']}</td>
          <td class="num">{p['generation']}</td>
          <td class="num">{p['times']}</td>
          <td class="time">{fmt_time(p['last'])}</td>
        </tr>"""

    sub_cards = ""
    for s in d["subjects"]:
        ps = [p for p in d["players"] if s["id"] in p["subjects"]]
        lis = "".join(
            f'<li><b>{p["nick"]}</b><span>{CYCLE_NAME[p["cycle"]]} · {p["topEra"]}</span></li>'
            for p in ps) or '<li class="none">暂无玩家抵达</li>'
        sub_cards += f"""<div class="card">
          <div class="card-h"><h3>{s['name']}</h3><em>{s['count']} 人</em></div>
          <ul>{lis}</ul>
        </div>"""

    fmax = max(funnel[0], 1)
    bars = ""
    for i, n in enumerate(funnel):
        w = round(n / fmax * 100) if n else 0
        bars += f"""<div class="bar-row">
            <span class="bar-lb">{CYCLE_NAME[i]}</span>
            <div class="bar"><i class="{['c0','c1','c2'][i]}" style="width:{w}%"></i></div>
            <b>{n}</b></div>"""

    dnew = "".join(f'<li><b>{p["nick"]}</b> 首次刻碑 · {CYCLE_NAME[p["cycle"]]}</li>' for p in delta["new"])
    dup = "".join(f'<li><b>{p["nick"]}</b> {CYCLE_NAME[p["cycle"]]} 通关</li>' for p in delta["up"])
    delta_html = ""
    if prev_date:
        delta_html = f"""<div class="delta">
          <div><h4>本期新增</h4><ul>{dnew or '<li class="none">无</li>'}</ul></div>
          <div><h4>本期进阶</h4><ul>{dup or '<li class="none">无</li>'}</ul></div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>玩家周报 · {d['date']}</title>
<style>
  :root{{--ink:#e8ecf5;--dim:#8b93a7;--gold:#ffd76a;--line:rgba(255,255,255,.08);--bg:#0a0c14;--card:#12151f}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:radial-gradient(120% 80% at 50% 0%,#1a1f31 0%,var(--bg) 55%);color:var(--ink);
    font:14px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;
    padding:38px 22px 60px;max-width:960px;margin:0 auto}}
  header{{margin-bottom:30px;border-bottom:1px solid var(--line);padding-bottom:20px}}
  .kick{{font-size:10px;letter-spacing:.32em;color:var(--gold);opacity:.75;text-transform:uppercase}}
  h1{{font-size:26px;font-weight:600;letter-spacing:.08em;margin:8px 0 6px}}
  .meta{{font-size:12px;color:var(--dim)}}
  h2{{font-size:13px;letter-spacing:.18em;color:var(--dim);margin:34px 0 14px;font-weight:500}}
  .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px}}
  .stat{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}}
  .stat b{{display:block;font-size:24px;font-weight:600;color:var(--gold);letter-spacing:.02em}}
  .stat span{{font-size:11px;color:var(--dim)}}
  table{{width:100%;border-collapse:collapse;font-size:13px;background:var(--card);
    border:1px solid var(--line);border-radius:12px;overflow:hidden}}
  th{{text-align:left;font-size:10.5px;letter-spacing:.1em;color:var(--dim);font-weight:500;
    padding:10px 12px;border-bottom:1px solid var(--line);background:rgba(255,255,255,.02)}}
  td{{padding:11px 12px;border-bottom:1px solid rgba(255,255,255,.04);vertical-align:middle}}
  tr:last-child td{{border-bottom:none}}
  .nick{{font-weight:600;letter-spacing:.02em}}
  .era{{color:var(--gold)}}
  .era i{{display:block;font-style:normal;font-size:10px;color:var(--dim);letter-spacing:.06em}}
  .num{{text-align:center;font-variant-numeric:tabular-nums;color:var(--dim)}}
  .time{{font-size:11.5px;color:var(--dim);white-space:nowrap}}
  .tag{{font-size:10.5px;padding:2.5px 8px;border-radius:999px;border:1px solid;white-space:nowrap}}
  .tag.c0{{color:#ffe1a0;border-color:rgba(255,215,106,.4);background:rgba(255,215,106,.08)}}
  .tag.c1{{color:#a8ecff;border-color:rgba(127,227,255,.4);background:rgba(127,227,255,.08)}}
  .tag.c2{{color:#eef4fa;border-color:rgba(205,228,250,.4);background:rgba(205,228,250,.08)}}
  .sub{{font-size:10.5px;color:var(--dim);border:1px solid var(--line);padding:1.5px 6px;border-radius:5px}}
  .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}}
  .card-h{{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:10px}}
  .card-h h3{{font-size:14px;font-weight:600;letter-spacing:.08em}}
  .card-h em{{font-style:normal;font-size:11px;color:var(--gold)}}
  .card ul{{list-style:none;font-size:12px}}
  .card li{{display:flex;justify-content:space-between;gap:8px;padding:4px 0;border-bottom:1px dashed rgba(255,255,255,.05)}}
  .card li:last-child{{border:none}}
  .card li span{{color:var(--dim);font-size:11px}}
  .card li.none{{color:var(--dim);font-size:11.5px;justify-content:center}}
  .bar-row{{display:flex;align-items:center;gap:12px;margin-bottom:9px;font-size:12px}}
  .bar-lb{{width:64px;color:var(--dim);flex:none}}
  .bar{{flex:1;height:6px;border-radius:99px;background:rgba(255,255,255,.06);overflow:hidden}}
  .bar i{{display:block;height:100%;border-radius:99px}}
  .bar i.c0{{background:linear-gradient(90deg,#ffd76a,#ffe9b0)}}
  .bar i.c1{{background:linear-gradient(90deg,#7fe3ff,#bff3ff)}}
  .bar i.c2{{background:linear-gradient(90deg,#cdd9ea,#fff)}}
  .bar-row b{{width:22px;text-align:right;font-variant-numeric:tabular-nums}}
  .delta{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
  .delta>div{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}}
  .delta h4{{font-size:11px;letter-spacing:.14em;color:var(--dim);font-weight:500;margin-bottom:9px}}
  .delta ul{{list-style:none;font-size:12.5px}}
  .delta li{{padding:3px 0}}
  .delta li.none{{color:var(--dim)}}
  .note{{margin-top:34px;padding:16px 18px;border-radius:12px;background:rgba(255,215,106,.05);
    border:1px solid rgba(255,215,106,.18);font-size:12px;line-height:1.85;color:#c9c2a8}}
  .note b{{color:var(--gold)}}
  .empty{{padding:28px;text-align:center;color:var(--dim);font-size:12px}}
  @media(max-width:640px){{.delta{{grid-template-columns:1fr}}table{{font-size:12px}}th,td{{padding:9px 8px}}}}
</style></head><body>
<header>
  <div class="kick">CHRONO · GEO · QUEST</div>
  <h1>玩家周报</h1>
  <div class="meta">{d['date']} · 数据源：星碑表 stela · 统计口径：已刻碑玩家</div>
</header>

<h2>总览</h2>
<div class="stats">
  <div class="stat"><b>{total}</b><span>刻碑玩家</span></div>
  <div class="stat"><b>{funnel[0]}</b><span>通关时空纪元</span></div>
  <div class="stat"><b>{funnel[1]}</b><span>通关修仙记</span></div>
  <div class="stat"><b>{funnel[2]}</b><span>通关无我篇</span></div>
</div>

<h2>玩家一览</h2>
{('<table><thead><tr><th>玩家</th><th>最高周目</th><th>最高境界</th><th>科目</th>'
  '<th class="num">碑</th><th class="num">世</th><th class="num">抵达</th><th>最后活跃</th></tr></thead>'
  '<tbody>' + rows + '</tbody></table>') if rows else '<div class="empty">暂无玩家刻碑</div>'}

<h2>各科目分布</h2>
<div class="cards">{sub_cards}</div>

<h2>周目漏斗</h2>
{bars}

{'<h2>与上期对比</h2>' + delta_html if prev_date else ''}

<div class="note">
  <b>口径说明</b><br>
  1. 本表只统计<b>刻过星碑</b>的玩家——玩家昵称只在刻碑那一刻上传，未刻碑的玩家在服务端没有身份。<br>
  2. 玩家当前所在的<b>具体境界（第几境）</b>存在各自手机的本地存储里，服务端没有上报，因此“最高境界”一列表示其<b>已通关的最高周目</b>（第 21 境封顶）。<br>
  3. 如需精确到“每个人当前第几境、卡在哪一境”，需要在服务端新增一张进度表并由前端定期上报。
</div>
</body></html>"""


def main():
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")
    OUT.mkdir(exist_ok=True); SNAP.mkdir(exist_ok=True)
    rows = fetch()
    prev = load_prev(today)
    d = build(rows, prev, today)
    d["prevDate"] = prev["date"] if prev else None
    html = render(d, d["prevDate"])
    p = OUT / f"weekly-{today}.html"
    p.write_text(html, encoding="utf-8")
    (SNAP / f"{today}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"file": str(p), "players": len(d["players"]),
                      "funnel": d["funnel"],
                      "subjects": d["subjects"],
                      "prev": d["prevDate"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
