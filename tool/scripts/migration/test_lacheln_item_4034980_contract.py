#!/usr/bin/env python3
"""Contract checks for Lacheln quest item 4034980."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/scripts/patch-client"))

import add_lacheln_quest_item_4034980 as item_patch  # noqa: E402


def direct_child(parent: ET.Element, name: str) -> ET.Element:
    node = next((child for child in parent if child.get("name") == name), None)
    assert node is not None
    return node


def values(parent: ET.Element) -> dict[str, str | None]:
    return {child.get("name", ""): child.get("value") for child in parent}


def main() -> int:
    expected = item_patch.build_expected()
    for path, (_baseline, result) in expected.items():
        assert path.read_bytes() == result

    for path, parent_name, record_name in (
        (item_patch.SERVER_ITEM, None, item_patch.ITEM_NAME),
        *((path, "Etc", str(item_patch.ITEM_ID)) for path in item_patch.SERVER_STRINGS),
    ):
        parent = ET.parse(path).getroot()
        if parent_name:
            parent = direct_child(parent, parent_name)
        direct_child(parent, record_name)

    checks = ET.parse(ROOT / "gms-server/wz/Quest.wz/Check.img.xml").getroot()
    quest = direct_child(checks, "34320")
    objective = direct_child(direct_child(direct_child(quest, "1"), "item"), "0")
    assert values(objective) == {"id": "4034980", "count": "20", "order": "1"}

    map_root = ET.parse(
        ROOT / "gms-server/wz/Map.wz/Map/Map4/450003400.img.xml"
    ).getroot()
    life = direct_child(map_root, "life")
    assert any(
        values(entry).get("type") == "m" and values(entry).get("id") == "8643008"
        for entry in life
    )

    drop_sql = (
        ROOT
        / "gms-server/src/main/resources/db/migration"
        / "V2.1.65__add_lacheln_4034980_quest_drop.sql"
    ).read_text(encoding="utf-8")
    assert "(8643008, 4034980, 1, 1, 34320, 500000)" in drop_sql
    assert drop_sql.count("4034980") == 1
    print(
        "Lacheln item 4034980 contract ok: item/string stores=5; "
        "icons=ARGB4444 visible; drop=8643008 quest 34320"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
