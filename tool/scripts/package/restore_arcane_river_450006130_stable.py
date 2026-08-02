#!/usr/bin/env python3
"""Restore the last field-tested stable 450006130 variant."""

from __future__ import annotations

import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MAP_ID = 450006130
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/450006130_不崩稳定版_恢复")
MAP_PATH = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
SERVER_PATH = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
ASSET_PATH = ROOT / "clien/Data/Map/Obj/morass.img"
TMS_ASSET_PATH = Path(
    "/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data/Map/Obj/morass.img"
)
EXPECTED_CURRENT_MAP_SHA256 = "6f8cff3b09b89d27149036d9aa067e39c00a3204f5326c55c0ad9bebc2db350a"
EXPECTED_CURRENT_SERVER_SHA256 = "cbea17d7e3c85710594f302f324312d48bd0713ae231c8b4430b81ed509a10bc"
EXPECTED_CURRENT_ASSET_SHA256 = "ba901c8d55b4ffb56451926c36161b4e081cfa2214d83008f2c9202b535e3935"
EXPECTED_TMS_ASSET_SHA256 = "d026830df4ed9557a302a5b8e46eadb72b74577f571a6d749b6e67be8f4b7805"
EXPECTED_RESTORED_ASSET_SHA256 = "5af8decae63f54e7ecba5fefce8335c2096f19b43080ee8b14adee449dc19f3e"
RESTORE_CANVASES = (
    "castle_Outside/foothold_Bridge/2/0",
    "castle_Outside/foothold_Bridge/4/0",
)
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_fields as migration  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output_paths() -> tuple[Path, Path, Path]:
    return (
        DESTINATION / f"Client/Data/Map/Map/Map4/{MAP_ID}.img",
        DESTINATION / "Client/Data/Map/Obj/morass.img",
        DESTINATION / f"Server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml",
    )


def assert_current_baseline() -> None:
    actual = (sha256(MAP_PATH), sha256(SERVER_PATH), sha256(ASSET_PATH))
    expected = (
        EXPECTED_CURRENT_MAP_SHA256,
        EXPECTED_CURRENT_SERVER_SHA256,
        EXPECTED_CURRENT_ASSET_SHA256,
    )
    if actual != expected:
        raise RuntimeError(f"project is not the expected twelfth-round A baseline: {actual}")
    if sha256(TMS_ASSET_PATH) != EXPECTED_TMS_ASSET_SHA256:
        raise RuntimeError("TMS Morass source changed")


def stable_map_bytes() -> tuple[bytes, str, int]:
    image = migration.load_image(MAP_PATH, migration.GMS_KEY)
    removed = 0
    for layer in image.root.children():
        if not layer.name.isdigit():
            continue
        objects = layer.child("obj")
        for entry in list(objects.children()):
            if migration.child_value(entry, "oS") == "morass":
                migration.remove_child(objects, entry.name)
                removed += 1
    if removed != 6:
        raise RuntimeError(f"expected 6 remaining Morass objects, removed {removed}")
    data = migration.encode_image_body(image, migration.gms_reader())
    xml = migration.image_to_xml(image, f"{MAP_ID}.img")
    return data, xml, removed


def restored_asset_bytes() -> bytes:
    source = migration.load_image(TMS_ASSET_PATH, migration.BMS_KEY)
    target = migration.load_image(ASSET_PATH, migration.GMS_KEY)
    materializer = migration.CanvasMaterializer()
    for path in RESTORE_CANVASES:
        source_canvas = source.root.get(path)
        target_canvas = target.root.get(path)
        restored = materializer.materialize(
            source_canvas, target_canvas.parent, source, TMS_ASSET_PATH
        )
        if (restored.width, restored.height) != (target_canvas.width, target_canvas.height):
            raise RuntimeError(f"restored Canvas dimensions differ: {path}")
        target_canvas._png_data = restored._png_data
        target_canvas._png_length = restored._png_length
        target_canvas._png_offset = 0
    data = migration.encode_image_body(target, migration.gms_reader())
    actual = hashlib.sha256(data).hexdigest()
    if actual != EXPECTED_RESTORED_ASSET_SHA256:
        raise RuntimeError(f"restored Morass resource hash changed: {actual}")
    return data


def verify(client: Path, asset: Path, server: Path) -> dict[str, object]:
    image = migration.load_image(client, migration.GMS_KEY)
    objects = [
        entry
        for layer in image.root.children()
        if layer.name.isdigit()
        for entry in layer.child("obj").children()
    ]
    resources = {migration.child_value(entry, "oS") for entry in objects}
    result = {
        "objects": len(objects),
        "resources": resources,
        "back": len(image.root.child("back").children()),
        "life": len(image.root.child("life").children()),
        "miniMap": image.root.child("miniMap") is not None,
        "bgm": image.root.child("info").child("bgm") is not None,
    }
    expected = {
        "objects": 6,
        "resources": {"connect"},
        "back": 27,
        "life": 25,
        "miniMap": True,
        "bgm": True,
    }
    if result != expected:
        raise RuntimeError(f"stable map verification failed: {result}")
    if server.read_text(encoding="utf-8-sig") != migration.image_to_xml(
        image, f"{MAP_ID}.img"
    ):
        raise RuntimeError("stable client and server trees differ")
    if sha256(asset) != EXPECTED_RESTORED_ASSET_SHA256:
        raise RuntimeError("restored Morass resource differs from original")
    return result


def build() -> dict[str, object]:
    assert_current_baseline()
    stable_map, stable_xml, removed = stable_map_bytes()
    stable_asset = restored_asset_bytes()
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)

    backup_root = DESTINATION / "Backup_恢复前第十二轮A"
    backup_map = backup_root / f"Client/Data/Map/Map/Map4/{MAP_ID}.img"
    backup_asset = backup_root / "Client/Data/Map/Obj/morass.img"
    backup_server = backup_root / f"Server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    migration.atomic_write_bytes(backup_map, MAP_PATH.read_bytes())
    migration.atomic_write_bytes(backup_asset, ASSET_PATH.read_bytes())
    migration.atomic_write_text(
        backup_server, SERVER_PATH.read_text(encoding="utf-8-sig")
    )

    client, asset, server = output_paths()
    migration.atomic_write_bytes(client, stable_map)
    migration.atomic_write_bytes(asset, stable_asset)
    migration.atomic_write_text(server, stable_xml)
    result = verify(client, asset, server)
    result.update(
        {
            "removed": removed,
            "client_sha256": sha256(client),
            "asset_sha256": sha256(asset),
            "server_sha256": sha256(server),
        }
    )
    readme = f"""# 450006130 实机不崩稳定版恢复

该版本恢复到收窄 AB 测试之前实机确认不崩的结构：保留完整背景、NPC、life、
小地图、BGM、portal、foothold、ladderRope 和 6 个旧端 connect 对象，删除全部
Morass 对象实例。`morass.img` 同时恢复为实验前原始资源。

- Client SHA256：`{result['client_sha256']}`
- morass.img SHA256：`{result['asset_sha256']}`
- Server SHA256：`{result['server_sha256']}`
- 恢复前第十二轮 A 已保存在 `Backup_恢复前第十二轮A`。
"""
    migration.atomic_write_text(DESTINATION / "README.md", readme)
    return result


def install() -> Path:
    client, asset, server = output_paths()
    if not all(path.exists() for path in (client, asset, server)):
        raise RuntimeError("stable restore package is missing; build it before installing")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = Path(f"/private/tmp/arcane-river-{MAP_ID}-before-stable-{timestamp}")
    for path in (MAP_PATH, ASSET_PATH, SERVER_PATH):
        backup = backup_root / path.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    migration.atomic_write_bytes(MAP_PATH, client.read_bytes())
    migration.atomic_write_bytes(ASSET_PATH, asset.read_bytes())
    migration.atomic_write_text(SERVER_PATH, server.read_text(encoding="utf-8-sig"))
    verify(MAP_PATH, ASSET_PATH, SERVER_PATH)
    return backup_root


def main() -> int:
    result = build()
    backup = install()
    print(f"restored stable map: {result} backup={backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
