#!/usr/bin/env python3
"""Contract checks for the legacy Chu Chu Village skyWhale projection."""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))
sys.path.insert(0, str(ROOT / "tool/scripts/patch-client"))

from wzpy import WzImage, WzKey, WzSubProperty  # noqa: E402

import migrate_arcane_river_fields as migration  # noqa: E402
from repair_arcane_river_cave_portals import (  # noqa: E402
    locate_extended_children,
    locate_root,
    record_bytes,
)


MAP_ID = 450002000
CLIENT = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
SERVER = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
EXPECTED = {
    "skyWhaleLift": (14, 3, 2475, -421, 450002000, "out04"),
}
EXPECTED_ADDITIONAL_RECORDS = ("14", "6", "3")
KEY = WzKey.for_region("GMS")


def git_baseline(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def portal_records(data: bytes):
    roots = locate_root(data)
    portal = next(record for record in roots.records if record.name == "portal")
    return roots, portal, locate_extended_children(data, portal)


def main() -> int:
    assert migration.LEGACY_CHUCHU_SKY_WHALE_PORTALS == {MAP_ID: EXPECTED}
    data = CLIENT.read_bytes()
    image = WzImage.from_bytes(data, key=KEY, name=CLIENT.name)
    image.parse()
    assert not image.truncated and image.parse_warnings == []
    portals = image.root.child("portal")
    assert isinstance(portals, WzSubProperty)
    by_name = {migration.child_value(node, "pn"): node for node in portals.children()}
    for name, (_, portal_type, x, y, target_map, target_name) in EXPECTED.items():
        entry = by_name[name]
        assert migration.child_value(entry, "pt") == portal_type
        assert migration.child_value(entry, "x") == x
        assert migration.child_value(entry, "y") == y
        assert migration.child_value(entry, "tm") == target_map
        assert migration.child_value(entry, "tn") == target_name
        assert entry.child("script") is None
    assert "skyWhaleTop" not in by_name
    assert migration.child_value(by_name["out04"], "x") == 2482
    assert migration.child_value(by_name["out04"], "y") == -950

    baseline = git_baseline(CLIENT)
    old_roots, _, old_portals = portal_records(baseline)
    new_roots, _, new_portals = portal_records(data)
    old_root_raw = record_bytes(baseline, old_roots.records)
    new_root_raw = record_bytes(data, new_roots.records)
    for name, raw in old_root_raw.items():
        if name != "portal":
            assert new_root_raw[name] == raw, name
    new_portal_raw = record_bytes(data, new_portals.records)
    for name, raw in record_bytes(baseline, old_portals.records).items():
        assert new_portal_raw[name] == raw, f"portal/{name}"
    assert tuple(record.name for record in new_portals.records) == (
        *(record.name for record in old_portals.records), *EXPECTED_ADDITIONAL_RECORDS
    )

    root = ET.parse(SERVER).getroot()
    xml_entries = {
        node.find('./string[@name="pn"]').get("value"): node
        for node in root.findall('./imgdir[@name="portal"]/imgdir')
        if node.find('./string[@name="pn"]') is not None
    }
    for name, (_, portal_type, x, y, target_map, target_name) in EXPECTED.items():
        entry = xml_entries[name]
        values = {node.get("name"): node.get("value") for node in entry}
        assert values == {
            "pn": name, "pt": str(portal_type), "x": str(x), "y": str(y),
            "tm": str(target_map), "tn": target_name,
        }

    print(
        "Chu Chu skyWhale contract ok: "
        "(2475,-421) --touch--> out04(2482,-950)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
