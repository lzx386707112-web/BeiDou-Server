#!/usr/bin/env python3
"""Delete field 450006140 and connect 450006130 directly to 450006150."""

from __future__ import annotations

import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REMOVED_MAP_ID = 450006140
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/450006140_已删除_双向跳过")
CLIENT_TEMPLATE = "clien/Data/Map/Map/Map4/{map_id}.img"
SERVER_TEMPLATE = "gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"

sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_fields as migration  # noqa: E402


def project_paths(map_id: int) -> tuple[Path, Path]:
    return (
        ROOT / CLIENT_TEMPLATE.format(map_id=map_id),
        ROOT / SERVER_TEMPLATE.format(map_id=map_id),
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def portal(image, name: str):
    matches = [
        entry
        for entry in image.root.child("portal").children()
        if migration.child_value(entry, "pn") == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one portal named {name}, found {len(matches)}")
    return matches[0]


def set_destination(entry, map_id: int, portal_name: str) -> None:
    migration.set_int(entry, "tm", map_id)
    migration.set_string(entry, "tn", portal_name)


def verify_map(map_id: int, portal_name: str, target_id: int, target_portal: str) -> None:
    client, server = project_paths(map_id)
    image = migration.load_image(client, migration.GMS_KEY)
    entry = portal(image, portal_name)
    actual = (
        migration.child_value(entry, "tm"),
        migration.child_value(entry, "tn"),
    )
    if actual != (target_id, target_portal):
        raise RuntimeError(f"{map_id}/{portal_name}={actual}")
    if server.read_text(encoding="utf-8-sig") != migration.image_to_xml(
        image, f"{map_id}.img"
    ):
        raise RuntimeError(f"{map_id}: client and server trees differ")


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = Path(f"/private/tmp/arcane-river-{REMOVED_MAP_ID}-before-bypass-{timestamp}")
    affected = [path for map_id in (450006130, 450006140, 450006150) for path in project_paths(map_id)]
    for path in affected:
        if not path.exists():
            raise RuntimeError(f"missing expected input: {path}")
        backup = backup_root / path.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)

    changes = (
        (450006130, "east00", 450006150, "west00"),
        (450006150, "west00", 450006130, "east00"),
    )
    for map_id, portal_name, target_id, target_portal in changes:
        client, server = project_paths(map_id)
        image = migration.load_image(client, migration.GMS_KEY)
        entry = portal(image, portal_name)
        set_destination(entry, target_id, target_portal)
        migration.atomic_write_bytes(
            client, migration.encode_image_body(image, migration.gms_reader())
        )
        migration.atomic_write_text(server, migration.image_to_xml(image, f"{map_id}.img"))

    removed_client, removed_server = project_paths(REMOVED_MAP_ID)
    removed_client.unlink()
    removed_server.unlink()

    verify_map(450006130, "east00", 450006150, "west00")
    verify_map(450006150, "west00", 450006130, "east00")
    if removed_client.exists() or removed_server.exists():
        raise RuntimeError("450006140 still exists after deletion")

    for map_id in (450006130, 450006150):
        client, server = project_paths(map_id)
        package_client = DESTINATION / f"Client/Data/Map/Map/Map4/{map_id}.img"
        package_server = DESTINATION / f"Server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
        migration.atomic_write_bytes(package_client, client.read_bytes())
        migration.atomic_write_text(package_server, server.read_text(encoding="utf-8-sig"))

    delete_manifest = f"""请从完整项目中删除以下两个文件后再重新打包 Map.wz：

Client/Data/Map/Map/Map4/{REMOVED_MAP_ID}.img
Server/wz/Map.wz/Map/Map4/{REMOVED_MAP_ID}.img.xml
"""
    migration.atomic_write_text(DESTINATION / "DELETE.txt", delete_manifest)
    readme = f"""# 删除 450006140 并双向跳过

- `450006130/east00` 现在进入 `450006150/west00`。
- `450006150/west00` 现在返回 `450006130/east00`。
- 项目中的 `450006140` 客户端 IMG 与服务端 XML 已删除。
- 删除前临时备份：`{backup_root}`
- 450006130 Client SHA256：`{sha256(project_paths(450006130)[0])}`
- 450006150 Client SHA256：`{sha256(project_paths(450006150)[0])}`
"""
    migration.atomic_write_text(DESTINATION / "README.md", readme)
    print(f"450006140 deleted and bypassed; backup={backup_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
