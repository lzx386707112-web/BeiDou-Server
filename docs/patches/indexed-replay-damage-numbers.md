# 服务端重放攻击的逐段叠高飘字模板

## 适用范围

该模板用于“技能只由玩家首次按键触发，后续攻击由服务端定时重放”的本地多段攻击。当前已接入宇宙之花 `11121012`、银河星爆 `11121005`、全蚀之力 `11121006`、灵魂蚀日 `11121008`。真实伤害仍由服务端按每次攻击、每只怪合计后结算一次；该模板只补本机旧客户端不能从自身重放包生成的逐段飘字。

它不适用于普通客户端主动攻击，也不用于修正目标选择、攻击时间、伤害公式或暴击计算。

## 已验证的客户端原因

- 自身收到 `CLOSE_RANGE_ATTACK (0xBA)` 后，在 `0x0097250B` 查询远程角色；本地角色查不到，随后从 `0x00972512..0x00972514` 返回。
- 远程角色路径会从 `0x00980617..0x00980631` 逐个读取 hit，并在 `0x009810F5..0x009811BB` 循环显示。
- 普通 `DAMAGE_MONSTER (0xF6)` 在 `0x0066C6C2` 只读取一个 damage，原逻辑在 `0x0066C6E4` 固定把 hit index `0` 传给 `0x006691D3`，所以连续发送普通包只会重叠在同一高度。
- 怪物原生多段路径在 `0x00668E01..0x00668E0D` 把逐段 hit index 传给同一个 `0x006691D3`。因此第二参数才是客户端原生纵向布局依据。
- 正常玩家攻击的数字构造函数 `0x0066B05E` 在默认分支以 `baseTime + 120ms * hitIndex` 安排每一段；轻舞飞扬 `1121008` 不在该函数的60ms特例名单中，因此使用120ms。

不能把本地 `CUserLocal` 强行传给只验证过远程对象的攻击函数 `0x009803AB`。该函数还会改变动作和攻击状态，不是纯飘字函数。

## 通用协议

`DAMAGE_MONSTER` 的方向字节在旧逻辑中会被读取后丢弃。该模板保留普通值的原行为，并只划出以下标记：

| 字节值 | 客户端行为 |
| --- | --- |
| `0x80..0x8E` | 转换成原生 hit index `0..14` |
| 其他值 | 严格使用原生默认 hit index `0` |

服务端使用 `PacketCreator.indexedDamageMonsterNumber(oid, damage, hitIndex)` 构造单段显示包。`AbstractDealDamageHandler.showIndexedDamageNumbers(...)` 同步发送第0段，后续最多14段默认按轻舞飞扬的原生间隔 `120ms * hitIndex` 发送；同一次攻击的所有目标共享相同 hitIndex 时点。只有源时间轴已验证且 replay 重叠会造成并发飘字时才能在技能调用点覆盖间隔，银河星爆 `11121005` 依据 TMS 60ms multi-attack 节奏使用60ms。helper 会复制原始 damage 列表并在延迟发送时验证角色仍处于原地图。负值中的客户端暴击位必须原样保留，不能在显示包中先解码。

空目标施放不代表发生了一次伤害。共用近战连续攻击模板会继续保留时间轴并在每个周期重新扫描范围；当周期内仍无存活目标时，不创建攻击包、飘字、仇恨或掉血。只有后续周期首次检测到目标后，才按当前角色状态创建逐段随机兜底模板；该模板不在空目标施放阶段提前生成，也不跨后续周期缓存，从而避免将一个最大值（例如 `500000`）复制为整套固定伤害。已有非空客户端伤害模板时仍优先使用客户端模板。

客户端由 `IndexedDamageNumberCompat.dll` 覆盖 `0x0066C6CB..0x0066C6E8`。安装前必须匹配完整 30 字节；匹配失败时不写入任何 hook。模块只调用原生解包函数和 `0x006691D3`，不读取技能 ID，不访问玩家对象，也不进入远程攻击路径。

模块由 `WzFileLogger.dll` 的 watchdog 线程在首次休眠前加载，不占用新的 EXE 代码洞，也不修改当前只有成品、缺少同版源码的 `DawnWarriorSkillCompat.dll`。生成运行文件时必须同时构建新的 indexed compat 和更新后的 `WzFileLogger.dll`。

## 新技能接入模板

1. 确认该技能的后续攻击确实由服务端重放，且本地 `0xBA` 因自身 CID 被远程角色查询拒绝；不能仅凭“看不到飘字”套用模板。
2. 重放包仍按完整 `List<Integer>` 发送给其他玩家，保持动作、目标数和 hit 数。
3. 对施法者本机调用 `showIndexedDamageNumbers(chr, expectedMap, damageByMonster)`，不要把各段先合计成一个普通 `damageMonster()` 包，也不要在外层循环对每只怪分别启动时间序列。
4. 独立计算解码后的 `total`，并且每只怪只调用一次 `aggroMonsterDamage()` 和一次 `map.damageMonster()`。逐段显示包绝不能再次结算伤害。
5. 首次客户端原始攻击如果也被本地路径吞掉，使用同一 helper 发送捕获到的 `attack.allDamage`；否则不要重复补发。
6. 只有需要旧合计飘字的既有技能使用 `TOTAL`；不需要本地补字的技能使用 `NONE`；确认需要原生逐段高度后才使用 `INDEXED`。

## 静态验证

```bash
rtk python3 tool/client-debug/indexed-damage-number-compat/test_indexed_damage_number_contract.py
rtk python3 tool/client-debug/test_log_cleanup_contract.py
rtk mvn -f gms-server/pom.xml -Dtest=IndexedDamageMonsterPacketTest test
rtk git diff --check
```

客户端检查必须确认：目标 EXE 的 `0x0066C6CB` 对应文件位置仍是记录的 30 字节；普通 `damageMonster()` 的 marker 仍为 `0`；索引边界只接受 `0` 和 `14` 之间的值；现有 `DawnWarriorSkillCompat.dll` 未被覆盖。

## Windows / Winlator 实机验证

- 启动和登录正常，日志出现 indexed compat 的 `LOAD` 与 `OK`。
- 宇宙之花首次攻击和后续每个 tick 都应从第0段开始，之后每120ms增加一段并按 hit index 纵向叠高；不能在一个视频帧里出现完整15段。
- 真实怪物 HP 只下降一次合计值，没有因显示包重复扣血。
- 暴击样式、目标切换、怪物死亡、地图切换、技能结束和连续施放均正常。
- 其他玩家仍看到完整重放攻击；普通技能和普通 `DAMAGE_MONSTER` 飘字保持原样。
