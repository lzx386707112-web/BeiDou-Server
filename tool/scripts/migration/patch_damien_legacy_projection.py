#!/usr/bin/env python3
"""Project Damien maps/mobs/backs onto old-client field and canvas contracts."""

from __future__ import annotations

import hashlib
import re
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

MAP_IDS = (350160240, 350160280, 105300303, 105300203)
BOSSDEMIAN_BACK = ROOT / "clien/Data/Map/Back/BossDemian.img"
HOFM4_BACK = ROOT / "clien/Data/Map/Back/HofM4.img"
KEEP_ANIMS = {
    8880110: {"info", "stand", "hit1", "die1", "attack1", "attack2", "attack4", "attack5", "attack6"},
    8880111: {"info", "stand", "hit1", "die1", "attack1", "attack2", "attack4", "attack5", "attack6"},
}
XML_INFO = re.compile(
    r"^[ \t]*<(int|string|float) name=\"("
    + "|".join(sorted(demian.DAMIEN_MAP_INFO_STRIP))
    + r")\"[^>]*/?>\n",
    re.M,
)
XML_CANTGO = re.compile(r"^[ \t]*<int name=\"cantGo\"[^>]*/?>\n", re.M)
XML_MOB = re.compile(
    r"^[ \t]*<(int|string|float) name=\"("
    + "|".join(sorted(demian.DAMIEN_MOB_INFO_STRIP))
    + r")\"[^>]*/?>\n",
    re.M,
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_checked(data: bytes, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{name} parse failed")
    return image


def verify_remove_scope(before: bytes, after: bytes, root: tuple[str, ...]) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)
    if before_orders.get(()) != after_orders.get(()):
        raise RuntimeError("top-level sibling order changed")
    gone = set(before_records) - set(after_records)
    if gone != {root}:
        raise RuntimeError(f"unexpected removals for {root}: {sorted(gone)}")
    added = set(after_records) - set(before_records)
    if added:
        raise RuntimeError(f"unexpected additions for {root}: {sorted(added)}")
    for path, raw in before_records.items():
        affected = path[: len(root)] == root or root[: len(path)] == path
        if not affected and after_records.get(path) != raw:
            raise RuntimeError(f"protected record changed: {path}")


def verify_replace_scope(before: bytes, after: bytes, root: tuple[str, ...]) -> None:
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


def placeholder_canvas(parent: WzSubProperty, name: str = "0") -> WzCanvasProperty:
    pixels = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    canvas = WzCanvasProperty(name, parent)
    canvas.width, canvas.height = 1, 1
    canvas.format = 1
    canvas.format2 = 0
    canvas._png_data = encode_canvas_payload(pixels, 1, 1, 1, key=arc.GMS_KEY, listwz=False, zlib_level=9)
    canvas._png_length = len(canvas._png_data)
    canvas.add(WzVectorProperty("origin", 0, 0, canvas))
    canvas.add(WzIntProperty("delay", 90, canvas))
    pixels.close()
    return canvas


def clone_canvas(name: str, source: WzCanvasProperty) -> WzCanvasProperty:
    pixels = decode_canvas(source, region="GMS").convert("RGBA")
    canvas = WzCanvasProperty(name)
    canvas.width, canvas.height = pixels.size
    canvas.format = 1
    canvas.format2 = 0
    canvas._png_data = encode_canvas_payload(
        pixels, 1, *pixels.size, key=arc.GMS_KEY, listwz=False, zlib_level=9
    )
    canvas._png_length = len(canvas._png_data)
    origin = source.child("origin")
    canvas.add(
        WzVectorProperty(
            "origin",
            int(origin.x) if origin is not None else canvas.width // 2,
            int(origin.y) if origin is not None else canvas.height,
            canvas,
        )
    )
    z_node = source.child("z")
    if z_node is not None:
        canvas.add(WzIntProperty("z", int(z_node.value), canvas))
    pixels.close()
    return canvas


def collect_named_paths(node, names: set[str], prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    found: list[tuple[str, ...]] = []
    if not hasattr(node, "children"):
        return found
    for child in node.children():
        path = prefix + (child.name,)
        if child.name in names:
            found.append(path)
        found.extend(collect_named_paths(child, names, path))
    return found


def strip_client_paths(path: Path, names: set[str]) -> None:
    image = load_checked(path, arc.GMS_KEY)
    for record in collect_named_paths(image.root, names):
        original = path.read_bytes()
        patched = mutate_img(original, "remove", record, region="GMS").data
        verify_remove_scope(original, patched, record)
        parse_checked(patched, path.name)
        arc.atomic_write_bytes(path, patched)


def strip_map_xml(map_id: int) -> None:
    path = demian.server_map_path("wz", map_id)
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    updated = XML_INFO.sub("", text)
    updated = XML_CANTGO.sub("", updated)
    if updated != text:
        arc.atomic_write_text(path, updated)


def strip_mob_xml(mob_id: int) -> None:
    path = demian.server_mob_path("wz", mob_id)
    text = path.read_text(encoding="utf-8")
    start = text.find('<imgdir name="info">')
    end = text.find("</imgdir>", start)
    if start < 0 or end < 0:
        raise RuntimeError(f"{path.name} missing info")
    info = text[start:end]
    updated = XML_MOB.sub("", info)
    if updated != info:
        arc.atomic_write_text(path, text[:start] + updated + text[end:])


def anim_is_stub(node: WzSubProperty) -> bool:
    canvases = [
        child for child in node.children()
        if isinstance(child, WzCanvasProperty) and child.name.isdigit()
    ]
    if not canvases:
        return False
    return all(canvas.width <= 1 and canvas.height <= 1 for canvas in canvases)


def stub_animation(mob_id: int, name: str) -> None:
    path = demian.client_mob_path(mob_id)
    original = path.read_bytes()
    image = load_checked(path, arc.GMS_KEY)
    existing = image.root.child(name)
    if not isinstance(existing, WzSubProperty):
        return
    info = existing.child("info")
    if isinstance(info, WzSubProperty):
        patched = original
        for child in list(existing.children()):
            if not isinstance(child, WzCanvasProperty) or not child.name.isdigit():
                continue
            if child.width <= 1 and child.height <= 1:
                continue
            stub = placeholder_canvas(WzSubProperty(name), child.name)
            updated = replace_img_record(patched, (name, child.name), stub, region="GMS").data
            verify_replace_scope(patched, updated, (name, child.name))
            parse_checked(updated, path.name)
            patched = updated
        if patched != original:
            arc.atomic_write_bytes(path, patched)
        return
    if anim_is_stub(existing):
        return
    node = WzSubProperty(name)
    node.add(placeholder_canvas(node))
    updated = replace_img_record(original, (name,), node, region="GMS").data
    verify_replace_scope(original, updated, (name,))
    checked = parse_checked(updated, path.name)
    stub = checked.root.child(name)
    if not isinstance(stub, WzSubProperty) or not anim_is_stub(stub):
        raise RuntimeError(f"{path.name} {name} stub failed")
    canvas = stub.child("0")
    decoded = decode_canvas(canvas, region="GMS")
    if (int(canvas.format), int(canvas.format2)) != (1, 0):
        raise RuntimeError(f"{path.name} {name} is not ARGB4444")
    decoded.close()
    arc.atomic_write_bytes(path, updated)


def stub_unused_anims(mob_id: int) -> None:
    image = load_checked(demian.client_mob_path(mob_id), arc.GMS_KEY)
    keep = KEEP_ANIMS[mob_id]
    for child in list(image.root.children()):
        if child.name in keep or not isinstance(child, WzSubProperty):
            continue
        stub_animation(mob_id, child.name)


def scale_bossdemian_back() -> None:
    original = BOSSDEMIAN_BACK.read_bytes()
    image = load_checked(BOSSDEMIAN_BACK, arc.GMS_KEY)
    source = image.root.get("back/1")
    if not isinstance(source, WzCanvasProperty):
        raise RuntimeError("BossDemian back/1 missing")
    if source.width <= demian.MAX_BACK_WIDTH:
        return
    pixels = decode_canvas(source, region="GMS").convert("RGBA")
    scale = demian.MAX_BACK_WIDTH / source.width
    width = max(1, int(round(source.width * scale)))
    height = max(1, int(round(source.height * scale)))
    scaled = pixels.resize((width, height), Image.Resampling.LANCZOS)
    pixels.close()
    canvas = WzCanvasProperty("1")
    canvas.width, canvas.height = width, height
    canvas.format = 1
    canvas.format2 = 0
    canvas._png_data = encode_canvas_payload(
        scaled, 1, width, height, key=arc.GMS_KEY, listwz=False, zlib_level=9
    )
    canvas._png_length = len(canvas._png_data)
    origin = source.child("origin")
    ox = int(round(int(origin.x) * scale)) if origin is not None else width // 2
    oy = int(round(int(origin.y) * scale)) if origin is not None else height
    canvas.add(WzVectorProperty("origin", ox, oy, canvas))
    z_node = source.child("z")
    if z_node is not None:
        canvas.add(WzIntProperty("z", int(z_node.value), canvas))
    scaled.close()
    updated = replace_img_record(original, ("back", "1"), canvas, region="GMS").data
    verify_replace_scope(original, updated, ("back", "1"))
    checked = parse_checked(updated, BOSSDEMIAN_BACK.name)
    result = checked.root.get("back/1")
    decoded = decode_canvas(result, region="GMS").convert("RGBA")
    if (int(result.format), int(result.format2)) != (1, 0):
        raise RuntimeError("scaled BossDemian back/1 is not ARGB4444")
    if result.width > demian.MAX_BACK_WIDTH or decoded.getbbox() is None:
        raise RuntimeError("scaled BossDemian back/1 failed visibility/size check")
    decoded.close()
    arc.atomic_write_bytes(BOSSDEMIAN_BACK, updated)


def fill_back_gaps(path: Path, template_name: str) -> None:
    original = path.read_bytes()
    image = load_checked(path, arc.GMS_KEY)
    back = image.root.child("back")
    if not isinstance(back, WzSubProperty):
        raise RuntimeError(f"{path.name} missing back")
    names = sorted(int(child.name) for child in back.children() if child.name.isdigit())
    missing = [index for index in range(max(names) + 1) if index not in names]
    if not missing:
        return
    template = back.child(template_name)
    if not isinstance(template, WzCanvasProperty):
        raise RuntimeError(f"{path.name} missing template {template_name}")
    patched = original
    groups: list[list[int]] = []
    for index in missing:
        if not groups or index != groups[-1][-1] + 1:
            groups.append([index])
        else:
            groups[-1].append(index)
    for group in groups:
        anchor = str(next(index for index in names if index > group[-1]))
        props = [clone_canvas(str(index), template) for index in group]
        current = patched
        updated = arc.insert_property_records_before(current, ("back",), props, anchor)
        arc.verify_raw_record_insert_scope(
            current,
            updated,
            {("back", str(index)) for index in group},
        )
        parse_checked(updated, path.name)
        patched = updated
    checked = parse_checked(patched, path.name)
    filled = checked.root.child("back")
    filled_names = sorted(int(child.name) for child in filled.children() if child.name.isdigit())
    leftover = [index for index in range(max(filled_names) + 1) if index not in filled_names]
    if leftover:
        raise RuntimeError(f"{path.name} still has back gaps {leftover}")
    sample = checked.root.get(f"back/{missing[0]}")
    decoded = decode_canvas(sample, region="GMS")
    if (int(sample.format), int(sample.format2)) != (1, 0):
        raise RuntimeError(f"{path.name} filler is not ARGB4444")
    decoded.close()
    arc.atomic_write_bytes(path, patched)


def patch_once() -> None:
    for map_id in MAP_IDS:
        strip_client_paths(
            demian.client_map_path(map_id),
            demian.DAMIEN_MAP_INFO_STRIP | demian.DAMIEN_OBJ_STRIP,
        )
        strip_map_xml(map_id)
    for mob_id in demian.BOSS_IDS:
        strip_client_paths(demian.client_mob_path(mob_id), demian.DAMIEN_MOB_INFO_STRIP)
        strip_mob_xml(mob_id)
        stub_unused_anims(mob_id)
    scale_bossdemian_back()
    fill_back_gaps(BOSSDEMIAN_BACK, "5")
    fill_back_gaps(HOFM4_BACK, "0")


def targets() -> list[Path]:
    paths = [BOSSDEMIAN_BACK, HOFM4_BACK]
    for map_id in MAP_IDS:
        paths.append(demian.client_map_path(map_id))
        xml = demian.server_map_path("wz", map_id)
        if xml.is_file():
            paths.append(xml)
    for mob_id in demian.BOSS_IDS:
        paths.append(demian.client_mob_path(mob_id))
        paths.append(demian.server_mob_path("wz", mob_id))
    return paths


def main() -> int:
    patch_once()
    first = {str(path): sha256_file(path) for path in targets()}
    patch_once()
    second = {str(path): sha256_file(path) for path in targets()}
    if first != second:
        raise RuntimeError(f"legacy projection patcher is not idempotent")
    print("damien legacy projection ok")
    for path, digest in first.items():
        print(f"{Path(path).relative_to(ROOT)} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
