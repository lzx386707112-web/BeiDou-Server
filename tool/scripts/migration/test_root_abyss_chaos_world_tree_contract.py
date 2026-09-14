#!/usr/bin/env python3
"""Static contract for chaos Root Abyss plus Fallen World Tree."""

from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tool/scripts/migration/migrate_root_abyss_chaos_world_tree.py"
SPEC = importlib.util.spec_from_file_location("root_abyss_chaos_world_tree", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)

from wzpy import WzCanvasProperty, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


def load(path: Path):
    return migration.load_checked(path, migration.arc.GMS_KEY)


def portal_scripts(map_id: int) -> dict[str, str]:
    image = load(migration.client_map_path(map_id))
    portal = image.root.child("portal")
    result = {}
    if not isinstance(portal, WzSubProperty):
        return result
    for entry in portal.children():
        pn = str(migration.arc.child_value(entry, "pn") or "")
        result[pn] = str(migration.arc.child_value(entry, "script") or "")
    return result


def main() -> int:
    errors: list[str] = []
    for map_id in migration.NORMAL_MAPS:
        if migration.client_map_path(map_id).exists():
            errors.append(f"normal map {map_id} still present")
        if map_id in migration.MAP_ID_SET:
            errors.append(f"normal map {map_id} kept in MAP_IDS")
    for mob_id in migration.NORMAL_BOSS_MOBS:
        if (ROOT / f"clien/Data/Mob/{mob_id}.img").exists():
            errors.append(f"normal boss {mob_id} still present")

    for map_id in migration.MAP_IDS:
        path = migration.client_map_path(map_id)
        if not path.is_file():
            errors.append(f"missing client map {map_id}")
            continue
        image = load(path)
        if image.truncated or image.parse_warnings:
            errors.append(f"unsafe map {map_id}")
        if migration.numeric_gaps(image.root.child("back")):
            errors.append(f"map {map_id} back gaps")
        for layer in [child for child in image.root.children() if child.name.isdigit()]:
            if migration.numeric_gaps(layer.child("obj")):
                errors.append(f"map {map_id} layer {layer.name} obj gaps")
            objects = layer.child("obj")
            if isinstance(objects, WzSubProperty):
                for entry in objects.children():
                    o_s = migration.arc.child_value(entry, "oS")
                    l1 = str(migration.arc.child_value(entry, "l1") or "")
                    if o_s == "connect" and l1 not in {"0", "1", "2", "3", "4"}:
                        errors.append(f"map {map_id} modern connect l1={l1}")
                    if entry.child("spineAni") is not None:
                        errors.append(f"map {map_id} kept spineAni")
        life = image.root.child("life")
        if isinstance(life, WzSubProperty):
            for entry in life.children():
                if migration.arc.child_value(entry, "type") == "m":
                    mob_id = int(migration.arc.child_value(entry, "id"))
                    if mob_id in migration.NORMAL_BOSS_MOBS:
                        errors.append(f"map {map_id} still spawns normal boss {mob_id}")
        for tree in ("wz", "wz-zh-CN"):
            server = migration.server_map_path(tree, map_id)
            if server.exists():
                ET.parse(server)

    hub = portal_scripts(migration.HUB_MAP)
    for name in ("rootafirstDoor", "rootasecondDoor", "rootathirdDoor", "rootaforthDoor", "shijieshu"):
        if name == "shijieshu":
            if hub.get("shijieshu") != "shijieshu":
                errors.append("hub missing shijieshu")
        elif name not in hub.values():
            errors.append(f"hub missing {name}")
    if "105200100" in (ROOT / "gms-server/scripts/portal/rootafirstDoor.js").read_text(encoding="utf-8"):
        errors.append("first door still warps to normal garden")
    next_script = (ROOT / "gms-server/scripts/portal/rootaNext.js").read_text(encoding="utf-8")
    if "105200100" in next_script or "105200110" in next_script:
        errors.append("rootaNext still points at normal rooms")
    enter = (ROOT / "gms-server/scripts/map/onUserEnter/rootaBossEnter.js").read_text(encoding="utf-8")
    if "8900100" in enter or "105200110" in enter:
        errors.append("rootaBossEnter still spawns normal bosses")
    for mob_id in (8900000, 8910000, 8920000, 8930000):
        if str(mob_id) not in enter:
            errors.append(f"rootaBossEnter missing {mob_id}")

    tree = load(migration.client_map_path(migration.WORLD_TREE_MAP))
    portal = tree.root.child("portal")
    linked = False
    if isinstance(portal, WzSubProperty):
        for entry in portal.children():
            if migration.arc.child_value(entry, "pn") == "in00":
                linked = migration.arc.child_value(entry, "tm") == migration.HUB_MAP
    if not linked:
        errors.append("105300000 in00 is not linked to 105200000")
    shijieshu = ROOT / "gms-server/scripts/portal/shijieshu.js"
    if not shijieshu.is_file() or "105300000" not in shijieshu.read_text(encoding="utf-8"):
        errors.append("missing shijieshu warp to 105300000")

    for path in (
        ROOT / "clien/Data/Video/root-abyss-pierre.mcv",
        ROOT / "clien/Data/Video/root-abyss-vonbon.mcv",
        ROOT / "clien/Data/Video/root-abyss-queen.mcv",
        ROOT / "clien/Data/Video/root-abyss-vellum.mcv",
    ):
        if not path.is_file():
            errors.append(f"missing MCV {path.name}")

    if errors:
        print("\n".join(errors))
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
