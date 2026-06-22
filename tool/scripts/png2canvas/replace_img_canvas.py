#!/usr/bin/env python3
"""Replace Canvas PNG payloads inside a standalone client .img file."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_ROOT = Path(__file__).resolve().parents[3]
_WZPY = _ROOT / "tool" / "wz-python"
if str(_WZPY) not in sys.path:
    sys.path.insert(0, str(_WZPY))

from PIL import Image  # noqa: E402
from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.canvas import _ZLIB_HEADERS, _read_canvas_bytes, encode_canvas_payload  # noqa: E402
from wzpy.properties import WzCanvasProperty, WzIntProperty, WzSubProperty, WzVectorProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


PNG_SUFFIX = ".png"


@dataclass(frozen=True)
class CanvasJob:
    png: Path
    canvas_path: str


def natural_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def parse_name_value(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError(f"Expected NAME=VALUE, got {raw!r}")
    name, value = raw.split("=", 1)
    if not name:
        raise argparse.ArgumentTypeError(f"Missing name in {raw!r}")
    if not re.fullmatch(r"-?\d+", value):
        raise argparse.ArgumentTypeError(f"Integer value required in {raw!r}")
    return name, value


def split_canvas_path(raw: str) -> list[str]:
    if raw.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", raw):
        raise ValueError(
            f"Canvas path must be an .img-internal path like skill/1221009/effect/0/0, not a disk path: {raw!r}"
        )
    if "\\" in raw:
        raise ValueError(f"Canvas path must use '/', not '\\': {raw!r}")
    lowered = raw.lower()
    if lowered.endswith((".png", ".img", ".img.xml")) or "/clien/data/" in f"/{lowered}/":
        raise ValueError(
            f"Canvas path must point inside the .img tree, for example skill/1221009/effect/0/0: {raw!r}"
        )
    parts = [part for part in raw.strip("/").split("/") if part]
    if not parts:
        raise ValueError("Canvas path cannot be empty")
    return parts


def read_png(path: Path) -> Image.Image:
    with Image.open(path) as image:
        image.load()
        return image.convert("RGBA")


def child_by_name(parent: WzSubProperty, name: str):
    return parent.child(name)


def ensure_sub(parent: WzSubProperty, name: str, create: bool) -> WzSubProperty:
    existing = child_by_name(parent, name)
    if isinstance(existing, WzSubProperty) and not isinstance(existing, WzCanvasProperty):
        return existing
    if existing is not None:
        raise TypeError(f"Path segment {name!r} already exists as {type(existing).__name__}, not imgdir")
    if not create:
        raise KeyError(f"Missing imgdir {name!r}")
    node = WzSubProperty(name, parent)
    parent.add(node)
    return node


def ensure_canvas(root: WzSubProperty, canvas_path: str, create: bool) -> WzCanvasProperty:
    parts = split_canvas_path(canvas_path)
    if root.name == parts[0]:
        parts = parts[1:]
    if not parts:
        raise ValueError(f"Canvas path {canvas_path!r} points to the root")

    parent = root
    for part in parts[:-1]:
        parent = ensure_sub(parent, part, create)

    name = parts[-1]
    existing = child_by_name(parent, name)
    if isinstance(existing, WzCanvasProperty):
        return existing
    if existing is not None:
        raise TypeError(f"Path {canvas_path!r} already exists as {type(existing).__name__}, not Canvas")
    if not create:
        raise KeyError(f"Missing canvas {canvas_path!r}")
    canvas = WzCanvasProperty(name, parent)
    canvas.format = 2
    canvas.format2 = 0
    parent.add(canvas)
    return canvas


def set_int_child(parent: WzSubProperty, name: str, value: str) -> None:
    node = parent.child(name)
    if node is None:
        parent.add(WzIntProperty(name, int(value), parent))
        return
    if not isinstance(node, WzIntProperty):
        raise TypeError(f"Child {name!r} exists as {type(node).__name__}, not Int")
    node._value = int(value)


def set_vector_child(parent: WzSubProperty, name: str, x: int, y: int) -> None:
    node = parent.child(name)
    if node is None:
        parent.add(WzVectorProperty(name, x, y, parent))
        return
    if not isinstance(node, WzVectorProperty):
        raise TypeError(f"Child {name!r} exists as {type(node).__name__}, not Vector")
    node.x = x
    node.y = y
    node._value = (x, y)


def resolve_origin(mode: str, canvas: WzCanvasProperty, width: int, height: int) -> tuple[int, int]:
    origin = canvas.child("origin")
    if mode == "keep":
        if isinstance(origin, WzVectorProperty):
            return int(origin.x), int(origin.y)
        return 0, height
    if mode == "center":
        return width // 2, height // 2
    if mode == "bottom-left":
        return 0, height
    if mode == "bottom-center":
        return width // 2, height

    match = re.fullmatch(r"\s*(-?\d+)\s*,\s*(-?\d+)\s*", mode)
    if match:
        return int(match.group(1)), int(match.group(2))
    raise ValueError(f"Invalid origin mode {mode!r}")


def collect_jobs(args: argparse.Namespace) -> list[CanvasJob]:
    if args.png:
        if not args.canvas:
            raise ValueError("--canvas is required with --png")
        split_canvas_path(args.canvas)
        return [CanvasJob(Path(args.png), args.canvas)]

    png_dir = Path(args.png_dir)
    if not args.canvas_dir:
        raise ValueError("--canvas-dir is required with --png-dir")
    split_canvas_path(args.canvas_dir)
    pngs = sorted(
        [path for path in png_dir.iterdir() if path.is_file() and path.suffix.lower() == PNG_SUFFIX],
        key=lambda path: natural_key(path.name),
    )
    if not pngs:
        raise ValueError(f"No PNG files found in {png_dir}")

    jobs: list[CanvasJob] = []
    for index, png in enumerate(pngs):
        name = str(index) if args.name_mode == "index" else png.stem
        jobs.append(CanvasJob(png, f"{args.canvas_dir.strip('/')}/{name}"))
    return jobs


def original_is_listwz(canvas: WzCanvasProperty) -> bool:
    if not canvas.has_pixels():
        return False
    raw = _read_canvas_bytes(canvas)
    return len(raw) >= 2 and (raw[0] | (raw[1] << 8)) not in _ZLIB_HEADERS


def update_canvas(
    root: WzSubProperty,
    job: CanvasJob,
    origin_mode: str,
    ints: Iterable[tuple[str, str]],
    create: bool,
    key: WzKey,
) -> str:
    image = read_png(job.png)
    canvas = ensure_canvas(root, job.canvas_path, create)
    old_size = (int(canvas.width), int(canvas.height))
    width, height = image.size
    origin_x, origin_y = resolve_origin(origin_mode, canvas, width, height)

    if canvas.format == 0:
        canvas.format = 2
        canvas.format2 = 0

    payload = encode_canvas_payload(
        image,
        int(canvas.format) + int(canvas.format2),
        width,
        height,
        key=key,
        listwz=original_is_listwz(canvas),
    )
    canvas.width = width
    canvas.height = height
    canvas._png_data = payload
    canvas._png_length = len(payload)
    set_vector_child(canvas, "origin", origin_x, origin_y)
    for name, value in ints:
        set_int_child(canvas, name, value)

    return f"{job.canvas_path}: {old_size[0]}x{old_size[1]} -> {width}x{height}"


def write_img(path: Path, data: bytes, backup: bool) -> None:
    if backup:
        backup_path = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup_path)
        print(f"backup: {backup_path}")

    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(data)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--png", help="Single PNG file to import.")
    source.add_argument("--png-dir", help="Directory of PNG frames to import.")
    target = parser.add_mutually_exclusive_group(required=False)
    target.add_argument("--canvas", help="Target canvas path for --png, e.g. skill/1221009/effect/0/0.")
    target.add_argument("--canvas-dir", help="Target parent path for --png-dir, e.g. skill/1221009/effect/0.")
    parser.add_argument("--img", required=True, help="Client standalone .img file to update.")
    parser.add_argument("--region", default="GMS", help="WZ region, default: GMS.")
    parser.add_argument(
        "--origin",
        default="keep",
        help="keep, center, bottom-left, bottom-center, or x,y. Default keeps existing origin.",
    )
    parser.add_argument(
        "--set-int",
        action="append",
        type=parse_name_value,
        default=[],
        metavar="NAME=VALUE",
        help="Set or create an int child on every canvas, e.g. delay=90 or z=0.",
    )
    parser.add_argument(
        "--name-mode",
        choices=("index", "stem"),
        default="index",
        help="Canvas names for --png-dir. index creates 0,1,2...; stem uses file names.",
    )
    parser.add_argument("--no-create", action="store_true", help="Fail if imgdirs/canvases are missing.")
    parser.add_argument("--backup", action="store_true", help="Create a .bak copy before writing .img.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing files.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    img_path = Path(args.img)
    jobs = collect_jobs(args)

    data = img_path.read_bytes()
    key = WzKey.for_region(args.region)
    image = WzImage.from_bytes(data, key=key, name=img_path.name)
    root = image.parse()

    summaries = [
        update_canvas(
            root=root,
            job=job,
            origin_mode=args.origin,
            ints=args.set_int,
            create=not args.no_create,
            key=key,
        )
        for job in jobs
    ]

    for summary in summaries:
        print(summary)

    if args.dry_run:
        print(f"[dry-run] would update client IMG: {img_path}")
        return 0

    out = encode_image_body(image, image.wz_file.reader)
    write_img(img_path, out, args.backup)
    print(f"updated {len(jobs)} canvas node(s) in {img_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
