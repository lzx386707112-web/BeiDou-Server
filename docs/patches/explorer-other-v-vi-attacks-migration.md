# 冒险家其余职业五、六转攻击技能迁移

## 范围

本迁移以 TMS v280 为源，将旧端已有完整职业体系的 8 个冒险家职业五、六转攻击技能迁移到
对应四转技能书。只保留直接攻击、攻击召唤、攻击领域和持续攻击型 Buff；纯增益、纯被动、纯防御
技能不迁移。双刀、火炮手和古迹猎人因旧端没有完整职业体系，不在本批范围内。
冰雷大魔导士的旧迁移已完整退出；重新迁移前须按
[冰雷五、六转技能迁移可行性](ice-lightning-v-vi-feasibility.md)逐项实现和验收。

| 职业 | 技能书 | 攻击资源节点 | 可施放入口 | 客户端 Canvas |
| --- | ---: | ---: | ---: | ---: |
| 火毒大魔导士 | `212.img` | 28 | 15 | 1429 |
| 主教 | `232.img` | 24 | 12 | 1197 |
| 箭神 | `312.img` | 23 | 12 | 841 |
| 神射手 | `322.img` | 27 | 12 | 959 |
| 夜使者 | `412.img` | 20 | 12 | 662 |
| 暗影神偷 | `422.img` | 32 | 13 | 829 |
| 拳霸 | `512.img` | 26 | 11 | 782 |
| 枪神 | `522.img` | 25 | 13 | 1527 |
| 合计 | 8 本 | 205 | 100 | 8226 |

可施放入口写入各职业 `V_VI_ACTIVE_ATTACKS`，只通过“技能中心 -> 冒险家五、六转攻击技能”脚本
补至技能等级/精通等级 30。隐藏攻击阶段保留完整资源，但不授予角色，只由服务器的多阶段时间轴调用。

脚本按数组顺序一次授予当前职业技能并依次覆盖绑定到 `A-Z`，各职业最多 15 个入口。学习前
`Character.setMasteries` 不初始化这些技能的精通等级，学习后技能已经是 30/30，因此技能面板不能
通过 SP 单独加点。该脚本只识别 11 个冒险家四转职业，不改变骑士团的自动授予逻辑。

## ID 与参数

每个职业按生成器配置的 `target_start`，依次把选中的 TMS 五转攻击节点和该职业全部可用六转攻击
节点映射到本地四转低 ID。TMS 的不可见节点映射为本地 `invisible=1`，供追加攻击、终结爆炸、
召唤攻击等内部阶段使用。相同源 ID 在客户端 Skill、服务端 Skill、String、Java 时间轴和 DLL 中
始终使用同一目标 ID。

服务端等级 1 到 30 均写入按 TMS 30 级表达式求出的参数，包括 `damage`、`attackCount`、
`mobCount`、`mpCon`、`cooltime`、`lt/rb` 和持续时间。现代 `common/time` 同时被用于秒、
毫秒施放阶段和伤害百分比，迁移器只把确认是持续时间的值写入旧服：众神之雷和冰锋刃的
`40000/4000ms` 分别换算为 `40/4s`，箭座采用说明中的 `u=60s`，闪·连杀采用说明中的
`x=10s`；必杀狙击伤害字段及死亡之眼、鲸鱼号突击的施放毫秒不写成持续秒数。
表达式求值支持 `d(...)`、`u(...)`、
`log10/20/30(...)`，并兼容 TMS 的 `2d(x/6)` 隐式乘法写法。攻击次数与目标数按旧端包结构上限
收敛到 15；法师额外写入 `mad` 及对应元素属性。

兼容 DLL v41 将 8 个职业的全部可施放入口和隐藏回放阶段分别送入旧端近战、魔法或远程攻击
构造器。箭神、神射手、夜使者和枪神的 49 个可施放入口按各自 `mobCount` 进入原生多目标收集，
并使用迁移后的 `lt/rb`，不再套用骑士团远程技能的固定目标数。

## 局部特效与怪物命中

迁移器从 TMS `_Canvas` 解出并重编码为旧端 GMS ARGB4444，保留帧延迟、origin、z 层级和链接
结构。迁移范围覆盖角色 `effect/effect0...`、`prepare`、`keydown`、`repeat`、`end`、召唤、弹体、
`SecondAtom`、`special`、`mob`、`tile`、`affected` 和逐怪 `hit` 等攻击表现。

跨技能组 `_outlink` 会自动加载引用的 `_Canvas/<group>.img`。例如火毒节点 `2141004` 的命中画面
指向 `211.img`，生成器会跟随链接迁移真实画面，而不是留下空引用。契约测试只要求源节点确有可
渲染 hit 时目标客户端也必须存在命中 Canvas，避免把 TMS 的 `1x1` 空占位误判为怪物命中特效。

## 多阶段伤害

`ExplorerOtherSkillCompat` 按 TMS `multiAttackInfo` 的累计 `attackTime` 展开 18 个可施放技能的
毫秒时间轴。阶段中的源 `x` 会映射到对应隐藏目标节点，从而让主段、追加段和终结段使用各自的
伤害参数与局部特效。

- 法师和近战处理器延迟首击，再按时间轴逐段结算；
- 远程处理器对这些技能使用 scheduled-only 路径，避免客户端即时结算后服务器再次回放造成双倍伤害；
- 施放时同步广播对应 FIELD_EFFECT，局部角色和怪物特效仍由 Skill WZ 在世界坐标绘制。

没有 `multiAttackInfo` 的攻击召唤、领域和持续攻击 Buff 保留技能参数与全部资源；其现代职业状态机
无法由旧端通用攻击包准确表达的部分不伪造无条件追加伤害，留待实机测试后按具体技能补专用状态。

## MCV 大动画

16 个带 TMS `screen/video` 的可施放技能导出为 `1280x720` MCV。每条源视频轨按自身 Alpha 可见
区域归一，再按时间边界合成 VP9 颜色轨与独立 Alpha 轨，因此多分辨率、不同帧数的颜色/遮罩源也
能保持同步。`Map/Effect.img` 为每项演出增加 `7x5` FIELD_EFFECT 标记，兼容 DLL 负责播放文件。

| 职业 | 技能 ID / 文件 | 帧数 | 时长 |
| --- | --- | ---: | ---: |
| 火毒 | `2121032` / `explorer-2121032.mcv` | 111 | 6660ms |
| 火毒 | `2121035` / `explorer-2121035.mcv` | 57 | 4860ms |
| 主教 | `2321037` / `explorer-2321037.mcv` | 73 | 4380ms |
| 主教 | `2321042` / `explorer-2321042.mcv` | 54 | 3240ms |
| 箭神 | `3121029` / `explorer-3121029.mcv` | 76 | 4560ms |
| 箭神 | `3121031` / `explorer-3121031.mcv` | 26 | 1560ms |
| 神射手 | `3221032` / `explorer-3221032.mcv` | 133 | 7980ms |
| 神射手 | `3221034` / `explorer-3221034.mcv` | 29 | 1740ms |
| 夜使者 | `4121026` / `explorer-4121026.mcv` | 63 | 3780ms |
| 夜使者 | `4121028` / `explorer-4121028.mcv` | 46 | 2760ms |
| 暗影神偷 | `4221036` / `explorer-4221036.mcv` | 85 | 5100ms |
| 暗影神偷 | `4221039` / `explorer-4221039.mcv` | 40 | 2400ms |
| 拳霸 | `5121029` / `explorer-5121029.mcv` | 85 | 5100ms |
| 拳霸 | `5121035` / `explorer-5121035.mcv` | 39 | 2340ms |
| 枪神 | `5221032` / `explorer-5221032.mcv` | 79 | 4740ms |
| 枪神 | `5221034` / `explorer-5221034.mcv` | 41 | 2460ms |

## 生成与验证

```bash
rtk python3 tool/scripts/patch-skill/export_explorer_other_ms.py
rtk python3 tool/scripts/patch-skill/patch_explorer_other_v_vi.py --job all
rtk python3 tool/client-video/export_explorer_other_mcvs.py --force
rtk python3 -m unittest tool/scripts/patch-skill/test_explorer_other_v_vi_contract.py -v
rtk python3 -m unittest tool/scripts/patch-skill/test_explorer_skill_grant_contract.py -v
rtk bash tool/client-debug/dawn-warrior-skill-compat/build.sh
rtk env JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
  PATH=/opt/homebrew/opt/openjdk@21/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin \
  mvn -q -DskipTests compile
```

契约测试核对 8 个主动技能数组、服务端 30 级参数、客户端真实 hit、16 个 MCV 的尺寸/帧数/Alpha、
DLL 映射、Map Effect 标记，以及 18 个 TMS 多阶段时间轴。最终仍需在 Windows/Winlator 客户端
逐项检查角色动作、左右朝向、怪物锚点、他人视角和 FIELD_EFFECT/MCV 的实际层级。
