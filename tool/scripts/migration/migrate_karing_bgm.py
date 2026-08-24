#!/usr/bin/env python3
"""Restore TMS Karing map BGM and add the legacy-compatible Bgm57 pack."""

from __future__ import annotations

import argparse
import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
sys.path.insert(0, str(ROOT / "tool" / "scripts" / "migration"))

from wzpy import WzImage, WzKey, WzSoundProperty, WzStringProperty, WzSubProperty  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import (  # noqa: E402
    _read_sound_payload,
    encode_compressed_int,
    encode_image_body,
)

from migrate_arcane_river_fields import image_to_xml, is_legacy_mp3_payload  # noqa: E402
from migrate_karing_p1_maps import (  # noqa: E402
    GMS_KEY,
    BMS_KEY,
    KARING_MAP_BGM,
    atomic_write_bytes,
    atomic_write_text,
    encode_root_record,
    gms_reader,
    locate_root_records,
    load_image,
)


TARGET_TRACKS = (
    "Invasion",
    "DestroyedFourSeasons",
    "FadedWinter",
    "RuinationOfFourSeasons",
)


def transcode_legacy_mp3(source: WzSoundProperty) -> bytes:
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "mp3", "-i", "pipe:0", "-map_metadata", "-1",
            "-codec:a", "libmp3lame", "-ar", "22050", "-ac", "2",
            "-b:a", "64k", "-write_xing", "0", "-id3v2_version", "0",
            "-write_id3v1", "0", "-f", "mp3", "pipe:1",
        ],
        input=_read_sound_payload(source),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or not is_legacy_mp3_payload(result.stdout):
        raise RuntimeError(
            f"legacy MP3 transcode failed for {source.name}: "
            f"{result.stderr.decode('utf-8', 'replace').strip()}"
        )
    return result.stdout


def clone_sound(source: WzSoundProperty, parent: WzSubProperty, header: bytes) -> WzSoundProperty:
    output = WzSoundProperty(source.name, parent)
    output.length_ms = source.length_ms
    output.header = header
    output._data_offset = 0
    output._data = transcode_legacy_mp3(source)
    output._data_length = len(output._data)
    return output


def write_bgm57() -> None:
    source_path = SOURCE / "Sound/Bgm57.img"
    source = load_image(source_path, BMS_KEY)
    template = load_image(ROOT / "clien/Data/Sound/Bgm12.img", GMS_KEY)
    legacy_template = template.root.get("AquaCave")
    if not isinstance(legacy_template, WzSoundProperty):
        raise RuntimeError("Bgm12/AquaCave is missing as the legacy sound template")

    root = WzSubProperty("Bgm57.img")
    for track in TARGET_TRACKS:
        sound = source.root.get(track)
        if not isinstance(sound, WzSoundProperty):
            raise RuntimeError(f"TMS Bgm57/{track} is missing")
        root.add(clone_sound(sound, root, bytes(legacy_template.header)))

    source._root = root
    source._parsed = True
    target = ROOT / "clien/Data/Sound/Bgm57.img"
    atomic_write_bytes(target, encode_image_body(source, gms_reader()))
    atomic_write_text(
        ROOT / "gms-server/wz/Sound.wz/Bgm57.img.xml",
        image_to_xml(source, "Bgm57.img"),
    )


def patch_bgm00_silence() -> None:
    source = load_image(SOURCE / "Sound/Bgm00.img", BMS_KEY)
    target_path = ROOT / "clien/Data/Sound/Bgm00.img"
    original = target_path.read_bytes()
    target = WzImage.from_bytes(original, key=GMS_KEY, name=target_path.name)
    target.parse()
    names, spans = locate_root_records(original, target_path)
    raw_records = {
        name: original[start:end] for name, (start, end) in zip(names, spans)
    }
    existing = target.root.child("Silence")
    if existing is not None:
        if not isinstance(existing, WzSoundProperty):
            raise RuntimeError(f"{target_path}: Silence is not a sound")
        return

    template = load_image(ROOT / "clien/Data/Sound/Bgm12.img", GMS_KEY).root.get("AquaCave")
    source_sound = source.root.get("Silence")
    if not isinstance(template, WzSoundProperty) or not isinstance(source_sound, WzSoundProperty):
        raise RuntimeError("missing Bgm12/AquaCave or TMS Bgm00/Silence")
    silence = clone_sound(source_sound, target.root, bytes(template.header))
    record = encode_root_record(silence)

    reader = WzBinaryReader(io.BytesIO(original), GMS_KEY)
    reader.read_byte()
    reader.read_string()
    reader.skip(2)
    count_offset = reader.position
    count = reader.read_compressed_int()
    records_start = reader.position
    if count != len(names) or records_start != spans[0][0] or spans[-1][1] != len(original):
        raise RuntimeError(f"{target_path}: unexpected root record layout")
    updated = (
        original[:count_offset]
        + encode_compressed_int(count + 1)
        + original[records_start:]
        + record
    )
    verified = WzImage.from_bytes(updated, key=GMS_KEY, name=target_path.name)
    verified.parse()
    if verified.truncated or verified.parse_warnings or not isinstance(verified.root.child("Silence"), WzSoundProperty):
        raise RuntimeError(f"{target_path}: Bgm00/Silence did not round-trip")
    atomic_write_bytes(target_path, updated)

    server_path = ROOT / "gms-server/wz/Sound.wz/Bgm00.img.xml"
    server_text = server_path.read_text(encoding="utf-8")
    if '<sound name="Silence"' not in server_text:
        marker = "</imgdir>"
        server_text = server_text.replace(
            marker,
            '<sound name="Silence"/>\n' + marker,
            1,
        )
        atomic_write_text(server_path, server_text)


def patch_map_bgm(map_id: int, reference: str) -> None:
    client_path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
    original = client_path.read_bytes()
    image = WzImage.from_bytes(original, key=GMS_KEY, name=client_path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{client_path}: truncated={image.truncated} warnings={image.parse_warnings}")

    names, spans = locate_root_records(original, client_path)
    raw_records = {
        name: original[start:end] for name, (start, end) in zip(names, spans)
    }
    info = image.root.child("info")
    if not isinstance(info, WzSubProperty) or "info" not in raw_records:
        raise RuntimeError(f"{client_path}: missing info root")
    if encode_root_record(info) != raw_records["info"]:
        raise RuntimeError(f"{client_path}: info root is not reproducible before BGM patch")

    current = info.child("bgm")
    if isinstance(current, WzStringProperty) and current.value == reference:
        return
    if current is not None:
        info._children.pop("bgm", None)
    info.add(WzStringProperty("bgm", reference, info))
    replacement = encode_root_record(info)
    rebuilt = b"".join(
        replacement if name == "info" else raw_records[name] for name in names
    )
    records_start, records_end = spans[0][0], spans[-1][1]
    updated = original[:records_start] + rebuilt + original[records_end:]

    verified = WzImage.from_bytes(updated, key=GMS_KEY, name=client_path.name)
    verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise RuntimeError(f"{client_path}: malformed BGM patch {verified.parse_warnings}")
    verified_info = verified.root.child("info")
    if not isinstance(verified_info, WzSubProperty) or verified_info.child("bgm").value != reference:
        raise RuntimeError(f"{client_path}: BGM reference did not round-trip")
    atomic_write_bytes(client_path, updated)


def patch_server_map_bgm(map_id: int, reference: str) -> None:
    path = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
    text = path.read_text(encoding="utf-8")
    if re.search(r'<string name="bgm" value="[^"]*"\s*/>', text):
        text = re.sub(
            r'<string name="bgm" value="[^"]*"\s*/>',
            f'<string name="bgm" value="{reference}"/>',
            text,
            count=1,
        )
    else:
        marker = "  </imgdir>"
        info_start = text.find('  <imgdir name="info">')
        info_end = text.find(marker, info_start)
        if info_start < 0 or info_end < 0:
            raise RuntimeError(f"{path}: missing info imgdir")
        text = text[:info_end] + f'    <string name="bgm" value="{reference}"/>\n' + text[info_end:]
    atomic_write_text(path, text)


def verify() -> None:
    bgm = load_image(ROOT / "clien/Data/Sound/Bgm57.img", GMS_KEY)
    if tuple(child.name for child in bgm.root.children()) != TARGET_TRACKS:
        raise RuntimeError("Bgm57 track order/content mismatch")
    for child in bgm.root.children():
        if not isinstance(child, WzSoundProperty) or not is_legacy_mp3_payload(_read_sound_payload(child)):
            raise RuntimeError(f"Bgm57/{child.name}: invalid legacy MP3 payload")
    for map_id, reference in KARING_MAP_BGM.items():
        path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        image = load_image(path, GMS_KEY)
        info = image.root.child("info")
        bgm = info.child("bgm") if isinstance(info, WzSubProperty) else None
        if not isinstance(bgm, WzStringProperty) or bgm.value != reference:
            raise RuntimeError(f"{path}: missing BGM {reference}")


def migrate() -> None:
    write_bgm57()
    patch_bgm00_silence()
    for map_id, reference in KARING_MAP_BGM.items():
        patch_map_bgm(map_id, reference)
        patch_server_map_bgm(map_id, reference)
    verify()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    verify() if args.verify_only else migrate()
