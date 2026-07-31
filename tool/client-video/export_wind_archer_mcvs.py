#!/usr/bin/env python3
"""Encode Wind Archer V/VI full-screen effects as transparent MCV videos."""

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
DEFAULT_SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-MS-Export/WindArcher")
DEFAULT_OUTPUT_DIRECTORY = ROOT / "clien" / "Data" / "Video"
PATCH_SKILL = ROOT / "tool" / "scripts" / "patch-skill"
sys.path.insert(0, str(PATCH_SKILL))

import patch_wind_archer_v_vi as wind_archer  # noqa: E402


MONSOON_KEY = "monsoon-vi"
EFFECTS = (
    EffectSpec(
        "mistral-spring",
        13141500,
        (("screen", "video"),),
        "mistral-spring.mcv",
        cover_field=True,
    ),
    EffectSpec(
        "elemental-tempest",
        13141506,
        (("screen", "video"), ("screen2", "video")),
        "elemental-tempest.mcv",
    ),
)


def render_canvas(canvas, meta) -> Image.Image:
    rendered = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    layer = wind_archer.engine.base.clean_rgba(
        wind_archer.engine.base.decode_source_canvas(canvas)
    )
    origin_x, origin_y = wind_archer.engine.base.canvas_origin(canvas, meta)
    rendered.alpha_composite(layer, (WIDTH // 2 - origin_x, HEIGHT // 2 - origin_y))
    layer.close()
    return rendered


def encode_monsoon(output_directory: Path) -> Path:
    wind_archer.configure_engine()
    groups, _, metadata = wind_archer.engine.load_sources()
    tracks = wind_archer.engine.tracks(groups, metadata, 13141005, "screen")
    if len(tracks) != 1 or not tracks[0]:
        raise RuntimeError("unexpected Monsoon VI screen track")
    track = tracks[0]
    delays = [wind_archer.engine.base.frame_delay(canvas, meta) for canvas, meta in track]
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required to export MCV files")
    output_directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="monsoon-vi-mcv-") as directory:
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
            for index, (canvas, meta) in enumerate(track):
                rendered = render_canvas(canvas, meta)
                rgb = rendered.convert("RGB")
                alpha_channel = rendered.getchannel("A")
                color.stdin.write(rgb.tobytes())
                alpha.stdin.write(alpha_channel.tobytes())
                rgb.close()
                alpha_channel.close()
                rendered.close()
                if index == 0 or (index + 1) % 20 == 0 or index + 1 == len(track):
                    print(f"encoded monsoon-vi: {index + 1}/{len(track)}", flush=True)
            color.stdin.close()
            alpha.stdin.close()
            if color.wait() != 0 or alpha.wait() != 0:
                raise RuntimeError("FFmpeg failed while encoding Monsoon VI")
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
        output = output_directory / "monsoon-vi.mcv"
        write_mcv(output, color_fourcc, color_packets, alpha_packets, delays)
    print(f"wrote: {output} frames={len(delays)} duration_ms={sum(delays)} bytes={output.stat().st_size}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument(
        "--effect",
        choices=("all", MONSOON_KEY, *(spec.key for spec in EFFECTS)),
        default="all",
    )
    args = parser.parse_args()
    if args.effect in {"all", MONSOON_KEY}:
        encode_monsoon(args.output_directory)
    selected = EFFECTS if args.effect == "all" else tuple(
        spec for spec in EFFECTS if spec.key == args.effect
    )
    args.output_directory.mkdir(parents=True, exist_ok=True)
    for spec in selected:
        encode_effect(spec, args.source, args.output_directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
