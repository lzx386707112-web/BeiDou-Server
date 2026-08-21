#!/usr/bin/env python3
"""地图 / Boss 迁移兼容性规则引擎。

判定一个 .img 里的节点对「旧端 GMS 客户端」是否兼容。状态分为四种：

- ``ok``          旧端兼容，无需处理。
- ``modern``      使用了新版特性，但通常不会让旧端崩溃；建议降级或保留时留意。
- ``incompatible`` 会让旧端崩溃 / 黑屏 / 不可见 / 卡启动，必须剔除或降级。
- ``review``      性质模糊，需要人工判断（例如空脚本字段、未知 fieldType）。

每条规则只针对「节点名 + 父节点 + 取值」做静态判断，不依赖对照文件。
规则数据驱动、集中在文件顶部常量，方便后续补充。

判定证据来源（本项目 docs/migrations）：
- shenshuo-boss-pack.md：现代 Boss 地图移除 particle/mobTeleport/noSkill、高版本
  field/复活/远程效果、动态 Spine 对象元数据、扩展背景尺寸字段、扩展 portal 范围字段。
- root-abyss-migration.md：移除 info/standAlone、partyStandAlone、noMapCmd、空
  fieldScript/onFirstUserEnter/onUserEnter、obj 的 hide/reactor/flow、portal 的
  delay/hideTooltip/onlyOnce、foothold/piece。
- black-mage-hard-reference/README.md：根节点 particle/userSit/clock/area、fieldType=210、
  ARC/AUT、remoteEffect、复活等。
- 095-migration.md：地图至少应有 miniMap/canvas，否则解码为 0；portal/reactor/life/miniMap
  结构保留。
- arcane-river-complete-sync-readme.md：fieldLimit 高版本值(1048576)降级；foothold/piece 移除。
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# 常量：已知「现代专属」取值与字段名
# ---------------------------------------------------------------------------

# 旧端地图允许的根节点来自已落地的 Arcane River / Karing 白名单。
LEGACY_MAP_ROOTS = {
    "info", "back", "life", "reactor", "foothold", "ladderRope",
    "miniMap", "portal", *(str(index) for index in range(8)),
}

# 根级目录：迁移脚本和实机记录均要求移除。
MODERN_ROOT_DIRS = {"particle", "usersit", "clock", "area", "mobteleport", "noskill"}

# info 下已证实不能直接带入旧端的字段。
INFO_INCOMPATIBLE = {
    "standAlone", "partyStandAlone", "barrierArc", "barrierAut",
    "fieldLimit2", "fieldScript", "remoteEffect", "reviveCurField",
    "ReviveCurFieldOfNoTransfer", "ReviveCurFieldOfNoTransferNotDamaged",
    "ReviveCurFieldOfNoTransferPoint", "quarterView",
}

# 已在迁移脚本中移除，但缺少足够证据证明单独出现必然崩溃的字段。
INFO_MODERN_REVIEW = {
    "AmbientBGM", "AmbientBGMv", "bgmSub", "consumeItemCoolTime",
    "largeSplit", "limitUpgradeItem", "limitUseShop", "lvLimit", "mode",
    "noChair", "noHekatonEffect", "noMapCmd", "qrLimit", "specialSound",
    "MRLeft", "MRTop", "MRRight", "MRBottom", "footStepSound",
    "mirror_Bottom", "AFKmob", "HobbangKing", "MR",
    "bonusStageNoChangeBack", "individualHuntField",
    "individualHuntFieldServerType", "noBackOverlapped", "qrLimitState",
    "qrLimitState2", "ratemob", "towerChairEnable", "zeroSideOnly",
}

# 已知会让旧端无法处理的 fieldType 取值（证据：黑魔法师 fieldType=210）
INCOMPATIBLE_FIELDTYPE = {210}

# 旧端已知合法 fieldType（不在其中且 >=100 的归为 review）
LEGACY_FIELDTYPE_OK = {0, 2, 4, 6, 7, 8, 9, 10, 11, 12}

# 只标记有明确迁移证据的取值。不能使用 >= 阈值：已验证的卡琳旧端值
# 1909496 更大，但属于刻意保留的兼容位掩码。
MODERN_FIELDLIMIT_VALUES = {1048576}

# obj / back / life / portal 的现代字段来自已落地迁移器的清洗白名单。
OBJ_INCOMPATIBLE = {"spineAni", "dynamic"}
OBJ_MODERN_REVIEW = {
    "hide", "reactor", "flow", "SN0", "SN_count", "move", "name",
    "piece", "questex", "tags", "timeScale", "cantThrough", "fadeName",
    "fadeType", "groupName", "quest", "sideType",
}
BACK_MODERN_REVIEW = {"backTags", "w", "wx", "wy", "spineAni", "flowX", "flowY"}
LIFE_MODERN_REVIEW = {"hold", "nofoothold", "forcedZPage", "forcedZMass"}

PORTAL_MODERN_REVIEW = {
    "delay", "hideTooltip", "onlyOnce", "hRange", "horizontalImpact",
    "vRange", "shownAtMinimap", "ignoreRandomMission",
}

# 任何层级出现以下名称都视为 Spine 动态元数据（旧端不支持）
SPINE_NAMES = {"spine", "spineanchors", "spineani", "skeleton", "atlas", "spineevent"}
SPINE_VALUE_HINT = re.compile(r"spine", re.IGNORECASE)

# 背景扩展尺寸字段（证据：扩展背景尺寸字段），形如 cx2/cy2/rx2 等
BACK_EXTENDED_FIELD = re.compile(r"^[a-z]+(?:2|Ex|Extended)$", re.IGNORECASE)

# Boss 客户端安全上限（证据：客户端 maxHP 保持 20 亿安全值）
BOSS_MAXHP_CLIENT_CAP = 2000000000
# Boss eva 上限（证据：旧客户端 eva 上限 200）
BOSS_EVA_CAP = 200

BOSS_INFO_INCOMPATIBLE = {
    "attack", "bodyDisease", "bodyDiseaseLevel", "chaseEffect", "default",
    "defaultHP", "defaultMP", "delAtomOnDead", "finalmaxHP", "firstAttackRange",
    "ignoreFieldOut", "ignoreMovable", "ignoreMoveImpact", "isRemoteRange",
    "linkMob", "maxHPb", "mobZone", "mobZoneType", "opacityLayer", "passive",
    "publicReward", "showNotRemoteDam", "stalking", "trans", "useReaction",
}
BOSS_INFO_MODERN_REVIEW = {
    "category", "ex", "explosiveReward", "ignoreSlow", "ignoreSlowMsg",
    "moveAbility", "mobJobCategory", "shieldEffectUOL", "shieldSoundUOL",
}

# 严重度排序（用于过滤/排序）
SEVERITY = {"ok": 0, "modern": 1, "review": 2, "incompatible": 3}


@dataclass
class Verdict:
    status: str
    reason: str
    suggestion: str = ""

    @property
    def severity(self) -> int:
        return SEVERITY.get(self.status, 0)


STATUS_LABELS = {
    "ok": "兼容",
    "modern": "现代",
    "incompatible": "不兼容",
    "review": "待审",
}


def _ok() -> Verdict:
    return Verdict("ok", "旧端兼容，无需处理。")


# ---------------------------------------------------------------------------
# 单节点规则
# ---------------------------------------------------------------------------

def evaluate(node: dict, mode: str = "map") -> Verdict:
    """对单个归一化节点做兼容性判定。

    node 字段：
      name        末级节点名
      parent_name 父节点名（根节点为空字符串）
      type        canvas/imgdir/int/string/vector/uol/float/...
      value       标量值（int/string/vector/...）
      ints        canvas 的子 int 字典（仅 type==canvas）
    """
    name = node.get("name", "")
    parent = node.get("parent_name", "")
    ntype = node.get("type", "")
    value = node.get("value")

    if ntype in {"rawdata", "video"}:
        return Verdict(
            "incompatible",
            "节点类型 %s 是现代运行时数据，旧端没有对应解码/播放实现。" % ntype,
            "不要直接复制；先投影为旧端静态 Canvas/动作或由服务端兼容逻辑替代。",
        )
    if ntype == "canvas":
        fmt = (node.get("format"), node.get("format2"))
        width, height = int(node.get("width") or 0), int(node.get("height") or 0)
        if fmt != (1, 0):
            return Verdict(
                "incompatible",
                "Canvas 格式 %s/%s 不是旧端迁移要求的 GMS ARGB4444(1/0)。" % fmt,
                "解析真实像素后重新编码为 GMS-keyed ARGB4444，并再次解码验证。",
            )
        if width > 2048 or height > 2048:
            return Verdict(
                "incompatible",
                "Canvas 尺寸 %sx%s 超过已验证的旧端单边 2048 上限。" % (width, height),
                "按动作原点同步缩放或裁切，不能只缩图片而不调整 Vector。",
            )
    if name in {"_outlink", "_inlink"}:
        return Verdict(
            "incompatible",
            "%s 是现代来源的 Canvas 链接，散 IMG/旧端目标不能依赖该外链。" % name,
            "解析引用链并把真实像素物化进目标 Canvas，同时保留 origin/delay 等本地元数据。",
        )

    # ---- 任何层级：Spine 动态元数据 ----
    if name.lower() in SPINE_NAMES:
        return Verdict(
            "incompatible",
            "动态 Spine 元数据节点「%s」，旧端无 Spine 运行时，加载即崩或不可见。" % name,
            "删除该 Spine 节点；若 obj 有静态贴图/动作回退，保留回退层。",
        )
    if ntype == "string" and isinstance(value, str) and SPINE_VALUE_HINT.search(value):
        return Verdict(
            "incompatible",
            "字符串引用了 Spine 资源：%r。" % value,
            "改为旧端已有的静态资源路径，或删除该引用。",
        )

    if mode == "map":
        return _evaluate_map(node, name, parent, ntype, value)
    if mode == "boss":
        return _evaluate_boss(node, name, parent, ntype, value)
    return _ok()


def _evaluate_map(node, name, parent, ntype, value) -> Verdict:
    path = node.get("path", "") or ""
    segs = [p for p in path.split("/") if p]
    ancestors = set(segs[:-1]) if segs else set()

    # 根级现代目录
    if parent == "" and name.lower() in MODERN_ROOT_DIRS:
        return Verdict(
            "incompatible",
            "根级现代节点「%s」，旧端不支持渲染/读取。" % name,
            "直接删除根节点「%s」（不删会卡启动或黑屏）。" % name,
        )
    if parent == "" and path and name not in LEGACY_MAP_ROOTS:
        return Verdict(
            "review",
            "根节点「%s」不在已验证的旧端地图根节点白名单。" % name,
            "先确认客户端读取路径和依赖；不能因为未知就直接删除。",
        )

    # info 子节点
    if parent == "info":
        if name in INFO_INCOMPATIBLE:
            return Verdict(
                "incompatible",
                "info/%s 属于已确认不能直接带入旧端的现代场景字段。" % name,
                "按稳定底座投影对应行为后移除 info/%s；不要机械保留。" % name,
            )
        if name in INFO_MODERN_REVIEW:
            return Verdict(
                "modern",
                "info/%s 是已落地迁移器会清理的现代扩展字段。" % name,
                "核对地图行为后决定删除或服务端替代；静态规则不自动改写。",
            )
        if name == "fieldType" and isinstance(value, int):
            if value in INCOMPATIBLE_FIELDTYPE:
                return Verdict(
                    "incompatible",
                    "info/fieldType=%s 是旧端未实现的高版本场景类型。" % value,
                    "移除 fieldType 或降级为旧端支持的 0/2/4/8；需与服务端场景逻辑一致。",
                )
            if value not in LEGACY_FIELDTYPE_OK:
                return Verdict(
                    "review",
                    "info/fieldType=%s 不在旧端已知合法集合，可能不被支持。" % value,
                    "确认旧端是否支持该 fieldType；不支持则降级。",
                )
        if name == "fieldLimit" and isinstance(value, int) and value in MODERN_FIELDLIMIT_VALUES:
            return Verdict(
                "modern",
                "info/fieldLimit=%s 是高版本区域限制值。" % value,
                "降级为相邻旧端 fieldLimit 值（如 0 或地图原本用的低值）。",
            )
        if name in {"onFirstUserEnter", "onUserEnter", "fieldScript"} and value == "":
            return Verdict(
                "modern",
                "info/%s 为空字符串脚本字段，旧端读取空脚本无意义。" % name,
                "删除空脚本字段，避免空引用。",
            )

    # obj 下的现代标记（可能嵌套在 obj/<id>/ 下）
    if "obj" in ancestors and name in OBJ_INCOMPATIBLE:
        return Verdict(
            "incompatible",
            "obj/%s 依赖现代动态对象/Spine 运行时，旧端不识别。" % name,
            "删除整个动态对象，或替换为已验证的静态 obj 回退层。",
        )
    if "obj" in ancestors and name in OBJ_MODERN_REVIEW:
        return Verdict(
            "modern",
            "obj/%s 是现代对象扩展元数据。" % name,
            "确认静态对象仍能独立显示后再移除该字段。",
        )

    # portal 下的现代标记（可能嵌套在 portal/<id>/ 下）
    if "portal" in ancestors and name in PORTAL_MODERN_REVIEW:
        return Verdict(
            "modern",
            "portal/%s 是现代传送点扩展字段。" % name,
            "删除前核对 portal 类型、脚本和目标落点；部分现代 pt 还需要投影。",
        )

    if "life" in ancestors and name in LIFE_MODERN_REVIEW:
        return Verdict(
            "modern",
            "life/%s 是现代生命体扩展字段。" % name,
            "旧端刷新点通常不需要该字段；与稳定 life 节点对照后移除。",
        )

    # back 扩展尺寸字段（可能嵌套在 back/<id>/ 下）
    if "back" in ancestors and (
        name in BACK_MODERN_REVIEW
        or (ntype in ("int", "float") and BACK_EXTENDED_FIELD.match(name))
    ):
        return Verdict(
            "modern",
            "back/%s 是扩展背景尺寸字段，旧端按固定尺寸读取。" % name,
            "删除 back/%s 或回填旧端尺寸。" % name,
        )

    # foothold/piece：编辑器专用，旧端无用
    if "foothold" in ancestors and (name == "piece" or parent == "piece"):
        return Verdict(
            "modern",
            "foothold/piece 字段仅供现代编辑器关联，旧端无作用且体积大。",
            "删除 foothold/piece 全部子节点（不影响碰撞，碰撞坐标在 foothold 主节点）。",
        )

    return _ok()


def _evaluate_boss(node, name, parent, ntype, value) -> Verdict:
    path = node.get("path", "") or ""
    if parent == "info":
        if name == "maxHP" and isinstance(value, int) and value > BOSS_MAXHP_CLIENT_CAP:
            return Verdict(
                "incompatible",
                "info/maxHP=%s 超过旧端客户端安全上限 %s（约 20 亿）。" % (value, BOSS_MAXHP_CLIENT_CAP),
                "客户端 maxHP 封顶 2e9；服务端用 long（如 300 亿）单独配置。",
            )
        if name == "eva" and isinstance(value, int) and value > BOSS_EVA_CAP:
            return Verdict(
                "modern",
                "info/eva=%s 超过旧端 eva 上限 %s。" % (value, BOSS_EVA_CAP),
                "降级 eva 到 %s（证据：白发希拉 625->200、卡翁/敦凯尔 300->200）。" % BOSS_EVA_CAP,
            )
        if name == "link" and isinstance(value, str) and SPINE_VALUE_HINT.search(value):
            return Verdict(
                "incompatible",
                "info/link 指向 Spine 资源：%r。" % value,
                "改指向旧端已有的静态 Mob IMG，或删除 link 使用本体。",
            )
        if name == "mobType" and ntype != "int":
            return Verdict(
                "incompatible",
                "info/mobType 使用 %s，旧客户端/服务端契约要求整数。" % ntype,
                "投影为稳定底座使用的整数 mobType（本项目 Boss 通常为 1）。",
            )
        if name in BOSS_INFO_INCOMPATIBLE:
            suggestion = "按稳定 Boss 动作/服务端逻辑投影后移除；不要直接丢弃其中的攻击参数。"
            if name != "attack":
                suggestion = "与稳定 Boss info 对照并在服务端补齐等价行为后移除。"
            return Verdict(
                "incompatible",
                "info/%s 是已落地 Boss 迁移器会投影或移除的现代字段。" % name,
                suggestion,
            )
        if name in BOSS_INFO_MODERN_REVIEW:
            return Verdict(
                "modern",
                "info/%s 是现代 Boss 扩展字段，旧端没有稳定契约证据。" % name,
                "检查动作、服务端 MobSkill 和阶段逻辑后决定是否移除。",
            )
    if parent == "" and path and name == "flip":
        return Verdict(
            "review",
            "根级 flip 动作容器在现代 Boss 中常见，但不属于本项目已验证的旧端动作集合。",
            "确认是否为真实动作或镜像元数据；卡琳迁移选择移除，其他 Boss 不能照搬。",
        )
    return _ok()


# ---------------------------------------------------------------------------
# 跨节点后处理
# ---------------------------------------------------------------------------

def post_analyze(nodes: list, mode: str) -> list:
    """对单节点判定结果做跨节点补充，返回带 verdict 的完整节点列表。"""
    verdicts = [_attach(node, mode) for node in nodes]
    if mode == "map":
        verdicts = _post_map(verdicts, nodes)
    elif mode == "boss":
        verdicts = _post_boss(verdicts, nodes)
    return verdicts


def _attach(node: dict, mode: str) -> dict:
    node = dict(node)
    node["verdict"] = evaluate(node, mode)
    return node


def _has_canvas_descendant(nodes: list, root_path: str) -> bool:
    for n in nodes:
        p = n.get("path", "")
        if p == root_path or not p.startswith(root_path + "/"):
            continue
        if n.get("type") == "canvas":
            return True
    return False


def _post_map(verdicts: list, nodes: list) -> list:
    by_path = {n["path"]: n for n in verdicts}
    minimap = by_path.get("miniMap")
    if minimap is not None and not _has_canvas_descendant(nodes, "miniMap"):
        minimap["verdict"] = Verdict(
            "incompatible",
            "miniMap 下没有可解码的 canvas，旧端小地图会缺失/解码为 0。",
            "从稳定底座地图（如普通祭坛 280030000）复制 miniMap/canvas，或补一张 1x1 透明占位。",
        )
    return verdicts


def _post_boss(verdicts: list, nodes: list) -> list:
    by_path = {n["path"]: n for n in verdicts}
    canvases = [n for n in nodes if n.get("type") == "canvas"]
    visible_sized = [n for n in canvases if int(n.get("width") or 0) > 4 or int(n.get("height") or 0) > 4]
    has_outlink = any(n.get("name") == "_outlink" for n in nodes)
    if not canvases and verdicts:
        verdicts[0]["verdict"] = Verdict(
            "review",
            "整个 Mob IMG 没有 Canvas；主 Boss 会不可见，但召唤壳/逻辑实体可能刻意无图。",
            "先确认实体职责和 revive/召唤链；主 Boss 必须补可见动作，逻辑实体可保留占位。",
        )
    elif not visible_sized and not has_outlink and verdicts:
        verdicts[0]["verdict"] = Verdict(
            "review",
            "Mob 只有 4x4 以下小画布且没有 _outlink，可能是占位实体，也可能丢失了真实像素。",
            "与来源和召唤链核对；不要把刻意占位误修成可见 Boss，也不要放过导出失败。",
        )

    info = by_path.get("info")
    if info is not None:
        required = {"level", "PADamage", "PDDamage", "MADamage", "MDDamage"}
        present = {
            n.get("name") for n in nodes
            if n.get("path", "").startswith("info/") and n.get("path", "").count("/") == 1
        }
        missing = sorted(required - present)
        if missing and info["verdict"].status == "ok":
            info["verdict"] = Verdict(
                "review",
                "info 缺少旧服务端常读字段：%s。" % ", ".join(missing),
                "客户端与服务端 XML 一起核对；阶段/revive 怪缺字段可能在 LifeFactory 读取时 NPE。",
            )
    return verdicts


# ---------------------------------------------------------------------------
# 节点含义说明（中文）
# ---------------------------------------------------------------------------

def node_meaning(name: str, path: str, meta: dict, mode: str = "map") -> str:
    parts = [p for p in (path or "").split("/") if p]
    parent = parts[-2] if len(parts) >= 2 else ""
    ntype = meta.get("type")
    base = _meaning_common(name, parent, ntype)
    if base:
        return base
    if mode == "map":
        return _meaning_map(name, parent, ntype)
    if mode == "boss":
        return _meaning_boss(name, parent, ntype)
    return "WZ 属性节点；含义取决于父节点与客户端读取方式。"


def _meaning_common(name, parent, ntype) -> str:
    if ntype == "canvas":
        return "实际图片帧；客户端保存像素，服务端 XML 仅保存尺寸、原点与子属性。"
    if ntype == "uol":
        return "引用节点；不存图片，指向另一个 canvas 或属性。"
    if ntype == "vector":
        return "二维坐标（x,y），常见原点/范围/偏移。"
    if ntype == "float":
        return "浮点属性；如怪物刷新率 mobRate。"
    if ntype == "string":
        return "字符串属性；常见动作名、脚本名、BGM、链接路径。"
    if ntype == "int":
        return "整数属性；具体含义取决于节点名与父节点。"
    if ntype == "imgdir":
        return "目录/容器节点，用于组织子节点，本身不存像素。"
    return ""


_MAP_INFO = {
    "version": "地图数据版本号。",
    "cloud": "云朵开关。",
    "town": "是否为城镇。",
    "swim": "是否可游泳。",
    "returnMap": "死亡/返回时去的地图 ID。",
    "forcedReturn": "强制返回地图 ID（无返回点时用）。",
    "mobRate": "怪物刷新倍率（浮点）。",
    "bgm": "背景音乐路径。",
    "mapMark": "小地图标记图标。",
    "fly": "是否可飞行。",
    "hideMinimap": "是否隐藏小地图。",
    "fieldLimit": "区域限制位掩码（如不能跳/不能瞬移等）。",
    "VRTop": "镜头可见区域上边界。",
    "VRLeft": "镜头可见区域左边界。",
    "VRBottom": "镜头可见区域下边界。",
    "VRRight": "镜头可见区域右边界。",
    "onFirstUserEnter": "首次进入地图时触发的脚本。",
    "onUserEnter": "每次进入地图时触发的脚本。",
    "fieldType": "场景类型（城镇/战斗/镜头等）。",
    "standAlone": "现代独立场景标记。",
    "partyStandAlone": "现代组队独立场景标记。",
    "noMapCmd": "是否禁用地图命令。",
    "userSit": "现代坐下点（旧端不支持）。",
    "timeLimit": "副本时间限制。",
}


def _meaning_map(name, parent, ntype) -> str:
    if parent == "info" and name in _MAP_INFO:
        return "地图基础信息：" + _MAP_INFO[name]
    conv = {
        "back": "背景层容器；按顺序叠放背景图，决定地图视觉。",
        "life": "地图生命体（怪物/NPC）刷新点容器。",
        "reactor": "地图机关（反应堆）容器。",
        "obj": "地图物件（装饰/可交互静态物）容器。",
        "tile": "地图地砖层容器。",
        "portal": "传送点容器；每个子节点是一个门。",
        "miniMap": "小地图容器；应含可解码 canvas。",
        "foothold": "foothold 碰撞层容器；定义可站立地面。",
        "clock": "现代世界时钟（旧端不支持）。",
        "area": "现代区域标记（旧端不支持）。",
        "particle": "现代粒子系统（旧端不支持）。",
    }
    if name in conv:
        return conv[name]
    if parent == "portal":
        pm = {
            "pt": "传送点类型（0 出生点/1 普通门/2 脚本门/.../8 隐藏门等）。",
            "x": "传送点 x 坐标。",
            "y": "传送点 y 坐标。",
            "tm": "目标地图 ID。",
            "tn": "目标传送点名。",
            "script": "传送点脚本名。",
            "delay": "现代传送延迟字段。",
            "hideTooltip": "现代隐藏提示字段。",
            "onlyOnce": "现代仅触发一次字段。",
        }
        return pm.get(name, "传送点子属性 %s。" % name)
    if parent == "life":
        lm = {
            "type": "生命体类型（m=怪物/n=NPC）。",
            "id": "怪物或 NPC 的 ID。",
            "x": "刷新 x 坐标。",
            "y": "刷新 y 坐标。",
            "fh": "所在 foothold 编号。",
            "cy": "mob 向上浮动上限。",
            "rx0": "左右活动范围左。",
            "rx1": "左右活动范围右。",
            "mobTime": "怪物刷新周期。",
        }
        return lm.get(name, "生命体子属性 %s。" % name)
    if parent == "back":
        bm = {
            "bS": "背景图资源名。",
            "front": "是否前景（1 前景 / 0 背景）。",
            "ani": "是否动画背景。",
            "no": "背景图编号。",
            "f": "是否翻转。",
            "x": "背景 x 坐标。",
            "y": "背景 y 坐标。",
            "rx": "背景滚动 x。",
            "ry": "背景滚动 y。",
            "type": "背景类型（0 平铺/1 拉伸/2 居中）。",
            "cx": "背景宽度。",
            "cy": "背景高度。",
            "a": "背景透明度 0-255。",
        }
        return bm.get(name, "背景子属性 %s。" % name)
    if parent == "foothold":
        return "foothold 碰撞线段；x1,y1,x2,y2 定义可站立地面，next 链接相邻段。"
    if name == "piece":
        return "foothold 编辑器专用碎片字段，旧端无作用。"
    return "地图节点；含义取决于父节点与客户端读取方式。"


_BOSS_INFO = {
    "maxHP": "怪物最大血量（客户端安全上限约 20 亿）。",
    "maxMP": "怪物最大蓝量。",
    "maxMobHP": "怪物血量显示值。",
    "level": "怪物等级。",
    "exp": "击杀经验。",
    "eva": "回避率（旧端上限 200）。",
    "acc": "命中率。",
    "speed": "移动速度。",
    "fs": "攻击速度。",
    "pad": "物理攻击力。",
    "pdr": "物理防御力。",
    "mad": "魔法攻击力。",
    "mdr": "魔法防御力。",
    "hp": "当前血量。",
    "link": "指向另一个 Mob IMG 复用数据（静态或 Spine）。",
    "mobType": "怪物类型。",
    "elemAttr": "属性抗性（火/冰/雷/毒/圣/暗）。",
    "undead": "是否为不死系。",
    "flySpeed": "飞行速度。",
    "bodyAttack": "是否本体接触伤害。",
    "noFlip": "是否不翻转。",
    "boss": "是否为 Boss（1/0）。",
    "hpTagColor": "血条颜色。",
    "hpTagBgColor": "血条背景色。",
    "firstAttack": "是否开局直接攻击。",
    "reaction": "反应类型。",
}


def _meaning_boss(name, parent, ntype) -> str:
    if parent == "info" and name in _BOSS_INFO:
        return "怪物基础属性：" + _BOSS_INFO[name]
    conv = {
        "skill": "怪物技能节点（按技能编号分组，含攻击动作与 MobSkill）。",
        "attack": "攻击动作节点（含攻击帧与判定）。",
        "effect": "怪物特效容器。",
        "frames": "动画帧容器；按 0,1,2... 存放 canvas 动作帧。",
        "info": "怪物基础信息节点。",
        "speak": "怪物对话气泡配置。",
        "body": "怪物本体贴图容器。",
        "ui": "血条/Boss UI 配置。",
        "rd0": "转向右时的帧容器。",
        "rd1": "转向左时的帧容器。",
    }
    if name in conv:
        return conv[name]
    if name.isdigit() and parent in {"frames", "rd0", "rd1", "attack", "effect", "body"}:
        return "动画帧序号；批量预览/替换时通常按帧号映射到这些编号。"
    if name.startswith("skill"):
        return "怪物技能分组；里面按编号存放 MobSkill 配置。"
    return "怪物节点；含义取决于父节点与客户端读取方式。"


# ---------------------------------------------------------------------------
# 统计与摘要
# ---------------------------------------------------------------------------

def summarize(verdicts: list) -> dict:
    counts = Counter(v["verdict"].status for v in verdicts)
    return {
        "total": len(verdicts),
        "ok": counts.get("ok", 0),
        "modern": counts.get("modern", 0),
        "incompatible": counts.get("incompatible", 0),
        "review": counts.get("review", 0),
    }


def collect_actions(verdicts: list) -> list:
    """返回应该被剔除/降级的节点清单（用于一键清洗预览/执行）。"""
    actions = []
    for v in verdicts:
        status = v["verdict"].status
        if status in ("incompatible", "modern", "review"):
            actions.append({
                "path": v["path"],
                "name": v["name"],
                "type": v["type"],
                "status": status,
                "reason": v["verdict"].reason,
                "suggestion": v["verdict"].suggestion,
            })
    return actions


def action_for(verdict: Verdict, node: dict) -> dict | None:
    """把判定结果翻译成可执行的清洗动作。

    返回：
      {"op": "delete"}            删除该节点（含子树）
      {"op": "set_int", "value"}  把 int 节点改为给定值（降级）
      None                        需人工处理（strip 时跳过并提示）
    """
    status = verdict.status
    if status == "ok":
        return None
    name = node.get("name", "")
    parent = node.get("parent_name", "")

    # miniMap 缺 canvas / 整个 Mob 无 canvas：需要手动补资源，不能简单删
    if verdict.reason.startswith("miniMap") or verdict.reason.startswith("整个 Mob"):
        return None
    # 待审字段默认跳过，交给人工
    if status == "review":
        return None

    # 只有证据固定、无需上下文选择的数值转换才自动执行。
    if parent == "info" and name == "eva" and status == "modern":
        return {"op": "set_int", "value": BOSS_EVA_CAP}
    if parent == "info" and name == "maxHP" and status == "incompatible":
        return {"op": "set_int", "value": BOSS_MAXHP_CLIENT_CAP}

    path = node.get("path", "") or ""
    ancestors = set(path.split("/")[:-1])
    explicit_delete = (
        (parent == "" and name.lower() in MODERN_ROOT_DIRS)
        or (parent == "info" and name in {"standAlone", "partyStandAlone"})
        or (parent == "info" and name in {"onFirstUserEnter", "onUserEnter"} and node.get("value") == "")
        or ("foothold" in ancestors and (name == "piece" or parent == "piece"))
    )
    if explicit_delete:
        return {"op": "delete"}

    # fieldLimit、动态 obj、现代攻击元数据等都需要底座/服务端上下文，绝不自动删。
    return None


def format_markdown(verdicts: list, meta: dict) -> str:
    """生成兼容性分析报告（Markdown）。"""
    lines = []
    title = "地图" if meta.get("mode") == "map" else "Boss"
    lines.append("# %s 迁移兼容性分析报告" % title)
    lines.append("")
    lines.append("- 文件：`%s`" % meta.get("imgPath", ""))
    if meta.get("xmlPath"):
        lines.append("- 服务端 XML：`%s`" % meta.get("xmlPath"))
    lines.append("- 模式：`%s`" % meta.get("mode"))
    s = summarize(verdicts)
    lines.append("- 节点总数：%d　兼容 %d　现代 %d　不兼容 %d　待审 %d" % (
        s["total"], s["ok"], s["modern"], s["incompatible"], s["review"]))
    lines.append("")
    for status, label in (
        ("incompatible", "不兼容（必须处理）"),
        ("modern", "现代（建议降级/移除）"),
        ("review", "待审（需人工判断）"),
    ):
        items = [v for v in verdicts if v["verdict"].status == status]
        if not items:
            continue
        lines.append("## %s（%d）" % (label, len(items)))
        lines.append("")
        lines.append("| 路径 | 类型 | 原因 | 建议 |")
        lines.append("|---|---|---|---|")
        for v in items:
            p = v["path"] or v["name"]
            t = v["type"]
            r = v["verdict"].reason.replace("|", "\\|")
            sug = (v["verdict"].suggestion or "").replace("|", "\\|")
            lines.append("| `%s` | %s | %s | %s |" % (p, t, r, sug))
        lines.append("")
    return "\n".join(lines)
