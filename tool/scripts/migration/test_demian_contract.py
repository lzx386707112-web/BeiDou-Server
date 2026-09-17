#!/usr/bin/env python3
"""Static contract for the TMS Damien remigration."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_demian as migration  # noqa: E402
from wzpy import WzCanvasProperty, WzStringProperty, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def portal_map(map_id: int) -> dict[str, tuple[int, str]]:
    image = migration.load_checked(migration.client_map_path(map_id), migration.arc.GMS_KEY)
    result = {}
    portal = image.root.child("portal")
    if not isinstance(portal, WzSubProperty):
        return result
    for entry in portal.children():
        pn = str(migration.arc.child_value(entry, "pn") or "")
        result[pn] = (
            int(migration.arc.child_value(entry, "pt") or 0),
            str(migration.arc.child_value(entry, "script") or ""),
        )
    return result


def errors() -> list[str]:
    found: list[str] = []
    for map_id in migration.MAP_IDS:
        path = migration.client_map_path(map_id)
        if not path.is_file():
            found.append(f"missing map {map_id}")
            continue
        image = migration.load_checked(path, migration.arc.GMS_KEY)
        if image.truncated or image.parse_warnings:
            found.append(f"{map_id} parse failed")
        extra = [child.name for child in image.root.children() if child.name not in migration.arc.MAP_ROOTS]
        if extra:
            found.append(f"{map_id} leftover roots {extra}")
        if migration.numeric_gaps(image.root.child("back")):
            found.append(f"{map_id} back gaps")
        back = image.root.child("back")
        if isinstance(back, WzSubProperty):
            for entry in back.children():
                if int(migration.arc.child_value(entry, "ani") or 0) == 2:
                    found.append(f"{map_id} spine-style ani=2 back {entry.name}")
        for layer in [child for child in image.root.children() if child.name.isdigit()]:
            objects = layer.child("obj")
            if migration.numeric_gaps(objects):
                found.append(f"{map_id} obj gaps on {layer.name}")
            if isinstance(objects, WzSubProperty):
                for entry in objects.children():
                    if entry.child("spineAni") is not None:
                        found.append(f"{map_id} leftover spineAni")
                    if migration.arc.child_value(entry, "oS") == "connect":
                        l1 = int(migration.arc.child_value(entry, "l1") or 0)
                        if l1 not in {0, 1, 2, 3, 4}:
                            found.append(f"{map_id} connect l1={l1}")
        xml = ET.parse(migration.server_map_path(map_id)).getroot()
        if xml.find('./imgdir[@name="stigma"]') is not None:
            found.append(f"{map_id} XML still has stigma")
        zh = ROOT / f"gms-server/wz-zh-CN/Map.wz/Map/Map{str(map_id)[0]}/{map_id}.img.xml"
        if zh.exists():
            found.append(f"wz-zh-CN Map overlay {zh}")

    portals = portal_map(migration.ENTRY_FIELD)
    if portals.get("pt_enter", (None, None))[1] != "fallenWT_boss":
        found.append("105300303 pt_enter missing fallenWT_boss")
    if portals.get("in00", (None, None))[1] != "BPReturn_Demian":
        found.append("105300303 in00 missing BPReturn_Demian")
    if portal_map(migration.PHASE_ONE_MAP).get("ptDemianOut", (None, None))[1] != "ptDemianOut":
        found.append("350160240 missing ptDemianOut")
    if portal_map(migration.PHASE_TWO_MAP).get("ptDemianOut_R", (None, None))[1] != "ptDemianOut_R":
        found.append("350160280 missing ptDemianOut_R")

    strings = migration.load_checked(ROOT / "clien/Data/String/Map.img", migration.arc.GMS_KEY)
    for map_id, expected in (
        (350160240, "世界樹頂端"),
        (350160280, "世界樹頂端"),
        (105300303, "前往世界樹頂端的通道"),
    ):
        node = strings.root.get(f"victoria/{map_id}/mapName")
        if node is None or expected not in str(node.value):
            found.append(f"String/Map missing {map_id}")
    mob_strings = migration.load_checked(ROOT / "clien/Data/String/Mob.img", migration.arc.GMS_KEY)
    for mob_id in migration.BOSS_IDS:
        name = mob_strings.root.get(f"{mob_id}/name")
        if name is None or "戴米安" not in str(name.value):
            found.append(f"String/Mob missing {mob_id}")

    for mob_id in (migration.PHASE_TWO_BOSS,):
        image = migration.load_checked(migration.client_mob_path(mob_id), migration.arc.GMS_KEY)
        info = image.root.child("info")
        if info.child("attack") is not None:
            found.append(f"{mob_id} still has info/attack")
        if isinstance(info.child("maxHP"), WzStringProperty):
            found.append(f"{mob_id} maxHP is still a string")
        if isinstance(info.child("mobType"), WzStringProperty):
            found.append(f"{mob_id} mobType is still a string")
        leftover_info = [
            child.name for child in info.children()
            if child.name not in migration.LEGACY_MOB_INFO and child.name != "skill"
        ]
        if leftover_info:
            found.append(f"{mob_id} leftover info {leftover_info}")
        skill = info.child("skill")
        if skill is None:
            found.append(f"{mob_id} missing projected skill table")
        else:
            actual = set()
            for slot in skill.children():
                skill_id = int(migration.arc.child_value(slot, "skill") or 0)
                level = int(migration.arc.child_value(slot, "level") or 0)
                action = int(migration.arc.child_value(slot, "action") or 0)
                actual.add((skill_id, level, action))
                if skill_id in {170, 215, 201, 214}:
                    found.append(f"{mob_id} still uses modern skill {skill_id}")
                if skill_id not in {100, 101, 120, 122, 123, 124, 125, 126, 128, 133}:
                    found.append(f"{mob_id} unexpected skill {skill_id}")
            expected = {
                (slot["skill"], slot["level"], slot["action"])
                for slot in migration.SKILLS_BY_MOB[mob_id]
            }
            if actual != expected:
                found.append(f"{mob_id} skill table {actual} != {expected}")
        if migration.arc.child_value(info, "speed") != migration.STAND_SPEED:
            found.append(f"{mob_id} speed is not {migration.STAND_SPEED}")
        if migration.arc.child_value(info, "bodyAttack") != 1:
            found.append(f"{mob_id} bodyAttack is not 1")
        if image.root.child("move") is not None:
            found.append(f"{mob_id} should not have a walk cycle")
        skill1 = image.root.child("skill1")
        if mob_id == migration.PHASE_ONE_BOSS and isinstance(skill1, WzSubProperty):
            frames = [child.name for child in skill1.children() if child.name.isdigit()]
            if len(frames) < 20:
                found.append(f"{mob_id} skill1 missing folded skillAfter frames")
        if any(child.name.startswith("skillAfter") for child in image.root.children()):
            found.append(f"{mob_id} leftover skillAfter")
        for name in migration.expected_attacks(mob_id):
            attack = image.root.child(name)
            if not isinstance(attack, WzSubProperty):
                found.append(f"{mob_id} missing TMS {name}")
            else:
                info_node = attack.child("info")
                if isinstance(info_node, WzSubProperty) and info_node.child("areaWarning") is not None:
                    found.append(f"{mob_id} leftover {name}/info/areaWarning")
        if mob_id == migration.PHASE_TWO_BOSS:
            attack3 = image.root.child("attack3")
            info3 = attack3.child("info") if isinstance(attack3, WzSubProperty) else None
            if info3 is None or info3.child("ball") is None:
                found.append("8880111 attack3 missing TMS flying-knife ball")
        if migration.arc.child_value(info, "eva") != 100:
            found.append(f"{mob_id} eva is not 100")
        xml_root = ET.parse(migration.server_mob_path(mob_id)).getroot()
        if xml_root.find('./imgdir[@name="info"]/imgdir[@name="skill"]') is None:
            found.append(f"{mob_id} XML missing projected info/skill")
        for node, path in migration.arc.walk(image.root):
            if isinstance(node, WzCanvasProperty) and (int(node.format), int(node.format2)) != (1, 0):
                found.append(f"{mob_id} {path} is not ARGB4444")
                break
    leftover = migration.iter_incomplete_ballistic_attacks((migration.PHASE_TWO_BOSS,))
    if leftover:
        found.append(f"incomplete ballistic attacks {leftover}")

    back = migration.load_checked(ROOT / "clien/Data/Map/Back/BossDemian.img", migration.arc.GMS_KEY)
    if back.root.child("spine") is not None:
        found.append("BossDemian still has spine")
    canvas = back.root.get("back/1")
    if not isinstance(canvas, WzCanvasProperty):
        found.append("BossDemian back/1 missing")
    else:
        decoded = decode_canvas(canvas, region="GMS").convert("RGBA")
        if decoded.getbbox() is None:
            found.append("BossDemian back/1 is empty")
        decoded.close()

    bgm = migration.load_checked(ROOT / "clien/Data/Sound/Bgm45.img", migration.arc.GMS_KEY)
    if bgm.root.child("Demian True") is None:
        found.append("Bgm45 missing Demian True")

    event = (ROOT / "gms-server/scripts/event/DamienBattle.js").read_text(encoding="utf-8")
    if "8880110" not in event or "8880111" not in event:
        found.append("DamienBattle missing boss IDs")
    if "onPlayerEnter" in event or "tryClearStigma" in event:
        found.append("DamienBattle still calls removed DamienBossCompat combat hooks")
    if "startPhase(targetMap, phaseTwo, 2)" not in event:
        found.append("DamienBattle must startPhase phase 2 field mobs")
    warp_at = event.find("players.get(i).changeMap(targetMap")
    phase_at = event.find("startPhase(targetMap, phaseTwo, 2)")
    if warp_at < 0 or phase_at < 0 or phase_at < warp_at:
        found.append("DamienBattle must warp into phase 2 before spawning 8880113/8880114")
    if "350160240" not in event or "350160280" not in event:
        found.append("DamienBattle missing fight maps")
    if "170" in event.split("skill")[-1][:20]:
        pass
    npc = (ROOT / "gms-server/scripts/npc/1540895.js").read_text(encoding="utf-8")
    if "DamienBattle" not in npc or "startInstance" not in npc:
        found.append("1540895 does not start DamienBattle")
    portal = (ROOT / "gms-server/scripts/portal/fallenWT_boss.js").read_text(encoding="utf-8")
    if "DamienBattle" not in portal:
        found.append("fallenWT_boss does not join DamienBattle")
    ret = (ROOT / "gms-server/scripts/portal/BPReturn_Demian.js").read_text(encoding="utf-8")
    if "105300000" not in ret:
        found.append("BPReturn_Demian does not return to camp")
    compat = (ROOT / "gms-server/src/main/java/org/gms/server/life/DamienBossCompat.java").read_text(encoding="utf-8")
    if "handleSkillCast" in compat or "schedulePercentDamage" in compat:
        found.append("DamienBossCompat must not replace MobSkill.applyEffect")
    if "onSkill2Cast" not in compat or "planSkill2Orbs" not in compat:
        found.append("DamienBossCompat missing skill2 orb routing")
    if "onAttack3Cast" not in compat or "planAttack3Balls" not in compat:
        found.append("DamienBossCompat missing phase-two attack3 balls")
    if "SHADOW_ORB_MOB" not in compat or "FLYING_SWORD_MOB" not in compat:
        found.append("DamienBossCompat missing 8880113/8880114 field mobs")
    if "getMonster(8880102)" in compat:
        found.append("DamienBossCompat must not LifeFactory.getMonster 8880102")
    if "STAND_LEFT_STANCE" not in compat:
        found.append("DamienBossCompat must fly-patrol with stand facing")
    if "SWORD_SPAWN_DELAY_MS" not in compat:
        found.append("DamienBossCompat missing sword spawn delay constant")
    if "spawnFakeMonster" in compat or "resetMobPosition(" in compat:
        found.append("DamienBossCompat must not fake-spawn or relocate shooters")
    if "spawnMonster(" not in compat or "8880112" not in compat:
        found.append("DamienBossCompat must spawn 8880112 sphere shooters")
    if "LifeFactory.getMonster(SKILL2_ORB_MOB)" not in compat:
        found.append("DamienBossCompat must LifeFactory.getMonster the skill2 shooter")
    if "SKILL2_ORB_MOB = 8880102" in compat or "SKILL2_ORB_MOB = MobId.DAMIEN_CRASH_ON_SUMMON" in compat:
        found.append("DamienBossCompat must not summon 8880102")
    if "SKILL2_ORB_MOB = 8880165" in compat:
        found.append("DamienBossCompat must not reuse Lucid 8880165 for Damien gold fire")
    maple = (ROOT / "gms-server/src/main/java/org/gms/server/maps/MapleMap.java").read_text(encoding="utf-8")
    if "crashesOldClientOnSummon" not in maple or "refuseCrashSummon" not in maple:
        found.append("MapleMap must refuse 8880102 crash-on-summon")
    mob_id = (ROOT / "gms-server/src/main/java/org/gms/constants/id/MobId.java").read_text(encoding="utf-8")
    if "DAMIEN_CRASH_ON_SUMMON" not in mob_id:
        found.append("MobId must mark 8880102 as crash-on-summon")
    if "STIGMA_CAP" in compat:
        found.append("DamienBossCompat still has stigma combat")
    if "SKILL2_GROUND_EFFECT" not in compat:
        found.append("DamienBossCompat missing skill2 ground-burst scene")
    mob_skill = (ROOT / "gms-server/src/main/java/org/gms/server/life/MobSkill.java").read_text(encoding="utf-8")
    if "character.sendPacket(packet)" not in mob_skill:
        found.append("MobSkill must send hit packet to the victim")
    move = (ROOT / "gms-server/src/main/java/org/gms/net/server/channel/handlers/MoveLifeHandler.java").read_text(encoding="utf-8")
    if "resolveCastSkill" not in move:
        found.append("MoveLifeHandler must resolve Damien skills by action when packet ids mismatch")
    if "onSkill2Cast" not in move:
        found.append("MoveLifeHandler must queue Damien skill2 orbs")
    if "onAttack3Cast" not in move:
        found.append("MoveLifeHandler must queue Damien attack3 balls")
    if move.find("DamienBossCompat.onAttack3Cast") > move.find("attackStatus = monster.canUseAttack"):
        found.append("MoveLifeHandler must queue attack3 balls before canUseAttack")
    if "skillEffectDelayMs" not in move or "allowClientAttack" not in move:
        found.append("MoveLifeHandler must align Damien skill/attack hit timing")
    if "addHP(" in compat:
        found.append("DamienBossCompat must not apply skill2 HP before the client ball")
    if "MobSkillType" in compat:
        found.append("DamienBossCompat must not apply dummy MobSkill buffs")
    return found


def main() -> int:
    found = errors()
    if found:
        raise SystemExit("\n".join(found))
    for relative in (
        "event/DamienBattle.js",
        "npc/1540895.js",
        "portal/fallenWT_boss.js",
        "portal/BPReturn_Demian.js",
        "portal/ptDemianOut.js",
        "portal/ptDemianOut_R.js",
    ):
        for tree in ("scripts", "scripts-zh-CN"):
            path = ROOT / "gms-server" / tree / relative
            subprocess.run(["node", "--check", str(path)], check=True)
    print("damien tms contract ok", sha256(migration.client_mob_path(8880110)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
