#!/usr/bin/env python3
"""Contract checks for repaired Tenebris maps and NPC 3003907."""

from __future__ import annotations

import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tool/scripts/patch-client/repair_tenebris_crash_maps.py"
SPEC = importlib.util.spec_from_file_location("repair_tenebris_crash_maps", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
repair = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(repair)


def main() -> int:
    outputs, canvases = repair.build_outputs(ROOT)
    for relative, expected in outputs.items():
        assert (ROOT / relative).read_bytes() == expected, relative
    assert canvases == 91

    map_301 = repair.load_client(
        (ROOT / repair.MAP_301_CLIENT).read_bytes(), "450009301.img"
    )
    server_301 = ET.parse(ROOT / repair.MAP_301_SERVER).getroot()
    for name in repair.MAP_301_SERVER_BLOCKS:
        client = ET.fromstring(repair.arc.property_to_xml(map_301.root.child(name), 0))
        server = next(child for child in server_301 if child.get("name") == name)
        assert repair.xml_signature(client) == repair.xml_signature(server), name

    map_990 = repair.load_client(
        (ROOT / repair.MAP_990_CLIENT).read_bytes(), "450011990.img"
    )
    for path in repair.MAP_990_REMOVALS:
        assert map_990.root.get("/".join(path)) is None, path
    repair.verify_map_990_contract(ROOT, (ROOT / repair.MAP_990_CLIENT).read_bytes())

    npc = repair.load_client((ROOT / repair.NPC_CLIENT).read_bytes(), "3003907.img")
    npc_canvases = [
        node for node in repair.walk(npc.root)
        if isinstance(node, repair.WzCanvasProperty)
    ]
    assert len(npc_canvases) == 91
    assert all((int(node.format), int(node.format2)) == (1, 0) for node in npc_canvases)
    assert all(
        node.child("_outlink") is None and node.child("_inlink") is None
        for node in npc_canvases
    )
    ET.parse(ROOT / repair.NPC_SERVER)

    client_strings = repair.load_client(
        (ROOT / repair.NPC_STRING_CLIENT).read_bytes(), "Npc.img"
    )
    assert client_strings.root.get(f"{repair.NPC_ID}/name").value == "墮落勇士"
    for relative in repair.NPC_STRING_SERVERS:
        root = ET.parse(ROOT / relative).getroot()
        record = next(child for child in root if child.get("name") == str(repair.NPC_ID))
        name = next(child for child in record if child.get("name") == "name")
        assert name.get("value") == "墮落勇士"

    print(
        "Tenebris crash-map contract ok: 450009301 runtime blocks synchronized; "
        "450011990 legacy-safe; NPC 3003907 materialized with 91 ARGB4444 canvases"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
