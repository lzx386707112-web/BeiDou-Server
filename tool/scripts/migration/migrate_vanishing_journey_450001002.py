#!/usr/bin/env python3
"""Migrate Vanishing Journey map 450001002 for the legacy client."""

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


MAP_ID = 450001002
TOWN_ID = 450001000
SOURCE_SHA256 = "f70e23e11a2180e2ac3ecea6bfd94a607620c596adcbbc44af3e27b78c7ecac6"
PROTECTED_TOWN_SHA256 = "ac6127f16ca8c56bac8db7448ced677c24ca557cbc22bb4ea861104d679d373e"

BASELINE_SHA256 = {
    "clien/Data/Map/Obj/ReverseCity.img": "d8cb201ccac66265f5e0496ad3a3300ef31a9392bd8d09a35f0f1abab6814695",
    "clien/Data/String/Map.img": "099ea183e01fa40f9dfbb24f34eff670239806b68af9c25bdc396e4aceb38f68",
    "gms-server/wz/String.wz/Map.img.xml": "fe0ad1cab73881b61abc53458a242e1000e12761ff5cc69178b8c9f886d79c71",
    "gms-server/wz-zh-CN/String.wz/Map.img.xml": "24958ca24403cf4730529dcf85b5d9f238821e95f73ddce5749b71a93f76c19c",
}

FINAL_SHA256 = {
    "clien/Data/Map/Obj/ReverseCity.img": "9c9ecc1e32d1e75a7f40b3d33be5779d4a53ce2b559120c0b29b49036e085b2f",
    "clien/Data/String/Map.img": "fe144586fc24f13471eef261b9435713d2eb6d567d3aeb63b42faf0b735bcf6b",
    "gms-server/wz/String.wz/Map.img.xml": "e8ae7243f198761355152765aefcce941f8dfdc7d1d0701095b625fb73b335ad",
    "gms-server/wz-zh-CN/String.wz/Map.img.xml": "459f241672bb1c5ef2b83c1caeca9a8257a012fdd4a8cf29f26e3f1575ff37fe",
    "clien/Data/Map/Map/Map4/450001002.img": "a510abc1e5bc21a4c3c86e9c43a45107a3205b6446531bd61e4d51bd7e19ff12",
    "gms-server/wz/Map.wz/Map/Map4/450001002.img.xml": "b10be9f8ea8e7711a92d469c74d22fdf4b35945115a680adb9cf26c9f3438dc6",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configure(root: Path) -> None:
    arc.ROOT = root
    arc.BACKUP_ROOT = (
        Path("/private/tmp/vanishing-journey-450001002-backup")
        if root.resolve() == ROOT.resolve()
        else root.parent / f".{root.name}-450001002-backup"
    )
    arc.MAP_IDS = (MAP_ID,)
    arc.MAP_ID_SET = {MAP_ID}
    arc.INSTALLED_ROUTE_MAP_IDS = {TOWN_ID}
    arc.TOWN_BY_PREFIX["450001"] = TOWN_ID
    arc.LEGACY_CONNECT_FIRST_MAPS = {MAP_ID}


def verify_source() -> None:
    source = arc.SOURCE / f"Map/Map/Map4/{MAP_ID}.img"
    if sha256(source) != SOURCE_SHA256:
        raise RuntimeError("TMS 450001002 source hash changed")


def verify_known_states(root: Path, *, require_final: bool) -> None:
    town = root / f"clien/Data/Map/Map/Map4/{TOWN_ID}.img"
    if sha256(town) != PROTECTED_TOWN_SHA256:
        raise RuntimeError(f"protected 450001000 changed: {sha256(town)}")
    for relative in sorted(BASELINE_SHA256):
        actual = sha256(root / relative)
        allowed = {FINAL_SHA256[relative]} if require_final else {
            value
            for value in (BASELINE_SHA256[relative], FINAL_SHA256.get(relative))
            if value is not None
        }
        if actual not in allowed:
            raise RuntimeError(f"unknown migration state: {relative} {actual}")
    for relative, expected in FINAL_SHA256.items():
        if relative in BASELINE_SHA256:
            continue
        path = root / relative
        if require_final:
            if not path.is_file() or sha256(path) != expected:
                raise RuntimeError(f"missing or changed final artifact: {relative}")
        elif path.exists() and sha256(path) != expected:
            raise RuntimeError(f"unknown existing artifact: {relative} {sha256(path)}")


def expected_dependencies() -> dict[str, object]:
    return {
        "assets": {
            ("Back", "extinction"): {
                "ani/14", "ani/15", "ani/16", "ani/3", "ani/4", "ani/5",
                "ani/6", "ani/8", "ani/9", "back/0", "back/1", "back/10",
                "back/11", "back/12", "back/13", "back/14", "back/15",
                "back/16", "back/18", "back/19", "back/2", "back/20",
                "back/21", "back/23", "back/25", "back/26", "back/27",
                "back/28", "back/3", "back/4", "back/5",
            },
            ("Obj", "extinctionLegacy"): {
                "extinction/ani/0", "extinction/ani/1", "extinction/ani/2",
                "extinction/ani/3", "extinction/ani/4", "extinction/ani/5",
                "extinction/ani/7", "extinction/ani/8",
                "extinction/foothold0/0", "extinction/foothold0/1",
                "extinction/foothold0/3", "extinction/obj/14",
                "extinction/obj/19", "extinction/obj/20", "extinction/obj/21",
            },
            ("Obj", "ReverseCity"): {"subway/obj/0"},
        },
        "mobs": set(), "npcs": set(),
        "bgms": {"Bgm46/Lake Of Oblivion"},
        "marks": {"Road of Vanishing"},
    }


def create_map(root: Path):
    client = root / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
    server = root / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    materializer = arc.CanvasMaterializer()
    if client.exists():
        image = arc.load_image(client, arc.GMS_KEY)
    else:
        image, materializer = arc.clone_image(
            arc.SOURCE / f"Map/Map/Map4/{MAP_ID}.img",
            lambda map_root: arc.sanitize_map(map_root, MAP_ID),
        )
        arc.write_client_image(client, image)
    if server.exists():
        ET.parse(server)
    else:
        arc.write_server_image(server, image, f"{MAP_ID}.img")
    dependencies = arc.collect_dependencies(image)
    if dependencies != expected_dependencies():
        raise RuntimeError(f"450001002 dependency contract changed: {dependencies}")
    return dependencies, materializer


def migrate(root: Path) -> None:
    verify_source()
    configure(root)
    verify_known_states(root, require_final=False)
    dependencies, materializer = create_map(root)
    asset_canvases = asset_links = asset_resized = 0
    for (kind, name), branches in sorted(dependencies["assets"].items()):
        canvases, links, resized = arc.merge_asset(kind, name, branches)
        asset_canvases += canvases
        asset_links += links
        asset_resized += resized
    arc.merge_map_marks(dependencies["marks"])
    arc.migrate_bgms(dependencies["bgms"])
    strings = {
        "client": arc.upsert_client_strings("Map", {MAP_ID}, "grandis")
    }
    for tree in ("wz", "wz-zh-CN"):
        strings[tree] = arc.upsert_server_strings(tree, "Map", {MAP_ID}, "grandis")
    if FINAL_SHA256:
        verify_known_states(root, require_final=True)
    print(
        f"450001002 migrated: map_canvases={materializer.canvases} "
        f"asset_canvases={asset_canvases} links={asset_links} "
        f"resized={asset_resized} strings={strings}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    migrate(args.root.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
