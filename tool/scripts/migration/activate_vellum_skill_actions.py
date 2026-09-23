#!/usr/bin/env python3
"""Activate Vellum's projected skills without rewriting existing IMG trees."""

from __future__ import annotations

import hashlib
import io
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data/Mob/_Canvas/8930000.img")
MOB_IMG = ROOT / "clien/Data/Mob/8930000.img"
MOB_XML = ROOT / "gms-server/wz/Mob.wz/8930000.img.xml"
SKILL_IMG = ROOT / "clien/Data/Skill/MobSkill.img"
SKILL_XML = ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml"
ALIASES = (("attack2", "skill4"), ("attack6", "skill5"),
           ("attack12", "skill6"), ("attack13", "skill7"))
LEVELS = (251, 252, 253, 254, 255)
INTERVALS = (12, 14, 18, 16, 18, 16)
ROWS = tuple((200, level) for level in LEVELS) + ((100, 30),)

sys.path.insert(0, str(ROOT / "tool/resource-workbench"))

from map_mob import app  # noqa: E402
from wzpy import WzCanvasProperty, WzIntProperty, WzStringProperty, WzSubProperty, WzUolProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.canvas import _read_canvas_bytes  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402


def record(name: str, fields: dict[str, int | str]) -> WzSubProperty:
    node = WzSubProperty(name)
    for field, value in fields.items():
        node.add(WzStringProperty(field, value) if isinstance(value, str)
                 else WzIntProperty(field, value))
    return node


def alias_node(old: str, name: str) -> WzSubProperty:
    source = app.companion_logical_node(SOURCE, old)
    if not isinstance(source, WzSubProperty):
        raise RuntimeError(f"missing TMS action: {old}")
    node = app.clone_supported_node(source)
    node.name = name

    def remap(parent: WzSubProperty) -> None:
        for child in parent.children():
            if isinstance(child, WzUolProperty):
                parts = str(child.value).replace("\\", "/").split("/")
                child._value = "/".join("attack5" if part == "attack7" else part for part in parts)
            elif isinstance(child, WzSubProperty):
                remap(child)

    remap(node)
    return node


def skill_row(index: int) -> WzSubProperty:
    kind, level = ROWS[index - 1]
    return record(str(index), {"skill": kind, "action": index + 1, "level": level})


def client_summon(level: int, interval: int) -> WzSubProperty:
    # The target exists in the old client; matching server skills have no
    # summon IDs, so this is an AI selection cue rather than a new spawn.
    return record(str(level), {"info": "Vellum", "hp": 100, "interval": interval,
                               "limit": 1, "0": 8930001})


def server_skill(level: int, interval: int) -> WzSubProperty:
    return record(str(level), {"hp": 100, "interval": interval})


def legacy_buff(image) -> WzSubProperty:
    source = image.root.get("100/level/1")
    if not isinstance(source, WzSubProperty):
        raise RuntimeError("missing working legacy buff template")
    node = WzSubProperty("30")
    for child in source.children():
        if isinstance(child, WzSubProperty) and child.name in {"effect", "mob"}:
            branch = WzSubProperty(child.name)
            for frame in child.children():
                if isinstance(frame, WzCanvasProperty):
                    clone = WzCanvasProperty(frame.name)
                    clone.width, clone.height = frame.width, frame.height
                    clone.format, clone.format2 = frame.format, frame.format2
                    clone._png_data = _read_canvas_bytes(frame)
                    clone._png_length = len(clone._png_data)
                    for meta in frame.children():
                        clone.add(app.clone_supported_node(meta))
                    branch.add(clone)
                else:
                    branch.add(app.clone_supported_node(frame))
            node.add(branch)
        else:
            node.add(app.clone_supported_node(child))
    overrides = {"x": 0, "mpCon": 0, "time": 1, "interval": INTERVALS[-1]}
    for field, value in overrides.items():
        node.child(field)._value = value
    node.add(WzIntProperty("hp", 100))
    return node


def record_spans(layout) -> dict[tuple[str, ...], tuple[int, int]]:
    spans: dict[tuple[str, ...], tuple[int, int]] = {}

    def visit(prop_list, parent: tuple[str, ...] = ()) -> None:
        for item in prop_list.records:
            path = (*parent, item.name)
            spans[path] = (item.start, item.end)
            if item.children is not None:
                visit(item.children, path)

    visit(layout.root)
    return spans


def audit_insert(before: bytes, after: bytes, path: tuple[str, ...], refs, layout) -> None:
    previous, old_orders = app.arc.raw_record_state(before)
    current, new_orders = app.arc.raw_record_state(after)
    spans = record_spans(layout)
    added = set(current) - set(previous)
    if set(previous) - set(current) or any(item[:len(path)] != path for item in added):
        raise RuntimeError(f"unapproved IMG record addition/removal: {path}")
    for parent, names in old_orders.items():
        now = new_orders.get(parent)
        if now is None or tuple(name for name in now if name in names) != names:
            raise RuntimeError(f"IMG sibling order changed: {parent}")
    for item, raw in previous.items():
        if item == path or item[:len(path)] == path or path[:len(item)] == item:
            continue
        start, end = spans[item]
        expected = bytearray(raw)
        for ref_start, ref_end, replacement in refs:
            if start <= ref_start and ref_end <= end:
                expected[ref_start - start:ref_end - start] = replacement
        if current[item] != expected:
            raise RuntimeError(f"non-reference IMG bytes changed: {item}")


def append_img(data: bytes, parent: tuple[str, ...], prop, *, stats: list[int]) -> bytes:
    arc = app.arc
    layout = arc.scan_img(data, region="GMS")
    prop_list, ancestors = arc._find_list(layout.root, parent)
    if any(item.name == prop.name for item in prop_list.records):
        raise RuntimeError(f"duplicate IMG path: {parent}/{prop.name}")
    reader = WzBinaryReader(io.BytesIO(data), arc.GMS_KEY)
    encoded = arc._record_bytes(prop, reader)
    count = arc._count_edit(prop_list, prop_list.count + 1)
    delta = len(encoded) + len(count[2]) - (count[1] - count[0])
    edits = [(prop_list.end, prop_list.end, encoded), count, *arc._size_edits(ancestors, delta)]
    refs = arc._reference_edits(layout, edits)
    output = arc.verified_image_bytes(arc._apply_edits(data, [*edits, *refs]), prop.name)
    audit_insert(data, output, (*parent, prop.name), refs, layout)
    stats.append(len(refs))
    return output


def audit_xml_insert(before: bytes, after: bytes, roots: tuple[str, ...]) -> None:
    old, new = app.index_xml(before), app.index_xml(after)
    if set(old) - set(new) or any(not any(
            path == root or path.startswith(root + "/")
            for root in roots) for path in set(new) - set(old)):
        raise RuntimeError("unapproved XML node addition/removal")
    for path, span in old.items():
        if not path or any(root.startswith(path + "/") or root == path for root in roots):
            continue
        current = new[path]
        if before[span.start:span.end] != after[current.start:current.end]:
            raise RuntimeError(f"protected XML node changed: {path}")


def validate_mob(data: bytes) -> None:
    image = app._verified_img_from_bytes(MOB_IMG, data)
    attacks = tuple(child.name for child in image.root.children()
                    if re.fullmatch(r"attack\d+", child.name))
    if attacks != tuple(f"attack{i}" for i in range(1, 9)):
        raise RuntimeError(f"Vellum attack count changed: {attacks}")
    rows = image.root.get("info/skill")
    if [(int(row.child("skill").value), int(row.child("action").value),
         int(row.child("level").value)) for row in rows.children()[1:]] != [
             (kind, index + 1, level) for index, (kind, level) in enumerate(ROWS, 1)]:
        raise RuntimeError("Vellum client skill table mismatch")
    for index in range(1, 8):
        if not isinstance(image.root.get(f"skill{index}"), WzSubProperty):
            raise RuntimeError(f"missing Vellum skill{index}")

    def visit(parent: WzSubProperty, path: tuple[str, ...] = ()) -> None:
        for child in parent.children():
            child_path = (*path, child.name)
            if isinstance(child, WzUolProperty):
                target = app.resolve_uol_absolute("/".join(child_path), str(child.value))
                if image.root.get(target) is None:
                    raise RuntimeError(f"broken Vellum UOL: {'/'.join(child_path)} -> {target}")
            if isinstance(child, WzSubProperty):
                visit(child, child_path)

    visit(image.root)


def mob_img(data: bytes, stats: list[int]) -> bytes:
    image = app._verified_img_from_bytes(MOB_IMG, data)
    if image.root.get("skill7") is not None:
        validate_mob(data)
        return data
    if image.root.get("skill4") is not None or len(image.root.get("info/skill").children()) != 1:
        raise RuntimeError("partial Vellum skill migration")
    output = data
    for old, new in ALIASES:
        output = append_img(output, (), alias_node(old, new), stats=stats)
    for index in range(1, 7):
        output = append_img(output, ("info", "skill"), skill_row(index), stats=stats)
    validate_mob(output)
    return output


def mob_xml(data: bytes) -> bytes:
    root = ET.fromstring(data)
    if root.find('./imgdir[@name="skill7"]') is not None:
        validate_mob_xml(data)
        return data
    text = data.decode("utf-8")
    text = app.arc.append_xml_properties(text, ("info", "skill"), [skill_row(i) for i in range(1, 7)])
    text = app.arc.append_xml_properties(text, (), [alias_node(old, name) for old, name in ALIASES])
    result = text.encode("utf-8")
    validate_mob_xml(result)
    audit_xml_insert(data, result, tuple(f"info/skill/{i}" for i in range(1, 7))
                     + tuple(name for _, name in ALIASES))
    return result


def validate_mob_xml(data: bytes) -> None:
    root = ET.fromstring(data)
    rows = root.find('./imgdir[@name="info"]/imgdir[@name="skill"]')
    if [(int(row.find('./int[@name="skill"]').get("value")),
         int(row.find('./int[@name="action"]').get("value")),
         int(row.find('./int[@name="level"]').get("value"))) for row in list(rows)[1:]] != [
             (kind, index + 1, level) for index, (kind, level) in enumerate(ROWS, 1)]:
        raise RuntimeError("server Vellum skill table mismatch")
    if [node.get("name") for node in root if re.fullmatch(r"attack\d+", node.get("name", ""))] != [
            f"attack{i}" for i in range(1, 9)]:
        raise RuntimeError("server Vellum attack count changed")
    if any(root.find(f'./imgdir[@name="skill{i}"]') is None for i in range(1, 8)):
        raise RuntimeError("server Vellum skill action missing")


def validate_skill(data: bytes) -> None:
    image = app._verified_img_from_bytes(SKILL_IMG, data)
    for level in (239, *LEVELS):
        node = image.root.get(f"200/level/{level}")
        if int(node.child("limit").value) != 1 or int(node.child("0").value) != 8930001:
            raise RuntimeError(f"client MobSkill 200/{level} invalid")
    action = image.root.get("100/level/30")
    if not isinstance(action, WzSubProperty) or int(action.child("interval").value) != INTERVALS[-1]:
        raise RuntimeError("client MobSkill 100/30 missing")
    for branch in ("effect", "mob"):
        for frame in action.child(branch).children():
            if isinstance(frame, WzCanvasProperty):
                if (frame.format, frame.format2) != (1, 0) or not decode_canvas(frame, region="GMS").convert("RGBA").getbbox():
                    raise RuntimeError(f"client 100/30/{branch}/{frame.name} invalid Canvas")


def skill_img(data: bytes, stats: list[int]) -> bytes:
    image = app._verified_img_from_bytes(SKILL_IMG, data)
    if image.root.get("100/level/30") is not None:
        validate_skill(data)
        return data
    if image.root.get("200/level/251") is not None or image.root.get("200/level/239/limit") is not None:
        raise RuntimeError("partial MobSkill projection")
    output = data
    for field, value in (("limit", 1), ("0", 8930001)):
        output = append_img(output, ("200", "level", "239"), WzIntProperty(field, value), stats=stats)
    for level, interval in zip(LEVELS, INTERVALS):
        output = append_img(output, ("200", "level"), client_summon(level, interval), stats=stats)
    output = append_img(output, ("100", "level"), legacy_buff(image), stats=stats)
    validate_skill(output)
    return output


def skill_xml(data: bytes) -> bytes:
    root = ET.fromstring(data)
    if root.find('./imgdir[@name="100"]/imgdir[@name="level"]/imgdir[@name="30"]') is not None:
        validate_skill_xml(data)
        return data
    text = app.arc.append_xml_properties(
        data.decode("utf-8"), ("200", "level"),
        [server_skill(level, interval) for level, interval in zip(LEVELS, INTERVALS)],
    )
    text = app.arc.append_xml_properties(text, ("100", "level"),
                                         [server_skill(30, INTERVALS[-1])])
    result = text.encode("utf-8")
    validate_skill_xml(result)
    audit_xml_insert(data, result, tuple(f"200/level/{level}" for level in LEVELS)
                     + ("100/level/30",))
    return result


def validate_skill_xml(data: bytes) -> None:
    root = ET.fromstring(data)
    for (kind, level), interval in zip(ROWS, INTERVALS):
        path = f'./imgdir[@name="{kind}"]/imgdir[@name="level"]/imgdir[@name="{level}"]'
        node = root.find(path)
        if node is None or node.find('./int[@name="0"]') is not None:
            raise RuntimeError(f"server visual skill {kind}/{level} could summon")
        if int(node.find('./int[@name="interval"]').get("value")) != interval:
            raise RuntimeError(f"server visual skill {kind}/{level} interval mismatch")


TARGETS = ((MOB_IMG, mob_img), (MOB_XML, mob_xml),
           (SKILL_IMG, skill_img), (SKILL_XML, skill_xml))
BASELINE_SHA256 = {
    MOB_IMG: "ef07db5d532f22aa67659a0c1a04c5085517e9f1c2b1cd6014d232a980118ae3",
    MOB_XML: "aceee0a0af1abcfd8782800a841f58426e98b6f7ff6667657ddb7bc7c39b5bc6",
    SKILL_IMG: "e8cdccd68257e1d17ba5d9a8d4bd4b657e78b2b1444d33e3d586c2827e02eac7",
    SKILL_XML: "c4dcc389b7bf55cd7e033953a2f9aaea444e40808da5388b66ed6e12c0524984",
}


def migrate() -> dict[str, str]:
    originals = {path: path.read_bytes() for path, _ in TARGETS}
    hashes = {path: hashlib.sha256(data).hexdigest() for path, data in originals.items()}
    if any(hashes[path] != baseline for path, baseline in BASELINE_SHA256.items()):
        for path, transform in TARGETS:
            if (transform(originals[path], []) if path.suffix == ".img"
                    else transform(originals[path])) != originals[path]:
                raise RuntimeError(f"unexpected Vellum baseline: {path}")
        return {str(path.relative_to(ROOT)): hashes[path] for path, _ in TARGETS}
    reference_edits: list[int] = []
    outputs = {
        MOB_IMG: mob_img(originals[MOB_IMG], reference_edits),
        MOB_XML: mob_xml(originals[MOB_XML]),
        SKILL_IMG: skill_img(originals[SKILL_IMG], reference_edits),
        SKILL_XML: skill_xml(originals[SKILL_XML]),
    }
    for path, transform in TARGETS:
        if (transform(outputs[path], []) if path.suffix == ".img" else transform(outputs[path])) != outputs[path]:
            raise RuntimeError(f"generator not idempotent: {path}")
    written: list[Path] = []
    try:
        for path, _ in TARGETS:
            if originals[path] != outputs[path]:
                app.atomic_write(path, outputs[path], backup=False)
                written.append(path)
        app._load_image_cached.cache_clear()
        for path, transform in TARGETS:
            data = path.read_bytes()
            if (transform(data, []) if path.suffix == ".img" else transform(data)) != data:
                raise RuntimeError(f"persisted artifact invalid: {path}")
    except Exception:
        for path in reversed(written):
            app.atomic_write(path, originals[path], backup=False)
        app._load_image_cached.cache_clear()
        raise
    print("reference offsets updated:", reference_edits)
    return {str(path.relative_to(ROOT)): hashlib.sha256(outputs[path]).hexdigest() for path, _ in TARGETS}


if __name__ == "__main__":
    print(migrate())
