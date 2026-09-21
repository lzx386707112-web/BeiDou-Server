#!/usr/bin/env python3
"""Migrate Princess No, Odium/Shangri-La, and legacy Commerci voyages.

The source whitelists are deliberate. Existing IMG containers are changed only
through raw record insertion; newly installed standalone resources are written
from an old-client compatibility projection.
"""

from __future__ import annotations

import copy
import importlib.util
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

spec = importlib.util.spec_from_file_location(
    "arcane_migration", ROOT / "tool/scripts/migration/migrate_arcane_river_expansion.py"
)
arc = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = arc
spec.loader.exec_module(arc)

from wzpy import WzImage, WzIntProperty, WzStringProperty, WzSubProperty  # noqa: E402
from wzpy.incremental_img import mutate_img, replace_img_record  # noqa: E402
from wzpy.incremental_xml import mutate_xml  # noqa: E402


ODIUM_MAPS = (*range(410007000, 410007019), 410007051, 410007052)
SHANGRI_MAPS = (*range(410007020, 410007025), *range(410007026, 410007046))
NOHIME_MAPS = (811000999, 811000100, 811000200, 811000300, 811000400, 811000500)
COMMERCI_MAPS = (865000001, 865000100, 865000200, 865000300,
                 865000400, 865000500, 865000501, 865000900)
COMMERCI_SOLO_VOYAGE_MAPS = (865000100, 865000200, 865000300, 865000400, 865000900)
MAP_IDS = (*ODIUM_MAPS, *SHANGRI_MAPS, *NOHIME_MAPS, *COMMERCI_MAPS)

ODIUM_MOBS = set(range(8645290, 8645300))
SHANGRI_MOBS = set(range(8645365, 8645373))
NOHIME_MOBS = {9450035, 9450037, 9450038, 9450039, 9450040}
NOHIME_BALLISTIC_ATTACKS = {9450037: (1, 140)}
NOHIME_SCENE_MOB = 9450040
NOHIME_SCENE_SUMMON_MOBS = {9450021, 9450047, 9450048, 9450049, 9450050}
NOHIME_SCENE_SKILLS = (
    (0, 1, 235, (("effectAfter", 0), ("afterAttack", 4), ("afterAttackCount", 1))),
    (1, 2, 236, (("skillAfter", 960),)),
)
NOHIME_SCENE_LEVEL_SOURCES = {235: (170, 55), 236: (201, 111)}
NOHIME_MOB_SKILL_CACHE = Path("/private/tmp/nohime-mob-skill-cache")
COMMERCI_MOBS = set(range(9390800, 9390809))
NOHIME_MOBS |= NOHIME_SCENE_SUMMON_MOBS
MOB_IDS = ODIUM_MOBS | SHANGRI_MOBS | NOHIME_MOBS | COMMERCI_MOBS

ODIUM_NPCS = {9000365}
NOHIME_NPCS = {9130100}
COMMERCI_NPCS = {9390220, 9390221, 9390225, 9390253, 9390254}
EXPLICIT_NPCS = ODIUM_NPCS | NOHIME_NPCS | COMMERCI_NPCS

ODIUM_QUESTS = {*range(38301, 38331), 38350, 38432}
SHANGRI_QUESTS = {*range(38391, 38402), *range(38404, 38416), 38417, 38418, 38433}
QUEST_IDS = ODIUM_QUESTS | SHANGRI_QUESTS
QUEST_ITEMS = {4036894, 4036895, 4036896, 4037167, 4037168, 4037169, 4037170}
ITEM_IDS = QUEST_ITEMS | {4310100}

MAP_CATEGORY = {
    **{map_id: "grandis" for map_id in (*ODIUM_MAPS, *SHANGRI_MAPS)},
    **{map_id: "jp" for map_id in NOHIME_MAPS},
    **{map_id: "etc" for map_id in COMMERCI_MAPS},
}

PORTAL_OVERRIDES = {
    410007001: {"east00": (410007000, "west00")},
    410007005: {"west00": (410007051, "east00")},
    410007009: {"east00": (410007010, "west00")},
    410007011: {"east00": (410007015, "west00")},
    410007018: {"east00": (410007021, "west00")},
    410007021: {"east00": (410007022, "west00"), "ground00": (410007026, "east00")},
    410007022: {"east00": (410007023, "west00"), "ground00": (410007029, "west00")},
    410007023: {"east00": (410007024, "west00"), "ground00": (410007032, "east00")},
    410007024: {"east00": (410007020, "west00"), "ground00": (410007035, "west00")},
    811000999: {"out00": (807000000, "sp")},
}

QUEST_INFO_FIELDS = {
    "name", "area", "0", "1", "2", "category", "demandSummary",
    "rewardSummary", "autoStart", "autoAccept", "autoPreComplete",
    "dailyAlarm", "medalCategory", "viewMedalItem",
}


def child_value(node, name):
    return arc.child_value(node, name)


def dense_numeric_children(node: WzSubProperty | None) -> None:
    if not isinstance(node, WzSubProperty):
        return
    children = list(node.children())
    node._children.clear()
    for index, child in enumerate(children):
        child.name = str(index)
        node.add(child)


def sanitize_map(root: WzSubProperty, map_id: int) -> None:
    # questex/tags/timeScale are unsupported fields, not reasons to discard the
    # complete object. Remove them before the shared sanitizer evaluates the
    # object; spineAni remains a whole-object removal for this legacy client.
    for layer in (child for child in root.children() if child.name.isdigit()):
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        for entry in list(objects.children()):
            if (
                map_id == 410007000
                and child_value(entry, "oS") == "odium"
                and child_value(entry, "l0") == "spine"
            ):
                arc.remove_child(objects, entry.name)
                continue
            for field in ("questex", "tags", "timeScale"):
                arc.remove_child(entry, field)
    arc.sanitize_map(root, map_id)
    if map_id in COMMERCI_SOLO_VOYAGE_MAPS:
        ship = root.get("5/obj/0")
        if (
            isinstance(ship, WzSubProperty)
            and child_value(ship, "oS") == "dawnveil1_BT"
            and child_value(ship, "l0") == "sailing"
            and child_value(ship, "l1") == "ship"
        ):
            # SailField normally unhides this object. The legacy projection
            # uses Rien's visible ship state because that client-side field
            # controller is unavailable.
            arc.set_string(ship, "l2", "1")
            arc.set_int(ship, "hide", 0)
    if map_id in COMMERCI_MAPS:
        # These legacy ship reactors are absent from both the TMS export and
        # the target client. The custom voyage event does not use them.
        reactor = root.child("reactor")
        if isinstance(reactor, WzSubProperty):
            reactor._children.clear()
    if map_id == 410007000:
        back = root.child("back")
        if isinstance(back, WzSubProperty):
            for entry in back.children():
                number = entry.child("no")
                if isinstance(number, WzStringProperty) and str(number.value).isdigit():
                    entry._children["no"] = WzIntProperty("no", int(number.value), entry)
        portal = root.child("portal")
        if isinstance(portal, WzSubProperty):
            for entry in portal.children():
                if child_value(entry, "pt") != 17:
                    continue
                arc.set_int(entry, "pt", 3)
                for field in ("cameraLooseLevel", "cameraLooseLevelTime", "verticalImpact"):
                    arc.remove_child(entry, field)
    for name in ("back", "life", "ladderRope", "reactor", "portal"):
        dense_numeric_children(root.child(name))
    for layer in (child for child in root.children() if child.name.isdigit()):
        dense_numeric_children(layer.child("obj"))
        dense_numeric_children(layer.child("tile"))


def repair_commerci_ship_visibility() -> None:
    approved = {("5", "obj", "0", "l2"), ("5", "obj", "0", "hide")}
    for map_id in COMMERCI_SOLO_VOYAGE_MAPS:
        client = ROOT / f"clien/Data/Map/Map/Map8/{map_id}.img"
        server = ROOT / f"gms-server/wz/Map.wz/Map/Map8/{map_id}.img.xml"
        before = client.read_bytes()
        image = arc.load_image(client, arc.GMS_KEY)
        ship = image.root.get("5/obj/0")
        signature = tuple(child_value(ship, field) for field in ("oS", "l0", "l1"))
        if signature != ("dawnveil1_BT", "sailing", "ship"):
            raise RuntimeError(f"unexpected ship object in map {map_id}: {signature}")
        after = before
        if child_value(ship, "l2") != "1":
            after = mutate_img(
                after, "edit", ("5", "obj", "0", "l2"),
                values={"value": "1"}, region="GMS",
            ).data
        current = WzImage.from_bytes(after, key=arc.GMS_KEY, name=client.name)
        current.parse()
        if child_value(current.root.get("5/obj/0"), "hide") != 0:
            after = mutate_img(
                after, "edit", ("5", "obj", "0", "hide"),
                values={"value": 0}, region="GMS",
            ).data
        if after != before:
            arc.verify_raw_record_scope(before, after, approved, allow_additions=False)
            arc.atomic_write_bytes(client, after)

        text = server.read_text(encoding="utf-8")
        updated = text
        root = ET.fromstring(updated)
        ship_xml = root.find('./imgdir[@name="5"]/imgdir[@name="obj"]/imgdir[@name="0"]')
        if ship_xml is None:
            raise RuntimeError(f"missing server ship object in map {map_id}")
        signature_xml = tuple(
            ship_xml.find(f'./string[@name="{field}"]').get("value")
            for field in ("oS", "l0", "l1")
        )
        if signature_xml != ("dawnveil1_BT", "sailing", "ship"):
            raise RuntimeError(f"unexpected server ship object in map {map_id}: {signature_xml}")
        if ship_xml.find('./string[@name="l2"]').get("value") != "1":
            updated = mutate_xml(
                updated, "edit", ("5", "obj", "0", "l2"),
                kind="String", values={"value": "1"},
            )
        root = ET.fromstring(updated)
        hide = root.find('./imgdir[@name="5"]/imgdir[@name="obj"]/imgdir[@name="0"]/int[@name="hide"]')
        if hide is None:
            raise RuntimeError(f"missing server ship hide field in map {map_id}")
        if hide.get("value") != "0":
            updated = mutate_xml(
                updated, "edit", ("5", "obj", "0", "hide"),
                kind="Int", values={"value": 0},
            )
        if updated != text:
            arc.atomic_write_text(server, updated)


def configure_arcane_helpers() -> None:
    arc.MAP_ID_SET = set(MAP_IDS)
    arc.INSTALLED_ROUTE_MAP_IDS = {807000000, 865000000}
    arc.LEGACY_CONNECT_FIRST_MAPS = set(MAP_IDS)
    arc.TOWN_BY_PREFIX.update({"410007": 410007000, "811000": 807000000, "865000": 865000001})
    arc.LEGACY_CAVE_ROUTE_PORTALS = PORTAL_OVERRIDES
    arc.BACKUP_ROOT = Path("/private/tmp/nohime-odium-shangrila-commerci-backup")


def install_npcs(npc_ids: set[int]) -> None:
    for npc_id in sorted(npc_ids):
        arc.migrate_one_npc(npc_id)


def source_map_path(map_id: int) -> Path:
    return SOURCE / f"Map/Map/Map{str(map_id)[0]}/{map_id}.img"


def migrate_maps():
    dependencies = {
        "assets": defaultdict(set), "mobs": set(), "npcs": set(), "bgms": set(), "marks": set()
    }
    for map_id in MAP_IDS:
        source = source_map_path(map_id)
        target = ROOT / f"clien/Data/Map/Map/Map{str(map_id)[0]}/{map_id}.img"
        server = ROOT / f"gms-server/wz/Map.wz/Map/Map{str(map_id)[0]}/{map_id}.img.xml"
        image, _ = arc.clone_image(source, lambda root, mid=map_id: sanitize_map(root, mid))
        arc.write_client_image(target, image)
        arc.write_server_image(server, image, f"{map_id}.img")
        arc.merge_dependency_sets(dependencies, arc.collect_dependencies(image))
    return dependencies


def upsert_strings(img_name: str, ids: set[int], category: str | None = None) -> None:
    arc.upsert_client_strings(img_name, ids, category)
    for tree in ("wz", "wz-zh-CN"):
        arc.upsert_server_strings(tree, img_name, ids, category)


def migrate_map_strings() -> None:
    for category in {value for value in MAP_CATEGORY.values()}:
        ids = {map_id for map_id, value in MAP_CATEGORY.items() if value == category}
        upsert_strings("Map", ids, category)


def install_nohime_entry() -> None:
    client = ROOT / "clien/Data/Map/Map/Map8/807000000.img"
    server = ROOT / "gms-server/wz/Map.wz/Map/Map8/807000000.img.xml"
    image = arc.load_image(client, arc.GMS_KEY)
    life = image.root.child("life")
    if any(child_value(entry, "id") == "9130100" for entry in life.children()):
        return
    entry = WzSubProperty("1006")
    entry.add(WzStringProperty("type", "n", entry))
    entry.add(WzStringProperty("id", "9130100", entry))
    for name, value in (
        ("x", -1550), ("y", 17), ("mobTime", 0), ("f", 0), ("hide", 0),
        ("fh", 162), ("cy", 30), ("rx0", -1600), ("rx1", -1500),
    ):
        entry.add(WzIntProperty(name, value, entry))
    before = client.read_bytes()
    after = arc.append_property_record(before, ("life",), entry)
    arc.verify_raw_record_insert_scope(before, after, {("life", "1006")})
    arc.atomic_write_bytes(client, after)
    text = server.read_text(encoding="utf-8")
    text = arc.append_xml_properties(text, ("life",), [entry])
    arc.atomic_write_text(server, text)


def find_item_record(image, item_id: int):
    candidates = (str(item_id), f"0{item_id}")
    for name in candidates:
        node = image.root.child(name)
        if node is not None:
            return node
    raise RuntimeError(f"missing source item record {item_id}")


def migrate_item_container(container: str, item_ids: set[int]) -> None:
    source_path = SOURCE / f"Item/Etc/{container}.img"
    client_path = ROOT / f"clien/Data/Item/Etc/{container}.img"
    server_path = ROOT / f"gms-server/wz/Item.wz/Etc/{container}.img.xml"
    source = arc.load_image(source_path, arc.BMS_KEY)
    target = arc.load_image(client_path, arc.GMS_KEY)
    data = client_path.read_bytes()
    xml = server_path.read_text(encoding="utf-8")
    xml_root = ET.fromstring(xml)
    materializer = arc.CanvasMaterializer()
    for item_id in sorted(item_ids):
        source_node = find_item_record(source, item_id)
        name = source_node.name
        if target.root.child(name) is None:
            cloned = arc.clone_property(source_node, None, source, source_path, materializer, name)
            data = arc.append_property_record(data, (), cloned)
            target = arc.load_image_bytes(data, arc.GMS_KEY, client_path.name) if hasattr(arc, "load_image_bytes") else None
            if target is None:
                from wzpy import WzImage
                target = WzImage.from_bytes(data, key=arc.GMS_KEY, name=client_path.name)
                target.parse()
        if xml_root.find(f'./imgdir[@name="{name}"]') is None:
            xml = arc.append_xml_properties(xml, (), [source_node])
            xml_root = ET.fromstring(xml)
    if data != client_path.read_bytes():
        arc.backup(client_path)
        arc.atomic_write_bytes(client_path, data)
    if xml != server_path.read_text(encoding="utf-8"):
        arc.backup(server_path)
        arc.atomic_write_text(server_path, xml)


def migrate_items() -> None:
    migrate_item_container("0403", QUEST_ITEMS)
    migrate_item_container("0431", {4310100})
    source = arc.load_image(SOURCE / "String/Etc.img", arc.BMS_KEY)
    for tree_path in [
        ROOT / "clien/Data/String/Etc.img",
    ]:
        target = arc.load_image(tree_path, arc.GMS_KEY)
        data = tree_path.read_bytes()
        parent = target.root.get("Etc")
        materializer = arc.CanvasMaterializer()
        for item_id in sorted(ITEM_IDS):
            if parent.child(str(item_id)) is None:
                node = source.root.get(f"Etc/{item_id}")
                cloned = arc.clone_property(node, None, source, SOURCE / "String/Etc.img", materializer)
                data = arc.append_property_record(data, ("Etc",), cloned)
                from wzpy import WzImage
                target = WzImage.from_bytes(data, key=arc.GMS_KEY, name=tree_path.name)
                target.parse()
                parent = target.root.get("Etc")
        if data != tree_path.read_bytes():
            arc.backup(tree_path)
            arc.atomic_write_bytes(tree_path, data)
    for tree in ("wz", "wz-zh-CN"):
        path = ROOT / f"gms-server/{tree}/String.wz/Etc.img.xml"
        text = path.read_text(encoding="utf-8")
        root = ET.fromstring(text)
        parent = root.find('./imgdir[@name="Etc"]')
        additions = [source.root.get(f"Etc/{item_id}") for item_id in sorted(ITEM_IDS)
                     if parent.find(f'./imgdir[@name="{item_id}"]') is None]
        if additions:
            text = arc.append_xml_properties(text, ("Etc",), additions)
            arc.backup(path)
            arc.atomic_write_text(path, text)


def migrate_mobs() -> None:
    for mob_id in sorted(MOB_IDS):
        client = ROOT / f"clien/Data/Mob/{mob_id:07d}.img"
        server = ROOT / f"gms-server/wz/Mob.wz/{mob_id:07d}.img.xml"
        if client.exists():
            image = arc.load_image(client, arc.GMS_KEY)
            if not server.exists():
                arc.write_server_image(server, image, f"{mob_id:07d}.img")
            continue
        arc.migrate_one_mob(mob_id)


def make_nohime_scene_skill_info() -> WzSubProperty:
    skills = WzSubProperty("skill")
    for slot, action, level, extra_fields in NOHIME_SCENE_SKILLS:
        entry = WzSubProperty(str(slot), skills)
        entry.add(WzIntProperty("action", action, entry))
        entry.add(WzIntProperty("skill", 200, entry))
        entry.add(WzIntProperty("level", level, entry))
        for name, value in extra_fields:
            entry.add(WzIntProperty(name, value, entry))
        skills.add(entry)
    return skills


def extract_nohime_mob_skill(skill_id: int) -> Path:
    output = NOHIME_MOB_SKILL_CACHE / f"Skill_MobSkill_{skill_id}.img"
    if output.exists():
        return output
    NOHIME_MOB_SKILL_CACHE.mkdir(parents=True, exist_ok=True)
    pack = arc.PACKS / "Skill_00007.ms"
    result = subprocess.run(
        [
            "dotnet", str(arc.MS_PROBE), str(pack), str(NOHIME_MOB_SKILL_CACHE),
            f"Skill/MobSkill/{skill_id}.img",
        ],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0 or not output.exists():
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"unable to extract MobSkill {skill_id}: {detail}")
    return output


def load_nohime_scene_level(target_level: int) -> WzSubProperty:
    source_skill, source_level = NOHIME_SCENE_LEVEL_SOURCES[target_level]
    source_path = extract_nohime_mob_skill(source_skill)
    source = arc.load_image(source_path, arc.BMS_KEY)
    node = source.root.get(f"level/{source_level}")
    if not isinstance(node, WzSubProperty):
        raise RuntimeError(f"TMS MobSkill {source_skill}/{source_level} is missing")
    cloned = WzSubProperty(str(target_level))
    for child in node.children():
        if not isinstance(child, WzIntProperty):
            raise RuntimeError(
                f"unexpected TMS MobSkill {source_skill}/{source_level} field: "
                f"{child.name} ({child.type_name})"
            )
        cloned.add(WzIntProperty(child.name, int(child.value), cloned))
    return cloned


def scalar_level_values(node: WzSubProperty) -> tuple[tuple[str, int], ...]:
    values = []
    for child in node.children():
        if not isinstance(child, WzIntProperty):
            raise RuntimeError(f"unexpected scene MobSkill field type: {child.type_name}")
        values.append((child.name, int(child.value)))
    return tuple(values)


def verify_scene_level_replacements(
    before: bytes, after: bytes, approved_roots: set[tuple[str, ...]]
) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)

    def inside_approved(path: tuple[str, ...]) -> bool:
        return any(path[:len(root)] == root for root in approved_roots)

    changed_paths = set(before_records) ^ set(after_records)
    if any(not inside_approved(path) for path in changed_paths):
        raise RuntimeError(f"scene MobSkill patch changed unapproved paths: {sorted(changed_paths)}")
    for path, raw in before_records.items():
        affected = inside_approved(path) or any(root[:len(path)] == path for root in approved_roots)
        if not affected and after_records.get(path) != raw:
            raise RuntimeError(f"scene MobSkill patch changed protected record: {path}")
    for parent, names in before_orders.items():
        if not inside_approved(parent) and after_orders.get(parent) != names:
            raise RuntimeError(f"scene MobSkill patch reordered siblings at {parent}")


def replace_xml_property_record(text: str, path: tuple[str, ...], prop: WzSubProperty) -> str:
    current = arc.scan_xml(text)
    for part in path:
        matches = [child for child in current.children if child.name == part]
        if len(matches) != 1:
            raise RuntimeError(f"XML path is not unique: {'/'.join(path)}")
        current = matches[0]
    line_start = text.rfind("\n", 0, current.start) + 1
    line_prefix = text[line_start:current.start]
    standalone = not line_prefix.strip()
    indent = line_prefix if standalone and len(line_prefix) <= 16 else ""
    trailing_space = len(line_prefix) - len(line_prefix.rstrip())
    replace_start = line_start if standalone else current.start - trailing_space
    replacement = arc.property_to_xml(prop, len(indent) // 2)
    if not standalone:
        replacement = replacement.lstrip()
    result = text[:replace_start] + replacement + text[current.end:]
    arc.scan_xml(result)
    return result


def assert_nohime_scene_skill_info(info: WzSubProperty, label: str) -> None:
    skills = info.child("skill")
    if not isinstance(skills, WzSubProperty):
        raise RuntimeError(f"{label}: missing info/skill")
    if [child.name for child in skills.children()] != ["0", "1"]:
        raise RuntimeError(f"{label}: unexpected info/skill slots")
    for slot, action, level, extra_fields in NOHIME_SCENE_SKILLS:
        entry = skills.child(str(slot))
        expected = {"action": action, "skill": 200, "level": level, **dict(extra_fields)}
        actual = {child.name: child_value(entry, child.name) for child in entry.children()}
        if actual != expected:
            raise RuntimeError(f"{label}: conflicting info/skill/{slot}: {actual}")


def repair_nohime_scene_skills() -> None:
    client_mob = ROOT / f"clien/Data/Mob/{NOHIME_SCENE_MOB}.img"
    server_mob = ROOT / f"gms-server/wz/Mob.wz/{NOHIME_SCENE_MOB}.img.xml"
    client_skills = ROOT / "clien/Data/Skill/MobSkill.img"
    server_skills = ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml"

    before_mob = client_mob.read_bytes()
    mob_image = arc.load_image(client_mob, arc.GMS_KEY)
    info = mob_image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{NOHIME_SCENE_MOB}: missing info")
    after_mob = before_mob
    if info.child("skill") is None:
        after_mob = arc.insert_property_record_before(
            before_mob, ("info",), make_nohime_scene_skill_info(), "exp"
        )
        arc.verify_raw_record_insert_scope(
            before_mob, after_mob, {("info", "skill")}
        )
        arc.atomic_write_bytes(client_mob, after_mob)
    current_mob = WzImage.from_bytes(after_mob, key=arc.GMS_KEY, name=client_mob.name)
    current_mob.parse()
    assert_nohime_scene_skill_info(current_mob.root.child("info"), "client mob")

    mob_xml = server_mob.read_text(encoding="utf-8")
    updated_mob_xml = mob_xml
    mob_root = ET.fromstring(updated_mob_xml)
    info_xml = mob_root.find('./imgdir[@name="info"]')
    if info_xml is None:
        raise RuntimeError(f"{NOHIME_SCENE_MOB}: missing server info")
    if info_xml.find('./imgdir[@name="skill"]') is None:
        updated_mob_xml = arc.insert_xml_properties_before(
            updated_mob_xml, ("info",), [make_nohime_scene_skill_info()], "exp"
        )
        arc.atomic_write_text(server_mob, updated_mob_xml)

    source_levels = {
        level: load_nohime_scene_level(level) for level in NOHIME_SCENE_LEVEL_SOURCES
    }
    before_skills = client_skills.read_bytes()
    after_skills = before_skills
    for level, source_level in source_levels.items():
        current = WzImage.from_bytes(after_skills, key=arc.GMS_KEY, name=client_skills.name)
        current.parse()
        node = current.root.get(f"200/level/{level}")
        if node is None:
            after_skills = arc.append_property_record(
                after_skills, ("200", "level"), source_level
            )
        elif not isinstance(node, WzSubProperty):
            raise RuntimeError(f"client MobSkill 200/{level} is not a level node")
        elif scalar_level_values(node) != scalar_level_values(source_level):
            after_skills = replace_img_record(
                after_skills, ("200", "level", str(level)), source_level, region="GMS"
            ).data
    if after_skills != before_skills:
        approved = {("200", "level", str(level)) for level in source_levels}
        verify_scene_level_replacements(before_skills, after_skills, approved)
        arc.atomic_write_bytes(client_skills, after_skills)

    skill_xml = server_skills.read_text(encoding="utf-8")
    updated_skill_xml = skill_xml
    for level, source_level in source_levels.items():
        root = ET.fromstring(updated_skill_xml)
        path = f'./imgdir[@name="200"]/imgdir[@name="level"]/imgdir[@name="{level}"]'
        node = root.find(path)
        if node is None:
            updated_skill_xml = arc.append_xml_properties(
                updated_skill_xml, ("200", "level"), [source_level]
            )
        else:
            updated_skill_xml = replace_xml_property_record(
                updated_skill_xml, ("200", "level", str(level)), source_level
            )
    if updated_skill_xml != skill_xml:
        arc.atomic_write_text(server_skills, updated_skill_xml)

    for mob_id in sorted(NOHIME_SCENE_SUMMON_MOBS):
        arc.migrate_one_mob(mob_id)
    upsert_strings("Mob", NOHIME_SCENE_SUMMON_MOBS)


def repair_nohime_ballistics() -> None:
    for mob_id, (attack_number, bullet_speed) in NOHIME_BALLISTIC_ATTACKS.items():
        client = ROOT / f"clien/Data/Mob/{mob_id:07d}.img"
        server = ROOT / f"gms-server/wz/Mob.wz/{mob_id:07d}.img.xml"
        parent = (f"attack{attack_number}", "info")
        approved = {(*parent, "type"), (*parent, "bulletSpeed")}

        before = client.read_bytes()
        image = arc.load_image(client, arc.GMS_KEY)
        info = image.root.get("/".join(parent))
        if not isinstance(info, WzSubProperty) or not isinstance(info.child("ball"), WzSubProperty):
            raise RuntimeError(f"{mob_id}: missing ballistic {parent[0]}/info/ball")
        if info.child("attackAfter") is None:
            raise RuntimeError(f"{mob_id}: missing ballistic {parent[0]}/info/attackAfter")

        after = before
        attack_type = child_value(info, "type")
        if attack_type is None:
            after = arc.insert_property_record_before(
                after, parent, WzIntProperty("type", 2), "attackAfter"
            )
        elif attack_type != 2:
            raise RuntimeError(f"{mob_id}: conflicting ballistic type={attack_type}")

        image = WzImage.from_bytes(after, key=arc.GMS_KEY, name=client.name)
        image.parse()
        info = image.root.get("/".join(parent))
        current_speed = child_value(info, "bulletSpeed")
        if current_speed is None:
            after = arc.append_property_record(
                after, parent, WzIntProperty("bulletSpeed", bullet_speed)
            )
        elif current_speed != bullet_speed:
            raise RuntimeError(
                f"{mob_id}: conflicting ballistic bulletSpeed={current_speed}"
            )

        if after != before:
            arc.verify_raw_record_insert_scope(before, after, approved)
            arc.atomic_write_bytes(client, after)

        text = server.read_text(encoding="utf-8")
        updated = text
        root = ET.fromstring(updated)
        info_xml = root.find(
            f'./imgdir[@name="attack{attack_number}"]/imgdir[@name="info"]'
        )
        if info_xml is None or info_xml.find('./imgdir[@name="ball"]') is None:
            raise RuntimeError(f"{mob_id}: missing server ballistic {parent[0]}/info/ball")
        expected = {"type": 2, "bulletSpeed": bullet_speed}
        for name, value in expected.items():
            current = info_xml.find(f'./int[@name="{name}"]')
            if current is None:
                updated = mutate_xml(
                    updated, "add", parent, name=name, kind="Int", values={"value": value}
                )
                root = ET.fromstring(updated)
                info_xml = root.find(
                    f'./imgdir[@name="attack{attack_number}"]/imgdir[@name="info"]'
                )
            elif current.get("value") != str(value):
                raise RuntimeError(
                    f"{mob_id}: conflicting server ballistic {name}={current.get('value')}"
                )
        if updated != text:
            arc.atomic_write_text(server, updated)


def clone_quest_part(source, name: str) -> WzSubProperty:
    node = source.root.child(name)
    output = WzSubProperty("quest")
    if node is not None:
        materializer = arc.CanvasMaterializer()
        for child in node.children():
            output.add(arc.clone_property(child, output, source, source.source_path, materializer))
    return output


def prune_quest(quest_id: int, part: str, root: WzSubProperty) -> None:
    if part == "QuestInfo":
        for child in list(root.children()):
            if child.name not in QUEST_INFO_FIELDS:
                arc.remove_child(root, child.name)
        return
    if part == "Check":
        for phase in root.children():
            for field in ("startscript", "endscript", "start", "subJobFlags",
                          "notInTeleportItemLimitedField", "normalAutoStart",
                          "completeNpcAutoGuide"):
                arc.remove_child(phase, field)
            if phase.name == "0":
                if phase.child("lvmin") is not None:
                    arc.set_int(phase, "lvmin", 200)
                quests = phase.child("quest")
                if isinstance(quests, WzSubProperty):
                    for entry in list(quests.children()):
                        required = int(child_value(entry, "id") or 0)
                        if required not in QUEST_IDS:
                            arc.remove_child(quests, entry.name)
                    dense_numeric_children(quests)
            mobs = phase.child("mob")
            if isinstance(mobs, WzSubProperty):
                for entry in list(mobs.children()):
                    mob_id = int(child_value(entry, "id") or 0)
                    if 8880000 <= mob_id < 8890000:
                        arc.remove_child(mobs, entry.name)
                    elif mob_id in {9101234, 9101251}:
                        arc.set_int(entry, "id", 8645290)
                    elif mob_id == 9101235:
                        arc.set_int(entry, "id", 8645365)
                dense_numeric_children(mobs)


def quest_node(source_path: Path, quest_id: int, part: str) -> ET.Element:
    source = arc.load_image(source_path, arc.BMS_KEY)
    source.source_path = source_path
    projected = clone_quest_part(source, part)
    prune_quest(quest_id, part, projected)
    wrapper = ET.fromstring(arc.image_to_xml(type("Image", (), {"root": projected})(), str(quest_id)))
    wrapper.set("name", str(quest_id))
    return wrapper


def signed_quest_id(quest_id: int) -> int:
    return quest_id - 65536 if quest_id >= 32768 else quest_id


def migrate_quests() -> None:
    sys.path.insert(0, str(ROOT / "tool/resource-workbench"))
    from quest_manager import app as qm
    for quest_id in sorted(QUEST_IDS):
        source_path = SOURCE / f"Quest/QuestData/{quest_id}.img"
        for part in ("QuestInfo", "Check", "Act", "Say"):
            node = quest_node(source_path, quest_id, part)
            client = ROOT / f"clien/Data/Quest/{part}.img"
            before = client.read_bytes()
            after = qm._replace_img_record(before, str(quest_id), node)
            if after != before:
                arc.atomic_write_bytes(client, after)
            for tree in ("wz", "wz-zh-CN"):
                path = ROOT / f"gms-server/{tree}/Quest.wz/{part}.img.xml"
                server_node = copy.deepcopy(node)
                server_node.set("name", str(signed_quest_id(quest_id)))
                before_xml = path.read_bytes()
                after_xml = qm._replace_xml_record(
                    before_xml, str(signed_quest_id(quest_id)), server_node
                )
                if after_xml != before_xml:
                    arc.atomic_write_bytes(path, after_xml)


def main() -> int:
    configure_arcane_helpers()
    install_npcs(EXPLICIT_NPCS)
    install_nohime_entry()
    dependencies = migrate_maps()
    install_npcs({npc for npc in dependencies["npcs"] if str(npc).startswith("300")})
    arc.migrate_map_assets(dependencies)
    arc.merge_map_marks(dependencies["marks"])
    arc.migrate_bgms(dependencies["bgms"])
    migrate_mobs()
    repair_nohime_scene_skills()
    repair_nohime_ballistics()
    migrate_map_strings()
    upsert_strings("Mob", MOB_IDS)
    upsert_strings("Npc", EXPLICIT_NPCS | {npc for npc in dependencies["npcs"] if str(npc).startswith("300")})
    migrate_items()
    migrate_quests()
    print(f"installed {len(MAP_IDS)} maps, {len(MOB_IDS)} mobs, {len(QUEST_IDS)} quests")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--repair-commerci-ships"]:
        repair_commerci_ship_visibility()
        print(f"repaired {len(COMMERCI_SOLO_VOYAGE_MAPS)} Commerci ship objects")
        raise SystemExit(0)
    if sys.argv[1:] == ["--repair-nohime-ballistics"]:
        repair_nohime_ballistics()
        print(f"repaired {len(NOHIME_BALLISTIC_ATTACKS)} Princess No ballistic attacks")
        raise SystemExit(0)
    if sys.argv[1:] == ["--repair-nohime-scene-skills"]:
        repair_nohime_scene_skills()
        print("repaired Princess No scene skill triggers")
        raise SystemExit(0)
    raise SystemExit(main())
