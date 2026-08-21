#!/usr/bin/env python3
"""Export a deterministic, read-only equipment catalog and icon atlases.

The exporter only parses existing client IMG files and server XML files. It
never serializes an IMG/WZ tree back to disk. Decoded icons are cached by the
source IMG SHA-256 so unchanged records do not need to be decoded again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool/wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.properties import WzCanvasProperty  # noqa: E402


CLIENT_CHARACTER = ROOT / "clien/Data/Character"
SERVER_CHARACTER = ROOT / "gms-server/wz/Character.wz"
EQUIPMENT_STRINGS = ROOT / "gms-server/wz/String.wz/Eqp.img.xml"
OUTPUT_DIR = ROOT / "gms-server/src/main/resources/equipment-catalog"
CACHE_DIR = ROOT / ".cache/equipment-catalog"
CELL_SIZE = 48
MAX_COLUMNS = 80
GMS_KEY = WzKey.for_region("GMS")
CATEGORY_ORDER = (
    "Weapon",
    "Cap",
    "Coat",
    "Longcoat",
    "Pants",
    "Shoes",
    "Glove",
    "Cape",
    "Shield",
    "Accessory",
    "Ring",
    "PetEquip",
    "Taming",
    "Dragon",
)

STAT_NAMES = {
    "tuc",
    "cash",
    "gender",
    "tradeBlock",
    "only",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0,
                        help="export at most this many items per category")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--cache", type=Path, default=CACHE_DIR)
    return parser.parse_args()


def child_named(node: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in node if child.attrib.get("name") == name), None)


def equipment_strings() -> dict[str, list[dict[str, object]]]:
    root = ET.parse(EQUIPMENT_STRINGS).getroot()
    eqp = child_named(root, "Eqp")
    if eqp is None:
        raise RuntimeError(f"missing Eqp root in {EQUIPMENT_STRINGS}")
    candidates: dict[int, list[dict[str, object]]] = {}
    for category_node in eqp:
        category = category_node.attrib.get("name", "")
        for item_node in category_node:
            raw_id = item_node.attrib.get("name", "")
            if not raw_id.isdigit():
                continue
            item_id = int(raw_id)
            if not 1_000_000 <= item_id < 2_000_000:
                continue
            name_node = child_named(item_node, "name")
            if name_node is None or not name_node.attrib.get("value", "").strip():
                continue
            desc_node = child_named(item_node, "desc")
            candidates.setdefault(item_id, []).append({
                "id": item_id,
                "name": name_node.attrib["value"].strip(),
                "desc": desc_node.attrib.get("value", "").strip()
                if desc_node is not None else "",
                "category": category,
            })
    result: dict[str, list[dict[str, object]]] = {}
    for item_id, choices in candidates.items():
        category = display_category(str(choices[0]["category"]), item_id)
        selected = next(
            (choice for choice in choices if choice["category"] == category),
            choices[0],
        ).copy()
        selected["category"] = category
        result.setdefault(category, []).append(selected)
    for items in result.values():
        items.sort(key=lambda item: int(item["id"]))
    return result


def display_category(category: str, item_id: int) -> str:
    prefix = item_id // 10_000
    fixed = {
        100: "Cap",
        104: "Coat",
        105: "Longcoat",
        106: "Pants",
        107: "Shoes",
        108: "Glove",
        109: "Shield",
        110: "Cape",
        111: "Ring",
        180: "PetEquip",
    }
    if prefix in fixed:
        return fixed[prefix]
    if 101 <= prefix <= 103 or 112 <= prefix <= 119:
        return "Accessory"
    if 121 <= prefix <= 160 or prefix == 170:
        return "Weapon"
    if 190 <= prefix <= 193 or 198 <= prefix <= 199:
        return "Taming"
    if 194 <= prefix <= 197:
        return "Dragon"
    return category


def equipment_directory(category: str, item_id: int) -> str:
    category = display_category(category, item_id)
    return "TamingMob" if category == "Taming" else category


def item_paths(category: str, item_id: int) -> tuple[Path, Path]:
    directory = equipment_directory(category, item_id)
    stem = f"{item_id:08d}.img"
    return (
        CLIENT_CHARACTER / directory / stem,
        SERVER_CHARACTER / directory / f"{stem}.xml",
    )


def equipment_stats(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {}
    root = ET.parse(path).getroot()
    info = child_named(root, "info")
    if info is None:
        return {}
    result: dict[str, int] = {}
    for node in info:
        name = node.attrib.get("name", "")
        value = node.attrib.get("value")
        if value is None or not (
            name.startswith("inc") or name.startswith("req") or name in STAT_NAMES
        ):
            continue
        try:
            result[name] = int(value)
        except ValueError:
            continue
    return result


def decode_icon(path: Path, cache_root: Path, category: str) -> Image.Image | None:
    if not path.is_file():
        return None
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    cache_path = cache_root / category / f"{path.stem}-{digest[:20]}.png"
    if cache_path.is_file():
        with Image.open(cache_path) as cached:
            return cached.convert("RGBA")

    image = WzImage.from_bytes(data, key=GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        return None
    canvas = image.root.get("info/icon")
    if not isinstance(canvas, WzCanvasProperty):
        canvas = image.root.get("info/iconRaw")
    if not isinstance(canvas, WzCanvasProperty):
        return None
    try:
        icon = decode_canvas(canvas, region="GMS").convert("RGBA")
    except Exception:
        return None
    if icon.getbbox() is None:
        return None
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    icon.save(cache_path, format="PNG", optimize=False, compress_level=9)
    return icon


def fit_icon(icon: Image.Image) -> Image.Image:
    maximum = CELL_SIZE - 6
    if icon.width <= maximum and icon.height <= maximum:
        return icon
    resized = icon.copy()
    resized.thumbnail((maximum, maximum), Image.Resampling.LANCZOS)
    return resized


def export_category(
    category: str,
    items: list[dict[str, object]],
    output_dir: Path,
    cache_dir: Path,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    columns = min(MAX_COLUMNS, max(1, math.ceil(math.sqrt(len(items)))))
    rows = math.ceil(len(items) / columns)
    atlas = Image.new("RGBA", (columns * CELL_SIZE, rows * CELL_SIZE), (0, 0, 0, 0))
    exported: list[dict[str, object]] = []
    icon_count = 0

    for index, source in enumerate(items):
        item_id = int(source["id"])
        x = (index % columns) * CELL_SIZE
        y = (index // columns) * CELL_SIZE
        client_path, server_path = item_paths(category, item_id)
        icon = decode_icon(client_path, cache_dir, category)
        has_icon = icon is not None
        if icon is not None:
            icon = fit_icon(icon)
            atlas.alpha_composite(icon, (x + (CELL_SIZE - icon.width) // 2,
                                         y + (CELL_SIZE - icon.height) // 2))
            icon_count += 1
        exported.append({
            **source,
            "stats": equipment_stats(server_path),
            "icon": has_icon,
            "x": x,
            "y": y,
        })

    atlas_dir = output_dir / "atlases"
    atlas_dir.mkdir(parents=True, exist_ok=True)
    atlas.save(atlas_dir / f"{category}.png", format="PNG", optimize=False,
               compress_level=9)
    return exported, {
        "count": len(items),
        "icons": icon_count,
        "width": atlas.width,
        "height": atlas.height,
    }


def export(args: argparse.Namespace) -> None:
    categories = equipment_strings()
    args.output.mkdir(parents=True, exist_ok=True)
    all_items: list[dict[str, object]] = []
    atlases: dict[str, dict[str, int]] = {}
    ordered_categories = sorted(
        categories,
        key=lambda category: CATEGORY_ORDER.index(category)
        if category in CATEGORY_ORDER else len(CATEGORY_ORDER),
    )
    for category in ordered_categories:
        source_items = categories[category]
        items = source_items[:args.limit] if args.limit > 0 else source_items
        exported, atlas = export_category(
            category, items, args.output, args.cache
        )
        all_items.extend(exported)
        atlases[category] = atlas
        print(
            f"{category}: {atlas['icons']}/{atlas['count']} icons, "
            f"{atlas['width']}x{atlas['height']}",
            flush=True,
        )

    payload = {
        "version": 1,
        "cellSize": CELL_SIZE,
        "atlases": atlases,
        "items": all_items,
    }
    (args.output / "catalog.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"catalog: {len(all_items)} items -> {args.output}", flush=True)


if __name__ == "__main__":
    export(parse_args())
