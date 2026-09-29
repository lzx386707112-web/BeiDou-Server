#!/usr/bin/env python3
"""Close the last hole in the 未來之門 daily chain (尋找祖先的智慧).

31918-31920 send the player to 村长阿勒斯 (2142001) and 幽灵斯坦 (2142007), who
live in 271010000 - the chapter-one village that BeiDou never received.  With
them unreachable the daily sub-chain 31917 -> 31918 -> 31919 -> 31920 -> 31921
dies at 31918.

Fixes, both following precedents already used by the 黃昏的勇士之村 import:

  * 2142001 (村长阿勒斯) is remapped to 2142106 (阿勒斯) - the same character as
    he appears in the twilight village, already spawned in 273000000.  This is
    the same substitution style as the existing 1105001 -> 1022000 remap.
  * 2142007 (幽灵斯坦) has no counterpart, so he is spawned in 273000000.  His
    Npc image already exists on both sides; only the life entry was missing.

Run:  /opt/homebrew/bin/python3 tool/scripts/migration/close_twilight_perion_daily_gap.py
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

BACKUP_ROOT = Path("/private/tmp/twilight-perion-daily-gap-backup")

# quest -> (branch, old npc, new npc)
REMAPS = (
    ("31918", "1", "2142001", "2142106"),
    ("31919", "0", "2142001", "2142106"),
)
SPAWN_NPC = ("273000000", "2142007")

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
    return WzImage.from_bytes(
        data, key=WzKey.for_region(detect_region_from_img(data) or "GMS")
    ).parse()


def remap_server(path: Path, quest: str, branch: str, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    tree = ET.fromstring(text)
    node = tree.find(f'./imgdir[@name="{quest}"]/imgdir[@name="{branch}"]/int[@name="npc"]')
    if node is None:
        raise RuntimeError(f"{quest}/{branch}/npc missing in {path.name}")
    if node.get("value") != old:
        print(f"    {path.name} {quest}/{branch}/npc already {node.get('value')}, skip")
        return
    result = mutate_xml(
        text, "edit", (quest, branch, "npc"), kind="Int", values={"value": int(new)}
    )
    backup(path)
    path.write_text(result, encoding="utf-8")


def remap_client(path: Path, quest: str, branch: str, old: str, new: str) -> None:
    data = path.read_bytes()
    root = parse_client(path)
    quest_node = root.child(quest)
    target = quest_node.child(branch).child("npc") if quest_node else None
    if target is None:
        raise RuntimeError(f"{quest}/{branch}/npc missing in {path.name}")
    if str(target.value) != old:
        print(f"    {path.name} {quest}/{branch}/npc already {target.value}, skip")
        return
    patched = mutate_img(
        data, "edit", (quest, branch, "npc"),
        values={"value": int(new)}, region="GMS",
    ).data
    backup(path)
    path.write_bytes(patched)


def spawn_npc(map_id: str, npc_id: str) -> None:
    client = ROOT / f"clien/Data/Map/Map/Map2/{map_id}.img"
    server = ROOT / f"gms-server/wz/Map.wz/Map/Map2/{map_id}.img.xml"

    root = parse_client(client)
    life = root.child("life")
    entries = {e.name: {c.name: c.value for c in e.children()} for e in life.children()}
    if any(str(v.get("id")) == npc_id for v in entries.values()):
        print(f"    {map_id}: npc {npc_id} already spawned, skip")
        return
    template = next(v for v in entries.values() if v.get("type") == "n")
    values = dict(template)
    values["type"] = "n"
    values["id"] = npc_id
    index = str(max(int(name) for name in entries if name.isdigit()) + 1)

    data = client.read_bytes()
    data = mutate_img(
        data, "add", ("life",), name=index, kind="SubProperty", region="GMS"
    ).data
    for field, kind in LIFE_FIELDS:
        data = mutate_img(
            data, "add", ("life", index), name=field, kind=kind,
            values={"value": values[field]}, region="GMS",
        ).data
    backup(client)
    client.write_bytes(data)

    text = server.read_text(encoding="utf-8")
    result = mutate_xml(text, "add", ("life",), name=index, kind="SubProperty")
    for field, kind in LIFE_FIELDS:
        result = mutate_xml(
            result, "add", ("life", index), name=field, kind=kind,
            values={"value": values[field]},
        )
    backup(server)
    server.write_text(result, encoding="utf-8")
    print(f"    {map_id}: spawned npc {npc_id} as life/{index}")


def main() -> int:
    server_check = ROOT / "gms-server/wz-zh-CN/Quest.wz/Check.img.xml"
    client_check = ROOT / "clien/Data/Quest/Check.img"
    for quest, branch, old, new in REMAPS:
        print(f"  {quest}/{branch}: {old} -> {new}")
        remap_server(server_check, quest, branch, old, new)
        remap_client(client_check, quest, branch, old, new)
    print(f"  spawn: {SPAWN_NPC[1]} -> {SPAWN_NPC[0]}")
    spawn_npc(*SPAWN_NPC)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
