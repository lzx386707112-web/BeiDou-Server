#!/usr/bin/env python3
"""Align the four Root Abyss boss phase/skill contracts with TMS.

Existing GMS IMG files are changed only by scalar patches, raw record
replacement, or raw record append.  Modern MobSkill IDs are projected onto
reserved 200/* client levels; the server XML keeps the real TMS IDs.
"""

from __future__ import annotations

import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TMS_DATA = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
sys.path.insert(0, str(ROOT / "tool/resource-workbench"))

from map_mob import app  # noqa: E402
from wzpy import (  # noqa: E402
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.incremental_img import replace_img_record  # noqa: E402


MOB_INFO = {
    8900000: {"level": 190, "maxHP": 400_000_000, "maxMP": 108_000, "boss": 1},
    8900001: {"level": 190, "maxHP": 400_000_000, "maxMP": 108_000, "boss": 1},
    8900002: {"level": 190, "maxHP": 400_000_000, "maxMP": 108_000, "boss": 1},
    8910000: {"level": 190, "maxHP": 400_000_000, "maxMP": 100_000, "boss": 1},
    8910001: {"level": 190, "maxHP": 400_000_000, "maxMP": 100_000, "boss": 1},
    8920000: {"level": 190, "maxHP": 400_000_000, "maxMP": 15_000_000, "boss": 1},
    8920001: {"level": 190, "maxHP": 400_000_000, "maxMP": 15_000_000, "boss": 1},
    8920002: {"level": 190, "maxHP": 400_000_000, "maxMP": 15_000_000, "boss": 1},
    8920004: {"level": 190, "maxHP": 20, "maxMP": 200, "boss": 1},
    8920005: {"level": 190, "maxHP": 550_000_000, "maxMP": 15_000_000, "boss": 1},
    8930000: {"level": 190, "maxHP": 600_000_000, "maxMP": 64_500, "boss": 1},
    8930001: {"level": 190, "maxHP": 600_000_000, "maxMP": 64_500, "boss": 1},
}

SERVER_SKILLS = {
    8900000: ({"skill": 201, "action": 1, "level": 40, "afterDead": 1},),
    8900001: ({"skill": 170, "action": 1, "level": 10, "skillForbid": 2160,
               "afterAttack": 1, "afterAttackCount": 1},),
    8910000: (
        {"skill": 203, "action": 1, "level": 1},
        {"skill": 184, "action": 2, "level": 1, "skillAfter": 1440},
        {"skill": 170, "action": 3, "level": 11, "effectAfter": 0,
         "skillForbid": 1200, "afterAttack": 3, "afterAttackCount": 1},
        {"skill": 191, "action": 4, "level": 1},
        {"skill": 191, "action": 5, "level": 2},
        {"skill": 170, "action": 6, "level": 14, "skillForbid": 1200},
    ),
    8920000: (
        {"skill": 201, "action": 1, "level": 47, "skillAfter": 1620},
        {"skill": 201, "action": 2, "level": 48, "skillAfter": 2160},
        {"skill": 201, "action": 3, "level": 52, "afterDead": 1},
        {"skill": 201, "action": 4, "level": 53, "afterDead": 1},
    ),
    8920001: (
        {"skill": 186, "action": 1, "level": 1, "skillAfter": 960},
        {"skill": 201, "action": 2, "level": 51, "afterDead": 1},
        {"skill": 201, "action": 3, "level": 53, "afterDead": 1},
    ),
    8920002: (
        {"skill": 183, "action": 1, "level": 1, "skillAfter": 1440},
        {"skill": 201, "action": 2, "level": 51, "afterDead": 1},
        {"skill": 201, "action": 3, "level": 52, "afterDead": 1},
    ),
    8920005: ({"skill": 188, "action": 1, "level": 1, "skillAfter": 720},),
    8930000: ({"skill": 170, "action": 1, "level": 13, "skillForbid": 4000,
               "afterAttack": 8, "afterAttackCount": 1},),
}

PROJECTED_LEVEL = {
    (170, 10): 237, (170, 11): 238, (170, 13): 239, (170, 14): 240,
    (191, 1): 241, (191, 2): 242,
    (201, 40): 243, (201, 47): 244, (201, 48): 245,
    (201, 51): 246, (201, 52): 247, (201, 53): 248,
    (203, 1): 249, (188, 1): 250,
}

CLIENT_SKILLS = {
    mob_id: tuple(
        {
            "skill": entry["skill"] if entry["skill"] in {183, 184, 186}
            else 200,
            "action": entry["action"],
            "level": entry["level"] if entry["skill"] in {183, 184, 186}
            else PROJECTED_LEVEL[(entry["skill"], entry["level"])],
        }
        for entry in entries
    )
    for mob_id, entries in SERVER_SKILLS.items()
}

PROJECTED_MOB_SKILLS = {
    237: {"info": "混沌红色皮埃尔", "x": 5, "interval": 9},
    238: {"info": "半半", "x": 3, "interval": 6},
    239: {"info": "贝伦", "x": 3, "interval": 60, "fieldScript": 1},
    240: {"info": "半半", "x": 5, "interval": 10, "fieldScript": 1},
    241: {"mpCon": 5, "interval": 10, "time": 20, "prop": 100,
          "lt": (-201, -222), "rb": (201, 33), "x": 15, "rangeGap": 150},
    242: {"mpCon": 5, "interval": 10, "time": 20, "prop": 100,
          "lt": (-201, -222), "rb": (201, 33), "x": -15, "rangeGap": 150},
    243: {"hp": 31, "limit": 2, "0": 8900001, "1": 8900002,
          "linkHP": 1, "summonEffect": -2},
    244: {"interval": 20, "hp": 100, "limit": 1, "summonEffect": -2,
          "0": 8920005, "lt": (-790, -800), "rb": (790, 0), "targetType": 1},
    245: {"interval": 10, "hp": 100, "limit": 50,
          **{str(i): 8920004 for i in range(12)}, "summonEffect": -2,
          "lt": (-1024, -800), "rb": (1024, 0)},
    246: {"hp": 100, "limit": 1, "0": 8920000, "linkHP": 1,
          "summonEffect": -2, "fieldScript": 1, "afterEffect": 35, "interval": 0},
    247: {"hp": 100, "limit": 1, "0": 8920001, "linkHP": 1,
          "summonEffect": -2, "afterEffect": 35, "interval": 0, "fieldScript": 1},
    248: {"hp": 100, "limit": 1, "0": 8920002, "linkHP": 1,
          "summonEffect": -2, "fieldScript": 1, "afterEffect": 35, "interval": 0},
    249: {"mpCon": 5, "interval": 45, "time": 10, "prop": 100,
          "fieldScript": 1, "tremble": 1},
    250: {"prop": 100, "count": 1, "interval": 30, "x": 50,
          "bossHeal": 20, "face": "love", "afterEffect": 3},
}

SERVER_MOB_SKILL_LEVELS = {
    (170, 10): PROJECTED_MOB_SKILLS[237],
    (183, 1): {"mpCon": 5, "interval": 5, "prop": 100, "count": 6,
               "time": 900, "x": 4000, "limit": 3, "y": 1,
               "lt": (-6000, -2000), "rb": (6000, 2000)},
    (188, 1): PROJECTED_MOB_SKILLS[250],
}

MISSING_ACTIONS = {
    8910000: ("skillAfter1",),
}

PLACEHOLDER_AFTER_ACTIONS = {8900001: ("skillAfter1",), 8910000: ("skillAfter3", "skillAfter6")}


def make_values_node(name: str, values: dict[str, object]) -> WzSubProperty:
    node = WzSubProperty(name)
    for field, value in values.items():
        if isinstance(value, tuple):
            child = WzVectorProperty(field, int(value[0]), int(value[1]), node)
        elif isinstance(value, str) and not value.lstrip("-").isdigit():
            child = WzStringProperty(field, value, node)
        else:
            child = WzIntProperty(field, int(value), node)
        node.add(child)
    return node


def make_skill_table(entries: tuple[dict[str, int], ...]) -> WzSubProperty:
    table = WzSubProperty("skill")
    for index, values in enumerate(entries):
        record = make_values_node(str(index), values)
        record.parent = table
        table.add(record)
    return table


def sync_img_record(path: Path, node_path: tuple[str, ...], node: WzSubProperty) -> None:
    original = path.read_bytes()
    image = app._verified_img_from_bytes(path, original)
    if image.root.get("/".join(node_path)) is None:
        output = app.arc.append_property_record(original, node_path[:-1], node)
        app.arc.verify_raw_record_insert_scope(original, output, {node_path})
    else:
        output = replace_img_record(original, node_path, node, region="GMS").data
        app.verify_img_replace_scope(original, output, node_path, label="鲁塔比斯合同")
    if output != original:
        app.atomic_write(path, output, backup=True)
        app._load_image_cached.cache_clear()


def sync_xml_record(path: Path, node_path: str, node: WzSubProperty) -> None:
    spans = app.index_xml(path.read_bytes())
    if node_path in spans:
        app.xml_replace_cloned_node(path, node_path, node, dry_run=False, backup=True)
    else:
        app.xml_add_cloned_node(
            path, node_path.rpartition("/")[0], node, dry_run=False, backup=True,
        )


def sync_mob_info() -> None:
    for mob_id, values in MOB_INFO.items():
        client = ROOT / f"clien/Data/Mob/{mob_id}.img"
        server = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
        for field, value in values.items():
            app.patch_img(client, f"info/{field}", value, dry_run=False, backup=True)
            app.patch_xml_value(server, f"info/{field}", value, dry_run=False, backup=True)

        entries = SERVER_SKILLS.get(mob_id)
        # The later Vellum activation owns its expanded info/skill table.
        if entries is not None and not (mob_id == 8930000
                                    and app.load_image(client).root.get("skill7") is not None):
            sync_img_record(client, ("info", "skill"), make_skill_table(CLIENT_SKILLS[mob_id]))
            sync_xml_record(server, "info/skill", make_skill_table(entries))

    queen_client = ROOT / "clien/Data/Mob/8920000.img"
    queen_server = ROOT / "gms-server/wz/Mob.wz/8920000.img.xml"
    if app.load_image(queen_client).root.get("info/revive") is not None:
        app.patch_img_delete(queen_client, "info/revive", dry_run=False, backup=True)
    if "info/revive" in app.index_xml(queen_server.read_bytes()):
        app.xml_delete_node(queen_server, "info/revive", dry_run=False, backup=True)


def sync_projected_mob_skills() -> None:
    client = ROOT / "clien/Data/Skill/MobSkill.img"
    for level, values in PROJECTED_MOB_SKILLS.items():
        if level == 239 and app.load_image(client).root.get("200/level/239/limit") is not None:
            continue  # The active Vellum projection extends this legacy record.
        sync_img_record(client, ("200", "level", str(level)), make_values_node(str(level), values))

    server = ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml"
    for (skill_id, level), values in SERVER_MOB_SKILL_LEVELS.items():
        spans = app.index_xml(server.read_bytes())
        if str(skill_id) not in spans:
            skill = WzSubProperty(str(skill_id))
            levels = WzSubProperty("level", skill)
            record = make_values_node(str(level), values)
            record.parent = levels
            levels.add(record)
            skill.add(levels)
            app.xml_add_cloned_node(server, "", skill, dry_run=False, backup=True)
            continue
        spans = app.index_xml(server.read_bytes())
        level_parent = f"{skill_id}/level"
        if level_parent not in spans:
            app.xml_add_cloned_node(
                server, str(skill_id), WzSubProperty("level"), dry_run=False, backup=True,
            )
        sync_xml_record(server, f"{level_parent}/{level}", make_values_node(str(level), values))


def sync_actions() -> None:
    for mob_id, actions in MISSING_ACTIONS.items():
        client = ROOT / f"clien/Data/Mob/{mob_id}.img"
        source = TMS_DATA / f"Mob/_Canvas/{mob_id}.img"
        for action in actions:
            if app.load_image(client).root.get(action) is not None:
                continue
            app.copy_tms_node_with_server_sync(client, source, action)
    for mob_id, actions in PLACEHOLDER_AFTER_ACTIONS.items():
        client = ROOT / f"clien/Data/Mob/{mob_id}.img"
        server = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
        for action in actions:
            if app.load_image(client).root.get(action) is not None:
                continue
            action_node = WzSubProperty(action)
            frame = app._legacy_stub_canvas("0", action_node)
            action_node.add(frame)
            sync_img_record(client, (action,), action_node)
            sync_xml_record(server, action, action_node)


def create_treasure_mobs() -> None:
    for mob_id in (8900003, 8920006):
        client = ROOT / f"clien/Data/Mob/{mob_id}.img"
        source = TMS_DATA / f"Mob/_Canvas/{mob_id}.img"
        if not source.is_file():
            extracted = app.extract_ms_mob(str(mob_id))
            if extracted is None:
                raise FileNotFoundError(f"TMS Mob/{mob_id}.img")
            source = extracted[0]
        if not client.exists():
            app.create_empty_main_files(client)
        app.copy_tms_node_with_server_sync(client, source, "info")
        source_image = app.load_image(source)
        for action in (child.name for child in source_image.root.children()):
            app.copy_tms_node_with_server_sync(client, source, action)


def validate_outputs() -> None:
    for mob_id in (*MOB_INFO, 8900003, 8920006):
        client = ROOT / f"clien/Data/Mob/{mob_id}.img"
        image = app.load_image(client)
        if image.truncated or image.parse_warnings:
            raise ValueError(f"{client.name}: truncated={image.truncated} warnings={image.parse_warnings}")
        ET.parse(ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml")
    app.load_image(ROOT / "clien/Data/Skill/MobSkill.img")
    ET.parse(ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml")


def main() -> None:
    create_treasure_mobs()
    sync_mob_info()
    sync_projected_mob_skills()
    sync_actions()
    validate_outputs()
    paths = [ROOT / f"clien/Data/Mob/{mob_id}.img" for mob_id in (*MOB_INFO, 8900003, 8920006)]
    paths += [ROOT / "clien/Data/Skill/MobSkill.img"]
    for path in paths:
        print(f"{path.relative_to(ROOT)} {hashlib.sha256(path.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
