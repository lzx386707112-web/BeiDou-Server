# 套装面板属性标签：固定值与百分比（2026-09-29）

## 输入与输出

- 输入基线：`backup/BeiDouSetItemCompat.dll.before-stat-labels`
  （sha256 `d6f9143373f50601f3020acc7277ec25c334de73c61b51f6a14a4a2529f839f0`，
  即「9 系列称号」补丁后的成品）
- 输出：`clien/BeiDouSetItemCompat.dll`
  当前 sha256 `4be45cec77c0abe5751af9a7d6908343a719dbd3994b391934923cc8c9f8f5f3`
  （23040 字节；基线 20480 字节，最后一节扩展，节数量和 RVA 不变）
  PE CheckSum：基线 `0x147e6`，输出 `0x12a86`。
- 构建入口：`build.sh`，调用 `patch_stat_labels.py` 后执行标签与称号契约。
- 脚本：`patch_stat_labels.py`（从不可变基线重建；整文件相同才报 already patched）
- 契约：`test_stat_labels_contract.py`

> 本文只解决**客户端面板显示**。服务端白名单与真实生效另见
> `docs/套装属性与槽位编辑-实现与验收.md`。原始可行性调查保留为历史记录。

## 为什么要改

套装面板把服务端包里的属性 key 翻译成中文标签，逻辑是**一条直线比较链**：
9 次 `lstrcmpA(key, 常量)`，全不中则落到兜底标签「属性」（VA `0x65c8548c`）。

`PDD / MDD / ACC / EVA` 不在链上 → 面板只会显示四行一模一样的「属性 +N」。
本次同时补齐 `STR / DEX / INT / LUK`，以及 12 个基本属性的规范 `Pct` 后缀键。

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
异址加载时标签会指向野地址；Windows 同样会重定位。本补丁注册了 41 条（见下）。

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
   执行 20 次新比较再跳回 `0x367b`，共 530 字节：

   ```text
   c7 44 24 04 <key_VA>   mov dword [esp+4], key
   89 1c 24               mov [esp], ebx
   ff d6                  call esi            ; lstrcmpA
   85 c0                  test eax, eax
   b8 <label_VA>          mov eax, label
   0f 84 <rel32>         je common           ; 26 字节/块
   ...  x20 ...
   b8 <兜底 VA>           mov eax, 0x65c8548c
   e9 <rel32>             jmp 0x65c8367b
   ```

   **cave 全程不动 esp**（`lstrcmpA` 是 stdcall 自弹参），所以共用尾部那次
   `wsprintfW` 的 5 个参数槽仍然落在合法的 scratch 区。

3. **字面量**（紧跟 cave）：20 个 key（ANSI，共 114 字节，含对齐）和 UTF-16LE
   标签（168 字节），占用到文件 `0x51d8`。

4. **`.titles` VirtualSize `0x4aa` 和 raw size `0x600` 均扩到 `0x1000`**。
   仍在原有 SizeOfImage 预留页内，没有移动 RVA 或扩大映像页数。

5. **`.reloc` 新增一个块**：page `0x312000`，41 条（20 个 key 槽、20 个标签槽和兜底槽）。
   基线 RVA `0x3674` 失效条目在写盘前用现有重定位工具的 API 摘除并重排，
   VirtualSize 与数据目录 [5].Size 均为 `0x300`，总条目 `323 - 1 + 41 = 363`。

## 验证（全部离线、可复现）

- `patch_stat_labels.py` 自带断言：窗口原字节、9 个既有 `je` 落点、共用尾部、
  **窗口不是任何跳转的目标**（逐字节扫描 `E8/E9/70-7F/0F8x/EB` 全字节位置）、
  cave 区为全零、生成后用 capstone 断言
  「20 x (`mov`/`mov`/`call esi`/`test`/`mov eax,imm`/`je`)」与结尾 `jmp`，
  并逐字节比对基线，**只允许** 窗口 8 字节 / cave 区 / 节头尺寸 / SizeOfCode /
  重定位目录尺寸 / PE CheckSum / `.reloc` 区 变化。
- `test_stat_labels_contract.py`：PE CheckSum、差异范围白名单、窗口语义、
  cave 指令序列、**端到端模拟 key→标签**（9 个既有 + 20 个新增 + 兜底；
  `PDDX/pdd/PD/HPpct/空串` 仍回落「属性」，规范键为 `HPPct`）、
  新 key 的**后缀必须为空**（`PDD/MDD/ACC/EVA` 不含 `Damage/Rate/Pct`，也不是
  `StatusRes/BuffDuration`，所以渲染成「物理防御力 +30」而不是「+30%」）、
  `Pct` 键后缀为 `%`；41 条新重定位存在、`0x3674` 已消失、条目数 `323 → 363`，
  每个目标 dword 在映像内；模拟 delta `0x12340000` 后所有标签指针仍指向原文本，
  分支编码和落点不受破坏；称号数据未丢。
- `test_nameplate_series_contract.py` / `test_reloc_hygiene_contract.py`：同步更新
  白名单与条目数后**全部通过**。
- `fix_dll_reloc_hygiene.py` 报告：`363 relocations, 0 cross-module displacement(s)`，
  无 stale。

## 回滚

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
5. 手机（Wine/Box86）也需实测；PC 和手机都可能异址加载，离线模拟不等于实机通过；
6. 原截图临时文件已失效，本次没有按截图修改字体、颜色和面板布局。
