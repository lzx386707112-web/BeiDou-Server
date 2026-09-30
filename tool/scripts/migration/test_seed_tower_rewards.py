#!/usr/bin/env python3
"""起源之塔奖励（抽奖卷 / 奖池 / 积分商店 / 积分发放）契约测试。

只读校验，不修改任何文件。跑法：

    python3 tool/scripts/migration/test_seed_tower_rewards.py

覆盖：
  1. 5 个抽奖卷在客户端 Item/Etc/0400.img 里存在，info 字段齐全，
     icon/iconRaw 是 32x32 的 ARGB4444（format=1, format2=0）且像素非全透明。
  2. 客户端 String/Etc.img、服务端 wz / wz-zh-CN 两份 String.wz XML 都有名称与说明。
  3. 服务端 Item.wz/Etc/0400.img.xml 有对应记录。
  4. 两个脚本里的奖池数据块与后台装备预览的数据源 catalog.json 完全一致；
     法弗纳清单 = 每种武器 1 件。
  5. 大厅 NPC 菜单项齐全，4 个子脚本存在。
  6. 两份 SeedTower20.js 代码部分一致，且积分规则 = 通关 40 / 超时 2×通过层数 / 主动退出 0。
  7. 生成清单 manifest 的文件哈希与实际文件一致。
"""
import importlib.util
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

spec = importlib.util.spec_from_file_location(
    "seed_arc", ROOT / "tool/scripts/migration/migrate_arcane_river_expansion.py"
)
a = importlib.util.module_from_spec(spec)
sys.modules["seed_arc"] = a
spec.loader.exec_module(a)

CATALOG = ROOT / "gms-server/src/main/resources/equipment-catalog/catalog.json"
ITEM_IMG = ROOT / "clien/Data/Item/Etc/0400.img"
STRING_IMG = ROOT / "clien/Data/String/Etc.img"
ITEM_XML = ROOT / "gms-server/wz/Item.wz/Etc/0400.img.xml"
STRING_XMLS = [
    ROOT / "gms-server/wz/String.wz/Etc.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Etc.img.xml",
]
SCRIPT_DIR = ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/起源之塔"
NPC = ROOT / "gms-server/scripts/npc/2540000.js"
EVENT_COPIES = [
    ROOT / "gms-server/scripts/event/SeedTower20.js",
    ROOT / "gms-server/scripts-zh-CN/event/SeedTower20.js",
]
MANIFEST = ROOT / "docs/migrations/seed-tower-rewards-manifest.json"

# (道具 ID, 名称, 抽取次数, 售价)
TICKETS = [
    (4009930, "起源抽奖卷1抽", 1, 40),
    (4009931, "起源抽奖卷5连抽", 5, 160),
    (4009932, "起源抽奖卷10连抽", 10, 360),
    (4009933, "起源抽奖卷20连抽", 20, 760),
    (4009934, "起源抽奖卷50连抽", 50, 1200),
]
DESC = "起源之塔专属抽奖卷"
POOL_KINDS = [(101, "脸饰"), (103, "耳环"), (112, "项环"), (113, "腰带")]
FAFNIR_TOTAL = 16
SUB_SCRIPTS = ["玩法说明.js", "积分商店.js", "抽奖.js", "奖池预览.js"]
MENU_ITEMS = ["玩法说明", "查看当前积分", "积分商店", "起源抽奖", "奖池预览"]


def load_image(path: Path):
    data = path.read_bytes()
    image = a.WzImage.from_bytes(data, key=a.GMS_KEY)
    image.parse()
    return data, image


def decode_4444(canvas):
    raw = a._decompress(canvas, a.GMS_KEY)
    if len(raw) != canvas.width * canvas.height * 2:
        raise AssertionError("ARGB4444 载荷长度不符")
    pixels = np.frombuffer(raw, dtype=np.uint8).reshape(canvas.height, canvas.width, 2)
    lo, hi = pixels[:, :, 0], pixels[:, :, 1]
    return np.stack(((hi & 15) * 17, (lo >> 4) * 17, (lo & 15) * 17, (hi >> 4) * 17), axis=2)


def code_lines(path: Path):
    return [ln.rstrip() for ln in path.read_text(encoding="utf-8").splitlines()
            if not ln.strip().startswith("//")]


def validate():
    assert MANIFEST.exists(), f"缺少生成清单 {MANIFEST}"
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    # ---- 1. 抽奖卷道具 ----------------------------------------------------
    data, image = load_image(ITEM_IMG)
    assert not image.truncated and not image.parse_warnings, "Item/Etc/0400.img 解析异常"
    for item_id, name, draws, _price in TICKETS:
        node = image.root.child("0" + str(item_id))
        assert node is not None, f"缺少道具记录 {item_id}"
        info = node.child("info")
        fields = {child.name: child for child in info.children()}
        for field in ("slotMax", "price", "tradeBlock", "notSale"):
            assert field in fields, f"{item_id} 缺少 info/{field}"
        assert fields["slotMax"].value >= 1, f"{item_id} slotMax 非法"
        for icon_name in ("icon", "iconRaw"):
            canvas = fields.get(icon_name)
            assert canvas is not None, f"{item_id} 缺少 {icon_name}"
            assert (canvas.width, canvas.height) == (32, 32), f"{item_id} {icon_name} 尺寸不是 32x32"
            assert (canvas.format, canvas.format2) == (1, 0), f"{item_id} {icon_name} 不是 ARGB4444"
            bitmap = Image.fromarray(decode_4444(canvas))
            assert bitmap.getbbox() is not None, f"{item_id} {icon_name} 全透明"
            origin = canvas.child("origin")
            assert origin is not None and tuple(origin.value) == (0, 32), f"{item_id} {icon_name} origin 异常"
        assert manifest["tickets"][str(item_id)]["name"] == name
        assert manifest["tickets"][str(item_id)]["draws"] == draws

    # ---- 2. 客户端 String ------------------------------------------------
    _sdata, simage = load_image(STRING_IMG)
    container = simage.root.child("Etc")
    assert container is not None, "String/Etc.img 缺少 Etc 容器"
    for item_id, name, _draws, _price in TICKETS:
        node = container.child(str(item_id))
        assert node is not None, f"String/Etc.img 缺少 {item_id}"
        assert str(node.child("name").value) == name, f"{item_id} 名称不符"
        assert str(node.child("desc").value) == DESC, f"{item_id} 说明不符"

    # ---- 3. 服务端 XML ---------------------------------------------------
    item_root = ET.fromstring(ITEM_XML.read_text(encoding="utf-8"))
    item_names = {child.get("name") for child in item_root}
    for item_id, *_ in TICKETS:
        assert ("0" + str(item_id)) in item_names, f"Item XML 缺少 {item_id}"
    for path in STRING_XMLS:
        root = ET.fromstring(path.read_text(encoding="utf-8"))
        par = next(child for child in root if child.get("name") == "Etc")
        names = {child.get("name") for child in par}
        for item_id, *_ in TICKETS:
            assert str(item_id) in names, f"{path.name} 缺少 {item_id}"

    # ---- 4. 奖池 / 法弗纳 数据块 -----------------------------------------
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    expect_pool = {name: sorted(i["id"] for i in catalog["items"] if i["id"] // 10000 == seg)
                   for seg, name in POOL_KINDS}
    smallest: dict[str, int] = {}
    for item in catalog["items"]:
        item_name = item.get("name") or ""
        if item_name.startswith("法弗纳"):
            smallest[item_name] = min(smallest.get(item_name, item["id"]), item["id"])
    expect_fafnir = sorted(smallest.values())
    assert len(expect_fafnir) == FAFNIR_TOTAL, f"后台数据里法弗纳种数 {len(expect_fafnir)} != {FAFNIR_TOTAL}"

    for file_name in ("抽奖.js", "奖池预览.js"):
        text = (SCRIPT_DIR / file_name).read_text(encoding="utf-8")
        matched = re.search(r"var 起源奖池 = (\{.*?\});", text, re.S)
        assert matched, f"{file_name} 缺少 起源奖池 数据块"
        assert json.loads(matched.group(1)) == expect_pool, f"{file_name} 奖池与 catalog.json 不一致"

    shop = (SCRIPT_DIR / "积分商店.js").read_text(encoding="utf-8")
    matched = re.search(r"var 法弗纳清单 = (\[[^\]]*\]);", shop)
    assert matched and json.loads(matched.group(1)) == expect_fafnir, "积分商店法弗纳清单不一致"
    for item_id, _name, _draws, price in TICKETS:
        assert re.search(r"\[%d, *\d+, *%d\]" % (item_id, price), shop), f"积分商店缺少 {item_id} 的 {price} 分售价"

    # ---- 4b. 装备属性键名契约 --------------------------------------------
    # 坑：ItemInformationProvider.getEquipStats() 会把 info 里以 "inc" 开头的字段
    # **去掉前缀**再入表（incSTR -> STR、incSpeed -> Speed），而 catalog.json 存的是
    # 原始 WZ 名（incSTR）。脚本如果照抄 catalog 的 incXXX 去查，真机上永远查不到，
    # 详情页会一条加成都不显示。这里把这个契约钉死。
    java_src = (ROOT / "gms-server/src/main/java/org/gms/server/ItemInformationProvider.java").read_text(
        encoding="utf-8")
    assert 'data.getName().startsWith("inc")' in java_src and \
           "ret.put(data.getName().substring(3)" in java_src, \
        "getEquipStats() 不再剥离 inc 前缀，属性键名契约已变，需重新核对 奖池预览.js"
    explicit_keys = set(re.findall(r'ret\.put\("([A-Za-z]+)"', java_src))
    assert {"reqJob", "reqLevel", "reqPOP", "cash", "tuc"} <= explicit_keys, \
        "getEquipStats() 的显式入表键发生变化，需重新核对 奖池预览.js"

    pool_stats_keys: set[str] = set()
    for item in catalog["items"]:
        if item["id"] // 10000 in {seg for seg, _ in POOL_KINDS}:
            pool_stats_keys |= set((item.get("stats") or {}).keys())
    pool_inc_keys = {k for k in pool_stats_keys if k.startswith("inc")}
    pool_stripped = {k[3:] for k in pool_inc_keys}

    preview = (SCRIPT_DIR / "奖池预览.js").read_text(encoding="utf-8")

    def js_pairs(var_name: str):
        block = re.search(r"var %s = \[(.*?)\];" % var_name, preview, re.S)
        assert block, f"奖池预览.js 缺少 {var_name} 表"
        return [(m.group(1), m.group(2))
                for m in re.finditer(r'\["([^"]+)",\s*"([^"]+)"\]', block.group(1))]

    # 变量名带 装备_ 前缀：它们住在「装备属性」标记块里，两个脚本共用同一份实现
    bonus = js_pairs("装备_加成项")
    demand = js_pairs("装备_需求项")
    assert bonus, "装备属性块里的 装备_加成项 为空"

    bad_prefix = [k for k, _ in bonus if k.startswith("inc")]
    assert not bad_prefix, f"加成项 误用了 inc 前缀键 {bad_prefix}（服务端会剥掉 inc，永远查不到）"
    covered = {k for k, _ in bonus}
    missing = sorted(pool_stripped - covered)
    assert not missing, f"奖池里出现的加成字段没有展示：{missing}（应写去掉 inc 后的名字）"

    demand_bad = [k for k, _ in demand if not k.startswith("req")]
    assert not demand_bad, f"需求项 键名异常 {demand_bad}"
    demand_unknown = sorted({k for k, _ in demand} - explicit_keys)
    assert not demand_unknown, f"需求项 用了服务端不返回的键 {demand_unknown}"

    # ---- 4c. 发放契约：背包放不下 → 掉在地上（抽奖与商店共用一份实现） ------
    # 抽奖.js 与 积分商店.js 共用一份**逐字节相同**的「掉落兜底」标记块，把放不下的
    # 部分掉在玩家脚下。任一服务端签名改名都会让它 **静默失效**（既不进背包也不掉落），
    # 所以这里同时核对 Java 源码。教训同 4b：脚本符号必须由实现反推，不能凭假设。
    draw = (SCRIPT_DIR / "抽奖.js").read_text(encoding="utf-8")
    shop = (SCRIPT_DIR / "积分商店.js").read_text(encoding="utf-8")
    begin_mark, end_mark = "// BEGIN 掉落兜底", "// END 掉落兜底"

    def drop_block(text: str, name: str) -> str:
        assert text.count(begin_mark) == 1 and text.count(end_mark) == 1, \
            f"{name} 的「掉落兜底」标记块被破坏（必须各出现一次）"
        return text.split(begin_mark)[1].split(end_mark)[0]

    draw_drop = drop_block(draw, "抽奖.js")
    shop_drop = drop_block(shop, "积分商店.js")
    assert draw_drop == shop_drop, \
        "抽奖.js 与 积分商店.js 的掉落实现不再一致（口径会漂移，请重跑 seed_tower_rewards.py）"

    maple_map = (ROOT / "gms-server/src/main/java/org/gms/server/maps/MapleMap.java").read_text(
        encoding="utf-8")
    assert re.search(
        r"public final void spawnItemDrop\(final MapObject dropper, final Character owner, "
        r"final Item item, Point pos, final boolean ffaDrop, final boolean playerDrop\)",
        maple_map), "MapleMap.spawnItemDrop(MapObject,Character,Item,Point,boolean,boolean) 签名已变"
    assert "FieldLimit.DROP_LIMIT.check(this.getFieldLimit())" in maple_map, \
        "spawnItemDrop 不再检查 DROP_LIMIT（禁止掉落的地图会静默吞掉道具）"

    field_limit = (ROOT / "gms-server/src/main/java/org/gms/server/maps/FieldLimit.java").read_text(
        encoding="utf-8")
    assert "DROP_LIMIT(0x400000)" in field_limit, "FieldLimit.DROP_LIMIT 的位值已变（脚本按 0x400000 判断）"
    assert "(fieldlimit & i) == i" in field_limit, "FieldLimit.check() 语义已变"

    iip = (ROOT / "gms-server/src/main/java/org/gms/server/ItemInformationProvider.java").read_text(
        encoding="utf-8")
    for symbol in ("public Item getEquipById(int equipId)",
                   "public Equip randomizeStats(Equip equip)",
                   "public boolean isPickupRestricted(int itemId)"):
        assert symbol in iip, f"ItemInformationProvider 缺少 {symbol!r}，掉落兜底会失效"

    item_java = (ROOT / "gms-server/src/main/java/org/gms/client/inventory/Item.java").read_text(
        encoding="utf-8")
    assert "public Item(int id, short position, short quantity)" in item_java, \
        "Item(int,short,short) 构造器已变，掉落块的 new Item(id,0,数量) 会失效"

    item_constants = (ROOT / "gms-server/src/main/java/org/gms/constants/inventory/ItemConstants.java"
                      ).read_text(encoding="utf-8")
    assert "public static boolean isAccessory(int itemId)" in item_constants, \
        "ItemConstants.isAccessory(int) 签名已变"

    char_java = (ROOT / "gms-server/src/main/java/org/gms/client/Character.java").read_text(
        encoding="utf-8")
    assert "public boolean haveItemWithId(int itemid, boolean checkEquipped)" in char_java, \
        "Character.haveItemWithId(int,boolean) 签名已变"

    aip = (ROOT / "gms-server/src/main/java/org/gms/scripting/AbstractPlayerInteraction.java").read_text(
        encoding="utf-8")
    assert "public boolean canHold(int itemid, int quantity)" in aip, "cm.canHold(int,int) 签名已变"
    assert "public Item gainItem(int id, short quantity, boolean randomStats, boolean showMessage)" in aip, \
        "cm.gainItem(int,short,boolean,boolean) 签名已变（掉落块的进包那条路要用它）"

    # 脚本侧：掉落块必须真的落地，且装备构造口径与 gainItem 一致
    assert "spawnItemDrop(chr, chr, 件, chr.getPosition(), false, false)" in draw_drop, \
        "掉落块不再把道具掉在玩家脚下（写法：chr, chr, ..., false, false）"
    assert "DROP_LIMIT.check" in draw_drop and "getFieldLimit()" in draw_drop, \
        "掉落块缺少「该地图禁止掉落」的判断，会把道具静默丢掉"
    assert "getEquipById" in draw_drop and "randomizeStats" in draw_drop, \
        "掉落块未按 gainItem 的口径构造装备（地上的会和包里的品质不同）"
    assert "isAccessory" in draw_drop and "setUpgradeSlots(3)" in draw_drop, \
        "掉落块没有给升级次数为 0 的饰品补 3 次（对齐 AbstractPlayerInteraction:648）"
    assert "cm.canHold(道具ID, 1)" in draw_drop, \
        "掉落块没有逐件预检 canHold（会触发 gainItem 内部「背包已满」刷屏）"
    assert draw_drop.count("掉落_发一个") >= 1, "掉落块没有提供统一的 掉落_发一个()"

    # 抽奖：逐件判定、随机潜能（与 gainItem(id,1,true,true) 同口径）
    assert "掉落_发一个(chr, id, true)" in draw, \
        "抽奖.js 没有按「随机潜能」口径发放（应与 gainItem(id,1,true,true) 一致）"
    assert "isPickupRestricted(id) && chr.haveItemWithId(id, true)" in draw, \
        "抽奖.js 不再排除已拥有的唯一件（info/only=1 抽到也发不出、捡不起）"
    assert "直接掉在你脚下" in draw, "抽奖.js 的确认框没有提示背包满会掉地上"
    assert "请先清理装备栏" not in draw, "抽奖.js 仍在整轮拒绝背包满的抽奖（需求是掉在地上）"

    # ---- 4d. 抽取口径：同一批连抽内不重复 ----------------------------------
    # 抽走一件就从候选池移除一件。三条必须同时成立，少一条就会静默退化成别的口径：
    #   ① 候选池是 奖池() 的**副本** —— 原地删会把平铺缓存抽空，下一批就没奖可抽；
    #   ② 排除「已拥有的唯一件」只发生在**建池时** —— 放进循环里重试，命中率会随
    #      收集进度一路下滑（已收集 1000 件时仅 13.3%，重试 8 次仍全落空 = 31.9%，
    #      也就是卷照扣、什么都没给）；
    #   ③ 取一件必须真的移出候选池 —— 否则同批内会再抽到同一件。
    assert "var 候选 = 候选池(chr);" in draw, \
        "抽奖.js 不再为每批连抽单独建候选池（同批不重复的前提）"
    assert "抽一件(候选)" in draw, "抽奖.js 的抽取不再走候选池"
    assert "抽一件(池, chr)" not in draw, "抽奖.js 又退回按原池直接抽取"
    assert re.search(r"池\[Math\.floor\(Math\.random\(\) \* 池\.length\)\]", draw) is None, \
        "抽奖.js 又退回「有放回」的取池方式（同一批连抽会抽出重复件）"
    assert "候选[位] = 候选[候选.length - 1];" in draw and "候选.pop();" in draw, \
        "抽奖.js 的候选池没有实现「取走即移除」，同批内会重复"
    pool_body = draw.split("function 候选池")[1].split("function 抽一件")[0]
    assert "var 源 = 奖池();" in pool_body and "出.push(id);" in pool_body \
        and "return 出;" in pool_body, \
        "候选池 必须复制 奖池() 再筛后返回新数组，而不是原地删"
    for breaker in ("源.pop(", "源.splice(", "源.shift(", "源.unshift(", "源.reverse(",
                    "源.sort(", "源.length =", "奖池().pop(", "奖池().splice("):
        assert breaker not in pool_body, \
            f"候选池 直接改动了 奖池() 的返回数组（{breaker}）—— 平铺缓存会被抽空，下一批无奖可抽"
    assert "isPickupRestricted(id)" in pool_body, \
        "候选池 没有再排除已拥有的唯一件（会白占本批名额）"
    assert draw.count("// BEGIN 起源奖池") == 1 and draw.count("// END 起源奖池") == 1, \
        "抽奖.js 的生成块标记被破坏"

    # 商店：只把"超出背包容量的部分"掉地上，不再整笔拒绝
    assert "掉落_发一个(chr, 商品.id, false)" in shop, \
        "积分商店.js 没有走发放兜底（超出的部分应掉在地上）"
    assert "背包空间不足，请先清理" not in shop, \
        "积分商店.js 仍在整笔拒绝背包满的购买（需求是超出的部分掉在地上）"
    assert "背包空间不足" in shop and "直接掉在你脚下" in shop, \
        "积分商店.js 的确认框没有提示超出的部分会掉地上"
    assert "写积分(持有 - 花费)" in shop, "积分商店.js 的扣分口径被改动（应为整笔扣除）"

    # ---- 4d. UI 契约：属性块共用 + 图标必须在 #L 链接之外 -------------------
    # 两条都是「写错不报错、只是静默变丑」的坑：
    #   ① 属性块被拆成两份不同实现 → 两个界面显示的属性不一样，很难发现；
    #   ② #v 图标套在 #L...#l 里面 → 客户端把鼠标交互交给链接，悬停说明弹不出来。
    #      #i 是静态图标、#v 才是可交互图标（见 TMS-248 的 resources/npcFormatting.txt）。
    equip_begin, equip_end = "// BEGIN 装备属性", "// END 装备属性"

    def equip_block(text: str, name: str) -> str:
        assert text.count(equip_begin) == 1 and text.count(equip_end) == 1, \
            f"{name} 的「装备属性」标记块被破坏（必须各出现一次）"
        return text.split(equip_begin)[1].split(equip_end)[0]

    assert equip_block(preview, "奖池预览.js") == equip_block(shop, "积分商店.js"), \
        "奖池预览.js 与 积分商店.js 的装备属性实现不再一致（请重跑 seed_tower_rewards.py）"

    for text, name in ((preview, "奖池预览.js"), (shop, "积分商店.js")):
        assert not re.search(r"#L\d*#[^#]*#v\d+#", text), \
            f"{name} 把 #v 图标写进了 #L 链接内部，悬停说明会失效"
    # 源码是拼接出来的，所以断言拼接形态：`"#v" + <id> + "# #L" + <序号> + "#"`。
    # 一旦有人改成 `"#L" + n + "##v" + id + "#"`（图标被链接包住），这里就会红。
    assert re.search(r'"#v"\s*\+\s*[^+?]+\+\s*"# #L"', preview), \
        "奖池预览.js 的图标没有放在 #L 链接之外（悬停说明会失效）"
    assert re.search(r'"#v"\s*\+\s*[^+?]+\+\s*"# #L"', shop), \
        "积分商店.js 的图标没有放在 #L 链接之外（悬停说明会失效）"
    assert "\\t" not in shop.split("// BEGIN 掉落兜底")[0], \
        "积分商店.js 的菜单又用 \\t 对齐了（对话框没有制表位，会错位）"

    # ---- 5. NPC / 子脚本 --------------------------------------------------
    npc = NPC.read_text(encoding="utf-8")
    for label in MENU_ITEMS:
        assert label in npc, f"大厅 NPC 缺少菜单项「{label}」"
    for file_name in SUB_SCRIPTS:
        assert (SCRIPT_DIR / file_name).exists(), f"缺少子脚本 {file_name}"
    assert "起源积分" in npc, "大厅 NPC 未使用 起源积分"

    # ---- 6. 事件脚本积分规则 ---------------------------------------------
    assert code_lines(EVENT_COPIES[0]) == code_lines(EVENT_COPIES[1]), \
        "两份 SeedTower20.js 的代码部分不再一致"
    event = "\n".join(code_lines(EVENT_COPIES[1]))
    assert "function timeout(eim,reason)" in event, "缺少 timeout() 超时专用出口"
    assert "function awardSeedPoints(eim)" in event, "缺少 awardSeedPoints()"
    assert 'kind == "clear" ? 40 : 2 * num(eim,"cleared")' in event, "结算规则不是 通关40 / 超时2×层数"
    assert "awardSeedPoints(eim);" in event, "end() 未调用发分"
    assert 'function scheduledTimeout(eim) {timeout(eim' in event, "scheduledTimeout 未打超时标记"
    for key in ("起源积分", "起源累计积分"):
        assert key in event, f"事件脚本缺少积分键 {key}"
    # 主动退出 / 死亡 / 掉线路径不得打标记
    assert "function playerExit(eim,chr) {end(eim);}" in event, "playerExit 不应发分"
    assert "function playerLeft(eim,chr) {end(eim);}" in event, "playerLeft 不应发分"

    # ---- 7. manifest 哈希 -------------------------------------------------
    import hashlib
    for rel, digest in manifest["files"].items():
        path = ROOT / rel
        assert path.exists(), f"清单里的文件不存在 {rel}"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == digest, f"清单哈希不符 {rel}"
    assert manifest["pool_total"] == sum(len(v) for v in expect_pool.values())

    print(f"抽奖卷 {len(TICKETS)} 个；奖池 {manifest['pool']} 共 {manifest['pool_total']} 件；"
          f"法弗纳 {len(expect_fafnir)} 件；清单文件 {len(manifest['files'])} 个")
    print("起源之塔奖励契约测试：全部通过")


if __name__ == "__main__":
    validate()
