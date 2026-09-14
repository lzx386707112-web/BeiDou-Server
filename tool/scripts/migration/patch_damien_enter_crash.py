#!/usr/bin/env python3
"""Stop Damien from playing huge overlays on the first in-map attack."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_demian as demian  # noqa: E402
from migrate_twilight_perion_monster_park import load_checked  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzIntProperty, WzSubProperty, WzVectorProperty  # noqa: E402
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.incremental_img import mutate_img, replace_img_record  # noqa: E402

OVERLAYS = (
    (8880110, "attack1", "areaWarning"),
    (8880110, "attack3", "areaWarning"),
    (8880111, "attack1", "effect"),
    (8880111, "attack4", "areaWarning"),
)
ONLY_FSM = (
    (8880110, "attack1"),
    (8880110, "attack3"),
    (8880111, "attack1"),
    (8880111, "attack4"),
)
SKILL_ACTIONS = (
    (8880110, 133, 1),
    (8880111, 133, 1),
    (8880111, 185, 1),
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_overlay_scope(before: bytes, after: bytes, root: tuple[str, ...]) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)
    if before_orders.get(()) != after_orders.get(()):
        raise RuntimeError("top-level sibling order changed")
    for path, raw in before_records.items():
        under = path[: len(root)] == root or root[: len(path)] == path
        if not under and after_records.get(path) != raw:
            raise RuntimeError(f"protected record changed: {path}")
    for path in after_records:
        under = path[: len(root)] == root
        if not under and path not in before_records:
            raise RuntimeError(f"unapproved record added: {path}")


def placeholder_canvas(parent: WzSubProperty) -> WzCanvasProperty:
    pixels = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    canvas = WzCanvasProperty("0", parent)
    canvas.width, canvas.height = 1, 1
    canvas.format = 1
    canvas.format2 = 0
    canvas._png_data = encode_canvas_payload(pixels, 1, 1, 1, key=arc.GMS_KEY, listwz=False, zlib_level=9)
    canvas._png_length = len(canvas._png_data)
    canvas.add(WzVectorProperty("origin", 0, 0, canvas))
    canvas.add(WzIntProperty("delay", 90, canvas))
    pixels.close()
    return canvas


def overlay_is_stub(node: WzSubProperty) -> bool:
    canvases = [child for child in node.children() if isinstance(child, WzCanvasProperty) and child.name.isdigit()]
    return len(canvases) == 1 and canvases[0].width <= 1 and canvases[0].height <= 1


def stub_overlay(mob_id: int, attack: str, overlay: str) -> None:
    path = demian.client_mob_path(mob_id)
    original = path.read_bytes()
    image = load_checked(path, arc.GMS_KEY)
    existing = image.root.get(f"{attack}/info/{overlay}")
    if not isinstance(existing, WzSubProperty):
        raise RuntimeError(f"{path.name} missing {attack}/info/{overlay}")
    if overlay_is_stub(existing):
        return
    node = WzSubProperty(overlay)
    node.add(placeholder_canvas(node))
    updated = replace_img_record(original, (attack, "info", overlay), node, region="GMS").data
    verify_overlay_scope(original, updated, (attack, "info", overlay))
    checked = WzImage.from_bytes(updated, key=arc.GMS_KEY, name=path.name)
    checked.parse()
    if checked.truncated or checked.parse_warnings:
        raise RuntimeError(f"{path.name} parse failed after {attack}/{overlay}")
    stub = checked.root.get(f"{attack}/info/{overlay}")
    if not isinstance(stub, WzSubProperty) or not overlay_is_stub(stub):
        raise RuntimeError(f"{path.name} {attack}/{overlay} stub failed")
    canvas = stub.child("0")
    decoded = decode_canvas(canvas, region="GMS")
    if (int(canvas.format), int(canvas.format2)) != (1, 0):
        raise RuntimeError(f"{path.name} {overlay} is not ARGB4444")
    decoded.close()
    arc.atomic_write_bytes(path, updated)


def ensure_only_fsm(mob_id: int, attack: str) -> None:
    path = demian.client_mob_path(mob_id)
    original = path.read_bytes()
    image = load_checked(path, arc.GMS_KEY)
    record = (attack, "info", "onlyFsm")
    node = image.root.get("/".join(record))
    if node is not None:
        if int(node.value) == 1:
            return
        patched = arc.mutate_img(original, "edit", record, values={"value": 1}, region="GMS").data
        arc.verify_raw_record_scope(original, patched, {record}, allow_additions=False)
    else:
        patched = mutate_img(
            original, "add", (attack, "info"), name="onlyFsm", kind="Int", values={"value": 1}, region="GMS"
        ).data
        arc.verify_raw_record_scope(original, patched, {(attack, "info")}, allow_additions=True)
    checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=path.name)
    checked.parse()
    if checked.truncated or checked.parse_warnings:
        raise RuntimeError(f"{path.name} parse failed after {attack}/onlyFsm")
    arc.atomic_write_bytes(path, patched)


def set_skill_action(mob_id: int, skill_id: int, action: int) -> None:
    path = demian.client_mob_path(mob_id)
    image = load_checked(path, arc.GMS_KEY)
    skill = image.root.get("info/skill")
    index = None
    for child in skill.children():
        if int(arc.child_value(child, "skill") or 0) == skill_id:
            index = child.name
            break
    if index is None:
        raise RuntimeError(f"{path.name} missing skill {skill_id}")
    record = ("info", "skill", index, "action")
    original = path.read_bytes()
    current = image.root.get("/".join(record))
    if current is not None and int(current.value) == action:
        return
    patched = arc.mutate_img(original, "edit", record, values={"value": action}, region="GMS").data
    arc.verify_raw_record_scope(original, patched, {record}, allow_additions=False)
    arc.atomic_write_bytes(path, patched)


def xml_imgdir_span(text: str, name: str, start_at: int = 0) -> tuple[int, int]:
    token = f'<imgdir name="{name}">'
    start = text.find(token, start_at)
    if start < 0:
        raise RuntimeError(f"XML imgdir {name} not found")
    depth = 0
    idx = start
    while True:
        next_open = text.find("<imgdir", idx)
        next_close = text.find("</imgdir>", idx)
        if next_close < 0:
            raise RuntimeError(f"XML imgdir {name} end not found")
        if 0 <= next_open < next_close:
            depth += 1
            idx = next_open + 7
        else:
            depth -= 1
            if depth == 0:
                return start, next_close + len("</imgdir>")
            idx = next_close + 9


def set_xml_only_fsm(mob_id: int, attack: str) -> None:
    xml = demian.server_mob_path("wz", mob_id)
    text = xml.read_text(encoding="utf-8")
    start, end = xml_imgdir_span(text, attack)
    chunk = text[start:end]
    if 'name="onlyFsm" value="1"' in chunk:
        return
    if 'name="onlyFsm" value="0"' in chunk:
        chunk = chunk.replace('name="onlyFsm" value="0"', 'name="onlyFsm" value="1"', 1)
    else:
        needle = '<int name="attackAfter"'
        at = chunk.find(needle)
        if at < 0:
            raise RuntimeError(f"{mob_id} XML {attack} missing attackAfter")
        line_end = chunk.find("\n", at)
        chunk = chunk[:line_end + 1] + '      <int name="onlyFsm" value="1"/>\n' + chunk[line_end + 1:]
    arc.atomic_write_text(xml, text[:start] + chunk + text[end:])


def set_xml_skill_action(mob_id: int, skill_id: int, action: int) -> None:
    xml = demian.server_mob_path("wz", mob_id)
    text = xml.read_text(encoding="utf-8")
    marker = f'<int name="skill" value="{skill_id}"/>'
    skill_at = text.find(marker)
    if skill_at < 0:
        raise RuntimeError(f"{mob_id} XML missing skill {skill_id}")
    action_at = text.find('<int name="action" value="', skill_at)
    action_end = text.find("/>", action_at)
    wanted = f'<int name="action" value="{action}"'
    if text[action_at:action_end] == wanted:
        return
    arc.atomic_write_text(xml, text[:action_at] + wanted + text[action_end:])


def patch_once() -> None:
    for mob_id, attack, overlay in OVERLAYS:
        stub_overlay(mob_id, attack, overlay)
    for mob_id, attack in ONLY_FSM:
        ensure_only_fsm(mob_id, attack)
        set_xml_only_fsm(mob_id, attack)
    for mob_id, skill_id, action in SKILL_ACTIONS:
        set_skill_action(mob_id, skill_id, action)
        set_xml_skill_action(mob_id, skill_id, action)


def main() -> int:
    targets = (
        demian.client_mob_path(8880110),
        demian.client_mob_path(8880111),
        demian.server_mob_path("wz", 8880110),
        demian.server_mob_path("wz", 8880111),
    )
    patch_once()
    first = {str(path): sha256_file(path) for path in targets}
    patch_once()
    second = {str(path): sha256_file(path) for path in targets}
    if first != second:
        raise RuntimeError(f"enter-crash patcher is not idempotent: {first} vs {second}")
    print("damien enter-crash patch ok")
    for path, digest in first.items():
        print(f"{Path(path).relative_to(ROOT)} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
