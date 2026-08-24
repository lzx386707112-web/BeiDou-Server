#!/usr/bin/env python3
"""Static contract checks for the migrated Karing map music resources."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

from wzpy import WzImage, WzKey, WzSoundProperty, WzStringProperty, WzSubProperty  # noqa: E402
from wzpy.writer import _read_sound_payload  # noqa: E402

from migrate_arcane_river_fields import is_legacy_mp3_payload  # noqa: E402
from migrate_karing_p1_maps import KARING_MAP_BGM  # noqa: E402


def load(path: Path):
    image = WzImage.from_bytes(
        path.read_bytes(),
        key=WzKey.for_region("GMS"),
        name=path.name,
    )
    image.parse()
    assert not image.truncated
    assert image.parse_warnings == []
    return image


def test_karing_bgm57_contains_only_legacy_safe_tracks():
    image = load(ROOT / "clien/Data/Sound/Bgm57.img")
    assert [child.name for child in image.root.children()] == [
        "Invasion",
        "DestroyedFourSeasons",
        "FadedWinter",
        "RuinationOfFourSeasons",
    ]
    for child in image.root.children():
        assert isinstance(child, WzSoundProperty)
        assert is_legacy_mp3_payload(_read_sound_payload(child))


def test_karing_bgm00_silence_was_added():
    image = load(ROOT / "clien/Data/Sound/Bgm00.img")
    assert isinstance(image.root.child("Silence"), WzSoundProperty)
    assert is_legacy_mp3_payload(_read_sound_payload(image.root.child("Silence")))


def test_karing_map_bgm_references_match_tms():
    for map_id, reference in KARING_MAP_BGM.items():
        image = load(ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img")
        info = image.root.child("info")
        assert isinstance(info, WzSubProperty)
        bgm = info.child("bgm")
        assert isinstance(bgm, WzStringProperty)
        assert bgm.value == reference

        xml = (
            ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
        ).read_text(encoding="utf-8")
        assert f'<string name="bgm" value="{reference}"/>' in xml


def test_karing_server_sound_catalogs_exist():
    bgm57 = (ROOT / "gms-server/wz/Sound.wz/Bgm57.img.xml").read_text(encoding="utf-8")
    bgm00 = (ROOT / "gms-server/wz/Sound.wz/Bgm00.img.xml").read_text(encoding="utf-8")
    for name in ("Invasion", "DestroyedFourSeasons", "FadedWinter", "RuinationOfFourSeasons"):
        assert f'<sound name="{name}"' in bgm57
    assert '<sound name="Silence"/>' in bgm00
