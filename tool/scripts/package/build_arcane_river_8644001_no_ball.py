#!/usr/bin/env python3
"""Build the no-projectile compatibility repair for Arcana mob 8644001."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MOB_ID = 8644001
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/8644001_修复版_保留攻击去除ball")

sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_fields as migration  # noqa: E402
from wzpy import WzSubProperty  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image_snapshot(image) -> str:
    return "\n".join(
        migration.property_to_xml(child, 0) for child in image.root.children()
    )


def main() -> int:
    source = ROOT / f"clien/Data/Mob/{MOB_ID}.img"
    image = migration.load_image(source, migration.GMS_KEY)
    info = image.root.child("info")
    attack = image.root.child("attack1")
    attack_info = attack.child("info") if isinstance(attack, WzSubProperty) else None
    if not isinstance(info, WzSubProperty) or info.child("firstAttack") is None:
        raise RuntimeError("mob is missing info/firstAttack")
    if not isinstance(attack_info, WzSubProperty) or attack_info.child("ball") is None:
        raise RuntimeError("mob is missing attack1/info/ball")

    ball = attack_info.child("ball")
    ball_frames = len(ball.children()) if isinstance(ball, WzSubProperty) else 0
    if ball_frames != 3:
        raise RuntimeError(f"expected 3 ball frames, got {ball_frames}")
    migration.remove_child(attack_info, "ball")
    expected_snapshot = image_snapshot(image)

    client = DESTINATION / f"Client/Data/Mob/{MOB_ID}.img"
    server = DESTINATION / f"Server/wz/Mob.wz/{MOB_ID}.img.xml"
    migration.atomic_write_bytes(
        client, migration.encode_image_body(image, migration.gms_reader())
    )
    migration.atomic_write_text(server, migration.image_to_xml(image, f"{MOB_ID}.img"))

    written = migration.load_image(client, migration.GMS_KEY)
    written_info = written.root.child("info")
    written_attack = written.root.child("attack1")
    written_attack_info = (
        written_attack.child("info") if isinstance(written_attack, WzSubProperty) else None
    )
    if not isinstance(written_info, WzSubProperty) or written_info.child("firstAttack") is None:
        raise RuntimeError("written mob lost firstAttack")
    if not isinstance(written_attack_info, WzSubProperty):
        raise RuntimeError("written mob lost attack1/info")
    if written_attack_info.child("ball") is not None:
        raise RuntimeError("written mob still contains attack1/info/ball")
    if image_snapshot(written) != expected_snapshot:
        raise RuntimeError("mob data outside attack1/info/ball changed")
    expected_xml = migration.image_to_xml(written, f"{MOB_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError("server XML differs from the client mob tree")

    attack_frames = len(
        [child for child in written_attack.children() if child.name.isdigit()]
    )
    hit = written_attack_info.child("hit")
    hit_frames = len(hit.children()) if isinstance(hit, WzSubProperty) else 0
    readme = f"""# {MOB_ID} 保留攻击修复版

本版本保留 `{MOB_ID}` 的原始外观和主动攻击，仅从客户端与服务端同步移除
`attack1/info/ball` 的 {ball_frames} 个投射物帧。旧端已有合法的
`sp+r + hit`、无 `ball` 攻击，因此攻击主动作和伤害流程仍可使用。

- `firstAttack` 保留。
- `attack1` 的 {attack_frames} 个主动作帧保留。
- `attack1/info/range`、{hit_frames} 个 hit 帧及 `attackAfter` 保留。
- 怪物 ID、属性、经验、掉落和任务关系不变。
- 客户端 IMG SHA256：`{sha256(client)}`
- 服务端 XML SHA256：`{sha256(server)}`
- 原客户端 IMG SHA256：`{sha256(source)}`

测试时同时替换 Client 与 Server 文件，重新打包 `Mob.wz` 并重启服务端，
然后使用原版地图测试 `450005120` 和 `450005131`。
"""
    migration.atomic_write_text(DESTINATION / "README_测试说明.md", readme)
    print(
        f"mob={MOB_ID} ball_frames=removed:{ball_frames} "
        f"attack_frames={attack_frames} hit_frames={hit_frames} "
        f"client_sha256={sha256(client)}"
    )
    print(f"output={DESTINATION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
