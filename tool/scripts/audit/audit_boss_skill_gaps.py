#!/usr/bin/env python3
"""Audit the second-pass Boss-only compatibility skills."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/patch-boss"))

from wzpy import WzCanvasProperty, WzImage, WzKey  # noqa: E402
from patch_boss_skill_gaps import CUSTOM_SKILLS, MAGNUS_STATUS_SKILLS, VISUAL_SKILLS  # noqa: E402


def load(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    image.parse()
    return image


def main() -> int:
    errors = []
    mobskill = load(ROOT / "clien/Data/Skill/MobSkill.img")
    server_mobskill = ET.parse(ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml").getroot()
    effects = load(ROOT / "clien/Data/Map/Effect.img")
    enum_text = (ROOT / "gms-server/src/main/java/org/gms/server/life/MobSkillType.java").read_text()
    logic_text = (ROOT / "gms-server/src/main/java/org/gms/server/life/MobSkill.java").read_text()

    for mob_id, (skill_id, action, _, _, effect_root, effect_name) in VISUAL_SKILLS.items():
        client = load(ROOT / f"clien/Data/Mob/{mob_id}.img")
        specs = client.root.get("info/skill")
        actual = [] if specs is None else [
            (int(entry.get("skill").value), int(entry.get("level").value), int(entry.get("action").value))
            for entry in specs.children()
        ]
        if (skill_id, 1, action) not in actual:
            errors.append(f"{mob_id}: missing custom skill {skill_id}/1 action {action}")
        actions = [spec[2] for spec in actual]
        if len(actions) != len(set(actions)):
            errors.append(f"{mob_id}: duplicate skill actions remain: {actual}")
        if mob_id == 8880000 and actual[:-1] != list(MAGNUS_STATUS_SKILLS):
            errors.append(f"8880000: Magnus status skills not restored: {actual}")
        if client.root.child(f"skill{action}") is None:
            errors.append(f"{mob_id}: missing skill{action} action")
        server = ET.parse(ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml").getroot()
        if server.find(f'./imgdir[@name="skill{action}"]') is None:
            errors.append(f"{mob_id}: missing server skill{action}")
        effect = effects.root.get(f"{effect_root}/{effect_name}")
        effect_frames = [] if effect is None else [frame for frame in effect.children() if isinstance(frame, WzCanvasProperty)]
        canvas_count = len(effect_frames)
        if canvas_count == 0:
            errors.append(f"{effect_root}/{effect_name}: missing effect Canvas")
        for frame in effect_frames:
            missing = [name for name in ("origin", "head", "lt", "rb", "delay") if frame.child(name) is None]
            if missing:
                errors.append(f"{effect_root}/{effect_name}/{frame.name}: missing {missing}")

    for mob_id in (8880300, 8880301, 8880302, 8880000, 8880140, 8880141, 8880142):
        client = load(ROOT / f"clien/Data/Mob/{mob_id}.img")
        stack = [client.root]
        while stack:
            node = stack.pop()
            if isinstance(node, WzCanvasProperty) and node.has_pixels() and int(node.format) + int(node.format2) != 1:
                errors.append(f"{mob_id}/{node.name}: expected ARGB4444")
                break
            if hasattr(node, "children"):
                stack.extend(node.children())

    for skill_id in CUSTOM_SKILLS:
        if mobskill.root.get(f"{skill_id}/level/1") is None:
            errors.append(f"missing client MobSkill {skill_id}/1")
        if server_mobskill.find(f'./imgdir[@name="{skill_id}"]/imgdir[@name="level"]/imgdir[@name="1"]') is None:
            errors.append(f"missing server MobSkill {skill_id}/1")
        if not re.search(rf"\({skill_id}\)", enum_text):
            errors.append(f"MobSkillType missing {skill_id}")
    for token in ("customBossWill/webBurst", "customBossMagnus/meteorStorm", "customBossLucid/dreamBurst", "customBossSeren/sacredBurst"):
        if token not in logic_text:
            errors.append(f"server handler missing {token}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"boss skill gap audit ok: bosses=4 custom_skills=4 magnus_status_skills={len(MAGNUS_STATUS_SKILLS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
