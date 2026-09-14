#!/usr/bin/env python3
"""Contract checks for the Free Market Monster Park shuttle."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/patch-client"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import install_fm_monster_park_npc as install  # noqa: E402
from wzpy import WzCanvasProperty, WzImage  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


def verify_map_compatibility(image: WzImage) -> None:
    for section in ("back", *(str(index) for index in range(9))):
        objects = image.root.get(section if section == "back" else f"{section}/obj")
        if objects is None:
            continue
        numbers = sorted(int(child.name) for child in objects.children() if child.name.isdigit())
        if numbers:
            assert numbers == list(range(max(numbers) + 1)), section
        if section != "back":
            for entry in objects.children():
                if install.arc.child_value(entry, "oS") == "connect":
                    assert str(install.arc.child_value(entry, "l1")) in {"0", "1", "2", "3", "4"}
                for field in ("spineAni", "questex", "tags", "timeScale"):
                    assert entry.child(field) is None, (section, entry.name, field)


def verify_npc_resource() -> int:
    path = ROOT / f"clien/Data/Npc/{install.NPC_ID}.img"
    image = WzImage.from_bytes(path.read_bytes(), key=install.arc.GMS_KEY, name=path.name)
    image.parse()
    assert not image.truncated and not image.parse_warnings
    canvases = 0
    for node, prop_path in install.arc.walk(image.root):
        if not isinstance(node, WzCanvasProperty):
            continue
        canvases += 1
        assert (int(node.format), int(node.format2)) == (1, 0), prop_path
        decoded = decode_canvas(node, region="GMS").convert("RGBA")
        assert decoded.size == (int(node.width), int(node.height)), prop_path
        assert decoded.getchannel("A").getbbox() is not None, prop_path
    assert canvases == 1

    strings = WzImage.from_bytes(
        (ROOT / "clien/Data/String/Npc.img").read_bytes(),
        key=install.arc.GMS_KEY,
        name="Npc.img",
    )
    strings.parse()
    assert not strings.truncated and not strings.parse_warnings
    assert strings.root.get(f"{install.NPC_ID}/name") is not None
    assert (ROOT / f"gms-server/wz/Npc.wz/{install.NPC_ID}.img.xml").is_file()
    assert (ROOT / "gms-server/scripts/npc/9071003.js").is_file()
    return canvases


def main() -> int:
    baseline, installed, server_baseline = install.accepted_states()
    assert install.CLIENT_MAP.read_bytes() == installed
    assert install.SERVER_MAP.read_bytes() == server_baseline
    install.arc.verify_raw_record_insert_scope(
        baseline, installed, {("life", install.CLIENT_RECORD)}
    )
    install.assert_installed(installed, server_baseline)
    verify_map_compatibility(install.checked_client(installed))
    canvases = verify_npc_resource()

    server = ET.fromstring(server_baseline)
    assert sum(
        1
        for entry in server.find("./imgdir[@name='life']")
        for child in entry
        if child.get("name") == "id" and child.get("value") == str(install.NPC_ID)
    ) == 1

    environment = (
        ROOT / "gms-server/src/main/java/soloMapling/Environment/EnvironmentManager.java"
    ).read_text(encoding="utf-8")
    auto_spawner = (
        ROOT / "gms-server/src/main/java/soloMapling/ArtificialPlayer/BotAutoSpawner.java"
    ).read_text(encoding="utf-8")
    command = (
        ROOT / "gms-server/src/main/java/org/gms/client/command/commands/gm4/EnvironmentCommand.java"
    ).read_text(encoding="utf-8")
    assert "spawnCasinoNpcs" not in environment
    assert "ensureMarketServiceNpcs" not in environment
    assert "ensureMarketServiceNpcs" not in auto_spawner
    assert "spawnrpsnpc" not in command
    assert "spawncasinonpcs" not in command
    assert "9000019" not in command

    print(
        "FM Monster Park NPC contract ok: life/8=9071003, one visible ARGB4444 "
        f"Canvas, {install.REMOVED_NPC_ID} spawn paths absent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
