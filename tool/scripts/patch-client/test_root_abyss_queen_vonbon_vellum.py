#!/usr/bin/env python3
"""Root Abyss: long HP lives only in server XML strings; client stays int-safe."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_expansion as arc  # noqa: E402
from migrate_twilight_perion_monster_park import load_checked  # noqa: E402
from wzpy import WzUolProperty, WzSubProperty  # noqa: E402

INT_MAX = 2_147_483_647
LONG_HP_BOSSES = {
    8900000: 80_000_000_000,
    8910000: 100_000_000_000,
    8930000: 200_000_000_000,
}


def numeric_frames(node: WzSubProperty) -> list[str]:
    return sorted((child.name for child in node.children() if child.name.isdigit()), key=int)


def main() -> int:
    errors: list[str] = []
    for mob_id, expected in LONG_HP_BOSSES.items():
        xml_path = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
        root = ET.parse(xml_path).getroot()
        node = root.find('./imgdir[@name="info"]/*[@name="maxHP"]')
        if node is None:
            errors.append(f"{mob_id} missing server maxHP")
            continue
        if node.tag != "string":
            errors.append(f"{mob_id} server maxHP must be string, got <{node.tag}>")
        hp = int(node.get("value") or 0)
        if hp != expected:
            errors.append(f"{mob_id} server maxHP {hp} != {expected}")
        client = load_checked(ROOT / f"clien/Data/Mob/{mob_id}.img", arc.GMS_KEY)
        client_hp = int(arc.child_value(client.root.child("info"), "maxHP") or 0)
        if client_hp > INT_MAX:
            errors.append(f"{mob_id} client maxHP {client_hp} exceeds int")

    source = (ROOT / "gms-server/src/main/java/org/gms/server/life/MobSkill.java").read_text(
        encoding="utf-8"
    )
    for needle in (
        "customSkill/rootAbyss/queenVideoLayer",
        "customSkill/rootAbyss/vonBonVideoLayer",
        "customSkill/rootAbyss/vellumVideoLayer",
    ):
        if needle in source:
            errors.append(f"MobSkill still broadcasts {needle}")

    queen = load_checked(ROOT / "clien/Data/Mob/8920000.img", arc.GMS_KEY)
    skill2 = queen.root.child("skill2")
    attack2 = queen.root.child("attack2")
    if not isinstance(skill2, WzSubProperty) or not isinstance(attack2, WzSubProperty):
        errors.append("queen missing skill2/attack2")
    else:
        if numeric_frames(skill2) != numeric_frames(attack2):
            errors.append("queen skill2 frames != attack2")
        for name in numeric_frames(skill2):
            node = skill2.child(name)
            if not isinstance(node, WzUolProperty) or node.value != f"../attack2/{name}":
                errors.append(f"queen skill2/{name} is not attack2 UOL")
        skill1 = queen.root.child("skill1")
        if isinstance(skill1, WzSubProperty):
            for name in numeric_frames(skill1):
                delay = arc.child_value(skill1.child(name), "delay")
                if delay != 120:
                    errors.append(f"queen skill1/{name} delay={delay}")

    vellum = load_checked(ROOT / "clien/Data/Mob/8930000.img", arc.GMS_KEY)
    if arc.child_value(vellum.root.child("info"), "hideMove") != 0:
        errors.append("vellum client hideMove must be 0")
    if int(arc.child_value(vellum.root.child("info"), "maxHP") or 0) > INT_MAX:
        errors.append("vellum client maxHP must stay int-safe")

    xml = ET.parse(ROOT / "gms-server/wz/Mob.wz/8930000.img.xml").getroot()
    pd = xml.find('./imgdir[@name="info"]/int[@name="PDDamage"]')
    md = xml.find('./imgdir[@name="info"]/int[@name="MDDamage"]')
    if pd is None or int(pd.get("value") or 0) <= 0:
        errors.append("vellum server PDDamage must be positive")
    if md is None or int(md.get("value") or 0) <= 0:
        errors.append("vellum server MDDamage must be positive")

    if errors:
        print("\n".join(errors))
        return 1
    print("root abyss queen/vonbon/vellum contract ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
