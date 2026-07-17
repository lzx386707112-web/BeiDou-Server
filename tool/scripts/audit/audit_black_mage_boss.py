#!/usr/bin/env python3
"""Audit the mobile-safe Boss-only Black Mage chain."""

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
from patch_black_mage_boss_compat import (  # noqa: E402
    BLACK_MAGE_IDS,
    CUSTOM_SKILLS,
    FIELD_EFFECT_NAME,
    FIELD_EFFECT_ROOT,
    MAIN_IDS,
    NAMES,
    REVIVE,
    SKILLS,
    SPIRIT_IDS,
    SUPPORT_HP,
    SUPPORT_IDS,
    VISUALS,
)


MOB_IDS = BLACK_MAGE_IDS
EXPECTED_CANVAS = {
    8880500: 116,
    8880501: 131,
    8880502: 227,
    8880503: 139,
    8880504: 224,
    8880505: 74,
    8880506: 61,
    8880507: 16,
    8880511: 48,
}
EXPECTED_EFFECT_CANVAS = 39
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

    for mob_id in MOB_IDS:
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
        if mob_id in MAIN_IDS or mob_id in SPIRIT_IDS:
            expected_client_hp = 2_000_000_000
        else:
            expected_client_hp = SUPPORT_HP[mob_id]
        if value(info.child("maxHP")) != expected_client_hp:
            errors.append(f"client maxHP {mob_id}: expected {expected_client_hp}")
        if value(info.child("PDRate")) != 50 or value(info.child("MDRate")) != 50:
            errors.append(f"client defense rates {mob_id} must be 50")
        if mob_id == 8880502:
            if info.child("buff") is not None:
                errors.append("8880502: unsupported info/buff remains")
            for action in range(1, 7):
                if client.root.child(f"skill{action}") is None:
                    errors.append(f"8880502: restored skill{action} is missing")

        expected_specs = SKILLS.get(mob_id, ())
        skill_root = info.child("skill")
        actual_specs = [] if skill_root is None else [
            (value(entry.child("skill")), value(entry.child("level")), value(entry.child("action")))
            for entry in skill_root.children()
        ]
        if tuple(actual_specs) != expected_specs:
            errors.append(f"client skills {mob_id}: expected {expected_specs}, got {actual_specs}")

        server_info = server.find('./imgdir[@name="info"]')
        server_hp = None if server_info is None else server_info.find('./string[@name="maxHP"]')
        if mob_id in MAIN_IDS:
            expected_hp = "20000000000"
        elif mob_id in SPIRIT_IDS:
            expected_hp = "2000000000"
        else:
            expected_hp = str(SUPPORT_HP[mob_id])
        if server_hp is None or server_hp.attrib.get("value") != expected_hp:
            errors.append(f"server maxHP {mob_id}: expected {expected_hp}")

        server_skill_root = None if server_info is None else server_info.find('./imgdir[@name="skill"]')
        server_specs = []
        if server_skill_root is not None:
            for entry in server_skill_root.findall("imgdir"):
                server_specs.append(tuple(int(entry.find(f'./int[@name="{name}"]').attrib["value"]) for name in ("skill", "level", "action")))
        if tuple(server_specs) != expected_specs:
            errors.append(f"server skills {mob_id}: expected {expected_specs}, got {server_specs}")

        for action, source_name in VISUALS.get(mob_id, {}).items():
            group = client.root.child(f"skill{action}")
            frames = [] if group is None else [child for child in group.children() if child.name.isdigit()]
            if not frames:
                errors.append(f"{mob_id}/skill{action}: missing frames")
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
    if clients.get(8880504) is not None and clients[8880504].root.get("info/revive") is not None:
        errors.append("final Black Mage stage must not revive")

    client_mobskill = load_img(ROOT / "clien/Data/Skill/MobSkill.img")
    server_mobskill = ET.parse(ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml").getroot()
    all_specs = {(skill, level) for specs in SKILLS.values() for skill, level, _ in specs}
    for skill, level in sorted(all_specs):
        if client_mobskill.root.get(f"{skill}/level/{level}") is None:
            errors.append(f"missing client MobSkill {skill}/{level}")
        if not xml_level_exists(server_mobskill, skill, level):
            errors.append(f"missing server MobSkill {skill}/{level}")
    mobskill_root_names = [child.name for child in client_mobskill.root.children()]
    expected_custom_names = tuple(str(skill_id) for skill_id in CUSTOM_SKILLS)
    if tuple(mobskill_root_names[-len(expected_custom_names):]) != expected_custom_names:
        errors.append("custom Black Mage MobSkill nodes must be append-only root entries")

    enum_text = (ROOT / "gms-server/src/main/java/org/gms/server/life/MobSkillType.java").read_text(encoding="utf-8")
    for skill in sorted({skill for skill, _ in all_specs}):
        if not re.search(rf"\({skill}\)", enum_text):
            errors.append(f"MobSkillType enum missing {skill}")

    life_factory_text = (ROOT / "gms-server/src/main/java/org/gms/server/life/LifeFactory.java").read_text(encoding="utf-8")
    monster_text = (ROOT / "gms-server/src/main/java/org/gms/server/life/Monster.java").read_text(encoding="utf-8")
    move_life_text = (ROOT / "gms-server/src/main/java/org/gms/net/server/channel/handlers/MoveLifeHandler.java").read_text(encoding="utf-8")
    if 'getInt(i + "/action", monsterSkillInfoData, i + 1)' not in life_factory_text:
        errors.append("LifeFactory must resolve skill animation from the declared action")
    if "getSkillsInRandomOrder()" not in monster_text or "monster.getSkillsInRandomOrder()" not in move_life_text:
        errors.append("monster skill selection must retry randomized candidates")

    effect_img = load_img(ROOT / "clien/Data/Map/Effect.img")
    field_effect = effect_img.root.get(f"{FIELD_EFFECT_ROOT}/{FIELD_EFFECT_NAME}")
    effect_canvases = [] if field_effect is None else list(walk_canvas(field_effect))
    if len(effect_canvases) != EXPECTED_EFFECT_CANVAS:
        errors.append(f"field effect: expected {EXPECTED_EFFECT_CANVAS} canvases, got {len(effect_canvases)}")
    for canvas in effect_canvases:
        if int(canvas.format) + int(canvas.format2) != 1:
            errors.append(f"field effect frame {canvas.name}: expected ARGB4444")
        try:
            decode_canvas(canvas, region="GMS")
        except Exception as exc:
            errors.append(f"field effect decode failed {canvas.name}: {exc}")

    strings = load_img(ROOT / "clien/Data/String/Mob.img")
    for mob_id, name in NAMES.items():
        if value(strings.root.get(f"{mob_id}/name")) != name:
            errors.append(f"missing client name {mob_id}")
    ui = load_img(ROOT / "clien/Data/UI/UIWindow.img")
    for mob_id in MAIN_IDS:
        if ui.root.get(f"MobGage/Mob/{mob_id}") is None:
            errors.append(f"missing existing UIWindow boss gauge {mob_id}")

    for mob_id in MOB_IDS:
        server_info = servers[mob_id].find('./imgdir[@name="info"]')
        if server_info is not None:
            serialized = ET.tostring(server_info, encoding="unicode")
            if "skillAfter" in serialized or "effectAfter" in serialized:
                errors.append(f"{mob_id}: skill timing metadata remains")
    unsupported = ((136, 26), (133, 14), (126, 18))
    for mob_id in MOB_IDS:
        specs = {(skill, level) for skill, level, _ in SKILLS.get(mob_id, ())}
        for spec in unsupported:
            if spec in specs:
                errors.append(f"unsupported skill remains {mob_id}: {spec}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"black mage audit failed: errors={len(errors)} canvas={canvas_total}")
        return 1

    print(
        "black mage audit ok: "
        f"mobs={len(MOB_IDS)} mob_canvas={canvas_total} effect_canvas={len(effect_canvases)} "
        f"source_canvas={canvas_total + len(effect_canvases)} format=ARGB4444 "
        f"stages={len(MAIN_IDS)} stage_hp=20000000000 skills={sum(len(v) for v in SKILLS.values())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
