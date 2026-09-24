# BeiDouSetItemCompat 名牌战力补丁（int32 → int64 + 等级前缀）

`patch_nameplate_power.py` 对 `clien/BeiDouSetItemCompat.dll` 做二进制补丁，
前提是输入为原版 int32 逻辑的 dll（脚本读取 `.bak.int32` 还原后重打，
因此在已补丁的 dll 上重复运行结果不变）。脚本同时锁定原始和最终
SHA-256；没有基线备份时，正确的已补丁产物会直接成功退出，其他未知
DLL 会被拒绝，避免在错误版本上叠加补丁。

用法（Windows）：

```bat
python tool\client-debug\BeiDouSetItemCompat\patch_nameplate_power.py clien\BeiDouSetItemCompat.dll
```

补丁内容：

- `0x17C` 包长度校验 `11 → 15`，`power` 按 8 字节读取，符号位按高 32 位判定。
- 状态表条目复用 16 字节 stride：`[0]=charId, [4]=power低32, [8]=enabled, [9..11]=power高24位, [12]=canvas句柄`
 （`+12` 的 canvas 语义和 `+8` 的 enabled 语义与原版完全一致；`+9..+11` 经全引用扫描确认原版从未使用；
  power 高 24 位覆盖到约 `1.8×10^19`，游戏内不可能溢出）。
- 收到状态未变化的 `0x17C` 包时直接返回；禁用且没有 Canvas 的条目也不触发刷新。
  原版刷新会先释放并重建所有启用名牌，此去重避免重复包持续制造 Canvas 生命周期压力。
- 自定义成功日志完成后直接进入函数尾声，不再落入原版日志器；该日志器要求 `EBX`
  指向栈字符串，而自定义路径中的 `EBX` 是角色 ID，误入会在 `strlen` 中解引用小整数地址。
- 绘制：使用补丁内的无依赖 64 位十进制转换，避开旧版 `USER32!wsprintfA`
  不支持 `%I64d` 的限制；千分位循环保持不变，最终文本改为
  `%s || 战斗力：%s`，等级按阈值选取：
  乾元玄阶 / 坤极天域 / 天元墟境 / 玄枢天宿 / 星墟玄阙 /
  太白星河 / 苍元帝宿 / 昊天玄宿 / 九曜神王 / 无敌大帝。
- 等级名、阈值和最终格式串都以 `call` 压栈的下一条指令地址为相对基址；
  生成器验证三类地址的位移，禁止把格式串指向前导 `NUL` 后仍产出 DLL。
- 最终显示文本写入原生 `label[64]`（`[ebp-0xf8]`）；数字临时区和诊断日志区
  不作为 `MakeNameplate` 参数，避免 `D <角色> <低位> <高位>` 覆盖正文。
- 新增代码/数据全部放在 `.data` / `.rdata` 的 slack 区，`.data` 补上可执行标志；
  新增地址一律 call/pop 相对寻址，不新增重定位表项。
- 服务端配套改动：`PacketCreator.nameplatePowerUpdate` 改发 `long`（15 字节），
  `calculateNameplatePower` 去掉 `Integer.MAX_VALUE` 截断。

回滚：把 `clien/BeiDouSetItemCompat.dll.bak.int32` 改回原名即可
（同时服务端也要同步回退到 int 版，否则包长对不上）。
