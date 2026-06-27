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
