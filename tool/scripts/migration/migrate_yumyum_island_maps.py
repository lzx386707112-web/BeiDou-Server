#!/usr/bin/env python3
"""Install the legacy-safe YumYum Island dependency closure.

The 29 maps are new standalone artifacts. Existing MapHelper and String IMG
files are changed only by raw child-record insertion.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))
sys.path.insert(0, str(ROOT / "tool/scripts/patch-client"))

import migrate_arcane_river_fields as arcane  # noqa: E402
import migrate_chewchew_story_maps as story  # noqa: E402
from migrate_karing_later_stages import insert_raw_record, insert_xml_record  # noqa: E402
from wzpy import WzSubProperty  # noqa: E402


MAP_IDS = tuple(range(450015020, 450015301, 10))
MAP_ID_SET = set(MAP_IDS) | {450002025}
EXPECTED_MOBS = {
    8642050, 8642051, 8642052, 8642053, 8642054, 8642055,
    8642060, 8642061, 8642062, 8642063, 8642064, 8642065,
}
EXPECTED_NPCS = {
    3004700, 3004701, 3004702, 3004703, 3004704, 3004705, 3004706,
    3004707, 3004708, 3004709, 3004710, 3004711, 3004712, 3004713,
    3004714, 3004715, 3004716, 3004717, 3004718, 3004719, 3004720,
    3004721, 3004722, 3004723, 3004724, 3004725, 3004727, 3004728,
    3004729, 3004780, 3004781, 9010022,
}
EXPECTED_BGMS = {"Bgm54/FungusForest", "Bgm54/IlliyardMoor", "Bgm54/MushbudForest"}
EXPECTED_MARKS = {"YumYum"}
EXPECTED_ASSETS = {
    ("Back", "YumYum"),
    ("Back", "YumYum2"),
    ("Back", "chewchewIsland"),
    ("Obj", "YumYum"),
    ("Obj", "connect"),
    ("Tile", "blackTileFly"),
}
NEW_ASSETS = {
    ("Back", "YumYum"),
    ("Back", "YumYum2"),
    ("Obj", "YumYum"),
    ("Tile", "blackTileFly"),
}
STORY_ASSET_BRANCHES = {("Obj", "YumYum"): {"field1/obj/9"}}
LEGACY_PORTAL_OVERRIDES = {
    450015170: {"east00": (2, 450015180, "west00")},
}


def map_exists(map_id: int) -> bool:
    return map_id in MAP_ID_SET or (
        ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
    ).exists()


def sanitize_map(root: WzSubProperty, map_id: int) -> None:
    """Project modern YumYum fields onto the proven Arcane River schema."""
    for child in list(root.children()):
        if child.name not in story.MAP_ROOTS:
            arcane.remove_child(root, child.name)

    info = root.child("info")
    if isinstance(info, WzSubProperty):
        for name in story.MAP_INFO_UNSUPPORTED:
            arcane.remove_child(info, name)
        for name in ("returnMap", "forcedReturn"):
            target = arcane.child_value(info, name)
            if isinstance(target, int) and target != 999999999 and not map_exists(target):
                arcane.set_int(info, name, 450015020)

    life = root.child("life")
    if isinstance(life, WzSubProperty):
        for entry in list(life.children()):
            if arcane.child_value(entry, "type") == "n":
                npc_id = int(arcane.child_value(entry, "id"))
                regional = str(npc_id).startswith("300")
                installed = (ROOT / f"clien/Data/Npc/{npc_id:07d}.img").exists()
                hidden = int(arcane.child_value(entry, "hide") or 0) != 0
                if hidden or npc_id in story.REMOVED_NPCS or (not regional and not installed):
                    arcane.remove_child(life, entry.name)
                    continue
            for name in story.LIFE_UNSUPPORTED:
                arcane.remove_child(entry, name)

    for layer in [child for child in root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        for entry in list(objects.children()):
            values = " ".join(str(getattr(child, "value", "")) for child in entry.children())
            modern = any(entry.child(name) is not None for name in ("questex", "tags", "timeScale"))
            if "2025MysticBloom" in values or entry.child("spineAni") is not None or modern:
                arcane.remove_child(objects, entry.name)
                continue
            for name in story.OBJ_UNSUPPORTED:
                arcane.remove_child(entry, name)

    arcane.downgrade_connect_nodes(root)
    arcane.normalize_connect_object_order(root)

    back = root.child("back")
    if isinstance(back, WzSubProperty):
        for entry in list(back.children()):
            values = " ".join(str(getattr(child, "value", "")) for child in entry.children())
            if "2025MysticBloom" in values or int(arcane.child_value(entry, "ani") or 0) == 2:
                arcane.remove_child(back, entry.name)
                continue
            for name in story.BACK_UNSUPPORTED:
                arcane.remove_child(entry, name)

    portal = root.child("portal")
    if not isinstance(portal, WzSubProperty):
        return
    arcane.downgrade_portal_types(root)
    for entry in list(portal.children()):
        portal_name = str(arcane.child_value(entry, "pn") or "")
        override = LEGACY_PORTAL_OVERRIDES.get(map_id, {}).get(portal_name)
        if override is not None:
            portal_type, target_map, target_name = override
            arcane.set_int(entry, "pt", portal_type)
            arcane.set_int(entry, "tm", target_map)
            arcane.set_string(entry, "tn", target_name)
        target = arcane.child_value(entry, "tm")
        script = str(arcane.child_value(entry, "script") or "")
        if (
            isinstance(target, int)
            and target != 999999999
            and not map_exists(target)
        ) or (script and target == 999999999):
            arcane.remove_child(portal, entry.name)
            continue
        arcane.remove_child(entry, "script")
        for name in story.PORTAL_UNSUPPORTED:
            arcane.remove_child(entry, name)


def migrate_maps() -> dict[str, int]:
    totals = {"maps": 0, "canvases": 0, "links": 0, "resized": 0}
    for map_id in MAP_IDS:
        source = SOURCE / f"Map/Map/Map4/{map_id}.img"
        if not source.exists():
            raise FileNotFoundError(source)
        image, materializer = story.clone_image(
            source, lambda root, value=map_id: sanitize_map(root, value)
        )
        story.write_client_image(
            ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img", image
        )
        story.write_server_image(
            ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml",
            image,
            f"{map_id}.img",
        )
        totals["maps"] += 1
        totals["canvases"] += materializer.canvases
        totals["links"] += materializer.links
        totals["resized"] += materializer.resized
    return totals


def collect_dependencies() -> dict[str, object]:
    result: dict[str, object] = {
        "assets": defaultdict(set),
        "mobs": set(),
        "npcs": set(),
        "bgms": set(),
        "marks": set(),
    }
    for map_id in MAP_IDS:
        image = arcane.load_image(
            ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img", arcane.GMS_KEY
        )
        arcane.merge_dependency_sets(result, arcane.collect_dependencies(image))
    actual = {
        "assets": set(result["assets"]),
        "mobs": set(result["mobs"]),
        "npcs": set(result["npcs"]),
        "bgms": set(result["bgms"]),
        "marks": set(result["marks"]),
    }
    expected = {
        "assets": EXPECTED_ASSETS,
        "mobs": EXPECTED_MOBS,
        "npcs": EXPECTED_NPCS,
        "bgms": EXPECTED_BGMS,
        "marks": EXPECTED_MARKS,
    }
    changed = {
        name: {"actual": sorted(actual[name]), "expected": sorted(values)}
        for name, values in expected.items()
        if actual[name] != values
    }
    if changed:
        raise RuntimeError(f"YumYum dependency contract changed: {changed}")
    return result


def ensure_path(root: WzSubProperty, path: str) -> WzSubProperty:
    current = root
    for name in [part for part in path.split("/") if part]:
        child = current.child(name)
        if not isinstance(child, WzSubProperty):
            child = WzSubProperty(name, current)
            current.add(child)
        current = child
    return current


def migrate_new_assets(dependencies: dict[str, object]) -> dict[str, int]:
    totals = {"files": 0, "branches": 0, "canvases": 0}
    branches_by_asset = {
        key: set(branches)
        for key, branches in dependencies["assets"].items()
        if key in NEW_ASSETS
    }
    for key, branches in STORY_ASSET_BRANCHES.items():
        branches_by_asset.setdefault(key, set()).update(branches)
    if set(branches_by_asset) != NEW_ASSETS:
        raise RuntimeError(f"unexpected new YumYum assets: {sorted(branches_by_asset)}")

    for (kind, name), branches in sorted(branches_by_asset.items()):
        source_path = SOURCE / f"Map/{kind}/{name}.img"
        source = arcane.load_image(source_path, arcane.BMS_KEY)
        materializer = arcane.CanvasMaterializer()
        root = WzSubProperty(source.root.name)
        for branch in sorted(branches):
            source_node = source.root.get(branch)
            if source_node is None:
                raise RuntimeError(f"missing source Map/{kind}/{name}.img/{branch}")
            parent_path, _, leaf = branch.rpartition("/")
            parent = ensure_path(root, parent_path)
            parent.add(
                arcane.clone_property(
                    source_node, parent, source, source_path, materializer, leaf
                )
            )
        source._root = root
        source._parsed = True
        story.write_client_image(ROOT / f"clien/Data/Map/{kind}/{name}.img", source)
        story.write_server_image(
            ROOT / f"gms-server/wz/Map.wz/{kind}/{name}.img.xml",
            source,
            f"{name}.img",
        )
        totals["files"] += 1
        totals["branches"] += len(branches)
        totals["canvases"] += materializer.canvases
    return totals


def migrate_map_mark() -> dict[str, int]:
    source_path = SOURCE / "Map/MapHelper.img"
    source = arcane.load_image(source_path, arcane.BMS_KEY)
    source_node = source.root.get("mark/YumYum")
    if source_node is None:
        raise RuntimeError("source MapHelper.img has no mark/YumYum")
    parent = WzSubProperty("mark")
    materializer = arcane.CanvasMaterializer()
    node = arcane.clone_property(
        source_node, parent, source, source_path, materializer, "YumYum"
    )
    parent.add(node)
    return {
        "client": int(
            insert_raw_record(ROOT / "clien/Data/Map/MapHelper.img", ("mark",), node)
        ),
        "canvases": materializer.canvases,
    }


def migrate_npcs(npc_ids: set[int]) -> dict[str, int]:
    totals = {"npcs": 0, "canvases": 0, "links": 0, "resized": 0}
    for npc_id in sorted(value for value in npc_ids if str(value).startswith("300")):
        source = SOURCE / f"Npc/{npc_id:07d}.img"
        image, materializer = story.clone_image(source, arcane.sanitize_npc)
        story.write_client_image(ROOT / f"clien/Data/Npc/{npc_id:07d}.img", image)
        story.write_server_image(
            ROOT / f"gms-server/wz/Npc.wz/{npc_id:07d}.img.xml",
            image,
            f"{npc_id:07d}.img",
        )
        totals["npcs"] += 1
        totals["canvases"] += materializer.canvases
        totals["links"] += materializer.links
        totals["resized"] += materializer.resized
    return totals


def migrate_mobs(mob_ids: set[int]) -> dict[str, int]:
    totals = {"mobs": 0, "canvases": 0, "links": 0, "resized": 0}
    for mob_id in sorted(mob_ids):
        canvases, links, resized = arcane.migrate_one_mob(mob_id)
        totals["mobs"] += 1
        totals["canvases"] += canvases
        totals["links"] += links
        totals["resized"] += resized
    return totals


def string_node(source, source_path: Path, node, name: str):
    parent = WzSubProperty("strings")
    output = arcane.clone_property(
        node, parent, source, source_path, arcane.CanvasMaterializer(), name
    )
    parent.add(output)
    return output


def migrate_strings(dependencies: dict[str, object]) -> dict[str, int]:
    totals = {"client": 0, "server": 0}
    specs = (
        ("Map", set(MAP_IDS), ("grandis",)),
        ("Mob", set(dependencies["mobs"]), ()),
        ("Npc", set(dependencies["npcs"]), ()),
    )
    for image_name, ids, parent_path in specs:
        source_path = SOURCE / f"String/{image_name}.img"
        source = arcane.load_image(source_path, arcane.BMS_KEY)
        for value in sorted(ids):
            source_record = (
                story.source_map_string(source, value)
                if image_name == "Map"
                else source.root.get(str(value))
            )
            if source_record is None:
                raise RuntimeError(f"missing source String/{image_name}.img/{value}")
            node = string_node(source, source_path, source_record, str(value))
            totals["client"] += int(
                insert_raw_record(
                    ROOT / f"clien/Data/String/{image_name}.img", parent_path, node
                )
            )
            for tree in ("wz", "wz-zh-CN"):
                target = ROOT / f"gms-server/{tree}/String.wz/{image_name}.img.xml"
                if target.exists():
                    totals["server"] += int(insert_xml_record(target, parent_path, node))
    return totals


def main() -> int:
    print(f"YumYum maps: {MAP_IDS[0]}-{MAP_IDS[-1]} ({len(MAP_IDS)})")
    print("maps", migrate_maps())
    dependencies = collect_dependencies()
    print("assets", migrate_new_assets(dependencies))
    print("map mark", migrate_map_mark())
    print("npcs", migrate_npcs(set(dependencies["npcs"])))
    print("mobs", migrate_mobs(set(dependencies["mobs"])))
    print("bgms", arcane.migrate_bgms(set(dependencies["bgms"])))
    print("strings", migrate_strings(dependencies))
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
