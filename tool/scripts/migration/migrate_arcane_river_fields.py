#!/usr/bin/env python3
"""Migrate stable Arcane River towns and training fields from TMS.

The migration is intentionally whitelist based.  It materializes modern canvas
links, converts every imported bitmap to GMS ARGB4444, prunes unsupported map
features, and writes the client plus both server map trees together.
"""

from __future__ import annotations

import io
import shutil
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from xml.sax.saxutils import quoteattr

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
PACKS = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory/Data/Packs")
MS_PROBE = Path(
    "/Users/lizixian/Documents/mxd/TMS/black_mage_report_tools/"
    "ms_probe/bin/Debug/net8.0/MSProbe.dll"
)
BACKUP_ROOT = Path("/private/tmp/arcane-river-fields-backup")
MOB_CACHE = Path("/private/tmp/arcane-river-mob-cache")
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

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
from wzpy.canvas import _decompress, decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import _read_sound_payload, encode_image_body  # noqa: E402


BMS_KEY = WzKey.for_region("BMS")
GMS_KEY = WzKey.for_region("GMS")
MAX_CANVAS_EDGE = 2048

MAP_IDS = tuple(
    int(value)
    for value in """
450001000,450001003,450001005,450001010,450001011,450001012,450001013,450001014,450001015,450001016,450001100,450001110,450001111,450001112,450001113,450001114,450001200,450001210,450001211,450001212,450001213,450001214,450001215,450001216,450001217,450001218,450001260,450001261,450001262,
450002000,450002001,450002002,450002003,450002004,450002005,450002006,450002007,450002008,450002009,450002010,450002011,450002012,450002013,450002014,450002015,450002016,450002017,450002018,450002019,450002020,450002300,450002301,450002302,
450003000,450003100,450003200,450003210,450003220,450003300,450003310,450003320,450003330,450003340,450003350,450003360,450003400,450003410,450003420,450003430,450003440,450003450,450003460,450003500,450003510,450003520,450003530,450003540,450003560,
450005000,450005100,450005110,450005120,450005121,450005130,450005131,450005200,450005210,450005220,450005221,450005222,450005230,450005240,450005241,450005242,450005300,450005400,450005410,450005411,450005412,450005420,450005430,450005431,450005432,450005440,450005500,450005510,450005520,450005530,450005550,
450006000,450006010,450006020,450006030,450006040,450006110,450006120,450006130,450006150,450006160,450006200,450006210,450006220,450006230,450006240,450006300,450006310,450006320,450006400,450006410,450006420,450006430,450006440,
450007000,450007010,450007020,450007030,450007040,450007050,450007060,450007070,450007100,450007110,450007120,450007130,450007140,450007150,450007160,450007200,450007210,450007220,450007230
""".replace("\n", "").split(",")
    if value
)
MAP_ID_SET = set(MAP_IDS)

TOWN_BY_PREFIX = {
    "450001": 450001000,
    "450002": 450002000,
    "450003": 450003000,
    "450005": 450005000,
    "450006": 450006130,
    "450007": 450007040,
}
MAP_MARKS = {"Road of Vanishing", "ChewChew", "Lacheln", "Arcana", "Morass", "esfera"}
MAP_ONLY_AB_TESTS: set[int] = set()
LEGACY_MEDIA_DISABLED_MAPS = {450001000}
LEGACY_CONNECT_FIRST_MAPS = set(MAP_IDS)
LEGACY_SWIM_MAPS = {450002011}
LEGACY_ZERO_FIELD_LIMIT_MAPS = {450006130}
LIFE_UNSUPPORTED_BY_MAP = {
    450006130: {"forcedZPage", "forcedZMass"},
}
FOOTHOLD_UNSUPPORTED_BY_MAP = {
    450006130: {"piece"},
}
LEGACY_ASSET_CHILD_RENAMES = {
    ("Obj", "morass", "castle_Outside/stone/7/0/foothold"): {"5": "4"},
}
PINNED_CLIENT_MAP_SHA256 = {
    450001000: "ac6127f16ca8c56bac8db7448ced677c24ca557cbc22bb4ea861104d679d373e",
}
PRESERVED_ARRIVAL_PORTALS = {
    450001100: {"PV00"},
    450001210: {"PS00"},
    450001215: {"PS00"},
    450002010: {"pt_out00"},
    450002015: {"pt_BackToArc1"},
    450003000: {"in01", "in02", "in03"},
    450003500: {"top00"},
    450003510: {"top00"},
    450003520: {"top00"},
    450005000: {"out10"},
    450005130: {"east00"},
    450005400: {"pt00"},
    450006040: {"east00"},
    450006240: {"east00", "center00"},
    450006400: {"east00"},
    450007030: {"pt01"},
}

REMOVED_NPCS = {
    9000123, 9000124, 9000131, 9000132, 9010100, 9010106, 9010109,
    9010112, 9010113, 9063173, 9063313, 9063366, 9063620, 9063870,
    9070104, 9070105, 9201594, 9270343, 9310649, 9330072,
    9401686, 9401687, 9401704, 9401705, 9401706, 9401707, 9401708,
}

MAP_ROOTS = {
    "info", "back", "life", "reactor", "foothold",
    "ladderRope", "miniMap", "portal", *(str(index) for index in range(8)),
}
MAP_INFO_UNSUPPORTED = {
    "AmbientBGM", "AmbientBGMv", "ReviveCurFieldOfNoTransfer",
    "ReviveCurFieldOfNoTransferNotDamaged", "ReviveCurFieldOfNoTransferPoint",
    "barrierArc", "barrierAut", "consumeItemCoolTime", "fieldLimit2",
    "fieldScript", "fieldType", "largeSplit", "limitUpgradeItem",
    "limitUseShop", "lvLimit", "mode", "noChair", "noHekatonEffect",
    "onFirstUserEnter", "onUserEnter", "partyStandAlone", "qrLimit",
    "quarterView", "remoteEffect", "reviveCurField", "specialSound",
    "standAlone", "noMapCmd", "MRLeft", "MRTop", "MRRight", "MRBottom",
    "bgmSub", "footStepSound", "mirror_Bottom",
    "AFKmob", "HobbangKing", "MR", "bonusStageNoChangeBack",
    "individualHuntField", "individualHuntFieldServerType", "noBackOverlapped",
    "qrLimitState", "qrLimitState2", "ratemob", "towerChairEnable", "zeroSideOnly",
}
OBJ_UNSUPPORTED = {
    "SN0", "SN_count", "dynamic", "move", "name", "piece", "spineAni",
    "questex", "tags", "timeScale",
    "cantThrough", "fadeName", "fadeType", "groupName", "quest", "sideType",
}
BACK_UNSUPPORTED = {"backTags", "w", "wx", "wy", "spineAni", "flowX", "flowY"}
LIFE_UNSUPPORTED = {"hold", "nofoothold"}
PORTAL_UNSUPPORTED = {
    "delay", "hideTooltip", "onlyOnce", "hRange", "horizontalImpact", "vRange",
    "shownAtMinimap",
}
MOB_INFO_UNSUPPORTED = {
    "attack", "bodyDisease", "bodyDiseaseLevel", "category", "chaseEffect",
    "default", "defaultHP", "defaultMP", "delAtomOnDead", "explosiveReward",
    "finalmaxHP", "firstAttackRange", "ignoreFieldOut", "ignoreMovable",
    "ignoreMoveImpact", "isRemoteRange", "linkMob", "maxHPb", "mobZone",
    "passive", "publicReward", "showNotRemoteDam", "skill", "stalking",
    "trans", "useReaction", "revive",
    "mobJobCategory", "opacityLayer",
}
NPC_INFO_UNSUPPORTED = {"condition1", "miniMapType", "sayFlip"}
NPC_ROOT_UNSUPPORTED_PREFIX = "condition"
OLD_MOB_FIELDS = {
    "PADamage": 0,
    "PDDamage": 0,
    "MADamage": 0,
    "MDDamage": 0,
    "level": 1,
}


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


def backup(path: Path) -> None:
    if not path.exists():
        return
    relative = path.relative_to(ROOT)
    target = BACKUP_ROOT / relative
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def load_image(path: Path, key: WzKey) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=key, name=path.name)
    image.parse()
    return image


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), GMS_KEY)


def child_value(node, name: str):
    child = node.child(name) if node is not None else None
    return getattr(child, "value", None)


def remove_child(node, name: str) -> None:
    if node is not None:
        node._children.pop(name, None)


def set_int(node: WzSubProperty, name: str, value: int) -> None:
    remove_child(node, name)
    node.add(WzIntProperty(name, int(value), node))


def set_string(node: WzSubProperty, name: str, value: str) -> None:
    remove_child(node, name)
    node.add(WzStringProperty(name, str(value), node))


def legacy_rope_pieces(y1: int, y2: int) -> list[tuple[str, int]]:
    pieces = [("0", y1 - 1)]
    cursor = y1 + 24
    bottom_start = y2 - 32
    while bottom_start - cursor >= 120:
        pieces.append(("3", cursor + 60))
        cursor += 120
    while cursor < bottom_start:
        pieces.append(("1", cursor + 15))
        cursor += 30
    pieces.append(("2", y2 - 17))
    return pieces


def legacy_ladder_pieces(y1: int, y2: int) -> list[tuple[str, int]]:
    pieces = [("0", y1 - 6)]
    middle_y = y1 + 29
    while middle_y < y2 - 5:
        pieces.append(("1", middle_y))
        middle_y += 48
    pieces.append(("3", y2 - 22))
    return pieces


def next_numeric_child_name(node: WzSubProperty) -> int:
    return max((int(child.name) for child in node.children() if child.name.isdigit()), default=-1) + 1


def add_legacy_connect_object(
    objects: WzSubProperty,
    index: int,
    kind: str,
    piece: str,
    x: int,
    y: int,
    z: int = 3,
    f: int = 0,
    z_mass: int = 0,
) -> int:
    entry = WzSubProperty(str(index), objects)
    objects.add(entry)
    set_string(entry, "oS", "connect")
    set_string(entry, "l0", kind)
    set_string(entry, "l1", "0")
    set_string(entry, "l2", piece)
    set_int(entry, "x", x)
    set_int(entry, "y", y)
    set_int(entry, "z", z)
    set_int(entry, "f", f)
    set_int(entry, "zM", z_mass)
    return index + 1


def downgrade_connect_nodes(root: WzSubProperty) -> dict[str, int]:
    ladder_rope = root.child("ladderRope")
    collisions = list(ladder_rope.children()) if isinstance(ladder_rope, WzSubProperty) else []
    collision_data = [
        (
            "ladder" if int(child_value(entry, "l") or 0) else "rope",
            int(child_value(entry, "x")),
            int(child_value(entry, "y1")),
            int(child_value(entry, "y2")),
        )
        for entry in collisions
    ]
    decorative: list[tuple[str, str, str, int, int, int, int, int]] = []
    removed = 0
    for layer in [child for child in root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        for entry in list(objects.children()):
            if child_value(entry, "oS") != "connect":
                continue
            kind = str(child_value(entry, "l0"))
            x, y = int(child_value(entry, "x")), int(child_value(entry, "y"))
            matched = any(
                collision_kind == kind
                and abs(collision_x - x) <= 5
                and y1 - 160 <= y <= y2 + 160
                for collision_kind, collision_x, y1, y2 in collision_data
            )
            if not matched:
                original_piece = str(child_value(entry, "l2") or "1")
                max_piece = 4
                piece = original_piece if original_piece.isdigit() and int(original_piece) <= max_piece else "1"
                decorative.append(
                    (
                        layer.name,
                        kind if kind in {"rope", "ladder"} else "rope",
                        piece,
                        x,
                        y,
                        int(child_value(entry, "z") or 3),
                        int(child_value(entry, "f") or 0),
                        int(child_value(entry, "zM") or 0),
                    )
                )
            remove_child(objects, entry.name)
            removed += 1

    generated = 0
    for collision in collisions:
        remove_child(collision, "piece")
        kind = "ladder" if int(child_value(collision, "l") or 0) else "rope"
        x = int(child_value(collision, "x"))
        y1, y2 = int(child_value(collision, "y1")), int(child_value(collision, "y2"))
        page = int(child_value(collision, "page"))
        layer = root.child(str(page))
        objects = layer.child("obj") if isinstance(layer, WzSubProperty) else None
        if not isinstance(objects, WzSubProperty):
            raise RuntimeError(f"missing object layer {page} for ladderRope/{collision.name}")
        index = next_numeric_child_name(objects)
        pieces = legacy_ladder_pieces(y1, y2) if kind == "ladder" else legacy_rope_pieces(y1, y2)
        for piece, y in pieces:
            index = add_legacy_connect_object(objects, index, kind, piece, x, y)
            generated += 1

    for page, kind, piece, x, y, z, f, z_mass in decorative:
        layer = root.child(page)
        objects = layer.child("obj") if isinstance(layer, WzSubProperty) else None
        if not isinstance(objects, WzSubProperty):
            raise RuntimeError(f"missing decorative connect object layer {page}")
        add_legacy_connect_object(
            objects, next_numeric_child_name(objects), kind, piece, x, y, z, f, z_mass
        )
        generated += 1
    return {
        "removed": removed,
        "generated": generated,
        "collisions": len(collisions),
        "decorative": len(decorative),
    }


def normalize_connect_object_order(root: WzSubProperty) -> int:
    """Keep legacy connect pieces before ordinary objects with dense indices."""
    changed = 0
    for layer in [child for child in root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        entries = list(objects.children())
        connect = [entry for entry in entries if child_value(entry, "oS") == "connect"]
        if not connect:
            continue
        ordered = connect + [entry for entry in entries if child_value(entry, "oS") != "connect"]
        expected_names = [str(index) for index in range(len(ordered))]
        if ordered == entries and [entry.name for entry in entries] == expected_names:
            continue
        objects._children.clear()
        for index, entry in enumerate(ordered):
            entry.name = str(index)
            objects.add(entry)
        changed += 1
    return changed


def downgrade_portal_types(root: WzSubProperty) -> int:
    portal = root.child("portal")
    if not isinstance(portal, WzSubProperty):
        return 0
    changed = 0
    for entry in portal.children():
        if int(child_value(entry, "pt") or 0) == 10:
            set_int(entry, "pt", 3)
            changed += 1
    return changed


def walk(node, path: str = ""):
    yield node, path
    if hasattr(node, "children"):
        for child in node.children():
            child_path = f"{path}/{child.name}" if path else child.name
            yield from walk(child, child_path)


def decode_source_canvas(canvas: WzCanvasProperty) -> Image.Image:
    if int(canvas.format) + int(canvas.format2) != 4098:
        return decode_canvas(canvas, region="BMS").convert("RGBA")
    raw = _decompress(canvas, BMS_KEY)
    width, height = int(canvas.width), int(canvas.height)
    linear_size = ((width + 3) // 4) * ((height + 3) // 4) * 16
    if len(raw) < linear_size:
        raise RuntimeError(f"short BC7 payload: {len(raw)} < {linear_size}")
    header = struct.pack(
        "<I6I11I", 124, 0x00081007, height, width, linear_size, 0, 0, *([0] * 11)
    )
    pixel_format = struct.pack("<II4s5I", 32, 4, b"DX10", 0, 0, 0, 0, 0)
    caps = struct.pack("<5I", 0x1000, 0, 0, 0, 0)
    dx10 = struct.pack("<5I", 98, 3, 0, 1, 0)
    with Image.open(io.BytesIO(b"DDS " + header + pixel_format + caps + dx10 + raw[:linear_size])) as decoded:
        return decoded.convert("RGBA")


class CanvasMaterializer:
    def __init__(self) -> None:
        self.images: dict[Path, WzImage] = {}
        self.decoded: dict[tuple[Path, str], Image.Image] = {}
        self.canvases = 0
        self.links = 0
        self.resized = 0

    def source_image(self, path: Path) -> WzImage:
        path = path.resolve()
        if path not in self.images:
            if not path.exists():
                raise FileNotFoundError(f"linked IMG does not exist: {path}")
            self.images[path] = load_image(path, BMS_KEY)
        return self.images[path]

    def external_target(self, value: str) -> tuple[Path, str]:
        normalized = value.replace("\\", "/").removeprefix("Data/").lstrip("/")
        marker = ".img/"
        if marker not in normalized:
            raise RuntimeError(f"invalid _outlink: {value}")
        file_part, property_path = normalized.split(marker, 1)
        return SOURCE / f"{file_part}.img", property_path

    def resolve_canvas(
        self, canvas: WzCanvasProperty, image: WzImage, image_path: Path, seen: set[tuple[Path, str]]
    ) -> tuple[WzCanvasProperty, WzImage, Path, str]:
        outlink = canvas.child("_outlink")
        inlink = canvas.child("_inlink")
        if outlink is not None:
            target_path, property_path = self.external_target(str(outlink.value))
            target_image = self.source_image(target_path)
            target = target_image.root.get(property_path)
            self.links += 1
        elif inlink is not None:
            target_path, property_path, target_image = image_path, str(inlink.value).lstrip("/"), image
            target = image.root.get(property_path)
            self.links += 1
        elif canvas.has_pixels():
            return canvas, image, image_path, ""
        else:
            raise RuntimeError(f"canvas without pixels or link in {image_path}: {canvas.name}")
        identity = (target_path.resolve(), property_path)
        if identity in seen:
            raise RuntimeError(f"cyclic canvas link: {target_path}:{property_path}")
        if not isinstance(target, WzCanvasProperty):
            raise RuntimeError(f"unresolved canvas link: {target_path}:{property_path}")
        if target.has_pixels():
            return target, target_image, target_path, property_path
        return self.resolve_canvas(target, target_image, target_path, seen | {identity})

    def materialize(
        self, source: WzCanvasProperty, parent, image: WzImage, image_path: Path
    ) -> WzCanvasProperty:
        pixel_source, pixel_image, pixel_path, pixel_property = self.resolve_canvas(
            source, image, image_path, set()
        )
        cache_key = (pixel_path.resolve(), pixel_property or f"@{id(pixel_source)}")
        decoded = self.decoded.get(cache_key)
        if decoded is None:
            decoded = decode_source_canvas(pixel_source)
            self.decoded[cache_key] = decoded
        bitmap = decoded.copy()
        scale = min(1.0, MAX_CANVAS_EDGE / max(bitmap.width, bitmap.height))
        if scale < 1.0:
            size = (max(1, round(bitmap.width * scale)), max(1, round(bitmap.height * scale)))
            bitmap = bitmap.resize(size, Image.Resampling.LANCZOS)
            self.resized += 1
        output = WzCanvasProperty(source.name, parent)
        output.width, output.height = bitmap.size
        output.format, output.format2 = 1, 0
        output._png_data = encode_canvas_payload(
            bitmap, 1, bitmap.width, bitmap.height, key=GMS_KEY, listwz=False, zlib_level=6
        )
        output._png_length = len(output._png_data)
        output._png_offset = 0

        metadata: dict[str, object] = {}
        for candidate in (pixel_source, source):
            for child in candidate.children():
                if child.name not in {"_outlink", "_inlink"}:
                    metadata[child.name] = child
        for child in metadata.values():
            output.add(clone_property(child, output, image, image_path, self))
        if scale < 1.0:
            for node, _ in walk(output):
                if isinstance(node, WzVectorProperty):
                    node.x = round(int(node.x) * scale)
                    node.y = round(int(node.y) * scale)
        self.canvases += 1
        return output


def clone_property(source, parent, image: WzImage, image_path: Path, materializer: CanvasMaterializer, name=None):
    output_name = source.name if name is None else name
    if isinstance(source, WzCanvasProperty):
        old_name = source.name
        source.name = output_name
        try:
            return materializer.materialize(source, parent, image, image_path)
        finally:
            source.name = old_name
    if isinstance(source, WzSubProperty):
        output = WzSubProperty(output_name, parent)
        for child in source.children():
            output.add(clone_property(child, output, image, image_path, materializer))
        return output
    if isinstance(source, WzVectorProperty):
        return WzVectorProperty(output_name, int(source.x), int(source.y), parent)
    if isinstance(source, WzStringProperty):
        return WzStringProperty(output_name, str(source.value), parent)
    if isinstance(source, WzIntProperty):
        return WzIntProperty(output_name, int(source.value), parent)
    if isinstance(source, WzShortProperty):
        return WzShortProperty(output_name, int(source.value), parent)
    if isinstance(source, WzLongProperty):
        return WzLongProperty(output_name, int(source.value), parent)
    if isinstance(source, WzFloatProperty):
        return WzFloatProperty(output_name, float(source.value), parent)
    if isinstance(source, WzDoubleProperty):
        return WzDoubleProperty(output_name, float(source.value), parent)
    if isinstance(source, WzUolProperty):
        return WzUolProperty(output_name, str(source.value), parent)
    if isinstance(source, WzNullProperty):
        return WzNullProperty(output_name, parent)
    if isinstance(source, WzConvexProperty):
        output = WzConvexProperty(output_name, parent)
        output.points = [
            clone_property(point, output, image, image_path, materializer) for point in source.points
        ]
        return output
    if isinstance(source, WzSoundProperty):
        output = WzSoundProperty(output_name, parent)
        output.length_ms = source.length_ms
        output.header = source.header
        output._data_offset = source._data_offset
        output._data_length = source._data_length
        output._wz_image = source._wz_image
        output._data = source._data
        return output
    raise TypeError(f"unsupported WZ property: {type(source).__name__}")


def clone_image(source_path: Path, sanitizer=None) -> tuple[WzImage, CanvasMaterializer]:
    image = load_image(source_path, BMS_KEY)
    if sanitizer is not None:
        sanitizer(image.root)
    materializer = CanvasMaterializer()
    root = WzSubProperty(image.root.name)
    for child in image.root.children():
        root.add(clone_property(child, root, image, source_path, materializer))
    image._root = root
    image._parsed = True
    return image, materializer


def property_to_xml(prop, indent: int = 1) -> str:
    pad = "  " * indent
    name = f"name={quoteattr(prop.name)}"
    if isinstance(prop, WzNullProperty):
        return f"{pad}<null {name}/>"
    if isinstance(prop, WzVectorProperty):
        return f'{pad}<vector {name} x="{int(prop.x)}" y="{int(prop.y)}"/>'
    if isinstance(prop, WzCanvasProperty):
        attrs = f'{name} width="{int(prop.width)}" height="{int(prop.height)}" format="1"'
        body = "\n".join(property_to_xml(child, indent + 1) for child in prop.children())
        return f"{pad}<canvas {attrs}>{chr(10) + body + chr(10) + pad if body else ''}</canvas>"
    if isinstance(prop, WzSoundProperty):
        return f'{pad}<sound {name} length_ms="{int(prop.length_ms)}" bytes="{int(prop.value)}"/>'
    if isinstance(prop, WzConvexProperty):
        body = "\n".join(property_to_xml(point, indent + 1) for point in prop.points)
        return f"{pad}<extended {name}>\n{body}\n{pad}</extended>"
    if isinstance(prop, WzUolProperty):
        return f"{pad}<uol {name} value={quoteattr(str(prop.value))}/>"
    if isinstance(prop, WzSubProperty):
        body = "\n".join(property_to_xml(child, indent + 1) for child in prop.children())
        return f"{pad}<imgdir {name}>{chr(10) + body + chr(10) + pad if body else ''}</imgdir>"
    tags = {
        WzShortProperty: "short", WzIntProperty: "int", WzLongProperty: "long",
        WzFloatProperty: "float", WzDoubleProperty: "double", WzStringProperty: "string",
    }
    tag = next((value for kind, value in tags.items() if isinstance(prop, kind)), "string")
    return f"{pad}<{tag} {name} value={quoteattr(str(prop.value))}/>"


def image_to_xml(image: WzImage, name: str) -> str:
    body = "\n".join(property_to_xml(child) for child in image.root.children())
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<imgdir name="{name}">\n{body}\n</imgdir>\n'
    )


def town_for(map_id: int) -> int:
    return TOWN_BY_PREFIX[str(map_id)[:6]]


def sanitize_map(root: WzSubProperty, map_id: int) -> None:
    for child in list(root.children()):
        if child.name not in MAP_ROOTS:
            remove_child(root, child.name)
    info = root.child("info")
    if isinstance(info, WzSubProperty):
        for name in MAP_INFO_UNSUPPORTED:
            remove_child(info, name)
        if map_id in LEGACY_SWIM_MAPS:
            set_int(info, "swim", 1)
        if map_id in LEGACY_ZERO_FIELD_LIMIT_MAPS:
            set_int(info, "fieldLimit", 0)
        if map_id in MAP_ONLY_AB_TESTS or map_id in LEGACY_MEDIA_DISABLED_MAPS:
            remove_child(info, "bgm")
            remove_child(info, "mapMark")
        for name in ("returnMap", "forcedReturn"):
            value = child_value(info, name)
            if isinstance(value, int) and value != 999999999 and value not in MAP_ID_SET:
                set_int(info, name, town_for(map_id))

    life = root.child("life")
    if isinstance(life, WzSubProperty):
        if map_id in MAP_ONLY_AB_TESTS:
            life._children.clear()
        for entry in list(life.children()):
            if child_value(entry, "type") == "n":
                npc_id = int(child_value(entry, "id"))
                regional = str(npc_id).startswith("300")
                installed = (ROOT / f"clien/Data/Npc/{npc_id}.img").exists()
                hidden = int(child_value(entry, "hide") or 0) != 0
                if hidden or npc_id in REMOVED_NPCS or (not regional and not installed):
                    remove_child(life, entry.name)
                    continue
            for name in LIFE_UNSUPPORTED | LIFE_UNSUPPORTED_BY_MAP.get(map_id, set()):
                remove_child(entry, name)

    foothold = root.child("foothold")
    for node, _ in walk(foothold) if foothold is not None else ():
        if not isinstance(node, WzSubProperty):
            continue
        for name in FOOTHOLD_UNSUPPORTED_BY_MAP.get(map_id, set()):
            remove_child(node, name)

    for layer in [child for child in root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if isinstance(objects, WzSubProperty):
            for entry in list(objects.children()):
                values = " ".join(str(getattr(child, "value", "")) for child in entry.children())
                modern_object = any(entry.child(name) is not None for name in ("questex", "tags", "timeScale"))
                if "2025MysticBloom" in values or entry.child("spineAni") is not None or modern_object:
                    remove_child(objects, entry.name)
                    continue
                if map_id != 450001000 and child_value(entry, "oS") == "extinction":
                    set_string(entry, "oS", "extinctionLegacy")
                for name in OBJ_UNSUPPORTED:
                    remove_child(entry, name)

    downgrade_connect_nodes(root)
    if map_id in LEGACY_CONNECT_FIRST_MAPS:
        normalize_connect_object_order(root)

    back = root.child("back")
    if isinstance(back, WzSubProperty):
        for entry in list(back.children()):
            values = " ".join(str(getattr(child, "value", "")) for child in entry.children())
            if "2025MysticBloom" in values or int(child_value(entry, "ani") or 0) == 2:
                remove_child(back, entry.name)
                continue
            for name in BACK_UNSUPPORTED:
                remove_child(entry, name)

    portal = root.child("portal")
    if not isinstance(portal, WzSubProperty):
        return
    downgrade_portal_types(root)
    for entry in list(portal.children()):
        portal_name = str(child_value(entry, "pn") or "")
        target = child_value(entry, "tm")
        script = str(child_value(entry, "script") or "")
        remove = False
        override = None
        if portal_name in PRESERVED_ARRIVAL_PORTALS.get(map_id, set()):
            set_int(entry, "pt", 0)
            set_int(entry, "tm", 999999999)
            set_string(entry, "tn", "")
        elif map_id == 450001005 and portal_name == "PS00":
            override = (450001100, "PV00")
        elif map_id == 450001100 and portal_name == "PS00":
            override = (450001200, "PV01")
        elif map_id == 450002000 and portal_name in {"out02", "out05"}:
            remove = True
        elif map_id == 450001262 and portal_name == "PV00":
            remove = True
        elif isinstance(target, int) and target != 999999999 and target not in MAP_ID_SET:
            remove = True
        elif script and target == 999999999:
            remove = True
        if remove:
            remove_child(portal, entry.name)
            continue
        if override:
            set_int(entry, "tm", override[0])
            set_string(entry, "tn", override[1])
        remove_child(entry, "script")
        for name in PORTAL_UNSUPPORTED:
            remove_child(entry, name)


def sanitize_mob(root: WzSubProperty) -> None:
    info = root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{root.name}: missing mob info")
    for name in MOB_INFO_UNSUPPORTED:
        remove_child(info, name)
    for name, value in OLD_MOB_FIELDS.items():
        if info.child(name) is None:
            set_int(info, name, value)
    # Modern Arcane River EVA values (up to 930) make the legacy client miss
    # even at 999 accuracy. Keep the imported mobs on the old-client scale.
    set_int(info, "eva", 200)
    max_hp = info.child("maxHP")
    if max_hp is not None and int(max_hp.value) > 2_147_483_647:
        set_int(info, "maxHP", 2_147_483_647)


def sanitize_npc(root: WzSubProperty) -> None:
    info = root.child("info")
    if isinstance(info, WzSubProperty):
        for name in NPC_INFO_UNSUPPORTED:
            remove_child(info, name)
    # The old client supports condition actions only together with the matching
    # info/condition* selector.  Once that modern selector is removed, leaving
    # the root condition* trees creates dead UOL action graphs with a different
    # shape from the legacy NPC schema.
    for child in list(root.children()):
        suffix = child.name.removeprefix(NPC_ROOT_UNSUPPORTED_PREFIX)
        if child.name.startswith(NPC_ROOT_UNSUPPORTED_PREFIX) and suffix.isdigit():
            remove_child(root, child.name)


def collect_dependencies(image: WzImage) -> dict[str, object]:
    dependencies: dict[str, object] = {
        "assets": defaultdict(set), "mobs": set(), "npcs": set(), "bgms": set(), "marks": set()
    }
    bgm = child_value(image.root.child("info"), "bgm")
    mark = child_value(image.root.child("info"), "mapMark")
    if bgm:
        dependencies["bgms"].add(str(bgm))
    if mark:
        dependencies["marks"].add(str(mark))
    life = image.root.child("life")
    if isinstance(life, WzSubProperty):
        for entry in life.children():
            kind, value = child_value(entry, "type"), child_value(entry, "id")
            if kind == "m" and value is not None:
                dependencies["mobs"].add(int(value))
            elif kind == "n" and value is not None:
                dependencies["npcs"].add(int(value))
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


def merge_dependency_sets(target: dict[str, object], source: dict[str, object]) -> None:
    for name in ("mobs", "npcs", "bgms", "marks"):
        target[name].update(source[name])
    for key, branches in source["assets"].items():
        target["assets"][key].update(branches)


def write_client_image(path: Path, image: WzImage) -> None:
    backup(path)
    atomic_write_bytes(path, encode_image_body(image, gms_reader()))


def write_server_image(path: Path, image: WzImage, name: str) -> None:
    backup(path)
    atomic_write_text(path, image_to_xml(image, name))


def migrate_maps() -> tuple[dict[str, object], dict[str, int]]:
    dependencies = {
        "assets": defaultdict(set), "mobs": set(), "npcs": set(), "bgms": set(), "marks": set()
    }
    totals = {"maps": 0, "canvases": 0, "links": 0, "resized": 0}
    for map_id in MAP_IDS:
        source = SOURCE / f"Map/Map/Map4/{map_id}.img"
        image, materializer = clone_image(source, lambda root, value=map_id: sanitize_map(root, value))
        merge_dependency_sets(dependencies, collect_dependencies(image))
        client = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        write_client_image(client, image)
        trees = ["wz"]
        if (ROOT / "gms-server/wz-zh-CN/Map.wz").exists():
            trees.append("wz-zh-CN")
        for tree in trees:
            server = ROOT / f"gms-server/{tree}/Map.wz/Map/Map4/{map_id}.img.xml"
            write_server_image(server, image, f"{map_id}.img")
        totals["maps"] += 1
        totals["canvases"] += materializer.canvases
        totals["links"] += materializer.links
        totals["resized"] += materializer.resized
    return dependencies, totals


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


def normalize_legacy_asset_structure(image: WzImage, kind: str, name: str) -> int:
    changed = 0
    for (asset_kind, asset_name, path), renames in LEGACY_ASSET_CHILD_RENAMES.items():
        if (kind, name) != (asset_kind, asset_name):
            continue
        node = image.root.get(path)
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"missing compatibility asset node: {kind}/{name}.img/{path}")
        for old_name, new_name in renames.items():
            old = node.child(old_name)
            new = node.child(new_name)
            if old is None and new is not None:
                continue
            if old is None or new is not None:
                raise RuntimeError(
                    f"unexpected compatibility asset children: {kind}/{name}.img/{path}"
                )
            node._children.pop(old_name)
            old.name = new_name
            node.add(old)
            changed += 1
    return changed


def legacy_asset_structure_errors(image: WzImage, kind: str, name: str) -> list[str]:
    errors = []
    for asset_kind, asset_name, path in LEGACY_ASSET_CHILD_RENAMES:
        if (kind, name) != (asset_kind, asset_name):
            continue
        node = image.root.get(path)
        names = [child.name for child in node.children()] if isinstance(node, WzSubProperty) else []
        expected = [str(index) for index in range(len(names))]
        if names != expected:
            errors.append(f"{kind}/{name}.img/{path}: {names}, expected {expected}")
    return errors


def merge_asset(kind: str, name: str, branches: set[str]) -> tuple[int, int, int]:
    source_path = SOURCE / f"Map/{kind}/{name}.img"
    target_path = ROOT / f"clien/Data/Map/{kind}/{name}.img"
    if kind == "Obj" and name == "connect":
        target = load_image(target_path, GMS_KEY) if target_path.exists() else None
        missing = [branch for branch in branches if target is None or target.root.get(branch) is None]
        if missing:
            raise FileNotFoundError(f"missing legacy Obj/connect.img branches: {missing}")
        return 0, 0, 0
    if not source_path.exists():
        target = load_image(target_path, GMS_KEY) if target_path.exists() else None
        missing = [branch for branch in branches if target is None or target.root.get(branch) is None]
        if missing:
            raise FileNotFoundError(f"missing {kind}/{name}.img branches: {missing}")
        return 0, 0, 0
    source = load_image(source_path, BMS_KEY)
    materializer = CanvasMaterializer()
    if target_path.exists():
        target = load_image(target_path, GMS_KEY)
    else:
        target = load_image(source_path, BMS_KEY)
        target._root = WzSubProperty(source.root.name)
        target._parsed = True
    for branch in sorted(branches):
        source_node = source.root.get(branch)
        if source_node is None:
            if target.root.get(branch) is None:
                raise RuntimeError(f"source asset missing {kind}/{name}.img/{branch}")
            continue
        parent_path, _, leaf = branch.rpartition("/")
        parent = ensure_path(target.root, parent_path)
        remove_child(parent, leaf)
        parent.add(clone_property(source_node, parent, source, source_path, materializer, leaf))
    normalize_legacy_asset_structure(target, kind, name)
    write_client_image(target_path, target)
    return materializer.canvases, materializer.links, materializer.resized


def migrate_map_assets(dependencies: dict[str, object]) -> dict[str, int]:
    totals = {"files": 0, "branches": 0, "canvases": 0, "links": 0, "resized": 0}
    jobs = [(kind, name, branches) for (kind, name), branches in sorted(dependencies["assets"].items())]
    with ProcessPoolExecutor(max_workers=4) as executor:
        results = executor.map(merge_asset_job, jobs)
        for (_, _, branches), (canvases, links, resized) in zip(jobs, results, strict=True):
            totals["files"] += 1
            totals["branches"] += len(branches)
            totals["canvases"] += canvases
            totals["links"] += links
            totals["resized"] += resized
    return totals


def merge_asset_job(job: tuple[str, str, set[str]]) -> tuple[int, int, int]:
    kind, name, branches = job
    return merge_asset(kind, name, branches)


def merge_map_marks(marks: set[str]) -> int:
    source_path = SOURCE / "Map/MapHelper.img"
    target_path = ROOT / "clien/Data/Map/MapHelper.img"
    source = load_image(source_path, BMS_KEY)
    target = load_image(target_path, GMS_KEY)
    materializer = CanvasMaterializer()
    mark_root = ensure_path(target.root, "mark")
    for mark in sorted(marks):
        source_node = source.root.get(f"mark/{mark}")
        if source_node is None:
            raise RuntimeError(f"MapHelper missing mark/{mark}")
        remove_child(mark_root, mark)
        mark_root.add(clone_property(source_node, mark_root, source, source_path, materializer, mark))
    write_client_image(target_path, target)
    return materializer.canvases


def extract_mob(mob_id: int) -> Path:
    destination = MOB_CACHE / str(mob_id)
    output = destination / f"Mob_{mob_id:07d}.img"
    if output.exists():
        return output
    destination.mkdir(parents=True, exist_ok=True)
    errors = []
    for pack in sorted(PACKS.glob("Mob_*.ms")):
        result = subprocess.run(
            ["dotnet", str(MS_PROBE), str(pack), str(destination), f"Mob/{mob_id:07d}.img"],
            capture_output=True, text=True, check=False,
        )
        if output.exists():
            return output
        errors.append(f"{pack.name}: {result.stderr.strip() or result.stdout.strip()}")
    raise RuntimeError(f"unable to extract mob {mob_id}: {' | '.join(errors)}")


def migrate_one_mob(mob_id: int) -> tuple[int, int, int]:
    source = extract_mob(mob_id)
    image, materializer = clone_image(source, sanitize_mob)
    write_client_image(ROOT / f"clien/Data/Mob/{mob_id:07d}.img", image)
    write_server_image(
        ROOT / f"gms-server/wz/Mob.wz/{mob_id:07d}.img.xml", image, f"{mob_id:07d}.img"
    )
    return materializer.canvases, materializer.links, materializer.resized


def migrate_mobs(mob_ids: set[int]) -> dict[str, int]:
    totals = {"mobs": 0, "canvases": 0, "links": 0, "resized": 0}
    with ProcessPoolExecutor(max_workers=4) as executor:
        for canvases, links, resized in executor.map(migrate_one_mob, sorted(mob_ids)):
            totals["mobs"] += 1
            totals["canvases"] += canvases
            totals["links"] += links
            totals["resized"] += resized
    return totals


def migrate_one_npc(npc_id: int) -> tuple[int, int, int]:
    source = SOURCE / f"Npc/{npc_id:07d}.img"
    image, materializer = clone_image(source, sanitize_npc)
    write_client_image(ROOT / f"clien/Data/Npc/{npc_id:07d}.img", image)
    write_server_image(
        ROOT / f"gms-server/wz/Npc.wz/{npc_id:07d}.img.xml", image, f"{npc_id:07d}.img"
    )
    return materializer.canvases, materializer.links, materializer.resized


def migrate_npcs(npc_ids: set[int]) -> dict[str, int]:
    totals = {"npcs": 0, "canvases": 0, "links": 0, "resized": 0}
    regional = sorted(npc_id for npc_id in npc_ids if str(npc_id).startswith("300"))
    with ProcessPoolExecutor(max_workers=4) as executor:
        for canvases, links, resized in executor.map(migrate_one_npc, regional):
            totals["npcs"] += 1
            totals["canvases"] += canvases
            totals["links"] += links
            totals["resized"] += resized
    return totals


def transcode_legacy_mp3(source: WzSoundProperty) -> bytes:
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "mp3", "-i", "pipe:0", "-map_metadata", "-1",
            "-codec:a", "libmp3lame", "-ar", "22050", "-ac", "2",
            "-b:a", "64k", "-write_xing", "0", "-id3v2_version", "0",
            "-write_id3v1", "0", "-f", "mp3", "pipe:1",
        ],
        input=_read_sound_payload(source), capture_output=True, check=False,
    )
    if result.returncode != 0 or not is_legacy_mp3_payload(result.stdout):
        raise RuntimeError(
            f"legacy MP3 transcode failed for {source.name}: "
            f"{result.stderr.decode('utf-8', 'replace').strip()}"
        )
    return result.stdout


def is_legacy_mp3_payload(payload: bytes) -> bool:
    """Return whether payload matches the imported 64 kbps legacy MP3 template."""
    if len(payload) < 4:
        return False
    header = int.from_bytes(payload[:4], "big")
    sync = (header >> 21) & 0x7FF
    version = (header >> 19) & 0x3
    layer = (header >> 17) & 0x3
    bitrate_index = (header >> 12) & 0xF
    sample_rate_index = (header >> 10) & 0x3
    channel_mode = (header >> 6) & 0x3
    return (
        sync == 0x7FF
        and version == 0x2  # MPEG-2
        and layer == 0x1  # Layer III
        and bitrate_index == 0x8  # 64 kbps for MPEG-2 Layer III
        and sample_rate_index == 0x0  # 22.05 kHz for MPEG-2
        and channel_mode != 0x3  # stereo/joint stereo/dual channel, not mono
    )


def clone_sound(source: WzSoundProperty, parent, legacy_header: bytes) -> WzSoundProperty:
    payload = transcode_legacy_mp3(source)
    output = WzSoundProperty(source.name, parent)
    output.length_ms = source.length_ms
    output.header = legacy_header
    output._data_offset = 0
    output._data_length = len(payload)
    output._wz_image = None
    output._data = payload
    return output


def migrate_bgms(bgms: set[str]) -> dict[str, int]:
    legacy_image = load_image(ROOT / "clien/Data/Sound/Bgm12.img", GMS_KEY)
    legacy_sound = legacy_image.root.get("AquaCave")
    if not isinstance(legacy_sound, WzSoundProperty):
        raise RuntimeError("missing legacy Bgm12/AquaCave 64 kbps sound template")
    legacy_header = bytes(legacy_sound.header)
    by_pack: dict[str, set[str]] = defaultdict(set)
    for reference in bgms:
        pack, name = reference.split("/", 1)
        by_pack[pack].add(name)
    totals = {"packs": 0, "tracks": 0}
    for pack, names in sorted(by_pack.items()):
        source_path = SOURCE / f"Sound/{pack}.img"
        target_path = ROOT / f"clien/Data/Sound/{pack}.img"
        source = load_image(source_path, BMS_KEY)
        if target_path.exists():
            target = load_image(target_path, GMS_KEY)
        else:
            target = load_image(source_path, BMS_KEY)
            target._root = WzSubProperty(source.root.name)
            target._parsed = True
        for name in sorted(names):
            sound = source.root.get(name)
            if not isinstance(sound, WzSoundProperty):
                raise RuntimeError(f"missing sound {pack}/{name}")
            remove_child(target.root, name)
            target.root.add(clone_sound(sound, target.root, legacy_header))
            totals["tracks"] += 1
        write_client_image(target_path, target)
        totals["packs"] += 1
    return totals


def source_map_string(image: WzImage, map_id: int):
    for category in image.root.children():
        node = category.child(str(map_id))
        if node is not None:
            return node
    return None


def upsert_client_strings(img_name: str, ids: set[int] | tuple[int, ...], category_name=None) -> int:
    source_path = SOURCE / f"String/{img_name}.img"
    target_path = ROOT / f"clien/Data/String/{img_name}.img"
    source = load_image(source_path, BMS_KEY)
    target = load_image(target_path, GMS_KEY)
    materializer = CanvasMaterializer()
    parent = ensure_path(target.root, category_name) if category_name else target.root
    for item_id in sorted(ids):
        node = source_map_string(source, item_id) if img_name == "Map" else source.root.get(str(item_id))
        if node is None:
            raise RuntimeError(f"String/{img_name}.img missing {item_id}")
        remove_child(parent, str(item_id))
        parent.add(clone_property(node, parent, source, source_path, materializer, str(item_id)))
    write_client_image(target_path, target)
    return len(ids)


def upsert_server_strings(
    tree: str, img_name: str, ids: set[int] | tuple[int, ...], category_name=None
) -> int:
    source_path = SOURCE / f"String/{img_name}.img"
    source = load_image(source_path, BMS_KEY)
    target_path = ROOT / f"gms-server/{tree}/String.wz/{img_name}.img.xml"
    root = ET.parse(target_path).getroot()
    parent = root
    if category_name:
        parent = next((child for child in root if child.get("name") == category_name), None)
        if parent is None:
            parent = ET.Element("imgdir", {"name": category_name})
            root.append(parent)
    for item_id in sorted(ids):
        node = source_map_string(source, item_id) if img_name == "Map" else source.root.get(str(item_id))
        if node is None:
            raise RuntimeError(f"String/{img_name}.img missing {item_id}")
        for old in list(parent):
            if old.get("name") == str(item_id):
                parent.remove(old)
        parent.append(ET.fromstring(property_to_xml(node, 0)))
    backup(target_path)
    xml = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    atomic_write_text(
        target_path, f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n{xml}\n'
    )
    return len(ids)


def migrate_strings(dependencies: dict[str, object]) -> dict[str, int]:
    regional_npcs = {value for value in dependencies["npcs"] if str(value).startswith("300")}
    totals = {
        "client_maps": upsert_client_strings("Map", MAP_IDS, "grandis"),
        "client_mobs": upsert_client_strings("Mob", dependencies["mobs"]),
        "client_npcs": upsert_client_strings("Npc", regional_npcs),
    }
    for tree in ("wz", "wz-zh-CN"):
        totals[f"{tree}_maps"] = upsert_server_strings(tree, "Map", MAP_IDS, "grandis")
        totals[f"{tree}_mobs"] = upsert_server_strings(tree, "Mob", dependencies["mobs"])
    totals["wz_npcs"] = upsert_server_strings("wz", "Npc", regional_npcs)
    return totals


def main() -> int:
    if not SOURCE.exists() or not MS_PROBE.exists():
        raise SystemExit("TMS IMG source or MSProbe is missing")
    print(f"Arcane River maps: {len(MAP_IDS)}")
    print(f"Backups: {BACKUP_ROOT}")
    dependencies, map_stats = migrate_maps()
    print("maps", map_stats)
    print(
        "dependencies",
        {name: len(dependencies[name]) for name in ("assets", "mobs", "npcs", "bgms", "marks")},
    )
    print("map assets", migrate_map_assets(dependencies))
    print("map marks", merge_map_marks(dependencies["marks"]))
    print("npcs", migrate_npcs(dependencies["npcs"]))
    print("mobs", migrate_mobs(dependencies["mobs"]))
    print("bgms", migrate_bgms(dependencies["bgms"]))
    print("strings", migrate_strings(dependencies))
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
