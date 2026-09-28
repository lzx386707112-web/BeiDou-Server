# BeiDou.exe `_variant_t(IUnknown*)` 空指针保护

## 现象

反复切换地图时客户端直接消失（`ExitProcess(0xC0000005)`）。
崩溃日志（`clien/diagnostics/session-20260924-082413-pid3136.log` 第 528 行）：

```
event=first_chance_av code=0xc0000005 address=00410FF5
  eip=00410FF5 esp=001ADA40 eax=0x00000000 ecx=0x001ada8c esi=0x001ada8c
  stack_candidates="s1:BeiDou.exe+0x0023a85d@0063A85D; ..."
```

转储 EBP 链（`crash-…-61741156.dmp`）：

```
#0 BeiDou.exe+0x10ff5      <- 崩在这里
#1 BeiDou.exe+0x23a538
#2 BeiDou.exe+0x239cad
#3 BeiDou.exe+0x129bcb  #4 +0x129305  #5 +0x3774b6
#6 +0x3762fe  #7 +0x37601d  #8 +0x96664  #9 +0x965c9  #10 +0x96218
#11 BeiDou.exe+0x5feb3d
#12 user32.dll+0x39693 ...  <- 窗口消息路径
```

## 根因

`BeiDou.exe+0x410FDF` 是被 **397 处**调用的极小叶子函数，就是 ATL 的
`_variant_t(IUnknown* pSrc, bool fAddRef = true)`：

```
410fdf  cmp  BYTE PTR [esp+0x8],0x0    ; fAddRef
410fe4  mov  eax,DWORD PTR [esp+0x4]   ; pSrc
410fe8  push esi
410fe9  mov  esi,ecx                   ; this
410feb  mov  WORD PTR [esi],0xd        ; vt = VT_UNKNOWN
410ff0  mov  DWORD PTR [esi+0x8],eax   ; punkVal = pSrc
410ff3  je   0x410ffb                  ; 只判断了 fAddRef
410ff5  mov  ecx,DWORD PTR [eax]       ; ★ pSrc==0 时读 0x00000000
410ff7  push eax
410ff8  call DWORD PTR [ecx+0x4]       ; AddRef()
410ffb  mov  eax,esi
410ffd  pop  esi
410ffe  ret  8
```

**缺少 `pSrc != NULL` 判断。**

调用方 `0x63A858`（UI / 地图刷新路径）在媒体对象拿不到时正好传
NULL + `fAddRef = true`：

```
63a850  push 0x1                    ; fAddRef = true
63a852  push DWORD PTR [ebp-0x14]   ; pSrc —— 此时为 0
63a855  lea  ecx,[ebp-0x38]
63a858  call 0x410fdf               ; ☠ 访问违例
63a85d  cmp  DWORD PTR ds:0xbf14ec,ebx  ; ← 作者到这里才检查媒体对象
63a867  jne  0x63a873
63a869  push 0x80004003                 ; E_POINTER，作者预留的错误路径
63a86e  call 0xa5fde4                   ; 抛 _com_error
```

也就是说：**作者写了"媒体对象为空"的处理分支，但它排在构造变体之后，
代码在到达那个分支之前就已经崩了。**

崩溃时栈上正好是三个参数：
`[001ada44]=0063a85d`(返回地址) `[001ada48]=0`(pSrc) `[001ada4c]=1`(fAddRef)。

## 改法

在 `0x410FF5`（6 字节，`0x410FF5..0x410FFA`）放一条 `call` 指向
`.text` 尾部空洞 `0xAEFE30`；桩内先判断 `eax`，`0x410FF3` 的
`je 0x410FFB` **原样保留**，返回地址落在 `0x410FFA` 的 `nop` 上。

```
410ff5  e8 36 ee 6d 00   call 0xAEFE30
410ffa  90               nop
aefe30  85 c0            test eax,eax
aefe32  74 06            je   0xaefe3a      ; pSrc==0 -> 跳过 AddRef
aefe34  8b 08            mov  ecx,[eax]
aefe36  50               push eax
aefe37  ff 51 04         call [ecx+0x4]      ; AddRef()
aefe3a  c3               ret
```

- **`pSrc != NULL` 时逐字节等价**：`mov ecx,[eax] / push eax / call [ecx+4]`
  三条指令原封不动搬进桩里（`mov`、`call` 的编码和操作数都一样）。
- **`pSrc == NULL` 时**得到合法的空 `VT_UNKNOWN` 变体（`vt=13`、`punkVal=0`），
  不再访问违例。
- 选空洞 `0xAEFE30..0xAF0000`（464 字节全零、**零入口**）；
  `0xAEFA20` 的 DawnWarriorSkillCompat 加载器 thunk 和 `0xAEFD80`
  的既有桩都在它**之前**（`0xAEFE2E` 是那个桩的结尾，未动）。

### 栈平衡

| 位置 | ESP |
|---|---|
| 进入 `0x410FDF` | `E` |
| `push esi` 后，`0x410FF5` 处 | `E-4` |
| `call 0xAEFE30` | `E-8` |
| 桩内 `push eax` | `E-12` |
| `call [ecx+4]` → AddRef `ret 4` | `E-8` |
| 桩 `ret` | `E-4` ✔ 与基线 AddRef 分支到 `0x410FFB` 时一致 |

`0x410FF3` 的 `je`（`fAddRef==0`）路径本就不经过任何 `push`，
到 `0x410FFB` 时 ESP 也是 `E-4`，两条路径一致。

## 文件

- `patch_variant_null_guard.py` —— `--dry-run` / `--apply`，
  自带 PE 布局断言、CheckSum 自检、基线字节校验、空洞全零校验、幂等。
- `test_variant_null_guard_contract.py` —— capstone 契约测试
  （基线缺陷存在性 + 补丁后桩结构 + `je` 跳过 AddRef + 无外部分支入口 +
  未触碰列表 + 字节差异清单）。用 `/opt/homebrew/bin/python3` 运行。
- `backup/BeiDou.exe.prevpatch` —— 本轮改动前的版本
  （`0c6ea164…9633`，已含 0x403AE9 的上一轮补丁）。
  更早的原始版在 `../beidou-skip-media-com-error/backup/BeiDou.exe.orig`
  （`06cdac31…ba18`）。

## 验证结果

```
CheckSum    : 0x0082a466 -> 0x00822279   （算法自检通过）
变化字节    : 19 处 = 6（补丁点）+ 11（桩）+ 2（CheckSum）
幂等        : 重跑报 already patched，sha256 不变
objdump     : 410ff5 call 0xaefe30 / 410ffa nop / 410ffb mov eax,esi
              aefe30 test eax,eax / je 0xaefe3a / mov ecx,[eax] / push eax / call [ecx+4] / ret
契约测试    : 全部通过（基线缺陷存在、补丁后无外部分支入口、尾声未变）
```

`PATCHED_SHA256 = 6e6fe237c6712d045a6644cc8608e425963a6ee9001e2d575ca1af4dec1e9cec`

## 已知遗留

1. 修好之后，如果全局媒体对象 `0xbf14ec` 也是 0，会走到 `0x63A869` 的
   `push 0x80004003`（E_POINTER）抛 `_com_error`。那是**作者自己写的**
   错误路径（日志里 `filters=…/E06D7363/80004003` 把它列为预期码），
   不是访问违例。要不要把这条也改成"静默跳过"是另一个决定。
2. 根因仍然是**某个媒体 / Flash 资源加载失败**（上一轮的
   `_com_error hr=0x80030002 STG_E_FILENOTFOUND`）。本补丁只消除崩溃，
   不补资源。
3. **必须确认虚拟机真的加载了这份二进制**——见交付说明里的哈希核对步骤。
