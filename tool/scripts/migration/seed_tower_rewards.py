#!/usr/bin/env python3
"""起源之塔奖励：抽奖卷道具 + 中文名称/说明 + 脚本内的奖池数据块。

只做「原始记录插入」与「标记块文本替换」，不整树重写任何既有 IMG/XML：

  clien/Data/Item/Etc/0400.img                插入 4009930-4009934（GMS ARGB4444 32x32 图标）
  gms-server/wz/Item.wz/Etc/0400.img.xml      同步
  clien/Data/String/Etc.img                   在 Etc 容器插入 5 条 name/desc
  gms-server/wz/String.wz/Etc.img.xml         同步
  gms-server/wz-zh-CN/String.wz/Etc.img.xml   同步
  BeiDouSpecial/起源之塔/抽奖.js              重写「起源奖池」「掉落兜底」标记块
  BeiDouSpecial/起源之塔/奖池预览.js          重写「起源奖池」标记块
  BeiDouSpecial/起源之塔/积分商店.js          重写「法弗纳」「掉落兜底」标记块

「掉落兜底」标记块是脚本里唯一的发放实现：背包放得下就进背包，放不下的部分掉在
玩家脚下。抽奖与商店共用同一份代码，避免两边口径漂移。

奖池数据源 = gms-server/src/main/resources/equipment-catalog/catalog.json，
也就是后台管理「装备预览」页的数据源（EquipmentCatalogService）。
分类映射与 EquipmentCatalogService.EQUIP_KIND_NAMES 一致：101 脸饰 / 103 耳环 /
112 项环 / 113 腰带。

用法：
  python3 tool/scripts/migration/seed_tower_rewards.py --check    # 只报告要改什么
  python3 tool/scripts/migration/seed_tower_rewards.py --install  # 落地
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("seed_arc", HERE / "migrate_arcane_river_expansion.py")
a = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = a
spec.loader.exec_module(a)

ROOT = a.ROOT
MANIFEST = ROOT / "docs/migrations/seed-tower-rewards-manifest.json"

# 抽奖卷图标：统一用这张图（用户提供的 5157420.png）
ICON_SOURCE = Path("/Users/lizixian/Downloads/5157420.png")
CATALOG = ROOT / "gms-server/src/main/resources/equipment-catalog/catalog.json"
SCRIPT_DIR = ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/起源之塔"

ITEM_IMG = "clien/Data/Item/Etc/0400.img"
ITEM_XML = "gms-server/wz/Item.wz/Etc/0400.img.xml"
STRING_IMG = "clien/Data/String/Etc.img"
STRING_XMLS = (
    "gms-server/wz/String.wz/Etc.img.xml",
    "gms-server/wz-zh-CN/String.wz/Etc.img.xml",
)
STRING_PARENT = ("Etc",)

DESC = "起源之塔专属抽奖卷"

# (道具ID, 名称, 抽取次数)
TICKETS = (
    (4009930, "起源抽奖卷1抽", 1),
    (4009931, "起源抽奖卷5连抽", 5),
    (4009932, "起源抽奖卷10连抽", 10),
    (4009933, "起源抽奖卷20连抽", 20),
    (4009934, "起源抽奖卷50连抽", 50),
)

# 装备 ID 前 3 位 -> 分类名（与 EquipmentCatalogService 的中文映射一致）
POOL_KINDS = ((101, "脸饰"), (103, "耳环"), (112, "项环"), (113, "腰带"))
FAFNIR_PREFIX = "法弗纳"
FAFNIR_EXPECTED = 16

# 脚本标记块：文件 -> (起始标记, 结束标记)，仅作文档说明；实际写入见 scripts()
POOL_MARKERS = ("// BEGIN 起源奖池", "// END 起源奖池")
FAFNIR_MARKERS = ("// BEGIN 法弗纳", "// END 法弗纳")
DROP_MARKERS = ("// BEGIN 掉落兜底", "// END 掉落兜底")
EQUIP_MARKERS = ("// BEGIN 装备属性", "// END 装备属性")
SCRIPT_BLOCKS = {
    "抽奖.js": (POOL_MARKERS, DROP_MARKERS),
    "奖池预览.js": (POOL_MARKERS, EQUIP_MARKERS),
    "积分商店.js": (FAFNIR_MARKERS, DROP_MARKERS, EQUIP_MARKERS),
}

ICON_SIZE = 32

# 抽奖与商店共用的发放实现（标记块见 DROP_MARKERS）。抽取单位是「一件」，所以只暴露 掉落_发一个()；
# 需要连发 N 件（商店）时由调用方自己循环统计。
DROP_BODY = """
// 发放口径：背包放得下的进背包，放不下的部分直接掉在玩家脚下，由玩家自己拾取。
// 掉落之后的命运（15 秒的归属保护、之后任何人都能捡、到期自然消失）全部走
// 服务端 MapItem 的既有逻辑，脚本不干预、也不额外统计。
//
// 两个必须守住的服务端契约：
//   1. 掉落件的构造口径要和 cm.gainItem() 一致，否则「地上的」和「包里的」品质不同。
//      gainItem 对装备走 getEquipById()，并给升级次数为 0 的饰品补 3 次；
//      是否 randomizeStats 取决于调用方传进来的 随机潜能（必须与进背包那条路相同）。
//   2. fieldLimit 带 DROP_LIMIT 的地图会静默吞掉掉落（内部降级成
//      disappearingItemDrop，连返回值都没有），所以落地前先自查一次。
var 掉落_装备栏编号 = 1;
var 掉落_道具类 = Java.type("org.gms.client.inventory.Item");
var 掉落_常量类 = Java.type("org.gms.constants.inventory.ItemConstants");
var 掉落_限制类 = Java.type("org.gms.server.maps.FieldLimit");

function 掉落_信息() {
    return Java.type("org.gms.server.ItemInformationProvider").getInstance();
}

// 造一件用于掉落的道具：装备恒为 1 件，其它按堆叠件。
function 掉落_造件(道具ID, 数量, 随机潜能) {
    if (Math.floor(道具ID / 1000000) === 掉落_装备栏编号) {
        var 件 = 掉落_信息().getEquipById(道具ID);
        if (件 === null || 件 === undefined) {
            return null;
        }
        try {
            if (掉落_常量类.isAccessory(道具ID) && 件.getUpgradeSlots() <= 0) {
                件.setUpgradeSlots(3);
            }
        } catch (e) { }
        if (随机潜能) {
            try {
                件 = 掉落_信息().randomizeStats(件);
            } catch (e) { }
        }
        return 件;
    }
    return new 掉落_道具类(道具ID, 0, 数量);
}

// 把 数量 个 道具ID 掉在玩家脚下；返回 true 表示确实掉出去了。
// ffa=false = 常规掉落：15 秒内归自己（同队队员可立即拾取），之后任何人都能捡。
function 掉落_地面(chr, 道具ID, 数量, 随机潜能) {
    try {
        var 地图 = chr.getMap();
        if (掉落_限制类.DROP_LIMIT.check(地图.getFieldLimit())) {
            return false;
        }
        var 件 = 掉落_造件(道具ID, 数量, 随机潜能);
        if (件 === null || 件 === undefined) {
            return false;
        }
        地图.spawnItemDrop(chr, chr, 件, chr.getPosition(), false, false);
        return true;
    } catch (e) {
        return false;
    }
}

// 发一个：放得下就进背包，放不下就掉地上。返回 '包' / '地' / ''（发不出去）。
// cm.canHold() 是只读预检（Inventory.checkSpots），所以可以逐件先问一次，
// 不会触发 gainItem 内部那句「您的背包已满…」（50 连抽会刷 50 条）。
function 掉落_发一个(chr, 道具ID, 随机潜能) {
    if (cm.canHold(道具ID, 1)) {
        var 结果 = cm.gainItem(道具ID, 1, 随机潜能, true);
        if (结果 !== null && 结果 !== undefined) {
            return '包';
        }
    }
    return 掉落_地面(chr, 道具ID, 1, 随机潜能) ? '地' : '';
}
"""

# 奖池预览与积分商店共用的装备属性读取 + 排版（标记块见 EQUIP_MARKERS）。
# 必须共用：getEquipStats() 剥 inc 前缀这件事，只要两边写法有一点不一致，
# 就会一边显示正常、另一边整段空白而且不报错，极难排查。
EQUIP_BODY = """
// 装备属性的读取与排版。奖池预览与积分商店共用同一份实现
// （由 tool/scripts/migration/seed_tower_rewards.py 注入，契约测试核对两份逐字节相同）。
//
// ★ 键名注意：服务端 ItemInformationProvider.getEquipStats() 会把 info 里以 "inc"
// 开头的字段**去掉前缀**再放进 Map（见 ItemInformationProvider.java:575-577）：
//   incPAD -> PAD, incSTR -> STR, incPDD -> PDD, incSpeed -> Speed, incJump -> Jump ...
// 所以下面必须写去掉前缀后的名字；写 incPAD 会永远查不到值、属性整段空白且不报错。
// reqLevel/reqJob/reqSTR/reqDEX/reqINT/reqLUK/reqPOP/cash/tuc/only 是原样入表的。
var 装备_需求项 = [
    ["reqLevel", "等级要求"],
    ["reqSTR", "力量要求"],
    ["reqDEX", "敏捷要求"],
    ["reqINT", "智力要求"],
    ["reqLUK", "运气要求"],
    ["reqPOP", "人气要求"]
];
// 加成项的名字 = WZ 里的 incXXX 去掉 "inc"。这份清单是按奖池 1153 件
// （脸饰/耳环/项环/腰带）实际出现过的字段统计的，覆盖全部 20 个。
var 装备_加成项 = [
    ["PAD", "物理攻击力"],
    ["MAD", "魔法攻击力"],
    ["STR", "力量"],
    ["DEX", "敏捷"],
    ["INT", "智力"],
    ["LUK", "运气"],
    ["PDD", "物理防御力"],
    ["MDD", "魔法防御力"],
    ["ACC", "命中率"],
    ["EVA", "回避率"],
    ["MHP", "最大HP"],
    ["MMP", "最大MP"],
    ["MHPr", "最大HP%"],
    ["MMPr", "最大MP%"],
    ["Speed", "移动速度"],
    ["MSpeed", "移动速度%"],
    ["Jump", "跳跃力"],
    ["PVPDamage", "PVP伤害"],
    ["Craft", "制作技能"],
    ["CriticalMAXDamage", "暴击最大伤害"]
];

var 装备_部位名 = { "101": "脸饰", "103": "耳环", "112": "项环", "113": "腰带" };

function 装备_部位文本(道具ID) {
    var 段 = String(Math.floor(道具ID / 10000));
    return 装备_部位名[段] || ("道具 " + 段 + " 段");
}

// 读一件装备的全部 info 数值（键名已按上面的规则去过 inc 前缀）。
// 读失败时返回 {读取失败:true}，让调用方显式提示，而不是静默显示成"无附加属性"。
function 装备_取属性(道具ID) {
    var 结果 = {};
    try {
        var II = Java.type("org.gms.server.ItemInformationProvider").getInstance();
        var 映射 = II.getEquipStats(道具ID);
        if (映射 === null || 映射 === undefined) {
            return 结果;
        }
        var 迭代 = 映射.entrySet().iterator();
        while (迭代.hasNext()) {
            var 键值 = 迭代.next();
            var 值 = 键值.getValue();
            结果[String(键值.getKey())] = (值 === null || 值 === undefined) ? 0 : Number(值);
        }
    } catch (e) {
        结果.读取失败 = true;
    }
    return 结果;
}

function 装备_职业文本(掩码) {
    var 表 = [[1, "战士"], [2, "法师"], [4, "弓箭手"], [8, "飞侠"], [16, "海盗"]];
    var 名 = [];
    for (var i = 0; i < 表.length; i++) {
        if ((掩码 & 表[i][0]) !== 0) {
            名.push(表[i][1]);
        }
    }
    return 名.length > 0 ? 名.join("/") : "全职业";
}

// 需求行 [[标签, 值], ...]：职业位掩码排最前，其余按 装备_需求项 的顺序。
function 装备_需求行(属性) {
    var 行 = [];
    if (属性.reqJob && 属性.reqJob > 0) {
        行.push(["职业要求", 装备_职业文本(属性.reqJob)]);
    }
    for (var i = 0; i < 装备_需求项.length; i++) {
        var 值 = 属性[装备_需求项[i][0]];
        if (值 && 值 > 0) {
            行.push([装备_需求项[i][1], String(值)]);
        }
    }
    return 行;
}

// 加成行：已经是带好颜色标记的成品字符串，调用方直接逐行输出即可。
function 装备_加成行(属性) {
    var 行 = [];
    for (var i = 0; i < 装备_加成项.length; i++) {
        var 值 = 属性[装备_加成项[i][0]];
        if (值 && 值 !== 0) {
            行.push(装备_加成项[i][1] + " +#r" + 值 + "#k");
        }
    }
    if (属性.tuc && 属性.tuc > 0) {
        行.push("可升级次数 +#r" + 属性.tuc + "#k");
    }
    return 行;
}

// 半角宽度：中文按 2 格、ASCII 按 1 格。客户端点阵字体里全角正好是半角的两倍宽，
// 用这个单位补空格就能让两段文字左右对齐。对话框没有制表位，别用 \t 去对齐。
function 文本_宽度(文本) {
    var 宽 = 0;
    for (var i = 0; i < 文本.length; i++) {
        宽 += (文本.charCodeAt(i) > 0x7F) ? 2 : 1;
    }
    return 宽;
}

function 文本_补右(文本, 目标宽) {
    var 缺 = 目标宽 - 文本_宽度(文本);
    return 缺 > 0 ? 文本 + new Array(缺 + 1).join(" ") : 文本;
}

function 文本_补左(文本, 目标宽) {
    var 缺 = 目标宽 - 文本_宽度(文本);
    return 缺 > 0 ? new Array(缺 + 1).join(" ") + 文本 : 文本;
}
"""


def sha(data) -> str:
    return hashlib.sha256(data).hexdigest()


def xml_signature(element, exclude=frozenset()) -> str:
    """元素语义指纹：剔除新插入的子节点、忽略 tail（纯缩进空白）。

    插入点是锚点的行首，会让前一个兄弟节点的 tail 变成新块的缩进，
    这是唯一允许的差异；元素本身、text、属性和子节点顺序都必须逐字节一致。
    """
    clone = copy.deepcopy(element)
    for child in list(clone):
        if child.get("name") in exclude:
            clone.remove(child)
    for node in clone.iter():
        node.tail = None
    return ET.tostring(clone).decode("utf-8")


# 与 a.insert_xml_properties_before 等价，只是把缩进深度封顶：
# 仓库里有些 XML（例如 wz-zh-CN/String.wz/Etc.img.xml 的 Etc 容器尾部）被
# 别的工具写成了几百个空格的缩进，照抄那份缩进会让新块凭空多出十几 KB 空格。
XML_MAX_INDENT_DEPTH = 12


def insert_xml_properties(text: str, parent_path: tuple[str, ...], props: list, before_name: str) -> str:
    root = a.scan_xml(text)
    current = root
    for part in parent_path:
        matches = [child for child in current.children if child.name == part]
        if len(matches) != 1:
            raise RuntimeError(f"XML path is not unique: {'/'.join(parent_path)}")
        current = matches[0]
    existing = {child.name for child in current.children}
    duplicates = [prop.name for prop in props if prop.name in existing]
    if duplicates:
        raise FileExistsError(", ".join(duplicates))
    anchors = [child for child in current.children if child.name == before_name]
    if len(anchors) != 1:
        raise RuntimeError(f"XML anchor is not unique: {before_name}")

    anchor = anchors[0]
    line_start = text.rfind("\n", 0, anchor.start) + 1
    indent = text[line_start:anchor.start]
    depth = min(len(indent) // 2, XML_MAX_INDENT_DEPTH)
    insert_at = line_start if not indent.strip() else anchor.start
    block = "".join(a.property_to_xml(prop, depth) + "\n" for prop in props)
    result = text[:insert_at] + block + text[insert_at:]
    a.scan_xml(result)
    return result


def scalar_node(name: str, values: dict):
    node = a.WzSubProperty(name)
    for key, value in values.items():
        (a.set_string if isinstance(value, str) else a.set_int)(node, key, value)
    return node


def ticket_bitmap() -> Image.Image:
    """把提供的 PNG 贴到 32x32 透明底上（超尺寸先等比缩到 32 以内，底部居中）。"""
    source = Image.open(ICON_SOURCE).convert("RGBA")
    if source.width > ICON_SIZE or source.height > ICON_SIZE:
        source = source.copy()
        source.thumbnail((ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (ICON_SIZE, ICON_SIZE))
    canvas.alpha_composite(source, ((ICON_SIZE - source.width) // 2, ICON_SIZE - source.height))
    return canvas


def decode_4444(canvas) -> Image.Image:
    import numpy as np

    raw = a._decompress(canvas, a.GMS_KEY)
    if len(raw) != canvas.width * canvas.height * 2:
        raise RuntimeError("ARGB4444 payload length mismatch")
    pixels = np.frombuffer(raw, dtype=np.uint8).reshape(canvas.height, canvas.width, 2)
    lo, hi = pixels[:, :, 0], pixels[:, :, 1]
    rgba = np.stack(((hi & 15) * 17, (lo >> 4) * 17, (lo & 15) * 17, (hi >> 4) * 17), axis=2)
    return Image.fromarray(rgba)


class Rewards:
    def __init__(self):
        self.outputs: dict[str, bytes] = {}
        # 本工具负责的全部文件（含本次因幂等而跳过的），清单里必须都记录哈希，
        # 否则第二次运行会把跳过的文件从清单里丢掉。
        self.managed: list[str] = []
        self.script_blocks: dict[str, list[tuple[str, str]]] = {}
        self.approved: dict[str, list[list[str]]] = {}
        self.xml_approved: dict[str, tuple[tuple[str, ...], set[str]]] = {}
        self.canvas_count = 0
        self.pool: dict[str, list[int]] = {}
        self.fafnir: list[int] = []

    # ---------------------------------------------------------------- 输出登记
    def put(self, relative: str, data) -> None:
        self.outputs[relative] = data if isinstance(data, bytes) else data.encode("utf-8")

    def validate_img(self, relative: str, data: bytes, approved=None) -> None:
        image = a.WzImage.from_bytes(data, key=a.GMS_KEY, name=relative)
        image.parse()
        if image.truncated or image.parse_warnings:
            raise RuntimeError(f"invalid {relative}: {image.parse_warnings}")
        for node, path in a.walk(image.root):
            if approved and not any(tuple(path.split("/"))[:len(root)] == root for root in approved):
                continue
            if isinstance(node, a.WzCanvasProperty):
                if (node.format, node.format2) != (1, 0):
                    raise RuntimeError(f"Canvas format: {relative}:{path}")
                bitmap = decode_4444(node)
                if bitmap.getbbox() is None:
                    raise RuntimeError(f"invisible Canvas: {relative}:{path}")
                self.canvas_count += 1
            if isinstance(node, a.WzUolProperty) and node.parent.get(str(node.value)) is None:
                raise RuntimeError(f"unresolved UOL: {relative}:{path}")

    def all_ids_present(self, relative: str, parent: tuple[str, ...], names: set[str]) -> bool:
        """目标文件里是否已经全部存在（用于幂等）。"""
        data = (ROOT / relative).read_bytes()
        image = a.WzImage.from_bytes(data, key=a.GMS_KEY)
        image.parse()
        node = image.root.get("/".join(parent)) if parent else image.root
        if node is None:
            return False
        existing = {child.name for child in node.children()}
        if not names.issubset(existing):
            missing = names - existing
            present = names & existing
            if present:
                raise RuntimeError(f"{relative}: 部分道具已存在，先人工核对 {sorted(missing)}")
            return False
        return True

    # ------------------------------------------------------- 原始记录插入（IMG+XML）
    def insert(self, relative: str, parent: tuple[str, ...], props: list, xmls=()) -> None:
        names = {prop.name for prop in props}
        anchor_parent = "/".join(parent) if parent else "<root>"
        if relative not in self.managed:
            self.managed.append(relative)
        for xml_rel in xmls:
            if xml_rel not in self.managed:
                self.managed.append(xml_rel)
        if self.all_ids_present(relative, parent, names):
            print(f"  skip {relative} （{anchor_parent} 下 {len(names)} 条已存在）")
            return
        current = (ROOT / relative).read_bytes()
        image = a.WzImage.from_bytes(current, key=a.GMS_KEY)
        image.parse()
        node = image.root.get("/".join(parent)) if parent else image.root
        if node is None:
            raise RuntimeError(f"missing insertion parent {relative}:{parent}")
        anchor = node.children()[-1].name
        result = a.insert_property_records_before(current, parent, props, anchor)
        approved = {(*parent, name) for name in names}
        self.validate_img(relative, result, approved)
        self.approved[relative] = [list(x) for x in sorted(approved)]
        self.put(relative, result)

        for xml_rel in xmls:
            text = (ROOT / xml_rel).read_text(encoding="utf-8")
            root = ET.fromstring(text)
            par = root
            for key in parent:
                par = next(child for child in par if child.get("name") == key)
            xml_anchor = list(par)[-1].get("name")
            result_text = insert_xml_properties(text, parent, props, xml_anchor)
            new = ET.fromstring(result_text)
            par_new = new
            for key in parent:
                par_new = next(child for child in par_new if child.get("name") == key)
            if xml_signature(par_new, names) != xml_signature(par):
                raise RuntimeError(f"protected XML changed {xml_rel}")
            self.xml_approved[xml_rel] = (parent, names)
            self.put(xml_rel, result_text)

    # ------------------------------------------------------------- 脚本标记块
    def script_block(self, file_name: str, begin: str, end: str, body: str) -> None:
        """替换一个标记块的内容。

        同一文件有多个标记块时，第二次调用必须基于「上一次的待写内容」而不是磁盘原文，
        否则后写的块会把先写的块覆盖回旧内容。
        """
        path = SCRIPT_DIR / file_name
        relative = str(path.relative_to(ROOT))
        pending = self.outputs.get(relative)
        text = pending.decode("utf-8") if pending is not None else path.read_text(encoding="utf-8")
        if text.count(begin) != 1 or text.count(end) != 1:
            raise RuntimeError(f"{relative}: 标记块必须各出现一次（{begin} / {end}）")
        head, rest = text.split(begin, 1)
        _, tail = rest.split(end, 1)
        self.script_blocks.setdefault(relative, []).append((begin, end))
        if relative not in self.managed:
            self.managed.append(relative)
        self.put(relative, head + begin + body + end + tail)

    def file_hash(self, relative: str) -> str:
        """本次生成的用内存内容，跳过未生成的读磁盘——两种都要进清单。"""
        data = self.outputs.get(relative)
        if data is None:
            data = (ROOT / relative).read_bytes()
        return sha(data)

    # ------------------------------------------------------------------ 数据源
    def load_pool(self) -> None:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        items = catalog["items"]
        for segment, name in POOL_KINDS:
            ids = sorted(item["id"] for item in items if item["id"] // 10000 == segment)
            if not ids:
                raise RuntimeError(f"奖池分类为空: {name}")
            self.pool[name] = ids
        # 法弗纳：后台数据里 16 种武器各有 3 个复本（名称与数值完全相同），
        # 商店只上架每种武器 ID 最小的那件，避免货架上摆三件一样的武器。
        smallest: dict[str, int] = {}
        for item in items:
            name = item.get("name") or ""
            if not name.startswith(FAFNIR_PREFIX):
                continue
            current = smallest.get(name)
            if current is None or item["id"] < current:
                smallest[name] = item["id"]
        self.fafnir = sorted(smallest.values())
        if len(self.fafnir) != FAFNIR_EXPECTED:
            raise RuntimeError(f"法弗纳件数 {len(self.fafnir)} != {FAFNIR_EXPECTED}")

    # ------------------------------------------------------------------ 各步骤
    def tickets(self) -> None:
        """抽奖卷道具 + 中文名称。

        幂等：5 件道具与 5 条名称都已在位时整段跳过，**不再读 ICON_SOURCE**。
        图标源是用户临时给的（Downloads/5157420.png），随时可能被清掉，
        而图标早已编码进 0400.img —— 重跑生成器不该反过来依赖那个文件。
        """
        item_names = {"0" + str(item_id) for item_id, _n, _d in TICKETS}
        string_names = {str(item_id) for item_id, _n, _d in TICKETS}
        if self.all_ids_present(ITEM_IMG, (), item_names) and \
                self.all_ids_present(STRING_IMG, STRING_PARENT, string_names):
            for relative in (ITEM_IMG, ITEM_XML, STRING_IMG, *STRING_XMLS):
                if relative not in self.managed:
                    self.managed.append(relative)
            for item_id, name, draws in TICKETS:
                print(f"  skip 抽奖卷 {item_id} {name}（{draws} 抽）—— 道具与名称均已存在")
            self.validate_ticket_canvases()
            return
        if not ICON_SOURCE.exists():
            raise RuntimeError(f"需要新建抽奖卷，但图标源文件已不存在: {ICON_SOURCE}")

        bitmap = ticket_bitmap()
        if bitmap.getbbox() is None:
            raise RuntimeError(f"抽奖卷图标全透明: {ICON_SOURCE}")
        props = []
        strings = []
        for item_id, name, draws in TICKETS:
            node = a.WzSubProperty("0" + str(item_id))
            info = scalar_node("info", {"slotMax": 1000, "price": 1, "tradeBlock": 1, "notSale": 1})
            for icon_name in ("icon", "iconRaw"):
                canvas = a.WzCanvasProperty(icon_name)
                canvas.width = canvas.height = ICON_SIZE
                canvas.format = 1
                canvas.format2 = 0
                canvas._png_data = a.encode_canvas_payload(
                    bitmap, 1, ICON_SIZE, ICON_SIZE, key=a.GMS_KEY, listwz=False, zlib_level=6
                )
                canvas._png_length = len(canvas._png_data)
                canvas._png_offset = 0
                canvas.add(a.WzVectorProperty("origin", 0, ICON_SIZE))
                info.add(canvas)
            node.add(info)
            props.append(node)
            strings.append(scalar_node(str(item_id), {"name": name, "desc": DESC}))
            print(f"  道具 {item_id} {name}（{draws} 抽）")
        self.insert(ITEM_IMG, (), props, [ITEM_XML])
        self.insert(STRING_IMG, STRING_PARENT, strings, STRING_XMLS)
        # 无论本次有没有写入，都把 5 个抽奖卷的 icon/iconRaw 解码一遍：
        # 这样清单里的 canvas_decodes 始终反映交付件的真实状态，而不是"本次写了几张画布"。
        self.validate_ticket_canvases()

    def validate_ticket_canvases(self) -> None:
        data = (ROOT / ITEM_IMG).read_bytes()
        self.validate_img(ITEM_IMG, data, {("0" + str(item_id),) for item_id, _n, _d in TICKETS})

    def scripts(self) -> None:
        pool_body = "\nvar 起源奖池 = " + json.dumps(self.pool, ensure_ascii=False, separators=(",", ":")) + ";\n"
        for file_name in ("抽奖.js", "奖池预览.js"):
            self.script_block(file_name, *POOL_MARKERS, body=pool_body)
        fafnir_body = "\nvar 法弗纳清单 = " + json.dumps(self.fafnir, ensure_ascii=False, separators=(",", ":")) + ";\n"
        self.script_block("积分商店.js", *FAFNIR_MARKERS, body=fafnir_body)
        # 发放/掉落实现两份必须逐字节相同，否则抽奖和商店的口径会漂移。
        for file_name in ("抽奖.js", "积分商店.js"):
            self.script_block(file_name, *DROP_MARKERS, body=DROP_BODY)
        # 装备属性的键名口径同样必须一致（getEquipStats 剥 inc 前缀这件事写错就整段空白）。
        for file_name in ("奖池预览.js", "积分商店.js"):
            self.script_block(file_name, *EQUIP_MARKERS, body=EQUIP_BODY)

    def run(self) -> dict:
        self.load_pool()
        print("奖池：", {k: len(v) for k, v in self.pool.items()}, "合计",
              sum(len(v) for v in self.pool.values()))
        print("法弗纳上架：", len(self.fafnir), "件")
        print("奖励道具：")
        self.tickets()
        print("脚本数据块：")
        self.scripts()
        for relative, data in self.outputs.items():
            if relative.endswith(".xml"):
                ET.fromstring(data)
        return self.outputs

    # ------------------------------------------------------------------ 落地
    def install(self) -> None:
        for relative, data in self.outputs.items():
            target = ROOT / relative
            if relative in self.script_blocks:
                if not target.exists():
                    raise RuntimeError(f"missing script {relative}")
                old = target.read_text(encoding="utf-8")
                new = data.decode("utf-8")
                pairs = self.script_blocks[relative]
                # 结构自检：本工具的输出与它读到的输入，差异必须全部落在标记块之内。
                # 这不是"漂移检测"——块外的手工改动会被原样带进新内容（这是有意的，
                # 块只拥有自己的那一段）；真正被拦下的是标记丢失/重复，或者 body 里
                # 混进了结束标记导致切分错位。
                if mask_blocks(old, pairs) != mask_blocks(new, pairs):
                    raise RuntimeError(f"脚本标记块结构异常（块外内容被切分错位）: {relative}")
                if not target.read_bytes() == data:
                    a.atomic_write_text(target, new)
                continue
            if not target.exists():
                if not (relative in self.approved or relative in self.xml_approved):
                    raise RuntimeError(f"拒绝整体重写不存在的文件 {relative}")
                a.atomic_write_bytes(target, data)
                continue
            current = target.read_bytes()
            if current == data:
                continue
            if relative in self.approved:
                a.verify_raw_record_insert_scope(
                    current, data, {tuple(p) for p in self.approved[relative]}
                )
            elif relative in self.xml_approved:
                parent, ids = self.xml_approved[relative]
                signatures = []
                for payload in (current, data):
                    root = ET.fromstring(payload)
                    node = root
                    for name in parent:
                        node = next(child for child in node if child.get("name") == name)
                    signatures.append(xml_signature(node, ids))
                if signatures[0] != signatures[1]:
                    raise RuntimeError(f"XML 保护内容被改动: {relative}")
            else:
                raise RuntimeError(f"拒绝整体重写既有文件 {relative}")
            a.atomic_write_bytes(target, data)

        manifest = {
            "tickets": {
                str(item_id): {"name": name, "draws": draws}
                for item_id, name, draws in TICKETS
            },
            "desc": DESC,
            "icon_source": str(ICON_SOURCE),
            "pool": {k: len(v) for k, v in self.pool.items()},
            "pool_total": sum(len(v) for v in self.pool.values()),
            "fafnir": self.fafnir,
            "canvas_decodes": self.canvas_count,
            "files": {rel: self.file_hash(rel) for rel in sorted(self.managed)},
        }
        a.atomic_write_text(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


def mask_block(text: str, begin: str, end: str) -> str:
    """去掉标记块内容，只留块外文本。

    因为新内容本来就是由旧内容的「块外 + 新块内」拼出来的，所以拿它做
    old/new 比较**不会**检出「有人在块外手改」（那种改动会被原样保留）。
    它能保证的是结构没被切错：标记一旦丢失、重复，或 body 里混进结束标记，
    比较就会失配。
    """
    head, rest = text.split(begin, 1)
    _, tail = rest.split(end, 1)
    return head + begin + end + tail


def mask_blocks(text: str, pairs) -> str:
    """把文件里全部标记块的内容一起去掉，只留块外文本。

    同一文件有多个标记块时必须一次性屏蔽：只屏蔽其中一个的话，另一个块的内容仍留在
    文本里，比较就会把「另一个块被填充」误判成「块外被改动」。
    顺带校验每个标记各出现一次——重复或丢失都会在这里拦下。
    """
    for begin, end in pairs:
        if text.count(begin) != 1 or text.count(end) != 1:
            raise RuntimeError(f"标记块丢失或重复: {begin}")
        text = mask_block(text, begin, end)
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true", help="落地修改")
    parser.add_argument("--check", action="store_true", help="只报告计划")
    args = parser.parse_args()
    if not args.install and not args.check:
        args.check = True

    rewards = Rewards()
    rewards.run()
    print()
    for relative, data in sorted(rewards.outputs.items()):
        target = ROOT / relative
        old = target.read_bytes() if target.exists() else None
        if old is None:
            state = "NEW"
        elif old == data:
            state = "UNCHANGED"
        else:
            state = f"WRITE  {len(old)} -> {len(data)} bytes ({len(data) - len(old):+d})"
        print(f"  {state:38} {relative}")
    if args.check:
        print("\n（--check：未写入任何文件）")
        return 0
    rewards.install()
    print("\n已写入。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
