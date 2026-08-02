#!/usr/bin/env python3
"""Build the legacy-safe no-ranged-attack repair for Arcana mob 8644001."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MOB_ID = 8644001
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/8644001_修复版_禁用主动攻击")

sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_fields as migration  # noqa: E402
from wzpy import WzSubProperty  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def xml_snapshot(image, excluded: set[str]) -> str:
    return "\n".join(
        migration.property_to_xml(child, 0)
        for child in image.root.children()
        if child.name not in excluded
    )


def main() -> int:
    source = ROOT / f"clien/Data/Mob/{MOB_ID}.img"
    image = migration.load_image(source, migration.GMS_KEY)
    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError("mob has no info node")
    if info.child("firstAttack") is None or image.root.child("attack1") is None:
        raise RuntimeError("expected firstAttack and attack1 in source mob")

    migration.remove_child(info, "firstAttack")
    migration.remove_child(image.root, "attack1")
    expected_snapshot = xml_snapshot(image, set())

    client = DESTINATION / f"Client/Data/Mob/{MOB_ID}.img"
    server = DESTINATION / f"Server/wz/Mob.wz/{MOB_ID}.img.xml"
    migration.atomic_write_bytes(
        client, migration.encode_image_body(image, migration.gms_reader())
    )
    migration.atomic_write_text(server, migration.image_to_xml(image, f"{MOB_ID}.img"))

    written = migration.load_image(client, migration.GMS_KEY)
    written_info = written.root.child("info")
    if not isinstance(written_info, WzSubProperty):
        raise RuntimeError("written mob has no info node")
    if written_info.child("firstAttack") is not None or written.root.child("attack1") is not None:
        raise RuntimeError("written mob still contains active attack nodes")
    if xml_snapshot(written, set()) != expected_snapshot:
        raise RuntimeError("mob data outside firstAttack/attack1 changed")
    expected_xml = migration.image_to_xml(written, f"{MOB_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError("server XML differs from the client mob tree")

    actions = [child.name for child in written.root.children()]
    readme = f"""# {MOB_ID} 修复版

本版本保留 `{MOB_ID}` 的原始外观、站立、移动、受击和死亡动作，同时从
客户端和服务端移除会在怪物出现后触发黑屏的 `firstAttack` 与 `attack1`。
怪物仍保留 `bodyAttack=1`，可进行接触伤害。

- 怪物 ID、等级、血量、经验、掉落和任务关系不变。
- 不再使用 `{MOB_ID}` 的远程主动攻击。
- 客户端 IMG SHA256：`{sha256(client)}`
- 服务端 XML SHA256：`{sha256(server)}`
- 原客户端 IMG SHA256：`{sha256(source)}`
- 保留节点：`{', '.join(actions)}`

测试时同时替换 Client 与 Server 文件，重新打包 `Mob.wz` 并重启服务端，
然后使用原版地图测试 `450005120` 和 `450005131`。
"""
    migration.atomic_write_text(DESTINATION / "README_测试说明.md", readme)
    print(
        f"mob={MOB_ID} firstAttack=removed attack1=removed "
        f"actions={actions} client_sha256={sha256(client)}"
    )
    print(f"output={DESTINATION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
