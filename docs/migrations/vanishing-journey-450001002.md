# 消逝的旅途 450001002 旧端兼容迁移

来源：`/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data`。

本轮迁入“地铁站入口” `450001002`。兼容投影后地图没有怪物或 NPC；现有
消逝的旅途背景、旧端 `extinctionLegacy` 对象、BGM 和地图标记已经覆盖大部分
依赖，只需向 `Obj/ReverseCity.img` 追加 `subway/obj/0`，并补入地图字符串。

`west00` 保留为返回 `450001000/north00` 的普通门。`east00` 只有现代剧情脚本、
没有可证明且已安装的地图目标，因此不迁入。无名村 `450001000` 保持已实机通过的
固定 SHA-256，不为本轮新增入口或改写记录。

所有新增 Canvas 均物化外链并转为 GMS ARGB4444：`format=1`、`format2=0`。
既有 `Obj/ReverseCity.img` 与 `String/Map.img` 只追加白名单原始记录。

静态验证命令：

```bash
rtk python3 tool/scripts/migration/migrate_vanishing_journey_450001002.py
rtk python3 tool/scripts/audit/audit_vanishing_journey_450001002.py
```

按本轮要求不做 WZ 打包验证。离线检查通过后，仍需在旧客户端验证启动、登录、
进入 `450001002`、向西回到无名村、地铁动画、BGM 和重复切图。
