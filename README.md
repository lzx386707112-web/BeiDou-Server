# BeiDou Server

BeiDou 服务端、后台管理、客户端资源和配套工具的工作区。

## 常用入口

- 服务端：`gms-server/`
- 后台管理前端：`gms-ui/`
- 客户端资源：`clien/`
- 工具集：[tool/README.md](tool/README.md)
- 项目文档：[docs/README.md](docs/README.md)

## 常用脚本

```sh
rtk tool/scripts/package/package_server_jar.sh
rtk tool/scripts/runtime/start_server.sh
rtk tool/scripts/package/pack_img_wz.sh
rtk tool/scripts/png2canvas/png2canvas.sh
rtk tool/scripts/wz/wzpy.sh
```

更多脚本说明见 [docs/tools/tool-scripts.md](docs/tools/tool-scripts.md)。

## 迁移资料

- [095 内容迁移概览](docs/migrations/095-overview.md)
- [095 内容迁移手册](docs/migrations/095-migration.md)

## 排障经验

- 迁移地图、怪物、Boss 后出现黑屏、崩溃或怪物外形不对时，先看 [095 内容迁移手册](docs/migrations/095-migration.md)。其中记录了地图资源审计、召唤 Boss 后崩溃、Boss 血条 UI、MobSkill、阿卡伊勒 `8860000` 兼容修复，以及 `9300301/9300302/9300304` 占位怪资源替换等经验。
- 新增或改造技能时，先看 [新增技能与 BeiDou.exe 识别记录](docs/patches/new-skills-exe-notes.md)。其中记录了龙神技能、矩形 AoE、`1121001` 磁石改造成轻舞飞扬式攻击，以及继续迁移成 `400011124` 剑影分身的完整排查过程：WZ 数据、`effect/effect0`、服务端技能类型、EXE 小端编码、code cave 追加判断、伤害延迟和攻击范围对齐；也记录了“消耗品热键触发服务端技能”的不改 EXE 备选思路。

## 当前技能试验：斗气死亡断层

当前测试目标是 273 导出的 `_Canvas/40001.img` 下 `400011027`，技能名“斗气死亡断层”，说明为“用剑分割空间”。源技能包含 `effect`、`screen`、`special`、`hit` 四类表现：

```text
effect: 角色施法动画
screen: 全屏字段动画
special/hit: 怪物被击中时的表现
```

阶段性结论：

```text
1. 直接把资源放进 232 技能路径后，2321010 作为客户端已识别技能，可以触发 effect 动画。
2. 通过 2430125 消耗品触发服务端逻辑时，目前稳定能看到 screen，但看不到 effect/special/hit。
3. 这说明消耗品路径和“客户端自己按技能”的本地技能释放链路不等价。
4. 服务端主动广播 SKILL_EFFECT / CLOSE_RANGE_ATTACK 更像是给其他客户端看的同步包，不能保证让本机客户端补齐按技能时的本地动画链。
5. 把 2430125 从 spec/script/npc 脚本道具改成普通消耗品壳 spec/hp=0 后，仍然不能满足预期：拖键/触发链路依旧不可靠，也没有补出 effect/special/hit。
6. 因此 2430125 消耗品路线不适合作为“完整技能释放”方案，最多只能作为服务端入口、冷却、范围选怪、伤害结算、FIELD_EFFECT 全屏表现的辅助触发器。
7. 完整技能动画必须以客户端认识的 skillId 为基准，让客户端实际走技能释放链路。
```

当前实现策略：

```text
视觉壳技能: 2321010
源视觉技能: 400011027
触发道具: 2430125
冷却: 5 秒
MP 消耗: 500
伤害: 416%
攻击段数: 14
最大目标: 15
范围: lt=(-3000,-2000), rb=(3000,2000)
全屏动画路径: Map/Effect.img/customSkill/deathFault/screen
```

`2321010` 是临时视觉壳，用来验证“客户端已识别技能 ID + 迁移后的 273 视觉资源”是否能完整播放。这个测试会临时覆盖原先 `2321010` 龙神复刻技能的外观；如果验证成功，再考虑迁到独立技能 ID 并补 EXE 识别。

`2430125` 曾尝试两种形态，都没有达成“像技能一样完整释放”的目标：

```text
方案 1: spec/script/npc 脚本道具
结果: 服务端可接入，但放键盘/按键链路不可靠，只能看到 screen。

方案 2: 普通消耗品壳 spec/hp=0
结果: 仍然不满足预期，不能作为完整技能动画触发路径。
```

当前普通消耗品壳形态如下，仅保留为排查记录：

```text
02430125
  info
  spec/hp = 0
```

服务端在 `UseItemHandler` 中按 itemId 先拦截 `2430125`，再进入 `CustomSkillCastService`。这一步已经验证过，不能解决完整动画问题；后续不要再围绕“消耗品能否天然触发 effect/special/hit”反复试。

最终建议：

```text
主路线: 把 400011027 正式迁成客户端认识的技能 ID，必要时补 BeiDou.exe 识别，让玩家实际按技能触发 effect/hit/special。
备选路线: 接受消耗品只做服务端触发器，screen 用 FIELD_EFFECT 播，伤害由服务端结算，不追求完整技能动画。
```

相关落地点：

```text
clien/Data/Item/Consume/0243.img
clien/Data/String/Consume.img
clien/Data/Map/Effect.img
clien/Data/Skill/232.img
clien/Data/String/Skill.img
gms-server/wz/Item.wz/Consume/0243.img.xml
gms-server/wz/String.wz/Consume.img.xml
gms-server/wz/Skill.wz/232.img.xml
gms-server/wz/String.wz/Skill.img.xml
gms-server/src/main/java/org/gms/net/server/channel/handlers/UseItemHandler.java
gms-server/src/main/java/org/gms/net/server/channel/handlers/ScriptedItemHandler.java
gms-server/src/main/java/org/gms/server/skills/CustomSkillCastService.java
gms-server/src/main/java/org/gms/client/command/commands/gm3/CustomSkillCommand.java
tool/scripts/patch-skill/patch_400011027_consumable_test.py
```

测试顺序：

```text
1. 重启服务端，让 Java 入口和服务端 WZ XML 重新加载。
2. 重启客户端，让 0243.img、Consume.img、Map/Effect.img、Skill/232.img、String/Skill.img 更新生效。
3. 先用 2321010 真技能验证 effect 是否仍能出现。
4. 不再把 2430125 作为完整动画测试重点；它只用于确认服务端触发和 FIELD_EFFECT screen。
5. 后续重点转向独立技能 ID/EXE 识别/技能栏或快捷键真实释放。
```
