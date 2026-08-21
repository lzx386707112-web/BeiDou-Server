# BeiDou Windows Dependency Check

`BeiDouDependencyCheck.exe` 是给最终用户使用的只读 Windows 加载依赖检查器。它不
注册 DLL、不修改系统、不启动游戏，也不加载客户端 DLL 的入口代码。

## 使用方法

1. 将 `BeiDouDependencyCheck.exe` 放在 `BeiDou.exe` 同一目录。
2. 双击运行。
3. 将同目录新生成的 `BeiDouDependencyReport.txt` 发给维护者。

报告会检查：

- 客户端根目录全部 `.exe` 和 `.dll` 是否为有效的 32 位 PE；
- 普通导入和延迟导入引用的 DLL；
- 依赖来自客户端目录还是 Windows 32 位系统环境；
- 缺失或无法加载的 Win32 模块及错误码；
- 依赖 DLL 是否缺少调用方要求的导出函数或序号；
- VC 2015-2022 x86、VC 7.1 和 DirectX 8 等常见运行库问题。

检查器本身使用无 CRT 构建，只导入 `KERNEL32.dll` 和 `USER32.dll`。因此用户缺少
VC/UCRT 时，检查器仍然能运行并报告问题。

## 构建

在仓库根目录运行：

```bash
rtk bash tool/client-debug/dependency-check/build.sh
```

输出文件：

```text
clien/BeiDouDependencyCheck.exe
```

构建脚本会拒绝带有 `KERNEL32.dll`、`USER32.dll` 以外运行时导入的产物，防止诊断器
自身重新引入 VC/UCRT 依赖。链接时不写入 PE 时间戳，相同源码的重复构建哈希应一致。

## 边界

这是静态 PE 和加载器环境检查，不能证明游戏运行时创建 COM/PCOM 对象一定成功。
如果报告全部通过，但 Windows 仍显示 `0x80040154` 或 `Class not registered`，需要
同时提供完整弹窗、错误码和客户端诊断日志，继续定位具体类创建调用。不要对整个客户
端目录批量执行 `regsvr32`；多数旧客户端 DLL 不提供自注册入口。
