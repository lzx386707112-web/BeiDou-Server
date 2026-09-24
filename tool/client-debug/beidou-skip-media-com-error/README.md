# beidou-skip-media-com-error

`BeiDou.exe` —— 媒体/资源加载失败时**跳过播放、不再抛 `_com_error`** 的 1 字节补丁。

## 症状

2026-09-23 20:11 会话（`clien/diagnostics/session-20260923-201148-pid7388.log`）：

```
first_chance_cpp occurrence=1/2/3 code=0xe06d7363 exception_info="i0=0x19930520;..."
flash_render_guard action=skipped_null_movie
process_exit code=0
```

随后客户端弹出错误框（`HRESULT = 0x80030002` / `-2147287038`，`STG_E_FILENOTFOUND`）并退出。

`0xe06d7363` + `i0=0x19930520` 是 MSVC 的 C++ 异常魔数，对应 MSVC COM 支持库的 `_com_error`。

## 根因

`BeiDou.exe` 里一个通用 COM 包装函数（模板实例化的 `_com_ptr_t` 风格 `CreateInstance`，
地址 `0x403a93`，`ret 0x10`，被 964 处调用）在媒体/资源接口虚调用返回失败时，直接抛 `_com_error`：

```
403ae4  ff 51 1c          call  dword ptr [ecx+0x1c]   ; 媒体/资源接口虚调用，返回 HRESULT
403ae7  85 c0             test  eax,eax
403ae9  7d 0c             jge   0x403af7               ; S_OK -> 跳过抛出（正常收尾）
403aeb  68 18 83 bd 00    push  0xbd8318              ; riid = 硬编码 IID 常量
403af0  53                push  ebx                   ; pUnk（本轮为 0x0a769604）
403af1  50                push  eax                   ; hr   = 0x80030002
403af2  e8 fb c2 65 00    call  0xa5fdf2              ; _com_raise_error -> 抛 _com_error
403af7  8b 4d 08          mov   ecx,[ebp+0x8]          ; 正常收尾（成功路径也落到这里）
```

抛点由转储交叉确认：`first-chance-cpp-20260923-201148-pid7388-17723343.dmp` 的
`_com_raise_error` 帧里 `[ebp+8]=0x80030002`(hr)、`[ebp+0x10]=0x00bd8318`(riid)，
与 `0x403aeb` 处的 `push 0xbd8318 / push ebx / push eax` 压栈顺序完全一致。

- `0xa5fdf2` 反汇编即为 `_com_raise_error(hr, pUnk, riid)`：先 `QueryInterface` 取 `IErrorInfo`，
  再构造 `_com_error` 并 `_CxxThrowException`。
- `0x00bd8318` = IID `{57DFE40B-3E20-4DBC-97E8-805A50F381BF}`，出现在 `ResMan.dll` / `BeiDouWeatherCompat.dll`，
  是客户端自定义的媒体/资源接口，**不是**系统接口。该 IID 也以立即数形式硬编码在 `0x403aeb`，
  所以日志里的 riid 是抛点签名（`0x5cad2f` 的备选抛点走 `_com_issue_error`，只带 hr、不带 riid，
  可据此排除）。

## 修法

把 `0x403ae9` 的 `jge +0xc`（`0x7d`）改成长跳 `jmp +0xc`（`0xeb`）——**1 字节**。

成功路径原本就跳 `0x403af7`，改成长跳后失败路径也落到同一个正常收尾，
于是失败被当作"没有可用对象"，沿调用链自然降级：

1. `0x403af7` → `0x403af7: mov ecx,[ebp+8]` → `call 0x4039ac`。
   `0x4039ac` 是 16 字节搬运：`memcpy(dst, &[ebp-0x20], 16)` 然后清源首字
   （`0x4039d5` 分支，第 3 参由 `0x403afa` 的 `push 0` 选入）。**与成败无关，不解引用任何可能为空的指针。**
   而 `[ebp-0x20]` 在 `0x403ab1` 已由 `call dword ptr [0xaf0268]`（空值构造）初始化。
2. 调用方 `0x5cac3d` 在 `0x5cad06` 用 `0x4032b2` 把该 16 字节转成指针，并**专门有空值分支**：

   ```
   5cad0b  cmp eax,ebx(0)
   5cad13  je  0x5cad36      -> mov ebx,0x80004002 (E_NOINTERFACE)，
                               走 0x5cad36 起的正常清理，全程不再 throw
   ```

   `0x4032b2` 在空值（`vt == VT_EMPTY`）上必然 `xor eax,eax` 返回 0：
   其第 3 参取 `[ebp+0xc]`，而该栈槽由 `0x5cacc0` 的 `push ebx`（`ebx=0`）写入——已按压栈序列
   （`0x403382` 为 `ret 0x4`、F_A 为 `ret 0x10`）逐字节对齐确认。

即：**媒体加载失败 → 静默跳过播放，不再抛 `_com_error`、不弹框、不退出。**

## 为什么 1 字节是安全的

- `0x403aeb..0x403af6`（死代码）在全 `.text` 扫描下**没有任何分支进入**（补丁脚本与契约测试各自独立验证）。
- 改动只落在 1 个代码字节 + PE CheckSum 的 4 字节字段（实测仅 3 字节变化），其余全文件逐字节相同。
- `BeiDou.exe` 是**固定 ImageBase**（`0x400000`）且 `DllCharacteristics = 0x0`（无 `DYNAMIC_BASE`、
  无强制完整性校验），原地改字节无需任何重定位。
- 死代码字节**保留原样**，便于比对与回退。
- 注意：`0xAEFA20` 处有加载器代码洞（加载 `DawnWarriorSkillCompat.dll`），本补丁不触碰它。

## 用法

```bash
# 干跑（只校验，不落盘）
/opt/homebrew/bin/python3 patch_skip_media_com_error.py --dry-run

# 落盘（自动备份到 backup/BeiDou.exe.orig）
/opt/homebrew/bin/python3 patch_skip_media_com_error.py --apply

# 契约测试（需要 capstone）
/opt/homebrew/bin/python3 test_skip_media_com_error_contract.py
```

契约测试会从函数入口 `0x403a93` 做**控制流可达性分析**，并给出差分结论
（基线：`0x403af2` 可达；补丁后：不可达），而不是只做字节比对。

## 基线 / 回滚

| | sha256 |
|---|---|
| 原始 `BeiDou.exe` | `06cdac314a6c91f3e133778aa7b72a829778549d4f14e3b95c3589fed541ba18` |
| 补丁后 | `0c6ea1643f27abf36447e714fbdfcdef7670290fe7418c41e049ef8b51ca9633` |

回滚：`cp backup/BeiDou.exe.orig ../../clien/BeiDou.exe`
（`clien/BeiDou.exe` 已纳入 git，也可用 `git cat-file blob HEAD:clien/BeiDou.exe` 取回原始基线。）

## 未覆盖 / 后续观察

- `0x5cad2f`（`call 0xa5fde4` = `_com_issue_error`）是同一调用方里**另一个**抛点。
  它只在 `0x4052ad` 返回"非 `E_NOINTERFACE` 的失败"时触发；本轮证据里从未命中
  （其产出的 `_com_error` 不带 riid，与日志中的 `i2=0x00b44b18` 不符，可排除）。
  本补丁刻意不动它——保持最小改动。若后续日志出现新的 `_com_error`，先看它是否带 riid：
  带 `0xbd8318` 才是本文件补的这条路径。
- 本补丁只解决"**失败即抛异常**"。若目标是"**正常播放**"，仍需补上缺失的媒体资源
  （`STG_E_FILENOTFOUND` 说明目标文件不存在）。
