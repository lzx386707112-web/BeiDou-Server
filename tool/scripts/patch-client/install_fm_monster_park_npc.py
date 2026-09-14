#!/usr/bin/env python3
"""Install the Monster Park shuttle in the Free Market client map life."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import WzImage, WzIntProperty, WzStringProperty, WzSubProperty  # noqa: E402


NPC_ID = 9071003
REMOVED_NPC_ID = 9000019
CLIENT_RECORD = "8"
CLIENT_MAP = ROOT / "clien/Data/Map/Map/Map9/910000000.img"
SERVER_MAP = ROOT / "gms-server/wz/Map.wz/Map/Map9/910000000.img.xml"
FIELDS = (
    ("type", "String", "n"),
    ("id", "String", str(NPC_ID)),
    ("mobTime", "Int", 0),
    ("f", "Int", 0),
    ("hide", "Int", 0),
    ("x", "Int", 1450),
    ("y", "Int", 23),
    ("cy", "Int", 23),
    ("fh", "Int", 216),
    ("rx0", "Int", 1400),
    ("rx1", "Int", 1500),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_baseline(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["rtk", "proxy", "git", "cat-file", "blob", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def life_node() -> WzSubProperty:
    node = WzSubProperty(CLIENT_RECORD)
    for field_name, field_type, value in FIELDS:
        if field_type == "String":
            node.add(WzStringProperty(field_name, str(value), node))
        else:
            node.add(WzIntProperty(field_name, int(value), node))
    return node


def checked_client(data: bytes) -> WzImage:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=CLIENT_MAP.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"unsafe client map: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    return image


def node_values(node: WzSubProperty) -> tuple[tuple[str, object], ...]:
    return tuple((child.name, child.value) for child in node.children())


def server_life_nodes(data: bytes) -> dict[str, ET.Element]:
    root = ET.fromstring(data)
    life = next((child for child in root if child.get("name") == "life"), None)
    if life is None:
        raise RuntimeError("server map is missing life")
    return {child.get("name"): child for child in life}


def assert_baseline(client: bytes, server: bytes) -> None:
    image = checked_client(client)
    life = image.root.get("life")
    if not isinstance(life, WzSubProperty):
        raise RuntimeError("client map is missing life")
    if tuple(child.name for child in life.children()) != tuple(str(i) for i in range(8)):
        raise RuntimeError("unexpected client life baseline order")
    ids = {str(arc.child_value(entry, "id")) for entry in life.children()}
    if str(NPC_ID) in ids or str(REMOVED_NPC_ID) in ids:
        raise RuntimeError("HEAD client map already contains a task NPC")

    nodes = server_life_nodes(server)
    if tuple(nodes) != tuple(str(i) for i in range(9)):
        raise RuntimeError("unexpected server life baseline order")
    expected = tuple((name, value) for name, _kind, value in FIELDS)
    actual = tuple((child.get("name"), child.get("value")) for child in nodes["8"])
    if actual != tuple((name, str(value)) for name, value in expected):
        raise RuntimeError("server life/8 is not the reviewed Monster Park shuttle")
    if any(
        child.get("name") == "id" and child.get("value") == str(REMOVED_NPC_ID)
        for entry in nodes.values()
        for child in entry
    ):
        raise RuntimeError(f"server map still contains removed NPC {REMOVED_NPC_ID}")


def accepted_states() -> tuple[bytes, bytes, bytes]:
    client_baseline = git_baseline(CLIENT_MAP)
    server_baseline = git_baseline(SERVER_MAP)
    assert_baseline(client_baseline, server_baseline)
    installed = arc.append_property_record(client_baseline, ("life",), life_node())
    arc.verify_raw_record_insert_scope(
        client_baseline, installed, {("life", CLIENT_RECORD)}
    )
    return client_baseline, installed, server_baseline


def assert_installed(client: bytes, server: bytes) -> None:
    image = checked_client(client)
    life = image.root.get("life")
    if not isinstance(life, WzSubProperty):
        raise RuntimeError("client map is missing life")
    if tuple(child.name for child in life.children()) != tuple(str(i) for i in range(9)):
        raise RuntimeError("unexpected client life order")
    node = life.child(CLIENT_RECORD)
    if not isinstance(node, WzSubProperty) or node_values(node) != tuple(
        (name, value) for name, _kind, value in FIELDS
    ):
        raise RuntimeError("client Monster Park life node differs from contract")
    if any(str(arc.child_value(entry, "id")) == str(REMOVED_NPC_ID) for entry in life.children()):
        raise RuntimeError(f"client map still contains removed NPC {REMOVED_NPC_ID}")
    assert_baseline(git_baseline(CLIENT_MAP), server)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing")
    args = parser.parse_args()

    baseline, installed, server_baseline = accepted_states()
    current = CLIENT_MAP.read_bytes()
    if current == installed:
        changed = 0
    elif current == baseline:
        if args.check:
            raise SystemExit(f"client map is missing NPC {NPC_ID}")
        arc.atomic_write_bytes(CLIENT_MAP, installed)
        changed = 1
    else:
        raise RuntimeError(f"refusing unknown target state: {CLIENT_MAP}")

    if SERVER_MAP.read_bytes() != server_baseline:
        raise RuntimeError(f"refusing unknown server map state: {SERVER_MAP}")
    assert_installed(CLIENT_MAP.read_bytes(), SERVER_MAP.read_bytes())
    print(f"FM Monster Park NPC install ok: changed={changed} npc={NPC_ID}")
    print(f"{CLIENT_MAP.relative_to(ROOT)} sha256={sha256(CLIENT_MAP.read_bytes())}")
    print(f"{SERVER_MAP.relative_to(ROOT)} sha256={sha256(SERVER_MAP.read_bytes())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
