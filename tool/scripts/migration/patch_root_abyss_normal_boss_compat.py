#!/usr/bin/env python3
"""Project Root Abyss boss resources onto old-client-safe shapes."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

from wzpy import WzCanvasProperty, WzImage, WzSubProperty, WzVectorProperty  # noqa: E402
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402

from migrate_root_abyss_maps import (  # noqa: E402
    TARGET_KEY,
    atomic_write_bytes,
    clone_property,
    gms_reader,
    ensure_int_child,
    patch_server_boss_xml_hp,
    remove_child,
    sanitize_root_abyss_boss_mob,
    write_server_xml_from_client_img,
)


NORMAL_BOSS_MOBS = (
    8900100,
    8910100,
    8920101,
    8930100,
)
ADVANCED_BOSS_MOBS = (
    8900000,
    8910000,
    8920000, 8920001,
    8930000,
)

CRIMSON_QUEEN_VISUAL_TEMPLATES = {
    8920101: 8920001,
}
ADVANCED_STABLE_VISUAL_TEMPLATES = {
    8900000: 8900100,
    8910000: 8910100,
    8920000: 8920101,
}
ADVANCED_BASIC_COMBAT_MOBS = set(ADVANCED_STABLE_VISUAL_TEMPLATES)
# Only adjust existing stand/move origins on the normal Queen resource. Do not
# add missing origins to advanced Pierre/Von Bon/Queen; that path made them
# crash on room entry in the legacy client.
FOOT_ALIGNMENT_MOBS = {8920101}
FOOT_ALIGNMENT_ACTIONS = {"stand", "move"}
FOOT_ALIGNMENT_TEMPLATES = {}
COMPAT_ORIGIN_TEMPLATES = {}
VELLUM_COMPAT_MOBS = {8930000, 8930100}
VELLUM_MAX_ATTACK_FRAME_WIDTH = 960
VELLUM_MAX_ATTACK_FRAME_HEIGHT = 720
VELLUM_FIRE_BREATH_FRAMES = {str(frame) for frame in range(52, 66)}
VELLUM_FIRE_BREATH_ORIGIN_X = 1004


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


def canvas_origins_by_path(root: WzSubProperty) -> dict[str, tuple[int, int]]:
    origins: dict[str, tuple[int, int]] = {}

    def walk(node, path: str) -> None:
        if isinstance(node, WzCanvasProperty):
            origin = node.child("origin")
            if isinstance(origin, WzVectorProperty):
                origins[path] = (int(origin.x), int(origin.y))
        if hasattr(node, "children"):
            for child in node.children():
                walk(child, f"{path}/{child.name}" if path else child.name)

    walk(root, "")
    return origins


def add_missing_origins_from_template(root: WzSubProperty, template: WzSubProperty) -> int:
    template_origins = canvas_origins_by_path(template)
    changed = 0

    def walk(node, path: str) -> None:
        nonlocal changed
        if isinstance(node, WzCanvasProperty) and node.child("origin") is None:
            copied = template_origins.get(path)
            if copied is None:
                copied = (int(node.width) // 2, int(node.height))
            node.add(WzVectorProperty("origin", copied[0], copied[1], node))
            changed += 1
        if hasattr(node, "children"):
            for child in node.children():
                walk(child, f"{path}/{child.name}" if path else child.name)

    walk(root, "")
    return changed


def scale_vellum_attack_frames(root: WzSubProperty) -> int:
    changed = 0
    for action in root.children():
        if not isinstance(action, WzSubProperty) or not action.name.startswith("attack"):
            continue
        for frame in action.children():
            if not isinstance(frame, WzCanvasProperty) or not frame.has_pixels():
                continue
            width = int(frame.width)
            height = int(frame.height)
            scale = min(
                VELLUM_MAX_ATTACK_FRAME_WIDTH / width,
                VELLUM_MAX_ATTACK_FRAME_HEIGHT / height,
                1.0,
            )
            if scale >= 1.0:
                continue
            image = decode_canvas(frame, region="GMS").convert("RGBA")
            new_width = max(1, round(width * scale))
            new_height = max(1, round(height * scale))
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            frame.width = new_width
            frame.height = new_height
            frame.format = 1
            frame.format2 = 0
            frame._png_data = encode_canvas_payload(
                image,
                1,
                new_width,
                new_height,
                key=TARGET_KEY,
                listwz=False,
            )
            frame._png_length = len(frame._png_data)
            for child in frame.children():
                if isinstance(child, WzVectorProperty):
                    child.x = round(int(child.x) * scale)
                    child.y = round(int(child.y) * scale)
            changed += 1
    return changed


def restore_vellum_fire_breath_origin(root: WzSubProperty) -> int:
    action = root.child("attack5")
    if not isinstance(action, WzSubProperty):
        return 0
    changed = 0
    for frame_name in VELLUM_FIRE_BREATH_FRAMES:
        frame = action.child(frame_name)
        origin = frame.child("origin") if isinstance(frame, WzCanvasProperty) else None
        if isinstance(origin, WzVectorProperty) and int(origin.x) != VELLUM_FIRE_BREATH_ORIGIN_X:
            origin.x = VELLUM_FIRE_BREATH_ORIGIN_X
            changed += 1
    return changed


def patch_specific_boss_contract(root: WzSubProperty, mob_id: int) -> None:
    if mob_id in ADVANCED_BASIC_COMBAT_MOBS:
        info = root.child("info")
        if isinstance(info, WzSubProperty):
            remove_child(info, "skill")
            ensure_int_child(info, "firstAttack", 1)
    if mob_id in {8900000, 8920000}:
        info = root.child("info")
        if isinstance(info, WzSubProperty):
            ensure_int_child(info, "firstAttack", 1)
    if mob_id in VELLUM_COMPAT_MOBS:
        scale_vellum_attack_frames(root)
        restore_vellum_fire_breath_origin(root)


def patch_mob(mob_id: int) -> str:
    path = ROOT / f"clien/Data/Mob/{mob_id}.img"
    if not path.exists():
        return "missing"

    image = target_img(path)
    template_id = CRIMSON_QUEEN_VISUAL_TEMPLATES.get(mob_id)
    if template_id is not None:
        template = target_img(ROOT / f"clien/Data/Mob/{template_id}.img")
        copy_non_info_children(image.root, template.root)
    stable_template_id = ADVANCED_STABLE_VISUAL_TEMPLATES.get(mob_id)
    if stable_template_id is not None:
        template = target_img(ROOT / f"clien/Data/Mob/{stable_template_id}.img")
        copy_non_info_children(image.root, template.root)

    sanitize_root_abyss_boss_mob(image.root, mob_id)
    origin_template_id = COMPAT_ORIGIN_TEMPLATES.get(mob_id)
    if origin_template_id is not None:
        template = target_img(ROOT / f"clien/Data/Mob/{origin_template_id}.img")
        add_missing_origins_from_template(image.root, template.root)
    patch_specific_boss_contract(image.root, mob_id)
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
