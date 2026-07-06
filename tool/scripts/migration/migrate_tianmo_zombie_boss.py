#!/usr/bin/env python3
"""Migrate the Tianmo Zombie boss into BeiDou with old-client-safe skill fallbacks."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import migrate_root_abyss_maps as base


ROOT = Path(__file__).resolve().parents[3]
SRC_CLIENT = Path("/Users/lizixian/Documents/mxd/神说/Data")
MOB_ID = 9600318
DEADLY_ATTACKS = ("attack1", "attack2")
CLIENT_SAFE_MAX_HP = 2_100_000_000
SERVER_MAX_HP = "5000000000"


CLIENT_MOBSKILL_PATH = ROOT / "clien/Data/Skill/MobSkill.img"
SERVER_MOBSKILL_PATH = ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml"
SERVER_STRING_PATHS = [
    ROOT / "gms-server/wz/String.wz/Mob.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Mob.img.xml",
]


def load_client_mobskill() -> base.WzImage:
    img = base.WzImage.from_bytes(
        CLIENT_MOBSKILL_PATH.read_bytes(),
        key=base.TARGET_KEY,
        name=CLIENT_MOBSKILL_PATH.name,
    )
    img.parse()
    return img


def best_supported_level(
    client_mobskill: base.WzImage,
    server_mobskill_root: ET.Element,
    skill_id: int,
    requested_level: int,
) -> int | None:
    server_skill = base.direct_xml_child(server_mobskill_root, str(skill_id))
    server_level_root = base.direct_xml_child(server_skill, "level") if server_skill is not None else None
    for level in range(requested_level, 0, -1):
        client_level = client_mobskill.get(f"{skill_id}/level/{level}")
        server_level = base.direct_xml_child(server_level_root, str(level)) if server_level_root is not None else None
        if client_level is not None and server_level is not None:
            return level
    return None


def available_skill_actions(root: base.WzSubProperty) -> list[int]:
    actions: list[int] = []
    for child in root.children():
        if child.name.startswith("skill") and child.name[5:].isdigit():
            actions.append(int(child.name[5:]))
    return sorted(actions)


def best_supported_action(requested_action: int | None, supported_actions: list[int]) -> int | None:
    if not supported_actions:
        return None
    if requested_action is None:
        return supported_actions[0]
    if requested_action in supported_actions:
        return requested_action
    return supported_actions[-1]


def sanitize_tianmo_zombie(root: base.WzSubProperty) -> None:
    info = root.child("info")
    if not isinstance(info, base.WzSubProperty):
        raise RuntimeError(f"Mob {MOB_ID} missing info")

    base.ensure_int_child(info, "mobType", 1)
    base.remove_child(info, "category")

    # Match the local Bloody Queen pattern: keep the projectile attack normal,
    # but make Tianmo's direct melee swings land as deadly hits.
    for attack_name in DEADLY_ATTACKS:
        attack = root.child(attack_name)
        if not isinstance(attack, base.WzSubProperty):
            continue
        attack_info = attack.child("info")
        if not isinstance(attack_info, base.WzSubProperty):
            continue
        base.ensure_int_child(attack_info, "deadlyAttack", 1)

    supported_actions = available_skill_actions(root)
    client_mobskill = load_client_mobskill()
    server_mobskill_root = ET.parse(SERVER_MOBSKILL_PATH).getroot()
    skill_root = info.child("skill")
    if not isinstance(skill_root, base.WzSubProperty):
        return

    sanitized_entries: list[tuple[int, int, int]] = []
    for entry in sorted(skill_root.children(), key=lambda child: int(child.name)):
        skill_id = base.child_value(entry, "skill")
        level = base.child_value(entry, "level")
        action = base.child_value(entry, "action")
        if skill_id is None or level is None:
            continue

        # Keep the boss on old-client-safe MobSkill levels and remap missing
        # skill animations to the highest available local skill action.
        supported_level = best_supported_level(client_mobskill, server_mobskill_root, int(skill_id), int(level))
        if supported_level is None:
            continue
        supported_action = best_supported_action(int(action) if action is not None else None, supported_actions)
        if supported_action is None:
            continue
        sanitized_entries.append((int(skill_id), supported_level, supported_action))

    base.remove_child(info, "skill")
    if not sanitized_entries:
        return

    new_skill_root = base.WzSubProperty("skill", info)
    for idx, (skill_id, level, action) in enumerate(sanitized_entries):
        entry = base.WzSubProperty(str(idx), new_skill_root)
        entry.add(base.WzIntProperty("skill", skill_id, entry))
        entry.add(base.WzIntProperty("level", level, entry))
        entry.add(base.WzIntProperty("action", action, entry))
        entry.add(base.WzIntProperty("effectAfter", 0, entry))
        new_skill_root.add(entry)
    info.add(new_skill_root)


def upsert_server_mob_strings() -> None:
    src = base.source_img(SRC_CLIENT / "String/Mob.img")
    source_node = src.get(str(MOB_ID))
    if source_node is None:
        raise RuntimeError(f"source String/Mob.img missing {MOB_ID}")

    block = base.property_to_xml(source_node, 1).strip()
    for path in SERVER_STRING_PATHS:
        text = path.read_text(encoding="utf-8")
        token = f'<imgdir name="{MOB_ID}"'
        idx = text.find(token)
        if idx >= 0:
            start, end = base.find_imgdir_span_at(text, idx)
            text = text[:start] + block + text[end:]
        else:
            insert_at = text.rfind("</imgdir>")
            if insert_at < 0:
                raise RuntimeError(f"{path} missing root closing imgdir")
            separator = "\n" if "\n" in text else ""
            text = text[:insert_at] + separator + block + separator + text[insert_at:]
        base.backup(path)
        base.atomic_write_text(path, text)


def enforce_server_long_hp(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'<(?:int|long|string) name="maxHP" value="[^"]*"/>',
        f'<string name="maxHP" value="{SERVER_MAX_HP}"/>',
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError(f"failed to rewrite maxHP in {path}")
    base.backup(path)
    base.atomic_write_text(path, updated)


def verify() -> None:
    client_mobskill = load_client_mobskill()
    mob_client = base.WzImage.from_bytes(
        (ROOT / f"clien/Data/Mob/{MOB_ID}.img").read_bytes(),
        key=base.TARGET_KEY,
        name=f"{MOB_ID}.img",
    )
    mob_client.parse()
    client_max_hp = mob_client.get("info/maxHP")
    if client_max_hp is None or int(client_max_hp.value) != CLIENT_SAFE_MAX_HP:
        raise RuntimeError(f"unexpected client maxHP: {client_max_hp}")

    skill_root = mob_client.get("info/skill")
    if not isinstance(skill_root, base.WzSubProperty):
        raise RuntimeError("migrated client mob missing info/skill")

    for entry in skill_root.children():
        skill_id = int(base.child_value(entry, "skill"))
        level = int(base.child_value(entry, "level"))
        action = int(base.child_value(entry, "action"))
        if mob_client.get(f"skill{action}") is None:
            raise RuntimeError(f"unsupported action persisted: skill{action}")
        if client_mobskill.get(f"{skill_id}/level/{level}") is None:
            raise RuntimeError(f"unsupported client MobSkill persisted: {skill_id}/{level}")

    for attack_name in DEADLY_ATTACKS:
        if mob_client.get(f"{attack_name}/info/deadlyAttack") is None:
            raise RuntimeError(f"missing deadlyAttack on {attack_name}")

    server_root = ET.parse(ROOT / f"gms-server/wz/Mob.wz/{MOB_ID}.img.xml").getroot()
    server_info = base.direct_xml_child(server_root, "info")
    server_max_hp = base.direct_xml_child(server_info, "maxHP")
    if server_max_hp is None or server_max_hp.tag != "string" or server_max_hp.get("value") != SERVER_MAX_HP:
        raise RuntimeError(f"unexpected server maxHP: {server_max_hp}")


def main() -> int:
    src = SRC_CLIENT / f"Mob/{MOB_ID}.img"
    client_dst = ROOT / f"clien/Data/Mob/{MOB_ID}.img"
    server_dst = ROOT / f"gms-server/wz/Mob.wz/{MOB_ID}.img.xml"

    print("client mob", base.reencode_img(src, client_dst, sanitizer=sanitize_tianmo_zombie))
    print("server mob", base.write_server_xml_from_source(src, server_dst, sanitizer=sanitize_tianmo_zombie))
    enforce_server_long_hp(server_dst)
    base.upsert_client_string("Mob", [MOB_ID])
    upsert_server_mob_strings()
    verify()
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
