#!/usr/bin/env python3
"""Add the advanced Boss teleporter to the Free Market."""

from __future__ import annotations

import argparse
import io
import re
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

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzKey,
    WzStringProperty,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.canvas import _decompress, decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_image_body, encode_image_body_compact  # noqa: E402


NPC_ID = "9063168"
NPC_NAME = "高级Boss传送"
SOURCE_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data/Npc")
SOURCE_NPC = SOURCE_ROOT / f"{NPC_ID}.img"

CLIENT_NPC = ROOT / f"clien/Data/Npc/{NPC_ID}.img"
CLIENT_MAP = ROOT / "clien/Data/Map/Map/Map9/910000000.img"
CLIENT_STRING = ROOT / "clien/Data/String/Npc.img"
SERVER_NPC = ROOT / f"gms-server/wz/Npc.wz/{NPC_ID}.img.xml"
SERVER_MAP = ROOT / "gms-server/wz/Map.wz/Map/Map9/910000000.img.xml"
SERVER_STRING = ROOT / "gms-server/wz-zh-CN/String.wz/Npc.img.xml"

BMS_KEY = WzKey.for_region("BMS")
GMS_KEY = WzKey.for_region("GMS")
LIFE_VALUES = {
    "mobTime": 0,
    "f": 0,
    "hide": 0,
    "x": 1120,
    "y": 23,
    "cy": 23,
    "fh": 198,
    "rx0": 1070,
    "rx1": 1170,
}


def load_image(path: Path, key: WzKey) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=key, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"cannot safely rewrite {path}: {image.parse_warnings}")
    return image


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), GMS_KEY)


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


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

    def linked_canvas(self, value: str) -> WzCanvasProperty:
        prefix = "Npc/_Canvas/"
        normalized = value.replace("\\", "/")
        if not normalized.startswith(prefix):
            raise RuntimeError(f"unsupported NPC outlink: {value}")
        file_name, separator, property_path = normalized[len(prefix) :].partition("/")
        if not separator or not file_name.endswith(".img"):
            raise RuntimeError(f"invalid NPC outlink: {value}")
        image = self.images.get(file_name)
        if image is None:
            image = load_image(SOURCE_ROOT / "_Canvas" / file_name, BMS_KEY)
            self.images[file_name] = image
        canvas = image.root.get(property_path)
        if not isinstance(canvas, WzCanvasProperty) or not canvas.has_pixels():
            raise RuntimeError(f"unresolved NPC outlink: {value}")
        return canvas

    def materialize(self, source: WzCanvasProperty, parent) -> WzCanvasProperty:
        self.canvases += 1
        outlink = source.child("_outlink")
        if isinstance(outlink, WzStringProperty):
            value = str(outlink.value)
            pixels = self.payloads.get(value)
            if pixels is None:
                pixels = self.argb4444(self.linked_canvas(value))
                self.payloads[value] = pixels
            self.outlinks += 1
        else:
            pixels = self.argb4444(source)

        width, height, payload = pixels
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

    @staticmethod
    def argb4444(canvas: WzCanvasProperty) -> tuple[int, int, bytes]:
        width = int(canvas.width)
        height = int(canvas.height)
        if width <= 0 or height <= 0 or not canvas.has_pixels():
            raise RuntimeError(f"invalid NPC canvas {canvas.name}: {width}x{height}")
        if int(canvas.format) + int(canvas.format2) == 1:
            payload = zlib.compress(_decompress(canvas, BMS_KEY), 9)
        else:
            image = decode_canvas(canvas, region="BMS").convert("RGBA")
            payload = encode_canvas_payload(
                image, 1, width, height, key=GMS_KEY, listwz=False, zlib_level=9
            )
        return width, height, payload


def clone_property(source, parent, materializer: CanvasMaterializer):
    if isinstance(source, WzCanvasProperty):
        return materializer.materialize(source, parent)
    if isinstance(source, WzSubProperty):
        output = WzSubProperty(source.name, parent)
        for child in source.children():
            output.add(clone_property(child, output, materializer))
        return output
    if isinstance(source, WzVectorProperty):
        return WzVectorProperty(source.name, int(source.x), int(source.y), parent)
    if isinstance(source, WzStringProperty):
        return WzStringProperty(source.name, str(source.value), parent)
    if isinstance(source, WzIntProperty):
        return WzIntProperty(source.name, int(source.value), parent)
    raise TypeError(f"unsupported NPC node: {type(source).__name__}")


def property_to_xml(prop, indent: int = 1) -> str:
    pad = "  " * indent
    name = f"name={quoteattr(prop.name)}"
    if isinstance(prop, WzCanvasProperty):
        children = prop.children()
        attrs = f'{name} width="{int(prop.width)}" height="{int(prop.height)}"'
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
    if isinstance(prop, WzVectorProperty):
        return f'{pad}<vector {name} x="{int(prop.x)}" y="{int(prop.y)}"/>'
    if isinstance(prop, WzStringProperty):
        return f"{pad}<string {name} value={quoteattr(str(prop.value))}/>"
    if isinstance(prop, WzIntProperty):
        return f'{pad}<int {name} value="{int(prop.value)}"/>'
    raise TypeError(f"unsupported XML node: {type(prop).__name__}")


def image_xml(root: WzSubProperty) -> bytes:
    body = "\n".join(property_to_xml(child) for child in root.children())
    text = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<imgdir name="{NPC_ID}.img">\n{body}\n</imgdir>\n'
    )
    return text.encode("utf-8")


def build_npc_outputs() -> tuple[bytes, bytes, CanvasMaterializer]:
    image = load_image(SOURCE_NPC, BMS_KEY)
    materializer = CanvasMaterializer()
    root = WzSubProperty(image.root.name)
    for child in image.root.children():
        root.add(clone_property(child, root, materializer))
    if materializer.outlinks == 0:
        raise RuntimeError("expected the TMS NPC to contain linked canvases")
    image._root = root
    image._parsed = True
    return encode_image_body_compact(image, gms_reader()), image_xml(root), materializer


def client_map_bytes() -> bytes | None:
    image = load_image(CLIENT_MAP, GMS_KEY)
    life_root = image.get("life")
    if not isinstance(life_root, WzSubProperty):
        raise RuntimeError(f"{CLIENT_MAP} has no life node")

    matching = []
    for life in life_root.children():
        life_id = life.child("id") if isinstance(life, WzSubProperty) else None
        if isinstance(life_id, WzStringProperty) and str(life_id.value) == NPC_ID:
            matching.append(life)
    if len(matching) > 1:
        raise RuntimeError(f"client map contains {len(matching)} copies of NPC {NPC_ID}")

    changed = False
    if matching:
        life = matching[0]
    else:
        numeric_names = [int(life.name) for life in life_root.children() if life.name.isdigit()]
        life = WzSubProperty(str(max(numeric_names, default=-1) + 1), life_root)
        life.add(WzStringProperty("type", "n", life))
        life.add(WzStringProperty("id", NPC_ID, life))
        life_root.add(life)
        changed = True

    for name, value in LIFE_VALUES.items():
        current = life.child(name)
        if not isinstance(current, WzIntProperty) or int(current.value) != value:
            life.add(WzIntProperty(name, value, life))
            changed = True
    return encode_image_body(image, gms_reader()) if changed else None


def client_string_bytes() -> bytes | None:
    image = load_image(CLIENT_STRING, GMS_KEY)
    entry = image.get(NPC_ID)
    changed = False
    if not isinstance(entry, WzSubProperty):
        entry = WzSubProperty(NPC_ID, image.root)
        image.root.add(entry)
        changed = True
    name = entry.child("name")
    if not isinstance(name, WzStringProperty) or str(name.value) != NPC_NAME:
        entry.add(WzStringProperty("name", NPC_NAME, entry))
        changed = True
    return encode_image_body(image, gms_reader()) if changed else None


def find_imgdir_block(text: str, node_name: str, start: int = 0) -> tuple[int, int]:
    pattern = re.compile(rf'<imgdir\b[^>]*\bname="{re.escape(node_name)}"[^>]*>')
    match = pattern.search(text, start)
    if match is None:
        raise RuntimeError(f"missing XML imgdir {node_name}")
    root_start = match.start()
    depth = 0
    for tag_match in re.finditer(r"</?imgdir\b[^>]*>", text[root_start:]):
        tag = tag_match.group(0)
        if tag.startswith("</"):
            depth -= 1
            if depth == 0:
                return root_start, root_start + tag_match.end()
        elif not tag.endswith("/>"):
            depth += 1
    raise RuntimeError(f"unterminated XML imgdir {node_name}")


def server_life_block(index: str) -> str:
    lines = [
        f'    <imgdir name="{index}">',
        '      <string name="type" value="n"/>',
        f'      <string name="id" value="{NPC_ID}"/>',
    ]
    lines.extend(f'      <int name="{name}" value="{value}"/>' for name, value in LIFE_VALUES.items())
    lines.append("    </imgdir>")
    return "\n".join(lines)


def server_map_bytes() -> bytes | None:
    text = SERVER_MAP.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    life_root = next((node for node in root if node.tag == "imgdir" and node.get("name") == "life"), None)
    if life_root is None:
        raise RuntimeError(f"{SERVER_MAP} has no life node")
    matching = [
        node
        for node in life_root
        if any(
            child.tag == "string" and child.get("name") == "id" and child.get("value") == NPC_ID
            for child in node
        )
    ]
    if len(matching) > 1:
        raise RuntimeError(f"server map contains {len(matching)} copies of NPC {NPC_ID}")
    index = matching[0].get("name") if matching else str(max((int(n.get("name")) for n in life_root), default=-1) + 1)
    if index is None:
        raise RuntimeError("NPC life node has no numeric name")

    life_start, life_end = find_imgdir_block(text, "life")
    life_text = text[life_start:life_end]
    replacement = server_life_block(index)
    if matching:
        child_start, child_end = find_imgdir_block(life_text, index)
        current = life_text[child_start:child_end]
        if current.strip() == replacement.strip():
            return None
        life_text = life_text[:child_start] + replacement + life_text[child_end:]
    else:
        insert_at = life_text.rfind("</imgdir>")
        prefix = life_text[:insert_at].rstrip(" ")
        life_text = prefix + replacement + "\n  " + life_text[insert_at:]
    return (text[:life_start] + life_text + text[life_end:]).encode("utf-8")


def server_string_bytes() -> bytes | None:
    text = SERVER_STRING.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    matching = [node for node in root if node.tag == "imgdir" and node.get("name") == NPC_ID]
    if len(matching) > 1:
        raise RuntimeError(f"server string contains {len(matching)} copies of NPC {NPC_ID}")
    replacement = (
        f'  <imgdir name="{NPC_ID}">\n'
        f'    <string name="name" value="{NPC_NAME}"/>\n'
        "  </imgdir>"
    )
    if matching:
        start, end = find_imgdir_block(text, NPC_ID)
        if text[start:end].strip() == replacement.strip():
            return None
        text = text[:start] + replacement + text[end:]
    else:
        insert_at = text.rfind("</imgdir>")
        text = text[:insert_at] + replacement + "\n" + text[insert_at:]
    return text.encode("utf-8")


def verify() -> None:
    image = load_image(CLIENT_NPC, GMS_KEY)
    canvases = 0
    for node in walk(image.root):
        if isinstance(node, WzCanvasProperty):
            canvases += 1
            if node.child("_outlink") is not None:
                raise RuntimeError("client NPC still contains an _outlink")
            decode_canvas(node, region="GMS")
    if canvases == 0:
        raise RuntimeError("client NPC contains no canvases")

    map_image = load_image(CLIENT_MAP, GMS_KEY)
    life_root = map_image.get("life")
    matching = []
    if isinstance(life_root, WzSubProperty):
        for life in life_root.children():
            life_id = life.child("id") if isinstance(life, WzSubProperty) else None
            if isinstance(life_id, WzStringProperty) and str(life_id.value) == NPC_ID:
                matching.append(life)
    if len(matching) != 1:
        raise RuntimeError(f"expected one client map NPC, found {len(matching)}")
    for name, value in LIFE_VALUES.items():
        prop = matching[0].child(name)
        if not isinstance(prop, WzIntProperty) or int(prop.value) != value:
            raise RuntimeError(f"client map verification failed for {name}")

    name = load_image(CLIENT_STRING, GMS_KEY).get(f"{NPC_ID}/name")
    if not isinstance(name, WzStringProperty) or str(name.value) != NPC_NAME:
        raise RuntimeError("client NPC name verification failed")

    server_map = ET.parse(SERVER_MAP).getroot()
    server_life = server_map.find("./imgdir[@name='life']")
    server_matches = [] if server_life is None else [
        node for node in server_life if node.find(f"./string[@name='id'][@value='{NPC_ID}']") is not None
    ]
    if len(server_matches) != 1:
        raise RuntimeError(f"expected one server map NPC, found {len(server_matches)}")
    server_strings = ET.parse(SERVER_STRING).getroot()
    server_name = server_strings.find(f"./imgdir[@name='{NPC_ID}']/string[@name='name']")
    if server_name is None or server_name.get("value") != NPC_NAME:
        raise RuntimeError("server NPC name verification failed")
    if ET.parse(SERVER_NPC).getroot().get("name") != f"{NPC_ID}.img":
        raise RuntimeError("server NPC resource verification failed")


def backup(paths: list[Path]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = Path("/private/tmp") / f"beidou-advanced-boss-npc-{stamp}"
    for path in paths:
        if not path.exists():
            continue
        target = destination / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write validated NPC resources")
    args = parser.parse_args()

    npc_bytes, npc_xml, materializer = build_npc_outputs()
    planned: dict[Path, bytes] = {}
    for path, data in ((CLIENT_NPC, npc_bytes), (SERVER_NPC, npc_xml)):
        if path.exists() and path.read_bytes() != data:
            raise RuntimeError(f"refusing to replace unrelated existing resource: {path}")
        if not path.exists():
            planned[path] = data
    for path, data in (
        (CLIENT_MAP, client_map_bytes()),
        (CLIENT_STRING, client_string_bytes()),
        (SERVER_MAP, server_map_bytes()),
        (SERVER_STRING, server_string_bytes()),
    ):
        if data is not None:
            planned[path] = data

    print(
        f"materialized {materializer.outlinks}/{materializer.canvases} linked canvases "
        f"from {len(materializer.images)} TMS _Canvas files"
    )
    if not args.apply:
        for path in planned:
            print(path.relative_to(ROOT))
        print("dry-run complete; pass --apply to write outputs")
        return 0

    backup_dir = backup(list(planned))
    for path, data in planned.items():
        atomic_write(path, data)
    verify()
    print(f"verification passed; backup={backup_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
