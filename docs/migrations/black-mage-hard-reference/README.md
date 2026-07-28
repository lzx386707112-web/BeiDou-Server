# 黑魔法师 Hard 迁移与旧客户端兼容参考

> 状态：实现已从项目中移除。本文件保留删除前的设计、TMS 取证结果、兼容方法和失败经验，供后续重新迁移 Boss 时参考。文中的类名、脚本和资源路径是历史实现，不表示当前仓库仍提供这些文件。

## 1. 迁移目标与最终边界

目标客户端是 BeiDou 使用的旧版 GMS 格式客户端，来源是 TMS v280 的 64 位 Data 包。TMS 黑魔法师依赖新版 `fieldType=210`、FieldSkill、Pattern/Group 子弹、Particle、Spine 转场和地图机关，不能直接复制到旧客户端。

历史实现采用以下边界：

1. 地图、Boss 动作、NPC、BGM 和可验证的 Canvas 来自 TMS。
2. TMS 新版场地执行器无法移植的部分，由服务端定时器选择技能、广播兼容 Effect，并独立计算伤害。
3. 不让旧客户端解释 TMS 的 FieldSkill FSM、Particle、Pattern/Group 或新版场景对象。
4. 不凭视觉相似度猜素材。所有技能必须能回溯到地图、技能或 Mob 的真实引用链。
5. 大型效果统一写入 `Map/Effect.img`，使用 GMS key 重新编码为 ARGB4444，并限制同时播放数量。

这套方案最终仍遇到了素材误用和旧客户端崩溃，因此已撤回。后续重做时，应先建立最小技能闭环，再逐项放量，不能一次合并完整 P1-P4。

## 2. 资源与实体清单

### 2.1 地图

| 用途 | 地图 ID |
|---|---:|
| 返回/中转 | `450012500` |
| P1 | `450013100` |
| P2 | `450013300` |
| P3 | `450013500` |
| P4 | `450013700` |

TMS 地图源：

```text
Data/Map/Map/Map4/450012500.img
Data/Map/Map/Map4/450013100.img
Data/Map/Map/Map4/450013300.img
Data/Map/Map/Map4/450013500.img
Data/Map/Map/Map4/450013700.img
```

地图视觉依赖：

```text
Data/Map/Back/BM3_4_bossBlackMage.img
Data/Map/Obj/BM3.img
Data/Map/Obj/spinOff1.img
Data/Map/MapHelper.img/mark/Limen
Data/Sound/Bgm50.img
```

旧客户端不支持的地图根节点应删除或降级，包括 `particle`、`userSit`、`clock`、`area` 以及新版独占的复活、ARC/AUT、remoteEffect 等字段。删除前必须检查是否有技能实际引用这些节点。

### 2.2 Boss 与辅助实体

| 阶段/用途 | Mob ID |
|---|---:|
| P1 创造 | `8880500` |
| P1 破坏 | `8880501` |
| P2 | `8880502` |
| P3 | `8880503` |
| P4 | `8880504` |
| 骑士/血条兼容模板 | `8880505` |
| 红色闪电 | `8880506` |
| 哭墙 | `8880507` |
| P3 侍从 A | `8880509` |
| P3 侍从 B | `8880510` |
| P2/P3 辅助实体 | `8880511` |
| FieldSkill 攻击引用中间 Mob | `8880512` |
| 碰撞警告来源 | `8880516` |

客户端 Boss 动作来自 `Data/Mob/_Canvas/<mobId>.img`，动作元数据来自 `Mob_*.ms`。只看 `_Canvas` 会丢失 `origin`、`delay`、`action`、攻击引用和 UOL 关系。

### 2.3 NPC 与入口

```text
3003993
3005426
9091018
9091019
9091020
9091024
```

历史入口由传送 NPC 进入 `450013100`，返回裂缝通过 Encounter 查询当前阶段，再传送到该阶段的 portal 0。阶段重连不能只判断玩家当前地图，必须判断过渡状态和存活 Boss。

## 3. 必须先解 `.ms`

现代 TMS 的真实技能规则不全在 `.img`。本次取证使用：

```text
/Users/lizixian/Documents/mxd/TMS/black_mage_report_tools/ms_probe
```

工具用法：

```bash
rtk dotnet run --project /Users/lizixian/Documents/mxd/TMS/black_mage_report_tools/ms_probe/MSProbe.csproj -- \
  /path/to/Skill_00007.ms /tmp/skill-ms --list

rtk dotnet run --project /Users/lizixian/Documents/mxd/TMS/black_mage_report_tools/ms_probe/MSProbe.csproj -- \
  /path/to/Skill_00007.ms /tmp/skill-ms Skill/

rtk dotnet run --project /Users/lizixian/Documents/mxd/TMS/black_mage_report_tools/ms_probe/MSProbe.csproj -- \
  /path/to/Mob_00000.ms /tmp/mob-ms Mob/88805
```

调查顺序应固定为：

```text
地图 450013x00 的 fieldType / particle / obj / mob
  -> Skill_00007.ms 中 FieldSkill 的等级、周期和 mobattackref
  -> Mob_00000.ms 中引用 Mob 的 attack index 与 action
  -> Mob/_Canvas/<id>.img 中该 action 的 ball / hit / areaWarning
  -> _outlink 指向的共享 Canvas
```

不得在整个 Data 包里按“看起来相似”搜索图片。搜索范围只应扩展到地图实际引用、技能实际引用和引用链最终落到的共享 Canvas。

### 3.1 已确认的 P3 引用

```text
FieldSkill 100011
  laserCenterDirRotationAttack/laser
  laserCenterDirRotationAttack/ball

FieldSkill 100013
  level/1/effect
  mobattackref -> 8880512 attack index 4 -> action 4
  hit -> Mob/_Canvas/8645064.img/attack4/info/hit

FieldSkill 100015
  level/1/pre  : 24 帧
  level/1/end  : 13 帧
  mobattackref -> 8880512 attack index 5 -> action 3
  hit -> Mob/_Canvas/8645064.img/attack3/info/hit

P3 zone
  Mob/_Canvas/8645049.img/info/mobZone/3/effect
```

重要结论：`attack3/info/hit` 是紫色命中圆环，不是红球主体；红球主体是 `100015 pre/end`。命中 Canvas 属于局部命中表现，不能直接合成为全屏 Field Effect。

## 4. 历史服务端 Encounter 结构

历史实现用一个 `BlackMageEncounter` 维护四张地图的阶段状态：

```text
startOrGetCurrent
  -> P1 转场并生成 8880500 + 8880501
  -> 两只均死亡后切 P2/8880502
  -> P2 死亡后切 P3/8880503
  -> P3 死亡后切 P4/8880504
  -> P4 为终阶段
```

状态表包括：

- 正在播放转场但尚未生成 Boss 的地图。
- P1 是否已启动定时器，防止重连重复调度。
- P1 两只 Boss 的死亡位图。
- P3 六块平台的开关位图。

所有递归定时器在执行前都检查 `boss.isAlive()` 且 `boss.getMap() == map`。这是避免 Boss 死亡后任务继续堆积的必要条件。

### 4.1 阶段切换

| 转场 | 时长 |
|---|---:|
| P1 开场 | `6067 ms` |
| P2 开场 | `8367 ms` |
| P4 开场 | `6667 ms` |
| Effect 提前量 | `300 ms` |

P1 两只 Boss 都死亡后额外等待 `2000 ms`。P2 到 P3 没有独立 Spine 转场时，先生成目标 Boss，再直接切图。转场期间必须把目标地图标记为 pending，避免多名玩家同时触发重复生成。

## 5. 各阶段历史逻辑

### 5.1 P1

- `8880500` 和 `8880501` 分别生成在 `(-350, 75)` 与 `(350, 75)`。
- 每 `7290 ms` 交换位置。该值来自 TMS `attack4 = 48 * 90 ms` 加 `attackAfter=2970 ms`。
- 场景循环 `30000 ms`，其中骑士冲锋在循环第 `10000 ms` 触发，命中延迟 `1500 ms`，造成最大 HP `55%` 伤害。
- 陨石每 `60000 ms` 一轮，共 7 个落点，命中起始延迟 `2790 ms`，相邻陨石错开 `900 ms`，范围半径 `190`，伤害 `50%` 并附创造诅咒。
- 锁链针对每个玩家单独播放，随机 3 连或 10 连；相邻锁链 `700 ms`，命中延迟 `840 ms`，每次 `15%` 并附破坏诅咒。每轮结束后冷却 `5000 ms`。

锁链视觉来源：

```text
FieldSkill 100007/level/1/areaWarning       42 帧
FieldSkill 100007/level/1/...impact...      14 帧
```

垂直、左斜、右斜必须由同一真实素材旋转后生成，碰撞范围和画面方向一致。

### 5.2 P2

旧客户端同时解码多个大 Effect 容易崩溃，因此历史实现把技能串成一个 `60000 ms` 场景周期：

| 周期位置 | 技能 |
|---:|---|
| `0 ms` | 尖刺安全区 |
| `4000 ms` | 黑暗之眼 |
| `8000 ms` | 晨星滚动 |
| `13000 ms` | 跟踪锁链 |
| `21000 ms` | 第二轮尖刺 |
| `25000 ms` | 红色牢笼/闪电 |
| `31000 ms` | 哭墙 |
| `37000 ms` | 陨石排 |
| `47000 ms` | FMA |
| `56000 ms` | 碰撞冲锋 |

关键参数：

- 尖刺：3 个安全区变体，`2790 ms` 命中，安全中心 `-620/0/620`，槽宽 `155`，非安全区 `90%`。
- 晨星：两条真实路径，每条含两只；落地 `1620 ms`，第二只错开 `360 ms`；落地 `10%`，滚动 5 tick、每 `300 ms`、每人最多命中一次 `15%`。
- 黑暗之眼：选择两个存活目标，10 tick、每 `300 ms`；两个眼速度分别 `260/160`，半径 `150`，每 tick `5%`。
- FMA：Phase1 播放 `3330 ms`，完整命中在 `4410 ms`；左、右、中三种安全区，安全半宽 `180`，其余玩家致死。

真实素材：

```text
晨星：Etc/BossBlackMage.img/hard/BulletAfterObtacleCollision/Ball + End
黑暗之眼：FieldSkill 100012/level/1/pre|loop|end
FMA：FieldSkill 100017/level/1/BMTrigger2/<variant>/phase<1|2>
尖刺警告：Mob/_Canvas/8880516.img/attack1/info/areaWarning
```

FMA 的 TMS 变体映射不是界面顺序，历史验证使用 `source_variant = (1, 2, 0)[variant]`。不要绘制人造白色安全区标记，也不要拿 Boss 本体动作当屏幕效果。

### 5.3 P3

P3 有一个独立的持续 zone，以及 6 个串行技能分支。分支每轮打乱 `[0..5]` 后依次执行，因此一轮内每个技能恰好出现一次；一轮结束后重新洗牌。普通分支之间随机等待 `6000~9000 ms`。

```text
01 laser
02 blue-orb
03 red-orb
04 servant
05 collision
06 destruction/platform
```

不存在独立的 TMS `07-morning-stars`。把晨星额外加到 P3 会造成错误素材和额外纹理压力。

#### Zone

- 每 `1800 ms` 给每名玩家单独发送一次视觉，使球体跟随 Boss 而不是玩家。
- 根据 Boss HP 分三档，半径 `450/350/235`。
- 玩家在 zone 外攻击 Boss 时只保留 `10%` 伤害，至少 1 点。
- 为兼容旧版 `showEffect`，历史实现预生成 5 个相对偏移 `-800/-400/0/400/800`，按 Boss 与玩家的相对 X 选择最近版本。

#### 激光

- 一次连续 8 条，不是 8 条同时出现。
- 角度为 `0/45/90/135/180/225/270/315`。
- 每轮使用洗牌袋，8 个角度各一次；相邻轮首尾也避免重复。
- 相邻激光创建间隔随机 `350~650 ms`。
- 单条动画 `1950 ms`，在 `1080 ms` 计算命中。
- 伤害线段半宽 `42`，命中 `50%` 并附破坏诅咒。
- 画面必须同时旋转 laser 和 ball，不能只旋转光束或把全部角度缩成横竖两类。

#### 蓝球与红球

- 两种布局互为镜像。
- 蓝球主体来自 `FieldSkill 100013/level/1/effect`，一次 5 个，命中延迟 `1380 ms`，方形判定半宽 `120`，伤害 `25%` 并附创造诅咒。
- 红球主体来自 `FieldSkill 100015/level/1/pre + end`，一次 2 个，间隔/命中延迟 `1700 ms`，判定半宽 `70`、Y 范围 `-110..30`，伤害 `20%`。
- 蓝球 `attack4/info/hit` 曾作为兼容命中视觉广播。
- 红球 `attack3/info/hit` 被错误当成全屏 Effect 后，在 `03-red-orb` 附近造成黑屏崩溃；最终修正是只保留 `100015 pre/end`，服务端独立结算伤害。

#### 侍从

- 历史版本生成 `8880509/10/11`，左右各一只，共 6 只。
- 生成前检查地图是否已有这三个 ID，避免重复堆积。
- TMS 三个 ID 共享 `8880509` 的动作语义，但各自攻击参数不同；不能只复制 stand，必须保留 `attack1/info/ball` 和 `attack1/info/hit`。
- P3 Boss 死亡时主动清理全部侍从。

#### 碰撞与平台

- 碰撞左右各一只并错开 `360 ms`。
- 命中从 `630 ms` 开始，共 17 tick、每 `90 ms`，从地图一侧扫到另一侧；每名玩家一轮最多命中一次，伤害 `50%` 并附创造诅咒。
- 平台技能操作 `foo2/foo4`、`foo5/foo3`、`foot1/foo6` 三组环境对象。
- `720 ms` 后切换平台，`5000 ms` 时结算并恢复；未站在目标平台上的玩家受到 `9999` 固定伤害。

### 5.4 P4

- 场地粒子每 `6700 ms` 播放一次。
- 粒子来源是 `Effect/particle.img` 的 `bossBlackMage_4p_big` 与 `bossBlackMage_4p_small`，位置必须与 `450013700.img/particle` 完全一致。
- Pattern/Group 子弹来自 `Etc/BossBlackMage.img/Bullet`。
- 历史实现按 10 组服务端 pattern 循环调度；group `0..13` 直接生成，group `14/15` 各生成 3 个布局变体。
- 子弹兼容帧间隔 `60 ms`。type 0 使用源方向向量，type 1 使用源径向偏移推导方向；不允许静止显示。
- P4 爆炸来自 `Etc/BossBlackMage.img/Bullet/effect/pre|loop|end`，共 16 帧。

## 6. 兼容 Effect 的生成规则

### 6.1 区域、密钥与编码

```text
读取 TMS Canvas：BMS key
写入 BeiDou IMG：GMS key
像素格式：ARGB4444，format=1, format2=0
兼容视口：1368 x 768
视口原点：(683, 384)
```

不能把 TMS `.img` 的加密像素原样复制进 GMS IMG。正确流程是解码为 RGBA，再使用目标区域 key 重新编码。

### 6.2 `_outlink` 与 `_inlink`

TMS 大量 Canvas 只有 `_outlink`。旧客户端合并后通常无法解析跨 IMG 链接，因此必须：

1. 沿真实 `_outlink` 找到最终 Canvas。
2. 解码最终像素。
3. 在目标 IMG 中写入实体 Canvas。
4. 生成后的兼容 Effect 不保留跨文件 `_outlink/_inlink`。

同一 Effect 内为了减少实体帧，可以使用本地 `WzUolProperty` 指向同级数字帧。但必须确认目标客户端支持该 UOL 形式；若出现卡顿或崩溃，应先恢复更多实体帧做 A/B 测试。

### 6.3 原点与透明边界

先在 `1368x768` 场景上合成，再按 ARGB4444 实际可见 alpha 阈值裁剪透明边界。裁剪后原点应调整为：

```text
origin.x = 683 - crop.left
origin.y = 384 - crop.top
```

未裁剪的大透明画布会放大解码和纹理成本；裁剪后不修正 origin 会导致技能位置漂移。审计应检查：

- Canvas 可解码且非空。
- alpha bbox 等于画布边界，不保留透明边框。
- `origin` 和 `delay` 存在。
- 逻辑帧总时长与 TMS 动作时长一致。
- 本地 UOL 目标存在且类型正确。

## 7. 纹理预算

文件压缩大小不能代表客户端运行时纹理开销。历史审计采用保守估算：

```text
decodedBytes = width * height * 4
```

即使 ARGB4444 实际像素是 2 bytes，使用 4 bytes 预算可以覆盖解码中间缓冲、上传副本和兼容层额外拷贝。

历史阈值：

| 范围 | 上限 |
|---|---:|
| 单个大型 P2/P3 Effect 的实体 Canvas 总量 | `64 MiB` |
| 全部 P3 兼容 Effect 的实体 Canvas 累计 | `288 MiB` |

一个完整 `1368x768` RGBA 预算约为 `4.0 MiB`。因此 16 张未裁剪的实体全屏帧就会逼近 `64 MiB`。降低压力的方法依次是：

1. 裁剪透明边界。
2. 串行调度大型技能，禁止多个全屏序列重叠。
3. 只对真正重复的帧使用本地 UOL。
4. 在不破坏动作节奏的前提下降采样实体帧，并把逻辑 delay 合并到保留帧。
5. 最后才考虑缩放；Boss 和技能不应默认缩放，否则判定、原点和观感都会失真。

不要只限制单节点。旧客户端可能缓存整个 `Effect.img` 分支，P3 的累计纹理量同样会导致进入阶段即崩溃。

## 8. 经常遇到的崩溃与错误素材

### 8.1 黑屏实际是客户端崩溃

若日志停在某个分支，按以下顺序缩小范围：

1. 在服务端每个技能分支入口记录唯一名称，例如 `03-red-orb`。
2. 先禁用该分支的第二段/命中 Effect，保留主体和伤害。
3. 逐个解码该分支所有实体 Canvas。
4. 统计逻辑帧、实体帧、最大尺寸和 `width * height * 4`。
5. 检查 UOL、origin、delay、空帧和跨文件链接。
6. 确认运行端部署的 IMG 哈希与工作区一致，并完整重启客户端。

不要把黑屏当成剧情转场，也不要先减少全 Boss 的帧数。只有锁定触发分支后才能改资源。

### 8.2 命中素材被当成技能主体

`mobattackref` 指向的 `attack/info/hit` 是命中反馈，不等于 FieldSkill 主体。历史红球错误就是：真实引用链虽然正确，但播放层级错误。正确做法是：

```text
FieldSkill pre/effect/end -> 场地技能主体
Mob attack/info/ball      -> 弹体或发射物
Mob attack/info/hit       -> 局部命中反馈
```

只有确定旧客户端能在正确坐标播放局部 hit 时才迁移 hit；否则保留服务端伤害，不广播全屏 hit。

### 8.3 方形技能图标混入战斗

出现带圆角背景的方形图标，通常说明拿到了 `icon`、UI Canvas 或错误的 Effect 节点，而不是攻击动画。排查时应对比：

- 工作区实际 `Effect.img` 中该分支的逐帧图。
- Boss 与召唤物的全部实际动作帧。
- 运行端文件 SHA-256。

历史最后一次检查中，方形火流星图标不在当前 P3 Effect、Boss 或三种侍从资源里；运行端仍显示时，应优先判断旧 `Effect.img` 未替换或客户端读取了另一套 Data 路径，而不是继续猜一个新素材覆盖。

### 8.4 帧少导致卡顿

把每 4 帧仅保留一张实体 Canvas、其余全指向同一帧，可以降低内存，但会明显卡顿。应分别控制：

- 逻辑帧数量和总时长：决定节奏。
- 实体 Canvas 数量：决定画面变化和内存。
- UOL 重复跨度：决定停顿感。

对快速旋转、激光和爆炸，不应使用过大的重复跨度。先测 2:1，再测 3:1；4:1 只适用于变化很小的动画。

### 8.5 服务端调度与视觉不同步

旧端没有 TMS FieldSkill FSM 时，伤害必须由服务端按已验证命中帧延迟结算。视觉 duration、命中 delay 和下一技能调度要分别记录，不能拿动画总长直接当命中时间。

技能递归定时器还必须满足：

- Boss 已死亡或离图后不再续调度。
- 每人一轮最多命中一次的技能使用 identity set 去重。
- 分支使用洗牌袋，避免随机函数长期重复同一技能。
- 大型 Effect 完成后才开始下一分支的等待时间。

## 9. 推荐的重新迁移顺序

不要重新执行历史的一次性全量迁移。建议按以下门禁逐步推进：

1. 只迁五张地图和 P1-P4 Boss stand/hit/die，验证进图、击杀、切阶段。
2. 只迁 P1 一种技能，运行 20 分钟并重复进出地图。
3. P2 每次只增加一个场景技能，确认一分钟周期无重叠。
4. P3 先上 zone，再逐个启用 6 个分支；每个分支至少独立循环 30 次。
5. P4 最后迁 Pattern/Group 和 Particle。
6. 每增加一个兼容 Effect，重新计算单节点和阶段累计纹理预算。

每个技能的验收记录至少包含：

```text
TMS 规则来源 (.ms 路径)
TMS 像素来源 (.img / _Canvas 路径)
引用链中的 mobattackref / attack index / action
原始帧数、实体帧数、总时长、命中时刻
目标 Effect 路径
decodedBytes
服务端伤害范围与诅咒
连续播放次数与运行端文件哈希
```

## 10. 历史审计口径

删除前的审计覆盖：

- 地图、NPC、BGM 和字符串闭环。
- Boss 动作、技能 action、服务端 XML 与客户端 IMG 对齐。
- 所有 Canvas 使用 GMS key 可解码。
- 兼容 Effect 为 ARGB4444。
- 逻辑帧数量、实体帧数量、时长和 TMS builder 输出一致。
- 无跨 IMG `_inlink/_outlink`。
- 单 Effect `64 MiB`、P3 累计 `288 MiB` 预算。
- 不存在废弃的 P3 `morning-stars`、创造/破坏假特效和重复 A/B 分片。
- Java 不再引用已删除的 Effect 路径。

JDK 21 路径：

```text
/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home
```

服务端验证示例：

```bash
rtk env JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
  mvn -pl gms-server -am -DskipTests compile
```

## 11. 删除原因总结

该实现能够跑通四阶段、服务端伤害和大量真实 TMS 视觉，但兼容层承担了过多新版客户端职责。P3 尤其同时包含 zone、激光、球体、侍从、碰撞和平台机关，生成的 `Effect.img` 体积和运行时纹理压力很高；错误把局部 hit 当成全屏视觉又会直接触发旧客户端崩溃。素材修正过程中还出现运行端旧 IMG 与工作区不一致，导致错误图标持续出现。

后续若重新迁移，应把目标改为“每个技能独立、可验证、可撤回”，而不是一次还原完整 TMS 场地执行器。
