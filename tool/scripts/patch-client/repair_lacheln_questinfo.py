#!/usr/bin/env python3
"""Rebuild Lacheln QuestInfo from a clean baseline with raw record inserts."""

from __future__ import annotations

import argparse
import hashlib
import io
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wzpy import (  # noqa: E402
    WzImage,
    WzIntProperty,
    WzKey,
    WzStringProperty,
    WzSubProperty,
)
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import (  # noqa: E402
    _encode_property_list,
    encode_compressed_int,
)

from repair_arcane_river_8641002_attack_gap import (  # noqa: E402
    PropertyList,
    Record,
    read_property_list,
)


TARGET = ROOT / "clien/Data/Quest/QuestInfo.img"
BASELINE = ROOT / "clien/Data/Quest/QuestInfo.img.bak3"
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
BACKUP = Path("/private/tmp/beidou-lacheln-questinfo-backup/QuestInfo.img")
BASELINE_SHA256 = "da8a6d935dcb48b26c5163fe55c92c6204b557e49cc8009ef10cd1ec80010998"
QUEST_IDS = tuple(range(34300, 34333))
LEGACY_FIELDS = ("name", "0", "1", "2", "area")
FORBIDDEN_SIGNED_CHUCHU_IDS = {
    str(quest_id - 65536) for quest_id in range(34200, 34219)
}
BMS_KEY = WzKey.for_region("BMS")
GMS_KEY = WzKey.for_region("GMS")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_image(data: bytes, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"malformed {name}: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    return image


def locate_root(data: bytes) -> PropertyList:
    reader = WzBinaryReader(io.BytesIO(data), GMS_KEY)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError("unsupported IMG header")
    reader.skip(2)
    return read_property_list(reader, len(data))


def encode_property_record(image: WzImage, prop) -> bytes:
    encoded = _encode_property_list((prop,), image.wz_file.reader)
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError(f"unexpected encoded {prop.name} record prefix")
    return encoded[len(prefix):]


def record_bytes(data: bytes, records: tuple[Record, ...]) -> dict[str, bytes]:
    return {record.name: data[record.start:record.end] for record in records}


def clone_legacy_field(source, parent):
    if isinstance(source, WzStringProperty):
        return WzStringProperty(source.name, source.value, parent)
    if isinstance(source, WzIntProperty):
        return WzIntProperty(source.name, source.value, parent)
    raise RuntimeError(
        f"unsupported QuestInfo field type: {source.name}={type(source).__name__}"
    )


def legacy_quest_node(quest_id: int, target_image) -> WzSubProperty:
    source_path = SOURCE / f"Quest/QuestData/{quest_id}.img"
    source = WzImage.from_file(str(source_path), key=BMS_KEY)
    source.parse()
    if source.truncated or source.parse_warnings:
        raise RuntimeError(
            f"malformed TMS QuestInfo {quest_id}: "
            f"truncated={source.truncated} warnings={source.parse_warnings}"
        )
    source_info = source.root.get("QuestInfo")
    if not isinstance(source_info, WzSubProperty):
        raise RuntimeError(f"missing TMS QuestInfo for {quest_id}")
    output = WzSubProperty(str(quest_id), target_image.root)
    for name in LEGACY_FIELDS:
        child = source_info.child(name)
        if child is not None:
            output.add(clone_legacy_field(child, output))
    if tuple(child.name for child in output.children()) != LEGACY_FIELDS:
        raise RuntimeError(f"incomplete legacy QuestInfo fields for {quest_id}")
    return output


def build_expected() -> tuple[bytes, tuple[str, ...]]:
    baseline = BASELINE.read_bytes()
    if sha256(baseline) != BASELINE_SHA256:
        raise RuntimeError("QuestInfo.img.bak3 is not the verified clean baseline")
    image = load_image(baseline, BASELINE.name)
    roots = locate_root(baseline)
    baseline_names = tuple(record.name for record in roots.records)
    insert_names = tuple(str(quest_id) for quest_id in QUEST_IDS if str(quest_id) not in baseline_names)
    if insert_names != (
        "34300", "34301", "34302", "34305", "34306", "34307", "34308", "34309",
        "34310", "34311", "34316", "34317", "34318", "34319", "34320", "34321",
        "34322", "34323", "34324", "34325", "34326", "34327", "34328", "34329",
        "34330", "34331", "34332",
    ):
        raise RuntimeError(f"unexpected Lacheln QuestInfo baseline set: {insert_names}")

    encoded = b"".join(
        encode_property_record(image, legacy_quest_node(int(name), image))
        for name in insert_names
    )
    position = roots.records[-1].end
    updated = bytearray(baseline[:position] + encoded + baseline[position:])
    encoded_count = encode_compressed_int(roots.count + len(insert_names))
    if len(encoded_count) != roots.count_length:
        raise RuntimeError("QuestInfo root count encoding width changed")
    updated[roots.count_offset:roots.count_offset + roots.count_length] = encoded_count
    result = bytes(updated)
    verify_expected(baseline, result, insert_names)
    return result, insert_names


def verify_expected(baseline: bytes, result: bytes, insert_names: tuple[str, ...]) -> None:
    image = load_image(result, TARGET.name)
    before = locate_root(baseline)
    after = locate_root(result)
    before_raw = record_bytes(baseline, before.records)
    after_raw = record_bytes(result, after.records)
    if tuple(after_raw) != (*tuple(before_raw), *insert_names):
        raise RuntimeError("QuestInfo record order is not baseline plus approved inserts")
    for name, raw in before_raw.items():
        if after_raw.get(name) != raw:
            raise RuntimeError(f"unapproved QuestInfo record changed: {name}")
    if set(after_raw) - set(before_raw) != set(insert_names):
        raise RuntimeError("QuestInfo changed outside the approved Lacheln ID set")
    if FORBIDDEN_SIGNED_CHUCHU_IDS & set(after_raw):
        raise RuntimeError("signed Chu Chu duplicates remain in client QuestInfo")
    for name in insert_names:
        node = image.root.child(name)
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"missing inserted QuestInfo record: {name}")
        if tuple(child.name for child in node.children()) != LEGACY_FIELDS:
            raise RuntimeError(f"unsupported QuestInfo fields remain: {name}")


def atomic_write(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing")
    args = parser.parse_args()
    expected, insert_names = build_expected()
    current = TARGET.read_bytes()
    changed = current != expected
    if args.check and changed:
        raise SystemExit("Lacheln QuestInfo needs repair")
    if changed:
        if not BACKUP.exists():
            BACKUP.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(TARGET, BACKUP)
        atomic_write(TARGET, expected)
    print(
        f"Lacheln QuestInfo ok: changed={changed} records={len(locate_root(expected).records)} "
        f"inserted={len(insert_names)} sha256={sha256(expected)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
