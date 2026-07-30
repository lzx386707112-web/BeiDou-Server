#!/usr/bin/env python3
"""Migrate all TMS Blaze Wizard V/VI attack resources into the empty 1212 book."""

from __future__ import annotations

import argparse
import html
import math
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
PATCH_SKILL = ROOT / "tool" / "scripts" / "patch-skill"
sys.path.insert(0, str(WZPY))
sys.path.insert(0, str(PATCH_SKILL))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.properties import WzCanvasProperty, WzIntProperty, WzSubProperty, WzUolProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402

import patch_dawn_warrior_v_vi as base  # noqa: E402
from patch_1121001_sword_illusion import find_imgdir_block, set_int, set_string, set_vector  # noqa: E402


TMS_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
MS_EXPORT_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-MS-Export/BlazeWizard")
SOURCE_PATHS = {
    "1214": TMS_ROOT / "Skill" / "_Canvas" / "1214.img",
    "40002": TMS_ROOT / "Skill" / "_Canvas" / "40002.img",
}
SOURCE_STRING = TMS_ROOT / "String" / "Skill.img"
CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / "1212.img"
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
CLIENT_MAP_EFFECT = ROOT / "clien" / "Data" / "Map" / "Effect.img"
SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / "1212.img.xml"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"
FIELD_EFFECT_ROOT = "customSkill/blazeWizard"
VIDEO_MARKERS = ("eternalPhoenixVideoLayer", "flameConcertoVideoLayer")
MASTER_LEVEL = 30
CUSTOM_SKILL_IDS = range(12121000, 12121037)


@dataclass(frozen=True)
class SkillSpec:
    target_id: int
    source_id: int
    source_group: str
    name: str
    damage: int
    attack_count: int
    mob_count: int
    mp_con: int = 0
    cooldown: int = 0
    hidden: bool = True
    icon_source_id: int | None = None
    effect_source_id: int | None = None
    effect_nodes: tuple[str, ...] = ("effect", "effect0")
    hit_source_id: int | None = None
    projectile_nodes: tuple[str, ...] = ()
    summon_node: str | None = None
    extra_nodes: tuple[str, ...] = ()
    lt: tuple[int, int] = (-700, -500)
    rb: tuple[int, int] = (700, 300)
    duration_seconds: int | None = None
    include_hit: bool = True


@dataclass(frozen=True)
class TimedEffectSpec:
    intro_nodes: tuple[str, ...]
    loop_nodes: tuple[str, ...]
    end_nodes: tuple[str, ...]
    loop_duration_ms: int
    z: int | None = None


# Hidden stages stay addressable for packet replay, while retired families keep
# their former IDs empty so saved hotkeys cannot resolve to a different skill.
SKILLS = (
    SkillSpec(12121001, 400021042, "40002", "烈炎爆发（火狮）", 1100, 12, 15, 500, 10, False,
              effect_source_id=400021043, hit_source_id=400021043, lt=(-380, -460), rb=(380, 80),
              duration_seconds=18, include_hit=False),
    SkillSpec(12121002, 400021043, "40002", "烈炎爆发：火狮爆裂", 1100, 12, 15,
              icon_source_id=400021042, effect_nodes=(), lt=(-380, -460), rb=(380, 80)),
    SkillSpec(12121003, 400021044, "40002", "烈炎爆发：火狮余焰", 1100, 1, 8,
              icon_source_id=400021042, effect_nodes=(), lt=(-500, -400), rb=(500, 10)),
    SkillSpec(12121004, 400021045, "40002", "烈炎爆发：火狮终焰", 1100, 1, 8,
              icon_source_id=400021042, effect_nodes=(), lt=(-500, -400), rb=(500, 10)),
    SkillSpec(12121007, 400021072, "40002", "无尽之炎燄", 1900, 8, 12, 750, 10, False,
              effect_nodes=("keydown", "keydown0"), extra_nodes=("prepare", "prepare0", "keydownend", "keydownend0", "special"),
              lt=(-380, -460), rb=(380, 300), duration_seconds=5, include_hit=False),
    SkillSpec(12121020, 12140015, "1214", "魔法爆发 VI", 330, 3, 10, 15,
              hit_source_id=12141016, lt=(-700, -450), rb=(700, 250)),
    SkillSpec(12121021, 12141016, "1214", "魔法爆发 VI：火息", 330, 3, 10,
              icon_source_id=12140015, effect_source_id=12140015, lt=(-700, -450), rb=(700, 250)),
    SkillSpec(12121022, 12141010, "1214", "凤凰爆裂 VI", 1800, 6, 8, 330, 10, False,
              extra_nodes=("special", "special0", "end", "end0"), lt=(-390, -230), rb=(390, 80),
              duration_seconds=20, include_hit=False),
    SkillSpec(12121025, 12141500, "1214", "永恒凤炎", 2100, 10, 15, 1200, 10, False,
              effect_nodes=("repeat",), lt=(-1200, -800), rb=(1200, 800), duration_seconds=30,
              include_hit=False),
    SkillSpec(12121026, 12141501, "1214", "永恒凤炎：循环之焰", 3700, 13, 15,
              icon_source_id=12141500, effect_nodes=(), lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(12121027, 12141502, "1214", "永恒凤炎：循环状态", 0, 1, 1,
              icon_source_id=12141500, effect_nodes=(), hit_source_id=12141501),
    SkillSpec(12121028, 12141503, "1214", "炎焰协奏曲", 4340, 12, 15, 769, 10, False,
              effect_nodes=("effect", "effect2"), extra_nodes=("special", "special0"),
              lt=(-1200, -800), rb=(1200, 800), include_hit=False),
    SkillSpec(12121029, 12141504, "1214", "炎焰协奏曲：最终乐章", 7000, 15, 15,
              icon_source_id=12141503, effect_nodes=(),
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(12121030, 400021072, "40002", "无尽之炎燄：持续攻击", 1900, 8, 12,
              icon_source_id=400021072, effect_nodes=(), lt=(-380, -460), rb=(380, 300)),
    SkillSpec(12121033, 12141010, "1214", "凤凰爆裂 VI：持续攻击", 1800, 6, 8,
              icon_source_id=12141010, effect_nodes=(), lt=(-390, -230), rb=(390, 80)),
    SkillSpec(12121035, 12141500, "1214", "永恒凤炎：初始焰击", 2100, 10, 15,
              icon_source_id=12141500, effect_nodes=(), lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(12121036, 12141503, "1214", "炎焰协奏曲：火焰演奏", 4340, 12, 15,
              icon_source_id=12141503, effect_nodes=(), lt=(-1200, -800), rb=(1200, 800)),
)


TIMED_EFFECTS = {
    12121007: TimedEffectSpec(("prepare", "prepare0"), ("keydown", "keydown0"),
                              ("keydownend", "keydownend0"), 5000),
    12121022: TimedEffectSpec(("effect", "effect0"), ("special", "special0"),
                              ("end", "end0"), 20000, -1),
    12121025: TimedEffectSpec((), ("repeat",), (), 30000),
}


base.SKILLS = SKILLS
base.MS_EXPORT_ROOT = MS_EXPORT_ROOT


def backup(path: Path) -> None:
    target = path.with_name(path.name + ".bak-blaze-wizard-v-vi")
    if not target.exists():
        shutil.copy2(path, target)
        print(f"backup: {target}")


def source_spec(skill_id: int) -> SkillSpec:
    return next(spec for spec in SKILLS if spec.source_id == skill_id)


def load_sources():
    groups = {}
    for name, path in SOURCE_PATHS.items():
        groups[name] = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("BMS"), name=path.name).parse()
    strings = WzImage.from_bytes(SOURCE_STRING.read_bytes(), key=WzKey.for_region("BMS"), name=SOURCE_STRING.name).parse()
    return groups, strings, base.MsMetadata.load()


def source_node(groups, skill_id: int) -> WzSubProperty:
    spec = source_spec(skill_id)
    node = groups[spec.source_group].get(f"skill/{skill_id}")
    if not isinstance(node, WzSubProperty):
        raise RuntimeError(f"missing source skill/{skill_id}")
    return node


def tracks(groups, metadata, skill_id: int, node_name: str):
    spec = source_spec(skill_id)
    skill = groups[spec.source_group].get(f"skill/{skill_id}")
    source = skill
    meta = metadata.roots[skill_id]
    for segment in node_name.split("/"):
        source = source.child(segment) if isinstance(source, WzSubProperty) else None
        meta = metadata.child(meta, segment)
    return base.effect_tracks(source if isinstance(source, WzSubProperty) else None, meta, groups, metadata)


def add_effect(target, key, groups, metadata, skill_id: int, node_names: tuple[str, ...]) -> None:
    available = [(name, tracks(groups, metadata, skill_id, name)) for name in node_names]
    available = [(name, value) for name, value in available if value]
    if not available:
        return
    effect = WzSubProperty("effect", target)
    primary = available[0][1][0]
    secondary = available[1][1][0] if len(available) > 1 else []
    base.merge_tracks(primary, secondary, effect, key)
    target.add(effect)


def metadata_node_int(metadata, skill_id: int, node_name: str, property_names: tuple[str, ...], default: int) -> int:
    node = metadata.roots[skill_id]
    for segment in node_name.split("/"):
        node = metadata.child(node, segment)
        if node is None:
            return default
    for property_name in property_names:
        value = base.ms_int(node, property_name)
        if value is not None:
            return value
    return default


def paired_tracks(groups, metadata, skill_id: int, node_names: tuple[str, ...]):
    values = [tracks(groups, metadata, skill_id, node_name) for node_name in node_names]
    values = [variants[0] for variants in values if variants]
    if not values:
        return [], []
    return values[0], values[1] if len(values) > 1 else []


def track_frame(track, index: int, repeat_index: int):
    if index < len(track):
        return track[index]
    loop_length = len(track) - repeat_index
    return track[repeat_index + ((index - repeat_index) % loop_length)]


def add_timed_effect(target, key, groups, metadata, skill_id: int, spec: TimedEffectSpec) -> None:
    effect = WzSubProperty("effect", target)
    output_index = 0

    intro_primary, intro_secondary = paired_tracks(groups, metadata, skill_id, spec.intro_nodes)
    if intro_primary or intro_secondary:
        base.merge_tracks(intro_primary, intro_secondary, effect, key, start_index=output_index)
        output_index += max(len(intro_primary), len(intro_secondary))

    loop_primary, loop_secondary = paired_tracks(groups, metadata, skill_id, spec.loop_nodes)
    if not loop_primary and not loop_secondary:
        raise RuntimeError(f"missing timed effect loop: {skill_id}")
    primary_repeat = metadata_node_int(metadata, skill_id, spec.loop_nodes[0], ("repeat", "repeatIdx"), 0)
    secondary_repeat = metadata_node_int(
        metadata, skill_id, spec.loop_nodes[1], ("repeat", "repeatIdx"), 0
    ) if len(spec.loop_nodes) > 1 else 0
    if loop_primary and not 0 <= primary_repeat < len(loop_primary):
        raise RuntimeError(f"invalid primary repeat index: {skill_id}/{spec.loop_nodes[0]}")
    if loop_secondary and not 0 <= secondary_repeat < len(loop_secondary):
        raise RuntimeError(f"invalid secondary repeat index: {skill_id}/{spec.loop_nodes[1]}")

    repeat_start = max(primary_repeat if loop_primary else 0, secondary_repeat if loop_secondary else 0)
    cycle_lengths = []
    if loop_primary:
        cycle_lengths.append(len(loop_primary) - primary_repeat)
    if loop_secondary:
        cycle_lengths.append(len(loop_secondary) - secondary_repeat)
    joint_cycle = math.lcm(*cycle_lengths)
    base_frame_count = repeat_start + joint_cycle
    loop_start_index = output_index
    loop_elapsed = 0
    encoded_count = 0
    while encoded_count < base_frame_count and loop_elapsed < spec.loop_duration_ms:
        first = track_frame(loop_primary, encoded_count, primary_repeat) if loop_primary else None
        second = track_frame(loop_secondary, encoded_count, secondary_repeat) if loop_secondary else None
        frame_name = str(output_index)
        if first is not None and second is not None:
            frame = base.compose_frames(first, second, frame_name, effect, key)
        else:
            canvas, meta = first or second
            frame = base.encode_target_canvas(canvas, frame_name, effect, key, meta=meta)
        effect.add(frame)
        loop_elapsed += base.frame_delay(frame)
        output_index += 1
        encoded_count += 1

    if loop_elapsed < spec.loop_duration_ms:
        cycle_start = loop_start_index + repeat_start
        cycle_end = loop_start_index + encoded_count
        cycle_index = cycle_start
        while loop_elapsed < spec.loop_duration_ms:
            source_frame = effect.child(str(cycle_index))
            if not isinstance(source_frame, WzCanvasProperty):
                raise RuntimeError(f"missing encoded loop frame: {skill_id}/{cycle_index}")
            effect.add(WzUolProperty(str(output_index), source_frame.name, effect))
            loop_elapsed += base.frame_delay(source_frame)
            output_index += 1
            cycle_index += 1
            if cycle_index >= cycle_end:
                cycle_index = cycle_start

    end_primary, end_secondary = paired_tracks(groups, metadata, skill_id, spec.end_nodes)
    if end_primary or end_secondary:
        base.merge_tracks(end_primary, end_secondary, effect, key, start_index=output_index)
    if spec.z is not None:
        set_int(effect, "z", spec.z)
    target.add(effect)


def add_variant_node(target, key, groups, metadata, skill_id: int, source_name: str, target_name: str | None = None) -> None:
    variants = tracks(groups, metadata, skill_id, source_name)
    if not variants:
        return
    node = WzSubProperty(target_name or source_name, target)
    for index, frames in enumerate(variants):
        variant = WzSubProperty(str(index), node)
        base.merge_tracks(frames, [], variant, key)
        node.add(variant)
    target.add(node)


def add_direct_node(target, key, groups, metadata, skill_id: int, source_names: tuple[str, ...], target_name: str) -> None:
    sources = [tracks(groups, metadata, skill_id, source_name) for source_name in source_names]
    sources = [variants for variants in sources if variants]
    if not sources:
        return
    node = WzSubProperty(target_name, target)
    base.merge_tracks(sources[0][0], sources[1][0] if len(sources) > 1 else [], node, key)
    target.add(node)


def make_levels(spec: SkillSpec, parent: WzSubProperty) -> WzSubProperty:
    levels = WzSubProperty("level", parent)
    for level in range(1, MASTER_LEVEL + 1):
        node = WzSubProperty(str(level), levels)
        set_int(node, "attackCount", min(15, spec.attack_count))
        set_int(node, "cooltime", spec.cooldown)
        set_int(node, "damage", spec.damage)
        set_int(node, "mad", spec.damage)
        set_string(node, "hs", f"h{level}")
        set_vector(node, "lt", spec.lt)
        set_int(node, "mobCount", min(15, spec.mob_count))
        set_int(node, "mpCon", spec.mp_con)
        set_vector(node, "rb", spec.rb)
        if spec.duration_seconds is not None:
            set_int(node, "time", spec.duration_seconds)
        levels.add(node)
    return levels


def build_skill(spec: SkillSpec, parent: WzSubProperty, key, groups, metadata) -> WzSubProperty:
    target = WzSubProperty(str(spec.target_id), parent)
    icon_owner = source_node(groups, spec.icon_source_id or spec.source_id)
    for icon_name in ("icon", "iconMouseOver", "iconDisabled"):
        icon = icon_owner.child(icon_name)
        if isinstance(icon, WzCanvasProperty):
            target.add(base.make_icon(icon, icon_name, target, key))
    effect_owner = spec.effect_source_id or spec.source_id
    timed_effect = TIMED_EFFECTS.get(spec.target_id)
    if timed_effect is not None:
        add_timed_effect(target, key, groups, metadata, effect_owner, timed_effect)
    else:
        add_effect(target, key, groups, metadata, effect_owner, spec.effect_nodes)
    if spec.include_hit:
        hit_owner = spec.hit_source_id or spec.source_id
        add_variant_node(target, key, groups, metadata, hit_owner, "hit")
    if spec.projectile_nodes:
        add_direct_node(target, key, groups, metadata, spec.source_id, spec.projectile_nodes, "ball")
    if spec.summon_node:
        add_variant_node(target, key, groups, metadata, spec.source_id, spec.summon_node)
    for node_name in spec.extra_nodes:
        add_variant_node(target, key, groups, metadata, spec.source_id, node_name)
    action = WzSubProperty("action", target)
    set_string(action, "0", "firestrike")
    target.add(action)
    target.add(make_levels(spec, target))
    set_int(target, "masterLevel", MASTER_LEVEL)
    set_string(target, "elemAttr", "f")
    if spec.hidden:
        set_int(target, "invisible", 1)
    return target


def patch_client_skill(groups, metadata, dry_run: bool) -> None:
    image = WzImage.from_bytes(CLIENT_SKILL.read_bytes(), key=WzKey.for_region("GMS"), name=CLIENT_SKILL.name)
    root = image.parse()
    skill_root = base.ensure_path(root, "skill")
    for skill_id in CUSTOM_SKILL_IDS:
        skill_root._children.pop(str(skill_id), None)
    key = image.wz_file.reader.key
    for spec in SKILLS:
        base.replace_child(skill_root, build_skill(spec, skill_root, key, groups, metadata))
        print(f"client skill: {spec.source_id} -> {spec.target_id}")
    if not dry_run:
        backup(CLIENT_SKILL)
        base.atomic_write_bytes(CLIENT_SKILL, encode_image_body(image, image.wz_file.reader))


def source_string_values(strings: WzSubProperty, skill_id: int) -> dict[str, str]:
    node = strings.get(str(skill_id))
    if not isinstance(node, WzSubProperty):
        return {}
    return {child.name: str(child.value) for child in node.children() if hasattr(child, "value")}


def level_text(spec: SkillSpec) -> str:
    cooldown = f"，冷却时间{spec.cooldown}秒" if spec.cooldown else ""
    return f"消耗MP {spec.mp_con}，最多攻击{spec.mob_count}名敌人，以{spec.damage}%伤害攻击{spec.attack_count}次{cooldown}                    "


def patch_client_string(strings, dry_run: bool) -> None:
    image = WzImage.from_bytes(CLIENT_STRING.read_bytes(), key=WzKey.for_region("GMS"), name=CLIENT_STRING.name)
    root = image.parse()
    for skill_id in CUSTOM_SKILL_IDS:
        root._children.pop(str(skill_id), None)
    for spec in SKILLS:
        source = source_string_values(strings, spec.source_id)
        node = WzSubProperty(str(spec.target_id), root)
        set_string(node, "name", spec.name)
        set_string(node, "desc", source.get("desc", "TMS炎术士五/六转攻击技能兼容迁移。"))
        for level in range(1, MASTER_LEVEL + 1):
            set_string(node, f"h{level}", level_text(spec))
        base.replace_child(root, node)
    if not dry_run:
        backup(CLIENT_STRING)
        base.atomic_write_bytes(CLIENT_STRING, encode_image_body(image, image.wz_file.reader))


def patch_map_effect(dry_run: bool) -> None:
    image = WzImage.from_bytes(CLIENT_MAP_EFFECT.read_bytes(), key=WzKey.for_region("GMS"), name=CLIENT_MAP_EFFECT.name)
    root = image.parse()
    parent = base.ensure_path(root, FIELD_EFFECT_ROOT)
    key = image.wz_file.reader.key
    for name in VIDEO_MARKERS:
        base.replace_child(parent, base.build_video_field_marker(name, parent, key))
        print(f"field effect marker: {FIELD_EFFECT_ROOT}/{name}")
    if not dry_run:
        backup(CLIENT_MAP_EFFECT)
        base.atomic_write_bytes(CLIENT_MAP_EFFECT, encode_image_body(image, image.wz_file.reader))


def xml_escape(value: str) -> str:
    return html.escape(value, quote=True)


def server_skill_block(spec: SkillSpec) -> str:
    lines = [f'  <imgdir name="{spec.target_id}">', '    <imgdir name="action">',
             '      <string name="0" value="firestrike"/>', "    </imgdir>", '    <imgdir name="level">']
    for level in range(1, MASTER_LEVEL + 1):
        lines.extend([
            f'      <imgdir name="{level}">',
            f'        <int name="attackCount" value="{min(15, spec.attack_count)}"/>',
            f'        <int name="cooltime" value="{spec.cooldown}"/>',
            f'        <int name="damage" value="{spec.damage}"/>',
            f'        <int name="mad" value="{spec.damage}"/>',
            f'        <string name="hs" value="h{level}"/>',
            f'        <vector name="lt" x="{spec.lt[0]}" y="{spec.lt[1]}"/>',
            f'        <int name="mobCount" value="{min(15, spec.mob_count)}"/>',
            f'        <int name="mpCon" value="{spec.mp_con}"/>',
            f'        <vector name="rb" x="{spec.rb[0]}" y="{spec.rb[1]}"/>',
            *([f'        <int name="time" value="{spec.duration_seconds}"/>'] if spec.duration_seconds is not None else []),
            "      </imgdir>",
        ])
    lines.extend(["    </imgdir>", f'    <int name="masterLevel" value="{MASTER_LEVEL}"/>',
                  '    <string name="elemAttr" value="f"/>'])
    if spec.hidden:
        lines.append('    <int name="invisible" value="1"/>')
    lines.append("  </imgdir>")
    return "\n".join(lines)


def patch_server_skill(dry_run: bool) -> None:
    text = SERVER_SKILL.read_text(encoding="utf-8")
    info_start, info_end = find_imgdir_block(text, "info")
    info = text[info_start:info_end]
    blocks = "\n".join(server_skill_block(spec) for spec in SKILLS)
    updated = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<imgdir name="1212.img">\n{info}\n<imgdir name="skill">\n{blocks}\n</imgdir>\n</imgdir>\n'
    if not dry_run:
        backup(SERVER_SKILL)
        base.atomic_write_text(SERVER_SKILL, updated)


def server_string_block(spec: SkillSpec, source: dict[str, str]) -> str:
    lines = [f'<imgdir name="{spec.target_id}">', f'  <string name="name" value="{xml_escape(spec.name)}"/>',
             f'  <string name="desc" value="{xml_escape(source.get("desc", "TMS炎术士五/六转攻击技能兼容迁移。"))}"/>']
    for level in range(1, MASTER_LEVEL + 1):
        lines.append(f'  <string name="h{level}" value="{xml_escape(level_text(spec))}"/>')
    lines.append("</imgdir>")
    return "\n".join(lines)


def remove_xml_block(text: str, name: str) -> str:
    try:
        start, end = find_imgdir_block(text, name)
    except RuntimeError:
        return text
    line_start = text.rfind("\n", 0, start) + 1
    if not text[line_start:start].strip():
        start = line_start
    return text[:start] + text[end:]


def patch_server_string(strings, dry_run: bool) -> None:
    text = SERVER_STRING.read_text(encoding="utf-8")
    for skill_id in CUSTOM_SKILL_IDS:
        text = remove_xml_block(text, str(skill_id))
    closing = text.rfind("</imgdir>")
    if closing < 0:
        raise RuntimeError("missing String.wz root closing imgdir")
    blocks = "\n".join(server_string_block(spec, source_string_values(strings, spec.source_id)) for spec in SKILLS)
    text = text[:closing] + blocks + "\n" + text[closing:]
    if not dry_run:
        backup(SERVER_STRING)
        base.atomic_write_text(SERVER_STRING, text)


def flat_animation_duration(node) -> int:
    if not isinstance(node, WzSubProperty):
        return 0
    duration = 0
    frames = sorted(
        (child for child in node.children() if child.name.isdigit()),
        key=lambda child: int(child.name),
    )
    for frame in frames:
        source = frame
        if isinstance(frame, WzUolProperty):
            source = node.child(str(frame.value))
        if not isinstance(source, WzCanvasProperty):
            raise RuntimeError(f"unresolved flat animation frame: {node.name}/{frame.name}")
        duration += base.frame_delay(source)
    return duration


def validate() -> None:
    skill_image = WzImage.from_bytes(CLIENT_SKILL.read_bytes(), key=WzKey.for_region("GMS"), name=CLIENT_SKILL.name)
    root = skill_image.parse()
    canvas_count = 0
    for spec in SKILLS:
        node = root.get(f"skill/{spec.target_id}")
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"missing client skill {spec.target_id}")
        if node.get("action/0") is None or node.get("level/30") is None:
            raise RuntimeError(f"incomplete client skill {spec.target_id}")
        damage = node.get("level/30/damage")
        magic_damage = node.get("level/30/mad")
        if damage is None or magic_damage is None or int(damage.value) != int(magic_damage.value):
            raise RuntimeError(f"magic damage field mismatch: {spec.target_id}")
        if not spec.hidden and spec.effect_nodes and not base.numeric_canvases(node.get("effect")):
            raise RuntimeError(f"magic skill effect is not flat: {spec.target_id}")
        if spec.include_hit and not base.numeric_canvases(node.get("hit/0")):
            raise RuntimeError(f"missing magic hit effect: {spec.target_id}")
        stack = [node]
        while stack:
            current = stack.pop()
            if isinstance(current, WzCanvasProperty):
                canvas_count += 1
                if int(current.format) != 1 or int(current.format2) != 0:
                    raise RuntimeError(f"non-ARGB4444 Canvas in {spec.target_id}")
                if int(current.width) > 1280 or int(current.height) > 720:
                    raise RuntimeError(f"oversized Canvas in {spec.target_id}: {current.width}x{current.height}")
                if decode_canvas(current, region="GMS").getbbox() is None:
                    raise RuntimeError(f"transparent Canvas in {spec.target_id}")
            if hasattr(current, "children"):
                stack.extend(current.children())
    effect_image = WzImage.from_bytes(CLIENT_MAP_EFFECT.read_bytes(), key=WzKey.for_region("GMS"), name=CLIENT_MAP_EFFECT.name).parse()
    for name in VIDEO_MARKERS:
        marker = effect_image.get(f"{FIELD_EFFECT_ROOT}/{name}/0")
        if not isinstance(marker, WzCanvasProperty) or (int(marker.width), int(marker.height)) != (7, 5):
            raise RuntimeError(f"missing MCV marker {name}")
    server = SERVER_SKILL.read_text(encoding="utf-8")
    for spec in SKILLS:
        find_imgdir_block(server, str(spec.target_id))
    for skill_id, timed_effect in TIMED_EFFECTS.items():
        duration = flat_animation_duration(root.get(f"skill/{skill_id}/effect"))
        if duration < timed_effect.loop_duration_ms:
            raise RuntimeError(
                f"timed effect is too short: {skill_id} {duration}ms < {timed_effect.loop_duration_ms}ms"
            )
        if timed_effect.z is not None:
            effect_z = root.get(f"skill/{skill_id}/effect/z")
            if not isinstance(effect_z, WzIntProperty) or int(effect_z.value) != timed_effect.z:
                raise RuntimeError(f"timed effect z mismatch: {skill_id}")
        print(f"timed effect: {skill_id} duration={duration}ms")
    print(f"validated Blaze Wizard V/VI resources: skills={len(SKILLS)} canvases={canvas_count} markers={len(VIDEO_MARKERS)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        validate()
        return 0
    groups, strings, metadata = load_sources()
    patch_client_skill(groups, metadata, args.dry_run)
    patch_client_string(strings, args.dry_run)
    patch_server_skill(args.dry_run)
    patch_server_string(strings, args.dry_run)
    patch_map_effect(args.dry_run)
    if not args.dry_run:
        validate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
