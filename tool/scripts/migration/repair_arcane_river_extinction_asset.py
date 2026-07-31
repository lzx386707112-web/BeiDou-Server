#!/usr/bin/env python3
"""Isolate shared Vanishing Journey objects from the verified town resource."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/private/tmp/arcane-river-fields-backup/clien/Data/Map/Obj/extinction.img")
TARGET_NAME = "extinctionLegacy"
sys.path.insert(0, str(ROOT / "tool" / "scripts" / "migration"))

import migrate_arcane_river_fields as migration  # noqa: E402


def main() -> None:
    maps: dict[int, migration.WzImage] = {}
    references: dict[str, set[str]] = defaultdict(set)
    changed_objects = 0
    for map_id in migration.MAP_IDS:
        if map_id == 450001000:
            continue
        path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        image = migration.load_image(path, migration.GMS_KEY)
        changed = False
        for layer in [child for child in image.root.children() if child.name.isdigit()]:
            objects = layer.child("obj")
            if not isinstance(objects, migration.WzSubProperty):
                continue
            for entry in objects.children():
                if migration.child_value(entry, "oS") != "extinction":
                    continue
                category = str(migration.child_value(entry, "l1"))
                leaf = str(migration.child_value(entry, "l2"))
                references[category].add(leaf)
                migration.set_string(entry, "oS", TARGET_NAME)
                changed_objects += 1
                changed = True
        if changed:
            maps[map_id] = image

    resource = migration.load_image(SOURCE, migration.GMS_KEY)
    extinction = resource.root.child("extinction")
    if not isinstance(extinction, migration.WzSubProperty):
        raise RuntimeError("source Obj/extinction.img is missing extinction root")
    for category in list(extinction.children()):
        if category.name not in references:
            migration.remove_child(extinction, category.name)
            continue
        for leaf in list(category.children()):
            if leaf.name not in references[category.name]:
                migration.remove_child(category, leaf.name)
    for category, leaves in references.items():
        for leaf in leaves:
            if resource.root.get(f"extinction/{category}/{leaf}") is None:
                raise RuntimeError(f"missing source extinction/{category}/{leaf}")

    target = ROOT / f"clien/Data/Map/Obj/{TARGET_NAME}.img"
    migration.write_client_image(target, resource)
    for map_id, image in maps.items():
        client = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        server = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
        migration.write_client_image(client, image)
        migration.write_server_image(server, image, f"{map_id}.img")
    print(
        f"maps={len(maps)} objects={changed_objects} "
        f"branches={sum(len(leaves) for leaves in references.values())} target={target}"
    )


if __name__ == "__main__":
    main()
