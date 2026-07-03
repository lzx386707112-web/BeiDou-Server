# Boss 视觉资源与 MobSkill 兼容记录

本文记录从 273 客户端资源迁移 Boss 本体、大招动画、全屏特效到 BeiDou 时的判断。目标是先解决“视觉能显示、动画能播放”，不包含完整 Boss 机制、地图脚本、阶段切换、奖励逻辑。

## 结论

视觉层面，BeiDou 当前客户端节点结构可以承载 Boss 全屏动画和大特效。

不建议一开始修改 `BeiDou.exe`。更稳的方式是：

1. 把 273 的 Boss 本体动作合并到 BeiDou 客户端 `Mob` 资源。
2. 把 273 的 MobSkill 动画节点合并到 BeiDou `Skill/MobSkill.img`。
3. 服务端扩展或映射 `MobSkillType`。
4. 对超过 `255` 的 273 MobSkill ID 做重映射，而不是改客户端协议。

只有在必须保持 273 原始 MobSkill ID 时，才考虑修改 `BeiDou.exe` 的怪物移动/技能协议解析。

## 资源结构对比

BeiDou 当前客户端怪物技能资源是单文件：

```text
clien/Data/Skill/MobSkill.img
  <skillId>
    level
      <level>
        effect / hit / special / affected / ...
```

273 转换后的怪物技能资源是拆分结构：

```text
273/sanjindao/Data/Skill/MobSkill/_Canvas/<skillId>.img
  level
    <level>
      effect / hit / special / affected / ...
```

因此迁移时不能把 273 的 `_Canvas` 目录直接复制进 BeiDou。应当把 273 `<skillId>.img` 的根节点内容合并到 BeiDou 的：

```text
clien/Data/Skill/MobSkill.img/<targetSkillId>
```

例如 273 的 `Skill/MobSkill/_Canvas/238.img` 应合并成 BeiDou 的：

```text
Skill/MobSkill.img/238/level/...
```

## Boss 视觉资源组成

单纯做 Boss 视觉迁移时，通常涉及这些资源：

```text
Boss 本体动作:
  273/sanjindao/Data/Mob/_Canvas/<mobId>.img

Boss 会放哪些技能:
  273/tms273/WZ_JSON_TW/Mob/<mobId>.json

怪物技能动画:
  273/sanjindao/Data/Skill/MobSkill/_Canvas/<skillId>.img

怪物技能规则:
  273/tms273/WZ_JSON_TW/Skill/MobSkill/<skillId>.json

Boss 专属特效:
  273/sanjindao/Data/Etc/_Canvas/Boss*.img
  273/sanjindao/Data/Mob/BossPattern/_Canvas/Boss*.img

文本:
  273/sanjindao/Data/String/Mob.img
  273/sanjindao/Data/String/MobSkill.img

声音，可后补:
  273/sanjindao/Data/Sound/Mob.img
  273/sanjindao/Data/Sound/MobSkill.img
  273/sanjindao/Data/Sound/MobVoice.img
  273/sanjindao/Data/Sound/MobPattern.img
```

## 当前 BeiDou 的限制

服务端当前 `MobSkillType` 只支持老版本的一批 ID：

```text
100, 101, 102, 103,
110, 111, 112, 113, 114, 115,
120..129,
131..136,
138,
140..146,
150..157,
170..172,
200
```

相关文件：

```text
gms-server/src/main/java/org/gms/server/life/MobSkillType.java
gms-server/src/main/java/org/gms/server/life/MobSkillFactory.java
gms-server/src/main/java/org/gms/server/life/LifeFactory.java
gms-server/src/main/java/org/gms/net/server/channel/handlers/MoveLifeHandler.java
gms-server/src/main/java/org/gms/util/PacketCreator.java
```

怪物移动和怪物技能响应包里，`skillId` 和 `skillLevel` 都按 byte 写入：

```java
p.writeByte(skillId);
p.writeByte(skillLevel);
```

所以当前协议天然适合 `0..255` 的 MobSkill ID。273 中 `238`、`242` 这类 ID 可以走这个范围；`264`、`268`、`274` 这类 ID 超过 `255`，不建议原样使用。

## 推荐映射策略

优先保留 `<=255` 的原 ID：

```text
136  黑魔法师相关，可直接用
238  露希妲相关，可直接扩展服务端支持
242  威爾相关，可直接扩展服务端支持
```

对 `>255` 的新技能做映射：

```text
264 -> 244  受選的賽蓮
268 -> 245  卡洛斯
274 -> 246  咖凌
```

映射时需要同步改三处：

```text
1. BeiDou 客户端 Skill/MobSkill.img:
   写入目标 ID，例如 244/245/246。

2. Boss 本体 Mob img 的 info/skill:
   把 skill=264 改成 skill=244。

3. 服务端 Mob XML 或等价数据:
   把对应 Boss 的 skill 引用改成映射后的 ID。
```

如果只做视觉展示，也可以把大特效改挂到：

```text
Effect/BasicEff.img/customBoss/...
```

然后通过现有脚本接口触发：

```java
PacketCreator.showEffect("customBoss/...")
PacketCreator.environmentChange(path, 3)
```

这种方式更适合手动演示或剧情演出，不适合还原 Boss 自动放招。

## 是否需要改 BeiDou.exe

多数视觉迁移不需要改 `BeiDou.exe`。

不需要改 exe 的情况：

- 只是补 Boss 本体动作。
- 合并 `Skill/MobSkill.img` 中 `<=255` 的技能节点。
- 使用空闲 `201..255` 做技能 ID 重映射。
- 用 `showEffect` / `environmentChange` 播放普通场景特效。

可能需要改 exe 的情况：

- 必须保留 `264/268/274` 这种超过 byte 范围的原始 MobSkill ID。
- 希望客户端按 273 的新版协议解析怪物技能。
- 希望复刻 273 新 Boss 的特殊 UI、场地机关、专属对象协议。

这类修改比已有技能 AoE 补丁难，因为它不是简单把新 ID 接到旧分支，而是涉及客户端包解析字段宽度和后续偏移。若没有强需求，优先重映射。

## 第一批建议目标

建议先选视觉价值高、依赖较可控的目标：

```text
威爾:
  Mob 8880303
  MobSkill 170, 146, 242

露希妲:
  Mob 8880140
  MobSkill 238, 201

黑魔法師:
  Mob 8880502
  MobSkill 136
  Etc/BossBlackMage.img

受選的賽蓮:
  Mob 8880600
  MobSkill 264 -> 建议映射到 244
```

卡洛斯和咖凌资源很新，但专属特效、阶段、机关依赖更重，建议放到后面。

## 最小验证闭环

第一阶段只验证视觉，不做完整机制：

1. 在 BeiDou 客户端补入 Boss 本体 `.img`。
2. 补入或合并相关 `MobSkill.img/<skillId>` 节点。
3. 服务端扩展 `MobSkillType` 或建立映射。
4. 用 GM 命令或临时脚本触发目标 MobSkill。
5. 确认客户端不崩溃，Boss 动作和大帧动画能显示。

通过后，再逐步补伤害范围、召唤物、阶段切换、场地机关和奖励。
