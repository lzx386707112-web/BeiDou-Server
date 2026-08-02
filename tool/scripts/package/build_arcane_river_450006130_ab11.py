#!/usr/bin/env python3
"""Test redundant object foothold metadata in Morass map 450006130."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MAP_ID = 450006130
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/AB测试_450006130_第十一轮")
MAP_PATH = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
SERVER_PATH = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
ASSET_PATH = ROOT / "clien/Data/Map/Obj/morass.img"
EXPECTED_MAP_SHA256 = "6f8cff3b09b89d27149036d9aa067e39c00a3204f5326c55c0ad9bebc2db350a"
EXPECTED_SERVER_SHA256 = "cbea17d7e3c85710594f302f324312d48bd0713ae231c8b4430b81ed509a10bc"
EXPECTED_ASSET_SHA256 = "5af8decae63f54e7ecba5fefce8335c2096f19b43080ee8b14adee449dc19f3e"
TARGET_CANVASES = (
    "castle_Outside/foothold_Bridge/2/0",
    "castle_Outside/foothold_Bridge/4/0",
)
VARIANT_A = "A_移除l2_2_4对象foothold"
VARIANT_B = "B_原始资源对照"
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_fields as migration  # noqa: E402
from wzpy import WzCanvasProperty, WzConvexProperty, WzImage  # noqa: E402
from wzpy.canvas import _read_canvas_bytes  # noqa: E402


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


def assert_baseline() -> None:
    actual = (sha256(MAP_PATH), sha256(SERVER_PATH), sha256(ASSET_PATH))
    expected = (EXPECTED_MAP_SHA256, EXPECTED_SERVER_SHA256, EXPECTED_ASSET_SHA256)
    if actual != expected:
        raise RuntimeError(f"project is not the expected AB8 B baseline: {actual}")


def canvas_payloads(image) -> dict[str, str]:
    payloads: dict[str, str] = {}
    for node, path in migration.walk(image.root):
        if isinstance(node, WzCanvasProperty):
            payloads[path] = hashlib.sha256(_read_canvas_bytes(node)).hexdigest()
    return payloads


def xml_without_target_footholds(image) -> tuple:
    xml = migration.image_to_xml(image, "morass.img")
    root = ET.fromstring(xml.lstrip("\ufeff"))
    for canvas_path in TARGET_CANVASES:
        node = root
        for part in canvas_path.split("/"):
            node = next(
                (child for child in node if child.attrib.get("name") == part),
                None,
            )
            if node is None:
                raise RuntimeError(f"missing XML node: {canvas_path}")
        foothold = next(
            (child for child in node if child.attrib.get("name") == "foothold"),
            None,
        )
        if foothold is not None:
            node.remove(foothold)

    def canonical(node) -> tuple:
        return (
            node.tag,
            tuple(sorted(node.attrib.items())),
            (node.text or "").strip(),
            tuple(canonical(child) for child in node),
        )

    return canonical(root)


def sanitize_asset() -> bytes:
    original = migration.load_image(ASSET_PATH, migration.GMS_KEY)
    original_payloads = canvas_payloads(original)
    expected_tree = xml_without_target_footholds(original)
    for path in TARGET_CANVASES:
        canvas = original.root.get(path)
        if not isinstance(canvas, WzCanvasProperty):
            raise RuntimeError(f"missing Canvas: {path}")
        foothold = canvas.child("foothold")
        if not isinstance(foothold, WzConvexProperty) or len(foothold.points) != 2:
            raise RuntimeError(f"unexpected foothold node: {path}")
        migration.remove_child(canvas, "foothold")

    encoded = migration.encode_image_body(original, migration.gms_reader())
    written = load_image_bytes(encoded)
    for path in TARGET_CANVASES:
        if written.root.get(path).child("foothold") is not None:
            raise RuntimeError(f"target foothold was not removed: {path}")
    if canvas_payloads(written) != original_payloads:
        raise RuntimeError("Canvas payloads changed while removing foothold metadata")
    if xml_without_target_footholds(written) != expected_tree:
        raise RuntimeError("non-target resource nodes changed")
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
    text = f"""# 450006130 崩溃 AB 测试（第十一轮）

第八至第十轮证明 `foothold_Bridge` 的 `l2=0/1/2/4` 均可单独触发高负载，
且单个实例即可触发。本轮保持第八轮 B 地图和服务端 XML 不变，只测试
`morass.img` Canvas 自带的冗余 foothold 元数据。

## A_移除l2_2_4对象foothold

- 删除 `castle_Outside/foothold_Bridge/2/0/foothold`。
- 删除 `castle_Outside/foothold_Bridge/4/0/foothold`。
- Canvas 像素、origin、z 和地图固定 foothold 均不变。
- Map SHA256：`{a['map']}`
- morass.img SHA256：`{a['asset']}`
- Server SHA256：`{a['server']}`

## B_原始资源对照

- 保留原始 `morass.img`，用于恢复和对照。
- Map SHA256：`{b['map']}`
- morass.img SHA256：`{b['asset']}`
- Server SHA256：`{b['server']}`

## 结果判断

- A 正常：旧端高负载由对象 Canvas 的 foothold 元数据触发。
- A 仍高负载：恢复 B，下一步只替换目标 Canvas 像素，不再删除地图节点。
"""
    migration.atomic_write_text(DESTINATION / "README_测试顺序.md", text)


def build() -> tuple[dict[str, str], dict[str, str]]:
    assert_baseline()
    sanitized = sanitize_asset()
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    a = write_variant(VARIANT_A, sanitized)
    b = write_variant(VARIANT_B, ASSET_PATH.read_bytes())
    if a["map"] != b["map"] or a["server"] != b["server"]:
        raise RuntimeError("A and B map/server files differ")
    if b["asset"] != EXPECTED_ASSET_SHA256 or a["asset"] == b["asset"]:
        raise RuntimeError("resource variant hashes are invalid")
    write_readme(a, b)
    return a, b


def install(name: str) -> Path:
    generated_map, generated_asset, generated_server = output_paths(name)
    if not all(path.exists() for path in (generated_map, generated_asset, generated_server)):
        raise RuntimeError("eleventh-round package is missing; generate it before installing")
    if sha256(MAP_PATH) != EXPECTED_MAP_SHA256 or sha256(SERVER_PATH) != EXPECTED_SERVER_SHA256:
        raise RuntimeError("project map/server are no longer the AB8 B baseline")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    label = "A" if name == VARIANT_A else "B"
    backup_root = Path(f"/private/tmp/arcane-river-{MAP_ID}-before-AB11-{label}-{timestamp}")
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
