#!/usr/bin/env python3
"""Migrate selected TMS Destiny weapons and Eternal armor into BeiDou."""

from __future__ import annotations

import argparse
import io
import re
import shutil
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import quoteattr


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.canvas import _decompress, decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.properties import (  # noqa: E402
    WzCanvasProperty,
    WzConvexProperty,
    WzDoubleProperty,
    WzFloatProperty,
    WzIntProperty,
    WzLongProperty,
    WzNullProperty,
    WzShortProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_compressed_int, encode_image_body  # noqa: E402


TMS_DATA = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
SOURCE_STRING = TMS_DATA / "String/Eqp.img"
CLIENT_CHARACTER = ROOT / "clien/Data/Character"
SERVER_CHARACTER = ROOT / "gms-server/wz/Character.wz"
CLIENT_STRING = ROOT / "clien/Data/String/Eqp.img"
SERVER_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Eqp.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Eqp.img.xml",
)

BMS_KEY = WzKey.for_region("BMS")
GMS_KEY = WzKey.for_region("GMS")
TARGET_LEVEL = 200
LIMIT_BREAK = 2_147_483_647
EXPECTED_ITEMS = 51
EXPECTED_CANVASES = 3560
EXPECTED_OUTLINKS = 3544
DESTINY_WEAPON_DESCRIPTION = "天命武器，可参与对应职业的永恒套装效果。"
ETERNAL_ARMOR_DESCRIPTION = "永恒套装装备，穿戴对应职业装备可激活套装属性。"


@dataclass(frozen=True)
class ItemSpec:
    item_id: int
    category: str
    req_job: int
    tuc: int
    weapon: bool = False
    target_level: int = TARGET_LEVEL

    @property
    def file_name(self) -> str:
        return f"{self.item_id:08d}.img"

    @property
    def source_path(self) -> Path:
        return TMS_DATA / "Character" / self.category / self.file_name

    @property
    def client_path(self) -> Path:
        return CLIENT_CHARACTER / self.category / self.file_name

    @property
    def server_path(self) -> Path:
        return SERVER_CHARACTER / self.category / f"{self.file_name}.xml"


WEAPON_SPECS = tuple(
    ItemSpec(item_id, "Weapon", req_job, 9, True)
    for item_id, req_job in (
        (1302376, 1),
        (1312227, 1),
        (1322283, 1),
        (1332305, 8),
        (1372252, 2),
        (1382289, 2),
        (1402295, 1),
        (1412198, 1),
        (1422210, 1),
        (1432242, 1),
        (1442301, 1),
        (1452287, 4),
        (1462270, 4),
        (1472290, 8),
        (1482247, 16),
        (1492261, 16),
    )
)

JOB_ORDER = (1, 2, 4, 8, 16)
ARMOR_SPECS = tuple(
    ItemSpec(first_id + offset, category, req_job, tuc)
    for category, first_id, tuc in (
        ("Cap", 1005980, 12),
        ("Cape", 1103433, 8),
        ("Coat", 1042433, 8),
        ("Glove", 1082760, 8),
        ("Pants", 1062285, 8),
        ("Shoes", 1073629, 8),
        ("Accessory", 1152212, 2),
    )
    for offset, req_job in enumerate(JOB_ORDER)
)
ITEM_SPECS = WEAPON_SPECS + ARMOR_SPECS
SHOULDER_SPECS = tuple(spec for spec in ARMOR_SPECS if spec.category == "Accessory")

REMOVE_INFO_FIELDS = frozenset(
    {
        "bdR",
        "bossReward",
        "charmEXP",
        "equipTradeBlock",
        "exceptToadsHammer",
        "exceptTransmission",
        "exceptUpgrade",
        "exItem",
        "imdR",
        "jokerToSetItem",
        "noDrop",
        "notSale",
        "only",
        "onlyEquip",
        "onlyUpgrade",
        "onlyUpgradeThousand",
        "setItemID",
        "tradeAvailable",
        "tradeBlock",
        "undecomposable",
        "unsyntesizable",
    }
)


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), GMS_KEY)


def load_image(path: Path, key: WzKey) -> WzImage:
    if not path.is_file():
        raise RuntimeError(f"missing IMG: {path}")
    image = WzImage.from_bytes(path.read_bytes(), key=key, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"parse warning in {path}: {image.parse_warnings}")
    return image


def walk(node):
    yield node
    if hasattr(node, "children"):
        for child in node.children():
            yield from walk(child)


class CanvasMaterializer:
    def __init__(self) -> None:
        self.images: dict[str, WzImage] = {}
        self.payloads: dict[str, tuple[int, int, bytes]] = {}
        self.canvases = 0
        self.outlinks = 0
        self.converted = 0

    def linked_canvas(self, value: str) -> WzCanvasProperty:
        normalized = value.replace("\\", "/")
        marker = "/_Canvas/"
        if marker not in normalized:
            raise RuntimeError(f"unsupported outlink: {value}")
        before, after = normalized.split(marker, 1)
        file_name, separator, property_path = after.partition("/")
        if not separator or not file_name.endswith(".img"):
            raise RuntimeError(f"invalid outlink: {value}")
        relative = f"{before}/_Canvas/{file_name}"
        image = self.images.get(relative)
        if image is None:
            image = load_image(TMS_DATA / relative, BMS_KEY)
            self.images[relative] = image
        canvas = image.root.get(property_path)
        if not isinstance(canvas, WzCanvasProperty) or not canvas.has_pixels():
            raise RuntimeError(f"unresolved outlink: {value}")
        return canvas

    def argb4444(self, canvas: WzCanvasProperty) -> tuple[int, int, bytes]:
        width = int(canvas.width)
        height = int(canvas.height)
        if width <= 0 or height <= 0 or not canvas.has_pixels():
            raise RuntimeError(f"invalid Canvas {canvas.name}: {width}x{height}")
        if int(canvas.format) + int(canvas.format2) == 1:
            payload = zlib.compress(_decompress(canvas, BMS_KEY), 9)
        else:
            image = decode_canvas(canvas, region="BMS").convert("RGBA")
            payload = encode_canvas_payload(
                image,
                1,
                width,
                height,
                key=GMS_KEY,
                listwz=False,
                zlib_level=9,
            )
            self.converted += 1
        return width, height, payload

    def clone_canvas(self, source: WzCanvasProperty, parent) -> WzCanvasProperty:
        self.canvases += 1
        outlink = source.child("_outlink")
        if isinstance(outlink, WzStringProperty):
            value = str(outlink.value)
            materialized = self.payloads.get(value)
            if materialized is None:
                materialized = self.argb4444(self.linked_canvas(value))
                self.payloads[value] = materialized
            self.outlinks += 1
        else:
            materialized = self.argb4444(source)

        width, height, payload = materialized
        output = WzCanvasProperty(source.name, parent)
        output.width = width
        output.height = height
        output.format = 1
        output.format2 = 0
        output._png_data = payload
        output._png_length = len(payload)
        output._png_offset = 0
        for child in source.children():
            if child.name != "_outlink":
                output.add(clone_property(child, output, self))
        return output


def clone_property(source, parent, materializer: CanvasMaterializer):
    if isinstance(source, WzCanvasProperty):
        return materializer.clone_canvas(source, parent)
    if isinstance(source, WzSubProperty):
        output = WzSubProperty(source.name, parent)
        for child in source.children():
            if child.name != "particle":
                output.add(clone_property(child, output, materializer))
        return output
    if isinstance(source, WzVectorProperty):
        return WzVectorProperty(source.name, int(source.x), int(source.y), parent)
    if isinstance(source, WzStringProperty):
        return WzStringProperty(source.name, str(source.value), parent)
    if isinstance(source, WzIntProperty):
        return WzIntProperty(source.name, int(source.value), parent)
    if isinstance(source, WzShortProperty):
        return WzShortProperty(source.name, int(source.value), parent)
    if isinstance(source, WzLongProperty):
        return WzLongProperty(source.name, int(source.value), parent)
    if isinstance(source, WzFloatProperty):
        return WzFloatProperty(source.name, float(source.value), parent)
    if isinstance(source, WzDoubleProperty):
        return WzDoubleProperty(source.name, float(source.value), parent)
    if isinstance(source, WzNullProperty):
        return WzNullProperty(source.name, parent)
    if isinstance(source, WzUolProperty):
        return WzUolProperty(source.name, str(source.value), parent)
    if isinstance(source, WzConvexProperty):
        output = WzConvexProperty(source.name, parent)
        output.points = [
            WzVectorProperty(point.name, int(point.x), int(point.y), output)
            for point in source.points
        ]
        return output
    raise TypeError(f"unsupported WZ node: {type(source).__name__}")


def int_value(node, name: str) -> int:
    child = node.child(name)
    if not isinstance(child, (WzIntProperty, WzShortProperty)):
        raise RuntimeError(f"missing integer {name} in {node.name}")
    return int(child.value)


def patch_info(root: WzSubProperty, spec: ItemSpec) -> None:
    info = root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{spec.file_name}: missing info")
    if int_value(info, "reqLevel") != 250:
        raise RuntimeError(f"{spec.file_name}: source reqLevel is not 250")
    if int_value(info, "reqJob") != spec.req_job:
        raise RuntimeError(f"{spec.file_name}: unexpected reqJob")
    if int_value(info, "tuc") != spec.tuc:
        raise RuntimeError(f"{spec.file_name}: unexpected tuc")

    for name in REMOVE_INFO_FIELDS:
        info._children.pop(name, None)
    info._children["reqLevel"] = WzIntProperty("reqLevel", spec.target_level, info)
    if spec.weapon:
        info._children["limitBreak"] = WzIntProperty("limitBreak", LIMIT_BREAK, info)


def property_to_xml(prop, indent: int = 1) -> str:
    pad = "  " * indent
    name = f"name={quoteattr(prop.name)}"
    if isinstance(prop, WzNullProperty):
        return f"{pad}<null {name}/>"
    if isinstance(prop, WzShortProperty):
        return f'{pad}<short {name} value="{int(prop.value)}"/>'
    if isinstance(prop, WzIntProperty):
        return f'{pad}<int {name} value="{int(prop.value)}"/>'
    if isinstance(prop, WzLongProperty):
        return f'{pad}<long {name} value="{int(prop.value)}"/>'
    if isinstance(prop, WzFloatProperty):
        return f'{pad}<float {name} value="{float(prop.value)}"/>'
    if isinstance(prop, WzDoubleProperty):
        return f'{pad}<double {name} value="{float(prop.value)}"/>'
    if isinstance(prop, WzStringProperty):
        return f"{pad}<string {name} value={quoteattr(str(prop.value))}/>"
    if isinstance(prop, WzUolProperty):
        return f"{pad}<uol {name} value={quoteattr(str(prop.value))}/>"
    if isinstance(prop, WzVectorProperty):
        return f'{pad}<vector {name} x="{int(prop.x)}" y="{int(prop.y)}"/>'
    if isinstance(prop, WzConvexProperty):
        body = "\n".join(property_to_xml(child, indent + 1) for child in prop.children())
        return f"{pad}<extended {name}>\n{body}\n{pad}</extended>"
    if isinstance(prop, WzCanvasProperty):
        attrs = f'{name} width="{int(prop.width)}" height="{int(prop.height)}"'
        children = prop.children()
        if not children:
            return f"{pad}<canvas {attrs}/>"
        body = "\n".join(property_to_xml(child, indent + 1) for child in children)
        return f"{pad}<canvas {attrs}>\n{body}\n{pad}</canvas>"
    if isinstance(prop, WzSubProperty):
        children = prop.children()
        if not children:
            return f"{pad}<imgdir {name}/>"
        body = "\n".join(property_to_xml(child, indent + 1) for child in children)
        return f"{pad}<imgdir {name}>\n{body}\n{pad}</imgdir>"
    raise TypeError(f"unsupported XML node: {type(prop).__name__}")


def image_xml(name: str, root: WzSubProperty) -> bytes:
    body = "\n".join(property_to_xml(child) for child in root.children())
    text = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<imgdir name="{name}">\n{body}\n</imgdir>\n'
    )
    return text.encode("utf-8")


def build_selected_items(
    specs: tuple[ItemSpec, ...],
) -> tuple[dict[ItemSpec, tuple[bytes, bytes]], CanvasMaterializer]:
    materializer = CanvasMaterializer()
    outputs = {}
    for spec in specs:
        image = load_image(spec.source_path, BMS_KEY)
        root = WzSubProperty(image.root.name)
        for child in image.root.children():
            root.add(clone_property(child, root, materializer))
        patch_info(root, spec)
        image._root = root
        image._parsed = True
        outputs[spec] = (
            encode_image_body(image, gms_reader()),
            image_xml(spec.file_name, root),
        )
    return outputs, materializer


def build_items() -> tuple[dict[ItemSpec, tuple[bytes, bytes]], CanvasMaterializer]:
    outputs, materializer = build_selected_items(ITEM_SPECS)
    if materializer.canvases != EXPECTED_CANVASES:
        raise RuntimeError(f"expected {EXPECTED_CANVASES} canvases, got {materializer.canvases}")
    if materializer.outlinks != EXPECTED_OUTLINKS:
        raise RuntimeError(f"expected {EXPECTED_OUTLINKS} outlinks, got {materializer.outlinks}")
    return outputs, materializer


def source_strings(
    specs: tuple[ItemSpec, ...] = ITEM_SPECS,
) -> dict[ItemSpec, tuple[tuple[str, str], ...]]:
    image = load_image(SOURCE_STRING, BMS_KEY)
    result = {}
    for spec in specs:
        node = image.root.get(f"Eqp/{spec.category}/{spec.item_id}")
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"missing source string for {spec.item_id}")
        values = tuple(
            (child.name, str(child.value))
            for child in node.children()
            if isinstance(child, WzStringProperty)
        )
        names = [value for name, value in values if name == "name"]
        expected_prefix = "命運" if spec.weapon else "永恆"
        if len(names) != 1 or not names[0].startswith(expected_prefix):
            raise RuntimeError(f"unexpected source name for {spec.item_id}: {names}")
        description = (
            DESTINY_WEAPON_DESCRIPTION if spec.weapon else ETERNAL_ARMOR_DESCRIPTION
        )
        result[spec] = complete_string_values(values, description)
    return result


def complete_string_values(
    values: tuple[tuple[str, str], ...], description: str
) -> tuple[tuple[str, str], ...]:
    completed = []
    replaced = False
    for name, value in values:
        if name == "desc":
            completed.append((name, description))
            replaced = True
        else:
            completed.append((name, value))
    if not replaced:
        completed.append(("desc", description))
    return tuple(completed)


def patch_client_strings(names: dict[ItemSpec, tuple[tuple[str, str], ...]]) -> bytes:
    image = load_image(CLIENT_STRING, GMS_KEY)
    for spec, values in names.items():
        category = image.root.get(f"Eqp/{spec.category}")
        if not isinstance(category, WzSubProperty):
            raise RuntimeError(f"client String/Eqp missing category {spec.category}")
        category._children.pop(str(spec.item_id), None)
        node = WzSubProperty(str(spec.item_id), category)
        for name, value in values:
            node.add(WzStringProperty(name, value, node))
        category.add(node)
    return encode_image_body(image, gms_reader())


def direct_child(parent: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in parent if child.get("name") == name), None)


def patch_server_string(
    path: Path, names: dict[ItemSpec, tuple[tuple[str, str], ...]]
) -> bytes:
    text = path.read_text(encoding="utf-8")
    compact_empty_tags = text.count("/>") > text.count(" />") * 2
    grouped: dict[str, list[tuple[ItemSpec, tuple[tuple[str, str], ...]]]] = {}
    for spec, values in names.items():
        grouped.setdefault(spec.category, []).append((spec, values))

    for spec in names:
        pattern = re.compile(
            rf'^      <imgdir name="{spec.item_id}">\n.*?^      </imgdir>\n?',
            re.MULTILINE | re.DOTALL,
        )
        text, count = pattern.subn("", text)
        if count > 1:
            raise RuntimeError(f"{path}: duplicate string nodes for {spec.item_id}")

    empty_close = "/>" if compact_empty_tags else " />"
    for category_name, entries in grouped.items():
        marker = f'    <imgdir name="{category_name}">'
        start = text.find(marker)
        if start < 0:
            raise RuntimeError(f"{path}: missing category {category_name}")
        end = text.find("\n    </imgdir>", start)
        if end < 0:
            raise RuntimeError(f"{path}: unterminated category {category_name}")
        lines = []
        for spec, values in entries:
            lines.append(f'      <imgdir name="{spec.item_id}">')
            for name, value in values:
                lines.append(
                    f"        <string name={quoteattr(name)} "
                    f"value={quoteattr(value)}{empty_close}"
                )
            lines.append("      </imgdir>")
        text = text[:end] + "\n" + "\n".join(lines) + text[end:]

    ET.fromstring(text)
    return text.encode("utf-8")


def backup_paths(paths: list[Path]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = Path("/private/tmp") / f"beidou-destiny-eternal-{stamp}"
    for path in paths:
        if not path.exists():
            continue
        destination = backup / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    return backup


def assert_no_removed_fields(info: WzSubProperty, path: Path) -> None:
    remaining = REMOVE_INFO_FIELDS & set(info._children)
    if remaining:
        raise RuntimeError(f"{path}: removed fields remain: {sorted(remaining)}")


def scalar_values(info: WzSubProperty) -> dict[str, str]:
    scalar_types = (
        WzStringProperty,
        WzIntProperty,
        WzShortProperty,
        WzLongProperty,
        WzFloatProperty,
        WzDoubleProperty,
        WzUolProperty,
    )
    return {
        child.name: str(child.value)
        for child in info.children()
        if isinstance(child, scalar_types)
    }


def verify_item(spec: ItemSpec) -> tuple[int, int]:
    image = load_image(spec.client_path, GMS_KEY)
    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{spec.client_path}: missing info")
    if int_value(info, "reqLevel") != spec.target_level:
        raise RuntimeError(f"{spec.client_path}: reqLevel mismatch")
    if int_value(info, "reqJob") != spec.req_job:
        raise RuntimeError(f"{spec.client_path}: reqJob mismatch")
    if int_value(info, "tuc") != spec.tuc:
        raise RuntimeError(f"{spec.client_path}: tuc mismatch")
    assert_no_removed_fields(info, spec.client_path)
    if spec.weapon and int_value(info, "limitBreak") != LIMIT_BREAK:
        raise RuntimeError(f"{spec.client_path}: limitBreak mismatch")

    source = load_image(spec.source_path, BMS_KEY)
    source_info = source.root.child("info")
    if not isinstance(source_info, WzSubProperty):
        raise RuntimeError(f"{spec.source_path}: missing info")
    expected_scalars = {
        name: value
        for name, value in scalar_values(source_info).items()
        if name not in REMOVE_INFO_FIELDS
    }
    expected_scalars["reqLevel"] = str(spec.target_level)
    if spec.weapon:
        expected_scalars["limitBreak"] = str(LIMIT_BREAK)
    actual_scalars = scalar_values(info)
    if actual_scalars != expected_scalars:
        raise RuntimeError(f"{spec.client_path}: scalar property mismatch")

    canvases = 0
    particles = 0
    for node in walk(image.root):
        if isinstance(node, WzCanvasProperty):
            canvases += 1
            if node.child("_outlink") is not None:
                raise RuntimeError(f"{spec.client_path}: _outlink remains")
            if int(node.format) + int(node.format2) != 1:
                raise RuntimeError(f"{spec.client_path}: non-ARGB4444 Canvas")
            decode_canvas(node, region="GMS")
        if node.name == "particle":
            particles += 1
        if isinstance(node, WzStringProperty) and "destinyWeapon_4" in str(node.value):
            particles += 1
    if particles:
        raise RuntimeError(f"{spec.client_path}: particle data remains")

    server_root = ET.parse(spec.server_path).getroot()
    server_info = direct_child(server_root, "info")
    if server_info is None:
        raise RuntimeError(f"{spec.server_path}: missing info")
    server_values = {
        child.get("name", ""): child.get("value", "")
        for child in server_info
        if child.tag in {"string", "int", "short", "long", "float", "double", "uol"}
    }
    if server_values != actual_scalars:
        raise RuntimeError(f"{spec.server_path}: client/server property mismatch")
    if REMOVE_INFO_FIELDS & set(server_values):
        raise RuntimeError(f"{spec.server_path}: removed fields remain")
    return canvases, particles


def verify_strings(names: dict[ItemSpec, tuple[tuple[str, str], ...]]) -> None:
    client = load_image(CLIENT_STRING, GMS_KEY)
    for spec, values in names.items():
        node = client.root.get(f"Eqp/{spec.category}/{spec.item_id}")
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"client String/Eqp missing {spec.item_id}")
        actual = tuple(
            (child.name, str(child.value))
            for child in node.children()
            if isinstance(child, WzStringProperty)
        )
        if actual != values:
            raise RuntimeError(f"client String/Eqp mismatch for {spec.item_id}")
    for path in SERVER_STRINGS:
        root = ET.parse(path).getroot()
        eqp = direct_child(root, "Eqp")
        categories = {child.get("name"): child for child in eqp} if eqp is not None else {}
        for spec, values in names.items():
            category = categories.get(spec.category)
            node = direct_child(category, str(spec.item_id)) if category is not None else None
            actual = tuple(
                (child.get("name", ""), child.get("value", "")) for child in node
            ) if node is not None else ()
            if actual != values:
                raise RuntimeError(f"{path}: mismatch for {spec.item_id}")

def verify_outputs(names: dict[ItemSpec, tuple[tuple[str, str], ...]]) -> None:
    total_canvases = 0
    for spec in ITEM_SPECS:
        if not spec.client_path.is_file() or not spec.server_path.is_file():
            raise RuntimeError(f"missing migrated item {spec.item_id}")
        canvases, _ = verify_item(spec)
        total_canvases += canvases
    if total_canvases != EXPECTED_CANVASES:
        raise RuntimeError(f"written Canvas count mismatch: {total_canvases}")
    verify_strings(names)


def string_node(
    spec: ItemSpec, values: tuple[tuple[str, str], ...]
) -> WzSubProperty:
    node = WzSubProperty(str(spec.item_id))
    for name, value in values:
        node.add(WzStringProperty(name, value, node))
    return node


def upsert_client_string_records(
    names: dict[ItemSpec, tuple[tuple[str, str], ...]]
) -> int:
    from migrate_karing_later_stages import encode_record, locate_records

    grouped: dict[str, list[tuple[ItemSpec, tuple[tuple[str, str], ...]]]] = {}
    for spec, values in names.items():
        grouped.setdefault(spec.category, []).append((spec, values))

    changed = 0
    for category_name, entries in grouped.items():
        original = CLIENT_STRING.read_bytes()
        image = WzImage.from_bytes(original, key=GMS_KEY, name=CLIENT_STRING.name)
        image.parse()
        if image.truncated or image.parse_warnings:
            raise RuntimeError(
                f"{CLIENT_STRING}: malformed baseline {image.parse_warnings}"
            )
        size_offsets, count_offset, count_end, record_names, spans, records_end = (
            locate_records(image, original, ("Eqp", category_name))
        )
        raw_before = {
            name: original[start:end]
            for name, (start, end) in zip(record_names, spans)
        }
        replacements = {
            str(spec.item_id): encode_record(string_node(spec, values), image)
            for spec, values in entries
        }
        missing = tuple(name for name in replacements if name not in raw_before)
        expected_names = (*record_names, *missing)
        rebuilt = b"".join(
            replacements.get(name, raw_before[name]) for name in expected_names
        )
        records_start = spans[0][0] if spans else records_end
        updated = bytearray(
            original[:records_start] + rebuilt + original[records_end:]
        )
        if missing:
            new_count = encode_compressed_int(len(expected_names))
            if len(new_count) != count_end - count_offset:
                raise RuntimeError(
                    f"{CLIENT_STRING}: child-count encoding size changed"
                )
            updated[count_offset:count_end] = new_count
        delta = len(updated) - len(original)
        for size_offset in size_offsets:
            old_size = struct.unpack_from("<I", original, size_offset)[0]
            struct.pack_into("<I", updated, size_offset, old_size + delta)

        verified_data = bytes(updated)
        if verified_data == original:
            continue
        verified = WzImage.from_bytes(
            verified_data, key=GMS_KEY, name=CLIENT_STRING.name
        )
        verified.parse()
        if verified.truncated or verified.parse_warnings:
            raise RuntimeError(
                f"{CLIENT_STRING}: incremental result malformed "
                f"{verified.parse_warnings}"
            )
        _, _, _, after_names, after_spans, _ = locate_records(
            verified, verified_data, ("Eqp", category_name)
        )
        if after_names != expected_names:
            raise RuntimeError(
                f"{CLIENT_STRING}: {category_name} child order changed"
            )
        raw_after = {
            name: verified_data[start:end]
            for name, (start, end) in zip(after_names, after_spans)
        }
        for name, record in raw_before.items():
            expected = replacements.get(name, record)
            if raw_after.get(name) != expected:
                raise RuntimeError(
                    f"{CLIENT_STRING}: unexpected record change {category_name}/{name}"
                )
        for name in missing:
            if raw_after.get(name) != replacements[name]:
                raise RuntimeError(
                    f"{CLIENT_STRING}: inserted record mismatch {category_name}/{name}"
                )
        atomic_write(CLIENT_STRING, verified_data)
        changed += sum(
            raw_before.get(name) != replacement
            for name, replacement in replacements.items()
        )
    return changed


def upsert_server_string_records(
    path: Path,
    names: dict[ItemSpec, tuple[tuple[str, str], ...]],
) -> int:
    from migrate_karing_later_stages import find_xml_parent_close, property_to_xml

    text = path.read_text(encoding="utf-8")
    changed = 0
    for spec, values in names.items():
        node = string_node(spec, values)
        parent_path = ("Eqp", spec.category)
        parent_marker = f'<imgdir name="{spec.category}">'
        parent_start = text.find(parent_marker)
        if parent_start < 0:
            raise RuntimeError(f"{path}: missing category {spec.category}")
        parent_end = find_xml_parent_close(text, parent_path)
        record = find_xml_record_span(text, parent_path, str(spec.item_id))
        if record is not None:
            start, end, indent = record
            rendered = property_to_xml(node).splitlines()
            replacement = "\n".join(
                indent + (line[2:] if line.startswith("  ") else line)
                for line in rendered
            ) + "\n"
            if text[start:end] == replacement:
                continue
            text = text[:start] + replacement + text[end:]
        else:
            parent_line_start = text.rfind("\n", 0, parent_start) + 1
            parent_indent = text[parent_line_start:parent_start]
            rendered = "\n".join(
                parent_indent + "  " + line[2:]
                for line in property_to_xml(node).splitlines()
            ) + "\n"
            text = text[:parent_end] + rendered + text[parent_end:]
        changed += 1

    root = ET.fromstring(text)
    eqp = direct_child(root, "Eqp")
    categories = {child.get("name"): child for child in eqp} if eqp is not None else {}
    for spec, values in names.items():
        category = categories.get(spec.category)
        node = direct_child(category, str(spec.item_id)) if category is not None else None
        actual = tuple(
            (child.get("name", ""), child.get("value", "")) for child in node
        ) if node is not None else ()
        if actual != values:
            raise RuntimeError(f"{path}: incremental string mismatch {spec.item_id}")
    if changed:
        atomic_write(path, text.encode("utf-8"))
    return changed


def find_xml_record_span(
    text: str, parent_path: tuple[str, ...], child_name: str
) -> tuple[int, int, str] | None:
    token_pattern = re.compile(r'<imgdir\b[^>]*\bname="([^"]+)"[^>]*>|</imgdir>')
    stack: list[str] = []
    active_start: int | None = None
    active_indent = ""
    matches: list[tuple[int, int, str]] = []
    for match in token_pattern.finditer(text):
        if match.group(1) is not None:
            name = match.group(1)
            if match.group(0).rstrip().endswith("/>"):
                continue
            if tuple(stack[1:]) == parent_path and name == child_name:
                line_start = text.rfind("\n", 0, match.start()) + 1
                prefix = text[line_start:match.start()]
                active_start = line_start if prefix.isspace() else match.start()
                active_indent = prefix if prefix.isspace() else ""
            stack.append(name)
            continue
        if not stack:
            raise RuntimeError("unbalanced XML imgdir close")
        closing_name = stack.pop()
        if closing_name == child_name and tuple(stack[1:]) == parent_path:
            if active_start is None:
                raise RuntimeError(f"missing XML record start: {child_name}")
            end = match.end()
            if end < len(text) and text[end] == "\n":
                end += 1
            matches.append((active_start, end, active_indent))
            active_start = None
    if stack:
        raise RuntimeError("unbalanced XML imgdir open")
    if len(matches) > 1:
        raise RuntimeError(f"duplicate XML record {child_name}")
    return matches[0] if matches else None


def apply_string_records_incrementally(
    names: dict[ItemSpec, tuple[tuple[str, str], ...]]
) -> tuple[int, int, Path]:
    backup = backup_paths([CLIENT_STRING, *SERVER_STRINGS])
    client_records = upsert_client_string_records(names)
    server_records = sum(
        upsert_server_string_records(path, names) for path in SERVER_STRINGS
    )
    verify_strings(names)
    return client_records, server_records, backup


def apply_shoulders_incrementally() -> None:
    from migrate_karing_later_stages import insert_raw_record, insert_xml_record

    names = source_strings(SHOULDER_SPECS)
    outputs, materializer = build_selected_items(SHOULDER_SPECS)
    if materializer.canvases != 10 or materializer.outlinks != 10:
        raise RuntimeError(
            "unexpected shoulder Canvas contract: "
            f"canvases={materializer.canvases} outlinks={materializer.outlinks}"
        )

    touched = [CLIENT_STRING, *SERVER_STRINGS]
    touched += [spec.client_path for spec in SHOULDER_SPECS]
    touched += [spec.server_path for spec in SHOULDER_SPECS]
    backup = backup_paths(touched)
    for spec, (client_data, server_data) in outputs.items():
        atomic_write(spec.client_path, client_data)
        atomic_write(spec.server_path, server_data)

    client_records = 0
    server_records = 0
    for spec, values in names.items():
        node = string_node(spec, values)
        client_records += int(insert_raw_record(CLIENT_STRING, ("Eqp", "Accessory"), node))
        for path in SERVER_STRINGS:
            server_records += int(insert_xml_record(path, ("Eqp", "Accessory"), node))

    for spec in SHOULDER_SPECS:
        verify_item(spec)
    verify_strings(names)
    print(
        f"shoulders={len(outputs)} canvases={materializer.canvases} "
        f"outlinks={materializer.outlinks} clientStrings={client_records} "
        f"serverStrings={server_records} backup={backup}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write validated migration outputs")
    parser.add_argument(
        "--apply-shoulders",
        action="store_true",
        help="incrementally add only the five Eternal shoulder items",
    )
    parser.add_argument(
        "--apply-strings",
        action="store_true",
        help="incrementally complete only the selected equipment strings",
    )
    parser.add_argument("--verify", action="store_true", help="verify existing migration outputs")
    args = parser.parse_args()

    if len(ITEM_SPECS) != EXPECTED_ITEMS or len({spec.item_id for spec in ITEM_SPECS}) != EXPECTED_ITEMS:
        raise RuntimeError("selected item set is not exactly 51 unique IDs")
    if args.apply_shoulders:
        apply_shoulders_incrementally()
        return 0
    names = source_strings()
    if args.apply_strings:
        client_records, server_records, backup = apply_string_records_incrementally(names)
        print(
            f"strings={len(names)} clientRecords={client_records} "
            f"serverRecords={server_records} backup={backup}"
        )
        return 0
    if args.verify:
        verify_outputs(names)
        print(f"verification passed: items={EXPECTED_ITEMS} canvases={EXPECTED_CANVASES}")
        return 0

    outputs, materializer = build_items()
    client_string_data = patch_client_strings(names)
    server_string_data = {path: patch_server_string(path, names) for path in SERVER_STRINGS}
    print(
        f"items={len(outputs)} canvases={materializer.canvases} "
        f"outlinks={materializer.outlinks} unique_links={len(materializer.payloads)} "
        f"linked_files={len(materializer.images)} converted={materializer.converted}"
    )
    if not args.apply:
        print("dry-run complete; pass --apply to write outputs")
        return 0

    touched = [CLIENT_STRING, *SERVER_STRINGS]
    touched += [spec.client_path for spec in ITEM_SPECS]
    touched += [spec.server_path for spec in ITEM_SPECS]
    backup = backup_paths(touched)
    for spec, (client_data, server_data) in outputs.items():
        atomic_write(spec.client_path, client_data)
        atomic_write(spec.server_path, server_data)
    atomic_write(CLIENT_STRING, client_string_data)
    for path, data in server_string_data.items():
        atomic_write(path, data)

    verify_outputs(names)
    print(f"verification passed; backup={backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
