#!/usr/bin/env python3
"""Contract checks for legacy-compatible Arcane River projectile attacks."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

from wzpy import WzImage, WzIntProperty, WzKey, WzSubProperty  # noqa: E402

import migrate_arcane_river_fields as migration  # noqa: E402


EXPECTED = {
    8641002: (1, 300),
    8642012: (2, 400),
    8642013: (2, 400),
    8642014: (2, 400),
    8642015: (2, 400),
    8642021: (2, 400),
    8642022: (2, 400),
    8642050: (1, 300),
    8644001: (1, 300),
    8644005: (1, 300),
    8644007: (2, 300),
    8644008: (1, 300),
    8644010: (1, 300),
}
INFO_ORDER = ("range", "ball", "hit", "type", "attackAfter", "bulletSpeed")
KEY = WzKey.for_region("GMS")


def main() -> int:
    assert migration.LEGACY_BALLISTIC_ATTACKS == EXPECTED
    for mob_id, (attack_number, bullet_speed) in EXPECTED.items():
        client_path = ROOT / f"clien/Data/Mob/{mob_id}.img"
        image = WzImage.from_bytes(client_path.read_bytes(), key=KEY, name=client_path.name)
        image.parse()
        assert not image.truncated and image.parse_warnings == [], mob_id
        info = image.root.get(f"attack{attack_number}/info")
        assert isinstance(info, WzSubProperty), mob_id
        assert tuple(child.name for child in info.children()) == INFO_ORDER, mob_id
        assert isinstance(info.child("ball"), WzSubProperty), mob_id
        attack_type = info.child("type")
        speed = info.child("bulletSpeed")
        assert isinstance(attack_type, WzIntProperty) and int(attack_type.value) == 2, mob_id
        assert isinstance(speed, WzIntProperty) and int(speed.value) == bullet_speed, mob_id

        xml = ET.parse(ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml").getroot()
        xml_info = xml.find(
            f'./imgdir[@name="attack{attack_number}"]/imgdir[@name="info"]'
        )
        assert xml_info is not None, mob_id
        assert tuple(child.get("name") for child in xml_info) == INFO_ORDER, mob_id
        xml_type = xml_info.find('./int[@name="type"]')
        xml_speed = xml_info.find('./int[@name="bulletSpeed"]')
        assert xml_type is not None and xml_type.get("value") == "2", mob_id
        assert xml_speed is not None and xml_speed.get("value") == str(bullet_speed), mob_id
    print(f"Arcane River ballistic attack contract ok: mobs={len(EXPECTED)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
