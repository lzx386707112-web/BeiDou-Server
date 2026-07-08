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
- 新增或改造技能时，先看 [新增技能与 BeiDou.exe 识别记录](docs/patches/new-skills-exe-notes.md)。其中记录了龙神技能、矩形 AoE、`1121001` 磁石改造成轻舞飞扬式攻击，以及继续迁移成 `400011124` 剑影分身的完整排查过程：WZ 数据、`effect/effect0`、服务端技能类型、EXE 小端编码、code cave 追加判断、伤害延迟和攻击范围对齐。
