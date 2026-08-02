#!/usr/bin/env python3
"""Split Morass town objects by resource IMG for the fourth crash test."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MAP_ID = 450006130
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/AB测试_450006130_第四轮")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import build_arcane_river_450006130_ab3 as round3  # noqa: E402
import migrate_arcane_river_fields as migration  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def keep_resource(image, resource: str) -> None:
    round3.keep_objects_only(image)
    for layer in image.root.children():
        if not layer.name.isdigit():
            continue
        objects = layer.child("obj")
        for entry in list(objects.children()):
            if migration.child_value(entry, "oS") != resource:
                migration.remove_child(objects, entry.name)


def write_variant(name: str, resource: str, expected_objects: int) -> dict[str, object]:
    image = round3.full_morass_image()
    keep_resource(image, resource)
    root = DESTINATION / name
    client = root / f"Client/Data/Map/Map/Map4/{MAP_ID}.img"
    server = root / f"Server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    asset_source = ROOT / f"clien/Data/Map/Obj/{resource}.img"
    asset_target = root / f"Client/Data/Map/Obj/{resource}.img"
    migration.atomic_write_bytes(
        client, migration.encode_image_body(image, migration.gms_reader())
    )
    migration.atomic_write_text(server, migration.image_to_xml(image, f"{MAP_ID}.img"))
    asset_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(asset_source, asset_target)

    written = migration.load_image(client, migration.GMS_KEY)
    layers = [node for node in written.root.children() if node.name.isdigit()]
    objects = [entry for layer in layers for entry in layer.child("obj").children()]
    resources = {migration.child_value(entry, "oS") for entry in objects}
    if len(objects) != expected_objects or resources != {resource}:
        raise RuntimeError(
            f"{name}: expected {expected_objects} {resource} objects, "
            f"got {len(objects)} objects from {resources}"
        )
    expected_xml = migration.image_to_xml(written, f"{MAP_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError(f"{name}: client and server trees differ")
    return {
        "client": sha256(client),
        "server": sha256(server),
        "objects": len(objects),
        "resource": resource,
    }


def output_paths(name: str) -> tuple[Path, Path]:
    root = DESTINATION / name
    return (
        root / f"Client/Data/Map/Map/Map4/{MAP_ID}.img",
        root / f"Server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml",
    )


def install(name: str) -> Path:
    generated_client, generated_server = output_paths(name)
    if not generated_client.exists() or not generated_server.exists():
        raise RuntimeError("fourth-round package is missing; generate it before installing")
    client = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
    server = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    label = "A" if name.startswith("A_") else "B"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = Path(f"/private/tmp/arcane-river-{MAP_ID}-before-AB4-{label}-{timestamp}")
    for path in (client, server):
        backup = backup_root / path.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    migration.atomic_write_bytes(client, generated_client.read_bytes())
    migration.atomic_write_text(server, generated_server.read_text(encoding="utf-8-sig"))
    if sha256(client) != sha256(generated_client):
        raise RuntimeError(f"installed fourth-round {label} client differs from package")
    image = migration.load_image(client, migration.GMS_KEY)
    expected_xml = migration.image_to_xml(image, f"{MAP_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError(f"installed fourth-round {label} server differs from client")
    return backup_root


def write_readme(a: dict[str, object], b: dict[str, object]) -> None:
    text = f"""# 450006130 崩溃 AB 测试（第四轮）

第三轮仅对象层 A 实机崩溃，本轮按对象资源 IMG 拆分。两版均无 back、life、
miniMap、bgm 和 mapMark，只保留地图核心与指定对象。

## A_仅connect对象

- 仅保留 6 个 `Obj/connect.img/rope` 旧端绳索显示对象。
- Client SHA256：`{a['client']}`
- Server SHA256：`{a['server']}`

## B_仅morass对象

- 仅保留 97 个 `Obj/morass.img` 对象。
- Client SHA256：`{b['client']}`
- Server SHA256：`{b['server']}`

## 结果判断

- A 正常、B 崩：问题在 Morass 对象或 `Obj/morass.img`，继续按分支二分。
- A 崩、B 正常：问题在 6 个 connect 绳索显示对象。
- A、B 都正常：connect 与 Morass 对象存在组合触发条件。
- A、B 都崩：两个资源分组各自存在问题。
"""
    migration.atomic_write_text(DESTINATION / "README_测试顺序.md", text)


def build() -> tuple[dict[str, object], dict[str, object]]:
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    a = write_variant("A_仅connect对象", "connect", 6)
    b = write_variant("B_仅morass对象", "morass", 97)
    write_readme(a, b)
    return a, b


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-a", action="store_true")
    parser.add_argument("--install-b", action="store_true")
    args = parser.parse_args()
    if args.install_a and args.install_b:
        parser.error("--install-a and --install-b are mutually exclusive")
    if args.install_a or args.install_b:
        name = "A_仅connect对象" if args.install_a else "B_仅morass对象"
        backup = install(name)
        client = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
        print(f"installed {name}: sha256={sha256(client)} backup={backup}")
        return 0
    a, b = build()
    print(f"A: {a}")
    print(f"B: {b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
