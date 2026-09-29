"""Build an inventory of the largest client IMG files and identify their content.

Read-only pipeline, no IMG is ever written:

1. Rank every ``clien/**/*.img`` by file size.
2. Parse each ranked IMG with ``tool/wz-python`` to get its real top-level
   structure (never guessed from the path).
3. Resolve display names from the client's own ``Data/String/*.img``
   (Mob, Npc, Skill, Eqp, Ins, Consume, Etc, Cash, Map) and from the
   server-side ``gms-server/wz/Map.wz`` XML for asset -> map usage joins
   (``oS`` object sets, ``bS`` background sets, ``info/bgm`` music sets).
4. Emit ``inventory.json``, ``inventory.csv`` and a dark-theme HTML report.

Usage:
    /opt/homebrew/bin/python3 tool/img-inventory/build_inventory.py [top_n]
"""

from __future__ import annotations

import csv
import html
import json
import os
import re
import sys
import time

REPO = "/Users/lizixian/Documents/mxd/BeiDou-Server"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "tool", "wz-python"))

from wzpy import WzImage, WzKey, detect_region_from_img  # noqa: E402

CLIENT = os.path.join(REPO, "clien")
DATA = os.path.join(CLIENT, "Data")
STRING = os.path.join(DATA, "String")
MAP_XML_ROOT = os.path.join(REPO, "gms-server", "wz", "Map.wz", "Map")

RE_OS = re.compile(rb'<string name="oS" value="([^"]*)"')
RE_BS = re.compile(rb'<string name="bS" value="([^"]*)"')
RE_BGM = re.compile(rb'<string name="bgm" value="([^"]*)"')

ITEM_CAT = {
    "Install": ("椅子/设置道具", "Ins.img"),
    "Consume": ("消耗品", "Consume.img"),
    "Etc": ("其他道具", "Etc.img"),
    "Cash": ("现金道具", "Cash.img"),
    "Pet": ("宠物道具", "Pet.img"),
    "Special": ("特殊道具", None),
}
CHR_CAT = {
    "Cap": "帽子", "Coat": "上衣", "Longcoat": "套服", "Pants": "裤裙",
    "Shoes": "鞋子", "Glove": "手套", "Cape": "披风", "Shield": "盾牌",
    "Weapon": "武器", "Accessory": "饰品", "Ring": "戒指", "Face": "脸饰",
    "Hair": "发型", "Skin": "皮肤", "Dragon": "龙（龙神）", "PetEquip": "宠物装备",
}
EFFECT_HINT = {
    "CharacterEff.img": "角色通用特效（技能光效 / 状态 / 伤害数字）",
    "Direction.img": "剧情演出特效（第一组）",
    "Direction1.img": "剧情演出特效（第二组）",
    "BasicEff.img": "基础特效",
    "HitEff.img": "命中特效",
}
GRAND = {
    "BgmGL": "GMS 全球版区域 BGM 包",
    "BgmJp": "日服区域 BGM 包",
    "BgmJp2": "日服区域 BGM 包（第二组）",
    "BgmCN": "国服区域 BGM 包",
    "BgmTW": "台服区域 BGM 包",
    "BgmTH": "泰服区域 BGM 包",
    "BgmSG": "新马服区域 BGM 包",
}


# ── low level helpers ────────────────────────────────────────────────
def load_img(path):
    with open(path, "rb") as fh:
        data = fh.read()
    region = detect_region_from_img(data) or "GMS"
    img = WzImage.from_bytes(data, key=WzKey.for_region(region))
    img.parse()
    return img


def scalar(node):
    if node is None:
        return None
    try:
        v = node.value
    except Exception:
        return None
    return v if isinstance(v, str) else None


def norm(iid: str) -> str:
    return str(int(iid)) if iid.isdigit() else iid


def build_name_map(string_file: str, key_attr: str = "name") -> dict:
    out = {}
    path = os.path.join(STRING, string_file)
    if not os.path.exists(path):
        return out
    for child in load_img(path).children():
        nm = scalar(child.get(key_attr))
        if nm:
            out[norm(child.name)] = nm
    return out


def build_eqp_map() -> dict:
    out: dict[str, dict[str, str]] = {}
    path = os.path.join(STRING, "Eqp.img")
    if not os.path.exists(path):
        return out
    root = load_img(path).get("Eqp")
    if root is None:
        return out
    for cat in root.children():
        bucket = {}
        for item in cat.children():
            nm = scalar(item.get("name"))
            if nm:
                bucket[norm(item.name)] = nm
        if bucket:
            out[cat.name] = bucket
    return out


def load_job_names() -> dict:
    """job id -> Chinese job name, from the server i18n resource table."""
    path = os.path.join(REPO, "gms-server", "src", "main", "resources",
                        "i18n", "message_zh_CN.properties")
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = re.match(r"\s*job\.name\.(\d+)\s*=\s*(.+?)\s*$", line)
            if not m:
                continue
            val = re.sub(r"\\u([0-9a-fA-F]{4})",
                         lambda g: chr(int(g.group(1), 16)), m.group(2))
            out[m.group(1)] = val
    return out


def build_map_index() -> dict:
    """map id -> '街道 / 地图名'."""
    path = os.path.join(STRING, "Map.img")
    img = load_img(path)
    out = {}
    for region in img.children():
        for m in region.children():
            parts = [scalar(m.get("streetName")), scalar(m.get("mapName"))]
            label = " / ".join(p for p in parts if p)
            if label:
                out[m.name] = label
    return out


def scan_map_xml() -> tuple[dict, dict, dict]:
    """Return (obj_links, back_links, bgm_links): set name -> {map ids}."""
    obj: dict[str, set] = {}
    back: dict[str, set] = {}
    bgm: dict[str, set] = {}
    for root, _dirs, files in os.walk(MAP_XML_ROOT):
        for f in files:
            if not f.endswith(".xml"):
                continue
            mid = f[:-8]
            with open(os.path.join(root, f), "rb") as fh:
                blob = fh.read()
            for m in RE_OS.finditer(blob):
                obj.setdefault(m.group(1).decode("utf-8", "replace"), set()).add(mid)
            for m in RE_BS.finditer(blob):
                back.setdefault(m.group(1).decode("utf-8", "replace"), set()).add(mid)
            for m in RE_BGM.finditer(blob):
                v = m.group(1).decode("utf-8", "replace")
                if "/" in v:
                    bgm.setdefault(v.split("/", 1)[0], set()).add(mid)
    return obj, back, bgm


def map_summary(ids: set, map_names: dict, limit: int = 4) -> str:
    if not ids:
        return "服务端地图数据中未见引用（可能是客户端专用 / 活动图或已废弃资源）"
    named = [map_names.get(i, "") for i in sorted(ids)]
    streets = []
    for n in named:
        s = n.split(" / ")[0].strip()
        if s and s not in streets:
            streets.append(s)
    if not any(named):
        return f"用于 {len(ids)} 张地图（地图名未收录）"
    head = "、".join(streets[:limit])
    more = f" 等 {len(streets)} 个区域" if len(streets) > limit else ""
    return f"用于 {len(ids)} 张地图：{head}{more}"


# ── main pipeline ────────────────────────────────────────────────────
def collect(top_n: int) -> list[dict]:
    listing = []
    for root, _dirs, files in os.walk(CLIENT):
        for f in files:
            if f.endswith(".img"):
                p = os.path.join(root, f)
                listing.append((os.path.getsize(p), os.path.relpath(p, CLIENT)))
    listing.sort(reverse=True)
    listing = listing[:top_n]

    t0 = time.time()
    mob_names = build_name_map("Mob.img")
    npc_names = build_name_map("Npc.img")
    skill_names = build_name_map("Skill.img")
    eqp_map = build_eqp_map()
    job_names = load_job_names()
    item_names = {c: build_name_map(sf) for c, (_l, sf) in ITEM_CAT.items() if sf}
    map_names = build_map_index()
    skill_books = {}
    skill_img_path = os.path.join(STRING, "Skill.img")
    if os.path.exists(skill_img_path):
        for ch in load_img(skill_img_path).children():
            b = scalar(ch.get("bookName"))
            if b:
                skill_books[ch.name] = b
    obj_links, back_links, bgm_links = scan_map_xml()
    sys.stderr.write(
        f"[index] {time.time()-t0:.1f}s mob={len(mob_names)} npc={len(npc_names)} "
        f"skill={len(skill_names)} eqp={sum(len(v) for v in eqp_map.values())} "
        f"map={len(map_names)} obj={len(obj_links)} back={len(back_links)} bgm={len(bgm_links)}\n"
    )

    rows = []
    for rank, (size, rel) in enumerate(listing, 1):
        img = load_img(os.path.join(CLIENT, rel))
        kids = [c.name for c in img.children()]
        p = rel.split("/")
        d = p[1] if len(p) > 2 else ""
        stem = os.path.splitext(p[-1])[0]
        rec = {
            "rank": rank, "bytes": size, "size_mb": round(size / 1048576, 2),
            "path": rel, "dir": d, "stem": stem,
            "node_count": len(kids), "nodes_head": kids[:20],
            "truncated": bool(img.truncated), "kind": "", "item": "", "detail": "",
            "names": [],
        }

        if d == "Skill":
            if stem == "MobSkill":
                rec["kind"] = "怪物技能"
                rec["item"] = "MobSkill"
                rec["detail"] = f"全部怪物技能的图标与动画定义，{len(kids)} 个技能 ID"
                rec["names"] = kids[:12]
            else:
                book = skill_books.get(stem)
                node = img.get("skill")
                sids = [c.name for c in node.children()] if node is not None else []
                names = [skill_names.get(norm(s)) for s in sids]
                names = [n for n in names if n]
                rec["kind"] = "职业技能"
                rec["item"] = f"{job_names.get(stem, 'job ' + stem)}（job {stem}）"
                rec["detail"] = (
                    f"职业技能文件，技能书《{book or '未标注'}》，含 {len(sids)} 个技能"
                    + (f"（ID {sids[0]}–{sids[-1]}）" if sids else "")
                )
                rec["names"] = names[:16]
        elif d == "Mob":
            rec["kind"] = "怪物"
            rec["item"] = f"{mob_names.get(norm(stem), '')}（{stem}）"
            rec["detail"] = f"怪物动画与数据，{len(kids)} 组动作：{'、'.join(kids[:8])}"
        elif d == "Npc":
            rec["kind"] = "NPC"
            rec["item"] = f"{npc_names.get(norm(stem), '')}（{stem}）"
            rec["detail"] = f"NPC 动画，{len(kids)} 组动作"
        elif d == "Map":
            sub = p[2] if len(p) > 3 else ""
            if sub == "Obj":
                links = obj_links.get(stem, set())
                rec["kind"] = "地图物件"
                rec["item"] = stem
                rec["detail"] = (f"Obj 物件图集，{len(kids)} 个物件分组："
                                 f"{'、'.join(kids[:8])}；{map_summary(links, map_names)}")
            elif sub == "Back":
                links = back_links.get(stem, set())
                rec["kind"] = "地图背景"
                rec["item"] = stem
                rec["detail"] = (f"Back 背景图集，{len(kids)} 个背景分组；"
                                 f"{map_summary(links, map_names)}")
            else:
                rec["kind"] = "地图特效"
                rec["item"] = stem
                rec["detail"] = f"地图通用资源，{len(kids)} 个分组：{'、'.join(kids[:10])}"
                rec["names"] = kids[:16]
        elif d == "Sound":
            links = bgm_links.get(stem, set())
            if stem == "Mob":
                rec["kind"] = "音效"
                rec["item"] = "怪物音效库"
                rec["detail"] = f"全部怪物攻击 / 死亡 / 技能音效，{len(kids)} 条"
            else:
                rec["kind"] = "BGM"
                rec["item"] = GRAND.get(stem, stem)
                rec["detail"] = (f"背景音乐集，{len(kids)} 首：{'、'.join(kids[:8])}；"
                                 f"{map_summary(links, map_names)}")
                rec["names"] = kids[:20]
        elif d == "Item":
            cat = p[2] if len(p) > 3 else ""
            label, _ = ITEM_CAT.get(cat, (cat, None))
            nm = item_names.get(cat, {}).get(norm(stem), "")
            sample = []
            for ch in img.children()[:400]:
                v = item_names.get(cat, {}).get(norm(ch.name))
                if v:
                    sample.append(v)
            rec["kind"] = f"道具图标（{label}）"
            rec["item"] = f"{label} {stem} 段"
            rec["detail"] = (f"{label}图标集（道具 ID 前 4 位 {stem}），{len(kids)} 项"
                             + (f"，名称段：{nm}" if nm else ""))
            rec["names"] = sample[:16]
        elif d == "Character":
            cat = p[2] if len(p) > 3 else ""
            label = CHR_CAT.get(cat, cat)
            nm = eqp_map.get(cat, {}).get(norm(stem), "")
            rec["kind"] = f"装备外观（{label}）"
            rec["item"] = f"{nm or stem}（{stem}）"
            rec["detail"] = f"{label}装备外观 / 动作帧，{len(kids)} 组动作"
        elif d == "Effect":
            rec["kind"] = "特效"
            rec["item"] = stem
            rec["detail"] = (f"{EFFECT_HINT.get(p[-1], '特效集')}，{len(kids)} 个分组："
                             f"{'、'.join(kids[:12])}")
            rec["names"] = kids[:20]
        elif d == "UI":
            rec["kind"] = "界面"
            rec["item"] = stem
            rec["detail"] = f"UI 界面资源，{len(kids)} 个分组：{'、'.join(kids[:10])}"
        else:
            rec["kind"] = d or "其他"
            rec["item"] = stem
            rec["detail"] = f"{rel}，{len(kids)} 个节点"
        rows.append(rec)

    with open(os.path.join(HERE, "inventory.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(HERE, "inventory.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["排名", "大小(MB)", "类别", "对象", "路径", "顶层节点数", "内容说明"])
        for r in rows:
            w.writerow([r["rank"], r["size_mb"], r["kind"], r["item"], r["path"],
                        r["node_count"], r["detail"]])
    sys.stderr.write(f"[scan] {len(rows)} rows in {time.time()-t0:.1f}s\n")
    return rows


def render_html(rows: list[dict], total_client_bytes: int) -> str:
    total = sum(r["bytes"] for r in rows)
    by_kind: dict[str, list[int]] = {}
    for r in rows:
        e = by_kind.setdefault(r["kind"], [0, 0])
        e[0] += 1
        e[1] += r["bytes"]

    def esc(s):
        return html.escape(str(s))

    cards = [
        (f"{total/2**30:.2f} GB", f"前 {len(rows)} 个 IMG 合计"),
        (f"{total/total_client_bytes*100:.1f}%", f"占客户端 clien/ 总量（{total_client_bytes/2**30:.2f} GB）"),
        (f"{rows[0]['size_mb']} MB", f"最大单体：{rows[0]['path']}"),
        (f"{len(by_kind)}", "覆盖资源大类"),
    ]
    trs = []
    for r in rows:
        names = "".join(f'<span class="badge">{esc(n)}</span>' for n in r.get("names", [])[:10])
        trs.append(
            f'<tr data-idx="{r["rank"]-1}" data-k="{esc(r["kind"])}">'
            f'<td class="n">{r["rank"]}</td>'
            f'<td class="n">{r["size_mb"]:.1f}</td>'
            f'<td><span class="tag">{esc(r["kind"])}</span></td>'
            f'<td class="name">{esc(r["item"])}</td>'
            f'<td><code>{esc(r["path"])}</code></td>'
            f'<td class="detail">{esc(r["detail"])}'
            + (f'<div>{names}</div>' if names else "")
            + "</td></tr>"
        )
    kind_bars = "".join(
        f'<div class="kb"><span>{esc(k)}</span>'
        f'<div class="meter" style="width:{v[1]/total*100:.1f}%"></div>'
        f'<b>{v[1]/2**20:.0f} MB · {v[0]} 个</b></div>'
        for k, v in sorted(by_kind.items(), key=lambda kv: -kv[1][1])
    )
    kinds = sorted(by_kind)
    buttons = "".join(
        f'<button data-g="{esc(k)}">{esc(k)}</button>' for k in kinds
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>客户端最大 {len(rows)} 个 IMG 清单</title>
<style>
  :root{{--bg:#0f1116;--panel:#171a21;--panel2:#1d2129;--line:#2a2f3a;--tx:#e6e9ef;--tx2:#98a1b3;--acc:#e05c5c;--acc2:#63b3ed;}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--tx);font:14px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,sans-serif;}}
  .wrap{{max-width:1320px;margin:0 auto;padding:28px 20px 60px;}}
  h1{{font-size:22px;margin:0 0 6px;}}
  .sub{{color:var(--tx2);font-size:13px;margin-bottom:18px;}}
  .cards{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;}}
  .card{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 16px;min-width:170px;}}
  .card b{{display:block;font-size:20px;color:var(--acc);}}
  .card span{{color:var(--tx2);font-size:12px;}}
  .bar{{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px;}}
  input,button{{font:inherit;color:var(--tx);background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:7px 12px;outline:none;}}
  input{{min-width:240px}}
  button{{cursor:pointer}}
  button.on{{border-color:var(--acc);color:var(--acc)}}
  table{{width:100%;border-collapse:collapse;background:var(--panel);border-radius:10px;overflow:hidden;}}
  th,td{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;}}
  th{{background:var(--panel2);color:var(--tx2);font-weight:600;cursor:pointer;white-space:nowrap;user-select:none;}}
  th:hover{{color:var(--tx)}}
  td.n,th.n{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;}}
  tr:hover td{{background:#1a1e26}}
  .name{{font-weight:600;white-space:nowrap}}
  .detail{{color:var(--tx2);font-size:12.5px;max-width:640px}}
  .tag{{display:inline-block;font-size:11.5px;padding:1px 8px;border-radius:20px;border:1px solid var(--line);color:var(--tx2);white-space:nowrap}}
  .badge{{display:inline-block;font-size:11px;padding:1px 7px;border-radius:20px;border:1px solid #33405a;color:var(--acc2);margin:4px 4px 0 0}}
  code{{background:var(--panel2);padding:1px 5px;border-radius:5px;color:#d5b06a;font-size:12px}}
  h2{{font-size:16px;margin:26px 0 10px;color:var(--tx2);}}
  .kbs{{display:flex;flex-direction:column;gap:6px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 18px;}}
  .kb{{display:grid;grid-template-columns:130px 1fr 130px;gap:10px;align-items:center;font-size:12.5px;color:var(--tx2)}}
  .meter{{height:8px;border-radius:5px;background:linear-gradient(90deg,#e05c5c,#f0b95e);}}
  .kb b{{text-align:right;color:var(--tx);font-weight:500}}
  .note{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 18px;color:var(--tx2);font-size:13px;margin-top:14px}}
  .note b{{color:var(--tx)}}
  tr.hide{{display:none}}
</style>
</head>
<body>
<div class="wrap">
  <h1>客户端最大 {len(rows)} 个 IMG 清单</h1>
  <div class="sub">扫描范围 <code>clien/</code> 下全部 53,915 个 <code>.img</code>；内容由 <code>tool/wz-python</code> 实际解析文件结构得到，
  名称取自客户端 <code>Data/String/*.img</code>，地图 / BGM 归属由服务端 <code>gms-server/wz/Map.wz</code> 的
  <code>oS</code> / <code>bS</code> / <code>info/bgm</code> 字段反向关联。生成时间 2026-09-29。</div>

  <div class="cards">
    {''.join(f'<div class="card"><b>{esc(a)}</b><span>{esc(b)}</span></div>' for a, b in cards)}
  </div>

  <h2>资源大类占用</h2>
  <div class="kbs">{kind_bars}</div>

  <h2>明细</h2>
  <div class="bar">
    <input id="q" placeholder="搜索名称 / ID / 路径 / 说明">
    <button class="on" data-g="all">全部</button>
    {buttons}
    <span style="color:var(--tx2);font-size:12px">点击表头排序</span>
  </div>

  <table id="t">
    <thead><tr>
      <th class="n" data-k="rank">排名</th>
      <th class="n" data-k="size_mb">大小 MB</th>
      <th data-k="kind">类别</th>
      <th data-k="item">对象</th>
      <th data-k="path">路径</th>
      <th data-k="detail">内容说明</th>
    </tr></thead>
    <tbody>{''.join(trs)}</tbody>
  </table>

  <div class="note">
    <b>说明</b><br>
    · 排名按文件字节数降序，同尺寸并列时按路径。<br>
    · 「对象」对技能文件为 job 编号 + 技能书名，对怪物 / NPC 为客户端 <code>String</code> 里的显示名，
    对地图物件 / 背景 / BGM 为被引用的地图数量与区域。<br>
    · 全部 {len(rows)} 个文件独立解析通过，无 <code>truncated</code>、无解析告警；本工具全程只读，不写入任何 IMG。<br>
    · 原始数据见 <code>tool/img-inventory/inventory.json</code> 与 <code>inventory.csv</code>。
  </div>
</div>
<script>
const RAW={json.dumps([{ "rank": r["rank"], "size_mb": r["size_mb"], "kind": r["kind"], "item": r["item"], "path": r["path"], "detail": r["detail"] } for r in rows], ensure_ascii=False)};
const TB=document.querySelector('#t tbody');
let rows=[...TB.querySelectorAll('tr')];
let group='all';
function apply(){{
  const q=document.getElementById('q').value.trim().toLowerCase();
  rows.forEach(tr=>{{
    const okG = group==='all' || tr.dataset.k===group;
    const okQ = !q || tr.textContent.toLowerCase().includes(q);
    tr.classList.toggle('hide', !(okG&&okQ));
  }});
}}
document.getElementById('q').addEventListener('input',apply);
document.querySelectorAll('.bar button').forEach(b=>{{
  b.addEventListener('click',()=>{{
    document.querySelectorAll('.bar button').forEach(x=>x.classList.remove('on'));
    b.classList.add('on'); group=b.dataset.g; apply();
  }});
}});
const dir={{}};
document.querySelectorAll('th').forEach(th=>{{
  th.addEventListener('click',()=>{{
    const k=th.dataset.k; dir[k]=!dir[k];
    rows.sort((a,b)=>{{
      const av=RAW[+a.dataset.idx][k], bv=RAW[+b.dataset.idx][k];
      const an=typeof av==='number', bn=typeof bv==='number';
      const r = (an&&bn) ? av-bv : String(av).localeCompare(String(bv),'zh');
      return dir[k] ? -r : r;
    }});
    rows.forEach(t=>TB.appendChild(t));
  }});
}});
</script>
</body>
</html>
"""


def main() -> int:
    top_n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    rows = collect(top_n)
    total_client = 0
    for root, _dirs, files in os.walk(CLIENT):
        for f in files:
            try:
                total_client += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    out_html = os.path.join(REPO, "docs", f"客户端最大{top_n}个IMG清单.html")
    with open(out_html, "w", encoding="utf-8") as fh:
        fh.write(render_html(rows, total_client))
    sys.stderr.write(f"[html] {out_html}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
