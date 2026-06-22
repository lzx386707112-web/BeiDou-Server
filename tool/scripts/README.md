# Tool Scripts 工具包说明

这套脚本是在 macOS 环境下写的，路径和命令格式也都是按 Mac 来的。

如果你是在 Windows 环境使用，不建议直接运行这些 `.sh` 脚本。可以把脚本内容和你的目录结构发给 AI，让 AI 帮你翻译成对应的 `.bat`、`.ps1` 或 Windows 可用命令。

## 使用前需要准备

### 1. JDK 21

服务端打包、启动，以及 WZ 打包工具都需要 JDK 21。

如果脚本自动找不到 JDK 21，可以手动指定：

```sh
JAVA_HOME_21=/path/to/jdk21 rtk tool/scripts/package_server_jar.sh
```

### 2. Maven

服务端打包需要 Maven。

```sh
mvn -version
```

### 3. OrzRepacker / orange-wz

客户端 `.img -> .wz` 打包依赖 OrzRepacker 的 `lib` 目录。

项目地址：

```text
https://github.com/leevccc/orange-wz
```

当前脚本默认使用的本机目录是：

```text
/Users/lizixian/Documents/mxd/OrzRepacker-v1.157.48
```

如果你自己的 OrzRepacker 放在别的位置，可以设置：

```sh
ORZ_REPACKER_HOME=/你的/OrzRepacker路径 rtk tool/scripts/pack_img_wz.sh ...
```

或者直接让 AI 根据你的实际目录修改脚本里的 `DEFAULT_ORZ_HOME`。

### 4. wz-python

`wzpy.sh` 和部分辅助检查依赖 `wz-python`。

项目地址：

```text
https://github.com/Leonana69/wz-python
```

当前工具包里已经放了一份：

```text
tool/wz-python
```

## 目录和路径说明

这些脚本是按当前项目结构写的，默认认为：

```text
BeiDou-Server/
  clien/Data
  gms-server
  tool/scripts
  tool/orange-wz
  tool/wz-python
```

如果你的客户端目录、服务端目录、OrzRepacker 目录不一样，可以把你的目录结构告诉 AI，让 AI 帮你调整脚本里的路径。

## 每个脚本的作用

### `pack_img_wz.sh`

客户端 `.img -> .wz` 打包脚本。

不带参数运行时，会进入交互式操作，用于把客户端 `clien/Data` 里的散 `.img` 打包成根目录用的 `*.wz`。

选择“全部目录”时，会打包出：

```text
Base.wz
Character.wz
Effect.wz
Etc.wz
Item.wz
Map.wz
Mob.wz
Morph.wz
Npc.wz
Quest.wz
Reactor.wz
Skill.wz
Sound.wz
String.wz
TamingMob.wz
UI.wz
```

其中 `Base.wz` 会自动包含 `Data` 根目录下的 `.img`，以及 `Character`、`Skill`、`UI` 等一级目录索引。

示例：

```sh
rtk tool/scripts/pack_img_wz.sh
rtk tool/scripts/pack_img_wz.sh --input clien/Data/Skill --output "$HOME/Downloads/Skill.wz" --version 83
```

### `pack_xml_wz.sh`

旧的 `.img.xml -> .wz` 辅助脚本。

一般不推荐使用，除非你明确知道自己要把 XML 格式重新打包成 WZ。

不带参数运行时不会自动打包，会提示你改用 `pack_img_wz.sh` 或显式传入参数。

### `package_server_jar.sh`

服务端打包脚本。

会把 `gms-server` 打包成：

```text
gms-server/BeiDou.jar
```

示例：

```sh
rtk tool/scripts/package_server_jar.sh
```

### `start_server.sh`

启动当前服务端。

默认启动：

```text
gms-server/BeiDou.jar
```

示例：

```sh
rtk tool/scripts/start_server.sh
```

后台启动：

```sh
rtk tool/scripts/start_server.sh --background
```

### `png2canvas.sh`

交互式 PNG 写入 Canvas 工具。

只保留交互式操作。直接运行后按提示选择单张 PNG 或 PNG 帧目录。
如果要替换 `Skill.wz/122.img.xml` 里 `1221009/effect` 的一组帧，通常选择：

```text
目标 XML: Skill.wz 技能节点
Skill img ID: 122
技能节点 ID: 1221009
图片节点名: effect
PNG 来源: PNG 帧目录
图片分组: 0
帧画布命名方式: 按序号
```

这样会把排序后的 PNG 写到 XML 内部路径 `skill/1221009/effect/0/0`,
`skill/1221009/effect/0/1`, `skill/1221009/effect/0/2` ...。

示例：

```sh
rtk tool/scripts/png2canvas.sh
```

### `png2canvas/png_to_img_canvas.py`

`png2canvas.sh` 调用的底层 Python 实现，单独放在 `png2canvas/` 目录里，一般不用直接运行。

### `wzpy.sh`

`wz-python` 的包装脚本，用来解析、转换、检查 WZ 或单个 `.img`。

示例：

```sh
rtk tool/scripts/wzpy.sh convert clien/Data/Skill/1112.img --region GMS -o /tmp/1112.img.json
```

## 打包客户端后的处理

打包出 `*.wz` 后，需要把这些 WZ 文件放到客户端根目录。

例如：

```text
客户端目录/
  BeiDou.exe
  Base.wz
  Character.wz
  Skill.wz
  UI.wz
  ...
```

确认 WZ 都放到根目录后，再删除原来的：

```text
客户端目录/Data
```

不要保留一个旧的 `Data` 目录和新的根目录 WZ 混着用，容易造成客户端读取到错误资源。

## 手机端运行注意

如果客户端要在手机端运行，需要替换这两个 DLL：

```text
ijl15.dll
2ijl15.dll
```

工具包里放了一份验证可用的手机端 DLL：

```text
tool/client-runtime/ijl15_手机用.dll
tool/client-runtime/2ijl15_手机用.dll
```

为了避免误覆盖，文件名带了 `_手机用` 后缀。

真正放进客户端根目录时，需要改回原名：

```text
ijl15_手机用.dll  -> ijl15.dll
2ijl15_手机用.dll -> 2ijl15.dll
```

这两个 DLL 必须成套替换。如果没有替换，或者两个 DLL 版本不匹配，手机端启动时可能会报找不到资源、资源读取失败，或者类似 `0x80030002` 的错误。

## 连接服务器注意

客户端根目录的 `config.ini` 要改成实际服务器地址和游戏登录端口。

本项目默认：

```ini
ServerIP_Address=127.0.0.1
serverIP_Port=19696
```

注意：`8686` 是 HTTP/API/Swagger 端口，不是游戏登录端口。
