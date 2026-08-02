#!/usr/bin/env python3
"""Build and install the full Morass town map without the crashing acc group."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MAP_ID = 450006130
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/450006130_排除acc完整版")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import build_arcane_river_450006130_ab3 as round3  # noqa: E402
import migrate_arcane_river_fields as migration  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def remove_acc(image) -> int:
    removed = 0
    for layer in image.root.children():
        if not layer.name.isdigit():
            continue
        objects = layer.child("obj")
        for entry in list(objects.children()):
            if (
                migration.child_value(entry, "oS") == "morass"
                and migration.child_value(entry, "l1") == "acc"
            ):
                migration.remove_child(objects, entry.name)
                removed += 1
    if removed != 32:
        raise RuntimeError(f"expected to remove 32 acc objects, removed {removed}")
    return removed


def output_paths() -> tuple[Path, Path]:
    return (
        DESTINATION / f"Client/Data/Map/Map/Map4/{MAP_ID}.img",
        DESTINATION / f"Server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml",
    )


def verify(image, server: Path) -> dict[str, object]:
    layers = [node for node in image.root.children() if node.name.isdigit()]
    objects = [entry for layer in layers for entry in layer.child("obj").children()]
    acc = [
        entry
        for entry in objects
        if migration.child_value(entry, "oS") == "morass"
        and migration.child_value(entry, "l1") == "acc"
    ]
    result = {
        "objects": len(objects),
        "acc": len(acc),
        "back": len(image.root.child("back").children()),
        "life": len(image.root.child("life").children()),
        "miniMap": image.root.child("miniMap") is not None,
        "bgm": image.root.child("info").child("bgm") is not None,
    }
    expected = {
        "objects": 71,
        "acc": 0,
        "back": 27,
        "life": 25,
        "miniMap": True,
        "bgm": True,
    }
    if result != expected:
        raise RuntimeError(f"full-without-acc verification failed: {result}, expected {expected}")
    expected_xml = migration.image_to_xml(image, f"{MAP_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError("client and server trees differ")
    return result


def build() -> dict[str, object]:
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    image = round3.full_morass_image()
    remove_acc(image)
    client, server = output_paths()
    migration.atomic_write_bytes(
        client, migration.encode_image_body(image, migration.gms_reader())
    )
    migration.atomic_write_text(server, migration.image_to_xml(image, f"{MAP_ID}.img"))
    written = migration.load_image(client, migration.GMS_KEY)
    result = verify(written, server)
    result["client_sha256"] = sha256(client)
    result["server_sha256"] = sha256(server)
    readme = f"""# 450006130 排除 acc 完整版

本版本恢复完整莫拉斯城镇，只删除第六轮 A 已定位的 32 个
`Obj/morass.img/castle_Outside/acc/*` 地图对象实例。

- 对象：71
- 背景：27
- life：25
- miniMap：保留
- BGM/mapMark：保留
- foothold、portal、ladderRope：保留
- `Obj/morass.img` 等资源文件未修改，不属于本包更新项
- Client SHA256：`{result['client_sha256']}`
- Server SHA256：`{result['server_sha256']}`
"""
    migration.atomic_write_text(DESTINATION / "README.md", readme)
    return result


def install() -> Path:
    generated_client, generated_server = output_paths()
    if not generated_client.exists() or not generated_server.exists():
        raise RuntimeError("full-without-acc package is missing; build it before installing")
    client = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
    server = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = Path(f"/private/tmp/arcane-river-{MAP_ID}-before-full-no-acc-{timestamp}")
    for path in (client, server):
        backup = backup_root / path.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    migration.atomic_write_bytes(client, generated_client.read_bytes())
    migration.atomic_write_text(server, generated_server.read_text(encoding="utf-8-sig"))
    if sha256(client) != sha256(generated_client):
        raise RuntimeError("installed client differs from the generated package")
    image = migration.load_image(client, migration.GMS_KEY)
    verify(image, server)
    return backup_root


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    if args.install:
        backup = install()
        client = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
        print(f"installed full without acc: sha256={sha256(client)} backup={backup}")
        return 0
    print(build())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
