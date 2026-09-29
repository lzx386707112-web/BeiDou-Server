"""Render the client-wide ARGB8888 -> ARGB4444 feasibility report.

Inputs (all produced by sibling scripts; read-only against client data):
  full.json       -- scan_4444_full.py            whole client, all files
  byclass.json    -- scan_4444_full.py --max-files random subsample with
                     per-class c4 accounting (the lossless/lossy size split)
  structure.json  -- probe_structure.py           mechanical safety probes

Output: docs/全量ARGB4444转换可行性评估.html (dark theme, matches the other
client reports in docs/).
"""
from __future__ import annotations

import html
import json
import os
from collections import defaultdict

REPO = "/Users/lizixian/Documents/mxd/BeiDou-Server"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(REPO, "docs", "全量ARGB4444转换可行性评估.html")

KINDS = [
    ("LOSSLESS", "位逐位无损",
     "四个通道的值本来就是 17 的倍数（低 4 位 = 高 4 位的复制），转 4444 后像素完全不变"),
    ("ALPHA_ONLY", "仅 alpha 变",
     "颜色完全一致，只有 alpha 台阶改变"),
    ("COLOUR_LOSS", "会掉色",
     "有颜色通道被量化，存在可见色带风险"),
]


def esc(s) -> str:
    return html.escape(str(s))


def mb(n: float) -> str:
    v = n / 2**20
    return f"{v / 1024:.2f} GB" if v >= 1024 else f"{v:.1f} MB"


def main() -> int:
    with open(os.path.join(HERE, "full.json"), encoding="utf-8") as f:
        full = json.load(f)
    with open(os.path.join(HERE, "byclass.json"), encoding="utf-8") as f:
        bycls = json.load(f)
    with open(os.path.join(HERE, "structure.json"), encoding="utf-8") as f:
        st = json.load(f)

    counts, zlib, classes, class_bytes = (full["counts"], full["zlib"],
                                          full["classes"], full["class_bytes"])
    errors = full["errors"]

    agg = defaultdict(int)
    for v in bycls["class_bytes"].values():
        for k, vv in v.items():
            agg[k] += vv
    c8t = sum(agg[k] for k, _l, _d in KINDS)
    c4t = sum(agg[k + "_c4"] for k, _l, _d in KINDS)

    tot_8888 = sum(c.get("fmt2", 0) for c in counts.values())
    tot_4444 = sum(c.get("fmt1", 0) for c in counts.values())
    tot_canvas = sum(c.get("canvas", 0) for c in counts.values())
    files_with_8888 = sum(v.get("files", 0) for v in counts.values() if v.get("fmt2", 0) > 0)
    pay8888 = sum(z.get("payload_all", 0) for z in zlib.values())
    overall_ratio = c4t / c8t if c8t else 1.0
    saved_lo = pay8888 * (1 - overall_ratio)
    c8f = sum(z.get("c8", 0) for z in zlib.values())
    c4f = sum(z.get("c4", 0) for z in zlib.values())
    ratio_full = c4f / c8f if c8f else overall_ratio
    saved_hi = pay8888 * (1 - ratio_full)

    measured_cls = sum(classes[k].get("measured", 0) for k in classes)
    lossless_pct = 100 * sum(classes[k].get("LOSSLESS", 0) for k in classes) / max(measured_cls, 1)
    lossless_byte_share = agg["LOSSLESS"] / c8t if c8t else 0
    ll_ratio = agg["LOSSLESS_c4"] / max(agg["LOSSLESS"], 1)
    cl_ratio = agg["COLOUR_LOSS_c4"] / max(agg["COLOUR_LOSS"], 1)
    lossless_only_save = pay8888 * lossless_byte_share * (1 - ll_ratio)

    p1 = st["probe1_variable_length_refusal"]["counts"]
    refused = sum(v for k, v in p1.items() if k.startswith("refused"))
    attempted = p1.get("accepted", 0) + refused
    refuse_pct = 100 * refused / max(attempted, 1)
    p2 = st["probe2_same_length_inplace"]
    p3 = st["probe3_zero_tail_plane"]["summary"]

    r = defaultdict(int)
    for v in full["ratio"].values():
        for k, vv in v.items():
            r[k] += vv
    ratio_tot = r.get("x1.0", 0) + r.get("x2.0", 0) + r.get("x0.5", 0)
    x2_pct = 100 * r.get("x2.0", 0) / max(ratio_tot, 1)
    tail_zero_pct = 100 * r.get("tail_zero", 0) / max(r.get("x2.0", 0), 1)

    px = sum(e.get("px", 0) for e in errors.values())
    rgb_mae = sum(e.get("rgb", 0) for e in errors.values()) / max(px * 3, 1)
    a_mae = sum(e.get("a", 0) for e in errors.values()) / max(px, 1)
    a_changed = 100 * sum(e.get("a_changed", 0) for e in errors.values()) / max(px, 1)
    rgb_max = max(e.get("rgbmax", 0) for e in errors.values())

    cls_share = {}
    for cat in classes:
        b = class_bytes.get(cat, {})
        tb = sum(b.get(k, 0) for k, _l, _d in KINDS)
        cls_share[cat] = 100 * b.get("LOSSLESS", 0) / tb if tb else 0

    rows = []
    for cat, v in counts.items():
        if not v.get("fmt2"):
            continue
        z = zlib.get(cat, {})
        pay = z.get("payload_all", 0)
        z8, z4 = z.get("c8", 0), z.get("c4", 0)
        rt = z4 / z8 if z8 else 1.0
        rows.append({"cat": cat, "canvas": v.get("canvas", 0), "f2": v.get("fmt2", 0),
                     "pay": pay, "ratio": rt, "saved": pay * (1 - rt),
                     "ll": cls_share.get(cat, 0), "loss": 100 - cls_share.get(cat, 0)})
    rows.sort(key=lambda x: -x["saved"])
    top2_save = sum(x["saved"] for x in rows if x["cat"] in
                    ("Character/Weapon", "Character/Cap"))

    css = """
  :root{--bg:#0f1116;--panel:#171a21;--panel2:#1d2129;--line:#2a2f3a;--tx:#e6e9ef;--tx2:#98a1b3;--acc:#e05c5c;--acc2:#63b3ed;--ok:#5fbf85;--warn:#f0b95e;}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,sans-serif;}
  .wrap{max-width:1240px;margin:0 auto;padding:28px 20px 60px;}
  h1{font-size:22px;margin:0 0 6px;}
  h2{font-size:16px;margin:30px 0 10px;color:var(--tx2);}
  h3{font-size:14px;margin:20px 0 8px;}
  .sub{color:var(--tx2);font-size:13px;margin-bottom:18px;}
  .cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 16px;min-width:172px;flex:1 1 172px;}
  .card b{display:block;font-size:19px;color:#fff;line-height:1.3;}
  .card span{color:var(--tx2);font-size:12px;}
  .verdict{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--acc);border-radius:8px;padding:12px 16px;margin:10px 0 18px;}
  .verdict.ok{border-left-color:var(--ok);}
  .verdict.warn{border-left-color:var(--warn);}
  table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:13px;}
  th,td{padding:7px 10px;text-align:right;border-bottom:1px solid var(--line);}
  th:first-child,td:first-child{text-align:left;}
  th{background:var(--panel2);color:var(--tx2);font-weight:600;white-space:nowrap;}
  tr:last-child td{border-bottom:none;}
  code{background:var(--panel2);padding:1px 5px;border-radius:4px;font-size:12px;color:#cbd5e1;}
  .v-ok{color:var(--ok)}.v-warn{color:var(--warn)}.v-bad{color:var(--acc)}
  ul{margin:8px 0 8px 18px;padding:0}li{margin:5px 0}
  .note{color:var(--tx2);font-size:12px;margin-top:6px;}
  .meter{display:inline-block;height:7px;border-radius:4px;background:var(--acc2);vertical-align:middle;}
"""
    h = ['<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">',
         '<meta name="viewport" content="width=device-width,initial-scale=1">',
         "<title>全量 ARGB8888 → ARGB4444 转换可行性评估</title>",
         f"<style>{css}</style></head><body><div class='wrap'>",
         "<h1>全客户端 ARGB8888 → ARGB4444 转换可行性评估</h1>",
         f"<div class='sub'>数据源：<code>clien/</code> 全部 {full['files_total']:,} 个 IMG、"
         f"{tot_canvas:,} 个画布（普查耗时 {full['seconds']:.0f}s）；按文件随机抽样测量后"
         "按目录加权外推。脚本 <code>tool/img-inventory/scan_4444_full.py</code> + "
         "<code>probe_structure.py</code>；全程只读，未改写任何客户端文件。</div>"]

    h.append(
        "<div class='verdict warn'><b>能转，但「全改成 4444」有三个真问题，建议不要全量做。</b><br>"
        "编码不是障碍：老客户端本来就在渲染 " + f"{tot_4444:,}" + " 个 ARGB4444 画布，"
        "按 <code>AGENTS.md</code> 迁移的技能载荷也是 4444 且能播。真正的障碍是：<br>"
        "① <b>省的空间集中在「会掉色」的那部分</b>——位逐位无损的画布占 "
        f"{lossless_pct:.1f}%，但它们的冗余早已被 zlib 吃掉，转过去只小 "
        f"{100 * (1 - ll_ratio):.1f}%；而会掉色的画布能小 {100 * (1 - cl_ratio):.1f}%。"
        "想省 0.5 GB 就得接受掉色。<br>"
        f"② <b>全量改写要动 {files_with_8888:,} 个文件</b>，命中项目里明令禁止的整树重写形态；"
        f"而且现有增量补丁器对变长替换的拒绝率是 {refuse_pct:.0f}%（全部落在 "
        "<code>Character/</code> 装备），这条路现在是断的。<br>"
        "③ <b>结构上真正安全的路线（等长原地补丁）带一个仓库内无证据的假设</b>："
        "压缩后变短的部分要用 0 补齐，客户端能否容忍 zlib 流后的填充字节，只能真机验。</div>")

    h.append("<div class='cards'>")
    for big, small in [
        (f"{tot_8888:,}", "待转换的 ARGB8888 画布"),
        (f"{tot_4444:,}", f"已是 ARGB4444（占 {100 * tot_4444 / max(tot_canvas, 1):.0f}%）"),
        (f"{files_with_8888:,}", "含 8888 画布的 IMG 文件"),
        (mb(pay8888), "8888 画布载荷总量"),
        (f"{mb(saved_lo)}~{mb(saved_hi)}",
         f"全量转换预估可省（客户端的 {100 * saved_lo / full['clien_img_bytes']:.0f}~"
         f"{100 * saved_hi / full['clien_img_bytes']:.0f}%）"),
        (f"{lossless_pct:.1f}%", "画布转 4444 后像素完全不变"),
        (f"{refuse_pct:.0f}%", "变长替换被工具链拒绝"),
    ]:
        h.append(f"<div class='card'><b>{big}</b><span>{small}</span></div>")
    h.append("</div>")

    h.append("<h2>1. 体积：省得动，但省的不是你以为的那部分</h2>")
    h.append("<div class='verdict'>ARGB4444 的未压缩数据确实是 8888 的一半，但 IMG 里的画布是 "
             "<b>zlib 压缩存储</b>，实际能省多少取决于「被丢掉的那 4 位里还剩多少信息量」。</div>")
    h.append("<table><tr><th>画布类别</th><th>占 8888 画布数</th><th>占 8888 压缩体积</th>"
             "<th>转换前</th><th>转换后</th><th>比值</th><th>说明</th></tr>")
    for k, label, desc in KINDS:
        n = sum(classes[c].get(k, 0) for c in classes)
        c8, c4 = agg[k], agg[k + "_c4"]
        if not c8:
            continue
        h.append(f"<tr><td><b>{esc(label)}</b></td><td>{100 * n / max(measured_cls, 1):.1f}%</td>"
                 f"<td>{100 * c8 / max(c8t, 1):.1f}%</td><td>{mb(c8)}</td><td>{mb(c4)}</td>"
                 f"<td>{100 * c4 / max(c8, 1):.1f}%</td><td>{esc(desc)}</td></tr>")
    h.append(f"<tr><td><b>合计</b></td><td>100%</td><td>100%</td><td><b>{mb(c8t)}</b></td>"
             f"<td><b>{mb(c4t)}</b></td><td><b>{100 * overall_ratio:.1f}%</b></td><td></td></tr>")
    h.append("</table>")
    h.append(f"<div class='note'><b>这是本次评估最反直觉的结论</b>："
             f"位逐位无损的画布（{lossless_pct:.1f}% 个、{100 * lossless_byte_share:.0f}% 体积）"
             f"只能省 {100 * (1 - ll_ratio):.1f}%——它们的低 4 位是高 4 位的复制，"
             f"zlib 早就把这层冗余吃掉了；而会掉色的画布能省 {100 * (1 - cl_ratio):.1f}%，"
             f"因为被丢掉的那 4 位正是它的信息量所在。<br>"
             f"换算到全客户端：<b>只转无损子集约省 {mb(lossless_only_save)}，画质零风险；"
             f"全量约省 {mb(saved_lo)}~{mb(saved_hi)}（客户端 6.71 GB 的 "
             f"{100 * saved_lo / full['clien_img_bytes']:.0f}~"
             f"{100 * saved_hi / full['clien_img_bytes']:.0f}%），"
             f"代价是那 {100 - lossless_pct:.1f}% 的画布掉色。</b></div>")

    h.append("<h3>按目录（收益从大到小）</h3>")
    h.append("<table><tr><th>分类</th><th>含 8888 画布</th><th>8888 载荷</th><th>4444 后</th>"
             "<th>比值</th><th>可省</th><th>位逐位无损（按体积）</th><th>会掉色（按体积）</th></tr>")
    for x in rows:
        ll = x["ll"]
        bar = f"<span class='meter' style='width:{max(2, ll * 0.9):.0f}px'></span>"
        h.append(f"<tr><td><code>{esc(x['cat'])}</code></td><td>{x['f2']:,}</td>"
                 f"<td>{mb(x['pay'])}</td><td>{mb(x['pay'] * x['ratio'])}</td>"
                 f"<td>{100 * x['ratio']:.0f}%</td><td>{mb(x['saved'])}</td>"
                 f"<td>{bar} {ll:.0f}%</td>"
                 f"<td class='{'v-bad' if x['loss'] > 40 else ''}'>{x['loss']:.0f}%</td></tr>")
    h.append(f"<tr><td><b>合计</b></td><td><b>{tot_8888:,}</b></td><td><b>{mb(pay8888)}</b></td>"
             f"<td><b>{mb(pay8888 * overall_ratio)}</b></td>"
             f"<td><b>{100 * overall_ratio:.0f}%</b></td><td><b>{mb(saved_lo)}</b></td>"
             f"<td colspan=2></td></tr>")
    h.append("</table>")
    h.append("<div class='note'>收益最大的两个正好是掉色最重的两个："
             "<code>Character/Weapon</code>（842 MB，约 43% 体积会掉色）与 "
             "<code>Character/Cap</code>（297 MB，约 59% 会掉色）。"
             "而 <code>Effect</code>(89%)、<code>UI</code>(93%)、<code>Character/Hair</code>(99%) "
             "几乎全是掉色——头发渐变、UI 描边、光效 logo 正是 4 bit 通道最不友好的内容。</div>")

    h.append("<h2>2. 画质：平均误差很小，但集中在最显眼的地方</h2>")
    h.append(f"<table><tr><th>指标（抽样 {px / 1e6:.0f} M 像素）</th><th>实测</th></tr>"
             f"<tr><td>RGB 平均绝对误差</td><td>{rgb_mae:.2f} / 255</td></tr>"
             f"<tr><td>单像素 RGB 最大误差</td><td>{rgb_max} / 255（≈6%）</td></tr>"
             f"<tr><td>alpha 平均绝对误差</td><td>{a_mae:.2f} / 255</td></tr>"
             f"<tr><td>alpha 被改动的像素占比</td><td>{a_changed:.1f}%</td></tr></table>")
    h.append(f"<div class='note'>平均误差之所以小，是因为 {lossless_pct:.1f}% 的画布本来就无损。"
             f"一旦落到剩下 {100 - lossless_pct:.1f}% 上，误差就是 {rgb_max}/255 的硬量化台阶，"
             "在渐变、抗锯齿描边、半透明阴影上表现为可见色带与色阶断裂。</div>")
    h.append("<h3>误差分布（按目录，像素最多的 14 个）</h3>")
    h.append("<table><tr><th>分类</th><th>像素</th><th>RGB 平均</th><th>RGB 最大</th>"
             "<th>alpha 平均</th><th>alpha 改变</th></tr>")
    for k, e in sorted(errors.items(), key=lambda kv: -kv[1].get("px", 0))[:14]:
        if not e.get("px"):
            continue
        h.append(f"<tr><td><code>{esc(k)}</code></td><td>{e['px'] / 1e6:.1f} M</td>"
                 f"<td>{e['rgb'] / max(e['px'] * 3, 1):.2f}</td><td>{e['rgbmax']}</td>"
                 f"<td>{e['a'] / max(e['px'], 1):.2f}</td>"
                 f"<td>{100 * e['a_changed'] / max(e['px'], 1):.2f}%</td></tr>")
    h.append("</table>")

    h.append("<h2>3. 工程障碍（与画质无关，但决定能不能落地）</h2>")
    h.append("<h3>3.1 变长替换会被工具链拒绝</h3>")
    h.append(f"<div class='verdict'>对 {st['probe1_variable_length_refusal']['sample']} 个随机文件里"
             "第一个 8888 画布，用现成的增量补丁器做「把记录替换成它自己」——"
             "变长替换里最温和的情形："
             f"接受 {p1.get('accepted', 0)} 个、拒绝 {refused} 个（<b>{refuse_pct:.0f}%</b>）。"
             "拒绝信息是 <code>string reference at 0x… points into replaced bytes</code>："
             "有别的记录的字符串引用指向这段字节，缩短它会产生悬空指针，"
             "补丁器选择报错而不是写出坏文件。被拒的全部落在 <code>Character/</code> 装备上。</div>")
    h.append("<table><tr><th>探测结果</th><th>文件数</th></tr>")
    for k, v in sorted(p1.items(), key=lambda kv: -kv[1]):
        h.append(f"<tr><td><code>{esc(k)}</code></td><td>{v}</td></tr>")
    h.append("</table>")
    if st["probe1_variable_length_refusal"].get("by_top_dir"):
        h.append("<div class='note'>按顶层目录：" + " ".join(
            f"<code>{esc(k)}</code>={esc(dict(v))}"
            for k, v in st["probe1_variable_length_refusal"]["by_top_dir"].items()) + "</div>")

    h.append("<h3>3.2 唯一结构上安全的路线：等长原地载荷补丁</h3>")
    h.append("<div class='verdict ok'>把载荷区域<b>原地</b>覆盖成同样长度的字节："
             "文件长度不变、不触碰任何 size 字段、不需要重定位任何字符串引用。"
             f"在 {len(p2)} 个文件上实测：改动字节全部落在载荷区间内、长度不变、重解析无告警。</div>")
    h.append("<table><tr><th>文件</th><th>画布</th><th>载荷区间</th><th>改动字节</th>"
             "<th>全在载荷内</th><th>长度不变</th><th>重解析干净</th></tr>")
    for x in p2:
        def ok(b):
            return "<span class='v-ok'>✓</span>" if b else "<span class='v-bad'>✗</span>"
        h.append(f"<tr><td><code>{esc(x['file'])}</code></td><td>{esc(x['canvas'])}</td>"
                 f"<td>[{x['payload_offset']}, {x['payload_offset'] + x['payload_len']})</td>"
                 f"<td>{x['changed_bytes']:,}</td><td>{ok(x['all_inside_payload'])}</td>"
                 f"<td>{ok(x['length_unchanged'])}</td><td>{ok(x['reparses_clean'])}</td></tr>")
    h.append("</table>")
    h.append("<div class='verdict warn'><b>但这条路有一个仓库内无证据的假设</b>："
             "4444 载荷压缩后通常更短，等长要求把剩余字节补 0。"
             "客户端 zlib 解码器是否容忍流结束后的填充字节，本仓库无法验证——"
             "<b>必须在实机上先试一个文件，不能假设。</b></div>")

    h.append("<h3>3.3 载荷里藏着一个「一倍零平面」</h3>")
    h.append(f"<div class='verdict warn'>抽样 {ratio_tot:,} 个 8888 画布的载荷里，"
             f"<b>{x2_pct:.1f}%</b> 解压出来的字节数是 <code>w×h×4</code> 的<b>整整 2 倍</b>，"
             f"多出来的后半段 <b>{tail_zero_pct:.1f}% 全为 0</b>，"
             "客户端只读前 <code>w×h×4</code>。<br>"
             "这段冗余原始数据有几百 MB，但全零数据 zlib 压完几乎没有成本——"
             f"去掉它只回收 {p3['tail_share_of_compressed_pct']:.1f}%。"
             "<b>所以它不是一个可回收空间，而是一个必须理解的坑</b>："
             "任何把载荷当成 2 倍像素来处理的工具都会画错；"
             "<code>decode_canvas</code> 现在“能用”只是因为 PIL 恰好忽略了多余字节。</div>")

    h.append("<h2>4. 建议</h2>")
    h.append("<div class='verdict ok'><b>不要全量。</b>按「收益 ÷ 风险」排序，只做窄子集。</div>")
    h.append("<ul>")
    h.append(f"<li><b>第一优先：只转「位逐位无损」的画布（{lossless_pct:.1f}% 个、"
             f"{100 * lossless_byte_share:.0f}% 体积）。</b>"
             f"像素零变化、可自动判定、无需人眼验收，约省 {mb(lossless_only_save)}。"
             "这是唯一能全程自动化的部分。</li>")
    h.append("<li><b>第二优先（需人眼验收）：<code>Character/Weapon</code> + "
             f"<code>Character/Cap</code></b>，合计可省 {mb(top2_save)}，"
             "但这两块同时是掉色最重的（约 43% / 59% 体积），"
             "必须先截图比对装备外观再决定。</li>")
    h.append("<li><b>不要碰</b>：<code>Item/Install</code>、<code>Map/Tile</code>、"
             "<code>Morph</code>（已 100% 是 4444）、<code>Skill</code>（99% 无损且省得极少）、"
             "<code>Effect</code> / <code>UI</code>（89% / 93% 会掉色，收益还小）。</li>")
    h.append("<li><b>绝对不能碰</b> <code>Skill/</code> 里已按 <code>AGENTS.md</code> "
             "转成 4444 的迁移技能载荷。那是规范红线，<code>format=1, format2=0</code> 必须保住。</li>")
    h.append("<li><b>验证门槛（缺一不可）</b>：① 生成器跑两遍、哈希一致；"
             "② 载荷区间外字节逐字节不变；③ 解析无 <code>truncated</code>、无 "
             "<code>parse_warnings</code>；④ 抽样画布解码出可见像素且尺寸不变；"
             "⑤ <b>真机启动 + 进游戏看装备 / 头发 / 特效 / UI</b>。"
             "前四条仓库里能做，第五条只有你能做。</li>")
    h.append("</ul>")

    h.append("<h2>5. 复现命令</h2>")
    h.append("<table><tr><th>目的</th><th>命令</th></tr>"
             "<tr><td>全客户端普查（约 8 分钟）</td><td><code>"
             "python3 tool/img-inventory/scan_4444_full.py --per-file 8</code></td></tr>"
             "<tr><td>按类别的体积拆分（约 80 秒）</td><td><code>"
             "python3 tool/img-inventory/scan_4444_full.py --per-file 30 "
             "--max-files 6500 --out byclass.json</code></td></tr>"
             "<tr><td>结构安全三探测</td><td><code>"
             "python3 tool/img-inventory/probe_structure.py</code></td></tr>"
             "<tr><td>三种载荷策略体积对比</td><td><code>"
             "python3 tool/img-inventory/test_record_fidelity.py</code></td></tr>"
             "<tr><td>本报告</td><td><code>"
             "python3 tool/img-inventory/render_4444_report.py</code></td></tr>"
             "</table>")
    h.append("</div></body></html>")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(h))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
