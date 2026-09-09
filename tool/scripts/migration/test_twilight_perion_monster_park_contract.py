#!/usr/bin/env python3
"""Static contract for Twilight Perion and Monster Park migration."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tool/scripts/migration/migrate_twilight_perion_monster_park.py"
SPEC = importlib.util.spec_from_file_location("twilight_park", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)

from wzpy import WzImage, WzStringProperty, WzSubProperty  # noqa: E402


def load(path: Path):
    image = migration.load_checked(path, migration.arc.GMS_KEY)
    return image


def main() -> int:
    errors: list[str] = []
    if 953400000 in migration.MAP_ID_SET:
        errors.append("excluded Monster Park maps were added to the whitelist")
    if 951000300 not in migration.MAP_ID_SET or 951000400 not in migration.MAP_ID_SET:
        errors.append("extreme Monster Park maps are missing from the whitelist")
    if len(migration.TWILIGHT_MAP_IDS) != 24:
        errors.append(f"twilight map count {len(migration.TWILIGHT_MAP_IDS)}")
    if len(migration.MAP_IDS) < 24 + 48:
        errors.append(f"map whitelist too small: {len(migration.MAP_IDS)}")

    for map_id in migration.TWILIGHT_MAP_IDS:
        path = migration.client_map_path(map_id)
        if not path.is_file():
            errors.append(f"missing twilight map {map_id}")
            continue
        image = load(path)
        if image.truncated or image.parse_warnings:
            errors.append(f"bad twilight map {map_id}")

    lobby = migration.client_map_path(951000000)
    if not lobby.is_file():
        errors.append("missing Monster Park lobby")
    else:
        image = load(lobby)
        npcs = []
        life = image.root.child("life")
        if isinstance(life, WzSubProperty):
            npcs = [
                int(migration.arc.child_value(entry, "id"))
                for entry in life.children()
                if migration.arc.child_value(entry, "type") == "n"
            ]
        if 9071000 not in npcs:
            errors.append("lobby is missing NPC 9071000")

    town = load(migration.client_map_path(273000000))
    life = town.root.child("life")
    town_npcs = {
        int(migration.arc.child_value(entry, "id"))
        for entry in life.children()
        if isinstance(life, WzSubProperty) and migration.arc.child_value(entry, "type") == "n"
    }
    for npc_id, _ in migration.TOWN_EXTRA_NPCS:
        if npc_id not in town_npcs:
            errors.append(f"twilight town missing NPC {npc_id}")

    for name in migration.QUEST_NAMES:
        image = load(ROOT / f"clien/Data/Quest/{name}.img")
        for quest_id in migration.QUEST_IDS:
            if image.root.child(str(quest_id)) is None:
                errors.append(f"missing client quest {name}/{quest_id}")
            if image.root.child(str(quest_id - 65536)) is not None:
                errors.append(f"signed alias collision {name}/{quest_id}")

    for relative in (
        "gms-server/scripts/event/MonsterPark.js",
        "gms-server/scripts/npc/9071000.js",
        "gms-server/scripts/npc/9071003.js",
        "gms-server/scripts/npc/9071005.js",
        "gms-server/scripts/npc/mPark_retire.js",
        "gms-server/scripts/portal/mPark_nextStage.js",
        "gms-server/scripts/portal/mPark_final.js",
        "gms-server/scripts/map/onUserEnter/953020200.js",
        "gms-server/scripts-zh-CN/npc/9071005.js",
        "gms-server/src/main/resources/db/migration/V2.1.76__add_twilight_perion_monster_park_drops.sql",
    ):
        if not (ROOT / relative).is_file():
            errors.append(f"missing {relative}")
    next_stage = (ROOT / "gms-server/scripts/portal/mPark_nextStage.js").read_text(
        encoding="utf-8"
    )
    if "countMonsters" not in next_stage:
        errors.append("mPark_nextStage does not require a clear")
    welcome = (ROOT / "gms-server/scripts/npc/9071000.js").read_text(encoding="utf-8")
    if "MPARK_BASIC" not in welcome or "MPARK_MIDDLE" not in welcome or "MPARK_ADVANCED" not in welcome:
        errors.append("9071000 is missing per-door region keys")
    if "DAILY_LIMIT = 2" not in welcome:
        errors.append("9071000 is missing the 2-entry daily limit")
    for portal_name, script_name in (
        ("mPark_in00.js", "mPark_in00"),
        ("mPark_in01.js", "mPark_in01"),
        ("mPark_in02.js", "mPark_in02"),
    ):
        portal = (ROOT / "gms-server/scripts/portal" / portal_name).read_text(encoding="utf-8")
        if f'openNpc(9071000, "{script_name}")' not in portal:
            errors.append(f"{portal_name} still opens the shared course menu")
    extreme_portal = (ROOT / "gms-server/scripts/portal/extreme_in03.js").read_text(
        encoding="utf-8"
    )
    if "openNpc(9071006" not in extreme_portal:
        errors.append("extreme_in03 is missing the Extreme door NPC")
    extreme_npc = (ROOT / "gms-server/scripts/npc/9071006.js").read_text(encoding="utf-8")
    if "MPARK_EXTREME" not in extreme_npc or "DAILY_LIMIT = 2" not in extreme_npc:
        errors.append("9071006 is missing the Extreme daily limit")
    if "cm.warp(EXTREME_MAP, 0)" not in extreme_npc and "cm.warp(951000300, 0)" not in extreme_npc:
        errors.append("9071006 does not warp into Extreme on confirm")
    retire = (ROOT / "gms-server/scripts/npc/9071005.js").read_text(encoding="utf-8")
    if "离开怪物公园" not in retire or "送我去下一阶段" not in retire:
        errors.append("9071005 is missing retire/next-stage dialogue")

    warp = (ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/万能传送.js").read_text(
        encoding="utf-8"
    )
    if "273000000" not in warp or "951000000" not in warp:
        errors.append("warp script is missing Twilight Perion or Monster Park")
    shuttle = (ROOT / "gms-server/scripts/npc/9071003.js").read_text(encoding="utf-8")
    if "cm.warp(951000000, 0)" not in shuttle:
        errors.append("9071003 does not warp Free Market players into Monster Park")
    fm = (ROOT / "gms-server/wz/Map.wz/Map/Map9/910000000.img.xml").read_text(encoding="utf-8")
    if 'name="8"' not in fm or 'value="9071003"' not in fm:
        errors.append("910000000 is missing the Monster Park shuttle NPC")

    twilight = load(migration.client_map_path(273010000))
    portal = twilight.root.child("portal")
    by_pn = {}
    if isinstance(portal, WzSubProperty):
        for entry in portal.children():
            pn = migration.arc.child_value(entry, "pn")
            by_pn[str(pn)] = int(migration.arc.child_value(entry, "pt") or 0)
    if by_pn.get("p000") != 10 or by_pn.get("p001") != 10:
        errors.append(f"273010000 hidden portals are not inner pt=10: {by_pn}")

    analogue = load(ROOT / "clien/Data/Map/Map/Map1/102000000.img")
    analogue_pt = None
    analogue_portal = analogue.root.child("portal")
    if isinstance(analogue_portal, WzSubProperty):
        entry = analogue_portal.child("14")
        if entry is not None:
            analogue_pt = int(migration.arc.child_value(entry, "pt") or 0)
    if analogue_pt != 10:
        errors.append(f"analogue 102000000/14 pt={analogue_pt}")

    for map_id in migration.MAP_IDS:
        path = migration.client_map_path(map_id)
        if not path.is_file():
            continue
        image = load(path)
        leftover_pt, leftover_tm = migration.inner_portal_edits(map_id, image.root)
        if leftover_pt or leftover_tm:
            errors.append(f"{map_id} inner portal edits still pending pt={leftover_pt} tm={leftover_tm}")
        leftover = migration.looping_auto_portal_names(image.root)
        if leftover:
            errors.append(f"{map_id} looping auto portals {leftover}")

    drop = load(migration.client_map_path(954100300))
    drop_pts = {}
    drop_portal = drop.root.child("portal")
    if isinstance(drop_portal, WzSubProperty):
        for entry in drop_portal.children():
            pn = str(migration.arc.child_value(entry, "pn"))
            if pn.startswith("col"):
                drop_pts[pn] = int(migration.arc.child_value(entry, "pt") or 0)
    if drop_pts and any(pt != 3 for pt in drop_pts.values()):
        errors.append(f"954100300 drop portals lost auto-touch: {drop_pts}")

    tile = load(ROOT / "clien/Data/Map/Tile/destructionPerion.img")
    if tile.root.child("info") is None:
        errors.append("Tile/destructionPerion.img is missing the legacy info node")
    if tile.root.get("enV1/1") is None:
        errors.append("Tile/destructionPerion.img is missing enV1/1")
    acc = load(ROOT / "clien/Data/Map/Obj/acc14.img")
    if acc.root.get("PerionDryRock/rock/7") is None:
        errors.append("Obj/acc14.img is missing PerionDryRock/rock/7")

    ranged = load(ROOT / "clien/Data/Mob/8620002.img")
    attack3 = ranged.root.get("attack3/info")
    analogue = load(ROOT / "clien/Data/Mob/8641002.img")
    analogue_info = analogue.root.get("attack1/info")
    if int(migration.arc.child_value(attack3, "type") or 0) != 2:
        errors.append("8620002 attack3 is missing legacy ballistic type=2")
    if int(migration.arc.child_value(attack3, "bulletSpeed") or 0) != 300:
        errors.append("8620002 attack3 is missing bulletSpeed=300")
    if attack3 is None or attack3.child("ball") is None:
        errors.append("8620002 attack3 lost ball")
    if analogue_info is None or int(migration.arc.child_value(analogue_info, "type") or 0) != 2:
        errors.append("analogue 8641002 attack1 type is not 2")

    leftover = migration.iter_incomplete_ballistic_attacks(migration.TWILIGHT_MOBS)
    if leftover:
        errors.append(f"ball attacks still missing type=2: {leftover}")

    analogue_eva = migration.analogue_eva()
    if analogue_eva != 100:
        errors.append(f"analogue 8641003 eva is {analogue_eva}")
    sample = load(migration.client_mob_path(8620002))
    sample_info = sample.root.child("info")
    if int(migration.arc.child_value(sample_info, "PADamage") or 0) != 1113:
        errors.append("8620002 PADamage was not reduced 10x from 11130")
    if int(migration.arc.child_value(sample_info, "MADamage") or 0) != 1074:
        errors.append("8620002 MADamage was not reduced 10x from 10749")
    for mob_id in migration.TWILIGHT_MOBS:
        image = load(migration.client_mob_path(mob_id))
        info = image.root.child("info")
        if int(migration.arc.child_value(info, "eva") or 0) != analogue_eva:
            errors.append(f"{mob_id} eva != {analogue_eva}")
        pad = int(migration.arc.child_value(info, "PADamage") or 0)
        mad = int(migration.arc.child_value(info, "MADamage") or 0)
        if pad >= migration.ATTACK_DAMAGE_UNSCALED_MIN:
            errors.append(f"{mob_id} PADamage {pad} was not reduced 10x")
        if mad >= migration.ATTACK_DAMAGE_UNSCALED_MIN:
            errors.append(f"{mob_id} MADamage {mad} was not reduced 10x")

    for mob_id in migration.AUTO_GUARD_COURSE_MOBS:
        image = load(migration.client_mob_path(mob_id))
        info = image.root.child("info")
        if isinstance(info.child("mobType"), WzStringProperty):
            errors.append(f"{mob_id} still has string info/mobType")
        if info.child("partyBonusMob") is not None:
            errors.append(f"{mob_id} still has info/partyBonusMob")
        if info.child("charismaEXP") is not None:
            errors.append(f"{mob_id} still has info/charismaEXP")
        if info.child("HPgaugeHide") is not None:
            errors.append(f"{mob_id} still has info/HPgaugeHide")
        if info.child("PDRate") is not None or info.child("MDRate") is not None:
            errors.append(f"{mob_id} still has PDRate/MDRate")
        if mob_id in (9800046, 9800047):
            if image.root.child("stand") is None:
                errors.append(f"{mob_id} is still a link-only combat stub")
            if info.child("link") is not None:
                errors.append(f"{mob_id} client still has info/link")
        if int(migration.arc.child_value(info, "eva") or 0) != migration.PARK_FALLBACK_EVA:
            errors.append(f"{mob_id} eva != {migration.PARK_FALLBACK_EVA}")
        if mob_id in (9800046, 9800047) and int(migration.arc.child_value(info, "boss") or 0) != 0:
            errors.append(f"{mob_id} fodder is still boss=1")
    for map_id in (953020000, 953020100):
        leftover_r = migration.iter_map_object_r_paths(load(migration.client_map_path(map_id)))
        if leftover_r:
            errors.append(f"{map_id} still has object r fields {leftover_r[:4]}")

    moss = load(migration.client_map_path(953030000))
    moss_deps = migration.arc.collect_dependencies(moss)
    for (kind, name), branches in moss_deps["assets"].items():
        if kind != "Obj" or name not in {"acc10", "guide"}:
            continue
        obj_path = ROOT / f"clien/Data/Map/Obj/{name}.img"
        if not obj_path.is_file():
            errors.append(f"missing Obj/{name}.img")
            continue
        obj = load(obj_path)
        for branch in branches:
            if obj.root.get(branch) is None:
                errors.append(f"953030000 missing Obj/{name}.img/{branch}")
        for leftover in migration.iter_canvas_link_paths(obj):
            joined = "/".join(leftover)
            if any(joined == branch or joined.startswith(branch + "/") for branch in branches):
                errors.append(f"953030000 Obj/{name}.img/{joined} still has a canvas link")

    leftover_assets = migration.used_map_asset_files_with_canvas_links()
    if leftover_assets:
        errors.append(f"map assets still have canvas links: {leftover_assets}")

    lobby = load(migration.client_map_path(951000000))
    leftover_life = migration.iter_life_modern_field_paths(lobby)
    if leftover_life:
        errors.append(f"951000000 still has modern life fields: {leftover_life}")
    board = load(ROOT / "clien/Data/Npc/9071009.img")
    info = board.root.child("info")
    for name in ("conditionEffect", "button"):
        if info is not None and info.child(name) is not None:
            errors.append(f"9071009 still has info/{name}")
    if str(migration.arc.child_value(lobby.root.child("info"), "mapMark") or "") != "Perion":
        errors.append("951000000 mapMark is not projected to Perion")
    life = lobby.root.child("life")
    if isinstance(life, WzSubProperty):
        npc_ids = [
            int(migration.arc.child_value(entry, "id") or 0)
            for entry in life.children()
            if migration.arc.child_value(entry, "type") == "n"
        ]
        if 9071009 in npc_ids:
            errors.append("951000000 still spawns modern billboard NPC 9071009")
        if 9071000 not in npc_ids:
            errors.append("951000000 lost Spiegelmann 9071000")
    pig = load(ROOT / "clien/Data/Npc/9071000.img")
    extra = [child.name for child in pig.root.children() if child.name not in {"info", "stand"}]
    if extra:
        errors.append(f"9071000 still has extra roots {extra}")
    helper = load(ROOT / "clien/Data/Map/MapHelper.img")
    park_mark = helper.root.get("mark/MonsterPark")
    henesys = helper.root.get("mark/Henesys")
    if park_mark is None or henesys is None:
        errors.append("MapHelper missing MonsterPark or Henesys mark")
    elif (int(park_mark.format), int(park_mark.format2 or 0)) != (
        int(henesys.format),
        int(henesys.format2 or 0),
    ):
        errors.append("MapHelper MonsterPark mark is not projected to Henesys format")

    analogue_jump = load(ROOT / "clien/Data/Map/Map/Map1/106021800.img")
    analogue_pt = analogue_jump.root.get("portal/2")
    if int(migration.arc.child_value(analogue_pt, "pt") or 0) != 3:
        errors.append("mushroom castle analogue 106021800 portal 2 is not pt=3")
    for map_id in migration.EXTREME_PARK_MAP_IDS:
        path = migration.client_map_path(map_id)
        if not path.is_file():
            errors.append(f"missing extreme park map {map_id}")
            continue
        image = load(path)
        leftover_pt, leftover_tm = migration.inner_portal_edits(map_id, image.root)
        if leftover_pt or leftover_tm:
            errors.append(f"{map_id} inner portal edits still pending")
        portal = image.root.child("portal")
        if not isinstance(portal, WzSubProperty):
            errors.append(f"{map_id} missing portal")
            continue
        by_name = migration.portal_by_name(portal)
        if map_id == 951000300:
            for jump_name, landing in migration.EXTREME_JUMP_LANDINGS.items():
                jump = by_name.get(jump_name)
                dest = by_name.get(landing)
                if jump is None or dest is None:
                    errors.append(f"951000300 missing {jump_name}->{landing}")
                    continue
                if int(migration.arc.child_value(jump, "pt") or 0) != 3:
                    errors.append(f"951000300 {jump_name} is not pt=3")
                if str(migration.arc.child_value(jump, "tn") or "") != landing:
                    errors.append(f"951000300 {jump_name} tn != {landing}")
                if int(migration.arc.child_value(dest, "pt") or 0) != 1:
                    errors.append(f"951000300 landing {landing} is not hidden pt=1")
            hidden = by_name.get("leftuphidden")
            if hidden is None or int(migration.arc.child_value(hidden, "pt") or 0) != 10:
                errors.append("951000300 leftuphidden is not pt=10")
        if map_id == 951000400:
            exit_pt = by_name.get("exitPT")
            if exit_pt is None or int(migration.arc.child_value(exit_pt, "pt") or 0) != 7:
                errors.append("951000400 exitPT is not script pt=7")
            if str(migration.arc.child_value(exit_pt, "script") or "") != "Extreme_out2":
                errors.append("951000400 exitPT lost Extreme_out2")

    if errors:
        print("FAIL")
        for error in errors:
            print(error)
        return 1
    print("ok", len(migration.MAP_IDS), "maps", len(migration.QUEST_IDS), "quests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
