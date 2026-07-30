#!/usr/bin/env python3
"""Encode Night Walker VI origin screen layers as transparent MCV videos."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

from export_blaze_wizard_mcvs import (
    HEIGHT,
    WIDTH,
    EffectSpec,
    encode_effect,
    encoder_command,
    read_ivf,
    write_mcv,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-MS-Export/NightWalker")
DEFAULT_OUTPUT_DIRECTORY = ROOT / "clien" / "Data" / "Video"
PATCH_SKILL = ROOT / "tool" / "scripts" / "patch-skill"
sys.path.insert(0, str(PATCH_SKILL))

import patch_night_walker_v_vi as night_walker  # noqa: E402

DOMINION_KEY = "dominion"
EFFECTS = (
    EffectSpec("silent-night", 14141500, (("screen", "video"),), "silent-night.mcv"),
    EffectSpec(
        "stygian-command",
        14141503,
        (("screen", "video"), ("screen2", "video")),
        "stygian-command.mcv",
    ),
)


def aligned_timeline(tracks):
    indexes = [0] * len(tracks)
    remaining = [
        night_walker.engine.base.frame_delay(canvas, meta)
        for canvas, meta in (track[0] for track in tracks)
    ]
    result = []
    while any(index < len(track) for index, track in zip(indexes, tracks)):
        active = [
            track[index] if index < len(track) else None
            for index, track in zip(indexes, tracks)
        ]
        delay = min(value for value, item in zip(remaining, active) if item is not None)
        result.append((active, delay))
        for track_index, item in enumerate(active):
            if item is None:
                continue
            remaining[track_index] -= delay
            if remaining[track_index] == 0:
                indexes[track_index] += 1
                if indexes[track_index] < len(tracks[track_index]):
                    canvas, meta = tracks[track_index][indexes[track_index]]
                    remaining[track_index] = night_walker.engine.base.frame_delay(canvas, meta)
    return result


def render_canvas_layers(active) -> Image.Image:
    rendered = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    for item in active:
        if item is None:
            continue
        canvas, meta = item
        layer = night_walker.engine.base.clean_rgba(
            night_walker.engine.base.decode_source_canvas(canvas)
        )
        origin_x, origin_y = night_walker.engine.base.canvas_origin(canvas, meta)
        rendered.alpha_composite(layer, (WIDTH // 2 - origin_x, HEIGHT // 2 - origin_y))
        layer.close()
    return rendered


def encode_dominion(output_directory: Path) -> Path:
    night_walker.configure_engine()
    groups, _, metadata = night_walker.engine.load_sources()
    tracks = [
        night_walker.engine.tracks(groups, metadata, 14141018, node_name)[0]
        for node_name in ("screen", "screen2")
    ]
    timeline = aligned_timeline(tracks)
    delays = [delay for _, delay in timeline]
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required to export MCV files")
    with tempfile.TemporaryDirectory(prefix="dominion-mcv-") as directory:
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
            for index, (active, _) in enumerate(timeline):
                rendered = render_canvas_layers(active)
                rgb = rendered.convert("RGB")
                alpha_channel = rendered.getchannel("A")
                color.stdin.write(rgb.tobytes())
                alpha.stdin.write(alpha_channel.tobytes())
                rgb.close()
                alpha_channel.close()
                rendered.close()
                if index == 0 or (index + 1) % 20 == 0 or index + 1 == len(timeline):
                    print(f"encoded dominion: {index + 1}/{len(timeline)}", flush=True)
            color.stdin.close()
            alpha.stdin.close()
            if color.wait() != 0 or alpha.wait() != 0:
                raise RuntimeError("FFmpeg failed while encoding dominion")
        except BaseException:
            for process in (color, alpha):
                if process.stdin is not None and not process.stdin.closed:
                    process.stdin.close()
                if process.poll() is None:
                    process.terminate()
                    process.wait()
            raise
        color_fourcc, color_packets = read_ivf(color_path)
        alpha_fourcc, alpha_packets = read_ivf(alpha_path)
        if color_fourcc != alpha_fourcc:
            raise RuntimeError("color and alpha codecs do not match")
        output = output_directory / "dominion.mcv"
        write_mcv(output, color_fourcc, color_packets, alpha_packets, delays)
    print(f"wrote: {output} frames={len(delays)} duration_ms={sum(delays)} bytes={output.stat().st_size}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument(
        "--effect",
        choices=("all", DOMINION_KEY, *(spec.key for spec in EFFECTS)),
        default="all",
    )
    args = parser.parse_args()
    if args.effect in {"all", DOMINION_KEY}:
        encode_dominion(args.output_directory)
    selected = EFFECTS if args.effect == "all" else tuple(
        spec for spec in EFFECTS if spec.key == args.effect
    )
    args.output_directory.mkdir(parents=True, exist_ok=True)
    for spec in selected:
        encode_effect(spec, args.source, args.output_directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
