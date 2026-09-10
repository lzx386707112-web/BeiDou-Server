#!/usr/bin/env python3
"""Contract: daily quest 57481, ticket 4000697, and ticket-gated Ranmaru entry."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT / "tool/wz-python"),
    str(ROOT / "tool/scripts/migration"),
    str(ROOT / "tool/scripts/patch-client"),
]

import add_item_4000697_ranmaru_ticket as ticket  # noqa: E402
import add_ranmaru_daily_ticket as daily  # noqa: E402
import migrate_ranmaru as ranmaru  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


CLIENT_QUEST_ID = "57481"
SERVER_QUEST_ID = "-8055"
TICKET_ID = "4000697"
FIELD_MOBS = ranmaru.FIELD_MOBS


def load(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=ranmaru.arc.GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"unsafe {path}: truncated={image.truncated} warnings={image.parse_warnings}")
    return image


def xml_text(tree: str, name: str) -> ET.Element:
    path = ROOT / f"gms-server/{tree}/Quest.wz/{name}.img.xml"
    return ET.parse(path).getroot()


def quest_dir(root: ET.Element, quest_id: str) -> ET.Element:
    node = root.find(f'./imgdir[@name="{quest_id}"]')
    if node is None:
        raise RuntimeError(f"missing XML quest {quest_id}")
    return node


def main() -> int:
    errors: list[str] = []
    ticket_payloads = ticket.build()
    for path, data in ticket_payloads.items():
        if path.read_bytes() != data:
            errors.append(f"ticket generator drift {path.relative_to(ROOT)}")

    for name in daily.QUEST_NAMES:
        image = load(ROOT / f"clien/Data/Quest/{name}.img")
        if image.root.child(CLIENT_QUEST_ID) is None:
            errors.append(f"missing client quest {name}/{CLIENT_QUEST_ID}")
        if image.root.child(SERVER_QUEST_ID) is not None:
            errors.append(f"signed alias collision {name}/{CLIENT_QUEST_ID}")
        for tree in ("wz", "wz-zh-CN"):
            root = xml_text(tree, name)
            if root.find(f'./imgdir[@name="{SERVER_QUEST_ID}"]') is None:
                errors.append(f"missing {tree} quest {name}/{SERVER_QUEST_ID}")
            if root.find(f'./imgdir[@name="{CLIENT_QUEST_ID}"]') is not None:
                errors.append(f"{tree} kept unsigned quest {name}/{CLIENT_QUEST_ID}")

    check_client = load(ROOT / "clien/Data/Quest/Check.img").root.child(CLIENT_QUEST_ID)
    if not isinstance(check_client, WzSubProperty):
        errors.append("client Check/57481 missing")
    else:
        start = check_client.child("0")
        if int(ranmaru.arc.child_value(start, "interval") or 0) != 1440:
            errors.append("daily interval is not 1440")
        if int(ranmaru.arc.child_value(start, "npc") or 0) != 9130000:
            errors.append("daily start NPC is not 9130000")
        if int(ranmaru.arc.child_value(start, "lvmin") or 0) != 120:
            errors.append("daily lvmin is not 120")
        mobs = check_client.get("1/mob")
        if not isinstance(mobs, WzSubProperty):
            errors.append("daily mob list missing")
        else:
            found = []
            for child in mobs.children():
                found.append(
                    (
                        int(ranmaru.arc.child_value(child, "id") or 0),
                        int(ranmaru.arc.child_value(child, "count") or 0),
                    )
                )
            expected = [(mob_id, 200) for mob_id in FIELD_MOBS]
            if found != expected:
                errors.append(f"daily mob list mismatch: {found}")

    act_client = load(ROOT / "clien/Data/Quest/Act.img").root.child(CLIENT_QUEST_ID)
    reward_id = int(ranmaru.arc.child_value(act_client.get("1/item/0"), "id") or 0) if act_client else 0
    reward_count = int(ranmaru.arc.child_value(act_client.get("1/item/0"), "count") or 0) if act_client else 0
    if reward_id != int(TICKET_ID) or reward_count != 1:
        errors.append("daily reward is not 1x 4000697")

    info = load(ROOT / "clien/Data/Quest/QuestInfo.img").root.child(CLIENT_QUEST_ID)
    info_text = str(ranmaru.arc.child_value(info, "1") or "") if info else ""
    for index, mob_id in enumerate(FIELD_MOBS, start=1):
        if f"#o{mob_id}#" not in info_text:
            errors.append(f"QuestInfo does not list mob {mob_id}")
        marker = f"#a{CLIENT_QUEST_ID}{index}#"
        if marker not in info_text:
            errors.append(f"QuestInfo missing progress marker {marker}")

    check_xml = quest_dir(xml_text("wz", "Check"), SERVER_QUEST_ID)
    mob_ids = [
        int(node.attrib.get("value", "0"))
        for node in check_xml.findall('./imgdir[@name="1"]/imgdir[@name="mob"]/imgdir/int[@name="id"]')
    ]
    if mob_ids != list(FIELD_MOBS):
        errors.append(f"server Check mobs mismatch {mob_ids}")

    town = load(ranmaru.client_map_path(ranmaru.TOWN_MAP))
    town_npcs = {
        int(ranmaru.arc.child_value(entry, "id"))
        for entry in town.root.child("life").children()
        if ranmaru.arc.child_value(entry, "type") == "n"
    }
    if 9130000 not in town_npcs:
        errors.append("town missing daily NPC 9130000")

    for relative in (
        "npc/9130000.js",
        "npc/9130145.js",
        "portal/Ranmaru_accept.js",
        "portal/Ranmaru_ptlNPC2.js",
        "portal/pt_ranmaruOut.js",
        "event/RanmaruHardBattle.js",
    ):
        for tree in ("scripts-zh-CN", "scripts"):
            path = ROOT / "gms-server" / tree / relative
            text = path.read_text(encoding="utf-8")
            if relative.startswith("npc/9130000") and "-8055" not in text:
                errors.append(f"{tree}/{relative} missing signed quest -8055")
            if relative.startswith("npc/9130145") and "4000697" not in text:
                errors.append(f"{tree}/{relative} missing ticket check")
            if relative.startswith("portal/Ranmaru") and "4000697" not in text:
                errors.append(f"{tree}/{relative} missing ticket gate")
            if relative.endswith("RanmaruHardBattle.js") and "807300100" not in text:
                errors.append(f"{tree}/{relative} hard exit is not the altar")

    item = load(ROOT / "clien/Data/Item/Etc/0400.img").root.child("04000697")
    if not isinstance(item, WzSubProperty):
        errors.append("missing client item 4000697")
    else:
        for canvas_name in ("icon", "iconRaw"):
            canvas = item.get(f"info/{canvas_name}")
            if not isinstance(canvas, WzCanvasProperty):
                errors.append(f"missing {canvas_name}")
                continue
            if (int(canvas.format), int(canvas.format2 or 0)) != (1, 0):
                errors.append(f"{canvas_name} is not ARGB4444")
            decoded = decode_canvas(canvas, region="GMS")
            if decoded.getbbox() is None:
                errors.append(f"{canvas_name} has no visible pixels")

    if errors:
        print("\n".join(errors))
        return 1
    print("ranmaru daily ticket contract ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
