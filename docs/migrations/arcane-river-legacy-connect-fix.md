# 神秘河全地图旧端连接节点修复

## 范围

- 审计地图：152 张（`migrate_arcane_river_fields.py` 的完整白名单）
- 实际修改地图：141 张
- 无需修改：`450003100`、`450003330`、`450003430`、`450005100`、
  `450005200`、`450005300`、`450006000`、`450006200`、`450006240`、
  `450007000`、`450007200`

## 已修复

- 3352 个现代 `connect` 对象改用旧端 `rope/0` 或 `ladder/0`。
- 按 672 条 `ladderRope` 碰撞坐标重新铺设显示节点。
- 保留并旧端化 71 个不属于攀爬碰撞的装饰连接对象。
- 删除 669 个不兼容的 `ladderRope/piece` 字段。
- 将 223 个 `pt=10` 光洞降级为旧端 `pt=3`。
- 长绳优先使用旧端 `rope/0/3` 的 120 像素段，最终连接对象数为 3946，
  避免全部用 30 像素段造成额外负载。
- 无名村继续使用已实测的 `Obj/extinction.img`（42 个引用分支、145 张 Canvas）。
- 无名村的旧端绳索对象必须位于各对象层开头并连续编号：layer 2 为
  `0-11`，layer 3 为 `0-5`。批处理不得在删除后把它们追加到层末尾。
- 其余 28 张消亡旅途地图改用隔离的 `Obj/extinctionLegacy.img`
  （73 个引用分支、169 张 Canvas），避免共享资源裁剪导致缺失。

## 验证结果

- 所有 `connect` 引用均存在，且 `l1` 均为旧端样式 `0`。
- 所有 672 条绳/梯碰撞都有对应显示对象。
- 修复脚本重复执行后，无名村 IMG 字节保持不变。
- 全部地图中不存在 `pt=10` 或 `ladderRope/piece`。
- 152 张客户端地图与服务端 XML 逐份完全一致。
- 完整闭包审计：152 张地图、83 个怪物、182 个 NPC、16 首 BGM、
  27 个地图资源文件、9901 张 Canvas。
- 最终结果：`errors=0 warnings=0`。

## 对象顺序回归复核

无名村实机确认后，对 152 张地图重新检查 connect 在对象层中的顺序和编号：

- 136 张地图含 connect，16 张不含 connect。
- 37 张含 connect 的地图原本已经是层前部连续编号，无需修改。
- 99 张地图存在与无名村相同的“删除后追加”痕迹，已只调整对象顺序与编号。
- 99 张按区域分布：消亡旅途 23、啾啾岛 24、拉克兰 22、阿尔卡娜 4、
  莫拉斯 9、埃斯佩拉 17。
- 修复前后逐图对象属性多重集完全一致；没有增删对象，也没有改动坐标、资源、
  Portal、foothold、life 或 ladderRope。
- 完整修复流程再次执行后，152 张地图全部保持字节不变。

## 维护入口

- 修复脚本：`tool/scripts/migration/repair_arcane_river_legacy_connect.py`
- 消亡旅途资源隔离：`tool/scripts/migration/repair_arcane_river_extinction_asset.py`
- 迁移规则：`tool/scripts/migration/migrate_arcane_river_fields.py`
- 审计脚本：`tool/scripts/audit/audit_arcane_river_fields.py`
