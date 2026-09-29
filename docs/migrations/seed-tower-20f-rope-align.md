# 起源之塔 1~20 层绳索/梯子对齐 TMS

## 症状

玩家实机反馈：地图里的绳子「断断续续不连续」。第 2 层（`992002000`）最明显。

## 根因

`migrate_seed_tower_20f.sanitize_map()` 把所有 `oS=connect` 对象压平成旧端
固定形状：

```python
if str(a.child_value(c, "l1")) not in {"0", "1", "2", "3", "4"}:
    a.set_string(c, "l1", "0")
a.set_string(c, "l2", str(max(0, min(4, int(a.child_value(c, "l2") or 0)))))
```

这条规则来自 `migrate_arcane_river_expansion.downgrade_connect_nodes()`。
神秘河的连接对象是**从 `ladderRope` 碰撞坐标现铺**的，没有原始样式，所以只能
挑一个样式（`0`）。它并不适用于「源地图自带 `l1`/`l2`」的情况。

后果有两层：

1. **样式被换掉、`l2` 被保留** —— 件高不匹配。`rope/0` 的件高是
   49/30/30/120/49 px，而 TMS 的 `l2` 是按它自己的样式
   （`8` / `22` / `45` / `60` / `65` / `73`）的件高挑的。两套件高不同，
   铺上去就对不齐 ⇒ 露出空洞。
2. **`l2` 被夹到 0–4** —— 第 3 层 `l2` 有 `5`，第 11 层有 `11`，全部被改写。

同时「`l1` 超过 0–4 绳子就不显示」这个说法在本客户端**不成立**：
`clien/Data/Map/Obj/connect.img` 保留了完整样式表（rope `0`–`82`、
ladder `0`–`87`），且**未改动的 GMS 城镇图**本来就在用高 `l1`——
rope 共 12 971 个对象、ladder 共 7 503 个对象，最高到 `43` / `67`。
实测 `196000000`（`rope/8`，`l2` 到 `5`）连续缺口 = **0 px**。
真正会让绳子消失的只有一个原因：`connect/{l0}/{l1}/{l2}` 在
`connect.img` 里查不到。

## 修复

脚本：`tool/scripts/migration/repair_seed_tower_20f_ropes.py`
报告：`docs/migrations/seed-tower-20f-rope-align.json`

规则：**只要 `connect/{l0}/{l1}/{l2}` 在客户端 `connect.img` 里能解析，
就保留 TMS 的 `l1`/`l2`**；只有样式或件号确实缺失时才退回旧的压平映射
（`l1="0"`，件号按样式 `0` 的真实件数收敛）。

一个关键细节：**客户端与 TMS 的 `obj` 子节点编号是错位的**，必须按物理位置
`(layer, x, y, z, l0)` 配对，不能按子节点名配对；按名字配会静默地把两条
不相干的绳子放在一起比较。（两张表的位置集合完全一致，且唯一。）

## 结果

连续缺口 = 每条链（按 `layer/l0/x` 分组）在竖直方向上没有任何件覆盖的像素。
按件的 `height` 与 `origin.y` 还原成区间后排序求并集即得。

| 地图 | 改动数 | 缺口 前 → 后 | 文件字节变化 |
|---|---|---|---|
| 992002000 | 47 | **639 → 0** | +0 |
| 992003000 | 42 | **1435 → 0** | +39 |
| 992011000 | 103 | 0 → 0 | +74 |
| 992016000 | 45 | **858 → 450** | +0 |
| 992017000 | 13 | **895 → 0** | +0 |
| 992019000 | 47 | **114 → 1** | +46 |
| 合计 | **297** | | |

- `992016000` 残留的 450 px **是 TMS 源数据本身就有的**（同一 x 层上有两条互相
  独立的短绳，被分组并到一起），对齐后客户端与 TMS 逐对象完全一致。
- `992011000` 原本就不缺件，但样式被压成了 `0`（TMS 是 `73`），一并按 TMS 还原。
- 其余 15 张图（含 lobby `992000000`，无 `connect`）**字节未变**。
- 每层 `connect` 对象数、位置集合、兄弟顺序、Canvas 载荷、`back`/`foothold`/
  `life`/`portal` 全部未变；服务端 `.img.xml` 与客户端 IMG 逐份语义一致。

## 客户端 IMG 写法

用 `wzpy.incremental_img.mutate_img` 逐个标量改，不做整文件序列化：

- 同长替换（`0`→`8`）：**只动 1 个字节**（XOR 后的载荷字节），`byte_delta=0`。
- 变长替换（`0`→`45`）：记录 +1 字节，由 `mutate_img` 自动重定位 string-block
  引用并回填各级 tag-9 块大小；`scan_img` 必须正好落在文件末尾。
- 每次改完都做：树级 diff（只允许目标节点变化）、兄弟顺序比对、Canvas 解码
  摘要比对，全部通过才落盘。
- 脚本可重复执行：再跑一次计划为空、文件字节不变。

## 维护入口

- 修复脚本：`tool/scripts/migration/repair_seed_tower_20f_ropes.py`
  （`--check` 干跑 / `--write` 落盘 / `--check --source-dir <基线>` 复算审计记录）
- 审计记录：`docs/migrations/seed-tower-20f-rope-align.json`
- 迁移规则（**行为刻意未改**）：`tool/scripts/migration/migrate_seed_tower_20f.py`
  的 `sanitize_map()`，已在 connect 段加警示注释。`install()` 拒绝重写已安装的
  独立 IMG，改规则会破坏既有幂等约定，因此**保留规则 + 后置修复脚本**。
  ⚠️ 若将来整表重迁，必须接着跑一次本修复脚本。
- 契约测试：`tool/scripts/migration/test_seed_tower_20f_resources.py`
  的 connect 断言已从「`l1 ∈ {0..4}`」改为「`connect/{l0}/{l1}/{l2}` 可解析」。
