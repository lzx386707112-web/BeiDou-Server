# MCV 透明视频播放器实现说明（脱敏版）

> 文档定位：这是一份可独立交付的实现规格。读者不需要接触原项目源码，也可以据此实现一个功能等价的 32 位 Windows / Direct3D 8 透明视频播放器，并把它接入旧客户端的既有特效绘制链。
>
> 脱敏声明：本文省略或替换了真实产品名、模块名、业务 ID、资源路径、固定内存地址、原始指令字节、标记纹理签名和实机环境名称。`<...>` 表示部署方必须自行定义的值。容器布局、播放算法、线程模型、渲染方法和验证标准均按当前实现保留。

## 1. 要解决的问题

旧客户端通常把动画保存为逐帧图片。全屏动画一旦达到数十或数百帧，会同时放大以下成本：

- 资源包体积；
- 首次使用时的图片解压耗时；
- 大量纹理的创建、上传与释放；
- 32 位进程的内存压力；
- 移动兼容层或低性能设备上的卡顿。

本方案把大动画改为一个外置 MCV 文件。MCV 内含一条压缩颜色视频、一条可选的压缩 Alpha 视频以及逐帧时间轴。运行时只保留一个只读文件映射、两个视频解码器、三个 CPU 帧槽和两张 GPU 纹理，内存不会随视频总帧数线性增长。

播放器只负责全屏视频层。角色动作、局部技能图、命中特效、伤害数字、目标选择和伤害结算仍走宿主原有系统。这样既能降低资源压力，也能保留旧客户端已经验证过的业务与渲染顺序。

## 2. 成功标准

实现完成后应同时满足：

1. 32 位宿主能加载播放器，不要求用代理 DLL 替换系统图形库。
2. VP8 或 VP9 的颜色轨可以播放；存在 Alpha 轨时能正确透明合成。
3. 解码在后台线程执行，所有 D3D8 调用只发生在宿主渲染线程。
4. 视频短暂跟不上时丢弃过期帧并追赶时间轴，不延长整段演出。
5. 播放结束后不保留末帧，文件映射、线程、CPU 帧和纹理均可释放。
6. 优先在宿主原生特效层的绘制时机插入视频；该层未绘制时可在帧提交前兜底。
7. 播放器可由独立 Harness 验证，不依赖业务客户端才能排查容器或解码问题。

## 3. 总体架构

```text
素材帧/源视频
    |
    +-- 统一画布、原点和逐帧时长
    +-- 颜色 RGB  -> VP8/VP9 I420 包
    +-- Alpha 灰度 -> VP8/VP9 I420 包
    +-- 写入 MCV 头、索引表、时间表和压缩数据
                         |
                         v
                    外置 MCV 文件
                         |
        +----------------+----------------+
        |                                 |
        v                                 v
  只读格式检查器                      播放器动态库
                                          |
                            内存映射 + 严格容器校验
                                          |
                              后台线程双路 VPX 解码
                                          |
                                 三槽 BGRA 有界队列
                                          |
                              宿主渲染线程选择当前帧
                                          |
                               双 D3D8 纹理轮换上传
                                          |
                          原生特效层插入 / Present 兜底
                                          |
                                  全目标表面 Alpha 合成
```

建议拆成五个组件：

| 组件 | 职责 |
| --- | --- |
| 容器库 | 定义 MCV 数据结构，严格解析和检查边界 |
| 播放器动态库 | 文件映射、异步解码、排队、纹理上传、绘制和状态查询 |
| 宿主接入层 | 获取真实 D3D8 设备、接收业务触发、选择插入层和调用播放器 |
| 导出器 | 将 RGBA 帧编码成颜色/Alpha 双轨并封装为 MCV |
| Probe 与 Harness | 分别验证容器和完整解码/渲染链 |

不要把业务 ID 映射、Hook 地址或服务端伤害调度写进播放器核心。它们属于宿主接入层。

## 4. MCV 容器规格

### 4.1 基本约定

- 所有整数使用小端序。
- 固定头为 36 字节。
- 偏移与长度使用无符号整数。
- 颜色与 Alpha 必须使用相同编码、尺寸和帧数。
- 当前解码端接受 VP8 (`VP80`) 和 VP9 (`VP90`)。
- `<MAGIC4>` 和 `<FOURCC_MASK>` 在本文中已脱敏。自行实现时可选任意固定值，但导出器、Probe 和播放器必须完全一致。
- FourCC 掩码只是格式混淆，不提供加密、认证或防篡改能力。

### 4.2 固定头

| 偏移 | 长度 | 类型 | 字段 | 规则 |
| ---: | ---: | --- | --- | --- |
| 0 | 4 | bytes | signature | 固定为 `<MAGIC4>` |
| 4 | 2 | uint16 | versionOrReserved | 当前写 0；解析器暂不依赖它 |
| 6 | 2 | uint16 | headerLength | 不小于 36，且不超过文件长度 |
| 8 | 4 | uint32 | encodedFourCC | `fourCC XOR <FOURCC_MASK>` |
| 12 | 2 | uint16 | width | `1..MAX_DIMENSION` |
| 14 | 2 | uint16 | height | `1..MAX_DIMENSION` |
| 16 | 4 | uint32 | frameCount | `1..MAX_FRAMES` |
| 20 | 1 | uint8 | flags | 只能包含下表定义的位 |
| 21 | 3 | bytes | reserved | 写 0 |
| 24 | 8 | uint64 | delayUnitNs | delay/timeline 每单位代表多少纳秒 |
| 32 | 4 | uint32 | defaultDelay | 无逐帧 delay 表时使用 |

建议沿用当前上限：

```text
MAX_DIMENSION = 8192
MAX_FRAMES    = 100000
```

### 4.3 Flags

| 位 | 建议名称 | 含义 |
| ---: | --- | --- |
| `0x01` | HAS_ALPHA | 存在与颜色逐帧对应的 Alpha 包表 |
| `0x02` | HAS_FRAME_DELAYS | 存在每帧一个 uint32 的 delay 表 |
| `0x04` | HAS_FRAME_TIMELINE | 存在每帧一个 uint64 的显式开始时间表 |

遇到未知位必须拒绝文件，不能静默忽略。

### 4.4 可变区布局

从 `headerLength` 开始依次存放：

1. 颜色帧表：`frameCount` 个 `{offset:uint32, size:uint32}`；
2. Alpha 帧表：仅 `HAS_ALPHA` 时存在，结构同上；
3. delay 表：仅 `HAS_FRAME_DELAYS` 时存在，每项为 `uint32`；
4. timeline 表：仅 `HAS_FRAME_TIMELINE` 时存在，每项为 `uint64`；
5. 压缩数据区。

帧表中的 offset 相对于压缩数据区开头，而不是相对于文件开头。解析成功后可把它转换成绝对文件偏移，便于解码线程直接访问内存映射。

当前写入策略是：先连续写全部颜色包，再连续写全部 Alpha 包。解析器不应依赖这个顺序，只应依赖各帧的 offset/size。

### 4.5 时间轴

若有逐帧 delay：

```text
frame[i].delayNs = delayTable[i] * delayUnitNs
```

否则：

```text
frame[i].delayNs = defaultDelay * delayUnitNs
```

若有显式 timeline：

```text
frame[i].startNs = timelineTable[i] * delayUnitNs
```

否则按 delay 累加：

```text
start = 0
for frame in frames:
    frame.startNs = start
    start += frame.delayNs
```

总时长取所有帧 `startNs + delayNs` 的最大值。每一次乘法和加法都要先做无符号 64 位溢出检查。

### 4.6 必须实施的解析检查

解析器至少检查：

- 文件指针非空，长度不小于 36；
- signature、FourCC、宽高、帧数和 flags 合法；
- `headerLength` 合法；
- 每张表都完整存在；
- 计算表长时没有乘法溢出；
- `dataStart + offset` 没有加法溢出；
- 每个颜色包非空且完全落在文件内；
- 声明了 Alpha 时，每个 Alpha 包非空且完全落在文件内；
- 每帧开始时间、时长和结束时间无溢出；
- 最终绝对偏移可由播放器使用的整数类型表达。

所有失败都返回明确错误文本，不允许“尽量播放”。该容器会在宿主进程内被解析，宽松解析会把损坏文件升级成越界读取或崩溃风险。

### 4.7 解析伪代码

```cpp
bool ParseMcv(bytes, fileSize, Video* out, Error* error) {
    clear(*out);
    require(fileSize >= 36);
    require(read4(bytes + 0) == MAGIC4);

    headerLength = readU16LE(bytes + 6);
    codec = readU32LE(bytes + 8) ^ FOURCC_MASK;
    width = readU16LE(bytes + 12);
    height = readU16LE(bytes + 14);
    frameCount = readU32LE(bytes + 16);
    flags = bytes[20];
    unitNs = readU64LE(bytes + 24);
    defaultDelay = readU32LE(bytes + 32);

    validateHeaderAndLimits();
    position = headerLength;
    readColorTable(position);
    if (flags & HAS_ALPHA) readAlphaTable(position);
    if (flags & HAS_FRAME_DELAYS) readDelayTable(position);
    else fillDefaultDelays();
    if (flags & HAS_FRAME_TIMELINE) readTimelineTable(position);
    else buildCumulativeTimeline();

    dataStart = position;
    for each frame:
        frame.colorOffset = checkedAdd(dataStart, frame.colorOffset);
        validateRange(frame.colorOffset, frame.colorSize, fileSize);
        if (HAS_ALPHA) {
            frame.alphaOffset = checkedAdd(dataStart, frame.alphaOffset);
            validateRange(frame.alphaOffset, frame.alphaSize, fileSize);
        }
        duration = max(duration, checkedAdd(frame.startNs, frame.delayNs));

    commitParsedResultOnlyNow();
    return true;
}
```

关键点是最后才提交结果：中途失败时，调用方不能拿到半解析对象。

## 5. 导出器实现

### 5.1 输入规范化

对每个源帧执行：

1. 解码为 RGBA8；
2. 读取源帧 origin，缺失时用图像中心；
3. 创建统一尺寸的透明画布；
4. 按 `canvasCenter - origin` 把源帧合成到画布；
5. 记录该帧 delay，缺失时使用项目约定默认值，最小为 1；
6. 如需全屏色调或固定背景，在编码前合成到 RGBA 帧，不要在播放器里写业务特例。

所有帧必须输出相同宽高。局部、跟随角色或跟随怪物的效果不适合直接烘焙成固定全屏视频，应继续留在宿主资源系统中。

### 5.2 双路编码

从每张 RGBA 帧拆出：

- RGB 三通道送入颜色编码器；
- A 通道作为灰度图送入 Alpha 编码器。

推荐使用 VP9、I420、无音频，并关闭会改变逐帧包对应关系的前瞻行为。一个可行配置如下；质量参数应按素材调整：

```text
codec           = VP9
pixel format    = yuv420p
lag-in-frames   = 0
auto-alt-ref    = 0
keyframe period = frameCount
color CRF       = 约 20~28
alpha CRF       = 约 12~20
```

颜色和 Alpha 编码完成后，从 IVF 中剥离文件头与每包 12 字节的 IVF 包头，仅保留实际 VPX packet。必须断言：

```text
colorPacketCount == alphaPacketCount == delayCount == frameCount
colorFourCC == alphaFourCC
```

### 5.3 封装与原子写入

写入顺序：固定头、颜色表、Alpha 表、delay 表、可选 timeline 表、颜色包、Alpha 包。

先在目标目录创建临时文件，完整写入并关闭后再原子替换正式文件。生成前计算所有 packet 总长，并拒绝超过 uint32 offset 能表达的容器。

每次生成后必须运行 Probe；正式生成器还应连续运行两次并比较 SHA-256，要求第二次不再改变结果。编码器若不能保证位级确定性，至少固定版本、线程/编码参数并说明其可重复性边界。

## 6. 播放器动态库接口

为了让接入层与播放器解耦，使用 `extern "C"`、`__stdcall` 的稳定 ABI。函数名可自定义，接口语义建议如下：

```cpp
struct PlayerStatus {
    uint32_t structureSize;
    uint32_t state;
    uint32_t width;
    uint32_t height;
    uint32_t frameCount;
    uint32_t decodedFrames;
    uint32_t displayedFrames;
    uint32_t droppedFrames;
    uint64_t durationMilliseconds;
    uint64_t positionMilliseconds;
};

int  AttachDevice(void* d3dDevice8);
void DetachDevice();
int  PlayFile(const char* path);
void Stop();
void Render();
int  GetStatus(PlayerStatus* status);
void GetLastError(char* buffer, uint32_t capacity);
```

状态定义：

```text
IDLE -> DECODING -> PLAYING -> FINISHED
                    \-> ERROR
DECODING ------------------> ERROR
任意活动状态 --Stop()-----> IDLE
```

调用约束：

- `AttachDevice` 成功后才能 `PlayFile`；
- `Render` 必须在持有有效 D3D8 scene 的宿主渲染线程调用；
- `GetStatus` 先检查 `structureSize`，便于 ABI 扩展；
- 新的 `PlayFile` 应先完整停止和清理旧播放；
- 动态库卸载前必须先 `Stop`、`DetachDevice`。

## 7. 文件与对象生命周期

### 7.1 文件读取

使用以下 Win32 流程只读映射文件：

```text
CreateFileA(read-only, share-read)
  -> GetFileSizeEx
  -> CreateFileMapping(PAGE_READONLY)
  -> MapViewOfFile(FILE_MAP_READ)
```

这样不用再把整个视频复制到堆上。映射必须一直存活到解码线程退出；清理顺序是：

```text
停止 worker
-> UnmapViewOfFile
-> CloseHandle(mapping)
-> CloseHandle(file)
```

### 7.2 设备引用

`AttachDevice` 保存真实 `IDirect3DDevice8*` 并调用 `AddRef`。重复附加时先释放旧纹理和旧设备引用。`DetachDevice` 释放纹理，再对设备 `Release`。

不要从解码线程创建、锁定或绘制纹理。旧 D3D8 宿主即使使用了多线程设备，也不应把设备调用散落到未知线程。

### 7.3 Stop 的正确顺序

`Stop` 不能在持锁状态下无限等待 worker，否则 worker 可能正等待同一把锁，形成死锁。正确顺序：

```text
加锁：取得 worker 句柄并 SetEvent(stopEvent)
解锁
等待 worker 退出
加锁：关闭线程句柄，清空帧槽，关闭映射，释放纹理，重置状态
解锁
```

## 8. 后台解码

### 8.1 解码器

按容器 FourCC 选择 libvpx 的 VP8 或 VP9 decoder。颜色轨始终需要一个 decoder；有 Alpha 时再创建一个 decoder。当前实现为每个 decoder 配置两个内部线程。

每帧执行：

```text
检查 stopEvent
-> 解码颜色 packet
-> 解码对应 Alpha packet（如有）
-> 验证输出尺寸和像素格式
-> 转换为一张 BGRA8
-> 等待有界队列出现空槽
-> 写入 frameIndex/startNs/BGRA，最后置 ready=true
```

当前支持 I420 和 YV12。若 decoder 输出高位深或其他色度格式，应明确报错，不能按 I420 强行读取。

### 8.2 YUV 到 BGRA

颜色轨按有限范围 BT.601 整数公式转换：

```text
C = max(0, Y - 16)
D = U - 128
E = V - 128

R = clamp((298*C + 409*E + 128) >> 8)
G = clamp((298*C - 100*D - 208*E + 128) >> 8)
B = clamp((298*C + 516*D + 128) >> 8)
```

I420/YV12 是 4:2:0：Y 每像素取样，U/V 使用 `(x/2, y/2)`。YV12 的 U/V 平面顺序与 I420 相反，必须交换。

Alpha 轨也用同一转换函数，其结果的 R（由灰度输入生成，三通道应基本相同）作为最终 opacity。没有 Alpha 轨时 A 固定为 255。输出字节顺序为 `B,G,R,A`。

如果新实现能直接、安全地使用 Alpha 轨的 Y 平面，也应先通过与参考实现逐帧对比再替换上述路径，因为有限范围换算会影响边缘透明度。

### 8.3 三槽有界队列

CPU 侧使用固定三个 `FrameSlot`：

```cpp
struct FrameSlot {
    vector<uint8_t> bgra;
    uint64_t startNs;
    uint32_t frameIndex;
    bool ready;
};
```

解码线程只写 `ready == false` 的槽；渲染线程消费后将其设回 false。队列满时 worker 等待 stop event 一个很短的间隔（当前量级约数毫秒），再重试。

三槽足以提供少量预解码，同时限制内存。CPU 帧内存近似为：

```text
width * height * 4 * 3 bytes
```

还需另计两个 libvpx decoder 的工作区。

第一帧成功入队时记录高精度播放起点，并把状态从 DECODING 改为 PLAYING。这样文件打开和 decoder 初始化耗时不会消耗视频时间轴。

## 9. 渲染线程与时间同步

### 9.1 播放时钟

使用 `QueryPerformanceCounter` / `QueryPerformanceFrequency`：

```text
elapsedNs = (nowTicks - startTicks) * 1,000,000,000 / frequency
```

生产代码应考虑乘法溢出；32 位进程中仍使用 64 位中间值。

### 9.2 选帧与掉帧

每次 `Render()`：

1. 若未附加设备或首帧尚未入队，直接返回；
2. 若解码已结束且 `elapsedNs >= durationNs`，清队列、释放纹理并进入 FINISHED；
3. 在三个槽中找到 `startNs <= elapsedNs` 且 startNs 最大的帧；
4. 将所有比它更早的 ready 帧标记为空，并增加 droppedFrames；
5. 上传被选中的帧，增加 displayedFrames；
6. 若已有 currentTexture，则绘制它。

这是一种“按墙钟追赶”的策略。卡顿时宁可跳过视觉帧，也不让视频整体延迟，适合需要和服务端时间点对齐的技能演出。

如果当前没有新的到期帧，继续绘制上一张纹理；一旦播放时钟达到总时长且解码完成，立即释放纹理，不再显示末帧。

## 10. D3D8 上传与绘制

### 10.1 双纹理

创建两张：

```text
format = D3DFMT_A8R8G8B8
pool   = D3DPOOL_MANAGED
levels = 1
usage  = 0
```

每次上传切换纹理索引。`LockRect` 后必须逐行复制，因为目标 `Pitch` 不保证等于 `width * 4`。

GPU 纹理内存近似为：

```text
width * height * 4 * 2 bytes
```

分辨率改变或播放另一个尺寸的视频时，先释放旧纹理再重建。

### 10.2 绘制区域

不要盲目沿用宿主当前 viewport。旧引擎在局部绘制后可能留下一个小 viewport，导致全屏视频只显示在矩形区域。

正确流程：

1. 保存原 viewport；
2. 取得当前 render target 并查询其真实宽高；
3. 创建覆盖整个 render target 的临时 viewport；
4. 画一个屏幕空间 triangle strip；
5. 恢复原 viewport 和全部 D3D 状态。

顶点使用 `XYZRHW + TEX1`，四角坐标采用 D3D8 半像素修正：

```text
left   = -0.5
top    = -0.5
right  = renderTargetWidth  - 0.5
bottom = renderTargetHeight - 0.5
```

UV 为 `(0,0) .. (1,1)`。当前方案会把视频拉伸到完整目标表面；若要求保持比例，应在导出阶段 letterbox/crop，或在此计算目标矩形，但必须统一产品规则。

### 10.3 渲染状态

绘制前创建 `D3DSBT_ALL` state block，绘制后完整恢复。至少设置：

```text
ZENABLE          = FALSE
ALPHABLENDENABLE = TRUE
SRCBLEND         = SRCALPHA
DESTBLEND        = INVSRCALPHA
CULLMODE         = NONE
LIGHTING         = FALSE
COLOROP          = SELECTARG1(TEXTURE)
ALPHAOP          = SELECTARG1(TEXTURE)
MINFILTER        = LINEAR
MAGFILTER        = LINEAR
pixel shader     = 0
vertex shader    = D3DFVF_XYZRHW | D3DFVF_TEX1
```

绘制后先解除 stage 0 纹理，再 Apply/Delete state block，并恢复原 viewport。任何中途失败都要走对称清理路径，避免污染宿主后续绘制。

## 11. 宿主接入层

播放器核心不知道“什么业务事件应该播放什么文件”。接入层负责三件事：捕获真实设备、把业务事件映射为视频、选择正确的绘制时机。

### 11.1 不使用图形代理 DLL

在部分兼容环境中，用同名代理替换系统 D3D8 会改变 DLL override 和图形翻译链，甚至让宿主在启动阶段失败。当前方案在已经由宿主加载的兼容模块中获取真实设备：

1. 观察宿主图形模块加载；
2. 在已确认的导入点拦截 `GetProcAddress("Direct3DCreate8")`；
3. 包装 `IDirect3D8::CreateDevice`；
4. 设备创建后对其共享 vtable 安装 `Present`、`SetTexture` 和四类 draw Hook；
5. 把真实设备交给播放器 `AttachDevice`。

若图形模块已经初始化，可创建一个 1×1 的临时窗口设备，取得该运行环境共享的 D3D8 vtable 并安装同样的 Hook；随后在真实设备第一次 `Present` 时附加真实设备。临时设备只用于取得函数表，完成后立即释放。

所有二进制 Hook 都必须版本锁定：先核对模块版本、映像基址假设和原始字节，再写入跳转或替换函数指针。本文故意不提供任何真实地址或原始字节；移植者必须针对自己的合法宿主重新审计。

### 11.2 播放请求排队

业务 Hook 可能不在渲染线程，或发生在宿主攻击状态尚未初始化完成时。安全做法是只写一个原子 pending ID：

```cpp
void QueueVideo(businessId) {
    atomicExchange(pendingVideoId, businessId);
}

HookedPresent(...) {
    id = atomicExchange(pendingVideoId, 0);
    if (id != 0) StartMappedVideo(id);
    ...
}
```

当前模型只支持一个播放器实例，因此新的 pending ID 会覆盖尚未消费的旧 ID，新的 `PlayFile` 也会停止正在播放的视频。需要重叠演出时，应改为有界请求队列和多播放器实例，不能简单移除 `Stop()`。

### 11.3 原生层标记

为了把视频放在已经验证过的原生特效层，而不是固定画在整帧末尾，在资源系统中放一张极小、不可见用途的标记纹理：

- 尺寸取 `<MARKER_W> × <MARKER_H>`；
- 前若干像素写入部署方自定义签名；
- 标记节点的持续时间覆盖视频最长时长；
- 资源层级选择宿主原先能正确显示大特效、伤害数字和 UI 的位置。

Hook `SetTexture(stage=0)` 时：

1. 检查资源类型确为 2D texture；
2. 检查尺寸只落在一个很窄的允许区间；
3. 检查纹理格式；
4. `LockRect(READONLY)` 后比对签名像素；
5. 命中后缓存该纹理指针，避免以后重复锁定。

随后 Hook 四类绘制 API：

```text
DrawPrimitive
DrawIndexedPrimitive
DrawPrimitiveUP
DrawIndexedPrimitiveUP
```

若当前绑定的是标记纹理：

1. 本帧尚未画视频则调用 `Render()`；
2. 返回成功，但不调用原 draw；
3. 因此标记本身不会显示。

需要 `renderingVideo` 递归保护：播放器内部也会调用 `SetTexture` 和 `DrawPrimitiveUP`，Hook 看到该标志时必须直接转发，否则会递归进入自身。

纹理缓存若调用了 `AddRef`，必须在设备销毁、资源重载或 DLL 卸载时成对 `Release`。生产实现还应处理纹理指针失效和缓存上限。

### 11.4 Present 兜底

并非每个宿主分支都会稳定画出标记。当前实现保留帧级兜底：

```text
若 videoPlaying && 本帧 marker draw 没有调用 Render
    在调用真实 Present 之前调用一次 Render
```

标记层绘制优先，因为它能保持原生层级；Present 兜底只保证“可见”，其层级位于帧末，可能覆盖本应在视频上方的元素。每帧真实 `Present` 返回后重置：

```text
videoRenderedThisFrame = false
markerBound = false
```

同时查询播放器状态，FINISHED 或 ERROR 时清掉接入层的 `videoPlaying`。

### 11.5 业务与服务端边界

推荐的数据流是：

```text
本地业务事件 -> 接入层排队播放 MCV
服务端/资源事件 -> 仅向施法者触发原生层标记
服务端时间轴 -> 独立负责多段伤害和目标扫描
```

不要用视频播放进度驱动权威伤害。渲染可能掉帧、关闭或失败，而服务端逻辑必须保持确定性。反过来，伤害时间点也不能早于对应视觉冲击，二者应由同一份设计时间轴生成或通过契约测试对齐。

全屏视频通常只发给本地施法者，避免其他玩家同时启动完整屏幕演出；其他玩家仍接收宿主原有的角色动作、攻击和简化命中特效。

## 12. 并发设计

推荐共享状态：

```text
CRITICAL_SECTION:
  mappedFile, parsedVideo, frameSlots
  D3D device/texture pointers
  counters, playback start, last error

atomic state:
  IDLE/DECODING/PLAYING/FINISHED/ERROR

manual-reset event:
  stopEvent
```

约束：

- worker 只访问内存映射、decoder 和 CPU 帧槽；
- 渲染线程独占所有 D3D8 调用；
- `ready=true` 是帧槽最后一次写入；消费时先完成纹理上传再设回 false；
- 错误文本和统计计数与结构状态在同一锁下读写；
- 不在持锁状态下等待 worker；
- 接入层的 pending 业务 ID 使用原子交换；
- Hook 的每帧布尔量只由渲染线程访问，若宿主可能多线程绘制则必须改为线程安全状态。

## 13. 最小实现顺序

按以下顺序实现最容易隔离问题：

1. 定义容器结构和纯只读解析器。
2. 编写 Probe，用有效、截断、越界和溢出样本覆盖解析器。
3. 编写导出器，先生成无 Alpha 的短视频，再增加 Alpha 双轨。
4. 实现文件映射和 libvpx 单线程逐帧解码，输出 BGRA 校验图。
5. 增加三槽队列、worker、stop event 和状态机。
6. 编写独立 D3D8 Harness，完成双纹理上传与透明合成。
7. 验证结束释放、连续播放、主动 Stop、损坏文件和缺文件。
8. 在宿主接入层捕获真实设备，先只用 Present 验证可见性。
9. 加入原生层标记识别和四类 draw 吞标记逻辑。
10. 增加 Present 兜底、递归保护、状态轮询和日志。
11. 接入业务 ID 映射与服务端标记，不在播放器核心写业务特例。
12. 做真实客户端的层级、时间轴、地图切换和重复施放回归。

## 14. Probe 与 Harness

### 14.1 Probe

Probe 只依赖容器库，输入一个 MCV，输出：

```text
codec, width, height, frameCount, hasAlpha, durationMs, fileBytes
```

返回码建议：参数错误为 2，文件或格式错误为 1，成功为 0。Probe 通过只能证明容器结构有效，不能证明 VPX packet 可解码或画面正确。

### 14.2 Harness

Harness 创建一个普通窗口和 D3D8 设备，然后动态加载播放器并解析所有导出函数：

```text
Create D3D8 device
-> AttachDevice
-> PlayFile
-> message loop
-> Clear / BeginScene / Render / EndScene / Present
-> poll status
-> Stop / DetachDevice / Release device / unload module
```

Harness 至少验证：

- 动态库与 ABI；
- 设备附加；
- 文件解析；
- 颜色与 Alpha 解码；
- BGRA 上传和 Alpha 混合；
- 时间轴、掉帧统计、FINISHED 和 ERROR；
- 播放结束不残留末帧。

只有 Harness 通过后才进入宿主集成测试，这能把“容器/解码/渲染”与“Hook/业务触发/资源层级”分开。

## 15. 验证清单

### 15.1 容器与导出

- [ ] 颜色、Alpha、delay 数量完全一致。
- [ ] 宽高、FourCC、帧数、flags 和总时长正确。
- [ ] 所有 offset/size 在文件范围内。
- [ ] 截断文件、未知 flag、错误 codec、零尺寸、超大帧数均被拒绝。
- [ ] 首帧、关键帧、尾帧可以实际解码。
- [ ] Alpha 并集非空，透明边缘没有明显黑边或白边。
- [ ] 生成器连续运行两次，输出哈希稳定或有明确的编码器确定性说明。

### 15.2 播放器

- [ ] 未附加设备时拒绝播放并给出错误。
- [ ] 首帧入队后才启动播放时钟。
- [ ] 队列永远不超过三个 CPU 帧。
- [ ] 卡顿后 droppedFrames 增长且时间轴能追上。
- [ ] 结束时进入 FINISHED、清队列并释放两张纹理。
- [ ] Stop 不死锁，连续播放不同尺寸文件正常。
- [ ] 动态库卸载前 worker 已退出。
- [ ] D3D 状态、viewport 和纹理绑定在绘制后恢复。

### 15.3 宿主集成

- [ ] 模块版本与 Hook 前原始字节匹配；不匹配时拒绝安装。
- [ ] 捕获的是实际游戏设备，而不是只附加临时设备。
- [ ] 播放请求在渲染帧边界消费。
- [ ] 标记签名不会误命中普通小纹理。
- [ ] 标记 draw 被吞掉，视频每帧最多绘制一次。
- [ ] 标记缺失时 Present 兜底可见并产生日志。
- [ ] 视频不会递归触发自己的 draw Hook。
- [ ] UI、伤害数字、角色和怪物的层级符合设计。
- [ ] 换图、死亡、断线、窗口切换和重复施放不崩溃。
- [ ] 伤害时间轴与视频冲击点对齐，播放失败不影响权威伤害逻辑。

## 16. 日志与故障定位

播放器日志至少记录：

```text
device attached
playback queued
parse/decode/texture error text
```

接入层日志至少记录：

```text
host hooks installed
active device attached
marker detected
mapped video started
Present fallback activated
video finished/error
```

常见问题：

| 现象 | 优先检查 |
| --- | --- |
| 宿主启动即失败 | 是否错误部署了图形代理；Hook 版本/原始字节是否不匹配 |
| 报设备未附加 | 是否捕获真实 CreateDevice/Present；播放器 API 是否完整加载 |
| 文件打不开 | 外置路径、工作目录、文件名和部署清单 |
| 容器签名错误 | 导出器与解析器的 `<MAGIC4>` 是否一致；文件是否损坏 |
| VPX 解码失败 | packet 边界、颜色/Alpha 包数、FourCC、编码器参数 |
| 只显示在局部矩形 | 是否按 render target 尺寸重设完整 viewport |
| 视频不透明或边缘异常 | Alpha 轨是否存在；YUV 范围与 YV12 平面顺序 |
| 视频越来越慢 | 是否按墙钟选最新到期帧；是否错误地逐帧补播 |
| 视频不可见但状态在播放 | 标记是否被画出；Present 兜底是否运行；scene 是否有效 |
| 播完停在末帧 | FINISHED 条件是否释放 currentTexture |

## 17. 安全与兼容性注意事项

- MCV 是不可信二进制输入，所有长度、偏移、乘法和加法都必须检查。
- signature 和 FourCC 掩码不是安全机制。如需防篡改，应在发布层增加签名或可信哈希清单。
- Hook 只能用于有权修改和测试的宿主。不要复用本文的抽象说明去猜测未知程序地址。
- 32 位 ABI、调用约定、结构对齐和函数导出名必须由自动化测试检查。
- 不要在 `DllMain` 中启动复杂线程或调用 D3D；这里只创建轻量对象，真正初始化延后到显式 API。
- 设备 Reset、分辨率切换和窗口模式切换需要显式释放/重建纹理；当前最小实现只覆盖 attach/detach。
- 当前无音频、无 seek、无暂停、无多实例混播，只支持 VP8/VP9 的 I420/YV12 输出。
- marker 缓存必须有生命周期策略；只 AddRef 不 Release 会造成长期资源泄漏。

## 18. 性能预算

设视频宽高为 `W × H`：

```text
CPU 三帧队列 ≈ W * H * 4 * 3
GPU 双纹理   ≈ W * H * 4 * 2
```

除此之外还有文件页缓存、两个 decoder 工作区、容器索引和临时转换对象。总帧数主要影响文件大小和总解码时长，不应直接影响常驻 BGRA/纹理内存。

性能采样至少记录：

- 每帧解码耗时；
- YUV→BGRA 耗时；
- 队列深度；
- 纹理 Lock/复制耗时；
- displayed/dropped 比例；
- Present 兜底命中次数。

若 CPU 转换成为瓶颈，可评估 SIMD 或 GPU 色彩转换，但必须保留当前实现作为像素参考，并验证 Alpha 边缘、旧 GPU 能力和 D3D8 状态隔离。

## 19. 交付物建议

一个完整、可维护的实现应交付：

```text
include/player_api.h
src/container_parser.cpp
src/player.cpp
src/host_adapter.cpp
tools/export_mcv.py
tools/mcv_probe
tools/video_harness.exe
tests/container_negative_cases/*
docs/deployment-and-runtime-checklist.md
```

部署包只放运行所需的播放器、宿主接入模块、外置视频和必要资源标记。Probe、Harness、临时 IVF、基线、日志和测试视频不要混入正式客户端目录。

## 20. 当前实现的关键取舍总结

当前方案真正重要的不是某个固定业务 ID 或 Hook 地址，而是以下组合：

1. 用颜色/Alpha 双路 VPX 保存透明动画；
2. 用小型索引容器保存 packet 边界与原始逐帧时间轴；
3. 文件映射、后台解码、三槽 CPU 队列和双 GPU 纹理限制内存；
4. 按高精度墙钟选最新到期帧，卡顿时丢帧追时钟；
5. D3D8 全状态保存/恢复，并按真实 render target 做全屏合成；
6. 在原生特效层用签名标记取得正确绘制顺序，同时保留 Present 可见性兜底；
7. 播放触发、渲染和服务端伤害相互解耦，只通过共同时间轴保持体验一致；
8. 用 Probe、Harness、宿主实测三级验证，不能把“容器能解析”等同于“客户端可用”。

照此拆分后，播放器核心可以在不携带任何原项目业务信息的情况下复用；每个新宿主只需重新实现经过版本审计的设备捕获、业务映射和原生层插入部分。
