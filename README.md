# BeiDou Server

BeiDou 服务端、后台管理、客户端资源和配套工具的工作区。

## 常用入口

- 服务端：`gms-server/`
- 后台管理前端：`gms-ui/`
- 客户端资源：`clien/`
- 工具集：[tool/README.md](tool/README.md)
- 项目文档：[docs/README.md](docs/README.md)

## 常用脚本

```sh
rtk tool/scripts/package/package_server_jar.sh
rtk tool/scripts/runtime/start_server.sh
rtk tool/scripts/package/pack_img_wz.sh
rtk tool/scripts/png2canvas/png2canvas.sh
rtk tool/scripts/wz/wzpy.sh
```

更多脚本说明见 [docs/tools/tool-scripts.md](docs/tools/tool-scripts.md)。

## 迁移资料

- [095 内容迁移概览](docs/migrations/095-overview.md)
- [095 内容迁移手册](docs/migrations/095-migration.md)

## 排障经验

- 迁移地图、怪物、Boss 后出现黑屏、崩溃或怪物外形不对时，先看 [095 内容迁移手册](docs/migrations/095-migration.md)。其中记录了地图资源审计、召唤 Boss 后崩溃、Boss 血条 UI、MobSkill、阿卡伊勒 `8860000` 兼容修复，以及 `9300301/9300302/9300304` 占位怪资源替换等经验。
- 新增或改造技能时，先看 [新增技能与 BeiDou.exe 识别记录](docs/patches/new-skills-exe-notes.md)。其中记录了龙神技能、矩形 AoE、`1121001` 磁石改造成轻舞飞扬式攻击，以及继续迁移成 `400011124` 剑影分身的完整排查过程：WZ 数据、`effect/effect0`、服务端技能类型、EXE 小端编码、code cave 追加判断、伤害延迟和攻击范围对齐；也记录了 112 新增四转技能不显示时，需要补 `0x4F0751` 和 `0xA0A3D6` 两处技能窗口职业过滤的结论，以及“消耗品热键触发服务端技能”的不改 EXE 备选思路。

## 当前技能：1121012 斗气死亡断层

当前正式目标是把 273 导出的 `_Canvas/40001.img / skill/400011027` 迁移到英雄四转技能 `112.img / skill/1121012`。`1121012` 之前只是从 `1121011` 复制出来验证技能面板显示的测试壳；现在它的内容、字符串、服务端常量和 EXE 识别都改为“斗气死亡断层”，不再继承 `1121011` 勇士的意志语义。

源技能实测结构：

```text
源文件: /Users/lizixian/Documents/mxd/skill-273-export/img/_Canvas/40001.img
源区域 key: BMS
源技能: 400011027
目标技能: 1121012

effect  : 24 个直接 canvas，角色起手动画
screen  : 27 个直接 canvas，源帧名 19,20,23..47
special : 4 组子动画，怪物被击中特效的一部分
hit     : 1 组子动画，怪物被击中特效的一部分
```

当前迁移结果：

```text
clien/Data/Skill/112.img / skill/1121012
  effect      : 源 effect 24 帧复制为 effect/0、effect/1 两组 Brandish 兼容变体，走人物技能 effect 层
  screen      : 保留源 screen 节点，重编号为 0..26
  special     : 保留源 special 节点
  hit         : 合成 special/0..3 + 源 hit/0 为 hit/0..3 兼容命中特效
  action      : brandish1 / brandish2
  level       : 1..30
  masterLevel : 30

level 参数:
  damage      = 416
  attackCount = 14
  mobCount    = 15
  mpCon       = 500
  cooltime    = 5
  lt/rb       = (-3000,-2000) / (3000,2000)

clien/Data/Map/Effect.img
  customSkill/deathFault/full   : 28 帧 screen FIELD_EFFECT 资源，先空等再播放 screen
  customSkill/deathFault/screen : 旧全屏 screen 资源，已由优化脚本移除；当前不再由服务端广播
```

源 `400011027` 的 canvas 没有 `origin/delay` 子节点，迁移脚本会给 `screen/special/hit` 补默认动画元数据，避免旧客户端播放时一闪而过。这是迁移兼容处理，不是源 WZ 原始数据。`effect` 是人物技能层，不能套用 `1121001` 的手工 origin，也不能用场景中心点伪造源参数；当前 effect 以旧客户端无 origin 时的默认中心锚点为基准，只补 `delay=30`，再按 Brandish 两个动作变体做水平微调：`effect/0 origin=(frame.width/2-200, frame.height/2)` 让视觉右移 200px，`effect/1 origin=(frame.width/2+160, frame.height/2)` 让视觉左移 160px。之前写成固定 `origin=(-200,0)` / `(160,0)` 会覆盖每帧的默认 Y 锚点，导致两个方向一起偏下；现在每帧保留自身中心 Y，只改水平挂点。由于当前 EXE 让 `1121012` 走 Brandish 正常角色视觉路径，WZ 结构也必须匹配 Brandish：源 effect 直接帧会复制成 `effect/0`、`effect/1` 两组，否则客户端找不到可播放 effect。

源 `screen` 帧名是 `19,20,23..47`，`special/1` 和 `special/2` 也有中间缺号。旧客户端动画播放层更稳妥的输入是从 `0` 开始的连续帧，所以迁移时会把 `screen/special/hit` 的直接动画组重编号为 `0..n`。

`screen` 原始帧只有约 `684x268` 到 `680x384`。实测把它镜像到 `effect/90` 后仍走普通角色 effect 层，不是真正屏幕坐标层，会出现没有全屏、闪一下就播放完的问题。因此 `1121012` 当前不再写 `skill/1121012/effect/90`；WZ 里仍保留真实 `skill/1121012/screen` 节点，实际全屏表现改走旧端已支持的 `Map/Effect.img + FIELD_EFFECT` 路径。

`patch_1121012_death_fault.py` 默认读取 `clien/config.ini` 的 `width/height`，当前配置是 `1280x720`。源 `effect` 是人物放技能的前置动画，不能放进 `Map/Effect` 做居中或全屏放大，否则会丢失人物锚点；它保留在 `skill/1121012/effect/0` 和 `skill/1121012/effect/1`，由客户端 Brandish 技能 effect 层按角色位置播放。只有源 `screen` 被迁到 `customSkill/deathFault/full`，每一帧生成成 1280x720 透明 FIELD_EFFECT canvas，并按 alpha 内容区域 cover 到全屏场景层。命令行可用 `--canvas-width/--canvas-height` 临时覆盖分辨率。

`customSkill/deathFault/full` 当前生成结果是 28 帧：第 0 帧是 1280x720 透明帧，delay 为源 screen 起始帧 `19 * 30ms = 570ms`；后 27 帧是源 `screen` 全屏化，按源 screen 帧名恢复时间轴，可见 screen 部分总计 `2610ms`。整个 FIELD_EFFECT 总计 `3180ms`，经过 `tool/scripts/patch-skill/optimize_112_skill_assets.py --canvas-format 1` 转成 ARGB4444 后，当前 payload 约 `1.76MB`，encoded raw 从约 `98.4MB` 降到约 `49.2MB`。实测 `skill/1121012/effect` 只有 `0`、`1` 两个子组，每组 24 帧源尺寸，例如 `284x224`、`564x268`、`1152x444`、`792x256`；`effect/0` 每帧 `origin.x=frame.width/2-200`、`origin.y=frame.height/2`，`effect/1` 每帧 `origin.x=frame.width/2+160`、`origin.y=frame.height/2`，`delay=30`；`skill/1121012/effect/90` 不存在。

快捷栏图标还需要旧端常见 icon 元数据：`icon/iconMouseOver/iconDisabled` 都是 `32x32`，并设置 `origin=(0,32)`、`z=0`。`1121001` 和 `1121012` 的来源 icon 原本没有这些子节点，放到键盘上会偏位；对应迁移脚本现在都会补齐。

### 迁移经验总结

这次 `400011027 -> 1121012` 的关键经验是先分清每个 WZ 节点属于哪个播放层，再决定是否迁移、镜像或合成。不要只看节点名字下结论，也不要只用截图倒推坐标；最终判断必须回到源 WZ 结构、目标客户端实际代码路径和运行后的资源验证。

`effect`、`screen`、`special`、`hit` 不是同一种东西：

```text
effect  : 施放者身上的起手/武器视觉，必须走角色技能 effect 层，跟角色坐标绑定。
screen  : 全屏或场景级表现，不能当普通 effect 播放；普通 effect 层会受角色/范围/锚点限制。
special : 客户端有加载槽位和命中特效播放证据，但具体攻击链路未必自然触发。
hit     : 老客户端稳定的怪物命中特效路径，适合承接 special 的兼容合成。
```

实际迁移时应保持这个边界：`effect` 放在 `skill/1121012/effect/0`、`effect/1`，让 EXE 把 `1121012` 当 Brandish 兼容攻击来播放；`screen` 保留在真实 `skill/1121012/screen` 作为来源，但全屏视觉使用 `Map/Effect.img/customSkill/deathFault/full` 加服务端 `PacketCreator.showEffect(...)`；`special` 原样保留，同时把 `special + hit` 合成进 `hit/0..3`，保证怪物命中表现能走当前稳定路径。

不要把 `screen` 镜像到 `effect/90` 当成真正支持 screen。`effect/90..93` hook 只能证明旧端可以多选几个 effect 子槽，不能证明它进入了现代客户端的 screen 屏幕坐标层。`1121012` 实测过 `effect/90` 会出现两个问题：一是按普通角色 effect 层播放，不会自然全屏；二是 screen 时间轴不完整时会闪一下就结束。因此当前结论是：真实 `screen` 节点可以保留，但播放层先走 FIELD_EFFECT，直到反汇编确认 native screen 对象布局和播放路径为止。

`effect` 的坐标不要用截图硬调，也不要把它居中或放大。源 `400011027/effect` 是人物起手动画，应该看起来像角色拿在手上释放；它不是全屏素材。把 effect 放进 `Map/Effect`、按分辨率 cover、或者走 `0x0093587C` default flat effect path，都会让它脱离角色锚点，表现成居中、范围裁剪或偏离身体。当前必须走 `0x0093465F` Brandish 正常角色视觉路径。

`origin` 是这次最容易误判的点。源 `400011027/effect` 没有 `origin`，旧客户端会给无 origin 的 canvas 使用自己的默认挂点。为了左右微调，如果写成固定 `origin=(-200,0)` 或 `origin=(160,0)`，虽然 X 看似有变化，但 Y 被强行改成 0，等于覆盖默认纵向锚点，结果两个方向都会偏下。正确做法是按每帧尺寸保留默认中心 Y，只改水平锚点：

```text
effect/0 视觉右移 200px: origin=(frame.width/2-200, frame.height/2)
effect/1 视觉左移 160px: origin=(frame.width/2+160, frame.height/2)
```

这里的正负方向也要按客户端绘制公式理解：增加 `origin.x` 会让画面相对角色往左，减少 `origin.x` 会让画面相对角色往右。修改坐标后必须抽查多帧，因为本技能每帧尺寸差异很大，不能只拿第 0 帧代表全部。

源 canvas 没有 `delay` 时，旧客户端可能一帧带过。`screen/special/hit` 的兼容动画需要补默认元数据，并且把源帧名重编号为从 `0` 开始的连续帧。`screen` 还要按源帧编号恢复时间轴：源第一帧是 `19`，所以 FIELD_EFFECT 前面补透明帧 `19 * 30ms = 570ms`；后续可见帧按相邻源帧差计算 delay，当前总时长是 `3180ms`。不要为了“看起来慢一点”随便改全局帧率，先确认是 delay 缺失、首帧空等、还是播放层错误。

全屏效果要按客户端分辨率生成画布，但这只适用于 `screen` 的 FIELD_EFFECT 版本。当前脚本读取 `clien/config.ini` 的 `width/height`，生成 `1280x720` 透明画布，再把 screen alpha 内容区域按 cover 放进去。`effect` 不参与这个分辨率逻辑，不能被放大；否则角色起手动画会失真并且失去人物位置。

第一次释放技能明显卡顿时，优先怀疑大体积 WZ canvas 首次解码/加载，而不是先改帧数。第一版 256 色量化只降低 payload，没有降低解压后的像素尺寸，实测首放卡顿改善不明显；当前改用 ARGB4444 (`format=1`) 来降低运行时像素流。`customSkill/deathFault/full` 的 encoded raw 从约 `98.4MB` 降到约 `49.2MB`；`112.img` 中 `1121001/1121012/1121013` 的目标 canvas encoded raw 从约 `480.1MB` 降到约 `240.0MB`。`1121013` 的源 `effect`、`effect0`、`effect1` 是三条同时播放的视觉轨道，但旧客户端实际可播放入口是 `effect/%d`；当前结构是 `effect/0` 镜像源 `effect`、`effect/1` 镜像源 `effect0`、`effect/2` 镜像源 `effect1`。`BeiDou.exe` 让 `1121013` 的主视觉走默认平铺 effect 出口以播放 `effect/0`，再在 screen-effect cave 尾部追加启动 `effect/1` 和 `effect/2`；每次 selector 调用都使用独立栈临时资源引用并恢复播放参数，避免后启动的效果覆盖或破坏前一条轨道的上下文。当前仍没有做通用预热机制；后续如果要继续优化，应优先考虑资源预加载或更激进的 UOL/_inlink 复用，而不是改变源 screen 时间轴或 effect 坐标。

新增技能面板显示和技能实际释放是两件事。`1121012` 能出现在四转技能面板，依赖 `0x4F0751`、`0xA0A3D6` 的职业过滤 patch；但能显示不代表能按正确攻击类型、动作、视觉路径和伤害结算释放。`1121012` 还需要 Brandish 兼容攻击识别 patch，以及服务端 `Hero.DEATH_FAULT` 分支来广播 FIELD_EFFECT、延迟结算伤害。

每次调整后至少做这几类验证：

```text
1. WZ 结构: skill/1121012/effect 只有 0、1 两组，effect/90 不存在。
2. effect 坐标: 多帧检查 origin 是否为 frame.width/2 +/- offset、frame.height/2。
3. screen 资源: customSkill/deathFault/full 为 28 帧、1280x720、总 delay 3180ms。
4. EXE 路径: 1121012 visual branch 仍跳到 0x0093465F，不回到 default flat effect path。
5. 服务端路径: Hero.DEATH_FAULT 先广播 FIELD_EFFECT，再延迟 applyAttack。
```

如果后续迁移别的带 screen 的技能，先照这个顺序判断：源节点实际结构是什么；旧客户端是否有真实 loader 和播放调用；该节点应该绑定角色、怪物还是屏幕；目标技能的 EXE 攻击路径会读取哪种 WZ 结构；最后再决定是原样保留、重编号、合成到 hit，还是迁到 Map/Effect。

### Screen 和 Special 证据

`special` 不是猜测，`BeiDou.exe` 已有实际加载和播放证据：

```text
0x75DE3D push 0x9BC                         ; 检查 special 字段
0x75DE85 push 0x9BD                         ; Skill/%03d.img/skill/%07d/special
0x75DEC4 lea edi, [eax+0x9C]                ; special 资源槽位
0x75DED9 mov [edi], eax                     ; 保存 special
0x426CFE mov eax, [esi+0x9C]                ; 命中特效路径读取 special
0x426E05 / 0x426EAE call [vtable+0x80]      ; 走客户端现有播放路径
```

`screen` 当前不按“新客户端原生 screen 槽位”下结论。代码证据显示老客户端现有 `effect/90` hook 复用的是普通角色 effect 层：

```text
真实节点保留: skill/1121012/screen
弃用镜像:   skill/1121012/effect/90
EXE hook:   0x9358EE -> 0xAEFD80，选 effect/90 后仍复用普通角色 effect playback block
当前播放:   Map/Effect.img/customSkill/deathFault/full + PacketCreator.showEffect(...)
```

也就是说，WZ 里保留 `screen` 作为真实来源，但不再让 1121012 通过 `effect/90` 播放。服务端在释放 `Hero.DEATH_FAULT` 时广播 `PacketCreator.showEffect("customSkill/deathFault/full")`，使用旧端 FIELD_EFFECT 全屏层。后续如果继续反汇编出完整 native screen 对象布局，可以再把播放层从 FIELD_EFFECT 切回原生 screen；当前不要把“有字符串”误写成“已经完整原生支持”。

`special` 的情况类似，也不能只因为 loader 存在就认定普通攻击命中一定会播。反汇编确认 `special` 会加载到技能对象 `+0x9C`，但播放函数 `0x426CE6` 只有一个调用点 `0x425BDC`，并依赖额外状态数组 `+0x5FC/+0x608`；当前 1121012 走 Brandish 兼容攻击链路时，不保证自然进入这条 native special 播放路径。因此迁移脚本保留原始 `special/0..3`，同时把 `special/0..3 + hit/0` 合成到 `hit/0..3`，让怪物命中特效走当前更稳定的 hit 播放层。

### EXE 识别

1121012 需要三类 EXE 支持：

```text
1. 技能窗口显示:
   0x4F0751 -> 0xAEFA80
   0xA0A3D6 -> 0xAEF980
   作用: 让 job 112 的新增四转技能进入技能面板列表。

2. screen 兼容播放:
   0x9358EE -> 0xAEFD80
   作用: 可播放 effect/90..93，但 1121012 已不使用这条路径；实测它仍是角色 effect 层，不适合本技能全屏 screen。

3. 1121012 攻击识别:
   0x933ABF Brandish visual branch
   0x950DE5 Brandish action type
   0x95255A Brandish visual offset
   0x967A10 Brandish state switch
   0x78E9D6 Brandish hit randomization
   0x934720 保留既有 effect/2 尾段分支
```

第 3 组 patch 点和历史 `1121001` 实验使用同一组 Brandish hardcode hook，这是 EXE 结构重叠，不是技能来源关系。`1121012` 的 WZ 来源只有 `400011027`；脚本 `patch_1121012_death_fault_attack.py` 只是识别当前 EXE 已经存在的 hook，并在保留旧行为的前提下追加 `1121012`。当前 `0x933ABF` visual branch 对 `1121012` 跳到 `0x0093465F` Brandish 正常角色视觉路径；旧的 `0x0093587C` default flat effect path 只用于早期 `effect/90` screen mirror 实验，现已不用，否则 effect 会像居中场景效果一样被范围裁剪，不能贴在施放角色身上。

### 服务端伤害

服务端新增常量：

```text
org.gms.constants.skills.Hero.DEATH_FAULT = 1121012
```

`CloseRangeDamageHandler` 对 `Hero.DEATH_FAULT` 先广播全屏 FIELD_EFFECT，再延迟 1000ms 后执行 `applyAttack`，让真实扣血、死亡和掉落尽量落在 screen 播放窗口，而不是 effect 起手瞬间：

```text
attack.skill == Hero.DEATH_FAULT
  -> PacketCreator.showEffect("customSkill/deathFault/full")
  -> TimerManager.schedule(applyAttack, 1000ms)
```

怪物命中视觉由客户端 `special + hit` 路径承担；服务端只负责近战攻击包校验、冷却、MP、范围和实际伤害结算。

### 相关脚本

```text
tool/scripts/patch-skill/patch_1121012_death_fault.py
tool/scripts/patch-client/patch_112_skill_window_display.py
tool/scripts/patch-client/patch_1121012_death_fault_attack.py
```

验证命令：

```sh
rtk python3 tool/scripts/patch-skill/patch_1121012_death_fault.py --dry-run
rtk python3 tool/scripts/patch-client/patch_112_skill_window_display.py --dry-run
rtk python3 tool/scripts/patch-client/patch_1121012_death_fault_attack.py --dry-run
```
