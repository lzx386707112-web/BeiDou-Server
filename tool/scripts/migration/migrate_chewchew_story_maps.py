#!/usr/bin/env python3
"""Migrate ChewChew story maps 450002021, 450002023, 450002025 from TMS.

These are quest/story fields that were not included in the original Arcane River
migration. They share the ChewChew theme and need the same old-client sanitization.

The maps, NPCs, and the new YumYum asset are standalone artifacts. Existing
shared Map and String IMG files are changed only by raw child-record insertion.
"""

from __future__ import annotations

import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))
sys.path.insert(0, str(ROOT / "tool/scripts/patch-client"))

from wzpy import (
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
from wzpy.canvas import decode_canvas, encode_canvas_payload
from wzpy.reader import WzBinaryReader
from wzpy.writer import encode_image_body

import migrate_arcane_river_fields as arcane
from migrate_karing_later_stages import (  # noqa: E402
    encode_record,
    insert_raw_record,
    insert_xml_record,
    locate_records,
)
from repair_arcane_river_8641002_attack_gap import find_node_span  # noqa: E402

BMS_KEY = WzKey.for_region("BMS")
GMS_KEY = WzKey.for_region("GMS")
MAX_CANVAS_EDGE = 2048

MAP_IDS = (450002021, 450002023, 450002025)
YUMYUM_ENTRY_MAP_ID = 450015020
MAP_ID_SET = arcane.MAP_ID_SET | set(MAP_IDS) | {YUMYUM_ENTRY_MAP_ID}
NPC_IDS = (3003151, 3003153, 3003154, 3003155, 3003156, 3003165, 3003166, 3004726)
SHARED_ASSET_BRANCHES = {
    ("Obj", "chewchewIsland"): ("MainField/muto/8", "MainField/muto/9"),
}
SHARED_ASSET_REPLACEMENTS = {
    ("Back", "chewchewIsland"): ("back/51", "back/52"),
}
NEW_ASSET_BRANCHES = {
    ("Obj", "YumYum"): ("field1/obj/9",),
}
LEGACY_PORTAL_OVERRIDES = {
    450002023: {"out00": (2, 450002021, "sp")},
    450002025: {"out00": (2, YUMYUM_ENTRY_MAP_ID, "west00")},
}

# ---- 来自 migrate_arcane_river_fields.py 的完整清理规则 ----

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

REMOVED_NPCS = {
    9000123, 9000124, 9000131, 9000132, 9010100, 9010106, 9010109,
    9010112, 9010113, 9063173, 9063313, 9063366, 9063620, 9063870,
    9070104, 9070105, 9201594, 9270343, 9310649, 9330072,
    9401686, 9401687, 9401704, 9401705, 9401706, 9401707, 9401708,
}


def load_image(path: Path, key: WzKey) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=key, name=path.name)
    image.parse()
    return image


def child_value(node, name: str):
    child = node.child(name) if node is not None else None
    return getattr(child, "value", None)


def remove_child(node, name: str) -> None:
    if node is not None:
        node._children.pop(name, None)


def walk(node, path: str = ""):
    yield node, path
    if hasattr(node, "children"):
        for child in node.children():
            child_path = f"{path}/{child.name}" if path else child.name
            yield from walk(child, child_path)


def decode_source_canvas(canvas: WzCanvasProperty) -> "Image.Image":
    from PIL import Image
    import io
    import struct
    from wzpy.canvas import _decompress

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
        self.decoded: dict[tuple[Path, str], "Image.Image"] = {}
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
            bitmap = bitmap.resize(size, 1)  # Image.Resampling.LANCZOS = 1
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


def sanitize_map(root: WzSubProperty, map_id: int) -> None:
    """Apply the proven Arcane River projection for the three story fields."""
    for child in list(root.children()):
        if child.name not in MAP_ROOTS:
            remove_child(root, child.name)

    info = root.child("info")
    if isinstance(info, WzSubProperty):
        for name in MAP_INFO_UNSUPPORTED:
            remove_child(info, name)

    life = root.child("life")
    if isinstance(life, WzSubProperty):
        for entry in list(life.children()):
            if child_value(entry, "type") == "n":
                npc_id = int(child_value(entry, "id"))
                regional = str(npc_id).startswith("300")
                installed = (ROOT / f"clien/Data/Npc/{npc_id}.img").exists()
                hidden = int(child_value(entry, "hide") or 0) != 0
                if hidden or npc_id in REMOVED_NPCS or (not regional and not installed):
                    remove_child(life, entry.name)
                    continue
            for name in LIFE_UNSUPPORTED:
                remove_child(entry, name)

    for layer in [child for child in root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        for entry in list(objects.children()):
            values = " ".join(str(getattr(child, "value", "")) for child in entry.children())
            modern = any(entry.child(name) is not None for name in ("questex", "tags", "timeScale"))
            if "2025MysticBloom" in values or entry.child("spineAni") is not None or modern:
                remove_child(objects, entry.name)
                continue
            for name in OBJ_UNSUPPORTED:
                remove_child(entry, name)

    arcane.downgrade_connect_nodes(root)
    arcane.normalize_connect_object_order(root)

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
    if isinstance(portal, WzSubProperty):
        arcane.downgrade_portal_types(root)
        for entry in list(portal.children()):
            portal_name = str(child_value(entry, "pn") or "")
            override = LEGACY_PORTAL_OVERRIDES.get(map_id, {}).get(portal_name)
            if override is not None:
                portal_type, target_map, target_name = override
                arcane.set_int(entry, "pt", portal_type)
                arcane.set_int(entry, "tm", target_map)
                arcane.set_string(entry, "tn", target_name)
            target = child_value(entry, "tm")
            script = str(child_value(entry, "script") or "")
            if (
                isinstance(target, int)
                and target != 999999999
                and target not in MAP_ID_SET
            ) or (script and target == 999999999):
                remove_child(portal, entry.name)
                continue
            remove_child(entry, "script")
            for name in PORTAL_UNSUPPORTED:
                remove_child(entry, name)


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


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(None, GMS_KEY)


def write_client_image(path: Path, image: WzImage) -> None:
    """Write client IMG binary format."""
    arcane.atomic_write_bytes(path, encode_image_body(image, gms_reader()))


def write_server_image(path: Path, image: WzImage, name: str) -> None:
    """Write server XML format."""
    arcane.atomic_write_text(path, image_to_xml(image, name))


def migrate_maps() -> dict[str, int]:
    totals = {"maps": 0, "canvases": 0, "links": 0, "resized": 0}
    for map_id in MAP_IDS:
        source = SOURCE / f"Map/Map/Map4/{map_id}.img"
        if not source.exists():
            print(f"  WARNING: {source} not found, skipping")
            continue
        image, materializer = clone_image(
            source, lambda root, value=map_id: sanitize_map(root, value)
        )

        client = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        write_client_image(client, image)
        print(f"  Client: {client} ({client.stat().st_size:,} bytes)")

        trees = ["wz"]
        if (ROOT / "gms-server/wz-zh-CN/Map.wz").exists():
            trees.append("wz-zh-CN")
        for tree in trees:
            server = ROOT / f"gms-server/{tree}/Map.wz/Map/Map4/{map_id}.img.xml"
            write_server_image(server, image, f"{map_id}.img")
            print(f"  Server: {server} ({server.stat().st_size:,} bytes)")

        totals["maps"] += 1
        totals["canvases"] += materializer.canvases
        totals["links"] += materializer.links
        totals["resized"] += materializer.resized
    return totals


def ensure_path(root: WzSubProperty, path: str) -> WzSubProperty:
    current = root
    for name in [part for part in path.split("/") if part]:
        child = current.child(name)
        if not isinstance(child, WzSubProperty):
            child = WzSubProperty(name, current)
            current.add(child)
        current = child
    return current


def cloned_source_node(kind: str, name: str, branch: str):
    source_path = SOURCE / f"Map/{kind}/{name}.img"
    source = load_image(source_path, BMS_KEY)
    source_node = source.root.get(branch)
    if source_node is None:
        raise RuntimeError(f"missing source Map/{kind}/{name}.img/{branch}")
    materializer = CanvasMaterializer()
    parent_path, _, leaf = branch.rpartition("/")
    parent = WzSubProperty(parent_path.rsplit("/", 1)[-1] or source.root.name)
    node = clone_property(source_node, parent, source, source_path, materializer, leaf)
    parent.add(node)
    return node, materializer


def replace_raw_record(path: Path, parent_path: tuple[str, ...], node) -> bool:
    original = path.read_bytes()
    image = WzImage.from_bytes(original, key=GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{path}: malformed baseline {image.parse_warnings}")
    size_offsets, _, _, names, spans, _ = locate_records(image, original, parent_path)
    if node.name not in names:
        raise RuntimeError(f"{path}: missing replacement record {'/'.join((*parent_path, node.name))}")
    index = names.index(node.name)
    start, end = spans[index]
    replacement = encode_record(node, image)
    if original[start:end] == replacement:
        return False
    raw_before = {
        name: original[record_start:record_end]
        for name, (record_start, record_end) in zip(names, spans, strict=True)
        if name != node.name
    }
    updated = bytearray(original[:start] + replacement + original[end:])
    delta = len(replacement) - (end - start)
    for size_offset in size_offsets:
        old_size = struct.unpack_from("<I", original, size_offset)[0]
        struct.pack_into("<I", updated, size_offset, old_size + delta)

    result = bytes(updated)
    verified = WzImage.from_bytes(result, key=GMS_KEY, name=path.name)
    verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise RuntimeError(f"{path}: malformed replacement {verified.parse_warnings}")
    _, _, _, after_names, after_spans, _ = locate_records(
        verified, result, parent_path
    )
    if after_names != names:
        raise RuntimeError(f"{path}: child order changed during replacement")
    raw_after = {
        name: result[record_start:record_end]
        for name, (record_start, record_end) in zip(after_names, after_spans, strict=True)
    }
    for name, record in raw_before.items():
        if raw_after[name] != record:
            raise RuntimeError(f"{path}: unchanged record changed: {name}")
    if raw_after[node.name] != replacement:
        raise RuntimeError(f"{path}: replacement record mismatch: {node.name}")
    arcane.atomic_write_bytes(path, result)
    return True


def replace_xml_record(path: Path, parent_path: tuple[str, ...], node) -> bool:
    original = path.read_text(encoding="utf-8")
    parent_start, parent_end = 0, len(original)
    for segment in parent_path:
        parent_start, parent_end = find_node_span(
            original, "imgdir", segment, parent_start, parent_end
        )
    tag = "canvas" if isinstance(node, WzCanvasProperty) else "imgdir"
    start, end = find_node_span(original, tag, node.name, parent_start, parent_end)
    line_start = original.rfind("\n", 0, start) + 1
    prefix = original[line_start:start]
    if prefix.strip():
        line_start = start
        prefix = ""
    replacement = property_to_xml(node, len(prefix) // 2)
    if original[line_start:end] == replacement:
        return False
    updated = original[:line_start] + replacement + original[end:]
    ET.fromstring(updated)
    updated_parent_start, updated_parent_end = 0, len(updated)
    for segment in parent_path:
        updated_parent_start, updated_parent_end = find_node_span(
            updated, "imgdir", segment, updated_parent_start, updated_parent_end
        )
    find_node_span(updated, tag, node.name, updated_parent_start, updated_parent_end)
    arcane.atomic_write_text(path, updated)
    return True


def migrate_shared_assets() -> dict[str, int]:
    totals = {
        "client_insertions": 0,
        "server_insertions": 0,
        "client_replacements": 0,
        "server_replacements": 0,
        "canvases": 0,
    }
    for (kind, name), branches in SHARED_ASSET_BRANCHES.items():
        client = ROOT / f"clien/Data/Map/{kind}/{name}.img"
        server = ROOT / f"gms-server/wz/Map.wz/{kind}/{name}.img.xml"
        for branch in branches:
            node, materializer = cloned_source_node(kind, name, branch)
            parent_path, _, _ = branch.rpartition("/")
            parent = tuple(part for part in parent_path.split("/") if part)
            totals["client_insertions"] += int(insert_raw_record(client, parent, node))
            totals["server_insertions"] += int(insert_xml_record(server, parent, node))
            totals["canvases"] += materializer.canvases
    for (kind, name), branches in SHARED_ASSET_REPLACEMENTS.items():
        client = ROOT / f"clien/Data/Map/{kind}/{name}.img"
        server = ROOT / f"gms-server/wz/Map.wz/{kind}/{name}.img.xml"
        for branch in branches:
            node, materializer = cloned_source_node(kind, name, branch)
            parent_path, _, _ = branch.rpartition("/")
            parent = tuple(part for part in parent_path.split("/") if part)
            totals["client_replacements"] += int(replace_raw_record(client, parent, node))
            totals["server_replacements"] += int(replace_xml_record(server, parent, node))
            totals["canvases"] += materializer.canvases
    return totals


def migrate_new_assets() -> dict[str, int]:
    totals = {"files": 0, "branches": 0, "canvases": 0}
    for (kind, name), branches in NEW_ASSET_BRANCHES.items():
        source_path = SOURCE / f"Map/{kind}/{name}.img"
        source = load_image(source_path, BMS_KEY)
        materializer = CanvasMaterializer()
        root = WzSubProperty(source.root.name)
        for branch in branches:
            source_node = source.root.get(branch)
            if source_node is None:
                raise RuntimeError(f"missing source Map/{kind}/{name}.img/{branch}")
            parent_path, _, leaf = branch.rpartition("/")
            parent = ensure_path(root, parent_path)
            parent.add(clone_property(source_node, parent, source, source_path, materializer, leaf))
        source._root = root
        source._parsed = True
        write_client_image(ROOT / f"clien/Data/Map/{kind}/{name}.img", source)
        write_server_image(
            ROOT / f"gms-server/wz/Map.wz/{kind}/{name}.img.xml",
            source,
            f"{name}.img",
        )
        totals["files"] += 1
        totals["branches"] += len(branches)
        totals["canvases"] += materializer.canvases
    return totals


def migrate_npcs() -> dict[str, int]:
    totals = {"npcs": 0, "canvases": 0, "links": 0, "resized": 0}
    for npc_id in NPC_IDS:
        source = SOURCE / f"Npc/{npc_id:07d}.img"
        image, materializer = clone_image(source, arcane.sanitize_npc)
        write_client_image(ROOT / f"clien/Data/Npc/{npc_id:07d}.img", image)
        write_server_image(
            ROOT / f"gms-server/wz/Npc.wz/{npc_id:07d}.img.xml",
            image,
            f"{npc_id:07d}.img",
        )
        totals["npcs"] += 1
        totals["canvases"] += materializer.canvases
        totals["links"] += materializer.links
        totals["resized"] += materializer.resized
    return totals


def source_map_string(image: WzImage, map_id: int):
    for category in image.root.children():
        node = category.child(str(map_id))
        if node is not None:
            return node
    return None


def clone_string_node(source: WzImage, source_path: Path, node, name: str):
    parent = WzSubProperty("strings")
    cloned = clone_property(node, parent, source, source_path, CanvasMaterializer(), name)
    parent.add(cloned)
    return cloned


def migrate_strings() -> dict[str, int]:
    totals = {"client_map": 0, "client_npc": 0, "server_map": 0, "server_npc": 0}
    map_source_path = SOURCE / "String/Map.img"
    map_source = load_image(map_source_path, BMS_KEY)
    for map_id in MAP_IDS:
        source_node = source_map_string(map_source, map_id)
        if source_node is None:
            raise RuntimeError(f"missing source String/Map.img/{map_id}")
        node = clone_string_node(map_source, map_source_path, source_node, str(map_id))
        totals["client_map"] += int(
            insert_raw_record(ROOT / "clien/Data/String/Map.img", ("grandis",), node)
        )
        for tree in ("wz", "wz-zh-CN"):
            path = ROOT / f"gms-server/{tree}/String.wz/Map.img.xml"
            if path.exists():
                totals["server_map"] += int(insert_xml_record(path, ("grandis",), node))

    npc_source_path = SOURCE / "String/Npc.img"
    npc_source = load_image(npc_source_path, BMS_KEY)
    for npc_id in NPC_IDS:
        source_node = npc_source.root.get(str(npc_id))
        if source_node is None:
            raise RuntimeError(f"missing source String/Npc.img/{npc_id}")
        node = clone_string_node(npc_source, npc_source_path, source_node, str(npc_id))
        totals["client_npc"] += int(
            insert_raw_record(ROOT / "clien/Data/String/Npc.img", (), node)
        )
        totals["server_npc"] += int(
            insert_xml_record(ROOT / "gms-server/wz/String.wz/Npc.img.xml", (), node)
        )
    return totals


def main() -> int:
    print(f"Migrating ChewChew story maps: {MAP_IDS}")
    print("maps", migrate_maps())
    print("shared assets", migrate_shared_assets())
    print("new assets", migrate_new_assets())
    print("npcs", migrate_npcs())
    print("strings", migrate_strings())
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
