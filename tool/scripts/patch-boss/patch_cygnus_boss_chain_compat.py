#!/usr/bin/env python3
"""Patch Cygnus boss-chain skill refs to what the current client supports."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


KEY = WzKey.for_region("GMS")


def child(node, name: str):
    return node.child(name) if node is not None and hasattr(node, "child") else None


def set_scalar(node, value: int) -> None:
    if node is None:
        raise ValueError("missing scalar node")
    node._value = str(value) if isinstance(getattr(node, "value", None), str) else value


def save_img(path: Path, edits) -> None:
    img = WzImage.from_bytes(path.read_bytes(), key=KEY, name=path.name)
    img.parse()
    edits(img)
    data = encode_image_body(img, img.wz_file.reader)
    path.write_bytes(data)


def edit_8850000(img: WzImage) -> None:
    set_scalar(img.get("attack3/info/level"), 14)


def edit_8850002(img: WzImage) -> None:
    remove_skill(img, 146)
    set_scalar(img.get("attack2/info/level"), 26)
    set_scalar(img.get("attack3/info/level"), 26)


def remove_skill(img: WzImage, skill_id: int) -> None:
    info = img.get("info")
    skills = child(info, "skill")
    if skills is None:
        return
    remove_names = [
        entry.name
        for entry in skills.children()
        if child(entry, "skill") is not None and child(entry, "skill").value == skill_id
    ]
    for name in remove_names:
        del skills._children[name]
    if not skills.children():
        del info._children["skill"]
        return
    for idx, entry in enumerate(sorted(skills.children(), key=lambda p: int(p.name))):
        old_name = entry.name
        new_name = str(idx)
        if old_name == new_name:
            continue
        del skills._children[old_name]
        entry.name = new_name
        skills._children[new_name] = entry


def edit_8850005(img: WzImage) -> None:
    set_scalar(img.get("attack3/info/level"), 14)


def edit_8850007(img: WzImage) -> None:
    remove_skill(img, 146)
    set_scalar(img.get("attack2/info/level"), 26)
    set_scalar(img.get("attack3/info/level"), 26)


def edit_8850008(img: WzImage) -> None:
    set_scalar(img.get("attack4/info/level"), 26)


def edit_8850010(img: WzImage) -> None:
    remove_skill(img, 146)


def edit_8850003(img: WzImage) -> None:
    set_scalar(img.get("attack4/info/level"), 26)


def replace_once(path: Path, pattern: str, replacement: str, *, already: str | None = None) -> None:
    text = path.read_text(encoding="utf-8")
    new_text, count = re.subn(pattern, replacement, text, count=1)
    if count == 0 and already is not None and already in text:
        return
    if count != 1:
        raise ValueError(f"{path}: expected one replacement, got {count}")
    path.write_text(new_text, encoding="utf-8")


def replace_all(path: Path, old: str, new: str, expected: int) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count == 0 and text.count(new) >= expected:
        return
    if count != expected:
        raise ValueError(f"{path}: expected {expected} replacements for {old!r}, got {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def remove_once_if_skill_absent(path: Path, pattern: str, skill_id: int) -> None:
    text = path.read_text(encoding="utf-8")
    new_text, count = re.subn(pattern, "", text, count=1)
    if count == 0 and f'<int name="skill" value="{skill_id}"/>' not in text:
        return
    if count != 1:
        raise ValueError(f"{path}: expected one skill removal, got {count}")
    path.write_text(new_text, encoding="utf-8")


def patch_xml() -> None:
    mob_xml = ROOT / "gms-server/wz/Mob.wz"
    replace_once(
        mob_xml / "8850000.img.xml",
        r'(<imgdir name="attack3"><imgdir name="info">.*?<int name="disease" value="121"/><string name="level" value=")15(")',
        r"\g<1>14\2",
        already='<int name="disease" value="121"/><string name="level" value="14"/>',
    )
    replace_all(
        mob_xml / "8850002.img.xml",
        '<int name="disease" value="123"/><int name="level" value="32"/>',
        '<int name="disease" value="123"/><int name="level" value="26"/>',
        2,
    )
    replace_once(
        mob_xml / "8850002.img.xml",
        r'<imgdir name="0"><int name="skill" value="146"/><int name="action" value="1"/><int name="level" value="2"/><int name="skillAfter" value="990"/></imgdir><imgdir name="1">',
        '<imgdir name="0">',
        already='<imgdir name="0"><int name="skill" value="200"/><int name="action" value="1"/><int name="level" value="231"/>',
    )
    replace_once(
        mob_xml / "8850003.img.xml",
        r'(<imgdir name="attack4"><imgdir name="info">.*?<int name="disease" value="123"/><int name="level" value=")33(")',
        r"\g<1>26\2",
        already='<int name="disease" value="123"/><int name="level" value="26"/>',
    )
    replace_once(
        mob_xml / "8850005.img.xml",
        r'(<imgdir name="attack3"><imgdir name="info">.*?<int name="disease" value="121"/><string name="level" value=")15(")',
        r"\g<1>14\2",
        already='<int name="disease" value="121"/><string name="level" value="14"/>',
    )
    replace_all(
        mob_xml / "8850007.img.xml",
        '<int name="disease" value="123"/><int name="level" value="32"/>',
        '<int name="disease" value="123"/><int name="level" value="26"/>',
        2,
    )
    remove_once_if_skill_absent(
        mob_xml / "8850007.img.xml",
        r'<imgdir name="skill"><imgdir name="0"><int name="skill" value="146"/><int name="action" value="1"/><int name="level" value="2"/><int name="effectAfter" value="990"/></imgdir></imgdir>',
        146,
    )
    replace_once(
        mob_xml / "8850008.img.xml",
        r'(<imgdir name="attack4"><imgdir name="info">.*?<int name="disease" value="123"/><int name="level" value=")33(")',
        r"\g<1>26\2",
        already='<int name="disease" value="123"/><int name="level" value="26"/>',
    )
    remove_once_if_skill_absent(
        mob_xml / "8850010.img.xml",
        r'<imgdir name="1"><int name="skill" value="146"/><int name="action" value="1"/><int name="level" value="1"/><int name="effectAfter" value="980"/></imgdir>',
        146,
    )


def main() -> int:
    mob = ROOT / "clien/Data/Mob"
    save_img(mob / "8850000.img", edit_8850000)
    save_img(mob / "8850002.img", edit_8850002)
    save_img(mob / "8850003.img", edit_8850003)
    save_img(mob / "8850005.img", edit_8850005)
    save_img(mob / "8850007.img", edit_8850007)
    save_img(mob / "8850008.img", edit_8850008)
    save_img(mob / "8850010.img", edit_8850010)
    patch_xml()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
