from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from flask import Flask, jsonify, render_template, request, send_file

HERE = Path(__file__).resolve().parent
RESOURCE_ROOT = HERE.parent
TOOL_ROOT = RESOURCE_ROOT.parent
REPO_ROOT = TOOL_ROOT.parent
WZPY_ROOT = TOOL_ROOT / "wz-python"
if str(WZPY_ROOT) not in sys.path:
    sys.path.insert(0, str(WZPY_ROOT))
if str(RESOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(RESOURCE_ROOT))

from wzpy.crypto import WzKey  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.incremental_img import (  # noqa: E402
    SUPPORTED_ADD_TYPES,
    mutate_img,
    normalized_values,
    scan_img,
)
from wzpy.incremental_xml import mutate_xml, scan_xml  # noqa: E402
from wzpy.properties import (  # noqa: E402
    WzCanvasProperty,
    WzConvexProperty,
    WzProperty,
    WzSoundProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.wz_image import WzImage  # noqa: E402
from map_mob.compat import STATUS_LABELS, evaluate as compat_evaluate  # noqa: E402

_DEFAULT_EXPORT_ROOT = Path.home() / "Downloads" / "ImgEditorExport"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_temp(path: Path, payload: bytes) -> Path:
    fd, raw_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(raw_path)
    try:
        os.fchmod(fd, path.stat().st_mode & 0o777)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return temp_path


def _backup_once(path: Path, payload: bytes) -> Path:
    backup = path.with_name(path.name + ".web-editor.bak")
    try:
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        return backup
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return backup


def _atomic_restore(path: Path, payload: bytes) -> None:
    temp = _write_temp(path, payload)
    os.replace(temp, path)


def _suggest_xml_path(img_path: Path) -> Optional[Path]:
    try:
        relative = img_path.resolve().relative_to(REPO_ROOT / "clien" / "Data")
    except ValueError:
        return None
    if len(relative.parts) < 2:
        return None
    wz_name = relative.parts[0]
    remainder = Path(*relative.parts[1:])
    return REPO_ROOT / "gms-server" / "wz" / f"{wz_name}.wz" / Path(str(remainder) + ".xml")


def _pick_file(kind: str, current: str = "") -> str:
    if kind not in ("img", "xml"):
        raise ValueError("kind must be img or xml")
    current_path = Path(current).expanduser() if current else None
    if current_path and current_path.is_file():
        initial_dir = current_path.parent
    elif current_path and current_path.is_dir():
        initial_dir = current_path
    elif current_path and current_path.parent.is_dir():
        initial_dir = current_path.parent
    else:
        initial_dir = REPO_ROOT
    result = subprocess.run(
        [
            sys.executable,
            str(HERE / "_file_picker.py"),
            kind,
            str(initial_dir),
        ],
        cwd=HERE,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or "native file picker failed"
        raise RuntimeError(message)
    selected = result.stdout.strip()
    if not selected:
        return ""
    path = Path(selected).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"selected file does not exist: {path}")
    if kind == "img" and path.suffix.lower() != ".img":
        raise ValueError("selected file must end with .img")
    if kind == "xml" and not path.name.lower().endswith(".img.xml"):
        raise ValueError("selected file must end with .img.xml")
    return str(path)


# wzpy type_name → compat 引擎使用的节点类型名
_COMPAT_TYPE_NAMES = {
    "Canvas": "canvas",
    "SubProperty": "imgdir",
    "UOL": "uol",
    "Vector": "vector",
    "Null": "null",
    "Video": "video",
    "RawData": "rawdata",
}


def _compat_mode(img_path: Path) -> Optional[str]:
    """根据 IMG 路径自动选择 compat 引擎模式。"""
    text = str(img_path)
    if "/Map/" in text:
        return "map"
    if "/Mob/" in text:
        return "boss"
    return None


def _compat_verdict(prop: WzProperty, path: Sequence[str], img_path: Optional[Path]) -> Dict[str, Any]:
    mode = _compat_mode(img_path) if img_path else None
    node: Dict[str, Any] = {
        "name": prop.name,
        "parent_name": path[-2] if len(path) >= 2 else "",
        "path": "/".join(path),
        "type": _COMPAT_TYPE_NAMES.get(prop.type_name, prop.type_name.lower()),
        "value": prop.value if isinstance(prop.value, (int, str)) else None,
    }
    if isinstance(prop, WzCanvasProperty):
        node["width"] = prop.width
        node["height"] = prop.height
        node["format"] = prop.format
        node["format2"] = prop.format2
    verdict = compat_evaluate(node, mode) if mode else compat_evaluate(node, "generic")
    return {
        "status": verdict.status,
        "label": STATUS_LABELS.get(verdict.status, verdict.status),
        "reason": verdict.reason,
        "suggestion": verdict.suggestion,
    }


def _property_value(prop: WzProperty) -> Any:
    if isinstance(prop, WzVectorProperty):
        return {"x": prop.x, "y": prop.y}
    if isinstance(prop, WzCanvasProperty):
        return {
            "width": prop.width,
            "height": prop.height,
            "format": prop.format,
            "format2": prop.format2,
            "payload_bytes": prop._png_length,
        }
    if isinstance(prop, WzSoundProperty):
        return {"length_ms": prop.length_ms, "bytes": prop._data_length}
    if isinstance(prop, WzConvexProperty):
        return {"points": prop.value}
    if isinstance(prop, WzSubProperty):
        return {"children": prop.child_count()}
    return prop.value


def _property_json(
    prop: WzProperty,
    path: Sequence[str],
    img_path: Optional[Path] = None,
) -> Dict[str, Any]:
    return {
        "name": prop.name,
        "path": list(path),
        "type": prop.type_name,
        "container": isinstance(prop, WzSubProperty),
        "child_count": prop.child_count() if isinstance(prop, WzSubProperty) else 0,
        "value": _property_value(prop),
        "editable": prop.type_name in {
            "Short", "Int", "Long", "Float", "Double", "String", "Vector", "UOL",
        },
        "compat": _compat_verdict(prop, path, img_path),
    }


def _absolute_path(node: WzProperty) -> List[str]:
    """返回 node 在 IMG 内的绝对路径（不含 IMG 根名），可直接喂给 state.resolve / /api/canvas。"""
    parts: List[str] = []
    cur: Optional[WzProperty] = node
    while cur is not None:
        parts.append(cur.name)
        cur = cur.parent
    parts.reverse()
    # parts[0] 是 IMG 根节点（名为 xxx.img），去掉它
    if len(parts) > 1:
        parts = parts[1:]
    return parts


def _resolve_uol_target(uol: WzUolProperty) -> Optional[WzProperty]:
    """跟随 UOL 链（兄弟相对路径，含 `..`）直到非 UOL 目标节点。

    算法与 wzpy.character._resolve_uol 一致：取 cur.value 作为相对路径，
    从 cur.parent 出发用 WzProperty.get 解析（自动处理 `..`），带环检测。
    """
    seen: set = set()
    cur: Optional[WzProperty] = uol
    for _ in range(16):
        if cur is None or not isinstance(cur, WzUolProperty):
            return cur
        if id(cur) in seen:
            return None
        seen.add(id(cur))
        target_str = cur.value
        if not target_str or cur.parent is None:
            return None
        cur = cur.parent.get(str(target_str))
    return None


def _find_first_canvas(node: WzProperty, max_depth: int = 6):
    """在以 node 为根的子树中深度优先查找第一个带像素的 Canvas。

    搜索过程中会跟随遇到的 UOL 引用，以便"被引用的节点本身又是一个 UOL"的嵌套场景也能找到 Canvas。
    返回 (canvas, 占位子路径列表)；找不到返回 (None, None)。
    当 node 本身即 Canvas 时，子路径为空列表。
    """
    if isinstance(node, WzCanvasProperty):
        return node, []
    if not isinstance(node, WzSubProperty):
        return None, None
    stack = [(child, [child.name]) for child in node.children()]
    seen_uol: set = set()
    while stack:
        child, sub = stack.pop()
        # 跟随 UOL：最多 16 跳，避免循环
        while isinstance(child, WzUolProperty):
            if id(child) in seen_uol:
                child = None
                break
            seen_uol.add(id(child))
            target_str = child.value
            if not target_str or child.parent is None:
                child = None
                break
            child = child.parent.get(str(target_str))
            if child is None:
                break
        if isinstance(child, WzCanvasProperty):
            return child, sub
        if isinstance(child, WzSubProperty) and len(sub) < max_depth:
            stack.extend((c, [*sub, c.name]) for c in child.children())
    return None, None


class EditorState:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.img_path: Optional[Path] = None
        self.xml_path: Optional[Path] = None
        self.region: Optional[str] = None
        self.img_bytes: Optional[bytes] = None
        self.xml_text: Optional[str] = None
        self.image: Optional[WzImage] = None

    @property
    def opened(self) -> bool:
        return self.image is not None

    def load(self, img_path: Path, xml_path: Path, region: Optional[str] = None) -> None:
        img_path = img_path.expanduser().resolve()
        xml_path = xml_path.expanduser().resolve()
        if not img_path.is_file():
            raise FileNotFoundError(f"IMG file does not exist: {img_path}")
        if not xml_path.is_file():
            raise FileNotFoundError(f"XML file does not exist: {xml_path}")
        img_bytes = img_path.read_bytes()
        layout = scan_img(img_bytes, region=region)
        xml_text = _read_text(xml_path)
        xml_root = scan_xml(xml_text)
        if xml_root.tag != "imgdir" or xml_root.name != img_path.name:
            raise ValueError(
                f"XML root must be <imgdir name={img_path.name!r}>"
            )
        image = WzImage.from_bytes(
            img_bytes,
            key=WzKey.for_region(layout.region),
            name=img_path.name,
        )
        image.parse()
        if image.truncated or image.parse_warnings:
            raise ValueError(
                "IMG parse verification failed: " + "; ".join(image.parse_warnings or ["truncated"])
            )
        self.img_path = img_path
        self.xml_path = xml_path
        self.region = layout.region
        self.img_bytes = img_bytes
        self.xml_text = xml_text
        self.image = image

    def reload(self) -> None:
        """从磁盘重新读取当前已打开的 IMG/XML（保留内存中的路径与区域）。

        用于文件在编辑器外部被修改后，无需重新选文件即可刷新内存中的树。
        """
        if not self.img_path or not self.xml_path:
            raise RuntimeError("没有已打开的 IMG，无法重载")
        self.load(self.img_path, self.xml_path, self.region)

    def resolve(self, path: Sequence[str]) -> WzProperty:
        if not self.image:
            raise RuntimeError("no IMG is open")
        node = self.image.root.get("/".join(path)) if path else self.image.root
        if node is None:
            raise KeyError("/".join(path))
        return node

    def state_json(self) -> Dict[str, Any]:
        if not self.opened:
            return {"opened": False}
        assert self.img_path and self.xml_path and self.img_bytes is not None
        return {
            "opened": True,
            "img_path": str(self.img_path),
            "xml_path": str(self.xml_path),
            "region": self.region,
            "img_bytes": len(self.img_bytes),
            "img_sha256": _sha256(self.img_bytes),
            "add_types": list(SUPPORTED_ADD_TYPES),
            "default_export_root": str(_DEFAULT_EXPORT_ROOT),
        }


def _node_signature(prop: WzProperty) -> tuple:
    """节点签名，用于 A/B 对比（Canvas 视为叶子，不再深入其元数据子节点）。"""
    if isinstance(prop, WzCanvasProperty):
        return ("canvas", prop.width, prop.height, prop.format, prop.format2, prop._png_length)
    if isinstance(prop, WzSubProperty):
        return ("imgdir", prop.child_count())
    if isinstance(prop, WzVectorProperty):
        return ("vector", prop.x, prop.y)
    if isinstance(prop, WzSoundProperty):
        return ("sound", prop.length_ms)
    if isinstance(prop, WzConvexProperty):
        return ("convex", tuple(prop.value))
    return (prop.type_name, prop.value)


def diff_slot_trees(root_a: WzProperty, root_b: WzProperty, max_nodes: int = 200000) -> Dict[str, str]:
    """对比两棵树，返回 path → status 映射。

    status: same（一致）/ changed（已修改）/ aOnly（仅 A）/ bOnly（仅 B）。
    容器节点的 status 由后代汇总：任一后代不同即为 changed。
    """
    rows: Dict[str, str] = {}
    count = 0

    def walk(a: Optional[WzProperty], b: Optional[WzProperty], path: str) -> str:
        nonlocal count
        count += 1
        if count > max_nodes:
            raise ValueError(f"节点数超过 {max_nodes}，跳过对比")
        if a is not None and b is None:
            rows[path] = "aOnly"
            return "diff"
        if a is None and b is not None:
            rows[path] = "bOnly"
            return "diff"
        sig_a, sig_b = _node_signature(a), _node_signature(b)
        both_containers = (
            isinstance(a, WzSubProperty) and not isinstance(a, WzCanvasProperty)
            and isinstance(b, WzSubProperty) and not isinstance(b, WzCanvasProperty)
        )
        if both_containers:
            children_status = "same"
            names_a = {child.name: child for child in a.children()}
            names_b = {child.name: child for child in b.children()}
            for name in names_a.keys() | names_b.keys():
                child_path = f"{path}/{name}" if path else name
                status = walk(names_a.get(name), names_b.get(name), child_path)
                if status != "same":
                    children_status = "diff"
            rows[path] = "same" if children_status == "same" and sig_a == sig_b else "changed"
            return "same" if rows[path] == "same" else "diff"
        if sig_a == sig_b:
            rows[path] = "same"
            return "same"
        rows[path] = "changed"
        return "diff"

    walk(root_a, root_b, "")
    return rows


def _export_destination(destination_text: str) -> Path:
    downloads = (Path.home() / "Downloads").resolve()
    destination = (
        Path(destination_text).expanduser() if destination_text else _DEFAULT_EXPORT_ROOT
    )
    if not destination.is_absolute():
        destination = downloads / destination
    destination = destination.resolve()
    if destination != downloads and not destination.is_relative_to(downloads):
        raise ValueError("导出目录必须位于 Downloads 内")
    return destination


def export_current_files(
    img_path: Path,
    xml_path: Optional[Path],
    destination_text: str,
    include_server: bool,
) -> Dict[str, Any]:
    destination = _export_destination(destination_text)
    sources = [img_path]
    if include_server and xml_path:
        sources.append(xml_path)
    exported = []
    for item in sources:
        item = item.resolve()
        if not item.is_file():
            raise FileNotFoundError(f"文件不存在: {item}")
        try:
            relative = item.relative_to(REPO_ROOT.resolve())
        except ValueError:
            raise ValueError(f"只支持导出仓库内的文件: {item}")
        data = item.read_bytes()
        if item.name.lower().endswith((".xml", ".img.xml")):
            ET.fromstring(data)
        elif not item.name.lower().endswith(".img"):
            raise ValueError(f"不支持导出的文件类型: {item.name}")
        digest = _sha256(data)
        target = destination / relative
        overwritten = target.exists()
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, raw_path = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        temp = Path(raw_path)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp, 0o644)
            os.replace(temp, target)
        except Exception:
            temp.unlink(missing_ok=True)
            raise
        if _sha256(target.read_bytes()) != digest:
            raise ValueError(f"导出后哈希不一致: {target}")
        exported.append({
            "source": str(relative),
            "target": str(target),
            "sha256": digest,
            "size": len(data),
            "overwritten": overwritten,
        })
    return {"destination": str(destination), "files": exported}


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(HERE / "templates"),
        static_folder=str(HERE / "static"),
    )
    shared_lock = threading.RLock()
    states = {"a": EditorState(), "b": EditorState()}
    for state in states.values():
        state.lock = shared_lock
    app.config["EDITOR_STATES"] = states

    def error_response(exc: Exception, status: int = 400):
        return jsonify({"ok": False, "error": str(exc), "type": type(exc).__name__}), status

    def slot_state(body_or_args) -> EditorState:
        slot = body_or_args.get("slot", "a")
        if slot not in ("a", "b"):
            raise ValueError("slot must be 'a' or 'b'")
        return states[slot]

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/state")
    def api_state():
        with shared_lock:
            return jsonify({
                "a": states["a"].state_json(),
                "b": states["b"].state_json(),
            })

    @app.post("/api/suggest-xml")
    def api_suggest_xml():
        body = request.get_json(silent=True) or {}
        raw = body.get("img_path")
        if not isinstance(raw, str) or not raw.strip():
            return error_response(ValueError("img_path is required"))
        suggestion = _suggest_xml_path(Path(raw.strip()))
        return jsonify({
            "ok": True,
            "xml_path": str(suggestion) if suggestion and suggestion.exists() else "",
        })

    @app.post("/api/pick-file")
    def api_pick_file():
        body = request.get_json(silent=True) or {}
        kind = body.get("kind")
        current = body.get("current", "")
        if not isinstance(kind, str) or not isinstance(current, str):
            return error_response(ValueError("kind and current must be strings"))
        try:
            return jsonify({"ok": True, "path": _pick_file(kind, current)})
        except (OSError, RuntimeError, ValueError) as exc:
            return error_response(exc)

    @app.post("/api/open")
    def api_open():
        body = request.get_json(silent=True) or {}
        try:
            state = slot_state(body)
        except ValueError as exc:
            return error_response(exc)
        img_raw = body.get("img_path")
        xml_raw = body.get("xml_path")
        if not isinstance(img_raw, str) or not img_raw.strip():
            return error_response(ValueError("img_path is required"))
        if not isinstance(xml_raw, str) or not xml_raw.strip():
            suggestion = _suggest_xml_path(Path(img_raw.strip()))
            if not suggestion or not suggestion.exists():
                return error_response(ValueError("xml_path is required"))
            xml_raw = str(suggestion)
        requested_region = body.get("region")
        if requested_region in (None, "", "auto"):
            requested_region = None
        try:
            with shared_lock:
                state.load(Path(img_raw.strip()), Path(xml_raw.strip()), requested_region)
                return jsonify({"ok": True, **state.state_json()})
        except (OSError, ValueError) as exc:
            return error_response(exc)

    @app.post("/api/reload")
    def api_reload():
        body = request.get_json(silent=True) or {}
        try:
            state = slot_state(body)
        except ValueError as exc:
            return error_response(exc)
        try:
            with shared_lock:
                if not state.opened:
                    raise RuntimeError("no IMG is open")
                state.reload()
                return jsonify({"ok": True, **state.state_json()})
        except (OSError, ValueError, RuntimeError) as exc:
            return error_response(exc)

    @app.post("/api/children")
    def api_children():
        body = request.get_json(silent=True) or {}
        path = body.get("path", [])
        if not isinstance(path, list) or not all(isinstance(item, str) for item in path):
            return error_response(ValueError("path must be a string array"))
        try:
            state = slot_state(body)
        except ValueError as exc:
            return error_response(exc)
        try:
            with shared_lock:
                node = state.resolve(path)
                if not isinstance(node, WzSubProperty):
                    raise ValueError("node is not a container")
                return jsonify({
                    "ok": True,
                    "path": path,
                    "children": [
                        _property_json(child, [*path, child.name], state.img_path)
                        for child in node.children()
                    ],
                })
        except (RuntimeError, KeyError, ValueError) as exc:
            return error_response(exc, 404 if isinstance(exc, KeyError) else 400)

    @app.post("/api/node")
    def api_node():
        body = request.get_json(silent=True) or {}
        path = body.get("path", [])
        try:
            state = slot_state(body)
        except ValueError as exc:
            return error_response(exc)
        try:
            with shared_lock:
                node = state.resolve(path)
                return jsonify({"ok": True, "node": _property_json(node, path, state.img_path)})
        except (RuntimeError, KeyError, ValueError) as exc:
            return error_response(exc, 404 if isinstance(exc, KeyError) else 400)

    @app.post("/api/search")
    def api_search():
        body = request.get_json(silent=True) or {}
        query = str(body.get("query", "")).strip().lower()
        if not query:
            return jsonify({"ok": True, "results": []})
        try:
            state = slot_state(body)
        except ValueError as exc:
            return error_response(exc)
        try:
            with shared_lock:
                if not state.image:
                    raise RuntimeError("no IMG is open")
                results: List[Dict[str, Any]] = []
                stack = [(child, [child.name]) for child in reversed(state.image.root.children())]
                while stack and len(results) < 200:
                    node, path = stack.pop()
                    value_text = str(_property_value(node)).lower()
                    if query in node.name.lower() or query in value_text:
                        results.append(_property_json(node, path, state.img_path))
                    if isinstance(node, WzSubProperty):
                        stack.extend(
                            (child, [*path, child.name]) for child in reversed(node.children())
                        )
                return jsonify({"ok": True, "results": results, "limited": len(results) == 200})
        except RuntimeError as exc:
            return error_response(exc)

    @app.get("/api/canvas")
    def api_canvas():
        raw = request.args.get("path", "")
        slot = request.args.get("slot", "a")
        if slot not in ("a", "b"):
            return error_response(ValueError("slot must be 'a' or 'b'"))
        try:
            path = list(json.loads(raw)) if raw else []
        except json.JSONDecodeError as exc:
            return error_response(ValueError("invalid path parameter: " + str(exc)))
        if not isinstance(path, list) or not all(isinstance(item, str) for item in path):
            return error_response(ValueError("path must be a JSON string array"))
        state = states[slot]
        try:
            with shared_lock:
                node = state.resolve(path)
                if not isinstance(node, WzCanvasProperty):
                    raise ValueError("node is not a Canvas")
                if not node.has_pixels:
                    raise ValueError("Canvas has no pixel payload")
                region = state.region or "GMS"
                png = decode_canvas(node, region=region)
                buffer = io.BytesIO()
                png.save(buffer, format="PNG")
                buffer.seek(0)
                return send_file(buffer, mimetype="image/png", max_age=60)
        except (RuntimeError, KeyError, ValueError) as exc:
            return error_response(exc, 404 if isinstance(exc, KeyError) else 400)

    @app.post("/api/compare-slots")
    def api_compare_slots():
        try:
            with shared_lock:
                if not states["a"].opened or not states["b"].opened:
                    raise RuntimeError("需要同时打开 A 与 B 才能对比")
                return jsonify({
                    "ok": True,
                    "rows": diff_slot_trees(states["a"].image.root, states["b"].image.root),
                })
        except RuntimeError as exc:
            return error_response(exc)

    @app.post("/api/export")
    def api_export():
        body = request.get_json(silent=True) or {}
        try:
            state = slot_state(body)
        except ValueError as exc:
            return error_response(exc)
        try:
            with shared_lock:
                if not state.opened:
                    raise RuntimeError("no IMG is open")
                result = export_current_files(
                    state.img_path,
                    state.xml_path,
                    str(body.get("destination", "")),
                    bool(body.get("includeServer", True)),
                )
            return jsonify({"ok": True, **result})
        except (OSError, ValueError, RuntimeError) as exc:
            return error_response(exc)

    @app.post("/api/mutate")
    def api_mutate():
        body = request.get_json(silent=True) or {}
        operation = body.get("operation")
        path = body.get("path", [])
        name = body.get("name")
        kind = body.get("kind")
        values = body.get("values") or {}
        if operation not in ("add", "edit", "rename", "remove"):
            return error_response(ValueError("invalid operation"))
        if not isinstance(path, list) or not all(isinstance(item, str) for item in path):
            return error_response(ValueError("path must be a string array"))
        if not isinstance(values, dict):
            return error_response(ValueError("values must be an object"))
        try:
            state = slot_state(body)
        except ValueError as exc:
            return error_response(exc)
        try:
            with shared_lock:
                if not state.opened:
                    raise RuntimeError("no IMG is open")
                assert state.img_path and state.xml_path
                assert state.img_bytes is not None and state.xml_text is not None
                disk_img = state.img_path.read_bytes()
                disk_xml = _read_text(state.xml_path)
                if disk_img != state.img_bytes or disk_xml != state.xml_text:
                    raise RuntimeError("files changed outside the editor; reopen them before saving")

                effective_kind = kind
                if operation != "add":
                    effective_kind = state.resolve(path).type_name
                if operation in ("add", "edit"):
                    if not effective_kind:
                        raise ValueError("kind is required")
                    values = normalized_values(effective_kind, values)

                img_result = mutate_img(
                    disk_img,
                    operation,
                    path,
                    name=name,
                    kind=effective_kind,
                    values=values,
                    region=state.region,
                )
                xml_result = mutate_xml(
                    disk_xml,
                    operation,
                    path,
                    name=name,
                    kind=effective_kind,
                    values=values,
                )
                xml_bytes = xml_result.encode("utf-8")
                img_temp = _write_temp(state.img_path, img_result.data)
                xml_temp = _write_temp(state.xml_path, xml_bytes)
                _backup_once(state.img_path, disk_img)
                _backup_once(state.xml_path, disk_xml.encode("utf-8"))
                img_replaced = False
                xml_replaced = False
                try:
                    os.replace(img_temp, state.img_path)
                    img_replaced = True
                    os.replace(xml_temp, state.xml_path)
                    xml_replaced = True
                except Exception:
                    if img_replaced:
                        _atomic_restore(state.img_path, disk_img)
                    if xml_replaced:
                        _atomic_restore(state.xml_path, disk_xml.encode("utf-8"))
                    raise
                finally:
                    img_temp.unlink(missing_ok=True)
                    xml_temp.unlink(missing_ok=True)

                state.load(state.img_path, state.xml_path, state.region)
                return jsonify({
                    "ok": True,
                    "operation": operation,
                    "path_before": list(img_result.path_before),
                    "path_after": list(img_result.path_after) if img_result.path_after else None,
                    "byte_delta": img_result.byte_delta,
                    "img_sha256": _sha256(img_result.data),
                    "backups": [
                        str(state.img_path) + ".web-editor.bak",
                        str(state.xml_path) + ".web-editor.bak",
                    ],
                })
        except (OSError, RuntimeError, KeyError, FileExistsError, ValueError) as exc:
            status = 409 if isinstance(exc, (FileExistsError, RuntimeError)) else 400
            return error_response(exc, status)

    # ── Mob Skill Effects ──────────────────────────────────────────────

    # MobSkillType names (from Java enum)
    _MOB_SKILL_NAMES = {
        100: "ATTACK_UP", 101: "MAGIC_ATTACK_UP", 102: "DEFENSE_UP", 103: "MAGIC_DEFENSE_UP",
        110: "ATTACK_UP_M", 111: "MAGIC_ATTACK_UP_M", 112: "DEFENSE_UP_M", 113: "MAGIC_DEFENSE_UP_M",
        114: "HEAL_M", 115: "HASTE_M",
        120: "SEAL", 121: "DARKNESS", 122: "WEAKNESS", 123: "STUN", 124: "CURSE",
        125: "POISON", 126: "SLOW", 127: "DISPEL", 128: "SEDUCE", 129: "BANISH",
        131: "AREA_POISON", 132: "REVERSE_INPUT", 133: "UNDEAD", 134: "STOP_POTION",
        135: "STOP_MOTION", 136: "FEAR",
        140: "PHYSICAL_IMMUNE", 141: "MAGIC_IMMUNE", 142: "HARD_SKIN",
        143: "PHYSICAL_COUNTER", 144: "MAGIC_COUNTER", 145: "PHYSICAL_AND_MAGIC_COUNTER",
        150: "PAD", 151: "MAD", 152: "PDR", 153: "MDR", 154: "ACC", 155: "EVA",
        156: "SPEED", 157: "SEAL_SKILL",
        170: "SUMMON_170", 174: "AKAYRUM_BLACK_HOLE_VISUAL", 176: "AKAYRUM_SCREEN_CRACK_VISUAL",
        177: "AKAYRUM_GREEN_ORB_VISUAL", 183: "WILL_WEB_BURST", 184: "MAGNUS_METEOR_STORM",
        185: "LUCID_DREAM_BURST", 186: "SUMMON_186", 187: "SEREN_SACRED_BURST",
        188: "SUMMON_188", 189: "SUMMON_189", 190: "SUMMON_190", 191: "SUMMON_191",
        200: "SUMMON", 201: "SUMMON_201", 202: "SUMMON_202", 203: "SUMMON_203",
        214: "DAMAGE_CANCEL", 215: "MOB_CHANGE",
    }

    _mob_skill_img_cache: Dict[str, Any] = {"data": None, "path": None}

    def _mob_skill_level_has_frames(img: WzImage, skill_id: int, level: int) -> bool:
        """判断某个 MobSkill 等级是否包含 effect/mob Canvas 帧。"""
        try:
            node = img.root.get(f"{skill_id}/level/{level}")
            if not isinstance(node, WzSubProperty):
                return False
            for sub_name in ("effect", "mob"):
                sub = node.get(sub_name)
                if isinstance(sub, WzSubProperty):
                    for child in sub.children():
                        if isinstance(child, WzCanvasProperty) and child.has_pixels:
                            return True
        except Exception:
            return False
        return False

    def _get_mob_skill_img() -> Optional[WzImage]:
        """懒加载 MobSkill.img（客户端二进制 IMG）。"""
        if _mob_skill_img_cache["data"] is not None:
            return _mob_skill_img_cache["data"]
        mob_skill_path = REPO_ROOT / "clien" / "Data" / "Skill" / "MobSkill.img"
        if not mob_skill_path.exists():
            return None
        img_bytes = mob_skill_path.read_bytes()
        try:
            layout = scan_img(img_bytes)
            img = WzImage.from_bytes(img_bytes, key=WzKey.for_region(layout.region), name="MobSkill.img")
            img.parse()
            _mob_skill_img_cache["data"] = img
            _mob_skill_img_cache["path"] = mob_skill_path
            return img
        except Exception:
            return None

    @app.get("/api/mob-skills")
    def api_mob_skills():
        """列出所有 mob 技能类型（id + 名称 + 子节点数）。"""
        img = _get_mob_skill_img()
        if not img:
            return jsonify({"ok": False, "error": "MobSkill.img not found or decode failed"})
        root = img.root
        skills = []
        for child in root.children():
            skill_id = int(child.name) if child.name.isdigit() else 0
            level_node = child.child("level") if isinstance(child, WzSubProperty) else None
            level_count = level_node.child_count() if isinstance(level_node, WzSubProperty) else 0
            skills.append({
                "id": skill_id,
                "name": _MOB_SKILL_NAMES.get(skill_id, child.name),
                "level_count": level_count,
            })
        return jsonify({"ok": True, "skills": skills})

    @app.get("/api/mob-skill-effect")
    def api_mob_skill_effect():
        """返回指定 mob 技能等级的 effect Canvas 帧列表（PNG 预览 URL + 元数据）。"""
        skill_id = request.args.get("skillId", "")
        level = request.args.get("level", "1")
        if not skill_id.isdigit() or not level.isdigit():
            return error_response(ValueError("skillId and level must be integers"))
        img = _get_mob_skill_img()
        if not img:
            return jsonify({"ok": False, "error": "MobSkill.img not found"})
        try:
            skill_node = img.root.get(f"{skill_id}/level/{level}")
            if not isinstance(skill_node, WzSubProperty):
                raise KeyError(f"Skill {skill_id} level {level} not found")
            effect_node = skill_node.get("effect")
            frames = []
            if isinstance(effect_node, WzSubProperty):
                for child in effect_node.children():
                    if isinstance(child, WzCanvasProperty) and child.has_pixels:
                        origin_node = child.get("origin")
                        delay_node = child.get("delay")
                        ox = getattr(origin_node, "x", None)
                        oy = getattr(origin_node, "y", None)
                        frames.append({
                            "name": child.name,
                            "width": child.width,
                            "height": child.height,
                            "origin": (
                                {"x": ox, "y": oy}
                                if ox is not None and oy is not None else None
                            ),
                            "delay": int(delay_node.value) if delay_node is not None else None,
                        })
            # Also get mob overlay frames
            mob_frames = []
            mob_node = skill_node.get("mob")
            if isinstance(mob_node, WzSubProperty):
                for child in mob_node.children():
                    if isinstance(child, WzCanvasProperty) and child.has_pixels:
                        origin_node = child.get("origin")
                        ox = getattr(origin_node, "x", None)
                        oy = getattr(origin_node, "y", None)
                        mob_frames.append({
                            "name": child.name,
                            "width": child.width,
                            "height": child.height,
                            "origin": (
                                {"x": ox, "y": oy}
                                if ox is not None and oy is not None else None
                            ),
                        })
            # Get other fields
            fields = {}
            for child in skill_node.children():
                if child.name not in ("effect", "mob") and not isinstance(child, (WzCanvasProperty, WzSubProperty)):
                    fields[child.name] = _property_value(child)
            return jsonify({
                "ok": True,
                "skillId": int(skill_id),
                "level": int(level),
                "skillName": _MOB_SKILL_NAMES.get(int(skill_id), skill_id),
                "effect_frames": frames,
                "mob_frames": mob_frames,
                "fields": fields,
            })
        except (KeyError, ValueError) as exc:
            return error_response(exc, 404)

    @app.get("/api/node-mob-skill")
    def api_node_mob_skill():
        """给定选中的节点路径，向上回溯祖先，查找 mobSkillID 引用。

        找到则返回对应的 MobSkill 编号、名称、可用等级（用于预览）。
        """
        raw = request.args.get("path", "")
        slot = request.args.get("slot", "a")
        if slot not in ("a", "b"):
            return error_response(ValueError("slot must be 'a' or 'b'"))
        try:
            path = list(json.loads(raw)) if raw else []
        except json.JSONDecodeError as exc:
            return error_response(ValueError("invalid path parameter: " + str(exc)))
        if not isinstance(path, list) or not all(isinstance(item, str) for item in path):
            return error_response(ValueError("path must be a JSON string array"))
        state = states[slot]
        try:
            with shared_lock:
                node = state.resolve(path)
                cur = node
                while cur is not None:
                    if isinstance(cur, WzSubProperty):
                        for child in cur.children():
                            if child.name == "mobSkillID" and isinstance(child.value, int):
                                msid = int(child.value)
                                # 找到该 MobSkill 可用于预览的等级：
                                # 优先选"包含 effect/mob Canvas 帧"的等级（从低到高），
                                # 否则回退到最高可用等级。
                                preview_level = 1
                                mob_img = _get_mob_skill_img()
                                if mob_img is not None:
                                    try:
                                        level_node = mob_img.root.get(f"{msid}/level")
                                        if isinstance(level_node, WzSubProperty):
                                            levels = sorted(
                                                int(c.name) for c in level_node.children()
                                                if c.name.isdigit()
                                            )
                                            if levels:
                                                chosen = None
                                                for lv in levels:
                                                    if _mob_skill_level_has_frames(mob_img, msid, lv):
                                                        chosen = lv
                                                        break
                                                preview_level = chosen if chosen is not None else max(levels)
                                    except Exception:
                                        pass
                                return jsonify({
                                    "ok": True,
                                    "found": True,
                                    "mobSkillId": msid,
                                    "mobSkillName": _MOB_SKILL_NAMES.get(msid, str(msid)),
                                    "previewLevel": preview_level,
                                    "path": "/".join(path),
                                })
                    cur = cur.parent
                return jsonify({"ok": True, "found": False})
        except (RuntimeError, KeyError, ValueError) as exc:
            return error_response(exc, 404 if isinstance(exc, KeyError) else 400)

    @app.get("/api/node-uol")
    def api_node_uol():
        """给定选中的节点路径，若为 UOL（引用）则解析其目标节点，返回：

        - uolLink：UOL 原始链接值（相对路径字符串）
        - targetPath / targetName / targetType：解析后目标节点的绝对路径、名称、类型
        - canvas：若目标节点（或其子树）包含带像素的 Canvas，返回其路径与元数据，
          前端据此直接取 /api/canvas 显示被引用节点的画面
        """
        raw = request.args.get("path", "")
        slot = request.args.get("slot", "a")
        if slot not in ("a", "b"):
            return error_response(ValueError("slot must be 'a' or 'b'"))
        try:
            path = list(json.loads(raw)) if raw else []
        except json.JSONDecodeError as exc:
            return error_response(ValueError("invalid path parameter: " + str(exc)))
        if not isinstance(path, list) or not all(isinstance(item, str) for item in path):
            return error_response(ValueError("path must be a JSON string array"))
        state = states[slot]
        try:
            with shared_lock:
                node = state.resolve(path)
                if not isinstance(node, WzUolProperty):
                    return jsonify({"ok": True, "isUol": False, "type": node.type_name})
                link = node.value
                target = _resolve_uol_target(node)
                payload: Dict[str, Any] = {
                    "ok": True,
                    "isUol": True,
                    "uolLink": link,
                    "selectedPath": "/".join(path),
                    "resolved": target is not None,
                }
                if target is None:
                    payload["reason"] = (
                        "无法解析该 UOL：链接目标不存在、路径无效，或跨越了文件边界 "
                        "（本编辑器每次只加载单个 IMG）。"
                    )
                    return jsonify(payload)
                target_path = _absolute_path(target)
                payload["targetPath"] = "/".join(target_path)
                payload["targetName"] = target.name
                payload["targetType"] = target.type_name

                canvas, _sub = _find_first_canvas(target)
                # 处理 _outlink / _inlink 占位 Canvas：尝试跟随取到真实像素
                if canvas is not None and not canvas.has_pixels:
                    try:
                        from wzpy.wz_package import resolve_canvas_link
                        linked = resolve_canvas_link(canvas, state.image.root)
                        if linked is not None and linked.has_pixels:
                            canvas = linked
                    except Exception:
                        pass
                if canvas is not None and canvas.has_pixels:
                    canvas_path = _absolute_path(canvas)
                    origin_node = canvas.get("origin")
                    ox = getattr(origin_node, "x", None) if isinstance(origin_node, WzVectorProperty) else None
                    oy = getattr(origin_node, "y", None) if isinstance(origin_node, WzVectorProperty) else None
                    delay_node = canvas.get("delay")
                    delay = None
                    if delay_node is not None and hasattr(delay_node, "value"):
                        try:
                            delay = int(delay_node.value)
                        except (TypeError, ValueError):
                            delay = None
                    payload["canvas"] = {
                        "path": "/".join(canvas_path),
                        "width": canvas.width,
                        "height": canvas.height,
                        "origin": (
                            {"x": ox, "y": oy}
                            if ox is not None and oy is not None else None
                        ),
                        "delay": delay,
                    }
                else:
                    payload["canvas"] = None
                return jsonify(payload)
        except (RuntimeError, KeyError, ValueError) as exc:
            return error_response(exc, 404 if isinstance(exc, KeyError) else 400)

    @app.get("/api/mob-skill-canvas")
    def api_mob_skill_canvas():
        """返回 MobSkill effect Canvas PNG。"""
        skill_id = request.args.get("skillId", "")
        level = request.args.get("level", "1")
        frame = request.args.get("frame", "0")
        kind = request.args.get("kind", "effect")  # "effect" or "mob"
        if not skill_id.isdigit() or not level.isdigit():
            return error_response(ValueError("skillId and level must be integers"))
        img = _get_mob_skill_img()
        if not img:
            return jsonify({"ok": False, "error": "MobSkill.img not found"})
        try:
            node = img.root.get(f"{skill_id}/level/{level}/{kind}/{frame}")
            if not isinstance(node, WzCanvasProperty) or not node.has_pixels:
                raise KeyError("Canvas not found or has no pixels")
            png = decode_canvas(node, region="GMS")
            buffer = io.BytesIO()
            png.save(buffer, format="PNG")
            buffer.seek(0)
            return send_file(buffer, mimetype="image/png", max_age=60)
        except (KeyError, ValueError) as exc:
            return error_response(exc, 404)

    return app


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Local standalone IMG/XML web editor")
    parser.add_argument("--port", type=int, default=5017)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    create_app().run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
