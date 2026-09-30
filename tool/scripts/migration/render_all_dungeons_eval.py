#!/usr/bin/env python3
"""逐案分析 TMS 其余具名副本/活动能否完整迁移到 BeiDou。

数据：
- /tmp/missing_eval.json：39 候选的资源清单（地图数 / 新怪 / 新 NPC / reactor / 街道）
- /tmp/tms_mapnames.json：TMS 地图名（繁体）
- /tmp/strmap.json：BeiDou 现有地图名（中文树 String/Map）
- clien/Data/Map/Map*/：BeiDou 现有地图 ID 集合
只读，只写 docs/。
"""
import os, glob, json
ROOT = '/Users/lizixian/Documents/mxd/BeiDou-Server'
os.chdir(ROOT)
OUT = 'docs/副本迁移可行性逐案分析.html'

# ---------- BeiDou 现有资源 ----------
bd_ids = set()
for p in glob.glob('clien/Data/Map/Map*/Map*/*.img'):
    bd_ids.add(os.path.basename(p)[:-4])
bd_names = json.load(open('/tmp/strmap.json'))   # BeiDou 中文树地图名
bd_pair = set()
for area in bd_names.get('children', []):
    for m in area.get('children', []):
        d = {c['name']: c.get('value') for c in m.get('children', [])}
        nm = d.get('mapName') or ''
        st = d.get('streetName') or ''
        if nm:
            bd_pair.add((st, nm))

# ---------- TMS 数据 ----------
d = json.load(open('/tmp/missing_eval.json'))
clusters = d['clusters']
cands = d['candidates']
tms_names = json.load(open('/tmp/tms_mapnames.json'))

keymap = {}
for c in clusters:
    keymap.setdefault(c['key'], []).extend(c.get('maps', []))

# ---------- 每个候选归集地图 + 覆盖率 ----------
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
    return {
        'maps': maps, 'n': n,
        'cov_id': len(hit_id), 'cov_name': len(hit_name),
        'cov': round(max(len(hit_id), len(hit_name)) / n, 3) if n else 0,
    }

cov = {cid: coverage(cid) for cid in cands}

# ---------- 机制判定（领域知识编码）----------
# tier: A=可完整迁移(高价值/传统), B=可迁但量大或需自写脚本, C=部分可迁(需新系统/273UI局部), X=不可迁/排除
# verdict: 可完整迁移 / 部分可迁 / 不可迁
J = {
 'bm2_maze':   ('B','传统迷宫 PQ（Black Mage 前哨），靠 reactor 解谜 + 刷怪推进','可完整迁移','机制纯数据驱动，083 完全能表达；但 157 图 + 3056 reactor 体量极大，建议分 4 批交付','量大，排最高优先级金矿'),
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
 'evolve':     ('X','進化系統（evolvingsystem），局内进化 + buff 装配','不可迁','需整套进化状态机 + 专属 UI，083/服务端均无；客户端无 .js','排除'),
 'rootabyss_garden':('A','露塔必思庭園（rootabyssGarden），花园探索 + reactor','可完整迁移','需 4 怪 + 4 NPC + 22 reactor；传统','第二批'),
 'viking':     ('A','維京飛行船（flowervioleta），骑乘飞行图','可完整迁移','0 新怪 0 新 NPC，纯地图','首批'),
 'elodin':     ('A','露安的家（elodin），家园 + 18 reactor','可完整迁移','需 4 新怪；传统','第二批'),
 'dim_invade': ('A','穿越次元的戰場（dimensionInvade），战场刷怪','可完整迁移','仅需 1 NPC；体量小','第二批'),
 'escort_past':('A','護衛哈沙勒 納希綠洲城（escortPast），护送','可完整迁移','需 2 新怪；传统','第二批'),
 'neotokyo':   ('B','新東京 / 日本區系列（gabuki/sengoku/nohime），地区 Boss + 刷怪','可完整迁移','88 图 + 27 怪 + 28 NPC 体量大，但多为传统机制（日拳内容早于 273）；ninja 城演出局部需简化','量大，后期批次'),
 'blackheaven':('X','黑色天堂 Blockbuster（blackheavenCG/BM*_mParkAllkill），剧情电影化副本','不可迁','依赖 CG 演出 UI + 章节脚本，083 端无对应；客户端无 .js','排除（剧情演出）'),
 'cernium':    ('X','神秘河後段（賽爾尼溫/魔菈斯/艾斯佩拉/奧迪溫/卡爾西溫），arcaneforce 区域','不可迁','服务端全库 arcaneForce/authenticForce = 0 命中，神秘河后段数值体系缺失','排除（需新数值系统）'),
 'hofm':       ('X','楓葉英雄系列（act4 museum 等），Blockbuster 电影化副本','不可迁','依赖 CG 演出 UI + 章节脚本；客户端无 .js','排除（剧情演出）'),
 'bosses':     ('C','單體 Boss 图（戴米安/麥格納斯/拉圖斯/貝倫/希拉/敦凱爾）','部分可迁','麥格納斯/戴米安/維倫是 273 阶段 Boss（专属 phase UI）；papulatus/hillah/dunkel 较传统可数据化；整体 273 阶段机制缺失','部分可迁，按传统 Boss 自配'),
 'arcana':     ('X','阿爾卡納 / 尖耳狐狸村支線，arcaneforce 区域','不可迁','同上，神秘河后段数值体系缺失','排除（需新数值系统）'),
 'spinoff':    ('A','皇家神獸學院（spinOffPark），校园小游戏 + 刷怪','可完整迁移','需 9 新怪；机制传统','第二批'),
 'dim_library':('X','次元圖書館（demensionLibrary），章节叙事副本','不可迁','需专属叙事 UI + 章节系统；客户端无 .js','排除（需新系统）'),
 'helisium':   ('A','赫力席母奪回戰（Helisium），攻城战 PQ','可完整迁移','需 10 怪 + 2 NPC；传统攻城机制','第三批'),
 'mystic':     ('X','神秘戰地（mysticField），273 专属刷怪场系统','不可迁','需 273 mystic field 系统；服务端无','排除（需新系统）'),
 'bat_storm':  ('A','蝙蝠群 / 暴風雨森林（batField/stormField），区域刷怪事件','可完整迁移','需 3 怪 + 6 NPC；传统','第二批'),
 'ep3':        ('A','耶雷弗奪還戰 / 全力突破（Episode3），地区战争','可完整迁移','需 6 新怪；传统战争机制','第三批'),
 'murumuru':   ('A','米尼姆勒護送（Murumuru_Escort），护送','可完整迁移','需 6 新怪；传统','第二批'),
 'treasure':   ('C','魔物藏寶城小遊戲（multigame），藏宝 minigame','部分可迁','minigame 需交互 UI；地图/怪可迁，玩法需自写','可选，低优先'),
 'flag':       ('A','旗幟爭奪戰（flag），夺旗 PvP 小游戏','可完整迁移','仅需 1 NPC；传统 capture-flag','第二批'),
 'karotte':    ('A','卡羅泰 亞空間（Karotte），空间解谜','可完整迁移','需 3 新怪；传统','第二批'),
 'mukhyun':    ('A','玄山派 武陵桃園支線（Wz2_Mukhyun），门派任务','可完整迁移','需 8 NPC（无新怪）；传统','第三批'),
 'm4_job':     ('A','耶雷弗庭院四轉任務（m4_jobQuest），四转任务','可完整迁移','083 已有四转体系，仅需 1 新怪；传统','第二批'),
 'treglo':     ('A','狂躁的實驗室（treglo），实验场刷怪','可完整迁移','仅需 1 NPC；传统','第二批'),
 'comeback':   ('A','回歸勇士修練場（comebackTuto），回归教学','可完整迁移','需 7 NPC（无新怪）；传统教学','第二批'),
 'colossus':   ('DONE','岩壁巨人 克洛宿斯 — 已单独出报告','已分析','见 docs/岩壁巨人与紅月之森-迁移评估.html','详另报'),
}

def e(s): return str(s if s is not None else '')

# ---------- CSS ----------
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
H.append('<title>副本迁移可行性 — 逐案分析（TMS→BeiDou）</title><style>%s</style></head><body><div class="wrap">' % CSS)
H.append('<h1>副本 / 活动迁移可行性 —— 逐案分析</h1>')
H.append('<div class="sub">对象：TMS 273 客户端 <code>~/Documents/mxd/TMS/</code>　对照：BeiDou 客户端 <code>clien/Data</code> + 服务端。<br>'
 '范围：<b>39 个具名副本/活动</b>（岩壁巨人、紅月之森已单独出报告，本篇含其余 37 个逐案判定 + 二者汇总）。'
 '资源清单来自上次实测扫描（地图/新怪/新 NPC/reactor），BeiDou 覆盖率按 <b>地图 ID + 中文地图名双口径</b> 现场计算。'
 '判定维度：① 机制是否 083 老端能表达；② 是否依赖 273 专属 UI / 新数值系统（arcaneforce）/ 剧情电影化演出；③ 数据可得性。</div>')

# 统计
feas = [c for c in J if J[c][0] in ('A','B')]
part = [c for c in J if J[c][0]=='C']
excl = [c for c in J if J[c][0]=='X']
done = [c for c in J if J[c][0]=='DONE']
H.append('<div class="note"><b>总览：</b>'
 f'可完整迁移（A/B 档）<b>{len(feas)}</b> 个　·　部分可迁（C 档）<b>{len(part)}</b> 个　·　不可迁/排除（X 档）<b>{len(excl)}</b> 个　·　已另报 <b>{len(done)}</b> 个。<br>'
 '排除项的三条硬前提：① <code>job.name</code> 最大 id=2218（龙神）→ 2219+ 职业内容全排除；'
 '② 服务端 <code>arcaneForce/authenticForce</code> 零命中 → 神秘河后段（赛尔尼温/魔菈斯/艾斯佩拉/奥迪温/卡尔西温/阿尔卡纳）全排除；'
 '③ 083 老端无法渲染 273 专属 UI（进化/次元图书馆/黑色天堂/枫叶英雄的 CG 演出）。</div>')

# 分档渲染
tier_name = {'A':'一、可完整迁移（A 档 · 传统机制，零或极少新增资源，优先）',
             'B':'二、可完整迁移但体量大（B 档 · 传统机制，需分批）',
             'C':'三、部分可迁（C 档 · 需新系统/273 UI 局部，玩法核心需自写）',
             'X':'四、不可迁 / 排除（X 档 · 273 专属系统/数值/剧情演出）'}

def card(cid):
    tier, mech, verdict, judge, rec = J[cid]
    v = cands[cid]
    c = cov[cid]
    tagcls = {'A':'ok','B':'ok','C':'part','X':'no','DONE':'done'}[tier]
    vtxt = {'A':'可完整迁移','B':'可完整迁移','C':'部分可迁','X':'不可迁','DONE':'已分析'}[tier]
    barcls = '' if tier in ('A','B') else ('warn' if tier=='C' else 'no')
    bd = v.get('bd_cov', c['cov'])
    return f'''<div class="card">
<h3>{e(v['name'])}</h3>
<span class="tag {tagcls}">{vtxt}</span>
<div class="mech">{e(mech)}</div>
<div class="chips">
<span class="chip">地图 <b>{c['n']}</b></span>
<span class="chip">新怪 <b>{v.get('new_mobs',0)}</b></span>
<span class="chip">新NPC <b>{v.get('new_npcs',0)}</b></span>
<span class="chip">reactor <b>{v.get('reactors',0)}</b></span>
</div>
<div class="bar {barcls}"><i style="width:{int(c['cov']*100)}%"></i></div>
<div class="cov">BeiDou 覆盖率（ID/名称口径）：{c['cov_id']}/{c['n']} 图 ID 命中，{c['cov_name']}/{c['n']} 名称命中 → <b>{int(c['cov']*100)}%</b></div>
<div class="judge"><b>判定：</b>{e(judge)}</div>
<div class="rec">▸ 建议：{e(rec)}</div>
</div>'''

for tier in ['A','B','C','X']:
    items = [c for c in J if J[c][0]==tier]
    if not items: continue
    H.append(f'<h2>{tier_name[tier]}</h2>')
    H.append('<div class="cards">')
    for cid in items:
        H.append(card(cid))
    H.append('</div>')

# 已分析
H.append('<h2>五、已单独出报告的案例</h2>')
H.append('<div class="cards">')
for cid in done:
    H.append(card(cid))
H.append('</div>')

# 主对比表
H.append('<h2>六、全量对比表</h2>')
H.append('<table><tr><th>名称</th><th>档</th><th>结论</th><th>地图</th><th>新怪</th><th>新NPC</th>'
 '<th>reactor</th><th>覆盖率</th><th>机制 / 缺口</th></tr>')
order = [c for c in J if J[c][0] in ('A','B')] + [c for c in J if J[c][0]=='C'] + [c for c in J if J[c][0]=='X'] + [c for c in J if J[c][0]=='DONE']
for cid in order:
    tier, mech, verdict, judge, rec = J[cid]
    v = cands[cid]; c = cov[cid]
    td = {'A':'<span class="tag ok">A</span>','B':'<span class="tag ok">B</span>','C':'<span class="tag part">C</span>','X':'<span class="tag no">X</span>','DONE':'<span class="tag done">已报</span>'}[tier]
    vt = {'A':'可完整迁移','B':'可完整迁移','C':'部分可迁','X':'不可迁','DONE':'已分析'}[tier]
    H.append(f'<tr><td>{e(v["name"])}</td><td>{td}</td><td>{vt}</td>'
     f'<td class="mono">{c["n"]}</td><td class="mono">{v.get("new_mobs",0)}</td><td class="mono">{v.get("new_npcs",0)}</td>'
     f'<td class="mono">{v.get("reactors",0)}</td><td class="mono">{int(c["cov"]*100)}%</td>'
     f'<td>{e(judge)}</td></tr>')
H.append('</table>')

H.append('<div class="key"><h3>推荐迁移顺序（仅含可完整迁移档）</h3><ul>'
 '<li><b>首批（零资源新增，性价比最高）：</b>龍騎士組隊、夏摩斯護送、CWKPQ 扩展段、第一次同行、維京飛行船。</li>'
 '<li><b>第二批（需少量新怪/NPC）：</b>健太護送、妖精學院、嚼嚼、怪物競技、露塔必思庭園、露安的家、穿越次元戰場、護衛哈沙勒、皇家神獸學院、蝙蝠群/暴風雨、米尼姆勒、旗幟爭奪、卡羅泰、玄山派(无新怪)、四轉任務、狂躁實驗室、回歸修練場、岩壁巨人(已报)。</li>'
 '<li><b>第三批（体量大/多新怪）：</b>培羅德(17怪)、赫力席母奪回戰(10怪)、耶雷弗奪還戰、苦痛迷宮(157图·分4批)、新東京(88图·后期)。</li>'
 '<li><b>可选（minigame 需自写交互）：</b>釣魚王、湯寶寶、魔物藏寶城。</li>'
 '<li><b>排除：</b>進化系統、黑色天堂、楓葉英雄、神秘河后段(赛尔尼温/魔菈斯/艾斯佩拉/奥迪温/卡尔西温/阿尔卡纳)、次元圖書館、神秘戰地、單體273 Boss(部分)。</li>'
 '</ul></div>')

H.append('<div class="note">数据来源：<code>/tmp/missing_eval.json</code>（39 候选资源清单，来自 TMS 地图 info 全量扫描 + 逐图 life 解析）+ '
 'BeiDou 客户端地图集合 <code>clien/Data/Map/Map*/Map*/*.img</code> + 中文树 <code>String/Map.img</code> 名称比对 + '
 '<code>/tmp/tms_mapnames.json</code>。生成脚本：<code>tool/scripts/migration/render_all_dungeons_eval.py</code>（只读，未改动任何文件）。</div>')
H.append('</div></body></html>')

open(OUT, 'w').write('\n'.join(H))
print('written', OUT, os.path.getsize(OUT), 'bytes')
print('feasible(A/B)=%d  partial(C)=%d  excluded(X)=%d  done=%d' % (len(feas), len(part), len(excl), len(done)))
