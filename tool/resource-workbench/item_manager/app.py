from __future__ import annotations

import copy
import hashlib
import io
import os
import re
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
import xml.parsers.expat
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request, send_file

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WZPY_ROOT = ROOT / "tool" / "wz-python"
MIGRATION_ROOT = ROOT / "tool" / "scripts" / "migration"
for dependency in (WZPY_ROOT, MIGRATION_ROOT):
    if str(dependency) not in sys.path:
        sys.path.insert(0, str(dependency))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzKey,
    WzRawDataProperty,
    WzSoundProperty,
    WzSubProperty,
)
from wzpy.properties import WzVideoProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.incremental_img import mutate_img, replace_img_record, scan_img  # noqa: E402
from wzpy.incremental_xml import mutate_xml  # noqa: E402
from wzpy.writer import _encode_property_list, encode_image_type_string  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402

import migrate_arcane_river_expansion as arc  # noqa: E402


TMS_DATA = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
CLIENT_ITEM = ROOT / "clien" / "Data" / "Item"
CLIENT_CHARACTER = ROOT / "clien" / "Data" / "Character"
SERVER_ITEM = ROOT / "gms-server" / "wz" / "Item.wz"
SERVER_CHARACTER = ROOT / "gms-server" / "wz" / "Character.wz"
CLIENT_STRING = ROOT / "clien" / "Data" / "String"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz"
ZH_STRING = ROOT / "gms-server" / "wz-zh-CN" / "String.wz"
BACKUP_ROOT = ROOT / ".workbuddy" / "resource-workbench-backups" / "items"
GMS_KEY = WzKey.for_region("GMS")
BMS_KEY = WzKey.for_region("BMS")


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    directory: str
    string_file: str | None
    string_parent: tuple[str, ...] = ()
    standalone: bool = False
    family: str = "item"
    migratable: bool = True
    target_directory: str | None = None
    target_string_parent: tuple[str, ...] | None = None
    id_prefixes: tuple[str, ...] = ()
    legacy_analogues: tuple[str, ...] = ()


CATEGORIES = {
    row.key: row for row in (
        Category("consume", "消耗物品", "Consume", "Consume.img"),
        Category("install", "设置物品", "Install", "Ins.img"),
        Category("etc", "其他／掉落物", "Etc", "Etc.img", ("Etc",)),
        Category("cash", "现金物品", "Cash", "Cash.img"),
        Category("pet", "宠物", "Pet", "Pet.img", standalone=True),
        Category("special", "特殊物品", "Special", None),
        Category(
            "quest_equip", "任务引用装备（兼容迁移）", "ArcaneForce", "Eqp.img",
            ("Eqp", "ArcaneForce"), standalone=True, family="character",
            target_directory="Weapon", target_string_parent=("Eqp", "Weapon"), id_prefixes=("1712",),
            legacy_analogues=("01302000.img", "01332111.img", "01702022.img"),
        ),
    )
}
EDITABLE_TYPES = {"Short", "Int", "Long", "Float", "Double", "String", "Vector", "UOL"}
BLOCKED_TYPES = (WzVideoProperty, WzRawDataProperty, WzSoundProperty)
_WRITE_LOCK = threading.RLock()

app = Flask(__name__, template_folder=str(HERE / "templates"), static_folder=str(HERE / "static"))


def _ok(**payload):
    return jsonify({"ok": True, **payload})


@app.errorhandler(Exception)
def _error(exc: Exception):
    status = 404 if isinstance(exc, (FileNotFoundError, KeyError)) else 400
    return jsonify({"ok": False, "reason": str(exc).strip("'")}), status


def _category(raw: Any) -> Category:
    key = str(raw or "").strip().lower()
    if key not in CATEGORIES:
        raise ValueError("物品分类无效")
    return CATEGORIES[key]


def _item_id(raw: Any) -> int:
    value = str(raw or "").strip()
    if not re.fullmatch(r"\d{7}", value):
        raise ValueError("物品 ID 必须是 7 位数字")
    return int(value)


def _expected_category(item_id: int) -> str | None:
    return {1: "quest_equip", 2: "consume", 3: "install", 4: "etc", 5: "cash", 9: "special"}.get(item_id // 1_000_000)


def _validate_category_id(category: Category, item_id: int) -> None:
    if category.key == "pet":
        if not str(item_id).startswith("500"):
            raise ValueError("宠物 ID 必须以 500 开头")
        return
    expected = _expected_category(item_id)
    if expected != category.key:
        raise ValueError(f"物品 ID {item_id} 不属于{category.label}")
    if category.id_prefixes and not str(item_id).startswith(category.id_prefixes):
        raise ValueError(f"物品 ID {item_id} 不属于当前兼容迁移范围")


def _category_directory(category: Category, scope: str) -> str:
    if scope == "local" and category.target_directory:
        return category.target_directory
    return category.directory


def _category_string_parent(category: Category, scope: str) -> tuple[str, ...]:
    if scope == "local" and category.target_string_parent is not None:
        return category.target_string_parent
    return category.string_parent


def _category_accepts_id(category: Category, item_id: str) -> bool:
    return not category.id_prefixes or item_id.startswith(category.id_prefixes)


def _record_candidates(item_id: int) -> tuple[str, ...]:
    return (f"0{item_id}", str(item_id))


def _group_file(category: Category, item_id: int, scope: str) -> Path:
    directory = _category_directory(category, scope)
    if category.family == "character":
        base = (TMS_DATA / "Character" if scope == "tms" else CLIENT_CHARACTER) / directory
    else:
        base = TMS_DATA / "Item" / directory if scope == "tms" else CLIENT_ITEM / directory
    if category.standalone:
        name = f"{item_id:08d}" if category.family == "character" else str(item_id)
        return base / f"{name}.img"
    padded = f"0{item_id}"
    if scope == "local":
        return base / f"{padded[:4]}.img"
    matches = [path for path in base.glob("*.img") if padded.startswith(path.stem) and path.stem.isdigit()]
    if not matches:
        return base / f"{padded[:4]}.img"
    return max(matches, key=lambda path: len(path.stem))


def _server_item_path(category: Category, item_id: int) -> Path:
    client = _group_file(category, item_id, "local")
    if category.family == "character":
        return SERVER_CHARACTER / _category_directory(category, "local") / f"{client.name}.xml"
    return SERVER_ITEM / _category_directory(category, "local") / f"{client.name}.xml"


def _load_image(path: Path, scope: str) -> WzImage:
    if not path.is_file():
        raise FileNotFoundError(f"IMG 不存在: {path}")
    region = "BMS" if scope == "tms" else "GMS"
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region(region), name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise ValueError(f"IMG 解析失败: {path.name}: {image.parse_warnings}")
    return image


def _item_node(image: WzImage, category: Category, item_id: int):
    if category.standalone:
        return image.root
    for name in _record_candidates(item_id):
        node = image.root.child(name)
        if node is not None:
            return node
    for node in image.root.children():
        if node.name.isdigit() and int(node.name) == item_id:
            return node
    raise KeyError(f"物品记录不存在: {item_id}")


@lru_cache(maxsize=256)
def _record_names(path_text: str, region: str, mtime_ns: int, size: int) -> frozenset[str]:
    del mtime_ns, size
    path = Path(path_text)
    return frozenset(record.name for record in scan_img(path.read_bytes(), region=region).root.records)


def _item_exists(category: Category, item_id: int, scope: str) -> bool:
    path = _group_file(category, item_id, scope)
    if not path.is_file():
        return False
    if category.standalone:
        return True
    region = "BMS" if scope == "tms" else "GMS"
    try:
        stat = path.stat()
        names = _record_names(str(path), region, stat.st_mtime_ns, stat.st_size)
    except Exception:
        return False
    return any(name in names for name in _record_candidates(item_id)) or any(
        name.isdigit() and int(name) == item_id for name in names
    )


def _resource_ids(category: Category, scope: str) -> frozenset[str]:
    directory = _category_directory(category, scope)
    if category.family == "character":
        base = (TMS_DATA / "Character" if scope == "tms" else CLIENT_CHARACTER) / directory
    else:
        base = (TMS_DATA / "Item" if scope == "tms" else CLIENT_ITEM) / directory
    if not base.is_dir():
        return frozenset()
    if category.standalone:
        return frozenset(
            item_id for path in base.glob("*.img")
            if re.fullmatch(r"\d{7,8}", path.stem)
            and _category_accepts_id(category, item_id := str(int(path.stem)))
        )
    region = "BMS" if scope == "tms" else "GMS"
    result: set[str] = set()
    for path in base.glob("*.img"):
        try:
            stat = path.stat()
            names = _record_names(str(path), region, stat.st_mtime_ns, stat.st_size)
        except Exception:
            continue
        for name in names:
            if name.isdigit() and len(str(int(name))) == 7:
                result.add(str(int(name)))
    return frozenset(result)


def _scalar_value(node) -> Any:
    if node.type_name == "Vector":
        return {"x": int(node.x), "y": int(node.y)}
    if isinstance(node, WzCanvasProperty):
        return {
            "width": int(node.width), "height": int(node.height),
            "format": int(node.format), "format2": int(node.format2),
            "linked": bool(node.child("_outlink") or node.child("_inlink")),
        }
    if isinstance(node, WzRawDataProperty):
        return {"bytes": int(getattr(node, "_data_length", 0))}
    if isinstance(node, WzSoundProperty):
        return {"lengthMs": int(node.length_ms), "bytes": int(getattr(node, "_data_length", 0))}
    if isinstance(node, WzSubProperty):
        return {"children": node.child_count()}
    value = getattr(node, "value", None)
    return value if isinstance(value, (str, int, float, bool, type(None))) else str(value)


def _walk_nodes(root) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def visit(parent, prefix: tuple[str, ...]) -> None:
        for child in parent.children():
            path = (*prefix, child.name)
            rows.append({
                "path": "/".join(path), "name": child.name, "type": child.type_name,
                "value": _scalar_value(child), "depth": len(path) - 1,
                "container": isinstance(child, WzSubProperty), "editable": child.type_name in EDITABLE_TYPES,
            })
            if hasattr(child, "children"):
                visit(child, path)

    visit(root, ())
    return rows


def _normalize_path(path: str) -> str:
    return "/".join("#" if part.isdigit() else part for part in path.split("/"))


@lru_cache(maxsize=128)
def _legacy_schema(category_key: str, file_name: str) -> frozenset[tuple[str, str]]:
    category = CATEGORIES[category_key]
    if category.legacy_analogues:
        base = CLIENT_CHARACTER / _category_directory(category, "local")
        schema: set[tuple[str, str]] = set()
        for analogue in category.legacy_analogues:
            path = base / analogue
            if not path.is_file():
                continue
            image = _load_image(path, "local")
            for row in _walk_nodes(image.root):
                schema.add((_normalize_path(row["path"]), row["type"]))
        return frozenset(schema)
    base = CLIENT_CHARACTER if category.family == "character" else CLIENT_ITEM
    path = base / _category_directory(category, "local") / file_name
    if not path.is_file() or category.standalone:
        return frozenset()
    image = _load_image(path, "local")
    schema: set[tuple[str, str]] = set()
    for record in image.root.children()[:400]:
        for row in _walk_nodes(record):
            schema.add((_normalize_path(row["path"]), row["type"]))
    return frozenset(schema)


def _compatibility(source_image: WzImage, source_node, source_path: Path, category: Category, item_id: int) -> dict[str, Any]:
    target = _group_file(category, item_id, "local")
    schema = _legacy_schema(category.key, target.name)
    issues: list[dict[str, Any]] = []
    if category.key == "quest_equip":
        issues.append({
            "level": "convert", "path": "资源分类", "title": "映射到旧端 Weapon 分类",
            "reason": "当前服务端按物品 ID 将 1712xxx 读取为 Weapon，旧客户端也没有 ArcaneForce 分类。",
            "resolution": "迁移时写入 Character/Weapon 与 Eqp/Weapon；保留任务奖励、名称和图标，不启用 ARC 属性或装备槽。",
            "automatic": True,
        })
    materializer = arc.CanvasMaterializer()
    for row in _walk_nodes(source_node):
        node = source_node.get(row["path"])
        path = row["path"]
        if isinstance(node, BLOCKED_TYPES):
            issues.append({
                "level": "blocker", "path": path, "title": f"旧端不支持 {row['type']} 节点",
                "reason": "该节点类型没有已验证的旧客户端解析契约，直接写入可能导致资源读取失败。",
                "resolution": "从迁移投影移除该节点，或先提供可工作的旧端同类节点作为兼容基线。",
                "automatic": False,
            })
            continue
        if isinstance(node, WzCanvasProperty):
            try:
                resolved, _image, _path, _property = materializer.resolve_canvas(node, source_image, source_path, set())
                arc.decode_source_canvas(resolved)
            except Exception as exc:
                issues.append({
                    "level": "blocker", "path": path, "title": "图像无法解码",
                    "reason": f"TMS Canvas 或其链接解析失败：{exc}",
                    "resolution": "修复资源链接或替换为可解码图像后才能迁移。", "automatic": False,
                })
                continue
            if (int(node.format), int(node.format2)) != (1, 0) or node.child("_outlink") or node.child("_inlink"):
                issues.append({
                    "level": "convert", "path": path, "title": "图像链接与像素格式转换",
                    "reason": "TMS 图像使用链接或不是旧端要求的内嵌 GMS ARGB4444。",
                    "resolution": "一键迁移会解析真实图像、移除链接节点并转换为 format=1、format2=0。",
                    "automatic": True,
                })
        normalized = (_normalize_path(path), row["type"])
        canvas_link = row["name"] in ("_outlink", "_inlink") and isinstance(source_node.get(path.rsplit("/", 1)[0]), WzCanvasProperty)
        if schema and not canvas_link and normalized not in schema and row["type"] not in ("Canvas", "SubProperty"):
            guidance = {
                "info/incARC": (
                    "神秘力量属性", "旧客户端没有神秘力量（ARC）属性读取与显示逻辑。",
                    "迁移时自动移除；物品仍可作为任务奖励显示，但不会提供神秘力量。",
                ),
                "info/reqQuestOnProgress": (
                    "现代任务装备限制", "旧端装备记录中没有该任务状态限制节点。",
                    "迁移时自动移除，任务发放条件继续由 Quest 数据控制。",
                ),
                "info/MDUReward": (
                    "现代奖励标记", "旧端装备记录中没有 MDUReward 契约。",
                    "迁移时自动移除，不影响当前任务直接发放物品。",
                ),
                "info/CatalystReqQuest": (
                    "催化剂任务限制", "旧端没有 ArcaneForce 催化剂与对应任务逻辑。",
                    "迁移时自动移除；旧端不提供催化剂功能。",
                ),
            }.get(path, (
                "旧端未定义节点", "选定的旧端同类装备基线中没有这个节点。",
                "迁移时自动移除；如需保留，必须先提供旧端可工作的同类节点证据。",
            ))
            issues.append({
                "level": "drop", "path": path, "title": guidance[0],
                "reason": guidance[1], "resolution": guidance[2], "automatic": True,
            })
    if not schema and not category.standalone:
        issues.append({
            "level": "blocker", "path": "资源记录", "title": "缺少旧端兼容基线",
            "reason": f"找不到旧端目标分片 {target.name}，无法判断哪些节点可被旧客户端读取。",
            "resolution": "补充同分类旧端记录作为白名单基线后再迁移。", "automatic": False,
        })
    return {
        "safe": not any(issue["level"] == "blocker" for issue in issues),
        "issues": issues,
        "counts": {level: sum(issue["level"] == level for issue in issues) for level in ("blocker", "convert", "drop")},
    }


def _build_projection(category: Category, item_id: int, compatibility: dict[str, Any] | None = None):
    source_path = _group_file(category, item_id, "tms")
    source_image = _load_image(source_path, "tms")
    source_node = _item_node(source_image, category, item_id)
    check = compatibility or _compatibility(source_image, source_node, source_path, category, item_id)
    if not check["safe"]:
        return None, [], 0
    materializer = arc.CanvasMaterializer()
    record_name = str(item_id) if category.key == "special" else f"0{item_id}"
    cloned = arc.clone_property(source_node, None, source_image, source_path, materializer, record_name)
    removed = _prune_to_schema(cloned, _legacy_schema(category.key, _group_file(category, item_id, "local").name))
    return cloned, removed, materializer.canvases


def _apply_projection_changes(category: Category, item_id: int, node, changes: list[dict[str, Any]]):
    if len(changes) > 200:
        raise ValueError("单次迁移最多调整 200 个节点")
    record_name = node.name
    data = _new_img(node)
    for change in changes:
        operation = str(change.get("operation", ""))
        if operation not in ("add", "edit", "remove"):
            raise ValueError("迁移节点操作无效")
        relative = tuple(part for part in str(change.get("path", "")).split("/") if part)
        if operation != "add" and not relative:
            raise ValueError("不能修改迁移记录根节点")
        kwargs: dict[str, Any] = {}
        if operation == "add":
            name = str(change.get("name", "")).strip()
            kind = str(change.get("kind", ""))
            if not name or "/" in name or kind not in (*EDITABLE_TYPES, "SubProperty", "Null"):
                raise ValueError("迁移新增节点的名称或类型无效")
            kwargs.update(name=name, kind=kind, values=change.get("values") or {})
        elif operation == "edit":
            kwargs["values"] = change.get("values") or {}
        data = mutate_img(data, operation, (record_name, *relative), region="GMS", **kwargs).data
    image = WzImage.from_bytes(data, key=GMS_KEY, name="migration-preview.img")
    image.parse()
    if image.truncated or image.parse_warnings:
        raise ValueError("迁移节点调整后的 IMG 解析失败")
    projected = image.root.child(record_name)
    if projected is None:
        raise ValueError("迁移投影记录丢失")
    schema = _legacy_schema(category.key, _group_file(category, item_id, "local").name)
    for row in _walk_nodes(projected):
        current = projected.get(row["path"])
        if isinstance(current, BLOCKED_TYPES):
            raise ValueError(f"迁移投影包含旧端不支持节点: {row['path']}")
        if isinstance(current, WzCanvasProperty):
            if (int(current.format), int(current.format2)) != (1, 0) or current.child("_outlink") or current.child("_inlink"):
                raise ValueError(f"迁移投影 Canvas 未完成旧端转换: {row['path']}")
        elif schema and row["type"] != "SubProperty" and (_normalize_path(row["path"]), row["type"]) not in schema:
            raise ValueError(f"节点不在旧端兼容白名单中: {row['path']}")
    return projected


def _override_string_record(node, item_id: int, name: str, desc: str):
    data = _new_img(node)
    record_name = str(item_id)
    for key, value in (("name", name), ("desc", desc)):
        path = (record_name, key)
        image = WzImage.from_bytes(data, key=GMS_KEY, name="migration-string.img"); image.parse()
        record = image.root.child(record_name)
        operation = "edit" if record is not None and record.child(key) is not None else "add"
        kwargs = {"values": {"value": value}}
        if operation == "add":
            kwargs.update(name=key, kind="String")
            path = (record_name,)
        data = mutate_img(data, operation, path, region="GMS", **kwargs).data
    image = WzImage.from_bytes(data, key=GMS_KEY, name="migration-string.img"); image.parse()
    if image.truncated or image.parse_warnings or image.root.child(record_name) is None:
        raise ValueError("迁移文本调整失败")
    return image.root.child(record_name)


def _node_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["path"]: row for row in rows}


def _diff(local_rows: list[dict[str, Any]], tms_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    local, tms = _node_map(local_rows), _node_map(tms_rows)
    result = []
    for path in sorted(set(local) | set(tms), key=lambda value: (value.count("/"), value)):
        left, right = local.get(path), tms.get(path)
        status = "localOnly" if right is None else "tmsOnly" if left is None else "same"
        if left is not None and right is not None and (left["type"], left["value"]) != (right["type"], right["value"]):
            status = "changed"
        result.append({"path": path, "status": status, "local": left, "tms": right})
    return result


def _string_path(scope: str, category: Category) -> Path | None:
    if not category.string_file:
        return None
    return (TMS_DATA / "String" / category.string_file) if scope == "tms" else (CLIENT_STRING / category.string_file)


def _string_node(scope: str, category: Category, item_id: int):
    path = _string_path(scope, category)
    if path is None or not path.is_file():
        return None
    image = _load_image(path, scope)
    parent = image.root
    for part in _category_string_parent(category, scope):
        parent = parent.child(part)
        if parent is None:
            return None
    return parent.child(str(item_id))


def _string_values(node) -> dict[str, str]:
    if node is None:
        return {"name": "", "desc": ""}
    return {
        "name": str(getattr(node.child("name"), "value", "")),
        "desc": str(getattr(node.child("desc"), "value", "")),
    }


@lru_cache(maxsize=16)
def _local_catalog(category_key: str) -> tuple[dict[str, str], ...]:
    category = CATEGORIES[category_key]
    if category.string_file:
        path = ZH_STRING / f"{category.string_file}.xml"
        if not path.is_file():
            path = SERVER_STRING / f"{category.string_file}.xml"
        root = ET.parse(path).getroot()
        parent = root
        for part in _category_string_parent(category, "local"):
            parent = next((child for child in parent if child.get("name") == part), None)
            if parent is None:
                return ()
        rows = []
        for node in parent:
            item_id = node.get("name", "")
            if item_id.isdigit() and len(item_id) == 7 and _category_accepts_id(category, item_id):
                values = {child.get("name"): child.get("value", "") for child in node}
                rows.append({"id": item_id, "name": values.get("name", ""), "desc": values.get("desc", "")})
        return tuple(rows)
    return tuple(_special_catalog("local", category))


@lru_cache(maxsize=16)
def _tms_catalog(category_key: str) -> tuple[dict[str, str], ...]:
    category = CATEGORIES[category_key]
    if not category.string_file:
        return tuple(_special_catalog("tms", category))
    path = _string_path("tms", category)
    if path is None:
        return ()
    image = _load_image(path, "tms")
    parent = image.root
    for part in _category_string_parent(category, "tms"):
        parent = parent.child(part)
        if parent is None:
            return ()
    rows = []
    for node in parent.children():
        if node.name.isdigit() and len(str(int(node.name))) == 7 and _category_accepts_id(category, str(int(node.name))):
            values = _string_values(node)
            rows.append({"id": str(int(node.name)), **values})
    return tuple(rows)


def _special_catalog(scope: str, category: Category) -> list[dict[str, str]]:
    directory = _category_directory(category, scope)
    if category.family == "character":
        base = (TMS_DATA / "Character" if scope == "tms" else CLIENT_CHARACTER) / directory
    else:
        base = (TMS_DATA / "Item" if scope == "tms" else CLIENT_ITEM) / directory
    rows: dict[str, dict[str, str]] = {}
    for path in base.glob("*.img"):
        try:
            image = _load_image(path, scope)
        except Exception:
            continue
        for node in image.root.children():
            if not node.name.isdigit():
                continue
            item_id = str(int(node.name))
            name = getattr(node.child("name"), "value", "") or getattr(node.get("info/name"), "value", "")
            desc = getattr(node.child("desc"), "value", "") or getattr(node.get("info/desc"), "value", "")
            rows[item_id] = {"id": item_id, "name": str(name), "desc": str(desc)}
    return list(rows.values())


def _detail(scope: str, category: Category, item_id: int) -> dict[str, Any] | None:
    if not _item_exists(category, item_id, scope):
        return None
    path = _group_file(category, item_id, scope)
    image = _load_image(path, scope)
    node = _item_node(image, category, item_id)
    strings = _string_values(_string_node(scope, category, item_id))
    if not strings["name"]:
        strings["name"] = str(getattr(node.child("name"), "value", ""))
        strings["desc"] = str(getattr(node.child("desc"), "value", ""))
    rows = _walk_nodes(node)
    return {
        "scope": scope, "category": category.key, "id": str(item_id), "name": strings["name"],
        "desc": strings["desc"], "file": str(path), "record": node.name,
        "nodes": rows, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "mutable": scope == "local" and not category.standalone,
    }


def _raw_records(data: bytes, region: str) -> dict[str, bytes]:
    layout = scan_img(data, region=region)
    return {record.name: data[record.start:record.end] for record in layout.root.records}


def _upsert_img_record(data: bytes, node, name: str, region: str = "GMS") -> bytes:
    before = _raw_records(data, region)
    exists = name in before
    if not exists:
        data = mutate_img(data, "add", (), name=name, kind="SubProperty", region=region).data
    result = replace_img_record(data, (name,), node, region=region).data
    after = _raw_records(result, region)
    for sibling, raw in before.items():
        if sibling != name and after.get(sibling) != raw:
            raise ValueError(f"未修改的 IMG 记录发生变化: {sibling}")
    return result


def _remove_img_record(data: bytes, name: str, region: str = "GMS") -> bytes:
    before = _raw_records(data, region)
    if name not in before:
        return data
    result = mutate_img(data, "remove", (name,), region=region).data
    after = _raw_records(result, region)
    for sibling, raw in before.items():
        if sibling != name and after.get(sibling) != raw:
            raise ValueError(f"未修改的 IMG 记录发生变化: {sibling}")
    return result


def _replace_xml_record(data: bytes, name: str, node_xml: str | None) -> bytes:
    spans: dict[str, tuple[int, int]] = {}
    stack: list[tuple[str, int, bool]] = []
    parser = xml.parsers.expat.ParserCreate()

    def tag_end(start: int) -> int:
        quote = 0
        for index in range(start, len(data)):
            byte = data[index]
            if quote:
                if byte == quote:
                    quote = 0
            elif byte in (34, 39):
                quote = byte
            elif byte == 62:
                return index + 1
        raise ValueError("XML 标签未闭合")

    def start(_tag: str, attrs: dict[str, str]) -> None:
        offset = parser.CurrentByteIndex; end = tag_end(offset)
        stack.append((attrs.get("name", ""), offset, data[offset:end].rstrip().endswith(b"/>")))

    def end(_tag: str) -> None:
        node_name, offset, self_closing = stack.pop()
        finish = tag_end(offset) if self_closing else tag_end(parser.CurrentByteIndex)
        if len(stack) == 1:
            spans[node_name] = (offset, finish)

    parser.StartElementHandler = start; parser.EndElementHandler = end; parser.Parse(data, True)
    span = spans.get(name)
    if node_xml is None:
        if span is None:
            return data
        start_at, end_at = span
        line_start = data.rfind(b"\n", 0, start_at) + 1
        if not data[line_start:start_at].strip():
            start_at = line_start
        if end_at < len(data) and data[end_at:end_at + 1] == b"\n":
            end_at += 1
        result = data[:start_at] + data[end_at:]
    else:
        fragment = node_xml.encode()
        if span is not None:
            line_start = data.rfind(b"\n", 0, span[0]) + 1
            indent = data[line_start:span[0]]
            formatted = fragment.replace(b"\n", b"\n" + indent)
            result = data[:span[0]] + formatted + data[span[1]:]
        else:
            closing = data.rfind(b"</imgdir>")
            if closing < 0:
                raise ValueError("XML 缺少根结束标签")
            indented = b"  " + fragment.replace(b"\n", b"\n  ")
            prefix = b"" if data[:closing].endswith(b"\n") else b"\n"
            result = data[:closing] + prefix + indented + b"\n" + data[closing:]
    ET.fromstring(result)
    return result


def _new_img(node) -> bytes:
    reader = WzBinaryReader(io.BytesIO(), GMS_KEY)
    return encode_image_type_string(reader, "Property") + b"\x00\x00" + _encode_property_list((node,), reader)


def _new_standalone_img(node) -> bytes:
    reader = WzBinaryReader(io.BytesIO(), GMS_KEY)
    return encode_image_type_string(reader, "Property") + b"\x00\x00" + _encode_property_list(tuple(node.children()), reader)


def _standalone_xml(file_name: str, node) -> bytes:
    children = "\n".join(arc.property_to_xml(child, 0).strip() for child in node.children())
    return _new_xml(file_name, children)


def _new_xml(file_name: str, node_xml: str) -> bytes:
    indented = "  " + node_xml.replace("\n", "\n  ")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<imgdir name="{file_name}">\n{indented}\n</imgdir>\n'
    ).encode()


def _upsert_string_xml(text: str, parent_path: tuple[str, ...], item_id: str, node) -> str:
    root = ET.fromstring(text)
    parent = root
    for part in parent_path:
        parent = next((child for child in parent if child.get("name") == part), None)
        if parent is None:
            raise KeyError("/".join(parent_path))
    existing = next((child for child in parent if child.get("name") == item_id), None)
    record_path = (*parent_path, item_id)
    if existing is None:
        text = mutate_xml(text, "add", parent_path, name=item_id, kind="SubProperty")
        existing_names: dict[str, str] = {}
    else:
        existing_names = {child.get("name", ""): child.tag for child in existing}
    source_names = {child.name: child for child in node.children()}
    for old_name in existing_names.keys() - source_names.keys():
        text = mutate_xml(text, "remove", (*record_path, old_name))
    tag_by_type = {"Short": "short", "Int": "int", "Long": "long", "Float": "float", "Double": "double", "String": "string", "UOL": "uol"}
    for child_name, child in source_names.items():
        values = {"value": child.value}
        if child_name in existing_names and existing_names[child_name] == tag_by_type.get(child.type_name):
            text = mutate_xml(text, "edit", (*record_path, child_name), kind=child.type_name, values=values)
        else:
            if child_name in existing_names:
                text = mutate_xml(text, "remove", (*record_path, child_name))
            text = mutate_xml(text, "add", record_path, name=child_name, kind=child.type_name, values=values)
    return text


def _atomic_commit(payloads: dict[Path, bytes]) -> None:
    originals = {path: path.read_bytes() if path.exists() else None for path in payloads}
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    temporaries: dict[Path, Path] = {}
    replaced: list[Path] = []
    try:
        for path, payload in payloads.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if originals[path] is not None:
                backup = BACKUP_ROOT / ("__".join(path.relative_to(ROOT).parts) + ".bak")
                if not backup.exists():
                    backup.write_bytes(originals[path])
            fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload); handle.flush(); os.fsync(handle.fileno())
            temporaries[path] = Path(raw)
        for path, temporary in temporaries.items():
            os.replace(temporary, path); replaced.append(path)
    except Exception:
        for path in reversed(replaced):
            original = originals[path]
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(original)
        raise
    finally:
        for temporary in temporaries.values():
            temporary.unlink(missing_ok=True)


def _prune_to_schema(node, schema: frozenset[tuple[str, str]]) -> list[str]:
    removed: list[str] = []

    def prune(parent, prefix: tuple[str, ...]) -> None:
        for child in list(parent.children()):
            path = (*prefix, child.name)
            normalized = _normalize_path("/".join(path))
            matching_prefix = normalized + "/"
            allowed = (normalized, child.type_name) in schema or any(item[0].startswith(matching_prefix) for item in schema)
            if not allowed:
                parent._children.pop(child.name, None)
                removed.append("/".join(path))
                continue
            if isinstance(child, WzSubProperty):
                prune(child, path)

    prune(node, ())
    return removed


def _copy_from_tms(
    category: Category,
    item_id: int,
    overwrite: bool,
    changes: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not category.migratable:
        raise ValueError("旧客户端尚无已验证的 ArcaneForce 装备契约，禁止直接迁移")
    if category.key == "pet":
        raise ValueError("宠物是一物品一 IMG，当前仅支持查看、搜索和对比，暂不允许覆盖复制")
    source_path = _group_file(category, item_id, "tms")
    source_image = _load_image(source_path, "tms")
    source_node = _item_node(source_image, category, item_id)
    compatibility = _compatibility(source_image, source_node, source_path, category, item_id)
    if not compatibility["safe"]:
        raise ValueError("存在阻断兼容问题，不能复制")
    target_path = _group_file(category, item_id, "local")
    exists = _item_exists(category, item_id, "local")
    if exists and not overwrite:
        raise FileExistsError("本地物品已存在，覆盖复制需要明确确认")
    record_name = str(item_id) if category.key == "special" else f"0{item_id}"
    cloned, removed, converted_canvases = _build_projection(category, item_id, compatibility)
    if cloned is None:
        raise ValueError("存在阻断兼容问题，不能复制")
    cloned = _apply_projection_changes(category, item_id, cloned, list(changes or []))
    server_path = _server_item_path(category, item_id)
    if category.standalone:
        item_data = _new_standalone_img(cloned)
        server_data = _standalone_xml(target_path.name, cloned)
        if target_path.exists() and target_path.read_bytes() != item_data:
            raise ValueError("本地独立装备 IMG 已存在且内容不同；为保护二进制布局，请先在节点对比中确认差异")
        if server_path.exists() and server_path.read_bytes() != server_data:
            raise ValueError("服务端独立装备 XML 已存在且内容不同；请先确认差异")
    else:
        item_xml = arc.property_to_xml(cloned, 0).strip()
        if target_path.exists():
            item_data = _upsert_img_record(target_path.read_bytes(), cloned, record_name)
        else:
            item_data = _new_img(cloned)
        server_data = _replace_xml_record(server_path.read_bytes(), record_name, item_xml) if server_path.exists() else _new_xml(target_path.name, item_xml)
    verified = WzImage.from_bytes(item_data, key=GMS_KEY, name=target_path.name)
    verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise ValueError("复制后的客户端物品 IMG 解析失败")
    ET.fromstring(server_data)
    payloads = {target_path: item_data, server_path: server_data}

    if category.string_file:
        source_string = _string_node("tms", category, item_id)
        if source_string is None:
            raise ValueError("TMS 物品缺少名称记录")
        tms_string_path = _string_path("tms", category)
        string_path = _string_path("local", category)
        assert tms_string_path is not None and string_path is not None
        string_clone = arc.clone_property(source_string, None, _load_image(tms_string_path, "tms"), tms_string_path, arc.CanvasMaterializer(), str(item_id))
        text_values = _string_values(source_string)
        metadata = metadata or {}
        string_clone = _override_string_record(
            string_clone, item_id,
            str(metadata.get("name", text_values["name"])),
            str(metadata.get("desc", text_values["desc"])),
        )
        string_data = string_path.read_bytes()
        target_parent = _category_string_parent(category, "local")
        if target_parent:
            exists_string = _string_node("local", category, item_id) is not None
            if not exists_string:
                string_data = mutate_img(string_data, "add", target_parent, name=str(item_id), kind="SubProperty", region="GMS").data
            string_data = replace_img_record(string_data, (*target_parent, str(item_id)), string_clone, region="GMS").data
        else:
            string_data = _upsert_img_record(string_data, string_clone, str(item_id))
        payloads[string_path] = string_data
        string_xml = arc.property_to_xml(string_clone, 0).strip()
        for base in (SERVER_STRING, ZH_STRING):
            xml_path = base / f"{category.string_file}.xml"
            if target_parent:
                text = xml_path.read_text(encoding="utf-8-sig")
                updated = _upsert_string_xml(text, target_parent, str(item_id), string_clone)
                payloads[xml_path] = updated.encode()
            else:
                payloads[xml_path] = _replace_xml_record(xml_path.read_bytes(), str(item_id), string_xml)
    changed_payloads = {path: data for path, data in payloads.items() if not path.exists() or path.read_bytes() != data}
    if changed_payloads:
        _atomic_commit(changed_payloads)
    _local_catalog.cache_clear(); _legacy_schema.cache_clear()
    return {"files": [str(path) for path in payloads], "convertedCanvases": converted_canvases, "removedNodes": removed}


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/catalog")
def catalog():
    availability = request.args.get("availability", "missing")
    if availability not in ("missing", "both", "local", "all"):
        raise ValueError("物品范围无效")
    category = _category(request.args.get("category", "etc"))
    query = request.args.get("q", "").strip().lower()
    local_catalog = {row["id"]: row for row in _local_catalog(category.key)}
    tms_catalog = {row["id"]: row for row in _tms_catalog(category.key)}
    local_ids = _resource_ids(category, "local")
    tms_ids = _resource_ids(category, "tms")
    rows = []
    for item_id in set(local_catalog) | set(tms_catalog) | set(local_ids) | set(tms_ids):
        local, tms = item_id in local_ids, item_id in tms_ids
        if availability == "missing" and not (tms and not local):
            continue
        if availability == "both" and not (local and tms):
            continue
        if availability == "local" and not (local and not tms):
            continue
        local_row, tms_row = local_catalog.get(item_id, {}), tms_catalog.get(item_id, {})
        name = str((local_row if local else tms_row).get("name") or tms_row.get("name") or local_row.get("name") or "")
        if query and query not in item_id and query not in name.lower():
            continue
        status = "both" if local and tms else "missing" if tms else "local" if local else "metadataOnly"
        rows.append({
            "id": item_id, "name": name,
            "desc": str((local_row if local else tms_row).get("desc") or ""),
            "local": local, "tms": tms, "status": status,
            "localName": str(local_row.get("name") or ""), "tmsName": str(tms_row.get("name") or ""),
            "iconScope": "local" if local else "tms" if tms else "",
        })
    rows.sort(key=lambda row: int(row["id"]))
    limit = min(max(int(request.args.get("limit", 300)), 1), 1000)
    return _ok(
        items=rows[:limit],
        total=len(rows), categories=[{"id": row.key, "name": row.label} for row in CATEGORIES.values()],
        counts={
            "missing": len(tms_ids - local_ids), "both": len(tms_ids & local_ids),
            "local": len(local_ids - tms_ids), "all": len(local_ids | tms_ids),
        },
        tmsAvailable=TMS_DATA.is_dir(),
    )


@app.get("/api/item/<scope>/<category_key>/<int:item_id>")
def detail(scope: str, category_key: str, item_id: int):
    if scope not in ("local", "tms"):
        raise ValueError("物品范围无效")
    category = _category(category_key); _validate_category_id(category, item_id)
    local = _detail("local", category, item_id)
    tms = _detail("tms", category, item_id)
    selected = local if scope == "local" else tms
    if selected is None:
        raise KeyError(f"{scope} 物品不存在: {item_id}")
    if tms is None:
        compatibility = {"safe": False, "issues": [], "counts": {}}
        projection = None
    else:
        tms_path = _group_file(category, item_id, "tms"); tms_image = _load_image(tms_path, "tms")
        compatibility = _compatibility(tms_image, _item_node(tms_image, category, item_id), tms_path, category, item_id)
        projected, removed, converted = _build_projection(category, item_id, compatibility)
        projection = None if projected is None else {
            "nodes": _walk_nodes(projected), "removedNodes": removed, "convertedCanvases": converted,
            "mutable": category.key != "pet",
        }
    comparison_rows = projection["nodes"] if projection else (tms["nodes"] if tms else [])
    return _ok(
        item=selected, local=local, tms=tms, projection=projection,
        diff=_diff(local["nodes"] if local else [], comparison_rows), compatibility=compatibility,
    )


@app.get("/api/item/<scope>/<category_key>/<int:item_id>/icon")
def icon(scope: str, category_key: str, item_id: int):
    if scope not in ("local", "tms"):
        raise ValueError("物品范围无效")
    category = _category(category_key); _validate_category_id(category, item_id)
    path = _group_file(category, item_id, scope); image = _load_image(path, scope); node = _item_node(image, category, item_id)
    canvas = node.get("info/icon") or node.get("info/iconRaw") or node.get("icon")
    if not isinstance(canvas, WzCanvasProperty):
        return "", 404
    if scope == "tms":
        resolved, _image, _path, _property = arc.CanvasMaterializer().resolve_canvas(canvas, image, path, set())
        pixels = arc.decode_source_canvas(resolved)
    else:
        pixels = decode_canvas(canvas, region="GMS")
    output = io.BytesIO(); pixels.save(output, format="PNG"); output.seek(0)
    return send_file(output, mimetype="image/png", max_age=3600)


@app.post("/api/item/copy")
def copy_item():
    body = request.get_json(silent=True) or {}
    category = _category(body.get("category")); item_id = _item_id(body.get("id")); _validate_category_id(category, item_id)
    overwrite = bool(body.get("overwrite"))
    if overwrite and str(body.get("confirm", "")) != str(item_id):
        raise ValueError("覆盖复制必须确认物品 ID")
    with _WRITE_LOCK:
        result = _copy_from_tms(
            category, item_id, overwrite,
            changes=list(body.get("changes") or []), metadata=dict(body.get("metadata") or {}),
        )
    return _ok(result=result, item=_detail("local", category, item_id))


@app.post("/api/item/node")
def mutate_node():
    body = request.get_json(silent=True) or {}
    category = _category(body.get("category")); item_id = _item_id(body.get("id")); _validate_category_id(category, item_id)
    if category.standalone:
        raise ValueError("宠物 IMG 暂不开放节点修改")
    operation = str(body.get("operation", "")); relative = tuple(part for part in str(body.get("path", "")).split("/") if part)
    if not relative and operation != "add":
        raise ValueError("不能修改物品记录根节点")
    client = _group_file(category, item_id, "local"); server = _server_item_path(category, item_id)
    if not client.is_file() or not server.is_file():
        raise FileNotFoundError("本地物品 IMG/XML 不完整")
    image = _load_image(client, "local"); record = _item_node(image, category, item_id).name
    path = (record, *relative); values = body.get("values") or {}
    kwargs = {"name": body.get("name"), "kind": body.get("kind"), "values": values}
    with _WRITE_LOCK:
        img_before = client.read_bytes(); xml_before = server.read_text(encoding="utf-8-sig")
        img_after = mutate_img(img_before, operation, path, region="GMS", **kwargs).data
        xml_after = mutate_xml(xml_before, operation, path, **kwargs)
        verified = WzImage.from_bytes(img_after, key=GMS_KEY, name=client.name); verified.parse()
        if verified.truncated or verified.parse_warnings:
            raise ValueError("节点修改后的 IMG 解析失败")
        ET.fromstring(xml_after)
        _atomic_commit({client: img_after, server: xml_after.encode()})
    _legacy_schema.cache_clear()
    return _ok(item=_detail("local", category, item_id))


@app.post("/api/item/metadata")
def metadata():
    body = request.get_json(silent=True) or {}
    category = _category(body.get("category")); item_id = _item_id(body.get("id")); _validate_category_id(category, item_id)
    if not category.string_file:
        raise ValueError("特殊物品名称保存在物品节点中，请直接编辑节点")
    string_path = _string_path("local", category); assert string_path is not None
    node = _string_node("local", category, item_id)
    if node is None:
        raise KeyError("本地物品名称记录不存在")
    values = {"name": str(body.get("name", "")), "desc": str(body.get("desc", ""))}
    target_parent = _category_string_parent(category, "local")
    payloads: dict[Path, bytes] = {}
    data = string_path.read_bytes()
    for key, next_value in values.items():
        path = (*target_parent, str(item_id), key)
        current = node.child(key)
        if current is None:
            data = mutate_img(data, "add", path[:-1], name=key, kind="String", values={"value": next_value}, region="GMS").data
        else:
            data = mutate_img(data, "edit", path, values={"value": next_value}, region="GMS").data
    payloads[string_path] = data
    for base in (SERVER_STRING, ZH_STRING):
        path = base / f"{category.string_file}.xml"; text = path.read_text(encoding="utf-8-sig")
        for key, next_value in values.items():
            node_path = (*target_parent, str(item_id), key)
            try:
                text = mutate_xml(text, "edit", node_path, values={"value": next_value})
            except KeyError:
                text = mutate_xml(text, "add", node_path[:-1], name=key, kind="String", values={"value": next_value})
        payloads[path] = text.encode()
    with _WRITE_LOCK:
        _atomic_commit(payloads)
    _local_catalog.cache_clear()
    return _ok(item=_detail("local", category, item_id))


@app.post("/api/item/delete")
def delete_item():
    body = request.get_json(silent=True) or {}
    category = _category(body.get("category")); item_id = _item_id(body.get("id")); _validate_category_id(category, item_id)
    if str(body.get("confirm", "")) != str(item_id):
        raise ValueError("删除物品必须确认物品 ID")
    if category.standalone:
        raise ValueError("宠物是一物品一 IMG，当前不开放删除")
    client = _group_file(category, item_id, "local"); server = _server_item_path(category, item_id)
    image = _load_image(client, "local"); record = _item_node(image, category, item_id).name
    payloads = {
        client: _remove_img_record(client.read_bytes(), record),
        server: _replace_xml_record(server.read_bytes(), record, None),
    }
    if category.string_file:
        string_path = _string_path("local", category); assert string_path is not None
        string_data = string_path.read_bytes()
        string_node = _string_node("local", category, item_id)
        if string_node is not None:
            string_data = mutate_img(string_data, "remove", (*category.string_parent, str(item_id)), region="GMS").data
        payloads[string_path] = string_data
        for base in (SERVER_STRING, ZH_STRING):
            xml_path = base / f"{category.string_file}.xml"; text = xml_path.read_text(encoding="utf-8-sig")
            try:
                text = mutate_xml(text, "remove", (*category.string_parent, str(item_id)))
            except KeyError:
                pass
            payloads[xml_path] = text.encode()
    with _WRITE_LOCK:
        _atomic_commit(payloads)
    _local_catalog.cache_clear(); _legacy_schema.cache_clear()
    return _ok(deleted=str(item_id), files=[str(path) for path in payloads])
