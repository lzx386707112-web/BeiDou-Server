#!/usr/bin/env python3
"""Test Morass foothold_Bridge Canvas payloads with a known legacy source."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
MAP_ID = 450006130
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/AB测试_450006130_第十二轮")
MAP_PATH = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
SERVER_PATH = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
ASSET_PATH = ROOT / "clien/Data/Map/Obj/morass.img"
ORIGINAL_ASSET = Path(
    "/Users/lizixian/Downloads/神秘河/AB测试_450006130_第十一轮/"
    "B_原始资源对照/Client/Data/Map/Obj/morass.img"
)
CONNECT_ASSET = ROOT / "clien/Data/Map/Obj/connect.img"
CONNECT_CANVAS = "rope/0/1/0"
TARGET_CANVASES = (
    "castle_Outside/foothold_Bridge/2/0",
    "castle_Outside/foothold_Bridge/4/0",
)
EXPECTED_MAP_SHA256 = "6f8cff3b09b89d27149036d9aa067e39c00a3204f5326c55c0ad9bebc2db350a"
EXPECTED_SERVER_SHA256 = "cbea17d7e3c85710594f302f324312d48bd0713ae231c8b4430b81ed509a10bc"
EXPECTED_ASSET_SHA256 = "5af8decae63f54e7ecba5fefce8335c2096f19b43080ee8b14adee449dc19f3e"
EXPECTED_CONNECT_SHA256 = "66cd212682a5760bd277d8dff07728251625e3c7f1f7aef22247d6372ba2c7ae"
VARIANT_A = "A_替换l2_2_4画布载荷"
VARIANT_B = "B_原始资源对照"
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_fields as migration  # noqa: E402
from wzpy import WzCanvasProperty, WzImage  # noqa: E402
from wzpy.canvas import _read_canvas_bytes, decode_canvas, encode_canvas_payload  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_image_bytes(data: bytes):
    image = WzImage.from_bytes(data, key=migration.GMS_KEY, name="morass.img")
    image.parse()
    return image


def output_paths(name: str) -> tuple[Path, Path, Path]:
    root = DESTINATION / name
    return (
        root / f"Client/Data/Map/Map/Map4/{MAP_ID}.img",
        root / "Client/Data/Map/Obj/morass.img",
        root / f"Server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml",
    )


def assert_sources() -> None:
    if sha256(MAP_PATH) != EXPECTED_MAP_SHA256 or sha256(SERVER_PATH) != EXPECTED_SERVER_SHA256:
        raise RuntimeError("project map/server are not the expected AB8 B baseline")
    if not ORIGINAL_ASSET.exists() or sha256(ORIGINAL_ASSET) != EXPECTED_ASSET_SHA256:
        raise RuntimeError("original Morass control resource is missing or changed")
    if sha256(CONNECT_ASSET) != EXPECTED_CONNECT_SHA256:
        raise RuntimeError("known-compatible connect resource changed")


def canvas_payloads(image) -> dict[str, str]:
    return {
        path: hashlib.sha256(_read_canvas_bytes(node)).hexdigest()
        for node, path in migration.walk(image.root)
        if isinstance(node, WzCanvasProperty)
    }


def canonical_xml(image) -> tuple:
    root = ET.fromstring(migration.image_to_xml(image, "morass.img").lstrip("\ufeff"))

    def canonical(node) -> tuple:
        return (
            node.tag,
            tuple(sorted(node.attrib.items())),
            (node.text or "").strip(),
            tuple(canonical(child) for child in node),
        )

    return canonical(root)


def replace_payloads() -> bytes:
    image = migration.load_image(ORIGINAL_ASSET, migration.GMS_KEY)
    before_payloads = canvas_payloads(image)
    before_tree = canonical_xml(image)
    connect = migration.load_image(CONNECT_ASSET, migration.GMS_KEY)
    source = connect.root.get(CONNECT_CANVAS)
    if not isinstance(source, WzCanvasProperty):
        raise RuntimeError(f"missing known-compatible Canvas: {CONNECT_CANVAS}")
    source_image = decode_canvas(source, region="GMS").convert("RGBA")

    for path in TARGET_CANVASES:
        canvas = image.root.get(path)
        if not isinstance(canvas, WzCanvasProperty):
            raise RuntimeError(f"missing target Canvas: {path}")
        replacement = source_image.resize(
            (canvas.width, canvas.height), Image.Resampling.NEAREST
        )
        payload = encode_canvas_payload(
            replacement,
            int(canvas.format) + int(canvas.format2),
            canvas.width,
            canvas.height,
            key=migration.GMS_KEY,
            listwz=False,
        )
        canvas._png_data = payload
        canvas._png_length = len(payload)
        canvas._png_offset = 0

    encoded = migration.encode_image_body(image, migration.gms_reader())
    written = load_image_bytes(encoded)
    after_payloads = canvas_payloads(written)
    changed = {path for path in before_payloads if before_payloads[path] != after_payloads[path]}
    if changed != set(TARGET_CANVASES):
        raise RuntimeError(f"unexpected changed Canvas payloads: {changed}")
    if canonical_xml(written) != before_tree:
        raise RuntimeError("Canvas metadata or other resource nodes changed")
    for path in TARGET_CANVASES:
        decode_canvas(written.root.get(path), region="GMS")
    return encoded


def write_variant(name: str, asset_data: bytes) -> dict[str, str]:
    map_output, asset_output, server_output = output_paths(name)
    migration.atomic_write_bytes(map_output, MAP_PATH.read_bytes())
    migration.atomic_write_bytes(asset_output, asset_data)
    migration.atomic_write_text(
        server_output, SERVER_PATH.read_text(encoding="utf-8-sig")
    )
    return {
        "map": sha256(map_output),
        "asset": sha256(asset_output),
        "server": sha256(server_output),
    }


def write_readme(a: dict[str, str], b: dict[str, str]) -> None:
    text = f"""# 450006130 崩溃 AB 测试（第十二轮）

第十一轮删除对象 Canvas 的 foothold 元数据后仍然高负载，证明 foothold 元数据
不是触发源。本轮恢复原始 `morass.img` 的所有元数据，只替换 `l2=2/4` 两个
Canvas 的压缩像素载荷。替换像素来自当前地图已验证正常的
`connect.img/rope/0/1/0`，按目标宽高使用最近邻缩放并编码为 ARGB4444。

## A_替换l2_2_4画布载荷

- 仅改变 `castle_Outside/foothold_Bridge/2/0` 的 Canvas 载荷。
- 仅改变 `castle_Outside/foothold_Bridge/4/0` 的 Canvas 载荷。
- 宽高、format、origin、z、foothold、地图对象和固定 foothold 均不变。
- Map SHA256：`{a['map']}`
- morass.img SHA256：`{a['asset']}`
- Server SHA256：`{a['server']}`

## B_原始资源对照

- 原始高负载资源，用于恢复。
- Map SHA256：`{b['map']}`
- morass.img SHA256：`{b['asset']}`
- Server SHA256：`{b['server']}`

## 结果判断

- A 正常：触发源在目标 Canvas 像素载荷或其压缩内容。
- A 仍高负载：排除像素内容，下一步测试目标 Canvas 尺寸或对象分支结构。
"""
    migration.atomic_write_text(DESTINATION / "README_测试顺序.md", text)


def build() -> tuple[dict[str, str], dict[str, str]]:
    assert_sources()
    replacement = replace_payloads()
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    a = write_variant(VARIANT_A, replacement)
    b = write_variant(VARIANT_B, ORIGINAL_ASSET.read_bytes())
    if a["map"] != b["map"] or a["server"] != b["server"]:
        raise RuntimeError("A and B map/server files differ")
    if b["asset"] != EXPECTED_ASSET_SHA256 or a["asset"] == b["asset"]:
        raise RuntimeError("resource variant hashes are invalid")
    write_readme(a, b)
    return a, b


def install(name: str) -> Path:
    generated_map, generated_asset, generated_server = output_paths(name)
    if not all(path.exists() for path in (generated_map, generated_asset, generated_server)):
        raise RuntimeError("twelfth-round package is missing; generate it before installing")
    if sha256(MAP_PATH) != EXPECTED_MAP_SHA256 or sha256(SERVER_PATH) != EXPECTED_SERVER_SHA256:
        raise RuntimeError("project map/server are no longer the AB8 B baseline")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    label = "A" if name == VARIANT_A else "B"
    backup_root = Path(f"/private/tmp/arcane-river-{MAP_ID}-before-AB12-{label}-{timestamp}")
    for path in (MAP_PATH, SERVER_PATH, ASSET_PATH):
        backup = backup_root / path.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    migration.atomic_write_bytes(ASSET_PATH, generated_asset.read_bytes())
    if MAP_PATH.read_bytes() != generated_map.read_bytes():
        raise RuntimeError("installed map differs from package")
    if SERVER_PATH.read_bytes() != generated_server.read_bytes():
        raise RuntimeError("installed server XML differs from package")
    if ASSET_PATH.read_bytes() != generated_asset.read_bytes():
        raise RuntimeError("installed morass.img differs from package")
    return backup_root


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-a", action="store_true")
    parser.add_argument("--install-b", action="store_true")
    args = parser.parse_args()
    if args.install_a and args.install_b:
        parser.error("--install-a and --install-b are mutually exclusive")
    if args.install_a or args.install_b:
        name = VARIANT_A if args.install_a else VARIANT_B
        backup = install(name)
        print(
            f"installed {name}: map={sha256(MAP_PATH)} asset={sha256(ASSET_PATH)} "
            f"server={sha256(SERVER_PATH)} backup={backup}"
        )
        return 0
    a, b = build()
    print(f"A: {a}")
    print(f"B: {b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
