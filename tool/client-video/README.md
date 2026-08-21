# BeiDou MCV 视频流特效框架

本目录实现了一套面向旧版 32 位 `BeiDou.exe` / Direct3D 8 客户端的视频流特效框架。它用于承载 TMS 新版技能中的大尺寸 `Canvas#Video` 演出，避免旧客户端把视频拆成大量 WZ Canvas 后逐帧解码、上传纹理所造成的卡顿。

截至 2026-07-29，最终 FIELD_EFFECT 层方案已经在手机 Winlator 环境完成实机验证：

- 32 位客户端可以正常启动，不需要替换系统 `d3d8.dll`；
- `1280x720`、159 帧、带 Alpha 的 VP9 MCV 可以在游戏内播放；
- 相比 159 张 Canvas 帧，视频流播放明显更流畅；
- 服务端可以在视频期间继续执行正式技能的周期伤害逻辑；
- 视频已经从失败的 `effect/90` 实验层迁回旧大帧使用过的 FIELD_EFFECT 层，画面可以正常显示；
- 视频播完会释放纹理，不会继续停留在最后一帧；
- 三个正式技能共用同一套标记检测和绘制链路，伤害飘字、命中特效继续走旧客户端原生逻辑。

本次正式化新增了完整 render target 绘制、三个正式技能映射和三个新 MCV，并通过构建、资源静态校验和手机实机验证。

当前落地技能为：

| 正式技能 | 技能 ID | MCV | 帧数 | 时长 |
| --- | ---: | --- | ---: | ---: |
| 银河星爆 | `11121005` | `galaxy-star-burst.mcv` | 119 | 7140ms |
| 全蚀之力 | `11121006` | `eclipse-force.mcv` | 52 | 5220ms |
| 灵魂蚀日 | `11121008` | `soul-eclipse.mcv` | 159 | 20000ms |

三者均为 `1280x720` VP9 颜色流 + Alpha 流。独立测试技能 `11121013` 已删除，正式技能直接触发视频。

## 设计目标

这个框架解决的是旧客户端的资源和渲染瓶颈，而不是让旧 WZ 解析器直接理解新版 MS 节点。

传统 Canvas 方案需要把每一帧都存进 `Map/Effect.img` 或 `Skill.img`。大特效会产生以下开销：

- 启动或首次施放时解析大量 WZ Canvas；
- 每帧执行图片解压和像素转换；
- 大量独立纹理分配、上传和释放；
- WZ 文件膨胀，手机端内存和 I/O 压力显著增加；
- 帧数越多，卡顿和掉帧越明显。

MCV 方案把主动画压缩为连续 VP8/VP9 数据流，只保留有限数量的解码帧和 D3D 纹理。轻量背景、角色动作、伤害逻辑仍由原有 WZ 和服务端机制承担。

## 整体架构

```text
技能 11121005 / 11121006 / 11121008 被施放
        |
        +--> DawnWarriorSkillCompat.dll
        |      |
        |      +--> 按技能 ID 选择对应 Data\\Video\\*.mcv
        |      +--> 捕获真实 IDirect3DDevice8
        |      +--> 识别 Map/Effect 的 7x5 FIELD_EFFECT 标记纹理
        |      +--> 在旧大帧 FIELD_EFFECT 层调用 BDV_Render
        |
        +--> 服务端 CloseRangeDamageHandler
               |
               +--> 不再广播旧全屏 Map/Effect Canvas
               +--> 仅向施法者发送 7x5 FIELD_EFFECT 标记
               +--> 按各技能 TMS 时间轴执行周期伤害

MCV 文件
  --> 内存映射
  --> 校验 MCV0 头和帧表
  --> 后台线程解码 VP9 颜色/Alpha
  --> 3 帧 CPU 队列
  --> 渲染线程上传到 2 张 D3D8 纹理
  --> 全视口 Alpha 混合绘制
```

框架分成四层：

1. `MCV` 容器保存压缩后的颜色、Alpha 和时间轴。
2. `BeiDouVideo.dll` 负责读取、解码、排队、上传和绘制；播放器包含固定的 `boss-scene` 与 `player-skill` 两个通道。
3. `DawnWarriorSkillCompat.dll` 负责从旧客户端取得真实 D3D8 设备并触发播放。
4. 服务端和 WZ 继续负责技能等级、攻击包、周期伤害和轻量帧效果。

### 固定双通道

播放器只提供两个有界通道，不开放任意数量的视频实例：

| 通道 | API 编号 | 用途 |
| --- | ---: | --- |
| `player-skill` | `0` | 现有玩家五/六转全屏技能；旧 API 默认操作此通道 |
| `boss-scene` | `1` | Boss 转场和全屏场景；由后续 Boss 兼容路由触发 |

`BDV_Render()` 与 `BDV_RenderAll()` 都先绘制 `boss-scene`，再绘制
`player-skill`。同一通道的新播放仍会替换该通道内的旧播放，但不会停止另一个
通道。`BDV_PlayFile()`、`BDV_Stop()`、`BDV_GetStatus()` 和
`BDV_GetLastError()` 保持原有 ABI，并继续映射到 `player-skill`；新调用方使用
`BDV_PlayFileEx()`、`BDV_StopChannel()`、`BDV_GetStatusEx()` 和
`BDV_GetLastErrorEx()`。

Harness 默认保持单视频播放。要验证两个通道并发，使用竖线分隔玩家和 Boss
视频路径：

```text
BeiDouVideoHarness.exe "Data\Video\soul-eclipse.mcv|Data\Video\galaxy-star-burst.mcv"
```

咖凌 Boss 迁移使用 `boss-scene` 通道承载转场和全屏/近全屏大特效。当前导出
`karing-dark-pulse.mcv`、`karing-goongi-screen.mcv`、三兽
`karing-perils-*.mcv`、`karing-reward-screen.mcv` 以及三兽
`karing-clear*.mcv`，以及固定出生点播放的 P2/P3 `regen` 演出，共 14 个
VP9 + Alpha MCV。对应
`Map/Effect.img` marker 位于 `customSkill/karing/*VideoLayer`，进入
`karing_first`、`goongi_direction`、`dool_direction`、`hondon_direction`
地图脚本时由服务端发送 FIELD_EFFECT 触发。

## 最终层级方案和演进记录

视频解码本身不是这次层级问题的根因。旧大帧版本的伤害飘字正常，说明原 `Map/Effect.img` 的 FIELD_EFFECT 绘制时机已经满足技能演出的层级要求。最终方案因此保留这个已验证的插入点，只把大 Canvas 序列替换成一个极小标记和 MCV 视频流。

方案演进如下：

1. 早期方案在 `Present` 中直接绘制视频。它能证明解码器和 D3D8 设备接入可用，但视频固定在整帧末端，无法可靠保持技能特效、怪物、伤害数字和 UI 的原生顺序。
2. 随后尝试把签名标记放进技能 `effect/90`。旧客户端不会稳定遍历这个额外 screen slot；即使给 EXE 增加兼容补丁，手机实机仍出现三个视频全部不可见，因此该方案已废弃。
3. 最终方案恢复服务端 `FIELD_EFFECT` 封包，并在 `Map/Effect.img` 放置 `7x5` 标记。draw hook 在旧大帧原本的绘制时刻调用 `BDV_Render`，然后吞掉标记本身。实机确认视频重新可见。

这不是把视频重新拆回图片帧。最终 `Map/Effect.img` 每个技能只有一个 `7x5` Canvas，真正的 119、52、159 帧仍由外部 MCV 连续解码，所以不会恢复大帧方案的 WZ 体积和逐帧图片解码压力。

### FIELD_EFFECT 标记约定

最终资源节点为：

```text
customSkill/dawnWarrior/galaxyStarBurstVideoLayer
customSkill/dawnWarrior/eclipseForceVideoLayer
customSkill/dawnWarrior/soulEclipseVideoLayer
```

每个节点只包含一张 `7x5`、持续 30000ms 的 Canvas。前四个 RGBA 像素构成签名：

```text
(17,34,51,255)
(68,85,102,255)
(119,136,153,255)
(170,187,204,255)
```

兼容 DLL 在 `SetTexture` 中检查尺寸、纹理格式和签名，在随后的 draw 调用中执行 `BDV_Render`，并阻止这张标记纹理真正显示。30000ms 只用于保证 FIELD_EFFECT 节点覆盖最长的 20000ms 灵魂蚀日；视频自身仍严格按 MCV 时间轴结束。

服务端通过 `chr.sendPacket(PacketCreator.showEffect(path))` 只把标记发给施法者，不向整个地图广播。其他玩家继续接收原生攻击与伤害相关封包，但不会被迫在本机启动施法者的全屏视频。

## 目录和组件

| 文件 | 作用 |
| --- | --- |
| `McvFormat.h/.cpp` | 解析和严格校验 MCV0 容器 |
| `BeiDouVideoApi.h` | 解码 DLL 的稳定 C ABI |
| `BeiDouVideo.cpp` | VP8/VP9 解码、三帧队列、双纹理和 D3D8 绘制 |
| `VideoHarness.cpp` | 不启动游戏即可测试解码和渲染的 Windows 程序 |
| `McvProbe.cpp` | 只读检查 MCV 元数据和边界 |
| `export_soul_eclipse_mcv.py` | 单独从现有灵魂蚀日 Canvas 生成 MCV |
| `export_dawn_warrior_mcvs.py` | 一次生成三个正式技能 MCV，并合入必要的全屏色调 |
| `finalize_dawn_warrior_video_skills.py` | 导出后删除测试技能和已被 MCV 替代的大 Canvas |
| `D3D8Proxy.cpp` | 仅保留作桌面代理实验，不用于手机部署 |
| `build-libvpx-win32.sh` | 交叉编译 32 位静态 libvpx |
| `build.sh` | 构建解码 DLL、Harness、Probe 和桌面代理实验文件 |

游戏接入代码位于：

```text
tool/client-debug/dawn-warrior-skill-compat/
```

服务端周期攻击接入位于：

```text
gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java
```

## MCV0 容器格式

MCV 使用小端序。固定头长度为 36 字节，后面按 flags 决定有哪些表。

### 固定头

| 偏移 | 长度 | 字段 | 说明 |
| ---: | ---: | --- | --- |
| `0` | 4 | signature | 固定为 `MCV0` |
| `4` | 2 | version/reserved | 当前写入 `0` |
| `6` | 2 | headerLength | 当前为 `36` |
| `8` | 4 | encodedFourCC | FourCC 与 `0xA5A5A5A5` 异或后的值 |
| `12` | 2 | width | 视频宽度 |
| `14` | 2 | height | 视频高度 |
| `16` | 4 | frameCount | 帧数 |
| `20` | 1 | flags | Alpha、逐帧 delay、显式 timeline |
| `21` | 3 | reserved | 保留 |
| `24` | 8 | delayUnit | delay/timeline 的纳秒单位 |
| `32` | 4 | defaultDelay | 未提供逐帧 delay 时使用 |

### Flags

| 值 | 名称 | 说明 |
| ---: | --- | --- |
| `0x01` | `kAlphaMap` | 每帧有独立 Alpha 压缩包 |
| `0x02` | `kPerFrameDelay` | 存在逐帧 32 位 delay 表 |
| `0x04` | `kPerFrameTimeline` | 存在逐帧 64 位开始时间表 |

固定头之后依次排列：

1. 颜色帧表，每帧 `offset:uint32 + size:uint32`；
2. Alpha 帧表，仅当 `kAlphaMap` 开启；
3. delay 表，仅当 `kPerFrameDelay` 开启；
4. timeline 表，仅当 `kPerFrameTimeline` 开启；
5. 压缩数据区。

帧表 offset 相对于压缩数据区开头。当前导出器先写全部颜色包，再写全部 Alpha 包。

解析器支持 `VP80` 和 `VP90`，并限制：

- 最大 100000 帧；
- 最大宽高 8192；
- 不接受未知 flag；
- 校验所有乘法、加法、offset、size、timeline 和 duration 溢出；
- 拒绝越界、截断、空帧表和未知编码。

FourCC 异或只是格式标识的一部分，不是加密或安全措施。

## 解码和渲染原理

### 文件读取

`BeiDouVideo.dll` 使用 `CreateFileMapping` 和 `MapViewOfFile` 映射 MCV，不把整个文件额外复制进堆内存。播放停止后会释放映射、文件句柄、帧队列和纹理。

### 后台解码

每次播放创建一个 Win32 worker thread。颜色和 Alpha 分别使用一个 libvpx decoder，每个 decoder 配置 2 个内部线程。

解码输出目前要求 I420 或 YV12。颜色 YUV 和 Alpha YUV 被转换为 `BGRA8`：

- 颜色流产生 B、G、R；
- Alpha 流的亮度结果作为透明度；
- 没有 Alpha 流时透明度固定为 255。

### 有界队列

CPU 侧只有 3 个 `FrameSlot`。解码线程在队列满时等待 2ms，不会无限提前解码并占满内存。

以 `1280x720 BGRA8` 计算，三帧像素队列约为：

```text
1280 * 720 * 4 * 3 = 10.55 MiB
```

这不包含 libvpx 自身工作区，但不会随总帧数线性增长。

### 时间轴和掉帧

播放时钟使用 `QueryPerformanceCounter`。渲染线程从 3 帧队列中选择开始时间不晚于当前时间的最新帧。已经过期的更早帧会被丢弃并计入 `droppedFrames`，所以设备短暂卡顿后会追上时间轴，而不是把整段演出越拖越长。

解码完成且播放时钟到达容器时长后，播放器会在下一次绘制前切换到 `FINISHED`，清空待显示帧并释放两张纹理。完成状态不会继续提交末帧。

### GPU 上传和绘制

GPU 侧循环使用 2 张 `D3DFMT_A8R8G8B8`、`D3DPOOL_MANAGED` 纹理。当前帧上传完成后，以全视口 triangle strip 绘制：

- `SRCALPHA / INVSRCALPHA` 混合；
- 线性纹理过滤；
- 关闭 Z、光照和剔除；
- 绘制前保存完整 D3D8 state block；
- 绘制后恢复原有渲染状态。

两张 `1280x720 BGRA8` 纹理约占 7.03MiB 显存或托管纹理内存。

## D3D8 无代理接入

手机端不能把本项目的代理命名成游戏根目录 `d3d8.dll`。Winlator/Mobox 对 DLL override 和 Wine/DXVK 内置 D3D8 的转发行为与桌面 Windows 不完全一致，代理会导致 `Gr2D_DX8.dll` 初始化失败，游戏在启动阶段弹错。

当前 v9 方案不替换 D3D8：

1. `BeiDou.exe` 启动时加载 `DawnWarriorSkillCompat.dll`；
2. 兼容 DLL 监控 `Gr2D_DX8.dll`；
3. 优先拦截其 `GetProcAddress("Direct3DCreate8")`；
4. 捕获 `IDirect3D8::CreateDevice`；
5. 捕获真实 `IDirect3DDevice8::Present`、`SetTexture` 和四种 draw 方法；
6. 如果 Gr2D 已经完成初始化，则创建一个最小临时设备，取得 Wine/DXVK 共享的 D3D8 vtable；
7. 游戏真实设备第一次 Present 时调用 `BDV_AttachDevice`；
8. 服务端向施法者发送 `FIELD_EFFECT`，其 `Map/Effect.img` 节点只有一个 `7x5` 签名纹理；
9. draw hook 在旧大帧 FIELD_EFFECT 的绘制位置识别签名纹理，调用 `BDV_Render`，并丢弃标记本身；
10. `Present` 只承担设备附加、帧边界和状态检查，不再绘制视频。

成功日志应包含：

```text
LOAD: Dawn Warrior Skill Compat v9 (Gr2D field layer)
OK: Dawn Warrior Skill Compat v9 hooks installed (7 recognition sites)
VIDEO OK: shared D3D8 field-layer hooks installed after initialization
VIDEO OK: active D3D8 device attached on first Present
VIDEO OK: Gr2D field-layer marker texture detected
```

这套挂钩依赖当前 `BeiDou.exe` 和 `Gr2D_DX8.dll` 的固定版本、IAT 和指令地址。替换 EXE 或 Gr2D 后必须重新审计地址和原始字节，不能假设二进制兼容。

## DLL API

`BeiDouVideo.dll` 导出以下 `__stdcall` C API：

| API | 作用 |
| --- | --- |
| `BDV_AttachDevice(void*)` | 保存并 AddRef 真实 `IDirect3DDevice8*` |
| `BDV_DetachDevice()` | 停止使用设备并释放纹理 |
| `BDV_PlayFile(const char*)` | 校验并异步播放 MCV |
| `BDV_Stop()` | 停止 worker，清理文件映射和队列 |
| `BDV_Render()` | 在 D3D8 渲染线程绘制当前帧 |
| `BDV_GetStatus(BdvStatus*)` | 获取状态、时间和帧统计 |
| `BDV_GetLastError(char*, uint32)` | 获取最近错误文本 |

`BdvStatus.state` 可能为：

| 值 | 状态 |
| ---: | --- |
| `0` | IDLE |
| `1` | DECODING |
| `2` | PLAYING |
| `3` | FINISHED |
| `4` | ERROR |

调用约束：

- 必须先成功 `BDV_AttachDevice`，再调用 `BDV_PlayFile`；
- `BDV_Render` 必须在游戏 D3D8 渲染线程、有效 scene 内调用；
- `BdvStatus.structureSize` 必须设为 `sizeof(BdvStatus)`；
- 播放另一个文件前会先停止并清理当前播放。

## 正式视频技能

三个正式技能直接在 `DawnWarriorSkillCompat.dll` 中建立“技能 ID -> MCV 路径”映射：

| 技能 | 视频内容 | 服务端逻辑 |
| --- | --- | --- |
| 银河星爆 `11121005` | TMS 119 帧主轨 + 暗色全屏背景 | 保留原多段爆发时间点 |
| 全蚀之力 `11121006` | TMS 男性 `screen` 主轨及第二阶段 | 保留原多段攻击时间点 |
| 灵魂蚀日 `11121008` | 159 帧演出 + 暖色全屏背景 | 600ms 周期攻击至 19800ms |

灵魂蚀日按 TMS `400011088/common` 对齐为：持续 20 秒、消耗 MP 1000、冷却 120 秒、635% 伤害 7 次、最多 15 个目标、范围 `(-700,-600)~(700,200)`。旧端仍由服务端调度后续攻击；角色死亡、离线或换图时停止。

`11121013`、`soulEclipseStreamTest`、三个正式技能的大尺寸 `Map/Effect.img` 帧和单帧背景均已从最终资源删除。背景已经合成进对应 MCV，因此部署时不能遗漏视频文件。

## 构建环境

macOS 需要：

- `i686-w64-mingw32-g++`；
- `make`、`git`、`curl`、`tar`；
- `ffmpeg`，仅导出 MCV 时需要；
- Python 3 和 Pillow；
- Java 21 和 Maven，仅重新打包服务端时需要。

首次构建会联网下载固定版本：

- libvpx `1.15.2`；
- NASM `2.16.03`，仅本机没有 NASM/YASM 时下载。

依赖缓存在：

```text
tool/client-video/.deps/
```

构建全部视频组件：

```bash
rtk bash tool/client-video/build.sh
```

输出：

```text
clien/BeiDouVideo.dll
clien/BeiDouVideoHarness.exe
tool/client-video/build/mcv_probe
tool/client-video/build/d3d8-desktop-test.dll
```

构建游戏兼容 DLL：

```bash
rtk bash tool/client-debug/dawn-warrior-skill-compat/build.sh
```

输出：

```text
clien/DawnWarriorSkillCompat.dll
```

首次给 EXE 安装兼容 DLL loader：

```bash
rtk python3 tool/scripts/patch-client/patch_dawn_warrior_skill_dll_loader.py --dry-run
rtk python3 tool/scripts/patch-client/patch_dawn_warrior_skill_dll_loader.py
```

早期 `effect/90..93` screen-slot 实验补丁不再是视频播放依赖；当前层级标记位于 `Map/Effect.img`，由服务端 `FIELD_EFFECT` 封包触发。已安装过该实验补丁的 EXE 可以继续使用，无需为这次修改再次更新 EXE。

## 生成和验证 MCV

导出器从迁移脚本临时生成的以下 WZ 节点读取三段正式演出：

```text
clien/Data/Map/Effect.img
customSkill/dawnWarrior/galaxyStarBurst
customSkill/dawnWarrior/fullEclipseMale
customSkill/dawnWarrior/soulEclipse
```

完整生成顺序：

```bash
rtk python3 tool/scripts/patch-skill/patch_dawn_warrior_v_vi.py
rtk python3 tool/client-video/export_dawn_warrior_mcvs.py
rtk python3 tool/client-video/finalize_dawn_warrior_video_skills.py
```

最后一步必须在 MCV 成功生成后执行，因为它会从最终 `Effect.img` 删除导出源。默认输出：

```text
clien/Data/Video/galaxy-star-burst.mcv
clien/Data/Video/eclipse-force.mcv
clien/Data/Video/soul-eclipse.mcv
```

导出参数为 VP9：颜色 CRF 24、Alpha CRF 16、I420、无音频。每个 Canvas 的 delay 会写入逐帧 delay 表；灵魂蚀日的 18030ms 源演出按比例校准到 TMS `time=20` 的 20000ms。动态画面保留源 Alpha；银河星爆背景 Alpha 为220，灵魂蚀日暖色背景 Alpha 为145。

灵魂蚀日的 `400011088/screen1` 源轨是684x384半分辨率资源，导出前按2倍缩放到1368x768参考画布。若按1倍导出，三个黄色边缘帧会只出现在中央小矩形内。

只读验证：

```bash
rtk tool/client-video/build/mcv_probe clien/Data/Video/galaxy-star-burst.mcv
rtk tool/client-video/build/mcv_probe clien/Data/Video/eclipse-force.mcv
rtk tool/client-video/build/mcv_probe clien/Data/Video/soul-eclipse.mcv
```

当前正确结果：

```text
codec=VP90 size=1280x720 frames=119 alpha=yes duration_ms=7140 bytes=6587446
codec=VP90 size=1280x720 frames=52 alpha=yes duration_ms=5220 bytes=8173516
codec=VP90 size=1280x720 frames=159 alpha=yes duration_ms=20000 bytes=6645874
```

## 独立 Harness 测试

在 Windows/Winlator 的客户端根目录运行：

```text
BeiDouVideoHarness.exe
```

不带参数时读取：

```text
Data\Video\soul-eclipse.mcv
```

也可以传入其他 MCV 路径。Harness 会独立创建一个 1280x720 D3D8 窗口，验证：

- DLL 加载和 API；
- D3D8 设备附加；
- MCV 解析；
- 异步颜色/Alpha 解码；
- 纹理上传和 Alpha 混合；
- 播放完成和错误状态。

Harness 通过后再接游戏，可以把容器/解码问题与客户端挂钩问题分开定位。

## 服务端构建

本项目要求 Java 21。当前 macOS Homebrew JDK 路径可这样使用：

```bash
cd gms-server
rtk proxy env JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home /opt/homebrew/bin/mvn -q -DskipTests package
```

输出：

```text
gms-server/target/BeiDou.jar
```

## PC 客户端部署

游戏根目录至少需要：

```text
BeiDou.exe
DawnWarriorSkillCompat.dll
BeiDouVideo.dll
Data/
  Video/
    galaxy-star-burst.mcv
    eclipse-force.mcv
    soul-eclipse.mcv
```

正式技能还需要更新后的：

```text
Data/Skill/1112.img
Data/String/Skill.img
Data/Map/Effect.img
```

禁止在游戏根目录放置本项目生成的 `d3d8.dll`。

## 手机 Winlator/Mobox 部署

手机端会把 `Data` 中各资源目录分别打包为 WZ。按以下方式处理：

| 本地源目录 | 手机客户端产物 |
| --- | --- |
| `clien/Data/Skill` | `Skill.wz` |
| `clien/Data/String` | `String.wz` |
| `clien/Data/Map` | `Map.wz` |
| `clien/Data/Video` | 不打 WZ，保留普通目录 |

MCV 是由 `CreateFileA` 直接读取的外部二进制，不是 WZ 节点。手机目录必须保留：

```text
游戏根目录/
  Data/
    Video/
      galaxy-star-burst.mcv
      eclipse-force.mcv
      soul-eclipse.mcv
```

即使其他 `Data` 子目录已经打包并删除，也要保留这个最小 `Data/Video` 目录。不要创建 `Video.wz`。

手机游戏根目录更新：

```text
DawnWarriorSkillCompat.dll
BeiDouVideo.dll
```

本次层级接入要求把最新 `clien/Data/Map` 重新打包为手机端 `Map.wz`，其中包含三个正式视频技能的 `7x5` FIELD_EFFECT 标记；同时用最新 `clien/Data/Skill` 重新打包 `Skill.wz`。本次不要求再次替换 `BeiDou.exe`。

服务端必须同步替换：

```text
gms-server/target/BeiDou.jar
gms-server/wz/Skill.wz/1112.img.xml
gms-server/wz/String.wz/Skill.img.xml
```

服务端 WZ XML 是 JAR 外部资源，不会被打进 JAR。旧 JAR 不会向施法者发送 FIELD_EFFECT 标记；旧 `1112.img.xml` 则会继续提供旧技能参数。`String.img.xml` 不直接控制视频层，但应与技能 ID 和名称同步部署。

同时确认手机专用资源读取 DLL 仍成套存在：

```text
ijl15.dll
2ijl15.dll
```

它们应来自：

```text
tool/client-runtime/ijl15_手机用.dll
tool/client-runtime/2ijl15_手机用.dll
```

手机端明确不要部署：

```text
d3d8.dll
d3d8-desktop-test.dll
BeiDouVideoHarness.exe
```

## 游戏内测试流程

1. 完全停止并重启服务端。
2. 完全退出并重启手机客户端。
3. 使用魂骑士四转角色登录。
4. 确认银河星爆、全蚀之力和灵魂蚀日为 30 级。
5. 分别将 `11121005`、`11121006`、`11121008` 绑定到快捷键。
6. 在有怪物的地图依次施放。
7. 观察三段 MCV、完整屏幕覆盖和周期伤害；灵魂蚀日应持续 20 秒。
8. 检查客户端和服务端日志。

## 日志

### DawnWarriorSkillCompat.log

记录 DLL 版本、旧客户端技能识别补丁、D3D8 捕获和播放调用。

关键成功行：

```text
LOAD: Dawn Warrior Skill Compat v9 (Gr2D field layer)
OK: Dawn Warrior Skill Compat v9 hooks installed (7 recognition sites)
VIDEO OK: shared D3D8 field-layer hooks installed after initialization
VIDEO OK: active D3D8 device attached on first Present
VIDEO OK: Gr2D field-layer marker texture detected
VIDEO OK: Galaxy Star Burst started
VIDEO OK: Eclipse Force started
VIDEO OK: Soul Eclipse started
```

### BeiDouVideo.log

记录设备附加、播放排队、解析和解码错误。DLL 初始化时写入的单独一行 `not initialized` 是初始状态，不代表最终失败；需要结合后续日志判断。

### 服务端日志

周期攻击使用：

```text
DW_ANIM v3
```

日志包含技能 ID、tick 数、目标数、攻击矩形、停止原因和末段执行情况。

`BeiDouVideoProxy.log` 属于已废弃的本地 d3d8 代理路径，当前手机方案不会生成。

## 常见问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 放入 `d3d8.dll` 后游戏无法启动 | Wine/DXVK D3D8 override 冲突 | 删除或改名该 DLL，使用 v9 兼容 DLL |
| `D3D8 device is not attached` | 真实设备尚未捕获或 DLL 版本旧 | 检查 v9 日志和 `DawnWarriorSkillCompat.dll` 是否已替换 |
| 视频不出现且日志报告没有 marker draw | 服务端 JAR 没有发送 FIELD_EFFECT，或 `Map.wz` 标记缺失 | 更新服务端 JAR，并由最新 `clien/Data/Map` 重新打包 `Map.wz` |
| `failed to open MCV file` | MCV 路径错误 | 保留根目录 `Data/Video/...mcv`，不要打进 WZ |
| `invalid MCV signature` | 文件损坏或不是 MCV0 | 重新导出并运行 `mcv_probe` |
| `VPX color/alpha frame decode failed` | 压缩包损坏或编码不匹配 | 重新导出，检查 VP80/VP90 和帧数 |
| 视频只出现在一个矩形内或边缘被裁切 | `BeiDouVideo.dll` 仍是旧 viewport 版本 | 更新最新播放器 DLL，确认其按完整 render target 绘制 |
| 视频播放但无全屏色调 | MCV 文件是旧版本 | 重新部署当前三个 MCV；色调已合入视频，不再来自 Map.wz |
| 技能显示 0 级 | 服务端 JAR 旧或角色不是魂骑士四转 | 更新 `BeiDou.jar` 并重新登录对应职业 |
| 有视频但没有周期伤害 | 服务端 JAR/WZ 未更新，或范围内没有存活怪物 | 检查 `DW_ANIM v3` 日志和攻击矩形 |
| 视频逐渐落后 | 渲染线程阻塞或解码不足 | 查看 `droppedFrames`；框架会主动丢过期帧追赶时间轴 |
| 只有 `not initialized` | 这是 DLL 构造时初始错误文本 | 继续查看是否出现 `device attached` 和 `playback queued` |

## 扩展到其他技能

新增视频技能时按以下顺序实施：

1. 从 TMS MS 或已迁移 Canvas 中确认主视频轨、Alpha、分辨率和逐帧时长。
2. 为新资源生成 MCV，并先通过 `mcv_probe`。
3. 使用 Harness 验证解码、Alpha 和时间轴。
4. 为测试创建新的技能 ID，不直接覆盖正式技能。
5. 在兼容 DLL 中建立“技能 ID -> MCV 路径”触发映射。
6. 把主动画交给 MCV，只把必要的单帧背景、角色局部动画或小型短序列留在 WZ。
7. 在服务端配置与正式技能一致的攻击时间轴和范围扫描。
8. PC 验证后，再按手机规则打包 Skill/String/Map WZ，并单独部署 `Data/Video`。
9. 对比 Canvas 与 MCV 的 CPU、内存、掉帧和演出同步。

不要把所有视觉轨都机械地编码进一个视频。适合拆分保留的内容包括：

- 长时间保持的纯色或渐变背景，可用单帧 Canvas；
- 必须位于角色或 UI 特定层级的局部效果；
- 与服务器命中时间严格绑定的短帧闪光；
- 其他玩家也必须看到、但无需播放完整视频的简化效果。

## 当前限制和后续方向

当前 v9 已通过手机实机验证，仍有以下边界：

- `BDV_Render` 由 `Map/Effect.img` 中 FIELD_EFFECT 标记的 draw 调用触发，层级跟随旧大帧方案；
- 标记纹理依赖 `7x5` 尺寸和四像素签名，若 Gr2D 更换纹理格式或图集策略，需要重新适配检测；
- D3D8 挂钩地址绑定当前 EXE/Gr2D 版本；
- 当前技能触发和 MCV 路径仍写在兼容 DLL 中；
- 当前没有音频轨；
- 当前只支持 VP8/VP9 I420/YV12；
- 单次播放器实例同一时间只播放一个 MCV；
- 手机端仍需外置 `Data/Video`，不能只分发 WZ。

后续增强建议：

1. 对不同 Winlator/Wine/DXVK 版本做兼容性回归；
2. 建立数据驱动的技能 ID、视频路径、位置、缩放和层级配置；
3. 为设备 Reset、分辨率切换和窗口模式切换增加恢复流程；
4. 增加多实例或受控队列，用于重叠技能；
5. 增加性能统计输出，记录平均解码耗时、队列深度和纹理上传耗时。

## 回滚

视频框架出现问题时，最小回滚方式：

1. 恢复上一版 `DawnWarriorSkillCompat.dll`、Skill/String/Map WZ 和服务端 JAR；
2. 从客户端根目录移除 `BeiDouVideo.dll` 和三个 MCV；
3. 保持根目录没有 `d3d8.dll`。

当前兼容 DLL 在 `BeiDouVideo.dll` 加载失败时只记录错误，不应阻止游戏启动；但三个正式技能的大 Canvas 已从最终 Map 资源删除，因此缺少视频文件时不会有主演出。
