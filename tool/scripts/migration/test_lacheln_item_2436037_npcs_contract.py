#!/usr/bin/env python3
"""Contract checks for Lacheln item 2436037 and referenced NPC resources."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/scripts/patch-client"))

import add_lacheln_item_2436037_npcs as patch  # noqa: E402


def direct_child(parent: ET.Element, name: str) -> ET.Element:
    matches = [child for child in parent if child.get("name") == name]
    assert len(matches) == 1, (name, len(matches))
    return matches[0]


def has_property_value(path: Path, property_name: str, value: str) -> bool:
    root = ET.parse(path).getroot()
    return any(
        node.get("name") == property_name and node.get("value") == value
        for node in root.iter()
    )


def main() -> int:
    first = patch.build_expected()
    second = patch.build_expected()
    assert first.keys() == second.keys()
    for path, (_baseline, result) in first.items():
        assert path.read_bytes() == result
        assert result == second[path][1]

    direct_child(ET.parse(patch.SERVER_ITEM).getroot(), patch.ITEM_NAME)
    for path in patch.SERVER_ITEM_STRINGS:
        item = direct_child(ET.parse(path).getroot(), str(patch.ITEM_ID))
        assert direct_child(item, "name").get("value") == patch.ITEM_STRING_NAME

    for npc_id in patch.NEW_NPC_IDS:
        assert patch.CLIENT_NPCS[npc_id].is_file()
        assert ET.parse(patch.SERVER_NPCS[npc_id]).getroot().get("name") == f"{npc_id}.img"
    assert (ROOT / "gms-server/scripts-zh-CN/npc/3003200.js").is_file()

    for index, path in enumerate(patch.SERVER_NPC_STRINGS):
        required = patch.NPC_IDS if index else patch.NEW_NPC_IDS
        root = ET.parse(path).getroot()
        for npc_id in required:
            npc = direct_child(root, str(npc_id))
            assert direct_child(npc, "name").get("value") == patch.NPC_NAMES[npc_id]

    act = ROOT / "gms-server/wz/Quest.wz/Act.img.xml"
    check = ROOT / "gms-server/wz/Quest.wz/Check.img.xml"
    assert has_property_value(act, "id", str(patch.ITEM_ID))
    for npc_id in patch.NPC_IDS:
        assert has_property_value(check, "npc", str(npc_id))

    print(
        "Lacheln resource contract ok: item=2436037; "
        "NPCs=3003200,3003208,9000159,9010100,3006902; "
        "ARGB4444 visible; idempotent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
