#!/usr/bin/env python3
"""Export the three formal Dawn Warrior full-screen effects as MCV files."""

from __future__ import annotations

import argparse
import tempfile
from dataclasses import dataclass
from pathlib import Path

from export_soul_eclipse_mcv import (
    DEFAULT_SOURCE,
    encode_streams,
    frame_delay,
    load_frames,
    read_ivf,
    write_mcv,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIRECTORY = ROOT / "clien" / "Data" / "Video"


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
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
        export_effect(spec, args.source, args.output_directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
