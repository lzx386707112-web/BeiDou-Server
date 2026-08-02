#!/usr/bin/env python3
"""Build the full Morass town without acc and bridge decorations."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MAP_ID = 450006130
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/450006130_排除acc和bridge完整版")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import build_arcane_river_450006130_ab3 as round3  # noqa: E402
import migrate_arcane_river_fields as migration  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def remove_plain_objects(image) -> int:
    removed = 0
    for layer in image.root.children():
        if not layer.name.isdigit():
            continue
        objects = layer.child("obj")
        for entry in list(objects.children()):
            if (
                migration.child_value(entry, "oS") == "morass"
                and migration.child_value(entry, "l1") in {"acc", "bridge"}
            ):
                migration.remove_child(objects, entry.name)
                removed += 1
    if removed != 67:
        raise RuntimeError(f"expected to remove 67 plain objects, removed {removed}")
    return removed


def output_paths() -> tuple[Path, Path]:
    return (
        DESTINATION / f"Client/Data/Map/Map/Map4/{MAP_ID}.img",
        DESTINATION / f"Server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml",
    )


def verify(image, server: Path) -> dict[str, object]:
    objects = [
        entry
        for layer in image.root.children()
        if layer.name.isdigit()
        for entry in layer.child("obj").children()
    ]
    plain = [
        entry
        for entry in objects
        if migration.child_value(entry, "oS") == "morass"
        and migration.child_value(entry, "l1") in {"acc", "bridge"}
    ]
    result = {
        "objects": len(objects),
        "plain": len(plain),
        "back": len(image.root.child("back").children()),
        "life": len(image.root.child("life").children()),
        "miniMap": image.root.child("miniMap") is not None,
        "bgm": image.root.child("info").child("bgm") is not None,
    }
    expected = {
        "objects": 36,
        "plain": 0,
        "back": 27,
        "life": 25,
        "miniMap": True,
        "bgm": True,
    }
    if result != expected:
        raise RuntimeError(f"full-without-plain verification failed: {result}, expected {expected}")
    expected_xml = migration.image_to_xml(image, f"{MAP_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError("client and server trees differ")
    return result


def build() -> dict[str, object]:
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    image = round3.full_morass_image()
    remove_plain_objects(image)
    client, server = output_paths()
    migration.atomic_write_bytes(
        client, migration.encode_image_body(image, migration.gms_reader())
    )
    migration.atomic_write_text(server, migration.image_to_xml(image, f"{MAP_ID}.img"))
    written = migration.load_image(client, migration.GMS_KEY)
    result = verify(written, server)
    result["client_sha256"] = sha256(client)
    result["server_sha256"] = sha256(server)
    readme = f"""# 450006130 排除 acc 和 bridge 完整版

本版本恢复完整莫拉斯城镇的非对象内容，只删除已确认会崩的普通装饰对象组：

- 删除 32 个 `castle_Outside/acc` 对象
- 删除 35 个 `castle_Outside/bridge` 对象
- 保留 6 个 connect 对象和 30 个带 foothold 元数据的 Morass 对象
- 保留 27 个背景、25 个 life、miniMap、BGM、mapMark
- `Obj/morass.img` 等资源文件未修改，不属于本包更新项
- Client SHA256：`{result['client_sha256']}`
- Server SHA256：`{result['server_sha256']}`
"""
    migration.atomic_write_text(DESTINATION / "README.md", readme)
    return result


def install() -> Path:
    generated_client, generated_server = output_paths()
    if not generated_client.exists() or not generated_server.exists():
        raise RuntimeError("full-without-plain package is missing; build it before installing")
    client = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
    server = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = Path(f"/private/tmp/arcane-river-{MAP_ID}-before-full-no-plain-{timestamp}")
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
        print(f"installed full without plain objects: sha256={sha256(client)} backup={backup}")
        return 0
    print(build())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
