#!/usr/bin/env python3
"""Migrate the Enma face accessory as collision-free equipment 1012136."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import struct
import sys
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

spec = importlib.util.spec_from_file_location(
    "arcane_migration",
    ROOT / "tool/scripts/migration/migrate_arcane_river_expansion.py",
)
arc = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = arc
spec.loader.exec_module(arc)

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.canvas import _encode_pixels, decode_canvas  # noqa: E402
from wzpy.incremental_img import (  # noqa: E402
    _apply_edits,
    _count_edit,
    _find_list,
    _find_record,
    _record_bytes,
    _reference_edits,
    _size_edits,
    scan_img,
)
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_string_block  # noqa: E402


SOURCE_ID = 1012135
TARGET_ID = 1012136
SOURCE_NAME = f"0{SOURCE_ID}.img"
TARGET_NAME = f"0{TARGET_ID}.img"
SOURCE_ATTACHMENT = Path("/Users/lizixian/Downloads") / SOURCE_NAME
SOURCE_ATTACHMENT_SHA256 = "a75a8e01ff9f0d1a4257a7753dc370c045c8058178ef7559c18d78e86a440810"
LEGACY_BASELINE = ROOT / "clien/Data/Character/Accessory" / SOURCE_NAME
LEGACY_BASELINE_SHA256 = "47fae7e84d568e4943c83458d6462608c9f447b3797319271886804e0280559d"
CLIENT_TARGET = ROOT / "clien/Data/Character/Accessory" / TARGET_NAME
SERVER_TARGET = ROOT / "gms-server/wz/Character.wz/Accessory" / f"{TARGET_NAME}.xml"
SERVER_BASELINE = ROOT / "gms-server/wz/Character.wz/Accessory" / f"{SOURCE_NAME}.xml"
CLIENT_STRING = ROOT / "clien/Data/String/Eqp.img"
SERVER_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Eqp.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Eqp.img.xml",
)
STRING_PARENT = ("Eqp", "Accessory")
STRING_ANCHOR = "1012137"
ITEM_NAME = "阎魔"
ITEM_DESC = "光月日和赠予索隆的刀，属于大快刀二十一工，能强行释放使用者的霸气。"
STATS = {
    "incSTR": 20,
    "incDEX": 20,
    "incINT": 20,
    "incLUK": 20,
    "incPAD": 100,
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_image(data: bytes, *, region: str, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=arc.WzKey.for_region(region), name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"malformed {name}: truncated={image.truncated}, warnings={image.parse_warnings}"
        )
    return image


def semantic_state(image: WzImage, *, region: str) -> tuple:
    state = []

    def visit(node, parent: tuple[str, ...] = ()) -> None:
        for child in node.children():
            path = (*parent, child.name)
            if isinstance(child, WzCanvasProperty):
                bitmap = decode_canvas(child, region=region).convert("RGBA")
                value = (
                    "Canvas",
                    bitmap.size,
                    hashlib.sha256(bitmap.tobytes()).hexdigest(),
                )
            elif isinstance(child, WzVectorProperty):
                value = ("Vector", int(child.x), int(child.y))
            elif isinstance(child, WzSubProperty):
                value = ("SubProperty",)
            else:
                value = (type(child).__name__, getattr(child, "value", None))
            state.append((path, value))
            if hasattr(child, "children"):
                visit(child, path)

    visit(image.root)
    return tuple(state)


def verify_attachment_matches_legacy() -> None:
    if not SOURCE_ATTACHMENT.is_file():
        raise FileNotFoundError(SOURCE_ATTACHMENT)
    attachment_data = SOURCE_ATTACHMENT.read_bytes()
    if sha256(attachment_data) != SOURCE_ATTACHMENT_SHA256:
        raise RuntimeError("the supplied 01012135.img is not the reviewed attachment")
    legacy_data = LEGACY_BASELINE.read_bytes()
    if sha256(legacy_data) != LEGACY_BASELINE_SHA256:
        raise RuntimeError("the proven GMS 1012135 compatibility baseline changed")
    attachment = load_image(attachment_data, region="EMS", name=SOURCE_NAME)
    legacy = load_image(legacy_data, region="GMS", name=SOURCE_NAME)
    if semantic_state(attachment, region="EMS") != semantic_state(legacy, region="GMS"):
        raise RuntimeError("the supplied EMS equipment differs from the GMS legacy analogue")


def argb4444_icon(image: WzImage, icon_name: str) -> WzCanvasProperty:
    source = image.root.get(f"info/{icon_name}")
    if not isinstance(source, WzCanvasProperty):
        raise RuntimeError(f"missing info/{icon_name}")
    bitmap = decode_canvas(source, region="GMS").convert("RGBA")
    output = WzCanvasProperty(icon_name)
    output.width, output.height = bitmap.size
    output.format, output.format2 = 1, 0
    # Both payloads are ordinary zlib streams. These deterministic compressor
    # settings make their combined record delta exactly cancel the five new
    # stat records, so the info block keeps its original byte length and every
    # later raw record remains byte-for-byte stable.
    compression = {
        "icon": (6, 4, zlib.Z_DEFAULT_STRATEGY, 870),
        "iconRaw": (7, 1, zlib.Z_FILTERED, 1003),
    }
    level, mem_level, strategy, expected_length = compression[icon_name]
    compressor = zlib.compressobj(
        level, zlib.DEFLATED, zlib.MAX_WBITS, mem_level, strategy
    )
    raw = _encode_pixels(bitmap, 1, bitmap.width, bitmap.height)
    output._png_data = compressor.compress(raw) + compressor.flush()
    if len(output._png_data) != expected_length:
        raise RuntimeError(f"unexpected {icon_name} compressed length")
    output._png_length = len(output._png_data)
    output._png_offset = 0
    for child in source.children():
        if not isinstance(child, WzVectorProperty):
            raise RuntimeError(f"unsupported icon metadata: {child.name} ({type(child).__name__})")
        output.add(WzVectorProperty(child.name, int(child.x), int(child.y), output))
    return output


def verify_equipment_scope(before: bytes, after: bytes) -> None:
    approved = {
        ("info", "icon"),
        ("info", "iconRaw"),
        *(("info", name) for name in STATS),
    }
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)

    def affected(path: tuple[str, ...]) -> bool:
        return any(
            path[: len(root)] == root or root[: len(path)] == path
            for root in approved
        )

    removed = set(before_records) - set(after_records)
    added = set(after_records) - set(before_records)
    if removed:
        raise RuntimeError(f"equipment migration removed records: {sorted(removed)}")
    if any(not affected(path) for path in added):
        raise RuntimeError(f"equipment migration added unapproved records: {sorted(added)}")
    for path in set(before_records) & set(after_records):
        if not affected(path) and before_records[path] != after_records[path]:
            raise RuntimeError(f"equipment migration changed protected record: {path}")
    for parent, names in before_orders.items():
        current = after_orders[parent]
        protected = tuple(name for name in current if (*parent, name) not in added)
        if protected != names:
            raise RuntimeError(f"equipment migration reordered siblings at {parent}")


def replace_canvas_record(data: bytes, path: tuple[str, ...], prop) -> bytes:
    """Replace one Canvas while preserving valid references into its string prefix."""
    layout = scan_img(data, region="GMS")
    reader = WzBinaryReader(io.BytesIO(data), arc.GMS_KEY)
    _parent, record, ancestors = _find_record(layout.root, path)
    encoded = _record_bytes(prop, reader)
    encoded_name_end = len(encode_string_block(reader, prop.name))
    replacement = data[record.start : record.tag_offset] + encoded[encoded_name_end:]
    delta = len(replacement) - (record.end - record.start)
    structural_edits = [
        (record.start, record.end, replacement),
        *_size_edits(ancestors, delta),
    ]
    preview = _apply_edits(data, [(record.start, record.end, replacement)])
    old_reader = WzBinaryReader(io.BytesIO(data), arc.GMS_KEY)
    new_reader = WzBinaryReader(io.BytesIO(preview), arc.GMS_KEY)
    reference_edits = []
    shifting = [
        edit for edit in structural_edits if len(edit[2]) != edit[1] - edit[0]
    ]
    for reference in layout.string_references:
        if any(
            start < end and start <= reference.field_offset < end
            for start, end, _replacement in shifting
        ):
            continue
        target = reference.target_offset
        for start, end, edit_data in sorted(shifting, key=lambda edit: edit[0]):
            edit_delta = len(edit_data) - (end - start)
            if start < end and start <= reference.target_offset < end:
                if (start, end) != (record.start, record.end):
                    raise RuntimeError("string reference points into a size-changing metadata edit")
                if old_reader.read_string_at(reference.target_offset) != new_reader.read_string_at(
                    reference.target_offset
                ):
                    raise RuntimeError("Canvas replacement moved an internally referenced string")
                continue
            if reference.target_offset >= end:
                target += edit_delta
        if target != reference.target_offset:
            reference_edits.append(
                (
                    reference.field_offset,
                    reference.field_offset + 4,
                    struct.pack("<I", target),
                )
            )
    result = _apply_edits(data, [*structural_edits, *reference_edits])
    load_image(result, region="GMS", name=TARGET_NAME)
    scan_img(result, region="GMS")
    return result


def insert_stats(data: bytes) -> bytes:
    layout = scan_img(data, region="GMS")
    prop_list, ancestors = _find_list(layout.root, ("info",))
    props = tuple(WzIntProperty(name, value) for name, value in STATS.items())
    names = {prop.name for prop in props}
    if names.intersection(record.name for record in prop_list.records):
        raise RuntimeError("one or more Enma stat nodes already exist in the baseline")
    anchor = next((record for record in prop_list.records if record.name == "cash"), None)
    if anchor is None:
        raise RuntimeError("missing info/cash stat insertion anchor")
    reader = WzBinaryReader(io.BytesIO(data), arc.GMS_KEY)
    records = b"".join(_record_bytes(prop, reader) for prop in props)
    count_edit = _count_edit(prop_list, prop_list.count + len(props))
    count_delta = len(count_edit[2]) - (count_edit[1] - count_edit[0])
    delta = len(records) + count_delta
    edits = [
        (anchor.start, anchor.start, records),
        count_edit,
        *_size_edits(ancestors, delta),
    ]
    edits.extend(_reference_edits(layout, edits))
    result = _apply_edits(data, edits)
    load_image(result, region="GMS", name=TARGET_NAME)
    scan_img(result, region="GMS")
    return result


def build_client_equipment() -> bytes:
    before = LEGACY_BASELINE.read_bytes()
    image = load_image(before, region="GMS", name=SOURCE_NAME)
    after = before
    for icon_name in ("icon", "iconRaw"):
        after = replace_canvas_record(
            after,
            ("info", icon_name),
            argb4444_icon(image, icon_name),
        )
    after = insert_stats(after)
    verify_equipment_scope(before, after)
    return after


def make_string_record() -> WzSubProperty:
    record = WzSubProperty(str(TARGET_ID))
    record.add(WzStringProperty("desc", ITEM_DESC, record))
    record.add(WzStringProperty("name", ITEM_NAME, record))
    return record


def build_server_equipment() -> str:
    text = SERVER_BASELINE.read_text(encoding="utf-8")
    source_root = f'<imgdir name="{SOURCE_NAME}">'
    target_root = f'<imgdir name="{TARGET_NAME}">'
    if text.count(source_root) != 1:
        raise RuntimeError("unexpected legacy server equipment root")
    text = text.replace(source_root, target_root, 1)
    for icon_name in ("icon", "iconRaw"):
        marker = f'<canvas name="{icon_name}" width="31" height="32">'
        replacement = f'<canvas name="{icon_name}" width="31" height="32" format="1">'
        if text.count(marker) != 1:
            raise RuntimeError(f"unexpected server {icon_name} Canvas")
        text = text.replace(marker, replacement, 1)
    anchor = '    <int name="cash" value="1"/>'
    if text.count(anchor) != 1:
        raise RuntimeError("unexpected server info/cash anchor")
    stats = "\n".join(
        f'    <int name="{name}" value="{value}"/>' for name, value in STATS.items()
    )
    text = text.replace(anchor, f"{stats}\n{anchor}", 1)
    ET.fromstring(text)
    return text


def stage_client_string() -> bytes:
    before = CLIENT_STRING.read_bytes()
    image = load_image(before, region="GMS", name=CLIENT_STRING.name)
    existing = image.root.get("/".join((*STRING_PARENT, str(TARGET_ID))))
    if existing is not None:
        if (
            getattr(existing.child("name"), "value", None) != ITEM_NAME
            or getattr(existing.child("desc"), "value", None) != ITEM_DESC
        ):
            raise RuntimeError(f"conflicting client String record {TARGET_ID}")
        return before
    after = arc.insert_property_record_before(
        before, STRING_PARENT, make_string_record(), STRING_ANCHOR
    )
    arc.verify_raw_record_insert_scope(
        before, after, {(*STRING_PARENT, str(TARGET_ID))}
    )
    return after


def stage_server_string(path: Path) -> str:
    before = path.read_text(encoding="utf-8")
    root = ET.fromstring(before)
    parent = root.find('./imgdir[@name="Eqp"]/imgdir[@name="Accessory"]')
    if parent is None:
        raise RuntimeError(f"missing Eqp/Accessory in {path}")
    existing = parent.find(f'./imgdir[@name="{TARGET_ID}"]')
    if existing is not None:
        values = {child.get("name"): child.get("value") for child in existing}
        if values.get("name") != ITEM_NAME or values.get("desc") != ITEM_DESC:
            raise RuntimeError(f"conflicting server String record {TARGET_ID} in {path}")
        return before
    after = arc.insert_xml_properties_before(
        before, STRING_PARENT, [make_string_record()], STRING_ANCHOR
    )
    ET.fromstring(after)
    return after


def validate_equipment(data: bytes) -> WzImage:
    image = load_image(data, region="GMS", name=TARGET_NAME)
    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError("missing equipment info")
    for name, value in STATS.items():
        if getattr(info.child(name), "value", None) != value:
            raise RuntimeError(f"incorrect {name}")
    canvases = []

    def visit(node) -> None:
        for child in node.children():
            if isinstance(child, WzCanvasProperty):
                bitmap = decode_canvas(child, region="GMS")
                if bitmap.getbbox() is None:
                    raise RuntimeError(f"blank Canvas: {child.path}")
                canvases.append(child)
            if hasattr(child, "children"):
                visit(child)

    visit(image.root)
    if len(canvases) != 21:
        raise RuntimeError(f"expected 21 Canvases, found {len(canvases)}")
    for name in ("icon", "iconRaw"):
        icon = info.child(name)
        if not isinstance(icon, WzCanvasProperty):
            raise RuntimeError(f"missing {name}")
        if (icon.format, icon.format2) != (1, 0):
            raise RuntimeError(f"{name} is not GMS ARGB4444")
    return image


def main() -> None:
    verify_attachment_matches_legacy()
    equipment = build_client_equipment()
    validate_equipment(equipment)
    server_equipment = build_server_equipment()
    ET.fromstring(server_equipment)
    client_string = stage_client_string()
    server_strings = {path: stage_server_string(path) for path in SERVER_STRINGS}

    if CLIENT_TARGET.exists() and CLIENT_TARGET.read_bytes() != equipment:
        raise RuntimeError(f"conflicting target equipment: {CLIENT_TARGET}")
    if SERVER_TARGET.exists() and SERVER_TARGET.read_text(encoding="utf-8") != server_equipment:
        raise RuntimeError(f"conflicting server equipment: {SERVER_TARGET}")

    arc.atomic_write_bytes(CLIENT_TARGET, equipment)
    arc.atomic_write_text(SERVER_TARGET, server_equipment)
    arc.atomic_write_bytes(CLIENT_STRING, client_string)
    for path, text in server_strings.items():
        arc.atomic_write_text(path, text)

    print(f"installed {TARGET_ID} {ITEM_NAME}")
    print(f"equipment_sha256={sha256(equipment)}")
    print(f"canvases=21 icons_argb4444=2 stats={STATS}")


if __name__ == "__main__":
    main()
