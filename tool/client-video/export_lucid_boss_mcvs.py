#!/usr/bin/env python3
"""Export TMS Lucid field mechanics as legacy FIELD_EFFECT MCV scenes."""

from __future__ import annotations

import argparse
import importlib.util
import math
import shutil
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
VIDEO_DIR = Path(__file__).resolve().parent
TMS_DATA = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
PROXY_PATH = TMS_DATA / "Etc/BossLucid.img"
CANVAS_PATH = TMS_DATA / "Etc/_Canvas/BossLucid.img"
DEFAULT_OUTPUT_DIRECTORY = ROOT / "clien/Data/Video"
CLIENT_MAP_EFFECT = ROOT / "clien/Data/Map/Effect.img"
FIELD_EFFECT_ROOT = "customSkill/lucid"
MARKER_WIDTH = 7
MARKER_HEIGHT = 5
MARKER_DURATION_MS = 500
PHANTOM_PREPARE_MS = 2400
PHANTOM_HIT_INTERVAL_MS = 1000
PHANTOM_HIT_COUNT = 12
PHANTOM_PROJECTILE_TRAVEL_MS = 720
RUSH_DURATION_MS = 3000

# TMS phase 1 places the right-side dragon at pos1=(2308, 30) and its field
# warning at (1019, 45).  Projecting that 1289-unit gap across map
# VRLeft=-37..VRRight=1960 onto 1280px gives 826px.  Phase 2 reuses the same
# art with every corresponding frame origin shifted 414px left, so 412px
# preserves the same visible right-side placement.
DRAGON_RIGHT_OFFSETS = {
    "phase1": (826, 0),
    "phase2": (412, 0),
}

# Exact TMS BossLucid/RushLucid/path0 field coordinates.  The legacy MCV is a
# screen-space projection, while the server keeps these original coordinates
# for authoritative body-box collision.
RUSH_PATH = (
    ((685, -510), 15),
    ((45, -420), 15),
    ((181, -571), 20),
    ((394, -738), 25),
    ((698, -792), 30),
    ((978, -746), 25),
    ((1067, -587), 20),
    ((1028, -403), 15),
    ((732, -117), 20),
    ((469, -107), 25),
    ((341, -225), 20),
    ((356, -417), 15),
    ((538, -576), 20),
    ((804, -742), 25),
    ((978, -742), 20),
)

# 1280x720 compatibility projection of the TMS Shoot spiral/bidirection field.
# Coordinates are relative to the video centre.  Each quadratic path ends at
# the exact time used by LucidBossCompat for the corresponding damage tick.
PHANTOM_TRAJECTORIES = (
    ((-700, -330), (-410, -300), (-360, 150)),
    ((700, -330), (390, -280), (-120, 120)),
    ((-700, 330), (-390, 270), (120, -110)),
    ((700, 330), (410, 300), (360, 140)),
    ((-700, -220), (-160, -330), (280, -170)),
    ((700, -220), (150, -310), (-280, -160)),
    ((-700, 220), (-130, 320), (40, 180)),
    ((700, 220), (130, 300), (-40, 170)),
    ((-700, -350), (-500, 40), (190, 40)),
    ((700, -350), (500, 60), (-190, 30)),
    ((-700, 350), (-450, -20), (330, -20)),
    ((700, 350), (450, 0), (-330, -30)),
)

sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(VIDEO_DIR))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzKey,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402

from export_soul_eclipse_mcv import (  # noqa: E402
    FOURCC_XOR,
    HEIGHT,
    WIDTH,
    encoder_command,
    read_ivf,
    write_mcv,
)
import export_karing_boss_mcvs as karing  # noqa: E402


ARC_SCRIPT = ROOT / "tool/scripts/migration/migrate_arcane_river_expansion.py"
ARC_SPEC = importlib.util.spec_from_file_location("arcane_river_expansion", ARC_SCRIPT)
if ARC_SPEC is None or ARC_SPEC.loader is None:
    raise RuntimeError(f"cannot import {ARC_SCRIPT}")
arc = importlib.util.module_from_spec(ARC_SPEC)
ARC_SPEC.loader.exec_module(arc)
arc.SOURCE = TMS_DATA


@dataclass(frozen=True)
class LucidSceneSpec:
    key: str
    output_name: str
    marker_name: str
    marker_code: int
    duration_ms: int
    step_ms: int = 60


@dataclass(frozen=True)
class TimelineLayer:
    frames: tuple[tuple[WzCanvasProperty, WzCanvasProperty, int], ...]
    start_ms: int
    end_ms: int
    loop: bool = False
    offsets: tuple[tuple[int, int], ...] = ((0, 0),)
    motion: tuple[tuple[int, int], tuple[int, int], tuple[int, int]] | None = None
    path: tuple[tuple[int, int, int], ...] | None = None


SCENES = (
    LucidSceneSpec("dragon-p1", "lucid-dragon-p1.mcv", "dragonP1VideoLayer", 1, 11850),
    LucidSceneSpec("dragon-p2", "lucid-dragon-p2.mcv", "dragonP2VideoLayer", 2, 11850),
    LucidSceneSpec("laser-rain", "lucid-laser-rain.mcv", "laserRainVideoLayer", 3, 7320),
    LucidSceneSpec(
        "phantom-barrage", "lucid-phantom-barrage.mcv",
        "phantomBarrageVideoLayer", 4, 14880,
    ),
    LucidSceneSpec("rush", "lucid-rush.mcv", "rushVideoLayer", 5, RUSH_DURATION_MS),
    LucidSceneSpec("fury", "lucid-fury.mcv", "furyVideoLayer", 6, 49320, 120),
    LucidSceneSpec(
        "butterfly-burst", "lucid-butterfly-burst.mcv",
        "butterflyBurstVideoLayer", 7, 1620,
    ),
    LucidSceneSpec("bomb", "lucid-bomb.mcv", "bombVideoLayer", 8, 4170),
    LucidSceneSpec(
        "stained-glass-0", "lucid-stained-glass.mcv",
        "stainedGlassVideoLayer", 9, 1260,
    ),
    LucidSceneSpec(
        "stained-glass-1", "lucid-stained-glass-1.mcv",
        "stainedGlass1VideoLayer", 10, 1260,
    ),
    LucidSceneSpec(
        "stained-glass-2", "lucid-stained-glass-2.mcv",
        "stainedGlass2VideoLayer", 11, 1260,
    ),
    LucidSceneSpec(
        "stained-glass-3", "lucid-stained-glass-3.mcv",
        "stainedGlass3VideoLayer", 12, 1260,
    ),
    LucidSceneSpec(
        "stained-glass-4", "lucid-stained-glass-4.mcv",
        "stainedGlass4VideoLayer", 13, 1260,
    ),
    LucidSceneSpec(
        "stained-glass-5", "lucid-stained-glass-5.mcv",
        "stainedGlass5VideoLayer", 14, 1260,
    ),
)


def load_images() -> tuple[WzImage, WzImage]:
    proxy = arc.load_image(PROXY_PATH, arc.BMS_KEY)
    canvas = arc.load_image(CANVAS_PATH, arc.BMS_KEY)
    for image, path in ((proxy, PROXY_PATH), (canvas, CANVAS_PATH)):
        if image.truncated or image.parse_warnings:
            raise RuntimeError(
                f"{path}: truncated={image.truncated} warnings={image.parse_warnings}"
            )
    return proxy, canvas


def numeric_frames(node: WzSubProperty) -> list[WzCanvasProperty]:
    return sorted(
        (
            child for child in node.children()
            if isinstance(child, WzCanvasProperty) and child.name.isdigit()
        ),
        key=lambda frame: int(frame.name),
    )


def frame_delay(frame: WzCanvasProperty, default: int) -> int:
    delay = frame.child("delay")
    return max(1, int(delay.value)) if isinstance(delay, WzIntProperty) else default


def load_sequence(
        proxy: WzImage,
        materializer: arc.CanvasMaterializer,
        path: str,
        default_delay: int = 60,
) -> tuple[tuple[WzCanvasProperty, WzCanvasProperty, int], ...]:
    node = proxy.root.get(path)
    if not isinstance(node, WzSubProperty):
        raise RuntimeError(f"missing BossLucid sequence: {path}")
    output = []
    for frame in numeric_frames(node):
        pixel, _, _, _ = materializer.resolve_canvas(
            frame, proxy, PROXY_PATH, set()
        )
        output.append((frame, pixel, frame_delay(frame, default_delay)))
    if not output:
        raise RuntimeError(f"empty BossLucid sequence: {path}")
    return tuple(output)


def joined(*sequences):
    return tuple(frame for sequence in sequences for frame in sequence)


def sequence_duration(sequence) -> int:
    return sum(frame[2] for frame in sequence)


def rush_screen_path() -> tuple[tuple[int, int, int], ...]:
    """Project the exact TMS field path onto the 1280x720 video plane."""
    weights = []
    for index in range(1, len(RUSH_PATH)):
        (previous, _), (current, speed) = RUSH_PATH[index - 1], RUSH_PATH[index]
        weights.append(math.dist(previous, current) / max(1, speed))
    total_weight = sum(weights)
    elapsed_weight = 0.0
    output = []
    for index, ((x, y), _) in enumerate(RUSH_PATH):
        if index:
            elapsed_weight += weights[index - 1]
        timestamp = (
            RUSH_DURATION_MS if index == len(RUSH_PATH) - 1
            else round(RUSH_DURATION_MS * elapsed_weight / total_weight)
        )
        screen_x = x - WIDTH // 2
        screen_y = round((y + 850) * HEIGHT / 900) - HEIGHT // 2
        output.append((timestamp, screen_x, screen_y))
    return tuple(output)


def scene_layers(
        proxy: WzImage,
        materializer: arc.CanvasMaterializer,
        scene: LucidSceneSpec,
) -> tuple[TimelineLayer, ...]:
    sequence = lambda path, delay=60: load_sequence(proxy, materializer, path, delay)
    if scene.key.startswith("dragon-"):
        phase = "phase1" if scene.key.endswith("p1") else "phase2"
        dragon_offset = (DRAGON_RIGHT_OFFSETS[phase],)
        warning_pre = sequence(f"Dragon/{phase}/areaWarning/pre", 90)
        warning_start = sequence(f"Dragon/{phase}/areaWarning/start", 90)
        warning_loop = sequence(f"Dragon/{phase}/areaWarning/loop", 90)
        warning_end = sequence(f"Dragon/{phase}/areaWarning/end", 60)
        prepare = sequence(f"Dragon/{phase}/action/0", 180)
        attack = sequence(f"Dragon/{phase}/action/1", 150)
        end = prepare if phase == "phase1" else sequence("Dragon/phase2/action/2", 180)
        breath = sequence(f"Dragon/{phase}/breath", 90)
        shadow = joined(
            sequence("DragonShadow/action/0", 60),
            sequence("DragonShadow/action/1", 60),
            sequence("DragonShadow/action/2", 60),
        )
        return (
            TimelineLayer(
                shadow, 0, sequence_duration(shadow),
                motion=((-650, 110), (0, 80), (650, 110)),
            ),
            TimelineLayer(warning_pre, 0, sequence_duration(warning_pre)),
            TimelineLayer(
                warning_start,
                sequence_duration(warning_pre),
                sequence_duration(warning_pre) + sequence_duration(warning_start),
            ),
            TimelineLayer(warning_loop, 2790, 4650, True),
            TimelineLayer(prepare, 3000, 4800, offsets=dragon_offset),
            TimelineLayer(warning_end, 4650, 5490),
            TimelineLayer(attack, 4650, 10050, offsets=dragon_offset),
            TimelineLayer(breath, 4650, 6300, True, offsets=dragon_offset),
            TimelineLayer(end, 10050, scene.duration_ms, offsets=dragon_offset),
        )
    if scene.key == "laser-rain":
        action = sequence("LaserRain/action", 150)
        laser = sequence("LaserRain/laser", 60)
        return (
            TimelineLayer(action, 0, scene.duration_ms),
            TimelineLayer(laser, 1260, 3000, True),
        )
    if scene.key == "phantom-barrage":
        if len(PHANTOM_TRAJECTORIES) != PHANTOM_HIT_COUNT:
            raise RuntimeError("phantom trajectory count does not match damage contract")
        map_effect = sequence("Shoot/map", 120)
        ball = sequence("Shoot/ball", 60)
        hit = sequence("Shoot/hit", 60)
        pre_lucid = sequence("Shoot/info/action/pre/lucid", 60)
        pre_butterfly = sequence("Shoot/info/action/pre/butterfly", 60)
        loop_lucid = sequence("Shoot/info/action/loop/lucid", 60)
        loop_butterfly = sequence("Shoot/info/action/loop/butterfly", 60)
        end_lucid = sequence("Shoot/info/action/end/lucid", 60)
        end_butterfly = sequence("Shoot/info/action/end/butterfly", 60)
        projectile_layers = []
        hit_layers = []
        hit_duration = sequence_duration(hit)
        for index, motion in enumerate(PHANTOM_TRAJECTORIES):
            impact_ms = PHANTOM_PREPARE_MS + index * PHANTOM_HIT_INTERVAL_MS
            projectile_layers.append(TimelineLayer(
                ball,
                impact_ms - PHANTOM_PROJECTILE_TRAVEL_MS,
                impact_ms,
                True,
                motion=motion,
            ))
            hit_layers.append(TimelineLayer(
                hit,
                impact_ms,
                impact_ms + hit_duration,
                offsets=(motion[-1],),
            ))
        return (
            TimelineLayer(map_effect, 0, scene.duration_ms, True),
            TimelineLayer(pre_lucid, 0, 2400),
            TimelineLayer(pre_butterfly, 0, 2400, True, ((-160, 40), (160, -20))),
            TimelineLayer(loop_lucid, 2400, 14400, True),
            TimelineLayer(
                loop_butterfly, 2400, 14400, True,
                ((-300, -120), (-120, 80), (130, -60), (310, 90)),
            ),
            *projectile_layers,
            *hit_layers,
            TimelineLayer(end_lucid, 14400, scene.duration_ms),
            TimelineLayer(end_butterfly, 14400, scene.duration_ms, True),
        )
    if scene.key == "rush":
        action = joined(
            sequence("RushLucid/action/0", 70),
            sequence("RushLucid/action/1", 70),
            sequence("RushLucid/action/2", 70),
        )
        smoke = sequence("RushLucid/particle/smoke/0", 90)
        grain = sequence("RushLucid/particle/grain/0", 90)
        path = rush_screen_path()
        return (
            TimelineLayer(
                smoke, 0, scene.duration_ms, True,
                ((-180, 70), (120, -40)), path=path,
            ),
            TimelineLayer(
                grain, 0, scene.duration_ms, True,
                ((-240, 0), (220, 80)), path=path,
            ),
            TimelineLayer(action, 0, scene.duration_ms, path=path),
        )
    if scene.key == "fury":
        background = sequence("Fury/background", 120)
        fog = sequence("Fury/fog", 120)
        fail = sequence("Fury/fail", 120)
        return (
            TimelineLayer(background, 0, 45000, True),
            TimelineLayer(fog, 0, 45000, True),
            TimelineLayer(fail, 45000, scene.duration_ms),
        )
    if scene.key.startswith("stained-glass-"):
        glass_index = int(scene.key.rsplit("-", 1)[1])
        glass = sequence(f"StainedGlass/BreakEffect/{glass_index}", 90)
        return (TimelineLayer(glass, 0, scene.duration_ms),)
    fly = sequence("Butterfly/butterfly/0/fly", 90)
    bomb = sequence("Butterfly/butterfly/0/bomb", 90)
    if scene.key == "butterfly-burst":
        offsets = ((-420, -180), (-250, 110), (-80, -80), (110, 140), (280, -120), (430, 80))
        return (
            TimelineLayer(fly, 0, 450, True, offsets),
            TimelineLayer(bomb, 450, scene.duration_ms, False, offsets),
        )
    if scene.key == "bomb":
        return (
            TimelineLayer(fly, 0, 3000, True),
            TimelineLayer(bomb, 3000, scene.duration_ms),
        )
    raise RuntimeError(f"unsupported Lucid scene: {scene.key}")


def frame_at(layer: TimelineLayer, timestamp: int):
    if timestamp < layer.start_ms or timestamp >= layer.end_ms:
        return None
    elapsed = timestamp - layer.start_ms
    duration = sequence_duration(layer.frames)
    if layer.loop:
        elapsed %= duration
    elif elapsed >= duration:
        return None
    for proxy_frame, pixel_frame, delay in layer.frames:
        if elapsed < delay:
            return proxy_frame, pixel_frame
        elapsed -= delay
    return layer.frames[-1][:2]


def frame_origin(
        proxy_frame: WzCanvasProperty,
        pixel_frame: WzCanvasProperty,
) -> tuple[int, int]:
    for frame in (proxy_frame, pixel_frame):
        origin = frame.child("origin")
        if isinstance(origin, WzVectorProperty):
            return int(origin.x), int(origin.y)
    return int(pixel_frame.width) // 2, int(pixel_frame.height) // 2


def alpha_composite_clipped(
        base: Image.Image,
        layer: Image.Image,
        left: int,
        top: int,
) -> None:
    src_left = max(0, -left)
    src_top = max(0, -top)
    dst_left = max(0, left)
    dst_top = max(0, top)
    width = min(layer.width - src_left, base.width - dst_left)
    height = min(layer.height - src_top, base.height - dst_top)
    if width <= 0 or height <= 0:
        return
    cropped = layer.crop((src_left, src_top, src_left + width, src_top + height))
    base.alpha_composite(cropped, (dst_left, dst_top))
    cropped.close()


def render_scene_frame(
        layers: tuple[TimelineLayer, ...],
        timestamp: int,
        decoded_cache: dict[int, Image.Image],
) -> Image.Image:
    output = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    for layer in layers:
        current = frame_at(layer, timestamp)
        if current is None:
            continue
        proxy_frame, pixel_frame = current
        cache_key = id(pixel_frame)
        source = decoded_cache.get(cache_key)
        if source is None:
            source = arc.decode_source_canvas(pixel_frame).convert("RGBA")
            decoded_cache[cache_key] = source
        origin_x, origin_y = frame_origin(proxy_frame, pixel_frame)
        offsets = layer.offsets
        path_offset = (0, 0)
        if layer.motion is not None:
            duration = max(1, layer.end_ms - layer.start_ms)
            progress = min(1.0, max(0.0, (timestamp - layer.start_ms) / duration))
            remaining = 1.0 - progress
            start, control, end = layer.motion
            offset_x = round(
                remaining * remaining * start[0]
                + 2 * remaining * progress * control[0]
                + progress * progress * end[0]
            )
            offset_y = round(
                remaining * remaining * start[1]
                + 2 * remaining * progress * control[1]
                + progress * progress * end[1]
            )
            path_offset = (offset_x, offset_y)
        elif layer.path is not None:
            elapsed = timestamp - layer.start_ms
            start = layer.path[0]
            end = layer.path[-1]
            for candidate in layer.path[1:]:
                if elapsed <= candidate[0]:
                    end = candidate
                    break
                start = candidate
            span = max(1, end[0] - start[0])
            progress = min(1.0, max(0.0, (elapsed - start[0]) / span))
            path_offset = (
                round(start[1] + (end[1] - start[1]) * progress),
                round(start[2] + (end[2] - start[2]) * progress),
            )
        for offset_x, offset_y in offsets:
            alpha_composite_clipped(
                output,
                source,
                WIDTH // 2 + path_offset[0] + offset_x - origin_x,
                HEIGHT // 2 + path_offset[1] + offset_y - origin_y,
            )
    return output


def frame_delays(scene: LucidSceneSpec) -> list[int]:
    delays = [scene.step_ms] * (scene.duration_ms // scene.step_ms)
    remainder = scene.duration_ms % scene.step_ms
    if remainder:
        delays.append(remainder)
    return delays


def encode_scene(
        proxy: WzImage,
        scene: LucidSceneSpec,
        output_directory: Path,
) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required to export Lucid MCV files")
    materializer = arc.CanvasMaterializer()
    layers = scene_layers(proxy, materializer, scene)
    delays = frame_delays(scene)
    decoded_cache: dict[int, Image.Image] = {}
    visible_frames = 0
    visible_tail = False
    output_directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"lucid-{scene.key}-mcv-") as directory:
        temporary = Path(directory)
        color_path = temporary / "color.ivf"
        alpha_path = temporary / "alpha.ivf"
        color = subprocess.Popen(
            encoder_command(ffmpeg, "rgb24", 24, len(delays), color_path),
            stdin=subprocess.PIPE,
        )
        alpha = subprocess.Popen(
            encoder_command(ffmpeg, "gray", 16, len(delays), alpha_path),
            stdin=subprocess.PIPE,
        )
        try:
            if color.stdin is None or alpha.stdin is None:
                raise RuntimeError("failed to open FFmpeg input pipes")
            timestamp = 0
            for index, delay in enumerate(delays):
                rendered = render_scene_frame(layers, timestamp, decoded_cache)
                rgb = rendered.convert("RGB")
                alpha_channel = rendered.getchannel("A")
                if alpha_channel.getbbox() is not None:
                    visible_frames += 1
                    if timestamp >= scene.duration_ms - 1000:
                        visible_tail = True
                color.stdin.write(rgb.tobytes())
                alpha.stdin.write(alpha_channel.tobytes())
                rgb.close()
                alpha_channel.close()
                rendered.close()
                timestamp += delay
                if index == 0 or (index + 1) % 100 == 0 or index + 1 == len(delays):
                    print(f"encoded {scene.key}: {index + 1}/{len(delays)}", flush=True)
            color.stdin.close()
            alpha.stdin.close()
            if color.wait() != 0 or alpha.wait() != 0:
                raise RuntimeError(f"FFmpeg failed while encoding {scene.key}")
            if visible_frames == 0 or not visible_tail:
                raise RuntimeError(
                    f"{scene.key}: visible frame audit failed "
                    f"frames={visible_frames} visible_tail={visible_tail}"
                )
        except BaseException:
            for process in (color, alpha):
                if process.stdin is not None and not process.stdin.closed:
                    process.stdin.close()
                if process.poll() is None:
                    process.terminate()
                    process.wait()
            raise
        finally:
            for decoded in decoded_cache.values():
                decoded.close()

        color_fourcc, color_packets = read_ivf(color_path)
        alpha_fourcc, alpha_packets = read_ivf(alpha_path)
        if color_fourcc != alpha_fourcc:
            raise RuntimeError(f"{scene.key}: color/alpha codecs do not match")
        output = output_directory / scene.output_name
        write_mcv(output, color_fourcc, color_packets, alpha_packets, delays)
    print(
        f"wrote: {output} frames={len(delays)} "
        f"duration_ms={sum(delays)} bytes={output.stat().st_size}"
    )
    return output


def marker_pixels(marker_code: int) -> list[tuple[int, int, int, int]]:
    if marker_code < 1 or marker_code > 14:
        raise RuntimeError(f"invalid Lucid marker code: {marker_code}")
    return [
        (17, 34, 68, 255),
        (85, 102, 119, 255),
        (136, 153, 170, 255),
        (187, 204, 238, 255),
        (marker_code * 17, 68, 221, 255),
    ] + [(0, 0, 0, 0)] * (MARKER_WIDTH * MARKER_HEIGHT - 5)


def build_marker(
        parent: WzSubProperty,
        scene: LucidSceneSpec,
        key: WzKey,
) -> WzSubProperty:
    effect = WzSubProperty(scene.marker_name, parent)
    image = Image.new("RGBA", (MARKER_WIDTH, MARKER_HEIGHT), (0, 0, 0, 0))
    image.putdata(marker_pixels(scene.marker_code))
    frame = WzCanvasProperty("0", effect)
    frame.width = MARKER_WIDTH
    frame.height = MARKER_HEIGHT
    frame.format = 1
    frame.format2 = 0
    frame._png_data = encode_canvas_payload(
        image, 1, MARKER_WIDTH, MARKER_HEIGHT,
        key=key, listwz=False, zlib_level=9,
    )
    frame._png_length = len(frame._png_data)
    frame._png_offset = 0
    frame.add(WzVectorProperty("origin", MARKER_WIDTH // 2, MARKER_HEIGHT // 2, frame))
    frame.add(WzIntProperty("delay", MARKER_DURATION_MS, frame))
    frame.add(WzIntProperty("z", 0, frame))
    effect.add(frame)
    image.close()
    return effect


def patch_lucid_record(image: WzImage, original: bytes, parent: WzSubProperty) -> bytes:
    replacement = karing.encode_property_record(parent, image)
    (size_offsets, count_offset, count_end,
     names, spans, records_end) = karing.locate_nested_property_records(
        image, original, ("customSkill",)
    )
    original_records = {
        name: original[start:end]
        for name, (start, end) in zip(names, spans)
    }
    if "lucid" in original_records:
        index = names.index("lucid")
        record_start, record_end = spans[index]
        updated = bytearray(original[:record_start] + replacement + original[record_end:])
        count_delta = 0
    else:
        updated = bytearray(original[:records_end] + replacement + original[records_end:])
        count_delta = 1
    size_delta = len(updated) - len(original)
    if count_delta:
        new_count = karing.encode_compressed_int(len(names) + count_delta)
        if len(new_count) != count_end - count_offset:
            raise RuntimeError("customSkill child-count encoding size changed")
        updated[count_offset:count_end] = new_count
    for size_offset in size_offsets:
        old_size = struct.unpack_from("<I", original, size_offset)[0]
        struct.pack_into("<I", updated, size_offset, old_size + size_delta)

    result = bytes(updated)
    verified = WzImage.from_bytes(
        result, key=WzKey.for_region("GMS"), name=CLIENT_MAP_EFFECT.name
    )
    verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise RuntimeError(f"incremental Effect.img patch is malformed: {verified.parse_warnings}")
    (_, _, _, verified_names,
     verified_spans, _) = karing.locate_nested_property_records(
        verified, result, ("customSkill",)
    )
    verified_records = {
        name: result[start:end]
        for name, (start, end) in zip(verified_names, verified_spans)
    }
    for name, record in original_records.items():
        if name != "lucid" and verified_records.get(name) != record:
            raise RuntimeError(f"unchanged customSkill record changed: {name}")
    return result


def marker_matches(image: WzImage, scene: LucidSceneSpec) -> bool:
    frame = image.root.get(f"{FIELD_EFFECT_ROOT}/{scene.marker_name}/0")
    if not isinstance(frame, WzCanvasProperty):
        return False
    if (int(frame.width), int(frame.height)) != (MARKER_WIDTH, MARKER_HEIGHT):
        return False
    if (int(frame.format), int(frame.format2)) != (1, 0):
        return False
    decoded = decode_canvas(frame, region="GMS").convert("RGBA")
    matches = list(decoded.getdata())[:5] == marker_pixels(scene.marker_code)[:5]
    decoded.close()
    return matches


def install_markers(selected: tuple[LucidSceneSpec, ...]) -> None:
    original = CLIENT_MAP_EFFECT.read_bytes()
    image = WzImage.from_bytes(
        original, key=WzKey.for_region("GMS"), name=CLIENT_MAP_EFFECT.name
    )
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"{CLIENT_MAP_EFFECT}: truncated={image.truncated} "
            f"warnings={image.parse_warnings}"
        )
    if all(marker_matches(image, scene) for scene in selected):
        return
    parent = karing.ensure_path(root, FIELD_EFFECT_ROOT)
    for scene in selected:
        karing.replace_child(parent, build_marker(parent, scene, image.wz_file.reader.key))
    updated = patch_lucid_record(image, original, parent)
    if updated != original:
        arc.atomic_write_bytes(CLIENT_MAP_EFFECT, updated)


def verify_markers(selected: tuple[LucidSceneSpec, ...]) -> None:
    image = arc.load_image(CLIENT_MAP_EFFECT, arc.GMS_KEY)
    if image.truncated or image.parse_warnings:
        raise RuntimeError("Effect.img did not parse cleanly")
    for scene in selected:
        frame = image.root.get(f"{FIELD_EFFECT_ROOT}/{scene.marker_name}/0")
        if not isinstance(frame, WzCanvasProperty):
            raise RuntimeError(f"missing Lucid marker: {scene.marker_name}")
        if (int(frame.width), int(frame.height)) != (MARKER_WIDTH, MARKER_HEIGHT):
            raise RuntimeError(f"invalid Lucid marker size: {scene.marker_name}")
        if (int(frame.format), int(frame.format2)) != (1, 0):
            raise RuntimeError(f"invalid Lucid marker format: {scene.marker_name}")
        decoded = decode_canvas(frame, region="GMS").convert("RGBA")
        if list(decoded.getdata())[:5] != marker_pixels(scene.marker_code)[:5]:
            raise RuntimeError(f"Lucid marker signature mismatch: {scene.marker_name}")
        decoded.close()


def selected_scenes(key: str) -> tuple[LucidSceneSpec, ...]:
    if key == "all":
        return SCENES
    return tuple(scene for scene in SCENES if scene.key == key)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--scene", choices=("all", *(scene.key for scene in SCENES)), default="all")
    parser.add_argument("--markers-only", action="store_true")
    parser.add_argument("--videos-only", action="store_true")
    args = parser.parse_args()
    if args.markers_only and args.videos_only:
        parser.error("--markers-only and --videos-only are mutually exclusive")
    selected = selected_scenes(args.scene)
    if not args.markers_only:
        proxy, _ = load_images()
        for scene in selected:
            encode_scene(proxy, scene, args.output_directory)
    if not args.videos_only:
        install_markers(selected)
        verify_markers(selected)
    print(f"Lucid MCV export ok: scenes={len(selected)} marker_root={FIELD_EFFECT_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
