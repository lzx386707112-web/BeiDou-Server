#!/usr/bin/env python3
"""Project Root Abyss boss resources onto old-client-safe shapes."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

from wzpy import WzCanvasProperty, WzImage, WzSubProperty, WzVectorProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402

from migrate_root_abyss_maps import (  # noqa: E402
    TARGET_KEY,
    atomic_write_bytes,
    clone_property,
    gms_reader,
    patch_server_boss_xml_hp,
    remove_child,
    sanitize_root_abyss_boss_mob,
    write_server_xml_from_client_img,
)


NORMAL_BOSS_MOBS = (
    8900100, 8900101, 8900102, 8900103,
    8910100,
    8920100, 8920101, 8920102, 8920103, 8920104, 8920105, 8920106,
    8930100,
)
ADVANCED_BOSS_MOBS = (
    8900000, 8900001, 8900002, 8900003,
    8910000, 8910001,
    8920000, 8920001, 8920002, 8920003, 8920004, 8920005, 8920006,
    8930000, 8930001,
)

CRIMSON_QUEEN_VISUAL_TEMPLATES = {
    8920100: 8920000,
    8920101: 8920001,
    8920102: 8920002,
    8920103: 8920003,
}
FOOT_ALIGNMENT_MOBS = {8900100, 8910100, 8920100, 8930100}
FOOT_ALIGNMENT_ACTIONS = {"stand", "move"}
FOOT_ALIGNMENT_TEMPLATES = {
    8900000: 8900100,
    8910000: 8910100,
    8920000: 8920100,
    8930000: 8930100,
}


def target_img(path: Path) -> WzImage:
    img = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=path.name)
    img.parse()
    return img


def copy_non_info_children(dst_root: WzSubProperty, src_root: WzSubProperty) -> int:
    changed = 0
    for child in src_root.children():
        if child.name == "info":
            continue
        remove_child(dst_root, child.name)
        dst_root.add(clone_property(child, name=child.name, parent=dst_root))
        changed += 1
    return changed


def template_origin(template: WzSubProperty | None, action_name: str, frame_name: str) -> tuple[int, int] | None:
    if template is None:
        return None
    action = template.child(action_name)
    frame = action.child(frame_name) if isinstance(action, WzSubProperty) else None
    origin = frame.child("origin") if isinstance(frame, WzCanvasProperty) else None
    if isinstance(origin, WzVectorProperty):
        return int(origin.x), int(origin.y)
    return None


def align_visible_feet_to_origin(root: WzSubProperty, template: WzSubProperty | None = None) -> int:
    changed = 0
    for action_name in FOOT_ALIGNMENT_ACTIONS:
        action = root.child(action_name)
        if not isinstance(action, WzSubProperty):
            continue
        for frame in action.children():
            if not isinstance(frame, WzCanvasProperty) or not frame.has_pixels():
                continue
            origin = frame.child("origin")
            image = decode_canvas(frame, region="GMS")
            bbox = image.getbbox()
            if bbox is None:
                continue
            if not isinstance(origin, WzVectorProperty):
                copied = template_origin(template, action_name, frame.name)
                origin_x = copied[0] if copied is not None else int(bbox[0] + ((bbox[2] - bbox[0]) // 2))
                origin = WzVectorProperty("origin", origin_x, int(bbox[3]), frame)
                frame.add(origin)
                changed += 1
                continue
            visible_bottom_delta = int(bbox[3]) - int(origin.y)
            if visible_bottom_delta > 0:
                origin.y += visible_bottom_delta
                changed += 1
    return changed


def patch_mob(mob_id: int) -> str:
    path = ROOT / f"clien/Data/Mob/{mob_id}.img"
    if not path.exists():
        return "missing"

    image = target_img(path)
    template_id = CRIMSON_QUEEN_VISUAL_TEMPLATES.get(mob_id)
    if template_id is not None:
        template = target_img(ROOT / f"clien/Data/Mob/{template_id}.img")
        copy_non_info_children(image.root, template.root)

    sanitize_root_abyss_boss_mob(image.root, mob_id)
    if mob_id in FOOT_ALIGNMENT_MOBS:
        align_visible_feet_to_origin(image.root)
    elif mob_id in FOOT_ALIGNMENT_TEMPLATES:
        template = target_img(ROOT / f"clien/Data/Mob/{FOOT_ALIGNMENT_TEMPLATES[mob_id]}.img")
        align_visible_feet_to_origin(image.root, template.root)
    atomic_write_bytes(path, encode_image_body(image, gms_reader()))

    server_path = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
    write_server_xml_from_client_img(path, server_path)
    patch_server_boss_xml_hp(server_path, mob_id)
    return "write"


def main() -> int:
    counts: dict[str, int] = {}
    for mob_id in (*NORMAL_BOSS_MOBS, *ADVANCED_BOSS_MOBS):
        result = patch_mob(mob_id)
        counts[result] = counts.get(result, 0) + 1
    print(counts)
    return 1 if counts.get("missing") else 0


if __name__ == "__main__":
    raise SystemExit(main())
