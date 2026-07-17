#!/usr/bin/env python3
"""Audit the mobile-safe five-stage Boss-only Chosen Seren chain."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
sys.path.insert(0, str(ROOT / "tool" / "scripts" / "patch-boss"))

from wzpy import WzCanvasProperty, WzImage, WzKey, WzUolProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from patch_seren_boss_compat import NAMES, REVIVE, SKILLS, SOURCE_BY_TARGET, TARGET_IDS, VISUALS  # noqa: E402


EXPECTED_CANVAS = {8880340: 97, 8880341: 92, 8880342: 157, 8880343: 102, 8880344: 99}
SKILLS = dict(SKILLS)
SKILLS[8880342] = SKILLS[8880342] + ((187, 1, 3),)
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
    clients: dict[int, WzImage] = {}
    servers: dict[int, ET.Element] = {}
    canvas_total = 0

    for mob_id in TARGET_IDS:
        client_path = ROOT / f"clien/Data/Mob/{mob_id}.img"
        server_path = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
        if not client_path.exists() or not server_path.exists():
            errors.append(f"missing client/server Mob {mob_id}")
            continue
        client = load_img(client_path)
        server = ET.parse(server_path).getroot()
        clients[mob_id] = client
        servers[mob_id] = server

        canvases = list(walk_canvas(client.root))
        canvas_total += len(canvases)
        if len(canvases) != EXPECTED_CANVAS[mob_id]:
            errors.append(f"{mob_id}: expected {EXPECTED_CANVAS[mob_id]} canvases, got {len(canvases)}")
        formats = {int(canvas.format) + int(canvas.format2) for canvas in canvases}
        if formats != {1}:
            errors.append(f"{mob_id}: expected ARGB4444, got {sorted(formats)}")
        for canvas in canvases:
            try:
                decode_canvas(canvas, region="GMS")
            except Exception as exc:
                errors.append(f"canvas decode failed {mob_id}/{canvas.name}: {exc}")

        info = client.root.get("info")
        if value(info.child("maxHP")) != 2_000_000_000:
            errors.append(f"client maxHP {mob_id} must be 2000000000")
        if value(info.child("PDRate")) != 50 or value(info.child("MDRate")) != 50:
            errors.append(f"client defense rates {mob_id} must be 50")

        expected_specs = SKILLS[mob_id]
        skill_root = info.child("skill")
        actual_specs = [] if skill_root is None else [
            (value(entry.child("skill")), value(entry.child("level")), value(entry.child("action")))
            for entry in skill_root.children()
        ]
        if tuple(actual_specs) != expected_specs:
            errors.append(f"client skills {mob_id}: expected {expected_specs}, got {actual_specs}")

        server_info = server.find('./imgdir[@name="info"]')
        server_hp = None if server_info is None else server_info.find('./string[@name="maxHP"]')
        if server_hp is None or server_hp.attrib.get("value") != "5000000000":
            errors.append(f"server maxHP {mob_id}: expected 5000000000")
        server_skill_root = None if server_info is None else server_info.find('./imgdir[@name="skill"]')
        server_specs = []
        if server_skill_root is not None:
            for entry in server_skill_root.findall("imgdir"):
                server_specs.append(tuple(int(entry.find(f'./int[@name="{name}"]').attrib["value"]) for name in ("skill", "level", "action")))
        if tuple(server_specs) != expected_specs:
            errors.append(f"server skills {mob_id}: expected {expected_specs}, got {server_specs}")

        for action, source_name in VISUALS[mob_id].items():
            group = client.root.child(f"skill{action}")
            frames = [] if group is None else [child for child in group.children() if child.name.isdigit()]
            if not frames:
                errors.append(f"{mob_id}/skill{action}: missing frames from {source_name}")
            elif source_name != f"skill{action}":
                if not all(isinstance(frame, WzUolProperty) for frame in frames):
                    errors.append(f"{mob_id}/skill{action}: expected UOL frames")
                elif not all(str(frame.value).startswith(f"../{source_name}/") for frame in frames):
                    errors.append(f"{mob_id}/skill{action}: wrong visual source {source_name}")
            if server.find(f'./imgdir[@name="skill{action}"]') is None:
                errors.append(f"missing server {mob_id}/skill{action}")

    for mob_id, target in REVIVE.items():
        if value(clients[mob_id].root.get("info/revive/0")) != target:
            errors.append(f"client revive {mob_id}: expected {target}")
        node = servers[mob_id].find('./imgdir[@name="info"]/imgdir[@name="revive"]/int[@name="0"]')
        if node is None or int(node.attrib["value"]) != target:
            errors.append(f"server revive {mob_id}: expected {target}")
    final_id = TARGET_IDS[-1]
    if clients.get(final_id) is not None and clients[final_id].root.get("info/revive") is not None:
        errors.append("final Seren stage must not revive")

    client_mobskill = load_img(ROOT / "clien/Data/Skill/MobSkill.img")
    server_mobskill = ET.parse(ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml").getroot()
    all_specs = {(skill, level) for specs in SKILLS.values() for skill, level, _ in specs}
    for skill, level in sorted(all_specs):
        if client_mobskill.root.get(f"{skill}/level/{level}") is None:
            errors.append(f"missing client MobSkill {skill}/{level}")
        if not xml_level_exists(server_mobskill, skill, level):
            errors.append(f"missing server MobSkill {skill}/{level}")

    enum_text = (ROOT / "gms-server/src/main/java/org/gms/server/life/MobSkillType.java").read_text(encoding="utf-8")
    for skill in sorted({skill for skill, _ in all_specs}):
        if not re.search(rf"\({skill}\)", enum_text):
            errors.append(f"MobSkillType enum missing {skill}")

    strings = load_img(ROOT / "clien/Data/String/Mob.img")
    for mob_id, name in NAMES.items():
        if value(strings.root.get(f"{mob_id}/name")) != name:
            errors.append(f"missing client name {mob_id}")
    root_names = [child.name for child in strings.root.children()]
    if tuple(root_names[-len(TARGET_IDS):]) != tuple(str(mob_id) for mob_id in TARGET_IDS):
        errors.append("client Seren names must be the last append-only String/Mob entries")
    for path in (
        ROOT / "gms-server/wz/String.wz/Mob.img.xml",
        ROOT / "gms-server/wz-zh-CN/String.wz/Mob.img.xml",
    ):
        server_strings = ET.parse(path).getroot()
        for mob_id, name in NAMES.items():
            node = server_strings.find(f'./imgdir[@name="{mob_id}"]/string[@name="name"]')
            if node is None or node.attrib.get("value") != name:
                errors.append(f"missing server name {mob_id} in {path}")
    ui = load_img(ROOT / "clien/Data/UI/UIWindow.img")
    for mob_id in TARGET_IDS:
        if ui.root.get(f"MobGage/Mob/{mob_id}") is None:
            errors.append(f"missing existing UIWindow boss gauge alias {mob_id}")

    source_mechanism_ids = {8880614, 8880615, 8880616, 8880617, 8880618}
    for mob_id, client in clients.items():
        revive = client.root.get("info/revive")
        revive_values = set() if revive is None else {value(entry) for entry in revive.children()}
        if revive_values & source_mechanism_ids:
            errors.append(f"{mob_id}: source map-mechanism revive remains")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"seren audit failed: errors={len(errors)} canvas={canvas_total}")
        return 1

    print(
        "seren audit ok: "
        f"sources={tuple(SOURCE_BY_TARGET.values())} targets={TARGET_IDS} "
        f"canvas={canvas_total} format=ARGB4444 stages={len(TARGET_IDS)} "
        f"stage_hp=5000000000 skills={sum(len(v) for v in SKILLS.values())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
