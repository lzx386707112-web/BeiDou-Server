#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只保留「可重复副本 / 团本 / Boss 战」，排除一次性剧情/CG/转职/回归教学/纯系统门槛项。

数据：
- /tmp/missing_eval.json：39 候选资源清单
- /tmp/tms_mapnames.json / /tmp/strmap.json：名称比对
- clien/Data/Map/Map*/Map*/*.img：BeiDou 地图集
只读，只写 docs/。
"""
import os, glob, json
ROOT = '/Users/lizixian/Documents/mxd/BeiDou-Server'
os.chdir(ROOT)
OUT = 'docs/可重复副本迁移可行性.html'

# ---------- BeiDou 现有资源 ----------
bd_ids = set()
for p in glob.glob('clien/Data/Map/Map*/Map*/*.img'):
    bd_ids.add(os.path.basename(p)[:-4])
bd_names = json.load(open('/tmp/strmap.json'))
bd_pair = set()
for area in bd_names.get('children', []):
    for m in area.get('children', []):
        d = {c['name']: c.get('value') for c in m.get('children', [])}
        nm = d.get('mapName') or ''
        st = d.get('streetName') or ''
        if nm:
            bd_pair.add((st, nm))

d = json.load(open('/tmp/missing_eval.json'))
clusters = d['clusters']; cands = d['candidates']
tms_names = json.load(open('/tmp/tms_mapnames.json'))
keymap = {}
for c in clusters:
    keymap.setdefault(c['key'], []).extend(c.get('maps', []))

def coverage(cid):
    v = cands[cid]
    maps = set()
    for k in v['keys']:
        if k in keymap:
            maps.update(keymap[k])
    maps = sorted(maps)
    hit_id = [m for m in maps if m in bd_ids]
    hit_name = []
    for m in maps:
        tn = tms_names.get(m, {})
        nm = tn.get('mapName') or ''
        st = tn.get('streetName') or ''
        if (st, nm) in bd_pair or (nm and any(nm == x[0] for x in bd_pair)):
            hit_name.append(m)
    n = len(maps)
    return {'maps': maps, 'n': n, 'cov_id': len(hit_id), 'cov_name': len(hit_name),
            'cov': round(max(len(hit_id), len(hit_name)) / n, 3) if n else 0}
cov = {cid: coverage(cid) for cid in cands}

# ---------- 机制判定（沿用领域知识，J 里 tier 用于卡片着色）----------
J = {
 'bm2_maze':   ('B','传统迷宫 PQ（Black Mage 前哨），靠 reactor 解谜 + 刷怪推进','可完整迁移','机制纯数据驱动，083 完全能表达；但 157 图 + 3056 reactor 体量极大，建议分 4 批交付','量大金矿，最高优先'),
 'dragon_rider':('A','天空地区龍騎士組隊任務（dragonRiderPQ），骑乘 + 阶段战斗','可完整迁移','0 新怪 0 新 NPC——全部复用既有资源，性价比最高','首批，零资源新增'),
 'shammos':    ('A','萬年冰河夏摩斯護送（shammosPQ），护送 + 打怪','可完整迁移','0 新怪 0 新 NPC，复用既有；51 图纯地图迁移','首批，零资源新增'),
 'kenta':      ('A','危險之海健太護送（Kenta_Escort），护送 + boss','可完整迁移','需迁 8 新怪 + 1 NPC；机制传统','第二批'),
 'cwkpq':      ('A','瑪斯特利亞祭壇 CWKPQ 扩展段（cwpqBoss），服务端已有 CWKPQ.js','可完整迁移','0 新怪 0 新 NPC，只补 boss 段 18 图','首批，已有脚本'),
 'kerning':    ('A','第一次同行 KerningPQ 重製段，阶段解谜','可完整迁移','仅需 1 新怪 + 2 NPC','首批'),
 'giant_boss': ('B','瑪斯特利亞巨型 Boss 培羅德（GiantBossField），多阶段 Boss 战','可完整迁移','需迁 17 新怪（含 Boss）；传统 Boss 机制，招式/掉落自配','第三批'),
 'fairy':      ('A','妖精學院（fairyAcademy），学院小游戏 + 刷怪','可完整迁移','需 3 怪 + 5 NPC；机制传统','第二批'),
 'yumyum':     ('A','嚼嚼艾爾蘭 / 啾啾島（yumyum/hungryMuto），喂养小游戏 + 刷怪','可完整迁移','需 7 新怪；机制传统','第二批'),
 'fishing':    ('C','釣魚王小遊戲（fishingKing），钓鱼 minigame','部分可迁','minigame 需输入交互，083 无对应钓鱼 UI；地图/怪可迁，玩法核心需自写','可选，低优先'),
 'tangyoon':   ('C','湯寶寶烹飪小遊戲（tangyoon），料理 minigame','部分可迁','烹饪 minigame 需交互 UI；地图可迁，玩法需自写','可选，低优先'),
 'arena':      ('A','怪物競技戰場（monsterArena），擂台刷怪','可完整迁移','仅需 1 新怪；传统','第二批'),
 'rootabyss_garden':('A','露塔必思庭園（rootabyssGarden），花园探索 + reactor','可完整迁移','需 4 怪 + 4 NPC + 22 reactor；传统','第二批'),
 'viking':     ('A','維京飛行船（flowervioleta），骑乘飞行图','可完整迁移','0 新怪 0 新 NPC，纯地图','首批'),
 'escort_past':('A','護衛哈沙勒 納希綠洲城（escortPast），护送','可完整迁移','需 2 新怪；传统','第二批'),
 'neotokyo':   ('B','新東京 / 日本區系列，地区 Boss + 刷怪（含日拳/战国/歌舞伎）','部分可迁','88 图 + 27 怪 + 28 NPC 体量大；多为传统机制，但 nohime 章节(故事)需排除，仅 Boss/刷怪段可迁','量大，后期批次'),
 'bosses':     ('C','單體 Boss 图（戴米安/麥格納斯/拉圖斯/貝倫/希拉/敦凱爾）','部分可迁','麥格納斯/戴米安/維倫是 273 阶段 Boss（专属 phase UI）；papulatus/hillah/dunkel 较传统可数据化；整体 273 阶段机制缺失','按传统 Boss 自配'),
 'spinoff':    ('A','皇家神獸學院（spinOffPark），校园小游戏 + 刷怪','可完整迁移','需 9 新怪；机制传统','第二批'),
 'helisium':   ('A','赫力席母奪回戰（Helisium），攻城战 PQ','可完整迁移','需 10 怪 + 2 NPC；传统攻城机制','第三批'),
 'bat_storm':  ('A','蝙蝠群 / 暴風雨森林（batField/stormField），区域刷怪事件','可完整迁移','需 3 怪 + 6 NPC；传统','第二批'),
 'ep3':        ('A','耶雷弗奪還戰 / 全力突破（Episode3），地区战争','可完整迁移','需 6 新怪；传统战争机制','第三批'),
 'murumuru':   ('A','米尼姆勒護送（Murumuru_Escort），护送','可完整迁移','需 6 新怪；传统','第二批'),
 'treasure':   ('C','魔物藏寶城小遊戲（multigame），藏宝 minigame','部分可迁','minigame 需交互 UI；地图/怪可迁，玩法需自写','可选，低优先'),
 'flag':       ('A','旗幟爭奪戰（flag），夺旗 PvP 小游戏','可完整迁移','仅需 1 NPC；传统 capture-flag','第二批'),
 'mukhyun':    ('A','玄山派 武陵桃園（Wz2_Mukhyun），门派/武神区域，可重复刷','可完整迁移','需 8 NPC（无新怪）；传统，但 key 含 story 需核实 Boss 段是否纯重复','第三批（机制核实）'),
 'treglo':     ('A','狂躁的實驗室（treglo），实验场刷怪','可完整迁移','仅需 1 NPC；传统','第二批'),
 'colossus':   ('DONE','岩壁巨人 克洛宿斯 — 已单独出报告（还原度≈85%）','已分析','见 docs/岩壁巨人与紅月之森-迁移评估.html','详另报'),
}

# ---------- 可重复性归类（本次新增过滤）----------
# rep = 可重复副本/团本/Boss战（聚焦对象）；mini = 可重复小游戏（轻量，非副本）
# once = 一次性剧情/CG/转职/教学；sys = 需 273 专属系统/神秘河数值
REPEAT = {
 'bm2_maze':'rep','dragon_rider':'rep','shammos':'rep','kenta':'rep','cwkpq':'rep',
 'kerning':'rep','giant_boss':'rep','fairy':'rep','yumyum':'rep','arena':'rep',
 'colossus':'rep','rootabyss_garden':'rep','viking':'rep','escort_past':'rep',
 'bosses':'rep','spinoff':'rep','helisium':'rep','bat_storm':'rep','ep3':'rep',
 'murumuru':'rep','treglo':'rep','mukhyun':'rep','neotokyo':'rep',
 'fishing':'mini','tangyoon':'mini','treasure':'mini','flag':'mini',
 'elodin':'once','dim_invade':'once','blackheaven':'once','hofm':'once',
 'dim_library':'once','m4_job':'once','comeback':'once',
 'evolve':'sys','cernium':'sys','arcana':'sys','mystic':'sys','karotte':'sys',
}
# 排除原因
EXC_REASON = {
 'elodin':'一次性剧情：10108 段（埃羅汀/露安的家）属 Ereve 骑士团叙事，不可反复刷',
 'dim_invade':'一次性 CG：94002 段含「希拉 VS 梅格耐斯」隐藏阶段，是黑色天堂电影化收尾',
 'blackheaven':'一次性 CG：Blockbuster 章节电影化，依赖 273 演出 UI + 章节脚本',
 'hofm':'一次性 CG：楓葉英雄 Act 电影化副本，依赖 273 演出 UI',
 'dim_library':'一次性叙事：次元圖書館章节副本，需专属叙事 UI + 章节系统',
 'm4_job':'一次性：耶雷弗庭院四轉任務，转职流程只做一次',
 'comeback':'一次性：回歸勇士修練場，回归玩家引导教学，不可反复刷',
 'evolve':'系统门槛：進化系統需整套进化状态机 + 专属 UI，083/服务端均无',
 'cernium':'系统门槛：神秘河后段需 arcaneforce 数值体系，服务端零命中',
 'arcana':'系统门槛：阿爾卡納属神秘河后段，需 arcaneforce 数值体系',
 'mystic':'系统门槛：神秘戰地需 273 mystic field 系统，服务端无',
 'karotte':'系统门槛：卡羅泰 993165 段（Limen 亞空間，fieldType 292/296）属神秘河后段，需 arcaneforce',
}

def e(s): return str(s if s is not None else '')

CSS = """
:root{--bg:#0f1116;--panel:#171a21;--panel2:#1d2129;--line:#2a2f3a;--tx:#e6e9ef;--tx2:#98a1b3;
--acc:#e05c5c;--acc2:#63b3ed;--ok:#5fbf85;--warn:#f0b95e;--pur:#b392f0;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.75 -apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,sans-serif;}
.wrap{max-width:1280px;margin:0 auto;padding:30px 20px 90px;}
h1{font-size:24px;margin:0 0 6px;}
h2{font-size:19px;margin:38px 0 14px;border-left:3px solid var(--acc);padding-left:10px;}
h3{font-size:15px;margin:22px 0 8px;color:var(--acc2);}
.sub{color:var(--tx2);font-size:13px;margin-bottom:16px;line-height:1.9;}
code{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#d5b06a;background:var(--panel2);padding:1px 5px;border-radius:5px;}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(370px,1fr));gap:14px;margin:14px 0;}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px;display:flex;flex-direction:column;}
.card h3{margin:0 0 4px;font-size:15px;color:var(--tx);}
.card .mech{color:var(--tx2);font-size:12.5px;margin:4px 0 8px;min-height:34px;}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 8px;}
.chip{font-size:11px;padding:2px 8px;border-radius:16px;background:var(--panel2);border:1px solid var(--line);color:var(--tx2);}
.chip b{color:var(--tx);}
.tag{font-size:11px;padding:2px 9px;border-radius:20px;border:1px solid var(--line);color:var(--tx2);white-space:nowrap;display:inline-block;margin-bottom:6px;}
.tag.ok{border-color:#3d5140;color:#8fd6a2;background:#16211a;}
.tag.part{border-color:#5a4a3b;color:#e6b98f;background:#241f17;}
.tag.no{border-color:#5a3a3a;color:#e69191;background:#241a1c;}
.tag.done{border-color:#3a4a5a;color:#9fc7e6;background:#16202a;}
.tag.rep{border-color:#3a4a5a;color:#9fc7e6;background:#16202a;}
.tag.mini{border-color:#4a4a3a;color:#d3d39f;background:#202016;}
.bar{height:8px;border-radius:5px;background:var(--panel2);overflow:hidden;margin:6px 0 4px;}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#3d7d52,#5fbf85);}
.bar.warn i{background:linear-gradient(90deg,#7d6a3d,#f0b95e);}
.bar.no i{background:linear-gradient(90deg,#7d3d3d,#e69191);}
.cov{font-size:11.5px;color:var(--tx2);}
.judge{font-size:12.5px;color:var(--tx2);margin-top:6px;line-height:1.7;}
.judge b{color:var(--tx);}
.rec{font-size:12px;color:var(--warn);margin-top:6px;}
.note{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 18px;color:var(--tx2);font-size:13px;margin:12px 0;}
.note b{color:var(--tx);}
.key{border-radius:12px;padding:14px 18px;margin:14px 0;background:var(--panel2);border:1px solid var(--line);}
.key b{color:var(--acc2);}
table{width:100%;border-collapse:collapse;margin:10px 0 6px;font-size:12.5px;}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top;}
th{color:var(--tx2);font-weight:600;font-size:11.5px;background:var(--panel);}
tr:hover td{background:#1a1e26;}
.mono{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;}
ul{margin:8px 0 8px 18px;padding:0;} li{margin:5px 0;}
"""

H = []
H.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">')
H.append('<title>可重复副本迁移可行性（TMS→BeiDou）</title><style>%s</style></head><body><div class="wrap">' % CSS)
H.append('<h1>可重复副本迁移可行性 —— 只保留能反复刷的</h1>')
H.append('<div class="sub">对象：TMS 273 客户端　对照：BeiDou 客户端 + 服务端。<br>'
 '本次<b>只筛「可重复副本 / 团本 / Boss 战」</b>：能反复进入、靠机制（解谜/护送/攻城/Boss 阶段）提供可玩性；'
 '<b>一次性剧情 / CG 演出 / 转职 / 回归教学 / 纯 273 系统门槛</b>一律排除（可玩性不高）。<br>'
 '资源清单来自上次实测扫描，BeiDou 覆盖率按<b>地图 ID + 中文地图名双口径</b>现场计算。'
 '判定维度：① 机制 083 老端能否表达；② 是否依赖 273 专属 UI / 神秘河数值；③ 数据可得性。</div>')

rep_ids   = [c for c in cands if REPEAT[c]=='rep']
mini_ids  = [c for c in cands if REPEAT[c]=='mini']
once_ids  = [c for c in cands if REPEAT[c]=='once']
sys_ids   = [c for c in cands if REPEAT[c]=='sys']
feas = [c for c in rep_ids if J[c][0] in ('A','B')]
part = [c for c in rep_ids if J[c][0]=='C']
done = [c for c in rep_ids if J[c][0]=='DONE']
H.append('<div class="note"><b>总览（39 候选 → 过滤后）：</b>'
 f'可重复副本（聚焦）<b>{len(rep_ids)}</b> 个（其中可完整迁移 A/B <b>{len(feas)}</b>、部分可迁 C <b>{len(part)}</b>、已另报 <b>{len(done)}</b>）；'
 f'可重复小游戏 <b>{len(mini_ids)}</b> 个（轻量，非副本）；'
 f'排除：一次性 <b>{len(once_ids)}</b> 个 + 系统门槛 <b>{len(sys_ids)}</b> 个。</div>')

def card(cid):
    tier, mech, verdict, judge, rec = J[cid]
    v = cands[cid]; c = cov[cid]
    tagcls = {'A':'ok','B':'ok','C':'part','X':'no','DONE':'done'}[tier]
    vtxt = {'A':'可完整迁移','B':'可完整迁移','C':'部分可迁','X':'不可迁','DONE':'已分析'}[tier]
    barcls = '' if tier in ('A','B') else ('warn' if tier=='C' else 'no')
    badge = '<span class="tag rep">可重复副本</span>' if REPEAT[cid]=='rep' else '<span class="tag mini">可重复小游戏</span>'
    return f'''<div class="card">
<h3>{e(v['name'])}</h3>
{badge}<span class="tag {tagcls}">{vtxt}</span>
<div class="mech">{e(mech)}</div>
<div class="chips">
<span class="chip">地图 <b>{c['n']}</b></span>
<span class="chip">新怪 <b>{v.get('new_mobs',0)}</b></span>
<span class="chip">新NPC <b>{v.get('new_npcs',0)}</b></span>
<span class="chip">reactor <b>{v.get('reactors',0)}</b></span>
</div>
<div class="bar {barcls}"><i style="width:{int(c['cov']*100)}%"></i></div>
<div class="cov">BeiDou 覆盖率：{c['cov_id']}/{c['n']} 图 ID 命中，{c['cov_name']}/{c['n']} 名称命中 → <b>{int(c['cov']*100)}%</b></div>
<div class="judge"><b>判定：</b>{e(judge)}</div>
<div class="rec">▸ 建议：{e(rec)}</div>
</div>'''

H.append('<h2>一、可重复副本 / 团本 / Boss 战（聚焦对象）</h2>')
H.append('<h3>1.1 可完整迁移（A/B 档 · 传统机制，083 老端能表达）</h3>')
H.append('<div class="cards">')
for cid in sorted(feas, key=lambda x: (J[x][0], -cands[x].get('new_mobs',0))):
    H.append(card(cid))
H.append('</div>')

if part:
    H.append('<h3>1.2 部分可迁（C 档 · 需新系统/273 UI 局部，玩法核心需自写）</h3>')
    H.append('<div class="cards">')
    for cid in part:
        H.append(card(cid))
    H.append('</div>')

if done:
    H.append('<h3>1.3 已单独出报告的案例</h3>')
    H.append('<div class="cards">')
    for cid in done:
        H.append(card(cid))
    H.append('</div>')

H.append('<h2>二、可重复小游戏（轻量，非副本，按需）</h2>')
H.append('<div class="cards">')
for cid in mini_ids:
    H.append(card(cid))
H.append('</div>')

# 全量对比表（聚焦 + 小游戏）
H.append('<h2>三、聚焦全量对比表</h2>')
H.append('<table><tr><th>名称</th><th>类别</th><th>档</th><th>结论</th><th>地图</th><th>新怪</th><th>新NPC</th>'
 '<th>reactor</th><th>覆盖率</th><th>机制 / 缺口</th></tr>')
order = feas + part + done + mini_ids
for cid in order:
    tier, mech, verdict, judge, rec = J[cid]
    v = cands[cid]; c = cov[cid]
    td = {'A':'<span class="tag ok">A</span>','B':'<span class="tag ok">B</span>','C':'<span class="tag part">C</span>','X':'<span class="tag no">X</span>','DONE':'<span class="tag done">已报</span>'}[tier]
    vt = {'A':'可完整迁移','B':'可完整迁移','C':'部分可迁','X':'不可迁','DONE':'已分析'}[tier]
    cat = '副本' if REPEAT[cid]=='rep' else '小游戏'
    H.append(f'<tr><td>{e(v["name"])}</td><td>{cat}</td><td>{td}</td><td>{vt}</td>'
     f'<td class="mono">{c["n"]}</td><td class="mono">{v.get("new_mobs",0)}</td><td class="mono">{v.get("new_npcs",0)}</td>'
     f'<td class="mono">{v.get("reactors",0)}</td><td class="mono">{int(c["cov"]*100)}%</td>'
     f'<td>{e(judge)}</td></tr>')
H.append('</table>')

H.append('<div class="key"><h3>推荐迁移顺序（仅可重复副本）</h3><ul>'
 '<li><b>首批（零资源新增，性价比最高）：</b>龍騎士組隊、夏摩斯護送、CWKPQ 扩展段、第一次同行、維京飛行船。</li>'
 '<li><b>第二批（少量新怪/NPC）：</b>健太護送、妖精學院、嚼嚼/啾啾島、怪物競技、露塔必思庭園、護衛哈沙勒、皇家神獸學院、蝙蝠群/暴風雨、米尼姆勒、旗幟爭奪、狂躁實驗室、岩壁巨人(已报)。</li>'
 '<li><b>第三批（体量大/多新怪）：</b>培羅德(17怪)、赫力席母奪回戰(10怪)、耶雷弗奪還戰、玄山派(机制核实)、苦痛迷宮(157图·分4批)、新東京(88图·后期,仅Boss/刷怪段)。</li>'
 '<li><b>按传统 Boss 自配：</b>單體 Boss 图（戴米安/麥格納斯/拉圖斯/貝倫/希拉/敦凱爾，273 阶段 UI 缺失，数据化部分可迁）。</li>'
 '<li><b>可选小游戏：</b>釣魚王、湯寶寶、魔物藏寶城（需自写交互 UI）。</li>'
 '</ul></div>')

# 排除附录
H.append('<h2>四、已排除项（一次性 / 系统门槛，可玩性不高）</h2>')
H.append('<table><tr><th>名称</th><th>类别</th><th>排除原因</th></tr>')
for cid in once_ids:
    H.append(f'<tr><td>{e(cands[cid]["name"])}</td><td>一次性</td><td>{e(EXC_REASON.get(cid,"—"))}</td></tr>')
for cid in sys_ids:
    H.append(f'<tr><td>{e(cands[cid]["name"])}</td><td>系统门槛</td><td>{e(EXC_REASON.get(cid,"—"))}</td></tr>')
H.append('</table>')

H.append('<div class="note">剔除的 12 项里，5 项在上一份「逐案分析」里曾被误判为可迁（露安的家、穿越次元的戰場、卡羅泰、四轉任務、回歸修練場）——'
 '本次按「只保留可重复」口径纠正：前 2 项属黑色天堂/Ereve 一次性 CG 剧情，卡羅泰属神秘河后段需 arcaneforce，四轉与回歸是一次性流程。<br>'
 '数据来源：<code>/tmp/missing_eval.json</code> + <code>clien/Data/Map</code> + 中文树 <code>String/Map.img</code>。'
 '生成脚本：<code>tool/scripts/migration/render_repeatable_dungeons.py</code>（只读，未改动任何文件）。</div>')
H.append('</div></body></html>')

open(OUT, 'w').write('\n'.join(H))
print('written', OUT, os.path.getsize(OUT), 'bytes')
print('rep=%d(可迁%d/部分%d/已报%d) mini=%d once=%d sys=%d'
      % (len(rep_ids), len(feas), len(part), len(done), len(mini_ids), len(once_ids), len(sys_ids)))
