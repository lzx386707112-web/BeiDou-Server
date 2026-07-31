#!/usr/bin/env python3
"""Replace modern Arcane River connect/portal nodes with legacy client forms."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "scripts" / "migration"))

import migrate_arcane_river_fields as migration  # noqa: E402


def count_piece_nodes(image) -> int:
    ladder_rope = image.root.child("ladderRope")
    if not isinstance(ladder_rope, migration.WzSubProperty):
        return 0
    return sum(entry.child("piece") is not None for entry in ladder_rope.children())


def main() -> None:
    totals = {
        "maps": 0,
        "removed": 0,
        "generated": 0,
        "collisions": 0,
        "decorative": 0,
        "pieces": 0,
        "portals": 0,
    }
    changed_maps: list[int] = []
    for map_id in migration.MAP_IDS:
        client = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        image = migration.load_image(client, migration.GMS_KEY)
        pieces = count_piece_nodes(image)
        connect = migration.downgrade_connect_nodes(image.root)
        reordered = (
            migration.normalize_connect_object_order(image.root)
            if map_id in migration.LEGACY_CONNECT_FIRST_MAPS
            else 0
        )
        portals = migration.downgrade_portal_types(image.root)
        changed = bool(connect["removed"] or connect["generated"] or pieces or reordered or portals)
        if not changed:
            continue
        migration.write_client_image(client, image)
        server = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
        migration.write_server_image(server, image, f"{map_id}.img")
        changed_maps.append(map_id)
        totals["maps"] += 1
        totals["pieces"] += pieces
        totals["portals"] += portals
        for name in ("removed", "generated", "collisions", "decorative"):
            totals[name] += connect[name]
    print("changed maps", len(changed_maps), changed_maps)
    print("totals", totals)


if __name__ == "__main__":
    main()
