#!/usr/bin/env python3
"""Restore NPC 3003104 daily quests without full client IMG encoding."""

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
from wzpy import WzImage, WzIntProperty, WzStringProperty, WzSubProperty  # noqa: E402


VANISHING_QUEST_IDS = tuple(range(34128, 34151))
REVERSE_CITY_QUEST_IDS = tuple(range(39055, 39064))
TMS_QUEST_IDS = VANISHING_QUEST_IDS + REVERSE_CITY_QUEST_IDS
SIGNED_QUEST_IDS = tuple(quest_id - 65536 for quest_id in TMS_QUEST_IDS)
QUEST_NAMES = ("Act", "Check", "QuestInfo", "Say")
CLIENT_QUESTS = {name: ROOT / f"clien/Data/Quest/{name}.img" for name in QUEST_NAMES}
SERVER_QUESTS = {
    name: ROOT / f"gms-server/wz/Quest.wz/{name}.img.xml" for name in QUEST_NAMES
}
QUEST_SCRIPT_ROOT = ROOT / "gms-server/scripts-zh-CN/quest"

VIRTUAL_MOBS = {8641003: 9101085, 8641006: 9101086}
COLLECTION_QUESTS = {
    34139: (4034922, 50), 34140: (4034923, 50),
    34141: (4034924, 50), 34142: (4034925, 50),
    34143: (4034926, 50), 34144: (4034927, 50),
    34145: (4034928, 50), 34146: (4034929, 50),
    34147: (4034930, 33), 34148: (4034934, 30),
    34149: (4034935, 30), 34150: (4034936, 30),
    39063: (4036709, 50),
}


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


def signed_quest_id(quest_id: int) -> int:
    return quest_id - 65536 if 32767 < quest_id < 65536 else quest_id


def source_int(parent: WzSubProperty, name: str, default: int = 0) -> int:
    child = parent.child(name)
    return default if child is None else int(child.value)


def clone_child(source, name, target, image, source_path):
    child = source.child(name)
    if child is None:
        return None
    cloned = arc.clone_property(
        child, target, image, source_path, arc.CanvasMaterializer(), name
    )
    target.add(cloned)
    return cloned


def build_quest_nodes():
    output = {name: [] for name in QUEST_NAMES}
    descriptions = {}
    for quest_id in TMS_QUEST_IDS:
        source_path = SOURCE / f"Quest/QuestData/{quest_id}.img"
        source = load_checked(source_path, arc.BMS_KEY)
        source_info = source.root.child("QuestInfo")
        source_check = source.root.child("Check")
        source_say = source.root.child("Say")
        if not all(isinstance(node, WzSubProperty) for node in (source_info, source_check, source_say)):
            raise RuntimeError(f"TMS quest structure is incomplete: {quest_id}")
        signed_name = str(signed_quest_id(quest_id))

        info = WzSubProperty(signed_name)
        text = {}
        for name in ("name", "0", "1", "2"):
            field = source_info.child(name)
            if not isinstance(field, WzStringProperty):
                raise RuntimeError(f"TMS QuestInfo field is missing: {quest_id}/{name}")
            text[name] = str(field.value)
            info.add(WzStringProperty(name, text[name], info))
        add_int(info, "area", 272)
        descriptions[quest_id] = text
        output["QuestInfo"].append(info)

        source_start = source_check.child("0")
        source_end = source_check.child("1")
        if not isinstance(source_start, WzSubProperty) or not isinstance(source_end, WzSubProperty):
            raise RuntimeError(f"TMS Check branches are missing: {quest_id}")
        check = WzSubProperty(signed_name)
        start = add_sub(check, "0")
        add_int(start, "npc", source_int(source_start, "npc", 3003104))
        add_int(start, "lvmin", 200)
        if quest_id not in (34128, 34129):
            add_int(start, "interval", 1440)
        prerequisites = source_start.child("quest")
        if isinstance(prerequisites, WzSubProperty):
            quests = add_sub(start, "quest")
            for source_entry in prerequisites.children():
                if not isinstance(source_entry, WzSubProperty):
                    continue
                entry = add_sub(quests, source_entry.name)
                add_int(entry, "id", signed_quest_id(source_int(source_entry, "id")))
                add_int(entry, "state", source_int(source_entry, "state"))

        end = add_sub(check, "1")
        add_int(end, "npc", source_int(source_end, "npc", 3003104))
        for objective_name in ("mob", "item"):
            objective = clone_child(source_end, objective_name, end, source, source_path)
            if objective_name == "mob" and isinstance(objective, WzSubProperty):
                for entry in objective.children():
                    if not isinstance(entry, WzSubProperty):
                        continue
                    mob_id = entry.child("id")
                    if isinstance(mob_id, WzIntProperty):
                        mob_id._value = VIRTUAL_MOBS.get(int(mob_id.value), int(mob_id.value))
        output["Check"].append(check)

        act = WzSubProperty(signed_name)
        add_sub(act, "0")
        act_end = add_sub(act, "1")
        if quest_id != 34128:
            items = add_sub(act_end, "item")
            reward = add_sub(items, "0")
            add_int(reward, "id", 1712001)
            add_int(reward, "count", 2)
            if quest_id in COLLECTION_QUESTS:
                item_id, count = COLLECTION_QUESTS[quest_id]
                removal = add_sub(items, "1")
                add_int(removal, "id", item_id)
                add_int(removal, "count", -count)
        output["Act"].append(act)

        say = arc.clone_property(
            source_say, None, source, source_path, arc.CanvasMaterializer(), signed_name
        )
        if not isinstance(say, WzSubProperty):
            raise RuntimeError(f"TMS Say is invalid: {quest_id}")
        output["Say"].append(say)
    return output, descriptions


def client_quest_nodes(nodes):
    result = copy.deepcopy(nodes)
    for node in result:
        node.name = str(int(node.name) + 65536)
    return result


def tms_descriptions():
    _, descriptions = build_quest_nodes()
    return {
        str(signed_quest_id(quest_id)): [
            WzStringProperty(name, descriptions[quest_id][name])
            for name in ("0", "1", "2")
        ]
        for quest_id in TMS_QUEST_IDS
    }


def append_server_records(path: Path, nodes) -> bool:
    original = path.read_text(encoding="utf-8")
    root = ET.fromstring(original)
    existing = {child.get("name") for child in root if child.tag == "imgdir"}
    additions = [node for node in nodes if node.name not in existing]
    if not additions:
        return False
    updated = arc.append_xml_properties(original, (), additions)
    ET.fromstring(updated)
    arc.atomic_write_text(path, updated)
    return True


def append_client_records(path: Path, nodes) -> bool:
    original = path.read_bytes()
    data = original
    approved = {(node.name,) for node in nodes}
    for node in nodes:
        records, _ = arc.raw_record_state(data)
        if (node.name,) in records:
            continue
        before_name = "34200" if int(node.name) < 39000 else "39064"
        data = arc.insert_property_record_before(data, (), node, before_name)
    arc.verify_raw_record_insert_scope(original, data, approved)
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"generated IMG failed validation: {path}")
    if data == original:
        return False
    arc.atomic_write_bytes(path, data)
    return True


def quest_script(quest_id: int, description) -> str:
    title = description["name"]
    start_text = description["0"]
    end_text = description["2"]
    return (
        f"// 任務 {signed_quest_id(quest_id)} (TMS {quest_id}) - {title}\n"
        "var status = -1;\n\n"
        "function start(mode, type, selection) {\n"
        "    if (mode <= 0) { qm.dispose(); return; }\n"
        "    status++;\n"
        "    if (status == 0) {\n"
        f"        qm.sendYesNo({json.dumps(start_text + chr(13) + chr(10) + chr(13) + chr(10) + '#b接受任務？#k', ensure_ascii=False)});\n"
        "    } else if (status == 1) {\n"
        "        qm.forceStartQuest();\n"
        "        qm.sendOk(\"任務已接受！完成後回來找我吧。\");\n"
        "        qm.dispose();\n"
        "    }\n"
        "}\n\n"
        "function end(mode, type, selection) {\n"
        "    if (mode <= 0) { qm.dispose(); return; }\n"
        "    status++;\n"
        "    if (status == 0) {\n"
        f"        qm.sendYesNo({json.dumps(end_text + chr(13) + chr(10) + chr(13) + chr(10) + '#b完成任務？#k', ensure_ascii=False)});\n"
        "    } else if (status == 1) {\n"
        "        qm.forceCompleteQuest();\n"
        "        qm.sendOk(\"辛苦了！謝謝你的幫忙。\");\n"
        "        qm.dispose();\n"
        "    }\n"
        "}\n"
    )


def write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise RuntimeError(f"refusing to overwrite a differing generated file: {path}")
        return False
    arc.atomic_write_text(path, content)
    return True


def xml_property(element: ET.Element, parent=None):
    name = element.get("name")
    if name is None:
        raise RuntimeError(f"XML property without a name: {element.tag}")
    if element.tag == "imgdir":
        output = WzSubProperty(name, parent)
        for child in element:
            output.add(xml_property(child, output))
        return output
    if element.tag == "int":
        return WzIntProperty(name, int(element.get("value", "0")), parent)
    if element.tag == "string":
        return WzStringProperty(name, element.get("value", ""), parent)
    raise RuntimeError(f"unsupported Quest XML property: {element.tag}/{name}")


def server_quest_nodes(name: str):
    root = ET.parse(SERVER_QUESTS[name]).getroot()
    nodes = []
    for signed_id in map(str, SIGNED_QUEST_IDS):
        element = root.find(f"./imgdir[@name='{signed_id}']")
        if element is None:
            raise RuntimeError(f"server {name} record is missing: {signed_id}")
        node = xml_property(element)
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"invalid server {name} record: {signed_id}")
        nodes.append(node)
    return nodes


def main() -> int:
    changed = []
    quest_nodes, descriptions = build_quest_nodes()
    for name in QUEST_NAMES:
        if append_server_records(SERVER_QUESTS[name], quest_nodes[name]):
            changed.append(SERVER_QUESTS[name])
        if append_client_records(CLIENT_QUESTS[name], client_quest_nodes(quest_nodes[name])):
            changed.append(CLIENT_QUESTS[name])
    for quest_id in TMS_QUEST_IDS:
        script = QUEST_SCRIPT_ROOT / f"{signed_quest_id(quest_id)}.js"
        if write_if_missing(script, quest_script(quest_id, descriptions[quest_id])):
            changed.append(script)

    unique_changed = list(dict.fromkeys(changed))
    print(f"NPC 3003104 daily quests ready: quests={len(TMS_QUEST_IDS)} changed={len(unique_changed)}")
    for path in unique_changed:
        print(f"{path.relative_to(ROOT)} sha256={hashlib.sha256(path.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
