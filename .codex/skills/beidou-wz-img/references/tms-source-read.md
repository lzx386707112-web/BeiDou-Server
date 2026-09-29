# 读取 TMS 273 解包资源（只读）

迁移任务需要「源数据证据」时，源在 `~/Documents/mxd/TMS/MapleStory-IMG/Data/`
（TMS 273 时代的解包 IMG 树），不是 BeiDou 的 `clien/Data/`。

## 密钥：TMS 用的是 LATEST，不是 BeiDou 那套

`.img` 首字节都是 `0x73`（`withoutOffsetFlag`），但字符串块密钥不同：

| 目标 | IV | userKey |
| --- | --- | --- |
| TMS 273 解包 IMG | `WzAESConstant.WZ_LATEST_IV`（4 字节全 0） | `WzAESConstant.DEFAULT_KEY` |
| BeiDou 客户端 IMG | 项目自己的 WZ 配置 | 同 |

实测字节对照：TMS `73 f8 fa d9 c3 dd cb dd c4 c8 …`，
BeiDou `73 f8 6c 77 fc 79 83 27 19 58 …`——第 3 字节起就分叉。
**把 BeiDou 的解析配置套到 TMS 上会直接 `ERROR_KEY`，反之亦然。**

IV 全 0 时 `WzMutableKey.ensureKeySize` 会让 keys 全 0（等价无 XOR），
所以 TMS 的 IMG 用 `tool/orange-wz` 的 `WzImageFile` 加上面两个常量就能直接 parse。

## 工具

`tool/tms-wz/`（见该目录 README，含编译命令）：

- `ImgJson <in.img> <out.json>`：单文件导出 JSON，`JsonExport` 自动过滤
  canvas / `_outlink` / `_Canvas` 外链，只留标量节点。
- `QuestScan <QuestData目录> <out.tsv>`：单 JVM 内批量扫描全部任务，
  输出 `id \t name \t area \t reqType \t lvmin \t lvmax \t npc`，全量约 1 分钟。
  **不要每文件起一次 JVM。**

## 找内容时先看索引，不要先扫地图

地图目录（`Map/Map/Map0..Map9`，约 1.9 万个 img）里没有「分类」信息，
靠名字关键字捞副本会大量漏报。TMS 把分类写在这几个索引文件里：

| 文件 | 作用 |
| --- | --- |
| `Quest/PQuest.img` | 组队任务 / 内容目录主表：名称即条目键，`info` 下有
`levelMin` / `recommendationLevelMin|Max` / `memberMin|Max` / `difficulty` / `fieldSet` / `timeOut` / `desc` |
| `Etc/ContentsGuide.img` | 游戏内「内容向导」，顶层 `career` / `field` / `boss` / `special` / `requireQuest` / `rankReward` / `levelReward`；`special.*` = `{story, growth, arcane, competition}` |
| `Etc/ContentsQuestCategory.img` | 任务 UI「副本目录」四个页签：1 主題副本 / 2 Boss目錄 / 3 組隊任務 / 4 特別項目 |
| `String/mirrorDungeon.img` | 镜像副本条目：`name` / `desc` / `level` / `disable`（开放章节） |
| `Etc/mirrorDungeonMap.img` | 镜像副本 → 地图 ID 的二维网格（`x`,`y`,`map`） |
| `Etc/mirrorDungeonEnter.img` | 入口地图 → 条目 → `recordID` / `day` / `quest` |
| `Quest/QuestData/*.img` | 全量任务。`QuestInfo/name` 前缀（`[主題副本]` / `[史詩副本]` / `[組隊任務]`）+ `Check/0/lvmin` 是最可靠的分类依据 |
| `Etc/ContentsShortcut.img` | 内容快捷入口（BossArena / CrossHunter / ItemPot / Bits …） |

`QuestInfo` 只有 `name` / `0,1,2`（文案）/ `area` / `reqType`，
**没有** `contents` 之类的分类字段——分类只能靠 `name` 前缀。
组队/剧情任务的 `area` 通常是 `49`（pquest）或 `248`（史诗副本），
可用作二次校验。

`Etc/` 目录名本身就是内容清单：`MonsterPyramid`、`Roguelike`、
`AbyssExpedition*`、`MExplorer*`、`CrossBrigade2_FloorData` / `CrossBrigade3_*`、
`JinHillah`、`MazeData`、`Redmoon`(String)、`GuildCastle`、`monsterParkExtreme`、
`mirrorDungeon*` 等各自对应一套独立副本玩法。

盘点结果见 `docs/TMS副本玩法盘点.html`（258 条，10 个分类）。
玩法逻辑深挖见 `docs/TMS副本玩法深度解析.html`（252 条，8 种结构型 + 脚本索引）。

## ★ 副本「玩法逻辑」写在 Map info 里，用 MapScan 全量扫

要回答「这个副本怎么玩」，权威证据不是名字，而是每张地图的 `info`：

| 字段 | 含义 | 为什么关键 |
| --- | --- | --- |
| `fieldScript` | 场地脚本名 | **服务端同名 `.js` 就是该副本的逻辑本体**（如 `MonsterPark` / `MDojang_KillMob` / `guildD_Culvert` / `mirrorDungeon` / `prisonBreak` / `shammosPQ` / `RPDungeon`） |
| `onFirstUserEnter` / `onUserEnter` | 首次/每次进入脚本 | 阶段提示、召唤、结算（如 `mPark_stageEff` / `dojang_Msg` / `Massacre_result`） |
| `timeLimit` | 限时（秒） | 只有 140 张图有；有限时的基本就是挑战类 |
| `forcedReturn` | 失败/退出回退图 | 同一副本的所有阶段共享同一个 `forcedReturn` ⇒ 可据此把散落的地图**聚成一个副本** |
| `fieldType` | 场地类型码 | 14=道场层、24=大乱斗结算、25/26=海贼船作战室、128~135=赏金猎人各关、255/258=公会水道 |
| `link` | 复用另一张图的几何 | 阶段图大量 `link` 到同一模板，只是换 mob，**不要**据此判定为重复副本 |

工具 `tool/tms-wz/MapScan.java`（用法同 QuestScan，单 JVM 跑完 **18 888 张地图约 25 秒**）：

```
java -cp "<orange-wz>/target/classes:<orange-wz>/target/dependency/*:/tmp/tms-wz" \
     MapScan <Map/Map 目录> <out.tsv>
```

输出 4 列：`mapId \t info的k=v;... \t portal(name>target,...) \t mob数/npc数`。

**判副本归属的经验规则**（按可靠性排序）：
1. 同 `fieldScript` + 同 `forcedReturn` ⇒ 同一副本的不同阶段/房间；
2. `fieldType` 相同且在连续 ID 段内 ⇒ 同一系统；
3. 地图段（前 3 位）：`993xx` 赏金猎人（5122 张，最大段）、`954xx` 怪物公园、`92502/92507xx` 武陵道场、
   `9406xx` 公会水道、`993xxx` Polo&Fritto、`867xx` 深渊远征队/M探险、`875xx` 红月 Roguelike；

**不要**用「固定脚本名向前搜 `E8`」之类的启发式去推断——直接读 `info` 的原始字段。

### 关卡配置文件（`Etc/*.img`）——机制的第二证据源

这些文件把「几层、几阶段、几%、什么条件」写死在客户端，是最接近玩法说明的东西：

| 文件 | 结构要点 |
| --- | --- |
| `ContentsGuide.img` → `special.{story,growth,arcane,competition}` | **每个玩法都有官方一句话 `desc`**，直接引用即可 |
| `CrossBrigade2_FloorData.img` | 13 层楼，每层 `rewardPoint` / `requireQuestID` / `clearCountQuestRecordID` |
| `CrossBrigade3_Acts.img` / `_Raid.img` | Act/Raid 各绑 `script` + `UnlockQst` + `ClearQst` |
| `JinHillah.img` | `soulCripple` 阶段 0/1/2 → `hp` 100/60/30（%）+ skillID |
| `DreamBreaker.img` | `stageTime=180` / `maxGauge=1000` / `awakenMobID` 与 `sleepMobID` 各 5 个 |
| `RPDungeonMap.img` | **节点图**（`x`,`y`,`map`,`boss`,`randomType`）⇒ 随机迷宫 |
| `RPDungeonStat.img` / `RPDungeonAttackCharacter.img` | 进场后套用的固定角色素质与装备 |
| `MazeData.img` | 迷宫分区（如 `blackHeaven` 的 `D1_Z05`…），格点带 `type`/`name`/`mob` |
| `MonsterPyramid.img` | `timeLimit` / `timeLimitAI` / `msg`（回合、罚金、退场） |
| `MuruengExpField.img` | `provideExpSec=5` / `timeReduceSec=60` / `outMapID` |
| `AbyssExpeditionConfig.img` | `slotCooltime` / `levelPlaytime` / `bossMap` / `MercenaryGachapon` |
| `MExplorer.img` / `Roguelike.img` / `GuildCastle.img` | ability·recipe / 独立角色常量 / ResearchTree |

**客户端的边界**：血量、伤害、掉落、奖励概率、入场次数、Boss 招式时序
**不在客户端**，别在 IMG 里找，直接看服务端脚本与数据库。

## 脚本层：TMS 客户端**不含任务脚本**（硬事实）

`find ~/Documents/mxd/TMS -iname "*.js" | wc -l` → **0**。TMS 目录是纯客户端安装
（`MapleStory.exe` + `Data/` + DLL），`Quest/QuestData/*.img` 里只有
`Check/{n}/startscript|endscript` 的**脚本文本名**（如 `q31903s`），
**脚本本体在服务端**。所以「把 TMS 的原版流程脚本抠出来」这条路是封死的。

能拿到的只有「流程」：任务名 / 三句说明 / 前置（`Check/quest` 的 `id`+`state`）/
要求 NPC·等级·道具·怪物数 / 奖励 EXP / 脚本名。按 `Check/quest` 串起来就是完整流程说明书。

## BeiDou 服务端怎么找脚本（决定「缺脚本」的实际后果）

| 类型 | 服务端查找路径 | 缺失时行为 |
| --- | --- | --- |
| 任务脚本 | `QuestScriptManager.getQuestScriptEngine` → **按任务 ID** 取 `scripts[-zh-CN]/quest/<questid>.js`（**不是** `startscript` 的值当文件名！） | `QuestActionHandler`：`hasScriptRequirement && checkFunctionExists` 都真才走脚本，否则回退 `quest.start(player,npc)` ⇒ **任务照样能接/能交，只是跳过脚本化过场** |
| NPC 脚本 | `scripts/npc/<npcid>.js` | 无则走默认对话/任务列表 |
| 场地脚本 | `scripts/map/onUserEnter/<name>.js`、`map/onFirstUserEnter/<name>.js`（`MapleMap` 用 `info/onUserEnter` 的值拼路径） | 无则静默不触发 |
| 服务器级自检 | `org.gms.service.MapDetectService.checkFieldScript` 报 `WARN 脚本缺失`；REST `POST /map/latest/detect` | — |

## 副本完整性核对套路（六层）

做「某某副本能不能玩完整」这类问题时，逐层列证据，**不要只看地图在不在**：

1. **地图资源**：对比地图段 ID 集合（TMS vs `clien/Data/Map`），注意排除 `_Canvas/` 目录；
2. **任务定义**：`QuestInfo/Check/Act/Say` **四个 XML 都要查**（是拆开的，只看 QuestInfo 会误判成"残缺"）；
3. **脚本钩子**：`Check.img.xml` 里 `startscript`/`endscript` 是否被剥离（仓库全域有 400+ 个，别拿 0 当正常）；
4. **任务脚本文件**：`scripts-zh-CN/quest/<id>.js`（两棵树 `scripts/` 与 `scripts-zh-CN/` 都要查）；
5. **NPC 脚本**：先从地图 `life` 里取实际刷出的 NPC id，再逐个查；
6. **地图 info 字段差异**：把 TMS 的 `mapinfo.tsv` 与仓库侧用 wzpy 解析出的 `info` 逐键比，
   `lvLimit` / `onUserEnter` / `fieldScript` 是最容易丢的三个。

⚠️ 用 wzpy 对比地图 info 时，**别只挑几个 key 打印**——曾经因为只 print 了 11 个 key 而误判
「仓库图缺 VRTop/mobRate」。要么全量 dict 对比，要么把 key 列表列全。
⚠️ 仓库 2730 段地图**没有 `standAlone`/`partyStandAlone`/`noMapCmd`/`fieldType=0`**——
这些 TMS 侧值是 0，缺失等价，不算缺口；但 `lvLimit=180` 与 `onUserEnter` 缺失是实打实的。
