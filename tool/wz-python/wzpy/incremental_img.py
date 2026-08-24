"""Binary-safe record-level mutations for standalone IMG files.

The existing full writer is useful for constructing a new property record,
but rewriting a complete legacy IMG can change unrelated string-block forms.
This module scans the original record boundaries and patches only the target
record, its property-list count, and the size fields of enclosing tag-9 blocks.
"""

from __future__ import annotations

import io
import struct
from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional, Sequence, Tuple

from .crypto import WzKey, detect_region_from_img
from .properties import (
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
from .reader import WzBinaryReader
from .writer import (
    _encode_property_list,
    encode_compressed_int,
    encode_string_block,
)
from .wz_image import WzImage


SUPPORTED_ADD_TYPES = (
    "SubProperty", "Null", "Short", "Int", "Long", "Float", "Double",
    "String", "Vector", "UOL",
)


@dataclass
class PropertyListSpan:
    count_offset: int
    count_end: int
    count: int
    records: List["PropertyRecordSpan"] = field(default_factory=list)
    end: int = 0


@dataclass
class PropertyRecordSpan:
    name: str
    start: int
    name_end: int
    tag_offset: int
    body_start: int
    end: int
    tag: int
    size_offset: Optional[int] = None
    block_size: Optional[int] = None
    ext_type: Optional[str] = None
    children: Optional[PropertyListSpan] = None


@dataclass
class ImgLayout:
    region: str
    header_end: int
    root: PropertyListSpan
    string_references: List["StringReference"] = field(default_factory=list)
    opaque_extended_types: List[str] = field(default_factory=list)


@dataclass
class StringReference:
    field_offset: int
    target_offset: int


@dataclass
class MutationResult:
    data: bytes
    region: str
    operation: str
    path_before: Tuple[str, ...]
    path_after: Optional[Tuple[str, ...]]
    byte_delta: int


def _scan_property_list(
    reader: WzBinaryReader,
    *,
    base_offset: int,
    string_references: List[StringReference],
    opaque_extended_types: List[str],
) -> PropertyListSpan:
    count_offset = reader.position
    count = reader.read_compressed_int()
    if count < 0:
        raise ValueError(f"negative property count at 0x{count_offset:X}")
    result = PropertyListSpan(count_offset, reader.position, count)
    for _ in range(count):
        start = reader.position
        name = _read_string_block(reader, base_offset, string_references)
        name_end = reader.position
        tag_offset = reader.position
        tag = reader.read_byte()
        body_start = reader.position
        size_offset: Optional[int] = None
        block_size: Optional[int] = None
        ext_type: Optional[str] = None
        children: Optional[PropertyListSpan] = None

        if tag == 0:
            pass
        elif tag in (2, 11):
            reader.skip(2)
        elif tag in (3, 19):
            reader.read_compressed_int()
        elif tag == 20:
            reader.read_compressed_long()
        elif tag == 4:
            if reader.read_byte() == 0x80:
                reader.skip(4)
        elif tag == 5:
            reader.skip(8)
        elif tag == 8:
            _read_string_block(reader, base_offset, string_references)
        elif tag == 9:
            size_offset = reader.position
            block_size = reader.read_u32()
            block_end = reader.position + block_size
            ext_type = _read_string_block(reader, base_offset, string_references)
            if ext_type == "Property":
                reader.skip(2)
                children = _scan_property_list(
                    reader,
                    base_offset=base_offset,
                    string_references=string_references,
                    opaque_extended_types=opaque_extended_types,
                )
            elif ext_type in ("Canvas", "Canvas#Video"):
                reader.skip(1)
                has_children = reader.read_byte()
                if has_children == 1:
                    reader.skip(2)
                    children = _scan_property_list(
                        reader,
                        base_offset=base_offset,
                        string_references=string_references,
                        opaque_extended_types=opaque_extended_types,
                    )
                elif has_children != 0:
                    raise ValueError(
                        f"invalid {ext_type} child marker {has_children} at 0x{reader.position - 1:X}"
                    )
            elif ext_type == "RawData":
                data_type = reader.read_byte()
                if data_type == 1:
                    has_children = reader.read_byte()
                    if has_children == 1:
                        reader.skip(2)
                        children = _scan_property_list(
                            reader,
                            base_offset=base_offset,
                            string_references=string_references,
                            opaque_extended_types=opaque_extended_types,
                        )
                    elif has_children != 0:
                        raise ValueError(
                            f"invalid RawData child marker {has_children} at 0x{reader.position - 1:X}"
                        )
            elif ext_type == "Shape2D#Convex2D":
                point_count = reader.read_compressed_int()
                for _ in range(point_count):
                    point_type = _read_string_block(reader, base_offset, string_references)
                    if point_type != "Shape2D#Vector2D":
                        raise ValueError(f"unsupported convex point type: {point_type}")
                    reader.read_compressed_int()
                    reader.read_compressed_int()
            elif ext_type == "Shape2D#Vector2D":
                reader.read_compressed_int()
                reader.read_compressed_int()
            elif ext_type in ("Sound_DX8", "Sound"):
                reader.seek(block_end)
            elif ext_type == "UOL":
                reader.skip(1)
                _read_string_block(reader, base_offset, string_references)
            else:
                opaque_extended_types.append(ext_type)
            if reader.position > block_end:
                raise ValueError(
                    f"property {name!r} overruns its block by {reader.position - block_end} bytes"
                )
            reader.seek(block_end)
        else:
            raise ValueError(f"unsupported property tag {tag} for {name!r}")

        result.records.append(PropertyRecordSpan(
            name=name,
            start=start,
            name_end=name_end,
            tag_offset=tag_offset,
            body_start=body_start,
            end=reader.position,
            tag=tag,
            size_offset=size_offset,
            block_size=block_size,
            ext_type=ext_type,
            children=children,
        ))
    result.end = reader.position
    return result


def _read_string_block(
    reader: WzBinaryReader,
    base_offset: int,
    references: List[StringReference],
) -> str:
    marker_offset = reader.position
    marker = reader.read_byte()
    if marker in (0x00, 0x73):
        return reader.read_string()
    if marker in (0x01, 0x1B):
        relative_offset = reader.read_u32()
        references.append(StringReference(marker_offset + 1, base_offset + relative_offset))
        return reader.read_string_at(base_offset + relative_offset)
    raise ValueError(f"unknown string-block marker 0x{marker:02X} at 0x{marker_offset:X}")


def scan_img(data: bytes, region: Optional[str] = None) -> ImgLayout:
    picked = region or detect_region_from_img(data)
    if not picked:
        raise ValueError("cannot detect the IMG encryption region")
    reader = WzBinaryReader(io.BytesIO(data), WzKey.for_region(picked))
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise ValueError("unsupported standalone IMG header")
    reader.skip(2)
    header_end = reader.position
    string_references: List[StringReference] = []
    opaque_extended_types: List[str] = []
    root = _scan_property_list(
        reader,
        base_offset=0,
        string_references=string_references,
        opaque_extended_types=opaque_extended_types,
    )
    if reader.position != len(data):
        raise ValueError(
            f"root records end at 0x{reader.position:X}, file ends at 0x{len(data):X}"
        )
    return ImgLayout(
        picked,
        header_end,
        root,
        string_references=string_references,
        opaque_extended_types=opaque_extended_types,
    )


def _find_record(
    root: PropertyListSpan,
    path: Sequence[str],
) -> Tuple[PropertyListSpan, PropertyRecordSpan, List[PropertyRecordSpan]]:
    if not path:
        raise ValueError("path must identify a property")
    current = root
    ancestors: List[PropertyRecordSpan] = []
    for index, part in enumerate(path):
        record = next((item for item in current.records if item.name == part), None)
        if record is None:
            raise KeyError("/".join(path[:index + 1]))
        if index == len(path) - 1:
            return current, record, ancestors
        if record.children is None:
            raise ValueError(f"{'/'.join(path[:index + 1])} is not a container")
        ancestors.append(record)
        current = record.children
    raise AssertionError("unreachable")


def _find_list(
    root: PropertyListSpan,
    path: Sequence[str],
) -> Tuple[PropertyListSpan, List[PropertyRecordSpan]]:
    if not path:
        return root, []
    parent_list, record, ancestors = _find_record(root, path)
    del parent_list
    if record.children is None:
        raise ValueError(f"{'/'.join(path)} is not a container")
    return record.children, ancestors + [record]


def _apply_edits(data: bytes, edits: Iterable[Tuple[int, int, bytes]]) -> bytes:
    ordered = sorted(edits, key=lambda edit: edit[0], reverse=True)
    last_start = len(data) + 1
    result = bytearray(data)
    for start, end, replacement in ordered:
        if not (0 <= start <= end <= len(data)):
            raise ValueError(f"invalid byte edit {start}:{end}")
        if end > last_start:
            raise ValueError("overlapping byte edits")
        result[start:end] = replacement
        last_start = start
    return bytes(result)


def _reference_edits(
    layout: ImgLayout,
    structural_edits: Sequence[Tuple[int, int, bytes]],
) -> List[Tuple[int, int, bytes]]:
    shifting = [
        edit for edit in structural_edits
        if len(edit[2]) != edit[1] - edit[0]
    ]
    if not shifting:
        return []
    if layout.opaque_extended_types:
        unique = ", ".join(sorted(set(layout.opaque_extended_types)))
        raise ValueError(
            "size-changing edits are unsafe with opaque extended properties: " + unique
        )

    result: List[Tuple[int, int, bytes]] = []
    for reference in layout.string_references:
        field_replaced = any(
            start < end and start <= reference.field_offset < end
            for start, end, _ in shifting
        )
        if field_replaced:
            continue

        original_target = reference.target_offset
        target = original_target
        for start, end, replacement in sorted(shifting, key=lambda edit: edit[0]):
            delta = len(replacement) - (end - start)
            if start < end and start <= original_target < end:
                raise ValueError(
                    f"string reference at 0x{reference.field_offset:X} points into replaced bytes"
                )
            if original_target >= end:
                target += delta
        if target != reference.target_offset:
            if not 0 <= target <= 0xFFFFFFFF:
                raise ValueError("rebased string reference is out of range")
            result.append((
                reference.field_offset,
                reference.field_offset + 4,
                struct.pack("<I", target),
            ))
    return result


def _size_edits(
    ancestors: Sequence[PropertyRecordSpan],
    delta: int,
) -> List[Tuple[int, int, bytes]]:
    edits: List[Tuple[int, int, bytes]] = []
    for record in ancestors:
        if record.size_offset is None or record.block_size is None:
            raise ValueError(f"container {record.name!r} has no block-size field")
        new_size = record.block_size + delta
        if not (0 <= new_size <= 0xFFFFFFFF):
            raise ValueError(f"container {record.name!r} size is out of range")
        edits.append((record.size_offset, record.size_offset + 4, struct.pack("<I", new_size)))
    return edits


def _count_edit(prop_list: PropertyListSpan, new_count: int) -> Tuple[int, int, bytes]:
    if new_count < 0:
        raise ValueError("property count cannot be negative")
    return (prop_list.count_offset, prop_list.count_end, encode_compressed_int(new_count))


def _record_bytes(prop: Any, reader: WzBinaryReader) -> bytes:
    encoded = _encode_property_list((prop,), reader)
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise ValueError("unexpected encoded property-list prefix")
    return encoded[len(prefix):]


def _construct_property(kind: str, name: str, values: dict) -> Any:
    if kind not in SUPPORTED_ADD_TYPES:
        raise ValueError(f"unsupported property type: {kind}")
    if not name:
        raise ValueError("property name is required")
    if kind == "SubProperty":
        return WzSubProperty(name)
    if kind == "Null":
        return WzNullProperty(name)
    if kind == "Short":
        value = int(values.get("value", 0))
        if not -(1 << 15) <= value < (1 << 15):
            raise ValueError("Short value is out of range")
        return WzShortProperty(name, value)
    if kind == "Int":
        value = int(values.get("value", 0))
        if not -(1 << 31) <= value < (1 << 31):
            raise ValueError("Int value is out of range")
        return WzIntProperty(name, value)
    if kind == "Long":
        value = int(values.get("value", 0))
        if not -(1 << 63) <= value < (1 << 63):
            raise ValueError("Long value is out of range")
        return WzLongProperty(name, value)
    if kind == "Float":
        return WzFloatProperty(name, float(values.get("value", 0)))
    if kind == "Double":
        return WzDoubleProperty(name, float(values.get("value", 0)))
    if kind == "String":
        return WzStringProperty(name, str(values.get("value", "")))
    if kind == "UOL":
        return WzUolProperty(name, str(values.get("value", "")))
    return WzVectorProperty(name, int(values.get("x", 0)), int(values.get("y", 0)))


def normalized_values(kind: str, values: dict) -> dict:
    prop = _construct_property(kind, "value", values)
    if kind == "Null" or kind == "SubProperty":
        return {}
    if kind == "Vector":
        return {"x": prop.x, "y": prop.y}
    return {"value": prop.value}


def mutate_img(
    data: bytes,
    operation: str,
    path: Sequence[str],
    *,
    name: Optional[str] = None,
    kind: Optional[str] = None,
    values: Optional[dict] = None,
    region: Optional[str] = None,
) -> MutationResult:
    layout = scan_img(data, region=region)
    reader = WzBinaryReader(io.BytesIO(data), WzKey.for_region(layout.region))
    path_tuple = tuple(path)
    values = values or {}
    edits: List[Tuple[int, int, bytes]] = []
    path_after: Optional[Tuple[str, ...]] = path_tuple

    if operation == "add":
        if not kind:
            raise ValueError("kind is required for add")
        if not name:
            raise ValueError("name is required for add")
        prop_list, ancestors = _find_list(layout.root, path_tuple)
        if any(record.name == name for record in prop_list.records):
            raise FileExistsError("/".join((*path_tuple, name)))
        prop = _construct_property(kind, name, values)
        record_bytes = _record_bytes(prop, reader)
        count_bytes = encode_compressed_int(prop_list.count + 1)
        count_delta = len(count_bytes) - (prop_list.count_end - prop_list.count_offset)
        delta = len(record_bytes) + count_delta
        edits.append((prop_list.end, prop_list.end, record_bytes))
        edits.append((prop_list.count_offset, prop_list.count_end, count_bytes))
        edits.extend(_size_edits(ancestors, delta))
        path_after = (*path_tuple, name)
    else:
        prop_list, record, ancestors = _find_record(layout.root, path_tuple)
        if operation == "remove":
            count_bytes = encode_compressed_int(prop_list.count - 1)
            count_delta = len(count_bytes) - (prop_list.count_end - prop_list.count_offset)
            delta = -(record.end - record.start) + count_delta
            edits.append((record.start, record.end, b""))
            edits.append((prop_list.count_offset, prop_list.count_end, count_bytes))
            edits.extend(_size_edits(ancestors, delta))
            path_after = None
        elif operation == "rename":
            if not name:
                raise ValueError("name is required for rename")
            if name != record.name and any(item.name == name for item in prop_list.records):
                raise FileExistsError("/".join((*path_tuple[:-1], name)))
            replacement = encode_string_block(reader, name) + data[record.tag_offset:record.end]
            delta = len(replacement) - (record.end - record.start)
            edits.append((record.start, record.end, replacement))
            edits.extend(_size_edits(ancestors, delta))
            path_after = (*path_tuple[:-1], name)
        elif operation == "edit":
            image = WzImage.from_bytes(data, key=WzKey.for_region(layout.region))
            image.parse()
            prop = image.root.get("/".join(path_tuple))
            if prop is None:
                raise KeyError("/".join(path_tuple))
            editable = {
                "Short", "Int", "Long", "Float", "Double", "String", "Vector", "UOL",
            }
            if prop.type_name not in editable:
                raise ValueError(f"{prop.type_name} properties have no editable value")
            replacement_prop = _construct_property(prop.type_name, prop.name, values)
            encoded = _record_bytes(replacement_prop, reader)
            encoded_name_end = len(encode_string_block(reader, prop.name))
            replacement = data[record.start:record.tag_offset] + encoded[encoded_name_end:]
            delta = len(replacement) - (record.end - record.start)
            edits.append((record.start, record.end, replacement))
            edits.extend(_size_edits(ancestors, delta))
        else:
            raise ValueError(f"unsupported operation: {operation}")

    edits.extend(_reference_edits(layout, edits))
    patched = _apply_edits(data, edits)
    verified = scan_img(patched, region=layout.region)
    image = WzImage.from_bytes(patched, key=WzKey.for_region(layout.region))
    image.parse()
    if image.truncated or image.parse_warnings:
        raise ValueError(
            "patched IMG failed verification: " + "; ".join(image.parse_warnings or ["truncated"])
        )
    if verified.root.count != len(verified.root.records):
        raise ValueError("patched IMG property count mismatch")
    return MutationResult(
        data=patched,
        region=layout.region,
        operation=operation,
        path_before=path_tuple,
        path_after=path_after,
        byte_delta=len(patched) - len(data),
    )
