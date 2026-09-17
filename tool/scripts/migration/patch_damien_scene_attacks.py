#!/usr/bin/env python3
"""Enable Damien flying knives, ground burst, and scene skills on the old client."""

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
from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.incremental_img import replace_img_record  # noqa: E402

CLIENT_EFFECT = ROOT / "clien/Data/Map/Effect.img"
EFFECT_ANCHOR = "customBossSeren"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clone_canvas(name: str, parent: WzSubProperty, source: WzCanvasProperty, *, with_bounds: bool) -> WzCanvasProperty:
    pixels = decode_canvas(source, region="GMS").convert("RGBA")
    canvas = WzCanvasProperty(name, parent)
    canvas.width, canvas.height = pixels.size
    canvas.format = 1
    canvas.format2 = 0
    canvas._png_data = encode_canvas_payload(
        pixels, 1, *pixels.size, key=arc.GMS_KEY, listwz=False, zlib_level=6
    )
    canvas._png_length = len(canvas._png_data)
    origin = source.child("origin")
    ox = int(origin.x) if origin is not None else canvas.width // 2
    oy = int(origin.y) if origin is not None else canvas.height
    canvas.add(WzVectorProperty("origin", ox, oy, canvas))
    delay = source.child("delay")
    canvas.add(WzIntProperty("delay", int(delay.value) if delay is not None else 90, canvas))
    if with_bounds:
        canvas.add(WzVectorProperty("head", 0, min(-20, -oy + 40), canvas))
        canvas.add(WzVectorProperty("lt", -ox, -oy, canvas))
        canvas.add(WzVectorProperty("rb", canvas.width - ox, canvas.height - oy, canvas))
    z_node = source.child("z")
    if z_node is not None:
        canvas.add(WzIntProperty("z", int(z_node.value), canvas))
    pixels.close()
    return canvas


def visible_frames(node) -> list[WzCanvasProperty]:
    frames = []
    if node is None:
        return frames
    for child in node.children():
        if isinstance(child, WzCanvasProperty) and child.width > 1 and child.height > 1:
            frames.append(child)
    return frames


def build_effect_node() -> WzSubProperty:
    p1 = load_checked(demian.client_mob_path(8880110), arc.GMS_KEY)
    p2 = load_checked(demian.client_mob_path(8880111), arc.GMS_KEY)
    root = WzSubProperty("customBossDemian")
    ground = WzSubProperty("groundBurst", root)
    scene = WzSubProperty("scene", root)
    root.add(ground)
    root.add(scene)
    ground_src = visible_frames(p1.root.get("attack1/info/areaWarning"))[:24]
    scene_src = visible_frames(p2.root.get("skillAfter3"))[:16]
    if len(ground_src) < 8:
        raise RuntimeError("P1 attack1 areaWarning has too few visible frames")
    if len(scene_src) < 6:
        raise RuntimeError("P2 skillAfter3 has too few scene frames")
    for index, source in enumerate(ground_src):
        ground.add(clone_canvas(str(index), ground, source, with_bounds=True))
    for index, source in enumerate(scene_src):
        scene.add(clone_canvas(str(index), scene, source, with_bounds=True))
    return root


def verify_outside(before: bytes, after: bytes, allowed: set[tuple[str, ...]]) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)
    for path, raw in before_records.items():
        affected = any(path[: len(root)] == root or root[: len(path)] == path for root in allowed)
        if not affected and after_records.get(path) != raw:
            raise RuntimeError(f"protected record changed: {path}")
    for parent, names in before_orders.items():
        if any(parent[: len(root)] == root for root in allowed):
            continue
        if after_orders.get(parent) != names:
            raise RuntimeError(f"protected sibling order changed: {parent}")


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


def replace_skill_table(mob_id: int, entries: tuple[dict, ...]) -> None:
    client = demian.client_mob_path(mob_id)
    original = client.read_bytes()
    image = load_checked(client, arc.GMS_KEY)
    current = []
    skill_node = image.root.get("info/skill")
    for child in skill_node.children():
        if not child.name.isdigit():
            continue
        record = {}
        for name in ("skill", "action", "level", "effectAfter", "skillForbid", "stopByBind", "onlyFsm", "skillAfter"):
            node = child.child(name)
            if node is not None:
                record[name] = int(node.value)
        current.append(record)
    skill = WzSubProperty("skill")
    for index, entry in enumerate(entries):
        record = WzSubProperty(str(index), skill)
        for name, value in entry.items():
            record.add(WzIntProperty(name, int(value), record))
        skill.add(record)
    if current != list(entries):
        updated = replace_img_record(original, ("info", "skill"), skill, region="GMS").data
        verify_outside(original, updated, {("info", "skill")})
        checked = WzImage.from_bytes(updated, key=arc.GMS_KEY, name=client.name)
        checked.parse()
        if checked.truncated or checked.parse_warnings:
            raise RuntimeError(f"{mob_id} skill table parse failed")
        arc.atomic_write_bytes(client, updated)
    xml = demian.server_mob_path("wz", mob_id)
    text = xml.read_text(encoding="utf-8")
    start, end = xml_imgdir_span(text, "skill")
    line_start = text.rfind("\n", 0, start) + 1
    fragment = arc.property_to_xml(skill, indent=2)
    if text[line_start:end] != fragment:
        arc.atomic_write_text(xml, text[:line_start] + fragment + text[end:])


def opaque_stub_canvas(parent: WzSubProperty) -> WzCanvasProperty:
    pixels = Image.new("RGBA", (1, 1), (255, 255, 255, 255))
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


def action_is_stub(node: WzSubProperty) -> bool:
    frames = [child for child in node.children() if isinstance(child, WzCanvasProperty) and child.name.isdigit()]
    return len(frames) == 1 and frames[0].width == 1 and frames[0].height == 1


def stub_unsafe_action(mob_id: int, name: str) -> None:
    path = demian.client_mob_path(mob_id)
    original = path.read_bytes()
    image = load_checked(path, arc.GMS_KEY)
    source = image.root.child(name)
    if not isinstance(source, WzSubProperty):
        raise RuntimeError(f"{path.name} missing {name}")
    if action_is_stub(source):
        return
    action = WzSubProperty(name)
    info = source.child("info")
    if isinstance(info, WzSubProperty):
        action.add(arc.clone_property(info, action, image, path, arc.CanvasMaterializer()))
    action.add(opaque_stub_canvas(action))
    updated = replace_img_record(original, (name,), action, region="GMS").data
    verify_outside(original, updated, {(name,)})
    checked = WzImage.from_bytes(updated, key=arc.GMS_KEY, name=path.name)
    checked.parse()
    if checked.truncated or checked.parse_warnings:
        raise RuntimeError(f"{path.name} parse failed after stubbing {name}")
    if not action_is_stub(checked.root.child(name)):
        raise RuntimeError(f"{path.name} {name} stub failed")
    arc.atomic_write_bytes(path, updated)


def stub_unsafe_actions() -> None:
    for mob_id, names in demian.STUB_ACTIONS.items():
        for name in names:
            stub_unsafe_action(mob_id, name)
    for source_id, dest_id in ((8880110, 8880100), (8880111, 8880101)):
        source = demian.client_mob_path(source_id).read_bytes()
        dest = demian.client_mob_path(dest_id)
        if dest.read_bytes() != source:
            arc.atomic_write_bytes(dest, source)


def set_int_img(path: Path, record_path: tuple[str, ...], value: int) -> None:
    original = path.read_bytes()
    image = load_checked(path, arc.GMS_KEY)
    node = image.root.get("/".join(record_path))
    if node is None:
        raise RuntimeError(f"{path.name} missing {'/'.join(record_path)}")
    if int(node.value) == value:
        return
    patched = arc.mutate_img(original, "edit", record_path, values={"value": value}, region="GMS").data
    arc.verify_raw_record_scope(original, patched, {record_path}, allow_additions=False)
    checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=path.name)
    checked.parse()
    if checked.truncated or checked.parse_warnings:
        raise RuntimeError(f"{path.name} parse failed after {record_path}")
    arc.atomic_write_bytes(path, patched)


def add_int_if_missing(patched: bytes, image: WzImage, parent: tuple[str, ...], name: str, value: int) -> bytes:
    node = image.root.get("/".join(parent))
    existing = node.child(name) if node is not None else None
    if existing is not None:
        if int(existing.value) == value:
            return patched
        return arc.mutate_img(patched, "edit", (*parent, name), values={"value": value}, region="GMS").data
    before = patched
    patched = arc.mutate_img(
        patched, "add", parent, name=name, kind="Int", values={"value": value}, region="GMS"
    ).data
    arc.verify_raw_record_insert_scope(before, patched, {(*parent, name)})
    return patched


def ensure_p1_knives() -> None:
    client = demian.client_mob_path(8880110)
    original = client.read_bytes()
    image = load_checked(client, arc.GMS_KEY)
    info = image.root.get("attack2/info")
    pose = image.root.get("attack2/0")
    complete = (
        info.child("ball") is not None
        and int(arc.child_value(info, "type") or 0) == 2
        and info.child("bulletSpeed") is not None
        and info.child("hit") is not None
        and info.child("hit").child("attach") is not None
        and isinstance(pose, WzCanvasProperty)
        and pose.width > 1
    )
    patched = original
    if not complete:
        p2 = load_checked(demian.client_mob_path(8880111), arc.GMS_KEY)
        src_ball = p2.root.get("attack3/info/ball")
        if info.child("ball") is None:
            ball = WzSubProperty("ball")
            frames = visible_frames(src_ball)
            if len(frames) < 4:
                raise RuntimeError("P2 attack3 ball has too few frames")
            for child in frames:
                ball.add(clone_canvas(child.name, ball, child, with_bounds=False))
            patched = arc.append_property_record(patched, ("attack2", "info"), ball)
            arc.verify_raw_record_insert_scope(original, patched, {("attack2", "info", "ball")})
        image = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=client.name)
        image.parse()
        patched = add_int_if_missing(patched, image, ("attack2", "info"), "type", 2)
        image = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=client.name)
        image.parse()
        patched = add_int_if_missing(patched, image, ("attack2", "info"), "bulletSpeed", 300)
        image = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=client.name)
        image.parse()
        patched = add_int_if_missing(patched, image, ("attack2", "info", "hit"), "attach", 1)
        image = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=client.name)
        image.parse()
        pose = image.root.get("attack2/0")
        if isinstance(pose, WzCanvasProperty) and pose.width <= 1:
            stand = image.root.get("stand/0")
            if not isinstance(stand, WzCanvasProperty):
                raise RuntimeError("P1 stand/0 missing for knife pose")
            cloned = clone_canvas("0", WzSubProperty("attack2"), stand, with_bounds=True)
            before = patched
            patched = replace_img_record(patched, ("attack2", "0"), cloned, region="GMS").data
            verify_outside(before, patched, {("attack2", "0")})
        checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=client.name)
        checked.parse()
        if checked.truncated or checked.parse_warnings:
            raise RuntimeError("8880110 knives parse failed")
        info = checked.root.get("attack2/info")
        if (
            info.child("ball") is None
            or int(arc.child_value(info, "type") or 0) != 2
            or info.child("bulletSpeed") is None
            or info.child("hit") is None
            or info.child("hit").child("attach") is None
        ):
            raise RuntimeError("P1 attack2 ballistic incomplete after patch")
        if patched != client.read_bytes():
            arc.atomic_write_bytes(client, patched)

    xml = demian.server_mob_path("wz", 8880110)
    text = xml.read_text(encoding="utf-8")
    start, end = xml_imgdir_span(text, "attack2")
    chunk = text[start:end]
    updated_chunk = chunk
    if "<imgdir name=\"ball\">" not in chunk:
        p2_xml = demian.server_mob_path("wz", 8880111).read_text(encoding="utf-8")
        attack3_start = p2_xml.find('<imgdir name="attack3">')
        ball_start, ball_end = xml_imgdir_span(p2_xml, "ball", attack3_start)
        line_start = p2_xml.rfind("\n", 0, ball_start) + 1
        ball_xml = p2_xml[line_start:ball_end]
        needle = '      <int name="attackAfter" value="30"/>\n      <int name="onlyFsm" value="1"/>'
        if needle not in chunk:
            raise RuntimeError("8880110 XML attack2 needle missing")
        updated_chunk = chunk.replace(
            needle,
            ball_xml + "\n      <int name=\"attackAfter\" value=\"480\"/>\n"
            '      <int name="onlyFsm" value="1"/>\n'
            '      <int name="type" value="2"/>\n'
            '      <int name="bulletSpeed" value="300"/>',
            1,
        )
    misplaced_attach = (
        '        <int name="attach" value="1"/>\n      </imgdir>\n      <int name="attackAfter"'
    )
    if misplaced_attach in updated_chunk:
        updated_chunk = updated_chunk.replace(
            misplaced_attach,
            '      </imgdir>\n      <int name="attackAfter"',
            1,
        )
    hit_start = updated_chunk.find('<imgdir name="hit">')
    ball_at = updated_chunk.find('<imgdir name="ball">')
    hit_chunk = updated_chunk[hit_start:ball_at if ball_at > hit_start else len(updated_chunk)]
    if 'name="attach"' not in hit_chunk:
        if '</imgdir>\n<imgdir name="ball">' in updated_chunk:
            updated_chunk = updated_chunk.replace(
                '      </imgdir>\n<imgdir name="ball">',
                '        <int name="attach" value="1"/>\n      </imgdir>\n<imgdir name="ball">',
                1,
            )
        else:
            updated_chunk = updated_chunk.replace(
                '      </imgdir>\n      <imgdir name="ball">',
                '        <int name="attach" value="1"/>\n      </imgdir>\n      <imgdir name="ball">',
                1,
            )
    if 'name="onlyFsm" value="0"' in updated_chunk:
        updated_chunk = updated_chunk.replace('name="onlyFsm" value="0"', 'name="onlyFsm" value="1"', 1)
    if 'width="1" height="1"' in updated_chunk:
        client_image = load_checked(client, arc.GMS_KEY)
        pose = client_image.root.get("attack2/0")
        if isinstance(pose, WzCanvasProperty) and pose.width > 1:
            updated_chunk = updated_chunk.replace(
                '<canvas name="0" width="1" height="1" format="1"></canvas>',
                arc.property_to_xml(pose, indent=2),
                1,
            )
    if updated_chunk != chunk:
        arc.atomic_write_text(xml, text[:start] + updated_chunk + text[end:])


def restore_only_fsm(mob_id: int, attack: str) -> None:
    client = demian.client_mob_path(mob_id)
    path = (attack, "info", "onlyFsm")
    image = load_checked(client, arc.GMS_KEY)
    node = image.root.get("/".join(path))
    if node is None:
        return
    set_int_img(client, path, 1)
    xml = demian.server_mob_path("wz", mob_id)
    text = xml.read_text(encoding="utf-8")
    start, end = xml_imgdir_span(text, attack)
    chunk = text[start:end]
    if 'name="onlyFsm" value="0"' in chunk:
        chunk2 = chunk.replace('name="onlyFsm" value="0"', 'name="onlyFsm" value="1"', 1)
        arc.atomic_write_text(xml, text[:start] + chunk2 + text[end:])


def is_video_marker(node) -> bool:
    frames = visible_frames(node)
    return (
        len(frames) == 1
        and frames[0].width == 7
        and frames[0].height == 5
        and int(frames[0].format) == 1
        and int(frames[0].format2) == 0
    )


def patch_effect() -> None:
    """Do not restore huge customBossDemian canvases; MCV export owns that node."""
    image = load_checked(CLIENT_EFFECT, arc.GMS_KEY)
    existing = image.root.child("customBossDemian")
    if not isinstance(existing, WzSubProperty):
        return
    if is_video_marker(existing.child("scene")) and (
        is_video_marker(existing.child("groundBurst"))
        or (
            existing.child("groundBurst") is not None
            and len(visible_frames(existing.child("groundBurst"))) >= 8
        )
    ):
        return
    raise RuntimeError(
        "customBossDemian overlays must not be restored; Damien MCV playback was removed"
    )


def main() -> int:
    patch_effect()
    ensure_p1_knives()
    restore_only_fsm(8880110, "attack2")
    restore_only_fsm(8880111, "attack3")
    replace_skill_table(8880110, demian.SKILLS_BY_MOB[8880110])
    replace_skill_table(8880111, demian.SKILLS_BY_MOB[8880111])
    stub_unsafe_actions()
    targets = (
        demian.client_mob_path(8880100),
        demian.client_mob_path(8880101),
        demian.client_mob_path(8880110),
        demian.client_mob_path(8880111),
        demian.server_mob_path("wz", 8880110),
        demian.server_mob_path("wz", 8880111),
    )
    first = {str(path): sha256_file(path) for path in targets}
    ensure_p1_knives()
    restore_only_fsm(8880110, "attack2")
    restore_only_fsm(8880111, "attack3")
    replace_skill_table(8880110, demian.SKILLS_BY_MOB[8880110])
    replace_skill_table(8880111, demian.SKILLS_BY_MOB[8880111])
    stub_unsafe_actions()
    second = {str(path): sha256_file(path) for path in targets}
    if first != second:
        raise RuntimeError(f"damien scene patcher is not idempotent: {first} vs {second}")
    print("damien scene/knives/ground patch ok")
    for path, digest in first.items():
        print(f"{Path(path).relative_to(ROOT)} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
