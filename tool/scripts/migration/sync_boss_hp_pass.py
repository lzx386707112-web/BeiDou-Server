#!/usr/bin/env python3
"""Final HP/level sync for the boss-HP pass (both delivery ends).

Ends: clien/Data/Mob/<mobId>.img  +  gms-server/wz/Mob.wz/<mobId>.img.xml
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/resource-workbench"))

from map_mob import app  # noqa: E402

YI = 100_000_000
HP = {
    '8880803': 295, '8880400': 285,
    '8880340': 70, '8880341': 70, '8880342': 70, '8880343': 70, '8880344': 70,
    '8645009': 265,
    '8880300': 84, '8880301': 84, '8880302': 84,
    '8880140': 120, '8880141': 120,
    '8880700': 220,
    '8880110': 105, '8880111': 105,
    '8880000': 190, '8850011': 105, '8840000': 63,
    '8860000': 21, '9450040': 21,
    '8880830': 21, '8880831': 21, '8880832': 21,
    '9421581': 2, '9421583': 10,
    '8930000': 6, '8910000': 4,
    '8900000': 4, '8900001': 4, '8900002': 4,
    '8920000': 4, '8920001': 5, '8920002': 6,
    '9600087': 2.5,
}
LEVEL = {'8880700': 220, '8880830': 250, '8880831': 250, '8880832': 250}


def main() -> None:
    for mob, yi in HP.items():
        hp = int(yi * YI)
        client = ROOT / f"clien/Data/Mob/{mob}.img"
        server = ROOT / f"gms-server/wz/Mob.wz/{mob}.img.xml"
        # Client .img stores maxHP as compressed int32: clamp; server XML holds the real long HP.
        app.patch_img(client, "info/maxHP", min(hp, 2147483647), dry_run=False, backup=True)
        app.patch_xml_value(server, "info/maxHP", hp, dry_run=False, backup=True)
        if mob in LEVEL:
            app.patch_img(client, "info/level", LEVEL[mob], dry_run=False, backup=True)
            app.patch_xml_value(server, "info/level", LEVEL[mob], dry_run=False, backup=True)
        image = app.load_image(client)
        assert not image.truncated and not image.parse_warnings, mob
        assert int(image.root.get("info/maxHP").value) == min(hp, 2147483647), mob
        print(f"{mob} -> {hp}", flush=True)
    print("SYNC OK", flush=True)


if __name__ == "__main__":
    main()
