#!/usr/bin/env python3
"""Give shield 1092065 the green-flame appearance of weapon 1302107.

Use 1342053, a proven old-client Si-slot secondary blade, as the hand-position
and z-order analogue. Only the target's action tail is replaced.
"""

from __future__ import annotations

import colorsys
import hashlib
import importlib.util
import io
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image


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
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.incremental_img import _record_bytes, scan_img  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402


TARGET_IMG = ROOT / "clien/Data/Character/Shield/01092065.img"
SOURCE_IMG = ROOT / "clien/Data/Character/Weapon/01302107.img"
REFERENCE_IMG = ROOT / "clien/Data/Character/Weapon/01342053.img"
BODY_IMG = ROOT / "clien/Data/Character/00002000.img"
TARGET_XML = ROOT / "gms-server/wz/Character.wz/Shield/01092065.img.xml"

TARGET_INFO_RECORD_SHA256 = "458ff77fadfb75fe989eaa485892af4eda52a9b12643bd43471028b69572e61b"
SOURCE_SHA256 = "f62cc3a100b0b34a9b76a321af06a915d475b0cf6ddc0cc3275069943eb52ed5"
REFERENCE_SHA256 = "cc1461c55c7b6ff4e06e1dd60e4b7b530ce795450db640e734d25e06fd0bd0fc"
BODY_SHA256 = "c0e140e0ab828655f4a94a0f69acb328a249480a41e837e195ced8a7d59f7b4b"

ACTION_ROOTS = (
    "walk1",
    "stand1",
    "alert",
    "swingO1",
    "swingO2",
    "swingO3",
    "swingOF",
    "stabO1",
    "stabO2",
    "stabOF",
    "proneStab",
    "prone",
    "heal",
    "fly",
    "jump",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_image(data: bytes, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"malformed {name}: truncated={image.truncated}, warnings={image.parse_warnings}"
        )
    return image


def green_flame(bitmap: Image.Image) -> Image.Image:
    """Shift saturated cyan/blue flame pixels to green, preserving luminosity."""
    output = bitmap.convert("RGBA").copy()
    pixels = output.load()
    for y in range(output.height):
        for x in range(output.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0:
                continue
            hue, saturation, value = colorsys.rgb_to_hsv(
                red / 255.0, green / 255.0, blue / 255.0
            )
            if 0.44 <= hue <= 0.67 and saturation >= 0.12:
                # Retain the source flame's saturation and brightness. White
                # cores stay white, while cyan/blue glow becomes vivid green.
                red_f, green_f, blue_f = colorsys.hsv_to_rgb(
                    1.0 / 3.0, saturation, value
                )
                pixels[x, y] = (
                    round(red_f * 255),
                    round(green_f * 255),
                    round(blue_f * 255),
                    alpha,
                )
    return output


def hilt_pixels(bitmap: Image.Image) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    for y in range(bitmap.height):
        for x in range(bitmap.width):
            red, green, blue, alpha = bitmap.getpixel((x, y))
            if alpha < 96:
                continue
            hue, saturation, value = colorsys.rgb_to_hsv(
                red / 255.0, green / 255.0, blue / 255.0
            )
            if 0.07 <= hue <= 0.19 and saturation >= 0.35 and value >= 0.25:
                points.append((x, y))
    return points


def center(points: list[tuple[int, int]]) -> tuple[float, float] | None:
    if not points:
        return None
    return (
        sum(x for x, _ in points) / len(points),
        sum(y for _, y in points) / len(points),
    )


def vector(canvas: WzCanvasProperty, name: str) -> tuple[int, int]:
    node = canvas.child(name)
    if not isinstance(node, WzVectorProperty):
        raise RuntimeError(f"{canvas.name}: missing vector {name}")
    return int(node.x), int(node.y)


def resolve_uol(node):
    seen: set[int] = set()
    current = node
    for _ in range(16):
        if not isinstance(current, WzUolProperty):
            return current
        if id(current) in seen or current.parent is None:
            raise RuntimeError("cyclic or detached UOL")
        seen.add(id(current))
        current = current.parent.get(str(current.value))
    raise RuntimeError("UOL chain is too deep")


def map_vector(canvas: WzCanvasProperty, name: str) -> tuple[int, int] | None:
    map_node = canvas.child("map")
    if not isinstance(map_node, WzSubProperty):
        return None
    point = map_node.child(name)
    if not isinstance(point, WzVectorProperty):
        return None
    return int(point.x), int(point.y)


def body_hand_offset(body: WzImage, action: str, frame_name: str) -> tuple[int, int]:
    frame = body.root.get(f"{action}/{frame_name}")
    if not isinstance(frame, WzSubProperty):
        raise RuntimeError(f"body is missing {action}/{frame_name}")
    for child in frame.children():
        if not isinstance(child, WzCanvasProperty):
            continue
        hand = map_vector(child, "hand")
        navel = map_vector(child, "navel")
        if hand is not None and navel is not None:
            return hand[0] - navel[0], hand[1] - navel[1]
    raise RuntimeError(f"body is missing a hand anchor at {action}/{frame_name}")


def source_hand_anchor(
    canvas: WzCanvasProperty,
    body: WzImage,
    action: str,
    frame_name: str,
) -> tuple[int, int]:
    origin = vector(canvas, "origin")
    hand = map_vector(canvas, "hand")
    if hand is not None:
        return origin[0] + hand[0], origin[1] + hand[1]
    navel = map_vector(canvas, "navel")
    if navel is None:
        raise RuntimeError(f"1302107 has no hand/navel anchor at {action}/{frame_name}")
    hand_world = body_hand_offset(body, action, frame_name)
    return (
        origin[0] + navel[0] + hand_world[0],
        origin[1] + navel[1] + hand_world[1],
    )


def exact_canvas(image: WzImage, action: str, frame_name: str, leaf: str):
    frame = image.root.get(f"{action}/{frame_name}")
    if not isinstance(frame, WzSubProperty):
        return None
    return resolve_uol(frame.child(leaf))


def nearest(mapping: dict[int, object], frame_name: str):
    if not mapping:
        raise RuntimeError("no compatible reference frames")
    frame = int(frame_name)
    key = min(mapping, key=lambda candidate: (abs(candidate - frame), candidate))
    return mapping[key]


def action_position_shifts(
    action: str,
    source: WzImage,
    reference: WzImage,
    body: WzImage,
) -> dict[int, tuple[float, float]]:
    source_action = source.root.child(action)
    if not isinstance(source_action, WzSubProperty):
        raise RuntimeError(f"1302107 is missing {action}")
    shifts: dict[int, tuple[float, float]] = {}
    concrete_frames = 0
    for frame in source_action.children():
        source_canvas = frame.child("weapon")
        if not isinstance(source_canvas, WzCanvasProperty):
            continue
        concrete_frames += 1
        reference_canvas = exact_canvas(reference, action, frame.name, "weapon")
        if not isinstance(reference_canvas, WzCanvasProperty):
            continue
        source_hilt = center(
            hilt_pixels(decode_canvas(source_canvas, region="GMS").convert("RGBA"))
        )
        reference_hilt = center(
            hilt_pixels(decode_canvas(reference_canvas, region="GMS").convert("RGBA"))
        )
        if source_hilt is None or reference_hilt is None:
            continue
        source_anchor = source_hand_anchor(source_canvas, body, action, frame.name)
        reference_origin = vector(reference_canvas, "origin")
        source_hilt_world = (
            source_hilt[0] - source_anchor[0],
            source_hilt[1] - source_anchor[1],
        )
        reference_hilt_world = (
            reference_hilt[0] - reference_origin[0],
            reference_hilt[1] - reference_origin[1],
        )
        shifts[int(frame.name)] = (
            reference_hilt_world[0] - source_hilt_world[0],
            reference_hilt_world[1] - source_hilt_world[1],
        )
    if concrete_frames and not shifts:
        raise RuntimeError(f"1342053 has no usable hilt reference for {action}")
    return shifts


def reference_z(reference: WzImage, action: str, frame_name: str) -> str:
    values: dict[int, str] = {}
    action_node = reference.root.child(action)
    if not isinstance(action_node, WzSubProperty):
        raise RuntimeError(f"1342053 is missing {action}")
    for frame in action_node.children():
        canvas = exact_canvas(reference, action, frame.name, "weapon")
        if not isinstance(canvas, WzCanvasProperty):
            continue
        z = canvas.child("z")
        if isinstance(z, WzStringProperty):
            values[int(frame.name)] = str(z.value)
    return str(nearest(values, frame_name))


def replacement_canvas(
    source_canvas: WzCanvasProperty,
    body: WzImage,
    reference: WzImage,
    action: str,
    frame_name: str,
    shifts: dict[int, tuple[float, float]],
) -> WzCanvasProperty:
    bitmap = green_flame(decode_canvas(source_canvas, region="GMS"))
    source_anchor = source_hand_anchor(source_canvas, body, action, frame_name)
    shift = nearest(shifts, frame_name)
    assert isinstance(shift, tuple)
    origin = (
        round(source_anchor[0] - shift[0]),
        round(source_anchor[1] - shift[1]),
    )
    output = WzCanvasProperty("shield")
    output.width, output.height = bitmap.size
    output.format, output.format2 = 1, 0
    output._png_data = encode_canvas_payload(
        bitmap,
        1,
        bitmap.width,
        bitmap.height,
        key=arc.GMS_KEY,
        listwz=False,
        zlib_level=6,
    )
    output._png_length = len(output._png_data)
    output._png_offset = 0
    output.add(WzVectorProperty("origin", origin[0], origin[1], output))
    map_node = WzSubProperty("map", output)
    map_node.add(WzVectorProperty("hand", 0, 0, map_node))
    output.add(map_node)
    output.add(WzStringProperty("z", reference_z(reference, action, frame_name), output))
    return output


def build_action(
    action: str,
    source_image: WzImage,
    reference_image: WzImage,
    body_image: WzImage,
) -> WzSubProperty:
    source_action = source_image.root.child(action)
    if not isinstance(source_action, WzSubProperty):
        raise RuntimeError(f"missing action {action}")
    shifts = action_position_shifts(action, source_image, reference_image, body_image)
    output = WzSubProperty(action)
    for source_frame in source_action.children():
        if not isinstance(source_frame, WzSubProperty):
            raise RuntimeError(f"invalid frame {action}/{source_frame.name}")
        source_visual = source_frame.child("weapon")
        frame = WzSubProperty(source_frame.name, output)
        if isinstance(source_visual, WzUolProperty):
            value = str(source_visual.value).replace("weapon", "shield")
            frame.add(WzUolProperty("shield", value, frame))
        elif isinstance(source_visual, WzCanvasProperty):
            frame.add(
                replacement_canvas(
                    source_visual,
                    body_image,
                    reference_image,
                    action,
                    source_frame.name,
                    shifts,
                )
            )
        else:
            raise RuntimeError(
                f"unsupported source visual at {action}/{source_frame.name}: "
                f"{type(source_visual).__name__}"
            )
        output.add(frame)
    return output


def approved_roots() -> set[tuple[str, ...]]:
    return {(action,) for action in ACTION_ROOTS}


def verify_action_tail_scope(before: bytes, after: bytes) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)
    approved = approved_roots()

    def allowed(path: tuple[str, ...]) -> bool:
        return any(path[: len(root)] == root for root in approved)

    changed = {
        path
        for path in set(before_records) | set(after_records)
        if before_records.get(path) != after_records.get(path)
    }
    protected = sorted(path for path in changed if not allowed(path))
    if protected:
        raise RuntimeError(f"hand-position patch changed protected records: {protected}")
    if before_orders[()] != after_orders[()]:
        raise RuntimeError("hand-position patch changed top-level record order")
    if before_records[("info",)] != after_records[("info",)]:
        raise RuntimeError("hand-position patch changed the info record")


def build_client(
    baseline: bytes,
    source_data: bytes,
    reference_data: bytes,
    body_data: bytes,
) -> bytes:
    target = load_image(baseline, TARGET_IMG.name)
    source = load_image(source_data, SOURCE_IMG.name)
    reference = load_image(reference_data, REFERENCE_IMG.name)
    body = load_image(body_data, BODY_IMG.name)
    if [child.name for child in target.root.children()] != ["info", *ACTION_ROOTS]:
        raise RuntimeError("unexpected 1092065 top-level record order")
    target_records, _ = arc.raw_record_state(baseline)
    if digest(target_records[("info",)]) != TARGET_INFO_RECORD_SHA256:
        raise RuntimeError("1092065 info record differs from the proven baseline")
    if [child.name for child in source.root.children()] != ["info", *ACTION_ROOTS]:
        raise RuntimeError("unexpected 1302107 top-level record order")
    reference_info = reference.root.child("info")
    if not isinstance(reference_info, WzSubProperty):
        raise RuntimeError("1342053 is missing info")
    for name in ("islot", "vslot"):
        value = reference_info.child(name)
        if not isinstance(value, WzStringProperty) or value.value != "Si":
            raise RuntimeError(f"1342053 is not a proven Si-slot reference: {name}")

    layout = scan_img(baseline, region="GMS")
    records = {record.name: record for record in layout.root.records}
    first = records[ACTION_ROOTS[0]].start
    last = records[ACTION_ROOTS[-1]].end
    replaced_names = tuple(record.name for record in layout.root.records[1:])
    if replaced_names != ACTION_ROOTS or last != len(baseline):
        raise RuntimeError("1092065 action records are not one continuous tail")
    crossing = [
        reference
        for reference in layout.string_references
        if reference.field_offset < first <= reference.target_offset < last
    ]
    if crossing:
        raise RuntimeError("1092065 info record references strings inside the action tail")

    reader = WzBinaryReader(io.BytesIO(baseline), arc.GMS_KEY)
    action_bytes = b"".join(
        _record_bytes(build_action(action, source, reference, body), reader)
        for action in ACTION_ROOTS
    )
    updated = baseline[:first] + action_bytes
    load_image(updated, TARGET_IMG.name)
    verify_action_tail_scope(baseline, updated)
    return updated


def validate_client(
    data: bytes,
    source_data: bytes,
    reference_data: bytes,
    body_data: bytes,
) -> None:
    image = load_image(data, TARGET_IMG.name)
    source = load_image(source_data, SOURCE_IMG.name)
    reference = load_image(reference_data, REFERENCE_IMG.name)
    body = load_image(body_data, BODY_IMG.name)
    visible = 0
    green_pixels = 0
    for action in ACTION_ROOTS:
        target_action = image.root.child(action)
        source_action = source.root.child(action)
        assert isinstance(target_action, WzSubProperty)
        assert isinstance(source_action, WzSubProperty)
        if [frame.name for frame in target_action.children()] != [
            frame.name for frame in source_action.children()
        ]:
            raise RuntimeError(f"1092065 frame order differs from 1302107 at {action}")
        shifts = action_position_shifts(action, source, reference, body)
        for target_frame, source_frame in zip(
            target_action.children(), source_action.children()
        ):
            visual = target_frame.child("shield")
            source_visual = source_frame.child("weapon")
            if isinstance(source_visual, WzUolProperty):
                expected_value = str(source_visual.value).replace("weapon", "shield")
                if not isinstance(visual, WzUolProperty) or visual.value != expected_value:
                    raise RuntimeError(f"{action}/{target_frame.name}: UOL mismatch")
                continue
            if not isinstance(source_visual, WzCanvasProperty) or not isinstance(
                visual, WzCanvasProperty
            ):
                raise RuntimeError(f"{action}/{target_frame.name}: missing shield Canvas")
            if (visual.format, visual.format2) != (1, 0):
                raise RuntimeError(f"{action}/{target_frame.name}: not GMS ARGB4444")
            bitmap = decode_canvas(visual, region="GMS").convert("RGBA")
            if bitmap.getbbox() is None:
                raise RuntimeError(f"{action}/{target_frame.name}: invisible Canvas")
            expected = replacement_canvas(
                source_visual,
                body,
                reference,
                action,
                source_frame.name,
                shifts,
            )
            expected_bitmap = decode_canvas(expected, region="GMS").convert("RGBA")
            if bitmap.size != expected_bitmap.size or bitmap.tobytes() != expected_bitmap.tobytes():
                raise RuntimeError(
                    f"{action}/{target_frame.name}: pixels differ from recolored 1302107"
                )
            if vector(visual, "origin") != vector(expected, "origin"):
                raise RuntimeError(f"{action}/{target_frame.name}: hand-position origin mismatch")
            if map_vector(visual, "hand") != (0, 0) or map_vector(visual, "navel") is not None:
                raise RuntimeError(f"{action}/{target_frame.name}: not hand-anchored")
            z = visual.child("z")
            expected_z = expected.child("z")
            if not isinstance(z, WzStringProperty) or not isinstance(
                expected_z, WzStringProperty
            ) or z.value != expected_z.value:
                raise RuntimeError(f"{action}/{target_frame.name}: 1342053 z-order mismatch")
            visible += 1
            for red, green, blue, alpha in bitmap.getdata():
                if alpha >= 32 and green > red * 1.15 and green > blue * 1.10:
                    green_pixels += 1
    if visible != 33:
        raise RuntimeError(f"expected 33 concrete action canvases, got {visible}")
    if green_pixels < 5000:
        raise RuntimeError(f"green flame conversion is too weak: {green_pixels} pixels")


def action_xml_blocks(data: bytes) -> dict[str, str]:
    image = load_image(data, TARGET_IMG.name)
    return {
        action: arc.property_to_xml(image.root.child(action), 1)
        for action in ACTION_ROOTS
    }


def replace_xml_actions(baseline: str, data: bytes) -> str:
    result = baseline
    layout = arc.scan_xml(result)
    for action, replacement in action_xml_blocks(data).items():
        current = next((node for node in layout.children if node.name == action), None)
        if current is None:
            raise RuntimeError(f"XML is missing action {action}")
        line_start = result.rfind("\n", 0, current.start) + 1
        result = result[:line_start] + replacement + result[current.end:]
        layout = arc.scan_xml(result)
    ET.fromstring(result)
    return result


def validate_xml(text: str, data: bytes) -> None:
    root = ET.fromstring(text)
    image = load_image(data, TARGET_IMG.name)
    names = [child.attrib.get("name") for child in root]
    if names != ["info", *ACTION_ROOTS]:
        raise RuntimeError("server XML top-level order changed")
    for action in ACTION_ROOTS:
        xml_action = next(child for child in root if child.attrib.get("name") == action)
        client_action = image.root.child(action)
        assert isinstance(client_action, WzSubProperty)
        if [child.attrib.get("name") for child in xml_action] != [
            child.name for child in client_action.children()
        ]:
            raise RuntimeError(f"server XML frame mismatch for {action}")
        for xml_frame, client_frame in zip(xml_action, client_action.children()):
            client_visual = client_frame.child("shield")
            xml_visual = next(
                (child for child in xml_frame if child.attrib.get("name") == "shield"),
                None,
            )
            if xml_visual is None:
                raise RuntimeError(f"server XML missing {action}/{client_frame.name}/shield")
            if isinstance(client_visual, WzUolProperty):
                if xml_visual.tag != "uol" or xml_visual.attrib.get("value") != str(
                    client_visual.value
                ):
                    raise RuntimeError(f"server XML UOL mismatch at {action}/{client_frame.name}")
                continue
            if not isinstance(client_visual, WzCanvasProperty) or xml_visual.tag != "canvas":
                raise RuntimeError(f"server XML Canvas mismatch at {action}/{client_frame.name}")
            expected_attrs = {
                "name": "shield",
                "width": str(client_visual.width),
                "height": str(client_visual.height),
                "format": "1",
            }
            if xml_visual.attrib != expected_attrs:
                raise RuntimeError(f"server XML Canvas attrs mismatch at {action}/{client_frame.name}")
            xml_origin = next(child for child in xml_visual if child.attrib.get("name") == "origin")
            origin = vector(client_visual, "origin")
            if (xml_origin.attrib.get("x"), xml_origin.attrib.get("y")) != (
                str(origin[0]),
                str(origin[1]),
            ):
                raise RuntimeError(f"server XML origin mismatch at {action}/{client_frame.name}")
            xml_map = next(child for child in xml_visual if child.attrib.get("name") == "map")
            xml_points = {
                child.attrib.get("name"): (
                    child.attrib.get("x"),
                    child.attrib.get("y"),
                )
                for child in xml_map
            }
            if xml_points != {"hand": ("0", "0")}:
                raise RuntimeError(f"server XML hand anchor mismatch at {action}/{client_frame.name}")
            client_z = client_visual.child("z")
            xml_z = next(child for child in xml_visual if child.attrib.get("name") == "z")
            if not isinstance(client_z, WzStringProperty) or xml_z.attrib.get("value") != str(
                client_z.value
            ):
                raise RuntimeError(f"server XML z-order mismatch at {action}/{client_frame.name}")


def main() -> None:
    target_data = TARGET_IMG.read_bytes()
    source_data = SOURCE_IMG.read_bytes()
    reference_data = REFERENCE_IMG.read_bytes()
    body_data = BODY_IMG.read_bytes()
    xml_text = TARGET_XML.read_text(encoding="utf-8")

    source_hash = digest(source_data)
    if source_hash != SOURCE_SHA256:
        raise RuntimeError(f"1302107 source changed: {source_hash}")
    if digest(reference_data) != REFERENCE_SHA256:
        raise RuntimeError("1342053 reference changed")
    if digest(body_data) != BODY_SHA256:
        raise RuntimeError("00002000 body anchor reference changed")

    updated = build_client(target_data, source_data, reference_data, body_data)
    updated_xml = replace_xml_actions(xml_text, updated)

    validate_client(updated, source_data, reference_data, body_data)
    validate_xml(updated_xml, updated)
    arc.atomic_write_bytes(TARGET_IMG, updated)
    arc.atomic_write_text(TARGET_XML, updated_xml)
    print(f"client_sha256={digest(updated)}")
    print(f"server_xml_sha256={digest(updated_xml.encode('utf-8'))}")


if __name__ == "__main__":
    main()
