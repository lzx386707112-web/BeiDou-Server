#!/usr/bin/env python3
"""Migrate TMS Mori Ranmaru, Momijigaoka fields, and the defeat quest."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import migrate_arcane_river_expansion as arc  # noqa: E402
from migrate_twilight_perion_monster_park import (  # noqa: E402
    add_int,
    add_string,
    add_sub,
    append_named_records,
    append_server_named,
    iter_incomplete_ballistic_attacks,
    load_checked,
    repair_ballistic_mobs,
)
from wzpy import WzSubProperty  # noqa: E402


MAP_IDS = (
    807000000,
    807000011,
    807010000,
    807010001,
    807010002,
    807010003,
    807010004,
    807010100,
    807300100,
    807300110,
    807300120,
    807300200,
    807300210,
    807300220,
)
MAP_ID_SET = set(MAP_IDS)
TOWN_MAP = 807000000
ELNATH_ALTAR = 211041700
NORMAL_ENTRY = 807300100
HARD_ENTRY = 807300200
NORMAL_BATTLE = 807300110
HARD_BATTLE = 807300210
NORMAL_BOSS_ID = 9421581
HARD_BOSS_ID = 9421583
BOSS_MOBS = tuple(range(9421580, 9421590))
FIELD_MOBS = (9421511, 9421512, 9421513, 9421514)
QUEST_IDS = (57480,)
QUEST_NPC_ID = 9130145
REACTOR_IDS = (8079000, 8079001, 8079002)
KEEP_PORTAL_SCRIPTS = {
    "Ranmaru_accept",
    "Ranmaru_ptlNPC2",
    "pt_ranmaruOut",
    "BPReturn_ranmaru",
    "east_807000000",
}
PORTAL_RETARGETS = {
    807010004: {"east00": (807000000, "east00")},
}
RETURN_OVERRIDES = {
    807300110: NORMAL_ENTRY,
    807300120: NORMAL_ENTRY,
    807300210: HARD_ENTRY,
    807300220: HARD_ENTRY,
}
EXTRA_TOWN_REMOVED = {9000086, 9000087, 9000088}
DROP_SQL = (
    ROOT
    / "gms-server/src/main/resources/db/migration/"
    "V2.1.79__add_ranmaru_mob_drops.sql"
)
WARP_SCRIPT = ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/万能传送.js"
QUEST_NAMES = ("Act", "Check", "QuestInfo", "Say")


def source_map_path(map_id: int) -> Path:
    return SOURCE / f"Map/Map/Map{str(map_id)[0]}/{map_id}.img"


def client_map_path(map_id: int) -> Path:
    return ROOT / f"clien/Data/Map/Map/Map{str(map_id)[0]}/{map_id}.img"


def server_map_path(tree: str, map_id: int) -> Path:
    return ROOT / f"gms-server/{tree}/Map.wz/Map/Map{str(map_id)[0]}/{map_id}.img.xml"


def densify_numeric(parent: WzSubProperty) -> None:
    numbered = [child for child in parent.children() if child.name.isdigit()]
    if not numbered:
        return
    ordered = sorted(numbered, key=lambda child: int(child.name))
    if [child.name for child in ordered] == [str(index) for index in range(len(ordered))]:
        return
    for child in ordered:
        parent._children.pop(child.name, None)
    for index, child in enumerate(ordered):
        child.name = str(index)
        parent.add(child)


def densify_map_nodes(root: WzSubProperty) -> None:
    back = root.child("back")
    if isinstance(back, WzSubProperty):
        densify_numeric(back)
    for layer in [child for child in root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if isinstance(objects, WzSubProperty):
            densify_numeric(objects)


def town_for(map_id: int) -> int:
    if map_id in RETURN_OVERRIDES:
        return RETURN_OVERRIDES[map_id]
    if 807300100 <= map_id <= 807300199:
        return NORMAL_ENTRY
    if 807300200 <= map_id <= 807300299:
        return HARD_ENTRY
    return TOWN_MAP


def sanitize_field(root: WzSubProperty, map_id: int) -> None:
    for child in list(root.children()):
        if child.name not in arc.MAP_ROOTS:
            arc.remove_child(root, child.name)
    info = root.child("info")
    if isinstance(info, WzSubProperty):
        keep_enter = {"onUserEnter", "onFirstUserEnter"} if map_id in (
            NORMAL_BATTLE,
            HARD_BATTLE,
        ) else set()
        for name in arc.MAP_INFO_UNSUPPORTED:
            if name not in keep_enter:
                arc.remove_child(info, name)
        if map_id in (NORMAL_BATTLE, HARD_BATTLE):
            arc.set_string(info, "onUserEnter", "Ranmaru_Enter")
            arc.set_string(info, "onFirstUserEnter", "Ranmaru_EnterF")
        arc.set_int(info, "fieldLimit", 0)
        for name in ("returnMap", "forcedReturn"):
            value = arc.child_value(info, name)
            if name == "forcedReturn" and value == 999999999:
                continue
            if isinstance(value, int) and value != 999999999 and value not in (
                MAP_ID_SET | {ELNATH_ALTAR}
            ):
                arc.set_int(info, name, town_for(map_id))
        if map_id in RETURN_OVERRIDES:
            arc.set_int(info, "returnMap", RETURN_OVERRIDES[map_id])
            arc.set_int(info, "forcedReturn", RETURN_OVERRIDES[map_id])

    life = root.child("life")
    if isinstance(life, WzSubProperty):
        for entry in list(life.children()):
            if arc.child_value(entry, "type") == "n":
                npc_id = int(arc.child_value(entry, "id"))
                hidden = int(arc.child_value(entry, "hide") or 0) != 0
                if hidden or npc_id in arc.REMOVED_NPCS or npc_id in EXTRA_TOWN_REMOVED:
                    arc.remove_child(life, entry.name)
                    continue
            for name in arc.LIFE_UNSUPPORTED:
                arc.remove_child(entry, name)

    for layer in [child for child in root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if isinstance(objects, WzSubProperty):
            for entry in list(objects.children()):
                if entry.child("spineAni") is not None:
                    arc.remove_child(objects, entry.name)
                    continue
                for name in arc.OBJ_UNSUPPORTED:
                    arc.remove_child(entry, name)

    arc.downgrade_connect_nodes(root)
    back = root.child("back")
    if isinstance(back, WzSubProperty):
        for entry in list(back.children()):
            if int(arc.child_value(entry, "ani") or 0) == 2:
                arc.remove_child(back, entry.name)
                continue
            for name in arc.BACK_UNSUPPORTED:
                arc.remove_child(entry, name)

    portal = root.child("portal")
    if isinstance(portal, WzSubProperty):
        for entry in list(portal.children()):
            portal_name = str(arc.child_value(entry, "pn") or "")
            target = arc.child_value(entry, "tm")
            script = str(arc.child_value(entry, "script") or "")
            pt = int(arc.child_value(entry, "pt") or 0)
            retarget = PORTAL_RETARGETS.get(map_id, {}).get(portal_name)
            if retarget:
                arc.set_int(entry, "pt", 2)
                arc.set_int(entry, "tm", retarget[0])
                arc.set_string(entry, "tn", retarget[1])
                arc.remove_child(entry, "script")
            elif pt == 11:
                arc.set_int(entry, "pt", 7)
            elif script in KEEP_PORTAL_SCRIPTS:
                pass
            elif isinstance(target, int) and target != 999999999 and target not in (
                MAP_ID_SET | {ELNATH_ALTAR}
            ):
                arc.remove_child(portal, entry.name)
                continue
            elif script and target == 999999999:
                arc.remove_child(portal, entry.name)
                continue
            if script not in KEEP_PORTAL_SCRIPTS:
                arc.remove_child(entry, "script")
            for name in arc.PORTAL_UNSUPPORTED:
                arc.remove_child(entry, name)
        arc.downgrade_portal_types(root)
    densify_map_nodes(root)


def migrate_maps() -> tuple[dict[str, object], dict[str, int]]:
    dependencies = {
        "assets": defaultdict(set),
        "mobs": set(),
        "npcs": set(),
        "bgms": set(),
        "marks": set(),
    }
    totals = {"maps": 0, "canvases": 0, "links": 0, "resized": 0}
    for map_id in MAP_IDS:
        source = source_map_path(map_id)
        client = client_map_path(map_id)
        if client.exists():
            image = load_checked(client, arc.GMS_KEY)
            materializer = arc.CanvasMaterializer()
        else:
            image, materializer = arc.clone_image(
                source,
                lambda root, value=map_id: sanitize_field(root, value),
            )
            arc.write_client_image(client, image)
        arc.merge_dependency_sets(dependencies, arc.collect_dependencies(image))
        for tree in ("wz", "wz-zh-CN"):
            server = server_map_path(tree, map_id)
            if not server.parent.exists():
                continue
            if server.exists():
                ET.parse(server)
            else:
                arc.write_server_image(server, image, f"{map_id}.img")
        totals["maps"] += 1
        totals["canvases"] += materializer.canvases
        totals["links"] += materializer.links
        totals["resized"] += materializer.resized
    dependencies["mobs"].update(BOSS_MOBS)
    dependencies["mobs"].update(FIELD_MOBS)
    dependencies["npcs"].add(QUEST_NPC_ID)
    dependencies["npcs"].add(9130090)
    return dependencies, totals


def merge_assets_tolerant(dependencies: dict[str, object]) -> dict[str, int]:
    totals = {"files": 0, "branches": 0, "canvases": 0, "links": 0, "resized": 0, "skipped": 0}
    for (kind, name), branches in sorted(dependencies["assets"].items()):
        remaining = set(branches)
        try:
            canvases, links, resized = arc.merge_asset(kind, name, remaining)
        except RuntimeError:
            canvases = links = resized = 0
            for branch in sorted(remaining):
                try:
                    part_c, part_l, part_r = arc.merge_asset(kind, name, {branch})
                    canvases += part_c
                    links += part_l
                    resized += part_r
                except RuntimeError as exc:
                    print(f"skip asset {kind}/{name}.img/{branch}: {exc}")
                    totals["skipped"] += 1
        totals["files"] += 1
        totals["branches"] += len(branches)
        totals["canvases"] += canvases
        totals["links"] += links
        totals["resized"] += resized
    return totals


def migrate_npcs(npc_ids: set[int]) -> dict[str, int]:
    totals = {"npcs": 0, "canvases": 0, "links": 0, "resized": 0}
    with ProcessPoolExecutor(max_workers=4) as executor:
        for canvases, links, resized in executor.map(arc.migrate_one_npc, sorted(npc_ids)):
            totals["npcs"] += 1
            totals["canvases"] += canvases
            totals["links"] += links
            totals["resized"] += resized
    return totals


def migrate_reactors() -> dict[str, int]:
    totals = {"reactors": 0, "canvases": 0, "links": 0, "resized": 0}
    for reactor_id in REACTOR_IDS:
        client = ROOT / f"clien/Data/Reactor/{reactor_id}.img"
        server = ROOT / f"gms-server/wz/Reactor.wz/{reactor_id}.img.xml"
        if client.exists():
            if not server.exists():
                image = load_checked(client, arc.GMS_KEY)
                arc.write_server_image(server, image, f"{reactor_id}.img")
            totals["reactors"] += 1
            continue
        source = SOURCE / f"Reactor/{reactor_id}.img"
        image, materializer = arc.clone_image(source)
        arc.write_client_image(client, image)
        arc.write_server_image(server, image, f"{reactor_id}.img")
        zh = ROOT / f"gms-server/wz-zh-CN/Reactor.wz/{reactor_id}.img.xml"
        if zh.parent.exists() and not zh.exists():
            arc.write_server_image(zh, image, f"{reactor_id}.img")
        totals["reactors"] += 1
        totals["canvases"] += materializer.canvases
        totals["links"] += materializer.links
        totals["resized"] += materializer.resized
    return totals


def source_map_string(image, map_id: int):
    preferred = ("Sengoku_2025_Field", "japan", "jp")
    for name in preferred:
        category = image.root.child(name)
        if isinstance(category, WzSubProperty):
            node = category.child(str(map_id))
            if node is not None:
                return node
    for category in image.root.children():
        node = category.child(str(map_id))
        if node is not None:
            return node
    return None


def upsert_map_strings(map_ids: tuple[int, ...]) -> dict[str, int]:
    original = arc.source_map_string

    def lookup(image, map_id: int):
        node = source_map_string(image, map_id)
        if node is not None:
            return node
        if map_id == 807000011:
            node = WzSubProperty(str(map_id))
            add_string(node, "streetName", "楓葉丘陵")
            add_string(node, "mapName", "當主的房間")
            return node
        raise RuntimeError(f"String/Map.img missing {map_id}")

    arc.source_map_string = lookup
    try:
        totals = {
            "client_jp": arc.upsert_client_strings("Map", map_ids, "jp"),
        }
        for tree in ("wz", "wz-zh-CN"):
            totals[f"{tree}_jp"] = arc.upsert_server_strings(tree, "Map", map_ids, "jp")
        return totals
    finally:
        arc.source_map_string = original


def build_quest_nodes() -> dict[str, list[WzSubProperty]]:
    output = {name: [] for name in QUEST_NAMES}
    for quest_id in QUEST_IDS:
        signed = str(quest_id)
        info = WzSubProperty(signed)
        add_string(info, "name", "[戰國時代] 打倒森蘭丸")
        add_int(info, "area", 56)
        add_string(
            info,
            "0",
            "在#b#m807300100##k見到了#b#p9130145##k。詳細的事就聽聽他怎麼說吧。",
        )
        add_string(
            info,
            "1",
            "進入#b#m807300110##k，擊敗#o9421581#並阻止儀式。",
        )
        add_string(
            info,
            "2",
            "聽說#b#p9130090##k在#b#m211041700##k準備了祕密祭壇。將 #b#p9130090##k打倒並阻止儀式吧！",
        )
        output["QuestInfo"].append(info)

        check = WzSubProperty(signed)
        start = add_sub(check, "0")
        add_int(start, "lvmin", 120)
        add_int(start, "npc", QUEST_NPC_ID)
        end = add_sub(check, "1")
        add_int(end, "npc", QUEST_NPC_ID)
        add_int(end, "order", 1)
        mobs = add_sub(end, "mob")
        entry = add_sub(mobs, "0")
        add_int(entry, "id", NORMAL_BOSS_ID)
        add_int(entry, "count", 1)
        output["Check"].append(check)

        act = WzSubProperty(signed)
        add_sub(act, "0")
        act_end = add_sub(act, "1")
        add_int(act_end, "exp", 500000)
        output["Act"].append(act)

        say = WzSubProperty(signed)
        start_say = add_sub(say, "0")
        add_string(
            start_say,
            "0",
            "織田殘黨在廢礦深處布置了祕密祭壇。森蘭丸正在舉行會威脅楓之谷的儀式。",
        )
        no = add_sub(start_say, "no")
        add_string(no, "0", "等你準備好再來找我。")
        yes = add_sub(start_say, "yes")
        add_string(
            yes,
            "0",
            "從這裡進入祕密祭壇，擊敗#b#o9421581##k。完成後再回來告訴我。",
        )
        end_say = add_sub(say, "1")
        add_string(end_say, "0", "儀式被打斷了。楓之谷暫時安全了，謝謝你。")
        output["Say"].append(say)
    return output


def migrate_quests() -> None:
    quest_nodes = build_quest_nodes()
    for name in QUEST_NAMES:
        append_named_records(
            ROOT / f"clien/Data/Quest/{name}.img", (), quest_nodes[name]
        )
        append_server_named(
            ROOT / f"gms-server/wz/Quest.wz/{name}.img.xml", (), quest_nodes[name]
        )
        zh = ROOT / f"gms-server/wz-zh-CN/Quest.wz/{name}.img.xml"
        if zh.exists():
            append_server_named(zh, (), quest_nodes[name])


def write_drop_sql() -> None:
    field = ",\n".join(f"({mob_id})" for mob_id in FIELD_MOBS)
    bosses = ",\n".join(f"({mob_id})" for mob_id in (NORMAL_BOSS_ID, HARD_BOSS_ID))
    sql = f"""-- Momijigaoka field mobs and Mori Ranmaru boss meso/potion drops.
CREATE TEMPORARY TABLE `ranmaru_field_mob_ids` (
    `mobid` INT NOT NULL PRIMARY KEY
);
INSERT INTO `ranmaru_field_mob_ids` (`mobid`) VALUES
{field};

CREATE TEMPORARY TABLE `ranmaru_boss_mob_ids` (
    `mobid` INT NOT NULL PRIMARY KEY
);
INSERT INTO `ranmaru_boss_mob_ids` (`mobid`) VALUES
{bosses};

INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 0, 400, 800, 0, 400000 FROM `ranmaru_field_mob_ids`
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 2000005, 1, 1, 0, 100000 FROM `ranmaru_field_mob_ids`
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 0, 8000, 16000, 0, 400000 FROM `ranmaru_boss_mob_ids`
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 2000005, 1, 3, 0, 200000 FROM `ranmaru_boss_mob_ids`
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
"""
    arc.atomic_write_text(DROP_SQL, sql)


def patch_warp_script() -> None:
    text = WARP_SCRIPT.read_text(encoding="utf-8")
    town_needle = '    Array(951000000, 10000, "怪物公园#r                （消耗1万金币）#b")'
    town_line = '    Array(807000000, 10000, "枫叶丘陵#r              （消耗1万金币）#b"),\n'
    if "807000000" not in text:
        if town_needle not in text:
            raise RuntimeError("warp town anchor missing")
        text = text.replace(town_needle, town_line + town_needle, 1)
    boss_needle = '    Array(703011000, 500000, "钻机                  #r（消耗50万金币，每日3次）#b"),'
    boss_line = (
        '    Array(807300100, 500000, "森兰丸秘密祭坛            #r（消耗50万金币）#b"),\n'
    )
    if "807300100" not in text:
        if boss_needle not in text:
            raise RuntimeError("warp boss anchor missing")
        text = text.replace(boss_needle, boss_needle + "\n" + boss_line, 1)
    WARP_SCRIPT.write_text(text, encoding="utf-8")


def write_script(relative: str, contents: str) -> None:
    for tree in ("scripts-zh-CN", "scripts"):
        path = ROOT / "gms-server" / tree / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")


def write_gameplay_scripts() -> None:
    write_script(
        "portal/east_807000000.js",
        """function enter(pi) {
    pi.playPortalSound();
    pi.warp(807000011, "exit00");
    return true;
}
""",
    )
    write_script(
        "portal/BPReturn_ranmaru.js",
        """function enter(pi) {
    pi.playPortalSound();
    pi.warp(211041700, 0);
    return true;
}
""",
    )
    write_script(
        "portal/pt_ranmaruOut.js",
        """function enter(pi) {
    pi.playPortalSound();
    pi.warp(807300100, 0);
    return true;
}
""",
    )
    ticket_portal = """function enter(pi) {
    if (!pi.haveItem(4000697, 1)) {
        pi.playerMessage(5, "需要持有森兰丸挑战门票才能进入。");
        return false;
    }
    pi.openNpc(9130145);
    return true;
}
"""
    write_script("portal/Ranmaru_accept.js", ticket_portal)
    write_script("portal/Ranmaru_ptlNPC2.js", ticket_portal)
    write_script(
        "npc/9130145.js",
        (ROOT / "gms-server/scripts-zh-CN/npc/9130145.js").read_text(encoding="utf-8"),
    )
    write_script(
        "npc/9130000.js",
        (ROOT / "gms-server/scripts-zh-CN/npc/9130000.js").read_text(encoding="utf-8"),
    )
    event_template = """var isPq = true;
var minPlayers = 1, maxPlayers = 30;
var minLevel = 120, maxLevel = 255;
var entryMap = %d;
var exitMap = %d;
var recruitMap = %d;
var eventTime = 30;
var bossId = %d;
const maxLobbies = 1;
const GameConfig = Java.type('org.gms.config.GameConfig');
const LifeFactory = Java.type('org.gms.server.life.LifeFactory');
const Point = Java.type('java.awt.Point');

minPlayers = GameConfig.getServerBoolean("use_enable_solo_expeditions") ? 1 : minPlayers;
if (GameConfig.getServerBoolean("use_enable_party_level_limit_lift")) {
    minLevel = 1;
}

function init() {
    setEventRequirements();
}

function getMaxLobbies() {
    return maxLobbies;
}

function setEventRequirements() {
    em.setProperty("party", "\\r\\n   组队人数：1 ~ 30\\r\\n   等级要求：120+\\r\\n   时间限制：30 分钟");
}

function setEventExclusives(eim) {
    eim.setExclusiveItems([]);
}

function setEventRewards(eim) {
    eim.setEventRewards(1, [], []);
    eim.setEventClearStageExp([]);
    eim.setEventClearStageMeso([]);
}

function setup(channel) {
    var eim = em.newInstance("%s" + channel);
    eim.setProperty("canJoin", "1");
    eim.setIntProperty("defeatedBoss", 0);
    var map = eim.getInstanceMap(entryMap);
    map.resetPQ(1);
    map.killAllMonsters();
    var mob = LifeFactory.getMonster(bossId);
    map.spawnMonsterOnGroundBelow(mob, new Point(200, 100));
    eim.startEventTimer(eventTime * 60000);
    setEventRewards(eim);
    setEventExclusives(eim);
    return eim;
}

function afterSetup(eim) {}

function playerEntry(eim, player) {
    var map = eim.getMapInstance(entryMap);
    player.changeMap(map, map.getPortal(0));
}

function scheduledTimeout(eim) {
    end(eim);
}

function changedMap(eim, player, mapid) {
    if (mapid != entryMap) {
        eim.unregisterPlayer(player);
        if (eim.getPlayerCount() < 1) {
            end(eim);
        }
    }
}

function changedLeader(eim, leader) {}
function playerDead(eim, player) {}
function playerRevive(eim, player) {}
function playerDisconnected(eim, player) {
    eim.unregisterPlayer(player);
    if (eim.getPlayerCount() < 1) {
        end(eim);
    }
}
function leftParty(eim, player) {}
function disbandParty(eim) {}
function monsterValue(eim, mobId) { return 1; }
function playerUnregistered(eim, player) {}

function playerExit(eim, player) {
    eim.unregisterPlayer(player);
    player.changeMap(exitMap, 0);
}

function end(eim) {
    var party = eim.getPlayers();
    for (var i = 0; i < party.size(); i++) {
        playerExit(eim, party.get(i));
    }
    eim.dispose();
}

function clearPQ(eim) {
    eim.stopEventTimer();
    eim.setEventCleared();
    eim.setProperty("canJoin", "0");
    eim.dropMessage(5, "[远征队] 森兰丸已被击败。");
    eim.startEventTimer(60000);
}

function monsterKilled(mob, eim) {
    if (mob.getId() == bossId && eim.getIntProperty("defeatedBoss") == 0) {
        eim.setIntProperty("defeatedBoss", 1);
        eim.showClearEffect(mob.getMap().getId());
        clearPQ(eim);
    }
}

function allMonstersDead(eim) {}
function cancelSchedule() {}
function dispose(eim) {}
"""
    write_script(
        "event/RanmaruBattle.js",
        event_template
        % (NORMAL_BATTLE, NORMAL_ENTRY, NORMAL_ENTRY, NORMAL_BOSS_ID, "RanmaruBattle"),
    )
    write_script(
        "event/RanmaruHardBattle.js",
        event_template
        % (HARD_BATTLE, NORMAL_ENTRY, NORMAL_ENTRY, HARD_BOSS_ID, "RanmaruHardBattle"),
    )


def numeric_gaps(parent: WzSubProperty | None) -> list[int]:
    if not isinstance(parent, WzSubProperty):
        return []
    names = {int(child.name) for child in parent.children() if child.name.isdigit()}
    if not names:
        return []
    return [index for index in range(max(names) + 1) if index not in names]


def maps_needing_repair() -> list[int]:
    broken = []
    for map_id in MAP_IDS:
        path = client_map_path(map_id)
        if not path.is_file():
            broken.append(map_id)
            continue
        image = load_checked(path, arc.GMS_KEY)
        if numeric_gaps(image.root.child("back")):
            broken.append(map_id)
            continue
        for layer in [child for child in image.root.children() if child.name.isdigit()]:
            if numeric_gaps(layer.child("obj")):
                broken.append(map_id)
                break
    return broken


def main() -> int:
    arc.ROOT = ROOT
    arc.BACKUP_ROOT = Path("/private/tmp/ranmaru-migration-backup")
    arc.MAP_IDS = MAP_IDS
    arc.MAP_ID_SET = MAP_ID_SET
    if not SOURCE.exists() or not arc.MS_PROBE.exists():
        raise SystemExit("TMS IMG source or MSProbe is missing")
    print(f"maps {len(MAP_IDS)}")
    dependencies, map_stats = migrate_maps()
    print("maps", map_stats)
    print("map assets", merge_assets_tolerant(dependencies))
    print("map marks", arc.merge_map_marks(dependencies["marks"]))
    print("npcs", migrate_npcs(dependencies["npcs"]))
    print("reactors", migrate_reactors())
    print("mobs", arc.migrate_mobs(dependencies["mobs"]))
    print("ballistic", repair_ballistic_mobs(tuple(sorted(dependencies["mobs"]))))
    leftover = iter_incomplete_ballistic_attacks(tuple(sorted(dependencies["mobs"])))
    if leftover:
        raise RuntimeError(f"incomplete ballistic attacks: {leftover}")
    print("bgms", arc.migrate_bgms(dependencies["bgms"]))
    print("map strings", upsert_map_strings(MAP_IDS))
    print(
        "entity strings",
        {
            "client_mobs": arc.upsert_client_strings("Mob", dependencies["mobs"]),
            "client_npcs": arc.upsert_client_strings("Npc", dependencies["npcs"]),
            "wz_mobs": arc.upsert_server_strings("wz", "Mob", dependencies["mobs"]),
            "wz_npcs": arc.upsert_server_strings("wz", "Npc", dependencies["npcs"]),
            "zh_mobs": arc.upsert_server_strings("wz-zh-CN", "Mob", dependencies["mobs"]),
            "zh_npcs": arc.upsert_server_strings("wz-zh-CN", "Npc", dependencies["npcs"]),
        },
    )
    migrate_quests()
    write_drop_sql()
    patch_warp_script()
    write_gameplay_scripts()
    broken = maps_needing_repair()
    if broken:
        raise RuntimeError(f"obj/back gaps remain: {broken}")
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
