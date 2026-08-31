#!/usr/bin/env python3
"""Contract checks for the restored Morass 450006130 TMS NPC resources."""

from __future__ import annotations

import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tool/scripts/patch-client/restore_morass_450006130_npcs.py"
SPEC = importlib.util.spec_from_file_location("restore_morass_npcs", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
restore = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(restore)


def main() -> int:
    outputs, canvases = restore.build_outputs(ROOT)
    for relative, expected in outputs.items():
        assert (ROOT / relative).read_bytes() == expected, relative
    assert canvases == sum(restore.NPC_CANVASES.values()) == 127

    client_strings = restore.load_client(
        (ROOT / restore.STRING_CLIENT).read_bytes(), Path(restore.STRING_CLIENT).name
    )
    for npc_id in restore.NPC_IDS:
        assert client_strings.root.get(f"{npc_id}/name").value == restore.NPC_NAMES[npc_id]
        client = restore.load_client(
            (ROOT / f"clien/Data/Npc/{npc_id}.img").read_bytes(), f"{npc_id}.img"
        )
        server = ET.parse(ROOT / f"gms-server/wz/Npc.wz/{npc_id}.img.xml").getroot()
        expected = ET.fromstring(restore.arc.image_to_xml(client, f"{npc_id}.img"))
        assert restore.xml_signature(server) == restore.xml_signature(expected), npc_id

    for relative in restore.STRING_SERVERS:
        root = ET.parse(ROOT / relative).getroot()
        records = {int(child.get("name")): child for child in root}
        for npc_id in restore.NPC_IDS:
            name = next(
                child for child in records[npc_id] if child.get("name") == "name"
            )
            assert name.get("value") == restore.NPC_NAMES[npc_id]

    restore.verify_map_contract(ROOT)
    print(
        "Morass 450006130 NPC contract ok: 5 TMS NPCs, 127 visible "
        "ARGB4444 canvases, client/server strings synchronized"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
