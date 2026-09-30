#!/usr/bin/env python3
"""渲染「TMS 有 / BeiDou 目前没有」的迁移评估报告 → docs/TMS缺失内容迁移评估.html

输入：/tmp/missing_eval.json（由 eval_missing_content.py 生成）+ 本文件内的手工机制判定表。
只读，只写 docs/ 下的报告。
"""
import os
import json
import html
from collections import defaultdict, Counter

ROOT = '/Users/lizixian/Documents/mxd/BeiDou-Server'
os.chdir(ROOT)
EV = json.load(open('/tmp/missing_eval.json'))
CL = EV['clusters']
CAND = EV['candidates']
OUT = 'docs/TMS缺失内容迁移评估.html'

# ---------- 手工机制判定：把簇归入「机制族」 ----------
S1 = """mirrorDungeon guildD_Culvert WarZone0_Next WarZone1_Next WarZone0_Final WarZone1_Final
Warzone1_First MDojang_KillMob gloryWmission gloryWmissionFinal FUE:prisonBreak_mapEnter prisonBreak
prisonBreakBoss FUE:PRaid_D_Fenter FUE:PRaid_B_Fenter FUE:GC_onFirstUserEnter_Lobby GuildCastle_Story
FUE:first_pfMeteorStage""".split()

S2 = """Angelic Kaiser Kaiser_tuto0 Kaiser_tuto1 DemonSlayer zero illium_hunt_fin hoyoung adele kainMP
Xenon phantom aran_2024 mikhail_2022 cygnus_2022 CrossH2024 adventure_2022 eunwol Lynn_story
kinesisTuto1 cadena_mPark cadena_mParkAllkill ark_mParkAllkill SavageT""".split()

S3 = """CerniumT1 CerniumT2 CerniumT3 seren FUE:first_SerenHard2 carcion tallahart odium_01 odium_02
sellas_2 bosswill bossWill morassDQ Morass_02 dunkel FUE:firstenter_bossBlackMageSc
FUE:firstenter_bossBlackMagepre FUE:firstenter_bossBlackMageEpre FUE:Fenter_450004300 evolvingsystem
link5_bossSummon dimensionInvade""".split()

S4 = """blackHeavenPark blackheavenCG BlackHeavenDollMaster bh_350062110 2023_12_BH BM1_mParkAllkill
BM1_mParkAllkillF BM3_mParkAllkill BMPre_mParkAllkill BMPre_mParkAllkillF BM3_story_2024 202412_BM1
HofM_8240134 HofM_act4tree HofM_act2inside HofM_8240133 HofM_8240162 HofM_2024 HofM3_Museum
HofM3_Museum2 Episode3 dunaEpisode3 Helisium demensionLibrary demensionLibrary1 spinOffPark spinOffPlus
Wz2_Mukhyun_story elodin BossDemian""".split()

S5 = "BugCat_2023 2020halloween_3 PL_event_chco coronaLink".split()

S7 = "BossMagnus papulatus velum hillah GiantBossField colossus colossus2".split()

FAMILY = [
    ('S1', '273 專屬系統 / 新 UI', 'S1', '#e05c5c', '不可行',
     '依賴 083 端根本沒有的介面與系統（鏡像副本、道場樓層、公會水道、榮耀週任、Roguelike、空中監獄、戰爭區、小屋、深淵遠征、小豬酒吧）。客戶端渲染不出來，遷了也玩不了。'),
    ('S2', '083 後新增職業劇情', '', '#e05c5c', '不可行',
     'BeiDou 職業上限只到龍神（job.id ≤ 2218），沒有凱撒／天使／神之子／伊利恩／虎影／阿黛爾／凱恩／幻影／尖兵／隱月／琳恩／狂龍（含 2022-2024 重製）等職業，劇情圖沒有承載主體。'),
    ('S3', '需新數值系統（神秘力量 / 進化）', '', '#e05c5c', '不可行（除非自研）',
     '服務端全庫搜不到 arcaneForce／authenticForce；神秘河後段（賽爾尼溫／奧迪溫／卡爾西溫／賽拉斯／威爾／瑟琳）與進化系統、次元入侵都綁這套數值，083 端與服務端都沒有。'),
    ('S4', 'Blockbuster 大型劇情戰役', '', '#f0b95e', '有條件可行（去過場）',
     '黑色天堂、楓葉英雄、耶雷弗奪還、赫力席母、次元圖書館等。戰鬥與地圖可遷，但正戲靠 CG／對話推動，按現有「無過場」策略只能做成純戰鬥版。'),
    ('S5', '聯動 / 限時活動', '', '#f0b95e', '不建議',
     '咖波地下城、萬聖小屋、巧克力、日蝕慶典等一次性活動，內容與授權綁定，壽命短。'),
    ('S6', '傳統機制副本 / 任務', '', '#5fbf85', '★ 主要可遷池',
     '打怪、收集、護送、階段通關、Boss 戰、小遊戲——083 端全部能表達，服務端也有 EventInstanceManager 框架支撐。'),
    ('S7', '單體 Boss 圖', '', '#63b3ed', '可做（需配服務端）',
     '單張 Boss 房＋Boss 怪，地圖工作量小，但要補服務端 Boss 技能／血量／掉落，成本在邏輯不在地圖。'),
]

KEY2FAM = {}
for fid, names in (('S1', S1), ('S2', S2), ('S3', S3), ('S4', S4), ('S5', S5), ('S7', S7)):
    for n in names:
        KEY2FAM[n] = fid


def fam_of(key):
    return KEY2FAM.get(key, 'S6')


# ---------- 74 個組隊任務的狀態（依 BeiDou 既有 event 腳本 / 地圖判定） ----------
# (PQuest id, 中文名, 狀態, BeiDou 既有證據, 可行性)
PQ = [
 ('1202','時空的裂縫','已有','LudiPQ.js','-'),
 ('1204','金勾海賊王','已有','PiratePQ.js','-'),
 ('1205','羅密歐和茱麗葉','半成品','地圖 9261 系列已遷（覆蓋 ~95%），缺 event 腳本','★ A：只差腳本'),
 ('1209','侏儒帝王的復活','缺失','無','A/B：傳統階段 PQ'),
 ('1210','龍騎士','缺失','無（神木村天空地區）','★ A：50 圖，0 新怪 0 新 NPC'),
 ('1211','奈特的金字塔','缺失','無','A/B：傳統 PQ'),
 ('1212','林車長的地鐵站','已有','KerningPQ.js / Subway.js','-'),
 ('1213','武陵道場','缺失','無','C：樓層 UI + 排行'),
 ('1214','陷入危險的健太','缺失','無（危險之海）','★ A：40 圖，8 新怪'),
 ('1215','逃脫（空中監獄）','缺失','無','C：273 專屬機制'),
 ('1218','冰騎士的詛咒（夏摩斯護送）','缺失','無（冰雪峽谷）','★ A：51 圖，0 新怪 0 新 NPC'),
 ('1301','怪物擂台賽','缺失','無','A/B：10 圖，1 新怪'),
 ('1302','第2回怪物擂台賽','缺失','無','A/B'),
 ('1303','霧海幽靈船','缺失','無','B'),
 ('1304','魔王巴洛古','已有','BalrogBattle.js','-'),
 ('1305','獅子王凡雷恩','已有','MK_PrimeMinister.js','-'),
 ('1306','殘暴炎魔','已有','ZakumBattle.js / ZakumPQ.js','-'),
 ('1307','海怒斯','已有/待核','HenesysPQ.js 疑似對應','-'),
 ('1308','拉圖斯','已有','PapulatusBattle.js','-'),
 ('1309','闇黑龍王','已有','HorntailBattle.js / HorntailPQ.js','-'),
 ('1310','粉豆','已有','PinkBeanBattle.js','-'),
 ('1311','菇菇王國','缺失','無','A/B'),
 ('1312','墮落城市','已有/待核','KerningPQ.js（第一次同行）','A：補重製段 13 圖'),
 ('1313','奈歐市','缺失','無','B'),
 ('1314','克里塞','缺失','無','B'),
 ('1315','軍團長阿卡伊農','已有','AKAYRUMBattle.js','-'),
 ('1316','希拉','缺失','無（Boss 圖 hillah 3 張）','B：單 Boss 圖，需補服務端'),
 ('1317','奇怪的畫廊','缺失','無','A/B'),
 ('1318','奇幻主題樂園','缺失','無','B'),
 ('1319','大亂鬥','缺失','無','C：配對 UI'),
 ('1321','進化系統研究所','缺失','無','C：進化系統'),
 ('1322','次元入侵','缺失','無','C：需新系統'),
 ('1323','組隊任務入場（初級）','缺失','無','C：273 入場 UI'),
 ('1324','組隊任務（中級）','缺失','無','C'),
 ('1325','組隊任務','缺失','無','C'),
 ('1221','瑪斯特利亞的祭壇','已有','CWKPQ.js','★ A：補 boss 段 18 圖，0 新怪'),
 ('1339','深紅森林城堡','缺失','無','B'),
 ('1326','地上樂園 黃金海灘','缺失','無','A/B'),
 ('1327','湯寶寶的烹飪教室','缺失','無（10 圖，1 新 NPC）','A/B：小遊戲機制需自研'),
 ('1328','妖精學院 艾利涅','缺失','無（20 圖，3 怪 5 NPC）','★ A'),
 ('1330','里恩海峽','缺失','無','B'),
 ('1329','阿里安特競技大會','缺失','無','A/B：10 圖'),
 ('1331','麥格納斯','缺失','無（暴君之城 3 圖）','B：單 Boss 圖'),
 ('1332','西格諾斯','已有','CygnusBattle.js','-'),
 ('1333','貝倫','缺失','無（深潭洞穴 3 圖）','B：單 Boss 圖'),
 ('1334','血腥女王','缺失','無','B：RootAbyss 之一'),
 ('1335','皮埃爾','缺失','無','B：RootAbyss 之一'),
 ('1336','班班','缺失','無','B：RootAbyss 之一'),
 ('1337','櫻花城','缺失','無','B'),
 ('1338','黃金寺院','缺失','無','B'),
 ('1340','岩壁巨人 克洛蘇斯','缺失','無（13 圖，1 新怪 1 新 NPC）','★ A'),
 ('1341','艾琳森林','已有','EllinPQ.js','-'),
 ('1342','阿斯旺解放戰','缺失','無','B：24 圖（enterAswanField）'),
 ('1343','怪物公園','已有','MonsterPark.js','-'),
 ('1344','十字獵手','缺失','無','C：273 機制'),
 ('1345','黃昏的勇士之村','已有（本次補齊）','地圖 2730 系列 + 任務鏈 + event 腳本','-'),
 ('1346','次元圖書館','缺失','無（30 圖，10 新怪）','B：劇情副本，去過場可做'),
 ('1347','組隊任務綜合入場','缺失','無','C'),
 ('1348','世界綜合組隊任務','缺失','無','C'),
 ('1349','露塔必思','部分','RootAbyss 合約已遷，庭園圖（8 張）缺','★ A：補 8 圖'),
 ('1350','楓之谷聯盟會議廳','缺失','無','C：273 系統'),
 ('1351','The Seed','已有','SeedTower20.js','-'),
 ('33041','Friends Story','缺失','無','C：273 系統'),
 ('33959','楓之谷聯盟會議廳','缺失','無','C'),
 ('34555','God of Control','缺失','無','C'),
 ('7039','阿斯旺反抗戰','缺失','無','B'),
 ('17206','外星侵略者','缺失','無','B'),
 ('1222','世界綜合組隊任務','缺失','無','C'),
 ('1353','中國_龍與虎','缺失','神說島自有版本（非 TMS）','B：武陵系列'),
 ('1354','怪物公園 REBORN','缺失','無','B：MonsterPark 擴展'),
 ('17600','柯梅爾茲','已有','CommerciVoyage.js','-'),
 ('31199','墮落的西格諾斯（簡單）','缺失','無','B'),
 ('30201','幽靈公園','缺失','無','B'),
 ('33553','霸王烏爾斯','缺失','無','C：需 UI'),
]

# ---------- A 檔推薦（手工評語 + 自動數據） ----------
A_NOTES = {
 'cwkpq': dict(mech='瑪斯特利亞祭壇的 Boss 段（魔王雷德納格／瑪爾加納房間）。BeiDou 已有 CWKPQ.js 主流程，缺的是這幾張 boss 房與過渡圖。',
               dep='無新怪、無新 NPC；需確認 CWKPQ.js 的關卡號與新圖對得上。',
               risk='低。要核對 BeiDou 現有 CWKPQ 地圖 ID 與 TMS 是否同號，不同則要改腳本裡的 mapid。'),
 'dragon_rider': dict(mech='神木村天空地區的經典組隊任務：分階段清怪 → 收集 → 中 Boss → 龍騎士 Boss。',
               dep='0 個新怪、0 個新 NPC（怪物與 NPC 兩端都有）。',
               risk='低。需要一份 event 腳本（照 LudiPQ.js 骨架）；life 用 mobTime=0 的圖要自己 instanceMapRespawn()。'),
 'shammos': dict(mech='萬年冰河冰雪峽谷的護送型 PQ：保護夏摩斯穿越峽谷 → 冰騎士 Boss。',
               dep='0 個新怪、0 個新 NPC。護送邏輯可參考 RescueGaga.js。',
               risk='中低。護送 NPC 的移動／失敗判定要自寫，TMS 只有腳本名沒有腳本。'),
 'kenta': dict(mech='危險之海的健太護送：護送健太穿越洞窟 → 洞窟 Boss。與夏摩斯同型。',
               dep='8 個新怪、1 個新 NPC 要從 ms-extract/Mob_0000X 遷。',
               risk='中。怪物遷移走 arc.clone_image + sanitize_mob，畫布統一下 ARGB4444。'),
 'colossus': dict(mech='岩壁巨人：爬上巨人身體、打掉部位單元的「部位戰」，與扎昆／龍王同型的老機制。',
               dep='1 個新怪、1 個新 NPC。',
               risk='中。部位 Boss 的服務端邏輯要自寫（血量分部位、階段推進）。'),
 'fairy': dict(mech='妖精學院艾利涅：教學／新手向的階段副本，打怪 + 對話 + 小 Boss，機制與 EllinPQ 同族。',
               dep='3 個新怪、5 個新 NPC。',
               risk='中低。NPC 對話可用現有 npc 腳本模式補，不需過場。'),
 'bm2_maze': dict(mech='苦痛迷宮：固定迷宮地圖組 + 大量任務引用（被 83 條任務引用，是全 TMS 引用最高的內容）。BeiDou 已遷過約 26%，實缺約 116 張。',
               dep='8 個新怪、1 個新 NPC。',
               risk='中。工作量大但每張圖都是靜態迷宮，無機制依賴；建議分批 30 張一組交付。'),
 'yumyum': dict(mech='嚼嚼／啾啾艾爾蘭：低等級島嶼內容，打怪收集為主，適合作為新手路線補充。',
               dep='7 個新怪。',
               risk='中低。等級帶低，與現有新手線要重新串。'),
 'tangyoon': dict(mech='湯寶寶的烹飪教室：小遊戲型 PQ（按順序做出料理）。',
               dep='1 個新 NPC，無新怪。',
               risk='中。小遊戲判定邏輯要自寫（TMS 無腳本），可簡化為「收集材料 → 交貨」。'),
 'rootabyss_garden': dict(mech='露塔必思庭園（東／西／南／北庭園）：RootAbyss 四王的外部圖。',
               dep='4 個新怪、4 個新 NPC。',
               risk='中。要確認 BeiDou 現有 RootAbyss 用的是哪套地圖 ID，避免與本次補的 8 張撞號。'),
 'viking': dict(mech='維京飛行船：5 張圖的小型任務副本（船長室等）。',
               dep='無新怪、無新 NPC。',
               risk='極低。最便宜的一檔，適合當試點。'),
 'arena': dict(mech='怪物競技戰場：召喚怪物對戰的競技型內容。',
               dep='1 個新怪。',
               risk='中。競技判定需服務端自寫。'),
}

A_ORDER = ['cwkpq','dragon_rider','shammos','kenta','colossus','fairy','bm2_maze','yumyum',
           'tangyoon','rootabyss_garden','viking','arena']

B_ORDER = ['neotokyo','bosses','blackheaven','dim_library','helisium','spinoff','mukhyun','ep3',
           'arcana','bat_storm','escort_past','murumuru','elodin','fishing','treasure','flag',
           'm4_job','karotte','dim_invade','mystic','kerning','giant_boss','comeback','mysticField']

B_NOTES = {
 'neotokyo': '新東京／日本區：88 圖、27 新怪、28 新 NPC，是候選裡最貴的一檔。機制傳統（清怪→階段→Boss），前提是 BeiDou 日本區（ShowaBattle／RanmaruBattle）還在。建議拆成「東京都廳」與「2100 年台場」兩批。',
 'bosses': '單體 Boss 圖（戴米安／麥格納斯／拉圖斯／貝倫／希拉／敦凱爾）：22 圖、只 1 個新怪、7 個新 NPC。地圖便宜，貴在服務端 Boss 技能組與血量。',
 'blackheaven': '黑色天堂 Blockbuster：76 圖、34 新怪。戰鬥圖可遷，但主線靠 CG 推進；按「無過場」策略只能給出戰鬥 + 任務文本版。',
 'dim_library': '次元圖書館：30 圖、10 新怪。本質是「重玩舊副本」的劇情副本，機制傳統，強依賴對話文本。',
 'helisium': '赫力席母奪回戰：17 圖、10 新怪。大型戰場（佔領／推進）型，需自寫推進邏輯。',
 'spinoff': '皇家神獸學院：19 圖、9 新怪。劇情副本。',
 'mukhyun': '玄山派（武陵桃園）：23 圖、0 新怪、8 新 NPC。任務向支線，成本低。',
 'ep3': '耶雷弗奪還戰／全力突破：36 圖、6 新怪。劇情戰役。',
 'arcana': '阿爾卡納／尖耳狐狸村：11 圖、9 新怪。神秘河前段，可去掉 AF 數值做純地圖版。',
 'bat_storm': '蝙蝠群／暴風雨森林：30 圖、3 新怪、6 新 NPC。活動型刷怪圖，可做節慶活動。',
 'escort_past': '護衛哈沙勒（納希綠洲城）：5 圖、2 新怪。小型護送。',
 'murumuru': '姆勒姆勒護送：8 圖、6 新怪。小型護送副本。',
 'elodin': '露安的家：6 圖、4 新怪。劇情向。',
 'fishing': '釣魚王：9 圖、3 新 NPC。小遊戲，需確認 083 端釣魚系統是否可用。',
 'treasure': '魔物藏寶城：7 圖、6 新 NPC。小遊戲（攀爬／計時）。',
 'flag': '旗幟爭奪戰：6 圖。PvP 小遊戲，需隊伍對抗框架。',
 'giant_boss': '培羅德（瑪斯特利亞巨型 Boss）：12 圖、17 新怪。多階段部位戰，新怪偏多。',
 'kerning': '第一次同行（KerningPQ 重製段）：13 圖、1 新怪、2 新 NPC。BeiDou 已有 KerningPQ.js，只需補重製段。',
 'm4_job': '耶雷弗庭院（四轉任務）：10 圖、1 新怪。',
 'karotte': '卡羅泰（亞空間）：3 圖、3 新怪。',
}

# ---------- 統計 ----------
def e(s):
    return html.escape(str(s if s is not None else ''))


zero = [c for c in CL if c['hit'] == 0]
part = [c for c in CL if 0 < c['cov'] < 1]
full = [c for c in CL if c['cov'] == 1]
fam_stat = defaultdict(lambda: {'n': 0, 'maps': 0})
for c in zero:
    f = fam_of(c['key'])
    fam_stat[f]['n'] += 1
    fam_stat[f]['maps'] += c['n']

# 只由 onUserEnter 驅動的系統玩法（補充口徑）
rows = []
for line in open('/tmp/test_one.tsv'):
    p = line.rstrip('\n').split('\t')
    if len(p) < 4:
        continue
    d = {}
    for kv in p[1].split(';'):
        if '=' in kv:
            k, v = kv.split('=', 1)
            d[k] = v
    if d.get('fieldScript') or d.get('onFirstUserEnter'):
        continue
    ue = d.get('onUserEnter')
    if ue:
        rows.append(ue)
ue_counter = Counter(rows)
bd_maps = EV['bd_maps']

# ---------- HTML ----------
def card(v, label, cls=''):
    return f'<div class="card {cls}"><b>{v}</b><span>{label}</span></div>'


H = []
H.append('''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TMS 缺失内容迁移评估（BeiDou 目前没有的）</title>
<style>
:root{--bg:#0f1116;--panel:#171a21;--panel2:#1d2129;--line:#2a2f3a;--tx:#e6e9ef;--tx2:#98a1b3;
--acc:#e05c5c;--acc2:#63b3ed;--ok:#5fbf85;--warn:#f0b95e;--pur:#b392f0;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.75 -apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,sans-serif;}
.wrap{max-width:1240px;margin:0 auto;padding:30px 20px 90px;}
h1{font-size:24px;margin:0 0 6px;}
h2{font-size:17px;margin:36px 0 12px;border-left:3px solid var(--acc);padding-left:10px;}
h3{font-size:14px;margin:18px 0 8px;color:var(--acc2);}
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
.cards{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0;}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:11px 15px;min-width:130px;flex:1;}
.card b{display:block;font-size:20px;} .card span{color:var(--tx2);font-size:12px;}
.card.a b{color:var(--ok);} .card.b b{color:var(--warn);} .card.c b{color:var(--acc);} .card.n b{color:var(--acc2);}
.item{border:1px solid var(--line);border-radius:12px;padding:14px 18px;margin:12px 0;background:var(--panel);}
.item .hd{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap;}
.item .hd b{font-size:15px;color:var(--tx);}
.item .kv{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--tx2);margin:6px 0 8px;}
.item .kv span b{color:var(--tx);font-weight:600;}
.item p{margin:6px 0;font-size:13px;color:var(--tx2);}
.item p b{color:var(--tx);}
.bar{display:inline-block;width:88px;height:7px;background:#2a2f3a;border-radius:4px;overflow:hidden;vertical-align:middle;margin-right:6px;}
.barf{display:block;height:100%;}
ul{margin:8px 0 8px 18px;padding:0;} li{margin:4px 0;}
.mono{font-family:ui-monospace,Menlo,monospace;font-size:12px;}
</style></head><body><div class="wrap">''')

H.append('<h1>TMS 缺失内容迁移评估</h1>')
H.append('<div class="sub">对象：<code>~/Documents/mxd/TMS/MapleStory-IMG/Data</code>（TMS 273）中 <b>BeiDou 目前没有</b>的玩法内容。'
         '<br>方法：18,888 张 TMS 地图按 <code>fieldScript / onFirstUserEnter</code> 聚成玩法簇 → 与 BeiDou 客户端 6,336 张地图比对覆盖率 → '
         '取覆盖率为 0 的簇 → 逐簇扫 <code>life</code> 统计还要新迁多少怪／NPC → 叠加机制判定。'
         '<br>判定所用的两个硬事实：BeiDou 职业上限 = 龙神（<code>job.name</code> 最大 id 2218）；服务端全库 <code>arcaneForce / authenticForce</code> 零命中。</div>')

H.append('<div class="cards">')
H.append(card(len(CL), 'TMS 玩法簇（≥3 图）', 'n'))
H.append(card(len(zero), '完全缺失簇', 'c'))
H.append(card(sum(c['n'] for c in zero), '完全缺失地图数', 'c'))
H.append(card(len(part), '部分缺失簇', 'b'))
H.append(card(len(full), '已完整覆盖簇', 'a'))
H.append(card(len([p for p in PQ if p[2] == '缺失']), '74 组队任务中缺失', 'b'))
H.append('</div>')

H.append('<div class="key"><h3>先说结论</h3><ul>'
         '<li><b>绝大多数「没有」是真没有，但大多数也不该迁。</b>182 个完全缺失簇里，约 <b>三分之二</b>属于 273 专属系统、083 后新增职业剧情、或需要神秘力量/进化系统——这三类在 GMS 083 客户端上<b>根本表达不出来</b>，不是工作量问题。</li>'
         '<li><b>真正值得做的是「传统机制」那一池。</b>打怪 / 收集 / 护送 / 阶段通关 / Boss 战 / 小游戏，083 端全都能表达，服务端也有 <code>EventInstanceManager</code> + 121 个 event 脚本的既有框架。</li>'
         '<li><b>性价比最高的一组是「地图有缺口、但资源零新增」</b>：龍騎士（50 图 / 0 新怪 / 0 新 NPC）、夏摩斯护送（51 图 / 0 / 0）、CWKPQ boss 段（18 图 / 0 / 0）、維京飛行船（5 图 / 0 / 0）。迁地图即可，不用碰 Mob.wz。</li>'
         '<li><b>最大的一块「金矿」是苦痛迷宮</b>：全 TMS 被 83 条任务引用（引用数第一），BeiDou 已迁约 26%，实缺约 116 张，只需 8 个新怪——贵在图多，不贵在机制。</li>'
         '</ul></div>')

H.append('<div class="note"><b>口径校准（避免误判）：</b>覆盖率按<b>地图 ID</b> 比对，但 BeiDou 历史上从 TMS 迁过的图会换新 ID。'
         '因此额外做了<b>中文地图名</b>交叉校验：绝大多数簇名称命中为 0（确认真缺失），只有三组有存量——'
         '苦痛迷宮 26%、黑色天堂 11%、神秘河后段 8%。这三组在下文按「实缺张数」计算，不是按 ID 全缺。</div>')

# 分族
H.append('<h2>一、182 个完全缺失簇按「机制族」归类</h2>')
H.append('<table><tr><th style="width:60px">族</th><th style="width:190px">机制族</th><th style="width:60px">簇数</th>'
         '<th style="width:70px">地图数</th><th style="width:130px">可迁移性</th><th>判定依据</th></tr>')
for fid, name, _, color, verdict, why in FAMILY:
    st = fam_stat.get(fid, {'n': 0, 'maps': 0})
    H.append(f'<tr><td class="mono" style="color:{color}">{fid}</td><td><b>{e(name)}</b></td>'
             f'<td>{st["n"]}</td><td>{st["maps"]}</td><td><span class="tag {"ok" if fid=="S6" else ("warn" if fid in ("S4","S7","S5") else "no")}">{e(verdict)}</span></td>'
             f'<td>{e(why)}</td></tr>')
H.append('</table>')

H.append('<div class="note"><b>补充口径：只由 <code>onUserEnter</code> 驱动的系统型玩法</b>（这类没有 fieldScript，不在上面的 219 簇里，但同样是「目前没有的」）：</div>')
H.append('<table><tr><th>脚本键</th><th style="width:70px">地图数</th><th>判定</th></tr>')
UE_JUDGE = {
 'piggy_rewardEnter': '小豬酒吧獎勵圖（273 小遊戲系統）— 不可行',
 'enterPiggyBarMinigameRound': '小豬酒吧小遊戲回合 — 不可行',
 'roguelike_game_enter': 'Roguelike 模式（273 專屬）— 不可行',
 'MDojang_KillMob': '武陵道場（樓層 UI + 排行）— 不可行',
 'myHomeOnUserEnter': '我的小屋（273 系統）— 不可行',
 'MExplorer_onUserEnter': '怪物探險（273 系統）— 不可行',
 'Abyss3_OnUserEnter_Common': '深淵遠征（Etc/AbyssExpeditionConfig）— 不可行',
 'Abyss5_OnUserEnter_Common': '深淵遠征 — 不可行',
 'Abyss4_OnUserEnter_Common': '深淵遠征 — 不可行',
 'enter_abysscommon': '深淵遠征 — 不可行',
 'enter_pfCommonStage': '273 階段舞台 — 不可行',
 'enterAswanField': '阿斯旺解放戰（24 圖）— <b>可遷，B 檔</b>',
 'enter_WUPQgateway': '組隊任務入口（273 入場 UI）— 不可行',
 'enter_NihalTrade': '尼哈爾交易（273 系統）— 不可行',
 'library_SaveFieldID': '次元圖書館存檔 — B 檔（隨 dim_library 一起）',
 'MistyIsland_onUserEnter': '迷霧島 — A/B 檔（傳統機制）',
 'enter_dlep1dir': '威廉系列（需核對是否屬公會地下城）— 待核',
 'enter_dlep2dir': '威廉系列 — 待核',
 'enter_gabuki': '東京市政廳（日本區）— B 檔',
 'g_reset': '（通用重置入口）— 無獨立玩法',
}
shown = 0
for k, n in ue_counter.most_common(40):
    if n < 15:
        continue
    judge = UE_JUDGE.get(k, '待核')
    H.append(f'<tr><td class="mono">{e(k)}</td><td>{n}</td><td>{judge}</td></tr>')
    shown += 1
H.append('</table>')

# A 档
H.append('<h2>二、A 档：建议优先迁移（12 个，机制传统 + 依赖少）</h2>')
H.append('<div class="sub">排序按「性价比」＝ 可还原度 ÷ 工作量。数据列里的 <b>新怪 / 新 NPC</b> = TMS 该簇用到的、BeiDou 两端都没有的种类数（已按 8 位补零归一比对）。</div>')
for cid in A_ORDER:
    c = CAND.get(cid)
    if not c:
        continue
    note = A_NOTES.get(cid, {})
    H.append('<div class="item"><div class="hd"><b>%s</b><span class="tag ok">A 档</span></div>' % e(c['name']))
    H.append('<div class="kv">'
             f'<span>地图 <b>{c["maps"]}</b></span>'
             f'<span>新怪 <b>{c["new_mobs"]}</b> / 共 {c["mob_kinds"]}</span>'
             f'<span>新 NPC <b>{c["new_npcs"]}</b> / 共 {c["npc_kinds"]}</span>'
             f'<span>Reactor <b>{c["reactors"]}</b></span>'
             f'<span>簇键 <b class="mono">{e(", ".join(c["keys"])[:60])}</b></span></div>')
    if note.get('mech'):
        H.append('<p><b>机制：</b>%s</p>' % e(note['mech']))
    if note.get('dep'):
        H.append('<p><b>依赖：</b>%s</p>' % e(note['dep']))
    if note.get('risk'):
        H.append('<p><b>风险：</b>%s</p>' % e(note['risk']))
    H.append('</div>')

# B 档
H.append('<h2>三、B 档：可以做，但要算清楚成本</h2>')
H.append('<table><tr><th style="width:150px">组</th><th style="width:60px">地图</th><th style="width:80px">新怪</th>'
         '<th style="width:70px">新 NPC</th><th>说明</th></tr>')
for cid in B_ORDER:
    c = CAND.get(cid)
    if not c:
        continue
    H.append(f'<tr><td><b>{e(c["name"])}</b><br><span class="mono" style="color:#98a1b3">{cid}</span></td>'
             f'<td>{c["maps"]}</td><td>{c["new_mobs"]}</td><td>{c["new_npcs"]}</td>'
             f'<td>{e(B_NOTES.get(cid, ""))}</td></tr>')
H.append('</table>')

# C 档
H.append('<h2>四、C 档：不建议碰（老端天花板）</h2>')
H.append('<div class="note">这三类的共同点：<b>不是工作量问题，是 083 客户端根本没有对应的表达手段</b>。强行迁地图只会得到一堆进得去、但玩不了的图。</div>')
H.append('<table><tr><th style="width:150px">簇</th><th style="width:60px">地图</th><th style="width:110px">街道 / 区域</th><th>为什么不行</th></tr>')
C_REASON = {
 'mirrorDungeon': '镜像副本：42 个镜像 + 镜像专用 UI（String/mirrorDungeon.img + Etc/mirrorDungeonMap.img），083 端无镜像界面。',
 'guildD_Culvert': '公会水道：156 张 + 公会地下城系统（贡献、阶级、每周重置），273 才有。',
 'MDojang_KillMob': '武陵道场：楼层选择 / 计时 / 排行榜 UI，083 端无这套界面。',
 'gloryWmission': '荣耀使命（每周任务：调查异常现象）：任务面板 + 进度 UI，273 专属。',
 'prisonBreak': '空中监狱逃脱：逃脱机制 + 追捕者 AI，273 专属。',
 'WarZone0_Next': '战争区域（占领战 / 联盟战）：配对与占领推进 UI，273 专属。',
 'Angelic': '天使破坏者职业剧情：BeiDou 无该职业（job ≤ 2218）。',
 'Kaiser': '凯撒职业剧情：BeiDou 无该职业。',
 'DemonSlayer': '恶魔猎手剧情：BeiDou 职业表止于龙神，无恶魔猎手。',
 'zero': '神之子职业剧情：无该职业。',
 'illium_hunt_fin': '伊利恩职业剧情：无该职业。',
 'hoyoung': '虎影职业剧情：无该职业。',
 'adele': '阿黛尔职业剧情：无该职业。',
 'kainMP': '凯恩职业支线：无该职业。',
 'CerniumT1': '赛尔尼温：需神秘力量（AF）系统与 250+ 等级带，服务端零支持。',
 'seren': '瑟琳 Boss：需 AF 数值与高阶装备线。',
 'odium_01': '奥迪温：需正宗力量（AF）系统。',
 'evolvingsystem': '进化系统：273 的装备进化系统，服务端无对应实现。',
 'dimensionInvade': '次元入侵：273 专属玩法（PQuest 1322）。',
}
for c in zero:
    f = fam_of(c['key'])
    if f not in ('S1', 'S2', 'S3'):
        continue
    reason = C_REASON.get(c['key'], {'S1': '273 专属系统 / UI，083 端无对应界面。',
                                     'S2': '083 后新增职业，BeiDou 无该职业（job.name ≤ 2218）。',
                                     'S3': '需神秘力量 / 进化等 273 数值系统，服务端零支持。'}[f])
    if c['n'] < 20:
        continue
    H.append(f'<tr><td class="mono">{e(c["key"])}</td><td>{c["n"]}</td><td>{e(c["street"])}</td><td>{e(reason)}</td></tr>')
H.append('</table>')
H.append('<div class="note">上表只列 ≥20 图的大簇（共 %d 个），其余小簇同族同理。</div>'
         % len([c for c in zero if fam_of(c['key']) in ('S1', 'S2', 'S3') and c['n'] >= 20]))

# 组队任务
H.append('<h2>五、74 个组队任务逐条状态</h2>')
H.append('<div class="sub">判定依据：<code>gms-server/scripts-zh-CN/event/</code> 下 121 个脚本 + 地图覆盖。<b>已有</b> = 脚本或内容在；'
         '<b>缺失</b> = 两端都没有；<b>半成品</b> = 地图在、逻辑不在。</div>')
H.append('<table><tr><th style="width:60px">ID</th><th style="width:220px">名称</th><th style="width:90px">状态</th>'
         '<th style="width:220px">BeiDou 既有证据</th><th>可行性</th></tr>')
for pid, name, status, proof, feas in PQ:
    cls = {'已有': 'ok', '已有（本次补齐）': 'ok', '已有/待核': 'warn', '部分': 'warn',
           '半成品': 'warn', '缺失': 'no'}.get(status, 'warn')
    H.append(f'<tr><td class="mono">{e(pid)}</td><td>{e(name)}</td>'
             f'<td><span class="tag {cls}">{e(status)}</span></td><td class="mono">{e(proof)}</td><td>{e(feas)}</td></tr>')
H.append('</table>')

# 落地顺序
H.append('<h2>六、建议落地顺序</h2>')
H.append('<table><tr><th style="width:50px">批次</th><th style="width:200px">内容</th><th style="width:90px">工作量</th><th>交付物 / 注意</th></tr>')
BATCH = [
 ('1', 'CWKPQ boss 段 + 維京飛行船 + 露塔必思庭園', '约 31 图',
  '地图 + 中文树名字；先核 BeiDou 现有 CWKPQ / RootAbyss 用的是哪套 ID，避免撞号。'),
 ('2', '龍騎士組隊任務（1210）', '50 图 + 1 脚本',
  '0 新怪 0 新 NPC，最干净的一档；脚本照 LudiPQ.js 骨架，<code>mobTime=0</code> 的图必须 <code>eim.schedule</code> + <code>instanceMapRespawn()</code>。'),
 ('3', '夏摩斯護送（1218）+ 健太護送（1214）', '91 图 + 8 新怪',
  '护送逻辑自写（TMS 无脚本）；护送失败判定、NPC 路径要实测。'),
 ('4', '岩壁巨人（1340）+ 妖精學院（1328）', '33 图 + 4 怪 6 NPC',
  '部位战与教学型副本，机制与扎昆 / EllinPQ 同族，可复用。'),
 ('5', '苦痛迷宮补齐（分 4 批）', '约 116 图 + 8 新怪',
  '每批 30 张，逐批 <code>!debug map</code> 验收；这是任务引用数最高的内容，补完收益最大。'),
 ('6', '嚼嚼 / 啾啾島、湯寶寶、怪物競技', '31 图 + 8 怪',
  '小游戏机制需自研，建议先做简化版（收集 → 交货）。'),
 ('7', '（可选）新東京 / 日本區', '88 图 + 27 怪 28 NPC',
  '最贵的一档，建议拆「東京都廳」与「2100 年台場」两批，先做前者。'),
]
for b, name, work, deliv in BATCH:
    H.append(f'<tr><td><b>{b}</b></td><td>{e(name)}</td><td>{e(work)}</td><td>{e(deliv)}</td></tr>')
H.append('</table>')

H.append('<div class="key"><h3>迁移前的三条硬前提</h3><ul>'
         '<li><b>中文树必须同步。</b><code>WZFiles</code> 优先读 <code>wz-zh-CN/</code>，而 <code>wz-zh-CN/</code> 只有 Etc / Quest / String 三棵——String（地图名、怪物名、NPC 名、道具名）漏改就会显示空白。</li>'
         '<li><b>副本自刷怪。</b>事件实例的 <code>MapManager</code> 拿不到 <code>RespawnTask</code> 的 tick，凡是 <code>mobTime=0</code> 的点，脚本必须 <code>eim.schedule(fn, 5000)</code> + <code>map.instanceMapRespawn()</code>，否则清场后永不重生。</li>'
         '<li><b>ID 一律 8 位补零。</b>查存在性用 7 位会假阴性（已踩两次）。怪物完整源在 <code>~/Documents/mxd/TMS/ms-extract/Mob_0000X/</code>，'
         '<code>MapleStory-IMG/Data/Mob/</code> 只有 <code>_Canvas</code> 没有 info。</li></ul></div>')

H.append('<div class="note">本报告数据来源：TMS 18,888 张地图 info 全量扫描 + 182 个缺失簇逐图 <code>life</code> 解析 + BeiDou 6,336 张地图 / Mob / Npc 集合比对。'
         '生成脚本：<code>tool/scripts/migration/eval_missing_content.py</code> + <code>render_missing_eval.py</code>（只读，未改动任何客户端或服务端文件）。</div>')
H.append('</div></body></html>')

open(OUT, 'w').write('\n'.join(H))
print('written', OUT, os.path.getsize(OUT), 'bytes')
print('完全缺失簇', len(zero), '地图', sum(c['n'] for c in zero), '| 部分', len(part), '| 完整', len(full))
for fid, name, *_ in FAMILY:
    print(' ', fid, name, fam_stat.get(fid, {'n': 0, 'maps': 0}))
