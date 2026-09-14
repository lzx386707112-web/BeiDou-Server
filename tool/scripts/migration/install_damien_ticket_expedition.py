#!/usr/bin/env python3
"""Install Damien daily ticket and align reflect 145 with Ranmaru."""

from __future__ import annotations

import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT / "tool/wz-python"),
    str(ROOT / "tool/scripts/migration"),
    str(ROOT / "tool/scripts/patch-client"),
]

import add_ranmaru_daily_ticket as daily  # noqa: E402
import migrate_arcane_river_expansion as arc  # noqa: E402
from migrate_twilight_perion_monster_park import (  # noqa: E402
    add_int,
    add_string,
    add_sub,
    append_named_records,
    load_checked,
)
from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.incremental_img import replace_img_record  # noqa: E402

CLIENT_QUEST_ID = 57482
SERVER_QUEST_ID = CLIENT_QUEST_ID - 65536
CLIENT_QUEST_NAME = str(CLIENT_QUEST_ID)
SERVER_QUEST_NAME = str(SERVER_QUEST_ID)
QUEST_NPC_ID = 1540895
TICKET_ID = 4000698
ITEM_NODE = f"0{TICKET_ID}"
STRING_NODE = str(TICKET_ID)
ITEM_ANCHOR = "04000828"
STRING_ANCHOR = "4000828"
PREVIOUS_ITEM = "04000697"
PREVIOUS_STRING = "4000697"
ITEM_NAME = "戴米安挑战门票"
ITEM_DESC = "可进入戴米安战斗的免费门票，使用1次即作废。"
KILL_COUNT = 100
FIELD_MOBS = tuple(3503000 + i for i in range(10))
QUEST_NAMES = ("Act", "Check", "QuestInfo", "Say")
# Keep MobSkill 145 on its distinct projected TMS action and a GMS-safe level.
# Level 9 exists in both the legacy client and server MobSkill resources.
SKILL_REMAPS = {
    8880110: {
        (("info", "skill", "2", "action"), 3),
        (("info", "skill", "2", "level"), 9),
    },
    8880111: {
        (("info", "skill", "2", "action"), 3),
        (("info", "skill", "2", "level"), 9),
    },
}
CLIENT_ITEM = ROOT / "clien/Data/Item/Etc/0400.img"
CLIENT_STRING = ROOT / "clien/Data/String/Etc.img"
SERVER_ITEM = ROOT / "gms-server/wz/Item.wz/Etc/0400.img.xml"
SERVER_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Etc.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Etc.img.xml",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clone_canvas(name: str, parent: WzSubProperty, source: WzCanvasProperty) -> WzCanvasProperty:
    decode_canvas(source, region="GMS")
    canvas = WzCanvasProperty(name, parent)
    canvas.width = source.width
    canvas.height = source.height
    canvas.format = source.format
    canvas.format2 = source.format2 or 0
    if not source._png_data:
        raise RuntimeError(f"source canvas {source.name} has no payload")
    canvas._png_data = source._png_data
    canvas._png_length = len(canvas._png_data)
    origin = source.child("origin")
    if origin is not None:
        canvas.add(WzVectorProperty("origin", int(origin.x), int(origin.y), canvas))
    return canvas


def make_item_node(source_item: WzSubProperty) -> WzSubProperty:
    info_src = source_item.child("info")
    item = WzSubProperty(ITEM_NODE)
    info = WzSubProperty("info", item)
    item.add(info)
    for canvas_name in ("icon", "iconRaw"):
        source = info_src.child(canvas_name)
        if not isinstance(source, WzCanvasProperty):
            raise RuntimeError(f"4000697 missing {canvas_name}")
        info.add(clone_canvas(canvas_name, info, source))
    info.add(WzIntProperty("notSale", 1, info))
    info.add(WzIntProperty("price", 1, info))
    info.add(WzIntProperty("slotMax", 200, info))
    return item


def make_string_node() -> WzSubProperty:
    node = WzSubProperty(STRING_NODE)
    node.add(WzStringProperty("desc", ITEM_DESC, node))
    node.add(WzStringProperty("name", ITEM_NAME, node))
    return node


def xml_has_path(text: str, path: tuple[str, ...]) -> bool:
    current = arc.scan_xml(text)
    for part in path:
        matches = [child for child in current.children if child.name == part]
        if len(matches) != 1:
            return False
        current = matches[0]
    return True


def insert_or_keep_xml(original: str, parent_path: tuple[str, ...], node: WzSubProperty, before_name: str) -> str:
    if xml_has_path(original, (*parent_path, node.name)):
        return original
    updated = arc.insert_xml_properties_before(original, parent_path, [node], before_name)
    ET.fromstring(updated)
    return updated


def patch_ticket_item() -> None:
    original = CLIENT_ITEM.read_bytes()
    image = load_checked(CLIENT_ITEM, arc.GMS_KEY)
    source = image.root.child(PREVIOUS_ITEM)
    if not isinstance(source, WzSubProperty):
        raise RuntimeError("missing source ticket 4000697")
    node = make_item_node(source)
    records, _ = arc.raw_record_state(original)
    if (node.name,) in records:
        item_data = original
    else:
        item_data = arc.insert_property_record_before(original, (), node, ITEM_ANCHOR)
        arc.verify_raw_record_insert_scope(original, item_data, {(node.name,)})
        checked = WzImage.from_bytes(item_data, key=arc.GMS_KEY, name=CLIENT_ITEM.name)
        checked.parse()
        if checked.truncated or checked.parse_warnings:
            raise RuntimeError("item IMG parse failed after 4000698 insert")
        arc.atomic_write_bytes(CLIENT_ITEM, item_data)
    string_node = make_string_node()
    string_original = CLIENT_STRING.read_bytes()
    records, _ = arc.raw_record_state(string_original)
    if ("Etc", string_node.name) in records:
        string_data = string_original
    else:
        string_data = arc.insert_property_record_before(
            string_original, ("Etc",), string_node, STRING_ANCHOR
        )
        arc.verify_raw_record_insert_scope(string_original, string_data, {("Etc", string_node.name)})
        checked = WzImage.from_bytes(string_data, key=arc.GMS_KEY, name=CLIENT_STRING.name)
        checked.parse()
        if checked.truncated or checked.parse_warnings:
            raise RuntimeError("String/Etc parse failed after 4000698 insert")
        arc.atomic_write_bytes(CLIENT_STRING, string_data)
    xml_item = SERVER_ITEM.read_text(encoding="utf-8")
    updated_item = insert_or_keep_xml(xml_item, (), node, ITEM_ANCHOR)
    if updated_item != xml_item:
        SERVER_ITEM.write_text(updated_item, encoding="utf-8")
    for path in SERVER_STRINGS:
        text = path.read_text(encoding="utf-8")
        updated = insert_or_keep_xml(text, ("Etc",), string_node, STRING_ANCHOR)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
    validate_ticket()


def validate_ticket() -> None:
    item = load_checked(CLIENT_ITEM, arc.GMS_KEY)
    names = [child.name for child in item.root.children()]
    if names.index(ITEM_NODE) != names.index(PREVIOUS_ITEM) + 1:
        raise RuntimeError("4000698 is not immediately after 4000697")
    if names[names.index(ITEM_NODE) + 1] != ITEM_ANCHOR:
        raise RuntimeError("4000698 is not immediately before 04000828")
    record = item.root.child(ITEM_NODE)
    for canvas_name in ("icon", "iconRaw"):
        canvas = record.get(f"info/{canvas_name}")
        if not isinstance(canvas, WzCanvasProperty):
            raise RuntimeError(f"missing {canvas_name}")
        if (int(canvas.format), int(canvas.format2 or 0)) != (1, 0):
            raise RuntimeError(f"{canvas_name} is not ARGB4444")
        decoded = decode_canvas(canvas, region="GMS")
        if decoded.getbbox() is None:
            raise RuntimeError(f"{canvas_name} has no visible pixels")
    strings = load_checked(CLIENT_STRING, arc.GMS_KEY)
    text = strings.root.get(f"Etc/{STRING_NODE}")
    if str(arc.child_value(text, "name")) != ITEM_NAME:
        raise RuntimeError("unexpected Damien ticket name")


def progress_line() -> str:
    lines = ["在堕落世界树击杀以下怪物各100只：", ""]
    for index, mob_id in enumerate(FIELD_MOBS, start=1):
        lines.append(f"#o{mob_id}# #r#a{CLIENT_QUEST_ID}{index}##k")
    return "\n".join(lines)


def build_quest_node(record_name: str, kind: str) -> WzSubProperty:
    node = WzSubProperty(record_name)
    if kind == "QuestInfo":
        add_string(node, "0", "去堕落世界树找#b#p1540895##k，听取魔族清剿委托。")
        add_string(node, "1", progress_line())
        add_string(node, "2", "完成了堕落世界树清剿，获得了#b#t4000698##k。")
        add_int(node, "area", 1)
        add_string(node, "name", "[每日] 堕落世界树的清剿")
        return node
    if kind == "Check":
        start = add_sub(node, "0")
        add_int(start, "interval", 1440)
        add_int(start, "lvmin", 180)
        add_int(start, "npc", QUEST_NPC_ID)
        end = add_sub(node, "1")
        add_int(end, "npc", QUEST_NPC_ID)
        add_int(end, "order", 1)
        mobs = add_sub(end, "mob")
        for index, mob_id in enumerate(FIELD_MOBS):
            entry = add_sub(mobs, str(index))
            add_int(entry, "id", mob_id)
            add_int(entry, "count", KILL_COUNT)
        return node
    if kind == "Act":
        add_sub(node, "0")
        act_end = add_sub(node, "1")
        items = add_sub(act_end, "item")
        reward = add_sub(items, "0")
        add_int(reward, "id", TICKET_ID)
        add_int(reward, "count", 1)
        return node
    if kind == "Say":
        start_say = add_sub(node, "0")
        add_string(
            start_say,
            "0",
            "堕落世界树里的魔族太多了。去击杀#b#o3503000#、#o3503001#、#o3503002#、#o3503003#、#o3503004#、#o3503005#、#o3503006#、#o3503007#、#o3503008#、#o3503009##k各100只。完成后给你#b#t4000698##k。",
        )
        no = add_sub(start_say, "no")
        add_string(no, "0", "准备好再来找我。")
        yes = add_sub(start_say, "yes")
        add_string(yes, "0", "去世界树清剿那些魔族，打完回来。")
        end_say = add_sub(node, "1")
        add_string(end_say, "0", "干得漂亮。拿好门票，去世界树顶端通道的光洞组建戴米安远征。")
        return node
    raise RuntimeError(f"unknown quest file {kind}")


def reject_alias_collision(path: Path) -> None:
    image = load_checked(path, arc.GMS_KEY)
    names = {child.name for child in image.root.children()}
    if SERVER_QUEST_NAME in names and CLIENT_QUEST_NAME in names:
        raise RuntimeError(f"alias collision in {path.name}")
    if SERVER_QUEST_NAME in names:
        raise RuntimeError(f"signed alias {SERVER_QUEST_NAME} exists in client {path.name}")


def upsert_client_quest(path: Path, node: WzSubProperty) -> None:
    reject_alias_collision(path)
    original = path.read_bytes()
    records, _ = arc.raw_record_state(original)
    if (node.name,) in records:
        updated = replace_img_record(original, (node.name,), node, region="GMS").data
        arc.verify_raw_record_scope(original, updated, {(node.name,)}, allow_additions=False)
        parsed = WzImage.from_bytes(updated, key=arc.GMS_KEY, name=path.name)
        parsed.parse()
        if parsed.truncated or parsed.parse_warnings:
            raise RuntimeError(f"replaced quest IMG failed validation: {path}")
        if updated != original:
            arc.atomic_write_bytes(path, updated)
        return
    append_named_records(path, (), [node])


def upsert_server_quest(path: Path, node: WzSubProperty) -> None:
    if not path.exists():
        return
    original = path.read_text(encoding="utf-8")
    fragment = arc.property_to_xml(node, indent=1)
    spans = daily.xml_spans(original.encode("utf-8"))
    if CLIENT_QUEST_NAME in spans and SERVER_QUEST_NAME in spans:
        raise RuntimeError(f"server XML has both quest ids in {path}")
    if SERVER_QUEST_NAME in spans:
        return
    if CLIENT_QUEST_NAME in spans:
        updated = daily.replace_xml_span(original, CLIENT_QUEST_NAME, fragment)
    else:
        updated = arc.append_xml_properties(original, (), [node])
        ET.fromstring(updated)
    if updated != original:
        arc.atomic_write_text(path, updated)


def patch_quest() -> None:
    for name in QUEST_NAMES:
        client_node = build_quest_node(CLIENT_QUEST_NAME, name)
        server_node = build_quest_node(SERVER_QUEST_NAME, name)
        client = ROOT / f"clien/Data/Quest/{name}.img"
        upsert_client_quest(client, client_node)
        for tree in ("wz", "wz-zh-CN"):
            server = ROOT / f"gms-server/{tree}/Quest.wz/{name}.img.xml"
            upsert_server_quest(server, server_node)


def _int_at(root, path: tuple[str, ...]) -> int:
    node = root
    for part in path:
        node = node.child(part)
        if node is None:
            raise RuntimeError(f"missing {'/'.join(path)}")
    return int(node.value)


def patch_boss_skills() -> None:
    for mob_id, edits in SKILL_REMAPS.items():
        client = ROOT / f"clien/Data/Mob/{mob_id}.img"
        original = client.read_bytes()
        patched = original
        image = load_checked(client, arc.GMS_KEY)
        skill_id = _int_at(image.root, ("info", "skill", "2", "skill"))
        if skill_id != 145:
            raise RuntimeError(f"{mob_id} skill index 2 is {skill_id}, expected 145")
        for path, value in sorted(edits):
            if _int_at(image.root, path) == value:
                continue
            before = patched
            patched = arc.mutate_img(
                patched,
                "edit",
                path,
                values={"value": value},
                region="GMS",
            ).data
            arc.verify_raw_record_scope(before, patched, {path}, allow_additions=False)
        if patched != original:
            checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=client.name)
            checked.parse()
            if checked.truncated or checked.parse_warnings:
                raise RuntimeError(f"{mob_id} parse failed after skill remap")
            arc.atomic_write_bytes(client, patched)
        xml = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
        text = xml.read_text(encoding="utf-8")
        updated = text
        for path, value in sorted(edits):
            updated = arc.mutate_xml(updated, "edit", path, kind="Int", values={"value": value})
        if updated != text:
            xml.write_text(updated, encoding="utf-8")


def snapshot() -> dict[str, str]:
    paths = [
        CLIENT_ITEM,
        CLIENT_STRING,
        SERVER_ITEM,
        *SERVER_STRINGS,
        ROOT / "clien/Data/Mob/8880110.img",
        ROOT / "clien/Data/Mob/8880111.img",
        ROOT / "gms-server/wz/Mob.wz/8880110.img.xml",
        ROOT / "gms-server/wz/Mob.wz/8880111.img.xml",
    ]
    for name in QUEST_NAMES:
        paths.append(ROOT / f"clien/Data/Quest/{name}.img")
        paths.append(ROOT / f"gms-server/wz/Quest.wz/{name}.img.xml")
        paths.append(ROOT / f"gms-server/wz-zh-CN/Quest.wz/{name}.img.xml")
    return {str(path.relative_to(ROOT)): sha256_file(path) for path in paths}


def main() -> int:
    patch_boss_skills()
    patch_ticket_item()
    patch_quest()
    first = snapshot()
    patch_boss_skills()
    patch_ticket_item()
    patch_quest()
    second = snapshot()
    if first != second:
        raise RuntimeError("Damien ticket/skill installer is not idempotent")
    print("damien ticket/skill installer ok")
    for path, digest in first.items():
        print(f"{path} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
