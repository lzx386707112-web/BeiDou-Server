# Tool Scripts

按用途分类：

- `audit/`：资源和链路审计脚本。
- `migration/`：一次性内容迁移脚本。
- `package/`：服务端和客户端 WZ 打包脚本。
- `runtime/`：本地服务启动脚本。
- `wz/`：WZ/IMG 解析工具包装脚本。
- `png2canvas/`：PNG 写入客户端 IMG Canvas 的网页工具。
- `patch-client/`：客户端 EXE 级补丁。
- `patch-skill/`：技能数据、技能特效和技能 EXE 行为补丁。
- `patch-boss/`：Boss 兼容和技能映射补丁。
- `patch-equipment/`：装备数据补丁。

详细用法见 [../../docs/tools/tool-scripts.md](../../docs/tools/tool-scripts.md)。

## 保留策略

- `migration/` 中的脚本虽然通常只向生产数据写入一次，但也是资源来源、允许变更集和幂等验证的一部分，不按“执行完毕”删除。
- `audit/` 和 `test_*_contract.*` 是回归检查，必须与对应迁移或补丁一起保留。
- 神秘河早期 A/B、`no_*` 和临时恢复脚本已在正式迁移、修复、审计与完整同步链路接管后清理；排障结论保留在 `docs/` 和 Git 历史中。
- 废弃结论必须按消费者判断：`effect/90..93` 不再用于 MCV 视频层，但仍被神说五转附加效果和 `patch_1121013_raging_blow_vi_attack.py` 使用，因此相关共享补丁保留。
- `patch-*` 中明确写有 restore/retire 的脚本是回滚或删除生成器，不等于无用脚本。
- `__pycache__/`、`*.pyc`、`.DS_Store`、构建目录和依赖下载缓存都是本机生成物，应保持未跟踪并可直接重建。
