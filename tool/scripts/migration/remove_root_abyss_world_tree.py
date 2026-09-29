#!/usr/bin/env python3
"""Incrementally remove retired regions and their runtime resources."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from remove_weapon_resources import (  # noqa: E402
    apply_img,
    apply_text,
    batch_remove_img,
    batch_remove_xml,
)


ROOT_ABYSS_MAPS = (
    105200000,
    105200500, 105200510, 105200520,
    105200600, 105200610,
    105200700, 105200710,
    105200800, 105200810,
    105200900,
    105201000, 105201100, 105201200, 105201300,
)
WORLD_TREE_MAPS = (
    105300000,
    *range(105300100, 105300104),
    *range(105300200, 105300212),
    *range(105300300, 105300306),
    350160240, 350160280,
)
MAP_IDS = ROOT_ABYSS_MAPS + WORLD_TREE_MAPS
MAP_STRING_IDS = MAP_IDS + (
    105200100, 105200110, 105200120,
    105200200, 105200210,
    105200300, 105200310,
    105200400, 105200410,
    *range(105200901, 105200910),
)

MONSTER_PARK_MAPS = (
    *range(954111000, 954111501, 100),
    *range(954112000, 954112501, 100),
    *range(954113000, 954113501, 100),
    951000300, 951000400,
)
MONSTER_PARK_MOB_IDS = tuple(range(9800339, 9800363))
MONSTER_PARK_NPC_IDS = (9071006,)

MOB_IDS = (
    *range(3503000, 3503010),
    *range(7120110, 7120116),
    9834610,
    8880102,
    *range(8880110, 8880115),
    *range(8900000, 8900004),
    *range(8910000, 8910002),
    8920000, 8920001, 8920002, 8920004, 8920005, 8920006,
    *range(8930000, 8930002),
)
MOB_STRING_IDS = MOB_IDS + (
    *range(8900100, 8900104),
    8910100,
    8920003,
    *range(8920100, 8920107),
    8930100,
)

NPC_IDS = (
    *range(1064001, 1064010),
    *range(1064012, 1064018),
    1064029, 1064032,
    1540893, 1540894, 1540895, 1540936, 1540941,
    2010011,
    3007007, 3007008,
    9091004, 9091021, 9091023,
)
NPC_STRING_IDS = NPC_IDS + (1064031,)

REACTOR_IDS = (
    1052000, 1052001, 1052002, 1052003, 1052006, 1052008,
    *range(1058000, 1058006),
    *range(1058011, 1058030),
)

QUEST_SERVER_IDS = (30000, *range(30002, 30023), 30027, -8054)
QUEST_CLIENT_IDS = (30000, *range(30002, 30023), 30027, 57482)

DIRECT_MOB_GAUGE_IDS = (
    8880110, 8880111,
    8900000, 8900001, 8900002,
    8900100, 8900101, 8900102,
    8910000, 8910100,
    8920000, 8920001, 8920002, 8920003,
    8920100, 8920101, 8920102, 8920103,
    8930000, 8930100,
)
ALIAS_MOB_GAUGE_IDS = (9410270, 9410271, 9410272, 9410273, 9410277, 9410281, 9410285, 9410289)

SERVER_MOB_SKILLS = (
    ("170", "level", "10"), ("170", "level", "11"),
    ("170", "level", "13"), ("170", "level", "14"),
    ("186", "level", "1"), ("188", "level", "1"),
    ("191", "level", "1"), ("191", "level", "2"),
    ("201", "level", "40"), ("201", "level", "47"),
    ("201", "level", "48"), ("201", "level", "49"),
    ("201", "level", "51"), ("201", "level", "52"),
    ("201", "level", "53"), ("201", "level", "59"),
    ("201", "level", "60"), ("201", "level", "292"),
    ("203", "level", "1"),
)
CLIENT_MOB_SKILLS = (
    ("186",),
    *(("200", "level", str(level)) for level in range(237, 251)),
)

MAP_OBJ_FILES = ("rootabyss.img", "HofM4.img", "BossDemian.img")
MAP_BACK_FILES = ("rootabyss.img", "rootabyss1.img", "rootabyss2.img", "HofM4.img", "BossDemian.img")
MAP_TILE_FILES = ("rootabyssBan.img", "rootabyssBanInside.img", "rootabyssBellum.img", "rootabyssQueen.img")
SOUND_FILES = ("Bgm29.img", "Bgm45.img")
VIDEO_FILES = (
    "root-abyss-pierre.mcv",
    "root-abyss-queen.mcv",
    "root-abyss-vellum-attack10.mcv",
    "root-abyss-vellum-attack11.mcv",
    "root-abyss-vellum.mcv",
    "root-abyss-vonbon.mcv",
)

EVENT_SCRIPTS = ("PIERREBattle.js", "VELLUMBattle.js", "VONBONBattle.js", "CQBattle.js", "DamienBattle.js")
NPC_SCRIPTS = (
    "1064002.js", "1064003.js", "1064004.js", "1064005.js", "1064006.js",
    "1064007.js", "1064008.js", "1064016.js", "1064032.js",
    "1540893.js", "1540894.js", "1540895.js", "1540936.js", "1540941.js",
    "2010011.js", "3007007.js", "3007008.js",
    "9091004.js", "9091021.js", "9091023.js",
    "bbbattle.js", "blbattle.js", "nwbattle.js", "paebattle.js", "beilun.js",
    "rootaFirstDoorSelect.js", "rootaFourthDoorSelect.js", "rootaSecondDoorSelect.js", "rootaThirdDoorSelect.js",
)
PORTAL_SCRIPTS = (
    "BPReturn_Demian.js", "banbanGoInside.js", "fallenWT_boss.js", "fallenWT_gate.js",
    "go_rootabyss.js", "outrootaBoss.js", "ptBossIn.js", "ptBossOut.js",
    "ptDemianOut.js", "ptDemianOut_R.js", "pt_outrootaBoss.js", "rootaNext.js",
    "rootabyssGardenOut.js", "rootabyssOUT.js", "rootafirstDoor.js", "rootaforthDoor.js",
    "rootahiddenDoor.js", "rootasecondDoor.js", "rootathirdDoor.js", "shijieshu.js",
)
MAP_SCRIPTS = ("enter_105300000.js", "root_meet.js", "root_qrcave.js", "rootaBossEnter.js")
MONSTER_PARK_NPC_SCRIPTS = ("9071006.js", "extreme_welcome.js")
MONSTER_PARK_PORTAL_SCRIPTS = ("extreme_in03.js", "Extreme_out.js", "Extreme_out2.js")


def paired_resource_files() -> list[Path]:
    paths: list[Path] = []
    for map_id in MAP_IDS:
        group = "Map1" if str(map_id).startswith("1") else "Map3"
        paths.extend((
            ROOT / "clien" / "Data" / "Map" / "Map" / group / f"{map_id:09}.img",
            ROOT / "gms-server" / "wz" / "Map.wz" / "Map" / group / f"{map_id:09}.img.xml",
        ))
    for item_id in MOB_IDS:
        paths.extend((
            ROOT / "clien" / "Data" / "Mob" / f"{item_id:07}.img",
            ROOT / "gms-server" / "wz" / "Mob.wz" / f"{item_id:07}.img.xml",
        ))
    for item_id in NPC_IDS:
        paths.extend((
            ROOT / "clien" / "Data" / "Npc" / f"{item_id:07}.img",
            ROOT / "gms-server" / "wz" / "Npc.wz" / f"{item_id:07}.img.xml",
        ))
    for item_id in REACTOR_IDS:
        paths.extend((
            ROOT / "clien" / "Data" / "Reactor" / f"{item_id:07}.img",
            ROOT / "gms-server" / "wz" / "Reactor.wz" / f"{item_id:07}.img.xml",
        ))
    return paths


def monster_park_paired_resource_files() -> list[Path]:
    paths: list[Path] = []
    for map_id in MONSTER_PARK_MAPS:
        paths.extend((
            ROOT / "clien" / "Data" / "Map" / "Map" / "Map9" / f"{map_id:09}.img",
            ROOT / "gms-server" / "wz" / "Map.wz" / "Map" / "Map9" / f"{map_id:09}.img.xml",
        ))
    for mob_id in MONSTER_PARK_MOB_IDS:
        paths.extend((
            ROOT / "clien" / "Data" / "Mob" / f"{mob_id:07}.img",
            ROOT / "gms-server" / "wz" / "Mob.wz" / f"{mob_id:07}.img.xml",
        ))
    for npc_id in MONSTER_PARK_NPC_IDS:
        paths.extend((
            ROOT / "clien" / "Data" / "Npc" / f"{npc_id:07}.img",
            ROOT / "gms-server" / "wz" / "Npc.wz" / f"{npc_id:07}.img.xml",
        ))
    return paths


def monster_park_exclusive_resource_files() -> list[Path]:
    return [
        ROOT / "clien" / "Data" / "Map" / kind / "monsterparkEX.img"
        for kind in ("Obj", "Back")
    ]


def monster_park_script_files() -> list[Path]:
    paths: list[Path] = []
    for script_root in (ROOT / "gms-server" / "scripts", ROOT / "gms-server" / "scripts-zh-CN"):
        paths.extend(script_root / "npc" / name for name in MONSTER_PARK_NPC_SCRIPTS)
        paths.extend(script_root / "portal" / name for name in MONSTER_PARK_PORTAL_SCRIPTS)
    return paths


def independent_resource_files() -> list[Path]:
    paths: list[Path] = []
    for name in MAP_OBJ_FILES:
        paths.append(ROOT / "clien" / "Data" / "Map" / "Obj" / name)
        paths.append(ROOT / "gms-server" / "wz" / "Map.wz" / "Obj" / f"{name}.xml")
    for name in MAP_BACK_FILES:
        paths.append(ROOT / "clien" / "Data" / "Map" / "Back" / name)
        paths.append(ROOT / "gms-server" / "wz" / "Map.wz" / "Back" / f"{name}.xml")
    for name in MAP_TILE_FILES:
        paths.append(ROOT / "clien" / "Data" / "Map" / "Tile" / name)
        paths.append(ROOT / "gms-server" / "wz" / "Map.wz" / "Tile" / f"{name}.xml")
    paths.extend(ROOT / "clien" / "Data" / "Sound" / name for name in SOUND_FILES)
    paths.extend(ROOT / "clien" / "Data" / "Video" / name for name in VIDEO_FILES)
    return paths


def script_files() -> list[Path]:
    paths: list[Path] = []
    for script_root in (ROOT / "gms-server" / "scripts", ROOT / "gms-server" / "scripts-zh-CN"):
        paths.extend(script_root / "event" / name for name in EVENT_SCRIPTS)
        paths.extend(script_root / "npc" / name for name in NPC_SCRIPTS)
        paths.extend(script_root / "portal" / name for name in PORTAL_SCRIPTS)
        paths.extend(script_root / "map" / "onUserEnter" / name for name in MAP_SCRIPTS)
        paths.extend(script_root / "reactor" / f"{item_id}.js" for item_id in REACTOR_IDS)
        paths.extend(script_root / "quest" / f"{quest_id}.js" for quest_id in QUEST_SERVER_IDS if quest_id >= 0)
    return paths


def delete_paths(paths: list[Path], apply: bool, label: str, require_all_or_none: bool = False) -> None:
    existing = [path for path in paths if path.exists()]
    if require_all_or_none and existing and len(existing) != len(paths):
        missing = [str(path.relative_to(ROOT)) for path in paths if not path.exists()]
        raise ValueError(f"partial {label} baseline, missing: {missing[:20]}")
    removed_bytes = sum(path.stat().st_size for path in existing)
    if apply:
        for path in existing:
            path.unlink()
    print(f"{label}_files={len(existing)} bytes={removed_bytes}")


def remove_shared(client: Path, servers: tuple[Path, ...], client_paths, server_paths, apply: bool, label: str) -> None:
    client_data, client_count = batch_remove_img(client.read_bytes(), client_paths)
    client_saved = apply_img(client, client_data, apply)
    print(f"client_{label}_records={client_count} bytes={client_saved}")
    for server in servers:
        text, count = batch_remove_xml(server.read_text(encoding="utf-8"), server_paths)
        saved = apply_text(server, text, apply)
        print(f"server_{label}={server.relative_to(ROOT)} records={count} bytes={saved}")


def update_mob_catalog(apply: bool) -> None:
    catalog_path = ROOT / "gms-server" / "src" / "main" / "resources" / "mob-catalog" / "catalog.json"
    atlas_path = catalog_path.parent / "atlases" / "mob.png"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    removed_ids = set(MOB_IDS + MONSTER_PARK_MOB_IDS)
    removed = [mob for mob in catalog["mobs"] if int(mob["id"]) in removed_ids]
    if removed and apply:
        from PIL import Image

        image = Image.open(atlas_path).convert("RGBA")
        cell = int(catalog["cellSize"])
        for mob in removed:
            if mob.get("icon"):
                image.paste((0, 0, 0, 0), (int(mob["x"]), int(mob["y"]), int(mob["x"]) + cell, int(mob["y"]) + cell))
        image.save(atlas_path, optimize=True)
    catalog["mobs"] = [mob for mob in catalog["mobs"] if int(mob["id"]) not in removed_ids]
    catalog["atlas"]["count"] = len(catalog["mobs"])
    catalog["atlas"]["icons"] = sum(bool(mob.get("icon")) for mob in catalog["mobs"])
    text = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
    saved = apply_text(catalog_path, text, apply)
    print(f"mob_catalog_records={len(removed)} bytes={saved}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(f"mode={'apply' if args.apply else 'check'}")

    delete_paths(paired_resource_files(), args.apply, "paired_resource", require_all_or_none=True)
    delete_paths(independent_resource_files(), args.apply, "exclusive_resource")
    delete_paths(script_files(), args.apply, "script")
    delete_paths(monster_park_paired_resource_files(), args.apply, "monster_park_paired_resource", require_all_or_none=True)
    delete_paths(monster_park_exclusive_resource_files(), args.apply, "monster_park_exclusive_resource", require_all_or_none=True)
    delete_paths(monster_park_script_files(), args.apply, "monster_park_script")

    remove_shared(
        ROOT / "clien" / "Data" / "String" / "Map.img",
        (
            ROOT / "gms-server" / "wz" / "String.wz" / "Map.img.xml",
            ROOT / "gms-server" / "wz-zh-CN" / "String.wz" / "Map.img.xml",
        ),
        [("victoria", str(item_id)) for item_id in MAP_STRING_IDS],
        [("victoria", str(item_id)) for item_id in MAP_STRING_IDS],
        args.apply,
        "map_string",
    )
    remove_shared(
        ROOT / "clien" / "Data" / "String" / "Mob.img",
        (
            ROOT / "gms-server" / "wz" / "String.wz" / "Mob.img.xml",
            ROOT / "gms-server" / "wz-zh-CN" / "String.wz" / "Mob.img.xml",
        ),
        [(str(item_id),) for item_id in MOB_STRING_IDS],
        [(str(item_id),) for item_id in MOB_STRING_IDS],
        args.apply,
        "mob_string",
    )
    remove_shared(
        ROOT / "clien" / "Data" / "String" / "Map.img",
        (
            ROOT / "gms-server" / "wz" / "String.wz" / "Map.img.xml",
            ROOT / "gms-server" / "wz-zh-CN" / "String.wz" / "Map.img.xml",
        ),
        [("etc", str(item_id)) for item_id in MONSTER_PARK_MAPS],
        [("etc", str(item_id)) for item_id in MONSTER_PARK_MAPS],
        args.apply,
        "monster_park_map_string",
    )
    remove_shared(
        ROOT / "clien" / "Data" / "String" / "Mob.img",
        (
            ROOT / "gms-server" / "wz" / "String.wz" / "Mob.img.xml",
            ROOT / "gms-server" / "wz-zh-CN" / "String.wz" / "Mob.img.xml",
        ),
        [(str(item_id),) for item_id in MONSTER_PARK_MOB_IDS],
        [(str(item_id),) for item_id in MONSTER_PARK_MOB_IDS],
        args.apply,
        "monster_park_mob_string",
    )
    remove_shared(
        ROOT / "clien" / "Data" / "String" / "Npc.img",
        (
            ROOT / "gms-server" / "wz" / "String.wz" / "Npc.img.xml",
            ROOT / "gms-server" / "wz-zh-CN" / "String.wz" / "Npc.img.xml",
        ),
        [(str(item_id),) for item_id in MONSTER_PARK_NPC_IDS],
        [(str(item_id),) for item_id in MONSTER_PARK_NPC_IDS],
        args.apply,
        "monster_park_npc_string",
    )
    remove_shared(
        ROOT / "clien" / "Data" / "String" / "Npc.img",
        (
            ROOT / "gms-server" / "wz" / "String.wz" / "Npc.img.xml",
            ROOT / "gms-server" / "wz-zh-CN" / "String.wz" / "Npc.img.xml",
        ),
        [(str(item_id),) for item_id in NPC_STRING_IDS],
        [(str(item_id),) for item_id in NPC_STRING_IDS],
        args.apply,
        "npc_string",
    )

    for name in ("Act", "Check", "QuestInfo", "Say"):
        remove_shared(
            ROOT / "clien" / "Data" / "Quest" / f"{name}.img",
            (
                ROOT / "gms-server" / "wz" / "Quest.wz" / f"{name}.img.xml",
                ROOT / "gms-server" / "wz-zh-CN" / "Quest.wz" / f"{name}.img.xml",
            ),
            [(str(item_id),) for item_id in QUEST_CLIENT_IDS],
            [(str(item_id),) for item_id in QUEST_SERVER_IDS],
            args.apply,
            f"quest_{name.lower()}",
        )

    remove_shared(
        ROOT / "clien" / "Data" / "Skill" / "MobSkill.img",
        (ROOT / "gms-server" / "wz" / "Skill.wz" / "MobSkill.img.xml",),
        CLIENT_MOB_SKILLS,
        SERVER_MOB_SKILLS,
        args.apply,
        "mob_skill",
    )
    remove_shared(
        ROOT / "clien" / "Data" / "Sound" / "Mob.img",
        (ROOT / "gms-server" / "wz" / "Sound.wz" / "Mob.img.xml",),
        [("8900000",)],
        [("8900000",)],
        args.apply,
        "root_abyss_mob_sound",
    )
    remove_shared(
        ROOT / "clien" / "Data" / "UI" / "UIWindow.img",
        (ROOT / "gms-server" / "wz" / "UI.wz" / "UIWindow.img.xml",),
        [("MobGage", "Mob", str(item_id)) for item_id in DIRECT_MOB_GAUGE_IDS + ALIAS_MOB_GAUGE_IDS],
        [("MobGage", "Mob", str(item_id)) for item_id in DIRECT_MOB_GAUGE_IDS + ALIAS_MOB_GAUGE_IDS],
        args.apply,
        "mob_gauge",
    )

    remove_shared(
        ROOT / "clien" / "Data" / "Map" / "Map" / "Map1" / "105040300.img",
        (ROOT / "gms-server" / "wz" / "Map.wz" / "Map" / "Map1" / "105040300.img.xml",),
        [("portal", "24")],
        [("portal", "24")],
        args.apply,
        "root_abyss_entrance_portal",
    )
    remove_shared(
        ROOT / "clien" / "Data" / "Map" / "Map" / "Map9" / "951000000.img",
        (ROOT / "gms-server" / "wz" / "Map.wz" / "Map" / "Map9" / "951000000.img.xml",),
        [("life", "5"), ("portal", "5")],
        [("life", "5"), ("portal", "5")],
        args.apply,
        "monster_park_extreme_entrance",
    )
    remove_shared(
        ROOT / "clien" / "Data" / "Map" / "Obj" / "effect.img",
        (ROOT / "gms-server" / "wz" / "Map.wz" / "Obj" / "effect.img.xml",),
        [("quest", "gate", "8")],
        [("quest", "gate", "8")],
        args.apply,
        "shared_effect_object",
    )
    remove_shared(
        ROOT / "clien" / "Data" / "Map" / "Obj" / "gran_helisium.img",
        (ROOT / "gms-server" / "wz" / "Map.wz" / "Obj" / "gran_helisium.img.xml",),
        [("citadel_boss", "magnus", "14")],
        [("citadel_boss", "magnus", "14")],
        args.apply,
        "shared_gran_helisium_object",
    )

    house = ROOT / "clien" / "Data" / "Map" / "Obj" / "house.img"
    house_data, house_count = batch_remove_img(house.read_bytes(), [("fallenWorldTree",)])
    house_saved = apply_img(house, house_data, args.apply)
    print(f"client_house_records={house_count} bytes={house_saved}")

    map_effect = ROOT / "clien" / "Data" / "Map" / "Effect.img"
    effect_data, effect_count = batch_remove_img(
        map_effect.read_bytes(),
        [("customSkill", "rootAbyss"), ("customBossDemian",)],
    )
    effect_saved = apply_img(map_effect, effect_data, args.apply)
    print(f"client_map_effect_records={effect_count} bytes={effect_saved}")

    update_mob_catalog(args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
