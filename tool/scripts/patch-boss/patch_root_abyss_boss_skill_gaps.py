#!/usr/bin/env python3
"""Fill Root Abyss boss skill pools from TMS metadata.

The existing boss animation resources are kept in place.  This patch only
adds missing summon helper mobs and server-side skill tables/skill lists so
the server AI has the TMS Root Abyss skill pool to choose from.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import io
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

from wzpy import WzImage, WzIntProperty, WzKey, WzSubProperty  # noqa: E402
from wzpy.properties import _parse_extended_or_basic  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import _encode_property_body, _tag_for, encode_image_body, encode_string_block  # noqa: E402

from migrate_root_abyss_maps import (  # noqa: E402
    atomic_write_bytes,
    atomic_write_text,
    backup,
    gms_reader,
    img_to_xml,
    inline_canvas_outlinks,
    reencode_canvas_tree,
    sanitize_root_abyss_boss_mob,
    property_to_xml,
)
from patch_boss_skill_gaps import append_root_properties  # noqa: E402


TMS_ROOT = Path("/Users/lizixian/Documents/mxd/TMS")
PACK_ROOT = TMS_ROOT / "MapleStory/Data/Packs"
MS_PROBE = TMS_ROOT / "black_mage_report_tools/ms_probe/bin/Debug/net8.0/MSProbe.dll"
BMS_KEY = WzKey.for_region("BMS")

HELPER_MOBS = (
    8900001,
    8900002,
    8920002,
    8920004,
    8920005,
    8930001,
)

SERVER_MOB_SKILL_LEVELS = {
    170: (14,),
    186: (1,),
    201: (40, 47, 48, 51, 52, 53),
}

BOSS_SKILLS = {
    8900000: ((201, 40, 1),),
    8910000: (
        (203, 1, 1),
        (184, 1, 2),
        (170, 11, 3),
        (191, 1, 4),
        (191, 2, 5),
        (170, 14, 6),
    ),
    8920000: (
        (201, 47, 1),
        (201, 48, 2),
        (201, 52, 3),
        (201, 53, 4),
    ),
    8920001: (
        (186, 1, 1),
        (201, 51, 2),
        (201, 53, 3),
    ),
    # TMS uses 170/13 as a field-script trigger.  The legacy server has no
    # field-script implementation for it, so retain that action and also enable
    # the already-migrated Vellum helper summon.
    8930000: (
        (170, 13, 1),
        (201, 49, 1),
    ),
}

APPENDED_CLIENT_ACTIONS = {
    8910000: ("skill6",),
}

CLIENT_SKILL_LISTS = BOSS_SKILLS


def run_probe(pack: Path, out_dir: Path, prefix: str) -> None:
    result = subprocess.run(
        ["dotnet", str(MS_PROBE), str(pack), str(out_dir), prefix],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def load_bms_img(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=BMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{path}: parse warnings={image.parse_warnings} truncated={image.truncated}")
    return image


def root_property_spans(data: bytes, path: Path) -> dict[str, tuple[int, int]]:
    reader = WzBinaryReader(io.BytesIO(data), WzKey.for_region("GMS"))
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise ValueError(f"{path}: unexpected image header")
    reader.skip(2)
    count = reader.read_compressed_int()
    root = WzSubProperty(path.name)
    spans: dict[str, tuple[int, int]] = {}
    image = WzImage.from_bytes(data, key=WzKey.for_region("GMS"), name=path.name)
    for _ in range(count):
        start = reader.position
        name = reader.read_string_block(0)
        _parse_extended_or_basic(reader, 0, name, root, image)
        spans[name] = (start, reader.position)
    return spans


def build_skill_property(specs: tuple[tuple[int, int, int], ...], parent: WzSubProperty) -> WzSubProperty:
    skill_root = WzSubProperty("skill", parent)
    for index, (skill_id, level, action) in enumerate(specs):
        item = WzSubProperty(str(index), skill_root)
        item.add(WzIntProperty("skill", skill_id, item))
        item.add(WzIntProperty("level", level, item))
        item.add(WzIntProperty("action", action, item))
        skill_root.add(item)
    return skill_root


def replace_info_skill_property(info: WzSubProperty, specs: tuple[tuple[int, int, int], ...]) -> None:
    skill = build_skill_property(specs, info)
    children = info._children
    if "skill" in children:
        ordered = {}
        for name, child in children.items():
            ordered[name] = skill if name == "skill" else child
        children.clear()
        children.update(ordered)
    else:
        info.add(skill)


def encode_root_property(prop: WzSubProperty) -> bytes:
    encoder = gms_reader()
    return (
        encode_string_block(encoder, prop.name)
        + bytes([_tag_for(prop)])
        + _encode_property_body(prop, encoder)
    )


def patch_client_skill_list(mob_id: int, specs: tuple[tuple[int, int, int], ...]) -> None:
    path = ROOT / f"clien/Data/Mob/{mob_id}.img"
    data = path.read_bytes()
    image = WzImage.from_bytes(data, key=WzKey.for_region("GMS"), name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{path}: parse warnings={image.parse_warnings} truncated={image.truncated}")
    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{path}: missing info")

    before = [(child.name, tuple((entry.child("skill").value, entry.child("level").value, entry.child("action").value)
                                for entry in child.children()))
              for child in info.children() if child.name == "skill"]
    replace_info_skill_property(info, specs)
    after = tuple((entry.child("skill").value, entry.child("level").value, entry.child("action").value)
                  for entry in info.child("skill").children())
    if after != specs:
        raise RuntimeError(f"{path}: failed to build client skill list")
    if before and before[0][1] == specs:
        return

    spans = root_property_spans(data, path)
    if "info" not in spans:
        raise RuntimeError(f"{path}: missing top-level info span")
    start, end = spans["info"]
    encoded = encode_root_property(info)
    patched = data[:start] + encoded + data[end:]
    backup(path)
    atomic_write_bytes(path, patched)


def extract_sources(tmp: Path) -> None:
    for mob_id in (*HELPER_MOBS, *BOSS_SKILLS):
        run_probe(PACK_ROOT / "Mob_00000.ms", tmp, f"Mob/{mob_id}.img")
    for skill_id in SERVER_MOB_SKILL_LEVELS:
        run_probe(PACK_ROOT / "Skill_00007.ms", tmp, f"Skill/MobSkill/{skill_id}.img")


def write_helper_mob(tmp: Path, mob_id: int) -> None:
    source = load_bms_img(tmp / f"Mob_{mob_id}.img")
    inline_canvas_outlinks(source.root)
    reencode_canvas_tree(source.root)
    sanitize_root_abyss_boss_mob(source.root, mob_id)

    client_path = ROOT / f"clien/Data/Mob/{mob_id}.img"
    backup(client_path)
    atomic_write_bytes(client_path, encode_image_body(source, gms_reader()))

    server_path = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
    backup(server_path)
    atomic_write_text(server_path, img_to_xml(source, root_name=f"{mob_id}.img"))


def find_imgdir(text: str, name: str, start: int = 0, end_limit: int | None = None) -> tuple[int, int]:
    marker = f'<imgdir name="{name}">'
    block_start = text.find(marker, start, len(text) if end_limit is None else end_limit)
    if block_start < 0:
        raise ValueError(f"missing {marker}")
    pos = block_start
    depth = 0
    limit = len(text) if end_limit is None else end_limit
    while pos < limit:
        next_open = text.find("<imgdir ", pos, limit)
        next_close = text.find("</imgdir>", pos, limit)
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


def insert_server_mobskill_level(text: str, skill_id: int, level_xml: str) -> str:
    skill_marker = f'<imgdir name="{skill_id}"><imgdir name="level">'
    skill_start = text.find(skill_marker)
    if skill_start < 0:
        raise ValueError(f"missing top-level MobSkill {skill_id}/level")
    skill_start, skill_end = find_imgdir(text, str(skill_id), skill_start)
    level_start, level_end = find_imgdir(text, "level", skill_start, skill_end)
    level_name = ET.fromstring(level_xml).get("name")
    if text.find(f'<imgdir name="{level_name}">', level_start, level_end) >= 0:
        return text
    insert_at = level_end - len("</imgdir>")
    return text[:insert_at] + level_xml + text[insert_at:]


def patch_server_mobskills(tmp: Path) -> None:
    path = ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml"
    text = path.read_text(encoding="utf-8")
    for skill_id, levels in SERVER_MOB_SKILL_LEVELS.items():
        source = load_bms_img(tmp / f"Skill_MobSkill_{skill_id}.img")
        for level in levels:
            node = source.root.get(f"level/{level}")
            if node is None:
                raise RuntimeError(f"TMS MobSkill {skill_id}/{level} not found")
            level_xml = property_to_xml(node, 0)
            text = insert_server_mobskill_level(text, skill_id, level_xml)
    backup(path)
    atomic_write_text(path, text)


def patch_client_actions(tmp: Path) -> None:
    for mob_id, action_names in APPENDED_CLIENT_ACTIONS.items():
        source = load_bms_img(tmp / f"Mob_{mob_id}.img")
        inline_canvas_outlinks(source.root)
        reencode_canvas_tree(source.root)
        properties = []
        for action_name in action_names:
            action = source.root.child(action_name)
            if action is None:
                raise RuntimeError(f"TMS mob {mob_id} missing {action_name}")
            properties.append(action)
        append_root_properties(ROOT / f"clien/Data/Mob/{mob_id}.img", properties)


def patch_server_actions(tmp: Path) -> None:
    for mob_id, action_names in APPENDED_CLIENT_ACTIONS.items():
        path = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
        text = path.read_text(encoding="utf-8")
        source = load_bms_img(tmp / f"Mob_{mob_id}.img")
        inline_canvas_outlinks(source.root)
        reencode_canvas_tree(source.root)
        changed = False
        insert_at = text.rfind("</imgdir>")
        if insert_at < 0:
            raise RuntimeError(f"{path}: missing root close")
        for action_name in action_names:
            if f'<imgdir name="{action_name}">' in text:
                continue
            action = source.root.child(action_name)
            if action is None:
                raise RuntimeError(f"TMS mob {mob_id} missing {action_name}")
            text = text[:insert_at] + property_to_xml(action, 1) + "\n" + text[insert_at:]
            insert_at = text.rfind("</imgdir>")
            changed = True
        if changed:
            backup(path)
            atomic_write_text(path, text)


def skill_block(specs: tuple[tuple[int, int, int], ...]) -> str:
    lines = ['    <imgdir name="skill">']
    for index, (skill_id, level, action) in enumerate(specs):
        lines.extend([
            f'      <imgdir name="{index}">',
            f'        <int name="skill" value="{skill_id}" />',
            f'        <int name="level" value="{level}" />',
            f'        <int name="action" value="{action}" />',
            "      </imgdir>",
        ])
    lines.append("    </imgdir>")
    return "\n".join(lines)


def patch_server_mob_skill_list(mob_id: int, specs: tuple[tuple[int, int, int], ...]) -> None:
    path = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
    text = path.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    for _skill_id, _level, action in specs:
        if root.find(f'./imgdir[@name="skill{action}"]') is None:
            raise RuntimeError(f"{mob_id}: missing skill{action}")

    info_start, info_end = find_imgdir(text, "info")
    block = skill_block(specs)
    try:
        current_start, current_end = find_imgdir(text, "skill", info_start, info_end)
        current_start = text.rfind("\n", 0, current_start) + 1
        text = text[:current_start] + block + text[current_end:]
    except ValueError:
        insert_at = info_start + len('<imgdir name="info">')
        text = text[:insert_at] + "\n" + block + text[insert_at:]
    backup(path)
    atomic_write_text(path, text)


def main() -> int:
    if not MS_PROBE.exists():
        raise RuntimeError(f"missing MS probe: {MS_PROBE}")
    with tempfile.TemporaryDirectory(prefix="root-abyss-boss-skills-") as raw_tmp:
        tmp = Path(raw_tmp)
        extract_sources(tmp)
        for mob_id in HELPER_MOBS:
            write_helper_mob(tmp, mob_id)
        patch_client_actions(tmp)
        for mob_id, specs in CLIENT_SKILL_LISTS.items():
            patch_client_skill_list(mob_id, specs)
        patch_server_actions(tmp)
        patch_server_mobskills(tmp)
        for mob_id, specs in BOSS_SKILLS.items():
            patch_server_mob_skill_list(mob_id, specs)
    print(
        "Root Abyss boss skill gaps patched:",
        f"helper_mobs={len(HELPER_MOBS)}",
        f"bosses={len(BOSS_SKILLS)}",
        f"server_mobskill_levels={sum(len(v) for v in SERVER_MOB_SKILL_LEVELS.values())}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
