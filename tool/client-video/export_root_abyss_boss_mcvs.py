#!/usr/bin/env python3
"""Export Root Abyss ultimate attacks as FIELD_EFFECT MCV scenes."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
VIDEO_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/resource-workbench"))
sys.path.insert(0, str(VIDEO_DIR))

from export_karing_boss_mcvs import (  # noqa: E402
    CLIENT_MAP_EFFECT,
    HEIGHT,
    MARKER_HEIGHT,
    MARKER_WIDTH,
    WIDTH,
    alpha_composite_clipped,
    build_marker,
    frame_delay,
    frame_origin,
    numeric_canvases,
)
from export_soul_eclipse_mcv import encoder_command, read_ivf, write_mcv  # noqa: E402
from map_mob import app  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzKey, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402

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
    canvas_source: Path | None = None
    repeat_duration_ms: int | None = None


SCENES = (
    SceneSpec(
        "vellum-attack10",
        Path("/Users/lizixian/Documents/mxd/TMS/ms-extract/Mob_00000/Mob_8930000.img"),
        "BMS",
        "attack10/info/screen",
        "root-abyss-vellum-attack10.mcv",
        "vellumAttack10VideoLayer",
        5,
        canvas_source=TMS_DATA / "Mob/_Canvas/8930000.img",
        repeat_duration_ms=5000,
    ),
    SceneSpec(
        "vellum-attack11",
        Path("/Users/lizixian/Documents/mxd/TMS/ms-extract/Mob_00000/Mob_8930000.img"),
        "BMS",
        "attack11/info/screen",
        "root-abyss-vellum-attack11.mcv",
        "vellumAttack11VideoLayer",
        6,
        canvas_source=TMS_DATA / "Mob/_Canvas/8930000.img",
    ),
)


def marker_pixels(marker_code: int) -> list[tuple[int, int, int, int]]:
    if marker_code < 1 or marker_code > 6:
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
    proxy_frames = numeric_canvases(node)
    if not proxy_frames:
        raise RuntimeError(f"no frames in {spec.source.name}/{spec.node}")
    canvas_frames: dict[str, WzCanvasProperty] = {}
    if spec.canvas_source is not None:
        canvas_image = load_image(spec.canvas_source, spec.region)
        canvas_node = canvas_image.root.get(spec.node)
        if not isinstance(canvas_node, WzSubProperty):
            raise RuntimeError(f"missing {spec.canvas_source.name}/{spec.node}")
        canvas_frames = {frame.name: frame for frame in numeric_canvases(canvas_node)}
    rendered = []
    delays = []
    for proxy_frame in proxy_frames:
        canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        pixel_frame = canvas_frames.get(proxy_frame.name, proxy_frame)
        should_decode = spec.canvas_source is None or (
            pixel_frame.has_pixels()
            and (pixel_frame.width > 1 or pixel_frame.height > 1)
        )
        if should_decode:
            source = decode_canvas(pixel_frame, region=spec.region).convert("RGBA")
            origin_x, origin_y = frame_origin(proxy_frame)
            left = WIDTH // 2 - origin_x
            top = HEIGHT // 2 - origin_y
            alpha_composite_clipped(canvas, source, left, top)
            source.close()
        rendered.append(canvas)
        delays.append(frame_delay(proxy_frame))
    if spec.repeat_duration_ms is not None:
        cycle_frames = rendered
        cycle_delays = delays
        rendered = []
        delays = []
        elapsed = 0
        index = 0
        while elapsed < spec.repeat_duration_ms:
            delay = min(cycle_delays[index], spec.repeat_duration_ms - elapsed)
            rendered.append(cycle_frames[index].copy())
            delays.append(delay)
            elapsed += delay
            index = (index + 1) % len(cycle_frames)
        for frame in cycle_frames:
            frame.close()
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


def validate_marker(marker: WzSubProperty, spec: SceneSpec) -> None:
    frame = marker.child("0")
    if not isinstance(frame, WzCanvasProperty):
        raise RuntimeError(f"invalid existing marker: {FIELD_EFFECT_ROOT}/{spec.marker_name}/0")
    if (frame.width, frame.height, frame.format, frame.format2) != (
        MARKER_WIDTH, MARKER_HEIGHT, 1, 0
    ):
        raise RuntimeError(f"incompatible existing marker: {FIELD_EFFECT_ROOT}/{spec.marker_name}")
    decoded = decode_canvas(frame, region="GMS").convert("RGBA")
    try:
        actual = list(decoded.getdata())
    finally:
        decoded.close()
    if actual != marker_pixels(spec.marker_code):
        raise RuntimeError(f"marker signature mismatch: {FIELD_EFFECT_ROOT}/{spec.marker_name}")


def install_markers(selected: tuple[SceneSpec, ...], dry_run: bool) -> None:
    if not selected:
        return
    original = CLIENT_MAP_EFFECT.read_bytes()
    updated = original
    import export_karing_boss_mcvs as karing
    original_pixels = karing.marker_pixels
    karing.marker_pixels = marker_pixels
    try:
        for spec in selected:
            image = WzImage.from_bytes(
                updated, key=WzKey.for_region("GMS"), name=CLIENT_MAP_EFFECT.name
            )
            image.parse()
            if image.truncated or image.parse_warnings:
                raise RuntimeError(
                    f"{CLIENT_MAP_EFFECT}: truncated={image.truncated} "
                    f"warnings={image.parse_warnings}"
                )
            parent = image.root.get(FIELD_EFFECT_ROOT)
            if not isinstance(parent, WzSubProperty):
                raise RuntimeError(f"missing Effect.img path: {FIELD_EFFECT_ROOT}")
            existing = parent.child(spec.marker_name)
            if existing is not None:
                if not isinstance(existing, WzSubProperty):
                    raise RuntimeError(
                        f"invalid existing marker: {FIELD_EFFECT_ROOT}/{spec.marker_name}"
                    )
                validate_marker(existing, spec)
                continue
            marker = build_marker(parent, spec, image.wz_file.reader.key)
            updated = app.arc.append_property_record(
                updated, tuple(FIELD_EFFECT_ROOT.split("/")), marker
            )
            print(f"field effect marker: {FIELD_EFFECT_ROOT}/{spec.marker_name}")
    finally:
        karing.marker_pixels = original_pixels
    approved = {
        (*FIELD_EFFECT_ROOT.split("/"), spec.marker_name)
        for spec in selected
    }
    app.arc.verify_raw_record_insert_scope(original, updated, approved)
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
