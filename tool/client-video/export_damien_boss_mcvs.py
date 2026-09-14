#!/usr/bin/env python3
"""Export Damien huge scene/ground frames as FIELD_EFFECT MCV clips."""

from __future__ import annotations

import argparse
import hashlib
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
sys.path.insert(0, str(VIDEO_DIR))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

from export_karing_boss_mcvs import (  # noqa: E402
    CLIENT_MAP_EFFECT,
    HEIGHT,
    MARKER_HEIGHT,
    MARKER_WIDTH,
    WIDTH,
    KaringSceneSpec,
    alpha_composite_clipped,
    build_marker,
    frame_delay,
    frame_origin,
    numeric_canvases,
)
from export_soul_eclipse_mcv import encoder_command, read_ivf, write_mcv  # noqa: E402
import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzKey, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.incremental_img import replace_img_record  # noqa: E402

DEFAULT_OUTPUT_DIRECTORY = ROOT / "clien/Data/Video"
P1_MOB = ROOT / "clien/Data/Mob/8880110.img"
P2_MOB = ROOT / "clien/Data/Mob/8880111.img"


@dataclass(frozen=True)
class SceneSpec:
    key: str
    mob_id: int
    source: Path
    node: str
    output_name: str
    marker_name: str
    marker_code: int
    skip_tiny: bool = False


SCENES = (
    SceneSpec(
        "scene",
        8880111,
        P2_MOB,
        "skillAfter3",
        "damien-scene.mcv",
        "scene",
        1,
    ),
    SceneSpec(
        "ground",
        8880110,
        P1_MOB,
        "attack1/info/areaWarning",
        "damien-ground.mcv",
        "groundBurst",
        2,
        skip_tiny=True,
    ),
)


def marker_pixels(marker_code: int) -> list[tuple[int, int, int, int]]:
    if marker_code < 1 or marker_code > 2:
        raise RuntimeError(f"invalid Damien marker code: {marker_code}")
    return [
        (17, 68, 102, 255),
        (85, 119, 136, 255),
        (136, 153, 187, 255),
        (187, 221, 238, 255),
        (marker_code * 17, 153, 221, 255),
    ] + [(0, 0, 0, 0)] * (MARKER_WIDTH * MARKER_HEIGHT - 5)


def load_image(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{path}: truncated={image.truncated} warnings={image.parse_warnings}")
    return image


def selected_frames(node: WzSubProperty, spec: SceneSpec) -> list[WzCanvasProperty]:
    frames = numeric_canvases(node)
    if spec.skip_tiny:
        frames = [frame for frame in frames if frame.width > 1 and frame.height > 1]
    if not frames:
        raise RuntimeError(f"no frames in {spec.source.name}/{spec.node}")
    return frames


def render_frames(spec: SceneSpec) -> tuple[list[Image.Image], list[int]]:
    image = load_image(spec.source)
    node = image.root.get(spec.node)
    if not isinstance(node, WzSubProperty):
        source_path = arc.extract_mob(spec.mob_id)
        source_image = arc.load_image(source_path, arc.BMS_KEY)
        source_node = source_image.root.get(spec.node)
        if not isinstance(source_node, WzSubProperty):
            raise RuntimeError(f"missing TMS {spec.mob_id}/{spec.node}")
        node = arc.clone_property(
            source_node,
            None,
            source_image,
            source_path,
            arc.CanvasMaterializer(),
        )
    frames = selected_frames(node, spec)
    rendered = []
    delays = []
    visible = 0
    for frame in frames:
        source = decode_canvas(frame, region="GMS").convert("RGBA")
        origin_x, origin_y = frame_origin(frame)
        left = WIDTH // 2 - origin_x
        top = HEIGHT // 2 - origin_y
        canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        alpha_composite_clipped(canvas, source, left, top)
        if canvas.getchannel("A").getbbox() is not None:
            visible += 1
        source.close()
        rendered.append(canvas)
        delays.append(frame_delay(frame))
    if visible == 0:
        raise RuntimeError(f"{spec.key} rendered no visible pixels")
    last = rendered[-1].getchannel("A")
    if last.getbbox() is None:
        last.close()
        raise RuntimeError(f"{spec.key} missing visible tail")
    last.close()
    return rendered, delays


def encode_scene(spec: SceneSpec, output_directory: Path) -> Path:
    frames, delays = render_frames(spec)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required to export Damien MCV files")
    output = output_directory / spec.output_name
    with tempfile.TemporaryDirectory(prefix=f"damien-{spec.key}-mcv-") as directory:
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


def build_effect_node(image: WzImage) -> WzSubProperty:
    parent = WzSubProperty("customBossDemian")
    key = image.wz_file.reader.key
    import export_karing_boss_mcvs as karing

    original_pixels = karing.marker_pixels
    karing.marker_pixels = marker_pixels
    try:
        for spec in SCENES:
            karing_spec = KaringSceneSpec(
                spec.key,
                spec.node,
                spec.output_name,
                spec.marker_name,
                spec.marker_code,
            )
            parent.add(build_marker(parent, karing_spec, key))
    finally:
        karing.marker_pixels = original_pixels
    return parent


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_demian_effect_scope(before: bytes, after: bytes) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)
    approved = ("customBossDemian",)
    if before_orders.get(()) != after_orders.get(()):
        raise RuntimeError("Effect.img top-level sibling order changed")
    for path, raw in before_records.items():
        under_demian = path[: len(approved)] == approved
        if not under_demian and after_records.get(path) != raw:
            raise RuntimeError(f"protected record changed: {path}")
    for path in after_records:
        under_demian = path[: len(approved)] == approved
        if not under_demian and path not in before_records:
            raise RuntimeError(f"unapproved record added: {path}")
    if ("customBossDemian", "scene") not in after_records:
        raise RuntimeError("missing customBossDemian/scene after marker replace")
    if ("customBossDemian", "groundBurst") not in after_records:
        raise RuntimeError("missing customBossDemian/groundBurst after marker replace")


def install_markers(dry_run: bool) -> bytes:
    original = CLIENT_MAP_EFFECT.read_bytes()
    image = WzImage.from_bytes(original, key=WzKey.for_region("GMS"), name=CLIENT_MAP_EFFECT.name)
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{CLIENT_MAP_EFFECT}: truncated={image.truncated}")
    if not isinstance(root.child("customBossDemian"), WzSubProperty):
        raise RuntimeError("Effect.img missing customBossDemian; insert it before replacing with markers")
    node = build_effect_node(image)
    updated = replace_img_record(original, (node.name,), node, region="GMS").data
    verify_demian_effect_scope(original, updated)
    checked = WzImage.from_bytes(updated, key=WzKey.for_region("GMS"), name=CLIENT_MAP_EFFECT.name)
    checked.parse()
    if checked.truncated or checked.parse_warnings:
        raise RuntimeError(f"incremental Effect.img patch is malformed: {checked.parse_warnings}")
    parent = checked.root.child("customBossDemian")
    for spec in SCENES:
        child = parent.child(spec.marker_name)
        if not isinstance(child, WzSubProperty):
            raise RuntimeError(f"missing marker {spec.marker_name}")
        canvas = child.child("0")
        if not isinstance(canvas, WzCanvasProperty):
            raise RuntimeError(f"{spec.marker_name} missing canvas 0")
        if (canvas.width, canvas.height, int(canvas.format), int(canvas.format2)) != (
            MARKER_WIDTH,
            MARKER_HEIGHT,
            1,
            0,
        ):
            raise RuntimeError(f"{spec.marker_name} is not a 7x5 ARGB4444 marker")
        decoded = decode_canvas(canvas, region="GMS").convert("RGBA")
        pixels = list(decoded.getdata())[:5]
        decoded.close()
        if pixels != marker_pixels(spec.marker_code)[:5]:
            raise RuntimeError(f"{spec.marker_name} marker pixels mismatch: {pixels}")
    if dry_run:
        return updated
    temporary = CLIENT_MAP_EFFECT.with_name(f".{CLIENT_MAP_EFFECT.name}.damien.tmp")
    temporary.write_bytes(updated)
    temporary.replace(CLIENT_MAP_EFFECT)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--effect", choices=("all", *(spec.key for spec in SCENES)), default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--markers-only", action="store_true")
    args = parser.parse_args()
    selected = SCENES if args.effect == "all" else tuple(spec for spec in SCENES if spec.key == args.effect)
    args.output_directory.mkdir(parents=True, exist_ok=True)
    if not args.dry_run and not args.markers_only:
        for spec in selected:
            encode_scene(spec, args.output_directory)
    first = install_markers(args.dry_run)
    second = install_markers(args.dry_run)
    if sha256_bytes(first) != sha256_bytes(second):
        raise RuntimeError("Damien Effect.img marker install is not idempotent")
    if not args.dry_run:
        on_disk = CLIENT_MAP_EFFECT.read_bytes()
        if sha256_bytes(on_disk) != sha256_bytes(first):
            raise RuntimeError("Damien Effect.img on-disk hash drifted after second install")
    print(f"damien MCV markers ok sha256={sha256_bytes(first)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
