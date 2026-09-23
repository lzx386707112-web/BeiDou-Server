#!/usr/bin/env python3
"""Build missing custom mob files (8880700/8880830-32) from TMS canvas + clean info template.

Delivery targets (both ends, matching migrate_root_abyss_boss_contracts.py convention):
  clien/Data/Mob/<mobId>.img  +  gms-server/wz/Mob.wz/<mobId>.img.xml
Usage: build_missing_mob.py <mobId> <maxHP> <level>
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/resource-workbench"))

from map_mob import app  # noqa: E402

TMS = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data/Mob/_Canvas")


def main() -> None:
    mob, hp, level = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    client = ROOT / f"clien/Data/Mob/{mob}.img"
    server = ROOT / f"gms-server/wz/Mob.wz/{mob}.img.xml"
    for p in (client, server):
        if p.exists():
            p.unlink()
    app.create_empty_main_files(client)
    app.copy_tms_node_with_server_sync(client, ROOT / "clien/Data/Mob/8900003.img", "info")
    simg = app.load_image(TMS / f"{mob}.img")
    skip = {"skillAfter"}
    if mob == "8880831":
        # TMS skill2 is 1-indexed (frames 1-14); GMS timeline requires frame 0.
        skip.add("skill2")
    for action in [c.name for c in simg.root.children()]:
        if action.startswith("skillAfter"):
            print(f"skip {mob}/{action} (TMS effect layer, GMS client drops it)", flush=True)
            continue
        if action in skip:
            print(f"skip {mob}/{action} (frame numbering incompatible, TBD)", flush=True)
            continue
        app.copy_tms_node_with_server_sync(client, TMS / f"{mob}.img", action)
        print(f"copied {mob}/{action}", flush=True)
    app.patch_img(client, "info/level", level, dry_run=False, backup=True)
    app.patch_img(client, "info/maxHP", hp, dry_run=False, backup=True)
    app.patch_xml_value(server, "info/maxHP", hp, dry_run=False, backup=True)
    image = app.load_image(client)
    assert not image.truncated and not image.parse_warnings
    print(f"DONE {mob} maxHP={hp} level={level}", flush=True)


if __name__ == "__main__":
    main()
