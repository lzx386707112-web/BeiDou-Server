#!/usr/bin/env python3
"""Attach Queen skills to mob frames and keep Vellum hittable.

Queen / Von Bon fullscreen MCV layers were screen-centered (TMS canvas dumps
have no origin → Von Bon composited at 0,0). Native skill/attack frames are the
correct mob-attached contract. This script:

- replaces Queen skill2/skill3 stubs with UOLs onto attack2/attack3
- inserts delay=120 on Queen skill1 frames that lack delay
- sets Vellum hideMove to 0 (same-length)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_expansion as arc  # noqa: E402
from migrate_twilight_perion_monster_park import load_checked  # noqa: E402
from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzSubProperty,
    WzUolProperty,
)
from wzpy.incremental_img import replace_img_record  # noqa: E402


QUEEN_PATH = ROOT / "clien/Data/Mob/8920000.img"
VELLUM_PATH = ROOT / "clien/Data/Mob/8930000.img"
SKILL_DELAY = 120


def numeric_frames(node: WzSubProperty) -> list[str]:
    names = [child.name for child in node.children() if child.name.isdigit()]
    return sorted(names, key=int)


def replace_skill_with_attack_uols(data: bytes, skill_name: str, attack_name: str) -> bytes:
    image = load_checked(QUEEN_PATH, arc.GMS_KEY)
    attack = image.root.child(attack_name)
    if not isinstance(attack, WzSubProperty):
        raise RuntimeError(f"missing {attack_name}")
    frames = numeric_frames(attack)
    if not frames:
        raise RuntimeError(f"{attack_name} has no frames")
    replacement = WzSubProperty(skill_name)
    for name in frames:
        replacement.add(WzUolProperty(name, f"../{attack_name}/{name}", replacement))
    result = replace_img_record(data, (skill_name,), replacement, region="GMS")
    return result.data


def add_skill1_delays(data: bytes) -> bytes:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=QUEEN_PATH.name)
    image.parse()
    skill1 = image.root.child("skill1")
    if not isinstance(skill1, WzSubProperty):
        raise RuntimeError("missing skill1")
    patched = data
    for name in numeric_frames(skill1):
        frame = skill1.child(name)
        if not isinstance(frame, WzCanvasProperty):
            continue
        if frame.child("delay") is not None:
            continue
        patched = arc.mutate_img(
            patched,
            "add",
            ("skill1", name),
            name="delay",
            kind="Int",
            values={"value": SKILL_DELAY},
            region="GMS",
        ).data
        image = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=QUEEN_PATH.name)
        image.parse()
        skill1 = image.root.child("skill1")
    return patched


def patch_queen() -> None:
    original = QUEEN_PATH.read_bytes()
    patched = replace_skill_with_attack_uols(original, "skill2", "attack2")
    patched = replace_skill_with_attack_uols(patched, "skill3", "attack3")
    patched = add_skill1_delays(patched)
    checked = load_checked_bytes(patched, QUEEN_PATH.name)
    skill2 = checked.root.child("skill2")
    attack2 = checked.root.child("attack2")
    if not isinstance(skill2, WzSubProperty) or not isinstance(attack2, WzSubProperty):
        raise RuntimeError("queen skill2/attack2 missing after patch")
    if numeric_frames(skill2) != numeric_frames(attack2):
        raise RuntimeError("queen skill2 UOL set does not match attack2")
    for name in numeric_frames(skill2):
        node = skill2.child(name)
        if not isinstance(node, WzUolProperty) or node.value != f"../attack2/{name}":
            raise RuntimeError(f"queen skill2/{name} is not an attack2 UOL")
    skill1 = checked.root.child("skill1")
    if isinstance(skill1, WzSubProperty):
        for name in numeric_frames(skill1):
            frame = skill1.child(name)
            delay = arc.child_value(frame, "delay") if frame is not None else None
            if delay != SKILL_DELAY:
                raise RuntimeError(f"queen skill1/{name} delay={delay}")
    before, _ = arc.raw_record_state(original)
    after, _ = arc.raw_record_state(patched)
    allowed = {("skill2",), ("skill3",)}
    for path, payload in before.items():
        if path[0] in {"skill1", "skill2", "skill3"}:
            continue
        if after.get(path) != payload:
            raise RuntimeError(f"queen changed protected record {path}")
    for path in after:
        if path not in before and path[0] not in {"skill1", "skill2", "skill3"}:
            raise RuntimeError(f"queen added unexpected record {path}")
    if patched != original:
        arc.atomic_write_bytes(QUEEN_PATH, patched)


def load_checked_bytes(data: bytes, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{name} truncated={image.truncated} warnings={image.parse_warnings}")
    return image


def patch_vellum() -> None:
    original = VELLUM_PATH.read_bytes()
    image = load_checked(VELLUM_PATH, arc.GMS_KEY)
    hide = image.root.child("info")
    if not isinstance(hide, WzSubProperty):
        raise RuntimeError("vellum missing info")
    current = arc.child_value(hide, "hideMove")
    if current == 0:
        return
    if current != 1:
        raise RuntimeError(f"vellum hideMove={current}, expected 1")
    patched = arc.mutate_img(
        original,
        "edit",
        ("info", "hideMove"),
        values={"value": 0},
        region="GMS",
    ).data
    arc.verify_raw_record_scope(original, patched, {("info", "hideMove")}, allow_additions=False)
    checked = load_checked_bytes(patched, VELLUM_PATH.name)
    if arc.child_value(checked.root.child("info"), "hideMove") != 0:
        raise RuntimeError("vellum hideMove not cleared")
    arc.atomic_write_bytes(VELLUM_PATH, patched)


def main() -> int:
    patch_queen()
    patch_vellum()
    print("patched queen skill UOLs/delays and vellum hideMove")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
