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
