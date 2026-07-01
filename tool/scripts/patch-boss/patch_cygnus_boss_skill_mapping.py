#!/usr/bin/env python3
"""Map unsupported Cygnus boss skills to current-client compatible skills."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

from wzpy import WzImage, WzIntProperty, WzKey, WzSubProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


KEY = WzKey.for_region("GMS")


def child(node, name: str):
    return node.child(name) if node is not None and hasattr(node, "child") else None


def set_scalar(node, value: int) -> None:
    if node is None:
        raise ValueError("missing scalar node")
    node._value = str(value) if isinstance(getattr(node, "value", None), str) else value


def int_prop(name: str, value: int) -> WzIntProperty:
    return WzIntProperty(name, value)


def skill_entry(name: str, skill: int, action: int, level: int, *, skill_after=None, effect_after=None,
                pre_skill_index=None, pre_skill_count=None) -> WzSubProperty:
    entry = WzSubProperty(name)
    entry.add(int_prop("skill", skill))
    entry.add(int_prop("action", action))
    entry.add(int_prop("level", level))
    if skill_after is not None:
        entry.add(int_prop("skillAfter", skill_after))
    if effect_after is not None:
        entry.add(int_prop("effectAfter", effect_after))
    if pre_skill_index is not None:
        entry.add(int_prop("preSkillIndex", pre_skill_index))
    if pre_skill_count is not None:
        entry.add(int_prop("preSkillCount", pre_skill_count))
    return entry


def set_skill_entries(img: WzImage, entries: list[WzSubProperty]) -> None:
    info = img.get("info")
    if info is None:
        raise ValueError(f"{img.name}: missing info")
    skills = child(info, "skill")
    if skills is None:
        skills = WzSubProperty("skill")
        info.add(skills)
    skills._children.clear()
    for idx, entry in enumerate(entries):
        entry.name = str(idx)
        skills.add(entry)


def save_img(path: Path, edit) -> None:
    img = WzImage.from_bytes(path.read_bytes(), key=KEY, name=path.name)
    img.parse()
    edit(img)
    path.write_bytes(encode_image_body(img, img.wz_file.reader))


def edit_8850011(img: WzImage) -> None:
    set_skill_entries(img, [
        skill_entry("0", 133, 3, 8, skill_after=1760),
        skill_entry("1", 129, 1, 13, skill_after=990),
        skill_entry("2", 200, 2, 223, skill_after=1440),
        skill_entry("3", 132, 4, 8, skill_after=1260, effect_after=1260),  # 172/1 compatible mapping
        skill_entry("4", 145, 6, 9, effect_after=0),
        skill_entry("5", 200, 5, 222, skill_after=1440, pre_skill_index=7, pre_skill_count=5),
        skill_entry("6", 131, 7, 16, effect_after=630, skill_after=630),  # 171/1 compatible mapping
        skill_entry("7", 200, 5, 221, skill_after=1440),
        skill_entry("8", 200, 2, 228, skill_after=1440),
        skill_entry("9", 114, 7, 43, skill_after=630),
        skill_entry("10", 128, 7, 18, skill_after=630),  # 138/1 compatible mapping
    ])
    info = img.get("attack4/info")
    if info is None:
        raise ValueError("8850011 missing attack4/info")
    if child(info, "disease") is None:
        info.add(int_prop("disease", 132))
    else:
        set_scalar(child(info, "disease"), 132)
    if child(info, "level") is None:
        info.add(int_prop("level", 8))
    else:
        set_scalar(child(info, "level"), 8)


def edit_8850002(img: WzImage) -> None:
    set_skill_entries(img, [
        skill_entry("0", 140, 1, 18, skill_after=990),  # 146/2 compatible mapping
        skill_entry("1", 200, 1, 231, effect_after=0),
    ])


def edit_8850007(img: WzImage) -> None:
    set_skill_entries(img, [
        skill_entry("0", 140, 1, 18, effect_after=990),  # 146/2 compatible mapping
    ])


def edit_8850010(img: WzImage) -> None:
    set_skill_entries(img, [
        skill_entry("0", 114, 2, 42, effect_after=480),
        skill_entry("1", 141, 1, 15, effect_after=980),  # 146/1 compatible mapping
    ])


def replace_between(path: Path, start: str, end: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    pattern = re.escape(start) + r".*?" + re.escape(end)
    new_text, count = re.subn(pattern, start + replacement + end, text, count=1)
    if count != 1:
        raise ValueError(f"{path}: expected one replacement between markers, got {count}")
    path.write_text(new_text, encoding="utf-8")


def patch_xml() -> None:
    mob = ROOT / "gms-server/wz/Mob.wz"
    replace_between(
        mob / "8850011.img.xml",
        '<imgdir name="skill">',
        '</imgdir><imgdir name="ban">',
        '<imgdir name="0"><int name="skill" value="133"/><int name="action" value="3"/><int name="level" value="8"/><int name="skillAfter" value="1760"/></imgdir>'
        '<imgdir name="1"><int name="skill" value="129"/><int name="action" value="1"/><int name="level" value="13"/><int name="skillAfter" value="990"/></imgdir>'
        '<imgdir name="2"><int name="skill" value="200"/><int name="action" value="2"/><int name="level" value="223"/><int name="skillAfter" value="1440"/></imgdir>'
        '<imgdir name="3"><int name="skill" value="132"/><int name="action" value="4"/><int name="level" value="8"/><int name="skillAfter" value="1260"/><int name="effectAfter" value="1260"/></imgdir>'
        '<imgdir name="4"><int name="skill" value="145"/><int name="action" value="6"/><int name="level" value="9"/><int name="effectAfter" value="0"/></imgdir>'
        '<imgdir name="5"><int name="skill" value="200"/><int name="action" value="5"/><int name="level" value="222"/><int name="skillAfter" value="1440"/><int name="preSkillIndex" value="7"/><int name="preSkillCount" value="5"/></imgdir>'
        '<imgdir name="6"><int name="skill" value="131"/><int name="action" value="7"/><int name="level" value="16"/><int name="effectAfter" value="630"/><int name="skillAfter" value="630"/></imgdir>'
        '<imgdir name="7"><int name="skill" value="200"/><int name="action" value="5"/><int name="level" value="221"/><int name="skillAfter" value="1440"/></imgdir>'
        '<imgdir name="8"><int name="skill" value="200"/><int name="action" value="2"/><int name="level" value="228"/><int name="skillAfter" value="1440"/></imgdir>'
        '<imgdir name="9"><int name="skill" value="114"/><int name="action" value="7"/><int name="level" value="43"/><int name="skillAfter" value="630"/></imgdir>'
        '<imgdir name="10"><int name="skill" value="128"/><int name="action" value="7"/><int name="level" value="18"/><int name="skillAfter" value="630"/></imgdir>',
    )
    text = (mob / "8850011.img.xml").read_text(encoding="utf-8")
    text = text.replace(
        '<imgdir name="attack4"><imgdir name="info">',
        '<imgdir name="attack4"><imgdir name="info"><int name="disease" value="132"/><int name="level" value="8"/>',
        1,
    ) if '<imgdir name="attack4"><imgdir name="info"><int name="disease"' not in text else text
    (mob / "8850011.img.xml").write_text(text, encoding="utf-8")

    replace_between(
        mob / "8850002.img.xml",
        '<imgdir name="skill">',
        '</imgdir><int name="firstAttack"',
        '<imgdir name="0"><int name="skill" value="140"/><int name="action" value="1"/><int name="level" value="18"/><int name="skillAfter" value="990"/></imgdir>'
        '<imgdir name="1"><int name="skill" value="200"/><int name="action" value="1"/><int name="level" value="231"/><int name="effectAfter" value="0"/></imgdir>',
    )
    text = (mob / "8850007.img.xml").read_text(encoding="utf-8")
    skill_xml = '<imgdir name="skill"><imgdir name="0"><int name="skill" value="140"/><int name="action" value="1"/><int name="level" value="18"/><int name="effectAfter" value="990"/></imgdir></imgdir>'
    if '<imgdir name="skill">' not in text:
        text = text.replace('<int name="firstAttack"', skill_xml + '<int name="firstAttack"', 1)
    else:
        text = re.sub(r'<imgdir name="skill">.*?</imgdir><int name="firstAttack"', skill_xml + '<int name="firstAttack"', text, count=1)
    (mob / "8850007.img.xml").write_text(text, encoding="utf-8")

    replace_between(
        mob / "8850010.img.xml",
        '<imgdir name="skill">',
        '</imgdir><int name="removeAfter"',
        '<imgdir name="0"><int name="skill" value="114"/><int name="action" value="2"/><int name="level" value="42"/><int name="effectAfter" value="480"/></imgdir>'
        '<imgdir name="1"><int name="skill" value="141"/><int name="action" value="1"/><int name="level" value="15"/><int name="effectAfter" value="980"/></imgdir>',
    )


def main() -> int:
    mob = ROOT / "clien/Data/Mob"
    save_img(mob / "8850011.img", edit_8850011)
    save_img(mob / "8850002.img", edit_8850002)
    save_img(mob / "8850007.img", edit_8850007)
    save_img(mob / "8850010.img", edit_8850010)
    patch_xml()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
