#!/usr/bin/env python3
"""Add the Trend Front NPC client resources without replacing existing edits."""

from __future__ import annotations

import argparse
import io
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import WzImage, WzIntProperty, WzKey, WzStringProperty, WzSubProperty  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


NPC_ID = "9900009"
SOURCE_NPC_ID = "9120019"
NPC_NAME = "潮流前线"
TARGET_KEY = WzKey.for_region("GMS")

CLIENT_MAP = ROOT / "clien/Data/Map/Map/Map9/910000000.img"
CLIENT_STRING = ROOT / "clien/Data/String/Npc.img"
CLIENT_SOURCE_NPC = ROOT / f"clien/Data/Npc/{SOURCE_NPC_ID}.img"
CLIENT_TARGET_NPC = ROOT / f"clien/Data/Npc/{NPC_ID}.img"


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), TARGET_KEY)


def load_img(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"cannot safely rewrite {path}: {image.parse_warnings}")
    return image


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def client_map_bytes() -> tuple[bytes | None, WzImage]:
    image = load_img(CLIENT_MAP)
    life_root = image.get("life")
    if not isinstance(life_root, WzSubProperty):
        raise RuntimeError(f"{CLIENT_MAP} has no life node")

    for life in life_root.children():
        life_id = life.child("id") if isinstance(life, WzSubProperty) else None
        if isinstance(life_id, WzStringProperty) and str(life_id.value) == NPC_ID:
            return None, image

    numeric_names = [int(life.name) for life in life_root.children() if life.name.isdigit()]
    life = WzSubProperty(str(max(numeric_names, default=-1) + 1), life_root)
    life.add(WzStringProperty("type", "n", life))
    life.add(WzStringProperty("id", NPC_ID, life))
    for name, value in (
        ("mobTime", 0),
        ("f", 0),
        ("hide", 0),
        ("x", 850),
        ("y", 23),
        ("cy", 23),
        ("fh", 181),
        ("rx0", 800),
        ("rx1", 900),
    ):
        life.add(WzIntProperty(name, value, life))
    life_root.add(life)
    return encode_image_body(image, gms_reader()), image


def client_string_bytes() -> tuple[bytes | None, WzImage]:
    image = load_img(CLIENT_STRING)
    current = image.get(NPC_ID)
    if isinstance(current, WzSubProperty):
        name = current.child("name")
        if isinstance(name, WzStringProperty) and str(name.value) == NPC_NAME:
            return None, image

    entry = WzSubProperty(NPC_ID, image.root)
    entry.add(WzStringProperty("name", NPC_NAME, entry))
    image.root.add(entry)
    return encode_image_body(image, gms_reader()), image


def backup(paths: list[Path]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = Path("/private/tmp") / f"beidou-trend-front-npc-{stamp}"
    for path in paths:
        if not path.exists():
            continue
        target = destination / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return destination


def verify() -> None:
    if CLIENT_TARGET_NPC.read_bytes() != CLIENT_SOURCE_NPC.read_bytes():
        raise RuntimeError("target NPC appearance differs from source 9120019")

    map_image = load_img(CLIENT_MAP)
    life_root = map_image.get("life")
    matching = []
    if isinstance(life_root, WzSubProperty):
        for life in life_root.children():
            life_id = life.child("id") if isinstance(life, WzSubProperty) else None
            if isinstance(life_id, WzStringProperty) and str(life_id.value) == NPC_ID:
                matching.append(life)
    if len(matching) != 1:
        raise RuntimeError(f"expected one {NPC_ID} life node, found {len(matching)}")
    expected_life = {
        "x": 850,
        "y": 23,
        "cy": 23,
        "fh": 181,
        "rx0": 800,
        "rx1": 900,
    }
    for property_name, expected_value in expected_life.items():
        prop = matching[0].child(property_name)
        if not isinstance(prop, WzIntProperty) or int(prop.value) != expected_value:
            raise RuntimeError(f"client map {property_name} verification failed")

    name = load_img(CLIENT_STRING).get(f"{NPC_ID}/name")
    if not isinstance(name, WzStringProperty) or str(name.value) != NPC_NAME:
        raise RuntimeError("client NPC name verification failed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write validated client resources")
    args = parser.parse_args()

    source_bytes = CLIENT_SOURCE_NPC.read_bytes()
    if CLIENT_TARGET_NPC.exists() and CLIENT_TARGET_NPC.read_bytes() != source_bytes:
        raise RuntimeError(f"refusing to replace existing {CLIENT_TARGET_NPC}")

    map_bytes, _ = client_map_bytes()
    string_bytes, _ = client_string_bytes()
    planned = []
    if not CLIENT_TARGET_NPC.exists():
        planned.append(CLIENT_TARGET_NPC)
    if map_bytes is not None:
        planned.append(CLIENT_MAP)
    if string_bytes is not None:
        planned.append(CLIENT_STRING)

    if not args.apply:
        for path in planned:
            print(path.relative_to(ROOT))
        if not planned:
            verify()
            print("verification passed; resources already up to date")
        print("dry-run complete; pass --apply to write outputs")
        return 0

    backup_dir = backup([CLIENT_MAP, CLIENT_STRING])
    if not CLIENT_TARGET_NPC.exists():
        atomic_write(CLIENT_TARGET_NPC, source_bytes)
    if map_bytes is not None:
        atomic_write(CLIENT_MAP, map_bytes)
    if string_bytes is not None:
        atomic_write(CLIENT_STRING, string_bytes)
    verify()
    print(f"verification passed; backup={backup_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
