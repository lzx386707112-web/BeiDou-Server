#!/usr/bin/env python3
"""Migrate TMS Hero, Paladin, and Dark Knight V/VI attacks into legacy 4th-job books."""

from __future__ import annotations

import argparse
import html
import math
import shutil
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
PATCH_SKILL = ROOT / "tool" / "scripts" / "patch-skill"
sys.path.insert(0, str(PATCH_SKILL))

import patch_blaze_wizard_v_vi as engine  # noqa: E402


TMS_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
MS_EXPORT_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-MS-Export/ExplorerWarrior")
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"
CLIENT_MAP_EFFECT = ROOT / "clien" / "Data" / "Map" / "Effect.img"
SECOND_ATOM_METADATA = TMS_ROOT / "Etc" / "SecondAtom.img"
SECOND_ATOM_CANVAS = TMS_ROOT / "Etc" / "_Canvas" / "SecondAtom.img"
MASTER_LEVEL = 30


@dataclass(frozen=True)
class JobSpec:
    key: str
    book: int
    source_groups: tuple[str, ...]
    action: str
    custom_ids: tuple[int, ...] | range
    video_markers: tuple[str, ...]
    skills: tuple[engine.SkillSpec, ...]


SkillSpec = engine.SkillSpec


HERO_SKILLS = (
    SkillSpec(1121012, 400011027, "40001", "斗气死亡断层", 880, 14, 15, 500, 0, False,
              effect_nodes=("effect",), extra_nodes=("special",), lt=(-690, -350), rb=(520, 190)),
    SkillSpec(1121013, 1141000, "114", "狂暴攻击VI", 530, 4, 8, 51, 0, False,
              lt=(-360, -240), rb=(40, 70)),
    SkillSpec(1121014, 400011001, "40001", "燃烧灵魂之剑", 470, 12, 8, 350, 0, False,
              effect_nodes=(), include_hit=False, duration_seconds=20),
    SkillSpec(1121015, 400011002, "40001", "燃烧灵魂之剑：攻击", 252, 12, 8, 350,
              icon_source_id=400011001, effect_nodes=(),
              lt=(-900, -600), rb=(900, 450), duration_seconds=120, include_hit=False),
    SkillSpec(1121020, 400011124, "40001", "剑影分身", 275, 4, 8, 700, 0, False,
              effect_nodes=(), hit_source_id=400011125,
              lt=(-600, -300), rb=(5, 50)),
    SkillSpec(1121021, 400011125, "40001", "剑影分身：斩击", 275, 4, 8,
              icon_source_id=400011124, lt=(-600, -300), rb=(5, 50)),
    SkillSpec(1121022, 400011126, "40001", "剑影分身：爆发", 550, 5, 8,
              icon_source_id=400011124, lt=(-600, -300), rb=(5, 50)),
    SkillSpec(1121023, 1141500, "114", "圣剑降临", 472, 14, 15, 1200, 10, False,
              effect_nodes=(), lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(1121024, 1141501, "114", "圣剑降临：魂灵巨剑", 470, 15, 15,
              icon_source_id=1141500, effect_nodes=(), lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(1121025, 1141002, "114", "愤怒爆发VI", 341, 8, 10, 230, 0, False,
              effect_nodes=("effect", "effect0", "effect1"), lt=(-460, -600), rb=(110, 140)),
    SkillSpec(1121030, 1141008, "114", "烈焰翔斩VI", 640, 4, 8, 42, 0, False,
              effect_nodes=("effect", "effect0"), extra_nodes=("mob",),
              lt=(-380, -320), rb=(120, 70), duration_seconds=60),
)


PALADIN_SKILLS = (
    SkillSpec(1221015, 400011072, "40001", "圣十字架", 515, 12, 12, 1000, 0, False,
              effect_nodes=(),
              lt=(-210, -100), rb=(210, 30), duration_seconds=4),
    SkillSpec(1221016, 400011131, "40001", "雷神战锤", 535, 6, 4, 400, 0, False,
              effect_nodes=(),
              lt=(-500, -500), rb=(500, 500)),
    SkillSpec(1221017, 400011132, "40001", "雷神战锤：爆炸", 605, 9, 6,
              icon_source_id=400011131, effect_nodes=(),
              lt=(-240, -240), rb=(240, 240)),
    SkillSpec(1221020, 1241500, "124", "圣域展开", 787, 9, 15, 1200, 10, False,
              effect_nodes=(), lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(1221021, 1241502, "124", "圣域展开：圣域打击", 1200, 13, 5,
              icon_source_id=1241500, lt=(-500, -400), rb=(500, 300)),
    SkillSpec(1221022, 1241503, "124", "圣域展开：终结", 895, 14, 15,
              icon_source_id=1241500, effect_nodes=(), lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(1221027, 1241007, "124", "鬼神之击VI", 237, 8, 15, 90, 0, False,
              effect_nodes=("effect", "effect0"), lt=(-500, -440), rb=(400, 250)),
    SkillSpec(1221028, 1241010, "124", "鬼神之击VI：余震", 237, 8, 15,
              icon_source_id=1241007, effect_nodes=("effect", "effect0"),
              lt=(-500, -440), rb=(400, 250)),
    SkillSpec(1221029, 1241009, "124", "正义崛起", 1060, 6, 1,
              effect_nodes=(), lt=(-450, -550), rb=(450, 200)),
    SkillSpec(1221030, 1241504, "124", "圣狮之主", 10924, 10, 15, 1000, 10, False,
              effect_nodes=(),
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(1221031, 1241505, "124", "圣狮之主：终结", 10908, 13, 15,
              icon_source_id=1241504, effect_nodes=(), lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(1221032, 400011072, "40001", "圣十字架：持续攻击", 515, 12, 12, 1000,
              icon_source_id=400011072, effect_nodes=(), include_hit=False,
              lt=(-210, -100), rb=(210, 30)),
)


DARK_KNIGHT_SKILLS = (
    SkillSpec(1321011, 400011004, "40001", "断罪之枪", 875, 7, 12, 350, 0, False,
              lt=(-700, -450), rb=(700, 250)),
    SkillSpec(1321015, 400011068, "40001", "枪刺旋风", 583, 8, 12, 100, 0, False,
              effect_nodes=("keydown",), extra_nodes=("prepare", "keydownend", "keydownFinish"),
              lt=(-650, -400), rb=(100, 15)),
    SkillSpec(1321016, 400011069, "40001", "枪刺旋风：终结", 1254, 15, 12,
              icon_source_id=400011068, lt=(-575, -350), rb=(5, 15)),
    SkillSpec(1321018, 1341500, "134", "灭世永恒之枪", 1200, 6, 15, 1200, 10, False,
              effect_nodes=(), lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(1321019, 1341501, "134", "灭世永恒之枪：终结", 1035, 14, 15,
              icon_source_id=1341500, effect_nodes=(), lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(1321020, 1341001, "134", "暗炎斩连杀VI", 568, 6, 8, 55, 0, False,
              lt=(-465, -230), rb=(30, 95)),
    SkillSpec(1321021, 1341002, "134", "闇之标枪", 586, 7, 12, 57, 0,
              icon_source_id=1341001, lt=(-600, -290), rb=(30, 95)),
    SkillSpec(1321022, 1341003, "134", "黑暗统合VI", 775, 12, 12, 220, 0, False,
              lt=(-335, -450), rb=(335, 120)),
    SkillSpec(1321025, 1341502, "134", "黑暗契约", 4115, 12, 15, 1000, 10, False,
              effect_nodes=("effect", "effect2", "effect3", "effect4"), extra_nodes=("special",),
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(1321026, 1341503, "134", "黑暗契约：终结", 5534, 15, 15,
              icon_source_id=1341502, effect_nodes=(), lt=(-1200, -800), rb=(1200, 800)),
)


JOBS = (
    JobSpec("hero", 112, ("114", "40001"), "brandish1", range(1121012, 1121031),
            ("spiritCaliberVideoLayer",), HERO_SKILLS),
    JobSpec("paladin", 122, ("121", "124", "40001"), "blast", range(1221013, 1221033),
            ("sacredBastionVideoLayer", "dominusObrionVideoLayer"), PALADIN_SKILLS),
    JobSpec("darkKnight", 132, ("134", "40001"), "swingP1", range(1321011, 1321027),
            ("deadSpaceVideoLayer", "darkHalidomVideoLayer"), DARK_KNIGHT_SKILLS),
)


CURRENT_JOB: JobSpec | None = None
ORIGINAL_BUILD_SKILL = engine.build_skill
PARAMETER_SOURCE_IDS = {}
COOLDOWN_SOURCE_FIELDS = {
    1121014: "x",
}
COOLDOWN_OVERRIDES = {
    1121012: 0,
    1121013: 0,
    1121014: 0,
    1121020: 0,
    1121023: 10,
    1121025: 0,
    1121030: 0,
    1221015: 0,
    1221016: 0,
    1221020: 10,
    1221027: 0,
    1221030: 10,
    1321011: 0,
    1321015: 0,
    1321016: 0,
    1321018: 10,
    1321019: 0,
    1321020: 0,
    1321021: 0,
    1321022: 0,
    1321025: 10,
    1321026: 0,
}
NESTED_HIT_PATHS = {
    1121015: "summon/attack1/info/hit",
}
def configured_backup(path: Path) -> None:
    if CURRENT_JOB is None:
        raise RuntimeError("job is not configured")
    target = path.with_name(path.name + f".bak-{CURRENT_JOB.key}-v-vi")
    if not target.exists():
        shutil.copy2(path, target)
        print(f"backup: {target}")


def source_animation_layer(groups, metadata, skill_id: int, node_name: str):
    node = metadata.roots[skill_id]
    for segment in node_name.split("/"):
        node = metadata.child(node, segment)
    frames = sorted(
        (child for child in node if child.get("name", "").isdigit()
         and child.tag in {"canvas", "uol"}),
        key=lambda child: int(child.get("name")),
    )
    leading_delay = 0
    result = []
    for raw_frame in frames:
        frame = metadata.resolve(raw_frame)
        has_outlink = any(
            child.tag == "string" and child.get("name") == "_outlink"
            for child in frame
        )
        empty_placeholder = (
            frame.tag == "canvas"
            and frame.get("width") == "1"
            and frame.get("height") == "1"
            and not has_outlink
        )
        if empty_placeholder and not result:
            leading_delay += engine.base.ms_int(frame, "delay", 0) or 0
            continue
        canvas = engine.base.resolve_ms_canvas(frame, groups, metadata)
        if canvas is not None:
            result.append((canvas, frame))
    return leading_delay, result


def transparent_frame(name: str, parent, key, delay: int):
    image = engine.base.Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    frame = engine.WzCanvasProperty(name, parent)
    frame.width = 1
    frame.height = 1
    frame.format = engine.base.CANVAS_FORMAT
    frame.format2 = 0
    frame._png_data = engine.base.encode_canvas_payload(
        image, engine.base.CANVAS_FORMAT, 1, 1, key=key, listwz=False, zlib_level=9
    )
    frame._png_length = len(frame._png_data)
    engine.set_vector(frame, "origin", (0, 0))
    engine.set_int(frame, "delay", delay)
    return frame


def encode_offset_frame(
        canvas, meta, name, parent, key, delay: int,
        offset: tuple[int, int] = (0, 0),
):
    image = engine.base.clean_rgba(engine.base.decode_source_canvas(canvas))
    width, height, scale = engine.base.fit_size(image.width, image.height)
    if (width, height) != image.size:
        resized = image.resize((width, height), Image.Resampling.LANCZOS)
        image.close()
        image = resized
    frame = engine.WzCanvasProperty(name, parent)
    frame.width = width
    frame.height = height
    frame.format = engine.base.CANVAS_FORMAT
    frame.format2 = 0
    frame._png_data = engine.base.encode_canvas_payload(
        image, engine.base.CANVAS_FORMAT, width, height,
        key=key, listwz=False, zlib_level=9,
    )
    image.close()
    frame._png_length = len(frame._png_data)
    origin = engine.base.canvas_origin(canvas, meta)
    engine.set_vector(
        frame, "origin",
        (round((origin[0] - offset[0]) * scale),
         round((origin[1] - offset[1]) * scale)),
    )
    engine.set_int(frame, "delay", delay)
    if meta is not None:
        for child in meta:
            property_name = child.attrib.get("name")
            if not property_name or property_name in {"_outlink", "origin", "delay"}:
                continue
            if child.tag in {"int", "short", "long"}:
                engine.set_int(frame, property_name, int(child.attrib["value"]))
            elif child.tag == "string":
                engine.set_string(frame, property_name, child.attrib["value"])
            elif child.tag == "vector":
                engine.set_vector(
                    frame, property_name,
                    (int(child.attrib["x"]), int(child.attrib["y"])),
                )
    return frame


def compose_layers(
        active, name, parent, key, delay: int,
        offsets: list[tuple[int, int]] | None = None,
):
    canvases = [item[0] for item in active]
    metas = [item[1] for item in active]
    images = [
        engine.base.clean_rgba(engine.base.decode_source_canvas(canvas))
        for canvas in canvases
    ]
    origins = [
        engine.base.canvas_origin(canvas, meta)
        for canvas, meta in zip(canvases, metas)
    ]
    if offsets is None:
        offsets = [(0, 0)] * len(active)
    left = min(-origin[0] + offset[0] for origin, offset in zip(origins, offsets))
    top = min(-origin[1] + offset[1] for origin, offset in zip(origins, offsets))
    right = max(
        image.width - origin[0] + offset[0]
        for image, origin, offset in zip(images, origins, offsets)
    )
    bottom = max(
        image.height - origin[1] + offset[1]
        for image, origin, offset in zip(images, origins, offsets)
    )
    merged_width, merged_height = max(1, right - left), max(1, bottom - top)
    merged = Image.new("RGBA", (merged_width, merged_height), (0, 0, 0, 0))
    for image, origin, offset in zip(images, origins, offsets):
        merged.alpha_composite(
            image,
            (-origin[0] + offset[0] - left, -origin[1] + offset[1] - top),
        )
    for image in images:
        image.close()
    width, height, scale = engine.base.fit_size(merged.width, merged.height)
    if (width, height) != merged.size:
        resized = merged.resize((width, height), Image.Resampling.LANCZOS)
        merged.close()
        merged = resized
    frame = engine.WzCanvasProperty(name, parent)
    frame.width = width
    frame.height = height
    frame.format = engine.base.CANVAS_FORMAT
    frame.format2 = 0
    frame._png_data = engine.base.encode_canvas_payload(
        merged, engine.base.CANVAS_FORMAT, width, height,
        key=key, listwz=False, zlib_level=9,
    )
    merged.close()
    frame._png_length = len(frame._png_data)
    engine.set_vector(frame, "origin", (round(-left * scale), round(-top * scale)))
    engine.set_int(frame, "delay", delay)
    for child in engine.base.ms_children(metas[0]):
        property_name = child.attrib.get("name")
        if (property_name in {"a0", "a1", "z", "rotate", "flip"}
                and child.tag in {"int", "short", "long"}):
            engine.set_int(frame, property_name, int(child.attrib["value"]))
    return frame


def add_timeline_animation(
        target, output_name: str, key, layers, layer_offset=None,
) -> None:
    if any(not frames for _, frames in layers):
        raise RuntimeError(f"missing concurrent animation layers: {output_name}")

    boundaries = {0}
    intervals = []
    for leading_delay, frames in layers:
        elapsed = leading_delay
        layer_intervals = []
        boundaries.add(elapsed)
        for canvas, meta in frames:
            end = elapsed + engine.base.frame_delay(canvas, meta)
            layer_intervals.append((elapsed, end, (canvas, meta)))
            boundaries.add(end)
            elapsed = end
        intervals.append(layer_intervals)

    timeline = sorted(boundaries)
    effect = engine.WzSubProperty(output_name, target)
    indices = [0] * len(intervals)
    for output_index, start in enumerate(timeline[:-1]):
        active = []
        offsets = []
        for track_index, layer_intervals in enumerate(intervals):
            while (indices[track_index] < len(layer_intervals)
                   and start >= layer_intervals[indices[track_index]][1]):
                indices[track_index] += 1
            if indices[track_index] < len(layer_intervals):
                frame_start, frame_end, frame = layer_intervals[indices[track_index]]
                if frame_start <= start < frame_end:
                    active.append(frame)
                    offsets.append(
                        layer_offset(track_index, start) if layer_offset is not None else (0, 0)
                    )
        delay = timeline[output_index + 1] - start
        if len(active) >= 2 and (len(active) > 2 or layer_offset is not None):
            frame = compose_layers(
                active, str(output_index), effect, key, delay, offsets
            )
        elif len(active) == 2:
            frame = engine.base.compose_frames(
                active[0], active[1], str(output_index), effect, key
            )
            engine.set_int(frame, "delay", delay)
        elif len(active) == 1:
            canvas, meta = active[0]
            if offsets[0] != (0, 0):
                frame = encode_offset_frame(
                    canvas, meta, str(output_index), effect, key, delay, offsets[0]
                )
            else:
                frame = engine.base.encode_target_canvas(
                    canvas, str(output_index), effect, key, meta=meta
                )
                engine.set_int(frame, "delay", delay)
        else:
            frame = transparent_frame(str(output_index), effect, key, delay)
        effect.add(frame)
    target.add(effect)


def add_concurrent_effect(
        target, key, groups, metadata, skill_id: int,
        node_names: tuple[str, ...] = ("effect", "effect0"),
        layer_offset=None,
) -> None:
    layers = [
        source_animation_layer(groups, metadata, skill_id, name)
        for name in node_names
    ]
    add_timeline_animation(target, "effect", key, layers, layer_offset)


def repeated_animation_layer(layer, leading_delay: int, duration_ms: int):
    _, frames = layer
    if not frames:
        raise RuntimeError("cannot repeat an empty animation layer")
    repeated = []
    elapsed = 0
    while elapsed < duration_ms:
        for canvas, meta in frames:
            frame_delay = engine.base.frame_delay(canvas, meta)
            if frame_delay <= 0:
                raise RuntimeError("cannot repeat an animation frame without delay")
            remaining = duration_ms - elapsed
            if frame_delay > remaining:
                clipped_meta = ET.fromstring(ET.tostring(meta, encoding="unicode"))
                delay_node = next(
                    (child for child in clipped_meta if child.get("name") == "delay"),
                    None,
                )
                if delay_node is None:
                    delay_node = ET.SubElement(clipped_meta, "int", {"name": "delay"})
                delay_node.set("value", str(remaining))
                repeated.append((canvas, clipped_meta))
                elapsed += remaining
                break
            repeated.append((canvas, meta))
            elapsed += frame_delay
            if elapsed == duration_ms:
                break
    return leading_delay, repeated


def add_grand_guardian_effect(target, key, groups, metadata) -> None:
    phases = (
        (0, 900, False, ("prepare",)),
        (900, 1520, True, ("keydown", "keydown0")),
        (2420, 480, False, ("prepare2", "prepare20")),
        (2900, 2000, True, ("keydown2", "keydown20")),
        (4900, 960, False, ("keydownend2",)),
    )
    layers = []
    for start, duration, repeat, node_names in phases:
        for node_name in node_names:
            layer = source_animation_layer(groups, metadata, 400011072, node_name)
            if repeat:
                layer = repeated_animation_layer(layer, start, duration)
            else:
                leading_delay, frames = layer
                actual_duration = sum(
                    engine.base.frame_delay(canvas, meta) for canvas, meta in frames
                )
                if actual_duration != duration:
                    raise RuntimeError(
                        f"Grand Guardian phase duration mismatch: "
                        f"{node_name}={actual_duration}ms expected={duration}ms"
                    )
                layer = (start + leading_delay, frames)
            layers.append(layer)
    add_timeline_animation(target, "effect", key, layers)


def add_grand_guardian_hit(target, key, groups, metadata) -> None:
    hit = engine.WzSubProperty("hit", target)
    layers = [
        source_animation_layer(groups, metadata, 400011072, "hit/0"),
        source_animation_layer(groups, metadata, 400011072, "hit2/0"),
    ]
    add_timeline_animation(hit, "0", key, layers)
    target.add(hit)


def add_mighty_mjolnir_summon(target, key, groups, metadata) -> None:
    projectile = engine.tracks(groups, metadata, 400011131, "effect")
    explosion = engine.tracks(groups, metadata, 400011132, "effect")
    if not projectile or not explosion:
        raise RuntimeError("missing Mighty Mjolnir summon animation")
    summon = engine.WzSubProperty("summon", target)
    for state, frames in (
        ("summoned", projectile[0]),
        ("stand", projectile[0][-1:]),
        ("die", explosion[0]),
    ):
        node = engine.WzSubProperty(state, summon)
        engine.base.merge_tracks(frames, [], node, key)
        summon.add(node)
    target.add(summon)


def second_atom_frames(atom_type: int = 70):
    metadata_image = engine.WzImage.from_bytes(
        SECOND_ATOM_METADATA.read_bytes(),
        key=engine.WzKey.for_region("BMS"),
        name=SECOND_ATOM_METADATA.name,
    ).parse()
    canvas_image = engine.WzImage.from_bytes(
        SECOND_ATOM_CANVAS.read_bytes(),
        key=engine.WzKey.for_region("BMS"),
        name=SECOND_ATOM_CANVAS.name,
    ).parse()
    result = []
    for state, limit in (("startEff", None), ("parentAtom", 5), ("endEff2", None)):
        source = metadata_image.get(f"atom/{atom_type}/layer/{state}")
        canvases = canvas_image.get(f"atom/{atom_type}/layer/{state}")
        if not isinstance(source, engine.WzSubProperty) or not isinstance(
                canvases, engine.WzSubProperty):
            raise RuntimeError(f"missing SecondAtom state: {atom_type}/{state}")
        frames = [
            child for child in source.children()
            if isinstance(child, engine.WzCanvasProperty) and child.name.isdigit()
        ]
        frames.sort(key=lambda child: int(child.name))
        if limit is not None:
            frames = frames[:limit]
        for source_frame in frames:
            canvas = canvases.get(source_frame.name)
            if not isinstance(canvas, engine.WzCanvasProperty):
                continue
            meta = ET.Element("canvas")
            origin = source_frame.get("origin")
            if hasattr(origin, "x") and hasattr(origin, "y"):
                ET.SubElement(meta, "vector", {
                    "name": "origin", "x": str(int(origin.x)), "y": str(int(origin.y)),
                })
            delay = source_frame.get("delay")
            ET.SubElement(meta, "int", {
                "name": "delay",
                "value": str(int(delay.value) if isinstance(delay, engine.WzIntProperty) else 60),
            })
            result.append((canvas, meta))
    if not result:
        raise RuntimeError(f"empty SecondAtom animation: {atom_type}")
    return 0, result


def rising_justice_offset(_track_index: int, time_ms: int) -> tuple[int, int]:
    duration = 1080
    progress = min(1.0, time_ms / duration)
    return round(417 - (834 * progress)), round(-147 + (120 * progress))


def add_rising_justice_effect(target, key) -> None:
    add_timeline_animation(
        target, "effect", key, [second_atom_frames()], rising_justice_offset,
    )


def add_burning_soul_blade_summon(target, key, groups, metadata) -> None:
    summon = engine.WzSubProperty("summon", target)
    for state in ("summoned", "stand", "attack1", "die"):
        variants = engine.tracks(groups, metadata, 400011002, f"summon/{state}")
        if not variants:
            raise RuntimeError(f"missing Burning Soul Blade summon state: {state}")
        node = engine.WzSubProperty(state, summon)
        engine.base.merge_tracks(variants[0], [], node, key)
        summon.add(node)

    attack_info = engine.WzSubProperty("info", summon.child("attack1"))
    attack_range = engine.WzSubProperty("range", attack_info)
    engine.set_vector(attack_range, "lt", (-285, -370))
    engine.set_vector(attack_range, "rb", (285, 50))
    attack_info.add(attack_range)
    engine.set_int(attack_info, "attackAfter", 270)
    engine.set_int(attack_info, "mobCount", 8)
    engine.set_int(attack_info, "type", 0)
    summon.child("attack1").add(attack_info)
    target.add(summon)


def spear_of_darkness_layer_offset(track_index: int, time_ms: int) -> tuple[int, int]:
    if track_index != 2 or time_ms <= 510:
        return 0, 0
    travel = min(700, round((time_ms - 510) * 700 / 450))
    return -travel, 0


def build_skill(spec, parent, key, groups, metadata):
    if CURRENT_JOB is None:
        raise RuntimeError("job is not configured")
    target = ORIGINAL_BUILD_SKILL(spec, parent, key, groups, metadata)
    nested_hit = NESTED_HIT_PATHS.get(spec.target_id)
    if nested_hit is not None:
        engine.add_variant_node(
            target, key, groups, metadata, spec.source_id, nested_hit, "hit"
        )
    if spec.target_id == 1221015:
        target._children.pop("hit", None)
        add_grand_guardian_effect(target, key, groups, metadata)
        add_grand_guardian_hit(target, key, groups, metadata)
    elif spec.target_id == 1221032:
        add_grand_guardian_hit(target, key, groups, metadata)
    elif spec.target_id == 1221016:
        add_concurrent_effect(
            target, key, groups, metadata, spec.source_id,
            node_names=("effect0", "special/0"),
        )
        add_mighty_mjolnir_summon(target, key, groups, metadata)
    elif spec.target_id == 1221029:
        add_rising_justice_effect(target, key)
    elif spec.target_id == 1221030:
        add_concurrent_effect(
            target, key, groups, metadata, spec.source_id,
            node_names=("effect", "effect0", "special"),
        )
    elif spec.target_id == 1121014:
        add_burning_soul_blade_summon(target, key, groups, metadata)
        engine.add_variant_node(
            target, key, groups, metadata, 400011002,
            "summon/attack1/info/hit", "hit",
        )
    elif spec.target_id == 1121015:
        engine.add_direct_node(
            target, key, groups, metadata, spec.source_id,
            ("summon/attack1",), "effect",
        )
    elif spec.target_id == 1121020:
        add_concurrent_effect(target, key, groups, metadata, spec.source_id)
    elif spec.target_id == 1321011:
        target._children.pop("effect", None)
        add_concurrent_effect(
            target, key, groups, metadata, spec.source_id,
            node_names=("effect", "special", "shootobj/layerList/b1"),
            layer_offset=spear_of_darkness_layer_offset,
        )
    elif spec.target_id == 1321022:
        target._children.pop("effect", None)
        add_concurrent_effect(
            target, key, groups, metadata, spec.source_id,
            node_names=("effect",),
        )
    elif spec.target_id == 1321025:
        target._children.pop("effect", None)
        add_concurrent_effect(
            target, key, groups, metadata, spec.source_id,
            node_names=("effect", "effect2", "effect3", "effect4"),
        )
    engine.set_string(target.child("action"), "0", CURRENT_JOB.action)
    target._children.pop("elemAttr", None)
    return target


def server_skill_block(spec: SkillSpec) -> str:
    if CURRENT_JOB is None:
        raise RuntimeError("job is not configured")
    lines = [f'  <imgdir name="{spec.target_id}">', '    <imgdir name="action">',
             f'      <string name="0" value="{CURRENT_JOB.action}"/>', "    </imgdir>",
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
            *([f'        <int name="time" value="{spec.duration_seconds}"/>'] if spec.duration_seconds is not None else []),
            "      </imgdir>",
        ])
    lines.extend(["    </imgdir>", f'    <int name="masterLevel" value="{MASTER_LEVEL}"/>'])
    if spec.hidden:
        lines.append('    <int name="invisible" value="1"/>')
    lines.append("  </imgdir>")
    return "\n".join(lines)


def remove_named_blocks(text: str, ids: tuple[int, ...] | range) -> str:
    for skill_id in ids:
        text = engine.remove_xml_block(text, str(skill_id))
    return text


def restore_client_node(path: Path, node_path: str) -> None:
    if CURRENT_JOB is None:
        raise RuntimeError("job is not configured")
    backup = path.with_name(path.name + f".bak-{CURRENT_JOB.key}-v-vi")
    target_image = engine.WzImage.from_bytes(
        path.read_bytes(), key=engine.WzKey.for_region("GMS"), name=path.name
    )
    backup_image = engine.WzImage.from_bytes(
        backup.read_bytes(), key=engine.WzKey.for_region("GMS"), name=backup.name
    )
    target_root = target_image.parse()
    source = backup_image.parse().get(node_path)
    parent_path, name = node_path.rsplit("/", 1) if "/" in node_path else ("", node_path)
    parent = target_root.get(parent_path) if parent_path else target_root
    if not isinstance(source, engine.WzSubProperty) or not isinstance(parent, engine.WzSubProperty):
        raise RuntimeError(f"missing original client node: {node_path}")
    engine.base.replace_child(parent, engine.base.clone_property(source, name, parent))
    engine.base.atomic_write_bytes(
        path, engine.encode_image_body(target_image, target_image.wz_file.reader)
    )


def restore_server_node(path: Path, node_name: str) -> None:
    if CURRENT_JOB is None:
        raise RuntimeError("job is not configured")
    backup = path.with_name(path.name + f".bak-{CURRENT_JOB.key}-v-vi")
    target = path.read_text(encoding="utf-8")
    source = backup.read_text(encoding="utf-8")
    target_start, target_end = engine.find_imgdir_block(target, node_name)
    source_start, source_end = engine.find_imgdir_block(source, node_name)
    engine.base.atomic_write_text(
        path, target[:target_start] + source[source_start:source_end] + target[target_end:]
    )


def restore_original_hero_nodes() -> None:
    if CURRENT_JOB is None or CURRENT_JOB.key != "hero":
        return
    restore_client_node(engine.CLIENT_SKILL, "skill/1121001")
    restore_client_node(CLIENT_STRING, "1121001")
    restore_server_node(engine.SERVER_SKILL, "1121001")
    restore_server_node(SERVER_STRING, "1121001")


def patch_server_skill(dry_run: bool) -> None:
    if CURRENT_JOB is None:
        raise RuntimeError("job is not configured")
    path = ROOT / "gms-server" / "wz" / "Skill.wz" / f"{CURRENT_JOB.book}.img.xml"
    text = remove_named_blocks(path.read_text(encoding="utf-8"), CURRENT_JOB.custom_ids)
    start, end = engine.find_imgdir_block(text, "skill")
    closing = text.rfind("</imgdir>", start, end)
    if closing < 0:
        raise RuntimeError(f"missing skill closing node: {path}")
    blocks = "\n".join(server_skill_block(spec) for spec in CURRENT_JOB.skills)
    updated = text[:closing] + blocks + "\n" + text[closing:]
    if not dry_run:
        configured_backup(path)
        engine.base.atomic_write_text(path, updated)


def evaluate(node: ET.Element | None, level: int = MASTER_LEVEL, default: int = 0) -> int:
    if node is None or node.get("value") is None:
        return default
    return int(eval(node.get("value"), {"__builtins__": {}}, {
        "x": level,
        "d": math.floor,
        "u": math.ceil,
        "log10": lambda value: int(value >= 10),
        "log20": lambda value: int(value >= 20),
        "log30": lambda value: int(value >= 30),
    }))


def validate_source_parameters() -> None:
    if CURRENT_JOB is None:
        raise RuntimeError("job is not configured")
    for spec in CURRENT_JOB.skills:
        parameter_source_id = PARAMETER_SOURCE_IDS.get(spec.target_id, spec.source_id)
        root = ET.parse(MS_EXPORT_ROOT / f"{parameter_source_id}.xml").getroot()
        common = next((child for child in root if child.get("name") == "common"), None)
        values = {} if common is None else {child.get("name"): child for child in common}
        cooldown_name = COOLDOWN_SOURCE_FIELDS.get(spec.target_id, "cooltime")
        actual = (
            evaluate(values.get("damage")),
            evaluate(values.get("attackCount"), default=1),
            evaluate(values.get("mobCount"), default=1),
            evaluate(values.get("mpCon")),
            spec.cooldown if (spec.hidden or parameter_source_id != spec.source_id
                              or spec.target_id in COOLDOWN_OVERRIDES)
            else evaluate(values.get(cooldown_name)),
        )
        expected = (
            spec.damage, spec.attack_count, spec.mob_count, spec.mp_con, spec.cooldown
        )
        if actual != expected:
            raise RuntimeError(
                f"TMS parameter mismatch {parameter_source_id}->{spec.target_id}: source={actual} spec={expected}"
            )
        if "lt" in values and "rb" in values:
            source_range = (
                int(values["lt"].get("x")), int(values["lt"].get("y")),
                int(values["rb"].get("x")), int(values["rb"].get("y")),
            )
            if source_range != (*spec.lt, *spec.rb):
                raise RuntimeError(
                    f"TMS range mismatch {parameter_source_id}->{spec.target_id}: {source_range} != {(*spec.lt, *spec.rb)}"
                )


def validate_nested_hits(root) -> None:
    for target_id in NESTED_HIT_PATHS:
        if CURRENT_JOB is None or target_id not in CURRENT_JOB.custom_ids:
            continue
        if not engine.base.numeric_canvases(root.get(f"skill/{target_id}/hit/0")):
            raise RuntimeError(f"missing nested TMS hit effect: {target_id}")


def configure(job: JobSpec) -> None:
    global CURRENT_JOB
    CURRENT_JOB = job
    engine.TMS_ROOT = TMS_ROOT
    engine.MS_EXPORT_ROOT = MS_EXPORT_ROOT
    engine.SOURCE_PATHS = {
        group: TMS_ROOT / "Skill" / "_Canvas" / f"{group}.img"
        for group in job.source_groups
    }
    engine.CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / f"{job.book}.img"
    engine.CLIENT_STRING = CLIENT_STRING
    engine.CLIENT_MAP_EFFECT = CLIENT_MAP_EFFECT
    engine.SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / f"{job.book}.img.xml"
    engine.SERVER_STRING = SERVER_STRING
    engine.FIELD_EFFECT_ROOT = f"customSkill/{job.key}"
    engine.VIDEO_MARKERS = job.video_markers
    engine.MASTER_LEVEL = MASTER_LEVEL
    engine.CUSTOM_SKILL_IDS = job.custom_ids
    engine.SKILLS = job.skills
    engine.TIMED_EFFECTS = {}
    engine.base.SKILLS = job.skills
    engine.base.MS_EXPORT_ROOT = MS_EXPORT_ROOT
    engine.backup = configured_backup
    engine.build_skill = build_skill
    engine.server_skill_block = server_skill_block


def validate_generated() -> None:
    if CURRENT_JOB is None:
        raise RuntimeError("job is not configured")
    validate_source_parameters()
    image = engine.WzImage.from_bytes(
        engine.CLIENT_SKILL.read_bytes(),
        key=engine.WzKey.for_region("GMS"),
        name=engine.CLIENT_SKILL.name,
    )
    root = image.parse()
    canvas_count = 0
    for spec in CURRENT_JOB.skills:
        node = root.get(f"skill/{spec.target_id}")
        if not isinstance(node, engine.WzSubProperty):
            raise RuntimeError(f"missing client skill: {spec.target_id}")
        action = node.get("action/0")
        level = node.get("level/30")
        if action is None or action.value != CURRENT_JOB.action or level is None:
            raise RuntimeError(f"client action/level mismatch: {spec.target_id}")
        values = (
            int(level.get("damage").value),
            int(level.get("attackCount").value),
            int(level.get("mobCount").value),
            int(level.get("mpCon").value),
            int(level.get("cooltime").value),
            (int(level.get("lt").x), int(level.get("lt").y)),
            (int(level.get("rb").x), int(level.get("rb").y)),
        )
        expected = (
            spec.damage, spec.attack_count, spec.mob_count, spec.mp_con,
            spec.cooldown, spec.lt, spec.rb,
        )
        if values != expected:
            raise RuntimeError(
                f"client level-30 parameter mismatch {spec.target_id}: {values} != {expected}"
            )
        duration = level.get("time")
        actual_duration = None if duration is None else int(duration.value)
        if actual_duration != spec.duration_seconds:
            raise RuntimeError(
                f"client duration mismatch {spec.target_id}: "
                f"{actual_duration} != {spec.duration_seconds}"
            )
        if not spec.hidden and spec.effect_nodes and not engine.base.numeric_canvases(node.get("effect")):
            raise RuntimeError(f"missing flat character effect: {spec.target_id}")
        if spec.include_hit and not engine.base.numeric_canvases(node.get("hit/0")):
            raise RuntimeError(f"missing monster hit effect: {spec.target_id}")
        stack = [node]
        while stack:
            current = stack.pop()
            if isinstance(current, engine.WzCanvasProperty):
                canvas_count += 1
                if int(current.format) != 1 or int(current.format2) != 0:
                    raise RuntimeError(f"non-ARGB4444 Canvas: {spec.target_id}")
                if int(current.width) > 1280 or int(current.height) > 720:
                    raise RuntimeError(
                        f"oversized Canvas {spec.target_id}: {current.width}x{current.height}"
                    )
            if hasattr(current, "children"):
                stack.extend(current.children())
    validate_nested_hits(root)
    effect_root = engine.WzImage.from_bytes(
        CLIENT_MAP_EFFECT.read_bytes(),
        key=engine.WzKey.for_region("GMS"),
        name=CLIENT_MAP_EFFECT.name,
    ).parse()
    for marker in CURRENT_JOB.video_markers:
        frame = effect_root.get(f"customSkill/{CURRENT_JOB.key}/{marker}/0")
        if not isinstance(frame, engine.WzCanvasProperty) or (frame.width, frame.height) != (7, 5):
            raise RuntimeError(f"missing video marker: {CURRENT_JOB.key}/{marker}")
    server = engine.SERVER_SKILL.read_text(encoding="utf-8")
    server_root = ET.fromstring(server)
    server_skills = server_root.find("./imgdir[@name='skill']")
    for spec in CURRENT_JOB.skills:
        engine.find_imgdir_block(server, str(spec.target_id))
        skill = server_skills.find(f"./imgdir[@name='{spec.target_id}']")
        level = skill.find("./imgdir[@name='level']/imgdir[@name='30']")
        properties = {child.get("name"): child for child in level}
        values = (
            int(properties["damage"].get("value")),
            int(properties["attackCount"].get("value")),
            int(properties["mobCount"].get("value")),
            int(properties["mpCon"].get("value")),
            int(properties["cooltime"].get("value")),
            (int(properties["lt"].get("x")), int(properties["lt"].get("y"))),
            (int(properties["rb"].get("x")), int(properties["rb"].get("y"))),
        )
        expected = (
            spec.damage, spec.attack_count, spec.mob_count, spec.mp_con,
            spec.cooldown, spec.lt, spec.rb,
        )
        if values != expected:
            raise RuntimeError(
                f"server level-30 parameter mismatch {spec.target_id}: {values} != {expected}"
            )
        duration = properties.get("time")
        actual_duration = None if duration is None else int(duration.get("value"))
        if actual_duration != spec.duration_seconds:
            raise RuntimeError(
                f"server duration mismatch {spec.target_id}: "
                f"{actual_duration} != {spec.duration_seconds}"
            )
    print(f"validated {CURRENT_JOB.key}: skills={len(CURRENT_JOB.skills)} canvases={canvas_count}")


def migrate_job(job: JobSpec, dry_run: bool) -> None:
    configure(job)
    validate_source_parameters()
    groups, strings, metadata = engine.load_sources()
    engine.patch_client_skill(groups, metadata, dry_run)
    engine.patch_client_string(strings, dry_run)
    patch_server_skill(dry_run)
    engine.patch_server_string(strings, dry_run)
    engine.patch_map_effect(dry_run)
    if not dry_run:
        restore_original_hero_nodes()
        validate_generated()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", choices=("all", *(job.key for job in JOBS)), default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    selected = JOBS if args.job == "all" else tuple(job for job in JOBS if job.key == args.job)
    for job in selected:
        configure(job)
        if args.validate_only:
            validate_generated()
        else:
            migrate_job(job, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
