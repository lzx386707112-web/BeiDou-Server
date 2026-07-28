#!/usr/bin/env python3
"""Limit Kalos Canvas frames to 1280x720 and recompress them as ARGB4444."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

from wzpy import WzCanvasProperty, WzImage, WzKey, WzVectorProperty  # noqa: E402
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


CLIENT_MOB = ROOT / "clien/Data/Mob/8880803.img"
MAX_WIDTH = 1280
MAX_HEIGHT = 720
TARGET_KEY = WzKey.for_region("GMS")


def walk(node):
    yield node
    if hasattr(node, "children"):
        for child in node.children():
            yield from walk(child)


def atomic_write(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
    ) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def optimize() -> tuple[int, int, int]:
    before = CLIENT_MOB.stat().st_size
    image = WzImage.from_bytes(CLIENT_MOB.read_bytes(), key=TARGET_KEY, name=CLIENT_MOB.name)
    image.parse()

    canvas_count = 0
    resized_count = 0
    for canvas in walk(image.root):
        if not isinstance(canvas, WzCanvasProperty) or not canvas.has_pixels():
            continue
        if int(canvas.format) + int(canvas.format2) != 1:
            raise ValueError(f"unexpected Canvas format on {canvas.name}: {canvas.value}")

        pixels = decode_canvas(canvas, region="GMS").convert("RGBA")
        old_width, old_height = pixels.size
        scale = min(1.0, MAX_WIDTH / old_width, MAX_HEIGHT / old_height)
        new_width = max(1, min(MAX_WIDTH, round(old_width * scale)))
        new_height = max(1, min(MAX_HEIGHT, round(old_height * scale)))

        if (new_width, new_height) != (old_width, old_height):
            pixels = pixels.resize((new_width, new_height), Image.Resampling.LANCZOS)
            scale_x = new_width / old_width
            scale_y = new_height / old_height
            for child in canvas.children():
                if isinstance(child, WzVectorProperty):
                    child.x = round(child.x * scale_x)
                    child.y = round(child.y * scale_y)
            canvas.width = new_width
            canvas.height = new_height
            resized_count += 1

        canvas.format = 1
        canvas.format2 = 0
        canvas._png_data = encode_canvas_payload(
            pixels,
            1,
            int(canvas.width),
            int(canvas.height),
            key=TARGET_KEY,
            listwz=False,
            zlib_level=9,
        )
        canvas._png_length = len(canvas._png_data)
        canvas_count += 1

    atomic_write(CLIENT_MOB, encode_image_body(image, image.wz_file.reader))
    return before, CLIENT_MOB.stat().st_size, resized_count


def verify() -> int:
    image = WzImage.from_bytes(CLIENT_MOB.read_bytes(), key=TARGET_KEY, name=CLIENT_MOB.name)
    image.parse()
    canvas_count = 0
    for canvas in walk(image.root):
        if not isinstance(canvas, WzCanvasProperty) or not canvas.has_pixels():
            continue
        if int(canvas.width) > MAX_WIDTH or int(canvas.height) > MAX_HEIGHT:
            raise ValueError(f"oversized Canvas remains: {canvas.width}x{canvas.height}")
        decode_canvas(canvas, region="GMS")
        canvas_count += 1
    return canvas_count


def main() -> None:
    before, after, resized_count = optimize()
    canvas_count = verify()
    print(
        f"kalos 720p optimization ok: canvases={canvas_count} resized={resized_count} "
        f"before={before / 1024 / 1024:.2f}MiB after={after / 1024 / 1024:.2f}MiB "
        f"saved={(before - after) / before:.2%}"
    )


if __name__ == "__main__":
    main()
