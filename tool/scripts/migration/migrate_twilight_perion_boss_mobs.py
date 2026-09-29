#!/usr/bin/env python3
"""Migrate the script-summoned 黃昏的勇士之村 quest mobs from TMS.

TMS never spawns these two in any 2730 field:  they are summoned by the theme
dungeon quest scripts (``q31913s`` for 9100043, the 麥吉 trial script for
8620012).  BeiDou runs the dungeon data-only, so the mobs must exist as normal
field mobs for the quest chain to be completable.

Source of truth is the extracted TMS mob image in ``ms-extract/Mob_*/``; the
``MapleStory-IMG`` dump only keeps ``Mob/_Canvas`` (sprites without stats).

Placement (documented in docs/黃昏的勇士之村-流程與完整性核對.html):
  * 8620012 變形樹妖王 -> 273020400 寒風蕭瑟的墓地  (quest 31930 Say: "#m273020400")
  * 9100043 驅夢者的手下 -> 273060300 戰士們的決戰之地

Run:  /opt/homebrew/bin/python3 tool/scripts/migration/migrate_twilight_perion_boss_mobs.py
"""

from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

from wzpy import WzImage, WzKey, detect_region_from_img  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402

ARC_PATH = ROOT / "tool/scripts/migration/migrate_arcane_river_expansion.py"
_spec = importlib.util.spec_from_file_location("arc", ARC_PATH)
arc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(arc)

TMS_MS = Path("/Users/lizixian/Documents/mxd/TMS/ms-extract")

# mob_id -> source file name is Mob_<id>.img inside ms-extract/Mob_0000*
MOBS = (9100043,)


def find_source(mob_id: int) -> Path:
    for folder in sorted(TMS_MS.glob("Mob_*")):
        candidate = folder / f"Mob_{mob_id}.img"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"no ms-extract mob image for {mob_id}")


def migrate(mob_id: int) -> None:
    client = ROOT / f"clien/Data/Mob/{mob_id:07d}.img"
    server = ROOT / f"gms-server/wz/Mob.wz/{mob_id:07d}.img.xml"
    if client.exists() and server.exists():
        print(f"{mob_id}: already present, skipping")
        return

    source = find_source(mob_id)
    image, materializer = arc.clone_image(
        source, lambda root: arc.sanitize_mob(root, mob_id)
    )
    arc.write_client_image(client, image)
    arc.write_server_image(server, image, f"{mob_id:07d}.img")
    print(
        f"{mob_id}: wrote client+server "
        f"(canvases={materializer.canvases} links={materializer.links} "
        f"resized={materializer.resized})"
    )


def verify(mob_id: int) -> None:
    client = ROOT / f"clien/Data/Mob/{mob_id:07d}.img"
    server = ROOT / f"gms-server/wz/Mob.wz/{mob_id:07d}.img.xml"

    data = client.read_bytes()
    image = WzImage.from_bytes(
        data, key=WzKey.for_region(detect_region_from_img(data) or "GMS")
    )
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"{mob_id}: client IMG malformed: "
            f"truncated={image.truncated} warnings={image.parse_warnings}"
        )

    canvas_count = 0
    bad_format = []
    blank = []
    for state in root.children():
        if not state.children():
            continue
        for frame in state.children():
            if frame.__class__.__name__ != "WzCanvasProperty":
                continue
            canvas_count += 1
            if (frame.format, frame.format2) != (1, 0):
                bad_format.append(f"{state.name}/{frame.name}={frame.format},{frame.format2}")
            if frame.name == "0" or frame.name == "1":
                pixels = decode_canvas(frame)
                if pixels is None or not any(pixels.getdata()):
                    blank.append(f"{state.name}/{frame.name}")
    if bad_format:
        raise RuntimeError(f"{mob_id}: non-ARGB4444 canvases: {bad_format[:5]}")
    if blank:
        raise RuntimeError(f"{mob_id}: blank frames: {blank[:5]}")

    tree = ET.parse(server)
    info = tree.getroot().find('./imgdir[@name="info"]')
    if info is None:
        raise RuntimeError(f"{mob_id}: server mob has no info block")
    values = {node.get("name"): node.get("value") for node in info}
    if values.get("eva") != "100":
        raise RuntimeError(f"{mob_id}: server mob eva={values.get('eva')}")
    print(
        f"{mob_id}: OK  canvases={canvas_count} (all ARGB4444)  "
        f"level={values.get('level')} maxHP={values.get('maxHP')} "
        f"boss={values.get('boss')}"
    )


def main() -> int:
    for mob_id in MOBS:
        migrate(mob_id)
        verify(mob_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
