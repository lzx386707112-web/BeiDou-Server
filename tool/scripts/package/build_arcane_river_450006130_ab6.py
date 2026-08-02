#!/usr/bin/env python3
"""Split plain Morass decorations into acc and bridge branches."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MAP_ID = 450006130
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/AB测试_450006130_第六轮")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import build_arcane_river_450006130_ab3 as round3  # noqa: E402
import build_arcane_river_450006130_ab4 as round4  # noqa: E402
import migrate_arcane_river_fields as migration  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def keep_branch(image, branch_name: str) -> None:
    round4.keep_resource(image, "morass")
    for layer in image.root.children():
        if not layer.name.isdigit():
            continue
        objects = layer.child("obj")
        for entry in list(objects.children()):
            if migration.child_value(entry, "l1") != branch_name:
                migration.remove_child(objects, entry.name)


def write_variant(name: str, branch_name: str, expected_objects: int) -> dict[str, object]:
    image = round3.full_morass_image()
    keep_branch(image, branch_name)
    root = DESTINATION / name
    client = root / f"Client/Data/Map/Map/Map4/{MAP_ID}.img"
    server = root / f"Server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    asset = root / "Client/Data/Map/Obj/morass.img"
    migration.atomic_write_bytes(
        client, migration.encode_image_body(image, migration.gms_reader())
    )
    migration.atomic_write_text(server, migration.image_to_xml(image, f"{MAP_ID}.img"))
    asset.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "clien/Data/Map/Obj/morass.img", asset)

    written = migration.load_image(client, migration.GMS_KEY)
    objects = [
        entry
        for layer in written.root.children()
        if layer.name.isdigit()
        for entry in layer.child("obj").children()
    ]
    branches = {migration.child_value(entry, "l1") for entry in objects}
    if len(objects) != expected_objects or branches != {branch_name}:
        raise RuntimeError(
            f"{name}: expected {expected_objects} {branch_name} objects, "
            f"got {len(objects)} from {branches}"
        )
    expected_xml = migration.image_to_xml(written, f"{MAP_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError(f"{name}: client and server trees differ")
    return {"client": sha256(client), "server": sha256(server), "objects": len(objects)}


def output_paths(name: str) -> tuple[Path, Path]:
    root = DESTINATION / name
    return (
        root / f"Client/Data/Map/Map/Map4/{MAP_ID}.img",
        root / f"Server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml",
    )


def install(name: str) -> Path:
    generated_client, generated_server = output_paths(name)
    if not generated_client.exists() or not generated_server.exists():
        raise RuntimeError("sixth-round package is missing; generate it before installing")
    client = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
    server = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    label = "A" if name.startswith("A_") else "B"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = Path(f"/private/tmp/arcane-river-{MAP_ID}-before-AB6-{label}-{timestamp}")
    for path in (client, server):
        backup = backup_root / path.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    migration.atomic_write_bytes(client, generated_client.read_bytes())
    migration.atomic_write_text(server, generated_server.read_text(encoding="utf-8-sig"))
    if sha256(client) != sha256(generated_client):
        raise RuntimeError(f"installed sixth-round {label} client differs from package")
    image = migration.load_image(client, migration.GMS_KEY)
    expected_xml = migration.image_to_xml(image, f"{MAP_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError(f"installed sixth-round {label} server differs from client")
    return backup_root


def write_readme(a: dict[str, object], b: dict[str, object]) -> None:
    text = f"""# 450006130 崩溃 AB 测试（第六轮）

第五轮普通装饰对象 A 崩溃，本轮按 Morass 的 `l1` 分支拆分。两版均无 back、
life、miniMap、bgm、connect 对象和 foothold 元数据对象。

## A_仅acc

- 保留 32 个 `castle_Outside/acc` 对象。
- Client SHA256：`{a['client']}`
- Server SHA256：`{a['server']}`

## B_仅bridge

- 保留 35 个 `castle_Outside/bridge` 对象。
- Client SHA256：`{b['client']}`
- Server SHA256：`{b['server']}`

## 结果判断

- A 崩、B 正常：问题在 acc 分支，继续二分 acc 编号。
- A 正常、B 崩：问题在 bridge 分支，继续二分 bridge 编号。
- A、B 都正常：acc 与 bridge 存在组合触发条件。
- A、B 都崩：两组各自包含问题分支。
"""
    migration.atomic_write_text(DESTINATION / "README_测试顺序.md", text)


def build() -> tuple[dict[str, object], dict[str, object]]:
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    a = write_variant("A_仅acc", "acc", 32)
    b = write_variant("B_仅bridge", "bridge", 35)
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
        name = "A_仅acc" if args.install_a else "B_仅bridge"
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
