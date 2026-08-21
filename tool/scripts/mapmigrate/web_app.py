#!/usr/bin/env python3
"""地图 / Boss 迁移兼容性 Web 工作台。

参考 tool/scripts/png2canvas 的架构，但核心从「Canvas 像素替换」改为
「节点兼容性分析 + 一键清洗 + 报告导出」。

启动：
  rtk tool/scripts/mapmigrate/mapmigrate.sh [--host 127.0.0.1] [--port 8770]
或
  python3 tool/scripts/mapmigrate/web_app.py [--host 127.0.0.1] [--port 8770]
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
_WZPY = _ROOT / "tool" / "wz-python"
for path in (str(_HERE), str(_WZPY), str(_ROOT / "tool" / "scripts" / "png2canvas")):
    if path not in sys.path:
        sys.path.insert(0, path)

from flask import Flask, jsonify, request, send_file  # noqa: E402
from PIL import Image as PILImage  # noqa: E402
from wzpy import WzImage, WzKey, detect_region_from_img  # noqa: E402
from wzpy.canvas import _read_canvas_bytes, decode_canvas  # noqa: E402
from wzpy.properties import (  # noqa: E402
    WzCanvasProperty,
    WzConvexProperty,
    WzDoubleProperty,
    WzFloatProperty,
    WzIntProperty,
    WzLongProperty,
    WzNullProperty,
    WzRawDataProperty,
    WzShortProperty,
    WzSoundProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.writer import encode_image_body  # noqa: E402

import compat  # noqa: E402
import replace_img_canvas as replace  # noqa: E402

app = Flask(__name__)

MAX_FLAT = 20000  # 超过则截断，避免单次响应过大
FULL_REWRITE_ENV = "MAPMIGRATE_UNSAFE_FULL_REWRITE"
TEXTURE_EDGE_LIMIT = 2048


# --------------------------------------------------------------------------
# 路径工具
# --------------------------------------------------------------------------

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


def full_rewrite_enabled() -> bool:
    return os.environ.get(FULL_REWRITE_ENV, "").strip() == "1"


def require_full_rewrite_enabled() -> None:
    if not full_rewrite_enabled():
        raise PermissionError(
            "生产 IMG 写入已禁用：当前实现会整树序列化，可能破坏旧客户端二进制布局。"
            f"仅在明确接受风险时设置 {FULL_REWRITE_ENV}=1；新工具应改用增量记录补丁。"
        )


def default_client_img(mode: str, item_id: str) -> Path:
    if mode == "map":
        prefix = item_id[:1] if item_id else "0"
        return _ROOT / "clien" / "Data" / "Map" / "Map" / f"Map{prefix}" / f"{item_id}.img"
    return _ROOT / "clien" / "Data" / "Mob" / f"{item_id}.img"


def default_server_xml(mode: str, item_id: str) -> Path:
    if mode == "map":
        prefix = item_id[:1] if item_id else "0"
        return _ROOT / "gms-server" / "wz" / "Map.wz" / "Map" / f"Map{prefix}" / f"{item_id}.img.xml"
    return _ROOT / "gms-server" / "wz" / "Mob.wz" / f"{item_id}.img.xml"


def path_for_picker(raw: str) -> Path:
    path = root_path(raw) if raw else _ROOT
    if path.is_file():
        return path.parent
    return path


def file_matches_kind(path: Path, kind: str) -> bool:
    name = path.name.lower()
    if kind in ("img", "reference"):
        return name.endswith(".img")
    if kind == "ms":
        return name.endswith(".ms")
    if kind == "xml":
        return name.endswith(".img.xml") or name.endswith(".xml")
    return path.is_file()


def list_picker_dir(raw: str, kind: str) -> dict[str, Any]:
    current = path_for_picker(raw).expanduser().resolve()
    if not current.exists():
        current = _ROOT
    if not current.is_dir():
        current = current.parent
    dirs, files = [], []
    for item in sorted(current.iterdir(), key=lambda p: (not p.is_dir(), replace.natural_key(p.name))):
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


def load_client_image(img_path: Path, region: str | None = None) -> WzImage:
    data = img_path.read_bytes()
    if region is None:
        region = detect_region_from_img(data)
    key = WzKey.for_region(region) if region is not None else WzKey.for_region("GMS")
    image = WzImage.from_bytes(data, key=key, name=img_path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        warnings = "; ".join(image.parse_warnings) or "文件被截断"
        raise ValueError(f"IMG 解析不完整，已拒绝继续：{warnings}")
    image._region = region
    return image


# --------------------------------------------------------------------------
# 新客户端 .ms 包解析（经 MSProbe.dll + dotnet 解密，输出 legacy .img）
# --------------------------------------------------------------------------

MSPROBE_DLL = Path(os.environ.get(
    "MSPROBE_DLL",
    "/Users/lizixian/Documents/mxd/TMS/black_mage_report_tools/ms_probe/bin/Debug/net8.0/MSProbe.dll",
))
DOTNET_BIN = os.environ.get("DOTNET_BIN", "/opt/homebrew/bin/dotnet")
MSPACKS_DIR = Path(os.environ.get(
    "MSPACKS_DIR",
    "/Users/lizixian/Documents/mxd/TMS/MapleStory/Data/Packs",
))
MS_IMG_DATA_DIR = Path(os.environ.get(
    "MS_IMG_DATA_DIR",
    "/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data",
))
MS_CACHE = Path(tempfile.gettempdir()) / "mapmigrate_ms_cache"
MS_CACHE.mkdir(parents=True, exist_ok=True)


def ms_available() -> bool:
    return MSPROBE_DLL.is_file() and shutil.which(DOTNET_BIN) is not None


def ms_mode_for_entry(entry: str) -> str:
    """从条目路径推断分析模式：Mob/*→boss, Map/*→map, 其余→boss(可手动覆盖)。"""
    head = entry.split("/", 1)[0].lower()
    if head == "map":
        return "map"
    if head == "mob":
        return "boss"
    return "boss"


def ms_canvas_entry_name(entry: str) -> str | None:
    """新客户端把贴图像素放在独立的 `_Canvas` 条目里（如
    ``Mob/8880000.img`` → ``Mob/_Canvas/8880000.img``），主条目只留 1x1
    占位 + _outlink。返回对应条目名，无斜杠则返回 None。"""
    i = entry.find("/")
    if i < 0:
        return None
    head, rest = entry[:i], entry[i + 1:]
    return f"{head}/_Canvas/{rest}"


def loose_canvas_path(img_path: Path) -> Path | None:
    """查找现代散 IMG 同目录下的 ``_Canvas/<同名>.img``。"""
    candidate = img_path.parent / "_Canvas" / img_path.name
    return candidate if candidate.is_file() else None


def ms_locate_entry(pack_dir: Path, entry_name: str) -> Path | None:
    """优先找已导出的现代散 IMG，否则跨 .ms 包精确查找并提取。"""
    loose = MS_IMG_DATA_DIR / Path(entry_name)
    if loose.is_file():
        return loose
    if not pack_dir.is_dir():
        return None
    for pack in sorted(pack_dir.glob("*.ms")):
        try:
            entries = ms_list_entries(pack)
        except Exception:
            continue
        if entry_name in entries:
            try:
                return ms_extract_entry(pack, entry_name)
            except Exception:
                return None
    return None


def outlink_canvas_target(prop) -> tuple[str, str] | None:
    """返回 Canvas ``_outlink`` 指向的 ``(条目名, 节点路径)``。"""
    if not isinstance(prop, WzCanvasProperty):
        return None
    link = prop.child("_outlink")
    if not isinstance(link, WzStringProperty):
        return None
    target_str = str(link.value)
    idx = target_str.find(".img/")
    if idx < 0:
        return None
    entry_name = target_str[:idx + 4]
    sub = target_str[idx + 5:]
    return entry_name, sub


def resolve_outlink_canvas(prop, region: str, canvas_entry_path: Path | None = None):
    """若 prop 是带 _outlink 的占位 canvas，则解析真实像素画布。
    canvas_entry_path 与链接条目匹配时优先；否则按链接里的精确条目跨包定位。"""
    target = outlink_canvas_target(prop)
    if target is None:
        return None
    entry_name, sub = target
    ce_path = Path(canvas_entry_path) if canvas_entry_path else None
    if ce_path is None or not ce_path.exists() or ce_path.name != Path(entry_name).name:
        ce_path = ms_locate_entry(MSPACKS_DIR, entry_name)
    if not ce_path:
        return None
    try:
        ce = load_client_image(Path(ce_path), region)
        node = ce.root.get(sub)
        return node if isinstance(node, WzCanvasProperty) else None
    except Exception:
        return None


def annotate_resolved_canvases(result: dict[str, Any], source_path: Path,
                               default_canvas_path: Path | None, mode: str) -> int:
    """给现代占位 Canvas 附加真实外链 Canvas 元数据，供详情页明确区分。"""
    source = load_client_image(source_path)
    region = getattr(source, "_region", None) or "GMS"
    image_cache: dict[Path, WzImage] = {}
    resolved_count = 0
    for row in result.get("flat", []):
        node = row.get("sourceNode") if "sourceNode" in row else row
        if not node or node.get("type") != "canvas":
            continue
        prop = source.root.get(node.get("path", ""))
        target = outlink_canvas_target(prop)
        if target is None:
            continue
        entry_name, sub = target
        canvas_path = default_canvas_path
        if (canvas_path is None or not canvas_path.is_file()
                or canvas_path.name != Path(entry_name).name):
            canvas_path = ms_locate_entry(MSPACKS_DIR, entry_name)
        if canvas_path is None:
            continue
        canvas_path = canvas_path.resolve()
        try:
            canvas_image = image_cache.get(canvas_path)
            if canvas_image is None:
                canvas_image = load_client_image(canvas_path, region)
                image_cache[canvas_path] = canvas_image
            resolved_prop = canvas_image.root.get(sub)
            if not isinstance(resolved_prop, WzCanvasProperty):
                continue
            resolved = meta_of(resolved_prop)
            resolved["texture"] = texture_metrics({**resolved, "origin": node.get("origin")})
            resolved_node = {
                "name": node.get("name", ""),
                "parent_name": node.get("parent_name", ""),
                "path": node.get("path", ""),
                **resolved,
            }
            verdict = compat.evaluate(resolved_node, mode)
            resolved.update({
                "entry": entry_name,
                "path": sub,
                "status": verdict.status,
                "reason": verdict.reason,
                "suggestion": verdict.suggestion,
            })
            node["resolvedCanvas"] = resolved
            resolved_count += 1
        except Exception:
            continue
    update_result_modern_tags(result)
    update_texture_summary(result)
    return resolved_count


def ms_list_entries(pack_path: Path) -> list[str]:
    """用 MSProbe --list 列出 .ms 包内全部条目（按包 mtime/size 缓存）。"""
    pack_key = hashlib.sha256(str(pack_path.resolve()).encode()).hexdigest()[:16]
    cache = MS_CACHE / f"{pack_path.name}.{pack_key}.entries.json"
    try:
        st = pack_path.stat()
        if cache.exists():
            rec = json.loads(cache.read_text())
            if rec.get("mtime") == st.st_mtime and rec.get("size") == st.st_size:
                return rec["entries"]
    except Exception:
        pass
    out = subprocess.run(
        [DOTNET_BIN, str(MSPROBE_DLL), str(pack_path), str(MS_CACHE / "_list"), "--list"],
        capture_output=True, text=True, check=True,
    )
    entries = [ln.strip() for ln in out.stdout.splitlines() if ln.strip().endswith(".img")]
    try:
        st = pack_path.stat()
        cache.write_text(json.dumps({"mtime": st.st_mtime, "size": st.st_size, "entries": entries}))
    except Exception:
        pass
    return entries


def ms_extract_entry(pack_path: Path, entry: str) -> Path:
    """解密提取单个条目（如 'Mob/8880000.img'）到缓存，返回 legacy .img 路径。"""
    entries = ms_list_entries(pack_path)
    if entry not in entries:
        raise FileNotFoundError(f"{pack_path.name} 中没有精确条目 {entry}")
    pack_key = hashlib.sha256(str(pack_path.resolve()).encode()).hexdigest()[:16]
    out_name = entry.replace("/", "_")
    extract_dir = MS_CACHE / "_extract" / pack_key
    target = extract_dir / out_name
    cache_meta = extract_dir / (out_name + ".meta.json")
    try:
        st = pack_path.stat()
        if target.exists() and cache_meta.exists():
            rec = json.loads(cache_meta.read_text())
            if rec.get("mtime") == st.st_mtime and rec.get("size") == st.st_size:
                return target
    except Exception:
        pass
    prefix = entry[:-4] if entry.lower().endswith(".img") else entry
    extract_dir.mkdir(parents=True, exist_ok=True)
    res = subprocess.run(
        [DOTNET_BIN, str(MSPROBE_DLL), str(pack_path), str(extract_dir), prefix],
        capture_output=True, text=True, check=True,
    )
    if not target.exists():
        raise FileNotFoundError(f"MSProbe 未能提取 {entry}：{res.stdout} {res.stderr}")
    try:
        st = pack_path.stat()
        cache_meta.write_text(json.dumps({"mtime": st.st_mtime, "size": st.st_size}))
    except Exception:
        pass
    return target


def normalized_img_path(root: Any, path: str) -> str:
    parts = [p for p in path.strip("/").split("/") if p]
    if parts and parts[0] == getattr(root, "name", ""):
        parts = parts[1:]
    return "/".join(parts)


# --------------------------------------------------------------------------
# 节点归一化
# --------------------------------------------------------------------------

def meta_of(prop: Any) -> dict[str, Any]:
    if isinstance(prop, WzCanvasProperty):
        ints = {c.name: int(c.value) for c in prop.children() if isinstance(c, WzIntProperty)}
        origin = None
        o = prop.child("origin")
        if isinstance(o, WzVectorProperty):
            origin = {"x": int(o.x), "y": int(o.y)}
        pixel_sha256 = None
        payload_bytes = 0
        if prop.has_pixels():
            payload = _read_canvas_bytes(prop)
            payload_bytes = len(payload)
            pixel_sha256 = hashlib.sha256(payload).hexdigest()
        meta = {
            "type": "canvas",
            "width": int(prop.width),
            "height": int(prop.height),
            "format": int(prop.format),
            "format2": int(prop.format2),
            "origin": origin,
            "ints": ints,
            "children": len(list(prop.children())),
            "hasPixels": prop.has_pixels(),
            "pixelSha256": pixel_sha256,
            "payloadBytes": payload_bytes,
        }
        meta["texture"] = texture_metrics(meta)
        return meta
    if isinstance(prop, WzUolProperty):
        return {"type": "uol", "value": str(prop.value)}
    if isinstance(prop, WzVectorProperty):
        return {"type": "vector", "value": {"x": int(prop.x), "y": int(prop.y)}}
    if isinstance(prop, (WzShortProperty, WzIntProperty, WzLongProperty)):
        return {"type": "int", "value": int(prop.value)}
    if isinstance(prop, WzStringProperty):
        return {"type": "string", "value": str(prop.value)}
    if isinstance(prop, (WzFloatProperty, WzDoubleProperty)):
        return {"type": "float", "value": float(prop.value)}
    if isinstance(prop, WzNullProperty):
        return {"type": "null", "value": None}
    if isinstance(prop, WzSoundProperty):
        return {"type": "sound", "lengthMs": int(prop.length_ms), "bytes": int(prop.value)}
    if isinstance(prop, WzRawDataProperty):
        return {"type": "rawdata", "bytes": int(prop.value), "children": len(list(prop.children()))}
    if isinstance(prop, WzConvexProperty):
        return {"type": "convex", "value": list(prop.value), "children": len(list(prop.children()))}
    if isinstance(prop, WzSubProperty):
        return {"type": "imgdir", "children": len(list(prop.children()))}
    return {"type": str(getattr(prop, "type_name", "unknown")).lower()}


def _next_power_of_two(value: int) -> int:
    return 0 if value <= 0 else 1 << (value - 1).bit_length()


def texture_metrics(meta: dict[str, Any], edge_limit: int = TEXTURE_EDGE_LIMIT) -> dict[str, Any]:
    """计算 Canvas 纹理占用和保持比例的旧端尺寸投影。"""
    width = max(0, int(meta.get("width") or 0))
    height = max(0, int(meta.get("height") or 0))
    pixels = width * height
    scale = min(1.0, edge_limit / width if width else 1.0, edge_limit / height if height else 1.0)
    target_width = max(1, min(edge_limit, round(width * scale))) if width else 0
    target_height = max(1, min(edge_limit, round(height * scale))) if height else 0
    origin = meta.get("origin")
    projected_origin = None
    if isinstance(origin, dict) and width and height:
        projected_origin = {
            "x": round(int(origin.get("x") or 0) * target_width / width),
            "y": round(int(origin.get("y") or 0) * target_height / height),
        }
    pot_width = _next_power_of_two(width)
    pot_height = _next_power_of_two(height)
    return {
        "edgeLimit": edge_limit,
        "overLimit": width > edge_limit or height > edge_limit,
        "pixelCount": pixels,
        "payloadBytes": int(meta.get("payloadBytes") or 0),
        "argb4444Bytes": pixels * 2,
        "rgbaBytes": pixels * 4,
        "potWidth": pot_width,
        "potHeight": pot_height,
        "potArgb4444Bytes": pot_width * pot_height * 2,
        "suggestedWidth": target_width,
        "suggestedHeight": target_height,
        "scale": scale,
        "suggestedOrigin": projected_origin,
    }


def update_texture_summary(result: dict[str, Any]) -> None:
    """按迁移源的真实外链 Canvas（若有）刷新纹理汇总。"""
    textures = []
    for row in result.get("flat", []):
        node = row.get("sourceNode") if "sourceNode" in row else row
        if not node or node.get("type") != "canvas":
            continue
        effective = node.get("resolvedCanvas") or node
        metric = effective.get("texture")
        if metric:
            textures.append((node.get("path", ""), effective, metric))
    largest = max(textures, key=lambda item: item[2]["pixelCount"], default=None)
    result["summary"]["textures"] = {
        "count": len(textures),
        "overLimit": sum(1 for _, _, metric in textures if metric["overLimit"]),
        "formatIssues": sum(
            1 for _, node, _ in textures
            if (node.get("format"), node.get("format2")) != (1, 0)
        ),
        "payloadBytes": sum(metric["payloadBytes"] for _, _, metric in textures),
        "argb4444Bytes": sum(metric["argb4444Bytes"] for _, _, metric in textures),
        "rgbaBytes": sum(metric["rgbaBytes"] for _, _, metric in textures),
        "potArgb4444Bytes": sum(metric["potArgb4444Bytes"] for _, _, metric in textures),
        "maxWidth": max((node.get("width", 0) for _, node, _ in textures), default=0),
        "maxHeight": max((node.get("height", 0) for _, node, _ in textures), default=0),
        "largestPath": largest[0] if largest else "",
        "largestPixels": largest[2]["pixelCount"] if largest else 0,
        "edgeLimit": TEXTURE_EDGE_LIMIT,
    }


def annotate_modern_tags(nodes: list[dict[str, Any]]) -> None:
    """标记节点所属的现代容器，以及节点自身使用的现代资源。"""
    modern_node_paths: dict[str, str] = {}
    resource_tags: dict[str, list[dict[str, str]]] = {}
    for node in nodes:
        path = node.get("path", "")
        name = node.get("name", "")
        reason = node.get("reason", "") or ""
        status = node.get("status", "ok")
        effective = node.get("resolvedCanvas") or node
        tags: list[dict[str, str]] = []
        if effective.get("type") == "canvas" and (
            effective.get("format"), effective.get("format2")
        ) != (1, 0):
            tags.append({
                "kind": "resource",
                "label": "纹理 %s/%s" % (effective.get("format"), effective.get("format2")),
                "path": path,
            })
        if name in {"_outlink", "_inlink"}:
            tags.append({"kind": "resource", "label": "现代外链", "path": path})
        if effective.get("type") in {"rawdata", "video"}:
            tags.append({"kind": "resource", "label": effective.get("type", "现代资源"), "path": path})
        if name.lower() in compat.SPINE_NAMES or "Spine" in reason:
            tags.append({"kind": "resource", "label": "Spine", "path": path})
        resource_tags[path] = tags

        is_modern_node = (
            (path == "flip" and name == "flip")
            or status == "modern"
            or ("现代" in reason and not tags)
        )
        if is_modern_node:
            modern_node_paths[path] = path or name

    for node in nodes:
        path = node.get("path", "")
        tags = list(resource_tags.get(path, []))
        parts = [part for part in path.split("/") if part]
        for end in range(len(parts), 0, -1):
            ancestor = "/".join(parts[:end])
            if ancestor in modern_node_paths:
                tags.insert(0, {"kind": "node", "label": modern_node_paths[ancestor], "path": ancestor})
                break
        node["modernTags"] = tags


def update_result_modern_tags(result: dict[str, Any]) -> None:
    source_nodes, reference_nodes = [], []
    for row in result.get("flat", []):
        if "sourceNode" in row:
            if row.get("sourceNode"):
                source_nodes.append(row["sourceNode"])
            if row.get("referenceNode"):
                reference_nodes.append(row["referenceNode"])
        else:
            source_nodes.append(row)
    annotate_modern_tags(source_nodes)
    annotate_modern_tags(reference_nodes)


def texture_report_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in result.get("flat", []):
        node = row.get("sourceNode") if "sourceNode" in row else row
        if not node or node.get("type") != "canvas":
            continue
        effective = node.get("resolvedCanvas") or node
        rows.append({
            "path": node.get("path", ""),
            "width": effective.get("width", 0),
            "height": effective.get("height", 0),
            "format": effective.get("format"),
            "format2": effective.get("format2"),
            "pixelSha256": effective.get("pixelSha256"),
            "sourceEntry": effective.get("entry", ""),
            "sourcePath": effective.get("path", node.get("path", "")),
            "texture": effective.get("texture", {}),
        })
    return rows


def format_texture_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"].get("textures", {})
    rows = texture_report_rows(result)
    lines = [
        "## 纹理审计",
        "",
        "- 实际纹理：%d　尺寸超限：%d　格式不兼容：%d" % (
            summary.get("count", 0), summary.get("overLimit", 0), summary.get("formatIssues", 0)),
        "- 最大尺寸：%dx%d　ARGB4444 理论：%d bytes　RGBA 解码：%d bytes　POT 保守：%d bytes" % (
            summary.get("maxWidth", 0), summary.get("maxHeight", 0),
            summary.get("argb4444Bytes", 0), summary.get("rgbaBytes", 0),
            summary.get("potArgb4444Bytes", 0)),
        "",
        "| 路径 | 尺寸 | 格式 | 像素 | ARGB4444 | POT 估算 | 2048 投影 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        metric = row["texture"]
        if not metric.get("overLimit") and (row["format"], row["format2"]) == (1, 0):
            continue
        projection = "%dx%d (%.1f%%)" % (
            metric.get("suggestedWidth", 0), metric.get("suggestedHeight", 0),
            float(metric.get("scale", 0)) * 100,
        )
        lines.append("| `%s` | %dx%d | %s/%s | %d | %d | %d | %s |" % (
            row["path"], row["width"], row["height"], row["format"], row["format2"],
            metric.get("pixelCount", 0), metric.get("argb4444Bytes", 0),
            metric.get("potArgb4444Bytes", 0), projection,
        ))
    lines.append("")
    return "\n".join(lines)


def walk_flat(prop: Any, path: str, parent_name: str, out: list[dict], depth: int) -> None:
    name = prop.name if path else "<root>"
    m = meta_of(prop)
    out.append({
        "name": name,
        "path": path,
        "parent_name": parent_name,
        "depth": depth,
        **m,
    })
    if isinstance(prop, WzSubProperty):
        for ch in prop.children():
            cpath = (path + "/" + ch.name) if path else ch.name
            cparent = "" if path == "" else name
            walk_flat(ch, cpath, cparent, out, depth + 1)


def build_nav_tree(prop: Any, path: str, parent_name: str, depth: int, max_depth: int) -> dict[str, Any]:
    name = prop.name if path else "<root>"
    m = meta_of(prop)
    node = {
        "name": name,
        "path": path,
        "type": m.get("type"),
        "children": [],
    }
    if isinstance(prop, WzSubProperty) and depth < max_depth:
        for ch in prop.children():
            cpath = (path + "/" + ch.name) if path else ch.name
            node["children"].append(build_nav_tree(ch, cpath, name, depth + 1, max_depth))
    return node


# --------------------------------------------------------------------------
# 分析
# --------------------------------------------------------------------------

def analyze(img_path: Path, mode: str, reference_path: Path | None = None) -> dict[str, Any]:
    image = load_client_image(img_path)
    nodes: list[dict] = []
    walk_flat(image.root, "", "", nodes, 0)
    verdicts = compat.post_analyze(nodes, mode)

    source_flat = [_node_for_api(v, mode) for v in verdicts]
    flat = source_flat
    comparison = None
    if reference_path is not None:
        reference = load_client_image(reference_path)
        reference_nodes: list[dict] = []
        walk_flat(reference.root, "", "", reference_nodes, 0)
        reference_verdicts = compat.post_analyze(reference_nodes, mode)
        reference_flat = [_node_for_api(v, mode) for v in reference_verdicts]
        flat, comparison = compare_nodes(source_flat, reference_flat)

    truncated = len(flat) > MAX_FLAT
    if truncated:
        flat = flat[:MAX_FLAT]

    # 导航树（深度受限）带 status
    verdict_by_path = {v["path"]: v["verdict"].status for v in verdicts}
    nav = _annotate_nav(build_nav_tree(image.root, "", "", 0, 6), verdict_by_path)

    summary = compat.summarize(verdicts)
    summary["canvases"] = sum(1 for n in nodes if n["type"] == "canvas")
    summary["truncated"] = truncated
    issue_counts = Counter(
        (v["verdict"].status, v["verdict"].reason)
        for v in verdicts if v["verdict"].status != "ok"
    )
    summary["issueGroups"] = [
        {"status": status, "reason": reason, "count": count}
        for (status, reason), count in issue_counts.most_common()
    ]

    actions = [a for v in verdicts for a in [_action_entry(v)] if a]
    result = {
        "ok": True,
        "mode": mode,
        "imgPath": rel_path(img_path),
        "rootName": image.root.name,
        "navTree": nav,
        "flat": flat,
        "summary": summary,
        "actions": actions,
        "hasReference": reference_path is not None,
        "referencePath": rel_path(reference_path) if reference_path is not None else "",
        "comparison": comparison,
    }
    update_result_modern_tags(result)
    update_texture_summary(result)
    return result


def _node_for_api(v: dict, mode: str) -> dict[str, Any]:
    node = dict(v)
    node["meaning"] = compat.node_meaning(v["name"], v["path"], node, mode)
    node["status"] = v["verdict"].status
    node["reason"] = v["verdict"].reason
    node["suggestion"] = v["verdict"].suggestion
    node.pop("verdict", None)
    return node


def _comparison_signature(node: dict[str, Any]) -> dict[str, Any]:
    ignored = {
        "depth", "meaning", "parent_name", "path", "name", "reason",
        "status", "suggestion", "modernTags", "sourceNode", "referenceNode", "compareStatus",
    }
    return {key: value for key, value in node.items() if key not in ignored}


def compare_nodes(source: list[dict[str, Any]], reference: list[dict[str, Any]]) -> tuple[list, dict]:
    """按完整节点路径比较迁移源与兼容底座，保留两侧完整详情。"""
    source_by_path = {node["path"]: node for node in source}
    reference_by_path = {node["path"]: node for node in reference}
    ordered_paths = [node["path"] for node in source]
    ordered_paths.extend(node["path"] for node in reference if node["path"] not in source_by_path)
    counts = {"same": 0, "changed": 0, "source_only": 0, "reference_only": 0}
    rows = []
    for path in ordered_paths:
        source_node = source_by_path.get(path)
        reference_node = reference_by_path.get(path)
        if source_node is None:
            compare_status = "reference_only"
        elif reference_node is None:
            compare_status = "source_only"
        elif _comparison_signature(source_node) == _comparison_signature(reference_node):
            compare_status = "same"
        else:
            compare_status = "changed"
        counts[compare_status] += 1
        display = dict(source_node or reference_node)
        display["sourceNode"] = source_node
        display["referenceNode"] = reference_node
        display["compareStatus"] = compare_status
        rows.append(display)
    return rows, {"total": len(rows), **counts}


def format_comparison_markdown(rows: list[dict[str, Any]], summary: dict[str, int]) -> str:
    labels = {"changed": "有变化", "source_only": "仅迁移源", "reference_only": "仅底座"}
    lines = [
        "## 与兼容底座的节点对照",
        "",
        "- 相同 %d　有变化 %d　仅迁移源 %d　仅底座 %d" % (
            summary["same"], summary["changed"], summary["source_only"], summary["reference_only"]),
        "",
        "| 对照 | 路径 | 迁移源详情 | 底座详情 |",
        "|---|---|---|---|",
    ]
    for row in rows:
        status = row.get("compareStatus")
        if status == "same":
            continue
        source = _comparison_signature(row["sourceNode"]) if row.get("sourceNode") else None
        reference = _comparison_signature(row["referenceNode"]) if row.get("referenceNode") else None
        source_text = json.dumps(source, ensure_ascii=False, sort_keys=True).replace("|", "\\|")
        reference_text = json.dumps(reference, ensure_ascii=False, sort_keys=True).replace("|", "\\|")
        lines.append("| %s | `%s` | `%s` | `%s` |" % (
            labels.get(status, status), row.get("path", ""), source_text, reference_text))
    lines.append("")
    return "\n".join(lines)


def _action_entry(v: dict) -> dict | None:
    act = compat.action_for(v["verdict"], v)
    if act is None:
        return None
    return {
        "path": v["path"],
        "name": v["name"],
        "type": v["type"],
        "status": v["verdict"].status,
        "op": act["op"],
        "value": act.get("value"),
        "reason": v["verdict"].reason,
        "suggestion": v["verdict"].suggestion,
    }


def _annotate_nav(node: dict, verdict_by_path: dict[str, str]) -> dict[str, Any]:
    node = dict(node)
    node["status"] = verdict_by_path.get(node["path"], "ok")
    node["children"] = [_annotate_nav(c, verdict_by_path) for c in node.get("children", [])]
    return node


# --------------------------------------------------------------------------
# 清洗（strip）
# --------------------------------------------------------------------------

def strip_incompatible(img_path: Path, xml_path: Path | None, include: set[str],
                       backup: bool, dry_run: bool, mode: str = "map") -> dict[str, Any]:
    if not dry_run:
        require_full_rewrite_enabled()
    image = load_client_image(img_path)
    nodes: list[dict] = []
    walk_flat(image.root, "", "", nodes, 0)
    verdicts = compat.post_analyze(nodes, mode)

    xml_tree = None
    if xml_path is not None and xml_path.exists():
        xml_tree = ET.parse(xml_path)

    applied = []
    skipped = []
    for v in verdicts:
        status = v["verdict"].status
        if status not in include:
            continue
        act = compat.action_for(v["verdict"], v)
        if act is None:
            skipped.append({"path": v["path"], "status": status, "note": "需人工处理"})
            continue
        path = v["path"]
        try:
            if act["op"] == "delete":
                removed = replace.delete_img_node(image.root, path)
                if removed and xml_tree is not None:
                    replace.delete_xml_node(xml_tree.getroot(), path)
                applied.append({"op": "delete", "path": path, "xml": xml_tree is not None and removed})
            elif act["op"] == "set_int":
                parent, name = replace.img_parent_and_name(image.root, path, create=False)
                replace.set_int_child(parent, name, str(act["value"]))
                if xml_tree is not None:
                    xml_parent, xml_name = _xml_parent_and_name(xml_tree.getroot(), path)
                    if xml_parent is not None:
                        from xml.etree.ElementTree import SubElement
                        node = None
                        for child in xml_parent:
                            if child.tag == "int" and child.get("name") == xml_name:
                                node = child
                                break
                        if node is None:
                            node = SubElement(xml_parent, "int", {"name": xml_name})
                        node.set("value", str(act["value"]))
                applied.append({"op": "set_int", "path": path, "value": act["value"]})
        except Exception as exc:
            skipped.append({"path": path, "status": status, "note": f"执行失败：{exc}"})

    if not dry_run and (applied or skipped):
        out = encode_image_body(image, image.wz_file.reader)
        replace.write_img(img_path, out, backup=backup)
        if xml_tree is not None:
            replace.write_xml(xml_path, xml_tree, backup=backup)

    return {
        "ok": True,
        "dryRun": dry_run,
        "applied": applied,
        "skipped": skipped,
        "imgPath": rel_path(img_path),
        "xmlPath": rel_path(xml_path) if xml_path else None,
    }


def _xml_parent_and_name(root: ET.Element, raw_path: str):
    parts = [p for p in raw_path.strip("/").split("/") if p]
    if not parts:
        return None, None
    parent = root
    for part in parts[:-1]:
        found = None
        for child in parent:
            if child.tag in ("imgdir", "canvas") and child.get("name") == part:
                found = child
                break
        if found is None:
            return None, None
        parent = found
    return parent, parts[-1]


# --------------------------------------------------------------------------
# 前端
# --------------------------------------------------------------------------

HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>地图 / Boss 迁移兼容性工作台</title>
  <style>
    :root {
      color-scheme: dark;
      --bg:#070a0f; --panel:#0e141d; --line:#263241; --ink:#e7edf5;
      --muted:#8fa0b5; --accent:#14b8a6; --warn:#eab308; --bad:#fb7185; --ok:#22c55e; --modern:#38bdf8;
    }
    * { box-sizing: border-box; }
    html, body { height:100%; }
    body { margin:0; display:grid; grid-template-rows:auto auto auto auto minmax(0,1fr) auto; font:13px/1.35 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); background:var(--bg); }
    header { display:flex; align-items:center; gap:14px; padding:8px 14px; background:#090d14; border-bottom:1px solid var(--line); }
    header strong { font-size:15px; }
    header .muted { margin-right:auto; }
    .topbar { display:grid; grid-template-columns:auto auto minmax(160px,1fr) minmax(200px,1fr) minmax(200px,1fr) auto; gap:8px; padding:10px 12px; background:#0a0f17; border-bottom:1px solid var(--line); align-items:end; }
    .summary { display:flex; gap:8px; flex-wrap:wrap; padding:8px 12px; background:#0a0f17; border-bottom:1px solid var(--line); align-items:center; }
    .chip { display:inline-flex; align-items:center; gap:6px; padding:3px 10px; border-radius:999px; font-size:12px; background:#17202c; color:var(--muted); }
    .chip b { color:var(--ink); }
    .chip.ok b { color:var(--ok); } .chip.modern b { color:var(--modern); }
    .chip.incompatible b { color:var(--bad); } .chip.review b { color:var(--warn); }
    main { min-height:0; display:grid; grid-template-columns:clamp(240px,20vw,300px) minmax(0,1fr) clamp(300px,26vw,380px); }
    section { min-height:0; padding:10px; border-right:1px solid var(--line); overflow:hidden; display:flex; flex-direction:column; gap:8px; }
    section:last-child { border-right:0; }
    label { display:block; margin:0 0 4px; color:var(--muted); font-size:11px; }
    input, select, button { font:inherit; }
    input, select { width:100%; height:30px; padding:5px 8px; border:1px solid var(--line); border-radius:6px; color:var(--ink); background:#0d1420; outline:none; }
    input:focus, select:focus { border-color:var(--accent); box-shadow:0 0 0 2px rgba(20,184,166,.14); }
    button { height:30px; border:1px solid var(--line); color:var(--ink); background:#101827; border-radius:6px; padding:0 10px; cursor:pointer; white-space:nowrap; }
    button.primary { background:var(--accent); color:#03110f; border-color:var(--accent); font-weight:600; }
    button.danger { background:#3a1620; border-color:#6b2230; color:#fda4af; }
    button:disabled { opacity:.55; cursor:not-allowed; }
    .seg { display:inline-flex; border:1px solid var(--line); border-radius:6px; overflow:hidden; }
    .seg button { border:0; border-radius:0; background:#101827; }
    .seg button.active { background:var(--accent); color:#03110f; font-weight:600; }
    .path-field { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:6px; }
    .ms-entries { min-height:0; overflow:auto; display:flex; align-content:flex-start; flex-wrap:wrap; gap:6px; padding:8px; background:var(--panel); border:1px solid var(--line); border-radius:6px; }
    .ms-entry { border:1px solid var(--line); background:#101827; color:var(--ink); border-radius:6px; padding:5px 9px; font-size:12px; cursor:pointer; max-width:280px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .ms-entry:hover { border-color:var(--accent); }
    .ms-entry.sel { background:var(--accent); color:#03110f; font-weight:600; }
    .panel-title { color:var(--muted); font-size:11px; display:flex; justify-content:space-between; gap:8px; align-items:center; }
    .tree { flex:1; min-height:0; background:var(--panel); border:1px solid var(--line); overflow:auto; padding:6px; border-radius:6px; }
    .tree-node { margin:1px 0; }
    .node-line { display:grid; grid-template-columns:14px minmax(0,1fr) auto; gap:6px; align-items:center; padding:3px 5px; border-radius:5px; cursor:pointer; }
    .node-line:hover, .node-line.sel { background:#172536; }
    .dot { width:8px; height:8px; border-radius:50%; background:#33414f; }
    .dot.ok { background:var(--ok); } .dot.modern { background:var(--modern); }
    .dot.incompatible { background:var(--bad); } .dot.review { background:var(--warn); }
    .node-name { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .type-pill { color:var(--muted); font-size:11px; }
    .children { margin-left:10px; border-left:1px solid #223044; padding-left:6px; }

    .toolbar { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
    .filters { display:inline-flex; gap:4px; }
    .filters button { padding:0 9px; font-size:12px; }
    .filters button.active { background:#172536; border-color:var(--accent); color:var(--accent); }
    .table-wrap { flex:1; min-height:0; overflow:auto; border:1px solid var(--line); border-radius:6px; background:var(--panel); }
    table { width:100%; border-collapse:collapse; }
    .audit-table { min-width:1080px; table-layout:fixed; }
    .audit-table col.compat-col { width:118px; }
    .audit-table col.compare-col { width:78px; }
    .audit-table col.modern-col { width:150px; }
    .audit-table col.path-col { width:180px; }
    .audit-table col.type-col { width:72px; }
    .audit-table col.reason-col, .audit-table col.suggestion-col { width:240px; }
    th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); vertical-align:top; }
    th { font-size:11px; color:var(--muted); background:#101722; position:sticky; top:0; z-index:1; cursor:pointer; }
    td { font-size:12px; }
    tr.row { cursor:pointer; }
    tr.row:hover, tr.row.sel { background:#162234; }
    .audit-table td { white-space:normal; overflow-wrap:anywhere; word-break:break-word; }
    .compat-stack { display:grid; gap:4px; }
    .compat-side { display:grid; grid-template-columns:22px minmax(0,1fr); gap:4px; align-items:center; }
    .side-key { color:var(--muted); font-size:10px; }
    .modern-stack { display:flex; flex-wrap:wrap; gap:4px; }
    .modern-tag { display:inline-block; max-width:100%; padding:2px 6px; border-radius:5px; font-size:10px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .modern-tag.node { color:#c4b5fd; background:rgba(139,92,246,.14); }
    .modern-tag.resource { color:var(--modern); background:rgba(56,189,248,.12); }
    code { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:11px; color:#dbeafe; word-break:break-all; }
    .badge { display:inline-block; min-width:46px; text-align:center; padding:1px 7px; border-radius:999px; font-size:11px; }
    .badge.ok { color:var(--ok); background:rgba(34,197,94,.12); }
    .badge.modern { color:var(--modern); background:rgba(56,189,248,.12); }
    .badge.incompatible { color:var(--bad); background:rgba(251,113,133,.13); }
    .badge.review { color:var(--warn); background:rgba(234,179,8,.13); }
    .badge.same { color:var(--ok); background:rgba(34,197,94,.12); }
    .badge.changed { color:var(--warn); background:rgba(234,179,8,.13); }
    .badge.source_only { color:var(--modern); background:rgba(56,189,248,.12); }
    .badge.reference_only { color:#c4b5fd; background:rgba(196,181,253,.13); }
    .details { flex:1; min-height:0; background:var(--panel); border:1px solid var(--line); padding:10px; border-radius:6px; overflow:auto; }
    .details h3 { margin:0 0 8px; font-size:13px; }
    .kv { display:grid; grid-template-columns:64px minmax(0,1fr); gap:5px 8px; margin:6px 0; }
    .kv div:nth-child(odd) { color:var(--muted); }
    .suggest { margin-top:8px; padding:8px; border:1px solid var(--line); border-radius:6px; background:#0c121b; }
    .preview-box { margin-top:8px; min-height:120px; border:1px solid var(--line); border-radius:6px; background:#0c121b; display:flex; align-items:center; justify-content:center; padding:6px; }
    .preview-box img { max-width:100%; height:auto; image-rendering:auto; background:repeating-conic-gradient(#182231 0 25%,#0f1722 0 50%) 50% / 18px 18px; }
    .preview-tools { display:flex; align-items:center; flex-wrap:wrap; gap:4px; margin-top:6px; }
    .preview-tools button { height:24px; padding:0 7px; font-size:11px; }
    .preview-tools button.active { border-color:var(--accent); color:var(--accent); }
    .texture-alert { color:var(--bad); font-weight:600; }
    .compare-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
    .side-card { min-width:0; padding:8px; border:1px solid var(--line); border-radius:6px; background:#0a1018; }
    .side-card h4 { margin:0 0 7px; color:var(--muted); }
    .side-card .preview-box { min-height:90px; }
    .ops { display:grid; gap:14px; }
    .ops-row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
    .ops-grid { display:grid; grid-template-columns:auto auto auto 1fr; gap:8px 12px; align-items:center; }
    .result { min-width:0; white-space:pre-wrap; color:var(--muted); font-size:12px; max-height:64px; overflow:auto; }
    .statusbar { min-height:42px; padding:6px 12px; background:#090d14; border-top:1px solid var(--line); display:grid; grid-template-columns:minmax(0,1fr) auto auto; gap:8px; align-items:center; }
    .modal { position:fixed; inset:0; display:none; align-items:center; justify-content:center; background:rgba(0,0,0,.62); z-index:20; }
    .modal.open { display:flex; }
    .dialog { width:min(900px,calc(100vw - 36px)); max-height:calc(100vh - 36px); display:grid; grid-template-rows:auto minmax(0,1fr); background:#0c121b; border:1px solid var(--line); border-radius:8px; overflow:hidden; box-shadow:0 24px 80px rgba(0,0,0,.45); }
    .dialog.wide { width:min(1220px,calc(100vw - 36px)); }
    .dialog-head { display:flex; align-items:center; gap:8px; padding:10px 12px; border-bottom:1px solid var(--line); }
    .dialog-head strong { margin-right:auto; }
    .dialog-body { min-height:0; overflow:auto; padding:12px; }
    .dialog-body .details { max-height:none; overflow:visible; }
    .ms-dialog-body { min-height:0; display:grid; grid-template-rows:auto minmax(0,1fr); gap:8px; padding:12px; }
    .picker { width:min(840px,calc(100vw - 40px)); height:min(620px,calc(100vh - 40px)); display:grid; grid-template-rows:auto auto minmax(0,1fr); background:#0c121b; border:1px solid var(--line); border-radius:8px; overflow:hidden; }
    .picker-head, .picker-path { display:flex; gap:8px; align-items:center; padding:10px; border-bottom:1px solid var(--line); }
    .picker-head strong { margin-right:auto; }
    .picker-list { overflow:auto; padding:6px; }
    .picker-row { width:100%; min-height:30px; display:grid; grid-template-columns:22px minmax(0,1fr) auto; gap:8px; align-items:center; text-align:left; margin:2px 0; border:0; background:transparent; color:var(--ink); }
    .picker-row:hover { background:#172536; }
    @media (max-width:1680px) {
      main { grid-template-columns:clamp(220px,20vw,280px) minmax(0,1fr); }
      main section:last-child { display:none; }
    }
    @media (max-width:1050px) {
      main { grid-template-columns:1fr; grid-template-rows:minmax(180px,34%) minmax(280px,1fr); }
      section { border-right:0; border-bottom:1px solid var(--line); }
      .topbar { grid-template-columns:auto 1fr 1fr; }
      .compare-grid { grid-template-columns:1fr; }
    }
    @media (max-width:700px) {
      .topbar { grid-template-columns:1fr; }
      .statusbar { grid-template-columns:minmax(0,1fr) auto auto; }
      header > .muted { display:none; }
    }
  </style>
</head>
<body>
  <header>
    <strong>地图 / Boss 迁移兼容性工作台</strong>
    <span class="muted">规则自检 · 节点含义 · 兼容清洗 · 报告</span>
    <span id="rootName" class="muted"></span>
  </header>

  <div class="topbar">
    <div class="field" style="display:flex;align-items:center;gap:8px;">
      <span class="muted" style="font-size:11px;">模式</span>
      <div class="seg" id="modeSeg">
        <button data-mode="map" class="active">地图</button>
        <button data-mode="boss">Boss</button>
      </div>
    </div>
    <div class="field" style="display:flex;align-items:center;gap:8px;">
      <span class="muted" style="font-size:11px;">数据源</span>
      <div class="seg" id="srcSeg">
        <button data-src="img" class="active">本地 / 散装 .img</button>
        <button data-src="ms">新客户端 .ms 包</button>
      </div>
    </div>
    <div class="field"><label>兼容底座 / 对照 .img</label><div class="path-field"><input id="refPath" placeholder="可空；用于逐节点对照" /><button data-pick="refPath" data-kind="reference">选择</button></div></div>
    <div class="actions"><button class="primary" id="loadBtn">读取分析</button></div>
  </div>

  <div class="topbar" id="imgPanel">
    <div class="field"><label id="idLabel">地图 ID</label><input id="itemId" placeholder="如 100000000 或 8880700" /></div>
    <div class="field"><label>来源 .img</label><div class="path-field"><input id="imgPath" /><button data-pick="imgPath" data-kind="img">选择</button></div></div>
    <div class="field"><label>服务端 .img.xml</label><div class="path-field"><input id="xmlPath" /><button data-pick="xmlPath" data-kind="xml">选择</button></div></div>
  </div>

  <div class="topbar" id="msPanel" style="display:none;">
    <div class="field"><label>新客户端 .ms 包</label><div class="path-field"><input id="msPack" placeholder="如 Mob_00001.ms 或绝对路径" /><button data-pick="msPack" data-kind="ms" data-init="msdir">选择</button></div></div>
    <div class="field"><label>当前条目</label><div class="path-field"><input id="msSelected" readonly placeholder="尚未选择" /><button id="msListBtn">选择条目</button></div></div>
    <span id="msStatus" class="muted"></span>
  </div>

  <div class="summary" id="summary"></div>

  <main>
    <section>
      <div class="panel-title"><span>节点树（导航）</span><span id="navHint" class="muted"></span></div>
      <div class="tree" id="navTree"></div>
    </section>

    <section>
      <div class="toolbar">
        <div class="filters" id="filters">
          <button data-f="all" class="active">全部</button>
          <button data-f="incompatible">不兼容</button>
          <button data-f="modern">现代</button>
          <button data-f="review">待审</button>
        </div>
        <div class="filters" id="compareFilters">
          <button data-c="all" class="active">全部对照</button>
          <button data-c="diff">仅差异</button>
          <button data-c="changed">值变化</button>
          <button data-c="source_only">仅迁移源</button>
          <button data-c="reference_only">仅底座</button>
        </div>
        <input id="search" placeholder="搜索路径/名称/含义…" style="flex:1;min-width:160px;" />
        <span id="rowCount" class="muted"></span>
      </div>
      <div class="table-wrap">
        <table class="audit-table">
          <colgroup><col class="compat-col"><col class="compare-col"><col class="modern-col"><col class="path-col"><col class="type-col"><col class="reason-col"><col class="suggestion-col"></colgroup>
          <thead><tr>
            <th data-sort="status">来源 / 底座兼容</th><th data-sort="compareStatus">对照</th><th>现代性</th><th data-sort="path">路径</th><th data-sort="type">类型</th>
            <th>含义 / 原因</th><th>建议</th>
          </tr></thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
    </section>

    <section>
      <div class="panel-title"><span>选中节点</span><span><span id="inspPath" class="muted"></span> <button id="detailInlineBtn" title="在弹窗中放大节点详情" style="height:24px;padding:0 7px;" disabled>放大</button></span></div>
      <div class="details" id="details"><div class="muted">在中间表格点击一个节点查看详情与预览。</div></div>
    </section>
  </main>

  <div class="statusbar">
    <div class="result" id="result"></div>
    <button id="detailPopBtn" disabled title="双击节点也可以打开">放大节点</button>
    <button id="opsOpenBtn">操作与报告</button>
  </div>

  <div class="modal" id="opsModal">
    <div class="dialog">
      <div class="dialog-head"><strong>操作与报告</strong><span class="muted">生产 IMG 写入默认关闭</span><button id="opsCloseBtn">关闭</button></div>
      <div class="dialog-body ops">
        <div class="ops-row">
          <strong style="font-size:12px;">兼容清洗预演</strong>
          <label style="display:inline-flex;gap:5px;align-items:center;color:var(--ink);"><input type="checkbox" id="incInc" checked style="width:auto;height:auto;" />不兼容</label>
          <label style="display:inline-flex;gap:5px;align-items:center;color:var(--ink);"><input type="checkbox" id="incMod" checked style="width:auto;height:auto;" />现代</label>
          <label style="display:inline-flex;gap:5px;align-items:center;color:var(--ink);"><input type="checkbox" id="incRev" style="width:auto;height:auto;" />待审</label>
          <label style="display:inline-flex;gap:5px;align-items:center;color:var(--ink);"><input type="checkbox" id="backup" checked style="width:auto;height:auto;" />备份</label>
          <label style="display:inline-flex;gap:5px;align-items:center;color:var(--ink);"><input type="checkbox" id="dryRun" checked style="width:auto;height:auto;" />预览(不写盘)</label>
          <button id="stripBtn" class="danger">执行清洗</button>
          <button id="deleteSelBtn" class="danger">删除选中</button>
        </div>
        <div class="ops-row">
          <strong style="font-size:12px;">报告</strong>
          <button id="mdBtn">导出 Markdown</button>
          <button id="jsonBtn">导出 JSON</button>
        </div>
        <div class="ops-row">
          <strong style="font-size:12px;">从底座复制节点</strong>
          <input id="copySource" placeholder="来源路径，如 info 或 0/obj/0" style="max-width:300px;" />
          <input id="copyTarget" placeholder="目标父路径，如 info 或 0/obj" style="max-width:300px;" />
          <button id="copySelBtn">复制/迁移</button>
        </div>
      </div>
    </div>
  </div>

  <div class="modal" id="detailModal">
    <div class="dialog wide">
      <div class="dialog-head"><strong>节点详情与预览</strong><span id="detailModalPath" class="muted"></span><button id="detailCloseBtn">关闭</button></div>
      <div class="dialog-body" id="detailModalBody"></div>
    </div>
  </div>

  <div class="modal" id="msEntryModal">
    <div class="dialog">
      <div class="dialog-head"><strong>选择 MS 条目</strong><span id="msModalStatus" class="muted"></span><button id="msEntryCloseBtn">关闭</button></div>
      <div class="ms-dialog-body">
        <input id="msSearch" placeholder="筛选条目，如 8880 或 Mob/888" />
        <div class="ms-entries" id="msEntries"><div class="muted">正在读取条目…</div></div>
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
    let state = { mode:"map", source:"img", imgPath:"", xmlPath:"", referencePath:"", flat:[], navTree:null, summary:null, comparison:null, selected:null, scope:null, filter:"all", compareFilter:"all", sortKey:null, sortDir:1, msPack:"", msEntry:"", fullRewriteEnabled:false };
    let pickerTarget = null, pickerKind = "img", pickerRoots = [], pickerInit = "";

    const $ = id => document.getElementById(id);
    const statusText = { ok:"兼容", modern:"现代", incompatible:"不兼容", review:"待审" };
    const compareText = { same:"相同", changed:"有变化", source_only:"仅迁移源", reference_only:"仅底座" };
    const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
    const fmt = v => (v && typeof v === 'object') ? JSON.stringify(v, null, 2) : String(v ?? '');
    const fmtBytes = value => {
      let n = Number(value||0), unit = 'B';
      if (n >= 1024*1024*1024){ n /= 1024*1024*1024; unit = 'GiB'; }
      else if (n >= 1024*1024){ n /= 1024*1024; unit = 'MiB'; }
      else if (n >= 1024){ n /= 1024; unit = 'KiB'; }
      return `${n >= 10 || unit==='B' ? n.toFixed(0) : n.toFixed(2)} ${unit}`;
    };

    function setTexturePreview(button, maxEdge){
      const card = button.closest('.side-card');
      const img = card && card.querySelector('.preview-box img');
      if (!img) return;
      const url = new URL(img.dataset.base, location.origin);
      if (maxEdge) url.searchParams.set('max_texture', maxEdge); else url.searchParams.delete('max_texture');
      img.src = url.pathname + url.search;
      card.querySelectorAll('.preview-tools button').forEach(x=>x.classList.toggle('active', x===button));
    }

    function texturePreviewLoaded(img){
      const label = img.closest('.side-card').querySelector('.preview-size');
      const memory = img.naturalWidth * img.naturalHeight * 2;
      if (label) label.textContent = `预览 ${img.naturalWidth}×${img.naturalHeight} · ARGB4444 ${fmtBytes(memory)}（不写盘）`;
    }

    function downloadTexturePreview(button){
      const img = button.closest('.side-card').querySelector('.preview-box img');
      if (!img || !img.naturalWidth) return;
      const a = document.createElement('a');
      a.href = img.src;
      const safePath = (img.dataset.path||'canvas').replace(/[^a-zA-Z0-9._-]+/g, '_');
      a.download = `${safePath}_${img.naturalWidth}x${img.naturalHeight}.png`;
      a.click();
    }

    function setMode(m){ state.mode = m; document.querySelectorAll('#modeSeg button').forEach(b=>b.classList.toggle('active', b.dataset.mode===m)); $('idLabel').textContent = m==="map" ? "地图 ID" : "Boss ID"; }

    function setSource(s){
      state.source = s;
      document.querySelectorAll('#srcSeg button').forEach(b=>b.classList.toggle('active', b.dataset.src===s));
      $('imgPanel').style.display = s==="img" ? "grid" : "none";
      $('msPanel').style.display = s==="ms" ? "grid" : "none";
      if (s==="ms") $('rootName').textContent = "";
      updateWriteButtons();
    }

    function updateWriteButtons(){
      $('deleteSelBtn').disabled = !state.fullRewriteEnabled;
      $('copySelBtn').disabled = !state.fullRewriteEnabled || state.source === 'ms';
    }

    async function loadData(){
      const mode = state.mode;
      $('result').textContent = "读取中…";
      try {
        let url;
        if (state.source === "ms"){
          if (!state.msPack || !state.msEntry){ $('result').textContent = "请先选择 .ms 包与条目"; return; }
          url = `/api/load?mode=${encodeURIComponent(mode)}&ms_pack=${encodeURIComponent(state.msPack)}&ms_entry=${encodeURIComponent(state.msEntry)}`;
          const ref = $('refPath').value.trim();
          if (ref) url += `&reference_img_path=${encodeURIComponent(ref)}`;
        } else {
          const itemId = $('itemId').value.trim();
          const img = $('imgPath').value.trim();
          const xml = $('xmlPath').value.trim();
          const ref = $('refPath').value.trim();
          url = `/api/load?mode=${encodeURIComponent(mode)}`;
          if (itemId) url += `&item_id=${encodeURIComponent(itemId)}`;
          if (img) url += `&img_path=${encodeURIComponent(img)}`;
          if (xml) url += `&xml_path=${encodeURIComponent(xml)}`;
          if (ref) url += `&reference_img_path=${encodeURIComponent(ref)}`;
        }
        const r = await fetch(url); const d = await r.json();
        if (!d.ok){ $('result').textContent = "错误：" + d.reason; return; }
        state.imgPath = d.imgPath; state.xmlPath = d.xmlPath || ""; state.referencePath = d.referencePath || "";
        state.canvasPath = d.canvasPath || d.msCanvasPath || "";
        state.flat = d.flat || []; state.navTree = d.navTree; state.summary = d.summary; state.comparison = d.comparison;
        if (d.referencePath) $('refPath').value = d.referencePath;
        if (!state.comparison){
          state.compareFilter = 'all';
          document.querySelectorAll('#compareFilters button').forEach(x=>x.classList.toggle('active', x.dataset.c==='all'));
        }
        if (state.source === "img"){ if ($('imgPath').value.trim()) $('imgPath').value = d.imgPath; if (d.xmlPath) $('xmlPath').value = d.xmlPath; }
        let tag = d.source === "ms" ? `【新客户端 .ms】${d.msPack} → ${d.msEntry}\n` : "";
        $('rootName').textContent = (d.source==="ms" ? "新客户端: " : "") + d.rootName;
        renderSummary(); renderNav(); renderRows();
        $('result').textContent = tag + `已分析 ${d.summary.total} 个节点，兼容 ${d.summary.ok} / 现代 ${d.summary.modern} / 不兼容 ${d.summary.incompatible} / 待审 ${d.summary.review}。`;
      } catch(e){ $('result').textContent = "请求失败：" + e; }
    }

    // 新客户端 .ms 包
    let CFG = { msAvailable:false, msPacksDir:"" };
    async function loadConfig(){
      try {
        const r = await fetch('/api/config'); const d = await r.json();
        if (d.ok){
          CFG = d; state.fullRewriteEnabled = !!d.fullRewriteEnabled;
          if (!d.msAvailable) $('msStatus').textContent = "MSProbe 不可用（缺 DLL/dotnet）";
          else if (!d.msImgDataAvailable) $('msStatus').textContent = "MS 元数据可读；现代 _Canvas 散 IMG 目录缺失，图片预览会受限";
          updateWriteButtons();
          if (!state.fullRewriteEnabled) $('result').textContent = "安全模式：整树 IMG 写入已关闭；分析、对照、预览与清洗预演可用。";
        }
      } catch(e){}
    }
    async function msList(){
      const pack = $('msPack').value.trim();
      if (!pack){ $('msStatus').textContent = "请先填写/选择 .ms 包"; return; }
      $('msStatus').textContent = "列出中…";
      $('msModalStatus').textContent = "读取中…";
      $('msEntries').innerHTML = '<div class="muted">正在读取条目…</div>';
      $('msEntryModal').classList.add('open');
      try {
        const r = await fetch(`/api/ms/list?pack=${encodeURIComponent(pack)}`);
        const d = await r.json();
        if (!d.ok){ $('msStatus').textContent = "错误：" + d.reason; $('msModalStatus').textContent = "读取失败"; return; }
        if (state.msPack !== pack){ state.msEntry = ""; $('msSelected').value = ""; }
        state.msPack = pack; state.msAll = d.entries;
        renderMsEntries();
        const groups = Object.entries(d.groups||{}).map(([k,v])=>`${k} ${v}`).join(' / ');
        $('msStatus').textContent = `共 ${d.count} 个条目${groups?' · '+groups:''}`;
      } catch(e){ $('msStatus').textContent = "请求失败：" + e; $('msModalStatus').textContent = "读取失败"; }
    }
    function renderMsEntries(){
      const box = $('msEntries'); box.innerHTML = "";
      const q = $('msSearch').value.trim().toLowerCase();
      const list = (state.msAll || []).filter(e => !q || e.toLowerCase().includes(q));
      const limit = q ? 500 : 100;
      const shown = Math.min(list.length, limit);
      $('msModalStatus').textContent = q
        ? `匹配 ${list.length} / ${(state.msAll||[]).length}，显示 ${shown}`
        : `共 ${list.length} 个，先显示 ${shown}；输入关键词可筛选`;
      if (!list.length){ box.innerHTML = '<div class="muted">无匹配条目</div>'; return; }
      list.slice(0, limit).forEach(e => {
        const b = document.createElement('button');
        b.className = 'ms-entry' + (e === state.msEntry ? ' sel' : '');
        b.textContent = e;
        b.title = e;
        b.onclick = () => {
          state.msEntry = e;
          $('msSelected').value = e;
          const head = e.split('/', 1)[0].toLowerCase();
          if (head === 'map') setMode('map'); else if (head === 'mob') setMode('boss');
          document.querySelectorAll('.ms-entry').forEach(x=>x.classList.remove('sel'));
          b.classList.add('sel');
          $('msEntryModal').classList.remove('open');
          loadData();
        };
        box.appendChild(b);
      });
    }

    function renderSummary(){
      const s = state.summary; if(!s) return;
      const tx = s.textures || {};
      const issueTip = (s.issueGroups||[]).slice(0,12).map(x=>`${statusText[x.status]||x.status} ×${x.count}：${x.reason}`).join('\n');
      const textureTip = tx.count ? `实际纹理 ${tx.count}\n尺寸超限 ${tx.overLimit}\n格式不兼容 ${tx.formatIssues}\n最大 ${tx.maxWidth}×${tx.maxHeight}\n压缩载荷 ${fmtBytes(tx.payloadBytes)}\nARGB4444 理论 ${fmtBytes(tx.argb4444Bytes)}\nRGBA 解码 ${fmtBytes(tx.rgbaBytes)}\nPOT 保守估算 ${fmtBytes(tx.potArgb4444Bytes)}\n最大纹理：${tx.largestPath}` : '';
      $('summary').innerHTML =
        `<span class="chip"><b>${s.total}</b> 节点</span>` +
        `<span class="chip ok"><b>${s.ok}</b> 兼容</span>` +
        `<span class="chip modern"><b>${s.modern}</b> 现代</span>` +
        `<span class="chip incompatible"><b>${s.incompatible}</b> 不兼容</span>` +
        `<span class="chip review"><b>${s.review}</b> 待审</span>` +
        `<span class="chip"><b>${s.canvases}</b> canvas</span>` +
        (tx.count ? `<span class="chip ${(tx.overLimit||tx.formatIssues)?'incompatible':'ok'}" title="${esc(textureTip)}"><b>${tx.overLimit}</b> 尺寸超限 / <b>${tx.formatIssues}</b> 格式不兼容 · ${fmtBytes(tx.argb4444Bytes)}</span>` : ``) +
        (issueTip ? `<span class="chip" title="${esc(issueTip)}">悬浮查看规则汇总</span>` : ``) +
        (state.comparison ? `<span class="chip"><b>${state.comparison.changed + state.comparison.source_only + state.comparison.reference_only}</b> 对照差异</span>` : ``) +
        (s.truncated ? `<span class="chip">已截断</span>` : ``);
    }

    function renderNav(){
      const t = state.navTree; if(!t) return;
      $('navTree').innerHTML = "";
      const root = document.createElement('div');
      root.appendChild(navNode(t, 0));
      $('navTree').appendChild(root);
    }
    function navNode(n, depth){
      const wrap = document.createElement('div'); wrap.className='tree-node';
      const line = document.createElement('div'); line.className='node-line';
      const dot = document.createElement('span'); dot.className='dot '+(n.status||'ok');
      const name = document.createElement('span'); name.className='node-name'; name.textContent = n.name + (n.type==='imgdir' ? '/' : '');
      const tp = document.createElement('span'); tp.className='type-pill'; tp.textContent = n.type==='imgdir' ? `${n.children.length}` : n.type;
      line.title = (n.path || '<root>') + ' · 点击限定表格范围';
      line.append(dot, name, tp);
      line.onclick = () => { state.scope = n.path || null; renderRows(); document.querySelectorAll('.node-line').forEach(x=>x.classList.remove('sel')); line.classList.add('sel'); };
      wrap.appendChild(line);
      if (n.children && n.children.length){
        const ch = document.createElement('div'); ch.className='children';
        n.children.forEach(c => ch.appendChild(navNode(c, depth+1)));
        wrap.appendChild(ch);
      }
      return wrap;
    }

    function filtered(){
      let rows = state.flat;
      if (state.filter === 'modern') rows = rows.filter(r => {
        const source = r.sourceNode === undefined ? r : r.sourceNode;
        const reference = r.referenceNode === undefined ? null : r.referenceNode;
        return r.status === 'modern' || [source, reference].some(node => node && (node.modernTags||[]).length);
      });
      else if (state.filter !== 'all') rows = rows.filter(r => r.status === state.filter);
      if (state.compareFilter === 'diff') rows = rows.filter(r => r.compareStatus && r.compareStatus !== 'same');
      else if (state.compareFilter !== 'all') rows = rows.filter(r => r.compareStatus === state.compareFilter);
      if (state.scope) rows = rows.filter(r => (r.path === state.scope) || r.path.startsWith(state.scope + "/"));
      const q = $('search').value.trim().toLowerCase();
      if (q) rows = rows.filter(r => {
        const source = r.sourceNode === undefined ? r : r.sourceNode;
        const reference = r.referenceNode === undefined ? null : r.referenceNode;
        const modern = [source, reference].flatMap(node => node ? (node.modernTags||[]).map(tag=>tag.label+' '+tag.path) : []).join(' ');
        return (r.path+' '+r.name+' '+(r.meaning||'')+' '+(r.type||'')+' '+modern).toLowerCase().includes(q);
      });
      if (state.sortKey){ rows = rows.slice().sort((a,b)=>{ const x=a[state.sortKey]||'', y=b[state.sortKey]||''; return (x<y?-1:x>y?1:0)*state.sortDir; }); }
      return rows;
    }

    function compatibilityCell(r){
      const source = r.sourceNode === undefined ? r : r.sourceNode;
      const reference = r.referenceNode === undefined ? null : r.referenceNode;
      const line = (key, node) => node
        ? `<div class="compat-side"><span class="side-key">${key}</span><span class="badge ${node.status}" title="${esc(node.reason||node.meaning||'')}">${statusText[node.status]||node.status}</span></div>`
        : `<div class="compat-side"><span class="side-key">${key}</span><span class="muted">—</span></div>`;
      return `<div class="compat-stack">${line('源', source)}${r.compareStatus ? line('底', reference) : ''}</div>`;
    }

    function modernityCell(r){
      const source = r.sourceNode === undefined ? r : r.sourceNode;
      const reference = r.referenceNode === undefined ? null : r.referenceNode;
      const items = [];
      const add = (side, node) => (node && node.modernTags||[]).forEach(tag => {
        const kind = tag.kind === 'node' ? '节点' : '资源';
        items.push(`<span class="modern-tag ${tag.kind}" title="${esc(side+'现代'+kind+'：'+tag.path)}">${esc(side+'·'+kind+' '+tag.label)}</span>`);
      });
      add(r.compareStatus ? '源' : '', source);
      if (r.compareStatus) add('底', reference);
      return items.length ? `<div class="modern-stack">${items.join('')}</div>` : '<span class="muted">未标现代</span>';
    }

    function renderRows(){
      const rows = filtered();
      const body = $('rows'); body.innerHTML = "";
      const limit = Math.min(rows.length, 800);
      for (let i=0;i<limit;i++){
        const r = rows[i];
        const tr = document.createElement('tr'); tr.className='row';
        const comparison = r.compareStatus ? `<span class="badge ${r.compareStatus}">${compareText[r.compareStatus]||r.compareStatus}</span>` : '<span class="muted">—</span>';
        const reason = (r.status==='ok') ? (r.meaning||'') : (r.reason||'');
        tr.title = '单击查看；双击弹窗放大详情';
        tr.innerHTML = `<td>${compatibilityCell(r)}</td><td>${comparison}</td><td>${modernityCell(r)}</td><td><code>${esc(r.path||r.name)}</code></td><td>${esc(r.type)}</td><td class="reason-cell">${esc(reason)}</td><td class="suggestion-cell">${esc(r.suggestion||'')}</td>`;
        tr.onclick = () => selectRow(r, tr);
        tr.ondblclick = () => { selectRow(r, tr); openDetailModal(); };
        body.appendChild(tr);
      }
      $('rowCount').textContent = `显示 ${limit} / ${rows.length}`;
    }

    function nodeSide(title, node, imgPath, canvasExtra){
      if (!node) return `<div class="side-card"><h4>${title}</h4><div class="muted">此侧不存在该节点。</div></div>`;
      let html = `<div class="side-card"><h4>${title}</h4>`;
      if (node.type === 'canvas' && imgPath){
        const previewUrl = `/api/canvas.png?img_path=${encodeURIComponent(imgPath)}&path=${encodeURIComponent(node.path)}${canvasExtra||''}`;
        html += `<div class="preview-box"><img src="${esc(previewUrl)}" data-base="${esc(previewUrl)}" data-path="${esc(node.path)}" alt="preview" onload="texturePreviewLoaded(this)" onerror="this.parentNode.textContent='无法解码该 canvas'"/></div>`;
        html += `<div class="preview-tools"><span class="preview-size muted">读取预览…</span><button class="active" onclick="setTexturePreview(this,0)">原图</button><button onclick="setTexturePreview(this,2048)">≤2048</button><button onclick="setTexturePreview(this,1024)">≤1024</button><button onclick="setTexturePreview(this,512)">≤512</button><button onclick="downloadTexturePreview(this)">下载当前 PNG</button></div>`;
      }
      html += `<div class="kv">`;
      html += `<div>路径</div><div><code>${esc(node.path||node.name)}</code></div>`;
      html += `<div>类型</div><div>${esc(node.type)}</div>`;
      html += `<div>现代性</div><div>${modernityCell(node)}</div>`;
      if (node.value !== undefined && node.value !== null) html += `<div>取值</div><div><code>${esc(fmt(node.value))}</code></div>`;
      if (node.children !== undefined) html += `<div>子节点</div><div>${esc(node.children)}</div>`;
      if (node.type === 'canvas'){
        const resolved = node.resolvedCanvas;
        const effective = resolved || node;
        const texture = effective.texture || {};
        html += `<div>${resolved?'占位尺寸':'尺寸'}</div><div>${node.width||0}×${node.height||0}</div>`;
        html += `<div>${resolved?'占位格式':'格式'}</div><div>${esc(node.format)} / ${esc(node.format2)}</div>`;
        html += `<div>原点</div><div><code>${esc(fmt(node.origin))}</code></div>`;
        html += `<div>子整数</div><div><code>${esc(fmt(node.ints||{}))}</code></div>`;
        html += `<div>${resolved?'占位摘要':'像素摘要'}</div><div><code>${esc(node.pixelSha256||'无像素')}</code></div>`;
        if (resolved){
          html += `<div>真实像素</div><div>${resolved.width||0}×${resolved.height||0}</div>`;
          html += `<div>真实格式</div><div>${esc(resolved.format)} / ${esc(resolved.format2)}</div>`;
          html += `<div>像素来源</div><div><code>${esc(resolved.entry)} / ${esc(resolved.path)}</code></div>`;
          html += `<div>真实摘要</div><div><code>${esc(resolved.pixelSha256||'无像素')}</code></div>`;
          html += `<div>真实兼容</div><div><span class="badge ${resolved.status}" title="${esc(resolved.reason||'')}">${statusText[resolved.status]||resolved.status}</span></div>`;
        }
        html += `<div>纹理像素</div><div>${Number(texture.pixelCount||0).toLocaleString()}</div>`;
        html += `<div>压缩载荷</div><div>${fmtBytes(texture.payloadBytes)}</div>`;
        html += `<div>ARGB4444</div><div>${fmtBytes(texture.argb4444Bytes)}（2 B/px）</div>`;
        html += `<div>RGBA 解码</div><div>${fmtBytes(texture.rgbaBytes)}（4 B/px）</div>`;
        html += `<div>POT 估算</div><div>${texture.potWidth||0}×${texture.potHeight||0} · ${fmtBytes(texture.potArgb4444Bytes)}</div>`;
        if (texture.overLimit){
          html += `<div>单边上限</div><div class="texture-alert">超过 ${texture.edgeLimit}，必须降级</div>`;
          html += `<div>降级建议</div><div><b>${texture.suggestedWidth}×${texture.suggestedHeight}</b> · ${(Number(texture.scale||0)*100).toFixed(1)}%</div>`;
          if (texture.suggestedOrigin) html += `<div>新原点</div><div><code>${esc(fmt(texture.suggestedOrigin))}</code></div>`;
        } else {
          html += `<div>单边上限</div><div><span class="badge ok">未超 ${texture.edgeLimit||2048}</span></div>`;
        }
      }
      html += `<div>兼容</div><div><span class="badge ${node.status}">${statusText[node.status]||node.status}</span></div></div>`;
      html += `<div class="suggest"><b>含义：</b>${esc(node.meaning||'')}`;
      if (node.status !== 'ok') html += `<br><b>原因：</b>${esc(node.reason||'')}<br><b>建议：</b>${esc(node.suggestion||'')}`;
      if (node.type === 'canvas') html += `<br><b>降纹理：</b>按钮仅生成缩放预览。正式迁移时需用 Lanczos 等比缩放像素，并按横纵比例同步调整 origin、lt/rb/head 等 Vector；delay 不变。`;
      html += `</div>`;
      return html + `</div>`;
    }

    async function selectRow(r, tr){
      state.selected = r;
      document.querySelectorAll('tr.row').forEach(x=>x.classList.remove('sel')); tr.classList.add('sel');
      $('inspPath').textContent = r.path || r.name;
      $('detailPopBtn').disabled = false; $('detailInlineBtn').disabled = false;
      if (state.source === "ms" && r.sourceNode){ $('copySource').value = r.path || r.name; }
      const sourceNode = r.sourceNode === undefined ? r : r.sourceNode;
      const referenceNode = r.referenceNode === undefined ? null : r.referenceNode;
      const cextra = state.canvasPath ? `&canvas_img_path=${encodeURIComponent(state.canvasPath)}` : '';
      let html = `<h3>${esc(r.name)}</h3>`;
      if (r.compareStatus) html += `<div class="suggest"><b>对照结论：</b><span class="badge ${r.compareStatus}">${compareText[r.compareStatus]}</span></div>`;
      html += `<div class="compare-grid">${nodeSide('迁移源 / 当前文件', sourceNode, state.imgPath, cextra)}${nodeSide('兼容底座 / 对照文件', referenceNode, state.referencePath, '')}</div>`;
      if (state.source === "ms"){
        html += `<div class="suggest">当前为「新客户端 .ms」来源。现阶段可完成结构审查、与兼容底座逐节点对照及双方预览；写入旧客户端尚未接入安全的增量记录生成器。</div>`;
      }
      $('details').innerHTML = html;
      $('detailModalPath').textContent = r.path || r.name;
      $('detailModalBody').innerHTML = html;
    }

    function openDetailModal(){
      if (!state.selected){ $('result').textContent='请先选中一个节点'; return; }
      $('detailModal').classList.add('open');
    }

    // 清洗
    async function doStrip(){
      const include = [];
      if ($('incInc').checked) include.push('incompatible');
      if ($('incMod').checked) include.push('modern');
      if ($('incRev').checked) include.push('review');
      if (!$('dryRun').checked && !state.fullRewriteEnabled){ $('result').textContent='安全模式禁止整树 IMG 写入；请保持“预览(不写盘)”勾选。'; return; }
      const body = { mode:state.mode, img_path:state.imgPath, xml_path:state.xmlPath, include, backup:$('backup').checked, dry_run:$('dryRun').checked };
      $('result').textContent = "清洗中…";
      try {
        const r = await fetch('/api/strip', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
        const d = await r.json();
        if (!d.ok){ $('result').textContent = "错误：" + d.reason; return; }
        const a = d.applied||[], sk = d.skipped||[];
        let msg = `${d.dryRun?'[预览] ':'[已执行] '}处理 ${a.length} 项，跳过 ${sk.length} 项。\n`;
        a.slice(0,40).forEach(x=> msg += `  ${x.op} ${x.path}${x.value!==undefined?' -> '+x.value:''}\n`);
        sk.slice(0,10).forEach(x=> msg += `  跳过 ${x.path} (${x.note})\n`);
        $('result').textContent = msg;
        if (!d.dryRun) loadData();
      } catch(e){ $('result').textContent = "请求失败：" + e; }
    }

    async function deleteSelected(){
      if (!state.selected){ $('result').textContent='请先选中一个节点'; return; }
      if (state.selected.sourceNode === null){ $('result').textContent='该节点仅存在于对照底座，不能从当前文件删除。'; return; }
      const body = { img_path:state.imgPath, xml_path:state.xmlPath, path:state.selected.path, backup:$('backup').checked, dry_run:false };
      const r = await fetch('/api/delete_node', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
      const d = await r.json();
      $('result').textContent = d.ok ? `已删除 ${d.path}（clientRemoved=${d.clientRemoved}, xmlRemoved=${d.xmlRemoved}）` : "错误：" + d.reason;
      if (d.ok) loadData();
    }

    async function exportReport(fmt){
      const body = { mode:state.mode, img_path:state.imgPath, xml_path:state.xmlPath, reference_img_path:state.referencePath, canvas_img_path:state.canvasPath||'', format:fmt };
      const r = await fetch('/api/report', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
      const d = await r.json();
      if (!d.ok){ $('result').textContent = "错误：" + d.reason; return; }
      const blob = new Blob([d.report], { type: fmt==='json' ? 'application/json' : 'text/markdown' });
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
      a.download = `${state.mode}_${state.rootName||'report'}.${fmt==='json'?'json':'md'}`; a.click();
      $('result').textContent = `已导出 ${fmt} 报告。`;
    }

    async function copySelected(){
      if (state.source === 'ms'){ $('result').textContent='新客户端 .ms 到旧客户端的安全写入尚未接入，当前只能对照与预览。'; return; }
      const source = $('copySource').value.trim();
      const target = $('copyTarget').value.trim();
      if (!source || !target){ $('result').textContent='请填写来源路径与目标路径'; return; }
      const sourceImg = state.source === "ms" ? state.imgPath : $('refPath').value.trim();
      const body = { img_path:state.imgPath, xml_path:state.xmlPath, source_img_path:sourceImg,
                     source_path:source, parent_path:target, backup:$('backup').checked, dry_run:false };
      const r = await fetch('/api/copy_node', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
      const d = await r.json();
      $('result').textContent = d.ok ? `已${state.source==="ms"?"从新客户端迁移":"复制"} ${d.sourcePath} -> ${d.path}` : "错误：" + d.reason;
      if (d.ok && state.source !== "ms") loadData();
    }

    // 文件选择器
    async function openPicker(target, kind, initial){
      pickerTarget = target; pickerKind = kind; pickerRoots = [{name:'项目',path:''},{name:'用户目录',path:String(await homeDir())}];
      await browsePicker(initial || '');
      $('pickerModal').classList.add('open');
    }
    async function homeDir(){ try { const r = await fetch('/api/browse?kind=img&path='); const d=await r.json(); return (d.roots&&d.roots[1]&&d.roots[1].path)||''; } catch(e){ return ''; } }
    async function browsePicker(path){
      const r = await fetch(`/api/browse?kind=${pickerKind}&path=${encodeURIComponent(path)}`);
      const d = await r.json();
      $('pickerPath').value = d.path || '';
      const list = $('pickerList'); list.innerHTML='';
      (d.dirs||[]).forEach(dir=>{
        const row = document.createElement('button'); row.className='picker-row';
        row.innerHTML = `<span>📁</span><span class="name">${esc(dir.name)}/</span><span></span>`;
        row.onclick = () => browsePicker(dir.path);
        list.appendChild(row);
      });
      (d.files||[]).forEach(f=>{
        const row = document.createElement('button'); row.className='picker-row';
        row.innerHTML = `<span>📄</span><span class="name">${esc(f.name)}</span><span class="size">${(f.size/1024).toFixed(1)}K</span>`;
        row.onclick = () => {
          $(pickerTarget).value = f.path;
          $('pickerModal').classList.remove('open');
          if (pickerTarget === 'msPack'){
            state.msPack = ""; state.msEntry = ""; state.msAll = [];
            $('msSelected').value = ""; $('msStatus').textContent = "已选择，点击「选择条目」";
          }
        };
        list.appendChild(row);
      });
    }

    // 事件绑定
    document.querySelectorAll('#modeSeg button').forEach(b=> b.onclick = () => setMode(b.dataset.mode));
    document.querySelectorAll('#srcSeg button').forEach(b=> b.onclick = () => setSource(b.dataset.src));
    $('loadBtn').onclick = loadData;
    document.querySelectorAll('[data-pick]').forEach(b => b.onclick = () => openPicker(b.dataset.pick, b.dataset.kind, b.dataset.init==="msdir" ? CFG.msPacksDir : ''));
    document.querySelectorAll('#filters button').forEach(b => b.onclick = () => { state.filter=b.dataset.f; document.querySelectorAll('#filters button').forEach(x=>x.classList.remove('active')); b.classList.add('active'); renderRows(); });
    document.querySelectorAll('#compareFilters button').forEach(b => b.onclick = () => { state.compareFilter=b.dataset.c; document.querySelectorAll('#compareFilters button').forEach(x=>x.classList.remove('active')); b.classList.add('active'); renderRows(); });
    $('search').oninput = renderRows;
    $('msSearch').oninput = renderMsEntries;
    $('msListBtn').onclick = msList;
    document.querySelectorAll('th[data-sort]').forEach(th => th.onclick = () => { const k=th.dataset.sort; if(state.sortKey===k) state.sortDir*=-1; else {state.sortKey=k; state.sortDir=1;} renderRows(); });
    $('stripBtn').onclick = doStrip;
    $('deleteSelBtn').onclick = deleteSelected;
    $('mdBtn').onclick = () => exportReport('markdown');
    $('jsonBtn').onclick = () => exportReport('json');
    $('copySelBtn').onclick = copySelected;
    $('opsOpenBtn').onclick = () => $('opsModal').classList.add('open');
    $('opsCloseBtn').onclick = () => $('opsModal').classList.remove('open');
    $('detailPopBtn').onclick = openDetailModal;
    $('detailInlineBtn').onclick = openDetailModal;
    $('detailCloseBtn').onclick = () => $('detailModal').classList.remove('open');
    $('msEntryCloseBtn').onclick = () => $('msEntryModal').classList.remove('open');
    $('pickerCloseBtn').onclick = () => $('pickerModal').classList.remove('open');
    $('pickerUpBtn').onclick = () => { const p=$('pickerPath').value; const i=p.lastIndexOf('/'); browsePicker(i>0?p.slice(0,i):''); };
    $('pickerGoBtn').onclick = () => browsePicker($('pickerPath').value);
    $('pickerProjectBtn').onclick = () => browsePicker('');
    $('pickerHomeBtn').onclick = async () => browsePicker(await homeDir());
    document.querySelectorAll('.modal').forEach(modal => modal.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('open'); }));
    document.addEventListener('keydown', e => { if (e.key === 'Escape') document.querySelectorAll('.modal.open').forEach(x=>x.classList.remove('open')); });

    loadConfig();
    setSource('img');
    setMode('map');
  </script>
</body>
</html>"""

@app.get("/")
def index():
    return HTML


@app.get("/api/load")
def api_load():
    mode = request.args.get("mode", "map").strip() or "map"
    item_id = request.args.get("item_id", "").strip()
    img_raw = request.args.get("img_path", "").strip()
    xml_raw = request.args.get("xml_path", "").strip()
    ref_raw = request.args.get("reference_img_path", "").strip()

    # 新客户端 .ms 包：提取指定条目后再分析
    ms_pack = request.args.get("ms_pack", "").strip()
    ms_entry = request.args.get("ms_entry", "").strip()
    if ms_pack and ms_entry:
        pack_path = Path(ms_pack).expanduser()
        if not pack_path.exists():
            return jsonify({"ok": False, "reason": f"找不到 .ms 包：{ms_pack}"}), 404
        try:
            extracted = ms_extract_entry(pack_path, ms_entry)
        except Exception as exc:
            return jsonify({"ok": False, "reason": f"MSProbe 提取失败：{exc}"}), 400
        reference_path = root_path(ref_raw) if ref_raw else None
        if reference_path is not None and not reference_path.is_file():
            return jsonify({"ok": False, "reason": f"找不到对照 .img：{rel_path(reference_path)}"}), 404
        # 新客户端贴图在独立 _Canvas 条目，提取以备预览解析 _outlink
        canvas_entry_path = ""
        try:
            ce_name = ms_canvas_entry_name(ms_entry)
            if ce_name:
                located = ms_locate_entry(MSPACKS_DIR, ce_name)
                canvas_entry_path = str(located) if located else ""
        except Exception:
            canvas_entry_path = ""
        try:
            result = analyze(extracted, mode, reference_path)
            result["source"] = "ms"
            result["msPack"] = str(pack_path)
            result["msEntry"] = ms_entry
            result["imgPath"] = str(extracted)
            result["msCanvasPath"] = canvas_entry_path
            result["canvasPath"] = canvas_entry_path
            result["resolvedCanvases"] = annotate_resolved_canvases(
                result,
                extracted,
                Path(canvas_entry_path) if canvas_entry_path else None,
                mode,
            )
            result["xmlPath"] = ""
            return jsonify(result)
        except Exception as exc:
            return jsonify({"ok": False, "reason": str(exc)}), 400

    img_path = root_path(img_raw) if img_raw else default_client_img(mode, item_id)
    xml_path = root_path(xml_raw) if xml_raw else default_server_xml(mode, item_id)
    reference_path = root_path(ref_raw) if ref_raw else None

    if not img_path.exists():
        return jsonify({"ok": False, "reason": f"找不到客户端 .img：{rel_path(img_path)}"}), 404
    if reference_path is not None and not reference_path.is_file():
        return jsonify({"ok": False, "reason": f"找不到对照 .img：{rel_path(reference_path)}"}), 404
    try:
        result = analyze(img_path, mode, reference_path)
        result["source"] = "img"
        canvas_path = loose_canvas_path(img_path)
        result["canvasPath"] = str(canvas_path) if canvas_path else ""
        result["resolvedCanvases"] = annotate_resolved_canvases(
            result, img_path, canvas_path, mode,
        ) if canvas_path else 0
        result["xmlPath"] = rel_path(xml_path) if xml_path.exists() else ""
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 400


@app.get("/api/config")
def api_config():
    return jsonify({
        "ok": True,
        "msAvailable": ms_available(),
        "msPacksDir": str(MSPACKS_DIR),
        "msImgDataDir": str(MS_IMG_DATA_DIR),
        "msImgDataAvailable": MS_IMG_DATA_DIR.is_dir(),
        "msProbeDll": str(MSPROBE_DLL),
        "dotnet": DOTNET_BIN,
        "fullRewriteEnabled": full_rewrite_enabled(),
        "fullRewriteEnv": FULL_REWRITE_ENV,
    })


@app.get("/api/ms/list")
def api_ms_list():
    pack = request.args.get("pack", "").strip()
    if not pack:
        return jsonify({"ok": False, "reason": "缺少 pack 参数"}), 400
    pack_path = Path(pack).expanduser()
    if not pack_path.exists():
        return jsonify({"ok": False, "reason": f"找不到 .ms 包：{pack}"}), 404
    if not ms_available():
        return jsonify({"ok": False, "reason": "MSProbe 不可用（缺少 DLL 或 dotnet）"}), 500
    try:
        entries = ms_list_entries(pack_path)
        groups = Counter(entry.split("/", 1)[0] for entry in entries)
        return jsonify({
            "ok": True,
            "pack": str(pack_path),
            "count": len(entries),
            "entries": entries,
            "groups": dict(groups),
        })
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
    canvas_img_raw = request.args.get("canvas_img_path", "").strip()
    max_texture_raw = request.args.get("max_texture", "").strip()
    try:
        max_texture = int(max_texture_raw) if max_texture_raw else 0
        if max_texture and not 16 <= max_texture <= TEXTURE_EDGE_LIMIT:
            return jsonify({"ok": False, "reason": "max_texture 必须在 16..2048"}), 400
        image = load_client_image(img_path)
        prop = image.root.get(canvas_path)
        if not isinstance(prop, WzCanvasProperty):
            return jsonify({"ok": False, "reason": "target is not a client Canvas"}), 404
        region = getattr(image, "_region", None) or "GMS"
        target = prop
        # 新客户端：主条目里是 1x1 占位 + _outlink，到 _Canvas 条目取真实像素
        if not prop.has_pixels() or int(prop.width) <= 1 or int(prop.height) <= 1:
            resolved = resolve_outlink_canvas(prop, region, root_path(canvas_img_raw) if canvas_img_raw else None)
            if resolved is not None:
                target = resolved
        png = decode_canvas(target, region=region)
        original_size = png.size
        if max_texture and (png.width > max_texture or png.height > max_texture):
            png.thumbnail((max_texture, max_texture), PILImage.Resampling.LANCZOS)
        buf = io.BytesIO()
        png.save(buf, format="PNG")
        buf.seek(0)
        response = send_file(buf, mimetype="image/png")
        response.headers["X-Canvas-Original-Size"] = "%sx%s" % original_size
        response.headers["X-Canvas-Preview-Size"] = "%sx%s" % png.size
        response.headers["X-Canvas-Preview-Only"] = "1"
        return response
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 400


@app.post("/api/strip")
def api_strip():
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "map").strip() or "map"
    img_path = root_path(body.get("img_path", ""))
    xml_raw = body.get("xml_path", "").strip()
    xml_path = root_path(xml_raw) if xml_raw else None
    include = set(body.get("include", ["incompatible", "modern"]))
    backup = bool(body.get("backup", True))
    dry_run = bool(body.get("dry_run", False))
    if not img_path.exists():
        return jsonify({"ok": False, "reason": "img_path 不存在"}), 400
    try:
        return jsonify(strip_incompatible(img_path, xml_path, include, backup, dry_run, mode))
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 400


@app.post("/api/copy_node")
def api_copy_node():
    body = request.get_json(silent=True) or {}
    img_path = root_path(body.get("img_path", ""))
    xml_raw = body.get("xml_path", "").strip()
    xml_path = root_path(xml_raw) if xml_raw else None
    source_img_raw = body.get("source_img_path", "").strip()
    source_img_path = root_path(source_img_raw) if source_img_raw else None
    source_path = str(body.get("source_path", "")).strip("/")
    parent_path = str(body.get("parent_path", "")).strip("/")
    name = str(body.get("name", "")).strip()
    backup = bool(body.get("backup", True))
    dry_run = bool(body.get("dry_run", False))
    if not source_path or not parent_path:
        return jsonify({"ok": False, "reason": "source_path 与 parent_path 必填"}), 400
    try:
        if not dry_run:
            require_full_rewrite_enabled()
        target_image = load_client_image(img_path)
        if source_img_path is not None and source_img_path.exists() and source_img_path != img_path:
            source_image = load_client_image(source_img_path)
            s_path = normalized_img_path(source_image.root, source_path)
            source_prop = source_image.root.get(s_path)
            if source_prop is None:
                return jsonify({"ok": False, "reason": f"对照 .img 中找不到来源节点：{s_path}"}), 400
            p_path = normalized_img_path(target_image.root, parent_path)
            target_name = name or s_path.split("/")[-1]
            target_path = f"{p_path}/{target_name}" if p_path else target_name
            parent, tname = replace.img_parent_and_name(target_image.root, target_path, create=True)
            if parent.child(tname) is not None:
                return jsonify({"ok": False, "reason": f"目标已存在：{target_path}"}), 400
            replace.add_cloned_property(parent, source_prop, tname)
        else:
            s_path = normalized_img_path(target_image.root, source_path)
            p_path = normalized_img_path(target_image.root, parent_path)
            target_name = name or s_path.split("/")[-1]
            target_path = f"{p_path}/{target_name}" if p_path else target_name
            replace.copy_img_subtree(target_image.root, target_image.root, s_path, target_path, replace_existing=False)

        xml_tree = ET.parse(xml_path) if xml_path and xml_path.exists() else None
        if xml_tree is not None:
            replace.sync_xml_subtree_from_client(xml_tree.getroot(), target_image.root, target_path, replace_existing=False)
        if not dry_run:
            out = encode_image_body(target_image, target_image.wz_file.reader)
            replace.write_img(img_path, out, backup=backup)
            if xml_tree is not None:
                replace.write_xml(xml_path, xml_tree, backup=backup)
        return jsonify({"ok": True, "dryRun": dry_run, "sourcePath": s_path, "path": target_path,
                        "fromReference": source_img_path is not None})
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 400


@app.post("/api/delete_node")
def api_delete_node():
    body = request.get_json(silent=True) or {}
    img_path = root_path(body.get("img_path", ""))
    xml_raw = body.get("xml_path", "").strip()
    xml_path = root_path(xml_raw) if xml_raw else None
    path = str(body.get("path", "")).strip("/")
    backup = bool(body.get("backup", True))
    dry_run = bool(body.get("dry_run", False))
    if not path:
        return jsonify({"ok": False, "reason": "path 必填"}), 400
    try:
        if not dry_run:
            require_full_rewrite_enabled()
        image = load_client_image(img_path)
        removed = replace.delete_img_node(image.root, path)
        xml_tree = None
        xml_removed = False
        if xml_path is not None and xml_path.exists():
            xml_tree = ET.parse(xml_path)
            xml_removed = replace.delete_xml_node(xml_tree.getroot(), path)
        if not dry_run:
            out = encode_image_body(image, image.wz_file.reader)
            replace.write_img(img_path, out, backup=backup)
            if xml_tree is not None:
                replace.write_xml(xml_path, xml_tree, backup=backup)
        return jsonify({"ok": True, "dryRun": dry_run, "path": path, "clientRemoved": removed, "xmlRemoved": xml_removed})
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 400


@app.post("/api/report")
def api_report():
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "map").strip() or "map"
    img_path = root_path(body.get("img_path", ""))
    xml_raw = body.get("xml_path", "").strip()
    xml_path = root_path(xml_raw) if xml_raw else None
    reference_raw = body.get("reference_img_path", "").strip()
    reference_path = root_path(reference_raw) if reference_raw else None
    canvas_img_raw = body.get("canvas_img_path", "").strip()
    canvas_img_path = root_path(canvas_img_raw) if canvas_img_raw else None
    fmt = body.get("format", "markdown").strip()
    if not img_path.exists():
        return jsonify({"ok": False, "reason": "img_path 不存在"}), 400
    try:
        image = load_client_image(img_path)
        nodes: list[dict] = []
        walk_flat(image.root, "", "", nodes, 0)
        verdicts = compat.post_analyze(nodes, mode)
        meta = {"mode": mode, "imgPath": rel_path(img_path),
                "xmlPath": rel_path(xml_path) if xml_path and xml_path.exists() else "",
                "referencePath": rel_path(reference_path) if reference_path else ""}
        analysis = analyze(img_path, mode, reference_path)
        if canvas_img_path and canvas_img_path.is_file():
            annotate_resolved_canvases(analysis, img_path, canvas_img_path, mode)
        if fmt == "json":
            payload = {"meta": meta, "summary": analysis["summary"],
                       "nodes": [{"path": v["path"], "name": v["name"], "type": v["type"],
                                  "status": v["verdict"].status, "reason": v["verdict"].reason,
                                  "suggestion": v["verdict"].suggestion} for v in verdicts],
                       "textureSummary": analysis["summary"].get("textures", {}),
                       "textures": texture_report_rows(analysis)}
            if analysis["comparison"]:
                payload["comparison"] = analysis["comparison"]
                payload["comparisonNodes"] = analysis["flat"]
            return jsonify({"ok": True, "report": json.dumps(payload, ensure_ascii=False, indent=2)})
        report = compat.format_markdown(verdicts, meta) + "\n\n" + format_texture_markdown(analysis)
        if analysis["comparison"]:
            report += "\n\n" + format_comparison_markdown(
                analysis["flat"], analysis["comparison"])
        return jsonify({"ok": True, "report": report})
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 400


# --------------------------------------------------------------------------
# 启动
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
