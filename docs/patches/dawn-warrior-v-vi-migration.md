# 魂骑士五、六转主动攻击技能迁移

## 兼容 ID

新版技能统一映射到旧端已有但为空的 `1112` 四转技能树：

| 本地 ID | TMS ID | 技能 | 面板 |
|---:|---:|---|---|
| 11121005 | 11141500 | 银河星爆 | 显示 |
| 11121006 | 11141503 | 全蚀之力 | 显示 |
| 11121007 | 11141504 | 全蚀之力：魂斩 | 隐藏内部阶段 |
| 11121008 | 400011088 | 灵魂蚀日 | 显示 |
| 11121009 | 400011089 | 日月分裂 | 隐藏内部阶段 |
| 11121011 | 400011056 | 冥河破（TMS：黄泉十字架） | 显示 |
| 11121012 | 400011142 | 宇宙之花（TMS：宇宙） | 显示 |

转职到 `DAWNWARRIOR4(1112)` 时，服务端会立即授予5个可见技能30级；登录时会补齐遗漏等级。两个内部阶段不会作为已学技能授予，也不会写入角色技能封包。冥河破使用真实内部攻击节点 `400011056`，旧端不接管“状态期间用普通攻击触发”的新版输入协议。

登录补级只写入角色内存，再由标准 `getCharInfo` 技能列表统一下发；不会在角色信息封包之前发送自定义 `updateSkill`，避免旧客户端在地图初始化前提前解析技能节点。

`V2.1.35__remove_retired_dawn_warrior_skills.sql` 清理已删除的 `11121000..11121004`；`V2.1.36__remove_dawn_warrior_elysion.sql` 单独清理 `11121010`。两条迁移都会删除对应技能等级、冷却、快捷键和技能宏，避免旧角色登录封包继续引用客户端已经不存在的技能图标。

## 客户端方案

`BeiDou.exe` 在入口处加载新的 `DawnWarriorSkillCompat.dll`。DLL v9 保留主动攻击识别 hook，并为银河星爆、全蚀之力和灵魂蚀日触发 `BeiDouVideo.dll`；`1112.img` 由旧端原生四转技能面板枚举，不接入主教等职业的特殊技能窗口分支。`ijl15.dll` 不修改。早期实验使用的 `effect/90..93` screen-slot 补丁已不再参与视频播放。

主动攻击识别包含两道旧端前置门：快捷键分派进入通用主动技能入口，`DoActiveSkill` 原生校验完成后进入
近战攻击入口。技能保留真实 `111210xx` ID；不会跳过 `0x00764256` 的原生攻击校验。

角色特效还需要在高ID视觉树 `0x00934617` 提前识别；否则约1100万的 `111210xx` 会在到达原
Brandish 比较点前进入只读取平铺帧的通用分支，无法播放兼容节点 `effect/0`、`effect/1`。

DLL 将 `11121005..11121012` 中除 `11121010` 外的保留技能接到旧客户端已经稳定的 Brandish 近战攻击链路，因此：

- 按键释放使用玩家近战攻击包；
- 伤害飘字沿用原生玩家伤害数字；
- `hit` 由技能节点按怪物 OID 播放；
- 角色动作使用 `brandish1/brandish2`、`rush/rush2`、`sanctuary` 或 `genesis`；
- 新版 `effect0` 会在迁移时与主 `effect` 合成，避免旧端遗漏视觉轨道。
- 没有角色 `effect` 的视频/场景技能不会再拿 `hit` 或 `screen` 冒充角色挂点特效。
- 三个全屏技能不再广播 `FIELD_EFFECT` 大 Canvas；服务端只向施法者发送一个 `FIELD_EFFECT`，对应 `Map/Effect.img` 中的 `7x5` 签名标记。MCV 在旧大帧方案相同的 field-effect draw 时刻绘制，沿用已验证的伤害飘字、命中特效和 UI 层级顺序；`Present` 只做帧边界和状态检查。
- MCV 使用完整 render target 尺寸，不沿用游戏最后一个 viewport，避免画面被限制在中央矩形。

构建 DLL：

```bash
rtk bash tool/client-debug/dawn-warrior-skill-compat/build.sh
```

安装或检查 EXE 加载器：

```bash
rtk python3 tool/scripts/patch-client/patch_dawn_warrior_skill_dll_loader.py --dry-run
rtk python3 tool/scripts/patch-client/patch_dawn_warrior_skill_dll_loader.py
```

运行成功后，客户端目录会生成 `DawnWarriorSkillCompat.log`。

## 资源迁移

迁移器：

```bash
rtk python3 tool/scripts/patch-skill/patch_dawn_warrior_v_vi.py --dry-run
rtk python3 tool/scripts/patch-skill/patch_dawn_warrior_v_vi.py
rtk python3 tool/scripts/patch-skill/patch_dawn_warrior_v_vi.py --validate-only
```

正式视频资源必须按以下顺序生成和收口：

```bash
rtk python3 tool/scripts/patch-skill/patch_dawn_warrior_v_vi.py
rtk python3 tool/client-video/export_dawn_warrior_mcvs.py
rtk python3 tool/client-video/finalize_dawn_warrior_video_skills.py
```

第一步临时生成可供导出的 Canvas，第二步编码三个 MCV，第三步从最终 `Effect.img` 删除这些大帧和旧测试技能。

规则：

- 由 `orange-wz` 解析 `Skill_00000.ms` 与 `Skill_00005.ms`；
- `_Canvas` IMG 只提供像素，逐帧 `origin/delay/z` 和节点顺序以 `.ms` 为准；
- `_outlink` 与跨技能 UOL 会先解析到真实 Canvas，再写成旧端自包含节点；
- MCV0 视频由 FFmpeg 解码为带 Alpha PNG，迁移时保留全部源帧和原始 delay，再编码进旧端 IMG；
- 所有客户端 Canvas 重编码为 ARGB4444（WZ format 1）；
- 灵魂蚀日按 TMS `400011088/common` 使用 MP 1000、冷却120秒、635%×7、20秒持续时间和 `(-700,-600)~(700,200)` 范围；其他迁移技能保留当前兼容参数；
- 攻击范围优先采用TMS `common/lt,rb`：银河星爆和全蚀之力保留大范围，冥河破为 `(-600,-480)~(10,40)`，宇宙之花为 `(-380,-340)~(380,80)`；
- 普通角色挂点帧只缩不放；
- 超大帧等比压入 `1280x720`，同时保留 `2048x2048` 硬限制；
- 银河星爆使用一张 `config.ini` 尺寸的静态暗幕，动态帧按整段统一 Alpha 边界以 cover 方式扩展到配置画布，避免中央矩形外仍露出地图；
- 银河星爆保留119张源帧和 `60ms`帧间隔；灵魂蚀日保留159张源帧和各自的原始 delay，不再固定每3帧抽1帧；
- 宇宙之花按TMS `special/0/repeat=18` 与 `common/time=15000` 展开为15000ms开场/循环，再接720ms收尾；循环帧使用旧端已有先例的数字UOL复用，两个兼容effect入口共享42张实际Canvas，不复制220张循环纹理；
- 宇宙之花的两个兼容动画分支 `effect/0` 和 `effect/1` 都设为 `z=-1`，按旧端现有角色技能资源的负层级规则绘制在角色后方；
- 灵魂蚀日不再同时启动多个场景节点；客户端只播放一条动态序列，减少并发解码和图层数；
- TMS中以 `684x384` 半分辨率制作的开场闪光和终结爆发按2倍缩放到屏幕基准，同时等比放大 `origin`；日蚀主体保持原尺寸，避免出现居中的矩形边界或整体过度放大；
- 银河星爆暗色背景与灵魂蚀日暖色背景直接合入 MCV Alpha 画面；
- BC7（format 4098）先用 DDS-DX10 兼容路径解码，再转 ARGB4444；
- `screen` 不伪装成角色 effect；迁移阶段临时写入 `Map/Effect.img/customSkill/dawnWarrior/*`，MCV 导出完成后删除。

当前静态审计结果：

- 银河星爆 MCV：119帧、7140ms、`6587446`字节；
- 全蚀之力 MCV：52帧、5220ms、`8173516`字节，当前采用男性主轨作为统一旧端视频；
- 灵魂蚀日 MCV：159帧，源演出由18030ms等比校准为20000ms，`6645874`字节；
- 三个文件均为 `1280x720`、VP9颜色流+Alpha流，并通过 `mcv_probe`；
- 最终 `Map/Effect.img` 不再包含 `galaxyStarBurst`、`fullEclipseMale/Female`、`soulEclipse` 及旧测试节点，只保留三个 `7x5` 视频层标记。

## 持续攻击

银河星爆、全蚀之力、灵魂蚀日和宇宙之花在动画期间持续发送近战攻击包。每个后续攻击包先直接发送给施法者本人，再以排除施法者的方式广播给地图其他玩家；由于旧端本地角色不会稳定显示服务器重放的自身近战飘字，每段同时只给施法者补一条现有v83 `DAMAGE_MONSTER` 数字包，并逐段结算真实伤害。银河星爆和全蚀之力的时间点来自 TMS `multiAttackInfo`，将小于180ms的密集点节流后保留各爆发段；灵魂蚀日按600ms周期攻击至19800ms；宇宙之花按原始 `time=15000ms`、`subTime=450ms` 执行33段攻击，最后一段为14850ms。

第一次延迟命中仍走完整 `applyAttack`，只扣一次MP并应用一次技能效果。银河星爆、全蚀之力和灵魂蚀日的后续命中复用首次攻击包的一组伤害值，并在每个时间点重新扫描施法时固定的技能矩形。宇宙之花则复用海龙螺旋的追踪攻击机制：每450ms按角色当前位置重新计算技能矩形，首次没有命中怪物时使用服务端回退伤害模板，之后怪物只要进入当前范围就可在下一周期被命中。所有持续攻击均从范围内当前存活的怪物中选取最多 `mobCount` 个目标；角色死亡、离线或换图后停止后续任务。

## MS 提取

解析器源码：

```text
/Users/lizixian/Documents/mxd/orange-wz
```

编译并导出本次迁移需要的7个技能元数据与7段视频：

```bash
rtk env JAVA_HOME=/opt/homebrew/opt/openjdk@21 PATH=/opt/homebrew/opt/openjdk@21/bin:$PATH mvn -q -DskipTests compile dependency:copy-dependencies -DincludeScope=runtime
rtk /opt/homebrew/opt/openjdk@21/bin/java -Xmx6g -cp 'target/classes:target/dependency/*' orange.wz.cli.MsSkillExporter /Users/lizixian/Documents/mxd/TMS/MapleStory/Data/Packs /Users/lizixian/Documents/mxd/TMS/MapleStory-MS-Export/DawnWarrior
```

中间目录约350MiB，不需要复制进客户端。迁移器读取其中的 XML 参数和 PNG 帧；三个全屏技能最终编码为外置 MCV，其余角色与命中特效仍写为 ARGB4444 Canvas。

## 实机检查

2026-07-29 手机 Winlator 实机已经确认最终 FIELD_EFFECT 标记层可以显示 MCV。旧大帧版本曾验证伤害飘字顺序正常，因此最终视频桥接复用相同 field-effect draw 时刻；失败的技能 `effect/90` 标记方案不再使用。

1. 进入 `1112` 角色，确认5个可见技能出现在四转面板并能拖到快捷栏。
2. 查看 `DawnWarriorSkillCompat.log` 是否记录 hook 安装成功。
3. 每个技能分别验证自己视角和他人视角的角色动作、effect、hit与伤害数字。
4. 银河星爆、全蚀之力、灵魂蚀日验证视频与持续 hit/飘字是否对施法者和同地图玩家同时显示。
5. 验证视频覆盖完整 render target，左下角弧光等边缘内容不被中央 viewport 裁切。
6. 验证银河星爆119帧、全蚀之力52帧和灵魂蚀日159帧连续播放；灵魂蚀日应持续20秒。
