本项目基于Cosmic来的汉化和优化，Cosmic地址：https://github.com/P0nk/Cosmic   

# BeiDou由来
北斗卫星导航系统（Beidou Navigation Satellite System，简称：BDS，又称为：COMPASS，中文音译名称：BeiDou）是中国自行研制的全球卫星导航系统，也是继GPS、GLONASS之后的第三个成熟的卫星导航系统。北斗卫星导航系统（BDS）和美国GPS、俄罗斯GLONASS、欧盟GALILEO，是联合国卫星导航委员会已认定的供应商。  
北斗卫星导航系统由空间段、地面段和用户段三部分组成，可在全球范围内全天候、全天时为各类用户提供高精度、高可靠定位、导航、授时服务，并且具备短报文通信能力。经过多年发展，北斗系统已成为面向全球用户提供全天候、全天时、高精度定位、导航与授时服务的重要新型基础设施。北斗系统定位导航授时服务，通过30颗卫星，免费向全球用户提供服务，全球范围水平定位精度优于9米、垂直定位精度优于10米，测速精度优于0.2米/秒、授时精度优于20纳秒。  
北斗这一词对于中国来说，有着特殊的意义。北斗，是中国的一个卫星导航系统，也是中国自主研制的第一个卫星导航系统。既然小伙伴说这个项目也要整个天体的名字，想了半天，就叫北斗好了！这也意味着我们要做的比HeavenMS和Cosmic更加优秀和强大！  

# 开发进展
[开发进展](https://github.com/BeiDouMS/BeiDou-Server/wiki/%E5%BC%80%E5%8F%91%E8%BF%9B%E5%BA%A6)

# gms-server 服务端
- 已实现自动创建数据库，执行初始化sql脚本，只要保证mysql是启动的即可  
- 已开放api端口8686
- 已引入swagger，swagger地址：http://localhost:8686/swagger-ui/index.html
- 接口由版本控制，如：v1 v2 v3。默认的swagger标签为name = ApiConstant.LATEST，默认的RequestMapping为："/" + ApiConstant.LATEST + "/xx"
- 接口如果增加新版本且接口不需要更新，只需要把ApiConstant.LATEST指向新版本即可。如果部分接口不兼容，需要把旧接口的Tag和RequestMapping都改成指定版本，如：ApiConstant.V1。其他的，只需要把ApiConstant.LATEST指向新版本即可。
- 支持多语言，脚本和wz针对多语言会读取不同的路径：wz-zh-CN，wz-en-US，script-zh-CN，script-en-US
- 不支持MySQL8以下的版本

## 开发环境
- OpenJDK 21：https://jdk.java.net/archive/
- Intellij IDEA 2023.3及以上：https://www.jetbrains.com/idea/
- MySQL8：https://github.com/SleepNap/NapMysqlTool/releases/latest 或者 https://downloads.mysql.com/archives/community/
- Maven：https://maven.apache.org/download.cgi
- git：https://git-scm.com/downloads
- DBeaver：https://dbeaver.io/download/ 或者 Navicat Lite：https://www.navicat.com/en/download/navicat-premium-lite

# gms-ui web端

## 开发环境部署

请根据自身实际情况选择性跳过已完成的步骤

**1 安装 NodeJS v20.15.0 （LTS 版）**

下载地址：https://nodejs.org/dist/v20.15.0/node-v20.15.0-x64.msi

**2 安装 Yarn**

```shell
npm install -g yarn
```

> 如提示npm命令不存在，可能是安装NodeJS时，安装程序配置的环境变量还没有生效，小白请使用重启大法

**3 初始化前端开发环境**

在命令行进入 gms-ui 目录，然后执行命令

```shell
yarn install
```

**4 启动开发环境**

```shell
yarn dev
```

## 备注
web中所有的图片均需要联网获取，感谢 https://maplestory.io 提供给的图片接口！  

# 客户端
服务端和客户端已经打包好了在[Release](https://github.com/BeiDouMS/BeiDou-Server/releases)中，大家直接下载即可。  
如果想下载北斗客户端的**早期Beta的版本**，可以[点击这里了解更多](https://github.com/BeiDouMS/BeiDou-Server/wiki/%E5%8C%97%E6%96%97%E5%AE%A2%E6%88%B7%E7%AB%AF%E5%8F%91%E5%B8%83) 

## 客户端 WZ 打包注意事项

如果把客户端 `Data` 目录下的散 `.img` 重新打包成根目录下的 `*.wz`，不能只把每个子目录分别打成 `Character.wz`、`Skill.wz` 等文件，还需要特别处理 `Base.wz`。

`Base.wz` 必须同时包含两类内容：

- `Data` 根目录下的 `.img` 文件，例如 `StandardPDD.img`、`smap.img`、`zmap.img`
- `Data` 下一级目录的空目录索引，例如 `Character`、`Effect`、`Item`、`Map`、`Mob`、`Skill`、`UI` 等

如果 `Base.wz` 只包含根目录 `.img`，缺少这些一级目录索引，客户端可能在启动早期报错，例如 `0x80030002`。

推荐使用脚本：

```shell
rtk tool/scripts/pack_img_wz_wizard.sh
```

选择“全部目录”时，脚本会自动生成正确结构的 `Base.wz`，并把各一级目录分别打包成对应的 `*.wz`。

另外，根目录运行库 `ijl15.dll` 和 `2ijl15.dll` 需要成套匹配。`ijl15.dll` 是客户端加载的 JPEG 库代理/补丁 DLL，`2ijl15.dll` 是实际的 Intel JPEG Library。如果这两个 DLL 版本不匹配，客户端可能在启动或加载资源阶段直接报错。遇到启动期资源错误时，除了检查 WZ，也要确认这两个 DLL 来自同一套可运行客户端。


# 095 内容迁移记录

来源目录：`/Users/lizixian/Documents/mxd/怀旧岛V095仿官版/怀旧岛V095服务端`。本次仅做资源与脚本盘点，未直接迁移文件。

## 差异概览

与当前 beidou 资源相比，095 服务端 WZ 大约多出：

- 怪物：575 个
- 地图：703 张

095 是 Windows 成品包，`ZeroMS/095.jar` 不是普通 JVM 可直接加载的 jar，直接 `java -cp ZeroMS/095.jar:lib/* server.Start` 会报 `ClassFormatError`。因此更现实的路线是把可读的 WZ、脚本、入口 NPC 逐步迁入 beidou，而不是迁移 095 服务端本体。

## 优先迁移目标

### 第一批：进阶扎昆

适合作为迁移试点，资源范围小，现有 beidou 已有普通扎昆逻辑可参考。

- 怪物：`8800100-8800116`
- 地图：`211042301` 进阶扎昆入口、`280030001` 进阶扎昆的祭台
- 095 脚本：`scripts/event/ChaosZakum.js`
- beidou 参考：`scripts/event/ZakumBattle.js`

### 第二批：进阶暗黑龙王

可以参考 beidou 现有普通龙王事件，主要补充进阶龙王怪物、地图与召唤流程。

- 怪物：`8810100-8810130`
- 地图：`240060001`、`240060101`、`240060201`
- 095 脚本：`scripts/event/ChaosHorntail.js`
- beidou 参考：`scripts/event/HorntailBattle.js`

### 第三批：希纳斯 / 未来之门

内容价值高，但依赖范围比前两批大，需要整套地图、怪物、NPC、入口与事件脚本配合。

- 怪物：`8850000-8850013`，包含米哈尔、奥兹、伊莉娜、伊卡尔特、胡克、神兽、希纳斯
- 地图：`271000000` 起的未来之门、破坏的射手村、骑士团要塞；重点入口 `271040000`、`271040100`
- 095 脚本：`scripts/event/CygnusBattle.js`

### 第四批：埃德尔斯坦 / 反抗者区域

地图资源相对完整，但如果继续迁职业、技能、任务链，成本会明显提高。

- 地图：`310000000` 起，包含埃德尔斯坦、反抗者本部、莱班矿山、格里梅尔研究所
- 注意：反抗者职业相关逻辑可能涉及客户端、技能、任务、包处理，不建议作为第一批迁移内容。

## 暂缓迁移内容

以下内容在 095 脚本中存在，但实际 WZ 资源不完整或与当前版本跨度较大，暂不作为第一批目标：

- Hilla：`scripts/event/HillaBattle.js`，引用 `262030300`、`8870000`
- Arkarium：`scripts/event/ArkariumBattle.js`，引用 `272020200`、`8860000`
- Magnus：`scripts/event/BossMagnus_HARD.js`，引用 `401060100`、`8880000`
- Root Abyss 四 Boss：`BossBanban_CHAOS.js`、`BossBelen_CHAOS.js`、`BossBloody_CHAOS.js`、`BossPierre_CHAOS.js`

这些脚本更像高版本内容混入或残留，迁移前需要先确认客户端 WZ、服务端 WZ、包结构和入口 NPC 是否完整。

## 迁移注意事项

- 服务端和客户端 WZ 必须同步迁移；只拷服务端 XML，客户端缺素材时会黑图、缺怪或闪退。
- beidou 脚本风格偏 HeavenMS/Cosmic，095 脚本偏老 Odin 风格。095 中的 `em.getMonster(...)`、`setInstanceMap(...)`、`disposeIfPlayerBelow(...)` 等调用需要按 beidou 现有事件脚本改写。
- 先迁一个闭环 Boss：地图 XML、怪物 XML、String 名称、NPC/反应堆入口、event 脚本、掉落/奖励，再进游戏验证。
- Tokyo、拉瓦那、马来西亚等内容 beidou 已有较多资源，优先级低于上述新增 Boss 和地图。

# docker
原服务端中docker相关配置已移除，配置已独立到[新的仓库](https://github.com/BeiDouMS/BeiDou-docker)，且支持[镜像拉取](https://github.com/BeiDouMS/BeiDou-docker/pkgs/container/beidou-server-all)。想参加docker开发，欢迎在新仓库进行pr。  
[了解更多](https://github.com/BeiDouMS/BeiDou-docker)

# Wiki
发现很多同学的问题基本在Wiki中都有答案，欢迎大家去看看。另外如果发现Wiki中没有的问题，欢迎提issue，或直接补充。已将Wiki开放为所有人都可以编辑。  
[Wiki地址](https://github.com/BeiDouMS/BeiDou-Server/wiki)
