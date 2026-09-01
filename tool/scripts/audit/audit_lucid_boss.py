#!/usr/bin/env python3
"""Audit the Boss-only Lucid compatibility chain."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

from wzpy import WzCanvasProperty, WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


KEY = WzKey.for_region("GMS")
MAIN_IDS = (8880140, 8880141, 8880142)
SUPPORT_IDS = (8880161, 8880164, 8880165, 8880171, 8880175)
LUCID_IDS = MAIN_IDS + SUPPORT_IDS
EXPECTED_REVIVE = {8880140: 8880141, 8880141: 8880142}
EXPECTED_SERVER_HP = {
    8880140: "250000000000",
    8880141: "5000000000",
    8880142: "5000000000",
}
EXPECTED_SKILLS = {
    8880140: ((145, 2, 2), (128, 16, 3), (131, 13, 4), (185, 1, 1)),
    8880141: ((145, 5, 1), (145, 2, 2), (128, 16, 3), (125, 9, 4)),
    8880142: ((145, 2, 1), (126, 2, 2), (128, 10, 3)),
}
SUPPORTED_MOB_SKILL_TYPES = {
    100, 101, 102, 103, 110, 111, 112, 113, 114, 115,
    120, 121, 122, 123, 124, 125, 126, 127, 128, 129,
    131, 132, 133, 134, 135, 136, 138, 140, 141, 142,
    143, 144, 145, 146, 150, 151, 152, 153, 154, 155,
    156, 157, 171, 172, 174, 176, 177, 185, 200,
}


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


def server_info(root: ET.Element) -> ET.Element | None:
    return root.find('./imgdir[@name="info"]')


def server_direct_child(parent: ET.Element | None, tag: str, name: str) -> ET.Element | None:
    if parent is None:
        return None
    return parent.find(f'./{tag}[@name="{name}"]')


def main() -> int:
    errors: list[str] = []
    canvas_count = 0
    mobs: dict[int, WzImage] = {}

    for mob_id in LUCID_IDS:
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

    for mob_id, target in EXPECTED_REVIVE.items():
        actual = value(mobs[mob_id].root.get("info/revive/0"))
        if actual != target:
            errors.append(f"client revive {mob_id}: expected {target}, got {actual}")
        root = ET.parse(ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml").getroot()
        node = root.find('./imgdir[@name="info"]/imgdir[@name="revive"]/int[@name="0"]')
        if node is None or int(node.attrib["value"]) != target:
            errors.append(f"server revive {mob_id}: expected {target}")
    if mobs[8880142].root.get("info/revive") is not None:
        errors.append("8880142 must not revive")

    client_mobskill = load_img(ROOT / "clien/Data/Skill/MobSkill.img")
    server_mobskill = ET.parse(ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml").getroot()

    for mob_id in MAIN_IDS:
        root = ET.parse(ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml").getroot()
        info = server_info(root)
        hp = server_direct_child(info, "string", "maxHP")
        expected_hp = EXPECTED_SERVER_HP[mob_id]
        if hp is None or hp.attrib.get("value") != expected_hp:
            errors.append(f"server maxHP {mob_id}: expected string {expected_hp}")

        expected = EXPECTED_SKILLS[mob_id]
        skills = mobs[mob_id].root.get("info/skill")
        actual = [] if skills is None else [
            (value(entry.child("skill")), value(entry.child("level")), value(entry.child("action")))
            for entry in skills.children()
        ]
        if tuple(actual) != expected:
            errors.append(f"client skills {mob_id}: expected {expected}, got {actual}")
        for rate in ("PDRate", "MDRate"):
            if value(mobs[mob_id].root.get(f"info/{rate}")) != 50:
                errors.append(f"{mob_id}: expected {rate}=50")

        server_skill_root = info.find('./imgdir[@name="skill"]') if info is not None else None
        server_actual = []
        if server_skill_root is not None:
            for entry in server_skill_root.findall("imgdir"):
                skill = entry.find('./int[@name="skill"]')
                level = entry.find('./int[@name="level"]')
                action = entry.find('./int[@name="action"]')
                server_actual.append((int(skill.attrib["value"]), int(level.attrib["value"]), int(action.attrib["value"])))
        if tuple(server_actual) != expected:
            errors.append(f"server skills {mob_id}: expected {expected}, got {server_actual}")

        for skill, level, action in expected:
            if skill not in SUPPORTED_MOB_SKILL_TYPES:
                errors.append(f"server MobSkillType does not support {skill}")
            if client_mobskill.root.get(f"{skill}/level/{level}") is None:
                errors.append(f"missing client MobSkill {skill}/{level}")
            if not server_skill_exists(server_mobskill, skill, level):
                errors.append(f"missing server MobSkill {skill}/{level}")
            if mobs[mob_id].root.child(f"skill{action}") is None:
                errors.append(f"{mob_id}: missing client skill{action}")
            if root.find(f'./imgdir[@name="skill{action}"]') is None:
                errors.append(f"{mob_id}: missing server skill{action}")

        text = (ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml").read_text(encoding="utf-8")
        for unsupported in ('skill" value="186"', 'skill" value="201"', 'skill" value="238"'):
            if unsupported in text:
                errors.append(f"{mob_id}: unsupported {unsupported} still present")

    strings = load_img(ROOT / "clien/Data/String/Mob.img")
    for mob_id in LUCID_IDS:
        if strings.root.get(f"{mob_id}/name") is None:
            errors.append(f"missing client String/Mob {mob_id}")

    enum_text = (ROOT / "gms-server/src/main/java/org/gms/server/life/MobSkillType.java").read_text(encoding="utf-8")
    for skill in sorted({skill for specs in EXPECTED_SKILLS.values() for skill, _, _ in specs}):
        if not re.search(rf"\({skill}\)", enum_text):
            errors.append(f"MobSkillType enum missing {skill}")

    ui = load_img(ROOT / "clien/Data/UI/UIWindow.img")
    for mob_id in MAIN_IDS:
        if ui.root.get(f"MobGage/Mob/{mob_id}") is None:
            errors.append(f"missing Lucid boss gauge icon {mob_id}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"lucid audit failed: errors={len(errors)} canvas={canvas_count}")
        return 1

    print(
        "lucid audit ok: "
        f"mobs={len(LUCID_IDS)} canvas={canvas_count} "
        f"stages={len(MAIN_IDS)} stage_hp={','.join(EXPECTED_SERVER_HP.values())} "
        f"skills={sum(len(v) for v in EXPECTED_SKILLS.values())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
