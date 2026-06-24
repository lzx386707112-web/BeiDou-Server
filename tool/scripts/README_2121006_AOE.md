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

## 九、以后修改其它技能的参考流程

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

## 十、这次踩过的坑

1. 一开始误把技能看成 `2121001`，实际目标是 `2121006`。
2. `2121001` 的问题点和 `2121006` 不一样，不能套同一个 exe patch。
3. 只补 `mobCount` 只能解除服务端最多 1 只的限制，不能强迫客户端选择多只怪。
4. `2121006` 原本在 exe 中被识别成某个单体/特殊魔法分类，但没有进入矩形 AoE 选怪列表。
5. 修改 exe 时不要直接拿已有技能 ID 做替换，否则会让被替换技能丢失原行为。
