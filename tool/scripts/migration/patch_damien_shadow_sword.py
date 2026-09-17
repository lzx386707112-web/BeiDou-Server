#!/usr/bin/env python3
"""Install 8880102 as a byte-identical copy of Lucid butterfly 8880165.

8880110 skill2 has no attack*/info/ball; the old client never shoots from
skill poses. The working ballistic analogue is 8880165: fly + regen +
firstAttack + attack1/info type=2 ball, with fly/regen _outlink to 8880169.
Do not encode_image_body or restamp that IMG — dropping _outlink and
re-inlining canvases is what the previous 8880102 generator did.
This is a new ID file created by copying a proven IMG; do not rewrite 8880165.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_demian as demian  # noqa: E402
from migrate_twilight_perion_monster_park import load_checked  # noqa: E402
from wzpy import WzCanvasProperty, WzIntProperty  # noqa: E402

SHADOW_ID = 8880102
BUTTERFLY_ID = 8880165


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install() -> dict[str, str]:
    source_client = demian.client_mob_path(BUTTERFLY_ID)
    source_xml = demian.server_mob_path(BUTTERFLY_ID)
    if not source_client.is_file():
        raise RuntimeError("missing proven analogue clien/Data/Mob/8880165.img")
    if not source_xml.is_file():
        raise RuntimeError("missing proven analogue gms-server/wz/Mob.wz/8880165.img.xml")
    data = source_client.read_bytes()
    checked = load_checked(source_client, arc.GMS_KEY)
    fly0 = checked.root.get("fly/0")
    if not isinstance(fly0, WzCanvasProperty):
        raise RuntimeError("8880165 missing fly/0")
    outlink = fly0.child("_outlink")
    if outlink is None or "8880169" not in str(outlink.value):
        raise RuntimeError("8880165 fly/0 must keep _outlink to 8880169")
    attack_info = checked.root.get("attack1/info")
    type_node = attack_info.child("type") if attack_info is not None else None
    if not isinstance(type_node, WzIntProperty) or int(type_node.value) != 2:
        raise RuntimeError("8880165 attack1/info type must be 2")
    if attack_info.child("bulletSpeed") is None:
        raise RuntimeError("8880165 attack1/info missing bulletSpeed")
    attach = attack_info.get("hit/attach") if attack_info is not None else None
    if not isinstance(attach, WzIntProperty) or int(attach.value) != 1:
        raise RuntimeError("8880165 attack1/info/hit must keep attach=1")
    xml = source_xml.read_text(encoding="utf-8")
    if 'name="8880165.img"' not in xml.split("\n", 2)[1]:
        raise RuntimeError("8880165 server XML root name is not the first imgdir")
    xml = xml.replace('name="8880165.img"', 'name="8880102.img"', 1)
    client = demian.client_mob_path(SHADOW_ID)
    server = demian.server_mob_path(SHADOW_ID)
    client.parent.mkdir(parents=True, exist_ok=True)
    server.parent.mkdir(parents=True, exist_ok=True)
    client.write_bytes(data)
    server.write_text(xml, encoding="utf-8")
    if sha256_file(client) != sha256_file(source_client):
        raise RuntimeError("8880102 client IMG must stay byte-identical to 8880165")
    return {str(client): sha256_file(client), str(server): sha256_file(server)}


def main() -> int:
    first = install()
    second = install()
    if first != second:
        raise RuntimeError(f"8880102 copy is not idempotent: {first} vs {second}")
    print("damien 8880102 is byte-copy of 8880165")
    for path, digest in first.items():
        print(f"{Path(path).relative_to(ROOT)} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
