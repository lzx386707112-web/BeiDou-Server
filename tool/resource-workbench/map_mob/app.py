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
from wzpy import (  # noqa: E402
    StaticWzKey,
    WzImage,
    WzKey,
    derive_keystream_from_property,
    detect_region_from_img,
)
from wzpy import writer as wz_writer  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.incremental_img import replace_img_record  # noqa: E402
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
)
from . import compat as map_compat  # noqa: E402
import migrate_arcane_river_expansion as arc  # noqa: E402

app = Flask(__name__)
_WRITE_LOCK = threading.Lock()
_ALLOWED_SUFFIXES = (".img", ".img.xml", ".xml", ".json")
_SCALAR_TYPES = {"short", "int", "long", "float", "double", "string", "uol", "vector"}
_TMS_ROOT = _ROOT.parent / "TMS"
_TMS_DATA = _ROOT.parent / "TMS" / "MapleStory-IMG" / "Data"
_MS_PACKS = _TMS_ROOT / "MapleStory" / "Data" / "Packs"
_MS_PROBE = _TMS_ROOT / "black_mage_report_tools" / "ms_probe" / "bin" / "Debug" / "net8.0" / "MSProbe.dll"
_MS_CACHE_ROOT = Path.home() / "Library" / "Caches" / "BeiDouMapMobWorkbench" / "ms"
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
            tms if tms.is_file() else (
                tms_canvas if tms_canvas.is_file()
                else _ROOT / "gms-server" / "wz" / "Mob.wz" / f"{item_id}.img.xml"
            ),
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
    for pack_text, _mtime_ns, _size in signature:
        pack = Path(pack_text)
        result = subprocess.run(
            [dotnet, str(_MS_PROBE), str(pack), str(_MS_CACHE_ROOT), "--list"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise ValueError(
                f"无法读取 {pack.name}: {result.stderr.strip() or result.stdout.strip()}"
            )
        for line in result.stdout.splitlines():
            match = re.fullmatch(r"Mob/(\d{7})\.img", line.strip(), re.IGNORECASE)
            if match:
                output.setdefault(match.group(1), pack)
    return output


def ms_mob_index() -> dict[str, Path]:
    return _ms_mob_index_cached(ms_pack_signature())


def extract_ms_mob(item_id: str) -> tuple[Path, Path] | None:
    if not re.fullmatch(r"\d{7}", item_id):
        raise ValueError("怪物 ID 必须是 7 位数字")
    pack = ms_mob_index().get(item_id)
    if pack is None:
        return None
    target_dir = _MS_CACHE_ROOT / pack.stem
    target = target_dir / f"Mob_{item_id}.img"
    if target.is_file() and target.stat().st_mtime_ns >= pack.stat().st_mtime_ns:
        load_image(target)
        return target, pack
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
        (source["path"] for source in sources if source["kind"] in {"ms", "img", "canvas"}),
        relative_path(server),
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
    if isinstance(prop, WzSubProperty) and not isinstance(prop, WzCanvasProperty):
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


def flatten_img(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
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

    walk(image.root, "")
    return nodes, {"format": "img", "warnings": [], "truncated": False}


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
            if meta.get("type") == "SubProperty":
                meta["type"] = "imgdir"
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
        if path.resolve().is_relative_to(_MS_CACHE_ROOT.resolve()):
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
            desc = canvas_descriptor(path, property_path(child))
            if desc:
                frames.append({"path": property_path(child), **desc})
        if frames:
            actions.append({"name": action.name, "frames": frames, "duration": sum(frame["delay"] for frame in frames)})
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


def clone_compatible_mob_action(
    source: WzSubProperty, source_image: WzImage, source_path: Path,
) -> tuple[WzSubProperty, arc.CanvasMaterializer]:
    if not _LEGACY_MOB_ACTION.fullmatch(source.name):
        raise ValueError(f"动作名称不属于旧端已知结构: {source.name}")
    materializer = arc.CanvasMaterializer()

    def clone_node(node: WzProperty, parent: WzProperty | None) -> WzProperty:
        if isinstance(node, WzUolProperty) and node.name.isdigit():
            try:
                linked_image, linked_canvas, linked_path = resolve_canvas_node(
                    source_image, property_path(node), source_path,
                )
            except ValueError:
                pass
            else:
                return arc.clone_property(
                    linked_canvas, parent, linked_image, linked_path, materializer, node.name,
                )
        if isinstance(node, WzCanvasProperty):
            return arc.clone_property(node, parent, source_image, source_path, materializer)
        if isinstance(node, WzSubProperty):
            output = WzSubProperty(node.name, parent)
            for child in node.children():
                output.add(clone_node(child, output))
            return output
        return arc.clone_property(node, parent, source_image, source_path, materializer)

    clone = clone_node(source, None)
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


def verify_mob_action_replace_scope(before: bytes, after: bytes, action_name: str) -> int:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)
    action_root = (action_name,)
    outside = lambda path: path[:1] != action_root
    removed = {path for path in before_records.keys() - after_records.keys() if outside(path)}
    added = {path for path in after_records.keys() - before_records.keys() if outside(path)}
    if removed or added:
        raise ValueError(f"动作迁移影响了其他记录: removed={sorted(removed)} added={sorted(added)}")
    for parent, names in before_orders.items():
        if parent[:1] == action_root:
            continue
        if after_orders.get(parent) != names:
            raise ValueError(f"动作迁移改变了其他兄弟顺序: {'/'.join(parent) or '/'}")
    protected = 0
    for path, raw in before_records.items():
        if not outside(path):
            continue
        if after_records.get(path) != raw:
            raise ValueError(f"动作迁移改变了未授权记录: {'/'.join(path)}")
        protected += 1
    return protected


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
    clone, materializer = clone_compatible_mob_action(source_action, source_image, source_path)

    server_path = server_xml_for_client(client_path)
    if server_path is None or not server_path.is_file():
        raise ValueError("当前项目缺少对应的服务端 Mob XML，不能执行动作级同步")
    client_original = client_path.read_bytes()
    if detect_region_from_img(client_original) != "GMS":
        raise ValueError("当前项目怪物 IMG 不是 GMS 格式")
    current = _verified_img_from_bytes(client_path, client_original).root.get(action_name)
    if current is not None and not isinstance(current, WzSubProperty):
        raise ValueError(f"当前项目同名节点不是动作目录: {action_name}")

    if current is None:
        client_data = arc.append_property_record(client_original, (), clone)
        arc.verify_raw_record_insert_scope(client_original, client_data, {(action_name,)})
        protected_records = len(arc.raw_record_state(client_original)[0])
        client_operation = "add"
    else:
        client_data = replace_img_record(
            client_original, (action_name,), clone, region="GMS",
        ).data
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


def copy_tms_node_with_server_sync(
    client_path: Path, source_path: Path, node_path: str,
) -> dict[str, Any]:
    require_repo_write(client_path)
    source_image = load_image(source_path)
    source_node = source_image.root if not node_path else source_image.root.get(node_path)
    if source_node is None:
        raise ValueError(f"TMS 节点不存在: {node_path}")
    is_map_source = "/Data/Map/Map/" in source_path.as_posix()
    resource_references = selected_map_resource_references(source_image.root, node_path) if is_map_source else []
    server_path = server_xml_for_client(client_path)
    if server_path is None:
        raise ValueError("找不到对应的服务端 XML 路径")

    existing_target = None
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
    else:
        clone, skipped_paths = clone_supported_node(source_node), []
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
                client_result: Any = patch_img_add(
                    staged_client, parent_path, clone.name, "imgdir", None,
                    dry_run=False, backup=False, node=clone,
                )
                server_result: Any = xml_add_cloned_node(
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
            else:
                raise ValueError(f"客户端同名节点已存在且不是空目录: {node_path}")
            client_data = staged_client.read_bytes()
            server_data = staged_server.read_bytes()
            _verified_img_from_bytes(client_path, client_data)
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


def require_mob_action_source(path: Path) -> None:
    allowed_roots = ((_TMS_DATA / "Mob").resolve(), _MS_CACHE_ROOT.resolve())
    if not any(path == root or path.is_relative_to(root) for root in allowed_roots):
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
