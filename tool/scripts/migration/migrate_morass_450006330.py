#!/usr/bin/env python3
"""Migrate Morass map 450006330 with legacy-client-safe resources."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ARC_SCRIPT = Path(__file__).with_name("migrate_arcane_river_expansion.py")
SPEC = importlib.util.spec_from_file_location("arcane_river_expansion", ARC_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {ARC_SCRIPT}")
arc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(arc)


MAP_ID = 450006330
RETURN_MAP_ID = 450006130
VISIBLE_NPCS = {3003540, 3003577, 3003578}
SOURCE_SHA256 = "cf14c0d3bc2dfd603bf46634ab0cb977fd69f9f96bd7b881f05206f56771c688"

BASELINE_SHA256 = {
    "clien/Data/Map/Obj/morass.img": "5af8decae63f54e7ecba5fefce8335c2096f19b43080ee8b14adee449dc19f3e",
    "clien/Data/String/Map.img": "21ab7791d0ebd3da1871a11bee175b60494888eb31d5d5033b02f416ca6ea0ea",
    "clien/Data/String/Npc.img": "1115191114582ff25d33797f68f8dbb288ceb16c0308eac53bc3851026ab11d1",
    "gms-server/wz/String.wz/Map.img.xml": "a5e4f88b30c2b4a79d4f014b4301e8799702c21c5b4c9ee52fdbe0a8655b44f3",
    "gms-server/wz/String.wz/Npc.img.xml": "e4bab4a432ed59351df2a1bddc1a5cfecbf12fd30cb63588bbc749bfed7b7b97",
    "gms-server/wz-zh-CN/String.wz/Map.img.xml": "944ccc89c83f53aa6495c67ac32d7419b32f812b90b484dcf71b60445943eff9",
    "gms-server/wz-zh-CN/String.wz/Npc.img.xml": "d247c50fa775aa0a6e54dbb8149cee293ff2c9a25b3f4d08272506abd132aec5",
}

FINAL_SHA256 = {
    "clien/Data/Map/Obj/morass.img": "ae1186a8b277c1fb76569c66e0204bd0769857e8ad2fb22fe438bcdca4db9fc5",
    "clien/Data/String/Map.img": "099ea183e01fa40f9dfbb24f34eff670239806b68af9c25bdc396e4aceb38f68",
    "clien/Data/String/Npc.img": "f05d0f9e732931391305769944e6e62af498c061ef305a54b9d67f1c5e1a76a7",
    "gms-server/wz/String.wz/Map.img.xml": "fe0ad1cab73881b61abc53458a242e1000e12761ff5cc69178b8c9f886d79c71",
    "gms-server/wz/String.wz/Npc.img.xml": "853f7695bf3e69294ee4a3ecba21d850ac452a6b739d65219ef4bfba40c3e6c9",
    "gms-server/wz-zh-CN/String.wz/Map.img.xml": "24958ca24403cf4730529dcf85b5d9f238821e95f73ddce5749b71a93f76c19c",
    "gms-server/wz-zh-CN/String.wz/Npc.img.xml": "c611cfc9f3beaaffdbab51c1ef60a2a3bd5d4a04a15da1c2b0f8dafa7199796a",
    "clien/Data/Map/Map/Map4/450006330.img": "ed9f0a23c352304788f45307d0c163126fd8ff2a9b83c94f110cd9147e1f943c",
    "gms-server/wz/Map.wz/Map/Map4/450006330.img.xml": "ee2a19cb79d72cef1fed73b1f572852d4d85b210e4392bf5bd8eb20ed13eacf2",
    "clien/Data/Npc/3003540.img": "cb8315acbf58670964c4ec72cea1229698684ce3d5e251dcdb9dad24daf0ab06",
    "clien/Data/Npc/3003577.img": "d797d7b1d989f17b23f45bd36104c982d0a1d1580aa4ebd977a7ad1bac1f8966",
    "clien/Data/Npc/3003578.img": "538f6c67cc958c70adcd0c5dc3a7ba7cbaf37e3ec99f73440e524b5537c35961",
    "gms-server/wz/Npc.wz/3003540.img.xml": "5bac58825202d2ae3dc46a7ff13e6c472c0af7d59f7ab0e876a6ec77a2099302",
    "gms-server/wz/Npc.wz/3003577.img.xml": "b30387ed9d593d8bf20983890f08d53df395a0a881002b9fb5efeb29d233232f",
    "gms-server/wz/Npc.wz/3003578.img.xml": "49cd9dc7b45f200cca5145759e1a10d6a7d85f3edce64aafbf58bc6b5086ac27",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configure(root: Path) -> None:
    arc.ROOT = root
    arc.BACKUP_ROOT = (
        Path("/private/tmp/morass-450006330-backup")
        if root.resolve() == ROOT.resolve()
        else root.parent / f".{root.name}-450006330-backup"
    )
    arc.MAP_IDS = (MAP_ID,)
    arc.MAP_ID_SET = {MAP_ID}
    arc.INSTALLED_ROUTE_MAP_IDS = {450006320, RETURN_MAP_ID}
    arc.TOWN_BY_PREFIX["450006"] = RETURN_MAP_ID
    arc.LEGACY_CONNECT_FIRST_MAPS = {MAP_ID}


def verify_source() -> None:
    source = arc.SOURCE / f"Map/Map/Map4/{MAP_ID}.img"
    if sha256(source) != SOURCE_SHA256:
        raise RuntimeError("TMS 450006330 source hash changed")


def verify_known_states(root: Path, *, require_final: bool) -> None:
    for relative in sorted(BASELINE_SHA256):
        actual = sha256(root / relative)
        allowed = {FINAL_SHA256[relative]} if require_final else {
            value
            for value in (BASELINE_SHA256.get(relative), FINAL_SHA256.get(relative))
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
            ("Back", "morass"): {"back/68", "back/69", "back/70"},
            ("Obj", "morass"): {
                "closedArea/ani/0", "closedArea/foothold_Base/0",
                "closedArea/gate/0", "closedArea/gate/1",
                "closedArea/light/0", "closedArea/light/1",
                "closedArea/skullStone/0", "prison/acc_Back/2",
                "prison/acc_Front/0", "prison/acc_Front/3",
                "prison/acc_Front/6", "prison/acc_Front/7",
                "prison/ani/0", "prison/ani/1", "prison/wall_Pattern/0",
                "prison/wall_Pattern/1", "prison/wall_Pattern/2",
            },
        },
        "mobs": set(), "npcs": VISIBLE_NPCS,
        "bgms": {"Bgm48/BlackDungeon"}, "marks": {"Morass"},
    }


def create_map(root: Path):
    client = root / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
    server = root / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    materializer = arc.CanvasMaterializer()
    if client.exists():
        image = arc.load_image(client, arc.GMS_KEY)
    else:
        source = arc.SOURCE / f"Map/Map/Map4/{MAP_ID}.img"
        image, materializer = arc.clone_image(
            source, lambda map_root: arc.sanitize_map(map_root, MAP_ID)
        )
        arc.write_client_image(client, image)
    if server.exists():
        ET.parse(server)
    else:
        arc.write_server_image(server, image, f"{MAP_ID}.img")
    dependencies = arc.collect_dependencies(image)
    if dependencies != expected_dependencies():
        raise RuntimeError(f"450006330 dependency contract changed: {dependencies}")
    return image, dependencies, materializer


def migrate(root: Path) -> None:
    verify_source()
    configure(root)
    verify_known_states(root, require_final=False)
    _, dependencies, materializer = create_map(root)

    asset_stats = defaultdict(int)
    for (kind, name), branches in sorted(dependencies["assets"].items()):
        canvases, links, resized = arc.merge_asset(kind, name, branches)
        asset_stats["files"] += 1
        asset_stats["canvases"] += canvases
        asset_stats["links"] += links
        asset_stats["resized"] += resized
    arc.merge_map_marks(dependencies["marks"])
    arc.migrate_bgms(dependencies["bgms"])

    npc_stats = defaultdict(int)
    for npc_id in sorted(dependencies["npcs"]):
        canvases, links, resized = arc.migrate_one_npc(npc_id)
        npc_stats["npcs"] += 1
        npc_stats["canvases"] += canvases
        npc_stats["links"] += links
        npc_stats["resized"] += resized

    string_stats = {
        "client_map": arc.upsert_client_strings("Map", {MAP_ID}, "grandis"),
        "client_npc": arc.upsert_client_strings("Npc", VISIBLE_NPCS),
    }
    for tree in ("wz", "wz-zh-CN"):
        string_stats[f"{tree}_map"] = arc.upsert_server_strings(
            tree, "Map", {MAP_ID}, "grandis"
        )
        string_stats[f"{tree}_npc"] = arc.upsert_server_strings(
            tree, "Npc", VISIBLE_NPCS
        )

    if FINAL_SHA256:
        verify_known_states(root, require_final=True)
    print(
        f"450006330 migrated: map_canvases={materializer.canvases} "
        f"assets={dict(asset_stats)} "
        f"npcs={dict(npc_stats)} strings={string_stats}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    migrate(args.root.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
