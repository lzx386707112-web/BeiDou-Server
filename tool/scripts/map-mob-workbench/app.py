#!/usr/bin/env python3
"""Local map and mob IMG/XML browser, previewer, comparer, and safe editor."""

from __future__ import annotations

import argparse
import html
import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
import xml.parsers.expat
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
_WZPY = _ROOT / "tool" / "wz-python"
if str(_WZPY) not in sys.path:
    sys.path.insert(0, str(_WZPY))
_MAPMIGRATE = _ROOT / "tool" / "scripts" / "mapmigrate"
if str(_MAPMIGRATE) not in sys.path:
    sys.path.insert(0, str(_MAPMIGRATE))

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
import compat as map_compat  # noqa: E402

app = Flask(__name__)
_WRITE_LOCK = threading.Lock()
_ALLOWED_SUFFIXES = (".img", ".img.xml", ".xml", ".json")
_SCALAR_TYPES = {"short", "int", "long", "float", "double", "string", "uol", "vector"}
_TMS_DATA = _ROOT.parent / "TMS" / "MapleStory-IMG" / "Data"


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
        return (
            _ROOT / "clien" / "Data" / "Mob" / f"{item_id}.img",
            tms if tms.is_file() else _ROOT / "gms-server" / "wz" / "Mob.wz" / f"{item_id}.img.xml",
        )
    if kind != "map" or not re.fullmatch(r"\d{9}", item_id):
        raise ValueError("地图 ID 必须是 9 位数字")
    bucket = f"Map{item_id[0]}"
    tms = _TMS_DATA / "Map" / "Map" / bucket / f"{item_id}.img"
    return (
        _ROOT / "clien" / "Data" / "Map" / "Map" / bucket / f"{item_id}.img",
        tms if tms.is_file() else _ROOT / "gms-server" / "wz" / "Map.wz" / "Map" / bucket / f"{item_id}.img.xml",
    )


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
    if path == "info/swim":
        scope = "整张地图的移动物理。旧端没有单独的水域矩形范围；VR 和 foothold 不决定 swim 开关范围。"
        values = "0=普通陆地移动；1=启用旧端水下/游泳移动。"
        migration = "客户端 Map IMG 与服务端 Map XML 的 info/swim 必须一致。客户端只做等长 int 标量原位修改。"
        if item_id == "450002011":
            migration = "本项目已验证方案：保留 A 的 info/swim=1，不要用 TMS B 的 0 覆盖；服务端 XML 同步为 1。fieldLimit、VR 边界、foothold 和传送门均不修改。"
    elif path == "info/fieldLimit":
        scope = "整张地图的动作/技能限制位掩码，与游泳区域范围无关。"
        values = "整数位掩码，不是连续范围；不能按大小阈值判断新旧版本。"
        migration = "从相邻旧端可工作地图或已有迁移证据选择值，客户端和服务端同步；不要为了启用游泳随意改它。"
    elif leaf in {"VRLeft", "VRRight", "VRTop", "VRBottom"} and "info" in ancestors:
        scope = "整张地图的镜头可见边界，不改变碰撞、刷怪或游泳物理。"
        values = "地图坐标；Left < Right、Top < Bottom。"
        migration = "仅在画面裁切或镜头范围错误时修改，并成组核对四个边界。"
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
    return {"scope": scope, "valueGuide": values, "migration": migration}


def contextual_meaning(path: str, meta: dict[str, Any], mode: str) -> str:
    parts = [part for part in path.split("/") if part]
    name = str(meta.get("name") or (parts[-1] if parts else "root"))
    if not parts:
        return "资源文件根节点；所有地图结构、属性和引用都位于其子树中。"
    if mode != "map":
        return map_compat.node_meaning(name, path, meta, mode)
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
    elif kind == "mob":
        left_files = (_ROOT / "clien" / "Data" / "Mob").glob("*.img")
        right_root = _ROOT / "gms-server" / "wz" / "Mob.wz"
    else:
        raise ValueError("kind 必须是 map 或 mob")
    query = query.strip().lower()
    rows = []
    for left in left_files:
        item_id = left.stem
        if query and query not in item_id.lower():
            continue
        _, right = default_paths(kind, item_id)
        rows.append({
            "id": item_id,
            "leftPath": relative_path(left),
            "rightPath": relative_path(right),
            "hasXml": right.is_file(),
        })
    rows.sort(key=lambda row: natural_key(row["id"]))
    return rows[:300]


def data_root_for(path: Path) -> Path:
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
    return {
        "kind": "map", "bounds": bounds, "elements": elements, "footholds": footholds,
        "life": life, "portals": portals, "minimap": minimap,
        "summary": {
            "elements": len(elements), "footholds": len(footholds),
            "mobs": sum(point["kind"] == "mob" for point in life),
            "npcs": sum(point["kind"] == "npc" for point in life), "portals": len(portals),
        },
    }


def compatibility_category(path: str) -> str:
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


def map_resource_references(root: WzSubProperty) -> list[dict[str, Any]]:
    references: dict[tuple[str, str, str], dict[str, Any]] = {}

    def add(kind: str, name: str, canvas_path: str, node_path: str) -> None:
        if not name:
            return
        key = (kind, name, canvas_path)
        entry = references.setdefault(key, {
            "kind": kind, "name": name, "canvasPath": canvas_path, "nodes": [],
        })
        if len(entry["nodes"]) < 6:
            entry["nodes"].append(node_path)

    back = root.child("back")
    if isinstance(back, WzSubProperty):
        for item in back.children():
            if not isinstance(item, WzSubProperty):
                continue
            number = str(child_value(item, "no", "0"))
            canvas_path = f"ani/{number}/0" if int(child_value(item, "ani", 0)) else f"back/{number}"
            add("back", str(child_value(item, "bS", "")), canvas_path, property_path(item))

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
                    add("tile", tile_set, f"{child_value(item, 'u', '')}/{child_value(item, 'no', 0)}", property_path(item))
        obj_root = layer.child("obj")
        if isinstance(obj_root, WzSubProperty):
            for item in obj_root.children():
                if not isinstance(item, WzSubProperty):
                    continue
                canvas_path = "/".join(str(child_value(item, name, "")) for name in ("l0", "l1", "l2")) + "/0"
                add("obj", str(child_value(item, "oS", "")), canvas_path, property_path(item))

    life = root.child("life")
    if isinstance(life, WzSubProperty):
        for item in life.children():
            if not isinstance(item, WzSubProperty):
                continue
            kind = "mob" if str(child_value(item, "type", "")) == "m" else "npc"
            add(kind, str(child_value(item, "id", "")), "", property_path(item))
    return list(references.values())


def audit_map_resources(left_path: Path, right_path: Path) -> list[dict[str, Any]]:
    if not right_path.name.lower().endswith(".img"):
        return []
    right_root = load_image(right_path).root
    left_data = data_root_for(left_path)
    folders = {"back": ("Map", "Back"), "tile": ("Map", "Tile"), "obj": ("Map", "Obj"), "mob": ("Mob",), "npc": ("Npc",)}
    result = []
    for reference in map_resource_references(right_root):
        relative = Path(*folders[reference["kind"]]) / f'{reference["name"]}.img'
        resource = left_data / relative
        if not resource.is_file() and reference["kind"] in {"mob", "npc"}:
            resource = resource.parent / "_Canvas" / resource.name
        if not resource.is_file():
            status = "missingFile"
        elif reference["kind"] in {"mob", "npc"}:
            status = "ready" if first_entity_frame(resource) else "missingCanvas"
        else:
            status = "ready" if canvas_descriptor(resource, reference["canvasPath"]) else "missingCanvas"
        result.append({
            **reference, "status": status,
            "clientPath": relative_path(resource) if resource.is_file() else relative_path(left_data / relative),
        })
    severity = {"ready": 0, "missingCanvas": 1, "missingFile": 2}
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in result:
        key = (item["kind"], item["name"])
        entry = grouped.setdefault(key, {
            "kind": item["kind"], "name": item["name"], "status": item["status"],
            "clientPath": item["clientPath"], "canvasPaths": [], "nodes": [],
        })
        if severity[item["status"]] > severity[entry["status"]]:
            entry["status"] = item["status"]
        if item["canvasPath"] and item["canvasPath"] not in entry["canvasPaths"] and len(entry["canvasPaths"]) < 6:
            entry["canvasPaths"].append(item["canvasPath"])
        for node_path in item["nodes"]:
            if node_path not in entry["nodes"] and len(entry["nodes"]) < 6:
                entry["nodes"].append(node_path)
    return sorted(grouped.values(), key=lambda item: (item["status"] == "ready", item["kind"], natural_key(item["name"])))


def compatibility_analysis(
    left: dict[str, dict[str, Any]], right: dict[str, dict[str, Any]], left_path: Path, right_path: Path,
) -> dict[str, Any]:
    item_id = infer_id(left_path)
    right_only = sorted(set(right) - set(left), key=lambda value: [natural_key(part) for part in value.split("/")])
    right_only_set = set(right_only)
    added_roots = [path for path in right_only if (path.rsplit("/", 1)[0] if "/" in path else "") not in right_only_set]
    definitions = {
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
        "rightOnlyCount": len(right_only), "addedRoots": added_roots[:40], "addedRootCount": len(added_roots),
        "modernCandidateCount": finding_counts["modern"], "incompatibleCount": finding_counts["incompatible"],
        "reviewCount": finding_counts["review"], "findings": findings, "changedNodes": changed_nodes,
        "categories": categories, "resources": resources,
        "missingResourceCount": sum(item["status"] != "ready" for item in resources),
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


def patch_img(path: Path, node_path: str, value: Any, *, dry_run: bool, backup: bool) -> dict[str, Any]:
    image = load_image(path)
    node = image.root.get(node_path)
    if node is None:
        raise ValueError(f"节点不存在: {node_path}")
    patches = encode_img_scalar(image, node, value)
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


@app.errorhandler(Exception)
def handle_error(exc: Exception):
    status = getattr(exc, "code", 400)
    return jsonify({"ok": False, "reason": str(exc)}), status if isinstance(status, int) else 400


@app.get("/")
def index():
    return render_template("index.html", tms_data_root=str(_TMS_DATA))


@app.get("/api/catalog")
def api_catalog():
    return jsonify({"ok": True, "items": catalog_rows(request.args.get("kind", "map"), request.args.get("q", ""))})


@app.get("/api/files")
def api_files():
    return jsonify({"ok": True, **browse_directory(request.args.get("path", ""))})


@app.post("/api/compare")
def api_compare():
    body = request.get_json(silent=True) or {}
    left_path = resolve_repo_path(str(body.get("leftPath", "")))
    right_path = resolve_repo_path(str(body.get("rightPath", "")))
    left, left_info = flatten_source(left_path)
    right, right_info = flatten_source(right_path)
    nodes, counts = merge_sources(left, right)
    mode = "map" if str(body.get("kind", "map")) == "map" else "boss"
    compatibility = compatibility_analysis(left, right, left_path, right_path) if mode == "map" else None
    annotate_rows(nodes, mode, infer_id(left_path))
    return jsonify({
        "ok": True, "leftPath": relative_path(left_path), "rightPath": relative_path(right_path),
        "leftInfo": left_info, "rightInfo": right_info, "nodes": nodes, "counts": counts, "compatibility": compatibility,
    })


@app.post("/api/preview")
def api_preview():
    body = request.get_json(silent=True) or {}
    kind = str(body.get("kind", "map"))
    source = resolve_repo_path(str(body.get("sourcePath", "")))
    if not source.name.lower().endswith(".img"):
        client, _ = default_paths(kind, infer_id(source))
        source = resolve_repo_path(relative_path(client))
    payload = map_preview(source) if kind == "map" else mob_preview(source)
    return jsonify({"ok": True, "sourcePath": relative_path(source), **payload})


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
    dry_run = bool(body.get("dryRun", True))
    backup = bool(body.get("backup", True))
    with _WRITE_LOCK:
        if path.name.lower().endswith(".img"):
            result = patch_img(path, node_path, body.get("value"), dry_run=dry_run, backup=backup)
        elif path.name.lower().endswith((".xml", ".img.xml")):
            result = patch_xml_value(path, node_path, body.get("value"), dry_run=dry_run, backup=backup)
        else:
            raise ValueError("JSON 文件当前只读")
    return jsonify({"ok": True, "dryRun": dry_run, **result})


@app.post("/api/add")
def api_add():
    body = request.get_json(silent=True) or {}
    path = resolve_repo_path(str(body.get("sourcePath", "")))
    require_repo_write(path)
    if path.name.lower().endswith(".img"):
        raise ValueError("二进制 IMG 不允许增删节点；请编辑对应 XML，再通过审核过的增量迁移脚本同步客户端")
    if path.suffix.lower() == ".json":
        raise ValueError("JSON 文件当前只读")
    with _WRITE_LOCK:
        result = xml_add_node(
            path, str(body.get("parentPath", "")).strip("/"), str(body.get("name", "")).strip(),
            str(body.get("type", "int")), body.get("value"), dry_run=bool(body.get("dryRun", True)), backup=bool(body.get("backup", True)),
        )
    return jsonify({"ok": True, "dryRun": bool(body.get("dryRun", True)), **result})


@app.post("/api/delete")
def api_delete():
    body = request.get_json(silent=True) or {}
    path = resolve_repo_path(str(body.get("sourcePath", "")))
    require_repo_write(path)
    if path.name.lower().endswith(".img"):
        raise ValueError("二进制 IMG 不允许删除节点；请使用审核过的原始记录增量替换脚本")
    if path.suffix.lower() == ".json":
        raise ValueError("JSON 文件当前只读")
    with _WRITE_LOCK:
        result = xml_delete_node(path, str(body.get("path", "")).strip("/"), dry_run=bool(body.get("dryRun", True)), backup=bool(body.get("backup", True)))
    return jsonify({"ok": True, "dryRun": bool(body.get("dryRun", True)), **result})


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
