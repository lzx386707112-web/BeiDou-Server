# 新增技能与 BeiDou.exe 识别记录

本文记录后续新增技能时，客户端 `BeiDou.exe` 需要如何配合修改。重点结论：
有完整技能节点后，可以尝试通过 exe hook 让客户端把新技能接入已有同类技能逻辑；
但 WZ 节点本身不能保证客户端自动认识这个技能。

## 基本判断

`BeiDou.exe` 里没有一张统一的“技能注册表”。客户端在多个功能点用技能 ID 做硬编码判断：

- 技能动作/分类。
- 选怪路径，例如单体、矩形 AoE、链式、弹道、召唤、全屏。
- 攻击封包生成。
- 技能释放、命中、弹道、buff、特殊效果播放。
- 部分 UI、冷却、状态图标、屏幕效果。

因此新增技能不是只 patch 一个地方就一定完整生效。要看这个技能要模仿哪类已有技能。

例如 `2321010` 复制 `2321003` 时，除了召唤表现相关判断，还需要补客户端技能释放/动作分类表；
否则技能能学习、能绑键，但按快捷键不会触发动作。

## 最稳的新增方式

优先让新技能复制或改造一个已有技能的行为。

例如：

```text
新技能 2121010
行为参考 2121006 / 2121007 / 2121001
目标：矩形范围 AoE 攻击
```

这种情况下，可以把新技能 ID 追加到已有客户端分支中，而不是替换旧技能 ID。

## 后续需要提供的信息

等新技能节点加好后，至少确认这些信息：

```text
新技能 ID
所在职业文件，例如 212.img / 122.img
客户端 clien/Data/Skill/<job>.img 是否已有该技能
服务端 gms-server/wz/Skill.wz/<job>.img.xml 是否已有该技能
String.wz/Skill.img 是否补了技能名和描述
它要模仿哪个已有技能
技能类型：buff、被动、单体、矩形 AoE、全屏、弹道、召唤、持续伤害等
```

攻击技能还要重点检查：

```text
attackCount
mobCount
lt
rb
effect / hit / ball / action / prepare / keydown 等节点
```

## exe patch 原则

1. 先把技能 ID 转为十六进制和 little-endian 字节。

   ```bash
   rtk node -e 'const n=2121010; console.log(n.toString(16), Buffer.from(Uint32Array.of(n).buffer).toString("hex"))'
   ```

2. 在 `clien/BeiDou.exe` 中搜索该 ID 的字节，看客户端是否已经有硬编码识别。

3. 反汇编同类技能附近逻辑，确认目标分支。

   ```bash
   rtk objdump -D -Mintel --start-address=0x... --stop-address=0x... clien/BeiDou.exe
   ```

4. 优先用跳板和 code cave 追加新技能判断。

   不要直接把旧技能 ID 改成新技能 ID，否则旧技能行为会被破坏。

5. code cave 中保留被覆盖的原逻辑。

6. patch 后用 `objdump` 验证跳转和比较目标正确。

7. 游戏内验证自己视角、他人视角、实际命中目标、服务端校验是否正常。

## 已确认可参考的 AoE 分支

当前 `2121006` 群攻补丁已经验证过矩形 AoE 分支：

```text
AoE 分支 VA      = 0x956372
hook VA          = 0x955d0e
当前 code cave VA = 0xaef602
```

当前 cave 逻辑大意：

```asm
cmp eax, 2121006
je  0x956372
cmp eax, 2201005
je  0x956372
jmp 0x955d19
```

如果未来新增技能也要走同一类矩形 AoE，可以把 cave 升级为：

```asm
cmp eax, <newSkillId>
je  0x956372
cmp eax, 2121006
je  0x956372
cmp eax, 2201005
je  0x956372
jmp 0x955d19
```

具体要根据当前 cave 剩余空间和是否需要新 code cave 决定。

## 已成功案例：2321010 复制 2321003

目标：

```text
新技能 ID：2321010
原技能 ID：2321003
职业文件：232.img
技能名：新技能测试
类型：主教强化圣龙同类召唤攻击
成功表现：快捷技能学习后，绑定 Y 键可正常释放
```

必须同时完成四层修改：

```text
1. 客户端技能节点
   clien/Data/Skill/232.img
   克隆 skill/2321003 -> skill/2321010

2. 客户端技能文字
   clien/Data/String/Skill.img
   克隆 2321003 -> 2321010，并把 name 改成“新技能测试”

3. 服务端技能数据与发放入口
   gms-server/wz/Skill.wz/232.img.xml
   gms-server/wz/String.wz/Skill.img.xml
   gms-server/scripts-zh-CN/BeiDouSpecial/快捷技能.js
   gms-server/scripts-zh-CN/BeiDouSpecial/技能全满.js
   gms-server/scripts-zh-CN/BeiDouSpecial/快速转职.js

4. BeiDou.exe 硬编码识别
   不能只补一个地方。2321010 至少需要下面三个 hook。
```

已验证的三个 EXE hook：

```text
hook1：召唤相关距离/方向判断
原位置 VA：0x7A5227
cave VA：0xAEF620
逻辑：cmp [ebx+0xb4], 2321010；命中后走 2321003 同一分支 0x7A5236

hook2：技能对象属性分类
原位置 VA：0x7AD4F8
cave VA：0xAEF650
逻辑：cmp eax, 2321010；命中后走 2321003 同一分支 0x7AD51B

hook3：技能释放/动作分类表
原位置 VA：0x967EE6
cave VA：0xAEF680
逻辑：cmp esi, 2321010；命中后走 2321003 同一分支 0x9689DF
```

关键排错结论：

```text
技能栏能看到，说明客户端 WZ、String、服务端 teachSkill/登录封包大体没问题。

能绑定到快捷键但按键没反应，通常不是技能栏问题，而是客户端释放/动作分类没认这个技能。
2321010 这次就是缺少 hook3，导致技能 ID 超出原 2321000~2321009 的分类范围，
客户端没有把它送进 2321003 的释放处理分支。

服务端学习成功不代表客户端会释放。客户端按键释放前还会做一轮本地技能类型分派。
```

验证命令：

```bash
rtk objdump -D -Mintel --start-address=0x967ed8 --stop-address=0x967f20 clien/BeiDou.exe
rtk objdump -D -Mintel --start-address=0xaef680 --stop-address=0xaef6c0 clien/BeiDou.exe
```

成功时应能看到：

```asm
0x967ee6: jmp 0xaef680
0xaef680: cmp esi, 0x236a72
0xaef686: je  0x9689df
```

本案例脚本：

```text
tool/scripts/patch_2321010_skill.py
```

注意：这个脚本只用于最初的单技能测试。当前已经把 `2321010` 扩展成龙神复刻技能范围，
后续维护应优先使用：

```text
tool/scripts/patch_bishop_dragon_skills.py
```

## 已实现案例：2321010-2321018 复刻龙神效果

目标：

```text
职业文件：232.img
原行为参考：2321003
技能类型：主教强化圣龙同类召唤攻击
视觉来源：Data/Skill/Dragon/_Canvas/2217.img、2218.img、2220.img
实现方式：每个新技能固定一种龙神攻击效果，而不是单个技能内随机效果
```

当前技能文字从 `/Users/lizixian/Documents/mxd/273/sanjindao/Data/String/Skill.img` 复制，
不要用临时自造名字覆盖。

当前技能分配：

```text
2321010 聖歐尼斯龍 -> String 22171081 -> 2217.img / dragonSwift
2321011 龍之躍 -> String 22141012 -> 2217.img / dragonDive
2321012 龍之氣息 -> String 22171063 -> 2217.img / dragonBreath
2321013 閃雷之捷 -> String 22140014 -> 2218.img / dragonSwiftThunder
2321014 塵土之躍 -> String 22170067 -> 2218.img / dragonDiveEarth
2321015 風之氣息 -> String 22170066 -> 2218.img / dragonBreathWind
2321016 龍之捷VI -> String 22201003 -> 2220.img / 6thDragonSwift
2321017 龍之躍VI -> String 22201007 -> 2220.img / 6thDragonDive
2321018 龍之氣息VI -> String 22201011 -> 2220.img / 6thDragonBreath
```

语义注意：

```text
2217 才包含 stand/move 等龙 UI 和召唤相关素材。
2218、2220 主要是龙已经存在后的攻击动作素材。
当前 2321010-2321018 仍然借用 2321003 的召唤技能释放路径来播放 summon/attack1，
这是为了先验证客户端能识别并播放龙攻击动画。
如果要完全复刻 Evan 的机制，应下一步拆成：
1. 一个真正的召唤/龙 UI 技能。
2. 多个非召唤的龙攻击技能。
3. 服务端和客户端都检查“龙已召唤”后才允许释放攻击技能。
```

实现内容：

```text
1. 客户端 232.img
   复制 2321003 的技能结构和等级数据。
   替换 summon/summoned、stand、fly、die、attack1 为龙神素材帧。

2. 客户端 String/Skill.img
   写入 2321010-2321018 的技能名。

3. 服务端 XML 与发放入口
   gms-server/wz/Skill.wz/232.img.xml
   gms-server/wz/String.wz/Skill.img.xml
   快捷技能.js、技能全满.js、快速转职.js

4. 服务端 Java 召唤识别
   Bishop.java 增加常量和 isDragonCopySkill。
   StatEffect.java 把这些技能加入 summon statup 和移动类型分支。
   Character.java 把这些技能加入召唤取消/驱散分支。
   SummonDamageHandler.java 放行这些召唤技能的伤害日志校验。

5. BeiDou.exe 硬编码识别
   三个原 2321010 hook 升级为范围判断：
   sub skillId, 2321010
   cmp <= 8
   命中后走 2321003 同类分支。
```

EXE 当前范围 hook：

```text
hook1 VA 0x7A5227 -> cave 0xAEF620
hook2 VA 0x7AD4F8 -> cave 0xAEF650
hook3 VA 0x967EE6 -> cave 0xAEF680
范围：2321010-2321018
```

验证命令：

```bash
rtk python3 tool/scripts/patch_bishop_dragon_skills.py --dry-run
rtk objdump -D -Mintel --start-address=0xaef620 --stop-address=0xaef645 clien/BeiDou.exe
rtk objdump -D -Mintel --start-address=0xaef650 --stop-address=0xaef675 clien/BeiDou.exe
rtk objdump -D -Mintel --start-address=0xaef680 --stop-address=0xaef6b0 clien/BeiDou.exe
```

游戏内验证路径：

```text
当前通过 BeiDouSpecial/龙神技能面板.js 选择其中一个龙神技能。
脚本会 teachSkill 到 30 级。
面板会先询问“只学习/解锁”还是“学习并绑定到 Y 键”。
默认不要强制绑定，避免服务端发送全量 keymap 时覆盖玩家刚手动调整过的按键。
快捷技能.js、技能全满.js、快速转职.js 不再发放 2321010-2321018。
如果要改成物品双击唤起，只需要把对应物品的 spec/script 指向“龙神技能面板”。
```

图标处理：

```text
当前资源只提供 Dragon/_Canvas 动作帧，没有完整 Dragon 技能文件中的原始 icon。
patch_bishop_dragon_skills.py 会从对应攻击动作的中间帧裁剪并缩放生成 32x32 图标，
写入 icon/iconMouseOver/iconDisabled，避免 2321010-2321018 全部显示为 2321003 的强化圣龙图标。
```

## 阶段性记录：2331010-2331018 独立 V tab 尝试

目标：

```text
2321010-2321018 保留为当前可用的主教 4 转龙神复刻技能。
2331010-2331018 作为显示/学习用的新技能组，目标是放到单独的 V tab。
2331010 是召唤龙。
2331011-2331018 是手动龙攻击。
```

当前生成脚本：

```text
tool/scripts/patch_bishop_dragon_manual_attacks.py
```

已落地内容：

```text
1. 客户端新增 clien/Data/Skill/233.img。
   2331010-2331018 从 2321010-2321018 克隆。

2. 服务端新增 gms-server/wz/Skill.wz/233.img.xml。

3. String 已补 2331010-2331018。
   客户端：clien/Data/String/Skill.img
   服务端：gms-server/wz/String.wz/Skill.img.xml

4. 龙神技能面板改为 teachSkill 2331010-2331018。
   文件：gms-server/scripts-zh-CN/BeiDouSpecial/龙神技能面板.js

5. 服务端 Java 已识别 233 组。
   Bishop.java：增加 DRAGON_5TH_* 常量，isDragonCopySkill/isDragonManualAttackSkill 支持 233。
   StatEffect.java：2331010 加入 SUMMON statup 和 FOLLOW 移动类型。
   Character.java：2331010 加入 dispelSkills。
   MagicDamageHandler.java：233 攻击要求 2321010 或 2331010 召唤存在，攻击后取消召唤。

6. EXE 当前尝试补丁：
   召唤识别支持 2331010。
   手动攻击释放支持 2331011-2331018。
   AoE 判定支持 2331011-2331018。
   技能窗口职业分类支持 233。
   尝试把技能窗口 tab 循环从 <= 5 扩到 <= 6。
   尝试让第 5 页只收 232，第 6 页只收 233。
```

关键 EXE hook 记录：

```text
0x7A5227  召唤技能路径 hook，支持 2321003/2321010/2331010。
0x7AD4F8  召唤技能路径 hook，支持 2321003/2321010/2331010。
0x967EE6  释放分类 hook，支持 2321010/2331010 召唤与 232/233 攻击范围。
0x955D0E  AoE 分类 hook，支持 2321011-2321018 与 2331011-2331018。
0x4F0751  技能窗口职业分类 hook。
0xA0A3D6  Bishop 技能列表子分支 hook，避免 233 进入后又被 232 判断过滤。
0x4E6679  技能窗口 tab 循环上限，当前从 5 改为 6。
0x4B071E  技能窗口 tab 布局槽位上限，当前从 5 改为 6。
0x4EFDE8  当前职业 4 转 tab 分支，尝试拆成 232 第 5 页、233 第 6 页。
```

特效/延时结论：

```text
不要把 Dragon/_Canvas 的完整龙动作补到 skill/effect。
实测现象是客户端疑似顺序播放 effect，播完后才出现 hit/伤害反馈，
会导致击中效果延迟 1-2 秒。

当前修正版改法：
不要把手动龙攻击伪装成 genesis 类大范围技能。
2321011-2321018、2331011-2331018 改用已验证普通矩形 AoE 更接近的 action=paralyze。
完整 Dragon 动作写入 skill/effect。
移除 skill/effect0，避免额外表现入口干扰。
保留原始 hit。

静态检查结果：
2321011-2321018、2331011-2331018：
action=paralyze。
effect 有完整 Dragon 动作帧。
effect0 不存在。
hit 存在，delay 总和为 0。
```

本次修复点：

```text
1. 手动攻击原来使用 action=genesis。
   现改为：
   - action=paralyze。
   - effect 写入完整 Dragon 动作帧。
   - effect0 移除。
   这样让龙攻击更接近 2121006 这类已验证矩形 AoE 的表现路径，
   避免 genesis 类大特效路径先播完特效再出现 hit/伤害反馈。

2. V tab 不显示的关键原因之一是 tab 布局槽位函数仍限制 1..5。
   除了 0x4E6679 的 tab 循环上限 5 -> 6 外，
   还需要把 0x4B071E 从 cmp eax, 5 改为 cmp eax, 6，
   否则第 6 页循环到了也拿不到布局槽位，tab 可能不会被画出来。

3. 如果 233 技能仍出现在 4 转 tab，
   说明 0x4F0751 的 selected-tab 过滤还没有命中真实字段，
   需要继续反汇编技能窗口中 [skillWindow + offset] 的当前页签字段。
```

## 最终方案：保留在 4 转 tab

最终没有继续强行实现第 5/V tab，而是采用更稳的 4 转 tab 方案：

```text
1. 技能继续放在主教 4 转职业文件 232.img。
   这样沿用客户端已有技能窗口和释放分类路径，减少 EXE UI patch 风险。

2. 技能排序放到 4 转 tab 最下面。
   通过技能节点顺序/客户端数据顺序控制显示位置。

3. 显示门槛放到服务端控制。
   登录或面板发放时检查角色等级，大于 180 级才 teach/显示龙神技能。
   等级不足时不 teachSkill，客户端技能栏自然不会显示。

4. 5/V tab 尝试先保留为研究记录。
   独立 tab 涉及 tab 循环、布局槽位、职业分类、当前选中页字段等多处 EXE UI 逻辑，
   容易出现“循环到了但不绘制”或“仍归入 4 转 tab”的问题。
```

当前推荐维护方向：

```text
优先维护 232 组技能、4 转 tab 排序、180 级服务端门槛。
不要再为了显示页签优先改 EXE UI，除非后续明确要完整实现第 5/V tab。
```

## 风险边界

容易成功：

- 已有技能改造。
- 新技能复制已有同类攻击。
- 简单 buff 或被动，且服务端和客户端已有通用路径。

中等难度：

- 在已有职业下新增攻击技能，让它接入已有 AoE、弹道或近战分支。
- 新技能需要额外 `effect0/effect1` 表现。

高难度：

- 完全新目标选择。
- 全新封包结构。
- 全新 UI/技能学习/状态图标/冷却逻辑。
- 自定义 WZ 节点名，例如 `myCustomEffect`。

## 当前参考文件

- `tool/scripts/README_2121006_AOE.md`
- `tool/scripts/patch_2121006_exe_aoe.js`
- `tool/scripts/patch_2121006_aoe.py`
- `clien/BeiDou.exe`
- `clien/Data/Skill/<job>.img`
- `gms-server/wz/Skill.wz/<job>.img.xml`
