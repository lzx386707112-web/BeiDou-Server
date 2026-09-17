#!/usr/bin/env python3
"""Project Damien 8880110 onto Cygnus 8850011 node structure and combat XML.

Keep Damien canvases. Copy only Cygnus property names, attack/info schema,
skill table, firstAttack, and walk speed. Do not copy Cygnus pixels.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_demian as demian  # noqa: E402
from migrate_twilight_perion_monster_park import load_checked  # noqa: E402
from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzDoubleProperty,
    WzFloatProperty,
    WzImage,
    WzIntProperty,
    WzLongProperty,
    WzNullProperty,
    WzShortProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402

CYGNUS_ID = 8850011
DAMIEN_P1 = 8880110
P2_ID = 8880111
TOP_LEVEL = (
    "info", "stand", "move", "attack1", "attack2", "attack3", "attack4",
    "skill1", "skill2", "skill3", "skill4", "skill5", "skill6", "skill7",
    "die1", "hit1", "sleep", "wakeup",
)
DAMIEN_STAT_NAMES = (
    "level", "maxHP", "maxMP", "mpRecovery", "PADamage", "MADamage",
    "PDRate", "MDRate", "acc", "elemAttr", "exp", "hpTagColor",
    "hpTagBgcolor", "rareItemDropLevel",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def client_cygnus() -> Path:
    return ROOT / f"clien/Data/Mob/{CYGNUS_ID}.img"


def load_head_damien() -> WzImage:
    data = subprocess.check_output(
        ["git", "cat-file", "blob", f"HEAD:clien/Data/Mob/{DAMIEN_P1}.img"],
        cwd=ROOT,
    )
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=f"{DAMIEN_P1}.img")
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError("HEAD 8880110.img does not parse")
    return image


def visible_frames(node) -> list[WzCanvasProperty]:
    frames: list[WzCanvasProperty] = []
    if node is None:
        return frames
    children = list(node.children()) if hasattr(node, "children") else []
    numbered = [child for child in children if isinstance(child, WzCanvasProperty) and child.name.isdigit()]
    numbered.sort(key=lambda child: int(child.name))
    for child in numbered:
        if int(child.width) > 4 and int(child.height) > 4:
            frames.append(child)
    return frames


def clone_canvas(name: str, parent: WzSubProperty, source: WzCanvasProperty) -> WzCanvasProperty:
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
    oy = int(origin.y) if origin is not None else canvas.height // 2
    canvas.add(WzVectorProperty("origin", ox, oy, canvas))
    delay = source.child("delay")
    canvas.add(WzIntProperty("delay", int(delay.value) if delay is not None else 90, canvas))
    z_node = source.child("z")
    if z_node is not None:
        canvas.add(WzIntProperty("z", int(z_node.value), canvas))
    pixels.close()
    return canvas


def clone_scalar(source, parent):
    name = source.name
    if isinstance(source, WzVectorProperty):
        return WzVectorProperty(name, int(source.x), int(source.y), parent)
    if isinstance(source, WzStringProperty):
        return WzStringProperty(name, str(source.value), parent)
    if isinstance(source, WzIntProperty):
        return WzIntProperty(name, int(source.value), parent)
    if isinstance(source, WzShortProperty):
        return WzShortProperty(name, int(source.value), parent)
    if isinstance(source, WzLongProperty):
        return WzLongProperty(name, int(source.value), parent)
    if isinstance(source, WzFloatProperty):
        return WzFloatProperty(name, float(source.value), parent)
    if isinstance(source, WzDoubleProperty):
        return WzDoubleProperty(name, float(source.value), parent)
    if isinstance(source, WzUolProperty):
        return WzUolProperty(name, str(source.value), parent)
    if isinstance(source, WzNullProperty):
        return WzNullProperty(name, parent)
    raise TypeError(f"unsupported scalar {type(source).__name__}")


class ArtBank:
    def __init__(self, damien: WzImage, phase_two: WzImage) -> None:
        stand = visible_frames(damien.root.child("stand"))
        attack1 = visible_frames(damien.root.child("attack1"))
        hit = visible_frames(damien.root.get("attack1/info/hit"))
        hit1 = visible_frames(damien.root.child("hit1"))
        skills = [visible_frames(damien.root.child(f"skill{index}")) for index in range(1, 5)]
        ball = visible_frames(phase_two.root.get("attack3/info/ball"))
        knife_hit = visible_frames(phase_two.root.get("attack3/info/hit"))
        if len(stand) < 4:
            raise RuntimeError("HEAD Damien stand is missing visible frames")
        if len(attack1) < 8:
            raise RuntimeError("HEAD Damien attack1 is missing visible frames")
        if len(hit) < 4:
            raise RuntimeError("HEAD Damien attack1/info/hit is missing visible frames")
        if len(ball) < 4:
            raise RuntimeError("8880111 attack3/info/ball is missing flying-knife frames")
        self.stand = stand
        self.attack1 = attack1
        self.hit = hit
        self.hit1 = hit1 or hit[:1]
        self.skills = skills
        self.ball = ball
        self.knife_hit = knife_hit or hit

    def pool(self, path: tuple[str, ...]) -> list[WzCanvasProperty]:
        root = path[0] if path else ""
        joined = "/".join(path)
        if root in {"stand", "move", "sleep", "wakeup"}:
            return self.stand
        if root == "hit1":
            return self.hit1
        if root == "die1":
            return self.attack1[-8:] or self.hit1
        if "info/ball" in joined:
            return self.ball
        if "info/hit" in joined or "info/areaWarning" in joined:
            return self.hit if root != "attack2" else self.knife_hit
        if root.startswith("skill"):
            index = int(root[5:]) - 1
            frames = self.skills[index % 4]
            if not frames:
                raise RuntimeError(f"HEAD Damien {root} has no visible frames")
            return frames
        if root.startswith("attack"):
            return self.attack1
        raise RuntimeError(f"no Damien art mapping for {path}")


def pick_frame(pool: list[WzCanvasProperty], path: tuple[str, ...]) -> WzCanvasProperty:
    digits = [part for part in path if part.isdigit()]
    index = int(digits[-1]) if digits else 0
    return pool[index % len(pool)]


def project_node(source, parent, path: tuple[str, ...], art: ArtBank):
    if isinstance(source, WzCanvasProperty):
        return clone_canvas(source.name, parent, pick_frame(art.pool(path), path))
    if isinstance(source, WzSubProperty):
        output = WzSubProperty(source.name, parent)
        for child in source.children():
            output.add(project_node(child, output, path + (child.name,), art))
        return output
    return clone_scalar(source, parent)


def overlay_damien_stats(info: WzSubProperty, damien_info: WzSubProperty) -> None:
    for name in DAMIEN_STAT_NAMES:
        value = arc.child_value(damien_info, name)
        if value is None:
            continue
        if isinstance(value, str):
            arc.remove_child(info, name)
            info.add(WzStringProperty(name, value, info))
        else:
            arc.set_int(info, name, int(value) if not isinstance(value, float) else int(value))
    arc.set_int(info, "firstAttack", 1)
    arc.set_int(info, "speed", -60)
    arc.set_int(info, "bodyAttack", 1)
    for name in ("ban", "revive"):
        arc.remove_child(info, name)


def build_image() -> WzImage:
    cygnus = load_checked(client_cygnus(), arc.GMS_KEY)
    damien = load_head_damien()
    phase_two = load_checked(demian.client_mob_path(P2_ID), arc.GMS_KEY)
    art = ArtBank(damien, phase_two)
    root = WzSubProperty(cygnus.root.name)
    for child in cygnus.root.children():
        root.add(project_node(child, root, (child.name,), art))
    info = root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError("projected 8880110 missing info")
    overlay_damien_stats(info, damien.root.child("info"))
    names = [child.name for child in root.children()]
    if names != list(TOP_LEVEL):
        raise RuntimeError(f"projected top-level {names}")
    image = load_checked(client_cygnus(), arc.GMS_KEY)
    image._root = root
    image._parsed = True
    image.name = f"{DAMIEN_P1}.img"
    return image


def verify_client() -> None:
    cygnus = client_cygnus().read_bytes()
    damien = demian.client_mob_path(DAMIEN_P1).read_bytes()
    if damien == cygnus:
        raise RuntimeError("8880110.img still is a Cygnus pixel copy")
    image = load_checked(demian.client_mob_path(DAMIEN_P1), arc.GMS_KEY)
    names = [child.name for child in image.root.children()]
    if names != list(TOP_LEVEL):
        raise RuntimeError(f"8880110 top-level order {names}")
    stand = image.root.get("stand/0")
    cygnus_stand = load_checked(client_cygnus(), arc.GMS_KEY).root.get("stand/0")
    if (int(stand.width), int(stand.height)) == (int(cygnus_stand.width), int(cygnus_stand.height)):
        raise RuntimeError("8880110 stand/0 still has Cygnus dimensions")
    if int(stand.width) <= 4:
        raise RuntimeError("8880110 stand/0 is a placeholder")
    if int(arc.child_value(image.root.child("info"), "firstAttack") or 0) != 1:
        raise RuntimeError("8880110 firstAttack is not 1")
    if int(arc.child_value(image.root.child("info"), "speed") or 0) != -60:
        raise RuntimeError("8880110 speed is not Cygnus walk speed")
    attack2 = image.root.get("attack2/info")
    if int(arc.child_value(attack2, "type") or 0) != 2:
        raise RuntimeError("8880110 attack2 type is not 2")
    if arc.child_value(attack2, "bulletSpeed") is None:
        raise RuntimeError("8880110 attack2 missing bulletSpeed")
    if image.root.get("attack3/info/areaWarning/0") is None:
        raise RuntimeError("8880110 missing Cygnus-style attack3 areaWarning")
    if image.root.get("info/skill/0") is None:
        raise RuntimeError("8880110 missing Cygnus skill table")


def verify_xml() -> None:
    xml = demian.server_mob_path(DAMIEN_P1).read_text(encoding="utf-8")
    if f'<imgdir name="{DAMIEN_P1}.img">' not in xml:
        raise RuntimeError("8880110 XML root name is wrong")
    if 'name="8850011.img"' in xml:
        raise RuntimeError("8880110 XML still named Cygnus")
    for token in (
        '<int name="type" value="2"/>',
        '<int name="bulletSpeed"',
        '<int name="firstAttack" value="1"/>',
        '<int name="skill" value="133"/>',
        '<imgdir name="areaWarning">',
        '<imgdir name="move">',
    ):
        if token not in xml:
            raise RuntimeError(f"8880110 XML missing {token}")


def patch_once() -> None:
    built = build_image()
    data = arc.verified_image_bytes(
        encode_image_body(built, arc.gms_reader()), f"{DAMIEN_P1}.img"
    )
    checked = WzImage.from_bytes(data, key=arc.GMS_KEY, name=f"{DAMIEN_P1}.img")
    checked.parse()
    if checked.truncated or checked.parse_warnings:
        raise RuntimeError("projected 8880110 parse failed")
    xml = arc.image_to_xml(checked, f"{DAMIEN_P1}.img")
    arc.atomic_write_bytes(demian.client_mob_path(DAMIEN_P1), data)
    arc.atomic_write_text(demian.server_mob_path(DAMIEN_P1), xml)
    verify_client()
    verify_xml()


def main() -> int:
    targets = (demian.client_mob_path(DAMIEN_P1), demian.server_mob_path(DAMIEN_P1))
    patch_once()
    first = {str(path): sha256_file(path) for path in targets}
    patch_once()
    second = {str(path): sha256_file(path) for path in targets}
    if first != second:
        raise RuntimeError(f"cygnus-structure projection is not idempotent: {first} vs {second}")
    print("8880110 cygnus structure with Damien art ok")
    for path, digest in first.items():
        print(f"{Path(path).relative_to(ROOT)} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
