#!/usr/bin/env python3
"""8880112 inlines TMS 8880101 attack3/info/ball onto the 8880165 ball contract."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_demian as demian  # noqa: E402
import patch_damien_skill2_gold_orbs as gold_orbs  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402

ORB = demian.client_mob_path(8880112)
GENERATOR = Path(__file__).resolve().parent / "patch_damien_skill2_gold_orbs.py"


def load(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    image.parse()
    return image


def main() -> int:
    errors: list[str] = []
    first = hashlib.sha256(ORB.read_bytes()).hexdigest()
    subprocess.check_call([sys.executable, str(GENERATOR)])
    second = hashlib.sha256(ORB.read_bytes()).hexdigest()
    if first != second:
        errors.append(f"generator changed 8880112: {first} vs {second}")
    image = load(ORB)
    if image.truncated or image.parse_warnings:
        errors.append(f"8880112 parse {image.parse_warnings}")
    info = image.root.get("attack1/info")
    if info is None or int(getattr(info.child("type"), "value", 0) or 0) != 2:
        errors.append("8880112 type is not 2")
    if info is None or info.child("bulletSpeed") is None:
        errors.append("8880112 missing bulletSpeed")
    attach = image.root.get("attack1/info/hit/attach")
    if attach is None or int(attach.value) != 1:
        errors.append("8880112 hit/attach is not 1")
    ball0 = image.root.get("attack1/info/ball/0")
    sources = gold_orbs.ball_sources()
    if not isinstance(ball0, WzCanvasProperty) or not sources:
        errors.append("missing ball0 or 8880101 attack3/info/ball")
    else:
        source = sources[0]
        if ball0.child("_outlink") is not None:
            errors.append("8880112 ball still has _outlink")
        if (int(ball0.format), int(ball0.format2)) != (1, 0):
            errors.append("8880112 ball is not ARGB4444")
        expected = gold_orbs.scaled_size(int(source.width), int(source.height))
        if (int(ball0.width), int(ball0.height)) != expected:
            errors.append(f"8880112 ball size {ball0.width}x{ball0.height} != 8880101 {expected}")
        if expected[0] < 40 or expected[0] >= 160:
            errors.append("8880112 ball size is not the 8880101 sphere")
        decoded = decode_canvas(ball0, region="GMS").convert("RGBA")
        if decoded.getbbox() is None:
            errors.append("8880112 ball empty")
        decoded.close()
    xml = demian.server_mob_path(8880112).read_text(encoding="utf-8")
    if "8880169" in xml or "8880102" in xml:
        errors.append("8880112 XML still names butterfly/shadow IDs")
    if 'name="disease"' in xml:
        errors.append("8880112 XML still has Lucid seduce disease")
    if 'name="fixDamR" value="20"' not in xml:
        errors.append("8880112 XML missing fixDamR=20")
    if errors:
        print("damien skill2 gold orb contract failed:")
        for error in errors:
            print(f"  {error}")
        return 1
    print("damien skill2 gold orb contract ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
