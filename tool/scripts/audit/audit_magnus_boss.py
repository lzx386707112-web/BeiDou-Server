#!/usr/bin/env python3
"""Audit the single Boss-only Magnus configuration."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

from wzpy import WzCanvasProperty, WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


KEY = WzKey.for_region("GMS")


def load_img(path: Path) -> WzImage:
    img = WzImage.from_bytes(path.read_bytes(), key=KEY, name=path.name)
    img.parse()
    return img


def main() -> int:
    errors = []
    img = load_img(ROOT / "clien/Data/Mob/8880000.img")
    expected_client = {
        "maxHP": 2_000_000_000,
        "hpRecovery": 100_000_000,
        "speed": 50,
        "PDDamage": 30_000,
        "MDDamage": 30_000,
    }
    for name, expected in expected_client.items():
        node = img.root.get(f"info/{name}")
        if node is None or node.value != expected:
            errors.append(f"client info/{name}: expected {expected}, got {None if node is None else node.value}")
    if img.root.get("info/revive") is not None:
        errors.append("8880000 must not have revive")

    canvas_count = 0
    def walk(node):
        nonlocal canvas_count
        if isinstance(node, WzCanvasProperty) and node.has_pixels():
            canvas_count += 1
            decode_canvas(node, region="GMS")
        if hasattr(node, "children"):
            for child in node.children():
                walk(child)
    walk(img.root)

    server = ET.parse(ROOT / "gms-server/wz/Mob.wz/8880000.img.xml").getroot()
    info = server.find('./imgdir[@name="info"]')
    expected_server = {"maxHP": "5000000000", "hpRecovery": "100000000", "speed": "50"}
    for name, expected in expected_server.items():
        node = info.find(f'./*[@name="{name}"]') if info is not None else None
        if node is None or node.attrib.get("value") != expected:
            errors.append(f"server info/{name}: expected {expected}")
    hp_node = info.find('./string[@name="maxHP"]') if info is not None else None
    if hp_node is None:
        errors.append("server maxHP must use a long-safe string node")

    strings = load_img(ROOT / "clien/Data/String/Mob.img")
    name = strings.root.get("8880000/name")
    if name is None or name.value != "麦格纳斯":
        errors.append("missing client Magnus name")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"magnus audit ok: mob=8880000 canvas={canvas_count} server_hp=5000000000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
