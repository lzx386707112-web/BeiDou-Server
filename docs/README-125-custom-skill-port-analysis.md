# 125 自定义主动技能方案移植分析

## 1. 背景与目标

`/Users/lizixian/Downloads/125` 分享了一套通过 GM 命令和消耗品触发自定义技能的实现，主要目标是绕过客户端主程序对主动技能 ID 的限制，使服务端能够主动组织一次技能表现和伤害结算。

分享方案大致包含：

1. 在客户端和服务端 WZ 中增加技能，例如 `1321018`。
2. 增加 `2430125`、`2430126` 等脚本消耗品。
3. 增加 `!sx`、`!six` 等 GM 测试命令。
4. 服务端构造攻击上下文并主动发送技能表现、攻击和飘字封包。
5. 按固定顺序执行表现、伤害结算和动作解锁。
6. 通过消耗品的 `spec/script` 属性选择需要执行的技能。

本分析要回答：

- 125 到底绕过了客户端的哪一层限制？
- 服务端如何让客户端按照技能 ID 查找并播放 WZ 节点？
- 全屏特效与人物技能特效分别走什么路径？
- 这套思路能否迁移到当前 BeiDou v83 项目？
- 哪些部分可以复用，哪些部分必须针对当前客户端重新实现？

## 2. 最终结论

125 方案没有让客户端 EXE 真正“学会一个新主动技能”，也没有完全绕过 EXE。

它绕过的是客户端的**本地主动施法入口**，然后利用客户端已有的**服务端下行封包处理入口**，让 EXE 以“服务器通知某角色已经释放技能”的方式加载 WZ 资源并播放部分表现。

准确模型如下：

```text
正常主动释放：

玩家按技能键
  → EXE 主动技能分发和合法性判断
  → EXE 根据技能类型组织动作及上行攻击包
  → EXE 从 Skill.wz 读取对应表现
  → 服务端收到攻击包并结算

125 服务端主动释放：

消耗品或 GM 命令
  → 服务端选怪并构造 AttackInfo
  → 服务端向客户端发送表现封包和攻击广播包
  → EXE 的网络封包处理器接收技能 ID
  → 网络处理器按技能 ID 尝试读取 Skill.wz 节点
  → 服务端直接执行权威伤害结算
  → 服务端补充飘字并解锁动作
```

因此：

- 它仍然经过 EXE；所有画面最终都由 EXE 渲染。
- 它没有经过 EXE 的本地按键主动施法分支。
- 自定义技能 ID 是否能播放，取决于具体下行封包处理器是否会通用地按 ID 查 WZ。
- EXE 完全没有实现的高版本机制，仍然不能仅靠增加 WZ 节点实现。
- 全屏画面可以转入 `Map/Effect.img`，通过字符串路径播放，这条路线最稳定。

## 3. 为什么新增 WZ 技能后只有伤害、没有特效

客户端 WZ 中存在一个技能节点，不代表 EXE 会主动使用它。

新增技能后通常会出现以下状态：

```text
服务端 SkillFactory 能读取技能
服务端能计算范围、段数和伤害
服务端能直接扣除怪物 HP
客户端 EXE 的主动施法入口不接受该技能 ID
客户端没有建立人物动作和技能效果上下文
最终表现为只有扣血或攻击数字，没有完整技能动画
```

客户端主动技能入口通常还需要知道：

- 技能属于近战、远程、魔法、召唤还是特殊技能；
- 应当发送哪一种攻击包；
- 是否需要蓄力、坐标、组合键或特殊状态；
- 应当播放哪个人物动作；
- 是否创建召唤物、投射物或场景对象；
- 是否进入客户端专属的技能控制状态。

这些行为很可能存在技能 ID、职业或技能类别判断，所以单纯增加 WZ 节点不能补齐 EXE 逻辑。

## 4. 服务端如何让客户端按技能 ID 查找 WZ

服务端不会读取客户端 WZ，也不会向客户端发送完整 WZ 路径。

服务端通常只发送：

```text
角色 ID
技能 ID
技能等级
动作/display
方向
速度
坐标
怪物 OID
伤害列表
```

客户端网络处理器收到技能 ID 后，可能执行类似逻辑：

```text
OnSkillEffect(packet)
  → 读取 characterId、skillId、level
  → 查找角色对象
  → SkillWzManager.GetSkill(skillId)
  → 根据 skillId 定位职业 WZ 文件和 skill 节点
  → 播放该封包所支持的 effect/action/hit 子节点
```

例如：

```text
技能 ID 1321018
  → 解析职业资源组 132
  → Skill/132.img
  → skill/1321018
```

关键区别是客户端内部可能存在两个入口：

```text
本地主动施法入口：
  需要识别技能类型和全部客户端行为，容易存在 ID 限制。

服务器广播表现入口：
  只负责显示服务器通知的技能，可能会直接按技能 ID 查 WZ。
```

125 利用的是第二个入口。

但是，某个下行包通常只负责部分节点。发送一次 `SKILL_EFFECT` 不等于播放技能节点下的全部内容。

## 5. 125 方案使用的表现封包

### 5.1 `SHOW_SPECIAL_EFFECT`

125 通过 `EffectPacket.showOwnBuffEffect` 给施法者发送特殊效果通知。

它用于建立本机技能效果上下文，并让客户端按技能 ID 尝试读取对应的效果数据。

实现位置：

```text
/Users/lizixian/Downloads/125/src/tools/packet/EffectPacket.java
```

### 5.2 `SKILL_EFFECT`

125 的 `MaplePacketCreator.skillEffect` 包含：

```text
fromId
skillId
level
display
direction
speed
position（可选）
```

实现位置：

```text
/Users/lizixian/Downloads/125/src/tools/MaplePacketCreator.java
```

这类包的含义不是“玩家现在主动按下了这个技能”，而是“显示某个角色的技能效果”。

### 5.3 `SHOW_SPECIAL_ATTACK`

125 额外发送特殊攻击表现包，字段包括：

```text
角色 ID
时间戳
坐标
display
技能 ID
技能等级
朝向
速度
```

它用于给客户端补充动作、坐标和特殊攻击上下文。

这可能是 125 客户端中绕开正常主动施法分发表的关键通用入口之一。

### 5.4 `EXPLOSION_ATTACK`

125 还存在：

```text
技能 ID
坐标
怪物 OID
次数
```

它用于建立爆炸或命中上下文。某些技能的 hit、explosion 和伤害数字需要这类上下文才会正常显示。

当前项目没有发现与 125 同协议、同结构的 `EXPLOSION_ATTACK`。

### 5.5 攻击广播包

125 最终仍会发送近战或魔法攻击包，攻击包内包含技能 ID、目标 OID 和伤害列表。

一个重要细节是：攻击包必须明确发送给施法者本人，然后再广播给其他玩家。

```text
先：player session write(packet)
再：map broadcastMessage(player, packet, false)
```

如果地图广播方法默认排除施法者，只广播而没有单独发送给本人，可能出现：

- 怪物实际扣血；
- 其他玩家能看到部分攻击；
- 施法者本人看不到技能动作或命中表现。

## 6. 125 的 `!sx` 执行顺序

125 的 `!sx` 主链可以简化为：

```text
可选：SHOW_SPECIAL_EFFECT + SKILL_EFFECT
→ EXPLOSION_ATTACK，OID=0，初始化表现或命中上下文
→ 给本人发送攻击包
→ 给地图其他玩家广播攻击包
→ 结算前发送飘字
→ 服务端 applyAttack 权威结算
→ 结算后补飘字
→ enableActions
→ 延迟再次 enableActions，避免客户端动作锁死
```

125 相关核心文件：

```text
/Users/lizixian/Downloads/125/src/handling/channel/handler/DamageParse.java
/Users/lizixian/Downloads/125/src/handling/channel/handler/HexaSkillExecutor.java
/Users/lizixian/Downloads/125/src/client/messages/commands/GMCommand.java
/Users/lizixian/Downloads/125/src/handling/channel/handler/InventoryHandler.java
```

这不是一个小型命令补丁，而是建立了一套服务端主动攻击编排器。

## 7. 技能表现不是一条统一路径

高版本技能需要按表现类型拆分。不同类型由不同客户端入口播放。

### 7.1 人物动作和人物周围特效

通常来源于：

```text
Skill.wz/<job>.img/skill/<skillId>/action
Skill.wz/<job>.img/skill/<skillId>/effect
Skill.wz/<job>.img/skill/<skillId>/affected
```

可能需要：

- `SKILL_EFFECT`；
- 攻击广播包；
- 客户端认识的动作名；
- 客户端支持该技能 ID 或该封包处理器允许通用查 WZ。

这是移植风险最高的部分之一。

### 7.2 命中特效和投射物

通常来源于：

```text
hit
ball
affected
特殊 explosion 节点
```

它们可能绑定：

- 攻击包中的技能 ID；
- 怪物 OID；
- 攻击段数；
- 专用命中封包；
- 客户端内置技能逻辑。

当前 v83 没有 125 同型的 `EXPLOSION_ATTACK`，不能假设复制 opcode 或字段后即可工作。

### 7.3 全屏特效

全屏特效可以脱离技能 ID，改走：

```text
Map/Effect.img/<字符串路径>
```

服务器发送 `FIELD_EFFECT`：

```text
mode = 3
path = customSkill/deathFault/full
```

客户端根据字符串路径加载：

```text
Map/Effect.img/customSkill/deathFault/full
```

这条路径不要求 EXE 的主动技能入口认识 `1321018`。

### 7.4 音效

当前项目可以使用 `FIELD_EFFECT mode=4` 播放声音路径。

因此高版本技能音效可以和全屏动画独立编排，而不必强制依赖技能节点。

## 8. 当前项目已有的全屏特效能力

当前项目发送全屏场景效果的实现位于：

```text
gms-server/src/main/java/org/gms/util/PacketCreator.java
```

核心接口：

```java
PacketCreator.showEffect(path)
PacketCreator.playSound(path)
PacketCreator.environmentChange(path, mode)
PacketCreator.mapEffect(path)
```

对应发送码：

```text
FIELD_EFFECT = 0x8A
```

当前项目已经存在死亡断层全屏效果的调用：

```text
gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java
```

逻辑为：

```text
收到死亡断层攻击
→ 广播 customSkill/deathFault/full 全屏效果
→ 延迟 1000ms
→ applyAttack 结算伤害
```

这已经证明：

- 当前客户端支持按 `Map/Effect.img` 字符串路径播放全屏动画；
- 全屏动画可以与实际伤害时间独立控制；
- 高版本 `screen` 画面可以转换到当前客户端支持的场景效果结构。

当前资源转换脚本：

```text
tool/scripts/patch-skill/patch_400011027_consumable_test.py
```

该脚本将高版本技能的 `screen` 画布转换到当前客户端 `Map/Effect.img` 的自定义路径中。

## 9. 当前项目与 125 的协议差异

当前项目是 v83 风格，125 代码不能直接复制。

当前攻击相关代码主要位于：

```text
gms-server/src/main/java/org/gms/net/server/channel/handlers/AbstractDealDamageHandler.java
gms-server/src/main/java/org/gms/util/PacketCreator.java
```

当前项目支持：

- `CLOSE_RANGE_ATTACK`
- `RANGED_ATTACK`
- `MAGIC_ATTACK`
- `SKILL_EFFECT`
- `FIELD_EFFECT`
- 服务端 `map.damageMonster`
- `enableActions`

当前项目没有发现与 125 完全对应的：

- `SHOW_SPECIAL_ATTACK`
- `EXPLOSION_ATTACK`
- 125 格式的 `SHOW_SPECIAL_EFFECT`
- 125 格式的攻击包扩展字段
- 125 的多档 `MobPacket.damageMonster` 飘字补偿链

因此不能直接使用 125 的发送码数值或包体结构。发送错误的 opcode 或字段可能造成：

- 客户端无反应；
- 后续封包错位；
- 技能没有效果；
- 角色动作锁死；
- 严重时客户端崩溃或断线。

## 10. 当前项目的 WZ 和脚本道具能力

### 10.1 服务端技能加载

当前 `SkillFactory` 会扫描服务端 Skill WZ 中的技能节点，并将数字节点名解析为技能 ID。

这意味着服务端层面可以维护自定义技能 ID，例如 `1321018`。

但这只证明服务器能读取数值，不证明客户端 EXE 能主动播放该技能。

### 10.2 消耗品 `spec/script`

当前项目会读取：

```text
spec/npc
spec/script
spec/runOnPickup
```

随后将 `script` 当作 NPC/道具脚本名称执行。

因此：

```xml
<string name="script" value="1321018"/>
```

默认含义是运行名为 `1321018` 的脚本，不是直接释放技能 `1321018`。

如果希望把 `script` 当作技能配置，建议定义明确格式，例如：

```text
skill:normal:1321018:5
skill:six:1:1321018:2
```

然后由 `ScriptedItemHandler` 或独立分发器识别并调用统一技能执行器。

不建议把所有纯数字脚本名称自动当成技能 ID，以免和现有脚本命名冲突。

此外，125 分享代码本身对 `2430125` 仍然检查 `script=test`，然后在 Java 中固定调用 `1321018`，并没有完全实现“script 内容直接等于技能 ID”。

## 11. 推荐的当前项目落地架构

建议新增一个独立的 `CustomSkillExecutor`，而不是把逻辑散落在 GM 命令、道具处理器和各攻击 Handler 中。

### 11.1 统一输入

入口可以来自：

```text
!sx <技能ID> <模式>
!six <类别> <技能ID> <模式>
脚本消耗品
NPC 脚本
活动或 Boss 逻辑
```

所有入口最终转换成一个统一请求：

```text
caster
displaySkillId
templateSkillId
skillLevel
attackType
mode
screenEffectPath
soundPath
hitTimeline
```

### 11.2 表现 ID 与伤害模板 ID 分离

建议明确区分：

```text
displaySkillId
  写入客户端攻击和技能表现包。
  必须是客户端对应封包入口能够识别或读取的技能 ID。

templateSkillId
  服务端读取范围、mobCount、attackCount、damage 等数据的技能 ID。
  可以是纯服务端自定义技能。
```

例如：

```text
displaySkillId = 一个 v83 客户端确认可播放的原版技能 ID
templateSkillId = 1321018
```

这样即使客户端不能用 `1321018` 播放人物动作，仍可以使用视觉外壳展示，实际伤害则完全按 `1321018` 配置结算。

### 11.3 推荐执行时序

```text
1. 校验角色、地图、死亡、切图、冷却和技能数据
2. 播放全屏 FIELD_EFFECT（如果存在）
3. 播放声音（如果存在）
4. 尝试发送人物 SKILL_EFFECT 或使用视觉外壳
5. 根据模板技能选择目标并构造攻击上下文
6. 在动画命中时间发送攻击包给施法者本人
7. 将同一攻击包广播给地图其他玩家
8. 在配置的命中时间执行服务端伤害结算
9. 按时间线执行后续段数或持续伤害
10. 最后发送 enableActions
11. 角色死亡、断线或切图时取消剩余调度
```

### 11.4 命中时间线

高版本技能不应统一用固定 300ms 间隔。建议按技能配置实际动画时间：

```text
0ms     全屏动画开始
150ms   人物动作或武器效果
700ms   第一段命中
1000ms  主伤害
1300ms  余波
1800ms  动画结束并最终解锁
```

服务端使用定时任务执行对应阶段，同时每次任务都检查：

- 玩家仍在线；
- 玩家仍存活；
- 玩家仍在原地图；
- 当前释放会话仍有效；
- 目标怪物仍存在。

## 12. 不同技能组成的可行性

| 技能组成 | 可行性 | 推荐实现 |
| --- | --- | --- |
| 全屏图片序列 | 高 | 转入 `Map/Effect.img`，使用 `FIELD_EFFECT mode=3` |
| 全屏音效 | 高 | 使用 `FIELD_EFFECT mode=4` |
| 普通近战攻击 | 高 | 服务端构造 v83 `CLOSE_RANGE_ATTACK` |
| 普通远程攻击 | 高 | 服务端构造 v83 `RANGED_ATTACK` |
| 普通魔法攻击 | 高 | 服务端构造 v83 `MAGIC_ATTACK` |
| 人物周围 `effect` | 中 | 尝试 `SKILL_EFFECT`，失败则使用原版视觉外壳 |
| 普通 `hit` | 中 | 攻击包配合客户端认识的表现 ID |
| 每只怪独立 explosion | 中低 | 当前缺少 125 同型封包，可烘焙进全屏动画或复用原版技能 |
| 屏幕震动、遮罩 | 中 | 使用 v83 已有场景效果；否则合成进全屏画布 |
| 高版本召唤物 | 低 | 需要转换召唤物结构并补当前版本协议 |
| 六转 cutscene | 中 | 转换成 `Map/Effect.img` 全屏动画，不实现真实六转协议 |
| 高版本专用场景对象 | 低 | 需要逐项模拟或修改客户端 |

## 13. 可从 125 复用的部分

可以复用其设计思想：

- 消耗品和 GM 命令作为服务端触发入口；
- 服务端主动选怪和构造攻击上下文；
- 表现技能 ID 与伤害模板技能 ID 分离；
- 主段、持续段和命中时间线编排；
- 攻击包明确发送给施法者本人；
- 再将攻击包广播给其他玩家；
- 伤害由服务端权威结算；
- 角色切图、死亡和断线后取消剩余任务；
- 结尾补发 `enableActions`，避免动作锁死。

不能直接复用：

- 125 的 opcode 数值；
- 125 的攻击包字节结构；
- `SHOW_SPECIAL_ATTACK` 的实现；
- `EXPLOSION_ATTACK` 的实现；
- 125 的 `DamageParse.applyAttack` 调用方式；
- 针对 125 客户端试错形成的大量补飘字和补解锁时序。

## 14. 推荐验证顺序

### 第一步：验证当前 v83 的服务端重放能力

使用一个原版、客户端确认可正常播放的近战技能 ID：

```text
GM 命令触发
→ 服务端给本人发送 SKILL_EFFECT
→ 服务端给本人发送 CLOSE_RANGE_ATTACK
→ 服务端广播给其他玩家
→ 服务端结算
→ enableActions
```

如果原版 ID 重放也没有人物特效，应先修正当前封包构造和发送对象，而不是测试自定义 ID。

### 第二步：只替换为自定义 ID

保持所有其他参数不变，仅把表现 ID 换成 `1321018`。

结果判断：

- 原版 ID 有表现、自定义 ID 无表现：客户端对应入口仍过滤或不理解该 ID。
- 两者都有表现：可以继续使用自定义 ID。
- 两者都没有表现：当前下行包或字段不足，不能据此判断 ID 限制。

### 第三步：验证全屏路径

独立发送：

```text
PacketCreator.showEffect("customSkill/.../full")
```

先确认画布、延迟、origin、分辨率和清理行为，再与伤害逻辑组合。

### 第四步：组合单段技能

只实现：

```text
一个 GM 命令
一个全屏路径
一次攻击包
一次伤害结算
一次最终解锁
```

### 第五步：增加持续段和六转编排

在单段稳定后，再增加：

- 多命中时间点；
- 持续伤害；
- 多种攻击类别；
- 消耗品入口；
- 会话取消和防重复触发。

## 15. 风险和限制

1. **网络表现入口也可能限制技能 ID。** 125 能播放不代表 v83 的同类入口也能播放。
2. **高版本 WZ 结构不能直接复制。** 节点名、画布布局、动作和专用对象可能不兼容。
3. **人物动作与全屏画面必须分开处理。** 全屏路径成功不代表人物技能 ID 成功。
4. **不能复制 125 opcode。** 不同客户端版本的发送码和字段完全可能不同。
5. **攻击包必须给本人。** 只广播给其他玩家会导致施法者缺少表现上下文。
6. **伤害必须由服务端权威结算。** 客户端表现包不能作为可信伤害来源。
7. **必须处理动作解锁。** 服务端主动制造的表现链可能让客户端进入无法攻击、拾取或操作的状态。
8. **持续技能必须支持取消。** 切图、死亡或新一轮释放后不能继续结算旧任务。
9. **脚本道具需防止重复触发。** 客户端重复封包可能造成技能叠放和重复伤害。

## 16. 建议的最终技术路线

当前项目最现实的方案是：

```text
消耗品或 GM 命令
  → CustomSkillExecutor
  → 播放 Map/Effect 全屏路径
  → 播放音效
  → 尝试自定义技能 ID 的 SKILL_EFFECT
  → 失败时使用原版技能视觉外壳
  → 服务端构造 v83 攻击包
  → 攻击包单独发送给施法者本人
  → 攻击包广播给其他玩家
  → 按动画时间线执行权威伤害结算
  → 调度持续段
  → 最终 enableActions
```

一句话总结：

> 125 的本质不是让 EXE 支持新主动技能，而是绕过本地主动施法入口，通过服务端下行表现入口和攻击广播入口驱动 EXE 加载现有 WZ；在当前 v83 项目中，全屏效果应优先转换到 `Map/Effect.img` 按路径播放，人物表现则需要实测 `SKILL_EFFECT`，并准备使用客户端认识的原版技能 ID 作为视觉外壳。

