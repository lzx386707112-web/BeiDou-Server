#!/usr/bin/env python3
"""Install Damien's complete TMS attack/skill set on the proven safe baseline."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_demian as demian  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzIntProperty, WzSubProperty, WzUolProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.incremental_img import replace_img_record  # noqa: E402

WORKING_BASELINE = Path("/private/tmp/damien-boss-skills-20260911/baseline")
SHARED_BASELINE = Path("/private/tmp/damien-full-tms-20260911/baseline")
TMS_MOB_CACHE = Path("/private/tmp/arcane-river-mob-cache")
TMS_MOB_SKILLS = Path("/private/tmp/damien-boss-skills-20260911/tms")
CLIENT_MOB_SKILL = ROOT / "clien/Data/Skill/MobSkill.img"
SERVER_MOB_SKILL = ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml"

ATTACKS_BY_MOB = {
    8880110: tuple(f"attack{index}" for index in range(1, 7)),
    8880111: tuple(f"attack{index}" for index in range(1, 8)),
}
SKILL_ACTIONS_BY_MOB = {
    8880110: tuple(f"skill{index}" for index in range(1, 5)),
    8880111: tuple(f"skill{index}" for index in range(1, 11)),
}
# Extra 170/201/214/215 levels crash the old client during combat.
MOB_SKILL_LEVELS = {}
DEPENDENCY_MOBS = (8880100, 8880101, 8880102)
BALLISTIC_P1_ATTACK = "attack2"
BALLISTIC_SOURCE = (8880111, "attack3")
STRIP_RANGE_FIELDS = {"start", "areaCount", "attackCount"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tms_mob_path(mob_id: int) -> Path:
    return TMS_MOB_CACHE / str(mob_id) / f"Mob_{mob_id}.img"


def restore_working_baseline() -> None:
    required = [
        *(WORKING_BASELINE / f"{mob_id}.img" for mob_id in demian.BOSS_IDS),
        *(WORKING_BASELINE / f"{mob_id}.img.xml" for mob_id in demian.BOSS_IDS),
        SHARED_BASELINE / "MobSkill.img",
        SHARED_BASELINE / "MobSkill.img.xml",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing Damien working baseline: {missing}")
    for mob_id in demian.BOSS_IDS:
        arc.atomic_write_bytes(
            demian.client_mob_path(mob_id),
            (WORKING_BASELINE / f"{mob_id}.img").read_bytes(),
        )
        arc.atomic_write_text(
            demian.server_mob_path("wz", mob_id),
            (WORKING_BASELINE / f"{mob_id}.img.xml").read_text(encoding="utf-8"),
        )
    arc.atomic_write_bytes(CLIENT_MOB_SKILL, (SHARED_BASELINE / "MobSkill.img").read_bytes())
    arc.atomic_write_text(
        SERVER_MOB_SKILL,
        (SHARED_BASELINE / "MobSkill.img.xml").read_text(encoding="utf-8"),
    )


def clone_child(source, parent, image, image_path, materializer, *, name=None):
    cloned = arc.clone_property(source, parent, image, image_path, materializer, name=name)
    if parent is not None:
        cloned.parent = parent
    return cloned


def build_attack(mob_id, action_name, image, image_path, materializer, linked_image, linked_path):
    source = image.root.child(action_name)
    if not isinstance(source, WzSubProperty):
        raise RuntimeError(f"TMS {mob_id} missing {action_name}")
    source_info = source.child("info")
    if not isinstance(source_info, WzSubProperty):
        raise RuntimeError(f"TMS {mob_id}/{action_name} missing info")

    action = WzSubProperty(action_name)
    info = WzSubProperty("info", action)
    action.add(info)
    for name in ("range", "ball", "hit"):
        child = source_info.child(name)
        child_image, child_path = image, image_path
        if mob_id == 8880110 and action_name == BALLISTIC_P1_ATTACK and name == "ball":
            child = linked_image.root.get(f"{BALLISTIC_SOURCE[1]}/info/ball")
            child_image, child_path = linked_image, linked_path
        if child is not None:
            info.add(clone_child(child, info, child_image, child_path, materializer, name=name))

    attack_after = source_info.child("attackAfter")
    attack_after_value = int(attack_after.value) if attack_after is not None else 0
    if mob_id == 8880110 and action_name == BALLISTIC_P1_ATTACK:
        attack_after_value = 480
    ball = info.child("ball")
    hit = info.child("hit")
    if isinstance(ball, WzSubProperty):
        modern = image.root.get(f"info/attack/{int(action_name.removeprefix('attack')) - 1}")
        bullet_speed = int(arc.child_value(modern, "bulletSpeed") or 0)
        if mob_id == 8880110 and action_name == BALLISTIC_P1_ATTACK:
            bullet_speed = int(arc.child_value(linked_image.root.get("info/attack/2"), "bulletSpeed") or 220)
        info.add(WzIntProperty("type", 2, info))
        info.add(WzIntProperty("attackAfter", attack_after_value, info))
        info.add(WzIntProperty("bulletSpeed", bullet_speed or 220, info))
        if isinstance(hit, WzSubProperty) and hit.child("attach") is None:
            hit.add(WzIntProperty("attach", 1, hit))
    else:
        info.add(WzIntProperty("attackAfter", attack_after_value, info))
        if isinstance(hit, WzSubProperty):
            arc.remove_child(hit, "attach")

    attack_range = info.child("range")
    if isinstance(attack_range, WzSubProperty):
        for name in STRIP_RANGE_FIELDS:
            arc.remove_child(attack_range, name)
    for child in source.children():
        if child.name.isdigit():
            action.add(clone_child(child, action, image, image_path, materializer))
    return action


def materialize_missing_followups(action, source, image, image_path, materializer) -> None:
    for child in source.children():
        if not isinstance(child, WzUolProperty) or "skillAfter" not in str(child.value):
            continue
        target = child.parent.get(str(child.value)) if child.parent is not None else None
        if not isinstance(target, WzCanvasProperty):
            raise RuntimeError(f"unresolved follow-up UOL {source.name}/{child.name}: {child.value}")
        replacement = clone_child(target, action, image, image_path, materializer, name=child.name)
        action._children = {
            name: replacement if name == child.name else existing
            for name, existing in action._children.items()
        }


def build_boss_projection(mob_id: int) -> dict[str, WzSubProperty]:
    image_path = tms_mob_path(mob_id)
    image = arc.load_image(image_path, arc.BMS_KEY)
    linked_path = tms_mob_path(BALLISTIC_SOURCE[0])
    linked_image = arc.load_image(linked_path, arc.BMS_KEY)
    materializer = arc.CanvasMaterializer()
    result = {}

    stand = image.root.child("stand")
    if not isinstance(stand, WzSubProperty):
        raise RuntimeError(f"TMS {mob_id} missing stand")
    result["move"] = clone_child(stand, None, image, image_path, materializer, name="move")
    for name in ATTACKS_BY_MOB[mob_id]:
        result[name] = build_attack(
            mob_id, name, image, image_path, materializer, linked_image, linked_path
        )
    for name in SKILL_ACTIONS_BY_MOB[mob_id]:
        source = image.root.child(name)
        if not isinstance(source, WzSubProperty):
            raise RuntimeError(f"TMS {mob_id} missing {name}")
        action = clone_child(source, None, image, image_path, materializer)
        materialize_missing_followups(action, source, image, image_path, materializer)
        result[name] = action
    table = image.root.get("info/skill")
    if not isinstance(table, WzSubProperty):
        raise RuntimeError(f"TMS {mob_id} missing info/skill")
    result["skill"] = clone_child(table, None, image, image_path, materializer)
    if materializer.resized:
        raise RuntimeError(f"TMS {mob_id} projection resized {materializer.resized} canvases")
    return result


def verify_outside(before: bytes, after: bytes, allowed: set[tuple[str, ...]]) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)

    def affected(path):
        return any(path[: len(root)] == root or root[: len(path)] == path for root in allowed)

    for path, raw in before_records.items():
        if not affected(path) and after_records.get(path) != raw:
            raise RuntimeError(f"protected IMG record changed: {'/'.join(path)}")
    for path in after_records:
        if path not in before_records and not affected(path):
            raise RuntimeError(f"unapproved IMG record added: {'/'.join(path)}")
    for parent, names in before_orders.items():
        if affected(parent):
            continue
        current = after_orders.get(parent)
        if current is None:
            raise RuntimeError(f"protected IMG parent removed: {'/'.join(parent)}")
        common = set(names).intersection(current)
        if tuple(name for name in names if name in common) != tuple(name for name in current if name in common):
            raise RuntimeError(f"protected IMG sibling order changed: {'/'.join(parent)}")


def replace_or_insert_img(data, name, node, before_name):
    records, _ = arc.raw_record_state(data)
    if (name,) in records:
        updated = replace_img_record(data, (name,), node, region="GMS").data
        verify_outside(data, updated, {(name,)})
        return updated
    updated = arc.insert_property_record_before(data, (), node, before_name)
    arc.verify_raw_record_insert_scope(data, updated, {(name,)})
    return updated


def resolve_uol(node: WzUolProperty):
    current = node
    seen = set()
    for _ in range(64):
        if not isinstance(current, WzUolProperty):
            return current
        if id(current) in seen or current.parent is None:
            return None
        seen.add(id(current))
        current = current.parent.get(str(current.value))
    return None


def validate_client_boss(mob_id: int, data: bytes) -> None:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=f"{mob_id}.img")
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{mob_id}.img parse failed: {image.parse_warnings}")
    roots = tuple(child.name for child in image.root.children())
    if roots != demian.LEGACY_BOSS_TOP_LEVEL_BY_MOB[mob_id]:
        raise RuntimeError(f"{mob_id}.img root order {roots}")
    table = image.root.get("info/skill")
    actual_table = [
        {entry.name: int(entry.value) for entry in child.children()}
        for child in table.children()
    ]
    if actual_table != list(demian.SKILLS_BY_MOB[mob_id]):
        raise RuntimeError(f"{mob_id}.img skill table does not match TMS")
    for action_name in ("move", *ATTACKS_BY_MOB[mob_id], *SKILL_ACTIONS_BY_MOB[mob_id]):
        action = image.root.child(action_name)
        if not isinstance(action, WzSubProperty):
            raise RuntimeError(f"{mob_id}.img missing {action_name}")
        visible = 0
        seen_canvases = set()
        for node, path in arc.walk(action):
            target = resolve_uol(node) if isinstance(node, WzUolProperty) else node
            if isinstance(node, WzUolProperty) and not isinstance(target, WzCanvasProperty):
                raise RuntimeError(f"{mob_id}/{action_name}/{path} unresolved UOL")
            if not isinstance(target, WzCanvasProperty) or id(target) in seen_canvases:
                continue
            seen_canvases.add(id(target))
            if (int(target.format), int(target.format2)) != (1, 0):
                raise RuntimeError(f"{mob_id}/{action_name}/{path} is not ARGB4444")
            if max(int(target.width), int(target.height)) > arc.MAX_CANVAS_EDGE:
                raise RuntimeError(f"{mob_id}/{action_name}/{path} exceeds 2048")
            decoded = decode_canvas(target, region="GMS").convert("RGBA")
            visible += decoded.getbbox() is not None
            decoded.close()
        if visible == 0:
            raise RuntimeError(f"{mob_id}/{action_name} has no visible frames")


def patch_client_boss(mob_id: int, projection) -> None:
    path = demian.client_mob_path(mob_id)
    original = path.read_bytes()
    patched = replace_or_insert_img(original, "move", projection["move"], "attack1")
    for name in ATTACKS_BY_MOB[mob_id]:
        patched = replace_or_insert_img(patched, name, projection[name], "skill1")
    for name in SKILL_ACTIONS_BY_MOB[mob_id]:
        patched = replace_or_insert_img(patched, name, projection[name], "hit1")
    replaced = replace_img_record(patched, ("info", "skill"), projection["skill"], region="GMS").data
    verify_outside(patched, replaced, {("info", "skill")})
    patched = replaced
    allowed = {
        ("info", "skill"), ("move",),
        *((name,) for name in ATTACKS_BY_MOB[mob_id]),
        *((name,) for name in SKILL_ACTIONS_BY_MOB[mob_id]),
    }
    verify_outside(original, patched, allowed)
    validate_client_boss(mob_id, patched)
    arc.atomic_write_bytes(path, patched)


def find_xml_node(text, path):
    current = arc.scan_xml(text)
    for part in path:
        matches = [child for child in current.children if child.name == part]
        if len(matches) != 1:
            return None
        current = matches[0]
    return current


def replace_xml_node(text, path, node, before_name=None):
    current = find_xml_node(text, path)
    if current is None:
        if before_name is not None:
            return arc.insert_xml_properties_before(text, path[:-1], [node], before_name)
        return arc.append_xml_properties(text, path[:-1], [node])
    line_start = text.rfind("\n", 0, current.start) + 1
    indent = text[line_start:current.start]
    if indent.strip():
        line_start = current.start
        indent = ""
    fragment = arc.property_to_xml(node, len(indent) // 2)
    return text[:line_start] + fragment + text[current.end:]


def xml_state(text):
    root = ET.fromstring(text)
    state = {}

    def visit(parent, prefix=()):
        for child in parent:
            name = child.get("name")
            if name is None:
                continue
            path = (*prefix, name)
            state[path] = (child.tag, tuple(sorted(child.attrib.items())))
            visit(child, path)

    visit(root)
    return state


def validate_xml_scope(before, after, allowed):
    before_state, after_state = xml_state(before), xml_state(after)

    def affected(path):
        return any(path[: len(root)] == root or root[: len(path)] == path for root in allowed)

    for path, value in before_state.items():
        if not affected(path) and after_state.get(path) != value:
            raise RuntimeError(f"protected XML node changed: {'/'.join(path)}")
    for path in after_state:
        if path not in before_state and not affected(path):
            raise RuntimeError(f"unapproved XML node added: {'/'.join(path)}")


def patch_server_boss(mob_id: int, projection) -> None:
    path = demian.server_mob_path("wz", mob_id)
    original = path.read_text(encoding="utf-8")
    updated = original
    updated = replace_xml_node(updated, ("move",), projection["move"], "attack1")
    for name in ATTACKS_BY_MOB[mob_id]:
        updated = replace_xml_node(updated, (name,), projection[name], "skill1")
    for name in SKILL_ACTIONS_BY_MOB[mob_id]:
        updated = replace_xml_node(updated, (name,), projection[name], "hit1")
    updated = replace_xml_node(updated, ("info", "skill"), projection["skill"])
    allowed = {
        ("info", "skill"), ("move",),
        *((name,) for name in ATTACKS_BY_MOB[mob_id]),
        *((name,) for name in SKILL_ACTIONS_BY_MOB[mob_id]),
    }
    ET.fromstring(updated)
    validate_xml_scope(original, updated, allowed)
    roots = tuple(child.get("name") for child in ET.fromstring(updated) if child.tag == "imgdir")
    if roots != demian.LEGACY_BOSS_TOP_LEVEL_BY_MOB[mob_id]:
        raise RuntimeError(f"{path.name} root order {roots}")
    arc.atomic_write_text(path, updated)


def clone_mob_skill_level(skill_id, level, parent, materializer):
    source_path = TMS_MOB_SKILLS / f"Skill_MobSkill_{skill_id}.img"
    image = arc.load_image(source_path, arc.BMS_KEY)
    source = image.root.get(f"level/{level}")
    if not isinstance(source, WzSubProperty):
        raise RuntimeError(f"TMS MobSkill {skill_id}/{level} missing")
    return clone_child(source, parent, image, source_path, materializer, name=str(level))


def clone_level_node(image, image_path, skill_id, level, materializer):
    source = image.root.get(f"{skill_id}/level/{level}")
    if not isinstance(source, WzSubProperty):
        raise RuntimeError(f"MobSkill {skill_id}/{level} missing")
    return clone_child(source, None, image, image_path, materializer, name=str(level))


def skill_levels(image, skill_id):
    node = image.root.get(f"{skill_id}/level")
    if not isinstance(node, WzSubProperty):
        return []
    return sorted(int(child.name) for child in node.children() if child.name.isdigit())


def assert_dense_levels(image, skill_id, expected_max):
    levels = skill_levels(image, skill_id)
    if levels != list(range(1, expected_max + 1)):
        raise RuntimeError(f"MobSkill {skill_id} levels {levels} are not 1..{expected_max}")


def append_property_records(data: bytes, parent_path: tuple[str, ...], props) -> bytes:
    props = tuple(props)
    if not props:
        return data
    names = tuple(prop.name for prop in props)
    layout = arc.scan_img(data, region="GMS")
    prop_list, ancestors = arc._find_list(layout.root, parent_path)
    existing = {record.name for record in prop_list.records}
    conflicts = existing.intersection(names)
    if conflicts:
        raise FileExistsError("/".join((*parent_path, sorted(conflicts)[0])))
    reader = arc.WzBinaryReader(arc.io.BytesIO(data), arc.GMS_KEY)
    records = b"".join(arc._record_bytes(prop, reader) for prop in props)
    count_edit = arc._count_edit(prop_list, prop_list.count + len(props))
    count_delta = len(count_edit[2]) - (count_edit[1] - count_edit[0])
    delta = len(records) + count_delta
    edits = [
        (prop_list.end, prop_list.end, records),
        count_edit,
        *arc._size_edits(ancestors, delta),
    ]
    edits.extend(arc._reference_edits(layout, edits))
    result = arc.verified_image_bytes(arc._apply_edits(data, edits), names[-1])
    arc.verify_raw_record_scope(
        data, result, {(*parent_path, name) for name in names}, allow_additions=True
    )
    return result


def verify_dense_mob_skills(image: WzImage) -> None:
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"MobSkill.img parse failed: {image.parse_warnings}")
    for skill_id, levels in MOB_SKILL_LEVELS.items():
        assert_dense_levels(image, skill_id, max(levels))
        for level in levels:
            node = image.root.get(f"{skill_id}/level/{level}")
            if not isinstance(node, WzSubProperty):
                raise RuntimeError(f"MobSkill.img missing {skill_id}/{level}")
            for canvas, canvas_path in arc.walk(node):
                if not isinstance(canvas, WzCanvasProperty):
                    continue
                if (int(canvas.format), int(canvas.format2)) != (1, 0):
                    raise RuntimeError(f"MobSkill {skill_id}/{level}/{canvas_path} format")
                decoded = decode_canvas(canvas, region="GMS").convert("RGBA")
                decoded.close()
    if image.root.get("170/level/42/etcEffect") is None:
        raise RuntimeError("MobSkill 170/42 lost etcEffect")
    if int(arc.child_value(image.root.get("201/level/182"), "0") or 0) != 8880102:
        raise RuntimeError("MobSkill 201/182 lost shadow summon")
    if image.root.get("214/level/14/succeed") is None:
        raise RuntimeError("MobSkill 214/14 lost succeed")
    if int(arc.child_value(image.root.get("215/level/2"), "x") or 0) != 8880100:
        raise RuntimeError("MobSkill 215/2 lost 8880100")
    if int(arc.child_value(image.root.get("215/level/4"), "x") or 0) != 8880101:
        raise RuntimeError("MobSkill 215/4 lost 8880101")


def patch_client_mob_skills() -> None:
    """Restore the last working client MobSkill.img (no extra 170/201/214/215)."""
    patched = subprocess.check_output(["git", "cat-file", "blob", "HEAD:clien/Data/Skill/MobSkill.img"])
    image = WzImage.from_bytes(patched, key=arc.GMS_KEY, name="MobSkill.img")
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"HEAD MobSkill.img parse failed: {image.parse_warnings}")
    if image.root.get("170/level/42") is not None or image.root.child("201") is not None:
        raise RuntimeError("HEAD MobSkill.img unexpectedly contains Damien extra levels")
    arc.atomic_write_bytes(CLIENT_MOB_SKILL, patched)


def patch_server_mob_skills() -> None:
    """Restore the last working server MobSkill XML."""
    patched = subprocess.check_output(
        ["git", "cat-file", "blob", "HEAD:gms-server/wz/Skill.wz/MobSkill.img.xml"]
    ).decode("utf-8")
    ET.fromstring(patched)
    arc.atomic_write_text(SERVER_MOB_SKILL, patched)


def install_dependency_mobs() -> None:
    for target_id, source_id in {8880100: 8880110, 8880101: 8880111}.items():
        data = demian.client_mob_path(source_id).read_bytes()
        validate_client_boss(source_id, data)
        arc.atomic_write_bytes(demian.client_mob_path(target_id), data)
        source_xml = demian.server_mob_path("wz", source_id).read_text(encoding="utf-8")
        target_xml = source_xml.replace(f'name="{source_id}.img"', f'name="{target_id}.img"', 1)
        ET.fromstring(target_xml)
        arc.atomic_write_text(demian.server_mob_path("wz", target_id), target_xml)

    source = tms_mob_path(8880102)
    image, materializer = arc.clone_image(source, lambda root: arc.sanitize_mob(root, 8880102))
    if materializer.resized:
        raise RuntimeError("8880102 shadow projection resized canvases")
    data = arc.verified_image_bytes(arc.encode_image_body(image, arc.gms_reader()), "8880102.img")
    checked = WzImage.from_bytes(data, key=arc.GMS_KEY, name="8880102.img")
    checked.parse()
    visible = 0
    for node, _ in arc.walk(checked.root):
        if isinstance(node, WzCanvasProperty):
            decoded = decode_canvas(node, region="GMS").convert("RGBA")
            visible += decoded.getbbox() is not None
            decoded.close()
    if visible == 0:
        raise RuntimeError("8880102 shadow has no visible frames")
    arc.atomic_write_bytes(demian.client_mob_path(8880102), data)
    arc.atomic_write_text(demian.server_mob_path("wz", 8880102), arc.image_to_xml(image, "8880102.img"))


def patch_all(*, restore_baseline=False) -> None:
    if restore_baseline:
        restore_working_baseline()
    for mob_id in demian.BOSS_IDS:
        projection = build_boss_projection(mob_id)
        patch_client_boss(mob_id, projection)
        patch_server_boss(mob_id, projection)
    patch_client_mob_skills()
    patch_server_mob_skills()
    install_dependency_mobs()


def output_paths():
    paths = [CLIENT_MOB_SKILL, SERVER_MOB_SKILL]
    for mob_id in (*demian.BOSS_IDS, *DEPENDENCY_MOBS):
        paths.extend((demian.client_mob_path(mob_id), demian.server_mob_path("wz", mob_id)))
    return tuple(paths)


def snapshot():
    return {str(path.relative_to(ROOT)): sha256_file(path) for path in output_paths()}


def main() -> int:
    patch_all(restore_baseline=True)
    first = snapshot()
    patch_all(restore_baseline=True)
    second = snapshot()
    if first != second:
        raise RuntimeError(f"Damien full TMS patch is not idempotent: {first} vs {second}")
    print("damien complete TMS attack/skill projection ok")
    for path, digest in first.items():
        print(f"{path} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
