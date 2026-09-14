#!/usr/bin/env python3
"""Project Damien boss actions onto the Lucid/Will-safe frame contract.

Keep skill1 body frames 0-4, drop hide=1 overlays, use a single Hard-Skin skill
slot, strip onlyFsm, replace empty 1x1 action frames with stand UOLs, and replace
TMS attack1 bodies with a raw clone of stand/0. A UOL attack1 lets Cosmos run but
Brandish/Styx ReleaseFlash-crashes; the 43-frame TMS body does the opposite.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_demian as demian  # noqa: E402
import patch_damien_legacy_skill_table as skill_table  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzSubProperty, WzUolProperty  # noqa: E402
from wzpy.incremental_img import (  # noqa: E402
    _apply_edits,
    _find_record,
    _reference_edits,
    _size_edits,
    mutate_img,
    replace_img_record,
    scan_img,
)

STAND_UOL = "../stand/0"
HUGE_BODY_ATTACKS = {
    8880110: ("attack1",),
    8880100: ("attack1",),
    8880111: ("attack1",),
    8880101: ("attack1",),
}
EMPTY_CANVAS = re.compile(
    r'<canvas name="0" width="1" height="1" format="1"(?:/>|></canvas>)',
    re.M,
)
ONLY_FSM = re.compile(r"^[ \t]*<int name=\"onlyFsm\"[^>]*/?>\n", re.M)
SKILL1_HIDE_UOL = re.compile(r'<uol name="([5-9]|10)" value="\.\./skill1/(?:[5-9]|10)"/>')


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_outside(before: bytes, after: bytes, allowed: set[tuple[str, ...]]) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)
    for path, raw in before_records.items():
        affected = any(
            path[: len(root)] == root or root[: len(path)] == path for root in allowed
        )
        if not affected and after_records.get(path) != raw:
            raise RuntimeError(f"protected record changed: {path}")
    for parent, names in before_orders.items():
        affected = any(
            parent[: len(root)] == root or root[: len(parent)] == parent
            for root in allowed
        )
        if not affected and after_orders.get(parent) != names:
            raise RuntimeError(f"protected sibling order changed: {parent}")


def load_client(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=arc.GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{path.name} parse failed: {image.parse_warnings}")
    return image


def hide_frame_names(image: WzImage) -> list[str]:
    skill1 = image.root.child("skill1")
    if not isinstance(skill1, WzSubProperty):
        raise RuntimeError("missing skill1")
    names = []
    for child in skill1.children():
        if not child.name.isdigit():
            continue
        if int(child.name) < 5:
            continue
        names.append(child.name)
    return sorted(names, key=int, reverse=True)


def empty_action_frames(image: WzImage) -> list[tuple[str, str]]:
    found = []
    for action in image.root.children():
        if not isinstance(action, WzSubProperty):
            continue
        if not (
            action.name.startswith("attack")
            or action.name.startswith("skill")
            or action.name in {"hit1", "die1"}
        ):
            continue
        for child in action.children():
            if child.name == "info":
                continue
            if isinstance(child, WzCanvasProperty) and child.width <= 1 and child.height <= 1:
                found.append((action.name, child.name))
    return found


def action_body_frame_names(image: WzImage, action_name: str) -> list[str]:
    action = image.root.child(action_name)
    if not isinstance(action, WzSubProperty):
        raise RuntimeError(f"missing {action_name}")
    names = [child.name for child in action.children() if child.name.isdigit()]
    return sorted(names, key=int, reverse=True)


def action_body_already_stubbed(image: WzImage, action_name: str) -> bool:
    action = image.root.child(action_name)
    stand0 = image.root.get("stand/0")
    frames = [child for child in action.children() if child.name != "info"]
    frame0 = action.child("0")
    return (
        len(frames) == 1
        and isinstance(frame0, WzCanvasProperty)
        and isinstance(stand0, WzCanvasProperty)
        and frame0.name == "0"
        and int(frame0.width) == int(stand0.width)
        and int(frame0.height) == int(stand0.height)
        and frame0.child("delay") is not None
    )


def copy_raw_record(data: bytes, dest_path: tuple[str, ...], source_path: tuple[str, ...]) -> bytes:
    layout = scan_img(data, region="GMS")
    _parent, dest, dest_ancestors = _find_record(layout.root, dest_path)
    _source_parent, source, _source_ancestors = _find_record(layout.root, source_path)
    raw = data[source.start : source.end]
    if data[dest.start : dest.end] == raw:
        return data
    delta = len(raw) - (dest.end - dest.start)
    edits = [(dest.start, dest.end, raw), *_size_edits(dest_ancestors, delta)]
    edits.extend(_reference_edits(layout, edits))
    patched = bytes(_apply_edits(data, edits))
    checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name="patched.img")
    checked.parse()
    if checked.truncated or checked.parse_warnings:
        raise RuntimeError(f"copy {source_path} -> {dest_path} failed: {checked.parse_warnings}")
    return patched


def stub_client_action_body(data: bytes, image_name: str, action_name: str) -> bytes:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=image_name)
    image.parse()
    if action_body_already_stubbed(image, action_name):
        return data
    for name in action_body_frame_names(image, action_name):
        if name == "0":
            continue
        patched = mutate_img(data, "remove", (action_name, name), region="GMS").data
        verify_outside(data, patched, {(action_name, name), (action_name,)})
        data = patched
    patched = copy_raw_record(data, (action_name, "0"), ("stand", "0"))
    verify_outside(data, patched, {(action_name, "0"), (action_name,)})
    return patched


def only_fsm_paths(image: WzImage) -> list[tuple[str, ...]]:
    found = []
    for action in image.root.children():
        node = action.child("info").child("onlyFsm") if action.child("info") is not None else None
        if node is not None:
            found.append((action.name, "info", "onlyFsm"))
    return found


def patch_client_mob(mob_id: int) -> None:
    path = demian.client_mob_path(mob_id)
    data = path.read_bytes()
    image = load_client(path)

    for name in hide_frame_names(image):
        allowed = {("skill1", name), ("skill1",)}
        patched = mutate_img(data, "remove", ("skill1", name), region="GMS").data
        verify_outside(data, patched, allowed)
        data = patched
        image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=path.name)
        image.parse()

    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=path.name)
    image.parse()
    for record in only_fsm_paths(image):
        patched = mutate_img(data, "remove", record, region="GMS").data
        verify_outside(data, patched, {record, record[:2], record[:1]})
        data = patched
        image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=path.name)
        image.parse()

    for action_name, frame_name in empty_action_frames(image):
        uol = WzUolProperty(frame_name, STAND_UOL)
        patched = replace_img_record(
            data, (action_name, frame_name), uol, region="GMS"
        ).data
        verify_outside(data, patched, {(action_name, frame_name), (action_name,)})
        data = patched
        image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=path.name)
        image.parse()

    for action_name in HUGE_BODY_ATTACKS[mob_id]:
        data = stub_client_action_body(data, path.name, action_name)
        image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=path.name)
        image.parse()

    if data != path.read_bytes():
        checked = WzImage.from_bytes(data, key=arc.GMS_KEY, name=path.name)
        checked.parse()
        if checked.truncated or checked.parse_warnings:
            raise RuntimeError(f"{path.name} parse failed after hit-compat patch")
        arc.atomic_write_bytes(path, data)

    skill_table.patch_client_mob(mob_id)


def xml_tag_span(text: str, tag: str, name: str, start_at: int, end_at: int | None = None) -> tuple[int, int]:
    token = f'<{tag} name="{name}"'
    start = text.find(token, start_at, end_at)
    if start < 0:
        raise RuntimeError(f"XML {tag} {name} not found")
    slice_end = len(text) if end_at is None else end_at
    gt = text.find(">", start, slice_end)
    if gt < 0:
        raise RuntimeError(f"XML {tag} {name} is truncated")
    if text[gt - 1] == "/":
        return start, gt + 1
    close = f"</{tag}>"
    depth = 0
    idx = start
    while True:
        next_open = text.find(f"<{tag}", idx, slice_end)
        next_close = text.find(close, idx, slice_end)
        if next_close < 0:
            raise RuntimeError(f"XML {tag} {name} end not found")
        if 0 <= next_open < next_close:
            depth += 1
            idx = next_open + len(tag) + 1
        else:
            depth -= 1
            if depth == 0:
                return start, next_close + len(close)
            idx = next_close + len(close)


def xml_imgdir_span(text: str, name: str, start_at: int = 0, end_at: int | None = None) -> tuple[int, int]:
    return xml_tag_span(text, "imgdir", name, start_at, end_at)


def remove_xml_span(text: str, start: int, end: int) -> str:
    line_start = text.rfind("\n", 0, start) + 1
    return text[:line_start] + text[end:]


def stub_xml_action_body(text: str, action_name: str) -> str:
    stand_start, stand_end = xml_imgdir_span(text, "stand")
    stand_canvas_start, stand_canvas_end = xml_tag_span(text, "canvas", "0", stand_start, stand_end)
    stand_canvas = text[stand_canvas_start:stand_canvas_end]
    action_start, action_end = xml_imgdir_span(text, action_name)
    info_end = xml_imgdir_span(text, "info", action_start, action_end)[1]
    for name in (str(index) for index in range(80, 0, -1)):
        replaced = False
        for tag in ("canvas", "uol"):
            try:
                start, end = xml_tag_span(text, tag, name, info_end, action_end)
            except RuntimeError:
                continue
            text = remove_xml_span(text, start, end)
            action_start, action_end = xml_imgdir_span(text, action_name)
            info_end = xml_imgdir_span(text, "info", action_start, action_end)[1]
            replaced = True
            break
        if not replaced:
            continue
    for tag in ("canvas", "uol"):
        try:
            start, end = xml_tag_span(text, tag, "0", info_end, action_end)
        except RuntimeError:
            continue
        if text[start:end] == stand_canvas:
            return text
        line_start = text.rfind("\n", 0, start) + 1
        indent = text[line_start:start]
        return text[:line_start] + indent + stand_canvas + text[end:]
    raise RuntimeError(f"XML {action_name} missing body frame 0")


def patch_server_mob(mob_id: int) -> None:
    path = demian.server_mob_path("wz", mob_id)
    text = path.read_text(encoding="utf-8")
    updated = ONLY_FSM.sub("", text)
    skill_start, skill_end = xml_imgdir_span(updated, "skill1")
    for name in ("10", "9", "8", "7", "6", "5"):
        try:
            start, end = xml_tag_span(updated, "canvas", name, skill_start, skill_end)
        except RuntimeError:
            continue
        line_start = updated.rfind("\n", 0, start) + 1
        updated = updated[:line_start] + updated[end:]
        if updated[line_start:line_start + 1] == "\n":
            pass
        skill_start, skill_end = xml_imgdir_span(updated, "skill1")
    updated = EMPTY_CANVAS.sub(f'<uol name="0" value="{STAND_UOL}"/>', updated)
    updated = SKILL1_HIDE_UOL.sub(r'<uol name="\1" value="../skill1/4"/>', updated)
    for action_name in HUGE_BODY_ATTACKS[mob_id]:
        updated = stub_xml_action_body(updated, action_name)
    if updated != text:
        import xml.etree.ElementTree as ET

        ET.fromstring(updated)
        arc.atomic_write_text(path, updated)
    skill_table.patch_server_mob(mob_id)


def sync_dependency_mob(boss_id: int, dependency_id: int) -> None:
    skill_table.sync_dependency_mob(boss_id, dependency_id)


def assert_hit_compat(mob_id: int, image: WzImage) -> None:
    skill1 = image.root.child("skill1")
    if not isinstance(skill1, WzSubProperty):
        raise RuntimeError(f"{mob_id} missing skill1")
    names = [child.name for child in skill1.children() if child.name.isdigit()]
    if names != [str(index) for index in range(len(names))] or int(names[-1]) != 4:
        raise RuntimeError(f"{mob_id} skill1 frames {names}")
    for child in skill1.children():
        if isinstance(child, WzCanvasProperty) and child.child("hide") is not None:
            raise RuntimeError(f"{mob_id} skill1/{child.name} kept hide")
        if isinstance(child, WzCanvasProperty) and child.child("delay") is None:
            raise RuntimeError(f"{mob_id} skill1/{child.name} missing delay")
    for path in only_fsm_paths(image):
        raise RuntimeError(f"{mob_id} kept {'/'.join(path)}")
    leftovers = empty_action_frames(image)
    if leftovers:
        raise RuntimeError(f"{mob_id} kept empty canvases {leftovers}")
    for action_name in HUGE_BODY_ATTACKS[mob_id]:
        if not action_body_already_stubbed(image, action_name):
            raise RuntimeError(f"{mob_id} {action_name} still has a TMS body")
    skill_table.assert_legacy_skill_table(mob_id, image)


def patch_all() -> None:
    for mob_id in demian.BOSS_IDS:
        patch_client_mob(mob_id)
        patch_server_mob(mob_id)
    for boss_id, dependency_id in demian.DEPENDENCY_MOB_BY_BOSS.items():
        sync_dependency_mob(boss_id, dependency_id)
        image = load_client(demian.client_mob_path(dependency_id))
        assert_hit_compat(dependency_id, image)
    for mob_id in demian.BOSS_IDS:
        assert_hit_compat(mob_id, load_client(demian.client_mob_path(mob_id)))


def output_paths() -> tuple[Path, ...]:
    paths = []
    for mob_id in (*demian.BOSS_IDS, *demian.DEPENDENCY_MOBS):
        paths.extend((demian.client_mob_path(mob_id), demian.server_mob_path("wz", mob_id)))
    return tuple(paths)


def main() -> int:
    patch_all()
    first = {str(path.relative_to(ROOT)): sha256_file(path) for path in output_paths()}
    patch_all()
    second = {str(path.relative_to(ROOT)): sha256_file(path) for path in output_paths()}
    if first != second:
        raise RuntimeError(f"Damien hit-compat patch is not idempotent: {first} vs {second}")
    print("damien hit-compat patch ok")
    for path, digest in first.items():
        print(f"{path} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
