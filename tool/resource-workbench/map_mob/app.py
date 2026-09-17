#!/usr/bin/env python3
"""Local map and mob IMG/XML browser, previewer, comparer, and safe editor."""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
import xml.parsers.expat
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
_WZPY = _ROOT / "tool" / "wz-python"
_MIGRATION = _ROOT / "tool" / "scripts" / "migration"
for dependency in (_WZPY, _MIGRATION):
    if str(dependency) not in sys.path:
        sys.path.insert(0, str(dependency))
from flask import Flask, jsonify, render_template, request, send_file  # noqa: E402
from PIL import Image  # noqa: E402
from wzpy import (  # noqa: E402
    StaticWzKey,
    WzImage,
    WzKey,
    derive_keystream_from_property,
    detect_region_from_img,
)
from wzpy import writer as wz_writer  # noqa: E402
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.incremental_img import replace_img_record, scan_img  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.properties import (  # noqa: E402
    WzCanvasProperty,
    WzDoubleProperty,
    WzFloatProperty,
    WzIntProperty,
    WzLongProperty,
    WzNullProperty,
    WzProperty,
    WzShortProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
    WzVideoProperty,
)
from . import compat as map_compat  # noqa: E402
from . import server_control_help  # noqa: E402
from . import mob_skill_resolve  # noqa: E402
import migrate_arcane_river_expansion as arc  # noqa: E402

app = Flask(__name__)
_WRITE_LOCK = threading.Lock()
_ALLOWED_SUFFIXES = (".img", ".img.xml", ".xml", ".json")
_SCALAR_TYPES = {"short", "int", "long", "float", "double", "string", "uol", "vector"}
_TMS_ROOT = _ROOT.parent / "TMS"
_TMS_DATA = _ROOT.parent / "TMS" / "MapleStory-IMG" / "Data"
_MS_PACKS = _TMS_ROOT / "MapleStory" / "Data" / "Packs"
# Thin .NET shim: Java 21 + /Users/lizixian/Documents/mxd/orange-wz MsRawExtract (Snow2/ChaCha).
_MS_PROBE = _TMS_ROOT / "black_mage_report_tools" / "ms_probe" / "bin" / "Debug" / "net8.0" / "MSProbe.dll"
_MS_CACHE_ROOT = _TMS_ROOT / "ms-extract"
_LEGACY_MS_CACHE_ROOT = Path.home() / "Library" / "Caches" / "BeiDouMapMobWorkbench" / "ms"
# tool/scripts/migration/migrate_arcane_river_expansion.extract_mob 的落盘目录
_ARCANE_MOB_CACHE = Path("/private/tmp/arcane-river-mob-cache")
_DEFAULT_EXPORT_ROOT = Path.home() / "Downloads" / "MapMobWorkbenchExport"


def natural_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def resolve_repo_path(raw: str, *, must_exist: bool = True) -> Path:
    if not raw:
        raise ValueError("文件路径不能为空")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = _ROOT / path
    path = path.resolve()
    allowed_roots = (_ROOT.resolve(), Path.home().resolve())
    if not any(path == root or path.is_relative_to(root) for root in allowed_roots):
        raise ValueError("只允许读取当前项目或用户目录内的文件")
    if not path.name.lower().endswith(_ALLOWED_SUFFIXES):
        raise ValueError("仅支持 .img、.img.xml、.xml 和 .json 文件")
    if must_exist and not path.is_file():
        raise ValueError(f"文件不存在: {relative_path(path)}")
    return path


def browse_directory(raw: str) -> dict[str, Any]:
    path = Path(raw).expanduser() if raw else _ROOT
    if not path.is_absolute():
        path = _ROOT / path
    path = path.resolve()
    home = Path.home().resolve()
    if path.is_file():
        path = path.parent
    elif not path.exists() and path.parent.is_dir():
        path = path.parent
    if not (path == home or path.is_relative_to(home)):
        raise ValueError("文件浏览器只允许访问用户目录")
    if not path.is_dir():
        raise ValueError(f"目录不存在: {relative_path(path)}")
    items = []
    for child in path.iterdir():
        if child.name.startswith("."):
            continue
        try:
            resolved = child.resolve()
            if not (resolved == home or resolved.is_relative_to(home)):
                continue
            if child.is_dir():
                items.append({"name": child.name, "path": relative_path(resolved), "type": "directory"})
            elif child.is_file() and child.name.lower().endswith(_ALLOWED_SUFFIXES):
                items.append({"name": child.name, "path": relative_path(resolved), "type": "file", "size": child.stat().st_size})
        except OSError:
            continue
    items.sort(key=lambda item: (item["type"] != "directory", item["name"].lower()))
    parent = path.parent if path != home else None
    return {
        "path": relative_path(path),
        "parent": relative_path(parent) if parent is not None else None,
        "items": items,
    }


def require_repo_write(path: Path) -> None:
    if path != _ROOT and not path.is_relative_to(_ROOT):
        raise ValueError("项目外文件仅供浏览和对比，不允许写入")


def relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(_ROOT))
    except ValueError:
        return str(path)


def default_paths(kind: str, item_id: str) -> tuple[Path, Path]:
    if kind == "mob":
        tms = _TMS_DATA / "Mob" / f"{item_id}.img"
        tms_canvas = _TMS_DATA / "Mob" / "_Canvas" / f"{item_id}.img"
        return (
            _ROOT / "clien" / "Data" / "Mob" / f"{item_id}.img",
            tms_canvas if tms_canvas.is_file() else tms if tms.is_file() else tms_canvas,
        )
    if kind != "map" or not re.fullmatch(r"\d{9}", item_id):
        raise ValueError("地图 ID 必须是 9 位数字")
    bucket = f"Map{item_id[0]}"
    tms = _TMS_DATA / "Map" / "Map" / bucket / f"{item_id}.img"
    return (
        _ROOT / "clien" / "Data" / "Map" / "Map" / bucket / f"{item_id}.img",
        tms if tms.is_file() else _ROOT / "gms-server" / "wz" / "Map.wz" / "Map" / bucket / f"{item_id}.img.xml",
    )


def ms_pack_signature() -> tuple[tuple[str, int, int], ...]:
    return tuple(
        (str(path), path.stat().st_mtime_ns, path.stat().st_size)
        for path in sorted(_MS_PACKS.glob("Mob_*.ms"))
    )


@lru_cache(maxsize=4)
def _ms_mob_index_cached(
    signature: tuple[tuple[str, int, int], ...],
) -> dict[str, Path]:
    if not signature or not _MS_PROBE.is_file():
        return {}
    dotnet = shutil.which("dotnet")
    if not dotnet:
        return {}
    output: dict[str, Path] = {}
    failures: list[str] = []
    for pack_text, _mtime_ns, _size in signature:
        pack = Path(pack_text)
        result = subprocess.run(
            [dotnet, str(_MS_PROBE), str(pack), str(_MS_CACHE_ROOT), "--list"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr.strip() or result.stdout.strip()).splitlines()
            failures.append(f"{pack.name}: {detail[0] if detail else 'exit ' + str(result.returncode)}")
            continue
        for line in result.stdout.splitlines():
            match = re.fullmatch(r"Mob/(\d{7})\.img", line.strip(), re.IGNORECASE)
            if match:
                output.setdefault(match.group(1), pack)
    if not output:
        raise ValueError("无法读取任何 Mob MS 包: " + "; ".join(failures) if failures else "MS 包没有 Mob 条目")
    return output


def ms_mob_index() -> dict[str, Path]:
    return _ms_mob_index_cached(ms_pack_signature())


def _ms_extract_roots() -> tuple[Path, ...]:
    return (_MS_CACHE_ROOT, _LEGACY_MS_CACHE_ROOT, _ARCANE_MOB_CACHE)


def find_extracted_ms_mob(item_id: str) -> Path | None:
    """Find a previously unpacked MS logical record without calling MSProbe."""
    if not re.fullmatch(r"\d{7}", item_id):
        return None
    names = (f"Mob_{item_id}.img", f"{item_id}.img")
    for root in _ms_extract_roots():
        if not root.is_dir():
            continue
        for name in names:
            for candidate in (root / item_id / name, root / name):
                if candidate.is_file():
                    return candidate
        try:
            for child in root.iterdir():
                if not child.is_dir():
                    continue
                for name in names:
                    candidate = child / name
                    if candidate.is_file():
                        return candidate
        except OSError:
            continue
    return None


def _existing_ms_extract(item_id: str, pack: Path) -> Path | None:
    for root in _ms_extract_roots():
        target = root / pack.stem / f"Mob_{item_id}.img"
        if target.is_file():
            return target
    return find_extracted_ms_mob(item_id)


def extract_ms_mob(item_id: str) -> tuple[Path, Path] | None:
    if not re.fullmatch(r"\d{7}", item_id):
        raise ValueError("怪物 ID 必须是 7 位数字")
    cached = find_extracted_ms_mob(item_id)
    pack = ms_mob_index().get(item_id)
    if pack is None:
        if cached is None:
            return None
        load_image(cached)
        return cached, cached.parent
    target_dir = _MS_CACHE_ROOT / pack.stem
    target = target_dir / f"Mob_{item_id}.img"
    existing = _existing_ms_extract(item_id, pack) or cached
    if existing is not None and existing.stat().st_mtime_ns >= pack.stat().st_mtime_ns:
        if existing.resolve() != target.resolve():
            target_dir.mkdir(parents=True, exist_ok=True)
            if not target.is_file() or target.stat().st_mtime_ns < existing.stat().st_mtime_ns:
                atomic_write(target, existing.read_bytes(), backup=False)
            load_image(target)
            return target, pack
        load_image(existing)
        return existing, pack
    if not _MS_PROBE.is_file():
        raise ValueError(f"MSProbe 不存在: {_MS_PROBE}")
    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise ValueError("找不到 dotnet，无法读取 TMS MS 包")
    _MS_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".mob-extract-", dir=_MS_CACHE_ROOT) as directory:
        result = subprocess.run(
            [dotnet, str(_MS_PROBE), str(pack), directory, f"Mob/{item_id}.img"],
            capture_output=True,
            text=True,
            check=False,
        )
        extracted = Path(directory) / f"Mob_{item_id}.img"
        if result.returncode != 0 or not extracted.is_file():
            raise ValueError(
                f"无法从 {pack.name} 提取 {item_id}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        data = extracted.read_bytes()
        image = WzImage.from_bytes(data, key=key_for_data(data), name=f"{item_id}.img")
        image.parse()
        if image.truncated or image.parse_warnings:
            raise ValueError(
                f"MS 条目解析不完整: truncated={image.truncated}, "
                f"warnings={image.parse_warnings}"
            )
        target_dir.mkdir(parents=True, exist_ok=True)
        atomic_write(target, data, backup=False)
    return target, pack


@lru_cache(maxsize=4)
def _mob_names_cached(path_text: str, mtime_ns: int, size: int) -> dict[str, str]:
    del mtime_ns, size
    image = load_image(Path(path_text))
    output = {}
    for record in image.root.children():
        name = child_value(record if isinstance(record, WzSubProperty) else None, "name")
        if record.name.isdigit() and name:
            output[record.name] = str(name)
    return output


def mob_names(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    stat = path.stat()
    return _mob_names_cached(str(path.resolve()), stat.st_mtime_ns, stat.st_size)


def mob_source_summary(path: Path) -> dict[str, Any]:
    nodes, info = flatten_source(path)
    roots = sorted(
        (node_path for node_path in nodes if node_path and "/" not in node_path),
        key=natural_key,
    )
    return {
        "format": info["format"],
        "size": path.stat().st_size,
        "rootCount": len(roots),
        "roots": roots,
    }


def mob_source_options(item_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"\d{7}", item_id):
        raise ValueError("怪物 ID 必须是 7 位数字")
    client = _ROOT / "clien" / "Data" / "Mob" / f"{item_id}.img"
    direct = _TMS_DATA / "Mob" / f"{item_id}.img"
    canvas = _TMS_DATA / "Mob" / "_Canvas" / f"{item_id}.img"
    server = _ROOT / "gms-server" / "wz" / "Mob.wz" / f"{item_id}.img.xml"
    extracted = extract_ms_mob(item_id)
    sources = []

    def add_source(kind: str, label: str, path: Path, *, pack: Path | None = None) -> None:
        if not path.is_file():
            return
        sources.append({
            "kind": kind,
            "label": label,
            "path": relative_path(path),
            "pack": pack.name if pack else "",
            **mob_source_summary(path),
        })

    if extracted:
        add_source("ms", "MS 完整记录", extracted[0], pack=extracted[1])
    add_source("img", "TMS IMG", direct)
    add_source("canvas", "TMS Canvas", canvas)
    add_source("server", "服务端 XML", server)
    tms_names = mob_names(_TMS_DATA / "String" / "Mob.img")
    client_names = mob_names(_ROOT / "clien" / "Data" / "String" / "Mob.img")
    comparison = next(
        (source["path"] for source in sources if source["kind"] == "canvas"),
        next((source["path"] for source in sources if source["kind"] == "img"), relative_path(canvas)),
    )
    return {
        "id": item_id,
        "name": tms_names.get(item_id) or client_names.get(item_id) or "",
        "clientPath": relative_path(client),
        "clientExists": client.is_file(),
        "comparisonPath": comparison,
        "sources": sources,
        "msEntry": f"Mob/{item_id}.img" if extracted else "",
    }


def server_xml_for_client(path: Path) -> Path | None:
    try:
        relative = path.resolve().relative_to((_ROOT / "clien" / "Data").resolve())
    except ValueError:
        return None
    parts = relative.parts
    if len(parts) == 4 and parts[:2] == ("Map", "Map") and path.name.lower().endswith(".img"):
        return _ROOT / "gms-server" / "wz" / "Map.wz" / "Map" / parts[2] / f"{path.name}.xml"
    if len(parts) == 2 and parts[0] == "Mob" and path.name.lower().endswith(".img"):
        return _ROOT / "gms-server" / "wz" / "Mob.wz" / f"{path.name}.xml"
    return None


def key_for_data(data: bytes):
    region = detect_region_from_img(data)
    return WzKey.for_region(region) if region else StaticWzKey(derive_keystream_from_property(data))


@lru_cache(maxsize=24)
def _load_image_cached(path_text: str, mtime_ns: int, size: int) -> WzImage:
    del mtime_ns, size
    path = Path(path_text)
    data = path.read_bytes()
    image = WzImage.from_bytes(data, key=key_for_data(data), name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise ValueError(
            f"IMG 解析不完整: truncated={image.truncated}, warnings={image.parse_warnings}"
        )
    return image


def load_image(path: Path) -> WzImage:
    stat = path.stat()
    return _load_image_cached(str(path), stat.st_mtime_ns, stat.st_size)


def property_path(prop: WzProperty) -> str:
    parts: list[str] = []
    node: WzProperty | None = prop
    while node is not None and node.parent is not None:
        parts.append(node.name)
        node = node.parent
    return "/".join(reversed(parts))


def child_value(parent: WzSubProperty | None, name: str, default: Any = None) -> Any:
    node = parent.child(name) if isinstance(parent, WzSubProperty) else None
    if node is None:
        return default
    try:
        return node.value
    except Exception:
        return default


def property_meta(prop: WzProperty, *, include_children: bool = True) -> dict[str, Any]:
    node_type = prop.type_name.lower()
    if isinstance(prop, WzSubProperty) and not isinstance(prop, WzCanvasProperty) and not isinstance(prop, WzVideoProperty):
        node_type = "imgdir"
    out: dict[str, Any] = {"name": prop.name, "type": node_type}
    if include_children and isinstance(prop, WzSubProperty):
        out["childCount"] = len(prop.children())
    if isinstance(prop, WzCanvasProperty):
        out.update(
            width=int(prop.width),
            height=int(prop.height),
            format=int(prop.format),
            format2=int(prop.format2),
            hasPixels=prop.has_pixels(),
        )
        origin = prop.child("origin")
        if isinstance(origin, WzVectorProperty):
            out["origin"] = {"x": int(origin.x), "y": int(origin.y)}
        outlink = prop.child("_outlink")
        if isinstance(outlink, WzStringProperty):
            out["_outlink"] = str(outlink.value)
    elif isinstance(prop, WzVideoProperty):
        out["type"] = "video"
        out["videoType"] = prop.video_type
        out["dataLength"] = prop._data_length
        out["hasData"] = prop._data_length > 0
    elif isinstance(prop, WzVectorProperty):
        out["value"] = {"x": int(prop.x), "y": int(prop.y)}
        out["editable"] = prop._x_offset is not None and prop._y_offset is not None
    elif isinstance(prop, WzUolProperty):
        out["value"] = str(prop.value)
    elif isinstance(prop, WzNullProperty):
        out["value"] = None
    elif not isinstance(prop, WzSubProperty):
        out["value"] = prop.value
        out["editable"] = (
            getattr(prop, "_value_offset", None) is not None
            or getattr(prop, "_payload_offset", None) is not None
        )
        if isinstance(prop, WzStringProperty):
            out["encoding"] = prop._encoding
            out["byteLength"] = prop._payload_length
            out["shared"] = bool(prop._indirected)
    return out


def is_mob_canvas_store(path: Path) -> bool:
    parts = Path(path).parts
    try:
        canvas_index = parts.index("_Canvas")
    except ValueError:
        return False
    return path.suffix.lower() == ".img" and canvas_index > 0 and parts[canvas_index - 1] == "Mob"


def logical_companion_for_canvas_store(path: Path) -> Path | None:
    item_id = path.stem
    if not re.fullmatch(r"\d{7}", item_id):
        return None
    extracted = find_extracted_ms_mob(item_id)
    if extracted is not None:
        return extracted
    direct = _TMS_DATA / "Mob" / f"{item_id}.img"
    if direct.is_file() and direct.resolve() != path.resolve():
        return direct
    pack = None
    try:
        pack = ms_mob_index().get(item_id)
    except Exception:
        pack = None
    if pack is not None:
        extracted = _existing_ms_extract(item_id, pack)
        if extracted is not None:
            return extracted
    json_dump = _ROOT / "clien" / "Data" / "Mob" / f"{item_id}.img.json"
    if json_dump.is_file():
        return json_dump
    fallback_json = _HERE.parents[2] / "clien" / "Data" / "Mob" / f"{item_id}.img.json"
    if fallback_json.is_file():
        return fallback_json
    return None


def _parent_path(node_path: str) -> str:
    return node_path.rsplit("/", 1)[0] if "/" in node_path else ""


def normalize_node_meta(meta: dict[str, Any]) -> dict[str, Any]:
    out = dict(meta)
    node_type = str(out.get("type") or "")
    if node_type in {"SubProperty", "subproperty"}:
        out["type"] = "imgdir"
    elif node_type.lower() == "uol":
        out["type"] = "uol"
        if out.get("value") in (None, "") and out.get("target") not in (None, ""):
            out["value"] = str(out["target"])
    elif node_type:
        out["type"] = node_type.lower()
    return out


def _refresh_direct_child_counts(nodes: dict[str, dict[str, Any]]) -> None:
    counts: Counter[str] = Counter()
    for node_path in nodes:
        if node_path:
            counts[_parent_path(node_path)] += 1
    for node_path, count in counts.items():
        if node_path in nodes:
            nodes[node_path]["childCount"] = count
    if "" in nodes:
        nodes[""]["childCount"] = counts.get("", nodes[""].get("childCount", 0))


def overlay_canvas_store_tree(
    path: Path, nodes: dict[str, dict[str, Any]], info: dict[str, Any],
) -> dict[str, Any]:
    extra = merge_canvas_metadata_tables(path, allow_extract=False)
    canvas_roots = {node_path.split("/")[0] for node_path in nodes if node_path}
    canvas_roots.add("info")
    if extra:
        for node_path, meta in extra.items():
            if not node_path or node_path in nodes:
                continue
            root = node_path.split("/")[0]
            if root not in canvas_roots:
                continue
            nodes[node_path] = {
                **normalize_node_meta(meta),
                "canvasStoreMissing": True,
                "logicalSource": True,
            }
        companions = canvas_metadata_companion_paths(path, allow_extract=False)
        if companions:
            info["logicalCompanion"] = relative_path(companions[0])
    children_by_parent: dict[str, list[str]] = {}
    for node_path in nodes:
        if not node_path:
            continue
        children_by_parent.setdefault(_parent_path(node_path), []).append(node_path.rsplit("/", 1)[-1])
    for parent, names in children_by_parent.items():
        digits = [int(name) for name in names if name.isdigit()]
        if len(digits) < 2:
            continue
        present = {str(value) for value in digits}
        for index in range(min(digits), max(digits) + 1):
            name = str(index)
            if name in present:
                continue
            node_path = f"{parent}/{name}".strip("/")
            if node_path in nodes:
                continue
            nodes[node_path] = {
                "name": name, "type": "gap", "canvasStoreMissing": True,
                "value": "Canvas 库未收录",
            }
    _refresh_direct_child_counts(nodes)
    info["canvasStore"] = True
    return info


def flatten_img_records(path: Path) -> dict[str, dict[str, Any]]:
    """Walk one IMG's properties. Do not overlay canvas companions (avoids recursion)."""
    image = load_image(path)
    nodes: dict[str, dict[str, Any]] = {
        "": {"name": path.name, "type": "imgdir", "childCount": len(image.root.children())}
    }

    def walk(parent: WzSubProperty, prefix: str) -> None:
        for child in parent.children():
            node_path = f"{prefix}/{child.name}".strip("/")
            nodes[node_path] = property_meta(child)
            if isinstance(child, WzSubProperty):
                walk(child, node_path)
            elif isinstance(child, WzCanvasProperty):
                for grandchild in child.children():
                    nodes[f"{node_path}/{grandchild.name}"] = property_meta(
                        grandchild, include_children=False,
                    )

    walk(image.root, "")
    return nodes


def flatten_img(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    nodes = flatten_img_records(path)
    info: dict[str, Any] = {"format": "img", "warnings": [], "truncated": False}
    if is_mob_canvas_store(path):
        overlay_canvas_store_tree(path, nodes, info)
    return nodes, info


def xml_meta(node: ET.Element) -> dict[str, Any]:
    out: dict[str, Any] = {"name": node.get("name", node.tag), "type": "imgdir" if node.tag == "imgdir" else node.tag}
    if len(node):
        out["childCount"] = len(node)
    if node.tag == "canvas":
        for key in ("width", "height", "format", "format2"):
            if node.get(key) is not None:
                try:
                    out[key] = int(node.get(key, "0"))
                except ValueError:
                    out[key] = node.get(key)
        origin = next((c for c in node if c.tag == "vector" and c.get("name") == "origin"), None)
        if origin is not None:
            out["origin"] = {"x": int(origin.get("x", "0")), "y": int(origin.get("y", "0"))}
    elif node.tag == "vector":
        out["value"] = {"x": int(node.get("x", "0")), "y": int(node.get("y", "0"))}
    elif node.tag == "null":
        out["value"] = None
    elif node.get("value") is not None:
        value: Any = node.get("value", "")
        if node.tag in {"int", "short", "long"}:
            try:
                value = int(value)
            except ValueError:
                pass
        elif node.tag in {"float", "double"}:
            try:
                value = float(value)
            except ValueError:
                pass
        out["value"] = value
    out["editable"] = node.tag in _SCALAR_TYPES or node.tag == "canvas"
    return out


def flatten_xml(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    root = ET.parse(path).getroot()
    nodes: dict[str, dict[str, Any]] = {"": xml_meta(root)}

    def walk(parent: ET.Element, prefix: str) -> None:
        for child in parent:
            name = child.get("name")
            if name is None:
                continue
            node_path = f"{prefix}/{name}".strip("/")
            nodes[node_path] = xml_meta(child)
            walk(child, node_path)

    walk(root, "")
    return nodes, {"format": "xml"}


def flatten_json(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    nodes: dict[str, dict[str, Any]] = {}

    def walk(node: Any, prefix: str, fallback_name: str = "root") -> None:
        if isinstance(node, dict) and "type" in node:
            name = str(node.get("name", fallback_name))
            meta = {key: value for key, value in node.items() if key != "children"}
            meta.setdefault("name", name)
            meta = normalize_node_meta(meta)
            children = node.get("children") or []
            if children:
                meta["childCount"] = len(children)
            nodes[prefix] = meta
            for child in children:
                child_name = str(child.get("name", "?"))
                walk(child, f"{prefix}/{child_name}".strip("/"), child_name)
            return
        if isinstance(node, dict):
            nodes[prefix] = {"name": fallback_name, "type": "object", "childCount": len(node)}
            for key, value in node.items():
                walk(value, f"{prefix}/{key}".strip("/"), str(key))
            return
        nodes[prefix] = {"name": fallback_name, "type": type(node).__name__, "value": node}

    walk(raw, "", path.name)
    return nodes, {"format": "json"}


def flatten_source(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if path.name.lower().endswith(".img"):
        return flatten_img(path)
    if path.suffix.lower() == ".json":
        return flatten_json(path)
    return flatten_xml(path)


def flatten_optional_source(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if path.is_file():
        nodes, info = flatten_source(path)
        return nodes, {**info, "exists": True}
    root_type = "img" if path.name.lower().endswith(".img") else "xml"
    return {}, {"format": root_type, "exists": False, "missing": relative_path(path)}


def comparable(meta: dict[str, Any] | None) -> dict[str, Any] | None:
    if meta is None:
        return None
    return {
        key: meta.get(key)
        for key in ("type", "value", "width", "height", "format", "format2", "origin")
        if key in meta
    }


def operational_guide(path: str, meta: dict[str, Any], item_id: str) -> dict[str, str]:
    parts = path.split("/") if path else []
    leaf = parts[-1] if parts else ""
    ancestors = set(parts[:-1])
    scope = "当前节点；父容器和引用它的节点可能同时受影响。"
    values = "值域取决于客户端读取逻辑；未知字段不能只凭数值猜测。"
    migration = "先与旧端同类可工作节点对照，再做最小增量修改；不要整树序列化 IMG。"
    placement = ""
    structure = ""
    if path == "info/swim":
        scope = "整张地图的移动物理。旧端没有单独的水域矩形范围；VR 和 foothold 不决定 swim 开关范围。"
        values = "0=普通陆地移动；1=启用旧端水下/游泳移动。"
        migration = "客户端 Map IMG 与服务端 Map XML 的 info/swim 必须一致。客户端只做等长 int 标量原位修改。"
        if item_id == "450002011":
            migration = "精确还原应使用旧端诺特勒斯结构：info/swim=0，并把 TMS rapidStream/swim01 的矩形投影为 swimArea/swim01；不要修改 fieldLimit、VR、foothold 或传送门。"
            placement = "info/swim 保留在 info 下；新增的 swimArea 必须放在地图 IMG 根节点，与 info、back、life、portal 同级。"
            structure = "/\n└─ swimArea (imgdir)\n   └─ swim01 (imgdir)\n      ├─ x1 = -819 (int)\n      ├─ y1 = 206 (int)\n      ├─ x2 = 5000 (int)\n      └─ y2 = 474 (int)"
    elif path == "info/fieldLimit":
        scope = "整张地图的动作/技能限制位掩码，与游泳区域范围无关。"
        values = "整数位掩码，不是连续范围；不能按大小阈值判断新旧版本。"
        migration = "从相邻旧端可工作地图或已有迁移证据选择值，客户端和服务端同步；不要为了启用游泳随意改它。"
    elif leaf in {"VRLeft", "VRRight", "VRTop", "VRBottom"} and "info" in ancestors:
        scope = "整张地图的镜头可见边界，不改变碰撞、刷怪或游泳物理。"
        values = "地图坐标；Left < Right、Top < Bottom。"
        migration = "仅在画面裁切或镜头范围错误时修改，并成组核对四个边界。"
    elif parts and parts[0] in {"swimArea", "rapidStream"}:
        modern = parts[0] == "rapidStream"
        scope = "当前矩形内的局部游泳/水流区域；可存在多个子区域，区域名只用于配对和区分。"
        values = "地图坐标矩形：x1 < x2、y1 < y2；x1/y1 为左上角，x2/y2 为右下角，y 越大位置越低。"
        migration = ("旧端已验证 swimArea 结构；修改范围只改 x1/y1/x2/y2，info/swim 保持 0。"
                     if not modern else
                     "现代 rapidStream 不能原样复制；将同名子节点的 x1/y1/x2/y2 写入旧端 swimArea，info/swim 保持 0。")
        if item_id == "450002011":
            migration += " 本图 TMS 矩形为 x=-819..5000、y=206..474，对应下方河流。"
        placement = ("swimArea 是地图 IMG 根节点，与 info、back、life、portal 同级；区域名是 swimArea 的子节点。"
                     if not modern else
                     "rapidStream 是 TMS 根节点；迁移到旧端时不要把它放入其他容器，而是在旧端根节点新建 swimArea。")
        structure = "/\n└─ swimArea (imgdir)\n   └─ swim01 (imgdir)\n      ├─ x1 (int)\n      ├─ y1 (int)\n      ├─ x2 (int)\n      └─ y2 (int)"
    elif parts and parts[0] == "areaCtrl":
        scope = "与同名 rapidStream 区域配对的现代移动物理配置；不决定矩形边界。"
        values = "force/keyForce/speed/jump 为现代客户端物理参数，倍率通常为浮点数；精确单位依赖现代客户端实现。"
        migration = "旧端 swimArea 只支持矩形，不支持这些物理参数。节点迁移时不复制；需要相同水流手感时必须由兼容 DLL 实现。"
        placement = "areaCtrl 是 TMS 根节点，但旧端目标不新增 areaCtrl；应在旧端地图 IMG 根节点新增 swimArea。"
        structure = "/\n└─ swimArea (imgdir)\n   └─ swim01 (imgdir)\n      ├─ x1 (int)\n      ├─ y1 (int)\n      ├─ x2 (int)\n      └─ y2 (int)"
    elif "life" in ancestors:
        scope = "单个怪物/NPC 刷新点。rx0/rx1 控制横向活动范围，x/y 是出生坐标，fh 是落脚 foothold。"
        values = "id/type 为实体身份；坐标使用地图世界坐标；mobTime 为刷新周期。"
        migration = "同时核对客户端 Mob/Npc IMG、服务端 Map XML 和对应实体数据。"
    elif "portal" in ancestors:
        scope = "单个传送点；x/y 是触发位置，tm/tn 是目标地图和目标门。"
        values = "pt 是离散门类型，不是范围；现代 hRange/vRange 不能直接带入旧端。"
        migration = "投影为旧端 pn/pt/tn/tm/x/y 结构，并实测进出两端落点。"
    elif "foothold" in ancestors:
        scope = "单条或一组碰撞线段；x1/y1/x2/y2 决定可站立地面，prev/next 决定相邻链。"
        values = "地图世界坐标与编号引用；piece 是现代编辑器元数据，不是碰撞范围。"
        migration = "坐标和 prev/next 链必须整体一致；可移除 piece，但不能只复制部分坐标叶子。"
    elif "obj" in ancestors or "tile" in ancestors or "back" in ancestors:
        scope = "当前场景元素；资源名和层级路径决定图片，x/y/z/f 决定位置、层级和翻转。"
        values = "坐标为地图世界坐标；资源路径必须能在旧客户端解析到实际 Canvas。"
        migration = "优先映射到旧版 Back/Obj/Tile 结构；动态、Spine、piece 等现代元数据不能整段复制。"
    return {
        "scope": scope, "valueGuide": values, "migration": migration,
        "placement": placement, "structure": structure,
    }


def contextual_meaning(path: str, meta: dict[str, Any], mode: str) -> str:
    parts = [part for part in path.split("/") if part]
    name = str(meta.get("name") or (parts[-1] if parts else "root"))
    if not parts:
        return "资源文件根节点；所有地图结构、属性和引用都位于其子树中。"
    if mode != "map":
        return map_compat.node_meaning(name, path, meta, mode)
    if parts[0] in {"swimArea", "rapidStream", "areaCtrl"}:
        root = parts[0]
        root_meanings = {
            "swimArea": "旧客户端已验证的局部游泳区域容器；诺特勒斯等地图使用此结构。",
            "rapidStream": "现代客户端的局部水流区域容器；每个子节点用矩形坐标定义作用范围。",
            "areaCtrl": "现代客户端的区域移动物理容器；与 rapidStream 的同名区域配对。",
        }
        if len(parts) == 1:
            return root_meanings[root]
        if len(parts) == 2:
            if root == "swimArea":
                return f"旧端局部游泳区域“{name}”；其四个坐标组成生效矩形。"
            if root == "rapidStream":
                return f"现代水流区域“{name}”；同名 areaCtrl 节点提供区域内的移动参数。"
            return f"现代区域控制配置“{name}”；应与 rapidStream/{name} 配对。"
        if root in {"swimArea", "rapidStream"} and name in {"x1", "y1", "x2", "y2"}:
            coordinate_meanings = {
                "x1": "局部水域矩形左边界。", "y1": "局部水域矩形上边界，通常对应水面高度。",
                "x2": "局部水域矩形右边界。", "y2": "局部水域矩形下边界。",
            }
            return coordinate_meanings[name]
        area_fields = {
            "inputX": "现代区域控制器的水平输入方向参数。", "inputY": "现代区域控制器的垂直输入方向参数。",
            "fixSpeedShoe": "现代区域内鞋子移动速度修正倍率。", "forceX": "现代区域的水平基础作用力。",
            "forceY": "现代区域的垂直基础作用力。", "keyForceX": "按方向键时追加的水平作用力。",
            "keyForceY": "按方向键时追加的垂直作用力。", "revdir_vrate": "逆着水流移动时的速度倍率。",
            "samedir_vrate": "顺着水流移动时的速度倍率。", "speedX": "现代区域的水平速度参数。",
            "speedY": "现代区域的垂直速度参数。", "outjump": "离开区域时使用的跳跃/推出力度。",
            "jump": "区域内使用的跳跃力度。",
        }
        if root == "areaCtrl" and name in area_fields:
            return area_fields[name]
    if parts[0] == "info":
        specific = map_compat._meaning_map(name, "info", meta.get("type"))
        if not specific.startswith("地图节点；"):
            return specific
    context = next((part for part in ("portal", "life", "back", "foothold") if part in parts[:-1]), "")
    if context:
        specific = map_compat._meaning_map(name, context, meta.get("type"))
        if not specific.endswith("；含义取决于父节点与客户端读取方式。"):
            return specific
    obj_fields = {
        "oS": "对象资源文件名，对应 Map/Obj/<oS>.img。", "l0": "对象资源一级目录。",
        "l1": "对象资源二级目录。", "l2": "对象资源三级目录。", "x": "场景元素的地图 x 坐标。",
        "y": "场景元素的地图 y 坐标。", "z": "对象在当前图层内的绘制顺序。",
        "zM": "地砖的绘制顺序。", "f": "是否水平翻转（0/1）。", "r": "现代对象运行/旋转扩展字段，旧端无稳定契约。",
        "dynamic": "现代动态对象开关，旧端不支持。", "move": "现代对象移动扩展元数据。",
        "piece": "现代编辑器对象碎片/关联编号，旧端渲染通常不需要。",
    }
    tile_fields = {"u": "地砖分类目录。", "no": "地砖在分类目录中的 Canvas 编号。"}
    foothold_fields = {
        "x1": "碰撞线段起点 x。", "y1": "碰撞线段起点 y。", "x2": "碰撞线段终点 x。",
        "y2": "碰撞线段终点 y。", "prev": "相邻的前一条 foothold 编号。", "next": "相邻的后一条 foothold 编号。",
        "piece": "现代地图编辑器使用的碰撞碎片关联数据；真实碰撞由 x1/y1/x2/y2 与 prev/next 决定。",
    }
    portal_fields = {
        "pn": "当前传送点名称。", "pt": "传送点类型枚举。", "tn": "目标地图中的传送点名称。",
        "tm": "目标地图 ID。", "script": "触发的传送点脚本名。", "hRange": "现代横向触发范围扩展字段。",
        "vRange": "现代纵向触发范围扩展字段。",
    }
    life_fields = {
        "id": "怪物或 NPC 资源 ID。", "type": "生命体类型：m=怪物，n=NPC。", "fh": "出生时依附的 foothold 编号。",
        "cy": "生命体中心/基准 y。", "rx0": "怪物横向活动范围左边界。", "rx1": "怪物横向活动范围右边界。",
        "mobTime": "怪物刷新周期。", "f": "生命体初始朝向/翻转。",
    }
    back_fields = {
        "bS": "背景资源文件名，对应 Map/Back/<bS>.img。", "no": "背景 Canvas 编号。",
        "ani": "是否使用动画背景。", "front": "是否绘制在角色前景。", "rx": "背景横向滚动参数。",
        "ry": "背景纵向滚动参数。", "cx": "背景平铺宽度。", "cy": "背景平铺高度。", "a": "背景透明度（0-255）。",
    }
    if "obj" in parts[:-1] and name in obj_fields:
        return obj_fields[name]
    if "tile" in parts[:-1] and name in {**obj_fields, **tile_fields}:
        return {**obj_fields, **tile_fields}[name]
    if "foothold" in parts[:-1] and name in foothold_fields:
        return foothold_fields[name]
    if "portal" in parts[:-1] and name in {**obj_fields, **portal_fields}:
        return {**obj_fields, **portal_fields}[name]
    if "life" in parts[:-1] and name in {**obj_fields, **life_fields}:
        return {**obj_fields, **life_fields}[name]
    if "back" in parts[:-1] and name in {**obj_fields, **back_fields}:
        return {**obj_fields, **back_fields}[name]
    if parts[0].isdigit() and len(parts) == 1:
        return f"地图场景图层 {parts[0]}；数字越大通常绘制层级越靠前。"
    return map_compat.node_meaning(name, path, meta, mode)


def annotate_meta(path: str, meta: dict[str, Any] | None, mode: str, item_id: str) -> dict[str, Any] | None:
    if meta is None:
        return None
    output = dict(meta)
    name = str(output.get("name") or (path.rsplit("/", 1)[-1] if path else "root"))
    parent_name = path.rsplit("/", 2)[-2] if "/" in path else ""
    normalized = {**output, "path": path, "name": name, "parent_name": parent_name}
    verdict = map_compat.evaluate(normalized, mode)
    output["meaning"] = contextual_meaning(path, output, mode)
    output["compatibility"] = {
        "status": verdict.status, "label": map_compat.STATUS_LABELS[verdict.status],
        "reason": verdict.reason, "suggestion": verdict.suggestion,
    }
    output.update(operational_guide(path, output, item_id))
    if mode == "map" and item_id == "450002011" and path == "info/swim" and output.get("value") == 1:
        output["compatibility"] = {
            "status": "review",
            "label": "全图兼容降级",
            "reason": "值 1 可被旧端解析，但会让整张地图进入游泳物理；诺特勒斯证明局部水域应使用 swimArea。",
            "suggestion": output["migration"],
        }
    return output


def annotate_rows(rows: list[dict[str, Any]], mode: str, item_id: str) -> None:
    for row in rows:
        row["left"] = annotate_meta(row["path"], row["left"], mode, item_id)
        row["right"] = annotate_meta(row["path"], row["right"], mode, item_id)
    if mode == "boss":
        server_control_help.attach(rows, item_id)


def merge_sources(
    left: dict[str, dict[str, Any]], right: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    counts = {"same": 0, "changed": 0, "leftOnly": 0, "rightOnly": 0}
    for path in sorted(set(left) | set(right), key=lambda value: [natural_key(p) for p in value.split("/")]):
        left_meta = left.get(path)
        right_meta = right.get(path)
        if left_meta is None:
            status = "rightOnly"
        elif right_meta is None:
            status = "leftOnly"
        elif comparable(left_meta) == comparable(right_meta):
            status = "same"
        else:
            status = "changed"
        counts[status] += 1
        rows.append({"path": path, "parent": path.rsplit("/", 1)[0] if "/" in path else "", "left": left_meta, "right": right_meta, "status": status})
    return rows, counts


def infer_id(path: Path) -> str:
    name = path.name
    return name[:-8] if name.lower().endswith(".img.xml") else path.stem


def catalog_rows(kind: str, query: str) -> list[dict[str, Any]]:
    if kind == "map":
        left_files = (_ROOT / "clien" / "Data" / "Map" / "Map").glob("Map*/*.img")
        right_root = _ROOT / "gms-server" / "wz" / "Map.wz" / "Map"
        query = query.strip().lower()
        rows = []
        for left in left_files:
            item_id = left.stem
            if query and query not in item_id.lower():
                continue
            _, right = default_paths(kind, item_id)
            rows.append({
                "id": item_id,
                "name": "",
                "leftPath": relative_path(left),
                "rightPath": relative_path(right),
                "hasXml": right.is_file(),
                "sources": ["A", "TMS" if right.is_file() and right.name.endswith(".img") else "XML"],
            })
        rows.sort(key=lambda row: natural_key(row["id"]))
        return rows[:300]
    if kind != "mob":
        raise ValueError("kind 必须是 map 或 mob")

    query = query.strip().lower()
    client_root = _ROOT / "clien" / "Data" / "Mob"
    server_root = _ROOT / "gms-server" / "wz" / "Mob.wz"
    direct_root = _TMS_DATA / "Mob"
    canvas_root = direct_root / "_Canvas"
    clients = {path.stem: path for path in client_root.glob("*.img")}
    candidate_ids = set(clients)
    names = {}
    ms_index = {}
    if query:
        names = mob_names(_TMS_DATA / "String" / "Mob.img")
        ms_index = ms_mob_index()
        candidate_ids.update(item_id for item_id in ms_index if item_id.startswith(query))
        candidate_ids.update(
            item_id for item_id, name in names.items()
            if query in item_id.lower() or query in name.lower()
        )
        if query.isdigit():
            candidate_ids.update(path.stem for path in direct_root.glob(f"{query}*.img"))
            candidate_ids.update(path.stem for path in canvas_root.glob(f"{query}*.img"))
    rows = []
    for item_id in candidate_ids:
        name = names.get(item_id, "")
        if query and query not in item_id.lower() and query not in name.lower():
            continue
        left = clients.get(item_id, client_root / f"{item_id}.img")
        direct = direct_root / f"{item_id}.img"
        canvas = canvas_root / f"{item_id}.img"
        server = server_root / f"{item_id}.img.xml"
        _, right = default_paths("mob", item_id)
        sources = []
        if left.is_file():
            sources.append("A")
        if item_id in ms_index:
            sources.append("MS")
        if direct.is_file():
            sources.append("IMG")
        if canvas.is_file():
            sources.append("Canvas")
        if server.is_file():
            sources.append("XML")
        rows.append({
            "id": item_id,
            "name": name,
            "leftPath": relative_path(left),
            "rightPath": relative_path(right),
            "hasXml": right.is_file(),
            "sources": sources,
        })
    rows.sort(key=lambda row: natural_key(row["id"]))
    return rows[:300]


def data_root_for(path: Path) -> Path:
    try:
        resolved = path.resolve()
        if any(resolved.is_relative_to(root.resolve()) for root in _ms_extract_roots()):
            return _TMS_DATA
    except OSError:
        pass
    for parent in path.parents:
        if parent.name == "Data":
            return parent
    return _ROOT / "clien" / "Data"


def resolve_canvas_node(image: WzImage, path: str, file_path: Path, depth: int = 0) -> tuple[WzImage, WzCanvasProperty, Path]:
    if depth > 8:
        raise ValueError("Canvas 引用链过深")
    node = image.root.get(path)
    if isinstance(node, WzUolProperty):
        target = node.parent.get(str(node.value)) if node.parent else None
        if target is None:
            raise ValueError(f"UOL 目标不存在: {node.value}")
        return resolve_canvas_node(image, property_path(target), file_path, depth + 1)
    if not isinstance(node, WzCanvasProperty):
        raise ValueError(f"节点不是 Canvas: {path}")
    inlink = node.child("_inlink")
    if isinstance(inlink, WzStringProperty):
        return resolve_canvas_node(image, str(inlink.value), file_path, depth + 1)
    outlink = node.child("_outlink")
    if isinstance(outlink, WzStringProperty):
        raw = str(outlink.value).replace("\\", "/")
        match = re.match(r"^(.*?\.img)/(.*)$", raw)
        if not match:
            raise ValueError(f"无法解析 _outlink: {raw}")
        linked_file = resolve_repo_path(str(data_root_for(file_path) / match.group(1)))
        linked_image = load_image(linked_file)
        return resolve_canvas_node(linked_image, match.group(2), linked_file, depth + 1)
    if node.has_pixels():
        return image, node, file_path
    raise ValueError(f"Canvas 没有可解码像素: {path}")


@lru_cache(maxsize=256)
def canvas_region(path_text: str, mtime_ns: int, size: int) -> str:
    del mtime_ns, size
    return detect_region_from_img(Path(path_text).read_bytes()) or "GMS"


def canvas_descriptor(file_path: Path, path: str) -> dict[str, Any] | None:
    try:
        image = load_image(file_path)
        original = image.root.get(path)
        _, canvas, _ = resolve_canvas_node(image, path, file_path)
    except Exception:
        return None
    metadata = original if isinstance(original, WzCanvasProperty) else canvas
    origin = metadata.child("origin")
    delay = child_value(metadata, "delay", child_value(canvas, "delay", 100))
    return {
        "url": f"/api/canvas?file={quote(relative_path(file_path))}&path={quote(path)}",
        "width": int(canvas.width),
        "height": int(canvas.height),
        "origin": {
            "x": int(origin.x) if isinstance(origin, WzVectorProperty) else 0,
            "y": int(origin.y) if isinstance(origin, WzVectorProperty) else int(canvas.height),
        },
        "delay": max(16, int(delay or 100)),
    }


# ── TMS 真实资源解析 ─────────────────────────────────────────────────
# TMS/MS 的怪物记录里，绝大多数“帧”本身只是 1×1 的占位 Canvas，真正的像素在
# Mob/_Canvas/<怪ID>.img 里，而且经常跨到另一个怪 ID（例如 8880141 → 8880140）。
# 下面这组函数把占位帧解析回真实资源，供界面展示与复制操作使用。

_PLACEHOLDER_MAX_SIZE = 4
_LINK_KEYS = ("_outlink", "_inlink")
_RESOURCE_LABEL_ROOTS = (
    (_TMS_DATA, "TMS/Data"),
    (_MS_CACHE_ROOT, "TMS/ms-extract"),
    (_LEGACY_MS_CACHE_ROOT, "MS缓存"),
)


def resource_file_label(path: Path) -> str:
    """把资源路径转成可读标签，例如 TMS/Data/Mob/_Canvas/8880140.img。"""
    resolved = path.resolve()
    for root, prefix in _RESOURCE_LABEL_ROOTS + (
        (_ROOT / "clien" / "Data", "clien/Data"),
        (_ROOT / "gms-server" / "wz", "gms-server/wz"),
    ):
        try:
            return f"{prefix}/{resolved.relative_to(root.resolve()).as_posix()}"
        except ValueError:
            continue
    return str(resolved)


def mob_id_of_resource(path: Path) -> str:
    """从 Mob/8880141.img、Mob/_Canvas/0100007.img、Mob_8880141.img 里取出怪 ID。"""
    stem = path.stem
    if stem.startswith("Mob_"):
        stem = stem[4:]
    digits = re.sub(r"\D", "", stem)
    return digits.lstrip("0") or digits


def resource_owner_label(path: Path) -> str:
    """标注资源属于项目还是 TMS 只读数据。"""
    resolved = path.resolve()
    if resolved.is_relative_to((_ROOT / "clien" / "Data").resolve()):
        return "client"
    if resolved.is_relative_to((_ROOT / "gms-server" / "wz").resolve()):
        return "server"
    if resolved.is_relative_to(_TMS_DATA.resolve()):
        return "tms"
    if any(resolved.is_relative_to(root.resolve()) for root in _ms_extract_roots()):
        return "ms"
    return "other"


def _node_link(node: WzProperty | None) -> tuple[str, str]:
    if isinstance(node, WzUolProperty):
        return "UOL", str(node.value).replace("\\", "/")
    if isinstance(node, WzCanvasProperty):
        for name in _LINK_KEYS:
            link = node.child(name)
            if isinstance(link, WzStringProperty):
                return name, str(link.value).replace("\\", "/")
    return "", ""


def _next_link_hop(
    image: WzImage, file_path: Path, node: WzProperty, kind: str, raw: str,
) -> tuple[WzImage, Path, str] | None:
    """按 resolve_canvas_node 的规则算出下一跳 (image, file, path)。"""
    if kind == "UOL":
        target = node.parent.get(raw) if node.parent else None
        return None if target is None else (image, file_path, property_path(target))
    if kind == "_inlink":
        return image, file_path, raw
    if kind == "_outlink":
        match = re.match(r"^(.*?\.img)/(.*)$", raw)
        if not match:
            return None
        linked_file = Path(str(data_root_for(file_path) / match.group(1))).resolve()
        if not linked_file.is_file():
            return None
        return load_image(linked_file), linked_file, match.group(2)
    return None


def describe_canvas_reference(
    image: WzImage, path: str, file_path: Path, *, max_hops: int = 9,
) -> dict[str, Any]:
    """只读解析一个帧节点：它声明的像素到底来自哪个真实资源。

    覆盖 TMS 常见的三种“1×1 占位”：
      1. Canvas 带 ``_outlink``/``_inlink`` → 真实像素在别的文件（可能别的怪 ID）；
      2. ``UOL`` → 同文件或跨文件的另一帧；
      3. 既无链接、``Mob/_Canvas`` 里也没有同名节点 → 真的没有像素来源。
    """
    report: dict[str, Any] = {
        "path": path,
        "declaredType": "",
        "declaredWidth": None,
        "declaredHeight": None,
        "placeholder": False,
        "linkKind": "",
        "linkRaw": "",
        "hops": [],
        "resolved": None,
        "crossMob": False,
        "recovered": False,
        "state": "missing",
        "error": "",
    }
    self_mob = mob_id_of_resource(file_path)
    current_image, current_file, current_path = image, file_path, path
    seen: set[tuple[str, str]] = set()
    try:
        for _ in range(max_hops + 1):
            key = (str(current_file.resolve()), current_path)
            if key in seen:
                report["error"] = f"引用链出现循环: {current_path}"
                break
            seen.add(key)
            node = current_image.root.get(current_path)
            if node is None:
                report["error"] = f"引用目标不存在: {current_path}"
                break
            if not report["declaredType"]:
                report["declaredType"] = (
                    "uol" if isinstance(node, WzUolProperty)
                    else "canvas" if isinstance(node, WzCanvasProperty)
                    else node.type_name.lower()
                )
            if report["declaredWidth"] is None and isinstance(node, WzCanvasProperty):
                report["declaredWidth"] = int(node.width)
                report["declaredHeight"] = int(node.height)
            # 顺序必须与 resolve_canvas_node 一致：先看 _inlink/_outlink，再看本体像素。
            # TMS 的占位 Canvas 同时带着 1×1 的 payload 和 _outlink，先判 payload 会漏掉真实资源。
            kind, raw = _node_link(node)
            if not kind:
                if isinstance(node, WzCanvasProperty) and node.has_pixels():
                    report["resolved"] = {
                        "file": relative_path(current_file),
                        "absPath": str(current_file.resolve()),
                        "fileLabel": resource_file_label(current_file),
                        "owner": resource_owner_label(current_file),
                        "inProject": resource_owner_label(current_file) in {"client", "server"},
                        "mobId": mob_id_of_resource(current_file),
                        "path": current_path,
                        "width": int(node.width),
                        "height": int(node.height),
                        "format": f"{int(node.format)}/{int(node.format2)}",
                        "region": canvas_region(
                            str(current_file), current_file.stat().st_mtime_ns, current_file.stat().st_size,
                        ),
                        "visible": int(node.width) > _PLACEHOLDER_MAX_SIZE
                        or int(node.height) > _PLACEHOLDER_MAX_SIZE,
                    }
                    break
                report["error"] = f"节点既无像素也没有链接: {current_path}"
                break
            report["linkKind"] = report["linkKind"] or kind
            report["linkRaw"] = report["linkRaw"] or raw
            report["hops"].append({
                "kind": kind,
                "raw": raw,
                "fileLabel": resource_file_label(current_file),
                "path": current_path,
            })
            hop = _next_link_hop(current_image, current_file, node, kind, raw)
            if hop is None:
                report["error"] = f"无法解析链接 {kind}={raw}"
                break
            current_image, current_file, current_path = hop
    except Exception as exc:  # noqa: BLE001 - 解析失败必须降级为可读信息
        report["error"] = str(exc)

    declared = (report["declaredWidth"], report["declaredHeight"])
    report["placeholder"] = bool(
        declared[0] is not None
        and declared[0] <= _PLACEHOLDER_MAX_SIZE
        and declared[1] <= _PLACEHOLDER_MAX_SIZE
    )
    resolved = report["resolved"]
    if resolved is None:
        report["state"] = "broken" if report["linkKind"] else (
            "orphan" if report["placeholder"] else "missing"
        )
    else:
        relocated = (
            resolved["file"] != relative_path(file_path) or resolved["path"] != path
        )
        if report["placeholder"] and resolved["visible"] and relocated:
            report["state"] = "linked"
            report["recovered"] = True
        elif report["placeholder"]:
            # 声明的就是占位，解析回来仍是占位：TMS 里这一帧确实没有可见像素
            report["state"] = "orphan"
        else:
            report["state"] = "real"
    if resolved is not None:
        report["crossMob"] = bool(
            self_mob and resolved["mobId"] and resolved["mobId"] != self_mob
        )
    return report


def canvas_reference_summary(report: dict[str, Any]) -> str:
    """把解析结果压成一句话，供界面与日志复用。"""
    resolved = report.get("resolved")
    state = report.get("state")
    if resolved is None:
        reason = report.get("error") or "没有像素来源"
        return f"无可解析资源（{reason}）"
    if state == "orphan":
        return (
            f"{report['declaredWidth']}×{report['declaredHeight']} 空占位，"
            "TMS 里该帧确实没有可见像素"
        )
    if state != "linked":
        return f"{resolved['width']}×{resolved['height']} ← {resolved['fileLabel']}/{resolved['path']}"
    cross = "（跨怪引用）" if report.get("crossMob") else ""
    return (
        f"{report['declaredWidth']}×{report['declaredHeight']} 占位 → "
        f"{resolved['width']}×{resolved['height']} ← "
        f"{resolved['fileLabel']}/{resolved['path']}{cross}"
    )


def mob_frame_entries(image: WzImage) -> list[tuple[str, str, WzProperty]]:
    """产出 (动作名, 帧路径, 帧节点)。识别规则与 mob_preview 一致：
    根下非 info 的 imgdir 里，数字名的 Canvas/UOL 子节点就是帧。"""
    entries: list[tuple[str, str, WzProperty]] = []
    for action in image.root.children():
        if not isinstance(action, WzSubProperty) or action.name == "info":
            continue
        for child in sorted(action.children(), key=lambda node: natural_key(node.name)):
            if child.name.isdigit() and isinstance(child, (WzCanvasProperty, WzUolProperty)):
                entries.append((action.name, f"{action.name}/{child.name}", child))
    return entries


def mob_resource_manifest(
    image: WzImage, file_path: Path, node_path: str = "",
) -> dict[str, Any]:
    """列出这个 IMG 里全部帧的真实资源来源。

    这是「不要只看到 1×1 占位」的核心：把每一帧解析到真实文件/节点，
    按文件聚合，并标出跨怪引用、无源占位与项目内/只读来源。
    """
    scope = node_path.strip("/")
    entries = mob_frame_entries(image)
    if scope:
        entries = [
            entry for entry in entries
            if entry[1] == scope or entry[1].startswith(f"{scope}/")
        ]
    self_mob = mob_id_of_resource(file_path)
    frames: list[dict[str, Any]] = []
    files: dict[str, dict[str, Any]] = {}
    orphan_paths: list[str] = []
    broken: list[dict[str, str]] = []
    for action, path, node in entries:
        report = describe_canvas_reference(image, path, file_path)
        resolved = report["resolved"]
        frames.append({
            "action": action,
            "path": path,
            "state": report["state"],
            "placeholder": report["placeholder"],
            "declaredWidth": report["declaredWidth"],
            "declaredHeight": report["declaredHeight"],
            "linkKind": report["linkKind"],
            "crossMob": report["crossMob"],
            "resolved": resolved,
            "error": report["error"],
            "summary": canvas_reference_summary(report),
        })
        if report["state"] == "orphan":
            orphan_paths.append(path)
        if report["state"] == "broken":
            broken.append({"path": path, "error": report["error"]})
        if resolved is None:
            continue
        bucket = files.setdefault(resolved["absPath"], {
            "file": resolved["file"],
            "absPath": resolved["absPath"],
            "label": resolved["fileLabel"],
            "owner": resolved["owner"],
            "inProject": resolved["inProject"],
            "mobId": resolved["mobId"],
            "crossMob": bool(
                self_mob and resolved["mobId"] and resolved["mobId"] != self_mob
            ),
            "isCanvasStore": "_Canvas" in Path(resolved["absPath"]).parts,
            "frameCount": 0,
            "actions": [],
            "framePaths": [],
            "sizes": [],
        })
        bucket["frameCount"] += 1
        if action not in bucket["actions"]:
            bucket["actions"].append(action)
        bucket["framePaths"].append(resolved["path"])
        if resolved["visible"]:
            bucket["sizes"].append(f"{resolved['width']}×{resolved['height']}")
    ordered = sorted(files.values(), key=lambda item: (-item["frameCount"], item["label"]))
    for bucket in ordered:
        bucket["actions"].sort(key=natural_key)
    states = Counter(frame["state"] for frame in frames)
    primary = next((bucket for bucket in ordered if bucket["crossMob"]), None) or (
        ordered[0] if ordered else None
    )
    return {
        "sourceFile": relative_path(file_path),
        "sourceLabel": resource_file_label(file_path),
        "sourceMobId": self_mob,
        "scope": scope,
        "frameCount": len(frames),
        "stateCounts": dict(states),
        "realFiles": ordered,
        "crossMobFiles": [bucket for bucket in ordered if bucket["crossMob"]],
        "orphanPaths": orphan_paths,
        "brokenPaths": broken,
        "primaryFile": primary,
        "frames": frames,
    }


def find_resource(folder: str, name: str, source_path: Path) -> Path | None:
    base = data_root_for(source_path) / "Map" / folder
    direct = base / f"{name}.img"
    if direct.is_file():
        return direct
    lowered = direct.name.lower()
    return next((path for path in base.glob("*.img") if path.name.lower() == lowered), None)


def iter_subtree(node: WzSubProperty | None) -> Iterable[WzProperty]:
    if not isinstance(node, WzSubProperty):
        return
    for child in node.children():
        yield child
        if isinstance(child, WzSubProperty):
            yield from iter_subtree(child)


@lru_cache(maxsize=8192)
def _canvas_reference_cached(
    path_text: str, mtime_ns: int, size: int, node_path: str,
) -> dict[str, Any]:
    del mtime_ns, size
    file_path = Path(path_text)
    return describe_canvas_reference(load_image(file_path), node_path, file_path)


def canvas_reference(file_path: Path, node_path: str) -> dict[str, Any]:
    """带缓存的帧资源解析。缓存键含 mtime+size，文件改写后自动失效。"""
    stat = file_path.stat()
    return _canvas_reference_cached(
        str(file_path.resolve()), stat.st_mtime_ns, stat.st_size, node_path,
    )


def mob_frame_descriptor(
    file_path: Path, frame_path: str, node: WzProperty | None = None,
) -> dict[str, Any]:
    """把一帧压成前端可直接用的结构：声明尺寸、真实资源、缩略图 URL、锚点与延时。

    ``width``/``height`` 返回**真实像素**尺寸（占位帧会是真实资源的大小），
    否则动画舞台会按 1×1 对齐；声明尺寸另存为 ``declaredWidth``/``declaredHeight``。
    """
    report = canvas_reference(file_path, frame_path)
    if node is None:
        node = load_image(file_path).root.get(frame_path)
    resolved = report["resolved"]
    target = None
    if resolved is not None:
        target = load_image(Path(resolved["absPath"])).root.get(resolved["path"])
    declared_node = node if isinstance(node, WzCanvasProperty) else None
    origin = declared_node.child("origin") if declared_node is not None else None
    if not isinstance(origin, WzVectorProperty) and isinstance(target, WzCanvasProperty):
        origin = target.child("origin")
    delay = child_value(declared_node, "delay")
    if delay is None and isinstance(target, WzCanvasProperty):
        delay = child_value(target, "delay")
    width = int(resolved["width"]) if resolved is not None else int(report["declaredWidth"] or 0)
    height = int(resolved["height"]) if resolved is not None else int(report["declaredHeight"] or 0)
    return {
        "path": frame_path,
        "url": (
            f"/api/canvas?file={quote(relative_path(file_path))}&path={quote(frame_path)}"
            if resolved is not None else ""
        ),
        "width": width,
        "height": height,
        "declaredWidth": report["declaredWidth"],
        "declaredHeight": report["declaredHeight"],
        "origin": (
            {"x": int(origin.x), "y": int(origin.y)} if isinstance(origin, WzVectorProperty)
            else {"x": 0, "y": height}
        ),
        "delay": max(16, int(delay or 100)),
        "state": report["state"],
        "placeholder": report["placeholder"],
        "linkKind": report["linkKind"],
        "linkRaw": report["linkRaw"],
        "crossMob": report["crossMob"],
        "resolved": resolved,
        "summary": canvas_reference_summary(report),
        "error": report["error"],
    }


def mob_preview(path: Path) -> dict[str, Any]:
    image = load_image(path)
    actions = []
    for action in image.root.children():
        if not isinstance(action, WzSubProperty) or action.name == "info":
            continue
        frames = []
        for child in sorted(action.children(), key=lambda node: natural_key(node.name)):
            if not child.name.isdigit() or not isinstance(child, (WzCanvasProperty, WzUolProperty)):
                continue
            frames.append(mob_frame_descriptor(path, property_path(child), child))
        if frames:
            real_files = sorted({
                frame["resolved"].get("absPath") or frame["resolved"]["fileLabel"]
                for frame in frames if frame["resolved"]
            })
            actions.append({
                "name": action.name,
                "frames": frames,
                "duration": sum(frame["delay"] for frame in frames),
                "realFiles": real_files,
                "linkedFrames": sum(1 for frame in frames if frame["state"] == "linked"),
                "orphanFrames": sum(1 for frame in frames if frame["state"] == "orphan"),
            })
    info = image.root.child("info")
    stats = {}
    for name in ("level", "maxHP", "maxMP", "PADamage", "MADamage", "speed", "exp"):
        value = child_value(info if isinstance(info, WzSubProperty) else None, name)
        if value is not None:
            stats[name] = value
    return {"kind": "mob", "actions": actions, "stats": stats}


def mob_xml_preview(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    info = next(
        (child for child in root if child.tag == "imgdir" and child.get("name") == "info"),
        None,
    )
    stats = {}
    if info is not None:
        wanted = {"level", "maxHP", "maxMP", "PADamage", "MADamage", "speed", "exp"}
        for child in info:
            name = child.get("name", "")
            if name not in wanted or child.get("value") is None:
                continue
            value: Any = child.get("value")
            try:
                value = int(value)
            except (TypeError, ValueError):
                pass
            stats[name] = value
    return {"kind": "mob", "actions": [], "stats": stats}


def foothold_lines(root: WzSubProperty) -> list[dict[str, Any]]:
    result = []
    foothold = root.child("foothold")
    for node in iter_subtree(foothold if isinstance(foothold, WzSubProperty) else None):
        if not isinstance(node, WzSubProperty):
            continue
        values = {name: child_value(node, name) for name in ("x1", "y1", "x2", "y2")}
        if all(value is not None for value in values.values()):
            result.append({"path": property_path(node), **{key: int(value) for key, value in values.items()}})
    return result


def point_nodes(root: WzSubProperty, parent_name: str) -> list[dict[str, Any]]:
    parent = root.child(parent_name)
    points = []
    if not isinstance(parent, WzSubProperty):
        return points
    for node in parent.children():
        if not isinstance(node, WzSubProperty):
            continue
        x, y = child_value(node, "x"), child_value(node, "y")
        if x is None or y is None:
            continue
        points.append({
            "path": property_path(node), "x": int(x), "y": int(y), "name": node.name,
            "id": str(child_value(node, "id", child_value(node, "tn", ""))),
            "type": str(child_value(node, "type", "")),
            "flip": bool(child_value(node, "f", 0)),
            "portalName": str(child_value(node, "pn", "")),
            "portalType": int(child_value(node, "pt", -1)),
        })
    return points


def first_entity_frame(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        image = load_image(path)
    except Exception:
        return None
    actions = ["stand", "move", "fly", "jump"]
    actions.extend(child.name for child in image.root.children() if child.name not in actions and child.name != "info")
    for action_name in actions:
        action = image.root.child(action_name)
        if not isinstance(action, WzSubProperty):
            continue
        for frame in sorted(action.children(), key=lambda node: natural_key(node.name)):
            if frame.name.isdigit() and isinstance(frame, (WzCanvasProperty, WzUolProperty)):
                desc = canvas_descriptor(path, property_path(frame))
                if desc:
                    return desc
    return None


def map_life_preview(root: WzSubProperty, source_path: Path) -> list[dict[str, Any]]:
    points = point_nodes(root, "life")
    data_root = data_root_for(source_path)
    for point in points:
        point["kind"] = "mob" if point["type"] == "m" else "npc"
        folder = "Mob" if point["kind"] == "mob" else "Npc"
        resource = data_root / folder / f'{point["id"]}.img'
        if not resource.is_file():
            resource = resource.parent / "_Canvas" / resource.name
        sprite = first_entity_frame(resource)
        if sprite:
            point["sprite"] = sprite
    return points


def map_portal_preview(root: WzSubProperty, source_path: Path) -> list[dict[str, Any]]:
    points = point_nodes(root, "portal")
    helper = data_root_for(source_path) / "Map" / "MapHelper.img"
    portal_codes = ("sp", "pi", "pv", "pc", "pg", "pgi", "tp", "ps", "psi", "pcs", "ph", "psh", "pcj", "pci", "pcig")
    for point in points:
        portal_type = point["portalType"]
        code = portal_codes[portal_type] if 0 <= portal_type < len(portal_codes) else "sp"
        sprite = canvas_descriptor(helper, f"portal/game/{code}/0")
        if sprite is None:
            sprite = canvas_descriptor(helper, f"portal/editor/{code}")
        if sprite:
            point["sprite"] = sprite
    return points


def map_water_areas(root: WzSubProperty) -> list[dict[str, Any]]:
    areas = []
    for container_name in ("swimArea", "rapidStream"):
        container = root.child(container_name)
        if not isinstance(container, WzSubProperty):
            continue
        for area in container.children():
            if not isinstance(area, WzSubProperty):
                continue
            values = {name: child_value(area, name) for name in ("x1", "y1", "x2", "y2")}
            if not all(value is not None for value in values.values()):
                continue
            x1, x2 = sorted((int(values["x1"]), int(values["x2"])))
            y1, y2 = sorted((int(values["y1"]), int(values["y2"])))
            areas.append({
                "path": property_path(area), "kind": container_name,
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            })
    return areas


def map_preview(path: Path) -> dict[str, Any]:
    image = load_image(path)
    root = image.root
    info = root.child("info")
    bounds = {
        "left": int(child_value(info, "VRLeft", -800)),
        "top": int(child_value(info, "VRTop", -600)),
        "right": int(child_value(info, "VRRight", 800)),
        "bottom": int(child_value(info, "VRBottom", 600)),
    }
    footholds = foothold_lines(root)
    if footholds and not all(child_value(info, name) is not None for name in ("VRLeft", "VRTop", "VRRight", "VRBottom")):
        xs = [value for line in footholds for value in (line["x1"], line["x2"])]
        ys = [value for line in footholds for value in (line["y1"], line["y2"])]
        bounds = {"left": min(xs) - 160, "top": min(ys) - 160, "right": max(xs) + 160, "bottom": max(ys) + 160}

    elements: list[dict[str, Any]] = []
    back = root.child("back")
    if isinstance(back, WzSubProperty):
        for item in back.children():
            if not isinstance(item, WzSubProperty):
                continue
            resource = find_resource("Back", str(child_value(item, "bS", "")), path)
            if resource is None:
                continue
            number = str(child_value(item, "no", "0"))
            canvas_path = f"ani/{number}/0" if int(child_value(item, "ani", 0)) else f"back/{number}"
            desc = canvas_descriptor(resource, canvas_path)
            if desc:
                elements.append({
                    "path": property_path(item), "kind": "back", "x": int(child_value(item, "x", 0)), "y": int(child_value(item, "y", 0)),
                    "z": -1000 + int(child_value(item, "front", 0)) * 2000, "flip": bool(child_value(item, "f", 0)), **desc,
                })

    for layer_number in range(8):
        layer = root.child(str(layer_number))
        if not isinstance(layer, WzSubProperty):
            continue
        layer_info = layer.child("info")
        tile_set = str(child_value(layer_info if isinstance(layer_info, WzSubProperty) else None, "tS", ""))
        tile_file = find_resource("Tile", tile_set, path) if tile_set else None
        tile_root = layer.child("tile")
        if tile_file and isinstance(tile_root, WzSubProperty):
            for item in tile_root.children():
                if not isinstance(item, WzSubProperty):
                    continue
                canvas_path = f"{child_value(item, 'u', '')}/{child_value(item, 'no', 0)}"
                desc = canvas_descriptor(tile_file, canvas_path)
                if desc:
                    elements.append({
                        "path": property_path(item), "kind": "tile", "x": int(child_value(item, "x", 0)), "y": int(child_value(item, "y", 0)),
                        "z": layer_number * 100 + int(child_value(item, "zM", 0)), "flip": False, **desc,
                    })
        obj_root = layer.child("obj")
        if isinstance(obj_root, WzSubProperty):
            for item in obj_root.children():
                if not isinstance(item, WzSubProperty):
                    continue
                obj_file = find_resource("Obj", str(child_value(item, "oS", "")), path)
                if obj_file is None:
                    continue
                canvas_path = "/".join(str(child_value(item, name, "")) for name in ("l0", "l1", "l2")) + "/0"
                desc = canvas_descriptor(obj_file, canvas_path)
                if desc:
                    elements.append({
                        "path": property_path(item), "kind": "obj", "x": int(child_value(item, "x", 0)), "y": int(child_value(item, "y", 0)),
                        "z": layer_number * 100 + 20 + int(child_value(item, "z", 0)), "flip": bool(child_value(item, "f", 0)), **desc,
                    })
    elements.sort(key=lambda item: item["z"])
    minimap = canvas_descriptor(path, "miniMap/canvas")
    life = map_life_preview(root, path)
    portals = map_portal_preview(root, path)
    water_areas = map_water_areas(root)
    return {
        "kind": "map", "bounds": bounds, "elements": elements, "footholds": footholds,
        "life": life, "portals": portals, "waterAreas": water_areas, "minimap": minimap,
        "summary": {
            "elements": len(elements), "footholds": len(footholds),
            "mobs": sum(point["kind"] == "mob" for point in life),
            "npcs": sum(point["kind"] == "npc" for point in life), "portals": len(portals),
            "waterAreas": len(water_areas),
        },
    }


def compatibility_category(path: str) -> str:
    if path.split("/", 1)[0] in {"swimArea", "rapidStream", "areaCtrl"}:
        return "waterArea"
    if re.fullmatch(r"[0-7]/obj/[^/]+/(dynamic|move|piece|r)", path):
        return "modernRenderer"
    if path.startswith("life/"):
        return "life"
    if path.startswith("portal/"):
        return "portal"
    if path.startswith("foothold/"):
        return "foothold"
    if path.startswith("info/"):
        return "info"
    if path.startswith("back/") or re.match(r"[0-7]/(obj|tile)/", path):
        return "scene"
    return "other"


def is_spine_map_object(node: WzSubProperty) -> bool:
    if node.child("spineAni") is not None:
        return True
    return any(
        isinstance(child, WzStringProperty)
        and child.name.lower() in map_compat.SPINE_NAMES
        and map_compat.SPINE_VALUE_HINT.search(str(child.value))
        for child in node.children()
    )


def map_resource_references(root: WzSubProperty) -> list[dict[str, Any]]:
    references: dict[tuple[str, str, str], dict[str, Any]] = {}

    def add(kind: str, name: str, canvas_path: str, node_path: str, branch: str = "") -> None:
        if not name:
            return
        key = (kind, name, canvas_path)
        entry = references.setdefault(key, {
            "kind": kind, "name": name, "canvasPath": canvas_path, "branch": branch, "nodes": [],
        })
        if node_path not in entry["nodes"]:
            entry["nodes"].append(node_path)

    back = root.child("back")
    if isinstance(back, WzSubProperty):
        for item in back.children():
            if not isinstance(item, WzSubProperty):
                continue
            number = str(child_value(item, "no", "0"))
            branch = f"ani/{number}" if int(child_value(item, "ani", 0)) else f"back/{number}"
            canvas_path = f"{branch}/0" if branch.startswith("ani/") else branch
            add("back", str(child_value(item, "bS", "")), canvas_path, property_path(item), branch)

    for layer_number in range(8):
        layer = root.child(str(layer_number))
        if not isinstance(layer, WzSubProperty):
            continue
        layer_info = layer.child("info")
        tile_set = str(child_value(layer_info if isinstance(layer_info, WzSubProperty) else None, "tS", ""))
        tile_root = layer.child("tile")
        if isinstance(tile_root, WzSubProperty):
            for item in tile_root.children():
                if isinstance(item, WzSubProperty):
                    branch = f"{child_value(item, 'u', '')}/{child_value(item, 'no', 0)}"
                    add("tile", tile_set, branch, property_path(item), branch)
        obj_root = layer.child("obj")
        if isinstance(obj_root, WzSubProperty):
            for item in obj_root.children():
                if not isinstance(item, WzSubProperty):
                    continue
                if is_spine_map_object(item):
                    continue
                branch = "/".join(str(child_value(item, name, "")) for name in ("l0", "l1", "l2"))
                add("obj", str(child_value(item, "oS", "")), f"{branch}/0", property_path(item), branch)

    life = root.child("life")
    if isinstance(life, WzSubProperty):
        for item in life.children():
            if not isinstance(item, WzSubProperty):
                continue
            kind = "mob" if str(child_value(item, "type", "")) == "m" else "npc"
            add(kind, str(child_value(item, "id", "")), "", property_path(item))
    return list(references.values())


def entity_resource_paths(kind: str, entity_id: str, *, repo_root: Path = _ROOT) -> dict[str, Any]:
    title = "Npc" if kind == "npc" else "Mob"
    return {
        "client": repo_root / "clien" / "Data" / title / f"{entity_id}.img",
        "server": repo_root / "gms-server" / "wz" / f"{title}.wz" / f"{entity_id}.img.xml",
        "stringClient": repo_root / "clien" / "Data" / "String" / f"{title}.img",
        "stringServers": [
            repo_root / "gms-server" / tree / "String.wz" / f"{title}.img.xml"
            for tree in ("wz", "wz-zh-CN")
        ],
        "title": title,
    }


def tms_entity_source(kind: str, entity_id: str, *, tms_data: Path = _TMS_DATA) -> Path:
    title = "Npc" if kind == "npc" else "Mob"
    direct = tms_data / title / f"{entity_id}.img"
    canvas = tms_data / title / "_Canvas" / f"{entity_id}.img"
    return direct if direct.is_file() else canvas


def xml_has_root_child(path: Path, name: str) -> bool:
    if not path.is_file():
        return False
    stat = path.stat()
    return name in _xml_node_paths_cached(str(path.resolve()), stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=20)
def _xml_node_paths_cached(path_text: str, mtime_ns: int, size: int) -> frozenset[str]:
    del mtime_ns, size
    return frozenset(index_xml(Path(path_text).read_bytes()))


def entity_contract_status(
    kind: str, entity_id: str, *, repo_root: Path = _ROOT, tms_data: Path = _TMS_DATA,
) -> dict[str, Any]:
    paths = entity_resource_paths(kind, entity_id, repo_root=repo_root)
    client = paths["client"]
    client_exists = client.is_file()
    canvas_ready = bool(first_entity_frame(client)) if client_exists else False
    string_client = paths["stringClient"]
    string_client_ready = bool(
        string_client.is_file() and load_image(string_client).root.get(entity_id) is not None
    )
    missing_string_servers = [
        relative_path(path) if repo_root == _ROOT else str(path.relative_to(repo_root))
        for path in paths["stringServers"] if not xml_has_root_child(path, entity_id)
    ]
    issues = []
    if not client_exists:
        issues.append("客户端 IMG 缺失")
    elif not canvas_ready:
        issues.append("客户端 IMG 没有可用 Canvas")
    if not paths["server"].is_file():
        issues.append("服务端实体 XML 缺失")
    if not string_client_ready:
        issues.append("客户端 String 记录缺失")
    if missing_string_servers:
        issues.append("服务端 String 记录缺失")
    source = tms_entity_source(kind, entity_id, tms_data=tms_data)
    source_string = tms_data / "String" / f'{paths["title"]}.img'
    source_string_ready = bool(
        source_string.is_file() and load_image(source_string).root.get(entity_id) is not None
    )
    if not client_exists:
        status = "missingFile"
    elif not canvas_ready:
        status = "missingCanvas"
    elif not paths["server"].is_file():
        status = "missingServer"
    elif not string_client_ready or missing_string_servers:
        status = "missingString"
    else:
        status = "ready"
    return {
        "status": status, "issues": issues, "clientExists": client_exists,
        "canvasReady": canvas_ready, "serverExists": paths["server"].is_file(),
        "stringClientExists": string_client_ready,
        "stringServerExists": not missing_string_servers,
        "sourcePath": relative_path(source) if source.is_file() else str(source),
        "sourceExists": source.is_file(), "sourceStringExists": source_string_ready,
        "autoCopy": status != "missingCanvas" and source.is_file() and source_string_ready,
    }


def audit_map_resources(left_path: Path, right_path: Path) -> list[dict[str, Any]]:
    if not right_path.is_file() or not right_path.name.lower().endswith(".img"):
        return []
    right_root = load_image(right_path).root
    left_root = load_image(left_path).root if left_path.is_file() and left_path.name.lower().endswith(".img") else None
    left_data = data_root_for(left_path)
    folders = {"back": ("Map", "Back"), "tile": ("Map", "Tile"), "obj": ("Map", "Obj"), "mob": ("Mob",), "npc": ("Npc",)}
    left_references = {}
    if left_root is not None:
        for left_reference in map_resource_references(left_root):
            for node_path in left_reference["nodes"]:
                left_references[(left_reference["kind"], node_path)] = left_reference

    def resource_path(reference: dict[str, Any]) -> Path:
        relative = Path(*folders[reference["kind"]]) / f'{reference["name"]}.img'
        resource = left_data / relative
        if not resource.is_file() and reference["kind"] in {"mob", "npc"}:
            resource = resource.parent / "_Canvas" / resource.name
        return resource

    result = []
    for reference in map_resource_references(right_root):
        relative = Path(*folders[reference["kind"]]) / f'{reference["name"]}.img'
        resource = resource_path(reference)
        contract = None
        projected = False
        if reference["kind"] in {"mob", "npc"}:
            contract = entity_contract_status(reference["kind"], reference["name"])
            status = contract["status"]
        elif not resource.is_file():
            status = "missingFile"
        else:
            status = "ready" if canvas_descriptor(resource, reference["canvasPath"]) else "missingCanvas"
        if status != "ready" and reference["kind"] in {"back", "tile", "obj"}:
            projected_references = [
                left_references.get((reference["kind"], node_path)) for node_path in reference["nodes"]
            ]
            projected = bool(projected_references) and all(
                item is not None
                and resource_path(item).is_file()
                and canvas_descriptor(resource_path(item), item["canvasPath"])
                for item in projected_references
            )
            if projected:
                status = "ready"
        auto_copy = contract["autoCopy"] if contract else False
        if contract is None and status != "ready":
            title = {"back": "Back", "tile": "Tile", "obj": "Obj"}[reference["kind"]]
            source_resource = _TMS_DATA / "Map" / title / f'{reference["name"]}.img'
            target_branch_missing = True
            if resource.is_file():
                target_branch_missing = load_image(resource).root.get(reference["branch"]) is None
            auto_copy = bool(
                source_resource.is_file() and target_branch_missing
                and not (reference["kind"] == "obj" and reference["name"] == "connect")
            )
            contract = {
                "issues": [
                    "客户端资源文件缺失" if status == "missingFile"
                    else f'缺少 Canvas：{reference["canvasPath"]}'
                ],
                "sourceExists": source_resource.is_file(), "sourcePath": relative_path(source_resource),
                "autoCopy": auto_copy,
            }
        result.append({
            **reference, "status": status,
            "clientPath": relative_path(resource) if resource.is_file() else relative_path(left_data / relative),
            "contract": contract, "autoCopy": auto_copy, "projected": projected,
        })
    severity = {"ready": 0, "missingString": 1, "missingServer": 2, "missingCanvas": 3, "missingFile": 4}
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in result:
        key = (item["kind"], item["name"])
        entry = grouped.setdefault(key, {
            "kind": item["kind"], "name": item["name"], "status": item["status"],
            "clientPath": item["clientPath"], "canvasPaths": [], "nodes": [],
            "issueNodes": [], "branches": [], "autoCopy": item["autoCopy"],
            "contract": item.get("contract"), "projected": item.get("projected", False),
        })
        if severity[item["status"]] > severity[entry["status"]]:
            entry["status"] = item["status"]
            entry["contract"] = item.get("contract")
        entry["autoCopy"] = entry["autoCopy"] or item["autoCopy"]
        entry["projected"] = entry["projected"] or item.get("projected", False)
        if item["canvasPath"] and item["canvasPath"] not in entry["canvasPaths"] and len(entry["canvasPaths"]) < 6:
            entry["canvasPaths"].append(item["canvasPath"])
        if item.get("branch") and item["branch"] not in entry["branches"]:
            entry["branches"].append(item["branch"])
        for node_path in item["nodes"]:
            if node_path not in entry["nodes"]:
                entry["nodes"].append(node_path)
            if item["status"] != "ready" and node_path not in entry["issueNodes"]:
                entry["issueNodes"].append(node_path)
    return sorted(grouped.values(), key=lambda item: (item["status"] == "ready", item["kind"], natural_key(item["name"])))


def attach_resource_statuses(rows: list[dict[str, Any]], resources: list[dict[str, Any]]) -> None:
    row_by_path = {row["path"]: row for row in rows}
    for resource in resources:
        summary = {
            "kind": resource["kind"], "name": resource["name"], "status": resource["status"],
            "issues": (resource.get("contract") or {}).get("issues", []),
            "clientPath": resource["clientPath"], "autoCopy": resource.get("autoCopy", False),
        }
        node_paths = (resource.get("issueNodes") or resource["nodes"]) if resource["status"] != "ready" else resource["nodes"]
        for node_path in node_paths:
            row = row_by_path.get(node_path)
            if row is not None:
                row.setdefault("resources", []).append(summary)


_CRASH_PHASES = {
    "unknown": "时机未知",
    "map_load": "进图瞬间（尚未看到怪物）",
    "entity_appear": "怪物/NPC 首次出现",
    "attack": "怪物攻击时",
    "death": "怪物死亡时",
}


def normalize_crash_phase(value: str) -> str:
    phase = str(value or "unknown").strip()
    return phase if phase in _CRASH_PHASES else "unknown"


@lru_cache(maxsize=16)
def _regional_scene_usage(bucket_text: str, map_prefix: str) -> dict[str, Any]:
    bucket = Path(bucket_text)
    usage: dict[tuple[str, str, str], list[str]] = {}
    parsed = 0
    errors = 0
    files = sorted(bucket.glob(f"{map_prefix}*.img"), key=lambda item: natural_key(item.name))
    for sibling in files:
        try:
            references = map_resource_references(load_image(sibling).root)
        except Exception:
            errors += 1
            continue
        parsed += 1
        for reference in references:
            if reference["kind"] not in {"back", "obj", "tile"}:
                continue
            key = (reference["kind"], reference["name"], reference["canvasPath"])
            maps = usage.setdefault(key, [])
            if sibling.stem not in maps:
                maps.append(sibling.stem)
    return {"mapCount": len(files), "parsedCount": parsed, "errors": errors, "usage": usage}


def _canvas_link(node: WzProperty | None) -> tuple[str, str]:
    if isinstance(node, WzUolProperty):
        return "UOL", str(node.value)
    if not isinstance(node, WzCanvasProperty):
        return "", ""
    for name, label in (("_outlink", "_outlink"), ("_inlink", "_inlink")):
        link = node.child(name)
        if isinstance(link, WzStringProperty):
            return label, str(link.value).replace("\\", "/")
    return "", ""


def analyze_scene_resource_risks(path: Path, image: WzImage, phase: str = "unknown") -> dict[str, Any]:
    """Collect read-only scene-reference evidence and rank concrete A/B candidates."""
    phase = normalize_crash_phase(phase)
    map_id = infer_id(path)
    if not re.fullmatch(r"\d{9}", map_id):
        return {"regionalMapCount": 0, "parsedMapCount": 0, "errors": [], "resources": [], "suspects": []}
    bucket = _TMS_DATA / "Map" / "Map" / f"Map{map_id[0]}"
    tms_map = bucket / f"{map_id}.img"
    region = _regional_scene_usage(str(bucket), map_id[:6])
    resources: list[dict[str, Any]] = []
    errors: list[str] = []
    folders = {"back": "Back", "obj": "Obj", "tile": "Tile"}
    for reference in map_resource_references(image.root):
        kind = reference["kind"]
        if kind not in folders:
            continue
        client_file = find_resource(folders[kind], reference["name"], path)
        source_file = find_resource(folders[kind], reference["name"], tms_map)
        if client_file is None or source_file is None:
            continue
        try:
            source_image = load_image(source_file)
            source_node = source_image.root.get(reference["canvasPath"])
            source_link_type, source_link_path = _canvas_link(source_node)
            source_width = int(source_node.width) if isinstance(source_node, WzCanvasProperty) else 0
            source_height = int(source_node.height) if isinstance(source_node, WzCanvasProperty) else 0
            source_format = (
                f"{int(source_node.format)}/{int(source_node.format2)}"
                if isinstance(source_node, WzCanvasProperty) else ""
            )
            _, source_target, source_target_file = resolve_canvas_node(
                source_image, reference["canvasPath"], source_file,
            )
            client_image = load_image(client_file)
            _, client_target, client_target_file = resolve_canvas_node(
                client_image, reference["canvasPath"], client_file,
            )
        except Exception as exc:
            errors.append(
                f"{reference['nodes'][0] if reference['nodes'] else reference['canvasPath']}: {exc}"
            )
            continue
        key = (kind, reference["name"], reference["canvasPath"])
        usage_maps = list(region["usage"].get(key, []))
        source_pixels = max(1, source_width * source_height)
        client_pixels = int(client_target.width) * int(client_target.height)
        placeholder_link = source_width == 1 and source_height == 1 and bool(source_link_type)
        exclusive = region["parsedCount"] > 1 and len(usage_maps) == 1
        large_materialization = placeholder_link and client_pixels >= 250_000
        risk = "high" if exclusive and large_materialization else ""
        resources.append({
            "kind": kind, "name": reference["name"], "canvasPath": reference["canvasPath"],
            "mapPath": reference["nodes"][0] if reference["nodes"] else "",
            "mapPaths": reference["nodes"], "regionalUsageCount": len(usage_maps),
            "regionalMaps": usage_maps[:8], "sourcePath": relative_path(source_file),
            "sourceWidth": source_width, "sourceHeight": source_height, "sourceFormat": source_format,
            "sourceLinkType": source_link_type, "sourceLinkPath": source_link_path,
            "sourceTargetPath": relative_path(source_target_file),
            "sourceTargetWidth": int(source_target.width), "sourceTargetHeight": int(source_target.height),
            "clientPath": relative_path(client_file), "clientTargetPath": relative_path(client_target_file),
            "clientWidth": int(client_target.width), "clientHeight": int(client_target.height),
            "clientFormat": f"{int(client_target.format)}/{int(client_target.format2)}",
            "pixelExpansionRatio": round(client_pixels / source_pixels, 1),
            "placeholderLink": placeholder_link, "exclusive": exclusive, "risk": risk,
        })
    resources.sort(key=lambda item: (item["risk"] != "high", item["kind"], natural_key(item["mapPath"])))
    return {
        "regionalMapCount": region["mapCount"], "parsedMapCount": region["parsedCount"],
        "regionalPrefix": map_id[:6], "errors": errors, "resources": resources,
        "suspects": [item for item in resources if item["risk"]], "phase": phase,
    }


def compatibility_analysis(
    left: dict[str, dict[str, Any]], right: dict[str, dict[str, Any]], left_path: Path, right_path: Path,
) -> dict[str, Any]:
    left_available = left_path.is_file()
    right_available = right_path.is_file()
    item_id = infer_id(left_path)
    right_only = sorted(
        (set(right) - set(left)) - {""},
        key=lambda value: [natural_key(part) for part in value.split("/")],
    )
    right_only_set = set(right_only)
    added_roots = [path for path in right_only if (path.rsplit("/", 1)[0] if "/" in path else "") not in right_only_set]
    definitions = {
        "waterArea": ("局部游泳与水流区域", "中", "旧端使用 swimArea 矩形；现代 rapidStream 的坐标可投影，areaCtrl 物理参数不能直接复制。"),
        "modernRenderer": ("现代渲染字段候选", "高", "旧客户端通常不识别这组对象控制字段。不要直接复制；忽略字段并用旧版 oS/l0/l1/l2、x/y/z/f 结构重建可见对象。"),
        "scene": ("场景与图层结构", "中", "核对引用的 Back/Obj/Tile IMG 与 Canvas 路径；只迁移可见帧和旧客户端已证明支持的字段。"),
        "life": ("怪物与 NPC 节点", "中", "先验证旧客户端 Mob/Npc 资源和服务端生命节点，再按旧版 life 字段投影。"),
        "portal": ("传送门节点", "中", "保留旧版 pn/pt/tn/tm/x/y 结构，并验证 MapHelper 对应类型和目标地图。"),
        "foothold": ("地形节点", "高", "保持 foothold 层级、编号及 prev/next 链一致；不要只复制坐标叶子。"),
        "info": ("地图信息字段", "中", "按旧客户端已存在的 info 字段白名单迁移，未知开关默认不复制。"),
        "other": ("其他 B 独有结构", "待确认", "仅能确认旧客户端没有同路径节点；需查旧版同类地图或运行证据后再决定。"),
    }
    grouped: dict[str, list[str]] = {key: [] for key in definitions}
    for path in right_only:
        grouped[compatibility_category(path)].append(path)
    categories = [{
        "id": key, "title": definitions[key][0], "risk": definitions[key][1], "guidance": definitions[key][2],
        "count": len(paths), "paths": paths[:20],
    } for key, paths in grouped.items() if paths]
    findings = []
    finding_counts = {"modern": 0, "incompatible": 0, "review": 0}
    for path in right_only:
        meta = right[path]
        annotated = annotate_meta(path, meta, "map", item_id)
        compatibility = annotated["compatibility"]
        if compatibility["status"] == "ok":
            continue
        finding_counts[compatibility["status"]] += 1
        if len(findings) < 80:
            findings.append({
                "path": path, "meaning": annotated["meaning"], "scope": annotated["scope"],
                "migration": annotated["migration"], **compatibility,
            })
    changed_paths = [path for path in set(left) & set(right) if comparable(left[path]) != comparable(right[path])]
    changed_paths.sort(key=lambda path: (not path.startswith("info/"), [natural_key(part) for part in path.split("/")]))
    changed_nodes = []
    for path in changed_paths:
        meta = annotate_meta(path, left[path], "map", item_id)
        if meta.get("value") is None and meta.get("type") == "imgdir":
            continue
        changed_nodes.append({
            "path": path, "leftValue": comparable(left[path]), "rightValue": comparable(right[path]),
            "meaning": meta["meaning"], "scope": meta["scope"], "valueGuide": meta["valueGuide"],
            "migration": meta["migration"],
        })
        if len(changed_nodes) >= 60:
            break
    resources = audit_map_resources(left_path, right_path)
    return {
        "leftAvailable": left_available, "rightAvailable": right_available,
        "rightOnlyCount": len(right_only), "addedRoots": added_roots[:40], "addedRootCount": len(added_roots),
        "modernCandidateCount": finding_counts["modern"], "incompatibleCount": finding_counts["incompatible"],
        "reviewCount": finding_counts["review"], "findings": findings, "changedNodes": changed_nodes,
        "categories": categories, "resources": resources,
        "missingResourceCount": sum(item["status"] != "ready" for item in resources),
    }


def _diagnostic_finding(
    domain: str, severity: str, title: str, detail: str, action: str, *,
    confidence: str = "high", map_path: str = "", entity_kind: str = "", entity_id: str = "",
    evidence: Iterable[str] = (),
) -> dict[str, Any]:
    return {
        "domain": domain, "severity": severity, "title": title, "detail": detail,
        "action": action, "confidence": confidence, "mapPath": map_path,
        "entityKind": entity_kind, "entityId": entity_id, "evidence": list(evidence),
    }


def _normalized_nodes(path: Path) -> list[dict[str, Any]]:
    flattened, _ = flatten_source(path)
    output = []
    for node_path, meta in flattened.items():
        name = str(meta.get("name") or (node_path.rsplit("/", 1)[-1] if node_path else "root"))
        parent_name = node_path.rsplit("/", 2)[-2] if "/" in node_path else ""
        output.append({**meta, "path": node_path, "name": name, "parent_name": parent_name})
    return output


def _numeric_child_gaps(root: WzSubProperty, node_path: str) -> list[str]:
    node = root.get(node_path)
    if not isinstance(node, WzSubProperty):
        return []
    names = [child.name for child in node.children()]
    if not names or any(not name.isdigit() for name in names):
        return []
    numbers = {int(name) for name in names}
    return [str(number) for number in range(max(numbers) + 1) if number not in numbers]


def _audit_canvas_payloads(path: Path) -> dict[str, Any]:
    image = load_image(path)
    canvases = [node for node in iter_subtree(image.root) if isinstance(node, WzCanvasProperty)]
    visible = 0
    errors = []
    for node in canvases:
        node_path = property_path(node)
        if (int(node.format), int(node.format2)) != (1, 0):
            errors.append(f"{node_path}: Canvas 格式 {node.format}/{node.format2}，不是 GMS ARGB4444 1/0")
            continue
        if int(node.width) > 2048 or int(node.height) > 2048:
            errors.append(f"{node_path}: Canvas 尺寸 {node.width}x{node.height} 超过旧端 2048 单边上限")
            continue
        try:
            resolved_image, canvas, resolved_path = resolve_canvas_node(image, node_path, path)
            del resolved_image
            stat = resolved_path.stat()
            bitmap = decode_canvas(
                canvas, region=canvas_region(str(resolved_path), stat.st_mtime_ns, stat.st_size),
            )
            if bitmap.size != (int(canvas.width), int(canvas.height)):
                errors.append(f"{node_path}: 解码尺寸与 Canvas 头不一致")
            elif bitmap.getbbox() is not None:
                visible += 1
        except Exception as exc:
            errors.append(f"{node_path}: {exc}")
    return {"canvases": len(canvases), "visible": visible, "errors": errors}


def _case_control_path(path: str) -> str:
    parts = path.split("/")
    if len(parts) > 1 and parts[0] in {"back", "life", "portal", "reactor", "ladderRope"} and parts[1].isdigit():
        parts[1] = "*"
    if len(parts) > 2 and parts[0].isdigit() and parts[1] in {"obj", "tile"} and parts[2].isdigit():
        parts[2] = "*"
    if len(parts) > 3 and parts[0] == "foothold":
        parts[1:4] = ["*", "*", "*"]
    return "/".join(parts)


def _case_control_features(path: Path) -> dict[tuple[Any, ...], dict[str, Any]]:
    image = load_image(path)
    root = image.root
    features: dict[tuple[Any, ...], dict[str, Any]] = {}

    def add(key: tuple[Any, ...], category: str, title: str, map_path: str, detail: str) -> None:
        item = features.setdefault(key, {
            "category": category, "title": title, "mapPath": map_path,
            "detail": detail, "paths": [],
        })
        if map_path and map_path not in item["paths"] and len(item["paths"]) < 8:
            item["paths"].append(map_path)

    containers = ["back", "life", "portal", "reactor", "ladderRope"]
    containers.extend(f"{layer}/{kind}" for layer in range(8) for kind in ("obj", "tile"))
    for node_path in containers:
        node = root.get(node_path)
        if not isinstance(node, WzSubProperty):
            continue
        names = [child.name for child in node.children()]
        numeric = [int(name) for name in names if name.isdigit()]
        dense = len(numeric) == len(names) and numeric == list(range(len(numeric)))
        add(
            ("container", node_path, len(names), dense), "structure",
            f"{node_path} 子节点数量与连续性", node_path,
            f"{len(names)} 个子节点，数字编号{'连续' if dense else '不连续'}。",
        )
        schemas = Counter(
            tuple((child.name, child.type_name.lower()) for child in entry.children())
            for entry in node.children() if isinstance(entry, WzSubProperty)
        )
        if schemas:
            signature = tuple(sorted(schemas.items(), key=lambda item: (item[1], item[0])))
            summary = "；".join(
                f"{count} 条 × [{', '.join(name for name, _ in schema)}]"
                for schema, count in signature
            )
            key = ("schema", node_path, signature)
            add(key, "schema", f"{node_path} 字段顺序分布", node_path, summary)
            rare_schemas = {schema for schema, count in signature if count == min(schemas.values())}
            for entry in node.children():
                if not isinstance(entry, WzSubProperty):
                    continue
                schema = tuple((child.name, child.type_name.lower()) for child in entry.children())
                if schema in rare_schemas:
                    add(key, "schema", f"{node_path} 字段顺序分布", property_path(entry), summary)

    sensitive_fields = {
        "forcedZPage", "forcedZMass", "piece", "spineAni", "dynamic", "move",
        "ani", "front", "type", "pt", "zM", "r",
    }
    for node in iter_subtree(root):
        node_path = property_path(node)
        if isinstance(node, (WzSubProperty, WzCanvasProperty, WzVectorProperty)):
            continue
        leaf_name = node_path.rsplit("/", 1)[-1]
        if not (node_path.startswith("info/") or node_path.startswith("miniMap/") or leaf_name in sensitive_fields):
            continue
        try:
            value = node.value
        except Exception:
            continue
        normalized = _case_control_path(node_path)
        key = ("field", normalized, node.type_name.lower(), value)
        add(key, "field", f"{normalized} = {value}", node_path, f"类型 {node.type_name.lower()}。")

    for node in iter_subtree(root):
        if not isinstance(node, WzCanvasProperty):
            continue
        node_path = property_path(node)
        signature = (int(node.width), int(node.height), int(node.format), int(node.format2))
        add(
            ("canvas", node_path, *signature), "canvas",
            f"{node_path} Canvas {signature[0]}x{signature[1]}", node_path,
            f"格式 {signature[2]}/{signature[3]}，像素负载{'存在' if node.has_pixels() else '缺失'}。",
        )

    portal = root.child("portal")
    if isinstance(portal, WzSubProperty):
        topology = tuple(sorted(Counter(int(child_value(entry, "pt", -1)) for entry in portal.children()).items()))
        add(("portal", topology), "portal", "Portal 类型分布", "portal", str(dict(topology)))

    for reference in map_resource_references(root):
        if reference["kind"] not in {"back", "obj", "tile"}:
            continue
        key = ("resource", reference["kind"], reference["name"], reference["canvasPath"])
        add(
            key, "resource",
            f"{reference['kind']} {reference['name']}/{reference['canvasPath']}",
            reference["nodes"][0] if reference["nodes"] else "", "场景资源分支。",
        )
    return features


def analyze_regional_crash_cases(path: Path, peer_map_ids: Iterable[str]) -> dict[str, Any]:
    map_id = infer_id(path)
    peers = []
    for raw in peer_map_ids:
        peer = str(raw).strip()
        if peer and peer != map_id and peer not in peers:
            peers.append(peer)
    if not peers:
        return {"enabled": False, "caseMaps": [map_id], "controlMaps": [], "exclusive": [], "counterexamples": [], "errors": []}
    if any(not re.fullmatch(r"\d{9}", peer) or peer[:6] != map_id[:6] for peer in peers):
        raise ValueError("同样崩溃地图必须是当前地区的 9 位地图 ID")

    case_maps = [map_id, *peers]
    case_paths = {map_id: path}
    for peer in peers:
        peer_path = path.parent / f"{peer}.img"
        if not peer_path.is_file():
            raise ValueError(f"同样崩溃地图不存在: {relative_path(peer_path)}")
        case_paths[peer] = peer_path
    sibling_paths = {
        sibling.stem: sibling for sibling in path.parent.glob(f"{map_id[:6]}*.img")
        if sibling.stem not in case_maps
    }

    profiles: dict[str, dict[tuple[Any, ...], dict[str, Any]]] = {}
    errors = []
    for sibling_id, sibling_path in {**case_paths, **sibling_paths}.items():
        try:
            profiles[sibling_id] = _case_control_features(sibling_path)
        except Exception as exc:
            errors.append(f"{sibling_id}: {exc}")
    if any(case_id not in profiles for case_id in case_maps):
        raise ValueError("崩溃组地图无法完整解析，不能进行地区对照")

    common = set.intersection(*(set(profiles[case_id]) for case_id in case_maps))
    control_maps = sorted((set(profiles) - set(case_maps)), key=natural_key)
    rows = []
    for key in common:
        control_users = [control for control in control_maps if key in profiles[control]]
        source = profiles[map_id][key]
        rows.append({
            **{name: value for name, value in source.items() if name != "paths"},
            "casePaths": {case_id: profiles[case_id][key]["paths"] for case_id in case_maps},
            "controlCount": len(control_users), "controlMaps": control_users,
        })
    priority = {"schema": 0, "canvas": 1, "structure": 2, "portal": 3, "field": 4, "resource": 5}
    rows.sort(key=lambda item: (item["controlCount"], priority.get(item["category"], 9), natural_key(item["title"])))
    exclusive = [item for item in rows if item["controlCount"] == 0][:20]
    counterexamples = [
        item for item in rows
        if item["controlCount"] and item["category"] == "field"
        and any(name in item["title"] for name in ("forcedZPage", "forcedZMass", "piece"))
    ][:12]
    return {
        "enabled": True, "caseMaps": case_maps, "controlMaps": control_maps,
        "parsedControlCount": len(control_maps), "regionalMapCount": len(case_maps) + len(control_maps),
        "exclusive": exclusive, "counterexamples": counterexamples, "errors": errors,
        "conclusion": (
            f"找到 {len(exclusive)} 个崩溃组独占特征；它们是定位候选，不是崩溃证明。"
            if exclusive else "未找到崩溃组共有且对照图缺失的静态特征。"
        ),
    }


def _scalar_sync_differences(client_path: Path, server_path: Path) -> list[str]:
    client, _ = flatten_source(client_path)
    server, _ = flatten_source(server_path)
    differences = []
    scalar_types = {"short", "int", "long", "float", "double", "string", "vector", "uol", "null"}
    for node_path in sorted(set(client) | set(server), key=natural_key):
        left, right = client.get(node_path), server.get(node_path)
        if (left and left.get("type") not in scalar_types) and (right and right.get("type") not in scalar_types):
            continue
        if comparable(left) != comparable(right):
            differences.append(node_path or "/")
    return differences


def diagnose_map_crash(
    path: Path, phase: str = "unknown", peer_map_ids: Iterable[str] = (),
) -> dict[str, Any]:
    require_repo_write(path)
    if not path.is_file() or "/clien/Data/Map/Map/" not in path.as_posix():
        raise ValueError("崩溃诊断只支持项目内客户端地图 IMG")
    phase = normalize_crash_phase(phase)
    map_id = infer_id(path)
    case_control = analyze_regional_crash_cases(path, peer_map_ids)
    findings: list[dict[str, Any]] = []
    verified: list[str] = []
    checked = 0

    image = load_image(path)
    checked += 1
    if image.truncated or image.parse_warnings:
        findings.append(_diagnostic_finding(
            "map", "crash", "地图 IMG 结构损坏", str(image.parse_warnings),
            "先恢复最后可工作的地图 IMG；不要在损坏文件上继续叠加修改。",
        ))
    else:
        verified.append("地图 IMG 可完整解析，无 truncated 或 parse_warnings")

    server_path = server_xml_for_client(path)
    checked += 1
    if server_path is None or not server_path.is_file():
        findings.append(_diagnostic_finding(
            "server", "crash", "服务端地图 XML 缺失", relative_path(server_path) if server_path else path.name,
            "补齐对应 Map.wz XML，并确认它与客户端地图引用相同的 life、portal 和 foothold。",
        ))
    else:
        try:
            ET.parse(server_path)
            differences = _scalar_sync_differences(path, server_path)
            if differences:
                findings.append(_diagnostic_finding(
                    "server", "warn", "客户端与服务端地图节点不同步",
                    f"{len(differences)} 个标量节点不同，前几项：{', '.join(differences[:8])}",
                    "先核对差异是否有意；life、portal、foothold 和 info 物理字段应保持一致。",
                    confidence="medium", map_path=differences[0] if differences else "",
                ))
            else:
                verified.append("客户端与服务端地图标量节点一致")
        except Exception as exc:
            findings.append(_diagnostic_finding(
                "server", "crash", "服务端地图 XML 无法解析", str(exc), "恢复或重新生成该地图 XML。",
            ))

    checked += 1
    map_nodes = _normalized_nodes(path)
    map_rule_groups: dict[tuple[str, str, str], list[str]] = {}
    for item in map_compat.post_analyze(map_nodes, "map"):
        verdict = item["verdict"]
        if verdict.status == "ok":
            continue
        key = (verdict.status, verdict.reason, verdict.suggestion)
        map_rule_groups.setdefault(key, []).append(item["path"] or "/")
    for (status, reason, suggestion), paths in map_rule_groups.items():
        severity = "crash" if status == "incompatible" else "warn"
        examples = "、".join(paths[:4])
        detail = reason if len(paths) == 1 else f"{reason} 共 {len(paths)} 个节点，示例：{examples}。"
        findings.append(_diagnostic_finding(
            "map", severity, f"地图节点规则：{map_compat.STATUS_LABELS[status]}", detail,
            suggestion or "与旧端同类可工作地图对照。",
            confidence="high" if severity == "crash" else ("low" if status == "modern" else "medium"),
            map_path=paths[0] if paths else "",
        ))
    back_gaps = _numeric_child_gaps(image.root, "back")
    if back_gaps:
        findings.append(_diagnostic_finding(
            "map", "warn", "背景编号存在空洞，当前 A/B 结果无效",
            f"back 子节点缺少 {', '.join(back_gaps)}，但后面仍有更大的数字节点。"
            "旧端是否容忍该结构尚无运行证据；至少不能用这个实验版排除被删除的背景。",
            "先把后继背景按原顺序改成连续编号，再复测同一个候选；不要同时改其他地图节点。",
            confidence="high", map_path="back",
            evidence=(f"当前 back 顺序：{', '.join(child.name for child in image.root.child('back').children())}",),
        ))
    if not any(item["domain"] == "map" and item["severity"] == "crash" for item in findings):
        verified.append("地图节点未命中已知旧端必崩规则")

    checked += 1
    map_canvas = _audit_canvas_payloads(path)
    if map_canvas["errors"]:
        findings.append(_diagnostic_finding(
            "map", "crash", "地图内嵌 Canvas 解码失败", "；".join(map_canvas["errors"][:5]),
            "修复列出的 Canvas 格式、尺寸或像素负载；不能只修改 XML 尺寸。",
        ))
    else:
        verified.append(f"地图内嵌 {map_canvas['canvases']} 个 Canvas 均可解码")

    checked += 1
    resources = audit_map_resources(path, path)
    broken_resources = [item for item in resources if item["status"] != "ready"]
    for item in broken_resources:
        findings.append(_diagnostic_finding(
            "resource", "crash", f"{item['kind'].upper()} 资源不可用：{item['name']}",
            f"{item['clientPath']}，状态 {item['status']}",
            "补齐旧端资源并解析实际 Canvas；同名 IMG 存在不代表引用路径可用。",
            map_path=item["nodes"][0] if item["nodes"] else "",
        ))
    if not broken_resources:
        verified.append(f"地图引用的 {len(resources)} 组 Back/Obj/Tile/生命资源路径均可解析")

    checked += 1
    scene_resources = analyze_scene_resource_risks(path, image, phase)
    for item in scene_resources["suspects"]:
        node_names = "、".join(item["mapPaths"])
        confidence = "high" if phase == "map_load" else ("medium" if phase in {"unknown", "entity_appear"} else "low")
        detail = (
            f"地图节点 {node_names} 引用 {item['name']}/{item['canvasPath']}。"
            f"TMS 主资源是 {item['sourceWidth']}x{item['sourceHeight']}、格式 {item['sourceFormat']} 的占位 Canvas，"
            f"通过 {item['sourceLinkType']}={item['sourceLinkPath']} 指向 "
            f"{item['sourceTargetWidth']}x{item['sourceTargetHeight']}；旧端客户端资源已实体化为 "
            f"{item['clientWidth']}x{item['clientHeight']}（{item['pixelExpansionRatio']:,.1f} 倍像素）。"
            f"同区域 {scene_resources['parsedMapCount']} 张已解析地图中只有 "
            f"{item['regionalUsageCount']} 张使用该分支。"
        )
        if phase == "map_load":
            detail += " 崩溃发生在进图瞬间，这条场景加载链与时机直接吻合。"
        findings.append(_diagnostic_finding(
            "resource", "warn", f"区域独占的大型场景分支：{item['name']}/{item['canvasPath']}",
            detail,
            f"在测试副本中只同步移除 {node_names}，重进 {map_id}；若不再崩溃，即可把范围收敛到这条资源链。",
            confidence=confidence, map_path=item["mapPath"], evidence=(
                f"地图节点：{node_names}",
                f"TMS：{item['sourcePath']} → {item['sourceLinkPath']}",
                f"旧端：{item['clientPath']} / {item['clientWidth']}x{item['clientHeight']} / 格式 {item['clientFormat']}",
                f"区域用量：{item['regionalUsageCount']}/{scene_resources['parsedMapCount']} 张地图",
            ),
        ))
    if scene_resources["errors"]:
        findings.append(_diagnostic_finding(
            "resource", "warn", "部分场景资源证据链无法展开",
            "；".join(scene_resources["errors"][:5]),
            "先修复列出的资源链接或缺失节点，再重新运行诊断。", confidence="medium",
        ))
    elif scene_resources["resources"]:
        verified.append(
            f"已追踪 {len(scene_resources['resources'])} 条 Back/Obj/Tile 源链接，并对比 "
            f"{scene_resources['parsedMapCount']} 张同区域地图的使用频率"
        )

    footholds = {
        node.name for node in iter_subtree(image.root.child("foothold"))
        if isinstance(node, WzSubProperty) and node.child("x1") is not None and node.child("x2") is not None
    }
    life_root = image.root.child("life")
    entities: dict[tuple[str, str], list[str]] = {}
    if isinstance(life_root, WzSubProperty):
        for spawn in life_root.children():
            kind = str(child_value(spawn, "type", ""))
            entity_id = str(child_value(spawn, "id", ""))
            entities.setdefault((kind, entity_id), []).append(property_path(spawn))
            fh = str(child_value(spawn, "fh", ""))
            if fh and fh not in footholds:
                findings.append(_diagnostic_finding(
                    "map", "crash", f"生命节点引用不存在的 foothold：{entity_id}",
                    f"{property_path(spawn)}/fh={fh}，地图碰撞层没有该编号。",
                    "把刷新点 fh 改到实际存在的 foothold；客户端和服务端必须同步。",
                    map_path=property_path(spawn),
                ))

    entity_summaries = []
    for (kind, entity_id), spawns in sorted(entities.items()):
        if kind not in {"m", "n"} or not entity_id:
            findings.append(_diagnostic_finding(
                "map", "warn", f"未知 life 类型：{kind or '空'}", f"实体 {entity_id or '?'} 出现 {len(spawns)} 次。",
                "核对 life/type，旧端只应使用 m（怪物）或 n（NPC）。", map_path=spawns[0],
            ))
            continue
        folder = "Mob" if kind == "m" else "Npc"
        entity_kind = "mob" if kind == "m" else "npc"
        client_path = _ROOT / "clien" / "Data" / folder / f"{int(entity_id):07d}.img"
        entity_server = _ROOT / "gms-server" / "wz" / f"{folder}.wz" / f"{int(entity_id):07d}.img.xml"
        summary = {"kind": entity_kind, "id": entity_id, "spawns": len(spawns), "clientPath": relative_path(client_path)}
        entity_summaries.append(summary)
        checked += 1
        if not client_path.is_file():
            findings.append(_diagnostic_finding(
                "entity", "crash", f"{folder} {entity_id} 客户端资源缺失", relative_path(client_path),
                "先补齐客户端 IMG；地图进入视野时加载不到怪物资源极可能直接崩溃。",
                map_path=spawns[0], entity_kind=entity_kind, entity_id=entity_id,
            ))
            continue
        try:
            entity_image = load_image(client_path)
            if entity_image.truncated or entity_image.parse_warnings:
                raise ValueError(str(entity_image.parse_warnings))
            canvas = _audit_canvas_payloads(client_path)
            summary.update(canvases=canvas["canvases"], visible=canvas["visible"])
            if canvas["errors"] or (canvas["canvases"] and not canvas["visible"]):
                detail = "；".join(canvas["errors"][:5]) or "所有 Canvas 都没有可见像素"
                findings.append(_diagnostic_finding(
                    "entity", "crash", f"{folder} {entity_id} Canvas 不可用", detail,
                    "修复实体动作帧的真实像素、格式和链接后再进图。",
                    map_path=spawns[0], entity_kind=entity_kind, entity_id=entity_id,
                ))
            elif canvas["canvases"]:
                verified.append(f"{folder} {entity_id}：{canvas['canvases']} 个 Canvas 可解码，{canvas['visible']} 个有可见像素")
        except Exception as exc:
            findings.append(_diagnostic_finding(
                "entity", "crash", f"{folder} {entity_id} IMG 无法解析", str(exc),
                "恢复该实体最后可工作的客户端 IMG。", map_path=spawns[0],
                entity_kind=entity_kind, entity_id=entity_id,
            ))
            continue

        checked += 1
        if not entity_server.is_file():
            findings.append(_diagnostic_finding(
                "server", "crash", f"{folder} {entity_id} 服务端 XML 缺失", relative_path(entity_server),
                "补齐服务端实体 XML；怪物生成阶段可能失败或断开地图线程。",
                map_path=spawns[0], entity_kind=entity_kind, entity_id=entity_id,
            ))
        else:
            try:
                ET.parse(entity_server)
                sync_diffs = _scalar_sync_differences(client_path, entity_server)
                if sync_diffs:
                    findings.append(_diagnostic_finding(
                        "server", "warn", f"{folder} {entity_id} 客户端/服务端字段不同步",
                        f"{len(sync_diffs)} 项：{', '.join(sync_diffs[:8])}",
                        "核对差异是否是有意的客户端安全投影；动作选择和必读属性不能意外分叉。",
                        confidence="medium", map_path=spawns[0], entity_kind=entity_kind, entity_id=entity_id,
                    ))
            except Exception as exc:
                findings.append(_diagnostic_finding(
                    "server", "crash", f"{folder} {entity_id} 服务端 XML 无法解析", str(exc),
                    "修复该实体 XML。", map_path=spawns[0], entity_kind=entity_kind, entity_id=entity_id,
                ))

        if kind == "m":
            checked += 1
            for item in map_compat.post_analyze(_normalized_nodes(client_path), "boss"):
                verdict = item["verdict"]
                if verdict.status == "ok":
                    continue
                is_mob_type = item["path"] == "info/mobType" and item.get("type") == "string"
                severity = "warn" if is_mob_type or verdict.status != "incompatible" else "crash"
                detail = verdict.reason
                action = verdict.suggestion or "与已验证可工作的旧端怪物对照。"
                confidence = "medium" if is_mob_type else ("high" if severity == "crash" else "low")
                if is_mob_type:
                    detail += " 当前仓库还有 160 个服务端 Mob XML 使用字符串 1N，单凭该字段不能证明必崩。"
                    action = "优先做无怪物地图 A/B；若确认由该怪物触发，再与同类可工作的旧端怪物比较 mobType 和动作树。"
                    if phase == "map_load":
                        confidence = "low"
                        detail += " 当前选择的是进图瞬间且尚未看到怪物，与攻击/死亡动作字段弱相关，因此不计入主要评分。"
                findings.append(_diagnostic_finding(
                    "entity", severity, f"怪物 {entity_id} / {item['path'] or '/'}", detail, action,
                    confidence=confidence, map_path=spawns[0], entity_kind="mob", entity_id=entity_id,
                ))

    scores = {"map": 0, "entity": 0, "server": 0, "resource": 0}
    if case_control["enabled"]:
        for counterexample in case_control["counterexamples"]:
            field_name = counterexample["title"].split(" = ", 1)[0].rsplit("/", 1)[-1]
            for finding in findings:
                if not finding["mapPath"].endswith(f"/{field_name}"):
                    continue
                controls = counterexample["controlMaps"]
                finding["detail"] += (
                    f" 病例对照中另有 {len(controls)} 张可工作地图包含相同字段和值，"
                    "因此它不是这两张崩溃图的独占原因。"
                )
                finding["action"] = "已有可工作反例，不要据此删除节点；等待运行时日志定位实际加载文件或异常地址。"
                finding["evidence"].append(f"可工作反例：{', '.join(controls)}")
    for finding in findings:
        if finding["severity"] == "crash":
            weight = 5
        else:
            weight = {"high": 3, "medium": 2, "low": 0}.get(finding["confidence"], 0)
        scores[finding["domain"]] += weight
    map_side = scores["map"] + scores["resource"]
    entity_side = scores["entity"]
    if entity_side > map_side and entity_side:
        conclusion = "更偏向怪物/NPC 资源问题"
        confidence = "高" if any(item["domain"] == "entity" and item["severity"] == "crash" for item in findings) else "中"
    elif map_side > entity_side and map_side:
        conclusion = "更偏向地图结构或场景资源问题"
        confidence = "高" if any(item["domain"] in {"map", "resource"} and item["severity"] == "crash" for item in findings) else "中"
    elif map_side or entity_side:
        conclusion, confidence = "地图与生命资源都有嫌疑，需要 A/B 隔离", "中"
    else:
        conclusion, confidence = "离线检查未发现明确崩溃点", "低"

    findings.sort(key=lambda item: (
        {"crash": 0, "warn": 1}[item["severity"]],
        {"high": 0, "medium": 1, "low": 2}.get(item["confidence"], 3),
        item["domain"], item["title"],
    ))
    crash_count = sum(item["severity"] == "crash" for item in findings)
    warn_count = sum(item["severity"] == "warn" for item in findings)
    entity_ids = [item["id"] for item in entity_summaries if item["kind"] == "mob"]
    isolation = []
    if scene_resources["suspects"]:
        for item in scene_resources["suspects"][:3]:
            nodes = "、".join(item["mapPaths"])
            isolation.append(
                f"场景 A/B：在测试副本中只同步移除 {nodes}（{item['name']}/{item['canvasPath']}），重进 {map_id}。"
            )
    if phase != "map_load" or not isolation:
        isolation.append(
            f"生命 A/B：在测试副本中同步移除 life，重进 {map_id}。若不再崩溃，嫌疑收敛到 "
            f"{'、'.join(entity_ids) if entity_ids else '生命资源'}。"
        )
    isolation.extend([
        "若上述单节点候选均不能复现差异，再保留 portal/foothold/miniMap，按 back、0-7 层 obj/tile 分组二分；不要一次删除多个类别。",
        f"按当前记录的崩溃阶段“{_CRASH_PHASES[phase]}”复测，并保持每轮只改变一个地图节点或一种生命资源。",
    ])
    if case_control["enabled"]:
        isolation = [
            f"分别进入 {'、'.join(case_control['caseMaps'])}，让直接崩溃生成 diagnostics/session-*.log 和 .dmp；若卡死，按住 Ctrl+F12 约 2 秒后等待 5 秒。",
            "运行 tool/client-debug/wz_file_logger/analyze_client_diagnostics.py，把最后成功读取的 WZ/IMG 路径、异常线程和地址与两次会话交叉核对。",
            "只有运行日志指向具体节点或资源后，才做单记录 A/B；当前两个静态独占特征没有旧端崩溃证据。",
        ]
    return {
        "mapId": map_id, "phase": phase, "phaseLabel": _CRASH_PHASES[phase],
        "conclusion": conclusion, "confidence": confidence, "scores": scores,
        "counts": {"checked": checked, "crash": crash_count, "warn": warn_count, "verified": len(verified)},
        "findings": findings[:80], "verified": verified[:24], "entities": entity_summaries,
        "sceneResources": scene_resources, "caseControl": case_control, "isolation": isolation,
        "note": "离线诊断能证明文件结构、引用和像素是否有效，但不能替代旧客户端实际加载时序。",
    }


@dataclass
class XmlSpan:
    path: str
    tag: str
    attrs: dict[str, str]
    start: int
    open_end: int
    end: int = -1
    self_closing: bool = False


def scan_tag_end(data: bytes, start: int) -> int:
    quote = 0
    for index in range(start, len(data)):
        byte = data[index]
        if quote:
            if byte == quote:
                quote = 0
        elif byte in (ord('"'), ord("'")):
            quote = byte
        elif byte == ord(">"):
            return index + 1
    raise ValueError("XML 标签未闭合")


def index_xml(data: bytes) -> dict[str, XmlSpan]:
    spans: dict[str, XmlSpan] = {}
    stack: list[XmlSpan] = []
    parser = xml.parsers.expat.ParserCreate()

    def on_start(tag: str, attrs: dict[str, str]) -> None:
        name = attrs.get("name", tag)
        parent_path = stack[-1].path if stack else ""
        path = f"{parent_path}/{name}".strip("/") if stack else ""
        start = parser.CurrentByteIndex
        open_end = scan_tag_end(data, start)
        self_closing = data[start:open_end].rstrip().endswith(b"/>")
        span = XmlSpan(path, tag, dict(attrs), start, open_end, self_closing=self_closing)
        spans[path] = span
        stack.append(span)

    def on_end(_tag: str) -> None:
        span = stack.pop()
        if span.self_closing:
            span.end = span.open_end
        else:
            span.end = scan_tag_end(data, parser.CurrentByteIndex)

    parser.StartElementHandler = on_start
    parser.EndElementHandler = on_end
    parser.Parse(data, True)
    return spans


def replace_attribute(tag_bytes: bytes, name: str, value: str) -> bytes:
    encoded = html.escape(value, quote=True)
    pattern = re.compile(rb"(\s" + re.escape(name.encode()) + rb"\s*=\s*)([\"'])(.*?)(\2)", re.S)
    match = pattern.search(tag_bytes)
    if match:
        return tag_bytes[:match.start(3)] + encoded.encode("utf-8") + tag_bytes[match.end(3):]
    insert_at = len(tag_bytes.rstrip()) - (2 if tag_bytes.rstrip().endswith(b"/>") else 1)
    return tag_bytes[:insert_at] + f' {name}="{encoded}"'.encode() + tag_bytes[insert_at:]


def atomic_write(path: Path, data: bytes, *, backup: bool = True) -> None:
    if backup:
        backup_dir = _ROOT / ".workbuddy" / "map-mob-workbench-backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / (relative_path(path).replace("/", "__") + ".bak")
        if not backup_path.exists():
            shutil.copy2(path, backup_path)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def encode_img_scalar(image: WzImage, node: WzProperty, value: Any) -> list[tuple[int, bytes, Any]]:
    if isinstance(node, WzVectorProperty):
        if not isinstance(value, dict):
            raise ValueError("vector 值必须包含 x 和 y")
        result = []
        for axis in ("x", "y"):
            normalized = int(value.get(axis, getattr(node, axis)))
            encoded = wz_writer.encode_compressed_int(normalized)
            offset = getattr(node, f"_{axis}_offset")
            length = getattr(node, f"_{axis}_length")
            if offset is None or len(encoded) != length:
                raise ValueError(f"{axis} 编码长度会从 {length} 变为 {len(encoded)}，拒绝原位写入")
            result.append((int(offset), encoded, normalized))
        return result
    if isinstance(node, WzShortProperty):
        normalized, encoded = int(value), wz_writer.encode_short(int(value))
    elif isinstance(node, WzIntProperty):
        normalized, encoded = int(value), wz_writer.encode_compressed_int(int(value))
    elif isinstance(node, WzLongProperty):
        normalized, encoded = int(value), wz_writer.encode_compressed_long(int(value))
    elif isinstance(node, WzFloatProperty):
        normalized, encoded = float(value), wz_writer.encode_float(float(value))
    elif isinstance(node, WzDoubleProperty):
        normalized, encoded = float(value), wz_writer.encode_double(float(value))
    elif isinstance(node, WzStringProperty):
        normalized = str(value)
        if node._payload_offset is None or node._payload_length is None or node._encoding is None:
            raise ValueError("字符串没有可安全写入的原始 payload 位置")
        encoded = wz_writer.re_encrypt_string(image.wz_file.reader, normalized, node._encoding)
        if len(encoded) != node._payload_length:
            raise ValueError(f"字符串编码长度必须保持 {node._payload_length} 字节，当前为 {len(encoded)}")
        return [(int(node._payload_offset), encoded, normalized)]
    else:
        raise ValueError(f"{node.type_name} 不能安全原位编辑")
    offset = getattr(node, "_value_offset", None)
    length = getattr(node, "_value_length", None)
    if offset is None or len(encoded) != length:
        raise ValueError(f"编码长度会从 {length} 变为 {len(encoded)}，拒绝原位写入")
    return [(int(offset), encoded, normalized)]


def _skip_raw_property_body(reader: Any, tag: int) -> None:
    if tag == 0:
        return
    if tag in (2, 11):
        reader.skip(2)
        return
    if tag in (3, 19):
        reader.read_compressed_int()
        return
    if tag == 20:
        reader.read_compressed_long()
        return
    if tag == 4:
        if reader.read_byte() == 0x80:
            reader.skip(4)
        return
    if tag == 5:
        reader.skip(8)
        return
    if tag == 8:
        reader.read_string_block(0)
        return
    if tag == 9:
        block_size = reader.read_u32()
        reader.seek(reader.position + block_size)
        return
    raise ValueError(f"不支持的 IMG 属性标签: {tag}")


def locate_img_records(
    image: WzImage, data: bytes, parent_path: tuple[str, ...],
) -> tuple[tuple[int, ...], int, int, tuple[str, ...], tuple[tuple[int, int], ...], int]:
    reader = image.wz_file.reader
    reader.seek(0)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise ValueError("只支持独立 Property IMG")
    reader.skip(2)

    def read_list(size_offsets: tuple[int, ...], block_end: int):
        count_offset = reader.position
        count = reader.read_compressed_int()
        count_end = reader.position
        names: list[str] = []
        spans: list[tuple[int, int]] = []
        for _ in range(count):
            start = reader.position
            names.append(reader.read_string_block(0))
            _skip_raw_property_body(reader, reader.read_byte())
            spans.append((start, reader.position))
        if reader.position != block_end:
            raise ValueError("属性记录没有填满父节点块")
        return size_offsets, count_offset, count_end, tuple(names), tuple(spans), block_end

    if not parent_path:
        return read_list((), len(data))

    def descend(segments: tuple[str, ...], block_end: int, size_offsets: tuple[int, ...]):
        count = reader.read_compressed_int()
        for _ in range(count):
            name = reader.read_string_block(0)
            tag = reader.read_byte()
            if tag != 9:
                _skip_raw_property_body(reader, tag)
                continue
            size_offset = reader.position
            block_size = reader.read_u32()
            child_start = reader.position
            child_end = child_start + block_size
            if name != segments[0]:
                reader.seek(child_end)
                continue
            reader.seek(child_start)
            if reader.read_string_block(0) != "Property":
                raise ValueError(f"父节点 {'/'.join(parent_path)} 不是 imgdir Property")
            reader.skip(2)
            next_offsets = (*size_offsets, size_offset)
            if len(segments) == 1:
                return read_list(next_offsets, child_end)
            return descend(segments[1:], child_end, next_offsets)
        reader.seek(block_end)
        raise ValueError(f"父节点不存在: {'/'.join(parent_path)}")

    return descend(parent_path, len(data), ())


def build_img_node(name: str, node_type: str, value: Any) -> WzProperty:
    if not name or "/" in name or "\\" in name:
        raise ValueError("节点名不能为空且不能包含路径分隔符")
    scalar_types = {
        "short": (WzShortProperty, int), "int": (WzIntProperty, int),
        "long": (WzLongProperty, int), "float": (WzFloatProperty, float),
        "double": (WzDoubleProperty, float), "string": (WzStringProperty, str),
        "uol": (WzUolProperty, str),
    }
    if node_type == "imgdir":
        return WzSubProperty(name)
    if node_type == "null":
        return WzNullProperty(name)
    if node_type == "vector":
        vector = value if isinstance(value, dict) else {}
        return WzVectorProperty(name, int(vector.get("x", 0)), int(vector.get("y", 0)))
    if node_type not in scalar_types:
        raise ValueError(f"二进制 IMG 不支持添加 {node_type} 节点")
    node_class, converter = scalar_types[node_type]
    return node_class(name, converter(value))


def encode_img_record(node: WzProperty, image: WzImage) -> bytes:
    encoded = wz_writer._encode_property_list((node,), image.wz_file.reader)
    prefix = wz_writer.encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise ValueError("新增节点记录编码异常")
    return encoded[len(prefix):]


def _verified_img_from_bytes(path: Path, data: bytes) -> WzImage:
    image = WzImage.from_bytes(data, key=key_for_data(data), name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise ValueError(f"增量结果解析失败: {image.parse_warnings}")
    return image


def patch_img_add(
    path: Path, parent_path: str, name: str, node_type: str, value: Any, *, dry_run: bool, backup: bool,
    node: WzProperty | None = None,
) -> dict[str, Any]:
    original = path.read_bytes()
    image = _verified_img_from_bytes(path, original)
    parent_parts = tuple(part for part in parent_path.split("/") if part)
    size_offsets, count_offset, count_end, names, spans, records_end = locate_img_records(image, original, parent_parts)
    if len(set(names)) != len(names):
        raise ValueError("父节点存在重名子节点，拒绝自动增删")
    if name in names:
        raise ValueError(f"同名节点已存在: {parent_path}/{name}".strip("/"))
    raw_before = {item: original[start:end] for item, (start, end) in zip(names, spans)}
    record = encode_img_record(node if node is not None else build_img_node(name, node_type, value), image)
    new_count = wz_writer.encode_compressed_int(len(names) + 1)
    if len(new_count) != count_end - count_offset:
        raise ValueError("子节点计数编码长度变化，拒绝增量插入")
    updated = bytearray(original[:records_end] + record + original[records_end:])
    updated[count_offset:count_end] = new_count
    for size_offset in size_offsets:
        struct.pack_into("<I", updated, size_offset, struct.unpack_from("<I", original, size_offset)[0] + len(record))
    output = bytes(updated)
    verified = _verified_img_from_bytes(path, output)
    _, _, _, new_names, new_spans, _ = locate_img_records(verified, output, parent_parts)
    raw_after = {item: output[start:end] for item, (start, end) in zip(new_names, new_spans)}
    if new_names != (*names, name) or raw_after.get(name) != record:
        raise ValueError("新增记录顺序或内容验证失败")
    if any(raw_after.get(item) != raw for item, raw in raw_before.items()):
        raise ValueError("检测到未修改的兄弟记录发生变化")
    if not dry_run:
        atomic_write(path, output, backup=backup)
        _load_image_cached.cache_clear()
    return {"path": f"{parent_path}/{name}".strip("/"), "insertedBytes": len(record)}


def patch_img_delete(path: Path, node_path: str, *, dry_run: bool, backup: bool) -> dict[str, Any]:
    if not node_path:
        raise ValueError("不能删除 IMG 根节点")
    parent_text, _, child_name = node_path.rpartition("/")
    parent_parts = tuple(part for part in parent_text.split("/") if part)
    original = path.read_bytes()
    image = _verified_img_from_bytes(path, original)
    size_offsets, count_offset, count_end, names, spans, _ = locate_img_records(image, original, parent_parts)
    if len(set(names)) != len(names):
        raise ValueError("父节点存在重名子节点，拒绝自动增删")
    if child_name not in names:
        raise ValueError(f"节点不存在: {node_path}")
    index = names.index(child_name)
    start, end = spans[index]
    raw_before = {
        item: original[record_start:record_end]
        for item, (record_start, record_end) in zip(names, spans) if item != child_name
    }
    new_count = wz_writer.encode_compressed_int(len(names) - 1)
    if len(new_count) != count_end - count_offset:
        raise ValueError("子节点计数编码长度变化，拒绝增量删除")
    updated = bytearray(original[:start] + original[end:])
    updated[count_offset:count_end] = new_count
    removed_bytes = end - start
    for size_offset in size_offsets:
        struct.pack_into("<I", updated, size_offset, struct.unpack_from("<I", original, size_offset)[0] - removed_bytes)
    output = bytes(updated)
    verified = _verified_img_from_bytes(path, output)
    _, _, _, new_names, new_spans, _ = locate_img_records(verified, output, parent_parts)
    raw_after = {item: output[record_start:record_end] for item, (record_start, record_end) in zip(new_names, new_spans)}
    if new_names != tuple(item for item in names if item != child_name):
        raise ValueError("删除后兄弟节点顺序发生变化")
    if any(raw_after.get(item) != raw for item, raw in raw_before.items()):
        raise ValueError("检测到未修改的兄弟记录发生变化")
    if not dry_run:
        atomic_write(path, output, backup=backup)
        _load_image_cached.cache_clear()
    return {"path": node_path, "removedBytes": removed_bytes}


def replace_img_scalar_record(
    path: Path, node_path: str, value: Any, *, dry_run: bool, backup: bool,
) -> dict[str, Any]:
    if not node_path:
        raise ValueError("不能替换 IMG 根节点")
    parent_text, _, child_name = node_path.rpartition("/")
    parent_parts = tuple(part for part in parent_text.split("/") if part)
    original = path.read_bytes()
    image = _verified_img_from_bytes(path, original)
    source = image.root.get(node_path)
    if source is None:
        raise ValueError(f"节点不存在: {node_path}")
    node_type = source.type_name.lower()
    if node_type not in {"short", "int", "long", "float", "double", "string", "uol", "vector"}:
        raise ValueError(f"{source.type_name} 不能安全替换属性记录")

    size_offsets, _, _, names, spans, _ = locate_img_records(image, original, parent_parts)
    if len(set(names)) != len(names):
        raise ValueError("父节点存在重名子节点，拒绝替换属性记录")
    if child_name not in names:
        raise ValueError(f"节点不存在: {node_path}")
    index = names.index(child_name)
    start, end = spans[index]
    raw_before = {
        item: original[record_start:record_end]
        for item, (record_start, record_end) in zip(names, spans) if item != child_name
    }
    replacement_node = build_img_node(child_name, node_type, value)
    replacement = encode_img_record(replacement_node, image)
    delta = len(replacement) - (end - start)
    updated = bytearray(original[:start] + replacement + original[end:])
    for size_offset in size_offsets:
        old_size = struct.unpack_from("<I", original, size_offset)[0]
        if old_size + delta < 0:
            raise ValueError("父节点块长度无效")
        struct.pack_into("<I", updated, size_offset, old_size + delta)
    output = bytes(updated)

    verified = _verified_img_from_bytes(path, output)
    verified_node = verified.root.get(node_path)
    if verified_node is None:
        raise ValueError("替换后验证失败：目标节点丢失")
    _, _, _, new_names, new_spans, _ = locate_img_records(verified, output, parent_parts)
    raw_after = {
        item: output[record_start:record_end]
        for item, (record_start, record_end) in zip(new_names, new_spans)
    }
    if new_names != names:
        raise ValueError("替换后兄弟节点顺序发生变化")
    if any(raw_after.get(item) != raw for item, raw in raw_before.items()):
        raise ValueError("检测到未修改的兄弟记录发生变化")
    if not dry_run and output != original:
        atomic_write(path, output, backup=backup)
        _load_image_cached.cache_clear()
    return {
        "mode": "record-replacement", "path": node_path,
        "oldRecordBytes": end - start, "newRecordBytes": len(replacement), "sizeDelta": delta,
    }


def patch_img(path: Path, node_path: str, value: Any, *, dry_run: bool, backup: bool) -> dict[str, Any]:
    image = load_image(path)
    node = image.root.get(node_path)
    if node is None:
        raise ValueError(f"节点不存在: {node_path}")
    try:
        patches = encode_img_scalar(image, node, value)
    except ValueError as exc:
        if "长度" not in str(exc):
            raise
        return replace_img_scalar_record(
            path, node_path, value, dry_run=dry_run, backup=backup,
        )
    original = path.read_bytes()
    output = bytearray(original)
    for offset, encoded, _ in patches:
        output[offset:offset + len(encoded)] = encoded
    changed_offsets = [index for index, (old, new) in enumerate(zip(original, output)) if old != new]
    allowed = {index for offset, encoded, _ in patches for index in range(offset, offset + len(encoded))}
    if any(index not in allowed for index in changed_offsets):
        raise ValueError("安全检查失败：检测到目标槽位外的字节变化")
    if not dry_run and output != original:
        atomic_write(path, bytes(output), backup=backup)
        _load_image_cached.cache_clear()
        verify = load_image(path)
        if verify.root.get(node_path) is None:
            raise ValueError("写入后验证失败：目标节点丢失")
    return {"changedBytes": len(changed_offsets), "slots": [{"offset": offset, "length": len(data)} for offset, data, _ in patches]}


def patch_xml_value(path: Path, node_path: str, value: Any, *, dry_run: bool, backup: bool) -> dict[str, Any]:
    data = path.read_bytes()
    spans = index_xml(data)
    span = spans.get(node_path)
    if span is None:
        raise ValueError(f"节点不存在: {node_path}")
    attrs: dict[str, str]
    if span.tag == "vector":
        if not isinstance(value, dict):
            raise ValueError("vector 值必须包含 x 和 y")
        attrs = {"x": str(int(value.get("x", span.attrs.get("x", 0)))), "y": str(int(value.get("y", span.attrs.get("y", 0))))}
    elif span.tag == "canvas" and isinstance(value, dict):
        attrs = {key: str(value[key]) for key in ("width", "height", "format") if key in value}
    elif span.tag in _SCALAR_TYPES:
        attrs = {"value": str(value)}
    else:
        raise ValueError(f"{span.tag} 没有可编辑值")
    new_tag = data[span.start:span.open_end]
    for key, attr_value in attrs.items():
        new_tag = replace_attribute(new_tag, key, attr_value)
    output = data[:span.start] + new_tag + data[span.open_end:]
    ET.fromstring(output)
    if not dry_run and output != data:
        atomic_write(path, output, backup=backup)
    return {"changedBytes": sum(a != b for a, b in zip(data, output)) + abs(len(data) - len(output)), "attributes": attrs}


def patch_with_server_sync(
    client_path: Path, node_path: str, value: Any, *, dry_run: bool, backup: bool,
) -> dict[str, Any]:
    server_path = server_xml_for_client(client_path)
    if server_path is None or not server_path.is_file():
        target = relative_path(server_path) if server_path is not None else client_path.name
        raise ValueError(f"找不到对应的服务端 XML: {target}")

    client_preview = patch_img(client_path, node_path, value, dry_run=True, backup=False)
    server_preview = patch_xml_value(server_path, node_path, value, dry_run=True, backup=False)
    if dry_run:
        return {
            "clientPath": relative_path(client_path), "serverPath": relative_path(server_path),
            "client": client_preview, "server": server_preview,
        }

    client_original = client_path.read_bytes()
    server_original = server_path.read_bytes()
    try:
        client_result = patch_img(client_path, node_path, value, dry_run=False, backup=backup)
        server_result = patch_xml_value(server_path, node_path, value, dry_run=False, backup=backup)
    except Exception:
        atomic_write(client_path, client_original, backup=False)
        atomic_write(server_path, server_original, backup=False)
        _load_image_cached.cache_clear()
        raise
    return {
        "clientPath": relative_path(client_path), "serverPath": relative_path(server_path),
        "client": client_result, "server": server_result,
    }


def xml_add_node(path: Path, parent_path: str, name: str, node_type: str, value: Any, *, dry_run: bool, backup: bool) -> dict[str, Any]:
    if not name or "/" in name or "\\" in name:
        raise ValueError("节点名不能为空且不能包含路径分隔符")
    if node_type not in {"imgdir", "int", "short", "long", "float", "double", "string", "vector", "uol", "null"}:
        raise ValueError("不支持的节点类型")
    data = path.read_bytes()
    spans = index_xml(data)
    parent = spans.get(parent_path)
    if parent is None or parent.tag not in {"imgdir", "canvas"} or parent.self_closing:
        raise ValueError("父节点必须是非自闭合 imgdir 或 canvas")
    target_path = f"{parent_path}/{name}".strip("/")
    if target_path in spans:
        raise ValueError(f"同名节点已存在: {target_path}")
    line_start = data.rfind(b"\n", 0, parent.start) + 1
    parent_indent = data[line_start:parent.start]
    indent = parent_indent + b"  "
    escaped_name = html.escape(name, quote=True)
    if node_type == "imgdir":
        snippet = f'<imgdir name="{escaped_name}"></imgdir>'
    elif node_type == "vector":
        vector = value if isinstance(value, dict) else {}
        snippet = f'<vector name="{escaped_name}" x="{int(vector.get("x", 0))}" y="{int(vector.get("y", 0))}"/>'
    elif node_type == "null":
        snippet = f'<null name="{escaped_name}"/>'
    else:
        escaped_value = html.escape(str(value if value is not None else ""), quote=True)
        snippet = f'<{node_type} name="{escaped_name}" value="{escaped_value}"/>'
    close_start = data.rfind(b"</", parent.open_end, parent.end)
    if close_start < 0:
        raise ValueError("无法定位父节点结束标签")
    close_line_start = data.rfind(b"\n", parent.open_end, close_start) + 1
    if data[close_line_start:close_start].strip():
        close_line_start = close_start
        insertion = b"\n" + indent + snippet.encode("utf-8") + b"\n" + parent_indent
    else:
        insertion = indent + snippet.encode("utf-8") + b"\n"
    output = data[:close_line_start] + insertion + data[close_line_start:]
    ET.fromstring(output)
    if not dry_run:
        atomic_write(path, output, backup=backup)
    return {"path": target_path, "insertedBytes": len(insertion)}


def xml_delete_node(path: Path, node_path: str, *, dry_run: bool, backup: bool) -> dict[str, Any]:
    if not node_path:
        raise ValueError("不能删除根节点")
    data = path.read_bytes()
    span = index_xml(data).get(node_path)
    if span is None:
        raise ValueError(f"节点不存在: {node_path}")
    start = span.start
    line_start = data.rfind(b"\n", 0, start) + 1
    if data[line_start:start].strip() == b"":
        start = line_start
    end = span.end
    if end < len(data) and data[end:end + 1] == b"\n":
        end += 1
    output = data[:start] + data[end:]
    ET.fromstring(output)
    if not dry_run:
        atomic_write(path, output, backup=backup)
    return {"path": node_path, "removedBytes": end - start}


def add_with_server_sync(
    client_path: Path, parent_path: str, name: str, node_type: str, value: Any, *, dry_run: bool, backup: bool,
) -> dict[str, Any]:
    server_path = server_xml_for_client(client_path)
    if server_path is None or not server_path.is_file():
        target = relative_path(server_path) if server_path is not None else client_path.name
        raise ValueError(f"找不到对应的服务端 XML: {target}")

    client_preview = patch_img_add(
        client_path, parent_path, name, node_type, value, dry_run=True, backup=False,
    )
    server_preview = xml_add_node(
        server_path, parent_path, name, node_type, value, dry_run=True, backup=False,
    )
    if dry_run:
        return {
            "clientPath": relative_path(client_path), "serverPath": relative_path(server_path),
            "client": client_preview, "server": server_preview,
        }

    client_original = client_path.read_bytes()
    server_original = server_path.read_bytes()
    try:
        client_result = patch_img_add(
            client_path, parent_path, name, node_type, value, dry_run=False, backup=backup,
        )
        server_result = xml_add_node(
            server_path, parent_path, name, node_type, value, dry_run=False, backup=backup,
        )
    except Exception:
        atomic_write(client_path, client_original, backup=False)
        atomic_write(server_path, server_original, backup=False)
        _load_image_cached.cache_clear()
        raise
    return {
        "clientPath": relative_path(client_path), "serverPath": relative_path(server_path),
        "client": client_result, "server": server_result,
    }


def delete_with_server_sync(
    client_path: Path, node_path: str, *, dry_run: bool, backup: bool,
) -> dict[str, Any]:
    server_path = server_xml_for_client(client_path)
    if server_path is None or not server_path.is_file():
        target = relative_path(server_path) if server_path is not None else client_path.name
        raise ValueError(f"找不到对应的服务端 XML: {target}")

    client_preview = patch_img_delete(client_path, node_path, dry_run=True, backup=False)
    server_preview = xml_delete_node(server_path, node_path, dry_run=True, backup=False)
    if dry_run:
        return {
            "clientPath": relative_path(client_path), "serverPath": relative_path(server_path),
            "client": client_preview, "server": server_preview,
        }

    client_original = client_path.read_bytes()
    server_original = server_path.read_bytes()
    try:
        client_result = patch_img_delete(client_path, node_path, dry_run=False, backup=backup)
        server_result = xml_delete_node(server_path, node_path, dry_run=False, backup=backup)
    except Exception:
        atomic_write(client_path, client_original, backup=False)
        atomic_write(server_path, server_original, backup=False)
        _load_image_cached.cache_clear()
        raise
    return {
        "clientPath": relative_path(client_path), "serverPath": relative_path(server_path),
        "client": client_result, "server": server_result,
    }


def empty_gms_img_bytes() -> bytes:
    reader = WzBinaryReader(io.BytesIO(), WzKey.for_region("GMS"))
    return wz_writer.encode_image_type_string(reader, "Property") + b"\x00\x00\x00"


def create_empty_main_files(client_path: Path) -> dict[str, Any]:
    require_repo_write(client_path)
    server_path = server_xml_for_client(client_path)
    if server_path is None:
        raise ValueError("当前路径不是受支持的地图或怪物客户端 IMG")
    if client_path.exists():
        raise ValueError(f"主文件已存在: {relative_path(client_path)}")

    client_data = empty_gms_img_bytes()
    _verified_img_from_bytes(client_path, client_data)
    server_data = f'<imgdir name="{html.escape(client_path.name, quote=True)}">\n</imgdir>\n'.encode("utf-8")
    ET.fromstring(server_data)
    server_original = server_path.read_bytes() if server_path.is_file() else None
    try:
        client_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(client_path, client_data, backup=False)
        if not server_path.exists():
            server_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(server_path, server_data, backup=False)
        _load_image_cached.cache_clear()
        _verified_img_from_bytes(client_path, client_path.read_bytes())
        ET.parse(server_path)
    except Exception:
        if client_path.exists():
            client_path.unlink()
        if server_original is not None:
            atomic_write(server_path, server_original, backup=False)
        elif server_path.exists():
            server_path.unlink()
        _load_image_cached.cache_clear()
        raise
    return {
        "clientPath": relative_path(client_path), "serverPath": relative_path(server_path),
        "createdClient": True, "createdServer": server_original is None,
    }


def clone_supported_node(source: WzProperty) -> WzProperty:
    if isinstance(source, WzCanvasProperty):
        raise ValueError(f"节点 {property_path(source)} 包含 Canvas，不能直接复制到旧端")
    if isinstance(source, WzSubProperty):
        clone = WzSubProperty(source.name)
        for child in source.children():
            clone.add(clone_supported_node(child))
        return clone
    if isinstance(source, WzVectorProperty):
        return WzVectorProperty(source.name, int(source.x), int(source.y))
    if isinstance(source, WzUolProperty):
        return WzUolProperty(source.name, str(source.value))
    if isinstance(source, WzNullProperty):
        return WzNullProperty(source.name)
    scalar_classes = (
        WzShortProperty, WzIntProperty, WzLongProperty, WzFloatProperty,
        WzDoubleProperty, WzStringProperty,
    )
    if isinstance(source, scalar_classes):
        return type(source)(source.name, source.value)
    raise ValueError(f"节点 {property_path(source)} 的类型 {source.type_name} 不支持安全复制")


def clone_compatible_map_node(source: WzProperty, client_path: Path) -> tuple[WzProperty, list[str]]:
    skipped: list[str] = []

    def clone(candidate: WzProperty, *, selected: bool = False) -> WzProperty | None:
        candidate_path = property_path(candidate)
        if (
            isinstance(candidate, WzSubProperty)
            and re.fullmatch(r"[0-7]/obj/[^/]+", candidate_path)
            and is_spine_map_object(candidate)
        ):
            if selected:
                raise ValueError(
                    f"所选节点 {candidate_path} 是现代 Spine/动态对象，必须整条删除后再做旧端静态投影。"
                )
            skipped.append(candidate_path)
            return None
        annotated = annotate_meta(
            candidate_path, property_meta(candidate), "map", infer_id(client_path),
        )
        compatibility = annotated["compatibility"]
        supported = not isinstance(candidate, WzCanvasProperty)
        if compatibility["status"] != "ok" or not supported:
            if selected:
                detail = compatibility["suggestion"] if compatibility["status"] != "ok" else "Canvas 不能直接复制到旧端"
                raise ValueError(
                    f"所选节点 {candidate_path} 标记为“{compatibility['label']}”，不能直接复制。{detail}"
                )
            skipped.append(candidate_path)
            return None
        if not isinstance(candidate, WzSubProperty):
            return clone_supported_node(candidate)
        projected = WzSubProperty(candidate.name)
        for child in candidate.children():
            cloned_child = clone(child)
            if cloned_child is not None:
                projected.add(cloned_child)
        return projected

    projected = clone(source, selected=True)
    if projected is None:
        raise ValueError(f"节点 {property_path(source)} 没有可复制的旧端兼容内容")
    return projected, skipped


def xml_snippet_for_node(node: WzProperty, indent: bytes) -> bytes:
    name = html.escape(node.name, quote=True)
    if isinstance(node, WzCanvasProperty):
        child_indent = indent + b"  "
        children = b"".join(xml_snippet_for_node(child, child_indent) for child in node.children())
        attrs = (
            f'<canvas name="{name}" width="{int(node.width)}" height="{int(node.height)}" '
            f'format="{int(node.format)}">'
        ).encode()
        return indent + attrs + b"\n" + children + indent + b"</canvas>\n"
    if isinstance(node, WzSubProperty):
        child_indent = indent + b"  "
        children = b"".join(xml_snippet_for_node(child, child_indent) for child in node.children())
        return indent + f'<imgdir name="{name}">\n'.encode() + children + indent + b"</imgdir>\n"
    if isinstance(node, WzVectorProperty):
        return indent + f'<vector name="{name}" x="{int(node.x)}" y="{int(node.y)}"/>\n'.encode()
    if isinstance(node, WzNullProperty):
        return indent + f'<null name="{name}"/>\n'.encode()
    tag = {
        WzShortProperty: "short", WzIntProperty: "int", WzLongProperty: "long",
        WzFloatProperty: "float", WzDoubleProperty: "double", WzStringProperty: "string",
        WzUolProperty: "uol",
    }.get(type(node))
    if tag is None:
        raise ValueError(f"节点 {node.name} 不能生成服务端 XML")
    value = html.escape(str(node.value), quote=True)
    return indent + f'<{tag} name="{name}" value="{value}"/>\n'.encode()


def xml_add_cloned_node(
    path: Path, parent_path: str, node: WzProperty, *, dry_run: bool, backup: bool = True,
) -> dict[str, Any]:
    data = path.read_bytes()
    spans = index_xml(data)
    parent = spans.get(parent_path)
    if parent is None or parent.tag != "imgdir":
        raise ValueError(f"服务端父节点不存在或不是 imgdir: {parent_path or '/'}")
    target_path = f"{parent_path}/{node.name}".strip("/")
    if target_path in spans:
        raise ValueError(f"服务端同名节点已存在: {target_path}")
    line_start = data.rfind(b"\n", 0, parent.start) + 1
    line_prefix = data[line_start:parent.start]
    indent_match = re.match(rb"[ \t]*", line_prefix)
    parent_indent = indent_match.group(0) if indent_match else b""
    indent = parent_indent + b"  "
    snippet = xml_snippet_for_node(node, indent)
    if parent.self_closing:
        tag = data[parent.start:parent.open_end]
        trimmed_end = len(tag.rstrip())
        open_tag = tag[:trimmed_end - 2] + b">" + tag[trimmed_end:]
        replacement = open_tag + b"\n" + snippet + parent_indent + b"</imgdir>"
        output = data[:parent.start] + replacement + data[parent.open_end:]
        inserted_bytes = len(replacement) - len(tag)
    else:
        close_start = data.rfind(b"</", parent.open_end, parent.end)
        close_line_start = data.rfind(b"\n", parent.open_end, close_start) + 1
        if close_line_start <= parent.open_end:
            insertion = b"\n" + snippet + parent_indent
            output = data[:close_start] + insertion + data[close_start:]
            inserted_bytes = len(insertion)
        else:
            output = data[:close_line_start] + snippet + data[close_line_start:]
            inserted_bytes = len(snippet)
    ET.fromstring(output)
    if not dry_run:
        atomic_write(path, output, backup=backup)
    return {"path": target_path, "insertedBytes": inserted_bytes}


def xml_replace_cloned_node(
    path: Path, node_path: str, node: WzProperty, *, dry_run: bool, backup: bool = True,
) -> dict[str, Any]:
    data = path.read_bytes()
    target = index_xml(data).get(node_path)
    if target is None:
        raise ValueError(f"服务端节点不存在: {node_path}")
    line_start = data.rfind(b"\n", 0, target.start) + 1
    indent_match = re.match(rb"[ \t]*", data[line_start:target.start])
    indent = indent_match.group(0) if indent_match else b""
    replacement = xml_snippet_for_node(node, indent).rstrip(b"\n")
    output = data[:line_start] + replacement + data[target.end:]
    ET.fromstring(output)
    if not dry_run and output != data:
        atomic_write(path, output, backup=backup)
    return {
        "path": node_path,
        "replacedBytes": target.end - target.start,
        "replacementBytes": len(replacement),
        "changed": output != data,
    }


def selected_map_resource_references(root: WzSubProperty, node_path: str) -> list[dict[str, Any]]:
    selected = node_path.strip("/")
    output = []
    for reference in map_resource_references(root):
        if any(
            not selected
            or path == selected
            or path.startswith(f"{selected}/")
            or selected.startswith(f"{path}/")
            for path in reference["nodes"]
        ):
            output.append(reference)
    return output


def migrate_missing_entity_resources(
    references: list[dict[str, Any]], *, repo_root: Path = _ROOT, tms_data: Path = _TMS_DATA,
) -> dict[str, Any]:
    entities = sorted({
        (reference["kind"], str(reference["name"]))
        for reference in references if reference["kind"] in {"npc", "mob"}
    })
    asset_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for reference in references:
        if reference["kind"] in {"back", "tile", "obj"}:
            asset_groups.setdefault((reference["kind"], str(reference["name"])), []).append(reference)
    if not entities and not asset_groups:
        return {"migrated": [], "unresolved": [], "files": []}

    migrations = []
    unresolved = []
    with tempfile.TemporaryDirectory(prefix=".copy-map-resources-", dir=_HERE) as directory:
        stage_root = Path(directory)
        staged: dict[Path, Path] = {}

        def staged_target(target: Path, *, initial: bytes | None = None) -> Path:
            existing = staged.get(target)
            if existing is not None:
                return existing
            try:
                relative = target.relative_to(repo_root)
            except ValueError as exc:
                raise ValueError(f"资源目标不在项目目录内: {target}") from exc
            output = stage_root / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            if initial is not None:
                output.write_bytes(initial)
            elif target.is_file():
                shutil.copy2(target, output)
            staged[target] = output
            return output

        for kind, entity_id in entities:
            contract = entity_contract_status(
                kind, entity_id, repo_root=repo_root, tms_data=tms_data,
            )
            if contract["status"] == "ready":
                continue
            if contract["status"] == "missingCanvas":
                raise ValueError(
                    f"{kind.upper()} {entity_id} 已有客户端 IMG，但没有可用 Canvas；"
                    "为保护现有二进制记录，不能自动覆盖，请先在资源审计中处理。"
                )
            paths = entity_resource_paths(kind, entity_id, repo_root=repo_root)
            source = tms_entity_source(kind, entity_id, tms_data=tms_data)
            image = None
            materializer = None
            if not paths["client"].is_file():
                if not source.is_file():
                    raise ValueError(f"TMS 缺少 {kind.upper()} {entity_id} 的资源文件: {source}")
                sanitizer = arc.sanitize_npc if kind == "npc" else (
                    lambda root, value=int(entity_id): arc.sanitize_mob(root, value)
                )
                image, materializer = arc.clone_image(source, sanitizer)
                client_data = arc.verified_image_bytes(
                    arc.encode_image_body(image, arc.gms_reader()), f"{entity_id}.img",
                )
                client_stage = staged_target(paths["client"], initial=client_data)
                canvas_audit = _audit_canvas_payloads(client_stage)
                if canvas_audit["errors"] or not canvas_audit["canvases"] or not canvas_audit["visible"]:
                    raise ValueError(
                        f"{kind.upper()} {entity_id} Canvas 兼容校验失败: "
                        f"{canvas_audit['errors'] or '没有可见 Canvas'}"
                    )
            else:
                image = load_image(paths["client"])
                ET.parse(paths["server"]) if paths["server"].is_file() else None

            if not paths["server"].is_file():
                server_data = arc.image_to_xml(image, f"{entity_id}.img").encode("utf-8")
                ET.fromstring(server_data)
                staged_target(paths["server"], initial=server_data)

            source_string_path = tms_data / "String" / f'{paths["title"]}.img'
            source_string = load_image(source_string_path) if source_string_path.is_file() else None
            source_record = source_string.root.get(entity_id) if source_string is not None else None
            string_client = paths["stringClient"]
            string_client_ready = bool(
                string_client.is_file() and load_image(string_client).root.get(entity_id) is not None
            )
            missing_string_servers = [
                target for target in paths["stringServers"] if not xml_has_root_child(target, entity_id)
            ]
            if (not string_client_ready or missing_string_servers) and source_record is None:
                raise ValueError(f"TMS String/{paths['title']}.img 缺少 {entity_id} 记录")
            if not string_client_ready:
                if not string_client.is_file():
                    raise ValueError(f"项目缺少 String 主文件: {string_client}")
                string_stage = staged_target(string_client)
                clone = clone_supported_node(source_record)
                patch_img_add(
                    string_stage, "", entity_id, "imgdir", None,
                    dry_run=False, backup=False, node=clone,
                )
            for string_server in missing_string_servers:
                initial = None
                if not string_server.is_file():
                    initial = f'<imgdir name="{paths["title"]}.img">\n</imgdir>\n'.encode("utf-8")
                server_stage = staged_target(string_server, initial=initial)
                xml_add_cloned_node(
                    server_stage, "", clone_supported_node(source_record),
                    dry_run=False, backup=False,
                )

            migrations.append({
                "kind": kind, "id": entity_id,
                "canvases": materializer.canvases if materializer is not None else 0,
                "links": materializer.links if materializer is not None else 0,
                "resized": materializer.resized if materializer is not None else 0,
            })

        for (kind, name), asset_references in sorted(asset_groups.items()):
            title = {"back": "Back", "tile": "Tile", "obj": "Obj"}[kind]
            source_path = tms_data / "Map" / title / f"{name}.img"
            target_path = repo_root / "clien" / "Data" / "Map" / title / f"{name}.img"
            target_image = load_image(target_path) if target_path.is_file() else None
            missing = [
                reference for reference in asset_references
                if target_image is None or canvas_descriptor(target_path, reference["canvasPath"]) is None
            ]
            if not missing:
                continue
            blocked = [
                reference for reference in missing
                if (
                    not source_path.is_file()
                    or (target_image is not None and target_image.root.get(reference["branch"]) is not None)
                    or (kind == "obj" and name == "connect")
                )
            ]
            if blocked:
                unresolved.append({
                    "kind": kind, "name": name,
                    "branches": sorted({reference["branch"] for reference in blocked}),
                    "reason": (
                        "Obj/connect 使用旧端专用结构，不能用现代 TMS 分支覆盖。"
                        if kind == "obj" and name == "connect"
                        else "TMS 来源缺失，或项目中已有同名分支但 Canvas 不兼容，拒绝自动覆盖。"
                    ),
                })
            migratable = [reference for reference in missing if reference not in blocked]
            if not migratable:
                continue

            source_image = arc.load_image(source_path, arc.BMS_KEY)
            materializer = arc.CanvasMaterializer()
            target_data = target_path.read_bytes() if target_path.is_file() else empty_gms_img_bytes()
            working = WzImage.from_bytes(target_data, key=arc.GMS_KEY, name=target_path.name)
            working.parse()
            added_branches = []
            for reference in migratable:
                branch = reference["branch"]
                if branch in added_branches or working.root.get(branch) is not None:
                    continue
                source_node = source_image.root.get(branch)
                if source_node is None:
                    raise ValueError(f"TMS 资源缺少分支: Map/{title}/{name}.img/{branch}")
                parent_path, _, leaf = branch.rpartition("/")
                clone = arc.clone_property(
                    source_node, None, source_image, source_path, materializer, leaf,
                )
                parent_parts = tuple(part for part in parent_path.split("/") if part)
                target_data = arc.ensure_binary_parent(target_data, parent_parts)
                target_data = arc.append_property_record(target_data, parent_parts, clone)
                working = WzImage.from_bytes(target_data, key=arc.GMS_KEY, name=target_path.name)
                working.parse()
                added_branches.append(branch)
            asset_stage = staged_target(target_path, initial=target_data)
            _verified_img_from_bytes(asset_stage, target_data)
            _load_image_cached.cache_clear()
            missing_after = [
                reference["canvasPath"] for reference in migratable
                if canvas_descriptor(asset_stage, reference["canvasPath"]) is None
            ]
            if missing_after:
                raise ValueError(f"迁移后 Canvas 仍不可解析: Map/{title}/{name}.img {missing_after}")
            migrations.append({
                "kind": kind, "id": name, "branches": added_branches,
                "canvases": materializer.canvases, "links": materializer.links,
                "resized": materializer.resized,
            })

        payloads: dict[Path, bytes] = {}
        for target, stage_path in staged.items():
            data = stage_path.read_bytes()
            if stage_path.name.lower().endswith(".img"):
                _verified_img_from_bytes(stage_path, data)
            else:
                ET.fromstring(data)
            payloads[target] = data

        originals = {target: target.read_bytes() if target.is_file() else None for target in payloads}
        committed: list[Path] = []
        try:
            for target, data in payloads.items():
                target.parent.mkdir(parents=True, exist_ok=True)
                atomic_write(target, data, backup=originals[target] is not None)
                committed.append(target)
        except Exception:
            for target in reversed(committed):
                original = originals[target]
                if original is None:
                    if target.exists():
                        target.unlink()
                else:
                    atomic_write(target, original, backup=False)
            _load_image_cached.cache_clear()
            raise

    _load_image_cached.cache_clear()
    _xml_node_paths_cached.cache_clear()
    return {
        "migrated": migrations, "unresolved": unresolved,
        "files": [relative_path(target) if repo_root == _ROOT else str(target.relative_to(repo_root)) for target in payloads],
    }


_LEGACY_MOB_ACTION = re.compile(
    r"^(?:stand|move|fly|jump|hit|die|attack|skill|regen|chase|rope|ladder|speak)\d*$",
    re.I,
)


# onlyFsm / randDelayAttack are TMS FSM timers and must not be written to GMS.
# onlyFsm bodies are projected to stand UOLs (see ensure_fsm_only_stand_body).
# Old-client area attacks need effectAfter + range start/areaCount/attackCount
# (Zakum 8800000, Cygnus 8850011, Karing 8880301). bulletCount belongs on
# type=2 (Lucid 8880141).
_MOB_ATTACK_INFO_SKIP = frozenset({"onlyFsm", "randDelayAttack"})
_MOB_RANGE_SKIP = frozenset({"reverse"})
_MOB_ROOT_INFO_SKIP = frozenset({
    "forcedSeperateSoul", "activeStopAttackExceptFirstAttackRange", "activeStopAttackExceptMob",
})
_LEGACY_BULLET_SPEED_MIN = 40
_LEGACY_BULLET_SPEED_SAFE = 220
_UNSAFE_MOB_SKILL_IDS = frozenset({170, 215})
# TMS 170/215 cannot enter v83. Do not occupy Lucid 185 / Akayrum 176:
# those applyEffect paths play other bosses' field skills.
# 100/101 are generic ATK buffs; 123/128 are shared diseases, not boss-specific VFX.
_LIFEFACTORY_REQUIRED_INTS = ("level", "PADamage", "PDDamage", "MADamage", "MDDamage")
_LEGACY_INFO_RATE_MAX = 70
_PROJECTED_MOB_SKILL_TABLES = {
    "8880110": (
        {"skill": 100, "level": 1, "action": 1},
        {"skill": 101, "level": 1, "action": 2},
        {"skill": 123, "level": 4, "action": 3},
        {"skill": 128, "level": 6, "action": 4},
    ),
    "8880111": (
        {"skill": 100, "level": 1, "action": 1},
        {"skill": 101, "level": 1, "action": 2},
        {"skill": 123, "level": 4, "action": 3},
        {"skill": 128, "level": 6, "action": 4},
        {"skill": 126, "level": 1, "action": 5},
        {"skill": 120, "level": 4, "action": 6},
        {"skill": 122, "level": 1, "action": 7},
        {"skill": 124, "level": 1, "action": 8},
        {"skill": 125, "level": 1, "action": 9},
        {"skill": 133, "level": 1, "action": 10},
    ),
}
_LEGACY_MOB_CANVAS_CHILDREN = ("origin", "delay", "z", "head", "lt", "rb")
_POSE_CANVAS_CHILDREN = frozenset({"origin", "head", "lt", "rb", "z"})
_DEFAULT_FRAME_DELAY = 90
# Signed 32-bit max. TMS often writes info/maxHP as "??????"; old client needs an int.
_CLIENT_MAXHP_INT = 2_147_483_647


def _positive_int(value: object) -> int | None:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _legacy_client_maxhp(source_value: object, existing: WzProperty | None) -> int:
    """Numeric source HP, else target HP, else signed-int max (21亿)."""
    parsed = _positive_int(source_value)
    if parsed is not None:
        return min(parsed, _CLIENT_MAXHP_INT)
    if isinstance(existing, (WzIntProperty, WzLongProperty, WzShortProperty)):
        inherited = _positive_int(existing.value)
        if inherited is not None:
            return min(inherited, _CLIENT_MAXHP_INT)
    return _CLIENT_MAXHP_INT


def resolve_uol_absolute(from_path: str, target: str) -> str:
    parts = [part for part in from_path.split("/") if part]
    if parts:
        parts.pop()
    for segment in str(target).replace("\\", "/").split("/"):
        if not segment or segment == ".":
            continue
        if segment == "..":
            if parts:
                parts.pop()
            continue
        parts.append(segment)
    return "/".join(parts)


def skip_companion_leaf(path: str) -> bool:
    parts = [part for part in path.split("/") if part]
    name = parts[-1] if parts else ""
    parent_name = parts[-2] if len(parts) > 1 else ""
    if name in {"_inlink", "_outlink"} or name in map_compat.SPINE_NAMES:
        return True
    if name.startswith("directionAct"):
        return True
    if parent_name == "info" and name in _MOB_ATTACK_INFO_SKIP:
        return True
    if parent_name == "range" and name in _MOB_RANGE_SKIP:
        return True
    if _is_mob_root_info_path(parts):
        root_child = parts[1]
        if (
            root_child in map_compat.BOSS_INFO_INCOMPATIBLE
            or root_child in map_compat.BOSS_INFO_MODERN_REVIEW
            or root_child in _MOB_ROOT_INFO_SKIP
        ):
            return True
    return False


def _is_mob_root_info_path(parts: list[str]) -> bool:
    return len(parts) >= 2 and parts[0] == "info"


def _under_action_info(node: WzProperty) -> bool:
    current = node.parent
    while current is not None:
        if re.fullmatch(r"(?:attack|skill)\d+", current.name or "", re.I):
            return True
        current = current.parent
    return False


def find_tms_canvas_store_match(
    source_path: Path, width: int, height: int, frame: str, folder: str,
) -> tuple[WzImage, WzCanvasProperty, Path] | None:
    """Find unique pixels for a logical canvas that the current _Canvas file omitted."""
    if not is_mob_canvas_store(source_path) or width <= 1 or height <= 1:
        return None
    canvas_dir = source_path.parent
    ordered: list[Path] = []
    stem = source_path.stem
    if stem.isdigit():
        for delta in (1, -1, 2, -2, 10, 11):
            neighbor = canvas_dir / f"{int(stem) + delta:07d}.img"
            if neighbor.is_file() and neighbor.resolve() != source_path.resolve():
                ordered.append(neighbor)
    for path in sorted(canvas_dir.glob("*.img")):
        if path.resolve() != source_path.resolve() and path not in ordered:
            ordered.append(path)

    def match_canvas(node: WzProperty, parent_name: str) -> WzCanvasProperty | None:
        if isinstance(node, WzCanvasProperty):
            if (
                node.name == frame
                and int(node.width) == width
                and int(node.height) == height
                and (not folder or parent_name == folder)
                and node.has_pixels()
            ):
                return node
            return None
        if isinstance(node, WzSubProperty):
            for child in node.children():
                found = match_canvas(child, node.name)
                if found is not None:
                    return found
        return None

    for path in ordered:
        image = load_image(path)
        found = match_canvas(image.root, "")
        if found is not None:
            return image, found, path
    return None


def clamp_legacy_bullet_speed(value: int) -> int:
    """Keep old-client ballistic speed in the proven GMS cluster used here.

    Repo Mob XML speeds are 40..600. Damien flying knives already land at 220;
    树妖王 is 140. TMS JSON often writes 300, which is valid on 8641002 but
    faster than this project's Damien analogue.
    """
    if value < _LEGACY_BULLET_SPEED_MIN:
        return 140
    if value > _LEGACY_BULLET_SPEED_SAFE:
        return _LEGACY_BULLET_SPEED_SAFE
    return int(value)


def ensure_ballistic_contract(node: WzProperty) -> None:
    """Project attack/info/ball onto the 8641002 / 树妖王 type=2 analogue."""
    if not isinstance(node, WzSubProperty):
        return
    infos: list[WzSubProperty] = []
    if node.name == "info" and node.child("ball") is not None:
        infos.append(node)
    info = node.child("info")
    if isinstance(info, WzSubProperty) and info.child("ball") is not None:
        infos.append(info)
    for child in node.children():
        nested = child.child("info") if isinstance(child, WzSubProperty) else None
        if isinstance(nested, WzSubProperty) and nested.child("ball") is not None:
            infos.append(nested)
    seen: set[int] = set()
    for info in infos:
        if id(info) in seen:
            continue
        seen.add(id(info))
        if info.child("type") is None:
            info.add(WzIntProperty("type", 2, info))
        speed = info.child("bulletSpeed")
        if speed is None:
            info.add(WzIntProperty("bulletSpeed", _LEGACY_BULLET_SPEED_SAFE, info))
        elif isinstance(speed, (WzIntProperty, WzLongProperty, WzShortProperty)):
            speed._value = clamp_legacy_bullet_speed(int(speed.value))
        hit = info.child("hit")
        if isinstance(hit, WzSubProperty) and hit.child("attach") is None:
            hit.add(WzIntProperty("attach", 1, hit))


def _iter_action_infos(node: WzProperty) -> list[WzSubProperty]:
    infos: list[WzSubProperty] = []
    if node.name == "info" and isinstance(node, WzSubProperty):
        infos.append(node)
    info = node.child("info") if isinstance(node, WzSubProperty) else None
    if isinstance(info, WzSubProperty):
        infos.append(info)
    if isinstance(node, WzSubProperty):
        for child in node.children():
            nested = child.child("info") if isinstance(child, WzSubProperty) else None
            if isinstance(nested, WzSubProperty):
                infos.append(nested)
    seen: set[int] = set()
    unique: list[WzSubProperty] = []
    for info in infos:
        if id(info) in seen:
            continue
        seen.add(id(info))
        unique.append(info)
    return unique


def ensure_area_attack_contract(node: WzProperty) -> None:
    """Zakum/Cygnus/Karing: areaWarning attacks carry type=3 unless already typed."""
    for info in _iter_action_infos(node):
        if info.child("areaWarning") is None:
            continue
        if info.child("type") is None:
            info.add(WzIntProperty("type", 3, info))


def _read_three_field_skill_table(skill: WzSubProperty) -> list[dict[str, int]] | None:
    entries: list[dict[str, int]] = []
    for child in skill.children():
        if not child.name.isdigit():
            return None
        record = {
            item.name: int(item.value)
            for item in child.children()
            if isinstance(item, (WzIntProperty, WzLongProperty, WzShortProperty))
        }
        if set(record) != {"skill", "action", "level"}:
            return None
        if int(record["skill"]) in _UNSAFE_MOB_SKILL_IDS:
            return None
        entries.append(record)
    return entries or None


def _build_skill_table(entries: tuple[dict[str, int], ...] | list[dict[str, int]]) -> WzSubProperty:
    skill = WzSubProperty("skill")
    for index, entry in enumerate(entries):
        record = WzSubProperty(str(index), skill)
        for name in ("skill", "action", "level"):
            record.add(WzIntProperty(name, int(entry[name]), record))
        skill.add(record)
    return skill


def _mob_root_info(node: WzProperty) -> WzSubProperty | None:
    if isinstance(node, WzSubProperty) and node.name == "info" and not _under_action_info(node):
        return node
    if isinstance(node, WzSubProperty):
        candidate = node.child("info")
        if isinstance(candidate, WzSubProperty) and not _under_action_info(candidate):
            return candidate
    return None


def _skill_action_has_frames(image: WzImage | None, action: int) -> bool:
    if image is None:
        return False
    folder = image.root.child(f"skill{int(action)}")
    return isinstance(folder, WzSubProperty) and any(child.name.isdigit() for child in folder.children())


def _projected_skill_entries(dest_mob_id: str, existing_image: WzImage | None) -> list[dict[str, int]] | None:
    projected = _PROJECTED_MOB_SKILL_TABLES.get(dest_mob_id)
    if projected is None:
        return None
    present = [dict(entry) for entry in projected if _skill_action_has_frames(existing_image, entry["action"])]
    return present or [dict(entry) for entry in projected]


def ensure_projected_root_skill_table(
    node: WzProperty,
    *,
    existing_image: WzImage | None = None,
    dest_mob_id: str = "",
) -> None:
    """Damien always uses the proven v83 table. Other mobs reuse A's three-field table."""
    info = _mob_root_info(node)
    if info is None:
        return
    entries = _projected_skill_entries(dest_mob_id, existing_image)
    if entries is None:
        existing = existing_image.root.get("info/skill") if existing_image is not None else None
        if isinstance(existing, WzSubProperty):
            entries = _read_three_field_skill_table(existing)
    skill = info.child("skill")
    if entries is None:
        if isinstance(skill, WzSubProperty) and _read_three_field_skill_table(skill) is None:
            raise ValueError("Mob info/skill 使用旧端未验证的技能；目标没有可沿用的三字段技能表")
        return
    if skill is not None:
        info._children.pop("skill", None)
    info.add(_build_skill_table(entries))


def compact_mob_tree(node: WzProperty) -> int:
    """Densify nested folders (areaWarning). Keep action-root frame indices.

    skill2 UOLs target sibling names such as 23; compacting 10..n down to 0
    would retarget those loops onto the wrong canvases.
    """
    if not isinstance(node, WzSubProperty):
        return 0
    renamed = 0
    if not re.fullmatch(r"(?:attack|skill|skillAfter)\d+", node.name):
        renamed = compact_numeric_children(node)
    for child in list(node.children()):
        renamed += compact_mob_tree(child)
    return renamed


def missing_mob_inserts(
    clone: WzProperty, existing: WzProperty | None, prefix: str,
) -> list[tuple[str, WzProperty]]:
    if existing is None:
        parent = prefix.rpartition("/")[0]
        return [(parent, clone)]
    leaf_types = (WzCanvasProperty, WzUolProperty, WzVideoProperty)
    if isinstance(clone, leaf_types) or isinstance(existing, leaf_types):
        return []
    if not isinstance(clone, WzSubProperty) or not isinstance(existing, WzSubProperty):
        return []
    inserts: list[tuple[str, WzProperty]] = []
    present = {child.name: child for child in existing.children()}
    for child in clone.children():
        child_path = f"{prefix}/{child.name}".strip("/")
        if child.name not in present:
            inserts.append((prefix, child))
        else:
            inserts.extend(missing_mob_inserts(child, present[child.name], child_path))
    return inserts


def _attack_has_usable_payload(action: WzProperty) -> bool:
    """Body frames, or a type=2 ball attack that never had a pose (Damien attack2)."""
    if not isinstance(action, WzSubProperty):
        return False
    if any(child.name.isdigit() for child in action.children()):
        return True
    info = action.child("info")
    if not isinstance(info, WzSubProperty):
        return False
    attack_type = info.child("type")
    typed = (
        isinstance(attack_type, (WzIntProperty, WzLongProperty, WzShortProperty))
        and int(attack_type.value) == 2
    )
    ball = info.child("ball")
    has_ball = isinstance(ball, WzSubProperty) and any(
        child.name.isdigit() or isinstance(child, WzCanvasProperty) for child in ball.children()
    )
    return typed and has_ball


def ensure_legacy_speed_without_move(
    clone: WzProperty, client_image: WzImage | None,
) -> None:
    """TMS Damien uses speed=-60 with no move; the old client crashes on spawn."""
    info = _mob_root_info(clone)
    if info is None:
        return
    has_move = isinstance(clone, WzSubProperty) and clone.child("move") is not None
    if client_image is not None and client_image.root.child("move") is not None:
        has_move = True
    speed = info.child("speed")
    if has_move or not isinstance(speed, (WzIntProperty, WzLongProperty, WzShortProperty)):
        return
    if int(speed.value) != 0:
        speed._value = 0


def ensure_legacy_lifefactory_info(
    clone: WzProperty, client_image: WzImage | None,
) -> None:
    """LifeFactory.getIntConvert(level/PA/PD/MA/MDDamage) has no default; missing → 怪物不存在."""
    info = _mob_root_info(clone)
    if info is None:
        return
    for name in _LIFEFACTORY_REQUIRED_INTS:
        current = info.child(name)
        if isinstance(current, (WzIntProperty, WzLongProperty, WzShortProperty)):
            continue
        existing = client_image.root.get(f"info/{name}") if client_image is not None else None
        value = 1 if name == "level" else 0
        if isinstance(existing, (WzIntProperty, WzLongProperty, WzShortProperty)):
            value = int(existing.value)
        info.add(WzIntProperty(name, value, info))
    for name in ("PDRate", "MDRate"):
        rate = info.child(name)
        if isinstance(rate, (WzIntProperty, WzLongProperty, WzShortProperty)):
            if int(rate.value) > _LEGACY_INFO_RATE_MAX:
                rate._value = 0


def sync_clamped_info_rates(
    client_path: Path, server_path: Path, clone: WzProperty, node_path: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Insert-only copy leaves TMS PDRate=300 on A; clamp dest scalars to the clone."""
    info = _mob_root_info(clone)
    if info is None or node_path not in {"", "info"}:
        return [], []
    dest = _verified_img_from_bytes(client_path, client_path.read_bytes()).root.child("info")
    if not isinstance(dest, WzSubProperty):
        return [], []
    client_result: list[dict[str, Any]] = []
    server_result: list[dict[str, Any]] = []
    for name in ("PDRate", "MDRate"):
        wanted = info.child(name)
        have = dest.child(name)
        if not isinstance(wanted, (WzIntProperty, WzLongProperty, WzShortProperty)):
            continue
        if not isinstance(have, (WzIntProperty, WzLongProperty, WzShortProperty)):
            continue
        if int(have.value) == int(wanted.value):
            continue
        client_result.append(patch_img(
            client_path, f"info/{name}", int(wanted.value), dry_run=False, backup=False,
        ))
        server_result.append(patch_xml_value(
            server_path, f"info/{name}", int(wanted.value), dry_run=False, backup=False,
        ))
    return client_result, server_result


def _skill_table_entries(skill: WzProperty | None) -> list[dict[str, int]] | None:
    if not isinstance(skill, WzSubProperty):
        return None
    return _read_three_field_skill_table(skill)


def replace_existing_mob_skill_table(
    client_path: Path, server_path: Path, clone: WzProperty, node_path: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Insert-only copy cannot overwrite Cygnus/TMS skill IDs; swap info/skill when projection differs."""
    info = _mob_root_info(clone)
    wanted = info.child("skill") if info is not None else None
    wanted_entries = _skill_table_entries(wanted)
    if wanted_entries is None or not isinstance(wanted, WzSubProperty):
        return [], []
    dest_skill_path = "info/skill" if node_path in {"", "info"} else f"{node_path.rstrip('/')}/skill"
    dest_parent = dest_skill_path.rpartition("/")[0]
    dest_image = _verified_img_from_bytes(client_path, client_path.read_bytes())
    existing = dest_image.root.get(dest_skill_path)
    if _skill_table_entries(existing) == wanted_entries:
        return [], []
    client_result: list[dict[str, Any]] = []
    server_result: list[dict[str, Any]] = []
    if existing is not None:
        client_result.append(patch_img_delete(client_path, dest_skill_path, dry_run=False, backup=False))
        server_result.append(xml_delete_node(server_path, dest_skill_path, dry_run=False, backup=False))
    client_result.append(patch_img_add(
        client_path, dest_parent, "skill", "imgdir", None,
        dry_run=False, backup=False, node=wanted,
    ))
    server_result.append(xml_add_cloned_node(
        server_path, dest_parent, wanted, dry_run=False, backup=False,
    ))
    return client_result, server_result


def _legacy_stub_canvas(name: str, parent: WzProperty | None) -> WzCanvasProperty:
    """GMS ARGB4444 1x1 transparent canvas. Zakum/Cygnus areaWarning/0 uses this."""
    pixels = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    canvas = WzCanvasProperty(name, parent)
    canvas.width, canvas.height = 1, 1
    canvas.format, canvas.format2 = 1, 0
    canvas._png_data = encode_canvas_payload(pixels, 1, 1, 1, key=arc.GMS_KEY, listwz=False, zlib_level=9)
    canvas._png_length = len(canvas._png_data)
    canvas.add(WzVectorProperty("origin", 0, 0, canvas))
    canvas.add(WzIntProperty("delay", _DEFAULT_FRAME_DELAY, canvas))
    pixels.close()
    return canvas


def _is_tiny_canvas(node: WzProperty | None) -> bool:
    if not isinstance(node, WzCanvasProperty):
        return False
    return int(node.width) <= _PLACEHOLDER_MAX_SIZE and int(node.height) <= _PLACEHOLDER_MAX_SIZE


def _is_area_warning_frame(path: str, node: WzProperty) -> bool:
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 2 and parts[-2] == "areaWarning":
        return True
    parent = node.parent
    return parent is not None and parent.name == "areaWarning"


def _keep_area_warning_stub(node: WzProperty, lookup_path: str) -> bool:
    """Frame 0 of areaWarning must stay 1x1; do not follow _outlink to a real warning image."""
    if not _is_area_warning_frame(lookup_path or property_path(node) or node.name, node):
        return False
    return node.name == "0"


def _digit_action_frames(action: WzSubProperty) -> list[WzProperty]:
    return [child for child in action.children() if child.name.isdigit()]


def _pose_frame_is_empty_stub(node: WzProperty) -> bool:
    """1x1 with no origin/head/lt is TMS FSM leftover, not a playable old-client pose."""
    if isinstance(node, WzUolProperty):
        return False
    if not isinstance(node, WzCanvasProperty):
        return False
    if not _is_tiny_canvas(node):
        return False
    return not _logical_pose_usable(node)


def _action_has_ball(action: WzSubProperty) -> bool:
    info = action.child("info")
    if not isinstance(info, WzSubProperty):
        return False
    if info.child("ball") is not None:
        return True
    attack_type = info.child("type")
    return (
        isinstance(attack_type, (WzIntProperty, WzLongProperty, WzShortProperty))
        and int(attack_type.value) == 2
    )


def _stand_frame_names(image: WzImage | None) -> list[str]:
    if image is None:
        return []
    stand = image.root.child("stand")
    if not isinstance(stand, WzSubProperty):
        return []
    names = [child.name for child in stand.children() if child.name.isdigit()]
    names.sort(key=lambda name: int(name))
    return names


def _read_only_fsm(
    source: WzProperty | None,
    copied_root: str,
    companion_nodes: dict[str, dict[str, Any]],
) -> bool:
    info = source.child("info") if isinstance(source, WzSubProperty) else None
    if isinstance(info, WzSubProperty):
        value = info.child("onlyFsm")
        if isinstance(value, (WzIntProperty, WzLongProperty, WzShortProperty)) and int(value.value) == 1:
            return True
    prefix = (copied_root or "").strip("/")
    keys = [f"{prefix}/info/onlyFsm"] if prefix else []
    keys.append("info/onlyFsm")
    for key in keys:
        meta = companion_nodes.get(key)
        if not meta:
            continue
        try:
            if int(meta.get("value") or 0) == 1:
                return True
        except (TypeError, ValueError):
            continue
    return False


def ensure_fsm_only_stand_body(
    clone: WzProperty,
    *,
    source: WzProperty,
    client_image: WzImage | None,
    companion_nodes: dict[str, dict[str, Any]],
    copied_root: str,
) -> int:
    """TMS onlyFsm attacks keep a 1x1 empty pose; the old client plays it as the body.

    That flickers the sprite and attaches hit/status VFX at origin=(0,0) (the feet).
    Project onto Damien attack3: UOL every target stand frame. Do not UOL ballistic
    stubs or real pose bodies — UOL attack1 crashes Brandish/Styx ReleaseFlash.
    """
    if not isinstance(clone, WzSubProperty) or not re.fullmatch(r"(?:attack|skill)\d+", clone.name):
        return 0
    if _action_has_ball(clone):
        return 0
    frames = _digit_action_frames(clone)
    empty_pose = (not frames) or all(_pose_frame_is_empty_stub(child) for child in frames)
    if not empty_pose:
        return 0
    only_fsm = _read_only_fsm(source, copied_root, companion_nodes)
    stand_names = _stand_frame_names(client_image)
    if not stand_names:
        if only_fsm or not frames:
            raise ValueError(
                f"{clone.name} 是 TMS onlyFsm/空姿势动作，旧端会把 1×1 origin(0,0) 当身体播放"
                "（闪烁、特效掉到脚下）。请先在目标 IMG 保留 stand 帧，复制时会投影为 ../stand/N UOL"
            )
        return 0
    for child in frames:
        clone._children.pop(child.name, None)
    added = 0
    for name in stand_names:
        if clone.child(name) is not None:
            continue
        clone.add(WzUolProperty(name, f"../stand/{name}", clone))
        added += 1
    return added


def ensure_legacy_attack_body_frame(clone: WzProperty) -> None:
    """Ball-only TMS attacks still need attackN/0; UOL those bodies crash Brandish Flash."""
    if not isinstance(clone, WzSubProperty) or not re.fullmatch(r"attack\d+", clone.name):
        return
    if any(child.name.isdigit() for child in clone.children()):
        return
    clone.add(_legacy_stub_canvas("0", clone))


def ensure_area_warning_leading_stub(node: WzProperty) -> int:
    """Old-client areaWarning walks 0..max; Zakum/Cygnus keep 0 as 1x1 and visuals at 1..n.

    TMS Canvas stores often omit 0 and start at 1. Densify must not promote the first
    real warning frame into slot 0.
    """
    changed = 0
    if isinstance(node, WzSubProperty) and node.name == "areaWarning":
        children = list(node.children())
        numeric = [child for child in children if child.name.isdigit()]
        numeric.sort(key=lambda child: int(child.name))
        others = [child for child in children if not child.name.isdigit()]
        zero = numeric[0] if numeric and numeric[0].name == "0" else None
        if zero is not None and _is_tiny_canvas(zero):
            visuals = numeric[1:]
            stub = zero
        else:
            visuals = numeric
            stub = _legacy_stub_canvas("0", node)
            changed += 1
        renamed = []
        for index, child in enumerate(visuals, start=1):
            if child.name != str(index):
                child.name = str(index)
                changed += 1
            renamed.append(child)
        stub.name = "0"
        stub.parent = node
        node._children = {child.name: child for child in [*others, stub, *renamed]}
        return changed
    if isinstance(node, WzSubProperty):
        for child in list(node.children()):
            changed += ensure_area_warning_leading_stub(child)
    return changed


def validate_copied_mob_info(image: WzImage) -> None:
    """Reject a stale incompatible target after an insert-only root info copy."""
    roots = list(image.root.children())
    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise ValueError("Mob info 未创建")
    if roots[0] is not info:
        raise ValueError("Mob info 不在首节点；现有文件须从旧端兼容基线重建")
    hp = info.child("maxHP")
    if not isinstance(hp, (WzIntProperty, WzLongProperty)) or int(hp.value) <= 0:
        raise ValueError("Mob info/maxHP 仍不是正数整数；现有 info 须从兼容基线重建")
    for name in _LIFEFACTORY_REQUIRED_INTS:
        if not isinstance(info.child(name), (WzIntProperty, WzLongProperty, WzShortProperty)):
            raise ValueError(
                f"Mob info/{name} 缺失；LifeFactory 无默认值会 NPE，客户端显示怪物不存在"
            )
    for name in sorted(map_compat.BOSS_INFO_INCOMPATIBLE | _MOB_ROOT_INFO_SKIP):
        if info.child(name) is not None:
            raise ValueError(f"Mob info/{name} 仍是旧端不兼容节点；须从兼容基线重建")
    mob_type = info.child("mobType")
    if isinstance(mob_type, WzStringProperty) and not re.fullmatch(r"[0-4]N", str(mob_type.value)):
        raise ValueError("Mob info/mobType 仍是未经验证的现代字符串；须从兼容基线重建")
    for action in roots:
        if not re.fullmatch(r"attack\d+", action.name):
            continue
        if not _attack_has_usable_payload(action):
            raise ValueError(f"Mob {action.name} 没有动作帧，不能完成 info 复制")
    skill = info.child("skill")
    if isinstance(skill, WzSubProperty):
        for slot in skill.children():
            target_name = f"skill{int(slot.child('action').value)}" if slot.child("action") is not None else ""
            target = image.root.child(target_name)
            if target is None or not any(frame.name.isdigit() for frame in target.children()):
                raise ValueError(f"Mob info/skill/{slot.name}/action 没有对应动作帧: {target_name}")


_OUTLINK_ACTION_FRAME = re.compile(r"/((?:attack|skill|skillAfter)\d+)/(\d+)$")


def _outlink_frame_uol(path: str, extra: dict[str, dict[str, Any]]) -> str | None:
    """1x1 _outlink → sibling '23' or '../skill3/0'. skill4/0 points at skill3, not skill1."""
    parts = [part for part in path.split("/") if part]
    if len(parts) != 2 or not parts[1].isdigit():
        return None
    if not re.fullmatch(r"(?:attack|skill|skillAfter)\d+", parts[0]):
        return None
    meta = extra.get(path) or {}
    raw = str(meta.get("_outlink") or "")
    if not raw:
        raw = str((extra.get(f"{path}/_outlink") or {}).get("value") or "")
    raw = raw.replace("\\", "/")
    match = _OUTLINK_ACTION_FRAME.search(raw)
    if match is None:
        return None
    action, frame = match.group(1), match.group(2)
    if action == parts[0]:
        if frame == parts[1]:
            return None
        return f"../{action}/{frame}"
    return f"../{action}/{frame}"


def _same_action_outlink_uol(path: str, extra: dict[str, dict[str, Any]]) -> str | None:
    """skill2/72 is a 1x1 whose _outlink points at skill2/23 — old client gets a sibling UOL."""
    value = _outlink_frame_uol(path, extra)
    if value is None or value.startswith("../"):
        return None
    return value


def _uol_target_in_clone(clone: WzProperty, prefix: str, abs_target: str) -> bool:
    if not abs_target or not isinstance(clone, WzSubProperty):
        return False
    prefix = prefix.strip("/")
    if prefix and abs_target == prefix:
        return True
    if prefix and abs_target.startswith(f"{prefix}/"):
        return clone.get(abs_target[len(prefix) + 1:]) is not None
    return clone.get(abs_target) is not None


def action_frame_gaps(action: WzSubProperty) -> list[int]:
    names = sorted(int(child.name) for child in action.children() if child.name.isdigit())
    if not names:
        return []
    present = set(names)
    return [index for index in range(names[-1] + 1) if index not in present]


def validate_action_frame_timeline(clone: WzProperty) -> None:
    """Old client walks 0..max. skill2 must keep TMS indices, not densify from 10."""
    if not isinstance(clone, WzSubProperty) or not re.fullmatch(
        r"(?:attack|skill|skillAfter)\d+", clone.name,
    ):
        return
    gaps = action_frame_gaps(clone)
    if not gaps:
        return
    hint = ""
    if clone.name.startswith("skill"):
        hint = (
            f"；{clone.name} 的缺口应是 TMS 1×1 _outlink 转成的 UOL"
            "（skill2 的 0–9 才是 ../skill1/N；skill4 的 0–1 是 ../skill3/N）"
        )
    preview = ",".join(str(gap) for gap in gaps[:12])
    more = "…" if len(gaps) > 12 else ""
    raise ValueError(
        f"{clone.name} 复制后帧不连续，缺 {preview}{more}。"
        "TMS 从 0 播到最后一帧，不要把缺口压成 0..n-1，也不要用 stand 去填"
        f"{hint}"
    )


def compact_numeric_children(parent: WzSubProperty) -> int:
    """Renumber digit children to 0..n-1 in existing order. Do not invent frames."""
    children = list(parent.children())
    numeric = [child for child in children if child.name.isdigit()]
    if len(numeric) < 2:
        return 0
    numeric.sort(key=lambda child: int(child.name))
    if [int(child.name) for child in numeric] == list(range(len(numeric))):
        return 0
    renamed = 0
    for index, child in enumerate(numeric):
        if child.name != str(index):
            child.name = str(index)
            renamed += 1
    ordered = [child for child in children if not child.name.isdigit()]
    ordered.extend(numeric)
    parent._children = {child.name: child for child in ordered}
    return renamed


def _skip_incompatible_mob_node(node: WzProperty) -> bool:
    name = node.name
    parent_name = node.parent.name if node.parent is not None else ""
    if name in {"_inlink", "_outlink"} or name in map_compat.SPINE_NAMES:
        return True
    if name.startswith("directionAct"):
        return True
    if isinstance(node, WzVideoProperty):
        return True
    if parent_name == "info" and name in _MOB_ATTACK_INFO_SKIP:
        return True
    if parent_name == "range" and name in _MOB_RANGE_SKIP:
        return True
    if parent_name == "info" and not _under_action_info(node):
        if (
            name in map_compat.BOSS_INFO_INCOMPATIBLE
            or name in map_compat.BOSS_INFO_MODERN_REVIEW
            or name in _MOB_ROOT_INFO_SKIP
        ):
            return True
    return False


def _uol_target_available(
    abs_path: str, *, client_image: WzImage | None, source_image: WzImage, copied_root: str,
) -> bool:
    if not abs_path:
        return False
    if client_image is not None and client_image.root.get(abs_path) is not None:
        return True
    source_node = source_image.root.get(abs_path)
    if source_node is None:
        return False
    if not copied_root:
        return True
    return abs_path == copied_root or abs_path.startswith(f"{copied_root}/")


_JSON_METADATA_LEAVES = frozenset({"origin", "delay", "z", "head", "lt", "rb"})


def _json_companion_key_allowed(key: str, authoritative: set[str]) -> bool:
    """JSON dumps may fill origin/delay on existing frames, not invent ball/type."""
    if key in authoritative:
        return True
    if "/" not in key:
        return False
    parent, leaf = key.rsplit("/", 1)
    return leaf in _JSON_METADATA_LEAVES and parent in authoritative


def canvas_metadata_companion_paths(source_path: Path, *, allow_extract: bool = False) -> list[Path]:
    """MS extract first, then TMS logical Mob.img, then JSON dump. Never the _Canvas store itself."""
    if not is_mob_canvas_store(source_path):
        return []
    item_id = source_path.stem
    if not re.fullmatch(r"\d{7}", item_id):
        return []
    ordered: list[Path] = []
    seen: set[str] = set()

    def add(path: Path | None) -> None:
        if path is None or not path.is_file():
            return
        resolved = path.resolve()
        if resolved == source_path.resolve():
            return
        key = str(resolved)
        if key in seen:
            return
        seen.add(key)
        ordered.append(path)

    pack = None
    try:
        pack = ms_mob_index().get(item_id)
    except Exception:
        pack = None
    if pack is not None:
        extracted = _existing_ms_extract(item_id, pack)
        if extracted is None and allow_extract:
            try:
                found = extract_ms_mob(item_id)
                extracted = found[0] if found else None
            except Exception:
                extracted = None
        add(extracted)
    add(find_extracted_ms_mob(item_id))
    add(_TMS_DATA / "Mob" / f"{item_id}.img")
    add(_ROOT / "clien" / "Data" / "Mob" / f"{item_id}.img.json")
    return ordered


def merge_canvas_metadata_tables(source_path: Path, *, allow_extract: bool = False) -> dict[str, dict[str, Any]]:
    """IMG trees win. JSON only supplies origin/delay/pose scalars on paths those IMGs already have.

    ``clien/Data/Mob/<id>.img.json`` is a flattened dump and can contain folders the live
    TMS ``_Canvas`` / MS logical record never had (Damien 8880100 attack2 ``ball``).
    """
    merged: dict[str, dict[str, Any]] = {}
    json_tables: list[dict[str, dict[str, Any]]] = []
    if is_mob_canvas_store(source_path) and source_path.is_file():
        for key, meta in flatten_img_records(source_path).items():
            merged.setdefault(key, meta)
    for companion in canvas_metadata_companion_paths(source_path, allow_extract=allow_extract):
        nodes, _ = flatten_source(companion)
        if companion.suffix.lower() == ".json":
            json_tables.append(nodes)
            continue
        for key, meta in nodes.items():
            merged.setdefault(key, meta)
    authoritative = set(merged)
    for nodes in json_tables:
        for key, meta in nodes.items():
            if key in merged:
                continue
            if _json_companion_key_allowed(key, authoritative):
                merged[key] = meta
    return merged


def _is_placeholder_canvas_meta(meta: dict[str, Any] | None) -> bool:
    if not meta:
        return False
    try:
        width = int(meta.get("width") or 0)
        height = int(meta.get("height") or 0)
    except (TypeError, ValueError):
        return False
    return 0 < width <= _PLACEHOLDER_MAX_SIZE and 0 < height <= _PLACEHOLDER_MAX_SIZE


def _origin_nonzero(value: Any) -> bool:
    if isinstance(value, WzVectorProperty):
        return int(value.x) != 0 or int(value.y) != 0
    if isinstance(value, dict):
        return int(value.get("x", 0) or 0) != 0 or int(value.get("y", 0) or 0) != 0
    return False


def _logical_pose_usable(logical: WzCanvasProperty) -> bool:
    """MS logical frames are often 1x1 + _outlink, but origin/head are still real."""
    if logical.child("head") is not None or logical.child("lt") is not None:
        return True
    origin = logical.child("origin")
    if _origin_nonzero(origin):
        return True
    return int(logical.width) > _PLACEHOLDER_MAX_SIZE or int(logical.height) > _PLACEHOLDER_MAX_SIZE


def _companion_pose_usable(abs_path: str, companion_nodes: dict[str, dict[str, Any]]) -> bool:
    origin_meta = companion_nodes.get(f"{abs_path}/origin") or {}
    if _origin_nonzero(origin_meta.get("value")):
        return True
    if companion_nodes.get(f"{abs_path}/head") or companion_nodes.get(f"{abs_path}/lt"):
        return True
    return not _is_placeholder_canvas_meta(companion_nodes.get(abs_path))


def _clone_canvas_child(name: str, source: WzProperty, parent: WzCanvasProperty) -> WzProperty | None:
    if isinstance(source, WzVectorProperty):
        return WzVectorProperty(name, int(source.x), int(source.y), parent)
    if isinstance(source, (WzIntProperty, WzShortProperty, WzLongProperty)):
        return WzIntProperty(name, int(source.value), parent)
    return None


def _child_from_flatten_meta(name: str, meta: dict[str, Any], parent: WzCanvasProperty) -> WzProperty | None:
    node_type = str(meta.get("type") or "").lower()
    if name in {"origin", "head", "lt", "rb"} or node_type == "vector":
        value = meta.get("value") or {}
        if not isinstance(value, dict):
            return None
        return WzVectorProperty(name, int(value.get("x", 0)), int(value.get("y", 0)), parent)
    if name in {"delay", "z"} or node_type in {"int", "short", "long"}:
        value = meta.get("value")
        if value is None:
            return None
        return WzIntProperty(name, int(value), parent)
    return None


def attach_legacy_canvas_metadata(
    canvas: WzCanvasProperty,
    logical: WzCanvasProperty | None,
    abs_path: str,
    companion_nodes: dict[str, dict[str, Any]],
) -> int:
    """Copy origin/delay/pose scalars from the logical/MS/JSON tree onto a materialized canvas.

    Pixel stores usually have empty Canvas children. Placeholder 1x1 origin=(0,0) is not
    applied onto a larger decoded frame; delay still copies. Missing origin/delay get
    Zakum-style defaults: (width/2, height) and 90ms, or (0,0) on a 1x1 stub.
    """
    added = 0
    companion_usable = _companion_pose_usable(abs_path, companion_nodes)
    logical_usable = logical is not None and _logical_pose_usable(logical)

    for name in _LEGACY_MOB_CANVAS_CHILDREN:
        if canvas.child(name) is not None:
            continue
        pose_field = name in _POSE_CANVAS_CHILDREN
        if logical is not None and (not pose_field or logical_usable):
            child = logical.child(name)
            cloned = _clone_canvas_child(name, child, canvas) if child is not None else None
            if cloned is not None:
                canvas.add(cloned)
                added += 1
                continue
        if pose_field and not companion_usable:
            continue
        meta = companion_nodes.get(f"{abs_path}/{name}")
        if meta is None:
            continue
        cloned = _child_from_flatten_meta(name, meta, canvas)
        if cloned is None:
            continue
        canvas.add(cloned)
        added += 1

    if canvas.child("origin") is None:
        width, height = int(canvas.width), int(canvas.height)
        origin = (0, 0) if width <= 1 and height <= 1 else (width // 2, height)
        canvas.add(WzVectorProperty("origin", origin[0], origin[1], canvas))
        added += 1
    if canvas.child("delay") is None:
        canvas.add(WzIntProperty("delay", _DEFAULT_FRAME_DELAY, canvas))
        added += 1
    return added


def attach_companion_uols(
    clone: WzProperty,
    source_path: Path,
    copied_root: str,
    client_image: WzImage | None,
    skipped: list[str],
    source_image: WzImage | None = None,
    materializer: arc.CanvasMaterializer | None = None,
) -> int:
    """Copy logical UOLs, scalars, and store-missing frames from the TMS companion."""
    if not isinstance(clone, WzSubProperty) or not is_mob_canvas_store(source_path):
        return 0
    extra = merge_canvas_metadata_tables(source_path, allow_extract=True)
    if not extra:
        return 0
    prefix = copied_root.strip("/")
    kept = 0

    def ensure_parent(relative: str) -> tuple[WzSubProperty, str] | None:
        parent: WzProperty = clone
        parts = [part for part in relative.split("/") if part]
        if not parts:
            return None
        for name in parts[:-1]:
            if not isinstance(parent, WzSubProperty):
                return None
            child = parent.get(name)
            if child is None:
                child = WzSubProperty(name, parent)
                parent.add(child)
            parent = child
        if not isinstance(parent, WzSubProperty):
            return None
        return parent, parts[-1]

    for path in sorted(extra, key=lambda item: (item.count("/"), item)):
        if str(extra[path].get("type") or "").lower() not in {
            "uol", "canvas", "imgdir", "short", "int", "long", "float", "double", "string", "vector",
        }:
            continue
        if prefix and path != prefix and not path.startswith(f"{prefix}/"):
            continue
        if path == prefix:
            continue
        ancestor = path
        under_canvas = False
        while "/" in ancestor:
            ancestor = ancestor.rsplit("/", 1)[0]
            if str(extra.get(ancestor, {}).get("type") or "").lower() in {"canvas", "uol"}:
                under_canvas = True
                break
        if under_canvas:
            continue
        if skip_companion_leaf(path):
            skipped.append(path)
            continue
        relative = path[len(prefix) + 1:] if prefix and path.startswith(f"{prefix}/") else path
        if not relative or clone.get(relative) is not None:
            continue
        meta = extra[path]
        node_type = str(meta.get("type") or "").lower()
        if path == "info/mobType" and node_type == "string" and not re.fullmatch(
            r"[0-4]N", str(meta.get("value") or ""),
        ):
            skipped.append(path)
            continue
        if path == "info/maxHP" and node_type == "string":
            existing_hp = client_image.root.get(path) if client_image is not None else None
            meta = {
                **meta,
                "type": "int",
                "value": _legacy_client_maxhp(meta.get("value"), existing_hp),
            }
            node_type = "int"
        parent_leaf = ensure_parent(relative)
        if parent_leaf is None:
            continue
        parent, leaf = parent_leaf
        if parent.get(leaf) is not None:
            continue
        added: WzProperty | None = None
        if node_type == "uol":
            value = str(meta.get("value") or meta.get("target") or "")
            if leaf.isdigit() and "/info/" in f"/{path}/":
                skipped.append(path)
                continue
            if not value:
                skipped.append(path)
                continue
            action = path.split("/", 1)[0]
            if value.isdigit() and re.fullmatch(r"(?:attack|skill|skillAfter)\d+", action):
                value = f"../{action}/{value}"
            abs_target = resolve_uol_absolute(path, value)
            if not _uol_target_in_clone(clone, prefix, abs_target):
                if client_image is None or client_image.root.get(abs_target) is None:
                    skipped.append(path)
                    continue
            added = WzUolProperty(leaf, value, parent)
            kept += 1
        elif node_type == "canvas":
            folder = None
            for candidate in ("ball", "hit", "areaWarning", "effect"):
                if f"/info/{candidate}/" in f"{path}/":
                    folder = candidate
                    break
            if folder is None:
                uol_value = _outlink_frame_uol(path, extra)
                if not uol_value:
                    skipped.append(path)
                    continue
                abs_target = resolve_uol_absolute(path, uol_value)
                if not _uol_target_in_clone(clone, prefix, abs_target):
                    if client_image is None or client_image.root.get(abs_target) is None:
                        action = abs_target.split("/", 1)[0] if abs_target else ""
                        raise ValueError(
                            f"{path} 是 1×1 _outlink → {uol_value}，"
                            f"目标 {abs_target or uol_value} 不在当前怪物上，请先复制 {action or '被引用的动作'}"
                        )
                added = WzUolProperty(leaf, uol_value, parent)
                kept += 1
            else:
                width = int(meta.get("width") or 0)
                height = int(meta.get("height") or 0)
                if folder == "areaWarning" and leaf == "0":
                    added = _legacy_stub_canvas(leaf, parent)
                    if isinstance(added, WzCanvasProperty):
                        attach_legacy_canvas_metadata(added, None, path, extra)
                    parent.add(added)
                    continue
                found = find_tms_canvas_store_match(source_path, width, height, leaf, folder)
                if found is None and source_image is not None:
                    for candidate_path in (path, re.sub(r"attack\d+/info/hit/", "attack1/info/hit/", path)):
                        alt = source_image.root.get(candidate_path)
                        if isinstance(alt, WzCanvasProperty) and int(alt.width) > 1 and int(alt.height) > 1:
                            found = (source_image, alt, source_path)
                            break
                if found is None or materializer is None:
                    skipped.append(path)
                    continue
                linked_image, linked_canvas, linked_path = found
                added = arc.clone_property(
                    linked_canvas, parent, linked_image, linked_path, materializer, leaf,
                )
                if isinstance(added, WzCanvasProperty):
                    attach_legacy_canvas_metadata(added, None, path, extra)
        elif node_type == "vector":
            value = meta.get("value") or {}
            added = WzVectorProperty(leaf, int(value.get("x", 0)), int(value.get("y", 0)), parent)
        elif node_type in {"short", "int", "long", "float", "double", "string"}:
            value = meta.get("value")
            if value is None:
                skipped.append(path)
                continue
            makers = {
                "short": WzShortProperty, "int": WzIntProperty, "long": WzLongProperty,
                "float": WzFloatProperty, "double": WzDoubleProperty, "string": WzStringProperty,
            }
            added = makers[node_type](leaf, value, parent)
        elif node_type == "imgdir":
            continue
        if added is not None:
            parent.add(added)
    return kept


def clone_compatible_mob_node(
    source: WzProperty,
    source_image: WzImage,
    source_path: Path,
    *,
    client_image: WzImage | None = None,
    copied_root: str = "",
    dest_mob_id: str = "",
) -> tuple[WzProperty, arc.CanvasMaterializer, dict[str, Any]]:
    """Project a mob subtree onto GMS canvases, keep resolvable UOLs, skip modern fields."""
    materializer = arc.CanvasMaterializer()
    materializer.max_edge = None
    skipped: list[str] = []
    stats = {"skipped": skipped, "uolsKept": 0, "densified": 0, "canvasMeta": 0}
    copied_root = copied_root.strip("/") or property_path(source)
    companion_nodes = merge_canvas_metadata_tables(source_path, allow_extract=True)

    def materialize_canvas(node: WzProperty, parent: WzProperty | None, lookup_path: str) -> WzProperty | None:
        if _keep_area_warning_stub(node, lookup_path):
            cloned = _legacy_stub_canvas(node.name, parent)
            if isinstance(cloned, WzCanvasProperty):
                logical = node if isinstance(node, WzCanvasProperty) else None
                stats["canvasMeta"] += attach_legacy_canvas_metadata(
                    cloned, logical, lookup_path, companion_nodes,
                )
            return cloned
        try:
            linked_image, linked_canvas, linked_path = resolve_canvas_node(
                source_image, property_path(node), source_path,
            )
        except ValueError:
            if _is_area_warning_frame(lookup_path or property_path(node) or node.name, node) and _is_tiny_canvas(node):
                cloned = _legacy_stub_canvas(node.name, parent)
                if isinstance(cloned, WzCanvasProperty):
                    logical = node if isinstance(node, WzCanvasProperty) else None
                    stats["canvasMeta"] += attach_legacy_canvas_metadata(
                        cloned, logical, lookup_path, companion_nodes,
                    )
                return cloned
            skipped.append(property_path(node) or node.name)
            return None
        cloned = arc.clone_property(
            linked_canvas, parent, linked_image, linked_path, materializer, node.name,
        )
        if isinstance(cloned, WzCanvasProperty):
            logical = node if isinstance(node, WzCanvasProperty) else None
            stats["canvasMeta"] += attach_legacy_canvas_metadata(
                cloned, logical, lookup_path, companion_nodes,
            )
        return cloned

    def project_uol(node: WzUolProperty, parent: WzProperty | None) -> WzProperty | None:
        target = str(node.value)
        action = copied_root.split("/", 1)[0] if copied_root else (parent.name if parent is not None else "")
        if target.isdigit() and re.fullmatch(r"(?:attack|skill|skillAfter)\d+", action):
            target = f"../{action}/{target}"
        abs_path = resolve_uol_absolute(property_path(node), target)
        if _uol_target_available(
            abs_path, client_image=client_image, source_image=source_image, copied_root=copied_root,
        ):
            stats["uolsKept"] += 1
            return WzUolProperty(node.name, target, parent)
        return materialize_canvas(node, parent, abs_path)

    def clone_node(node: WzProperty, parent: WzProperty | None) -> WzProperty | None:
        if _skip_incompatible_mob_node(node):
            skipped.append(property_path(node) or node.name)
            return None
        if node.name == "maxHP" and not _under_action_info(node):
            existing = client_image.root.get("info/maxHP") if client_image is not None else None
            return WzIntProperty(node.name, _legacy_client_maxhp(getattr(node, "value", None), existing), parent)
        if node.name == "mobType" and isinstance(node, WzStringProperty) and not _under_action_info(node):
            if not re.fullmatch(r"[0-4]N", str(node.value)):
                skipped.append(property_path(node) or node.name)
                return None
        if isinstance(node, WzUolProperty):
            return project_uol(node, parent)
        if isinstance(node, WzCanvasProperty):
            return materialize_canvas(node, parent, property_path(node))
        if isinstance(node, WzSubProperty):
            output = WzSubProperty(node.name, parent)
            for child in node.children():
                cloned = clone_node(child, output)
                if cloned is not None:
                    output.add(cloned)
            return output
        if node.name == "maxHP" and isinstance(node, (WzIntProperty, WzLongProperty)):
            capped = min(int(node.value), _CLIENT_MAXHP_INT)
            return type(node)(node.name, capped, parent)
        if node.name == "eva" and isinstance(node, (WzIntProperty, WzLongProperty)):
            capped = min(int(node.value), map_compat.BOSS_EVA_CAP)
            return type(node)(node.name, capped, parent)
        return arc.clone_property(node, parent, source_image, source_path, materializer)

    clone = clone_node(source, None)
    if clone is None:
        raise ValueError(f"节点 {copied_root or source.name} 没有可投影到旧端的内容")
    stats["uolsKept"] += attach_companion_uols(
        clone, source_path, copied_root, client_image, skipped, source_image, materializer,
    )
    info = clone if clone.name == "info" else clone.child("info") if isinstance(clone, WzSubProperty) else None
    if isinstance(info, WzSubProperty) and not _under_action_info(info):
        hp = info.child("maxHP")
        existing_hp = client_image.root.get("info/maxHP") if client_image is not None else None
        if not isinstance(hp, (WzIntProperty, WzLongProperty)) or int(hp.value) <= 0:
            if hp is not None:
                info._children.pop("maxHP", None)
            info.add(WzIntProperty("maxHP", _legacy_client_maxhp(getattr(hp, "value", None), existing_hp), info))
    ensure_ballistic_contract(clone)
    ensure_area_attack_contract(clone)
    ensure_projected_root_skill_table(
        clone, existing_image=client_image, dest_mob_id=dest_mob_id,
    )
    ensure_legacy_speed_without_move(clone, client_image)
    ensure_legacy_lifefactory_info(clone, client_image)
    stats["uolsKept"] += ensure_fsm_only_stand_body(
        clone,
        source=source,
        client_image=client_image,
        companion_nodes=companion_nodes,
        copied_root=copied_root,
    )
    ensure_legacy_attack_body_frame(clone)
    stats["densified"] += compact_mob_tree(clone)
    stats["densified"] += ensure_area_warning_leading_stub(clone)
    validate_action_frame_timeline(clone)
    return clone, materializer, stats


def clone_compatible_mob_action(
    source: WzSubProperty,
    source_image: WzImage,
    source_path: Path,
    *,
    client_image: WzImage | None = None,
    dest_mob_id: str = "",
) -> tuple[WzSubProperty, arc.CanvasMaterializer]:
    if not _LEGACY_MOB_ACTION.fullmatch(source.name):
        raise ValueError(f"动作名称不属于旧端已知结构: {source.name}")
    clone, materializer, _stats = clone_compatible_mob_node(
        source, source_image, source_path,
        client_image=client_image, copied_root=source.name, dest_mob_id=dest_mob_id,
    )
    if not isinstance(clone, WzSubProperty):
        raise ValueError(f"动作根节点不是 imgdir: {source.name}")
    return clone, materializer


def audit_mob_action_canvases(data: bytes, image_name: str, action_name: str) -> dict[str, Any]:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=image_name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise ValueError(f"动作迁移结果解析失败: {image.parse_warnings}")
    action = image.root.get(action_name)
    if not isinstance(action, WzSubProperty):
        raise ValueError(f"迁移后动作不存在: {action_name}")

    canvases = 0
    visible = 0
    formats: set[tuple[int, int]] = set()

    def visit(node: WzProperty) -> None:
        nonlocal canvases, visible
        if isinstance(node, WzCanvasProperty):
            canvases += 1
            formats.add((int(node.format), int(node.format2)))
            bitmap = decode_canvas(node, region="GMS").convert("RGBA")
            if bitmap.width > 4 and bitmap.height > 4 and bitmap.getchannel("A").getbbox():
                visible += 1
        for child in node.children() if hasattr(node, "children") else ():
            visit(child)

    visit(action)
    if not canvases:
        raise ValueError(f"动作 {action_name} 没有 Canvas，拒绝迁移")
    if formats != {(1, 0)}:
        raise ValueError(f"动作 {action_name} Canvas 不是 GMS ARGB4444: {sorted(formats)}")
    if not visible:
        raise ValueError(f"动作 {action_name} 只有占位或透明 Canvas，拒绝迁移")
    return {"canvases": canvases, "visible": visible, "formats": ["1/0"]}


def img_record_reference_hazard(
    data: bytes, path: tuple[str, ...], *, region: str = "GMS",
) -> int:
    """统计有多少处字符串引用指向 ``path`` 记录内部的字节区间。

    旧版 IMG 没有独立字符串块：属性名在首次出现处内联，之后的同名属性用绝对偏移
    回指。若某个记录内部正好存着这些共享名字（通常是文件里第一个大动作），就不能
    对它做**变长**替换——那 1000+ 处引用的目标偏移会全部失效。
    返回 0 表示可安全变长替换；正数则只允许同长度原地改写。
    """
    layout = scan_img(data, region=region)
    found: list[Any] = []

    def walk(prop_list: Any, parent: tuple[str, ...] = ()) -> None:
        if found:
            return
        for record in prop_list.records:
            current = (*parent, record.name)
            if current == path:
                found.append(record)
                return
            if record.children is not None:
                walk(record.children, current)
            if found:
                return

    walk(layout.root)
    if not found:
        return 0
    span = found[0]
    return sum(
        1 for reference in layout.string_references
        if span.start <= reference.target_offset < span.end
    )


def img_length_change_blocked_message(node_label: str, hazard: int) -> str:
    """旧版 IMG 无法变长改写时的可执行提示。"""
    return (
        f"{node_label} 不能变长改写：它所在的字节区间被 {hazard} 处共享属性名引用占用，"
        "改动长度会让这些回指偏移全部失效。这是旧版 IMG（没有独立字符串块）的格式限制，"
        "不是可以绕过的工具缺陷。可行做法：改用同一只怪物里其它动作（文件里第一个大动作通常最受限）；"
        "或用动作级迁移整条新增/替换动作。"
    )


def verify_img_replace_scope(
    before: bytes, after: bytes, approved_root: tuple[str, ...], *, label: str = "替换",
) -> int:
    """证明只有 approved_root 记录变了，其余记录逐字节不变。

    ``approved_root`` 可以是任意深度的记录路径，例如 ``("attack1",)`` 或
    ``("die1", "0")``。记录跨度包含自己的子记录，所以被替换记录的**祖先**跨度
    也会变——祖先只校验子节点顺序，不校验整段字节。
    """
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)
    depth = len(approved_root)

    def inside(path: tuple[str, ...]) -> bool:
        return path[:depth] == approved_root

    def is_ancestor(path: tuple[str, ...]) -> bool:
        return len(path) < depth and approved_root[:len(path)] == path

    def protected(path: tuple[str, ...]) -> bool:
        return not inside(path) and not is_ancestor(path)

    removed = {path for path in before_records.keys() - after_records.keys() if protected(path)}
    added = {path for path in after_records.keys() - before_records.keys() if protected(path)}
    if removed or added:
        raise ValueError(f"{label}影响了其他记录: removed={sorted(removed)} added={sorted(added)}")
    for parent, names in before_orders.items():
        if inside(parent):
            continue
        if after_orders.get(parent) != names:
            raise ValueError(f"{label}改变了其他兄弟顺序: {'/'.join(parent) or '/'}")
    protected_count = 0
    for path, raw in before_records.items():
        if not protected(path):
            continue
        if after_records.get(path) != raw:
            raise ValueError(f"{label}改变了未授权记录: {'/'.join(path)}")
        protected_count += 1
    return protected_count


def verify_mob_action_replace_scope(before: bytes, after: bytes, action_name: str) -> int:
    return verify_img_replace_scope(before, after, (action_name,), label="动作迁移")


def audit_mob_frame_canvas(
    data: bytes, image_name: str, frame_path: str, *, allow_blank: bool = False,
) -> dict[str, Any]:
    """校验单帧写入结果：必须是 GMS ARGB4444，且默认要求有可见像素。"""
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=image_name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise ValueError(f"帧写入结果解析失败: {image.parse_warnings}")
    node = image.root.get(frame_path)
    if not isinstance(node, WzCanvasProperty):
        raise ValueError(f"写入后帧不存在或不是 Canvas: {frame_path}")
    formats = {(int(node.format), int(node.format2))}
    if formats != {(1, 0)}:
        raise ValueError(f"帧 Canvas 不是 GMS ARGB4444: {sorted(formats)}")
    if not node.has_pixels():
        raise ValueError(f"帧 {frame_path} 没有像素数据")
    bitmap = decode_canvas(node, region="GMS").convert("RGBA")
    visible = bitmap.width > 4 and bitmap.height > 4 and bool(bitmap.getchannel("A").getbbox())
    if not visible and not allow_blank:
        raise ValueError(
            f"帧 {frame_path} 只有占位或全透明像素（{bitmap.width}×{bitmap.height}）："
            "这通常说明源帧本身没有真实资源，拒绝写入。如确实要写入空帧，请显式勾选“允许空帧”。"
        )
    return {
        "canvas": 1, "visible": 1 if visible else 0,
        "width": bitmap.width, "height": bitmap.height, "formats": ["1/0"],
    }


def copy_mob_frame_with_server_sync(
    client_path: Path, source_path: Path, source_frame_path: str,
    action_name: str, frame_index: int, *, dry_run: bool = False,
    allow_blank: bool = False, sync_server: bool = True,
) -> dict[str, Any]:
    """把一帧的真实像素复制/替换到项目怪物 IMG。

    占位帧会被解析到真实资源后再写入（TMS 的 1×1 占位本身没有像素）。
    只做增量记录替换：其他帧的记录逐字节保持不变，并同步服务端 Mob XML。
    """
    require_repo_write(client_path)
    if client_path.parent.resolve() != (_ROOT / "clien" / "Data" / "Mob").resolve():
        raise ValueError("帧复制目标必须是 clien/Data/Mob 下的 IMG")
    if not client_path.is_file():
        raise ValueError(f"当前项目怪物 IMG 不存在: {relative_path(client_path)}")
    action_name = action_name.strip()
    if not action_name or "/" in action_name or "\\" in action_name:
        raise ValueError("动作名称必须是顶层节点名")
    source_frame_path = source_frame_path.strip("/")
    if not source_frame_path:
        raise ValueError("缺少 sourceFramePath")
    frame_name = str(int(frame_index))

    source_image = load_image(source_path)
    source_node = source_image.root.get(source_frame_path)
    if source_node is None:
        raise ValueError(f"源帧不存在: {source_frame_path}")
    reference = canvas_reference(source_path, source_frame_path)
    if reference["resolved"] is None:
        raise ValueError(
            f"源帧没有可复制的真实像素：{source_frame_path}"
            f"（{reference['error'] or '无像素来源'}）"
        )
    if reference["state"] == "orphan" and not allow_blank:
        raise ValueError(
            f"源帧 {source_frame_path} 是空占位（声明 "
            f"{reference['declaredWidth']}×{reference['declaredHeight']}，无链接，"
            "TMS 里它本身就没有可见像素）：复制过去只会得到一个透明小图。"
            "请改用同一动作里有真实资源的帧；如确实要写入空帧，请显式允许空帧。"
        )

    client_original = client_path.read_bytes()
    if detect_region_from_img(client_original) != "GMS":
        raise ValueError("当前项目怪物 IMG 不是 GMS 格式")
    client_image = _verified_img_from_bytes(client_path, client_original)
    target_action = client_image.root.get(action_name)
    if not isinstance(target_action, WzSubProperty):
        raise ValueError(
            f"客户端缺少动作目录 {action_name}，单帧复制只负责“替换/补帧”。"
            f"请改用动作级迁移：它会把 {reference['resolved']['fileLabel']} "
            f"里该动作的全部真实帧一次带入。"
        )
    existing_frame = target_action.get(frame_name)

    materializer = arc.CanvasMaterializer()
    clone = arc.clone_property(
        source_node, None, source_image, source_path, materializer, name=frame_name,
    )
    if not isinstance(clone, WzCanvasProperty):
        raise ValueError(f"源帧不是 Canvas，无法复制: {source_frame_path}")

    target_frame_path = f"{action_name}/{frame_name}"
    reference_hazard = 0
    if existing_frame is None:
        client_data = arc.append_property_record(client_original, (action_name,), clone)
        arc.verify_raw_record_insert_scope(client_original, client_data, {(action_name,)})
        protected_records = len(arc.raw_record_state(client_original)[0])
        client_operation = "add"
    else:
        reference_hazard = img_record_reference_hazard(
            client_original, (action_name, frame_name),
        )
        try:
            client_data = replace_img_record(
                client_original, (action_name, frame_name), clone, region="GMS",
            ).data
        except ValueError as exc:
            if "points into replaced bytes" in str(exc):
                raise ValueError(
                    img_length_change_blocked_message(
                        f"{action_name}/{frame_name}", reference_hazard,
                    )
                ) from exc
            raise
        protected_records = verify_img_replace_scope(
            client_original, client_data, (action_name, frame_name), label="帧替换",
        )
        client_operation = "replace"
    canvas_audit = audit_mob_frame_canvas(
        client_data, client_path.name, target_frame_path, allow_blank=allow_blank,
    )

    server_path = server_xml_for_client(client_path)
    server_original = None
    server_data = None
    server_operation = "skipped"
    if sync_server and server_path is not None and server_path.is_file():
        server_original = server_path.read_bytes()
        spans = index_xml(server_original)
        # 暂存用系统临时目录：xml_*_cloned_node 需要真实文件路径，但目录位置无所谓
        # （atomic_write 自己在目标同目录建临时文件）。放在仓库里会污染工作区，
        # 且临时目录清理会被当成仓库内的批量删除。
        with tempfile.TemporaryDirectory(prefix="beidou-copy-mob-frame-") as directory:
            staged_server = Path(directory) / server_path.name
            staged_server.write_bytes(server_original)
            if target_frame_path in spans:
                xml_replace_cloned_node(
                    staged_server, target_frame_path, clone, dry_run=False, backup=False,
                )
                server_operation = "replace"
            elif action_name in spans and spans[action_name].tag == "imgdir":
                xml_add_cloned_node(
                    staged_server, action_name, clone, dry_run=False, backup=False,
                )
                server_operation = "addFrame"
            else:
                # 服务端镜像里没有这个动作目录：只补一帧会造成半截动作树，
                # 这里不猜，明确跳过并让界面提示改用动作级迁移。
                server_operation = "skippedMissingAction"
            if server_operation == "skippedMissingAction":
                server_data = None
                server_original = None
            else:
                server_data = staged_server.read_bytes()
                ET.fromstring(server_data)

    client_changed = client_data != client_original
    server_changed = server_data is not None and server_data != server_original
    committed: list[tuple[Path, bytes]] = []
    if not dry_run:
        try:
            if client_changed:
                atomic_write(client_path, client_data, backup=True)
                committed.append((client_path, client_original))
            if server_changed and server_path is not None and server_data is not None \
                    and server_original is not None:
                atomic_write(server_path, server_data, backup=True)
                committed.append((server_path, server_original))
            _load_image_cached.cache_clear()
            _verified_img_from_bytes(client_path, client_path.read_bytes())
            if server_changed and server_path is not None:
                ET.parse(server_path)
        except Exception:
            for target, original in reversed(committed):
                atomic_write(target, original, backup=False)
            _load_image_cached.cache_clear()
            raise

    modified_files: list[str] = []
    if client_changed and not dry_run:
        modified_files.append(relative_path(client_path))
    if server_changed and not dry_run and server_path is not None:
        modified_files.append(relative_path(server_path))
    # 与 migrate_mob_action_with_server_sync 一致：modifiedFiles 只表示“已写入”。
    # dry run 想展示将要改哪些文件时用 plannedFiles。
    planned_files: list[str] = []
    if client_changed:
        planned_files.append(relative_path(client_path))
    if server_changed and server_path is not None:
        planned_files.append(relative_path(server_path))
    return {
        "action": action_name,
        "frame": frame_name,
        "framePath": target_frame_path,
        "sourcePath": relative_path(source_path),
        "sourceFramePath": source_frame_path,
        "sourceSummary": canvas_reference_summary(reference),
        "sourceResolved": reference["resolved"],
        "sourceState": reference["state"],
        "sourceCrossMob": reference["crossMob"],
        "declaredWidth": reference["declaredWidth"],
        "declaredHeight": reference["declaredHeight"],
        "clientPath": relative_path(client_path),
        "serverPath": relative_path(server_path) if server_path is not None else "",
        "clientOperation": client_operation,
        "serverOperation": server_operation,
        "changed": client_changed or server_changed,
        "dryRun": dry_run,
        "canvas": canvas_audit,
        "materialized": {
            "canvases": materializer.canvases,
            "links": materializer.links,
            "resized": materializer.resized,
        },
        "rawScope": {
            "approvedRoots": [target_frame_path],
            "protectedRecords": protected_records,
            "referencedStringRefs": reference_hazard,
        },
        "modifiedFiles": modified_files,
        "plannedFiles": planned_files,
        "sha256": {"client": hashlib.sha256(client_data).hexdigest()},
    }


def migrate_mob_action_with_server_sync(
    client_path: Path, source_path: Path, action_name: str, *, dry_run: bool = False,
) -> dict[str, Any]:
    require_repo_write(client_path)
    if client_path.parent.resolve() != (_ROOT / "clien" / "Data" / "Mob").resolve():
        raise ValueError("动作迁移目标必须是 clien/Data/Mob 下的 IMG")
    if not client_path.is_file():
        raise ValueError("当前项目怪物 IMG 不存在，不能只迁移单个动作")
    action_name = action_name.strip()
    if "/" in action_name or "\\" in action_name or not action_name:
        raise ValueError("动作名称必须是顶层节点名")

    source_image = load_image(source_path)
    source_action = source_image.root.get(action_name)
    if not isinstance(source_action, WzSubProperty):
        raise ValueError(f"TMS 动作不存在或不是 imgdir: {action_name}")
    server_path = server_xml_for_client(client_path)
    if server_path is None or not server_path.is_file():
        raise ValueError("当前项目缺少对应的服务端 Mob XML，不能执行动作级同步")
    client_original = client_path.read_bytes()
    if detect_region_from_img(client_original) != "GMS":
        raise ValueError("当前项目怪物 IMG 不是 GMS 格式")
    client_image = _verified_img_from_bytes(client_path, client_original)
    clone, materializer = clone_compatible_mob_action(
        source_action, source_image, source_path,
        client_image=client_image, dest_mob_id=client_path.stem,
    )
    current = client_image.root.get(action_name)
    if current is not None and not isinstance(current, WzSubProperty):
        raise ValueError(f"当前项目同名节点不是动作目录: {action_name}")

    if current is None:
        client_data = arc.append_property_record(client_original, (), clone)
        arc.verify_raw_record_insert_scope(client_original, client_data, {(action_name,)})
        protected_records = len(arc.raw_record_state(client_original)[0])
        client_operation = "add"
    else:
        try:
            client_data = replace_img_record(
                client_original, (action_name,), clone, region="GMS",
            ).data
        except ValueError as exc:
            if "points into replaced bytes" in str(exc):
                raise ValueError(img_length_change_blocked_message(
                    f"动作 {action_name}",
                    img_record_reference_hazard(client_original, (action_name,)),
                )) from exc
            raise
        protected_records = verify_mob_action_replace_scope(
            client_original, client_data, action_name,
        )
        client_operation = "replace"
    canvas_audit = audit_mob_action_canvases(client_data, client_path.name, action_name)

    server_original = server_path.read_bytes()
    with tempfile.TemporaryDirectory(prefix=".migrate-mob-action-", dir=_HERE) as directory:
        staged_server = Path(directory) / server_path.name
        staged_server.write_bytes(server_original)
        if action_name in index_xml(server_original):
            xml_result = xml_replace_cloned_node(
                staged_server, action_name, clone, dry_run=False, backup=False,
            )
            server_operation = "replace"
        else:
            xml_result = xml_add_cloned_node(
                staged_server, "", clone, dry_run=False, backup=False,
            )
            server_operation = "add"
        server_data = staged_server.read_bytes()
        ET.fromstring(server_data)
        if action_name not in index_xml(server_data):
            raise ValueError(f"服务端动作同步失败: {action_name}")

    client_changed = client_data != client_original
    server_changed = server_data != server_original
    committed: list[tuple[Path, bytes]] = []
    try:
        if client_changed and not dry_run:
            atomic_write(client_path, client_data, backup=True)
            committed.append((client_path, client_original))
        if server_changed and not dry_run:
            atomic_write(server_path, server_data, backup=True)
            committed.append((server_path, server_original))
        if not dry_run:
            _load_image_cached.cache_clear()
            _verified_img_from_bytes(client_path, client_path.read_bytes())
            ET.parse(server_path)
    except Exception:
        for target, original in reversed(committed):
            atomic_write(target, original, backup=False)
        _load_image_cached.cache_clear()
        raise

    modified_files = []
    if client_changed and not dry_run:
        modified_files.append(relative_path(client_path))
    if server_changed and not dry_run:
        modified_files.append(relative_path(server_path))
    return {
        "action": action_name,
        "clientPath": relative_path(client_path),
        "serverPath": relative_path(server_path),
        "clientOperation": client_operation,
        "serverOperation": server_operation,
        "changed": client_changed or server_changed,
        "dryRun": dry_run,
        "canvas": canvas_audit,
        "materialized": {
            "canvases": materializer.canvases,
            "links": materializer.links,
            "resized": materializer.resized,
        },
        "rawScope": {"approvedRoots": [action_name], "protectedRecords": protected_records},
        "xml": xml_result,
        "modifiedFiles": modified_files,
        "sha256": {
            "client": hashlib.sha256(client_data).hexdigest(),
            "server": hashlib.sha256(server_data).hexdigest(),
        },
    }


def companion_logical_image(source_path: Path) -> WzImage | None:
    """Load the MS / logical Mob.img that holds root info the _Canvas store omits."""
    companion = logical_companion_for_canvas_store(source_path)
    if companion is None and is_mob_canvas_store(source_path):
        try:
            found = extract_ms_mob(source_path.stem)
            companion = found[0] if found else None
        except Exception:
            companion = None
    if companion is None or companion.suffix.lower() != ".img":
        return None
    return load_image(companion)


def companion_logical_node(source_path: Path, node_path: str) -> WzProperty | None:
    image = companion_logical_image(source_path)
    if image is None:
        return None
    if not node_path:
        return image.root
    return image.root.get(node_path)


def resolve_mob_copy_source(
    source_image: WzImage, source_path: Path, node_path: str,
) -> WzProperty | None:
    canvas_node = source_image.root if not node_path else source_image.root.get(node_path)
    companion_node = companion_logical_node(source_path, node_path) if is_mob_canvas_store(source_path) else None
    if canvas_node is None:
        return companion_node
    if (
        isinstance(canvas_node, WzSubProperty)
        and not canvas_node.has_children()
        and companion_node is not None
    ):
        return companion_node
    return canvas_node


def companion_uol_property(source_path: Path, node_path: str) -> WzUolProperty | None:
    if not node_path or not is_mob_canvas_store(source_path):
        return None
    companion = logical_companion_for_canvas_store(source_path)
    if companion is None:
        return None
    extra, _ = flatten_source(companion)
    meta = extra.get(node_path)
    if meta is None or str(meta.get("type") or "").lower() != "uol":
        return None
    value = str(meta.get("value") or meta.get("target") or "")
    if not value:
        return None
    action = node_path.split("/", 1)[0]
    if value.isdigit() and re.fullmatch(r"(?:attack|skill|skillAfter)\d+", action):
        value = f"../{action}/{value}"
    dummy = WzSubProperty("root")
    parent = dummy
    parts = node_path.split("/")
    for name in parts[:-1]:
        child = WzSubProperty(name, parent)
        parent.add(child)
        parent = child
    uol = WzUolProperty(parts[-1], str(value), parent)
    parent.add(uol)
    return uol


def copy_tms_node_with_server_sync(
    client_path: Path, source_path: Path, node_path: str,
) -> dict[str, Any]:
    require_repo_write(client_path)
    source_image = load_image(source_path)
    is_map_source = "/Data/Map/Map/" in source_path.as_posix()
    is_mob_copy = client_path.parent.name == "Mob" or "Mob" in source_path.parts
    if is_mob_copy and is_mob_canvas_store(source_path):
        source_node = resolve_mob_copy_source(source_image, source_path, node_path)
        if source_node is None:
            source_node = companion_uol_property(source_path, node_path)
    else:
        source_node = source_image.root if not node_path else source_image.root.get(node_path)
    if source_node is None:
        raise ValueError(f"TMS 节点不存在: {node_path}")
    resource_references = selected_map_resource_references(source_image.root, node_path) if is_map_source else []
    server_path = server_xml_for_client(client_path)
    if server_path is None:
        raise ValueError("找不到对应的服务端 XML 路径")

    existing_target = None
    existing_image = None
    densified_frames = 0
    uols_kept = 0
    if client_path.is_file():
        existing_image = load_image(client_path)
        existing_target = existing_image.root if not node_path else existing_image.root.get(node_path)
    mergeable_empty = bool(
        isinstance(existing_target, WzSubProperty) and not existing_target.children()
    )
    if existing_target is not None and not mergeable_empty and resource_references:
        resource_result = migrate_missing_entity_resources(resource_references)
        return {
            "path": node_path, "clientPath": relative_path(client_path),
            "serverPath": relative_path(server_path), "client": [], "server": [],
            "createdClient": False, "createdServer": False, "createdAncestors": [],
            "skippedPaths": [], "resourceOnly": True, "resources": resource_result,
            "modifiedFiles": list(dict.fromkeys(resource_result.get("files", []))),
        }

    if is_map_source:
        clone, skipped_paths = clone_compatible_map_node(source_node, client_path)
        materializer = None
    elif is_mob_copy:
        clone, materializer, projection = clone_compatible_mob_node(
            source_node, source_image, source_path,
            client_image=existing_image, copied_root=node_path,
            dest_mob_id=client_path.stem,
        )
        skipped_paths = list(projection.get("skipped") or [])
        densified_frames = int(projection.get("densified") or 0)
        uols_kept = int(projection.get("uolsKept") or 0)
    else:
        clone, skipped_paths = clone_supported_node(source_node), []
        materializer = None
    parent_path = node_path.rpartition("/")[0]

    client_original = client_path.read_bytes() if client_path.is_file() else None
    server_original = server_path.read_bytes() if server_path.is_file() else None
    created_ancestors: list[str] = []
    commit_started = False
    try:
        with tempfile.TemporaryDirectory(prefix=".copy-tms-node-", dir=_HERE) as directory:
            stage = Path(directory)
            staged_client = stage / client_path.name
            staged_server = stage / server_path.name
            staged_client.write_bytes(client_original if client_original is not None else empty_gms_img_bytes())
            staged_server.write_bytes(server_original if server_original is not None else (
                f'<imgdir name="{html.escape(client_path.name, quote=True)}">\n</imgdir>\n'.encode("utf-8")
            ))

            current_parent = ""
            for name in (part for part in parent_path.split("/") if part):
                ancestor_path = f"{current_parent}/{name}".strip("/")
                source_ancestor = source_image.root.get(ancestor_path)
                if not isinstance(source_ancestor, WzSubProperty) and is_mob_copy:
                    source_ancestor = companion_logical_node(source_path, ancestor_path)
                if not isinstance(source_ancestor, WzSubProperty):
                    raise ValueError(f"TMS 父节点不是目录: {ancestor_path}")

                staged_image = _verified_img_from_bytes(staged_client, staged_client.read_bytes())
                client_ancestor = staged_image.root.get(ancestor_path)
                if client_ancestor is None:
                    patch_img_add(
                        staged_client, current_parent, name, "imgdir", None,
                        dry_run=False, backup=False,
                    )
                    created_ancestors.append(ancestor_path)
                elif not isinstance(client_ancestor, WzSubProperty):
                    raise ValueError(f"客户端父节点不是目录: {ancestor_path}")

                server_span = index_xml(staged_server.read_bytes()).get(ancestor_path)
                if server_span is None:
                    xml_add_cloned_node(
                        staged_server, current_parent, WzSubProperty(name), dry_run=False,
                    )
                elif server_span.tag != "imgdir":
                    raise ValueError(f"服务端父节点不是 imgdir: {ancestor_path}")
                current_parent = ancestor_path

            staged_image = _verified_img_from_bytes(staged_client, staged_client.read_bytes())
            existing_target = staged_image.root.get(node_path)
            if not node_path:
                if staged_image.root.children():
                    raise ValueError("客户端根节点已有子节点，不能整根复制")
                server_spans = index_xml(staged_server.read_bytes())
                server_root = server_spans.get("")
                if server_root is None or server_root.tag != "imgdir":
                    raise ValueError("服务端 XML 根节点不存在或不是 imgdir")
                if any(path for path in server_spans):
                    raise ValueError("服务端 XML 根节点已有子节点，不能整根复制")
                client_result = []
                server_result = []
                for child in clone.children():
                    client_result.append(patch_img_add(
                        staged_client, "", child.name, "imgdir", None,
                        dry_run=False, backup=False, node=child,
                    ))
                    server_result.append(xml_add_cloned_node(
                        staged_server, "", child, dry_run=False,
                    ))
            elif existing_target is None:
                if is_mob_copy and node_path == "info" and staged_image.root.children():
                    anchor = staged_image.root.children()[0].name
                    before = staged_client.read_bytes()
                    inserted = arc.insert_property_record_before(before, (), clone, anchor)
                    arc.verify_raw_record_insert_scope(before, inserted, {("info",)})
                    staged_client.write_bytes(inserted)
                    server_text = staged_server.read_text(encoding="utf-8")
                    server_root = ET.fromstring(server_text)
                    xml_anchor = next((child.get("name") for child in server_root if child.get("name")), None)
                    if xml_anchor is not None:
                        staged_server.write_text(
                            arc.insert_xml_properties_before(server_text, (), [clone], xml_anchor),
                            encoding="utf-8",
                        )
                        server_result = {"path": "info", "before": xml_anchor}
                    else:
                        server_result = xml_add_cloned_node(
                            staged_server, parent_path, clone, dry_run=False, backup=False,
                        )
                    client_result = {"path": "info", "before": anchor}
                else:
                    client_result = patch_img_add(
                        staged_client, parent_path, clone.name, "imgdir", None,
                        dry_run=False, backup=False, node=clone,
                    )
                    server_result = xml_add_cloned_node(
                        staged_server, parent_path, clone, dry_run=False,
                    )
            elif (
                isinstance(existing_target, WzSubProperty)
                and isinstance(clone, WzSubProperty)
                and not existing_target.children()
            ):
                server_target = index_xml(staged_server.read_bytes()).get(node_path)
                if server_target is None:
                    xml_add_cloned_node(
                        staged_server, parent_path, WzSubProperty(clone.name), dry_run=False,
                    )
                elif server_target.tag != "imgdir":
                    raise ValueError(f"服务端同名节点不是 imgdir: {node_path}")
                client_result = []
                server_result = []
                for child in clone.children():
                    client_result.append(patch_img_add(
                        staged_client, node_path, child.name, "imgdir", None,
                        dry_run=False, backup=False, node=child,
                    ))
                    server_result.append(xml_add_cloned_node(
                        staged_server, node_path, child, dry_run=False,
                    ))
            elif is_mob_copy and isinstance(clone, WzSubProperty):
                inserts = missing_mob_inserts(clone, existing_target, node_path)
                client_result = []
                server_result = []
                for parent, child in inserts:
                    client_result.append(patch_img_add(
                        staged_client, parent, child.name, "imgdir", None,
                        dry_run=False, backup=False, node=child,
                    ))
                    server_result.append(xml_add_cloned_node(
                        staged_server, parent, child, dry_run=False,
                    ))
                if node_path in {"", "info"}:
                    skill_client, skill_server = replace_existing_mob_skill_table(
                        staged_client, staged_server, clone, node_path,
                    )
                    client_result.extend(skill_client)
                    server_result.extend(skill_server)
                    rate_client, rate_server = sync_clamped_info_rates(
                        staged_client, staged_server, clone, node_path,
                    )
                    client_result.extend(rate_client)
                    server_result.extend(rate_server)
            else:
                raise ValueError(f"客户端同名节点已存在且不是空目录: {node_path}")
            client_data = staged_client.read_bytes()
            server_data = staged_server.read_bytes()
            checked_image = _verified_img_from_bytes(client_path, client_data)
            if is_mob_copy and node_path in {"", "info"}:
                validate_copied_mob_info(checked_image)
            ET.fromstring(server_data)

        client_path.parent.mkdir(parents=True, exist_ok=True)
        server_path.parent.mkdir(parents=True, exist_ok=True)
        commit_started = True
        atomic_write(client_path, client_data, backup=client_original is not None)
        atomic_write(server_path, server_data, backup=server_original is not None)
        _load_image_cached.cache_clear()
        _verified_img_from_bytes(client_path, client_path.read_bytes())
        ET.parse(server_path)
        resource_result = migrate_missing_entity_resources(resource_references)
    except Exception:
        if commit_started:
            if client_original is None:
                if client_path.exists():
                    client_path.unlink()
            else:
                atomic_write(client_path, client_original, backup=False)
            if server_original is None:
                if server_path.exists():
                    server_path.unlink()
            else:
                atomic_write(server_path, server_original, backup=False)
        _load_image_cached.cache_clear()
        raise
    return {
        "path": node_path, "clientPath": relative_path(client_path),
        "serverPath": relative_path(server_path), "client": client_result, "server": server_result,
        "createdClient": client_original is None, "createdServer": server_original is None,
        "createdAncestors": created_ancestors, "skippedPaths": skipped_paths,
        "resources": resource_result,
        "densifiedFrames": densified_frames,
        "uolsKept": uols_kept,
        "materialized": None if materializer is None else {
            "canvases": materializer.canvases,
            "links": materializer.links,
            "resized": materializer.resized,
        },
        "modifiedFiles": list(dict.fromkeys([
            relative_path(client_path), relative_path(server_path), *resource_result.get("files", []),
        ])),
    }


def validate_export_source(path: Path) -> tuple[bytes, str]:
    data = path.read_bytes()
    lower_name = path.name.lower()
    if lower_name.endswith(".img"):
        _verified_img_from_bytes(path, data)
    elif lower_name.endswith((".xml", ".img.xml")):
        ET.fromstring(data)
    elif lower_name.endswith(".json"):
        json.loads(data.decode("utf-8"))
    else:
        raise ValueError(f"不支持导出的文件类型: {path.name}")
    return data, hashlib.sha256(data).hexdigest()


def export_current_files(
    source: Path,
    destination_text: str,
    *,
    include_server: bool,
    additional_sources: Iterable[Path] = (),
) -> dict[str, Any]:
    require_repo_write(source)
    downloads = (Path.home() / "Downloads").resolve()
    destination = Path(destination_text).expanduser() if destination_text else _DEFAULT_EXPORT_ROOT
    if not destination.is_absolute():
        destination = downloads / destination
    destination = destination.resolve()
    if destination != downloads and not destination.is_relative_to(downloads):
        raise ValueError("导出目录必须位于 Downloads 内")

    sources = [source]
    if include_server and source.name.lower().endswith(".img"):
        server_path = server_xml_for_client(source)
        if server_path is None or not server_path.is_file():
            target = relative_path(server_path) if server_path is not None else source.name
            raise ValueError(f"找不到对应的服务端 XML: {target}")
        sources.append(server_path)

    sources.extend(additional_sources)

    verified = []
    seen: set[Path] = set()
    for item in sources:
        item = item.resolve()
        require_repo_write(item)
        if not item.is_file():
            raise ValueError(f"关联修改文件不存在: {relative_path(item)}")
        relative = item.relative_to(_ROOT.resolve())
        if not include_server and relative.parts[0] == "gms-server":
            continue
        if item in seen:
            continue
        seen.add(item)
        data, digest = validate_export_source(item)
        verified.append((item, relative, data, digest))

    exported = []
    for item, relative, data, digest in verified:
        target = destination / relative
        overwritten = target.exists()
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(target, data, backup=False)
        target_digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if target_digest != digest:
            raise ValueError(f"导出后哈希不一致: {target}")
        exported.append({
            "source": relative_path(item), "target": str(target), "sha256": digest,
            "size": len(data), "overwritten": overwritten,
        })
    return {"destination": str(destination), "files": exported}


@app.errorhandler(Exception)
def handle_error(exc: Exception):
    status = getattr(exc, "code", 400)
    if not isinstance(status, int) or not 400 <= status <= 599:
        status = 400
    return jsonify({"ok": False, "reason": str(exc)}), status


@app.get("/")
def index():
    return render_template(
        "index.html", tms_data_root=str(_TMS_DATA), default_export_root=str(_DEFAULT_EXPORT_ROOT),
        asset_version=max(
            (_HERE / "static" / "app.js").stat().st_mtime_ns,
            (_HERE / "static" / "app.css").stat().st_mtime_ns,
        ),
    )


@app.get("/api/catalog")
def api_catalog():
    return jsonify({"ok": True, "items": catalog_rows(request.args.get("kind", "map"), request.args.get("q", ""))})


@app.get("/api/mob-sources")
def api_mob_sources():
    return jsonify({"ok": True, **mob_source_options(request.args.get("id", ""))})


@app.get("/api/project-mobs")
def api_project_mobs():
    """列出项目 clien/Data/Mob/ 下的怪物 IMG 文件，供对比选择。"""
    mob_dir = _ROOT / "clien" / "Data" / "Mob"
    q = request.args.get("q", "").strip().lower()
    mobs = []
    if mob_dir.is_dir():
        for f in sorted(mob_dir.iterdir()):
            if not f.name.endswith(".img"):
                continue
            mob_id = f.name.replace(".img", "")
            if not mob_id.isdigit():
                continue
            if q and q not in mob_id:
                continue
            size = f.stat().st_size
            # Try to get name from String.wz
            name = _mob_string_name(mob_id)
            mobs.append({"id": mob_id, "path": relative_path(f), "size": size, "name": name})
    return jsonify({"ok": True, "mobs": mobs[:200]})


def _mob_string_name(mob_id: str) -> str:
    """从 String.wz/Mob.img.xml 获取怪物名称。"""
    try:
        string_path = _ROOT / "gms-server" / "wz" / "String.wz" / "Mob.img.xml"
        if not string_path.is_file():
            string_path = _ROOT / "gms-server" / "wz-zh-CN" / "String.wz" / "Mob.img.xml"
        if not string_path.is_file():
            return ""
        import xml.etree.ElementTree as ET
        tree = ET.parse(string_path)
        for imgdir in tree.getroot().findall(f".//imgdir[@name='{mob_id}']"):
            name_node = imgdir.find(".//string[@name='name']")
            if name_node is not None:
                return name_node.get("value", "")
    except Exception:
        pass
    return ""


@app.get("/api/files")
def api_files():
    return jsonify({"ok": True, **browse_directory(request.args.get("path", ""))})


@app.post("/api/export")
def api_export():
    body = request.get_json(silent=True) or {}
    source = resolve_repo_path(str(body.get("sourcePath", "")))
    additional_files = body.get("additionalFiles", [])
    if not isinstance(additional_files, list) or not all(
        isinstance(item, str) and item.strip() for item in additional_files
    ):
        raise ValueError("关联修改文件必须是路径列表")
    additional_sources = [resolve_repo_path(item, must_exist=False) for item in additional_files]
    with _WRITE_LOCK:
        result = export_current_files(
            source, str(body.get("destination", "")), include_server=bool(body.get("includeServer", True)),
            additional_sources=additional_sources,
        )
    return jsonify({"ok": True, **result})


@app.post("/api/compare")
def api_compare():
    body = request.get_json(silent=True) or {}
    kind = str(body.get("kind", "map"))
    left_path = resolve_repo_path(str(body.get("leftPath", "")), must_exist=False)
    right_path = resolve_repo_path(str(body.get("rightPath", "")), must_exist=False)
    left, left_info = flatten_optional_source(left_path)
    right, right_info = flatten_optional_source(right_path)
    if not left_info["exists"] and not right_info["exists"]:
        raise ValueError("A 与 B 文件都不存在，无法加载")
    nodes, counts = merge_sources(left, right)
    mode = "map" if kind == "map" else "boss"
    compatibility = compatibility_analysis(left, right, left_path, right_path) if mode == "map" else None
    annotate_rows(nodes, mode, infer_id(left_path))
    if compatibility:
        attach_resource_statuses(nodes, compatibility["resources"])
    return jsonify({
        "ok": True, "leftPath": relative_path(left_path), "rightPath": relative_path(right_path),
        "leftInfo": left_info, "rightInfo": right_info, "nodes": nodes, "counts": counts, "compatibility": compatibility,
    })


@app.get("/api/server-control-help")
def api_server_control_help():
    path = str(request.args.get("path") or "skill2")
    mob_id = str(request.args.get("mobId") or "")
    return jsonify({"ok": True, **server_control_help.help_for(path, [], mob_id)})


@app.get("/api/mob-skill-resolve")
def api_mob_skill_resolve():
    skill_id = request.args.get("skillId", type=int)
    level = request.args.get("level", type=int)
    action = request.args.get("action", type=int)
    tms_skill_id = request.args.get("tmsSkillId", type=int)
    mob_id = str(request.args.get("mobId") or "")
    intercept = str(request.args.get("intercept") or "").lower() in {"1", "true"}
    return jsonify({"ok": True, **mob_skill_resolve.mapping_card(
        skill_id, level, action,
        tms_skill_id=tms_skill_id, intercept=intercept, mob_id=mob_id,
    )})


@app.post("/api/create-main")
def api_create_main():
    body = request.get_json(silent=True) or {}
    path = resolve_repo_path(str(body.get("sourcePath", "")), must_exist=False)
    with _WRITE_LOCK:
        result = create_empty_main_files(path)
    return jsonify({"ok": True, **result})


@app.post("/api/copy-tms-node")
def api_copy_tms_node():
    body = request.get_json(silent=True) or {}
    client_path = resolve_repo_path(str(body.get("sourcePath", "")), must_exist=False)
    tms_path = resolve_repo_path(str(body.get("tmsPath", "")))
    if tms_path != _TMS_DATA and not tms_path.is_relative_to(_TMS_DATA):
        raise ValueError("复制来源必须位于 TMS 数据目录")
    node_path = str(body.get("path", "")).strip("/")
    with _WRITE_LOCK:
        result = copy_tms_node_with_server_sync(client_path, tms_path, node_path)
    return jsonify({"ok": True, **result})


@app.post("/api/migrate-mob-action")
def api_migrate_mob_action():
    body = request.get_json(silent=True) or {}
    client_path = resolve_repo_path(str(body.get("sourcePath", "")))
    tms_path = resolve_repo_path(str(body.get("tmsPath", "")))
    require_mob_action_source(tms_path)
    action_name = str(body.get("action", "")).strip()
    with _WRITE_LOCK:
        result = migrate_mob_action_with_server_sync(client_path, tms_path, action_name)
    return jsonify({"ok": True, **result})


@app.post("/api/copy-mob-frame")
def api_copy_mob_frame():
    """把单帧的真实像素复制到项目怪物 IMG（增量记录替换，不动其他帧）。"""
    body = request.get_json(silent=True) or {}
    source_path = resolve_repo_path(str(body.get("sourcePath", "")))
    target_path = resolve_repo_path(str(body.get("targetPath", "")))
    frame_path = str(body.get("sourceFramePath", "")).strip("/")
    action_name = str(body.get("actionName", "")).strip()
    frame_index = int(body.get("frameIndex", 0))
    if not frame_path or not action_name:
        raise ValueError("缺少 sourceFramePath 或 actionName")
    with _WRITE_LOCK:
        result = copy_mob_frame_with_server_sync(
            target_path, source_path, frame_path, action_name, frame_index,
            dry_run=bool(body.get("dryRun", False)),
            allow_blank=bool(body.get("allowBlank", False)),
            sync_server=bool(body.get("syncServer", True)),
        )
    return jsonify({"ok": True, **result})


@app.post("/api/canvas-reference")
def api_canvas_reference():
    """解析单个帧/Canvas 节点的真实资源来源（只读）。"""
    body = request.get_json(silent=True) or {}
    source_path = resolve_repo_path(str(body.get("sourcePath", "")))
    node_path = str(body.get("path", "")).strip("/")
    if not node_path:
        return jsonify({"ok": False, "error": "缺少 path"}), 400
    if not source_path.is_file():
        return jsonify({"ok": False, "error": f"文件不存在: {relative_path(source_path)}"}), 404
    report = canvas_reference(source_path, node_path)
    return jsonify({
        "ok": True,
        "sourcePath": relative_path(source_path),
        "summary": canvas_reference_summary(report),
        **report,
    })


@app.post("/api/mob-resource-manifest")
def api_mob_resource_manifest():
    """列出该怪物 IMG 全部帧的真实资源清单（TMS 占位帧的像素在哪）。"""
    body = request.get_json(silent=True) or {}
    source_path = resolve_repo_path(str(body.get("sourcePath", "")))
    if not source_path.is_file():
        return jsonify({"ok": False, "error": f"文件不存在: {relative_path(source_path)}"}), 404
    if source_path.suffix.lower() != ".img":
        return jsonify({"ok": False, "error": "真实资源清单只支持 .img"}), 400
    node_path = str(body.get("path", "")).strip("/")
    result = mob_resource_manifest(load_image(source_path), source_path, node_path)
    return jsonify({"ok": True, **result})


def require_mob_action_source(path: Path) -> None:
    allowed_roots = (
        (_TMS_DATA / "Mob").resolve(),
        *(_ms_extract_roots()),
    )
    resolved = path.resolve()
    if not any(resolved == root.resolve() or resolved.is_relative_to(root.resolve()) for root in allowed_roots):
        raise ValueError("动作迁移来源必须是 TMS Mob IMG 或已提取的 Mob MS 记录")


@app.post("/api/mob-action-plan")
def api_mob_action_plan():
    body = request.get_json(silent=True) or {}
    client_path = resolve_repo_path(str(body.get("sourcePath", "")))
    tms_path = resolve_repo_path(str(body.get("tmsPath", "")))
    require_mob_action_source(tms_path)
    action_name = str(body.get("action", "")).strip()
    try:
        with _WRITE_LOCK:
            result = migrate_mob_action_with_server_sync(
                client_path, tms_path, action_name, dry_run=True,
            )
    except (ValueError, RuntimeError) as exc:
        return jsonify({"ok": True, "allowed": False, "action": action_name, "reason": str(exc)})
    return jsonify({"ok": True, "allowed": True, "action": action_name, "plan": result})


@app.post("/api/preview")
def api_preview():
    body = request.get_json(silent=True) or {}
    kind = str(body.get("kind", "map"))
    source = resolve_repo_path(str(body.get("sourcePath", "")))
    if not source.name.lower().endswith(".img"):
        if kind == "mob":
            return jsonify({"ok": True, "sourcePath": relative_path(source), **mob_xml_preview(source)})
        client, _ = default_paths(kind, infer_id(source))
        source = resolve_repo_path(relative_path(client))
    payload = map_preview(source) if kind == "map" else mob_preview(source)
    return jsonify({"ok": True, "sourcePath": relative_path(source), **payload})


@app.post("/api/child-frames")
def api_child_frames():
    """返回指定节点的子节点列表（用于动作/技能的帧详情展示）。"""
    body = request.get_json(silent=True) or {}
    source_path = resolve_repo_path(str(body.get("sourcePath", "")))
    node_path = str(body.get("path", "")).strip("/")
    if not node_path:
        return jsonify({"ok": False, "error": "缺少 path"}), 400
    image = load_image(source_path)
    node = image.root.get(node_path)
    if node is None:
        return jsonify({"ok": False, "error": f"节点不存在: {node_path}"}), 404
    children = []
    if isinstance(node, WzSubProperty):
        for child in sorted(node.children(), key=lambda n: natural_key(n.name)):
            desc = {
                "name": child.name,
                "type": child.type_name.lower(),
                "path": f"{node_path}/{child.name}",
                "meaning": _mob_node_meaning(child.name, node_path, child),
            }
            if isinstance(child, (WzCanvasProperty, WzUolProperty)):
                report = canvas_reference(source_path, f"{node_path}/{child.name}")
                resolved = report["resolved"]
                # 真实像素尺寸优先：TMS 的帧常常声明成 1×1 占位，真实图在别的文件里。
                desc["width"] = (
                    int(resolved["width"]) if resolved is not None
                    else int(report["declaredWidth"] or 0)
                )
                desc["height"] = (
                    int(resolved["height"]) if resolved is not None
                    else int(report["declaredHeight"] or 0)
                )
                desc["declaredWidth"] = report["declaredWidth"]
                desc["declaredHeight"] = report["declaredHeight"]
                desc["state"] = report["state"]
                desc["placeholder"] = report["placeholder"]
                desc["linkKind"] = report["linkKind"]
                desc["linkRaw"] = report["linkRaw"]
                desc["crossMob"] = report["crossMob"]
                desc["resolved"] = resolved
                desc["summary"] = canvas_reference_summary(report)
                desc["error"] = report["error"]
                desc["isPlaceholder"] = report["placeholder"]
                if isinstance(child, WzUolProperty):
                    desc["value"] = str(child.value)
                if isinstance(child, WzCanvasProperty):
                    desc["format"] = int(child.format)
                    origin = child.child("origin")
                    if isinstance(origin, WzVectorProperty):
                        desc["origin"] = {"x": int(origin.x), "y": int(origin.y)}
                    delay = child_value(child, "delay")
                    if delay is not None:
                        desc["delay"] = int(delay)
                if resolved is not None:
                    desc["url"] = (
                        f"/api/canvas?file={quote(relative_path(source_path))}"
                        f"&path={quote(f'{node_path}/{child.name}')}"
                    )
            elif isinstance(child, WzSubProperty):
                desc["childCount"] = len(list(child.children()))
                # Recursively collect sub-children names for info-like nodes
                if child.name == "info":
                    sub_fields = []
                    for sub in child.children():
                        try:
                            sub_fields.append({"name": sub.name, "type": sub.type_name.lower(), "value": sub.value if not isinstance(sub, WzSubProperty) else None})
                        except Exception:
                            sub_fields.append({"name": sub.name, "type": sub.type_name.lower()})
                    desc["subFields"] = sub_fields
            elif not isinstance(child, WzSubProperty):
                try:
                    desc["value"] = child.value
                except Exception:
                    pass
            children.append(desc)
    if is_mob_canvas_store(source_path):
        overlay_nodes, _ = flatten_img(source_path)
        present = {child["name"] for child in children}
        extras = []
        for path, meta in overlay_nodes.items():
            if _parent_path(path) != node_path:
                continue
            name = str(meta.get("name") or path.rsplit("/", 1)[-1])
            if name in present:
                continue
            extras.append({
                "name": name,
                "type": str(meta.get("type") or "gap").lower(),
                "path": path,
                "meaning": (
                    server_control_help.action_frame_meaning(
                        node_path.split("/")[0],
                        name,
                        value=str(meta.get("value") or ""),
                        outlink=str(meta.get("_outlink") or ""),
                    )
                    or "Canvas 像素库未收录该帧；完整逻辑记录里仍有 UOL/_outlink。"
                ),
                "canvasStoreMissing": True,
                "width": meta.get("width"),
                "height": meta.get("height"),
                "value": meta.get("value"),
                "_outlink": meta.get("_outlink"),
                "isPlaceholder": True,
            })
        children.extend(extras)
        children.sort(key=lambda item: natural_key(item["name"]))
    return jsonify({
        "ok": True,
        "nodePath": node_path,
        "nodeType": node.type_name.lower(),
        "childCount": len(children),
        "children": children,
        "playback": list(server_control_help.SKILL2_PLAYBACK) if node_path == "skill2" else [],
    })


# 怪物动作节点含义表
_MOB_NODE_MEANINGS = {
    "info": "动作参数配置",
    "range": "攻击范围（左/右边界 x 坐标）",
    "hit": "命中判定参数（攻击框位置与大小）",
    "lt": "命中框左上角 (left, top)",
    "rb": "命中框右下角 (right, bottom)",
    "attackAfter": "攻击后硬直时间 (ms)，动作结束后等待该时长才可执行下一动作",
    "onlyFsm": "TMS 仅 FSM 触发；旧端不识别。复制时去掉该字段，空 1×1 身体投影为 ../stand/N UOL",
    "mobCount": "召唤怪物数量",
    "mob": "召唤的怪物 ID",
    "type": "攻击类型（0=近身，1=远程，2=魔法）",
    "delay": "帧延迟 (ms)，该帧显示时长",
    "origin": "锚点坐标 (x, y)，用于对齐到怪物脚底",
    "lt": "判定框左上角偏移",
    "rb": "判定框右下角偏移",
    "affect": "是否影响角色",
    "spell": "是否为魔法攻击",
    "fatal": "是否致死攻击",
    "buff": "附加 Buff 参数",
    "area": "攻击区域形状",
    "knockback": "击退距离",
    "mpConsume": "MP 消耗",
    "cooltime": "技能冷却时间 (ms)",
}


def _mob_node_meaning(name: str, parent_path: str, node) -> str:
    """返回怪物 IMG 节点的中文含义说明。"""
    # Direct name match
    if name in _MOB_NODE_MEANINGS:
        return _MOB_NODE_MEANINGS[name]
    # Numeric names = animation frames
    if name.isdigit():
        value = ""
        outlink = ""
        if isinstance(node, WzUolProperty):
            value = str(node.value or "")
        elif isinstance(node, WzCanvasProperty):
            linked = node.child("_outlink")
            if linked is not None:
                outlink = str(getattr(linked, "value", "") or "")
        action = (parent_path or "").split("/")[0] if parent_path else ""
        if parent_path == action:
            explained = server_control_help.action_frame_meaning(
                action, name, value=value, outlink=outlink,
            )
            if explained:
                return explained
        return f"动画帧 #{name}"
    # Common mob action names
    action_names = {
        "stand": "站立", "move": "移动", "fly": "飞行", "jump": "跳跃",
        "hit1": "受击", "die1": "死亡", "die2": "死亡(爆炸)",
        "attack1": "攻击1", "attack2": "攻击2", "attack3": "攻击3",
        "attack4": "攻击4", "attack5": "攻击5", "attack6": "攻击6",
        "skill1": "技能1", "skill2": "技能2", "skill3": "技能3",
        "skill4": "技能4", "skill5": "技能5", "skill6": "技能6",
        "skill7": "技能7", "skill8": "技能8", "skill9": "技能9",
        "skillAfter1": "技能1后摇", "skillAfter2": "技能2后摇",
        "skillAfter3": "技能3后摇", "skillAfter4": "技能4后摇",
    }
    if name in action_names:
        return action_names[name]
    # info sub-fields
    if parent_path.endswith("/info") or "/info/" in parent_path:
        return _MOB_NODE_MEANINGS.get(name, f"info 子属性: {name}")
    # Default
    return ""


@app.post("/api/diagnose-map")
def api_diagnose_map():
    body = request.get_json(silent=True) or {}
    source = resolve_repo_path(str(body.get("sourcePath", "")))
    case_map_ids = body.get("caseMapIds") or []
    if not isinstance(case_map_ids, list):
        raise ValueError("同样崩溃地图必须是地图 ID 列表")
    return jsonify({
        "ok": True,
        **diagnose_map_crash(source, str(body.get("phase", "unknown")), case_map_ids),
    })


@app.get("/api/canvas")
def api_canvas():
    file_path = resolve_repo_path(request.args.get("file", ""))
    image = load_image(file_path)
    resolved_image, canvas, resolved_path = resolve_canvas_node(image, request.args.get("path", ""), file_path)
    stat = resolved_path.stat()
    png = decode_canvas(canvas, region=canvas_region(str(resolved_path), stat.st_mtime_ns, stat.st_size))
    buffer = io.BytesIO()
    png.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png", max_age=3600)


@app.get("/api/video")
def api_video():
    file_path = resolve_repo_path(request.args.get("file", ""))
    image = load_image(file_path)
    node_path = request.args.get("path", "").strip("/")
    node = image.root.get(node_path)
    if not isinstance(node, WzVideoProperty):
        return jsonify({"ok": False, "error": "节点不是 Video 类型"}), 400
    # 提取视频数据
    data = node._data
    if data is None and node._wz_image is not None and node._data_length > 0:
        with node._wz_image.wz_file.reader_lock:
            reader = node._wz_image.wz_file.reader
            previous = reader.position
            reader.seek(node._data_offset)
            data = reader.read(node._data_length)
            reader.seek(previous)
    if not data:
        return jsonify({"ok": False, "error": "无视频数据"}), 404
    buffer = io.BytesIO(data)
    buffer.seek(0)
    return send_file(buffer, mimetype="video/ivf", max_age=3600)


_MCV_DIR = _ROOT / "clien" / "Data" / "Video"
_EFFECT_IMG = _ROOT / "clien" / "Data" / "Map" / "Effect.img"
# Boss/category Chinese labels
_BOSS_CN = {
    "deathFault": "戴斯Fault",
    "dawnWarrior": "魂骑士",
    "blazeWizard": "炎术士",
    "nightWalker": "夜行者",
    "windArcher": "风灵使者",
    "thunderBreaker": "奇袭者",
    "hero": "英雄",
    "paladin": "圣骑士",
    "darkKnight": "黑骑士",
    "fpArchMage": "火毒主教",
    "ilArchMage": "冰雷主教",
    "bishop": "主教",
    "bowmaster": "弓箭手",
    "marksman": "弩弓手",
    "nightLord": "隐士",
    "shadower": "侠盗",
    "buccaneer": "冲锋队长",
    "corsair": "船长",
    "karing": "卡琳",
    "lucid": "路西德",
    "rootAbyss": "根源深渊",
    "demian": "戴米安",
    "will": "威尔",
    "magnus": "玛格努斯",
    "seren": "塞莲",
    "akayrum": "阿卡伊伦",
}


@app.get("/api/mcv-catalog")
def api_mcv_catalog():
    """扫描 Effect.img 中所有 Boss 相关段（customSkill/customBoss*），列出 MCV 视频层引用。"""
    import re as _re
    try:
        image = load_image(_EFFECT_IMG)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    # Build a lookup of existing .mcv files by stem
    mcv_files = {}
    if _MCV_DIR.is_dir():
        for f in _MCV_DIR.iterdir():
            if f.suffix.lower() == ".mcv":
                mcv_files[f.stem.lower()] = f.name

    def camel_to_kebab(s):
        k = ""
        for ch in s:
            if ch.isupper():
                k += ("-" if k else "") + ch.lower()
            else:
                k += ch
        return k

    def match_mcv(layer_name, boss_name, section_key=""):
        candidates = []
        stem = layer_name.replace("VideoLayer", "").replace("video", "")
        kebab = camel_to_kebab(stem)
        # For numeric layer names in boss sections, also try matching by boss name
        if stem.isdigit() and boss_name:
            boss_stem = boss_name.replace("VideoLayer", "").replace("video", "")
            boss_kebab = camel_to_kebab(boss_stem)
            candidates.append(boss_kebab)
            candidates.append(boss_stem.lower())
        candidates.append(kebab)
        candidates.append(stem.lower())
        if stem and stem[0] in "2345":
            candidates.append(f"explorer-{stem}")
        candidates.append(f"{boss_name.lower()}-{kebab}")
        num_match = _re.match(r"^(.+?)(\d+)$", kebab)
        if num_match:
            base, num = num_match.group(1), num_match.group(2)
            candidates.append(f"{boss_name.lower()}-{base}-{num}")
            candidates.append(f"{base}-{num}")
        if boss_name == "windArcher" and "monsoon" in kebab:
            candidates.append("monsoon-vi")
        if boss_name == "rootAbyss":
            candidates.append(f"root-abyss-{kebab}")
            candidates.append(f"root-abyss-{kebab.replace('-', '')}")
        if "Demian" in section_key:
            candidates.append(f"damien-{kebab}")
            candidates.append(kebab)
            # groundBurst -> damien-ground (not damien-ground-burst)
            if num_match:
                candidates.append(f"damien-{num_match.group(1)}")
            candidates.append(f"damien-{stem.lower()}")
            # Also try the boss name for numeric layers
            if stem.isdigit() and boss_name:
                boss_kebab = camel_to_kebab(boss_name)
                candidates.append(f"damien-{boss_kebab}")
                candidates.append(f"damien-{boss_name.lower()}")
                # groundBurst -> damien-ground
                boss_num = _re.match(r"^(.+?)(\d+)$", boss_kebab)
                if boss_num:
                    candidates.append(f"damien-{boss_num.group(1)}")
                # groundBurst -> also try damien-ground (strip suffix words)
                parts = boss_kebab.split("-")
                if len(parts) > 1:
                    candidates.append(f"damien-{parts[0]}")
        for cand in candidates:
            if cand in mcv_files:
                return mcv_files[cand]
        return None

    def scan_section(section_node, section_key):
        result = []
        for boss_node in section_node.children():
            boss_name = boss_node.name
            boss_cn = _BOSS_CN.get(boss_name, boss_name)
            if boss_cn == boss_name and section_key.startswith("customBoss") and section_key != "customSkill":
                boss_cn = _BOSS_CN.get(section_key.replace("customBoss", "").lower(), boss_name)
            layers = []
            for layer_node in boss_node.children():
                layer_name = layer_node.name
                matched_mcv = match_mcv(layer_name, boss_name, section_key)
                child_count = 0
                has_canvas = False
                for c in layer_node.children():
                    child_count += 1
                    has_canvas = has_canvas or (c.type_name == "Canvas")
                layers.append({
                    "name": layer_name,
                    "path": f"{section_key}/{boss_name}/{layer_name}",
                    "mcvFile": matched_mcv,
                    "childCount": child_count,
                    "hasCanvas": has_canvas,
                })
            if layers:
                result.append({
                    "name": boss_name,
                    "label": boss_cn,
                    "section": section_key,
                    "layers": layers,
                })
        return result

    bosses = []
    custom_skill = image.root.child("customSkill")
    if custom_skill:
        bosses.extend(scan_section(custom_skill, "customSkill"))
    for child in image.root.children():
        if child.name.startswith("customBoss") and child.name != "customSkill":
            bosses.extend(scan_section(child, child.name))
    return jsonify({"ok": True, "bosses": bosses})


@app.get("/api/mcv-file")
def api_mcv_file():
    """将 .mcv 转换为 WebM 供浏览器播放（经 IVF → ffmpeg → WebM）。"""
    import shutil as _shutil
    name = request.args.get("name", "").strip()
    if not name or "/" in name or "\\" in name or ".." in name:
        return jsonify({"ok": False, "error": "无效文件名"}), 400
    path = _MCV_DIR / name
    if not path.is_file():
        return jsonify({"ok": False, "error": f"文件不存在: {name}"}), 404
    ffmpeg = _shutil.which("ffmpeg")
    if not ffmpeg:
        return jsonify({"ok": False, "error": "ffmpeg 未安装"}), 500
    try:
        ivf_data = _convert_mcv_to_ivf(path)
    except Exception as exc:
        return jsonify({"ok": False, "error": f"MCV 解析失败: {exc}"}), 500
    # Write IVF to temp file, convert with ffmpeg to WebM
    try:
        with tempfile.NamedTemporaryFile(suffix=".ivf", delete=False) as tmp_ivf:
            tmp_ivf.write(ivf_data)
            tmp_ivf_path = tmp_ivf.name
        tmp_webm_path = tmp_ivf_path.replace(".ivf", ".webm")
        proc = subprocess.run(
            [ffmpeg, "-v", "error",
             "-i", tmp_ivf_path,
             "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "30",
             "-deadline", "realtime", "-cpu-used", "8",
             "-f", "webm", "-y", tmp_webm_path],
            capture_output=True, timeout=30,
        )
        Path(tmp_ivf_path).unlink(missing_ok=True)
        if proc.returncode != 0:
            Path(tmp_webm_path).unlink(missing_ok=True)
            raise RuntimeError(proc.stderr.decode(errors="replace")[:200])
        webm_data = Path(tmp_webm_path).read_bytes()
        Path(tmp_webm_path).unlink(missing_ok=True)
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "ffmpeg 转码超时"}), 500
    except Exception as exc:
        return jsonify({"ok": False, "error": f"WebM 转码失败: {exc}"}), 500
    buffer = io.BytesIO(webm_data)
    buffer.seek(0)
    return send_file(buffer, mimetype="video/webm", max_age=3600)



@app.get("/api/mcv-info")
def api_mcv_info():
    """返回 MCV 文件的详细信息（帧数、时长、每帧延迟、Effect.img 引用等）。"""
    name = request.args.get("name", "").strip()
    if not name or "/" in name or "\\" in name or ".." in name:
        return jsonify({"ok": False, "error": "无效文件名"}), 400
    path = _MCV_DIR / name
    if not path.is_file():
        return jsonify({"ok": False, "error": f"文件不存在: {name}"}), 404
    data = path.read_bytes()
    if len(data) < 36 or data[:4] != b"MCV0":
        return jsonify({"ok": False, "error": "不是有效的 MCV 文件"}), 400
    encoded_fourcc = struct.unpack_from("<I", data, 8)[0]
    width = struct.unpack_from("<H", data, 12)[0]
    height = struct.unpack_from("<H", data, 14)[0]
    frame_count = struct.unpack_from("<I", data, 16)[0]
    decoded_fourcc = encoded_fourcc ^ _MCV_FOURCC_XOR
    color_table_start = 36
    alpha_table_start = color_table_start + frame_count * 8
    delay_table_start = alpha_table_start + frame_count * 8
    payload_start = delay_table_start + frame_count * 4
    color_entries = []
    for i in range(frame_count):
        off = struct.unpack_from("<I", data, color_table_start + i * 8)[0]
        sz = struct.unpack_from("<I", data, color_table_start + i * 8 + 4)[0]
        color_entries.append({"offset": off, "size": sz})
    alpha_entries = []
    for i in range(frame_count):
        off = struct.unpack_from("<I", data, alpha_table_start + i * 8)[0]
        sz = struct.unpack_from("<I", data, alpha_table_start + i * 8 + 4)[0]
        alpha_entries.append({"offset": off, "size": sz})
    delays = []
    total_ms = 0
    for i in range(frame_count):
        d = struct.unpack_from("<I", data, delay_table_start + i * 4)[0]
        delays.append(d)
        total_ms += d
    effect_refs = _find_mcv_effect_refs(name)
    return jsonify({
        "ok": True,
        "name": name,
        "fileSize": len(data),
        "fourcc": struct.pack("<I", decoded_fourcc).decode(errors="replace"),
        "width": width,
        "height": height,
        "frameCount": frame_count,
        "totalDurationMs": total_ms,
        "totalDurationSec": round(total_ms / 1000, 2),
        "payloadStart": payload_start,
        "frames": [
            {"index": i, "delayMs": delays[i], "colorSize": color_entries[i]["size"], "alphaSize": alpha_entries[i]["size"]}
            for i in range(frame_count)
        ],
        "effectRefs": effect_refs,
    })


def _find_mcv_effect_refs(mcv_name: str) -> list[dict]:
    """在 Effect.img 中查找引用指定 MCV 文件的视频层。"""
    try:
        image = load_image(_EFFECT_IMG)
    except Exception:
        return []
    stem = mcv_name.replace(".mcv", "").lower()
    refs = []
    for child in image.root.children():
        if not child.name.startswith("custom"):
            continue
        if not isinstance(child, WzSubProperty):
            continue
        for boss in child.children():
            for layer in boss.children():
                layer_lower = layer.name.lower()
                match = (stem in layer_lower
                         or layer_lower.replace("videolayer", "").replace("video", "") in stem
                         or layer_lower.replace("videolayer", "").replace("video", "") == stem.replace("-", "").replace(boss.name.lower(), ""))
                if not match:
                    continue
                marker = layer.child("0")
                ref = {
                    "section": child.name,
                    "boss": boss.name,
                    "layer": layer.name,
                    "path": f"{child.name}/{boss.name}/{layer.name}",
                }
                if isinstance(marker, WzCanvasProperty):
                    ref["markerWidth"] = int(marker.width)
                    ref["markerHeight"] = int(marker.height)
                    origin = marker.child("origin")
                    if isinstance(origin, WzVectorProperty):
                        ref["originX"] = int(origin.x)
                        ref["originY"] = int(origin.y)
                    delay = marker.child("delay")
                    if isinstance(delay, WzIntProperty):
                        ref["markerDelay"] = int(delay.value)
                refs.append(ref)
    return refs


@app.get("/api/mcv-frame")
def api_mcv_frame():
    """提取 MCV 指定帧为 PNG 图片（用于预览）。"""
    import shutil as _shutil
    name = request.args.get("name", "").strip()
    frame_idx = request.args.get("frame", "0")
    if not name or "/" in name or "\\" in name or ".." in name:
        return jsonify({"ok": False, "error": "无效文件名"}), 400
    try:
        frame_idx = int(frame_idx)
    except (TypeError, ValueError):
        frame_idx = 0
    path = _MCV_DIR / name
    if not path.is_file():
        return jsonify({"ok": False, "error": f"文件不存在: {name}"}), 404
    ffmpeg = _shutil.which("ffmpeg")
    if not ffmpeg:
        return jsonify({"ok": False, "error": "ffmpeg 未安装"}), 500
    try:
        ivf_data = _convert_mcv_to_ivf(path)
    except Exception as exc:
        return jsonify({"ok": False, "error": f"MCV 解析失败: {exc}"}), 500
    with tempfile.NamedTemporaryFile(suffix=".ivf", delete=False) as tmp:
        tmp.write(ivf_data)
        tmp_path = tmp.name
    png_path = tmp_path.replace(".ivf", ".png")
    try:
        proc = subprocess.run(
            [ffmpeg, "-v", "error",
             "-i", tmp_path,
             "-vf", f"select=eq(n\\,{frame_idx})",
             "-frames:v", "1", "-pix_fmt", "rgba",
             "-y", png_path],
            capture_output=True, timeout=10,
        )
        Path(tmp_path).unlink(missing_ok=True)
        if proc.returncode != 0 or not Path(png_path).exists():
            raise RuntimeError("帧提取失败")
        return send_file(png_path, mimetype="image/png", max_age=3600)
    except Exception as exc:
        Path(tmp_path).unlink(missing_ok=True)
        Path(png_path).unlink(missing_ok=True)
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/mcv-update-delays")
def api_mcv_update_delays():
    """更新 MCV 文件的帧延迟（不重新编码视频数据）。"""
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    delays = body.get("delays")  # list of int
    if not name or "/" in name or "\\" in name:
        return jsonify({"ok": False, "error": "无效文件名"}), 400
    if not isinstance(delays, list) or not all(isinstance(d, int) and d > 0 for d in delays):
        return jsonify({"ok": False, "error": "delays 必须是正整数列表"}), 400
    path = _MCV_DIR / name
    if not path.is_file():
        return jsonify({"ok": False, "error": f"文件不存在: {name}"}), 404
    data = path.read_bytes()
    if len(data) < 36 or data[:4] != b"MCV0":
        return jsonify({"ok": False, "error": "不是有效的 MCV 文件"}), 400
    frame_count = struct.unpack_from("<I", data, 16)[0]
    if len(delays) != frame_count:
        return jsonify({"ok": False, "error": f"延迟数量 ({len(delays)}) 与帧数 ({frame_count}) 不匹配"}), 400
    # Calculate delay table offset
    color_table_start = 36
    alpha_table_start = color_table_start + frame_count * 8
    delay_table_start = alpha_table_start + frame_count * 8
    # Backup
    backup_path = path.with_suffix(".mcv.bak")
    if not backup_path.exists():
        backup_path.write_bytes(data)
    # Patch delays in-place
    data = bytearray(data)
    for i, d in enumerate(delays):
        struct.pack_into("<I", data, delay_table_start + i * 4, d)
    path.write_bytes(bytes(data))
    total_ms = sum(delays)
    return jsonify({"ok": True, "name": name, "totalDurationMs": total_ms, "totalDurationSec": round(total_ms / 1000, 2)})


@app.get("/api/mcv-export-frames")
def api_mcv_export_frames():
    """导出 MCV 的所有 color 帧为 PNG 序列（返回 zip）。"""
    import io, zipfile
    name = request.args.get("name", "").strip()
    if not name or "/" in name or "\\" in name or ".." in name:
        return jsonify({"ok": False, "error": "无效文件名"}), 400
    path = _MCV_DIR / name
    if not path.is_file():
        return jsonify({"ok": False, "error": f"文件不存在: {name}"}), 404
    # Parse MCV and extract color VP9 packets
    ivf_data = _convert_mcv_to_ivf(path)
    # Use ffmpeg to extract frames to PNG
    import shutil as _shutil
    ffmpeg = _shutil.which("ffmpeg")
    if not ffmpeg:
        return jsonify({"ok": False, "error": "ffmpeg 未安装"}), 500
    stem = name.replace(".mcv", "")
    with tempfile.TemporaryDirectory() as tmpdir:
        ivf_path = Path(tmpdir) / "input.ivf"
        ivf_path.write_bytes(ivf_data)
        subprocess.run(
            [ffmpeg, "-v", "error", "-i", str(ivf_path),
             "-pix_fmt", "rgba", "-y", str(Path(tmpdir) / "frame_%04d.png")],
            capture_output=True, timeout=60,
        )
        # Build zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for png_file in sorted(Path(tmpdir).glob("frame_*.png")):
                zf.write(png_file, f"{stem}/{png_file.name}")
        zip_buffer.seek(0)
    return send_file(zip_buffer, mimetype="application/zip",
                     as_attachment=True, download_name=f"{stem}_frames.zip")


@app.post("/api/mcv-replace")
def api_mcv_replace():
    """用上传的 WebM/MP4 视频替换现有 MCV 文件（经 ffmpeg → IVF → MCV 打包）。"""
    import shutil as _shutil
    ffmpeg = _shutil.which("ffmpeg")
    if not ffmpeg:
        return jsonify({"ok": False, "error": "ffmpeg 未安装"}), 500
    name = request.form.get("name", "").strip()
    if not name or "/" in name or "\\" in name or ".." in name:
        return jsonify({"ok": False, "error": "无效文件名"}), 400
    target_path = _MCV_DIR / name
    if not target_path.is_file():
        return jsonify({"ok": False, "error": f"目标文件不存在: {name}"}), 404
    # Get uploaded file
    upload = request.files.get("file")
    if not upload:
        return jsonify({"ok": False, "error": "未上传文件"}), 400
    # Read original MCV header to get dimensions
    orig_data = target_path.read_bytes()
    orig_width = struct.unpack_from("<H", orig_data, 12)[0]
    orig_height = struct.unpack_from("<H", orig_data, 14)[0]
    with tempfile.TemporaryDirectory() as tmpdir:
        upload_path = Path(tmpdir) / upload.filename
        upload.save(str(upload_path))
        # Convert to IVF with VP9
        ivf_path = Path(tmpdir) / "output.ivf"
        proc = subprocess.run(
            [ffmpeg, "-v", "error", "-i", str(upload_path),
             "-vf", f"scale={orig_width}:{orig_height}",
             "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "20",
             "-deadline", "good", "-cpu-used", "4",
             "-f", "ivf", "-y", str(ivf_path)],
            capture_output=True, timeout=120,
        )
        if proc.returncode != 0:
            return jsonify({"ok": False, "error": f"ffmpeg 转码失败: {proc.stderr.decode(errors='replace')[:200]}"}), 500
        # Read IVF and pack into MCV
        ivf_bytes = ivf_path.read_bytes()
        if len(ivf_bytes) < 32 or ivf_bytes[:4] != b"DKIF":
            return jsonify({"ok": False, "error": "ffmpeg 输出的 IVF 无效"}), 500
        # Parse IVF packets
        ivf_hdr_size = struct.unpack_from("<H", ivf_bytes, 6)[0]
        ivf_frame_count = struct.unpack_from("<I", ivf_bytes, 24)[0]
        ivf_tb_num = struct.unpack_from("<I", ivf_bytes, 20)[0]
        ivf_tb_den = struct.unpack_from("<I", ivf_bytes, 16)[0]
        packets = []
        pos = ivf_hdr_size
        for _ in range(ivf_frame_count):
            if pos + 12 > len(ivf_bytes):
                break
            pkt_size = struct.unpack_from("<I", ivf_bytes, pos)[0]
            pkt = ivf_bytes[pos + 12:pos + 12 + pkt_size]
            packets.append(pkt)
            pos += 12 + pkt_size
        if not packets:
            return jsonify({"ok": False, "error": "IVF 中无有效帧"}), 500
        # Calculate delays from IVF timebase
        delays = []
        for i in range(len(packets)):
            d = max(16, int(ivf_tb_num / max(ivf_tb_den, 1) * 1000)) if ivf_tb_den else 33
            delays.append(d)
        # Pack into MCV format
        encoded_fourcc = struct.unpack("<I", b"VP90")[0] ^ _MCV_FOURCC_XOR
        mcv_header = struct.pack(
            "<4sHHIHHIB3xQI",
            b"MCV0", 0, 36, encoded_fourcc,
            orig_width, orig_height, len(packets), 3, 1_000_000, 0,
        )
        color_offsets = []
        offset = 0
        for pkt in packets:
            color_offsets.append(offset)
            offset += len(pkt)
        # Alpha is empty (same packets for simplicity)
        alpha_offsets = [offset] * len(packets)
        mcv_body = b""
        for off, pkt in zip(color_offsets, packets):
            mcv_body += struct.pack("<II", off, len(pkt))
        for off in alpha_offsets:
            mcv_body += struct.pack("<II", off, 0)
        for d in delays:
            mcv_body += struct.pack("<I", d)
        for pkt in packets:
            mcv_body += pkt
        # Backup and write
        backup_path = target_path.with_suffix(".mcv.bak")
        if not backup_path.exists():
            backup_path.write_bytes(orig_data)
        target_path.write_bytes(mcv_header + mcv_body)
    return jsonify({
        "ok": True,
        "name": name,
        "frameCount": len(packets),
        "totalDurationMs": sum(delays),
    })


_MCV_FOURCC_XOR = 0xA5A5A5A5


def _convert_mcv_to_ivf(path: Path) -> bytes:
    """解析 MCV 文件，提取 color VP9 流，包装为标准 IVF 容器。

    MCV 格式 (来自 export_soul_eclipse_mcv.py write_mcv):
      [0-35]    Header (36 bytes): MCV0 + XOR'd fourcc + w/h/count + timebase
      [36..]    Color offset table: frame_count × (cum_offset:u32, size:u32)
      [...]     Alpha offset table: frame_count × (cum_offset:u32, size:u32)
      [...]     Delay table: frame_count × delay_ms:u32
      [...]     Payload: all color VP9 packets + all alpha VP9 packets
    """
    data = path.read_bytes()
    if len(data) < 36 or data[:4] != b"MCV0":
        raise ValueError("不是有效的 MCV 文件")

    encoded_fourcc = struct.unpack_from("<I", data, 8)[0]
    width = struct.unpack_from("<H", data, 12)[0]
    height = struct.unpack_from("<H", data, 14)[0]
    frame_count = struct.unpack_from("<I", data, 16)[0]
    decoded_fourcc = encoded_fourcc ^ _MCV_FOURCC_XOR  # VP90

    # Offset table: color (frame_count × 8 bytes) + alpha (frame_count × 8 bytes)
    color_table_start = 36
    alpha_table_start = color_table_start + frame_count * 8
    delay_table_start = alpha_table_start + frame_count * 8
    payload_start = delay_table_start + frame_count * 4

    if payload_start > len(data):
        raise ValueError("MCV 文件截断")

    # Read color offset table (cumulative offsets + sizes)
    color_entries = []
    for i in range(frame_count):
        off = struct.unpack_from("<I", data, color_table_start + i * 8)[0]
        sz = struct.unpack_from("<I", data, color_table_start + i * 8 + 4)[0]
        color_entries.append((off, sz))

    # Read delays for timestamp calculation
    delays = []
    for i in range(frame_count):
        delays.append(struct.unpack_from("<I", data, delay_table_start + i * 4)[0])

    # Extract color VP9 packets with their original frame indices
    color_packets = []  # list of (timestamp_ms, packet_bytes)
    cumulative_ms = 0
    for i, (off, sz) in enumerate(color_entries):
        if sz > 0:
            pkt = data[payload_start + off:payload_start + off + sz]
            color_packets.append((cumulative_ms, pkt))
        if i < len(delays):
            cumulative_ms += delays[i]
        else:
            cumulative_ms += 33

    if not color_packets:
        raise ValueError("MCV 文件中没有有效的 color 数据包")

    # Build standard IVF container
    # IVF timebase: tb_num/tb_den seconds per timestamp unit
    # Our timestamps are in milliseconds, so tb_num=1, tb_den=1000 → 1ms per tick
    ivf_header = struct.pack(
        "<4sHHIHHIIII",
        b"DKIF",
        0,             # version
        32,            # header size
        decoded_fourcc,  # VP90
        width,
        height,
        1000,          # timebase denominator
        1,             # timebase numerator (1ms per tick)
        len(color_packets),
        0,
    )
    frame_data = b""
    for ts, pkt in color_packets:
        frame_data += struct.pack("<IQ", len(pkt), ts) + pkt
    return ivf_header + frame_data


@app.post("/api/edit")
def api_edit():
    body = request.get_json(silent=True) or {}
    path = resolve_repo_path(str(body.get("sourcePath", "")))
    require_repo_write(path)
    node_path = str(body.get("path", "")).strip("/")
    dry_run = bool(body.get("dryRun", False))
    backup = bool(body.get("backup", True))
    sync_server = bool(body.get("syncServer", True))
    with _WRITE_LOCK:
        if path.name.lower().endswith(".img"):
            if sync_server:
                result = patch_with_server_sync(path, node_path, body.get("value"), dry_run=dry_run, backup=backup)
            else:
                result = {"clientPath": relative_path(path), "client": patch_img(
                    path, node_path, body.get("value"), dry_run=dry_run, backup=backup,
                )}
        elif path.name.lower().endswith((".xml", ".img.xml")):
            result = patch_xml_value(path, node_path, body.get("value"), dry_run=dry_run, backup=backup)
        else:
            raise ValueError("JSON 文件当前只读")
    return jsonify({"ok": True, "dryRun": dry_run, "syncServer": sync_server, **result})


@app.post("/api/add")
def api_add():
    body = request.get_json(silent=True) or {}
    path = resolve_repo_path(str(body.get("sourcePath", "")))
    require_repo_write(path)
    if path.suffix.lower() == ".json":
        raise ValueError("JSON 文件当前只读")
    parent_path = str(body.get("parentPath", "")).strip("/")
    name = str(body.get("name", "")).strip()
    node_type = str(body.get("type", "int"))
    value = body.get("value")
    dry_run = bool(body.get("dryRun", False))
    backup = bool(body.get("backup", True))
    sync_server = bool(body.get("syncServer", True))
    with _WRITE_LOCK:
        if path.name.lower().endswith(".img"):
            if sync_server:
                result = add_with_server_sync(
                    path, parent_path, name, node_type, value, dry_run=dry_run, backup=backup,
                )
            else:
                result = {"clientPath": relative_path(path), "client": patch_img_add(
                    path, parent_path, name, node_type, value, dry_run=dry_run, backup=backup,
                )}
        else:
            result = xml_add_node(
                path, parent_path, name, node_type, value, dry_run=dry_run, backup=backup,
            )
    return jsonify({"ok": True, "dryRun": dry_run, "syncServer": sync_server, **result})


@app.post("/api/delete")
def api_delete():
    body = request.get_json(silent=True) or {}
    path = resolve_repo_path(str(body.get("sourcePath", "")))
    require_repo_write(path)
    if path.suffix.lower() == ".json":
        raise ValueError("JSON 文件当前只读")
    node_path = str(body.get("path", "")).strip("/")
    dry_run = bool(body.get("dryRun", False))
    backup = bool(body.get("backup", True))
    sync_server = bool(body.get("syncServer", True))
    with _WRITE_LOCK:
        if path.name.lower().endswith(".img"):
            if sync_server:
                result = delete_with_server_sync(
                    path, node_path, dry_run=dry_run, backup=backup,
                )
            else:
                result = {"clientPath": relative_path(path), "client": patch_img_delete(
                    path, node_path, dry_run=dry_run, backup=backup,
                )}
        else:
            result = xml_delete_node(path, node_path, dry_run=dry_run, backup=backup)
    return jsonify({"ok": True, "dryRun": dry_run, "syncServer": sync_server, **result})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8775)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
