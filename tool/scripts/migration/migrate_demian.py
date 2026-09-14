#!/usr/bin/env python3
"""Re-migrate TMS Damien (戴米安) onto old-client map/mob contracts.

Source of truth is TMS IMG + packed Mob metadata, not prior battle scripts.
Modern nodes are projected or stripped: spine/ani=2, stigma, fieldType,
info/attack, summon 170, string maxHP/mobType, connect l1>4, ballistic type=2.
"""

from __future__ import annotations

import hashlib
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
MOB_CACHE = Path("/Users/lizixian/Library/Caches/BeiDouMapMobWorkbench/ms/Mob_00000")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_lion_king_castle as lion  # noqa: E402
from migrate_twilight_perion_monster_park import (  # noqa: E402
    iter_incomplete_ballistic_attacks,
    load_checked,
    repair_ballistic_mobs,
)
from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas  # noqa: E402


ENTRY_FIELD = 105300303
CAMP_MAP = 105300000
PHASE_ONE_MAP = 350160240
PHASE_TWO_MAP = 350160280
MAP_IDS = (ENTRY_FIELD, PHASE_ONE_MAP, PHASE_TWO_MAP)
MAP_ID_SET = set(MAP_IDS) | {CAMP_MAP}
PHASE_ONE_BOSS = 8880110
PHASE_TWO_BOSS = 8880111
BOSS_IDS = (PHASE_ONE_BOSS, PHASE_TWO_BOSS)
BOSS_HP = 2_000_000_000
KEEP_PORTAL_SCRIPTS = {
    "ptDemianOut": "ptDemianOut",
    "ptDemianOut_R": "ptDemianOut_R",
    "pt_enter": "fallenWT_boss",
    "in00": "BPReturn_Demian",
}
ATTACK_INFO_STRIP = {
    "onlyFsm", "effectAfter", "randDelayAttack", "bulletCount", "areaWarning",
}
RANGE_UNSUPPORTED = {"start", "areaCount", "attackCount"}
MELEE_RANGE_LT = (-500, -400)
MELEE_RANGE_RB = (500, 80)
MODERN_MOB_ROOT_PREFIXES = ("directionAct",)
# Cygnus 8850013 uses speed=-10 and does not walk the field. TMS Damien
# uses speed=-60 with no move: teleport/FSM, not a walk cycle.
STAND_SPEED = 0
PHASE_ONE_ATTACKS = 6
PHASE_TWO_ATTACKS = 7
# Distinct legacy MobSkill ids that already apply through MobSkill.java
# (185/176 Damien field effects, 123/128 diseases), same as other bosses.
PHASE_ONE_SKILLS = (
    {"skill": 185, "level": 1, "action": 1},
    {"skill": 176, "level": 2, "action": 2},
    {"skill": 123, "level": 4, "action": 3},
    {"skill": 128, "level": 6, "action": 4},
)
PHASE_TWO_SKILLS = (
    {"skill": 185, "level": 1, "action": 1},
    {"skill": 176, "level": 2, "action": 2},
    {"skill": 123, "level": 4, "action": 3},
    {"skill": 128, "level": 6, "action": 4},
    {"skill": 126, "level": 1, "action": 5},
    {"skill": 120, "level": 4, "action": 6},
    {"skill": 122, "level": 1, "action": 7},
    {"skill": 124, "level": 1, "action": 8},
    {"skill": 125, "level": 1, "action": 9},
    {"skill": 133, "level": 1, "action": 10},
)
SKILLS_BY_MOB = {
    PHASE_ONE_BOSS: PHASE_ONE_SKILLS,
    PHASE_TWO_BOSS: PHASE_TWO_SKILLS,
}
LEGACY_MOB_INFO = {
    "level", "maxHP", "maxMP", "hpRecovery", "mpRecovery", "speed",
    "PADamage", "MADamage", "PDDamage", "MDDamage", "PDRate", "MDRate",
    "acc", "eva", "pushed", "fs", "exp", "summonType", "firstAttack",
    "bodyAttack", "boss", "hpTagColor", "hpTagBgcolor", "elemAttr",
    "rareItemDropLevel", "mobType",
}


def source_map_path(map_id: int) -> Path:
    return SOURCE / f"Map/Map/Map{str(map_id)[0]}/{map_id}.img"


def client_map_path(map_id: int) -> Path:
    return ROOT / f"clien/Data/Map/Map/Map{str(map_id)[0]}/{map_id}.img"


def server_map_path(map_id: int) -> Path:
    return ROOT / f"gms-server/wz/Map.wz/Map/Map{str(map_id)[0]}/{map_id}.img.xml"


def source_mob_path(mob_id: int) -> Path:
    cached = MOB_CACHE / f"Mob_{mob_id}.img"
    if cached.is_file():
        return cached
    return arc.extract_mob(mob_id)


def client_mob_path(mob_id: int) -> Path:
    return ROOT / f"clien/Data/Mob/{mob_id}.img"


def server_mob_path(mob_id: int) -> Path:
    return ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"


def decode_canvases(node) -> None:
    if isinstance(node, WzCanvasProperty):
        decode_canvas(node, region="GMS")
    if hasattr(node, "children"):
        for child in node.children():
            decode_canvases(child)


def numeric_gaps(parent: WzSubProperty | None) -> list[int]:
    return lion.numeric_gaps(parent)


def sanitize_field(root: WzSubProperty, map_id: int) -> None:
    for child in list(root.children()):
        if child.name not in arc.MAP_ROOTS:
            arc.remove_child(root, child.name)
    info = root.child("info")
    if isinstance(info, WzSubProperty):
        for name in arc.MAP_INFO_UNSUPPORTED:
            arc.remove_child(info, name)
        mark = str(arc.child_value(info, "mapMark") or "")
        if mark and mark not in {"Henesys", "ElNath", "Leafre"}:
            helper = ROOT / "clien/Data/Map/MapHelper.img"
            if helper.is_file():
                marks = load_checked(helper, arc.GMS_KEY).root.child("mark")
                known = {child.name for child in marks.children()} if marks else set()
                if mark not in known:
                    arc.remove_child(info, "mapMark")
        arc.set_int(info, "fieldLimit", 0)
        if map_id in (PHASE_ONE_MAP, PHASE_TWO_MAP):
            arc.set_int(info, "returnMap", ENTRY_FIELD)
            arc.set_int(info, "forcedReturn", ENTRY_FIELD)
        elif map_id == ENTRY_FIELD:
            arc.set_int(info, "returnMap", CAMP_MAP)

    life = root.child("life")
    if isinstance(life, WzSubProperty):
        for entry in list(life.children()):
            if arc.child_value(entry, "type") == "n":
                npc_id = int(arc.child_value(entry, "id"))
                if npc_id == 9091011 or npc_id in arc.REMOVED_NPCS:
                    arc.remove_child(life, entry.name)
                    continue
            for name in arc.LIFE_UNSUPPORTED:
                arc.remove_child(entry, name)

    for layer in [child for child in root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        for entry in list(objects.children()):
            if entry.child("spineAni") is not None:
                arc.remove_child(objects, entry.name)
                continue
            if arc.child_value(entry, "oS") == "spinOff1":
                arc.remove_child(objects, entry.name)
                continue
            for name in arc.OBJ_UNSUPPORTED:
                arc.remove_child(entry, name)

    arc.downgrade_connect_nodes(root)
    back = root.child("back")
    if isinstance(back, WzSubProperty):
        for entry in list(back.children()):
            if int(arc.child_value(entry, "ani") or 0) == 2 or entry.child("spineAni") is not None:
                arc.remove_child(back, entry.name)
                continue
            for name in arc.BACK_UNSUPPORTED:
                arc.remove_child(entry, name)

    portal = root.child("portal")
    if isinstance(portal, WzSubProperty):
        for entry in list(portal.children()):
            script = str(arc.child_value(entry, "script") or "")
            pt = int(arc.child_value(entry, "pt") or 0)
            pn = str(arc.child_value(entry, "pn") or "")
            if pt in {10, 11}:
                arc.set_int(entry, "pt", 7 if script else 2)
            if pn in KEEP_PORTAL_SCRIPTS:
                arc.set_string(entry, "script", KEEP_PORTAL_SCRIPTS[pn])
            elif script and script not in KEEP_PORTAL_SCRIPTS.values():
                arc.remove_child(entry, "script")
            for name in arc.PORTAL_UNSUPPORTED:
                arc.remove_child(entry, name)
        arc.downgrade_portal_types(root)
    lion.densify_map_nodes(root)


def convert_string_hp(info: WzSubProperty) -> None:
    max_hp = info.child("maxHP")
    if isinstance(max_hp, WzStringProperty):
        arc.set_int(info, "maxHP", BOSS_HP)


def normalize_attack(attack: WzSubProperty) -> None:
    info = attack.child("info")
    if not isinstance(info, WzSubProperty):
        info = WzSubProperty("info", attack)
        attack.add(info)
    for name in ("range", "hit", "attackAfter", "ball"):
        node = attack.child(name)
        if node is None:
            continue
        attack._children.pop(name, None)
        if info.child(name) is None:
            info.add(node)
    for name in ATTACK_INFO_STRIP:
        arc.remove_child(info, name)
        arc.remove_child(attack, name)
    rng = info.child("range")
    if isinstance(rng, WzSubProperty):
        for name in RANGE_UNSUPPORTED:
            arc.remove_child(rng, name)
    ball = info.child("ball")
    if ball is None:
        return
    if info.child("type") is None:
        info.add(WzIntProperty("type", 2, info))
    elif int(arc.child_value(info, "type") or 0) != 2:
        arc.set_int(info, "type", 2)
    if info.child("bulletSpeed") is None:
        info.add(WzIntProperty("bulletSpeed", 220, info))
    hit = info.child("hit")
    if isinstance(hit, WzSubProperty) and hit.child("attach") is None:
        hit.add(WzIntProperty("attach", 1, hit))


def widen_melee_ranges(root: WzSubProperty) -> None:
    for child in root.children():
        if not (child.name.startswith("attack") and child.name[6:].isdigit()):
            continue
        if not isinstance(child, WzSubProperty):
            continue
        info = child.child("info")
        if not isinstance(info, WzSubProperty) or info.child("ball") is not None:
            continue
        rng = info.child("range")
        if not isinstance(rng, WzSubProperty) or rng.child("lt") is None or rng.child("rb") is None:
            continue
        arc.remove_child(rng, "lt")
        arc.remove_child(rng, "rb")
        rng.add(WzVectorProperty("lt", MELEE_RANGE_LT[0], MELEE_RANGE_LT[1], rng))
        rng.add(WzVectorProperty("rb", MELEE_RANGE_RB[0], MELEE_RANGE_RB[1], rng))


def expected_attacks(mob_id: int) -> list[str]:
    count = PHASE_ONE_ATTACKS if mob_id == PHASE_ONE_BOSS else PHASE_TWO_ATTACKS
    return [f"attack{index}" for index in range(1, count + 1)]


def resolve_uol(node):
    current = node
    seen: set[int] = set()
    while isinstance(current, WzUolProperty):
        if id(current) in seen or current.parent is None:
            return None
        seen.add(id(current))
        current = current.parent.get(str(current.value))
    return current


def duplicate_node(source, parent, name: str):
    if isinstance(source, WzUolProperty):
        return WzUolProperty(name, str(source.value), parent)
    if isinstance(source, WzCanvasProperty):
        output = WzCanvasProperty(name, parent)
        output.width = int(source.width)
        output.height = int(source.height)
        output.format = int(source.format)
        output.format2 = int(source.format2)
        output._png_data = source._png_data
        output._png_length = source._png_length
        output._png_offset = 0
        output._wz_image = source._wz_image
        for child in source.children():
            output.add(duplicate_node(child, output, child.name))
        return output
    if isinstance(source, WzIntProperty):
        return WzIntProperty(name, int(source.value), parent)
    if isinstance(source, WzVectorProperty):
        return WzVectorProperty(name, int(source.x), int(source.y), parent)
    if isinstance(source, WzStringProperty):
        return WzStringProperty(name, str(source.value), parent)
    if isinstance(source, WzSubProperty):
        output = WzSubProperty(name, parent)
        for child in source.children():
            output.add(duplicate_node(child, output, child.name))
        return output
    raise RuntimeError(f"cannot duplicate {type(source).__name__} {name}")


def fold_skill_after(root: WzSubProperty) -> None:
    after_names = sorted(
        (child.name for child in root.children()
         if child.name.startswith("skillAfter") and child.name.removeprefix("skillAfter").isdigit()),
        key=lambda name: int(name.removeprefix("skillAfter")),
    )
    for after_name in after_names:
        after = root.child(after_name)
        skill = root.child(f"skill{after_name.removeprefix('skillAfter')}")
        if not isinstance(after, WzSubProperty) or not isinstance(skill, WzSubProperty):
            arc.remove_child(root, after_name)
            continue
        indexes = [int(child.name) for child in skill.children() if child.name.isdigit()]
        next_idx = (max(indexes) + 1) if indexes else 0
        for frame_name in sorted(
            (child.name for child in after.children() if child.name.isdigit()),
            key=int,
        ):
            frame = after.child(frame_name)
            if isinstance(frame, WzUolProperty) and str(frame.value).startswith("../stand/"):
                skill.add(WzUolProperty(str(next_idx), str(frame.value), skill))
                next_idx += 1
                continue
            resolved = resolve_uol(frame) if isinstance(frame, WzUolProperty) else frame
            if resolved is None:
                continue
            skill.add(duplicate_node(resolved, skill, str(next_idx)))
            next_idx += 1
        arc.remove_child(root, after_name)


def install_projected_skills(root: WzSubProperty, mob_id: int) -> None:
    info = root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{mob_id} missing info")
    arc.remove_child(info, "skill")
    slots = SKILLS_BY_MOB[mob_id]
    skill = WzSubProperty("skill", info)
    for index, slot in enumerate(slots):
        action = int(slot["action"])
        if root.child(f"skill{action}") is None:
            raise RuntimeError(f"{mob_id} missing skill{action} frames")
        entry = WzSubProperty(str(index), skill)
        entry.add(WzIntProperty("skill", int(slot["skill"]), entry))
        entry.add(WzIntProperty("level", int(slot["level"]), entry))
        entry.add(WzIntProperty("action", action, entry))
        skill.add(entry)
    info.add(skill)


def sanitize_boss(root: WzSubProperty, mob_id: int) -> None:
    fold_skill_after(root)
    info = root.child("info")
    if isinstance(info, WzSubProperty):
        convert_string_hp(info)
        modern = info.child("attack")
        if isinstance(modern, WzSubProperty):
            for slot in modern.children():
                action = int(arc.child_value(slot, "action") or 0)
                legacy = root.child(f"attack{action}")
                if not isinstance(legacy, WzSubProperty):
                    continue
                legacy_info = legacy.child("info")
                if not isinstance(legacy_info, WzSubProperty):
                    continue
                if legacy_info.child("ball") is None:
                    continue
                bullet = arc.child_value(slot, "bulletSpeed")
                if bullet is not None and legacy_info.child("bulletSpeed") is None:
                    legacy_info.add(WzIntProperty("bulletSpeed", int(bullet), legacy_info))
                if arc.child_value(slot, "type") == 2 and legacy_info.child("type") is None:
                    legacy_info.add(WzIntProperty("type", 2, legacy_info))
    arc.sanitize_mob(root, mob_id)
    info = root.child("info")
    if isinstance(info, WzSubProperty):
        arc.set_int(info, "maxHP", BOSS_HP)
        pushed = arc.child_value(info, "pushed")
        if isinstance(pushed, int) and pushed > 100_000:
            arc.set_int(info, "pushed", 100_000)
        for name in list(info._children):
            if name not in LEGACY_MOB_INFO:
                arc.remove_child(info, name)
        arc.set_int(info, "speed", STAND_SPEED)
        arc.set_int(info, "bodyAttack", 1)
    for child in list(root.children()):
        if any(child.name.startswith(prefix) for prefix in MODERN_MOB_ROOT_PREFIXES):
            arc.remove_child(root, child.name)
    for child in list(root.children()):
        if child.name.startswith("attack") and child.name[6:].isdigit():
            if isinstance(child, WzSubProperty):
                normalize_attack(child)
    widen_melee_ranges(root)
    install_projected_skills(root, mob_id)


def sanitize_back_asset(root: WzSubProperty) -> None:
    arc.remove_child(root, "spine")


def write_script(relative: str, contents: str) -> None:
    for tree in ("scripts", "scripts-zh-CN"):
        path = ROOT / "gms-server" / tree / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")


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
        image, materializer = arc.clone_image(
            source_map_path(map_id),
            lambda root, value=map_id: sanitize_field(root, value),
        )
        decode_canvases(image.root)
        if image.truncated or image.parse_warnings:
            raise RuntimeError(f"cloned map {map_id} parse failed")
        if numeric_gaps(image.root.child("back")):
            raise RuntimeError(f"map {map_id} still has back gaps")
        for layer in [child for child in image.root.children() if child.name.isdigit()]:
            if numeric_gaps(layer.child("obj")):
                raise RuntimeError(f"map {map_id} still has obj gaps on layer {layer.name}")
        arc.write_client_image(client_map_path(map_id), image)
        arc.write_server_image(server_map_path(map_id), image, f"{map_id}.img")
        zh = ROOT / f"gms-server/wz-zh-CN/Map.wz/Map/Map{str(map_id)[0]}/{map_id}.img.xml"
        if zh.exists():
            raise RuntimeError(f"refusing wz-zh-CN Map overlay {zh}")
        arc.merge_dependency_sets(dependencies, arc.collect_dependencies(image))
        totals["maps"] += 1
        totals["canvases"] += materializer.canvases
        totals["links"] += materializer.links
        totals["resized"] += materializer.resized
    return dependencies, totals


def migrate_bosses() -> dict[str, int]:
    totals = {"mobs": 0, "canvases": 0, "links": 0, "resized": 0}
    for mob_id in BOSS_IDS:
        image, materializer = arc.clone_image(
            source_mob_path(mob_id),
            lambda root, value=mob_id: sanitize_boss(root, value),
        )
        decode_canvases(image.root)
        names = sorted(
            (
                child.name for child in image.root.children()
                if child.name.startswith("attack") and child.name[6:].isdigit()
            ),
            key=lambda name: int(name[6:]),
        )
        if names != expected_attacks(mob_id):
            raise RuntimeError(f"{mob_id} attacks {names} != {expected_attacks(mob_id)}")
        for name in expected_attacks(mob_id):
            attack = image.root.child(name)
            if not isinstance(attack, WzSubProperty):
                raise RuntimeError(f"{mob_id} missing TMS {name}")
        if mob_id == PHASE_TWO_BOSS:
            knives = image.root.child("attack3")
            info3 = knives.child("info") if isinstance(knives, WzSubProperty) else None
            if info3 is None or info3.child("ball") is None:
                raise RuntimeError("8880111 attack3 missing TMS flying-knife ball")
            if int(arc.child_value(info3, "type") or 0) != 2:
                raise RuntimeError("8880111 attack3 ball is not type=2")
        if image.truncated or image.parse_warnings:
            raise RuntimeError(f"cloned mob {mob_id} parse failed")
        info = image.root.child("info")
        if not isinstance(info, WzSubProperty):
            raise RuntimeError(f"{mob_id} missing info")
        if info.child("attack") is not None:
            raise RuntimeError(f"{mob_id} still has modern info/attack")
        skill = info.child("skill")
        if not isinstance(skill, WzSubProperty):
            raise RuntimeError(f"{mob_id} missing projected info/skill")
        expected = {(slot["skill"], slot["level"], slot["action"]) for slot in SKILLS_BY_MOB[mob_id]}
        actual = set()
        for slot in skill.children():
            actual.add(
                (
                    int(arc.child_value(slot, "skill") or 0),
                    int(arc.child_value(slot, "level") or 0),
                    int(arc.child_value(slot, "action") or 0),
                )
            )
            if int(arc.child_value(slot, "skill") or 0) in {170, 215, 201, 214}:
                raise RuntimeError(f"{mob_id} still has modern skill id")
        if actual != expected:
            raise RuntimeError(f"{mob_id} skill table {actual} != {expected}")
        if arc.child_value(info, "speed") != STAND_SPEED:
            raise RuntimeError(f"{mob_id} speed is not {STAND_SPEED}")
        if arc.child_value(info, "bodyAttack") != 1:
            raise RuntimeError(f"{mob_id} bodyAttack is not 1")
        if image.root.child("move") is not None:
            raise RuntimeError(f"{mob_id} should not have a walk cycle")
        skill1 = image.root.child("skill1")
        skill1_frames = [
            child for child in skill1.children()
            if child.name.isdigit()
        ] if isinstance(skill1, WzSubProperty) else []
        if mob_id == PHASE_ONE_BOSS and len(skill1_frames) < 20:
            raise RuntimeError(f"{mob_id} skill1 was not folded with skillAfter ({len(skill1_frames)} frames)")
        if not isinstance(arc.child_value(info, "maxHP"), int):
            raise RuntimeError(f"{mob_id} maxHP is not an int")
        if info.child("mobType") is not None and isinstance(info.child("mobType"), WzStringProperty):
            raise RuntimeError(f"{mob_id} still has string mobType")
        arc.write_client_image(client_mob_path(mob_id), image)
        arc.write_server_image(server_mob_path(mob_id), image, f"{mob_id}.img")
        totals["mobs"] += 1
        totals["canvases"] += materializer.canvases
        totals["links"] += materializer.links
        totals["resized"] += materializer.resized
    leftover = iter_incomplete_ballistic_attacks(BOSS_IDS)
    if leftover:
        repair_ballistic_mobs(BOSS_IDS)
        leftover = iter_incomplete_ballistic_attacks(BOSS_IDS)
    if leftover:
        raise RuntimeError(f"incomplete ballistic attacks: {leftover}")
    return totals


def migrate_boss_assets(dependencies: dict[str, object]) -> dict[str, int]:
    totals = {"files": 0, "canvases": 0, "links": 0, "resized": 0}
    back = ROOT / "clien/Data/Map/Back/BossDemian.img"
    obj = ROOT / "clien/Data/Map/Obj/BossDemian.img"
    image, materializer = arc.clone_image(
        SOURCE / "Map/Back/BossDemian.img", sanitize_back_asset
    )
    if image.root.child("spine") is not None:
        raise RuntimeError("BossDemian spine was not stripped")
    decode_canvases(image.root)
    arc.write_client_image(back, image)
    totals["files"] += 1
    totals["canvases"] += materializer.canvases
    totals["links"] += materializer.links
    totals["resized"] += materializer.resized
    image, materializer = arc.clone_image(SOURCE / "Map/Obj/BossDemian.img")
    decode_canvases(image.root)
    arc.write_client_image(obj, image)
    totals["files"] += 1
    totals["canvases"] += materializer.canvases
    totals["links"] += materializer.links
    totals["resized"] += materializer.resized
    remaining = {
        (kind, name): set(branches)
        for (kind, name), branches in dependencies["assets"].items()
        if not (kind == "Back" and name == "BossDemian")
        and not (kind == "Obj" and name == "BossDemian")
    }
    for (kind, name), branches in sorted(remaining.items()):
        try:
            canvases, links, resized = arc.merge_asset(kind, name, branches)
        except (RuntimeError, FileNotFoundError) as exc:
            print(f"skip asset {kind}/{name}: {exc}")
            continue
        totals["files"] += 1
        totals["canvases"] += canvases
        totals["links"] += links
        totals["resized"] += resized
    return totals


def install_scripts() -> None:
    write_script(
        "event/DamienBattle.js",
        """\
var minPlayers = 1, maxPlayers = 30;
var minLevel = 180, maxLevel = 255;
var entryMap = 350160240;
var phaseTwoMap = 350160280;
var exitMap = 105300303;
var eventTime = 30;
var eventMaps = [entryMap, phaseTwoMap];
var phaseOneBoss = 8880110;
var phaseTwoBoss = 8880111;
var spawnX = 800;
var spawnY = 17;
const maxLobbies = 1;
const LifeFactory = Java.type("org.gms.server.life.LifeFactory");
const Point = Java.type("java.awt.Point");

function init() {
    setEventRequirements();
}

function getMaxLobbies() {
    return maxLobbies;
}

function getEventMaps() {
    var ArrayList = Java.type("java.util.ArrayList");
    var maps = new ArrayList();
    for (var i = 0; i < eventMaps.length; i++) {
        maps.add(eventMaps[i]);
    }
    return maps;
}

function setEventRequirements() {
    em.setProperty("party", "\\r\\n   组队人数: 1 ~ 30\\r\\n   等级要求: 180 ~ 255\\r\\n   时间限制: 30 分钟");
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
    var eim = em.newInstance("DAMIEN" + channel);
    eim.setProperty("canJoin", "1");
    eim.setIntProperty("phase", 1);
    for (var i = 0; i < eventMaps.length; i++) {
        var map = eim.getInstanceMap(eventMaps[i]);
        map.resetPQ(1);
        map.killAllMonsters();
    }
    var phaseOneMap = eim.getInstanceMap(entryMap);
    phaseOneMap.spawnMonsterOnGroundBelow(LifeFactory.getMonster(phaseOneBoss), new Point(spawnX, spawnY));
    eim.startEventTimer(eventTime * 60000);
    setEventRewards(eim);
    setEventExclusives(eim);
    return eim;
}

function afterSetup(eim) {}

function playerEntry(eim, player) {
    var targetMapId = eim.getIntProperty("phase") >= 2 ? phaseTwoMap : entryMap;
    var map = eim.getInstanceMap(targetMapId);
    player.changeMap(map, map.getPortal(0));
}

function scheduledTimeout(eim) {
    end(eim);
}

function isEventMap(mapId) {
    return mapId == entryMap || mapId == phaseTwoMap;
}

function changedMap(eim, player, mapId) {
    if (isEventMap(mapId)) {
        return;
    }
    eim.unregisterPlayer(player);
    disposeIfEmpty(eim);
}

function changedLeader(eim, leader) {}
function playerDead(eim, player) {}
function playerRevive(eim, player) {
    return true;
}

function playerDisconnected(eim, player) {
    eim.unregisterPlayer(player);
    disposeIfEmpty(eim);
}

function playerUnregistered(eim, player) {}
function leftParty(eim, player) {}
function disbandParty(eim) {}

function monsterValue(eim, mobId) {
    return mobId == phaseOneBoss || mobId == phaseTwoBoss ? 1 : 0;
}

function monsterKilled(mob, eim, hasKiller) {
    if (!hasKiller) {
        return;
    }
    if (mob.getId() == phaseOneBoss && eim.getIntProperty("phase") == 1) {
        eim.setIntProperty("phase", 2);
        eim.schedule("advanceToPhaseTwo", 2500);
    } else if (mob.getId() == phaseTwoBoss && !eim.isEventCleared()) {
        eim.setProperty("canJoin", "0");
        eim.schedule("clearPQ", 1000);
    }
}

function advanceToPhaseTwo(eim) {
    var targetMap = eim.getInstanceMap(phaseTwoMap);
    eim.getInstanceMap(entryMap).killAllMonsters();
    targetMap.killAllMonsters();
    targetMap.spawnMonsterOnGroundBelow(LifeFactory.getMonster(phaseTwoBoss), new Point(spawnX, spawnY));
    var players = eim.getPlayers();
    for (var i = 0; i < players.size(); i++) {
        players.get(i).changeMap(targetMap, targetMap.getPortal(0));
    }
}

function allMonstersDead(eim, hasKiller) {}
function monsterRevive(eim, mob) {}

function clearPQ(eim) {
    eim.stopEventTimer();
    eim.setProperty("canJoin", "0");
    eim.setEventCleared();
    eim.startEventTimer(300000);
}

function playerExit(eim, player) {
    eim.unregisterPlayer(player);
    player.changeMap(exitMap, 0);
}

function end(eim) {
    var players = eim.getPlayers();
    for (var i = 0; i < players.size(); i++) {
        playerExit(eim, players.get(i));
    }
    eim.dispose();
}

function disposeIfEmpty(eim) {
    if (eim.getPlayers().isEmpty()) {
        eim.dispose();
    }
}

function giveRandomEventReward(eim, player) {}
function cancelSchedule() {}
function dispose(eim) {}
""",
    )
    write_script(
        "npc/1540895.js",
        """\
var status = 0;
var expedition;
var expedMembers;
var player;
var em;
const ExpeditionType = Java.type("org.gms.server.expeditions.ExpeditionType");
const exped = ExpeditionType.DAMIEN;
var expedName = "DAMIEN";
var expedBoss = "戴米安";
var expedMap = "世界树顶端";
var list = "你想做什么？#b\\r\\n\\r\\n#L1#查看当前远征队成员#l\\r\\n#L2#开始战斗！#l\\r\\n#L3#退出远征队#l";

function start() {
    action(1, 0, 0);
}

function action(mode, type, selection) {
    player = cm.getPlayer();
    expedition = cm.getExpedition(exped);
    em = cm.getEventManager("DamienBattle");
    if (mode != 1) {
        cm.dispose();
        return;
    }
    if (status == 0) {
        if (player.getLevel() < exped.getMinLevel() || player.getLevel() > exped.getMaxLevel()) {
            cm.sendOk("您不符合与" + expedBoss + "战斗的条件！");
            cm.dispose();
            return;
        }
        if (expedition == null) {
            cm.sendSimple("#e#b<远征：" + expedName + ">#k#n" + em.getProperty("party") + "\\r\\n\\r\\n你想组建一个团队来挑战 #r" + expedBoss + "#k 吗？\\r\\n#b#L1#让我们开始吧！#l\\r\\n#L2#不，我想再等一会儿...#l");
            status = 1;
            return;
        }
        if (expedition.isLeader(player)) {
            if (expedition.isInProgress()) {
                cm.sendOk("远征已经在进行中。");
                cm.dispose();
                return;
            }
            cm.sendSimple(list);
            status = 2;
            return;
        }
        if (expedition.isRegistering()) {
            if (expedition.contains(player)) {
                cm.sendOk("你已经注册了这次远征。请等待队长开始。");
            } else {
                cm.sendOk(expedition.addMember(cm.getPlayer()));
            }
            cm.dispose();
            return;
        }
        if (expedition.isInProgress() && expedition.contains(player)) {
            var eim = em.getInstance(expedName + player.getClient().getChannel());
            if (eim != null && eim.getIntProperty("canJoin") == 1) {
                eim.registerPlayer(player);
            } else {
                cm.sendOk("战斗已经开始。");
            }
            cm.dispose();
            return;
        }
        cm.sendOk("另一支远征队正在挑战戴米安。");
        cm.dispose();
        return;
    }
    if (status == 1) {
        if (selection != 1) {
            cm.dispose();
            return;
        }
        var res = cm.createExpedition(exped);
        if (res == 0) {
            cm.sendOk("#r戴米安远征#k已经创建。再次与我交谈即可开始战斗。");
        } else if (res > 0) {
            cm.sendOk("今日挑战次数已用完。");
        } else {
            cm.sendOk("创建远征失败，请稍后重试。");
        }
        cm.dispose();
        return;
    }
    if (status == 2) {
        if (selection == 1) {
            cm.sendOk("当前远征队长是 #r" + expedition.getLeader().getName() + "#k。");
            cm.dispose();
            return;
        }
        if (selection == 2) {
            em.setProperty("leader", player.getName());
            em.setProperty("channel", player.getClient().getChannel());
            if (!em.startInstance(expedition)) {
                cm.sendOk("已有队伍正在挑战戴米安。");
            }
            cm.dispose();
            return;
        }
        cm.endExpedition(expedition);
        cm.sendOk("远征已经结束。");
        cm.dispose();
    }
}
""",
    )
    write_script(
        "portal/fallenWT_boss.js",
        """\
function enter(pi) {
    var em = pi.getEventManager("DamienBattle");
    if (em == null) {
        pi.playerMessage(5, "戴米安挑战尚未启用。");
        return false;
    }
    var eim = em.getInstance("DAMIEN" + pi.getPlayer().getClient().getChannel());
    if (eim != null && eim.getIntProperty("canJoin") == 1) {
        eim.registerPlayer(pi.getPlayer());
        return true;
    }
    pi.openNpc(1540895);
    return false;
}
""",
    )
    write_script(
        "portal/BPReturn_Demian.js",
        """\
function enter(pi) {
    pi.playPortalSound();
    pi.warp(105300000, "sp");
    return true;
}
""",
    )
    write_script(
        "portal/ptDemianOut.js",
        """\
function enter(pi) {
    var eim = pi.getEventInstance();
    pi.playPortalSound();
    if (eim != null) {
        eim.exitPlayer(pi.getPlayer());
        return true;
    }
    pi.warp(105300303, "sp");
    return true;
}
""",
    )
    write_script(
        "portal/ptDemianOut_R.js",
        """\
function enter(pi) {
    var eim = pi.getEventInstance();
    pi.playPortalSound();
    if (eim != null) {
        eim.exitPlayer(pi.getPlayer());
        return true;
    }
    pi.warp(105300303, "sp");
    return true;
}
""",
    )


def verify_static() -> None:
    for map_id in MAP_IDS:
        image = load_checked(client_map_path(map_id), arc.GMS_KEY)
        if image.truncated or image.parse_warnings:
            raise RuntimeError(f"{map_id} parse failed")
        extra = [child.name for child in image.root.children() if child.name not in arc.MAP_ROOTS]
        if extra:
            raise RuntimeError(f"{map_id} leftover modern roots: {extra}")
        if numeric_gaps(image.root.child("back")):
            raise RuntimeError(f"{map_id} back gaps")
        for layer in [child for child in image.root.children() if child.name.isdigit()]:
            objects = layer.child("obj")
            if numeric_gaps(objects):
                raise RuntimeError(f"{map_id} obj gaps")
            if isinstance(objects, WzSubProperty):
                for entry in objects.children():
                    for name in ("spineAni", "questex", "tags", "timeScale"):
                        if entry.child(name) is not None:
                            raise RuntimeError(f"{map_id} leftover {name}")
                    if arc.child_value(entry, "oS") == "connect":
                        l1 = int(arc.child_value(entry, "l1") or 0)
                        if l1 not in {0, 1, 2, 3, 4}:
                            raise RuntimeError(f"{map_id} connect l1={l1}")
        info = image.root.child("info")
        for name in ("onUserEnter", "onFirstUserEnter", "fieldType"):
            if info is not None and info.child(name) is not None:
                raise RuntimeError(f"{map_id} leftover info/{name}")
    for mob_id in BOSS_IDS:
        image = load_checked(client_mob_path(mob_id), arc.GMS_KEY)
        if image.truncated or image.parse_warnings:
            raise RuntimeError(f"{mob_id} parse failed")
        info = image.root.child("info")
        if info.child("attack") is not None:
            raise RuntimeError(f"{mob_id} leftover modern info/attack")
        if info.child("skill") is None:
            raise RuntimeError(f"{mob_id} missing projected info/skill")
        if arc.child_value(info, "speed") != STAND_SPEED:
            raise RuntimeError(f"{mob_id} speed is not {STAND_SPEED}")
        if image.root.child("move") is not None:
            raise RuntimeError(f"{mob_id} should not have a walk cycle")
        if any(child.name.startswith("skillAfter") for child in image.root.children()):
            raise RuntimeError(f"{mob_id} leftover skillAfter")
        for name in expected_attacks(mob_id):
            attack = image.root.child(name)
            if not isinstance(attack, WzSubProperty):
                raise RuntimeError(f"{mob_id} missing TMS {name}")
            info = attack.child("info")
            if isinstance(info, WzSubProperty) and info.child("areaWarning") is not None:
                raise RuntimeError(f"{mob_id} leftover {name}/info/areaWarning")
        if mob_id == PHASE_TWO_BOSS:
            knives = image.root.child("attack3")
            info3 = knives.child("info") if isinstance(knives, WzSubProperty) else None
            if info3 is None or info3.child("ball") is None:
                raise RuntimeError("8880111 attack3 missing TMS flying-knife ball")
        visible = 0
        for node, path in arc.walk(image.root):
            if not isinstance(node, WzCanvasProperty):
                continue
            if (int(node.format), int(node.format2)) != (1, 0):
                raise RuntimeError(f"{mob_id} {path} is not ARGB4444")
            decoded = decode_canvas(node, region="GMS").convert("RGBA")
            if decoded.getbbox() is not None and decoded.size != (1, 1):
                visible += 1
            decoded.close()
        if visible == 0:
            raise RuntimeError(f"{mob_id} has no visible canvases")
        for child in image.root.children():
            if any(child.name.startswith(prefix) for prefix in MODERN_MOB_ROOT_PREFIXES):
                raise RuntimeError(f"{mob_id} leftover {child.name}")
    back = load_checked(ROOT / "clien/Data/Map/Back/BossDemian.img", arc.GMS_KEY)
    if back.root.child("spine") is not None:
        raise RuntimeError("BossDemian still has spine")
    canvas = back.root.get("back/1")
    if not isinstance(canvas, WzCanvasProperty) or (int(canvas.format), int(canvas.format2)) != (1, 0):
        raise RuntimeError("BossDemian back/1 is not ARGB4444")
    decoded = decode_canvas(canvas, region="GMS").convert("RGBA")
    if decoded.getbbox() is None:
        raise RuntimeError("BossDemian back/1 is empty")
    decoded.close()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact_hashes() -> dict[str, str]:
    paths = [client_map_path(map_id) for map_id in MAP_IDS]
    paths.extend(client_mob_path(mob_id) for mob_id in BOSS_IDS)
    paths.append(ROOT / "clien/Data/Map/Back/BossDemian.img")
    paths.append(ROOT / "clien/Data/Map/Obj/BossDemian.img")
    return {str(path.relative_to(ROOT)): sha256(path) for path in paths}


def main() -> int:
    arc.ROOT = ROOT
    arc.BACKUP_ROOT = Path("/private/tmp/damien-tms-remigrate-backup")
    arc.MAP_IDS = MAP_IDS
    arc.MAP_ID_SET = MAP_ID_SET
    mobs_only = "--mobs-only" in sys.argv
    if not SOURCE.exists():
        raise SystemExit("TMS IMG source is missing")
    for mob_id in BOSS_IDS:
        if not source_mob_path(mob_id).is_file():
            raise SystemExit(f"missing TMS mob {mob_id}")
    if not mobs_only:
        dependencies, map_stats = migrate_maps()
        print("maps", map_stats)
        print("assets", migrate_boss_assets(dependencies))
        print("bgms", arc.migrate_bgms(dependencies["bgms"]))
        print("strings", {
            "client_maps": arc.upsert_client_strings("Map", MAP_IDS, "victoria"),
            "wz_maps": arc.upsert_server_strings("wz", "Map", MAP_IDS, "victoria"),
            "zh_maps": arc.upsert_server_strings("wz-zh-CN", "Map", MAP_IDS, "victoria"),
            "client_mobs": arc.upsert_client_strings("Mob", BOSS_IDS),
            "wz_mobs": arc.upsert_server_strings("wz", "Mob", BOSS_IDS),
            "zh_mobs": arc.upsert_server_strings("wz-zh-CN", "Mob", BOSS_IDS),
        })
        install_scripts()
    print("bosses", migrate_bosses())
    verify_static()
    first = artifact_hashes()
    if not mobs_only:
        migrate_maps()
        migrate_boss_assets(dependencies)
    migrate_bosses()
    second = artifact_hashes()
    if first != second:
        raise RuntimeError(f"generator is not idempotent: {first} != {second}")
    print("idempotent", True)
    print("hashes")
    for name, digest in first.items():
        print(f"  {name} {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
