#!/usr/bin/env python3
"""Update MapleStory IMG canvas metadata from PNG files.

This script updates the server-side XML exported from IMG files and can also
call an external wz-python command to write the real PNG pixels into the client
IMG file.

Examples:
  python3 tool/scripts/png2canvas/png_to_img_canvas.py \
    --png /tmp/frame0.png \
    --xml gms-server/wz/Skill.wz/100.img.xml \
    --canvas skill/1001004/effect/0 \
    --origin center \
    --set-int delay=90 \
    --set-int z=0

  python3 tool/scripts/png2canvas/png_to_img_canvas.py \
    --png-dir /tmp/effect_frames \
    --xml gms-server/wz/Skill.wz/100.img.xml \
    --canvas-dir skill/1001004/effect \
    --name-mode index \
    --origin center \
    --client-root clien/Data \
    --wz-python-cmd 'wz-python import-canvas --encoding {encoding} --img {img} --path {path} --png {png} --origin-x {origin_x} --origin-y {origin_y}'
"""

from __future__ import annotations

import argparse
import re
import shlex
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image


DEFAULT_ENCODING = "GMS"
PNG_SUFFIX = ".png"


@dataclass(frozen=True)
class CanvasJob:
    png: Path
    canvas_path: str


@dataclass(frozen=True)
class CanvasMeta:
    width: int
    height: int
    origin_x: int
    origin_y: int


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
            f"Canvas path must be an XML-internal path like skill/1221009/effect/0, not a disk path: {raw!r}"
        )
    if "\\" in raw:
        raise ValueError(f"Canvas path must use '/', not '\\': {raw!r}")
    lowered = raw.lower()
    if lowered.endswith((".png", ".img", ".img.xml")) or "/clien/data/" in f"/{lowered}/":
        raise ValueError(
            f"Canvas path must point inside the XML tree, for example skill/1221009/effect/0: {raw!r}"
        )
    parts = [part for part in raw.strip("/").split("/") if part]
    if not parts:
        raise ValueError("Canvas path cannot be empty")
    return parts


def child_by_name(parent: ET.Element, tag: str, name: str) -> ET.Element | None:
    for child in parent:
        if child.tag == tag and child.get("name") == name:
            return child
    return None


def ensure_imgdir(parent: ET.Element, name: str, create: bool) -> ET.Element:
    existing = child_by_name(parent, "imgdir", name)
    if existing is not None:
        return existing
    if not create:
        raise KeyError(f"Missing imgdir {name!r}")
    return ET.SubElement(parent, "imgdir", {"name": name})


def ensure_canvas(root: ET.Element, canvas_path: str, create: bool) -> ET.Element:
    parts = split_canvas_path(canvas_path)
    if root.get("name") == parts[0]:
        parts = parts[1:]
    if not parts:
        raise ValueError(f"Canvas path {canvas_path!r} points to the root")

    parent = root
    for part in parts[:-1]:
        parent = ensure_imgdir(parent, part, create)

    name = parts[-1]
    existing = child_by_name(parent, "canvas", name)
    if existing is not None:
        return existing

    non_canvas = child_by_name(parent, "imgdir", name)
    if non_canvas is not None:
        raise TypeError(f"Path {canvas_path!r} already exists as imgdir, not canvas")
    if not create:
        raise KeyError(f"Missing canvas {canvas_path!r}")
    return ET.SubElement(parent, "canvas", {"name": name})


def set_int_child(parent: ET.Element, name: str, value: str) -> None:
    node = child_by_name(parent, "int", name)
    if node is None:
        node = ET.SubElement(parent, "int", {"name": name})
    node.set("value", value)


def set_vector_child(parent: ET.Element, name: str, x: int, y: int) -> None:
    node = child_by_name(parent, "vector", name)
    if node is None:
        node = ET.SubElement(parent, "vector", {"name": name})
    node.set("x", str(x))
    node.set("y", str(y))


def read_png_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        image.verify()
        return image.size


def resolve_origin(
    mode: str,
    canvas: ET.Element,
    width: int,
    height: int,
) -> tuple[int, int]:
    origin = child_by_name(canvas, "vector", "origin")
    if mode == "keep":
        if origin is not None:
            return int(origin.get("x", "0")), int(origin.get("y", "0"))
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


def update_canvas(
    root: ET.Element,
    job: CanvasJob,
    origin_mode: str,
    ints: Iterable[tuple[str, str]],
    create: bool,
) -> CanvasMeta:
    width, height = read_png_size(job.png)
    canvas = ensure_canvas(root, job.canvas_path, create)
    origin_x, origin_y = resolve_origin(origin_mode, canvas, width, height)

    canvas.set("width", str(width))
    canvas.set("height", str(height))
    set_vector_child(canvas, "origin", origin_x, origin_y)
    for name, value in ints:
        set_int_child(canvas, name, value)

    return CanvasMeta(width=width, height=height, origin_x=origin_x, origin_y=origin_y)


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


def derive_client_img(xml_path: Path, server_root: Path, client_root: Path) -> Path:
    rel = xml_path.resolve().relative_to(server_root.resolve())
    parts = list(rel.parts)
    converted: list[str] = []
    for part in parts:
        if part.endswith(".wz"):
            converted.append(part[:-3])
        elif part.endswith(".img.xml"):
            converted.append(part[:-4])
        else:
            converted.append(part)
    return client_root.joinpath(*converted)


def shell_quote_map(values: dict[str, object]) -> dict[str, str]:
    return {key: shlex.quote(str(value)) for key, value in values.items()}


def run_wz_python_command(
    template: str,
    encoding: str,
    client_img: Path,
    job: CanvasJob,
    meta: CanvasMeta,
    dry_run: bool,
) -> None:
    command = template.format_map(
        shell_quote_map(
            {
                "encoding": encoding,
                "img": client_img,
                "path": job.canvas_path,
                "png": job.png,
                "origin_x": meta.origin_x,
                "origin_y": meta.origin_y,
                "width": meta.width,
                "height": meta.height,
            }
        )
    )
    if dry_run:
        print(f"[dry-run] {command}")
        return
    subprocess.run(command, shell=True, check=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--png", help="Single PNG file to import.")
    source.add_argument("--png-dir", help="Directory of PNG frames to import.")
    target = parser.add_mutually_exclusive_group(required=False)
    target.add_argument("--canvas", help="Target canvas path for --png, e.g. skill/1001004/effect/0.")
    target.add_argument("--canvas-dir", help="Target parent path for --png-dir.")

    parser.add_argument("--xml", required=True, help="Server-side .img.xml file to update.")
    parser.add_argument("--server-root", default="gms-server/wz", help="Server WZ XML root.")
    parser.add_argument("--client-root", default="clien/Data", help="Client Data root.")
    parser.add_argument("--client-img", help="Client .img file. If omitted, derived from --xml.")
    parser.add_argument("--encoding", default=DEFAULT_ENCODING, help="WZ encoding, default: GMS.")
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
    parser.add_argument("--backup", action="store_true", help="Create a .bak copy before writing XML.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing files.")
    parser.add_argument(
        "--wz-python-cmd",
        help=(
            "External command template used to write client IMG pixels. Available placeholders: "
            "{encoding}, {img}, {path}, {png}, {origin_x}, {origin_y}, {width}, {height}."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    xml_path = Path(args.xml)
    jobs = collect_jobs(args)

    tree = ET.parse(xml_path)
    root = tree.getroot()
    metas: dict[CanvasJob, CanvasMeta] = {}
    for job in jobs:
        metas[job] = update_canvas(
            root=root,
            job=job,
            origin_mode=args.origin,
            ints=args.set_int,
            create=not args.no_create,
        )

    if args.wz_python_cmd:
        if args.client_img:
            client_img = Path(args.client_img)
        else:
            client_img = derive_client_img(xml_path, Path(args.server_root), Path(args.client_root))
        if not client_img.exists():
            raise FileNotFoundError(f"Client IMG not found: {client_img}")
        for job in jobs:
            run_wz_python_command(
                template=args.wz_python_cmd,
                encoding=args.encoding,
                client_img=client_img,
                job=job,
                meta=metas[job],
                dry_run=args.dry_run,
            )

    if args.dry_run:
        print(f"[dry-run] would update XML: {xml_path}")
    else:
        if args.backup:
            backup_path = xml_path.with_suffix(xml_path.suffix + ".bak")
            shutil.copy2(xml_path, backup_path)
            print(f"backup: {backup_path}")
        tree.write(xml_path, encoding="UTF-8", xml_declaration=True, short_empty_elements=True)

    print(f"updated {len(jobs)} canvas node(s) in {xml_path}")
    if not args.wz_python_cmd:
        print("client IMG pixels were not written; pass --wz-python-cmd to call your wz-python importer")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
