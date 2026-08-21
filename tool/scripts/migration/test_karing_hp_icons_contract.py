#!/usr/bin/env python3
"""Contract checks for the Karing boss gauge icons and packet IDs."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

from wzpy import WzCanvasProperty, WzImage, WzVectorProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402

import migrate_karing_hp_icons as migration  # noqa: E402


def test_karing_boss_gauge_icons_are_legacy_safe():
    image = WzImage.from_bytes(
        migration.CLIENT_UI.read_bytes(), key=migration.p1.GMS_KEY, name="UIWindow.img"
    )
    image.parse()
    assert not image.truncated
    assert image.parse_warnings == []

    for mob_id in migration.ICON_IDS:
        icon = image.root.get(f"MobGage/Mob/{mob_id}")
        assert isinstance(icon, WzCanvasProperty)
        assert (icon.width, icon.height, icon.format, icon.format2) == (25, 25, 1, 0)
        assert icon.child("_inlink") is None
        assert icon.child("_outlink") is None
        assert icon.child("delay").value == 500
        origin = icon.child("origin")
        assert isinstance(origin, WzVectorProperty)
        assert (origin.x, origin.y) == (0, 0)
        assert decode_canvas(icon, region="GMS").getbbox() is not None


def test_karing_hp_packets_use_each_boss_id():
    source = (
        ROOT / "gms-server/src/main/java/org/gms/server/life/Monster.java"
    ).read_text(encoding="utf-8")
    mapped_case = "case 8880700, 8880803 -> 8870000;"
    assert mapped_case in source
    hp_packet_source = source[source.index("makeBossHPBarPacket"):]
    for mob_id in migration.ICON_IDS:
        assert mob_id not in hp_packet_source
