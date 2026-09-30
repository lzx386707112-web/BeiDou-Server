# 武器鞋子清理交付

## 结果

- 按用户最终决定，保留引用清单中的 39 个 ID，完整删除其余 315 个 ID。
- 删除 291 件武器、24 双鞋子的客户端 IMG 和服务端 XML，共 630 个文件。
- 同步删除客户端 String/Eqp.img 和两份服务端 String XML 中的 315 条名称。
- 管理装备目录移除 315 条记录；Weapon 手册移除 1 行；Shoes 手册原本没有这些 ID，保持不变。
- 任务、NPT、商城、融合、套装、Java、DLL 均未改动。
- 删除文件原内容在 Git HEAD 中，可按删除清单逐文件恢复；没有删除工作区根目录或用户原有改动。

## 交付目录和精确文件表

`/Users/lizixian/Downloads/武器鞋子清理/`

| 文件 | 用途 |
| --- | --- |
| Data/String/Eqp.img | 客户端名称表 |
| gms-server/wz/String.wz/Eqp.img.xml | 服务端默认名称表 |
| gms-server/wz-zh-CN/String.wz/Eqp.img.xml | 服务端中文名称表 |
| gms-server/src/main/resources/equipment-catalog/catalog.json | 管理装备目录 |
| gms-server/handbook/Equip/Weapon.txt | 装备手册 |
| gms-server/src/main/resources/db/migration/V2.1.105__remove_unreferenced_weapon_shoe_ids.sql | 数据库清理迁移 |
| removed-equipment-files.json | 精确删除路径、ID、原文件 SHA-256 |
| remove_equipment_files.ps1 | Windows 删除助手，默认仅预览 |
| 使用说明.md | 本说明 |

没有交付未修改的任务、商城、脚本或 DLL，也没有打包 WZ 或构建服务端 JAR。

## 在已有安装目录应用

仅覆盖交付包无法删除旧装备文件，必须同时按清单删除旧文件。

1. 停止客户端和服务端，备份客户端、服务端和数据库。
2. 在 PowerShell 中运行删除助手预览，`ClientRoot` 是包含 `Data` 的客户端根目录；可选 `ServerRoot` 是包含 `wz` 的服务端根目录：

   ```powershell
   .\remove_equipment_files.ps1 -ClientRoot 'D:\BeiDouClient' -ServerRoot 'D:\BeiDouServer'
   ```

3. 确认预览后加 `-Execute` 删除。助手只处理清单中的 315 个 ID，校验原文件 SHA-256 后才删除；文件已不存在会跳过，原内容不匹配会停止，默认预览不会删除：

   ```powershell
   .\remove_equipment_files.ps1 -ClientRoot 'D:\BeiDouClient' -ServerRoot 'D:\BeiDouServer' -Execute
   ```

4. 将 `Data/String/Eqp.img` 覆盖到客户端对应位置，将 `gms-server/` 下各文件覆盖到服务端相同相对路径。
5. 数据库清理 SQL 已生成但没有在本机执行。它会删除已删装备的获取配置，以及背包、穿戴、邮件、市场、额外仓库中的副本；39 个保留 ID 不在迁移中。正式环境需备份后通过正常 Flyway 部署应用。若运行的是已有 JAR，需要在下一次正式构建中包含新迁移和装备目录；本次没有构建 JAR。

删除助手没有在 Windows 环境执行验证。本机静态核查了默认预览、精确路径、保留 ID 排除、SHA-256 前置校验和无递归删除。

## 已通过的验证

- 8 个删除契约测试通过：删除文件、保留文件、名称记录、XML、目录/手册、SQL 边界、幂等性和删除清单。
- 保留的 39 件装备及其相关文件共 100 个文件 SHA-256 完全不变。
- 客户端名称 IMG 完整解析无截断、无警告，除批准删除记录和父块计数/长度外，其他原始记录字节与顺序完全不变。
- 两份服务端名称 XML 只删除批准节点，其余记录原文和顺序完全不变。
- 修改的名称 IMG 不含 Canvas；没有修改任何保留装备的 Canvas，因此没有新增 Canvas 格式或解码风险。
- 生成器第二次运行零写入、零删除，所有产物哈希稳定。
- Python 语法检查、`git diff --check` 和剩余资源引用扫描通过。
- 交付文件逐一对比源和目标 SHA-256，结果记录在仓库交付报告中。

## 仍需实际环境验证

启动、登录、背包和装备栏、保留装备的穿戴与外观、任务奖励、融合、套装、商城、百宝箱、切图，以及数据库迁移后的掉落/商店和存量装备清理。离线检查不能证明旧 Windows/Winlator 客户端实际行为。
