#!/usr/bin/env python3
"""Contract checks for the v79 Frenzy Totem equipment and skill resources."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_frenzy_totem_resources as patch  # noqa: E402
from wzpy import WzSubProperty  # noqa: E402


def direct_child(parent: ET.Element, name: str) -> ET.Element:
    matches = [child for child in parent if child.get("name") == name]
    assert len(matches) == 1, (name, len(matches))
    return matches[0]


def xml_record(path: Path, parent_path: tuple[str, ...], name: str) -> ET.Element:
    parent = ET.parse(path).getroot()
    for part in parent_path:
        parent = direct_child(parent, part)
    return direct_child(parent, name)


def find_xml_record(path: Path, name: str) -> ET.Element | None:
    return next((child for child in ET.parse(path).getroot()
                 if child.get("name") == name), None)


def raw_xml_children(text: str, parent_path: tuple[str, ...]):
    parent = patch.arc.scan_xml(text)
    for part in parent_path:
        matches = [child for child in parent.children if child.name == part]
        assert len(matches) == 1, (parent_path, part, len(matches))
        parent = matches[0]
    return tuple(
        (child.name, text[child.start:child.end]) for child in parent.children
    )


def semantic(node):
    details = []
    for attribute in ("value", "x", "y", "width", "height", "format", "format2"):
        if hasattr(node, attribute):
            details.append((attribute, getattr(node, attribute)))
    if getattr(node, "_png_data", None) is not None:
        details.append(("png", bytes(node._png_data)))
    return (
        node.name,
        type(node).__name__,
        tuple(details),
        tuple(semantic(child) for child in node.children()),
    )


def main() -> int:
    first = patch.build_expected()
    second = patch.build_expected()
    assert first.keys() == second.keys()
    for path, (_baseline, result) in first.items():
        assert path.read_bytes() == result, path
        assert second[path][1] == result, path

    equip = patch.checked_image(first[patch.CLIENT_EQUIP][1], patch.CLIENT_EQUIP.name)
    assert equip.root.get("info/islot").value == "Po"
    assert equip.root.get("info/vslot").value == "Po"
    assert equip.root.get("info/cash").value == 0
    assert patch.visible_canvases(equip.root) == {
        "info/icon": (27, 34), "info/iconRaw": (27, 34)
    }
    assert patch.ITEM_ID == 1189999
    assert patch.ITEM_ID // 1_000_000 == 1

    skill_image = patch.checked_image(first[patch.CLIENT_SKILL][1], patch.CLIENT_SKILL.name)
    skill = skill_image.root.get(f"skill/{patch.SKILL_ID}")
    assert isinstance(skill, WzSubProperty)
    assert skill.get("invisible").value == 0
    assert skill.get("disable").value == 0
    assert skill.get("timeLimited").value == 0
    assert skill.get("level/1/cooltime").value == 0
    assert skill.get("level/1/time").value == 600
    assert skill.get("level/1/mpCon") is None
    assert skill.get("level/2") is None
    assert skill.get("action/0").value == "alert2"
    assert skill.get("effect0/z").value == -2
    visible_skill_canvases = patch.visible_canvases(skill)
    assert len(visible_skill_canvases) == 44
    assert visible_skill_canvases["icon"] == (32, 32)
    assert visible_skill_canvases["iconMouseOver"] == (32, 32)
    assert visible_skill_canvases["iconDisabled"] == (32, 32)
    assert visible_skill_canvases["effect/0"] == (144, 115)
    assert visible_skill_canvases["effect/1"] == (140, 99)
    assert visible_skill_canvases["effect0/0"] == (167, 166)
    assert visible_skill_canvases["effect0/1"] == (161, 165)
    assert visible_skill_canvases["summon/summoned/12"] == (138, 212)
    assert visible_skill_canvases["summon/stand/0"] == (138, 212)
    assert visible_skill_canvases["summon/attack1/0"] == (138, 212)
    assert visible_skill_canvases["summon/die/5"] == (177, 52)
    for animation_name, frame_count in (("summoned", 13), ("stand", 9), ("attack1", 9), ("die", 6)):
        animation = skill.get(f"summon/{animation_name}")
        assert isinstance(animation, WzSubProperty)
        frames = tuple(child for child in animation.children() if child.name != "info")
        assert len(frames) == frame_count
        for frame in frames:
            assert frame.get("delay").value > 0
    attack_info = skill.get("summon/attack1/info")
    assert isinstance(attack_info, WzSubProperty)
    assert (attack_info.get("range/lt").x, attack_info.get("range/lt").y) == (-80, -220)
    assert (attack_info.get("range/rb").x, attack_info.get("range/rb").y) == (80, 20)
    assert attack_info.get("attackAfter").value == 270
    assert attack_info.get("mobCount").value == 1
    assert attack_info.get("type").value == 0
    assert tuple(child.name for child in skill.get("summon").children()) == (
        "summoned", "stand", "attack1", "die"
    )

    skill_string = patch.checked_image(
        first[patch.CLIENT_SKILL_STRING][1], patch.CLIENT_SKILL_STRING.name
    ).root.get(patch.SKILL_ID)
    assert isinstance(skill_string, WzSubProperty)
    assert skill_string.get("name").value == "轮回"
    assert "20分钟" in skill_string.get("desc").value

    equip_string = patch.checked_image(
        first[patch.CLIENT_EQP_STRING][1], patch.CLIENT_EQP_STRING.name
    ).root.get(f"Eqp/Accessory/{patch.ITEM_ID}")
    assert isinstance(equip_string, WzSubProperty)
    assert equip_string.get("name").value == patch.ITEM_NAME

    for path in patch.SERVER_EQP_STRINGS:
        record = xml_record(path, ("Eqp", "Accessory"), str(patch.ITEM_ID))
        assert direct_child(record, "name").get("value") == patch.ITEM_NAME
    equip_xml = ET.parse(patch.SERVER_EQUIP).getroot()
    assert direct_child(direct_child(equip_xml, "info"), "cash").get("value") == "0"
    info = direct_child(equip_xml, "info")
    assert direct_child(info, "incSTR").get("value") == "20"
    assert direct_child(info, "incDEX").get("value") == "20"
    assert direct_child(info, "incINT").get("value") == "20"
    assert direct_child(info, "incLUK").get("value") == "20"
    assert direct_child(info, "incMHP").get("value") == "2000"
    assert direct_child(info, "incMMP").get("value") == "2000"
    for path in patch.SERVER_SKILL_STRINGS:
        record = xml_record(path, (), patch.SKILL_ID)
        assert direct_child(record, "name").get("value") == "轮回"
    skill_xml = xml_record(patch.SERVER_SKILL, ("skill",), patch.SKILL_ID)
    assert direct_child(direct_child(skill_xml, "action"), "0").get("value") == "alert2"
    effect = direct_child(skill_xml, "effect")
    assert direct_child(effect, "0").get("width") == "144"
    assert direct_child(effect, "1").get("width") == "140"
    effect0 = direct_child(skill_xml, "effect0")
    assert direct_child(effect0, "0").get("width") == "167"
    assert direct_child(effect0, "z").get("value") == "-2"
    level = direct_child(direct_child(skill_xml, "level"), "1")
    assert direct_child(level, "cooltime").get("value") == "0"
    assert direct_child(level, "time").get("value") == "600"
    summon = direct_child(skill_xml, "summon")
    assert [child.get("name") for child in summon] == ["summoned", "stand", "attack1", "die"]
    assert len(direct_child(summon, "summoned")) == 13
    assert len(direct_child(summon, "stand")) == 9
    attack1 = direct_child(summon, "attack1")
    assert len([child for child in attack1 if child.get("name") != "info"]) == 9
    attack_info = direct_child(attack1, "info")
    attack_range = direct_child(attack_info, "range")
    lt = direct_child(attack_range, "lt")
    rb = direct_child(attack_range, "rb")
    assert (lt.get("x"), lt.get("y")) == ("-80", "-220")
    assert (rb.get("x"), rb.get("y")) == ("80", "20")
    assert direct_child(attack_info, "attackAfter").get("value") == "270"
    assert direct_child(attack_info, "mobCount").get("value") == "1"
    assert direct_child(attack_info, "type").get("value") == "0"
    assert len(direct_child(summon, "die")) == 6

    assert not patch.OBSOLETE_CLIENT_MOB.exists()
    assert not patch.OBSOLETE_SERVER_MOB.exists()
    assert patch.checked_image(
        first[patch.CLIENT_MOB_STRING][1], patch.CLIENT_MOB_STRING.name
    ).root.get(str(patch.OBSOLETE_MOB_ID)) is None
    for path in patch.SERVER_MOB_STRINGS:
        assert find_xml_record(path, str(patch.OBSOLETE_MOB_ID)) is None

    assert patch.checked_image(
        patch.LEGACY_CLIENT_INSTALL.read_bytes(), patch.LEGACY_CLIENT_INSTALL.name
    ).root.get(f"0{patch.OBSOLETE_ITEM_ID}") is None
    assert patch.checked_image(
        patch.LEGACY_CLIENT_INS_STRING.read_bytes(), patch.LEGACY_CLIENT_INS_STRING.name
    ).root.get(str(patch.OBSOLETE_ITEM_ID)) is None
    assert find_xml_record(patch.LEGACY_SERVER_INSTALL, f"0{patch.OBSOLETE_ITEM_ID}") is None
    for path in patch.LEGACY_SERVER_INS_STRINGS:
        assert find_xml_record(path, str(patch.OBSOLETE_ITEM_ID)) is None
    assert not patch.OBSOLETE_CLIENT_EQUIP.exists()
    assert not patch.OBSOLETE_SERVER_EQUIP.exists()

    before_skill = patch.checked_image(
        patch.git_baseline(patch.CLIENT_SKILL), patch.CLIENT_SKILL.name
    ).root.get("skill")
    after_skill = patch.checked_image(
        first[patch.CLIENT_SKILL][1], patch.CLIENT_SKILL.name
    ).root.get("skill")
    before_others = tuple(semantic(child) for child in before_skill.children()
                          if child.name != patch.SKILL_ID)
    after_others = tuple(semantic(child) for child in after_skill.children()
                         if child.name != patch.SKILL_ID)
    assert before_others == after_others
    assert semantic(before_skill.get(patch.SOURCE_SKILL_ID)) == semantic(
        after_skill.get(patch.SOURCE_SKILL_ID)
    )
    patch.arc.verify_raw_record_insert_scope(
        patch.git_baseline(patch.CLIENT_SKILL),
        first[patch.CLIENT_SKILL][1],
        {("skill", patch.SKILL_ID)},
    )
    patch.arc.verify_raw_record_insert_scope(
        patch.git_baseline(patch.CLIENT_SKILL_STRING),
        first[patch.CLIENT_SKILL_STRING][1],
        {(patch.SKILL_ID,)},
    )
    original_skill_string = patch.checked_image(
        patch.git_baseline(patch.CLIENT_SKILL_STRING),
        patch.CLIENT_SKILL_STRING.name,
    ).root.get(patch.SOURCE_SKILL_ID)
    current_skill_string = patch.checked_image(
        first[patch.CLIENT_SKILL_STRING][1],
        patch.CLIENT_SKILL_STRING.name,
    ).root.get(patch.SOURCE_SKILL_ID)
    assert semantic(original_skill_string) == semantic(current_skill_string)
    for path, parent_path in (
        (patch.SERVER_SKILL, ("skill",)),
        *[(path, ()) for path in patch.SERVER_SKILL_STRINGS],
    ):
        baseline_text = patch.git_baseline(path).decode("utf-8")
        current_text = first[path][1].decode("utf-8")
        baseline_records = raw_xml_children(baseline_text, parent_path)
        current_records = raw_xml_children(current_text, parent_path)
        assert tuple(name for name, _raw in current_records) == (
            *(name for name, _raw in baseline_records), patch.SKILL_ID
        )
        assert current_records[:-1] == baseline_records

    beginner_source = (
        patch.ROOT
        / "gms-server/src/main/java/org/gms/constants/skills/Beginner.java"
    ).read_text()
    assert "SPACESHIP = 1013" in beginner_source
    assert "FRENZY_TOTEM = 1016" in beginner_source
    assert patch.checked_image(
        first[patch.CLIENT_EQP_STRING][1], patch.CLIENT_EQP_STRING.name
    ).root.get(f"Eqp/Weapon/{patch.SOURCE_EQUIP_ID}") is None

    print(
        "Frenzy Totem resource contract ok: item=1189999 equipment; slot=53; "
        "skill=0001016 beginner; original beginner skills preserved; "
        "v79 0001013 effect/effect0; cooldown=0 in WZ, 20min enforced on skill use; "
        "stationary summon visual; legacy mob removed; idempotent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
