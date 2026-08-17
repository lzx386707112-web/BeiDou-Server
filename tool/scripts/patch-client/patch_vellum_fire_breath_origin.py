#!/usr/bin/env python3
"""Restore Vellum fire-breath frame placement without rewriting Mob IMG trees."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import WzCanvasProperty, WzImage, WzKey, WzVectorProperty  # noqa: E402
from wzpy.writer import encode_compressed_int  # noqa: E402


TARGET_KEY = WzKey.for_region("GMS")
MOB_IDS = (8930100, 8930000)
ACTION = "attack5"
FRAME_RANGE = range(52, 66)
TARGET_ORIGIN_X = 1004
EXPECTED_CURRENT_X = {
    "52": 739,
    "53": 735,
    **{str(frame): 820 for frame in range(54, 66)},
}


def patch_client_img(path: Path) -> int:
    data = bytearray(path.read_bytes())
    image = WzImage.from_bytes(bytes(data), key=TARGET_KEY, name=path.name)
    image.parse()
    if image.parse_warnings:
        raise RuntimeError(f"{path}: parse warnings before patch: {image.parse_warnings}")

    changed = 0
    action = image.root.child(ACTION)
    for frame_num in FRAME_RANGE:
        frame_name = str(frame_num)
        frame = action.child(frame_name)
        if not isinstance(frame, WzCanvasProperty):
            raise RuntimeError(f"{path}: missing {ACTION}/{frame_name} canvas")
        origin = frame.child("origin")
        if not isinstance(origin, WzVectorProperty):
            raise RuntimeError(f"{path}: missing {ACTION}/{frame_name}/origin")

        current_x = int(origin.x)
        expected_x = EXPECTED_CURRENT_X[frame_name]
        if current_x == TARGET_ORIGIN_X:
            continue
        if current_x != expected_x:
            raise RuntimeError(
                f"{path}: unexpected {ACTION}/{frame_name}/origin.x={current_x}, "
                f"expected {expected_x} or {TARGET_ORIGIN_X}"
            )
        if origin._x_offset is None or origin._x_length is None:
            raise RuntimeError(f"{path}: parser did not record {ACTION}/{frame_name}/origin.x offset")

        encoded = encode_compressed_int(TARGET_ORIGIN_X)
        if len(encoded) != int(origin._x_length):
            raise RuntimeError(
                f"{path}: encoded length change for {ACTION}/{frame_name}/origin.x "
                f"{origin._x_length} -> {len(encoded)}"
            )
        start = int(origin._x_offset)
        data[start:start + len(encoded)] = encoded
        changed += 1

    if changed:
        path.write_bytes(data)

    verify = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=path.name)
    verify.parse()
    if verify.parse_warnings:
        raise RuntimeError(f"{path}: parse warnings after patch: {verify.parse_warnings}")
    for frame_num in FRAME_RANGE:
        frame = verify.root.child(ACTION).child(str(frame_num))
        origin = frame.child("origin") if isinstance(frame, WzCanvasProperty) else None
        if not isinstance(origin, WzVectorProperty) or int(origin.x) != TARGET_ORIGIN_X:
            raise RuntimeError(f"{path}: verification failed for {ACTION}/{frame_num}/origin.x")
    return changed


def patch_server_xml(path: Path) -> int:
    text = path.read_text()
    start_marker = f'  <imgdir name="{ACTION}">\n'
    end_marker = '\n  <imgdir name="attack6">'
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        raise RuntimeError(f"{path}: could not isolate {ACTION} block")

    block = text[start:end]
    changed = 0
    for frame_num in FRAME_RANGE:
        frame_name = str(frame_num)
        pattern = re.compile(
            rf'(\s*<canvas name="{frame_name}"[^>]*>\n\s*<vector name="origin" x=")(\d+)(" y="[^"]+"/>)'
        )

        def replace(match: re.Match[str]) -> str:
            nonlocal changed
            current = int(match.group(2))
            if current == TARGET_ORIGIN_X:
                return match.group(0)
            expected = EXPECTED_CURRENT_X[frame_name]
            if current != expected:
                raise RuntimeError(
                    f"{path}: unexpected XML {ACTION}/{frame_name}/origin.x={current}, "
                    f"expected {expected} or {TARGET_ORIGIN_X}"
                )
            changed += 1
            return f"{match.group(1)}{TARGET_ORIGIN_X}{match.group(3)}"

        block, count = pattern.subn(replace, block, count=1)
        if count != 1:
            raise RuntimeError(f"{path}: missing XML {ACTION}/{frame_name}/origin")

    if changed:
        path.write_text(text[:start] + block + text[end:])
    return changed


def main() -> int:
    total_img = 0
    total_xml = 0
    for mob_id in MOB_IDS:
        total_img += patch_client_img(ROOT / f"clien/Data/Mob/{mob_id}.img")
        total_xml += patch_server_xml(ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml")
    print({"img_origin_x": total_img, "xml_origin_x": total_xml})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
