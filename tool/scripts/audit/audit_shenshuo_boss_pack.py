#!/usr/bin/env python3
"""Audit the Shenshuo eight-boss visual compatibility pack."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
sys.path.insert(0, str(ROOT / "tool" / "scripts" / "migration"))

from wzpy import WzCanvasProperty, WzImage, WzKey, WzUolProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from migrate_shenshuo_boss_pack import (  # noqa: E402
    CLIENT_HP,
    MAIN_MOBS,
    MAPS,
    MOB_NAMES,
    RELATED_MAPS,
    RETRY_MAPS,
    SAFE_SKILLS,
    SAME_FIELD_RETRY_MAPS,
    SERVER_EVA_CAP,
    SERVER_HP,
    TARGET_KEY,
)


def load(path: Path) -> WzImage:
    img = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=path.name)
    img.parse()
    return img


def walk(node, path=""):
    yield node, path
    if hasattr(node, "children"):
        for child in node.children():
            yield from walk(child, f"{path}/{child.name}" if path else child.name)


def main() -> int:
    errors = []
    canvas_total = 0
    over_2048 = []
    for mob_id in MOB_NAMES:
        client_path = ROOT / f"clien/Data/Mob/{mob_id}.img"
        server_path = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
        if not client_path.exists() or not server_path.exists():
            errors.append(f"missing mob {mob_id}")
            continue
        img = load(client_path)
        server_root = ET.parse(server_path).getroot()
        info = server_root.find("./imgdir[@name='info']")
        required_info = {"PADamage", "PDDamage", "MADamage", "MDDamage", "level"}
        present_info = {node.get("name") for node in info} if info is not None else set()
        missing_info = sorted(required_info - present_info)
        if missing_info:
            errors.append(f"mob {mob_id} missing required server info {missing_info}")
        if mob_id in MAIN_MOBS:
            client_info = img.root.child("info")
            client_hp = client_info.child("maxHP") if client_info is not None else None
            if client_hp is None or int(client_hp.value) != CLIENT_HP:
                errors.append(f"mob {mob_id} client maxHP must remain {CLIENT_HP}")
            server_hp = server_root.find("./imgdir[@name='info']/*[@name='maxHP']")
            if server_hp is None or server_hp.tag != "string" or int(server_hp.get("value")) != SERVER_HP:
                errors.append(f"mob {mob_id} server maxHP must be string {SERVER_HP}")
            server_eva = server_root.find("./imgdir[@name='info']/*[@name='eva']")
            if server_eva is None or int(server_eva.get("value")) > SERVER_EVA_CAP:
                errors.append(f"mob {mob_id} server eva must be <= {SERVER_EVA_CAP}")
        life = img.root.child("life")
        if life is not None:
            for entry in life.children():
                life_type = entry.child("type")
                life_id = entry.child("id")
                if life_type is None or life_id is None:
                    continue
                kind = str(life_type.value)
                resource_id = str(life_id.value)
                if kind == "m":
                    client_life = ROOT / f"clien/Data/Mob/{resource_id}.img"
                    server_life = ROOT / f"gms-server/wz/Mob.wz/{resource_id}.img.xml"
                elif kind == "n":
                    client_life = ROOT / f"clien/Data/Npc/{resource_id}.img"
                    server_life = ROOT / f"gms-server/wz/Npc.wz/{resource_id}.img.xml"
                else:
                    continue
                if not client_life.exists() or not server_life.exists():
                    errors.append(f"mob {mob_id} missing life {kind}:{resource_id}")
        for node, path in walk(img.root):
            if isinstance(node, WzCanvasProperty) and node.has_pixels():
                canvas_total += 1
                if int(node.format) + int(node.format2) != 1:
                    errors.append(f"non-ARGB4444 {mob_id}/{path}")
                try:
                    decode_canvas(node, region="GMS")
                except Exception as exc:
                    errors.append(f"decode {mob_id}/{path}: {exc}")
                if int(node.width) > 2048 or int(node.height) > 2048:
                    over_2048.append(f"{mob_id}/{path}:{node.width}x{node.height}")
            if isinstance(node, WzUolProperty) and node.name == "_inlink":
                if img.root.get(str(node.value)) is None:
                    errors.append(f"broken inlink {mob_id}/{path} -> {node.value}")
            if isinstance(node, WzUolProperty) and node.name == "_outlink":
                value = str(node.value)
                parts = value.split("/", 2)
                if len(parts) == 3 and parts[0] == "Mob":
                    target_path = ROOT / f"clien/Data/Mob/{parts[1]}"
                    if not target_path.exists() or load(target_path).root.get(parts[2]) is None:
                        errors.append(f"broken outlink {mob_id}/{path} -> {value}")
        for _, _, action in SAFE_SKILLS.get(mob_id, ()):
            if img.root.child(f"skill{action}") is None:
                errors.append(f"missing action {mob_id}/skill{action}")

    boss_rest_maps = {map_id: map_id for map_id in SAME_FIELD_RETRY_MAPS}
    for map_id in tuple(MAPS) + RELATED_MAPS + tuple(RETRY_MAPS):
        client_path = ROOT / f"clien/Data/Map/Map/Map{str(map_id)[0]}/{map_id}.img"
        server_path = ROOT / f"gms-server/wz/Map.wz/Map/Map{str(map_id)[0]}/{map_id}.img.xml"
        if not client_path.exists() or not server_path.exists():
            errors.append(f"missing map {map_id}")
            continue
        img = load(client_path)
        server_root = ET.parse(server_path).getroot()
        if map_id in boss_rest_maps:
            info = img.root.child("info")
            expected = boss_rest_maps[map_id]
            for field in ("returnMap", "forcedReturn"):
                node = info.child(field) if info is not None else None
                if node is None or int(node.value) != expected:
                    errors.append(f"map {map_id} {field} must use rest map {expected}")
        if map_id == 900000207:
            portal = img.root.get("portal/0")
            if portal is None or str(portal.child("pn").value) != "sp":
                errors.append("map 900000207 missing visible sp entry portal 0")
            life = server_root.find("./imgdir[@name='life']")
            slime = next(
                (
                    entry for entry in (life if life is not None else [])
                    if (entry.find("./string[@name='id']") is not None
                        and entry.find("./string[@name='id']").get("value") == "8880700")
                ),
                None,
            )
            def server_int(entry, name):
                node = entry.find(f"./int[@name='{name}']") if entry is not None else None
                return int(node.get("value")) if node is not None else None
            if slime is None or tuple(server_int(slime, name) for name in ("x", "y", "fh")) != (703, -1394, 28):
                errors.append("map 900000207 boss is not on visible foothold 28")
        if map_id in SAME_FIELD_RETRY_MAPS:
            _, _, _, retry_portal_name, retry_x, retry_y, rest_x, rest_y = SAME_FIELD_RETRY_MAPS[map_id]
            portals = img.root.child("portal")
            retry_portal = next(
                (
                    entry for entry in portals.children()
                    if entry.child("pn") is not None and str(entry.child("pn").value) == retry_portal_name
                ),
                None,
            ) if portals is not None else None
            retry_spawn = next(
                (
                    entry for entry in portals.children()
                    if entry.child("pn") is not None and str(entry.child("pn").value) == "bossRetry"
                ),
                None,
            ) if portals is not None else None
            script = retry_portal.child("script") if retry_portal is not None else None
            if script is None or str(script.value) != "shenshuoBossRetry":
                errors.append(f"map {map_id} {retry_portal_name} missing same-field retry script")
            if retry_spawn is None or (int(retry_spawn.child("x").value), int(retry_spawn.child("y").value)) != (retry_x, retry_y):
                errors.append(f"map {map_id} missing bossRetry spawn")
            elif int(retry_spawn.child("pt").value) <= 1:
                errors.append(f"map {map_id} bossRetry must not participate in random death respawn")
            rest_portal = portals.child("0") if portals is not None else None
            if rest_portal is None or (int(rest_portal.child("x").value), int(rest_portal.child("y").value)) != (rest_x, rest_y):
                errors.append(f"map {map_id} portal 0 is not at the configured left-side revive point")
        if map_id in RETRY_MAPS:
            _, _, _, _, _, retry_portal_name = RETRY_MAPS[map_id]
            if img.root.child("8") is not None:
                errors.append(f"retry map {map_id} still contains unsupported layer 8")
            client_life = img.root.child("life")
            if client_life is None or list(client_life.children()):
                errors.append(f"retry map {map_id} client life must be empty")
            server_life = server_root.find("./imgdir[@name='life']")
            if server_life is None or list(server_life):
                errors.append(f"retry map {map_id} server life must be empty")
            portals = img.root.child("portal")
            retry_portal = next(
                (
                    entry for entry in portals.children()
                    if entry.child("pn") is not None and str(entry.child("pn").value) == retry_portal_name
                ),
                None,
            ) if portals is not None else None
            script = retry_portal.child("script") if retry_portal is not None else None
            target = retry_portal.child("tm") if retry_portal is not None else None
            if script is None or str(script.value) != "shenshuoBossRetry":
                errors.append(f"retry map {map_id} portal {retry_portal_name} missing retry script")
            if target is None or int(target.value) != 999999999:
                errors.append(f"retry map {map_id} portal {retry_portal_name} must be script-only")
            if map_id == 450009301:
                dependencies = {
                    str(node.value) for node, _ in walk(img.root)
                    if node.name in ("bS", "oS") and getattr(node, "value", "")
                }
                if "DunkelBM1_2" in dependencies or "DunkelBM1_3" not in dependencies:
                    errors.append("retry map 450009301 must use the stable Dunkel boss-scene visuals")
        if map_id in (450010100, 450009400, 900000207, 410002060):
            forbidden_root = {"particle", "mobTeleport", "noSkill"}
            forbidden_info = {
                "AmbientBGM", "AmbientBGMv", "ReviveCurFieldOfNoTransfer",
                "ReviveCurFieldOfNoTransferNotDamaged", "ReviveCurFieldOfNoTransferPoint",
                "barrierArc", "barrierAut", "consumeItemCoolTime", "fieldLimit2",
                "fieldType", "largeSplit", "limitUpgradeItem", "limitUseShop", "lvLimit",
                "mode", "noChair", "noHekatonEffect", "qrLimit", "quarterView",
                "remoteEffect", "reviveCurField", "specialSound",
            }
            root_bad = {node.name for node in img.root.children()} & forbidden_root
            info_bad = {node.name for node in img.root.child("info").children()} & forbidden_info
            if root_bad or info_bad:
                errors.append(f"map {map_id} incompatible nodes root={sorted(root_bad)} info={sorted(info_bad)}")
        for node, path in walk(img.root):
            if node.name in ("bS", "oS", "tS") and getattr(node, "value", ""):
                kind = {"bS": "Back", "oS": "Obj", "tS": "Tile"}[node.name]
                dep = ROOT / f"clien/Data/Map/{kind}/{node.value}.img"
                if not dep.exists():
                    errors.append(f"map {map_id} missing {kind}/{node.value}.img")
            if node.name in ("returnMap", "forcedReturn", "tm") and getattr(node, "value", None) is not None:
                target = int(node.value)
                if target not in (-1, 999999999):
                    target_client = ROOT / f"clien/Data/Map/Map/Map{str(target)[0]}/{target}.img"
                    target_server = ROOT / f"gms-server/wz/Map.wz/Map/Map{str(target)[0]}/{target}.img.xml"
                    if not target_client.exists() or not target_server.exists():
                        errors.append(f"map {map_id} missing linked map {target}")
            if isinstance(node, WzCanvasProperty) and node.has_pixels():
                try:
                    decode_canvas(node, region="GMS")
                except Exception as exc:
                    errors.append(f"map decode {map_id}/{path}: {exc}")

    strings = load(ROOT / "clien/Data/String/Mob.img")
    ui = load(ROOT / "clien/Data/UI/UIWindow.img")
    for mob_id in MAIN_MOBS:
        if strings.root.get(f"{mob_id}/name") is None:
            errors.append(f"missing String/Mob {mob_id}")
        if ui.root.get(f"MobGage/Mob/{mob_id}") is None:
            errors.append(f"missing boss gauge {mob_id}")
    for mob_id in (8880700, 8880803):
        gauge = ui.root.get(f"MobGage/Mob/{mob_id}")
        if not isinstance(gauge, WzCanvasProperty):
            errors.append(f"boss gauge {mob_id} must be an embedded canvas")
            continue
        if int(gauge.width) < 20 or int(gauge.height) < 20:
            errors.append(f"boss gauge {mob_id} is still a placeholder: {gauge.width}x{gauge.height}")
        try:
            decode_canvas(gauge, region="GMS")
        except Exception as exc:
            errors.append(f"boss gauge {mob_id} decode failed: {exc}")

    retry_script = ROOT / "gms-server/scripts-zh-CN/portal/shenshuoBossRetry.js"
    if not retry_script.exists():
        errors.append("missing shenshuoBossRetry portal script")
    monster_source = (ROOT / "gms-server/src/main/java/org/gms/server/life/Monster.java").read_text(encoding="utf-8")
    if "case 8880700, 8880803 -> 8870000" not in monster_source:
        errors.append("missing mobile-safe boss HP bar template mapping")

    if errors:
        print("\n".join(f"ERROR: {item}" for item in errors))
        print(f"boss pack audit failed: errors={len(errors)} canvas={canvas_total}")
        return 1
    print(f"boss pack audit ok: mobs={len(MOB_NAMES)} maps={len(MAPS) + len(RELATED_MAPS) + len(RETRY_MAPS)} canvas={canvas_total} over2048={len(over_2048)}")
    for item in over_2048:
        print(f"WARN texture >2048: {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
