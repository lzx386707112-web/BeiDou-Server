#!/usr/bin/env python3
"""Restore Ranmaru boss skills, HP, battle-map enter scripts, and set drops."""

from __future__ import annotations

import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_ranmaru as ranmaru  # noqa: E402
from wzpy import WzImage, WzIntProperty, WzStringProperty, WzSubProperty  # noqa: E402


ZAKUM_HP = 110000000
HORNTAIL_HP = 2090000000
NORMAL_BOSS_ID = ranmaru.NORMAL_BOSS_ID
HARD_BOSS_ID = ranmaru.HARD_BOSS_ID
BATTLE_MAPS = (ranmaru.NORMAL_BATTLE, ranmaru.HARD_BATTLE)
ON_USER_ENTER = "Ranmaru_Enter"
ON_FIRST_USER_ENTER = "Ranmaru_EnterF"
DROP_SQL = (
    ROOT
    / "gms-server/src/main/resources/db/migration/"
    "V2.1.81__add_ranmaru_set_drops.sql"
)
DROP_CHANCE = 10000  # 1% on the 1,000,000 drop_data scale

# Project TMS skill IDs onto the highest GMS MobSkill levels already in-repo.
NORMAL_SKILLS = (
    {"skill": 100, "action": 1, "level": 25, "effectAfter": 0, "skillAfter": 1800},
    {"skill": 145, "action": 2, "level": 19, "effectAfter": 0, "skillAfter": 2160},
    {"skill": 128, "action": 3, "level": 23, "effectAfter": 0, "skillAfter": 1800},
    {"skill": 133, "action": 4, "level": 18, "effectAfter": 0, "skillAfter": 1800},
)
HARD_SKILLS = NORMAL_SKILLS + (
    {
        "skill": 176,
        "action": 5,
        "level": 6,
        "effectAfter": 0,
        "skillAfter": 4920,
        "priority": 2,
    },
)
HP_BY_MOB = {
    NORMAL_BOSS_ID: ZAKUM_HP,
    HARD_BOSS_ID: HORNTAIL_HP,
}
SKILLS_BY_MOB = {
    NORMAL_BOSS_ID: NORMAL_SKILLS,
    HARD_BOSS_ID: HARD_SKILLS,
}
NORMAL_DROPS = (
    (1003603, "天钿女命的帽子"),
    (1052511, "天钿女命的铠甲"),
    (1072713, "天钿女命的鞋子"),
    (1082474, "天钿女命的手套"),
    (1102458, "天钿女命的披风"),
    (1132158, "天钿女命的腰带"),
    (1003601, "天照的头盔"),
    (1052509, "天照的铠甲"),
    (1072711, "天照的鞋子"),
    (1082472, "天照的手套"),
    (1102456, "天照的披风"),
    (1132156, "天照的腰带"),
    (1003602, "大山祇神的帽子"),
    (1052510, "大山祇神的铠甲"),
    (1072712, "大山祇神的鞋子"),
    (1082473, "大山祇神的手套"),
    (1102457, "大山祇神的披风"),
    (1132157, "大山祇神的腰带"),
    (1003604, "月夜见尊的帽子"),
    (1052512, "月夜见尊的铠甲"),
    (1072714, "月夜见尊的鞋子"),
    (1082475, "月夜见尊的手套"),
    (1102459, "月夜见尊的披风"),
    (1132159, "月夜见尊的腰带"),
    (1003605, "素盏呜尊的头盔"),
    (1052513, "素盏呜尊的铠甲"),
    (1072715, "素盏呜尊的鞋子"),
    (1082476, "素盏呜尊的手套"),
    (1102460, "素盏呜尊的披风"),
    (1132160, "素盏呜尊的腰带"),
)
HARD_DROPS = (
    (1372234, "天钿女命的却鬼棒"),
    (1382271, "天钿女命的魔灵杖"),
    (1302349, "天照的丛云剑"),
    (1312209, "天照的天月斧"),
    (1322261, "天照的金刚杵"),
    (1402265, "天照的御魂剑"),
    (1412186, "天照的鬼炎斧"),
    (1422194, "天照的破雳刚杵"),
    (1432140, "天照的风灭戟"),
    (1442184, "天照的天羽羽斩"),
    (1452263, "大山祇神的火魂弓"),
    (1462249, "大山祇神的大通莲弓"),
    (1332195, "月夜见尊的斩杀刀"),
    (1332286, "月夜见尊的斩杀刀"),
    (1472271, "月夜见尊的惨魔拳"),
    (1482229, "素盏呜尊的惨血熊千"),
    (1492241, "素盏呜尊的雷激枪"),
)
SCRIPT_TREES = (
    ROOT / "gms-server/scripts",
    ROOT / "gms-server/scripts-zh-CN",
)
ENTER_SCRIPT = """\
function start(ms) {
    var player = ms.getPlayer();
    if (player == null) {
        return;
    }
    player.dropMessage(5, "森兰丸的气息笼罩了祭坛。");
}
"""
FIRST_ENTER_SCRIPT = """\
function start(ms) {
}
"""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_img(data: bytes, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"{name} parse failed: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    return image


def client_mob_path(mob_id: int) -> Path:
    path = ROOT / f"clien/Data/Mob/{mob_id}.img"
    padded = ROOT / f"clien/Data/Mob/{mob_id:07d}.img"
    return path if path.is_file() or not padded.is_file() else padded


def server_mob_path(mob_id: int) -> Path:
    path = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
    padded = ROOT / f"gms-server/wz/Mob.wz/{mob_id:07d}.img.xml"
    return path if path.is_file() or not padded.is_file() else padded


def skill_table(entries: tuple[dict, ...]) -> WzSubProperty:
    root = WzSubProperty("skill")
    for index, entry in enumerate(entries):
        slot = WzSubProperty(str(index), root)
        root.add(slot)
        for name in ("skill", "action", "level", "effectAfter", "skillAfter"):
            slot.add(WzIntProperty(name, int(entry[name]), slot))
        if "priority" in entry:
            slot.add(WzIntProperty("priority", int(entry["priority"]), slot))
    return root


def skill_matches(info, entries: tuple[dict, ...]) -> bool:
    if not isinstance(info, WzSubProperty):
        return False
    node = info.child("skill")
    if not isinstance(node, WzSubProperty):
        return False
    children = [child for child in node.children() if child.name.isdigit()]
    if len(children) != len(entries):
        return False
    for child, entry in zip(sorted(children, key=lambda item: int(item.name)), entries):
        for name, value in entry.items():
            actual = arc.child_value(child, name)
            if actual is None or int(actual) != int(value):
                return False
    return True


def xml_skill_matches(root: ET.Element, entries: tuple[dict, ...]) -> bool:
    skill = root.find('./imgdir[@name="info"]/imgdir[@name="skill"]')
    if skill is None:
        return False
    children = [
        child
        for child in skill
        if child.tag == "imgdir" and (child.get("name") or "").isdigit()
    ]
    if len(children) != len(entries):
        return False
    for child, entry in zip(
        sorted(children, key=lambda item: int(item.get("name") or 0)), entries
    ):
        for name, value in entry.items():
            node = child.find(f'./int[@name="{name}"]')
            if node is None or node.get("value") != str(value):
                return False
    return True


def patch_mob(mob_id: int) -> bool:
    client = client_mob_path(mob_id)
    server = server_mob_path(mob_id)
    if not client.is_file() or not server.is_file():
        raise FileNotFoundError(f"missing Ranmaru boss files for {mob_id}")
    target_hp = HP_BY_MOB[mob_id]
    entries = SKILLS_BY_MOB[mob_id]
    image = ranmaru.load_checked(client, arc.GMS_KEY)
    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{mob_id} missing info")
    for child in image.root.children():
        if not child.name.startswith("attack"):
            continue
        attack_info = child.child("info")
        if isinstance(attack_info, WzSubProperty) and attack_info.child("ball") is not None:
            raise RuntimeError(f"{mob_id} {child.name} has ball; ballistic contract needed")

    original = client.read_bytes()
    patched = original
    if int(arc.child_value(info, "maxHP") or 0) != target_hp:
        patched = arc.mutate_img(
            patched, "edit", ("info", "maxHP"), values={"value": target_hp}, region="GMS"
        ).data
        arc.verify_raw_record_scope(original, patched, {("info", "maxHP")}, allow_additions=False)

    current = parse_img(patched, client.name)
    current_info = current.root.child("info")
    if not skill_matches(current_info, entries):
        if isinstance(current_info, WzSubProperty) and current_info.child("skill") is not None:
            raise RuntimeError(f"{mob_id} already has a different info/skill table")
        before_skill = patched
        patched = arc.append_property_record(patched, ("info",), skill_table(entries))
        arc.verify_raw_record_insert_scope(before_skill, patched, {("info", "skill")})

    checked = parse_img(patched, client.name)
    patched_info = checked.root.child("info")
    if int(arc.child_value(patched_info, "maxHP") or 0) != target_hp:
        raise RuntimeError(f"{mob_id} maxHP was not set to {target_hp}")
    if not skill_matches(patched_info, entries):
        raise RuntimeError(f"{mob_id} skill table mismatch")
    changed_client = patched != original
    if changed_client:
        arc.atomic_write_bytes(client, patched)

    text = server.read_text(encoding="utf-8")
    original_text = text
    xml_root = ET.fromstring(text)
    hp_node = xml_root.find('./imgdir[@name="info"]/int[@name="maxHP"]')
    if hp_node is None:
        raise RuntimeError(f"{server.name} missing info/maxHP")
    if hp_node.get("value") != str(target_hp):
        text = arc.mutate_xml(
            text, "edit", ("info", "maxHP"), kind="Int", values={"value": target_hp}
        )
    xml_root = ET.fromstring(text)
    if not xml_skill_matches(xml_root, entries):
        if xml_root.find('./imgdir[@name="info"]/imgdir[@name="skill"]') is not None:
            raise RuntimeError(f"{server.name} already has a different info/skill table")
        text = arc.append_xml_properties(text, ("info",), [skill_table(entries)])
    xml_root = ET.fromstring(text)
    hp_node = xml_root.find('./imgdir[@name="info"]/int[@name="maxHP"]')
    if hp_node is None or hp_node.get("value") != str(target_hp):
        raise RuntimeError(f"{server.name} maxHP mismatch")
    if not xml_skill_matches(xml_root, entries):
        raise RuntimeError(f"{server.name} skill table mismatch")
    changed_server = text != original_text
    if changed_server:
        arc.atomic_write_text(server, text)
    return changed_client or changed_server


def patch_battle_map(map_id: int) -> bool:
    client = ranmaru.client_map_path(map_id)
    server = ranmaru.server_map_path("wz", map_id)
    image = ranmaru.load_checked(client, arc.GMS_KEY)
    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"map {map_id} missing info")

    original = client.read_bytes()
    patched = original
    approved: set[tuple[str, ...]] = set()
    if str(arc.child_value(info, "onUserEnter") or "") != ON_USER_ENTER:
        if info.child("onUserEnter") is not None:
            raise RuntimeError(f"map {map_id} has unexpected onUserEnter")
        patched = arc.append_property_record(
            patched, ("info",), WzStringProperty("onUserEnter", ON_USER_ENTER)
        )
        approved.add(("info", "onUserEnter"))
    current_info = parse_img(patched, client.name).root.child("info")
    if str(arc.child_value(current_info, "onFirstUserEnter") or "") != ON_FIRST_USER_ENTER:
        if isinstance(current_info, WzSubProperty) and current_info.child("onFirstUserEnter") is not None:
            raise RuntimeError(f"map {map_id} has unexpected onFirstUserEnter")
        patched = arc.append_property_record(
            patched, ("info",), WzStringProperty("onFirstUserEnter", ON_FIRST_USER_ENTER)
        )
        approved.add(("info", "onFirstUserEnter"))
    if approved:
        arc.verify_raw_record_insert_scope(original, patched, approved)

    checked_info = parse_img(patched, client.name).root.child("info")
    if str(arc.child_value(checked_info, "onUserEnter") or "") != ON_USER_ENTER:
        raise RuntimeError(f"map {map_id} onUserEnter missing")
    if str(arc.child_value(checked_info, "onFirstUserEnter") or "") != ON_FIRST_USER_ENTER:
        raise RuntimeError(f"map {map_id} onFirstUserEnter missing")
    changed_client = patched != original
    if changed_client:
        arc.atomic_write_bytes(client, patched)

    text = server.read_text(encoding="utf-8")
    original_text = text
    xml_root = ET.fromstring(text)
    info_xml = xml_root.find('./imgdir[@name="info"]')
    if info_xml is None:
        raise RuntimeError(f"{server.name} missing info")
    enter = info_xml.find('./string[@name="onUserEnter"]')
    first = info_xml.find('./string[@name="onFirstUserEnter"]')
    props = []
    if enter is None:
        props.append(WzStringProperty("onUserEnter", ON_USER_ENTER))
    elif enter.get("value") != ON_USER_ENTER:
        raise RuntimeError(f"{server.name} unexpected onUserEnter")
    if first is None:
        props.append(WzStringProperty("onFirstUserEnter", ON_FIRST_USER_ENTER))
    elif first.get("value") != ON_FIRST_USER_ENTER:
        raise RuntimeError(f"{server.name} unexpected onFirstUserEnter")
    if props:
        text = arc.append_xml_properties(text, ("info",), props)
    xml_root = ET.fromstring(text)
    info_xml = xml_root.find('./imgdir[@name="info"]')
    enter = info_xml.find('./string[@name="onUserEnter"]')
    first = info_xml.find('./string[@name="onFirstUserEnter"]')
    if enter is None or enter.get("value") != ON_USER_ENTER:
        raise RuntimeError(f"{server.name} onUserEnter mismatch")
    if first is None or first.get("value") != ON_FIRST_USER_ENTER:
        raise RuntimeError(f"{server.name} onFirstUserEnter mismatch")
    changed_server = text != original_text
    if changed_server:
        arc.atomic_write_text(server, text)
    return changed_client or changed_server


def write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return
    path.write_text(text, encoding="utf-8")


def write_scripts() -> None:
    for tree in SCRIPT_TREES:
        write_file(tree / "map/onUserEnter" / f"{ON_USER_ENTER}.js", ENTER_SCRIPT)
        write_file(
            tree / "map/onFirstUserEnter" / f"{ON_FIRST_USER_ENTER}.js",
            FIRST_ENTER_SCRIPT,
        )


def write_drop_sql() -> None:
    rows = []
    for dropper_id, drops in ((NORMAL_BOSS_ID, NORMAL_DROPS), (HARD_BOSS_ID, HARD_DROPS)):
        for item_id, name in drops:
            rows.append((f"({dropper_id}, {item_id}, 1, 1, 0, {DROP_CHANCE})", name))
    lines = []
    for index, (row, name) in enumerate(rows):
        comma = "," if index < len(rows) - 1 else ""
        lines.append(f"{row}{comma} -- {name} 1%")
    text = (
        "-- Mori Ranmaru set/weapon drops.\n"
        "-- drop_data chance scale: 1,000,000 = 100%, so 1% = 10000.\n"
        "INSERT INTO `drop_data`\n"
        "    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`) VALUES\n"
        + "\n".join(lines)
        + "\nON DUPLICATE KEY UPDATE\n"
        "    `minimum_quantity` = VALUES(`minimum_quantity`),\n"
        "    `maximum_quantity` = VALUES(`maximum_quantity`),\n"
        "    `questid` = VALUES(`questid`),\n"
        "    `chance` = VALUES(`chance`);\n"
    )
    write_file(DROP_SQL, text)


def main() -> int:
    changed = []
    for mob_id in (NORMAL_BOSS_ID, HARD_BOSS_ID):
        if patch_mob(mob_id):
            changed.append(f"mob {mob_id}")
    for map_id in BATTLE_MAPS:
        if patch_battle_map(map_id):
            changed.append(f"map {map_id}")
    write_scripts()
    write_drop_sql()
    print("changed:", ", ".join(changed) if changed else "none")
    for path in (
        client_mob_path(NORMAL_BOSS_ID),
        client_mob_path(HARD_BOSS_ID),
        ranmaru.client_map_path(ranmaru.NORMAL_BATTLE),
        ranmaru.client_map_path(ranmaru.HARD_BATTLE),
        server_mob_path(NORMAL_BOSS_ID),
        server_mob_path(HARD_BOSS_ID),
        ranmaru.server_map_path("wz", ranmaru.NORMAL_BATTLE),
        ranmaru.server_map_path("wz", ranmaru.HARD_BATTLE),
        DROP_SQL,
    ):
        print(f"{sha256(path)}  {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
