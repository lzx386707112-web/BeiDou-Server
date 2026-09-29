#!/usr/bin/env python3
"""Add the missing info/lvLimit=180 to the 24 黃昏的勇士之村 maps.

TMS sets lvLimit=180 on every 2730 field; the BeiDou import dropped it.  The
legacy server only reports the field in MapDetectService, so this is a data
completeness fix rather than an enforcement change - the client shows the
requirement and the self-check stops flagging the maps.

Run:  /opt/homebrew/bin/python3 tool/scripts/migration/add_twilight_perion_map_level_limit.py
"""

from __future__ import annotations

import glob
import os
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

from wzpy import WzImage, WzKey, detect_region_from_img  # noqa: E402
from wzpy.incremental_img import mutate_img  # noqa: E402
from wzpy.incremental_xml import mutate_xml  # noqa: E402

BACKUP_ROOT = Path("/private/tmp/twilight-perion-lvlimit-backup")
LEVEL_LIMIT = 180


def backup(path: Path) -> None:
    target = BACKUP_ROOT / path.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(path, target)


def main() -> int:
    client_files = sorted(glob.glob(str(ROOT / "clien/Data/Map/Map/Map2/2730*.img")))
    for client in client_files:
        map_id = os.path.basename(client)[:-4]
        server = ROOT / f"gms-server/wz/Map.wz/Map/Map2/{map_id}.img.xml"

        data = Path(client).read_bytes()
        root = WzImage.from_bytes(
            data, key=WzKey.for_region(detect_region_from_img(data) or "GMS")
        ).parse()
        info = root.child("info")
        if info is not None and info.child("lvLimit") is None:
            patched = mutate_img(
                data,
                "add",
                ("info",),
                name="lvLimit",
                kind="Int",
                values={"value": LEVEL_LIMIT},
                region="GMS",
            ).data
            backup(Path(client))
            Path(client).write_bytes(patched)
        else:
            patched = data
        check = WzImage.from_bytes(
            patched, key=WzKey.for_region(detect_region_from_img(patched) or "GMS")
        )
        check.parse()
        if check.truncated or check.parse_warnings:
            raise RuntimeError(f"{map_id}: client IMG invalid after patch")

        text = server.read_text(encoding="utf-8")
        tree = ET.fromstring(text)
        info_node = tree.find('./imgdir[@name="info"]')
        if info_node is not None and info_node.find('./int[@name="lvLimit"]') is None:
            result = mutate_xml(
                text,
                "add",
                ("info",),
                name="lvLimit",
                kind="Int",
                values={"value": LEVEL_LIMIT},
            )
            backup(server)
            server.write_text(result, encoding="utf-8")
            text = result
        ET.fromstring(text)
        print(f"  {map_id}: lvLimit={LEVEL_LIMIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
