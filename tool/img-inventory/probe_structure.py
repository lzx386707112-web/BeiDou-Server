"""Three structural probes that decide whether a client-wide ARGB4444
conversion is mechanically safe, independent of how good it looks.

Read-only for the client data. Writes structure.json next to itself.

Probe 1 -- variable-length refusal rate
    Ask ``incremental_img.replace_img_record`` to replace one ARGB8888 Canvas
    record with an identical copy. That is the *most permissive* case of a
    size-changing edit; if the patcher refuses this it will refuse the real
    conversion too. The refusal is deliberate: it fires when a string reference
    target lies inside the replaced span and cannot be rebased.

Probe 2 -- same-length in-place patch inertness
    Overwrite a canvas payload region in place with the same number of bytes
    and check that (a) every changed byte lies inside that region, (b) the file
    length is unchanged, (c) the result still parses without warnings. This is
    the technique AGENTS.md ranks first ("same-length in-place patch").

Probe 3 -- zero-tail plane census and cost
    Measure how often a decompressed ARGB8888 payload is an exact 2x multiple
    of width*height*4 with an all-zero second half, and how many compressed
    bytes that redundant plane actually costs.
"""
from __future__ import annotations

import json
import os
import random
import sys
import zlib
from collections import Counter, defaultdict

REPO = "/Users/lizixian/Documents/mxd/BeiDou-Server"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "tool", "wz-python"))

from wzpy import WzImage, WzKey, detect_region_from_img  # noqa: E402
from wzpy.properties import WzCanvasProperty  # noqa: E402
from wzpy.canvas import _read_canvas_bytes, _decompress  # noqa: E402
from wzpy.incremental_img import replace_img_record  # noqa: E402

CLIEN = os.path.join(REPO, "clien")


def walk(node, path=""):
    for ch in node.children():
        p = f"{path}/{ch.name}" if path else ch.name
        yield p, ch
        yield from walk(ch, p)


def load(fp):
    with open(fp, "rb") as fh:
        data = fh.read()
    region = detect_region_from_img(data) or "GMS"
    img = WzImage.from_bytes(data, key=WzKey.for_region(region))
    img.parse()
    return data, img, region


def first_rgb_canvas(img):
    for p, n in walk(img.root):
        if (isinstance(n, WzCanvasProperty) and n.has_pixels()
                and n.format + n.format2 == 2):
            return p.split("/"), n
    return None, None


def probe1(files, sample=120, seed=5):
    rnd = random.Random(seed)
    res = Counter()
    by_top = defaultdict(Counter)
    for fp in rnd.sample(files, sample):
        top = os.path.relpath(fp, CLIEN).split("/")[1] if "/" in os.path.relpath(fp, CLIEN) else "?"
        try:
            data, img, region = load(fp)
        except Exception:  # noqa: BLE001
            res["file_parse_fail"] += 1
            by_top[top]["file_parse_fail"] += 1
            continue
        path, node = first_rgb_canvas(img)
        if node is None:
            res["no_8888_payload"] += 1
            by_top[top]["no_8888_payload"] += 1
            continue
        try:
            replace_img_record(data, path, node, region=region)
            res["accepted"] += 1
            by_top[top]["accepted"] += 1
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            k = ("refused_string_reference" if "points into replaced bytes" in msg
                 else "refused_opaque_extended" if "opaque extended" in msg
                 else f"other:{type(e).__name__}")
            res[k] += 1
            by_top[top][k] += 1
    return {"sample": sample, "counts": dict(res),
            "by_top_dir": {k: dict(v) for k, v in by_top.items()}}


def probe2(files, sample=8, seed=99):
    rnd = random.Random(seed)
    out = []
    for fp in rnd.sample(files, sample):
        rel = os.path.relpath(fp, CLIEN)
        try:
            data, img, region = load(fp)
        except Exception:  # noqa: BLE001
            continue
        path, node = first_rgb_canvas(img)
        if node is None:
            continue
        start, ln = node._png_offset, node._png_length
        new = bytearray(data)
        new[start:start + ln] = bytes(reversed(data[start:start + ln]))
        diff = [i for i in range(len(data)) if data[i] != new[i]]
        inside = all(start <= i < start + ln for i in diff)
        try:
            im2 = WzImage.from_bytes(bytes(new), key=WzKey.for_region(region))
            im2.parse()
            reparses = not im2.truncated and not im2.parse_warnings
        except Exception:  # noqa: BLE001
            reparses = False
        out.append({"file": rel, "canvas": f"{node.width}x{node.height}",
                    "payload_offset": start, "payload_len": ln,
                    "changed_bytes": len(diff), "all_inside_payload": inside,
                    "length_unchanged": len(new) == len(data),
                    "reparses_clean": reparses})
    return out


def probe3(files, sample=10, seed=17):
    rnd = random.Random(seed)
    agg = Counter()
    per_file = []
    for fp in rnd.sample(files, sample):
        rel = os.path.relpath(fp, CLIEN)
        try:
            data, img, region = load(fp)
        except Exception:  # noqa: BLE001
            continue
        key = WzKey.for_region(region)
        pay = no_tail = tail_raw = n = 0
        for _p, node in walk(img.root):
            if not isinstance(node, WzCanvasProperty) or not node.has_pixels():
                continue
            if node.format + node.format2 != 2:
                continue
            need = node.width * node.height * 4
            if need == 0:
                continue
            try:
                raw = _decompress(node, key)
            except Exception:  # noqa: BLE001
                continue
            agg["rgb_canvases"] += 1
            if len(raw) <= need:
                agg["no_tail"] += 1
                continue
            tail = raw[need:]
            agg["has_tail"] += 1
            if any(tail):
                agg["tail_nonzero"] += 1
                continue
            agg["tail_all_zero"] += 1
            pay += len(_read_canvas_bytes(node))
            no_tail += len(zlib.compress(raw[:need], 6))
            tail_raw += len(tail)
            n += 1
        if n:
            per_file.append({"file": rel, "canvases": n, "payload_mb": round(pay / 2**20, 3),
                             "without_tail_mb": round(no_tail / 2**20, 3),
                             "tail_raw_mb": round(tail_raw / 2**20, 1),
                             "recoverable_pct": round(100 * (1 - no_tail / max(pay, 1)), 2)})
            agg["measured_payload"] += pay
            agg["measured_without_tail"] += no_tail
            agg["measured_tail_raw"] += tail_raw
    summary = {
        "rgb_canvases": agg["rgb_canvases"],
        "has_tail": agg["has_tail"],
        "tail_all_zero": agg["tail_all_zero"],
        "tail_nonzero": agg["tail_nonzero"],
        "measured_payload_mb": round(agg["measured_payload"] / 2**20, 3),
        "measured_without_tail_mb": round(agg["measured_without_tail"] / 2**20, 3),
        "measured_tail_raw_mb": round(agg["measured_tail_raw"] / 2**20, 1),
        "tail_share_of_compressed_pct": round(
            100 * (1 - agg["measured_without_tail"] / max(agg["measured_payload"], 1)), 3),
    }
    return {"summary": summary, "per_file": per_file}


def main() -> int:
    files = [os.path.join(r, f) for r, _d, fs in os.walk(CLIEN) for f in fs if f.endswith(".img")]
    out = {
        "files_scanned": len(files),
        "probe1_variable_length_refusal": probe1(files),
        "probe2_same_length_inplace": probe2(files),
        "probe3_zero_tail_plane": probe3(files),
    }
    with open(os.path.join(HERE, "structure.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    p1 = out["probe1_variable_length_refusal"]["counts"]
    print("probe1:", p1)
    print("probe2:", [(x["file"].split("/")[-1], x["all_inside_payload"], x["length_unchanged"],
                       x["reparses_clean"]) for x in out["probe2_same_length_inplace"]])
    print("probe3:", out["probe3_zero_tail_plane"]["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
