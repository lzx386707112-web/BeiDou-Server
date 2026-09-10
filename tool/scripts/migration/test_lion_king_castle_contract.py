#!/usr/bin/env python3
"""Static contract for Lion King's Castle field/quest migration."""

from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tool/scripts/migration/migrate_lion_king_castle.py"
SPEC = importlib.util.spec_from_file_location("lion_king_castle", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)

from wzpy import WzCanvasProperty, WzImage, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


def load(path: Path):
    return migration.load_checked(path, migration.arc.GMS_KEY)


def iter_canvases(node):
    if isinstance(node, WzCanvasProperty):
        yield node
    children = getattr(node, "children", None)
    if callable(children):
        for child in children():
            yield from iter_canvases(child)


def audit_argb4444(path: Path, errors: list[str], label: str) -> None:
    image = load(path)
    if image.truncated or image.parse_warnings:
        errors.append(f"{label} {path} unsafe parse")
        return
    for canvas in iter_canvases(image.root):
        fmt = (int(canvas.format), int(canvas.format2 or 0))
        if fmt != (1, 0):
            errors.append(f"{label} {path.name} format={fmt}")
            continue
        try:
            decoded = decode_canvas(canvas, region="GMS")
        except Exception as exc:
            errors.append(f"{label} {path.name} decode: {exc}")
            continue
        if decoded is None:
            continue
        if (canvas.width, canvas.height) != (1, 1) and decoded.getbbox() is None:
            errors.append(f"{label} {path.name}/{canvas.name} has no visible pixels")


def main() -> int:
    errors: list[str] = []
    if 211070100 in migration.MAP_ID_SET:
        errors.append("Van Leon battle map was added to the migration set")
    for map_id in migration.VAN_LEON_BATTLE_MAPS:
        if map_id in migration.MAP_ID_SET:
            errors.append(f"battle map {map_id} was added")

    van_leon = ROOT / "clien/Data/Map/Map/Map2/211070100.img"
    if not van_leon.is_file():
        errors.append("existing Van Leon map 211070100 is missing")

    for map_id in migration.MAP_IDS:
        path = migration.client_map_path(map_id)
        if not path.is_file():
            errors.append(f"missing client map {map_id}")
            continue
        image = load(path)
        if image.truncated or image.parse_warnings:
            errors.append(f"unsafe map {map_id}")
        info = image.root.child("info")
        if not isinstance(info, WzSubProperty):
            errors.append(f"map {map_id} missing info")
        else:
            if info.child("fieldType") is not None:
                errors.append(f"map {map_id} kept fieldType")
            if info.child("spineAni") is not None:
                errors.append(f"map {map_id} kept info spineAni")
        if migration.numeric_gaps(image.root.child("back")):
            errors.append(f"map {map_id} back gaps")
        life = image.root.child("life")
        if isinstance(life, WzSubProperty):
            for entry in life.children():
                if migration.arc.child_value(entry, "type") == "n":
                    npc_id = int(migration.arc.child_value(entry, "id"))
                    if npc_id in migration.EXTRA_REMOVED_NPCS:
                        errors.append(f"map {map_id} kept NPC {npc_id}")
        for layer in [child for child in image.root.children() if child.name.isdigit()]:
            if migration.numeric_gaps(layer.child("obj")):
                errors.append(f"map {map_id} layer {layer.name} obj gaps")
            objects = layer.child("obj")
            if isinstance(objects, WzSubProperty):
                for entry in objects.children():
                    if entry.child("spineAni") is not None:
                        errors.append(f"map {map_id} kept spineAni object")
                    o_s = migration.arc.child_value(entry, "oS")
                    l1 = str(migration.arc.child_value(entry, "l1") or "")
                    if o_s == "connect" and l1 not in {"0", "1", "2", "3", "4"}:
                        errors.append(f"map {map_id} modern connect l1={l1}")
        for tree in ("wz", "wz-zh-CN"):
            server = migration.server_map_path(tree, map_id)
            if server.exists():
                ET.parse(server)

    entrance = load(migration.client_map_path(migration.ENTRANCE_FROM_MAP))
    portal_names = {
        str(migration.arc.child_value(entry, "pn") or "")
        for entry in entrance.root.child("portal").children()
    }
    if "in00" not in portal_names:
        errors.append("Dead Mine 211040600 missing in00 portal to the castle")

    corridor = load(migration.client_map_path(211070000))
    scripts = {
        str(migration.arc.child_value(entry, "script") or "")
        for entry in corridor.root.child("portal").children()
    }
    if "enterVL00" not in scripts:
        errors.append("corridor 211070000 missing enterVL00")
    if "BPReturn_Vanleon" not in scripts:
        errors.append("corridor 211070000 missing BPReturn_Vanleon")
    corridor_npcs = {
        int(migration.arc.child_value(entry, "id"))
        for entry in corridor.root.child("life").children()
        if migration.arc.child_value(entry, "type") == "n"
    }
    if 2161005 not in corridor_npcs:
        errors.append("corridor 211070000 missing NPC 2161005")
    if 9000174 not in corridor_npcs:
        errors.append("corridor 211070000 missing NPC 9000174")
    if not (ROOT / "clien/Data/Npc/9000174.img").is_file():
        errors.append("missing NPC resource 9000174")
    else:
        audit_argb4444(ROOT / "clien/Data/Npc/9000174.img", errors, "npc")

    roof = load(migration.client_map_path(211061001))
    roof_scripts = {
        str(migration.arc.child_value(entry, "script") or "")
        for entry in roof.root.child("portal").children()
    }
    if "pt_rosegarden" not in roof_scripts:
        errors.append("211061001 missing pt_rosegarden")

    first_tower = load(migration.client_map_path(211060200))
    first_scripts = {
        str(migration.arc.child_value(entry, "pn") or ""): str(migration.arc.child_value(entry, "script") or "")
        for entry in first_tower.root.child("portal").children()
    }
    if first_scripts.get("east00") != "gotoNext1":
        errors.append("211060200 east00 missing gotoNext1")
    if first_scripts.get("up00") != "1stTowerTop":
        errors.append("211060200 up00 missing 1stTowerTop")
    first_roof = load(migration.client_map_path(211060201))
    first_roof_mobs = {
        str(migration.arc.child_value(entry, "id"))
        for entry in first_roof.root.child("life").children()
        if migration.arc.child_value(entry, "type") == "m"
    }
    if "8210010" not in first_roof_mobs:
        errors.append("211060201 missing first-tower Ani 8210010")
    if "8840002" in first_roof_mobs:
        errors.append("211060201 still spawns Von Leon clone 8840002")
    if any(int(migration.arc.child_value(entry, "mobTime") or 0) < 0 for entry in first_roof.root.child("life").children()):
        errors.append("211060201 still uses non-respawning mobTime")
    if not (ROOT / "clien/Data/Mob/8210010.img").is_file():
        errors.append("missing mob 8210010")
    else:
        audit_argb4444(ROOT / "clien/Data/Mob/8210010.img", errors, "mob")

    def roof_mobs(map_id: int) -> tuple[set[str], list]:
        roof = load(migration.client_map_path(map_id))
        entries = list(roof.root.child("life").children())
        ids = {
            str(migration.arc.child_value(entry, "id"))
            for entry in entries
            if migration.arc.child_value(entry, "type") == "m"
        }
        return ids, entries

    second_ids, second_entries = roof_mobs(211060401)
    if "8210011" not in second_ids:
        errors.append("211060401 missing second-tower Ani 8210011")
    if "8210006" in second_ids:
        errors.append("211060401 still spawns instructor 8210006")
    if any(int(migration.arc.child_value(entry, "mobTime") or 0) < 0 for entry in second_entries):
        errors.append("211060401 still uses non-respawning mobTime")
    third_ids, third_entries = roof_mobs(211060601)
    if "8210012" not in third_ids:
        errors.append("211060601 missing third-tower Ani 8210012")
    if "8210007" in third_ids:
        errors.append("211060601 still spawns instructor 8210007")
    if any(int(migration.arc.child_value(entry, "mobTime") or 0) < 0 for entry in third_entries):
        errors.append("211060601 still uses non-respawning mobTime")
    fourth_ids, fourth_entries = roof_mobs(211060801)
    if "8210014" not in fourth_ids:
        errors.append("211060801 missing fourth-tower Ani soul 8210014")
    if len(fourth_ids) == 0:
        errors.append("211060801 still has empty life")
    if any(int(migration.arc.child_value(entry, "mobTime") or 0) < 0 for entry in fourth_entries):
        errors.append("211060801 still uses non-respawning mobTime")
    for mob_id in (8210011, 8210012, 8210014):
        path = ROOT / f"clien/Data/Mob/{mob_id}.img"
        if not path.is_file():
            errors.append(f"missing mob {mob_id}")
        else:
            audit_argb4444(path, errors, "mob")
    audience = load(migration.client_map_path(211070100))
    audience_scripts = {
        str(migration.arc.child_value(entry, "script") or "")
        for entry in audience.root.child("portal").children()
    }
    if "lioncastleout" not in audience_scripts:
        errors.append("211070100 missing lioncastleout")
    if "portalNPC" in audience_scripts:
        errors.append("211070100 still uses shared portalNPC")

    garden = load(migration.client_map_path(211080000))
    garden_npcs = {
        int(migration.arc.child_value(entry, "id"))
        for entry in garden.root.child("life").children()
        if migration.arc.child_value(entry, "type") == "n"
    }
    if 2162000 not in garden_npcs:
        errors.append("211080000 missing gardener NPC 2162000")
    ani_ids, _ani_entries = roof_mobs(211061100)
    if "8210013" not in ani_ids:
        errors.append("211061100 missing instructor Ani 8210013")
    summon_ani = (ROOT / "gms-server/scripts-zh-CN/map/onFirstUserEnter/summon_ani.js").read_text(encoding="utf-8")
    if "8210013" not in summon_ani or "spawnMonsterOnGroundBelowIfMissing" not in summon_ani:
        errors.append("summon_ani.js does not spawn 8210013")
    garden_scripts = {
        str(migration.arc.child_value(entry, "script") or "")
        for entry in garden.root.child("portal").children()
    }
    if "pt_rosegardenout" not in garden_scripts:
        errors.append("211080000 missing pt_rosegardenout")

    for map_id in (211080100, 211080200, 211080300, 211080400, 211080500, 211080600):
        if not migration.client_map_path(map_id).is_file():
            errors.append(f"missing rose garden map {map_id}")

    portal_npc = (ROOT / "gms-server/scripts-zh-CN/portal/portalNPC.js").read_text(encoding="utf-8")
    if "211070100" in portal_npc:
        errors.append("shared portalNPC.js was overwritten to Van Leon")
    if "211050000" not in portal_npc:
        errors.append("shared portalNPC.js lost its original warp")

    for npc_id in (2161015, 2161016, 2161017, 2161018, 2161019, 2161020, 2161026):
        path = ROOT / f"clien/Data/Npc/{npc_id}.img"
        if not path.is_file():
            errors.append(f"missing NPC {npc_id}")
        else:
            audit_argb4444(path, errors, "npc")
    for mob_id in (8210007, 8840002, 8211000, 8211001, 8211002, 8211005, 8211006, 8211007):
        path = ROOT / f"clien/Data/Mob/{mob_id}.img"
        if not path.is_file():
            errors.append(f"missing mob {mob_id}")
        else:
            audit_argb4444(path, errors, "mob")

    quests = load(ROOT / "clien/Data/Quest/QuestInfo.img")
    for quest_id in migration.QUEST_IDS:
        if quests.root.child(str(quest_id)) is None:
            errors.append(f"client QuestInfo missing {quest_id}")

    etc = load(ROOT / "clien/Data/Item/Etc/0403.img")
    for _item_id, img_name, node_name in migration.ETC_ITEMS:
        if img_name != "0403.img":
            continue
        node = etc.root.child(node_name)
        if not isinstance(node, WzSubProperty):
            errors.append(f"missing item {node_name}")
            continue
        icon = node.get("info/icon")
        if not isinstance(icon, WzCanvasProperty) or (icon.width, icon.height) == (1, 1):
            errors.append(f"{node_name} icon is still a 1x1 placeholder")
    consume = load(ROOT / "clien/Data/Item/Consume/0203.img")
    if consume.root.child("02030021") is None:
        errors.append("missing consume 02030021")

    warp = migration.WARP_SCRIPT.read_text(encoding="utf-8")
    if "211060000" not in warp:
        errors.append("万能传送 missing 狮子王城")
    advanced = migration.ADVANCED_BOSS_WARP.read_text(encoding="utf-8")
    for needle in ("守护天使绿水灵", "咖凌", "8880700", "8880830", "咖凌终局之战"):
        if needle in advanced:
            errors.append(f"advanced boss warp still mentions {needle}")
    retry = migration.RETRY_PORTAL.read_text(encoding="utf-8")
    if "221040001" in retry or "900000207" in retry:
        errors.append("retry portal still warps to removed bosses")

    for mob_id in migration.REMOVED_BOSS_MOBS:
        if (ROOT / f"clien/Data/Mob/{mob_id}.img").exists():
            errors.append(f"removed boss mob {mob_id} still present")
    for map_id in migration.REMOVED_BOSS_MAPS:
        if migration.client_map_path(map_id).exists():
            errors.append(f"removed boss map {map_id} still present")

    for relative in (
        "gms-server/scripts-zh-CN/portal/lionCastle_enter.js",
        "gms-server/scripts-zh-CN/portal/BPReturn_Vanleon.js",
        "gms-server/scripts-zh-CN/portal/enterVL00.js",
        "gms-server/scripts-zh-CN/portal/pt_rosegarden.js",
        "gms-server/scripts-zh-CN/portal/pt_rosegardenout.js",
        "gms-server/scripts-zh-CN/portal/gotoNext1.js",
        "gms-server/scripts-zh-CN/portal/1stTowerTop.js",
        "gms-server/scripts-zh-CN/portal/gotoNext2_1.js",
        "gms-server/scripts-zh-CN/portal/gotoNext4.js",
        "gms-server/scripts-zh-CN/portal/lioncastleout.js",
        "gms-server/scripts-zh-CN/quest/3178.js",
        "gms-server/scripts-zh-CN/quest/3182.js",
        "gms-server/scripts-zh-CN/map/onUserEnter/enter_211070000.js",
        "gms-server/scripts-zh-CN/map/onUserEnter/enter_211080000.js",
        "gms-server/scripts-zh-CN/map/onFirstUserEnter/summon_ani.js",
    ):
        if not (ROOT / relative).is_file():
            errors.append(f"missing script {relative}")

    quest_drop_sql = ROOT / "gms-server/src/main/resources/db/migration/V2.1.83__add_lion_king_castle_quest_drops.sql"
    if not quest_drop_sql.is_file():
        errors.append("missing lion king quest drop SQL")
    else:
        quest_text = quest_drop_sql.read_text(encoding="utf-8")
        for needle in ("4032831", "4032835", "4032836", "4032838", "4032839"):
            if needle not in quest_text:
                errors.append(f"quest drop SQL missing {needle}")
    routing = (ROOT / "gms-server/src/main/java/org/gms/client/Character.java").read_text(encoding="utf-8")
    if "FIRST_TOWER_GUARD_QUEST" not in routing:
        errors.append("missing first-tower quest kill routing")
    garden_js = (ROOT / "gms-server/scripts-zh-CN/portal/pt_rosegarden.js").read_text(encoding="utf-8")
    if "4032836" not in garden_js:
        errors.append("rose garden portal is not key-gated")
    first_js = (ROOT / "gms-server/scripts-zh-CN/portal/1stTowerTop.js").read_text(encoding="utf-8")
    if "4032858" not in first_js:
        errors.append("first tower roof ignores the temporary key")

    leftover = migration.iter_incomplete_ballistic_attacks(
        (8210007, 8840002, 8210000, 8210010, 8210011, 8210012, 8210013, 8210014, 8211000, 8211001, 8211002, 8211005, 8211006, 8211007)
    )
    if leftover:
        errors.append(f"incomplete ballistic attacks: {leftover}")

    later_drop_sql = ROOT / "gms-server/src/main/resources/db/migration/V2.1.85__add_later_tower_ani_drops.sql"
    if not later_drop_sql.is_file():
        errors.append("missing later-tower Ani drop SQL")
    else:
        later_text = later_drop_sql.read_text(encoding="utf-8")
        for mob_id in (8210011, 8210012, 8210014):
            if f"({mob_id}, 0," not in later_text:
                errors.append(f"later-tower drop SQL missing meso for {mob_id}")

    drop_sql = ROOT / "gms-server/src/main/resources/db/migration/V2.1.82__add_lion_king_castle_field_drops.sql"
    if not drop_sql.is_file():
        errors.append("missing lion king field drop SQL")
    else:
        text = drop_sql.read_text(encoding="utf-8")
        required = {
            (8210000, 4000625),
            (8210001, 4000626),
            (8210002, 4000626),
            (8210003, 4000627),
            (8210004, 4000628),
            (8210005, 4000629),
        }
        for mob_id, item_id in required:
            if f"({mob_id}, {item_id}," not in text:
                errors.append(f"drop SQL missing {mob_id}->{item_id}")
        for mob_id in (8210000, 8210001, 8210002, 8210003, 8210004, 8210005, 8210006, 8210007, 8840002, 8211000, 8211001, 8211002, 8211005, 8211006, 8211007):
            if f"({mob_id}, 0," not in text:
                errors.append(f"drop SQL missing meso for {mob_id}")
        etc = load(ROOT / "clien/Data/Item/Etc/0400.img")
        for item_id in (4000625, 4000626, 4000627, 4000628, 4000629, 4000630):
            node = etc.root.child(f"0{item_id}")
            if node is None:
                errors.append(f"client missing drop item 0{item_id}")
                continue
            icon = node.get("info/icon")
            if not isinstance(icon, WzCanvasProperty) or (icon.width, icon.height) == (1, 1):
                errors.append(f"0{item_id} icon is still a 1x1 placeholder")
        coin = load(ROOT / "clien/Data/Item/Etc/0431.img")
        medal = coin.root.child("04310010")
        if medal is None:
            errors.append("client missing royal medal 04310010")
        else:
            icon = medal.get("info/icon")
            if not isinstance(icon, WzCanvasProperty) or (icon.width, icon.height) == (1, 1):
                errors.append("04310010 icon is still a 1x1 placeholder")
        later_purify = ROOT / "gms-server/src/main/resources/db/migration/V2.1.86__add_ani_pendant_and_purification_drops.sql"
        if not later_purify.is_file():
            errors.append("missing 3178/3199 drop SQL")
        else:
            purify_text = later_purify.read_text(encoding="utf-8")
            if "(8210000, 4000630," not in purify_text:
                errors.append("purification drop SQL missing 4000630")
            if "(8210005, 4310010," not in purify_text:
                errors.append("purification drop SQL missing 4310010")

    equipment_sql = ROOT / "gms-server/src/main/resources/db/migration/V2.1.87__add_lion_king_castle_equipment_drops.sql"
    if not equipment_sql.is_file():
        errors.append("missing castle equipment drop SQL")
    else:
        equipment_text = equipment_sql.read_text(encoding="utf-8")
        if ", 700)" not in equipment_text and ", 700)," not in equipment_text:
            errors.append("castle equipment drop chance is not 0.07% (700)")
        for item_id in (1302334, 1382101, 1003946, 1492190, 1132242):
            if f", {item_id}," not in equipment_text:
                errors.append(f"castle equipment drop SQL missing {item_id}")
        for mob_id in (8210000, 8210001, 8210002, 8210003, 8210004, 8210005, 8211000, 8211001, 8211002, 8211005, 8211006, 8211007):
            if f"({mob_id}, " not in equipment_text:
                errors.append(f"castle equipment drop SQL missing mob {mob_id}")

    if errors:
        print("\n".join(errors))
        return 1
    print("lion king castle contract ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
