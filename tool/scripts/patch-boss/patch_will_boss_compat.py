#!/usr/bin/env python3
"""Restore a load-safe three-stage Will chain and compatible skill actions."""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wzpy import WzImage, WzIntProperty, WzKey, WzStringProperty, WzSubProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402
from patch_lucid_boss_compat import convert_canvas_tree_to_argb4444  # noqa: E402


KEY = WzKey.for_region("GMS")
MOB_DIR = ROOT / "clien/Data/Mob"
SERVER_MOB_DIR = ROOT / "gms-server/wz/Mob.wz"
WILL_IDS = (8880300, 8880301, 8880302, 8880305, 8880315)
WILL_NAMES = {
    8880300: "威尔",
    8880301: "威尔",
    8880302: "威尔",
    8880305: "凝视之眼",
    8880315: "暗之执行者",
}


def int_prop(name: str, value: int) -> WzIntProperty:
    return WzIntProperty(name, value)


def skill_entry(name: str, skill: int, level: int, action: int) -> WzSubProperty:
    entry = WzSubProperty(name)
    entry.add(int_prop("skill", skill))
    entry.add(int_prop("level", level))
    entry.add(int_prop("action", action))
    return entry


def replace_child(parent: WzSubProperty, node) -> None:
    parent._children[node.name] = node


def set_revive(info: WzSubProperty, mob_id: int) -> None:
    revive = WzSubProperty("revive")
    revive.add(int_prop("0", mob_id))
    replace_child(info, revive)


def set_skills(info: WzSubProperty) -> None:
    skills = WzSubProperty("skill")
    for entry in (
        skill_entry("0", 120, 5, 3),
        skill_entry("1", 127, 2, 2),
        skill_entry("2", 140, 5, 4),
    ):
        skills.add(entry)
    replace_child(info, skills)


def clone_attack_as_skill(img: WzImage, action: int) -> None:
    source = img.root.child(f"attack{action}")
    if source is None:
        raise ValueError(f"{img.name}: missing attack{action}")
    clone = clone_property(source)
    clone.name = f"skill{action}"
    replace_child(img.root, clone)


def clone_property(source):
    """Clone a property tree without copying the WZ reader's thread lock."""
    clone = copy.copy(source)
    clone.parent = None
    if hasattr(source, "_children"):
        clone._children = {}
        for child in source.children():
            cloned_child = clone_property(child)
            cloned_child.parent = clone
            clone._children[cloned_child.name] = cloned_child
    if hasattr(source, "points"):
        clone.points = [clone_property(point) for point in source.points]
        for point in clone.points:
            point.parent = clone
    return clone


def patch_client_mob(mob_id: int) -> None:
    path = MOB_DIR / f"{mob_id}.img"
    img = WzImage.from_bytes(path.read_bytes(), key=KEY, name=path.name)
    img.parse()
    info = img.root.child("info")
    if info is None:
        raise ValueError(f"{path}: missing info")

    if mob_id == 8880300:
        set_revive(info, 8880301)
    elif mob_id == 8880301:
        set_skills(info)
        set_revive(info, 8880302)
        for action in (2, 3, 4):
            clone_attack_as_skill(img, action)

    convert_canvas_tree_to_argb4444(img.root, source_region="GMS")
    path.write_bytes(encode_image_body(img, img.wz_file.reader))


def find_imgdir(text: str, name: str) -> tuple[int, int]:
    marker = f'<imgdir name="{name}">'
    start = text.find(marker)
    if start < 0:
        raise ValueError(f"missing {marker}")
    pos = start
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
                return start, pos
    raise ValueError(f"unterminated {marker}")


def find_root_child(text: str, name: str) -> tuple[int, int]:
    root_open = text.find("<imgdir ")
    if root_open < 0:
        raise ValueError("missing root imgdir")
    pos = root_open
    depth = 0
    while pos < len(text):
        next_open = text.find("<imgdir ", pos)
        next_close = text.find("</imgdir>", pos)
        if next_close < 0:
            break
        if 0 <= next_open < next_close:
            depth += 1
            if depth == 2 and text.startswith(f'<imgdir name="{name}">', next_open):
                child_text = text[next_open:]
                _, relative_end = find_imgdir(child_text, name)
                return next_open, next_open + relative_end
            pos = next_open + 8
        else:
            depth -= 1
            pos = next_close + len("</imgdir>")
    raise ValueError(f"missing root child {name}")


def replace_or_append_root_info(text: str, child_name: str, child_xml: str) -> str:
    parent_start, parent_end = find_root_child(text, "info")
    parent = text[parent_start:parent_end]
    marker = f'<imgdir name="{child_name}">'
    if marker in parent:
        child_start, child_end = find_imgdir(parent, child_name)
        parent = parent[:child_start] + child_xml + parent[child_end:]
    else:
        close = parent.rfind("</imgdir>")
        parent = parent[:close] + child_xml + parent[close:]
    return text[:parent_start] + parent + text[parent_end:]


def remove_from_attack1_info(text: str, child_name: str) -> str:
    attack_start, attack_end = find_root_child(text, "attack1")
    attack = text[attack_start:attack_end]
    info_start, info_end = find_imgdir(attack, "info")
    info = attack[info_start:info_end]
    marker = f'<imgdir name="{child_name}">'
    if marker in info:
        child_start, child_end = find_imgdir(info, child_name)
        info = info[:child_start] + info[child_end:]
        attack = attack[:info_start] + info + attack[info_end:]
        return text[:attack_start] + attack + text[attack_end:]
    return text


def clone_xml_action(text: str, attack_name: str, skill_name: str) -> str:
    start, end = find_imgdir(text, attack_name)
    clone = text[start:end].replace(
        f'<imgdir name="{attack_name}">',
        f'<imgdir name="{skill_name}">',
        1,
    )
    root_close = text.rfind("</imgdir>")
    return text[:root_close] + clone + text[root_close:]


def patch_server_mob(mob_id: int) -> None:
    path = SERVER_MOB_DIR / f"{mob_id}.img.xml"
    text = path.read_text(encoding="utf-8")
    text, hp_count = re.subn(
        r'<(?:int|string) name="maxHP" value="[^"]*"/>',
        '<string name="maxHP" value="5000000000"/>',
        text,
        count=1,
    )
    if hp_count != 1:
        raise ValueError(f"{mob_id}: missing server maxHP")
    if mob_id == 8880300:
        text = replace_or_append_root_info(
            text,
            "revive",
            '<imgdir name="revive"><int name="0" value="8880301"/></imgdir>',
        )
    elif mob_id == 8880301:
        text = remove_from_attack1_info(text, "skill")
        text = remove_from_attack1_info(text, "revive")
        skills = (
            '<imgdir name="skill">'
            '<imgdir name="0"><int name="skill" value="120"/><int name="level" value="5"/><int name="action" value="3"/></imgdir>'
            '<imgdir name="1"><int name="skill" value="127"/><int name="level" value="2"/><int name="action" value="2"/></imgdir>'
            '<imgdir name="2"><int name="skill" value="140"/><int name="level" value="5"/><int name="action" value="4"/></imgdir>'
            '</imgdir>'
        )
        text = replace_or_append_root_info(text, "skill", skills)
        text = replace_or_append_root_info(
            text,
            "revive",
            '<imgdir name="revive"><int name="0" value="8880302"/></imgdir>',
        )
        for action in (2, 3, 4):
            skill_name = f"skill{action}"
            if f'<imgdir name="{skill_name}">' not in text:
                text = clone_xml_action(text, f"attack{action}", skill_name)
    path.write_text(text, encoding="utf-8")


def patch_client_strings() -> None:
    path = ROOT / "clien/Data/String/Mob.img"
    img = WzImage.from_bytes(path.read_bytes(), key=KEY, name=path.name)
    img.parse()
    for mob_id, name in WILL_NAMES.items():
        entry = WzSubProperty(str(mob_id))
        entry.add(WzStringProperty("name", name))
        replace_child(img.root, entry)
    path.write_bytes(encode_image_body(img, img.wz_file.reader))


def patch_server_strings(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    root_close = text.rfind("</imgdir>")
    additions = []
    for mob_id, name in WILL_NAMES.items():
        marker = f'<imgdir name="{mob_id}">'
        if marker not in text:
            additions.append(f'<imgdir name="{mob_id}"><string name="name" value="{name}"/></imgdir>')
    if additions:
        text = text[:root_close] + "".join(additions) + text[root_close:]
        path.write_text(text, encoding="utf-8")


def main() -> int:
    for mob_id in WILL_IDS:
        patch_client_mob(mob_id)
    for mob_id in (8880300, 8880301):
        patch_server_mob(mob_id)
    patch_server_mob(8880302)
    patch_client_strings()
    patch_server_strings(ROOT / "gms-server/wz/String.wz/Mob.img.xml")
    patch_server_strings(ROOT / "gms-server/wz-zh-CN/String.wz/Mob.img.xml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
