#!/usr/bin/env python3
"""Audit the migrated Akayrum and normal Root Abyss content closure."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import WzImage, WzKey  # noqa: E402


TARGET_KEY = WzKey.for_region("GMS")
QUEST_FILES = ("QuestInfo.img", "Check.img", "Act.img", "Say.img")
QUEST_IDS = {str(value) for value in (30000, *range(30002, 30014), 30027, *range(31165, 31181))}
MAP_IDS = (*range(105200410, 105200420), 910700200, 910700300)
MOB_IDS = (
    8860001,
    8900100, 8900101, 8900102, 8900103,
    8910100,
    8920100, 8920101, 8920102, 8920103, 8920104, 8920105, 8920106,
    8930000, 8930100,
    9300487,
)
NPC_IDS = (1064001, 1064017, 1064029, 2144001, 3005427)
EXISTING_MOB_DEPENDENCIES = (8930001,)
STRING_NODES = {
    "Mob.img": tuple(str(value) for value in MOB_IDS),
    "Npc.img": tuple(str(value) for value in NPC_IDS),
    "Consume.img": ("2431151",),
    "Etc.img": ("4033080", "4033081", "4033082", "4033611"),
    "Map.img": tuple(str(value) for value in MAP_IDS),
}
MOB_SKILL_LEVELS = (
    (100, 21), (114, 16), (114, 17),
    (128, 22), (128, 23), (133, 18), (145, 19),
    (170, 11), (170, 12),
    (170, 13), (183, 2), (184, 1),
    (186, 2), (186, 3), (186, 4), (187, 1), (188, 2),
    (191, 1), (191, 2),
    (201, 49), (201, 59), (201, 60), (201, 292),
    (202, 2), (203, 1),
)
CLIENT_ORIGINAL_MOB_SKILL_LEVELS = (
    (128, 18), (133, 8), (145, 9), (170, 1),
    (183, 1), (184, 1), (186, 1), (187, 1),
)
CLIENT_UNSUPPORTED_MOB_SKILL_TYPES = (188, 191, 201, 202, 203)
ITEMS = {
    1142536: ("Character/Accessory/01142536.img", "Character.wz/Accessory/01142536.img.xml"),
    2431151: ("Item/Consume/0243.img", "Item.wz/Consume/0243.img.xml"),
    4033080: ("Item/Etc/0403.img", "Item.wz/Etc/0403.img.xml"),
    4033081: ("Item/Etc/0403.img", "Item.wz/Etc/0403.img.xml"),
    4033082: ("Item/Etc/0403.img", "Item.wz/Etc/0403.img.xml"),
    4033611: ("Item/Etc/0403.img", "Item.wz/Etc/0403.img.xml"),
}


def direct_child(parent: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in parent if child.get("name") == name), None)


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def parse_client(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=path.name)
    image.parse()
    return image


def has_named_node(root, name: str) -> bool:
    for child in root.children():
        if child.name == name or (hasattr(child, "children") and has_named_node(child, name)):
            return True
    return False


def audit_quests(failures: list[str]) -> None:
    for image_name in QUEST_FILES:
        for server_root in (ROOT / "gms-server/wz", ROOT / "gms-server/wz-zh-CN"):
            path = server_root / "Quest.wz" / f"{image_name}.xml"
            root = ET.parse(path).getroot()
            present = {child.get("name") for child in root}
            missing = sorted(QUEST_IDS - present)
            require(not missing, f"{path}: missing quests {missing}", failures)
        client_path = ROOT / "clien/Data/Quest" / image_name
        image = parse_client(client_path)
        missing = sorted(quest_id for quest_id in QUEST_IDS if image.get(quest_id) is None)
        require(not missing, f"{client_path}: missing quests {missing}", failures)


def audit_individual_resources(failures: list[str]) -> None:
    for map_id in MAP_IDS:
        category = "Map1" if map_id < 900000000 else "Map9"
        client = ROOT / f"clien/Data/Map/Map/{category}/{map_id}.img"
        server = ROOT / f"gms-server/wz/Map.wz/Map/{category}/{map_id}.img.xml"
        require(client.exists(), f"missing {client}", failures)
        require(server.exists(), f"missing {server}", failures)
        if client.exists():
            parse_client(client)
        if server.exists():
            ET.parse(server)
    for mob_id in MOB_IDS:
        client = ROOT / f"clien/Data/Mob/{mob_id}.img"
        server = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
        require(client.exists(), f"missing {client}", failures)
        require(server.exists(), f"missing {server}", failures)
        if client.exists():
            parse_client(client)
        if server.exists():
            ET.parse(server)
    for mob_id in EXISTING_MOB_DEPENDENCIES:
        client = ROOT / f"clien/Data/Mob/{mob_id}.img"
        server = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
        require(client.exists(), f"missing existing mob dependency {client}", failures)
        require(server.exists(), f"missing existing mob dependency {server}", failures)
        if client.exists():
            parse_client(client)
        if server.exists():
            ET.parse(server)
    for npc_id in NPC_IDS:
        client = ROOT / f"clien/Data/Npc/{npc_id}.img"
        server = ROOT / f"gms-server/wz/Npc.wz/{npc_id}.img.xml"
        require(client.exists(), f"missing {client}", failures)
        require(server.exists(), f"missing {server}", failures)
        if client.exists():
            parse_client(client)
        if server.exists():
            ET.parse(server)


def audit_items(failures: list[str]) -> None:
    item_images: dict[Path, WzImage] = {}
    server_roots: dict[Path, ET.Element] = {}
    for item_id, (client_relative, server_relative) in ITEMS.items():
        client_path = ROOT / "clien/Data" / client_relative
        server_path = ROOT / "gms-server/wz" / server_relative
        require(client_path.exists(), f"missing item client file {client_path}", failures)
        require(server_path.exists(), f"missing item server file {server_path}", failures)
        if item_id == 1142536:
            if client_path.exists():
                parse_client(client_path)
            if server_path.exists():
                ET.parse(server_path)
            continue
        item_name = f"{item_id:08d}"
        if client_path.exists():
            image = item_images.setdefault(client_path, parse_client(client_path))
            require(image.get(item_name) is not None, f"{client_path}: missing {item_name}", failures)
        if server_path.exists():
            root = server_roots.setdefault(server_path, ET.parse(server_path).getroot())
            require(direct_child(root, item_name) is not None, f"{server_path}: missing {item_name}", failures)


def audit_strings_and_shared_resources(failures: list[str]) -> None:
    for image_name, node_names in STRING_NODES.items():
        client_path = ROOT / "clien/Data/String" / image_name
        client = parse_client(client_path)
        for node_name in node_names:
            require(has_named_node(client.root, node_name), f"{client_path}: missing string {node_name}", failures)
        for server_root in (ROOT / "gms-server/wz", ROOT / "gms-server/wz-zh-CN"):
            server_path = server_root / "String.wz" / f"{image_name}.xml"
            root = ET.parse(server_path).getroot()
            present = {element.get("name") for element in root.iter()}
            missing = sorted(set(node_names) - present)
            require(not missing, f"{server_path}: missing strings {missing}", failures)

    shared_resources = (
        (ROOT / "clien/Data/Reactor/1058020.img", ROOT / "gms-server/wz/Reactor.wz/1058020.img.xml"),
        (ROOT / "clien/Data/Sound/Bgm29.img", ROOT / "gms-server/wz/Sound.wz/Bgm29.img.xml"),
    )
    for client_path, server_path in shared_resources:
        require(client_path.exists(), f"missing {client_path}", failures)
        require(server_path.exists(), f"missing {server_path}", failures)
        if client_path.exists():
            parse_client(client_path)
        if server_path.exists():
            ET.parse(server_path)

    server_map = ET.parse(ROOT / "gms-server/wz/Map.wz/Map/Map1/105040300.img.xml").getroot()
    server_portals = direct_child(server_map, "portal")
    server_entries = [
        portal for portal in (() if server_portals is None else server_portals)
        if any(child.get("name") == "script" and child.get("value") == "go_rootabyss" for child in portal)
    ]
    require(len(server_entries) == 1, "105040300 server map must contain one go_rootabyss portal", failures)

    client_map = parse_client(ROOT / "clien/Data/Map/Map/Map1/105040300.img")
    client_portals = client_map.get("portal")
    client_entries = [
        portal for portal in client_portals.children()
        if getattr(portal.child("script"), "value", None) == "go_rootabyss"
    ]
    require(len(client_entries) == 1, "105040300 client map must contain one go_rootabyss portal", failures)


def audit_mob_skills(failures: list[str]) -> None:
    server_path = ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml"
    server_root = ET.parse(server_path).getroot()
    client_path = ROOT / "clien/Data/Skill/MobSkill.img"
    client = parse_client(client_path)
    for skill_id, level in MOB_SKILL_LEVELS:
        skill = direct_child(server_root, str(skill_id))
        levels = direct_child(skill, "level") if skill is not None else None
        require(
            levels is not None and direct_child(levels, str(level)) is not None,
            f"{server_path}: missing {skill_id}/{level}",
            failures,
        )

    # The legacy client must retain its original MobSkill table. Adding new
    # top-level types or jumping directly to high levels makes it reject the
    # whole data set during startup, even though wzpy can parse the IMG.
    for skill_id, level in CLIENT_ORIGINAL_MOB_SKILL_LEVELS:
        require(
            client.get(f"{skill_id}/level/{level}") is not None,
            f"{client_path}: missing original level {skill_id}/{level}",
            failures,
        )
    for skill_id in CLIENT_UNSUPPORTED_MOB_SKILL_TYPES:
        require(
            client.get(str(skill_id)) is None,
            f"{client_path}: unsupported top-level MobSkill {skill_id}",
            failures,
        )


def audit_scripts_and_java(failures: list[str]) -> None:
    event_names = ("AKAYRUMBattle", "AkayrumFSB", "CQBattle", "PIERREBattle", "VELLUMBattle", "VONBONBattle")
    root_abyss_event_names = ("CQBattle", "PIERREBattle", "VELLUMBattle", "VONBONBattle")
    entry_names = ("akayrumbattle", "bbbattle", "blbattle", "nwbattle", "paebattle")
    for script_root in (ROOT / "gms-server/scripts", ROOT / "gms-server/scripts-zh-CN"):
        for name in event_names:
            require((script_root / f"event/{name}.js").exists(), f"missing event script {script_root}:{name}", failures)
            text = (script_root / f"event/{name}.js").read_text(encoding="utf-8-sig")
            require("startDamageRecording" not in text, f"event {name} uses unsupported damage recording API", failures)
            require("broadcastDamageRanking" not in text, f"event {name} uses unsupported damage ranking API", failures)
        for name in root_abyss_event_names:
            text = (script_root / f"event/{name}.js").read_text(encoding="utf-8-sig")
            require("var minPlayers = 1, maxPlayers = 30;" in text, f"event {name} minimum party size is not 1", failures)
            require("var minLevel = 125, maxLevel = 255;" in text, f"event {name} minimum level is not 125", failures)
        for name in entry_names:
            require((script_root / f"npc/{name}.js").exists(), f"missing NPC script {script_root}:{name}", failures)
        for quest_id in (30000, *range(30002, 30014), 31165, 31170, 31171, 31172, 31173, 31174, 31176, 31179):
            require((script_root / f"quest/{quest_id}.js").exists(), f"missing quest script {script_root}:{quest_id}", failures)
        for quest_id in (30002, 30005):
            text = (script_root / f"quest/{quest_id}.js").read_text(encoding="utf-8-sig")
            require("inGameDirectionEvent_" not in text, f"quest {quest_id} retains unsupported direction API", failures)
            require("setInGameDirectionMode" not in text, f"quest {quest_id} retains unsupported direction mode", failures)
        oldscroll = (script_root / "map/onUserEnter/oldscroll_use.js").read_text(encoding="utf-8-sig")
        require("function start(ms)" in oldscroll, "oldscroll_use is not a compatible map entry script", failures)
        require("inGameDirectionEvent_" not in oldscroll, "oldscroll_use retains unsupported direction API", failures)

    expedition_type = (ROOT / "gms-server/src/main/java/org/gms/server/expeditions/ExpeditionType.java").read_text()
    for name in ("VONBON", "PIERRE", "CQ", "VELLUM", "AKAYRUM"):
        require(f"{name}(" in expedition_type, f"ExpeditionType missing {name}", failures)
    expedition_log = (ROOT / "gms-server/src/main/java/org/gms/server/expeditions/ExpeditionBossLog.java").read_text()
    for name in ("VONBON", "PIERRE", "CQ", "VELLUM", "AKAYRUM"):
        require(f"{name}(" in expedition_log, f"ExpeditionBossLog missing {name}", failures)
    mob_skill_type = (ROOT / "gms-server/src/main/java/org/gms/server/life/MobSkillType.java").read_text()
    for skill_id in (170, 186, 188, 189, 190, 191, 201, 202, 203):
        require(f"SUMMON_{skill_id}({skill_id})" in mob_skill_type, f"MobSkillType missing {skill_id}", failures)
    require("id > 203" in mob_skill_type, "MobSkillType upper bound is not 203", failures)
    mob_skill = (ROOT / "gms-server/src/main/java/org/gms/server/life/MobSkill.java").read_text()
    require("monster.getId() == 8910100" in mob_skill, "MobSkill lacks Von Bon/Magnus skill isolation", failures)
    require("monster.getId() == 8920102" in mob_skill, "MobSkill lacks Crimson Queen/Will skill isolation", failures)
    require(
        "monster.getId() == 8900101 || monster.getId() == 8900102" in mob_skill,
        "MobSkill lacks Pierre/Seren skill isolation",
        failures,
    )

    database_migration = ROOT / "gms-server/src/main/resources/db/migration/V2.1.47__add_akayrum_root_abyss_expeditions.sql"
    require(database_migration.exists(), f"missing database migration {database_migration}", failures)
    if database_migration.exists():
        sql = database_migration.read_text(encoding="utf-8")
        for name in ("VONBON", "PIERRE", "CQ", "VELLUM", "AKAYRUM"):
            require(f"'{name}'" in sql, f"database bosslog enum missing {name}", failures)
        require("(8220019, 4033080, 1, 1, 31171, 200000)" in sql, "Akayrum quest drop migration is missing", failures)


def main() -> int:
    failures: list[str] = []
    audit_quests(failures)
    audit_individual_resources(failures)
    audit_items(failures)
    audit_strings_and_shared_resources(failures)
    audit_mob_skills(failures)
    audit_scripts_and_java(failures)
    if failures:
        print("AUDIT FAILED")
        for failure in failures:
            print("-", failure)
        return 1
    print(
        "AUDIT OK:",
        f"quests={len(QUEST_IDS)}",
        f"maps={len(MAP_IDS)}",
        f"mobs={len(MOB_IDS)}",
        f"npcs={len(NPC_IDS)}",
        f"mobskills={len(MOB_SKILL_LEVELS)}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
