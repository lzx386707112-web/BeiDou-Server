#!/usr/bin/env python3
"""Move Lucid P1 artwork down 50px without changing its server foot point."""

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
BASELINE_CLIENT_SHA256 = "19eb3e121d1b7db402cc46da14c037f81e9b4f30e41e026b786a48fa1083b700"
BASELINE_SERVER_SHA256 = "0983a7b15be4e4c99a75c5a8e75e984d79f5d552927fa4a7719c773b9a8076bd"
POSITION_SHIFT_Y = 50
ACTION_ROOTS = (
    "die1", "skill1", "skill2", "attack2",
    "attack1", "stand", "skill3", "skill4",
)
EXPECTED_FRAME_COUNT = 173

sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import WzCanvasProperty, WzImage, WzKey, WzVectorProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.incremental_img import mutate_img  # noqa: E402


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
    expected_values = {
        path: (x, y - POSITION_SHIFT_Y)
        for path, (x, y) in baseline_values.items()
    }
    if current_values == expected_values:
        return current
    if current_values != baseline_values:
        changed = [
            "/".join(path) for path in baseline_values
            if current_values.get(path) not in (baseline_values[path], expected_values[path])
        ]
        raise RuntimeError(f"unexpected existing Lucid origin edits: {changed[:10]}")

    result = current
    approved = set(baseline_values)
    for path, (x, y) in baseline_values.items():
        result = mutate_img(
            result,
            "edit",
            path,
            values={"x": x, "y": y - POSITION_SHIFT_Y},
            region="GMS",
        ).data
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
    current_values = direct_canvas_origins(current)
    expected_values = {
        path: (x, y - POSITION_SHIFT_Y)
        for path, (x, y) in baseline_values.items()
    }
    if current_values == expected_values:
        return current
    if current_values != baseline_values:
        raise RuntimeError("unexpected existing Lucid server origin edits")

    text = current.decode("utf-8")
    for action in ACTION_ROOTS:
        start, end = block_span(text, action)
        block = text[start:end]
        for (target_action, frame), (x, y) in baseline_values.items():
            if target_action != action:
                continue
            canvas = re.compile(
                rf'(<canvas name="{re.escape(frame)}"[^>]*>.*?'
                rf'<vector name="origin" x="){x}(" y="){y}("/>)',
                re.DOTALL,
            )
            block, count = canvas.subn(
                rf'\g<1>{x}\g<2>{y - POSITION_SHIFT_Y}\g<3>', block, count=1
            )
            if count != 1:
                raise RuntimeError(f"server origin replacement failed: {action}/{frame}")
        text = text[:start] + block + text[end:]
    result = text.encode("utf-8")
    ET.fromstring(result)
    if direct_canvas_origins(result) != expected_values:
        raise RuntimeError("Lucid P1 server origin verification failed")
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
        f"shiftY={POSITION_SHIFT_Y} visible={visible} "
        f"client_sha256={sha256(client_result)} server_sha256={sha256(server_result)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
