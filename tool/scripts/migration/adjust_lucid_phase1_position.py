#!/usr/bin/env python3
"""Maintain Lucid P1's 50px adjustment and complete its idle TMS flower."""

from __future__ import annotations

import hashlib
import importlib.util
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CLIENT = ROOT / "clien/Data/Mob/8880140.img"
SERVER = ROOT / "gms-server/wz/Mob.wz/8880140.img.xml"
CLIENT_GIT_PATH = "clien/Data/Mob/8880140.img"
SERVER_GIT_PATH = "gms-server/wz/Mob.wz/8880140.img.xml"
BASELINE_CLIENT_SHA256 = "ce7c639498db723707040e8d96718161ca5ea8a71ec1050751e8ba70e92d2b41"
BASELINE_SERVER_SHA256 = "51e60848390e16d4f57f3ac3d247063e4fb79e227216357c428b52645e346582"
POSITION_SHIFT_Y = 50
ACTION_ROOTS = (
    "die1", "skill1", "skill2", "attack2",
    "attack1", "stand", "skill3", "skill4",
)
EXPECTED_FRAME_COUNT = 173
FLOWER_STAND_FRAMES = tuple(str(index) for index in range(8))

sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import WzCanvasProperty, WzImage, WzKey, WzVectorProperty  # noqa: E402
from wzpy.canvas import _read_canvas_bytes, decode_canvas  # noqa: E402
from wzpy.incremental_img import replace_img_record  # noqa: E402


ARC_SCRIPT = ROOT / "tool/scripts/migration/migrate_arcane_river_expansion.py"
ARC_SPEC = importlib.util.spec_from_file_location("arcane_river_expansion", ARC_SCRIPT)
if ARC_SPEC is None or ARC_SPEC.loader is None:
    raise RuntimeError(f"cannot import {ARC_SCRIPT}")
arc = importlib.util.module_from_spec(ARC_SPEC)
ARC_SPEC.loader.exec_module(arc)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(path: str) -> bytes:
    result = subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{path}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return result.stdout


def load_image(data: bytes) -> WzImage:
    image = WzImage.from_bytes(data, key=WzKey.for_region("GMS"), name=CLIENT.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"invalid {CLIENT.name}: truncated={image.truncated} "
            f"warnings={image.parse_warnings}"
        )
    return image


def action_origin_values(image: WzImage) -> dict[tuple[str, str, str], tuple[int, int]]:
    output = {}
    for action in ACTION_ROOTS:
        node = image.root.child(action)
        if node is None:
            raise RuntimeError(f"missing Lucid P1 action: {action}")
        for frame in node.children():
            if not isinstance(frame, WzCanvasProperty) or not frame.name.isdigit():
                continue
            origin = frame.child("origin")
            if not isinstance(origin, WzVectorProperty):
                raise RuntimeError(f"missing origin: {action}/{frame.name}")
            output[(action, frame.name, "origin")] = (int(origin.x), int(origin.y))
    if len(output) != EXPECTED_FRAME_COUNT:
        raise RuntimeError(
            f"Lucid P1 action-frame count changed: expected={EXPECTED_FRAME_COUNT} "
            f"actual={len(output)}"
        )
    return output


def patch_client(baseline: bytes, current: bytes) -> bytes:
    baseline_image = load_image(baseline)
    baseline_values = action_origin_values(baseline_image)
    current_values = action_origin_values(load_image(current))
    position_only_values = dict(baseline_values)
    expected_values = dict(position_only_values)
    for frame in FLOWER_STAND_FRAMES:
        expected_values[("stand", frame, "origin")] = position_only_values[
            ("die1", frame, "origin")
        ]
    if current_values not in (baseline_values, position_only_values, expected_values):
        changed = [
            "/".join(path) for path in baseline_values
            if current_values.get(path) not in (
                baseline_values[path], position_only_values[path], expected_values[path]
            )
        ]
        raise RuntimeError(f"unexpected existing Lucid origin edits: {changed[:10]}")

    result = current
    image = load_image(result)
    for frame in FLOWER_STAND_FRAMES:
        source = image.root.get(f"die1/{frame}")
        target = image.root.get(f"stand/{frame}")
        if not isinstance(source, WzCanvasProperty) or not isinstance(
                target, WzCanvasProperty):
            raise RuntimeError(f"missing Lucid flower source frame: die1/{frame}")
        source_origin = source.child("origin")
        target_origin = target.child("origin")
        if not isinstance(source_origin, WzVectorProperty) or not isinstance(
                target_origin, WzVectorProperty):
            raise RuntimeError(f"missing Lucid flower origin: {frame}")
        target.width = source.width
        target.height = source.height
        target.format = source.format
        target.format2 = source.format2
        target._png_data = _read_canvas_bytes(source)
        target._png_length = len(target._png_data)
        target._png_offset = 0
        target_origin.x = source_origin.x
        target_origin.y = source_origin.y
        result = replace_img_record(
            result, ("stand", frame), target, region="GMS"
        ).data

    approved = {("stand", frame) for frame in FLOWER_STAND_FRAMES}
    arc.verify_raw_record_scope(current, result, approved, allow_additions=False)
    if action_origin_values(load_image(result)) != expected_values:
        raise RuntimeError("Lucid P1 client origin verification failed")
    return result


def direct_canvas_origins(xml_data: bytes) -> dict[tuple[str, str], tuple[int, int]]:
    root = ET.fromstring(xml_data)
    output = {}
    for action in ACTION_ROOTS:
        action_node = root.find(f'./imgdir[@name="{action}"]')
        if action_node is None:
            raise RuntimeError(f"missing server Lucid action: {action}")
        for frame in action_node.findall("./canvas"):
            frame_name = frame.get("name", "")
            if not frame_name.isdigit():
                continue
            origin = frame.find('./vector[@name="origin"]')
            if origin is None:
                raise RuntimeError(f"missing server origin: {action}/{frame_name}")
            output[(action, frame_name)] = (
                int(origin.get("x", "0")), int(origin.get("y", "0"))
            )
    if len(output) != EXPECTED_FRAME_COUNT:
        raise RuntimeError(
            f"server Lucid action-frame count changed: expected={EXPECTED_FRAME_COUNT} "
            f"actual={len(output)}"
        )
    return output


def block_span(text: str, action: str) -> tuple[int, int]:
    start_match = re.search(rf'^  <imgdir name="{re.escape(action)}">$', text, re.MULTILINE)
    if start_match is None:
        raise RuntimeError(f"cannot locate XML action block: {action}")
    token = re.compile(r"<imgdir\b|</imgdir>")
    depth = 0
    for match in token.finditer(text, start_match.start()):
        if match.group() == "<imgdir":
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return start_match.start(), match.end()
    raise RuntimeError(f"unterminated XML action block: {action}")


def patch_server(baseline: bytes, current: bytes) -> bytes:
    baseline_values = direct_canvas_origins(baseline)
    expected_values = dict(baseline_values)
    for frame in FLOWER_STAND_FRAMES:
        expected_values[("stand", frame)] = baseline_values[("die1", frame)]

    baseline_root = ET.fromstring(baseline)
    text = baseline.decode("utf-8")
    die_start, die_end = block_span(text, "die1")
    stand_start, stand_end = block_span(text, "stand")
    stand_block = text[stand_start:stand_end]
    for frame in FLOWER_STAND_FRAMES:
        source = baseline_root.find(f'./imgdir[@name="die1"]/canvas[@name="{frame}"]')
        target = baseline_root.find(f'./imgdir[@name="stand"]/canvas[@name="{frame}"]')
        if source is None or target is None:
            raise RuntimeError(f"missing server flower Canvas: {frame}")
        source_origin = source.find('./vector[@name="origin"]')
        target_origin = target.find('./vector[@name="origin"]')
        if source_origin is None or target_origin is None:
            raise RuntimeError(f"missing server flower origin: {frame}")
        canvas_pattern = re.compile(
            rf'(<canvas name="{frame}" width="){target.get("width")}'
            rf'(" height="){target.get("height")}(" format="[^"]+">)'
        )
        stand_block, count = canvas_pattern.subn(
            rf'\g<1>{source.get("width")}\g<2>{source.get("height")}\g<3>',
            stand_block,
            count=1,
        )
        if count != 1:
            raise RuntimeError(f"server stand dimensions failed: stand/{frame}")
        origin_pattern = re.compile(
            rf'(<canvas name="{frame}"[^>]*>.*?<vector name="origin" x=")'
            rf'{target_origin.get("x")}(" y="){target_origin.get("y")}("/>)',
            re.DOTALL,
        )
        stand_block, count = origin_pattern.subn(
            rf'\g<1>{source_origin.get("x")}\g<2>{source_origin.get("y")}\g<3>',
            stand_block,
            count=1,
        )
        if count != 1:
            raise RuntimeError(f"server stand origin failed: stand/{frame}")
    text = text[:stand_start] + stand_block + text[stand_end:]
    result = text.encode("utf-8")
    ET.fromstring(result)
    if direct_canvas_origins(result) != expected_values:
        raise RuntimeError("Lucid P1 server origin verification failed")
    if current not in (baseline, result):
        raise RuntimeError("unexpected existing Lucid server XML edits")
    return result


def verify_visible_canvases(data: bytes) -> int:
    image = load_image(data)
    visible = 0
    for action, frame, _ in action_origin_values(image):
        canvas = image.root.get(f"{action}/{frame}")
        decoded = decode_canvas(canvas, region="GMS").convert("RGBA")
        if decoded.getbbox() is None:
            decoded.close()
            raise RuntimeError(f"empty Lucid P1 action frame: {action}/{frame}")
        decoded.close()
        visible += 1
    return visible


def main() -> int:
    baseline_client = git_blob(CLIENT_GIT_PATH)
    baseline_server = git_blob(SERVER_GIT_PATH)
    if sha256(baseline_client) != BASELINE_CLIENT_SHA256:
        raise RuntimeError("unexpected Git baseline for client 8880140.img")
    if sha256(baseline_server) != BASELINE_SERVER_SHA256:
        raise RuntimeError("unexpected Git baseline for server 8880140.img.xml")

    client_result = patch_client(baseline_client, CLIENT.read_bytes())
    server_result = patch_server(baseline_server, SERVER.read_bytes())
    visible = verify_visible_canvases(client_result)
    if client_result != CLIENT.read_bytes():
        arc.atomic_write_bytes(CLIENT, client_result)
    if server_result != SERVER.read_bytes():
        arc.atomic_write_bytes(SERVER, server_result)
    print(
        f"Lucid P1 position adjusted: frames={EXPECTED_FRAME_COUNT} "
        f"shiftY={POSITION_SHIFT_Y} flowerStand={len(FLOWER_STAND_FRAMES)} "
        f"visible={visible} "
        f"client_sha256={sha256(client_result)} server_sha256={sha256(server_result)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
