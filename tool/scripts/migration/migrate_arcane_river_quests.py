#!/usr/bin/env python3
"""Migrate a legacy-safe Arcane River quest subset and its quest items.

The modern TMS quest records are used as the source of truth for names,
descriptions, NPCs, objectives, and rewards.  Unsupported automatic/scripted
flow is replaced by ordinary v83 NPC accept/complete records.
"""

from __future__ import annotations

import io
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
QUEST_SOURCE = SOURCE / "Quest/QuestData"
BACKUP_ROOT = Path("/private/tmp/arcane-river-quest-backup")

sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from migrate_arcane_river_fields import (  # noqa: E402
    BMS_KEY,
    GMS_KEY,
    CanvasMaterializer,
    clone_property,
    load_image,
    property_to_xml,
)
from wzpy import (  # noqa: E402
    WzImage,
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
)
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


# quest id: (previous quest in the simplified regional chain, fallback exp)
QUESTS: dict[int, tuple[int | None, int]] = {
    34102: (None, 14_713_510),
    34103: (34102, 14_713_510),
    34104: (34103, 14_713_510),
    34105: (34104, 17_656_212),
    34203: (None, 16_000_000),
    34303: (None, 17_776_812),
    34304: (34303, 17_776_812),
    34312: (34304, 17_776_812),
    34313: (34312, 17_776_812),
    34314: (34313, 17_776_812),
    34315: (34314, 17_776_812),
    34474: (None, 23_050_188),
    34250: (None, 25_000_000),
    34252: (34250, 25_000_000),
    34256: (34252, 25_000_000),
    34265: (34256, 25_000_000),
    34568: (None, 30_000_000),
    34572: (34568, 30_000_000),
    34574: (34572, 30_000_000),
    34576: (34574, 30_000_000),
    34578: (34576, 30_000_000),
    34582: (34578, 30_000_000),
    34584: (34582, 30_000_000),
}

QUEST_ITEMS = {
    4034914, 4034915, 4034916, 4034917,
    4034942, 4034979, 4034981, 4034982,
}

AREA_PARENT = {
    272: "消逝的旅途",
    274: "啾啾艾爾蘭",
    276: "拉契爾恩",
    277: "阿爾卡娜",
    278: "魔菈斯",
    279: "艾斯佩拉",
}


def backup(path: Path) -> None:
    if not path.exists():
        return
    destination = BACKUP_ROOT / path.relative_to(ROOT)
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def atomic_write_text(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", prefix=f".{path.name}.", dir=path.parent, delete=False
    ) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), GMS_KEY)


def value(root, path: str, default=None):
    node = root.get(path) if root is not None else None
    return getattr(node, "value", default)


def add_int(parent: WzSubProperty, name: str, number: int) -> None:
    parent.add(WzIntProperty(name, int(number), parent))


def add_string(parent: WzSubProperty, name: str, string: str) -> None:
    parent.add(WzStringProperty(name, str(string), parent))


def objective_entries(source: WzImage, kind: str) -> list[tuple[int, int]]:
    root = source.get(f"Check/1/{kind}")
    if root is None:
        return []
    output = []
    for entry in root.children():
        item_id = value(entry, "id")
        count = value(entry, "count")
        if not isinstance(item_id, int) or not isinstance(count, int) or count <= 0:
            raise RuntimeError(f"invalid {kind} objective in {source.name}/{entry.name}")
        output.append((item_id, count))
    return output


def add_entries(parent: WzSubProperty, name: str, entries: list[tuple[int, int]]) -> None:
    if not entries:
        return
    container = WzSubProperty(name, parent)
    parent.add(container)
    for index, (item_id, count) in enumerate(entries):
        entry = WzSubProperty(str(index), container)
        container.add(entry)
        add_int(entry, "id", item_id)
        add_int(entry, "count", count)
        add_int(entry, "order", index + 1)


def demand_summary(items: list[tuple[int, int]], mobs: list[tuple[int, int]]) -> str:
    parts = [f"#i{item_id}:# #t{item_id}:# #c{item_id}# / {count}" for item_id, count in items]
    parts.extend(f"#o{mob_id}# #r#a{mob_id}# / {count}#k" for mob_id, count in mobs)
    return "\r\n".join(parts)


def build_quest_nodes(quest_id: int, previous: int | None, fallback_exp: int):
    source_path = QUEST_SOURCE / f"{quest_id}.img"
    source = load_image(source_path, BMS_KEY)
    source_info = source.get("QuestInfo")
    if source_info is None:
        raise RuntimeError(f"missing QuestInfo in {source_path}")

    name = value(source_info, "name", f"神秘河任務 {quest_id}")
    area = int(value(source_info, "area", 0))
    start_npc = value(source, "Check/0/npc")
    end_npc = value(source, "Check/1/npc", start_npc)
    if not isinstance(start_npc, int) or not isinstance(end_npc, int):
        raise RuntimeError(f"quest {quest_id} has no compatible start/end NPC")

    items = objective_entries(source, "item")
    mobs = objective_entries(source, "mob")
    if not items and not mobs:
        raise RuntimeError(f"quest {quest_id} has no legacy-safe objective")
    for item_id, _ in items:
        if item_id not in QUEST_ITEMS:
            raise RuntimeError(f"quest {quest_id} depends on unapproved item {item_id}")

    info = WzSubProperty(str(quest_id))
    for index in range(3):
        text = value(source_info, str(index), "")
        if text:
            add_string(info, str(index), text)
    add_int(info, "area", area)
    add_string(info, "name", name)
    add_string(info, "parent", AREA_PARENT.get(area, "神秘河"))
    add_int(info, "order", list(QUESTS).index(quest_id) + 1)
    summary = demand_summary(items, mobs)
    if summary:
        add_string(info, "demandSummary", summary)

    check = WzSubProperty(str(quest_id))
    start = WzSubProperty("0", check)
    complete = WzSubProperty("1", check)
    check.add(start)
    check.add(complete)
    add_int(start, "npc", start_npc)
    add_int(start, "lvmin", max(1, int(value(source, "Check/0/lvmin", 1))))
    if previous is not None:
        prerequisites = WzSubProperty("quest", start)
        start.add(prerequisites)
        entry = WzSubProperty("0", prerequisites)
        prerequisites.add(entry)
        add_int(entry, "id", previous)
        add_int(entry, "state", 2)
        add_int(entry, "order", 1)
    add_int(complete, "npc", end_npc)
    add_int(complete, "order", 1)
    add_entries(complete, "item", items)
    add_entries(complete, "mob", mobs)

    act = WzSubProperty(str(quest_id))
    act.add(WzSubProperty("0", act))
    finish = WzSubProperty("1", act)
    act.add(finish)
    source_exp = value(source, "Act/1/exp")
    add_int(finish, "exp", int(source_exp) if isinstance(source_exp, int) and source_exp > 0 else fallback_exp)
    if items:
        removals = WzSubProperty("item", finish)
        finish.add(removals)
        for index, (item_id, count) in enumerate(items):
            entry = WzSubProperty(str(index), removals)
            removals.add(entry)
            add_int(entry, "id", item_id)
            add_int(entry, "count", -count)

    say = WzSubProperty(str(quest_id))
    accept = WzSubProperty("0", say)
    finish_say = WzSubProperty("1", say)
    say.add(accept)
    say.add(finish_say)
    intro = value(source_info, "0", name)
    progress = value(source_info, "1", intro)
    completed = value(source_info, "2", "辛苦了，這件事總算解決了。")
    add_string(accept, "0", intro)
    yes = WzSubProperty("yes", accept)
    no = WzSubProperty("no", accept)
    accept.add(yes)
    accept.add(no)
    add_string(yes, "0", progress)
    add_string(no, "0", "如果改變心意，再來找我吧。")
    add_string(finish_say, "0", completed)
    finish_yes = WzSubProperty("yes", finish_say)
    finish_say.add(finish_yes)
    add_string(finish_yes, "0", "辛苦了，謝謝你的幫忙。")

    return {"QuestInfo": info, "Check": check, "Act": act, "Say": say}, {
        "id": quest_id,
        "name": name,
        "area": area,
        "start_npc": start_npc,
        "end_npc": end_npc,
        "items": items,
        "mobs": mobs,
    }


def write_client_quest_images(nodes_by_image: dict[str, list[WzSubProperty]]) -> None:
    for image_name, nodes in nodes_by_image.items():
        path = ROOT / f"clien/Data/Quest/{image_name}.img"
        target = load_image(path, GMS_KEY)
        for node in nodes:
            target.root._children.pop(node.name, None)
            target.root.add(node)
        backup(path)
        atomic_write_bytes(path, encode_image_body(target, gms_reader()))


def find_imgdir_block(text: str, node_name: str) -> tuple[int, int]:
    match = re.search(rf'<imgdir\b[^>]*\bname="{re.escape(node_name)}"[^>]*>', text)
    if match is None:
        raise RuntimeError(f"missing XML imgdir {node_name}")
    root_start = match.start()
    depth = 0
    for tag_match in re.finditer(r"</?imgdir\b[^>]*>", text[root_start:]):
        tag = tag_match.group(0)
        if tag.startswith("</"):
            depth -= 1
            if depth == 0:
                return root_start, root_start + tag_match.end()
        elif not tag.endswith("/>"):
            depth += 1
    raise RuntimeError(f"unterminated XML imgdir {node_name}")


def upsert_xml_nodes(path: Path, parent_name: str, nodes: list[WzSubProperty]) -> None:
    text = path.read_text(encoding="utf-8-sig")
    parent_start, parent_end = find_imgdir_block(text, parent_name)
    parent = text[parent_start:parent_end]
    for node in nodes:
        try:
            child_start, child_end = find_imgdir_block(parent, node.name)
            parent = parent[:child_start] + parent[child_end:]
        except RuntimeError:
            pass
    insert_at = parent.rfind("</imgdir>")
    blocks = "\n".join(property_to_xml(node, 1) for node in nodes)
    parent = parent[:insert_at] + ("\n" if not parent[:insert_at].endswith("\n") else "") + blocks + "\n" + parent[insert_at:]
    backup(path)
    atomic_write_text(path, text[:parent_start] + parent + text[parent_end:])


def write_server_quest_xml(nodes_by_image: dict[str, list[WzSubProperty]]) -> None:
    for tree in ("wz", "wz-zh-CN"):
        for image_name, nodes in nodes_by_image.items():
            upsert_xml_nodes(
                ROOT / f"gms-server/{tree}/Quest.wz/{image_name}.img.xml",
                f"{image_name}.img",
                nodes,
            )


def migrate_item_nodes() -> None:
    source_path = SOURCE / "Item/Etc/0403.img"
    source = load_image(source_path, BMS_KEY)
    target_path = ROOT / "clien/Data/Item/Etc/0403.img"
    target = load_image(target_path, GMS_KEY)
    materializer = CanvasMaterializer()
    item_nodes = []
    for item_id in sorted(QUEST_ITEMS):
        node_name = f"{item_id:08d}"
        source_node = source.get(node_name)
        if source_node is None:
            raise RuntimeError(f"missing TMS item node {node_name}")
        cloned = clone_property(source_node, target.root, source, source_path, materializer, node_name)
        target.root._children.pop(node_name, None)
        target.root.add(cloned)
        item_nodes.append(cloned)
    backup(target_path)
    atomic_write_bytes(target_path, encode_image_body(target, gms_reader()))
    upsert_xml_nodes(ROOT / "gms-server/wz/Item.wz/Etc/0403.img.xml", "0403.img", item_nodes)


def migrate_item_strings() -> None:
    source_path = SOURCE / "String/Etc.img"
    source = load_image(source_path, BMS_KEY)
    target_path = ROOT / "clien/Data/String/Etc.img"
    target = load_image(target_path, GMS_KEY)
    source_parent = source.get("Etc")
    target_parent = target.get("Etc")
    if source_parent is None or target_parent is None:
        raise RuntimeError("String/Etc.img has no Etc category")
    materializer = CanvasMaterializer()
    string_nodes = []
    for item_id in sorted(QUEST_ITEMS):
        source_node = source_parent.child(str(item_id))
        if source_node is None:
            raise RuntimeError(f"missing TMS item string {item_id}")
        cloned = clone_property(source_node, target_parent, source, source_path, materializer, str(item_id))
        target_parent._children.pop(str(item_id), None)
        target_parent.add(cloned)
        string_nodes.append(cloned)
    backup(target_path)
    atomic_write_bytes(target_path, encode_image_body(target, gms_reader()))

    for tree in ("wz", "wz-zh-CN"):
        path = ROOT / f"gms-server/{tree}/String.wz/Etc.img.xml"
        upsert_xml_nodes(path, "Etc", string_nodes)


def installed_life_ids() -> tuple[set[int], set[int]]:
    npcs: set[int] = set()
    mobs: set[int] = set()
    for path in (ROOT / "gms-server/wz/Map.wz/Map/Map4").glob("450*.img.xml"):
        map_id = int(path.name.split(".")[0])
        if str(map_id)[:6] not in {"450001", "450002", "450003", "450005", "450006", "450007"}:
            continue
        root = ET.parse(path).getroot()
        life = next((child for child in root if child.tag == "imgdir" and child.get("name") == "life"), None)
        if life is None:
            continue
        for entry in life:
            values = {child.get("name"): child.get("value") for child in entry}
            if not (values.get("id") or "").isdigit():
                continue
            if values.get("type") == "n":
                npcs.add(int(values["id"]))
            elif values.get("type") == "m":
                mobs.add(int(values["id"]))
    return npcs, mobs


def main() -> int:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    nodes_by_image = {name: [] for name in ("QuestInfo", "Check", "Act", "Say")}
    records = []
    for quest_id, (previous, fallback_exp) in QUESTS.items():
        nodes, record = build_quest_nodes(quest_id, previous, fallback_exp)
        records.append(record)
        for image_name, node in nodes.items():
            nodes_by_image[image_name].append(node)

    npcs, mobs = installed_life_ids()
    missing_npcs = sorted({record[key] for record in records for key in ("start_npc", "end_npc")} - npcs)
    missing_mobs = sorted({mob for record in records for mob, _ in record["mobs"]} - mobs)
    if missing_npcs or missing_mobs:
        raise RuntimeError(f"quest closure failed: missing NPCs={missing_npcs}, mobs={missing_mobs}")

    migrate_item_nodes()
    migrate_item_strings()
    write_client_quest_images(nodes_by_image)
    write_server_quest_xml(nodes_by_image)
    print(
        f"Arcane River quests migrated: quests={len(records)}, items={len(QUEST_ITEMS)}, "
        f"NPCs={len({record[key] for record in records for key in ('start_npc', 'end_npc')})}, "
        f"mobs={len({mob for record in records for mob, _ in record['mobs']})}. "
        f"Backups: {BACKUP_ROOT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
