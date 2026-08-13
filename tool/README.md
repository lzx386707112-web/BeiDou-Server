# Tool Directory

`tool` 目录按用途分组：

- `scripts/`：项目维护、迁移、补丁、打包和运行脚本。
- `orange-wz/`：WZ 打包/编辑工具源码。
- `wz-python/`：WZ/IMG 解析与辅助转换工具。
- `client-debug/`：客户端调试注入和日志工具。
- `client-video/`：客户端 MCV 导出、解码和播放工具。
- `client-runtime/`：客户端运行库和有文档记录的回滚基线。

脚本使用说明见 [docs/tools/tool-scripts.md](../docs/tools/tool-scripts.md)。

## 生命周期分类

| 分类 | 目录 | 处理原则 |
| --- | --- | --- |
| 长期基础工具 | `orange-wz/`、`wz-python/`、`scripts/package/`、`scripts/runtime/`、`scripts/wz/`、`scripts/png2canvas/` | 保留源码；删除本机构建目录和缓存 |
| 可重复生成与校验 | `scripts/migration/`、`scripts/audit/`、各目录的 `test_*_contract.*` | 即使迁移已经执行也保留，用于重建、幂等校验和兼容性审计 |
| 产品补丁 | `scripts/patch-*`、`client-debug/`、`client-video/` | 只保留当前补丁、回滚工具和有运行证据的诊断工具 |
| 历史单变量实验 | 神秘河 A/B、`no_*` 等旧排障脚本 | 完成根因定位且正式生成/审计链路接管后删除；设计记录和源码仍可从文档及 Git 历史追溯 |
| 本机生成物 | `target/`、`build/`、`.deps/`、`__pycache__/`、`*.pyc`、`.DS_Store` | 不入库，可随时删除并由构建或运行重新生成 |

## 清理边界

不要仅凭“没有被其他脚本 import”删除迁移脚本。很多脚本是命令行入口，且现有
IMG/WZ 的来源只能通过对应生成器和合同测试追溯。删除候选至少要同时满足：

1. 文档或最终实现已经明确声明它被淘汰；
2. 不再被源码、构建、测试、文档命令或交付流程引用；
3. 不是当前资源的唯一生成器、回滚脚本或二进制兼容证据；
4. Git 历史或其他明确基线可以恢复所需内容。

本机缓存不属于项目资产。运行 `git status --short --ignored tool` 可以识别这类
文件；清理时只删除明确的缓存目录，避免用覆盖整个 `tool` 的通配命令。
