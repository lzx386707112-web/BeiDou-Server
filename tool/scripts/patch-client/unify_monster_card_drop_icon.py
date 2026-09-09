#!/usr/bin/env python3
"""Use each monster card's drop icon in inventory, and make same cards stack."""

from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(ROOT / "tool/scripts/migration")]

import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzIntProperty  # noqa: E402
from wzpy.canvas import _read_canvas_bytes, decode_canvas  # noqa: E402
from wzpy.incremental_img import (  # noqa: E402
    _apply_edits,
    _find_record,
    _reference_edits,
    _size_edits,
    scan_img,
)
from wzpy.incremental_xml import _find_node, _replace_attr, mutate_xml, scan_xml  # noqa: E402
from wzpy.writer import encode_compressed_int  # noqa: E402


CLIENT_ITEM = ROOT / "clien/Data/Item/Consume/0238.img"
SERVER_ITEM = ROOT / "gms-server/wz/Item.wz/Consume/0238.img.xml"
SLOT_MAX = 100


def load_image(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=arc.GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"{path}: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    return image


def card_ids(image: WzImage) -> tuple[str, ...]:
    names = tuple(child.name for child in image.root.children())
    if not names or any(not name.startswith("0238") for name in names):
        raise RuntimeError("0238.img card list is unexpected")
    return names


def icon_matches_raw(icon: WzCanvasProperty, raw: WzCanvasProperty) -> bool:
    origin_icon = icon.get("origin")
    origin_raw = raw.get("origin")
    if origin_icon is None or origin_raw is None:
        return False
    return (
        (int(icon.width), int(icon.height), int(icon.format), int(icon.format2 or 0))
        == (int(raw.width), int(raw.height), int(raw.format), int(raw.format2 or 0))
        and (int(origin_icon.x), int(origin_icon.y)) == (int(origin_raw.x), int(origin_raw.y))
        and _read_canvas_bytes(icon) == _read_canvas_bytes(raw)
    )


def patch_client(data: bytes) -> bytes:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=CLIENT_ITEM.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"client 0238.img is truncated: {image.parse_warnings}")
    names = card_ids(image)
    layout = scan_img(data, region="GMS")
    edits: list[tuple[int, int, bytes]] = []

    for name in names:
        card = image.root.get(name)
        icon = card.get("info/icon")
        raw = card.get("info/iconRaw")
        only = card.get("info/only")
        if not isinstance(icon, WzCanvasProperty) or not isinstance(raw, WzCanvasProperty):
            raise RuntimeError(f"{name} missing icon canvases")
        if only is None:
            raise RuntimeError(f"{name} missing only")

        _, icon_rec, icon_anc = _find_record(layout.root, (name, "info", "icon"))
        _, raw_rec, _ = _find_record(layout.root, (name, "info", "iconRaw"))
        _, origin_rec, _ = _find_record(layout.root, (name, "info", "icon", "origin"))
        origin = icon.get("origin")
        raw_origin = raw.get("origin")
        if origin is None or raw_origin is None or icon_rec.children is None or raw_rec.children is None:
            raise RuntimeError(f"{name} missing canvas origin")
        if icon_rec.size_offset is None or icon_rec.block_size is None:
            raise RuntimeError(f"{name} icon has no block size")

        _, only_rec, _ = _find_record(layout.root, (name, "info", "only"))
        if int(only.value) != 0:
            if data[only_rec.end - 1] != 1:
                raise RuntimeError(f"{name} cannot patch only in place")
            edits.append((only_rec.end - 1, only_rec.end, b"\x00"))

        if not icon_matches_raw(icon, raw):
            old_x, old_y = int(origin.x), int(origin.y)
            new_x, new_y = int(raw_origin.x), int(raw_origin.y)
            if encode_compressed_int(old_x) + encode_compressed_int(old_y) != data[origin_rec.end - 2:origin_rec.end]:
                raise RuntimeError(f"{name} origin encoding is not a trailing xy pair")
            if len(encode_compressed_int(new_x)) != 1 or len(encode_compressed_int(new_y)) != 1:
                raise RuntimeError(f"{name} origin cannot stay same-length")
            edits.append((origin_rec.end - 2, origin_rec.end, encode_compressed_int(new_x) + encode_compressed_int(new_y)))
            new_tail = data[raw_rec.children.end:raw_rec.end]
            old_start, old_end = icon_rec.children.end, icon_rec.end
            delta = len(new_tail) - (old_end - old_start)
            edits.append((old_start, old_end, new_tail))
            edits.append((
                icon_rec.size_offset,
                icon_rec.size_offset + 4,
                struct.pack("<I", icon_rec.block_size + delta),
            ))
            edits.extend(_size_edits(icon_anc, delta))

    if edits:
        edits.extend(_reference_edits(layout, edits))
        data = _apply_edits(data, edits)
        data = arc.verified_image_bytes(data, CLIENT_ITEM.name)
    return data


def patch_xml_canvas_size(text: str, path: tuple[str, ...], width: int, height: int) -> str:
    root = scan_xml(text)
    node = _find_node(root, path)
    token = text[node.start:node.start_end]
    token = _replace_attr(token, "width", str(width))
    token = _replace_attr(token, "height", str(height))
    result = text[:node.start] + token + text[node.start_end:]
    scan_xml(result)
    return result


def xml_int(parent, name: str) -> int | None:
    child = next((item for item in parent if item.get("name") == name), None)
    if child is None:
        return None
    return int(child.get("value"))


def xml_canvas(parent, name: str):
    return next((item for item in parent if item.tag == "canvas" and item.get("name") == name), None)


def patch_server_xml(text: str) -> str:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(text)
    cards = [child for child in root if child.tag == "imgdir" and child.get("name", "").startswith("0238")]
    if not cards:
        raise RuntimeError("server 0238.img.xml has no monster cards")
    patched = text
    for card in cards:
        name = card.get("name")
        info = next(child for child in card if child.get("name") == "info")
        icon = xml_canvas(info, "icon")
        raw = xml_canvas(info, "iconRaw")
        if icon is None or raw is None:
            raise RuntimeError(f"{name} XML missing canvases")
        origin = next(child for child in raw if child.get("name") == "origin")
        width, height = int(raw.get("width")), int(raw.get("height"))
        ox, oy = int(origin.get("x")), int(origin.get("y"))
        if (int(icon.get("width")), int(icon.get("height"))) != (width, height):
            patched = patch_xml_canvas_size(patched, (name, "info", "icon"), width, height)
        icon_origin = next(child for child in icon if child.get("name") == "origin")
        if (int(icon_origin.get("x")), int(icon_origin.get("y"))) != (ox, oy):
            patched = mutate_xml(
                patched,
                "edit",
                (name, "info", "icon", "origin"),
                values={"x": ox, "y": oy},
            )
        if xml_int(info, "only") != 0:
            patched = mutate_xml(patched, "edit", (name, "info", "only"), values={"value": 0})
        slot = xml_int(info, "slotMax")
        if slot is None:
            patched = arc.append_xml_properties(
                patched, (name, "info"), [WzIntProperty("slotMax", SLOT_MAX)]
            )
        elif slot != SLOT_MAX:
            patched = mutate_xml(
                patched, "edit", (name, "info", "slotMax"), values={"value": SLOT_MAX}
            )
    return patched


def scalar_info(card) -> dict[str, int]:
    values = {}
    for name in ("price", "tradeBlock", "bigSize", "monsterBook", "mob"):
        node = card.get(f"info/{name}")
        if node is None:
            raise RuntimeError(f"{card.name} missing {name}")
        values[name] = int(node.value)
    return values


def canvas_hash(canvas: WzCanvasProperty) -> str:
    decoded = decode_canvas(canvas, region="GMS").convert("RGBA")
    if decoded.getchannel("A").getbbox() is None:
        raise RuntimeError(f"{canvas.name} has no visible pixels")
    return hashlib.sha256(decoded.tobytes()).hexdigest()


def verify_client(data: bytes, before: bytes, names: tuple[str, ...]) -> None:
    before_image = WzImage.from_bytes(before, key=arc.GMS_KEY, name=CLIENT_ITEM.name)
    before_image.parse()
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=CLIENT_ITEM.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"patched 0238.img failed parse: {image.parse_warnings}")
    if tuple(child.name for child in image.root.children()) != names:
        raise RuntimeError("monster card sibling order changed")
    before_order, after_order = arc.raw_record_state(before)[1], arc.raw_record_state(data)[1]
    if before_order[()] != after_order[()]:
        raise RuntimeError("top-level IMG order changed")
    for name in names:
        before_card = before_image.root.get(name)
        card = image.root.get(name)
        icon = card.get("info/icon")
        raw = card.get("info/iconRaw")
        before_raw = before_card.get("info/iconRaw")
        if not isinstance(icon, WzCanvasProperty) or not isinstance(raw, WzCanvasProperty):
            raise RuntimeError(f"{name} missing canvases after patch")
        if (int(icon.format), int(icon.format2 or 0), int(raw.format), int(raw.format2 or 0)) != (1, 0, 1, 0):
            raise RuntimeError(f"{name} canvas format is not 1/0")
        if canvas_hash(raw) != canvas_hash(before_raw):
            raise RuntimeError(f"{name} drop icon pixels changed")
        if not icon_matches_raw(icon, raw):
            raise RuntimeError(f"{name} inventory icon does not match drop icon")
        if int(card.get("info/only").value) != 0:
            raise RuntimeError(f"{name} only is not 0")
        if scalar_info(card) != scalar_info(before_card):
            raise RuntimeError(f"{name} unrelated info scalars changed")
        before_info = tuple(child.name for child in before_card.get("info").children())
        after_info = tuple(child.name for child in card.get("info").children())
        if before_info != after_info:
            raise RuntimeError(f"{name} info siblings changed: {before_info} -> {after_info}")


def verify_server_xml(text: str, names: tuple[str, ...]) -> None:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(text)
    xml_names = tuple(
        child.get("name") for child in root if child.tag == "imgdir" and child.get("name", "").startswith("0238")
    )
    if xml_names != names:
        raise RuntimeError("server XML card order or set mismatch")
    for name in names:
        card = next(child for child in root if child.get("name") == name)
        info = next(child for child in card if child.get("name") == "info")
        icon = xml_canvas(info, "icon")
        raw = xml_canvas(info, "iconRaw")
        origin = next(child for child in icon if child.get("name") == "origin")
        raw_origin = next(child for child in raw if child.get("name") == "origin")
        if (icon.get("width"), icon.get("height")) != (raw.get("width"), raw.get("height")):
            raise RuntimeError(f"{name} XML icon size still differs")
        if (origin.get("x"), origin.get("y")) != (raw_origin.get("x"), raw_origin.get("y")):
            raise RuntimeError(f"{name} XML icon origin still differs")
        if xml_int(info, "only") != 0 or xml_int(info, "slotMax") != SLOT_MAX:
            raise RuntimeError(f"{name} XML stack flags mismatch")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build() -> dict[Path, bytes]:
    before = CLIENT_ITEM.read_bytes()
    names = card_ids(load_image(CLIENT_ITEM))
    client = patch_client(before)
    verify_client(client, before, names)
    xml_before = SERVER_ITEM.read_text(encoding="utf-8")
    xml = patch_server_xml(xml_before)
    verify_server_xml(xml, names)
    return {
        CLIENT_ITEM: client,
        SERVER_ITEM: xml.encode("utf-8"),
    }


def main() -> None:
    payloads = build()
    for path, data in payloads.items():
        if path.suffix == ".xml":
            arc.atomic_write_text(path, data.decode("utf-8"))
        else:
            arc.atomic_write_bytes(path, data)
    again = build()
    for path, data in payloads.items():
        if sha256(path.read_bytes()) != sha256(data) or sha256(again[path]) != sha256(data):
            raise RuntimeError(f"generator is not idempotent: {path}")
    print(
        "unified 0238 monster-card inventory icons with drop icons "
        f"and set only=0 for {len(card_ids(load_image(CLIENT_ITEM)))} cards; server XML slotMax={SLOT_MAX}"
    )


if __name__ == "__main__":
    main()
