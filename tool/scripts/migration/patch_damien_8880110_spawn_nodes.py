#!/usr/bin/env python3
"""Fix 8880110 spawn/attack Flash crashes after the workbench TMS recopy.

Keep firstAttack=0. Stub areaWarning and hit overlays to 1x1. Replace the
28-frame TMS attack1 body with stand/0. Materialize action-body UOLs, keep
speed=0 without move, and give ball-only attack2 a stand/0 body.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_demian as demian  # noqa: E402
import patch_damien_enter_crash as enter_crash  # noqa: E402
import patch_damien_hit_compat as hit_compat  # noqa: E402
from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzSubProperty,
    WzUolProperty,
)
from wzpy.incremental_img import mutate_img, replace_img_record  # noqa: E402

CLIENT = demian.client_mob_path(8880110)
SERVER = demian.server_mob_path(8880110)
WARNINGS = ("attack1", "attack3")
OVERLAYS = ("areaWarning", "hit")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_checked(data: bytes, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{name} parse failed: truncated={image.truncated} warnings={image.parse_warnings}")
    return image


def is_action_root(name: str) -> bool:
    return name in {"hit1", "die1"} or name.startswith("attack") or name.startswith("skill")


def resolve_uol(node: WzUolProperty):
    current = node
    seen: set[int] = set()
    while isinstance(current, WzUolProperty):
        if id(current) in seen or current.parent is None:
            return None
        seen.add(id(current))
        current = current.parent.get(str(current.value))
    return current


def verify_outside(before: bytes, after: bytes, allowed: set[tuple[str, ...]]) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)
    for path, raw in before_records.items():
        affected = any(path[: len(root)] == root or root[: len(path)] == path for root in allowed)
        if not affected and after_records.get(path) != raw:
            raise RuntimeError(f"protected record changed: {path}")
    for path in after_records:
        affected = any(path[: len(root)] == root or root[: len(path)] == path for root in allowed)
        if not affected and path not in before_records:
            raise RuntimeError(f"unapproved record added: {path}")
    for parent, names in before_orders.items():
        affected = any(parent[: len(root)] == root or root[: len(parent)] == parent for root in allowed)
        if affected:
            continue
        current = after_orders.get(parent)
        if current is None:
            raise RuntimeError(f"protected parent removed: {parent}")
        common = set(names).intersection(current)
        if tuple(name for name in names if name in common) != tuple(name for name in current if name in common):
            raise RuntimeError(f"protected sibling order changed: {parent}")


def body_uols(image: WzImage) -> list[tuple[str, WzUolProperty]]:
    found = []
    for action in image.root.children():
        if not is_action_root(action.name) or not isinstance(action, WzSubProperty):
            continue
        for child in action.children():
            if child.name == "info" or not isinstance(child, WzUolProperty):
                continue
            found.append((action.name, child))
    return found


def clone_stand_frame(source: WzCanvasProperty, name: str, image: WzImage, image_path: Path) -> WzCanvasProperty:
    cloned = arc.clone_property(source, None, image, image_path, arc.CanvasMaterializer(), name=name)
    if not isinstance(cloned, WzCanvasProperty):
        raise RuntimeError(f"stand clone for {name} is not a canvas")
    if (int(cloned.format), int(cloned.format2)) != (1, 0):
        raise RuntimeError(f"stand clone {name} is not GMS ARGB4444")
    return cloned


def materialize_body_uols(data: bytes) -> bytes:
    image = parse_checked(data, CLIENT.name)
    pending = body_uols(image)
    while pending:
        action_name, uol = pending[0]
        target = resolve_uol(uol)
        if not isinstance(target, WzCanvasProperty):
            raise RuntimeError(f"unresolved action UOL {action_name}/{uol.name}: {uol.value}")
        cloned = clone_stand_frame(target, uol.name, image, CLIENT)
        patched = replace_img_record(data, (action_name, uol.name), cloned, region="GMS").data
        verify_outside(data, patched, {(action_name, uol.name), (action_name,)})
        parse_checked(patched, CLIENT.name)
        data = patched
        image = parse_checked(data, CLIENT.name)
        pending = body_uols(image)
    return data


def replace_empty_die1(data: bytes) -> bytes:
    image = parse_checked(data, CLIENT.name)
    die0 = image.root.get("die1/0")
    stand0 = image.root.get("stand/0")
    if not isinstance(stand0, WzCanvasProperty):
        raise RuntimeError("8880110 missing stand/0")
    if isinstance(die0, WzCanvasProperty) and int(die0.width) > 1 and int(die0.height) > 1:
        return data
    if die0 is None:
        cloned = clone_stand_frame(stand0, "0", image, CLIENT)
        patched = arc.append_property_record(data, ("die1",), cloned)
        arc.verify_raw_record_insert_scope(data, patched, {("die1", "0")})
        return patched
    cloned = clone_stand_frame(stand0, "0", image, CLIENT)
    patched = replace_img_record(data, ("die1", "0"), cloned, region="GMS").data
    verify_outside(data, patched, {("die1", "0"), ("die1",)})
    return patched


def ensure_attack2_body(data: bytes) -> bytes:
    image = parse_checked(data, CLIENT.name)
    attack2 = image.root.child("attack2")
    if not isinstance(attack2, WzSubProperty):
        raise RuntimeError("8880110 missing attack2")
    frame0 = attack2.child("0")
    if isinstance(frame0, WzCanvasProperty) and int(frame0.width) > 1:
        return data
    stand0 = image.root.get("stand/0")
    cloned = clone_stand_frame(stand0, "0", image, CLIENT)
    if frame0 is None:
        patched = arc.append_property_record(data, ("attack2",), cloned)
        arc.verify_raw_record_insert_scope(data, patched, {("attack2", "0")})
        return patched
    patched = replace_img_record(data, ("attack2", "0"), cloned, region="GMS").data
    verify_outside(data, patched, {("attack2", "0"), ("attack2",)})
    return patched


def patch_client() -> None:
    original = CLIENT.read_bytes()
    image = parse_checked(original, CLIENT.name)
    patched = original

    speed = image.root.get("info/speed")
    if speed is None:
        raise RuntimeError("8880110 missing info/speed")
    if int(speed.value) != demian.STAND_SPEED:
        patched = mutate_img(
            patched, "edit", ("info", "speed"), values={"value": demian.STAND_SPEED}, region="GMS",
        ).data
        arc.verify_raw_record_scope(original, patched, {("info", "speed")}, allow_additions=False)

    checked = parse_checked(patched, CLIENT.name)
    if checked.root.child("move") is not None:
        raise RuntimeError("8880110 unexpectedly has move; do not force speed=0")

    patched = materialize_body_uols(patched)
    patched = ensure_attack2_body(patched)
    patched = replace_empty_die1(patched)
    patched = hit_compat.stub_client_action_body(patched, CLIENT.name, "attack1")
    first_attack = parse_checked(patched, CLIENT.name).root.get("info/firstAttack")
    if first_attack is not None and int(first_attack.value) != 0:
        before = patched
        patched = mutate_img(
            patched, "edit", ("info", "firstAttack"), values={"value": 0}, region="GMS",
        ).data
        arc.verify_raw_record_scope(before, patched, {("info", "firstAttack")}, allow_additions=False)
    parse_checked(patched, CLIENT.name)
    if patched != original:
        arc.atomic_write_bytes(CLIENT, patched)
    for attack in WARNINGS:
        for overlay in OVERLAYS:
            existing = parse_checked(CLIENT.read_bytes(), CLIENT.name).root.get(f"{attack}/info/{overlay}")
            if isinstance(existing, WzSubProperty):
                enter_crash.stub_overlay(8880110, attack, overlay)
        enter_crash.ensure_only_fsm(8880110, attack)


def xml_tag_span(text: str, tag: str, name: str, start_at: int = 0, end_at: int | None = None) -> tuple[int, int]:
    token = f'<{tag} name="{name}"'
    slice_end = len(text) if end_at is None else end_at
    start = text.find(token, start_at, slice_end)
    if start < 0:
        raise RuntimeError(f"XML {tag} {name} not found")
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


def stand_canvas_xml(text: str, stand_name: str, dest_name: str) -> str:
    stand_start, stand_end = xml_imgdir_span(text, "stand")
    start, end = xml_tag_span(text, "canvas", stand_name, stand_start, stand_end)
    block = text[start:end]
    return block.replace(f'name="{stand_name}"', f'name="{dest_name}"', 1)


def replace_xml_uols(text: str) -> str:
    updated = text
    while True:
        token = '<uol name="'
        at = updated.find(token)
        if at < 0:
            break
        name_start = at + len(token)
        name_end = updated.find('"', name_start)
        value_token = 'value="'
        value_start = updated.find(value_token, name_end) + len(value_token)
        value_end = updated.find('"', value_start)
        name = updated[name_start:name_end]
        value = updated[value_start:value_end]
        if not value.startswith("../stand/"):
            raise RuntimeError(f"unexpected UOL {name} -> {value}")
        stand_name = value.rsplit("/", 1)[-1]
        canvas = stand_canvas_xml(updated, stand_name, name)
        line_start = updated.rfind("\n", 0, at) + 1
        indent = updated[line_start:at]
        end = updated.find("/>", at) + 2
        updated = updated[:line_start] + indent + canvas + updated[end:]
    return updated


def replace_xml_die1(text: str) -> str:
    die_start, die_end = xml_imgdir_span(text, "die1")
    try:
        canvas_start, canvas_end = xml_tag_span(text, "canvas", "0", die_start, die_end)
    except RuntimeError:
        return text
    chunk = text[canvas_start:canvas_end]
    if 'width="1"' not in chunk or 'height="1"' not in chunk:
        return text
    replacement = stand_canvas_xml(text, "0", "0")
    return text[:canvas_start] + replacement + text[canvas_end:]


def xml_overlay_is_stub(text: str, attack: str, overlay: str) -> bool:
    attack_start, attack_end = xml_imgdir_span(text, attack)
    try:
        warn_start, warn_end = xml_imgdir_span(text, overlay, attack_start, attack_end)
    except RuntimeError:
        return True
    chunk = text[warn_start:warn_end]
    if '<canvas name="0" width="1" height="1" format="1">' not in chunk:
        return False
    return '<canvas name="1"' not in chunk


def stub_xml_overlay(text: str, attack: str, overlay: str) -> str:
    if xml_overlay_is_stub(text, attack, overlay):
        return text
    attack_start, attack_end = xml_imgdir_span(text, attack)
    warn_start, warn_end = xml_imgdir_span(text, overlay, attack_start, attack_end)
    chunk = text[warn_start:warn_end]
    canvas_start = chunk.find('<canvas name="0"')
    canvas_end = chunk.find("</canvas>", canvas_start)
    if canvas_start < 0 or canvas_end < 0:
        raise RuntimeError(f"XML {attack} {overlay} missing canvas 0")
    canvas_end += len("</canvas>")
    if '<canvas name="0" width="1" height="1"' in chunk[canvas_start:canvas_end]:
        return text[:warn_start] + chunk[:canvas_end] + "\n    </imgdir>" + text[warn_end:]
    stub = (
        f'<imgdir name="{overlay}">\n'
        '        <canvas name="0" width="1" height="1" format="1">\n'
        '          <vector name="origin" x="0" y="0"/>\n'
        '          <int name="delay" value="90"/>\n'
        '        </canvas>\n'
        "    </imgdir>"
    )
    return text[:warn_start] + stub + text[warn_end:]


def set_xml_only_fsm(text: str, attack: str) -> str:
    start, end = xml_imgdir_span(text, attack)
    chunk = text[start:end]
    if 'name="onlyFsm" value="1"' in chunk:
        return text
    if 'name="onlyFsm" value="0"' in chunk:
        chunk = chunk.replace('name="onlyFsm" value="0"', 'name="onlyFsm" value="1"', 1)
        return text[:start] + chunk + text[end:]
    needle = '<int name="attackAfter"'
    at = chunk.find(needle)
    if at < 0:
        raise RuntimeError(f"XML {attack} missing attackAfter")
    line_end = chunk.find("\n", at)
    chunk = chunk[:line_end + 1] + '      <int name="onlyFsm" value="1"/>\n' + chunk[line_end + 1:]
    return text[:start] + chunk + text[end:]


def ensure_xml_attack2_body(text: str) -> str:
    start, end = xml_imgdir_span(text, "attack2")
    chunk = text[start:end]
    if '<canvas name="0"' in chunk:
        return text
    canvas = stand_canvas_xml(text, "0", "0")
    close = text.rfind("</imgdir>", start, end)
    return text[:close] + "    " + canvas + "\n  " + text[close:]


def patch_server() -> None:
    text = SERVER.read_text(encoding="utf-8")
    updated = text.replace('<int name="speed" value="-60"/>', '<int name="speed" value="0"/>', 1)
    if '<int name="speed" value="0"/>' not in updated:
        raise RuntimeError("8880110 XML missing speed=0 after patch")
    if '<int name="firstAttack" value="0"/>' not in updated:
        raise RuntimeError("8880110 XML missing firstAttack=0 after patch")
    updated = replace_xml_uols(updated)
    updated = replace_xml_die1(updated)
    updated = ensure_xml_attack2_body(updated)
    updated = hit_compat.stub_xml_action_body(updated, "attack1")
    for attack in WARNINGS:
        for overlay in OVERLAYS:
            updated = stub_xml_overlay(updated, attack, overlay)
        updated = set_xml_only_fsm(updated, attack)
    if updated != text:
        arc.atomic_write_text(SERVER, updated)


def verify() -> None:
    image = parse_checked(CLIENT.read_bytes(), CLIENT.name)
    if int(arc.child_value(image.root.get("info"), "speed")) != 0:
        raise RuntimeError("client speed is not 0")
    if image.root.child("move") is not None:
        raise RuntimeError("client still must not have move")
    if body_uols(image):
        leftover = [f"{action}/{uol.name}->{uol.value}" for action, uol in body_uols(image)]
        raise RuntimeError(f"action-body UOLs remain: {leftover}")
    attack2_0 = image.root.get("attack2/0")
    if not isinstance(attack2_0, WzCanvasProperty) or int(attack2_0.width) <= 1:
        raise RuntimeError("attack2/0 is not a materialized stand canvas")
    die0 = image.root.get("die1/0")
    if not isinstance(die0, WzCanvasProperty) or int(die0.width) <= 1:
        raise RuntimeError("die1/0 is still a 1x1 stub")
    first_attack = arc.child_value(image.root.get("info"), "firstAttack")
    if first_attack is None or int(first_attack) != 0:
        raise RuntimeError("client firstAttack is not 0")
    if not hit_compat.action_body_already_stubbed(image, "attack1"):
        raise RuntimeError("attack1 body is still the TMS multi-frame set")
    for attack in WARNINGS:
        for overlay in OVERLAYS:
            node = image.root.get(f"{attack}/info/{overlay}")
            if node is None:
                continue
            if not isinstance(node, WzSubProperty) or not enter_crash.overlay_is_stub(node):
                raise RuntimeError(f"{attack}/{overlay} is not a single 1x1 stub")
        only_fsm = image.root.get(f"{attack}/info/onlyFsm")
        if only_fsm is None or int(only_fsm.value) != 1:
            raise RuntimeError(f"{attack} onlyFsm is not 1")
    xml = SERVER.read_text(encoding="utf-8")
    if '<int name="firstAttack" value="0"/>' not in xml:
        raise RuntimeError("XML firstAttack is not 0")
    if "<uol " in xml:
        raise RuntimeError("XML still has UOL action frames")
    if '<int name="speed" value="0"/>' not in xml:
        raise RuntimeError("XML speed is not 0")
    for attack in WARNINGS:
        for overlay in OVERLAYS:
            if not xml_overlay_is_stub(xml, attack, overlay):
                raise RuntimeError(f"XML {attack} {overlay} is not a single 1x1 stub")
        attack_start, attack_end = xml_imgdir_span(xml, attack)
        if 'name="onlyFsm" value="1"' not in xml[attack_start:attack_end]:
            raise RuntimeError(f"XML {attack} onlyFsm is not 1")


def patch_once() -> None:
    patch_client()
    patch_server()
    verify()


def main() -> int:
    patch_once()
    first = {str(path): sha256_file(path) for path in (CLIENT, SERVER)}
    patch_once()
    second = {str(path): sha256_file(path) for path in (CLIENT, SERVER)}
    if first != second:
        raise RuntimeError(f"spawn-node patcher is not idempotent: {first} vs {second}")
    print("damien 8880110 spawn-node patch ok")
    for path, digest in first.items():
        print(f"{Path(path).relative_to(ROOT)} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
