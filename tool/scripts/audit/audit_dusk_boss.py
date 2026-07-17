#!/usr/bin/env python3
"""Audit the mobile-safe Boss-only Dusk compatibility build."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

from wzpy import WzCanvasProperty, WzImage, WzKey, WzUolProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


SOURCE_ID = 8644611
TARGET_ID = 8644630
SKILLS = ((120, 4, 1), (132, 2, 2), (114, 37, 3), (186, 1, 4))
KEY = WzKey.for_region("GMS")


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


def xml_level_exists(root: ET.Element, skill: int, level: int) -> bool:
    for skill_node in root.findall("imgdir"):
        if skill_node.attrib.get("name") != str(skill):
            continue
        for level_root in skill_node.findall("imgdir"):
            if level_root.attrib.get("name") != "level":
                continue
            return any(node.attrib.get("name") == str(level) for node in level_root.findall("imgdir"))
    return False


def main() -> int:
    errors: list[str] = []
    client_path = ROOT / f"clien/Data/Mob/{TARGET_ID}.img"
    server_path = ROOT / f"gms-server/wz/Mob.wz/{TARGET_ID}.img.xml"
    if not client_path.exists():
        errors.append(f"missing client Mob {TARGET_ID}")
    if not server_path.exists():
        errors.append(f"missing server Mob {TARGET_ID}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    client = load_img(client_path)
    server = ET.parse(server_path).getroot()
    info = client.root.get("info")
    if value(info.child("maxHP")) != 2_000_000_000:
        errors.append("client maxHP must be 2000000000")
    if value(info.child("speed")) != 0 or value(info.child("fixed")) != 1:
        errors.append("Dusk must be fixed with speed 0")
    if info.child("revive") is not None:
        errors.append("Dusk must not revive")

    server_info = server.find('./imgdir[@name="info"]')
    hp = None if server_info is None else server_info.find('./string[@name="maxHP"]')
    if hp is None or hp.attrib.get("value") != "5000000000":
        errors.append("server maxHP must be string 5000000000")
    if server_info is not None and server_info.find('./imgdir[@name="revive"]') is not None:
        errors.append("server Dusk must not revive")
    if server_info is not None:
        speed = server_info.find('./int[@name="speed"]')
        fixed = server_info.find('./int[@name="fixed"]')
        if speed is None or speed.attrib.get("value") != "0" or fixed is None or fixed.attrib.get("value") != "1":
            errors.append("server Dusk must be fixed with speed 0")

    skill_root = info.child("skill")
    actual = [] if skill_root is None else [
        (value(entry.child("skill")), value(entry.child("level")), value(entry.child("action")))
        for entry in skill_root.children()
    ]
    if tuple(actual) != SKILLS:
        errors.append(f"client skills: expected {SKILLS}, got {actual}")

    server_skill_root = None if server_info is None else server_info.find('./imgdir[@name="skill"]')
    server_actual = []
    if server_skill_root is not None:
        for entry in server_skill_root.findall("imgdir"):
            skill = entry.find('./int[@name="skill"]')
            level = entry.find('./int[@name="level"]')
            action = entry.find('./int[@name="action"]')
            server_actual.append((int(skill.attrib["value"]), int(level.attrib["value"]), int(action.attrib["value"])))
    if tuple(server_actual) != SKILLS:
        errors.append(f"server skills: expected {SKILLS}, got {server_actual}")

    for _, _, action in SKILLS:
        group = client.root.child(f"skill{action}")
        if group is None:
            errors.append(f"missing client skill{action}")
            continue
        frames = [child for child in group.children() if child.name.isdigit()]
        if not frames or not all(isinstance(frame, WzUolProperty) for frame in frames):
            errors.append(f"skill{action} must use UOL attack frames")
        if server.find(f'./imgdir[@name="skill{action}"]') is None:
            errors.append(f"missing server skill{action}")

    client_mobskill = load_img(ROOT / "clien/Data/Skill/MobSkill.img")
    server_mobskill = ET.parse(ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml").getroot()
    for skill, level, _ in SKILLS:
        if client_mobskill.root.get(f"{skill}/level/{level}") is None:
            errors.append(f"missing client MobSkill {skill}/{level}")
        if not xml_level_exists(server_mobskill, skill, level):
            errors.append(f"missing server MobSkill {skill}/{level}")

    enum_text = (ROOT / "gms-server/src/main/java/org/gms/server/life/MobSkillType.java").read_text(encoding="utf-8")
    for skill in sorted({skill for skill, _, _ in SKILLS}):
        if not re.search(rf"\({skill}\)", enum_text):
            errors.append(f"MobSkillType enum missing {skill}")

    canvas_count = 0
    formats: set[int] = set()
    for canvas in walk_canvas(client.root):
        canvas_count += 1
        formats.add(int(canvas.format) + int(canvas.format2))
        try:
            decode_canvas(canvas, region="GMS")
        except Exception as exc:
            errors.append(f"canvas decode failed {canvas.name}: {exc}")
        origin = canvas.child("origin")
        if origin is not None and int(origin.y) > int(canvas.height):
            errors.append(f"canvas origin below image bounds: {canvas.name}")
    if canvas_count != 285:
        errors.append(f"expected 285 canvases, got {canvas_count}")
    if formats != {1}:
        errors.append(f"expected ARGB4444 canvases, got formats {sorted(formats)}")

    strings = load_img(ROOT / "clien/Data/String/Mob.img")
    if value(strings.root.get(f"{TARGET_ID}/name")) != "戴斯克":
        errors.append("missing client Dusk name")
    if load_img(ROOT / "clien/Data/UI/UIWindow.img").root.get(f"MobGage/Mob/{TARGET_ID}") is None:
        errors.append(f"missing existing UIWindow boss gauge {TARGET_ID}")

    server_text = server_path.read_text(encoding="utf-8")
    if "skillAfter" in server_text:
        errors.append("unsupported skillAfter remains")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"dusk audit failed: errors={len(errors)} canvas={canvas_count}")
        return 1

    print(
        "dusk audit ok: "
        f"mob={TARGET_ID} source={SOURCE_ID} canvas={canvas_count} "
        f"format=ARGB4444 server_hp=5000000000 skills={len(SKILLS)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
