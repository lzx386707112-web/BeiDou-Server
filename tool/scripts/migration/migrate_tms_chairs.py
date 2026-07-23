#!/usr/bin/env python3
"""Replace existing chairs with same-ID TMS resources for the legacy client.

The fishing chair (3011000) is preserved from the current client. Existing
chairs without a same-ID TMS node are removed. Modern ``_outlink`` canvases
are materialized, and every output canvas is encoded as ARGB4444.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
import zlib
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import quoteattr


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.canvas import (  # noqa: E402
    _decompress,
    _read_canvas_bytes,
    decode_canvas,
    encode_canvas_payload,
)
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
from wzpy.writer import encode_image_body_compact  # noqa: E402


TMS = Path("/Users/lizixian/Documents/mxd/TMS")
TMS_DATA = TMS / "MapleStory-IMG/Data"
TMS_INSTALL = TMS_DATA / "Item/Install"
TMS_TAMING = TMS_DATA / "Character/TamingMob"
CHAIRS_CSV = TMS / "chair-preview/chairs.csv"

CLIENT_INSTALL = ROOT / "clien/Data/Item/Install/0301.img"
CLIENT_STRING = ROOT / "clien/Data/String/Ins.img"
CLIENT_TAMING = ROOT / "clien/Data/Character/TamingMob"
SERVER_INSTALL = ROOT / "gms-server/wz/Item.wz/Install/0301.img.xml"
SERVER_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Ins.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Ins.img.xml",
)
SERVER_TAMING = ROOT / "gms-server/wz/Character.wz/TamingMob"

BMS_KEY = WzKey.for_region("BMS")
GMS_KEY = WzKey.for_region("GMS")
FISHING_CHAIR = 3011000
EXPECTED_CURRENT = 606
EXPECTED_FINAL = 427
EXPECTED_MIGRATED = 426
EXPECTED_DELETED = 179
EXPECTED_TAMING = 55
EXPECTED_CSV_MIGRATED = 416


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(data)
        temp = Path(handle.name)
    temp.replace(path)


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), GMS_KEY)


def load_image(path: Path, key: WzKey) -> WzImage:
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


def item_id(node) -> int | None:
    return int(node.name) if node.name.isdigit() else None


class CanvasMaterializer:
    def __init__(self, source_dir: Path, outlink_prefix: str):
        self.source_dir = source_dir
        self.outlink_prefix = outlink_prefix.rstrip("/") + "/"
        self.linked_images: dict[str, WzImage] = {}
        self.payloads: dict[str, tuple[int, int, bytes]] = {}
        self.canvases = 0
        self.outlinks = 0
        self.converted = 0

    def linked_canvas(self, value: str) -> WzCanvasProperty:
        normalized = value.replace("\\", "/")
        if not normalized.startswith(self.outlink_prefix):
            raise RuntimeError(f"unsupported outlink: {value}")
        relative = normalized[len(self.outlink_prefix) :]
        file_name, separator, property_path = relative.partition("/")
        if not separator or not file_name.endswith(".img"):
            raise RuntimeError(f"invalid outlink: {value}")
        image = self.linked_images.get(file_name)
        if image is None:
            image = load_image(self.source_dir / "_Canvas" / file_name, BMS_KEY)
            self.linked_images[file_name] = image
        canvas = image.root.get(property_path)
        if not isinstance(canvas, WzCanvasProperty) or not canvas.has_pixels():
            raise RuntimeError(f"unresolved outlink: {value}")
        return canvas

    def argb4444(self, canvas: WzCanvasProperty) -> tuple[int, int, bytes]:
        width = int(canvas.width)
        height = int(canvas.height)
        if width <= 0 or height <= 0 or not canvas.has_pixels():
            raise RuntimeError(f"invalid canvas {canvas.name}: {width}x{height}")
        fmt = int(canvas.format) + int(canvas.format2)
        if fmt == 1:
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
        out = WzCanvasProperty(source.name, parent)
        out.width = width
        out.height = height
        out.format = 1
        out.format2 = 0
        out._png_data = payload
        out._png_length = len(payload)
        out._png_offset = 0
        for child in source.children():
            if child.name == "_outlink":
                continue
            out.add(clone_property(child, out, self))
        return out


def clone_property(source, parent, materializer: CanvasMaterializer):
    if isinstance(source, WzCanvasProperty):
        return materializer.clone_canvas(source, parent)
    if isinstance(source, WzSubProperty):
        out = WzSubProperty(source.name, parent)
        for child in source.children():
            out.add(clone_property(child, out, materializer))
        return out
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
        out = WzConvexProperty(source.name, parent)
        out.points = [
            WzVectorProperty(point.name, int(point.x), int(point.y), out)
            for point in source.points
        ]
        return out
    raise TypeError(f"unsupported WZ node: {type(source).__name__}")


def clone_current(source, parent):
    if isinstance(source, WzCanvasProperty):
        out = WzCanvasProperty(source.name, parent)
        out.width = int(source.width)
        out.height = int(source.height)
        out.format = int(source.format)
        out.format2 = int(source.format2)
        out._png_data = _read_canvas_bytes(source)
        out._png_length = len(out._png_data)
        for child in source.children():
            out.add(clone_current(child, out))
        return out
    if isinstance(source, WzSubProperty):
        out = WzSubProperty(source.name, parent)
        for child in source.children():
            out.add(clone_current(child, out))
        return out
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
        out = WzConvexProperty(source.name, parent)
        out.points = [
            WzVectorProperty(point.name, int(point.x), int(point.y), out)
            for point in source.points
        ]
        return out
    raise TypeError(f"unsupported current WZ node: {type(source).__name__}")


def load_source_chairs() -> tuple[dict[int, object], list[WzImage]]:
    chairs: dict[int, object] = {}
    images: list[WzImage] = []
    for path in sorted(TMS_INSTALL.glob("0301*.img")):
        image = load_image(path, BMS_KEY)
        images.append(image)
        for node in image.root.children():
            node_id = item_id(node)
            if node_id is not None:
                chairs[node_id] = node
    return chairs, images


def csv_strings() -> dict[int, tuple[str, str]]:
    with CHAIRS_CSV.open(encoding="utf-8-sig", newline="") as handle:
        return {
            int(row["id"]): (row["name"], row["desc"])
            for row in csv.DictReader(handle)
        }


def patch_client_strings(
    current_ids: set[int],
    final_ids: set[int],
    migrated_ids: set[int],
    names: dict[int, tuple[str, str]],
) -> bytes:
    image = load_image(CLIENT_STRING, GMS_KEY)
    root = image.root
    for node in list(root.children()):
        if node.name.isdigit() and int(node.name) in current_ids - final_ids:
            del root._children[node.name]
    for chair_id in sorted(migrated_ids & set(names)):
        node = WzSubProperty(str(chair_id), root)
        name, desc = names[chair_id]
        node.add(WzStringProperty("name", name, node))
        node.add(WzStringProperty("desc", desc, node))
        root.add(node)
    return encode_image_body_compact(image, gms_reader())


def patch_server_string(
    path: Path,
    current_ids: set[int],
    final_ids: set[int],
    migrated_ids: set[int],
    names: dict[int, tuple[str, str]],
) -> bytes:
    tree = ET.parse(path)
    root = tree.getroot()
    for node in list(root):
        if node.get("name", "").isdigit() and int(node.get("name")) in current_ids - final_ids:
            root.remove(node)
    by_id = {
        int(node.get("name")): node
        for node in root
        if node.get("name", "").isdigit()
    }
    for chair_id in sorted(migrated_ids & set(names)):
        old = by_id.get(chair_id)
        if old is not None:
            root.remove(old)
        node = ET.SubElement(root, "imgdir", {"name": str(chair_id)})
        name, desc = names[chair_id]
        ET.SubElement(node, "string", {"name": "name", "value": name})
        ET.SubElement(node, "string", {"name": "desc", "value": desc})
    header = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    return (header + ET.tostring(root, encoding="unicode") + "\n").encode("utf-8")


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


def fingerprint(node) -> str:
    digest = hashlib.sha256()

    def visit(current) -> None:
        digest.update(type(current).__name__.encode())
        digest.update(current.name.encode("utf-8"))
        if isinstance(current, WzCanvasProperty):
            digest.update(f"{current.width}:{current.height}:{current.format}:{current.format2}".encode())
            digest.update(_read_canvas_bytes(current))
        elif isinstance(current, WzVectorProperty):
            digest.update(f"{current.x}:{current.y}".encode())
        elif isinstance(
            current,
            (
                WzStringProperty,
                WzIntProperty,
                WzShortProperty,
                WzLongProperty,
                WzFloatProperty,
                WzDoubleProperty,
                WzUolProperty,
            ),
        ):
            digest.update(str(current.value).encode("utf-8"))
        if hasattr(current, "children"):
            for child in current.children():
                visit(child)

    visit(node)
    return digest.hexdigest()


def verify_img(path: Path, expected_ids: set[int] | None = None) -> WzImage:
    image = load_image(path, GMS_KEY)
    if expected_ids is not None:
        actual = {item_id(node) for node in image.root.children() if item_id(node) is not None}
        if actual != expected_ids:
            raise RuntimeError(f"{path}: ID mismatch")
    for node in walk(image.root):
        if isinstance(node, WzCanvasProperty):
            if int(node.format) + int(node.format2) != 1:
                raise RuntimeError(f"{path}: non-ARGB4444 canvas {node.name}")
            if node.child("_outlink") is not None:
                raise RuntimeError(f"{path}: _outlink remains at {node.name}")
            decode_canvas(node, region="GMS")
    return image


def backup_paths(paths: list[Path]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = Path("/private/tmp") / f"beidou-chair-migration-{stamp}"
    for path in paths:
        if not path.exists():
            continue
        destination = backup / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    return backup


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write validated migration outputs")
    args = parser.parse_args()

    target_image = load_image(CLIENT_INSTALL, GMS_KEY)
    current = {
        item_id(node): node
        for node in target_image.root.children()
        if item_id(node) is not None
    }
    source, source_images = load_source_chairs()
    del source_images  # Nodes retain their backing image references.

    current_ids = set(current)
    final_ids = current_ids & set(source)
    migrated_ids = final_ids - {FISHING_CHAIR}
    deleted_ids = current_ids - final_ids
    if (
        len(current_ids) != EXPECTED_CURRENT
        or len(final_ids) != EXPECTED_FINAL
        or len(migrated_ids) != EXPECTED_MIGRATED
        or len(deleted_ids) != EXPECTED_DELETED
        or FISHING_CHAIR not in final_ids
    ):
        raise RuntimeError(
            "unexpected chair sets: "
            f"current={len(current_ids)} final={len(final_ids)} "
            f"migrated={len(migrated_ids)} deleted={len(deleted_ids)}"
        )

    fishing_before = fingerprint(current[FISHING_CHAIR])
    materializer = CanvasMaterializer(TMS_INSTALL, "Item/Install/_Canvas")
    new_root = WzSubProperty(target_image.root.name)
    for chair_id in sorted(final_ids):
        source_node = current[chair_id] if chair_id == FISHING_CHAIR else source[chair_id]
        cloned = (
            clone_current(source_node, new_root)
            if chair_id == FISHING_CHAIR
            else clone_property(source_node, new_root, materializer)
        )
        new_root.add(cloned)
    target_image._root = new_root
    target_image._parsed = True
    item_bytes = encode_image_body_compact(target_image, gms_reader())

    taming_ids = set()
    for node in new_root.children():
        taming = node.get("info/tamingMob")
        if isinstance(taming, WzIntProperty):
            taming_ids.add(int(taming.value))
    if len(taming_ids) != EXPECTED_TAMING:
        raise RuntimeError(f"expected {EXPECTED_TAMING} TamingMob IDs, got {len(taming_ids)}")

    taming_materializer = CanvasMaterializer(TMS_TAMING, "Character/TamingMob/_Canvas")
    taming_outputs: dict[int, tuple[bytes, bytes]] = {}
    for taming_id in sorted(taming_ids):
        path = TMS_TAMING / f"{taming_id:08d}.img"
        image = load_image(path, BMS_KEY)
        root = WzSubProperty(path.name)
        for child in image.root.children():
            root.add(clone_property(child, root, taming_materializer))
        image._root = root
        image._parsed = True
        taming_outputs[taming_id] = (
            encode_image_body_compact(image, gms_reader()),
            image_xml(path.name, root),
        )

    names = csv_strings()
    named_migrations = migrated_ids & set(names)
    if len(named_migrations) != EXPECTED_CSV_MIGRATED:
        raise RuntimeError(f"expected {EXPECTED_CSV_MIGRATED} CSV matches, got {len(named_migrations)}")
    client_string_bytes = patch_client_strings(current_ids, final_ids, migrated_ids, names)
    server_string_bytes = {
        path: patch_server_string(path, current_ids, final_ids, migrated_ids, names)
        for path in SERVER_STRINGS
    }
    server_item_bytes = image_xml("0301.img", new_root)

    print(
        f"chairs: current={len(current_ids)} migrated={len(migrated_ids)} "
        f"preserved=1 deleted={len(deleted_ids)} final={len(final_ids)}"
    )
    print(
        f"item canvases={materializer.canvases} outlinks={materializer.outlinks} "
        f"converted_to_argb4444={materializer.converted}"
    )
    print(
        f"tamingMob={len(taming_ids)} canvases={taming_materializer.canvases} "
        f"outlinks={taming_materializer.outlinks} "
        f"converted_to_argb4444={taming_materializer.converted}"
    )
    print(f"0301.img: {CLIENT_INSTALL.stat().st_size} -> {len(item_bytes)} bytes")

    if not args.apply:
        print("dry-run complete; pass --apply to write outputs")
        return 0

    touched = [CLIENT_INSTALL, CLIENT_STRING, SERVER_INSTALL, *SERVER_STRINGS]
    touched += [CLIENT_TAMING / f"{item_id:08d}.img" for item_id in taming_ids]
    touched += [SERVER_TAMING / f"{item_id:08d}.img.xml" for item_id in taming_ids]
    backup = backup_paths(touched)

    atomic_write(CLIENT_INSTALL, item_bytes)
    atomic_write(SERVER_INSTALL, server_item_bytes)
    atomic_write(CLIENT_STRING, client_string_bytes)
    for path, data in server_string_bytes.items():
        atomic_write(path, data)
    for taming_id, (client_data, server_data) in taming_outputs.items():
        atomic_write(CLIENT_TAMING / f"{taming_id:08d}.img", client_data)
        atomic_write(SERVER_TAMING / f"{taming_id:08d}.img.xml", server_data)

    written = verify_img(CLIENT_INSTALL, final_ids)
    fishing_after = fingerprint(written.root.child(f"0{FISHING_CHAIR}"))
    if fishing_before != fishing_after:
        raise RuntimeError("fishing chair changed")
    for taming_id in sorted(taming_ids):
        verify_img(CLIENT_TAMING / f"{taming_id:08d}.img")

    server_ids = {
        int(node.get("name"))
        for node in ET.parse(SERVER_INSTALL).getroot()
        if node.get("name", "").isdigit()
    }
    if server_ids != final_ids:
        raise RuntimeError("server chair ID set does not match client")
    print(f"verification passed; backup={backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
