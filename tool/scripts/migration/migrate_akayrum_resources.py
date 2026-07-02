#!/usr/bin/env python3
"""Migrate the local Akayrum/Temple of Time resource pack into BeiDou.

The source pack is intentionally partial: it contains 272xxxx map XML with
embedded PNG canvas data, six new 822xxxx mobs, three existing 930xxxx mobs,
15 NPCs, and a small set of Map Back/Obj/Tile IMG files. It does not contain
Arkarium's boss/event scripts or String.wz text.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
SRC = Path("/Users/lizixian/Documents/mxd/阿卡伊勒")
SRC_273 = Path("/Users/lizixian/Documents/mxd/273")
SRC_273_JSON = SRC_273 / "tms273" / "WZ_JSON_TW"
SRC_273_CANVAS = SRC_273 / "sanjindao" / "Data"
BACKUP_ROOT = Path("/private/tmp/akayrum-migration-backup")
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzConvexProperty,
    WzFloatProperty,
    WzImage,
    WzIntProperty,
    WzKey,
    WzNullProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


TARGET_KEY = WzKey.for_region("GMS")
SOURCE_REGION = "EMS"
SOURCE_273_REGION = "BMS"
TRANSPARENT_PIXEL = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
AKAYRUM_BOSS_ID = 8860000
AKAYRUM_SUMMON_TEMPLATE_ID = 9900002
FORCE_SOURCE_MOB_IDS = {9300301, 9300302, 9300304}
AKAYRUM_BOSS_SKILLS = [
    {"skill": 140, "action": 1, "level": 9, "effectAfter": 0},
    {"skill": 141, "action": 2, "level": 10, "effectAfter": 0},
]
AKAYRUM_BOSS_EXTRA_ACTIONS: list[str] = []
AKAYRUM_BOSS_ATTACK_INFO_FIELDS = ["hit", "range", "attackAfter"]
AKAYRUM_BOSS_CLIENT_INFO = [
    ("int", "bodyAttack", 1),
    ("int", "level", 170),
    ("int", "maxHP", 2100000000),
    ("int", "maxMP", 15000000),
    ("int", "speed", -50),
    ("int", "PADamage", 30000),
    ("int", "PDDamage", 1700),
    ("int", "MADamage", 25000),
    ("int", "MDDamage", 1980),
    ("int", "acc", 600),
    ("int", "eva", 300),
    ("int", "exp", 5000000),
    ("int", "hpRecovery", 500000),
    ("int", "mpRecovery", 10000),
    ("int", "undead", 0),
    ("int", "pushed", 140000),
    ("float", "fs", 10.0),
    ("int", "summonType", 12),
    ("int", "firstAttack", 1),
    ("int", "boss", 1),
    ("int", "publicReward", 1),
    ("int", "explosiveReward", 1),
    ("int", "hpTagColor", 1),
    ("int", "hpTagBgcolor", 5),
    ("int", "mobType", 1),
    ("int", "rareItemDropLevel", 3),
]
AKAYRUM_BOSS_ATTACKS: list[dict[str, int]] = []


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


def atomic_write_bytes(path: Path, data: bytes, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def copy_file(src: Path, dst: Path, dry_run: bool, overwrite: bool = False) -> str:
    if dst.exists() and not overwrite:
        return "skip-existing"
    if dry_run:
        print(f"[dry-run] copy {src} -> {dst}")
        return "copy"
    backup(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return "copy"


def backup(path: Path) -> None:
    if not path.exists():
        return
    rel = path.relative_to(ROOT)
    backup_path = BACKUP_ROOT / rel
    if backup_path.exists():
        return
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)


def source_ids(kind: str) -> list[int]:
    return sorted(int(p.name.removesuffix(".img.xml")) for p in (SRC / kind).glob("*.img.xml"))


MAP_IDS = source_ids("map")
MOB_IDS = source_ids("mob")
NPC_IDS = source_ids("npc")


def scalar_value(node: ET.Element, default: str = "0") -> str:
    return node.get("value", default)


def xml_to_property(node: ET.Element, parent: WzSubProperty | None = None):
    name = node.get("name", "")
    if node.tag == "imgdir":
        out = WzSubProperty(name, parent)
        for child in node:
            out.add(xml_to_property(child, out))
        return out
    if node.tag == "canvas":
        out = WzCanvasProperty(name, parent)
        out.width = int(node.get("width", "0"))
        out.height = int(node.get("height", "0"))
        out.format = 2
        out.format2 = 0
        basedata = node.get("basedata")
        if basedata and out.width > 0 and out.height > 0:
            try:
                image = Image.open(io.BytesIO(base64.b64decode(basedata))).convert("RGBA")
            except Exception:
                image = TRANSPARENT_PIXEL
                out.width = 1
                out.height = 1
            out._png_data = encode_canvas_payload(
                image,
                2,
                int(out.width),
                int(out.height),
                key=TARGET_KEY,
                listwz=False,
            )
            out._png_length = len(out._png_data)
        for child in node:
            out.add(xml_to_property(child, out))
        return out
    if node.tag == "vector":
        return WzVectorProperty(name, int(node.get("x", "0")), int(node.get("y", "0")), parent)
    if node.tag == "int":
        return WzIntProperty(name, int(scalar_value(node)), parent)
    if node.tag == "float":
        return WzFloatProperty(name, float(scalar_value(node, "0.0")), parent)
    if node.tag == "string":
        return WzStringProperty(name, scalar_value(node, ""), parent)
    if node.tag == "uol":
        return WzUolProperty(name, scalar_value(node, ""), parent)
    if node.tag == "null":
        return WzNullProperty(name, parent)
    raise TypeError(f"unsupported XML tag: {node.tag}")


def xml_to_img(xml_path: Path, dst_path: Path, dry_run: bool, overwrite: bool = False) -> str:
    if dst_path.exists() and not overwrite:
        return "skip-existing"
    root_xml = ET.parse(xml_path).getroot()
    root = WzSubProperty(root_xml.get("name", dst_path.name))
    for child in root_xml:
        root.add(xml_to_property(child, root))
    backup(dst_path)
    atomic_write_bytes(dst_path, encode_image_body(BuiltImage(dst_path.name, root), gms_reader()), dry_run)
    return "write"


def reencode_canvas_tree(prop) -> None:
    if isinstance(prop, WzCanvasProperty) and prop.has_pixels():
        try:
            if int(prop.width) <= 0 or int(prop.height) <= 0:
                raise ValueError(f"invalid canvas size {prop.width}x{prop.height}")
            image = decode_canvas(prop, region=SOURCE_REGION)
            width = int(prop.width)
            height = int(prop.height)
            fmt = int(prop.format) + int(prop.format2)
        except Exception:
            image = TRANSPARENT_PIXEL
            width = 1
            height = 1
            fmt = 2
            prop.width = width
            prop.height = height
            prop.format = 2
            prop.format2 = 0
        prop._png_data = encode_canvas_payload(image, fmt, width, height, key=TARGET_KEY, listwz=False)
        prop._png_length = len(prop._png_data)
    if hasattr(prop, "children"):
        for child in prop.children():
            reencode_canvas_tree(child)


def iter_properties(prop):
    yield prop
    if hasattr(prop, "children"):
        for child in prop.children():
            yield from iter_properties(child)


def iter_named_properties(prop, path: str = ""):
    yield path, prop
    if hasattr(prop, "children"):
        for child in prop.children():
            child_path = f"{path}/{child.name}" if path else child.name
            yield from iter_named_properties(child, child_path)


def reencode_source_img(src_path: Path, dst_path: Path, dry_run: bool, overwrite: bool = False) -> str:
    return reencode_region_img(src_path, dst_path, dry_run, SOURCE_REGION, overwrite=overwrite)


def reencode_region_img(src_path: Path, dst_path: Path, dry_run: bool, source_region: str, overwrite: bool = False) -> str:
    if dst_path.exists() and not overwrite:
        return "skip-existing"
    src_img = WzImage.from_bytes(src_path.read_bytes(), key=WzKey.for_region(source_region), name=src_path.name)
    src_img.parse()
    reencode_canvas_tree_with_region(src_img.root, source_region)
    backup(dst_path)
    atomic_write_bytes(dst_path, encode_image_body(src_img, gms_reader()), dry_run)
    return "write"


def reencode_canvas_tree_with_region(prop, source_region: str) -> None:
    if isinstance(prop, WzCanvasProperty) and prop.has_pixels():
        try:
            if int(prop.width) <= 0 or int(prop.height) <= 0:
                raise ValueError(f"invalid canvas size {prop.width}x{prop.height}")
            image = decode_canvas(prop, region=source_region)
            width = int(prop.width)
            height = int(prop.height)
            fmt = int(prop.format) + int(prop.format2)
        except Exception:
            image = TRANSPARENT_PIXEL
            width = 1
            height = 1
            fmt = 2
            prop.width = width
            prop.height = height
            prop.format = 2
            prop.format2 = 0
        prop._png_data = encode_canvas_payload(image, fmt, width, height, key=TARGET_KEY, listwz=False)
        prop._png_length = len(prop._png_data)
    if hasattr(prop, "children"):
        for child in prop.children():
            reencode_canvas_tree_with_region(child, source_region)


def clone_property(prop, name: str | None = None, parent=None):
    new_name = prop.name if name is None else name
    if isinstance(prop, WzCanvasProperty):
        out = WzCanvasProperty(new_name, parent)
        out.width = prop.width
        out.height = prop.height
        out.format = prop.format
        out.format2 = prop.format2
        if prop.has_pixels():
            image = decode_canvas(prop, region="GMS")
            fmt = int(prop.format) + int(prop.format2)
            out._png_data = encode_canvas_payload(
                image,
                fmt,
                int(prop.width),
                int(prop.height),
                key=TARGET_KEY,
                listwz=False,
            )
            out._png_length = len(out._png_data)
        for child in prop.children():
            out.add(clone_property(child, parent=out))
        return out
    if isinstance(prop, WzSubProperty):
        out = WzSubProperty(new_name, parent)
        for child in prop.children():
            out.add(clone_property(child, parent=out))
        return out
    if isinstance(prop, WzConvexProperty):
        out = WzConvexProperty(new_name, parent)
        for point in prop.points:
            out.points.append(WzVectorProperty(point.name, int(point.x), int(point.y), out))
        return out
    if isinstance(prop, WzVectorProperty):
        return WzVectorProperty(new_name, int(prop.x), int(prop.y), parent)
    if isinstance(prop, WzStringProperty):
        return WzStringProperty(new_name, str(prop.value), parent)
    if isinstance(prop, WzIntProperty):
        return WzIntProperty(new_name, int(prop.value), parent)
    if isinstance(prop, WzFloatProperty):
        return WzFloatProperty(new_name, float(prop.value), parent)
    if isinstance(prop, WzUolProperty):
        return WzUolProperty(new_name, prop.value, parent)
    if isinstance(prop, WzNullProperty):
        return WzNullProperty(new_name, parent)
    raise TypeError(f"unsupported WZ property: {type(prop).__name__}")


def clone_property_from_region(prop, source_region: str, name: str | None = None, parent=None):
    new_name = prop.name if name is None else name
    if isinstance(prop, WzCanvasProperty):
        out = WzCanvasProperty(new_name, parent)
        out.width = prop.width
        out.height = prop.height
        out.format = prop.format
        out.format2 = prop.format2
        if prop.has_pixels():
            try:
                image = decode_canvas(prop, region=source_region)
                width = int(prop.width)
                height = int(prop.height)
                fmt = int(prop.format) + int(prop.format2)
            except Exception:
                image = TRANSPARENT_PIXEL
                width = 1
                height = 1
                fmt = 2
                out.width = width
                out.height = height
                out.format = 2
                out.format2 = 0
            out._png_data = encode_canvas_payload(
                image,
                fmt,
                width,
                height,
                key=TARGET_KEY,
                listwz=False,
            )
            out._png_length = len(out._png_data)
        for child in prop.children():
            out.add(clone_property_from_region(child, source_region, parent=out))
        return out
    if isinstance(prop, WzSubProperty):
        out = WzSubProperty(new_name, parent)
        for child in prop.children():
            out.add(clone_property_from_region(child, source_region, parent=out))
        return out
    if isinstance(prop, WzConvexProperty):
        out = WzConvexProperty(new_name, parent)
        for point in prop.points:
            out.points.append(WzVectorProperty(point.name, int(point.x), int(point.y), out))
        return out
    if isinstance(prop, WzVectorProperty):
        return WzVectorProperty(new_name, int(prop.x), int(prop.y), parent)
    if isinstance(prop, WzStringProperty):
        return WzStringProperty(new_name, str(prop.value), parent)
    if isinstance(prop, WzIntProperty):
        return WzIntProperty(new_name, int(prop.value), parent)
    if isinstance(prop, WzFloatProperty):
        return WzFloatProperty(new_name, float(prop.value), parent)
    if isinstance(prop, WzUolProperty):
        return WzUolProperty(new_name, prop.value, parent)
    if isinstance(prop, WzNullProperty):
        return WzNullProperty(new_name, parent)
    raise TypeError(f"unsupported WZ property: {type(prop).__name__}")


def ensure_subproperty(parent: WzSubProperty, name: str) -> WzSubProperty:
    existing = parent.child(name)
    if existing is not None:
        if not isinstance(existing, WzSubProperty):
            raise TypeError(f"{parent.name}/{name} is {type(existing).__name__}, expected WzSubProperty")
        return existing
    out = WzSubProperty(name, parent)
    parent.add(out)
    return out


def set_node_from_source(dst_img: WzImage, src_img: WzImage, node_path: str, source_region: str) -> bool:
    src_node = src_img.get(node_path)
    if src_node is None:
        raise RuntimeError(f"source {src_img.name} missing {node_path}")
    parent = dst_img.root
    parts = node_path.split("/")
    for part in parts[:-1]:
        parent = ensure_subproperty(parent, part)
    parent.add(clone_property_from_region(src_node, source_region, parts[-1], parent))
    return True


def set_node_from_same_img(dst_img: WzImage, source_path: str, target_path: str) -> bool:
    src_node = dst_img.get(source_path)
    if src_node is None:
        raise RuntimeError(f"{dst_img.name} missing fallback {source_path}")
    parent = dst_img.root
    parts = target_path.split("/")
    for part in parts[:-1]:
        parent = ensure_subproperty(parent, part)
    parent.add(clone_property(src_node, parts[-1], parent))
    return True


def merge_missing_non_canvas_children(dst_prop, src_prop, source_region: str) -> bool:
    if not hasattr(dst_prop, "child") or not hasattr(src_prop, "children"):
        return False
    changed = False
    for child in src_prop.children():
        if dst_prop.child(child.name) is not None:
            continue
        if isinstance(child, WzCanvasProperty):
            continue
        dst_prop.add(clone_property_from_region(child, source_region, parent=dst_prop))
        changed = True
    return changed


def merge_canvas_metadata_from_sources(
    dst_node,
    node_path: str,
    source_imgs: Iterable[tuple[WzImage, str]],
    existing_node=None,
) -> bool:
    if not isinstance(dst_node, WzCanvasProperty):
        return False
    changed = False
    if isinstance(existing_node, WzCanvasProperty) and existing_node is not dst_node:
        changed |= merge_missing_non_canvas_children(dst_node, existing_node, "GMS")
    for source_img, source_region in source_imgs:
        source_node = source_img.get(node_path)
        if isinstance(source_node, WzCanvasProperty):
            changed |= merge_missing_non_canvas_children(dst_node, source_node, source_region)
    return changed


def iter_canvas_paths(prop, prefix: str = "") -> Iterable[tuple[str, WzCanvasProperty]]:
    if isinstance(prop, WzCanvasProperty):
        yield prefix.strip("/"), prop
    if hasattr(prop, "children"):
        for child in prop.children():
            child_path = f"{prefix}/{child.name}".strip("/")
            yield from iter_canvas_paths(child, child_path)


def canvas_decode_problem(node) -> str | None:
    if not isinstance(node, WzCanvasProperty) or not node.has_pixels():
        return None
    try:
        image = decode_canvas(node, region="GMS")
    except Exception as exc:
        return f"decode_error:{exc!r}"
    if image.width <= 1 and image.height <= 1:
        return f"tiny:{image.width}x{image.height}"
    if image.getbbox() is None:
        return f"blank:{image.width}x{image.height}"
    return None


def canvas_decode_problem_with_region(node, region: str) -> str | None:
    if not isinstance(node, WzCanvasProperty) or not node.has_pixels():
        return None
    try:
        image = decode_canvas(node, region=region)
    except Exception as exc:
        return f"decode_error:{exc!r}"
    if image.width <= 1 and image.height <= 1:
        return f"tiny:{image.width}x{image.height}"
    if image.getbbox() is None:
        return f"blank:{image.width}x{image.height}"
    return None


def canvas_decode_error_with_region(node, region: str) -> str | None:
    if not isinstance(node, WzCanvasProperty) or not node.has_pixels():
        return None
    try:
        decode_canvas(node, region=region)
    except Exception as exc:
        return f"decode_error:{exc!r}"
    return None


def tree_canvas_decode_problem(node, region: str) -> str | None:
    problem = canvas_decode_problem_with_region(node, region)
    if problem is not None:
        return problem
    if hasattr(node, "children"):
        for child in node.children():
            problem = tree_canvas_decode_problem(child, region)
            if problem is not None:
                return f"{child.name}/{problem}"
    return None


def referenced_map_xml_roots() -> Iterable[tuple[int, ET.Element]]:
    for map_id in MAP_IDS:
        path = ROOT / f"gms-server/wz/Map.wz/Map/Map2/{map_id}.img.xml"
        if path.exists():
            yield map_id, ET.parse(path).getroot()


def collect_referenced_obj_nodes() -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {}
    for _, root in referenced_map_xml_roots():
        for layer_name in [str(i) for i in range(8)]:
            layer = direct_child(root, layer_name)
            if layer is None:
                continue
            obj_root = direct_child(layer, "obj")
            if obj_root is None:
                continue
            for obj in obj_root:
                o_s = text_child(obj, "oS")
                l0 = text_child(obj, "l0")
                l1 = text_child(obj, "l1")
                l2 = text_child(obj, "l2")
                if o_s and l0 and l1 and l2:
                    refs.setdefault(o_s, set()).add(f"{l0}/{l1}/{l2}")
    return refs


def collect_referenced_back_nodes() -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {}
    for _, root in referenced_map_xml_roots():
        back_root = direct_child(root, "back")
        if back_root is None:
            continue
        for back in back_root:
            b_s = text_child(back, "bS")
            no = text_child(back, "no")
            ani = int(text_child(back, "ani") or "0")
            if b_s and no is not None:
                group = "ani" if ani else "back"
                refs.setdefault(b_s, set()).add(f"{group}/{no}")
    return refs


def collect_referenced_tile_nodes() -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {}
    for _, root in referenced_map_xml_roots():
        for layer_name in [str(i) for i in range(8)]:
            layer = direct_child(root, layer_name)
            if layer is None:
                continue
            info = direct_child(layer, "info")
            t_s = text_child(info, "tS") if info is not None else None
            tile_root = direct_child(layer, "tile")
            if not t_s or tile_root is None:
                continue
            for tile in tile_root:
                u = text_child(tile, "u")
                no = text_child(tile, "no")
                if u and no is not None:
                    refs.setdefault(t_s, set()).add(f"{u}/{no}")
    return refs


def patch_referenced_common_nodes(
    src_subdir: str,
    dst_subdir: str,
    refs: dict[str, set[str]],
    dry_run: bool,
    replace_bad_canvas: bool = False,
) -> str:
    changed_files = 0
    for img_name, node_paths in sorted(refs.items()):
        dst_path = ROOT / f"clien/Data/Map/{dst_subdir}/{img_name}.img"
        if not dst_path.exists():
            continue
        source_imgs = []
        for src_path, source_region in [
            (SRC / src_subdir / f"{img_name}.img", SOURCE_REGION),
            (SRC_273_CANVAS / "Map" / dst_subdir / "_Canvas" / f"{img_name}.img", SOURCE_273_REGION),
            (SRC_273_CANVAS / "Map" / dst_subdir / f"{img_name}.img", SOURCE_273_REGION),
        ]:
            if src_path.exists():
                src_img = WzImage.from_bytes(src_path.read_bytes(), key=WzKey.for_region(source_region), name=src_path.name)
                src_img.parse()
                source_imgs.append((src_img, source_region))
        if not source_imgs:
            continue
        dst_img = WzImage.from_bytes(dst_path.read_bytes(), key=TARGET_KEY, name=dst_path.name)
        dst_img.parse()
        changed = False
        for node_path in sorted(node_paths):
            dst_node = dst_img.get(node_path)
            missing_dst_node = dst_node is None
            bad_dst_node = (
                dst_node is not None
                and replace_bad_canvas
                and tree_canvas_decode_problem(dst_node, "GMS") is not None
            )
            if missing_dst_node or bad_dst_node:
                fallback = None
                for src_img, source_region in source_imgs:
                    src_node = src_img.get(node_path)
                    if src_node is not None:
                        fallback = fallback or (src_img, source_region)
                        if replace_bad_canvas and tree_canvas_decode_problem(src_node, source_region) is not None:
                            continue
                        changed |= set_node_from_source(dst_img, src_img, node_path, source_region)
                        break
                else:
                    if fallback is not None and missing_dst_node:
                        src_img, source_region = fallback
                        changed |= set_node_from_source(dst_img, src_img, node_path, source_region)
                    elif img_name == "connect" and node_path.startswith("rope/22/") and missing_dst_node:
                        idx = int(node_path.rsplit("/", 1)[1])
                        changed |= set_node_from_same_img(dst_img, f"rope/0/{min(idx, 4)}", node_path)
                    elif missing_dst_node:
                        raise RuntimeError(f"sources for {img_name}.img missing {node_path}")
        if changed:
            changed_files += 1
            backup(dst_path)
            atomic_write_bytes(dst_path, encode_image_body(dst_img, gms_reader()), dry_run)
    if changed_files:
        return "write"
    return "skip-existing"


def patch_referenced_obj_nodes(dry_run: bool) -> str:
    return patch_referenced_common_nodes("obj", "Obj", collect_referenced_obj_nodes(), dry_run, replace_bad_canvas=True)


def patch_referenced_back_nodes(dry_run: bool) -> str:
    return patch_referenced_common_nodes("back", "Back", collect_referenced_back_nodes(), dry_run, replace_bad_canvas=True)


def patch_referenced_tile_nodes(dry_run: bool) -> str:
    return patch_referenced_common_nodes("tile", "Tile", collect_referenced_tile_nodes(), dry_run, replace_bad_canvas=True)


def patch_common_file_canvases(
    src_subdir: str,
    dst_subdir: str,
    img_names: Iterable[str],
    dry_run: bool,
    tiny_fallbacks: dict[tuple[str, str], str] | None = None,
) -> str:
    changed_files = 0
    tiny_fallbacks = tiny_fallbacks or {}
    for img_name in sorted(set(img_names)):
        if not img_name:
            continue
        dst_path = ROOT / f"clien/Data/Map/{dst_subdir}/{img_name}.img"
        if not dst_path.exists():
            continue
        source_imgs = []
        for src_path, source_region in [
            (SRC_273_CANVAS / "Map" / dst_subdir / "_Canvas" / f"{img_name}.img", SOURCE_273_REGION),
            (SRC / src_subdir / f"{img_name}.img", SOURCE_REGION),
            (SRC_273_CANVAS / "Map" / dst_subdir / f"{img_name}.img", SOURCE_273_REGION),
        ]:
            if src_path.exists():
                src_img = WzImage.from_bytes(src_path.read_bytes(), key=WzKey.for_region(source_region), name=src_path.name)
                src_img.parse()
                source_imgs.append((src_img, source_region))

        dst_img = WzImage.from_bytes(dst_path.read_bytes(), key=TARGET_KEY, name=dst_path.name)
        dst_img.parse()
        changed = False
        for node_path, dst_node in list(iter_canvas_paths(dst_img.root)):
            has_decode_error = canvas_decode_error_with_region(dst_node, "GMS") is not None
            fallback_path = tiny_fallbacks.get((img_name, node_path))
            if not has_decode_error and fallback_path is None:
                if merge_canvas_metadata_from_sources(dst_node, node_path, source_imgs):
                    changed = True
                continue
            replacement = None
            for source_img, source_region in source_imgs:
                source_node = source_img.get(node_path)
                if (
                    isinstance(source_node, WzCanvasProperty)
                    and canvas_decode_problem_with_region(source_node, source_region) is None
                ):
                    replacement = clone_property_from_region(source_node, source_region)
                    break
            if replacement is None and fallback_path is not None:
                fallback_node = dst_img.get(fallback_path)
                if isinstance(fallback_node, WzCanvasProperty) and canvas_decode_problem(fallback_node) is None:
                    replacement = clone_property(fallback_node)
            if replacement is None:
                replacement = WzCanvasProperty(node_path.rsplit("/", 1)[-1])
                replacement.width = 2
                replacement.height = 2
                replacement.format = 2
                replacement.format2 = 0
                image = Image.new("RGBA", (2, 2), (255, 255, 255, 1))
                replacement._png_data = encode_canvas_payload(image, 2, 2, 2, key=TARGET_KEY, listwz=False)
                replacement._png_length = len(replacement._png_data)
                for child in dst_node.children():
                    replacement.add(clone_property(child, parent=replacement))
            merge_canvas_metadata_from_sources(replacement, node_path, source_imgs, existing_node=dst_node)
            parent = dst_img.root
            parts = node_path.split("/")
            for part in parts[:-1]:
                parent = ensure_subproperty(parent, part)
            parent.add(clone_property(replacement, parts[-1], parent))
            changed = True
        if changed:
            changed_files += 1
            backup(dst_path)
            atomic_write_bytes(dst_path, encode_image_body(dst_img, gms_reader()), dry_run)
    return "write" if changed_files else "skip-existing"


def patch_referenced_common_file_canvases(dry_run: bool) -> str:
    changed = False
    obj_tiny_fallbacks = {
        ("dungeon3", "dragonRoad/nature2/7/0"): "dragonRoad/nature2/5/0",
    }
    changed |= patch_common_file_canvases(
        "obj",
        "Obj",
        collect_referenced_obj_nodes().keys(),
        dry_run,
        tiny_fallbacks=obj_tiny_fallbacks,
    ) == "write"
    changed |= patch_common_file_canvases("back", "Back", collect_referenced_back_nodes().keys(), dry_run) == "write"
    changed |= patch_common_file_canvases("tile", "Tile", collect_referenced_tile_nodes().keys(), dry_run) == "write"
    return "write" if changed else "skip-existing"


def patch_bgm22(dry_run: bool) -> str:
    src_path = SRC_273_CANVAS / "Sound" / "Bgm22.img"
    dst_path = ROOT / "clien/Data/Sound/Bgm22.img"
    if dst_path.exists():
        return "skip-existing"
    if not src_path.exists():
        return "skip-missing"
    return reencode_region_img(src_path, dst_path, dry_run, SOURCE_273_REGION)


def patch_shown_at_minimap(dry_run: bool) -> str:
    changed = False
    for map_id in MAP_IDS:
        client_path = ROOT / f"clien/Data/Map/Map/Map2/{map_id}.img"
        if client_path.exists():
            img = WzImage.from_bytes(client_path.read_bytes(), key=TARGET_KEY, name=client_path.name)
            img.parse()
            img_changed = False
            portal_root = img.get("portal")
            if portal_root is not None:
                for portal in portal_root.children():
                    if isinstance(portal, WzSubProperty) and portal.child("shownAtMinimap") is not None:
                        portal._children.pop("shownAtMinimap", None)
                        img_changed = True
            if img_changed:
                changed = True
                backup(client_path)
                atomic_write_bytes(client_path, encode_image_body(img, gms_reader()), dry_run)

        server_path = ROOT / f"gms-server/wz/Map.wz/Map/Map2/{map_id}.img.xml"
        if server_path.exists():
            text = server_path.read_text(encoding="utf-8")
            new_text = re.sub(r'<int name="shownAtMinimap" value="[^"]*"/>', "", text)
            if new_text != text:
                changed = True
                backup(server_path)
                if dry_run:
                    print(f"[dry-run] patch {server_path}")
                else:
                    with tempfile.NamedTemporaryFile(
                        prefix=f".{server_path.name}.",
                        suffix=".tmp",
                        dir=server_path.parent,
                        delete=False,
                    ) as tmp:
                        tmp.write(new_text.encode("utf-8"))
                        tmp_path = Path(tmp.name)
                    tmp_path.replace(server_path)

    return "write" if changed else "skip-existing"


def patch_acc10_nodes(dry_run: bool) -> str:
    src_path = SRC / "obj" / "acc10.img"
    dst_path = ROOT / "clien/Data/Map/Obj/acc10.img"
    if not src_path.exists() or not dst_path.exists():
        return "skip-missing"

    required_nodes = [
        "timeCrack/acc/0",
        "timeCrack/acc/1",
        "timeCrack/acc/4",
        "timeCrack/altar/4",
        "timeTemplePast/foot/0",
        "timeTemplePast/foot/1",
        "timeTemplePast/pillar/21",
        "timeTemplePast/pillar/22",
        "timeTemplePast/pillar/23",
        "timeTemplePast/pillar/42",
        "timeTemplePast/pillar/43",
    ]

    source_imgs = []
    for source_path, source_region in [
        (SRC_273_CANVAS / "Map/Obj/_Canvas/acc10.img", SOURCE_273_REGION),
        (src_path, SOURCE_REGION),
        (SRC_273_CANVAS / "Map/Obj/acc10.img", SOURCE_273_REGION),
    ]:
        if source_path.exists():
            source_img = WzImage.from_bytes(
                source_path.read_bytes(),
                key=WzKey.for_region(source_region),
                name=source_path.name,
            )
            source_img.parse()
            source_imgs.append((source_img, source_region))
    if not source_imgs:
        return "skip-missing"

    dst_img = WzImage.from_bytes(dst_path.read_bytes(), key=TARGET_KEY, name=dst_path.name)
    dst_img.parse()

    changed = False
    for node_path in required_nodes:
        if dst_img.get(node_path) is not None:
            continue
        fallback = None
        for source_img, source_region in source_imgs:
            src_node = source_img.get(node_path)
            if src_node is not None:
                fallback = (src_node, source_region)
                break
        if fallback is None:
            raise RuntimeError(f"source acc10.img missing {node_path}")
        src_node, source_region = fallback
        parent = dst_img.root
        parts = node_path.split("/")
        for part in parts[:-1]:
            parent = ensure_subproperty(parent, part)
        new_node = clone_property_from_region(src_node, source_region, parts[-1], parent)
        parent.add(new_node)
        changed = True

    for node_path, dst_node in list(iter_canvas_paths(dst_img.root)):
        metadata_changed = merge_canvas_metadata_from_sources(dst_node, node_path, source_imgs)
        if canvas_decode_problem(dst_node) is None:
            if metadata_changed:
                changed = True
            continue
        replacement = None
        for source_img, source_region in source_imgs:
            source_node = source_img.get(node_path)
            if isinstance(source_node, WzCanvasProperty) and canvas_decode_problem_with_region(source_node, source_region) is None:
                replacement = clone_property_from_region(source_node, source_region)
                break
        if replacement is None:
            replacement = WzCanvasProperty(node_path.rsplit("/", 1)[-1])
            replacement.width = 2
            replacement.height = 2
            replacement.format = 2
            replacement.format2 = 0
            image = Image.new("RGBA", (2, 2), (255, 255, 255, 1))
            replacement._png_data = encode_canvas_payload(image, 2, 2, 2, key=TARGET_KEY, listwz=False)
            replacement._png_length = len(replacement._png_data)
            for child in dst_node.children():
                replacement.add(clone_property(child, parent=replacement))
        merge_canvas_metadata_from_sources(replacement, node_path, source_imgs, existing_node=dst_node)
        parent = dst_img.root
        parts = node_path.split("/")
        for part in parts[:-1]:
            parent = ensure_subproperty(parent, part)
        parent.add(clone_property(replacement, parts[-1], parent))
        changed = True

    if not changed:
        return "skip-existing"
    backup(dst_path)
    atomic_write_bytes(dst_path, encode_image_body(dst_img, gms_reader()), dry_run)
    return "write"


def json_wz_to_xml_element(name: str, node: dict) -> ET.Element:
    kind = node.get("_dirType", "sub")
    if kind == "sub":
        out = ET.Element("imgdir", {"name": name})
        for child_name, child in node.items():
            if child_name.startswith("_"):
                continue
            out.append(json_wz_to_xml_element(child_name, child))
        return out
    if kind == "int":
        return ET.Element("int", {"name": name, "value": str(node.get("_value", "0"))})
    if kind == "float":
        return ET.Element("float", {"name": name, "value": str(node.get("_value", "0"))})
    if kind == "string":
        return ET.Element("string", {"name": name, "value": str(node.get("_value", ""))})
    if kind == "uol":
        return ET.Element("uol", {"name": name, "value": str(node.get("_value", ""))})
    if kind == "vector":
        x_node = node.get("x", {})
        y_node = node.get("y", {})
        return ET.Element(
            "vector",
            {
                "name": name,
                "x": str(x_node.get("_value", node.get("_x", "0"))),
                "y": str(y_node.get("_value", node.get("_y", "0"))),
            },
        )
    raise TypeError(f"unsupported JSON WZ type {kind!r} at {name}")


def json_wz_to_xml(src_path: Path, dst_path: Path, root_name: str, dry_run: bool, overwrite: bool = False) -> str:
    if dst_path.exists() and not overwrite:
        return "skip-existing"
    data = json.loads(src_path.read_text(encoding="utf-8"))
    root = ET.Element("imgdir", {"name": root_name})
    for child_name, child in data.items():
        if child_name.startswith("_"):
            continue
        root.append(json_wz_to_xml_element(child_name, child))
    backup(dst_path)
    if dry_run:
        print(f"[dry-run] write {dst_path}")
        return "write"
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    with tempfile.NamedTemporaryFile(prefix=f".{dst_path.name}.", suffix=".tmp", dir=dst_path.parent, delete=False) as tmp:
        tmp.write(b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n')
        tree.write(tmp, encoding="utf-8", xml_declaration=False, short_empty_elements=True)
        tmp_path = Path(tmp.name)
    tmp_path.replace(dst_path)
    return "write"


def direct_xml_child(parent: ET.Element, name: str) -> ET.Element | None:
    for child in parent:
        if child.get("name") == name:
            return child
    return None


def ensure_xml_int(parent: ET.Element, name: str, value: int, after_name: str | None = None) -> bool:
    existing = direct_xml_child(parent, name)
    if existing is not None:
        if existing.tag == "int" and existing.get("value") == str(value):
            return False
        existing.tag = "int"
        existing.set("value", str(value))
        return True
    node = ET.Element("int", {"name": name, "value": str(value)})
    if after_name is not None:
        for idx, child in enumerate(list(parent)):
            if child.get("name") == after_name:
                parent.insert(idx + 1, node)
                return True
    parent.append(node)
    return True


def set_akayrum_boss_skill_entries(info: ET.Element) -> bool:
    existing = direct_xml_child(info, "skill")
    if existing is None:
        existing = ET.Element("imgdir", {"name": "skill"})
        info.append(existing)
    old_xml = ET.tostring(existing, encoding="unicode")
    existing.clear()
    existing.tag = "imgdir"
    existing.set("name", "skill")
    for idx, entry in enumerate(AKAYRUM_BOSS_SKILLS):
        node = ET.SubElement(existing, "imgdir", {"name": str(idx)})
        for key, value in entry.items():
            ET.SubElement(node, "int", {"name": key, "value": str(value)})
    return ET.tostring(existing, encoding="unicode") != old_xml


def set_akayrum_boss_attack_entries(info: ET.Element) -> bool:
    existing = direct_xml_child(info, "attack")
    if not AKAYRUM_BOSS_ATTACKS:
        if existing is None:
            return False
        info.remove(existing)
        return True
    if existing is None:
        existing = ET.Element("imgdir", {"name": "attack"})
        info.append(existing)
    old_xml = ET.tostring(existing, encoding="unicode")
    existing.clear()
    existing.tag = "imgdir"
    existing.set("name", "attack")
    for idx, entry in enumerate(AKAYRUM_BOSS_ATTACKS):
        node = ET.SubElement(existing, "imgdir", {"name": str(idx)})
        for key, value in entry.items():
            ET.SubElement(node, "int", {"name": key, "value": str(value)})
    return ET.tostring(existing, encoding="unicode") != old_xml


def remove_xml_child(parent: ET.Element, name: str) -> bool:
    existing = direct_xml_child(parent, name)
    if existing is None:
        return False
    parent.remove(existing)
    return True


def make_wz_scalar(kind: str, name: str, value, parent: WzSubProperty):
    if kind == "int":
        return WzIntProperty(name, int(value), parent)
    if kind == "float":
        return WzFloatProperty(name, float(value), parent)
    if kind == "string":
        return WzStringProperty(name, str(value), parent)
    raise ValueError(f"unsupported scalar kind: {kind}")


def build_akayrum_boss_client_info(parent: WzSubProperty) -> WzSubProperty:
    info = WzSubProperty("info", parent)
    for kind, name, value in AKAYRUM_BOSS_CLIENT_INFO:
        info.add(make_wz_scalar(kind, name, value, info))

    skill = WzSubProperty("skill", info)
    for idx, entry in enumerate(AKAYRUM_BOSS_SKILLS):
        node = WzSubProperty(str(idx), skill)
        for key, value in entry.items():
            node.add(WzIntProperty(key, int(value), node))
        skill.add(node)
    info.add(skill)

    if AKAYRUM_BOSS_ATTACKS:
        attack = WzSubProperty("attack", info)
        for idx, entry in enumerate(AKAYRUM_BOSS_ATTACKS):
            node = WzSubProperty(str(idx), attack)
            for key, value in entry.items():
                node.add(WzIntProperty(key, int(value), node))
            attack.add(node)
        info.add(attack)
    return info


def property_signature(prop):
    if prop is None:
        return None
    if hasattr(prop, "children") and prop.children():
        return (type(prop).__name__, prop.name, tuple(property_signature(child) for child in prop.children()))
    return (type(prop).__name__, prop.name, getattr(prop, "value", None))


def default_frame_delay(path: str) -> int:
    top = path.split("/", 1)[0]
    if top.startswith("skill") or top.startswith("attack"):
        return 90
    if top in {"hit1"}:
        return 100
    return 120


def patch_canvas_frame_metadata(canvas: WzCanvasProperty, path: str) -> bool:
    changed = False
    width = int(canvas.width or 1)
    height = int(canvas.height or 1)
    origin_x = max(0, width // 2)
    origin_y = max(0, height)
    if canvas.child("origin") is None:
        canvas.add(WzVectorProperty("origin", origin_x, origin_y, canvas))
        changed = True
    if canvas.child("head") is None:
        canvas.add(WzVectorProperty("head", -1, -min(80, origin_y), canvas))
        changed = True
    if canvas.child("lt") is None:
        canvas.add(WzVectorProperty("lt", -origin_x, -origin_y, canvas))
        changed = True
    if canvas.child("rb") is None:
        canvas.add(WzVectorProperty("rb", width - origin_x, height - origin_y, canvas))
        changed = True
    if canvas.child("delay") is None:
        canvas.add(WzIntProperty("delay", default_frame_delay(path), canvas))
        changed = True
    return changed


def patch_action_zero_frame(action: WzSubProperty) -> bool:
    frame_names = sorted(int(child.name) for child in action.children() if child.name.isdigit())
    if not frame_names or frame_names[0] == 0:
        return False
    first = action.child(str(frame_names[0]))
    if first is None:
        return False
    action.add(clone_property(first, "0", action))
    return True


def remove_wz_child(parent: WzSubProperty, name: str) -> bool:
    if parent.child(name) is None:
        return False
    parent._children.pop(name, None)
    return True


def compatible_akayrum_action_info_xml(action_name: str, source_json: dict) -> ET.Element | None:
    if not action_name.startswith("attack"):
        return None
    info_json = source_json.get(action_name, {}).get("info")
    if not isinstance(info_json, dict):
        return None
    info = ET.Element("imgdir", {"name": "info"})
    for child_name in AKAYRUM_BOSS_ATTACK_INFO_FIELDS:
        child = info_json.get(child_name)
        if isinstance(child, dict):
            info.append(json_wz_to_xml_element(child_name, child))
    return info if len(info) else None


def build_compatible_akayrum_extra_action(
    source_action,
    action_name: str,
    source_json: dict,
    parent: WzSubProperty,
) -> WzSubProperty:
    out = WzSubProperty(action_name, parent)
    info_xml = compatible_akayrum_action_info_xml(action_name, source_json)
    if info_xml is not None:
        info_prop = xml_to_property(info_xml, out)
        out.add(info_prop)
    for child in source_action.children():
        if not isinstance(child, (WzCanvasProperty, WzUolProperty)):
            continue
        new_child = clone_property_from_region(child, SOURCE_273_REGION, child.name, out)
        if isinstance(new_child, WzCanvasProperty):
            patch_canvas_frame_metadata(new_child, f"{action_name}/{child.name}")
        out.add(new_child)
    return out


def set_compatible_akayrum_extra_action_xml(root: ET.Element, source_json: dict) -> bool:
    changed = False
    for action_name in AKAYRUM_BOSS_EXTRA_ACTIONS:
        existing = direct_xml_child(root, action_name)
        old_xml = ET.tostring(existing, encoding="unicode") if existing is not None else ""
        new_action = ET.Element("imgdir", {"name": action_name})
        info = compatible_akayrum_action_info_xml(action_name, source_json)
        if info is not None:
            new_action.append(info)
        if existing is None:
            root.append(new_action)
            changed = True
        elif ET.tostring(new_action, encoding="unicode") != old_xml:
            existing.clear()
            existing.tag = "imgdir"
            existing.set("name", action_name)
            for child in new_action:
                existing.append(child)
            changed = True
    return changed


def normalize_mob_delay_xml(root: ET.Element) -> bool:
    changed = False
    for node in root.iter("string"):
        if node.get("name") == "delay" and (node.get("value") or "").isdigit():
            node.tag = "int"
            changed = True
    return changed


def patch_mob_delay_compat(dry_run: bool) -> str:
    changed = False
    for mob_id in MOB_IDS:
        xml_path = ROOT / "gms-server" / "wz" / "Mob.wz" / f"{mob_id}.img.xml"
        if not xml_path.exists():
            continue
        root = ET.parse(xml_path).getroot()
        if not normalize_mob_delay_xml(root):
            continue
        changed = True
        backup(xml_path)
        if dry_run:
            print(f"[dry-run] patch {xml_path}")
            continue
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        with tempfile.NamedTemporaryFile(prefix=f".{xml_path.name}.", suffix=".tmp", dir=xml_path.parent, delete=False) as tmp:
            tmp.write(b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n')
            tree.write(tmp, encoding="utf-8", xml_declaration=False, short_empty_elements=True)
            tmp_path = Path(tmp.name)
        tmp_path.replace(xml_path)

    for mob_id in MOB_IDS:
        client_path = ROOT / "clien" / "Data" / "Mob" / f"{mob_id}.img"
        if not client_path.exists():
            continue
        img = WzImage.from_bytes(client_path.read_bytes(), key=TARGET_KEY, name=client_path.name)
        img.parse()
        img_changed = False
        for node in list(iter_properties(img.root)):
            if isinstance(node, WzStringProperty) and node.name == "delay" and str(node.value).isdigit():
                parent = node.parent
                if parent is None:
                    continue
                parent.add(WzIntProperty("delay", int(node.value), parent))
                img_changed = True
        if not img_changed:
            continue
        changed = True
        backup(client_path)
        atomic_write_bytes(client_path, encode_image_body(img, gms_reader()), dry_run)
    return "write" if changed else "skip-existing"


def patch_akayrum_mob_type_compat(dry_run: bool) -> str:
    changed = False
    for mob_id in [8220020, 9300301]:
        xml_path = ROOT / "gms-server" / "wz" / "Mob.wz" / f"{mob_id}.img.xml"
        if not xml_path.exists():
            continue
        root = ET.parse(xml_path).getroot()
        info = direct_xml_child(root, "info")
        mob_type = direct_xml_child(info, "mobType") if info is not None else None
        if mob_type is not None and mob_type.get("value") == "5N":
            mob_type.set("value", "4N")
            changed = True
            backup(xml_path)
            if dry_run:
                print(f"[dry-run] patch {xml_path}")
            else:
                tree = ET.ElementTree(root)
                ET.indent(tree, space="  ")
                with tempfile.NamedTemporaryFile(prefix=f".{xml_path.name}.", suffix=".tmp", dir=xml_path.parent, delete=False) as tmp:
                    tmp.write(b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n')
                    tree.write(tmp, encoding="utf-8", xml_declaration=False, short_empty_elements=True)
                    tmp_path = Path(tmp.name)
                tmp_path.replace(xml_path)

        client_path = ROOT / "clien" / "Data" / "Mob" / f"{mob_id}.img"
        if not client_path.exists():
            continue
        img = WzImage.from_bytes(client_path.read_bytes(), key=TARGET_KEY, name=client_path.name)
        img.parse()
        client_mob_type = img.get("info/mobType")
        if isinstance(client_mob_type, WzStringProperty) and client_mob_type.value == "5N":
            parent = client_mob_type.parent
            if parent is not None:
                parent.add(WzStringProperty("mobType", "4N", parent))
                changed = True
                backup(client_path)
                atomic_write_bytes(client_path, encode_image_body(img, gms_reader()), dry_run)
    return "write" if changed else "skip-existing"


def patch_akayrum_boss_compat(dry_run: bool) -> str:
    xml_path = ROOT / "gms-server" / "wz" / "Mob.wz" / f"{AKAYRUM_BOSS_ID}.img.xml"
    source_json_path = SRC_273_JSON / "Mob" / f"{AKAYRUM_BOSS_ID}.json"
    root = ET.parse(xml_path).getroot()
    info = direct_xml_child(root, "info")
    if info is None:
        raise RuntimeError(f"{xml_path} missing info")
    source_json = json.loads(source_json_path.read_text(encoding="utf-8")) if source_json_path.exists() else {}
    changed = False
    changed |= ensure_xml_int(info, "PDDamage", 1700, "PADamage")
    changed |= ensure_xml_int(info, "MDDamage", 1980, "MADamage")
    changed |= ensure_xml_int(info, "speed", -50, "maxMP")
    changed |= ensure_xml_int(info, "pushed", 140000, "eva")
    changed |= ensure_xml_int(info, "undead", 0, "mpRecovery")
    changed |= ensure_xml_int(info, "summonType", 12, "fs")
    changed |= ensure_xml_int(info, "publicReward", 1, "boss")
    changed |= ensure_xml_int(info, "mobType", 1, "hpTagBgcolor")
    changed |= ensure_xml_int(info, "rareItemDropLevel", 3, "mobType")
    changed |= set_akayrum_boss_skill_entries(info)
    changed |= set_akayrum_boss_attack_entries(info)
    changed |= remove_xml_child(info, "revive")
    for old_name in [
        "finalmaxHP",
        "ignoreFieldOut",
        "HPgaugeHide",
        "PDRate",
        "MDRate",
        "category",
        "charismaEXP",
        "ignoreMoveImpact",
        "wp",
    ]:
        changed |= remove_xml_child(info, old_name)
    for old_name in [
        "attack2",
        "attack3",
        "attack4",
        "skill3",
        "skill4",
        "skill5",
        "skill6",
        "skill7",
        "skill8",
        "skill9",
        "skill10",
        "skill11",
    ]:
        if old_name not in AKAYRUM_BOSS_EXTRA_ACTIONS:
            changed |= remove_xml_child(root, old_name)
    changed |= set_compatible_akayrum_extra_action_xml(root, source_json)
    if not changed:
        return "skip-existing"
    backup(xml_path)
    if dry_run:
        print(f"[dry-run] patch {xml_path}")
        return "write"
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    with tempfile.NamedTemporaryFile(prefix=f".{xml_path.name}.", suffix=".tmp", dir=xml_path.parent, delete=False) as tmp:
        tmp.write(b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n')
        tree.write(tmp, encoding="utf-8", xml_declaration=False, short_empty_elements=True)
        tmp_path = Path(tmp.name)
    tmp_path.replace(xml_path)
    return "write"


def patch_akayrum_boss_client_info_compat(dry_run: bool) -> str:
    client_path = ROOT / "clien" / "Data" / "Mob" / f"{AKAYRUM_BOSS_ID}.img"
    img = WzImage.from_bytes(client_path.read_bytes(), key=TARGET_KEY, name=client_path.name)
    img.parse()
    old_info = img.get("info")
    new_info = build_akayrum_boss_client_info(img.root)
    if old_info is not None and property_signature(old_info) == property_signature(new_info):
        return "skip-existing"
    img.root.add(new_info)
    backup(client_path)
    atomic_write_bytes(client_path, encode_image_body(img, gms_reader()), dry_run)
    return "write"


def patch_akayrum_boss_gauge_compat(dry_run: bool) -> str:
    ui_path = ROOT / "clien" / "Data" / "UI" / "UIWindow.img"
    img = WzImage.from_bytes(ui_path.read_bytes(), key=TARGET_KEY, name=ui_path.name)
    img.parse()
    gauge = img.get(f"MobGage/Mob/{AKAYRUM_BOSS_ID}")
    if not isinstance(gauge, WzCanvasProperty) or gauge.child("delay") is not None:
        return "skip-existing"
    gauge.add(WzIntProperty("delay", 500, gauge))
    backup(ui_path)
    atomic_write_bytes(ui_path, encode_image_body(img, gms_reader()), dry_run)
    return "write"


def patch_akayrum_boss_extra_actions_compat(dry_run: bool) -> str:
    client_path = ROOT / "clien" / "Data" / "Mob" / f"{AKAYRUM_BOSS_ID}.img"
    canvas_path = SRC_273_CANVAS / "Mob" / "_Canvas" / f"{AKAYRUM_BOSS_ID}.img"
    json_path = SRC_273_JSON / "Mob" / f"{AKAYRUM_BOSS_ID}.json"
    if not canvas_path.exists() or not json_path.exists():
        return "skip-missing"

    img = WzImage.from_bytes(client_path.read_bytes(), key=TARGET_KEY, name=client_path.name)
    img.parse()
    source = WzImage.from_bytes(
        canvas_path.read_bytes(),
        key=WzKey.for_region(SOURCE_273_REGION),
        name=canvas_path.name,
    )
    source.parse()
    source_json = json.loads(json_path.read_text(encoding="utf-8"))

    changed = False
    for action_name in AKAYRUM_BOSS_EXTRA_ACTIONS:
        source_action = source.get(action_name)
        if source_action is None:
            raise RuntimeError(f"{canvas_path} missing {action_name}")
        new_action = build_compatible_akayrum_extra_action(source_action, action_name, source_json, img.root)

        old_action = img.get(action_name)
        if property_signature(old_action) == property_signature(new_action):
            continue
        img.root.add(new_action)
        changed = True

    if not changed:
        return "skip-existing"
    backup(client_path)
    atomic_write_bytes(client_path, encode_image_body(img, gms_reader()), dry_run)
    return "write"


def patch_akayrum_boss_visual_template_compat(dry_run: bool) -> str:
    client_path = ROOT / "clien" / "Data" / "Mob" / f"{AKAYRUM_BOSS_ID}.img"
    template_path = ROOT / "clien" / "Data" / "Mob" / f"{AKAYRUM_SUMMON_TEMPLATE_ID}.img"
    if not template_path.exists():
        return "skip-existing"
    img = WzImage.from_bytes(client_path.read_bytes(), key=TARGET_KEY, name=client_path.name)
    img.parse()
    template = WzImage.from_bytes(template_path.read_bytes(), key=TARGET_KEY, name=template_path.name)
    template.parse()
    old_signature = [
        property_signature(child)
        for child in img.root.children()
        if child.name != "info" and child.name not in AKAYRUM_BOSS_EXTRA_ACTIONS
    ]
    template_signature = [
        property_signature(child) for child in template.root.children() if child.name != "info"
    ]
    if old_signature == template_signature:
        return "skip-existing"
    for child in list(img.root.children()):
        if child.name != "info":
            remove_wz_child(img.root, child.name)
    for child in template.root.children():
        if child.name != "info":
            img.root.add(clone_property(child, child.name, img.root))
    backup(client_path)
    atomic_write_bytes(client_path, encode_image_body(img, gms_reader()), dry_run)
    return "write"


def patch_akayrum_boss_canvas_metadata_compat(dry_run: bool) -> str:
    client_path = ROOT / "clien" / "Data" / "Mob" / f"{AKAYRUM_BOSS_ID}.img"
    img = WzImage.from_bytes(client_path.read_bytes(), key=TARGET_KEY, name=client_path.name)
    img.parse()
    changed = False
    for path, prop in ((path, prop) for path, prop in iter_named_properties(img.root) if isinstance(prop, WzCanvasProperty)):
        changed |= patch_canvas_frame_metadata(prop, path)
    if not changed:
        return "skip-existing"
    backup(client_path)
    atomic_write_bytes(client_path, encode_image_body(img, gms_reader()), dry_run)
    return "write"


def patch_akayrum_boss_action_sequence_compat(dry_run: bool) -> str:
    client_path = ROOT / "clien" / "Data" / "Mob" / f"{AKAYRUM_BOSS_ID}.img"
    img = WzImage.from_bytes(client_path.read_bytes(), key=TARGET_KEY, name=client_path.name)
    img.parse()
    changed = False
    for action in img.root.children():
        if isinstance(action, WzSubProperty) and (
            action.name.startswith("attack")
            or action.name.startswith("skill")
            or action.name in {"stand", "move", "hit1", "die1", "summon"}
        ):
            changed |= patch_action_zero_frame(action)
    if not changed:
        return "skip-existing"
    backup(client_path)
    atomic_write_bytes(client_path, encode_image_body(img, gms_reader()), dry_run)
    return "write"


def patch_akayrum_boss_summon_metadata_compat(dry_run: bool) -> str:
    client_path = ROOT / "clien" / "Data" / "Mob" / f"{AKAYRUM_BOSS_ID}.img"
    template_path = ROOT / "clien" / "Data" / "Mob" / f"{AKAYRUM_SUMMON_TEMPLATE_ID}.img"
    if not template_path.exists():
        return "skip-existing"
    img = WzImage.from_bytes(client_path.read_bytes(), key=TARGET_KEY, name=client_path.name)
    img.parse()
    template = WzImage.from_bytes(template_path.read_bytes(), key=TARGET_KEY, name=template_path.name)
    template.parse()
    summon = img.get("summon")
    template_summon = template.get("summon")
    if summon is None or template_summon is None:
        return "skip-existing"
    changed = False
    for frame in summon.children():
        if not isinstance(frame, WzCanvasProperty):
            continue
        template_frame = template_summon.child(frame.name)
        if not isinstance(template_frame, WzCanvasProperty):
            continue
        source_metadata = [
            child for child in template_frame.children() if child.name in {"origin", "head", "delay"}
        ]
        target_signature = [
            property_signature(frame.child(child.name)) for child in source_metadata
        ]
        source_signature = [property_signature(child) for child in source_metadata]
        target_order = [child.name for child in frame.children() if child.name in {"origin", "head", "delay"}]
        source_order = [child.name for child in source_metadata]
        if target_signature != source_signature or target_order != source_order:
            for metadata_name in ["origin", "head", "delay"]:
                remove_wz_child(frame, metadata_name)
            for source in source_metadata:
                frame.add(clone_property(source, source.name, frame))
            changed = True
        changed |= remove_wz_child(frame, "lt")
        changed |= remove_wz_child(frame, "rb")
    if not changed:
        return "skip-existing"
    backup(client_path)
    atomic_write_bytes(client_path, encode_image_body(img, gms_reader()), dry_run)
    return "write"


def patch_twisted_temple_entrance_life_compat(dry_run: bool) -> str:
    map_id = 272020000
    xml_path = ROOT / "gms-server" / "wz" / "Map.wz" / "Map" / "Map2" / f"{map_id}.img.xml"
    client_path = ROOT / "clien" / "Data" / "Map" / "Map" / "Map2" / f"{map_id}.img"
    src_path = SRC / "map" / f"{map_id}.img.xml"
    root = ET.parse(xml_path).getroot()
    src_root = ET.parse(src_path).getroot()
    life = direct_xml_child(root, "life")
    src_life = direct_xml_child(src_root, "life")
    if src_life is None:
        return "skip-existing"
    old_xml = ET.tostring(life, encoding="unicode") if life is not None else ""
    new_life = ET.fromstring(ET.tostring(src_life, encoding="utf-8"))
    if life is None:
        root.append(new_life)
    else:
        life.clear()
        life.set("name", "life")
        for child in new_life:
            life.append(child)
    if ET.tostring(direct_xml_child(root, "life"), encoding="unicode") == old_xml:
        return "skip-existing"
    backup(xml_path)
    if dry_run:
        print(f"[dry-run] patch {xml_path}")
        print(f"[dry-run] rebuild {client_path}")
        return "write"
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    with tempfile.NamedTemporaryFile(prefix=f".{xml_path.name}.", suffix=".tmp", dir=xml_path.parent, delete=False) as tmp:
        tmp.write(b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n')
        tree.write(tmp, encoding="utf-8", xml_declaration=False, short_empty_elements=True)
        tmp_path = Path(tmp.name)
    tmp_path.replace(xml_path)
    return xml_to_img(xml_path, client_path, dry_run, overwrite=True)


def patch_string_mob(dry_run: bool) -> str:
    xml_path = ROOT / "gms-server/wz/String.wz/Mob.img.xml"
    client_path = ROOT / "clien/Data/String/Mob.img"
    text = xml_path.read_text(encoding="utf-8")
    changed = False
    names = {
        "8220016": "墮落的翼龍",
        "8220017": "墮落的龍戰士",
        "8220018": "墮落的化石龍",
        "8220019": "墮落的半人馬",
        "8220020": "墮落的時間守護隊長",
        "8220021": "墮落的時間的神官",
        "8860000": "阿卡伊勒",
        "9300304": "阿卡伊勒",
    }
    for mob_id, mob_name in names.items():
        block_pattern = re.compile(
            rf'  <imgdir name="{re.escape(mob_id)}">\n'
            rf'    <string name="name" value="[^"]*"/>\n'
            rf'  </imgdir>'
        )
        replacement = f'  <imgdir name="{mob_id}">\n    <string name="name" value="{mob_name}"/>\n  </imgdir>'
        match = block_pattern.search(text)
        if match is not None:
            if match.group(0) != replacement:
                text = text[: match.start()] + replacement + text[match.end() :]
                changed = True
            continue
        insert = replacement + "\n"
        marker = "</imgdir>"
        idx = text.rfind(marker)
        if idx < 0:
            raise RuntimeError(f"{xml_path} missing root closing imgdir")
        text = text[:idx] + insert + text[idx:]
        changed = True
    if not changed:
        return "skip-existing"
    backup(xml_path)
    if dry_run:
        print(f"[dry-run] patch {xml_path}")
        print(f"[dry-run] rebuild {client_path}")
        return "write"
    with tempfile.NamedTemporaryFile(prefix=f".{xml_path.name}.", suffix=".tmp", dir=xml_path.parent, delete=False) as tmp:
        tmp.write(text.encode("utf-8"))
        tmp_path = Path(tmp.name)
    tmp_path.replace(xml_path)
    return xml_to_img(xml_path, client_path, dry_run, overwrite=True)


def patch_string_npc(dry_run: bool) -> str:
    xml_path = ROOT / "gms-server/wz/String.wz/Npc.img.xml"
    client_path = ROOT / "clien/Data/String/Npc.img"
    src_path = SRC_273_JSON / "String" / "Npc.json"
    if not src_path.exists():
        return "skip-missing"

    wanted_ids = [str(npc_id) for npc_id in NPC_IDS]
    data = json.loads(src_path.read_text(encoding="utf-8"))
    text = xml_path.read_text(encoding="utf-8")
    changed = False

    for npc_id in wanted_ids:
        if direct_xml_child(ET.fromstring(text), npc_id) is not None:
            continue
        node = data.get(npc_id)
        if node is None:
            continue
        insert = ET.tostring(json_wz_to_xml_element(npc_id, node), encoding="unicode", short_empty_elements=True) + "\n"
        marker = "</imgdir>"
        idx = text.rfind(marker)
        if idx < 0:
            raise RuntimeError(f"{xml_path} missing root closing imgdir")
        text = text[:idx] + insert + text[idx:]
        changed = True

    if not changed:
        return "skip-existing"
    backup(xml_path)
    if dry_run:
        print(f"[dry-run] patch {xml_path}")
        print(f"[dry-run] rebuild {client_path}")
        return "write"
    with tempfile.NamedTemporaryFile(prefix=f".{xml_path.name}.", suffix=".tmp", dir=xml_path.parent, delete=False) as tmp:
        tmp.write(text.encode("utf-8"))
        tmp_path = Path(tmp.name)
    tmp_path.replace(xml_path)
    return xml_to_img(xml_path, client_path, dry_run, overwrite=True)


def migrate_273_boss(dry_run: bool) -> dict[str, int]:
    stats: dict[str, int] = {}

    def count(status: str) -> None:
        stats[status] = stats.get(status, 0) + 1

    mob_json = SRC_273_JSON / "Mob" / f"{AKAYRUM_BOSS_ID}.json"
    mob_canvas = SRC_273_CANVAS / "Mob" / "_Canvas" / f"{AKAYRUM_BOSS_ID}.img"
    if not mob_json.exists() or not mob_canvas.exists():
        print(f"273 boss migration: missing {AKAYRUM_BOSS_ID} source files, skipped")
        return stats

    count(
        json_wz_to_xml(
            mob_json,
            ROOT / "gms-server" / "wz" / "Mob.wz" / f"{AKAYRUM_BOSS_ID}.img.xml",
            f"{AKAYRUM_BOSS_ID}.img",
            dry_run,
        )
    )
    count(patch_akayrum_boss_compat(dry_run))
    count(
        reencode_region_img(
            mob_canvas,
            ROOT / "clien" / "Data" / "Mob" / f"{AKAYRUM_BOSS_ID}.img",
            dry_run,
            SOURCE_273_REGION,
        )
    )
    count(patch_akayrum_boss_visual_template_compat(dry_run))
    count(patch_akayrum_boss_extra_actions_compat(dry_run))
    count(patch_akayrum_boss_client_info_compat(dry_run))
    count(patch_akayrum_boss_gauge_compat(dry_run))
    count(patch_string_mob(dry_run))
    return stats


def patch_maphelper_marks(dry_run: bool) -> str:
    dst_path = ROOT / "clien/Data/Map/MapHelper.img"
    dst_img = WzImage.from_bytes(dst_path.read_bytes(), key=TARGET_KEY, name="MapHelper.img")
    dst_img.parse()
    mark_root = dst_img.get("mark")
    source = dst_img.get("mark/TimeTemple")
    if mark_root is None or source is None:
        raise RuntimeError("MapHelper.img missing mark/TimeTemple")
    changed = False
    for mark_name in ["Akairum", "Akayrum"]:
        if dst_img.get(f"mark/{mark_name}") is None:
            mark_root.add(clone_property(source, mark_name, mark_root))
            changed = True
    if not changed:
        return "skip-existing"
    backup(dst_path)
    atomic_write_bytes(dst_path, encode_image_body(dst_img, gms_reader()), dry_run)
    return "write"


def migrate(dry_run: bool, overwrite_existing_common: bool) -> None:
    stats: dict[str, int] = {}

    def count(status: str) -> None:
        stats[status] = stats.get(status, 0) + 1

    for map_id in MAP_IDS:
        src_xml = SRC / "map" / f"{map_id}.img.xml"
        count(copy_file(src_xml, ROOT / f"gms-server/wz/Map.wz/Map/Map2/{map_id}.img.xml", dry_run))
        count(xml_to_img(src_xml, ROOT / f"clien/Data/Map/Map/Map2/{map_id}.img", dry_run))

    for mob_id in MOB_IDS:
        src_xml = SRC / "mob" / f"{mob_id}.img.xml"
        overwrite = mob_id in FORCE_SOURCE_MOB_IDS
        count(copy_file(src_xml, ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml", dry_run, overwrite=overwrite))
        count(xml_to_img(src_xml, ROOT / f"clien/Data/Mob/{mob_id}.img", dry_run, overwrite=overwrite))
    count(patch_mob_delay_compat(dry_run))
    count(patch_akayrum_mob_type_compat(dry_run))

    for npc_id in NPC_IDS:
        src_xml = SRC / "npc" / f"{npc_id}.img.xml"
        count(copy_file(src_xml, ROOT / f"gms-server/wz/Npc.wz/{npc_id}.img.xml", dry_run))
        count(xml_to_img(src_xml, ROOT / f"clien/Data/Npc/{npc_id}.img", dry_run))

    for src_subdir, dst_subdir in [("back", "Back"), ("obj", "Obj"), ("tile", "Tile")]:
        for src_img in sorted((SRC / src_subdir).glob("*.img")):
            dst = ROOT / f"clien/Data/Map/{dst_subdir}/{src_img.name}"
            count(reencode_source_img(src_img, dst, dry_run, overwrite=overwrite_existing_common))

    count(patch_referenced_obj_nodes(dry_run))
    count(patch_referenced_back_nodes(dry_run))
    count(patch_referenced_tile_nodes(dry_run))
    count(patch_bgm22(dry_run))
    count(patch_shown_at_minimap(dry_run))
    count(patch_acc10_nodes(dry_run))
    count(patch_twisted_temple_entrance_life_compat(dry_run))
    count(patch_referenced_common_file_canvases(dry_run))
    count(patch_string_npc(dry_run))
    count(patch_maphelper_marks(dry_run))
    for status, status_count in migrate_273_boss(dry_run).items():
        stats[status] = stats.get(status, 0) + status_count

    print("migration stats:", " ".join(f"{k}={v}" for k, v in sorted(stats.items())))


def iter_canvases(prop) -> Iterable[WzCanvasProperty]:
    if isinstance(prop, WzCanvasProperty):
        yield prop
    if hasattr(prop, "children"):
        for child in prop.children():
            yield from iter_canvases(child)


def audit_img(path: Path) -> tuple[int, int]:
    img = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=path.name)
    img.parse()
    bad = 0
    total = 0
    for canvas in iter_canvases(img.root):
        if not canvas.has_pixels():
            continue
        total += 1
        try:
            decode_canvas(canvas, region="GMS")
        except Exception:
            bad += 1
    return total, bad


def direct_child(parent: ET.Element, name: str) -> ET.Element | None:
    for child in parent:
        if child.get("name") == name:
            return child
    return None


def text_child(parent: ET.Element, name: str) -> str | None:
    child = direct_child(parent, name)
    return child.get("value") if child is not None else None


def audit_references() -> None:
    missing: dict[str, set[str]] = {}
    maphelper = ROOT / "clien/Data/Map/MapHelper.img"
    maphelper_img = WzImage.from_bytes(maphelper.read_bytes(), key=TARGET_KEY, name=maphelper.name)
    maphelper_img.parse()

    def miss(key: str, owner: str) -> None:
        missing.setdefault(key, set()).add(owner)

    for map_id in MAP_IDS:
        path = ROOT / f"gms-server/wz/Map.wz/Map/Map2/{map_id}.img.xml"
        root = ET.parse(path).getroot()
        info_root = direct_child(root, "info")
        map_mark = text_child(info_root, "mapMark") if info_root is not None else None
        if map_mark and maphelper_img.get(f"mark/{map_mark}") is None:
            miss(f"mapMark:{map_mark}", str(map_id))
        back_root = direct_child(root, "back")
        if back_root is not None:
            for node in back_root:
                b_s = text_child(node, "bS")
                if b_s and not (ROOT / f"clien/Data/Map/Back/{b_s}.img").exists():
                    miss(f"back:{b_s}.img", str(map_id))
        for layer_name in [str(i) for i in range(8)]:
            layer = direct_child(root, layer_name)
            if layer is None:
                continue
            info = direct_child(layer, "info")
            t_s = text_child(info, "tS") if info is not None else None
            if t_s and not (ROOT / f"clien/Data/Map/Tile/{t_s}.img").exists():
                miss(f"tile:{t_s}.img", str(map_id))
            obj_root = direct_child(layer, "obj")
            if obj_root is not None:
                for obj in obj_root:
                    o_s = text_child(obj, "oS")
                    obj_path = ROOT / f"clien/Data/Map/Obj/{o_s}.img" if o_s else None
                    if o_s and obj_path is not None and not obj_path.exists():
                        miss(f"obj:{o_s}.img", str(map_id))
                    if o_s and obj_path is not None and obj_path.exists():
                        obj_img = WzImage.from_bytes(obj_path.read_bytes(), key=TARGET_KEY, name=obj_path.name)
                        obj_img.parse()
                        l0 = text_child(obj, "l0")
                        l1 = text_child(obj, "l1")
                        l2 = text_child(obj, "l2")
                        if l0 and l1 and l2 and obj_img.get(f"{l0}/{l1}/{l2}") is None:
                            miss(f"obj_node:{o_s}/{l0}/{l1}/{l2}", str(map_id))
        life_root = direct_child(root, "life")
        if life_root is not None:
            for life in life_root:
                life_id = text_child(life, "id")
                life_type = text_child(life, "type")
                if not life_id:
                    continue
                if life_type == "m":
                    if not (ROOT / f"gms-server/wz/Mob.wz/{life_id}.img.xml").exists():
                        miss(f"mob_xml:{life_id}", str(map_id))
                    if not (ROOT / f"clien/Data/Mob/{life_id}.img").exists():
                        miss(f"mob_img:{life_id}", str(map_id))
                if life_type == "n":
                    if not (ROOT / f"gms-server/wz/Npc.wz/{life_id}.img.xml").exists():
                        miss(f"npc_xml:{life_id}", str(map_id))
                    if not (ROOT / f"clien/Data/Npc/{life_id}.img").exists():
                        miss(f"npc_img:{life_id}", str(map_id))

    if missing:
        print("reference audit: FAIL")
        for key, owners in sorted(missing.items()):
            sample = ",".join(sorted(owners)[:8])
            more = "" if len(owners) <= 8 else f",+{len(owners) - 8}"
            print(f"  {key}: {sample}{more}")
    else:
        print("reference audit: ok")


def audit_canvases() -> None:
    bad_files = []
    total_files = 0
    total_canvases = 0
    common_paths = [
        *(ROOT / f"clien/Data/Map/Obj/{name}.img" for name in collect_referenced_obj_nodes()),
        *(ROOT / f"clien/Data/Map/Back/{name}.img" for name in collect_referenced_back_nodes() if name),
        *(ROOT / f"clien/Data/Map/Tile/{name}.img" for name in collect_referenced_tile_nodes()),
    ]
    for path in [
        *(ROOT / "clien/Data/Map/Map/Map2").glob("272*.img"),
        *(ROOT / "clien/Data/Mob").glob("82200*.img"),
        ROOT / "clien/Data/Mob/8860000.img",
        *(ROOT / "clien/Data/Npc").glob("21440*.img"),
        ROOT / "clien/Data/Npc/1104209.img",
        ROOT / "clien/Data/Map/Back/timeCrack.img",
        ROOT / "clien/Data/Map/Back/timeTemplePast.img",
        ROOT / "clien/Data/Map/Obj/acc10.img",
        *common_paths,
    ]:
        if not path.exists():
            continue
        total_files += 1
        canvases, bad = audit_img(path)
        total_canvases += canvases
        if bad:
            bad_files.append((path, bad, canvases))
    if bad_files:
        print("canvas audit: FAIL")
        for path, bad, canvases in bad_files:
            print(f"  {path}: bad={bad}/{canvases}")
    else:
        print(f"canvas audit: ok files={total_files} canvases={total_canvases}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--overwrite-existing-common",
        action="store_true",
        help="Also overwrite existing shared Back/Obj/Tile IMG files. Default skips them.",
    )
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()

    if not SRC.exists():
        raise SystemExit(f"missing source directory: {SRC}")
    if not args.audit_only:
        migrate(args.dry_run, args.overwrite_existing_common)
    if not args.dry_run:
        audit_references()
        audit_canvases()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
