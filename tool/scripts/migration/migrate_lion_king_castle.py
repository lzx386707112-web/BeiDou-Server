#!/usr/bin/env python3
"""Migrate TMS Lion King's Castle field maps and quests; skip Van Leon battles."""

from __future__ import annotations

import io
import re
import shutil
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
from migrate_twilight_perion_monster_park import (  # noqa: E402
    add_int,
    add_string,
    add_sub,
    append_named_records,
    append_server_named,
    first_existing_anchor,
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
    WzVectorProperty,
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


# Field/tower maps plus the corridor that leads into the existing audience room.
MAP_IDS = (
    211060000,
    211060010,
    211060100,
    211060200,
    211060201,
    211060300,
    211060400,
    211060401,
    211060410,
    211060500,
    211060600,
    211060601,
    211060610,
    211060620,
    211060700,
    211060800,
    211060801,
    211060810,
    211060820,
    211060830,
    211060900,
    211061000,
    211061001,
    211061100,
    211061200,
    211061210,
    211070000,
    211080000,
    211080100,
    211080200,
    211080300,
    211080400,
    211080500,
    211080600,
)
MAP_ID_SET = set(MAP_IDS)
VAN_LEON_BATTLE_MAPS = {
    211070100,
    211070101,
    211070102,
    211070103,
    211070104,
    211070105,
    211070110,
    211070111,
    211070112,
    211070200,
    211070300,
    211070350,
    211070400,
    211070450,
    211070500,
    211070550,
}
ENTRANCE_FROM_MAP = 211040600
CASTLE_MAP = 211060000
ROSE_GARDEN_MAP = 211080000
FIFTH_TOWER_ROOF = 211061001
EXTRA_REMOVED_NPCS: set[int] = set()
KEEP_HIDDEN_NPCS = {2161005}
KEEP_PORTAL_SCRIPTS = {
    "lionCastle_enter",
    "BPReturn_Vanleon",
    "BPReturnVanleon2",
    "portalNPC",
    "enterVL00",
    "lioncastleout",
    "pt_rosegarden",
    "pt_rosegardenout",
    "gotoNext1",
    "1stTowerTop",
    "gotoNext2_1",
    "gotoNext2_2",
    "2ndTowerTop",
    "gotoNext3_1",
    "gotoNext3_2",
    "gotoNext3_3",
    "3rdTowerTop",
    "gotoNext4",
    "gotoAni",
    "out_ani",
    "lionCastleBoss",
}
SCRIPTED_PORTALS = {
    211060200: {"east00": "gotoNext1", "up00": "1stTowerTop"},
    211060400: {"out00": "gotoNext2_2", "east00": "gotoNext2_1", "up00": "2ndTowerTop"},
    211060600: {
        "east00": "gotoNext3_1",
        "out01": "gotoNext3_2",
        "out10": "gotoNext3_3",
        "up00": "3rdTowerTop",
    },
    211060700: {"east00": "gotoNext4"},
    211060801: {"down00": "BPReturnVanleon2"},
    211061000: {"east00": "gotoAni"},
    211061001: {"next00": "pt_rosegarden"},
    211061100: {"west00": "out_ani"},
    211061210: {"boss00": "lionCastleBoss"},
    211070000: {"lionCastleenter": "enterVL00", "west00": "BPReturn_Vanleon"},
    211080000: {"west00": "pt_rosegardenout"},
}
QUEST_IDS = (
    3163, 3164, 3165, 3166, 3167, 3168, 3169, 3170, 3171, 3172, 3173, 3174,
    3175, 3176, 3177, 3178, 3181, 3182, 3190, 3191, 3192, 3193, 3194, 3198,
    3199,
)
QUEST_NAMES = ("Act", "Check", "QuestInfo", "Say")
ETC_ITEMS = (
    (4000625, "0400.img", "04000625"),
    (4000626, "0400.img", "04000626"),
    (4000627, "0400.img", "04000627"),
    (4000628, "0400.img", "04000628"),
    (4000629, "0400.img", "04000629"),
    (4000630, "0400.img", "04000630"),
    (4032831, "0403.img", "04032831"),
    (4032832, "0403.img", "04032832"),
    (4032833, "0403.img", "04032833"),
    (4032834, "0403.img", "04032834"),
    (4032835, "0403.img", "04032835"),
    (4032836, "0403.img", "04032836"),
    (4032837, "0403.img", "04032837"),
    (4032838, "0403.img", "04032838"),
    (4032839, "0403.img", "04032839"),
    (4032840, "0403.img", "04032840"),
    (4032858, "0403.img", "04032858"),
    (4032859, "0403.img", "04032859"),
    (4310010, "0431.img", "04310010"),
)
CONSUME_ITEMS = ((2030021, "0203.img", "02030021"),)
ANALOGUE_ETC = "04032000"
WARP_SCRIPT = ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/万能传送.js"
ADVANCED_BOSS_WARP = ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/新高级boss传送.js"
RETRY_PORTAL = ROOT / "gms-server/scripts-zh-CN/portal/shenshuoBossRetry.js"
REMOVED_BOSS_MOBS = (8880200, 8880700, 8880830, 8880831, 8880832, 8880837, 8880842)
REMOVED_BOSS_MAPS = (
    221040001,
    900000207,
    410007100,
    410007120,
    410007140,
    410007160,
    410007180,
    410007200,
    410007220,
    410007240,
    410007260,
    410007280,
    410007300,
)


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


def sanitize_field(root: WzSubProperty, map_id: int) -> None:
    for child in list(root.children()):
        if child.name not in arc.MAP_ROOTS:
            arc.remove_child(root, child.name)
    info = root.child("info")
    if isinstance(info, WzSubProperty):
        for name in arc.MAP_INFO_UNSUPPORTED:
            if name not in {"onUserEnter", "onFirstUserEnter"}:
                arc.remove_child(info, name)
        arc.set_int(info, "fieldLimit", 0)
        for name in ("returnMap", "forcedReturn"):
            value = arc.child_value(info, name)
            if name == "forcedReturn" and value == 999999999:
                continue
            if isinstance(value, int) and value != 999999999 and value not in MAP_ID_SET:
                if value in VAN_LEON_BATTLE_MAPS:
                    continue
                if value == ENTRANCE_FROM_MAP:
                    continue
                arc.set_int(info, name, CASTLE_MAP)

    life = root.child("life")
    if isinstance(life, WzSubProperty):
        for entry in list(life.children()):
            if arc.child_value(entry, "type") == "n":
                npc_id = int(arc.child_value(entry, "id"))
                hidden = int(arc.child_value(entry, "hide") or 0) != 0
                if npc_id in arc.REMOVED_NPCS or npc_id in EXTRA_REMOVED_NPCS:
                    arc.remove_child(life, entry.name)
                    continue
                if hidden and npc_id not in KEEP_HIDDEN_NPCS:
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
            if isinstance(target, int) and target in VAN_LEON_BATTLE_MAPS:
                if map_id == 211070000 and script == "portalNPC":
                    pass
                else:
                    arc.set_int(entry, "tm", 211070100)
                    arc.set_string(entry, "tn", "sp")
                    arc.remove_child(entry, "script")
            elif script in KEEP_PORTAL_SCRIPTS:
                pass
            elif isinstance(target, int) and target != 999999999 and target not in (
                MAP_ID_SET | VAN_LEON_BATTLE_MAPS | {ENTRANCE_FROM_MAP, 211070100}
            ):
                arc.remove_child(portal, entry.name)
                continue
            elif script and target == 999999999 and script not in KEEP_PORTAL_SCRIPTS:
                arc.remove_child(entry, "script")
            if script not in KEEP_PORTAL_SCRIPTS:
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
        if client.exists():
            image = load_checked(client, arc.GMS_KEY)
            materializer = arc.CanvasMaterializer()
        else:
            image, materializer = arc.clone_image(
                source,
                lambda root, value=map_id: sanitize_field(root, value),
            )
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
    return totals


def entity_client_path(kind: str, entity_id: int) -> Path:
    unpadded = ROOT / f"clien/Data/{kind}/{entity_id}.img"
    padded = ROOT / f"clien/Data/{kind}/{entity_id:07d}.img"
    return unpadded if unpadded.exists() or not padded.exists() else padded


def entity_source_path(kind: str, entity_id: int) -> Path:
    for candidate in (
        SOURCE / f"{kind}/{entity_id}.img",
        SOURCE / f"{kind}/{entity_id:07d}.img",
    ):
        if candidate.exists():
            return candidate
    if kind == "Mob":
        return arc.extract_mob(entity_id)
    raise FileNotFoundError(f"missing TMS {kind} {entity_id}")


def clone_entity_image(source_path: Path, sanitizer):
    try:
        return arc.clone_image(source_path, sanitizer)
    except Exception:
        image = load_checked(source_path, arc.GMS_KEY)
        if sanitizer is not None:
            sanitizer(image.root)
        materializer = arc.CanvasMaterializer()
        root = WzSubProperty(image.root.name)
        for child in image.root.children():
            root.add(arc.clone_property(child, root, image, source_path, materializer))
        image._root = root
        image._parsed = True
        return image, materializer


def migrate_one_entity(kind: str, entity_id: int) -> tuple[int, int, int]:
    client = entity_client_path(kind, entity_id)
    server = ROOT / f"gms-server/wz/{kind}.wz/{client.name}.xml"
    if not str(server).endswith(".img.xml"):
        server = ROOT / f"gms-server/wz/{kind}.wz/{entity_id}.img.xml"
        if client.name.endswith(".img"):
            server = ROOT / f"gms-server/wz/{kind}.wz/{client.name}.xml"
    if client.exists():
        image = load_checked(client, arc.GMS_KEY)
        if not server.exists():
            arc.write_server_image(server, image, client.name)
        return 0, 0, 0
    source = entity_source_path(kind, entity_id)
    sanitizer = arc.sanitize_npc if kind == "Npc" else (
        lambda root, value=entity_id: arc.sanitize_mob(root, value)
    )
    image, materializer = clone_entity_image(source, sanitizer)
    if kind == "Mob":
        arc.fill_legacy_mob_animation_gap(image, entity_id)
    arc.write_client_image(client, image)
    arc.write_server_image(server, image, client.name)
    return materializer.canvases, materializer.links, materializer.resized


def migrate_npcs(npc_ids: set[int]) -> dict[str, int]:
    totals = {"npcs": 0, "canvases": 0, "links": 0, "resized": 0}
    for npc_id in sorted(npc_ids):
        canvases, links, resized = migrate_one_entity("Npc", npc_id)
        totals["npcs"] += 1
        totals["canvases"] += canvases
        totals["links"] += links
        totals["resized"] += resized
    return totals


def migrate_local_mobs(mob_ids: set[int]) -> dict[str, int]:
    totals = {"mobs": 0, "canvases": 0, "links": 0, "resized": 0}
    for mob_id in sorted(mob_ids):
        canvases, links, resized = migrate_one_entity("Mob", mob_id)
        totals["mobs"] += 1
        totals["canvases"] += canvases
        totals["links"] += links
        totals["resized"] += resized
    return totals


def make_portal_node(name: str) -> WzSubProperty:
    portal = WzSubProperty(name)
    add_int(portal, "x", -422)
    add_int(portal, "y", -1538)
    add_int(portal, "pt", 2)
    add_int(portal, "tm", CASTLE_MAP)
    add_string(portal, "tn", "out00")
    add_string(portal, "pn", "in00")
    return portal


def patch_corridor_audience_script() -> None:
    client = client_map_path(211070000)
    original = client.read_bytes()
    image = load_checked(client, arc.GMS_KEY)
    portal = image.root.child("portal")
    target = None
    for entry in portal.children():
        if arc.child_value(entry, "script") == "portalNPC":
            target = entry.name
            break
        if arc.child_value(entry, "script") == "enterVL00":
            return
    if target is None:
        return
    patched = arc.mutate_img(
        original,
        "edit",
        ("portal", target, "script"),
        values={"value": "enterVL00"},
        region="GMS",
    ).data
    arc.verify_raw_record_scope(
        original, patched, {("portal", target, "script")}, allow_additions=False
    )
    checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=client.name)
    checked.parse()
    if checked.truncated or checked.parse_warnings:
        raise RuntimeError("211070000 parse failed after script rename")
    arc.atomic_write_bytes(client, patched)
    for tree in ("wz", "wz-zh-CN"):
        server = server_map_path(tree, 211070000)
        if not server.exists():
            continue
        text = server.read_text(encoding="utf-8")
        updated = text.replace(
            '<string name="script" value="portalNPC"/>',
            '<string name="script" value="enterVL00"/>',
            1,
        )
        if updated != text:
            arc.atomic_write_text(server, updated)


def make_life_node(name: str, source) -> WzSubProperty:
    node = WzSubProperty(name)
    add_string(node, "type", str(arc.child_value(source, "type")))
    add_string(node, "id", str(arc.child_value(source, "id")))
    for field in ("x", "y", "mobTime", "f", "hide", "fh", "cy", "rx0", "rx1"):
        value = arc.child_value(source, field)
        add_int(node, field, int(value or 0))
    return node


def patch_corridor_life() -> None:
    client = client_map_path(211070000)
    image = load_checked(client, arc.GMS_KEY)
    life = image.root.child("life")
    if not isinstance(life, WzSubProperty):
        raise RuntimeError("211070000 missing life")
    existing = {
        str(arc.child_value(entry, "id"))
        for entry in life.children()
        if arc.child_value(entry, "type") == "n"
    }
    source = arc.load_image(source_map_path(211070000), arc.BMS_KEY)
    source_life = source.root.child("life")
    if not isinstance(source_life, WzSubProperty):
        raise RuntimeError("TMS 211070000 missing life")
    additions = []
    next_name = 0
    if any(child.name.isdigit() for child in life.children()):
        next_name = max(int(child.name) for child in life.children() if child.name.isdigit()) + 1
    for entry in source_life.children():
        npc_id = str(arc.child_value(entry, "id"))
        if npc_id in existing:
            continue
        additions.append(make_life_node(str(next_name), entry))
        next_name += 1
    if not additions:
        return
    data = client.read_bytes()
    for node in additions:
        data = append_record_with_refs(data, ("life",), node, client.name)
    arc.atomic_write_bytes(client, data)
    for tree in ("wz", "wz-zh-CN"):
        server = server_map_path(tree, 211070000)
        if server.exists():
            append_server_named(server, ("life",), additions)


def patch_rose_garden_portal() -> None:
    client = client_map_path(FIFTH_TOWER_ROOF)
    original = client.read_bytes()
    image = load_checked(client, arc.GMS_KEY)
    portal = image.root.child("portal")
    target = None
    for entry in portal.children():
        if arc.child_value(entry, "pn") != "next00":
            continue
        if arc.child_value(entry, "script") == "pt_rosegarden":
            return
        target = entry.name
        break
    if target is None:
        raise RuntimeError("211061001 missing next00 portal")
    script = WzStringProperty("script", "pt_rosegarden")
    patched = append_record_with_refs(original, ("portal", target), script, client.name)
    if patched != original:
        arc.atomic_write_bytes(client, patched)
    for tree in ("wz", "wz-zh-CN"):
        server = server_map_path(tree, FIFTH_TOWER_ROOF)
        if not server.exists():
            continue
        text = server.read_text(encoding="utf-8")
        if "pt_rosegarden" in text:
            continue
        updated = text.replace(
            '<string name="pn" value="next00"/>',
            '<string name="pn" value="next00"/>\n      <string name="script" value="pt_rosegarden"/>',
            1,
        )
        if updated != text:
            arc.atomic_write_text(server, updated)


def upsert_xml_portal_script(path: Path, pn: str, script: str) -> None:
    if not path.exists():
        return
    original = path.read_text(encoding="utf-8")
    marker = f'<string name="pn" value="{pn}"/>'
    idx = original.find(marker)
    if idx < 0:
        return
    close = original.find("</imgdir>", idx)
    chunk = original[idx:close]
    if f'<string name="script" value="{script}"/>' in chunk:
        return
    if '<string name="script"' in chunk:
        updated_chunk = re.sub(
            r'<string name="script" value="[^"]*"/>',
            f'<string name="script" value="{script}"/>',
            chunk,
            count=1,
        )
        updated = original[:idx] + updated_chunk + original[close:]
    else:
        updated = original[:idx] + marker + f'\n      <string name="script" value="{script}"/>' + original[idx + len(marker):]
    if updated != original:
        arc.atomic_write_text(path, updated)


def restore_map_portal_scripts(map_id: int, scripts: dict[str, str]) -> None:
    client = client_map_path(map_id)
    for pn, script_name in scripts.items():
        original = client.read_bytes()
        image = load_checked(client, arc.GMS_KEY)
        portal = image.root.child("portal")
        if not isinstance(portal, WzSubProperty):
            raise RuntimeError(f"{map_id} missing portal")
        target = None
        current = ""
        for entry in portal.children():
            if arc.child_value(entry, "pn") != pn:
                continue
            target = entry.name
            current = str(arc.child_value(entry, "script") or "")
            break
        if target is None:
            raise RuntimeError(f"{map_id} missing portal {pn}")
        if current == script_name:
            continue
        if current:
            patched = arc.mutate_img(
                original,
                "edit",
                ("portal", target, "script"),
                values={"value": script_name},
                region="GMS",
            ).data
            arc.verify_raw_record_scope(
                original, patched, {("portal", target, "script")}, allow_additions=False
            )
        else:
            patched = append_record_with_refs(
                original, ("portal", target), WzStringProperty("script", script_name), client.name
            )
        checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=client.name)
        checked.parse()
        if checked.truncated or checked.parse_warnings:
            raise RuntimeError(f"{map_id} parse failed after restoring {pn}")
        restored = None
        for entry in checked.root.child("portal").children():
            if arc.child_value(entry, "pn") == pn:
                restored = arc.child_value(entry, "script")
                break
        if restored != script_name:
            raise RuntimeError(f"{map_id} {pn} script is {restored!r}")
        arc.atomic_write_bytes(client, patched)
        upsert_xml_portal_script(server_map_path("wz", map_id), pn, script_name)
        upsert_xml_portal_script(server_map_path("wz-zh-CN", map_id), pn, script_name)


def restore_scripted_portals() -> None:
    for map_id, scripts in SCRIPTED_PORTALS.items():
        restore_map_portal_scripts(map_id, scripts)
    restore_map_portal_scripts(211070100, {"lioncastleout": "lioncastleout"})


def clone_field_mob(source_id: int, dest_id: int) -> None:
    source_client = entity_client_path("Mob", source_id)
    dest_client = ROOT / f"clien/Data/Mob/{dest_id}.img"
    if not source_client.is_file():
        raise RuntimeError(f"missing analogue mob {source_id}")
    if not dest_client.exists():
        shutil.copy2(source_client, dest_client)
    source_xml = ROOT / f"gms-server/wz/Mob.wz/{source_id}.img.xml"
    dest_xml = ROOT / f"gms-server/wz/Mob.wz/{dest_id}.img.xml"
    if source_xml.exists() and not dest_xml.exists():
        text = source_xml.read_text(encoding="utf-8")
        text = text.replace(f'name="{source_id}.img"', f'name="{dest_id}.img"', 1)
        dest_xml.write_text(text, encoding="utf-8")
    image = load_checked(dest_client, arc.GMS_KEY)
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"cloned mob {dest_id} parse failed")


def retarget_map_life(map_id: int, old_id: str, new_id: str, mob_time: int) -> None:
    if len(old_id) != len(new_id):
        raise RuntimeError(f"life id length mismatch {old_id} -> {new_id}")
    client = client_map_path(map_id)
    original = client.read_bytes()
    image = load_checked(client, arc.GMS_KEY)
    life = image.root.child("life")
    if not isinstance(life, WzSubProperty):
        raise RuntimeError(f"{map_id} missing life")
    patched = original
    allowed: set[tuple[str, ...]] = set()
    for entry in list(life.children()):
        if str(arc.child_value(entry, "id")) != old_id:
            continue
        patched = arc.mutate_img(
            patched,
            "edit",
            ("life", entry.name, "id"),
            values={"value": new_id},
            region="GMS",
        ).data
        allowed.add(("life", entry.name, "id"))
        if int(arc.child_value(entry, "mobTime") or 0) != mob_time:
            patched = arc.mutate_img(
                patched,
                "edit",
                ("life", entry.name, "mobTime"),
                values={"value": mob_time},
                region="GMS",
            ).data
            allowed.add(("life", entry.name, "mobTime"))
    if not allowed:
        checked = load_checked(client, arc.GMS_KEY)
        ids = [str(arc.child_value(entry, "id")) for entry in checked.root.child("life").children()]
        if new_id in ids and old_id not in ids:
            return
        raise RuntimeError(f"{map_id} has no life {old_id}: {ids}")
    arc.verify_raw_record_scope(original, patched, allowed, allow_additions=False)
    checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=client.name)
    checked.parse()
    if checked.truncated or checked.parse_warnings:
        raise RuntimeError(f"{map_id} parse failed after life retarget")
    ids = [str(arc.child_value(entry, "id")) for entry in checked.root.child("life").children()]
    if old_id in ids or new_id not in ids:
        raise RuntimeError(f"{map_id} life ids after retarget: {ids}")
    arc.atomic_write_bytes(client, patched)
    xml_path = server_map_path("wz", map_id)
    if xml_path.exists():
        text = xml_path.read_text(encoding="utf-8")
        updated = text.replace(f'value="{old_id}"', f'value="{new_id}"')
        updated = updated.replace('<int name="mobTime" value="-1"/>', '<int name="mobTime" value="0"/>')
        if updated != text:
            arc.atomic_write_text(xml_path, updated)


def install_first_tower_guard() -> None:
    install_tower_guard(8210000, 8210010, 211060201, "8840002")


def make_mob_life_node(
    name: str,
    mob_id: int,
    x: int,
    y: int,
    fh: int,
    cy: int,
    rx0: int,
    rx1: int,
) -> WzSubProperty:
    node = WzSubProperty(name)
    add_string(node, "type", "m")
    add_string(node, "id", str(mob_id))
    add_int(node, "x", x)
    add_int(node, "y", y)
    add_int(node, "mobTime", 0)
    add_int(node, "f", 0)
    add_int(node, "hide", 0)
    add_int(node, "fh", fh)
    add_int(node, "cy", cy)
    add_int(node, "rx0", rx0)
    add_int(node, "rx1", rx1)
    return node


def install_tower_guard(source_id: int, dest_id: int, map_id: int, old_life_id: str) -> None:
    clone_field_mob(source_id, dest_id)
    leftover = iter_incomplete_ballistic_attacks((dest_id,))
    if leftover:
        repair_ballistic_mobs((dest_id,))
        leftover = iter_incomplete_ballistic_attacks((dest_id,))
        if leftover:
            raise RuntimeError(f"incomplete ballistic attacks: {leftover}")
    arc.upsert_client_strings("Mob", {dest_id})
    arc.upsert_server_strings("wz", "Mob", {dest_id})
    arc.upsert_server_strings("wz-zh-CN", "Mob", {dest_id})
    retarget_map_life(map_id, old_life_id, str(dest_id), 0)


def insert_fourth_tower_roof_life() -> None:
    clone_field_mob(8210005, 8210014)
    leftover = iter_incomplete_ballistic_attacks((8210014,))
    if leftover:
        repair_ballistic_mobs((8210014,))
        leftover = iter_incomplete_ballistic_attacks((8210014,))
        if leftover:
            raise RuntimeError(f"incomplete ballistic attacks: {leftover}")
    arc.upsert_client_strings("Mob", {8210014})
    arc.upsert_server_strings("wz", "Mob", {8210014})
    arc.upsert_server_strings("wz-zh-CN", "Mob", {8210014})
    # TMS 211060801 has footholds but no life. Place field Ani souls on the roof walkway.
    spawns = (
        ("0", 120, -165, 4, -139, -29, 253),
        ("1", 420, -165, 1, -139, 253, 799),
        ("2", 650, -165, 1, -139, 253, 799),
        ("3", 980, -165, 2, -139, 799, 1339),
        ("4", 1200, -165, 2, -139, 799, 1339),
        ("5", 1550, -165, 3, -139, 1339, 1878),
    )
    nodes = [make_mob_life_node(name, 8210014, x, y, fh, cy, rx0, rx1) for name, x, y, fh, cy, rx0, rx1 in spawns]
    client = client_map_path(211060801)
    append_named_records(client, ("life",), nodes)
    xml_path = server_map_path("wz", 211060801)
    if xml_path.exists():
        append_server_named(xml_path, ("life",), nodes)


def install_remaining_tower_guards() -> None:
    install_tower_guard(8210001, 8210011, 211060401, "8210006")
    install_tower_guard(8210003, 8210012, 211060601, "8210007")
    insert_fourth_tower_roof_life()


def insert_instructor_ani_life() -> None:
    arc.upsert_client_strings("Mob", {8210013})
    arc.upsert_server_strings("wz", "Mob", {8210013})
    arc.upsert_server_strings("wz-zh-CN", "Mob", {8210013})
    leftover = iter_incomplete_ballistic_attacks((8210013,))
    if leftover:
        repair_ballistic_mobs((8210013,))
        leftover = iter_incomplete_ballistic_attacks((8210013,))
        if leftover:
            raise RuntimeError(f"incomplete ballistic attacks: {leftover}")
    client = client_map_path(211061100)
    image = load_checked(client, arc.GMS_KEY)
    life = image.root.child("life")
    if not isinstance(life, WzSubProperty):
        raise RuntimeError("211061100 missing life")
    if any(str(arc.child_value(entry, "id")) == "8210013" for entry in life.children()):
        return
    node = make_mob_life_node("1", 8210013, 420, -241, 2, -215, 166, 697)
    append_named_records(client, ("life",), [node])
    xml_path = server_map_path("wz", 211061100)
    if xml_path.exists():
        append_server_named(xml_path, ("life",), [node])


def install_purification_quest_items() -> None:
    migrate_items()


def insert_dead_mine_portal() -> None:
    client = client_map_path(ENTRANCE_FROM_MAP)
    image = load_checked(client, arc.GMS_KEY)
    portal = image.root.child("portal")
    if not isinstance(portal, WzSubProperty):
        raise RuntimeError("211040600 missing portal")
    if any(arc.child_value(entry, "pn") == "in00" for entry in portal.children()):
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
            raise RuntimeError(f"211040600 changed existing portal {child.name}")
    if ("portal", next_name) not in after_records:
        raise RuntimeError("211040600 missing inserted in00 portal")
    if after_orders[("portal",)][:-1] != tuple(child.name for child in portal.children()):
        raise RuntimeError("211040600 reordered existing portals")
    checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=client.name)
    checked.parse()
    if checked.truncated or checked.parse_warnings:
        raise RuntimeError("211040600 parse failed after portal insert")
    if not any(arc.child_value(entry, "pn") == "in00" for entry in checked.root.child("portal").children()):
        raise RuntimeError("211040600 in00 portal missing after parse")
    decode_canvases(checked.root)
    arc.atomic_write_bytes(client, patched)
    for tree in ("wz", "wz-zh-CN"):
        server = server_map_path(tree, ENTRANCE_FROM_MAP)
        if not server.exists():
            continue
        text = server.read_text(encoding="utf-8")
        xml_root = ET.fromstring(text)
        info = xml_root.find('./imgdir[@name="portal"]')
        if info is None:
            continue
        if any(child.find('./string[@name="pn"]') is not None and child.find('./string[@name="pn"]').get("value") == "in00" for child in info):
            continue
        updated = arc.append_xml_properties(text, ("portal",), [make_portal_node(next_name)])
        arc.atomic_write_text(server, updated)


def copy_canvas(source: WzCanvasProperty, name: str, parent: WzSubProperty) -> WzCanvasProperty:
    cloned = WzCanvasProperty(name, parent)
    cloned.width = source.width
    cloned.height = source.height
    cloned.format = 1
    cloned.format2 = 0
    cloned._png_data = source._png_data
    cloned._png_length = source._png_length
    origin = source.child("origin")
    if origin is not None and hasattr(origin, "x"):
        cloned.add(WzVectorProperty("origin", int(origin.x), int(origin.y), cloned))
    return cloned


def project_item_icons(item: WzSubProperty, analogue: WzSubProperty) -> None:
    info = item.child("info")
    analogue_info = analogue.child("info")
    if not isinstance(info, WzSubProperty) or not isinstance(analogue_info, WzSubProperty):
        return
    for canvas_name in ("icon", "iconRaw"):
        canvas = info.child(canvas_name)
        analogue_canvas = analogue_info.child(canvas_name)
        if not isinstance(canvas, WzCanvasProperty) or not isinstance(analogue_canvas, WzCanvasProperty):
            continue
        if (canvas.width, canvas.height) != (1, 1):
            continue
        info._children.pop(canvas_name, None)
        info.add(copy_canvas(analogue_canvas, canvas_name, info))


def strip_unproven_item_fields(item: WzSubProperty, analogue: WzSubProperty) -> None:
    info = item.child("info")
    analogue_info = analogue.child("info")
    if not isinstance(info, WzSubProperty) or not isinstance(analogue_info, WzSubProperty):
        return
    allowed = {child.name for child in analogue_info.children()} | {
        "icon",
        "iconRaw",
        "slotMax",
        "price",
        "notSale",
        "tradeBlock",
        "lv",
        "autoPrice",
    }
    for child in list(info.children()):
        if child.name not in allowed:
            info._children.pop(child.name, None)


def append_record_with_refs(original: bytes, parent_path: tuple[str, ...], node, name: str) -> bytes:
    layout = scan_img(original, region="GMS")
    prop_list, ancestors = _find_list(layout.root, parent_path)
    if any(record.name == node.name for record in prop_list.records):
        return original
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
    patched = arc.verified_image_bytes(_apply_edits(original, edits), name)
    image = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{name} parse failed after append {node.name}")
    parent = image.root
    for part in parent_path:
        parent = parent.child(part)
    if parent.child(node.name) is None:
        raise RuntimeError(f"{name} missing appended record {node.name}")
    decode_canvases(parent.child(node.name))
    return patched


def insert_item_record(client: Path, server: Path, node: WzSubProperty) -> None:
    original = client.read_bytes()
    records, _orders = arc.raw_record_state(original)
    if (node.name,) in records:
        return
    updated = append_record_with_refs(original, (), node, client.name)
    arc.atomic_write_bytes(client, updated)
    if server.exists():
        append_server_named(server, (), [node])


def migrate_items() -> None:
    analogue_path = ROOT / "clien/Data/Item/Etc/0403.img"
    analogue_image = load_checked(analogue_path, arc.GMS_KEY)
    analogue = analogue_image.root.child(ANALOGUE_ETC)
    if not isinstance(analogue, WzSubProperty):
        raise RuntimeError("missing analogue Etc item 04032000")
    for item_id, img_name, node_name in ETC_ITEMS:
        source_path = SOURCE / f"Item/Etc/{img_name}"
        source = arc.load_image(source_path, arc.BMS_KEY)
        raw = source.root.child(node_name)
        if not isinstance(raw, WzSubProperty):
            raise RuntimeError(f"TMS missing {node_name}")
        node = arc.clone_property(raw, None, source, source_path, arc.CanvasMaterializer(), node_name)
        analogue_for_item = analogue
        if img_name == "0400.img":
            brick = load_checked(ROOT / "clien/Data/Item/Etc/0400.img", arc.GMS_KEY).root.child("04000629")
            if isinstance(brick, WzSubProperty):
                analogue_for_item = brick
        elif img_name == "0431.img":
            coin = load_checked(ROOT / "clien/Data/Item/Etc/0431.img", arc.GMS_KEY).root.child("04310000")
            if isinstance(coin, WzSubProperty):
                analogue_for_item = coin
        project_item_icons(node, analogue_for_item)
        strip_unproven_item_fields(node, analogue_for_item)
        insert_item_record(
            ROOT / f"clien/Data/Item/Etc/{img_name}",
            ROOT / f"gms-server/wz/Item.wz/Etc/{img_name}.xml",
            node,
        )
        string_source_path = SOURCE / "String/Etc.img"
        string_source = arc.load_image(string_source_path, arc.BMS_KEY)
        string_raw = string_source.root.get(f"Etc/{item_id}")
        if isinstance(string_raw, WzSubProperty):
            string_node = arc.clone_property(
                string_raw, None, string_source, string_source_path, arc.CanvasMaterializer(), str(item_id)
            )
            append_named_records_tolerant(ROOT / "clien/Data/String/Etc.img", ("Etc",), [string_node])
            for tree in ("wz", "wz-zh-CN"):
                append_server_named(
                    ROOT / f"gms-server/{tree}/String.wz/Etc.img.xml",
                    ("Etc",),
                    [string_node],
                )
    for item_id, img_name, node_name in CONSUME_ITEMS:
        source_path = SOURCE / f"Item/Consume/{img_name}"
        source = arc.load_image(source_path, arc.BMS_KEY)
        raw = source.root.child(node_name)
        if not isinstance(raw, WzSubProperty):
            raise RuntimeError(f"TMS missing {node_name}")
        node = arc.clone_property(raw, None, source, source_path, arc.CanvasMaterializer(), node_name)
        project_item_icons(node, analogue)
        insert_item_record(
            ROOT / f"clien/Data/Item/Consume/{img_name}",
            ROOT / f"gms-server/wz/Item.wz/Consume/{img_name}.xml",
            node,
        )
        consume_string = WzSubProperty(str(item_id))
        add_string(consume_string, "name", "接见室卷轴")
        add_string(consume_string, "desc", "可以移动到狮子王城接见室前走道。")
        append_named_records_tolerant(ROOT / "clien/Data/String/Consume.img", (), [consume_string])
        for tree in ("wz", "wz-zh-CN"):
            path = ROOT / f"gms-server/{tree}/String.wz/Consume.img.xml"
            if path.exists():
                append_server_named(path, (), [consume_string])


def append_named_records_tolerant(
    path: Path,
    parent_path: tuple[str, ...],
    nodes: list[WzSubProperty],
) -> None:
    data = path.read_bytes()
    original = data
    for node in nodes:
        data = append_record_with_refs(data, parent_path, node, path.name)
    if data != original:
        arc.atomic_write_bytes(path, data)


def xml_property(element: ET.Element, parent=None):
    name = element.get("name", "")
    if element.tag == "imgdir":
        output = WzSubProperty(name, parent)
        for child in element:
            output.add(xml_property(child, output))
        return output
    if element.tag in {"int", "short"}:
        return WzIntProperty(name, int(element.get("value", "0")), parent)
    if element.tag == "string":
        return WzStringProperty(name, element.get("value", ""), parent)
    raise RuntimeError(f"unsupported quest node {element.tag}/{name}")


def migrate_quests() -> None:
    for name in QUEST_NAMES:
        server = ROOT / f"gms-server/wz/Quest.wz/{name}.img.xml"
        root = ET.parse(server).getroot()
        nodes = []
        for quest_id in QUEST_IDS:
            element = root.find(f'./imgdir[@name="{quest_id}"]')
            if element is None:
                raise RuntimeError(f"server {name} missing quest {quest_id}")
            nodes.append(xml_property(element))
        append_named_records_tolerant(ROOT / f"clien/Data/Quest/{name}.img", (), nodes)


def key_gate_js(item_ids: list[int], quest_ids: list[int], dest_map: int, dest_portal: str, message: str) -> str:
    items = ", ".join(str(item_id) for item_id in item_ids)
    quests = ", ".join(str(quest_id) for quest_id in quest_ids)
    return f"""function enter(pi) {{
    var items = [{items}];
    var quests = [{quests}];
    var allowed = false;
    var i;
    for (i = 0; i < items.length; i++) {{
        if (pi.haveItem(items[i], 1)) {{
            allowed = true;
            break;
        }}
    }}
    if (!allowed) {{
        for (i = 0; i < quests.length; i++) {{
            if (pi.isQuestStarted(quests[i]) || pi.isQuestCompleted(quests[i])) {{
                allowed = true;
                break;
            }}
        }}
    }}
    if (!allowed) {{
        pi.playerMessage(5, "{message}");
        return false;
    }}
    pi.playPortalSound();
    pi.warp({dest_map}, "{dest_portal}");
    return true;
}}
"""


def write_script(relative: str, contents: str) -> None:
    for tree in ("scripts-zh-CN", "scripts"):
        path = ROOT / "gms-server" / tree / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")


def write_gameplay_scripts() -> None:
    write_script(
        "portal/lionCastle_enter.js",
        """function enter(pi) {
    pi.playPortalSound();
    pi.warp(211060010, "west00");
    return true;
}
""",
    )
    write_script(
        "portal/BPReturn_Vanleon.js",
        """function enter(pi) {
    pi.playPortalSound();
    pi.warp(211060000, "east00");
    return true;
}
""",
    )
    write_script(
        "portal/portalNPC.js",
        """function enter(pi) {
    pi.playPortalSound();
    pi.warp(211050000, 4);
    return true;
}
""",
    )
    write_script(
        "portal/enterVL00.js",
        """function enter(pi) {
    pi.playPortalSound();
    pi.warp(211070100, 0);
    return true;
}
""",
    )
    write_script(
        "portal/pt_rosegarden.js",
        """function enter(pi) {
    if (!(pi.haveItem(4032836, 1) || pi.isQuestStarted(3174) || pi.isQuestCompleted(3174))) {
        pi.playerMessage(5, "需要持有玫瑰庭园的钥匙才能进入。");
        return false;
    }
    pi.playPortalSound();
    pi.warp(211080000, "west00");
    return true;
}
""",
    )
    write_script("portal/gotoNext1.js", key_gate_js([4032858, 4032832], [3164, 3165, 3190], 211060300, "west00", "需要持有第一座塔的钥匙才能进入。"))
    write_script("portal/1stTowerTop.js", key_gate_js([4032858, 4032832], [3164, 3165, 3190], 211060201, "down00", "需要持有第一座塔的钥匙才能登上屋顶。"))
    write_script("portal/gotoNext2_1.js", key_gate_js([4032833], [3166, 3191], 211060500, "west00", "需要持有第二座塔的钥匙才能进入。"))
    write_script("portal/gotoNext2_2.js", key_gate_js([4032833], [3166, 3191], 211060410, "in00", "需要持有第二座塔的钥匙才能进入。"))
    write_script("portal/2ndTowerTop.js", key_gate_js([4032833], [3166, 3191], 211060401, "down00", "需要持有第二座塔的钥匙才能登上屋顶。"))
    write_script("portal/gotoNext3_1.js", key_gate_js([4032834], [3167, 3192], 211060700, "west00", "需要持有第三座塔的钥匙才能进入。"))
    write_script("portal/gotoNext3_2.js", key_gate_js([4032834], [3167, 3192], 211060610, "in00", "需要持有第三座塔的钥匙才能进入。"))
    write_script("portal/gotoNext3_3.js", key_gate_js([4032834], [3167, 3192], 211060620, "in00", "需要持有第三座塔的钥匙才能进入。"))
    write_script("portal/3rdTowerTop.js", key_gate_js([4032834], [3167, 3192], 211060601, "down00", "需要持有第三座塔的钥匙才能登上屋顶。"))
    write_script("portal/gotoNext4.js", key_gate_js([4032840], [3193, 3194], 211060800, "west00", "需要持有第四座塔的钥匙才能进入。"))
    write_script(
        "portal/BPReturnVanleon2.js",
        """function enter(pi) {
    pi.playPortalSound();
    pi.warp(211060800, "up00");
    return true;
}
""",
    )
    write_script(
        "portal/gotoAni.js",
        """function enter(pi) {
    pi.playPortalSound();
    pi.warp(211061100, 0);
    return true;
}
""",
    )
    write_script(
        "portal/out_ani.js",
        """function enter(pi) {
    pi.playPortalSound();
    pi.warp(211061000, "east00");
    return true;
}
""",
    )
    write_script(
        "portal/lionCastleBoss.js",
        """function enter(pi) {
    pi.playerMessage(5, "这条密道现在没有反应。");
    return false;
}
""",
    )
    write_script(
        "portal/lioncastleout.js",
        """function enter(pi) {
    pi.playPortalSound();
    pi.warp(211070000, 0);
    return true;
}
""",
    )
    write_script(
        "quest/3178.js",
        """var status = -1;

function start(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
        return;
    }
    if (mode == 0 && type > 0) {
        qm.dispose();
        return;
    }
    if (mode == 1) {
        status++;
    } else {
        status--;
    }
    if (status == 0) {
        qm.sendNext("请走只有国王和王后才知道的密道，把我的吊坠带到接见室去。");
    } else {
        qm.forceStartQuest();
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
        return;
    }
    if (mode == 0 && type > 0) {
        qm.dispose();
        return;
    }
    if (mode == 1) {
        status++;
    } else {
        status--;
    }
    if (status == 0) {
        if (!qm.haveItem(4032839, 1)) {
            qm.sendOk("还没有把吊坠带回来。");
            qm.dispose();
            return;
        }
        qm.forceCompleteQuest();
        qm.dispose();
    }
}
""",
    )
    write_script(
        "quest/3182.js",
        """var status = -1;

function start(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
        return;
    }
    if (mode == 0 && type > 0) {
        qm.dispose();
        return;
    }
    if (mode == 1) {
        status++;
    } else {
        status--;
    }
    if (status == 0) {
        qm.sendNext("把这颗水晶带到莫特身边使用，就能解除狮子王的诅咒。");
    } else {
        qm.forceStartQuest();
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
        return;
    }
    if (mode == 0 && type > 0) {
        qm.dispose();
        return;
    }
    if (mode == 1) {
        status++;
    } else {
        status--;
    }
    if (status == 0) {
        qm.forceCompleteQuest();
        qm.dispose();
    }
}
""",
    )
    write_script(
        "portal/pt_rosegardenout.js",
        """function enter(pi) {
    pi.playPortalSound();
    pi.warp(211061001, "next00");
    return true;
}
""",
    )
    write_script(
        "map/onUserEnter/TD_LC_title.js",
        """function start(ms) {
}
""",
    )
    write_script(
        "map/onUserEnter/lionCastle_enter1.js",
        """function start(ms) {
}
""",
    )
    write_script(
        "map/onUserEnter/enter_211060300.js",
        """function start(ms) {
}
""",
    )
    write_script(
        "map/onUserEnter/q3143_clear.js",
        """function start(ms) {
}
""",
    )
    write_script(
        "map/onUserEnter/missionCheckForBmWeapon.js",
        """function start(ms) {
}
""",
    )
    write_script(
        "map/onUserEnter/enter_211070000.js",
        """function start(ms) {
}
""",
    )
    write_script(
        "map/onUserEnter/enter_211080000.js",
        """function start(ms) {
}
""",
    )
    write_script(
        "map/onFirstUserEnter/summon_ani.js",
        """function start(ms) {
    var map = ms.getMap();
    ms.spawnMonsterOnGroundBelowIfMissing(map, 8210013, 420, -241);
}
""",
    )


def patch_warp_script() -> None:
    text = WARP_SCRIPT.read_text(encoding="utf-8")
    needle = '    Array(807000000, 10000, "枫叶丘陵#r              （消耗1万金币）#b"),'
    line = '    Array(211060000, 10000, "狮子王城#r              （消耗1万金币）#b"),\n'
    if "211060000" not in text:
        if needle not in text:
            raise RuntimeError("warp town anchor missing")
        text = text.replace(needle, line + needle, 1)
    WARP_SCRIPT.write_text(text, encoding="utf-8")


def remove_boss_entries() -> None:
    text = ADVANCED_BOSS_WARP.read_text(encoding="utf-8")
    removed_lines = (
        '    Array(900000207, 500000, "守护天使绿水灵            #r（消耗50万金币）#b", 8880700, -1, 703, -1394),\n',
        '    Array(410007140, 500000, "咖凌·窮奇战                  #r（消耗50万金币）#b", 8880830, -1, 568, 106),\n',
        '    Array(410007180, 500000, "咖凌·檮杌战                  #r（消耗50万金币）#b", 8880831, -1, 568, 106),\n',
        '    Array(410007220, 500000, "咖凌·混沌战                  #r（消耗50万金币）#b", 8880832, -1, 634, 106),\n',
        '    Array(410007260, 500000, "咖凌·P2 咖凌                 #r（消耗50万金币）#b", 8880837, -1, 568, 106),\n',
        '    Array(410007300, 500000, "咖凌·P3 暴走咖凌             #r（消耗50万金币）#b", 8880842, -1, -545, 399)\n',
    )
    for line in removed_lines:
        text = text.replace(line, "")
    text = text.replace(
        '    text += "#L" + KARING_FINAL_BATTLE_SELECTION\n'
        '        + "##r咖凌·终局之战                 （远征队正式流程）#b#l\\r\\n";\n',
        "",
    )
    text = text.replace(
        '    if (selection == KARING_FINAL_BATTLE_SELECTION) {\n'
        '        cm.dispose();\n'
        '        cm.openNpc(9900001, "咖凌终局之战");\n'
        '        return;\n'
        '    }\n',
        "",
    )
    ADVANCED_BOSS_WARP.write_text(text, encoding="utf-8")
    retry = RETRY_PORTAL.read_text(encoding="utf-8")
    retry = retry.replace('    "221040001": [221040001, 8880200, -1215, 866, "bossRetry"],\n', "")
    retry = retry.replace('    "900000207": [900000207, 8880700, 703, -1394, "bossRetry"],\n', "")
    RETRY_PORTAL.write_text(retry, encoding="utf-8")
    for relative in (
        "event/KaringFinalBattle.js",
        "BeiDouSpecial/咖凌终局之战.js",
    ):
        for tree in ("scripts", "scripts-zh-CN"):
            path = ROOT / "gms-server" / tree / relative
            if path.is_file():
                path.unlink()
    for mob_id in REMOVED_BOSS_MOBS:
        for path in (
            ROOT / f"clien/Data/Mob/{mob_id}.img",
            ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml",
        ):
            if path.is_file():
                path.unlink()
    for map_id in REMOVED_BOSS_MAPS:
        for path in (
            client_map_path(map_id),
            server_map_path("wz", map_id),
            server_map_path("wz-zh-CN", map_id),
        ):
            if path.is_file():
                path.unlink()


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
    arc.BACKUP_ROOT = Path("/private/tmp/lion-king-castle-migration-backup")
    arc.MAP_IDS = MAP_IDS
    arc.MAP_ID_SET = MAP_ID_SET
    if not SOURCE.exists():
        raise SystemExit("TMS IMG source is missing")
    print(f"maps {len(MAP_IDS)}")
    dependencies, map_stats = migrate_maps()
    print("maps", map_stats)
    print("map assets", merge_assets_tolerant(dependencies))
    print("map marks", arc.merge_map_marks(dependencies["marks"]))
    dependencies["npcs"].update({9000174, 2161005, 2162000, 2161004})
    print("npcs", migrate_npcs(dependencies["npcs"]))
    print("mobs", migrate_local_mobs(dependencies["mobs"]))
    print("ballistic", repair_ballistic_mobs(tuple(sorted(dependencies["mobs"]))))
    leftover = iter_incomplete_ballistic_attacks(tuple(sorted(dependencies["mobs"])))
    if leftover:
        raise RuntimeError(f"incomplete ballistic attacks: {leftover}")
    print("bgms", arc.migrate_bgms(dependencies["bgms"]))
    print("map strings", {
        "client_ossyria": arc.upsert_client_strings("Map", MAP_IDS, "ossyria"),
        "wz_ossyria": arc.upsert_server_strings("wz", "Map", MAP_IDS, "ossyria"),
        "zh_ossyria": arc.upsert_server_strings("wz-zh-CN", "Map", MAP_IDS, "ossyria"),
    })
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
    insert_dead_mine_portal()
    patch_corridor_audience_script()
    patch_corridor_life()
    patch_rose_garden_portal()
    migrate_items()
    migrate_quests()
    patch_warp_script()
    write_gameplay_scripts()
    restore_scripted_portals()
    install_first_tower_guard()
    install_remaining_tower_guards()
    insert_instructor_ani_life()
    remove_boss_entries()
    broken = maps_needing_repair()
    if broken:
        raise RuntimeError(f"obj/back gaps remain: {broken}")
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
