#!/usr/bin/env python3
"""Build the second crash-isolation round for map 450006130."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TARGET_MAP_ID = 450006130
CONTROL_MAP_ID = 450005000
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/AB测试_450006130_第二轮")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_fields as migration  # noqa: E402
from wzpy import WzSubProperty  # noqa: E402


def output_paths(variant: str) -> tuple[Path, Path]:
    root = DESTINATION / variant
    client = root / f"Client/Data/Map/Map/Map4/{TARGET_MAP_ID}.img"
    server = root / f"Server/wz/Map.wz/Map/Map4/{TARGET_MAP_ID}.img.xml"
    return client, server


def write_control() -> tuple[str, str]:
    variant = "A_正常城镇对照"
    source = ROOT / f"clien/Data/Map/Map/Map4/{CONTROL_MAP_ID}.img"
    client, server = output_paths(variant)
    client.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, client)

    image = migration.load_image(client, migration.GMS_KEY)
    migration.atomic_write_text(
        server, migration.image_to_xml(image, f"{TARGET_MAP_ID}.img")
    )

    dependencies = {
        "Obj": {"arcana", "connect"},
        "Tile": {"arcana1"},
        "Back": {"arcana2"},
    }
    variant_root = DESTINATION / variant / "Client/Data/Map"
    for category, names in dependencies.items():
        for name in names:
            dependency = ROOT / f"clien/Data/Map/{category}/{name}.img"
            target = variant_root / category / dependency.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dependency, target)

    return sha256(client), sha256(server)


def install_control() -> Path:
    source = ROOT / f"clien/Data/Map/Map/Map4/{CONTROL_MAP_ID}.img"
    client = ROOT / f"clien/Data/Map/Map/Map4/{TARGET_MAP_ID}.img"
    server = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{TARGET_MAP_ID}.img.xml"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = Path(f"/private/tmp/arcane-river-{TARGET_MAP_ID}-before-A-{timestamp}")

    for path in (client, server):
        backup = backup_root / path.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)

    migration.atomic_write_bytes(client, source.read_bytes())
    image = migration.load_image(client, migration.GMS_KEY)
    migration.atomic_write_text(
        server, migration.image_to_xml(image, f"{TARGET_MAP_ID}.img")
    )

    if sha256(client) != sha256(source):
        raise RuntimeError("installed A client does not match the control map")
    expected_xml = migration.image_to_xml(image, f"{TARGET_MAP_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError("installed A server XML differs from the client tree")
    return backup_root


def install_skeleton() -> Path:
    generated_client, generated_server = output_paths("B_莫拉斯纯骨架")
    if not generated_client.exists() or not generated_server.exists():
        raise RuntimeError("B package is missing; regenerate round two before installing B")

    client = ROOT / f"clien/Data/Map/Map/Map4/{TARGET_MAP_ID}.img"
    server = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{TARGET_MAP_ID}.img.xml"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = Path(f"/private/tmp/arcane-river-{TARGET_MAP_ID}-before-B-{timestamp}")
    for path in (client, server):
        backup = backup_root / path.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)

    migration.atomic_write_bytes(client, generated_client.read_bytes())
    migration.atomic_write_text(
        server, generated_server.read_text(encoding="utf-8-sig")
    )

    if sha256(client) != sha256(generated_client):
        raise RuntimeError("installed B client does not match the generated skeleton")
    image = migration.load_image(client, migration.GMS_KEY)
    portal_count = len(image.root.child("portal").children())
    foothold_groups = len(image.root.child("foothold").children())
    verify_skeleton(image, server, portal_count, foothold_groups)
    return backup_root


def clear_subproperty(node, path: str) -> None:
    if not isinstance(node, WzSubProperty):
        raise RuntimeError(f"missing subproperty: {path}")
    node._children.clear()


def write_skeleton() -> tuple[str, str, int, int]:
    variant = "B_莫拉斯纯骨架"
    source = ROOT / f"clien/Data/Map/Map/Map4/{TARGET_MAP_ID}.img"
    image = migration.load_image(source, migration.GMS_KEY)

    clear_subproperty(image.root.child("back"), "back")
    clear_subproperty(image.root.child("life"), "life")
    clear_subproperty(image.root.child("reactor"), "reactor")
    for layer in image.root.children():
        if not layer.name.isdigit():
            continue
        clear_subproperty(layer.child("obj"), f"{layer.name}/obj")
        clear_subproperty(layer.child("tile"), f"{layer.name}/tile")
        info = layer.child("info")
        migration.remove_child(info, "tS")
        migration.remove_child(info, "tSMag")

    migration.remove_child(image.root, "miniMap")
    info = image.root.child("info")
    migration.remove_child(info, "bgm")
    migration.remove_child(info, "mapMark")

    client, server = output_paths(variant)
    migration.atomic_write_bytes(
        client, migration.encode_image_body(image, migration.gms_reader())
    )
    migration.atomic_write_text(
        server, migration.image_to_xml(image, f"{TARGET_MAP_ID}.img")
    )

    written = migration.load_image(client, migration.GMS_KEY)
    portal_count = len(written.root.child("portal").children())
    foothold_groups = len(written.root.child("foothold").children())
    verify_skeleton(written, server, portal_count, foothold_groups)
    return sha256(client), sha256(server), portal_count, foothold_groups


def verify_skeleton(image, server: Path, portal_count: int, foothold_groups: int) -> None:
    for name in ("back", "life", "reactor"):
        node = image.root.child(name)
        if not isinstance(node, WzSubProperty) or node.children():
            raise RuntimeError(f"skeleton still contains {name} entries")
    for layer in image.root.children():
        if not layer.name.isdigit():
            continue
        if layer.child("obj").children() or layer.child("tile").children():
            raise RuntimeError(f"skeleton layer {layer.name} is not empty")
    if image.root.child("miniMap") is not None:
        raise RuntimeError("skeleton still contains miniMap")
    info = image.root.child("info")
    if info.child("bgm") is not None or info.child("mapMark") is not None:
        raise RuntimeError("skeleton still contains media references")
    if portal_count != 17 or foothold_groups != 4:
        raise RuntimeError(
            f"core geometry changed: portals={portal_count}, foothold_groups={foothold_groups}"
        )
    expected_xml = migration.image_to_xml(image, f"{TARGET_MAP_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError("client and server skeleton trees differ")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_readme(control: tuple[str, str], skeleton: tuple[str, str, int, int]) -> None:
    text = f"""# 450006130 崩溃 AB 测试（第二轮）

第一轮 A、B 都崩溃，说明 `life` 和 5 组独占 Morass 对象都不是单独根因。
本轮测试地图内容边界，不修改正式项目文件。

每版必须独立覆盖客户端和服务端文件，重新打完整 `Map.wz`，重启服务端后测试。
不要把 A、B 两版叠加。

## A_正常城镇对照

- 将已确认可进入的 `450005000` 地图内容原样放到 `450006130.img`。
- 服务端 XML 由同一客户端 IMG 生成。
- 附带其 Map 资源：`Obj/arcana.img`、`Obj/connect.img`、
  `Tile/arcana1.img`、`Back/arcana2.img`。
- Client SHA256：`{control[0]}`
- Server SHA256：`{control[1]}`

## B_莫拉斯纯骨架

- 保留本图 `info`、17 个 portal、foothold、ladderRope 和 VR 边界。
- 清空全部 obj、tile、back、life、reactor。
- 删除 miniMap、bgm、mapMark，因此不再加载 Morass 渲染资源。
- foothold 一级分组：{skeleton[3]}
- Client SHA256：`{skeleton[0]}`
- Server SHA256：`{skeleton[1]}`

## 结果判断

- A、B 都崩：共同点只剩地图 ID/进入与打包链路，应检查实际 Map.wz 是否装入
  这两个测试 IMG、服务端是否加载对应 XML，不再修改地图节点。
- A 正常、B 崩：问题位于莫拉斯核心节点（info/foothold/portal/ladderRope）。
- A、B 都正常：问题位于本轮从 B 删除的渲染层，下一轮二分 back 与 obj/tile。
- A 崩、B 正常：对照图依赖或打包覆盖异常；同时复测原地图 450005000。
"""
    migration.atomic_write_text(DESTINATION / "README_测试顺序.md", text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--install-a",
        action="store_true",
        help="install the known-good control map into project map 450006130",
    )
    parser.add_argument(
        "--install-b",
        action="store_true",
        help="install the generated Morass skeleton into project map 450006130",
    )
    args = parser.parse_args()
    if args.install_a and args.install_b:
        parser.error("--install-a and --install-b are mutually exclusive")
    if args.install_a:
        backup_root = install_control()
        print(
            f"installed A: map={TARGET_MAP_ID} sha256="
            f"{sha256(ROOT / f'clien/Data/Map/Map/Map4/{TARGET_MAP_ID}.img')} "
            f"backup={backup_root}"
        )
        return 0
    if args.install_b:
        backup_root = install_skeleton()
        print(
            f"installed B: map={TARGET_MAP_ID} sha256="
            f"{sha256(ROOT / f'clien/Data/Map/Map/Map4/{TARGET_MAP_ID}.img')} "
            f"backup={backup_root}"
        )
        return 0

    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    control = write_control()
    skeleton = write_skeleton()
    write_readme(control, skeleton)
    print(
        f"A control client_sha256={control[0]} server_sha256={control[1]}"
    )
    print(
        "B skeleton "
        f"portals={skeleton[2]} foothold_groups={skeleton[3]} "
        f"client_sha256={skeleton[0]} server_sha256={skeleton[1]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
