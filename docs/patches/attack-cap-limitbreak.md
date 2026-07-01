# 攻击上限突破 19999999 说明

本文记录把当前角色真实输出上限从 `19999999` 提到 `2147483647` 需要同步修改的地方。

目标值使用 Java/C++ `int` 最大值：

```text
2147483647
```

## 1. 客户端配置

文件：

```text
clien/config.ini
```

需要确认以下三项都是 `2147483647`：

```ini
setDamageCap=2147483647
setMAtkCap=2147483647
setAtkOutCap=2147483647
```

含义：

- `setDamageCap`：物理攻击面板上限
- `setMAtkCap`：魔攻/魔防面板上限
- `setAtkOutCap`：真实输出上限

只改这里不够，因为客户端 DLL、武器 `limitBreak`、服务端伤害解码也会影响最终结果。

## 2. 客户端 DLL 硬编码上限

文件：

```text
clien/ijl15.dll
```

需要把 DLL 里的 `19999999` 常量改成 `2147483647`。

本次确认并修改的位置：

```text
0x3416c: int32 19999999 -> 2147483647
0x34170: int32 19999999 -> 2147483647
0x34180: double 19999999.0 -> 2147483647.0
```

对应小端字节：

```text
int32  19999999   = ff 2c 31 01
int32  2147483647 = ff ff ff 7f

double 19999999.0   = 00 00 00 f0 cf 12 73 41
double 2147483647.0 = 00 00 c0 ff ff ff df 41
```

校验命令：

```bash
rtk python3 - <<'PY'
from pathlib import Path
import struct

p = Path("clien/ijl15.dll")
data = p.read_bytes()

for name, needle in [
    ("i32_19999999", struct.pack("<I", 19999999)),
    ("f64_19999999", struct.pack("<d", 19999999.0)),
    ("ascii_19999999", b"19999999"),
    ("i32_2147483647", struct.pack("<I", 2147483647)),
    ("f64_2147483647", struct.pack("<d", 2147483647.0)),
]:
    offsets = []
    start = 0
    while True:
        index = data.find(needle, start)
        if index < 0:
            break
        offsets.append(index)
        start = index + 1
    print(name, len(offsets), [hex(x) for x in offsets[:20]])
PY
```

期望结果：

```text
i32_19999999 = 0
f64_19999999 = 0
ascii_19999999 = 0
f64_2147483647 包含 0x34180
i32_2147483647 包含 0x3416c、0x34170
```

补充：

- `clien/BeiDou.exe` 未发现相关 `19999999` 常量，本次没有修改。
- `clien/Canvas.dll` 曾扫到一个 `int32 19999999`，但位置更像资源/表数据误命中，实测成功不需要改。

### client-runtime 同步

如果使用下面目录里的独立客户端运行库，也要同步 DLL：

```text
tool/client-runtime/
```

本次处理的文件：

```text
tool/client-runtime/ijl15_手机用.dll
```

该 DLL 和 `clien/ijl15.dll` 大小不同，cap 表位置整体不同。同步修改的位置：

```text
0x3516c: int32 199999 -> 2147483647
0x35170: int32 1999 -> 2147483647
0x35180: double 199999.0 -> 2147483647.0
```

修改前已备份：

```text
tool/client-runtime/backup-before-attack-cap-20260630-142647/
```

`tool/client-runtime/2ijl15_手机用.dll` 没有发现需要同步的旧 cap 表值，本次未修改。

## 3. 武器 limitBreak

客户端和服务端的武器数据都要有：

```text
info/limitBreak = 2147483647
```

涉及目录：

```text
clien/Data/Character/Weapon/*.img
gms-server/wz/Character.wz/Weapon/*.img.xml
```
 

如果只给部分武器加 `limitBreak`，角色必须拿着带 `limitBreak` 的武器才能突破上限。当前做法是全武器补齐，所以理论上任意武器都可以突破。

## 4. 服务端高伤害解码

文件：

```text
gms-server/src/main/java/org/gms/net/server/channel/handlers/AbstractDealDamageHandler.java
```

原因：

客户端在暴击或特殊高伤害场景下，会把高于旧上限的伤害用负数形式发给服务端。服务端原逻辑是：

```java
if (eachd < 0) {
    eachd += Integer.MAX_VALUE;
}
```

这个解法少了 `+1`。结果就是客户端发出的 `20000000` 会被服务端还原成 `19999999`，看起来像上限仍然被定死。

修正方式：

```java
private static int decodeClientDamage(int damage) {
    if (damage >= 0) {
        return damage;
    }
    return (int) Math.min(Integer.MAX_VALUE, (long) damage + (long) Integer.MAX_VALUE + 1L);
}
```

然后在累计单只怪物伤害时使用解码后的值，并用 `long` 做中间计算避免 `int` 溢出：

```java
for (Integer eachd : onedList) {
    int decodedDamage = decodeClientDamage(eachd);
    totDamageToOneMonster = (int) Math.min(Integer.MAX_VALUE, (long) totDamageToOneMonster + decodedDamage);
}
totDamage = (int) Math.min(Integer.MAX_VALUE, (long) totDamage + totDamageToOneMonster);
```

飞侠 `PICKPOCKET` 等读取单段伤害的地方也要统一用 `decodeClientDamage(eachd)`。


## 6. 生效条件检查清单

最终要同时满足：

- `clien/config.ini` 三个 cap 都是 `2147483647`
- `clien/ijl15.dll` 中不再有 `19999999` 的 int/double/ascii 命中
- 当前武器的客户端 `.img` 有 `info/limitBreak=2147483647`
- 当前武器的服务端 `.img.xml` 有 `info/limitBreak=2147483647`
- 服务端 `AbstractDealDamageHandler` 使用 `decodeClientDamage`
- 实际运行的服务端 jar/classes 是改完后的版本
- 客户端和服务端都重启，且客户端运行的是本仓库这份已修改的 `clien/ijl15.dll`
