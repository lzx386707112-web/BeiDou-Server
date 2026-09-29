"""Scan client IMG files and histogram their Canvas pixel encodings.

Answer the question "does anything use ARGB8888?" with evidence. Walks the real
parsed property tree of each IMG (never guesses from the path) and counts
``(format, format2)`` pairs on every ``Canvas`` node.

Format meanings in this client (see tool/wz-python/wzpy/canvas.py):
    1    ARGB4444        16-bit, the compatibility baseline required by AGENTS.md
    2    ARGB8888        32-bit BGRA on disk          <- the format in question
    3    ARGB8888 1/4    4x4 block downsampled BGRA8888
    257  ARGB1555        16-bit 1/5/5/5
    513  RGB565          16-bit, no alpha
    517  RGB565 1/16     16x16 block downsampled
    1026 DXT3 (BC2)
    2050 DXT5 (BC3)

Usage:
    python3 scan_canvas_formats.py --top 100          # the size-ranked top N
    python3 scan_canvas_formats.py --all              # whole clien/ tree
    python3 scan_canvas_formats.py --paths a.img b.img
Read-only: no IMG is ever written.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter

REPO = "/Users/lizixian/Documents/mxd/BeiDou-Server"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "tool", "wz-python"))

from wzpy import WzImage, WzKey, detect_region_from_img  # noqa: E402
from wzpy.properties import WzCanvasProperty, WzProperty  # noqa: E402

CLIENT = os.path.join(REPO, "clien")

FORMAT_NAMES = {
    0: "unset",
    1: "ARGB4444",
    2: "ARGB8888",
    3: "ARGB8888(1/4 块)",
    257: "ARGB1555",
    513: "RGB565",
    517: "RGB565(1/16 块)",
    1026: "DXT3/BC2",
    2050: "DXT5/BC3",
}


def load_img(path: str) -> WzImage:
    with open(path, "rb") as fh:
        data = fh.read()
    key = WzKey.for_region(detect_region_from_img(data) or "GMS")
    img = WzImage.from_bytes(data, key=key)
    img.parse()
    return img


def walk(node: WzProperty, hist: Counter, examples: list, path: str) -> None:
    if isinstance(node, WzCanvasProperty):
        hist[(node.format, node.format2)] += 1
        if len(examples) < 8:
            examples.append((path, node.width, node.height,
                             node.format, node.format2, node._png_length))
    for ch in node.children():
        walk(ch, hist, examples, f"{path}/{ch.name}" if path else ch.name)


def scan_one(path: str) -> dict:
    hist: Counter = Counter()
    examples: list = []
    try:
        img = load_img(path)
    except Exception as exc:
        return {"path": os.path.relpath(path, CLIENT), "error": f"{type(exc).__name__}: {exc}"}
    walk(img.root, hist, examples, "")
    return {
        "path": os.path.relpath(path, CLIENT),
        "bytes": os.path.getsize(path),
        "canvases": sum(hist.values()),
        "formats": {f"{f}.{f2}": n for (f, f2), n in sorted(hist.items())},
        "examples": examples,
        "truncated": bool(img.truncated),
    }


def size_ranked(n: int) -> list:
    listing = []
    for root, _dirs, files in os.walk(CLIENT):
        for f in files:
            if f.endswith(".img"):
                p = os.path.join(root, f)
                listing.append((os.path.getsize(p), p))
    listing.sort(reverse=True)
    return [p for _s, p in listing[:n]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--paths", nargs="*")
    ap.add_argument("--out", default=os.path.join(HERE, "canvas_formats.json"))
    args = ap.parse_args()

    if args.paths:
        paths = [p if os.path.isabs(p) else os.path.join(REPO, p) for p in args.paths]
    elif args.all:
        paths = []
        for root, _dirs, files in os.walk(CLIENT):
            for f in files:
                if f.endswith(".img"):
                    paths.append(os.path.join(root, f))
    else:
        paths = size_ranked(args.top or 100)

    grand: Counter = Counter()
    per_file = []
    t0 = time.time()
    for i, p in enumerate(paths, 1):
        rec = scan_one(p)
        per_file.append(rec)
        if "formats" in rec:
            for k, v in rec["formats"].items():
                f = int(k.split(".")[0])
                grand[f] += v
        if i % 200 == 0 or i == len(paths):
            el = time.time() - t0
            sys.stderr.write(f"[{i}/{len(paths)}] {el:.0f}s\n")

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"grand": {str(k): v for k, v in sorted(grand.items())},
                   "files": per_file}, fh, ensure_ascii=False, indent=1)

    total = sum(grand.values()) or 1
    print(f"扫描 {len(paths)} 个 IMG，{total} 个 Canvas，用时 {time.time()-t0:.0f}s")
    print(f"{'format':>6} {'编码':<18} {'数量':>10} {'占比':>8}")
    for f, n in sorted(grand.items()):
        print(f"{f:>6} {FORMAT_NAMES.get(f, '?'):<18} {n:>10} {n/total*100:>7.2f}%")
    bad = [r for r in per_file if "error" in r]
    print(f"解析失败 {len(bad)} 个")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
