# 神说五转技能迁移、识别与播放闭环说明

> 最后核对日期：2026-07-20  
> 适用工程：`/Users/lizixian/Documents/mxd/BeiDou-Server`  
> 源客户端：`/Users/lizixian/Documents/mxd/神说`  
> 目标客户端：BeiDou 旧客户端  
> 当前范围：`1112.img` 的 21 个技能和 `1512.img` 的 19 个技能，共 40 个。

## 1. 文档目标和事实边界

这份文档记录的不是“把 IMG 复制过去”的单一操作，而是一条完整的技能闭环：

```text
神说 EMS-key WZ 资源
  -> 解码 Canvas 并用 GMS key 重新编码
  -> BeiDou 客户端 Skill/String IMG
  -> BeiDou 服务端 Skill/String XML
  -> SkillFactory 加载为 Skill/StatEffect
  -> 游戏内 NPC 面板学习并写入键位
  -> BeiDou.exe 的键盘分发门
  -> CUserLocal::DoActiveSkill
  -> 原生技能查找与完整验证
  -> 40-ID 精确白名单
  -> 原生 DoActiveSkill_MeleeAttack 路径
  -> 客户端上行 CLOSE_RANGE_ATTACK
  -> 服务端校验、结算和广播
  -> 其他客户端根据技能 ID 播放攻击表现
```

文档中将明确区分三类结论：

1. **源码可直接确认**：Java、JavaScript 和 Python 实际代码路径。
2. **二进制补丁可直接确认**：EXE 地址、原始字节、跳转目标、寄存器中的技能 ID 和最终 `.vattack` 内容。
3. **必须实机验证**：某个新增技能的每一帧、动作选择、命中时序和职业/武器兼容性。WZ 节点存在不等于旧 EXE 一定会消费该节点。

当前已经能够确认：

- 最终 `BeiDou.exe` 静态验证通过，两个客户端分发门都包含同一组 40-ID 白名单，分层特效 hook 只匹配实际带附加效果的 6 个技能。
- `0x00764256` 的原生验证函数字节保持未修改。
- 两个技能书在客户端和服务端都可解析，40 个目标节点都只保留 `level/1` 且 `masterLevel=1`。
- 迁移后 40 个节点都有 `hit`；服务端在已删除 `skillType=3` 的前提下，会按实际 `effect/hit/ball/action` 结构加载它们。
- 用户实机已确认最终路径能够释放技能；这不等于 40 个技能的每个动作和每个职业/武器组合都已逐一验收，完整验收仍要按本文测试矩阵执行。
- 2026-07-20 用户实机确认 `11121056` 的主 `effect` 与 `effect0/effect1/effect2` 兼容层能够在同一次施放中同时播放。

## 2. 当前最终架构

### 2.1 四层职责

| 层 | 实际责任 | 缺失后的典型现象 |
| --- | --- | --- |
| 资源层 | 提供图标、角色动作名、`effect`、`hit`、`ball`、范围、段数、伤害、MP 消耗等 | 空图标、无特效、服务端空指针或参数异常 |
| 服务端技能层 | 把 XML 加载成 `Skill`/`StatEffect`，保存学习等级，校验并结算攻击 | 面板显示“技能数据不可用”，或攻击包到达后不能结算 |
| 面板/键位层 | 用原生 NPC UI 学习技能，发 `UPDATE_SKILLS`，在现有 8 个快捷栏按键中找空位 | 学不了、看不到已学习状态、第二个技能覆盖第一个 |
| 客户端 EXE 层 | 让旧客户端将指定新 ID 当作通用主动技能，并进入原生近战施放路径 | 技能可学、可放键盘，但按下后毫无反应 |

### 2.2 不再使用 DLL 面板

最终方案是游戏内 NPC 对话面板，不是独立 Win32 窗口。

- 游戏内入口：`gms-server/scripts-zh-CN/BeiDouSpecial/技能中心.js`
- 游戏内面板：`gms-server/scripts-zh-CN/BeiDouSpecial/五转技能面板.js`
- 打开方式：技能中心的选项 7 调用 `cm.openNpc(9900001, "五转技能面板")`。
- 最终 EXE 不包含 `BeiDouVSkill` 或 `beidou_vskill_trace` 字符串，补丁验证只识别 `.vattack` PE 节。
- `clien/BeiDouVSkill.dll` 和 `patch_vskill_client.py` 是历史诊断/实验产物，不属于最终运行依赖；失效的 `tool/client-vskill/` 入口已经清理。

## 3. 文件清单与职责

### 3.1 源文件

```text
/Users/lizixian/Documents/mxd/神说/Data/Skill/1112.img
/Users/lizixian/Documents/mxd/神说/Data/Skill/1512.img
```

这两个 IMG 按 EMS key 读取。它们提供资源和技能参数，不提供可直接复制到 BeiDou 的 EXE 机器码逻辑。

### 3.2 客户端运行文件

```text
clien/BeiDou.exe
clien/Data/Skill/1112.img
clien/Data/Skill/1512.img
clien/Data/String/Skill.img
```

- `BeiDou.exe`：包含 `.vattack` 执行节、两个主动技能分发钩子和一个分层特效钩子。
- `Skill/1112.img`、`Skill/1512.img`：技能图标、动作、人物特效、命中特效和等级参数。
- `String/Skill.img`：客户端技能名称和描述，面板中 `#q<skillId>#` 依赖它。

### 3.3 服务端运行文件

```text
gms-server/BeiDou.jar
gms-server/wz/Skill.wz/1112.img.xml
gms-server/wz/Skill.wz/1512.img.xml
gms-server/wz/String.wz/Skill.img.xml
gms-server/scripts-zh-CN/BeiDouSpecial/技能中心.js
gms-server/scripts-zh-CN/BeiDouSpecial/五转技能面板.js
gms-server/scripts-zh-CN/BeiDouSpecial/快速转职.js       # 仅当需要转职时自动学习时必须同步
```

`BeiDou.jar` 中与本功能直接相关的源码：

```text
gms-server/src/main/java/org/gms/client/Job.java
gms-server/src/main/java/org/gms/client/SkillFactory.java
gms-server/src/main/java/org/gms/client/Character.java
gms-server/src/main/java/org/gms/scripting/AbstractPlayerInteraction.java
gms-server/src/main/java/org/gms/util/PacketCreator.java
gms-server/src/main/java/org/gms/net/server/channel/handlers/KeymapChangeHandler.java
gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java
gms-server/src/main/java/org/gms/net/server/channel/handlers/AbstractDealDamageHandler.java
gms-server/src/main/java/org/gms/client/keybind/QuickslotBinding.java
```

### 3.4 生成脚本

```text
tool/scripts/migration/migrate_shenshuo_vskills.py
tool/scripts/patch-client/patch_vskill_attacks.py
```

- 迁移脚本负责 WZ 区域密钥转码、结构归一化、服务端 XML、String 和图标导出。
- EXE 脚本负责对当前 BeiDou PE32 布局进行字节级验证，添加 `.vattack` 节，写入两个 40-ID 精确分发白名单和一个 6-ID 分层特效表。

## 4. 当前 40 个技能和 Skill Book 规则

### 4.1 `1112.img`：21 个

```text
11121054  11121055  11121056  11121057  11121058  11121059
11121060  11121061  11121062  11121064  11121065  11121066
11121068  11121069  11121070  11121071  11121072  11121073
11121074  11121075  11121076
```

神说源数据中：

- 21 个技能都有 `skillType=3`。
- 有些技能只有 1 级，有些技能有 1..5 级。
- 当前迁移规则是选每个技能的最高数字等级，写为目标 `level/1`。

### 4.2 `1512.img`：19 个

```text
15120000  15121001  15121002  15121003  15121004  15121005
15121006  15121007  15121008  15121009  15121010  15121011
15121012  15121013  15121014  15121015  15121016  15121017
15121018
```

神说源数据中：

- 19 个技能都有 `skillType=3`。
- 19 个技能都有 1..30 级。
- 当前迁移规则明确选源 `level/1`，再写为目标 `level/1`；它不使用 30 级数值。
- `15121009/action/*` 中的 `brandishNew` 被改成 BeiDou 旧角色资源存在的 `brandish1`。

### 4.3 三张必须完全一致的清单

每次增删目标技能，至少要同步：

1. `migrate_shenshuo_vskills.py` 的 `SKILL_IDS`：决定 String 同步和名称生成清单。
2. `patch_vskill_attacks.py` 的 `VSKILL_IDS`：决定 EXE 真正识别并释放的白名单。
3. `五转技能面板.js` 的 `skillBooks[book].skills`：决定玩家能看见和学习的清单。

`快速转职.js` 的 1112/1512 段落也包含当前 40 个 ID。如果需要快速转职后自动学习，这是第四张必须同步的清单；如果只通过五转面板学习，它不影响 EXE 识别。

`migrate_book()` 会复制源 IMG `skill` 下的所有节点，而不是只复制 `SKILL_IDS`。因此如果源 IMG 新增了节点却忘了上述三张清单，就会出现“资源已迁入，但面板看不见或 EXE 不响应”。

## 5. WZ 资源迁移原理和代码逻辑

### 5.1 为什么不能直接复制 IMG

当前代码中明确定义：

```python
SOURCE_KEY = WzKey.for_region("EMS")
TARGET_KEY = WzKey.for_region("GMS")
```

WZ Canvas 的图像 payload 受区域 key 影响。直接将 EMS-key IMG 复制到按 GMS key 读取的 BeiDou 客户端，并不会自动变成 GMS 资源；常见后果是 Canvas 无法解码、游戏数据不正确、空白特效或客户端崩溃。

`clone_property()` 对 Canvas 执行的真实路径是：

```text
decode_canvas(prop, region="EMS")
  -> RGBA 图像
  -> encode_canvas_payload(..., key=TARGET_KEY, listwz=False)
  -> 新的 GMS-key Canvas payload
```

它不只处理图像，还递归保留：

- `WzSubProperty`
- `WzVectorProperty`
- `WzStringProperty`
- `WzIntProperty` / `Short` / `Long`
- `Float` / `Double`
- `Null`
- `UOL`
- `Convex`
- `Sound`
- Canvas 下的子节点，例如 `origin`、`delay`、`z`

遇到未支持的 WZ property 类型时脚本会抛错，不会静默丢弃。

### 5.2 目标 IMG 的重建方式

`migrate_book(book, dry_run)` 按以下顺序执行：

1. 用 EMS key 解析神说 `book.img`。
2. 用 GMS key 解析 BeiDou 已有的同名 IMG，用它作为目标 writer 容器。
3. 清空目标根节点子节点。
4. 递归克隆源根节点的全部子节点，Canvas 逐张转为 GMS key。
5. 取得目标 `skill` 根，遍历每个技能节点执行 `normalize_skill()`。
6. 将目标编码为客户端二进制 IMG。
7. 用同一棵目标属性树导出服务端 XML，保证两端数值结构同源。
8. 将每个技能的 `icon` Canvas 导出到 `clien/VSkill/icons/<skillId>.bmp`，用于调试/人工检查；最终 NPC UI 直接使用 `#s<skillId>#`，不依赖这些 BMP。

写入使用临时文件后 `replace()` 的原子替换；首次真实写入前，原文件复制到：

```text
tool/backups/shenshuo-vskills/
```

### 5.3 `normalize_skill()` 的实际修改

对每个技能：

1. 删除源 `skillType`。
2. 1112 选取最高数字等级；1512 固定选取等级 1。
3. 创建新的 `level/1`，递归复制被选等级的全部数值、字符串、向量、UOL 和子属性。
4. 将 `masterLevel` 设为 1。
5. 对 1512 执行 `brandishNew -> brandish1`。

删除 `skillType=3` 是针对当前这 40 个攻击技能的兼容处理，不是通用规则。当前 `SkillFactory` 在 `skillType` 存在时优先使用它分类；删除后才会根据 `effect/hit/ball/action` 推导。新增 BUFF、召唤、投射、蓄力或其他特殊技能时，不能机械地删除 `skillType`并强制走近战。

### 5.4 String 同步

`migrate_strings()` 会同时修改：

```text
clien/Data/String/Skill.img
gms-server/wz/String.wz/Skill.img.xml
```

当前名称不是从神说 String 原样复制，而是按顺序生成：

```text
终极魂骑士 01 (11121054)
……
终极奇袭者 01 (15120000)
```

描述固定为“通过游戏内五转技能面板学习，学习后直接达到最高等级。”。如需要正式名称/描述，要修改 `make_string_node()` 或增加可审计的名称映射，然后重新迁移两端 String。

### 5.5 当前迁移脚本的实际只读验证结果

```text
[dry-run] 1112: 21 skills, 591 canvases, 21 icons,
          0 action aliases, 6 effect compatibility slots (69 canvases),
          21 skillType removed,
          client 76590228 bytes, server 187587 bytes
[dry-run] 1512: 19 skills, 564 canvases, 19 icons,
          1 action alias, 2 effect compatibility slots (16 canvases),
          19 skillType removed,
          client 28113446 bytes, server 150319 bytes
[dry-run] String/Skill.img: 40 client entries, 40 server entries updated,
          client 1077730 bytes, server 1172099 bytes
```

## 6. 服务端如何识别、学习和保存技能

### 6.1 `SkillFactory.loadAllSkills()` 的加载逻辑

服务端启动时，`SkillFactory.loadAllSkills()`：

1. 获取 `WZFiles.SKILL` 的根目录。
2. 遍历根下文件，只处理文件名长度 `<= 8` 的条目。`1112.img`、`1512.img` 满足条件。
3. 在每个 IMG/XML 中找名为 `skill` 的节点。
4. 遍历 `skill` 的子节点，用 `Integer.parseInt(data2.getName())` 把节点名解析成技能 ID。
5. 调用 `loadFromData(skillId, data2)` 生成 `Skill`。
6. 以 `Map<Integer, Skill>` 的键保存，`SkillFactory.getSkill(id)` 就是直接 `skills.get(id)`。

因此“服务端识别”的最小事实条件是：

```text
对应 XML 被服务端的 WZ provider 加载
  + XML 内存在 skill/<decimal skillId>
  + 该节点有可遍历的 level
  + level 参数能被 StatEffect.loadSkillEffectFromData 解析
```

`Job.java` 当前已有：

```text
DAWNWARRIOR4(1112)
THUNDERBREAKER4(1512)
```

这使 1112/1512 作为职业枚举是完整的。但 `SkillFactory` 加载技能节点并不依赖玩家当前职业。

### 6.2 当前 40 个技能的主动/攻击分类

`loadFromData()` 的实际分类顺序：

```text
action = 存在 action 或 prepare/action

如果 skillType 存在：
    skillType == 2 -> isBuff = true
否则：
    isBuff = effect 存在 && hit 不存在 && ball 不存在
    action/0 == alert2 也会标为 buff
    然后再应用原有的特定 ID switch 例外
```

当前迁移后的 40 个节点都有 `hit`，且 `skillType` 已删除，所以不会命中“只有 effect，没有 hit/ball”的 BUFF 推导条件。每个 `level/1` 会被加载成 `StatEffect`。

注意：服务端将它加载为可攻击技能，仍不能代替客户端 EXE 的主动施放分发。

### 6.3 面板学习调用链

`五转技能面板.js/learnSkill()` 先执行：

```javascript
var skill = SkillFactory.getSkill(skillId);
if (skill === null || skill.getMaxLevel() < 1) {
    // 拒绝学习
}
```

通过后调用：

```javascript
cm.teachSkill(skillId, maxLevel, maxLevel, -1);
```

`AbstractPlayerInteraction.teachSkill()` 内部：

1. 再次通过 `SkillFactory.getSkill(skillid)` 取 `Skill`。
2. 如果角色已有该技能且未强制覆盖，保留当前等级/上限/过期时间与新值的较大者。
3. 调用 `Character.changeSkillLevel()`。

`Character` 中的角色技能容器是：

```java
Map<Skill, SkillEntry> skills = new ConcurrentHashMap<>();
```

不同技能 ID 是不同的 `Skill` key，学第二个技能不会从这个 Map 中删除第一个。`changeSkillLevel()` 将 `SkillEntry(level, masterLevel, expiration)` 写入 Map，并发送 `PacketCreator.updateSkill()`。

`updateSkill()` 实际写入的包结构为：

```text
SendOpcode.UPDATE_SKILLS
byte  1
short 1                    # 本次更新 1 个技能
int   skillId
int   level
int   masterLevel
      expiration
byte  4
```

角色保存时，`skills` Map 的每个条目写入数据库 `skills(characterid, skillid, skilllevel, masterlevel, expiration)`，因此多个技能可持久化共存。

### 6.4 当前不判断职业

当前面板打开后先选“终极魂骑士”或“终极奇袭者”，没有读取玩家职业并拒绝学习的逻辑。

`KeymapChangeHandler` 原有的技能职业树/绑定限制代码也已整段注释，当前有效逻辑是直接：

```java
c.getPlayer().changeKeybinding(key, new KeyBinding(type, action));
```

EXE 补丁只比对精确技能 ID，也没有职业条件。所以当前闭环是“不限职业，只要通过面板学会并绑键就能尝试释放”。

## 7. 客户端如何识别技能：精确二进制路径

### 7.1 先明确：“能显示”不等于“能施放”

客户端同时有几个不同问题：

```text
能从 String/Skill 找到名称       -> 只证明文字资源存在
能从 Skill IMG 找到图标        -> 只证明资源节点存在
服务端发 UPDATE_SKILLS 后有等级 -> 只证明角色技能状态已更新
能放到键盘                         -> 只证明 keymap 中写了 type=1/action=skillId
按键进入 DoActiveSkill                -> 这时才进入本地主动技能逻辑
通过技能查找和完整验证           -> 只是已建立有效施放上下文
进入正确攻击类型并上行攻击包     -> 才是客户端真正“认识了这个主动技能”
```

这正是早期版本出现“已学习、已放键盘，点击却无反应”的原因。

### 7.2 最终 `.vattack` PE 节

`patch_vskill_attacks.py` 向 PE32 EXE 增加：

```text
节名                 .vattack
虚拟大小/原始大小  0x1000
属性                 0x60000020 = code | execute | read
当前装载 VA       0x00E94000
实际代码长度       1277 bytes
```

内部有三块跳板：

```text
0x00E94000  post-validation dispatch allowlist，491 bytes
0x00E941EB  keyboard dispatch allowlist，495 bytes
0x00E943DA  layered effect dispatch，291 bytes
```

每个白名单条目都是精确等值比较，不是范围、前缀或职业判断。未命中的任何技能都重放被覆盖的原指令并返回原控制流。

### 7.3 第一道门：键盘主动技能分发

补丁点：

```text
VA                  0x0094F89E
原始 10 字节         8B 4E 01 8B C1 BF 10 27 00 00
原指令语义          mov ecx,[esi+1]
                    mov eax,ecx
                    mov edi,10000
原路径返回          0x0094F8A8
通用主动技能目标      0x0094F9E9
当前钩子字节        E9 48 49 54 00 90 90 90 90 90
```

实际跳板逻辑：

```asm
mov ecx, [esi+1]                 ; 原逻辑从当前键位记录取 action/技能 ID

cmp ecx, 11121054
je  0x0094F9E9
cmp ecx, 11121055
je  0x0094F9E9
...                              ; 同样比较全部 40 个 ID
cmp ecx, 15121018
je  0x0094F9E9

mov eax, ecx                     ; 未命中：重放原指令
mov edi, 10000
jmp 0x0094F8A8
```

这一道门解决“旧键盘分发器不会把这些大 ID 送到通用主动技能路径”的问题。

诊断钩子源码记录的下一个直接调用为：

```text
0x0094FA28 -> CUserLocal::DoActiveSkill @ 0x00966F7A
```

最终版不需要加载诊断 DLL；这些地址是之前用于定位真实调用链的证据，当前有效修改只在 `.vattack`。

### 7.4 `DoActiveSkill` 内部：数据查找和完整验证

已定位的原生直接调用：

```text
0x009675D5 -> 技能数据/等级查找函数 @ 0x007616F6
0x00967759 -> 技能完整验证函数     @ 0x00764256
```

历史诊断 wrapper 传入 `skillId`，记录了查找返回值和 `skillEntry` 指针，也记录了验证函数的真实返回值。这条链证明客户端会用原技能 ID 进入自身的 Skill 数据/等级查找；补丁不会将它偷换成另一个旧技能 ID。

`0x00764256` 是完整的验证和状态初始化函数，不是一个可以随便 `return 1` 的“技能类型分类器”。当前补丁脚本明确校验其入口 `0x0076425C` 开始的字节仍为：

```text
53 8B 5D 14 8B C3
```

任何不匹配都拒绝打补丁或拒绝将当前 EXE 认定为正确版本。

### 7.5 第二道门：完整验证后的攻击类型分发

正确补丁点：

```text
VA                  0x009678F9
原始 6 字节          81 FE 07 04 00 00
原指令语义          cmp esi,0x407
原路径返回          0x009678FF
原生近战分支入口      0x009690AE
当前钩子字节        E9 02 C7 52 00 90
```

在这个点，`esi` 持有当前技能 ID。实际跳板逻辑：

```asm
cmp esi, 11121054
je  0x009690AE
cmp esi, 11121055
je  0x009690AE
...                              ; 同样比较全部 40 个 ID
cmp esi, 15121018
je  0x009690AE

cmp esi, 0x407                   ; 未命中：重放原指令
jmp 0x009678FF
```

此位置在技能数据查找和原生完整验证之后，在旧 EXE 后续的技能 ID 二叉分发表拒绝新 ID 之前。因此它同时满足：

- 不跳过数据查找。
- 不跳过等级、冷却、状态等原生验证/初始化。
- 只改变白名单 ID 的攻击类型归宿。
- 对其他旧技能重放原比较并回到原路径。

### 7.6 原生近战施放和本地播放

白名单命中后跳到：

```text
0x009690AE  原生近战分支入口
0x009690B6  调用点
0x00969465  原生近战攻击函数
```

历史诊断 wrapper 对 `0x009690B6 -> 0x00969465` 的调用记录了原生 `skillEntry` 和 `skillLevel` 指针，且不替换参数和返回值。最终补丁不实现自定义渲染器、不伪造技能 ID，而是让原生近战函数继续消费真实的 1112/1512 技能数据。

在这一阶段，客户端 Skill IMG 提供：

- `level/1`：`damage`、`attackCount`、`mobCount`、`mpCon`、`lt/rb` 等数值。
- `action`：资源中显式存在时，提供可用的角色动作名。
- `effect`：旧客户端原生通用路径直接播放的主视觉帧资源。
- `effect0/effect1/effect2/effect3`：保留的神说顶层附加视觉资源，并镜像为 `effect/90..93` 供旧客户端选择。
- `hit`：命中目标时可用的视觉帧资源。
- `ball`：只在部分源技能中存在的投射物相关资源。

需要严格区分：主 `effect` 仍由原生通用路径选择和播放；附加节点通过下一节记录的兼容镜像与视觉 hook 同时启动。补丁没有修改每张 Canvas 的 origin、delay、z 或朝向，所以新增技能仍必须实机检查位置、方向、透明度、前摇和帧延时，不能只根据静态结构宣称观感完整。

### 7.7 `effect0/effect1/effect2` 同时播放兼容

神说源节点仍原样保留，同时迁移脚本只对非空节点增加以下镜像：

```text
effect0 -> effect/90
effect1 -> effect/91
effect2 -> effect/92
effect3 -> effect/93
```

当前实际产生 8 个兼容槽、85 张镜像 Canvas：

```text
11121056  effect/90, effect/91, effect/92
11121058  effect/90
11121059  effect/90
11121064  effect/90
15121009  effect/90
15121015  effect/90
```

客户端视觉 hook：

```text
补丁点              0x009358EE
原始字节            8B 45 C8 3B C7
当前钩子字节        E9 E7 EA 55 00
跳板                0x00E943DA
原路径返回          0x009358F3
原生 effect 选择器  0x00932D40
```

`0x009358EE` 位于主 `effect` 已进入原生播放队列之后。跳板从 `[ebp+8]` 取得真实技能 ID，只匹配上面 6 个技能；保存寄存器和原参数后，按技能自己的位掩码调用 `0x00932D40` 选择 `effect/90..93`，并复用原生角色 effect layer 将附加动画立即入队。主效果和附加效果因此从同一次施放中并行运行，各自 Canvas 的 `delay` 继续独立生效。

不能无条件尝试四个索引。`0x00932D40` 在索引不存在时会回退到主 `effect`，会造成主特效重复播放。当前表明确规定：`11121056` 只尝试 90/91/92，其余 5 个技能只尝试 90；不存在的槽位不会调用选择器。

这条视觉兼容不改变技能 ID、攻击包、服务端伤害时序、职业判断或 `0x00764256` 原生验证，也不加载 `BeiDouVSkill.dll`。

实机验收记录：2026-07-20 使用面板中的“终极魂骑士 03”即 `11121056` 测试，确认主 `effect` 和三组附加效果能够同时显示。该结果证明四层播放闭环已打通；其余 5 个只有 `effect0` 的技能仍应逐个检查方向、位置和帧延时。

### 7.8 从客户端攻击到服务端结算

原生近战路径组织并上行近战攻击包。服务端的实际映射是：

```text
RecvOpcode.CLOSE_RANGE_ATTACK = 0x2C
PacketProcessor -> new CloseRangeDamageHandler()
```

`AbstractDealDamageHandler.parseDamage()` 从包中读取：

```text
numAttackedAndDamage
skillId
人物已学习的 skillLevel
display
direction
stance
speed
目标 OID 和每段伤害
```

它对 `skillId > 0` 执行：

```java
ret.skilllevel = chr.getSkillLevel(ret.skill);
Skill skill = SkillFactory.getSkill(ret.skill);
StatEffect effect = skill.getEffect(ret.skilllevel);
```

`CloseRangeDamageHandler` 再：

1. 将攻击体广播为 `SendOpcode.CLOSE_RANGE_ATTACK = 0xBA`。
2. 根据服务端 `StatEffect` 取 `attackCount`、冷却、MP 消耗、`mobCount` 等。
3. 调用 `applyAttack()` 进行权威校验和怪物伤害结算。

广播调用是：

```java
broadcastMessage(chr, PacketCreator.closeRangeAttack(...), false, true);
```

`MapleMap.broadcastMessage()` 中 `repeatToSource=false` 会排除源角色，`ranged=true` 只向附近角色发送。所以播放闭环是：

```text
施放者本人：
  按键 -> 本地 DoActiveSkill -> 本地原生近战动作/资源 -> 上行 0x2C

附近其他玩家：
  服务端收 0x2C -> 生成 0xBA -> 其他客户端按包中的真实 skillId/level/display 播放

怪物实际扣血：
  服务端 applyAttack() 权威结算
```

这也是为什么只有客户端特效、或只有服务端扣血，都不能算完成技能迁移。

### 7.9 神说与 BeiDou 的识别差异

从神说实际 WZ 能直接确认的是：1112/1512 节点、`skillType=3`、多级参数、动作和数百张 Canvas 都存在。

不能从这些 WZ 节点推出“神说 EXE 的机器码可以原样复制到 BeiDou”。神说客户端是另一个版本，它的职业/技能路径已原生支持这些 ID；BeiDou 旧 EXE 的真实控制流不同。

本迁移只复制“技能的数据和行为语义”，然后针对 BeiDou 自身的键盘分发、技能查找、完整验证和攻击分发位置实现补丁。这是当前不去“猜神说怎么做”、而以两套实际代码/二进制为准的边界。

## 8. 游戏内面板与多技能键位逻辑

### 8.1 面板状态机

`五转技能面板.js` 使用原生 NPC 对话 API：

- `books`：显示 1112/1512 两类。
- `skills`：每页 6 个技能，用 `#sID#` 显示图标，`#qID#` 显示名称。
- `resume`：学习结果对话关闭后返回当前技能页。
- `isSkillLearned()`：通过玩家当前等级是否达到 `skill.getMaxLevel()` 标记 `[已学习]`。
- `containsSkill()`：拒绝不在当前 `skillBooks` 列表中的选择值，防止通过伪造 NPC selection 学习任意 ID。

老客户端原生技能窗口不一定显示这些大 ID，所以当前流程不依赖原生技能窗口拖拽，而是学习后自动放入空闲快捷栏按键。

### 8.2 快捷栏的实际结构

`QuickslotBinding.QUICKSLOT_SIZE = 8`。默认按键顺序是：

```text
42  = Shift
82  = 小键盘0
71  = 小键盘7
73  = 小键盘9
29  = Ctrl
83  = 小键盘.
79  = 小键盘1
81  = 小键盘3
```

角色 `keymap` 是按键码到 `KeyBinding(type, action)` 的 Map。技能绑定使用：

```text
type   = 1
action = skillId
```

“快捷栏”只是 8 个按键码的排列；每个格子当前显示什么，取决于对应按键码在 `keymap` 中的 binding。

### 8.3 `addSkillToFirstFreeQuickslot()`

当前最终方法的真实逻辑：

1. 遍历整个 `keymap`，如果已有 `type=1 && action=skillId`，直接返回旧按键，不重复绑定。
2. 读当前角色的 `quickSlotKeyMapped`；为空时使用上述默认 8 键。
3. 按快捷栏顺序找第一个 `!keymap.containsKey(keyCode)` 的按键。
4. 写入 `new KeyBinding(1, skillId)`。
5. 发送完整键盘图和快捷栏更新。
6. 返回按键码。
7. 8 键都已有内容时返回 `-1`，不覆盖任何旧 binding。

面板是先学习、再尝试绑定。因此 8 格全满时：

- 技能已经学会。
- 面板会提示先腾位。
- 玩家腾出一个快捷栏按键后，再点一次同一技能，方法会完成绑定而不重置技能。

## 9. 从神说新增一个同类型技能

本节只适用于能够走当前“通用主动 + 原生近战”路径的技能。如果是 BUFF、魔法、远程、召唤、持续蓄力、组合键或高版专属机制，先看第 10 节。

### 步骤 1：审计源技能，不先写白名单

必须从源 IMG 实际确认：

- 技能 ID 节点确实存在。
- 有可用 `level` 子节点。
- 要选源的哪一级，不要默认“最高级一定对”。
- 是否有 `hit`、`ball`、`effect`、`action`。
- `action` 名是否存在于 BeiDou 旧 `Character` 资源。
- 参数是否包含旧服务端 `StatEffect` 不支持的高版字段。

先运行当前只读迁移验证，确保现有基线没有错：

```bash
rtk python3 tool/scripts/migration/migrate_shenshuo_vskills.py --dry-run
```

### 步骤 2：把 ID 加入三张核心清单

同时修改：

```text
tool/scripts/migration/migrate_shenshuo_vskills.py        SKILL_IDS
tool/scripts/patch-client/patch_vskill_attacks.py         VSKILL_IDS
gms-server/scripts-zh-CN/BeiDouSpecial/五转技能面板.js  skillBooks
```

如需转职自动学习，再修改：

```text
gms-server/scripts-zh-CN/BeiDouSpecial/快速转职.js
```

清单中使用完整十进制 ID，不用范围判断代替。

### 步骤 3：如有需要，增加书级兼容配置

`BOOKS` 当前的书级配置是：

```python
"1112": {"source_level": "max", "action_aliases": {}},
"1512": {"source_level": "1", "action_aliases": {"brandishNew": "brandish1"}},
```

新 action 名不能在旧端使用时，只在找到实际可兼容动作名并实机测试后加 alias。不要把所有技能统一改成 `brandish1`。

### 步骤 4：先 dry-run，再写入 WZ

```bash
rtk python3 tool/scripts/migration/migrate_shenshuo_vskills.py --dry-run
rtk python3 tool/scripts/migration/migrate_shenshuo_vskills.py
```

检查输出中：

- 技能数是否和源 IMG 实际节点数一致。
- Canvas 是否成功全量转码。
- alias 数量是否和配置一致。
- 删除 `skillType` 的数量是否符合实际源数据。
- 客户端 IMG 和服务端 XML 大小是否异常突变。

### 步骤 5：从已验证的无 `.vattack` 基底重建 EXE

补丁脚本是内容可验证的，但不会在已有 `.vattack` 的 EXE 上就地改写新清单。如果修改 `VSKILL_IDS` 后直接对当前最终 EXE 执行，旧 `.vattack` 内容与新脚本不一致，脚本会拒绝，这是预期保护。

当前已静态确认的重建基底是：

```text
clien/BeiDou.exe.bak-vskill-attacks
SHA-256: 1198fa57ca5a7c489bae43ec13c69681d9cabe0f96762f3dc0357facf2e7d4df
.vattack: 不存在
0x0094F89E: 8B 4E 01 8B C1 BF 10 27 00 00
0x009678F9: 81 FE 07 04 00 00
0x0076425C: 53 8B 5D 14 8B C3
```

先额外备份当前可用 EXE，再用该基底重建：

```bash
rtk cp clien/BeiDou.exe clien/BeiDou.exe.before-vskill-rebuild
rtk cp clien/BeiDou.exe.bak-vskill-attacks clien/BeiDou.exe
rtk python3 tool/scripts/patch-client/patch_vskill_attacks.py --dry-run
rtk python3 tool/scripts/patch-client/patch_vskill_attacks.py
rtk python3 tool/scripts/patch-client/patch_vskill_attacks.py --dry-run
```

最后一次 dry-run 应输出“already recognizes N imported skills at both client dispatch gates”。

不要随意选另一个 `.bak-*` 作基底。当前其他多个历史备份已包含不同阶段的 `.vattack` 或键盘钩子，不等价于干净基底。

### 步骤 6：如果 Java 逻辑变更，用 Java 21 构建 JAR

当前 `gms-server/pom.xml` 的 `maven.compiler.source/target` 都是 21，产物名是 `BeiDou.jar`。

```bash
rtk env JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home mvn -pl gms-server -DskipTests package
rtk cp gms-server/target/BeiDou.jar gms-server/BeiDou.jar
```

用 Java 17 构建会在 javac 阶段报：

```text
无效的目标发行版：21
```

只增加 WZ 节点和 JS 清单，且现有 JAR 已包含 `addSkillToFirstFreeQuickslot()` 时，代码逻辑未变；新部署仍要保证线上 JAR 确实是包含该方法的最终版本。

### 步骤 7：复制部署文件

详见第 12 节。客户端、服务端 WZ、服务端 JAR 和面板 JS 要按同一次版本成套部署。

### 步骤 8：重启后按闭环测试

服务端 `SkillFactory` 是启动加载；只替换 XML 不重启，内存中的 `skills` Map 不会自动变成新版。客户端 IMG/EXE 替换后也要完全退出重开。

## 10. 新 Skill Book 或非近战技能的处理

### 10.1 新增另一个 Skill Book

如果不再是 1112/1512，至少需要：

1. 在神说源目录放入对应 `<book>.img`。
2. 确认其实际区域 key，不要因为来自同一项目就默认一定是 EMS。
3. 确保 BeiDou `clien/Data/Skill/<book>.img` 存在可作 writer 容器，或扩展脚本的创建方式。
4. 在 `BOOKS` 增加明确的 `source_level` 和 `action_aliases`。
5. 在 `SKILL_IDS`、`VSKILL_IDS`、面板 `skillBooks` 增加同一组 ID。
6. 更新 `make_string_node()` 的分类名称，不要让新书被错误显示为终极奇袭者。
7. 扩展面板书类选择的 selection 允许值。
8. 如果项目其他流程需要该职业枚举，再在 `Job.java` 和转职逻辑中补充；`SkillFactory` 本身不因缺少 Job 枚举而停止按节点 ID 加载。

### 10.2 非近战技能不能直接进当前白名单

当前第二道门对所有白名单 ID 都跳到 `0x009690AE` 近战分支。所以在新 ID 入表前要确认它确实可以按近战上下文工作。

以下类型必须单独逆向和实现正确目标路径：

- 远程攻击：要组织远程攻击包、弹丸/投射物上下文。
- 魔法攻击：要走魔法攻击包和对应魔法计算/播放路径。
- BUFF：不应发近战伤害包，还需服务端 buff stat 映射。
- 召唤物：需要创建、持久化和广播召唤对象。
- 蓄力/持续键：需要 keyState/repeat 与蓄力值的特殊上下文。
- 高版专属机制：如果旧 EXE 没有对应状态对象/封包，WZ 资源不会自动创造机制。

这些类型要重新找到 BeiDou 自身合适的攻击/技能分支入口，并对应服务端 `RangedAttackHandler`、`MagicDamageHandler` 或 buff/summon handler，不能只往 `VSKILL_IDS` 追加 ID。

## 11. 构建、静态验证和实机验收

### 11.1 静态验证命令

WZ 只读重建验证：

```bash
rtk python3 tool/scripts/migration/migrate_shenshuo_vskills.py --dry-run
```

EXE 内容验证：

```bash
rtk python3 tool/scripts/patch-client/patch_vskill_attacks.py --dry-run
```

终端应识别到：

```text
BeiDou.exe already recognizes 40 imported skills at both client dispatch gates
and the layered-effect hook through .vattack at VA 0xE94000.
```

检查关键哈希：

```bash
rtk shasum -a 256 clien/BeiDou.exe clien/Data/Skill/1112.img clien/Data/Skill/1512.img
rtk shasum -a 256 tool/scripts/patch-client/patch_vskill_attacks.py
rtk shasum -a 256 gms-server/BeiDou.jar
rtk shasum -a 256 gms-server/scripts-zh-CN/BeiDouSpecial/五转技能面板.js
```

文档/补丁集完成后检查 Markdown 和 Git 空白错误：

```bash
rtk git diff --check -- README_神说五转技能迁移.md
```

### 11.2 服务端构建

```bash
rtk env JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home mvn -pl gms-server -DskipTests package
```

产物：

```text
gms-server/target/BeiDou.jar
```

### 11.3 游戏内完整测试矩阵

不要只测“能点一次”。至少要执行：

| 测试项 | 预期结果 | 定位的层 |
| --- | --- | --- |
| 从技能中心打开五转面板 | 游戏鼠标可点，使用原生 NPC UI | 面板层 |
| 切换 1112/1512、上下页 | 页码和选中正常 | JS 状态机 |
| 图标/名称 | 40 个都不是空白/未知 | 客户端 Skill/String |
| 学习第 1 个技能 | 变为 `[已学习]`，进第 1 个空闲快捷键 | 服务端 Skill/键位 |
| 连续学第 2、3、4 个 | 旧技能不消失，每个占不同空键 | `Character.keymap` |
| 重复点已学技能 | 保留原等级和原键位 | 幂等性 |
| 8 格全占满后学习 | 技能学会，提示腾位，不覆盖旧技能 | 满栏分支 |
| 腾位后重选刚才技能 | 绑定到空键 | 恢复路径 |
| 退出角色并重登 | 已学技能和多键位仍存在 | DB 持久化 |
| 按下每个技能 | 客户端不黑屏、不卡死，有动作/特效/命中 | EXE + WZ |
| 终极魂骑士 03 / `11121056` 四层特效 | 主 `effect` 与 `effect0/effect1/effect2` 同时播放；2026-07-20 已实机通过 | 分层特效 hook + WZ 镜像 |
| 攻击怪物 | 服务端收到近战包，怪物权威扣血 | 攻击闭环 |
| 第二个玩家在附近观看 | 能看到广播的技能 ID/攻击表现 | `0xBA` 下行播放 |
| 用非 1112/1512 职业测试 | 当前版本不因职业条件被面板拒绝 | 无职业限制 |
| 改变武器类型后测试 | 记录每个技能实际可用性，不把单武器成功当全部成功 | 原生近战兼容 |

每个新增 ID 至少要记录：学习结果、绑定键、人物动作、人物特效、命中特效、目标数、段数、MP、冷却、服务端收包和另一玩家的观察结果。

## 12. 最终部署/替换清单

### 12.1 客户端必须替换

```text
clien/BeiDou.exe
clien/Data/Skill/1112.img
clien/Data/Skill/1512.img
clien/Data/String/Skill.img
```

不需要：

```text
clien/BeiDouVSkill.dll
clien/VSkill/
clien/*.bak-vskill*
```

### 12.2 服务端必须替换

```text
gms-server/BeiDou.jar
gms-server/wz/Skill.wz/1112.img.xml
gms-server/wz/Skill.wz/1512.img.xml
gms-server/wz/String.wz/Skill.img.xml
gms-server/scripts-zh-CN/BeiDouSpecial/技能中心.js
gms-server/scripts-zh-CN/BeiDouSpecial/五转技能面板.js
```

如需快速转职自动学习同一批技能，再替换：

```text
gms-server/scripts-zh-CN/BeiDouSpecial/快速转职.js
```

### 12.3 开发脚本，不是线上运行依赖

```text
tool/scripts/migration/migrate_shenshuo_vskills.py
tool/scripts/patch-client/patch_vskill_attacks.py
```

建议一起归档，但不要在线上 Windows 游戏目录里直接执行未经备份的 EXE 重建。

### 12.4 `下载/补丁` 当前归档结构

```text
/Users/lizixian/Downloads/补丁/clien/BeiDou.exe
/Users/lizixian/Downloads/补丁/clien/Data/Skill/1112.img
/Users/lizixian/Downloads/补丁/clien/Data/Skill/1512.img
/Users/lizixian/Downloads/补丁/clien/Data/String/Skill.img
/Users/lizixian/Downloads/补丁/gms-server/BeiDou.jar
/Users/lizixian/Downloads/补丁/gms-server/wz/Skill.wz/1112.img.xml
/Users/lizixian/Downloads/补丁/gms-server/wz/Skill.wz/1512.img.xml
/Users/lizixian/Downloads/补丁/gms-server/wz/String.wz/Skill.img.xml
/Users/lizixian/Downloads/补丁/gms-server/scripts-zh-CN/BeiDouSpecial/技能中心.js
/Users/lizixian/Downloads/补丁/gms-server/scripts-zh-CN/BeiDouSpecial/五转技能面板.js
/Users/lizixian/Downloads/补丁/gms-server/scripts-zh-CN/BeiDouSpecial/快速转职.js
```

补丁目录中即使保留了历史 `patch_vskill_client.py`，也不代表最终客户端要执行它。当前最终运行方案以本节的替换清单为准。

## 13. 故障定位流程

### 13.1 技能中心没有五转入口

检查：

```text
scripts-zh-CN/BeiDouSpecial/技能中心.js 是否已替换
服务端当前语言是否加载 scripts-zh-CN
脚本是否重载/服务端是否重启
```

### 13.2 面板显示“技能数据不可用”

这个分支只在：

```text
SkillFactory.getSkill(skillId) == null
或 skill.getMaxLevel() < 1
```

时出现。先检查服务端 XML 节点和 `level/1`，再确认服务端已重启并重新执行 `loadAllSkills()`。

### 13.3 图标或名称为空

```text
图标空 -> 检查客户端 Data/Skill/<book>.img 和 icon Canvas
名称空 -> 检查客户端 Data/String/Skill.img
服务端名称空 -> 检查服务端 wz/String.wz/Skill.img.xml
```

### 13.4 已学习，但快捷栏没出现

1. 看面板是否明确提示“8 个快捷栏按键都已有内容”。
2. 腾出的必须是当前 8 个 quickslot 按键对应的 keymap binding，不是只移动视觉图标。
3. 腾位后重新在面板选择该技能。
4. 如果仍失败，确认线上 JAR 包含 `Character.addSkillToFirstFreeQuickslot()`，且面板不是历史固定 Y 键版。

### 13.5 按键后完全无反应

按顺序检查：

1. `keymap` 中该键是否为 `type=1, action=真实技能 ID`。
2. 客户端是否真的替换了最终 `BeiDou.exe`，而不是只替换 WZ。
3. 运行 `patch_vskill_attacks.py --dry-run`，必须同时验证键盘钩子、后验证分发钩子和原生验证函数字节。
4. 检查 ID 是否同时存在于 `VSKILL_IDS`，仅存在面板列表无效。
5. 检查是否误用历史只钩 `0x00967A10` 的版本。

### 13.6 有动作/特效，但怪物不扣血

这表明至少本地播放路径开始了，但不代表服务端攻击闭环完成。检查：

```text
服务端是否收到 RecvOpcode 0x2C
parseDamage 中的 skillId 是否真实 ID
chr.getSkillLevel(skillId) 是否为 1
SkillFactory.getSkill(skillId) 是否非 null
StatEffect 的 attackCount/mobCount/mpCon/damage/lt/rb 是否可解析
applyAttack 是否因目标数、MP、距离或冷却校验返回
```

### 13.7 施放者能看，其他玩家不能看

检查附近观察者是否在 `getRangedDistance()` 范围内，是否收到服务端 `SendOpcode.CLOSE_RANGE_ATTACK = 0xBA`，以及观察者客户端是否也部署了同一批 Skill IMG。EXE 补丁主要解决本地按键施放；其他客户端显示广播仍需要对应 WZ 资源。

### 13.8 黑屏、CPU/温度快速上升

立即停止测试，检查是否用了历史“在 `0x0076425C` 直接返回 1”的危险 EXE。该版本绕过了完整验证/初始化，后续攻击代码读取未初始化状态，曾导致黑屏和异常循环。

历史危险版本记录哈希：

```text
41a74294b2ec5ca2c2ae86585f1342ec12828e72120e447643e01c4b01400c90
```

永远不要使用该版本。最终脚本已将“原生验证函数入口字节必须保持原样”做成强制验证。

## 14. 完整踩坑记录与根因

### 坑 1：用独立 Win32 窗口做技能面板

**现象**：窗口能打开，日志显示 `Independent panel window was shown`，但游戏鼠标被游戏捕获，面板不能点。

**根因**：独立顶层窗口不在游戏自身 UI/输入管理中，焦点和鼠标捕获与游戏冲突。

**最终处理**：改用 NPC 对话 UI。最终 EXE 不加载面板 DLL。

### 坑 2：把“能学习、能绑键”当成“客户端已识别”

**现象**：技能能放到键盘，但按下毫无反应。

**根因**：键位只是 `type=1/action=skillId`。旧 EXE 的键盘分发和 `DoActiveSkill` 后续分发仍不接受这些 ID。

**最终处理**：同时打通 `0x0094F89E` 和 `0x009678F9` 两道门。

### 坑 3：在 `0x0076425C` 强制返回成功

**现象**：点技能黑屏，CPU/温度快速上升。

**根因**：`0x00764256` 不是纯布尔分类器，还初始化后续攻击代码需要的状态。短路返回使后续读取未初始化上下文。

**最终处理**：完整保留原生验证，只在验证完成后改变类型分发。

### 坑 4：把白名单挂在 `0x00967A10`

**现象**：补丁表里明明有 40 个 ID，按键仍无反应。

**根因**：`0x00967A10` 是原有技能 ID 二叉分发表的中间节点，只处理约 1,121,xxx 的某个区间。11,121,xxx 和 15,121,xxx 的大 ID 在更早的比较就跳到了其他分支，根本不会执行这里的新表。

**最终处理**：改在所有普通主动技能验证后都会到达的公共点 `0x009678F9` 执行精确白名单。

### 坑 5：每次固定绑定 Y 键

**现象**：放第二个技能时，第一个消失。

**根因**：历史面板每次都调用 `addSkillToKeyboardAndQuickslot(21, skillId)`。`keymap` 以按键码为 key，同一个 21/Y 不可能同时保存两个 action。

**最终处理**：在当前快捷栏的 8 个按键中查找第一个空 keymap。

### 坑 6：只取消自动绑定，指望从原生技能窗拖拽

**现象**：学习后仍无法使用，因为原生技能窗不显示这批大 ID，玩家无处拖拽。

**最终处理**：保留自动绑定，但改为无覆盖的空位查找。

### 坑 7：新键不在快捷栏时固定覆盖第 1 格

**现象**：角色 keymap 可能还有技能，但快捷栏视觉上前一个消失。

**根因**：历史 `addSkillToKeyboardAndQuickslot()` 在新 keyCode 不在 quickslot 数组时，直接执行 `quickSlots[0] = quickKey`。

**最终处理**：不修改 8 个 quickslot 键的排列，只对它们对应的空 keymap 写 binding。

### 坑 8：把神说客户端机器码当成 BeiDou 的通用答案

**根因**：两者不是同一版本的 EXE，函数地址、技能表和原生职业支持不同。

**最终处理**：神说只作为 EMS WZ 资源/行为来源；客户端识别以 BeiDou 自身二进制控制流为准。

### 坑 9：EMS IMG 直接复制到 GMS 客户端

**根因**：Canvas payload 的区域 key 不同。

**最终处理**：每个 Canvas 先以 EMS 解码成 RGBA，再以 GMS key 重新编码。

### 坑 10：`brandishNew` 动作在旧角色资源中不存在

**现象**：技能进入攻击路径后动作不兼容。

**最终处理**：只将 1512 源中实际出现的一处 `brandishNew` 别名为 `brandish1`。

### 坑 11：将全部技能强制套入 Brandish 专用补丁

**根因**：Brandish 特殊路径存在剑/斧武器限制，将拳套/指虎类技能套入会被拒绝。

**最终处理**：当前只把不存在的资源动作名别名为 `brandish1`，不将 40 个 ID 全部伪装成 Brandish ID，攻击路径保留真实 ID。

### 坑 12：把 `skillType=3` 原样保留给旧服务端

**根因**：当前 `SkillFactory` 只对 `skillType==2` 明确设 BUFF，且一旦 `skillType` 存在就不走后面的 `effect/hit/ball` 推导分支。高版的类型语义不能直接当成旧端已实现的类型。

**最终处理**：当前 40 个均有 `hit` 的攻击技能删除 `skillType=3`，让旧服务端按它实际实现的节点规则解析。这个处理不推广到其他技能类型。

## 15. 回滚、安全性和禁止事项

1. 替换 EXE、IMG、XML、JAR 前要成套备份，不要只备份其中一端。
2. 回滚时也要将客户端 EXE/Skill/String 和服务端 JAR/Skill/String/JS 回到同一版本。
3. 不要使用 SHA-256 为 `41a74294...` 的历史危险 EXE。
4. 不要再在 `0x0076425C` 短路返回。
5. 不要把 `0x00967A10` 当成所有大 ID 都会经过的公共入口。
6. 不要在没有保留原指令和非目标技能控制流的情况下写全局跳转。
7. 不要对已存在但与当前脚本不匹配的 `.vattack` 强行就地覆盖；回到已验证基底重建。
8. 不要将 `BeiDouVSkill.dll` 当成最终施放依赖。它的最后用途是历史诊断调用链。
9. 不要用固定键位批量绑定多个技能。
10. 不要在没有检查技能类型的情况下把新 ID 全部跳到近战分支。

## 16. 当前最终产物哈希

以 2026-07-20 当前工作区为准：

```text
481b82a5fbf61f4993aa06ece1886d476fd8967544ee5bc9646cfd61810cd1e4  clien/BeiDou.exe
9cfc24185a27171c8fc775de992d34527ac36f9defba50cece8862e2a0e112bb  clien/Data/Skill/1112.img
74e03188baf8d5b37e4e9346a58939a3fc66962a511765ebe08d4f09c623a50f  clien/Data/Skill/1512.img
8b5543a8d380690164f3339bfdf25f39d28df2e3cb33d27e4db22ae295438ad8  clien/Data/String/Skill.img

a7eefb2c76ae06881ff75bb2e5adb459dde37c590cbbf32f71061a047523dd30  gms-server/wz/Skill.wz/1112.img.xml
88b80e8b15d1826b7eaa114c7468ab99f1c155061240109ba9fbb6a0888cdf0c  gms-server/wz/Skill.wz/1512.img.xml
c8a87f220162d4bdbc56dc007201f5f37c683c7b40997220b4d8bc0d7031fcc7  gms-server/wz/String.wz/Skill.img.xml
9e4a5cd19d0cba3e244dfe80ad2831159fc0032e5be6f2a29c4c89f10ac444aa  gms-server/scripts-zh-CN/BeiDouSpecial/五转技能面板.js
b7b8da09af792f1e808fbb8f1b63d3c97f82bf0fa9ca3ec8829093f23214c1e1  gms-server/BeiDou.jar

511a15a40c54aedc2e3f95b4aaf58b33cc756d1c85f6bc0e9caf73c5e624ea5f  tool/scripts/patch-client/patch_vskill_attacks.py
10e975ec9fbdc294922f8a96e38b238fb8a871c45c65ffa5efc1f5e92f3af5d8  tool/scripts/migration/migrate_shenshuo_vskills.py
```

当前工作区与 `下载/补丁` 中三个最终运行核心产物已校验一致：

```text
clien/BeiDou.exe                                      481b82a5...
gms-server/BeiDou.jar                                 b7b8da09...
gms-server/scripts-zh-CN/BeiDouSpecial/五转技能面板.js 9e4a5cd1...
```

哈希只用于识别本文记录的当前版本。后续合法新增技能、修改数值、更新名称或重构 JAR 后，哈希变化是正常的；应同步更新本节、补丁目录和验收记录。
