#!/usr/bin/env python3
"""Migrate Twilight Perion and the installed TMS Monster Park contract."""

from __future__ import annotations

import hashlib
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzFloatProperty,
    WzImage,
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.incremental_img import (  # noqa: E402
    _apply_edits,
    _count_edit,
    _find_record,
    _reference_edits,
    _size_edits,
    mutate_img,
    replace_img_record,
    scan_img,
)
from wzpy.incremental_xml import mutate_xml  # noqa: E402


TWILIGHT_MAP_IDS = (
    273000000,
    273010000,
    273020000,
    273020100,
    273020200,
    273020300,
    273020400,
    273020500,
    273020600,
    273030000,
    273030100,
    273030200,
    273030300,
    273040000,
    273040100,
    273040200,
    273040300,
    273050000,
    273060000,
    273060100,
    273060200,
    273060300,
    273060400,
    273060500,
)
EXCLUDED_PARK_MAP_IDS = {953400000}
EXTREME_PARK_MAP_IDS = (951000300, 951000400)
KEEP_PORTAL_SCRIPTS = {
    "mPark_nextStage",
    "mPark_final",
    "Extreme_out",
    "Extreme_out2",
}
# Same-map auto-touch landings for TMS pt=13 jump pads.
# Analogue: mushroom castle 106020501/106021800 pt=3 -> hidden pt=1.
EXTREME_JUMP_LANDINGS = {
    "pt_Ljump": "floor07",
    "pt_Rjump": "floor09",
    "pt_Mjump": "boss3",
    "pt_Ljump2": "floor07",
    "pt_Rjump2": "floor09",
}
PORTAL_EXTRA_UNSUPPORTED = (
    "verticalImpact",
    "reactorName",
    "sessionValueKey",
    "sessionValue",
)
QUEST_IDS = tuple(
    list(range(31900, 31930)) + list(range(31960, 31966)) + [31093, 15177, 15196]
    + list(range(15181, 15189))
)
NPC_OVERRIDES = {
    31900: (1022000, 1022000),
    31901: (1022000, 1022000),
    31902: (1022000, 1022000),
    31903: (1022000, 2142100),
    31907: (2142107, 2142107),
    31908: (2142107, 2142100),
    31909: (2142100, 1022000),
    31910: (2142100, 2142100),
    31915: (2142100, 2142100),
    31961: (2142011, 2140000),
    15188: (9000159, 9000159),
}
TOWN_EXTRA_NPCS = (
    (2142011, 430),
    (2140000, 530),
    (2140002, 630),
    (1105001, 730),
    (1105003, 830),
    (1105004, 930),
)
COLLECTION_DROPS = (
    (31911, 4033732, 8620000),
    (31912, 4033733, 8620001),
    (31921, 4033729, 8620006),
    (31922, 4033735, 8620007),
    (31923, 4033726, 8620002),
    (31924, 4000828, 8620003),
    (31925, 4000828, 8620003),
    (31926, 4033727, 8620004),
    (31927, 4033728, 8620005),
    (31928, 4000832, 8620008),
    (31964, 4030048, 8620010),
)
MEDAL_IDS = (1142915, 1142916, 1142917, 1142918, 1142919, 1142920, 1142921, 1142922, 1143125)
CONSUME_IDS = (2431554,)
TWILIGHT_MOBS = tuple(range(8620000, 8620012)) + (8620028, 8620029, 8620030, 8620031)
# 自动警卫区域 953020000-953020500. Linked fodder uses TMS string mobType/boss.
AUTO_GUARD_COURSE_MOBS = (9800045, 9800046, 9800047, 9800048, 9800049, 9800050)
AUTO_GUARD_COURSE_MAPS = (953020000, 953020100, 953020200, 953020300, 953020400, 953020500)
PARK_MOB_INFO_REMOVE = ("partyBonusMob", "charismaEXP", "HPgaugeHide", "PDRate", "MDRate")
PARK_LINK_ANIMATIONS = ("move", "stand", "attack1", "attack2", "hit1", "die1")
PARK_FALLBACK_EVA = 5
QUEST_NAMES = ("Act", "Check", "QuestInfo", "Say")
DROP_SQL = (
    ROOT
    / "gms-server/src/main/resources/db/migration/"
    "V2.1.76__add_twilight_perion_monster_park_drops.sql"
)
WARP_SCRIPT = ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/万能传送.js"
LIFE_MODERN_FIELDS = ("forcedZPage", "forcedZMass", "limitedname")
NPC_INFO_MODERN_FIELDS = ("conditionEffect", "button", "noDiscountPrice")


def park_map_ids() -> tuple[int, ...]:
    maps = [951000000, *EXTREME_PARK_MAP_IDS]
    root = SOURCE / "Map/Map/Map9"
    for path in sorted(root.glob("9530*.img")) + sorted(root.glob("954*.img")):
        map_id = int(path.stem)
        if map_id not in EXCLUDED_PARK_MAP_IDS:
            maps.append(map_id)
    return tuple(maps)


MAP_IDS = TWILIGHT_MAP_IDS + park_map_ids()
MAP_ID_SET = set(MAP_IDS)


def source_map_path(map_id: int) -> Path:
    return SOURCE / f"Map/Map/Map{str(map_id)[0]}/{map_id}.img"


def client_map_path(map_id: int) -> Path:
    return ROOT / f"clien/Data/Map/Map/Map{str(map_id)[0]}/{map_id}.img"


def server_map_path(tree: str, map_id: int) -> Path:
    return ROOT / f"gms-server/{tree}/Map.wz/Map/Map{str(map_id)[0]}/{map_id}.img.xml"


def town_for(map_id: int) -> int:
    return 273000000 if 273000000 <= map_id <= 273099999 else 951000000


INNER_PORTAL_TYPE = 10
AUTO_PORTAL_TYPE = 3
NONE_MAP_ID = 999999999
WARP_PORTAL_TYPES = {2, 3, 7, 10}


def portal_by_name(portal: WzSubProperty) -> dict[str, WzSubProperty]:
    named: dict[str, WzSubProperty] = {}
    for entry in portal.children():
        name = arc.child_value(entry, "pn")
        if name:
            named[str(name)] = entry
    return named


def is_drop_destination(dest: WzSubProperty) -> bool:
    dest_pt = int(arc.child_value(dest, "pt") or 0)
    dest_tm = arc.child_value(dest, "tm")
    return dest_pt in (0, 1) and dest_tm == NONE_MAP_ID


def is_same_map_inner_portal(
    map_id: int, entry: WzSubProperty, by_name: dict[str, WzSubProperty]
) -> bool:
    dest = by_name.get(str(arc.child_value(entry, "tn") or ""))
    if dest is None or dest is entry:
        return False
    target_map = arc.child_value(entry, "tm")
    if target_map not in (map_id, NONE_MAP_ID):
        return False
    if is_drop_destination(dest):
        return False
    return int(arc.child_value(dest, "pt") or 0) in WARP_PORTAL_TYPES


def looping_auto_portal_names(root: WzSubProperty) -> list[str]:
    portal = root.child("portal")
    if not isinstance(portal, WzSubProperty):
        return []
    by_name = portal_by_name(portal)
    names = []
    for entry in portal.children():
        if int(arc.child_value(entry, "pt") or 0) != AUTO_PORTAL_TYPE:
            continue
        dest = by_name.get(str(arc.child_value(entry, "tn") or ""))
        if dest is None or dest is entry or is_drop_destination(dest):
            continue
        if int(arc.child_value(dest, "pt") or 0) in WARP_PORTAL_TYPES:
            names.append(entry.name)
    return names


def inner_portal_edits(map_id: int, root: WzSubProperty) -> tuple[list[str], list[str]]:
    portal = root.child("portal")
    if not isinstance(portal, WzSubProperty):
        return [], []
    by_name = portal_by_name(portal)
    pt_names: list[str] = []
    tm_names: list[str] = []
    for entry in portal.children():
        if not is_same_map_inner_portal(map_id, entry, by_name):
            continue
        if int(arc.child_value(entry, "pt") or 0) != INNER_PORTAL_TYPE:
            pt_names.append(entry.name)
        if arc.child_value(entry, "tm") == NONE_MAP_ID:
            tm_names.append(entry.name)
    return pt_names, tm_names


def project_force_jumps(root: WzSubProperty, map_id: int) -> None:
    """Project TMS pt=13 pads onto mushroom-castle pt=3 -> hidden pt=1 warps."""
    if map_id not in EXTREME_PARK_MAP_IDS:
        return
    portal = root.child("portal")
    if not isinstance(portal, WzSubProperty):
        return
    by_name = portal_by_name(portal)
    for entry in portal.children():
        name = str(arc.child_value(entry, "pn") or "")
        landing = EXTREME_JUMP_LANDINGS.get(name)
        if landing is None:
            continue
        dest = by_name.get(landing)
        if dest is None or not is_drop_destination(dest):
            raise RuntimeError(f"{map_id} jump {name} missing hidden landing {landing}")
        arc.set_int(entry, "pt", AUTO_PORTAL_TYPE)
        arc.set_int(entry, "tm", map_id)
        arc.set_string(entry, "tn", landing)


def project_script_portals(root: WzSubProperty) -> None:
    portal = root.child("portal")
    if not isinstance(portal, WzSubProperty):
        return
    for entry in portal.children():
        script = str(arc.child_value(entry, "script") or "")
        if script not in KEEP_PORTAL_SCRIPTS:
            continue
        if int(arc.child_value(entry, "pt") or 0) != 7:
            arc.set_int(entry, "pt", 7)


def project_inner_portals(root: WzSubProperty, map_id: int) -> int:
    portal = root.child("portal")
    if not isinstance(portal, WzSubProperty):
        return 0
    by_name = portal_by_name(portal)
    changed = 0
    for entry in portal.children():
        if not is_same_map_inner_portal(map_id, entry, by_name):
            continue
        if int(arc.child_value(entry, "pt") or 0) != INNER_PORTAL_TYPE:
            arc.set_int(entry, "pt", INNER_PORTAL_TYPE)
            changed += 1
        if arc.child_value(entry, "tm") == NONE_MAP_ID:
            arc.set_int(entry, "tm", map_id)
            changed += 1
    return changed


def map_string_category(map_id: int) -> str:
    return "ossyria" if 273000000 <= map_id <= 273099999 else "etc"


def add_sub(parent: WzSubProperty, name: str) -> WzSubProperty:
    child = WzSubProperty(name, parent)
    parent.add(child)
    return child


def add_int(parent: WzSubProperty, name: str, value: int) -> None:
    parent.add(WzIntProperty(name, value, parent))


def add_string(parent: WzSubProperty, name: str, value: str) -> None:
    parent.add(WzStringProperty(name, value, parent))


def source_value(parent, name: str):
    child = parent.child(name) if parent is not None else None
    return None if child is None else child.value


def load_checked(path: Path, key) -> WzImage:
    image = arc.load_image(path, key)
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"unsafe IMG {path}: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    return image


def iter_canvas_link_paths(image: WzImage) -> list[tuple[str, ...]]:
    """Return canvas `_outlink`/`_inlink` records the old client cannot resolve."""
    found: list[tuple[str, ...]] = []

    def walk(node, parts: tuple[str, ...]) -> None:
        if isinstance(node, WzCanvasProperty):
            for name in ("_outlink", "_inlink"):
                if node.child(name) is not None:
                    found.append((*parts, name))
        children = node.children() if hasattr(node, "children") else []
        for child in children:
            walk(child, (*parts, child.name))

    for child in image.root.children():
        walk(child, (child.name,))
    return found


def strip_canvas_links(path: Path) -> int:
    """Remove leftover modern canvas links after pixels were already inlined."""
    before = path.read_bytes()
    image = load_checked(path, arc.GMS_KEY)
    targets = iter_canvas_link_paths(image)
    if not targets:
        return 0
    layout = scan_img(before, region="GMS")
    grouped: dict[int, dict[str, object]] = {}
    for target in targets:
        prop_list, record, ancestors = _find_record(layout.root, target)
        bucket = grouped.setdefault(
            id(prop_list),
            {"prop_list": prop_list, "ancestors": ancestors, "records": []},
        )
        bucket["records"].append(record)
    edits: list[tuple[int, int, bytes]] = []
    ancestor_deltas: dict[int, tuple[object, int]] = {}
    for bucket in grouped.values():
        prop_list = bucket["prop_list"]
        records = bucket["records"]
        ancestors = bucket["ancestors"]
        count_edit = _count_edit(prop_list, prop_list.count - len(records))
        count_delta = len(count_edit[2]) - (count_edit[1] - count_edit[0])
        edits.append(count_edit)
        delta = -sum(record.end - record.start for record in records) + count_delta
        for ancestor in ancestors:
            previous = ancestor_deltas.get(id(ancestor))
            ancestor_deltas[id(ancestor)] = (
                ancestor,
                (0 if previous is None else previous[1]) + delta,
            )
        for record in records:
            edits.append((record.start, record.end, b""))
    for ancestor, delta in ancestor_deltas.values():
        edits.extend(_size_edits([ancestor], delta))
    edits.extend(_reference_edits(layout, edits))
    patched = arc.verified_image_bytes(_apply_edits(before, edits), path.name)
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(patched)
    target_set = set(targets)
    removed = set(before_records) - set(after_records)
    expected_removed = {
        record_path
        for record_path in before_records
        if any(record_path[: len(target)] == target for target in target_set)
    }
    if removed != expected_removed:
        raise RuntimeError(f"{path.name}: unexpected records removed {sorted(removed - expected_removed)[:8]}")
    if set(after_records) - set(before_records):
        raise RuntimeError(f"{path.name}: stripping canvas links added records")
    for parent, order in before_orders.items():
        if parent not in after_orders and parent in expected_removed:
            continue
        expected = tuple(
            name for name in order if (*parent, name) not in expected_removed
        )
        if after_orders.get(parent) != expected:
            raise RuntimeError(f"{path.name}: sibling order changed at {parent}")
    parsed = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=path.name)
    parsed.parse()
    if parsed.truncated or parsed.parse_warnings:
        raise RuntimeError(
            f"{path.name}: truncated={parsed.truncated} warnings={parsed.parse_warnings}"
        )
    leftover = iter_canvas_link_paths(parsed)
    if leftover:
        raise RuntimeError(f"{path.name}: leftover canvas links {leftover[:4]}")
    arc.backup(path)
    arc.atomic_write_bytes(path, patched)
    return len(targets)


def remove_img_records(path: Path, targets: list[tuple[str, ...]]) -> int:
    """Delete named records in one size-changing pass and keep sibling names."""
    if not targets:
        return 0
    before = path.read_bytes()
    layout = scan_img(before, region="GMS")
    grouped: dict[int, dict[str, object]] = {}
    for target in targets:
        prop_list, record, ancestors = _find_record(layout.root, target)
        bucket = grouped.setdefault(
            id(prop_list),
            {"prop_list": prop_list, "ancestors": ancestors, "records": []},
        )
        bucket["records"].append(record)
    edits: list[tuple[int, int, bytes]] = []
    ancestor_deltas: dict[int, tuple[object, int]] = {}
    for bucket in grouped.values():
        prop_list = bucket["prop_list"]
        records = bucket["records"]
        ancestors = bucket["ancestors"]
        count_edit = _count_edit(prop_list, prop_list.count - len(records))
        count_delta = len(count_edit[2]) - (count_edit[1] - count_edit[0])
        edits.append(count_edit)
        delta = -sum(record.end - record.start for record in records) + count_delta
        for ancestor in ancestors:
            previous = ancestor_deltas.get(id(ancestor))
            ancestor_deltas[id(ancestor)] = (
                ancestor,
                (0 if previous is None else previous[1]) + delta,
            )
        for record in records:
            edits.append((record.start, record.end, b""))
    for ancestor, delta in ancestor_deltas.values():
        edits.extend(_size_edits([ancestor], delta))
    edits.extend(_reference_edits(layout, edits))
    patched = arc.verified_image_bytes(_apply_edits(before, edits), path.name)
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(patched)
    expected_removed = {
        record_path
        for record_path in before_records
        if any(record_path[: len(target)] == target for target in targets)
    }
    removed = set(before_records) - set(after_records)
    if removed != expected_removed:
        raise RuntimeError(f"{path.name}: unexpected records removed {sorted(removed - expected_removed)[:8]}")
    if set(after_records) - set(before_records):
        raise RuntimeError(f"{path.name}: record removal added records")
    for parent, order in before_orders.items():
        if parent not in after_orders and parent in expected_removed:
            continue
        expected = tuple(name for name in order if (*parent, name) not in expected_removed)
        if after_orders.get(parent) != expected:
            raise RuntimeError(f"{path.name}: sibling order changed at {parent}")
    parsed = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=path.name)
    parsed.parse()
    if parsed.truncated or parsed.parse_warnings:
        raise RuntimeError(
            f"{path.name}: truncated={parsed.truncated} warnings={parsed.parse_warnings}"
        )
    arc.backup(path)
    arc.atomic_write_bytes(path, patched)
    return len(targets)


def iter_life_modern_field_paths(image: WzImage) -> list[tuple[str, ...]]:
    found: list[tuple[str, ...]] = []
    life = image.root.child("life")
    if not isinstance(life, WzSubProperty):
        return found
    for entry in life.children():
        for name in LIFE_MODERN_FIELDS:
            if entry.child(name) is not None:
                found.append(("life", entry.name, name))
    return found


def strip_modern_life_fields() -> dict[int, int]:
    totals: dict[int, int] = {}
    for map_id in MAP_IDS:
        path = client_map_path(map_id)
        if not path.is_file():
            continue
        image = load_checked(path, arc.GMS_KEY)
        targets = iter_life_modern_field_paths(image)
        count = remove_img_records(path, targets)
        if count:
            totals[map_id] = count
        if not targets:
            continue
        for tree in ("wz", "wz-zh-CN"):
            server = server_map_path(tree, map_id)
            if not server.is_file():
                continue
            text = server.read_text(encoding="utf-8")
            original = text
            for _, entry_name, field in targets:
                try:
                    text = mutate_xml(text, "remove", ("life", entry_name, field))
                except KeyError:
                    continue
            if text != original:
                ET.fromstring(text)
                arc.backup(server)
                arc.atomic_write_text(server, text)
    return totals


def strip_lobby_npc_modern_info() -> dict[str, int]:
    totals: dict[str, int] = {}
    for npc_id in (9071001, 9071009):
        path = ROOT / f"clien/Data/Npc/{npc_id}.img"
        if not path.is_file():
            continue
        image = load_checked(path, arc.GMS_KEY)
        info = image.root.child("info")
        targets = [
            ("info", name)
            for name in NPC_INFO_MODERN_FIELDS
            if isinstance(info, WzSubProperty) and info.child(name) is not None
        ]
        count = remove_img_records(path, targets)
        if count:
            totals[str(npc_id)] = count
        server = ROOT / f"gms-server/wz/Npc.wz/{npc_id}.img.xml"
        if server.is_file() and targets:
            text = server.read_text(encoding="utf-8")
            original = text
            for target in targets:
                try:
                    text = mutate_xml(text, "remove", target)
                except KeyError:
                    continue
            if text != original:
                ET.fromstring(text)
                arc.backup(server)
                arc.atomic_write_text(server, text)
    return totals


def project_legacy_map_mark(name: str, analogue_name: str = "Henesys") -> bool:
    """Match a newly appended map mark to the old-client Henesys format=2 canvas."""
    path = ROOT / "clien/Data/Map/MapHelper.img"
    image = load_checked(path, arc.GMS_KEY)
    mark = image.root.get(f"mark/{name}")
    analogue = image.root.get(f"mark/{analogue_name}")
    if not isinstance(mark, WzCanvasProperty) or not isinstance(analogue, WzCanvasProperty):
        raise RuntimeError(f"missing MapHelper mark {name} or analogue {analogue_name}")
    if (int(mark.format), int(mark.format2 or 0)) == (
        int(analogue.format),
        int(analogue.format2 or 0),
    ):
        return False
    decoded = decode_canvas(mark, region="GMS")
    replacement = WzCanvasProperty(name)
    replacement.width, replacement.height = decoded.size
    replacement.format, replacement.format2 = int(analogue.format), int(analogue.format2 or 0)
    replacement._png_data = encode_canvas_payload(
        decoded.convert("RGBA"),
        replacement.format,
        replacement.width,
        replacement.height,
        key=arc.GMS_KEY,
        listwz=False,
    )
    replacement._png_length = len(replacement._png_data)
    replacement._png_offset = 0
    before = path.read_bytes()
    patched = replace_img_record(before, ("mark", name), replacement, region="GMS").data
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(patched)
    if before_orders != after_orders:
        raise RuntimeError("MapHelper mark sibling order changed")
    for record_path, raw in before_records.items():
        if record_path == ("mark", name) or record_path[:2] == ("mark", name):
            continue
        if record_path == ("mark",) or record_path == ():
            continue
        if after_records.get(record_path) != raw:
            raise RuntimeError(f"MapHelper changed protected record: {record_path}")
    parsed = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=path.name)
    parsed.parse()
    if parsed.truncated or parsed.parse_warnings:
        raise RuntimeError(f"MapHelper failed parse after {name} projection")
    projected = parsed.root.get(f"mark/{name}")
    if not isinstance(projected, WzCanvasProperty):
        raise RuntimeError(f"MapHelper lost mark/{name}")
    if (int(projected.format), int(projected.format2 or 0)) != (
        int(analogue.format),
        int(analogue.format2 or 0),
    ):
        raise RuntimeError(f"MapHelper mark/{name} format was not projected")
    decode_canvas(projected, region="GMS")
    arc.backup(path)
    arc.atomic_write_bytes(path, patched)
    return True


def strip_npc_to_stand(npc_id: int) -> int:
    path = ROOT / f"clien/Data/Npc/{npc_id}.img"
    image = load_checked(path, arc.GMS_KEY)
    targets = [
        (child.name,)
        for child in image.root.children()
        if child.name not in {"info", "stand"}
    ]
    count = remove_img_records(path, targets)
    server = ROOT / f"gms-server/wz/Npc.wz/{npc_id}.img.xml"
    if server.is_file() and targets:
        text = server.read_text(encoding="utf-8")
        original = text
        for target in targets:
            try:
                text = mutate_xml(text, "remove", target)
            except KeyError:
                continue
        if text != original:
            ET.fromstring(text)
            arc.backup(server)
            arc.atomic_write_text(server, text)
    return count


def repair_lobby_shared_resources() -> dict[str, object]:
    """Project lobby onto resources the old client already proved in Perion/Henesys."""
    totals: dict[str, object] = {}
    totals["mark_monster_park"] = project_legacy_map_mark("MonsterPark")
    totals["npc_9071000"] = strip_npc_to_stand(9071000)
    totals["npc_9071006"] = strip_npc_to_stand(9071006)
    lobby = client_map_path(951000000)
    image = load_checked(lobby, arc.GMS_KEY)
    life = image.root.child("life")
    remove_life: list[tuple[str, ...]] = []
    if isinstance(life, WzSubProperty):
        for entry in life.children():
            npc_id = int(arc.child_value(entry, "id") or 0)
            hide = int(arc.child_value(entry, "hide") or 0)
            if npc_id == 9071009 or hide:
                remove_life.append(("life", entry.name))
    totals["lobby_life"] = remove_img_records(lobby, remove_life)
    image = load_checked(lobby, arc.GMS_KEY)
    mark = str(arc.child_value(image.root.child("info"), "mapMark") or "")
    if mark == "MonsterPark":
        before = lobby.read_bytes()
        patched = mutate_img(
            before, "edit", ("info", "mapMark"), values={"value": "Perion"}, region="GMS"
        ).data
        arc.verify_raw_record_scope(before, patched, {("info", "mapMark")}, allow_additions=False)
        arc.backup(lobby)
        arc.atomic_write_bytes(lobby, patched)
        totals["lobby_map_mark"] = "Perion"
    for tree in ("wz", "wz-zh-CN"):
        server = server_map_path(tree, 951000000)
        if not server.is_file():
            continue
        text = server.read_text(encoding="utf-8")
        original = text
        for _, entry_name in remove_life:
            try:
                text = mutate_xml(text, "remove", ("life", entry_name))
            except KeyError:
                continue
        try:
            text = mutate_xml(
                text, "edit", ("info", "mapMark"), kind="String", values={"value": "Perion"}
            )
        except KeyError:
            pass
        if text != original:
            ET.fromstring(text)
            arc.backup(server)
            arc.atomic_write_text(server, text)
    return totals


def used_map_asset_files_with_canvas_links() -> list[tuple[str, str]]:
    """Obj/Back/Tile files whose in-use branches still have modern canvas links."""
    dependencies = {
        "assets": defaultdict(set),
        "mobs": set(),
        "npcs": set(),
        "bgms": set(),
        "marks": set(),
    }
    for map_id in MAP_IDS:
        path = client_map_path(map_id)
        if path.is_file():
            arc.merge_dependency_sets(
                dependencies, arc.collect_dependencies(load_checked(path, arc.GMS_KEY))
            )
    found: list[tuple[str, str]] = []
    for (kind, name), branches in sorted(dependencies["assets"].items()):
        asset = ROOT / f"clien/Data/Map/{kind}/{name}.img"
        if not asset.is_file():
            continue
        image = load_checked(asset, arc.GMS_KEY)
        linked = False
        for branch in branches:
            node = image.root.get(branch)
            if node is None:
                continue
            stack = [node]
            while stack:
                current = stack.pop()
                if isinstance(current, WzCanvasProperty) and (
                    current.child("_outlink") is not None or current.child("_inlink") is not None
                ):
                    linked = True
                    break
                if hasattr(current, "children"):
                    stack.extend(current.children())
            if linked:
                break
        if linked:
            found.append((kind, name))
    return found


def strip_park_obj_canvas_links(names: tuple[str, ...] | None = None) -> dict[str, int]:
    files = [("Obj", name) for name in names] if names else used_map_asset_files_with_canvas_links()
    totals: dict[str, int] = {}
    for kind, name in files:
        path = ROOT / f"clien/Data/Map/{kind}/{name}.img"
        count = strip_canvas_links(path)
        print(f"stripped {kind}/{name}.img {count}")
        totals[f"{kind}/{name}"] = count
    return totals


def sanitize_field(root: WzSubProperty, map_id: int) -> None:
    for child in list(root.children()):
        if child.name not in arc.MAP_ROOTS:
            arc.remove_child(root, child.name)
    info = root.child("info")
    if isinstance(info, WzSubProperty):
        for name in arc.MAP_INFO_UNSUPPORTED:
            arc.remove_child(info, name)
        for name in ("returnMap", "forcedReturn"):
            value = arc.child_value(info, name)
            if isinstance(value, int) and value != 999999999 and value not in MAP_ID_SET:
                arc.set_int(info, name, town_for(map_id))

    life = root.child("life")
    if isinstance(life, WzSubProperty):
        for entry in list(life.children()):
            if arc.child_value(entry, "type") == "n":
                npc_id = int(arc.child_value(entry, "id"))
                hidden = int(arc.child_value(entry, "hide") or 0) != 0
                if hidden or npc_id in arc.REMOVED_NPCS:
                    arc.remove_child(life, entry.name)
                    continue
            for name in (*arc.LIFE_UNSUPPORTED, *LIFE_MODERN_FIELDS):
                arc.remove_child(entry, name)

    for layer in [child for child in root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if isinstance(objects, WzSubProperty):
            for entry in list(objects.children()):
                modern_object = any(
                    entry.child(name) is not None for name in ("questex", "tags", "timeScale")
                )
                if entry.child("spineAni") is not None or modern_object:
                    arc.remove_child(objects, entry.name)
                    continue
                for name in arc.OBJ_UNSUPPORTED:
                    arc.remove_child(entry, name)

    arc.downgrade_connect_nodes(root)
    back = root.child("back")
    if isinstance(back, WzSubProperty):
        for entry in list(back.children()):
            if int(arc.child_value(entry, "ani") or 0) == 2:
                arc.remove_child(back, entry.name)
                continue
            for name in arc.BACK_UNSUPPORTED:
                arc.remove_child(entry, name)

    portal = root.child("portal")
    if not isinstance(portal, WzSubProperty):
        return
    project_inner_portals(root, map_id)
    project_force_jumps(root, map_id)
    project_script_portals(root)
    for entry in list(portal.children()):
        target = arc.child_value(entry, "tm")
        script = str(arc.child_value(entry, "script") or "")
        keep_script = script in KEEP_PORTAL_SCRIPTS
        remove = False
        if isinstance(target, int) and target != 999999999 and target not in MAP_ID_SET:
            remove = True
        elif script and target == 999999999 and not keep_script:
            remove = True
        if remove:
            arc.remove_child(portal, entry.name)
            continue
        if not keep_script:
            arc.remove_child(entry, "script")
        for name in (*arc.PORTAL_UNSUPPORTED, *PORTAL_EXTRA_UNSUPPORTED):
            arc.remove_child(entry, name)


def add_town_npcs(root: WzSubProperty) -> None:
    life = root.child("life")
    if not isinstance(life, WzSubProperty):
        return
    analogue = next(
        (
            entry
            for entry in life.children()
            if arc.child_value(entry, "type") == "n"
        ),
        None,
    )
    if analogue is None:
        raise RuntimeError("Twilight town has no NPC analogue")
    existing = {
        int(arc.child_value(entry, "id"))
        for entry in life.children()
        if arc.child_value(entry, "type") == "n"
    }
    used = {int(entry.name) for entry in life.children() if entry.name.isdigit()}
    next_name = max(used, default=-1) + 1
    for npc_id, x in TOWN_EXTRA_NPCS:
        if npc_id in existing:
            continue
        node = WzSubProperty(str(next_name), life)
        add_string(node, "type", "n")
        add_string(node, "id", str(npc_id))
        add_int(node, "x", x)
        add_int(node, "y", int(arc.child_value(analogue, "y") or 63))
        add_int(node, "mobTime", 0)
        add_int(node, "f", 0)
        add_int(node, "hide", 0)
        add_int(node, "fh", int(arc.child_value(analogue, "fh") or 1))
        add_int(node, "cy", int(arc.child_value(analogue, "cy") or 63))
        add_int(node, "rx0", x - 50)
        add_int(node, "rx1", x + 50)
        life.add(node)
        next_name += 1


def repair_client_inner_portals(map_id: int, pt_names: list[str], tm_names: list[str]) -> bool:
    path = client_map_path(map_id)
    before = path.read_bytes()
    patched = before
    approved: set[tuple[str, ...]] = set()
    for name in pt_names:
        patched = mutate_img(
            patched,
            "edit",
            ("portal", name, "pt"),
            values={"value": INNER_PORTAL_TYPE},
            region="GMS",
        ).data
        approved.add(("portal", name, "pt"))
    for name in tm_names:
        patched = mutate_img(
            patched,
            "edit",
            ("portal", name, "tm"),
            values={"value": map_id},
            region="GMS",
        ).data
        approved.add(("portal", name, "tm"))
    if patched == before:
        return False
    image = load_checked_from_bytes(patched, path.name)
    leftover_pt, leftover_tm = inner_portal_edits(map_id, image.root)
    if leftover_pt or leftover_tm:
        raise RuntimeError(
            f"{map_id} still needs inner portal edits pt={leftover_pt} tm={leftover_tm}"
        )
    leftover_loop = looping_auto_portal_names(image.root)
    if leftover_loop:
        raise RuntimeError(f"{map_id} still has looping auto portals {leftover_loop}")
    arc.verify_raw_record_scope(before, patched, approved, allow_additions=False)
    arc.atomic_write_bytes(path, patched)
    return True


def load_checked_from_bytes(data: bytes, name: str):
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"unsafe patched IMG {name}: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    return image


def repair_server_inner_portals(map_id: int, pt_names: list[str], tm_names: list[str]) -> bool:
    changed = False
    for tree in ("wz", "wz-zh-CN"):
        path = server_map_path(tree, map_id)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        original = text
        for name in pt_names:
            text = mutate_xml(
                text,
                "edit",
                ("portal", name, "pt"),
                kind="Int",
                values={"value": INNER_PORTAL_TYPE},
            )
        for name in tm_names:
            text = mutate_xml(
                text,
                "edit",
                ("portal", name, "tm"),
                kind="Int",
                values={"value": map_id},
            )
        if text == original:
            continue
        arc.atomic_write_text(path, text)
        changed = True
    return changed


def ensure_legacy_tile_info(path: Path) -> bool:
    """Old-client tilesets have an empty root info node before bsc/enH0."""
    image = load_checked(path, arc.GMS_KEY)
    if image.root.child("info") is not None:
        return False
    children = [child.name for child in image.root.children()]
    if not children:
        raise RuntimeError(f"empty tileset {path}")
    before = path.read_bytes()
    patched = arc.insert_property_record_before(before, (), WzSubProperty("info"), children[0])
    checked = load_checked_from_bytes(patched, path.name)
    if checked.root.child("info") is None:
        raise RuntimeError(f"{path.name} missing info after insert")
    if [child.name for child in checked.root.children()] != ["info", *children]:
        raise RuntimeError(f"{path.name} info insert reordered tileset children")
    arc.verify_raw_record_insert_scope(before, patched, {("info",)})
    arc.atomic_write_bytes(path, patched)
    return True


def repair_legacy_tilesets() -> dict[str, int]:
    totals = {"files": 0, "patched": 0}
    names = set()
    for map_id in MAP_IDS:
        path = client_map_path(map_id)
        if not path.is_file():
            continue
        image = load_checked(path, arc.GMS_KEY)
        for kind, asset in arc.collect_dependencies(image)["assets"]:
            if kind == "Tile":
                names.add(asset)
    tile_dir = ROOT / "clien/Data/Map/Tile"
    for name in sorted(names):
        path = tile_dir / f"{name}.img"
        if not path.is_file():
            continue
        totals["files"] += 1
        if ensure_legacy_tile_info(path):
            totals["patched"] += 1
    return totals


def repair_looping_portals() -> dict[str, int]:
    totals = {"maps": 0, "portals": 0, "tm": 0, "xml": 0}
    for map_id in MAP_IDS:
        path = client_map_path(map_id)
        if not path.is_file():
            continue
        image = load_checked(path, arc.GMS_KEY)
        pt_names, tm_names = inner_portal_edits(map_id, image.root)
        if not pt_names and not tm_names:
            continue
        if repair_client_inner_portals(map_id, pt_names, tm_names):
            totals["maps"] += 1
            totals["portals"] += len(pt_names)
            totals["tm"] += len(tm_names)
        if repair_server_inner_portals(map_id, pt_names, tm_names):
            totals["xml"] += 1
    return totals


def migrate_maps() -> tuple[dict[str, object], dict[str, int]]:
    dependencies = {
        "assets": defaultdict(set),
        "mobs": set(),
        "npcs": set(),
        "bgms": set(),
        "marks": set(),
    }
    totals = {"maps": 0, "canvases": 0, "links": 0, "resized": 0}
    for map_id in MAP_IDS:
        source = source_map_path(map_id)
        client = client_map_path(map_id)
        if client.exists():
            image = load_checked(client, arc.GMS_KEY)
            materializer = arc.CanvasMaterializer()
        else:
            image, materializer = arc.clone_image(
                source,
                lambda root, value=map_id: sanitize_field(root, value),
            )
            if map_id == 273000000:
                add_town_npcs(image.root)
            arc.write_client_image(client, image)
        arc.merge_dependency_sets(dependencies, arc.collect_dependencies(image))
        for tree in ("wz", "wz-zh-CN"):
            server = server_map_path(tree, map_id)
            if not server.parent.exists():
                continue
            if server.exists():
                ET.parse(server)
            else:
                arc.write_server_image(server, image, f"{map_id}.img")
        totals["maps"] += 1
        totals["canvases"] += materializer.canvases
        totals["links"] += materializer.links
        totals["resized"] += materializer.resized
    for npc_id, _ in TOWN_EXTRA_NPCS:
        dependencies["npcs"].add(npc_id)
    totals.update({f"portal_{key}": value for key, value in repair_looping_portals().items()})
    return dependencies, totals


def merge_assets_tolerant(dependencies: dict[str, object]) -> dict[str, int]:
    totals = {"files": 0, "branches": 0, "canvases": 0, "links": 0, "resized": 0, "skipped": 0}
    for (kind, name), branches in sorted(dependencies["assets"].items()):
        remaining = set(branches)
        try:
            canvases, links, resized = arc.merge_asset(kind, name, remaining)
        except RuntimeError:
            canvases = links = resized = 0
            for branch in sorted(remaining):
                try:
                    part_c, part_l, part_r = arc.merge_asset(kind, name, {branch})
                    canvases += part_c
                    links += part_l
                    resized += part_r
                except RuntimeError as exc:
                    print(f"skip asset {kind}/{name}.img/{branch}: {exc}")
                    totals["skipped"] += 1
        totals["files"] += 1
        totals["branches"] += len(branches)
        totals["canvases"] += canvases
        totals["links"] += links
        totals["resized"] += resized
    totals.update({f"tile_{key}": value for key, value in repair_legacy_tilesets().items()})
    return totals


def migrate_npcs(npc_ids: set[int]) -> dict[str, int]:
    totals = {"npcs": 0, "canvases": 0, "links": 0, "resized": 0}
    with ProcessPoolExecutor(max_workers=4) as executor:
        for canvases, links, resized in executor.map(arc.migrate_one_npc, sorted(npc_ids)):
            totals["npcs"] += 1
            totals["canvases"] += canvases
            totals["links"] += links
            totals["resized"] += resized
    return totals


def upsert_map_strings(map_ids: tuple[int, ...]) -> dict[str, int]:
    totals = {}
    by_category: dict[str, list[int]] = defaultdict(list)
    for map_id in map_ids:
        by_category[map_string_category(map_id)].append(map_id)
    for category, ids in by_category.items():
        totals[f"client_{category}"] = arc.upsert_client_strings("Map", tuple(ids), category)
        for tree in ("wz", "wz-zh-CN"):
            totals[f"{tree}_{category}"] = arc.upsert_server_strings(
                tree, "Map", tuple(ids), category
            )
    return totals


def first_existing_anchor(order: tuple[str, ...], name: str) -> str | None:
    after = [item for item in order if item > name]
    return after[0] if after else None


def append_named_records(
    path: Path,
    parent_path: tuple[str, ...],
    nodes: list[WzSubProperty],
) -> bool:
    original = path.read_bytes()
    data = original
    approved = {(*parent_path, node.name) for node in nodes}
    for node in nodes:
        records, orders = arc.raw_record_state(data)
        if (*parent_path, node.name) in records:
            continue
        before_name = first_existing_anchor(orders[parent_path], node.name)
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


def append_server_named(
    path: Path, parent_path: tuple[str, ...], nodes: list[WzSubProperty]
) -> bool:
    if not path.exists():
        return False
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


def clone_record(source_path: Path, record_name: str, image, materializer) -> WzSubProperty:
    source = image.root.child(record_name)
    if not isinstance(source, WzSubProperty):
        raise RuntimeError(f"missing record {source_path}:{record_name}")
    cloned = arc.clone_property(
        source, None, image, source_path, materializer, record_name
    )
    if not isinstance(cloned, WzSubProperty):
        raise RuntimeError(f"invalid record {source_path}:{record_name}")
    return cloned


def audit_icons(node: WzSubProperty, item_id: int, names: tuple[str, ...]) -> None:
    for canvas_name in names:
        canvas = node.get(canvas_name)
        if not isinstance(canvas, WzCanvasProperty):
            canvas = node.get(f"info/{canvas_name}")
        if not isinstance(canvas, WzCanvasProperty):
            raise RuntimeError(f"missing Canvas {item_id}/{canvas_name}")
        if (canvas.format, canvas.format2) != (1, 0):
            raise RuntimeError(f"incompatible Canvas {item_id}/{canvas_name}")
        bitmap = decode_canvas(canvas, region="GMS")
        if bitmap.width * bitmap.height <= 1 or not bitmap.getbbox():
            raise RuntimeError(f"empty Canvas {item_id}/{canvas_name}")


def migrate_etc_items(item_ids: tuple[int, ...]) -> None:
    grouped: dict[str, list[int]] = defaultdict(list)
    for item_id in item_ids:
        grouped[f"0{str(item_id)[:3]}.img"].append(item_id)
    string_source_path = SOURCE / "String/Etc.img"
    string_source = load_checked(string_source_path, arc.BMS_KEY)
    string_parent = string_source.root.child("Etc")
    if not isinstance(string_parent, WzSubProperty):
        raise RuntimeError("TMS String/Etc.img has no Etc parent")
    for file_name, ids in grouped.items():
        item_source_path = SOURCE / f"Item/Etc/{file_name}"
        item_source = load_checked(item_source_path, arc.BMS_KEY)
        materializer = arc.CanvasMaterializer()
        item_nodes = []
        string_nodes = []
        for item_id in ids:
            record_name = f"0{item_id}"
            item = clone_record(item_source_path, record_name, item_source, materializer)
            audit_icons(item, item_id, ("icon", "iconRaw"))
            item_nodes.append(item)
            source_string = string_parent.child(str(item_id))
            if not isinstance(source_string, WzSubProperty):
                raise RuntimeError(f"missing Etc string {item_id}")
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
        append_named_records(ROOT / f"clien/Data/Item/Etc/{file_name}", (), item_nodes)
        append_named_records(
            ROOT / "clien/Data/String/Etc.img", ("Etc",), string_nodes
        )
        append_server_named(
            ROOT / f"gms-server/wz/Item.wz/Etc/{file_name}.xml", (), item_nodes
        )
        for tree in ("wz", "wz-zh-CN"):
            append_server_named(
                ROOT / f"gms-server/{tree}/String.wz/Etc.img.xml",
                ("Etc",),
                string_nodes,
            )


def migrate_consume_items(item_ids: tuple[int, ...]) -> None:
    source_path = SOURCE / "Item/Consume/0243.img"
    source = load_checked(source_path, arc.BMS_KEY)
    string_path = SOURCE / "String/Consume.img"
    strings = load_checked(string_path, arc.BMS_KEY)
    materializer = arc.CanvasMaterializer()
    item_nodes = []
    string_nodes = []
    for item_id in item_ids:
        item = clone_record(source_path, f"0{item_id}", source, materializer)
        audit_icons(item, item_id, ("icon", "iconRaw"))
        item_nodes.append(item)
        text = strings.root.child(str(item_id))
        if not isinstance(text, WzSubProperty):
            raise RuntimeError(f"missing Consume string {item_id}")
        string_nodes.append(
            arc.clone_property(
                text, None, strings, string_path, arc.CanvasMaterializer(), str(item_id)
            )
        )
    append_named_records(ROOT / "clien/Data/Item/Consume/0243.img", (), item_nodes)
    append_named_records(ROOT / "clien/Data/String/Consume.img", (), string_nodes)
    append_server_named(
        ROOT / "gms-server/wz/Item.wz/Consume/0243.img.xml", (), item_nodes
    )
    for tree in ("wz", "wz-zh-CN"):
        append_server_named(
            ROOT / f"gms-server/{tree}/String.wz/Consume.img.xml", (), string_nodes
        )


def migrate_medals() -> None:
    for medal_id in MEDAL_IDS:
        client = ROOT / f"clien/Data/Character/Accessory/{medal_id:08d}.img"
        source = SOURCE / f"Character/Accessory/{medal_id:08d}.img"
        if not client.exists():
            image, _ = arc.clone_image(source)
            audit_icons(image.root, medal_id, ("info/icon", "info/iconRaw"))
            arc.write_client_image(client, image)
            server = ROOT / f"gms-server/wz/Character.wz/Accessory/{medal_id:08d}.img.xml"
            if not server.exists():
                arc.write_server_image(server, image, f"{medal_id:08d}.img")
        string_source_path = SOURCE / "String/Eqp.img"
        string_source = load_checked(string_source_path, arc.BMS_KEY)
        record = string_source.root.get(f"Eqp/Accessory/{medal_id}")
        if not isinstance(record, WzSubProperty):
            continue
        node = arc.clone_property(
            record,
            None,
            string_source,
            string_source_path,
            arc.CanvasMaterializer(),
            str(medal_id),
        )
        append_named_records(
            ROOT / "clien/Data/String/Eqp.img", ("Eqp", "Accessory"), [node]
        )
        for tree in ("wz", "wz-zh-CN"):
            append_server_named(
                ROOT / f"gms-server/{tree}/String.wz/Eqp.img.xml",
                ("Eqp", "Accessory"),
                [node],
            )


def collect_group(node, name: str) -> WzSubProperty | None:
    child = node.child(name) if isinstance(node, WzSubProperty) else None
    return child if isinstance(child, WzSubProperty) else None


def build_quest_nodes() -> tuple[dict[str, list[WzSubProperty]], dict[int, dict[str, str]]]:
    output = {name: [] for name in QUEST_NAMES}
    descriptions: dict[int, dict[str, str]] = {}
    for quest_id in QUEST_IDS:
        source_path = SOURCE / f"Quest/QuestData/{quest_id}.img"
        source = load_checked(source_path, arc.BMS_KEY)
        materializer = arc.CanvasMaterializer()
        signed_name = str(quest_id)
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
        if "name" not in text_fields:
            raise RuntimeError(f"quest name missing: {quest_id}")
        descriptions[quest_id] = text_fields
        output["QuestInfo"].append(info)

        source_start = source_check.child("0")
        source_end = source_check.child("1")
        if not isinstance(source_start, WzSubProperty) or not isinstance(
            source_end, WzSubProperty
        ):
            raise RuntimeError(f"TMS Check branches are missing: {quest_id}")
        start_npc = int(source_value(source_start, "npc") or 0)
        end_npc = int(source_value(source_end, "npc") or 0)
        if quest_id in NPC_OVERRIDES:
            start_npc, end_npc = NPC_OVERRIDES[quest_id]
        if not start_npc or not end_npc:
            raise RuntimeError(f"quest NPC missing after projection: {quest_id}")

        check = WzSubProperty(signed_name)
        start = add_sub(check, "0")
        add_int(start, "lvmin", int(source_value(source_start, "lvmin") or 105))
        add_int(start, "npc", start_npc)
        source_prereqs = collect_group(source_start, "quest")
        if source_prereqs is not None:
            prereqs = add_sub(start, "quest")
            for source_entry in source_prereqs.children():
                if not isinstance(source_entry, WzSubProperty):
                    continue
                entry = add_sub(prereqs, source_entry.name)
                for field in source_entry.children():
                    add_int(entry, field.name, int(field.value))
        end = add_sub(check, "1")
        add_int(end, "order", int(source_value(source_end, "order") or 1))
        add_int(end, "npc", end_npc)
        for objective_name in ("item", "mob"):
            objective = collect_group(source_end, objective_name)
            if objective is not None:
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
        output["Check"].append(check)

        act = WzSubProperty(signed_name)
        add_sub(act, "0")
        act_end = add_sub(act, "1")
        source_act_end = source.root.get("Act/1")
        exp = source_value(source_act_end, "exp") if source_act_end else None
        if exp:
            add_int(act_end, "exp", int(exp))
        source_act_items = collect_group(source_act_end, "item") if source_act_end else None
        if source_act_items is not None:
            items = add_sub(act_end, "item")
            for source_item in source_act_items.children():
                if not isinstance(source_item, WzSubProperty):
                    continue
                item = add_sub(items, source_item.name)
                add_int(item, "id", int(source_value(source_item, "id")))
                add_int(item, "count", int(source_value(source_item, "count") or 1))
        output["Act"].append(act)

        say = arc.clone_property(
            source_say, None, source, source_path, materializer, signed_name
        )
        if not isinstance(say, WzSubProperty):
            raise RuntimeError(f"TMS Say is not a property tree: {quest_id}")
        output["Say"].append(say)
    return output, descriptions


def write_drop_sql(park_mobs: set[int]) -> None:
    twilight = ",\n".join(f"({mob_id})" for mob_id in TWILIGHT_MOBS)
    park = ",\n".join(f"({mob_id})" for mob_id in sorted(park_mobs))
    quest_rows = ",\n".join(
        f"({mob_id}, {item_id}, 1, 1, {quest_id}, 500000)"
        for quest_id, item_id, mob_id in COLLECTION_DROPS
    )
    sql = f"""-- Twilight Perion overworld drops plus Monster Park instance mobs.
-- Potions use the existing Arcane River mapping onto client-known 2000005/2000006.
CREATE TEMPORARY TABLE `twilight_perion_mob_ids` (
    `mobid` INT NOT NULL PRIMARY KEY
);
INSERT INTO `twilight_perion_mob_ids` (`mobid`) VALUES
{twilight};

CREATE TEMPORARY TABLE `monster_park_mob_ids` (
    `mobid` INT NOT NULL PRIMARY KEY
);
INSERT INTO `monster_park_mob_ids` (`mobid`) VALUES
{park};

INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 0, 900, 1400, 0, 400000 FROM `twilight_perion_mob_ids`
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 0, 400, 800, 0, 400000 FROM `monster_park_mob_ids`
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);

INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 2000005, 1, 1, 0, 100000 FROM `twilight_perion_mob_ids`
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 2000005, 1, 1, 0, 100000 FROM `monster_park_mob_ids`
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);

INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 2000006, 1, 1, 0, 100000 FROM `twilight_perion_mob_ids`
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 2000006, 1, 1, 0, 100000 FROM `monster_park_mob_ids`
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);

INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`) VALUES
{quest_rows}
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);

DROP TEMPORARY TABLE `twilight_perion_mob_ids`;
DROP TEMPORARY TABLE `monster_park_mob_ids`;
"""
    arc.atomic_write_text(DROP_SQL, sql)


def patch_warp_script() -> None:
    text = WARP_SCRIPT.read_text(encoding="utf-8")
    needle = '    Array(450012000, 10000, "泰涅布利斯利曼#r          （消耗1万金币）#b")'
    addition = (
        needle
        + ',\n    Array(273000000, 10000, "黄昏的勇士之村#r        （消耗1万金币）#b"),\n'
        + '    Array(951000000, 10000, "怪物公园#r                （消耗1万金币）#b")'
    )
    if "273000000" in text and "951000000" in text:
        return
    if needle not in text:
        raise RuntimeError("warp script anchor missing")
    WARP_SCRIPT.write_text(text.replace(needle, addition, 1), encoding="utf-8")


def migrate_quests() -> None:
    quest_nodes, _ = build_quest_nodes()
    for name in QUEST_NAMES:
        append_named_records(
            ROOT / f"clien/Data/Quest/{name}.img", (), quest_nodes[name]
        )
        append_server_named(
            ROOT / f"gms-server/wz/Quest.wz/{name}.img.xml", (), quest_nodes[name]
        )
        zh = ROOT / f"gms-server/wz-zh-CN/Quest.wz/{name}.img.xml"
        if zh.exists():
            append_server_named(zh, (), quest_nodes[name])


def client_mob_path(mob_id: int) -> Path:
    for name in (f"{mob_id}.img", f"{mob_id:07d}.img"):
        path = ROOT / f"clien/Data/Mob/{name}"
        if path.is_file():
            return path
    return ROOT / f"clien/Data/Mob/{mob_id}.img"


def server_mob_path(tree: str, mob_id: int) -> Path:
    for name in (f"{mob_id}.img.xml", f"{mob_id:07d}.img.xml"):
        path = ROOT / f"gms-server/{tree}/Mob.wz/{name}"
        if path.is_file():
            return path
    return ROOT / f"gms-server/{tree}/Mob.wz/{mob_id}.img.xml"


BALLISTIC_DEFAULT_SPEED = 300


def iter_incomplete_ballistic_attacks(
    mob_ids: tuple[int, ...] | None = None,
) -> list[tuple[int, int, int]]:
    """Find client ball attacks that still lack the 8641002 type=2 contract."""
    found: list[tuple[int, int, int]] = []
    if mob_ids is None:
        paths = sorted((ROOT / "clien/Data/Mob").glob("*.img"))
    else:
        paths = [client_mob_path(mob_id) for mob_id in mob_ids]
    for path in paths:
        try:
            mob_id = int(path.stem)
        except ValueError:
            continue
        image = arc.load_image(path, arc.GMS_KEY)
        if image.truncated:
            raise RuntimeError(f"{path.name}: truncated while scanning ballistic attacks")
        for child in image.root.children():
            if not child.name.startswith("attack") or not isinstance(child, WzSubProperty):
                continue
            info = child.child("info")
            if not isinstance(info, WzSubProperty) or info.child("ball") is None:
                continue
            type_node = info.child("type")
            attack_type = getattr(type_node, "value", None) if type_node is not None else None
            hit = info.child("hit")
            needs_type = type_node is None or int(attack_type or 0) != 2
            needs_speed = info.child("bulletSpeed") is None
            needs_attach = isinstance(hit, WzSubProperty) and hit.child("attach") is None
            if not (needs_type or needs_speed or needs_attach):
                continue
            speed = BALLISTIC_DEFAULT_SPEED
            legacy = arc.LEGACY_BALLISTIC_ATTACKS.get(mob_id)
            if legacy and legacy[1]:
                speed = int(legacy[1])
            found.append((mob_id, int(child.name[len("attack") :]), speed))
    return found


def _insert_or_append_type(patched: bytes, attack: str, info: WzSubProperty) -> bytes:
    if info.child("attackAfter") is not None:
        try:
            return arc.insert_property_record_before(
                patched,
                (attack, "info"),
                WzIntProperty("type", 2),
                "attackAfter",
            )
        except RuntimeError:
            pass
    return arc.append_property_record(patched, (attack, "info"), WzIntProperty("type", 2))


def _insert_or_append_xml_type(text: str, attack: str, attack_info) -> str:
    if attack_info.find('./int[@name="attackAfter"]') is not None:
        return arc.insert_xml_properties_before(
            text, (attack, "info"), [WzIntProperty("type", 2)], "attackAfter"
        )
    return arc.append_xml_properties(text, (attack, "info"), [WzIntProperty("type", 2)])


def repair_ballistic_mob(mob_id: int, attack_number: int, bullet_speed: int) -> bool:
    """Project a ball attack onto the 450001014 / 8641002 type=2 contract."""
    attack = f"attack{attack_number}"
    client = client_mob_path(mob_id)
    if not client.is_file():
        raise FileNotFoundError(client)
    image = load_checked(client, arc.GMS_KEY)
    info = image.root.get(f"{attack}/info")
    if not isinstance(info, WzSubProperty) or info.child("ball") is None:
        raise RuntimeError(f"{mob_id}: missing {attack}/info/ball")
    before = client.read_bytes()
    patched = before
    approved: set[tuple[str, ...]] = set()
    if info.child("type") is None:
        patched = _insert_or_append_type(patched, attack, info)
        approved.add((attack, "info", "type"))
    if bullet_speed is not None and info.child("bulletSpeed") is None:
        patched = arc.append_property_record(
            patched, (attack, "info"), WzIntProperty("bulletSpeed", bullet_speed)
        )
        approved.add((attack, "info", "bulletSpeed"))
    hit = info.child("hit")
    if isinstance(hit, WzSubProperty) and hit.child("attach") is None:
        patched = arc.append_property_record(
            patched, (attack, "info", "hit"), WzIntProperty("attach", 1)
        )
        approved.add((attack, "info", "hit", "attach"))
    if patched != before:
        if not approved:
            raise RuntimeError(f"{mob_id}: ballistic bytes changed without approved roots")
        checked = load_checked_from_bytes(patched, client.name)
        if checked.truncated or checked.parse_warnings:
            raise RuntimeError(f"{client.name} parse failed after ballistic patch")
        patched_info = checked.root.get(f"{attack}/info")
        if int(arc.child_value(patched_info, "type") or 0) != 2:
            raise RuntimeError(f"{mob_id}: type was not projected to 2")
        if patched_info.child("ball") is None:
            raise RuntimeError(f"{mob_id}: ball node lost")
        arc.verify_raw_record_insert_scope(before, patched, approved)
        arc.atomic_write_bytes(client, patched)

    xml_changed = False
    for tree in ("wz", "wz-zh-CN"):
        path = server_mob_path(tree, mob_id)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        original = text
        parsed = ET.fromstring(text)
        attack_info = parsed.find(f'./imgdir[@name="{attack}"]/imgdir[@name="info"]')
        if attack_info is None:
            raise RuntimeError(f"{path.name}: missing {attack}/info")
        if attack_info.find('./int[@name="type"]') is None:
            text = _insert_or_append_xml_type(text, attack, attack_info)
        if bullet_speed is not None and attack_info.find('./int[@name="bulletSpeed"]') is None:
            text = arc.append_xml_properties(
                text, (attack, "info"), [WzIntProperty("bulletSpeed", bullet_speed)]
            )
        if (
            attack_info.find('./imgdir[@name="hit"]') is not None
            and attack_info.find('./imgdir[@name="hit"]/int[@name="attach"]') is None
        ):
            text = arc.append_xml_properties(
                text, (attack, "info", "hit"), [WzIntProperty("attach", 1)]
            )
        if text != original:
            arc.atomic_write_text(path, text)
            xml_changed = True
    return patched != before or xml_changed


def repair_twilight_ballistic_mobs() -> dict[str, int]:
    return repair_ballistic_mobs(TWILIGHT_MOBS)


def arcane_river_mob_ids() -> tuple[int, ...]:
    return tuple(int(path.stem) for path in sorted((ROOT / "clien/Data/Mob").glob("864*.img")))


def repair_ballistic_mobs(mob_ids: tuple[int, ...]) -> dict[str, int]:
    totals = {"mobs": 0, "attacks": 0}
    changed: set[int] = set()
    for mob_id, attack_number, bullet_speed in iter_incomplete_ballistic_attacks(mob_ids):
        if repair_ballistic_mob(mob_id, attack_number, bullet_speed):
            changed.add(mob_id)
            totals["attacks"] += 1
    totals["mobs"] = len(changed)
    return totals


def repair_arcane_river_ballistic_mobs() -> dict[str, int]:
    return repair_ballistic_mobs(arcane_river_mob_ids())


ANALOGUE_COMBAT_MOB_ID = 8641003
ATTACK_DAMAGE_DIVISOR = 10
ATTACK_DAMAGE_UNSCALED_MIN = 5000


def analogue_eva() -> int:
    image = load_checked(client_mob_path(ANALOGUE_COMBAT_MOB_ID), arc.GMS_KEY)
    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{ANALOGUE_COMBAT_MOB_ID}: missing info")
    value = arc.child_value(info, "eva")
    if value is None:
        raise RuntimeError(f"{ANALOGUE_COMBAT_MOB_ID}: missing info/eva")
    return int(value)


def scaled_attack_damage(value: int) -> int:
    if int(value) >= ATTACK_DAMAGE_UNSCALED_MIN:
        return max(1, int(value) // ATTACK_DAMAGE_DIVISOR)
    return int(value)


def twilight_combat_targets(info: WzSubProperty) -> dict[str, int]:
    targets = {"eva": analogue_eva()}
    for name in ("PADamage", "MADamage"):
        current = arc.child_value(info, name)
        if current is None:
            raise RuntimeError(f"missing info/{name}")
        targets[name] = scaled_attack_damage(int(current))
    return targets


def repair_mob_combat_stats(mob_id: int, stats: dict[str, int]) -> bool:
    client = client_mob_path(mob_id)
    if not client.is_file():
        raise FileNotFoundError(client)
    image = load_checked(client, arc.GMS_KEY)
    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{mob_id}: missing info")
    before = client.read_bytes()
    patched = before
    approved: set[tuple[str, ...]] = set()
    added = False
    for name, target in stats.items():
        current = arc.child_value(info, name)
        if current is None:
            patched = arc.append_property_record(
                patched, ("info",), WzIntProperty(name, target)
            )
            approved.add(("info", name))
            added = True
            continue
        if int(current) == target:
            continue
        patched = mutate_img(
            patched,
            "edit",
            ("info", name),
            kind="Int",
            values={"value": target},
            region="GMS",
        ).data
        approved.add(("info", name))
    if patched != before:
        checked = load_checked_from_bytes(patched, client.name)
        if checked.truncated or checked.parse_warnings:
            raise RuntimeError(f"{client.name} parse failed after combat stat patch")
        patched_info = checked.root.child("info")
        for name, target in stats.items():
            if int(arc.child_value(patched_info, name) or 0) != target:
                raise RuntimeError(f"{mob_id}: info/{name} was not projected to {target}")
        if added:
            arc.verify_raw_record_insert_scope(before, patched, approved)
        else:
            arc.verify_raw_record_scope(before, patched, approved, allow_additions=False)
        arc.atomic_write_bytes(client, patched)

    xml_changed = False
    for tree in ("wz", "wz-zh-CN"):
        path = server_mob_path(tree, mob_id)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        original = text
        parsed = ET.fromstring(text)
        xml_info = parsed.find('./imgdir[@name="info"]')
        if xml_info is None:
            raise RuntimeError(f"{path.name}: missing info")
        for name, target in stats.items():
            node = xml_info.find(f'./int[@name="{name}"]')
            if node is None:
                text = mutate_xml(
                    text,
                    "add",
                    ("info",),
                    name=name,
                    kind="Int",
                    values={"value": target},
                )
                parsed = ET.fromstring(text)
                xml_info = parsed.find('./imgdir[@name="info"]')
                continue
            if int(node.get("value") or 0) == target:
                continue
            text = mutate_xml(
                text,
                "edit",
                ("info", name),
                kind="Int",
                values={"value": target},
            )
        if text != original:
            arc.atomic_write_text(path, text)
            xml_changed = True
    return patched != before or xml_changed


def repair_twilight_combat_stats() -> dict[str, int]:
    totals = {"mobs": 0}
    for mob_id in TWILIGHT_MOBS:
        image = load_checked(client_mob_path(mob_id), arc.GMS_KEY)
        info = image.root.child("info")
        if not isinstance(info, WzSubProperty):
            raise RuntimeError(f"{mob_id}: missing info")
        if repair_mob_combat_stats(mob_id, twilight_combat_targets(info)):
            totals["mobs"] += 1
    return totals


def iter_park_mob_info_removals(info: WzSubProperty, *, drop_link: bool) -> list[tuple[str, ...]]:
    targets: list[tuple[str, ...]] = []
    mob_type = info.child("mobType")
    if isinstance(mob_type, WzStringProperty):
        targets.append(("info", "mobType"))
    for name in PARK_MOB_INFO_REMOVE:
        if info.child(name) is not None:
            targets.append(("info", name))
    if drop_link and info.child("link") is not None:
        targets.append(("info", "link"))
    return targets


def park_eva_target(info: WzSubProperty) -> int:
    # Magatia analogues sit at eva 18-25. Park clones were left at 100, which
    # still misses for ordinary 105-level accuracy. Use the Victoria-era floor.
    return PARK_FALLBACK_EVA


def clone_gms_tree(source, parent=None, name=None):
    """Clone an already-GMS Magatia mob subtree without the BMS canvas decoder."""
    output_name = source.name if name is None else name
    if isinstance(source, WzCanvasProperty):
        decoded = decode_canvas(source, region="GMS").convert("RGBA")
        output = WzCanvasProperty(output_name, parent)
        output.width, output.height = decoded.size
        output.format, output.format2 = 1, 0
        output._png_data = encode_canvas_payload(
            decoded, 1, decoded.width, decoded.height, key=arc.GMS_KEY, listwz=False
        )
        output._png_length = len(output._png_data)
        output._png_offset = 0
        for child in source.children():
            if child.name in {"_inlink", "_outlink"}:
                continue
            output.add(clone_gms_tree(child, output))
        return output
    if isinstance(source, WzSubProperty):
        output = WzSubProperty(output_name, parent)
        for child in source.children():
            output.add(clone_gms_tree(child, output))
        return output
    if isinstance(source, WzVectorProperty):
        return WzVectorProperty(output_name, int(source.x), int(source.y), parent)
    if isinstance(source, WzStringProperty):
        return WzStringProperty(output_name, str(source.value), parent)
    if isinstance(source, WzIntProperty):
        return WzIntProperty(output_name, int(source.value), parent)
    if isinstance(source, WzFloatProperty):
        return WzFloatProperty(output_name, float(source.value), parent)
    if isinstance(source, WzUolProperty):
        return WzUolProperty(output_name, str(source.value), parent)
    raise TypeError(f"unsupported GMS clone type: {type(source).__name__}")


def materialize_park_link_animations(mob_id: int) -> bool:
    """Copy the link target's action tree into an info-only park stub.

    The old client resolves TMS stats-only `info/link` shells for drawing, but
    combat still misses. Analogue: Magatia 5110301 is a complete GMS mob.
    """
    client = client_mob_path(mob_id)
    image = load_checked(client, arc.GMS_KEY)
    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{mob_id}: missing info")
    link = arc.child_value(info, "link")
    if link is None or image.root.child("stand") is not None:
        return False
    source_path = client_mob_path(int(link))
    source = load_checked(source_path, arc.GMS_KEY)
    patched = client.read_bytes()
    added: set[tuple[str, ...]] = set()
    for name in PARK_LINK_ANIMATIONS:
        node = source.root.child(name)
        if node is None or image.root.child(name) is not None:
            continue
        cloned = clone_gms_tree(node, None, name)
        patched = arc.append_property_record(patched, (), cloned)
        added.add((name,))
    if not added:
        return False
    checked = load_checked_from_bytes(patched, client.name)
    stand = checked.root.get("stand/0")
    if not isinstance(stand, WzCanvasProperty):
        raise RuntimeError(f"{mob_id}: materialized stand/0 is not a canvas")
    decoded = decode_canvas(stand, region="GMS")
    if decoded.size == (1, 1):
        raise RuntimeError(f"{mob_id}: materialized stand/0 is a 1x1 placeholder")
    arc.atomic_write_bytes(client, patched)
    return True


def repair_one_park_mob_info(mob_id: int) -> bool:
    client = client_mob_path(mob_id)
    if not client.is_file():
        raise FileNotFoundError(client)
    image = load_checked(client, arc.GMS_KEY)
    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{mob_id}: missing info")
    changed = False
    if materialize_park_link_animations(mob_id):
        changed = True
        image = load_checked(client, arc.GMS_KEY)
        info = image.root.child("info")
        if not isinstance(info, WzSubProperty):
            raise RuntimeError(f"{mob_id}: missing info after link materialize")
    eva_target = park_eva_target(info)
    drop_link = image.root.child("stand") is not None
    fodder = info.child("partyBonusMob") is not None or mob_id in (9800045, 9800046, 9800047, 9800049)
    if fodder and int(arc.child_value(info, "boss") or 0) != 0:
        if repair_mob_combat_stats(mob_id, {"boss": 0}):
            changed = True
        image = load_checked(client, arc.GMS_KEY)
        info = image.root.child("info")
        if not isinstance(info, WzSubProperty):
            raise RuntimeError(f"{mob_id}: missing info after boss patch")
    stats = {}
    if int(arc.child_value(info, "eva") or 0) != eva_target:
        stats["eva"] = eva_target
    if stats:
        if repair_mob_combat_stats(mob_id, stats):
            changed = True
        image = load_checked(client, arc.GMS_KEY)
        info = image.root.child("info")
        if not isinstance(info, WzSubProperty):
            raise RuntimeError(f"{mob_id}: missing info after eva patch")
    targets = iter_park_mob_info_removals(info, drop_link=drop_link)
    if targets:
        remove_img_records(client, targets)
        changed = True
    for tree in ("wz", "wz-zh-CN"):
        path = server_mob_path(tree, mob_id)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        original = text
        parsed = ET.fromstring(text)
        xml_info = parsed.find('./imgdir[@name="info"]')
        if xml_info is None:
            raise RuntimeError(f"{path.name}: missing info")
        if fodder:
            boss = xml_info.find('./int[@name="boss"]')
            if boss is not None and boss.get("value") != "0":
                text = mutate_xml(text, "edit", ("info", "boss"), kind="Int", values={"value": 0})
                parsed = ET.fromstring(text)
                xml_info = parsed.find('./imgdir[@name="info"]')
        xml_eva = xml_info.find('./int[@name="eva"]')
        if xml_eva is not None and xml_eva.get("value") != str(eva_target):
            text = mutate_xml(text, "edit", ("info", "eva"), kind="Int", values={"value": eva_target})
            parsed = ET.fromstring(text)
            xml_info = parsed.find('./imgdir[@name="info"]')
        xml_names = []
        if xml_info.find('./string[@name="mobType"]') is not None:
            xml_names.append("mobType")
        for field in PARK_MOB_INFO_REMOVE:
            if xml_info.find(f'./*[@name="{field}"]') is not None:
                xml_names.append(field)
        for name in xml_names:
            try:
                text = mutate_xml(text, "remove", ("info", name))
            except (KeyError, ValueError):
                continue
        if text != original:
            ET.fromstring(text)
            arc.atomic_write_text(path, text)
            changed = True
    return changed


def repair_auto_guard_park_mobs() -> dict[str, int]:
    totals = {"mobs": 0}
    for mob_id in AUTO_GUARD_COURSE_MOBS:
        if repair_one_park_mob_info(mob_id):
            totals["mobs"] += 1
    return totals


def iter_map_object_r_paths(image: WzImage) -> list[tuple[str, ...]]:
    found: list[tuple[str, ...]] = []
    for layer in [child for child in image.root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        for entry in objects.children():
            if entry.child("r") is not None:
                found.append((layer.name, "obj", entry.name, "r"))
    return found


def strip_auto_guard_object_r() -> dict[int, int]:
    totals: dict[int, int] = {}
    for map_id in AUTO_GUARD_COURSE_MAPS:
        path = client_map_path(map_id)
        if not path.is_file():
            continue
        image = load_checked(path, arc.GMS_KEY)
        targets = iter_map_object_r_paths(image)
        count = remove_img_records(path, targets)
        if count:
            totals[map_id] = count
        if not targets:
            continue
        for tree in ("wz", "wz-zh-CN"):
            server = server_map_path(tree, map_id)
            if not server.is_file():
                continue
            text = server.read_text(encoding="utf-8")
            original = text
            for layer_name, _, entry_name, field in targets:
                try:
                    text = mutate_xml(text, "remove", (layer_name, "obj", entry_name, field))
                except KeyError:
                    continue
            if text != original:
                ET.fromstring(text)
                arc.atomic_write_text(server, text)
    return totals


def write_park_gameplay_scripts() -> dict[str, int]:
    """Keep lobby/stage NPC, portal, and onUserEnter scripts in both script trees."""
    import shutil

    gms = ROOT / "gms-server"
    pairs = [
        ("scripts/npc/9071000.js", "scripts-zh-CN/npc/9071000.js"),
        ("scripts/npc/9071003.js", "scripts-zh-CN/npc/9071003.js"),
        ("scripts/npc/9071004.js", "scripts-zh-CN/npc/9071004.js"),
        ("scripts/npc/9071005.js", "scripts-zh-CN/npc/9071005.js"),
        ("scripts/npc/9071006.js", "scripts-zh-CN/npc/9071006.js"),
        ("scripts/npc/9071001.js", "scripts-zh-CN/npc/9071001.js"),
        ("scripts/event/MonsterPark.js", "scripts-zh-CN/event/MonsterPark.js"),
        ("scripts/portal/mPark_nextStage.js", "scripts-zh-CN/portal/mPark_nextStage.js"),
        ("scripts/portal/mPark_final.js", "scripts-zh-CN/portal/mPark_final.js"),
        ("scripts/portal/Extreme_out.js", "scripts-zh-CN/portal/Extreme_out.js"),
        ("scripts/portal/Extreme_out2.js", "scripts-zh-CN/portal/Extreme_out2.js"),
        ("scripts/portal/mPark_in00.js", "scripts-zh-CN/portal/mPark_in00.js"),
        ("scripts/portal/mPark_in01.js", "scripts-zh-CN/portal/mPark_in01.js"),
        ("scripts/portal/mPark_in02.js", "scripts-zh-CN/portal/mPark_in02.js"),
        ("scripts/portal/extreme_in03.js", "scripts-zh-CN/portal/extreme_in03.js"),
        ("scripts/map/onUserEnter/mPark_stageEff.js", "scripts-zh-CN/map/onUserEnter/mPark_stageEff.js"),
    ]
    aliases = {
        "npc/mPark_retire.js": "npc/9071005.js",
        "npc/mPark_welcome.js": "npc/9071000.js",
        "npc/mParkShuttle.js": "npc/9071003.js",
        "npc/extreme_welcome.js": "npc/9071006.js",
        "npc/mParkEnter.js": "npc/9071004.js",
        "npc/mParkShop.js": "npc/9071001.js",
        "npc/mPark_in00.js": "npc/9071000.js",
        "npc/mPark_in01.js": "npc/9071000.js",
        "npc/mPark_in02.js": "npc/9071000.js",
    }
    for src, dst in pairs:
        destination = gms / dst
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(gms / src, destination)
    for tree in ("scripts", "scripts-zh-CN"):
        for alias, src in aliases.items():
            destination = gms / tree / alias
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(gms / tree / src, destination)
    stage_body = (gms / "scripts/map/onUserEnter/mPark_stageEff.js").read_text(encoding="utf-8")
    written = 0
    map_root = gms / "wz/Map.wz/Map/Map9"
    for path in sorted(map_root.glob("9530*.img.xml")) + sorted(map_root.glob("954*.img.xml")):
        map_id = int(path.name.split(".")[0])
        if map_id in EXCLUDED_PARK_MAP_IDS:
            continue
        for tree in ("scripts", "scripts-zh-CN"):
            out = gms / tree / "map/onUserEnter" / f"{map_id}.js"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(stage_body, encoding="utf-8")
        written += 1
    return {"stage_maps": written}


def write_extreme_portal_scripts() -> None:
    scripts = {
        "extreme_in03.js": (
            "function enter(pi) {\n"
            '    pi.openNpc(9071006, "extreme_welcome");\n'
            "    return false;\n"
            "}\n"
        ),
        "Extreme_out.js": (
            "function enter(pi) {\n"
            "    if (pi.getPlayer().getMap().countMonsters() > 0) {\n"
            '        pi.playerMessage(5, "必须先消灭这张地图上的所有怪物，才能离开。");\n'
            "        return false;\n"
            "    }\n"
            "    if (pi.canHold(4310020, 50)) {\n"
            "        pi.gainItem(4310020, 50);\n"
            '        pi.playerMessage(5, "获得了 50 枚怪物公园纪念币。");\n'
            "    } else {\n"
            '        pi.playerMessage(5, "其他栏已满，未能领取怪物公园纪念币。");\n'
            "    }\n"
            "    pi.playPortalSE();\n"
            '    pi.warp(951000400, "sp");\n'
            "    return true;\n"
            "}\n"
        ),
        "Extreme_out2.js": (
            "function enter(pi) {\n"
            "    pi.playPortalSE();\n"
            '    pi.warp(951000000, "sp");\n'
            "    return true;\n"
            "}\n"
        ),
    }
    for tree in ("scripts", "scripts-zh-CN"):
        for name, body in scripts.items():
            path = ROOT / "gms-server" / tree / "portal" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")


def migrate_extreme_park_maps() -> dict[str, object]:
    dependencies = {
        "assets": defaultdict(set),
        "mobs": set(),
        "npcs": set(),
        "bgms": set(),
        "marks": set(),
    }
    totals: dict[str, object] = {"maps": 0}
    for map_id in EXTREME_PARK_MAP_IDS:
        source = source_map_path(map_id)
        client = client_map_path(map_id)
        if client.exists():
            image = load_checked(client, arc.GMS_KEY)
        else:
            image, _materializer = arc.clone_image(
                source,
                lambda root, value=map_id: sanitize_field(root, value),
            )
            if image.truncated or image.parse_warnings:
                raise RuntimeError(
                    f"{map_id}.img: truncated={image.truncated} warnings={image.parse_warnings}"
                )
            arc.write_client_image(client, image)
        totals["maps"] += 1
        arc.merge_dependency_sets(dependencies, arc.collect_dependencies(image))
        for tree in ("wz", "wz-zh-CN"):
            server = server_map_path(tree, map_id)
            if not server.parent.exists():
                continue
            if not server.exists():
                arc.write_server_image(server, image, f"{map_id}.img")
    write_extreme_portal_scripts()
    totals["assets"] = merge_assets_tolerant(dependencies)
    totals["marks"] = arc.merge_map_marks(dependencies["marks"])
    totals["bgms"] = arc.migrate_bgms(dependencies["bgms"])
    totals["strings"] = upsert_map_strings(EXTREME_PARK_MAP_IDS)
    leftover = {}
    for map_id in EXTREME_PARK_MAP_IDS:
        image = load_checked(client_map_path(map_id), arc.GMS_KEY)
        pt_names, tm_names = inner_portal_edits(map_id, image.root)
        if pt_names or tm_names:
            leftover[map_id] = (pt_names, tm_names)
    if leftover:
        raise RuntimeError(f"extreme park inner portals still pending {leftover}")
    return totals


def main() -> int:
    if "--migrate-extreme" in sys.argv or "--repair-portals" in sys.argv:
        if "--migrate-extreme" in sys.argv or not client_map_path(951000300).is_file():
            print("extreme park", migrate_extreme_park_maps())
    if "--write-park-scripts" in sys.argv:
        print("park gameplay scripts", write_park_gameplay_scripts())
        return 0
    if "--repair-obj-gaps" in sys.argv:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import repair_monster_park_late_course_obj_gaps as park_obj

        print("modern obj/connect/gap repair", park_obj.main())
        return 0
    if "--repair-ballistic" in sys.argv:
        print("twilight ballistic", repair_twilight_ballistic_mobs())
        print("arcane river ballistic", repair_arcane_river_ballistic_mobs())
        leftover = iter_incomplete_ballistic_attacks(arcane_river_mob_ids())
        if leftover:
            raise RuntimeError(f"864* ball attacks still incomplete: {leftover}")
        return 0
    if "--repair-park-combat" in sys.argv:
        print("auto-guard park mobs", repair_auto_guard_park_mobs())
        print("auto-guard object r strip", strip_auto_guard_object_r())
        return 0
    if "--repair-portals" in sys.argv:
        print("portal repair", repair_looping_portals())
        print("tile repair", repair_legacy_tilesets())
        print("combat stat repair", repair_twilight_combat_stats())
        print("ballistic repair", repair_twilight_ballistic_mobs())
        print("auto-guard park mobs", repair_auto_guard_park_mobs())
        print("auto-guard object r strip", strip_auto_guard_object_r())
        return 0
    if "--migrate-extreme" in sys.argv:
        return 0
    if "--strip-obj-links" in sys.argv:
        print("obj canvas link strip", strip_park_obj_canvas_links())
        return 0
    if "--strip-life-fields" in sys.argv:
        print("lobby npc info", strip_lobby_npc_modern_info())
        print("life field strip", strip_modern_life_fields())
        return 0
    if "--repair-lobby" in sys.argv:
        print("lobby shared repair", repair_lobby_shared_resources())
        return 0
    if not SOURCE.exists() or not arc.MS_PROBE.exists():
        raise SystemExit("TMS IMG source or MSProbe is missing")
    print(f"maps {len(MAP_IDS)}")
    dependencies, map_stats = migrate_maps()
    print("maps", map_stats)
    print(
        "dependencies",
        {name: len(dependencies[name]) for name in ("assets", "mobs", "npcs", "bgms", "marks")},
    )
    print("map assets", merge_assets_tolerant(dependencies))
    print("map marks", arc.merge_map_marks(dependencies["marks"]))
    print("npcs", migrate_npcs(dependencies["npcs"]))
    print("mobs", arc.migrate_mobs(dependencies["mobs"]))
    print("ballistic repair", repair_twilight_ballistic_mobs())
    print("combat stat repair", repair_twilight_combat_stats())
    print("auto-guard park mobs", repair_auto_guard_park_mobs())
    print("auto-guard object r strip", strip_auto_guard_object_r())
    print("bgms", arc.migrate_bgms(dependencies["bgms"]))
    print("map strings", upsert_map_strings(MAP_IDS))
    print(
        "entity strings",
        {
            "client_mobs": arc.upsert_client_strings("Mob", dependencies["mobs"]),
            "client_npcs": arc.upsert_client_strings("Npc", dependencies["npcs"]),
            "wz_mobs": arc.upsert_server_strings("wz", "Mob", dependencies["mobs"]),
            "wz_npcs": arc.upsert_server_strings("wz", "Npc", dependencies["npcs"]),
            "zh_mobs": arc.upsert_server_strings("wz-zh-CN", "Mob", dependencies["mobs"]),
            "zh_npcs": arc.upsert_server_strings("wz-zh-CN", "Npc", dependencies["npcs"]),
        },
    )
    migrate_etc_items(tuple(dict.fromkeys(item_id for _, item_id, _ in COLLECTION_DROPS)))
    migrate_consume_items(CONSUME_IDS)
    migrate_medals()
    migrate_quests()
    write_drop_sql({int(mob_id) for mob_id in dependencies["mobs"] if int(mob_id) >= 9800000})
    patch_warp_script()
    print("park gameplay scripts", write_park_gameplay_scripts())
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
