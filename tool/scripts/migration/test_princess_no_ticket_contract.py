#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

spec = importlib.util.spec_from_file_location(
    "ticket_migration",
    ROOT / "tool/scripts/migration/add_princess_no_ticket.py",
)
migration = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = migration
spec.loader.exec_module(migration)

from wzpy import WzCanvasProperty, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


def child_value(node, name):
    child = node.child(name)
    return getattr(child, "value", None)


def assert_client_item() -> None:
    image = migration.load_client(ROOT / "clien/Data/Item/Etc/0400.img")
    source = image.root.child(migration.SOURCE_ITEM_RECORD)
    target = image.root.child(migration.TARGET_ITEM_RECORD)
    assert isinstance(source, WzSubProperty)
    assert isinstance(target, WzSubProperty)
    assert tuple(child.name for child in source.children()) == tuple(
        child.name for child in target.children()
    )
    for icon_name in ("icon", "iconRaw"):
        source_icon = source.get(f"info/{icon_name}")
        target_icon = target.get(f"info/{icon_name}")
        assert isinstance(source_icon, WzCanvasProperty)
        assert isinstance(target_icon, WzCanvasProperty)
        assert (target_icon.format, target_icon.format2) == (1, 0)
        source_bitmap = decode_canvas(source_icon, region="GMS").convert("RGBA")
        target_bitmap = decode_canvas(target_icon, region="GMS").convert("RGBA")
        assert source_bitmap.size == target_bitmap.size
        assert source_bitmap.tobytes() == target_bitmap.tobytes()
        assert target_bitmap.getbbox() is not None
    info = target.child("info")
    assert child_value(info, "notSale") == 1
    assert child_value(info, "price") == 1
    assert child_value(info, "slotMax") == 200


def assert_client_string_and_quest() -> None:
    strings = migration.load_client(ROOT / "clien/Data/String/Etc.img")
    ticket = strings.root.get(f"Etc/{migration.TARGET_TICKET}")
    assert isinstance(ticket, WzSubProperty)
    assert child_value(ticket, "name") == migration.TICKET_NAME
    assert child_value(ticket, "desc") == migration.TICKET_DESC

    act = migration.load_client(ROOT / "clien/Data/Quest/Act.img")
    assert act.root.get(f"{migration.QUEST_ID}/1/item") is None
    info = migration.load_client(ROOT / "clien/Data/Quest/QuestInfo.img")
    assert child_value(info.root.child(migration.QUEST_ID), "2") == migration.QUEST_COMPLETE_TEXT
    say = migration.load_client(ROOT / "clien/Data/Quest/Say.img")
    quest = say.root.child(migration.QUEST_ID)
    assert child_value(quest.child("0"), "0") == migration.QUEST_OFFER_TEXT
    assert child_value(quest.child("1"), "0") == migration.QUEST_FINISH_TEXT


def assert_server_contract() -> None:
    item = ET.parse(ROOT / "gms-server/wz/Item.wz/Etc/0400.img.xml").getroot()
    target = item.find(f'./imgdir[@name="{migration.TARGET_ITEM_RECORD}"]')
    assert target is not None
    for icon_name in ("icon", "iconRaw"):
        icon = target.find(f'./imgdir[@name="info"]/canvas[@name="{icon_name}"]')
        assert icon is not None
        assert icon.get("format") == "1"

    for tree in ("wz", "wz-zh-CN"):
        strings = ET.parse(ROOT / f"gms-server/{tree}/String.wz/Etc.img.xml").getroot()
        ticket = strings.find(
            f'./imgdir[@name="Etc"]/imgdir[@name="{migration.TARGET_TICKET}"]'
        )
        assert ticket is not None
        assert ticket.find('./string[@name="name"]').get("value") == migration.TICKET_NAME
        assert ticket.find('./string[@name="desc"]').get("value") == migration.TICKET_DESC

        quest_dir = ROOT / f"gms-server/{tree}/Quest.wz"
        act = ET.parse(quest_dir / "Act.img.xml").getroot()
        quest = act.find(f'./imgdir[@name="{migration.SERVER_QUEST_ID}"]')
        assert quest is not None
        assert quest.find('./imgdir[@name="1"]/imgdir[@name="item"]') is None

        info = ET.parse(quest_dir / "QuestInfo.img.xml").getroot()
        value = info.find(
            f'./imgdir[@name="{migration.SERVER_QUEST_ID}"]/string[@name="2"]'
        )
        assert value is not None and value.get("value") == migration.QUEST_COMPLETE_TEXT

        say = ET.parse(quest_dir / "Say.img.xml").getroot()
        offer = say.find(
            f'./imgdir[@name="{migration.SERVER_QUEST_ID}"]/imgdir[@name="0"]/'
            'string[@name="0"]'
        )
        finish = say.find(
            f'./imgdir[@name="{migration.SERVER_QUEST_ID}"]/imgdir[@name="1"]/'
            'string[@name="0"]'
        )
        assert offer is not None and offer.get("value") == migration.QUEST_OFFER_TEXT
        assert finish is not None and finish.get("value") == migration.QUEST_FINISH_TEXT


assert_client_item()
assert_client_string_and_quest()
assert_server_contract()
print("Princess No ticket resource contract checks passed")
