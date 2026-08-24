#!/usr/bin/env python3
"""Rebuild the Arcane River complete dependency sync directory."""

from __future__ import annotations

import hashlib
import shutil
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/神秘河完整依赖同步")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_fields as migration  # noqa: E402
import migrate_chewchew_story_maps as story  # noqa: E402
import migrate_yumyum_island_maps as yumyum  # noqa: E402


ALL_MAP_IDS = (*migration.MAP_IDS, *story.MAP_IDS, *yumyum.MAP_IDS)


def copy(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_relative(source_root: Path, destination_root: Path, relative: str | Path) -> None:
    relative = Path(relative)
    copy(source_root / relative, destination_root / relative)


def dependencies() -> dict[str, object]:
    result = {
        "assets": defaultdict(set), "mobs": set(), "npcs": set(), "bgms": set(), "marks": set()
    }
    for map_id in ALL_MAP_IDS:
        image = migration.load_image(
            ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img", migration.GMS_KEY
        )
        migration.merge_dependency_sets(result, migration.collect_dependencies(image))
    expected = {
        "maps": (len(ALL_MAP_IDS), 187),
        "assets": (len(result["assets"]), 31),
        "mobs": (len(result["mobs"]), 96),
        "npcs": (len(result["npcs"]), 223),
        "bgm_packs": (len({name.split("/", 1)[0] for name in result["bgms"]}), 6),
    }
    invalid = {name: values for name, values in expected.items() if values[0] != values[1]}
    if invalid:
        raise RuntimeError(f"Arcane River dependency counts changed: {invalid}")
    return result


def sync_client(deps: dict[str, object]) -> None:
    source = ROOT / "clien/Data"
    target = DESTINATION / "Client/Data"
    for map_id in ALL_MAP_IDS:
        copy_relative(source, target, f"Map/Map/Map4/{map_id}.img")
    for kind, name in sorted(deps["assets"]):
        copy_relative(source, target, f"Map/{kind}/{name}.img")
    for relative in ("Map/MapHelper.img", "Map/Effect.img"):
        copy_relative(source, target, relative)
    for mob_id in sorted(deps["mobs"]):
        copy_relative(source, target, f"Mob/{mob_id}.img")
    for npc_id in sorted(deps["npcs"]):
        copy_relative(source, target, f"Npc/{npc_id}.img")
    for pack in sorted({name.split("/", 1)[0] for name in deps["bgms"]}):
        copy_relative(source, target, f"Sound/{pack}.img")
    for name in ("Map", "Mob", "Npc", "Etc"):
        copy_relative(source, target, f"String/{name}.img")
    for name in ("Act", "Check", "QuestInfo", "Say"):
        copy_relative(source, target, f"Quest/{name}.img")
    copy_relative(source, target, "Item/Etc/0403.img")


def sync_server(deps: dict[str, object]) -> None:
    source = ROOT / "gms-server"
    target = DESTINATION / "Server"
    for map_id in ALL_MAP_IDS:
        copy_relative(source, target, f"wz/Map.wz/Map/Map4/{map_id}.img.xml")
    for mob_id in sorted(deps["mobs"]):
        copy_relative(source, target, f"wz/Mob.wz/{mob_id}.img.xml")
    for npc_id in sorted(deps["npcs"]):
        copy_relative(source, target, f"wz/Npc.wz/{npc_id}.img.xml")
    for tree in ("wz", "wz-zh-CN"):
        for name in ("Map", "Mob", "Npc", "Etc"):
            copy_relative(source, target, f"{tree}/String.wz/{name}.img.xml")
        for name in ("Act", "Check", "QuestInfo", "Say"):
            copy_relative(source, target, f"{tree}/Quest.wz/{name}.img.xml")
    copy_relative(source, target, "wz/Item.wz/Etc/0403.img.xml")
    for migration_name in (
        "V2.1.42__add_arcane_river_mob_and_quest_drops.sql",
        "V2.1.45__add_arcane_river_core_gemstone_drop.sql",
        "V2.1.46__increase_arcane_river_core_gemstone_drop_rate.sql",
        "V2.1.61__complete_vanishing_journey_quest_drops.sql",
        "V2.1.62__add_yumyum_mob_and_quest_drops.sql",
    ):
        copy_relative(source, target, f"src/main/resources/db/migration/{migration_name}")
    copy_relative(
        source,
        target,
        "src/main/java/org/gms/net/server/channel/handlers/QuestActionHandler.java",
    )
    copy_relative(source, target, "src/main/java/org/gms/client/Character.java")
    copy_relative(source, target, "src/main/java/org/gms/server/loot/LootManager.java")
    for relative in ("scripts-zh-CN/BeiDouSpecial/万能传送.js", "scripts-zh-CN/npc/9330045.js"):
        copy_relative(source, target, relative)


def sync_tools() -> None:
    relative_paths = [
        "docs/migrations/arcane-river-complete-sync-readme.md",
        "docs/migrations/arcane-river-detailed-audit.md",
        "docs/migrations/arcane-river-legacy-connect-fix.md",
        "docs/migrations/arcane-river-quest-drop-migration.md",
        "tool/orange-wz/src/main/java/orange/wz/cli/VerifyPackedImgWz.java",
        "tool/scripts/audit/audit_arcane_river_detailed.py",
        "tool/scripts/audit/audit_arcane_river_fields.py",
        "tool/scripts/migration/migrate_arcane_river_fields.py",
        "tool/scripts/migration/migrate_chewchew_story_maps.py",
        "tool/scripts/migration/migrate_yumyum_island_maps.py",
        "tool/scripts/migration/migrate_chewchew_quests.py",
        "tool/scripts/migration/migrate_arcane_river_quests.py",
        "tool/scripts/migration/migrate_vanishing_journey_quests.py",
        "tool/scripts/migration/normalize_arcane_river_mob_eva.py",
        "tool/scripts/migration/repair_arcane_river_chewchew_swim.py",
        "tool/scripts/migration/repair_arcane_river_morass_town.py",
        "tool/scripts/migration/repair_arcane_river_extinction_asset.py",
        "tool/scripts/migration/repair_arcane_river_legacy_connect.py",
        "tool/scripts/migration/test_arcane_river_450001014_contract.py",
        "tool/scripts/migration/test_arcane_river_ballistic_attack_contract.py",
        "tool/scripts/migration/test_arcane_river_cave_portal_contract.py",
        "tool/scripts/migration/test_chewchew_story_maps_contract.py",
        "tool/scripts/migration/test_yumyum_island_contract.py",
        "tool/scripts/migration/test_chewchew_yumyum_quest_contract.py",
        "tool/scripts/migration/test_vanishing_journey_quest_contract.py",
        "tool/scripts/package/pack_img_wz.sh",
        "tool/scripts/package/sync_arcane_river_complete.py",
        "tool/scripts/patch-client/repair_arcane_river_8641002_attack_gap.py",
        "tool/scripts/patch-client/repair_arcane_river_ballistic_attacks.py",
        "tool/scripts/patch-client/repair_arcane_river_cave_portals.py",
        "tool/wz-python/wzpy/properties.py",
        "tool/wz-python/wzpy/wz_file.py",
    ]
    for relative in relative_paths:
        copy_relative(ROOT, DESTINATION / "Tools", relative)
    copy(
        ROOT / "docs/migrations/arcane-river-complete-sync-readme.md",
        DESTINATION / "README_请先阅读.md",
    )


def write_manifest() -> int:
    manifest = DESTINATION / "文件清单_SHA256.txt"
    paths = sorted(
        path for path in DESTINATION.rglob("*")
        if path.is_file() and path.name not in {".DS_Store", manifest.name}
    )
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(DESTINATION).as_posix()}"
        for path in paths
    ]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(paths)


def main() -> int:
    deps = dependencies()
    sync_client(deps)
    sync_server(deps)
    sync_tools()
    files = write_manifest()
    print(
        f"Arcane River sync rebuilt: files={files}, maps={len(ALL_MAP_IDS)}, "
        f"mobs={len(deps['mobs'])}, npcs={len(deps['npcs'])}, assets={len(deps['assets'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
