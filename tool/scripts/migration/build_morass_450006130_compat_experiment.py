#!/usr/bin/env python3
"""Build isolated legacy-resource experiments for Morass town 450006130.

The installed map remains untouched.  Both variants start from the verified
22-object map, remove only its Morass object records, and append a projection
from the TMS source.  Every projected object references a new, map-specific
resource whose Canvas records retain only legacy playback metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool/wz-python"
sys.path.insert(0, str(WZPY))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import migrate_morass_450006130 as stable  # noqa: E402
from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzKey,
    WzStringProperty,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.canvas import _read_canvas_bytes, decode_canvas  # noqa: E402
from wzpy.incremental_img import mutate_img, scan_img  # noqa: E402
from wzpy.incremental_xml import mutate_xml, scan_xml  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


OUTPUT = Path("/private/tmp/morass-450006130-compat-experiment")
COMPAT_ASSET_NAME = "morassTownLegacy.img"
COMPAT_OBJECT_SET = "morassTownLegacy"
VARIANT_A = "A_兼容投影_排除问题桥"
VARIANT_B = "B_兼容投影_完整对象"
EXPECTED_CURRENT_MORASS = 16
EXPECTED_CONNECT = 6
EXPECTED_SOURCE_MORASS = 102
EXPECTED_PROBLEM_BRIDGE = 14
LEGACY_OBJECT_FIELDS = ("oS", "l0", "l1", "l2", "x", "y", "z", "f", "zM", "r")
CANVAS_CHILDREN = {"origin", "z", "delay"}
GMS_KEY = WzKey.for_region("GMS")
BMS_KEY = WzKey.for_region("BMS")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def child_value(node, name: str):
    child = node.child(name) if node is not None else None
    return getattr(child, "value", None)


def source_entries() -> list[tuple[str, WzSubProperty]]:
    source_data = stable.SOURCE.read_bytes()
    if sha256_bytes(source_data) != stable.SOURCE_SHA256:
        raise RuntimeError("TMS 450006130 source hash changed")
    source = stable.load_image(source_data, BMS_KEY, stable.SOURCE.name)
    entries = []
    for layer in source.root.children():
        if not layer.name.isdigit():
            continue
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        for entry in objects.children():
            if child_value(entry, "oS") == "morass":
                entries.append((layer.name, entry))
    if len(entries) != EXPECTED_SOURCE_MORASS:
        raise RuntimeError(f"expected {EXPECTED_SOURCE_MORASS} TMS Morass objects, got {len(entries)}")
    problem = sum(child_value(entry, "l1") == "foothold_Bridge" for _, entry in entries)
    if problem != EXPECTED_PROBLEM_BRIDGE:
        raise RuntimeError(f"expected {EXPECTED_PROBLEM_BRIDGE} problem bridge objects, got {problem}")
    return entries


def dense_zm(entries: list[tuple[str, WzSubProperty]]) -> dict[tuple[str, str], int]:
    values: dict[str, set[int]] = defaultdict(set)
    for layer, entry in entries:
        values[layer].add(int(child_value(entry, "zM")))
    ranks = {layer: {value: rank for rank, value in enumerate(sorted(layer_values))}
             for layer, layer_values in values.items()}
    return {
        (layer, entry.name): ranks[layer][int(child_value(entry, "zM"))]
        for layer, entry in entries
    }


def projected_entries(include_problem_bridge: bool) -> list[tuple[str, WzSubProperty]]:
    all_entries = source_entries()
    selected = [
        (layer, entry)
        for layer, entry in all_entries
        if include_problem_bridge or child_value(entry, "l1") != "foothold_Bridge"
    ]
    expected = EXPECTED_SOURCE_MORASS if include_problem_bridge else (
        EXPECTED_SOURCE_MORASS - EXPECTED_PROBLEM_BRIDGE
    )
    if len(selected) != expected:
        raise RuntimeError(f"unexpected projected object count: {len(selected)}")
    # Both variants use the complete source ranking so their shared records
    # are identical; variant B must differ only by its 14 added bridge objects.
    zm_values = dense_zm(all_entries)
    result = []
    for layer, source in selected:
        entry = WzSubProperty(source.name)
        for name in LEGACY_OBJECT_FIELDS:
            child = source.child(name)
            if child is None:
                raise RuntimeError(f"source object lacks {name}: {layer}/{source.name}")
            entry.add(stable.clone_scalar(child, entry))
        entry.add(WzStringProperty("oS", COMPAT_OBJECT_SET, entry))
        entry.add(WzIntProperty("zM", zm_values[(layer, source.name)], entry))
        fields = tuple(child.name for child in entry.children())
        if fields != LEGACY_OBJECT_FIELDS:
            raise RuntimeError(f"unexpected projected fields for {layer}/{entry.name}: {fields}")
        result.append((layer, entry))
    return result


def current_morass_paths(data: bytes) -> list[tuple[str, str]]:
    image = stable.load_image(data, GMS_KEY, stable.CLIENT.name)
    result = []
    for layer in image.root.children():
        if not layer.name.isdigit():
            continue
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        for entry in objects.children():
            if child_value(entry, "oS") == "morass":
                result.append((layer.name, entry.name))
    if len(result) != EXPECTED_CURRENT_MORASS:
        raise RuntimeError(f"expected {EXPECTED_CURRENT_MORASS} current Morass objects, got {len(result)}")
    return result


def protected_records(data: bytes) -> dict[tuple[str, ...], bytes]:
    layout = scan_img(data, region="GMS")
    protected = {}
    for record in layout.root.records:
        if not record.name.isdigit() or record.children is None:
            protected[(record.name,)] = data[record.start:record.end]
            continue
        for child in record.children.records:
            if child.name != "obj" or record.name not in {"0", "1", "2", "3", "4"}:
                protected[(record.name, child.name)] = data[child.start:child.end]
    return protected


def protected_xml_records(text: str) -> dict[tuple[str, ...], str]:
    root = scan_xml(text)
    protected = {}
    for node in root.children:
        if not str(node.name or "").isdigit() or node.name not in {"0", "1", "2", "3", "4"}:
            protected[(str(node.name),)] = text[node.start:node.end]
            continue
        for child in node.children:
            if child.name != "obj":
                protected[(str(node.name), str(child.name))] = text[child.start:child.end]
    return protected


def map_without_current_morass(client_data: bytes, server_text: str) -> tuple[bytes, str]:
    client = client_data
    server = server_text
    for layer, name in current_morass_paths(client_data):
        client = mutate_img(
            client, "remove", (layer, "obj", name), region="GMS"
        ).data
        server = mutate_xml(server, "remove", (layer, "obj", name))
    return client, server


def build_map(entries: list[tuple[str, WzSubProperty]]) -> tuple[bytes, str]:
    client_before = stable.CLIENT.read_bytes()
    server_before = stable.SERVER.read_text(encoding="utf-8-sig")
    if sha256_bytes(client_before) != stable.FINAL_CLIENT_SHA256:
        raise RuntimeError("installed client map is not the verified 22-object baseline")
    if sha256_bytes(stable.SERVER.read_bytes()) != stable.FINAL_SERVER_SHA256:
        raise RuntimeError("installed server XML is not the verified 22-object baseline")
    protected = protected_records(client_before)
    protected_xml = protected_xml_records(server_before)
    client, server = map_without_current_morass(client_before, server_before)
    for layer, entry in entries:
        client = stable.append_property(client, (layer, "obj"), entry)
        server = stable.append_xml_property(server, (layer, "obj"), entry)
    if protected_records(client) != protected:
        raise RuntimeError("a protected raw IMG record changed")
    if protected_xml_records(server) != protected_xml:
        raise RuntimeError("a protected server XML node changed")
    return client, server


def clone_canvas(source: WzCanvasProperty, parent: WzSubProperty) -> WzCanvasProperty:
    canvas = WzCanvasProperty(source.name, parent)
    canvas.width = int(source.width)
    canvas.height = int(source.height)
    canvas.format = int(source.format)
    canvas.format2 = int(source.format2)
    canvas._png_data = _read_canvas_bytes(source)
    canvas._png_length = len(canvas._png_data)
    for child in source.children():
        if child.name not in CANVAS_CHILDREN:
            continue
        if isinstance(child, WzVectorProperty):
            canvas.add(WzVectorProperty(child.name, int(child.x), int(child.y), canvas))
        elif isinstance(child, WzIntProperty):
            canvas.add(WzIntProperty(child.name, int(child.value), canvas))
        else:
            raise TypeError(f"unsupported Canvas metadata: {type(child).__name__}")
    if not isinstance(canvas.child("origin"), WzVectorProperty):
        raise RuntimeError(f"Canvas lacks origin: {source.name}")
    return canvas


def ensure_subproperty(parent: WzSubProperty, name: str) -> WzSubProperty:
    child = parent.child(name)
    if child is None:
        child = WzSubProperty(name, parent)
        parent.add(child)
    if not isinstance(child, WzSubProperty):
        raise TypeError(f"resource branch is not a container: {name}")
    return child


def all_branches() -> tuple[tuple[str, str, str], ...]:
    seen = set()
    result = []
    for _, entry in source_entries():
        branch = tuple(str(child_value(entry, name)) for name in ("l0", "l1", "l2"))
        if branch not in seen:
            seen.add(branch)
            result.append(branch)
    return tuple(result)


def build_compat_asset() -> bytes:
    source_data = stable.MORASS_ASSET.read_bytes()
    if sha256_bytes(source_data) != stable.MORASS_ASSET_SHA256:
        raise RuntimeError("installed morass.img is not the tested GMS resource")
    source = stable.load_image(source_data, GMS_KEY, stable.MORASS_ASSET.name)
    output_root = WzSubProperty(COMPAT_ASSET_NAME)
    for l0, l1, l2 in all_branches():
        source_branch = source.root.get(f"{l0}/{l1}/{l2}")
        if not isinstance(source_branch, WzSubProperty):
            raise RuntimeError(f"missing Morass branch: {l0}/{l1}/{l2}")
        target_l0 = ensure_subproperty(output_root, l0)
        target_l1 = ensure_subproperty(target_l0, l1)
        target_l2 = ensure_subproperty(target_l1, l2)
        for child in source_branch.children():
            if not isinstance(child, WzCanvasProperty):
                raise TypeError(f"non-Canvas node in {l0}/{l1}/{l2}: {child.name}")
            target_l2.add(clone_canvas(child, target_l2))

    carrier = stable.load_image(source_data, GMS_KEY, COMPAT_ASSET_NAME)
    carrier._root = output_root
    carrier._parsed = True
    reader = WzBinaryReader(io.BytesIO(b""), GMS_KEY)
    encoded = encode_image_body(carrier, reader)
    verify_asset(encoded, source)
    return encoded


def canvas_signatures(root: WzSubProperty) -> dict[str, tuple]:
    result = {}
    for node, path in stable.walk(root):
        if not isinstance(node, WzCanvasProperty):
            continue
        origin = node.child("origin")
        result[path] = (
            int(node.width),
            int(node.height),
            int(node.format),
            int(node.format2),
            (int(origin.x), int(origin.y)) if isinstance(origin, WzVectorProperty) else None,
            sha256_bytes(_read_canvas_bytes(node)),
        )
    return result


def verify_asset(data: bytes, source: WzImage) -> None:
    image = stable.load_image(data, GMS_KEY, COMPAT_ASSET_NAME)
    expected_paths = set()
    for branch in all_branches():
        node = source.root.get("/".join(branch))
        for child in node.children():
            expected_paths.add("/".join((*branch, child.name)))
    signatures = canvas_signatures(image.root)
    source_signatures = canvas_signatures(source.root)
    if set(signatures) != expected_paths:
        raise RuntimeError("compat resource Canvas set differs from referenced source branches")
    for path, signature in signatures.items():
        if signature != source_signatures[path]:
            raise RuntimeError(f"compat Canvas payload or geometry changed: {path}")
        canvas = image.root.get(path)
        if set(child.name for child in canvas.children()) - CANVAS_CHILDREN:
            raise RuntimeError(f"compat Canvas retains modern metadata: {path}")
        if (int(canvas.format), int(canvas.format2)) != (1, 0):
            raise RuntimeError(f"compat Canvas is not ARGB4444: {path}")
        pixels = decode_canvas(canvas, region="GMS").convert("RGBA")
        if pixels.getchannel("A").getbbox() is None:
            raise RuntimeError(f"compat Canvas has no visible pixels: {path}")


def collect_objects(image: WzImage) -> list[tuple[str, WzSubProperty]]:
    result = []
    for layer in image.root.children():
        if not layer.name.isdigit():
            continue
        objects = layer.child("obj")
        if isinstance(objects, WzSubProperty):
            result.extend((layer.name, entry) for entry in objects.children())
    return result


def xml_projection(text: str) -> dict[tuple[str, str], tuple[tuple[str, object], ...]]:
    root = ET.fromstring(text)
    result = {}
    for layer in root:
        if layer.tag != "imgdir" or not str(layer.get("name", "")).isdigit():
            continue
        objects = next((child for child in layer if child.tag == "imgdir" and child.get("name") == "obj"), None)
        for entry in objects if objects is not None else ():
            fields = []
            for child in entry:
                value: object = child.get("value")
                if child.tag in {"int", "short", "long"}:
                    value = int(value)
                fields.append((child.get("name"), value))
            result[(layer.get("name"), entry.get("name"))] = tuple(fields)
    return result


def verify_variant(
    client: bytes,
    server: str,
    asset: bytes,
    expected_entries: list[tuple[str, WzSubProperty]],
) -> None:
    image = stable.load_image(client, GMS_KEY, stable.CLIENT.name)
    objects = collect_objects(image)
    connect = [(layer, entry) for layer, entry in objects if child_value(entry, "oS") == "connect"]
    compat = [(layer, entry) for layer, entry in objects if child_value(entry, "oS") == COMPAT_OBJECT_SET]
    other = [(layer, entry) for layer, entry in objects if child_value(entry, "oS") not in {"connect", COMPAT_OBJECT_SET}]
    if len(connect) != EXPECTED_CONNECT or other or len(compat) != len(expected_entries):
        raise RuntimeError(
            f"variant object counts differ: connect={len(connect)} compat={len(compat)} other={len(other)}"
        )
    wanted = {
        (layer, entry.name): stable.record_projection(entry)
        for layer, entry in expected_entries
    }
    actual = {
        (layer, entry.name): stable.record_projection(entry)
        for layer, entry in compat
    }
    if actual != wanted:
        raise RuntimeError("client compat-object projection differs from source")
    server_objects = xml_projection(server)
    client_objects = {
        (layer, entry.name): stable.record_projection(entry)
        for layer, entry in objects
    }
    if server_objects != client_objects:
        raise RuntimeError("server XML object projection differs from client")
    asset_image = stable.load_image(asset, GMS_KEY, COMPAT_ASSET_NAME)
    for _, entry in compat:
        branch = "/".join(str(child_value(entry, name)) for name in ("l0", "l1", "l2"))
        if asset_image.root.get(branch) is None:
            raise RuntimeError(f"compat resource lacks branch: {branch}")
    scan_img(client, region="GMS")
    scan_xml(server)


def output_paths(variant: str) -> tuple[Path, Path, Path]:
    root = OUTPUT / variant
    return (
        root / f"Client/Data/Map/Map/Map4/{stable.MAP_ID}.img",
        root / f"Client/Data/Map/Obj/{COMPAT_ASSET_NAME}",
        root / f"Server/wz/Map.wz/Map/Map4/{stable.MAP_ID}.img.xml",
    )


def write_variant(
    variant: str,
    client: bytes,
    server: str,
    asset: bytes,
) -> dict[str, str]:
    map_path, asset_path, server_path = output_paths(variant)
    atomic_write(map_path, client)
    atomic_write(asset_path, asset)
    atomic_write(server_path, server.encode("utf-8"))
    return {
        "map": sha256_bytes(map_path.read_bytes()),
        "asset": sha256_bytes(asset_path.read_bytes()),
        "server": sha256_bytes(server_path.read_bytes()),
    }


def write_readme(results: dict[str, dict[str, str]]) -> None:
    text = f"""# 450006130 旧端对象兼容实验

本目录只包含隔离实验文件，没有覆盖项目中已验证的 22 对象正式地图。

两个版本都把 TMS 对象投影到地图专用 `{COMPAT_ASSET_NAME}`：Canvas 像素、
尺寸、ARGB4444 格式、origin、z 和 delay 保持不变；删除对象 Canvas 上的现代
foothold 等元数据；地图对象仅保留旧端十字段，并将每层 zM 稠密化以保持相对顺序。

## 测试顺序

1. `{VARIANT_A}`：6 connect + 88 兼容 Morass 对象，共 94 个；排除已知会触发
   黑屏高负载的 14 个 foothold_Bridge，但恢复其余 72 个缺失对象。
2. A 正常后再测 `{VARIANT_B}`：6 connect + 102 兼容 Morass 对象，共 108 个；
   在 A 的基础上补回全部 14 个 foothold_Bridge。

若 A 异常，立即恢复正式 22 对象版本，不测 B；若 A 正常而 B 异常，触发面仍
局限于 14 个 foothold_Bridge，下一步应把它们合成为少量静态 Canvas。

## SHA-256

### {VARIANT_A}

- Map: `{results[VARIANT_A]['map']}`
- {COMPAT_ASSET_NAME}: `{results[VARIANT_A]['asset']}`
- Server XML: `{results[VARIANT_A]['server']}`

### {VARIANT_B}

- Map: `{results[VARIANT_B]['map']}`
- {COMPAT_ASSET_NAME}: `{results[VARIANT_B]['asset']}`
- Server XML: `{results[VARIANT_B]['server']}`
"""
    atomic_write(OUTPUT / "README_测试顺序.md", text.encode("utf-8"))
    sums = []
    for variant in (VARIANT_A, VARIANT_B):
        for path in output_paths(variant):
            sums.append(f"{sha256_bytes(path.read_bytes())}  {path.relative_to(OUTPUT)}")
    atomic_write(OUTPUT / "SHA256SUMS", ("\n".join(sums) + "\n").encode("utf-8"))


def build(check_only: bool) -> dict[str, dict[str, str]]:
    asset = build_compat_asset()
    variants = {
        VARIANT_A: projected_entries(False),
        VARIANT_B: projected_entries(True),
    }
    projection_a = {
        (layer, entry.name): stable.record_projection(entry)
        for layer, entry in variants[VARIANT_A]
    }
    projection_b = {
        (layer, entry.name): stable.record_projection(entry)
        for layer, entry in variants[VARIANT_B]
    }
    if any(projection_b.get(key) != value for key, value in projection_a.items()):
        raise RuntimeError("A/B shared object records are not identical")
    added = set(projection_b) - set(projection_a)
    if len(added) != EXPECTED_PROBLEM_BRIDGE or any(
        dict(projection_b[key]).get("l1") != "foothold_Bridge" for key in added
    ):
        raise RuntimeError("variant B does not add exactly the 14 problem bridge objects")
    built = {}
    for name, entries in variants.items():
        client, server = build_map(entries)
        verify_variant(client, server, asset, entries)
        built[name] = (client, server)
    results = {
        name: {
            "map": sha256_bytes(client),
            "asset": sha256_bytes(asset),
            "server": sha256_bytes(server.encode("utf-8")),
        }
        for name, (client, server) in built.items()
    }
    if not check_only:
        written = {
            name: write_variant(name, client, server, asset)
            for name, (client, server) in built.items()
        }
        if written != results:
            raise RuntimeError("written experiment hashes differ from verified bytes")
        write_readme(written)
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify in memory without writing")
    args = parser.parse_args()
    results = build(args.check)
    for name, hashes in results.items():
        print(f"{name}: {hashes}")
    if not args.check:
        print(f"output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
