#!/usr/bin/env python3
"""Migrate the quest and expedition closure from the Akayrum/Root Abyss pack.

The earlier map migrations intentionally kept only a reduced boss subset. This
script adds the missing quest nodes, normal expedition resources and scripts
without replacing the project's compatibility-tuned Akayrum boss or shared WZ
images wholesale.
"""

from __future__ import annotations

import io
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Downloads/阿卡伊勒+鲁塔比斯.zip/阿卡伊勒+鲁塔比斯")
BACKUP_ROOT = Path("/private/tmp/akayrum-root-abyss-content-backup")
WZPY = ROOT / "tool/wz-python"
MIGRATION_TOOLS = ROOT / "tool/scripts/migration"
sys.path.insert(0, str(WZPY))
sys.path.insert(0, str(MIGRATION_TOOLS))

from wzpy import WzImage, WzKey, WzSubProperty  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402
from migrate_root_abyss_maps import clone_property  # noqa: E402


TARGET_KEY = WzKey.for_region("GMS")
QUEST_FILES = ("QuestInfo.img", "Check.img", "Act.img", "Say.img")
ROOT_ABYSS_QUEST_IDS = (30000, *range(30002, 30014), 30027)
AKAYRUM_QUEST_IDS = tuple(range(31165, 31181))
QUEST_IDS = tuple(str(value) for value in (*ROOT_ABYSS_QUEST_IDS, *AKAYRUM_QUEST_IDS))

MAP_IDS = (*range(105200410, 105200420), 910700200, 910700300)
MAP_STRING_IDS = tuple(str(value) for value in MAP_IDS)
MOB_IDS = (
    8860001,
    8900100, 8900101, 8900102, 8900103,
    8910100,
    8920100, 8920101, 8920102, 8920103, 8920104, 8920105, 8920106,
    8930000, 8930100,
    9300487,
)
NPC_IDS = (1064001, 1064017, 1064029, 2144001, 3005427)
MOB_SKILL_LEVELS = (
    (128, 22), (128, 23), (133, 18), (145, 19),
    (170, 11), (170, 12),
    (170, 13), (183, 2), (184, 1),
    (186, 2), (186, 3), (186, 4), (188, 2),
    (191, 1), (191, 2),
    (201, 49), (201, 59), (201, 60), (201, 292),
    (202, 2), (203, 1),
)

QUEST_SCRIPT_IDS = (
    30000, *range(30002, 30014),
    31165, 31170, 31171, 31172, 31173, 31174, 31176, 31179,
)
EVENT_SCRIPTS = (
    "AKAYRUMBattle.js", "AkayrumFSB.js", "CQBattle.js",
    "PIERREBattle.js", "VELLUMBattle.js", "VONBONBattle.js",
)
NPC_SCRIPTS = (
    "2144007.js", "2144014.js", "3005427.js",
    "AkayrumFS.js", "akayrumbattle.js", "bbbattle.js", "beilun.js",
    "blbattle.js", "nwbattle.js", "oldSuse.js", "out272000410.js",
    "out272000410b.js", "outAkayrum.js", "outrtb.js", "paebattle.js",
)
PORTAL_SCRIPTS = (
    "BPReturn_Akayrum.js", "banbanGoInside.js", "blackdracoout.js",
    "check_Portal0.js", "check_Portal1.js", "check_Portal2.js",
    "check_Portal3.js", "check_Portal4a.js", "check_Portal4b.js",
    "check_Portal5.js", "check_Portal6.js", "check_eNum.js",
    "go_rootabyss.js", "gotoDoor.js", "gotoNow.js", "in_cygnusAK.js",
    "outAkayrumP2.js", "outAkayrumPrison.js", "outPrison.js",
    "out_cygnusAK.js", "outpasttemple.js", "outportalNPC.js",
    "portalNPC1.js", "rootaNext.js", "rootaNext1.js", "rootaNext2.js",
    "rootaNext3.js", "rootabyssGardenOut.js", "rootafirstDoor.js",
    "rootaforthDoor.js", "rootasecondDoor.js", "rootathirdDoor.js",
    "shijieshu.js", "timeCrack.js",
)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def atomic_write_text(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", prefix=f".{path.name}.", dir=path.parent, delete=False
    ) as handle:
        handle.write(data)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def backup(path: Path) -> None:
    if not path.exists():
        return
    destination = BACKUP_ROOT / path.relative_to(ROOT)
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)


def copy_resource(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    backup(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def target_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), TARGET_KEY)


def find_imgdir_block(text: str, node_name: str, start: int = 0) -> tuple[int, int]:
    token = f'<imgdir name="{node_name}">'
    root_start = text.find(token, start)
    if root_start < 0:
        raise RuntimeError(f"missing XML imgdir {node_name}")
    depth = 0
    for match in re.finditer(r"</?imgdir\b[^>]*>", text[root_start:]):
        tag = match.group(0)
        if tag.startswith("</"):
            depth -= 1
            if depth == 0:
                return root_start, root_start + match.end()
        elif not tag.endswith("/>"):
            depth += 1
    raise RuntimeError(f"unterminated XML imgdir {node_name}")


def replace_root_xml_nodes(source: Path, destination: Path, node_names: tuple[str, ...]) -> None:
    source_text = source.read_text(encoding="utf-8-sig")
    destination_text = destination.read_text(encoding="utf-8-sig")
    for node_name in node_names:
        source_start, source_end = find_imgdir_block(source_text, node_name)
        block = source_text[source_start:source_end]
        try:
            target_start, target_end = find_imgdir_block(destination_text, node_name)
            destination_text = destination_text[:target_start] + block + destination_text[target_end:]
        except RuntimeError:
            insert_at = destination_text.rfind("</imgdir>")
            destination_text = destination_text[:insert_at] + block + "\n" + destination_text[insert_at:]
    backup(destination)
    atomic_write_text(destination, destination_text)


def child_path(root: WzSubProperty, node_name: str, prefix: tuple[str, ...] = ()) -> tuple[str, ...] | None:
    for child in root.children():
        path = (*prefix, child.name)
        if child.name == node_name:
            return path
        if isinstance(child, WzSubProperty):
            found = child_path(child, node_name, path)
            if found is not None:
                return found
    return None


def patch_client_nodes(source: Path, destination: Path, node_names: tuple[str, ...]) -> None:
    source_image = WzImage.from_bytes(source.read_bytes(), key=TARGET_KEY, name=source.name)
    target_image = WzImage.from_bytes(destination.read_bytes(), key=TARGET_KEY, name=destination.name)
    source_image.parse()
    target_image.parse()

    for node_name in node_names:
        path = child_path(source_image.root, node_name)
        if path is None:
            raise RuntimeError(f"missing client node {source}:{node_name}")
        source_node = source_image.get("/".join(path))
        parent_path = path[:-1]
        target_parent = target_image.get("/".join(parent_path)) if parent_path else target_image.root
        if not isinstance(target_parent, WzSubProperty):
            raise RuntimeError(f"missing client parent {destination}:{'/'.join(parent_path)}")
        target_parent.add(clone_property(source_node, name=node_name, parent=target_parent))

    backup(destination)
    atomic_write_bytes(destination, encode_image_body(target_image, target_reader()))


def patch_quest_resources() -> None:
    for image_name in QUEST_FILES:
        source_xml = SOURCE / "wz-zh-CN/Quest.wz" / f"{image_name}.xml"
        for target_root in (ROOT / "gms-server/wz", ROOT / "gms-server/wz-zh-CN"):
            replace_root_xml_nodes(source_xml, target_root / "Quest.wz" / f"{image_name}.xml", QUEST_IDS)
        patch_client_nodes(
            SOURCE / "Data/Quest" / image_name,
            ROOT / "clien/Data/Quest" / image_name,
            QUEST_IDS,
        )


def patch_item_resources() -> None:
    item_groups = {
        "Consume/0243.img": ("02431151",),
        "Etc/0403.img": ("04033080", "04033081", "04033082", "04033611"),
    }
    for relative, item_ids in item_groups.items():
        replace_root_xml_nodes(
            SOURCE / "wz/Item.wz" / f"{relative}.xml",
            ROOT / "gms-server/wz/Item.wz" / f"{relative}.xml",
            item_ids,
        )
        patch_client_nodes(
            SOURCE / "Data/Item" / relative,
            ROOT / "clien/Data/Item" / relative,
            item_ids,
        )

    copy_resource(
        SOURCE / "wz/Character.wz/Accessory/01142536.img.xml",
        ROOT / "gms-server/wz/Character.wz/Accessory/01142536.img.xml",
    )
    copy_resource(
        SOURCE / "Data/Character/Accessory/01142536.img",
        ROOT / "clien/Data/Character/Accessory/01142536.img",
    )


def patch_string_resources() -> None:
    node_groups = {
        "Mob.img": tuple(str(value) for value in MOB_IDS),
        "Npc.img": tuple(str(value) for value in NPC_IDS),
        "Consume.img": ("2431151",),
        "Etc.img": ("4033080", "4033081", "4033082", "4033611"),
    }
    for image_name, node_names in node_groups.items():
        source_xml = SOURCE / "wz-zh-CN/String.wz" / f"{image_name}.xml"
        for target_root in (ROOT / "gms-server/wz", ROOT / "gms-server/wz-zh-CN"):
            replace_root_xml_nodes(source_xml, target_root / "String.wz" / f"{image_name}.xml", node_names)
        patch_client_nodes(
            SOURCE / "Data/String" / image_name,
            ROOT / "clien/Data/String" / image_name,
            node_names,
        )

    # Map strings live below category nodes, so clone them through their actual paths.
    patch_client_nodes(
        SOURCE / "Data/String/Map.img",
        ROOT / "clien/Data/String/Map.img",
        MAP_STRING_IDS,
    )
    for target_root in (ROOT / "gms-server/wz", ROOT / "gms-server/wz-zh-CN"):
        patch_xml_nodes_by_source_path(
            SOURCE / "wz-zh-CN/String.wz/Map.img.xml",
            target_root / "String.wz/Map.img.xml",
            MAP_STRING_IDS,
        )


def xml_node_path(root: ET.Element, node_name: str, prefix: tuple[str, ...] = ()) -> tuple[str, ...] | None:
    for child in root:
        path = (*prefix, child.get("name", ""))
        if child.get("name") == node_name:
            return path
        found = xml_node_path(child, node_name, path)
        if found is not None:
            return found
    return None


def direct_xml_child(parent: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in parent if child.get("name") == name), None)


def patch_xml_nodes_by_source_path(source: Path, destination: Path, node_names: tuple[str, ...]) -> None:
    source_root = ET.parse(source).getroot()
    target_tree = ET.parse(destination)
    target_root = target_tree.getroot()
    for node_name in node_names:
        path = xml_node_path(source_root, node_name)
        if path is None:
            raise RuntimeError(f"missing server node {source}:{node_name}")
        source_parent = source_root
        target_parent = target_root
        for part in path[:-1]:
            source_parent = direct_xml_child(source_parent, part)
            target_parent = direct_xml_child(target_parent, part)
            if source_parent is None or target_parent is None:
                raise RuntimeError(f"missing server parent {destination}:{'/'.join(path[:-1])}")
        current = direct_xml_child(target_parent, node_name)
        if current is not None:
            target_parent.remove(current)
        target_parent.append(deepcopy(direct_xml_child(source_parent, node_name)))
    backup(destination)
    xml = ET.tostring(target_root, encoding="unicode", short_empty_elements=True)
    atomic_write_text(destination, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + xml)


def patch_mob_skills() -> None:
    """Patch server MobSkill data without extending the legacy client table.

    The BeiDou client rejects MobSkill top-level ids and non-contiguous levels
    that did not exist in its original data.  Server-side definitions are still
    required by the migrated boss logic, but copying those nodes into the
    client causes the startup-time "incorrect game data" error.
    """
    source_path = SOURCE / "wz/Skill.wz/MobSkill.img.xml"
    target_path = ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml"
    source_root = ET.parse(source_path).getroot()
    target_root = ET.parse(target_path).getroot()
    for skill_id, level in MOB_SKILL_LEVELS:
        source_skill = direct_xml_child(source_root, str(skill_id))
        source_levels = direct_xml_child(source_skill, "level") if source_skill is not None else None
        source_level = direct_xml_child(source_levels, str(level)) if source_levels is not None else None
        if source_level is None:
            raise RuntimeError(f"missing source MobSkill {skill_id}/{level}")
        target_skill = direct_xml_child(target_root, str(skill_id))
        if target_skill is None:
            target_skill = ET.SubElement(target_root, "imgdir", {"name": str(skill_id)})
        target_levels = direct_xml_child(target_skill, "level")
        if target_levels is None:
            target_levels = ET.SubElement(target_skill, "imgdir", {"name": "level"})
        current = direct_xml_child(target_levels, str(level))
        if current is not None:
            target_levels.remove(current)
        target_levels.append(deepcopy(source_level))
    backup(target_path)
    xml = ET.tostring(target_root, encoding="unicode", short_empty_elements=True)
    atomic_write_text(target_path, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + xml)


def copy_individual_resources() -> None:
    for map_id in MAP_IDS:
        category = "Map1" if map_id < 900000000 else "Map9"
        copy_resource(
            SOURCE / f"wz/Map.wz/Map/{category}/{map_id}.img.xml",
            ROOT / f"gms-server/wz/Map.wz/Map/{category}/{map_id}.img.xml",
        )
        copy_resource(
            SOURCE / f"Data/Map/Map/{category}/{map_id}.img",
            ROOT / f"clien/Data/Map/Map/{category}/{map_id}.img",
        )
    for mob_id in MOB_IDS:
        copy_resource(SOURCE / f"wz/Mob.wz/{mob_id}.img.xml", ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml")
        copy_resource(SOURCE / f"Data/Mob/{mob_id}.img", ROOT / f"clien/Data/Mob/{mob_id}.img")
    for npc_id in NPC_IDS:
        copy_resource(SOURCE / f"wz/Npc.wz/{npc_id}.img.xml", ROOT / f"gms-server/wz/Npc.wz/{npc_id}.img.xml")
        copy_resource(SOURCE / f"Data/Npc/{npc_id}.img", ROOT / f"clien/Data/Npc/{npc_id}.img")
    copy_resource(SOURCE / "wz/Reactor.wz/1058020.img.xml", ROOT / "gms-server/wz/Reactor.wz/1058020.img.xml")
    copy_resource(SOURCE / "Data/Reactor/1058020.img", ROOT / "clien/Data/Reactor/1058020.img")
    copy_resource(SOURCE / "wz/Sound.wz/Bgm29.img.xml", ROOT / "gms-server/wz/Sound.wz/Bgm29.img.xml")
    copy_resource(SOURCE / "Data/Sound/Bgm29.img", ROOT / "clien/Data/Sound/Bgm29.img")


def patch_ellinia_entrance_portal() -> None:
    source_xml = SOURCE / "wz/Map.wz/Map/Map1/105040300.img.xml"
    target_xml = ROOT / "gms-server/wz/Map.wz/Map/Map1/105040300.img.xml"
    backup_path = BACKUP_ROOT / target_xml.relative_to(ROOT)
    baseline_xml = backup_path if backup_path.exists() else target_xml
    source_root = ET.parse(source_xml).getroot()
    source_portals = direct_xml_child(source_root, "portal")
    source_portal = next(
        portal for portal in source_portals
        if any(child.get("name") == "script" and child.get("value") == "go_rootabyss" for child in portal)
    )
    target_root = ET.parse(baseline_xml).getroot()
    target_portals = direct_xml_child(target_root, "portal")
    next_id = max((int(portal.get("name")) for portal in target_portals), default=-1) + 1

    source_text = source_xml.read_text(encoding="utf-8-sig")
    source_parent_start, source_parent_end = find_imgdir_block(source_text, "portal")
    source_parent = source_text[source_parent_start:source_parent_end]
    source_child_start, source_child_end = find_imgdir_block(source_parent, source_portal.get("name"))
    source_block = source_parent[source_child_start:source_child_end]
    source_block = source_block.replace(
        f'<imgdir name="{source_portal.get("name")}">',
        f'<imgdir name="{next_id}">',
        1,
    )

    target_text = baseline_xml.read_text(encoding="utf-8-sig")
    target_parent_start, target_parent_end = find_imgdir_block(target_text, "portal")
    target_parent = target_text[target_parent_start:target_parent_end]
    insert_at = target_parent.rfind("</imgdir>")
    target_parent = target_parent[:insert_at] + source_block + "\n  " + target_parent[insert_at:]
    target_text = target_text[:target_parent_start] + target_parent + target_text[target_parent_end:]
    backup(target_xml)
    atomic_write_text(target_xml, target_text)

    source_client = SOURCE / "Data/Map/Map/Map1/105040300.img"
    target_client = ROOT / "clien/Data/Map/Map/Map1/105040300.img"
    source_image = WzImage.from_bytes(source_client.read_bytes(), key=TARGET_KEY, name=source_client.name)
    target_image = WzImage.from_bytes(target_client.read_bytes(), key=TARGET_KEY, name=target_client.name)
    source_image.parse()
    target_image.parse()
    source_portals = source_image.get("portal")
    target_portals = target_image.get("portal")
    source_portal = next(
        portal for portal in source_portals.children()
        if getattr(portal.child("script"), "value", None) == "go_rootabyss"
    )
    for portal in list(target_portals.children()):
        if getattr(portal.child("script"), "value", None) == "go_rootabyss":
            target_portals._children.pop(portal.name, None)
    next_id = max((int(portal.name) for portal in target_portals.children()), default=-1) + 1
    target_portals.add(clone_property(source_portal, name=str(next_id), parent=target_portals))
    backup(target_client)
    atomic_write_bytes(target_client, encode_image_body(target_image, target_reader()))


def copy_scripts() -> None:
    groups = {
        "event": EVENT_SCRIPTS,
        "npc": NPC_SCRIPTS,
        "portal": PORTAL_SCRIPTS,
        "quest": tuple(f"{quest_id}.js" for quest_id in QUEST_SCRIPT_IDS),
        "map/onUserEnter": ("oldscroll_use.js", "root_qrcave.js", "rootaBossEnter.js"),
        "reactor": ("1058020.js",),
        "item": ("consume_2431151.js",),
    }
    for group, file_names in groups.items():
        for file_name in file_names:
            source = SOURCE / "scripts-zh-CN" / group / file_name
            for script_root in (ROOT / "gms-server/scripts", ROOT / "gms-server/scripts-zh-CN"):
                copy_resource(source, script_root / group / file_name)


def patch_script_compatibility() -> None:
    for script_root in (ROOT / "gms-server/scripts", ROOT / "gms-server/scripts-zh-CN"):
        for event_name in ("VONBONBattle.js", "PIERREBattle.js", "CQBattle.js", "VELLUMBattle.js"):
            event_path = script_root / "event" / event_name
            text = event_path.read_text(encoding="utf-8-sig")
            text = text.replace("var minPlayers = 2, maxPlayers = 30;", "var minPlayers = 1, maxPlayers = 30;")
            text = text.replace("var minLevel = 120, maxLevel = 255;", "var minLevel = 125, maxLevel = 255;")
            text = text.replace("minLevel = 120, maxLevel = 200;", "minLevel = 125, maxLevel = 200;")
            atomic_write_text(event_path, text)

        quest_30002 = script_root / "quest/30002.js"
        text = quest_30002.read_text(encoding="utf-8-sig")
        text = re.sub(
            r'(else if \(status == 9\) \{\s+qm\.forceStartQuest\(\);).*?'
            r'(?=\n        \}\n    \}\n\}\n\nfunction end)',
            r'\1\n            qm.dispose();',
            text,
            count=1,
            flags=re.DOTALL,
        )
        atomic_write_text(quest_30002, text)

        quest_30005 = script_root / "quest/30005.js"
        text = quest_30005.read_text(encoding="utf-8-sig")
        for unsupported_line in (
            "            qm.curNodeEventEnd(true);\n",
            "            qm.setInGameDirectionMode(true, true, true);\n",
            "            qm.inGameDirectionEvent_MoveAction(0);\n",
            "            qm.setStandAloneMode(true);\n",
            "            qm.fieldEffect_ScreenMsg(\"rootabyss/demian\");\n",
            "            qm.inGameDirectionEvent_AskAnswerTime(2000);\n",
            "            qm.setStandAloneMode(false);\n",
            "            qm.setInGameDirectionMode(false, true, false);\n",
        ):
            text = text.replace(unsupported_line, "")
        text = text.replace(
            "            qm.forceStartQuest();\n            qm.forceCompleteQuest(30005);\n",
            "            qm.forceCompleteQuest();\n",
        )
        atomic_write_text(quest_30005, text)

        for event_name, lobby_map in (
            ("VONBONBattle.js", 105200000),
            ("PIERREBattle.js", 105200000),
            ("CQBattle.js", 105200000),
            ("VELLUMBattle.js", 105200000),
            ("AKAYRUMBattle.js", 272030300),
        ):
            event_path = script_root / "event" / event_name
            text = event_path.read_text(encoding="utf-8-sig")
            text = re.sub(
                r'\n    // 开启伤害记录\n    if \(GameConfig\.getServerBoolean\("damage_ranking"\)\) \{.*?\n    \}\n',
                "\n",
                text,
                flags=re.DOTALL,
            )
            text = re.sub(r"^\s*eim\.broadcastDamageRanking\(\);.*\n", "", text, flags=re.MULTILINE)
            old = (
                f"    em.getChannelServer().getMapFactory().getMap({lobby_map})"
                ".getReactorById(2118002).forceHitReactor(newState);"
            )
            new = (
                f"    var reactor = em.getChannelServer().getMapFactory().getMap({lobby_map})"
                ".getReactorById(2118002);\n"
                "    if (reactor != null) reactor.forceHitReactor(newState);"
            )
            atomic_write_text(event_path, text.replace(old, new))

        atomic_write_text(
            script_root / "map/onUserEnter/root_meet.js",
            "function start(ms) {\n    return true;\n}\n",
        )
        atomic_write_text(
            script_root / "map/onUserEnter/oldscroll_use.js",
            'function start(ms) {\n'
            '    ms.showInfoText("虽然卷轴很陈旧，但是一点问题都没有。重新回去吧。");\n'
            '    ms.setQuestProgress(30004, "oldscroll=2");\n'
            '    ms.warp(910700200, 0);\n'
            '}\n',
        )


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"missing source pack: {SOURCE}")
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    patch_quest_resources()
    patch_item_resources()
    patch_string_resources()
    patch_mob_skills()
    copy_individual_resources()
    patch_ellinia_entrance_portal()
    copy_scripts()
    patch_script_compatibility()
    print(f"Akayrum/Root Abyss content migrated. Backups: {BACKUP_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
