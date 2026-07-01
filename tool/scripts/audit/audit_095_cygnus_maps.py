#!/usr/bin/env python3
"""Audit 095 Cygnus / Future Gate map resources against the current client.

The check is intentionally conservative:
- client maps must live under Data/Map/Map/Map2, matching the loader path;
- every tile/obj/back/life/script/sound/mapMark reference is resolved;
- map node fields are compared with non-271 maps already present in this
  client, so higher-version-only structures are visible before we patch them.
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import WzImage, WzKey  # noqa: E402


KEY = WzKey.for_region("GMS")
CLIENT = ROOT / "clien/Data"
SERVER = ROOT / "gms-server"
MAP_DIR = CLIENT / "Map/Map/Map2"
WRONG_MAP_DIR = CLIENT / "Map/Map2"


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


def iter_client_map_paths(include_271: bool) -> list[Path]:
    out: list[Path] = []
    for p in (CLIENT / "Map/Map").glob("Map[0-9]/*.img"):
        if include_271 or not p.stem.startswith("271"):
            out.append(p)
    return sorted(out)


def collect_supported_schema() -> set[tuple[str, str, str]]:
    cache: dict[Path, WzImage] = {}
    schema: set[tuple[str, str, str]] = set()

    def add_entries(context: str, parent) -> None:
        if parent is None or not hasattr(parent, "children"):
            return
        for entry in parent.children():
            add_schema(schema, context, entry)

    for path in iter_client_map_paths(include_271=False):
        try:
            img = load_img(path, cache)
        except Exception:
            continue
        if img is None:
            continue
        add_schema(schema, "root", img.root)
        add_schema(schema, "info", img.get("info"))
        add_entries("back.entry", img.get("back"))
        add_entries("life.entry", img.get("life"))
        add_entries("reactor.entry", img.get("reactor"))
        add_entries("portal.entry", img.get("portal"))
        add_entries("ladderRope.entry", img.get("ladderRope"))
        add_schema(schema, "miniMap", img.get("miniMap"))
        for layer in [c for c in img.root.children() if c.name.isdigit()]:
            add_schema(schema, "layer.info", child(layer, "info"))
            add_entries("tile.entry", child(layer, "tile"))
            add_entries("obj.entry", child(layer, "obj"))
    return schema


def audit_271() -> int:
    supported = collect_supported_schema()
    cache: dict[Path, WzImage] = {}
    missing: dict[str, set[str]] = collections.defaultdict(set)
    unsupported: dict[str, set[str]] = collections.defaultdict(set)
    refs: dict[str, dict[str, set[str]]] = collections.defaultdict(lambda: collections.defaultdict(set))
    parse_errors: list[tuple[str, str]] = []

    wrong_count = len(list(WRONG_MAP_DIR.glob("271*.img")))
    map_paths = sorted(MAP_DIR.glob("271*.img"))

    for path in map_paths:
        mid = path.stem
        try:
            img = load_img(path, cache)
        except Exception as exc:
            parse_errors.append((mid, repr(exc)))
            continue
        if img is None:
            continue

        def check_schema(context: str, node) -> None:
            if node is None or not hasattr(node, "children"):
                return
            for c in node.children():
                item = (context, c.name, kind(c))
                if item not in supported:
                    unsupported[f"{context}/{c.name}:{kind(c)}"].add(mid)

        check_schema("root", img.root)
        info = img.get("info")
        check_schema("info", info)
        check_schema("back.entry", img.get("back/0"))
        check_schema("life.entry", img.get("life/0"))
        check_schema("reactor.entry", img.get("reactor/0"))
        check_schema("portal.entry", img.get("portal/0"))
        check_schema("ladderRope.entry", img.get("ladderRope/0"))
        check_schema("miniMap", img.get("miniMap"))

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
            check_schema("layer.info", child(layer, "info"))
            tile_root = child(layer, "tile")
            obj_root = child(layer, "obj")
            t_s = value(child(child(layer, "info"), "tS"), "")
            if t_s:
                tile_img = load_img(CLIENT / f"Map/Tile/{t_s}.img", cache)
                refs["tile_img"][t_s].add(mid)
                if tile_img is None:
                    missing[f"tile_img:{t_s}.img"].add(mid)
                if tile_root is not None:
                    for tile in tile_root.children():
                        check_schema("tile.entry", tile)
                        u = value(child(tile, "u"), "")
                        no = value(child(tile, "no"), None)
                        node_path = f"{u}/{no}"
                        refs["tile_node"][f"{t_s}/{node_path}"].add(mid)
                        if tile_img is None or tile_img.get(node_path) is None:
                            missing[f"tile_node:{t_s}/{node_path}"].add(mid)
            if obj_root is not None:
                for obj in obj_root.children():
                    check_schema("obj.entry", obj)
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
                    if o_s and (obj_img is None or obj_img.get(node_path) is None):
                        missing[f"obj_node:{o_s}/{node_path}"].add(mid)

        back_root = img.get("back")
        if back_root is not None:
            for back in back_root.children():
                check_schema("back.entry", back)
                b_s = value(child(back, "bS"), "")
                no = value(child(back, "no"), None)
                ani = int(value(child(back, "ani"), 0) or 0)
                back_img = load_img(CLIENT / f"Map/Back/{b_s}.img", cache) if b_s else None
                refs["back_img"][b_s].add(mid)
                if b_s and back_img is None:
                    missing[f"back_img:{b_s}.img"].add(mid)
                group = "ani" if ani else "back"
                if b_s and (back_img is None or back_img.get(f"{group}/{no}") is None):
                    missing[f"back_node:{b_s}/{group}/{no}"].add(mid)

        for life in (img.get("life") or []).children() if img.get("life") is not None else []:
            check_schema("life.entry", life)
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
                check_schema("portal.entry", portal)
                script = value(child(portal, "script"), "")
                if script:
                    refs["portal_script"][script].add(mid)
                    if not (SERVER / f"scripts/portal/{script}.js").exists() and not (
                        SERVER / f"scripts-zh-CN/portal/{script}.js"
                    ).exists():
                        missing[f"portal_script:{script}.js"].add(mid)

    print(f"maps={len(map_paths)} wrong_dir_maps={wrong_count} parse_errors={len(parse_errors)}")
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

    print(f"\nUNSUPPORTED FIELD SIGNATURES={len(unsupported)}")
    for item, maps in sorted(unsupported.items()):
        sample = ",".join(sorted(maps)[:12])
        more = "" if len(maps) <= 12 else f" +{len(maps) - 12}"
        print(f"{item}: maps={len(maps)} {sample}{more}")

    return 1 if parse_errors or missing else 0


if __name__ == "__main__":
    raise SystemExit(audit_271())
