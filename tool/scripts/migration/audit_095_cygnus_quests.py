#!/usr/bin/env python3
"""Audit v095 Cygnus quest resources and drops in the current project."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_CLIENT = Path("/Users/lizixian/Documents/mxd/怀旧岛V095仿官版/怀旧岛V095客户端")
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import WzFile, WzImage, WzKey  # noqa: E402


QUEST_IDS = {str(qid) for qid in range(31100, 31161)}
TARGET_KEY = WzKey.for_region("GMS")


def direct_child(node: ET.Element, name: str) -> ET.Element | None:
    for child in node:
        if child.get("name") == name:
            return child
    return None


def int_value(node: ET.Element, name: str) -> int | None:
    child = direct_child(node, name)
    if child is None:
        return None
    value = child.get("value")
    if value is None:
        return None
    return int(value)


def walk_items(node: ET.Element, parent_name: str | None = None):
    node_name = node.get("name")
    if parent_name == "item" and node.tag == "imgdir":
        item_id = int_value(node, "id")
        if item_id is not None:
            count = int_value(node, "count")
            yield item_id, count
    for child in node:
        yield from walk_items(child, node_name)


def walk_mobs(node: ET.Element, parent_name: str | None = None):
    node_name = node.get("name")
    if parent_name == "mob" and node.tag == "imgdir":
        mob_id = int_value(node, "id")
        if mob_id is not None:
            count = int_value(node, "count")
            yield mob_id, count
    for child in node:
        yield from walk_mobs(child, node_name)


def item_group(item_id: int) -> tuple[str, str]:
    text = f"{item_id:08d}"
    prefix = text[:4]
    if 2000000 <= item_id < 3000000:
        return "Consume", prefix
    if 4000000 <= item_id < 5000000:
        return "Etc", prefix
    if 1000000 <= item_id < 2000000:
        return "Equip", prefix
    raise ValueError(f"unsupported item id {item_id}")


def server_item_exists(item_id: int) -> bool:
    category, prefix = item_group(item_id)
    text = f"{item_id:08d}"
    if category == "Equip":
        return any(text in path.read_text(encoding="utf-8", errors="ignore") for path in (ROOT / "gms-server/wz/Character.wz").glob("**/*.xml"))
    path = ROOT / "gms-server/wz/Item.wz" / category / f"{prefix}.img.xml"
    if not path.exists():
        return False
    root = ET.parse(path).getroot()
    return direct_child(root, text) is not None


def client_item_exists(item_id: int) -> bool:
    category, prefix = item_group(item_id)
    text = f"{item_id:08d}"
    if category == "Equip":
        return (ROOT / f"clien/Data/Character/Cap/{text}.img").exists()
    path = ROOT / "clien/Data/Item" / category / f"{prefix}.img"
    if not path.exists():
        return False
    img = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=f"{prefix}.img")
    img.parse()
    return img.get(text) is not None


def source_client_item_exists(item_id: int) -> bool:
    category, prefix = item_group(item_id)
    text = f"{item_id:08d}"
    if category == "Equip":
        return False
    with WzFile.open(str(SRC_CLIENT / "Item.wz"), region="EMS", version=95) as wz:
        image = wz.root.get(f"{category}/{prefix}.img")
        if image is None:
            return False
        image.parse()
        return image.get(text) is not None


def existing_drop_pairs() -> set[tuple[int, int]]:
    pairs: set[tuple[int, int]] = set()
    pattern = re.compile(r"\((\d+),\s*(\d+),\s*\d+,\s*\d+,\s*\d+,\s*\d+\)")
    for path in (ROOT / "gms-server/src/main/resources/db/migration").glob("*.sql"):
        for dropper, item in pattern.findall(path.read_text(encoding="utf-8", errors="ignore")):
            pairs.add((int(dropper), int(item)))
    return pairs


def migration_drop_pairs() -> set[tuple[int, int]]:
    path = ROOT / "gms-server/src/main/resources/db/migration/V2.1.20__add_cygnus_future_gate_quest_drops.sql"
    if not path.exists():
        return set()
    pattern = re.compile(r"\((\d+),\s*(\d+),\s*\d+,\s*\d+,\s*\d+,\s*\d+\)")
    return {(int(dropper), int(item)) for dropper, item in pattern.findall(path.read_text(encoding="utf-8", errors="ignore"))}


def main() -> int:
    check_root = ET.parse(ROOT / "gms-server/wz/Quest.wz/Check.img.xml").getroot()
    act_root = ET.parse(ROOT / "gms-server/wz/Quest.wz/Act.img.xml").getroot()

    item_ids: set[int] = set()
    mob_ids: set[int] = set()
    for root in (check_root, act_root):
        for quest in root:
            if quest.get("name") in QUEST_IDS:
                item_ids.update(item_id for item_id, _ in walk_items(quest))
                mob_ids.update(mob_id for mob_id, _ in walk_mobs(quest))

    drops = existing_drop_pairs()
    migration_drops = migration_drop_pairs()
    print("QUEST_ITEMS", " ".join(str(item_id) for item_id in sorted(item_ids)))
    for item_id in sorted(item_ids):
        print(
            "ITEM",
            item_id,
            f"server={int(server_item_exists(item_id))}",
            f"client={int(client_item_exists(item_id))}",
            f"src_client={int(source_client_item_exists(item_id))}",
        )

    print("QUEST_MOBS", " ".join(str(mob_id) for mob_id in sorted(mob_ids)))
    for mob_id in sorted(mob_ids):
        mob_drops = sorted(item for dropper, item in drops if dropper == mob_id)
        relevant = sorted(item_id for item_id in item_ids if (mob_id, item_id) in drops)
        print("MOB_DROPS", mob_id, "count=" + str(len(mob_drops)), "quest_items=" + ",".join(map(str, relevant)))

    print("MIGRATION_DROP_ITEMS", " ".join(str(item_id) for item_id in sorted({item for _, item in migration_drops})))
    for item_id in sorted({item for _, item in migration_drops}):
        print(
            "DROP_ITEM",
            item_id,
            f"server={int(server_item_exists(item_id))}",
            f"client={int(client_item_exists(item_id))}",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
