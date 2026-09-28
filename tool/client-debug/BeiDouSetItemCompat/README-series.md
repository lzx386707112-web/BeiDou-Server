# 名牌多系列称号（9 系列）

## 输入与输出

- 输入基线：`backup/BeiDouSetItemCompat.dll.before-title-series`
  （`sha256 10b660c8...`，即 64 位战力补丁后的可运行版本）。
- 输出：`clien/BeiDouSetItemCompat.dll`。
- 当前输出 SHA-256：`d6f9143373f50601f3020acc7277ec25c334de73c61b51f6a14a4a2529f839f0`
  （20480 字节，PE CheckSum `0x000147E6`）。
  > 2026-09-24 档位阶梯修复前的产物是 `4e393447…4678457` / CheckSum `0x000145E6`，
  > 它的档位方向是反的（见下节）。
- 脚本幂等：输出已含 `.titles` 节时直接报告 already patched。
- 生成流程末尾会调用 `fix_dll_reloc_hygiene.py --apply`，从基线重建两次结果逐字节一致。

## 档位阶梯修复（2026-09-24，称号永远是最低档）

症状：玩家 400 多万战力，切换系列后显示的是该系列的**最低档**称号
（玄幻一直是「乾元玄阶」）。战力越高档位越低，战力低于 1 万反而拿最高档。

根因：D2 的档位阶梯比较指令**操作数写反了**。

```text
生成器写的:  39 94 88 <disp32>   # 注释声称 cmp edx,[eax+ecx*4+THR2]
实际语义:    39 /r = CMP r/m32, r32  ->  cmp [THR2+ecx*4], edx
```

于是 `jb done` 的语义从「战力 < 阈值 → 停」变成「**阈值 < 战力 → 停**」：
第一档阈值 1 万，凡是战力 ≥ 1 万的账号**第一次比较就跳出循环**，`ecx` 停在 0，
永远取索引 `series*10 + 0`。只有战力不足 1 万的账号才会一路走到 tier 8。

```text
RVA +0x35: 39 94 88 b9 20 31 00   cmp dword ptr [eax+ecx*4+0x3120b9], edx
RVA +0x3c: 72 06                  jb  0x312044     <- 立刻跳去 done, ecx=0
```

同一个编码错误也存在于 `patch_nameplate_power.py:246`（战力补丁的阶梯）。
那段在「战力 + 系列」成品里已是**死代码**（`0x1e60` 被重定向到新的 D2，
原 cave `0x65c8411e` 不再可达），所以本仓库只在其源码处加了警示注释，
没有改动它的字节（改它会打破 `PATCHED_SHA256` 与系列补丁基线链条）。

修复：编码改为 `3B /r`（CMP r32, r/m32）= `cmp edx,[eax+ecx*4+THR2]`，
`jb done` 恢复为「战力 < 阈值 → 停」。

```text
RVA +0x35: 3b 94 88 b9 20 31 00   cmp edx, dword ptr [eax+ecx*4+0x3120b9]
```

**判据已固化**（防止回归）：

- 生成器 `patch_nameplate_series.py` 在 capstone 验证阶段断言
  阶梯比较的首字节必须是 `0x3B` 且 op_str 形如 `edx, dword ptr [eax + ecx*4...]`。
- 契约测试 `test_nameplate_series_contract.py` 额外断言同一件事，
  并端到端模拟档位映射（0/9999/1e4/…/1e10 → 乾元玄阶…无敌大帝）、
  抽查其它系列（400 万 → 中将/破面十刃/实习英雄）以及**单调性**
  （战力升高档位不得下降）。对修复前的产物运行会精确报出操作数颠倒。

修复后档位阶梯（玄幻，10000 → 100000 → 100万 → 1000万 → 5000万 →
2亿 → 5亿 → 20亿 → 100亿共 10 档；其它系列上限 8 档）：

| 战力 | 玄幻 | 斗罗 | 海贼 |
| --- | --- | --- | --- |
| < 1 万 | 乾元玄阶 | 魂师 | 海贼新秀 |
| 100 万 | 玄枢天宿 | 魂王 | 中将 |
| 400 万 | 玄枢天宿 | 魂王 | 中将 |
| 1000 万 | 星墟玄阙 | 魂圣 | 四皇候补 |

> 若 400 万战力希望直接拿到更高档位，需要下调阈值表，而不是改这里的方向。

## 重定位修复（2026-09-24，手机黑屏崩溃）

症状：PC 正常，手机（Wine/Box86 跑同一份客户端）进图黑屏崩溃。

根因：基线的 `.reloc` 里带着 **7 条残留 HIGHLOW 条目**，指向早期补丁留下的
`0x90` 代码填充区。DLL 按首选基址加载时 delta=0，这些条目等于空操作（PC 上看不出
问题）；被重定位时加载器仍会按条目加 delta，把填充字节改成别的指令。实测手机上
DLL 落在 `0x78700000`（delta `0x12A80000`）：

```text
RVA 0x1EDC: 90 90 90 90  →  90 90 38 A3
RVA 0x1EDF 是真实跳转落点（.data+0x1F3 的 jmp 0x65C81EDF），
于是执行 A3 90 90 90 90 = mov dword ptr [0x90909090], eax → 写 0x90909090 访问违例
```

崩溃现场与推断完全吻合：`eax=0x78700000`（该块用 `call $+5/pop/add` 刚算出模块基址）、
`[esp+4]=base+0x59B0`、`esp=0x12E530` 与该块的参数布局逐字节一致。

处理：删除这 7 条（`0x1D87 / 0x1D9A / 0x1E64 / 0x1EDC / 0x2849 / 0x28CF / 0x28D8`），
重建 `.reloc` 块链（0x2B0 → 0x2A4）、清零 raw 尾部、重算 PE 校验和。
**文件长度不变，按首选基址运行时内存映像完全不变**，只影响重定位路径。

同类修复：`WzFileLogger.dll` 也有 2 条残留条目（`0x24EC` 压在 STUB_A 那个 `call` 的
rel32 上、`0x4413` 压在 CAVE_C 的 `jmp` rel32 上），重定位后调用/跳转目标变成野指针
——正是手机第二次崩溃（`eip=0x09616640`，栈顶返回地址 `WzFileLogger.dll+0x24EF`）的成因。
修复后 CheckSum `0x000101C4`。

### 另外两个曾被误判的 DLL（结论：都不要动）

用 `fix_dll_reloc_hygiene.py <dll>`（不带 `--apply`）可复现当前判定：

| DLL | 条目 | 目标值 | 判定 |
| --- | --- | --- | --- |
| `BeiDouDamageSkinCompat.dll` | 2（`0x1120`、`0x1196`） | `0x6FA4B63D`、`0x6FA49302` | **跨模块位移 `A−S`，必须保留**（`A` 落在本映像 `.text`，`S` 落在 `BeiDou.exe` 的补丁点）。重定位加上本模块 delta 后恰好指向正确位置，**删掉反而会让手机跳到未映射地址** |
| `Canvas.dll` | 1（`0x15A74`） | `0x507FFFFF` | 位于 `.rdata`（非可执行段），工具判 `review` 并保留。原版文件，未改动 |

> 最初这 2 条曾被当成"旧 ImageBase 时代的死值"，是**错误**结论。
> 判据随即升级：`displacement_site()` 会把 `value` 读作 `(本映像地址) − (宿主模块地址)`，
> 命中则归为 `displacement` 并 `KEEP`，只有真正落在填充区/指令中段的才叫 stale。
> 回归测试 `test_reloc_hygiene_contract.py` 覆盖了这条判据（含 2^32 环绕的负位移）。


## 协议

服务端 `0x17C` 的 enabled 字节复用为状态字节：

```text
0      = 未启用
1..9   = 系列 0..8 已启用
```

包总长度不变（15 字节），解包与状态表布局不变。

## DLL 改动

1. `0x1d31`：改为 `cmp byte [edi+8],0; je skip`，仅当状态字节为 0
   时跳过绘制（同时修正原补丁遗漏的条件跳转反转）。
2. 新增 PE 节 `.titles`（RWX），包含：
   （同时把 Cave_S/Cave_G 从 .text 尾部 slack 迁入本节：.text 的 VirtualSize
   恰好结束于 0x3FB4，旧位置在严格加载器上不可执行，会在首次解包时崩溃）
   - 新 D2（系列感知档位选择 + 称号查找）；
   - 8 档共用阈值表；
   - 9 系列 × 10 档称号（GBK，NUL 结尾）与 90 个 word 偏移。
   同时将已有 `.data` 节的 `VirtualSize` 从 `0x0c` 扩展到 raw 大小 `0x200`，
   覆盖 64 位战力补丁中的 `Cave_A/B/C...`，避免严格加载器在 `+0x400c`
   执行访问违例。
   `.rdata` 的 `VirtualSize` 也扩展到已有 raw 大小 `0xa00`，覆盖原战力补丁
   使用的显示格式串。
3. `0x1e60` 跳转重定向到新 D2；旧 D2 保留为死字节。
4. 系列号钳制在 0..8，越界回退玄幻系列；非玄幻系列档位上限为 8。

## 服务端

- `Character.nameplateTitleSeries`：内存字段 + 角色扩展数据持久化
 （`nameplate_title_series`），`set` 方法钳制、保存并广播。
- `PacketCreator.nameplatePowerUpdate(Character)`：发送 `series+1` 或 `0`。
- `AbstractPlayerInteraction`：9 个 `NAMEPLATE_SERIES_*` 常量与
  `get/setNameplateSeries`。
- `gms-server/scripts/npc/9900002.js`：称号系列选择 NPC 脚本
  （挂到任意 NPC ID 即可；注意不要覆盖已有 `9900000.js`）。

## 系列 ID

0 玄幻 / 1 斗罗 / 2 龙珠 / 3 火影 / 4 海贼 / 5 死神 / 6 鬼灭 / 7 咒术 / 8 英雄学院。

## 回滚

用 `backup/` 下的基线 DLL 覆盖 `clien/BeiDouSetItemCompat.dll`，
服务端改动 revert `Character`、`PacketCreator`、`AbstractPlayerInteraction` 及对应测试即可。

## 已完成的静态验证

- `test_nameplate_series_contract.py`：PE 节属性、CheckSum、跳转点、GBK 称号表、
  旧文件区域差分、**重定位条目全部指向映像内地址**（这项在修复前的产物上会失败并列出那 7 条）通过。
- 生成器从基线重建两次；第二次报告 `already patched`，SHA-256 保持不变。
- Python 语法检查和 `git diff --check` 通过。
- 服务端 `NameplatePowerPacketTest` 已更新，但本机只有 JDK 17，Maven 编译器要求 JDK 21，尚未在本机执行通过。

运行时仍需在 Windows 客户端验证：替换 DLL 后重启虚拟机/客户端，确认名牌戒指启用、切换 9 个系列、禁用/重新启用、其他玩家视角及重复切换均无崩溃或乱码。用 `certutil -hashfile` 与本机 SHA-256 核对实际加载文件。
