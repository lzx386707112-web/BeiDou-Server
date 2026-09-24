# WzFileLogger.dll flash 槽位野指针修复

针对 2026-09-23 20:15 那次 `WzFileLogger.dll+0x24F4` 访问违例（`0xC0000005`，读 `0x230EE088`）的二进制修复。
**未改动任何 WZ/IMG 资源**，只改 `clien/WzFileLogger.dll` 一个文件。

## 一、根因（转储 + 反汇编双重确证）

诊断 DLL 在检测到 `WzFlashRenderer.dll` 被加载时，把该模块内部两个**固定偏移**地址缓存成全局变量：

```asm
6dd05cd6: lea 0x14f0(%edi),%eax     ; edi = GetModuleHandleExW(FROM_ADDRESS,...) 返回的模块基址
6dd05cdc: cmp %eax,%ebx
6dd05cde: jne ...
6dd05ce2: lea 0x6e088(%edi),%eax    ; 硬编码偏移 0x6e088（渲染器 .data 里的全局槽位）
6dd05ce8: mov %eax,-0x82c(%ebp)
...
6dd05db1: mov %ebx,0x6dd509e4       ; g_flag = 模块基址 + 0x14f0（原始渲染函数指针）
6dd05db7: mov %eax,0x6dd509e0       ; g_slot = 模块基址 + 0x6e088（当前 flash 影片指针的槽位）
```

因此 **`g_slot ≡ g_mod + 0x6E088` 是构造性成立的**，不是猜测。转储实测：
`g_mod=0x23080000`（WzFlashRenderer 基址）、`g_slot=0x230EE088`、`g_flag=0x230814F0`，三个值在 5 个转储里完全一致。

问题在于有两处只做了 **NULL 判断**就去解引用：

```asm
6dd024ea: mov 0x6dd509e0,%ebx       ; 崩溃点A（退出期写最终状态快照）
6dd024f0: test %ebx,%ebx
6dd024f2: je   +2
6dd024f4: mov  (%ebx),%ebx          ; ← 崩在这里：ebx 非 NULL，但指向已卸载的模块

6dd04411: mov 0x6dd509e0,%esi       ; 崩溃类同点B（flash_render_guard 渲染拦截器）
6dd0441f: mov  (%esi),%esi          ; ← 同一类危险
```

客户端在异常退出流程里会卸载 `WzFlashRenderer.dll`（crash 转储的模块表比 flash-null 转储少 7 个模块），
但 `g_slot` 仍是旧值 → 非 NULL、不可读。退出时序：

```
20:15:02.063  event=process_exit api=ExitProcess code=0
20:15:02.064  event=first_chance_av            ; 1 毫秒后
```

顺带说明：`g_flag` 是同一模块内的函数指针，被 `6dd044a3  jmp *%eax` 尾调用 —— 模块卸载后它也是野指针。
本次修复让它走不到这条尾调用。

## 二、修复设计

在 `.text` 尾部既有的**全零填充区**（文件 0x5b00，RVA 0x6700；已确认 464 字节全 0）放一段校验桩，
两处解引用改为调用它：

```
value = (g_slot != 0
         && VirtualQuery(g_slot, &mbi, 28)
         && mbi.Type           == MEM_IMAGE      // 仍在某个已加载映像内
         && mbi.AllocationBase == g_mod)         // 且仍是**同一个**模块的映像
        ? *g_slot : 0
```

因为 `g_slot ≡ g_mod + 0x6E088`，`AllocationBase == g_mod` 恰好等价于
"WzFlashRenderer 的映像还映射着"，所以：

* 模块在时 —— 判定与老逻辑**完全一致**，不会误判（不会让 guard 永久跳过渲染）；
* 模块没了 —— 返回 0，语义正确（"没有正在播放的 flash"），同时避开野指针。

桩是 **位置无关** 的（全部用 rel32 调用/跳转和 EIP 相对位移），因为该 DLL 设了
`DYNAMIC_BASE`（运行时基址实测 0x70d40000 ≠ 0x6dd00000），所以**不需要新增重定位项**。

布局（RVA / 文件偏移）：

| 名称 | RVA | 长度 | 作用 |
|---|---|---|---|
| `STUB_A` | 0x6640 | 10 | `push eax; call COMMON; mov ebx,eax; pop eax; ret`，除 ebx 外全寄存器保持 |
| `COMMON` | 0x6650 | 84 | 校验 + 条件读取；`eax`=结果，`CF=1` 表示槽位不可用 |
| `CAVE_C` | 0x66b0 | 45 | 复刻 guard 原控制流：不可用→结语 `0x44a5`，影片为 0→`0x4425`，影片非 0→`0x4491` |
| 站点 A | 0x24ea | 12 | `call STUB_A` + 7×nop（原 12 字节） |
| 站点 C | 0x4411 | 14 | `jmp CAVE_C` + 9×nop（原 14 字节） |

另外把 `.text` 的 `VirtualSize` 从 0x5630 提到 0x5800（`SizeOfRawData` 本来就是 0x5800），
让填充区在段内"名正言顺"，保证该页以 RX 权限映射；并按标准算法重算 PE `CheckSum`。
文件大小不变（43008 字节），未新增段（NX_COMPAT 下数据段不可执行，所以必须复用 `.text`）。

## 三、验证结果

`test_flash_slot_guard_contract.py`（需 capstone，用 `/opt/homebrew/bin/python3` 运行）：

1. **逐字节 diff 图**：相对改动前的差异**只落在**声明的 16 个区间内（两处站点、三段桩、`.text` VirtualSize、CheckSum）；
2. 段布局：`.text` 0x1000..0x6800 为 RX，与 `.data`@0x7000 不重叠；
3. 两处站点分别反汇编为 `call 0x6dd06640` / `jmp 0x6dd066b0`；
4. 三段桩逐指令核对（助记符序列、每个分支目标、`VirtualQuery` IAT / `g_slot` / `g_mod` / `g_flag` 的位移全部命中预期地址，MBI 字段偏移 0x18/0x04 正确，`clc`/`stc` 位于最后一次改标志位指令之后）；
5. PE 校验和自洽；
6. 原 `mov (%reg),%reg` 无保护读取在两处均已消失。

另用 objdump（第二个工具链）独立反汇编复核了同样的桩，结果与 capstone 一致。

**行为仿真**（拿 5 个真实转储回放判定逻辑）：

| 状态 | 转储 | 结果 |
|---|---|---|
| WzFlashRenderer 已卸载 | `crash-...-17834890`、`window-lost-...-17836562` | 原逻辑 `FAULT(0xC0000005)` → 新逻辑返回 0，不解引用 |
| 模块正常加载 | `flash-null`、`first-chance-cpp`、`high-cpu`（3 个） | 原逻辑 `*g_slot=00000000` → 新逻辑 `*g_slot=00000000`（完全一致，无误判） |

安全性附加检查：被替换的三个区间**没有任何其它分支跳入**；站点 C 之后 0x441f..0x4424 的原指令按字节保留（成为不可达死代码），不做改动。

## 四、应用与回滚

```bash
# 应用（幂等：已打过会直接退出）
python3 tool/client-debug/wz-file-logger-fix/patch_flash_slot_guard.py

# 验证
/opt/homebrew/bin/python3 tool/client-debug/wz-file-logger-fix/test_flash_slot_guard_contract.py

# 回滚：直接用备份覆盖
cp tool/client-debug/wz-file-logger-fix/backup/WzFileLogger.dll.orig clien/WzFileLogger.dll
```

* 改动前：`1aa06ffb69353859b06671136c6373c9f0559d6d7c495ea5513ce832f483b53c`
* 改动后：`2099f66498bb0d64dcba7e183161b6405ee0476df54108bf0a0e3c746a99e217`
* 备份：`backup/WzFileLogger.dll.orig`（脚本首次运行自动生成）

脚本用 `apply_patch` 式的字节断言保护：目标文件不是已知基线、或原始字节不匹配时直接报错退出，绝不盲改。

## 五、本次**没有**覆盖的部分

`0x80030002`（`STG_E_FILENOTFOUND`）那个错误框是另一层问题：某次媒体/flash 载入失败，
被当作未捕获的 `_com_error` 抛出（`BeiDou.exe` RVA `0x73d8e9` 就是 MSVC `_com_error::ErrorMessage()` 的字符串表）。
本次修复只保证**它引发的退出流程不再二次崩溃**，不会让那个文件出现。定位缺失文件需要先补观测：

* `WzFileLogger.dll` 里有 `event=message_box` / `event=error_dialog` 钩子，但本次会话日志里 **0 条** —— 弹框文本目前抓不到；
* `clien/beidou_wz_access.log` 不存在，说明 `CreateFileW` / `CreateFileMappingA` 访问日志这次没落盘。

建议顺序：先让上述两条观测生效 → 复现一次拿到"打不开的那个路径" → 再决定是补资源还是在
`WzFlashRenderer!LoadMediaFile` 侧加兜底（把 HRESULT 失败转成"跳过播放"而不是抛 `_com_error`）。
