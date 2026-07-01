 

## 客户端 WZ 打包注意事项

如果把客户端 `Data` 目录下的散 `.img` 重新打包成根目录下的 `*.wz`，不能只把每个子目录分别打成 `Character.wz`、`Skill.wz` 等文件，还需要特别处理 `Base.wz`。

`Base.wz` 必须同时包含两类内容：

- `Data` 根目录下的 `.img` 文件，例如 `StandardPDD.img`、`smap.img`、`zmap.img`
- `Data` 下一级目录的空目录索引，例如 `Character`、`Effect`、`Item`、`Map`、`Mob`、`Skill`、`UI` 等

如果 `Base.wz` 只包含根目录 `.img`，缺少这些一级目录索引，客户端可能在启动早期报错，例如 `0x80030002`。

推荐使用脚本：

```shell
rtk tool/scripts/package/pack_img_wz.sh
```

选择“全部目录”时，脚本会自动生成正确结构的 `Base.wz`，并把各一级目录分别打包成对应的 `*.wz`。

另外，根目录运行库 `ijl15.dll` 和 `2ijl15.dll` 需要成套匹配。`ijl15.dll` 是客户端加载的 JPEG 库代理/补丁 DLL，`2ijl15.dll` 是实际的 Intel JPEG Library。如果这两个 DLL 版本不匹配，客户端可能在启动或加载资源阶段直接报错。遇到启动期资源错误时，除了检查 WZ，也要确认这两个 DLL 来自同一套可运行客户端。


# 095 内容迁移记录

来源目录：`/Users/lizixian/Documents/mxd/怀旧岛V095仿官版/怀旧岛V095服务端`。本次仅做资源与脚本盘点，未直接迁移文件。

迁移操作手册、踩坑记录和下一批进阶黑龙检查清单见：[095 内容迁移手册](095-migration.md)。

## 差异概览

与当前 beidou 资源相比，095 服务端 WZ 大约多出：

- 怪物：575 个
- 地图：703 张

095 是 Windows 成品包，`ZeroMS/095.jar` 不是普通 JVM 可直接加载的 jar，直接 `java -cp ZeroMS/095.jar:lib/* server.Start` 会报 `ClassFormatError`。因此更现实的路线是把可读的 WZ、脚本、入口 NPC 逐步迁入 beidou，而不是迁移 095 服务端本体。

## 优先迁移目标

### 第一批：进阶扎昆

适合作为迁移试点，资源范围小，现有 beidou 已有普通扎昆逻辑可参考。

- 怪物：`8800100-8800116`
- 地图：`211042301` 进阶扎昆入口、`280030001` 进阶扎昆的祭台
- 095 脚本：`scripts/event/ChaosZakum.js`
- beidou 参考：`scripts/event/ZakumBattle.js`

### 第二批：进阶暗黑龙王

可以参考 beidou 现有普通龙王事件，主要补充进阶龙王怪物、地图与召唤流程。

- 怪物：`8810100-8810130`
- 地图：`240060001`、`240060101`、`240060201`
- 095 脚本：`scripts/event/ChaosHorntail.js`
- beidou 参考：`scripts/event/HorntailBattle.js`

### 第三批：希纳斯 / 未来之门

内容价值高，但依赖范围比前两批大，需要整套地图、怪物、NPC、入口与事件脚本配合。

- 怪物：`8850000-8850013`，包含米哈尔、奥兹、伊莉娜、伊卡尔特、胡克、神兽、希纳斯
- 地图：`271000000` 起的未来之门、破坏的射手村、骑士团要塞；重点入口 `271040000`、`271040100`
- 095 脚本：`scripts/event/CygnusBattle.js`

### 第四批：埃德尔斯坦 / 反抗者区域

地图资源相对完整，但如果继续迁职业、技能、任务链，成本会明显提高。

- 地图：`310000000` 起，包含埃德尔斯坦、反抗者本部、莱班矿山、格里梅尔研究所
- 注意：反抗者职业相关逻辑可能涉及客户端、技能、任务、包处理，不建议作为第一批迁移内容。

## 暂缓迁移内容

以下内容在 095 脚本中存在，但实际 WZ 资源不完整或与当前版本跨度较大，暂不作为第一批目标：

- Hilla：`scripts/event/HillaBattle.js`，引用 `262030300`、`8870000`
- Arkarium：`scripts/event/ArkariumBattle.js`，引用 `272020200`、`8860000`
- Magnus：`scripts/event/BossMagnus_HARD.js`，引用 `401060100`、`8880000`
- Root Abyss 四 Boss：`BossBanban_CHAOS.js`、`BossBelen_CHAOS.js`、`BossBloody_CHAOS.js`、`BossPierre_CHAOS.js`

这些脚本更像高版本内容混入或残留，迁移前需要先确认客户端 WZ、服务端 WZ、包结构和入口 NPC 是否完整。

## 迁移注意事项

- 服务端和客户端 WZ 必须同步迁移；只拷服务端 XML，客户端缺素材时会黑图、缺怪或闪退。
- beidou 脚本风格偏 HeavenMS/Cosmic，095 脚本偏老 Odin 风格。095 中的 `em.getMonster(...)`、`setInstanceMap(...)`、`disposeIfPlayerBelow(...)` 等调用需要按 beidou 现有事件脚本改写。
- 先迁一个闭环 Boss：地图 XML、怪物 XML、String 名称、NPC/反应堆入口、event 脚本、掉落/奖励，再进游戏验证。
- Tokyo、拉瓦那、马来西亚等内容 beidou 已有较多资源，优先级低于上述新增 Boss 和地图。

## 第一批迁移：进阶扎昆

已把进阶扎昆闭环迁入 beidou，入口从 `211042301` 进入 `211042401`，由 NPC `2030016` 创建 `CHAOS_ZAKUM` 远征，事件 `ChaosZakum` 进入 `280030001`，通过反应堆 `2111101` 召唤 `8800100` 假身和 `8800103-8800110` 手臂。

本批次补充的服务端内容：

- 地图 XML：`211042301`，并把 `211042401` 回退目标改到 `211042301`
- NPC/反应堆 XML：`2030016`、`2111101`
- 脚本：`scripts/event/ChaosZakum.js`、`scripts/npc/2030016.js`、`scripts/reactor/2111101.js`，并适配 `portal/Zakum05.js`
- Java：补充进阶扎昆 MobId、远征 bosslog、Zakum 假身/手臂判定对进阶扎昆的支持
- DB：`V2.1.17__add_chaos_zakum_bosslog.sql`，给 bosslog enum 增加 `CHAOS_ZAKUM`

本批次补充的客户端内容：

- 从 095 客户端 WZ 直接导出的 IMG：`Map/Map2/211042301.img`、`Map/Map2/211042401.img`、`Reactor/2111101.img`
- 095 客户端 WZ 没有 `Npc/2030016.img`，因此使用同外观的 `2030013.img` 导出后作为 `2030016.img`
- `String/Npc.img` 由 beidou 已更新的 `String.wz/Npc.img.xml` 重建，用于补 `2030016` 文案
- 从 095 WZ 导出的客户端 IMG 需要从 CMS key 转成 beidou 客户端使用的 GMS key，否则客户端进图时可能报 `-2147467261` 无效指针

迁移校验结论：

- 095 客户端 WZ 需要用 CMS IV 才能正确解出明文 IMG 名称。
- 地图/反应堆/NPC 这类直接从 095 WZ 导出的 IMG，落到 `clien/Data` 前必须重新保存为 GMS key。
- 进阶扎昆本体 HP 当前为 `528000000`、`704000000`、`880000000`，未超过 21 亿，本批不需要把服务端 HP XML 改成 `string`。
- 进阶扎昆怪物服务端 XML 使用 `8800100-8800110`，客户端 IMG 已恢复为 095 原始进阶扎昆资源；`MobSkill.img` 中召唤技能 `200/184-194` 在 beidou 客户端和服务端均存在。
- `211042301` 引用的客户端素材 `Back/moltenRock.img`、`Obj/dungeon2.img`、`Tile/moltenRock.img` 在 beidou 客户端已存在。
- `280030001` 祭坛崩溃排查：显式引用的 `Back/moltenRock.img`、`Obj/connect.img`、`Obj/dungeon2.img`、`Tile/moltenRock.img`、`Npc/2030010.img`、`Reactor/2111101.img` 都存在且可用 GMS key 解析，未发现缺文件。
- 为规避 095 导出地图结构在 beidou 客户端中进图闪退，`280030001` 已改为基于 beidou 原 `280030000` 祭坛底座重建，仅保留自循环目标 `280030001` 和反应堆 `2111101`；旧版已备份到 `/private/tmp/280030001.before-compat.img(.xml)`。
- 普通扎昆祭坛对比后，服务端 `280030001` 与 `280030000` 地图只剩地图名、自循环传送目标和反应堆 ID 差异；客户端 `Reactor/2111101.img` 已改为完全复用普通祭坛 `2111001.img` 的兼容资源，服务端 XML 也只保留根节点 `2111101.img` 的差异，旧版备份到 `/private/tmp/2111101.before-compat.img(.xml)`。
- 进一步排查发现，由服务端 `media=NONE` XML 重建的客户端 `280030001.img` 缺少普通祭坛客户端 IMG 中的 `miniMap/canvas`，表现为 `decoded_canvases=0`；已改为直接复制普通 `280030000.img` 作为客户端 `280030001.img`，确保 `decoded_canvases=1`，旧版备份到 `/private/tmp/280030001.no-minimap-canvas.img`。
- 召唤后闪退排查：进图阶段已排除地图/反应堆显式资源缺失，召唤阶段新增加载 boss 血条 UI 和 `String/Mob`。实际缺口是客户端 `String/Mob.img` 缺少 `8800100-8800110` 名称，且 `UIWindow/MobGage/Mob/8800100-8800102` 原为 1x1 `_inlink` 到 `8800001`。已补客户端 `String/Mob.img` 名称，并把 `UIWindow.img` 中 `8800100/8800101/8800102` 血条 icon 改为实体 25x25 canvas，分别复制 `8800000/8800001/8800002`；服务端 XML 同步为 UOL 映射。临时普通扎昆 mob 替换已撤销，当前 `Mob/8800100-8800110.img` 已恢复为原始进阶扎昆资源，覆盖前状态备份在 `/private/tmp/chaos-zakum-before-resource-fix/`。
- 深度资源审计补齐：逐节点检查了 `211042301`、`211042401`、`280030001` 的 `back/obj/tile/life/reactor/miniMap/portal`，以及 `8800100-8800110` 的 `revive/skill/MobSkill`、召唤怪、UI 血条和 `String/Mob`。补齐项包括：客户端 `280030001.img` 的 portal 目标从 `280030000` 改为自循环 `280030001`、reactor id 从 `2111001` 改为 `2111101`；补客户端和服务端 `String/Mob` 的 `9400407`、`9420604` 名称；发现 `8800108` 原引用的 `MobSkill 114/37` 属于 095 新结构，包含 Beidou 客户端原生 `114` 等级中没有的 `mob/mob0` 特效节点，容易触发客户端“游戏数据不正确”；已撤回硬补的 `114/37`，改为把客户端和服务端 `8800108` 的该技能适配到 Beidou 原生 `114/1`；`9400389.img` 原为空壳 0 canvas，已保留自身 `info` 并补入 `9400387` 的显示动作，避免 `MobSkill 200/189` 召唤后加载空资源。深度审计最终结果：`ok=536 warn=6 fail=0`，6 个 warning 均为相关地图没有 `obj/tile/tS` 节点，属于未使用对应层级资源。覆盖前备份在 `/private/tmp/chaos-zakum-before-deep-audit-fix/`。
- 已用 OpenJDK 21 执行 `mvn -pl gms-server -DskipTests compile`，编译通过。

## 第二批迁移：进阶暗黑龙王

已把 095 进阶暗黑龙王闭环迁入 beidou。入口复用 NPC `2083004`，现在可选择普通暗黑龙王或 `CHAOS_HORNTAIL` 远征；事件 `ChaosHorntail` 使用 `240060001`、`240060101`、`240060201` 三张地图，前两张地图分别刷 `8810128`、`8810129` 预头召唤怪，最终场通过反应堆 `2401100` 调用 `spawnChaosHorntailOnGroundBelow` 召唤 `8810130`、`8810118` 和 `8810102-8810109` 部件。

本批次补充和适配内容：

- 脚本：`scripts/event/ChaosHorntail.js`、`scripts/reactor/2401100.js`，并扩展 `portal/hontale_BR.js` 支持 `240060001 -> 240060101 -> 240060201`。
- 入口：`scripts/npc/2083004.js` 支持普通/进阶黑龙双模式；`scripts-zh-CN` 同步了 NPC、event、portal、reactor 脚本。
- Java：补充进阶黑龙 MobId、远征击杀日志、`CHAOS_HORNTAIL` bosslog；新增 `spawnChaosHorntailOnGroundBelow`，并让死部件齐全后的本体击杀逻辑同时支持 `8810118`。
- DB：`V2.1.18__add_chaos_horntail_bosslog.sql` 给 bosslog enum 增加 `CHAOS_HORNTAIL`。
- 资源：补齐服务端和客户端 `String/Mob` 的 `8810100-8810109`、`8810118-8810130` 名称；`UIWindow/MobGage/Mob/8810118` 改为 UOL 到普通黑龙血条，避免 1x1 `_inlink` 占位。
- 服务端怪物 XML：给 `8810118`、`8810128`、`8810129`、`8810130` 补 `boss=1`；客户端怪物和地图 IMG 不从服务端 XML 重建，保留现有可解码画布资源。

兼容处理说明：

- 095 地图里的 `hontale_boss1/hontale_boss2` portal 触发方式没有硬搬；当前事件在 `setup()` 中直接刷预头，传送门只根据 `defeatedHead` 放行。
- 进阶黑龙死亡部件仍复用普通黑龙 `8810010-8810017`，因此服务端结算逻辑必须显式寻找并击杀 `8810118`，否则进阶本体不会进入后续阶段。
- 多部件 Boss 不能只看 IMG 文件是否存在。进阶黑龙已确认 `8810100-8810130` 客户端 IMG 均可解析且 canvas 可解码；后续问题主要集中在阶段语义和刷怪层级：`8810118-8810121` 是中间阶段，`die1` 应是小型/透明切换动画，最终大死亡动画只留给 `8810122`。
- 阶段刷新时要清理普通死部件 `8810010-8810017`，再按稳定刷怪路径和固定部件顺序补出 `8810102-8810109`。如果出现部位错位或翅膀跑到前景，优先对比普通版、095 来源和迁移后资源的 `origin/head`，再检查刷怪顺序、parent 关系和是否用错 `spawnMonsterOnGroundBelow`/`spawnMonster`。
- 更完整的迁移流程、进阶扎昆踩坑和进阶黑龙多部件 Boss 调试经验，见 `docs/migrations/095-migration.md`。后续迁新 Boss 时先按该文档做资源、脚本、UI、String、MobSkill、阶段链闭环审计。
- `8810110-8810117` 在 095 来源 WZ 中不存在，本批实际迁移的进阶黑龙资源为 `8810100-8810109`、`8810118-8810130`。

## 第三批迁移：希纳斯 / 骑士团要塞

已迁入 095 的未来之门 / 骑士团要塞闭环资源与入口逻辑。范围包括 51 张 `271xxxxxx` 服务端地图和客户端地图、地图依赖的 `Back/Obj/Tile` 资源、`8600000-8600006`、`8610000-8610022`、`8850000-8850012`、NPC `2142000-2142010`、`2143000/2143001/2143003/2143004`，并补齐 `String/Map`、`String/Mob`、`String/Npc` 与 `MobSkill` 引用。

- 入口 NPC `2143004` 使用当前远征系统创建 `CYGNUS`，事件 `CygnusBattle` 进入 `271040100`，按 095 顺序刷 `8850000 -> 8850001 -> 8850002 -> 8850003 -> 8850004 -> 8850011`。
- 新增并同步 `scripts-zh-CN` 的 Cygnus event、NPC、portal 和 map hook 脚本；portal 保留 095 的任务入口和道具门槛，但改用当前脚本 API。
- Java 侧补 `CYGNUS` 远征、bosslog enum、`8850000-8850013` boss 击杀日志范围，以及 095 希纳斯会引用但当前逻辑暂不实现的 `MobSkill 138/146/171/172` 枚举，避免加载怪物时因未知技能 ID 崩溃。
- 已审计 271 地图引用的 portal/map 脚本、life、back/obj/tile、885 技能 ID。已知兼容警告：`Tile/darkEreb.img` 被 095 地图引用，但 095 来源客户端和当前客户端均没有该文件；本批不伪造该资源，后续进图实测如确认黑块/崩溃再按实际节点补兼容素材。
- `8850012` 是 095 中 4x4 canvas 的希纳斯 revive/占位怪，不是导出失败；`8850013` 当前项目原有并保留。
- 客户端弹出“不正确的游戏数据”时，已确认 095 `Map/Obj/acc14.img` 等素材存在负宽高/异常 fmt canvas。迁移脚本现在会把 EMS canvas 解码后重编码为 GMS payload，无法解码的节点降级为 1x1 透明 canvas。
- `Map/Obj/connect.img` 是当前客户端已有资源，但本身也残留 67 个不可解码/负宽高 canvas。271 地图新增引用 `oS=connect` 后会触发整包加载，所以迁移脚本会对修改后的 `connect.img` 整包重编码并把坏节点降级为 1x1 透明 canvas。
- `MobSkill.img.xml` 已改为按根技能 ID 结构化迁移等级，避免把 `<imgdir name="146">` 这类同名等级节点误判为技能节点；`885` 系列引用的 33 个技能在服务端 XML 和客户端 IMG 均已对齐。
- 本机只有 Java 17，`mvn -pl gms-server -DskipTests compile` 被项目 Java 21 target 拦截，未能完成编译验证；结构审计和 `git diff --check` 已通过。
 
