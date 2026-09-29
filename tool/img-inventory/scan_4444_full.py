"""Client-wide, unbiased measurement of what an ARGB8888 -> ARGB4444 conversion costs.

Read-only. Never writes to any client file.

Walks every IMG under clien/, counts payload bytes by directory, and measures a
random per-file subsample of the 8888 canvases so the estimate is not biased
toward the first (usually largest) files. Per measured canvas it records the
compressed size before/after and a three-way risk class:

  LOSSLESS     all four channels already multiples of 17 -> 4444 is bit-exact
  ALPHA_ONLY   colour exact, only the alpha steps move
  COLOUR_LOSS  a colour channel moves -> visible banding risk

Also censuses the observed payload quirk: how often the decompressed payload is
an exact 2x multiple of width*height*4 with an all-zero trailing plane.

Run: python3 scan_4444_full.py --per-file 8 --out full.json
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import zlib
from collections import Counter, defaultdict

import numpy as np

REPO = "/Users/lizixian/Documents/mxd/BeiDou-Server"
sys.path.insert(0, os.path.join(REPO, "tool", "wz-python"))

from wzpy import WzImage, WzKey, detect_region_from_img  # noqa: E402
from wzpy.canvas import _read_canvas_bytes, _decompress  # noqa: E402
from wzpy.properties import WzCanvasProperty  # noqa: E402

CLIEN = os.path.join(REPO, "clien")
LEVEL = 6


def cat_of(rel: str) -> str:
    parts = rel.split("/")[1:]
    if parts and parts[-1].endswith(".img"):
        parts = parts[:-1]
    return "/".join(parts[:2]) if parts else "(root)"


def walk(node, path=""):
    for ch in node.children():
        p = f"{path}/{ch.name}" if path else ch.name
        yield p, ch
        yield from walk(ch, p)


def pack4444(arr: np.ndarray) -> bytes:
    """arr is HxWx4 BGRA uint8 -> packed ARGB4444 (2 bytes/pixel)."""
    b4 = arr[..., 0] >> 4
    g4 = arr[..., 1] >> 4
    r4 = arr[..., 2] >> 4
    a4 = arr[..., 3] >> 4
    lo = (b4 | (g4 << 4)).astype(np.uint8)
    hi = (r4 | (a4 << 4)).astype(np.uint8)
    out = np.empty((arr.shape[0], arr.shape[1], 2), dtype=np.uint8)
    out[..., 0] = lo
    out[..., 1] = hi
    return out.tobytes()


def unpack4444(packed: bytes, h: int, w: int) -> np.ndarray:
    pb = np.frombuffer(packed, dtype=np.uint8)
    lo = pb[0::2].astype(np.uint16)
    hi = pb[1::2].astype(np.uint16)
    dec = np.empty((h * w, 4), dtype=np.uint8)
    r4 = hi & 0x0F
    g4 = (lo >> 4) & 0x0F
    b4 = lo & 0x0F
    a4 = (hi >> 4) & 0x0F
    dec[:, 0] = (b4 | (b4 << 4)).astype(np.uint8)
    dec[:, 1] = (g4 | (g4 << 4)).astype(np.uint8)
    dec[:, 2] = (r4 | (r4 << 4)).astype(np.uint8)
    dec[:, 3] = (a4 | (a4 << 4)).astype(np.uint8)
    return dec.reshape(h, w, 4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-file", type=int, default=8,
                    help="max 8888 canvases measured per file (random)")
    ap.add_argument("--seed", type=int, default=424242)
    ap.add_argument("--max-files", type=int, default=0,
                    help="randomly restrict to this many files (0 = all)")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "full.json"))
    args = ap.parse_args()
    rnd = random.Random(args.seed)

    files = []
    for root, _d, fs in os.walk(CLIEN):
        for f in fs:
            if f.endswith(".img"):
                p = os.path.join(root, f)
                try:
                    files.append((os.path.getsize(p), os.path.relpath(p, CLIEN)))
                except OSError:
                    pass
    files.sort(reverse=True)
    total = sum(s for s, _ in files)
    rnd0 = random.Random(args.seed + 1)
    if args.max_files and args.max_files < len(files):
        files = rnd0.sample(files, args.max_files)

    cnt = defaultdict(Counter)
    cls = defaultdict(Counter)
    cls_bytes = defaultdict(Counter)
    ratio = defaultdict(Counter)
    zlibsum = defaultdict(Counter)
    err_acc = defaultdict(lambda: {"px": 0, "rgb": 0.0, "a": 0.0, "rgbmax": 0, "amax": 0,
                                   "a_changed": 0, "worst": None})
    failures = Counter()
    t0 = time.time()
    prog = open("/tmp/scan4444.progress", "w")

    for fi, (fsize, rel) in enumerate(files):
        cat = cat_of(rel)
        try:
            with open(os.path.join(CLIEN, rel), "rb") as fh:
                data = fh.read()
            region = detect_region_from_img(data) or "GMS"
            img = WzImage.from_bytes(data, key=WzKey.for_region(region))
            img.parse()
        except Exception as e:  # noqa: BLE001
            failures[f"parse:{type(e).__name__}"] += 1
            continue
        key = WzKey.for_region(region)
        file_bytes = len(data)

        canv = []
        for path, node in walk(img.root):
            if isinstance(node, WzCanvasProperty):
                canv.append((path, node))
        if not canv:
            continue

        p8 = [c for c in canv if c[1].format + c[1].format2 == 2 and c[1].has_pixels()]
        for _p, n in canv:
            fmt = n.format + n.format2
            cnt[cat][f"fmt{fmt}"] += 1
            cnt[cat]["canvas"] += 1
            if not n.has_pixels():
                cnt[cat]["no_payload"] += 1
        cnt[cat]["file_bytes"] += file_bytes
        cnt[cat]["files"] += 1

        # payload census for every 8888 canvas in this file
        for _p, n in p8:
            try:
                blob = _read_canvas_bytes(n)
            except Exception:  # noqa: BLE001
                failures["payload_read"] += 1
                continue
            zlibsum[cat]["payload_all"] += len(blob)
            cnt[cat]["payload_bytes"] += len(blob)

        if not p8:
            continue
        pick = p8 if len(p8) <= args.per_file else rnd.sample(p8, args.per_file)
        for path, node in pick:
            need = node.width * node.height * 4
            if need == 0:
                continue
            try:
                raw_full = _decompress(node, key)
            except Exception as e:  # noqa: BLE001
                failures[f"decompress:{type(e).__name__}"] += 1
                continue
            r = round(len(raw_full) / need, 3)
            ratio[cat][f"x{r}"] += 1
            if len(raw_full) > need:
                tail = np.frombuffer(raw_full, dtype=np.uint8)[need:]
                ratio[cat]["tail_zero" if not tail.any() else "tail_nonzero"] += 1
            if len(raw_full) < need:
                failures["short"] += 1
                continue
            arr = np.frombuffer(raw_full[:need], dtype=np.uint8).reshape(node.height, node.width, 4)

            c8 = len(zlib.compress(raw_full, LEVEL))
            packed = pack4444(arr)
            c4 = len(zlib.compress(packed, LEVEL))
            zlibsum[cat]["c8"] += c8
            zlibsum[cat]["c4"] += c4
            cls[cat]["measured"] += 1

            dec = unpack4444(packed, node.height, node.width)
            rgb_e = np.abs(dec[..., :3].astype(np.int16) - arr[..., :3].astype(np.int16))
            a_e = np.abs(dec[..., 3].astype(np.int16) - arr[..., 3].astype(np.int16))
            cmax, amax = int(rgb_e.max()), int(a_e.max())
            npx = node.width * node.height
            acc = err_acc[cat]
            acc["px"] += npx
            acc["rgb"] += float(rgb_e.sum())
            acc["a"] += float(a_e.sum())
            acc["rgbmax"] = max(acc["rgbmax"], cmax)
            acc["amax"] = max(acc["amax"], amax)
            acc["a_changed"] += int((a_e > 0).sum())

            if cmax == 0 and amax == 0:
                kind = "LOSSLESS"
            elif cmax == 0:
                kind = "ALPHA_ONLY"
            else:
                kind = "COLOUR_LOSS"
            cls[cat][kind] += 1
            cls_bytes[cat][kind] += c8
            cls_bytes[cat][kind + "_c4"] += c4
            cls_bytes[cat][kind + "_px"] += npx
            if kind == "COLOUR_LOSS" and (acc["worst"] is None or cmax > acc["worst"][0]):
                acc["worst"] = [cmax, f"{rel}::{path}", node.width, node.height]

        if fi % 2000 == 0:
            prog.write(f"{fi}/{len(files)} {time.time()-t0:.0f}s cat={cat}\n")
            prog.flush()

    dur = time.time() - t0
    prog.write(f"DONE {dur:.0f}s\n")
    prog.close()

    out = {
        "seconds": round(dur, 1),
        "files_total": len(files),
        "clien_img_bytes": total,
        "counts": {k: dict(v) for k, v in cnt.items()},
        "classes": {k: dict(v) for k, v in cls.items()},
        "class_bytes": {k: dict(v) for k, v in cls_bytes.items()},
        "ratio": {k: dict(v) for k, v in ratio.items()},
        "zlib": {k: dict(v) for k, v in zlibsum.items()},
        "errors": {k: {kk: vv for kk, vv in v.items() if kk != "worst"}
                   for k, v in err_acc.items()},
        "worst": {k: v["worst"] for k, v in err_acc.items() if v["worst"]},
        "failures": dict(failures),
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    sys.stderr.write(f"[done] {dur:.0f}s -> {args.out}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
