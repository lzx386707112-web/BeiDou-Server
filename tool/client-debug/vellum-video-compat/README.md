# BeiDouVellumVideoCompat.dll —— 全职业 MCV 不播放的修复

> 2026-09-28。只改 `clien/BeiDouVellumVideoCompat.dll` 与其源码，**没有改动**
> `BeiDouSkillCompatCore.dll`、`KaringSceneCompat.dll`、`WzFileLogger.dll`、`BeiDou.exe`
> 或任何 WZ/IMG 资源（也**没有**改 `BeiDouVideo.dll`）。

## 一、问题

PC 客户端上**所有角色的 MCV 大招都不播放**（不是某个职业/技能的映射问题，MCV 文件本身
在移动端播放正常）。分两个阶段诊断：

```text
阶段 A（v1 测试后）
clien/BeiDouVideo.log
  player-skill: D3D8 device is not attached        ← 播放器手里没有 D3D8 设备

阶段 B（v2 测试后，设备已拿到，但仍无画面）
clien/BeiDouVideo.log
  player-skill: device attached
  boss-scene:    device attached
  player-skill: playback queued                    ← 核心已把视频塞进播放器
clien/VellumVideoCompat.log                        ← v2 交付，5 行
  LOAD: Vellum attack10/11 video compatibility v2 …
  BUILD: …
  OK: d3d8 Direct3DCreate8 code hook installed ahead of the client
  OK: runtime capture armed
  OK: the client's Direct3DCreate8 reached the capture hook
  OK: IDirect3D8 vtable is shared process wide
  OK: capture confirmed by a live D3D8 device
  OK: D3D8 device attached
```

即：**解码链路是通的、设备也挂上了，但没有任何一帧被画到屏幕上。**

## 二、根因

### 2.1 阶段 A：设备捕获的时间窗（v2 已解决）

```text
10:17:50.087   Vellum 兼容层加载（比游戏需要设备早约 2.5 s）
10:17:52.578   GR2D_DX8.DLL 加载
10:17:52.606   D3D8.DLL 加载            ← 仅隔 28 ms
               ↑ 紧随其后 Gr2D 就 GetProcAddress + Direct3DCreate8 + CreateDevice（微秒级）
```

v1 的兜底是**每 10 ms 轮询 `GetModuleHandleA("d3d8.dll")`**，必然晚几毫秒，
`HookCreateDevice` 永远等不到。旁证：v1 日志最后一行的"捕获成功"之后再无一行，
`HookLoadLibraryA` 本该在 Gr2D/D3D8 加载时各打一行却没有。

> 附带结论：诊断器 `WzFileLogger.dll` 会在**每次模块加载时重写
> `BeiDou.exe+0x00AF00C0`**（转储里 Vellum 保存的"原函数"指针落在 `WzFileLogger`
> 地址区间内），把别人的 `LoadLibraryA` 钩子挤出链外 → **任何依赖 IAT 槽的捕获都不可靠**。

**v2 的修法**：预加载 `d3d8.dll` → 给 `d3d8!Direct3DCreate8` 函数体打 5 字节 `jmp`
（带 trampoline）→ 拿到客户端自己的 `IDirect3D8*` → 直接改 `vtable[15]`。实测有效。

### 2.2 阶段 B：**渲染被自己的"最外层"判定丢掉了**（v3 修复）

v2 的 `HookPresent` 里有一道门：

```cpp
if (!gRenderedThisFrame && gRender != nullptr && IsOutermostPresentHook(device) &&
    AnyChannelHasVideo()) { … gRender(); }
```

`IsOutermostPresentHook()` 读设备 `vtable[15]` 与自己比较。**它恒为假**，因为
`KaringSceneCompat.dll` 把它的 Present 钩子链在**我们之上**：

* 运行时证据：`clien/KaringSceneCompat.log` = `OK: chained after Dawn D3D8 hooks`
  （它是在我们的钩子装好之后才装的）；
* 反汇编证据（`clien/KaringSceneCompat.dll`，基址 `0x6D840000`）：

  ```asm
  6D84148C  lea  eax,[ebx+0x3c]        ; ebx = 客户端设备对象 → vtable[15] = Present
  6D8414A7  mov  [0x6D84313C],eax      ; 保存"上一层" = 本模块的 HookPresent
  6D841489  mov  [ebp-0x1c],0          ;
  6D841484  mov  edx,0x6D8416C8        ; Karing 自己的 Present 钩子
  6D84148F  call 0x6D8412E7            ; 写回 vtable[15]
  …
  6D8416C8  …                          ; Karing 的 Present 钩子
  6D84176E  call dword ptr [0x6D84313C] ; ← 每帧无条件回调我们的 HookPresent
  ```

  （它同时对 `[ebx+0xf4]/[ebx+0x118]/[ebx+0x11c]/[ebx+0x120]/[ebx+0x124]` 也就是
  SetTexture / 四个 Draw* 做了同样的链式接管——正是我们装的那 6 个槽，与转储里
  "Karing 数据段中 6 个指向 Vellum 的指针"完全对应。）

所以我们的 `HookPresent` **每帧都在跑**，只是 `vtable[15]` 此刻指向
`0x6D8416C8`（Karing），判定"我不是最外层" → 一帧都不画。

而另外两个可能渲染的层都不画：

* `KaringSceneCompat` 只在**它自己的 boss-scene 视频** 播放时才调 `BDV_RenderAll`
  （`0x6D8416C8` 开头 `cmp byte ptr [0x6D8430A0],0`，为 0 时直接跳到 `0x6D84174C`
  透传，从不进渲染分支）；
* v69 核心自己的 field-layer 钩子从未装上
  （`DawnWarriorSkillCompat.log: VIDEO ERROR: no complete D3D8 field-layer hooks were
  installed within 30 seconds`）。

**结论：除本模块外没有第二个人会画 player-skill 通道，因此渲染绝不能以"我是不是最外层"为前提。**

## 三、修复设计（v3：捕获沿用 v2，渲染与钩子位置无关）

1. **删掉 `IsOutermostPresentHook` 与那道门**。渲染条件只剩
   "有任一通道处于 `DECODING/PLAYING`" + "本帧还没画过" + `gRender != nullptr`。
   `HookPresent` 尾部依旧照原顺序 `gRealPresent(...)` → 复位 `gRenderedThisFrame`，
   所以每帧最多画一次、且画在真实 Present 之前（在最上层）。
2. **新增通道健康日志**（每 2 s 一条，仅当通道非 IDLE）：
   `VELLUM VIDEO STATUS: channel=… state=… decoded=… displayed=… dropped=… position=…ms`
   ——把"解码器没出帧（state=1 decoded=0）"、"出了帧但没上传（decoded>0 displayed=0）"、
   "正常在画"三种情况区分开；`state=4` 时附带 `error="…"`。
3. **首次真正出图时打一行**（v7 起该行只属于兜底路径）
   `OK: video frames are presented through the chained Present hook`（一次性），
   用来把"钩子在跑但没画"和"画了但用户看不见"区分开；v7 把这条 OK 改成了
   `WARN: Present fallback active`（见第十节），标记路径另有
   `OK: field-effect marker draw; the video is rendered at the skill effect layer`。
4. **减少噪声/泄漏**：客户端每次会话会调 `Direct3DCreate8` **301 次**；v2 每次都建一个
   探针接口（且**故意不 Release**，见下）并打两行日志。v3 把探针与证据行都限制为**首次**。
   > 探针仍然必须不 Release：若 d3d8 给的是每对象虚表，Release 会把刚打补丁的字节还回去，
   > 那就从"无害空操作"变成首机会崩溃。

## 四、验证

1. **基线可复现**：v1 之前的源码可**字节级**重建出厂二进制
   （`9cf5cbccdd1cd28fae9f2994fc4e24cf50c4644a55d54b8d649079fb1fb91e3f`）；
2. `test_contract.py` **23 项全过**，含八条硬约束：
   * 出厂 DLL 必须能由当前源码重建（防"改了没发"）；
   * **代码里不得再出现任何 IAT 槽**（注释可提及，断言只扫去注释后的代码）；
   * **`IsOutermostPresentHook` 不得再出现在代码里**（v3 的核心回归）；
   * **入口补丁宽度必须由 `RelocationLength` 决定**，`PrologueIsRelocatable` 与
     `kCreateDeviceSlotPatchSize` 不得再出现（v4 的核心回归，见第七节）；
   * **标记签名的判定只能有一份定义**（`IsFieldEffectMarkerA4R4G4B4/A8R8G8B8` 不得出现在
     `.cpp` 里，必须走 `MarkerSignature.h`）、`ConsumeMarkerDraw` 必须先清 `gMarkerBound`
     再 `gRender()`、`StartVideo` 只能挂在 `kVellumScene` 分支上（v7，见第十节）；
   * **出厂文件大小不得等于任一历史版本**（共享目录按大小缓存，等长替换会被静默忽略）；
   * **首机会观察者必须恒返回 `EXCEPTION_CONTINUE_SEARCH`**、阈值 0 必须等于"完全不装"、
     每次会话最多落一份转储（v5，见第八节）；
   * **每一次异常都必须带调用点采样**，且采样只能取自异常自己的 `Esp`、只保留落在主程序
     image 内的 dword、窗口与候选数都有上限（v6，见第九节）；
3. `PrologueRelocation.h` 无 Windows 依赖，`test_contract.py` 用本机编译器把它编译成
   一个小的宿主 harness，**17 个真实序言样例**逐条断言重定位宽度（含 v3 崩溃那个
   `C7 45 …` 落在偏移 4 的样例，以及相对跳转 / 绝对地址 / 0x0F / 窗口耗尽等必须拒绝的样例）；
3b. `MarkerSignature.h` 同样无 Windows 依赖，第三个宿主 harness 用 **20 条断言**钉住两个
   标记族的字节：FIELD_EFFECT 的 `F123/F456/F789/FABC` 与 `FF112233/FF445566/FF778899/
   FFAABBCC`（`X8R8G8B8` 忽略 alpha）、两个近似误判必须拒绝、Root Abyss 第五像素的 code
   5/6 与其它的 code 必须为 0，以及**两族必须互斥**——`00AABBCC` 是 FIELD_EFFECT 的第 4、
   Root Abyss 的第 3 个像素，只能用完整四像素判定，不能只看一个像素（见第十节）；
4. `FirstChanceFormat.h` 同样无 Windows 依赖，第二个宿主 harness 用 **34 条断言**固定住
   证据采集的语义：阈值 0 == 关闭、第 N 次才落转储且只落一次、摘要条数有上限、
   转储文件名逐字符比对、缓冲区不足必须整体失败、`0x19930520`/对象偏移 `+4`/HRESULT 命名、
   以及调用点采样的逐字符格式（`stack="s49:+0x3fd5b* s52:+0xa497"`）；
5. 两次构建哈希一致（`--no-insert-timestamp`）：
   `4ca5c1c7a734541425f4017c089977b81d3ea77572411fdb064dec7f6f05ae5d`；
6. 反汇编核验 `HookPresent`（v5/v6 布局 `0x69141a30`–`0x69141b46`；v7 因代码增长整体后移，
   新址见第 10 条）：
   * **通篇没有对本模块 `HookPresent` 地址的比较**，渲染分支只由
     `cmpl $0x0,0x69144040`（`gRender`）、通道状态循环（`call *0x6914403c` = `BDV_GetStatusEx`）
     与 `cmpb $0x0,0x69144007`（`gRenderedThisFrame`）决定；
   * 渲染块顺序：`movb $1,0x69144007` → `movb $1,0x69144006`（`gRenderingVideo`）
     → `call *0x69144040` → `movb $0,0x69144006` → 首次打确认行 → `call *0x69144030`（真 Present）；
7. 反汇编核验首机会观察者（v5/v6 布局 `0x69141f1c` 注册、`0x69142cdc` 回调）：
   * `mov dword ptr [esp+4], 0x69142cdc` + `mov dword ptr [esp], 1`
     → `call [0x69148094]`，即 `AddVectoredExceptionHandler(1, HandleException)`（链首）；
   * 回调里 `cmp dword ptr [eax], 0xe06d7363` 精确过滤、`lock xadd` 计数、
     `xchg` 占用"已落转储"标志、`rep movsd 0x14`（80 B = `EXCEPTION_RECORD`）、
     `rep movsd 0xb3`（716 B = `CONTEXT`）；
   * **回调只有一个出口**：`lea esp,[ebp-0xc]` → `xor eax,eax` → `pop`×4 → `ret 4`，
     所有提前分支（`je 0x69142dde` ×9）都汇到这里，即恒 `EXCEPTION_CONTINUE_SEARCH`；
   * 采样循环可验证：`mov esi,[eax+0xc4]`（`CONTEXT.Esp`）、`cmp esi,0xffff`（拒绝野栈）、
     `mov dword ptr [esp+0xc], 0x180`（窗口 = 384 B = 96 dword）、
     `lea edx,[esi-5]` + `mov dword ptr [esp+0xc], 5`（前置 `call` 校验读 5 字节），
     每次 `ReadProcessMemory` 后都 `test eax,eax / je`，失败即放弃采样；
   * `gExeBase`/`gExeEnd` 来自自己的 PE 头：`mov eax,[eax+0x50]`（`SizeOfImage`）、
     `test eax,eax / je`、`mov [0x69146000]`/`mov [0x69146004]`；
8. 导入表仍只有 `KERNEL32.dll`（`dbghelp.dll` 运行时解析）；`.reloc` 巡检（v7 交付）：
   **342 条 / 0 僵尸 / 0 跨模块位移**（`fix_dll_reloc_hygiene.py` 报 `[clean]`）；
9. 文件 17920 → **18944** → **20480 字节**（与历史版本均不同，含未交付的 v7 中间构建 19968）。
10. **v7 反汇编核验（本交付）**：
   * `DetectMarker` 的签名比较只此一处：`cmp $0xf123,%cx`（`0x69142069`，A4R4G4B4）、
     `cmp $0x112233,%ecx`（`0x69142134`，`X8R8G8B8` 路径前先 `and $0xffffff,%edx`），
     紧随其后的 `cmpw $0xf456/$0xf789/$0xfabc` 与 `cmp $0x445566/0x778899/0xaabbcc`；
   * `HookSetTexture`（`0x691421b3`–`0x691421eb`）：
     `mov %ecx,0x69147788`（`gMarkerKind`）→ `mov %edi,0x69147784`（`gMarkerCode`）
     → `setne 0x6914778c`（`gMarkerBound = kind != 0`）→ `dec %ecx` + `cmove`
     在 `0x69145941`（FIELD_EFFECT 行）与 `0x69145979`（Vellum 行）之间二选一，
     并 `movb $1,0x69147776`（`gMarkerSeenLogged`）**每会话只打一次**；`kind == 0` 时
     `je 0x691421f0` 直接透传，不做任何日志或状态写入；
   * `ConsumeMarkerDraw`（`0x691419f0`–`0x69141b70`）：入口先验
     `cmbb $0x0,0x69147777`（`gRenderingVideo`）与 `0x6914778c`（`gMarkerBound`），
     然后 `cmpl $0x2,0x69147788` + `mov 0x69147784,%esi`，**之后立刻**
     `movb $0,0x6914778c` / `movl $0,0x69147788` / `movl $0,0x69147784`
     ——即"只吞标记自己那一次 draw"；渲染块为
     `incl 0x69147770`（`marker_frames++`）→ `movb $1,0x69147779`（`gRenderedThisFrame`）
     → `movb $1,0x69147778`（`gRenderingVideo`）→ `call *0x691477b8`（`gRender`）
     → `movb $0,0x69147778`，即**画在标记 draw 的位置上**，不在帧末；
     `StartVideo` 只在 `cmpl $0x2` 相等（`kVellumScene`）且
     `gVideoPlaying`(=0x69147780) 为 0 或 `gActiveMarkerCode`(=0x6914777c) 不等时才进；
   * `HookPresent` 的兜底块只认 `!gRenderedThisFrame && gRender != nullptr && 通道活动`，
     先 `incl 0x6914776c`（`present_fallback_frames++`）再打
     `0x69145344`（`VELLUM VIDEO WARN: Present fallback active…`），且每帧只查一次通道
     （`call 0x69141000` = `AnyChannelHasVideo`，结果 `al` 同时喂兜底与
     `TrackPlaybackLayer`）；
   * 帧末复位：`movb $0,0x69147778`（`gRenderingVideo`）、`gRenderedThisFrame`、
     `0x6914778c`/`0x69147788`/`0x69147784` 三个标记状态归零 —— 不会把本帧状态带到下一帧。



## 五、构建与回滚

```bash
# 构建（直接覆盖 clien/BeiDouVellumVideoCompat.dll）
bash tool/client-debug/vellum-video-compat/build.sh

# 契约（含"出厂二进制 == 源码重建"校验）
/opt/homebrew/bin/python3 tool/client-debug/vellum-video-compat/test_contract.py

# 回滚（backup/ 下逐档备份；v6 是上一档，v7 是当前交付）
cp tool/client-debug/vellum-video-compat/backup/BeiDouVellumVideoCompat.dll.orig \
   clien/BeiDouVellumVideoCompat.dll   # 出厂基线 7680
cp tool/client-debug/vellum-video-compat/backup/BeiDouVellumVideoCompat.dll.v1 \
   clien/BeiDouVellumVideoCompat.dll   # v1 8704（虚表探针 + 10 ms 轮询，失败）
cp tool/client-debug/vellum-video-compat/backup/BeiDouVellumVideoCompat.dll.v2 \
   clien/BeiDouVellumVideoCompat.dll   # v2 9216（设备已挂上，但一帧没画）
cp tool/client-debug/vellum-video-compat/backup/BeiDouVellumVideoCompat.dll.v3 \
   clien/BeiDouVellumVideoCompat.dll   # v3 10240（PC 可用，手机闪退）
cp tool/client-debug/vellum-video-compat/backup/BeiDouVellumVideoCompat.dll.v5 \
   clien/BeiDouVellumVideoCompat.dll   # v5 17920（观察者能落盘，但看不到抛点）
cp tool/client-debug/vellum-video-compat/backup/BeiDouVellumVideoCompat.dll.size18944 \
   clien/BeiDouVellumVideoCompat.dll   # v6 18944（能播，但盖住飘字与 UI）
```

> v4（11264，`64629462…`）**没有单独留存二进制**：它当时直接写进了 `clien/`，下一次构建
> 把它覆盖了。它的全部内容都在 v5 里（v5 = v4 + 观察者），所以回滚到 v4 没有意义；
> 真要退，退到 v3 即可。它的**尺寸 11264 已进退休表**，不会再被复用。

| 版本 | 大小 | sha256 | 结果 |
| --- | --- | --- | --- |
| 出厂基线 | 7680 | `9cf5cbccdd1cd28fae9f2994fc4e24cf50c4644a55d54b8d649079fb1fb91e3f` | 设备捕获不到 |
| v1 虚表探针 + 10 ms 轮询 | 8704 | `8c8c8be5cf5008882401983d877c23c954835c40e020cc741098c404b761bd99` | **失败**：补丁晚于建设备 |
| v2 d3d8 预加载 + 代码钩子 | 9216 | `d0e42d9aded5d1c991fdfe06ddebdc9a83132f62e9984471a1683332d4f82f83` | **半成功**：设备挂上、播放入队，**一帧没画** |
| v3 渲染与钩子位置解耦 | 10240 | `a14900bec1b035008c546e222a3ee34d666e5346a02e55b4c80756ba755cef7a` | **PC 可用**；**手机启动即闪退**（见第七节） |
| v4 整指令序言重定位 | 11264 | `6462946279a6363fcd3dd39e302cbdcbbacd6abab7e2ffecec53842731b6f339` | **PC 可用且已实测**（`relocated 5`、`decoded=117 displayed=106`）；手机未复测；未留存二进制 |
| **v5 + 首机会 C++ 证据采集** | 17920 | `9d19c8eece6f75bdf7c57d8f2fcea4513e114fc38adc8a0d2fb8d6231ee68e72` | **PC 实测可用**：14 次 `_com_error` 全部 `hr=0x80004003 E_POINTER`、落了一份转储；但转储太晚、引擎采样配额用光 → **看不到抛点**（见第九节） |
| v6 + 每次异常带调用点采样 | 18944 | `65f38a41c2003e0b2a73d74cf17fade7e8b5b58011ec6cc2359edce3c07032e9` | PC 实测可用（`stack=` 已能命名抛点）；**但视频画在帧末，讲飘字与 UI 一起盖住**（见第十节） |
| v7 中间构建（未交付） | 19968 | `6315b39f…` → `390f2839…` | 已实现 FIELD_EFFECT 标记识别，仅源码组织不同；**尺寸与最终版不同、未交付**，尺寸一并退休 |
| **v7 + 在 FIELD_EFFECT 层渲染** | **20480** | **`4ca5c1c7a734541425f4017c089977b81d3ea77572411fdb064dec7f6f05ae5d`** | 待真机验收（第十节） |

## 六、部署与运行时验收（需在 Windows 侧确认）

客户端经 `C:\Mac\Home\...` 读 macOS 共享目录时，**原地等长替换会静默失效**。
本次 18944 → 20480 已变化，但仍建议按可靠性顺序执行：① 重启虚拟机 / 手机容器的
Windows 环境 → ② 先 `del` 再 `copy`（源放本地磁盘）→ ③ `certutil -hashfile` 与 Mac 侧
`shasum -a 256` 核对，确认拿到 `4ca5c1c7…`。

进游戏放一次大招后按顺序看：

| 文件 | 期望 |
| --- | --- |
| `clien/VellumVideoCompat.log` | `LOAD: … v7 (d3d8 preload + whole-instruction code hook + FIELD_EFFECT layer render + first-chance C++ call sites)`；`BUILD: … v7 capture=whole-instruction-prologue layer=field-effect-marker present=fallback-only deterministic …`；两行 `LAYER: …`（本次会话的层级契约）；`FIRST-CHANCE: status=armed filter=0xe06d7363 …`；`OK: d3d8 Direct3DCreate8 code hook installed ahead of the client (relocated N whole prologue bytes)`；`OK: the client's Direct3DCreate8 reached the capture hook`；`OK: D3D8 device attached`；**`OK: FIELD_EFFECT marker texture recognised`**；**`OK: field-effect marker draw; the video is rendered at the skill effect layer`**；随后每 2 s 一条 `VELLUM VIDEO STATUS: channel=0 state=2 decoded=… displayed=… dropped=… position=…ms`；视频放完一条 **`VELLUM VIDEO SUMMARY: marker_frames=N present_fallback_frames=0 (every frame was drawn at the skill effect layer)`** |
| `clien/BeiDouVideo.log` | `player-skill: device attached` + `player-skill: playback queued`（与 v2 相同） |
| `clien/VellumVideoCompat.log`（出问题时） | 每条 `FIRST-CHANCE CPP: occurrence=<n> … hr=0x80004003 E_POINTER stack="s49:+0x3fd5b* s52:+0xa497 …"` —— **`stack=` 里的 `*` 号项就是抛点**（第 9 节） |
| `clien/diagnostics/first-chance-cpp-*.dmp` | 第 1 次 C++ 异常时落盘；用 `dump_inspect.py exc/info/unwind` 分析。注意它是 worker 线程写的，只反映**已展开之后**的现场，抛点靠日志里的 `stack=` |
| 画面 | 各角色 MCV 大招正常播放，**且飘字/伤害数字照常显示**（不再被视频盖住） |

`FIRST-CHANCE: … exe=…` 这行先自证采样器是否就绪：`exe=unresolved` 表示 PE 头没读到，
此时每条异常的 `stack` 都会是 `(none)`；`exe=0x00400000+0xa94000` 才是正常。

`relocated N whole prologue bytes` 里的 **N 是判别 PC/手机 d3d8 的一等证据**：PC 上的
Microsoft d3d8.dll 报 `5`，手机上的 Wine 内置 d3d8.dll 报它自己序言所需的宽度（预期 **>5**）。
若手机上报的是 `5`，说明崩溃另有原因，请把那一行连同 `EquipSlotDiagnostic.log` 一起回传。

本轮日志自证（一眼定位，按"飘字是否还在"分诊）：

* 有 **`FIELD_EFFECT marker texture recognised`** → 标记找到了，插入点正确，飘字应当正常。
* **没有**那一行 → 服务端没发这个技能的 `FIELD_EFFECT`，或 `Map.wz` 丢了 7x5 节点；
  此时会出现 `VELLUM VIDEO WARN: Present fallback active` 且
  `VELLUM VIDEO SUMMARY … present_fallback_frames>0` —— **飘字就是被这一层盖住的**，
  要修的是资源/服务端侧（`CloseRangeDamageHandler`/`MagicDamageHandler`/
  `RangedAttackHandler` 的 `videoLayer` 表 + `Map/Effect.img` 节点），不是本 DLL。
* 有 `D3D8 device attached` 但连 `VELLUM VIDEO STATUS` 都没有 → 视频通道从未进入
  `DECODING/PLAYING`，核心根本没调 `BDV_PlayFileEx`，问题回到技能触发侧。
* 有 STATUS 且 `state=1 decoded=0` 一直不动 → VP8 解码没出帧；
  若 `state=4`，同一行会带 `error="…"`（播放器自己的错误文本）。
* 有 STATUS 且 `decoded>0` 而 `displayed` 不涨 → 帧上传失败（纹理创建/Lock 失败）。
* 画面正常但**飘字不见了** → 先看是不是走了兜底：`VELLUM VIDEO SUMMARY` 的
  `present_fallback_frames` 不为 0，就说明这个技能没拿到 FIELD_EFFECT 标记（第十节）。
* 有 `presented through the chained Present hook` 且 `displayed` 在涨，**但屏幕仍无画面**
  → 已超出本模块职责，下一个怀疑对象是绘制时序/覆盖层（届时看 `displayed` 是否等于
  `decoded` 以判断是否被丢帧）。

遗留观察项：

* 核心自己的 30 秒超时日志（`no complete D3D8 field-layer hooks…`）**仍会打印**，
  那是核心的判定，本次没动核心。
* **重复绘制的理论边界**：Karing 只在它自己的 boss-scene 视频播放时画全部通道。若某次
  同时有 boss-scene 与 player-skill 视频，同一帧可能被混合两次（只影响半透明像素的浓淡）。
  真出现可见叠影再按"仅对非 boss-scene 通道渲染"收敛，目前优先保证出画面。
* 想彻底根除诊断器抢槽，需让 `WzFileLogger.dll` 不再改写 `Gr2D_DX8` 的 `GetProcAddress` 槽
  （那对它没有诊断价值），但它无源码、字符串表被混淆，本次不动。
* 本次交付期间 `clien/*.log` 被清空过一次（`git status` 里那批 `D`），13:45 会话的原始
  `VellumVideoCompat.log` 已不在工作区；第十节引用的数字取自清空之前读到的 40941 字节副本。
  下轮请先备份日志再清。

## 七、手机闪退：5 字节函数体补丁的"指令边界"假设（v4 修复）

### 7.1 症状（2026-09-28 12:19 手机实机，`~/Downloads/diagnostics/`）

```text
12:19:14.929  session_start
12:19:16.070  GR2D_DX8.DLL 加载
12:19:16.082  D3D8.DLL 加载
12:19:16.097  event=crash code=0xc000001d address=022D0004 module="(unknown)"   ← 非法指令
12:19:20.082  event=process_exit api=ExitProcess code=3221225501
```

* 全程 `window=missing` / `client_window_ready=0` → **初始化阶段就死，根本没到登录**；
* `VellumVideoCompat.log` **停在最后一行** `OK: the client's Direct3DCreate8 reached the capture hook`；
* **先排除"文件没换"**：`which_build.py` 读出转储模块表 `BeiDou.exe` CheckSum `0x00825088`
  与磁盘一致，8 个 compat DLL 也逐一吻合 → 手机跑的就是当前交付。

### 7.2 证据链

1. 首机会异常寄存器（`EquipSlotDiagnostic.log`）：
   `code=C000001D eip=022D0004 eax=022D0000 edi=000000DC ebp=0012F3A8 esp=0012F36C`
   → `edi=0xDC` 正是 `D3D_SDK_VERSION`；`eax == eip-4` 是 `call *%eax` 的典型痕迹
   （eax 传被调地址）。
2. 反汇编 `clien/BeiDouVellumVideoCompat.dll`（ImageBase `0x69140000`，运行时基址 `0x78A30000`）：

   ```asm
   6914152d  push ebp / mov esp,ebp / push edi,esi,ebx / sub esp,0x1c   ← HookDirect3DCreate8
   69141536  mov  0x8(%ebp),%edi
   69141542  mov  $0x69143077,%eax ; call LogLine    ← "reached the capture hook"
   6914154c  mov  0x69144038,%eax                     ← gRealDirect3DCreate8
   6914155f  call *%eax                               ← ★ 调用 trampoline
   69141561  mov  %eax,%ebx                           ← 返回地址 RVA 0x1561
   ```

   转储里 tid 36 的栈上确有 `0x78A31561 [BeiDouVellumVideoCompat.dll+0x1561]`；
   回溯 tid 332（装载线程）得 `BeiDouVellumVideoCompat.dll+0x1FE2` 挂在 `BaseThreadInitThunk` 下。
3. 于是 **`eax = gRealDirect3DCreate8 = 0x022D0000`（trampoline 基址），
   `eip = 0x022D0004 = trampoline+4`**。`0x022D0000` 不属于任何模块，正是
   `VirtualAlloc` 分配的那一页；旁证：tid 332 的栈基址恰好压在 `0x022D0000` 正下方，
   转储只覆盖到该地址前一字节（所以 `mem 0x022D0000` 读不到——那页是代码页，不是栈）。
4. 结论：**崩溃发生在我们的 trampoline 内部第 4 个字节，异常是 `#UD`（非法指令）。**

### 7.3 根因

trampoline = `[原函数前 5 字节][E9 rel32 跳回 target+5]`，**这 5 字节必须落在整条指令边界上**：

* **PC**：`d3d8.dll` 是 **Microsoft 的 DX8 运行时**（真 Windows），`Direct3DCreate8` 序言的
  指令边界正好在偏移 5 → 拷贝合法 → 一直没暴露问题；
* **手机**：`d3d8.dll` 是 **Wine 的内置实现**（模块路径 `C:\windows\system32\d3d8.dll`，
  同机还加载了 `winex11.drv` / `winevulkan.dll`），序言边界落在偏移 **4**。

以 `53 55 8B EC C7 45 F8 00 00 00 00`（`push ebx` / `push ebp` / `mov ebp,esp` /
`mov dword ptr [ebp-8],0`）为例：

```text
v3 trampoline @022D0000:  53 55 8b ec | c7 e9 | 7b f9 31 76
                            └ 4 字节整指令 ┘  └ 本该是 C7 45 F8 00 00 00 00 的 ModRM
                                               0x45，被 trampoline[5]=0xE9 顶掉了
```

→ 偏移 4 解码为 **`C7 E9`**，`C7 /5` 的 opcode 扩展未定义 → **#UD**，
`eip = trampoline+4 = 0x022D0004` **与转储逐位吻合**。
（反证也成立：原函数里不可能存在 `C7 E9` 这种非法指令，只有"原本合法的 `C7 45 …`
被截断"才会产生它。）

同理受害的还有 `C6 45 …`（变 `C6 E9`）、`81 EC …`、`83 E4 …` 等一切起点落在偏移 3/4 的指令。

> **教训**：函数体入口挂钩**不能用固定宽度**，必须按整条指令决定宽度；
> "在 PC 上跑通"不能证明对另一份 `d3d8.dll` 实现也成立——这正是 AGENTS.md 说的
> "二进制契约是构建/编译器相关的"。

### 7.4 v4 修法

新增 `PrologueRelocation.h`（纯 C++、无 Windows 依赖，便于宿主单测）：

* `InstructionLength()`：返回单条指令长度，**拒绝**相对跳转（`E8/E9/EB/7x`）、`0x0F` 逃逸、
  `A0-A3` moffs、任意前缀、以及 `mod=0,rm=5` / SIB `base=5` 这类"只有 disp32 的绝对地址"
  （指令一搬走地址就失效）；
* `RelocationLength()`：从入口逐条累加，**首次 ≥5 字节即停在指令边界**并返回 N；
  任一字节不可搬迁则整体返回 0（假拒绝的代价只是退回探针路径，远好过半个指令进 trampoline）；
* `InstallDirect3DCreate8CodeHook()` 全面改用 N：`memcpy(trampoline, target, N)`、
  `trampoline[N]=0xE9`、跳回 `target+N`、入口写 `E9 rel32` + `(N-5)` 个 `0x90`、
  `VirtualProtect`/`FlushInstructionCache` 一律按 N；写入顺序依旧是
  **先位移、再填充、最后写操作码**（三处都走 `volatile`）；
* **PC 无回归**：N=5 时产出的每一个字节与 v3 完全相同（同一条 `jmp` 位移、同一次拷贝宽度），
  只有新日志行不同；
* 解码失败（返回 0）时落回原有的 `InstallProbeInterfaceHook`——只改 `IDirect3D8` 虚表、
  不执行任何生成代码。

### 7.5 验证

* `test_contract.py` **14 项全过**（v4 当时；v5 增至 **20 项**，见第四节与第八节），其中新增：
  宿主 harness 用本机编译器编译
  `PrologueRelocation.h`，**17 个真实序言样例**逐条断言宽度（含 7.3 那个偏移 4 的崩溃样例、
  以及相对跳转/绝对地址/`0x0F`/窗口耗尽等必须返回 0 的样例）；
* 新增硬约束：`PrologueIsRelocatable`、`kCreateDeviceSlotPatchSize` 不得再出现在源码里，
  patch 宽度必须来自 `RelocationLength`；
* 10240 进 `RETIRED_SIZES`；新尺寸 **11264**；`.reloc` 巡检 `192 条 / 0 僵尸 / 0 跨模块位移`。

### 7.6 遗留与边界

* 手机端 `d3d8.dll` 实体**拿不到**（本机全盘无该文件），无法直接反汇编 Wine 的
  `Direct3DCreate8` 去验证它确为 `C7 45 …`。结论建立在"崩溃地址 = trampoline+4 且异常为 #UD"
  这一逐位吻合的推导上，**属于高置信推断而非直接观测**；
* 本次启动即崩，`BeiDouVideo.dll` 因此从未加载（模块表里没有它）——那是结果不是原因；
  MCV 能否正常播放**仍未被验证**，要在不闪退之后才谈得上；
* 若手机上新日志报的 `relocated N` 是 `5`，说明崩溃另有原因，需回传该行继续查。

## 八、切图「无效指针」取证：首机会 C++ 异常观察者（v5 新增）

### 8.1 缺口

2026-09-28 13:11 会话（`clien/diagnostics/session-20260928-131114-pid5976.log`）：
`_com_error`（`0xE06D7363`）**抛了 19 次**，随后客户端弹「无效指针」框退出，
但 `diagnostics/` 里只有 `high-cpu-*.dmp` / `window-lost-*.dmp` / `exit-process-*.dmp`，
**没有** `first-chance-cpp-*.dmp`。而诊断层自己的 `cpp_limit=32` 只给前 8 次采了栈，
额度一满连摘要都不再记 —— 最后弹框那一次**查无实据**。

### 8.2 为什么会这样：诊断层是 `WzFileLogger.dll`，它的转储要"先被武装"

* 诊断层就是 `clien/WzFileLogger.dll`（43008 字节，**仓库内无源码**，字符串为 UTF-16，
  一直靠 `tool/client-debug/wz-file-logger-fix/patch_flash_slot_guard.py` 这类二进制补丁维护）。
  它写 `diagnostics/session-*.log`，也负责所有 `crash-*` / `high-cpu-*` / `window-lost-*` /
  `exit-process-*` / `flash-null-*` / `first-chance-*` 转储。
* 它**确实有** "first-chance C++ 异常就落盘" 的分支（字符串
  `event=first_chance_cpp action=dump_incident_context`），但这个分支**只在 flash 影片为空
  被捕获之后才武装**。证据来自唯一一次成功落盘的会话
  （`clien/diagnostics/session-20260924-082413-pid3136.log`）：

```text
08:25:48.899  event=flash_render_guard action=skipped_null_movie occurrence=1
08:25:48.900  event=flash_render_guard action=capture_first_null_context   ← 武装
08:25:50.860  event=first_chance_cpp occurrence=4
08:25:50.861  event=first_chance_cpp action=dump_incident_context          ← 只此一次
08:25:51.751  event=dump status=ok reason=first-chance-cpp path="…\first-chance-cpp-….dmp"
```

  13:11 会话的 `flash_null_skips=0`（视频正在正常工作，没有空影片）→ 没有武装 → 19 次异常
  一份转储都没有。
* 另外 `cpp_limit=32` 是**硬编码常量**（`first_chance_handler status=installed … cpp_limit=32 …`
  是一条固定字符串，不是 ini 项），所以"把额度调大"并不像文档早先假设的那样只是改个 ini 值。

### 8.3 为什么补在 vellum 模块里，而不是改诊断层

* 诊断层是**二进制、无源码、字符串混淆**，且 9/24 刚被手工补丁改过；要给它加开关，必须先
  逆向出它内部的 dump 入口与 ini 读取函数，再在它的代码洞里塞桩 —— 风险与收益不匹配。
* `BeiDouVellumVideoCompat.dll` 由 `DawnWarriorSkillCompat.dll` 在**启动早期**加载
  （`VellumVideoCompat.log` 第一行即证明），源码、构建、契约都在手里，**且不需要改任何加载链**。
* 观察者是**只读的旁观者**，与 vellum 的 D3D8 职责互不干扰（它只认 `0xE06D7363`）。

> 如果更希望这些行直接出现在 `session-*.log` 里，那就得改 `WzFileLogger.dll`；可以做，
> 但成本高一个量级（逆向 dump 入口 + 代码洞 + 重算 CheckSum），本轮先不做。

### 8.4 设计

* `AddVectoredExceptionHandler(1, HandleException)`，只处理 `ExceptionCode == 0xE06D7363`；
* **恒返回 `EXCEPTION_CONTINUE_SEARCH`**：不吞、不改、不重抛。反汇编已核：所有出口都是
  `xor eax,eax` + `ret 4`，客户端自己的 filter 看到的东西一字不差；
* **每次异常一行摘要**（每会话上限 64 行，防资源循环刷爆日志），把真实 HRESULT 解出来：
  MSVC 把 C++ 异常编码成 `RaiseException(0xE06D7363, 0, 3, {0x19930520, 对象指针, ThrowInfo})`，
  因此 `ExceptionInformation[1]` 就是抛出的对象指针，而 **`_com_error::m_hr` 位于对象 `+0x4`**
  （正是 `dump_inspect.py exc` 使用的偏移）。取值走 `ReadProcessMemory`，不可读时写
  `(unreadable)`，**绝不裸解引用**。这正好补上 13:11 会话缺的那半：到底是 `0x80004003`(E_POINTER)
  还是别的，以及抛点在哪；
* **第 N 次异常再落一份完整转储**（每会话只落一次），命名
  `first-chance-cpp-<YYYYMMDD-HHMMSS>-pid<PID>-<tick>.dmp`，写在 `<exe 目录>\diagnostics\`，
  与诊断层同目录、同风格；
  * 转储在**工作线程**里写：`MiniDumpWriteDump` 在 700 MB 进程上要一秒级，异常回调必须短;
  * 异常记录与 `CONTEXT` 在回调返回**之前**复制进静态区（原始记录活在工作线程看不见的栈帧里），
    并以 `MINIDUMP_EXCEPTION_INFORMATION` 传入，这样 `dump_inspect.py exc` 仍能读到 `params[1]`；
  * 用 `InterlockedExchange` 抢占"已落转储"标志，两个线程同时抛异常也只会写一份；
  * 转储类型 = `WithDataSegs|WithHandleData|WithUnloadedModules|WithIndirectlyReferencedMemory|WithFullMemoryInfo|WithThreadInfo`，
    **不含** `WithFullMemory`（700 MB 进程；栈 + 间接引用对象已足够）；
* `dbghelp.dll` **运行时解析**，导入表仍只有 `KERNEL32.dll`；
* 阈值 0 = **完全不装**：不挂钩子、不创建全局状态、不写日志。

### 8.5 开关

写在 `clien/beidou_diagnostics.ini`（**与诊断层同一个文件**，一个开关管两边）：

```ini
[diagnostics]
; 0 = 关闭；N > 0 = 每次异常记一行摘要（上限 64 行），并在第 N 次落一份转储
dump_first_chance_cpp_after=1
```

想抓"最后一次"的转储，把 N 调到比预期异常次数略大（例如 40）即可；**但定位靠的是摘要行**
（每一次的 `hr` + 抛点），转储只是补充调用栈。

### 8.6 使用

1. 部署新 DLL（见第六节）；
2. 复现切图；
3. 看 `clien/VellumVideoCompat.log`：

```text
FIRST-CHANCE: status=armed filter=0xe06d7363 summarize_limit=64 dump_after=1 ini="…\beidou_diagnostics.ini"
FIRST-CHANCE CPP: occurrence=1 code=0xe06d7363 tid=5572 address=0x0040a497 object=0x0a7162cc hr=0x80004003 E_POINTER
FIRST-CHANCE CPP: occurrence=2 code=0xe06d7363 tid=5572 address=0x0040a497 object=0x0a7162cc hr=0x80004003 E_POINTER
FIRST-CHANCE DUMP: status=ok reason=first-chance-cpp occurrence=1 error=0 path="…\first-chance-cpp-20260928-….dmp"
```

4. 需要更细的现场时用 `dump_inspect.py exc <dump>` 交叉验证：同一个对象指针、同一个 `+0x4`
   处的 HRESULT 应当与摘要行逐位吻合。

### 8.7 边界

* 手机端 `MiniDumpWriteDump` 走 Wine 的 dbghelp，**能否写成尚未验证**；失败时日志会给出
  `status=failed detail=load_dbghelp|missing_export|create_file`。**摘要行不依赖 dbghelp**，
  所以手机上一样能拿到 HRESULT 与抛点。
* 观察者**不修复**异常，它只保证下一次一定留下证据；`0x40A492` / `0x43FD4E` 这些站点的
  补与不补，要等拿到真实 HRESULT 之后再决定（P5 已挡的 `0x5CAC3D..0x5CF58C` 不在此列）。
* 安装点在 `InstallHooks` 里、`kExpectedImageBase` 校验之后：**换了宿主的 exe 什么都不会挂**。

## 九、v5 的实测结果与两个缺口（v6 修复）

### 9.1 实测（2026-09-28 13:45 PC 会话，`session-20260928-134516-pid9264.log`）

v5 在真机上**完全按设计工作**，而且第一次把 HRESULT 钉死了：

```
FIRST-CHANCE: status=armed filter=0xe06d7363 summarize_limit=64 dump_after=1 ini="…"
FIRST-CHANCE CPP: occurrence=1 code=0xe06d7363 tid=10384 address=0x75589e4f object=0x001adf74 hr=0x80004003 E_POINTER
…
FIRST-CHANCE DUMP: status=ok reason=first-chance-cpp occurrence=1 error=0 path="…\first-chance-cpp-…dmp"
```

* 该会话共 **14** 次 `_com_error`，**全部 `hr=0x80004003 E_POINTER`**；转储成功落盘。
  抛点由引擎的 `stack_candidates` 给出（前 8 次有，见 9.2）：

| occurrence | 时刻 | 对象 | 最外层 BeiDou.exe 帧 | 结论 |
| --- | --- | --- | --- | --- |
| 1–3 | 13:47:32.38–.40 | `0x001adf74` | `s49:0x40264D` → **`s52:0x40A497`** | 站点 **`0x40A492`**（`call 0x40263B` 型） |
| 4–8 | 13:47:41.35–59.94 | `0x001ae6a4` | **`s49:0x43FD5B`**（无 `0x40264D`） | 站点 **`0x43FD4E`**（**内联** `mov edi,0x80004003`） |
| 9–14 | 13:48:01–17 | `0x001ae6a4` ×4、`0x001ae050`、`0x001aeb58` | **`(sample_limit)`** | **未知** |

* `0x43FD4E` 的链上还有 `oleaut32.dll+0xC461C`（第 4–8 次都出现），说明该站点跑在
  **VARIANT/OLE 自动化**路径上；`0x40A492` 那条链是 `KERNEL32 + BeiDou.exe`，属媒体/资源侧。
* 同一个站点多次抛出时**异常对象地址逐位相同**（A 恒 `0x001adf74`、B 恒 `0x001ae6a4`），
  所以 `object=` 可以作为"是不是同一个抛点"的指纹；而 **`0x001aeb58` 在上一轮 13:11 会话里
  也出现过**（跨会话稳定），`0x001ae050` 只在本轮出现 → 第 9–14 次里至少有一个是**新抛点**。
* 本会话**不是崩溃**：无 `first_chance_av`、无 `event=crash`、无 `0xC0000005`；
  13:48:26.395 交给客户端 filter（`event=exception_filter action=preserved_client_filter`，
  本轮共 3 次，后两次在收尾路径上），之后 `window_lost` → `exit-process` 转储 → 退出。
  也就是说，用户看到的"无效指针"弹框，**内容就是 `_com_error(E_POINTER)`**。

### 9.2 缺口一：引擎的采样配额（`cpp_stack_samples=8`）

`event=first_chance_handler … filters=C0000005/E06D7363/80004003 cpp_stack_samples=8` ——
引擎每个会话只给 **8 次** C++ 异常采栈，第 9 次起写 `stack_candidates="(sample_limit)"`。
本会话最关键的 **第 13/14 次**（弹框之前最后两次，相隔 5 ms）正好落在配额之外，
于是"到底是哪个抛点"没有任何证据。**这不是崩溃原因，是取证缺口。**

### 9.3 缺口二：v5 的转储太晚，看不到抛点

v5 的转储由 worker 线程写（为了不在异常回调里跑 `MiniDumpWriteDump`），
代价是**故障线程已经展开过 throw 帧**：

* 转储里 `EXCEPTION` 流的 `CONTEXT.Esp = 0x001ADED0`（抛出点），
* 而 ThreadList 给该线程的 `Stack.StartOfMemoryRange = 0x001AE780`、`Stack.Rva = 0`
  （**描述符是空的**），内存表里实际覆盖的段是 `0x001AE6EC..0x001B02F0` ——
  全部**在抛出点之上 2.2 KB**，throw 帧不在里面。
* 实测用 `dump_inspect.py rets` 读这份转储，拿到的是**展开之后**的链
  （主线程当时在 `Gr2D_DX8.dll+0xA113` 渲染路径上），而不是抛点。
* 附带修好了工具的一处缺陷：`read_threads` 给的是空描述符时，旧的 `stack_bytes()`
  只认"起点完全相等"，于是自家转储全都报"栈未落在转储里"。
  现在会退化为"取包含 `st_start` 的那一段"（`dump_inspect.py`，2026-09-28）。

### 9.4 v6 修法

* **每次异常都采一次栈，且在异常现场采**：`HandleException` → `SummarizeOccurrence`
  末尾追加 ` stack="…"`，取自 `ContextRecord->Esp`（与引擎同一取法），窗口 **96 dword**（384 B）。
* **只保留落在主程序 image 内的 dword**：所有抛点都在 `BeiDou.exe`，范围由自己的 PE 头
  `SizeOfImage`（`[image+0x50]`）算出，写进 `gExeBase`/`gExeEnd`，**不硬编码尺寸**。
* **每个候选做"前置 `call`"校验**：读 `value-5` 起的 5 字节，必须是 `E8 rel32` 且目标落在
  主程序内 → 打 `*`。这样 UTF-16 字符串/常量不会混进采样（与 `dump_inspect.py rets` 同思路）。
* **有界**：窗口 96 dword、候选 ≤ 12 个、行缓冲 512 B；每次 `ReadProcessMemory` 都判返回值，
  失败即放弃采样（`stack="(none)"`），绝不因为取证把自己搞崩。
* 安装时打一行自证：`FIRST-CHANCE: … exe=0x00400000+0xa93d00 stack_dwords=96 …`。
* `dump_first_chance_cpp_after` 语义不变（第 N 次落一份完整转储），它现在是**补充**而非唯一证据。

### 9.5 下一步

拿到下一轮日志里的 `stack=` 就能直接命名第 9–14 次的抛点，再决定是否照 P5 的样式补站点。
注意 **`0x43FD4E` 不能照抄 P1 的 1 字节 `jne`→`jmp`**：跳过后 `0x43FD5B` 立刻把
`[ebp-0x18]`(=0) 当 `this` 传给 `0x43F71A`，几乎必然访问违例（见 `docs/崩溃诊断-切图无效指针-20260928.md` §十一）。

## 十、飘字被视频盖住：插入点错了（v7 修复）

### 10.1 症状

v3 之后视频能播了，但**"修改之后飘字就不显示了"，或"被动画遮挡了"**。
不是崩溃、不是解码失败、不是设备问题：视频在画，只是画在了错误的地方。

### 10.2 根因：本模块只认 Root Abyss 签名，从来不认 FIELD_EFFECT 签名

这版客户端（以及本项目自己的设计）把视频的层级交给**服务端发的 FIELD_EFFECT**：

```text
服务端  chr.sendPacket(PacketCreator.showEffect("customSkill/hero/spiritCaliberVideoLayer"))
        → Map/Effect.img 节点只有一张 7x5 Canvas、delay = 30000 ms
        → 客户端在技能特效层**每帧**绘制这一张小图
        → 兼容层在这一帧的这一次 draw 上改成调用 BDV_Render()，并吞掉标记本身
```

因为 delay 是 30000 ms，标记在整个视频期间**每帧都会被画一次**，所以这个插入点覆盖全程，
而且它位于技能特效层 —— **在飘字与 UI 之前**，这正是 `tool/client-video/README.md`
"最终层级方案"里写的"旧大帧版本伤害飘字正常"的那个已验证位置；
`docs/tools/beidou-video-dll-integration.md` 第 835 行的排查表也写着
"技能层压住 UI/飘字 → draw 插入点 → **优先使用已验证 FIELD_EFFECT marker 层，不要随意移到 Present**"。

本模块到 v6 为止只实现了 Root Abyss（`F357/F689/FABC/FDEF` + 第 5 像素 code 5/6）这一族，
**没有**实现 FIELD_EFFECT 那一族（`F123/F456/F789/FABC`，A8R8G8B8 为 `FF112233/FF445566/
FF778899/FFAABBCC`）。于是：

* `DetectMarker` 对每个技能都返回 0 → `gMarkerBound` 永假 → 标记 draw 照常交给客户端；
* `HookPresent` 的兜底成为**唯一**渲染路径 → 视频被画在 `EndScene` 之后、`Present` 之前，
  即**整帧最上层**，把怪物、飘字、UI 一起盖住。

13:45 那轮日志正好是这个状态：`BeiDouVideo.log` 只有 `player-skill: playback queued`
（核心按技能 ID 起播），`VellumVideoCompat.log` 只有 `channel=0 state=2→3 decoded=117
displayed=115` 与 224 条 STATUS —— 一帧都没走标记路径。

> 同一份签名判定在核心 `DawnWarriorSkillCompat.cpp`
> （`DetectVideoMarkerPixels`/`DetectVideoMarkerTexture`，code 0 即 FIELD_EFFECT 位置标记）
> 里是有的，但核心自己的 D3D8 field-layer 钩子从没装上
> （`DawnWarriorSkillCompat.log: VIDEO ERROR: no complete D3D8 field-layer hooks were
> installed within 30 seconds`，原因是它依赖 Gr2D 的 `GetProcAddress` IAT 槽）。本模块的
> d3d8 导出代码钩子是可用的那一条，所以签名判定必须补在这里。

### 10.3 v7 修法

1. **新增 `MarkerSignature.h`**（纯 C++、无 Windows 依赖、可被宿主 harness 编译）：
   `MatchesFieldEffectA4R4G4B4/A8R8G8B8`、`MatchesVellumA4R4G4B4/A8R8G8B8`、
   `VellumCodeFromA4R4G4B4/A8R8G8B8`。两族签名并存，**根 Abyss 的 code 5/6 也只在这里定义**
   （`.cpp` 里不再有第二份）。
2. **`DetectMarker` 返回 `Hit{kind, code}`**：`kFieldEffect`（位置标记，起播由核心负责）
   与 `kVellumScene`（位置 + 选片，code 5/6 映射到 `root-abyss-vellum-attack10/11.mcv`）。
   三个格式 `A4R4G4B4`（pitch≥8）、`A8R8G8B8`、`X8R8G8B8`（忽略 alpha，pitch≥16）都覆盖，
   尺寸仍是 7×5..8×8。
3. **渲染点从 Present 移到标记 draw**（`ConsumeMarkerDraw`）。渲染条件与核心一致：
   `gVideoPlaying || AnyChannelHasVideo()`，所以核心起的 player-skill 播放也会画在这里。
4. **只吞标记自己那一次 draw**：v6 之前 `gMarkerBound` 要到帧末 `HookPresent` 才清，
   于是标记之后、下一次 stage-0 `SetTexture` 之前的所有 draw 都被静默吞掉（本帧的
   飘字/特效若落在窗口里就会整段消失）。v7 在捕获 `kind`/`code` 之后立刻清
   `gMarkerBound`/`gMarkerKind`/`gMarkerCode`，只消费那一次。
5. **Present 明确降级为兜底**：日志改成 `VELLUM VIDEO WARN: Present fallback active
   (no field-effect marker was drawn)`，并新增每次播放一条
   `VELLUM VIDEO SUMMARY: marker_frames=N present_fallback_frames=M` ——
   `M>0` 就等于"这个技能的视频正在盖飘字"，且**原因在资源/服务端侧**。
6. **两条自证日志**：`FIELD_EFFECT marker texture recognised`（每会话一次，证明签名命中）
   与 `LAYER: …` 两行（把本次会话的层级契约写进日志，方便日后复核）。
7. `AnyChannelHasVideo()` 从每帧两次降到**一次**（同一个结果喂兜底与 `TrackPlaybackLayer`）。

### 10.4 为什么飘字就是被这一层盖住的

视频是**全屏** triangle strip（`BeiDouVideo.cpp` `DrawTextureLocked` 用完整 render target
尺寸，不沿用游戏的局部 viewport），所以画在 Present 就等于给整帧盖一张贴图；
画在标记 draw 则跟随特效层的原生顺序，飘字、聊天、HUD 都在它之后绘制。

### 10.5 边界

* 若某技能服务端**没发** `FIELD_EFFECT`、或 `Map.wz` 里缺 7x5 节点，本模块只能退回 Present，
  飘字仍会被盖住。本轮已核对的映射表包括
  `CloseRangeDamageHandler`（dawnWarrior/thunderBreaker/hero/paladin/darkKnight）、
  `MagicDamageHandler`（blazeWizard）、`RangedAttackHandler`（nightWalker/windArcher）与
  `ExplorerOtherSkillCompat.videoLayer()`；**新增技能必须同步补这两处**（表 + `Map/Effect.img`）。
* Karing/Lucid 的 boss-scene 标记（code 1..29）**仍然不归本模块管**：它们选片并起播在核心/
  `KaringSceneCompat`，本模块只在 `AnyChannelHasVideo()` 为真时把当前通道画到位置标记上。
  若将来出现"同一帧被两个模块各画一次"，按 README 第五节遗留项收敛为"只画非 boss-scene 通道"。
* 标记识别仍是"每帧每个 stage-0 `SetTexture` 一次 `GetLevelDesc` + `LockRect`"，
  与核心同策略；纹理尺寸过滤（7..8）保证了大头像/字体纹理不会进 `LockRect`。

