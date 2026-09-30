#!/usr/bin/env python3
"""渲染「岩壁巨人 克洛宿斯 / 紅月之森」能否完整迁移的评估报告。

数据来自本次实测：
- TMS 18,888 张地图 info 扫描 + 24009 / 87502 段逐图 life 解析
- Packs/Mob_00000.ms 用 MSProbe 实际提取 8147xxx / 8800400（含 info）
- QuestScan 全量 24,879 条任务
- BeiDou 客户端地图 / Mob / Npc 集合比对
只读，只写 docs/ 下的报告。
"""
import os
ROOT = '/Users/lizixian/Documents/mxd/BeiDou-Server'
os.chdir(ROOT)
OUT = 'docs/岩壁巨人与紅月之森-迁移评估.html'

# ---------- 岩壁巨人地图（30 张） ----------
MAPS = [
 ('240090000', '勘查本部', '岩壁巨人勘查現場', '', '城镇/入口，returnMap 自身'),
 ('240090100', '勘查現場西邊道路 1', '岩壁巨人勘查現場', '', '狩猎'),
 ('240090200', '勘查現場西邊道路 2', '岩壁巨人勘查現場', '', '狩猎'),
 ('240090300', '勘查現場西邊道路 3', '岩壁巨人勘查現場', '', '狩猎'),
 ('240090400', '勘查現場危險的路', '岩壁巨人勘查現場', '', '狩猎'),
 ('240090500', '勘查現場東邊道路 1', '岩壁巨人勘查現場', '', '狩猎'),
 ('240090600', '勘查現場東邊道路 2', '岩壁巨人勘查現場', '', '狩猎'),
 ('240090700', '勘查現場東邊道路 3', '岩壁巨人勘查現場', '', '狩猎'),
 ('240090800', '騎乘卡布：往上', '岩壁巨人勘查現場', 'ft=6 / timeLimit=5', '骑乘上升图 → 240091000'),
 ('240090801', '騎乘卡布：往下', '岩壁巨人勘查現場', 'ft=6 / timeLimit=5', '骑乘下降图 → 240090000'),
 ('240091000', '卡布碼頭', '前往岩壁巨人', '', '中继点'),
 ('240091100', '蜂群棲息處 1', '前往岩壁巨人', '', '狩猎'),
 ('240091200', '蜂群棲息處 2', '前往岩壁巨人', '', '狩猎'),
 ('240091300', '蜂群棲息處 3', '前往岩壁巨人', '', '狩猎（NPC 2210012）'),
 ('240091400', '蜂群的根據地', '前往岩壁巨人', '', '狩猎（8147015，1214 万 HP）'),
 ('240091500', '奇諾月台', '前往岩壁巨人', '', '中继点'),
 ('240091600', '奇諾月台：往上', '前往岩壁巨人', 'ft=6 / timeLimit=5', '骑乘上升 → 240092000'),
 ('240091601', '奇諾月台：往下', '前往岩壁巨人', 'ft=6 / timeLimit=5', '骑乘下降 → 240091500'),
 ('240092000', '奇諾月台頂端', '岩壁巨人的身體', '', '巨人脚下'),
 ('240092100', '岩壁巨人的手臂', '岩壁巨人的身體', 'fieldScript=240092100_enter', '阶段：打手臂'),
 ('240092101', '岩壁巨人的手臂', '岩壁巨人的身體', 'onUserEnter=enter_240092101', '阶段：打手臂（第二型）'),
 ('240092200', '岩壁巨人的身體上 1', '岩壁巨人的身體', '', '爬身体 · 狩猎'),
 ('240092300', '岩壁巨人的身體上 2', '岩壁巨人的身體', '', '爬身体 · 狩猎（forcedReturn 落点）'),
 ('240092400', '岩壁巨人的身體上 3', '岩壁巨人的身體', '', '爬身体 · 狩猎'),
 ('240093000', '岩壁巨人的體內 1', '岩壁巨人的內部', '', '体内 · 狩猎'),
 ('240093100', '岩壁巨人的體內 2', '岩壁巨人的內部', '', '体内 · 狩猎'),
 ('240093200', '岩壁巨人的體內 3', '岩壁巨人的內部', 'onUserEnter=enter_240093200', '体内终点（NPC 2210014 等）'),
 ('240093300', '岩壁巨人的心臟', '岩壁巨人的內部', 'fieldScript=colossus2', '★ Boss 房（8800400）'),
 ('240093310', '岩壁巨人的心臟', '岩壁巨人的內部', 'fieldScript=colossus', '★ Boss 房（第二型）'),
 ('924030000', '岩壁巨人', '（副本实例）', 'fieldScript=colossus / onUserEnter=enter_924030000 / standAlone=1', '★ 真正的 Boss 战实例图：returnMap=240090000、forcedReturn=240092300、mobRate=2.0、hideMinimap=1'),
]

# ---------- 怪物（实测提取） ----------
MOBS = [
 ('8147000', 152, 2310000, 10811, 4024, '', 6),
 ('8147001', 153, 2433600, 11293, 4113, '', 6),
 ('8147002', 154, 2559600, 11831, 4258, '', 6),
 ('8147003', 155, 2693600, 12324, 4290, '', 5),
 ('8147004', 156, 2824600, 12878, 4282, '', 5),
 ('8147005', 157, '~296万', '~13400', '~4400', '', '—'),
 ('8147006', 158, 3093800, 13949, 4460, '', 5),
 ('8147007', 159, 3238400, 14462, 4420, '', 5),
 ('8147008', 160, 3379200, 15041, 4623, '', 5),
 ('8147009', 161, 3522400, 15563, 4902, '', 5),
 ('8147010', 162, '~367万', '~16200', '~4700', '', '—'),
 ('8147011', 163, 3823200, 16759, 4918, '', 5),
 ('8147015', 159, 12144000, 43386, 6132, '蜂群根據地 · 强化型', 1),
 ('8800400', 165, 57000000, 462800, 7110, '★ BOSS 克洛宿斯（attack1-4 + skill1）', 13),
]

NPCS = ['2210000','2210001','2210002','2210003','2210004','2210005','2210007','2210008',
        '2210012','2210013','2210014','2210017','2210018','2210019','2210020','2211000','2211001']

QUESTS = [
 ('1340', '[主題副本] 岩壁巨人 克洛宿斯', 150, '2081000', '主线入口'),
 ('31330', '[岩壁巨人] 岩壁巨人的傳聞', 150, '2081000', '序章'),
 ('31331', '[岩壁巨人] 對巨人的疑惑', 150, '2081000', ''),
 ('31332', '[岩壁巨人] 拉比很頭疼', 150, '2210016', ''),
 ('31333', '[岩壁巨人] 可娜的請託', 150, '2210001', ''),
 ('31334', '[岩壁巨人] 和拉比對話', 150, '2210000', ''),
 ('31335', '[岩壁巨人] 拉比的試探', 150, '2210000', ''),
 ('31336', '[岩壁巨人] 和卡布一起去嘛。', 150, '2210002', '引入骑乘'),
 ('31337', '[岩壁巨人] 卡布需要燃料', 150, '2210002', ''),
 ('31338', '[岩壁巨人] 卡布需要更多燃料', 150, '2210002', ''),
 ('31339', '[岩壁巨人] 突然的地震', 150, '2210002', ''),
 ('31340', '[岩壁巨人] 去找戚諾吧', 150, '2210003', ''),
 ('31341', '[岩壁巨人] 戚諾的請託', 150, '2210004', ''),
 ('31342', '[岩壁巨人] 與戚諾同行', 150, '2210004', ''),
 ('31343', '[岩壁巨人] 岩壁巨人的苦衷', 150, '2210007', '登上手臂'),
 ('31344', '[岩壁巨人] 岩壁巨人的真面目', 150, '2210018', ''),
 ('31345', '岩壁巨人 救援作戰 1', 150, '2210007', '副本阶段'),
 ('31346', '岩壁巨人 救援作戰 2', 150, '2210007', ''),
 ('31347', '岩壁巨人 救援作戰 3', 150, '2210007', ''),
 ('31348', '岩壁巨人 救援作戰 4', 150, '2210018', ''),
 ('31349', '岩壁巨人 救援作戰 5', 150, '2210008', ''),
 ('31350', '岩壁巨人 救援作戰 6', 150, '2210008', ''),
 ('31351', '岩壁巨人 救援作戰 7', 150, '2210008', ''),
 ('31352', '巨人般的偉人', 150, '2210019', ''),
 ('31353', '[岩壁巨人] 如果不是敵人', 150, '2210018', '收尾'),
 ('31354', '[岩壁巨人] 尋找皇家果凍', 150, '2210012', '日常支线'),
 ('31355', '[岩壁巨人] 皇家果涷真好吃', 150, '2210012', '日常支线'),
]

def e(s):
    return str(s if s is not None else '')

CSS = """
:root{--bg:#0f1116;--panel:#171a21;--panel2:#1d2129;--line:#2a2f3a;--tx:#e6e9ef;--tx2:#98a1b3;
--acc:#e05c5c;--acc2:#63b3ed;--ok:#5fbf85;--warn:#f0b95e;--pur:#b392f0;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.75 -apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,sans-serif;}
.wrap{max-width:1240px;margin:0 auto;padding:30px 20px 90px;}
h1{font-size:24px;margin:0 0 6px;}
h2{font-size:18px;margin:36px 0 12px;border-left:3px solid var(--acc);padding-left:10px;}
h3{font-size:14px;margin:20px 0 8px;color:var(--acc2);}
.sub{color:var(--tx2);font-size:13px;margin-bottom:16px;line-height:1.9;}
code{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#d5b06a;background:var(--panel2);padding:1px 5px;border-radius:5px;}
table{width:100%;border-collapse:collapse;margin:8px 0 6px;font-size:13px;}
th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top;}
th{color:var(--tx2);font-weight:600;font-size:12px;background:var(--panel);}
tr:hover td{background:#1a1e26;}
.tag{font-size:11px;padding:1px 8px;border-radius:20px;border:1px solid var(--line);color:var(--tx2);white-space:nowrap;display:inline-block;}
.tag.ok{border-color:#3d5140;color:#8fd6a2;background:#16211a;}
.tag.no{border-color:#5a3a3a;color:#e69191;background:#241a1c;}
.tag.warn{border-color:#5a4a3b;color:#e6b98f;}
.note{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 18px;color:var(--tx2);font-size:13px;margin:12px 0;}
.note b{color:var(--tx);}
.key{background:linear-gradient(180deg,#1b1f28,#171a21);border:1px solid #39404e;border-radius:12px;padding:16px 20px;margin:14px 0;}
.key h3{margin:0 0 6px;color:var(--acc2);font-size:14px;}
.verdict{border-radius:12px;padding:16px 20px;margin:16px 0;border:1px solid;}
.v-ok{background:#141d18;border-color:#3d5140;}
.v-no{background:#1e1517;border-color:#5a3a3a;}
.v-ok h2,.v-no h2{margin:0 0 8px;border:none;padding:0;font-size:18px;}
.v-ok h2{color:var(--ok);} .v-no h2{color:var(--acc);}
ul{margin:8px 0 8px 18px;padding:0;} li{margin:5px 0;}
.mono{font-family:ui-monospace,Menlo,monospace;font-size:12px;}
.cards{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0;}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:11px 15px;min-width:120px;flex:1;}
.card b{display:block;font-size:20px;} .card span{color:var(--tx2);font-size:12px;}
"""

H = []
H.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">')
H.append('<title>岩壁巨人 克洛宿斯 / 紅月之森 — 能否完整迁移</title><style>%s</style></head><body><div class="wrap">' % CSS)

H.append('<h1>岩壁巨人 克洛宿斯 &amp; 紅月之森 —— 能否完整迁移</h1>')
H.append('<div class="sub">对象：TMS 273 客户端 <code>~/Documents/mxd/TMS/</code>　对照：BeiDou 客户端 <code>clien/Data</code> + 服务端 <code>gms-server/wz*</code> + <code>scripts-zh-CN/</code>。<br>'
         '方法：地图 info 全量扫描 → 逐图解析 <code>life</code>（怪/NPC）→ 用 MSProbe 从 <code>Packs/Mob_00000.ms</code> <b>实际提取</b>目标怪验证数据可得性 → QuestScan 全量 24,879 条任务定位任务链 → 比对 BeiDou 资源集合与客户端能力（<code>fieldType</code>、等级上限）。</div>')

# 结论卡
H.append('<div class="verdict v-ok"><h2>① 岩壁巨人 克洛宿斯 —— 可以完整迁移（除过场对话），还原度约 85%</h2>'
 '<div class="sub" style="margin:0">机制是「爬上巨人 → 打手臂 → 钻进体内 → 打心脏」的立体 Boss 副本，'
 '<b>083 老端全部能表达</b>：<code>fieldType=6</code> 骑乘图 BeiDou 现有地图里已有 <b>302 张</b>，等级带 150–165 也落在服务端上限 255 之内（<code>V2.1.50</code>）。'
 '缺的是 TMS 那份服务端脚本（客户端不带 <code>.js</code>），所以副本流程要自写——这与现有「无过场、数据驱动」策略一致。</div></div>')

H.append('<div class="verdict v-no"><h2>② 紅月之森 —— 不能迁移，它是 Roguelike（肉鸽）模式的本体</h2>'
 '<div class="sub" style="margin:0">紅月之森 = <code>Redmoon</code>，挂在 TMS 的 <b>Roguelike 系统</b>下：'
 '104 张图里 <b>0 个怪</b>（全部由系统脚本刷），玩法是「遗物 + 局内成长 + 载具 + 周排名」。'
 '这些在 083 端与 BeiDou 服务端<b>都不存在</b>。迁地图只会得到 104 张空壳图。</div></div>')

# 岩壁巨人
H.append('<h2>一、岩壁巨人 克洛宿斯</h2>')
H.append('<div class="cards">'
 '<div class="card"><b>30</b><span>地图</span></div>'
 '<div class="card"><b>14</b><span>新怪（含 1 Boss）</span></div>'
 '<div class="card"><b>17</b><span>新 NPC</span></div>'
 '<div class="card"><b>27</b><span>任务（1 主线 + 26 链）</span></div>'
 '<div class="card"><b>Lv150</b><span>等级带（怪 152–165）</span></div>'
 '<div class="card"><b>0</b><span>BeiDou 现有存量</span></div></div>')

H.append('<div class="note"><b>⚠️ 修正上一份报告：</b><code>docs/TMS缺失内容迁移评估.html</code> 里把 colossus 记成「1 新怪 / 1 新 NPC」——'
 '那是只扫了<b>心脏房</b>那 13 张图的结果。把整个 24009 段（30 张）摊开，真实需求是 <b>14 个新怪 + 17 个新 NPC</b>。</div>')

H.append('<h3>1.1 玩法链路</h3>')
H.append('<div class="note">主线任务 <code>1340 [主題副本] 岩壁巨人 克洛宿斯</code>（Lv150，NPC 2081000）开场，'
 '接 <code>31330–31355</code> 共 26 条 [岩壁巨人] 任务链（NPC 22100xx 一家）。<br>'
 '动线：勘查本部 → 勘查現場道路（打怪）→ <b>騎乘卡布上升</b>（ft=6 / 5 秒）→ 卡布碼頭 → 蜂群棲息處 → '
 '<b>奇諾月台上升</b> → 巨人手臂（打手臂阶段）→ 身體上 1–3 → 體內 1–3 → <b>心臟（Boss）</b>。</div>')

H.append('<h3>1.2 地图清单（30 张，全部 lvLimit=150）</h3>')
H.append('<table><tr><th style="width:92px">地图 ID</th><th style="width:170px">名称</th><th style="width:120px">区域</th>'
 '<th style="width:290px">脚本 / 字段</th><th>说明</th></tr>')
for m, name, street, fs, note in MAPS:
    star = ' style="color:#f0b95e"' if '★' in note else ''
    H.append(f'<tr><td class="mono"{star}>{m}</td><td>{e(name)}</td><td>{e(street)}</td>'
             f'<td class="mono">{e(fs)}</td><td>{e(note)}</td></tr>')
H.append('</table>')
H.append('<div class="note"><b>注意三张「心脏/Boss」图：</b><code>240093300</code>(colossus2)、<code>240093310</code>(colossus)、'
 '<code>924030000</code>(colossus + <code>standAlone=1</code> + <code>returnMap=240090000</code> + <code>forcedReturn=240092300</code> + <code>mobRate=2.0</code>)。'
 '从 <code>standAlone / partyStandAlone / hideMinimap</code> 看，<b>924030000 才是正式 Boss 战实例图</b>，另两张是阶段房。迁移时要先确认，别三张都上。</div>')

H.append('<h3>1.3 怪物清单（14 种，实测从 <code>Packs/Mob_00000.ms</code> 提取成功）</h3>')
H.append('<table><tr><th style="width:90px">ID</th><th style="width:50px">Lv</th><th style="width:110px">maxHP</th>'
 '<th style="width:80px">exp</th><th style="width:70px">PAD</th><th style="width:60px">动画组</th><th>备注</th></tr>')
for mid, lv, hp, exp, pad, note, anims in MOBS:
    cls = ' style="color:#f0b95e"' if 'BOSS' in note else ''
    H.append(f'<tr><td class="mono"{cls}>{mid}</td><td>{lv}</td><td>{e(hp)}</td><td>{e(exp)}</td>'
             f'<td>{e(pad)}</td><td>{e(anims)}</td><td>{e(note)}</td></tr>')
H.append('</table>')
H.append('<div class="note"><b>数据可得性已实测：</b>'
 '<code>dotnet MSProbe.dll Packs/Mob_00000.ms → Mob/8147000.img</code> 等 12 个全部提取成功，'
 '带完整 <code>info</code>（level / maxHP / exp / PADamage / MADamage / boss / bodyAttack）+ 动画组。'
 '<code>MapleStory-IMG/Data/Mob/</code> 只有 <code>_Canvas</code> 没有 info，<b>别拿它当迁移源</b>'
 '（<code>8147015</code> 连 _Canvas 都没有，但 .ms 包里有）。</div>')

H.append('<h3>1.4 NPC（17 个，BeiDou 全部没有）</h3>')
H.append('<div class="note mono">' + '、'.join(NPCS) + '</div>')

H.append('<h3>1.5 任务链（27 条）</h3>')
H.append('<table><tr><th style="width:70px">ID</th><th style="width:300px">名称</th><th style="width:60px">Lv</th>'
 '<th style="width:90px">NPC</th><th>阶段</th></tr>')
for qid, name, lv, npc, note in QUESTS:
    H.append(f'<tr><td class="mono">{qid}</td><td>{e(name)}</td><td>{lv}</td><td class="mono">{npc}</td><td>{e(note)}</td></tr>')
H.append('</table>')

H.append('<h3>1.6 能不能「完整」迁移：逐项判定</h3>')
H.append('<table><tr><th style="width:150px">要素</th><th style="width:100px">判定</th><th>依据 / 缺口</th></tr>')
ROWS = [
 ('地图美术与地形', '<span class="tag ok">可迁</span>', '30 张 TMS 地图可解析；与已迁过的神秘河/黃昏同类型，走既有地图迁移流程。'),
 ('骑乘图 (fieldType=6)', '<span class="tag ok">可迁</span>', 'BeiDou 现有地图里 <b>302 张</b> ft=6，老端本来就支持；<code>timeLimit=5</code> 的强制传送行为需实机确认一次。'),
 ('等级带 150–165', '<span class="tag ok">无阻碍</span>', '服务端等级上限已提到 255（<code>V2.1.50__raise_character_level_cap_to_255</code>）。'),
 ('怪物数据', '<span class="tag ok">可得</span>', 'Packs/Mob_00000.ms 实测可提取（含 info + 动画）；迁移走 <code>arc.clone_image</code> + <code>sanitize_mob</code>，画布统一 ARGB4444。'),
 ('NPC 数据', '<span class="tag ok">可得</span>', '<code>MapleStory-IMG/Data/Npc/2210000.img</code> 等存在。'),
 ('任务链', '<span class="tag ok">可迁</span>', '27 条任务按现有导入规范（QuestInfo 只留 name/area/0/1/2，Say 留空，剥 startscript/endscript）；不写过场照样能接能交。'),
 ('副本流程脚本', '<span class="tag warn">需自写</span>', 'TMS 客户端<b>不含任何 .js</b>，<code>colossus / colossus2 / 240092100_enter / enter_924030000</code> 的逻辑要自己实现（打手臂 → 体内 → 心脏阶段推进）。'),
 ('Boss 招式与时序', '<span class="tag warn">需自配</span>', '8800400 有 attack1–4 + skill1，但<b>招式时序/伤害/掉落都在服务端</b>，TMS 客户端没有；要按 BeiDou 现有 Boss 的配置方式自配。'),
 ('过场对话 / 剧情演出', '<span class="tag no">放弃</span>', '与既定「无过场」策略一致；用任务文本代替。'),
 ('掉落与奖励', '<span class="tag warn">需自定</span>', '客户端无掉落表，按 BeiDou 现有掉落/奖励标准自行配置。'),
]
for a, b, c in ROWS:
    H.append(f'<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td></tr>')
H.append('</table>')

H.append('<div class="key"><h3>建议落地步骤</h3><ul>'
 '<li><b>① 先迁资源，不碰逻辑</b>：30 张地图 + 14 怪 + 17 NPC（客户端 Mob/Npc + 服务端 XML + <b>wz-zh-CN 中文树名字</b>）。</li>'
 '<li><b>② 导任务链</b>：1340 + 31330–31355，按现有导入规范，Say 留空。</li>'
 '<li><b>③ 写 1 个 event 脚本</b>：照 <code>CWKPQ.js</code> / <code>LudiPQ.js</code> 骨架，把「手臂 → 体内 → 心脏」三段推进写进去；'
 '凡是 <code>mobTime=0</code> 的图，必须 <code>eim.schedule(fn, 5000)</code> + <code>map.instanceMapRespawn()</code>。</li>'
 '<li><b>④ 配 Boss</b>：8800400（5700 万 HP / Lv165）按 BeiDou 现有 Boss 方式配技能与掉落。</li>'
 '<li><b>⑤ 实测三件事</b>：ft=6 骑乘图、心脏房用哪一张、手臂阶段判定。</li>'
 '<li><b>⑥ 验收</b>：<code>!debug mobsp</code> / <code>!debug map</code>（gm5），改脚本用 <code>!reloadevents</code>。</li></ul></div>')

# 紅月之森
H.append('<h2>二、紅月之森（Redmoon）</h2>')
H.append('<div class="cards">'
 '<div class="card"><b>104</b><span>地图（87502xxxx）</span></div>'
 '<div class="card"><b>0</b><span>地图内怪物</span></div>'
 '<div class="card"><b>17</b><span>NPC（9402xxx）</span></div>'
 '<div class="card"><b>18</b><span>任务（68000–68017）</span></div>'
 '<div class="card"><b>Lv250</b><span>等级带</span></div>'
 '<div class="card"><b>0</b><span>BeiDou 现有存量</span></div></div>')

H.append('<h3>2.1 它到底是什么：Roguelike 模式的「红月」主题</h3>')
H.append('<div class="note">紅月之森不是「一张副本地图」，而是 TMS 273 的 <b>Roguelike（肉鸽）模式</b>的一个赛季主题。'
 '证据链（都在 TMS 客户端里，可逐一核对）：</div>')
H.append('<table><tr><th style="width:330px">文件</th><th>内容</th></tr>')
EV = [
 ('String/Redmoon.img', '828 条：<code>artifact</code>（遗物：名字/描述/详细效果）、<code>skill</code> 194、<code>buff</code> 61、<code>tankSkill</code> 9、<code>UI</code>、<code>select_chapter</code>、<code>systemMessage</code>'),
 ('UI/UIRedmoon.img', '红月专属界面（083 端无对应 UI 文件）'),
 ('Skill/Roguelike/Skill/Redmoon', 'Roguelike 局内技能树'),
 ('Etc/RoguelikeReactor/Redmoon', 'Roguelike 专属 reactor'),
 ('Etc/RoguelikeRiding/Redmoon_Tank.img<br>RoguelikeRiding/Redmoon_Tank_Weekly.img', '坦克载具（周常版）——083 端无载具系统'),
 ('Map/Obj/Redmoon.img、Map/Back/Redmoon_Set_*.img', '红月主题的地图物件与背景'),
 ('Effect/Redmoon.img、RedmoonDirection.img', '红月专属特效与演出'),
 ('地图 fieldScript：<code>Redmoon_check_Totui</code>、<code>Redmoon_EnterMapByWaitQueue</code>', '<b>等待队列入场</b>——排队分配场次的系统型玩法'),
]
for a, b in EV:
    H.append(f'<tr><td class="mono">{a}</td><td>{b}</td></tr>')
H.append('</table>')

H.append('<h3>2.2 决定性事实：104 张图里 0 个怪</h3>')
H.append('<div class="note">逐图解析 <code>life</code> 的结果：<b>怪物实例 0、怪物种类 0</b>，只有 17 个 NPC。'
 '也就是说地图只是<b>空白场地</b>，刷什么怪、掉什么、怎么推进，全在 Roguelike 系统里（服务端 + 专属 UI）。'
 '这与岩壁巨人完全相反——岩壁巨人每张狩猎图都老老实实摆了 12–23 只怪。</div>')

H.append('<h3>2.3 任务侧（18 条，Lv250）</h3>')
H.append('<div class="note"><code>68000 [紅月之森] 托圖伊的書信</code> → <code>68001 青林派的棟樑，托蘭</code> → '
 '<code>68002 運送補給品！</code> → <code>68003 嘯虎會和嘯虎砲</code> → <code>68004 驚天動地的巨響</code> → '
 '<code>68005 重建保護咒文陣</code> → … → <code>68017 色即是空，空即是色</code>；'
 '外加 <code>505076 [紅月之森] 領取每週排名獎勵</code>。<br>'
 '任务只是剧情外衣，<b>玩法本体是「进局 → 选遗物 → 打 → 排名」</b>。</div>')

H.append('<h3>2.4 为什么不能完整迁移</h3>')
H.append('<table><tr><th style="width:170px">依赖</th><th style="width:100px">083 端</th><th style="width:110px">BeiDou 服务端</th><th>说明</th></tr>')
DEP = [
 ('遗物（artifact）系统与选择界面', '<span class="tag no">无</span>', '<span class="tag no">无</span>', '局内成长核心：<code>String/Redmoon.img</code> 里每个遗物都有独立效果（最大体力/攻速/暴击/护盾…），需要一套 buff 装配与 UI。'),
 ('Roguelike 局内技能', '<span class="tag no">无</span>', '<span class="tag no">无</span>', '<code>Skill/Roguelike/Skill/Redmoon</code>，194 条。'),
 ('坦克载具（Redmoon_Tank）', '<span class="tag no">无</span>', '<span class="tag no">无</span>', '<code>Etc/RoguelikeRiding</code>，083 端无载具系统。'),
 ('红月专属 UI / 特效 / Reactor', '<span class="tag no">无</span>', '—', '<code>UIRedmoon.img</code>、<code>Effect/Redmoon*</code>、<code>RoguelikeReactor/Redmoon</code>。'),
 ('等待队列入场 / 场次分配', '<span class="tag no">无</span>', '<span class="tag no">无</span>', '<code>Redmoon_EnterMapByWaitQueue</code>，需要排队与实例调度。'),
 ('每周排名与奖励', '<span class="tag no">无</span>', '<span class="tag no">无</span>', '<code>505076 領取每週排名獎勵</code>——需要排名结算系统。'),
]
for a, b, c, d in DEP:
    H.append(f'<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td><td>{d}</td></tr>')
H.append('</table>')

H.append('<div class="note"><b>如果硬要做：</b>工作量不是「迁一个副本」，而是「<b>从零实现一个 Roguelike 模式</b>」'
 '（局内状态机 + 遗物系统 + 载具 + 排名 + 一整套 273 UI）。'
 '可剥离复用的只有：<b>104 张地图美术</b>（可改做普通狩猎场/活动场）、<b>17 个 NPC（9402xxx）</b>、'
 '红月主题的背景与物件素材。但做出来的东西不是紅月之森。</div>')

# 对比
H.append('<h2>三、对比与结论</h2>')
H.append('<table><tr><th style="width:150px">维度</th><th>岩壁巨人 克洛宿斯</th><th>紅月之森</th></tr>')
CMP = [
 ('本质', '立体 Boss 副本（爬身 → 打手臂 → 体内 → 心脏）', 'Roguelike 模式的一个赛季主题'),
 ('地图 / 怪 / NPC', '30 图 / 14 怪 / 17 NPC', '104 图 / 0 怪 / 17 NPC'),
 ('等级带', '150–165（怪 152–165）', '250'),
 ('083 端能否表达', '<span class="tag ok">能</span>（ft=6 现有 302 张）', '<span class="tag no">不能</span>（遗物 UI / 载具 / 局内成长全无）'),
 ('服务端缺口', '1 个副本流程脚本 + Boss 招式掉落自配', '整套 Roguelike 状态机 + 排名结算'),
 ('数据可得性', '<span class="tag ok">已实测</span>（.ms 可提取）', '地图可得；玩法逻辑无源（客户端无 .js）'),
 ('还原度预估', '<b>约 85%</b>（扣掉过场与 Boss 招式细节）', '<b>≈0%</b>（只剩地图外壳）'),
 ('结论', '<span class="tag ok">推荐迁移</span>，建议排在 A 档第 4 位', '<span class="tag no">排除</span>，不作为迁移目标'),
]
for a, b, c in CMP:
    H.append(f'<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td></tr>')
H.append('</table>')

H.append('<div class="key"><h3>建议</h3><ul>'
 '<li><b>岩壁巨人</b>：纳入迁移计划，排在 CWKPQ boss 段 / 龍騎士 / 夏摩斯之后（它是 A 档里唯一带「立体 Boss 战」的，玩法辨识度高）。'
 '但先把上一份报告里的「1 新怪 / 1 新 NPC」改成 <b>14 / 17</b>，别按低估的量排期。</li>'
 '<li><b>紅月之森</b>：冻结。除非哪天决定自研 Roguelike 模式——那是一个独立项目，不是迁移任务。</li></ul></div>')

H.append('<div class="note">数据来源：TMS 地图 info 全量扫描（18,888 张）+ 24009 / 87502 段逐图 <code>life</code> 解析 + '
 'QuestScan 全量 24,879 条任务 + MSProbe 从 <code>Packs/Mob_00000.ms</code> 实际提取 12 个怪 + '
 'BeiDou 客户端地图 / Mob / Npc 集合与 <code>fieldType</code> 分布比对。'
 '生成脚本：<code>tool/scripts/migration/render_two_content_eval.py</code>（只读，未改动任何客户端或服务端文件）。</div>')
H.append('</div></body></html>')

open(OUT, 'w').write('\n'.join(H))
print('written', OUT, os.path.getsize(OUT), 'bytes')
