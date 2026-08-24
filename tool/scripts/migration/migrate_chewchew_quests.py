#!/usr/bin/env python3
"""Install legacy-safe ChewChew and YumYum quest chains incrementally.

Client Quest IMG records keep their positive modern IDs. Server Quest XML and
quest-limited drops use the bit-identical signed-16 IDs received from v83.
"""

from __future__ import annotations

import re
import sys
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
    CanvasMaterializer,
    clone_property,
    load_image,
    property_to_xml,
)
from migrate_vanishing_journey_quests import (  # noqa: E402
    atomic_write_text,
    find_imgdir_block,
    patch_raw_records,
)
from wzpy import WzImage, WzIntProperty, WzStringProperty, WzSubProperty  # noqa: E402


CHEWCHEW_STORY_IDS = tuple(range(34200, 34219))
YUMYUM_STORY_IDS = tuple(range(37701, 37727))
CHEWCHEW_DAILY_IDS = tuple(range(39017, 39034))
YUMYUM_DAILY_IDS = tuple(range(39064, 39071))
QUEST_IDS = (
    *CHEWCHEW_STORY_IDS,
    *YUMYUM_STORY_IDS,
    *CHEWCHEW_DAILY_IDS,
    *YUMYUM_DAILY_IDS,
)
DAILY_IDS = set(CHEWCHEW_DAILY_IDS) | set(YUMYUM_DAILY_IDS)
QUEST_IMAGE_NAMES = ("QuestInfo", "Check", "Act", "Say")
QUEST_ITEMS = {*range(4034942, 4034959), 4036571, 4036710}
INSTALLED_MOBS = {
    *range(8642000, 8642016),
    8642050, 8642051, 8642052, 8642053, 8642054, 8642055,
    8642060, 8642061, 8642062, 8642063, 8642064, 8642065,
}
AREA_PARENT = {208: "啾啾艾爾蘭每日任務", 274: "啾啾艾爾蘭", 275: "嚼嚼艾爾蘭"}
FALLBACK_EXP = {274: 16_000_000, 275: 20_000_000, 208: 8_000_000}


@dataclass(frozen=True)
class QuestRecord:
    source_id: int
    runtime_id: int
    start_npc: int
    end_npc: int
    items: tuple[tuple[int, int], ...]
    mobs: tuple[tuple[int, int], ...]


def signed_quest_id(source_id: int) -> int:
    if not 32768 <= source_id <= 65535:
        raise ValueError(f"quest ID is not a signed-16 projection: {source_id}")
    return source_id - 65536


def value(image: WzImage, path: str, default=None):
    node = image.root.get(path)
    return getattr(node, "value", default)


def add_int(parent: WzSubProperty, name: str, number: int) -> None:
    parent.add(WzIntProperty(name, int(number), parent))


def add_string(parent: WzSubProperty, name: str, string: str) -> None:
    parent.add(WzStringProperty(name, str(string), parent))


def objective_entries(source: WzImage, kind: str) -> list[tuple[int, int]]:
    root = source.root.get(f"Check/1/{kind}")
    if not isinstance(root, WzSubProperty):
        return []
    output = []
    for entry in root.children():
        entry_id = value(source, f"Check/1/{kind}/{entry.name}/id")
        count = value(source, f"Check/1/{kind}/{entry.name}/count")
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


def load_sources(ids: tuple[int, ...]) -> dict[int, WzImage]:
    output = {}
    for quest_id in ids:
        path = QUEST_SOURCE / f"{quest_id}.img"
        if not path.exists():
            raise FileNotFoundError(path)
        output[quest_id] = load_image(path, BMS_KEY)
    return output


def story_endpoints(
    quest_ids: tuple[int, ...], sources: dict[int, WzImage]
) -> dict[int, tuple[int, int]]:
    endpoints: dict[int, tuple[int, int]] = {}
    previous_endpoint: int | None = None
    for index, quest_id in enumerate(quest_ids):
        source = sources[quest_id]
        next_start = next(
            (
                value(sources[candidate], "Check/0/npc")
                for candidate in quest_ids[index + 1 :]
                if isinstance(value(sources[candidate], "Check/0/npc"), int)
            ),
            None,
        )
        source_start = value(source, "Check/0/npc")
        start_npc = source_start if isinstance(source_start, int) else previous_endpoint
        if not isinstance(start_npc, int):
            start_npc = next_start
        source_end = value(source, "Check/1/npc")
        end_npc = source_end if isinstance(source_end, int) else next_start
        if not isinstance(end_npc, int):
            end_npc = start_npc
        if not isinstance(start_npc, int) or not isinstance(end_npc, int):
            raise RuntimeError(f"quest {quest_id} has no compatible NPC endpoint")
        endpoints[quest_id] = (start_npc, end_npc)
        previous_endpoint = end_npc
    return endpoints


def build_quest_node_set(
    source_id: int,
    target_id: int,
    order: int,
    start_npc: int,
    end_npc: int,
    prerequisite: int | None,
    source: WzImage,
) -> tuple[dict[str, WzSubProperty], QuestRecord]:
    source_info = source.root.get("QuestInfo")
    if not isinstance(source_info, WzSubProperty):
        raise RuntimeError(f"missing QuestInfo in {source.name}")
    area = int(value(source, "QuestInfo/area", 208))
    name = str(value(source, "QuestInfo/name", f"神秘河任務 {source_id}"))
    intro = str(value(source, "QuestInfo/0", name))
    progress = str(value(source, "QuestInfo/1", intro))
    completed = str(value(source, "QuestInfo/2", "這件事總算完成了。"))
    items = objective_entries(source, "item")
    mobs = [entry for entry in objective_entries(source, "mob") if entry[0] in INSTALLED_MOBS]
    unknown_items = {item_id for item_id, _ in items} - QUEST_ITEMS
    if unknown_items:
        raise RuntimeError(f"quest {source_id} uses unapproved items {sorted(unknown_items)}")

    info = WzSubProperty(str(target_id))
    add_string(info, "0", intro)
    add_string(info, "1", progress)
    add_string(info, "2", completed)
    add_int(info, "area", area)
    add_string(info, "name", name)
    add_string(info, "parent", AREA_PARENT.get(area, "神秘河"))
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
    add_int(start, "lvmin", max(1, int(value(source, "Check/0/lvmin", 210))))
    if source_id in DAILY_IDS:
        add_int(start, "interval", 1440)
    if prerequisite is not None:
        prerequisites = WzSubProperty("quest", start)
        prerequisite_node = WzSubProperty("0", prerequisites)
        start.add(prerequisites)
        prerequisites.add(prerequisite_node)
        add_int(prerequisite_node, "id", prerequisite)
        add_int(prerequisite_node, "state", 2)
        add_int(prerequisite_node, "order", 1)
    add_int(finish, "npc", end_npc)
    add_int(finish, "order", 1)
    add_entries(finish, "item", items)
    add_entries(finish, "mob", mobs)

    act = WzSubProperty(str(target_id))
    act.add(WzSubProperty("0", act))
    reward = WzSubProperty("1", act)
    act.add(reward)
    source_exp = value(source, "Act/1/exp")
    add_int(
        reward,
        "exp",
        int(source_exp)
        if isinstance(source_exp, int) and source_exp > 0
        else FALLBACK_EXP.get(area, 8_000_000),
    )
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
        runtime_id=signed_quest_id(source_id),
        start_npc=start_npc,
        end_npc=end_npc,
        items=tuple(items),
        mobs=tuple(mobs),
    )


def build_all_nodes(signed_ids: bool):
    sources = load_sources(QUEST_IDS)
    endpoints = {
        **story_endpoints(CHEWCHEW_STORY_IDS, sources),
        **story_endpoints(YUMYUM_STORY_IDS, sources),
    }
    for quest_id in (*CHEWCHEW_DAILY_IDS, *YUMYUM_DAILY_IDS):
        start_npc = value(sources[quest_id], "Check/0/npc")
        end_npc = value(sources[quest_id], "Check/1/npc", start_npc)
        if not isinstance(start_npc, int) or not isinstance(end_npc, int):
            raise RuntimeError(f"daily quest {quest_id} has no NPC endpoint")
        endpoints[quest_id] = (start_npc, end_npc)

    nodes = {name: [] for name in QUEST_IMAGE_NAMES}
    records = []
    previous_story: dict[int, int | None] = {}
    for group in (CHEWCHEW_STORY_IDS, YUMYUM_STORY_IDS):
        for index, quest_id in enumerate(group):
            previous_story[quest_id] = group[index - 1] if index else None
    for quest_id in CHEWCHEW_DAILY_IDS:
        previous_story[quest_id] = CHEWCHEW_STORY_IDS[-1]
    for quest_id in YUMYUM_DAILY_IDS:
        previous_story[quest_id] = YUMYUM_STORY_IDS[-1]

    for order, quest_id in enumerate(QUEST_IDS, 1):
        target_id = signed_quest_id(quest_id) if signed_ids else quest_id
        previous = previous_story[quest_id]
        prerequisite = (
            signed_quest_id(previous) if signed_ids and previous is not None else previous
        )
        start_npc, end_npc = endpoints[quest_id]
        built, record = build_quest_node_set(
            quest_id,
            target_id,
            order,
            start_npc,
            end_npc,
            prerequisite,
            sources[quest_id],
        )
        records.append(record)
        for image_name, node in built.items():
            nodes[image_name].append(node)
    return nodes, records


def installed_life_ids() -> tuple[set[int], set[int]]:
    npcs: set[int] = set()
    mobs: set[int] = set()
    for pattern in ("450002*.img.xml", "450015*.img.xml"):
        for path in (ROOT / "gms-server/wz/Map.wz/Map/Map4").glob(pattern):
            root = ET.parse(path).getroot()
            life = root.find("./imgdir[@name='life']")
            if life is None:
                continue
            for entry in life.findall("./imgdir"):
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
    string_parent = string_source.root.get("Etc")
    if not isinstance(string_parent, WzSubProperty):
        raise RuntimeError("TMS String/Etc.img has no Etc parent")
    item_materializer = CanvasMaterializer()
    string_materializer = CanvasMaterializer()
    item_nodes = []
    string_nodes = []
    for item_id in sorted(QUEST_ITEMS):
        item_name = f"0{item_id}"
        source_item = item_source.root.get(item_name)
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


def direct_imgdir_spans(text: str, parent_name: str) -> tuple[tuple[int, int], dict[str, tuple[int, int]]]:
    parent_span = find_imgdir_block(text, parent_name)
    if parent_span is None:
        raise RuntimeError(f"missing XML parent {parent_name}")
    parent_start, parent_end = parent_span
    token = re.compile(r"</?imgdir\b[^>]*>")
    name_pattern = re.compile(r'\bname="([^"]+)"')
    depth = 0
    child_start = None
    child_name = None
    children: dict[str, tuple[int, int]] = {}
    for match in token.finditer(text, parent_start, parent_end):
        tag = match.group(0)
        if tag.startswith("</"):
            if depth == 2 and child_start is not None and child_name is not None:
                if child_name in children:
                    raise RuntimeError(f"duplicate direct XML child {parent_name}/{child_name}")
                children[child_name] = (child_start, match.end())
                child_start = child_name = None
            depth -= 1
            continue
        if depth == 1:
            name_match = name_pattern.search(tag)
            if name_match is None:
                raise RuntimeError(f"unnamed direct XML child in {parent_name}")
            if tag.endswith("/>"):
                children[name_match.group(1)] = (match.start(), match.end())
            else:
                child_start = match.start()
                child_name = name_match.group(1)
        if not tag.endswith("/>"):
            depth += 1
    if depth != 0 or child_start is not None:
        raise RuntimeError(f"unterminated direct XML child in {parent_name}")
    return parent_span, children


def patch_xml_records(
    path: Path,
    parent_name: str,
    nodes: list[WzSubProperty],
    remove_names: tuple[str, ...] = (),
) -> bool:
    original = path.read_text(encoding="utf-8-sig")
    result = original
    for name in remove_names:
        (parent_start, parent_end), children = direct_imgdir_spans(result, parent_name)
        span = children.get(name)
        if span is None:
            continue
        line_start = result.rfind("\n", parent_start, span[0]) + 1
        remove_start = line_start if not result[line_start : span[0]].strip() else span[0]
        result = result[:remove_start] + result[span[1] :]

    for node in nodes:
        (parent_start, parent_end), children = direct_imgdir_spans(result, parent_name)
        span = children.get(node.name)
        block = property_to_xml(node, 1)
        if span is None:
            insert_at = result.rfind("</imgdir>", parent_start, parent_end)
            separator = "" if result[:insert_at].endswith("\n") else "\n"
            result = result[:insert_at] + separator + block + "\n" + result[insert_at:]
        else:
            line_start = result.rfind("\n", parent_start, span[0]) + 1
            replace_start = line_start if not result[line_start : span[0]].strip() else span[0]
            result = result[:replace_start] + block + result[span[1] :]

    ET.fromstring(result)
    _, verified = direct_imgdir_spans(result, parent_name)
    for name in remove_names:
        if name in verified:
            raise RuntimeError(f"obsolete direct XML child survived: {parent_name}/{name}")
    for node in nodes:
        if node.name not in verified:
            raise RuntimeError(f"direct XML child missing after patch: {parent_name}/{node.name}")
    if result != original:
        atomic_write_text(path, result)
        return True
    return False


def main() -> int:
    client_nodes, _ = build_all_nodes(signed_ids=False)
    server_nodes, records = build_all_nodes(signed_ids=True)
    installed_npcs, installed_mobs = installed_life_ids()
    required_npcs = {record.start_npc for record in records} | {
        record.end_npc for record in records
    }
    required_mobs = {mob_id for record in records for mob_id, _ in record.mobs}
    if required_npcs - installed_npcs or required_mobs - installed_mobs:
        raise RuntimeError(
            f"quest closure failed: missing NPCs={sorted(required_npcs - installed_npcs)}, "
            f"mobs={sorted(required_mobs - installed_mobs)}"
        )

    changed = []
    positive_names = tuple(str(quest_id) for quest_id in QUEST_IDS)
    negative_names = tuple(str(signed_quest_id(quest_id)) for quest_id in QUEST_IDS)
    for image_name, nodes in client_nodes.items():
        path = ROOT / f"clien/Data/Quest/{image_name}.img"
        if patch_raw_records(path, (), nodes, negative_names, append_order=positive_names):
            changed.append(path.relative_to(ROOT).as_posix())

    item_nodes, string_nodes = build_item_nodes()
    item_path = ROOT / "clien/Data/Item/Etc/0403.img"
    if patch_raw_records(item_path, (), item_nodes):
        changed.append(item_path.relative_to(ROOT).as_posix())
    string_path = ROOT / "clien/Data/String/Etc.img"
    if patch_raw_records(string_path, ("Etc",), string_nodes):
        changed.append(string_path.relative_to(ROOT).as_posix())

    for tree in ("wz", "wz-zh-CN"):
        for image_name, nodes in server_nodes.items():
            path = ROOT / f"gms-server/{tree}/Quest.wz/{image_name}.img.xml"
            if path.exists() and patch_xml_records(
                path, f"{image_name}.img", nodes, positive_names
            ):
                changed.append(path.relative_to(ROOT).as_posix())

    item_xml = ROOT / "gms-server/wz/Item.wz/Etc/0403.img.xml"
    if patch_xml_records(item_xml, "0403.img", item_nodes):
        changed.append(item_xml.relative_to(ROOT).as_posix())
    for tree in ("wz", "wz-zh-CN"):
        string_xml = ROOT / f"gms-server/{tree}/String.wz/Etc.img.xml"
        if string_xml.exists() and patch_xml_records(string_xml, "Etc", string_nodes):
            changed.append(string_xml.relative_to(ROOT).as_posix())

    print(
        f"ChewChew/YumYum quests ready: quests={len(records)}, "
        f"items={len(QUEST_ITEMS)}, changed={len(changed)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
