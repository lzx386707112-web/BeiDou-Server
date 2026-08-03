#!/usr/bin/env python3
"""Encode Explorer warrior VI full-screen layers as time-aligned transparent MCV files."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from export_blaze_wizard_mcvs import HEIGHT, WIDTH, contain_on_screen
from export_soul_eclipse_mcv import encoder_command, read_ivf, write_mcv


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-MS-Export/ExplorerWarrior")
DEFAULT_OUTPUT = ROOT / "clien" / "Data" / "Video"


@dataclass(frozen=True)
class EffectSpec:
    key: str
    skill_id: int
    paths: tuple[tuple[str, ...], ...]
    output: str
    cover_field: bool = False


EFFECTS = (
    EffectSpec("spirit-caliber", 1141500, (("screen", "video"),), "spirit-caliber.mcv"),
    EffectSpec("sacred-bastion", 1241500, (("screen", "video"),), "sacred-bastion.mcv", True),
    EffectSpec("dominus-obrion", 1241504,
               (("screen", "video"), ("screen2", "video"), ("screen3", "video")),
               "dominus-obrion.mcv", True),
    EffectSpec("dead-space", 1341500,
               (("screen", "video"), ("screen2", "video")), "dead-space.mcv", True),
    EffectSpec("dark-halidom", 1341502,
               (("special", "0", "video"), ("special", "1", "video"),
                ("screen", "video"), ("screen2", "video"), ("screen3", "video")),
               "dark-halidom.mcv"),
)


def child(node: ET.Element, name: str) -> ET.Element:
    result = next((item for item in node if item.get("name") == name), None)
    if result is None:
        raise RuntimeError(f"missing MS node {name}")
    return result


def load_tracks(spec: EffectSpec, source: Path) -> list[list[tuple[Path, int, int]]]:
    root = ET.parse(source / f"{spec.skill_id}.xml").getroot()
    tracks = []
    for path in spec.paths:
        node = root
        for name in path:
            node = child(node, name)
        if node.tag != "video":
            raise RuntimeError(f"not a video: {spec.skill_id}/{'/'.join(path)}")
        elapsed = 0
        track = []
        for frame in node.findall("frame"):
            delay = max(1, int(frame.get("delay", "1")))
            track.append((source / frame.get("file"), elapsed, elapsed + delay))
            elapsed += delay
        if not track:
            raise RuntimeError(f"empty video: {spec.skill_id}/{'/'.join(path)}")
        tracks.append(track)
    return tracks


def frame_at(track: list[tuple[Path, int, int]], time_ms: int) -> Path | None:
    for path, start, end in track:
        if start <= time_ms < end:
            return path
    return None


def timeline(tracks: list[list[tuple[Path, int, int]]]) -> list[tuple[int, int]]:
    boundaries = sorted({value for track in tracks for _, start, end in track for value in (start, end)})
    return [(start, end) for start, end in zip(boundaries, boundaries[1:]) if end > start]


def alpha_union_bounds(
        tracks: list[list[tuple[Path, int, int]]],
) -> tuple[int, int, int, int]:
    bounds = None
    for track in tracks:
        for path, _, _ in track:
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


def encode(spec: EffectSpec, source: Path, output_directory: Path) -> Path:
    tracks = load_tracks(spec, source)
    segments = timeline(tracks)
    cover_bounds = alpha_union_bounds(tracks) if spec.cover_field else None
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required")
    output_directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"{spec.key}-mcv-") as directory:
        temporary = Path(directory)
        color_path = temporary / "color.ivf"
        alpha_path = temporary / "alpha.ivf"
        color = subprocess.Popen(
            encoder_command(ffmpeg, "rgb24", 24, len(segments), color_path), stdin=subprocess.PIPE
        )
        alpha = subprocess.Popen(
            encoder_command(ffmpeg, "gray", 16, len(segments), alpha_path), stdin=subprocess.PIPE
        )
        try:
            if color.stdin is None or alpha.stdin is None:
                raise RuntimeError("failed to open FFmpeg input")
            for index, (start, _) in enumerate(segments):
                rendered = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
                for track in tracks:
                    path = frame_at(track, start)
                    if path is None:
                        continue
                    layer = contain_on_screen(path, cover_bounds)
                    rendered.alpha_composite(layer)
                    layer.close()
                rgb = rendered.convert("RGB")
                alpha_channel = rendered.getchannel("A")
                color.stdin.write(rgb.tobytes())
                alpha.stdin.write(alpha_channel.tobytes())
                rgb.close()
                alpha_channel.close()
                rendered.close()
                if index == 0 or (index + 1) % 20 == 0 or index + 1 == len(segments):
                    print(f"encoded {spec.key}: {index + 1}/{len(segments)}", flush=True)
            color.stdin.close()
            alpha.stdin.close()
            if color.wait() != 0 or alpha.wait() != 0:
                raise RuntimeError(f"FFmpeg failed: {spec.key}")
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
            raise RuntimeError("color/alpha codec mismatch")
        output = output_directory / spec.output
        write_mcv(output, color_fourcc, color_packets, alpha_packets,
                  [end - start for start, end in segments])
    print(f"wrote: {output} frames={len(segments)} duration_ms={segments[-1][1]}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--effect", choices=("all", *(item.key for item in EFFECTS)), default="all")
    args = parser.parse_args()
    selected = EFFECTS if args.effect == "all" else tuple(item for item in EFFECTS if item.key == args.effect)
    for spec in selected:
        encode(spec, args.source, args.output_directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
