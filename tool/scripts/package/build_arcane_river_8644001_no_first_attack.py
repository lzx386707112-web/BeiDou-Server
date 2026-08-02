#!/usr/bin/env python3
"""Build a single-variable firstAttack diagnostic for Arcana mob 8644001."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MOB_ID = 8644001
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/8644001_根因定位_仅关闭firstAttack")

sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_fields as migration  # noqa: E402
from wzpy import WzSubProperty  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(image) -> str:
    return "\n".join(
        migration.property_to_xml(child, 0) for child in image.root.children()
    )


def main() -> int:
    source = ROOT / f"clien/Data/Mob/{MOB_ID}.img"
    image = migration.load_image(source, migration.GMS_KEY)
    info = image.root.child("info")
    attack = image.root.child("attack1")
    if not isinstance(info, WzSubProperty) or info.child("firstAttack") is None:
        raise RuntimeError("mob is missing info/firstAttack")
    if not isinstance(attack, WzSubProperty):
        raise RuntimeError("mob is missing attack1")

    migration.remove_child(info, "firstAttack")
    expected_snapshot = snapshot(image)

    client = DESTINATION / f"Client/Data/Mob/{MOB_ID}.img"
    server = DESTINATION / f"Server/wz/Mob.wz/{MOB_ID}.img.xml"
    migration.atomic_write_bytes(
        client, migration.encode_image_body(image, migration.gms_reader())
    )
    migration.atomic_write_text(server, migration.image_to_xml(image, f"{MOB_ID}.img"))

    written = migration.load_image(client, migration.GMS_KEY)
    written_info = written.root.child("info")
    written_attack = written.root.child("attack1")
    if not isinstance(written_info, WzSubProperty) or written_info.child("firstAttack") is not None:
        raise RuntimeError("written mob still contains firstAttack")
    if not isinstance(written_attack, WzSubProperty):
        raise RuntimeError("written mob lost attack1")
    if snapshot(written) != expected_snapshot:
        raise RuntimeError("mob data outside info/firstAttack changed")
    expected_xml = migration.image_to_xml(written, f"{MOB_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError("server XML differs from the client mob tree")

    attack_info = written_attack.child("info")
    attack_frames = len([child for child in written_attack.children() if child.name.isdigit()])
    ball = attack_info.child("ball") if isinstance(attack_info, WzSubProperty) else None
    hit = attack_info.child("hit") if isinstance(attack_info, WzSubProperty) else None
    ball_frames = len(ball.children()) if isinstance(ball, WzSubProperty) else 0
    hit_frames = len(hit.children()) if isinstance(hit, WzSubProperty) else 0

    readme = f"""# {MOB_ID} 根因定位：仅关闭 firstAttack

本版本只移除客户端与服务端 `info/firstAttack`，完整保留 `attack1`、
{attack_frames} 个攻击主帧、{ball_frames} 个 ball 帧和 {hit_frames} 个 hit 帧。
它不是最终修复，用于区分“进图同时首攻”与“攻击动作资源”两个根因。

测试步骤：

1. 同时替换 Client 与 Server 文件，重新打包 `Mob.wz` 并重启服务端。
2. 使用原版地图进入 `450005120`，先原地等待 30 秒。
3. 若未黑屏，主动靠近或攻击怪物，直到观察到它执行远程攻击。

结果判断：

- 等待阶段黑屏：根因不在 `firstAttack`，停止修改攻击触发。
- 等待不黑、怪物第一次远程攻击时黑屏：根因确定在 `attack1` 运行路径。
- 怪物反复远程攻击仍不黑：根因是大量怪物进图同时首攻，而非攻击素材。

- 客户端 IMG SHA256：`{sha256(client)}`
- 服务端 XML SHA256：`{sha256(server)}`
- 原客户端 IMG SHA256：`{sha256(source)}`
"""
    migration.atomic_write_text(DESTINATION / "README_测试说明.md", readme)
    print(
        f"mob={MOB_ID} firstAttack=removed attack1=preserved "
        f"attack_frames={attack_frames} ball_frames={ball_frames} hit_frames={hit_frames}"
    )
    print(f"output={DESTINATION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
