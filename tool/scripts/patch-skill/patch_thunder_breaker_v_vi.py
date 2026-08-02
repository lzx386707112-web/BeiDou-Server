#!/usr/bin/env python3
"""Migrate TMS Thunder Breaker V/VI attacks into the empty 1512 book."""

from __future__ import annotations

import argparse
import html
import math
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import patch_blaze_wizard_v_vi as engine


ROOT = Path(__file__).resolve().parents[3]
TMS_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
MS_EXPORT_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-MS-Export/ThunderBreaker")
SOURCE_PATHS = {
    "000": TMS_ROOT / "Skill" / "_Canvas" / "000.img",
    "10000": TMS_ROOT / "Skill" / "_Canvas" / "10000.img",
    "110": TMS_ROOT / "Skill" / "_Canvas" / "110.img",
    "112": TMS_ROOT / "Skill" / "_Canvas" / "112.img",
    "1512": TMS_ROOT / "Skill" / "_Canvas" / "1512.img",
    "1514": TMS_ROOT / "Skill" / "_Canvas" / "1514.img",
    "40005": TMS_ROOT / "Skill" / "_Canvas" / "40005.img",
}
CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / "1512.img"
CLIENT_LEGACY_SKILL = ROOT / "clien" / "Data" / "Skill" / "1511.img"
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
CLIENT_MAP_EFFECT = ROOT / "clien" / "Data" / "Map" / "Effect.img"
SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / "1512.img.xml"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"
SERVER_CLOSE_HANDLER = (
    ROOT / "gms-server" / "src" / "main" / "java" / "org" / "gms"
    / "net" / "server" / "channel" / "handlers" / "CloseRangeDamageHandler.java"
)
FIELD_EFFECT_ROOT = "customSkill/thunderBreaker"
VIDEO_MARKERS = (
    "godOfSeaViVideoLayer",
    "waveRidingThunderVideoLayer",
    "swiftAnnihilationVideoLayer",
)
MASTER_LEVEL = 30
CUSTOM_SKILL_IDS = range(15121000, 15121034)
LIGHTNING_SPEAR_COMBO_VISUAL_IDS = tuple(range(15121022, 15121034))

SkillSpec = engine.SkillSpec


# Values are evaluated from the TMS level-30 common expressions. The hidden
# nodes retain the source damage, line count, target cap and attack rectangle
# used by server-side continuous and multi-stage replay.
SKILLS = (
    SkillSpec(15121000, 400051015, "40005", "海龙螺旋", 780, 3, 10, 300, 60, False,
              effect_nodes=("effect0", "effect"),
              lt=(-275, -145), rb=(275, 55)),
    SkillSpec(15121002, 400051058, "40005", "枪雷连击", 1430, 5, 4, 1000, 120, False,
              effect_source_id=400051059, hit_source_id=400051059,
              extra_nodes=("number",),
              lt=(-650, -400), rb=(450, 300), duration_seconds=60,
              include_hit=False),
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
              effect_nodes=("effect", "effect2"), extra_nodes=("number",),
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(15121020, 15141503, "1514", "疾浪歼灭：激流", 6510, 15, 15,
              icon_source_id=15141502, effect_nodes=(),
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(15121021, 400051015, "40005", "海龙螺旋：持续攻击", 780, 3, 10,
              300, 60,
              icon_source_id=400051015, effect_nodes=(),
              lt=(-275, -145), rb=(275, 55)),
) + tuple(
    SkillSpec(
        target_id,
        400051059 + ((target_id - 15121022) % 6),
        "40005",
        f"枪雷连击：第{target_id - 15121021}击视觉",
        1430,
        5,
        4,
        1000,
        icon_source_id=400051058,
        effect_nodes=("effect",),
        lt=(-415, -300),
        rb=(30, 15),
    )
    for target_id in LIGHTNING_SPEAR_COMBO_VISUAL_IDS
)

VISIBLE_IDS = {spec.target_id for spec in SKILLS if not spec.hidden}
AREA_ATTACK_IDS = {spec.target_id for spec in SKILLS if spec.mob_count > 1}
LIGHTNING_SPEAR_STAGE_IDS = frozenset(range(15121003, 15121012))
LOCAL_COOLDOWN_OVERRIDES = {
    spec.target_id: 10 if spec.target_id in {15121017, 15121019} else 0
    for spec in SKILLS
}
LEGACY_WEAPON_TYPES = {}
LEVEL_EXTRA_VALUES = {
    15121000: {
        "subTime": 240, "v": 100, "w": 10000, "w2": 40,
        "q": 3, "u": 10, "u2": 6000, "x": 6, "y": 10,
    },
    15121002: {
        "x": 12, "y": 3, "subTime": 180, "z": 3, "w": 4,
        "s": 1555, "u": 7, "v": 7, "q": 1990, "u2": 8,
        "v2": 6, "q2": 2145, "dot": 510, "w2": 330, "s2": 3,
    },
    15121015: {"x": 2, "y": 3, "u": 250},
    15121017: {
        "updatableTime": 10000, "ndTime": 8200, "u": 32,
        "dot": 1370, "dotInterval": 7, "w": 62,
        "ignoreMobpdpR": 50, "bdR": 50,
    },
    15121019: {
        "updatableTime": 5000, "ndTime": 3220,
        "ignoreMobpdpR": 100, "bdR": 60, "cr": 100,
        "6thCount": 3, "dummyStr": 11, "dummyStr2": 6510,
        "dummyStr3": 15, "dummyStr4": 18,
        "dummyStr5": 60, "dummyStr6": 40,
    },
    15121021: {
        "subTime": 240, "v": 100, "w": 10000, "w2": 40,
        "q": 3, "u": 10, "u2": 6000, "x": 6, "y": 10,
    },
}
LEVEL_EXTRA_VECTORS = {
    15121002: {"lt2": (-250, -30), "rb2": (250, 30)},
}
# These TMS root flags belong to client systems that do not exist in the
# legacy build. Their observable combat behavior is implemented by the local
# level/info data and server replay code instead of copying flags that could
# route a skill back into unavailable V-matrix, Origin or holding state code.
UNSUPPORTED_ROOT_INT_FLAGS = {
    "alertTime", "applyHyper", "applySixthSkillIncBuffDuration", "ascent",
    "bossClearOff", "excl", "holding", "ignoreHekateAttack",
    "ignoreSpecialCore", "isExceptSetLastAttack", "notCooltimeReduce",
    "notCooltimeReset", "notIncBuffDuration", "notRemoved", "origin",
    "preloadEff", "processtype", "psd", "vSkill",
}
HANDLED_ROOT_INT_FLAGS = {"invisible", "weapon", "weapon2"}
COUNTER_EFFECT_IDS = {15121019}
HIT_DELAY_COMPATIBILITY = {
    15121009: 390,
    15121011: 270,
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
    engine.TIMED_EFFECTS = {}
    engine.base.SKILLS = SKILLS
    engine.base.MS_EXPORT_ROOT = MS_EXPORT_ROOT


def backup(path: Path) -> None:
    target = path.with_name(path.name + ".bak-thunder-breaker-v-vi")
    if not target.exists():
        shutil.copy2(path, target)
        print(f"backup: {target}")


def action_for(spec: SkillSpec) -> str:
    if 15121002 <= spec.target_id <= 15121011 \
            or spec.target_id in LIGHTNING_SPEAR_COMBO_VISUAL_IDS:
        return "alert5"
    return "fist"


def find_source_metadata_node(metadata, skill_id: int, node_name: str):
    node = metadata.roots[skill_id]
    for segment in node_name.split("/"):
        node = metadata.child(node, segment)
        if node is None:
            return None
    return node


def source_metadata_node(metadata, skill_id: int, node_name: str):
    node = find_source_metadata_node(metadata, skill_id, node_name)
    if node is None:
        raise RuntimeError(f"missing source metadata: {skill_id}/{node_name}")
    return node


def copy_metadata_values(target, source, excluded: set[str] | None = None) -> None:
    excluded = excluded or set()
    for child in list(source):
        name = child.attrib.get("name")
        if not name or name in excluded:
            continue
        if child.tag in {"int", "short", "long"}:
            engine.set_int(target, name, int(child.attrib["value"]))
        elif child.tag == "string":
            engine.set_string(target, name, child.attrib["value"])
        elif child.tag == "vector":
            engine.set_vector(
                target, name, (int(child.attrib["x"]), int(child.attrib["y"]))
            )


def transparent_frame(name: str, parent, key, delay: int, metadata_node=None):
    image = engine.base.Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    frame = engine.WzCanvasProperty(name, parent)
    frame.width = 1
    frame.height = 1
    frame.format = engine.base.CANVAS_FORMAT
    frame.format2 = 0
    frame._png_data = engine.base.encode_canvas_payload(
        image, engine.base.CANVAS_FORMAT, 1, 1,
        key=key, listwz=False, zlib_level=9
    )
    frame._png_length = len(frame._png_data)
    origin = engine.base.ms_vector(metadata_node, "origin") or (0, 0)
    engine.set_vector(frame, "origin", origin)
    engine.set_int(frame, "delay", delay)
    if metadata_node is not None:
        copy_metadata_values(
            frame, metadata_node, {"_outlink", "origin", "delay"}
        )
    return frame


def animation_frame_entries(node, metadata):
    entries = [
        (child.attrib["name"], metadata.resolve(child))
        for child in list(node)
        if child.tag in {"canvas", "uol"}
        and (child.attrib.get("name", "").isdigit()
             or re.fullmatch(r"icon\d+", child.attrib.get("name", "")))
    ]
    entries.sort(
        key=lambda item: int(re.search(r"\d+$", item[0]).group())
    )
    return entries


def encode_exact_track(parent, key, groups, metadata, metadata_node) -> None:
    frames = animation_frame_entries(metadata_node, metadata)
    for frame_name, frame_metadata in frames:
        delay = engine.base.ms_int(frame_metadata, "delay", 60) or 60
        source = engine.base.resolve_ms_canvas(frame_metadata, groups, metadata)
        if source is None:
            frame = transparent_frame(
                frame_name, parent, key, delay, frame_metadata
            )
        else:
            frame = engine.base.encode_target_canvas(
                source, frame_name, parent, key, meta=frame_metadata
            )
            engine.set_int(frame, "delay", delay)
        parent.add(frame)


def replace_exact_node(target, key, groups, metadata, skill_id: int,
                       source_name: str, target_name: str | None = None) -> None:
    source_meta = source_metadata_node(metadata, skill_id, source_name)
    node = engine.WzSubProperty(target_name or source_name, target)
    direct_frames = animation_frame_entries(source_meta, metadata)
    if direct_frames:
        encode_exact_track(node, key, groups, metadata, source_meta)
    else:
        variants = [
            child for child in list(source_meta)
            if child.tag == "imgdir"
            and animation_frame_entries(child, metadata)
        ]
        for source_variant in variants:
            variant = engine.WzSubProperty(source_variant.attrib["name"], node)
            encode_exact_track(variant, key, groups, metadata, source_variant)
            copy_metadata_values(variant, source_variant)
            node.add(variant)
    copy_metadata_values(node, source_meta)
    engine.base.replace_child(target, node)


def source_timeline(groups, metadata, skill_id: int, node_name: str):
    source_meta = source_metadata_node(metadata, skill_id, node_name)
    elapsed = 0
    timeline = []
    for frame_meta in engine.base.ms_numeric_frames(source_meta, metadata):
        delay = engine.base.ms_int(frame_meta, "delay", 60) or 60
        canvas = engine.base.resolve_ms_canvas(frame_meta, groups, metadata)
        has_outlink = any(
            child.tag == "string" and child.attrib.get("name") == "_outlink"
            for child in frame_meta
        )
        if canvas is None and has_outlink:
            raise RuntimeError(
                f"unresolved TMS Canvas: {skill_id}/{node_name}/"
                f"{frame_meta.attrib.get('name', '?')}"
            )
        timeline.append((elapsed, elapsed + delay, canvas, frame_meta))
        elapsed += delay
    if not timeline:
        raise RuntimeError(f"missing source animation: {skill_id}/{node_name}")
    return timeline


def replace_time_aligned_node(target, key, groups, metadata, skill_id: int,
                              source_names: tuple[str, ...], target_name: str) -> None:
    timelines = [
        source_timeline(groups, metadata, skill_id, name)
        for name in source_names
    ]
    boundaries = sorted({
        time
        for timeline in timelines
        for begin, end, _canvas, _meta in timeline
        for time in (begin, end)
    })
    node = engine.WzSubProperty(target_name, target)
    for begin, end in zip(boundaries, boundaries[1:]):
        active = []
        for timeline in timelines:
            segment = next(
                (item for item in timeline if item[0] <= begin < item[1]), None
            )
            if segment is not None and segment[2] is not None:
                active.append((segment[2], segment[3]))
        frame_name = str(len(engine.base.numeric_canvases(node)))
        if not active:
            frame = transparent_frame(frame_name, node, key, end - begin)
        elif len(active) == 1:
            frame = engine.base.encode_target_canvas(
                active[0][0], frame_name, node, key, meta=active[0][1]
            )
        elif len(active) == 2:
            frame = engine.base.compose_frames(
                active[0], active[1], frame_name, node, key
            )
        else:
            raise RuntimeError(
                f"too many visual layers: {skill_id}/{target_name}/{begin}"
            )
        engine.set_int(frame, "delay", end - begin)
        node.add(frame)
    copy_metadata_values(
        node, source_metadata_node(metadata, skill_id, source_names[0])
    )
    engine.base.replace_child(target, node)


def wz_canvas_timeline(node) -> list[tuple[int, int, object]]:
    elapsed = 0
    timeline = []
    for frame in engine.base.numeric_canvases(node):
        delay = engine.base.frame_delay(frame)
        timeline.append((elapsed, elapsed + delay, frame))
        elapsed += delay
    return timeline


def counter_schedule(skill_id: int) -> list[int]:
    if skill_id == 15121002:
        interval = LEVEL_EXTRA_VALUES[skill_id]["subTime"]
        return [index * interval for index in range(LEVEL_EXTRA_VALUES[skill_id]["x"])]
    if skill_id == 15121019:
        # The first Origin strike has no counter; icon1..icon10 label the ten
        # following opening hits from the source multiAttackInfo.
        return source_multi_attack_times(15141502)[15141502][1:]
    raise RuntimeError(f"missing counter compatibility schedule: {skill_id}")


def replace_effect_with_counter(target, key, groups, metadata,
                                spec: SkillSpec) -> None:
    effect = target.get("effect")
    if not isinstance(effect, engine.WzSubProperty):
        raise RuntimeError(f"missing counter effect target: {spec.target_id}")
    effect_timeline = wz_canvas_timeline(effect)
    schedule = counter_schedule(spec.target_id)
    number_meta = source_metadata_node(metadata, spec.source_id, "number")
    number_entries = animation_frame_entries(number_meta, metadata)
    if len(number_entries) < len(schedule):
        raise RuntimeError(
            f"not enough counter icons {spec.source_id}: "
            f"icons={len(number_entries)} schedule={len(schedule)}"
        )
    duration = schedule[1] - schedule[0]
    number_timeline = []
    for start, (_name, frame_meta) in zip(schedule, number_entries):
        canvas = engine.base.resolve_ms_canvas(frame_meta, groups, metadata)
        if canvas is None:
            raise RuntimeError(f"unresolved counter icon: {spec.source_id}/{start}")
        number_timeline.append((start, start + duration, canvas, frame_meta))
    boundaries = sorted({
        time
        for timeline in (effect_timeline, number_timeline)
        for entry in timeline
        for time in entry[:2]
    })
    compatible = engine.WzSubProperty("effect", target)
    for begin, end in zip(boundaries, boundaries[1:]):
        effect_segment = next(
            (entry for entry in effect_timeline if entry[0] <= begin < entry[1]),
            None,
        )
        number_segment = next(
            (entry for entry in number_timeline if entry[0] <= begin < entry[1]),
            None,
        )
        name = str(len(engine.base.numeric_canvases(compatible)))
        if effect_segment is not None and number_segment is not None:
            frame = engine.base.compose_frames(
                (effect_segment[2], None),
                (number_segment[2], number_segment[3]),
                name,
                compatible,
                key,
            )
        elif effect_segment is not None:
            frame = engine.base.encode_target_canvas(
                effect_segment[2], name, compatible, key
            )
        elif number_segment is not None:
            frame = engine.base.encode_target_canvas(
                number_segment[2], name, compatible, key,
                meta=number_segment[3],
            )
        else:
            frame = transparent_frame(name, compatible, key, end - begin)
        engine.set_int(frame, "delay", end - begin)
        compatible.add(frame)
    for child in effect.children():
        if isinstance(child, engine.WzIntProperty):
            engine.set_int(compatible, child.name, int(child.value))
    engine.base.replace_child(target, compatible)


def replace_with_transparent_animation(target, key, node_name: str,
                                       delay: int = 180) -> None:
    compatible = engine.WzSubProperty(node_name, target)
    compatible.add(transparent_frame("0", compatible, key, delay))
    engine.base.replace_child(target, compatible)


def replace_lightning_spear_entry_effect(target, key) -> None:
    # The client sends the same entry skill for every press. Its local effect
    # must stay invisible; the server selects and echoes the authoritative
    # one-to-twelve visual node after accepting the input.
    replace_with_transparent_animation(target, key, "effect")


def replace_lightning_spear_combo_visual(target, key, groups, metadata,
                                         spec: SkillSpec) -> None:
    press_index = spec.target_id - LIGHTNING_SPEAR_COMBO_VISUAL_IDS[0]
    stage_timeline = source_timeline(
        groups, metadata, spec.source_id, "effect"
    )
    number_meta = source_metadata_node(metadata, 400051058, "number")
    number_entries = animation_frame_entries(number_meta, metadata)
    if press_index >= len(number_entries):
        raise RuntimeError(
            f"missing Lightning Spear counter icon {press_index + 1}"
        )
    _name, icon_meta = number_entries[press_index]
    icon_canvas = engine.base.resolve_ms_canvas(icon_meta, groups, metadata)
    if icon_canvas is None:
        raise RuntimeError(
            f"unresolved Lightning Spear counter icon {press_index + 1}"
        )
    counter_duration = LEVEL_EXTRA_VALUES[15121002]["subTime"]
    boundaries = sorted({
        0,
        counter_duration,
        *(time for begin, end, _canvas, _meta in stage_timeline
          for time in (begin, end)),
    })
    effect = engine.WzSubProperty("effect", target)
    for begin, end in zip(boundaries, boundaries[1:]):
        stage = next(
            (entry for entry in stage_timeline if entry[0] <= begin < entry[1]),
            None,
        )
        name = str(len(engine.base.numeric_canvases(effect)))
        if stage is not None and stage[2] is not None and begin < counter_duration:
            frame = engine.base.compose_frames(
                (stage[2], stage[3]),
                (icon_canvas, icon_meta),
                name,
                effect,
                key,
            )
        elif stage is not None and stage[2] is not None:
            frame = engine.base.encode_target_canvas(
                stage[2], name, effect, key, meta=stage[3]
            )
        elif begin < counter_duration:
            frame = engine.base.encode_target_canvas(
                icon_canvas, name, effect, key, meta=icon_meta
            )
        else:
            frame = transparent_frame(name, effect, key, end - begin)
        engine.set_int(frame, "delay", end - begin)
        effect.add(frame)
    copy_metadata_values(
        effect, source_metadata_node(metadata, spec.source_id, "effect")
    )
    # Hidden attacks arrive through the normal close-range attack packet, so
    # legacy clients render their caster animation from the standard effect
    # node.  Keep the stage and counter together there; hit stays per monster.
    engine.base.replace_child(target, effect)


def add_legacy_hit_delay(target, skill_id: int) -> None:
    delay = HIT_DELAY_COMPATIBILITY.get(skill_id)
    if delay is None:
        return
    hit = target.get("hit")
    if not isinstance(hit, engine.WzSubProperty):
        raise RuntimeError(f"missing delayed hit node: {skill_id}")
    for variant in hit.children():
        if isinstance(variant, engine.WzSubProperty):
            # delayedTime is a modern name. hitAfter is the equivalent field
            # present in the legacy Skill.wz and read by its hit renderer.
            engine.set_int(variant, "hitAfter", delay)


def extend_animation_with_uols(node, duration_ms: int) -> None:
    frames = engine.base.numeric_canvases(node)
    if not frames:
        raise RuntimeError("cannot extend an empty animation")
    elapsed = sum(engine.base.frame_delay(frame) for frame in frames)
    source_index = 0
    output_index = len(frames)
    while elapsed < duration_ms:
        source = frames[source_index]
        delay = engine.base.frame_delay(source)
        if elapsed + delay > duration_ms:
            raise RuntimeError(
                f"animation cannot end exactly at {duration_ms}ms: {elapsed}+{delay}"
            )
        node.add(engine.WzUolProperty(str(output_index), source.name, node))
        elapsed += delay
        output_index += 1
        source_index = (source_index + 1) % len(frames)


def build_skill(spec, parent, key, groups, metadata):
    target = engine.build_skill_original(spec, parent, key, groups, metadata)
    effect_owner = spec.effect_source_id or spec.source_id
    effect_nodes = tuple(
        name for name in spec.effect_nodes
        if find_source_metadata_node(metadata, effect_owner, name) is not None
    )
    if len(effect_nodes) == 1:
        replace_exact_node(
            target, key, groups, metadata, effect_owner,
            effect_nodes[0], "effect"
        )
    elif effect_nodes:
        replace_time_aligned_node(
            target, key, groups, metadata, effect_owner,
            effect_nodes, "effect"
        )
    if spec.include_hit:
        replace_exact_node(
            target, key, groups, metadata,
            spec.hit_source_id or spec.source_id, "hit"
        )
    for node_name in spec.extra_nodes:
        replace_exact_node(
            target, key, groups, metadata, spec.source_id, node_name
        )
    if spec.target_id in LIGHTNING_SPEAR_STAGE_IDS:
        # SHOW_*_EFFECT type 2 reads `special`. Keep an exact copy of the
        # caster-side stage animation so the timeline remains visible when a
        # previously selected monster dies before a later scheduled strike.
        replace_exact_node(
            target, key, groups, metadata, spec.source_id, "effect", "special"
        )
    if spec.projectile_nodes:
        replace_exact_node(
            target, key, groups, metadata, spec.source_id,
            spec.projectile_nodes[0], "ball"
        )
    if spec.target_id == 15121000:
        # Serpent Screw has no fixed TMS buff time: it owns 100 automatic
        # attacks at 240ms intervals.  Keep the player-side serpent visible
        # through the final scheduled attack instead of ending after 1620ms.
        extend_animation_with_uols(target.get("effect"), 23760)
        replace_time_aligned_node(
            target, key, groups, metadata, spec.source_id,
            ("special0", "special"), "special"
        )
        replace_time_aligned_node(
            target, key, groups, metadata, spec.source_id,
            ("end0", "end"), "end"
        )
    elif spec.target_id == 15121021:
        # Legacy clients never shipped a root `end` attack node. Re-expose the
        # exact end animation as `special`, which SHOW_*_EFFECT type 2 supports.
        replace_time_aligned_node(
            target, key, groups, metadata, spec.source_id,
            ("end0", "end"), "special"
        )
    if spec.target_id in COUNTER_EFFECT_IDS:
        replace_effect_with_counter(target, key, groups, metadata, spec)
    if spec.target_id == 15121002:
        replace_lightning_spear_entry_effect(target, key)
    elif spec.target_id in LIGHTNING_SPEAR_COMBO_VISUAL_IDS:
        replace_lightning_spear_combo_visual(
            target, key, groups, metadata, spec
        )
    add_legacy_hit_delay(target, spec.target_id)
    engine.set_string(target.child("action"), "0", action_for(spec))
    if spec.target_id in AREA_ATTACK_IDS:
        source_info = find_source_metadata_node(metadata, spec.source_id, "info")
        info = engine.WzSubProperty("info", target)
        if source_info is not None:
            copy_metadata_values(info, source_info, {"type"})
        # TMS types above the legacy client range are normalized while all
        # compatible flags (areaAttack/invincible/etc.) remain source-exact.
        engine.set_int(info, "type", 1)
        engine.set_int(info, "areaAttack", 1)
        engine.base.replace_child(target, info)
    source_info2 = find_source_metadata_node(metadata, spec.source_id, "info2")
    if source_info2 is not None:
        info2 = engine.WzSubProperty("info2", target)
        copy_metadata_values(info2, source_info2)
        engine.base.replace_child(target, info2)
    engine.set_string(target, "elemAttr", "l")
    legacy_weapon = LEGACY_WEAPON_TYPES.get(spec.target_id)
    if legacy_weapon is not None:
        engine.set_int(target, "weapon", legacy_weapon)
    for level in range(1, MASTER_LEVEL + 1):
        level_node = target.get(f"level/{level}")
        engine.set_int(level_node, "cooltime", effective_cooldown(spec))
        for name, value in LEVEL_EXTRA_VALUES.get(spec.target_id, {}).items():
            engine.set_int(level_node, name, value)
        for name, value in LEVEL_EXTRA_VECTORS.get(spec.target_id, {}).items():
            engine.set_vector(level_node, name, value)
    return target


def effective_cooldown(spec: SkillSpec) -> int:
    return LOCAL_COOLDOWN_OVERRIDES[spec.target_id]


def level_text(spec: SkillSpec) -> str:
    cooldown_value = effective_cooldown(spec)
    cooldown = f"，冷却时间{cooldown_value}秒" if cooldown_value else ""
    duration = f"，兼容持续{spec.duration_seconds}秒" if spec.duration_seconds else ""
    return (f"消耗MP {spec.mp_con}，最多攻击{spec.mob_count}名敌人，"
            f"以{spec.damage}%伤害攻击{spec.attack_count}次{duration}{cooldown}                    ")


def source_direct_int_values(spec: SkillSpec, node_name: str) -> dict[str, int]:
    root = ET.parse(MS_EXPORT_ROOT / f"{spec.source_id}.xml").getroot()
    node = root.find(f"./imgdir[@name='{node_name}']")
    if node is None:
        return {}
    return {
        child.get("name"): int(child.get("value"))
        for child in node
        if child.tag in {"int", "short", "long"} and child.get("name")
    }


def server_skill_block(spec: SkillSpec) -> str:
    lines = [f'  <imgdir name="{spec.target_id}">', '    <imgdir name="action">',
             f'      <string name="0" value="{action_for(spec)}"/>', "    </imgdir>",
             '    <imgdir name="level">']
    for level in range(1, MASTER_LEVEL + 1):
        lines.extend([
            f'      <imgdir name="{level}">',
            f'        <int name="attackCount" value="{min(15, spec.attack_count)}"/>',
            f'        <int name="cooltime" value="{effective_cooldown(spec)}"/>',
            f'        <int name="damage" value="{spec.damage}"/>',
            f'        <string name="hs" value="h{level}"/>',
            f'        <vector name="lt" x="{spec.lt[0]}" y="{spec.lt[1]}"/>',
            f'        <int name="mobCount" value="{min(15, spec.mob_count)}"/>',
            f'        <int name="mpCon" value="{spec.mp_con}"/>',
            f'        <vector name="rb" x="{spec.rb[0]}" y="{spec.rb[1]}"/>',
            *(f'        <int name="{name}" value="{value}"/>'
              for name, value in LEVEL_EXTRA_VALUES.get(spec.target_id, {}).items()),
            *(f'        <vector name="{name}" x="{value[0]}" y="{value[1]}"/>'
              for name, value in LEVEL_EXTRA_VECTORS.get(spec.target_id, {}).items()),
            *([f'        <int name="time" value="{spec.duration_seconds}"/>']
              if spec.duration_seconds is not None else []),
            "      </imgdir>",
        ])
    lines.extend([
        "    </imgdir>",
        f'    <int name="masterLevel" value="{MASTER_LEVEL}"/>',
        '    <string name="elemAttr" value="l"/>',
    ])
    legacy_weapon = LEGACY_WEAPON_TYPES.get(spec.target_id)
    if legacy_weapon is not None:
        lines.append(f'    <int name="weapon" value="{legacy_weapon}"/>')
    if spec.target_id in AREA_ATTACK_IDS:
        source_info = source_direct_int_values(spec, "info")
        lines.extend([
            '    <imgdir name="info">',
            '      <int name="type" value="1"/>',
            *(f'      <int name="{name}" value="{value}"/>'
              for name, value in source_info.items() if name != "type"),
            *(['      <int name="areaAttack" value="1"/>']
              if "areaAttack" not in source_info else []),
            '    </imgdir>',
        ])
    source_info2 = source_direct_int_values(spec, "info2")
    if source_info2:
        lines.extend([
            '    <imgdir name="info2">',
            *(f'      <int name="{name}" value="{value}"/>'
              for name, value in source_info2.items()),
            '    </imgdir>',
        ])
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
    level_functions = {
        "x": 30,
        "d": math.floor,
        "log10": lambda level: int(level >= 10),
        "log20": lambda level: int(level >= 20),
        "log30": lambda level: int(level >= 30),
    }
    return int(eval(value, {"__builtins__": {}}, level_functions))


def source_multi_attack_times(skill_id: int) -> dict[int, list[int]]:
    root = ET.parse(MS_EXPORT_ROOT / f"{skill_id}.xml").getroot()
    multi = next(
        (child for child in root
         if child.tag == "imgdir" and child.get("name") == "multiAttackInfo"),
        None,
    )
    if multi is None:
        raise RuntimeError(f"missing TMS multiAttackInfo: {skill_id}")
    elapsed = 0
    result: dict[int, list[int]] = {}
    entries = sorted(
        (child for child in multi
         if child.tag == "imgdir" and child.get("name", "").isdigit()),
        key=lambda child: int(child.get("name")),
    )
    for entry in entries:
        values = {child.get("name"): child for child in entry}
        elapsed += int(values["attackTime"].get("value"))
        stage = int(values.get("x", ET.Element("int", {"value": str(skill_id)})).get("value"))
        result.setdefault(stage, []).append(elapsed)
    return result


def java_int_array(source: str, name: str) -> list[int]:
    match = re.search(
        rf"private static final int\[\] {re.escape(name)}\s*=\s*\{{(.*?)\}};",
        source,
        re.DOTALL,
    )
    if match is None:
        raise RuntimeError(f"missing server attack timeline: {name}")
    return [int(value) for value in re.findall(r"\d+", match.group(1))]


def validate_server_attack_timelines() -> None:
    java = SERVER_CLOSE_HANDLER.read_text(encoding="utf-8")
    expected = {
        "WAVE_RIDING_THUNDER_OPENING_TIMES_MS": source_multi_attack_times(15141500)[15141500],
        "WAVE_RIDING_THUNDER_SHOCK_TIMES_MS": source_multi_attack_times(15141500)[15141501],
        "SWIFT_ANNIHILATION_OPENING_TIMES_MS": source_multi_attack_times(15141502)[15141502],
        "SWIFT_ANNIHILATION_SURGE_TIMES_MS": source_multi_attack_times(15141502)[15141503],
    }
    for name, source_times in expected.items():
        server_times = java_int_array(java, name)
        if server_times != source_times:
            raise RuntimeError(
                f"TMS multi-attack timeline mismatch {name}: "
                f"source={source_times} server={server_times}"
            )

    sea_dragon_root = ET.parse(MS_EXPORT_ROOT / "400051015.xml").getroot()
    common = sea_dragon_root.find("./imgdir[@name='common']")
    values = {child.get("name"): child for child in common}
    interval = evaluate_common_value(values["subTime"])
    tick_count = evaluate_common_value(values["v"])
    expected_call = f"intervalTimes(0, {interval}, {(tick_count - 1) * interval})"
    if expected_call not in java:
        raise RuntimeError(
            f"TMS Sea Dragon timeline mismatch: expected {expected_call}"
        )

    spear_root = ET.parse(MS_EXPORT_ROOT / "400051058.xml").getroot()
    spear_common = spear_root.find("./imgdir[@name='common']")
    spear_values = {child.get("name"): child for child in spear_common}
    interval = evaluate_common_value(spear_values["subTime"])
    strike_count = evaluate_common_value(spear_values["x"])
    thunder_count = evaluate_common_value(spear_values["y"])
    finish_time = evaluate_common_value(spear_values["dot"])
    giant_thunder_interval = evaluate_common_value(spear_values["w2"])
    giant_thunder_count = evaluate_common_value(spear_values["s2"])
    scalar_expected = {
        "LIGHTNING_SPEAR_MAX_PRESSES": strike_count,
        "LIGHTNING_SPEAR_MIN_PRESS_INTERVAL_MS": interval,
        "LIGHTNING_SPEAR_THUNDERS_PER_PRESS": thunder_count,
    }
    for name, source_value in scalar_expected.items():
        match = re.search(
            rf"private static final int {re.escape(name)}\s*=\s*(\d+)\s*;",
            java,
        )
        actual = None if match is None else int(match.group(1))
        if actual != source_value:
            raise RuntimeError(
                f"TMS Lightning Spear parameter mismatch {name}: "
                f"source={source_value} server={actual}"
            )
    spear_expected = {
        "LIGHTNING_SPEAR_FINISH_TIMES_MS": [finish_time],
        "LIGHTNING_SPEAR_GIANT_THUNDER_TIMES_MS": [
        finish_time + giant_thunder_interval * (index + 1)
        for index in range(giant_thunder_count)
        ],
    }
    for name, source_times in spear_expected.items():
        server_times = java_int_array(java, name)
        if server_times != source_times:
            raise RuntimeError(
                f"TMS Lightning Spear timeline mismatch {name}: "
                f"source={source_times} server={server_times}"
            )

def validate_source_parameters() -> None:
    validate_server_attack_timelines()
    base_common_names = {
        "maxLevel", "damage", "attackCount", "mobCount", "mpCon",
        "cooltime", "time", "lt", "rb",
    }
    for spec in SKILLS:
        root = ET.parse(MS_EXPORT_ROOT / f"{spec.source_id}.xml").getroot()
        common = next(
            (child for child in root if child.tag == "imgdir" and child.get("name") == "common"),
            None,
        )
        if common is None:
            raise RuntimeError(f"missing source common node: {spec.source_id}")
        root_int_names = {
            child.get("name") for child in root
            if child.tag in {"int", "short", "long"}
        }
        unknown_root_int_names = root_int_names - (
            HANDLED_ROOT_INT_FLAGS | UNSUPPORTED_ROOT_INT_FLAGS
        )
        if unknown_root_int_names:
            raise RuntimeError(
                f"unreviewed TMS root parameters {spec.source_id}: "
                f"{sorted(unknown_root_int_names)}"
            )
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
        source_time = evaluate_common_value(values.get("time")) if "time" in values else None
        if source_time != spec.duration_seconds:
            raise RuntimeError(
                f"TMS duration mismatch {spec.source_id}->{spec.target_id}: "
                f"source={source_time} spec={spec.duration_seconds}"
            )
        source_extra_names = set(values) - base_common_names
        migrated_extra_names = (
            set(LEVEL_EXTRA_VALUES.get(spec.target_id, {}))
            | set(LEVEL_EXTRA_VECTORS.get(spec.target_id, {}))
        )
        if source_extra_names != migrated_extra_names:
            raise RuntimeError(
                f"unmapped TMS common parameters {spec.source_id}->{spec.target_id}: "
                f"missing={sorted(source_extra_names-migrated_extra_names)} "
                f"extra={sorted(migrated_extra_names-source_extra_names)}"
            )
        for name, expected_value in LEVEL_EXTRA_VALUES.get(spec.target_id, {}).items():
            source_value = values.get(name)
            if source_value is None:
                raise RuntimeError(f"missing TMS parameter {spec.source_id}/{name}")
            actual_value = evaluate_common_value(source_value)
            if actual_value != expected_value:
                raise RuntimeError(
                    f"TMS extra parameter mismatch {spec.source_id}/{name}: "
                    f"source={actual_value} spec={expected_value}"
                )
        for name, expected_value in LEVEL_EXTRA_VECTORS.get(spec.target_id, {}).items():
            source_value = values.get(name)
            actual_value = None if source_value is None else (
                int(source_value.get("x")), int(source_value.get("y"))
            )
            if actual_value != expected_value:
                raise RuntimeError(
                    f"TMS extra vector mismatch {spec.source_id}/{name}: "
                    f"source={actual_value} spec={expected_value}"
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


def validate_metadata_values(target, source, label: str,
                             excluded: set[str] | None = None) -> None:
    excluded = excluded or set()
    for child in list(source):
        name = child.attrib.get("name")
        if not name or name in excluded:
            continue
        actual = target.get(name)
        if child.tag in {"int", "short", "long"}:
            if actual is None or int(actual.value) != int(child.attrib["value"]):
                raise RuntimeError(f"metadata mismatch {label}/{name}")
        elif child.tag == "string":
            if actual is None or actual.value != child.attrib["value"]:
                raise RuntimeError(f"metadata mismatch {label}/{name}")
        elif child.tag == "vector":
            expected = (int(child.attrib["x"]), int(child.attrib["y"]))
            if actual is None or (int(actual.x), int(actual.y)) != expected:
                raise RuntimeError(f"metadata mismatch {label}/{name}")


def validate_exact_frame(target_frame, source_frame, groups, metadata,
                         label: str) -> None:
    source_canvas = engine.base.resolve_ms_canvas(
        source_frame, groups, metadata
    )
    if source_canvas is None:
        has_outlink = any(
            child.tag == "string" and child.attrib.get("name") == "_outlink"
            for child in source_frame
        )
        if has_outlink:
            raise RuntimeError(f"unresolved TMS Canvas: {label}")
        if (int(target_frame.width), int(target_frame.height)) != (1, 1):
            raise RuntimeError(f"transparent Canvas size mismatch {label}")
        expected_origin = engine.base.ms_vector(source_frame, "origin") or (0, 0)
        target_origin = target_frame.get("origin")
        actual_origin = None if target_origin is None else (
            int(target_origin.x), int(target_origin.y)
        )
        if actual_origin != expected_origin:
            raise RuntimeError(f"transparent Canvas origin mismatch {label}")
        expected_delay = engine.base.ms_int(source_frame, "delay", 60) or 60
        if engine.base.frame_delay(target_frame) != expected_delay:
            raise RuntimeError(f"transparent Canvas delay mismatch {label}")
        validate_metadata_values(
            target_frame,
            source_frame,
            label,
            {"_outlink", "origin", "delay"},
        )
        return
    width, height, scale = engine.base.fit_size(
        int(source_canvas.width), int(source_canvas.height)
    )
    if (int(target_frame.width), int(target_frame.height)) != (width, height):
        raise RuntimeError(
            f"Canvas size mismatch {label}: "
            f"target={target_frame.width}x{target_frame.height} "
            f"source-fit={width}x{height}"
        )
    origin = engine.base.canvas_origin(source_canvas, source_frame)
    expected_origin = (round(origin[0] * scale), round(origin[1] * scale))
    target_origin = target_frame.get("origin")
    actual_origin = None if target_origin is None else (
        int(target_origin.x), int(target_origin.y)
    )
    if actual_origin != expected_origin:
        raise RuntimeError(
            f"Canvas origin mismatch {label}: "
            f"target={actual_origin} source-fit={expected_origin}"
        )
    expected_delay = engine.base.ms_int(source_frame, "delay", 60) or 60
    if engine.base.frame_delay(target_frame) != expected_delay:
        raise RuntimeError(f"Canvas delay mismatch {label}")
    validate_metadata_values(
        target_frame,
        source_frame,
        label,
        {"_outlink", "origin", "delay"},
    )


def validate_exact_node(node, target_name: str, source_meta, groups, metadata,
                        label: str) -> None:
    target = node.get(target_name)
    if not isinstance(target, engine.WzSubProperty):
        raise RuntimeError(f"missing visual node {label}")
    direct = animation_frame_entries(source_meta, metadata)
    if direct:
        expected_delays = [
            engine.base.ms_int(frame, "delay", 60) or 60
            for _name, frame in direct
        ]
        actual_delays = []
        for frame_name, source_frame in direct:
            frame = target.get(frame_name)
            if not isinstance(frame, engine.WzCanvasProperty):
                raise RuntimeError(f"missing visual frame {label}/{frame_name}")
            actual_delays.append(engine.base.frame_delay(frame))
            validate_exact_frame(
                frame, source_frame, groups, metadata,
                f"{label}/{frame_name}",
            )
        if actual_delays != expected_delays:
            raise RuntimeError(f"timeline mismatch {label}")
        validate_metadata_values(target, source_meta, label)
        return
    source_variants = [
        child for child in list(source_meta)
        if child.tag == "imgdir"
        and animation_frame_entries(child, metadata)
    ]
    for source_variant in source_variants:
        variant_name = source_variant.attrib["name"]
        variant = target.get(variant_name)
        if not isinstance(variant, engine.WzSubProperty):
            raise RuntimeError(f"missing visual variant {label}/{variant_name}")
        source_frames = animation_frame_entries(source_variant, metadata)
        expected_delays = [
            engine.base.ms_int(frame, "delay", 60) or 60
            for _name, frame in source_frames
        ]
        frames = []
        for frame_name, source_frame in source_frames:
            frame = variant.get(frame_name)
            if not isinstance(frame, engine.WzCanvasProperty):
                raise RuntimeError(
                    f"missing visual frame {label}/{variant_name}/{frame_name}"
                )
            frames.append(frame)
            validate_exact_frame(
                frame, source_frame, groups, metadata,
                f"{label}/{variant_name}/{frame_name}",
            )
        if ([engine.base.frame_delay(frame) for frame in frames] != expected_delays):
            raise RuntimeError(f"timeline mismatch {label}/{variant_name}")
        validate_metadata_values(
            variant, source_variant, f"{label}/{variant_name}"
        )
    validate_metadata_values(target, source_meta, label)


def animation_delays_with_uols(node) -> list[int]:
    entries = sorted(
        (child for child in node.children() if child.name.isdigit()),
        key=lambda child: int(child.name),
    )
    delays = []
    for child in entries:
        if isinstance(child, engine.WzCanvasProperty):
            source = child
        elif isinstance(child, engine.WzUolProperty):
            source = node._children.get(str(child.value))
            if not isinstance(source, engine.WzCanvasProperty):
                raise RuntimeError(
                    f"invalid animation UOL {node.name}/{child.name}->{child.value}"
                )
        else:
            continue
        delays.append(engine.base.frame_delay(source))
    return delays


def validate() -> None:
    validate_source_parameters()
    groups, _strings, metadata = engine.load_sources()
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
        expected_weapon = LEGACY_WEAPON_TYPES.get(spec.target_id)
        weapon = node.get("weapon")
        actual_weapon = None if weapon is None else int(weapon.value)
        if actual_weapon != expected_weapon or node.get("weapon2") is not None:
            raise RuntimeError(f"legacy weapon mismatch {spec.target_id}")
        info = node.get("info")
        if not isinstance(info, engine.WzSubProperty):
            raise RuntimeError(f"missing client info node {spec.target_id}")
        info_type = info.get("type")
        if info_type is None or int(info_type.value) != 1:
            raise RuntimeError(f"legacy info type mismatch {spec.target_id}")
        area_attack = info.get("areaAttack")
        if area_attack is None or int(area_attack.value) != 1:
            raise RuntimeError(f"missing client areaAttack {spec.target_id}")
        for name, expected_value in source_direct_int_values(spec, "info").items():
            if name == "type":
                continue
            value = info.get(name)
            if value is None or int(value.value) != expected_value:
                raise RuntimeError(f"client info mismatch {spec.target_id}/{name}")
        source_info2 = source_direct_int_values(spec, "info2")
        info2 = node.get("info2")
        if source_info2 and not isinstance(info2, engine.WzSubProperty):
            raise RuntimeError(f"missing client info2 node {spec.target_id}")
        for name, expected_value in source_info2.items():
            value = info2.get(name)
            if value is None or int(value.value) != expected_value:
                raise RuntimeError(f"client info2 mismatch {spec.target_id}/{name}")
        level = node.get(f"level/{MASTER_LEVEL}")
        values = (int(level.get("damage").value), int(level.get("attackCount").value),
                  int(level.get("mobCount").value), int(level.get("mpCon").value),
                  int(level.get("cooltime").value))
        expected_values = (
            spec.damage,
            spec.attack_count,
            spec.mob_count,
            spec.mp_con,
            effective_cooldown(spec),
        )
        if values != expected_values:
            raise RuntimeError(f"attack parameter mismatch {spec.target_id}: {values}")
        for name, expected_value in LEVEL_EXTRA_VALUES.get(spec.target_id, {}).items():
            value = level.get(name)
            if value is None or int(value.value) != expected_value:
                raise RuntimeError(
                    f"extra parameter mismatch {spec.target_id}/{name}"
                )
        for name, expected_value in LEVEL_EXTRA_VECTORS.get(spec.target_id, {}).items():
            value = level.get(name)
            if value is None or (int(value.x), int(value.y)) != expected_value:
                raise RuntimeError(
                    f"extra vector mismatch {spec.target_id}/{name}"
                )
        duration = level.get("time")
        actual_duration = int(duration.value) if duration is not None else None
        if actual_duration != spec.duration_seconds:
            raise RuntimeError(f"duration mismatch {spec.target_id}")
        lt = level.get("lt")
        rb = level.get("rb")
        if (int(lt.x), int(lt.y), int(rb.x), int(rb.y)) != (*spec.lt, *spec.rb):
            raise RuntimeError(f"range mismatch {spec.target_id}")
        invisible = node.get("invisible")
        if (invisible is not None) != spec.hidden:
            raise RuntimeError(f"visibility mismatch {spec.target_id}")
        if (spec.effect_nodes
                and spec.target_id != 15121002
                and spec.target_id not in LIGHTNING_SPEAR_COMBO_VISUAL_IDS):
            effect_owner = spec.effect_source_id or spec.source_id
            effect_nodes = tuple(
                name for name in spec.effect_nodes
                if find_source_metadata_node(metadata, effect_owner, name) is not None
            )
            timelines = [
                source_timeline(
                    groups, metadata, effect_owner, name
                )
                for name in effect_nodes
            ]
            boundaries = sorted({
                time
                for timeline in timelines
                for begin, end, _canvas, _meta in timeline
                for time in (begin, end)
            })
            frames = engine.base.numeric_canvases(node.get("effect"))
            delays = [engine.base.frame_delay(frame) for frame in frames]
            expected_delays = [
                end - begin for begin, end in zip(boundaries, boundaries[1:])
            ]
            if spec.target_id in COUNTER_EFFECT_IDS:
                schedule = counter_schedule(spec.target_id)
                duration = schedule[1] - schedule[0]
                boundaries = sorted({
                    *boundaries,
                    *schedule,
                    *(start + duration for start in schedule),
                })
                expected_delays = [
                    end - begin
                    for begin, end in zip(boundaries, boundaries[1:])
                ]
            if delays != expected_delays:
                raise RuntimeError(f"effect timeline mismatch {spec.target_id}")
            if spec.target_id == 15121000:
                complete_delays = animation_delays_with_uols(node.get("effect"))
                if complete_delays[:len(expected_delays)] != expected_delays:
                    raise RuntimeError("Sea Dragon source animation prefix mismatch")
                if sum(complete_delays) != 23760:
                    raise RuntimeError(
                        f"Sea Dragon visual duration mismatch: {sum(complete_delays)}"
                    )
        if spec.target_id == 15121002:
            effect_frames = engine.base.numeric_canvases(node.get("effect"))
            if (len(effect_frames) != 1
                    or int(effect_frames[0].width) != 1
                    or int(effect_frames[0].height) != 1
                    or engine.base.frame_delay(effect_frames[0]) != 180):
                raise RuntimeError(
                    f"non-transparent Lightning Spear entry effect {spec.target_id}"
                )
        if spec.target_id in LIGHTNING_SPEAR_COMBO_VISUAL_IDS:
            effect = node.get("effect")
            if not isinstance(effect, engine.WzSubProperty):
                raise RuntimeError(
                    f"missing Lightning Spear combo effect {spec.target_id}"
                )
            effect_frames = engine.base.numeric_canvases(effect)
            if not effect_frames or not any(
                    int(frame.width) > 1 and int(frame.height) > 1
                    for frame in effect_frames):
                raise RuntimeError(
                    f"transparent Lightning Spear combo effect {spec.target_id}"
                )
            stage_timeline = source_timeline(
                groups, metadata, spec.source_id, "effect"
            )
            expected_boundaries = sorted({
                0,
                LEVEL_EXTRA_VALUES[15121002]["subTime"],
                *(time for begin, end, _canvas, _meta in stage_timeline
                  for time in (begin, end)),
            })
            expected_delays = [
                end - begin
                for begin, end in zip(
                    expected_boundaries, expected_boundaries[1:]
                )
            ]
            actual_delays = [
                engine.base.frame_delay(frame) for frame in effect_frames
            ]
            if actual_delays != expected_delays:
                raise RuntimeError(
                    f"Lightning Spear combo timeline mismatch {spec.target_id}: "
                    f"expected={expected_delays} actual={actual_delays}"
                )
            actual_duration = sum(actual_delays)
            expected_duration = expected_boundaries[-1]
            if actual_duration != expected_duration:
                raise RuntimeError(
                    f"Lightning Spear combo duration mismatch {spec.target_id}: "
                    f"expected={expected_duration} actual={actual_duration}"
                )
        if spec.target_id in LIGHTNING_SPEAR_STAGE_IDS:
            validate_exact_node(
                node,
                "special",
                source_metadata_node(metadata, spec.source_id, "effect"),
                groups,
                metadata,
                f"{spec.target_id}/special",
            )
        if spec.include_hit:
            hit_owner = spec.hit_source_id or spec.source_id
            validate_exact_node(
                node,
                "hit",
                source_metadata_node(metadata, hit_owner, "hit"),
                groups,
                metadata,
                f"{spec.target_id}/hit",
            )
        expected_hit_after = HIT_DELAY_COMPATIBILITY.get(spec.target_id)
        if expected_hit_after is not None:
            hit_variant = node.get("hit/0")
            hit_after = hit_variant.get("hitAfter")
            if hit_after is None or int(hit_after.value) != expected_hit_after:
                raise RuntimeError(
                    f"legacy hitAfter mismatch {spec.target_id}: "
                    f"expected={expected_hit_after}"
                )
        for node_name in spec.extra_nodes:
            validate_exact_node(
                node,
                node_name,
                source_metadata_node(metadata, spec.source_id, node_name),
                groups,
                metadata,
                f"{spec.target_id}/{node_name}",
            )
        if spec.projectile_nodes:
            validate_exact_node(
                node,
                "ball",
                source_metadata_node(
                    metadata, spec.source_id, spec.projectile_nodes[0]
                ),
                groups,
                metadata,
                f"{spec.target_id}/ball",
            )
        if spec.target_id == 15121000:
            for target_name, source_names in (
                    ("special", ("special0", "special")),
                    ("end", ("end0", "end"))):
                timelines = [
                    source_timeline(groups, metadata, spec.source_id, name)
                    for name in source_names
                ]
                boundaries = sorted({
                    time
                    for timeline in timelines
                    for begin, end, _canvas, _meta in timeline
                    for time in (begin, end)
                })
                frames = engine.base.numeric_canvases(node.get(target_name))
                if [engine.base.frame_delay(frame) for frame in frames] != [
                        end - begin
                        for begin, end in zip(boundaries, boundaries[1:])]:
                    raise RuntimeError(
                        f"toggle effect timeline mismatch {spec.target_id}/{target_name}"
                    )
        if spec.target_id == 15121021:
            timelines = [
                source_timeline(groups, metadata, spec.source_id, name)
                for name in ("end0", "end")
            ]
            boundaries = sorted({
                time
                for timeline in timelines
                for begin, end, _canvas, _meta in timeline
                for time in (begin, end)
            })
            special = node.get("special")
            if not isinstance(special, engine.WzSubProperty):
                raise RuntimeError("missing Sea Dragon legacy end special")
            if [
                    engine.base.frame_delay(frame)
                    for frame in engine.base.numeric_canvases(special)
            ] != [
                    end - begin
                    for begin, end in zip(boundaries, boundaries[1:])
            ]:
                raise RuntimeError("Sea Dragon legacy end timeline mismatch")
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
        expected_weapon = LEGACY_WEAPON_TYPES.get(spec.target_id)
        server_weapon = server_node.find("./int[@name='weapon']")
        actual_weapon = (
            None if server_weapon is None else int(server_weapon.get("value"))
        )
        if (actual_weapon != expected_weapon
                or server_node.find("./int[@name='weapon2']") is not None):
            raise RuntimeError(f"server legacy weapon mismatch {spec.target_id}")
        server_info = server_node.find("./imgdir[@name='info']")
        if server_info is None:
            raise RuntimeError(f"missing server info node {spec.target_id}")
        server_info_type = server_info.find("./int[@name='type']")
        if server_info_type is None or int(server_info_type.get("value")) != 1:
            raise RuntimeError(f"server info type mismatch {spec.target_id}")
        server_area_attack = server_info.find("./int[@name='areaAttack']")
        if (server_area_attack is None
                or int(server_area_attack.get("value")) != 1):
            raise RuntimeError(f"missing server areaAttack {spec.target_id}")
        for name, expected_value in source_direct_int_values(spec, "info").items():
            if name == "type":
                continue
            value = server_info.find(f"./int[@name='{name}']")
            if value is None or int(value.get("value")) != expected_value:
                raise RuntimeError(f"server info mismatch {spec.target_id}/{name}")
        source_info2 = source_direct_int_values(spec, "info2")
        server_info2 = server_node.find("./imgdir[@name='info2']")
        if source_info2 and server_info2 is None:
            raise RuntimeError(f"missing server info2 node {spec.target_id}")
        for name, expected_value in source_info2.items():
            value = server_info2.find(f"./int[@name='{name}']")
            if value is None or int(value.get("value")) != expected_value:
                raise RuntimeError(f"server info2 mismatch {spec.target_id}/{name}")
        server_level = server_node.find(
            f"./imgdir[@name='level']/imgdir[@name='{MASTER_LEVEL}']"
        )
        if server_level is None:
            raise RuntimeError(f"missing server level {spec.target_id}")
        server_values = tuple(
            int(server_level.find(f"./int[@name='{name}']").get("value"))
            for name in ("damage", "attackCount", "mobCount", "mpCon", "cooltime")
        )
        expected_values = (
            spec.damage,
            spec.attack_count,
            spec.mob_count,
            spec.mp_con,
            effective_cooldown(spec),
        )
        if server_values != expected_values:
            raise RuntimeError(f"server parameter mismatch {spec.target_id}")
        for name, expected_value in LEVEL_EXTRA_VALUES.get(spec.target_id, {}).items():
            value = server_level.find(f"./int[@name='{name}']")
            if value is None or int(value.get("value")) != expected_value:
                raise RuntimeError(
                    f"server extra parameter mismatch {spec.target_id}/{name}"
                )
        for name, expected_value in LEVEL_EXTRA_VECTORS.get(spec.target_id, {}).items():
            value = server_level.find(f"./vector[@name='{name}']")
            actual_value = None if value is None else (
                int(value.get("x")), int(value.get("y"))
            )
            if actual_value != expected_value:
                raise RuntimeError(
                    f"server extra vector mismatch {spec.target_id}/{name}"
                )
        duration = server_level.find("./int[@name='time']")
        actual_duration = int(duration.get("value")) if duration is not None else None
        if actual_duration != spec.duration_seconds:
            raise RuntimeError(f"server duration mismatch {spec.target_id}")
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
