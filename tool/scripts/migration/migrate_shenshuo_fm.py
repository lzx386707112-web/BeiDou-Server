#!/usr/bin/env python3
"""Migrate Shenshuo's Chew Chew styled Free Market entrance.

The migration intentionally keeps the visual layout from Shenshuo while
downgrading map behavior to the older BeiDou client/server surface:

* map 910000000 is re-written with the project's GMS key;
* high-version optional map fields are removed;
* pt=10 inner portals are downgraded to pt=3;
* the current BeiDou Free Market NPC `life` nodes are preserved;
* required visual dependency images are converted to GMS where possible;
* undecodable source canvases are reported instead of silently hidden.
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import quoteattr

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
SRC = Path("/Users/lizixian/Documents/mxd/神说/Data/Map")
BACKUP_ROOT = Path("/private/tmp/shenshuo-fm-migration-backup")
REPORT_PATH = Path("/private/tmp/shenshuo_fm_migration_report.json")

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


SOURCE_REGION = "EMS"
TARGET_KEY = WzKey.for_region("GMS")

CLIENT_MAP = ROOT / "clien/Data/Map/Map/Map9/910000000.img"
CLIENT_OBJ = ROOT / "clien/Data/Map/Obj/chewchewIsland.img"
CLIENT_BACK = ROOT / "clien/Data/Map/Back/chewchewIsland.img"

SERVER_MAP = ROOT / "gms-server/wz/Map.wz/Map/Map9/910000000.img.xml"
SERVER_OBJ = ROOT / "gms-server/wz/Map.wz/Obj/chewchewIsland.img.xml"
SERVER_BACK = ROOT / "gms-server/wz/Map.wz/Back/chewchewIsland.img.xml"

SOURCE_MAP = SRC / "Map/Map9/910000000.img"
SOURCE_OBJ = SRC / "Obj/chewchewIsland.img"
SOURCE_BACK = SRC / "Back/chewchewIsland.img"


class BuiltImage:
    def __init__(self, name: str, root: WzSubProperty):
        self.name = name
        self._root = root

    def parse(self) -> WzSubProperty:
        return self._root

    @property
    def root(self) -> WzSubProperty:
        return self._root


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), TARGET_KEY)


def load_img(path: Path, region: str) -> WzImage:
    img = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region(region), name=path.name)
    img.parse()
    return img


def clone_prop(prop, parent=None):
    if isinstance(prop, WzNullProperty):
        out = WzNullProperty(prop.name, parent)
    elif isinstance(prop, WzShortProperty):
        out = WzShortProperty(prop.name, int(prop.value), parent)
    elif isinstance(prop, WzIntProperty):
        out = WzIntProperty(prop.name, int(prop.value), parent)
    elif isinstance(prop, WzLongProperty):
        out = WzLongProperty(prop.name, int(prop.value), parent)
    elif isinstance(prop, WzFloatProperty):
        out = WzFloatProperty(prop.name, float(prop.value), parent)
    elif isinstance(prop, WzDoubleProperty):
        out = WzDoubleProperty(prop.name, float(prop.value), parent)
    elif isinstance(prop, WzStringProperty):
        out = WzStringProperty(prop.name, str(prop.value), parent)
    elif isinstance(prop, WzVectorProperty):
        out = WzVectorProperty(prop.name, int(prop.x), int(prop.y), parent)
    elif isinstance(prop, WzUolProperty):
        out = WzUolProperty(prop.name, str(prop.value), parent)
    elif isinstance(prop, WzConvexProperty):
        out = WzConvexProperty(prop.name, parent)
        for point in prop.points:
            cloned = clone_prop(point, out)
            out.points.append(cloned)
    elif isinstance(prop, WzCanvasProperty):
        out = WzCanvasProperty(prop.name, parent)
        out.width = int(prop.width)
        out.height = int(prop.height)
        out.format = int(prop.format)
        out.format2 = int(prop.format2)
        out._png_offset = int(prop._png_offset)
        out._png_length = int(prop._png_length)
        out._png_data = prop._png_data
        out._wz_image = prop._wz_image
        for child in prop.children():
            out.add(clone_prop(child, out))
    elif isinstance(prop, WzSoundProperty):
        out = WzSoundProperty(prop.name, parent)
        out.length_ms = int(prop.length_ms)
        out.header = bytes(prop.header)
        out._data_length = int(prop._data_length)
        out._data = getattr(prop, "_data", None)
        out._wz_image = prop._wz_image
    elif isinstance(prop, WzSubProperty):
        out = WzSubProperty(prop.name, parent)
        for child in prop.children():
            out.add(clone_prop(child, out))
    else:
        raise TypeError(f"unsupported property type: {type(prop).__name__}")
    return out


def clone_root(image: WzImage) -> WzSubProperty:
    root = WzSubProperty(image.name)
    for child in image.children():
        root.add(clone_prop(child, root))
    return root


def remove_child(parent, name: str) -> bool:
    if isinstance(parent, WzSubProperty) and name in parent._children:
        del parent._children[name]
        return True
    return False


def set_int(parent: WzSubProperty, name: str, value: int) -> None:
    parent.add(WzIntProperty(name, int(value), parent))


def child(parent, name: str):
    return parent.child(name) if parent is not None and hasattr(parent, "child") else None


def iter_props(prop):
    yield prop
    if hasattr(prop, "children"):
        for item in prop.children():
            yield from iter_props(item)


def reencode_canvases(root: WzSubProperty, *, source_region: str, report: dict, label: str) -> None:
    for prop in iter_props(root):
        if not isinstance(prop, WzCanvasProperty) or not prop.has_pixels():
            continue
        path = prop_path(prop)
        try:
            if int(prop.width) <= 0 or int(prop.height) <= 0:
                raise ValueError(f"invalid canvas size {prop.width}x{prop.height}")
            image = decode_canvas(prop, region=source_region).convert("RGBA")
            prop.width = image.width
            prop.height = image.height
            prop.format = 2
            prop.format2 = 0
            prop._png_data = encode_canvas_payload(
                image,
                2,
                image.width,
                image.height,
                key=TARGET_KEY,
                listwz=False,
            )
            prop._png_length = len(prop._png_data)
            report["canvas_reencoded"][label] += 1
        except Exception as exc:  # noqa: BLE001
            report["canvas_unconverted"].append({
                "image": label,
                "path": path,
                "width": int(prop.width),
                "height": int(prop.height),
                "format": int(prop.format) + int(prop.format2),
                "error": str(exc),
            })


def prop_path(prop) -> str:
    parts = []
    node = prop
    while node is not None:
        parts.append(getattr(node, "name", ""))
        node = getattr(node, "parent", None)
    return "/".join(reversed([p for p in parts if p]))


def sanitize_map(root: WzSubProperty, project_map: WzImage, report: dict) -> None:
    info = child(root, "info")
    for key in ("moveLimit", "noMapCmd", "miniMapOnOff"):
        if remove_child(info, key):
            report["removed_map_fields"].append(f"info/{key}")

    for layer in [p for p in root.children() if p.name.isdigit()]:
        obj_root = child(layer, "obj")
        if obj_root is None:
            continue
        for obj in obj_root.children():
            for key in ("hide", "reactor", "flow"):
                if remove_child(obj, key):
                    report["removed_map_fields"].append(f"{layer.name}/obj/{obj.name}/{key}")

    portal_root = child(root, "portal")
    if portal_root is not None:
        for portal in portal_root.children():
            for key in ("delay", "hideTooltip", "onlyOnce"):
                if remove_child(portal, key):
                    report["removed_map_fields"].append(f"portal/{portal.name}/{key}")
            script = child(portal, "script")
            if isinstance(script, WzStringProperty) and script.value == "":
                remove_child(portal, "script")
                report["removed_map_fields"].append(f"portal/{portal.name}/script(empty)")
            pt = child(portal, "pt")
            if isinstance(pt, WzIntProperty) and int(pt.value) == 10:
                set_int(portal, "pt", 3)
                report["portal_downgrades"].append(portal.name)

    source_life = child(root, "life")
    project_life = project_map.get("life")
    if source_life is not None and project_life is not None:
        source_life._children.clear()
        for life in project_life.children():
            source_life.add(clone_prop(life, source_life))
        report["life_nodes_preserved"] = len(source_life.children())


def encode_img(root: WzSubProperty, name: str) -> bytes:
    return encode_image_body(BuiltImage(name, root), gms_reader())


def atomic_write(path: Path, data: bytes | str, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] write {path}")
        return
    backup(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if isinstance(data, str) else "wb"
    kwargs = {"encoding": "utf-8"} if isinstance(data, str) else {}
    with tempfile.NamedTemporaryFile(mode=mode, prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False, **kwargs) as tmp:
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


def property_to_xml(prop, indent: int = 0) -> str:
    pad = "  " * indent
    name_attr = f"name={quoteattr(prop.name)}"
    if isinstance(prop, WzNullProperty):
        return f"{pad}<null {name_attr}/>"
    if isinstance(prop, WzVectorProperty):
        return f'{pad}<vector {name_attr} x="{prop.x}" y="{prop.y}"/>'
    if isinstance(prop, WzCanvasProperty):
        attrs = f'{name_attr} width="{prop.width}" height="{prop.height}" format="{prop.format + prop.format2}"'
        if not prop.has_children():
            return f"{pad}<canvas {attrs}/>"
        body = "\n".join(property_to_xml(c, indent + 1) for c in prop.children())
        return f"{pad}<canvas {attrs}>\n{body}\n{pad}</canvas>"
    if isinstance(prop, WzUolProperty):
        return f"{pad}<uol {name_attr} value={quoteattr(str(prop.value))}/>"
    if isinstance(prop, WzConvexProperty):
        body = "\n".join(property_to_xml(c, indent + 1) for c in prop.children())
        return f"{pad}<extended {name_attr}>\n{body}\n{pad}</extended>"
    if isinstance(prop, WzSubProperty):
        if not prop.has_children():
            return f"{pad}<imgdir {name_attr}/>"
        body = "\n".join(property_to_xml(c, indent + 1) for c in prop.children())
        return f"{pad}<imgdir {name_attr}>\n{body}\n{pad}</imgdir>"
    tag = {
        "Short": "short",
        "Int": "int",
        "Long": "long",
        "Float": "float",
        "Double": "double",
        "String": "string",
    }.get(prop.type_name, "property")
    return f"{pad}<{tag} {name_attr} value={quoteattr(str(prop.value))}/>"


def image_to_xml(root: WzSubProperty, name: str) -> str:
    body = "\n".join(property_to_xml(c, 1) for c in root.children())
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<imgdir name="{name}">\n{body}\n</imgdir>\n'


def migrate(dry_run: bool) -> dict:
    report = {
        "canvas_reencoded": {"map": 0, "obj": 0, "back": 0},
        "canvas_unconverted": [],
        "removed_map_fields": [],
        "portal_downgrades": [],
        "life_nodes_preserved": 0,
        "source_parse_warnings": {},
        "written": [],
        "backup_root": str(BACKUP_ROOT),
    }

    source_map = load_img(SOURCE_MAP, SOURCE_REGION)
    project_map = load_img(CLIENT_MAP, "GMS")
    map_root = clone_root(source_map)
    sanitize_map(map_root, project_map, report)
    reencode_canvases(map_root, source_region=SOURCE_REGION, report=report, label="map")
    atomic_write(CLIENT_MAP, encode_img(map_root, "910000000.img"), dry_run)
    atomic_write(SERVER_MAP, image_to_xml(map_root, "910000000.img"), dry_run)
    report["written"].extend([str(CLIENT_MAP), str(SERVER_MAP)])

    for src, client, server, label in (
        (SOURCE_BACK, CLIENT_BACK, SERVER_BACK, "back"),
        (SOURCE_OBJ, CLIENT_OBJ, SERVER_OBJ, "obj"),
    ):
        image = load_img(src, SOURCE_REGION)
        report["source_parse_warnings"][label] = {
            "truncated": image.truncated,
            "warnings": image.parse_warnings,
        }
        root = clone_root(image)
        reencode_canvases(root, source_region=SOURCE_REGION, report=report, label=label)
        atomic_write(client, encode_img(root, src.name), dry_run)
        atomic_write(server, image_to_xml(root, src.name), dry_run)
        report["written"].extend([str(client), str(server)])

    if dry_run:
        print(f"[dry-run] write report {REPORT_PATH}")
    else:
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = migrate(args.dry_run)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
