#!/usr/bin/env python3
"""Split the failing eighth-round A group into l2=0 and l2=1."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MAP_ID = 450006130
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/AB测试_450006130_第九轮")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import build_arcane_river_450006130_ab8 as round8  # noqa: E402
import migrate_arcane_river_fields as migration  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output_paths(name: str) -> tuple[Path, Path]:
    root = DESTINATION / name
    return (
        root / f"Client/Data/Map/Map/Map4/{MAP_ID}.img",
        root / f"Server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml",
    )


def install(name: str) -> Path:
    generated_client, generated_server = output_paths(name)
    if not generated_client.exists() or not generated_server.exists():
        raise RuntimeError("ninth-round package is missing; generate it before installing")
    client = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
    server = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    label = "A" if name.startswith("A_") else "B"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = Path(f"/private/tmp/arcane-river-{MAP_ID}-before-AB9-{label}-{timestamp}")
    for path in (client, server):
        backup = backup_root / path.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    migration.atomic_write_bytes(client, generated_client.read_bytes())
    migration.atomic_write_text(server, generated_server.read_text(encoding="utf-8-sig"))
    if sha256(client) != sha256(generated_client):
        raise RuntimeError(f"installed ninth-round {label} client differs from package")
    image = migration.load_image(client, migration.GMS_KEY)
    expected_xml = migration.image_to_xml(image, f"{MAP_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError(f"installed ninth-round {label} server differs from client")
    return backup_root


def write_readme(a: dict[str, object], b: dict[str, object]) -> None:
    text = f"""# 450006130 崩溃 AB 测试（第九轮）

第八轮 A（`l2=0/1`）实机黑屏并持续高负载。逐节点审计未发现非法类型、
损坏 Canvas、异常 foothold 点或固定 foothold 断链，因此继续做单变量拆分。
两版均保留完整背景、NPC、life、小地图、BGM 和 6 个 `connect` 对象。

## A_仅l2_0

- 6 个 `connect` + 3 个 `foothold_Bridge/l2=0`，共 9 个对象。
- Client SHA256：`{a['client']}`
- Server SHA256：`{a['server']}`

## B_仅l2_1

- 6 个 `connect` + 5 个 `foothold_Bridge/l2=1`，共 11 个对象。
- Client SHA256：`{b['client']}`
- Server SHA256：`{b['server']}`

## 结果判断

- A 异常、B 正常：触发范围为 `l2=0` 的 3 个实例。
- A 正常、B 异常：触发范围为 `l2=1` 的 5 个实例。
- A、B 都正常：`l2=0` 与 `l2=1` 存在组合触发条件。
- A、B 都异常：两个资源分支各自都能触发。
"""
    migration.atomic_write_text(DESTINATION / "README_测试顺序.md", text)


def build() -> tuple[dict[str, object], dict[str, object]]:
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    round8.DESTINATION = DESTINATION
    a = round8.write_variant("A_仅l2_0", {"0"})
    b = round8.write_variant("B_仅l2_1", {"1"})
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
        name = "A_仅l2_0" if args.install_a else "B_仅l2_1"
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
