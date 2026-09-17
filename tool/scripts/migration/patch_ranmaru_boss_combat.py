#!/usr/bin/env python3
"""Restore Ranmaru boss skills, HP, battle-map enter scripts, and set drops."""

from __future__ import annotations

import hashlib
import io
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_ranmaru as ranmaru  # noqa: E402
from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.crypto import WzKey  # noqa: E402
from wzpy.incremental_img import replace_img_record  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_string_block  # noqa: E402


ZAKUM_HP = 110000000
HORNTAIL_HP = 2090000000
NORMAL_BOSS_ID = ranmaru.NORMAL_BOSS_ID
HARD_BOSS_ID = ranmaru.HARD_BOSS_ID
BATTLE_MAPS = (ranmaru.NORMAL_BATTLE, ranmaru.HARD_BATTLE)
ON_USER_ENTER = "Ranmaru_Enter"
ON_FIRST_USER_ENTER = "Ranmaru_EnterF"
DROP_SQL = (
    ROOT
    / "gms-server/src/main/resources/db/migration/"
    "V2.1.81__add_ranmaru_set_drops.sql"
)
DROP_CHANCE = 10000  # 1% on the 1,000,000 drop_data scale

# TMS / HEAD 9421581 info/skill. 145/19 and 133/18 are higher than hard.
NORMAL_SKILLS = (
    {"skill": 100, "action": 1, "level": 25, "effectAfter": 0, "skillAfter": 1800},
    {"skill": 145, "action": 2, "level": 19, "effectAfter": 0, "skillAfter": 2160},
    {"skill": 128, "action": 3, "level": 23, "effectAfter": 0, "skillAfter": 1800},
    {"skill": 133, "action": 4, "level": 18, "effectAfter": 0, "skillAfter": 1800},
)
# TMS ms-extract/Mob_00001/Mob_9421583.img info/skill. skill5 pose stays action 5.
# 176/10 in TMS _Canvas is hit-only (no screen/lua/x=999999). Fill that row; do
# not copy client 176/6 screenCrack.
HARD_SKILLS = (
    {"skill": 100, "action": 1, "level": 29, "effectAfter": 0, "skillAfter": 1800},
    {"skill": 145, "action": 2, "level": 17, "effectAfter": 0, "skillAfter": 2160},
    {"skill": 128, "action": 3, "level": 33, "effectAfter": 0, "skillAfter": 1800},
    {"skill": 133, "action": 4, "level": 16, "effectAfter": 0, "skillAfter": 1800},
    {
        "skill": 176,
        "action": 5,
        "level": 10,
        "effectAfter": 0,
        "skillAfter": 4920,
        "priority": 2,
    },
)
MAX_SKILL5_EDGE = 1024
TMS_EXTRACT_HARD = Path("/Users/lizixian/Documents/mxd/TMS/ms-extract/Mob_00001/Mob_9421583.img")
CLIENT_MOBSKILL = ROOT / "clien/Data/Skill/MobSkill.img"
SERVER_MOBSKILL = ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml"
# Clone missing TMS levels by copying existing client records, and fill every
# hole from 1..level. The old client walks that range; a lone 100/29 with no
# 26-28 is the startup "incorrect game data" class.
MOBSKILL_CLONES = (
    (100, 29, 25),
    (145, 19, 9),
    (128, 33, 18),
    (133, 18, 8),
)
HP_BY_MOB = {
    NORMAL_BOSS_ID: ZAKUM_HP,
    HARD_BOSS_ID: HORNTAIL_HP,
}
SKILLS_BY_MOB = {
    NORMAL_BOSS_ID: NORMAL_SKILLS,
    HARD_BOSS_ID: HARD_SKILLS,
}
NORMAL_DROPS = (
    (1003603, "天钿女命的帽子"),
    (1052511, "天钿女命的铠甲"),
    (1072713, "天钿女命的鞋子"),
    (1082474, "天钿女命的手套"),
    (1102458, "天钿女命的披风"),
    (1132158, "天钿女命的腰带"),
    (1003601, "天照的头盔"),
    (1052509, "天照的铠甲"),
    (1072711, "天照的鞋子"),
    (1082472, "天照的手套"),
    (1102456, "天照的披风"),
    (1132156, "天照的腰带"),
    (1003602, "大山祇神的帽子"),
    (1052510, "大山祇神的铠甲"),
    (1072712, "大山祇神的鞋子"),
    (1082473, "大山祇神的手套"),
    (1102457, "大山祇神的披风"),
    (1132157, "大山祇神的腰带"),
    (1003604, "月夜见尊的帽子"),
    (1052512, "月夜见尊的铠甲"),
    (1072714, "月夜见尊的鞋子"),
    (1082475, "月夜见尊的手套"),
    (1102459, "月夜见尊的披风"),
    (1132159, "月夜见尊的腰带"),
    (1003605, "素盏呜尊的头盔"),
    (1052513, "素盏呜尊的铠甲"),
    (1072715, "素盏呜尊的鞋子"),
    (1082476, "素盏呜尊的手套"),
    (1102460, "素盏呜尊的披风"),
    (1132160, "素盏呜尊的腰带"),
)
HARD_DROPS = (
    (1372234, "天钿女命的却鬼棒"),
    (1382271, "天钿女命的魔灵杖"),
    (1302349, "天照的丛云剑"),
    (1312209, "天照的天月斧"),
    (1322261, "天照的金刚杵"),
    (1402265, "天照的御魂剑"),
    (1412186, "天照的鬼炎斧"),
    (1422194, "天照的破雳刚杵"),
    (1432140, "天照的风灭戟"),
    (1442184, "天照的天羽羽斩"),
    (1452263, "大山祇神的火魂弓"),
    (1462249, "大山祇神的大通莲弓"),
    (1332195, "月夜见尊的斩杀刀"),
    (1332286, "月夜见尊的斩杀刀"),
    (1472271, "月夜见尊的惨魔拳"),
    (1482229, "素盏呜尊的惨血熊千"),
    (1492241, "素盏呜尊的雷激枪"),
)
SCRIPT_TREES = (
    ROOT / "gms-server/scripts",
    ROOT / "gms-server/scripts-zh-CN",
)
ENTER_SCRIPT = """\
function start(ms) {
    var player = ms.getPlayer();
    if (player == null) {
        return;
    }
    player.dropMessage(5, "森兰丸的气息笼罩了祭坛。");
}
"""
FIRST_ENTER_SCRIPT = """\
function start(ms) {
}
"""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_img(data: bytes, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"{name} parse failed: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    return image


def client_mob_path(mob_id: int) -> Path:
    path = ROOT / f"clien/Data/Mob/{mob_id}.img"
    padded = ROOT / f"clien/Data/Mob/{mob_id:07d}.img"
    return path if path.is_file() or not padded.is_file() else padded


def server_mob_path(mob_id: int) -> Path:
    path = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
    padded = ROOT / f"gms-server/wz/Mob.wz/{mob_id:07d}.img.xml"
    return path if path.is_file() or not padded.is_file() else padded


def skill_table(entries: tuple[dict, ...]) -> WzSubProperty:
    root = WzSubProperty("skill")
    for index, entry in enumerate(entries):
        root.add(skill_slot_record(index, entry))
    return root


def skill_slot_record(index: int, entry: dict) -> WzSubProperty:
    slot = WzSubProperty(str(index))
    for name in ("skill", "action", "level", "effectAfter", "skillAfter"):
        slot.add(WzIntProperty(name, int(entry[name]), slot))
    if "priority" in entry:
        slot.add(WzIntProperty("priority", int(entry["priority"]), slot))
    return slot


def skill_matches(info, entries: tuple[dict, ...]) -> bool:
    if not isinstance(info, WzSubProperty):
        return False
    node = info.child("skill")
    if not isinstance(node, WzSubProperty):
        return False
    children = [child for child in node.children() if child.name.isdigit()]
    if len(children) != len(entries):
        return False
    for child, entry in zip(sorted(children, key=lambda item: int(item.name)), entries):
        for name, value in entry.items():
            actual = arc.child_value(child, name)
            if actual is None or int(actual) != int(value):
                return False
    return True


def head_blob(rel: str) -> bytes:
    return subprocess.check_output(["git", "cat-file", "blob", f"HEAD:{rel}"], cwd=ROOT)


def append_raw_record(data: bytes, parent_path: tuple[str, ...], name: str, record: bytes) -> bytes:
    layout = arc.scan_img(data, region="GMS")
    prop_list, ancestors = arc._find_list(layout.root, parent_path)
    if any(item.name == name for item in prop_list.records):
        raise FileExistsError("/".join((*parent_path, name)))
    count_edit = arc._count_edit(prop_list, prop_list.count + 1)
    count_delta = len(count_edit[2]) - (count_edit[1] - count_edit[0])
    if count_delta != 0:
        raise RuntimeError(f"{'/'.join(parent_path)} count encoding changed length")
    delta = len(record) + count_delta
    edits = [
        (prop_list.end, prop_list.end, record),
        count_edit,
        *arc._size_edits(ancestors, delta),
    ]
    edits.extend(arc._reference_edits(layout, edits))
    result = arc.verified_image_bytes(arc._apply_edits(data, edits), name)
    arc.verify_raw_record_scope(data, result, {(*parent_path, name)}, allow_additions=True)
    return result


def find_record(data: bytes, path: tuple[str, ...]):
    layout = arc.scan_img(data, region="GMS")
    prop_list, _ancestors = arc._find_list(layout.root, path[:-1])
    record = next((item for item in prop_list.records if item.name == path[-1]), None)
    if record is None:
        raise KeyError("/".join(path))
    return record


def raw_rename_record(data: bytes, source_path: tuple[str, ...], dest_name: str) -> bytes:
    record = find_record(data, source_path)
    reader = WzBinaryReader(io.BytesIO(data), arc.GMS_KEY)
    return encode_string_block(reader, dest_name) + data[record.name_end:record.end]


def parse_tms(path: Path, name: str) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("BMS"), name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"{name} TMS parse failed: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    return image


def assert_tms_hard_table() -> None:
    if not TMS_EXTRACT_HARD.is_file():
        raise FileNotFoundError(TMS_EXTRACT_HARD)
    image = parse_tms(TMS_EXTRACT_HARD, "9421583.img")
    if not skill_matches(image.root.child("info"), HARD_SKILLS):
        raise RuntimeError("HARD_SKILLS does not match TMS 9421583 info/skill")


def fill_176_level(data: bytes, level_name: str) -> bytes:
    if parse_img(data, CLIENT_MOBSKILL.name).root.get(f"176/level/{level_name}") is not None:
        return data
    level = WzSubProperty(level_name)
    for name, value in (
        ("mpCon", 1),
        ("interval", 5),
        ("time", 0),
        ("prop", 100),
        ("hp", 100),
    ):
        level.add(WzIntProperty(name, value, level))
    patched = arc.append_property_record(data, ("176", "level"), level)
    hit = find_record(patched, ("176", "level", "6", "hit"))
    return append_raw_record(
        patched, ("176", "level", level_name), "hit", patched[hit.start:hit.end]
    )


def existing_levels(data: bytes, skill_id: int) -> set[int]:
    layout = arc.scan_img(data, region="GMS")
    prop_list, _ancestors = arc._find_list(layout.root, (str(skill_id), "level"))
    return {int(item.name) for item in prop_list.records if item.name.isdigit()}


def densify_client_levels(data: bytes, skill_id: int, dest: int, src: int) -> bytes:
    patched = data
    for level in range(1, dest + 1):
        if level in existing_levels(patched, skill_id):
            continue
        record = raw_rename_record(patched, (str(skill_id), "level", str(src)), str(level))
        patched = append_raw_record(patched, (str(skill_id), "level"), str(level), record)
    return patched


def xml_level_stub(level_name: str, analogue: ET.Element, drop: set[str]) -> WzSubProperty:
    level = WzSubProperty(level_name)
    for child in analogue:
        name = child.get("name") or ""
        if name in drop or child.tag == "imgdir":
            continue
        if child.tag == "int":
            level.add(WzIntProperty(name, int(child.get("value") or 0), level))
        elif child.tag == "string":
            level.add(WzStringProperty(name, child.get("value") or "", level))
        elif child.tag == "vector":
            level.add(
                WzVectorProperty(
                    name, int(child.get("x") or 0), int(child.get("y") or 0), level
                )
            )
    return level


def fill_client_mobskill() -> bool:
    original = CLIENT_MOBSKILL.read_bytes()
    patched = head_blob("clien/Data/Skill/MobSkill.img")
    for skill_id, dest, src in MOBSKILL_CLONES:
        patched = densify_client_levels(patched, skill_id, dest, src)
    for level in range(1, 11):
        patched = fill_176_level(patched, str(level))
    image = parse_img(patched, CLIENT_MOBSKILL.name)
    for skill_id, dest, _src in MOBSKILL_CLONES + ((176, 10, 6),):
        names = sorted(
            int(child.name)
            for child in image.root.get(f"{skill_id}/level").children()
            if child.name.isdigit()
        )
        required = list(range(1, dest + 1))
        if names[: dest] != required:
            raise RuntimeError(f"client MobSkill {skill_id} not contiguous 1..{dest}: {names}")
    node = image.root.get("176/level/10")
    if not isinstance(node, WzSubProperty):
        raise RuntimeError("client 176/10 missing after fill")
    if node.child("screen") is not None or node.child("lua") is not None:
        raise RuntimeError("client 176/10 still has screen/lua")
    if int(arc.child_value(node, "x") or 0) == 999999:
        raise RuntimeError("client 176/10 still has x=999999")
    hit = node.child("hit")
    if not isinstance(hit, WzSubProperty):
        raise RuntimeError("client 176/10 missing hit")
    digits = sorted(int(child.name) for child in hit.children() if child.name.isdigit())
    if digits != list(range(min(digits), max(digits) + 1)):
        raise RuntimeError(f"176/10 hit has numeric gaps {digits}")
    for child in hit.children():
        if not isinstance(child, WzCanvasProperty):
            continue
        if int(child.format) != 1 or int(child.format2) != 0:
            raise RuntimeError(f"176/10 hit/{child.name} format {child.format}/{child.format2}")
        decoded = decode_canvas(child, region="GMS")
        if decoded.size != (int(child.width), int(child.height)):
            raise RuntimeError(f"176/10 hit/{child.name} decode size mismatch")
    if patched == original:
        return False
    arc.atomic_write_bytes(CLIENT_MOBSKILL, patched)
    return True


def fill_server_mobskill() -> bool:
    original = SERVER_MOBSKILL.read_text(encoding="utf-8")
    patched = original
    root = ET.fromstring(patched)
    for skill_id, dest, src in MOBSKILL_CLONES:
        dest_node = root.find(
            f'./imgdir[@name="{skill_id}"]/imgdir[@name="level"]/imgdir[@name="{dest}"]'
        )
        if dest_node is not None:
            continue
        analogue = root.find(
            f'./imgdir[@name="{skill_id}"]/imgdir[@name="level"]/imgdir[@name="{src}"]'
        )
        if analogue is None:
            raise RuntimeError(f"server MobSkill {skill_id}/{src} missing clone source")
        patched = arc.append_xml_properties(
            patched,
            (str(skill_id), "level"),
            [xml_level_stub(str(dest), analogue, {"screen", "lua", "tremble"})],
        )
        root = ET.fromstring(patched)
    if root.find('./imgdir[@name="176"]/imgdir[@name="level"]/imgdir[@name="10"]') is None:
        stub = WzSubProperty("10")
        for name, value in (
            ("mpCon", 1),
            ("interval", 5),
            ("time", 0),
            ("prop", 100),
            ("hp", 100),
        ):
            stub.add(WzIntProperty(name, value, stub))
        patched = arc.append_xml_properties(patched, ("176", "level"), [stub])
        root = ET.fromstring(patched)
    node = root.find('./imgdir[@name="176"]/imgdir[@name="level"]/imgdir[@name="10"]')
    if node is None:
        raise RuntimeError("server 176/10 missing after fill")
    if node.find('./imgdir[@name="screen"]') is not None or node.find('./string[@name="lua"]') is not None:
        raise RuntimeError("server 176/10 still has screen/lua")
    x_node = node.find('./int[@name="x"]')
    if x_node is not None and x_node.get("value") == "999999":
        raise RuntimeError("server 176/10 still has x=999999")
    if patched == original:
        return False
    arc.atomic_write_text(SERVER_MOBSKILL, patched)
    return True


def oversized_skill5_frames(image: WzImage) -> list[WzCanvasProperty]:
    skill5 = image.root.child("skill5")
    if not isinstance(skill5, WzSubProperty):
        return []
    frames = []
    for child in skill5.children():
        if not isinstance(child, WzCanvasProperty):
            continue
        if int(child.width) > MAX_SKILL5_EDGE or int(child.height) > MAX_SKILL5_EDGE:
            frames.append(child)
    return frames


def clone_canvas_child(source, parent):
    if isinstance(source, WzIntProperty):
        return WzIntProperty(source.name, int(source.value), parent)
    if isinstance(source, WzVectorProperty):
        return WzVectorProperty(source.name, int(source.x), int(source.y), parent)
    if isinstance(source, WzStringProperty):
        return WzStringProperty(source.name, str(source.value), parent)
    raise RuntimeError(f"unsupported skill5 child {source.name}:{type(source).__name__}")


def scaled_skill5_canvas(source: WzCanvasProperty) -> WzCanvasProperty:
    pixels = decode_canvas(source, region="GMS").convert("RGBA")
    longest = max(pixels.width, pixels.height, 1)
    scale = min(1.0, MAX_SKILL5_EDGE / longest)
    if scale < 1.0:
        size = (max(1, round(pixels.width * scale)), max(1, round(pixels.height * scale)))
        pixels = pixels.resize(size, Image.Resampling.LANCZOS)
    output = WzCanvasProperty(source.name)
    output.width, output.height = pixels.size
    output.format, output.format2 = 1, 0
    output._png_data = encode_canvas_payload(
        pixels, 1, pixels.width, pixels.height, key=arc.GMS_KEY, listwz=False, zlib_level=6
    )
    output._png_length = len(output._png_data)
    output._png_offset = 0
    for child in source.children():
        cloned = clone_canvas_child(child, output)
        if scale < 1.0 and isinstance(cloned, WzVectorProperty):
            cloned.x = round(int(cloned.x) * scale)
            cloned.y = round(int(cloned.y) * scale)
        output.add(cloned)
    return output


def patch_skill5_oversize(data: bytes, name: str) -> bytes:
    image = parse_img(data, name)
    frames = oversized_skill5_frames(image)
    if not frames:
        return data
    patched = data
    for frame in frames:
        before = patched
        replacement = scaled_skill5_canvas(frame)
        patched = replace_img_record(patched, ("skill5", frame.name), replacement, region="GMS").data
        arc.verify_raw_record_scope(before, patched, {("skill5", frame.name)}, allow_additions=False)
        image = parse_img(patched, name)
        frame = image.root.get(f"skill5/{replacement.name}")
        if not isinstance(frame, WzCanvasProperty):
            raise RuntimeError(f"{name} skill5/{replacement.name} missing after scale")
        if int(frame.width) > MAX_SKILL5_EDGE or int(frame.height) > MAX_SKILL5_EDGE:
            raise RuntimeError(
                f"{name} skill5/{frame.name} still {frame.width}x{frame.height}"
            )
        decoded = decode_canvas(frame, region="GMS")
        if decoded.size != (int(frame.width), int(frame.height)):
            raise RuntimeError(f"{name} skill5/{frame.name} decode size mismatch")
    if oversized_skill5_frames(parse_img(patched, name)):
        raise RuntimeError(f"{name} skill5 still has canvases wider than {MAX_SKILL5_EDGE}")
    return patched


def sync_client_skills(data: bytes, name: str, entries: tuple[dict, ...]) -> bytes:
    image = parse_img(data, name)
    info = image.root.child("info")
    if skill_matches(info, entries):
        return data
    if not isinstance(info, WzSubProperty) or info.child("skill") is None:
        patched = arc.append_property_record(data, ("info",), skill_table(entries))
        arc.verify_raw_record_insert_scope(data, patched, {("info", "skill")})
        return patched
    patched = data
    current = parse_img(patched, name)
    skill_node = (
        current.root.child("info").child("skill")
        if isinstance(current.root.child("info"), WzSubProperty)
        else None
    )
    if isinstance(skill_node, WzSubProperty):
        extras = sorted(
            (child.name for child in skill_node.children() if child.name.isdigit()),
            key=lambda item: int(item),
        )
        while len(extras) > len(entries):
            extra = extras.pop()
            patched = arc.mutate_img(
                patched, "remove", ("info", "skill", extra), region="GMS"
            ).data
    for index, entry in enumerate(entries):
        slot = str(index)
        existing = parse_img(patched, name).root.get(f"info/skill/{slot}")
        if existing is None:
            patched = arc.append_property_record(
                patched, ("info", "skill"), skill_slot_record(index, entry)
            )
            continue
        for field, value in entry.items():
            current = parse_img(patched, name).root.get(f"info/skill/{slot}/{field}")
            if current is None:
                raise RuntimeError(f"{name} missing info/skill/{slot}/{field}")
            if int(getattr(current, "value", 0)) == int(value):
                continue
            before = patched
            path = ("info", "skill", slot, field)
            patched = arc.mutate_img(
                patched, "edit", path, values={"value": int(value)}, region="GMS"
            ).data
            arc.verify_raw_record_scope(before, patched, {path}, allow_additions=False)
    checked = parse_img(patched, name).root.child("info")
    if not skill_matches(checked, entries):
        raise RuntimeError(f"{name} skill table mismatch after sync")
    return patched


def sync_xml_skills(text: str, entries: tuple[dict, ...], label: str) -> str:
    root = ET.fromstring(text)
    if xml_skill_matches(root, entries):
        return text
    if root.find('./imgdir[@name="info"]/imgdir[@name="skill"]') is None:
        return arc.append_xml_properties(text, ("info",), [skill_table(entries)])
    patched = text
    skill = ET.fromstring(patched).find('./imgdir[@name="info"]/imgdir[@name="skill"]')
    extras = []
    if skill is not None:
        extras = sorted(
            (
                child.get("name") or ""
                for child in skill
                if child.tag == "imgdir" and (child.get("name") or "").isdigit()
            ),
            key=lambda item: int(item),
        )
    while len(extras) > len(entries):
        extra = extras.pop()
        patched = arc.mutate_xml(patched, "remove", ("info", "skill", extra))
    for index, entry in enumerate(entries):
        slot = str(index)
        existing = ET.fromstring(patched).find(
            f'./imgdir[@name="info"]/imgdir[@name="skill"]/imgdir[@name="{slot}"]'
        )
        if existing is None:
            patched = arc.append_xml_properties(
                patched, ("info", "skill"), [skill_slot_record(index, entry)]
            )
            continue
        for field, value in entry.items():
            path = ("info", "skill", slot, field)
            node = ET.fromstring(patched).find(
                f'./imgdir[@name="info"]/imgdir[@name="skill"]/imgdir[@name="{slot}"]/int[@name="{field}"]'
            )
            if node is None:
                raise RuntimeError(f"{label} missing info/skill/{slot}/{field}")
            if node.get("value") == str(value):
                continue
            patched = arc.mutate_xml(
                patched, "edit", path, kind="Int", values={"value": int(value)}
            )
    if not xml_skill_matches(ET.fromstring(patched), entries):
        raise RuntimeError(f"{label} skill table mismatch after sync")
    return patched


def xml_skill_matches(root: ET.Element, entries: tuple[dict, ...]) -> bool:
    skill = root.find('./imgdir[@name="info"]/imgdir[@name="skill"]')
    if skill is None:
        return False
    children = [
        child
        for child in skill
        if child.tag == "imgdir" and (child.get("name") or "").isdigit()
    ]
    if len(children) != len(entries):
        return False
    for child, entry in zip(
        sorted(children, key=lambda item: int(item.get("name") or 0)), entries
    ):
        for name, value in entry.items():
            node = child.find(f'./int[@name="{name}"]')
            if node is None or node.get("value") != str(value):
                return False
    return True


def patch_mob(mob_id: int) -> bool:
    client = client_mob_path(mob_id)
    server = server_mob_path(mob_id)
    if not client.is_file() or not server.is_file():
        raise FileNotFoundError(f"missing Ranmaru boss files for {mob_id}")
    target_hp = HP_BY_MOB[mob_id]
    entries = SKILLS_BY_MOB[mob_id]
    image = ranmaru.load_checked(client, arc.GMS_KEY)
    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{mob_id} missing info")
    for child in image.root.children():
        if not child.name.startswith("attack"):
            continue
        attack_info = child.child("info")
        if isinstance(attack_info, WzSubProperty) and attack_info.child("ball") is not None:
            raise RuntimeError(f"{mob_id} {child.name} has ball; ballistic contract needed")

    original = client.read_bytes()
    patched = original
    if int(arc.child_value(info, "maxHP") or 0) != target_hp:
        patched = arc.mutate_img(
            patched, "edit", ("info", "maxHP"), values={"value": target_hp}, region="GMS"
        ).data
        arc.verify_raw_record_scope(original, patched, {("info", "maxHP")}, allow_additions=False)

    patched = sync_client_skills(patched, client.name, entries)
    if mob_id == HARD_BOSS_ID:
        patched = patch_skill5_oversize(patched, client.name)

    checked = parse_img(patched, client.name)
    patched_info = checked.root.child("info")
    if int(arc.child_value(patched_info, "maxHP") or 0) != target_hp:
        raise RuntimeError(f"{mob_id} maxHP was not set to {target_hp}")
    if not skill_matches(patched_info, entries):
        raise RuntimeError(f"{mob_id} skill table mismatch")
    changed_client = patched != original
    if changed_client:
        arc.atomic_write_bytes(client, patched)

    text = server.read_text(encoding="utf-8")
    original_text = text
    xml_root = ET.fromstring(text)
    hp_node = xml_root.find('./imgdir[@name="info"]/int[@name="maxHP"]')
    if hp_node is None:
        raise RuntimeError(f"{server.name} missing info/maxHP")
    if hp_node.get("value") != str(target_hp):
        text = arc.mutate_xml(
            text, "edit", ("info", "maxHP"), kind="Int", values={"value": target_hp}
        )
    text = sync_xml_skills(text, entries, server.name)
    xml_root = ET.fromstring(text)
    hp_node = xml_root.find('./imgdir[@name="info"]/int[@name="maxHP"]')
    if hp_node is None or hp_node.get("value") != str(target_hp):
        raise RuntimeError(f"{server.name} maxHP mismatch")
    if not xml_skill_matches(xml_root, entries):
        raise RuntimeError(f"{server.name} skill table mismatch")
    changed_server = text != original_text
    if changed_server:
        arc.atomic_write_text(server, text)
    return changed_client or changed_server


def patch_battle_map(map_id: int) -> bool:
    client = ranmaru.client_map_path(map_id)
    server = ranmaru.server_map_path("wz", map_id)
    image = ranmaru.load_checked(client, arc.GMS_KEY)
    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"map {map_id} missing info")

    original = client.read_bytes()
    patched = original
    approved: set[tuple[str, ...]] = set()
    if str(arc.child_value(info, "onUserEnter") or "") != ON_USER_ENTER:
        if info.child("onUserEnter") is not None:
            raise RuntimeError(f"map {map_id} has unexpected onUserEnter")
        patched = arc.append_property_record(
            patched, ("info",), WzStringProperty("onUserEnter", ON_USER_ENTER)
        )
        approved.add(("info", "onUserEnter"))
    current_info = parse_img(patched, client.name).root.child("info")
    if str(arc.child_value(current_info, "onFirstUserEnter") or "") != ON_FIRST_USER_ENTER:
        if isinstance(current_info, WzSubProperty) and current_info.child("onFirstUserEnter") is not None:
            raise RuntimeError(f"map {map_id} has unexpected onFirstUserEnter")
        patched = arc.append_property_record(
            patched, ("info",), WzStringProperty("onFirstUserEnter", ON_FIRST_USER_ENTER)
        )
        approved.add(("info", "onFirstUserEnter"))
    if approved:
        arc.verify_raw_record_insert_scope(original, patched, approved)

    checked_info = parse_img(patched, client.name).root.child("info")
    if str(arc.child_value(checked_info, "onUserEnter") or "") != ON_USER_ENTER:
        raise RuntimeError(f"map {map_id} onUserEnter missing")
    if str(arc.child_value(checked_info, "onFirstUserEnter") or "") != ON_FIRST_USER_ENTER:
        raise RuntimeError(f"map {map_id} onFirstUserEnter missing")
    changed_client = patched != original
    if changed_client:
        arc.atomic_write_bytes(client, patched)

    text = server.read_text(encoding="utf-8")
    original_text = text
    xml_root = ET.fromstring(text)
    info_xml = xml_root.find('./imgdir[@name="info"]')
    if info_xml is None:
        raise RuntimeError(f"{server.name} missing info")
    enter = info_xml.find('./string[@name="onUserEnter"]')
    first = info_xml.find('./string[@name="onFirstUserEnter"]')
    props = []
    if enter is None:
        props.append(WzStringProperty("onUserEnter", ON_USER_ENTER))
    elif enter.get("value") != ON_USER_ENTER:
        raise RuntimeError(f"{server.name} unexpected onUserEnter")
    if first is None:
        props.append(WzStringProperty("onFirstUserEnter", ON_FIRST_USER_ENTER))
    elif first.get("value") != ON_FIRST_USER_ENTER:
        raise RuntimeError(f"{server.name} unexpected onFirstUserEnter")
    if props:
        text = arc.append_xml_properties(text, ("info",), props)
    xml_root = ET.fromstring(text)
    info_xml = xml_root.find('./imgdir[@name="info"]')
    enter = info_xml.find('./string[@name="onUserEnter"]')
    first = info_xml.find('./string[@name="onFirstUserEnter"]')
    if enter is None or enter.get("value") != ON_USER_ENTER:
        raise RuntimeError(f"{server.name} onUserEnter mismatch")
    if first is None or first.get("value") != ON_FIRST_USER_ENTER:
        raise RuntimeError(f"{server.name} onFirstUserEnter mismatch")
    changed_server = text != original_text
    if changed_server:
        arc.atomic_write_text(server, text)
    return changed_client or changed_server


def write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return
    path.write_text(text, encoding="utf-8")


def write_scripts() -> None:
    for tree in SCRIPT_TREES:
        write_file(tree / "map/onUserEnter" / f"{ON_USER_ENTER}.js", ENTER_SCRIPT)
        write_file(
            tree / "map/onFirstUserEnter" / f"{ON_FIRST_USER_ENTER}.js",
            FIRST_ENTER_SCRIPT,
        )


def write_drop_sql() -> None:
    rows = []
    for dropper_id, drops in ((NORMAL_BOSS_ID, NORMAL_DROPS), (HARD_BOSS_ID, HARD_DROPS)):
        for item_id, name in drops:
            rows.append((f"({dropper_id}, {item_id}, 1, 1, 0, {DROP_CHANCE})", name))
    lines = []
    for index, (row, name) in enumerate(rows):
        comma = "," if index < len(rows) - 1 else ""
        lines.append(f"{row}{comma} -- {name} 1%")
    text = (
        "-- Mori Ranmaru set/weapon drops.\n"
        "-- drop_data chance scale: 1,000,000 = 100%, so 1% = 10000.\n"
        "INSERT INTO `drop_data`\n"
        "    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`) VALUES\n"
        + "\n".join(lines)
        + "\nON DUPLICATE KEY UPDATE\n"
        "    `minimum_quantity` = VALUES(`minimum_quantity`),\n"
        "    `maximum_quantity` = VALUES(`maximum_quantity`),\n"
        "    `questid` = VALUES(`questid`),\n"
        "    `chance` = VALUES(`chance`);\n"
    )
    write_file(DROP_SQL, text)


def main() -> int:
    changed = []
    assert_tms_hard_table()
    if fill_client_mobskill():
        changed.append("client MobSkill")
    if fill_server_mobskill():
        changed.append("server MobSkill")
    for mob_id in (NORMAL_BOSS_ID, HARD_BOSS_ID):
        if patch_mob(mob_id):
            changed.append(f"mob {mob_id}")
    for map_id in BATTLE_MAPS:
        if patch_battle_map(map_id):
            changed.append(f"map {map_id}")
    write_scripts()
    write_drop_sql()
    print("changed:", ", ".join(changed) if changed else "none")
    for path in (
        client_mob_path(NORMAL_BOSS_ID),
        client_mob_path(HARD_BOSS_ID),
        ranmaru.client_map_path(ranmaru.NORMAL_BATTLE),
        ranmaru.client_map_path(ranmaru.HARD_BATTLE),
        server_mob_path(NORMAL_BOSS_ID),
        server_mob_path(HARD_BOSS_ID),
        ranmaru.server_map_path("wz", ranmaru.NORMAL_BATTLE),
        ranmaru.server_map_path("wz", ranmaru.HARD_BATTLE),
        DROP_SQL,
        CLIENT_MOBSKILL,
        SERVER_MOBSKILL,
    ):
        print(f"{sha256(path)}  {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
