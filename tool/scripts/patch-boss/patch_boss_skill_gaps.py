#!/usr/bin/env python3
"""Fill high-value Boss-only skill gaps after the five base migrations."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wzpy import WzCanvasProperty, WzImage, WzIntProperty, WzKey, WzStringProperty, WzSubProperty, WzUolProperty, WzVectorProperty  # noqa: E402
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402

from patch_black_mage_boss_compat import append_root_properties, build_custom_mobskill  # noqa: E402
from patch_lucid_boss_compat import atomic_write_bytes, atomic_write_text, gms_reader, img_to_xml, source_img  # noqa: E402


CUSTOM_SKILLS = {
    183: {"mpCon": 10, "interval": 25, "time": 0, "prop": 100, "x": 45},
    184: {"mpCon": 10, "interval": 20, "time": 0, "prop": 100, "x": 35},
    185: {"mpCon": 10, "interval": 25, "time": 0, "prop": 100, "x": 50},
    186: {"mpCon": 10, "interval": 20, "time": 0, "prop": 100, "x": 40},
    187: {"mpCon": 10, "interval": 25, "time": 0, "prop": 100, "x": 45},
}

# target mob -> (custom skill, action, source mob, source action, effect root, effect name)
VISUAL_SKILLS = {
    8880301: (183, 7, 8880301, "attack7", "customBossWill", "webBurst"),
    8880000: (184, 1, 8880000, "skill1", "customBossMagnus", "meteorStorm"),
    8880140: (185, 1, 8880140, "skill1", "customBossLucid", "dreamBurst"),
    8644630: (186, 4, 8644611, "attack4", "customBossDusk", "tentacleStrike"),
    8880342: (187, 3, 8880607, "attack3", "customBossSeren", "sacredBurst"),
}

MAGNUS_STATUS_SKILLS = ((120, 5, 3), (127, 2, 2), (140, 5, 4))


def skill_specs(mob_id: int) -> tuple[tuple[int, int, int], ...]:
    custom_id, action, *_ = VISUAL_SKILLS[mob_id]
    prefix = MAGNUS_STATUS_SKILLS if mob_id == 8880000 else ()
    return prefix + ((custom_id, 1, action),)


def ensure_skill_action(root: WzSubProperty, action: int, source_name: str) -> None:
    target_name = f"skill{action}"
    if root.child(target_name) is not None:
        return
    source = root.child(source_name)
    if source is None:
        raise ValueError(f"{root.name}: missing {source_name}")
    target = WzSubProperty(target_name, root)
    for frame in source.children():
        if frame.name.isdigit():
            target.add(WzUolProperty(frame.name, f"../{source_name}/{frame.name}", target))
    if not list(target.children()):
        raise ValueError(f"{root.name}: {source_name} has no frames")
    root._children[target_name] = target


def patch_client_mob(mob_id: int) -> None:
    path = ROOT / f"clien/Data/Mob/{mob_id}.img"
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    image.parse()
    info = image.root.child("info")
    if info is None:
        raise ValueError(f"{mob_id}: missing info")
    custom_id, action, _, source_action, _, _ = VISUAL_SKILLS[mob_id]
    ensure_skill_action(image.root, action, source_action)

    existing = info.child("skill")
    retained = []
    if existing is not None and mob_id != 8880000:
        retained = [
            (int(entry.get("skill").value), int(entry.get("level").value), int(entry.get("action").value))
            for entry in existing.children()
            if int(entry.get("skill").value) != custom_id
        ]
    specs = retained + list(skill_specs(mob_id))
    skills = WzSubProperty("skill", info)
    for index, (skill_id, level, skill_action) in enumerate(specs):
        entry = WzSubProperty(str(index), skills)
        entry.add(WzIntProperty("skill", skill_id, entry))
        entry.add(WzIntProperty("level", level, entry))
        entry.add(WzIntProperty("action", skill_action, entry))
        skills.add(entry)
    info._children["skill"] = skills
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))


def xml_skill_block(specs: list[tuple[int, int, int]]) -> str:
    entries = []
    for index, (skill_id, level, action) in enumerate(specs):
        entries.append(
            f'<imgdir name="{index}"><int name="skill" value="{skill_id}"/>'
            f'<int name="level" value="{level}"/><int name="action" value="{action}"/></imgdir>'
        )
    return '<imgdir name="skill">' + "".join(entries) + "</imgdir>"


def find_imgdir(text: str, name: str, start: int = 0) -> tuple[int, int]:
    marker = f'<imgdir name="{name}">'
    block_start = text.find(marker, start)
    if block_start < 0:
        raise ValueError(f"missing {marker}")
    pos = block_start
    depth = 0
    while pos < len(text):
        next_open = text.find("<imgdir ", pos)
        next_close = text.find("</imgdir>", pos)
        if next_close < 0:
            break
        if 0 <= next_open < next_close:
            depth += 1
            pos = next_open + 8
        else:
            depth -= 1
            pos = next_close + len("</imgdir>")
            if depth == 0:
                return block_start, pos
    raise ValueError(f"unterminated {marker}")


def patch_server_mob(mob_id: int) -> None:
    path = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
    text = path.read_text(encoding="utf-8")
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        client_path = ROOT / f"clien/Data/Mob/{mob_id}.img"
        image = WzImage.from_bytes(client_path.read_bytes(), key=WzKey.for_region("GMS"), name=client_path.name)
        image.parse()
        info_node = image.root.child("info")
        if info_node is None:
            raise ValueError(f"{mob_id}: cannot rebuild server Mob without info")
        info_node._children["maxHP"] = WzStringProperty("maxHP", "5000000000", info_node)
        text = img_to_xml(image, root_name=f"{mob_id}.img")
        root = ET.fromstring(text)
    info = root.find('./imgdir[@name="info"]')
    if info is None:
        raise ValueError(f"{mob_id}: missing server info")
    retained = []
    current = info.find('./imgdir[@name="skill"]')
    custom_id = VISUAL_SKILLS[mob_id][0]
    if current is not None and mob_id != 8880000:
        for entry in current.findall("imgdir"):
            values = tuple(int(entry.find(f'./int[@name="{name}"]').attrib["value"]) for name in ("skill", "level", "action"))
            if values[0] != custom_id:
                retained.append(values)
    specs = retained + list(skill_specs(mob_id))
    block = xml_skill_block(specs)
    if current is not None:
        info_start = text.find('<imgdir name="info">')
        start, end = find_imgdir(text, "skill", info_start)
        text = text[:start] + block + text[end:]
    else:
        marker = '<imgdir name="info">'
        text = text.replace(marker, marker + block, 1)

    action = VISUAL_SKILLS[mob_id][1]
    if f'<imgdir name="skill{action}">' not in text:
        source_name = VISUAL_SKILLS[mob_id][3]
        start, end = find_imgdir(text, source_name)
        source_block = text[start:end]
        target_block = source_block.replace(
            f'<imgdir name="{source_name}">',
            f'<imgdir name="skill{action}">',
            1,
        )
        text = text[:end] + target_block + text[end:]
    atomic_write_text(path, text)


def patch_custom_mobskills() -> None:
    import patch_black_mage_boss_compat as black_mage

    previous = black_mage.CUSTOM_SKILLS
    black_mage.CUSTOM_SKILLS = CUSTOM_SKILLS
    try:
        append_root_properties(
            ROOT / "clien/Data/Skill/MobSkill.img",
            [build_custom_mobskill(skill_id) for skill_id in CUSTOM_SKILLS],
        )
    finally:
        black_mage.CUSTOM_SKILLS = previous

    path = ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml"
    text = path.read_text(encoding="utf-8")
    existing = {node.attrib.get("name") for node in ET.fromstring(text).findall("imgdir")}
    append = []
    for skill_id, values in CUSTOM_SKILLS.items():
        if str(skill_id) in existing:
            continue
        body = "".join(f'<int name="{name}" value="{value}"/>' for name, value in values.items())
        body += '<vector name="lt" x="-2000" y="-1200"/><vector name="rb" x="2000" y="500"/>'
        append.append(f'<imgdir name="{skill_id}"><imgdir name="level"><imgdir name="1">{body}</imgdir></imgdir></imgdir>')
    if append:
        pos = text.rfind("</imgdir>")
        atomic_write_text(path, text[:pos] + "".join(append) + text[pos:])


def build_effect(source_id: int, source_action: str, root_name: str, effect_name: str) -> WzSubProperty:
    source = source_img(ROOT.parent / "神说/Data" / f"Mob/{source_id}.img")
    group = source.root.child(source_action)
    if group is None:
        raise ValueError(f"{source_id}: missing {source_action}")
    root = WzSubProperty(root_name)
    effect = WzSubProperty(effect_name, root)
    for frame in group.children():
        if not frame.name.isdigit() or not isinstance(frame, WzCanvasProperty):
            continue
        pixels = decode_canvas(frame, region="EMS")
        canvas = WzCanvasProperty(frame.name, effect)
        canvas.width, canvas.height = int(frame.width), int(frame.height)
        canvas.format, canvas.format2 = 1, 0
        canvas._png_data = encode_canvas_payload(pixels, 1, canvas.width, canvas.height, key=WzKey.for_region("GMS"), listwz=False)
        canvas._png_length = len(canvas._png_data)
        origin = frame.child("origin")
        ox = canvas.width // 2 if origin is None else int(origin.x)
        oy = canvas.height // 2 if origin is None else int(origin.y)
        canvas.add(WzVectorProperty("origin", ox, oy, canvas))
        canvas.add(WzVectorProperty("head", -1, -min(80, max(0, oy)), canvas))
        canvas.add(WzVectorProperty("lt", -ox, -oy, canvas))
        canvas.add(WzVectorProperty("rb", canvas.width - ox, canvas.height - oy, canvas))
        delay = frame.child("delay")
        canvas.add(WzIntProperty("delay", 90 if delay is None or int(delay.value) <= 0 else int(delay.value), canvas))
        effect.add(canvas)
    if not list(effect.children()):
        raise ValueError(f"{source_id}/{source_action}: no direct Canvas frames")
    root.add(effect)
    return root


def patch_effects() -> None:
    effects = [build_effect(source_id, action, root_name, effect_name) for _, _, source_id, action, root_name, effect_name in VISUAL_SKILLS.values()]
    path = ROOT / "clien/Data/Map/Effect.img"
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    image.parse()
    for effect in effects:
        effect.parent = image.root
        image.root._children[effect.name] = effect
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))


def main() -> int:
    patch_custom_mobskills()
    patch_effects()
    for mob_id in VISUAL_SKILLS:
        patch_client_mob(mob_id)
        patch_server_mob(mob_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
