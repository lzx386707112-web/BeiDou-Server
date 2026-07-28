# 神说七 Boss 视觉兼容迁移

来源：`/Users/lizixian/Documents/mxd/神说/Data`。

迁移范围：希拉、白发希拉、觉醒希拉、卡翁、敦凯尔、守护天使绿水灵、监视者卡洛斯，以及必要附属实体、地图和地图视觉依赖。

## 战斗地图

| 地图 | Boss | 说明 |
|---:|---:|---|
| `262030300` | `8870000` | 希拉之塔 |
| `262031300` | `8870200` | 白发希拉之塔 |
| `450010100` | `8880400` | 欲望祭坛兼容场景 |
| `221040001` | `8880200` | 地球防御本部兼容场景 |
| `450009400` | `8645009` | 泰涅布利斯兼容场景 |
| `900000207` | `8880700` | 天使绿水灵领地 |
| `410002060` | `8880803` | 卡洛斯兼容战场 |

地图服务端 XML 均包含对应 Boss 的单次刷新点；可直接使用管理员传送命令进入地图测试。

旧的死亡和返回关联图仍保留在资源包中，但本表的七张 Boss 图现在统一使用同场左侧复活，不再依赖独立休整图 ID。

服务端 `MapFactory` 同时增加缺图保护：角色数据库如果仍指向未安装的地图，地图加载返回 `null`，由 `CharacterService` 的既有逻辑送回射手村，不再在角色登录阶段抛出空指针。`MapManager` 不会缓存缺失地图。

现代 Boss 地图使用旧端兼容结构：移除 `particle/mobTeleport/noSkill`、高版本 field/复活/远程效果字段、动态 Spine 对象元数据、扩展背景尺寸字段和扩展 portal 范围字段；保留原 Back/Obj/Tile、foothold、portal、miniMap 和全部可解码 Canvas。七张 Boss 图的 `returnMap/forcedReturn` 均指向当前地图。

每张图的 `portal/0` 放在原图左侧可站立区域，原出口门改为 `shenshuoBossRetry` 继续挑战门，并在 Boss 区新增隐藏传送点 `bossRetry`。`bossRetry` 使用 `pt=8`，避免被服务端选为死亡后的随机出生点；万能传送仍可按名称直接进入 `bossRetry`，角色死亡则只会回到左侧 `portal/0`。

上述七张 Boss 图内死亡复活时，角色 HP 直接恢复至客户端最大值，避免在 Boss 攻击持续期间以 50 HP 复活后立即再次死亡。其他地图继续使用原有复活血量规则。

七个主 Boss 的客户端 `maxHP` 保持 `2000000000` 不变，服务端统一使用 `<string name="maxHP" value="30000000000"/>`。客户端和服务端的 `eva` 上限均为 `200`：白发希拉 `625 -> 200`、卡翁 `300 -> 200`、敦凯尔 `300 -> 200`、守护天使绿水灵 `500 -> 200`；希拉 `140`、觉醒希拉 `180`、监视者卡洛斯 `1` 保持不变。旧客户端使用本地 Mob 数据参与命中表现，只修改服务端 XML 会继续出现 `MISS`。

Flyway 迁移 `V2.1.28__add_shenshuo_eight_boss_drops.sql` 是已发布的历史迁移，不修改其校验和；`V2.1.32__remove_fallen_kalos_drops.sql` 会清理已移除 Boss 的掉落。剩余七个主 Boss 保留原掉落配置。

后台管理的两个“Boss 攻城”入口共享 `shenshuoSiegeBossOptions`，列表中可直接选择上述七个 Boss 并追加其怪物 ID。攻城服务端接口沿用现有资源有效性校验，无需额外白名单。

万能传送对 `221040001` 使用独立兼容分支：不再预加载地图或引用隐藏 portal，直接通过数字入口 `portal 0` 切图。脚本会在切图后核对角色实际地图 ID；失败时自动退还传送费用、提示客户端和服务端必装地图文件并立即结束，绝不会把 Boss 生成在当前地图。进入成功后仅在 Boss 缺失时，按原图静态生命参数 `(-1215,866, fh=43, rx=-1715~-715)` 直接生成，避免 `spawnMonsterOnGroundBelow` 在该兼容地图上找不到 foothold。

万能传送进入上述七张 Boss 图时，每次在原有 50 万金币基础上额外消耗 `4000019 × 500` 和 `2210006 × 1`。材料不足时不扣金币、不计次数且不生成 Boss；卡翁切图失败时两种材料会和金币一起原数退还。

为避免旧客户端进入敦凯尔地图时整包加载黑魔法师和历年活动资源，Boss 图使用专用精简视觉包 `DunkelBM1`、`DunkelBM1_3`、`DunkelEvent`，所有实际引用路径均存在且 Canvas 可解码。

`shenshuoBossRetry.js` 在当前地图内返回 Boss 区。Boss 对象仍存在时不做清场或重置，因此保留当前血量；只有 Boss 已不存在时才按兼容坐标补刷新 Boss。

守护天使绿水灵和监视者卡洛斯的服务端血条包使用旧端已存在的 `8870000` 血条模板 ID，怪物本体 ID、技能和掉落不变。该兼容需要使用新构建的 `BeiDou.jar`。

希拉两张死亡休整图的 `back_hillah` 缺失脚本也已转换：`262030310/in00 -> 262030300`，`262031310/in00 -> 262031300`；阿斯旺安全图 `262000000/out00` 直接返回 `910000000`，并删除缺失的 `BPReturn_Hillah/connect_UIOpen` 依赖。

万能传送会显式检查并生成对应 Boss，不再依赖地图首次加载时的静态 life 缓存。

旧端 `LifeFactory` 将 `PADamage/PDDamage/MADamage/MDDamage/level` 作为 Mob 必填字段。白发希拉及四个附属实体的神说数据缺少防御字段，现已补齐；否则地图读取到对应 life 时会空指针并被判定为未知地图。`MapFactory` 同时会跳过单个无法加载的 life，`ReactorFactory` 对缺失 Reactor 降级为空机制，避免附属资源拖垮整张地图。

守护天使绿水灵的高版本 `base` 门和 foothold `141` 位于旧客户端相机范围外，会导致角色与 Boss 都不可见，但服务端 Boss 仍能攻击。兼容版改为从可见的 `sp` 门进入，并在相邻 foothold `28` 的 `(703,-1394)` 生成 `8880700`。

卡洛斯与守护天使绿水灵的 Boss 血条图标不再映射到 `9300184` 的 1×1 占位 Canvas，而是复制旧端已验证的 25×25 实体 Canvas，避免有 Boss 对象和血量包却不显示血条。

## 兼容处理

- 所有 EMS Canvas 解码后以 GMS key、ARGB4444 重编码，降低纹理内存和补丁体积。
- 客户端 HP 保持 20 亿安全值，服务端主 Boss 使用 50 亿 long HP。
- 高版本专属技能规则映射到当前客户端和服务端已有的 MobSkill 等级，保留原 `attack/skill` 动画。
- 守护天使绿水灵失效的 `skill1/0 -> skill7/12` 改为现有 `attack3/0`。
- 神说源包中无法解码且解压结果为空的装饰 Canvas 降级为 1×1 透明节点，其余可解码画面不裁剪。
- 卡洛斯26张大攻击帧边长超过2048；当前补丁保留原尺寸，仅用ARGB4444压缩，需实机确认显卡纹理上限。

## 复现与审计

```bash
rtk python3 tool/scripts/migration/migrate_shenshuo_boss_pack.py
rtk python3 tool/scripts/audit/audit_shenshuo_boss_pack.py
```

当前范围：`mobs=15 maps=12 canvas=2750 over2048=26`。

## 安装与生效确认

补丁目录结构以 `BeiDou-Server` 为根目录。必须同时覆盖客户端 `clien/Data` 和服务端 `gms-server`，只覆盖客户端会导致万能传送提示地图不存在，只覆盖地图 XML 会导致进入后没有 Boss。

补丁中的新增地图 XML 同时放在 `gms-server/wz/Map.wz/Map` 和 `gms-server/wz-zh-CN/Map.wz/Map`。服务端只要检测到整个 `wz-zh-CN/Map.wz` 目录，就会优先使用语言 WZ 并忽略普通 Map.wz；因此手机端已有语言 Map.wz 时，两套路径都必须覆盖，否则即使提示普通 WZ 文件存在，地图仍会被判定为不存在。

不要把整个 `Boss` 文件夹复制进 `gms-server`。正确结果应是 `BeiDou-Server/gms-server/wz/...`，不能出现 `BeiDou-Server/gms-server/gms-server/wz/...`。服务端实际启动目录中还应直接存在 `BeiDou.jar`、`wz` 和 `scripts-zh-CN`。

```bash
cd /Users/lizixian/Documents/mxd/BeiDou-Server
rsync -a /Users/lizixian/Downloads/Boss/ ./
test -f gms-server/wz/Map.wz/Map/Map4/450009301.img.xml
test -f gms-server/wz/Map.wz/Map/Map9/900000207.img.xml
test -f gms-server/wz/Mob.wz/8880700.img.xml
python3 tool/scripts/audit/audit_shenshuo_boss_pack.py
```

覆盖后必须完全停止旧 Java 进程再启动；地图和怪物 WZ 会被服务端缓存，热替换 XML 不会刷新。服务端应从 `BeiDou-Server/gms-server` 对应的项目启动，避免读取另一份旧 `wz` 目录。

补丁包含已重新构建的 `gms-server/BeiDou.jar`。启动脚本会先切换到自身目录，确保相对路径指向同目录下的 `wz` 与 `scripts-zh-CN`。若万能传送仍报告资源未加载，最新版提示会列出当前进程检查的两个绝对路径及文件是否存在；如果仍显示旧版“无法去到不存在的地图”，表示运行服没有加载补丁中的万能传送脚本。
