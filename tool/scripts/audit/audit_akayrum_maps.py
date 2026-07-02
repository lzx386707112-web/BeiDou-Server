#!/usr/bin/env python3
"""Audit Arkarium / 272 map resources against the current GMS client."""

from __future__ import annotations

import collections
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import WzCanvasProperty, WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


KEY = WzKey.for_region("GMS")
CLIENT = ROOT / "clien/Data"
SERVER = ROOT / "gms-server"
MAP_DIR = CLIENT / "Map/Map/Map2"


def load_img(path: Path, cache: dict[Path, WzImage]) -> WzImage | None:
    if not path.exists():
        return None
    if path not in cache:
        img = WzImage.from_bytes(path.read_bytes(), key=KEY, name=path.name)
        img.parse()
        cache[path] = img
    return cache[path]


def child(node, name: str):
    return node.child(name) if node is not None and hasattr(node, "child") else None


def value(node, default=None):
    return getattr(node, "value", default) if node is not None else default


def kind(node) -> str:
    return type(node).__name__ if node is not None else "None"


def add_schema(schema: set[tuple[str, str, str]], context: str, node) -> None:
    if node is None or not hasattr(node, "children"):
        return
    for c in node.children():
        schema.add((context, c.name, kind(c)))


def add_entries(schema: set[tuple[str, str, str]], context: str, parent) -> None:
    if parent is None or not hasattr(parent, "children"):
        return
    for entry in parent.children():
        add_schema(schema, context, entry)


def collect_supported_schema() -> set[tuple[str, str, str]]:
    cache: dict[Path, WzImage] = {}
    schema: set[tuple[str, str, str]] = set()
    for path in sorted((CLIENT / "Map/Map").glob("Map[0-9]/*.img")):
        if path.stem.startswith("272"):
            continue
        try:
            img = load_img(path, cache)
        except Exception:
            continue
        if img is None:
            continue
        add_schema(schema, "root", img.root)
        add_schema(schema, "info", img.get("info"))
        add_entries(schema, "back.entry", img.get("back"))
        add_entries(schema, "life.entry", img.get("life"))
        add_entries(schema, "reactor.entry", img.get("reactor"))
        add_entries(schema, "portal.entry", img.get("portal"))
        add_entries(schema, "ladderRope.entry", img.get("ladderRope"))
        add_schema(schema, "miniMap", img.get("miniMap"))
        for layer in [c for c in img.root.children() if c.name.isdigit()]:
            add_schema(schema, "layer.info", child(layer, "info"))
            add_entries(schema, "tile.entry", child(layer, "tile"))
            add_entries(schema, "obj.entry", child(layer, "obj"))
    return schema


def decode_canvas_node(node) -> str | None:
    if not isinstance(node, WzCanvasProperty) or not node.has_pixels():
        return None
    try:
        img = decode_canvas(node, region="GMS")
    except Exception as exc:
        return f"decode_error:{exc!r}"
    if img.width <= 1 and img.height <= 1:
        return f"tiny:{img.width}x{img.height}"
    bbox = img.getbbox()
    if bbox is None:
        return f"blank:{img.width}x{img.height}"
    return None


def check_canvas(owner: str, node, problems: dict[str, set[str]]) -> None:
    problem = decode_canvas_node(node)
    if problem:
        problems[f"{owner}:{problem}"].add(owner)
    if hasattr(node, "children"):
        for child_node in node.children():
            child_owner = f"{owner}/{child_node.name}"
            check_canvas(child_owner, child_node, problems)


def check_file_canvas_decode(owner: str, node, problems: dict[str, set[str]]) -> None:
    if isinstance(node, WzCanvasProperty) and node.has_pixels():
        try:
            decode_canvas(node, region="GMS")
        except Exception as exc:
            problems[f"{owner}:decode_error:{exc!r}"].add(owner)
    if hasattr(node, "children"):
        for child_node in node.children():
            child_owner = f"{owner}/{child_node.name}"
            check_file_canvas_decode(child_owner, child_node, problems)


def audit_maps(map_ids: set[str] | None = None) -> int:
    supported = collect_supported_schema()
    cache: dict[Path, WzImage] = {}
    missing: dict[str, set[str]] = collections.defaultdict(set)
    unsupported: dict[str, set[str]] = collections.defaultdict(set)
    canvas_problems: dict[str, set[str]] = collections.defaultdict(set)
    file_canvas_problems: dict[str, set[str]] = collections.defaultdict(set)
    refs: dict[str, dict[str, set[str]]] = collections.defaultdict(lambda: collections.defaultdict(set))
    parse_errors: list[tuple[str, str]] = []

    map_paths = sorted(MAP_DIR.glob("272*.img"))
    if map_ids is not None:
        map_paths = [p for p in map_paths if p.stem in map_ids]

    def check_schema(mid: str, context: str, node) -> None:
        if node is None or not hasattr(node, "children"):
            return
        for c in node.children():
            item = (context, c.name, kind(c))
            if item not in supported:
                unsupported[f"{context}/{c.name}:{kind(c)}"].add(mid)

    for path in map_paths:
        mid = path.stem
        try:
            img = load_img(path, cache)
        except Exception as exc:
            parse_errors.append((mid, repr(exc)))
            continue
        if img is None:
            continue

        check_schema(mid, "root", img.root)
        info = img.get("info")
        check_schema(mid, "info", info)
        check_schema(mid, "back.entry", img.get("back/0"))
        check_schema(mid, "life.entry", img.get("life/0"))
        check_schema(mid, "reactor.entry", img.get("reactor/0"))
        check_schema(mid, "portal.entry", img.get("portal/0"))
        check_schema(mid, "ladderRope.entry", img.get("ladderRope/0"))
        check_schema(mid, "miniMap", img.get("miniMap"))
        check_canvas(f"map:{mid}/miniMap/canvas", img.get("miniMap/canvas"), canvas_problems)

        for hook, folder in [("onFirstUserEnter", "onFirstUserEnter"), ("onUserEnter", "onUserEnter")]:
            script = value(child(info, hook), "")
            if script:
                refs["map_script"][script].add(mid)
                if not (SERVER / f"scripts/map/{folder}/{script}.js").exists() and not (
                    SERVER / f"scripts-zh-CN/map/{folder}/{script}.js"
                ).exists():
                    missing[f"map_script:{folder}/{script}.js"].add(mid)

        bgm = value(child(info, "bgm"), "")
        if bgm:
            refs["bgm"][bgm].add(mid)
            pack, _, track = bgm.partition("/")
            sound_img = load_img(CLIENT / f"Sound/{pack}.img", cache)
            if sound_img is None:
                missing[f"sound_img:{pack}.img"].add(mid)
            elif track and sound_img.get(track) is None:
                missing[f"sound_node:{bgm}"].add(mid)

        mark = value(child(info, "mapMark"), "")
        if mark:
            refs["mapMark"][mark].add(mid)
            helper = load_img(CLIENT / "Map/MapHelper.img", cache)
            if helper is None:
                missing["map_helper:MapHelper.img"].add(mid)
            elif helper.get(f"mark/{mark}") is None:
                missing[f"mapMark:{mark}"].add(mid)

        for layer in [c for c in img.root.children() if c.name.isdigit()]:
            check_schema(mid, "layer.info", child(layer, "info"))
            tile_root = child(layer, "tile")
            obj_root = child(layer, "obj")
            t_s = value(child(child(layer, "info"), "tS"), "")
            tile_img = load_img(CLIENT / f"Map/Tile/{t_s}.img", cache) if t_s else None
            if t_s:
                refs["tile_img"][t_s].add(mid)
                if tile_img is None:
                    missing[f"tile_img:{t_s}.img"].add(mid)
            if tile_root is not None:
                for tile in tile_root.children():
                    check_schema(mid, "tile.entry", tile)
                    u = value(child(tile, "u"), "")
                    no = value(child(tile, "no"), None)
                    node_path = f"{u}/{no}"
                    refs["tile_node"][f"{t_s}/{node_path}"].add(mid)
                    node = tile_img.get(node_path) if tile_img is not None else None
                    if t_s and node is None:
                        missing[f"tile_node:{t_s}/{node_path}"].add(mid)
                    elif node is not None:
                        check_canvas(f"tile:{t_s}/{node_path}", node, canvas_problems)
            if obj_root is not None:
                for obj in obj_root.children():
                    check_schema(mid, "obj.entry", obj)
                    o_s = value(child(obj, "oS"), "")
                    l0 = value(child(obj, "l0"), "")
                    l1 = value(child(obj, "l1"), "")
                    l2 = value(child(obj, "l2"), "")
                    obj_img = load_img(CLIENT / f"Map/Obj/{o_s}.img", cache) if o_s else None
                    refs["obj_img"][o_s].add(mid)
                    if o_s and obj_img is None:
                        missing[f"obj_img:{o_s}.img"].add(mid)
                    node_path = f"{l0}/{l1}/{l2}"
                    refs["obj_node"][f"{o_s}/{node_path}"].add(mid)
                    node = obj_img.get(node_path) if obj_img is not None else None
                    if o_s and node is None:
                        missing[f"obj_node:{o_s}/{node_path}"].add(mid)
                    elif node is not None:
                        check_canvas(f"obj:{o_s}/{node_path}", node, canvas_problems)

        back_root = img.get("back")
        if back_root is not None:
            for back in back_root.children():
                check_schema(mid, "back.entry", back)
                b_s = value(child(back, "bS"), "")
                no = value(child(back, "no"), None)
                ani = int(value(child(back, "ani"), 0) or 0)
                back_img = load_img(CLIENT / f"Map/Back/{b_s}.img", cache) if b_s else None
                refs["back_img"][b_s].add(mid)
                if b_s and back_img is None:
                    missing[f"back_img:{b_s}.img"].add(mid)
                group = "ani" if ani else "back"
                node = back_img.get(f"{group}/{no}") if back_img is not None else None
                if b_s and node is None:
                    missing[f"back_node:{b_s}/{group}/{no}"].add(mid)
                elif node is not None:
                    check_canvas(f"back:{b_s}/{group}/{no}", node, canvas_problems)

        life_root = img.get("life")
        if life_root is not None:
            for life in life_root.children():
                check_schema(mid, "life.entry", life)
                life_type = value(child(life, "type"), "")
                life_id = value(child(life, "id"), "")
                if life_type == "m":
                    refs["mob"][life_id].add(mid)
                    if not (CLIENT / f"Mob/{life_id}.img").exists():
                        missing[f"mob_img:{life_id}.img"].add(mid)
                    if not (SERVER / f"wz/Mob.wz/{life_id}.img.xml").exists():
                        missing[f"mob_xml:{life_id}.img.xml"].add(mid)
                elif life_type == "n":
                    refs["npc"][life_id].add(mid)
                    if not (CLIENT / f"Npc/{life_id}.img").exists():
                        missing[f"npc_img:{life_id}.img"].add(mid)
                    if not (SERVER / f"wz/Npc.wz/{life_id}.img.xml").exists():
                        missing[f"npc_xml:{life_id}.img.xml"].add(mid)

        portal_root = img.get("portal")
        if portal_root is not None:
            for portal in portal_root.children():
                check_schema(mid, "portal.entry", portal)
                script = value(child(portal, "script"), "")
                if script:
                    refs["portal_script"][script].add(mid)
                    if not (SERVER / f"scripts/portal/{script}.js").exists() and not (
                        SERVER / f"scripts-zh-CN/portal/{script}.js"
                    ).exists():
                        missing[f"portal_script:{script}.js"].add(mid)

    for kind_name, folder in [("obj_img", "Obj"), ("back_img", "Back"), ("tile_img", "Tile")]:
        for img_name in refs[kind_name]:
            if not img_name:
                continue
            common_img = load_img(CLIENT / f"Map/{folder}/{img_name}.img", cache)
            if common_img is not None:
                check_file_canvas_decode(f"{folder.lower()}_file:{img_name}", common_img.root, file_canvas_problems)

    string_mob = load_img(CLIENT / "String/Mob.img", cache)
    for mob_id in refs["mob"]:
        if string_mob is None:
            missing["string_mob_img: Mob.img"].add(mob_id)
        elif string_mob.get(mob_id) is None:
            missing[f"string_mob:{mob_id}"].update(refs["mob"][mob_id])

    string_npc = load_img(CLIENT / "String/Npc.img", cache)
    for npc_id in refs["npc"]:
        if string_npc is None:
            missing["string_npc_img: Npc.img"].add(npc_id)
        elif string_npc.get(npc_id) is None:
            missing[f"string_npc:{npc_id}"].update(refs["npc"][npc_id])
        npc_img = load_img(CLIENT / f"Npc/{npc_id}.img", cache)
        if npc_img is not None:
            check_file_canvas_decode(f"npc_file:{npc_id}", npc_img.root, file_canvas_problems)

    print(f"maps={len(map_paths)} parse_errors={len(parse_errors)}")
    if parse_errors:
        for mid, err in parse_errors:
            print(f"PARSE {mid}: {err}")

    print("\nREFERENCE SETS")
    for key in ["tile_img", "obj_img", "back_img", "mob", "npc", "bgm", "mapMark", "map_script", "portal_script"]:
        print(f"{key}: {len(refs[key])} {sorted(refs[key])}")

    print(f"\nMISSING UNIQUE={len(missing)}")
    for item, maps in sorted(missing.items()):
        sample = ",".join(sorted(maps)[:12])
        more = "" if len(maps) <= 12 else f" +{len(maps) - 12}"
        print(f"{item}: maps={len(maps)} {sample}{more}")

    print(f"\nCANVAS PROBLEMS={len(canvas_problems)}")
    for item in sorted(canvas_problems):
        print(item)

    print(f"\nFILE CANVAS DECODE PROBLEMS={len(file_canvas_problems)}")
    for item in sorted(file_canvas_problems):
        print(item)

    print(f"\nUNSUPPORTED FIELD SIGNATURES={len(unsupported)}")
    for item, maps in sorted(unsupported.items()):
        sample = ",".join(sorted(maps)[:12])
        more = "" if len(maps) <= 12 else f" +{len(maps) - 12}"
        print(f"{item}: maps={len(maps)} {sample}{more}")

    return 1 if parse_errors or missing or canvas_problems or file_canvas_problems else 0


if __name__ == "__main__":
    wanted = set(sys.argv[1:]) or None
    raise SystemExit(audit_maps(wanted))
