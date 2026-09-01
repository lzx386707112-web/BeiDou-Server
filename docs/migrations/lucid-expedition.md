# 露希妲远征地图迁移

## TMS 地图链分析

TMS v280 的 `450004000` 是恶梦时间塔入口/返回大厅，不是战斗图。地图中的
`pt02` 使用 `tm=999999999`，由新版 Boss Party 系统接管；`out00` 调用
`BPReturn_Lucid`。旧客户端和当前服务端都没有这套控制器，因此直接复制地图
不会进入 Boss 战。

TMS 资源中存在三套五段字段链：

- `450004100 -> 450004150 -> 450004200 -> 450004250 -> 450004300`
- `450004400 -> 450004450 -> 450004500 -> 450004550 -> 450004600`
- `450004700 -> 450004750 -> 450004800 -> 450004850 -> 450004900`

每套依次为入场字段、P1 梦幻森林、过场字段、P2/P3 坍塌时间塔、结算字段。
`Etc/BossLucid.img` 证明这些字段由现代 Lucid 控制器驱动，并按 normal、hard、
story、easy 等模式选择不同 Mob。当前项目已经把露希妲投影为兼容三阶段链
`8880140 -> 8880141 -> 8880142`，并不具备现代 Boss Party、蝴蝶计数、石像、
强制切图或 `fieldType 147/152` 运行时。

## 兼容投影

本迁移只引入形成旧版远征闭环所需的三张地图：

- `450004000`：公共远征大厅，`pt02` 降为不可触发的出生点，入口改由兼容 NPC
  `3003208` 对话打开露希妲远征；
- `450004150`：远征实例 P1，生成 `8880140`；
- `450004250`：远征实例 P2/P3，生成 `8880141`，其现有 revive 继续生成
  `8880142`。

`8880140` 的现有 revive 会在 P1 死亡动画结束后生成 `8880141`。事件脚本在
2.5 秒后清空 P1（P1 死亡动画总长 1.98 秒），再在 `450004250` 显式生成
`8880141` 并传送全队，从而避免第二阶段留在错误地图。清理触发的无击杀事件
由 `hasKiller` 条件隔离，不会推进或结算远征。

实例内复活只恢复 HP、姿态和操作状态，不再对当前地图执行 `changeMap`；P1
控制器也不再用同图换图模拟强制位移，避免旧客户端完整重载地图时黑屏闪烁。

现代入场、过场和结算字段不迁移。地图中的现代 field 脚本、`fieldType`、
Boss 图中的光洞 NPC `9091012/9091013`、`mobTeleport` 和无意义的 `spinOff1`
1x1 对象均被移除；入口大厅复用旧客户端已验证的拉克兰人物 NPC `3003208`。
`fieldLimit` 归零。`450004150/1/obj` 的两个 Spine 2.1 对象不能由旧客户端播放，
但它们是 P1 场景主体，不能直接删空。迁移使用 Spine 2.1 运行库离线烘焙一帧，
投影到独立的 `Map/Obj/LucidBossLegacy.img`，地图节点保留原坐标和顺序，只移除
`piece`、`spineAni`、`tags` 等现代运行时字段。场景同时保留 TMS 的地形、普通
对象、背景、BGM、地图标记和传送点坐标。

## 资源边界

新增客户端资源为三张地图、按实际引用分支生成的 `Map/Back/Lach_boss.img`，
以及 P1 两个静态兼容对象组成的 `Map/Obj/LucidBossLegacy.img`。
共享 `Sound/Bgm46.img` 只追加 `WierldForestIntheGirlsdream`、`BrokenDream`；
共享 `String/Map.img` 只在 `grandis` 下追加 `450004000/150/250`。服务端只新增
三张匹配地图 XML，并在普通及中文 `String.wz/Map.img.xml` 追加同三个 ID。

现有露希妲 Mob、`String/Mob.img`、`Map/Obj/Lacheln.img`、
`Map/Back/Lacheln.img`、`Map/Tile/allblackTile.img` 和 `MapHelper.img` 均受哈希
保护，不在本迁移中修改。

## TMS 完整战斗兼容层

初版三阶段 Boss 只保留了旧客户端可执行的 MobSkill 子集，四只支援 Mob
`8880161/8880165/8880171/8880175` 虽已迁入，却没有事件控制器生成它们。
完整战斗改由 `LucidBossCompat` 维护实例级状态机，不把现代 `238`、`201`、
Spine 或 Particle schema 直接写入 v83 Mob IMG。现有 `8880140 -> 8880141 ->
8880142` 动作与 revive 合同保持原样。

状态机实现以下 TMS `Etc/BossLucid.img` 合同：

- `Butterfly`：按 Boss HP 使用 `5000/4500/4000/3000/2000ms` 周期和
  `5/7/10/15/20` 生成量，保留 P1/P2 各 40 个坐标；计数达到 40 时触发爆发，
  实际显示的飞行 Mob 限制为 12 只，避免旧客户端对象风暴。TMS P1 第 40 个
  坐标为明显越界的 `17100`，兼容投影修正为同一列的 `1710`。
- 梦魇召唤：P1 生成石巨人 `8880161` 和毒菇 `8880164`，P2 生成石巨人
  `8880171`；石巨人上限保持 `StainedGlass/maxSummon=15`。毒菇从 TMS MS
  完整记录迁入，沿 `Mob/_Canvas/8880157.img` 解析像素并生成 46 张 GMS
  ARGB4444 Canvas。
- `StainedGlass`：P2 每 `breakTerm=10000ms` 轮换一个平台区域，播放 1260ms
  破裂动画并结算区域伤害；TMS `BreakEffect/0..5` 六套彩色花/玻璃动画分别
  投影为独立 MCV，并与六个区域按同一索引轮换。`recoverTerm=3000ms` 后补召
  石巨人。旧客户端不能安全动态删除 foothold，因此只投影碰撞窗口，不改写
  地图地形记录。
- `Dragon`：保留 `createDelay=3000ms`、`breathDelay=1650ms`，服务端在
  4650ms 的吐息命中点结算；场景补入 `DragonShadow` 的出现预警和 P1/P2
  结束动作，影子本身不重复结算伤害。
- `LaserRain`：视频总长 7320ms，按 `collisionDelay=1260ms` 和
  `duration=1740ms` 在 1260ms、3000ms 结算两段伤害。
- `Shoot`：2400ms 预备后进入 12000ms 幻影弹幕循环；`Shoot/ball` 按 12 条
  720ms 二次曲线轨迹飞行，每 1000ms 到达一次，并在服务端伤害结算点同步播放
  360ms `Shoot/hit`，随后播放 480ms 收尾。
- `RushLucid`：保留 TMS `path0` 的起点、14 个路径点、逐段速度以及
  `bodyLT=(-47,-135)`、`bodyRB=(76,14)`，视频角色和粒子沿路径移动，服务端
  在 3000ms 路径过程中按身体碰撞框对每名玩家最多结算一次，不再在末尾全图
  结算。
- `HurdleArea`：石巨人存活期间按 TMS `LT=(-20,-500)`、`RB=(20,10)` 维护
  竖直阻挡碰撞窗口，同一轮检测中重叠石巨人不会重复伤害同一玩家。
- 传染炸弹：随机携带者获得 3000ms 分散时间，爆炸时仅伤害其 250 像素范围。
- `Fury`：P3 进入 45 秒雾化倒计时；仍未击败 Boss 时播放失败尾段并执行全图
  伤害。阶段转换、结算、超时、空队伍都会取消旧任务并清理支援 Mob。

## MCV 场景链

复杂场景由 `Map/Effect.img/customSkill/lucid` 的十四个 `7x5` ARGB4444 标记
触发 `BDV_CHANNEL_BOSS_SCENE`，对应：

- `lucid-dragon-p1.mcv`、`lucid-dragon-p2.mcv`；
- `lucid-laser-rain.mcv`、`lucid-phantom-barrage.mcv`；
- `lucid-rush.mcv`、`lucid-fury.mcv`；
- `lucid-butterfly-burst.mcv`、`lucid-bomb.mcv`。
- `lucid-stained-glass.mcv`、`lucid-stained-glass-1.mcv` 至
  `lucid-stained-glass-5.mcv`。

`export_lucid_boss_mcvs.py` 从 `BossLucid.img` 与 `_Canvas/BossLucid.img` 解析
实际 `_outlink`，合成 1280x720 透明 MCV，并以原始记录级方式只新增或替换
`customSkill/lucid`。独立 Boss 场景 Hook `KaringSceneCompat.dll` 使用 Lucid
签名，将标记代码 15–23
及新增的 24–28 路由到上述视频，既不与普通视频技能代码 0 冲突，也不与卡琳
代码 1–14 冲突。
视频生成时要求最后一秒仍有可见 alpha，且重复导出哈希必须一致。

`Horn` 的 `gaugeTime=2000` 与 `hornPos` 是新版采集键驱动的玩家压制交互，
`BombObject` 是炸弹对象可落点的平台坐标，两者都不是独立 Boss 攻击动画。
旧客户端没有可验证的现代采集键字段控制器，本轮不伪造 Hook 或把这些配置误
投影成额外全图伤害；关键 TMS `WeatherMessage` 改由服务端提示覆盖召唤、梦境
增强、强攻击预警、蓄力和愤怒状态。
