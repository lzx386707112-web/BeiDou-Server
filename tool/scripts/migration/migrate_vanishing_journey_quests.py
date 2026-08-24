#!/usr/bin/env python3
"""Install the complete legacy-safe Vanishing Journey quest chain.

The v83 client indexes Quest IMG records by the positive decimal names
34100-34120, while its packets and this server's quest model use the
bit-identical signed forms -31436 through -31416.  Existing IMG files are
changed only at raw property-record granularity; no full IMG serialization is
used.
"""

from __future__ import annotations

import hashlib
import re
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
QUEST_SOURCE = SOURCE / "Quest/QuestData"

sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

from migrate_arcane_river_fields import (  # noqa: E402
    BMS_KEY,
    GMS_KEY,
    CanvasMaterializer,
    clone_property,
    load_image,
    property_to_xml,
)
from migrate_karing_later_stages import encode_record, locate_records  # noqa: E402
from wzpy import WzImage, WzIntProperty, WzStringProperty, WzSubProperty  # noqa: E402
from wzpy.writer import encode_compressed_int  # noqa: E402


SOURCE_QUEST_IDS = tuple(range(34100, 34121))
LEGACY_QUEST_IDS = tuple(quest_id - 65536 for quest_id in SOURCE_QUEST_IDS)
OBSOLETE_POSITIVE_IDS = (34102, 34103, 34104, 34105)
QUEST_IMAGE_NAMES = ("QuestInfo", "Check", "Act", "Say")

QUEST_ITEMS = {
    4034914,
    4034915,
    4034916,
    4034917,
    4034918,
    4034919,
    4034920,
    4034921,
    4034937,
    4034938,
}

# Script-only or missing NPC endpoints are projected onto installed NPCs on
# the same route.  Every other quest keeps its original TMS start/end NPC.
NPC_PROJECTION = {
    34107: (3003110, 3003110),
    34108: (3003125, 3003125),
    34109: (3003125, 3003134),
    34113: (3003125, 3003125),
    34115: (3003127, 3003128),
    34120: (3003143, 3003143),
}

# The modern Arma boss (8641010) is not installed.  Map 450001230 contains
# its compatible legacy substitute, Arma's Henchman (8641012).
MOB_PROJECTION = {34119: [(8641012, 30)]}
EXP_PROJECTION = {34119: 17_656_212, 34120: 17_656_212}
TEXT_PROJECTION = {
    34119: {
        "name": "[消逝的旅途]擊退亞勒瑪的部下",
        "0": "亞勒瑪派出大量部下阻擋去路。擊退牠們，逃離安息的洞穴吧。",
        "1": "前往安息洞穴深處，擊退30隻亞勒瑪部下。",
        "2": "總算擊退了亞勒瑪的部下。帶著卡歐離開安息的洞穴吧。",
    },
    34120: {
        "0": "卡歐離開前留下了一股溫暖的力量。",
        "1": "觸碰卡歐留下的力量，完成消逝的旅途。",
        "2": "卡歐留下的力量融入了身體。消逝的旅途到此告一段落。",
    },
}


@dataclass(frozen=True)
class QuestRecord:
    source_id: int
    legacy_id: int
    start_npc: int
    end_npc: int
    items: tuple[tuple[int, int], ...]
    mobs: tuple[tuple[int, int], ...]


def signed_quest_id(source_id: int) -> int:
    if not 32768 <= source_id <= 65535:
        raise ValueError(f"quest ID is not a signed-16 projection: {source_id}")
    return source_id - 65536


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
        entry_id = value(entry, "id")
        count = value(entry, "count")
        if not isinstance(entry_id, int) or not isinstance(count, int) or count <= 0:
            raise RuntimeError(f"invalid {kind} objective in {source.name}/{entry.name}")
        output.append((entry_id, count))
    return output


def add_entries(parent: WzSubProperty, name: str, entries: list[tuple[int, int]]) -> None:
    if not entries:
        return
    container = WzSubProperty(name, parent)
    parent.add(container)
    for index, (entry_id, count) in enumerate(entries):
        entry = WzSubProperty(str(index), container)
        container.add(entry)
        add_int(entry, "id", entry_id)
        add_int(entry, "count", count)
        add_int(entry, "order", index + 1)


def demand_summary(items: list[tuple[int, int]], mobs: list[tuple[int, int]]) -> str:
    parts = [f"#i{item_id}:# #t{item_id}:# #c{item_id}# / {count}" for item_id, count in items]
    parts.extend(f"#o{mob_id}# #r#a{mob_id}# / {count}#k" for mob_id, count in mobs)
    return "\r\n".join(parts)


def quest_npcs(source: WzImage, source_id: int) -> tuple[int, int]:
    if source_id in NPC_PROJECTION:
        return NPC_PROJECTION[source_id]
    start_npc = value(source, "Check/0/npc")
    end_npc = value(source, "Check/1/npc", start_npc)
    if not isinstance(start_npc, int) or not isinstance(end_npc, int):
        raise RuntimeError(f"quest {source_id} has no compatible start/end NPC")
    return start_npc, end_npc


def source_text(source_info: WzSubProperty, source_id: int, key: str, default: str) -> str:
    projected = TEXT_PROJECTION.get(source_id, {}).get(key)
    return str(projected if projected is not None else value(source_info, key, default))


def build_quest_nodes(source_id: int, order: int, *, signed_ids: bool = True):
    legacy_id = signed_quest_id(source_id)
    target_id = legacy_id if signed_ids else source_id
    source_path = QUEST_SOURCE / f"{source_id}.img"
    source = load_image(source_path, BMS_KEY)
    source_info = source.get("QuestInfo")
    if not isinstance(source_info, WzSubProperty):
        raise RuntimeError(f"missing QuestInfo in {source_path}")

    start_npc, end_npc = quest_npcs(source, source_id)
    items = objective_entries(source, "item")
    mobs = list(MOB_PROJECTION.get(source_id, objective_entries(source, "mob")))
    unknown_items = {item_id for item_id, _ in items} - QUEST_ITEMS
    if unknown_items:
        raise RuntimeError(f"quest {source_id} uses unapproved items {sorted(unknown_items)}")

    name = source_text(source_info, source_id, "name", f"消逝的旅途 {source_id}")
    intro = source_text(source_info, source_id, "0", name)
    progress = source_text(source_info, source_id, "1", intro)
    completed = source_text(source_info, source_id, "2", "這件事總算完成了。")

    info = WzSubProperty(str(target_id))
    add_string(info, "0", intro)
    add_string(info, "1", progress)
    add_string(info, "2", completed)
    add_int(info, "area", 272)
    add_string(info, "name", name)
    add_string(info, "parent", "消逝的旅途")
    add_int(info, "order", order)
    summary = demand_summary(items, mobs)
    if summary:
        add_string(info, "demandSummary", summary)

    check = WzSubProperty(str(target_id))
    start = WzSubProperty("0", check)
    finish = WzSubProperty("1", check)
    check.add(start)
    check.add(finish)
    add_int(start, "npc", start_npc)
    add_int(start, "lvmin", max(1, int(value(source, "Check/0/lvmin", 200))))
    if source_id != SOURCE_QUEST_IDS[0]:
        prerequisites = WzSubProperty("quest", start)
        prerequisite = WzSubProperty("0", prerequisites)
        start.add(prerequisites)
        prerequisites.add(prerequisite)
        prerequisite_id = signed_quest_id(source_id - 1) if signed_ids else source_id - 1
        add_int(prerequisite, "id", prerequisite_id)
        add_int(prerequisite, "state", 2)
        add_int(prerequisite, "order", 1)
    add_int(finish, "npc", end_npc)
    add_int(finish, "order", 1)
    add_entries(finish, "item", items)
    add_entries(finish, "mob", mobs)

    act = WzSubProperty(str(target_id))
    act.add(WzSubProperty("0", act))
    reward = WzSubProperty("1", act)
    act.add(reward)
    source_exp = value(source, "Act/1/exp")
    exp = EXP_PROJECTION.get(
        source_id,
        int(source_exp) if isinstance(source_exp, int) and source_exp > 0 else 5_885_404,
    )
    add_int(reward, "exp", exp)
    if items:
        removals = WzSubProperty("item", reward)
        reward.add(removals)
        for index, (item_id, count) in enumerate(items):
            removal = WzSubProperty(str(index), removals)
            removals.add(removal)
            add_int(removal, "id", item_id)
            add_int(removal, "count", -count)

    say = WzSubProperty(str(target_id))
    accept = WzSubProperty("0", say)
    complete = WzSubProperty("1", say)
    say.add(accept)
    say.add(complete)
    add_string(accept, "0", intro)
    yes = WzSubProperty("yes", accept)
    no = WzSubProperty("no", accept)
    accept.add(yes)
    accept.add(no)
    add_string(yes, "0", progress)
    add_string(no, "0", "如果改變心意，再來找我吧。")
    add_string(complete, "0", completed)
    complete_yes = WzSubProperty("yes", complete)
    complete.add(complete_yes)
    add_string(complete_yes, "0", "辛苦了，謝謝你的幫忙。")

    return {"QuestInfo": info, "Check": check, "Act": act, "Say": say}, QuestRecord(
        source_id=source_id,
        legacy_id=legacy_id,
        start_npc=start_npc,
        end_npc=end_npc,
        items=tuple(items),
        mobs=tuple(mobs),
    )


def atomic_write_bytes(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def atomic_write_text(path: Path, data: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", prefix=f".{path.name}.", dir=path.parent, delete=False
    ) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def parse_image_bytes(path: Path, data: bytes) -> WzImage:
    image = WzImage.from_bytes(data, key=GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"malformed IMG {path}: {image.parse_warnings}")
    return image


def patch_raw_records(
    path: Path,
    parent_path: tuple[str, ...],
    nodes: list[WzSubProperty],
    remove_names: tuple[str, ...] = (),
    raw_replacements: dict[str, bytes] | None = None,
    append_order: tuple[str, ...] = (),
) -> bool:
    original = path.read_bytes()
    image = parse_image_bytes(path, original)
    size_offsets, count_offset, count_end, names, spans, records_end = locate_records(
        image, original, parent_path
    )
    raw_before = {name: original[start:end] for name, (start, end) in zip(names, spans)}
    replacements = {node.name: encode_record(node, image) for node in nodes}
    replacements.update(raw_replacements or {})
    remove = set(remove_names)

    next_names = [name for name in names if name not in remove]
    ordered_insertions = append_order or tuple(replacements)
    next_names.extend(name for name in ordered_insertions if name not in next_names)
    if len(next_names) != len(set(next_names)):
        raise RuntimeError(f"duplicate record name while patching {path}")

    records_start = spans[0][0] if spans else records_end
    rebuilt = b"".join(
        replacements[name] if name in replacements else raw_before[name]
        for name in next_names
    )
    new_count = encode_compressed_int(len(next_names))
    if len(new_count) != count_end - count_offset:
        raise RuntimeError(f"property-count encoding changed width in {path}")

    updated = bytearray(original[:records_start] + rebuilt + original[records_end:])
    updated[count_offset:count_end] = new_count
    delta = len(updated) - len(original)
    for size_offset in size_offsets:
        old_size = struct.unpack_from("<I", original, size_offset)[0]
        struct.pack_into("<I", updated, size_offset, old_size + delta)
    result = bytes(updated)

    verified = parse_image_bytes(path, result)
    _, _, _, verified_names, verified_spans, _ = locate_records(
        verified, result, parent_path
    )
    if verified_names != tuple(next_names):
        raise RuntimeError(f"record order changed unexpectedly in {path}")
    raw_after = {
        name: result[start:end] for name, (start, end) in zip(verified_names, verified_spans)
    }
    approved = set(replacements) | remove
    for name, record in raw_before.items():
        if name not in approved and raw_after.get(name) != record:
            raise RuntimeError(f"unapproved raw record changed in {path}: {name}")
    for name, record in replacements.items():
        if raw_after.get(name) != record:
            raise RuntimeError(f"replacement record mismatch in {path}: {name}")
    if any(name in raw_after for name in remove):
        raise RuntimeError(f"obsolete record survived in {path}")

    if result != original:
        atomic_write_bytes(path, result)
        return True
    return False


def git_baseline_records(path: Path, names: tuple[str, ...]) -> dict[str, bytes]:
    relative = path.relative_to(ROOT).as_posix()
    baseline = subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    image = parse_image_bytes(path, baseline)
    _, _, _, baseline_names, spans, _ = locate_records(image, baseline, ())
    records = {
        name: baseline[start:end]
        for name, (start, end) in zip(baseline_names, spans)
        if name in names
    }
    missing = set(names) - records.keys()
    if missing:
        raise RuntimeError(f"working Git baseline lacks Quest records {sorted(missing)} in {path}")
    return records


def find_imgdir_block(text: str, node_name: str) -> tuple[int, int] | None:
    match = re.search(rf'<imgdir\b[^>]*\bname="{re.escape(node_name)}"[^>]*>', text)
    if match is None:
        return None
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


def patch_xml_records(
    path: Path,
    parent_name: str,
    nodes: list[WzSubProperty],
    remove_names: tuple[str, ...] = (),
) -> bool:
    original = path.read_text(encoding="utf-8-sig")
    parent_span = find_imgdir_block(original, parent_name)
    if parent_span is None:
        raise RuntimeError(f"missing XML parent {parent_name} in {path}")
    parent_start, parent_end = parent_span
    parent = original[parent_start:parent_end]

    for name in remove_names:
        span = find_imgdir_block(parent, name)
        if span is not None:
            parent = parent[: span[0]] + parent[span[1] :]

    for node in nodes:
        block = property_to_xml(node, 1)
        span = find_imgdir_block(parent, node.name)
        if span is None:
            insert_at = parent.rfind("</imgdir>")
            separator = "" if parent[:insert_at].endswith("\n") else "\n"
            parent = parent[:insert_at] + separator + block + "\n" + parent[insert_at:]
        else:
            line_start = parent.rfind("\n", 0, span[0]) + 1
            replace_start = line_start if not parent[line_start : span[0]].strip() else span[0]
            parent = parent[:replace_start] + block + parent[span[1] :]

    result = original[:parent_start] + parent + original[parent_end:]
    ET.fromstring(result)
    if result != original:
        atomic_write_text(path, result)
        return True
    return False


def installed_life_ids() -> tuple[set[int], set[int]]:
    npcs: set[int] = set()
    mobs: set[int] = set()
    for path in (ROOT / "gms-server/wz/Map.wz/Map/Map4").glob("450001*.img.xml"):
        root = ET.parse(path).getroot()
        for entry in root.findall("./imgdir[@name='life']/imgdir"):
            values = {child.get("name"): child.get("value") for child in entry}
            life_id = values.get("id", "")
            if not life_id.isdigit():
                continue
            if values.get("type") == "n":
                npcs.add(int(life_id))
            elif values.get("type") == "m":
                mobs.add(int(life_id))
    return npcs, mobs


def build_item_nodes() -> tuple[list[WzSubProperty], list[WzSubProperty]]:
    item_source_path = SOURCE / "Item/Etc/0403.img"
    string_source_path = SOURCE / "String/Etc.img"
    item_source = load_image(item_source_path, BMS_KEY)
    string_source = load_image(string_source_path, BMS_KEY)
    string_parent = string_source.get("Etc")
    if not isinstance(string_parent, WzSubProperty):
        raise RuntimeError("TMS String/Etc.img has no Etc parent")

    item_materializer = CanvasMaterializer()
    string_materializer = CanvasMaterializer()
    item_nodes: list[WzSubProperty] = []
    string_nodes: list[WzSubProperty] = []
    for item_id in sorted(QUEST_ITEMS):
        item_name = f"0{item_id}"
        source_item = item_source.get(item_name)
        source_string = string_parent.child(str(item_id))
        if source_item is None or source_string is None:
            raise RuntimeError(f"missing TMS quest item resource {item_id}")
        item_nodes.append(
            clone_property(
                source_item,
                None,
                item_source,
                item_source_path,
                item_materializer,
                item_name,
            )
        )
        string_nodes.append(
            clone_property(
                source_string,
                None,
                string_source,
                string_source_path,
                string_materializer,
                str(item_id),
            )
        )
    return item_nodes, string_nodes


def main() -> int:
    client_nodes_by_image = {name: [] for name in QUEST_IMAGE_NAMES}
    server_nodes_by_image = {name: [] for name in QUEST_IMAGE_NAMES}
    records: list[QuestRecord] = []
    for order, source_id in enumerate(SOURCE_QUEST_IDS, 1):
        server_nodes, record = build_quest_nodes(source_id, order, signed_ids=True)
        client_nodes, _ = build_quest_nodes(source_id, order, signed_ids=False)
        records.append(record)
        for image_name, node in server_nodes.items():
            server_nodes_by_image[image_name].append(node)
        for image_name, node in client_nodes.items():
            if source_id not in OBSOLETE_POSITIVE_IDS:
                client_nodes_by_image[image_name].append(node)

    npcs, mobs = installed_life_ids()
    required_npcs = {record.start_npc for record in records} | {record.end_npc for record in records}
    required_mobs = {mob_id for record in records for mob_id, _ in record.mobs}
    if required_npcs - npcs or required_mobs - mobs:
        raise RuntimeError(
            f"quest closure failed: missing NPCs={sorted(required_npcs - npcs)}, "
            f"mobs={sorted(required_mobs - mobs)}"
        )

    item_nodes, string_nodes = build_item_nodes()
    changed: list[str] = []
    positive_ids = tuple(str(quest_id) for quest_id in SOURCE_QUEST_IDS)
    negative_ids = tuple(str(quest_id) for quest_id in LEGACY_QUEST_IDS)
    working_positive_ids = tuple(str(quest_id) for quest_id in OBSOLETE_POSITIVE_IDS)
    for image_name, nodes in client_nodes_by_image.items():
        path = ROOT / f"clien/Data/Quest/{image_name}.img"
        if patch_raw_records(
            path,
            (),
            nodes,
            negative_ids,
            raw_replacements=git_baseline_records(path, working_positive_ids),
            append_order=positive_ids,
        ):
            changed.append(str(path.relative_to(ROOT)))

    item_path = ROOT / "clien/Data/Item/Etc/0403.img"
    if patch_raw_records(item_path, (), item_nodes):
        changed.append(str(item_path.relative_to(ROOT)))
    string_path = ROOT / "clien/Data/String/Etc.img"
    if patch_raw_records(string_path, ("Etc",), string_nodes):
        changed.append(str(string_path.relative_to(ROOT)))

    for tree in ("wz", "wz-zh-CN"):
        for image_name, nodes in server_nodes_by_image.items():
            path = ROOT / f"gms-server/{tree}/Quest.wz/{image_name}.img.xml"
            if patch_xml_records(
                path,
                f"{image_name}.img",
                nodes,
                tuple(str(quest_id) for quest_id in OBSOLETE_POSITIVE_IDS),
            ):
                changed.append(str(path.relative_to(ROOT)))

    item_xml = ROOT / "gms-server/wz/Item.wz/Etc/0403.img.xml"
    if patch_xml_records(item_xml, "0403.img", item_nodes):
        changed.append(str(item_xml.relative_to(ROOT)))
    for tree in ("wz", "wz-zh-CN"):
        string_xml = ROOT / f"gms-server/{tree}/String.wz/Etc.img.xml"
        if patch_xml_records(string_xml, "Etc", string_nodes):
            changed.append(str(string_xml.relative_to(ROOT)))

    digest = hashlib.sha256("\n".join(changed).encode()).hexdigest()[:12]
    print(
        f"Vanishing Journey quests ready: source=34100-34120, "
        f"legacy={LEGACY_QUEST_IDS[0]}..{LEGACY_QUEST_IDS[-1]}, "
        f"quests={len(records)}, items={len(QUEST_ITEMS)}, changed={len(changed)}, "
        f"change-set={digest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
