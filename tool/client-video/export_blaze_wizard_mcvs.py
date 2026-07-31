#!/usr/bin/env python3
"""Encode Blaze Wizard VI screen videos as the same transparent MCV format used by Dawn Warrior."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from export_soul_eclipse_mcv import (  # noqa: E402
    HEIGHT,
    WIDTH,
    encoder_command,
    read_ivf,
    write_mcv,
)


DEFAULT_SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-MS-Export/BlazeWizard")
DEFAULT_OUTPUT_DIRECTORY = ROOT / "clien" / "Data" / "Video"


@dataclass(frozen=True)
class EffectSpec:
    key: str
    skill_id: int
    video_paths: tuple[tuple[str, ...], ...]
    output_name: str
    cover_field: bool = False


EFFECTS = (
    EffectSpec("eternal-phoenix", 12141500, (("screen", "video"),), "eternal-phoenix.mcv"),
    EffectSpec(
        "flame-concerto",
        12141503,
        (("screen", "video"), ("screen2", "video")),
        "flame-concerto.mcv",
    ),
)


def child(node: ET.Element, name: str) -> ET.Element:
    result = next((item for item in node if item.attrib.get("name") == name), None)
    if result is None:
        raise RuntimeError(f"missing MS node {name}")
    return result


def video_node(root: ET.Element, path: tuple[str, ...]) -> ET.Element:
    node = root
    for name in path:
        node = child(node, name)
    if node.tag != "video":
        raise RuntimeError(f"MS node {'/'.join(path)} is not a video")
    return node


def frame_entries(video: ET.Element, source: Path) -> list[tuple[Path, int]]:
    result = []
    for frame in video:
        if frame.tag != "frame":
            continue
        result.append((source / frame.attrib["file"], max(1, int(frame.attrib["delay"]))))
    if not result:
        raise RuntimeError("video has no decoded frames")
    return result


def alpha_union_bounds(tracks: list[list[tuple[Path, int]]]) -> tuple[int, int, int, int]:
    bounds = None
    for track in tracks:
        for path, _ in track:
            with Image.open(path) as opened:
                frame_bounds = opened.convert("RGBA").getchannel("A").getbbox()
            if frame_bounds is None:
                continue
            bounds = frame_bounds if bounds is None else (
                min(bounds[0], frame_bounds[0]),
                min(bounds[1], frame_bounds[1]),
                max(bounds[2], frame_bounds[2]),
                max(bounds[3], frame_bounds[3]),
            )
    if bounds is None:
        raise RuntimeError("full-screen video has no visible pixels")
    return bounds


def contain_on_screen(
        path: Path,
        cover_bounds: tuple[int, int, int, int] | None = None,
) -> Image.Image:
    with Image.open(path) as opened:
        source = opened.convert("RGBA")
    if cover_bounds is not None:
        cropped = source.crop(cover_bounds)
        source.close()
        source = cropped
        scale = max(WIDTH / source.width, HEIGHT / source.height)
    else:
        scale = min(1.0, WIDTH / source.width, HEIGHT / source.height)
    width = max(1, round(source.width * scale))
    height = max(1, round(source.height * scale))
    if (width, height) != source.size:
        resized = source.resize((width, height), Image.Resampling.LANCZOS)
        source.close()
        source = resized
    if cover_bounds is not None:
        left = max(0, (width - WIDTH) // 2)
        top = max(0, (height - HEIGHT) // 2)
        result = source.crop((left, top, left + WIDTH, top + HEIGHT))
    else:
        result = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        result.alpha_composite(source, ((WIDTH - width) // 2, (HEIGHT - height) // 2))
    source.close()
    return result


def load_effect_frames(spec: EffectSpec, source: Path) -> tuple[list[list[tuple[Path, int]]], list[int]]:
    root = ET.parse(source / f"{spec.skill_id}.xml").getroot()
    tracks = [frame_entries(video_node(root, path), source) for path in spec.video_paths]
    frame_count = len(tracks[0])
    if any(len(track) != frame_count for track in tracks):
        raise RuntimeError(f"video track length mismatch for {spec.key}")
    delays = [track[1] for track in tracks[0]]
    for track in tracks[1:]:
        other = [entry[1] for entry in track]
        if other != delays:
            raise RuntimeError(f"video track delay mismatch for {spec.key}")
    return tracks, delays


def encode_effect(spec: EffectSpec, source: Path, output_directory: Path) -> Path:
    tracks, delays = load_effect_frames(spec, source)
    cover_bounds = alpha_union_bounds(tracks) if spec.cover_field else None
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required to export MCV files")
    with tempfile.TemporaryDirectory(prefix=f"{spec.key}-mcv-") as directory:
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
            for index in range(len(delays)):
                rendered = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
                for track in tracks:
                    layer = contain_on_screen(track[index][0], cover_bounds)
                    rendered.alpha_composite(layer)
                    layer.close()
                rgb = rendered.convert("RGB")
                alpha_channel = rendered.getchannel("A")
                color.stdin.write(rgb.tobytes())
                alpha.stdin.write(alpha_channel.tobytes())
                rgb.close()
                alpha_channel.close()
                rendered.close()
                if index == 0 or (index + 1) % 20 == 0 or index + 1 == len(delays):
                    print(f"encoded {spec.key}: {index + 1}/{len(delays)}", flush=True)
            color.stdin.close()
            alpha.stdin.close()
            if color.wait() != 0 or alpha.wait() != 0:
                raise RuntimeError(f"FFmpeg failed while encoding {spec.key}")
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
        output = output_directory / spec.output_name
        write_mcv(output, color_fourcc, color_packets, alpha_packets, delays)
    print(f"wrote: {output} frames={len(delays)} duration_ms={sum(delays)} bytes={output.stat().st_size}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--effect", choices=("all", *(spec.key for spec in EFFECTS)), default="all")
    args = parser.parse_args()
    selected = EFFECTS if args.effect == "all" else tuple(spec for spec in EFFECTS if spec.key == args.effect)
    args.output_directory.mkdir(parents=True, exist_ok=True)
    for spec in selected:
        encode_effect(spec, args.source, args.output_directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
