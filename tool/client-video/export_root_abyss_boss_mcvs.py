#!/usr/bin/env python3
"""Export Root Abyss ultimate attacks as FIELD_EFFECT MCV scenes."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import struct
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
VIDEO_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(VIDEO_DIR))

from export_karing_boss_mcvs import (  # noqa: E402
    CLIENT_MAP_EFFECT,
    HEIGHT,
    MARKER_HEIGHT,
    MARKER_WIDTH,
    WIDTH,
    alpha_composite_clipped,
    build_marker,
    encode_property_record,
    ensure_path,
    frame_delay,
    frame_origin,
    locate_nested_property_records,
    numeric_canvases,
    replace_child,
)
from export_soul_eclipse_mcv import encoder_command, read_ivf, write_mcv  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzKey, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.writer import encode_compressed_int  # noqa: E402

TMS_DATA = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
DEFAULT_OUTPUT_DIRECTORY = ROOT / "clien/Data/Video"
FIELD_EFFECT_ROOT = "customSkill/rootAbyss"


@dataclass(frozen=True)
class SceneSpec:
    key: str
    source: Path
    region: str
    node: str
    output_name: str
    marker_name: str
    marker_code: int


SCENES = (
    SceneSpec(
        "pierre",
        ROOT / "clien/Data/Mob/8900000.img",
        "GMS",
        "attack2",
        "root-abyss-pierre.mcv",
        "pierreVideoLayer",
        1,
    ),
    SceneSpec(
        "vonbon",
        TMS_DATA / "Mob/_Canvas/8910000.img",
        "BMS",
        "skill2",
        "root-abyss-vonbon.mcv",
        "vonBonVideoLayer",
        2,
    ),
    SceneSpec(
        "queen",
        ROOT / "clien/Data/Mob/8920000.img",
        "GMS",
        "attack2",
        "root-abyss-queen.mcv",
        "queenVideoLayer",
        3,
    ),
    SceneSpec(
        "vellum",
        TMS_DATA / "Mob/_Canvas/8930000.img",
        "BMS",
        "attack3",
        "root-abyss-vellum.mcv",
        "vellumVideoLayer",
        4,
    ),
)


def marker_pixels(marker_code: int) -> list[tuple[int, int, int, int]]:
    if marker_code < 1 or marker_code > 4:
        raise RuntimeError(f"invalid Root Abyss marker code: {marker_code}")
    return [
        (51, 85, 119, 255),
        (102, 136, 153, 255),
        (170, 187, 204, 255),
        (221, 238, 255, 255),
        (marker_code * 17, 136, 238, 255),
    ] + [(0, 0, 0, 0)] * (MARKER_WIDTH * MARKER_HEIGHT - 5)


def load_image(path: Path, region: str) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region(region), name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{path}: truncated={image.truncated} warnings={image.parse_warnings}")
    return image


def render_frames(spec: SceneSpec) -> tuple[list[Image.Image], list[int]]:
    image = load_image(spec.source, spec.region)
    node = image.root.get(spec.node)
    if not isinstance(node, WzSubProperty):
        raise RuntimeError(f"missing {spec.source.name}/{spec.node}")
    frames = numeric_canvases(node)
    if not frames:
        raise RuntimeError(f"no frames in {spec.source.name}/{spec.node}")
    rendered = []
    delays = []
    for frame in frames:
        source = decode_canvas(frame, region=spec.region).convert("RGBA")
        origin_x, origin_y = frame_origin(frame)
        left = WIDTH // 2 - origin_x
        top = HEIGHT // 2 - origin_y
        canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        alpha_composite_clipped(canvas, source, left, top)
        source.close()
        rendered.append(canvas)
        delays.append(frame_delay(frame))
    return rendered, delays


def encode_scene(spec: SceneSpec, output_directory: Path) -> Path:
    frames, delays = render_frames(spec)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required to export Root Abyss MCV files")
    output = output_directory / spec.output_name
    with tempfile.TemporaryDirectory(prefix=f"root-abyss-{spec.key}-mcv-") as directory:
        temporary = Path(directory)
        color_path = temporary / "color.ivf"
        alpha_path = temporary / "alpha.ivf"
        color = subprocess.Popen(
            encoder_command(ffmpeg, "rgb24", 24, len(frames), color_path),
            stdin=subprocess.PIPE,
        )
        alpha = subprocess.Popen(
            encoder_command(ffmpeg, "gray", 16, len(frames), alpha_path),
            stdin=subprocess.PIPE,
        )
        try:
            if color.stdin is None or alpha.stdin is None:
                raise RuntimeError("failed to open FFmpeg input pipes")
            for index, frame in enumerate(frames):
                rgb = frame.convert("RGB")
                alpha_channel = frame.getchannel("A")
                color.stdin.write(rgb.tobytes())
                alpha.stdin.write(alpha_channel.tobytes())
                rgb.close()
                alpha_channel.close()
                frame.close()
                if index == 0 or (index + 1) % 10 == 0 or index + 1 == len(frames):
                    print(f"encoded {spec.key}: {index + 1}/{len(frames)}", flush=True)
            color.stdin.close()
            alpha.stdin.close()
        except Exception:
            color.kill()
            alpha.kill()
            raise
        if color.wait() != 0 or alpha.wait() != 0:
            raise RuntimeError(f"ffmpeg failed for {spec.key}")
        color_fourcc, color_packets = read_ivf(color_path)
        alpha_fourcc, alpha_packets = read_ivf(alpha_path)
        if color_fourcc != alpha_fourcc or len(color_packets) != len(alpha_packets) or len(color_packets) != len(delays):
            raise RuntimeError(f"MCV packet mismatch for {spec.key}")
        write_mcv(output, color_fourcc, color_packets, alpha_packets, delays)
    print(f"wrote {output} frames={len(delays)} bytes={output.stat().st_size}")
    return output


def patch_root_abyss_record(image: WzImage, original: bytes, parent: WzSubProperty) -> bytes:
    replacement = encode_property_record(parent, image)
    (size_offsets, count_offset, count_end,
     names, spans, records_end) = locate_nested_property_records(
        image, original, ("customSkill",)
    )
    original_records = {
        name: original[start:end]
        for name, (start, end) in zip(names, spans)
    }
    if "rootAbyss" in original_records:
        index = names.index("rootAbyss")
        record_start, record_end = spans[index]
        updated = bytearray(original[:record_start] + replacement + original[record_end:])
        count_delta = 0
    else:
        updated = bytearray(original[:records_end] + replacement + original[records_end:])
        count_delta = 1
    size_delta = len(updated) - len(original)
    if count_delta:
        new_count = encode_compressed_int(len(names) + count_delta)
        if len(new_count) != count_end - count_offset:
            raise RuntimeError("customSkill child-count encoding size changed")
        updated[count_offset:count_end] = new_count
    for size_offset in size_offsets:
        old_size = struct.unpack_from("<I", original, size_offset)[0]
        struct.pack_into("<I", updated, size_offset, old_size + size_delta)
    verified = WzImage.from_bytes(bytes(updated), key=WzKey.for_region("GMS"), name=CLIENT_MAP_EFFECT.name)
    verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise RuntimeError(f"incremental Effect.img patch is malformed: {verified.parse_warnings}")
    return bytes(updated)


def install_markers(selected: tuple[SceneSpec, ...], dry_run: bool) -> None:
    original = CLIENT_MAP_EFFECT.read_bytes()
    image = WzImage.from_bytes(original, key=WzKey.for_region("GMS"), name=CLIENT_MAP_EFFECT.name)
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{CLIENT_MAP_EFFECT}: truncated={image.truncated}")
    parent = ensure_path(root, FIELD_EFFECT_ROOT)
    key = image.wz_file.reader.key
    import export_karing_boss_mcvs as karing
    original_pixels = karing.marker_pixels
    karing.marker_pixels = marker_pixels
    try:
        for spec in selected:
            replace_child(parent, build_marker(parent, spec, key))
            print(f"field effect marker: {FIELD_EFFECT_ROOT}/{spec.marker_name}")
        updated = patch_root_abyss_record(image, original, parent)
    finally:
        karing.marker_pixels = original_pixels
    if dry_run:
        return
    temporary = CLIENT_MAP_EFFECT.with_name(f".{CLIENT_MAP_EFFECT.name}.rootabyss.tmp")
    temporary.write_bytes(updated)
    temporary.replace(CLIENT_MAP_EFFECT)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--effect", choices=("all", *(spec.key for spec in SCENES)), default="all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    selected = SCENES if args.effect == "all" else tuple(spec for spec in SCENES if spec.key == args.effect)
    args.output_directory.mkdir(parents=True, exist_ok=True)
    if not args.dry_run:
        for spec in selected:
            encode_scene(spec, args.output_directory)
    install_markers(selected, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
