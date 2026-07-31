#!/usr/bin/env python3
"""Migrate TMS Night Walker V/VI ranged skills into the empty 1412 book."""

from __future__ import annotations

import argparse
import html
import re
import shutil
from pathlib import Path

import patch_blaze_wizard_v_vi as engine
from wzpy.properties import WzSoundProperty


ROOT = Path(__file__).resolve().parents[3]
TMS_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
MS_EXPORT_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-MS-Export/NightWalker")
SOURCE_PATHS = {
    "1414": TMS_ROOT / "Skill" / "_Canvas" / "1414.img",
    "40004": TMS_ROOT / "Skill" / "_Canvas" / "40004.img",
    "1400": TMS_ROOT / "Skill" / "_Canvas" / "1400.img",
    "1412": TMS_ROOT / "Skill" / "_Canvas" / "1412.img",
}
CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / "1412.img"
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
CLIENT_MAP_EFFECT = ROOT / "clien" / "Data" / "Map" / "Effect.img"
CLIENT_SOUND = ROOT / "clien" / "Data" / "Sound" / "Skill.img"
SOURCE_SOUND = TMS_ROOT / "Sound" / "Skill.img"
SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / "1412.img.xml"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"
FIELD_EFFECT_ROOT = "customSkill/nightWalker"
VIDEO_MARKERS = ("dominionVideoLayer", "silentNightVideoLayer", "stygianCommandVideoLayer")
MASTER_LEVEL = 30
CUSTOM_SKILL_IDS = range(14121000, 14121037)
RETIRED_SKILL_IDS = {14121009, 14121010, 14121011, 14121012, 14121013}
SHADOW_BITE_BULLET_COUNTS = {14121003: 15, 14121016: 3, 14121017: 1}
SHADOW_BITE_ATTACK_COUNT = 8
SHADOW_BITE_ATTACK_SKILL_IDS = (14121003, 14121014, 14121015)
AVENGER_REPLAY_SKILL_IDS = {
    14121005, 14121006, 14121007, 14121008,
    14121016, 14121017, 14121018, 14121028,
    14121031, 14121033, 14121034, 14121036,
}
RAPID_THROW_REPLAY_SKILL_IDS = {14121005, 14121006, 14121007, 14121008}

SkillSpec = engine.SkillSpec
TimedEffectSpec = engine.TimedEffectSpec


# Visible entry points retain icons and descriptions. Internal attack and
# projectile states are invisible but remain packet-addressable.
SKILLS = (
    SkillSpec(14121003, 400041037, "40004", "暗影吞噬", 990, SHADOW_BITE_ATTACK_COUNT, 15, 1500, 0, False,
              extra_nodes=("hit2",), lt=(-450, -450), rb=(450, 150), duration_seconds=20),
    SkillSpec(14121004, 400041059, "40004", "暗影投掷", 858, 5, 8, 1000, 0, False,
              effect_nodes=(), include_hit=False,
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(14121005, 400041060, "40004", "暗影投掷：终结", 1980, 13, 10,
              icon_source_id=400041059, projectile_nodes=("shootobj/layerList/b1",),
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(14121006, 400041059, "40004", "暗影投掷：上段飞镖", 858, 5, 8,
              icon_source_id=400041059, effect_nodes=(), projectile_nodes=("shootobj/layerList/b1",),
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(14121007, 400041059, "40004", "暗影投掷：中段飞镖", 858, 5, 8,
              icon_source_id=400041059, effect_nodes=(), projectile_nodes=("shootobj/layerList/b2",),
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(14121008, 400041059, "40004", "暗影投掷：下段飞镖", 858, 5, 8,
              icon_source_id=400041059, effect_nodes=(), projectile_nodes=("shootobj/layerList/b3",),
              lt=(-1200, -800), rb=(1200, 800)),

    SkillSpec(14121014, 400041037, "40004", "暗影吞噬：普通命中", 990, SHADOW_BITE_ATTACK_COUNT, 15,
              icon_source_id=400041037, effect_nodes=(), include_hit=False,
              lt=(-450, -450), rb=(450, 150)),
    SkillSpec(14121015, 400041037, "40004", "暗影吞噬：Boss命中", 2673, SHADOW_BITE_ATTACK_COUNT, 15,
              icon_source_id=400041037, effect_nodes=(), include_hit=False,
              lt=(-450, -450), rb=(450, 150)),
    SkillSpec(14121016, 400041037, "40004", "暗影吞噬：暗影蝙蝠", 150, 1, 3,
              icon_source_id=400041037, effect_nodes=(), include_hit=False,
              lt=(-450, -450), rb=(450, 150)),
    SkillSpec(14121017, 400041037, "40004", "暗影吞噬：饥饿蝙蝠", 480, 2, 1,
              icon_source_id=400041037, effect_nodes=(), include_hit=False,
              lt=(-450, -450), rb=(450, 150)),
    SkillSpec(14121018, 14141018, "1414", "支配 VI：连续攻击", 2000, 10, 15,
              icon_source_id=14141018, effect_nodes=(),
              lt=(-1200, -800), rb=(1200, 800)),

    SkillSpec(14121027, 14141017, "1414", "闇黑天魔 VI", 820, 6, 6, 122, 0, False,
              duration_seconds=7, lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(14121028, 14141017, "1414", "闇黑天魔 VI：持续攻击", 820, 6, 6,
              icon_source_id=14141017, effect_nodes=(),
              lt=(-300, -300), rb=(300, 30)),
    SkillSpec(14121030, 14141018, "1414", "支配 VI", 2000, 10, 15, 410, 0, False,
              effect_nodes=("effect", "effect0"), duration_seconds=20,
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(14121031, 14141503, "1414", "冥河指令：连续攻击", 6380, 14, 15,
              icon_source_id=14141503, effect_nodes=(), lt=(-1200, -800), rb=(1200, 800)),

    SkillSpec(14121032, 14141500, "1414", "静谧之夜", 945, 12, 15, 1200, 10, False,
              effect_nodes=(), include_hit=False,
              lt=(-1200, -800), rb=(1200, 800), duration_seconds=30),
    SkillSpec(14121033, 14141501, "1414", "静谧之夜：开幕攻击", 945, 12, 15,
              icon_source_id=14141500, hit_source_id=14141500, effect_nodes=(),
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(14121034, 14141502, "1414", "静谧之夜：追踪飞镖", 900, 12, 15,
              icon_source_id=14141500, effect_nodes=(), projectile_nodes=("summon/stand",),
              hit_source_id=14141501, duration_seconds=30,
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(14121035, 14141503, "1414", "冥河指令", 6380, 14, 15, 1000, 10, False,
              effect_nodes=("effect", "effect0"), include_hit=False,
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(14121036, 14141504, "1414", "冥河指令：终结", 5680, 15, 15,
              icon_source_id=14141503, effect_nodes=(), lt=(-1200, -800), rb=(1200, 800)),
)

TIMED_EFFECTS = {
    14121004: TimedEffectSpec(("prepare",), ("keydown",), ("keydownend",), 2400),
    14121027: TimedEffectSpec(
        ("prepare", "effect"),
        ("effect_ple/loop", "effect_ple0/loop"),
        ("effect_ple/end", "effect_ple0/end"),
        5160,
    ),
}


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
    engine.TIMED_EFFECTS = TIMED_EFFECTS
    engine.base.SKILLS = SKILLS
    engine.base.MS_EXPORT_ROOT = MS_EXPORT_ROOT


def copy_metadata_properties(target, meta) -> None:
    for child in engine.base.ms_children(meta):
        name = child.attrib.get("name")
        if not name or name.isdigit():
            continue
        if child.tag in {"int", "short", "long"}:
            engine.set_int(target, name, int(child.attrib["value"]))
        elif child.tag == "string":
            engine.set_string(target, name, child.attrib["value"])
        elif child.tag == "vector":
            engine.set_vector(target, name, (int(child.attrib["x"]), int(child.attrib["y"])))


def add_variant_node_with_metadata(
        target, key, groups, metadata, skill_id: int, source_name: str,
        target_name: str | None = None) -> None:
    variants = engine.tracks(groups, metadata, skill_id, source_name)
    if not variants:
        return
    node = engine.WzSubProperty(target_name or source_name, target)
    meta = metadata.roots[skill_id]
    for segment in source_name.split("/"):
        meta = metadata.child(meta, segment)
    copy_metadata_properties(node, meta)
    meta_variants = [
        child for child in engine.base.ms_children(meta)
        if child.attrib.get("name", "").isdigit()
    ]
    meta_variants.sort(key=lambda child: int(child.attrib["name"]))
    for index, frames in enumerate(variants):
        variant = engine.WzSubProperty(str(index), node)
        engine.base.merge_tracks(frames, [], variant, key)
        if index < len(meta_variants):
            copy_metadata_properties(variant, metadata.resolve(meta_variants[index]))
        node.add(variant)
    target.add(node)


def numbered_frames(source):
    return sorted(
        (child for child in source.children() if child.name.isdigit()),
        key=lambda child: int(child.name),
    )


def add_raw_flat_animation(target, key, frames, target_name, origins, delay: int) -> None:
    node = engine.WzSubProperty(target_name, target)
    frames = list(frames)
    if len(frames) != len(origins):
        raise RuntimeError(f"raw animation metadata mismatch: {target_name}")
    for index, (frame, origin) in enumerate(zip(frames, origins)):
        encoded = engine.base.encode_target_canvas(frame, str(index), node, key)
        engine.set_vector(encoded, "origin", origin)
        engine.set_int(encoded, "delay", delay)
        node.add(encoded)
    engine.base.replace_child(target, node)


def add_raw_hit_animation(target, key, source, origins, delay: int, metadata=None) -> None:
    hit = engine.WzSubProperty("hit", target)
    variant = engine.WzSubProperty("0", hit)
    frames = sorted(
        (child for child in source.children() if child.name.isdigit()),
        key=lambda child: int(child.name),
    )
    if len(frames) != len(origins):
        raise RuntimeError("raw hit animation metadata mismatch")
    for frame, origin in zip(frames, origins):
        encoded = engine.base.encode_target_canvas(frame, frame.name, variant, key)
        engine.set_vector(encoded, "origin", origin)
        engine.set_int(encoded, "delay", delay)
        variant.add(encoded)
    for name, value in (metadata or {}).items():
        engine.set_int(variant, name, value)
    hit.add(variant)
    engine.base.replace_child(target, hit)


def add_linked_shadow_bite_hit(target, source_name: str, frame_count: int, delay_show: int) -> None:
    hit = engine.WzSubProperty("hit", target)
    for variant_index in range(3):
        variant = engine.WzSubProperty(str(variant_index), hit)
        for frame_index in range(frame_count):
            variant.add(engine.WzUolProperty(
                str(frame_index),
                f"../../../14121003/{source_name}/{variant_index}/{frame_index}",
                variant,
            ))
        engine.set_int(variant, "pos", 1)
        engine.set_int(variant, "onlyOnce", 1)
        engine.set_int(variant, "delayShowDamage", delay_show)
        hit.add(variant)
    engine.base.replace_child(target, hit)


def add_legacy_ranged_visual_links(target) -> None:
    for level in range(1, MASTER_LEVEL + 1):
        level_node = target.get(f"level/{level}")
        if not isinstance(level_node, engine.WzSubProperty):
            raise RuntimeError(f"missing legacy ranged level: {target.name}/{level}")
        level_node.add(engine.WzUolProperty("ball", "../../ball", level_node))
        hit = engine.WzSubProperty("hit", level_node)
        hit.add(engine.WzUolProperty("0", "../../../hit/0", hit))
        level_node.add(hit)


def first_source_track(groups, metadata, skill_id: int, path: str):
    variants = engine.tracks(groups, metadata, skill_id, path)
    if len(variants) != 1 or not variants[0]:
        raise RuntimeError(f"unexpected source animation: {skill_id}/{path}")
    return variants[0]


def append_time_aligned_tracks(parent, key, primary, secondary, start_index: int) -> int:
    def boundaries(track):
        result = [0]
        for canvas, meta in track:
            result.append(result[-1] + engine.base.frame_delay(canvas, meta))
        return result

    def active_frame(track, frame_boundaries, elapsed):
        for index in range(len(track)):
            if frame_boundaries[index] <= elapsed < frame_boundaries[index + 1]:
                return track[index]
        return None

    primary_boundaries = boundaries(primary)
    secondary_boundaries = boundaries(secondary)
    timeline = sorted(set(primary_boundaries + secondary_boundaries))
    output_index = start_index
    for begin, end in zip(timeline, timeline[1:]):
        first = active_frame(primary, primary_boundaries, begin)
        second = active_frame(secondary, secondary_boundaries, begin)
        if first is None and second is None:
            continue
        name = str(output_index)
        if first is not None and second is not None:
            frame = engine.base.compose_frames(first, second, name, parent, key)
        else:
            canvas, meta = first or second
            frame = engine.base.encode_target_canvas(canvas, name, parent, key, meta=meta)
        engine.set_int(frame, "delay", end - begin)
        parent.add(frame)
        output_index += 1
    return output_index


def replace_rapid_throw_finish_effect(target, key, groups, metadata) -> None:
    effect = engine.WzSubProperty("effect", target)
    append_time_aligned_tracks(
        effect,
        key,
        first_source_track(groups, metadata, 400041060, "effect"),
        first_source_track(groups, metadata, 400041060, "effect0"),
        0,
    )
    engine.base.replace_child(target, effect)

    hit = target.get("hit")
    if not isinstance(hit, engine.WzSubProperty):
        raise RuntimeError("missing Rapid Throw finish hit")
    for variant in hit.children():
        if variant.name.isdigit() and isinstance(variant, engine.WzSubProperty):
            engine.set_int(variant, "delayShowDamage", 180)


def optimize_shadow_bite_normal_hit(target) -> None:
    hit = target.get("hit")
    if not isinstance(hit, engine.WzSubProperty):
        raise RuntimeError("missing Shadow Bite normal hit")
    for variant in hit.children():
        if not variant.name.isdigit() or not isinstance(variant, engine.WzSubProperty):
            continue
        frames = sorted(
            (child for child in variant.children() if child.name.isdigit()),
            key=lambda child: int(child.name),
        )
        if len(frames) == 17:
            retained = frames[::2]
            for frame in frames:
                variant._children.pop(frame.name, None)
            for index, frame in enumerate(retained):
                frame.name = str(index)
                engine.set_int(frame, "delay", 120 if index < len(retained) - 1 else 60)
                variant.add(frame)
        elif len(frames) != 9:
            raise RuntimeError(f"unexpected Shadow Bite normal hit frame count: {len(frames)}")


def backup(path: Path) -> None:
    target = path.with_name(path.name + ".bak-night-walker-v-vi")
    if not target.exists():
        shutil.copy2(path, target)
        print(f"backup: {target}")


def build_skill(spec, parent, key, groups, metadata):
    target = engine.build_skill_original(spec, parent, key, groups, metadata)
    if spec.target_id == 14121003:
        info = engine.WzSubProperty("info", target)
        engine.set_int(info, "type", 1)
        engine.set_int(info, "areaAttack", 1)
        engine.base.replace_child(target, info)
        optimize_shadow_bite_normal_hit(target)
    elif spec.target_id == 14121014:
        add_linked_shadow_bite_hit(target, "hit", 9, 720)
    elif spec.target_id == 14121015:
        add_linked_shadow_bite_hit(target, "hit2", 32, 1200)
    elif spec.target_id == 14121005:
        replace_rapid_throw_finish_effect(target, key, groups, metadata)
    elif spec.target_id == 14121016:
        shadow_bat_fly = numbered_frames(
            groups["1400"].get("skill/14000027/summon/fly")
        )
        shadow_bat_fly.append(
            groups["1400"].get("skill/14000027/summon/summoned/7")
        )
        add_raw_flat_animation(
            target,
            key,
            shadow_bat_fly,
            "ball",
            ((29, 45), (25, 47), (22, 46), (28, 46)),
            60,
        )
        add_raw_hit_animation(
            target,
            key,
            groups["1400"].get("skill/14000027/summon/attack1"),
            ((42, 40), (42, 40), (38, 40), (38, 40)),
            60,
        )
    elif spec.target_id == 14121017:
        add_raw_flat_animation(
            target,
            key,
            numbered_frames(groups["1412"].get("skill/14120017/summon/fly")),
            "ball",
            ((34, 48), (29, 51), (26, 49), (33, 49)),
            60,
        )
        add_raw_hit_animation(
            target,
            key,
            groups["1412"].get("skill/14120018/hit/0"),
            ((48, 43), (53, 45), (53, 46), (54, 45),
             (53, 43), (40, 39), (40, 39), (40, 39)),
            90,
            {"z": 2, "useZ": 1, "randomHitOrigin": 15},
        )
    action = target.child("action")
    action_name = "avenger" if spec.target_id in AVENGER_REPLAY_SKILL_IDS | {14121003} else "triplethrow"
    engine.set_string(action, "0", action_name)
    if spec.target_id in AVENGER_REPLAY_SKILL_IDS:
        info = engine.WzSubProperty("info", target)
        engine.set_int(info, "type", 1)
        engine.set_int(info, "areaAttack", 1)
        engine.base.replace_child(target, info)
    if spec.target_id in RAPID_THROW_REPLAY_SKILL_IDS:
        add_legacy_ranged_visual_links(target)
    engine.set_string(target, "elemAttr", "d")
    for level in range(1, MASTER_LEVEL + 1):
        level_node = target.get(f"level/{level}")
        bullet_count = SHADOW_BITE_BULLET_COUNTS.get(
            spec.target_id, min(15, max(1, spec.attack_count))
        )
        engine.set_int(level_node, "bulletCount", bullet_count)
    return target


def clone_sound(source, name: str, parent):
    target = WzSoundProperty(name, parent)
    target.length_ms = source.length_ms
    target.header = source.header
    target._data_offset = source._data_offset
    target._data_length = source._data_length
    target._wz_image = source._wz_image
    target._data = source._data
    return target


def patch_client_sound(dry_run: bool) -> None:
    source_image = engine.WzImage.from_bytes(
        SOURCE_SOUND.read_bytes(), key=engine.WzKey.for_region("BMS"), name=SOURCE_SOUND.name
    )
    source_root = source_image.parse()
    target_image = engine.WzImage.from_bytes(
        CLIENT_SOUND.read_bytes(), key=engine.WzKey.for_region("GMS"), name=CLIENT_SOUND.name
    )
    target_root = target_image.parse()
    mappings = {
        14121003: ((400041037, "Use", "Use"),
                   (400041037, "Hit", "Hit"),
                   (400041037, "Hit2", "Hit2")),
        14121014: ((400041037, "Hit", "Hit"),),
        14121015: ((400041037, "Hit2", "Hit"),),
        14121016: ((14000028, "Hit", "Hit"),),
        14121017: ((14120018, "Hit", "Hit"),),
        14121004: ((400041059, "Pre", "Pre"),
                   (400041059, "Loop", "Loop")),
        14121005: ((400041060, "Use", "Use"),
                   (400041060, "Hit", "Hit")),
        14121006: ((400041059, "Hit", "Hit"),),
        14121007: ((400041059, "Hit", "Hit"),),
        14121008: ((400041059, "Hit", "Hit"),),
        14121030: ((14141018, "Use", "Use"),),
        14121032: ((14141500, "Use", "Use"),),
        14121033: ((14141500, "Hit", "Hit"),),
        14121034: ((14141501, "Hit", "Hit"),),
    }
    for skill_id, sounds in mappings.items():
        node = engine.WzSubProperty(str(skill_id), target_root)
        for source_id, source_name, target_name in sounds:
            source = source_root.get(f"{source_id}/{source_name}")
            if not isinstance(source, WzSoundProperty):
                raise RuntimeError(f"missing TMS sound: {source_id}/{source_name}")
            node.add(clone_sound(source, target_name, node))
        engine.base.replace_child(target_root, node)
    if not dry_run:
        backup(CLIENT_SOUND)
        engine.base.atomic_write_bytes(
            CLIENT_SOUND, engine.encode_image_body(target_image, target_image.wz_file.reader)
        )


def level_text(spec) -> str:
    if spec.target_id == 14121003:
        return (f"消耗MP 1500，最多攻击15名敌人{SHADOW_BITE_ATTACK_COUNT}次，普通怪物伤害990%，"
                "Boss伤害2673%；命中后生成暗影蝙蝠与饥饿蝙蝠立即攻击。"
                "被动：最终伤害增加20%                    ")
    cooldown = f"，冷却时间{spec.cooldown}秒" if spec.cooldown else ""
    return (f"消耗MP {spec.mp_con}，最多锁定{spec.mob_count}名敌人，"
            f"以{spec.damage}%伤害攻击{spec.attack_count}次{cooldown}                    ")


def server_skill_block(spec) -> str:
    action_name = "avenger" if spec.target_id in AVENGER_REPLAY_SKILL_IDS | {14121003} else "triplethrow"
    bullet_count = SHADOW_BITE_BULLET_COUNTS.get(
        spec.target_id, min(15, max(1, spec.attack_count))
    )
    lines = [f'  <imgdir name="{spec.target_id}">', '    <imgdir name="action">',
             f'      <string name="0" value="{action_name}"/>', "    </imgdir>", '    <imgdir name="level">']
    for level in range(1, MASTER_LEVEL + 1):
        lines.extend([
            f'      <imgdir name="{level}">',
            f'        <int name="attackCount" value="{min(15, spec.attack_count)}"/>',
            f'        <int name="bulletCount" value="{bullet_count}"/>',
            f'        <int name="cooltime" value="{spec.cooldown}"/>',
            f'        <int name="damage" value="{spec.damage}"/>',
            f'        <string name="hs" value="h{level}"/>',
            f'        <vector name="lt" x="{spec.lt[0]}" y="{spec.lt[1]}"/>',
            f'        <int name="mobCount" value="{min(15, spec.mob_count)}"/>',
            f'        <int name="mpCon" value="{spec.mp_con}"/>',
            f'        <vector name="rb" x="{spec.rb[0]}" y="{spec.rb[1]}"/>',
            *([f'        <int name="time" value="{spec.duration_seconds}"/>'] if spec.duration_seconds is not None else []),
            "      </imgdir>",
        ])
    lines.extend(["    </imgdir>", f'    <int name="masterLevel" value="{MASTER_LEVEL}"/>',
                  '    <string name="elemAttr" value="d"/>', '    <int name="weapon" value="47"/>'])
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
               f'<imgdir name="1412.img">\n{info}\n<imgdir name="skill">\n{blocks}\n</imgdir>\n</imgdir>\n')
    if not dry_run:
        backup(SERVER_SKILL)
        engine.base.atomic_write_text(SERVER_SKILL, updated)


def patch_shadow_bite_only(dry_run: bool) -> None:
    image = engine.WzImage.from_bytes(
        CLIENT_SKILL.read_bytes(),
        key=engine.WzKey.for_region("GMS"),
        name=CLIENT_SKILL.name,
    )
    root = image.parse()
    for skill_id in (14121003, 14121016, 14121017):
        bullet_count = SHADOW_BITE_BULLET_COUNTS[skill_id]
        action = root.get(f"skill/{skill_id}/action")
        if not isinstance(action, engine.WzSubProperty):
            raise RuntimeError(f"missing Shadow Bite action: {skill_id}")
        engine.set_string(action, "0", "avenger")
        for level in range(1, MASTER_LEVEL + 1):
            level_node = root.get(f"skill/{skill_id}/level/{level}")
            engine.set_int(level_node, "bulletCount", bullet_count)
    for skill_id in SHADOW_BITE_ATTACK_SKILL_IDS:
        for level in range(1, MASTER_LEVEL + 1):
            level_node = root.get(f"skill/{skill_id}/level/{level}")
            if not isinstance(level_node, engine.WzSubProperty):
                raise RuntimeError(f"missing Shadow Bite level: {skill_id}/{level}")
            engine.set_int(level_node, "attackCount", SHADOW_BITE_ATTACK_COUNT)

    optimize_shadow_bite_normal_hit(root.get("skill/14121003"))
    add_linked_shadow_bite_hit(root.get("skill/14121014"), "hit", 9, 720)

    shadow_bat_ball = root.get("skill/14121016/ball")
    if not isinstance(shadow_bat_ball, engine.WzSubProperty):
        raise RuntimeError("missing Shadow Bat projectile")
    reused_frame = shadow_bat_ball._children.pop("7", None)
    if reused_frame is not None:
        reused_frame.name = "3"
        engine.base.replace_child(shadow_bat_ball, reused_frame)
    if not dry_run:
        backup(CLIENT_SKILL)
        engine.base.atomic_write_bytes(
            CLIENT_SKILL, engine.encode_image_body(image, image.wz_file.reader)
        )

    server = SERVER_SKILL.read_text(encoding="utf-8")
    for skill_id in (14121003, 14121016, 14121017):
        bullet_count = SHADOW_BITE_BULLET_COUNTS[skill_id]
        start, end = engine.find_imgdir_block(server, str(skill_id))
        block = server[start:end]
        triple_throw = '<string name="0" value="triplethrow"/>'
        avenger = '<string name="0" value="avenger"/>'
        if triple_throw in block:
            block = block.replace(triple_throw, avenger, 1)
        elif avenger not in block:
            raise RuntimeError(f"missing server Shadow Bite action: {skill_id}")
        block = re.sub(
            r'(<int name="bulletCount" value=")\d+("/>)',
            rf'\g<1>{bullet_count}\2',
            block,
        )
        server = server[:start] + block + server[end:]
    for skill_id in SHADOW_BITE_ATTACK_SKILL_IDS:
        start, end = engine.find_imgdir_block(server, str(skill_id))
        block, replacements = re.subn(
            r'(<int name="attackCount" value=")\d+("/>)',
            rf'\g<1>{SHADOW_BITE_ATTACK_COUNT}\2',
            server[start:end],
        )
        if replacements != MASTER_LEVEL:
            raise RuntimeError(
                f"unexpected Shadow Bite attackCount levels: {skill_id} {replacements}"
            )
        server = server[:start] + block + server[end:]
    if not dry_run:
        backup(SERVER_SKILL)
        engine.base.atomic_write_text(SERVER_SKILL, server)


def patch_client_string(strings, dry_run: bool) -> None:
    image = engine.WzImage.from_bytes(CLIENT_STRING.read_bytes(), key=engine.WzKey.for_region("GMS"), name=CLIENT_STRING.name)
    root = image.parse()
    for skill_id in CUSTOM_SKILL_IDS:
        root._children.pop(str(skill_id), None)
    for spec in SKILLS:
        source = engine.source_string_values(strings, spec.source_id)
        node = engine.WzSubProperty(str(spec.target_id), root)
        engine.set_string(node, "name", spec.name)
        engine.set_string(node, "desc", source.get("desc", "TMS夜行者五/六转技能兼容迁移。"))
        for level in range(1, MASTER_LEVEL + 1):
            engine.set_string(node, f"h{level}", level_text(spec))
        engine.base.replace_child(root, node)
    if not dry_run:
        backup(CLIENT_STRING)
        engine.base.atomic_write_bytes(CLIENT_STRING, engine.encode_image_body(image, image.wz_file.reader))


def server_string_block(spec, source: dict[str, str]) -> str:
    lines = [f'<imgdir name="{spec.target_id}">',
             f'  <string name="name" value="{html.escape(spec.name, quote=True)}"/>',
             f'  <string name="desc" value="{html.escape(source.get("desc", "TMS夜行者五/六转技能兼容迁移。"), quote=True)}"/>']
    for level in range(1, MASTER_LEVEL + 1):
        lines.append(f'  <string name="h{level}" value="{html.escape(level_text(spec), quote=True)}"/>')
    lines.append("</imgdir>")
    return "\n".join(lines)


def validate() -> None:
    image = engine.WzImage.from_bytes(CLIENT_SKILL.read_bytes(), key=engine.WzKey.for_region("GMS"), name=CLIENT_SKILL.name)
    root = image.parse()
    skill_root = root.get("skill")
    expected_ids = {spec.target_id for spec in SKILLS}
    actual_ids = {
        int(child.name)
        for child in skill_root.children()
        if child.name.isdigit() and int(child.name) in CUSTOM_SKILL_IDS
    }
    if actual_ids != expected_ids:
        raise RuntimeError(
            f"Night Walker skill ID mismatch: missing={sorted(expected_ids - actual_ids)} "
            f"extra={sorted(actual_ids - expected_ids)}"
        )
    canvas_count = 0
    for spec in SKILLS:
        node = root.get(f"skill/{spec.target_id}")
        if not isinstance(node, engine.WzSubProperty):
            raise RuntimeError(f"missing client skill {spec.target_id}")
        master_level = node.get("masterLevel")
        if master_level is None or int(master_level.value) != MASTER_LEVEL:
            raise RuntimeError(f"master level mismatch: {spec.target_id}")
        invisible = node.get("invisible")
        if (invisible is not None and int(invisible.value) != 0) != spec.hidden:
            raise RuntimeError(f"visibility mismatch: {spec.target_id}")
        if node.get("action/0") is None:
            raise RuntimeError(f"incomplete ranged skill {spec.target_id}")
        for level in range(1, MASTER_LEVEL + 1):
            bullet_count = node.get(f"level/{level}/bulletCount")
            cooltime = node.get(f"level/{level}/cooltime")
            if bullet_count is None:
                raise RuntimeError(f"missing level {level}: {spec.target_id}")
            if cooltime is None or int(cooltime.value) != spec.cooldown:
                raise RuntimeError(f"cooldown mismatch at level {level}: {spec.target_id}")
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
    expected_effect_durations = {14121004: 2880, 14121005: 1890, 14121027: 7020}
    for skill_id, expected_duration in expected_effect_durations.items():
        duration = engine.flat_animation_duration(root.get(f"skill/{skill_id}/effect"))
        if duration != expected_duration:
            raise RuntimeError(
                f"effect duration mismatch: {skill_id} {duration} != {expected_duration}"
            )
    required_metadata = {
        "skill/14121003/hit/0/pos": 1,
        "skill/14121006/hit/0/randomHitOrigin": 20,
        "skill/14121028/hit/0/randomHitAngle": 1,
        "skill/14121018/hit/0/delayShowDamage": 120,
        "skill/14121033/hit/0/onCoverFieldDamage": 1,
        "skill/14121031/hit/0/hitSoundProb": 40,
    }
    for path, expected_value in required_metadata.items():
        prop = root.get(path)
        if prop is None or int(prop.value) != expected_value:
            raise RuntimeError(f"hit metadata mismatch: {path}")
    if root.get("skill/14121003/hit2/0") is None:
        raise RuntimeError("missing Shadow Bite hit2")
    rapid_widths = [
        int(root.get(f"skill/{skill_id}/ball/0").width)
        for skill_id in (14121006, 14121007, 14121008)
    ]
    if rapid_widths != [160, 204, 256]:
        raise RuntimeError(f"Rapid Throw projectile mismatch: {rapid_widths}")
    finish_delay = root.get("skill/14121005/hit/0/delayShowDamage")
    if finish_delay is None or int(finish_delay.value) != 180:
        raise RuntimeError("Rapid Throw finish damage delay mismatch")
    expected_attack_parameters = {
        14121004: (858, 5, 8, (-1200, -800), (1200, 800)),
        14121005: (1980, 13, 10, (-1200, -800), (1200, 800)),
        14121006: (858, 5, 8, (-1200, -800), (1200, 800)),
        14121007: (858, 5, 8, (-1200, -800), (1200, 800)),
        14121008: (858, 5, 8, (-1200, -800), (1200, 800)),
        14121018: (2000, 10, 15, (-1200, -800), (1200, 800)),
        14121027: (820, 6, 6, (-1200, -800), (1200, 800)),
        14121028: (820, 6, 6, (-300, -300), (300, 30)),
    }
    for skill_id, (damage, attack_count, mob_count, lt, rb) in expected_attack_parameters.items():
        level = root.get(f"skill/{skill_id}/level/{MASTER_LEVEL}")
        actual = (
            int(level.get("damage").value),
            int(level.get("attackCount").value),
            int(level.get("mobCount").value),
            (int(level.get("lt").x), int(level.get("lt").y)),
            (int(level.get("rb").x), int(level.get("rb").y)),
        )
        if actual != (damage, attack_count, mob_count, lt, rb):
            raise RuntimeError(f"Night Walker attack parameter mismatch: {skill_id} {actual}")
    shadow_bite = root.get("skill/14121003")
    expected_shadow_range = {
        "level/30/lt": (-450, -450),
        "level/30/rb": (450, 150),
    }
    for path, expected in expected_shadow_range.items():
        vector = shadow_bite.get(path)
        if vector is None or (int(vector.x), int(vector.y)) != expected:
            raise RuntimeError(f"Shadow Bite range mismatch: {path}")
    area_attack = shadow_bite.get("info/areaAttack")
    if area_attack is None or int(area_attack.value) != 1:
        raise RuntimeError("missing Shadow Bite areaAttack marker")
    for skill_id in SHADOW_BITE_ATTACK_SKILL_IDS:
        for level in range(1, MASTER_LEVEL + 1):
            attack_count = root.get(f"skill/{skill_id}/level/{level}/attackCount")
            if attack_count is None or int(attack_count.value) != SHADOW_BITE_ATTACK_COUNT:
                raise RuntimeError(
                    f"Shadow Bite attack count mismatch: {skill_id}/{level}"
                )
    normal_hit = root.get("skill/14121003/hit/0")
    normal_hit_frames = [
        child for child in normal_hit.children() if child.name.isdigit()
    ]
    if len(normal_hit_frames) != 9 or engine.flat_animation_duration(normal_hit) != 1020:
        raise RuntimeError("Shadow Bite normal hit optimization mismatch")
    linked_normal_hit = root.get("skill/14121014/hit/0")
    linked_normal_hit_frames = [
        child for child in linked_normal_hit.children()
        if child.name.isdigit() and isinstance(child, engine.WzUolProperty)
    ]
    if (len(linked_normal_hit_frames) != 9 or
            linked_normal_hit_frames[-1].value != "../../../14121003/hit/0/8"):
        raise RuntimeError("Shadow Bite linked normal hit mismatch")
    boss_hit = root.get("skill/14121015/hit/0")
    boss_hit_frames = [
        child for child in boss_hit.children()
        if child.name.isdigit() and isinstance(child, engine.WzUolProperty)
    ]
    if len(boss_hit_frames) != 32 or boss_hit_frames[-1].value != "../../../14121003/hit2/0/31":
        raise RuntimeError("Shadow Bite boss hit animation mismatch")
    if engine.flat_animation_duration(root.get("skill/14121016/ball")) != 240:
        raise RuntimeError("Shadow Bat projectile animation mismatch")
    shadow_bat_ball_names = [
        child.name for child in root.get("skill/14121016/ball").children()
        if child.name.isdigit()
    ]
    if shadow_bat_ball_names != ["0", "1", "2", "3"]:
        raise RuntimeError(f"Shadow Bat projectile frame mismatch: {shadow_bat_ball_names}")
    for skill_id in (14121003, 14121016, 14121017):
        action = root.get(f"skill/{skill_id}/action/0")
        if action is None or action.value != "avenger":
            raise RuntimeError(f"Shadow Bite ranged action mismatch: {skill_id}")
        bullet_count = root.get(f"skill/{skill_id}/level/{MASTER_LEVEL}/bulletCount")
        if (bullet_count is None or
                int(bullet_count.value) != SHADOW_BITE_BULLET_COUNTS[skill_id]):
            raise RuntimeError(f"Shadow Bite projectile count mismatch: {skill_id}")
    for skill_id in AVENGER_REPLAY_SKILL_IDS:
        action = root.get(f"skill/{skill_id}/action/0")
        area_attack = root.get(f"skill/{skill_id}/info/areaAttack")
        if action is None or action.value != "avenger":
            raise RuntimeError(f"multi-target replay action mismatch: {skill_id}")
        if area_attack is None or int(area_attack.value) != 1:
            raise RuntimeError(f"multi-target replay marker mismatch: {skill_id}")
    for skill_id in RAPID_THROW_REPLAY_SKILL_IDS:
        for level in range(1, MASTER_LEVEL + 1):
            ball = root.get(f"skill/{skill_id}/level/{level}/ball")
            hit = root.get(f"skill/{skill_id}/level/{level}/hit/0")
            if not isinstance(ball, engine.WzUolProperty) or ball.value != "../../ball":
                raise RuntimeError(f"Rapid Throw legacy ball link mismatch: {skill_id}/{level}")
            if not isinstance(hit, engine.WzUolProperty) or hit.value != "../../../hit/0":
                raise RuntimeError(f"Rapid Throw legacy hit link mismatch: {skill_id}/{level}")
    if engine.flat_animation_duration(root.get("skill/14121017/hit/0")) != 720:
        raise RuntimeError("Ravenous Bat hit animation mismatch")
    effect_image = engine.WzImage.from_bytes(
        CLIENT_MAP_EFFECT.read_bytes(),
        key=engine.WzKey.for_region("GMS"),
        name=CLIENT_MAP_EFFECT.name,
    ).parse()
    for marker_name in VIDEO_MARKERS:
        marker = effect_image.get(f"{FIELD_EFFECT_ROOT}/{marker_name}/0")
        if not isinstance(marker, engine.WzCanvasProperty) or (int(marker.width), int(marker.height)) != (7, 5):
            raise RuntimeError(f"missing MCV marker: {marker_name}")
    sound_image = engine.WzImage.from_bytes(
        CLIENT_SOUND.read_bytes(), key=engine.WzKey.for_region("GMS"), name=CLIENT_SOUND.name
    ).parse()
    expected_sounds = {
        "14121003/Use": 2016,
        "14121003/Hit": 5112,
        "14121003/Hit2": 3504,
        "14121014/Hit": 5112,
        "14121015/Hit": 3504,
        "14121016/Hit": 364,
        "14121017/Hit": 338,
        "14121004/Pre": 339,
        "14121004/Loop": 679,
        "14121005/Use": 1306,
        "14121005/Hit": 653,
        "14121006/Hit": 914,
        "14121007/Hit": 914,
        "14121008/Hit": 914,
        "14121030/Use": 4392,
        "14121032/Use": 6286,
        "14121033/Hit": 886,
        "14121034/Hit": 886,
    }
    for path, expected_duration in expected_sounds.items():
        sound = sound_image.get(path)
        if not isinstance(sound, WzSoundProperty) or sound.length_ms != expected_duration:
            raise RuntimeError(f"sound mismatch: {path}")
    server = SERVER_SKILL.read_text(encoding="utf-8")
    client_string = engine.WzImage.from_bytes(
        CLIENT_STRING.read_bytes(),
        key=engine.WzKey.for_region("GMS"),
        name=CLIENT_STRING.name,
    ).parse()
    server_string = SERVER_STRING.read_text(encoding="utf-8")
    for spec in SKILLS:
        engine.find_imgdir_block(server, str(spec.target_id))
    for skill_id in RETIRED_SKILL_IDS:
        if root.get(f"skill/{skill_id}") is not None:
            raise RuntimeError(f"retired client skill remains: {skill_id}")
        if client_string.get(str(skill_id)) is not None:
            raise RuntimeError(f"retired client skill string remains: {skill_id}")
        if re.search(rf'<imgdir name="{skill_id}">', server):
            raise RuntimeError(f"retired server skill remains: {skill_id}")
        if re.search(rf'<imgdir name="{skill_id}">', server_string):
            raise RuntimeError(f"retired server skill string remains: {skill_id}")
    print(
        f"validated Night Walker V/VI resources: skills={len(SKILLS)} "
        f"canvases={canvas_count} markers={len(VIDEO_MARKERS)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--shadow-bite-only", action="store_true")
    args = parser.parse_args()
    configure_engine()
    if args.validate_only:
        validate()
        return 0
    if args.shadow_bite_only:
        patch_shadow_bite_only(args.dry_run)
        if not args.dry_run:
            validate()
        return 0
    groups, strings, metadata = engine.load_sources()
    engine.patch_client_skill(groups, metadata, args.dry_run)
    patch_client_string(strings, args.dry_run)
    patch_server_skill(args.dry_run)
    engine.patch_server_string(strings, args.dry_run)
    engine.patch_map_effect(args.dry_run)
    patch_client_sound(args.dry_run)
    if not args.dry_run:
        validate()
    return 0


configure_engine()
engine.backup = backup
engine.add_variant_node = add_variant_node_with_metadata
engine.build_skill_original = engine.build_skill
engine.build_skill = build_skill
engine.level_text = level_text
engine.server_skill_block = server_skill_block
engine.patch_server_skill = patch_server_skill
engine.patch_client_string = patch_client_string
engine.server_string_block = server_string_block


if __name__ == "__main__":
    raise SystemExit(main())
