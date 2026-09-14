#!/usr/bin/env python3
"""Remove Damien map info fields and BossDemian back layers that drive Flash."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_demian as demian  # noqa: E402
from migrate_twilight_perion_monster_park import load_checked  # noqa: E402
from wzpy import WzImage, WzIntProperty, WzStringProperty, WzSubProperty  # noqa: E402
from wzpy.incremental_img import mutate_img, replace_img_record  # noqa: E402

MAPS = (350160240, 350160280)
SAFE_FIELD_LIMIT = 34415352
XML_TAG = re.compile(
    r"^[ \t]*<(int|string|float) name=\"("
    + "|".join(sorted(demian.DAMIEN_MAP_INFO_STRIP))
    + r")\"[^>]*/?>\n",
    re.M,
)
EMPTY_BACK_XML = """  <imgdir name="back">
    <imgdir name="0">
      <string name="bS" value=""/>
      <int name="front" value="0"/>
      <int name="ani" value="0"/>
      <int name="no" value="0"/>
      <int name="f" value="0"/>
      <int name="x" value="0"/>
      <int name="y" value="0"/>
      <int name="rx" value="0"/>
      <int name="ry" value="0"/>
      <int name="type" value="0"/>
      <int name="cx" value="0"/>
      <int name="cy" value="0"/>
      <int name="a" value="255"/>
    </imgdir>
  </imgdir>"""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def verify_remove_scope(before: bytes, after: bytes, root: tuple[str, ...]) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)
    if before_orders.get(()) != after_orders.get(()):
        raise RuntimeError("top-level sibling order changed")
    gone = set(before_records) - set(after_records)
    expected_gone = {path for path in before_records if path[: len(root)] == root}
    if gone != expected_gone:
        raise RuntimeError(f"unexpected removals: {sorted(gone)}")
    added = set(after_records) - set(before_records)
    if added:
        raise RuntimeError(f"unexpected additions: {sorted(added)}")
    for path, raw in before_records.items():
        affected = path[: len(root)] == root or root[: len(path)] == path
        if not affected and after_records.get(path) != raw:
            raise RuntimeError(f"protected record changed: {path}")
    for parent, names in before_orders.items():
        if parent[: len(root)] == root:
            continue
        if parent == root[:-1]:
            expected = [name for name in names if name != root[-1]]
            if after_orders.get(parent) != expected:
                raise RuntimeError(f"sibling order changed: {parent}")
            continue
        if after_orders.get(parent) != names:
            raise RuntimeError(f"sibling order changed: {parent}")


def verify_edit_scope(before: bytes, after: bytes, allowed: set[tuple[str, ...]]) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)
    if set(before_records) != set(after_records):
        raise RuntimeError(f"record set changed: {sorted(set(before_records) ^ set(after_records))}")
    for parent, names in before_orders.items():
        if after_orders.get(parent) != names:
            raise RuntimeError(f"sibling order changed: {parent}")
    for path, raw in before_records.items():
        affected = any(path[: len(root)] == root or root[: len(path)] == path for root in allowed)
        if not affected and after_records.get(path) != raw:
            raise RuntimeError(f"protected record changed: {path}")


def strip_client(map_id: int) -> None:
    path = demian.client_map_path(map_id)
    image = load_checked(path, arc.GMS_KEY)
    info = image.root.child("info")
    present = [
        name for name in demian.DAMIEN_MAP_INFO_STRIP
        if info is not None and info.child(name) is not None
    ]
    for name in present:
        original = path.read_bytes()
        patched = mutate_img(original, "remove", ("info", name), region="GMS").data
        verify_remove_scope(original, patched, ("info", name))
        checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=path.name)
        checked.parse()
        if checked.truncated or checked.parse_warnings:
            raise RuntimeError(f"{path.name} parse failed after removing {name}")
        if checked.root.get(f"info/{name}") is not None:
            raise RuntimeError(f"{path.name} still has info/{name}")
        arc.atomic_write_bytes(path, patched)


def empty_back0() -> WzSubProperty:
    node = WzSubProperty("0")
    node.add(WzStringProperty("bS", "", node))
    for name, value in (
        ("front", 0),
        ("ani", 0),
        ("no", 0),
        ("f", 0),
        ("x", 0),
        ("y", 0),
        ("rx", 0),
        ("ry", 0),
        ("type", 0),
        ("cx", 0),
        ("cy", 0),
        ("a", 255),
    ):
        node.add(WzIntProperty(name, value, node))
    return node


def back0_is_empty(node) -> bool:
    if node is None:
        return False
    return (
        str(arc.child_value(node, "bS") or "") == ""
        and int(arc.child_value(node, "ani") or 0) == 0
        and int(arc.child_value(node, "type") or 0) == 0
        and int(arc.child_value(node, "no") or 0) == 0
        and int(arc.child_value(node, "x") or 0) == 0
        and int(arc.child_value(node, "y") or 0) == 0
    )


def strip_extra_backs(map_id: int) -> None:
    path = demian.client_map_path(map_id)
    image = load_checked(path, arc.GMS_KEY)
    names = sorted(
        (int(child.name) for child in image.root.child("back").children() if child.name.isdigit()),
        reverse=True,
    )
    for name in names:
        if name == 0:
            continue
        original = path.read_bytes()
        patched = mutate_img(original, "remove", ("back", str(name)), region="GMS").data
        verify_remove_scope(original, patched, ("back", str(name)))
        checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=path.name)
        checked.parse()
        if checked.truncated or checked.parse_warnings:
            raise RuntimeError(f"{path.name} parse failed after removing back/{name}")
        if checked.root.get(f"back/{name}") is not None:
            raise RuntimeError(f"{path.name} still has back/{name}")
        leftover = [
            int(child.name)
            for child in checked.root.child("back").children()
            if child.name.isdigit()
        ]
        if demian.numeric_gaps(checked.root.child("back")):
            raise RuntimeError(f"{path.name} back gaps after removing {name}: {leftover}")
        arc.atomic_write_bytes(path, patched)


def project_empty_back0(map_id: int) -> None:
    path = demian.client_map_path(map_id)
    original = path.read_bytes()
    image = load_checked(path, arc.GMS_KEY)
    names = tuple(child.name for child in image.root.child("back").children())
    if names == ("0",) and back0_is_empty(image.root.get("back/0")):
        return
    patched = replace_img_record(original, ("back", "0"), empty_back0(), region="GMS").data
    before_records, _before_orders = arc.raw_record_state(original)
    after_records, after_orders = arc.raw_record_state(patched)
    for record_path, raw in before_records.items():
        affected = record_path[:2] == ("back", "0") or record_path == ("back",)
        if not affected and after_records.get(record_path) != raw:
            raise RuntimeError(f"protected record changed: {record_path}")
    if after_orders.get(("back",)) != ["0"]:
        raise RuntimeError(f"{path.name} back order {after_orders.get(('back',))}")
    checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=path.name)
    checked.parse()
    if checked.truncated or checked.parse_warnings:
        raise RuntimeError(f"{path.name} parse failed after emptying back/0")
    if not back0_is_empty(checked.root.get("back/0")):
        raise RuntimeError(f"{path.name} back/0 is not the empty analogue")
    if demian.numeric_gaps(checked.root.child("back")):
        raise RuntimeError(f"{path.name} back gaps after emptying back/0")
    arc.atomic_write_bytes(path, patched)


def align_field_limit(map_id: int) -> None:
    path = demian.client_map_path(map_id)
    image = load_checked(path, arc.GMS_KEY)
    current = int(arc.child_value(image.root.child("info"), "fieldLimit") or 0)
    if current == SAFE_FIELD_LIMIT:
        return
    original = path.read_bytes()
    patched = mutate_img(
        original, "edit", ("info", "fieldLimit"), values={"value": SAFE_FIELD_LIMIT}, region="GMS"
    ).data
    verify_edit_scope(original, patched, {("info", "fieldLimit")})
    checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=path.name)
    checked.parse()
    if checked.truncated or checked.parse_warnings:
        raise RuntimeError(f"{path.name} parse failed after fieldLimit")
    if int(arc.child_value(checked.root.child("info"), "fieldLimit") or 0) != SAFE_FIELD_LIMIT:
        raise RuntimeError(f"{path.name} fieldLimit not aligned")
    arc.atomic_write_bytes(path, patched)


def strip_xml(map_id: int) -> None:
    path = demian.server_map_path("wz", map_id)
    text = path.read_text(encoding="utf-8")
    start = text.find('<imgdir name="info">')
    end = text.find("</imgdir>", start)
    if start < 0 or end < 0:
        raise RuntimeError(f"{path.name} missing info")
    info = text[start:end]
    updated = XML_TAG.sub("", info)
    if updated != info:
        text = text[:start] + updated + text[end:]
    text = text.replace(
        f'<int name="fieldLimit" value="{SAFE_FIELD_LIMIT + 256}"/>',
        f'<int name="fieldLimit" value="{SAFE_FIELD_LIMIT}"/>',
    )
    back_start, back_end = xml_imgdir_span(text, "back")
    if text[back_start:back_end] != EMPTY_BACK_XML:
        text = text[:back_start] + EMPTY_BACK_XML + text[back_end:]
    if text != path.read_text(encoding="utf-8"):
        arc.atomic_write_text(path, text)


def patch_once() -> None:
    for map_id in MAPS:
        strip_client(map_id)
        strip_extra_backs(map_id)
        project_empty_back0(map_id)
        align_field_limit(map_id)
        strip_xml(map_id)


def main() -> int:
    targets = [demian.client_map_path(map_id) for map_id in MAPS]
    targets.extend(demian.server_map_path("wz", map_id) for map_id in MAPS)
    patch_once()
    first = {str(path): sha256_file(path) for path in targets}
    patch_once()
    second = {str(path): sha256_file(path) for path in targets}
    if first != second:
        raise RuntimeError(f"map-info patcher is not idempotent: {first} vs {second}")
    for map_id in MAPS:
        image = load_checked(demian.client_map_path(map_id), arc.GMS_KEY)
        leftover = [
            name for name in demian.DAMIEN_MAP_INFO_STRIP
            if image.root.get(f"info/{name}") is not None
        ]
        if leftover:
            raise RuntimeError(f"{map_id} still has {leftover}")
        back = image.root.child("back")
        names = tuple(child.name for child in back.children())
        if names != ("0",) or not back0_is_empty(back.child("0")):
            raise RuntimeError(f"{map_id} back is not the empty analogue: {names}")
        if demian.numeric_gaps(back):
            raise RuntimeError(f"{map_id} back gaps")
        limit = int(arc.child_value(image.root.child("info"), "fieldLimit") or 0)
        if limit != SAFE_FIELD_LIMIT:
            raise RuntimeError(f"{map_id} fieldLimit {limit}")
    print("damien map-info flash strip ok")
    for path, digest in first.items():
        print(f"{Path(path).relative_to(ROOT)} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
