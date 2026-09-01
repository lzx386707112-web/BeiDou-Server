#!/usr/bin/env python3
"""Export the three formal Dawn Warrior full-screen effects as MCV files."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from export_soul_eclipse_mcv import (
    DEFAULT_SOURCE,
    HEIGHT,
    WIDTH,
    encode_streams,
    encoder_command,
    frame_delay,
    load_frames,
    read_ivf,
    write_mcv,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIRECTORY = ROOT / "clien" / "Data" / "Video"
DEFAULT_MS_SOURCE = Path(
    "/Users/lizixian/Documents/mxd/TMS/MapleStory-MS-Export/DawnWarrior"
)


@dataclass(frozen=True)
class EffectSpec:
    key: str
    source_node: str
    output_name: str
    background: tuple[int, int, int, int] | None = None
    target_duration_ms: int | None = None


EFFECTS = (
    EffectSpec(
        "galaxy-star-burst",
        "customSkill/dawnWarrior/galaxyStarBurst",
        "galaxy-star-burst.mcv",
        (4, 0, 16, 220),
    ),
    EffectSpec(
        "eclipse-force",
        "customSkill/dawnWarrior/fullEclipseMale",
        "eclipse-force.mcv",
    ),
    EffectSpec(
        "soul-eclipse",
        "customSkill/dawnWarrior/soulEclipse",
        "soul-eclipse.mcv",
        (48, 16, 4, 145),
        target_duration_ms=20_000,
    ),
)


def scale_delays(delays: list[int], target_duration_ms: int | None) -> list[int]:
    if target_duration_ms is None:
        return delays
    source_duration = sum(delays)
    if source_duration <= 0 or target_duration_ms < len(delays):
        raise RuntimeError("invalid target duration")
    result: list[int] = []
    source_elapsed = 0
    target_elapsed = 0
    for delay in delays:
        source_elapsed += delay
        next_target = round(source_elapsed * target_duration_ms / source_duration)
        result.append(max(1, next_target - target_elapsed))
        target_elapsed = next_target
    result[-1] += target_duration_ms - sum(result)
    if result[-1] <= 0 or sum(result) != target_duration_ms:
        raise RuntimeError("failed to scale frame delays")
    return result


def export_effect(spec: EffectSpec, source: Path, output_directory: Path) -> Path:
    image, frames = load_frames(source, spec.source_node)
    source_duration = sum(frame_delay(frame) for frame in frames)
    print(
        f"source effect: key={spec.key} frames={len(frames)} "
        f"duration_ms={source_duration} node={spec.source_node}"
    )
    with tempfile.TemporaryDirectory(prefix=f"{spec.key}-mcv-") as directory:
        temporary = Path(directory)
        color_path = temporary / "color.ivf"
        alpha_path = temporary / "alpha.ivf"
        delays = encode_streams(frames, color_path, alpha_path, spec.background)
        delays = scale_delays(delays, spec.target_duration_ms)
        color_fourcc, color_packets = read_ivf(color_path)
        alpha_fourcc, alpha_packets = read_ivf(alpha_path)
        if color_fourcc != alpha_fourcc:
            raise RuntimeError("color and alpha codecs do not match")
        output = output_directory / spec.output_name
        write_mcv(output, color_fourcc, color_packets, alpha_packets, delays)
    del image
    print(
        f"wrote: {output} frames={len(frames)} duration_ms={sum(delays)} "
        f"bytes={output.stat().st_size}"
    )
    return output


def child(node: ET.Element, name: str) -> ET.Element:
    result = next((item for item in node if item.attrib.get("name") == name), None)
    if result is None:
        raise RuntimeError(f"missing MS node: {name}")
    return result


def full_eclipse_track(
    source: Path,
    skill_id: int,
    branch_name: str,
) -> list[tuple[Path, int]]:
    root = ET.parse(source / f"{skill_id}.xml").getroot()
    branch = child(root, branch_name)
    video = child(branch, "video")
    result = [
        (source / frame.attrib["file"], max(1, int(frame.attrib["delay"])))
        for frame in video
        if frame.tag == "frame"
    ]
    if not result:
        raise RuntimeError(f"empty MS video: {skill_id}/{branch_name}/video")
    return result


def alpha_union_bounds(track: list[tuple[Path, int]]) -> tuple[int, int, int, int]:
    bounds = None
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
        raise RuntimeError("Full Eclipse track has no visible pixels")
    return bounds


def render_contained_frame(path: Path) -> Image.Image:
    with Image.open(path) as opened:
        source = opened.convert("RGBA")
    scale = min(1.0, WIDTH / source.width, HEIGHT / source.height)
    width = max(1, round(source.width * scale))
    height = max(1, round(source.height * scale))
    if (width, height) != source.size:
        resized = source.resize((width, height), Image.Resampling.LANCZOS)
        source.close()
        source = resized
    result = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    result.alpha_composite(
        source,
        (WIDTH // 2 - width // 2, HEIGHT // 2 - height // 2),
    )
    source.close()
    return result


def render_cover_frame(
    path: Path,
    crop_box: tuple[int, int, int, int],
) -> Image.Image:
    with Image.open(path) as opened:
        source = opened.convert("RGBA").crop(crop_box)
    scale = max(WIDTH / source.width, HEIGHT / source.height)
    width = max(WIDTH, round(source.width * scale))
    height = max(HEIGHT, round(source.height * scale))
    if (width, height) != source.size:
        resized = source.resize((width, height), Image.Resampling.LANCZOS)
        source.close()
        source = resized
    left = (width - WIDTH) // 2
    top = (height - HEIGHT) // 2
    result = source.crop((left, top, left + WIDTH, top + HEIGHT))
    source.close()
    return result


def export_full_eclipse(ms_source: Path, output_directory: Path) -> Path:
    opening = full_eclipse_track(ms_source, 11141503, "screen")
    finishing = full_eclipse_track(ms_source, 11141504, "screen")
    if len(opening) != 43 or len(finishing) != 44:
        raise RuntimeError(
            "Full Eclipse source frame count changed: "
            f"opening={len(opening)}, finishing={len(finishing)}"
        )
    delays = [delay for _, delay in (*opening, *finishing)]
    if delays != [60] * 87:
        raise RuntimeError("Full Eclipse source timing changed from 87 frames at 60ms")
    finishing_bounds = alpha_union_bounds(finishing)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required to export Full Eclipse")
    with tempfile.TemporaryDirectory(prefix="eclipse-force-mcv-") as directory:
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
                raise RuntimeError("failed to open Full Eclipse FFmpeg input pipes")
            tracks = ((opening, False), (finishing, True))
            output_index = 0
            for track, cover in tracks:
                for path, _ in track:
                    rendered = (
                        render_cover_frame(path, finishing_bounds)
                        if cover
                        else render_contained_frame(path)
                    )
                    rgb = rendered.convert("RGB")
                    opacity = rendered.getchannel("A")
                    color.stdin.write(rgb.tobytes())
                    alpha.stdin.write(opacity.tobytes())
                    rgb.close()
                    opacity.close()
                    rendered.close()
                    output_index += 1
                    if output_index == 1 or output_index % 20 == 0 or output_index == len(delays):
                        print(f"encoded eclipse-force: {output_index}/{len(delays)}", flush=True)
            color.stdin.close()
            alpha.stdin.close()
            if color.wait() != 0 or alpha.wait() != 0:
                raise RuntimeError("FFmpeg failed while encoding Full Eclipse")
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
            raise RuntimeError("Full Eclipse color and alpha codecs do not match")
        output = output_directory / "eclipse-force.mcv"
        write_mcv(output, color_fourcc, color_packets, alpha_packets, delays)
    print(
        f"wrote: {output} frames={len(delays)} duration_ms={sum(delays)} "
        f"bytes={output.stat().st_size}"
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--ms-source", type=Path, default=DEFAULT_MS_SOURCE)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument(
        "--effect",
        choices=("all", *(spec.key for spec in EFFECTS)),
        default="all",
    )
    args = parser.parse_args()
    selected = EFFECTS if args.effect == "all" else tuple(
        spec for spec in EFFECTS if spec.key == args.effect
    )
    args.output_directory.mkdir(parents=True, exist_ok=True)
    for spec in selected:
        if spec.key == "eclipse-force":
            export_full_eclipse(args.ms_source, args.output_directory)
        else:
            export_effect(spec, args.source, args.output_directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
