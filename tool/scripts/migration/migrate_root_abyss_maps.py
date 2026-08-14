#!/usr/bin/env python3
"""Migrate Root Abyss map resources from TMS into BeiDou.

This migrates the TMS Root Abyss map chain, NPC/reactor shells, and map assets
with old-client map field filtering. Canvas resources are always projected to
GMS-keyed ARGB4444 for the legacy client.
"""

from __future__ import annotations

import io
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import quoteattr

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
SRC_CLIENT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
BACKUP_ROOT = Path("/private/tmp/root-abyss-map-migration-backup")
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzConvexProperty,
    WzDoubleProperty,
    WzFloatProperty,
    WzImage,
    WzIntProperty,
    WzKey,
    WzLongProperty,
    WzNullProperty,
    WzShortProperty,
    WzSoundProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


SOURCE_REGION = "BMS"
TARGET_CANVAS_FORMAT = 1
TARGET_KEY = WzKey.for_region("GMS")
TRANSPARENT_PIXEL = Image.new("RGBA", (1, 1), (0, 0, 0, 0))

RETIRED_MAP_IDS = set()
RETIRED_MAP_ID_STRINGS = {str(map_id) for map_id in RETIRED_MAP_IDS}
MAP_IDS = [
    int(p.stem)
    for p in sorted((SRC_CLIENT / "Map/Map/Map1").glob("1052*.img"))
    if int(p.stem) not in RETIRED_MAP_IDS
]
NORTH_GARDEN_MAP_IDS = {105200400, 105200800}
NORMAL_MOB_IDS = [7120110, 7120111, 7120112, 7120113, 7120114, 7120115, 9834610]
ROOT_ABYSS_BOSS_ROOM_SPAWNS = {
    105200110: (8910100, 489, 454),
    105200210: (8900100, -131, 550),
    105200310: (8920100, 60, 134),
    105200410: (8930100, -192, 442),
    105200510: (8910000, 489, 454),
    105200610: (8900000, -131, 550),
    105200710: (8920000, 60, 134),
    105200810: (8930000, -192, 442),
}
ADVANCED_BOSS_MOB_IDS = [
    8900000, 8900001, 8900002, 8900003,
    8910000, 8910001,
    8910100,
    8920000, 8920001, 8920002, 8920003, 8920004, 8920005, 8920006,
    8930000, 8930001,
]
MOB_CANVAS_SOURCE_IDS = [
    7120110, 7120111, 9834610,
    8900000, 8900001, 8900002, 8900003,
    8910000, 8910001,
    8910100,
    8920000, 8920001, 8920002, 8920004, 8920005,
    8930000, 8930001,
]
INCOMPLETE_CANVAS_ONLY_MOBS = {8900003, 8910100, 8930001}
BOSS_GAUGE_MOB_IDS = {
    8900000, 8900001, 8900002,
    8910000,
    8920000, 8920001, 8920002, 8920003,
}
SUPPORTED_ROOT_ABYSS_BOSS_SKILLS = {
    (110, 5),
    (120, 3), (120, 5), (120, 8),
    (121, 4),
    (122, 10),
    (123, 1),
    (127, 2),
    (128, 1), (128, 3), (128, 16),
    (131, 3), (131, 12), (131, 13),
    (134, 2),
    (141, 4),
    (142, 1),
    (145, 1), (145, 2),
}
ROOT_ABYSS_MOB_SKILL_LEVELS = []
ROOT_ABYSS_SECOND_PHASE_BOSS_HP = {
    8900001: 3_000_000_000,
    8910001: 3_000_000_000,
    8920001: 3_000_000_000,
}
HIGH_VERSION_MOB_INFO_FIELDS = {
    "attack",
    "bodyDisease", "bodyDiseaseLevel",
    "category",
    "chaseEffect",
    "default", "defaultHP", "defaultMP",
    "delAtomOnDead",
    "explosiveReward",
    "finalmaxHP",
    "firstAttackRange",
    "ignoreFieldOut", "ignoreMovable", "ignoreMoveImpact",
    "isRemoteRange",
    "linkMob",
    "maxHPb",
    "mobZone",
    "passive",
    "publicReward",
    "showNotRemoteDam",
    "stalking",
    "trans",
    "useReaction",
}
OLD_SERVER_REQUIRED_BOSS_INFO_FIELDS = {
    "PADamage": 0,
    "PDDamage": 0,
    "MADamage": 0,
    "MDDamage": 0,
    "level": 1,
}
NPC_IDS = [
    1064002, 1064003, 1064005, 1064006, 1064007, 1064008,
    1064009,
    1064012, 1064013, 1064014, 1064015, 1064032,
    3007007, 3007008, 9091004, 9091021, 9091023,
]
STRING_ONLY_NPC_IDS = [1064031]
ROOT_ABYSS_QUEST_IDS = [30000, *range(30002, 30023), 30027]
ROOT_ABYSS_ETC_ITEM_IDS = [4001755, 4001756]
REACTOR_IDS = [
    1058016, 1058017, 1058018, 1058019, 1058020, 1058021, 1058022, 1058023,
    1058024, 1058025, 1058026, 1058027, 1058028, 1058029,
]

REACTOR_TEMPLATE = {
    reactor_id: reactor_id for reactor_id in REACTOR_IDS
}

IMGDIR_TAG_RE = re.compile(r"</?imgdir\b[^>]*>")
SOURCE_LINK_IMG_CACHE: dict[Path, WzImage] = {}


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def atomic_write_text(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def backup(path: Path) -> None:
    if not path.exists():
        return
    rel = path.relative_to(ROOT)
    dst = BACKUP_ROOT / rel
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), TARGET_KEY)


def source_img(path: Path) -> WzImage:
    img = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region(SOURCE_REGION), name=path.name)
    img.parse()
    return img


def source_img_by_rel(rel: Path) -> WzImage:
    if rel not in SOURCE_LINK_IMG_CACHE:
        SOURCE_LINK_IMG_CACHE[rel] = source_img(SRC_CLIENT / rel)
    return SOURCE_LINK_IMG_CACHE[rel]


def source_rel_for_link(value: str) -> tuple[Path, str] | None:
    parts = value.split("/")
    img_index = next((idx for idx, part in enumerate(parts) if part.endswith(".img")), None)
    if img_index is None:
        return None
    return Path(*parts[: img_index + 1]), "/".join(parts[img_index + 1 :])


def source_canvas_from_link(value: str) -> WzCanvasProperty | None:
    resolved = source_rel_for_link(value)
    if resolved is None:
        return None
    rel, path = resolved
    src_path = SRC_CLIENT / rel
    if not src_path.exists():
        return None
    node = source_img_by_rel(rel).get(path)
    return node if isinstance(node, WzCanvasProperty) else None


def inline_canvas_outlinks(prop) -> None:
    if isinstance(prop, WzCanvasProperty):
        outlink = prop.child("_outlink")
        if isinstance(outlink, WzStringProperty):
            source = source_canvas_from_link(str(outlink.value))
            if source is None:
                raise RuntimeError(f"cannot resolve canvas _outlink {outlink.value}")
            image = decode_canvas(source, region=SOURCE_REGION)
            prop._migration_image = image
            prop.width = int(source.width)
            prop.height = int(source.height)
            remove_child(prop, "_outlink")
            remove_child(prop, "_inlink")

    if hasattr(prop, "children"):
        for child in prop.children():
            inline_canvas_outlinks(child)


def reencode_canvas_tree(prop) -> None:
    if isinstance(prop, WzCanvasProperty) and (prop.has_pixels() or hasattr(prop, "_migration_image")):
        try:
            image = getattr(prop, "_migration_image", None)
            if image is None:
                if int(prop.width) <= 0 or int(prop.height) <= 0:
                    raise ValueError(f"invalid canvas size {prop.width}x{prop.height}")
                image = decode_canvas(prop, region=SOURCE_REGION)
            width = int(prop.width)
            height = int(prop.height)
        except Exception:
            image = TRANSPARENT_PIXEL
            width = 1
            height = 1
        prop.width = width
        prop.height = height
        prop.format = TARGET_CANVAS_FORMAT
        prop.format2 = 0
        prop._png_data = encode_canvas_payload(image, TARGET_CANVAS_FORMAT, width, height, key=TARGET_KEY, listwz=False)
        prop._png_length = len(prop._png_data)

    if hasattr(prop, "children"):
        for child in prop.children():
            reencode_canvas_tree(child)


def normalize_canvas_metadata_tree(prop) -> None:
    if isinstance(prop, WzCanvasProperty):
        prop.format = TARGET_CANVAS_FORMAT
        prop.format2 = 0
    if hasattr(prop, "children"):
        for child in prop.children():
            normalize_canvas_metadata_tree(child)


def sanitize_root_abyss_map(root: WzSubProperty, map_id: int | None = None) -> None:
    info = root.child("info")
    if info is not None:
        for key in (
            "standAlone",
            "partyStandAlone",
            "noMapCmd",
            "fieldScript",
            "onFirstUserEnter",
            "onUserEnter",
            "AmbientBGM",
            "AmbientBGMv",
            "ableMapleAuction",
            "abilityPresetBlock",
            "fieldLimit2",
            "limitUpgradeItem",
            "noBackOverlapped",
            "noChair",
            "qrLimitState",
            "qrLimitState2",
            "ReviveCurFieldOfNoTransfer",
            "ReviveCurFieldOfNoTransferPoint",
            "ReviveCurFieldOfNoTransferNotDamaged",
        ):
            remove_child(info, key)
        mark = info.child("mapMark")
        if isinstance(mark, WzStringProperty) and mark.value == "rootabyss":
            remove_child(info, "mapMark")
        if child_value(info, "forcedReturn") == 910000000:
            ensure_int_child(info, "forcedReturn", 105200000)

    for layer in [p for p in root.children() if p.name.isdigit()]:
        obj_root = layer.child("obj")
        if obj_root is None:
            continue
        for obj in obj_root.children():
            for key in ("hide", "reactor", "flow"):
                remove_child(obj, key)

    portal_root = root.child("portal")
    if portal_root is not None:
        for portal in portal_root.children():
            if map_id == 105200400 and child_value(portal, "script") == "rootaNext3":
                remove_child(portal_root, portal.name)
                continue
            for key in ("delay", "hideTooltip", "onlyOnce"):
                remove_child(portal, key)
            script = portal.child("script")
            if isinstance(script, WzStringProperty) and script.value == "":
                remove_child(portal, "script")
            if child_value(portal, "script") == "rootabyssOut":
                ensure_int_child(portal, "tm", 999999999)
                ensure_string_child(portal, "tn", "")
                ensure_string_child(portal, "script", "rootabyssGardenOut")
            if child_value(portal, "tm") == 910000000:
                ensure_int_child(portal, "tm", 999999999)
                ensure_string_child(portal, "tn", "")
                ensure_string_child(portal, "script", "rootabyssGardenOut")
            if map_id == 105200900 and child_value(portal, "tm") == 105200000 and child_value(portal, "tn") == "in00":
                ensure_string_child(portal, "tn", "sp")

    life_root = root.child("life")
    if isinstance(life_root, WzSubProperty):
        for life in list(life_root.children()):
            if child_value(life, "type") == "m" and int(child_value(life, "id") or 0) not in NORMAL_MOB_IDS:
                remove_child(life_root, life.name)
                continue
            for key in ("forcedZPage", "forcedZMass", "limitedname"):
                remove_child(life, key)

    if map_id in NORTH_GARDEN_MAP_IDS:
        move_garden_foot_objects_to_layer_zero(root)
    if map_id in ROOT_ABYSS_BOSS_ROOM_SPAWNS and isinstance(info, WzSubProperty):
        ensure_string_child(info, "onUserEnter", "rootaBossEnter")


def child_value(node, name: str):
    child = node.child(name) if node is not None else None
    return getattr(child, "value", None)


def next_numeric_child_name(parent: WzSubProperty) -> str:
    used = {child.name for child in parent.children()}
    idx = 0
    while str(idx) in used:
        idx += 1
    return str(idx)


def is_garden_foot_object(obj) -> bool:
    return (
        child_value(obj, "oS") == "rootabyss"
        and child_value(obj, "l0") == "garden"
        and child_value(obj, "l1") == "foot"
    )


def move_object_to_layer_zero(obj_root: WzSubProperty, obj, target_obj_root: WzSubProperty) -> None:
    remove_child(obj_root, obj.name)
    if target_obj_root.child(obj.name) is not None:
        obj.name = next_numeric_child_name(target_obj_root)
    target_obj_root.add(obj)


def move_garden_foot_objects_to_layer_zero(root: WzSubProperty) -> int:
    target_layer = root.child("0")
    if not isinstance(target_layer, WzSubProperty):
        target_layer = WzSubProperty("0", root)
        root.add(target_layer)
    target_obj_root = target_layer.child("obj")
    if not isinstance(target_obj_root, WzSubProperty):
        target_obj_root = WzSubProperty("obj", target_layer)
        target_layer.add(target_obj_root)

    moved = 0
    for layer in [p for p in root.children() if p.name.isdigit() and p.name != "0"]:
        obj_root = layer.child("obj")
        if not isinstance(obj_root, WzSubProperty):
            continue
        for obj in list(obj_root.children()):
            if not is_garden_foot_object(obj):
                continue
            move_object_to_layer_zero(obj_root, obj, target_obj_root)
            moved += 1
    return moved


def ensure_int_child(parent: WzSubProperty, name: str, value: int) -> None:
    remove_child(parent, name)
    parent.add(WzIntProperty(name, value, parent))


def ensure_string_child(parent: WzSubProperty, name: str, value: str) -> None:
    remove_child(parent, name)
    parent.add(WzStringProperty(name, value, parent))


def ensure_missing_int_child(parent: WzSubProperty, name: str, value: int) -> None:
    if parent.child(name) is None:
        parent.add(WzIntProperty(name, value, parent))


def sanitize_root_abyss_boss_mob(root: WzSubProperty, mob_id: int) -> None:
    info = root.child("info")
    if isinstance(info, WzSubProperty):
        for key in HIGH_VERSION_MOB_INFO_FIELDS:
            remove_child(info, key)
        ensure_int_child(info, "mobType", 1)
        ensure_old_server_boss_info_fields(info, mob_id)
        if mob_id not in BOSS_GAUGE_MOB_IDS:
            ensure_int_child(info, "boss", 0)
            remove_child(info, "hpTagColor")
            remove_child(info, "hpTagBgcolor")
        sanitize_boss_skill_entries(root, info)

    for child in list(root.children()):
        if child.name.startswith("skillAfter"):
            remove_child(root, child.name)


def set_root_abyss_server_boss_hp(root: WzSubProperty, mob_id: int) -> None:
    hp = ROOT_ABYSS_SECOND_PHASE_BOSS_HP.get(mob_id)
    if hp is None:
        return
    info = root.child("info")
    if not isinstance(info, WzSubProperty):
        return
    remove_child(info, "maxHP")
    info.add(WzStringProperty("maxHP", str(hp), info))


def ensure_old_server_boss_info_fields(info: WzSubProperty, mob_id: int) -> None:
    for name, default in OLD_SERVER_REQUIRED_BOSS_INFO_FIELDS.items():
        value = default
        if name in {"PDDamage", "MDDamage"} and mob_id in BOSS_GAUGE_MOB_IDS:
            value = 30000
        ensure_missing_int_child(info, name, value)


def sanitize_boss_skill_entries(root: WzSubProperty, info: WzSubProperty) -> None:
    skill_root = info.child("skill")
    if not isinstance(skill_root, WzSubProperty):
        return

    kept = []
    for entry in sorted(skill_root.children(), key=lambda item: int(item.name)):
        skill_id = child_value(entry, "skill")
        level = child_value(entry, "level")
        action = child_value(entry, "action")
        if (skill_id, level) not in SUPPORTED_ROOT_ABYSS_BOSS_SKILLS:
            continue
        if action is not None and root.child(f"skill{action}") is None:
            continue
        kept.append((int(skill_id), int(level), int(action or 1)))

    remove_child(info, "skill")
    if not kept:
        return

    new_skill_root = WzSubProperty("skill", info)
    for idx, (skill_id, level, action) in enumerate(kept):
        entry = WzSubProperty(str(idx), new_skill_root)
        entry.add(WzIntProperty("skill", skill_id, entry))
        entry.add(WzIntProperty("level", level, entry))
        entry.add(WzIntProperty("action", action, entry))
        new_skill_root.add(entry)
    info.add(new_skill_root)


def reencode_img(src: Path, dst: Path, overwrite: bool = True, sanitizer=None) -> str:
    if dst.exists() and not overwrite:
        return "skip-existing"
    img = source_img(src)
    if sanitizer is not None:
        sanitizer(img.root)
    inline_canvas_outlinks(img.root)
    reencode_canvas_tree(img.root)
    backup(dst)
    atomic_write_bytes(dst, encode_image_body(img, gms_reader()))
    return "write"


def xml_escape_attr(value: str) -> str:
    return quoteattr(value)


def property_to_xml(prop, indent: int = 1) -> str:
    pad = "  " * indent
    name_attr = f"name={xml_escape_attr(prop.name)}"

    if isinstance(prop, WzNullProperty):
        return f"{pad}<null {name_attr}/>"
    if isinstance(prop, WzVectorProperty):
        return f'{pad}<vector {name_attr} x="{prop.x}" y="{prop.y}"/>'
    if isinstance(prop, WzCanvasProperty):
        attrs = f'{name_attr} width="{prop.width}" height="{prop.height}"'
        if int(prop.format) + int(prop.format2) != 0:
            attrs += f' format="{int(prop.format) + int(prop.format2)}"'
        if not prop.has_children():
            return f"{pad}<canvas {attrs}/>"
        body = "\n".join(property_to_xml(child, indent + 1) for child in prop.children())
        return f"{pad}<canvas {attrs}>\n{body}\n{pad}</canvas>"
    if isinstance(prop, WzSoundProperty):
        return f'{pad}<sound {name_attr} length_ms="{prop.length_ms}" bytes="{prop.value}"/>'
    if isinstance(prop, WzConvexProperty):
        body = "\n".join(f'{pad}  <vector name="{point.name}" x="{point.x}" y="{point.y}"/>' for point in prop.points)
        return f"{pad}<extended {name_attr}>\n{body}\n{pad}</extended>"
    if isinstance(prop, WzUolProperty):
        return f"{pad}<uol {name_attr} value={xml_escape_attr(str(prop.value))}/>"
    if isinstance(prop, WzSubProperty):
        if not prop.has_children():
            return f"{pad}<imgdir {name_attr}/>"
        body = "\n".join(property_to_xml(child, indent + 1) for child in prop.children())
        return f"{pad}<imgdir {name_attr}>\n{body}\n{pad}</imgdir>"

    value = getattr(prop, "value", "")
    if isinstance(prop, WzShortProperty):
        tag = "short"
    elif isinstance(prop, WzIntProperty):
        tag = "int"
    elif isinstance(prop, WzLongProperty):
        tag = "long"
    elif isinstance(prop, WzFloatProperty):
        tag = "float"
    elif isinstance(prop, WzDoubleProperty):
        tag = "double"
    elif isinstance(prop, WzStringProperty):
        tag = "string"
    else:
        tag = "string"
    return f"{pad}<{tag} {name_attr} value={xml_escape_attr(str(value))}/>"


def img_to_xml(img: WzImage, root_name: str | None = None) -> str:
    name = root_name or img.name
    body = "\n".join(property_to_xml(child, 1) for child in img.root.children())
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<imgdir name="{name}">\n{body}\n</imgdir>\n'


def write_server_xml_from_source(
    src: Path,
    dst: Path,
    root_name: str | None = None,
    overwrite: bool = True,
    sanitizer=None,
) -> str:
    if dst.exists() and not overwrite:
        return "skip-existing"
    img = source_img(src)
    if sanitizer is not None:
        sanitizer(img.root)
    inline_canvas_outlinks(img.root)
    normalize_canvas_metadata_tree(img.root)
    backup(dst)
    atomic_write_text(dst, img_to_xml(img, root_name=root_name))
    return "write"


def clone_property(prop, name: str | None = None, parent=None):
    new_name = prop.name if name is None else name
    if isinstance(prop, WzCanvasProperty):
        out = WzCanvasProperty(new_name, parent)
        out.width = prop.width
        out.height = prop.height
        out.format = TARGET_CANVAS_FORMAT
        out.format2 = 0
        if prop.has_pixels() or hasattr(prop, "_migration_image"):
            if (
                getattr(prop, "_png_data", None) is not None
                and int(prop.format) == TARGET_CANVAS_FORMAT
                and int(prop.format2) == 0
            ):
                out._png_data = bytes(prop._png_data)
            else:
                image = getattr(prop, "_migration_image", None)
                if image is None:
                    image = decode_canvas(prop, region=SOURCE_REGION)
                out._png_data = encode_canvas_payload(
                    image,
                    TARGET_CANVAS_FORMAT,
                    int(prop.width),
                    int(prop.height),
                    key=TARGET_KEY,
                    listwz=False,
                )
            out._png_length = len(out._png_data)
        for child in prop.children():
            out.add(clone_property(child, parent=out))
        return out
    if isinstance(prop, WzVectorProperty):
        return WzVectorProperty(new_name, prop.x, prop.y, parent)
    if isinstance(prop, WzIntProperty):
        return WzIntProperty(new_name, int(prop.value), parent)
    if isinstance(prop, WzShortProperty):
        return WzShortProperty(new_name, int(prop.value), parent)
    if isinstance(prop, WzLongProperty):
        return WzLongProperty(new_name, int(prop.value), parent)
    if isinstance(prop, WzFloatProperty):
        return WzFloatProperty(new_name, float(prop.value), parent)
    if isinstance(prop, WzDoubleProperty):
        return WzDoubleProperty(new_name, float(prop.value), parent)
    if isinstance(prop, WzStringProperty):
        return WzStringProperty(new_name, str(prop.value), parent)
    if isinstance(prop, WzUolProperty):
        return WzUolProperty(new_name, str(prop.value), parent)
    if isinstance(prop, WzNullProperty):
        return WzNullProperty(new_name, parent)
    if isinstance(prop, WzConvexProperty):
        out = WzConvexProperty(new_name, parent)
        for point in prop.points:
            out.points.append(clone_property(point, parent=out))
        return out
    if isinstance(prop, WzSubProperty):
        out = WzSubProperty(new_name, parent)
        for child in prop.children():
            out.add(clone_property(child, parent=out))
        return out
    raise TypeError(f"unsupported property: {type(prop).__name__}")


def target_img(path: Path) -> WzImage:
    img = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=path.name)
    img.parse()
    return img


def write_server_xml_from_client_img(client_path: Path, server_path: Path) -> None:
    img = target_img(client_path)
    backup(server_path)
    atomic_write_text(server_path, img_to_xml(img))


def patch_server_boss_xml_hp(server_path: Path, mob_id: int) -> None:
    expected_hp = ROOT_ABYSS_SECOND_PHASE_BOSS_HP.get(mob_id)
    if expected_hp is None:
        return
    root = ET.parse(server_path).getroot()
    info = direct_xml_child(root, "info")
    if info is None:
        return
    for child in list(info):
        if child.get("name") == "maxHP":
            info.remove(child)
    info.append(ET.Element("string", {"name": "maxHP", "value": str(expected_hp)}))
    atomic_write_text(
        server_path,
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'{ET.tostring(root, encoding="unicode", short_empty_elements=True)}\n',
    )


def replace_children_from_source(parent: WzSubProperty, source_root: WzSubProperty, skip: set[str] | None = None) -> int:
    skip = skip or set()
    changed = 0
    for child in source_root.children():
        if child.name in skip:
            continue
        remove_child(parent, child.name)
        parent.add(clone_property(child, name=child.name, parent=parent))
        changed += 1
    return changed


def compatible_normal_mob_info(template_id: int, target_id: int) -> WzSubProperty:
    template_path = ROOT / f"clien/Data/Mob/{template_id}.img"
    template = target_img(template_path)
    info = template.get("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"template mob {template_id} missing info")
    out = clone_property(info, name="info")
    if target_id == 9834610:
        for key, value in {
            "level": 1,
            "maxHP": 1,
            "maxMP": 0,
            "PADamage": 0,
            "PDDamage": 0,
            "MADamage": 0,
            "MDDamage": 0,
            "acc": 0,
            "eva": 0,
            "pushed": 100000000,
            "summonType": 1,
            "bodyAttack": 0,
            "exp": 0,
        }.items():
            ensure_int_child(out, key, value)
        ensure_string_child(out, "mobType", "10N")
        remove_child(out, "boss")
    return out


def mob_template_for(mob_id: int) -> int:
    if mob_id == 7120111:
        return 7120113
    return 7120112


def migrate_mob_canvas_resource(mob_id: int) -> str:
    src_path = SRC_CLIENT / f"Mob/_Canvas/{mob_id}.img"
    if not src_path.exists():
        return "skip-missing-source"
    client_path = ROOT / f"clien/Data/Mob/{mob_id}.img"
    source = source_img(src_path)
    inline_canvas_outlinks(source.root)
    reencode_canvas_tree(source.root)

    if client_path.exists():
        target = target_img(client_path)
        if mob_id in INCOMPLETE_CANVAS_ONLY_MOBS:
            return "skip-incomplete-source"
        replace_children_from_source(target.root, source.root, skip={"info"})
        if mob_id in ADVANCED_BOSS_MOB_IDS:
            sanitize_root_abyss_boss_mob(target.root, mob_id)
    else:
        template_id = mob_template_for(mob_id)
        template = target_img(ROOT / f"clien/Data/Mob/{template_id}.img")
        target = WzImage.from_bytes(encode_image_body(template, gms_reader()), key=TARGET_KEY, name=f"{mob_id}.img")
        target.parse()
        target.root._children.clear()
        info = compatible_normal_mob_info(template_id, mob_id)
        target.root.add(clone_property(info, name="info", parent=target.root))
        replace_children_from_source(target.root, source.root, skip={"info"})

    backup(client_path)
    atomic_write_bytes(client_path, encode_image_body(target, gms_reader()))
    server_path = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
    write_server_xml_from_client_img(client_path, server_path)
    patch_server_boss_xml_hp(server_path, mob_id)
    return "write"


def iter_canvas_properties(prop, prefix: str = ""):
    path = f"{prefix}/{prop.name}" if prefix else prop.name
    if isinstance(prop, WzCanvasProperty):
        yield path, prop
    if hasattr(prop, "children"):
        for child in prop.children():
            yield from iter_canvas_properties(child, path)


def is_transparent_1x1(prop: WzCanvasProperty, region: str) -> bool:
    try:
        image = decode_canvas(prop, region=region)
    except Exception:
        return False
    return image.size == (1, 1) and image.getbbox() is None


def remove_child(parent: WzSubProperty, name: str) -> None:
    parent._children.pop(name, None)


def direct_xml_child(parent: ET.Element | None, name: str) -> ET.Element | None:
    if parent is None:
        return None
    for child in parent:
        if child.get("name") == name:
            return child
    return None


def compatible_client_mobskill_level_fields(img: WzImage, skill_id: int, target_level: int) -> set[str]:
    level_root = img.get(f"{skill_id}/level")
    if not isinstance(level_root, WzSubProperty):
        return set()
    fields: set[str] = set()
    for level in level_root.children():
        if level.name == str(target_level):
            continue
        if hasattr(level, "children"):
            fields.update(child.name for child in level.children())
    return fields


def prune_client_mobskill_level(level_node: WzSubProperty, allowed_fields: set[str]) -> None:
    if not allowed_fields:
        return
    for child in list(level_node.children()):
        if child.name not in allowed_fields:
            remove_child(level_node, child.name)


def patch_client_mobskill_levels() -> int:
    src = source_img(SRC_CLIENT / "Skill/MobSkill.img")
    dst_path = ROOT / "clien/Data/Skill/MobSkill.img"
    dst = WzImage.from_bytes(dst_path.read_bytes(), key=TARGET_KEY, name=dst_path.name)
    dst.parse()
    changed = 0
    for skill_id, level in ROOT_ABYSS_MOB_SKILL_LEVELS:
        source_level = src.get(f"{skill_id}/level/{level}")
        if source_level is None:
            raise RuntimeError(f"missing source MobSkill {skill_id}/level/{level}")
        skill = dst.get(str(skill_id))
        if not isinstance(skill, WzSubProperty):
            raise RuntimeError(f"current client does not support MobSkill {skill_id}")
        level_root = dst.get(f"{skill_id}/level")
        if not isinstance(level_root, WzSubProperty):
            raise RuntimeError(f"current client missing MobSkill {skill_id}/level")
        new_level = clone_property(source_level, str(level), level_root)
        prune_client_mobskill_level(new_level, compatible_client_mobskill_level_fields(dst, skill_id, level))
        existing = dst.get(f"{skill_id}/level/{level}")
        if existing is not None and property_to_xml(existing) == property_to_xml(new_level):
            continue
        level_root.add(new_level)
        changed += 1
    if changed:
        backup(dst_path)
        atomic_write_bytes(dst_path, encode_image_body(dst, gms_reader()))
    return changed


def patch_server_mobskill_levels() -> int:
    src = source_img(SRC_CLIENT / "Skill/MobSkill.img")
    dst_path = ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml"
    root = ET.parse(dst_path).getroot()
    changed = 0
    for skill_id, level in ROOT_ABYSS_MOB_SKILL_LEVELS:
        source_level = src.get(f"{skill_id}/level/{level}")
        if source_level is None:
            raise RuntimeError(f"missing source MobSkill {skill_id}/level/{level}")
        skill = direct_xml_child(root, str(skill_id))
        if skill is None:
            raise RuntimeError(f"current server does not support MobSkill {skill_id}")
        level_root = direct_xml_child(skill, "level")
        if level_root is None:
            raise RuntimeError(f"current server missing MobSkill {skill_id}/level")
        new_level = ET.fromstring(property_to_xml(source_level, 0))
        old_level = direct_xml_child(level_root, str(level))
        if old_level is not None and ET.tostring(old_level, encoding="unicode") == ET.tostring(new_level, encoding="unicode"):
            continue
        if old_level is not None:
            level_root.remove(old_level)
        level_root.append(new_level)
        changed += 1
    if changed:
        backup(dst_path)
        atomic_write_text(dst_path, f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n{ET.tostring(root, encoding="unicode", short_empty_elements=True)}\n')
    return changed


def patch_root_abyss_mobskills() -> dict[str, int]:
    if not ROOT_ABYSS_MOB_SKILL_LEVELS:
        return {"client": 0, "server": 0}
    return {
        "client": patch_client_mobskill_levels(),
        "server": patch_server_mobskill_levels(),
    }


def upsert_client_string(img_name: str, ids: list[int]) -> None:
    src = source_img(SRC_CLIENT / f"String/{img_name}.img")
    dst_path = ROOT / f"clien/Data/String/{img_name}.img"
    dst = WzImage.from_bytes(dst_path.read_bytes(), key=TARGET_KEY, name=dst_path.name)
    dst.parse()
    changed = False

    for item_id in ids:
        key = str(item_id)
        source_node = src.get(key)
        if source_node is None:
            raise RuntimeError(f"source String/{img_name}.img missing {key}")
        remove_child(dst.root, key)
        dst.root.add(clone_property(source_node, name=key, parent=dst.root))
        changed = True

    if changed:
        backup(dst_path)
        atomic_write_bytes(dst_path, encode_image_body(dst, gms_reader()))


def upsert_server_string_xml(img_name: str, ids: list[int]) -> None:
    src = source_img(SRC_CLIENT / f"String/{img_name}.img")
    for server_root in (ROOT / "gms-server/wz", ROOT / "gms-server/wz-zh-CN"):
        dst_path = server_root / f"String.wz/{img_name}.img.xml"
        if not dst_path.exists():
            continue
        root = ET.parse(dst_path).getroot()
        for item_id in ids:
            key = str(item_id)
            source_node = src.get(key)
            if source_node is None:
                raise RuntimeError(f"source String/{img_name}.img missing {key}")
            for child in list(root):
                if child.get("name") == key:
                    root.remove(child)
            root.append(ET.fromstring(property_to_xml(source_node, 1).strip()))

        backup(dst_path)
        xml = ET.tostring(root, encoding="unicode", short_empty_elements=True)
        atomic_write_text(dst_path, f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n{xml}\n')


def get_or_create_child(parent: WzSubProperty, name: str) -> WzSubProperty:
    child = parent.child(name)
    if isinstance(child, WzSubProperty):
        return child
    if child is not None:
        remove_child(parent, name)
    child = WzSubProperty(name, parent)
    parent.add(child)
    return child


def get_or_create_xml_child(parent: ET.Element, name: str) -> ET.Element:
    child = direct_xml_child(parent, name)
    if child is not None and child.tag == "imgdir":
        return child
    if child is not None:
        parent.remove(child)
    return ET.SubElement(parent, "imgdir", {"name": name})


def upsert_client_node_by_path(dst_path: Path, source_node, path_parts: list[str]) -> None:
    dst = target_img(dst_path)
    parent = dst.root
    for part in path_parts[:-1]:
        parent = get_or_create_child(parent, part)
    remove_child(parent, path_parts[-1])
    parent.add(clone_property(source_node, name=path_parts[-1], parent=parent))
    backup(dst_path)
    atomic_write_bytes(dst_path, encode_image_body(dst, gms_reader()))


def upsert_server_xml_node_by_path(dst_path: Path, source_node, path_parts: list[str]) -> None:
    root = ET.parse(dst_path).getroot()
    parent = root
    for part in path_parts[:-1]:
        parent = get_or_create_xml_child(parent, part)
    for child in list(parent):
        if child.get("name") == path_parts[-1]:
            parent.remove(child)
    parent.append(ET.fromstring(property_to_xml(source_node, 1).strip()))
    backup(dst_path)
    xml = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    atomic_write_text(dst_path, f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n{xml}\n')


def upsert_server_xml_node_all_roots(rel: Path, source_node, path_parts: list[str]) -> int:
    changed = 0
    for server_root in (ROOT / "gms-server/wz", ROOT / "gms-server/wz-zh-CN"):
        dst_path = server_root / rel
        if dst_path.exists():
            upsert_server_xml_node_by_path(dst_path, source_node, path_parts)
            changed += 1
    return changed


def migrate_etc_item_resources() -> dict[str, int]:
    stats = {"client": 0, "server": 0, "strings": 0}
    src_item = source_img(SRC_CLIENT / "Item/Etc/0400.img")
    client_item_path = ROOT / "clien/Data/Item/Etc/0400.img"
    client_item = target_img(client_item_path)
    for item_id in ROOT_ABYSS_ETC_ITEM_IDS:
        node_name = f"0{item_id}"
        source_node = src_item.get(node_name)
        if source_node is None:
            raise RuntimeError(f"source Item/Etc/0400.img missing {node_name}")
        clone = clone_property(source_node, name=node_name, parent=client_item.root)
        inline_canvas_outlinks(clone)
        reencode_canvas_tree(clone)
        remove_child(client_item.root, node_name)
        client_item.root.add(clone)
        stats["client"] += 1
    backup(client_item_path)
    atomic_write_bytes(client_item_path, encode_image_body(client_item, gms_reader()))

    server_item_path = ROOT / "gms-server/wz/Item.wz/Etc/0400.img.xml"
    server_item = ET.parse(server_item_path).getroot()
    for item_id in ROOT_ABYSS_ETC_ITEM_IDS:
        node_name = f"0{item_id}"
        node = target_img(client_item_path).get(node_name)
        for child in list(server_item):
            if child.get("name") == node_name:
                server_item.remove(child)
        server_item.append(ET.fromstring(property_to_xml(node, 1).strip()))
        stats["server"] += 1
    backup(server_item_path)
    atomic_write_text(
        server_item_path,
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'{ET.tostring(server_item, encoding="unicode", short_empty_elements=True)}\n',
    )

    src_string = source_img(SRC_CLIENT / "String/Etc.img")
    for item_id in ROOT_ABYSS_ETC_ITEM_IDS:
        source_node = src_string.get(f"Etc/{item_id}")
        if source_node is None:
            raise RuntimeError(f"source String/Etc.img missing Etc/{item_id}")
        upsert_client_node_by_path(
            ROOT / "clien/Data/String/Etc.img",
            source_node,
            ["Etc", str(item_id)],
        )
        stats["strings"] += upsert_server_xml_node_all_roots(
            Path("String.wz/Etc.img.xml"),
            source_node,
            ["Etc", str(item_id)],
        )
    return stats


def migrate_quest_data() -> dict[str, int]:
    stats = {"client": 0, "server": 0}
    quest_files = {
        "QuestInfo": "QuestInfo.img",
        "Check": "Check.img",
        "Act": "Act.img",
        "Say": "Say.img",
    }
    for branch, file_name in quest_files.items():
        client_path = ROOT / "clien/Data/Quest" / file_name
        client = target_img(client_path)
        server_roots = []
        for server_root in (ROOT / "gms-server/wz", ROOT / "gms-server/wz-zh-CN"):
            server_path = server_root / "Quest.wz" / f"{file_name}.xml"
            if server_path.exists():
                server_roots.append((server_path, ET.parse(server_path).getroot()))
        for quest_id in ROOT_ABYSS_QUEST_IDS:
            src = source_img(SRC_CLIENT / f"Quest/QuestData/{quest_id}.img")
            source_node = src.get(branch)
            if source_node is None:
                raise RuntimeError(f"source QuestData/{quest_id}.img missing {branch}")
            remove_child(client.root, str(quest_id))
            client.root.add(clone_property(source_node, name=str(quest_id), parent=client.root))
            for _path, server_root in server_roots:
                for child in list(server_root):
                    if child.get("name") == str(quest_id):
                        server_root.remove(child)
                server_root.append(ET.fromstring(property_to_xml(source_node, 1).replace(f'name="{branch}"', f'name="{quest_id}"', 1).strip()))
        backup(client_path)
        atomic_write_bytes(client_path, encode_image_body(client, gms_reader()))
        stats["client"] += len(ROOT_ABYSS_QUEST_IDS)
        for server_path, server_root in server_roots:
            backup(server_path)
            xml = ET.tostring(server_root, encoding="unicode", short_empty_elements=True)
            atomic_write_text(server_path, f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n{xml}\n')
            stats["server"] += len(ROOT_ABYSS_QUEST_IDS)
    return stats


ROOT_ABYSS_DAILY_QUEST_SCRIPT = """var status = -1;
var QUEST_ID = __QUEST_ID__;
var ITEM_REQUIREMENTS = {
    30017: [4001755, 20],
    30020: [4001756, 20]
};
var INFO_PROGRESS = {
    30014: "clear",
    30015: "clear",
    30016: "clear",
    30018: "5",
    30019: "clear",
    30021: "clear"
};

function start(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
        return;
    }
    if (mode == 1) status++; else status--;
    if (status == 0) {
        qm.sendAcceptDecline("要开始执行鲁塔比斯每日任务吗？");
    } else if (status == 1) {
        qm.forceStartQuest(QUEST_ID);
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
        return;
    }
    if (mode == 1) status++; else status--;
    if (status == 0) {
        var req = ITEM_REQUIREMENTS[QUEST_ID];
        if (req != null && !qm.haveItem(req[0], req[1])) {
            qm.sendOk("还需要 #b" + req[1] + " 个 #t" + req[0] + "##k。");
            qm.dispose();
            return;
        }
        qm.sendAcceptDecline("要完成这个鲁塔比斯每日任务吗？");
    } else if (status == 1) {
        var req = ITEM_REQUIREMENTS[QUEST_ID];
        if (req != null) {
            qm.gainItem(req[0], -req[1]);
        }
        var progress = INFO_PROGRESS[QUEST_ID];
        if (progress != null) {
            qm.setQuestProgress(QUEST_ID, QUEST_ID, progress);
        }
        qm.forceCompleteQuest(QUEST_ID);
        qm.dispose();
    }
}
"""


ROOT_ABYSS_DAILY_GROUP_SCRIPT = """var status = -1;
var QUEST_ID = 30022;

function start(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
        return;
    }
    if (mode == 1) status++; else status--;
    if (status == 0) {
        qm.sendAcceptDecline("要领取今天的鲁塔比斯每日任务吗？");
    } else if (status == 1) {
        qm.forceStartQuest(QUEST_ID);
        qm.forceCompleteQuest(QUEST_ID);
        qm.dispose();
    }
}

function end(mode, type, selection) {
    qm.forceCompleteQuest(QUEST_ID);
    qm.dispose();
}
"""


def migrate_daily_quest_scripts() -> dict[str, int]:
    stats = {"scripts": 0}
    for script_root in (ROOT / "gms-server/scripts", ROOT / "gms-server/scripts-zh-CN"):
        quest_dir = script_root / "quest"
        quest_dir.mkdir(parents=True, exist_ok=True)
        for quest_id in range(30014, 30022):
            path = quest_dir / f"{quest_id}.js"
            backup(path)
            atomic_write_text(path, ROOT_ABYSS_DAILY_QUEST_SCRIPT.replace("__QUEST_ID__", str(quest_id)))
            stats["scripts"] += 1
        path = quest_dir / "30022.js"
        backup(path)
        atomic_write_text(path, ROOT_ABYSS_DAILY_GROUP_SCRIPT)
        stats["scripts"] += 1
    return stats


def fallback_map_string(map_id: int, parent=None) -> WzSubProperty:
    node = WzSubProperty(str(map_id), parent)
    node.add(WzStringProperty("streetName", "鲁塔比斯", node))
    if 105200901 <= map_id <= 105200909:
        map_name = "贝伦洞穴"
    else:
        map_name = "鲁塔比斯"
    node.add(WzStringProperty("mapName", map_name, node))
    return node


def source_map_string_node(src: WzImage, map_id: int):
    key = str(map_id)
    for category in src.root.children():
        node = category.child(key)
        if node is not None:
            return node
    return None


def migrate_map_strings() -> dict[str, int]:
    src = source_img(SRC_CLIENT / "String/Map.img")
    ids = MAP_IDS

    client_path = ROOT / "clien/Data/String/Map.img"
    dst = WzImage.from_bytes(client_path.read_bytes(), key=TARGET_KEY, name=client_path.name)
    dst.parse()
    category = dst.root.child("victoria")
    if not isinstance(category, WzSubProperty):
        category = WzSubProperty("victoria", dst.root)
        dst.root.add(category)
    for client_category in dst.root.children():
        for map_id in RETIRED_MAP_IDS:
            remove_child(client_category, str(map_id))
    for map_id in ids:
        source_node = source_map_string_node(src, map_id) or fallback_map_string(map_id)
        remove_child(category, str(map_id))
        category.add(clone_property(source_node, name=str(map_id), parent=category))
    backup(client_path)
    atomic_write_bytes(client_path, encode_image_body(dst, gms_reader()))

    server_path = ROOT / "gms-server/wz/String.wz/Map.img.xml"
    root = ET.parse(server_path).getroot()
    server_category = next((child for child in root if child.get("name") == "victoria"), None)
    if server_category is None:
        server_category = ET.Element("imgdir", {"name": "victoria"})
        root.append(server_category)
    for category_node in root:
        for child in list(category_node):
            if child.get("name") in RETIRED_MAP_ID_STRINGS:
                category_node.remove(child)
    for map_id in ids:
        for child in list(server_category):
            if child.get("name") == str(map_id):
                server_category.remove(child)
        source_node = source_map_string_node(src, map_id) or fallback_map_string(map_id)
        server_category.append(ET.fromstring(property_to_xml(source_node, 1).strip()))
    backup(server_path)
    xml = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    atomic_write_text(server_path, f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n{xml}\n')
    return {"client": len(ids), "server": len(ids)}


def find_imgdir_span_at(text: str, start: int) -> tuple[int, int]:
    depth = 0
    for match in IMGDIR_TAG_RE.finditer(text, start):
        tag = match.group(0)
        if match.start() == start:
            if tag.endswith("/>"):
                return start, match.end()
            depth = 1
            continue
        if tag.startswith("</"):
            depth -= 1
            if depth == 0:
                return start, match.end()
        elif not tag.endswith("/>"):
            depth += 1
    raise ValueError(f"unclosed imgdir at {start}")


def upsert_server_imgdir_child(path: Path, parent_name: str, child_name: str, child_xml: str) -> None:
    text = path.read_text(encoding="utf-8")
    parent_token = f'<imgdir name="{parent_name}">'
    parent_start = text.find(parent_token)
    if parent_start < 0:
        raise RuntimeError(f"{path} missing {parent_name}")
    parent_start, parent_end = find_imgdir_span_at(text, parent_start)
    parent = text[parent_start:parent_end]
    child_token = f'<imgdir name="{child_name}"'
    child_start = parent.find(child_token)
    if child_start >= 0:
        child_abs_start = parent_start + child_start
        child_abs_start, child_abs_end = find_imgdir_span_at(text, child_abs_start)
        text = text[:child_abs_start] + text[child_abs_end:]
        parent_start = text.find(parent_token)
        parent_start, parent_end = find_imgdir_span_at(text, parent_start)
    closing_start = text.rfind("</imgdir>", parent_start, parent_end)
    insert_at = text.rfind("\n", parent_start, closing_start)
    if insert_at < 0:
        raise RuntimeError(f"{path} missing closing tag for {parent_name}")
    backup(path)
    text = text[:insert_at] + "\n" + child_xml + text[insert_at:]
    text = re.sub(r"[ \t]+(?=\n)", "", text)
    atomic_write_text(path, text)


def migrate_connect_compat() -> dict[str, int]:
    client_path = ROOT / "clien/Data/Map/Obj/connect.img"
    dst = WzImage.from_bytes(client_path.read_bytes(), key=TARGET_KEY, name=client_path.name)
    dst.parse()
    rope59 = dst.get("rope/59")
    expected_canvases = {
        "0": (18, 41),
        "1": (17, 30),
        "2": (17, 39),
        "3": (26, 120),
    }
    errors = []
    if not isinstance(rope59, WzSubProperty):
        errors.append("rope/59 is missing or is not a Property")
    else:
        for name, dimensions in expected_canvases.items():
            branch = rope59.child(name)
            canvas = branch.child("0") if isinstance(branch, WzSubProperty) else None
            if not isinstance(canvas, WzCanvasProperty):
                errors.append(f"rope/59/{name}/0 is not a canvas")
                continue
            actual_dimensions = (int(canvas.width), int(canvas.height))
            actual_format = int(canvas.format) + int(canvas.format2)
            if actual_dimensions != dimensions or actual_format != 1:
                errors.append(
                    f"rope/59/{name}/0 is {actual_dimensions} format {actual_format}, "
                    f"expected {dimensions} format 1"
                )
            convex = canvas.child("rope")
            if not isinstance(convex, WzConvexProperty) or len(convex.points) != 2:
                errors.append(f"rope/59/{name}/0/rope is not a two-point convex property")
    if errors:
        details = "; ".join(errors)
        raise RuntimeError(
            "target Map/Obj/connect.img has an old-client-incompatible rope/59 "
            f"({details}); run tool/scripts/patch-client/"
            "repair_root_abyss_connect_rope59.py"
        )

    server_path = ROOT / "gms-server/wz/Map.wz/Obj/connect.img.xml"
    server_root = ET.parse(server_path).getroot()
    server_rope59 = direct_xml_child(direct_xml_child(server_root, "rope"), "59")
    server_errors = []
    if server_rope59 is None:
        server_errors.append("rope/59 is missing")
    else:
        for name, dimensions in expected_canvases.items():
            branch = direct_xml_child(server_rope59, name)
            canvas = direct_xml_child(branch, "0")
            if canvas is None or canvas.tag != "canvas":
                server_errors.append(f"rope/59/{name}/0 is not a canvas")
                continue
            actual_dimensions = (int(canvas.get("width", 0)), int(canvas.get("height", 0)))
            actual_format = int(canvas.get("format", 0))
            if actual_dimensions != dimensions or actual_format != 1:
                server_errors.append(
                    f"rope/59/{name}/0 is {actual_dimensions} format {actual_format}, "
                    f"expected {dimensions} format 1"
                )
            convex = direct_xml_child(canvas, "rope")
            vectors = list(convex) if convex is not None and convex.tag == "extended" else []
            if len(vectors) != 2 or any(vector.tag != "vector" for vector in vectors):
                server_errors.append(
                    f"rope/59/{name}/0/rope is not a two-point convex property"
                )
    if server_errors:
        raise RuntimeError(
            "server Map.wz/Obj/connect.img.xml has an old-client-incompatible rope/59 "
            f"({'; '.join(server_errors)}); run tool/scripts/patch-client/"
            "repair_root_abyss_connect_rope59.py"
        )
    return {"client": 0, "server": 0}


def migrate_effect_compat() -> dict[str, int]:
    stats = {"client": 0, "server": 0}
    src = source_img(SRC_CLIENT / "Map/Obj/effect.img")
    inline_canvas_outlinks(src.root)
    reencode_canvas_tree(src.root)
    source_gate = src.get("quest/gate/8")
    if source_gate is None:
        raise RuntimeError("source Map/Obj/effect.img missing quest/gate/8")

    client_path = ROOT / "clien/Data/Map/Obj/effect.img"
    dst = WzImage.from_bytes(client_path.read_bytes(), key=TARGET_KEY, name=client_path.name)
    dst.parse()
    gate = dst.get("quest/gate")
    if not isinstance(gate, WzSubProperty):
        raise RuntimeError("target Map/Obj/effect.img missing quest/gate")
    remove_child(gate, "8")
    gate.add(clone_property(source_gate, name="8", parent=gate))
    backup(client_path)
    atomic_write_bytes(client_path, encode_image_body(dst, gms_reader()))
    stats["client"] = 1

    server_path = ROOT / "gms-server/wz/Map.wz/Obj/effect.img.xml"
    upsert_server_imgdir_child(server_path, "gate", "8", property_to_xml(source_gate, 3))
    stats["server"] = 1
    return stats


def server_xml_path_for_client_rel(client_rel: Path) -> Path:
    if len(client_rel.parts) < 3 or client_rel.parts[0] != "Map":
        raise ValueError(f"unsupported map asset path: {client_rel}")
    return ROOT / "gms-server/wz/Map.wz" / Path(*client_rel.parts[1:]).with_suffix(".img.xml")


def repair_transparent_canvas_regressions(client_rel: Path) -> dict[str, int]:
    stats = {"client": 0, "server": 0}
    src_path = SRC_CLIENT / client_rel
    client_path = ROOT / "clien/Data" / client_rel
    server_path = server_xml_path_for_client_rel(client_rel)
    if not src_path.exists() or not client_path.exists():
        return stats

    src = source_img(src_path)
    dst = WzImage.from_bytes(client_path.read_bytes(), key=TARGET_KEY, name=client_path.name)
    dst.parse()
    source_canvases = dict(iter_canvas_properties(src.root))

    for path, target in iter_canvas_properties(dst.root):
        if not target.has_pixels() or not is_transparent_1x1(target, "GMS"):
            continue
        source = source_canvases.get(path)
        if not isinstance(source, WzCanvasProperty) or not source.has_pixels():
            continue
        image = decode_canvas(source, region=SOURCE_REGION)
        if image.size == (1, 1) or image.getbbox() is None:
            continue
        parent = target.parent
        if not isinstance(parent, WzSubProperty):
            raise RuntimeError(f"cannot replace rootabyss canvas without parent: {path}")
        parent._children[target.name] = clone_property(source, name=target.name, parent=parent)
        stats["client"] += 1

    if stats["client"]:
        backup(client_path)
        atomic_write_bytes(client_path, encode_image_body(dst, gms_reader()))
        stats["server"] += write_server_xml_from_source(src_path, server_path) == "write"
    return stats


def repair_root_abyss_visual_canvases() -> dict[str, int]:
    stats = {"client": 0, "server": 0}
    rels = [
        Path("Map/Obj/rootabyss.img"),
        Path("Map/Obj/gran_helisium.img"),
        Path("Map/Tile/rootabyssBan.img"),
        Path("Map/Tile/rootabyssBanInside.img"),
        Path("Map/Tile/rootabyssBellum.img"),
        Path("Map/Tile/rootabyssQueen.img"),
    ]
    rels.extend(Path("Map/Back") / p.name for p in sorted((SRC_CLIENT / "Map/Back").glob("rootabyss*.img")))
    for rel in rels:
        current = repair_transparent_canvas_regressions(rel)
        stats["client"] += current["client"]
        stats["server"] += current["server"]
    return stats


def map_asset_refs() -> dict[str, set[str]]:
    refs = {"Back": set(), "Obj": set(), "Tile": set()}
    for map_id in MAP_IDS:
        img = source_img(SRC_CLIENT / f"Map/Map/Map1/{map_id}.img")
        idx = 0
        while True:
            back = img.get(f"back/{idx}/bS")
            if back is None:
                break
            value = getattr(back, "value", None)
            if value:
                refs["Back"].add(str(value))
            idx += 1

        for layer in range(8):
            tile = img.get(f"{layer}/info/tS")
            if tile is not None and getattr(tile, "value", None):
                refs["Tile"].add(str(tile.value))
            obj = img.get(f"{layer}/obj")
            if obj is None or not hasattr(obj, "children"):
                continue
            for child in obj.children():
                obj_set = img.get(f"{layer}/obj/{child.name}/oS")
                if obj_set is not None and getattr(obj_set, "value", None):
                    refs["Obj"].add(str(obj_set.value))
    return refs


def migrate_maps() -> dict[str, int]:
    stats = {"client": 0, "server": 0}
    for map_id in MAP_IDS:
        src = SRC_CLIENT / f"Map/Map/Map1/{map_id}.img"
        client_dst = ROOT / f"clien/Data/Map/Map/Map1/{map_id}.img"
        server_dst = ROOT / f"gms-server/wz/Map.wz/Map/Map1/{map_id}.img.xml"
        sanitizer = lambda root, current_map_id=map_id: sanitize_root_abyss_map(root, current_map_id)
        stats["client"] += reencode_img(src, client_dst, sanitizer=sanitizer) == "write"
        stats["server"] += write_server_xml_from_source(src, server_dst, sanitizer=sanitizer) == "write"
    return stats


def migrate_sound_assets() -> dict[str, int]:
    stats = {"client": 0}
    stats["client"] += reencode_img(
        SRC_CLIENT / "Sound/Bgm29.img",
        ROOT / "clien/Data/Sound/Bgm29.img",
    ) == "write"
    return stats


def migrate_map_assets() -> dict[str, int]:
    stats = {"client": 0, "server": 0}
    for kind, names in map_asset_refs().items():
        for name in sorted(names):
            if name in {"connect", "effect"}:
                continue
            src = SRC_CLIENT / f"Map/{kind}/{name}.img"
            if not src.exists():
                raise FileNotFoundError(src)
            client_dst = ROOT / f"clien/Data/Map/{kind}/{name}.img"
            server_dst = ROOT / f"gms-server/wz/Map.wz/{kind}/{name}.img.xml"
            stats["client"] += reencode_img(src, client_dst) == "write"
            stats["server"] += write_server_xml_from_source(src, server_dst) == "write"
    return stats


def migrate_mobs_and_npcs() -> dict[str, int]:
    stats = {"client": 0, "server": 0}
    for mob_id in NORMAL_MOB_IDS:
        if (SRC_CLIENT / f"Mob/_Canvas/{mob_id}.img").exists():
            result = migrate_mob_canvas_resource(mob_id)
            stats["client"] += result == "write"
            stats["server"] += result == "write"
        elif (SRC_CLIENT / f"Mob/{mob_id}.img").exists():
            src = SRC_CLIENT / f"Mob/{mob_id}.img"
            stats["client"] += reencode_img(src, ROOT / f"clien/Data/Mob/{mob_id}.img") == "write"
            stats["server"] += write_server_xml_from_source(src, ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml") == "write"

    for npc_id in NPC_IDS:
        src = SRC_CLIENT / f"Npc/{npc_id}.img"
        if not src.exists():
            src = SRC_CLIENT / f"Npc/_Canvas/{npc_id}.img"
        stats["client"] += reencode_img(src, ROOT / f"clien/Data/Npc/{npc_id}.img") == "write"
        stats["server"] += write_server_xml_from_source(src, ROOT / f"gms-server/wz/Npc.wz/{npc_id}.img.xml") == "write"

    if NORMAL_MOB_IDS:
        upsert_client_string("Mob", NORMAL_MOB_IDS)
        upsert_server_string_xml("Mob", NORMAL_MOB_IDS)
    npc_string_ids = [*NPC_IDS, *STRING_ONLY_NPC_IDS]
    upsert_client_string("Npc", npc_string_ids)
    upsert_server_string_xml("Npc", npc_string_ids)
    return stats


def migrate_root_abyss_boss_mobs() -> dict[str, int]:
    stats = {"client": 0, "server": 0, "skipped": 0}
    available_ids = []
    for mob_id in ADVANCED_BOSS_MOB_IDS:
        if (SRC_CLIENT / f"Mob/{mob_id}.img").exists() or (SRC_CLIENT / f"Mob/_Canvas/{mob_id}.img").exists():
            available_ids.append(mob_id)
    for mob_id in available_ids:
        if (SRC_CLIENT / f"Mob/_Canvas/{mob_id}.img").exists():
            result = migrate_mob_canvas_resource(mob_id)
            stats["client"] += result == "write"
            stats["server"] += result == "write"
            stats["skipped"] += result.startswith("skip")
            continue
        src = SRC_CLIENT / f"Mob/{mob_id}.img"
        sanitizer = lambda root, current_mob_id=mob_id: sanitize_root_abyss_boss_mob(root, current_mob_id)
        server_sanitizer = lambda root, current_mob_id=mob_id: (
            sanitize_root_abyss_boss_mob(root, current_mob_id),
            set_root_abyss_server_boss_hp(root, current_mob_id),
        )
        stats["client"] += reencode_img(src, ROOT / f"clien/Data/Mob/{mob_id}.img", sanitizer=sanitizer) == "write"
        stats["server"] += write_server_xml_from_source(src, ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml", sanitizer=server_sanitizer) == "write"
    stats["skipped"] += len(ADVANCED_BOSS_MOB_IDS) - len(available_ids)

    upsert_client_string("Mob", available_ids)
    upsert_server_string_xml("Mob", available_ids)
    return stats


def migrate_reactors() -> dict[str, int]:
    stats = {"client": 0, "server": 0}
    for reactor_id in REACTOR_IDS:
        template_id = REACTOR_TEMPLATE[reactor_id]
        src = SRC_CLIENT / f"Reactor/{template_id}.img"
        client_dst = ROOT / f"clien/Data/Reactor/{reactor_id}.img"
        server_dst = ROOT / f"gms-server/wz/Reactor.wz/{reactor_id}.img.xml"
        stats["client"] += reencode_img(src, client_dst) == "write"
        stats["server"] += write_server_xml_from_source(src, server_dst, root_name=f"{reactor_id}.img") == "write"
    return stats


def main() -> int:
    if not SRC_CLIENT.exists():
        raise SystemExit(f"missing source client: {SRC_CLIENT}")
    print(f"Root Abyss maps: {len(MAP_IDS)}")
    print(f"Backups: {BACKUP_ROOT}")
    print("maps", migrate_maps())
    print("map strings", migrate_map_strings())
    print("sound assets", migrate_sound_assets())
    print("connect compat", migrate_connect_compat())
    print("effect compat", migrate_effect_compat())
    print("map assets", migrate_map_assets())
    print("visual canvas repair", repair_root_abyss_visual_canvases())
    print("mobs/npcs", migrate_mobs_and_npcs())
    print("root abyss mobskills", patch_root_abyss_mobskills())
    print("boss mobs", migrate_root_abyss_boss_mobs())
    print("etc item resources", migrate_etc_item_resources())
    print("quest data", migrate_quest_data())
    print("daily quest scripts", migrate_daily_quest_scripts())
    print("reactors", migrate_reactors())
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
