#!/usr/bin/env python3
"""Split the three failing l2=0 objects by map instance."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MAP_ID = 450006130
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/AB测试_450006130_第十轮")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import build_arcane_river_450006130_ab3 as round3  # noqa: E402
import migrate_arcane_river_fields as migration  # noqa: E402


GROUP_A = {("1", "40")}
GROUP_B = {("1", "21"), ("3", "5")}
EXPECTED = {
    ("1", "40"): (-2369, -614, 69),
    ("1", "21"): (627, -728, 73),
    ("3", "5"): (1390, -404, 56),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def keep_instances(image, selected: set[tuple[str, str]]) -> None:
    for layer in image.root.children():
        if not layer.name.isdigit():
            continue
        objects = layer.child("obj")
        for entry in list(objects.children()):
            if migration.child_value(entry, "oS") == "morass" and (
                layer.name,
                entry.name,
            ) not in selected:
                migration.remove_child(objects, entry.name)


def write_variant(name: str, selected: set[tuple[str, str]]) -> dict[str, object]:
    image = round3.full_morass_image()
    keep_instances(image, selected)
    root = DESTINATION / name
    client = root / f"Client/Data/Map/Map/Map4/{MAP_ID}.img"
    server = root / f"Server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    migration.atomic_write_bytes(
        client, migration.encode_image_body(image, migration.gms_reader())
    )
    migration.atomic_write_text(server, migration.image_to_xml(image, f"{MAP_ID}.img"))

    written = migration.load_image(client, migration.GMS_KEY)
    objects = [
        (layer.name, entry)
        for layer in written.root.children()
        if layer.name.isdigit()
        for entry in layer.child("obj").children()
    ]
    connect = [entry for _, entry in objects if migration.child_value(entry, "oS") == "connect"]
    morass = {(layer, entry.name): entry for layer, entry in objects if migration.child_value(entry, "oS") == "morass"}
    if len(connect) != 6 or set(morass) != selected or len(objects) != 6 + len(selected):
        raise RuntimeError(
            f"{name}: expected 6 connect and Morass instances {selected}, "
            f"got {len(connect)} connect and {set(morass)}"
        )
    for key, entry in morass.items():
        actual = (
            migration.child_value(entry, "x"),
            migration.child_value(entry, "y"),
            migration.child_value(entry, "zM"),
        )
        if migration.child_value(entry, "l1") != "foothold_Bridge" or migration.child_value(entry, "l2") != "0" or actual != EXPECTED[key]:
            raise RuntimeError(f"{name}: unexpected instance {key}: {actual}")
    expected_xml = migration.image_to_xml(written, f"{MAP_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError(f"{name}: client and server trees differ")
    return {
        "client": sha256(client),
        "server": sha256(server),
        "objects": len(objects),
        "instances": sorted(selected),
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
        raise RuntimeError("tenth-round package is missing; generate it before installing")
    client = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
    server = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    label = "A" if name.startswith("A_") else "B"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = Path(f"/private/tmp/arcane-river-{MAP_ID}-before-AB10-{label}-{timestamp}")
    for path in (client, server):
        backup = backup_root / path.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    migration.atomic_write_bytes(client, generated_client.read_bytes())
    migration.atomic_write_text(server, generated_server.read_text(encoding="utf-8-sig"))
    if sha256(client) != sha256(generated_client):
        raise RuntimeError(f"installed tenth-round {label} client differs from package")
    image = migration.load_image(client, migration.GMS_KEY)
    expected_xml = migration.image_to_xml(image, f"{MAP_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError(f"installed tenth-round {label} server differs from client")
    return backup_root


def write_readme(a: dict[str, object], b: dict[str, object]) -> None:
    text = f"""# 450006130 崩溃 AB 测试（第十轮）

第九轮 A 仅包含 3 个 `foothold_Bridge/l2=0` 实例，仍然黑屏高负载。
三个实例引用完全相同的资源节点，本轮只按地图实例拆分。两版均保留完整背景、
NPC、life、小地图、BGM 和 6 个 `connect` 对象。

## A_单实例_1_40

- 仅保留 `layer=1, entry=40`：`x=-2369, y=-614, zM=69`。
- Client SHA256：`{a['client']}`
- Server SHA256：`{a['server']}`

## B_双实例_1_21_3_5

- 保留 `layer=1, entry=21` 和 `layer=3, entry=5`。
- Client SHA256：`{b['client']}`
- Server SHA256：`{b['server']}`

## 结果判断

- A 异常：单个 `l2=0` 实例即可触发，根因偏向资源分支本身。
- A 正常、B 异常：问题在另两个位置之一或双实例组合，继续拆 B。
- A、B 都正常：需要至少三个实例组合才触发。
"""
    migration.atomic_write_text(DESTINATION / "README_测试顺序.md", text)


def build() -> tuple[dict[str, object], dict[str, object]]:
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    a = write_variant("A_单实例_1_40", GROUP_A)
    b = write_variant("B_双实例_1_21_3_5", GROUP_B)
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
        name = "A_单实例_1_40" if args.install_a else "B_双实例_1_21_3_5"
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
