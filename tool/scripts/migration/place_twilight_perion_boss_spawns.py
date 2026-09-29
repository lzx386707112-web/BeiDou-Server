#!/usr/bin/env python3
"""Place the two script-summoned 黃昏的勇士之村 quest mobs into their fields.

TMS summons 8620012 / 9100043 from quest scripts, so no 2730 field spawns them.
BeiDou runs the dungeon without cutscene scripts, so they have to live in the
field data or 31913 / 31930 / 31915 can never be completed.

Placement evidence:
  * 8620012 變形樹妖王 -> 273020400 寒風蕭瑟的墓地
    TMS quest 31930 Say: "在#b#m273020400##k中有...#r木妖王#k"
    and Say/1/stop/mob/0: "變形樹妖王位於#b#m273020400##k"
  * 9100043 驅夢者的手下 -> 273060300 戰士們的決戰之地
    No map hint exists in TMS text (the memory-fragment item warps the player
    through a script).  Chosen as the arena-named field of the 幽靈之地 branch.

mobTime: -1 = "does not respawn, force spawn once" (boss), 0 = normal respawn.

Run:  /opt/homebrew/bin/python3 tool/scripts/migration/place_twilight_perion_boss_spawns.py
"""

from __future__ import annotations

import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

from wzpy import WzImage, WzKey, detect_region_from_img  # noqa: E402
from wzpy.incremental_img import mutate_img  # noqa: E402
from wzpy.incremental_xml import mutate_xml  # noqa: E402

BACKUP_ROOT = Path("/private/tmp/twilight-perion-boss-spawns-backup")

# (map id, mob id, mobTime)
PLACEMENTS = (
    (273020400, 8620012, -1),
    (273060300, 9100043, 0),
)

LIFE_FIELDS = (
    ("type", "String"),
    ("id", "String"),
    ("x", "Int"),
    ("y", "Int"),
    ("mobTime", "Int"),
    ("f", "Int"),
    ("hide", "Int"),
    ("fh", "Int"),
    ("cy", "Int"),
    ("rx0", "Int"),
    ("rx1", "Int"),
)


def backup(path: Path) -> None:
    target = BACKUP_ROOT / path.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(path, target)


def parse_client(path: Path):
    data = path.read_bytes()
    image = WzImage.from_bytes(
        data, key=WzKey.for_region(detect_region_from_img(data) or "GMS")
    )
    return image.parse()


def life_snapshot_client(root) -> dict[str, dict[str, object]]:
    life = root.child("life")
    snapshot = {}
    for entry in life.children():
        snapshot[entry.name] = {child.name: child.value for child in entry.children()}
    return snapshot


def next_index(indices: list[str]) -> str:
    numeric = [int(name) for name in indices if name.isdigit()]
    return str(max(numeric) + 1) if numeric else "0"


def template_from(snapshot: dict[str, dict[str, object]]) -> dict[str, object]:
    for values in snapshot.values():
        if values.get("type") == "m":
            return dict(values)
    raise RuntimeError("no mob entry to copy geometry from")


def patch_client(path: Path, mob_id: int, mob_time: int) -> int:
    root = parse_client(path)
    before = life_snapshot_client(root)
    index = next_index(list(before))
    template = template_from(before)
    values = dict(template)
    values["type"] = "m"
    values["id"] = str(mob_id)
    values["mobTime"] = mob_time

    data = path.read_bytes()
    data = mutate_img(
        data, "add", ("life",), name=index, kind="SubProperty", region="GMS"
    ).data
    for field, kind in LIFE_FIELDS:
        data = mutate_img(
            data,
            "add",
            ("life", index),
            name=field,
            kind=kind,
            values={"value": values[field]},
            region="GMS",
        ).data
    backup(path)
    path.write_bytes(data)

    after = life_snapshot_client(parse_client(path))
    if len(after) != len(before) + 1:
        raise RuntimeError(f"{path.name}: life count {len(before)} -> {len(after)}")
    for name, entry in before.items():
        if after.get(name) != entry:
            raise RuntimeError(f"{path.name}: life/{name} changed")
    if after.get(index) != values:
        raise RuntimeError(f"{path.name}: life/{index} mismatch {after.get(index)}")
    return int(index)


def patch_server(path: Path, mob_id: int, mob_time: int, index: str) -> None:
    text = path.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    life = root.find('./imgdir[@name="life"]')
    before = {
        node.get("name"): {c.get("name"): c.get("value") for c in node}
        for node in life
    }
    if index in before:
        raise RuntimeError(f"{path.name}: life/{index} already exists")
    template = None
    for values in before.values():
        if values.get("type") == "m":
            template = dict(values)
            break
    if template is None:
        raise RuntimeError(f"{path.name}: no mob entry to copy geometry from")
    values = dict(template)
    values["type"] = "m"
    values["id"] = str(mob_id)
    values["mobTime"] = str(mob_time)

    result = mutate_xml(text, "add", ("life",), name=index, kind="SubProperty")
    for field, kind in LIFE_FIELDS:
        result = mutate_xml(
            result,
            "add",
            ("life", index),
            name=field,
            kind=kind,
            values={"value": values[field]},
        )
    backup(path)
    path.write_text(result, encoding="utf-8")

    after = {
        node.get("name"): {c.get("name"): c.get("value") for c in node}
        for node in ET.fromstring(result).find('./imgdir[@name="life"]')
    }
    if len(after) != len(before) + 1:
        raise RuntimeError(f"{path.name}: server life count mismatch")
    for name, entry in before.items():
        if after.get(name) != entry:
            raise RuntimeError(f"{path.name}: server life/{name} changed")
    if after.get(index) != values:
        raise RuntimeError(f"{path.name}: server life/{index} mismatch")


def main() -> int:
    for map_id, mob_id, mob_time in PLACEMENTS:
        client = ROOT / f"clien/Data/Map/Map/Map2/{map_id}.img"
        server = ROOT / f"gms-server/wz/Map.wz/Map/Map2/{map_id}.img.xml"
        index = patch_client(client, mob_id, mob_time)
        patch_server(server, mob_id, mob_time, str(index))
        print(f"{mob_id} -> {map_id} (life/{index}, mobTime={mob_time}) OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
