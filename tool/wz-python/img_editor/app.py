from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from flask import Flask, jsonify, render_template, request

HERE = Path(__file__).resolve().parent
WZPY_ROOT = HERE.parent
REPO_ROOT = WZPY_ROOT.parent.parent
if str(WZPY_ROOT) not in sys.path:
    sys.path.insert(0, str(WZPY_ROOT))

from wzpy.crypto import WzKey  # noqa: E402
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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_temp(path: Path, payload: bytes) -> Path:
    fd, raw_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(raw_path)
    try:
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


def _property_json(prop: WzProperty, path: Sequence[str]) -> Dict[str, Any]:
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
    }


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
        scan_xml(xml_text)
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
        }


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(HERE / "templates"),
        static_folder=str(HERE / "static"),
    )
    state = EditorState()
    app.config["EDITOR_STATE"] = state

    def error_response(exc: Exception, status: int = 400):
        return jsonify({"ok": False, "error": str(exc), "type": type(exc).__name__}), status

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/state")
    def api_state():
        with state.lock:
            return jsonify(state.state_json())

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

    @app.post("/api/open")
    def api_open():
        body = request.get_json(silent=True) or {}
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
            with state.lock:
                state.load(Path(img_raw.strip()), Path(xml_raw.strip()), requested_region)
                return jsonify({"ok": True, **state.state_json()})
        except (OSError, ValueError) as exc:
            return error_response(exc)

    @app.post("/api/children")
    def api_children():
        body = request.get_json(silent=True) or {}
        path = body.get("path", [])
        if not isinstance(path, list) or not all(isinstance(item, str) for item in path):
            return error_response(ValueError("path must be a string array"))
        try:
            with state.lock:
                node = state.resolve(path)
                if not isinstance(node, WzSubProperty):
                    raise ValueError("node is not a container")
                return jsonify({
                    "ok": True,
                    "path": path,
                    "children": [
                        _property_json(child, [*path, child.name]) for child in node.children()
                    ],
                })
        except (RuntimeError, KeyError, ValueError) as exc:
            return error_response(exc, 404 if isinstance(exc, KeyError) else 400)

    @app.post("/api/node")
    def api_node():
        body = request.get_json(silent=True) or {}
        path = body.get("path", [])
        try:
            with state.lock:
                node = state.resolve(path)
                return jsonify({"ok": True, "node": _property_json(node, path)})
        except (RuntimeError, KeyError, ValueError) as exc:
            return error_response(exc, 404 if isinstance(exc, KeyError) else 400)

    @app.post("/api/search")
    def api_search():
        body = request.get_json(silent=True) or {}
        query = str(body.get("query", "")).strip().lower()
        if not query:
            return jsonify({"ok": True, "results": []})
        try:
            with state.lock:
                if not state.image:
                    raise RuntimeError("no IMG is open")
                results: List[Dict[str, Any]] = []
                stack = [(child, [child.name]) for child in reversed(state.image.root.children())]
                while stack and len(results) < 200:
                    node, path = stack.pop()
                    value_text = str(_property_value(node)).lower()
                    if query in node.name.lower() or query in value_text:
                        results.append(_property_json(node, path))
                    if isinstance(node, WzSubProperty):
                        stack.extend(
                            (child, [*path, child.name]) for child in reversed(node.children())
                        )
                return jsonify({"ok": True, "results": results, "limited": len(results) == 200})
        except RuntimeError as exc:
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
            with state.lock:
                if not state.opened:
                    raise RuntimeError("no IMG is open")
                assert state.img_path and state.xml_path
                assert state.img_bytes is not None and state.xml_text is not None
                disk_img = state.img_path.read_bytes()
                disk_xml = _read_text(state.xml_path)
                if disk_img != state.img_bytes or disk_xml != state.xml_text:
                    raise RuntimeError("files changed outside the editor; reopen them before saving")

                effective_kind = kind
                if operation == "edit":
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
