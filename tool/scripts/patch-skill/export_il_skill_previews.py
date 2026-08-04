#!/usr/bin/env python3
"""Export representative Ice/Lightning V and VI skill frames as contact sheets."""

from __future__ import annotations

import argparse
import math
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
sys.path.insert(0, str(ROOT / "tool" / "client-video"))

from export_thunder_breaker_mcvs import parse_mcv, start_decoder  # noqa: E402
from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.properties import WzCanvasProperty, WzProperty  # noqa: E402


DEFAULT_SOURCE = ROOT / "clien" / "Data" / "Skill" / "222.img"
DEFAULT_OUTPUT = Path.home() / "Downloads" / "冰雷五六转技能预览"
FONT_PATH = Path("/System/Library/Fonts/STHeiti Light.ttc")
VIDEO_ROOT = ROOT / "clien" / "Data" / "Video"

SKILL_GROUPS = (
    ("五转", "極冰雷域", (2221009,)),
    ("五转", "落雷凝聚", (2221010, 2221011, 2221012)),
    ("五转", "冰雪之精神", (2221013,)),
    ("五转", "眾神之雷", (2221014, 2221015)),
    ("六转", "極凍衝擊", (2221016,)),
    ("六转", "閃電連擊VI", (2221017, 2221018)),
    ("六转", "暴風雪VI", (2221020, 2221021)),
    ("六转", "雷霆萬鈞VI", (2221022, 2221026)),
    ("六转", "殛凍領域", (2221027, 2221028, 2221029)),
    ("六转", "圓弧雷鳴", (2221030, 2221031)),
)

BRANCH_PRIORITY = (
    "effect", "special", "hit", "ball", "shootobj", "secondatom",
    "attack", "summon", "prepare", "finish", "screen",
)

MCV_SKILLS = {
    2221027: VIDEO_ROOT / "explorer-2221027.mcv",
    2221030: VIDEO_ROOT / "explorer-2221030.mcv",
}


def walk_canvases(node: WzProperty, prefix: str = ""):
    for child in node.children():
        path = f"{prefix}/{child.name}" if prefix else child.name
        if isinstance(child, WzCanvasProperty) and child.has_pixels():
            if child.width > 1 and child.height > 1:
                yield path, child
        yield from walk_canvases(child, path)


def branch_rank(path: str) -> tuple[int, str]:
    lowered = path.lower()
    for index, keyword in enumerate(BRANCH_PRIORITY):
        if keyword in lowered:
            return index, path
    return len(BRANCH_PRIORITY), path


def representative_frames(skill: WzProperty, limit: int = 12):
    canvases = list(walk_canvases(skill))
    by_parent = defaultdict(list)
    icon = None
    for path, canvas in canvases:
        if path == "icon":
            icon = (path, canvas)
            continue
        by_parent[path.rpartition("/")[0]].append((path, canvas))

    branches = sorted(by_parent.items(), key=lambda item: branch_rank(item[0]))[:8]
    selected = [icon] if icon is not None else []
    for sample_index in range(3):
        for _, frames in branches:
            positions = (0, len(frames) // 2, len(frames) - 1)
            candidate = frames[positions[sample_index]]
            if candidate not in selected:
                selected.append(candidate)
            if len(selected) >= limit:
                return selected
    return selected


def fit_frame(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    rgba = source.convert("RGBA")
    bbox = rgba.getbbox()
    if bbox is not None:
        rgba = rgba.crop(bbox)
    rgba.thumbnail(size, Image.Resampling.LANCZOS)
    return rgba


def representative_mcv_frames(skill_id: int, path: Path):
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required to decode MCV previews")
    track = parse_mcv(path.read_bytes())
    targets = {0, len(track.delays) // 2, len(track.delays) - 1}
    selected = []
    with tempfile.TemporaryDirectory(prefix="il-preview-mcv-") as directory:
        decoder = start_decoder(ffmpeg, track, Path(directory), 0)
        try:
            for index in range(decoder.frame_count):
                frame = decoder.read_frame(index)
                if index in targets and frame is not None:
                    selected.append((skill_id, f"MCV/frame-{index}", frame.copy()))
                if frame is not None:
                    frame.close()
            decoder.close()
        except BaseException:
            if decoder.process.poll() is None:
                decoder.process.terminate()
                decoder.process.wait()
            raise
    return selected


def checkerboard(size: tuple[int, int], block: int = 16) -> Image.Image:
    image = Image.new("RGB", size, "#20242b")
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle((x, y, x + block - 1, y + block - 1), fill="#292e36")
    return image


def render_sheet(title: str, frames, output: Path) -> tuple[int, int]:
    columns = 4
    cell_width, cell_height = 390, 275
    header_height = 92
    rows = max(1, math.ceil(len(frames) / columns))
    sheet = Image.new("RGB", (columns * cell_width, header_height + rows * cell_height), "#15181d")
    draw = ImageDraw.Draw(sheet)
    title_font = ImageFont.truetype(str(FONT_PATH), 30)
    label_font = ImageFont.truetype(str(FONT_PATH), 17)
    draw.text((24, 18), title, font=title_font, fill="#f4f7fb")
    draw.text((24, 58), f"代表帧 {len(frames)} 张", font=label_font, fill="#9da8b7")

    decoded = 0
    for index, (skill_id, path, source) in enumerate(frames):
        x = (index % columns) * cell_width
        y = header_height + (index // columns) * cell_height
        panel = checkerboard((cell_width - 20, 220))
        try:
            decoded_frame = source if isinstance(source, Image.Image) else decode_canvas(source, region="GMS")
            frame = fit_frame(decoded_frame, (cell_width - 40, 200))
            panel.paste(frame, ((panel.width - frame.width) // 2, (panel.height - frame.height) // 2), frame)
            decoded += 1
        except Exception as exc:  # keep the sheet useful if one frame is unsupported
            ImageDraw.Draw(panel).text((12, 12), f"解码失败: {exc}", font=label_font, fill="#ff8c8c")
        sheet.paste(panel, (x + 10, y + 8))
        label = f"{skill_id}  {path}"
        draw.text((x + 12, y + 235), label[:43], font=label_font, fill="#d5dbe4")

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, optimize=True)
    return decoded, len(frames)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    image = WzImage.from_file(str(args.source), key=WzKey.for_region("GMS"))
    root = image.parse()
    args.output.mkdir(parents=True, exist_ok=True)

    for sequence, (job, name, skill_ids) in enumerate(SKILL_GROUPS, start=1):
        frames = []
        for skill_id in skill_ids:
            skill = root.get(f"skill/{skill_id}")
            if skill is None:
                raise RuntimeError(f"missing skill node {skill_id}")
            frames.extend((skill_id, path, canvas) for path, canvas in representative_frames(skill))
            if skill_id in MCV_SKILLS:
                frames.extend(representative_mcv_frames(skill_id, MCV_SKILLS[skill_id]))
        filename = f"{sequence:02d}_{job}_{name}_{'-'.join(map(str, skill_ids))}.png"
        decoded, total = render_sheet(
            f"{job} / {name} / 节点 {', '.join(map(str, skill_ids))}", frames, args.output / filename
        )
        print(f"{filename}: {decoded}/{total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
