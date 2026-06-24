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

### 3. Node.js / npm

`package_server_jar.sh` 默认会构建并内置 `gms-ui` 后台管理页面，因此需要 Node.js / npm。

```sh
node -v
npm -v
```

如果只想打包服务端，可以加 `--skip-ui`。

### 4. OrzRepacker / orange-wz

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

### 5. wz-python

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

会先构建 `gms-ui`，把后台管理页面内置到服务端静态资源里，然后把 `gms-server` 打包成：

```text
gms-server/BeiDou.jar
```

示例：

```sh
rtk tool/scripts/package_server_jar.sh
rtk tool/scripts/package_server_jar.sh --skip-ui
```

### `start_server.sh`

启动当前服务端。优先运行 `gms-server/BeiDou.jar`；如果 jar 不存在，则改用 Spring Boot Maven 插件从源码启动。

默认启动：

```text
gms-server/BeiDou.jar 或 mvn spring-boot:run
```

示例：

```sh
rtk tool/scripts/start_server.sh
```

启动后可以打开后台管理：

```text
http://localhost:8686/
```

后台启动：

```sh
rtk tool/scripts/start_server.sh --background
```

### `png2canvas.sh`

PNG 写入客户端 `.img` Canvas 的网页工具。

直接运行后打开浏览器访问 `http://127.0.0.1:8765`。页面会并排读取客户端
`.img` 和服务端 `.img.xml`，用树形结构对照节点关系，并在右侧显示客户端预览、
服务端同步状态、元数据差异和常见节点含义。
项目 `.img`、其他服 `.img`、服务端 `.img.xml` 路径可以手动填写，也可以点输入框旁边
的“选择”按钮从本机目录里浏览选择。

如果要替换游戏端 `clien/Data/Skill/122.img` 里 `1221009/effect` 的一组帧，通常选择：

```text
Skill img ID: 122
技能节点 ID: 1221009
图片节点名: effect
图片分组: 0
```

这样会把排序后的 PNG 写到客户端 `.img` 内部路径 `skill/1221009/effect/0/0`,
`skill/1221009/effect/0/1`, `skill/1221009/effect/0/2` ...。
替换时可以先点“预览替换”，确认映射无误后再“写入并同步”。服务端 XML 会同步
`width`、`height`、`origin`、`delay`、`z` 等元数据。

如果某个节点结构需要从目录改成单张图片，例如把 `skill/1221009/effect/0`
这个帧组目录换成普通 canvas，可以在树里选中该节点，选择“单图 PNG”，再点
“替换选中”。也可以用“删除节点”移除当前节点，或在当前目录下输入“新节点名”
后点“添加图片节点”。

如果已经加载了其他服 `.img`，可以选中一个节点后点“分析选中”，工具会生成一份
可编辑的计划 JSON。JSON 里的 `operations` 可以调整 `sourcePath`、`targetPath`、
`replace` 和 `syncXml`，改好后先点“预览 JSON”，确认无误再点“应用 JSON”批量更新
客户端 `.img` 并同步服务端 XML。

示例：

```sh
rtk tool/scripts/png2canvas.sh
```

### `png2canvas/web_app.py` / `png2canvas/replace_img_canvas.py`

`png2canvas.sh` 调用的网页和底层 Python 实现，单独放在 `png2canvas/` 目录里，一般不用直接运行。

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
