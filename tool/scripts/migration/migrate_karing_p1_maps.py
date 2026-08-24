#!/usr/bin/env python3
"""Migrate the first Karing boss map chain and required map assets.

The seven imported maps are new standalone legacy-client files.  They keep the
server script hooks used by the Karing transition MCVs, but drop modern map
nodes and missing BGM/MapHelper dependencies.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")

sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
sys.path.insert(0, str(ROOT / "tool" / "scripts" / "migration"))

from wzpy import WzCanvasProperty, WzImage, WzIntProperty, WzKey, WzStringProperty, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import (  # noqa: E402
    _encode_property_list,
    encode_compressed_int,
    encode_image_body,
    re_encrypt_string,
)

from migrate_arcane_river_fields import (  # noqa: E402
    BMS_KEY,
    GMS_KEY,
    BACK_UNSUPPORTED,
    LIFE_UNSUPPORTED,
    OBJ_UNSUPPORTED,
    PORTAL_UNSUPPORTED,
    CanvasMaterializer,
    atomic_write_bytes,
    atomic_write_text,
    child_value,
    clone_property,
    gms_reader,
    image_to_xml,
    load_image,
    remove_child,
    set_int,
)


MAP_IDS = (410007100, 410007120, 410007140, 410007160, 410007180, 410007200, 410007220)
KARING_MAP_BGM = {
    410007100: "Bgm57/Invasion",
    410007120: "Bgm00/Silence",
    410007140: "Bgm57/DestroyedFourSeasons",
    410007160: "Bgm00/Silence",
    410007180: "Bgm57/DestroyedFourSeasons",
    410007200: "Bgm00/Silence",
    410007220: "Bgm57/DestroyedFourSeasons",
    410007240: "Bgm00/Silence",
    410007260: "Bgm57/FadedWinter",
    410007280: "Bgm00/Silence",
    410007300: "Bgm57/RuinationOfFourSeasons",
}
NPC_IDS = (9091029, 9091030, 9091031)
RETURN_MAP = 910000000
MAX_CANVAS_EDGE = 2048
MAX_LEGACY_BACK_ANIMATION_FRAMES = 1

MAP_ROOTS = {
    "info", "back", "life", "reactor", "foothold",
    "ladderRope", "miniMap", "portal", *(str(index) for index in range(8)),
}
MAP_INFO_REMOVE = {
    "AmbientBGM", "AmbientBGMv", "ReviveCurFieldOfNoTransfer",
    "ReviveCurFieldOfNoTransferNotDamaged", "ReviveCurFieldOfNoTransferPoint",
    "barrierArc", "barrierAut", "bgmSub", "consumeItemCoolTime",
    "fieldLimit2", "fieldScript", "fieldType", "footStepSound", "largeSplit",
    "limitUpgradeItem", "limitUseShop", "lvLimit", "mapMark", "mode", "noChair",
    "noHekatonEffect", "noMapCmd", "partyStandAlone", "qrLimit", "quarterView",
    "remoteEffect", "reviveCurField", "specialSound", "standAlone",
}
NPC_INFO_REMOVE = {
    "script", "talkMouseOnly", "forcedZPage", "forcedZMass",
    "dcLeft", "dcRight", "dcTop", "dcBottom", "scriptDelay",
}
SCRIPT_PORTAL_TYPES = {11, 14}
HIDDEN_PORTAL_TYPES = {10}
MAP_LOAD_SAFE_PROJECTION_IDS = {410007140, 410007180, 410007220}
MAP_STRUCTURE_BASE_IDS = {
    410007180: 410007140,
}
MAP_VISUAL_SOURCE_IDS = {
    410007180: 410007180,
}
LEGACY_FIELD_LIMIT_OVERRIDES = {
    410007140: 1909496,
    410007180: 1909496,
    410007220: 1909496,
}
LEGACY_VISIBLE_SCRIPT_PORTALS = {
    410007140: {"ptKaringOut"},
    410007180: {"ptKaringOut"},
    410007220: {"ptKaringOut"},
}
P1_INTER_BOSS_PORTALS = {
    410007140: {"dool", "hondon", "hd00", "hd01", "hd02", "hd03"},
    410007180: {"dool", "hondon", "hd00", "hd01", "hd02", "hd03"},
    410007220: {"goongi", "dool"},
    410007260: {"hd00", "hd01", "hd02", "hd03"},
}
ON_FIRST_USER_ENTER_OVERRIDES = {
    410007180: "first_doolpre",
}
HIDDEN_PORTAL_TARGET_OVERRIDES = {
    410007180: 410007180,
}
REACTOR_ID_PROJECTION = {
    "9406000": "5018000",
    "9406001": "5018000",
    "9406002": "5018000",
}


def walk(node, path: str = ""):
    yield node, path
    if hasattr(node, "children"):
        for child in node.children():
            child_path = f"{path}/{child.name}" if path else child.name
            yield from walk(child, child_path)


def add_string(parent: WzSubProperty, name: str, value: str) -> None:
    remove_child(parent, name)
    parent.add(WzStringProperty(name, value, parent))


def project_boss_map_flow(root: WzSubProperty, map_id: int) -> None:
    info = root.child("info")
    on_first_user_enter = ON_FIRST_USER_ENTER_OVERRIDES.get(map_id)
    if isinstance(info, WzSubProperty) and on_first_user_enter is not None:
        script = info.child("onFirstUserEnter")
        if isinstance(script, WzStringProperty):
            script._value = on_first_user_enter
        else:
            add_string(info, "onFirstUserEnter", on_first_user_enter)

    portal = root.child("portal")
    if isinstance(portal, WzSubProperty):
        for entry in list(portal.children()):
            portal_name = str(child_value(entry, "pn") or "")
            if portal_name in P1_INTER_BOSS_PORTALS.get(map_id, set()):
                remove_child(portal, entry.name)
                continue
            hidden_target = HIDDEN_PORTAL_TARGET_OVERRIDES.get(map_id)
            target_map = entry.child("tm")
            if (
                hidden_target is not None
                and portal_name.startswith("hd")
                and isinstance(target_map, WzIntProperty)
            ):
                target_map._value = hidden_target


def clone_image(source_path: Path, sanitizer=None) -> tuple[WzImage, CanvasMaterializer]:
    image = load_image(source_path, BMS_KEY)
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"{source_path}: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    if sanitizer is not None:
        sanitizer(image.root)
    materializer = CanvasMaterializer()
    root = WzSubProperty(image.root.name)
    for child in image.root.children():
        root.add(clone_property(child, root, image, source_path, materializer))
    image._root = root
    image._parsed = True
    return image, materializer


def sanitize_map(root: WzSubProperty, map_id: int) -> None:
    for child in list(root.children()):
        if child.name not in MAP_ROOTS:
            remove_child(root, child.name)

    info = root.child("info")
    if isinstance(info, WzSubProperty):
        for name in MAP_INFO_REMOVE:
            remove_child(info, name)
        bgm = KARING_MAP_BGM.get(map_id)
        if bgm is not None:
            add_string(info, "bgm", bgm)
        field_limit = LEGACY_FIELD_LIMIT_OVERRIDES.get(map_id)
        if field_limit is not None:
            set_int(info, "fieldLimit", field_limit)
        set_int(info, "returnMap", RETURN_MAP)
        set_int(info, "forcedReturn", RETURN_MAP)

    project_boss_map_flow(root, map_id)

    life = root.child("life")
    if isinstance(life, WzSubProperty):
        for entry in list(life.children()):
            if child_value(entry, "type") == "n" and int(child_value(entry, "id") or 0) not in NPC_IDS:
                remove_child(life, entry.name)
                continue
            for name in LIFE_UNSUPPORTED | {"forcedZPage", "forcedZMass"}:
                remove_child(entry, name)

    reactor = root.child("reactor")
    if isinstance(reactor, WzSubProperty):
        for entry in reactor.children():
            reactor_id = entry.child("id")
            if isinstance(reactor_id, WzStringProperty):
                replacement = REACTOR_ID_PROJECTION.get(str(reactor_id.value))
                if replacement is not None:
                    reactor_id._value = replacement

    for layer in [child for child in root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if isinstance(objects, WzSubProperty):
            for entry in list(objects.children()):
                if entry.child("spineAni") is not None:
                    remove_child(objects, entry.name)
                    continue
                for name in OBJ_UNSUPPORTED:
                    remove_child(entry, name)

    back = root.child("back")
    if isinstance(back, WzSubProperty):
        for entry in list(back.children()):
            for name in BACK_UNSUPPORTED:
                remove_child(entry, name)

    portal = root.child("portal")
    if isinstance(portal, WzSubProperty):
        for entry in list(portal.children()):
            portal_type = int(child_value(entry, "pt") or 0)
            portal_name = str(child_value(entry, "pn") or "")
            script = child_value(entry, "script")
            visible_scripts = LEGACY_VISIBLE_SCRIPT_PORTALS.get(map_id, set())
            if portal_name in visible_scripts:
                set_int(entry, "pt", 7)
            elif portal_type in HIDDEN_PORTAL_TYPES:
                set_int(entry, "pt", 3)
            elif portal_type in SCRIPT_PORTAL_TYPES and script:
                set_int(entry, "pt", 9)
                set_int(entry, "tm", 999999999)
                add_string(entry, "tn", "")
            for name in PORTAL_UNSUPPORTED | {"shownAtMinimap", "ignoreRandomMission"}:
                remove_child(entry, name)

    project_map_load_safe_dependencies(root, map_id)


def project_map_load_safe_dependencies(root: WzSubProperty, map_id: int) -> list[str]:
    if map_id not in MAP_LOAD_SAFE_PROJECTION_IDS:
        return []

    removed: list[str] = []
    info = root.child("info")
    if isinstance(info, WzSubProperty) and info.child("abilityPresetBlock") is not None:
        remove_child(info, "abilityPresetBlock")
        removed.append("info/abilityPresetBlock")

    life = root.child("life")
    if isinstance(life, WzSubProperty):
        for entry in list(life.children()):
            removed.append(f"life/{entry.name}")
            remove_child(life, entry.name)

    reactor = root.child("reactor")
    if isinstance(reactor, WzSubProperty):
        for entry in list(reactor.children()):
            removed.append(f"reactor/{entry.name}")
            remove_child(reactor, entry.name)

    for layer in [child for child in root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        for entry in list(objects.children()):
            if child_value(entry, "oS") == "BossKaring":
                removed.append(f"{layer.name}/obj/{entry.name}")
                remove_child(objects, entry.name)
    return removed


def sanitize_npc(root: WzSubProperty) -> None:
    info = root.child("info")
    if isinstance(info, WzSubProperty):
        for name in NPC_INFO_REMOVE:
            remove_child(info, name)


def collect_dependencies(image: WzImage) -> dict[str, object]:
    dependencies: dict[str, object] = {"assets": defaultdict(set), "npcs": set()}
    life = image.root.child("life")
    if isinstance(life, WzSubProperty):
        for entry in life.children():
            if child_value(entry, "type") == "n":
                dependencies["npcs"].add(int(child_value(entry, "id")))

    back = image.root.child("back")
    if isinstance(back, WzSubProperty):
        for entry in back.children():
            resource, number = child_value(entry, "bS"), child_value(entry, "no")
            if resource and number is not None:
                branch = "ani" if int(child_value(entry, "ani") or 0) else "back"
                dependencies["assets"][("Back", str(resource))].add(f"{branch}/{number}")

    for layer in [child for child in image.root.children() if child.name.isdigit()]:
        tile_set = child_value(layer.child("info"), "tS")
        tiles = layer.child("tile")
        if tile_set and isinstance(tiles, WzSubProperty):
            for entry in tiles.children():
                unit, number = child_value(entry, "u"), child_value(entry, "no")
                if unit is not None and number is not None:
                    dependencies["assets"][("Tile", str(tile_set))].add(f"{unit}/{number}")
        objects = layer.child("obj")
        if isinstance(objects, WzSubProperty):
            for entry in objects.children():
                values = tuple(child_value(entry, key) for key in ("oS", "l0", "l1", "l2"))
                if all(value is not None for value in values):
                    dependencies["assets"][("Obj", str(values[0]))].add(
                        "/".join(str(value) for value in values[1:])
                    )
    return dependencies


def merge_dependencies(target: dict[str, object], source: dict[str, object]) -> None:
    target["npcs"].update(source["npcs"])
    for key, branches in source["assets"].items():
        target["assets"][key].update(branches)


def ensure_path(root: WzSubProperty, path: str) -> WzSubProperty:
    current = root
    for name in [part for part in path.split("/") if part]:
        child = current.child(name)
        if not isinstance(child, WzSubProperty):
            remove_child(current, name)
            child = WzSubProperty(name, current)
            current.add(child)
        current = child
    return current


def write_client(path: Path, image: WzImage) -> None:
    atomic_write_bytes(path, encode_image_body(image, gms_reader()))


def write_server_xml(path: Path, image: WzImage, name: str) -> None:
    atomic_write_text(path, image_to_xml(image, name))


def write_server_map_xml(image: WzImage, map_id: int) -> None:
    path = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
    write_server_xml(path, image, f"{map_id}.img")


def collapse_back_animation_frames(
    image: WzImage, branches: set[str]
) -> int:
    removed = 0
    for branch in sorted(branches):
        if not branch.startswith("ani/"):
            continue
        animation = image.root.get(branch)
        if not isinstance(animation, WzSubProperty):
            raise RuntimeError(f"{image.name}: missing animation branch {branch}")
        numeric_frames = [
            child for child in animation.children() if child.name.isdigit()
        ]
        numeric_frames.sort(key=lambda child: int(child.name))
        if not numeric_frames or numeric_frames[0].name != "0":
            raise RuntimeError(f"{image.name}: {branch} has no frame 0")
        for frame in numeric_frames[MAX_LEGACY_BACK_ANIMATION_FRAMES:]:
            remove_child(animation, frame.name)
            removed += 1
    return removed


def merge_asset(kind: str, name: str, branches: set[str]) -> dict[str, int]:
    source_path = SOURCE / f"Map/{kind}/{name}.img"
    target_path = ROOT / f"clien/Data/Map/{kind}/{name}.img"
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    source = load_image(source_path, BMS_KEY)
    materializer = CanvasMaterializer()
    if target_path.exists():
        target = load_image(target_path, GMS_KEY)
    else:
        target = WzImage.from_bytes(b"", key=GMS_KEY, name=source_path.name)
        target._root = WzSubProperty(source.root.name)
        target._parsed = True

    changed = 0
    for branch in sorted(branches):
        if target.root.get(branch) is not None:
            continue
        source_node = source.root.get(branch)
        if source_node is None:
            raise RuntimeError(f"source asset missing {kind}/{name}.img/{branch}")
        parent_path, _, leaf = branch.rpartition("/")
        parent = ensure_path(target.root, parent_path)
        parent.add(clone_property(source_node, parent, source, source_path, materializer, leaf))
        changed += 1

    collapsed = 0
    if kind == "Back":
        collapsed = collapse_back_animation_frames(target, branches)
        changed += collapsed

    if changed:
        write_client(target_path, target)

    server_target = WzImage.from_bytes(b"", key=GMS_KEY, name=source_path.name)
    server_target._root = WzSubProperty(source.root.name)
    server_target._parsed = True
    server_materializer = CanvasMaterializer()
    for branch in sorted(branches):
        source_node = source.root.get(branch)
        if source_node is None:
            raise RuntimeError(f"source asset missing {kind}/{name}.img/{branch}")
        parent_path, _, leaf = branch.rpartition("/")
        parent = ensure_path(server_target.root, parent_path)
        parent.add(clone_property(source_node, parent, source, source_path, server_materializer, leaf))
    server_collapsed = 0
    if kind == "Back":
        server_collapsed = collapse_back_animation_frames(server_target, branches)
    server_path = ROOT / f"gms-server/wz/Map.wz/{kind}/{name}.img.xml"
    if not server_path.exists() or server_collapsed:
        write_server_xml(server_path, server_target, f"{name}.img")
    return {
        "branches": len(branches),
        "changed": changed,
        "canvases": materializer.canvases + server_materializer.canvases,
        "links": materializer.links + server_materializer.links,
        "resized": materializer.resized + server_materializer.resized,
        "collapsed": collapsed,
    }


def migrate_npc(npc_id: int) -> dict[str, int]:
    source_path = SOURCE / f"Npc/{npc_id}.img"
    image, materializer = clone_image(source_path, sanitize_npc)
    write_client(ROOT / f"clien/Data/Npc/{npc_id}.img", image)
    write_server_xml(ROOT / f"gms-server/wz/Npc.wz/{npc_id}.img.xml", image, f"{npc_id}.img")
    return {"canvases": materializer.canvases, "links": materializer.links, "resized": materializer.resized}


def verify_img(
    path: Path,
    require_visible: bool = True,
    branches: set[str] | None = None,
) -> dict[str, int]:
    image = WzImage.from_bytes(path.read_bytes(), key=GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{path}: truncated={image.truncated} warnings={image.parse_warnings}")
    roots = [(image.root, "")]
    if branches is not None:
        roots = []
        for branch in sorted(branches):
            node = image.root.get(branch)
            if node is None:
                raise RuntimeError(f"{path}: missing {branch}")
            roots.append((node, branch))

    canvases = 0
    visible = 0
    for root, prefix in roots:
        for node, suffix in walk(root):
            prop_path = f"{prefix}/{suffix}" if prefix and suffix else prefix or suffix
            if not isinstance(node, WzCanvasProperty):
                continue
            canvases += 1
            if node.child("_outlink") is not None or node.child("_inlink") is not None:
                raise RuntimeError(f"{path}:{prop_path}: unresolved Canvas link")
            if int(node.format) != 1 or int(node.format2) != 0:
                raise RuntimeError(f"{path}:{prop_path}: format={node.format} format2={node.format2}")
            if int(node.width) > MAX_CANVAS_EDGE or int(node.height) > MAX_CANVAS_EDGE:
                raise RuntimeError(f"{path}:{prop_path}: oversized {node.width}x{node.height}")
            bitmap = decode_canvas(node, region="GMS").convert("RGBA")
            if bitmap.getbbox() is not None:
                visible += 1
    if require_visible and canvases and visible == 0:
        raise RuntimeError(f"{path}: all canvases are transparent")
    return {"canvases": canvases, "visible": visible}


def verify_map_contract(map_id: int) -> None:
    client_path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
    image = WzImage.from_bytes(client_path.read_bytes(), key=GMS_KEY, name=client_path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{client_path}: truncated={image.truncated} warnings={image.parse_warnings}")
    if image.root.child("particle") is not None:
        raise RuntimeError(f"{client_path}: modern particle root remains")
    info = image.root.child("info")
    if isinstance(info, WzSubProperty):
        for name in ("mapMark", "fieldType"):
            if info.child(name) is not None:
                raise RuntimeError(f"{client_path}: unsupported info/{name} remains")
        bgm = info.child("bgm")
        if not isinstance(bgm, WzStringProperty) or bgm.value != KARING_MAP_BGM.get(map_id):
            raise RuntimeError(f"{client_path}: BGM is not {KARING_MAP_BGM.get(map_id)}")
        expected_field_limit = LEGACY_FIELD_LIMIT_OVERRIDES.get(map_id)
        if expected_field_limit is not None and child_value(info, "fieldLimit") != expected_field_limit:
            raise RuntimeError(
                f"{client_path}: fieldLimit is not {expected_field_limit}"
            )
        for name in ("returnMap", "forcedReturn"):
            if child_value(info, name) != RETURN_MAP:
                raise RuntimeError(f"{client_path}: {name} is not {RETURN_MAP}")
        expected_script = ON_FIRST_USER_ENTER_OVERRIDES.get(map_id)
        if (
            expected_script is not None
            and child_value(info, "onFirstUserEnter") != expected_script
        ):
            raise RuntimeError(
                f"{client_path}: onFirstUserEnter is not {expected_script}"
            )
    portal = image.root.child("portal")
    if isinstance(portal, WzSubProperty):
        portal_names = {
            str(child_value(entry, "pn") or "") for entry in portal.children()
        }
        unexpected = portal_names & P1_INTER_BOSS_PORTALS.get(map_id, set())
        if unexpected:
            raise RuntimeError(f"{client_path}: inter-boss portals remain {unexpected}")
        for entry in portal.children():
            portal_type = int(child_value(entry, "pt") or 0)
            portal_name = str(child_value(entry, "pn") or "")
            hidden_target = HIDDEN_PORTAL_TARGET_OVERRIDES.get(map_id)
            if (
                hidden_target is not None
                and portal_name.startswith("hd")
                and child_value(entry, "tm") != hidden_target
            ):
                raise RuntimeError(
                    f"{client_path}: hidden portal {portal_name} targets "
                    f"{child_value(entry, 'tm')} instead of {hidden_target}"
                )
            if portal_type in SCRIPT_PORTAL_TYPES or portal_type in HIDDEN_PORTAL_TYPES:
                raise RuntimeError(f"{client_path}: modern portal type {portal_type} remains")
            if (
                portal_name in LEGACY_VISIBLE_SCRIPT_PORTALS.get(map_id, set())
                and portal_type != 7
            ):
                raise RuntimeError(
                    f"{client_path}: portal {portal_name} is not visible script type 7"
                )
            for name in PORTAL_UNSUPPORTED | {"shownAtMinimap", "ignoreRandomMission"}:
                if entry.child(name) is not None:
                    raise RuntimeError(f"{client_path}: unsupported portal/{entry.name}/{name} remains")
    verify_img(client_path, require_visible=False)

    server_path = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
    server_root = ET.parse(server_path).getroot()
    client_reactors = reactor_ids_from_client(image)
    server_reactors = reactor_ids_from_server(server_root)
    if client_reactors != server_reactors:
        raise RuntimeError(
            f"{map_id}: reactor mismatch client={client_reactors} server={server_reactors}"
        )
    for reactor_id in client_reactors:
        client_reactor = ROOT / f"clien/Data/Reactor/{reactor_id}.img"
        server_reactor = ROOT / f"gms-server/wz/Reactor.wz/{reactor_id}.img.xml"
        if not client_reactor.is_file() or not server_reactor.is_file():
            raise RuntimeError(
                f"{map_id}: missing reactor {reactor_id} "
                f"client={client_reactor.is_file()} server={server_reactor.is_file()}"
            )


def reactor_ids_from_client(image: WzImage) -> list[str]:
    reactor = image.root.child("reactor")
    if not isinstance(reactor, WzSubProperty):
        return []
    return [
        str(child_value(entry, "id"))
        for entry in reactor.children()
        if child_value(entry, "id") is not None
    ]


def reactor_ids_from_server(root: ET.Element) -> list[str]:
    reactor = next((child for child in root if child.get("name") == "reactor"), None)
    if reactor is None:
        return []
    return [
        str(node.get("value"))
        for entry in reactor
        for node in entry
        if node.get("name") == "id" and node.get("value") is not None
    ]


def locate_root_records(
    data: bytes, path: Path
) -> tuple[tuple[str, ...], tuple[tuple[int, int], ...]]:
    reader = WzBinaryReader(io.BytesIO(data), GMS_KEY)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError(f"{path}: unsupported IMG header")
    reader.skip(2)
    count = reader.read_compressed_int()

    names: list[str] = []
    spans: list[tuple[int, int]] = []
    for _ in range(count):
        start = reader.position
        name = reader.read_string_block(0)
        tag = reader.read_byte()
        if tag != 9:
            raise RuntimeError(f"{path}: unexpected root record {name}/{tag}")
        size = reader.read_u32()
        reader.seek(reader.position + size)
        names.append(name)
        spans.append((start, reader.position))
    if reader.position != len(data):
        raise RuntimeError(f"{path}: root records do not fill IMG body")
    return tuple(names), tuple(spans)


def encode_root_record(node) -> bytes:
    encoded = _encode_property_list((node,), gms_reader())
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError(f"{node.name}: unexpected encoded root record")
    return encoded[len(prefix):]


def find_imgdir_block(text: str, node_name: str) -> tuple[int, int]:
    pattern = re.compile(rf'<imgdir\b[^>]*\bname="{re.escape(node_name)}"[^>]*>')
    match = pattern.search(text)
    if match is None:
        raise RuntimeError(f"missing XML imgdir {node_name}")
    start = match.start()
    depth = 0
    for tag_match in re.finditer(r"</?imgdir\b[^>]*>", text[start:]):
        tag = tag_match.group(0)
        if tag.startswith("</"):
            depth -= 1
            if depth == 0:
                return start, start + tag_match.end()
        elif not tag.endswith("/>"):
            depth += 1
    raise RuntimeError(f"unterminated XML imgdir {node_name}")


def patch_existing_boss_map_flow() -> dict[int, tuple[str, ...]]:
    changed: dict[int, tuple[str, ...]] = {}
    for map_id in sorted(P1_INTER_BOSS_PORTALS):
        client_path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        original = client_path.read_bytes()
        image = WzImage.from_bytes(original, key=GMS_KEY, name=client_path.name)
        image.parse()
        if image.truncated or image.parse_warnings:
            raise RuntimeError(
                f"{client_path}: truncated={image.truncated} warnings={image.parse_warnings}"
            )

        names, spans = locate_root_records(original, client_path)
        raw_records = {
            name: original[start:end] for name, (start, end) in zip(names, spans)
        }
        allowed_roots = {"portal"}
        if map_id in ON_FIRST_USER_ENTER_OVERRIDES:
            allowed_roots.add("info")
        for name in allowed_roots:
            node = image.root.child(name)
            if node is None or name not in raw_records:
                raise RuntimeError(f"{client_path}: missing root {name}")
            if encode_root_record(node) != raw_records[name]:
                raise RuntimeError(f"{client_path}: root {name} is not reproducible")

        modified_roots: set[str] = set()
        portal = image.root.child("portal")
        if not isinstance(portal, WzSubProperty):
            raise RuntimeError(f"{client_path}: missing portal root")
        removed_names: set[str] = set()
        hidden_target_changed = False
        for entry in list(portal.children()):
            portal_name = str(child_value(entry, "pn") or "")
            if portal_name in P1_INTER_BOSS_PORTALS[map_id]:
                removed_names.add(portal_name)
                remove_child(portal, entry.name)
                continue
            hidden_target = HIDDEN_PORTAL_TARGET_OVERRIDES.get(map_id)
            target_map = entry.child("tm")
            if (
                hidden_target is not None
                and portal_name.startswith("hd")
                and isinstance(target_map, WzIntProperty)
                and int(target_map.value) != hidden_target
            ):
                target_map._value = hidden_target
                hidden_target_changed = True
        remaining_targets = {
            str(child_value(entry, "pn") or "") for entry in portal.children()
        } & P1_INTER_BOSS_PORTALS[map_id]
        if remaining_targets:
            raise RuntimeError(f"{client_path}: inter-boss portals remain {remaining_targets}")
        if removed_names or hidden_target_changed:
            modified_roots.add("portal")

        expected_script = ON_FIRST_USER_ENTER_OVERRIDES.get(map_id)
        if expected_script is not None:
            info = image.root.child("info")
            script = info.child("onFirstUserEnter") if isinstance(info, WzSubProperty) else None
            if not isinstance(script, WzStringProperty):
                raise RuntimeError(f"{client_path}: missing info/onFirstUserEnter")
            if str(script.value) != expected_script:
                script._value = expected_script
                modified_roots.add("info")

        replacements = {
            name: encode_root_record(image.root.child(name)) for name in modified_roots
        }
        rebuilt = b"".join(replacements.get(name, raw_records[name]) for name in names)
        records_start, records_end = spans[0][0], spans[-1][1]
        updated = original[:records_start] + rebuilt + original[records_end:]

        verified = WzImage.from_bytes(updated, key=GMS_KEY, name=client_path.name)
        verified.parse()
        if verified.truncated or verified.parse_warnings:
            raise RuntimeError(f"{client_path}: malformed flow patch {verified.parse_warnings}")
        verified_names, verified_spans = locate_root_records(updated, client_path)
        if verified_names != names:
            raise RuntimeError(f"{client_path}: root order changed")
        verified_raw = {
            name: updated[start:end]
            for name, (start, end) in zip(verified_names, verified_spans)
        }
        for name in names:
            expected = replacements.get(name, raw_records[name])
            if verified_raw[name] != expected:
                raise RuntimeError(f"{client_path}: unapproved root record changed: {name}")
        if updated != original:
            atomic_write_bytes(client_path, updated)

        server_path = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
        server_text = server_path.read_text(encoding="utf-8")
        server_root = ET.fromstring(server_text)
        server_modified: set[str] = set()
        server_portal = next(
            (node for node in server_root if node.get("name") == "portal"), None
        )
        if server_portal is None:
            raise RuntimeError(f"{server_path}: missing portal root")
        for entry in list(server_portal):
            portal_name = next(
                (
                    child.get("value")
                    for child in entry
                    if child.get("name") == "pn"
                ),
                "",
            )
            if portal_name in P1_INTER_BOSS_PORTALS[map_id]:
                server_portal.remove(entry)
                server_modified.add("portal")
                continue
            hidden_target = HIDDEN_PORTAL_TARGET_OVERRIDES.get(map_id)
            target_map = next(
                (child for child in entry if child.get("name") == "tm"), None
            )
            if (
                hidden_target is not None
                and str(portal_name).startswith("hd")
                and target_map is not None
                and target_map.get("value") != str(hidden_target)
            ):
                target_map.set("value", str(hidden_target))
                server_modified.add("portal")

        if expected_script is not None:
            server_info = next(
                (node for node in server_root if node.get("name") == "info"), None
            )
            server_script = next(
                (
                    node
                    for node in (server_info if server_info is not None else [])
                    if node.get("name") == "onFirstUserEnter"
                ),
                None,
            )
            if server_script is None:
                raise RuntimeError(f"{server_path}: missing info/onFirstUserEnter")
            if server_script.get("value") != expected_script:
                server_script.set("value", expected_script)
                server_modified.add("info")

        server_roots = {"portal"}
        if expected_script is not None:
            server_roots.add("info")
        for name in sorted(server_roots):
            node = server_portal if name == "portal" else server_info
            start, end = find_imgdir_block(server_text, name)
            block = ET.tostring(node, encoding="unicode").rstrip().replace(" />", "/>")
            if server_text[start:end] != block:
                server_text = server_text[:start] + block + server_text[end:]
                server_modified.add(name)
        if server_modified:
            atomic_write_text(server_path, server_text)

        roots = tuple(sorted(modified_roots | server_modified))
        if roots:
            changed[map_id] = roots

    return changed


def patch_existing_reactors() -> dict[int, list[tuple[int, int]]]:
    changed: dict[int, list[tuple[int, int]]] = {}
    for map_id in MAP_IDS:
        path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        data = bytearray(path.read_bytes())
        image = WzImage.from_bytes(bytes(data), key=GMS_KEY, name=path.name)
        image.parse()
        if image.truncated or image.parse_warnings:
            raise RuntimeError(
                f"{path}: truncated={image.truncated} warnings={image.parse_warnings}"
            )

        spans: list[tuple[int, int]] = []
        reactor = image.root.child("reactor")
        if isinstance(reactor, WzSubProperty):
            for entry in reactor.children():
                reactor_id = entry.child("id")
                if not isinstance(reactor_id, WzStringProperty):
                    continue
                replacement = REACTOR_ID_PROJECTION.get(str(reactor_id.value))
                if replacement is None:
                    continue
                if (
                    reactor_id._payload_offset is None
                    or reactor_id._payload_length is None
                    or reactor_id._encoding is None
                    or reactor_id._indirected
                ):
                    raise RuntimeError(f"{path}: reactor/{entry.name}/id is not safely patchable")
                encoded = re_encrypt_string(
                    image.wz_file.reader, replacement, reactor_id._encoding
                )
                if len(encoded) != reactor_id._payload_length:
                    raise RuntimeError(
                        f"{path}: reactor/{entry.name}/id replacement changes byte length"
                    )
                start = int(reactor_id._payload_offset)
                end = start + len(encoded)
                data[start:end] = encoded
                spans.append((start, end))

        if spans:
            atomic_write_bytes(path, bytes(data))
            changed[map_id] = spans

    return changed


def patch_existing_field_limits() -> dict[int, tuple[int, int]]:
    changed: dict[int, tuple[int, int]] = {}
    for map_id, replacement in LEGACY_FIELD_LIMIT_OVERRIDES.items():
        client_path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        data = bytearray(client_path.read_bytes())
        image = WzImage.from_bytes(bytes(data), key=GMS_KEY, name=client_path.name)
        image.parse()
        field_limit = image.root.get("info/fieldLimit")
        if not isinstance(field_limit, WzIntProperty):
            raise RuntimeError(f"{client_path}: missing integer info/fieldLimit")
        if field_limit._value_offset is None or field_limit._value_length is None:
            raise RuntimeError(f"{client_path}: fieldLimit is not safely patchable")

        current = int(field_limit.value)
        encoded_current = encode_compressed_int(current)
        encoded_replacement = encode_compressed_int(replacement)
        start = int(field_limit._value_offset)
        end = start + int(field_limit._value_length)
        if bytes(data[start:end]) != encoded_current:
            raise RuntimeError(f"{client_path}: fieldLimit payload does not match parsed value")
        if len(encoded_replacement) != int(field_limit._value_length):
            raise RuntimeError(f"{client_path}: fieldLimit replacement changes encoded length")
        if current != replacement:
            data[start:end] = encoded_replacement
            atomic_write_bytes(client_path, bytes(data))
            changed[map_id] = (start, end)

        server_path = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
        server_text = server_path.read_text(encoding="utf-8")
        server_root = ET.fromstring(server_text)
        server_info = next(
            (child for child in server_root if child.get("name") == "info"), None
        )
        server_field_limit = next(
            (
                child
                for child in (server_info if server_info is not None else [])
                if child.get("name") == "fieldLimit"
            ),
            None,
        )
        if server_field_limit is None or server_field_limit.get("value") is None:
            raise RuntimeError(f"{server_path}: missing info/fieldLimit")
        server_current = server_field_limit.get("value")
        if server_current != str(replacement):
            old_node = f'<int name="fieldLimit" value="{server_current}"/>'
            new_node = f'<int name="fieldLimit" value="{replacement}"/>'
            if server_text.count(old_node) != 1:
                raise RuntimeError(f"{server_path}: fieldLimit XML node is not uniquely patchable")
            atomic_write_text(server_path, server_text.replace(old_node, new_node, 1))

    return changed


def patch_existing_visible_portals() -> dict[int, list[tuple[int, int]]]:
    changed: dict[int, list[tuple[int, int]]] = {}
    for map_id, portal_names in LEGACY_VISIBLE_SCRIPT_PORTALS.items():
        client_path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        data = bytearray(client_path.read_bytes())
        image = WzImage.from_bytes(bytes(data), key=GMS_KEY, name=client_path.name)
        image.parse()
        portal = image.root.child("portal")
        if not isinstance(portal, WzSubProperty):
            raise RuntimeError(f"{client_path}: missing portal root")

        found: set[str] = set()
        spans: list[tuple[int, int]] = []
        for entry in portal.children():
            portal_name = str(child_value(entry, "pn") or "")
            if portal_name not in portal_names:
                continue
            found.add(portal_name)
            portal_type = entry.child("pt")
            if not isinstance(portal_type, WzIntProperty):
                raise RuntimeError(f"{client_path}: portal {portal_name} missing integer pt")
            if portal_type._value_offset is None or portal_type._value_length is None:
                raise RuntimeError(f"{client_path}: portal {portal_name}/pt is not safely patchable")
            current = int(portal_type.value)
            if current not in {7, 9}:
                raise RuntimeError(f"{client_path}: portal {portal_name} has unexpected pt={current}")
            encoded_current = encode_compressed_int(current)
            encoded_replacement = encode_compressed_int(7)
            start = int(portal_type._value_offset)
            end = start + int(portal_type._value_length)
            if bytes(data[start:end]) != encoded_current:
                raise RuntimeError(f"{client_path}: portal {portal_name}/pt payload mismatch")
            if len(encoded_replacement) != int(portal_type._value_length):
                raise RuntimeError(f"{client_path}: portal {portal_name}/pt changes encoded length")
            if current != 7:
                data[start:end] = encoded_replacement
                spans.append((start, end))
        if found != portal_names:
            raise RuntimeError(f"{client_path}: portal mismatch expected={portal_names} found={found}")
        if spans:
            atomic_write_bytes(client_path, bytes(data))
            changed[map_id] = spans

        server_path = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
        server_text = server_path.read_text(encoding="utf-8")
        server_root = ET.fromstring(server_text)
        server_portal = next(
            (child for child in server_root if child.get("name") == "portal"), None
        )
        if server_portal is None:
            raise RuntimeError(f"{server_path}: missing portal root")
        server_types: dict[str, str] = {}
        for entry in server_portal:
            portal_name = next(
                (
                    child.get("value")
                    for child in entry
                    if child.get("name") == "pn"
                ),
                None,
            )
            portal_type = next(
                (
                    child.get("value")
                    for child in entry
                    if child.get("name") == "pt"
                ),
                None,
            )
            if portal_name is not None and portal_type is not None:
                server_types[portal_name] = portal_type
        if set(server_types) & portal_names != portal_names:
            raise RuntimeError(f"{server_path}: missing expected script portals")
        unexpected_pt9 = {
            name for name, portal_type in server_types.items() if portal_type == "9"
        } - portal_names
        if unexpected_pt9:
            raise RuntimeError(f"{server_path}: unrelated pt=9 portals remain {unexpected_pt9}")
        patch_count = sum(server_types[name] == "9" for name in portal_names)
        if patch_count:
            old_node = '<int name="pt" value="9"/>'
            new_node = '<int name="pt" value="7"/>'
            if server_text.count(old_node) != patch_count:
                raise RuntimeError(f"{server_path}: pt=9 XML nodes are not uniquely patchable")
            atomic_write_text(
                server_path,
                server_text.replace(old_node, new_node, patch_count),
            )

    return changed


def collapse_existing_back_animations() -> dict[str, int]:
    expected: dict[str, set[str]] = defaultdict(set)
    for map_id in MAP_IDS:
        path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        image = WzImage.from_bytes(path.read_bytes(), key=GMS_KEY, name=path.name)
        image.parse()
        if image.truncated or image.parse_warnings:
            raise RuntimeError(
                f"{path}: truncated={image.truncated} warnings={image.parse_warnings}"
            )
        dependencies = collect_dependencies(image)
        for (kind, name), branches in dependencies["assets"].items():
            if kind == "Back":
                expected[name].update(branches)

    changed: dict[str, int] = {}
    for name, branches in sorted(expected.items()):
        path = ROOT / f"clien/Data/Map/Back/{name}.img"
        image = load_image(path, GMS_KEY)
        removed = collapse_back_animation_frames(image, branches)
        if not removed:
            continue
        write_client(path, image)
        write_server_xml(
            ROOT / f"gms-server/wz/Map.wz/Back/{name}.img.xml",
            image,
            f"{name}.img",
        )
        changed[name] = removed
    return changed


def strip_existing_map_load_dependencies() -> dict[int, list[str]]:
    changed: dict[int, list[str]] = {}
    for map_id in sorted(MAP_LOAD_SAFE_PROJECTION_IDS):
        path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        image = load_image(path, GMS_KEY)
        removed = project_map_load_safe_dependencies(image.root, map_id)
        if not removed:
            continue
        write_client(path, image)
        write_server_map_xml(image, map_id)
        changed[map_id] = removed
    return changed


def migrate() -> None:
    dependencies: dict[str, object] = {"assets": defaultdict(set), "npcs": set()}
    map_totals = {"canvases": 0, "links": 0, "resized": 0}
    for map_id in MAP_IDS:
        image, materializer = migrate_map(map_id)
        merge_dependencies(dependencies, collect_dependencies(image))
        map_totals["canvases"] += materializer.canvases
        map_totals["links"] += materializer.links
        map_totals["resized"] += materializer.resized

    asset_totals = {"files": 0, "branches": 0, "changed": 0, "canvases": 0, "links": 0, "resized": 0}
    for (kind, name), branches in sorted(dependencies["assets"].items()):
        stats = merge_asset(kind, name, branches)
        asset_totals["files"] += 1
        for key in ("branches", "changed", "canvases", "links", "resized"):
            asset_totals[key] += stats[key]

    npc_totals = {"npcs": 0, "canvases": 0, "links": 0, "resized": 0}
    for npc_id in sorted(dependencies["npcs"] | set(NPC_IDS)):
        stats = migrate_npc(npc_id)
        npc_totals["npcs"] += 1
        for key in ("canvases", "links", "resized"):
            npc_totals[key] += stats[key]

    verify()
    print(f"maps={len(MAP_IDS)} {map_totals}")
    print(f"assets={asset_totals}")
    print(f"npcs={npc_totals}")


def migrate_map(map_id: int) -> tuple[WzImage, CanvasMaterializer]:
    target_path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
    base_map_id = MAP_STRUCTURE_BASE_IDS.get(map_id)
    if base_map_id is not None:
        base_path = ROOT / f"clien/Data/Map/Map/Map4/{base_map_id}.img"
        data = base_path.read_bytes()
        image = WzImage.from_bytes(data, key=GMS_KEY, name=target_path.name)
        image.parse()
        if image.truncated or image.parse_warnings:
            raise RuntimeError(
                f"{base_path}: truncated={image.truncated} warnings={image.parse_warnings}"
            )
        project_boss_map_flow(image.root, map_id)
        visual_map_id = MAP_VISUAL_SOURCE_IDS.get(map_id)
        if visual_map_id is None:
            atomic_write_bytes(target_path, data)
            materializer = CanvasMaterializer()
        else:
            materializer = apply_map_visuals(image, map_id, visual_map_id)
            write_client(target_path, image)
    else:
        source_path = SOURCE / f"Map/Map/Map4/{map_id}.img"
        image, materializer = clone_image(
            source_path,
            lambda root, mid=map_id: sanitize_map(root, mid),
        )
        write_client(target_path, image)

    write_server_map_xml(image, map_id)
    return image, materializer


def apply_map_visuals(
    target: WzImage,
    map_id: int,
    visual_map_id: int,
) -> CanvasMaterializer:
    source_path = SOURCE / f"Map/Map/Map4/{visual_map_id}.img"
    source = load_image(source_path, BMS_KEY)
    if source.truncated or source.parse_warnings:
        raise RuntimeError(
            f"{source_path}: truncated={source.truncated} warnings={source.parse_warnings}"
        )
    sanitize_map(source.root, map_id)
    materializer = CanvasMaterializer()

    source_back = source.root.child("back")
    if not isinstance(source_back, WzSubProperty):
        raise RuntimeError(f"{source_path}: missing back root")
    target.root._children["back"] = clone_property(
        source_back,
        target.root,
        source,
        source_path,
        materializer,
    )

    return materializer


def migrate_selected_maps(map_ids: list[int]) -> None:
    for map_id in map_ids:
        migrate_map(map_id)

    verify()
    print(f"rebuilt maps={map_ids}")


def verify() -> None:
    expected_assets: dict[tuple[str, str], set[str]] = defaultdict(set)
    expected_npcs = set(NPC_IDS)
    for map_id in MAP_IDS:
        verify_map_contract(map_id)
        image = WzImage.from_bytes(
            (ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img").read_bytes(),
            key=GMS_KEY,
            name=f"{map_id}.img",
        )
        image.parse()
        dependencies = collect_dependencies(image)
        expected_npcs.update(dependencies["npcs"])
        for key, branches in dependencies["assets"].items():
            expected_assets[key].update(branches)

    for (kind, name), branches in sorted(expected_assets.items()):
        client_path = ROOT / f"clien/Data/Map/{kind}/{name}.img"
        server_path = ROOT / f"gms-server/wz/Map.wz/{kind}/{name}.img.xml"
        image = WzImage.from_bytes(client_path.read_bytes(), key=GMS_KEY, name=client_path.name)
        image.parse()
        if image.truncated or image.parse_warnings:
            raise RuntimeError(f"{client_path}: truncated={image.truncated} warnings={image.parse_warnings}")
        for branch in sorted(branches):
            node = image.root.get(branch)
            if node is None:
                raise RuntimeError(f"{client_path}: missing {branch}")
            if kind == "Back" and branch.startswith("ani/"):
                frame_count = sum(
                    1 for child in node.children() if child.name.isdigit()
                )
                if frame_count > MAX_LEGACY_BACK_ANIMATION_FRAMES:
                    raise RuntimeError(
                        f"{client_path}: {branch} has {frame_count} animation frames"
                    )
        verify_img(client_path, branches=branches)
        ET.parse(server_path)

    for npc_id in sorted(expected_npcs):
        verify_img(ROOT / f"clien/Data/Npc/{npc_id}.img")
        ET.parse(ROOT / f"gms-server/wz/Npc.wz/{npc_id}.img.xml")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--patch-field-limits-only", action="store_true")
    parser.add_argument("--patch-visible-portals-only", action="store_true")
    parser.add_argument("--patch-boss-flow-only", action="store_true")
    parser.add_argument("--patch-reactors-only", action="store_true")
    parser.add_argument("--collapse-back-animations-only", action="store_true")
    parser.add_argument("--strip-map-load-dependencies-only", action="store_true")
    parser.add_argument("--map-id", action="append", choices=MAP_IDS, type=int)
    args = parser.parse_args()

    if args.map_id:
        migrate_selected_maps(list(dict.fromkeys(args.map_id)))
        return 0
    if args.patch_boss_flow_only:
        changed = patch_existing_boss_map_flow()
        verify()
        for map_id, roots in changed.items():
            print(f"{map_id}: patched boss flow roots {roots}")
        return 0
    if args.patch_visible_portals_only:
        changed = patch_existing_visible_portals()
        verify()
        for map_id, spans in changed.items():
            print(f"{map_id}: patched visible script portal payloads {spans}")
        return 0
    if args.patch_field_limits_only:
        changed = patch_existing_field_limits()
        verify()
        for map_id, span in changed.items():
            print(f"{map_id}: patched fieldLimit payload {span}")
        return 0
    if args.strip_map_load_dependencies_only:
        changed = strip_existing_map_load_dependencies()
        verify()
        for map_id, removed in changed.items():
            print(f"{map_id}: removed optional map-load nodes {removed}")
        return 0
    if args.collapse_back_animations_only:
        changed = collapse_existing_back_animations()
        verify()
        for name, removed in changed.items():
            print(f"{name}: removed {removed} excess animation frames")
        return 0
    if args.patch_reactors_only:
        changed = patch_existing_reactors()
        verify()
        for map_id, spans in changed.items():
            print(f"{map_id}: patched reactor string payloads {spans}")
        return 0
    if args.verify_only:
        verify()
    else:
        migrate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
