#!/usr/bin/env python3
"""Bisect the 14 Morass foothold_Bridge objects by their l2 branch."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MAP_ID = 450006130
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/AB测试_450006130_第八轮")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import build_arcane_river_450006130_ab3 as round3  # noqa: E402
import migrate_arcane_river_fields as migration  # noqa: E402


GROUP_A = {"0", "1"}
GROUP_B = {"2", "4"}
EXPECTED_COUNTS = {"0": 3, "1": 5, "2": 4, "4": 2}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def keep_bridge_l2(image, l2_values: set[str]) -> None:
    for layer in image.root.children():
        if not layer.name.isdigit():
            continue
        objects = layer.child("obj")
        for entry in list(objects.children()):
            resource = migration.child_value(entry, "oS")
            branch = migration.child_value(entry, "l1")
            l2 = str(migration.child_value(entry, "l2"))
            if resource == "morass" and (
                branch != "foothold_Bridge" or l2 not in l2_values
            ):
                migration.remove_child(objects, entry.name)


def object_summary(image) -> tuple[int, Counter[str], set[str]]:
    objects = [
        entry
        for layer in image.root.children()
        if layer.name.isdigit()
        for entry in layer.child("obj").children()
    ]
    bridge_l2 = Counter(
        str(migration.child_value(entry, "l2"))
        for entry in objects
        if migration.child_value(entry, "oS") == "morass"
        and migration.child_value(entry, "l1") == "foothold_Bridge"
    )
    resources = {str(migration.child_value(entry, "oS")) for entry in objects}
    return len(objects), bridge_l2, resources


def write_variant(name: str, l2_values: set[str]) -> dict[str, object]:
    image = round3.full_morass_image()
    keep_bridge_l2(image, l2_values)
    root = DESTINATION / name
    client = root / f"Client/Data/Map/Map/Map4/{MAP_ID}.img"
    server = root / f"Server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    migration.atomic_write_bytes(
        client, migration.encode_image_body(image, migration.gms_reader())
    )
    migration.atomic_write_text(server, migration.image_to_xml(image, f"{MAP_ID}.img"))

    written = migration.load_image(client, migration.GMS_KEY)
    object_count, actual_l2, resources = object_summary(written)
    expected_l2 = Counter({key: EXPECTED_COUNTS[key] for key in l2_values})
    expected_objects = 6 + sum(expected_l2.values())
    if (
        object_count != expected_objects
        or actual_l2 != expected_l2
        or resources != {"connect", "morass"}
    ):
        raise RuntimeError(
            f"{name}: expected {expected_objects} connect/morass objects and "
            f"l2 counts {expected_l2}, got {object_count}, {resources}, {actual_l2}"
        )
    expected_xml = migration.image_to_xml(written, f"{MAP_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError(f"{name}: client and server trees differ")
    return {
        "client": sha256(client),
        "server": sha256(server),
        "objects": object_count,
        "bridge_l2": dict(sorted(actual_l2.items())),
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
        raise RuntimeError("eighth-round package is missing; generate it before installing")
    client = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
    server = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    label = "A" if name.startswith("A_") else "B"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = Path(f"/private/tmp/arcane-river-{MAP_ID}-before-AB8-{label}-{timestamp}")
    for path in (client, server):
        backup = backup_root / path.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    migration.atomic_write_bytes(client, generated_client.read_bytes())
    migration.atomic_write_text(server, generated_server.read_text(encoding="utf-8-sig"))
    if sha256(client) != sha256(generated_client):
        raise RuntimeError(f"installed eighth-round {label} client differs from package")
    image = migration.load_image(client, migration.GMS_KEY)
    expected_xml = migration.image_to_xml(image, f"{MAP_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError(f"installed eighth-round {label} server differs from client")
    return backup_root


def write_readme(a: dict[str, object], b: dict[str, object]) -> None:
    text = f"""# 450006130 崩溃 AB 测试（第八轮）

第七轮 A（14 个 `foothold_Bridge`）实机黑屏并持续高负载。本轮保留完整背景、
NPC、life、小地图、BGM 和 6 个 `connect` 对象，只按 `l2` 二分这 14 个实例。

## A_l2_0_1

- 6 个 `connect` + 8 个 `foothold_Bridge`，其中 `l2=0` 3 个、`l2=1` 5 个。
- Client SHA256：`{a['client']}`
- Server SHA256：`{a['server']}`

## B_l2_2_4

- 6 个 `connect` + 6 个 `foothold_Bridge`，其中 `l2=2` 4 个、`l2=4` 2 个。
- Client SHA256：`{b['client']}`
- Server SHA256：`{b['server']}`

## 结果判断

- A 黑屏高负载、B 正常：问题在 `l2=0/1`，下一轮再拆 0 与 1。
- A 正常、B 黑屏高负载：问题在 `l2=2/4`，下一轮再拆 2 与 4。
- A、B 都正常：这些分支存在组合触发条件。
- A、B 都异常：两组各自包含问题分支。
"""
    migration.atomic_write_text(DESTINATION / "README_测试顺序.md", text)


def build() -> tuple[dict[str, object], dict[str, object]]:
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    a = write_variant("A_l2_0_1", GROUP_A)
    b = write_variant("B_l2_2_4", GROUP_B)
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
        name = "A_l2_0_1" if args.install_a else "B_l2_2_4"
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
