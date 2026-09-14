#!/usr/bin/env python3
"""Contract: Damien TMS skills, daily 57482, ticket 4000698, expedition entry."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT / "tool/wz-python"),
    str(ROOT / "tool/scripts/migration"),
]

import install_damien_ticket_expedition as install  # noqa: E402
import migrate_demian as migration  # noqa: E402
from migrate_twilight_perion_monster_park import load_checked  # noqa: E402
from wzpy import WzCanvasProperty, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402

CLIENT_QUEST_ID = "57482"
SERVER_QUEST_ID = "-8054"
TICKET_ID = "4000698"
FIELD_MOBS = install.FIELD_MOBS


def main() -> int:
    errors: list[str] = []
    for mob_id in (8880110, 8880111):
        image = load_checked(ROOT / f"clien/Data/Mob/{mob_id}.img", install.arc.GMS_KEY)
        actual = [
            {entry.name: int(entry.value) for entry in child.children()}
            for child in image.root.get("info/skill").children()
        ]
        if actual != list(migration.SKILLS_BY_MOB[mob_id]):
            errors.append(f"{mob_id} client skill table differs from TMS")
        xml = ET.parse(ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml")
        nodes = xml.getroot().findall("./imgdir[@name='info']/imgdir[@name='skill']/imgdir")
        xml_actual = [
            {child.get("name"): int(child.get("value")) for child in node if child.tag == "int"}
            for node in nodes
        ]
        if xml_actual != list(migration.SKILLS_BY_MOB[mob_id]):
            errors.append(f"xml {mob_id} skill table differs from TMS")

    for name in install.QUEST_NAMES:
        image = load_checked(ROOT / f"clien/Data/Quest/{name}.img", install.arc.GMS_KEY)
        if image.root.child(CLIENT_QUEST_ID) is None:
            errors.append(f"missing client quest {name}/{CLIENT_QUEST_ID}")
        if image.root.child(SERVER_QUEST_ID) is not None:
            errors.append(f"signed alias collision {name}/{CLIENT_QUEST_ID}")
        for tree in ("wz", "wz-zh-CN"):
            root = ET.parse(ROOT / f"gms-server/{tree}/Quest.wz/{name}.img.xml").getroot()
            if root.find(f'./imgdir[@name="{SERVER_QUEST_ID}"]') is None:
                errors.append(f"missing {tree} quest {name}/{SERVER_QUEST_ID}")
            if root.find(f'./imgdir[@name="{CLIENT_QUEST_ID}"]') is not None:
                errors.append(f"{tree} kept unsigned quest {name}/{CLIENT_QUEST_ID}")

    check = load_checked(ROOT / "clien/Data/Quest/Check.img", install.arc.GMS_KEY).root.child(CLIENT_QUEST_ID)
    start = check.child("0")
    if int(install.arc.child_value(start, "interval") or 0) != 1440:
        errors.append("daily interval is not 1440")
    if int(install.arc.child_value(start, "npc") or 0) != 1540895:
        errors.append("daily start NPC is not 1540895")
    if int(install.arc.child_value(start, "lvmin") or 0) != 180:
        errors.append("daily lvmin is not 180")
    mobs = check.get("1/mob")
    found = []
    for child in mobs.children():
        found.append(
            (
                int(install.arc.child_value(child, "id") or 0),
                int(install.arc.child_value(child, "count") or 0),
            )
        )
    if found != [(mob_id, 100) for mob_id in FIELD_MOBS]:
        errors.append(f"daily mob list mismatch: {found}")

    act = load_checked(ROOT / "clien/Data/Quest/Act.img", install.arc.GMS_KEY).root.child(CLIENT_QUEST_ID)
    reward_id = int(install.arc.child_value(act.get("1/item/0"), "id") or 0)
    if reward_id != 4000698:
        errors.append("daily reward is not 4000698")

    item = load_checked(ROOT / "clien/Data/Item/Etc/0400.img", install.arc.GMS_KEY).root.child("04000698")
    if not isinstance(item, WzSubProperty):
        errors.append("missing client item 4000698")
    else:
        for canvas_name in ("icon", "iconRaw"):
            canvas = item.get(f"info/{canvas_name}")
            if not isinstance(canvas, WzCanvasProperty):
                errors.append(f"missing {canvas_name}")
                continue
            if (int(canvas.format), int(canvas.format2 or 0)) != (1, 0):
                errors.append(f"{canvas_name} is not ARGB4444")
            if decode_canvas(canvas, region="GMS").getbbox() is None:
                errors.append(f"{canvas_name} has no visible pixels")

    strings = load_checked(ROOT / "clien/Data/String/Etc.img", install.arc.GMS_KEY)
    name = str(install.arc.child_value(strings.root.get("Etc/4000698"), "name") or "")
    if name != "戴米安挑战门票":
        errors.append(f"unexpected ticket name {name}")

    for relative in ("npc/1540895.js", "portal/fallenWT_boss.js", "event/DamienBattle.js"):
        for tree in ("scripts-zh-CN", "scripts"):
            text = (ROOT / "gms-server" / tree / relative).read_text(encoding="utf-8")
            if relative.endswith("1540895.js") and (
                "-8054" not in text
                or "4000698" not in text
                or "DAMIEN" not in text
                or "startInstance" not in text
            ):
                errors.append(f"{tree}/{relative} missing daily/expedition contract")
            if relative.endswith("fallenWT_boss.js") and "4000698" not in text:
                errors.append(f"{tree}/{relative} missing ticket gate")
            if relative.endswith("DamienBattle.js") and 'newInstance("DAMIEN"' not in text:
                errors.append(f"{tree}/{relative} instance name is not DAMIEN")

    type_src = (ROOT / "gms-server/src/main/java/org/gms/server/expeditions/ExpeditionType.java").read_text(encoding="utf-8")
    if "DAMIEN(" not in type_src:
        errors.append("ExpeditionType missing DAMIEN")

    if errors:
        print("\n".join(errors))
        return 1
    print("damien ticket/expedition/TMS skill contract ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
