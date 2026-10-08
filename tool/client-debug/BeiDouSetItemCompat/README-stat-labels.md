# 套装面板属性标签：固定值、百分比与伤害（2026-09-30）

## 输入与输出

- 输入基线：`backup/BeiDouSetItemCompat.dll.before-stat-labels`
  （sha256 `d6f9143373f50601f3020acc7277ec25c334de73c61b51f6a14a4a2529f839f0`，
  即「9 系列称号」补丁后的成品）
- 输出：`clien/BeiDouSetItemCompat.dll`
  当前 sha256 `bd19d189f30a2981bc3e2f034d24d90485232d03a84c98eb3270d3edd59e5212`
  （23040 字节；基线 20480 字节，最后一节扩展，节数量和 RVA 不变）
  PE CheckSum：基线 `0x147e6`，崩溃版本 `0x7b38`，标签修复 `0x14297`，完整布局 `0x1311a`，配色版本 `0xa89a`。
- 构建入口：`build.sh`，调用 `patch_stat_labels.py` 后执行标签、称号及 x86 栈契约。
  Python 验证依赖 `capstone` 和 `unicorn`；布局 helper 编译依赖 i686 MinGW GCC/binutils。
- 脚本：`patch_stat_labels.py`（从不可变基线重建；整文件相同才报 already patched）
- 契约：`test_stat_labels_contract.py`

> 本文只解决**客户端面板显示**。服务端白名单与真实生效另见
> `docs/套装系列管理与装备补全-验收及待确认.md`。原始可行性调查保留为历史记录。

## 为什么要改

套装面板把服务端包里的属性 key 翻译成中文标签，逻辑是**一条直线比较链**：
9 次 `lstrcmpA(key, 常量)`，全不中则落到兜底标签「属性」（VA `0x65c8548c`）。

`PDD / MDD / ACC / EVA` 不在链上 → 面板只会显示四行一模一样的「属性 +N」。
本次同时补齐 `STR / DEX / INT / LUK`，以及 12 个基本属性的规范 `Pct` 后缀键。
新增 `SPD / JMP / NormalDamage / Damage`，分别显示移动速度、跳跃力、普通怪物伤害、伤害。伤害没有沿用最终伤害标签。未修改协议容量、状态存储和绘制入口。

## 比较链地址表（ImageBase `0x65c80000`；`.text` RVA `0x1000` 对应文件 `0x400`）

| RVA | 作用 |
| --- | --- |
| `0x3501` | `lea ebx,[eax+0x2b18]` —— ebx = 包里的 key 缓冲（ANSI） |
| `0x3507` | key 含 `Damage` / `Rate` / `Pct`（**大小写敏感**子串，helper `0x111e`）→ 后缀 `%` |
| `0x3543` / `0x355c` | `lstrcmpA(key,"StatusRes")` / `("BuffDuration")` → 后缀 `%` |
| `0x356f` | 否则后缀 = 空串（VA `0x65c85414`） |
| `0x357f` | `mov esi,[0x65f900f4]` —— esi = `lstrcmpA`（**stdcall，被调方弹参**） |
| `0x3591` `0x35ad` `0x35c9` `0x35e5` `0x35fd` `0x3615` `0x362d` `0x3645` | PAD / MAD / HP / MP / FinalDamage / BossDamage / ExpRate / DropRate |
| `0x365d` | MesoRate → 标签 VA `0x65c85492`，不中则兜底 |
| `0x3673` | `mov edx,兜底 / cmovne eax,edx` ← **本补丁替换的 8 字节** |
| `0x367b` | 共用尾部：`wsprintfW(buf, L"%s +%d%s", eax, value, suffix)` |

- **标签是 UTF-16LE**：格式串是 `wsprintfW`（IAT `0x65f90118`），其 `%s` 吃宽串。
- **key 是 ANSI**：比较用 `lstrcmpA`（IAT `0x65f900f4`）。
- 每个块的字节数不统一：前 4 块用 `0f 84 rel32`（**28 字节**），后 5 块用 `74 rel8`（**24 字节**）。
- 块内两个 `52`（`push edx`）是**占位**，用来在没有 `sub esp,8` 的情况下预留
  `lstrcmpA` 的两个参数槽（`[esp]` = key、`[esp+4]` = 常量）。

### ⚠️ 一个必须遵守的约束：绝对地址即时数必须带重定位

链上**每一个**绝对地址即时数都在 `.reloc` 里有对应 HIGHLOW 条目
（RVA `0x3508/0x351d/0x3524/0x3534/0x3547/0x354d/0x3560/0x3575/0x3581`，
以及 9 个 key 槽 `0x3595/0x35b1/0x35cd/0x35e9/0x3601/0x3619/0x3631/0x3649/0x3661`、
9 个标签槽 `0x35a2/0x35be/0x35da/0x35f6/0x360e/0x3626/0x363e/0x3656/0x366e`、
兜底槽 `0x3674`）。

也就是说**这个 DLL 是可以被重定位运行的**（手机 Wine/Box86 就落在别的基址）。
新增的 cave 因此必须自己注册同样的条目——漏掉的话 Windows（delta 0）看着完全正常，
异址加载时标签会指向野地址；Windows 同样会重定位。本补丁注册了 49 条（见下）。

## 本补丁做了什么

1. **RVA `0x3673`，8 字节** `ba 8c 54 c8 65 0f 45 c2`（`mov edx,兜底; cmovne`）改为
   `74 05` / `e9 rel32` / `90`：

   | key | 走向 |
   | --- | --- |
   | `== MesoRate` | `je` → RVA `0x367a`（nop）→ 共用尾部，eax 仍是 MesoRate 标签 |
   | `!= MesoRate` | `jmp` → cave |

   `0x366c` / `0x3672` 的两个 `push edx` 原样保留，`0x366a` 的 `test eax,eax` 的标志位
   也不受影响（`push`/`mov` 不改标志）→ **到达 `0x367b` 时 esp / eax / ebx / esi
   与参数槽与原件逐位一致**。

2. **cave：文件 `0x4eac` / VA `0x65f924ac`**（`.titles` 原始数据尾部，RWX，已映射）
   执行 24 次新比较再跳回 `0x367b`，共 682 字节：

   ```text
   c7 44 24 04 <key_VA>   mov dword [esp+4], key
   89 1c 24               mov [esp], ebx
   ff d6                  call esi            ; lstrcmpA
   52 52                  push edx / push edx ; 恢复 stdcall 弹出的 8 字节参数区
   85 c0                  test eax, eax
   b8 <label_VA>          mov eax, label
   0f 84 <rel32>         je common           ; 28 字节/块
   ...  x24 ...
   b8 <兜底 VA>           mov eax, 0x65c8548c
   e9 <rel32>             jmp 0x65c8367b
   ```

   **每次调用后必须恢复 esp**：`lstrcmpA` 的 `ret 8` 会弹出参数，两个 `push edx`
   将参数区重新预留出来。与原比较链一致，进入共用尾部时 esp 才能保持不变。

3. **字面量**（紧跟 cave）：24 个 key（ANSI，共 142 字节，含对齐）和 UTF-16LE
   标签（206 字节），占用到文件 `0x52b2`。

4. **`.titles` VirtualSize `0x4aa` 和 raw size `0x600` 均扩到 `0x1000`**。
   仍在原有 SizeOfImage 预留页内，没有移动 RVA 或扩大映像页数。

5. **`.reloc` 新增一个块**：page `0x312000`，49 条（24 个 key 槽、24 个标签槽和兜底槽）。
   基线 RVA `0x3674` 失效条目在写盘前用现有重定位工具的 API 摘除并重排，
   VirtualSize 与数据目录 [5].Size 均为 `0x310`，总条目 `323 - 1 + 49 = 371`。

## 验证（全部离线、可复现）

- `patch_stat_labels.py` 自带断言：窗口原字节、9 个既有 `je` 落点、共用尾部、
  **窗口不是任何跳转的目标**（逐字节扫描 `E8/E9/70-7F/0F8x/EB` 全字节位置）、
  cave 区为全零、生成后用 capstone 断言
  「24 x (`mov`/`mov`/`call esi`/`push`/`push`/`test`/`mov eax,imm`/`je`)」与结尾 `jmp`，
  并逐字节比对基线，**只允许** 窗口 8 字节 / cave 区 / 节头尺寸 / SizeOfCode /
  重定位目录尺寸 / PE CheckSum / `.reloc` 区 变化。
- `test_stat_labels_contract.py`：PE CheckSum、差异范围白名单、窗口语义、
  cave 指令序列、**端到端模拟 key→标签**（9 个既有 + 24 个新增 + 兜底；
  `PDDX/pdd/PD/HPpct/空串` 仍回落「属性」，规范键为 `HPPct`）、
  新 key 的**后缀必须为空**（`PDD/MDD/ACC/EVA` 不含 `Damage/Rate/Pct`，也不是
  `StatusRes/BuffDuration`，所以渲染成「物理防御力 +30」而不是「+30%」）、
  `Pct`、`Damage` 键后缀为 `%`；49 条新重定位存在、`0x3674` 已消失、条目数 `323 → 371`，
  每个目标 dword 在映像内；模拟 delta `0x12340000` 后所有标签指针仍指向原文本，
  分支编码和落点不受破坏；称号数据未丢。
- `test_nameplate_series_contract.py` / `test_reloc_hygiene_contract.py`：同步更新
  白名单与条目数后**全部通过**。
- `fix_dll_reloc_hygiene.py` 报告：`371 relocations, 0 cross-module displacement(s)`，
  无 stale。

## 2026-09-30 悬停崩溃现场与修复

现场 `session-20260930-170217-pid32.log` 在 17:05:11 记录
`user32.dll+0x529a0` 读取地址 `0x5`。转储中的套装 DLL 加载于 `0x78700000`，
CheckSum 为 `0x7b38`，确认运行的是上述崩溃版本。

栈上 `0x0012e31c` 为 `BeiDouSetItemCompat.dll+0x36aa`，紧随其后的
`wsprintfW` 参数为输出缓冲 `0x0012e460`、格式串 `0x78705612`、
最大 HP 标签 `0x78a12848`、错误数值 `0x7ffc2c00`、错误后缀指针 `0x5`。
旧 cave 每调用一次 `lstrcmpA` 都使 esp 上移 8 字节，连续比较覆盖了保存的数值和后缀。
此前仅模拟 key→标签映射的契约没有执行 stdcall，漏检了这个错误。

修复从原 `before-stat-labels` 基线完整重建，仅补齐每个比较后的两个 `push edx`。
相对崩溃成品，变化限定在 cave/字面量、重定位和 CheckSum；文件尺寸、其他函数、
状态表、星力/名牌路径与客户端资源不变。连续构建两次哈希一致。

`test_stat_label_stack_contract.py` 用 Unicorn 执行实际 x86 指令和 `ret 8`，
覆盖 33 个标签、5 个回退键、3 个数值、原基址及现场 Wine 基址。
旧 DLL 在 PDD 分支明确失败，新版全部通过，且局部变量区未被覆盖。

背包中的终极武器另有独立问题：完整系列的武器排在第 11 槽位，旧服务端
提示包取前 8 槽位而丢失其 item ID。`PacketCreator` 现将超出 8 槽位/10 候选的内容
拆成多个原协议视图，每个视图重复完整件数、加成档位和激活状态，不改变战斗计算。
`test_set_item_hover_contract.py` 使用 Java 测试导出的五职业真实数据包，执行 DLL 的
原生解码器与悬停成员查找；这不替代实机字体/Canvas 绘制验收。

服务端改动需要编译部署新 JAR，本轮没有打包 JAR，也不需要 SQL。

## 2026-09-30 终极 11 槽位完整显示

后续截图证明成员查找通过不代表整个套装已经显示：悬停第 11 槽武器时，
只画匹配的后一视图，故终极显示 3/11 个槽位。统一生成器现同时编译布局 helper，
在 RVA `0x312900`（文件 `0x5300`）写入 880 字节。具体契约、当前交付和运行时
验收见 `docs/套装详情完整显示修复.md`。原生表容量仍为 96/8/10；同系列视图只在
绘制时合并，现有 native Canvas/字体/清理入口不变。移除四个被替换指令的
HIGHLOW 条目 `0x307c/0x30dc/0x30e6/0x322d`，当前总数 367、目录尺寸 `0x308`。
上述 371 条与 `0x310` 是只含标签扩展的历史版本数值，不是当前布局版本。

## 2026-09-30 面板配色与文案

装备、套装及相邻星力背景使用不透明 `#1E1E1E`，套装标题追加“套装”（已有后缀不重复），
档位改为“3件套效果”等。标题与档位使用 `#A8FF53`，加成使用 `#CBCFD7`；
未激活档位不再覆盖成灰色，装备成员原有状态颜色不变。完整槽位及右侧续列保留。

布局 helper 现为 1020 字节；新增 UTF-16 格式串位于 RVA `0x312f00/0x312f30`。
当前重定位共 361 条、目录尺寸 `0x2fc`，其余函数生命周期不变。
`test_panel_style_contract.py` 验证原生 ARGB 传递、限定背景范围、后缀去重、栈及双基址加载。
交付及本次回滚说明见 `docs/套装面板配色与文案.md`。

## 回滚

以下基线回滚会同时移除固定值、百分比、速度/跳跃与伤害标签扩展，仅保留基线称号补丁；只想撤销本轮时，应恢复部署前自行备份的 DLL。

```bash
rtk proxy cp tool/client-debug/BeiDouSetItemCompat/backup/BeiDouSetItemCompat.dll.before-stat-labels \
   clien/BeiDouSetItemCompat.dll
```

## 仍需在 Windows 客户端实测

静态验证无法覆盖运行时。替换 DLL 后仍需重启客户端；共享目录部署需重启虚拟机，
或先将文件放在虚拟机本地磁盘，备份目标后删除再复制，避免旧文件内容缓存：

1. 用 `certutil -hashfile BeiDouSetItemCompat.dll SHA256` 核对与上表 SHA-256 一致；
2. 打开一件带套装的装备 tooltip，确认**原有 9 类属性显示不变**（回归）；
3. 让服务端下发 `PDD/MDD/ACC/EVA` 档位属性，确认显示为
   「物理防御力 / 魔法防御力 / 命中率 / 回避率」而不是四行「属性」；
4. 确认 `HPPct=20` 等显示为「最大HP +20%」，规范键区分大小写；
   确认速度/跳跃没有 `%`，`NormalDamage` 与 `Damage` 有 `%` 且标签不同于最终伤害；
5. 手机（Wine/Box86）也需实测；PC 和手机都可能异址加载，离线模拟不等于实机通过；
6. 核对终极显示全部 11 行中文装备名，超长加成向右续列；星力条随主提示框移动。
