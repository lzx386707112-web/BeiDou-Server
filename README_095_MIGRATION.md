# 095 内容迁移手册

本文记录从 `怀旧岛V095仿官版` 向 BeiDou 迁移内容时的正确流程、进阶扎昆踩坑，以及后续迁移进阶黑龙时需要复用的检查方法。

目标不是“把文件拷过去能进图就算完”，而是建立一个可复用的闭环：客户端资源、服务端 XML、脚本、入口、UI、String、召唤链、技能特效都要一起验证。

## 核心原则

- 客户端 `clien/Data` 和服务端 `gms-server/wz` 必须同步迁移。只改服务端 XML，客户端缺资源会黑屏、闪退、报“游戏数据不正确”。
- 095 来源是 WZ，BeiDou 客户端使用散 IMG。迁移客户端资源时要先从 095 WZ 导出 IMG，再保存成 BeiDou 客户端可读的 GMS key。
- 不要直接相信“文件存在”。要确认 IMG 能解析、canvas 能解码、引用的子资源也存在。
- 不要把高版本节点硬搬进 BeiDou。095 的部分 MobSkill、地图、反应堆节点结构可能超出当前客户端可识别范围，硬补会导致进图或召唤后崩溃。
- 先做稳定闭环，再逐层恢复视觉。地图崩溃时，优先保留可运行的 portal/reactor/life/miniMap 结构，再分层迁回 `back/obj/tile`。
- 每次迁移都要保留覆盖前备份，至少保存到 `/private/tmp`，方便快速回滚和差异比较。

## 标准迁移流程

### 1. 先确定闭环范围

迁 Boss 前先列清楚这些内容：

- 入口地图、等待地图、战斗地图、退出地图
- 入口 NPC、传送脚本、portal 脚本、reactor 脚本
- event 脚本和远征类型
- Boss 本体、阶段、部件、召唤怪、死亡怪
- `String/Mob`、`String/Npc`、`String/Map`
- Boss 血条 UI：`UIWindow/MobGage/Mob/<mobId>`
- `MobSkill` 技能等级、召唤表、技能特效引用
- 地图 `back/obj/tile/life/reactor/miniMap/portal`

不要只迁主 Boss ID。进阶扎昆这次真正导致问题的资源缺口，很多都不在主 Boss IMG 里，而是在 String、UI、MobSkill 召唤怪和地图结构中。

### 2. 导出和转换客户端 IMG

095 客户端 WZ 需要用 CMS IV 才能正确读取明文 IMG 名称。导出后放入 BeiDou 前，需要改成 BeiDou 客户端可读的 GMS key。

迁移后的客户端 IMG 至少要做三项验证：

- IMG 文件可以用 GMS key 解析。
- 所有 canvas 可以解码，不能只有空壳节点。
- 关键资源的 canvas 数量合理。例如地图至少应有 `miniMap/canvas` 或其他实际画布，怪物动作不能是 0 canvas 空文件。

进阶扎昆踩坑：由服务端 `media=NONE` XML 重建客户端地图时，可能丢失真实 canvas。`280030001.img` 曾经表现为 `decoded_canvases=0`，进图会崩。

### 3. 迁服务端 XML 和脚本

服务端要补齐：

- `gms-server/wz/Map.wz/...`
- `gms-server/wz/Mob.wz/...`
- `gms-server/wz/Npc.wz/...`
- `gms-server/wz/Reactor.wz/...`
- `gms-server/wz/String.wz/...`
- `gms-server/wz/UI.wz/...`
- `scripts/event`
- `scripts/npc`
- `scripts/reactor`
- `scripts/portal`
- 需要远征时，补 Java 常量、远征枚举、bosslog、DB migration

095 脚本通常不能原样放进 BeiDou。095 偏 Odin 风格，BeiDou 偏 HeavenMS/Cosmic 风格，需要按现有脚本 API 改写。

### 4. 检查地图引用

逐节点检查地图：

- `back`：检查 `bS` 指向的 `Map/Back/*.img`
- `obj`：检查 `oS/l0/l1/l2` 指向的 `Map/Obj/*.img` 子节点
- `tile`：检查层级 `info/tS` 指向的 `Map/Tile/*.img`
- `life`：检查 mob/npc ID 对应客户端 IMG、服务端 XML、String
- `reactor`：检查 reactor ID 对应客户端 IMG、服务端 XML、脚本
- `miniMap`：检查 `canvas` 是否存在并可解码
- `portal`：检查 `tm/tn/script` 是否指向正确地图或脚本

地图能进不代表地图完整。召唤后才崩时，往往是 Boss UI、String、MobSkill、召唤怪或血条资源缺失。

### 5. 检查怪物引用

逐个 Boss/部件检查：

- `info/maxHP`、`level`、`boss`、`firstAttack`
- `revive` 链是否指向下一阶段或死亡怪
- `skill` 中每个 `skill/level` 是否在 BeiDou 客户端和服务端 `MobSkill.img` 中存在
- `MobSkill 200` 的召唤怪是否都有客户端 IMG、服务端 XML、String
- 每个动作 canvas 是否能解码
- Boss 血条 `UIWindow/MobGage/Mob/<mobId>` 是否存在

HP 超过 21 亿时，服务端 XML 的 HP 需要使用 `string` 标记，客户端用多管血处理。进阶扎昆当前三阶段 HP 为 `528000000`、`704000000`、`880000000`，没有触发这个问题。迁进阶黑龙时必须重新检查。

### 6. 分阶段进游戏验证

推荐验证顺序：

1. 能通过入口 NPC 创建远征。
2. 能进入等待地图。
3. 能进入战斗地图，不召唤。
4. 能触发 reactor 或脚本召唤。
5. Boss 出现后不崩，血条显示正常。
6. Boss 使用技能、召唤怪时不崩。
7. 阶段切换、死亡、清场、退出都正常。

每一步只改少量内容。出现崩溃时，记录“进图前崩、进图后崩、召唤瞬间崩、出血条崩、放技能崩、召唤小怪崩”，不同时间点对应完全不同的排查方向。

## 进阶扎昆踩坑记录

### 1. 095 IMG key 不兼容

现象：客户端进图报无效指针或直接崩。

原因：从 095 WZ 导出的 IMG 是 CMS key，BeiDou 客户端读取 `clien/Data` 时需要 GMS key。

正确做法：导出后统一转换为 GMS key，再放入 `clien/Data`。

### 2. 服务端 XML 重建客户端 IMG 会丢 canvas

现象：地图资源文件存在，但进图黑屏或闪退。

原因：服务端 XML 通常是 `media=NONE`，不包含真实图片数据。用它重建客户端 IMG 会得到结构完整但画布缺失的空壳。

正确做法：客户端 IMG 必须来自客户端 WZ 或已有客户端 IMG；服务端 XML 只给服务端读，不要当客户端素材来源。

### 3. 地图显式资源存在，不代表结构兼容

现象：`280030001` 的 `Back/Obj/Tile/Npc/Reactor` 都存在，但进图仍崩。

原因：095 地图结构与 BeiDou 客户端不完全兼容，尤其是 `miniMap/canvas`、portal、reactor、层级节点等。

正确做法：先用 BeiDou 已稳定的普通祭坛 `280030000` 作为底座，改成进阶地图 ID、自循环 portal、进阶 reactor。确认能进图后，再逐层迁回 095 视觉层。

### 4. Reactor 视觉先兼容，行为走脚本

现象：095 进阶祭坛 reactor 直接迁入容易触发客户端问题。

当前处理：`Reactor/2111101.img` 先复用普通祭坛 `2111001.img` 的视觉，服务端脚本 `scripts/reactor/2111101.js` 负责召唤进阶扎昆。

结论：祭坛看起来像普通是当前的稳定策略，不代表事件没迁移。后续要恢复独立外观，需要单独分层迁 reactor 动作和事件节点。

### 5. 召唤后崩不一定是地图问题

现象：进图不崩，召唤 Boss 后崩。

实际缺口：

- 客户端 `String/Mob.img` 缺 `8800100-8800110`
- Boss 血条 `UIWindow/MobGage/Mob/8800100-8800102` 是不稳定的 1x1 `_inlink`
- `MobSkill 200/189` 召唤的 `9400389.img` 是空壳 0 canvas

正确做法：召唤阶段要检查 Boss 本体、血条 UI、String、技能、召唤怪，不要只盯地图。

### 6. MobSkill 不能硬补高版本节点

现象：补入 095 的 `MobSkill 114/37` 后，客户端提示“游戏数据不正确”。

原因：该技能等级包含 BeiDou 客户端原生 `114` 等级中没有的 `mob/mob0` 特效节点，客户端不认识或处理不兼容。

正确做法：不要硬搬。进阶扎昆的 `8800108` 已把该技能适配为 BeiDou 原生可识别的 `114/1`。迁进阶黑龙时也要逐项确认技能等级，不兼容时优先映射到现有兼容等级。

### 7. 进阶 Boss 外观可能本来就复用普通 Boss

进阶扎昆迁移后看起来像普通扎昆，经检查不是召错 ID：

- 反应堆脚本召唤 `8800100` 和 `8800103-8800110`
- 客户端 `8800100-8800110.img` 与普通 `8800000-8800010.img` 文件不同
- 但像素级对比显示，多数共享 canvas 与普通扎昆完全一致
- 差异主要在等级、HP、攻击、技能、召唤链和部分新增 hit/attack 节点

结论：095 的进阶扎昆主体美术基本复用普通扎昆，不要把“长得像普通”直接判断为迁移失败。

## 下一批：进阶黑龙迁移清单

进阶黑龙建议先按进阶扎昆的稳定路线迁，不要一上来追求完整视觉。

### 迁移范围预估

- 事件脚本：`ChaosHorntail.js`
- 战斗地图：`240060001`、`240060101`、`240060201`
- 相关怪物：`8810100-8810130`
- 入口 NPC、等待地图、portal、远征枚举和 bosslog
- 黑龙血条 UI、String、召唤怪、死亡部件

### 必查项目

- `8810100-8810130` 是否都有客户端 IMG、服务端 XML、`String/Mob`
- 每个部件 `revive` 是否完整
- 每个部件 `skill` 引用的 `MobSkill` 等级是否在 BeiDou 客户端可识别
- `MobSkill 200` 召唤怪是否补齐
- 头、手、翼、腿、尾死亡节点是否存在
- `UIWindow/MobGage/Mob/<主BossId>` 是否存在且 canvas 可解码
- 战斗地图的 `back/obj/tile/life/reactor/miniMap/portal` 是否全量审计
- HP 是否超过 21 亿；超过时服务端 XML 用 `string` HP

### 推荐落地顺序

1. 只迁服务端常量、String、NPC、event 脚本和入口，先能创建远征。
2. 迁等待地图和传送链，先能到战斗地图入口。
3. 战斗地图先使用 BeiDou 已稳定的普通黑龙地图结构，改地图 ID、portal、life/reactor。
4. 迁 `8810100-8810130` 客户端 IMG 和服务端 XML。
5. 补 `String/Mob` 和 Boss 血条 UI。
6. 审计 `MobSkill` 和召唤怪。
7. 进游戏验证召唤、阶段切换、死亡清场。
8. 稳定后再逐层恢复 095 地图视觉和特殊特效。

## 最小验收标准

每批 Boss 迁移完成前，至少满足：

- 入口、远征、传送、战斗地图闭环可走通。
- 战斗地图不召唤时不崩。
- 召唤 Boss 后不崩，血条和名字正常。
- Boss 普通攻击、技能、召唤怪不崩。
- 阶段切换和死亡流程正常。
- 客户端和服务端资源审计没有缺文件、空 canvas、缺 String、缺 UI 的失败项。
- README 更新本批踩坑和兼容处理，不把临时兼容方案藏在代码里。

## 第二批迁移记录：进阶暗黑龙王

进阶暗黑龙王已按当前普通黑龙事件风格落地，不直接照搬 095 的 `preheadCheck + hontale_boss1/hontale_boss2` 触发链。

- 入口 NPC `2083004` 支持普通/进阶黑龙选择，进阶模式创建 `CHAOS_HORNTAIL` 远征并启动 `ChaosHorntail`。
- `ChaosHorntail` 使用 `240060001`、`240060101`、`240060201`，前两张地图在 `setup()` 中刷 `8810128/8810129`，击杀其 revive 出来的 `8810100/8810101` 后，`hontale_BR.js` 放行到下一张地图。
- 最终场 `240060201` 的反应堆 `2401100` 调用服务端新增 `spawnChaosHorntailOnGroundBelow`，建立 `8810130` 召唤动画、`8810118` 本体和 `8810102-8810109` 部件的父子关系与伤害联动。
- 进阶部件死亡后仍 revive 普通死部件 `8810010-8810017`；已扩展 `Monster.killBy()`，死部件齐全时会优先击杀普通本体 `8810018`，找不到时击杀进阶本体 `8810118`。
- 已补服务端/客户端 `String/Mob` 的进阶黑龙名称，并把 `UIWindow/MobGage/Mob/8810118` 从 1x1 `_inlink` 占位改为 UOL 到 `8810018`。
- 最终场召唤动画播完后真身不显示时，不要继续改 `spawnChaosHorntailOnGroundBelow`。当前稳定方案是直接以普通黑龙客户端/服务端资源为母版重建 `8810100-8810109`、`8810118-8810130`：动作、canvas、基础 `info` 结构完全复用普通黑龙，只保留混沌的血量、攻防、经验等数值，以及 `8810130 -> 8810102-8810109/8810118` 和 `8810118 -> 8810119 -> 8810120 -> 8810121 -> 8810122` 的阶段 revive。`8810123-8810127` 是 `MobSkill 200/198-202` 引用的技能召唤小怪，也按普通小怪母版重建并保留混沌数值。
- 最终场地图 `240060201` 引用客户端反应堆 `2401100`、`2401200`。服务端 XML 已有这两个 reactor，但客户端散 IMG 原先缺失；已让 `clien/Data/Reactor/2401100.img` 复用普通黑龙 `2401000.img` 的稳定视觉，让 `2401200.img` 复用 1x1 隐藏 reactor 资源。行为仍由服务端 `scripts/reactor/2401100.js` 控制。
- 095 来源中没有 `8810110-8810117` 文件；本批资源实际存在并迁移的是 `8810100-8810109`、`8810118-8810130`。
