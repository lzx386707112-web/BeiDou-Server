# 鲁塔比斯迁移记录

来源客户端：`/Users/lizixian/Documents/mxd/神说/Data`。

## 2026-08-14：地图数据退役

按当前兼容策略，鲁塔比斯地图数据已从客户端和服务端下线，只保留 Boss 与任务相关数据。

已删除范围：

- 客户端与服务端 `1052*.img` / `1052*.img.xml` 共 191 张鲁塔比斯地图。
- 后续任务包恢复的剧情入口地图 `910700200`、`910700300`。
- Root Abyss 地图专用资源：`Back/rootabyss*`、`Obj/rootabyss`、`Obj/gran_helisium`、`Tile/rootabyss*`、`Sound/Bgm29`。
- 鲁塔比斯地图内部 portal/NPC 脚本；外部入口 `go_rootabyss.js` 保留为禁用提示，避免现有地图 portal 指向缺失脚本。
- 服务端 `String.wz/Map.img.xml` / `wz-zh-CN` 中对应地图名节点。

保留范围：

- 普通与进阶鲁塔比斯 Boss 的 Mob、String/Mob、掉落、MobSkill 兼容和远征脚本数据。
- 鲁塔比斯任务 WZ、任务脚本、NPC/Mob/Reactor 资源。
- `chewchewIsland` 地图资源，因为它被非鲁塔比斯地图复用。

## 第一阶段：地图、普通小怪和进阶 Boss

本阶段先迁鲁塔比斯地图、地图素材、地图 NPC、地图 reactor 兼容资源，以及地图里出现的普通小怪；随后补入四个进阶 Boss 类型的兼容闭环。Boss 逻辑以旧客户端稳定召唤为第一目标，专属高版本机制后续逐项恢复。

已落地范围：

- 地图：`1052*.img` 共 191 张，写入客户端 `clien/Data/Map/Map/Map1/` 和服务端 `gms-server/wz/Map.wz/Map/Map1/`。
- 地图素材：`Back/rootabyss*`、`Obj/rootabyss`、`Obj/gran_helisium`、`Obj/chewchewIsland`、`Tile/rootabyss*` 等实际引用资源。
- 普通小怪：`7120112-7120115`，并补 `String/Mob`。
- 进阶 Boss：`8900000-8900003` 进阶皮埃尔、`8910000-8910001` 进阶半半、`8920000-8920006` 混沌血腥女王、`8930000-8930001` 进阶贝伦，并补 `String/Mob`。
- 普通小怪掉落：新增 `V2.1.23__add_root_abyss_normal_mob_drops.sql`，覆盖 `7120112-7120115` 的金币、药水、矿石/水晶、召唤石/魔法石和少量当前包已有卷轴。神说 `String/Etc` 中存在 `4001755/4001756` 专属尾巴名称，但源端和当前客户端都没有对应 `Item/Etc` 图标节点，本阶段不加入掉落，避免拾取/显示时触发资源缺失。
- 进阶 Boss 掉落：新增 `V2.1.24__add_root_abyss_boss_drops.sql`，只挂四个主召唤 Boss：`8900000`、`8910000`、`8920000`、`8930000`。当前掉落为资源安全的金币、药水、现有召唤石/魔法石、现有 Boss 特殊物品和少量卷轴；阶段/辅助 mob 不挂掉落，避免阶段切换或召唤物重复爆东西。Root Abyss 专属装备、碎片和商店兑换待对应 Item 资源与脚本确认后再逐项恢复。
- NPC：`1064002-1064008`、`1064012-1064016`，并补 `String/Npc`。
- Reactor：地图引用的 `1052006`、`1052008`、`1058016`、`1058020`、`1058022-1058029`。神说来源客户端没有这些同 ID reactor IMG，本阶段按同系列稳定 reactor 资源生成兼容占位；四个 Boss 房 reactor 已开启召唤，`1052006 -> 8900000`、`1058016 -> 8910000`、`1052008 -> 8920000`、`1058020 -> 8930000`，其他庭院装饰 reactor 不召 Boss。
- Portal：补齐 `rootafirstDoor`、`rootasecondDoor`、`rootathirdDoor`、`rootaforthDoor`、`rootaNext*`、`rootabyssOUT/rootabyssGardenOut`、`outrootaBoss`、`shijieshu`、`banbanGoInside`，同步 `scripts` 和 `scripts-zh-CN`。

兼容处理：

- 神说散 IMG 使用 EMS key；写入本项目 `clien/Data` 前必须解析后重写为 GMS key，不能直接复制。
- 小地图文字缺失时需要同时补客户端 `clien/Data/String/Map.img` 和服务端 `String.wz/Map.img.xml`。本批只在 `victoria` 下 upsert 191 个 `1052` 地图名，`105200901-105200909` 因神说源端缺字符串，使用 `鲁塔比斯 / 贝伦洞穴` 兜底，避免全量重写无关字符串节点。
- `1052` 地图的 `mapMark=rootabyss` 在神说源包和当前客户端 `Map/MapHelper.img/mark` 中都没有对应节点，进图会踩到“地图文件存在但外部引用缺失”的老坑；当前已从客户端 IMG 和服务端 XML 的鲁塔比斯地图 info 中移除 `rootabyss` mapMark。
- 鲁塔比斯地图引用 `Bgm29/*`，当前客户端原本没有 `clien/Data/Sound/Bgm29.img`；已从神说 `Sound/Bgm29.img` 按 GMS key 重写补入。
- 鲁塔比斯地图会引用通用 `Map/Obj/connect.img/rope/59/*` 和 `Map/Obj/effect.img/quest/gate/8`。按希纳斯 `connect.img` 经验，只补缺失子节点，不全量覆盖通用 IMG。
- 地图兼容清洗会移除高版本/不必要字段：`info/standAlone`、`info/partyStandAlone`、`info/noMapCmd`、空 `fieldScript/onFirstUserEnter/onUserEnter`、对象 `hide/reactor/flow`、portal `delay/hideTooltip/onlyOnce` 和空脚本。
- Boss 兼容清洗遵循进阶扎昆、希纳斯和阿卡伊勒经验：不向客户端硬塞未知 `MobSkill` 顶层或高版本等级；移除 `finalmaxHP/defaultHP/ignoreFieldOut/showNotRemoteDam/publicReward/explosiveReward/useReaction` 等高版本字段；`mobType` 统一为旧端整数 `1`；`info/skill` 只保留当前客户端和服务端都存在、且有对应 `skillN` 动作的技能，并重排为连续索引。当前仍裁掉的典型技能包括 `117/*`、`132/10`、`170/12/81`、`186/8`、`188/*`、`201/59/60`、`211/20`、`266/1`。贝伦 `8930000` 原技能 action 没有对应 `skillN` 动作，默认先不启用技能，保证召唤稳定。
- Boss 二阶段真血量按 `docs/patches/2121006-aoe-analysis.md` 的 long HP 方案处理：`8900001/8910001/8920001/8930001` 只在服务端 XML 写 `<string name="maxHP" value="3000000000"/>`，客户端 `clien/Data/Mob/*.img` 保持原 int 安全血量，避免旧客户端读取超过 `2147483647` 的 `maxHP` 崩溃。客户端多管血由服务端 Boss HP 封包把真实 long HP 压成当前管 int 血条。
- Boss 阶段/辅助 mob 也必须补旧服务端必读字段。实机击杀混沌血腥女王 `8920000` 后，`revive -> 8920001` 会触发 `LifeFactory.getMonsterStats()`，旧服务端无默认值读取 `PDDamage/MDDamage`，缺失时会 NPE 并导致当前地图崩溃。当前迁移脚本会给全部进阶 Boss mob 兜底 `PADamage/PDDamage/MADamage/MDDamage/level`，其中带 Boss 血条的阶段 mob 缺失 `PDDamage/MDDamage` 时补 `30000`，辅助 mob 补 `0`；审计脚本已加入对应检查。
- NPC `1064002`、`1064003`、`1064004` 已补中英文占位脚本，只提示当前阶段开放地图探索和普通怪物；Boss/商店/任务逻辑后续再逐个打开。
- 主入口顶部 `shijieshu` 原目标 `105000000` 在当前包不存在，实机会提示目标地图不存在；当前改为弹窗提示世界树上层未开放、显式 `enableActions()` 并留在原地图。主入口左右出口 `rootabyssOUT` 优先读取 `EVENT` saved location；彩虹岛这类低位地图、自由市场 `910000000` 和鲁塔比斯自身都不能当作有效返回图，当前统一兜底到 `105040300/sp`。庭院出口脚本改为唯一名称 `rootabyssGardenOut`，只回鲁塔比斯主入口 `105200000/sp`，不能读取 `EVENT`。不要再用只靠大小写区分的 `rootabyssOut`：在大小写不敏感文件系统上它会和 `rootabyssOUT` 冲突，导致庭院光圈错误传到彩虹岛或其他历史返回点。
- 全光洞复查时发现 `105200900/out00` 是普通 portal，原始目标为 `105200000/in00`，但入口图没有 `in00`，会导致落点异常；当前客户端 IMG 和服务端 XML 均改为 `105200000/sp`。审计脚本已补充检查 `tm/tn` 指向的目标 portal 名是否真实存在。
- 主入口四个 Boss 门第一版进入 `105200100/200/300/400`，这些普通庭院本身没有小怪，且左侧 `out00` 残留 `tm=910000000` 会回自由市场。当前四门改为进入带普通小怪的 `<进阶>` 庭院：`105200500/600/700/800`，每张 15 只普通怪；旧普通庭院 `out00` 和所有 `1052` 地图残留的 `forcedReturn=910000000` 已统一改回 `105200000/sp` 或 `105200000`。审计脚本已禁止鲁塔比斯地图再残留自由市场目标。
- `<进阶>` 庭院保留普通小怪体验，但 `next00/rootaNext` 不能继续按 `mapId + 10` 去 `105200510/610/710/810`，这些图没有 Boss reactor。当前 `rootaNext` 对 `105200500/600/700/800` 分别映射到真正带召唤 reactor 的 `105200110/210/310/410`。
- 四张 Boss 房 `105200110/210/310/410` 当前使用 `info/onUserEnter=rootaBossEnter` 自动召唤 Boss，分别生成 `8900000/8910000/8920000/8930000`。原因是神说来源客户端缺同 ID reactor 资源，本阶段 reactor 只是兼容占位，实机可能不可见或不好点击；自动召唤能先保证四 Boss 流程可测。原 reactor 脚本仍保留备用，`rootaBossEnter` 会检查当前地图已有怪物时不重复召唤。
- Boss 自动召唤必须走 `spawnMonsterOnGroundBelow`，不要用 `ms.spawnMonster(id, x, y)` 直接设置坐标。半半房曾出现“只显示血条、不显示 Boss”：服务端已刷出 `8910000`，但裸坐标没有贴到 foothold。当前四房间坐标使用地板上方 1px 的落点：`105200110 -> (489,454)`、`105200210 -> (-131,550)`、`105200310 -> (60,134)`、`105200410 -> (-192,442)`，由服务端向下找地面。
- 北部庭院<进阶>实机出现角色下半身被地板遮住，是因为 `garden/foot` 地板视觉对象位于前景层。其他庭院没有这个实机遮脚表现，不能套用同一层级改动；当前只把 `105200400/105200800` 的 `rootabyss/garden/foot/*` 降到第 0 层，`northNature/northArtficiality` 等前景对象保持神说源端层级。曾尝试把北部地面前景对象也整体降层，但 `105200800` 进图会崩，已收窄为只移动 foot。
- `1064005-1064008` 和 `1064016` 是庭院/门内可见 NPC，已补中英文占位脚本；审计脚本已要求所有可见 NPC 必须有对应脚本，避免点击无反应。
- `7120112-7120115` 和四个主 Boss `8900000/8910000/8920000/8930000` 必须有 `drop_data` migration 记录；审计脚本会检查迁移 SQL 中每只怪至少有金币和物品掉落，并验证 SQL 引用的物品在当前客户端与服务端资源中存在。
- 不要只看 canvas 能否解码。早期重编码会把解码失败节点落成透明 `1x1`，审计仍会通过但实机缺地板/缺墙。当前已对照神说源端修复 Root Abyss 专用视觉素材中的透明占位：`Obj/rootabyss.img` 22 个、`Obj/gran_helisium.img` 34 个、`Tile/rootabyssBan*.img/rootabyssBellum.img/rootabyssQueen.img` 共 34 个；同时重写对应服务端 XML，使异常高版本宽高回到真实尺寸。
- Boss reactor 和 Boss 房间已开放召唤；当前只保证召唤、血条、基础攻击/可用技能和保守掉落不因资源或 `MobSkill` 缺口崩溃，完整机制、专属奖励和高版本专属技能后续逐项恢复。

验证结果：

- 相关客户端 IMG 可用 GMS key 解析，`tool/scripts/audit/audit_root_abyss_maps.py` 扫描 191 张 `1052` 地图、进阶 Boss 和依赖资源，3964 个 canvas 全部可解码，并会对照源端检查“真实图片被降成透明 `1x1`”的回归，当前 `warnings=0`、`errors=0`。
- 1052 地图引用的 BGM、Map mark、Back/Obj/Tile、life、reactor、portal 脚本缺失数为 0。
- 新增服务端 XML 共 234 个可被 `xml.etree.ElementTree` 解析。
- 已迁入进阶 `890/891/892/893` Boss 兼容资源；审计会检查 Boss IMG、服务端 XML、`String/Mob`、Boss 血条 UI、技能白名单和 canvas 解码。

复查命令：

```bash
rtk python3 tool/scripts/audit/audit_root_abyss_maps.py
```
