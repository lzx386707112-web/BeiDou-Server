# tms-wz —— 只读 TMS 273 资源读取工具

用来读取 `~/Documents/mxd/TMS/` 下的 TMS 客户端解包资源（`.img`），
用于给 BeiDou 迁移任务提供**源数据证据**（任务、地图、字符串、内容目录）。

本目录工具**只读**，不写任何客户端文件。

## 关键前提：TMS 273 的 IMG 用哪套密钥

TMS 273 的 `.img` 直接以 `0x73`（`withoutOffsetFlag`）开头，字符串块用
**`WZ_LATEST_IV`（4 字节全 0）+ `WZ_AESConstant.DEFAULT_KEY`** 解出。
两者都在 `tool/orange-wz` 里，所以**不需要额外找密钥盒**：

```java
new WzImageFile(name, path, "t", WzAESConstant.WZ_LATEST_IV, WzAESConstant.DEFAULT_KEY)
```

反例：BeiDou（GMS 083）客户端 `clien/Data/*.img` 的首字节同样是 `0x73`，
但第 3 个字节起就与 TMS 不同（`73 f8 6c 77 …` vs `73 f8 fa d9 …`），
说明两者密钥/IV 不同。**不要拿 BeiDou 的解析配置去读 TMS，反之亦然。**

## 编译

先确保 `orange-wz` 已编译（存在 `target/classes` 与 `target/dependency`）：

```sh
cd tool/orange-wz && JAVA_HOME=/opt/homebrew/opt/openjdk@21 mvn -o -q compile
```

然后编译本目录工具：

```sh
mkdir -p /tmp/tms-wz
/opt/homebrew/opt/openjdk@21/bin/javac -proc:none \
  -cp "tool/orange-wz/target/classes:tool/orange-wz/target/dependency/*" \
  -d /tmp/tms-wz tool/tms-wz/*.java
```

## 用法

### 1. 单个 IMG 导出为 JSON

```sh
/opt/homebrew/opt/openjdk@21/bin/java -Xmx2g \
  -cp "/tmp/tms-wz:tool/orange-wz/target/classes:tool/orange-wz/target/dependency/*" \
  ImgJson <输入.img> <输出.json>
```

`JsonExport` 会自动过滤 canvas / `_outlink` / `_Canvas` 外链等图片资源，
只留下服务端关心的标量节点，导出体积可控。

### 2. 批量扫描 QuestData（24 879 条）

输出 TSV：`id \t name \t area \t reqType \t lvmin \t lvmax \t npc`

```sh
/opt/homebrew/opt/openjdk@21/bin/java -Xmx2g \
  -cp "/tmp/tms-wz:tool/orange-wz/target/classes:tool/orange-wz/target/dependency/*" \
  QuestScan ~/Documents/mxd/TMS/MapleStory-IMG/Data/Quest/QuestData /tmp/tmsdump/quests.tsv
```

单 JVM 内循环解析，全量约 1 分钟。**不要每个文件起一次 JVM**，25000 个文件会慢到不可用。

### 3. 批量扫描 Map info（18 888 张，约 25 秒）

输出 TSV：`mapId \t info的k=v;... \t portal \t mob数/npc数`

```sh
/opt/homebrew/opt/openjdk@21/bin/java -Xmx2g \
  -cp "/tmp/tms-wz:tool/orange-wz/target/classes:tool/orange-wz/target/dependency/*" \
  MapScan ~/Documents/mxd/TMS/MapleStory-IMG/Data/Map/Map /tmp/tmsdump/mapinfo.tsv
```

这是**还原副本玩法逻辑**的主要工具：`info` 里的 `fieldScript` / `onFirstUserEnter` /
`onUserEnter` / `timeLimit` / `forcedReturn` / `fieldType` 直接给出「谁在驱动这个副本、
限时多久、失败回到哪、场地类型是什么」。服务端只要有同名 `.js`，就是该副本的逻辑本体。

## 内容盘点该看哪些文件

TMS 的「副本玩法」不是靠地图目录扫出来的，而是这几个索引文件：

| 文件 | 作用 |
| --- | --- |
| `Quest/PQuest.img` | 组队任务 / 内容目录主表（名称、等级、人数、难度、`fieldSet`、限时） |
| `Etc/ContentsGuide.img` | 游戏内「内容向导」：`special.{story,growth,arcane,competition}` + `boss` + `field` + `career` |
| `String/mirrorDungeon.img` | 镜像副本条目：`name` / `desc` / `level` / `disable`（开放章节） |
| `Etc/mirrorDungeonMap.img` | 镜像副本 → 实际地图 ID 的二维网格 |
| `Etc/mirrorDungeonEnter.img` | 镜像副本入口地图 → 条目 → `recordID` / 开放 `day` / 触发 `quest` |
| `Etc/ContentsQuestCategory.img` | 任务 UI「副本目录」分类：1 主題副本 / 2 Boss目錄 / 3 組隊任務 / 4 特別項目 |
| `Quest/QuestData/*.img` | 全部任务；`QuestInfo/name` 前缀（`[主題副本]` / `[史詩副本]` / `[組隊任務]`）+ `Check/0/lvmin` 是最可靠的分类依据 |
| `Etc/ContentsShortcut.img` | 内容快捷入口（BossArena / CrossHunter / ItemPot / Bits …） |

## 玩法逻辑的第二证据源：`Etc/*.img` 关卡配置

| 文件 | 结构 |
| --- | --- |
| `ContentsGuide.img` → `special.*` | 每个玩法带官方一句话 `desc` |
| `CrossBrigade2_FloorData.img` / `CrossBrigade3_Acts.img` / `_Raid.img` | 楼层 / Act / Raid + `UnlockQst` / `ClearQst` |
| `JinHillah.img` | `soulCripple` 阶段 → `hp` 100/60/30(%) |
| `DreamBreaker.img` | `stageTime` / `maxGauge` / `awakenMobID` / `sleepMobID` |
| `RPDungeonMap.img` / `RPDungeonStat.img` | 随机迷宫节点图 / 进场固定素质 |
| `MazeData.img` | 迷宫分区格点（`type`/`name`/`mob`） |
| `MonsterPyramid.img` | 回合限时与罚金文案 |
| `MuruengExpField.img` / `AbyssExpeditionConfig.img` | 经验场 / 派遣制参数 |
| `MExplorer.img` / `Roguelike.img` / `GuildCastle.img` | 能力树 / 独立角色常量 / 公会研究树 |

产物示例：
- `docs/TMS副本玩法盘点.html` —— 258 条清单（索引文件汇总）
- `docs/TMS副本玩法深度解析.html` —— 252 条玩法卡（8 种结构型 + 关卡链 + 脚本索引）
