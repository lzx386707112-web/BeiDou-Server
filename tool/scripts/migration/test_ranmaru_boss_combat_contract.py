#!/usr/bin/env python3
"""Static contract for Ranmaru HP, projected skills, enter scripts, and 1% drops."""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tool/scripts/migration/patch_ranmaru_boss_combat.py"
SPEC = importlib.util.spec_from_file_location("patch_ranmaru_boss_combat", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
patch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(patch)

from wzpy import WzSubProperty  # noqa: E402

ITEM_FOLDER = {
    100: "Cap",
    105: "Longcoat",
    107: "Shoes",
    108: "Glove",
    110: "Cape",
    113: "Accessory",
}


def item_xml(item_id: int) -> Path:
    prefix = item_id // 10000
    folder = ITEM_FOLDER.get(prefix, "Weapon")
    return ROOT / f"gms-server/wz/Character.wz/{folder}/{item_id:08d}.img.xml"


def hashes() -> dict[str, str]:
    paths = [
        patch.client_mob_path(patch.NORMAL_BOSS_ID),
        patch.client_mob_path(patch.HARD_BOSS_ID),
        patch.ranmaru.client_map_path(patch.ranmaru.NORMAL_BATTLE),
        patch.ranmaru.client_map_path(patch.ranmaru.HARD_BATTLE),
        patch.server_mob_path(patch.NORMAL_BOSS_ID),
        patch.server_mob_path(patch.HARD_BOSS_ID),
        patch.DROP_SQL,
        patch.CLIENT_MOBSKILL,
        patch.SERVER_MOBSKILL,
    ]
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def expect_skill_levels(errors: list[str]) -> None:
    xml = ET.parse(ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml").getroot()
    client = patch.parse_img(
        (ROOT / "clien/Data/Skill/MobSkill.img").read_bytes(), "MobSkill.img"
    )
    for skill_id, dest, _src in patch.MOBSKILL_CLONES + ((176, 10, 6),):
        level_root = client.root.get(f"{skill_id}/level")
        names = sorted(
            int(child.name)
            for child in (level_root.children() if level_root is not None else [])
            if child.name.isdigit()
        )
        required = list(range(1, dest + 1))
        if names[:dest] != required:
            errors.append(f"client MobSkill {skill_id} not contiguous 1..{dest}: {names}")
        xml_node = xml.find(
            f'./imgdir[@name="{skill_id}"]/imgdir[@name="level"]/imgdir[@name="{dest}"]'
        )
        if xml_node is None:
            errors.append(f"missing server MobSkill {skill_id}/{dest}")
    node = client.root.get("176/level/10")
    if node is None:
        return
    if node.child("screen") is not None or node.child("lua") is not None:
        errors.append("client 176/10 has screen/lua")
    if int(patch.arc.child_value(node, "x") or 0) == 999999:
        errors.append("client 176/10 has x=999999")
    hit = node.child("hit")
    if hit is None:
        errors.append("client 176/10 missing hit")
    else:
        from wzpy import WzCanvasProperty  # noqa: E402
        from wzpy.canvas import decode_canvas  # noqa: E402

        canvases = 0
        digits = []
        for child in hit.children():
            if child.name.isdigit():
                digits.append(int(child.name))
            if not isinstance(child, WzCanvasProperty):
                continue
            canvases += 1
            if int(child.format) != 1 or int(child.format2) != 0:
                errors.append(f"176/10 hit/{child.name} format {child.format}/{child.format2}")
            decoded = decode_canvas(child, region="GMS")
            if decoded.size != (int(child.width), int(child.height)):
                errors.append(f"176/10 hit/{child.name} decode size mismatch")
        if canvases == 0:
            errors.append("client 176/10 hit has no canvases")
        digits = sorted(digits)
        if digits and digits != list(range(digits[0], digits[-1] + 1)):
            errors.append(f"client 176/10 hit has numeric gaps {digits}")
    xml_176 = xml.find('./imgdir[@name="176"]/imgdir[@name="level"]/imgdir[@name="10"]')
    if xml_176 is not None:
        if xml_176.find('./imgdir[@name="screen"]') is not None or xml_176.find('./string[@name="lua"]') is not None:
            errors.append("server 176/10 has screen/lua")
        x_node = xml_176.find('./int[@name="x"]')
        if x_node is not None and x_node.get("value") == "999999":
            errors.append("server 176/10 has x=999999")


def main() -> int:
    errors: list[str] = []
    expect_skill_levels(errors)

    for mob_id, hp, entries in (
        (patch.NORMAL_BOSS_ID, patch.ZAKUM_HP, patch.NORMAL_SKILLS),
        (patch.HARD_BOSS_ID, patch.HORNTAIL_HP, patch.HARD_SKILLS),
    ):
        image = patch.parse_img(patch.client_mob_path(mob_id).read_bytes(), f"{mob_id}.img")
        info = image.root.child("info")
        if int(patch.arc.child_value(info, "maxHP") or 0) != hp:
            errors.append(f"{mob_id} client HP {patch.arc.child_value(info, 'maxHP')} != {hp}")
        if not patch.skill_matches(info, entries):
            errors.append(f"{mob_id} client skill table mismatch")
        for child in image.root.children():
            if not child.name.startswith("attack"):
                continue
            attack_info = child.child("info") if isinstance(child, WzSubProperty) else None
            if isinstance(attack_info, WzSubProperty) and attack_info.child("ball") is not None:
                errors.append(f"{mob_id} {child.name} has ball without this patch handling it")
        skill = info.child("skill") if isinstance(info, WzSubProperty) else None
        if isinstance(skill, WzSubProperty):
            for slot in skill.children():
                skill_id = int(patch.arc.child_value(slot, "skill") or 0)
                action = int(patch.arc.child_value(slot, "action") or 0)
                level = int(patch.arc.child_value(slot, "level") or 0)
                if skill_id in {170, 174, 185}:
                    errors.append(f"{mob_id} still binds crash skill {skill_id}")
                if skill_id == 176:
                    if mob_id != patch.HARD_BOSS_ID or action != 5 or level != 10:
                        errors.append(
                            f"{mob_id} 176 bind is {action}/{level}, expected hard action 5 level 10"
                        )
                elif action == 5:
                    errors.append(f"{mob_id} still casts skill5 via action {action}")
        skill5 = image.root.child("skill5")
        if isinstance(skill5, WzSubProperty):
            for frame in skill5.children():
                width = int(getattr(frame, "width", 0) or 0)
                height = int(getattr(frame, "height", 0) or 0)
                if width > patch.MAX_SKILL5_EDGE or height > patch.MAX_SKILL5_EDGE:
                    errors.append(f"{mob_id} skill5/{frame.name} {width}x{height} exceeds {patch.MAX_SKILL5_EDGE}")
        xml = ET.parse(patch.server_mob_path(mob_id)).getroot()
        hp_node = xml.find('./imgdir[@name="info"]/int[@name="maxHP"]')
        if hp_node is None or hp_node.get("value") != str(hp):
            errors.append(f"{mob_id} server HP mismatch")
        if not patch.xml_skill_matches(xml, entries):
            errors.append(f"{mob_id} server skill table mismatch")

    for map_id in patch.BATTLE_MAPS:
        image = patch.parse_img(
            patch.ranmaru.client_map_path(map_id).read_bytes(), f"{map_id}.img"
        )
        info = image.root.child("info")
        if str(patch.arc.child_value(info, "onUserEnter") or "") != patch.ON_USER_ENTER:
            errors.append(f"map {map_id} missing onUserEnter")
        if str(patch.arc.child_value(info, "onFirstUserEnter") or "") != patch.ON_FIRST_USER_ENTER:
            errors.append(f"map {map_id} missing onFirstUserEnter")
        if info.child("fieldScript") is not None:
            errors.append(f"map {map_id} kept modern fieldScript")
        xml = ET.parse(patch.ranmaru.server_map_path("wz", map_id)).getroot()
        enter = xml.find('./imgdir[@name="info"]/string[@name="onUserEnter"]')
        first = xml.find('./imgdir[@name="info"]/string[@name="onFirstUserEnter"]')
        if enter is None or enter.get("value") != patch.ON_USER_ENTER:
            errors.append(f"map {map_id} server onUserEnter mismatch")
        if first is None or first.get("value") != patch.ON_FIRST_USER_ENTER:
            errors.append(f"map {map_id} server onFirstUserEnter mismatch")

    sql = patch.DROP_SQL.read_text(encoding="utf-8")
    if f", {patch.DROP_CHANCE})" not in sql and f", {patch.DROP_CHANCE} " not in sql:
        errors.append("drop SQL missing 1% chance")
    for item_id, name in (*patch.NORMAL_DROPS, *patch.HARD_DROPS):
        if str(item_id) not in sql:
            errors.append(f"drop SQL missing {item_id} {name}")
        path = item_xml(item_id)
        if not path.is_file():
            errors.append(f"missing Character XML {path.name}")

    for tree in patch.SCRIPT_TREES:
        enter = tree / "map/onUserEnter" / f"{patch.ON_USER_ENTER}.js"
        first = tree / "map/onFirstUserEnter" / f"{patch.ON_FIRST_USER_ENTER}.js"
        if not enter.is_file():
            errors.append(f"missing {enter}")
        if not first.is_file():
            errors.append(f"missing {first}")

    java = (ROOT / "gms-server/src/main/java/org/gms/server/life/MobSkill.java").read_text(
        encoding="utf-8"
    )
    if "applyRanmaruScreenCrack" not in java or "isMoriRanmaruHard" not in java:
        errors.append("MobSkill.java missing Ranmaru skill5 percent damage")
    if "MobSkillType.MAGIC_ATTACK_UP && MobId.isMoriRanmaruHard" in java:
        errors.append("MobSkill.java still projects Ranmaru 176 onto 101")
    if "AKAYRUM_SCREEN_CRACK_VISUAL" not in java or "applyRanmaruScreenCrack(monster)" not in java:
        errors.append("MobSkill.java missing Ranmaru 176/10 percent damage")

    before = hashes()
    subprocess.check_call([sys.executable, str(SCRIPT)], cwd=ROOT)
    after = hashes()
    if before != after:
        errors.append("generator is not idempotent")

    if errors:
        print("FAILED")
        for error in errors:
            print(error)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
