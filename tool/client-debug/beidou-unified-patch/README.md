# beidou-unified-patch — BeiDou.exe 统一崩溃补丁

把已经**实证过**的全部崩溃点，从**原始基线一次性**打全，避免"一轮修一个"。

## 为什么需要"统一"

前两轮各写了一个独立补丁脚本（`beidou-skip-media-com-error`、
`beidou-variant-null-guard`），逐个叠加。一旦其中某个脚本的替换区间判断有误
（例如把 `0x401D44` 的 `test eax,eax` 一起吃掉），叠加出来的结果就没人能保证。
本目录改成**唯一入口**：永远从 `backup/BeiDou.exe.orig` 完整生成，不做增量叠加。

## 文件

| 文件 | 作用 |
|---|---|
| `patch_unified.py` | 补丁生成器。`--dry-run` 只校验，`--apply` 写盘。幂等。 |
| `test_unified_contract.py` | 契约测试。capstone + 全 `.text` 分支扫描 + 可达性差分。 |
| `backup/BeiDou.exe.orig` | 原始基线，sha256 `06cdac31…ba18`，PE CheckSum `0x004213DC` |
| `backup/BeiDou.exe.prev2patch` | 上一轮"两个独立补丁叠加"的结果（仅供对比） |

## 补丁清单

| 点 | 位置 | 原字节 | 新字节 | 问题 |
|---|---|---|---|---|
| P1 | `0x403AE9` | `7D` | `EB` | 媒体 COM 失败抛 `_com_error` |
| P2 | `0x410FF5` | `8B 08 50 FF 51 04` | `E8 …… 90` → 桩A | `_variant_t` 漏判 `pSrc` |
| P3 | `0x401D3E` | `8B 46 20 8B 40 14` | `E9 … 90` → 桩C | WZ 节点链式解引用缺判空 |
| P4 | `0x401D52` | `66 8B 07 66 85 C0` | `E9 … 90` → 桩B | WZ 数组遍历解引用 NULL |
| P5a | `0x403965` | `8B 0E 8D 55 E0` | `E9 …` → 桩D | get_item 包装的 `this` 为空时读地址 0 |
| P5b | 127 处（`P5_GETTER_SITES`） | `E8 <rel32→0x40263B>` | `E8 <rel32→桩E>` | 取址器抛 `E_POINTER`（**09-28 切图崩溃本体**） |
| P5c | `0x4039F5` | `83 65 FC 00 56 8B F1` | `E9 … 90 90` → 桩F | 0x4039F1(`vtbl[7]`) 的 `this` 判空 |
| P5d | `0x409EF6` | `8B 06 8D 4D FC 51` | `E9 … 90` → 桩G | 0x409EEF(`vtbl[8]`) 的 `this` 判空 |

代码桩落在 `.text` 尾部空洞（`VA 0xAEFE30` 起，raw size == vsize ==
`0x6EF000`，整段零字节、零入口、已映射 RX）：

```
0xAEFE30  桩A  11 B   test eax,eax / je / mov ecx,[eax] / push eax / call [ecx+4] / ret
0xAEFE40  桩B  23 B   test edi,edi / je / mov ax,[edi] / test ax,ax / jmp 0x401D58 / jmp 0x401D11
0xAEFE60  桩C  24 B   xor eax,eax / test esi,esi / ... / jmp 0x401D44
0xAEFE80  桩D  20 B   test esi,esi / je 空 / mov ecx,[esi] / lea edx,-0x20(%ebp) / jmp / jmp 0x403980
0xAEFEA0  桩E   3 B   mov eax,[ecx] / ret          <- 取址器 0x40263B 的容错克隆
0xAEFEB0  桩F  35 B   and [ebp-4],0 / push esi / mov esi,ecx / test ecx,ecx / je / ... / leave / ret 4
0xAEFEE0  桩G  20 B   test esi,esi / je / mov eax,[esi] / lea ecx,[ebp-4] / push ecx / jmp / ... / ret
```

**禁改区**（脚本会断言逐字节不变）：
`0xAEFA20` DawnWarriorSkillLoader thunk、`0xAEFD80` 既有桩。

## P5：为什么是"改调用目标 + 加壳"，而不是"把取址器改成返回 0"

`0x40263B` 就是那个"取址器"：

```
40263B  56            push esi
40263C  8B F1         mov  esi,ecx
40263E  83 3E 00      cmp  dword [esi],0     ; *ecx == 0 ?
402641  75 0A         jne  40264D
402643  68 03 40 00 80   push 0x80004003     ; E_POINTER
402648  E8 …          call _com_issue_error  ; 不返回
40264D  8B 06         mov  eax,[esi]
40264F  5E            pop  esi
402650  C3            ret
```

三条硬证据决定了修法：

1. **不能动 `0x40263B` 本体**：它在 `.text` 里有 **2406** 个调用点，
   其中 2381 个把返回值直接当 `this` 用。改成"返回 0"会把可捕获异常
   换成 0 地址解引用 → 大面积访问违例。
2. **`E_POINTER` 在全局从不被处理**：整个 `.text` 里立即数 `0x80004003`
   出现 5332 次，其中 **4927 次 `push` / 402 次 `mov` / 0 次 `cmp`** ——
   只被"产生"，没有任何 `cmp`/`test` 去分类它，所以它只能是致命错误。
   对照 `0x80004002`(E_NOINTERFACE) 有 **1404 次 `cmp`** ——
   那才是客户端设计上"接口不可用"的降级信号；崩溃函数自己在
   `0x5CAD25` 就是 `mov ebx,0x80004002` 这么用的。
3. **空槽本来就是设计内的状态**：崩溃函数 `0x5CAD0B..0x5CAD13` 先把
   `[ebp-0x64]` 清 0，源对象为空就直接跳过 QI —— 也就是"接口拿不到"时
   代码本来就打算带着 `ebx = E_NOINTERFACE` 继续走。后面取址器却抛
   `E_POINTER`，属于自相矛盾。

于是：**只在崩溃函数内**把这 127 个调用点改指容错克隆（桩 E =
`mov eax,[ecx]; ret`，与 `0x40263B` 的正常路径逐字节等价、只是不抛），
再用桩 D/F/G 接住 127 个站点里"返回 0"的三种下游消费者。

127 个站点按 CFG 可达性枚举，消费者分三组：

| 消费者 | 站点数 | 谁来接住 `this == 0` |
|---|---|---|
| `0x403935` get_item 包装（`ret 8`，VARIANT 出参） | 119 | 桩D → 直接出**空 VARIANT**（下游本来就判空 vt） |
| `0x4039F1`（`vtbl[7]`，`ret 4`，DWORD 出参） | 6 | 桩F → 出参写 0 |
| `0x409EEF`（`vtbl[8]`，`ret`，返回 DWORD） | 2 | 桩G → 返回 0 |

`ecx` 的取址形式在源码里有 3 种编码（`lea disp8(%ebp)` / `lea disp32(%ebp)` /
被 `mov dword [ebp-4],imm32` 隔开），所以**不能**用"逐点内联
`mov eax,[ebp+disp8]`"去做（前两种长度不同、后一种前缀对不上）；
改成"只换 `E8` 的 rel32 操作数"就一次性覆盖全部编码，
而且每个站点只有一个 4 字节操作数变化。

桩F/桩G 改的是**共享函数**（分别 95 / 182 个调用者），但它们只在
`this == 0` 时改变行为 —— 而基线在那个条件下是 `mov eax,[cs:0]`，
即**必然访问违例**。所以两处都只是"必崩 → 有定义的默认值"，
不会引入新的崩溃路径。

### 桩D 的栈深度为什么是安全的

`0x403965` 之后原流程是 `push edx / push eax / push esi / call [ecx+0x14]`，
桩D 的空分支直接跳到 `0x403980`（跳过那 4 条）。`0x403980` 之后一整段
（拷贝 VARIANT → 释放 → 恢复 SEH）以 **`leave`** 收尾，
而 `leave` = `mov esp,ebp; pop ebp` 会**重置 esp**，
所以入桩时的 esp 偏差在函数返回前必然被吸收，`ret 8` 的净效果不变。


## 两个容易踩的坑（都已在脚本里处理）

### 1. `0x401D3E` 只能替换 6 字节，不能 8 字节

```
401D3E  8B 46 20        mov eax,[esi+0x20]
401D41  8B 40 14        mov eax,[eax+0x14]
401D44  85 C0           test eax,eax      <-- 必须保留
401D46  8B DA           mov ebx,edx       <-- 必须保留
401D48  74 04           je 0x401D4E
```

桩 C 要跳回 `0x401D44` 靠 `test eax,eax` 设置 ZF，`0x401D48` 的 `je` 依赖它。
如果按 8 字节替换（连 `test` 一起吃掉），`je` 就会读到不确定的标志位。
所以替换长度取 `0x401D3E..0x401D43` 共 6 字节 = `jmp rel32`(5) + `nop`(1)。

### 2. `0x401D52` 有外部入口，但是安全的

`0x401DBC` 的内层循环回跳 `add edi,4; jmp 0x401D52` 会进入被替换区。
那里 `edi` 必然非零，走桩 B 的 `test edi,edi` 会原样通过 —— 行为等价。
契约测试里对这条入口做了**显式豁免**，而不是假装它不存在。

## 用法

```bash
# 校验前置条件（不写盘）
/opt/homebrew/bin/python3 tool/client-debug/beidou-unified-patch/patch_unified.py --dry-run

# 写盘
/opt/homebrew/bin/python3 tool/client-debug/beidou-unified-patch/patch_unified.py --apply

# 契约测试（需要 capstone，只有 /opt/homebrew/bin/python3 有）
/opt/homebrew/bin/python3 tool/client-debug/beidou-unified-patch/test_unified_contract.py
```

结果（P1~P5 全量）：`sha256 1b91cf5bd0f88eb2324bfdec39a7329eab970e863cbb253ee209b2fc6df134b2`，
PE CheckSum `0x00825088`，总差异 682 字节，文件大小不变（8503296）。
契约测试 234 项全通过。差异区间只有：PE CheckSum 字段、8 处手写补丁点、
127 个 `call` 的 4 字节操作数、7 个代码桩。

## ⚠️ 部署陷阱：补丁写了不等于客户端加载了

这是本项目目前最大的坑，比补丁本身重要。

客户端跑在 **Parallels 的 Windows 虚拟机**里，通过 `C:\Mac\Home\...`
读 macOS 共享目录。实测（见 `clien/diagnostics/` 的 08:55 会话）：

| 判据 | 值 | 说明 |
|---|---|---|
| 转储模块表 `BeiDou.exe` CheckSum | `0x004213DC` | **原始版** |
| 转储模块表 `WzFileLogger.dll` CheckSum | `0x0001898B` | **原始版** |
| 日志 `diagnostic_file` 报的 `WzFileLogger.dll` size | `43008` | 正确 |
| 日志 `diagnostic_file` 报的 `write_time` | `09-23 20:40:55.292` | 与 Mac 侧 mtime 逐毫秒一致 |

**元数据是新的，内容是旧的。** 共享目录驱动转发了 size/mtime，但 Windows 的
文件系统缓存因为**文件大小没变**而没有失效，加载的仍是旧映像。

- 改 IMG/WZ 能生效 —— 那些改动改变了文件大小
- 改 exe/dll 不生效 —— 原地等长替换，大小一个字节都没变

**排查清单**

1. 看崩溃转储模块表的 `CheckSum`。
   `0x004213DC` = 原版 → 补丁没加载，**先解决分发，别改代码**。
   `0x00825088` = 当前补丁版（P1~P5 全量）→ 补丁已加载，再看具体崩溃点。
   `0x00820778` = 2026-09-28 09:26 那版（只有 P5a + 10 处内联，**不完整**，应替换）。
2. 让用户在虚拟机里跑
   `certutil -hashfile "C:\Mac\Home\...\clien\BeiDou.exe" SHA256`。
   期望 `1b91cf5bd0f88eb2324bfdec39a7329eab970e863cbb253ee209b2fc6df134b2`。
3. 强制刷新：重启虚拟机（最省事）／在虚拟机里 `del` + `copy`（源必须是
   虚拟机本地磁盘上的文件）／整个 client 复制到本地磁盘运行。

`~/Downloads/切图崩溃全面修复/部署.bat` 就是把第 3 条的"删除+重建+校验"
自动化了，并会警告"脚本本身还在共享目录里跑"的情况。

## 修改日志

- 2026-09-24 建立。合并 `beidou-skip-media-com-error`（P1）与
  `beidou-variant-null-guard`（P2），新增 P3/P4（WZ 遍历判空）。
  本轮同时确认了"补丁未被加载"这一分发层问题。
- 2026-09-28 新增 P5（切图「无效指针」= `E_POINTER`）。
  - 先用转储 + 反汇编把因果链钉死：媒体/资源接口取不到 → 缓存槽 NULL →
    取址器 `0x40263B` 抛 `E_POINTER` → 顶层当致命错误弹框退出。
  - 关键取证：`0x40263B` 有 2406 个调用点（不能改本体）；
    全 `.text` 中 `E_POINTER` **0 次 `cmp`**（无人处理）而
    `E_NOINTERFACE` 有 1404 次 `cmp`（正规降级信号）。
  - 修法：只在崩溃函数内把 127 个取址器调用点改指容错克隆（桩E），
    再补桩 D/F/G 接住三种下游消费者（119 + 6 + 2）。
  - 期间修正/推翻的中间方案：
    ① 最初只找到 10 个站点（漏了 117 个）—— 因为只看"崩溃点附近"；
    ② 一度想逐点内联 `mov eax,[ebp+disp8]` —— 被 disp32 编码的 `lea`
       （6 字节，装不进 5 字节窗口）证伪；
    ③ 原契约测试里 `0x40263B` 的比对切片是 15 字节而期望串只有 14 字节，
       一直误报 FAIL；`P5_GETTER_SITES` 在两份文件里把 `0x5CBEBD`
       抄成了 `0x5CBEBF`（已被"站点集合与 walk 一致"这条断言抓住）。
