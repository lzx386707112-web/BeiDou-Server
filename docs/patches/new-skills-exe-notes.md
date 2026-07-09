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

## 备选方案：消耗品热键触发服务端技能

如果暂时不想继续补 `BeiDou.exe` 的主动技能 ID 分支，可以把消耗品当作技能触发器：
客户端按道具快捷键发送 `USE_ITEM` 或 `SCRIPTED_ITEM`，服务端读取道具配置后自行组装一次技能释放。

这个方案的关键不是“消耗品天然能释放主动技能”，而是绕开客户端按技能键释放时的 EXE 分派，
改由服务端模拟攻击流程。适合先做五转、六转或自定义技能验证。

基本流程：

```text
1. 新技能仍然要维护到客户端 Skill/String WZ 和服务端 Skill/String XML。
   例如技能 ID 1321018。

2. 新增一个或多个消耗品作为入口。
   例如 2430125 触发六转技能，2430126 触发五转技能。

3. 消耗品放到键位上执行。
   这里绑定的是道具快捷键，不是传统技能快捷键。

4. 服务端在道具使用入口识别技能 ID。
   可以复用 spec/script 存技能 ID 或脚本标识，例如 script=1321018。

5. GM 命令和道具入口都调用同一套自定义释放逻辑。
   例如：
   !sx <技能ID> <等级>
   !six <类型> <技能ID> <等级>

6. 自定义释放逻辑按固定顺序执行：
   构造攻击上下文
   播放 explosion / 技能表现包
   广播攻击包
   结算前飘字
   结算真实伤害
   结算后补飘字
   发送 enableActions 解锁动作
```

需要注意的边界：

```text
1. 这是服务端接管释放，不等价于客户端真正认识新主动技能。
2. 技能是否能显示、图标是否正常，仍取决于客户端 WZ 和 String。
3. 技能表现能多像原生技能，取决于服务端能否正确广播对应攻击包、特效包和飘字。
4. 弹道、链式、召唤协同、持续引导、客户端本地命中帧强依赖的技能风险更高。
5. 冷却、MP/HP 消耗、目标数、攻击范围、反伤、无敌、死亡和掉落时序都要由服务端补齐。
6. 道具脚本入口必须做白名单，避免玩家通过改包传任意技能 ID。
7. 消耗品热键本身不会自动触发 Skill WZ 里的 screen/effect/hit。
   如果客户端不认可 skillId，服务端发送 SKILL_EFFECT/攻击包也可能只有伤害没有动画。
   这类全屏表现可以优先把 screen 资源移植到 clien/Data/Map/Effect.img，
   再通过 FIELD_EFFECT，也就是 PacketCreator.showEffect("路径") 播放。
```

如果只是用消耗品作为入口，客户端不一定要新增 `Skill/*.img`。消耗品方案绕开的是“按技能键释放”的客户端主动技能分派；
真正需要客户端 Skill 资源的，是服务端广播 `skillEffect`、`magicAttack` 等包时使用的视觉 `skillId`。

当前客户端会在启动时扫描 `clien/Data/Skill`，直接新增 `40001.img` 可能触发“错误的游戏数据”弹窗。
因此第一阶段建议不要把 273 的 `40001.img` 直接写进客户端 Skill 目录。更稳的做法是：

```text
1. 客户端只新增/修改消耗品和 String，让 2430125 可以放键位并携带 script=400011027。
2. 服务端保留 400011027 的 Skill XML 或直接在自定义释放逻辑里维护数值，用于范围、段数、伤害、MP 和冷却。
3. 技能动画先用已有客户端能识别的技能 ID 做 visualSkillId，或者把 400011027 的视觉资源移植到现有合法 Skill IMG 的安全测试 ID。
4. 等确认客户端允许的 Skill IMG/ID 结构后，再考虑恢复真正的 40001.img 客户端资源。
```

后续如果落地，建议先选一个矩形范围或全屏类技能试验。目标是验证：

```text
1. 道具能放快捷键并触发服务端入口。
2. 服务端能从技能 WZ/XML 读到 level、damage、attackCount、mobCount、lt/rb。
3. 能选中预期范围内的怪物。
4. 自己视角和他人视角能看到技能表现或攻击表现。
5. 飘字和真实扣血一致。
6. 击杀、掉落、经验、反伤、冷却和 enableActions 都正常。
```

### 当前试验：273 的 400011027 斗气死亡断层

本次选用 273 导出的 `_Canvas/40001.img` 里的 `400011027` 做第一条链路测试。技能名为“斗气死亡断层”，描述为“用剑分割空间”。

上一轮把 400011027 伪装成 2321020/1121018，再走 `skillEffect`、`magicAttack` 或 EXE hook 的路线，结果都是“有伤害但没有原技能动画”。因此当前版本先回到更小的验证目标：

```text
不新增 Skill WZ
不修改 BeiDou.exe
不广播 skillEffect / magicAttack
只保留消耗品入口 + 服务端选怪结算
把 400011027/screen 迁到 Map/Effect.img
通过 FIELD_EFFECT 播放全屏动画
```

当前实现先复刻 400011027 的 `screen` 全屏动画，不处理 `effect/hit`。参考阿卡伊勒迁移的成功路径，把客户端能识别的资源放到 `clien/Data/Map/Effect.img/customSkill/deathFault/screen`，服务端广播 `PacketCreator.showEffect("customSkill/deathFault/screen")`。由于原始 `screen` 帧只有约 684x268 到 684x384，迁移时会封进与客户端分辨率一致的透明画布，并按统一比例等比缩放居中，避免旧客户端按局部范围效果显示，也避免每帧独立拉伸导致变形或跳动。脚本默认读取 `clien/config.ini` 的 `width/height`，也可以用 `--canvas-width/--canvas-height` 覆盖。源帧从 `19` 开始，迁移时按源帧编号推导时间轴：先补 1 个透明帧，delay 为 `19 * 30ms = 570ms`；后续可见帧 delay 按相邻源帧编号差值计算，例如 `20 -> 23` 会得到 `90ms`。伤害延迟约 800ms 后结算，用来对齐动画节奏。

```text
源技能 ID: 400011027
技能名: 斗气死亡断层
触发道具: 2430125
道具 script: 400011027
MP 消耗: 500
伤害: 416%
攻击段数: 14
最大目标: 15
冷却时间: 5 秒
说明: 施展动作中无敌
范围: lt=(-3000,-2000), rb=(3000,2000)
当前视觉测试: FIELD_EFFECT customSkill/deathFault/screen
画布尺寸: 默认读取 clien/config.ini，也可命令行覆盖
起始透明帧: 1 帧，delay 按源首帧编号计算，当前 570ms
伤害延迟: 800ms
```

相关落地点：

```text
clien/Data/Item/Consume/0243.img
clien/Data/String/Consume.img
clien/Data/Map/Effect.img
gms-server/wz/Item.wz/Consume/0243.img.xml
gms-server/wz/String.wz/Consume.img.xml
gms-server/src/main/java/org/gms/server/skills/CustomSkillCastService.java
gms-server/src/main/java/org/gms/client/command/commands/gm3/CustomSkillCommand.java
tool/scripts/patch-skill/patch_400011027_consumable_test.py
```

测试顺序：

```text
1. 重启服务端，让 Java 入口和 WZ XML 重新加载。
2. 重启客户端，让 0243.img、Consume.img 和 Map/Effect.img 更新生效。
3. 先用 GM 命令验证服务端释放链路：!sx 400011027 1
4. 再发放 2430125，把道具放到键位上使用。
5. 观察是否先播放全屏“斗气死亡断层”screen 动画，再约 800ms 后扣血。
6. 如果有动画但位置偏高/偏低，优先调 `patch_400011027_consumable_test.py` 里 paste 的 y 偏移或 `origin_y`。
7. 如果仍然没有动画，下一步检查客户端是否实际读取 `Map/Effect.img/customSkill/deathFault/screen`，以及 FIELD_EFFECT 的路径名是否被旧客户端限制。
```

## 工具与库

本次主要用到这些工具：

```text
Python 3
  用来批量改客户端 WZ、服务端 XML 和 BeiDou.exe 字节。

tool/wz-python/wzpy
  仓库内的 WZ 读写库，用 WzImage/WzKey 解析 .img，
  用 encode_image_body 写回客户端 WZ。

Pillow
  来自 tool/wz-python/requirements.txt 的 pillow>=10.0。
  用于 decode_canvas 后裁剪/缩放龙神动作帧，生成 32x32 技能图标。

struct
  Python 标准库，用来生成 little-endian 技能 ID、相对跳转偏移、cmp 立即数。

objdump
  用来反汇编 BeiDou.exe，确认 hook 位置、跳转目标和 code cave 内容。

rg / sed / jar / unzip
  用于快速检查文件、脚本、jar 内容和构建产物。

rtk
  本地命令代理。仓库里所有示例命令都按当前环境习惯加了 rtk 前缀。
```

WZ 区域 key 要特别注意：

```text
当前客户端 clien/Data 主要按 GMS key 读写。
外部素材来源 <modern-client>/Data 按 BMS key 读写。
脚本里如果 WzKey.for_region 选错，可能能解析节点名，但 canvas 解码/写回会出错。
```

依赖安装参考：

```bash
rtk python3 -m pip install -r tool/wz-python/requirements.txt
```

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

## 推荐排查顺序

新增攻击技能时，建议按下面顺序查，不要一开始就改 EXE：

```text
1. 客户端 WZ 是否有技能节点。
   clien/Data/Skill/<job>.img

2. 客户端 String 是否有技能名和描述。
   clien/Data/String/Skill.img

3. 服务端 XML 是否有同一份技能数据。
   gms-server/wz/Skill.wz/<job>.img.xml
   gms-server/wz/String.wz/Skill.img.xml

4. 服务端是否真的 teachSkill。
   技能栏看得到，通常说明这一步和前两步大体没问题。

5. 快捷键能绑定但按键没反应时，再查客户端释放/动作分类。
   这通常是 EXE 硬编码没有认新技能。

6. 技能能释放但打不到怪时，再查 AoE/选怪分支和服务端校验。

7. 技能能打怪但表现异常时，再查 action、effect、hit、effect0、delay。
```

## 实战流程：从一个新技能定位到 EXE hook

下面这套流程是从 `2121006` 群攻、`2321010` 复制强化圣龙、`2321010-2321018`
龙神复刻技能，以及后续 `233` V tab 尝试里沉淀出来的。重点不是记住某一个地址，
而是知道“症状对应客户端哪一层硬编码”。

### 1. 先选一个行为参考技能

新增技能不要从空白节点开始，先找一个客户端已经完整支持的同类技能。

```text
矩形 AoE：参考 2121006 / 2121007 / 2201005
召唤攻击：参考 2321003
全屏攻击：参考 genesis 类技能
弹道技能：参考同职业已有 ball/keydown/prepare 结构
```

必须先确认两件事：

```text
1. 新技能的数据结构尽量克隆参考技能，再改名字、图标、范围、特效。
2. EXE 里不是“注册新技能”，而是把新技能 ID 接到参考技能已经能走通的分支。
```

例如 `2321010` 复制 `2321003` 时，WZ 里复制技能节点只能让技能栏认识它；
如果 EXE 没把 `2321010` 接进 `2321003` 的释放/召唤分支，快捷键按下去仍然没动作。

### 2. 确认数据层是否完整

客户端和服务端都要有同一份技能数据。攻击技能至少检查这些节点：

```text
客户端：
clien/Data/Skill/<job>.img
clien/Data/String/Skill.img

服务端：
gms-server/wz/Skill.wz/<job>.img.xml
gms-server/wz/String.wz/Skill.img.xml

等级数据：
level/1..30
attackCount
mobCount
lt
rb
action
effect
hit
ball / prepare / keydown / summon 等按技能类型决定
```

服务端 `StatEffect` 会从 XML 读技能参数，例如 `mobCount` 缺失时默认只有 1：

```java
ret.mobCount = DataTool.getInt("mobCount", source, 1);
```

攻击处理还会校验客户端上报目标数：

```java
if (attack.numAttacked > mobCount) {
    AutobanFactory.MOB_COUNT.autoban(...);
    return;
}
```

所以如果要改群攻，只补 EXE 不补 `mobCount/lt/rb` 不行；反过来，只补 WZ 不补 EXE，
客户端也可能仍然只选 1 个目标。

### 3. 把技能 ID 转成 EXE 里能搜的字节

EXE 里比较技能 ID 时通常是 32 位立即数，小端序存放。

```bash
rtk node - <<'NODE'
const ids = [2121006, 2321003, 2321010, 2321018, 2331010];
for (const id of ids) {
  const b = Buffer.alloc(4);
  b.writeUInt32LE(id >>> 0, 0);
  console.log(id, "hex=0x" + id.toString(16), "le=" + b.toString("hex"));
}
NODE
```

也可以直接扫描 `BeiDou.exe` 中某个技能 ID 出现的位置：

```bash
rtk node - <<'NODE'
const fs = require("fs");
const buf = fs.readFileSync("clien/BeiDou.exe");

function le32(n) {
  const b = Buffer.alloc(4);
  b.writeUInt32LE(n >>> 0, 0);
  return b;
}

for (const id of [2321003, 2321010, 2121006, 2201005]) {
  const needle = le32(id);
  const hits = [];
  for (let i = 0; (i = buf.indexOf(needle, i)) >= 0; i += needle.length) {
    hits.push("0x" + i.toString(16));
  }
  console.log(id, hits.join(" "));
}
NODE
```

这里扫出来的是文件偏移，不是反汇编里看到的虚拟地址。

### 4. 做 PE 地址换算

当前 `BeiDou.exe` 的 `.text` 段里，文件偏移和虚拟地址的关系可以按下面处理：

```text
ImageBase = 0x400000
file offset = VA - 0x400000
VA = file offset + 0x400000
```

例如：

```text
file offset 0x555d0e -> VA 0x955d0e
VA 0x7A5227 -> file offset 0x3A5227
VA 0xAEF620 -> file offset 0x6EF620
```

反汇编时用 VA：

```bash
rtk objdump -D -Mintel --start-address=0x955d00 --stop-address=0x955d40 clien/BeiDou.exe
```

写文件时用 offset：

```python
IMAGE_BASE = 0x400000
HOOK_VA = 0x955D0E
HOOK_OFFSET = HOOK_VA - IMAGE_BASE
```

### 5. 根据症状判断要找哪一类硬编码

不同现象对应不同 EXE 逻辑，不要所有问题都往一个 hook 上堆。

```text
技能栏没有技能：
  先查 WZ / String / 服务端 teachSkill / 数据库 skills。
  如果是新职业段，例如 233，再查技能窗口职业分类和 tab 逻辑。

技能栏有、能绑键、按键没动作：
  优先查技能释放/动作分类。
  2321010 当时就是缺 0x967EE6 这一类释放分类 hook。

技能能释放但只能打一只：
  先查 mobCount/lt/rb。
  数据没问题再查 AoE/选怪分支，例如 0x955D0E。

技能能打怪但 hit 慢：
  先查 effect/hit/action 播放链路。
  这次 Dragon 动作放到 genesis 路径时出现过 effect 先播完、hit 后出现的问题。

新职业段技能不进技能窗口：
  查 skillId / 10000 的职业段分发。
  233 尝试时涉及 0x4F0751 和 Bishop 子分支 0xA0A3D6。

想新增第 5/V tab：
  不只是补 UI 图。
  还要查 tab 循环上限、tab 布局槽位、当前选中页字段、职业段过滤。
```

### 6. 反汇编对照技能附近代码

优先从“参考技能 ID 出现的位置”附近开始反汇编。例如 `2321003` 的小端字节是
`6b 6a 23 00`，能定位到召唤相关判断：

```bash
rtk objdump -D -Mintel --start-address=0x7a5200 --stop-address=0x7a5260 clien/BeiDou.exe
rtk objdump -D -Mintel --start-address=0x7ad4e0 --stop-address=0x7ad530 clien/BeiDou.exe
rtk objdump -D -Mintel --start-address=0x967ed8 --stop-address=0x967f20 clien/BeiDou.exe
```

判断目标分支时要看“命中旧技能后跳到哪里”，而不是只看 `cmp` 本身。
新增技能的目标就是让新 ID 命中后跳到同一个已验证分支。

### 7. 写 hook 时优先追加判断，不要替换旧 ID

错误做法：

```text
把 EXE 里的 2321003 直接改成 2321010。
```

这样旧技能会坏掉，而且同一技能可能在多处被硬编码，改一处不完整。

推荐做法：

```text
1. 原位置写 5 字节 jmp 跳到 code cave。
2. cave 里先保留被覆盖的原逻辑或等效逻辑。
3. 追加新技能 ID 判断。
4. 命中新技能时跳到旧技能的成功分支。
5. 不命中时跳回原来的继续分支。
```

Python 写相对跳转的基础函数：

```python
import struct

def jmp(from_va: int, to_va: int) -> bytes:
    return b"\xE9" + struct.pack("<i", to_va - (from_va + 5))

def je(from_va: int, to_va: int) -> bytes:
    return b"\x0F\x84" + struct.pack("<i", to_va - (from_va + 6))

def jbe(from_va: int, to_va: int) -> bytes:
    return b"\x0F\x86" + struct.pack("<i", to_va - (from_va + 6))

def cmp_reg_imm(op: bytes, value: int) -> bytes:
    return op + struct.pack("<I", value)
```

连续技能 ID 可以用范围判断，避免写一串 `cmp`：

```asm
mov edx, skillId
sub edx, 2321010
cmp edx, 8
jbe target
```

这表示 `2321010-2321018` 都命中，因为最大差值是 `8`。

### 8. patch 前后都要验证字节

脚本里要检查当前位置是“原始字节”或“自己已经写过的 hook”，避免重复 patch 或误伤别的版本。

```python
current = bytes(data[HOOK_OFFSET:HOOK_OFFSET + len(HOOK_ORIGINAL)])
if current not in (HOOK_ORIGINAL, hook_patch):
    raise RuntimeError(f"unexpected bytes at 0x{HOOK_VA:x}: {current.hex()}")
```

写入后用 `objdump` 看两段：

```bash
rtk objdump -D -Mintel --start-address=0x7a5220 --stop-address=0x7a5248 clien/BeiDou.exe
rtk objdump -D -Mintel --start-address=0xaef620 --stop-address=0xaef648 clien/BeiDou.exe
```

成功时应该能看到原位置已经跳到 cave，cave 里有新技能范围判断。

## exe patch 原则

上面的流程是完整操作步骤，实际落地时再记住这几条原则：

```text
1. 先做数据层闭环，再碰 EXE。
2. 先找同类旧技能，再让新技能接入旧技能已验证分支。
3. 不要把旧技能 ID 直接替换成新技能 ID，要用 code cave 追加判断。
4. code cave 要保留被覆盖的原逻辑，或者写出等效分支。
5. 写入前校验原始字节，写入后 objdump 验证跳转和目标分支。
6. 游戏内验证要分开看：技能栏、按键动作、选怪数量、hit/特效、服务端伤害校验。
```

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

### 2321010 定位过程

当时的现象是：

```text
1. 技能栏能看到 2321010。
2. 服务端可以 teachSkill。
3. 技能能拖到快捷键。
4. 按快捷键没有正常触发 2321003 那套召唤攻击动作。
```

这说明前面 WZ、String、服务端发放都基本没问题，问题集中在客户端本地释放/动作分类。

先扫描参考技能 `2321003` 和新技能 `2321010`：

```bash
rtk node - <<'NODE'
const fs = require("fs");
const buf = fs.readFileSync("clien/BeiDou.exe");

function scanId(id) {
  const b = Buffer.alloc(4);
  b.writeUInt32LE(id >>> 0, 0);
  const hits = [];
  for (let i = 0; (i = buf.indexOf(b, i)) >= 0; i += b.length) {
    hits.push("0x" + i.toString(16));
  }
  return hits;
}

for (const id of [2321003, 2321010]) {
  console.log(id, scanId(id).join(" "));
}
NODE
```

`2321010` 是新增技能，正常情况下原始 EXE 里搜不到；`2321003` 能搜到多个位置。
对这些位置附近反汇编后，最终确认至少三类判断要补：

```text
0x7A5227：召唤相关距离/方向判断。
0x7AD4F8：技能对象/属性分类。
0x967EE6：释放动作分类，决定按快捷键时是否进入对应技能处理。
```

其中 `0x967EE6` 是最容易漏的。前两个 hook 补了以后，技能仍可能“能学、能绑、按键没反应”；
缺的就是这层释放分类。

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

单技能测试时的 cave 逻辑大意：

```asm
; hook1：保留原本 mov [ebp-0x18], eax，再比较 [ebx+0xb4] 的技能 ID
mov [ebp-0x18], eax
cmp dword ptr [ebx+0xb4], 2321003
je  0x7A5236
cmp dword ptr [ebx+0xb4], 2321010
je  0x7A5236
jmp 0x7A5241

; hook2：eax 是当前技能 ID
cmp eax, 2321003
je  0x7AD51B
cmp eax, 2321010
je  0x7AD51B
jmp 0x7AD4FF

; hook3：esi 是当前释放技能 ID
cmp esi, 2321010
je  0x9689DF
; 后面接回原本被覆盖的比较/跳转逻辑
jmp 0x967EF5
```

后续扩展为 `2321010-2321018` 时，不再逐个 `cmp`，而是改成范围判断：

```asm
mov edx, skillId
sub edx, 2321010
cmp edx, 8
jbe oldSkillSuccessBranch
```

当前维护脚本对应：

```text
tool/scripts/patch-skill/patch_bishop_dragon_skills.py
```

关键常量：

```python
OLD_ID = 2321003
NEW_MIN = 2321010
NEW_MAX = 2321018

HOOK1_VA = 0x7A5227
HOOK1_CAVE_VA = 0xAEF620
HOOK1_EQUAL_VA = 0x7A5236
HOOK1_NOT_EQUAL_VA = 0x7A5241

HOOK2_VA = 0x7AD4F8
HOOK2_CAVE_VA = 0xAEF650
HOOK2_EQUAL_VA = 0x7AD51B
HOOK2_RETURN_VA = 0x7AD4FF

HOOK3_VA = 0x967EE6
HOOK3_CAVE_VA = 0xAEF680
HOOK3_TARGET_VA = 0x9689DF
HOOK3_RETURN_VA = 0x967EF5
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
rtk python3 tool/scripts/patch-skill/patch_bishop_dragon_skills.py --dry-run
rtk objdump -D -Mintel --start-address=0x7a5220 --stop-address=0x7a5248 clien/BeiDou.exe
rtk objdump -D -Mintel --start-address=0x7ad4e8 --stop-address=0x7ad530 clien/BeiDou.exe
rtk objdump -D -Mintel --start-address=0x967ed8 --stop-address=0x967f20 clien/BeiDou.exe
rtk objdump -D -Mintel --start-address=0xaef620 --stop-address=0xaef648 clien/BeiDou.exe
rtk objdump -D -Mintel --start-address=0xaef650 --stop-address=0xaef678 clien/BeiDou.exe
rtk objdump -D -Mintel --start-address=0xaef680 --stop-address=0xaef6c0 clien/BeiDou.exe
```

成功时应能看到：

```asm
0x7a5227: jmp 0xaef620
0x7ad4f8: jmp 0xaef650
0x967ee6: jmp 0xaef680
0xaef680: mov edx, esi
0xaef682: sub edx, 0x236a72   ; 2321010
0xaef688: cmp edx, 0x8
0xaef68b: jbe 0x9689df
```

本案例脚本：

```text
tool/scripts/patch-skill/patch_2321010_skill.py
```

注意：这个脚本只用于最初的单技能测试。当前已经把 `2321010` 扩展成龙神复刻技能范围，
后续维护应优先使用：

```text
tool/scripts/patch-skill/patch_bishop_dragon_skills.py
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

当前技能文字从 `<modern-client>/Data/String/Skill.img` 复制，
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
rtk python3 tool/scripts/patch-skill/patch_bishop_dragon_skills.py --dry-run
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
tool/scripts/patch-skill/patch_bishop_dragon_manual_attacks.py
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
0x4F0751  技能窗口职业分类 hook。当前确认 112 新增四转技能也要在这里放行到第 5 页。
0xA0A3D6  Bishop/四转技能列表子分支 hook，避免 233/112 进入后又被 232 判断过滤。
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

## 实战记录：112 新增四转技能不显示

本次验证目标是解释为什么同样新增技能节点，放在 `232.img` 里能显示，放在 `112.img` 里不显示。

最终确认不是 WZ/String/服务端发放链路问题，而是 `BeiDou.exe` 的技能窗口职业过滤。
测试方式是在 `112.img` 中复制已有技能：

```text
来源技能：1121011
测试技能：1121012
显示名称：测试
文件：
  clien/Data/Skill/112.img
  clien/Data/String/Skill.img
  gms-server/wz/Skill.wz/112.img.xml
  gms-server/wz/String.wz/Skill.img.xml
脚本：
  tool/scripts/patch-skill/patch_1121012_test_skill.py
```

补 EXE 前，`1121012` 即使资源和字符串存在，技能面板仍不显示。补 EXE 后，测试技能可以在 112 四转技能页显示。

关键原因有两处：

```text
1. 0x4F0751
   技能窗口按 skillId / 10000 得到职业段。
   现有 cave 原来只特殊放行：
     232 -> tab 5
     233 -> tab 6
   没有 112，所以 1121012 这类新增技能会被过滤掉。

2. 0xA0A3D6
   创建技能窗口条目时又按 skillId / 10000 做二次判断。
   原 cave 只允许 232/233 继续创建技能条目。
   即使 0x4F0751 放行，112 不补这里也可能进不去真正的 UI 列表。
```

当前补丁做法：

```text
0x4F0751 -> 新 cave 0xAEFA80
  112 -> 当前 tab == 5 时跳到 0x4F0758
  232 -> 当前 tab == 5 时跳到 0x4F0758
  233 -> 当前 tab == 6 时跳到 0x4F0758

0xA0A3D6 -> cave 0xAEF980
  112/232/233 都跳到 0xA0A3E1 创建技能条目
  其他职业跳到 0xA0A49B 拒绝
```

对应脚本：

```text
tool/scripts/patch-client/patch_112_skill_window_display.py
```

验证命令：

```bash
rtk python3 tool/scripts/patch-client/patch_112_skill_window_display.py --dry-run
rtk objdump -D -Mintel --start-address=0xaefa80 --stop-address=0xaefae0 clien/BeiDou.exe
rtk objdump -D -Mintel --start-address=0xaef980 --stop-address=0xaef9b0 clien/BeiDou.exe
```

期望能看到：

```text
0xAEFA80 cave:
  cmp eax, 0x70   ; 112
  cmp [ecx+0x18], 5
  je 0x4F0758
  cmp eax, 0xE8   ; 232
  cmp [ecx+0x18], 5
  je 0x4F0758
  cmp eax, 0xE9   ; 233
  cmp [ecx+0x18], 6
  je 0x4F0758

0xAEF980 cave:
  cmp eax, 0x70   ; 112
  je 0xA0A3E1
  cmp eax, 0xE8   ; 232
  je 0xA0A3E1
  cmp eax, 0xE9   ; 233
  je 0xA0A3E1
```

结论：

```text
给 112.img 新增四转技能时，仅补客户端 Skill/String 和服务端 XML 不够。
如果技能节点 ID 超出旧客户端原本的 112 技能窗口分支，必须把 112 加进技能窗口职业过滤。
当前已实测：补 0x4F0751 + 0xA0A3D6 后，1121012 测试技能可见。
```

## 完成后技能栏仍看不到：补数据库

客户端 WZ、服务端 WZ、String、JAR 都更新后，如果电脑端能看到、手机端看不到，
或者角色已经是 `job=232` 且等级大于 180 仍然没有新技能，优先检查数据库。

原因：

```text
技能栏显示不是只看 WZ。
客户端技能栏会显示角色已经学会的技能，服务端登录时会从数据库 skills 表加载技能。
复制客户端、JAR、服务端 wz 文件不会自动给已有角色补 skills 表记录。
```

当前 232 方案需要补的技能 ID：

```text
2321010-2321018
```

### 电脑端补数据库

如果本机服务端配置仍是默认值，可以直接连接：

```text
数据库：beidou
账号：root
密码：root
```

也可以先看 `gms-server/src/main/resources/application.yml` 里的 `spring.datasource.url`，
确认真实数据库名，例如：

```text
jdbc:mysql://localhost:3306/beidou?...
```

进入 MySQL/MariaDB 后，先查角色：

```sql
SELECT id, name, job, level FROM characters WHERE name = 'Admin';
```

角色确认是 `job=232` 且 `level>180` 后，补技能：

```sql
INSERT INTO skills (characterid, skillid, skilllevel, masterlevel, expiration)
SELECT c.id, s.skillid, 30, 30, -1
FROM characters c
JOIN (
    SELECT 2321010 AS skillid UNION ALL
    SELECT 2321011 UNION ALL
    SELECT 2321012 UNION ALL
    SELECT 2321013 UNION ALL
    SELECT 2321014 UNION ALL
    SELECT 2321015 UNION ALL
    SELECT 2321016 UNION ALL
    SELECT 2321017 UNION ALL
    SELECT 2321018
) s
WHERE c.name = 'Admin'
  AND c.job = 232
  AND c.level > 180
ON DUPLICATE KEY UPDATE
    skilllevel = VALUES(skilllevel),
    masterlevel = VALUES(masterlevel),
    expiration = VALUES(expiration);
```

验证：

```sql
SELECT s.skillid, s.skilllevel, s.masterlevel
FROM characters c
JOIN skills s ON s.characterid = c.id
WHERE c.name = 'Admin'
  AND s.skillid BETWEEN 2321010 AND 2321018
ORDER BY s.skillid;
```

能看到 `2321010` 到 `2321018` 共 9 行，就说明数据库已经补好。
角色需要离线后重新登录；如果服务端已经启动，建议重启服务端再进游戏验证。

### 手机 ZeroTermux / MariaDB 补数据库

打开 ZeroTermux 后，如果出现一键启动台，不要输入 `1`，直接回车进入普通命令行。
先单独启动数据库：

```bash
mysqld_safe &
sleep 3
```

教程里的数据库名是 `beidou`，账号密码是 `root/root`，进入数据库：

```bash
mariadb -u root -proot beidou
```

如果不支持 `-proot`，用交互密码：

```bash
mariadb -u root -p beidou
```

然后输入：

```text
root
```

进入 MariaDB 后执行和电脑端相同的查询、插入、验证 SQL。

如果手机端插完仍然看不到，按下面顺序查：

```text
1. 插入的是不是手机服务端实际连接的 beidou 数据库。
2. 角色是否已经离线并重新登录，必要时重启 Java 服务端。
3. 手机端运行的 BeiDou.jar 是否是最新打包后的 JAR。
4. 手机客户端 clien/Data/Skill/232.img 是否是替换后的新文件。
5. 手机客户端 clien/Data/String/Skill.img 是否包含 2321010-2321018 描述。
6. 服务端目录下 wz/Skill.wz/232.img.xml 和 wz/String.wz/Skill.img.xml 是否也是新文件。
```

## 实战记录：1121001 磁石改造成轻舞飞扬式攻击

这次目标不是新增一个空白技能，而是复用英雄 4 转已有技能位：

```text
原技能：1121001，英雄 Monster Magnet / 磁石
目标：改造成轻舞飞扬式近战攻击
显示名：测试
行为参考：1121008，轻舞飞扬 / Brandish
最终验证：技能面板可见，双击/按键可释放，有技能动作、攻击表现和伤害
```

### 最终结论

这次真正的问题不在 WZ 数据层，而在 `BeiDou.exe` 的技能分派逻辑。

```text
1. 只把 1121001 的 WZ 节点复制成 1121008，不够。
   客户端技能面板可以显示，但释放时仍可能按原磁石逻辑走。

2. 只把 1121001 从磁石 hardcode 中移除，也不够。
   这一步只能阻止它继续被当成 Monster Magnet，
   但不会自动让它进入 Brandish / 轻舞飞扬分支。

3. 必须把 1121001 追加进 1121008 已验证可用的 exe 分支。
   不能把 1121008 替换成 1121001，否则原轻舞飞扬会坏。
   正确做法是 code cave 追加判断：
   if skill == 1121001 or skill == 1121008 -> 走同一个分支。
```

### 数据层改造

客户端技能数据：

```text
clien/Data/Skill/112.img
```

把 `skill/1121001` 克隆为 `skill/1121008` 的结构，最终关键节点一致：

```text
children:
  action
  effect
  hit
  icon
  iconDisabled
  iconMouseOver
  level
  masterLevel

action:
  0 = brandish1
  1 = brandish2

level/30:
  attackCount = 2
  damage = 280
  lt = (-250, -110)
  mobCount = 4
  mpCon = 25
  rb = (100, 50)

masterLevel = 10
```

客户端 String：

```text
clien/Data/String/Skill.img
```

把 `1121001` 改成：

```text
name = 测试
desc = 连续攻击2次前面的敌人。
h30 = 消耗MP 25 , 伤害 280%, 4名攻击
```

服务端 XML 同步：

```text
gms-server/wz/Skill.wz/112.img.xml
gms-server/wz/String.wz/Skill.img.xml
gms-server/wz-zh-CN/String.wz/Skill.img.xml
```

服务端 XML 也要确保 `1121001` 和 `1121008` 的攻击参数一致，否则客户端能释放，
服务端也可能因为 `mobCount/attackCount/lt/rb` 不一致而校验失败。

### 服务端逻辑改造

原来服务端多处把 `Hero.MONSTER_MAGNET` 当成磁石特殊技能处理。
既然 `1121001` 已经被改成普通近战攻击，就要从这些磁石分支移除：

```text
gms-server/src/main/java/org/gms/client/SkillFactory.java
gms-server/src/main/java/org/gms/net/server/channel/handlers/SpecialMoveHandler.java
gms-server/src/main/java/org/gms/net/server/channel/handlers/SkillEffectHandler.java
```

最终状态：

```text
SkillFactory:
  Monster Magnet 相关 hardcode 只保留 Paladin / DarkKnight。

SpecialMoveHandler:
  Monster Magnet 特殊处理只保留 1221001 / 1321001。

SkillEffectHandler:
  1121001 不再作为 SKILL_EFFECT 特殊技能处理。
  如果测试时仍出现 entered SkillEffectHandler without being handled using 1121001，
  说明客户端还没有走近战攻击包。
```

近战攻击服务端校验中，把 1121001 加到 Brandish 同类距离余量：

```java
attack.skill == Hero.BRANDISH || attack.skill == Hero.MONSTER_MAGNET
```

注意：这里仍然沿用常量名 `Hero.MONSTER_MAGNET`，因为常量文件里 ID 名称未改。
语义上它现在代表被改造后的 `1121001` 测试技能。

### exe 编码检查

技能 ID 在 `BeiDou.exe` 中通常是 32 位小端整数：

```text
1121001 = 0x111ae9 = e9 1a 11 00
1121008 = 0x111af0 = f0 1a 11 00
1121099 = 0x111b4b = 4b 1b 11 00
1221001 = 0x12a189
1321001 = 0x142829
```

扫描命令：

```bash
rtk node -e 'const fs=require("fs"); const b=fs.readFileSync("clien/BeiDou.exe"); for(const id of [1121001,1121008,1121099,1221001,1321001]){const p=Buffer.alloc(4); p.writeUInt32LE(id>>>0,0); const a=[]; for(let i=0;(i=b.indexOf(p,i))>=0;i++) a.push(i); console.log(id,a.length,a.map(x=>"0x"+x.toString(16)).join(" "));}'
```

修复前的关键现象：

```text
1121001 原本只出现在磁石三职业硬编码附近。
1121008 另外有 5 个 Brandish / 轻舞飞扬分支。
把 1121001 改成 1121099 后，1121001 在 exe 里为 0 次。
这说明它不再是磁石，但也没有被加入轻舞飞扬逻辑。
```

这就是“数据像轻舞飞扬，但逻辑不像轻舞飞扬”的根因。

### exe 第一阶段：移除英雄磁石分支

脚本：

```text
tool/scripts/patch-client/patch_1121001_not_magnet.py
```

作用：

```text
把 Hero 1121001 的 14 个 Monster Magnet 判断改成 1121099。
Paladin 1221001 和 DarkKnight 1321001 保持不变。
```

这样做的目的不是让 1121001 变成攻击技能，而是先让客户端不要再把它当成磁石。

验证结果应该类似：

```text
1121001 LE 0
1121099 LE 14
1221001 LE 13/14，保持存在
1321001 LE 13/14，保持存在
```

### exe 第二阶段：追加进 Brandish 分支

脚本：

```text
tool/scripts/patch-client/patch_1121001_as_brandish.py
```

作用：

```text
把 1121001 追加到 1121008 的 5 个客户端分支。
保留 1121008 原逻辑，不替换原技能。
```

本次识别到的 1121008 分支：

```text
0x933ABF  Brandish skill branch
0x950DE5  Brandish action type
0x95255A  Brandish visual offset
0x967A10  Brandish state switch
0x78E9D6  Brandish hit randomization
```

补丁使用 code cave：

```text
code cave VA     = 0x00AEFB00
code cave offset = 0x006EFB00
```

避开已有 cave：

```text
0x00AEF602  2121006 AoE hook 使用
0x00AEFA20  WzFileLogger startup hook 使用
```

补丁逻辑示例：

```asm
cmp esi, 1121001
je  brandish_target
cmp esi, 1121008
je  brandish_target
jmp original_continue
```

其中 `0x967A10` 这一处要特别注意：

```text
原逻辑里有跨较远地址的 jg。
不能用 2 字节 short jg，否则跳转距离装不下，会跳到错误位置。
脚本必须使用 6 字节 near jg：0F 8F rel32。
```

这个坑已经踩过一次。反汇编正确结果应看到：

```asm
aefb66: 0f 8f 08 7f e7 ff    jg 0x967a74
```

### exe 补丁验证

执行 dry-run：

```bash
rtk python3 tool/scripts/patch-client/patch_1121001_as_brandish.py --dry-run
```

已补好时输出：

```text
BeiDou.exe already routes 1121001 through Brandish logic.
```

扫描 ID：

```text
1121001 5  只出现在新 code cave 里
1121008 5  同样在新 code cave 里保留
1121099 14 原英雄磁石分支哨兵
```

反汇编关键位置：

```bash
rtk objdump -d --triple=i386-pc-windows-msvc --x86-asm-syntax=intel \
  --start-address=0xaefb00 --stop-address=0xaefbb8 clien/BeiDou.exe
```

应能看到 `0x111ae9` 和 `0x111af0` 都跳向同一个 Brandish 目标。

### 成功前后的症状对照

失败阶段 1：技能面板不显示。

```text
优先查 WZ/String/服务端 skills 数据库。
本次后来已确认面板显示不是核心问题。
```

失败阶段 2：面板显示，双击只走两步，没有攻击和特效。

```text
服务端日志出现：
entered SkillEffectHandler without being handled using 1121001

含义：
客户端发的是 SKILL_EFFECT，不是 CLOSE_RANGE_ATTACK。
这说明它仍然不在普通近战攻击释放路径里。
服务端无法从 SKILL_EFFECT 包里得到目标和伤害列表。
```

失败阶段 3：服务端兜底能进，但 targets=0。

```text
这只能证明服务端收到 1121001 了，不代表客户端逻辑正确。
服务端伪造伤害可以临时验证，但不应该作为最终方案。
最终要让 exe 发 CLOSE_RANGE_ATTACK。
```

最终成功判断：

```text
1. 不再出现 SkillEffectHandler 未处理 1121001。
2. 客户端释放时有 brandish1/brandish2 动作。
3. 客户端上报近战攻击包。
4. 服务端 CloseRangeDamageHandler 正常 applyAttack。
5. 怪物出现 hit/伤害/扣血。
```

### 这次最重要的经验

```text
1. WZ 决定技能长什么样、参数是什么；exe 决定客户端把技能当成什么类型释放。

2. 把磁石数据改成攻击技能，只解决数据层，不会自动改变 exe 中的技能类型。

3. 解除旧类型和接入新类型是两件事：
   - 1121001_not_magnet：解除 Monster Magnet。
   - 1121001_as_brandish：接入 Brandish。

4. 服务端兜底可以帮助定位包流向，但最终要删除或停用。
   否则会掩盖 exe 是否真的发了正确攻击包。

5. 修改 exe 时必须保留旧技能。
   1121008 仍然要能用，所以只能追加 1121001 判断，不能直接替换 1121008。

6. 每一个 hook 都要 dry-run、检查原始字节、反汇编验证跳转目标。
   特别是 short jump 和 near jump 的区别，不能靠感觉。
```

## 实战记录：1121001 从轻舞飞扬式攻击继续迁移为剑影分身

这次是在上一节基础上继续做的二次改造。`1121001` 已经不是原生磁石，
而是一个能够进入 Brandish / 轻舞飞扬近战攻击路径的测试技能。
新目标是把它做成英雄 5 转技能 `剑影分身` 的表现和参数。

```text
源技能：40001.img / 400011124
来源目录：/Users/lizixian/Documents/mxd/skill-273-export/
目标技能：112.img / 1121001
目标职业：英雄 112
目标名称：剑影分身
原始技能位：Hero.MONSTER_MAGNET / 1121001
最终路径：继续复用 Brandish 攻击包路径，额外播放剑影分身 effect0 二段表现
```

### 最终涉及文件

```text
客户端技能 WZ：
  clien/Data/Skill/112.img
  clien/Data/String/Skill.img

服务端技能 XML：
  gms-server/wz/Skill.wz/112.img.xml
  gms-server/wz/String.wz/Skill.img.xml

客户端 EXE 补丁：
  clien/BeiDou.exe
  tool/scripts/patch-client/patch_1121001_as_brandish.py

资源同步脚本：
  tool/scripts/patch-skill/patch_1121001_sword_illusion.py

服务端命中时序和反伤处理：
  gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java
  gms-server/src/main/java/org/gms/net/server/channel/handlers/AbstractDealDamageHandler.java
```

### 参数来源

用户提供的是 1 级官方文本：

```text
MP消耗700，发动12次以130%的伤害最多攻击8名敌人4次的斩击后，
发动5次以260%的伤害攻击5次的爆炸
斗气集中激活期间，在8秒内，和增加6个斗气点数的最终伤害相同数值的最终伤害增加，
与斗气点数增加的最终伤害合计应用
```

实际数据层采用脚本生成：

```text
等级：1-30
MP：700
damage：130 + (level - 1) * 5
attackCount：4
mobCount：8
描述文字：每级 +5% 递增
```

注意：官方文本里还有第二段爆炸 `260% * 5`，但当前旧客户端和服务端的 1121001
仍然走 Brandish 近战攻击包，只有一组 `damage/attackCount/mobCount/lt/rb`。
所以目前服务端实际伤害使用第一段 `damage/attackCount`，第二段主要通过视觉和命中时序还原。
如果后续要严格拆成两段不同倍率，需要继续改攻击包或服务端二段结算模型。

### WZ 节点结构

源 `400011124` 不是旧 4 转技能结构，关键表现节点是：

```text
effect   = 前摇特效，本身不应该造成伤害
effect0  = 攻击特效，真正的斩击/爆炸视觉
```

目标 `1121001` 最终整理成：

```text
action:
  0 = brandish1
  1 = brandish2
  2 = brandish1

effect:
  0 = 源 effect 的 Brandish 兼容 variant
  1 = 源 effect 的 Brandish 兼容 variant
  2 = 源 effect0 的兼容镜像

effect0:
  保留源 effect0，作为资源真实来源和后续参考
```

为什么要把 `effect0` 镜像到 `effect/2`：

```text
1. 老客户端没有直接按字符串 "effect0" 自动加载新增节点。
2. 直接新增 skill/1121001/effect0 不代表释放时会播放。
3. Brandish 路径会按 action/effect index 选择 effect/%d。
4. 所以把 effect0 镜像成 effect/2，再让 EXE 额外选择 index=2 播放。
```

### effect0 延迟

剑影分身的正常观感是：

```text
先播放 effect 前摇
约 1 秒后播放 effect0 攻击特效
第二段出现时才命中
```

EXE hook 当前是在 Brandish 视觉出口立即播放 `effect/2`。
为了不继续扩大 EXE 改动，延迟放在 WZ 资源层实现：

```text
effect0/0  = 1x1 透明 canvas，delay=1000
effect0/1  = 原 effect0 第 0 帧
effect0/2  = 原 effect0 第 1 帧
...

effect/2/0 = 同样的 1x1 透明 delay 帧
effect/2/1 = 原 effect0 第 0 帧
...
```

当前验证结果：

```text
effect0 frames 48
  0 1x1 origin (0, 0) delay 1000
  1 720x448 origin (40, 344) delay 30

effect/2 frames 48
  0 1x1 origin (0, 0) delay 1000
  1 720x448 origin (40, 344) delay 30
```

这能让 EXE 继续立即启动 `effect/2`，但真实可见的二段动画晚 1 秒出现。

### EXE 兼容路径

脚本：

```text
tool/scripts/patch-client/patch_1121001_as_brandish.py
```

上一阶段已经把 `1121001` 接入 Brandish 攻击逻辑。
剑影分身阶段继续在同一个脚本里追加了 `effect/2` 攻击视觉：

```text
code cave VA     = 0x00AEFB00
code cave size   = 0x180
关键 hook        = 0x00934720 Brandish visual exit effect0
```

逻辑概要：

```text
1. 正常 Brandish 保持原出口。
2. 如果 skill id 是 1121001：
   - 释放当前 effect 资源。
   - 调用 0x00932D40，选择 effect index = 2。
   - 把 effect/2 播放到普通角色 effect layer。
   - 方向用 xor 1 修正，因为源 effect0 和旧客户端朝向相反。
3. 回到原 Brandish 视觉出口。
```

踩过的坑：

```text
1. 直接搜索 ASCII "effect0" 没用。
   老客户端这条路径不是按字符串找 effect0，而是按固定资源槽/编号 effect/%d。

2. 直接尝试播放 [ebx+0x1144] 的 effect0 不稳定。
   资源可能没有按预期加载，曾经出现数据错误和崩溃。

3. 最稳定方案是让 WZ 自己提供 effect/2，
   EXE 只负责选择 index=2，这样沿用原有 effect 播放结构。

4. 方向一开始反了。
   最后在 EXE 播放前对方向参数 xor 1。

5. 位置一开始挡角色、偏下、离角色太远。
   最后在资源脚本里统一改 effect0 origin，而不是在 EXE 里继续猜坐标。
```

当前 dry-run 成功提示：

```text
BeiDou.exe already routes 1121001 through Brandish attack logic and effect/2 attack visual.
```

### effect0 位置

位置调整集中在资源脚本常量：

```text
MERGED_EFFECT0_FORWARD_OFFSET = -40
MERGED_EFFECT0_UP_OFFSET = 120
```

脚本会遍历二段直接动画帧，修改每一帧 origin：

```text
origin.x = origin.x - forward_offset
origin.y = origin.y + up_offset
```

最终当前二段真实帧前几项：

```text
frame 1 origin = (40, 344)
frame 2 origin = (40, 348)
```

效果调试过程中的现象：

```text
1. 能攻击但没有技能效果：
   说明攻击逻辑通了，视觉资源没被正确播放。

2. effect 可见，effect0 不可见：
   说明普通 effect 路径通了，但 effect0 没有被客户端分支读取。

3. 第二段特效方向相反：
   源 effect0 面向和当前 Brandish 播放方向相反，需要 EXE xor 1。

4. 第二段离人物太远：
   不是攻击框问题，而是 canvas origin 和播放层锚点问题。
```

### 伤害时序

视觉修好后又出现一个语义问题：

```text
effect 是前摇，本身不应该命中。
effect0 才是攻击特效，应该在二段出现时命中。
```

客户端仍然走 Brandish 攻击包，攻击包发送时机更接近一段动作。
为了让实际扣血、死亡和掉落尽量落在二段窗口，服务端对 `1121001` 做了 1 秒延迟：

```java
private static final int SWORD_ILLUSION_HIT_DELAY_MS = 1000;

if (attack.skill == Hero.MONSTER_MAGNET) {
    final int delayedAttackCount = attackCount;
    TimerManager.getInstance().schedule(() -> applyAttack(attack, chr, delayedAttackCount), SWORD_ILLUSION_HIT_DELAY_MS);
} else {
    applyAttack(attack, chr, attackCount);
}
```

文件：

```text
gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java
```

注意边界：

```text
1. 这解决的是服务端真实伤害时机。
2. 如果旧客户端本地提前显示了某些命中数字，那是客户端本地表现问题。
3. 要完全从客户端层面改变攻击包发送时机，需要更深的 EXE 攻击动作/命中帧改造。
```

### 反伤免疫

官方说明里写明：

```text
剑影分身即使攻击反射状态的敌人也不会受到伤害。
```

服务端因此对 `1121001` 跳过反伤扣血：

```java
if (monster.isBuffed(MonsterStatus.WEAPON_REFLECT) && !attack.magic && attack.skill != Hero.MONSTER_MAGNET) {
    ...
}

if (monster.isBuffed(MonsterStatus.MAGIC_REFLECT) && attack.magic && attack.skill != Hero.MONSTER_MAGNET) {
    ...
}
```

文件：

```text
gms-server/src/main/java/org/gms/net/server/channel/handlers/AbstractDealDamageHandler.java
```

这里仍然使用 `Hero.MONSTER_MAGNET` 常量名，因为常量文件还没有重命名。
语义上它现在是英雄测试技能 `1121001`。

### 攻击范围

一开始攻击范围沿用了迁移时的粗大范围：

```text
lt = (-530, -370)
rb = (930, 280)
```

后面确认用户想要“攻击范围是整个二段动画的范围”，于是按 `effect0` 所有真实帧计算 union。
透明 delay 帧不参与范围：

```text
effect0 union = (-40, -366, 700, 126)
```

最终写入：

```text
level/*/lt = (-40, -366)
level/*/rb = (700, 126)
```

当前抽查：

```text
level/1 lt = (-40, -366)
level/1 rb = (700, 126)
effect0 union = (-40, -366, 700, 126)
```

这个范围同时写入客户端 `112.img` 和服务端 `112.img.xml`。
服务端距离校验会使用同一组 `lt/rb`，避免客户端能打到但服务端判越界。

### 为什么没有继续改成 Meteor / 天降落星路径

调试时参考过 `2121007` 天降落星：

```text
action = meteor
effect
effect0
hit
tile
```

它更像“先播前摇，再播真正攻击效果”的技能。
但是完全切换到 Meteor 路径风险更高：

```text
1. 1121001 当前已经验证能走 Brandish 近战攻击包。
2. Meteor 是魔法/范围技能路径，目标选择、封包结构和表现层都不同。
3. 直接换路径可能重新引入 targets=0、SkillEffectHandler、或服务端校验不一致的问题。
```

所以本次最终选择：

```text
攻击包：继续 Brandish 近战路径
前摇视觉：effect/0、effect/1
攻击视觉：effect0 镜像到 effect/2
二段延迟：WZ 透明 delay 帧
真实伤害：服务端 applyAttack 延迟 1000ms
范围：effect0 真实帧 union
```

### 调试顺序建议

以后再迁移类似“新版本技能到旧客户端职业技能位”，按这个顺序排查：

```text
1. 先确认技能面板和字符串。
   clien/Data/String/Skill.img
   gms-server/wz/String.wz/Skill.img.xml

2. 再确认服务端技能参数。
   level/damage/attackCount/mobCount/mpCon/lt/rb

3. 确认客户端发的是哪类包。
   如果进 SkillEffectHandler，说明不是攻击包。
   如果进 CloseRangeDamageHandler 但 targets=0，说明客户端选择目标失败。

4. 确认 EXE 是否把目标 ID 接入了正确的技能分支。
   WZ 数据改对不等于 EXE 分派改对。

5. 视觉缺失时先判断是 effect 不显示，还是 effect0 不显示。
   effect 显示而 effect0 不显示，通常是客户端没有读取 effect0。

6. effect0 不显示时，不要先猜 WZ 坏了。
   先找已有会播放 effect0 的技能或把 effect0 做成 effect/%d 兼容分支。

7. 有特效但崩溃或数据错误时，优先回退到旧客户端已经会加载的资源结构。
   本次就是从直接 effect0 槽位回退到 effect/2。

8. 有特效但位置不对时，优先调 canvas origin。
   EXE 坐标层更难确认，资源层更可控。

9. 视觉时序和伤害时序分开处理。
   视觉可以通过 WZ delay 解决，真实伤害可以通过服务端 TimerManager 延迟。

10. 攻击范围最后按最终攻击视觉重新计算。
    先做视觉，再定 lt/rb，否则很容易范围和画面不一致。
```

### 验证命令

资源补丁：

```bash
rtk python3 tool/scripts/patch-skill/patch_1121001_sword_illusion.py --dry-run
rtk python3 tool/scripts/patch-skill/patch_1121001_sword_illusion.py
```

EXE 补丁：

```bash
rtk python3 tool/scripts/patch-client/patch_1121001_as_brandish.py --dry-run
```

客户端 WZ 抽查重点：

```text
skill/1121001/effect/0
skill/1121001/effect/1
skill/1121001/effect/2
skill/1121001/effect0
skill/1121001/action/2
skill/1121001/level/1/lt
skill/1121001/level/1/rb
```

期望状态：

```text
effect0 frames = 48
effect0/0      = 1x1 transparent delay 1000
effect/2       = effect0 compat mirror
action/2       = brandish1
level/*/lt     = (-40, -366)
level/*/rb     = (700, 126)
```

编译检查注意：

```text
如果本机是 Java 17，而 Maven target 是 21，会报：
无效的目标发行版：21

这不是本次代码改动导致的语法错误，需要 Java 21 环境才能完整 compile。
```

### 本次踩坑总结

```text
1. 不要在错误资源包里找太久。
   神说的 5 转技能面板是独立体系，ID 和 UI 体系不同；
   后续明确用 skill-273-export / 40001.img / 400011124 作为源。

2. 新增 effect0 节点不会自动播放。
   客户端必须有对应技能逻辑读取它。

3. 直接改 EXE 播 effect0 容易崩。
   资源没加载、槽位不对、引用为空，都可能导致数据错误。

4. 兼容旧客户端时，effect/%d 比 effect0 字符串路径更稳。
   本次用 effect/2 作为二段攻击视觉入口。

5. 方向和位置是两个问题。
   方向在 EXE 播放参数里修，位置在 WZ origin 里修。

6. 延迟不能全部做到 effect 上。
   effect 是前摇，effect0 才是攻击特效；
   把二段硬合并到 effect 会让语义和调试都变混乱。

7. 视觉延迟和伤害延迟要同时处理。
   只延迟 effect0，真实伤害仍可能提前；
   只延迟服务端伤害，玩家可能看不到对应二段表现。

8. 攻击范围必须跟最终二段视觉对齐。
   不能用迁移初期的大概范围长期保留。

9. 反伤免疫是技能语义的一部分。
   只迁移视觉和伤害，不处理反伤，会和官方说明不一致。
```

## 踩坑清单

这次比较值得记住的坑：

```text
1. WZ 有节点不等于客户端会释放。
   客户端还有本地技能类型分派，新增 ID 往往要补 EXE 判断。

2. 不能把旧技能 ID 直接替换成新技能 ID。
   这样会让旧技能失效。正确做法是 code cave 里追加新技能判断。

3. 技能栏可见不代表释放路径正确。
   “能学习、能绑键、按键没反应”优先怀疑释放/动作分类 hook。

4. hit 延迟不一定是服务端问题。
   这次 action=genesis 加完整 Dragon effect 会出现先播完大特效再出 hit。
   改成 action=paralyze、移除 effect0 后，effect 和 hit 才回到同时播放的表现。

5. 技能 tab 比攻击逻辑更难稳定。
   新增第 5/V tab 会牵涉循环上限、布局槽位、职业分类、当前页字段等多处 UI 逻辑。
   已验证可行的方案是继续放 4 转 tab，并用排序和服务端等级门槛控制体验。

6. 外部 Dragon/_Canvas 不是完整技能文件。
   它主要是动作帧素材，缺完整 skill 节点、icon、等级数据和客户端释放分类。
   所以要么克隆已有技能结构，要么补齐所有必要节点。

7. 生成图标时不要直接复用 2321003 图标。
   否则多个新技能在技能栏里都像强化圣龙，不利于测试和玩家辨认。

8. WZ key/region 不能混用。
   本地客户端按 GMS，外部素材按 BMS；读写 key 错了很容易出现 canvas 异常。

9. dry-run 和 objdump 验证很重要。
   脚本先 dry-run，再反汇编确认 hook bytes；游戏内验证再看自己视角、他人视角和实际命中。

10. README 要记录失败方案。
    V tab 虽然最终没采用，但保留失败路径和地址记录，后面再查不会重复踩同一个坑。
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

## Skill screen 节点兼容

目标：让老客户端能吃到技能 WZ 里的 `screen` 类节点，并继续走当前稳定的技能 effect 播放链路。

结论：

```text
老 BeiDou.exe 没有现代客户端那套 skill screen 字符串/资源槽。
直接给技能对象扩 screen/screen0/screen1/screen2 槽位，需要改加载结构和析构引用计数，风险太高。
当前采用兼容镜像：

screen  -> effect/90
screen0 -> effect/91
screen1 -> effect/92
screen2 -> effect/93
```

EXE hook：

```text
脚本：tool/scripts/patch-client/patch_skill_screen_effect_slots.py
hook：0x009358EE
cave：0x00AEFD80

普通技能 effect 播放完成后，依次尝试 effect/90..93。
资源不存在就跳过；存在则调用旧客户端已有的 effect selector 0x00932D40，
再走原本稳定的角色 effect layer 播放路径。
```

资源镜像：

```text
脚本：tool/scripts/patch-skill/patch_skill_screen_effect_slots.py

默认不会扫描所有 Skill/*.img，必须指定技能。
确实要全量扫描时再显式加 `--all`：

rtk python3 tool/scripts/patch-skill/patch_skill_screen_effect_slots.py 1121001
rtk python3 tool/scripts/patch-skill/patch_skill_screen_effect_slots.py --all
```

当前仓库实际命中的旧 screen 技能：

```text
0001009, 0001020
10001009, 10001020
20001009, 20001020

这些是现有流星竹雨/法老王技能，本来已经能正常释放。
它们的 effect 下已有普通动画帧 10..13，不能拿这些编号做 screen 镜像。
已回滚对这些既有技能的 WZ 镜像改动；后续只对目标新技能显式执行脚本。
```

验证：

```text
rtk python3 tool/scripts/patch-client/patch_skill_screen_effect_slots.py --dry-run
=> BeiDou.exe already plays migrated skill screen effect slots.

rtk python3 tool/scripts/patch-skill/patch_skill_screen_effect_slots.py --dry-run
=> no skill ids supplied; pass explicit ids or --all to mirror screen nodes
```

限制：

```text
这不是现代客户端的原生 screen 对象布局，而是 screen 节点的兼容镜像。
播放层复用旧客户端当前稳定的 effect layer；如果某个 screen 资源必须严格按屏幕坐标/全屏遮罩表现，
仍可能需要把资源做成适合 effect layer 的全屏画布，或继续走 Map/Effect.img + FIELD_EFFECT 的服务端广播方案。
```

## 当前参考文件

- `docs/patches/2121006-aoe-analysis.md`
- `tool/scripts/patch-client/patch_2121006_exe_aoe.js`
- `tool/scripts/patch-skill/patch_2121006_aoe.py`
- `clien/BeiDou.exe`
- `clien/Data/Skill/<job>.img`
- `gms-server/wz/Skill.wz/<job>.img.xml`
