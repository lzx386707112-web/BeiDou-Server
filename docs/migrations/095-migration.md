# 095 内容迁移手册

本文记录从 `怀旧岛V095仿官版` 向 BeiDou 迁移内容时的正确流程、进阶扎昆踩坑，以及后续迁移进阶黑龙时需要复用的检查方法。

目标不是“把文件拷过去能进图就算完”，而是建立一个可复用的闭环：客户端资源、服务端 XML、脚本、入口、UI、String、召唤链、技能特效都要一起验证。

## 核心原则

- 客户端 `clien/Data` 和服务端 `gms-server/wz` 必须同步迁移。只改服务端 XML，客户端缺资源会黑屏、闪退、报“游戏数据不正确”。
- 095 来源是 WZ，BeiDou 客户端使用散 IMG。迁移客户端资源时要先从 095 WZ 导出 IMG，再保存成 BeiDou 客户端可读的 GMS key。
- 不要直接相信“文件存在”。要确认 IMG 能解析、canvas 能解码、引用的子资源也存在。
- 资源存在且 canvas 可解码也不代表逻辑正确。多部件 Boss 还要核对动作语义、`origin/head/lt/rb` 坐标、死亡阶段、父子对象和刷出顺序。
- 记录迁移结论时要区分“已验证事实”和“排查假设”。例如截图表现为翅膀在前景，只能说明绘制层或刷出顺序仍需核对，不能直接判定应该改 IMG 锚点。
- 不要把高版本节点硬搬进 BeiDou。095 的部分 MobSkill、地图、反应堆节点结构可能超出当前客户端可识别范围，硬补会导致进图或召唤后崩溃。
- 先做稳定闭环，再逐层恢复视觉。地图崩溃时，优先保留可运行的 portal/reactor/life/miniMap 结构，再分层迁回 `back/obj/tile`。
- 每次迁移都要保留覆盖前备份，至少保存到 `/private/tmp`，方便快速回滚和差异比较。

## 标准迁移流程

### 0. 问题排除方法和工具

客户端提示“不正确的游戏数据”或进图黑屏时，不要按最后看到的资源名直接猜结论，先把问题分阶段：

- 启动客户端就报错：优先检查启动阶段实际加载过、且本次修改过的 IMG，例如 `String/Map.img`、`Skill/MobSkill.img`、`List.wz` 相关校验链。
- 选择角色后或进图后崩溃：优先看最新日志最后加载的地图、通用 UI、`Map/Obj`、`Map/Tile`、角色外观、怪物资源。正常地图也会加载的通用资源不能随意全量重写。
- 召唤 Boss 后崩溃：再查 Boss 本体、`MobSkill`、召唤怪、血条 UI、String 和 revive 链。

当前客户端调试工具：

- `clien/WzFileLogger.dll` 会随已补丁的 `clien/BeiDou.exe` 启动，并写入 `clien/beidou_wz_access.log`。
- 日志可看到 `List.wz`、`CreateFileMappingA` 映射的实际 IMG 路径、`MapViewOfFile`、`MessageBoxA/W` 等访问记录。
- 关键判断不是“最后一行一定是坏文件”，而是“最后成功加载的文件、之后是否还有正常 detached、以及它是否是本次改动文件”。
- 用 `git status --short -- clien/Data` 列出本次改动 IMG，再和日志里实际加载过的 IMG 求交集，先定位启动阶段最小嫌疑集。
- 做 A/B 定位时只临时恢复一个客户端 IMG，例如只恢复 `MobSkill.img` 或只恢复 `connect.img`，每次都先备份到 `/private/tmp`。如果恢复某个文件后症状消失，说明问题在该文件内部，再继续按节点分段写回。
- 271 地图用 `tool/scripts/audit/audit_095_cygnus_maps.py` 做逐节点审计。它会检查客户端实际读取目录、tile/obj/back/life/portal/hook/bgm/mapMark 引用、引用子节点是否存在，并把 271 中当前客户端旧地图没出现过的字段签名列出来。
- 光圈无反应时看服务端 `gms-server/logs/out.log` 或控制台里的 `[PortalTrace]`。`CHANGE_MAP` 是普通跨图 portal，`CHANGE_MAP_SPECIAL` 是脚本 portal，`USE_INNER_PORTAL` 是同图内传送。重点看 `packetPortal` 是否能匹配到 `portal`、是否 `reject-distance`、是否 `ENTER no-target`、脚本是否 `script-result changed=false`。
- NPC 没有灯泡、任务列表完全没有新增任务时，要同时查服务端 `gms-server/wz/Quest.wz/{QuestInfo,Check,Act,Say}.img.xml` 和客户端 `clien/Data/Quest/{QuestInfo,Check,Act,Say}.img`。BeiDou 服务端读取 split 结构，不读取 095 的 `QuestData/<id>.img.xml`；客户端也需要散 IMG 内存在同一批 quest id。

本批希纳斯排障得到的具体经验：

- 启动即报“不正确的游戏数据”时，恢复 `clien/Data/Skill/MobSkill.img` 后不再报错，说明问题在新增 `MobSkill` 客户端节点内，而不是最后预加载到的普通 `Skill/200.img`。
- 角色在神木村进入后黑屏并报无效指针时，日志最后停在 `clien/Data/Map/Obj/connect.img`。该文件是正常地图也会使用的通用资源，本次全量重编码后影响了非 271 地图。
- 对已有通用 IMG 只能补缺失子节点，不能为了修几个 271 引用而全量重编码整个 IMG；否则可能破坏原本能正常加载的老节点。
- 客户端地图散文件路径必须匹配实际加载路径。日志显示普通地图加载 `clien/Data/Map/Map/Map2/240000000.img`，因此 271 客户端地图也必须放在 `clien/Data/Map/Map/Map2/`，不能放在 `clien/Data/Map/Map2/`。

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
- 多阶段本体的 `die1` 是否符合阶段语义。中间阶段通常应该是短小/透明切换动画，不能误用最终死亡大动画。
- `skill` 中每个 `skill/level` 是否在 BeiDou 客户端和服务端 `MobSkill.img` 中存在
- `MobSkill 200` 的召唤怪是否都有客户端 IMG、服务端 XML、String
- 每个动作 canvas 是否能解码
- 多部件 Boss 要抽样比较普通版、095 来源、迁移后客户端 IMG 的 `stand/0`、主要 `attack/skill`、`die1` 的 `origin/head/lt/rb`。截图里的错位通常不是地图坐标，而是这些锚点或刷怪层级不一致。
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

## 阿卡伊勒 Boss 召唤崩溃记录

### 1. 现象和定位

阿卡伊勒入口地图和战斗地图资源补齐后，角色进图已经不崩，但在 `272020200` 点击时间女神 NPC 召唤 `8860000` 时客户端黑屏或崩溃。中间曾出现“能看到怪物血条，然后马上黑屏”的阶段。

定位时不要只看地图。最新客户端日志停在 `clien/Data/Mob/8860000.img`，且没有继续访问 `Skill/MobSkill.img`，说明崩溃发生在 Boss 本体加载、实例化、绘制或 Boss 血条初始化阶段，不是 Boss 已经放技能后缺 `MobSkill` 特效。

本次排查用的关键检查：

- `272020200` 地图审计：`MISSING UNIQUE=0`，canvas 问题为 0，排除地图显式资源缺失。
- `Mob/8860000.img` 全量 canvas 解码：确认文件能解析、画布能解码，但这不代表节点结构兼容。
- `info/skill` 逐项检查：每个 `skill/level/action` 都要确认 `MobSkill.img` 存在，且 `skill<action>` 动作节点存在。
- `UIWindow.img/MobGage/Mob/8860000` 检查：Boss 血条节点存在且可解码，但缺少常见旧 Boss 血条上的 `delay=500`。

### 2. 根因判断

这次不是单纯漏文件。更接近“高版本 Boss 资源节点能被离线工具解码，但当前客户端加载时不兼容”。

主要问题点：

- 原始 `8860000` 动作树来自更高版本资源，节点和动作结构比当前客户端复杂。即使 canvas 能解码，也可能在客户端创建 Boss 对象时崩。
- `8860000/info` 带有当前客户端不稳定或不必要的高版本字段，例如 `finalmaxHP`、`ignoreFieldOut`、`HPgaugeHide`、`category`、`ignoreMoveImpact`、`wp`、`mobType="7N"`、`skillAfter`、`info/attack` 等。
- `UIWindow.img/MobGage/Mob/8860000` 的血条 canvas 可解码，但缺 `delay`。当表现为“血条出现后黑屏”时，血条 UI 也要纳入嫌疑，不要只盯 `Mob/8860000.img`。
- `info/revive` 曾指向未补齐或不需要的阶段怪，会把问题从召唤阶段延后到死亡/切阶段阶段；兼容闭环里先移除。

### 3. 当前兼容处理

当前稳定方案是先让 `8860000` 作为可召唤、可显示、可战斗的 Boss 跑通，再逐层恢复高版本专属行为。

已落地修改：

- `clien/Data/Mob/8860000.img`：保留 `8860000` ID，基础视觉层改用同系列、当前客户端可加载的 `9900002.img` 动作模板。
- `clien/Data/Mob/8860000.img`：`info` 改为旧端更常见的最小 Boss profile，移除高版本字段；`mobType` 改为整数 `1`，`summonType` 改为模板同款 `12`。
- `clien/Data/Mob/8860000.img`：`info/skill` 只保留已确认安全的 `140/9 -> skill1`、`141/10 -> skill2`，并移除 `skillAfter`。原版 `145/10`、`128/21-23`、`138/2`、`174/175/176/177/269` 等当前客户端或服务端不完整，暂不启用。
- `clien/Data/Mob/8860000.img`：移除 `info/attack`，避免客户端解析额外 attack 元数据；服务端仍可根据动作节点和基础怪物逻辑运行。
- `gms-server/wz/Mob.wz/8860000.img.xml`：同步上述 `info`、技能和字段清理，移除 `finalmaxHP`、`revive`、`PDRate/MDRate`、`attack2-attack4`、空的 `skill3-skill11` 等迁移残留。
- `clien/Data/UI/UIWindow.img`：给 `MobGage/Mob/8860000` 血条 canvas 补 `delay=500`。
- `gms-server/wz/String.wz/Mob.img.xml` 和 `clien/Data/String/Mob.img`：补 `8860000` 名称，避免名字链缺失。
- `tool/scripts/migration/migrate_akayrum_resources.py`：把这些兼容处理写回迁移脚本，后续重跑不会恢复成不兼容状态。

### 4. 踩坑和经验

- “能解码”不等于“客户端能实例化”。WZ 工具能读出 canvas，只能证明二进制和图片层没坏，不能证明 `info` 字段、动作名、动作序列、血条 UI 和技能引用符合当前客户端逻辑。
- 日志最后停在某个 IMG，不要立刻全量重写它。先判断崩溃阶段：召唤前、召唤瞬间、血条出现后、放技能时、死亡切阶段时，对应的嫌疑完全不同。
- 血条出现后崩时，要查 `UIWindow.img/MobGage/Mob/<mobId>`。Boss 血条节点即使存在，也要确认 canvas 可解码、`origin` 和 `delay` 等基础字段合理。
- 高版本字段要先减法。不要为了“还原完整”保留所有新字段；兼容迁移优先使用当前客户端已有 Boss 的字段形态。
- Boss 技能要和动作节点一起看。`info/skill/<n>/action=2` 必须有 `skill2`，技能 ID/等级也必须在 `MobSkill.img` 中存在。
- 先少技能、少字段、少阶段，跑通召唤闭环；再按实测逐项加回攻击、技能、召唤怪、阶段 revive。

### 5. 已验证和待继续测试

已验证：

- `272020200` 地图资源审计通过。
- `8860000` 客户端 IMG 可解析，全部 canvas 可解码。
- `140/9`、`141/10` 对应 `MobSkill.img` 节点存在，且 `skill1/skill2` 动作存在。
- `UIWindow.img/MobGage/Mob/8860000` 存在并已补 `delay=500`。
- 实机点击时间女神召唤后已确认不再崩溃。

还建议继续测试：

- 默认不恢复 `attack2-attack4`、`145/9` 反伤技能。原样恢复和按旧端结构裁剪恢复都已导致召唤阶段崩溃，当前兼容闭环以“不崩”为优先。
- Boss 受击、击杀、死亡动画和事件清场是否正常。
- 重新进出 `272020110 -> 272020200`，反复召唤、退出、重进是否有残留怪或事件状态未清理。
- 如果后续要恢复更多原版阿卡伊勒技能或阶段链，每次只加一项，并同步检查 `MobSkill`、召唤怪、动作节点和血条 UI。

补充记录：尝试默认加回 `attack2-attack4` 和 `skill5` 后，客户端又在召唤瞬间崩溃，最新日志停在 `clien/Data/Mob/8860000.img`，没有继续访问 `MobSkill.img`。离线解码全部 canvas 仍然正常，说明问题在旧客户端实例化高版本动作树，而不是图片损坏。

兼容实验失败记录：按现有旧端 boss 节点结构重建 `attack2-attack4` 和 `skill5` 后仍然召唤崩溃。实验版已把客户端动作帧裁剪为 canvas-only，并统一补 `origin/head/lt/rb/delay`；攻击动作的 `info` 也只保留旧端常见的 `hit/range/attackAfter`，不再带入 273 源里的 `ball/effect/areaWarning/randDelayAttack/effectAfter`。即使这样仍不稳定，因此当前默认迁移已回退到模板动作集合，不启用 `145/9 -> skill5`。

## 阿卡伊勒次元缝隙怪物外形错误记录

### 1. 现象和定位

角色传送到次元的缝隙后，地图能进入，但当前地图怪物外形明显不对。客户端日志显示实际加载的是 `Map/Map/Map2/272030000.img` 和 `Mob/9300301.img`。

对比源包和当前资源时，`272030000` 的 `life` 没有被替换，地图仍然引用源包里的 `9300301`。真正被替换的是怪物资源本体：

- 源包 `9300301` 有 `stand/move/attack1/attack2/attack3/hit1/die1`，共 127 张 canvas，`maxHP=155000`。
- 当前 `9300301` 只有 `move/stand/hit1/die1`，共 10 张小 canvas，`level=10`、`maxHP=10`，属于占位怪。
- 同系列 `9300302`、`9300304` 也因为目标文件已存在而被迁移脚本跳过，保留了旧占位属性。

### 2. 根因和修复

根因不是地图换怪，而是迁移脚本默认“不覆盖已存在 Mob”。阿卡伊勒源包里的 `9300301/9300302/9300304` 是这批地图的权威资源，但目标目录已有同 ID 旧资源，导致正确资源没有写入。

已落地处理：

- `gms-server/wz/Mob.wz/9300301.img.xml`、`9300302.img.xml`、`9300304.img.xml`：强制回灌源包 XML。
- `clien/Data/Mob/9300301.img`、`9300302.img`、`9300304.img`：由源包 XML 重新生成 GMS key 客户端 IMG。
- `tool/scripts/migration/migrate_akayrum_resources.py`：新增 `FORCE_SOURCE_MOB_IDS = {9300301, 9300302, 9300304}`，后续重跑迁移也会覆盖这些占位资源。
- `9300301` 源包带 `mobType=5N`，和之前 `8220020` 的兼容坑一致；迁移后要降为 `4N`，否则可能修好外形后在旧客户端加载阶段继续崩。
- `9300304` 源包没有独立动作 canvas，而是 `link=8860000`。这不是缺画布，而是 boss 链接怪，不能再保留旧的 `link=4230107` 占位配置。

### 3. 验证结论

已验证：

- `9300301` 客户端 IMG 恢复为 127 张 canvas，全部可用 GMS key 解码，动作包含 `attack1-attack3`。
- `9300302` 客户端 IMG 恢复为 91 张 canvas，全部可用 GMS key 解码，动作包含 `attack1-attack3`。
- `9300304` 恢复为 `level=120`、`maxHP=178500000`、`boss=1`、`link=8860000`。
- `272030000`、`272030100`、`272030200`、`272030400` 审计通过：缺失资源 0，canvas 解码问题 0，不支持字段签名 0。

经验：看到“怪物外形不对”时，不要只检查地图 `life/id` 有没有被替换；还要对比怪物 IMG 本体的动作节点、canvas 数量、尺寸和服务端属性。文件存在但只有小画布或 10 血，很可能是旧占位资源。

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

## 多部件 Boss 迁移经验

进阶黑龙这类 Boss 不是一个“本体 IMG”能决定显示结果，而是由召唤壳、本体、部件、死部件、阶段 revive 和客户端绘制层共同组成。

排查顺序建议固定为：

1. 先确认客户端 `Mob/<id>.img` 存在、可用 GMS key 解析、所有 canvas 可解码。
2. 再确认 `String/Mob` 和 `UIWindow/MobGage/Mob/<主BossId>`，避免只有血条或名字异常。
3. 对比普通版、095 来源、迁移后资源的关键帧坐标，尤其是 `origin` 和 `head`。如果坐标一致，错位多半不是资源锚点问题。
4. 检查阶段切换时是否残留旧死亡部件。进阶黑龙的死部件复用普通 `8810010-8810017`，不清理会让下一阶段误判“部件已全死”。
5. 检查刷怪路径。`setPosition + spawnMonster` 和 `spawnMonsterOnGroundBelow` 的落点/FH/封包效果不同，多部件 Boss 阶段刷新应尽量复用初次召唤的刷法。
6. 检查刷出顺序。翅膀、身体、手脚等部件的前后层可能受对象创建顺序影响；如果翅膀跑到最前面，要优先看刷怪顺序和 parent 关系，而不是直接改图片。
7. 区分“召唤壳动画”和“正式怪物”。普通黑龙进图/召唤正式本体时没有预头从右到左的出场动画；如果进阶版本仍出现这类动画，说明脚本或 summonType/revive 链还没对齐普通逻辑。

不要在没有证据时把整组资源反复覆盖成普通版。正确做法是逐层验证：文件存在、canvas 可解码、锚点一致、阶段语义一致、刷怪路径一致、绘制层一致。每一层都能缩小问题范围。

### 进阶黑龙本次调试结论

已确认的结论：

- `8810100-8810130` 客户端 IMG 可解析且 canvas 可解码，因此“文件不存在/空 canvas”不是当前主要问题。
- 095 来源没有 `8810110-8810117`，不要为了补连续 ID 人为创建这一段。
- 预备头和最终场逻辑不能混在一起看。前两阶段预备头已可验证通过后，最终场应直接聚焦 `8810130`、`8810118-8810122`、`8810102-8810109`、`8810010-8810017`。
- 普通黑龙正式本体没有从右到左的预头出场动画。进阶黑龙如果最终场还出现这类动画，优先检查脚本召唤对象、`summonType`、召唤壳和 revive 链是否仍走了预头逻辑。
- `8810118-8810121` 是中间阶段，本体死亡动画应只承担阶段切换；最终大死亡动画只应留给 `8810122`。否则容易出现打完阶段后只剩血条、黑屏或崩溃。
- 进阶黑龙死部件复用普通死部件 `8810010-8810017`。阶段刷新前不清理这些对象，会影响下一阶段是否认为部件已经死亡。

仍需谨慎验证的方向：

- 翅膀跑到前景或部件错位时，先抓运行时实际刷怪顺序、object id、parent 关系，再决定是否调整 spawn 顺序。不要只凭一张截图改资源坐标。
- 如果普通版、095 来源、迁移后资源的 `origin/head/lt/rb` 一致，错位大概率在刷怪路径、层级或父子关系，而不是 IMG 本身。
- `spawnMonsterOnGroundBelow` 和 `setPosition + spawnMonster` 可能产生不同的落点、FH 和封包效果；多部件 Boss 的阶段刷新应和初始召唤路径保持一致后再继续排查绘制层。

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
- 最终场召唤动画播完后真身不显示时，不要只盯 `spawnChaosHorntailOnGroundBelow`。需要同时核对召唤壳 `8810130`、本体阶段 `8810118-8810122`、部件 `8810102-8810109`、死部件 `8810010-8810017` 和客户端绘制层。当前资源策略是部件动作和锚点对齐普通黑龙，混沌保留自身血量、攻防、经验、阶段 revive；`8810123-8810127` 是 `MobSkill 200/198-202` 引用的技能召唤小怪，也按普通小怪母版重建并保留混沌数值。
- `8810118-8810121` 是中间阶段，本体 `stand/hit/die` 应保持小型/透明切换语义，不能误用最终阶段的大死亡动画；最终大死亡动画只应留给 `8810122`。否则打完一阶段后会出现血条异常、黑屏或客户端崩溃。
- 阶段刷新时需要清掉普通死部件 `8810010-8810017`，再按稳定刷怪路径补出缺失的 `8810102-8810109` 部件。部件刷新应复用初始召唤的顺序；如果翅膀跑到前景，优先检查刷出顺序和 parent/层级关系。
- 最终场地图 `240060201` 引用客户端反应堆 `2401100`、`2401200`。服务端 XML 已有这两个 reactor，但客户端散 IMG 原先缺失；已让 `clien/Data/Reactor/2401100.img` 复用普通黑龙 `2401000.img` 的稳定视觉，让 `2401200.img` 复用 1x1 隐藏 reactor 资源。行为仍由服务端 `scripts/reactor/2401100.js` 控制。
- 095 来源中没有 `8810110-8810117` 文件；本批资源实际存在并迁移的是 `8810100-8810109`、`8810118-8810130`。

## 第三批迁移记录：希纳斯 / 骑士团要塞

本批迁移目标是 095 的未来之门、骑士团要塞和希纳斯远征闭环。资源不是只迁 `271040000/271040100`，而是按地图节点引用把整套 `271xxxxxx` 所需的地图、life、portal、NPC、怪物和技能依赖一起补齐。

已落地内容：

- 地图：`gms-server/wz/Map.wz/Map/Map2/271*.img.xml` 共 51 张，对应客户端实际读取路径 `clien/Data/Map/Map/Map2/271*.img`。
- 地图素材：从 095 客户端导出并改写为 GMS key 的 `Map/Back/darkEreb/destructionTown/fakeDoors`、`Map/Obj/acc14`、`Map/Tile/destructionField/destructionTown1/destructionTown2`；`Tile/darkEreb.img` 按 271 地图既有引用补为兼容 tile；`MapHelper.img` 补 `mark/destructionTown`、`mark/darkEreb`；`Map/Obj/connect.img` 只补 271 引用的缺失子节点，不能整文件重编码。
- 怪物：`8600000-8600006`、`8610000-8610022`、`8850000-8850012` 的服务端 XML 和客户端 IMG；当前已有的 `8850013` 保留。
- NPC：`2142000-2142010`、`2143000`、`2143001`、`2143003`、`2143004` 的服务端 XML 和客户端 IMG。
- String：服务端补 `String/Map` 的 271 地图名；客户端 `String/Map.img` 保持迁移前版本，不写入 271 地图名。客户端仍补 `String/Mob` 的 860/861/885 名称、`String/Npc` 的 2142/2143 名称。
- MobSkill：服务端补 095 希纳斯和骑士团要塞怪物引用到的 `100/25`、`114/42-43`、`120/19`、`129/13`、`133/8`、`138/1`、`145/9`、`146/1-2`、`171/1`、`172/1`、`200/221-224/228-233`。客户端只补当前版本原本已有的技能类型，并按迁移前 `MobSkill.img` 字段白名单裁剪；`138/146/171/172` 不写入客户端。未来之门怪物 `8600001` 原始引用 `123/35`，当前客户端只安全支持到 `123/26`，所以改怪物引用等级为 `123/26`，不补客户端 `123/35`。
- Java：新增 `ExpeditionType.CYGNUS`、`BossLogEntry.CYGNUS`、`V2.1.19__add_cygnus_bosslog.sql`，并把 `8850000-8850013` 作为希纳斯 boss 日志范围；新增 `MobSkillType` 的 `138/146/171/172` 占位枚举，避免 `LifeFactory` 读取 095 怪物技能时 `orElseThrow()`。
- 脚本：新增 `scripts/event/CygnusBattle.js` 和 `scripts-zh-CN/event/CygnusBattle.js`；新增 NPC `2143004` 远征入口、`2143000` 精灵地图选择；新增 271 地图引用的 portal 脚本和 map hook 脚本。

兼容处理说明：

- 095 的 `CygnusBattle.js` 使用旧 squad API、`em.getMonster()`、`setInstanceMap()` 和 `disposeIfPlayerBelow()`，没有直接搬运。当前实现改成 BeiDou 现有 expedition 风格：`2143004` 创建 `CYGNUS` 远征，event `setup()` 重置 `271040100`，按 095 原始坐标 `(-363, 100)` 依次刷 `8850000 -> 8850001 -> 8850002 -> 8850003 -> 8850004 -> 8850011`，击杀 `8850011` 后清场。
- `271040100` 地图本身 `lvLimit=170`，所以 `CYGNUS` 远征最低等级采用 170。095 NPC 脚本里的 120 级限制没有硬搬。
- 地图引用的 `cygnus_Summon`、`cygnus_ExpeditionEnter`、`knights_Summon`、`enter_secretGarden`、`q31102e`、`q31103s` 在 095 来源脚本中没有可直接迁的兼容逻辑。当前新增为空 `start(ms)`，由 event 脚本承担实际希纳斯刷怪，避免地图进入时报缺脚本。
- 095 `885` 系列覆盖当前项目中原有的同 ID 资源，是有意选择：当前资源的 revive/skill 链与 095 希纳斯不一致，直接混用会导致召唤链和技能依赖不闭环。`8850013` 不在 095 来源中，保留当前项目版本。
- `8850012` 是一个 4x4 canvas 的 `summonType=12` / revive 到 `8850011` 的占位怪，不是客户端导出失败。
- `MobSkillType` 新增的 `138/146/171/172` 只是加载兼容枚举，当前 `MobSkill.applyEffect()` 不实现这些高版本技能效果。这样可以保证怪物加载和召唤不崩；后续如需要完整技能行为，再逐个按当前客户端/服务端能力实现。
- 095 客户端 IMG 不能直接按原 payload 写入当前客户端。`Map/Obj/acc14.img` 中已发现来源节点有负宽高和异常 fmt，直接搬会触发“不正确的游戏数据”。迁移脚本现在会逐个 canvas 用 EMS key 解码，再用 GMS key 重编码；普通装饰来源无效时可以临时隔离成 1x1 透明占位，但地图 Tile 不能粗暴透明化。
- `Tile/destructionTown1/destructionTown2/destructionField` 中部分 095 canvas 使用 prefixed ARGB4444 包装，表现为 `format=0` 或宽高字段异常。此前按普通解码失败后落成 1x1，导致未来之门光圈下方、草地和石墙之间出现一条不连续空块。当前迁移脚本会跳过包装前缀、按 ARGB4444 还原真实尺寸，再写成当前客户端支持的 `format=1`。
- 不要只检查新增节点。`Map/Obj/connect.img` 是当前客户端已有通用资源，神木村等正常地图也会加载。曾经为了补 `ladder/71`、`rope/14`、`rope/27` 对整个 `connect.img` 重编码，导致角色进神木村黑屏并报无效指针。当前做法是保留既有节点 payload，只补缺失子节点：`ladder/71/0-2` 从 095 源迁入；`rope/14/0-3`、`rope/27/0-3` 的 095 源 payload 在当前解析器下会落成 1x1 透明，表现为角色能爬但绳子不可见，所以复用当前客户端已稳定显示的 `rope/0/0-3` 作为兼容视觉母版，不改地图节点名。
- `MobSkill.img.xml` 不能用全局字符串匹配 `<imgdir name="技能ID">`。`138/146/171/172` 这类技能 ID 会和其他技能的等级节点重名，必须按根节点技能 ID -> `level` -> 等级逐层定位；当前脚本已改为结构化 XML 迁移，避免服务端缺技能根节点。
- 客户端 `String/Map.img` 是启动阶段会加载的文件。曾经只为补 42 个 271 地图名重编码整份客户端 `String/Map.img`，文件从 304.5KB 变成 441.0KB；虽然工具解析正常，但仍处在启动报“不正确游戏数据”的最小嫌疑集中。当前兼容策略是服务端保留 271 地图名，客户端 Map String 回退到迁移前版本，先保证启动稳定。
- 客户端 `MobSkill.img` 不能照搬服务端完整技能表。当前客户端原本没有顶层 `138/146/171/172`，写入这些 095 高版本技能类型会导致启动阶段提示“不正确的游戏数据”。兼容策略是：服务端 XML 保留这些 level 让怪物加载闭合；客户端只对已有技能类型补 level，补 level 时必须从迁移前最大 level 连续补齐，不能留下 `100: 23 -> 25`、`200: 214 -> 221` 这类跳号；同时删除旧客户端同类 level 从未出现过的字段，例如 `200` 的 `exchangeAttack/mobGroup/summonOnce` 和 `145/9` 的 `rank`。
- 271 地图引用 `Tile/darkEreb.img`，但 095 来源客户端和当前客户端都没有该 tile。兼容处理不是改地图 `tS` 名字，而是补地图已经引用的 `darkEreb.img`：以本批已导出的 `destructionField.img` 为基底，再从 `destructionTown2.img` 补唯一缺的 `bsc/5`，确保 271 实际引用的 20 个 tile 子节点都存在且 canvas 可解码。
- 271 地图的 `mapMark=destructionTown/darkEreb` 使用当前 `MapHelper.img` 既有 `mark` 结构。095 源端存在这两个 mark，当前客户端缺失，所以补 `mark/destructionTown` 和 `mark/darkEreb`，不删除地图字段。
- `271030000/271030010` 左侧返回 `271000300` 的 portal，095 原始目标是 `tn=in00`，也就是落到 `271000300` 的脚本 portal 上。当前客户端在这条链路上会进图后崩溃；兼容处理为同步改服务端 XML 和客户端 IMG，使 `west00 -> 271000300/sp`，避免普通跨图 portal 直接落到脚本光圈。
- `271000300` 登录即崩时，日志显示已加载 `Map/Map/Map2/271000300.img`、`Tile/darkEreb.img`、`Obj/acc14.img`，最后停在 `Back/darkEreb.img`。已确认该图实际引用的 tile、obj、back 静态 canvas、`darkEreb/ani/0` 动画帧均可用 GMS key 解码，资源存在本身不是充分证据。A/B 排查结论：把两个 `darkEreb/no=15` 降到 `no=14` 仍崩；把 `back/1/ani` 从 `1` 降为 `0` 仍崩；清空 20 个 `acc14` obj 摆放仍崩，但能显示地图背景；移除根节点 `ToolTip` 后不崩。当前最终兼容处理为只移除 `271000300/ToolTip`，并恢复 obj 摆放、`back/1/ani=1`、`back/16-17/no=15`，不改通用 `Obj/acc14.img`、`Tile/darkEreb.img`、`Back/darkEreb.img`。
- `271040000` 底部看起来“缺素材”时，实际不是 `acc14` 或 `darkEreb` 资源缺 canvas。该图没有 tile 层，地面由 `Obj/acc14.img/darkErebKnights/cygnusGarden/1/0` 组成，canvas 可解码且是完整岩壁；截图中露出的灰黑空区是当前客户端把地面下方的前景雾和空白视野显示出来。兼容处理为只把服务端 XML 和客户端 IMG 的 `info/VRBottom` 从 `297` 收到 `254`，不改节点名、不改通用资源。
- `271000300` 左侧 `hene00 -> 271020100/south00` 光圈无反应时，服务端日志停在 `ENTER start` 且没有 `ENTER warp`，说明客户端包、portal 名称和距离校验都已经通过，问题在目标图首次加载。离线审计发现目标图怪物 `8600001` 引用 `MobSkill 123/35`，当前服务端和客户端 `MobSkill` 只到 `123/26`。曾尝试补客户端 `123/35`，会导致启动时报“不正确的游戏数据”。最终兼容处理为把服务端 XML 和客户端 `Mob/8600001.img` 的 `info/skill/0/level` 改为 `26`，保持技能 ID `123` 不变；同时 `ChangeMapHandler` 的异常改为正式日志并 `enableActions()`，后续这类问题会直接落到 `out.log`。
- `8850011` 希纳斯本体出来后崩溃时，前置骑士 `8850000-8850004` 已正常，日志最后进入 `MobSkill.img` 和 `Mob/8850011.img`，说明重点不是地图。离线检查发现本体 `info/skill` 仍引用客户端不写入的 `138/1`、`171/1`、`172/1`，且 `attack4` 带唯一出现的 `disease=173/level=1`；当前客户端 `MobSkill.img` 没有这些顶层技能。兼容处理为同步修改服务端 XML 和客户端 `Mob/8850011.img`：移除 `138/171/172` 三个技能入口并重排索引，保留 `133/129/145/114/200` 等客户端已有技能；同时移除 `attack4` 的 `173/1` 状态，不改 `MobSkill.img` 顶层结构。
- 希纳斯整条链路闪退不能只查 `8850000-8850004/8850011`，还要查 `MobSkill 200` 召唤表带出的 `8850005-8850010` 和 `8610010-8610015`。本次日志停在 `Mob/8850002.img` 后，离线审计发现主骑士和召唤体都有同源高版本技能引用：`8850000/8850005 attack3` 的 `121/15` 超出客户端 `121/14`，`8850002/8850007` 的 `146/2` 客户端无顶层技能且 `attack2/attack3` 的 `123/32` 超出 `123/26`，`8850003/8850008 attack4` 的 `123/33` 超出 `123/26`，`8850010` 还有 `146/1`。兼容处理为同步修改客户端 IMG 和服务端 XML：`121/15 -> 121/14`，`123/32/33 -> 123/26`，移除 `146/1-2` 技能入口，保留已有 `200` 召唤技能，不向客户端 `MobSkill.img` 新增顶层 `146`。新增 `tool/scripts/audit/audit_cygnus_boss_chain.py` 用于复查这类 `skill/level` 和 `attack/info/disease+level` 越界问题。
- 进一步兼容还原时，不要把客户端缺失的顶层 `138/146/171/172/173` 原样塞回 `MobSkill.img`。当前采用“替代映射”恢复 boss 行为压力：`138/1 -> 128/18` 诱惑，`146/2 -> 140/18` 物理免疫，`146/1 -> 141/15` 魔法免疫，`171/1 -> 131/16` 区域毒雾，`172/1 -> 132/8` 反向控制，`173/1 -> 132/8` 攻击附带反向控制。该映射由 `tool/scripts/patch-boss/patch_cygnus_boss_skill_mapping.py` 写入客户端 mob IMG 和服务端 XML，只改怪物引用，不新增未知客户端技能顶层节点。
- 希纳斯本体技能把角色送到 `271040110` 后，地图左侧 `out00` 是 `pt=7` 脚本 portal，脚本为 `back_cygnus`。这个地图必须仍属于 `CygnusBattle` 实例，否则玩家会被 `changedMap()` 注销，回光圈只能走普通地图链并导致 boss 进度重开。当前兼容处理为把 event 范围扩大到 `271040100-271040110`，并让 `back_cygnus` 优先使用 `changeMapBanish()` 记录的原地图/portal 回到实例内 boss 图；记录过期但仍在实例时兜底回 `271040100`，不在实例时才退到 `271040200`。
- `in_knights/in_knights01` 原先要求 `4032922` 皇家骑士团勋章。该门槛是任务道具式限制，不适合当前传送测试和迁移闭环；当前已去掉道具检查，直接进入 `271030100`。
- 未来之门任务入口使用 095 的 `31100-31160`，来源实际缺 `31157`，所以本批迁移 60 个 quest id。服务端按 split XML 原节点复制到 `QuestInfo/Check/Act/Say`；客户端从 095 `Quest.wz` 克隆同一批节点到当前散 IMG。
- `tool/wz-python/wzpy/writer.py` 的 ASCII 长字符串编码必须使用 `-128 + length` 作为长串哨兵，长度 127 的 ASCII 字符串仍是普通 `-127`。旧 writer 使用 `-127 + length` 会让 `QuestInfo/Act/Say` 重编码后出现 `unknown string-block marker`、`truncated=true`，客户端资源会处于高风险状态。
- 未来之门地图缺地板、缺绳子、光圈下方断层时，不能只看节点名是否存在。需要扫描 271 地图实际引用到的 tile/obj/back canvas，重点查“能解析但实际是 1x1 透明”的节点。本批修复了实际引用的透明占位：`acc14/threeDoors/center/4/0`、`threeDoors/left/15/0`、`threeDoors/right/15/0`、`darkEreb/bridge/1/0`、`destructionTown/houseInside/1/0`、`darkErebKnights/tile/8-12/0`，以及 `Tile/destructionField/enV0/2`、`enV1/2`。同时 `decode_prefixed_argb4444_canvas()` 改为扫描最多 512 字节 zlib 前缀，并要求解码长度不小于预期尺寸，避免再次把包装过的真实素材落成 1x1。
- 头顶灯泡/任务 UI 发来的 quest action 可能是 `4/5`，不是普通 NPC 对话的 `1/2`。当前 `QuestActionHandler` 已让 action `4/5` 在脚本不存在时回落到 WZ `quest.start()` / `quest.complete()`；已有脚本仍优先执行。这个兼容点是 311xx 任务“有 WZ 节点但点了没反应/交不了”的关键。
- 095 明确标了脚本的 311xx 任务只有 `31105`、`31119`、`31146`、`31158`，已补 `scripts/quest` 和 `scripts-zh-CN/quest` 的同名脚本。来源脚本语义是感谢文本后 `forceCompleteQuest()`，不是杀怪或收集逻辑。
- `31102` 完成条件是 `infoNumber=31102` 且 `infoex=end`，地图 `271000000` 挂的 `q31102e` 不能留空；当前进入未来之门时会写入该进度，让玩家可回 NPC 完成。`31124/31144/31149` 继续由 portal 脚本按当前兼容策略直接完成，绕开 infoex 卡点。
- 任务物品不是只补 `Quest.wz` 就够。311xx 检查和奖励涉及 `2050004`、`2270021`、`4000642-4000659`、`4020013`、`4032921/2922/2924-2928/2930/2940/2941` 等；当前已从 095 客户端 `Item.wz` 和源服务端 XML 补到客户端散 IMG 与服务端 `Item.wz` XML。补 drop 之前必须先确认这些物品两端资源都存在，否则会变成新的客户端资源错误。
- 掉落只补任务闭环和未来之门普通 ETC，不整批带入 095 的配方/装备掉落。`V2.1.20__add_cygnus_future_gate_quest_drops.sql` 覆盖 860/861/885 相关普通 ETC 和 311xx 任务 ETC；`4032924` 原本是 31117 用 `2270021` 捕捉后的结果，但当前项目没有对应捕捉 item script，因此兼容成 `8600003` 的任务掉落，并在 SQL 注释中保留迁移意图。

本批验证：

- 逐节点结构审计：`rtk python3 tool/scripts/audit/audit_095_cygnus_maps.py` 通过。51 张 271 客户端地图位于 `clien/Data/Map/Map/Map2/` 并可解析；tile/obj/back/life/portal/hook/bgm/mapMark 引用缺失数为 0；当前客户端旧地图未出现过的字段签名数为 0。
- 任务资源验证：服务端 `QuestInfo/Check/Act/Say.img.xml` 均有 60 个 `311xx` 节点，且和 095 split XML 源节点一致；客户端 `QuestInfo/Check/Act/Say.img` 均可用 GMS key 解析，`311xx count=60`、`warnings=0`、`truncated=false`。`Check/Act` 的 311xx 子节点在当前 Quest 枚举中 unsupported 数为 0。
- 任务与掉落审计：`rtk python3 tool/scripts/migration/audit_095_cygnus_quests.py` 通过。311xx 任务检查/奖励涉及的物品均为 `server=1 client=1`；新增掉落 SQL 引用的 `4000642-4000659` 和 `4032921/2922/2924-2928/2930/2940/2941` 均有服务端 XML 和客户端 IMG；任务怪关键掉落已覆盖。
- 271 系列地图中所有怪物 `skill/level` 引用在服务端 `Skill.wz/MobSkill.img.xml` 已闭合。客户端 `Skill/MobSkill.img` 不新增未知顶层技能类型；当前保留的客户端新增 level 会连续补到所需最高等级：`100/24-25`、`114/35-43`、`120/17-19`、`129/13`、`133/7-8`、`145/9`、`200/215-233`，且已确认不存在 `123/35` 和顶层 `138/146/171/172`。
- 客户端目标资源 canvas 解码扫描：本批 `connect` 新补/兼容的 `ladder/71`、`rope/14`、`rope/27` 节点均可解码且非透明；`Tile/destructionTown1/destructionTown2/destructionField` 的 prefixed ARGB4444 修复节点、`Tile/darkEreb.img` 实际引用的 20 个 tile canvas、`MapHelper` 新补 2 个 mark canvas 均为 `bad=0`。
- 271 全引用素材扫描：修复后 referenced tile/obj/back canvas 的 expanded blank/tiny/decode problems 为 0；再次运行 `audit_095_cygnus_maps.py` 结果为 `parse_errors=0`、`MISSING UNIQUE=0`、`UNSUPPORTED FIELD SIGNATURES=0`。
- 按用户反馈复查后，已扩大为全量扫描：41 个修改过的客户端 IMG、88 个新增/新增目录下客户端 IMG 均可解析且 canvas `bad_files=0`。
- 已知 warning：`clien/Data/Map/Map2/` 旧错误目录里仍有 51 张 271 副本；客户端实际读取的是 `clien/Data/Map/Map/Map2/`，这些副本不参与加载。
- `git diff --check` 通过。
- `mvn -pl gms-server -DskipTests compile` 未完成：本机 `/usr/libexec/java_home -V` 仅有 Java 17/16/15/11/8，项目 `gms-server/pom.xml` target 为 Java 21，Maven 在 javac 阶段报 `无效的目标发行版：21`。需要 Java 21 环境后再跑完整编译。
