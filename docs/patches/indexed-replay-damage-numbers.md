# 服务端重放攻击的本机飘字

## 两条本机飘字路径

普通服务端重放技能若要和轻舞飞扬一致，继续走玩家构造函数 `0x0066B05E`。
全屏 MCV 大招统一对齐宇宙之花，走 `INDEXED F6 -> 0x006691D3`。两条路径不能同时
用于同一个技能，否则施法者会看到双重飘字。

完整步骤以 skill 为准：

`.cursor/skills/beidou-wz-img/references/indexed-replay-damage-numbers.md`

（`.codex/skills/beidou-wz-img/references/` 下为同一文件。）

已验证的普通重放范例是剑影分身 `1121020`；它的隐藏段 `1121021/1121022` 仍在
`HookLocalCloseRangeLookup` 白名单内。

摘要（普通重放）：

1. 确认前半段是客户端自己处理的 `CLOSE_RANGE_ATTACK (0xBA)`，数字来自 `0x0066B05E`（默认 `120ms * hitIndex`）。
2. 后半段服务端同样发 `0xBA` 给施法者和其他玩家；本机 `LocalDamageNumberMode.NONE`，不发 `DAMAGE_MONSTER` / `INDEXED` / `TOTAL`。
3. 每段按施放技能框 `isWithinAttackBox` 重选目标（最多技能 `mobCount`）。客户端第一包若是小范围动作（如 `brandish1`），`applyOriginalFirst=false`。
4. 在 `IndexedDamageNumberCompat.dll` 的 `HookLocalCloseRangeLookup` 里把**隐藏重放技能 ID**加入白名单。查找失败且包为 `0x5B`+skilllevel+skill 时，把 `esi` 设为 `[0x00BEBF98]`（`CUserLocal`）。
5. 保留已有的本机 `SetMoveAction` / `[+0x2AE0]` 跳过；不要从 hook 调用 `0x009803AB`。
6. 用仓库 `build.sh` 编两次 DLL，跑 `test_indexed_damage_number_contract.py`。

## 全屏 MCV 大招（宇宙之花模板）

全屏 MCV 大招保留现有 TMS 时间数组和 WZ `attackCount`，播放期内连续攻击。
本机每个阶段使用与宇宙之花相同的
`PacketCreator.indexedDamageMonsterNumber`，索引 `0..14` 按 `120ms * hitIndex`
展开。银河星爆继续保留已经验证的 60ms 特例。

1. 保留现有阶段数组和阶段数，不修改通用调度循环。
2. 每个阶段重新选择当前存活目标，继续发送原攻击类型的重放包给本人和同图玩家。
3. 近战、魔法和远程 MCV 都只对施法者补 `INDEXED F6`，不再补 `TOTAL`。
4. 每个怪物每个阶段只执行一次 `aggroMonsterDamage + damageMonster`，F6 只负责显示。
5. 打开段使用可见节点的 `attackCount`，隐藏阶段使用对应隐藏节点的 `attackCount`。
6. MCV 隐藏 ID 不进入本机 `0xBA` 白名单；该白名单只保留剑影分身，避免双重飘字。
7. 源数据只有一次命中的 MCV 只补这一击的索引飘字，不凭空增加攻击次数。

禁止：MCV 使用 `TOTAL`、同时启用 F6 与本机 `0xBA`、无技能过滤地注入
`CUserLocal`、去掉两个动作跳过、压成单行合计伤害、把源时间轴改成固定全图脉冲。

## 宇宙之花基准

宇宙之花 `11121012`、银河星爆 `11121005`（60ms）、全蚀之力 `11121006`、
灵魂蚀日 `11121008` 与所有玩家 MCV 大招使用 F6 `INDEXED -> 0x006691D3`。

- 自身 `0xBA` 在 `0x0097250B` 查远程角色失败。
- 普通 `DAMAGE_MONSTER` 固定 hit index `0`，连续发送会重叠。
- `PacketCreator.indexedDamageMonsterNumber` 使用方向字节 `0x80..0x8E`。
- 空客户端伤害模板的持续技能必须跳过该 tick，禁止 `500000` 估算。

## 静态验证

```bash
rtk python3 tool/client-debug/indexed-damage-number-compat/test_indexed_damage_number_contract.py
rtk git diff --check
```

Java 21 可用时再跑 `IndexedDamageMonsterPacketTest` / `SwordIllusionIndexedReplayContractTest`。不要默认打 JAR。
