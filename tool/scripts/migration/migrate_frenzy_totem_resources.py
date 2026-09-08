#!/usr/bin/env python3
"""Migrate the v79 Frenzy Totem equipment and beginner summon skill."""

from __future__ import annotations

import argparse
import hashlib
import io
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Downloads/79客户端/Data")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzKey,
    WzStringProperty,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402


ITEM_ID = 1189999
OBSOLETE_ITEM_ID = 3019999
SOURCE_EQUIP_ID = 1602008
SOURCE_SKILL_ID = "0001013"
SKILL_ID = "0001016"
SOURCE_TOTEM_VISUAL_ID = 9900000
OBSOLETE_MOB_ID = 9900005
ITEM_NAME = "轮回碑石"

SOURCE_EQUIP = SOURCE / f"Character/Weapon/0{SOURCE_EQUIP_ID}.img"
SOURCE_EQP_STRING = SOURCE / "String/Eqp.img"
SOURCE_SKILL = SOURCE / "Skill/000.img"
SOURCE_SKILL_STRING = SOURCE / "String/Skill.img"
SOURCE_TOTEM_VISUAL = SOURCE / f"Mob/{SOURCE_TOTEM_VISUAL_ID}.img"

CLIENT_EQUIP = ROOT / f"clien/Data/Character/Accessory/0{ITEM_ID}.img"
OBSOLETE_CLIENT_EQUIP = ROOT / f"clien/Data/Character/Accessory/0{OBSOLETE_ITEM_ID}.img"
CLIENT_EQP_STRING = ROOT / "clien/Data/String/Eqp.img"
CLIENT_SKILL = ROOT / "clien/Data/Skill/000.img"
CLIENT_SKILL_STRING = ROOT / "clien/Data/String/Skill.img"
CLIENT_MOB_STRING = ROOT / "clien/Data/String/Mob.img"

SERVER_EQUIP = ROOT / f"gms-server/wz/Character.wz/Accessory/0{ITEM_ID}.img.xml"
OBSOLETE_SERVER_EQUIP = ROOT / f"gms-server/wz/Character.wz/Accessory/0{OBSOLETE_ITEM_ID}.img.xml"
SERVER_SKILL = ROOT / "gms-server/wz/Skill.wz/000.img.xml"
OBSOLETE_CLIENT_MOB = ROOT / f"clien/Data/Mob/{OBSOLETE_MOB_ID}.img"
OBSOLETE_SERVER_MOB = ROOT / f"gms-server/wz/Mob.wz/{OBSOLETE_MOB_ID}.img.xml"
SERVER_EQP_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Eqp.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Eqp.img.xml",
)
SERVER_SKILL_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Skill.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Skill.img.xml",
)
SERVER_MOB_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Mob.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Mob.img.xml",
)

LEGACY_CLIENT_INSTALL = ROOT / "clien/Data/Item/Install/0301.img"
LEGACY_CLIENT_INS_STRING = ROOT / "clien/Data/String/Ins.img"
LEGACY_SERVER_INSTALL = ROOT / "gms-server/wz/Item.wz/Install/0301.img.xml"
LEGACY_SERVER_INS_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Ins.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Ins.img.xml",
)

SOURCE_SHA256 = {
    SOURCE_EQUIP: "1d682cf4982b08b39312e542f067f7b5acf5f40f7fdd448fa3a543d17909c79f",
    SOURCE_EQP_STRING: "69689c3db7ae1425e4236aa46bf60ba50ed3531b8fa2ffdd16de4c08e0574aad",
    SOURCE_SKILL: "d147b32e427a431b4ba17049849d86d286dd34ea2f084f50e9de525f822217a0",
    SOURCE_SKILL_STRING: "810ddfa42468e6d586e814502c8a244bbd14567af95f4b28c491ae1e04d3b4b7",
    SOURCE_TOTEM_VISUAL: "0bbaadabd3b505b33f5c937351b0e8080619340ac39ca54ece2755a2069b06e3",
}
EMS_KEY = WzKey.for_region("EMS")
PREVIOUS_OUTPUT_SHA256 = {
    CLIENT_EQUIP: "995d72a478d93526f4ebbe5dd6016f7765020378eaaa302b71e8d8d9bce6750d",
    SERVER_EQUIP: "d932bb3cca3d0f3d8c03202989a825b080e12e91e366c04d6afd5c8c82626ef3",
    CLIENT_SKILL: "0c3f6dafa83540139a3a27deb5afb6350ac78432eb86f0aebb8e8e6c7f21604f",
    CLIENT_SKILL_STRING: "4c8b985a4143660cc9464ce4aae95279ac4cf412b6aeeadb877e63b8e4f236a0",
    SERVER_SKILL: "fae86f227c3569c433ef28b3fa6d3beaa8ea453c158f1e3fa6fa5b2d75c86627",
    SERVER_SKILL_STRINGS[0]: "29dd1fe569bb421ffb093e27ba49646636c0a17965ef02dca431a990d9a698c3",
    SERVER_SKILL_STRINGS[1]: "e9b5fdcb571f798073a78f18e8a4f26636c9fe83e10d7770c5f0dfdb2f393b12",
}
OBSOLETE_OUTPUT_SHA256 = {
    OBSOLETE_CLIENT_EQUIP: "995d72a478d93526f4ebbe5dd6016f7765020378eaaa302b71e8d8d9bce6750d",
    OBSOLETE_SERVER_EQUIP: "2e42a500c3433ead7513981d87ad59683acf224145c5eede941781bed8009e38",
    OBSOLETE_CLIENT_MOB: "5da48be88a8cf6269688329b14ec25f3fd346582abb0b5320eececa33a970fff",
    OBSOLETE_SERVER_MOB: "0213bcca33fcd9d45c35ed23d443e05e68bb62baa2dfd3e1f77fddf5fc223b63",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_baseline(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def load_image(data: bytes, key: WzKey, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=key, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"unsafe IMG {name}: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    return image


def load_source(path: Path) -> WzImage:
    data = path.read_bytes()
    if sha256(data) != SOURCE_SHA256[path]:
        raise RuntimeError(f"source hash mismatch: {path}")
    return load_image(data, EMS_KEY, path.name)


def clone_property(source, parent, name: str | None = None):
    output_name = source.name if name is None else name
    if isinstance(source, WzCanvasProperty):
        if not source.has_pixels() or source.child("_inlink") or source.child("_outlink"):
            raise RuntimeError(f"linked or empty source Canvas is unsupported: {source.name}")
        bitmap = decode_canvas(source, region="EMS").convert("RGBA")
        output = canvas_property(output_name, bitmap, parent)
        for child in source.children():
            output.add(clone_property(child, output))
        return output
    if isinstance(source, WzSubProperty):
        output = WzSubProperty(output_name, parent)
        for child in source.children():
            output.add(clone_property(child, output))
        return output
    if isinstance(source, WzVectorProperty):
        return WzVectorProperty(output_name, int(source.x), int(source.y), parent)
    if isinstance(source, WzStringProperty):
        return WzStringProperty(output_name, str(source.value), parent)
    if isinstance(source, WzIntProperty):
        return WzIntProperty(output_name, int(source.value), parent)
    raise TypeError(f"unsupported Frenzy Totem property: {type(source).__name__}")


def canvas_property(name: str, bitmap: Image.Image, parent=None) -> WzCanvasProperty:
    output = WzCanvasProperty(name, parent)
    output.width, output.height = bitmap.size
    output.format, output.format2 = 1, 0
    output._png_data = encode_canvas_payload(
        bitmap, 1, bitmap.width, bitmap.height,
        key=arc.GMS_KEY, listwz=False, zlib_level=6,
    )
    output._png_length = len(output._png_data)
    output._png_offset = 0
    return output


def target_image(source: WzImage, name: str, records) -> WzImage:
    root = WzSubProperty(name)
    for record in records:
        root.add(clone_property(record, root))
    source._root = root
    source._parsed = True
    return source


def checked_image(data: bytes, name: str) -> WzImage:
    return load_image(data, arc.GMS_KEY, name)


def visible_canvases(node) -> dict[str, tuple[int, int]]:
    output: dict[str, tuple[int, int]] = {}
    for child, path in arc.walk(node):
        if not isinstance(child, WzCanvasProperty):
            continue
        if (child.format, child.format2) != (1, 0):
            raise RuntimeError(f"incompatible Canvas {path}: {child.format}/{child.format2}")
        bitmap = decode_canvas(child, region="GMS")
        if bitmap.getbbox() is not None:
            output[path] = (bitmap.width, bitmap.height)
    return output


def replace_property_record(data: bytes, parent_path: tuple[str, ...], prop) -> bytes:
    layout = arc.scan_img(data, region="GMS")
    prop_list, ancestors = arc._find_list(layout.root, parent_path)
    matches = [record for record in prop_list.records if record.name == prop.name]
    if len(matches) != 1:
        raise RuntimeError(f"IMG record is not unique: {'/'.join((*parent_path, prop.name))}")
    target = matches[0]
    reader = WzBinaryReader(io.BytesIO(data), arc.GMS_KEY)
    replacement = arc._record_bytes(prop, reader)
    delta = len(replacement) - (target.end - target.start)
    edits = [(target.start, target.end, replacement), *arc._size_edits(ancestors, delta)]
    edits.extend(arc._reference_edits(layout, edits))
    result = arc.verified_image_bytes(arc._apply_edits(data, edits), prop.name)
    verify_replaced_subtree(data, result, (*parent_path, prop.name))
    return result


def ensure_property_record(data: bytes, parent_path: tuple[str, ...], prop) -> bytes:
    layout = arc.scan_img(data, region="GMS")
    prop_list, _ancestors = arc._find_list(layout.root, parent_path)
    matches = [record for record in prop_list.records if record.name == prop.name]
    if not matches:
        return arc.append_property_record(data, parent_path, prop)
    if len(matches) != 1:
        raise RuntimeError(f"IMG record is not unique: {'/'.join((*parent_path, prop.name))}")
    return replace_property_record(data, parent_path, prop)


def remove_property_record(data: bytes, parent_path: tuple[str, ...], name: str) -> bytes:
    layout = arc.scan_img(data, region="GMS")
    prop_list, ancestors = arc._find_list(layout.root, parent_path)
    matches = [record for record in prop_list.records if record.name == name]
    if not matches:
        return data
    if len(matches) != 1:
        raise RuntimeError(f"IMG record is not unique: {'/'.join((*parent_path, name))}")
    target = matches[0]
    count_edit = arc._count_edit(prop_list, prop_list.count - 1)
    count_delta = len(count_edit[2]) - (count_edit[1] - count_edit[0])
    delta = -(target.end - target.start) + count_delta
    edits = [
        (target.start, target.end, b""),
        count_edit,
        *arc._size_edits(ancestors, delta),
    ]
    edits.extend(arc._reference_edits(layout, edits))
    result = arc.verified_image_bytes(arc._apply_edits(data, edits), name)
    verify_removed_subtree(data, result, (*parent_path, name))
    return result


def verify_replaced_subtree(before: bytes, after: bytes, target: tuple[str, ...]) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)
    for path in (set(before_records) | set(after_records)):
        if path[:len(target)] == target:
            continue
        if path not in before_records or path not in after_records:
            raise RuntimeError(f"replacement changed an unrelated IMG path: {path}")
        if target[:len(path)] != path and before_records[path] != after_records[path]:
            raise RuntimeError(f"replacement changed an unrelated IMG record: {path}")
    for path, order in before_orders.items():
        if path[:len(target)] == target:
            continue
        if after_orders.get(path) != order:
            raise RuntimeError(f"replacement reordered IMG siblings at {path}")


def verify_removed_subtree(before: bytes, after: bytes, target: tuple[str, ...]) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)
    removed = set(before_records) - set(after_records)
    expected_removed = {path for path in before_records if path[:len(target)] == target}
    if removed != expected_removed:
        raise RuntimeError(f"IMG removal changed unexpected records: {sorted(removed)}")
    if set(after_records) - set(before_records):
        raise RuntimeError("IMG removal added records")
    for path, raw in after_records.items():
        if target[:len(path)] != path and before_records[path] != raw:
            raise RuntimeError(f"IMG removal changed an unrelated record: {path}")
    for path, order in before_orders.items():
        if path[:len(target)] == target:
            continue
        expected = tuple(child for child in order if (*path, child) != target)
        if after_orders.get(path) != expected:
            raise RuntimeError(f"IMG removal reordered siblings at {path}")


def replace_xml_record(text: str, parent_path: tuple[str, ...], prop) -> str:
    root = arc.scan_xml(text)
    current = root
    for part in parent_path:
        matches = [child for child in current.children if child.name == part]
        if len(matches) != 1:
            raise RuntimeError(f"XML path is not unique: {'/'.join(parent_path)}")
        current = matches[0]
    matches = [child for child in current.children if child.name == prop.name]
    if len(matches) != 1:
        raise RuntimeError(f"XML record is not unique: {prop.name}")
    target = matches[0]
    line_start = text.rfind("\n", 0, target.start) + 1
    indent = text[line_start:target.start]
    if indent.strip():
        indent = ""
        replace_start = target.start
    else:
        replace_start = line_start
    replacement = arc.property_to_xml(prop, len(indent) // 2)
    suffix = text[target.end:]
    suffix_line_end = suffix.find("\n")
    if suffix_line_end >= 0:
        suffix = (suffix[:suffix_line_end].rstrip(" \t")
                  + suffix[suffix_line_end:])
    result = text[:replace_start] + replacement + suffix
    ET.fromstring(result)
    return result


def find_xml_record(text: str, parent_path: tuple[str, ...], name: str):
    current = arc.scan_xml(text)
    for part in parent_path:
        matches = [child for child in current.children if child.name == part]
        if len(matches) != 1:
            raise RuntimeError(f"XML path is not unique: {'/'.join(parent_path)}")
        current = matches[0]
    matches = [child for child in current.children if child.name == name]
    if len(matches) > 1:
        raise RuntimeError(f"XML record is not unique: {name}")
    return matches[0] if matches else None


def xml_semantic(node: ET.Element):
    return (
        node.tag,
        tuple(sorted(node.attrib.items())),
        tuple(xml_semantic(child) for child in node),
    )


def ensure_xml_record(text: str, parent_path: tuple[str, ...], prop) -> str:
    target = find_xml_record(text, parent_path, prop.name)
    if target is None:
        return arc.append_xml_properties(text, parent_path, [prop])
    current = ET.fromstring(text[target.start:target.end])
    expected = ET.fromstring(arc.property_to_xml(prop, 0))
    if xml_semantic(current) == xml_semantic(expected):
        return text
    return replace_xml_record(text, parent_path, prop)


def remove_xml_record(text: str, parent_path: tuple[str, ...], name: str) -> str:
    target = find_xml_record(text, parent_path, name)
    if target is None:
        return text

    start = target.start
    end = target.end
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end < 0:
        line_end = len(text)

    if not text[line_start:start].strip() and not text[end:line_end].strip():
        start = line_start
        end = min(len(text), line_end + 1)
    else:
        while start > line_start and text[start - 1] in " \t":
            start -= 1

    result = text[:start] + text[end:]
    ET.fromstring(result)
    return result


def source_string(path: Path, record_path: str, target_name: str) -> WzSubProperty:
    source = load_source(path).root.get(record_path)
    if not isinstance(source, WzSubProperty):
        raise RuntimeError(f"missing source String record: {record_path}")
    return clone_property(source, None, target_name)


def build_equipment() -> tuple[bytes, bytes, WzSubProperty, Image.Image]:
    source = load_source(SOURCE_EQUIP)
    equip = target_image(source, CLIENT_EQUIP.name, source.root.children())
    info = equip.root.get("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError("Frenzy Totem equipment is missing info")
    cash = info.child("cash")
    if not isinstance(cash, WzIntProperty):
        raise RuntimeError("Frenzy Totem equipment is missing info/cash")
    info_order = tuple(child.name for child in info.children())
    info.add(WzIntProperty("cash", 0, info))
    if tuple(child.name for child in info.children()) != info_order:
        raise RuntimeError("changing info/cash reordered equipment properties")
    equip_data = arc.encode_image_body(equip, arc.gms_reader())
    generated = checked_image(equip_data, CLIENT_EQUIP.name)
    if generated.root.get("info/islot").value != "Po":
        raise RuntimeError("Frenzy Totem islot is not Po")
    if generated.root.get("info/vslot").value != "Po":
        raise RuntimeError("Frenzy Totem vslot is not Po")
    if generated.root.get("info/cash").value != 0:
        raise RuntimeError("Frenzy Totem must use the normal equipment slot")
    if visible_canvases(generated.root) != {
        "info/icon": (27, 34), "info/iconRaw": (27, 34)
    }:
        raise RuntimeError("unexpected Frenzy Totem equipment icon contract")

    string_record = source_string(
        SOURCE_EQP_STRING, f"Eqp/Weapon/{SOURCE_EQUIP_ID}", str(ITEM_ID)
    )
    icon = decode_canvas(source.root.get("info/icon"), region="GMS").convert("RGBA")
    equip_xml = arc.image_to_xml(equip, CLIENT_EQUIP.name).encode("utf-8")
    ET.fromstring(equip_xml)
    return equip_data, equip_xml, string_record, icon


def summon_animation(source: WzSubProperty, source_name: str, target_name: str,
                     parent: WzSubProperty) -> WzSubProperty:
    source_animation = source.get(source_name)
    if not isinstance(source_animation, WzSubProperty):
        raise RuntimeError(f"missing totem animation: {source_name}")
    animation = clone_property(source_animation, parent, target_name)
    for frame in animation.children():
        if isinstance(frame, WzCanvasProperty) and frame.get("delay") is None:
            frame.add(WzIntProperty("delay", 120, frame))
    return animation


def summon_attack(source: WzSubProperty, parent: WzSubProperty) -> WzSubProperty:
    attack = summon_animation(source, "stand", "attack1", parent)
    info = WzSubProperty("info", attack)
    attack_range = WzSubProperty("range", info)
    attack_range.add(WzVectorProperty("lt", -80, -220, attack_range))
    attack_range.add(WzVectorProperty("rb", 80, 20, attack_range))
    info.add(attack_range)
    info.add(WzIntProperty("attackAfter", 270, info))
    info.add(WzIntProperty("mobCount", 1, info))
    info.add(WzIntProperty("type", 0, info))
    attack.add(info)
    return attack


def build_skill(equip_icon: Image.Image,
                totem_visual: WzImage,
                source_skill_image: WzImage) -> tuple[WzSubProperty, WzSubProperty]:
    skill = WzSubProperty(SKILL_ID)
    resized = equip_icon.resize((25, 32), Image.Resampling.LANCZOS)
    icon = Image.new("RGBA", (32, 32))
    icon.alpha_composite(resized, (3, 0))
    for name in ("icon", "iconMouseOver", "iconDisabled"):
        canvas = canvas_property(name, icon, skill)
        canvas.add(WzVectorProperty("origin", 0, 32, canvas))
        canvas.add(WzIntProperty("z", 0, canvas))
        skill.add(canvas)

    level = WzSubProperty("level", skill)
    first = WzSubProperty("1", level)
    first.add(WzStringProperty("hs", "h1", first))
    first.add(WzIntProperty("time", 600, first))
    first.add(WzIntProperty("cooltime", 0, first))
    level.add(first)
    skill.add(level)

    action = WzSubProperty("action", skill)
    action.add(WzStringProperty("0", "alert2", action))
    skill.add(action)

    source_skill = source_skill_image.root.get(f"skill/{SOURCE_SKILL_ID}")
    if not isinstance(source_skill, WzSubProperty):
        raise RuntimeError("missing v79 Frenzy Totem skill 0001013")
    source_effect = source_skill.get("effect")
    source_effect0 = source_skill.get("effect0")
    if not isinstance(source_effect, WzSubProperty) or not isinstance(source_effect0, WzSubProperty):
        raise RuntimeError("v79 Frenzy Totem is missing effect/effect0")
    skill.add(clone_property(source_effect, skill, "effect"))
    skill.add(clone_property(source_effect0, skill, "effect0"))

    summon = WzSubProperty("summon", skill)
    summon.add(summon_animation(
        totem_visual.root, "regen", "summoned", summon
    ))
    summon.add(summon_animation(
        totem_visual.root, "stand", "stand", summon
    ))
    summon.add(summon_attack(totem_visual.root, summon))
    summon.add(summon_animation(
        totem_visual.root, "die1", "die", summon
    ))
    skill.add(summon)
    skill.add(WzIntProperty("invisible", 0, skill))
    skill.add(WzIntProperty("timeLimited", 0, skill))
    skill.add(WzIntProperty("disable", 0, skill))

    string_record = source_string(
        SOURCE_SKILL_STRING, SOURCE_SKILL_ID, SKILL_ID
    )
    if string_record.get("name").value != "轮回":
        raise RuntimeError("unexpected Frenzy Totem skill name")
    return skill, string_record


def build_expected() -> dict[Path, tuple[bytes | None, bytes]]:
    equip, equip_xml, equip_string, equip_icon = build_equipment()
    skill, skill_string = build_skill(
        equip_icon,
        load_source(SOURCE_TOTEM_VISUAL),
        load_source(SOURCE_SKILL),
    )
    output: dict[Path, tuple[bytes | None, bytes]] = {
        CLIENT_EQUIP: (None, equip),
        SERVER_EQUIP: (None, equip_xml),
    }

    baseline = CLIENT_EQP_STRING.read_bytes()
    without_legacy = remove_property_record(
        baseline, ("Eqp", "Weapon"), str(SOURCE_EQUIP_ID)
    )
    without_legacy = remove_property_record(
        without_legacy, ("Eqp", "Accessory"), str(OBSOLETE_ITEM_ID)
    )
    output[CLIENT_EQP_STRING] = (
        baseline,
        ensure_property_record(without_legacy, ("Eqp", "Accessory"), equip_string),
    )
    for path in SERVER_EQP_STRINGS:
        baseline = path.read_bytes()
        without_legacy = remove_xml_record(
            baseline.decode("utf-8"), ("Eqp", "Weapon"), str(SOURCE_EQUIP_ID)
        )
        without_legacy = remove_xml_record(
            without_legacy, ("Eqp", "Accessory"), str(OBSOLETE_ITEM_ID)
        )
        output[path] = (
            baseline,
            ensure_xml_record(
                without_legacy, ("Eqp", "Accessory"), equip_string
            ).encode("utf-8"),
        )

    baseline = git_baseline(CLIENT_SKILL)
    output[CLIENT_SKILL] = (
        baseline, arc.append_property_record(baseline, ("skill",), skill)
    )
    baseline = git_baseline(CLIENT_SKILL_STRING)
    output[CLIENT_SKILL_STRING] = (
        baseline, arc.append_property_record(baseline, (), skill_string)
    )
    baseline = git_baseline(SERVER_SKILL)
    output[SERVER_SKILL] = (
        baseline,
        arc.append_xml_properties(
            baseline.decode("utf-8"), ("skill",), [skill]
        ).encode("utf-8"),
    )
    for path in SERVER_SKILL_STRINGS:
        baseline = git_baseline(path)
        output[path] = (
            baseline,
            arc.append_xml_properties(
                baseline.decode("utf-8"), (), [skill_string]
            ).encode("utf-8"),
        )

    baseline = CLIENT_MOB_STRING.read_bytes()
    output[CLIENT_MOB_STRING] = (
        baseline, remove_property_record(baseline, (), str(OBSOLETE_MOB_ID))
    )
    for path in SERVER_MOB_STRINGS:
        baseline = path.read_bytes()
        output[path] = (
            baseline,
            remove_xml_record(
                baseline.decode("utf-8"), (), str(OBSOLETE_MOB_ID)
            ).encode("utf-8"),
        )

    for path, parent_path, name in (
        (LEGACY_CLIENT_INSTALL, (), f"0{OBSOLETE_ITEM_ID}"),
        (LEGACY_CLIENT_INS_STRING, (), str(OBSOLETE_ITEM_ID)),
    ):
        baseline = path.read_bytes()
        output[path] = (baseline, remove_property_record(baseline, parent_path, name))
    for path in (LEGACY_SERVER_INSTALL, *LEGACY_SERVER_INS_STRINGS):
        baseline = path.read_bytes()
        output[path] = (
            baseline,
            remove_xml_record(baseline.decode("utf-8"), (),
                              f"0{OBSOLETE_ITEM_ID}" if path == LEGACY_SERVER_INSTALL else str(OBSOLETE_ITEM_ID))
            .encode("utf-8"),
        )

    validate_expected(output)
    return output


def validate_expected(expected: dict[Path, tuple[bytes | None, bytes]]) -> None:
    for path in (
        CLIENT_EQUIP, CLIENT_EQP_STRING, CLIENT_SKILL, CLIENT_SKILL_STRING,
        CLIENT_MOB_STRING, LEGACY_CLIENT_INSTALL, LEGACY_CLIENT_INS_STRING,
    ):
        checked_image(expected[path][1], path.name)
    for path, (_baseline, result) in expected.items():
        if path.suffix == ".xml":
            ET.fromstring(result)


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing")
    args = parser.parse_args()

    expected = build_expected()
    changed: list[Path] = []
    for path, (baseline, result) in expected.items():
        current = path.read_bytes() if path.exists() else None
        if current == result:
            continue
        previous_hash = sha256(current) if current is not None else None
        if current != baseline and PREVIOUS_OUTPUT_SHA256.get(path) != previous_hash:
            raise RuntimeError(f"refusing unknown resource state: {path}")
        if args.check:
            raise SystemExit(f"{path} needs Frenzy Totem resources")
        atomic_write(path, result)
        changed.append(path)

    for path, expected_hash in OBSOLETE_OUTPUT_SHA256.items():
        if not path.exists():
            continue
        if sha256(path.read_bytes()) != expected_hash:
            raise RuntimeError(f"refusing unknown obsolete resource state: {path}")
        if args.check:
            raise SystemExit(f"obsolete Frenzy Totem resource remains: {path}")
        path.unlink()
        changed.append(path)

    print(f"Frenzy Totem resources ok: changed={len(changed)}")
    for path, (_baseline, result) in expected.items():
        print(f"{path.relative_to(ROOT)} sha256={sha256(result)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
