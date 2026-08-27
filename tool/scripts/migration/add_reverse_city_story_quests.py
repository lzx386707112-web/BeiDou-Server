#!/usr/bin/env python3
"""Install the TMS Reverse City story chain as legacy signed quest records."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
)
from wzpy.canvas import decode_canvas  # noqa: E402


TMS_QUEST_IDS = tuple(range(37601, 37621))
SIGNED_QUEST_IDS = tuple(quest_id - 65536 for quest_id in TMS_QUEST_IDS)
QUEST_NAMES = ("Act", "Check", "QuestInfo", "Say")
CLIENT_QUESTS = {
    name: ROOT / f"clien/Data/Quest/{name}.img" for name in QUEST_NAMES
}
SERVER_QUESTS = {
    name: ROOT / f"gms-server/wz/Quest.wz/{name}.img.xml" for name in QUEST_NAMES
}

COLLECTION_QUESTS = {
    37604: (4036631, 20, 8641051),
    37606: (4036632, 20, 8641052),
    37610: (4036633, 20, 8641054),
    37612: (4036634, 20, 8641055),
    37615: (4036635, 20, 8641055),
}
KILL_QUESTS = {
    37608: (8641053, 100),
    37614: (8641056, 100),
    37617: (8641056, 100),
    37619: (8641059, 1),
}
ITEM_IDS = tuple(item_id for item_id, _, _ in COLLECTION_QUESTS.values())

CLIENT_ITEM = ROOT / "clien/Data/Item/Etc/0403.img"
CLIENT_ETC_STRING = ROOT / "clien/Data/String/Etc.img"
SERVER_ITEM = ROOT / "gms-server/wz/Item.wz/Etc/0403.img.xml"
SERVER_ETC_STRINGS = tuple(
    ROOT / f"gms-server/{tree}/String.wz/Etc.img.xml"
    for tree in ("wz", "wz-zh-CN")
)

NPC_ID = 3004651
MOB_ID = 8641059
CLIENT_NPC_STRING = ROOT / "clien/Data/String/Npc.img"
CLIENT_MOB_STRING = ROOT / "clien/Data/String/Mob.img"
SERVER_NPC_STRINGS = tuple(
    ROOT / f"gms-server/{tree}/String.wz/Npc.img.xml"
    for tree in ("wz", "wz-zh-CN")
)
SERVER_MOB_STRINGS = tuple(
    ROOT / f"gms-server/{tree}/String.wz/Mob.img.xml"
    for tree in ("wz", "wz-zh-CN")
)
CLIENT_NPC = ROOT / f"clien/Data/Npc/{NPC_ID:07d}.img"
SERVER_NPC = ROOT / f"gms-server/wz/Npc.wz/{NPC_ID:07d}.img.xml"
CLIENT_MOB = ROOT / f"clien/Data/Mob/{MOB_ID:07d}.img"
SERVER_MOB = ROOT / f"gms-server/wz/Mob.wz/{MOB_ID:07d}.img.xml"

MAP_ID = 450014240
CLIENT_MAP = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
SERVER_MAP = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
DROP_MIGRATION = (
    ROOT
    / "gms-server/src/main/resources/db/migration/"
    "V2.1.64__add_reverse_city_story_quest_drops.sql"
)
QUEST_SCRIPT_ROOT = ROOT / "gms-server/scripts-zh-CN/quest"


def load_checked(path: Path, key) -> WzImage:
    image = arc.load_image(path, key)
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"unsafe IMG {path}: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    return image


def add_sub(parent: WzSubProperty, name: str) -> WzSubProperty:
    child = WzSubProperty(name, parent)
    parent.add(child)
    return child


def add_int(parent: WzSubProperty, name: str, value: int) -> None:
    parent.add(WzIntProperty(name, value, parent))


def add_string(parent: WzSubProperty, name: str, value: str) -> None:
    parent.add(WzStringProperty(name, value, parent))


def signed_quest_id(quest_id: int) -> int:
    return quest_id - 65536 if 32767 < quest_id < 65536 else quest_id


def client_quest_nodes(nodes: list[WzSubProperty]) -> list[WzSubProperty]:
    result = copy.deepcopy(nodes)
    for node in result:
        node.name = str(int(node.name) + 65536)
    return result


def source_value(parent: WzSubProperty, name: str) -> object | None:
    child = parent.child(name)
    return None if child is None else child.value


def build_quest_nodes() -> tuple[dict[str, list[WzSubProperty]], dict[int, dict[str, str]]]:
    output = {name: [] for name in QUEST_NAMES}
    descriptions: dict[int, dict[str, str]] = {}
    for quest_id in TMS_QUEST_IDS:
        source_path = SOURCE / f"Quest/QuestData/{quest_id}.img"
        source = load_checked(source_path, arc.BMS_KEY)
        materializer = arc.CanvasMaterializer()
        signed_name = str(signed_quest_id(quest_id))

        source_info = source.root.child("QuestInfo")
        source_check = source.root.child("Check")
        source_say = source.root.child("Say")
        if not all(
            isinstance(node, WzSubProperty)
            for node in (source_info, source_check, source_say)
        ):
            raise RuntimeError(f"TMS quest structure is incomplete: {quest_id}")

        info = WzSubProperty(signed_name)
        text_fields: dict[str, str] = {}
        for child in source_info.children():
            if child.name not in {"area", "name", "0", "1", "2"}:
                continue
            cloned = arc.clone_property(
                child, info, source, source_path, materializer, child.name
            )
            info.add(cloned)
            if child.name in {"name", "0", "1", "2"}:
                text_fields[child.name] = str(cloned.value)
        if source_value(info, "area") != 273 or "name" not in text_fields:
            raise RuntimeError(f"unexpected Reverse City QuestInfo: {quest_id}")
        descriptions[quest_id] = text_fields
        output["QuestInfo"].append(info)

        check = WzSubProperty(signed_name)
        start = add_sub(check, "0")
        source_start = source_check.child("0")
        source_end = source_check.child("1")
        if not isinstance(source_start, WzSubProperty) or not isinstance(
            source_end, WzSubProperty
        ):
            raise RuntimeError(f"TMS Check branches are missing: {quest_id}")
        add_int(start, "lvmin", 205)
        start_npc = int(source_value(source_start, "npc") or 0)
        if quest_id == 37602:
            # The modern auto-start scene begins outside Reverse City. Keep the
            # legacy chain continuous at the NPC that completed 37601.
            start_npc = 3004603
        if not start_npc:
            raise RuntimeError(f"TMS start NPC is missing: {quest_id}")
        add_int(start, "npc", start_npc)
        add_string(start, "startscript", f"q{quest_id}s")
        source_prereqs = source_start.child("quest")
        if isinstance(source_prereqs, WzSubProperty):
            prereqs = add_sub(start, "quest")
            for source_entry in source_prereqs.children():
                if not isinstance(source_entry, WzSubProperty):
                    continue
                entry = add_sub(prereqs, source_entry.name)
                for field in source_entry.children():
                    value = int(field.value)
                    if field.name == "id":
                        value = signed_quest_id(value)
                    add_int(entry, field.name, value)

        end = add_sub(check, "1")
        add_int(end, "order", int(source_value(source_end, "order") or 1))
        end_npc = int(source_value(source_end, "npc") or 0)
        if not end_npc:
            raise RuntimeError(f"TMS end NPC is missing: {quest_id}")
        add_int(end, "npc", end_npc)
        add_string(end, "endscript", f"q{quest_id}e")
        for objective_name in ("item", "mob"):
            objective = source_end.child(objective_name)
            if isinstance(objective, WzSubProperty):
                end.add(
                    arc.clone_property(
                        objective,
                        end,
                        source,
                        source_path,
                        materializer,
                        objective_name,
                    )
                )
        if quest_id == 37619:
            mobs = add_sub(end, "mob")
            mob = add_sub(mobs, "0")
            add_int(mob, "id", MOB_ID)
            add_int(mob, "count", 1)
            add_int(mob, "order", 1)
        output["Check"].append(check)

        act = WzSubProperty(signed_name)
        add_sub(act, "0")
        act_end = add_sub(act, "1")
        collection = COLLECTION_QUESTS.get(quest_id)
        if collection is not None:
            item_id, count, _ = collection
            items = add_sub(act_end, "item")
            item = add_sub(items, "0")
            add_int(item, "id", item_id)
            add_int(item, "count", -count)
        output["Act"].append(act)

        say = arc.clone_property(
            source_say, None, source, source_path, materializer, signed_name
        )
        if not isinstance(say, WzSubProperty):
            raise RuntimeError(f"TMS Say is not a property tree: {quest_id}")
        output["Say"].append(say)

    return output, descriptions


def build_item_nodes() -> tuple[list[WzSubProperty], list[WzSubProperty]]:
    item_source_path = SOURCE / "Item/Etc/0403.img"
    string_source_path = SOURCE / "String/Etc.img"
    item_source = load_checked(item_source_path, arc.BMS_KEY)
    string_source = load_checked(string_source_path, arc.BMS_KEY)
    string_parent = string_source.root.child("Etc")
    if not isinstance(string_parent, WzSubProperty):
        raise RuntimeError("TMS String/Etc.img has no Etc parent")

    materializer = arc.CanvasMaterializer()
    item_nodes: list[WzSubProperty] = []
    string_nodes: list[WzSubProperty] = []
    for item_id in ITEM_IDS:
        item_name = f"0{item_id}"
        source_item = item_source.root.child(item_name)
        source_string = string_parent.child(str(item_id))
        if not isinstance(source_item, WzSubProperty) or not isinstance(
            source_string, WzSubProperty
        ):
            raise RuntimeError(f"TMS story item resource is missing: {item_id}")
        item = arc.clone_property(
            source_item,
            None,
            item_source,
            item_source_path,
            materializer,
            item_name,
        )
        if not isinstance(item, WzSubProperty):
            raise RuntimeError(f"invalid item record: {item_id}")
        for canvas_name in ("icon", "iconRaw"):
            canvas = item.get(f"info/{canvas_name}")
            if not isinstance(canvas, WzCanvasProperty):
                raise RuntimeError(f"missing item Canvas: {item_id}/{canvas_name}")
            if (canvas.format, canvas.format2) != (1, 0):
                raise RuntimeError(f"incompatible item Canvas: {item_id}/{canvas_name}")
            bitmap = decode_canvas(canvas, region="GMS")
            if bitmap.width * bitmap.height <= 1 or not bitmap.getbbox():
                raise RuntimeError(f"empty item Canvas: {item_id}/{canvas_name}")
        item_nodes.append(item)
        string_nodes.append(
            arc.clone_property(
                source_string,
                None,
                string_source,
                string_source_path,
                arc.CanvasMaterializer(),
                str(item_id),
            )
        )
    return item_nodes, string_nodes


def build_string_node(source_name: str, record_name: str) -> WzSubProperty:
    source_path = SOURCE / f"String/{source_name}.img"
    source = load_checked(source_path, arc.BMS_KEY)
    record = source.root.child(record_name)
    if not isinstance(record, WzSubProperty):
        raise RuntimeError(
            f"TMS String/{source_name}.img record is missing: {record_name}"
        )
    cloned = arc.clone_property(
        record,
        None,
        source,
        source_path,
        arc.CanvasMaterializer(),
        record_name,
    )
    if not isinstance(cloned, WzSubProperty):
        raise RuntimeError(f"invalid String/{source_name}.img record: {record_name}")
    return cloned


def append_client_records(
    path: Path,
    parent_path: tuple[str, ...],
    nodes: list[WzSubProperty],
    before_names: tuple[str, ...],
) -> bool:
    original = path.read_bytes()
    data = original
    approved = {(*parent_path, node.name) for node in nodes}
    for node in nodes:
        records, orders = arc.raw_record_state(data)
        if (*parent_path, node.name) not in records:
            before_name = next(
                (name for name in before_names if name in orders[parent_path]),
                None,
            )
            if before_name is None and before_names:
                raise RuntimeError(
                    f"missing insertion anchor in {path}: {before_names}"
                )
            if before_name is None:
                data = arc.append_property_record(data, parent_path, node)
            else:
                data = arc.insert_property_record_before(
                    data, parent_path, node, before_name
                )
    arc.verify_raw_record_insert_scope(original, data, approved)
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"generated IMG failed validation: {path}")
    if data == original:
        return False
    arc.atomic_write_bytes(path, data)
    return True


def append_server_records(
    path: Path, parent_path: tuple[str, ...], nodes: list[WzSubProperty]
) -> bool:
    original = path.read_text(encoding="utf-8")
    parent = ET.fromstring(original)
    for part in parent_path:
        parent = parent.find(f"./imgdir[@name='{part}']")
        if parent is None:
            raise RuntimeError(f"missing XML parent {'/'.join(parent_path)} in {path}")
    existing = {child.get("name") for child in parent}
    additions = [node for node in nodes if node.name not in existing]
    if not additions:
        return False
    updated = arc.append_xml_properties(original, parent_path, additions)
    ET.fromstring(updated)
    arc.atomic_write_text(path, updated)
    return True


def ensure_client_string(
    path: Path, parent_path: tuple[str, ...], name: str, value: str
) -> bool:
    original = path.read_bytes()
    image = load_checked(path, arc.GMS_KEY)
    current = image.root.get("/".join((*parent_path, name)))
    if isinstance(current, WzStringProperty) and str(current.value) == value:
        return False
    operation = "add" if current is None else "edit"
    kwargs = {"values": {"value": value}, "region": "GMS"}
    if operation == "add":
        kwargs.update({"name": name, "kind": "String"})
        result = arc.mutate_img(original, operation, parent_path, **kwargs).data
    elif isinstance(current, WzStringProperty):
        result = arc.mutate_img(original, operation, (*parent_path, name), **kwargs).data
    else:
        raise RuntimeError(f"conflicting client property: {'/'.join((*parent_path, name))}")
    approved = {(*parent_path, name)}
    arc.verify_raw_record_scope(
        original, result, approved, allow_additions=operation == "add"
    )
    arc.atomic_write_bytes(path, result)
    return True


def ensure_server_string(
    path: Path, parent_path: tuple[str, ...], name: str, value: str
) -> bool:
    original = path.read_text(encoding="utf-8")
    root = ET.fromstring(original)
    parent = root
    for part in parent_path:
        parent = parent.find(f"./imgdir[@name='{part}']")
        if parent is None:
            raise RuntimeError(f"missing XML parent {'/'.join(parent_path)} in {path}")
    current = parent.find(f"./string[@name='{name}']")
    if current is not None and current.get("value", "") == value:
        return False
    if current is None:
        updated = arc.mutate_xml(
            original,
            "add",
            parent_path,
            name=name,
            kind="String",
            values={"value": value},
        )
    elif current.tag == "string":
        updated = arc.mutate_xml(
            original, "edit", (*parent_path, name), values={"value": value}
        )
    else:
        raise RuntimeError(f"conflicting server property: {'/'.join((*parent_path, name))}")
    ET.fromstring(updated)
    arc.atomic_write_text(path, updated)
    return True


def life_node(
    name: str, life_type: str, life_id: int, x: int, rx0: int, rx1: int
) -> WzSubProperty:
    node = WzSubProperty(name)
    add_string(node, "type", life_type)
    add_string(node, "id", str(life_id))
    add_int(node, "x", x)
    add_int(node, "y", -37)
    add_int(node, "mobTime", 0)
    add_int(node, "f", 0)
    add_int(node, "hide", 0)
    add_int(node, "fh", 1)
    add_int(node, "cy", -33)
    add_int(node, "rx0", rx0)
    add_int(node, "rx1", rx1)
    return node


def quest_script(quest_id: int, descriptions: dict[str, str]) -> str:
    title = descriptions["name"]
    start_text = descriptions.get("0", title)
    progress_text = descriptions.get("1", "請依照任務指示前進。")
    end_text = descriptions.get("2", "任務已完成。")
    collection = COLLECTION_QUESTS.get(quest_id)
    item_guard = ""
    item_remove = ""
    if collection is not None:
        item_id, count, _ = collection
        item_guard = (
            f"        if (!qm.haveItem({item_id}, {count})) {{\n"
            f"            qm.sendOk(\"還需要#i{item_id}:# #t{item_id}:# {count}個。\");\n"
            "            qm.dispose();\n"
            "            return;\n"
            "        }\n"
        )
        item_remove = f"        qm.gainItem({item_id}, -{count});\n"
    final_warp = quest_id == 37619
    completion_tail = (
        "        qm.sendOk(" + json.dumps(end_text, ensure_ascii=False) + ");\n"
        + ("    } else if (status == 2) {\n        qm.warp(450014050, 0);\n        qm.dispose();\n" if final_warp else "        qm.dispose();\n")
    )
    return (
        f"// {title} (TMS {quest_id})\n"
        "var status = -1;\n\n"
        "function start(mode, type, selection) {\n"
        "    if (mode <= 0) { qm.dispose(); return; }\n"
        "    status++;\n"
        "    if (status == 0) {\n"
        f"        qm.sendYesNo({json.dumps(start_text + chr(13) + chr(10) + chr(13) + chr(10) + '#b接受任務？#k', ensure_ascii=False)});\n"
        "    } else if (status == 1) {\n"
        "        qm.forceStartQuest();\n"
        f"        qm.sendOk({json.dumps(progress_text, ensure_ascii=False)});\n"
        "        qm.dispose();\n"
        "    }\n"
        "}\n\n"
        "function end(mode, type, selection) {\n"
        "    if (mode <= 0) { qm.dispose(); return; }\n"
        "    status++;\n"
        "    if (status == 0) {\n"
        + item_guard
        + f"        qm.sendYesNo({json.dumps(end_text + chr(13) + chr(10) + chr(13) + chr(10) + '#b完成任務？#k', ensure_ascii=False)});\n"
        "    } else if (status == 1) {\n"
        + item_remove
        + "        qm.forceCompleteQuest();\n"
        + completion_tail
        + "    }\n"
        "}\n"
    )


def write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise RuntimeError(f"refusing to overwrite a differing generated file: {path}")
        return False
    arc.atomic_write_text(path, content)
    return True


def drop_sql() -> str:
    rows = [
        (mob_id, item_id, signed_quest_id(quest_id))
        for quest_id, (item_id, _, mob_id) in COLLECTION_QUESTS.items()
    ]
    values = ",\n".join(
        f"({mob_id}, {item_id}, 1, 1, {quest_id}, 500000)"
        for mob_id, item_id, quest_id in rows
    )
    return (
        "-- Reverse City story collection drops from TMS quests 37604, 37606,\n"
        "-- 37610, 37612 and 37615. Chance uses the existing Arcane River rate.\n"
        "INSERT INTO `drop_data`\n"
        "    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`) VALUES\n"
        f"{values}\n"
        "ON DUPLICATE KEY UPDATE\n"
        "    `minimum_quantity` = VALUES(`minimum_quantity`),\n"
        "    `maximum_quantity` = VALUES(`maximum_quantity`),\n"
        "    `questid` = VALUES(`questid`),\n"
        "    `chance` = VALUES(`chance`);\n"
    )


def audit_visible_resource(path: Path) -> None:
    image = load_checked(path, arc.GMS_KEY)
    canvas_count = 0
    visible_count = 0

    def visit(parent: WzSubProperty | WzCanvasProperty) -> None:
        nonlocal canvas_count, visible_count
        for child in parent.children():
            if isinstance(child, WzCanvasProperty):
                canvas_count += 1
                if (child.format, child.format2) != (1, 0):
                    raise RuntimeError(f"incompatible Canvas in {path}: {child.name}")
                bitmap = decode_canvas(child, region="GMS")
                if bitmap.width * bitmap.height > 1 and bitmap.getbbox():
                    visible_count += 1
            if isinstance(child, (WzSubProperty, WzCanvasProperty)):
                visit(child)

    visit(image.root)
    if not canvas_count or not visible_count:
        raise RuntimeError(f"resource has no visible Canvas: {path}")


def main() -> int:
    changed: list[Path] = []
    quest_nodes, descriptions = build_quest_nodes()
    client_quests = {
        name: client_quest_nodes(nodes) for name, nodes in quest_nodes.items()
    }
    item_nodes, item_strings = build_item_nodes()
    npc_string = build_string_node("Npc", str(NPC_ID))
    mob_string = build_string_node("Mob", str(MOB_ID))

    for name in QUEST_NAMES:
        if append_server_records(SERVER_QUESTS[name], (), quest_nodes[name]):
            changed.append(SERVER_QUESTS[name])
        if append_client_records(
            CLIENT_QUESTS[name], (), client_quests[name], ("37701",)
        ):
            changed.append(CLIENT_QUESTS[name])
    for quest_id, signed_id in zip(TMS_QUEST_IDS, SIGNED_QUEST_IDS):
        for branch, field, suffix in (
            ("0", "startscript", "s"),
            ("1", "endscript", "e"),
        ):
            value = f"q{quest_id}{suffix}"
            client_parent = (str(quest_id), branch)
            server_parent = (str(signed_id), branch)
            if ensure_client_string(
                CLIENT_QUESTS["Check"], client_parent, field, value
            ):
                changed.append(CLIENT_QUESTS["Check"])
            if ensure_server_string(
                SERVER_QUESTS["Check"], server_parent, field, value
            ):
                changed.append(SERVER_QUESTS["Check"])

    if append_client_records(
        CLIENT_ITEM, (), item_nodes, ("04036709", "04036710")
    ):
        changed.append(CLIENT_ITEM)
    if append_client_records(
        CLIENT_ETC_STRING,
        ("Etc",),
        item_strings,
        ("4036709", "4036710"),
    ):
        changed.append(CLIENT_ETC_STRING)
    if append_server_records(SERVER_ITEM, (), item_nodes):
        changed.append(SERVER_ITEM)
    for path in SERVER_ETC_STRINGS:
        if append_server_records(path, ("Etc",), item_strings):
            changed.append(path)

    if append_client_records(
        CLIENT_NPC_STRING, (), [npc_string], ("3004700",)
    ):
        changed.append(CLIENT_NPC_STRING)
    if append_client_records(
        CLIENT_MOB_STRING, (), [mob_string], ("8641066",)
    ):
        changed.append(CLIENT_MOB_STRING)
    for path in SERVER_NPC_STRINGS:
        if append_server_records(path, (), [npc_string]):
            changed.append(path)
    for path in SERVER_MOB_STRINGS:
        if append_server_records(path, (), [mob_string]):
            changed.append(path)

    resource_paths = (CLIENT_NPC, SERVER_NPC, CLIENT_MOB, SERVER_MOB)
    missing_before = {path for path in resource_paths if not path.exists()}
    arc.migrate_one_npc(NPC_ID)
    arc.migrate_one_mob(MOB_ID)
    changed.extend(path for path in resource_paths if path in missing_before)
    audit_visible_resource(CLIENT_NPC)
    audit_visible_resource(CLIENT_MOB)

    life_nodes = [
        life_node("1", "n", NPC_ID, -140, -190, -90),
        life_node("2", "m", MOB_ID, 180, 80, 280),
    ]
    if append_client_records(CLIENT_MAP, ("life",), life_nodes, ()):
        changed.append(CLIENT_MAP)
    if append_server_records(SERVER_MAP, ("life",), life_nodes):
        changed.append(SERVER_MAP)

    for quest_id in TMS_QUEST_IDS:
        script = QUEST_SCRIPT_ROOT / f"{signed_quest_id(quest_id)}.js"
        if write_if_missing(script, quest_script(quest_id, descriptions[quest_id])):
            changed.append(script)
    if write_if_missing(DROP_MIGRATION, drop_sql()):
        changed.append(DROP_MIGRATION)

    unique_changed = list(dict.fromkeys(changed))
    print(
        f"Reverse City story ready: quests={len(TMS_QUEST_IDS)} "
        f"items={len(ITEM_IDS)} changed={len(unique_changed)}"
    )
    for path in unique_changed:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{path.relative_to(ROOT)} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
