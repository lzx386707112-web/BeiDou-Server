#!/usr/bin/env python3
"""Contract checks for legacy-visible Cave of Repose portals."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

from wzpy import WzImage, WzKey, WzSubProperty  # noqa: E402

import migrate_arcane_river_fields as migration  # noqa: E402


EXPECTED = {
    450001210: {"PS00": (450001215, "PV00")},
    450001215: {"PS00": (450001218, "PV00")},
    450001218: {"PS00": (450001219, "PV00")},
    450001219: {
        "PS00": (450001230, "PV00"),
        "PS01": (450001240, "PV00"),
    },
    450001230: {
        "PS00": (450001262, "PV00"),
        "PH00": (450001230, "PH01"),
        "PH01": (450001230, "PH00"),
    },
    450001240: {"PS00": (450001250, "PV00")},
    450001262: {"PV00": (450001230, "PS00")},
}
EXPECTED_COLLISION = {
    450001250: {"PCS00": (450002000, "sp")},
}
KEY = WzKey.for_region("GMS")


def client_portal(map_id: int, portal_name: str) -> WzSubProperty:
    path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
    image = WzImage.from_bytes(path.read_bytes(), key=KEY, name=path.name)
    image.parse()
    assert not image.truncated and image.parse_warnings == [], map_id
    portal = image.root.child("portal")
    assert isinstance(portal, WzSubProperty), map_id
    entry = next(
        (
            node for node in portal.children()
            if migration.child_value(node, "pn") == portal_name
        ),
        None,
    )
    assert isinstance(entry, WzSubProperty), (map_id, portal_name)
    return entry


def main() -> int:
    assert migration.LEGACY_CAVE_ROUTE_PORTALS == EXPECTED
    assert migration.LEGACY_CAVE_COLLISION_PORTALS == EXPECTED_COLLISION
    portal_sets = ((2, EXPECTED), (3, EXPECTED_COLLISION))
    for portal_type, portal_maps in portal_sets:
        for map_id, portals in portal_maps.items():
            xml = ET.parse(
                ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
            ).getroot()
            for portal_name, (target_map, target_name) in portals.items():
                entry = client_portal(map_id, portal_name)
                assert migration.child_value(entry, "pt") == portal_type
                assert migration.child_value(entry, "tm") == target_map
                assert migration.child_value(entry, "tn") == target_name
                assert entry.child("script") is None
                client_portal(target_map, target_name)

                xml_entry = next(
                    (
                        node for node in xml.findall('./imgdir[@name="portal"]/imgdir')
                        if node.find('./string[@name="pn"]') is not None
                        and node.find('./string[@name="pn"]').get("value") == portal_name
                    ),
                    None,
                )
                assert xml_entry is not None, (map_id, portal_name)
                assert xml_entry.find('./int[@name="pt"]').get("value") == str(portal_type)
                assert xml_entry.find('./int[@name="tm"]').get("value") == str(target_map)
                assert xml_entry.find('./string[@name="tn"]').get("value") == target_name
                assert xml_entry.find('./string[@name="script"]') is None
    for map_id in (450001210, 450001215, 450001218, 450001219, 450001230, 450001240, 450001250, 450001262):
        path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        image = WzImage.from_bytes(path.read_bytes(), key=KEY, name=path.name)
        image.parse()
        portal = image.root.child("portal")
        assert isinstance(portal, WzSubProperty), map_id
        for entry in portal.children():
            assert migration.child_value(entry, "pt") != 7, (map_id, entry.name)
            assert entry.child("script") is None, (map_id, entry.name)
    print(
        "Cave of Repose portal contract ok: "
        "450001210 -> 450001215 -> 450001218 -> 450001219 -> "
        "{450001230 [PH00 <-> PH01] <-> 450001262, "
        "450001240 -> 450001250 --fall--> 450002000}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
