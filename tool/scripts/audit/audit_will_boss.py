#!/usr/bin/env python3
"""Audit the Boss-only Will compatibility chain."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

from wzpy import WzCanvasProperty, WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


KEY = WzKey.for_region("GMS")
WILL_IDS = (8880300, 8880301, 8880302, 8880305, 8880315)
EXPECTED_SKILLS = ((120, 5, 3), (127, 2, 2), (140, 5, 4), (183, 1, 7))


def value(node):
    return None if node is None else node.value


def load_img(path: Path) -> WzImage:
    img = WzImage.from_bytes(path.read_bytes(), key=KEY, name=path.name)
    img.parse()
    return img


def walk_canvas(node):
    if isinstance(node, WzCanvasProperty) and node.has_pixels():
        yield node
    if hasattr(node, "children"):
        for child in node.children():
            yield from walk_canvas(child)


def server_skill_exists(root: ET.Element, skill: int, level: int) -> bool:
    return root.find(
        f'./imgdir[@name="{skill}"]/imgdir[@name="level"]/imgdir[@name="{level}"]'
    ) is not None


def main() -> int:
    errors: list[str] = []
    canvas_count = 0
    mobs = {}
    for mob_id in WILL_IDS:
        client_path = ROOT / f"clien/Data/Mob/{mob_id}.img"
        server_path = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
        if not client_path.exists():
            errors.append(f"missing client Mob {mob_id}")
            continue
        if not server_path.exists():
            errors.append(f"missing server Mob {mob_id}")
            continue
        try:
            ET.parse(server_path)
        except ET.ParseError as exc:
            errors.append(f"invalid server XML {mob_id}: {exc}")
        img = load_img(client_path)
        mobs[mob_id] = img
        for canvas in walk_canvas(img.root):
            canvas_count += 1
            try:
                decode_canvas(canvas, region="GMS")
            except Exception as exc:
                errors.append(f"canvas decode failed {mob_id}/{canvas.name}: {exc}")

    expected_revive = {8880300: 8880301, 8880301: 8880302}
    for mob_id, target in expected_revive.items():
        actual = value(mobs[mob_id].root.get("info/revive/0"))
        if actual != target:
            errors.append(f"client revive {mob_id}: expected {target}, got {actual}")
        server = ET.parse(ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml").getroot()
        node = server.find('./imgdir[@name="info"]/imgdir[@name="revive"]/int[@name="0"]')
        if node is None or int(node.attrib["value"]) != target:
            errors.append(f"server revive {mob_id}: expected {target}")

    for mob_id in (8880300, 8880301, 8880302):
        server = ET.parse(ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml").getroot()
        hp = server.find('./imgdir[@name="info"]/string[@name="maxHP"]')
        if hp is None or hp.attrib.get("value") != "5000000000":
            errors.append(f"server maxHP {mob_id}: expected long-safe 5000000000")

    will = mobs[8880301]
    skills = will.root.get("info/skill")
    actual_skills = [] if skills is None else [
        (value(entry.child("skill")), value(entry.child("level")), value(entry.child("action")))
        for entry in skills.children()
    ]
    if tuple(actual_skills) != EXPECTED_SKILLS:
        errors.append(f"8880301 skill table mismatch: {actual_skills}")
    for _, _, action in EXPECTED_SKILLS:
        if will.root.child(f"skill{action}") is None:
            errors.append(f"8880301 missing client skill{action}")

    client_mobskill = load_img(ROOT / "clien/Data/Skill/MobSkill.img")
    server_mobskill = ET.parse(ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml").getroot()
    for skill, level, _ in EXPECTED_SKILLS:
        if client_mobskill.root.get(f"{skill}/level/{level}") is None:
            errors.append(f"missing client MobSkill {skill}/{level}")
        if not server_skill_exists(server_mobskill, skill, level):
            errors.append(f"missing server MobSkill {skill}/{level}")

    strings = load_img(ROOT / "clien/Data/String/Mob.img")
    for mob_id in WILL_IDS:
        if strings.root.get(f"{mob_id}/name") is None:
            errors.append(f"missing client String/Mob {mob_id}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"will audit failed: errors={len(errors)} canvas={canvas_count}")
        return 1
    print(f"will audit ok: mobs={len(WILL_IDS)} canvas={canvas_count} skills={len(EXPECTED_SKILLS)} stage_hp=5000000000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
