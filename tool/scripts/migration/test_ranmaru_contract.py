#!/usr/bin/env python3
"""Static contract for the TMS Mori Ranmaru migration."""

from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tool/scripts/migration/migrate_ranmaru.py"
SPEC = importlib.util.spec_from_file_location("ranmaru", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)

from wzpy import WzCanvasProperty, WzImage, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


def iter_canvases(node):
    if isinstance(node, WzCanvasProperty):
        yield node
    children = getattr(node, "children", None)
    if callable(children):
        for child in children():
            yield from iter_canvases(child)


def audit_argb4444(path: Path, errors: list[str], label: str) -> None:
    image = load(path)
    for canvas in iter_canvases(image.root):
        fmt = (int(canvas.format), int(canvas.format2 or 0))
        if fmt != (1, 0):
            errors.append(
                f"{label} {path.name}/{canvas.name} format={fmt} is not GMS ARGB4444"
            )
            continue
        try:
            decoded = decode_canvas(canvas, region="GMS")
        except Exception as exc:
            errors.append(f"{label} {path.name}/{canvas.name} decode: {exc}")
            continue
        if decoded is None:
            continue
        if (canvas.width, canvas.height) != (1, 1) and decoded.getbbox() is None:
            errors.append(f"{label} {path.name}/{canvas.name} has no visible pixels")


def load(path: Path):
    return migration.load_checked(path, migration.arc.GMS_KEY)


def numeric_gaps(parent) -> list[int]:
    return migration.numeric_gaps(parent)


def main() -> int:
    errors: list[str] = []
    if len(migration.MAP_IDS) != 14:
        errors.append(f"unexpected map count {len(migration.MAP_IDS)}")
    for excluded in (807050400, 807100120, 811000011):
        if excluded in migration.MAP_ID_SET:
            errors.append(f"excluded map {excluded} was added")

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
            continue
        if info.child("fieldType") is not None:
            errors.append(f"map {map_id} kept fieldType")
        if info.child("spineAni") is not None:
            errors.append(f"map {map_id} kept info spineAni")
        if numeric_gaps(image.root.child("back")):
            errors.append(f"map {map_id} back gaps")
        for layer in [child for child in image.root.children() if child.name.isdigit()]:
            if numeric_gaps(layer.child("obj")):
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

    town = load(migration.client_map_path(migration.TOWN_MAP))
    life = town.root.child("life")
    town_npcs = {
        int(migration.arc.child_value(entry, "id"))
        for entry in life.children()
        if isinstance(life, WzSubProperty) and migration.arc.child_value(entry, "type") == "n"
    }
    if 9130000 not in town_npcs:
        errors.append("town missing 武田信玄")
    if 9000086 in town_npcs:
        errors.append("town kept GM NPC 9000086")

    battle = load(migration.client_map_path(migration.NORMAL_BATTLE))
    scripts = {
        str(migration.arc.child_value(entry, "script") or "")
        for entry in battle.root.child("portal").children()
    }
    if "pt_ranmaruOut" not in scripts:
        errors.append("normal battle missing exit portal script")

    entry = load(migration.client_map_path(migration.NORMAL_ENTRY))
    entry_npcs = {
        int(migration.arc.child_value(entry_life, "id"))
        for entry_life in entry.root.child("life").children()
        if migration.arc.child_value(entry_life, "type") == "n"
    }
    if migration.QUEST_NPC_ID not in entry_npcs:
        errors.append("normal entry missing 9130145")

    ranmaru_asset_globs = (
        "clien/Data/Map/Back/JPSengoku*.img",
        "clien/Data/Map/Back/JP_Zipang_Kinoko.img",
        "clien/Data/Map/Back/blackHeaven_JP.img",
        "clien/Data/Map/Obj/JPSengoku*.img",
        "clien/Data/Map/Obj/JPsengoku2014.img",
        "clien/Data/Map/Obj/PL_Sengoku3.img",
        "clien/Data/Map/Obj/connectJP.img",
        "clien/Data/Map/Tile/JPSengokuDay.img",
    )
    for pattern in ranmaru_asset_globs:
        for path in sorted(ROOT.glob(pattern)):
            audit_argb4444(path, errors, "asset")
    for map_id in migration.MAP_IDS:
        audit_argb4444(migration.client_map_path(map_id), errors, "map")
    for npc_id in (9130000, 9130145, 9130147, 9130148, 9130149):
        npc_path = ROOT / f"clien/Data/Npc/{npc_id}.img"
        if npc_path.is_file():
            audit_argb4444(npc_path, errors, "npc")
    for reactor_id in migration.REACTOR_IDS:
        reactor_path = ROOT / f"clien/Data/Reactor/{reactor_id}.img"
        if reactor_path.is_file():
            audit_argb4444(reactor_path, errors, "reactor")
    for mob_id in (*migration.FIELD_MOBS, *migration.BOSS_MOBS):
        path = ROOT / f"clien/Data/Mob/{mob_id}.img"
        if not path.is_file():
            path = ROOT / f"clien/Data/Mob/{mob_id:07d}.img"
        if not path.is_file():
            errors.append(f"missing mob {mob_id}")
            continue
        image = load(path)
        for node in [image.root] + list(image.root.children()):
            if hasattr(node, "children"):
                for child in node.children():
                    if getattr(child, "format", None) is not None:
                        try:
                            decoded = decode_canvas(child, region="GMS")
                        except Exception as exc:
                            errors.append(f"mob {mob_id} canvas {child.name}: {exc}")
                            continue
                        if decoded is None:
                            continue
        leftover = migration.iter_incomplete_ballistic_attacks((mob_id,))
        audit_argb4444(path, errors, "mob")
        if leftover:
            errors.append(f"ballistic leftover {leftover}")

    strings = load(ROOT / "clien/Data/String/Map.img")
    jp = strings.root.child("jp")
    if not isinstance(jp, WzSubProperty) or jp.child(str(migration.TOWN_MAP)) is None:
        errors.append("missing jp map string 807000000")
    mob_string = load(ROOT / "clien/Data/String/Mob.img")
    name = mob_string.root.get(f"{migration.NORMAL_BOSS_ID}/name")
    if getattr(name, "value", None) != "森蘭丸":
        errors.append("missing String/Mob 9421581 森蘭丸")

    for name in migration.QUEST_NAMES:
        image = load(ROOT / f"clien/Data/Quest/{name}.img")
        if image.root.child("57480") is None:
            errors.append(f"missing client quest {name}/57480")
        if image.root.child(str(57480 - 65536)) is not None:
            errors.append(f"signed alias collision {name}/57480")
        server = ROOT / f"gms-server/wz/Quest.wz/{name}.img.xml"
        root = ET.parse(server).getroot()
        if root.find('./imgdir[@name="57480"]') is None:
            errors.append(f"missing server quest {name}/57480")

    for relative in (
        "portal/Ranmaru_accept.js",
        "portal/Ranmaru_ptlNPC2.js",
        "portal/pt_ranmaruOut.js",
        "portal/BPReturn_ranmaru.js",
        "portal/east_807000000.js",
        "npc/9130145.js",
        "npc/9130000.js",
        "event/RanmaruBattle.js",
        "event/RanmaruHardBattle.js",
    ):
        for tree in ("scripts-zh-CN", "scripts"):
            path = ROOT / "gms-server" / tree / relative
            if not path.is_file():
                errors.append(f"missing {tree}/{relative}")
    warp = migration.WARP_SCRIPT.read_text(encoding="utf-8")
    if "807000000" not in warp or "807300100" not in warp:
        errors.append("warp script missing Ranmaru destinations")
    if not migration.DROP_SQL.is_file():
        errors.append("missing drop SQL")

    if errors:
        print("\n".join(errors))
        return 1
    print("ranmaru contract ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
