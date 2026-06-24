# 2121006 群攻补丁分析记录

本文记录把 `2121006`（火毒 4 转 Paralyze）从单体改成群攻的分析过程、客户端
`BeiDou.exe` 里的相关代码结构、数据层修改、exe hook 修改、验证方法和后续改其它技能时
的参考步骤。

## 最终结论

只给 `212.img` 和 `212.img.xml` 补 `mobCount` 不够。`2121006` 在 `BeiDou.exe` 里没有进入
矩形 AoE 选怪分支，客户端封包仍只会上报 1 个目标。

最终需要两层一起改：

1. 数据层：给客户端 `clien/Data/Skill/212.img` 和服务端
   `gms-server/wz/Skill.wz/212.img.xml` 的 `2121006/level/1..30` 补：
   - `mobCount = 6`
   - `lt = (-300, -100)`
   - `rb = (0, 20)`
2. exe 层：把 `2121006` 加入 `BeiDou.exe` 里已有的矩形 AoE 处理分支。

实际测试结果：补完数据和 exe hook 后，`2121006` 已可一次命中多只怪。

## 相关文件

- 客户端数据：`clien/Data/Skill/212.img`
- 服务端数据：`gms-server/wz/Skill.wz/212.img.xml`
- 客户端程序：`clien/BeiDou.exe`
- 数据补丁脚本：`tool/scripts/patch_2121006_aoe.py`
- exe 补丁脚本：`tool/scripts/patch_2121006_exe_aoe.js`

补丁生成的备份：

- `clien/Data/Skill/212.img.bak-2121006-aoe`
- `gms-server/wz/Skill.wz/212.img.xml.bak-2121006-aoe`
- `clien/BeiDou.exe.bak-2121006-exe-aoe`

## 一、先排除数据层问题

一开始误以为目标技能是 `2121001`，后面确认真正要改的是 `2121006`。重新抽取
`2121006` 后发现：

- `2121006` 原始 XML 里有 30 个 `attackCount=2`
- 原始 XML 里没有任何 `mobCount`
- 原始 XML 里没有任何 `lt/rb`
- 客户端 `212.img` 导出的 JSON 也一样，没有 `mobCount/lt/rb`

服务端 `StatEffect` 读取 `mobCount` 的默认值是 1：

```java
ret.mobCount = DataTool.getInt("mobCount", source, 1);
```

攻击处理里还会校验客户端上报的目标数：

```java
if (attack.numAttacked > mobCount) {
    AutobanFactory.MOB_COUNT.autoban(...);
    return;
}
```

所以数据层必须补，否则客户端即使能上报多目标，服务端也会按最多 1 只处理。

但用户测试发现补 `mobCount` 后仍只打 1 只，说明客户端 exe 本身仍只选择 1 个目标。

## 二、技能 ID 和 exe 搜索方法

`2121006` 的十六进制是：

```text
2121006 decimal = 0x205d2e
little-endian bytes = 2e 5d 20 00
```

用脚本扫描 `BeiDou.exe` 里的技能 ID：

```bash
rtk node - <<'NODE'
const fs=require('fs');
const buf=fs.readFileSync('clien/BeiDou.exe');
function scan(hex){
  const needle=Buffer.from(hex,'hex');
  const hits=[];
  for(let i=0;(i=buf.indexOf(needle,i))>=0;i++){
    hits.push(i);
    i+=needle.length-1;
  }
  return hits;
}
for(const [id,hex] of [[2121006,'2e5d2000'],[2121003,'2b5d2000'],[2121007,'2f5d2000'],[2221006,'cee32100']]) {
  console.log(id, scan(hex).map(x=>'0x'+x.toString(16)).join(' '));
}
NODE
```

当时结果里 `2121006` 只出现两处：

```text
2121006: 0x3658d1 0x555804
```

`0x555804` 换成虚拟地址是 `0x955804`，位于魔法攻击处理的大函数附近。

## 三、PE 地址换算

此 exe 的 `.text` 段满足：

```text
ImageBase = 0x400000
.text raw offset = 0x1000
.text VA = 0x401000
VA - file offset = 0x400000
```

因此在 `.text` 内：

```text
file offset = VA - 0x400000
VA = file offset + 0x400000
```

例如：

```text
VA 0x955d0e -> file offset 0x555d0e
VA 0xaef602 -> file offset 0x6ef602
```

## 四、exe 中相关代码结构

### 1. `0x955803` 附近：技能动作/分类，不是最终 AoE 选怪

`2121006` 在这里被硬编码识别：

```asm
955803: sub eax, 0x205d2e
95580e: je  0x95598d
...
95598d: mov dword ptr [ebp - 0x28], 0x43
```

这里会给 `2121006` 设置一个内部动作/分类值 `0x43`。这不是最终“打几只”的逻辑，
只改这里不能让技能变群攻。

### 2. `0x955b02` 以后：读取技能数据和攻击范围

这一段会读取技能数据里的若干字段，包括目标数、攻击段数、范围等：

```asm
955b42: push dword ptr [esi + 0x138]
955b48: lea eax, [esi + 0x130]
955b4f: call 0x416563
...
955b64: push dword ptr [esi + 0x108]
955b6a: sub eax, dword ptr [ebp + 0x10]
955b74: mov dword ptr [ebp - 0x90], eax
...
955b87: push 0xf
955b8a: cmp eax, ecx
955b8c: mov dword ptr [ebp - 0x64], eax
```

结合后续封包写入：

```asm
956dcf: mov al, byte ptr [ebp - 0x2c]
956dd2: shl al, 0x4
956dd5: or  al, byte ptr [ebp - 0x64]
```

可推断：

- `[ebp - 0x2c]` 是本次攻击选中的怪物数量 `numAttacked`
- `[ebp - 0x64]` 是每只怪的伤害段数 `numDamage`
- `[ebp - 0x90]` 在 AoE 选怪调用中作为最大目标数相关参数使用

### 3. `0x955d0e` 附近：已有矩形 AoE 技能列表

这里是一个硬编码技能列表。命中的技能会跳到 `0x956372`，也就是矩形 AoE 处理路径。

原始开头是：

```asm
955d0e: cmp eax, 0x2195ad   ; 2201005, ILWizard.THUNDERBOLT
955d13: je  0x956372
955d19: cmp eax, 0x231c4a   ; 2301002, Cleric.HEAL
955d1e: je  0x956372
955d24: cmp eax, 0x20361a   ; 2111002, FPMage.EXPLOSION
955d29: je  0x956372
...
```

列表中能看到很多本来就是群攻或矩形范围技能的 ID，例如：

- `2201005` Thunder Bolt
- `2301002` Heal
- `2111002` Explosion
- `2211002` Ice Strike
- `2311004` Shining Ray
- `2121001` Big Bang
- `2121003` Fire Demon
- `2121007` Meteor
- `2221006` Chain Lightning / 类似多目标技能
- 若干骑士团和 Evan 技能

原始列表里没有 `2121006`，这就是只补 WZ 数据仍只打 1 只的核心原因。

### 4. `0x956372`：矩形 AoE 处理路径

命中硬编码 AoE 列表后会进入这里：

```asm
956372: push dword ptr [ebp + 0xc]
956375: mov ecx, dword ptr [ebp + 0x8]
956378: call 0x760f23
...
956567: push edi
956568: push esi
956569: lea eax, [ebp - 0x58]
95656c: push eax
95656d: call dword ptr [0xbf0454]
...
9565a1: mov ecx, dword ptr [0xbebfa4]
9565a7: xor edi, edi
9565a9: push edi
9565aa: push edi
9565ab: push edi
9565ac: push edi
9565ad: push edi
9565ae: push dword ptr [ebp - 0x90]
9565b4: lea eax, [ebp - 0x11c]
9565ba: push eax
9565bb: lea eax, [ebp - 0x58]
9565be: push eax
9565bf: call 0x678476
9565c4: mov esi, eax
9565c6: mov dword ptr [ebp - 0x2c], esi
```

`0x678476` 是关键的目标选择函数之一。它会根据矩形范围和最大目标数选怪，返回选中的数量。
因此把 `2121006` 引入这条路径后，客户端才会真正选择多只怪并把多目标写进攻击封包。

## 五、exe hook 方案

不直接替换某个旧技能 ID。这样会破坏原技能行为。

采用跳板方式：

1. 在 `0x955d0e` 覆盖原来的第一组 `cmp + je`
2. 写入一个 5 字节 `jmp` 到代码洞
3. 剩余 6 字节用 `nop` 填平
4. 代码洞里先判断 `2121006`
5. 命中跳到原 AoE 处理 `0x956372`
6. 不命中则执行原先被覆盖的 `2201005` 判断
7. 仍不命中则跳回 `0x955d19` 继续原列表

使用的地址：

```text
ImageBase = 0x400000
hook VA   = 0x955d0e
hook off  = 0x555d0e
cave VA   = 0xaef602
cave off  = 0x6ef602
AoE VA    = 0x956372
return VA = 0x955d19
```

原始 hook 字节：

```text
3d ad 95 21 00 0f 84 59 06 00 00
```

含义：

```asm
cmp eax, 0x2195ad
je  0x956372
```

补丁后的 hook：

```asm
955d0e: jmp 0xaef602
955d13: nop
955d14: nop
955d15: nop
955d16: nop
955d17: nop
955d18: nop
955d19: cmp eax, 0x231c4a
```

代码洞内容：

```asm
aef602: cmp eax, 0x205d2e   ; 2121006
aef607: je  0x956372
aef60d: cmp eax, 0x2195ad   ; 2201005, 原本被覆盖的第一项
aef612: je  0x956372
aef618: jmp 0x955d19
```

代码洞实际字节：

```text
3d2e5d20000f84656de6ff3dad9521000f845a6de6ffe9fc66e6ff
```

## 六、如何重新应用补丁

数据层：

```bash
rtk python3 tool/scripts/patch_2121006_aoe.py --dry-run
rtk python3 tool/scripts/patch_2121006_aoe.py
```

exe 层：

```bash
rtk node tool/scripts/patch_2121006_exe_aoe.js --dry-run
rtk node tool/scripts/patch_2121006_exe_aoe.js
```

脚本是幂等的。已 patch 时会输出：

```text
BeiDou.exe already has the 2121006 AoE hook.
```

## 七、验证方法

### 1. 验证客户端 IMG 可读

```bash
rtk tool/scripts/wzpy.sh convert clien/Data/Skill/212.img --region GMS -o /private/tmp/212.after.json
```

检查 `2121006/level/1..30` 是否都有：

- `mobCount`
- `lt`
- `rb`
- 原来的 `attackCount=2`

### 2. 验证服务端 XML

```bash
rtk node - <<'NODE'
const fs=require('fs');
const s=fs.readFileSync('gms-server/wz/Skill.wz/212.img.xml','utf8');
const start=s.indexOf('<imgdir name="2121006">');
const end=s.indexOf('<imgdir name="2121007">', start);
const block=s.slice(start,end);
console.log({
  mobCount:(block.match(/name="mobCount"/g)||[]).length,
  lt:(block.match(/name="lt"/g)||[]).length,
  rb:(block.match(/name="rb"/g)||[]).length,
  attackCount:(block.match(/name="attackCount"/g)||[]).length,
});
NODE
```

预期：

```text
{ mobCount: 30, lt: 30, rb: 30, attackCount: 30 }
```

### 3. 验证 exe hook

```bash
rtk objdump -D -Mintel --start-address=0x955d00 --stop-address=0x955d30 clien/BeiDou.exe
rtk objdump -D -Mintel --start-address=0xaef602 --stop-address=0xaef625 clien/BeiDou.exe
```

预期能看到：

```asm
955d0e: jmp 0xaef602
...
aef602: cmp eax, 0x205d2e
aef607: je  0x956372
aef60d: cmp eax, 0x2195ad
aef612: je  0x956372
aef618: jmp 0x955d19
```

### 4. 游戏内验证

1. 启动服务端和客户端。
2. 确认客户端使用的是已 patch 的 `clien/BeiDou.exe` 和 `clien/Data/Skill/212.img`。
3. 角色使用 `2121006`。
4. 在技能矩形范围内放多只怪。
5. 预期一次攻击封包中 `numAttacked` 大于 1，游戏表现为同时命中多只怪。

## 八、回滚方法

直接还原备份：

```bash
cp clien/BeiDou.exe.bak-2121006-exe-aoe clien/BeiDou.exe
cp clien/Data/Skill/212.img.bak-2121006-aoe clien/Data/Skill/212.img
cp gms-server/wz/Skill.wz/212.img.xml.bak-2121006-aoe gms-server/wz/Skill.wz/212.img.xml
```

或者使用版本控制还原对应文件。

## 九、技能在 exe 中是如何“编码”的

这里的“编码”不是一个统一的技能表，而是几层东西叠在一起：

1. WZ 数据树决定技能有哪些资源和数值：

   ```text
   Skill.wz/212.img/skill/2121006/...
   ```

2. 技能 ID 本身是 32 位整数，exe 中常以 little-endian 立即数出现：

   ```text
   2121006 = 0x205d2e
   exe 字节 = 2e 5d 20 00
   ```

3. 服务端也按整数 ID 识别技能：

   ```java
   public static final int PARALYZE = 2121006;
   ```

4. exe 里有大量硬编码分支，用 `cmp eax, skillId` 或 `sub eax, skillId` 判断特殊技能：

   ```asm
   cmp eax, 0x205d2e
   je  some_branch
   ```

5. 不同功能点会有不同硬编码列表，不是某个地方加一次就全局生效：

   - 技能动作/分类。
   - 是否进入矩形 AoE 选怪。
   - 是否使用特殊弹道、链式目标、召唤物、全屏技能逻辑。
   - 特定技能的屏幕震动、延迟、特效播放。
   - 部分 buff/特殊状态表现。

`2121006` 这次的关键就是：它在动作/分类处被识别了，但没有在矩形 AoE 选怪列表里。
所以补 WZ 后服务端知道它最多可以打多只，客户端仍只选 1 只。

## 十、新加一个全新的技能是否可能

结论：有可能，但难度取决于“新技能”想做到什么程度。

### 1. 最容易：复制/改造已有技能 ID

如果只是把某个已有技能改成新的效果、范围、伤害、段数，成功率最高。

需要改：

- 客户端 Skill `.img`
- 服务端 `.img.xml`
- 必要时改服务端常量和处理逻辑
- 如果客户端选怪/动作被硬编码限制，再 patch exe

`2121006` 属于这一类：技能 ID 已存在，只是把单体行为改成群攻。

### 2. 中等：在已有职业 WZ 里新增一个同职业技能 ID

例如在 `212.img` 里新增 `2121010`。理论上服务端 `SkillFactory` 会遍历 XML 里的 `skill`
子节点，能把它作为一个技能加载出来。

但客户端是否能正常使用，还取决于：

- 客户端 `clien/Data/Skill/212.img` 是否也有同一个技能节点。
- String.wz/技能名/技能描述是否补齐，否则 UI 可能显示异常。
- 技能窗口是否会展示这个技能，技能点和前置条件是否能处理。
- 快捷键能不能把这个技能放上去。
- 角色职业是否允许学习/使用这个 ID。
- 使用技能时客户端是否能走到一个通用逻辑，或必须在 exe 硬编码列表里加入它。

如果是简单 buff 或被动，成功率比攻击技能高。攻击技能通常还要解决客户端如何选怪、如何发攻击包、
如何播放 hit/ball/effect。

### 3. 最难：完全新类型技能

如果新技能不是复制现有行为，而是要全新的目标选择、全新的封包结构、全新的资源节点规则，
那就需要同时改：

- 客户端 WZ 数据。
- 服务端 WZ/XML 数据。
- 服务端技能逻辑和包解析/广播。
- `BeiDou.exe` 的技能分类、选怪、动画、封包生成。
- 可能还要改 UI、技能学习、快捷键、冷却、状态图标等路径。

这种不是“不可能”，但工作量接近给客户端加一个新技能引擎。比较稳的做法是：先找一个行为最接近的
原技能，把新技能伪装成它的同类，再逐步 patch 差异。

## 十一、技能资源节点是如何识别的

### 服务端目前识别哪些节点

服务端 `gms-server/src/main/java/org/gms/client/SkillFactory.java` 里，加载技能时明确读取：

```java
Data effect = data.getChildByPath("effect");
Data hit = data.getChildByPath("hit");
Data ball = data.getChildByPath("ball");
Data action_ = data.getChildByPath("action");
```

其中 `effect` 还会用于计算动画时间：

```java
if (effect != null) {
    for (Data effectEntry : effect) {
        ret.incAnimationTime(DataTool.getIntConvert("delay", effectEntry, 0));
    }
}
```

也就是说，服务端这套代码只把名字叫 `effect` 的节点当成主 effect。`effect0/effect1`
不会自动参与 `animationTime`，也不会因为你新建一个 `myEffect` 就被服务端理解。

### 客户端如何识别节点

客户端识别节点主要靠 exe 中的固定读取逻辑和 WZ 约定。常见节点名包括：

- `action`
- `effect`
- `effect0`
- `effect1`
- `hit`
- `ball`
- `keydown`
- `prepare`
- `affected`
- `tile`
- `mob`
- `summon`

并不是所有技能都会读所有节点。客户端会先根据技能 ID、技能类型、动作分类、封包里的 effectId
进入某条固定逻辑，然后那条逻辑再去读固定名字的节点。

这次统计服务端 WZ，可见：

```text
effect  = 大量技能使用
effect0 = 56 个技能使用
effect1 = 5 个技能使用
effect2 = 3 个技能使用
effect3 = 3 个技能使用
```

而且样本里 `effect0` 都是和 `effect` 同时存在的。例如：

```text
4211001: effect,effect0
1121006: effect,effect0
5221003: effect,effect0,effect1
1311001: effect,effect0,effect1,effect2,effect3
15111003: effect,effect0,effect1,effect2,effect3
2321004: effect,effect0
2221004: effect,effect0
```

这说明 `effect0` 更像“某些客户端逻辑会额外读取的编号效果”，不是 `effect` 的替代品。

### `effect` 和 `effect0` 同时存在时怎么选

先明确一点：`effect` 和 `effect0` 不是简单的“有 `effect0` 就替换 `effect`”。在一些技能里，
它们更可能是并行存在的两个视觉入口：

```text
effect  = 主释放效果
effect0 = 额外层、额外阶段、特殊 effectId，或某条技能专用逻辑读取的效果
```

如果客户端分支本来会同时创建两个 effect 对象，那么这两个动画可能是同一时刻播放，也可能各自带
独立的坐标、z 层、delay、alpha、翻转方向和结束时机。把 `effect0` 的帧硬合并进 `effect`，
只能得到“主 effect 播放了一串更多的帧”，不等于还原了客户端同时播放两层效果。

服务端发送 buff/特殊效果时，有一个 `effectId` 字段：

```java
PacketCreator.showOwnBuffEffect(skillId, effectId)
PacketCreator.showBuffEffect(chrId, skillId, effectId)
```

包里会写：

```java
p.writeByte(effectId);
p.writeInt(skillId);
```

客户端收到后会根据 `skillId + effectId` 选择对应表现。具体映射在 exe 内部，不能只靠 WZ
任意猜。常见经验是：

- `effect` 是默认主效果。
- `effect0/effect1/...` 是某些技能的附加或阶段效果。
- hit 类表现通常走 `hit`。
- 弹道类表现通常走 `ball`。
- 蓄力/按住类表现常见 `keydown`。
- 准备动作常见 `prepare`。
- 命中怪物身上的状态/受击表现可能走 `affected`、`mob` 或 `hit`，取决于技能类型。

所以如果看到一个技能同时有 `effect` 和 `effect0`，不能简单认为客户端会随机或自动播放两个。
通常是不同路径、不同 effectId，或技能专用代码同时触发。判断时要进游戏看释放瞬间、自己视角、
他人视角、怪物身上命中特效是否分别出现，而不是只看 WZ 节点是否存在。

### 是否可以自定义新节点名

通常不行，至少不能只改 WZ。

例如新增：

```text
skill/2121006/myCustomEffect
```

如果 exe 没有代码去找 `myCustomEffect`，客户端就不会播放它。服务端也不会理解它，除非你改
服务端代码显式读取这个节点。

比较现实的自定义方式有三种：

1. 复用客户端已认识的节点名：

   ```text
   effect
   effect0
   hit
   ball
   keydown
   prepare
   ```

2. 找一个同类技能，复制它的资源结构和 exe 分支。

3. exe patch：让某个技能在某条逻辑里读取你想要的节点名。这个难度明显更高，因为要找到
   具体字符串/路径构造和资源读取函数。

### 给技能加新视觉资源的建议顺序

1. 先复制同类技能的节点结构，不要自己发明名字。
2. 确认客户端能播放默认 `effect/hit/ball`。
3. 如果要多阶段效果，优先参考已有 `effect0/effect1` 技能。
4. 如果需要服务端主动触发某个效果，查对应 `PacketCreator.show...Effect` 是否有 effectId。
5. 游戏内测试时区分：

   - 技能释放者自己看到的效果。
   - 其他玩家看到的效果。
   - 怪物身上的命中特效。
   - 伤害数字和实际命中目标。

这些常常是不同封包和不同 WZ 节点。

### 给本来没有 `effect0` 的技能加 `effect0`

只在 WZ 里新增：

```text
skill/<skillId>/effect0
```

通常不会自动生效。原因是客户端必须在某条固定逻辑里“请求 effect0”，否则这个节点只是静静躺在 WZ
里，没人读取。

让客户端识别新 `effect0` 有几种可行路线，难度从低到高：

1. 只做资源复用或降级显示：把想播放的动画合并到 `effect`。

   这是“不改 exe 也能让画面出现”的低风险方案，因为客户端已经会读 `effect`。但它只适合简单
   视觉复用，不适合还原真正的 `effect + effect0` 同时播放。

   不适合合并的情况：

   - `effect` 和 `effect0` 原本应当同一时刻叠加。
   - 两个效果需要不同 origin、z 层、alpha、delay 或翻转规则。
   - `effect0` 要被封包里的某个 `effectId` 单独触发。
   - `effect0` 是蓄力、爆发、持续循环、命中附着等独立阶段。

   另外服务端 `SkillFactory` 当前只用 `effect` 计算 `animationTime`。把额外帧合并进 `effect`
   可能会改变服务端认为的技能动画时间；而单独新增 `effect0` 通常不会影响这个时间。

2. 用 `effect` 做 UOL/引用跳到 `effect0`。

   如果只是想复用资源，可以保留 `effect0` 作为资源仓库，让 `effect` 下的帧 UOL 到 `effect0`。
   这样客户端仍然读取 `effect`，但素材来自 `effect0`。这不等于客户端真正认识了 `effect0`，
   只是绕过了节点名问题。

3. 找一个原本就会播放 `effect0` 的同类技能，把目标技能接入同一条客户端分支。

   例如某些技能已有 `effect,effect0`，并且释放时确实会出现两段效果。可以在 exe 里搜索这些技能 ID，
   看它们是否进入了额外 effect 分支。然后把新技能 ID hook 进去。风险是同一分支可能还附带其它行为，
   比如延迟、屏幕效果、状态图标或特殊动作。

4. patch 客户端的资源读取逻辑，让它对某个技能额外读取 `effect0`。

   这是最硬核也最难稳定的方式。需要找到客户端构造 `"effect"` 字符串/路径的位置，或找到
   `skillId + effectId` 到节点名的映射逻辑，再新增分支。由于当前 exe 中字符串可能经过字符串池或
   加密/间接引用，不能指望简单搜索 ASCII `"effect0"` 就能定位。

经验判断：

- 只想让素材显示出来、能接受时序变化：可以改 `effect` 或 `hit`，先别碰 exe。
- 想要 `effect` 和 `effect0` 同一时刻双层叠加：需要找到/接入会创建双 effect 的客户端分支，
  或 patch exe 让目标技能额外创建并播放 `effect0`。
- 想让服务器主动触发额外 buff/特殊效果：先看现有 `showOwnBuffEffect/showBuffEffect` 的 `effectId`
  是否已经能触发你要的节点。
- 想让攻击释放时自动多播一个 `effect0`：大概率需要 exe patch，或找一个已经有同类行为的技能复制。

可以按这个表判断方案：

```text
目标                                         建议
------------------------------------------   --------------------------------------
只是复用素材                                 effect/UOL 可以
只是多一段连续动画                           合并进 effect 可以，但要看 animationTime
要同一时刻双层叠加                           需要客户端双播放分支或 exe patch
要被 effectId 单独触发                       查 show...Effect 和客户端 effectId 映射
要攻击释放时自动播放额外 effect0             对比同类技能，hook 到 effect0 分支
要自定义 myEffect 这种新名字                 基本需要 exe 资源读取逻辑 patch
```

## 十二、远程技能不丢东西，改成原地周围攻击

这里说的不是把远程技能真正改成 `CLOSE_RANGE_ATTACK` 包，也不是改成近战武器挥砍。更稳的目标是：

```text
保留远程武器动作
保留远程攻击封包 RANGED_ATTACK
隐藏或跳过飞行物视觉
把目标选择改成角色周围矩形/圆形范围
```

这样做的好处是动作和服务端 handler 变化最小。服务端当前有三类攻击广播：

```java
PacketCreator.closeRangeAttack(...)
PacketCreator.rangedAttack(...)
PacketCreator.magicAttack(...)
```

`rangedAttack` 会在公共攻击体里写 projectile：

```java
p.writeInt(projectile);
```

所以“远程不丢东西”至少分成两个层面：

1. 视觉层：不要显示飞行物。
2. 判定层：不要按飞行物路径找目标，而是按角色周围范围找目标。

### 1. 只隐藏飞行物，攻击逻辑不变

这是最容易的版本。

可能做法：

- 把技能自身 `ball` 节点改成透明/1x1 空帧。
- 如果飞行物来自投掷物/箭矢道具资源，而不是技能 `ball`，则改对应 projectile item 的显示资源。
- 服务端广播给别人时，把可见 projectile 改成 0 或一个透明 projectile。这个要看客户端对
  `projectile=0` 的容错，不能默认一定可用。

这种方式只解决“看不到东西飞出去”，但客户端可能仍按远程弹道/射线选择目标。

### 2. 保留远程包，但改成身边 AoE 选怪

这是你描述的目标：武器动作不变，角色原地向周围攻击。

需要处理：

- WZ 数据：给技能补 `mobCount`、`lt/rb`、合适的 `attackCount`。
- 客户端 exe：把该远程技能的目标选择从“远程路径/单目标/弹道目标”接到“角色周围范围选怪”。
- 客户端视觉：隐藏 `ball` 或 projectile，必要时把释放效果放到 `effect/hit`。
- 服务端 XML：同步 `mobCount/lt/rb`，否则服务端会按旧目标数校验。
- 服务端 handler：尽量仍走 `RangedAttackHandler`，不要改成 `CloseRangeDamageHandler`，否则客户端发包 opcode
  和服务端解析路径都要一起改。

换句话说，最好做成“远程封包 + 近身范围选怪”，而不是“远程技能改近战封包”。

### 3. 真正改成 CLOSE_RANGE_ATTACK

这个通常不好改。

因为客户端发送的 opcode、封包字段、服务端 handler、广播包类型、其它客户端播放逻辑都会变。
如果只改服务端，把 ranged 包当 close-range 广播，自己客户端和别人客户端看到的动作/特效可能不一致；
如果只改客户端发 close-range 包，服务端可能按错误 handler 解析，字段错位。

除非目标就是完整重做技能类型，否则不建议走这条路。

### 推荐实现路线

如果要把一个远程攻击改成“原地周围攻击、不丢东西、武器动作不变”，建议按这个顺序做：

1. 先只隐藏 projectile/ball，确认攻击仍能正常发包和造成伤害。
2. 给技能补 `mobCount/lt/rb`，服务端 XML 同步。
3. 在 exe 里找该技能 ID 出现位置，确认它当前进入哪条 ranged 选怪路径。
4. 找一个“远程动作但范围判定”的同类技能做参照，例如已有的范围弓/弩/飞侠/枪手技能。
5. 用 hook 把目标技能接入该范围选怪路径，保留原远程动作和 `RANGED_ATTACK` 发包。
6. 游戏内分别验证：

   - 自己看不到飞行物。
   - 其他玩家也看不到飞行物。
   - 多只怪在身边范围内会被命中。
   - 远处路径上的怪不会被错误命中。
   - 服务端不会触发 `MOB_COUNT` 或距离类检测。

难度判断：

- 只隐藏飞行物：通常容易，可能只改 WZ。
- 原地周围 AoE 判定：中等到偏难，通常要 exe patch。
- 真改 close-range 包：难，不建议作为第一方案。

## 十三、以后修改其它技能的参考流程

1. 确认技能 ID：

   ```bash
   rtk node -e 'const n=2121006; console.log(n.toString(16), Buffer.from(Uint32Array.of(n).buffer).toString("hex"))'
   ```

2. 查客户端和服务端数据是否有必要字段：

   - `mobCount`：服务端最大目标数，客户端也可能读取。
   - `attackCount`：每只怪伤害段数。
   - `lt/rb`：矩形范围，AoE 选怪通常需要。

3. 在 exe 中搜索技能 ID 的 little-endian 字节。

4. 反汇编命中附近：

   ```bash
   rtk objdump -D -Mintel --start-address=0x... --stop-address=0x... clien/BeiDou.exe
   ```

5. 判断技能应该进入哪类客户端选怪路径：

   - 矩形范围 AoE：通常可接入 `0x956372` 这类路径。
   - 特殊链式/弹道/召唤/全屏技能：不要盲目接入矩形 AoE，需要对比同类技能。

6. 优先使用跳板，不直接替换已有技能 ID：

   - 找代码洞。
   - 覆盖原位置为 `jmp cave`。
   - 在 cave 里补新技能判断。
   - 保留被覆盖的原逻辑。
   - 跳回原流程。

7. 验证：

   - exe 反汇编落点正确。
   - 数据文件可重新解析。
   - 服务端不会因为 `mobCount` 判超目标。
   - 游戏内实际封包/表现命中多只怪。

## 十四、这次踩过的坑

1. 一开始误把技能看成 `2121001`，实际目标是 `2121006`。
2. `2121001` 的问题点和 `2121006` 不一样，不能套同一个 exe patch。
3. 只补 `mobCount` 只能解除服务端最多 1 只的限制，不能强迫客户端选择多只怪。
4. `2121006` 原本在 exe 中被识别成某个单体/特殊魔法分类，但没有进入矩形 AoE 选怪列表。
5. 修改 exe 时不要直接拿已有技能 ID 做替换，否则会让被替换技能丢失原行为。
