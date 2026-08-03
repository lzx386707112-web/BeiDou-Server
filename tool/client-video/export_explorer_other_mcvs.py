#!/usr/bin/env python3
"""Encode full-screen TMS video tracks for the remaining Explorer attacks."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATCH_SKILL = ROOT / "tool" / "scripts" / "patch-skill"
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(PATCH_SKILL))
sys.path.insert(0, str(WZPY))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.properties import WzSubProperty, WzVideoProperty  # noqa: E402

import export_explorer_other_ms as ms_export  # noqa: E402
import patch_explorer_other_v_vi as migration  # noqa: E402
from export_thunder_breaker_mcvs import encode_tracks, source_video  # noqa: E402


DEFAULT_OUTPUT_DIRECTORY = ROOT / "clien" / "Data" / "Video"


def video_paths(node: WzSubProperty, prefix: str = "") -> list[str]:
    paths = []
    for child in node.children():
        path = f"{prefix}/{child.name}" if prefix else child.name
        if isinstance(child, WzVideoProperty):
            paths.append(path)
        elif isinstance(child, WzSubProperty):
            paths.extend(video_paths(child, path))
    return paths


def selected_video_skills():
    for job in migration.build_runtime_jobs():
        for spec in job.skills:
            if spec.hidden:
                continue
            metadata = migration.MS_EXPORT_ROOT / f"{spec.source_id}.xml"
            if "<video " in metadata.read_text(encoding="utf-8"):
                yield job, spec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--skill", type=int)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    selected = [item for item in selected_video_skills()
                if args.skill is None or item[1].target_id == args.skill]
    if args.list:
        for job, spec in selected:
            print(f"{spec.target_id}\t{spec.source_id}\t{job.config.key}\t{spec.name}\t"
                  f"explorer-{spec.target_id}.mcv")
        return 0
    if not selected:
        raise RuntimeError("no matching active video skill")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required")
    args.output_directory.mkdir(parents=True, exist_ok=True)
    by_group = {}
    for job, spec in selected:
        by_group.setdefault(spec.source_group, []).append((job, spec))
    with tempfile.TemporaryDirectory(prefix="explorer-other-mcv-") as directory_name:
        temporary = Path(directory_name)
        for group, skills in by_group.items():
            pack, prefix = ms_export.GROUPS[group]
            extracted_directory = temporary / group
            subprocess.run([
                "/opt/homebrew/bin/dotnet", str(ms_export.MS_PROBE), str(pack),
                str(extracted_directory), prefix,
            ], check=True)
            extracted = extracted_directory / f"Skill_{group}.img"
            image = WzImage.from_bytes(
                extracted.read_bytes(), key=WzKey.for_region("BMS"), name=extracted.name
            )
            root = image.parse()
            for _, spec in skills:
                output = args.output_directory / f"explorer-{spec.target_id}.mcv"
                if output.exists() and not args.force:
                    print(f"exists: {output}")
                    continue
                skill = root.get(f"skill/{spec.source_id}")
                if not isinstance(skill, WzSubProperty):
                    raise RuntimeError(f"missing video source skill: {spec.source_id}")
                paths = video_paths(skill)
                if not paths:
                    raise RuntimeError(f"missing source video tracks: {spec.source_id}")
                tracks = tuple(source_video(image, root, spec.source_id, path) for path in paths)
                encode_tracks(str(spec.target_id), tracks, output, ffmpeg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
