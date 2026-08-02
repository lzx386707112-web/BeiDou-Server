#!/usr/bin/env python3
"""Build the third crash-isolation round for Morass town map 450006130."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MAP_ID = 450006130
SOURCE = Path(
    "/private/tmp/arcane-river-morass-town-backup/"
    "clien/Data/Map/Map/Map4/450006130.img"
)
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/AB测试_450006130_第三轮")
EXPECTED_SOURCE_SHA256 = "215a831711ead57bc7733ed2e5d75c28adc157d2d8ddeb2c2ba3571aa11639a8"
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_fields as migration  # noqa: E402
from wzpy import WzSubProperty  # noqa: E402


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def full_morass_image():
    image = migration.load_image(SOURCE, migration.GMS_KEY)
    migration.set_int(image.root.child("info"), "fieldLimit", 0)
    for entry in image.root.child("life").children():
        for name in migration.LIFE_UNSUPPORTED_BY_MAP[MAP_ID]:
            migration.remove_child(entry, name)
    for node, _ in migration.walk(image.root.child("foothold")):
        if not isinstance(node, WzSubProperty):
            continue
        for name in migration.FOOTHOLD_UNSUPPORTED_BY_MAP[MAP_ID]:
            migration.remove_child(node, name)
    encoded = migration.encode_image_body(image, migration.gms_reader())
    actual = sha256_bytes(encoded)
    if actual != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(f"rebuilt Morass source hash changed: {actual}")
    return image


def clear(node, path: str) -> None:
    if not isinstance(node, WzSubProperty):
        raise RuntimeError(f"missing subproperty: {path}")
    node._children.clear()


def remove_life_and_reactors(image) -> None:
    clear(image.root.child("life"), "life")
    clear(image.root.child("reactor"), "reactor")


def keep_objects_only(image) -> None:
    remove_life_and_reactors(image)
    clear(image.root.child("back"), "back")
    migration.remove_child(image.root, "miniMap")
    info = image.root.child("info")
    migration.remove_child(info, "bgm")
    migration.remove_child(info, "mapMark")


def keep_background_only(image) -> None:
    remove_life_and_reactors(image)
    for layer in image.root.children():
        if not layer.name.isdigit():
            continue
        clear(layer.child("obj"), f"{layer.name}/obj")
        clear(layer.child("tile"), f"{layer.name}/tile")
        layer_info = layer.child("info")
        migration.remove_child(layer_info, "tS")
        migration.remove_child(layer_info, "tSMag")


def copy_dependencies(variant: str, dependencies: dict[str, set[str]]) -> None:
    target_root = DESTINATION / variant / "Client/Data"
    for category, names in dependencies.items():
        for name in names:
            source = ROOT / f"clien/Data/{category}/{name}.img"
            target = target_root / category / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def write_variant(variant: str, mutate, dependencies: dict[str, set[str]]) -> dict[str, object]:
    image = full_morass_image()
    mutate(image)
    root = DESTINATION / variant
    client = root / f"Client/Data/Map/Map/Map4/{MAP_ID}.img"
    server = root / f"Server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    migration.atomic_write_bytes(
        client, migration.encode_image_body(image, migration.gms_reader())
    )
    migration.atomic_write_text(server, migration.image_to_xml(image, f"{MAP_ID}.img"))
    copy_dependencies(variant, dependencies)

    written = migration.load_image(client, migration.GMS_KEY)
    layers = [node for node in written.root.children() if node.name.isdigit()]
    result = {
        "client": sha256(client),
        "server": sha256(server),
        "life": len(written.root.child("life").children()),
        "obj": sum(len(layer.child("obj").children()) for layer in layers),
        "tile": sum(len(layer.child("tile").children()) for layer in layers),
        "back": len(written.root.child("back").children()),
        "miniMap": written.root.child("miniMap") is not None,
        "bgm": written.root.child("info").child("bgm") is not None,
    }
    expected_xml = migration.image_to_xml(written, f"{MAP_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError(f"{variant}: client and server trees differ")
    return result


def verify_split(a: dict[str, object], b: dict[str, object]) -> None:
    expected_a = {"life": 0, "obj": 103, "tile": 0, "back": 0, "miniMap": False, "bgm": False}
    expected_b = {"life": 0, "obj": 0, "tile": 0, "back": 27, "miniMap": True, "bgm": True}
    for name, actual, expected in (("A", a, expected_a), ("B", b, expected_b)):
        mismatches = {
            key: (actual[key], value)
            for key, value in expected.items()
            if actual[key] != value
        }
        if mismatches:
            raise RuntimeError(f"{name} split verification failed: {mismatches}")


def write_readme(a: dict[str, object], b: dict[str, object]) -> None:
    text = f"""# 450006130 崩溃 AB 测试（第三轮）

第二轮 B 纯骨架实机不崩，证明 info、foothold、portal、ladderRope 兼容。
第一轮无 life 版本仍崩，因此本轮只二分渲染资源。

每版必须独立覆盖客户端和服务端文件，重新打完整 `Map.wz`，重启服务端后测试。

## A_仅对象层

- 保留 103 个 obj；本图 tile 原本为 0。
- 清空 back、life、reactor，删除 miniMap、bgm、mapMark。
- 附带 `Map/Obj/morass.img` 与 `Map/Obj/connect.img`。
- Client SHA256：`{a['client']}`
- Server SHA256：`{a['server']}`

## B_仅背景媒体

- 保留 27 个 back、miniMap、bgm、mapMark。
- 清空全部 obj、tile、life、reactor。
- 附带 `Map/Back/morass.img`、`Map/MapHelper.img` 与 `Sound/Bgm48.img`。
- Client SHA256：`{b['client']}`
- Server SHA256：`{b['server']}`

## 结果判断

- A 崩、B 正常：问题在 103 个 obj 或 `Obj/morass.img`/`Obj/connect.img`。
- A 正常、B 崩：问题在 back、miniMap、bgm 或 mapMark。
- A、B 都正常：两组渲染资源存在组合问题，再做组合验证。
- A、B 都崩：两组各自都有问题，分别继续二分。
"""
    migration.atomic_write_text(DESTINATION / "README_测试顺序.md", text)


def install_a() -> Path:
    generated_root = DESTINATION / "A_仅对象层"
    generated_client = generated_root / f"Client/Data/Map/Map/Map4/{MAP_ID}.img"
    generated_server = generated_root / f"Server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    if not generated_client.exists() or not generated_server.exists():
        raise RuntimeError("third-round A package is missing; regenerate it before installing")

    client = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
    server = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = Path(f"/private/tmp/arcane-river-{MAP_ID}-before-AB3-A-{timestamp}")
    for path in (client, server):
        backup = backup_root / path.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)

    migration.atomic_write_bytes(client, generated_client.read_bytes())
    migration.atomic_write_text(server, generated_server.read_text(encoding="utf-8-sig"))
    if sha256(client) != sha256(generated_client):
        raise RuntimeError("installed client does not match third-round A")
    image = migration.load_image(client, migration.GMS_KEY)
    expected_xml = migration.image_to_xml(image, f"{MAP_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError("installed server XML differs from the client tree")
    return backup_root


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--install-a",
        action="store_true",
        help="install the third-round object-only A variant into the project",
    )
    args = parser.parse_args()
    if args.install_a:
        backup_root = install_a()
        client = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
        print(f"installed AB3 A: sha256={sha256(client)} backup={backup_root}")
        return 0

    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    a = write_variant(
        "A_仅对象层",
        keep_objects_only,
        {"Map/Obj": {"morass", "connect"}},
    )
    b = write_variant(
        "B_仅背景媒体",
        keep_background_only,
        {"Map/Back": {"morass"}, "Map": {"MapHelper"}, "Sound": {"Bgm48"}},
    )
    verify_split(a, b)
    write_readme(a, b)
    print(f"A: {a}")
    print(f"B: {b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
