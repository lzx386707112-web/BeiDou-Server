#!/usr/bin/env python3
"""Web UI for comparing and editing client .img canvases with server .img.xml."""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
_WZPY = _ROOT / "tool" / "wz-python"
for path in (str(_HERE), str(_WZPY)):
    if path not in sys.path:
        sys.path.insert(0, path)

from flask import Flask, jsonify, request, send_file  # noqa: E402
from wzpy import StaticWzKey, WzImage, WzKey, derive_keystream_from_property, detect_region_from_img  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.properties import (  # noqa: E402
    WzCanvasProperty,
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.writer import encode_image_body  # noqa: E402

import replace_img_canvas as replace  # noqa: E402


app = Flask(__name__)


def root_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = _ROOT / path
    return path


def rel_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(_ROOT))
    except ValueError:
        return str(path)


def default_client_img(skill_img: str) -> Path:
    return _ROOT / "clien" / "Data" / "Skill" / f"{skill_img}.img"


def default_server_xml(skill_img: str) -> Path:
    return _ROOT / "gms-server" / "wz" / "Skill.wz" / f"{skill_img}.img.xml"


def path_for_picker(raw: str) -> Path:
    path = root_path(raw) if raw else _ROOT
    if path.is_file():
        return path.parent
    return path


def file_matches_kind(path: Path, kind: str) -> bool:
    name = path.name.lower()
    if kind in {"img", "reference"}:
        return name.endswith(".img")
    if kind == "xml":
        return name.endswith(".img.xml") or name.endswith(".xml")
    return path.is_file()


def list_picker_dir(raw: str, kind: str) -> dict[str, Any]:
    current = path_for_picker(raw).expanduser().resolve()
    if not current.exists():
        current = _ROOT
    if not current.is_dir():
        current = current.parent

    dirs = []
    files = []
    for item in sorted(current.iterdir(), key=lambda path: (not path.is_dir(), replace.natural_key(path.name))):
        if item.name.startswith("."):
            continue
        try:
            if item.is_dir():
                dirs.append({"name": item.name, "path": rel_path(item)})
            elif file_matches_kind(item, kind):
                files.append({"name": item.name, "path": rel_path(item), "size": item.stat().st_size})
        except OSError:
            continue

    parent = current.parent if current.parent != current else current
    return {
        "path": rel_path(current),
        "parent": rel_path(parent),
        "dirs": dirs,
        "files": files,
        "roots": [
            {"name": "项目", "path": rel_path(_ROOT)},
            {"name": "用户目录", "path": str(Path.home())},
        ],
    }


def load_client_image(img_path: Path) -> WzImage:
    data = img_path.read_bytes()
    region = detect_region_from_img(data)
    if region is not None:
        key = WzKey.for_region(region)
    else:
        key = StaticWzKey(derive_keystream_from_property(data))
    image = WzImage.from_bytes(data, key=key, name=img_path.name)
    image.parse()
    return image


def xml_child(parent: ET.Element, tag: str, name: str) -> ET.Element | None:
    for child in parent:
        if child.tag == tag and child.get("name") == name:
            return child
    return None


def xml_child_any(parent: ET.Element, tags: tuple[str, ...], name: str) -> ET.Element | None:
    for tag in tags:
        child = xml_child(parent, tag, name)
        if child is not None:
            return child
    return None


def find_xml_node(root: ET.Element, path: str) -> ET.Element | None:
    if not path.strip("/"):
        return root
    parts = replace.split_canvas_path(path)
    if root.get("name") == parts[0]:
        parts = parts[1:]
    node = root
    for part in parts:
        child = next((child for child in node if child.get("name") == part), None)
        if child is None:
            return None
        node = child
    return node


def img_child(root: WzSubProperty, path: str) -> Any:
    if not path.strip("/"):
        return root
    return root.get(path)


def normalized_img_path(root: WzSubProperty, path: str) -> str:
    parts = [part for part in path.strip("/").split("/") if part]
    if parts and parts[0] == root.name:
        parts = parts[1:]
    return "/".join(parts)


def reference_path_context(root: WzSubProperty, path: str) -> dict[str, Any]:
    parts = [part for part in path.strip("/").split("/") if part]
    if parts and parts[0] == root.name:
        parts = parts[1:]

    node: Any = root
    existing: list[str] = []
    missing = ""
    for index, part in enumerate(parts):
        if not isinstance(node, WzSubProperty):
            missing = "/".join(parts[index:])
            break
        child = node.child(part)
        if child is None:
            missing = "/".join(parts[index:])
            break
        node = child
        existing.append(part)

    children = []
    if isinstance(node, WzSubProperty):
        children = sorted((child.name for child in node.children()), key=replace.natural_key)[:30]
    return {
        "nearestPath": "/".join(existing),
        "missingPath": missing,
        "children": children,
    }


def join_img_path(parent: str, child: str) -> str:
    return f"{parent.rstrip('/')}/{child}".strip("/")


def vector_value(node: Any) -> dict[str, int] | None:
    if isinstance(node, WzVectorProperty):
        return {"x": int(node.x), "y": int(node.y)}
    if isinstance(node, ET.Element) and node.tag == "vector":
        return {"x": int(node.get("x", "0")), "y": int(node.get("y", "0"))}
    return None


def int_values_from_client(canvas: WzCanvasProperty) -> dict[str, int]:
    values: dict[str, int] = {}
    for child in canvas.children():
        if isinstance(child, WzIntProperty):
            values[child.name] = int(child.value)
    return values


def int_values_from_xml(canvas: ET.Element) -> dict[str, int]:
    values: dict[str, int] = {}
    for child in canvas:
        if child.tag == "int" and child.get("name"):
            try:
                values[child.get("name", "")] = int(child.get("value", "0"))
            except ValueError:
                pass
    return values


def client_meta(prop: Any) -> dict[str, Any]:
    if isinstance(prop, WzCanvasProperty):
        origin = vector_value(prop.child("origin"))
        return {
            "type": "canvas",
            "width": int(prop.width),
            "height": int(prop.height),
            "origin": origin,
            "ints": int_values_from_client(prop),
            "hasPixels": prop.has_pixels(),
        }
    if isinstance(prop, WzUolProperty):
        return {"type": "uol", "target": str(prop.value)}
    if isinstance(prop, WzVectorProperty):
        return {"type": "vector", "value": {"x": int(prop.x), "y": int(prop.y)}}
    if isinstance(prop, WzIntProperty):
        return {"type": "int", "value": int(prop.value)}
    if isinstance(prop, WzStringProperty):
        return {"type": "string", "value": str(prop.value)}
    if isinstance(prop, WzSubProperty):
        return {"type": "imgdir", "children": len(prop.children())}
    if prop is None:
        return {"type": "missing"}
    out = {"type": str(getattr(prop, "type_name", type(prop).__name__)).lower()}
    try:
        out["value"] = prop.value
    except Exception:
        pass
    return out


def xml_meta(node: ET.Element | None) -> dict[str, Any]:
    if node is None:
        return {"type": "missing"}
    if node.tag == "canvas":
        origin = None
        origin_node = xml_child(node, "vector", "origin")
        if origin_node is not None:
            origin = vector_value(origin_node)
        return {
            "type": "canvas",
            "width": int(node.get("width", "0")),
            "height": int(node.get("height", "0")),
            "origin": origin,
            "ints": int_values_from_xml(node),
        }
    if node.tag == "uol":
        return {"type": "uol", "target": node.get("value", "")}
    if node.tag == "vector":
        return {"type": "vector", "value": {"x": int(node.get("x", "0")), "y": int(node.get("y", "0"))}}
    if node.tag == "int":
        try:
            value = int(node.get("value", "0"))
        except ValueError:
            value = node.get("value", "")
        return {"type": "int", "value": value}
    if node.tag == "string":
        return {"type": "string", "value": node.get("value", "")}
    if node.tag == "imgdir":
        return {"type": "imgdir", "children": len(list(node))}
    out = {"type": node.tag}
    if node.get("value") is not None:
        out["value"] = node.get("value")
    return out


def comparable(meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": meta.get("type"),
        "width": meta.get("width"),
        "height": meta.get("height"),
        "origin": meta.get("origin"),
        "ints": meta.get("ints") or {},
        "target": meta.get("target"),
        "value": meta.get("value"),
    }


def sync_status(client: dict[str, Any], server: dict[str, Any]) -> str:
    if client.get("type") == "missing" and server.get("type") == "missing":
        return "missing"
    if server.get("type") == "missing":
        return "server-missing"
    if client.get("type") == "missing":
        return "client-missing"
    if comparable(client) == comparable(server):
        return "synced"
    return "different"


def compare_status(client: dict[str, Any], reference: dict[str, Any]) -> str:
    if reference.get("type") == "not-loaded":
        return "no-reference"
    if client.get("type") == "missing" and reference.get("type") == "missing":
        return "missing"
    if reference.get("type") == "missing":
        return "reference-missing"
    if client.get("type") == "missing":
        return "client-missing"
    if comparable(client) == comparable(reference):
        return "same"
    return "different"


def child_names(client_node: Any, reference_node: Any, xml_node: ET.Element | None) -> list[str]:
    names: set[str] = set()
    if isinstance(client_node, WzSubProperty):
        names.update(child.name for child in client_node.children())
    if isinstance(reference_node, WzSubProperty):
        names.update(child.name for child in reference_node.children())
    if xml_node is not None:
        names.update(child.get("name", "") for child in xml_node if child.get("name"))
    return sorted(names, key=replace.natural_key)


def node_meaning(name: str, path: str, meta: dict[str, Any]) -> str:
    node_type = meta.get("type")
    parts = [part for part in path.split("/") if part]
    parent = parts[-2] if len(parts) >= 2 else ""

    if node_type == "canvas":
        return "实际图片帧；客户端保存像素，服务端 XML 保存尺寸、原点和子属性。"
    if node_type == "uol":
        return "引用节点；不存图片，指向另一个 canvas 或属性。"
    if node_type == "vector" and name == "origin":
        return "绘制原点；决定图片相对角色/技能锚点的偏移。"
    if node_type == "vector" and name in {"lt", "rb"}:
        return "范围边界点；通常用于技能判定、包围盒或特效范围。"
    if node_type == "int" and name == "delay":
        return "帧停留时间，单位通常是毫秒；服务端会读取 effect 下的 delay 计算动画时间。"
    if node_type == "int" and name == "z":
        return "绘制层级/排序信息；影响图片与其他层的前后关系。"
    if name == "skill":
        return "技能列表根节点，下面按技能 ID 分组。"
    if len(parts) == 2 and parts[0] == "skill":
        return "单个技能节点，包含动作、特效、等级数据等。"
    if name == "effect":
        return "技能释放时播放的主要特效容器。"
    if parent == "effect" and name.isdigit():
        return "特效分组/方向/变体；里面通常按 0、1、2... 存放动画帧。"
    if name.isdigit() and parent.isdigit():
        return "动画帧序号；批量替换时通常按文件排序映射到这些编号。"
    if name == "action":
        return "角色动作名配置；告诉客户端播放哪个角色动作。"
    if name == "afterimage":
        return "武器残影/攻击轨迹相关图片配置。"
    if name == "level":
        return "技能等级数据；每级伤害、消耗、范围等数值通常在这里。"
    if name == "info":
        return "基础信息节点；常见于图标、说明或通用配置。"
    if name.startswith("icon"):
        return "技能图标相关 canvas。"
    if node_type == "imgdir":
        return "目录/容器节点，用来组织子节点，本身通常不存像素。"
    if node_type == "int":
        return "整数属性；具体含义取决于节点名和父节点。"
    if node_type == "string":
        return "字符串属性；通常是动作名、链接或配置文本。"
    if node_type == "vector":
        return "二维坐标属性。"
    return "WZ 属性节点；含义取决于父节点和客户端读取方式。"


def plan_node(prop: Any, path: str) -> dict[str, Any]:
    meta = client_meta(prop)
    out = {
        "name": path.strip("/").split("/")[-1] if path.strip("/") else "<root>",
        "path": path,
        "type": meta.get("type"),
    }
    for key in ("width", "height", "origin", "ints", "target", "value", "children"):
        if key in meta:
            out[key] = meta[key]
    if isinstance(prop, WzSubProperty):
        out["children"] = [plan_node(child, join_img_path(path, child.name)) for child in prop.children()]
    return out


def xml_append_from_client(parent: ET.Element, prop: Any, name: str) -> ET.Element:
    if isinstance(prop, WzCanvasProperty):
        attrs = {"name": name, "width": str(int(prop.width)), "height": str(int(prop.height))}
        node = ET.SubElement(parent, "canvas", attrs)
        for child in prop.children():
            xml_append_from_client(node, child, child.name)
        return node
    if isinstance(prop, WzSubProperty):
        node = ET.SubElement(parent, "imgdir", {"name": name})
        for child in prop.children():
            xml_append_from_client(node, child, child.name)
        return node
    if isinstance(prop, WzVectorProperty):
        return ET.SubElement(parent, "vector", {"name": name, "x": str(int(prop.x)), "y": str(int(prop.y))})
    if isinstance(prop, WzIntProperty):
        return ET.SubElement(parent, "int", {"name": name, "value": str(int(prop.value))})
    if isinstance(prop, WzStringProperty):
        return ET.SubElement(parent, "string", {"name": name, "value": str(prop.value)})
    if isinstance(prop, WzUolProperty):
        return ET.SubElement(parent, "uol", {"name": name, "value": str(prop.value)})
    return ET.SubElement(parent, "unknown", {"name": name, "type": type(prop).__name__})


def sync_xml_subtree_from_client(xml_root: ET.Element, client_root: WzSubProperty, target_path: str, replace_existing: bool) -> None:
    source = client_root.get(target_path)
    if source is None:
        raise KeyError(f"Missing copied target node {target_path!r}")
    parent, name = replace.xml_parent_and_name(xml_root, target_path, create=True)
    if replace_existing:
        for child in list(parent):
            if child.get("name") == name:
                parent.remove(child)
    elif any(child.get("name") == name for child in parent):
        raise TypeError(f"XML target path {target_path!r} already exists")
    xml_append_from_client(parent, source, name)


def add_client_node(root: WzSubProperty, target_path: str, kind: str, value: Any) -> Any:
    parent, name = replace.img_parent_and_name(root, target_path, create=False)
    if parent.child(name) is not None:
        raise TypeError(f"Target path {target_path!r} already exists")
    if kind == "imgdir":
        node = WzSubProperty(name, parent)
    elif kind == "int":
        node = WzIntProperty(name, int(value or 0), parent)
    elif kind == "string":
        node = WzStringProperty(name, "" if value is None else str(value), parent)
    elif kind == "uol":
        node = WzUolProperty(name, "" if value is None else str(value), parent)
    elif kind == "vector":
        if not isinstance(value, dict):
            raise ValueError("vector value must include x and y")
        node = WzVectorProperty(name, int(value.get("x", 0)), int(value.get("y", 0)), parent)
    else:
        raise ValueError(f"Unsupported node type: {kind!r}")
    parent.add(node)
    return node


def build_tree(
    client_node: Any,
    reference_node: Any,
    xml_node: ET.Element | None,
    path: str,
    reference_loaded: bool,
    depth: int = 0,
    max_depth: int = 8,
) -> dict[str, Any]:
    name = path.strip("/").split("/")[-1] if path.strip("/") else "<root>"
    client = client_meta(client_node)
    reference = client_meta(reference_node) if reference_loaded else {"type": "not-loaded"}
    server = xml_meta(xml_node)
    merged = client if client.get("type") != "missing" else reference if reference.get("type") != "missing" else server
    children = []
    if depth < max_depth:
        for child_name in child_names(client_node, reference_node, xml_node):
            child_client = client_node.child(child_name) if isinstance(client_node, WzSubProperty) else None
            child_reference = reference_node.child(child_name) if isinstance(reference_node, WzSubProperty) else None
            child_xml = None
            if xml_node is not None:
                child_xml = next((child for child in xml_node if child.get("name") == child_name), None)
            children.append(
                build_tree(
                    child_client,
                    child_reference,
                    child_xml,
                    join_img_path(path, child_name),
                    reference_loaded,
                    depth + 1,
                    max_depth,
                )
            )
    return {
        "name": name,
        "path": path,
        "client": client,
        "reference": reference,
        "server": server,
        "compareStatus": compare_status(client, reference),
        "syncStatus": sync_status(client, server),
        "meaning": node_meaning(name, path, merged),
        "children": children,
    }


def build_reference_tree(prop: Any, path: str, depth: int = 0, max_depth: int = 8) -> dict[str, Any]:
    meta = client_meta(prop)
    name = getattr(prop, "name", "") if not path.strip("/") else path.strip("/").split("/")[-1]
    out = {
        "name": name or "<root>",
        "path": path,
        "meta": meta,
        "meaning": node_meaning(name, path, meta),
        "children": [],
    }
    if isinstance(prop, WzSubProperty) and depth < max_depth:
        out["children"] = [
            build_reference_tree(child, join_img_path(path, child.name), depth + 1, max_depth)
            for child in prop.children()
        ]
    return out


def build_workspace(
    img_path: Path,
    xml_path: Path,
    reference_img_path: Path | None,
    tree_path: str,
    selected_path: str,
) -> dict[str, Any]:
    client_image = load_client_image(img_path)
    reference_image = load_client_image(reference_img_path) if reference_img_path is not None else None
    client_parent = img_child(client_image.root, selected_path)
    client_tree_root = img_child(client_image.root, tree_path)
    reference_parent = img_child(reference_image.root, selected_path) if reference_image is not None else None
    reference_tree_root = img_child(reference_image.root, tree_path) if reference_image is not None else None

    xml_root = ET.parse(xml_path).getroot() if xml_path.exists() else None
    xml_parent = find_xml_node(xml_root, selected_path) if xml_root is not None else None
    xml_tree_root = find_xml_node(xml_root, tree_path) if xml_root is not None else None

    rows = []
    for name in child_names(client_parent, reference_parent, xml_parent):
        path = join_img_path(selected_path, name)
        client = client_meta(client_parent.child(name) if isinstance(client_parent, WzSubProperty) else None)
        reference = (
            client_meta(reference_parent.child(name) if isinstance(reference_parent, WzSubProperty) else None)
            if reference_image is not None
            else {"type": "not-loaded"}
        )
        server_node = None
        if xml_parent is not None:
            server_node = xml_child_any(xml_parent, ("canvas", "imgdir", "uol", "vector", "int", "string"), name)
        server = xml_meta(server_node)
        rows.append({
            "name": name,
            "path": path,
            "client": client,
            "reference": reference,
            "server": server,
            "compareStatus": compare_status(client, reference),
            "syncStatus": sync_status(client, server),
            "meaning": node_meaning(
                name,
                path,
                client if client.get("type") != "missing" else reference if reference.get("type") != "missing" else server,
            ),
        })

    return {
        "imgPath": rel_path(img_path),
        "referenceImgPath": rel_path(reference_img_path) if reference_img_path is not None else "",
        "xmlPath": rel_path(xml_path),
        "selectedPath": selected_path,
        "treePath": tree_path,
        "clientParent": client_meta(client_parent),
        "referenceParent": client_meta(reference_parent) if reference_image is not None else {"type": "not-loaded"},
        "serverParent": xml_meta(xml_parent),
        "tree": build_tree(client_tree_root, reference_tree_root, xml_tree_root, tree_path, reference_image is not None),
        "referenceTree": build_reference_tree(reference_image.root, "") if reference_image is not None else None,
        "rows": rows,
    }


@app.get("/")
def index():
    return HTML


@app.get("/api/load")
def api_load():
    skill_img = request.args.get("skill_img", "122").strip() or "122"
    img_path = root_path(request.args.get("img_path") or str(default_client_img(skill_img)))
    reference_raw = request.args.get("reference_img_path", "").strip()
    reference_img_path = root_path(reference_raw) if reference_raw else None
    xml_path = root_path(request.args.get("xml_path") or str(default_server_xml(skill_img)))
    tree_path = request.args.get("root_path", "").strip("/")
    selected_path = request.args.get("selected_path", tree_path).strip("/")
    try:
        return jsonify({"ok": True, **build_workspace(img_path, xml_path, reference_img_path, tree_path, selected_path)})
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 400


@app.get("/api/browse")
def api_browse():
    kind = request.args.get("kind", "img").strip() or "img"
    raw_path = request.args.get("path", "").strip()
    try:
        return jsonify({"ok": True, **list_picker_dir(raw_path, kind)})
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 400


@app.get("/api/canvas.png")
def api_canvas_png():
    img_path = root_path(request.args["img_path"])
    canvas_path = request.args["path"]
    image = load_client_image(img_path)
    prop = image.root.get(canvas_path)
    if not isinstance(prop, WzCanvasProperty):
        return jsonify({"ok": False, "reason": "target is not a client Canvas"}), 404
    png = decode_canvas(prop, region="GMS")
    buf = io.BytesIO()
    png.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.post("/api/sync_xml")
def api_sync_xml():
    body = request.get_json(silent=True) or {}
    img_path = root_path(body.get("img_path", ""))
    xml_path = root_path(body.get("xml_path", ""))
    paths = body.get("paths") or []
    backup = bool(body.get("backup", True))
    dry_run = bool(body.get("dry_run", False))
    if not isinstance(paths, list) or not paths:
        return jsonify({"ok": False, "reason": "paths must be a non-empty list"}), 400

    image = load_client_image(img_path)
    xml_tree = ET.parse(xml_path)
    xml_root = xml_tree.getroot()
    updates = []
    for path in paths:
        prop = image.root.get(str(path))
        if not isinstance(prop, WzCanvasProperty):
            return jsonify({"ok": False, "reason": f"{path} is not a client Canvas"}), 400
        origin = prop.child("origin")
        if isinstance(origin, WzVectorProperty):
            ox, oy = int(origin.x), int(origin.y)
        else:
            ox, oy = 0, int(prop.height)
        update = replace.CanvasUpdate(
            canvas_path=str(path),
            old_width=int(prop.width),
            old_height=int(prop.height),
            width=int(prop.width),
            height=int(prop.height),
            origin_x=ox,
            origin_y=oy,
            ints=replace.canvas_int_children(prop),
        )
        replace.update_xml_canvas(xml_root, update, create=True)
        updates.append(asdict(update))

    if not dry_run:
        replace.write_xml(xml_path, xml_tree, backup=backup)
    return jsonify({"ok": True, "dryRun": dry_run, "updates": updates})


@app.post("/api/delete_node")
def api_delete_node():
    body = request.get_json(silent=True) or {}
    img_path = root_path(body.get("img_path", ""))
    xml_path = root_path(body.get("xml_path", ""))
    path = str(body.get("path", "")).strip("/")
    backup = bool(body.get("backup", True))
    dry_run = bool(body.get("dry_run", False))
    if not path:
        return jsonify({"ok": False, "reason": "path is required"}), 400

    image = load_client_image(img_path)
    client_removed = replace.delete_img_node(image.root, path)
    xml_removed = False
    xml_tree = None
    if xml_path.exists():
        xml_tree = ET.parse(xml_path)
        xml_removed = replace.delete_xml_node(xml_tree.getroot(), path)

    if not dry_run:
        out = encode_image_body(image, image.wz_file.reader)
        replace.write_img(img_path, out, backup=backup)
        if xml_tree is not None:
            replace.write_xml(xml_path, xml_tree, backup=backup)

    return jsonify({"ok": True, "dryRun": dry_run, "path": path, "clientRemoved": client_removed, "xmlRemoved": xml_removed})


@app.post("/api/add_node")
def api_add_node():
    body = request.get_json(silent=True) or {}
    img_path = root_path(body.get("img_path", ""))
    xml_path = root_path(body.get("xml_path", ""))
    parent_path = str(body.get("parent_path", "")).strip("/")
    name = str(body.get("name", "")).strip()
    kind = str(body.get("type", "")).strip()
    backup = bool(body.get("backup", True))
    dry_run = bool(body.get("dry_run", False))
    if not parent_path:
        return jsonify({"ok": False, "reason": "parent_path is required"}), 400
    if not name or "/" in name or "\\" in name:
        return jsonify({"ok": False, "reason": "node name is required and cannot include / or \\"}), 400

    target_path = join_img_path(parent_path, name)
    image = load_client_image(img_path)
    try:
        node = add_client_node(image.root, target_path, kind, body.get("value"))
        xml_tree = ET.parse(xml_path) if xml_path.exists() else None
        if xml_tree is not None:
            sync_xml_subtree_from_client(xml_tree.getroot(), image.root, target_path, replace_existing=False)

        if not dry_run:
            out = encode_image_body(image, image.wz_file.reader)
            replace.write_img(img_path, out, backup=backup)
            if xml_tree is not None:
                replace.write_xml(xml_path, xml_tree, backup=backup)
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 400

    return jsonify({
        "ok": True,
        "dryRun": dry_run,
        "path": target_path,
        "client": client_meta(node),
        "xmlSynced": xml_tree is not None,
    })


@app.post("/api/copy_node")
def api_copy_node():
    body = request.get_json(silent=True) or {}
    img_path = root_path(body.get("img_path", ""))
    xml_path = root_path(body.get("xml_path", ""))
    source_path = str(body.get("source_path", "")).strip("/")
    parent_path = str(body.get("parent_path", "")).strip("/")
    name = str(body.get("name", "")).strip()
    backup = bool(body.get("backup", True))
    dry_run = bool(body.get("dry_run", False))
    if not source_path:
        return jsonify({"ok": False, "reason": "source_path is required"}), 400
    if not parent_path:
        return jsonify({"ok": False, "reason": "parent_path is required"}), 400
    if name and ("/" in name or "\\" in name):
        return jsonify({"ok": False, "reason": "node name cannot include / or \\"}), 400

    image = load_client_image(img_path)
    source_path = normalized_img_path(image.root, source_path)
    parent_path = normalized_img_path(image.root, parent_path)
    if not source_path:
        return jsonify({"ok": False, "reason": "cannot copy IMG root node"}), 400
    if parent_path == source_path or parent_path.startswith(f"{source_path}/"):
        return jsonify({"ok": False, "reason": "cannot copy a node into itself or its child"}), 400

    target_name = name or source_path.split("/")[-1]
    target_path = join_img_path(parent_path, target_name)
    try:
        replace.copy_img_subtree(image.root, image.root, source_path, target_path, replace_existing=False)
        xml_tree = ET.parse(xml_path) if xml_path.exists() else None
        if xml_tree is not None:
            sync_xml_subtree_from_client(xml_tree.getroot(), image.root, target_path, replace_existing=False)

        if not dry_run:
            out = encode_image_body(image, image.wz_file.reader)
            replace.write_img(img_path, out, backup=backup)
            if xml_tree is not None:
                replace.write_xml(xml_path, xml_tree, backup=backup)
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 400

    return jsonify({
        "ok": True,
        "dryRun": dry_run,
        "sourcePath": source_path,
        "path": target_path,
        "xmlSynced": xml_tree is not None,
    })


@app.post("/api/update_node_value")
def api_update_node_value():
    body = request.get_json(silent=True) or {}
    img_path = root_path(body.get("img_path", ""))
    xml_path = root_path(body.get("xml_path", ""))
    path = str(body.get("path", "")).strip("/")
    backup = bool(body.get("backup", True))
    dry_run = bool(body.get("dry_run", False))
    value = body.get("value")
    if not path:
        return jsonify({"ok": False, "reason": "path is required"}), 400

    image = load_client_image(img_path)
    node = image.root.get(path)
    if node is None:
        return jsonify({"ok": False, "reason": f"node not found: {path}"}), 404

    try:
        if isinstance(node, WzIntProperty):
            node._value = int(value)
        elif isinstance(node, WzStringProperty):
            node._value = str(value)
        elif isinstance(node, WzUolProperty):
            node._value = str(value)
        elif isinstance(node, WzVectorProperty):
            if not isinstance(value, dict):
                raise ValueError("vector value must include x and y")
            node.x = int(value.get("x", 0))
            node.y = int(value.get("y", 0))
            node._value = (node.x, node.y)
        else:
            return jsonify({"ok": False, "reason": f"{path} is {type(node).__name__}, not an editable value node"}), 400

        xml_tree = ET.parse(xml_path) if xml_path.exists() else None
        if xml_tree is not None:
            sync_xml_subtree_from_client(xml_tree.getroot(), image.root, path, replace_existing=True)

        if not dry_run:
            out = encode_image_body(image, image.wz_file.reader)
            replace.write_img(img_path, out, backup=backup)
            if xml_tree is not None:
                replace.write_xml(xml_path, xml_tree, backup=backup)
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 400

    return jsonify({
        "ok": True,
        "dryRun": dry_run,
        "path": path,
        "client": client_meta(node),
        "xmlSynced": xml_tree is not None,
    })


@app.post("/api/analyze_plan")
def api_analyze_plan():
    body = request.get_json(silent=True) or {}
    img_path = root_path(body.get("img_path", ""))
    reference_path = root_path(body.get("reference_img_path", ""))
    xml_path = root_path(body.get("xml_path", ""))
    source_path = str(body.get("source_path") or body.get("path") or "").strip("/")
    target_path = str(body.get("target_path") or source_path).strip("/")
    if not reference_path.exists():
        return jsonify({"ok": False, "reason": "请先选择其他服 .img"}), 400

    reference_image = load_client_image(reference_path)
    source_path = normalized_img_path(reference_image.root, source_path)
    source = reference_image.root if not source_path else reference_image.root.get(source_path)
    if source is None:
        context = reference_path_context(reference_image.root, source_path)
        reason = f"其他服中找不到来源节点: {source_path}。请修改“来源路径(其他服)”为该 IMG 中真实存在的节点。"
        if context["nearestPath"] or context["children"]:
            nearest = context["nearestPath"] or "<root>"
            children = ", ".join(context["children"][:12]) if context["children"] else "无子节点"
            reason = f"{reason}\n最近存在节点: {nearest}\n可选子节点: {children}"
        return jsonify({"ok": False, "reason": reason, "context": context}), 400

    plan = {
        "version": 1,
        "kind": "png2canvas-node-plan",
        "sourceImg": rel_path(reference_path),
        "targetImg": rel_path(img_path),
        "serverXml": rel_path(xml_path),
        "operations": [
            {
                "op": "copyTree",
                "sourcePath": source_path,
                "targetPath": target_path,
                "replace": True,
                "syncXml": True,
            }
        ],
        "structure": plan_node(source, source_path),
    }
    return jsonify({"ok": True, "plan": plan})


@app.post("/api/apply_plan")
def api_apply_plan():
    body = request.get_json(silent=True) or {}
    plan = body.get("plan")
    if isinstance(plan, str):
        plan = json.loads(plan)
    if not isinstance(plan, dict):
        return jsonify({"ok": False, "reason": "plan must be a JSON object"}), 400

    img_path = root_path(body.get("img_path") or plan.get("targetImg", ""))
    reference_path = root_path(body.get("reference_img_path") or plan.get("sourceImg", ""))
    xml_path = root_path(body.get("xml_path") or plan.get("serverXml", ""))
    backup = bool(body.get("backup", True))
    dry_run = bool(body.get("dry_run", False))

    if not reference_path.exists():
        return jsonify({"ok": False, "reason": "sourceImg/reference_img_path does not exist"}), 400

    target_image = load_client_image(img_path)
    source_image = load_client_image(reference_path)
    xml_tree = ET.parse(xml_path) if xml_path.exists() else None
    applied = []

    try:
        for op in plan.get("operations", []):
            op_name = op.get("op")
            if op_name == "delete":
                target_path = str(op.get("targetPath", "")).strip("/")
                replace.delete_img_node(target_image.root, target_path)
                if xml_tree is not None and op.get("syncXml", True):
                    replace.delete_xml_node(xml_tree.getroot(), target_path)
                applied.append({"op": "delete", "targetPath": target_path})
                continue

            if op_name != "copyTree":
                raise ValueError(f"Unsupported op: {op_name!r}")
            source_path = str(op.get("sourcePath", "")).strip("/")
            target_path = str(op.get("targetPath", source_path)).strip("/")
            replace_existing = bool(op.get("replace", True))
            sync_xml = bool(op.get("syncXml", True))
            if not target_path:
                raise ValueError("copyTree requires targetPath")
            source_path = normalized_img_path(source_image.root, source_path)
            replace.copy_img_subtree(source_image.root, target_image.root, source_path, target_path, replace_existing)
            if xml_tree is not None and sync_xml:
                sync_xml_subtree_from_client(xml_tree.getroot(), target_image.root, target_path, replace_existing)
            applied.append({"op": "copyTree", "sourcePath": source_path, "targetPath": target_path, "replace": replace_existing})

        if not dry_run:
            out = encode_image_body(target_image, target_image.wz_file.reader)
            replace.write_img(img_path, out, backup=backup)
            if xml_tree is not None:
                replace.write_xml(xml_path, xml_tree, backup=backup)
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc), "applied": applied}), 400

    return jsonify({"ok": True, "dryRun": dry_run, "applied": applied})


def uploaded_png_to_temp(field: str) -> tuple[Path, Path]:
    upload = request.files.get(field)
    if upload is None:
        files = request.files.getlist("images")
        upload = files[0] if files else None
    if upload is None or not (upload.filename or "").lower().endswith(".png"):
        raise ValueError("请选择 PNG 文件")
    tmp_dir = Path(tempfile.mkdtemp(prefix="png2canvas-node."))
    out = tmp_dir / os.path.basename(upload.filename or "node.png")
    upload.save(out)
    return tmp_dir, out


@app.post("/api/upsert_canvas")
def api_upsert_canvas():
    img_path = root_path(request.form["img_path"])
    xml_path = root_path(request.form["xml_path"]) if request.form.get("sync_xml") == "1" else None
    target_path = request.form["path"].strip("/")
    origin = request.form.get("origin", "keep")
    backup = request.form.get("backup", "1") == "1"
    dry_run = request.form.get("dry_run", "1") == "1"
    replace_existing = request.form.get("replace_existing", "0") == "1"
    if not target_path:
        return jsonify({"ok": False, "reason": "path is required"}), 400

    tmp_dir = None
    try:
        tmp_dir, png = uploaded_png_to_temp("image")
        key = WzKey.for_region("GMS")
        image = load_client_image(img_path)
        update = replace.update_canvas(
            root=image.root,
            job=replace.CanvasJob(png=png, canvas_path=target_path),
            origin_mode=origin,
            ints=[],
            create=True,
            key=key,
            replace_existing=replace_existing,
        )

        xml_tree = None
        if xml_path is not None:
            xml_tree = ET.parse(xml_path)
            if replace_existing:
                replace.replace_existing_xml_with_canvas(xml_tree.getroot(), target_path)
            replace.update_xml_canvas(xml_tree.getroot(), update, create=True)

        if not dry_run:
            out = encode_image_body(image, image.wz_file.reader)
            replace.write_img(img_path, out, backup=backup)
            if xml_path is not None and xml_tree is not None:
                replace.write_xml(xml_path, xml_tree, backup=backup)

        return jsonify({"ok": True, "dryRun": dry_run, "update": asdict(update)})
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 400
    finally:
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/api/replace")
def api_replace():
    img_path = root_path(request.form["img_path"])
    xml_path = root_path(request.form["xml_path"]) if request.form.get("sync_xml") == "1" else None
    canvas_dir = request.form["canvas_dir"].strip("/")
    origin = request.form.get("origin", "keep")
    name_mode = request.form.get("name_mode", "index")
    backup = request.form.get("backup", "1") == "1"
    dry_run = request.form.get("dry_run", "1") == "1"
    files = request.files.getlist("images")
    if not files:
        return jsonify({"ok": False, "reason": "no PNG files uploaded"}), 400

    tmp_dir = Path(tempfile.mkdtemp(prefix="png2canvas-web."))
    try:
        pngs = []
        for upload in files:
            filename = os.path.basename(upload.filename or "")
            if not filename.lower().endswith(".png"):
                continue
            out = tmp_dir / filename
            upload.save(out)
            pngs.append(out)
        if not pngs:
            return jsonify({"ok": False, "reason": "uploaded files did not include PNGs"}), 400
        pngs.sort(key=lambda path: replace.natural_key(path.name))

        key = WzKey.for_region("GMS")
        image = load_client_image(img_path)
        jobs = [
            replace.CanvasJob(png=png, canvas_path=f"{canvas_dir}/{index if name_mode == 'index' else png.stem}")
            for index, png in enumerate(pngs)
        ]
        updates = [
            replace.update_canvas(
                root=image.root,
                job=job,
                origin_mode=origin,
                ints=[],
                create=True,
                key=key,
            )
            for job in jobs
        ]

        xml_tree = None
        if xml_path is not None:
            xml_tree = ET.parse(xml_path)
            xml_root = xml_tree.getroot()
            for update in updates:
                replace.update_xml_canvas(xml_root, update, create=True)

        if not dry_run:
            out = encode_image_body(image, image.wz_file.reader)
            replace.write_img(img_path, out, backup=backup)
            if xml_path is not None and xml_tree is not None:
                replace.write_xml(xml_path, xml_tree, backup=backup)

        return jsonify({
            "ok": True,
            "dryRun": dry_run,
            "updates": [asdict(update) for update in updates],
            "imgPath": rel_path(img_path),
            "xmlPath": rel_path(xml_path) if xml_path else None,
        })
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 400
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>PNG to Client IMG Canvas</title>
  <style>
    :root {
      color-scheme: dark;
      --bg:#070a0f; --panel:#0e141d; --line:#263241; --ink:#e7edf5;
      --muted:#8fa0b5; --accent:#14b8a6; --warn:#eab308; --bad:#fb7185; --ok:#22c55e;
    }
    * { box-sizing: border-box; }
    html, body { height:100%; }
    body { margin: 0; display:grid; grid-template-rows:auto auto minmax(0, 1fr) auto; font: 13px/1.35 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--ink); background: var(--bg); }
    header { min-height: 44px; display:flex; align-items:center; gap:14px; padding:8px 14px; background:#090d14; border-bottom:1px solid var(--line); }
    header strong { font-size: 15px; }
    header .muted { margin-right:auto; }
    .topbar { display:grid; grid-template-columns:72px 120px minmax(230px, 1fr) minmax(230px, 1fr) minmax(230px, 1fr) auto; gap:8px; padding:10px 12px; background:#0a0f17; border-bottom:1px solid var(--line); align-items:end; }
    main { min-height:0; display:grid; grid-template-columns:clamp(280px, 24vw, 340px) minmax(0, 1fr); }
    section { min-height:0; padding:10px; border-right:1px solid var(--line); overflow:hidden; display:flex; flex-direction:column; gap:8px; }
    section:last-child { border-right:0; }
    section.inspector { overflow:hidden; display:grid; grid-template-columns:minmax(340px, 42%) minmax(420px, 1fr); gap:10px; }
    label { display:block; margin:0 0 4px; color: var(--muted); font-size: 11px; }
    input, select, button { font: inherit; }
    input, select { width:100%; height:30px; padding:5px 8px; border:1px solid var(--line); border-radius:6px; color:var(--ink); background:#0d1420; outline:none; }
    input:focus, select:focus { border-color:var(--accent); box-shadow:0 0 0 2px rgba(20,184,166,.14); }
    button { height:30px; border:1px solid var(--line); color:var(--ink); background:#101827; border-radius:6px; padding:0 10px; cursor:pointer; white-space:nowrap; }
    button.primary { background:var(--accent); color:#03110f; border-color:var(--accent); font-weight:600; }
    button:disabled { opacity:.55; cursor:not-allowed; }
    .field { min-width:0; }
    .path-field { display:grid; grid-template-columns:minmax(0, 1fr) auto; gap:6px; }
    .actions, .toolbar { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
    .muted { color: var(--muted); }
    .status { display:inline-flex; align-items:center; justify-content:center; min-width:42px; padding:1px 6px; border-radius:999px; font-size:11px; background:#17202c; color:var(--muted); }
    .status.synced, .status.same { color:var(--ok); background:rgba(34,197,94,.11); }
    .status.different { color:var(--warn); background:rgba(234,179,8,.13); }
    .status.server-missing, .status.client-missing, .status.reference-missing { color:var(--bad); background:rgba(251,113,133,.12); }
    .status.no-reference { color:var(--muted); background:#17202c; }
    .panel-title { color:var(--muted); font-size:11px; display:flex; justify-content:space-between; gap:8px; align-items:center; min-height:18px; }
    .selected-path { color:#cbd5e1; font-size:12px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .tree { flex:1; min-height:0; background:var(--panel); border:1px solid var(--line); overflow:auto; padding:6px; border-radius:6px; }
    .tree-node { margin:2px 0; }
    .node-line { display:grid; grid-template-columns:18px minmax(0, 1fr) auto; gap:6px; align-items:center; padding:4px 5px; border-radius:5px; cursor:pointer; }
    .node-line:hover, .node-line.selected { background:#172536; }
    .tree-children { margin-left:12px; border-left:1px solid #223044; padding-left:7px; }
    .node-name { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .kind, .type-pill { color:var(--muted); font-size:11px; }
    .tree .type-pill { display:none; }
    .table-wrap { flex:1; min-height:0; overflow:auto; border:1px solid var(--line); border-radius:6px; background:var(--panel); }
    table { width:100%; border-collapse:collapse; min-width:760px; }
    th, td { text-align:left; padding:7px 8px; border-bottom:1px solid var(--line); vertical-align:top; }
    th { font-size:11px; color:var(--muted); background:#101722; position:sticky; top:0; z-index:1; }
    td { font-size:12px; }
    tr { cursor:pointer; }
    tr:hover, tr.selected { background:#162234; }
    code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size:11px; color:#dbeafe; }
    .inspect-column { min-height:0; display:flex; flex-direction:column; gap:8px; overflow:hidden; }
    .preview-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; min-height:240px; max-height:320px; }
    .preview-card { min-width:0; display:flex; flex-direction:column; border:1px solid var(--line); border-radius:6px; background:var(--panel); overflow:hidden; }
    .preview-head { height:28px; padding:6px 8px; color:var(--muted); border-bottom:1px solid var(--line); font-size:11px; }
    .preview-body { flex:1; min-height:210px; display:flex; align-items:center; justify-content:center; overflow:auto; }
    .preview-body img { image-rendering:auto; max-width:100%; height:auto; background: repeating-conic-gradient(#182231 0 25%, #0f1722 0 50%) 50% / 18px 18px; }
    .details-panel { flex:1; min-height:0; background:var(--panel); border:1px solid var(--line); padding:10px; border-radius:6px; overflow:auto; }
    .details-panel h3 { margin:0 0 8px; font-size:13px; font-weight:600; }
    .source-browser { flex:1; min-height:190px; display:flex; flex-direction:column; gap:6px; }
    .source-tree { min-height:0; }
    .source-details { flex:0 0 220px; }
    .edit-grid { display:grid; grid-template-columns:72px minmax(0, 1fr); gap:6px 8px; align-items:center; margin-top:10px; padding-top:10px; border-top:1px solid var(--line); }
    .edit-grid label { margin:0; }
    .advanced-json { flex:0 0 auto; border:1px solid var(--line); border-radius:6px; padding:8px; background:var(--panel); }
    .advanced-json summary { cursor:pointer; color:var(--muted); font-size:11px; }
    .plan-fields { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
    .plan-column .plan-editor { flex:0 0 32%; min-height:120px; resize:none; }
    .plan-editor { width:100%; min-height:120px; resize:vertical; padding:8px; border:1px solid var(--line); border-radius:6px; color:var(--ink); background:var(--panel); font:11px/1.35 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    .kv { display:grid; grid-template-columns:72px minmax(0, 1fr); gap:5px 8px; margin:8px 0; }
    .kv div:nth-child(odd) { color:var(--muted); }
    .raw { margin-top:10px; }
    .raw summary { color:var(--muted); cursor:pointer; }
    pre { margin:8px 0 0; white-space:pre-wrap; color:#cbd5e1; font-size:11px; }
    .replace-panel { display:grid; grid-template-columns:1fr; gap:8px; padding:8px 10px; background:#090d14; border-top:1px solid var(--line); }
    .replace-row { min-width:0; display:grid; gap:8px; align-items:end; }
    .replace-row-primary { grid-template-columns:minmax(170px, 1fr) minmax(150px, .85fr) 96px 112px auto auto minmax(220px, 1fr); }
    .replace-row-node { grid-template-columns:minmax(420px, 1.2fr) minmax(420px, 1fr); }
    .drop input { height:30px; padding:4px 6px; }
    .result { min-height:30px; max-height:70px; color:var(--muted); white-space:pre-wrap; overflow:auto; text-overflow:ellipsis; align-self:end; }
    .add-node-panel { display:grid; grid-template-columns:minmax(82px, 1fr) 96px minmax(86px, 1fr) minmax(86px, 1fr) auto; gap:6px; align-items:end; }
    .add-node-panel .vector-only { display:none; }
    .add-node-panel.vector-mode { grid-template-columns:minmax(82px, 1fr) 96px 70px 70px auto; }
    .add-node-panel.vector-mode .value-only { display:none; }
    .add-node-panel.vector-mode .vector-only { display:block; }
    .copy-node-panel { display:grid; grid-template-columns:auto minmax(120px, 1fr) auto; gap:6px; align-items:end; }
    .copy-node-panel label { grid-column:1 / -1; }
    .modal { position:fixed; inset:0; display:none; align-items:center; justify-content:center; background:rgba(0,0,0,.62); z-index:10; }
    .modal.open { display:flex; }
    .picker { width:min(840px, calc(100vw - 40px)); height:min(620px, calc(100vh - 40px)); display:grid; grid-template-rows:auto auto minmax(0, 1fr); background:#0c121b; border:1px solid var(--line); border-radius:8px; box-shadow:0 18px 60px rgba(0,0,0,.45); overflow:hidden; }
    .picker-head, .picker-path { display:flex; gap:8px; align-items:center; padding:10px; border-bottom:1px solid var(--line); }
    .picker-head strong { margin-right:auto; font-size:13px; }
    .picker-list { overflow:auto; padding:6px; }
    .picker-row { width:100%; height:auto; min-height:30px; display:grid; grid-template-columns:22px minmax(0, 1fr) auto; gap:8px; align-items:center; text-align:left; margin:2px 0; border:0; background:transparent; color:var(--ink); }
    .picker-row:hover { background:#172536; }
    .picker-row .name { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .picker-row .size { color:var(--muted); font-size:11px; }
    @media (max-width: 1180px) {
      .topbar { grid-template-columns:70px 120px 1fr 1fr; }
      .actions { grid-column:auto; }
      .replace-row-primary { grid-template-columns:1fr 1fr auto auto; }
      .replace-row-primary .result { grid-column:1 / -1; }
      .replace-row-node { grid-template-columns:1fr; }
      main { grid-template-columns:1fr; grid-template-rows:minmax(300px, 38%) minmax(480px, 62%); }
      section.inspector { border-top:1px solid var(--line); grid-template-columns:1fr; grid-template-rows:auto minmax(280px, 1fr); }
    }
  </style>
</head>
<body>
  <header>
    <strong>Skill IMG Workbench</strong>
    <span class="muted">项目 IMG / 其他服 IMG / 服务端 XML</span>
    <span id="summary" class="muted"></span>
  </header>
  <div class="topbar">
    <div class="field"><label>IMG</label><input id="skillImg" value="122" /></div>
    <div class="field"><label>根路径</label><input id="rootPath" placeholder="留空为根节点" /></div>
    <div class="field"><label>本项目 .img</label><div class="path-field"><input id="imgPath" value="clien/Data/Skill/122.img" /><button data-pick="imgPath" data-kind="img">选择</button></div></div>
    <div class="field"><label>其他服 .img</label><div class="path-field"><input id="referenceImgPath" placeholder="/path/to/other/Skill/122.img" /><button data-pick="referenceImgPath" data-kind="reference">选择</button></div></div>
    <div class="field"><label>服务端 .img.xml</label><div class="path-field"><input id="xmlPath" value="gms-server/wz/Skill.wz/122.img.xml" /><button data-pick="xmlPath" data-kind="xml">选择</button></div></div>
    <div class="actions">
      <button class="primary" id="loadBtn">读取</button>
      <button id="syncBtn" disabled>同步 XML</button>
    </div>
  </div>
  <main>
    <section>
      <div class="panel-title"><span id="treePath"></span><span id="rowCount"></span></div>
      <div class="selected-path" id="parentPath"></div>
      <div class="tree" id="tree"></div>
    </section>
    <section class="inspector">
      <div class="inspect-column preview-column">
        <div class="panel-title">预览</div>
        <div class="preview-grid" id="preview"></div>
        <div class="panel-title">节点说明与差异</div>
        <div class="details-panel" id="details"></div>
      </div>
      <div class="inspect-column plan-column">
        <div class="source-browser">
          <div class="panel-title">
            <span>其他服 IMG 树</span>
            <span class="actions">
              <span id="sourceRowCount"></span>
              <button id="dryReplaceSourceBtn">预览替换</button>
              <button class="primary" id="replaceSourceBtn">替换选中</button>
              <button id="dryAppendSourceBtn">预览追加</button>
              <button class="primary" id="appendSourceBtn">追加到目录</button>
            </span>
          </div>
          <div class="selected-path" id="sourcePathLabel"></div>
          <div class="tree source-tree" id="sourceTree"></div>
        </div>
        <div class="panel-title">其他服节点说明</div>
        <div class="details-panel source-details" id="sourceDetails"></div>
        <details class="advanced-json">
          <summary>高级 JSON</summary>
          <div class="panel-title">
            <span>计划 JSON</span>
            <span class="actions">
              <button id="analyzePlanBtn">分析选中</button>
              <button id="dryApplyPlanBtn">预览 JSON</button>
              <button class="primary" id="applyPlanBtn">应用 JSON</button>
            </span>
          </div>
          <div class="plan-fields">
            <div class="field"><label>来源路径(其他服)</label><input id="planSourcePath" placeholder="留空为其他服根节点" /></div>
            <div class="field"><label>目标路径(本项目)</label><input id="planTargetPath" placeholder="client/img/node/path" /></div>
          </div>
          <textarea id="planJson" class="plan-editor" spellcheck="false"></textarea>
        </details>
      </div>
    </section>
  </main>
  <div class="replace-panel">
    <div class="replace-row replace-row-primary">
      <div class="field drop"><label>批量替换 PNG</label><input id="files" type="file" accept="image/png" multiple /></div>
      <div class="field drop"><label>单图 PNG</label><input id="singleFile" type="file" accept="image/png" /></div>
      <div class="field"><label>命名</label><select id="nameMode"><option value="index">按序号</option><option value="stem">使用文件名</option></select></div>
      <div class="field"><label>原点</label><select id="origin"><option value="keep">保持</option><option value="center">居中</option><option value="bottom-left">左下</option><option value="bottom-center">底中</option></select></div>
      <div class="actions">
        <button id="dryReplaceBtn" disabled>预览替换</button>
        <button class="primary" id="replaceBtn" disabled>写入同步</button>
      </div>
      <div class="actions">
        <button id="deleteNodeBtn" disabled>删除节点</button>
        <button id="replaceNodeBtn" disabled>替换选中</button>
      </div>
      <div class="result" id="result"></div>
    </div>
    <div class="replace-row replace-row-node">
      <div class="add-node-panel" id="addNodePanel">
        <div class="field"><label>节点名</label><input id="newNodeName" placeholder="如 z 或 0" /></div>
        <div class="field"><label>类型</label><select id="newNodeType"><option value="int">整数</option><option value="imgdir">目录</option><option value="string">字符串</option><option value="vector">坐标</option><option value="uol">引用</option></select></div>
        <div class="field value-only"><label>值</label><input id="newNodeValue" placeholder="默认空/0" /></div>
        <div class="field vector-only"><label>x</label><input id="newNodeX" type="number" value="0" /></div>
        <div class="field vector-only"><label>y</label><input id="newNodeY" type="number" value="0" /></div>
        <button id="addNodeBtn" disabled>添加节点</button>
      </div>
      <div class="copy-node-panel">
        <label id="copyNodeLabel">未复制节点</label>
        <button id="copyNodeBtn" disabled>复制节点</button>
        <input id="copyNodeName" placeholder="粘贴名，默认原名" />
        <button id="pasteNodeBtn" disabled>粘贴到当前</button>
      </div>
    </div>
  </div>
  <div class="modal" id="pickerModal">
    <div class="picker">
      <div class="picker-head">
        <strong id="pickerTitle">选择文件</strong>
        <button id="pickerProjectBtn">项目</button>
        <button id="pickerHomeBtn">用户目录</button>
        <button id="pickerCloseBtn">关闭</button>
      </div>
      <div class="picker-path">
        <button id="pickerUpBtn">上级</button>
        <input id="pickerPath" />
        <button id="pickerGoBtn">打开</button>
      </div>
      <div class="picker-list" id="pickerList"></div>
    </div>
  </div>
  <script>
    let state = null;
    let selectedPath = null;
    let expandedPaths = new Set();
    let referenceExpandedPaths = new Set([""]);
    let selectedReferencePath = "";
    let selectedReferenceNode = null;
    let currentRows = [];
    let pickerTarget = null;
    let pickerKind = "img";
    let pickerRoots = [];
    let copiedNodePath = "";

    const $ = id => document.getElementById(id);
    const textMeta = m => {
      if (!m || m.type === "missing") return "missing";
      if (m.type === "not-loaded") return "未选择";
      const origin = m.origin ? ` origin=${m.origin.x},${m.origin.y}` : "";
      const ints = m.ints ? " " + Object.entries(m.ints).map(([k,v]) => `${k}=${v}`).join(" ") : "";
      if (m.type === "canvas") return `${m.width}x${m.height}${origin}${ints}`;
      if (m.type === "uol") return `uol -> ${m.target}`;
      if (m.type === "vector") return `(${m.value?.x ?? 0},${m.value?.y ?? 0})`;
      if (m.value !== undefined) return `${m.type}=${m.value}`;
      return `${m.type}`;
    };
    const statusText = s => ({
      synced: "同步",
      same: "相同",
      different: "不同",
      "server-missing": "缺XML",
      "client-missing": "缺项目",
      "reference-missing": "缺对照",
      "no-reference": "未选",
      missing: "缺失"
    }[s] || s);
    const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[ch]));
    const setResult = value => { $("result").textContent = value || ""; };

    function formatSize(bytes) {
      if (!Number.isFinite(bytes)) return "";
      if (bytes < 1024) return `${bytes} B`;
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
      return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    }

    async function browse(path) {
      const qs = new URLSearchParams({path: path || "", kind: pickerKind});
      const res = await fetch(`/api/browse?${qs}`);
      const data = await res.json();
      if (!data.ok) throw new Error(data.reason);
      pickerRoots = data.roots || [];
      $("pickerPath").value = data.path;
      $("pickerList").innerHTML = "";
      for (const dir of data.dirs) {
        const row = document.createElement("button");
        row.className = "picker-row";
        row.innerHTML = `<span>&gt;</span><span class="name">${esc(dir.name)}</span><span class="size">目录</span>`;
        row.onclick = () => browse(dir.path).catch(e => setResult(e.message));
        $("pickerList").appendChild(row);
      }
      for (const file of data.files) {
        const row = document.createElement("button");
        row.className = "picker-row";
        row.innerHTML = `<span>-</span><span class="name">${esc(file.name)}</span><span class="size">${formatSize(file.size)}</span>`;
        row.onclick = () => {
          if (pickerTarget) $(pickerTarget).value = file.path;
          $("pickerModal").classList.remove("open");
        };
        $("pickerList").appendChild(row);
      }
      $("pickerUpBtn").onclick = () => browse(data.parent).catch(e => setResult(e.message));
    }

    function openPicker(targetId, kind) {
      pickerTarget = targetId;
      pickerKind = kind;
      $("pickerTitle").textContent = kind === "xml" ? "选择服务端 XML" : "选择客户端 IMG";
      $("pickerModal").classList.add("open");
      browse($(targetId).value).catch(e => setResult(e.message));
    }

    function params(selected = null) {
      const values = {
        skill_img: $("skillImg").value,
        root_path: $("rootPath").value,
        img_path: $("imgPath").value,
        reference_img_path: $("referenceImgPath").value,
        xml_path: $("xmlPath").value,
      };
      if (selected !== null) values.selected_path = selected;
      return new URLSearchParams(values);
    }

    function syncPlanPathInputs(path) {
      const value = path || "";
      $("planTargetPath").value = value;
    }

    async function load(selected = null) {
      setResult("");
      const res = await fetch(`/api/load?${params(selected)}`);
      const data = await res.json();
      if (!data.ok) throw new Error(data.reason);
      state = data;
      selectedPath = data.selectedPath;
      currentRows = data.tree?.children || data.rows;
      expandedPaths = new Set(parentPaths(data.selectedPath));
      $("summary").textContent = data.referenceImgPath ? `已加载对照: ${data.referenceImgPath}` : "未选择其他服 IMG";
      $("parentPath").textContent = data.selectedPath || "<root>";
      $("treePath").textContent = data.treePath || "<root>";
      $("rowCount").textContent = `${data.rows.length} 个节点`;
      syncPlanPathInputs(selectedPath);
      updateActionButtons(data.clientParent.type);
      selectedReferencePath = $("planSourcePath").value.trim();
      selectedReferenceNode = findReferenceTreeNode(data.referenceTree, selectedReferencePath);
      if (!selectedReferenceNode) selectedReferencePath = "";
      selectedReferenceNode = findReferenceTreeNode(data.referenceTree, selectedReferencePath);
      referenceExpandedPaths = new Set(parentPaths(selectedReferencePath));
      renderTree();
      renderReferenceTree();
      renderRows();
      renderEmptyPreview();
      renderReferenceDetails(selectedReferenceNode);
      renderDetails({
        path: data.selectedPath || "<root>",
        meaning: "当前选中节点。",
        client: data.clientParent,
        reference: data.referenceParent,
        server: data.serverParent,
        compareStatus: compareStatus(data.clientParent, data.referenceParent),
        syncStatus: syncStatus(data.clientParent, data.serverParent),
      });
    }

    function parentPaths(path) {
      const parts = (path || "").split("/").filter(Boolean);
      const out = [""];
      for (let i = 1; i <= parts.length; i++) out.push(parts.slice(0, i).join("/"));
      return out;
    }

    function normalize(m) {
      return {
        type: m?.type,
        width: m?.width,
        height: m?.height,
        origin: m?.origin,
        ints: m?.ints || {},
        target: m?.target,
        value: m?.value,
      };
    }

    function compareStatus(client, reference) {
      if (!reference || reference.type === "not-loaded") return "no-reference";
      if (client?.type === "missing" && reference.type === "missing") return "missing";
      if (reference.type === "missing") return "reference-missing";
      if (client?.type === "missing") return "client-missing";
      return JSON.stringify(normalize(client)) === JSON.stringify(normalize(reference)) ? "same" : "different";
    }

    function syncStatus(client, server) {
      if (client?.type === "missing" && server?.type === "missing") return "missing";
      if (server?.type === "missing") return "server-missing";
      if (client?.type === "missing") return "client-missing";
      return JSON.stringify(normalize(client)) === JSON.stringify(normalize(server)) ? "synced" : "different";
    }

    function renderTree() {
      $("tree").innerHTML = "";
      if (!state.tree) return;
      $("tree").appendChild(treeNode(state.tree));
    }

    function renderReferenceTree() {
      $("sourceTree").innerHTML = "";
      if (!state.referenceTree) {
        $("sourcePathLabel").textContent = "未选择其他服 IMG";
        $("sourceRowCount").textContent = "";
        return;
      }
      const count = treeSize(state.referenceTree) - 1;
      $("sourceRowCount").textContent = `${Math.max(count, 0)} 个节点`;
      $("sourcePathLabel").textContent = selectedReferencePath || "<root>";
      $("sourceTree").appendChild(referenceTreeNode(state.referenceTree));
    }

    function treeSize(node) {
      if (!node) return 0;
      return 1 + (node.children || []).reduce((sum, child) => sum + treeSize(child), 0);
    }

    function treeNode(node) {
      const wrap = document.createElement("div");
      wrap.className = "tree-node";
      const line = document.createElement("div");
      const hasChildren = node.children && node.children.length;
      const expanded = expandedPaths.has(node.path);
      line.className = `node-line ${node.path === selectedPath ? "selected" : ""}`;
      line.innerHTML = `<div class="kind">${hasChildren ? (expanded ? "-" : "+") : ""}</div>
        <div class="node-name"><code>${esc(node.name)}</code></div>
        <div class="type-pill">P:${esc(node.client.type)}</div>
        <div class="type-pill">O:${esc(node.reference.type)}</div>
        <span class="status ${node.compareStatus}">${statusText(node.compareStatus)}</span>`;
      line.title = `${node.path}\n${node.meaning}`;
      line.onclick = (event) => {
        event.stopPropagation();
        if (hasChildren) {
          if (expanded) expandedPaths.delete(node.path);
          else expandedPaths.add(node.path);
        }
        selectNode(node);
      };
      wrap.appendChild(line);
      if (hasChildren && expanded) {
        const children = document.createElement("div");
        children.className = "tree-children";
        for (const child of node.children) children.appendChild(treeNode(child));
        wrap.appendChild(children);
      }
      return wrap;
    }

    function referenceTreeNode(node) {
      const wrap = document.createElement("div");
      wrap.className = "tree-node";
      const line = document.createElement("div");
      const hasChildren = node.children && node.children.length;
      const expanded = referenceExpandedPaths.has(node.path);
      line.className = `node-line ${node.path === selectedReferencePath ? "selected" : ""}`;
      line.innerHTML = `<div class="kind">${hasChildren ? (expanded ? "-" : "+") : ""}</div>
        <div class="node-name"><code>${esc(node.name)}</code></div>
        <span class="status">${esc(node.meta?.type || "")}</span>`;
      line.title = `${node.path || "<root>"}\n${node.meaning || ""}`;
      line.onclick = (event) => {
        event.stopPropagation();
        if (hasChildren) {
          if (expanded) referenceExpandedPaths.delete(node.path);
          else referenceExpandedPaths.add(node.path);
        }
        selectReferenceNode(node, false);
      };
      wrap.appendChild(line);
      if (hasChildren && expanded) {
        const children = document.createElement("div");
        children.className = "tree-children";
        for (const child of node.children) children.appendChild(referenceTreeNode(child));
        wrap.appendChild(children);
      }
      return wrap;
    }

    function renderRows() {
      $("parentPath").textContent = selectedPath || "<root>";
      $("rowCount").textContent = `${currentRows.length} 个节点`;
      const rows = $("rows");
      if (!rows) return;
      rows.innerHTML = "";
      for (const row of currentRows) {
        const tr = document.createElement("tr");
        tr.className = row.path === selectedPath ? "selected" : "";
        tr.innerHTML = `<td><code>${esc(row.name)}</code><br><code>${esc(row.path || "<root>")}</code></td>
          <td>${esc(textMeta(row.client))}</td>
          <td>${esc(textMeta(row.reference))}</td>
          <td>${esc(textMeta(row.server))}</td>
          <td><span class="status ${row.compareStatus}">${statusText(row.compareStatus)}</span></td>
          <td><span class="status ${row.syncStatus}">${statusText(row.syncStatus)}</span></td>`;
        tr.onclick = () => selectRow(row);
        $("rows").appendChild(tr);
      }
    }

    function findTreeNode(node, path) {
      if (!node) return null;
      if (node.path === path) return node;
      for (const child of node.children || []) {
        const found = findTreeNode(child, path);
        if (found) return found;
      }
      return null;
    }

    function findReferenceTreeNode(node, path) {
      if (!node) return null;
      const normalized = path || "";
      if (node.path === normalized) return node;
      for (const child of node.children || []) {
        const found = findReferenceTreeNode(child, normalized);
        if (found) return found;
      }
      return null;
    }

    async function selectRow(row) {
      const node = findTreeNode(state.tree, row.path) || row;
      await selectNode(node);
    }

    async function selectNode(node) {
      selectedPath = node.path;
      currentRows = node.children || [];
      syncPlanPathInputs(selectedPath);
      renderTree();
      renderRows();
      updateActionButtons(node.client.type);
      refreshCopyNodeFields();
      renderDetails(node);
      renderPreview(node);
    }

    function selectReferenceNode(node, expandParents) {
      selectedReferencePath = node.path || "";
      selectedReferenceNode = node;
      $("planSourcePath").value = selectedReferencePath;
      if (expandParents) {
        referenceExpandedPaths = new Set([...referenceExpandedPaths, ...parentPaths(selectedReferencePath)]);
      }
      renderReferenceTree();
      const targetNode = findTreeNode(state.tree, selectedPath);
      if (targetNode) renderPreview(targetNode);
      renderReferenceDetails(node);
      setResult(`已选择来源节点: ${selectedReferencePath || "<root>"}`);
    }

    function previewCard(title, body) {
      return `<div class="preview-card"><div class="preview-head">${title}</div><div class="preview-body">${body || '<span class="muted">选择 canvas</span>'}</div></div>`;
    }

    function renderEmptyPreview() {
      $("preview").innerHTML = previewCard("本项目", "") + previewCard("其他服", "");
    }

    function renderPreview(item) {
      const refNode = selectedReferenceNode || findReferenceTreeNode(state.referenceTree, $("planSourcePath").value.trim());
      const refPath = refNode ? refNode.path : item.path;
      const refMeta = refNode ? refNode.meta : item.reference;
      const current = item.client?.type === "canvas"
        ? `<img src="/api/canvas.png?img_path=${encodeURIComponent(state.imgPath)}&path=${encodeURIComponent(item.path)}&t=${Date.now()}" alt="${item.path}">`
        : '<span class="muted">非 canvas</span>';
      const reference = refMeta?.type === "canvas" && state.referenceImgPath
        ? `<img src="/api/canvas.png?img_path=${encodeURIComponent(state.referenceImgPath)}&path=${encodeURIComponent(refPath)}&t=${Date.now()}" alt="${refPath}">`
        : `<span class="muted">${state.referenceImgPath ? "非 canvas" : "未选择其他服 IMG"}</span>`;
      $("preview").innerHTML = previewCard("本项目", current) + previewCard("其他服", reference);
    }

    function renderDetails(item) {
      const box = $("details");
      box.innerHTML = "";
      const h = document.createElement("h3");
      h.textContent = item.path || selectedPath || "";
      box.appendChild(h);
      const desc = document.createElement("div");
      desc.className = "muted";
      desc.textContent = item.meaning || "";
      box.appendChild(desc);

      const kv = document.createElement("div");
      kv.className = "kv";
      const fields = [
        ["本服", textMeta(item.client)],
        ["服务端", textMeta(item.server)],
        ["类型", item.client?.type || "missing"],
        ["XML", statusText(item.syncStatus)],
      ];
      for (const [keyText, valueText] of fields) {
        const key = document.createElement("div");
        key.textContent = keyText;
        const value = document.createElement("div");
        value.textContent = valueText;
        kv.appendChild(key);
        kv.appendChild(value);
      }
      box.appendChild(kv);
      renderEditForm(box, item);

      const raw = document.createElement("details");
      raw.className = "raw";
      const summary = document.createElement("summary");
      summary.textContent = "原始节点数据";
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify(item, null, 2);
      raw.appendChild(summary);
      raw.appendChild(pre);
      box.appendChild(raw);
    }

    function renderReferenceDetails(node) {
      const box = $("sourceDetails");
      box.innerHTML = "";
      if (!node) {
        box.innerHTML = '<span class="muted">未选择其他服节点</span>';
        return;
      }
      const h = document.createElement("h3");
      h.textContent = node.path || "<root>";
      box.appendChild(h);
      const desc = document.createElement("div");
      desc.className = "muted";
      desc.textContent = node.meaning || "";
      box.appendChild(desc);
      const kv = document.createElement("div");
      kv.className = "kv";
      for (const [keyText, valueText] of [["类型", node.meta?.type || ""], ["数值", textMeta(node.meta)]]) {
        const key = document.createElement("div");
        key.textContent = keyText;
        const value = document.createElement("div");
        value.textContent = valueText;
        kv.appendChild(key);
        kv.appendChild(value);
      }
      box.appendChild(kv);
      const raw = document.createElement("details");
      raw.className = "raw";
      const summary = document.createElement("summary");
      summary.textContent = "原始节点数据";
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify(node, null, 2);
      raw.appendChild(summary);
      raw.appendChild(pre);
      box.appendChild(raw);
    }

    function editableKind(meta) {
      if (!meta) return "";
      if (["int", "string", "uol", "vector"].includes(meta.type)) return meta.type;
      return "";
    }

    function renderEditForm(box, item) {
      const kind = editableKind(item.client);
      if (!kind || item.path === "<root>") return;
      const form = document.createElement("div");
      form.className = "edit-grid";
      if (kind === "vector") {
        form.innerHTML = `<label>x</label><input id="editValueX" type="number" value="${esc(item.client.value?.x ?? 0)}" />
          <label>y</label><input id="editValueY" type="number" value="${esc(item.client.value?.y ?? 0)}" />
          <div></div><button class="primary" id="saveNodeValueBtn">保存同步</button>`;
      } else {
        form.innerHTML = `<label>值</label><input id="editValue" ${kind === "int" ? 'type="number"' : 'type="text"'} value="${esc(item.client.value ?? item.client.target ?? "")}" />
          <div></div><button class="primary" id="saveNodeValueBtn">保存同步</button>`;
      }
      box.appendChild(form);
      $("saveNodeValueBtn").onclick = () => saveSelectedValue(kind).catch(e => setResult(e.message));
    }

    function updateActionButtons(clientType) {
      $("syncBtn").disabled = clientType !== "canvas";
      $("dryReplaceBtn").disabled = clientType !== "imgdir" || !selectedPath;
      $("replaceBtn").disabled = clientType !== "imgdir" || !selectedPath;
      $("deleteNodeBtn").disabled = !selectedPath;
      $("replaceNodeBtn").disabled = !selectedPath;
      $("addNodeBtn").disabled = !["imgdir", "canvas"].includes(clientType) || !selectedPath;
      $("copyNodeBtn").disabled = !selectedPath;
      $("pasteNodeBtn").disabled = !copiedNodePath || !["imgdir", "canvas"].includes(clientType) || !selectedPath;
    }

    async function syncSelected() {
      if (!selectedPath) return;
      const res = await fetch("/api/sync_xml", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({img_path: state.imgPath, xml_path: state.xmlPath, paths: [selectedPath], backup: true, dry_run: false})
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.reason);
      setResult(`已同步 XML:\n${data.updates.map(u => u.canvas_path).join("\n")}`);
      await load(selectedPath);
    }

    async function replaceFrames(dryRun) {
      const files = $("files").files;
      if (!files.length) throw new Error("请选择 PNG 文件");
      const form = new FormData();
      form.append("img_path", state.imgPath);
      form.append("xml_path", state.xmlPath);
      form.append("canvas_dir", selectedPath);
      form.append("origin", $("origin").value);
      form.append("name_mode", $("nameMode").value);
      form.append("sync_xml", "1");
      form.append("backup", "1");
      form.append("dry_run", dryRun ? "1" : "0");
      for (const file of files) form.append("images", file, file.name);
      const res = await fetch("/api/replace", {method: "POST", body: form});
      const data = await res.json();
      if (!data.ok) throw new Error(data.reason);
      setResult(`${dryRun ? "预览" : "已写入"}:\n${data.updates.map(u => `${u.canvas_path}: ${u.old_width}x${u.old_height} -> ${u.width}x${u.height}`).join("\n")}`);
      if (!dryRun) await load(selectedPath);
    }

    function selectedParentPath() {
      const parts = (selectedPath || "").split("/").filter(Boolean);
      parts.pop();
      return parts.join("/");
    }

    function childPath(parent, name) {
      return `${(parent || "").replace(/\/+$/, "")}/${name.replace(/^\/+/, "")}`.replace(/^\/+/, "");
    }

    function singlePng() {
      const file = $("singleFile").files[0];
      if (!file) throw new Error("请选择单图 PNG");
      return file;
    }

    async function upsertCanvas(path, replaceExisting) {
      const file = singlePng();
      const form = new FormData();
      form.append("img_path", state.imgPath);
      form.append("xml_path", state.xmlPath);
      form.append("path", path);
      form.append("origin", $("origin").value);
      form.append("sync_xml", "1");
      form.append("backup", "1");
      form.append("dry_run", "0");
      form.append("replace_existing", replaceExisting ? "1" : "0");
      form.append("image", file, file.name);
      const res = await fetch("/api/upsert_canvas", {method: "POST", body: form});
      const data = await res.json();
      if (!data.ok) throw new Error(data.reason);
      setResult(`已写入:\n${data.update.canvas_path}: ${data.update.old_width}x${data.update.old_height} -> ${data.update.width}x${data.update.height}`);
      await load(path);
    }

    async function replaceSelectedNode() {
      if (!selectedPath) throw new Error("请选择要替换的节点");
      if (!confirm(`用单张 PNG 替换节点 ${selectedPath}？原节点如果是目录会被删除。`)) return;
      await upsertCanvas(selectedPath, true);
    }

    function newNodePayload(type) {
      if (type === "vector") {
        return {
          x: $("newNodeX").value,
          y: $("newNodeY").value,
        };
      }
      if (type === "int") return $("newNodeValue").value || "0";
      if (["string", "uol"].includes(type)) return $("newNodeValue").value;
      return null;
    }

    async function addNode() {
      if (!selectedPath) throw new Error("请选择父目录节点");
      const name = $("newNodeName").value.trim();
      if (!name) throw new Error("请输入新节点名");
      const type = $("newNodeType").value;
      const targetPath = childPath(selectedPath, name);
      const res = await fetch("/api/add_node", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          img_path: state.imgPath,
          xml_path: state.xmlPath,
          parent_path: selectedPath,
          name,
          type,
          value: newNodePayload(type),
          backup: true,
          dry_run: false,
        })
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.reason);
      setResult(`已添加并同步: ${data.path}`);
      await load(targetPath);
    }

    function refreshCopyNodeFields() {
      $("copyNodeLabel").textContent = copiedNodePath ? `已复制: ${copiedNodePath}` : "未复制节点";
      const targetNode = state ? findTreeNode(state.tree, selectedPath) : null;
      const targetType = targetNode?.client?.type || "";
      $("pasteNodeBtn").disabled = !copiedNodePath || !["imgdir", "canvas"].includes(targetType) || !selectedPath;
    }

    function copySelectedNode() {
      if (!selectedPath) throw new Error("请选择要复制的节点");
      copiedNodePath = selectedPath;
      $("copyNodeName").value = pathName(selectedPath);
      refreshCopyNodeFields();
      setResult(`已复制节点: ${copiedNodePath}`);
    }

    async function pasteCopiedNode() {
      if (!copiedNodePath) throw new Error("请先复制节点");
      if (!selectedPath) throw new Error("请选择目标父节点");
      const name = $("copyNodeName").value.trim();
      const targetName = name || pathName(copiedNodePath);
      const targetPath = childPath(selectedPath, targetName);
      if (!confirm(`复制 ${copiedNodePath} 到 ${targetPath}？同名节点存在时不会覆盖。`)) return;
      const res = await fetch("/api/copy_node", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          img_path: state.imgPath,
          xml_path: state.xmlPath,
          source_path: copiedNodePath,
          parent_path: selectedPath,
          name,
          backup: true,
          dry_run: false,
        })
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.reason);
      setResult(`已复制并同步:\n${data.sourcePath} -> ${data.path}`);
      await load(data.path);
    }

    async function deleteSelectedNode() {
      if (!selectedPath) throw new Error("请选择要删除的节点");
      if (!confirm(`删除节点 ${selectedPath}？客户端 IMG 和服务端 XML 中的同名节点都会删除。`)) return;
      const parent = selectedParentPath();
      const res = await fetch("/api/delete_node", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({img_path: state.imgPath, xml_path: state.xmlPath, path: selectedPath, backup: true, dry_run: false})
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.reason);
      setResult(`已删除 ${data.path}\nclient=${data.clientRemoved} xml=${data.xmlRemoved}`);
      await load(parent);
    }

    async function analyzePlan() {
      if (!selectedPath) throw new Error("请选择要分析的节点");
      if (!$("referenceImgPath").value.trim()) throw new Error("请先选择其他服 .img");
      const sourcePath = $("planSourcePath").value.trim();
      const targetPath = $("planTargetPath").value.trim() || selectedPath;
      const res = await fetch("/api/analyze_plan", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          img_path: state.imgPath,
          reference_img_path: $("referenceImgPath").value,
          xml_path: state.xmlPath,
          source_path: sourcePath,
          target_path: targetPath,
        })
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.reason);
      $("planJson").value = JSON.stringify(data.plan, null, 2);
      setResult(`已生成 JSON 计划:\n${sourcePath} -> ${targetPath}`);
    }

    async function applyPlan(dryRun) {
      const raw = $("planJson").value.trim();
      if (!raw) throw new Error("计划 JSON 为空");
      const plan = JSON.parse(raw);
      if (!dryRun && !confirm("按计划 JSON 更新本项目 IMG，并同步服务端 XML？")) return;
      const res = await fetch("/api/apply_plan", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          plan,
          img_path: state.imgPath,
          reference_img_path: $("referenceImgPath").value || plan.sourceImg,
          xml_path: state.xmlPath,
          dry_run: dryRun,
          backup: true,
        })
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.reason);
      setResult(`${dryRun ? "JSON 预览通过" : "JSON 已应用"}:\n${data.applied.map(item => `${item.op}: ${item.sourcePath || ""} -> ${item.targetPath}`).join("\n")}`);
      if (!dryRun) await load(selectedPath);
    }

    function pathName(path) {
      const parts = (path || "").split("/").filter(Boolean);
      return parts[parts.length - 1] || "";
    }

    function selectedCopyPlan(mode) {
      if (!selectedPath) throw new Error("请选择本项目目标节点");
      if (!$("referenceImgPath").value.trim()) throw new Error("请先选择其他服 .img");
      const sourcePath = $("planSourcePath").value.trim();
      let targetPath = selectedPath;
      if (mode === "append") {
        if (!sourcePath) throw new Error("追加时请选择其他服的具体节点");
        const targetNode = findTreeNode(state.tree, selectedPath);
        if (targetNode?.client?.type !== "imgdir") throw new Error("追加时请选择本项目目录节点");
        const name = selectedReferenceNode?.name || pathName(sourcePath);
        if (!name) throw new Error("无法从来源节点确定名称");
        targetPath = childPath(selectedPath, name);
      }
      if (!targetPath) throw new Error("请选择本项目目标节点");
      return {
        version: 1,
        kind: "png2canvas-node-plan",
        sourceImg: $("referenceImgPath").value,
        targetImg: state.imgPath,
        serverXml: state.xmlPath,
        operations: [{
          op: "copyTree",
          sourcePath,
          targetPath,
          replace: true,
          syncXml: true,
        }],
      };
    }

    async function copySourceToSelected(dryRun, mode) {
      const plan = selectedCopyPlan(mode);
      const op = plan.operations[0];
      $("planJson").value = JSON.stringify(plan, null, 2);
      const action = mode === "append" ? "追加" : "替换";
      if (!dryRun && !confirm(`${action} ${op.sourcePath || "<root>"} 到 ${op.targetPath}？${mode === "append" ? "同名目标存在时会被替换" : "目标节点会被替换"}，并同步服务端 XML。`)) return;
      const res = await fetch("/api/apply_plan", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          plan,
          img_path: state.imgPath,
          reference_img_path: $("referenceImgPath").value,
          xml_path: state.xmlPath,
          dry_run: dryRun,
          backup: true,
        })
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.reason);
      setResult(`${dryRun ? `${action}预览通过` : `已${action}并同步`}:\n${data.applied.map(item => `${item.sourcePath || "<root>"} -> ${item.targetPath}`).join("\n")}`);
      if (!dryRun) await load(op.targetPath);
    }

    async function saveSelectedValue(kind) {
      if (!selectedPath) throw new Error("请选择本服节点");
      let value;
      if (kind === "vector") {
        value = {
          x: $("editValueX").value,
          y: $("editValueY").value,
        };
      } else {
        value = $("editValue").value;
      }
      const res = await fetch("/api/update_node_value", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          img_path: state.imgPath,
          xml_path: state.xmlPath,
          path: selectedPath,
          value,
          backup: true,
          dry_run: false,
        })
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.reason);
      setResult(`已保存并同步: ${data.path}`);
      await load(selectedPath);
    }

    function refreshAddNodeFields() {
      const type = $("newNodeType").value;
      $("addNodePanel").classList.toggle("vector-mode", type === "vector");
      if (type === "imgdir") $("newNodeValue").placeholder = "无需填写";
      else if (type === "int") $("newNodeValue").placeholder = "默认 0";
      else if (type === "uol") $("newNodeValue").placeholder = "引用路径";
      else $("newNodeValue").placeholder = "默认空";
    }

    $("loadBtn").onclick = () => load().catch(e => setResult(e.message));
    $("syncBtn").onclick = () => syncSelected().catch(e => setResult(e.message));
    $("dryReplaceBtn").onclick = () => replaceFrames(true).catch(e => setResult(e.message));
    $("replaceBtn").onclick = () => replaceFrames(false).catch(e => setResult(e.message));
    $("deleteNodeBtn").onclick = () => deleteSelectedNode().catch(e => setResult(e.message));
    $("replaceNodeBtn").onclick = () => replaceSelectedNode().catch(e => setResult(e.message));
    $("addNodeBtn").onclick = () => addNode().catch(e => setResult(e.message));
    $("copyNodeBtn").onclick = () => copySelectedNode().catch(e => setResult(e.message));
    $("pasteNodeBtn").onclick = () => pasteCopiedNode().catch(e => setResult(e.message));
    $("dryReplaceSourceBtn").onclick = () => copySourceToSelected(true, "replace").catch(e => setResult(e.message));
    $("replaceSourceBtn").onclick = () => copySourceToSelected(false, "replace").catch(e => setResult(e.message));
    $("dryAppendSourceBtn").onclick = () => copySourceToSelected(true, "append").catch(e => setResult(e.message));
    $("appendSourceBtn").onclick = () => copySourceToSelected(false, "append").catch(e => setResult(e.message));
    $("analyzePlanBtn").onclick = () => analyzePlan().catch(e => setResult(e.message));
    $("dryApplyPlanBtn").onclick = () => applyPlan(true).catch(e => setResult(e.message));
    $("applyPlanBtn").onclick = () => applyPlan(false).catch(e => setResult(e.message));
    $("newNodeType").onchange = refreshAddNodeFields;
    $("planSourcePath").addEventListener("input", () => {
      if (!state) return;
      selectedReferencePath = $("planSourcePath").value.trim();
      selectedReferenceNode = findReferenceTreeNode(state.referenceTree, selectedReferencePath);
      referenceExpandedPaths = new Set([...referenceExpandedPaths, ...parentPaths(selectedReferencePath)]);
      renderReferenceTree();
      const targetNode = findTreeNode(state.tree, selectedPath);
      if (targetNode) renderPreview(targetNode);
    });
    document.querySelectorAll("[data-pick]").forEach(button => {
      button.onclick = () => openPicker(button.dataset.pick, button.dataset.kind || "img");
    });
    $("pickerCloseBtn").onclick = () => $("pickerModal").classList.remove("open");
    $("pickerGoBtn").onclick = () => browse($("pickerPath").value).catch(e => setResult(e.message));
    $("pickerPath").addEventListener("keydown", event => {
      if (event.key === "Enter") browse($("pickerPath").value).catch(e => setResult(e.message));
    });
    $("pickerProjectBtn").onclick = () => {
      const root = pickerRoots.find(item => item.name === "项目");
      if (root) browse(root.path).catch(e => setResult(e.message));
    };
    $("pickerHomeBtn").onclick = () => {
      const root = pickerRoots.find(item => item.name === "用户目录");
      if (root) browse(root.path).catch(e => setResult(e.message));
    };
    $("pickerModal").addEventListener("click", event => {
      if (event.target === $("pickerModal")) $("pickerModal").classList.remove("open");
    });
    for (const id of ["skillImg", "rootPath"]) {
      $(id).addEventListener("change", () => {
        if (id === "skillImg") {
          $("imgPath").value = `clien/Data/Skill/${$("skillImg").value}.img`;
          $("xmlPath").value = `gms-server/wz/Skill.wz/${$("skillImg").value}.img.xml`;
        }
      });
    }
    refreshAddNodeFields();
    load().catch(e => setResult(e.message));
  </script>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
