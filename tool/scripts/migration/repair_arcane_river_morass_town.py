#!/usr/bin/env python3
"""Apply the targeted old-client compatibility fix for Morass town."""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MAP_ID = 450006130
BACKUP_ROOT = Path("/private/tmp/arcane-river-morass-town-backup")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import migrate_arcane_river_fields as migration  # noqa: E402
from wzpy import WzIntProperty, WzSubProperty  # noqa: E402


def backup(path: Path) -> None:
    destination = BACKUP_ROOT / path.relative_to(ROOT)
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)


def patch() -> tuple[Path, Path, Path]:
    client = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
    server = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    asset = ROOT / "clien/Data/Map/Obj/morass.img"
    image = migration.load_image(client, migration.GMS_KEY)

    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{client}: missing info node")
    field_limit = info.child("fieldLimit")
    if not isinstance(field_limit, WzIntProperty):
        raise RuntimeError(f"{client}: missing integer info/fieldLimit")
    migration.set_int(info, "fieldLimit", 0)

    life = image.root.child("life")
    if not isinstance(life, WzSubProperty):
        raise RuntimeError(f"{client}: missing life node")
    for entry in life.children():
        for name in migration.LIFE_UNSUPPORTED_BY_MAP[MAP_ID]:
            migration.remove_child(entry, name)

    foothold = image.root.child("foothold")
    if not isinstance(foothold, WzSubProperty):
        raise RuntimeError(f"{client}: missing foothold node")
    for node, _ in migration.walk(foothold):
        if not isinstance(node, WzSubProperty):
            continue
        for name in migration.FOOTHOLD_UNSUPPORTED_BY_MAP[MAP_ID]:
            migration.remove_child(node, name)

    backup(client)
    backup(server)
    migration.write_client_image(client, image)
    migration.write_server_image(server, image, f"{MAP_ID}.img")
    asset_image = migration.load_image(asset, migration.GMS_KEY)
    migration.normalize_legacy_asset_structure(asset_image, "Obj", "morass")
    backup(asset)
    migration.write_client_image(asset, asset_image)
    return client, server, asset


def verify(client: Path, server: Path, asset: Path) -> None:
    image = migration.load_image(client, migration.GMS_KEY)
    if migration.child_value(image.root.child("info"), "fieldLimit") != 0:
        raise RuntimeError("client info/fieldLimit verification failed")
    for entry in image.root.child("life").children():
        remaining = migration.LIFE_UNSUPPORTED_BY_MAP[MAP_ID] & {
            child.name for child in entry.children()
        }
        if remaining:
            raise RuntimeError(f"client life/{entry.name} still contains {sorted(remaining)}")
    foothold = image.root.child("foothold")
    remaining_foothold = [
        path
        for node, path in migration.walk(foothold)
        if migration.FOOTHOLD_UNSUPPORTED_BY_MAP[MAP_ID]
        & {child.name for child in node.children()}
    ]
    if remaining_foothold:
        raise RuntimeError(f"client foothold still contains modern fields: {remaining_foothold}")
    expected = migration.image_to_xml(image, f"{MAP_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected:
        raise RuntimeError("client and server map trees differ")
    asset_image = migration.load_image(asset, migration.GMS_KEY)
    errors = migration.legacy_asset_structure_errors(asset_image, "Obj", "morass")
    if errors:
        raise RuntimeError(f"morass asset structure verification failed: {errors}")


def main() -> int:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    client, server, asset = patch()
    verify(client, server, asset)
    map_digest = hashlib.sha256(client.read_bytes()).hexdigest()
    asset_digest = hashlib.sha256(asset.read_bytes()).hexdigest()
    print(
        f"Morass town compatibility repaired: map={MAP_ID}, "
        f"map_sha256={map_digest}, morass_sha256={asset_digest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
