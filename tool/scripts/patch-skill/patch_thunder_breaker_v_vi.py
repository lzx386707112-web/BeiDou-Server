#!/usr/bin/env python3
"""Migrate TMS Thunder Breaker V/VI attacks into the empty 1512 book."""

from __future__ import annotations

import argparse
import html
import math
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import patch_blaze_wizard_v_vi as engine


ROOT = Path(__file__).resolve().parents[3]
TMS_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
MS_EXPORT_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-MS-Export/ThunderBreaker")
SOURCE_PATHS = {
    "1514": TMS_ROOT / "Skill" / "_Canvas" / "1514.img",
    "40005": TMS_ROOT / "Skill" / "_Canvas" / "40005.img",
}
CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / "1512.img"
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
CLIENT_MAP_EFFECT = ROOT / "clien" / "Data" / "Map" / "Effect.img"
SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / "1512.img.xml"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"
FIELD_EFFECT_ROOT = "customSkill/thunderBreaker"
VIDEO_MARKERS = (
    "godOfSeaViVideoLayer",
    "waveRidingThunderVideoLayer",
    "swiftAnnihilationVideoLayer",
)
MASTER_LEVEL = 30
CUSTOM_SKILL_IDS = range(15121000, 15121021)

SkillSpec = engine.SkillSpec


# Values are evaluated from the TMS level-30 common expressions. The hidden
# nodes retain the source damage, line count, target cap and attack rectangle
# used by server-side continuous and multi-stage replay.
SKILLS = (
    SkillSpec(15121000, 400051015, "40005", "海龙螺旋", 780, 3, 10, 300, 60, False,
              effect_nodes=("effect", "effect0"),
              extra_nodes=("special", "special0", "end", "end0"),
              lt=(-275, -145), rb=(275, 55), duration_seconds=24),
    SkillSpec(15121001, 400051016, "40005", "巨鲨狂浪", 2420, 7, 15, 500, 8, False,
              projectile_nodes=("shootobj/layerList/b1",),
              lt=(-980, -215), rb=(-30, 25)),
    SkillSpec(15121002, 400051058, "40005", "枪雷连击", 1430, 5, 4, 1000, 120, False,
              effect_source_id=400051059, hit_source_id=400051059,
              lt=(-650, -400), rb=(450, 300)),
    SkillSpec(15121003, 400051059, "40005", "枪雷连击：一式", 1430, 5, 4, 1000,
              icon_source_id=400051058, lt=(-415, -300), rb=(30, 15)),
    SkillSpec(15121004, 400051060, "40005", "枪雷连击：二式", 1430, 5, 4, 1000,
              icon_source_id=400051058, lt=(-415, -300), rb=(30, 15)),
    SkillSpec(15121005, 400051061, "40005", "枪雷连击：三式", 1430, 5, 4, 1000,
              icon_source_id=400051058, lt=(-415, -300), rb=(30, 15)),
    SkillSpec(15121006, 400051062, "40005", "枪雷连击：四式", 1430, 5, 4, 1000,
              icon_source_id=400051058, lt=(-415, -300), rb=(30, 15)),
    SkillSpec(15121007, 400051063, "40005", "枪雷连击：五式", 1430, 5, 4, 1000,
              icon_source_id=400051058, lt=(-415, -300), rb=(30, 15)),
    SkillSpec(15121008, 400051064, "40005", "枪雷连击：六式", 1430, 5, 4, 1000,
              icon_source_id=400051058, lt=(-415, -300), rb=(30, 15)),
    SkillSpec(15121009, 400051065, "40005", "枪雷连击：落雷", 1555, 4, 3,
              icon_source_id=400051058, lt=(-120, -500), rb=(120, 5)),
    SkillSpec(15121010, 400051066, "40005", "枪雷连击：终式", 1990, 7, 7, 1000,
              icon_source_id=400051058, lt=(-415, -490), rb=(150, 20)),
    SkillSpec(15121011, 400051067, "40005", "枪雷连击：巨大落雷", 2145, 6, 8,
              icon_source_id=400051058, lt=(-220, -700), rb=(220, 5)),

    SkillSpec(15121012, 15141000, "1514", "消灭VI", 500, 7, 3, 80, 0, False,
              effect_nodes=("effect", "effect0"), lt=(-410, -215), rb=(80, 35)),
    SkillSpec(15121013, 15141003, "1514", "霹雳VI", 515, 5, 8, 84, 0, False,
              lt=(-460, -275), rb=(60, 85)),
    SkillSpec(15121014, 15141004, "1514", "霹雳VI：霹雳闪", 545, 5, 12, 90, 6,
              icon_source_id=15141003, lt=(-420, -430), rb=(340, 100)),
    SkillSpec(15121015, 15141006, "1514", "台风VI", 859, 5, 8, 59, 12, False,
              lt=(-550, -320), rb=(80, 120), duration_seconds=95),
    SkillSpec(15121016, 15141007, "1514", "海神降临VI", 1380, 7, 15, 410, 45, False,
              lt=(-550, -330), rb=(550, 300)),
    SkillSpec(15121017, 15141500, "1514", "浪驰雷掣", 1390, 5, 15, 1200, 360, False,
              effect_nodes=(), lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(15121018, 15141501, "1514", "浪驰雷掣：雷海冲击", 1370, 7, 15,
              icon_source_id=15141500, effect_nodes=(),
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(15121019, 15141502, "1514", "疾浪歼灭", 6160, 12, 15, 1000, 240, False,
              effect_nodes=("effect", "effect2"),
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(15121020, 15141503, "1514", "疾浪歼灭：激流", 6510, 15, 15,
              icon_source_id=15141502, effect_nodes=(),
              lt=(-1200, -800), rb=(1200, 800)),
)

VISIBLE_IDS = {spec.target_id for spec in SKILLS if not spec.hidden}
AREA_ATTACK_IDS = {spec.target_id for spec in SKILLS if spec.mob_count > 1}


def configure_engine() -> None:
    engine.TMS_ROOT = TMS_ROOT
    engine.MS_EXPORT_ROOT = MS_EXPORT_ROOT
    engine.SOURCE_PATHS = SOURCE_PATHS
    engine.CLIENT_SKILL = CLIENT_SKILL
    engine.CLIENT_STRING = CLIENT_STRING
    engine.CLIENT_MAP_EFFECT = CLIENT_MAP_EFFECT
    engine.SERVER_SKILL = SERVER_SKILL
    engine.SERVER_STRING = SERVER_STRING
    engine.FIELD_EFFECT_ROOT = FIELD_EFFECT_ROOT
    engine.VIDEO_MARKERS = VIDEO_MARKERS
    engine.MASTER_LEVEL = MASTER_LEVEL
    engine.CUSTOM_SKILL_IDS = CUSTOM_SKILL_IDS
    engine.SKILLS = SKILLS
    engine.TIMED_EFFECTS = {}
    engine.base.SKILLS = SKILLS
    engine.base.MS_EXPORT_ROOT = MS_EXPORT_ROOT


def backup(path: Path) -> None:
    target = path.with_name(path.name + ".bak-thunder-breaker-v-vi")
    if not target.exists():
        shutil.copy2(path, target)
        print(f"backup: {target}")


def action_for(spec: SkillSpec) -> str:
    return "wave" if spec.target_id == 15121001 else "fist"


def build_skill(spec, parent, key, groups, metadata):
    target = engine.build_skill_original(spec, parent, key, groups, metadata)
    engine.set_string(target.child("action"), "0", action_for(spec))
    if spec.target_id in AREA_ATTACK_IDS:
        info = engine.WzSubProperty("info", target)
        engine.set_int(info, "type", 1)
        engine.set_int(info, "areaAttack", 1)
        engine.base.replace_child(target, info)
    engine.set_string(target, "elemAttr", "l")
    engine.set_int(target, "weapon", 48)
    engine.set_int(target, "weapon2", 39)
    return target


def level_text(spec: SkillSpec) -> str:
    cooldown = f"，冷却时间{spec.cooldown}秒" if spec.cooldown else ""
    duration = f"，兼容持续{spec.duration_seconds}秒" if spec.duration_seconds else ""
    return (f"消耗MP {spec.mp_con}，最多攻击{spec.mob_count}名敌人，"
            f"以{spec.damage}%伤害攻击{spec.attack_count}次{duration}{cooldown}                    ")


def server_skill_block(spec: SkillSpec) -> str:
    lines = [f'  <imgdir name="{spec.target_id}">', '    <imgdir name="action">',
             f'      <string name="0" value="{action_for(spec)}"/>', "    </imgdir>",
             '    <imgdir name="level">']
    for level in range(1, MASTER_LEVEL + 1):
        lines.extend([
            f'      <imgdir name="{level}">',
            f'        <int name="attackCount" value="{min(15, spec.attack_count)}"/>',
            f'        <int name="cooltime" value="{spec.cooldown}"/>',
            f'        <int name="damage" value="{spec.damage}"/>',
            f'        <string name="hs" value="h{level}"/>',
            f'        <vector name="lt" x="{spec.lt[0]}" y="{spec.lt[1]}"/>',
            f'        <int name="mobCount" value="{min(15, spec.mob_count)}"/>',
            f'        <int name="mpCon" value="{spec.mp_con}"/>',
            f'        <vector name="rb" x="{spec.rb[0]}" y="{spec.rb[1]}"/>',
            *([f'        <int name="time" value="{spec.duration_seconds}"/>']
              if spec.duration_seconds is not None else []),
            "      </imgdir>",
        ])
    lines.extend([
        "    </imgdir>",
        f'    <int name="masterLevel" value="{MASTER_LEVEL}"/>',
        '    <string name="elemAttr" value="l"/>',
        '    <int name="weapon" value="48"/>',
        '    <int name="weapon2" value="39"/>',
    ])
    if spec.target_id in AREA_ATTACK_IDS:
        lines.extend(['    <imgdir name="info">', '      <int name="type" value="1"/>',
                      '      <int name="areaAttack" value="1"/>', '    </imgdir>'])
    if spec.hidden:
        lines.append('    <int name="invisible" value="1"/>')
    lines.append("  </imgdir>")
    return "\n".join(lines)


def patch_server_skill(dry_run: bool) -> None:
    text = SERVER_SKILL.read_text(encoding="utf-8")
    info_start, info_end = engine.find_imgdir_block(text, "info")
    info = text[info_start:info_end]
    blocks = "\n".join(server_skill_block(spec) for spec in SKILLS)
    updated = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
               f'<imgdir name="1512.img">\n{info}\n<imgdir name="skill">\n'
               f'{blocks}\n</imgdir>\n</imgdir>\n')
    if not dry_run:
        backup(SERVER_SKILL)
        engine.base.atomic_write_text(SERVER_SKILL, updated)


def patch_client_string(strings, dry_run: bool) -> None:
    image = engine.WzImage.from_bytes(
        CLIENT_STRING.read_bytes(), key=engine.WzKey.for_region("GMS"), name=CLIENT_STRING.name
    )
    root = image.parse()
    for skill_id in CUSTOM_SKILL_IDS:
        root._children.pop(str(skill_id), None)
    for spec in SKILLS:
        source = engine.source_string_values(strings, spec.source_id)
        node = engine.WzSubProperty(str(spec.target_id), root)
        engine.set_string(node, "name", spec.name)
        engine.set_string(node, "desc", source.get("desc", "TMS奇袭者五/六转攻击技能兼容迁移。"))
        for level in range(1, MASTER_LEVEL + 1):
            engine.set_string(node, f"h{level}", level_text(spec))
        engine.base.replace_child(root, node)
    if not dry_run:
        backup(CLIENT_STRING)
        engine.base.atomic_write_bytes(CLIENT_STRING, engine.encode_image_body(image, image.wz_file.reader))


def server_string_block(spec: SkillSpec, source: dict[str, str]) -> str:
    lines = [f'<imgdir name="{spec.target_id}">',
             f'  <string name="name" value="{html.escape(spec.name, quote=True)}"/>',
             f'  <string name="desc" value="{html.escape(source.get("desc", "TMS奇袭者五/六转攻击技能兼容迁移。"), quote=True)}"/>']
    for level in range(1, MASTER_LEVEL + 1):
        lines.append(f'  <string name="h{level}" value="{html.escape(level_text(spec), quote=True)}"/>')
    lines.append("</imgdir>")
    return "\n".join(lines)


def evaluate_common_value(node: ET.Element | None, default: int = 0) -> int:
    if node is None:
        return default
    value = node.get("value")
    if value is None:
        return default
    return int(eval(value, {"__builtins__": {}}, {"x": 30, "d": math.floor}))


def validate_source_parameters() -> None:
    for spec in SKILLS:
        root = ET.parse(MS_EXPORT_ROOT / f"{spec.source_id}.xml").getroot()
        common = next(
            (child for child in root if child.tag == "imgdir" and child.get("name") == "common"),
            None,
        )
        if common is None:
            raise RuntimeError(f"missing source common node: {spec.source_id}")
        values = {child.get("name"): child for child in common}
        actual = (
            evaluate_common_value(values.get("damage")),
            evaluate_common_value(values.get("attackCount"), 1),
            evaluate_common_value(values.get("mobCount"), 1),
            evaluate_common_value(values.get("mpCon")),
            evaluate_common_value(values.get("cooltime")),
        )
        expected = (spec.damage, spec.attack_count, spec.mob_count, spec.mp_con, spec.cooldown)
        if actual != expected:
            raise RuntimeError(
                f"TMS level-30 parameter mismatch {spec.source_id}->{spec.target_id}: "
                f"source={actual} spec={expected}"
            )
        if "lt" in values and "rb" in values:
            source_range = (
                int(values["lt"].get("x")), int(values["lt"].get("y")),
                int(values["rb"].get("x")), int(values["rb"].get("y")),
            )
            if source_range != (*spec.lt, *spec.rb):
                raise RuntimeError(
                    f"TMS range mismatch {spec.source_id}->{spec.target_id}: "
                    f"source={source_range} spec={(*spec.lt, *spec.rb)}"
                )


def validate() -> None:
    validate_source_parameters()
    image = engine.WzImage.from_bytes(
        CLIENT_SKILL.read_bytes(), key=engine.WzKey.for_region("GMS"), name=CLIENT_SKILL.name
    )
    root = image.parse()
    actual = {
        int(child.name) for child in root.get("skill").children()
        if child.name.isdigit() and int(child.name) in CUSTOM_SKILL_IDS
    }
    expected = {spec.target_id for spec in SKILLS}
    if actual != expected:
        raise RuntimeError(f"Thunder Breaker skill mismatch: missing={sorted(expected-actual)} extra={sorted(actual-expected)}")
    canvas_count = 0
    for spec in SKILLS:
        node = root.get(f"skill/{spec.target_id}")
        if not isinstance(node, engine.WzSubProperty):
            raise RuntimeError(f"missing client skill {spec.target_id}")
        action = node.get("action/0")
        if action is None or action.value != action_for(spec):
            raise RuntimeError(f"action mismatch {spec.target_id}")
        level = node.get(f"level/{MASTER_LEVEL}")
        values = (int(level.get("damage").value), int(level.get("attackCount").value),
                  int(level.get("mobCount").value), int(level.get("mpCon").value),
                  int(level.get("cooltime").value))
        expected_values = (spec.damage, spec.attack_count, spec.mob_count, spec.mp_con, spec.cooldown)
        if values != expected_values:
            raise RuntimeError(f"attack parameter mismatch {spec.target_id}: {values}")
        lt = level.get("lt")
        rb = level.get("rb")
        if (int(lt.x), int(lt.y), int(rb.x), int(rb.y)) != (*spec.lt, *spec.rb):
            raise RuntimeError(f"range mismatch {spec.target_id}")
        invisible = node.get("invisible")
        if (invisible is not None) != spec.hidden:
            raise RuntimeError(f"visibility mismatch {spec.target_id}")
        stack = [node]
        while stack:
            current = stack.pop()
            if isinstance(current, engine.WzCanvasProperty):
                canvas_count += 1
                if int(current.format) != 1 or int(current.format2) != 0:
                    raise RuntimeError(f"non-ARGB4444 Canvas in {spec.target_id}")
                if int(current.width) > 1280 or int(current.height) > 720:
                    raise RuntimeError(f"oversized Canvas in {spec.target_id}: {current.width}x{current.height}")
            if hasattr(current, "children"):
                stack.extend(current.children())
    effect_image = engine.WzImage.from_bytes(
        CLIENT_MAP_EFFECT.read_bytes(), key=engine.WzKey.for_region("GMS"),
        name=CLIENT_MAP_EFFECT.name,
    ).parse()
    for marker_name in VIDEO_MARKERS:
        marker = effect_image.get(f"{FIELD_EFFECT_ROOT}/{marker_name}/0")
        if not isinstance(marker, engine.WzCanvasProperty) or (int(marker.width), int(marker.height)) != (7, 5):
            raise RuntimeError(f"missing MCV marker: {marker_name}")
    server_root = ET.parse(SERVER_SKILL).getroot()
    server_skills = server_root.find("./imgdir[@name='skill']")
    if server_skills is None:
        raise RuntimeError("missing server skill root")
    for spec in SKILLS:
        server_node = server_skills.find(f"./imgdir[@name='{spec.target_id}']")
        if server_node is None:
            raise RuntimeError(f"missing server skill {spec.target_id}")
        action = server_node.find("./imgdir[@name='action']/string[@name='0']")
        if action is None or action.get("value") != action_for(spec):
            raise RuntimeError(f"server action mismatch {spec.target_id}")
    print(f"validated Thunder Breaker V/VI resources: skills={len(SKILLS)} canvases={canvas_count}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    configure_engine()
    if args.validate_only:
        validate()
        return 0
    groups, strings, metadata = engine.load_sources()
    engine.patch_client_skill(groups, metadata, args.dry_run)
    patch_client_string(strings, args.dry_run)
    patch_server_skill(args.dry_run)
    engine.patch_server_string(strings, args.dry_run)
    engine.patch_map_effect(args.dry_run)
    if not args.dry_run:
        validate()
    return 0


configure_engine()
engine.backup = backup
engine.build_skill_original = engine.build_skill
engine.build_skill = build_skill
engine.level_text = level_text
engine.server_skill_block = server_skill_block
engine.patch_server_skill = patch_server_skill
engine.patch_client_string = patch_client_string
engine.server_string_block = server_string_block


if __name__ == "__main__":
    raise SystemExit(main())
