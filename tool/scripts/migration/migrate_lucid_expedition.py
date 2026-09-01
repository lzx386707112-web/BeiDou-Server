#!/usr/bin/env python3
"""Migrate the legacy-safe Lucid expedition fields from TMS."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ARC_SCRIPT = Path(__file__).with_name("migrate_arcane_river_expansion.py")
SPEC = importlib.util.spec_from_file_location("arcane_river_expansion", ARC_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {ARC_SCRIPT}")
arc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(arc)


SOURCE_SHA256 = {
    450004000: "4aff61280b8bac016f6c00a55a63caa7fed44d4a9c8084a53125baac866c8c51",
    450004150: "cd029ebd0cd75a46aca50b4d30cc452b1db6e886eed2d56e69c2969187eb6b60",
    450004250: "32c32cae338f4c26b6927836a4ad691c677d39203e78dab31a646921e1e32054",
    "Back/Lach_boss": "d22ef8e006cc13bc2ee79271bc4f4630c0ec0990fe837beb71eb987fe3f8c4ff",
    "String/Map": "02aa055ff48180de0bfa6c18b2e916f0d22d3c98cad150e10acf3e583ab9b3ad",
}
MAP_IDS = (450004000, 450004150, 450004250)
ENTRY_MAP = 450004000
RETURN_MAP = 450004000
ROUTE_MAP = 450003600
ENTRY_NPC_ID = 3003208
ENTRY_NPC_POSITION = {"x": -27, "y": 32, "cy": 37, "fh": 1, "rx0": -87, "rx1": 33}
MAP_BGM = {
    450004000: "Bgm46/ClockTowerofNightmare",
    450004150: "Bgm46/WierldForestIntheGirlsdream",
    450004250: "Bgm46/BrokenDream",
}
MISSING_BGM = {
    "Bgm46/WierldForestIntheGirlsdream",
    "Bgm46/BrokenDream",
}

BASELINE_SHARED_SHA256 = {
    "clien/Data/Sound/Bgm46.img": {
        "95e99135f31eb867af544122d98616847c29116247f21dd5c89527c7431dd71a",
        "dbf11ad12a15a4fc786f758f1e9efba06ee8063379301b2c183a20843e7f2a83",
    },
    "clien/Data/String/Map.img": {
        "fe144586fc24f13471eef261b9435713d2eb6d567d3aeb63b42faf0b735bcf6b",
        "3c6adfcbf5fea34cf62ca3d35ae72380350abd39f4efd4a1c521fa83cf2c6812",
    },
    "gms-server/wz/String.wz/Map.img.xml": {
        "e8ae7243f198761355152765aefcce941f8dfdc7d1d0701095b625fb73b335ad",
        "8b150f398afda710d19fdd23e5d44927f53e2de62ed09180d30390fff5202376",
    },
    "gms-server/wz-zh-CN/String.wz/Map.img.xml": {
        "459f241672bb1c5ef2b83c1caeca9a8257a012fdd4a8cf29f26e3f1575ff37fe",
        "3bafb01f1cf228f9d8d2acbbe770b10df09f5fe832fdced35333a2e7695a71d1",
    },
}

PROTECTED_SHA256 = {
    "clien/Data/Map/Back/Lacheln.img": "9676f0e3ecf39117f44e799b296827d05cbd0d7aa0199d63a90442ec8a284691",
    "clien/Data/Map/Obj/Lacheln.img": "9d6deecfdda4dc9bce211cad3915b52516df8d12306a3cdb169e05fe79307f4c",
    "clien/Data/Map/Tile/allblackTile.img": "8783edc9438e46ef03da2ce558329f4af80f1300b1c831fa7284f79d67cca78c",
    "clien/Data/Map/MapHelper.img": "e78b66855c14d8f771690a3ae6cccdb2879a0b23a6c21cd42660fb7a85be9a7e",
    "clien/Data/Mob/8880140.img": "19eb3e121d1b7db402cc46da14c037f81e9b4f30e41e026b786a48fa1083b700",
    "clien/Data/Mob/8880141.img": "1c2b02408e9d6d725376b9ea31726e052b6080664bb29b9b11f8ebbbbff63721",
    "clien/Data/Mob/8880142.img": "a69fc75492e3dd7e9dbae37528f6868f8a4d3aafb024bac12b7f3afe3c7d2312",
    "clien/Data/String/Mob.img": {
        "f552f842a7ae23734f2bbdcb9ebe235870b28314932ca967c8c41c20d2ac6612",
        "5281366e4e50094c940c4fb77086e3cba12c250cdb2917b0a2606f3fddda2112",
    },
}

LEGACY_OBJ_ASSET = "LucidBossLegacy"
LEGACY_OBJ_PATH = "clien/Data/Map/Obj/LucidBossLegacy.img"
LEGACY_OBJ_SOURCE = Path(__file__).with_name("assets") / "lucid"
LEGACY_OBJ_SOURCE_SHA256 = {
    "obj9.png": "b65f04deb23c610bb4fec0772730f0d7a06e80a194f8c1b3c845a8304f7eb47d",
    "obj10.png": "13301b3ef0c2223008a83f5ddc5098bdd9346e807d14c95e7342435e1e5ac552",
}
LEGACY_OBJ_SPECS = {
    "9": {"source": "obj9.png", "origin": (1004, 375), "size": (1997, 950)},
    "10": {"source": "obj10.png", "origin": (178, 253), "size": (365, 291)},
}
LEGACY_MAP_OBJECTS = (
    ("0", "9", 967, -275),
    ("1", "10", 1023, -107),
)

GENERATED_BASELINE_SHA256 = {
    "clien/Data/Map/Map/Map4/450004000.img": {
        "04e4121fd64e792477eb08e0a64f49303b36848c7206004a45df782fd3a7e248",
    },
    "clien/Data/Map/Map/Map4/450004150.img": {
        "d224db16231fde11965c5d92198740bf73f87997b542d8e71c2a8a74ea911932",
        "163cbdea10e3c01c4715eafccc218d09b6a0c0e4a3ee7761d33e64722a8fe97b",
    },
    "clien/Data/Map/Map/Map4/450004250.img": {
        "d7b82ca94b8bc139f52ccf75ca994b070f5ade1559a6a245fce35a820a8682cd",
    },
    "gms-server/wz/Map.wz/Map/Map4/450004000.img.xml": {
        "e3e1fa8223016456cb81cfa68061de12d6a72e0085ad7da9645e3fdc7428ef68",
    },
    "gms-server/wz/Map.wz/Map/Map4/450004150.img.xml": {
        "e135569d52f5f20c438c95f707767d4c06b81f96ee312e4999e541a0a68a0c70",
    },
    "gms-server/wz/Map.wz/Map/Map4/450004250.img.xml": {
        "003c3f0cc82384e8ba1d32a685a800c1296ef0389437448833cd4a8594a6584b",
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configure(root: Path) -> None:
    arc.ROOT = root
    arc.BACKUP_ROOT = Path("/private/tmp/lucid-expedition-migration-backup")
    arc.MAP_IDS = MAP_IDS
    arc.MAP_ID_SET = set(MAP_IDS)
    arc.INSTALLED_ROUTE_MAP_IDS = {ROUTE_MAP}
    arc.TOWN_BY_PREFIX["450004"] = ENTRY_MAP
    arc.LEGACY_CONNECT_FIRST_MAPS = set(MAP_IDS)


def verify_sources() -> None:
    for map_id in MAP_IDS:
        source = arc.SOURCE / f"Map/Map/Map4/{map_id}.img"
        if sha256(source) != SOURCE_SHA256[map_id]:
            raise RuntimeError(f"TMS source changed: {source}")
    for source_name, relative in (
        ("Back/Lach_boss", "Map/Back/Lach_boss.img"),
        ("String/Map", "String/Map.img"),
    ):
        source = arc.SOURCE / relative
        if sha256(source) != SOURCE_SHA256[source_name]:
            raise RuntimeError(f"TMS source changed: {source}")
    for name, expected in LEGACY_OBJ_SOURCE_SHA256.items():
        source = LEGACY_OBJ_SOURCE / name
        if sha256(source) != expected:
            raise RuntimeError(f"Lucid legacy Obj source changed: {source}")


def verify_known_shared_state(root: Path) -> None:
    for relative, allowed in BASELINE_SHARED_SHA256.items():
        actual = sha256(root / relative)
        if actual not in allowed:
            raise RuntimeError(f"unknown shared-file state: {relative} {actual}")


def verify_protected(root: Path) -> None:
    for relative, expected in PROTECTED_SHA256.items():
        actual = sha256(root / relative)
        allowed = {expected} if isinstance(expected, str) else expected
        if actual not in allowed:
            raise RuntimeError(f"protected artifact changed: {relative} {actual}")


def portal_by_name(root, name: str):
    portal = root.child("portal")
    if not isinstance(portal, arc.WzSubProperty):
        raise RuntimeError("map has no portal root")
    matches = [entry for entry in portal.children() if arc.child_value(entry, "pn") == name]
    if len(matches) != 1:
        raise RuntimeError(f"portal is not unique: {name}")
    return matches[0]


def set_script_portal(entry, script: str) -> None:
    arc.set_int(entry, "pt", 7)
    arc.set_int(entry, "tm", 999999999)
    arc.set_string(entry, "tn", "")
    arc.set_string(entry, "script", script)


def entry_npc_record() -> arc.WzSubProperty:
    entry = arc.WzSubProperty("0")
    entry.add(arc.WzStringProperty("id", str(ENTRY_NPC_ID), entry))
    for field in ("x", "y", "cy"):
        entry.add(arc.WzIntProperty(field, ENTRY_NPC_POSITION[field], entry))
    entry.add(arc.WzIntProperty("mobTime", 0, entry))
    for field in ("rx0", "rx1"):
        entry.add(arc.WzIntProperty(field, ENTRY_NPC_POSITION[field], entry))
    entry.add(arc.WzIntProperty("f", 0, entry))
    entry.add(arc.WzIntProperty("hide", 0, entry))
    entry.add(arc.WzStringProperty("type", "n", entry))
    entry.add(arc.WzIntProperty("fh", ENTRY_NPC_POSITION["fh"], entry))
    return entry


def sanitize_lucid_map(root, map_id: int) -> None:
    if map_id == ENTRY_MAP:
        out = portal_by_name(root, "out00")
        arc.remove_child(out, "script")
        arc.set_int(out, "pt", 2)
        arc.set_int(out, "tm", ROUTE_MAP)
        arc.set_string(out, "tn", "sp")
    elif map_id == 450004250:
        arc.remove_child(portal_by_name(root, "pt00"), "script")

    arc.sanitize_map(root, map_id)

    info = root.child("info")
    if not isinstance(info, arc.WzSubProperty):
        raise RuntimeError(f"{map_id}: missing info")
    arc.set_int(info, "returnMap", RETURN_MAP)
    arc.set_int(info, "forcedReturn", RETURN_MAP)
    arc.set_int(info, "fieldLimit", 0)

    for name in ("life", "reactor"):
        node = root.child(name)
        if isinstance(node, arc.WzSubProperty):
            node._children.clear()

    if map_id == ENTRY_MAP:
        life = root.child("life")
        if not isinstance(life, arc.WzSubProperty):
            raise RuntimeError(f"{map_id}: missing life root")
        life.add(entry_npc_record())

    for layer in [child for child in root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if not isinstance(objects, arc.WzSubProperty):
            continue
        for entry in list(objects.children()):
            if arc.child_value(entry, "oS") == "spinOff1":
                arc.remove_child(objects, entry.name)

    if map_id == ENTRY_MAP:
        recruit = portal_by_name(root, "pt02")
        arc.set_int(recruit, "pt", 0)
        arc.set_int(recruit, "tm", 999999999)
        arc.set_string(recruit, "tn", "")
        arc.set_string(recruit, "script", "")
    elif map_id == 450004150:
        set_script_portal(portal_by_name(root, "pt00"), "lucid_exit")
    elif map_id == 450004250:
        set_script_portal(portal_by_name(root, "pt00"), "lucid_exit")


def legacy_map_object_records() -> list[arc.WzSubProperty]:
    records: list[arc.WzSubProperty] = []
    for name, legacy_branch, x, y in LEGACY_MAP_OBJECTS:
        entry = arc.WzSubProperty(name)
        for field, value in (
            ("oS", LEGACY_OBJ_ASSET), ("l0", "Boss"),
            ("l1", "obj"), ("l2", legacy_branch),
        ):
            entry.add(arc.WzStringProperty(field, value, entry))
        for field, value in (
            ("x", x), ("y", y), ("z", 9), ("f", 0), ("zM", 5), ("r", 0),
        ):
            entry.add(arc.WzIntProperty(field, value, entry))
        records.append(entry)
    return records


def expected_dependencies() -> dict[int, dict[str, object]]:
    return {
        450004000: {
            "assets": {
                ("Back", "Lacheln"): {
                    "ani/0", "ani/1", "ani/10", "ani/2", "ani/3", "ani/7",
                    "ani/8", "ani/9", "back/3", "back/4", "back/41", "back/42",
                },
                ("Obj", "Lacheln"): {
                    "ClockT/obj/20", "ClockT/obj/21", "ClockT/obj/22",
                    "ClockT/obj/23", "ClockT/obj/24", "ClockT/obj/25",
                },
            },
            "mobs": set(), "npcs": {ENTRY_NPC_ID},
            "bgms": {MAP_BGM[450004000]}, "marks": {"Lacheln"},
        },
        450004150: {
            "assets": {
                ("Back", "Lach_boss"): {
                    "ani/0", "ani/1", "ani/2", "ani/3", "ani/4", "ani/5", "ani/6",
                    "back/69", "back/70", "back/73", "back/74", "back/75", "back/76",
                    "back/77", "back/78", "back/79", "back/81",
                },
                ("Obj", "Lacheln"): {
                    "Boss/foothold/6", "Boss/foothold/7",
                },
                ("Obj", LEGACY_OBJ_ASSET): {
                    "Boss/obj/9", "Boss/obj/10",
                },
            },
            "mobs": set(), "npcs": set(),
            "bgms": {MAP_BGM[450004150]}, "marks": {"Lacheln"},
        },
        450004250: {
            "assets": {
                ("Back", "Lach_boss"): {
                    "back/3", "back/4", "back/5", "back/9",
                    *(f"back/{index}" for index in range(12, 69)),
                    "back/82", "back/83", "back/84", "back/85",
                },
                ("Obj", "Lacheln"): {
                    "Boss/foothold/0", "Boss/foothold/1", "Boss/foothold/2",
                    "Boss/foothold/3", "Boss/foothold/4", "Boss/foothold/5",
                },
                ("Tile", "allblackTile"): {
                    "edD/0", "edU/0", "enH0/0", "enH1/0",
                },
            },
            "mobs": set(), "npcs": set(),
            "bgms": {MAP_BGM[450004250]}, "marks": {"Lacheln"},
        },
    }


def encoded_image(image, name: str) -> bytes:
    data = arc.encode_image_body(image, arc.gms_reader())
    return arc.verified_image_bytes(data, name)


def write_exact_bytes(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() != data:
            raise RuntimeError(f"existing generated artifact differs: {path}")
        return
    arc.atomic_write_bytes(path, data)


def write_exact_text(path: Path, text: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise RuntimeError(f"existing generated artifact differs: {path}")
        return
    arc.atomic_write_text(path, text)


def write_generated_bytes(root: Path, path: Path, data: bytes) -> None:
    if path.exists() and path.read_bytes() != data:
        relative = path.relative_to(root).as_posix()
        actual = sha256(path)
        if actual not in GENERATED_BASELINE_SHA256.get(relative, set()):
            raise RuntimeError(f"unknown generated-artifact state: {relative} {actual}")
    arc.atomic_write_bytes(path, data)


def write_generated_text(root: Path, path: Path, text: str) -> None:
    encoded = text.encode("utf-8")
    if path.exists() and path.read_bytes() != encoded:
        relative = path.relative_to(root).as_posix()
        actual = sha256(path)
        if actual not in GENERATED_BASELINE_SHA256.get(relative, set()):
            raise RuntimeError(f"unknown generated-artifact state: {relative} {actual}")
    arc.atomic_write_text(path, text)


def build_maps(root: Path) -> tuple[set[str], dict[str, set[str]], dict[str, int]]:
    bgms: set[str] = set()
    asset_branches: dict[str, set[str]] = {}
    totals = {"canvases": 0, "links": 0, "resized": 0}
    contracts = expected_dependencies()
    for map_id in MAP_IDS:
        source = arc.SOURCE / f"Map/Map/Map4/{map_id}.img"
        image, materializer = arc.clone_image(
            source, lambda map_root, value=map_id: sanitize_lucid_map(map_root, value)
        )
        data = encoded_image(image, f"{map_id}.img")
        if map_id == 450004150:
            objects = image.root.get("1/obj")
            if not isinstance(objects, arc.WzSubProperty) or objects.has_children():
                raise RuntimeError(
                    "450004150: expected empty layer 1 Obj before legacy insertion"
                )
            baseline = data
            for entry in legacy_map_object_records():
                data = arc.append_property_record(data, ("1", "obj"), entry)
            arc.verify_raw_record_insert_scope(
                baseline, data,
                {("1", "obj", name) for name, *_ in LEGACY_MAP_OBJECTS},
            )
            image = arc.WzImage.from_bytes(data, key=arc.GMS_KEY, name=f"{map_id}.img")
            image.parse()
            if image.truncated or image.parse_warnings:
                raise RuntimeError(
                    f"{map_id}: incremental Obj result malformed: "
                    f"truncated={image.truncated} warnings={image.parse_warnings}"
                )
        dependencies = arc.collect_dependencies(image)
        if dependencies != contracts[map_id]:
            raise RuntimeError(f"{map_id}: dependency contract changed: {dependencies}")
        bgms.update(dependencies["bgms"])
        branches = dependencies["assets"].get(("Back", "Lach_boss"), set())
        asset_branches.setdefault("Back/Lach_boss", set()).update(branches)

        client = root / f"clien/Data/Map/Map/Map4/{map_id}.img"
        if map_id == ENTRY_MAP and client.exists():
            arc.verify_raw_record_scope(
                client.read_bytes(), data, {("life",), ("portal",)},
                allow_additions=True,
            )
        write_generated_bytes(root, client, data)
        server = root / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
        write_generated_text(root, server, arc.image_to_xml(image, f"{map_id}.img"))
        ET.parse(server)

        totals["canvases"] += materializer.canvases
        totals["links"] += materializer.links
        totals["resized"] += materializer.resized
    return bgms, asset_branches, totals


def build_lach_boss_asset(root: Path, branches: set[str]) -> dict[str, int]:
    source_path = arc.SOURCE / "Map/Back/Lach_boss.img"
    source = arc.load_image(source_path, arc.BMS_KEY)
    materializer = arc.CanvasMaterializer()
    target = arc.load_image(source_path, arc.BMS_KEY)
    target._root = arc.WzSubProperty(source.root.name)
    target._parsed = True
    for branch in sorted(branches):
        source_node = source.root.get(branch)
        if source_node is None:
            raise RuntimeError(f"missing TMS Back/Lach_boss.img/{branch}")
        parent_path, _, leaf = branch.rpartition("/")
        parent = arc.ensure_path(target.root, parent_path)
        parent.add(arc.clone_property(
            source_node, parent, source, source_path, materializer, leaf
        ))
    path = root / "clien/Data/Map/Back/Lach_boss.img"
    write_exact_bytes(path, encoded_image(target, path.name))
    return {
        "branches": len(branches),
        "canvases": materializer.canvases,
        "links": materializer.links,
        "resized": materializer.resized,
    }


def build_legacy_obj_asset(root: Path) -> dict[str, object]:
    carrier_path = arc.SOURCE / "Map/Obj/Lacheln.img"
    target = arc.load_image(carrier_path, arc.BMS_KEY)
    target._root = arc.WzSubProperty(target.root.name)
    target._parsed = True
    visible_bboxes: dict[str, tuple[int, int, int, int]] = {}
    for branch, spec in LEGACY_OBJ_SPECS.items():
        with arc.Image.open(LEGACY_OBJ_SOURCE / spec["source"]) as opened:
            bitmap = opened.convert("RGBA")
        if bitmap.size != spec["size"]:
            raise RuntimeError(f"legacy Obj {branch}: unexpected source size {bitmap.size}")
        bbox = bitmap.getbbox()
        if bbox is None:
            raise RuntimeError(f"legacy Obj {branch}: source frame is empty")
        visible_bboxes[branch] = bbox

        parent = arc.ensure_path(target.root, f"Boss/obj/{branch}")
        canvas = arc.WzCanvasProperty("0", parent)
        canvas.width, canvas.height = bitmap.size
        canvas.format, canvas.format2 = 1, 0
        canvas._png_data = arc.encode_canvas_payload(
            bitmap, 1, bitmap.width, bitmap.height,
            key=arc.GMS_KEY, listwz=False, zlib_level=6,
        )
        canvas._png_length = len(canvas._png_data)
        canvas.add(arc.WzVectorProperty("origin", *spec["origin"], canvas))
        canvas.add(arc.WzIntProperty("z", 0, canvas))
        parent.add(canvas)

    path = root / LEGACY_OBJ_PATH
    write_exact_bytes(path, encoded_image(target, path.name))
    return {"branches": len(LEGACY_OBJ_SPECS), "visible_bboxes": visible_bboxes}


def migrate_shared_files(root: Path, bgms: set[str]) -> dict[str, object]:
    before_bgm = (root / "clien/Data/Sound/Bgm46.img").read_bytes()
    before_strings = (root / "clien/Data/String/Map.img").read_bytes()

    bgm_stats = arc.migrate_bgms(bgms)
    string_stats = {
        "client": arc.upsert_client_strings("Map", set(MAP_IDS), "grandis")
    }
    for tree in ("wz", "wz-zh-CN"):
        string_stats[tree] = arc.upsert_server_strings(
            tree, "Map", set(MAP_IDS), "grandis"
        )

    after_bgm = (root / "clien/Data/Sound/Bgm46.img").read_bytes()
    if before_bgm != after_bgm:
        arc.verify_raw_record_insert_scope(
            before_bgm, after_bgm,
            {(name.split("/", 1)[1],) for name in MISSING_BGM},
        )
    after_strings = (root / "clien/Data/String/Map.img").read_bytes()
    if before_strings != after_strings:
        arc.verify_raw_record_insert_scope(
            before_strings, after_strings,
            {("grandis", str(map_id)) for map_id in MAP_IDS},
        )
    return {"bgm": bgm_stats, "strings": string_stats}


def verify(root: Path) -> None:
    contracts = expected_dependencies()
    for map_id in MAP_IDS:
        client = root / f"clien/Data/Map/Map/Map4/{map_id}.img"
        image = arc.load_image(client, arc.GMS_KEY)
        if image.truncated or image.parse_warnings:
            raise RuntimeError(
                f"{map_id}: truncated={image.truncated} warnings={image.parse_warnings}"
            )
        if arc.collect_dependencies(image) != contracts[map_id]:
            raise RuntimeError(f"{map_id}: installed dependencies changed")
        for node, path in arc.walk(image.root):
            if not isinstance(node, arc.WzCanvasProperty):
                continue
            if node.child("_outlink") is not None or node.child("_inlink") is not None:
                raise RuntimeError(f"{map_id}: unresolved Canvas link {path}")
            arc.decode_canvas(node, region="GMS")
        ET.parse(root / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml")

    legacy_obj = arc.load_image(root / LEGACY_OBJ_PATH, arc.GMS_KEY)
    if legacy_obj.truncated or legacy_obj.parse_warnings:
        raise RuntimeError("LucidBossLegacy.img did not parse cleanly")
    for branch, spec in LEGACY_OBJ_SPECS.items():
        canvas = legacy_obj.root.get(f"Boss/obj/{branch}/0")
        if not isinstance(canvas, arc.WzCanvasProperty):
            raise RuntimeError(f"missing legacy Lucid Obj branch {branch}")
        if (int(canvas.width), int(canvas.height)) != spec["size"]:
            raise RuntimeError(f"legacy Lucid Obj {branch}: dimensions changed")
        if (int(canvas.format), int(canvas.format2)) != (1, 0):
            raise RuntimeError(f"legacy Lucid Obj {branch}: non-ARGB4444 Canvas")
        origin = canvas.child("origin")
        if not isinstance(origin, arc.WzVectorProperty) or (
            int(origin.x), int(origin.y)
        ) != spec["origin"]:
            raise RuntimeError(f"legacy Lucid Obj {branch}: origin changed")
        if arc.decode_canvas(canvas, region="GMS").convert("RGBA").getbbox() is None:
            raise RuntimeError(f"legacy Lucid Obj {branch}: decoded frame is empty")

    asset = arc.load_image(root / "clien/Data/Map/Back/Lach_boss.img", arc.GMS_KEY)
    if asset.truncated or asset.parse_warnings:
        raise RuntimeError("Back/Lach_boss.img did not parse cleanly")
    expected_branches = set().union(*(
        contract["assets"].get(("Back", "Lach_boss"), set())
        for contract in contracts.values()
    ))
    for branch in expected_branches:
        if asset.root.get(branch) is None:
            raise RuntimeError(f"missing Back/Lach_boss.img/{branch}")
    for node, path in arc.walk(asset.root):
        if not isinstance(node, arc.WzCanvasProperty):
            continue
        if int(node.format) != 1 or int(node.format2) != 0:
            raise RuntimeError(f"non-ARGB4444 Back/Lach_boss.img/{path}")
        arc.decode_canvas(node, region="GMS")

    sound = arc.load_image(root / "clien/Data/Sound/Bgm46.img", arc.GMS_KEY)
    for reference in MAP_BGM.values():
        name = reference.split("/", 1)[1]
        if not isinstance(sound.root.child(name), arc.WzSoundProperty):
            raise RuntimeError(f"missing {reference}")

    strings = arc.load_image(root / "clien/Data/String/Map.img", arc.GMS_KEY)
    for map_id in MAP_IDS:
        if strings.root.get(f"grandis/{map_id}/mapName") is None:
            raise RuntimeError(f"missing client map string {map_id}")
    for tree in ("wz", "wz-zh-CN"):
        xml_root = ET.parse(root / f"gms-server/{tree}/String.wz/Map.img.xml").getroot()
        grandis = next(child for child in xml_root if child.get("name") == "grandis")
        names = {child.get("name") for child in grandis}
        if not {str(value) for value in MAP_IDS}.issubset(names):
            raise RuntimeError(f"missing {tree} map strings")


def migrate(root: Path) -> None:
    configure(root)
    verify_sources()
    verify_known_shared_state(root)
    verify_protected(root)
    bgms, asset_branches, map_stats = build_maps(root)
    if bgms != set(MAP_BGM.values()):
        raise RuntimeError(f"unexpected Lucid BGM set: {bgms}")
    asset_stats = build_lach_boss_asset(root, asset_branches["Back/Lach_boss"])
    legacy_obj_stats = build_legacy_obj_asset(root)
    shared_stats = migrate_shared_files(root, bgms)
    verify(root)
    verify_protected(root)
    print(
        f"Lucid expedition migrated: maps={len(MAP_IDS)} map_stats={map_stats} "
        f"asset_stats={asset_stats} legacy_obj_stats={legacy_obj_stats} shared={shared_stats}"
    )
    for relative in BASELINE_SHARED_SHA256:
        print(f"shared_sha256 {relative} {sha256(root / relative)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    migrate(args.root.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
