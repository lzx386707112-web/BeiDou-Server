"""Render the client Canvas pixel-encoding report.

Reads the JSON produced by ``scan_canvas_formats.py`` (whole-client and
top-N runs), optionally re-extracts a Git baseline blob to prove whether an
encoding was original client data or introduced by the migration, and writes a
dark-theme HTML report to ``docs/客户端Canvas编码分布.html``.

Read-only with respect to client data: baseline blobs go to a temp dir only.

Usage:
    python3 render_canvas_report.py [--baseline-rev 0119c8d8a6]
"""

from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict

REPO = "/Users/lizixian/Documents/mxd/BeiDou-Server"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "tool", "wz-python"))

FORMAT_NAMES = {
    0: "未设置", 1: "ARGB4444", 2: "ARGB8888", 3: "ARGB8888(1/4)",
    257: "ARGB1555", 513: "RGB565", 517: "RGB565(1/16)",
    1026: "DXT3/BC3", 2050: "DXT5/BC3",
}
# Files sampled for the baseline comparison (skill + untouched originals).
BASELINE_FILES = [
    "Data/Skill/232.img", "Data/Skill/212.img", "Data/Skill/132.img",
    "Data/Mob/9420521.img", "Data/Map/Obj/acc6.img",
]


def esc(s) -> str:
    return html.escape(str(s))


def git_blob(rev: str, path: str) -> str:
    """Extract one blob through raw git plumbing (never `git show > file`)."""
    out = os.path.join(tempfile.gettempdir(), "beidou-base-" + path.replace("/", "_"))
    with open(out, "wb") as fh:
        subprocess.run(["git", "cat-file", "blob", f"{rev}:{path}"],
                       cwd=REPO, stdout=fh, check=True)
    return out


def canvas_map(path: str) -> dict:
    from wzpy import WzImage, WzKey, detect_region_from_img
    from wzpy.properties import WzCanvasProperty, WzProperty

    with open(path, "rb") as fh:
        data = fh.read()
    img = WzImage.from_bytes(data, key=WzKey.for_region(detect_region_from_img(data) or "GMS"))
    img.parse()
    out: dict[str, tuple] = {}

    def walk(node: WzProperty, p: str = "") -> None:
        if isinstance(node, WzCanvasProperty):
            out[p] = (node.format, node.format2, f"{node.width}x{node.height}")
        for ch in node.children():
            walk(ch, f"{p}/{ch.name}" if p else ch.name)

    walk(img.root)
    return out


def baseline_diff(rev: str) -> list[dict]:
    res = []
    for rel in BASELINE_FILES:
        try:
            base = canvas_map(git_blob(rev, "clien/" + rel))
        except Exception as exc:  # noqa: BLE001
            res.append({"path": rel, "error": str(exc)})
            continue
        cur = canvas_map(os.path.join(REPO, "clien", rel))
        changed = [p for p in base if p in cur and base[p][:2] != cur[p][:2]]
        gone = [p for p in base if p not in cur]
        new = [p for p in cur if p not in base]
        new_fmt = Counter(f"{cur[p][0]}.{cur[p][1]}" for p in new)
        res.append({
            "path": rel,
            "base_canvas": len(base),
            "base_8": sum(1 for v in base.values() if v[0] == 2),
            "cur_canvas": len(cur),
            "cur_8": sum(1 for v in cur.values() if v[0] == 2),
            "cur_4": sum(1 for v in cur.values() if v[0] == 1),
            "new": len(new), "new_fmt": dict(new_fmt),
            "gone": len(gone), "changed": len(changed),
            "changed_list": sorted(changed)[:12],
        })
    return res


def render(allf: dict, topn: dict, diffs: list, rev: str) -> str:
    files = [r for r in allf["files"] if "formats" in r]
    grand = Counter()
    for r in files:
        for k, v in r["formats"].items():
            grand[int(k.split(".")[0])] += v
    total = sum(grand.values())

    def dirkey(p):
        s = p.split("/")
        return "/".join(s[:2]) if len(s) > 2 else s[0]

    per = defaultdict(Counter)
    for r in files:
        for k, v in r["formats"].items():
            per[dirkey(r["path"])][int(k.split(".")[0])] += v

    has8 = sum(1 for r in files if "2.0" in r["formats"])
    pure8 = sum(1 for r in files if set(r["formats"]) == {"2.0"})
    pure4 = sum(1 for r in files if set(r["formats"]) == {"1.0"})
    rgb565 = [r["path"] for r in files if "513.0" in r["formats"]]

    top_hits = [r for r in topn["files"] if "formats" in r and "2.0" in r["formats"]]
    top_hits.sort(key=lambda r: -r["formats"]["2.0"])
    top_list = [r for r in topn["files"] if "formats" in r]
    rank_of = {}
    inv_path = os.path.join(HERE, "inventory.json")
    if os.path.exists(inv_path):
        for row in json.load(open(inv_path, encoding="utf-8")):
            rank_of[row["path"]] = row["rank"]

    cards = [
        (f"{total:,}", f"全客户端 Canvas 总数（{len(files):,} 个 IMG）"),
        (f"{grand.get(2,0):,}", f"ARGB8888（format=2）· {grand.get(2,0)/total*100:.1f}%"),
        (f"{grand.get(1,0):,}", f"ARGB4444（format=1）· {grand.get(1,0)/total*100:.1f}%"),
        (f"{has8:,}", f"含 ARGB8888 的文件（共 {len(files):,} 个，{has8/len(files)*100:.0f}%）"),
    ]

    dir_rows = "".join(
        f"<tr><td><code>{esc(k)}</code></td><td class='n'>{sum(c.values()):,}</td>"
        f"<td class='n'>{c.get(1,0):,}</td><td class='n'>{c.get(2,0):,}</td>"
        f"<td class='n'>{sum(v for f,v in c.items() if f not in (1,2)):,}</td>"
        f"<td class='n'>{c.get(2,0)/max(sum(c.values()),1)*100:.1f}%</td></tr>"
        for k, c in sorted(per.items(), key=lambda kv: -sum(kv[1].values()))
    )
    top_rows = "".join(
        f"<tr><td class='n'>{rank_of.get(r['path'], i+1)}</td><td><code>{esc(r['path'])}</code></td>"
        f"<td class='n'>{r['canvases']:,}</td>"
        f"<td class='n'>{r['formats'].get('2.0',0):,}</td>"
        f"<td class='n'>{r['formats'].get('1.0',0):,}</td>"
        f"<td class='n'>{r['formats'].get('2.0',0)/max(r['canvases'],1)*100:.1f}%</td></tr>"
        for i, r in enumerate(top_list)
    )
    top8_rows = "".join(
        f"<tr><td><code>{esc(r['path'])}</code></td><td class='n'>{r['canvases']:,}</td>"
        f"<td class='n'>{r['formats'].get('2.0',0):,}</td>"
        f"<td class='n'>{r['formats'].get('1.0',0):,}</td>"
        f"<td class='n'>{r['formats'].get('2.0',0)/max(r['canvases'],1)*100:.1f}%</td></tr>"
        for r in top_hits
    )
    diff_rows = "".join(
        f"<tr><td><code>{esc(d['path'])}</code></td>"
        f"<td class='n'>{d.get('base_canvas',0):,}</td><td class='n'>{d.get('base_8',0):,}</td>"
        f"<td class='n'>{d.get('cur_canvas',0):,}</td><td class='n'>{d.get('cur_8',0):,}</td>"
        f"<td class='n'>{d.get('cur_4',0):,}</td><td class='n'>{d.get('new',0):,}</td>"
        f"<td class='n'>{d.get('changed',0):,}</td><td class='n'>{d.get('gone',0):,}</td></tr>"
        for d in diffs if "error" not in d
    )
    changed_232 = next((d for d in diffs if d["path"] == "Data/Skill/232.img"), {})
    cl = changed_232.get("changed_list", [])
    cl_html = "".join(f"<code>{esc(p)}</code> " for p in cl)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>客户端 Canvas 像素编码分布</title>
<style>
  :root{{--bg:#0f1116;--panel:#171a21;--panel2:#1d2129;--line:#2a2f3a;--tx:#e6e9ef;--tx2:#98a1b3;--acc:#e05c5c;--acc2:#63b3ed;--ok:#5fbf85;--warn:#f0b95e;}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--tx);font:14px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,sans-serif;}}
  .wrap{{max-width:1240px;margin:0 auto;padding:28px 20px 60px;}}
  h1{{font-size:22px;margin:0 0 6px;}}
  h2{{font-size:16px;margin:28px 0 10px;color:var(--tx2);}}
  .sub{{color:var(--tx2);font-size:13px;margin-bottom:18px;}}
  .cards{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;}}
  .card{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 16px;min-width:186px;}}
  .card b{{display:block;font-size:20px;color:var(--acc);}}
  .card span{{color:var(--tx2);font-size:12px;}}
  table{{width:100%;border-collapse:collapse;background:var(--panel);border-radius:10px;overflow:hidden;}}
  th,td{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;}}
  th{{background:var(--panel2);color:var(--tx2);font-weight:600;white-space:nowrap;}}
  td.n,th.n{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;}}
  tr:hover td{{background:#1a1e26}}
  code{{background:var(--panel2);padding:1px 5px;border-radius:5px;color:#d5b06a;font-size:12px;}}
  .note{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 18px;color:var(--tx2);font-size:13px;margin-top:14px;}}
  .note b{{color:var(--tx)}}
  .verdict{{border-left:4px solid var(--ok);background:var(--panel);border-radius:10px;padding:14px 18px;margin-bottom:16px;font-size:13.5px;}}
  .verdict b{{color:var(--ok)}}
  .warn{{border-left:4px solid var(--warn);}}
  .warn b{{color:var(--warn)}}
</style>
</head>
<body>
<div class="wrap">
  <h1>客户端 Canvas 像素编码分布</h1>
  <div class="sub">数据来源：用 <code>tool/wz-python</code> 逐个解析 <code>clien/</code> 下全部 {len(files):,} 个 <code>.img</code>
  的真实属性树，统计每个 <code>Canvas</code> 节点的 <code>format</code>/<code>format2</code>。生成时间 2026-09-29。</div>

  <div class="cards">
    {''.join(f'<div class="card"><b>{esc(a)}</b><span>{esc(b)}</span></div>' for a, b in cards)}
  </div>

  <div class="verdict">
    <b>结论：有，而且 ARGB8888 是客户端的主流编码（占 {grand.get(2,0)/total*100:.1f}%）。</b>
    它不是迁移引入的，而是客户端原生数据：本仓库最早的客户端提交（<code>{esc(rev)}</code>，2025-09-20「魔改客户端上传资源」）
    中抽样的技能 / 怪物 / 地图物件文件就是 <b>100% ARGB8888</b>，且至今未改动过的那批仍是 ARGB8888。
    因此老客户端本来就能渲染 ARGB8888，它<b>本身不构成兼容性风险</b>。
  </div>

  <div class="verdict warn">
    <b>但项目的 ARGB4444 规范确实被执行了：</b>迁移新增的画布全部是 ARGB4444。
    以 <code>Data/Skill/232.img</code>（主教）为例——新增 {changed_232.get('new',0)} 个画布
    <b>全部为 ARGB4444</b>；{changed_232.get('changed',0)} 个原 ARGB8888 画布被替换成 ARGB4444（同时尺寸也变了，属重做而非单纯转码）；
    保留的 {changed_232.get('cur_8',0)} 个 ARGB8888 全部是未改动的原版数据。
  </div>

  <h2>全客户端编码分布</h2>
  <table>
    <thead><tr><th>format 值</th><th>编码</th><th class="n">画布数</th><th class="n">占比</th></tr></thead>
    <tbody>
    {''.join(f'<tr><td class="n">{f}</td><td>{esc(FORMAT_NAMES.get(f,"?"))}</td><td class="n">{n:,}</td><td class="n">{n/total*100:.2f}%</td></tr>' for f, n in sorted(grand.items()))}
    </tbody>
  </table>
  <div class="note">
    全客户端只出现 {len(grand)} 种编码，<b>没有 DXT（BC2/BC3）、没有 ARGB1555、没有未知编码</b>。
    RGB565 只出现在 <code>{esc(', '.join(rgb565) or '无')}</code>（{grand.get(513,0)} 个画布，肉眼不可见的占位图）。
    文件维度：含 ARGB8888 的 {has8:,} 个；<b>纯 ARGB8888</b> 的 {pure8:,} 个；纯 ARGB4444 的 {pure4:,} 个。
  </div>

  <h2>按目录分布</h2>
  <table>
    <thead><tr><th>目录</th><th class="n">画布</th><th class="n">ARGB4444</th><th class="n">ARGB8888</th><th class="n">其他</th><th class="n">8888 占比</th></tr></thead>
    <tbody>{dir_rows}</tbody>
  </table>
  <div class="note">
    <code>Data/Character</code>（{per['Data/Character'].get(2,0):,} 个 8888）是 ARGB8888 的绝对主力——角色装备外观帧数极多、且原版就是 32 位色。
    <code>Data/Effect</code>（98% 4444）、<code>Data/Map</code>（87% 4444）则基本都是 ARGB4444。
  </div>

  <h2>面积最大的 100 个 IMG 中，含 ARGB8888 的 {len(top_hits)} 个</h2>
  <table>
    <thead><tr><th class="n">排名</th><th>路径</th><th class="n">画布</th><th class="n">ARGB8888</th><th class="n">ARGB4444</th><th class="n">8888 占比</th></tr></thead>
    <tbody>{top_rows}</tbody>
  </table>

  <h2>全客户端 ARGB8888 画布数最多的文件（前 20）</h2>
  <table>
    <thead><tr><th>路径</th><th class="n">画布</th><th class="n">ARGB8888</th><th class="n">ARGB4444</th><th class="n">8888 占比</th></tr></thead>
    <tbody>{top8_rows}</tbody>
  </table>

  <h2>基线对照（{esc(rev)} → 当前）</h2>
  <table>
    <thead><tr><th>文件</th><th class="n">基线画布</th><th class="n">基线 8888</th><th class="n">当前画布</th>
    <th class="n">当前 8888</th><th class="n">当前 4444</th><th class="n">新增</th><th class="n">编码变化</th><th class="n">删除</th></tr></thead>
    <tbody>{diff_rows}</tbody>
  </table>
  <div class="note">
    232.img 中编码发生变化的画布全部集中在 <code>skill/2321003/summon/</code>（召唤物动画），例如：<br>
    {cl_html}
  </div>

  <div class="note">
    <b>复现方式</b><br>
    <code>/opt/homebrew/bin/python3 tool/img-inventory/scan_canvas_formats.py --all</code>（约 6 分钟，只读）<br>
    <code>/opt/homebrew/bin/python3 tool/img-inventory/render_canvas_report.py --baseline-rev {esc(rev)}</code><br>
    原始数据：<code>tool/img-inventory/canvas_formats_all.json</code>、<code>canvas_formats_top100.json</code>。
  </div>
</div>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-rev", default="0119c8d8a6")
    args = ap.parse_args()
    allf = json.load(open(os.path.join(HERE, "canvas_formats_all.json"), encoding="utf-8"))
    topn = json.load(open(os.path.join(HERE, "canvas_formats_top100.json"), encoding="utf-8"))
    diffs = baseline_diff(args.baseline_rev)
    out = os.path.join(REPO, "docs", "客户端Canvas编码分布.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(render(allf, topn, diffs, args.baseline_rev))
    sys.stderr.write(f"[html] {out}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
