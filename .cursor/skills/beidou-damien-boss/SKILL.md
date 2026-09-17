---
name: beidou-damien-boss
description: >-
  Documents Damien (戴米安 8880110/8880111) remaining server combat: projected
  MobSkill 100/101/123/128 plus phase-one skill2 orbs in DamienBossCompat.
  Use when changing DamienBossCompat, MoveLifeHandler Damien branches,
  MobSkill 176/185 Damien no-ops, never-summon 8880102, DamienBattle scripts,
  or when someone tries to restore stigma, swords, altar, percent TAKE_DAMAGE,
  Lucid 185, Akayrum 176, or MCV FIELD_EFFECT.
---

# 戴米安：只保留投影技能 + skill2 光球

本体动作由 IMG 播放。服务器 **不要** 再挂 Encounter、刻印、祭坛、百分比近战、MCV。
`DamienBossCompat` 做一阶段 `skill2` 光球，以及二阶段 `attack3` 两排球、`8880113` 暗影球、`8880114` 飞剑。其余技能走通用 `MobSkill.applyEffect`。

改戴米安前先读本 skill，并遵守 `beidou-wz-img`（禁止整文件重写现有 client IMG）。

## 允许的技能合同

| 端 | 内容 |
| --- | --- |
| 本体 `8880110` / `8880111` | `info/skill` 投影到 v83：**100** ATTACK_UP、**101** MAGIC_ATTACK_UP、**123** stun、**128** seduce。不要绑 176/185/170/215。 |
| `skill2` 动作 | 一阶段 `MOVE_LIFE` `skillActionIndex==1`。IMG 自己播飞天；Java 只在落地后排队光球。 |
| 光球视觉 | **禁止 `8880102`，也不召唤 `8880101`。** 旧端从 skill 姿势打不出弹，所以投影到 **`8880112`**：`LifeFactory.getMonster(8880112)` → `setPosition(plan.start)` → `spawnMonster`。弹道合同同露希妲 `attack1/info/ball type=2`，像素来自 TMS `8880101/attack3/info/ball`（约 70px 球体，最长边 cap 96）。**扣血只走客户端 TakeDamage + `fixDamR=20`**，不要服务端贝塞尔抢先 `addHP`。不要假怪、不要 `resetMobPosition`。不要地板 perch。 |
| 出球节奏 | 等 `SKILL2_AIRBORNE_MS=2790` 后刷 `8880112` 在天上，再落到**地面**（玩家/本体脚底），让球自己 firstAttack。**不要**再广播 `customBossDemian/groundBurst`。 |
| 二阶段 | `startPhase` 后：只刷 **2 个** `8880112` **贴地**左右巡逻；`8880113` 仍半空巡逻。`8880114` 轨迹代码保留，**`SPAWN_FLYING_SWORDS=false` 先不刷**。**禁止召唤 `8880102`。** attack3 不再加刷金球。 |

`MobSkill.java`：戴米安撞到残留 **176 / 185** 直接 `return`，不要播阿卡伊勒碎屏或路西德碎梦。病态技能照常 `applyDisease`。

## 禁止恢复

- `usesCustomCombat` / Encounter / `onAttackStart` / `onAttackHit` / `onPlayerDamaged`
- `tryClearStigma`、祭坛清印、`STIGMA_CAP`
- 仓库里的 `DamienBattle.js` 转二阶段必须调 `startPhase(map, boss, 2)`。不要调 `onPlayerEnter` 恢复刻印。

脚本异常必须 `log.error`，不要 `printStackTrace()`（只进终端，不进 `logs/gms-server.log`）。
- `SHADOW_SWORD` 原 TMS ID / Encounter 飞剑。飞剑视觉走 `8880114`，不要把 `Etc/BossDemian.img` 整文件塞进旧端。
- `customBossDemian/scene` 的 7x5 MCV 标记可留着不用。`groundBurst` 现在是 skill2 场景技能的真实 Canvas，由 `showEffect("customBossDemian/groundBurst")` 播放。不要回种 `damien-scene.mcv` / `damien-ground.mcv`。
- 整文件序列化 `Effect.img` 去拆 marker（二进制风险）；marker 可留着不用

## `DamienBossCompat` 方法与参数

### `isDamien(int mobId)`

- **mobId**：怪物模板 ID。
- **返回**：`8880110` 或 `8880111` 为 true。
- **用途**：MoveLife / MobSkill 识别戴米安，避免走 Lucid/Akayrum 分支。

### `startPhase(MapleMap map, Monster boss, int phase)`

- **phase=2**：玩家在图上后刷 `8880113`、2 个贴地 `8880112`。不要刷 `8880114`（`SPAWN_FLYING_SWORDS=false`），不要刷 `8880102`，不要 walk `MOVE_MONSTER`。
- **其它 phase**：忽略。`onPlayerEnter` 仍为空。

### `stop(MapleMap map)`

- **map**：副本图；null 直接返回。
- **逻辑**：摘掉该图 `Skill2OrbField` / `PhaseTwoField`，取消 tick 和待刷任务，`killMonster` 已刷出的 `8880112` / `8880113` / `8880114`。换图、清场、dispose 必须调。

### `onSkill2Cast(Monster monster)`

- **monster**：正在放 skill2 的本体。
- **门闩**：null / 无图 / **不是 8880110** 则忽略（二阶段不出球）。
- **逻辑**：按图复用 `Skill2OrbField`，把本次计划追加进队列。延迟不看 MobSkill 101 动画时长，只看 `SKILL2_AIRBORNE_MS`。

调用点：`MoveLifeHandler` 在 `resolveCastSkill` 成功且 `skillActionIndex == 1` 时，**先** `onSkill2Cast`，**再** 走通用 `applyDelayedEffect` / `applyEffect`（100/101 等仍生效）。

### `onAttack3Cast(Monster monster)`

- **门闩**：不是 `8880111` 则忽略。动画期间 2.2s 冷却，避免 MOVE_LIFE 连打。
- **逻辑**：本体 `attack3` 的 type=2 **只会飞出 1 颗弹**。场地金球只在 `startPhase` 刷 2 个，这里不再加刷。

### `planSkill2Orbs(Point sky, Point ground, Random random)`

纯函数，单测覆盖。

| 参数 | 含义 |
| --- | --- |
| `sky` | 天上起点。运行时用本体 `x`、`y - SKILL2_SKY_OFFSET_Y`（520；天上 origin≈661 对 stand≈146）。 |
| `ground` | 扇形落地下限 / 单球瞄准参考。优先当前控制器脚底，否则图上第一个角色，再否则本体位置。 |
| `random` | 单球横向抖动、时长、贝塞尔控制点。测试传入固定种子。 |

**返回** 6 条 `Skill2OrbPlan`：

1. **fan ×2**，`delayMs=0`，角度 `-0.55,0.55` 弧度，水平 `sin*FAN_TRAVEL(480)`，下落 `|cos|*480`，`end.y = max(计算值, ground.y)`，时长 `FAN_DURATION_MS=1100`。`targetId` 运行时为 0（不追人）。
2. **single ×4**，`delayMs = 180 * index`，起点在 sky 附近随机，终点在 ground.x±120、`ground.y`，时长 800–1200ms。运行时 `targetId` 锁控制器，tick 里刷新 `end`。

`Skill2OrbPlan` 字段：`wave`（`"fan"`/`"single"`）、`start`/`control`/`end`、`durationMs`、`delayMs`。

### `bezier(Point start, Point control, Point end, double t)`

二次贝塞尔。`t` clamp 到 `[0,1]`。tick 用 `(now-startAt)/durationMs`。

### `swordPathPoint(int pattern, double t, Point center, int ampX, int ampY)`

飞剑参数曲线。0 横向 8 字（`x=A sin t`，`y=B sin t cos t`），1 反向 8 字，2 椭圆。朝向用 `t` 与 `t+Δ` 的水平差决定站立左右。

## 场地 tick 关键逻辑

`Skill2OrbField` 每图一份，`TICK_MS=250`。

1. `cast`：算 sky/ground，把 plan 只用来排队 `spawnMonster(8880112)`（`startAt = now + 2790 + delayMs`）。射手刷在 `plan.start`（天上），不要地板 perch。同一时刻 `showEffect(customBossDemian/groundBurst)`。
2. 客户端 `attackAfter=1260` 后 type=2 金火飞出；命中由 TakeDamage 的 `fixDamR=20` 结算。不要服务端扫过即伤。
3. 本体死亡或离图：`stop`。

禁止 `8880102`。禁止把射手当飞体挪位。不要塞进 `skill2/ball`，也不要把光球做成 MobSkill `_Canvas` 或往 v83 `MobSkill.img` 合并 TMS 200+。

## 资源与验证

- 光球资源：`clien/Data/Mob/8880112.img`（球体像素来自 TMS `8880101/attack3/info/ball`）。`8880102` 仍禁止召唤。生成器 `tool/scripts/migration/patch_damien_skill2_gold_orbs.py`。
- 暗影球：`clien/Data/Mob/8880113.img`（像素来自 TMS `8880102` move/regen/die1）。飞剑：`clien/Data/Mob/8880114.img`（像素来自 `Etc/BossDemian` flyingSword）。生成器 `tool/scripts/migration/patch_damien_p2_field_mobs.py`。
- 合同：`DamienBossCompatTest`（扇形+交错+横向 8 字飞剑+2 个二阶段金球）、`test_demian_contract.py`、`test_damien_p2_field_mobs.py`。
- `test_damien_boss_mcv.py` 断言 Java/DLL **不再** 播 Damien MCV，Video 文件保持删除。
- 不要为这次任务重打包 WZ 或编译 JAR，除非用户明确要求。
