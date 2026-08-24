#!/usr/bin/env python3
"""Contract checks for the 450001014 legacy-client crash repair."""

from __future__ import annotations

import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import WzCanvasProperty, WzImage, WzIntProperty, WzKey, WzSubProperty  # noqa: E402
from wzpy.canvas import _read_canvas_bytes, decode_canvas  # noqa: E402


KEY = WzKey.for_region("GMS")


def load(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=KEY, name=path.name)
    image.parse()
    assert not image.truncated, path
    assert image.parse_warnings == [], (path, image.parse_warnings)
    return image


def child_value(node, name: str):
    child = node.child(name) if node is not None else None
    return getattr(child, "value", None)


def life_mobs(image: WzImage) -> set[int]:
    life = image.root.child("life")
    assert isinstance(life, WzSubProperty)
    return {
        int(child_value(entry, "id"))
        for entry in life.children()
        if child_value(entry, "type") == "m"
    }


def canvas_signature(canvas: WzCanvasProperty) -> tuple:
    pixels = decode_canvas(canvas, region="GMS").convert("RGBA")
    metadata = tuple(
        (child.name, child.type_name, getattr(child, "x", None), getattr(child, "y", None), child.value)
        for child in canvas.children()
    )
    return (
        int(canvas.width),
        int(canvas.height),
        int(canvas.format),
        int(canvas.format2),
        metadata,
        hashlib.sha256(_read_canvas_bytes(canvas)).hexdigest(),
        hashlib.sha256(pixels.tobytes()).hexdigest(),
    )


def main() -> int:
    normal = load(ROOT / "clien/Data/Map/Map/Map4/450001012.img")
    affected = load(ROOT / "clien/Data/Map/Map/Map4/450001014.img")
    assert life_mobs(normal) == {8641001}
    assert life_mobs(affected) == {8641002}

    mob = load(ROOT / "clien/Data/Mob/8641002.img")
    first_attack = mob.root.get("info/firstAttack")
    assert isinstance(first_attack, WzIntProperty) and int(first_attack.value) == 1
    attack = mob.root.child("attack1")
    assert isinstance(attack, WzSubProperty)
    assert tuple(child.name for child in attack.children()) == (
        "info", *(str(index) for index in range(16))
    )
    frame9, frame10 = attack.child("9"), attack.child("10")
    assert isinstance(frame9, WzCanvasProperty)
    assert isinstance(frame10, WzCanvasProperty)
    assert (int(frame10.format), int(frame10.format2)) == (1, 0)
    assert canvas_signature(frame9) == canvas_signature(frame10)
    attach = mob.root.get("attack1/info/hit/attach")
    assert isinstance(attach, WzIntProperty) and int(attach.value) == 1
    attack_info = mob.root.get("attack1/info")
    assert isinstance(attack_info, WzSubProperty)
    assert tuple(child.name for child in attack_info.children()) == (
        "range", "ball", "hit", "type", "attackAfter", "bulletSpeed"
    )
    attack_type = attack_info.child("type")
    bullet_speed = attack_info.child("bulletSpeed")
    assert isinstance(attack_type, WzIntProperty) and int(attack_type.value) == 2
    assert isinstance(bullet_speed, WzIntProperty) and int(bullet_speed.value) == 300

    xml = ET.parse(ROOT / "gms-server/wz/Mob.wz/8641002.img.xml").getroot()
    xml_attack = xml.find('./imgdir[@name="attack1"]')
    assert xml_attack is not None
    assert tuple(child.get("name") for child in xml_attack) == (
        "info", *(str(index) for index in range(16))
    )
    xml_attach = xml.find(
        './imgdir[@name="attack1"]/imgdir[@name="info"]/imgdir[@name="hit"]/'
        'int[@name="attach"]'
    )
    assert xml_attach is not None and xml_attach.get("value") == "1"
    xml_info = xml.find('./imgdir[@name="attack1"]/imgdir[@name="info"]')
    assert xml_info is not None
    assert tuple(child.get("name") for child in xml_info) == (
        "range", "ball", "hit", "type", "attackAfter", "bulletSpeed"
    )
    xml_type = xml_info.find('./int[@name="type"]')
    xml_bullet_speed = xml_info.find('./int[@name="bulletSpeed"]')
    assert xml_type is not None and xml_type.get("value") == "2"
    assert xml_bullet_speed is not None and xml_bullet_speed.get("value") == "300"
    print(
        "450001014 contract ok: life=8641002 firstAttack=1 "
        "attack1=0..15 frame10=frame9 attach=1 type=2 bulletSpeed=300"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
