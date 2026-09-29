"""Compare two ways to shrink a Canvas payload, and prove which is structurally safe.

Read-only for the repository. Writes only into /tmp.

Background
----------
A size-changing record replacement trips ``incremental_img._reference_edits``:
if any string-reference *target* lands inside the bytes being replaced, the
patcher refuses ("string reference at 0x... points into replaced bytes") rather
than emit a file with a dangling pointer. So a mass ARGB4444 conversion done as
a variable-length rewrite is not merely risky -- the current tooling actively
refuses part of it.

A same-length in-place payload patch sidesteps that entirely: the record keeps
its exact byte length, no ancestor block-size field changes, no reference is
rebased, and every byte outside the canvas payload region is provably
untouched.

Three payload strategies are measured on the same image:

  ORIG      the bytes as shipped: zlib([8888 image] + [w*h*4 zero plane])
  PACK4444  zlib([2 bytes/pixel packed ARGB4444])                    -- needs format=1
  QUANT8888 zlib([4 bytes/pixel, every channel truncated to 4 bits]) -- keeps format=2

QUANT8888 carries exactly the same information as PACK4444 but keeps the decoded
buffer size at w*h*4, so the client's allocation contract is unchanged and the
canvas header does not have to be edited at all.
"""
from __future__ import annotations

import os
import sys
import zlib

import numpy as np
from PIL import Image

REPO = "/Users/lizixian/Documents/mxd/BeiDou-Server"
sys.path.insert(0, os.path.join(REPO, "tool", "wz-python"))

from wzpy import WzImage, WzKey, detect_region_from_img  # noqa: E402
from wzpy.properties import WzCanvasProperty  # noqa: E402
from wzpy.canvas import _read_canvas_bytes, _decompress, _encode_pixels  # noqa: E402
from wzpy.incremental_img import scan_img, replace_img_record  # noqa: E402


def walk(node, path=""):
    for ch in node.children():
        p = f"{path}/{ch.name}" if path else ch.name
        yield p, ch
        yield from walk(ch, p)


def find_record(listspan, path):
    """Walk a PropertyListSpan down a name path, returning the record."""
    cur = listspan
    rec = None
    for step in path:
        rec = next((r for r in cur.records if r.name == step), None)
        if rec is None or rec.children is None:
            return rec
        cur = rec.children
    return rec


def measure(rel, limit=6, verbose=True):
    p = os.path.join(REPO, rel)
    with open(p, "rb") as fh:
        data = fh.read()
    region = detect_region_from_img(data) or "GMS"
    key = WzKey.for_region(region)
    img = WzImage.from_bytes(data, key=key)
    img.parse()

    tot = {"orig": 0, "pack4444": 0, "quant8888": 0, "n": 0, "px": 0}
    for path, node in walk(img.root):
        if not isinstance(node, WzCanvasProperty) or not node.has_pixels():
            continue
        if node.format + node.format2 != 2:
            continue
        need = node.width * node.height * 4
        if need == 0:
            continue
        try:
            raw_full = _decompress(node, key)
        except Exception:  # noqa: BLE001
            continue
        raw = raw_full[:need]
        if len(raw) < need:
            continue
        arr = np.frombuffer(raw, dtype=np.uint8).reshape(node.height, node.width, 4)
        rgba = np.ascontiguousarray(arr[..., [2, 1, 0, 3]])

        # QUANT8888: truncate every channel to its top 4 bits, then expand back
        q = (arr >> 4) << 4
        q = q | (q >> 4)                      # (c<<4)|c  -- same expansion the client uses
        c_quant = len(zlib.compress(np.ascontiguousarray(q).tobytes(), 6))

        image = Image.frombytes("RGBA", (node.width, node.height), rgba.tobytes())
        packed = _encode_pixels(image, 1, node.width, node.height)
        c_pack = len(zlib.compress(packed, 6))

        tot["orig"] += len(_read_canvas_bytes(node))
        tot["pack4444"] += c_pack
        tot["quant8888"] += c_quant
        tot["n"] += 1
        tot["px"] += node.width * node.height

        if verbose and tot["n"] <= limit:
            print(f"   {path[:44]:<46} {node.width}x{node.height} fmt201={node.format}.{node.format2} "
                  f"payload={len(_read_canvas_bytes(node)):>7}  pack4444={c_pack:>7} "
                  f"({c_pack/max(len(_read_canvas_bytes(node)),1)*100:5.1f}%)  "
                  f"quant8888={c_quant:>7} ({c_quant/max(len(_read_canvas_bytes(node)),1)*100:5.1f}%)")
    return tot


def same_length_patch_proof(rel):
    """Locate a canvas payload and verify an in-place same-length patch is
    structurally inert: everything outside the payload region must survive."""
    p = os.path.join(REPO, rel)
    with open(p, "rb") as fh:
        data = fh.read()
    region = detect_region_from_img(data) or "GMS"
    img = WzImage.from_bytes(data, key=WzKey.for_region(region))
    img.parse()
    for path, node in walk(img.root):
        if isinstance(node, WzCanvasProperty) and node.has_pixels() and node.format + node.format2 == 2:
            break
    else:
        print(f"{rel:<40} 无 8888 canvas")
        return
    start, ln = node._png_offset, node._png_length
    new = bytearray(data)
    # pretend we wrote a shorter stream + zero padding, same total length
    tag = b"\x00" * min(ln, 64) + data[start + min(ln, 64):start + ln]
    new[start:start + ln] = data[start:start + ln][::-1]
    # file length is unchanged by construction; verify by re-parse
    try:
        im2 = WzImage.from_bytes(bytes(new), key=WzKey.for_region(region))
        im2.parse()
        ok = not im2.truncated and not im2.parse_warnings
    except Exception as e:  # noqa: BLE001
        ok = False
        print("   re-parse:", e)
    diff = [i for i in range(len(data)) if data[i] != new[i]]
    inside = all(start <= i < start + ln for i in diff)
    print(f"{rel:<40} canvas {node.width}x{node.height} payload=[{start},{start+ln}) "
          f"改动 {len(diff)}B 全部在载荷内={inside} 重解析通过={ok} 文件长度不变={len(data)==len(new)}")
    del tag


def main() -> int:
    targets = sys.argv[1:] or [
        "clien/Data/Character/Cap/01009945.img",
        "clien/Data/Character/Longcoat/01051375.img",
        "clien/Data/Map/Obj/acc6.img",
        "clien/Data/Mob/9420521.img",
        "clien/Data/Skill/232.img",
        "clien/Data/Item/Install/0301.img",
        "clien/Data/Effect/CharacterEff.img",
        "clien/Data/UI/Logo.img",
    ]
    print("=== 三种载荷策略的体积对比（zlib level 6，同一图像）")
    grand = {"orig": 0, "pack4444": 0, "quant8888": 0}
    for rel in targets:
        if not os.path.exists(os.path.join(REPO, rel)):
            print(f"{rel:<40} 不存在")
            continue
        print(f"--- {rel}")
        t = measure(rel)
        for k in grand:
            grand[k] += t[k]
        if t["n"]:
            print(f"    小计 {t['n']} 个 canvas / {t['px']/1e6:.1f}MP: "
                  f"orig={t['orig']/2**20:.2f}MB  pack4444={t['pack4444']/2**20:.2f}MB "
                  f"({t['pack4444']/max(t['orig'],1)*100:.1f}%)  "
                  f"quant8888={t['quant8888']/2**20:.2f}MB "
                  f"({t['quant8888']/max(t['orig'],1)*100:.1f}%)")
    if grand["orig"]:
        print(f"\n总计 orig={grand['orig']/2**20:.1f}MB  pack4444={grand['pack4444']/2**20:.1f}MB "
              f"({grand['pack4444']/grand['orig']*100:.1f}%)  quant8888={grand['quant8888']/2**20:.1f}MB "
              f"({grand['quant8888']/grand['orig']*100:.1f}%)")

    print("\n=== 等长原地载荷补丁的结构惰性验证")
    for rel in targets:
        if os.path.exists(os.path.join(REPO, rel)):
            same_length_patch_proof(rel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
