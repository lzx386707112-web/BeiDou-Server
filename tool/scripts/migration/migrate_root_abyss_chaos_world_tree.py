#!/usr/bin/env python3
"""Keep Root Abyss chaos maps, drop normal bosses, and migrate Fallen World Tree."""

from __future__ import annotations

import io
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_lion_king_castle as lion  # noqa: E402
from migrate_twilight_perion_monster_park import (  # noqa: E402
    add_int,
    add_string,
    iter_incomplete_ballistic_attacks,
    load_checked,
    repair_ballistic_mobs,
)
from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
)
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.incremental_img import (  # noqa: E402
    _apply_edits,
    _count_edit,
    _find_list,
    _record_bytes,
    _reference_edits,
    _size_edits,
    scan_img,
)
from wzpy.reader import WzBinaryReader  # noqa: E402


HUB_MAP = 105200000
WORLD_TREE_MAP = 105300000
CHAOS_GARDENS = (105200500, 105200600, 105200700, 105200800)
CHAOS_BOSS_ROOMS = (105200510, 105200610, 105200710, 105200810)
KEEP_EXTRA_CHAOS = (
    105200520,
    105200900,
    105201000,
    105201100,
    105201200,
    105201300,
)
WORLD_TREE_MAPS = tuple(
    sorted(int(path.stem) for path in (SOURCE / "Map/Map/Map1").glob("1053*.img"))
)
MAP_IDS = (HUB_MAP, *CHAOS_GARDENS, *CHAOS_BOSS_ROOMS, *KEEP_EXTRA_CHAOS, *WORLD_TREE_MAPS)
MAP_ID_SET = set(MAP_IDS)
NORMAL_MAPS = (
    105200100, 105200110, 105200120,
    105200200, 105200210,
    105200300, 105200310,
    105200400, 105200410,
    *range(105200901, 105200910),
)
NORMAL_BOSS_MOBS = (
    8900100, 8900101, 8900102,
    8910100, 8910101,
    8920100, 8920101, 8920102, 8920103, 8920104, 8920105, 8920106,
    8930100, 8930101,
)
ADVANCED_BOSSES = (8900000, 8900001, 8900002, 8900003, 8910000, 8910001, 8920000, 8920001, 8930000, 8930001)
BOSS_ROOM_SPAWNS = {
    105200510: (8910000, 489, 454),
    105200610: (8900000, -131, 550),
    105200710: (8920000, 60, 134),
    105200810: (8930000, -192, 442),
}
KEEP_PORTAL_SCRIPTS = {
    "rootafirstDoor", "rootasecondDoor", "rootathirdDoor", "rootaforthDoor",
    "rootabyssOUT", "rootabyssGardenOut", "rootahiddenDoor", "rootaNext",
    "outrootaBoss", "shijieshu", "banbanGoInside",
}
SCRIPTED_PORTALS = {
    105200000: {
        "boss00": "rootafirstDoor",
        "boss01": "rootasecondDoor",
        "boss02": "rootathirdDoor",
        "boss03": "rootaforthDoor",
        "goOut00": "rootabyssOUT",
        "goOut01": "rootabyssOUT",
        "in00": "rootahiddenDoor",
    },
    105200500: {"next00": "rootaNext", "out00": "rootabyssGardenOut"},
    105200600: {"next00": "rootaNext", "out00": "rootabyssGardenOut"},
    105200700: {"next00": "rootaNext", "out00": "rootabyssGardenOut"},
    105200800: {"next00": "rootaNext", "out00": "rootabyssGardenOut"},
    105200510: {"hid00": "outrootaBoss"},
    105200610: {"hid00": "outrootaBoss"},
    105200710: {"hid00": "outrootaBoss"},
    105200810: {"hid00": "outrootaBoss"},
}
CASH_NPC_PREFIXES = ("90", "91", "92", "93", "94")
KEEP_ON_USER_ENTER = {
    105200510: "rootaBossEnter",
    105200610: "rootaBossEnter",
    105200710: "rootaBossEnter",
    105200810: "rootaBossEnter",
}
ULTIMATE_EFFECTS = {
    8900000: "customSkill/rootAbyss/pierreVideoLayer",
    8910000: "customSkill/rootAbyss/vonBonVideoLayer",
    8920000: "customSkill/rootAbyss/queenVideoLayer",
    8930000: "customSkill/rootAbyss/vellumVideoLayer",
}


def source_map_path(map_id: int) -> Path:
    return SOURCE / f"Map/Map/Map{str(map_id)[0]}/{map_id}.img"


def client_map_path(map_id: int) -> Path:
    return ROOT / f"clien/Data/Map/Map/Map{str(map_id)[0]}/{map_id}.img"


def server_map_path(tree: str, map_id: int) -> Path:
    return ROOT / f"gms-server/{tree}/Map.wz/Map/Map{str(map_id)[0]}/{map_id}.img.xml"


def decode_canvases(node) -> None:
    if isinstance(node, WzCanvasProperty):
        decode_canvas(node)
    if hasattr(node, "children"):
        for child in node.children():
            decode_canvases(child)


def densify_numeric(parent: WzSubProperty) -> None:
    numbered = [child for child in parent.children() if child.name.isdigit()]
    if not numbered:
        return
    ordered = sorted(numbered, key=lambda child: int(child.name))
    if [child.name for child in ordered] == [str(index) for index in range(len(ordered))]:
        return
    for child in ordered:
        parent._children.pop(child.name, None)
    for index, child in enumerate(ordered):
        child.name = str(index)
        parent.add(child)


def densify_map_nodes(root: WzSubProperty) -> None:
    back = root.child("back")
    if isinstance(back, WzSubProperty):
        densify_numeric(back)
    for layer in [child for child in root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if isinstance(objects, WzSubProperty):
            densify_numeric(objects)


def is_cash_npc(npc_id: int) -> bool:
    text = str(npc_id)
    return any(text.startswith(prefix) for prefix in CASH_NPC_PREFIXES)


def sanitize_field(root: WzSubProperty, map_id: int) -> None:
    for child in list(root.children()):
        if child.name not in arc.MAP_ROOTS:
            arc.remove_child(root, child.name)
    info = root.child("info")
    if isinstance(info, WzSubProperty):
        for name in arc.MAP_INFO_UNSUPPORTED:
            if name not in {"onUserEnter", "onFirstUserEnter"}:
                arc.remove_child(info, name)
        mark = str(arc.child_value(info, "mapMark") or "")
        if mark in {"rootabyss", "fallenWorldTree"}:
            arc.remove_child(info, "mapMark")
        enter = KEEP_ON_USER_ENTER.get(map_id)
        if enter:
            arc.set_string(info, "onUserEnter", enter)
        else:
            arc.remove_child(info, "onUserEnter")
            arc.remove_child(info, "onFirstUserEnter")
        for name in ("returnMap", "forcedReturn"):
            value = arc.child_value(info, name)
            if name == "forcedReturn" and value == 999999999:
                continue
            if isinstance(value, int) and value != 999999999 and value not in MAP_ID_SET:
                arc.set_int(info, name, HUB_MAP if map_id >= 105200000 else WORLD_TREE_MAP)
        if map_id == WORLD_TREE_MAP:
            arc.set_int(info, "returnMap", HUB_MAP)

    life = root.child("life")
    if isinstance(life, WzSubProperty):
        for entry in list(life.children()):
            if arc.child_value(entry, "type") == "n":
                npc_id = int(arc.child_value(entry, "id"))
                hidden = int(arc.child_value(entry, "hide") or 0) != 0
                if hidden or npc_id in arc.REMOVED_NPCS or is_cash_npc(npc_id):
                    arc.remove_child(life, entry.name)
                    continue
            if arc.child_value(entry, "type") == "m":
                mob_id = int(arc.child_value(entry, "id"))
                if mob_id in NORMAL_BOSS_MOBS:
                    arc.remove_child(life, entry.name)
                    continue
            for name in arc.LIFE_UNSUPPORTED:
                arc.remove_child(entry, name)

    for layer in [child for child in root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if isinstance(objects, WzSubProperty):
            for entry in list(objects.children()):
                if entry.child("spineAni") is not None:
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
    if isinstance(portal, WzSubProperty):
        for entry in list(portal.children()):
            script = str(arc.child_value(entry, "script") or "")
            target = arc.child_value(entry, "tm")
            pt = int(arc.child_value(entry, "pt") or 0)
            if pt == 11:
                arc.set_int(entry, "pt", 7)
            if map_id == WORLD_TREE_MAP and arc.child_value(entry, "pn") == "in00":
                arc.set_int(entry, "pt", 2)
                arc.set_int(entry, "tm", HUB_MAP)
                arc.set_string(entry, "tn", "sp")
                arc.remove_child(entry, "script")
            elif script in KEEP_PORTAL_SCRIPTS:
                pass
            elif isinstance(target, int) and target != 999999999 and target not in MAP_ID_SET:
                if target in NORMAL_MAPS:
                    arc.remove_child(portal, entry.name)
                    continue
                arc.set_int(entry, "tm", HUB_MAP)
                arc.set_string(entry, "tn", "sp")
                arc.remove_child(entry, "script")
            if script and script not in KEEP_PORTAL_SCRIPTS:
                arc.remove_child(entry, "script")
            for name in arc.PORTAL_UNSUPPORTED:
                arc.remove_child(entry, name)
        arc.downgrade_portal_types(root)
    densify_map_nodes(root)


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
        image, materializer = arc.clone_image(
            source,
            lambda root, value=map_id: sanitize_field(root, value),
        )
        decode_canvases(image.root)
        if image.truncated or image.parse_warnings:
            raise RuntimeError(f"cloned map {map_id} parse failed")
        arc.write_client_image(client, image)
        arc.merge_dependency_sets(dependencies, arc.collect_dependencies(image))
        for tree in ("wz", "wz-zh-CN"):
            server = server_map_path(tree, map_id)
            if not server.parent.exists():
                continue
            arc.write_server_image(server, image, f"{map_id}.img")
        totals["maps"] += 1
        totals["canvases"] += materializer.canvases
        totals["links"] += materializer.links
        totals["resized"] += materializer.resized
    return dependencies, totals


def delete_normal_content() -> dict[str, int]:
    removed = {"maps": 0, "mobs": 0}
    for map_id in NORMAL_MAPS:
        for path in (
            client_map_path(map_id),
            server_map_path("wz", map_id),
            server_map_path("wz-zh-CN", map_id),
        ):
            if path.is_file():
                path.unlink()
                removed["maps"] += 1
    for mob_id in NORMAL_BOSS_MOBS:
        for path in (
            ROOT / f"clien/Data/Mob/{mob_id}.img",
            ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml",
            ROOT / f"gms-server/wz-zh-CN/Mob.wz/{mob_id}.img.xml",
        ):
            if path.is_file():
                path.unlink()
                removed["mobs"] += 1
    return removed


def migrate_npcs(npc_ids: set[int]) -> dict[str, int]:
    totals = {"npcs": 0, "canvases": 0, "links": 0, "resized": 0}
    for npc_id in sorted(npc_ids):
        canvases, links, resized = lion.migrate_one_entity("Npc", npc_id)
        totals["npcs"] += 1
        totals["canvases"] += canvases
        totals["links"] += links
        totals["resized"] += resized
    return totals


def migrate_local_mobs(mob_ids: set[int]) -> dict[str, int]:
    totals = {"mobs": 0, "canvases": 0, "links": 0, "resized": 0}
    for mob_id in sorted(mob_ids):
        if mob_id in ADVANCED_BOSSES or mob_id in NORMAL_BOSS_MOBS:
            continue
        canvases, links, resized = lion.migrate_one_entity("Mob", mob_id)
        totals["mobs"] += 1
        totals["canvases"] += canvases
        totals["links"] += links
        totals["resized"] += resized
    return totals


def make_portal_node(name: str) -> WzSubProperty:
    portal = WzSubProperty(name)
    add_string(portal, "pn", "shijieshu")
    add_int(portal, "pt", 8)
    add_int(portal, "x", 388)
    add_int(portal, "y", -372)
    add_int(portal, "tm", 999999999)
    add_string(portal, "tn", "")
    add_string(portal, "script", "shijieshu")
    return portal


def insert_shijieshu_portal() -> None:
    client = client_map_path(HUB_MAP)
    image = load_checked(client, arc.GMS_KEY)
    portal = image.root.child("portal")
    if not isinstance(portal, WzSubProperty):
        raise RuntimeError("105200000 missing portal")
    if any(arc.child_value(entry, "pn") == "shijieshu" for entry in portal.children()):
        lion.restore_map_portal_scripts(HUB_MAP, {"shijieshu": "shijieshu"})
        return
    next_name = str(max(int(child.name) for child in portal.children() if child.name.isdigit()) + 1)
    original = client.read_bytes()
    node = make_portal_node(next_name)
    layout = scan_img(original, region="GMS")
    prop_list, ancestors = _find_list(layout.root, ("portal",))
    reader = WzBinaryReader(io.BytesIO(original), arc.GMS_KEY)
    record = _record_bytes(node, reader)
    count_edit = _count_edit(prop_list, prop_list.count + 1)
    count_delta = len(count_edit[2]) - (count_edit[1] - count_edit[0])
    delta = len(record) + count_delta
    edits = [
        (prop_list.end, prop_list.end, record),
        count_edit,
        *_size_edits(ancestors, delta),
    ]
    edits.extend(_reference_edits(layout, edits))
    patched = arc.verified_image_bytes(_apply_edits(original, edits), client.name)
    before_records, _ = arc.raw_record_state(original)
    after_records, after_orders = arc.raw_record_state(patched)
    for child in portal.children():
        path = ("portal", child.name)
        if before_records[path] != after_records.get(path):
            raise RuntimeError(f"105200000 changed existing portal {child.name}")
    if ("portal", next_name) not in after_records:
        raise RuntimeError("105200000 missing inserted shijieshu portal")
    if after_orders[("portal",)][:-1] != tuple(child.name for child in portal.children()):
        raise RuntimeError("105200000 reordered existing portals")
    checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=client.name)
    checked.parse()
    if checked.truncated or checked.parse_warnings:
        raise RuntimeError("105200000 parse failed after shijieshu insert")
    decode_canvases(checked.root)
    arc.atomic_write_bytes(client, patched)
    for tree in ("wz", "wz-zh-CN"):
        server = server_map_path(tree, HUB_MAP)
        if not server.exists():
            continue
        text = server.read_text(encoding="utf-8")
        xml_root = ET.fromstring(text)
        info = xml_root.find('./imgdir[@name="portal"]')
        if info is None:
            continue
        if any(
            child.find('./string[@name="pn"]') is not None
            and child.find('./string[@name="pn"]').get("value") == "shijieshu"
            for child in info
        ):
            continue
        updated = arc.append_xml_properties(text, ("portal",), [make_portal_node(next_name)])
        arc.atomic_write_text(server, updated)


def restore_scripted_portals() -> None:
    for map_id, scripts in SCRIPTED_PORTALS.items():
        if client_map_path(map_id).is_file():
            lion.restore_map_portal_scripts(map_id, scripts)


def write_script(relative: str, contents: str) -> None:
    for tree in ("scripts-zh-CN", "scripts"):
        path = ROOT / "gms-server" / tree / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")


def rewrite_ids(relative: str, replacements: dict[str, str]) -> None:
    for tree in ("scripts-zh-CN", "scripts"):
        path = ROOT / "gms-server" / tree / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")


def write_gameplay_scripts() -> None:
    write_script(
        "portal/rootafirstDoor.js",
        "function enter(pi) {\n    pi.playPortalSound();\n    pi.warp(105200500, \"sp\");\n    return true;\n}\n",
    )
    write_script(
        "portal/rootasecondDoor.js",
        "function enter(pi) {\n    pi.playPortalSound();\n    pi.warp(105200600, \"sp\");\n    return true;\n}\n",
    )
    write_script(
        "portal/rootathirdDoor.js",
        "function enter(pi) {\n    pi.playPortalSound();\n    pi.warp(105200700, \"sp\");\n    return true;\n}\n",
    )
    write_script(
        "portal/rootaforthDoor.js",
        "function enter(pi) {\n    pi.playPortalSound();\n    pi.warp(105200800, \"sp\");\n    return true;\n}\n",
    )
    write_script(
        "portal/rootaNext.js",
        """function enter(pi) {
    var targets = {
        105200500: 105200510,
        105200600: 105200610,
        105200700: 105200710,
        105200800: 105200810
    };
    var target = targets[pi.getMapId()];
    if (target == null) {
        return false;
    }
    pi.playPortalSound();
    pi.warp(target, "sp");
    return true;
}
""",
    )
    write_script(
        "map/onUserEnter/rootaBossEnter.js",
        """var BOSS_SPAWNS = {
    105200510: [8910000, 489, 454],
    105200610: [8900000, -131, 550],
    105200710: [8920000, 60, 134],
    105200810: [8930000, -192, 442]
};

function start(ms) {
    var spawn = BOSS_SPAWNS[ms.getMapId()];
    if (spawn == null || ms.countMonster() > 0) {
        return true;
    }
    var LifeFactory = Java.type("org.gms.server.life.LifeFactory");
    var Point = Java.type("java.awt.Point");
    ms.getPlayer().getMap().spawnMonsterOnGroundBelow(LifeFactory.getMonster(spawn[0]), new Point(spawn[1], spawn[2]));
    return true;
}
""",
    )
    write_script(
        "portal/shijieshu.js",
        """function enter(pi) {
    pi.playPortalSound();
    pi.warp(105300000, "sp");
    return true;
}
""",
    )
    write_script(
        "map/onUserEnter/enter_105300000.js",
        "function start(ms) {\n    return true;\n}\n",
    )
    door = """let status = -1;

function start() {
    cm.sendYesNo("%s");
}

function action(mode, type, selection) {
    if (mode === 1) {
        cm.warp(%s, "sp");
    }
    cm.dispose();
}
"""
    write_script("npc/rootaFirstDoorSelect.js", door % ("进入皮埃尔混沌庭院？", 105200500))
    write_script("npc/rootaSecondDoorSelect.js", door % ("进入半半混沌庭院？", 105200600))
    write_script("npc/rootaThirdDoorSelect.js", door % ("进入血腥女王混沌庭院？", 105200700))
    write_script("npc/rootaFourthDoorSelect.js", door % ("进入贝伦混沌庭院？", 105200800))
    rewrite_ids(
        "event/PIERREBattle.js",
        {
            "105200211": "105200610",
            "8900100": "8900000",
            "8900101": "8900001",
            "8900102": "8900002",
        },
    )
    rewrite_ids(
        "event/VONBONBattle.js",
        {"105200111": "105200510", "8910100": "8910000"},
    )
    rewrite_ids(
        "event/CQBattle.js",
        {"105200311": "105200710", "8920101": "8920000", "8920106": "8920006"},
    )
    rewrite_ids(
        "event/VELLUMBattle.js",
        {"105200411": "105200810", "8930100": "8930000"},
    )


def write_npc_stubs(npc_ids: set[int]) -> None:
    for npc_id in sorted(npc_ids):
        relative = f"npc/{npc_id}.js"
        existing = ROOT / "gms-server/scripts-zh-CN" / relative
        if existing.is_file():
            continue
        write_script(
            relative,
            """function start() {
    cm.sendOk("堕落世界树已经和鲁塔比斯连通。");
    cm.dispose();
}

function action(mode, type, selection) {
    cm.dispose();
}
""",
        )


def numeric_gaps(parent: WzSubProperty | None) -> list[int]:
    if not isinstance(parent, WzSubProperty):
        return []
    names = {int(child.name) for child in parent.children() if child.name.isdigit()}
    if not names:
        return []
    return [index for index in range(max(names) + 1) if index not in names]


def maps_needing_repair() -> list[int]:
    broken = []
    for map_id in MAP_IDS:
        path = client_map_path(map_id)
        if not path.is_file():
            broken.append(map_id)
            continue
        image = load_checked(path, arc.GMS_KEY)
        if numeric_gaps(image.root.child("back")):
            broken.append(map_id)
            continue
        for layer in [child for child in image.root.children() if child.name.isdigit()]:
            if numeric_gaps(layer.child("obj")):
                broken.append(map_id)
                break
    return broken


def main() -> int:
    arc.ROOT = ROOT
    arc.BACKUP_ROOT = Path("/private/tmp/root-abyss-chaos-world-tree-backup")
    arc.MAP_IDS = MAP_IDS
    arc.MAP_ID_SET = MAP_ID_SET
    lion.ROOT = ROOT
    lion.SOURCE = SOURCE
    if not SOURCE.exists():
        raise SystemExit("TMS IMG source is missing")
    print("delete", delete_normal_content())
    print(f"maps {len(MAP_IDS)}")
    dependencies, map_stats = migrate_maps()
    print("maps", map_stats)
    print("map assets", lion.merge_assets_tolerant(dependencies))
    print("npcs", migrate_npcs(dependencies["npcs"]))
    print("mobs", migrate_local_mobs(dependencies["mobs"]))
    leftover = iter_incomplete_ballistic_attacks(tuple(sorted(dependencies["mobs"] - set(ADVANCED_BOSSES))))
    if leftover:
        print("ballistic", repair_ballistic_mobs(tuple(sorted(dependencies["mobs"] - set(ADVANCED_BOSSES)))))
        leftover = iter_incomplete_ballistic_attacks(tuple(sorted(dependencies["mobs"] - set(ADVANCED_BOSSES))))
        if leftover:
            raise RuntimeError(f"incomplete ballistic attacks: {leftover}")
    print("bgms", arc.migrate_bgms(dependencies["bgms"]))
    print("map strings", {
        "client": arc.upsert_client_strings("Map", MAP_IDS, "victoria"),
        "wz": arc.upsert_server_strings("wz", "Map", MAP_IDS, "victoria"),
        "zh": arc.upsert_server_strings("wz-zh-CN", "Map", MAP_IDS, "victoria"),
    })
    print("entity strings", {
        "client_mobs": arc.upsert_client_strings("Mob", dependencies["mobs"]),
        "client_npcs": arc.upsert_client_strings("Npc", dependencies["npcs"]),
        "wz_mobs": arc.upsert_server_strings("wz", "Mob", dependencies["mobs"]),
        "wz_npcs": arc.upsert_server_strings("wz", "Npc", dependencies["npcs"]),
        "zh_mobs": arc.upsert_server_strings("wz-zh-CN", "Mob", dependencies["mobs"]),
        "zh_npcs": arc.upsert_server_strings("wz-zh-CN", "Npc", dependencies["npcs"]),
    })
    restore_scripted_portals()
    insert_shijieshu_portal()
    write_gameplay_scripts()
    write_npc_stubs(dependencies["npcs"])
    broken = maps_needing_repair()
    if broken:
        raise RuntimeError(f"obj/back gaps remain: {broken}")
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
