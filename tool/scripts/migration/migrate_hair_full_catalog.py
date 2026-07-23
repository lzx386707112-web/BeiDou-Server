#!/usr/bin/env python3
"""Migrate the complete modern Hair catalog into old-client-safe IDs.

Rules:
- Keep only complete 0..7 color families.
- Keep complete 3xxxx/4xxxx/6xxxx families at their source IDs.
- Move complete 71xxx families, in order, onto the earliest recognizable
  family slots. The target ID stays stable while its visual/name changes.
- Materialize hierarchical ``_outlink`` canvas pixels and encode GMS IMG.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
import zlib
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.canvas import _decompress  # noqa: E402
from wzpy.properties import (  # noqa: E402
    WzCanvasProperty,
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
)
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_image_body, encode_image_body_compact  # noqa: E402


SOURCE = Path("/Users/lizixian/Documents/mxd/MapleStory-IMG/Data")
SOURCE_HAIR = SOURCE / "Character/Hair"
SOURCE_STRING = SOURCE / "String/Eqp.img"
CLIENT_HAIR = ROOT / "clien/Data/Character/Hair"
CLIENT_STRING = ROOT / "clien/Data/String/Eqp.img"
CLIENT_MAKE_CHAR = ROOT / "clien/Data/Etc/MakeCharInfo.img"
SERVER_HAIR = ROOT / "gms-server/wz/Character.wz/Hair"
SERVER_STRING = ROOT / "gms-server/wz/String.wz/Eqp.img.xml"
SERVER_MAKE_CHARS = (
    ROOT / "gms-server/wz/Etc.wz/MakeCharInfo.img.xml",
    ROOT / "gms-server/wz-zh-CN/Etc.wz/MakeCharInfo.img.xml",
)
HANDBOOK = ROOT / "gms-server/handbook/Equip/Hair.txt"
HAIR_BASE_RESOURCE = ROOT / "gms-server/src/main/resources/hair-base-ids.txt"
DB_MIGRATION = ROOT / "gms-server/src/main/resources/db/migration/V2.1.29__migrate_full_hair_catalog.sql"
MAPPING_CSV = ROOT / "docs/migrations/hair-full-id-map.csv"
REPORT_JSON = ROOT / "docs/migrations/hair-full-migration.json"
WORK = Path("/private/tmp/beidou-hair-full-migration")
STAGING = WORK / "staging/Hair"
BACKUP = WORK / "backup"

BMS_KEY = WzKey.for_region("BMS")
GMS_KEY = WzKey.for_region("GMS")
RECOGNIZED_PREFIXES = {3, 4, 6}
MALE_DEFAULTS = [30290, 30300, 30310]
FEMALE_DEFAULTS = [31000, 31040, 31050]
HAIR_ID_RE = re.compile(r"\b[3467]\d{4}\b")
HAIR_CONTEXT_RE = re.compile(
    r"setHair|getHair|hairnew|haircolor|mhair|fhair|newHairs|hairColors|baseHair|HAIR_",
    re.I,
)
SCRIPT_HAIR_ID_REMAP = {
    30437: 30747,  # male bald style
    31437: 35487,  # female bald style
}


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        temp = Path(tmp.name)
    temp.replace(path)


def atomic_write_text(path: Path, data: str) -> None:
    atomic_write_bytes(path, data.encode("utf-8"))


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), GMS_KEY)


def source_groups(source_hair: Path) -> dict[int, set[int]]:
    groups: dict[int, set[int]] = defaultdict(set)
    for path in source_hair.glob("*.img"):
        hair_id = int(path.stem)
        groups[(hair_id // 10) * 10].add(hair_id % 10)
    return dict(groups)


def is_complete(colors: set[int]) -> bool:
    return set(range(8)) <= colors


def build_catalog(source_hair: Path) -> dict:
    groups = source_groups(source_hair)
    complete = {base for base, colors in groups.items() if is_complete(colors)}
    incomplete = sorted(set(groups) - complete)
    recognized = sorted(base for base in complete if base // 10000 in RECOGNIZED_PREFIXES)
    overflow = sorted(base for base in complete if base // 10000 not in RECOGNIZED_PREFIXES)
    if not overflow or any(base // 10000 != 7 for base in overflow):
        raise RuntimeError(f"unexpected overflow families: {overflow[:20]}")

    recognizable_slots = sorted(base for base in groups if base // 10000 in RECOGNIZED_PREFIXES)
    targets = recognizable_slots[: len(overflow)]
    target_to_source = {base: base for base in recognized}
    for source_base, target_base in zip(overflow, targets, strict=True):
        target_to_source[target_base] = source_base

    target_to_source = dict(sorted(target_to_source.items()))
    if any(base // 10000 not in RECOGNIZED_PREFIXES for base in target_to_source):
        raise RuntimeError("final catalog contains unrecognized target IDs")
    if any(not is_complete(groups[source]) for source in target_to_source.values()):
        raise RuntimeError("final catalog references an incomplete source family")

    overwritten = [base for base in targets if base in complete]
    reused_incomplete = [base for base in targets if base in incomplete]
    dropped_incomplete = [base for base in incomplete if base not in targets]
    return {
        "groups": groups,
        "target_to_source": target_to_source,
        "overflow": overflow,
        "targets": targets,
        "overwritten": overwritten,
        "reused_incomplete": reused_incomplete,
        "dropped_incomplete": dropped_incomplete,
        "suffix_8_9": sorted(
            int(path.stem)
            for path in source_hair.glob("*.img")
            if int(path.stem) % 10 > 7
        ),
    }


def walk(node):
    yield node
    if hasattr(node, "children"):
        for child in node.children():
            yield from walk(child)


def load_image(path: Path, key: WzKey) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=key, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"parse warning in {path}: {image.parse_warnings}")
    return image


def materialize_one(task: tuple[str, int, int, str]) -> tuple[int, int, int, int]:
    source_hair_raw, source_id, target_id, staging_raw = task
    source_hair = Path(source_hair_raw)
    staging = Path(staging_raw)
    main_path = source_hair / f"{source_id:08d}.img"
    image = load_image(main_path, BMS_KEY)
    canvas_cache: dict[str, WzImage] = {}
    outlinks = 0
    canvases = 0

    for node in walk(image.root):
        if not isinstance(node, WzCanvasProperty):
            continue
        canvases += 1
        outlink = node.child("_outlink")
        if not isinstance(outlink, WzStringProperty):
            continue
        value = str(outlink.value).replace("\\", "/")
        match = re.fullmatch(r"Character/Hair/_Canvas/([^/]+\.img)/(.+)", value)
        if match is None:
            raise RuntimeError(f"unsupported Hair outlink {main_path.name}: {value}")
        canvas_name, property_path = match.groups()
        linked_image = canvas_cache.get(canvas_name)
        if linked_image is None:
            linked_image = load_image(source_hair / "_Canvas" / canvas_name, BMS_KEY)
            canvas_cache[canvas_name] = linked_image
        linked = linked_image.root.get(property_path)
        if not isinstance(linked, WzCanvasProperty) or not linked.has_pixels():
            raise RuntimeError(f"unresolved Hair outlink {main_path.name}: {value}")

        payload = zlib.compress(_decompress(linked, BMS_KEY), 9)
        node.width = linked.width
        node.height = linked.height
        node.format = linked.format
        node.format2 = linked.format2
        node._png_data = payload
        node._png_length = len(payload)
        node._png_offset = 0
        del node._children["_outlink"]
        outlinks += 1

    # Direct canvases also benefit from deterministic level-9 zlib.  This
    # preserves their exact packed pixel bytes while dropping listWz chunk
    # overhead and weaker source compression.
    for node in walk(image.root):
        if not isinstance(node, WzCanvasProperty) or node._png_data is not None:
            continue
        if node.has_pixels():
            payload = zlib.compress(_decompress(node, BMS_KEY), 9)
            node._png_data = payload
            node._png_length = len(payload)
            node._png_offset = 0

    if any(
        isinstance(node, WzCanvasProperty) and node.child("_outlink") is not None
        for node in walk(image.root)
    ):
        raise RuntimeError(f"outlinks remain in {main_path.name}")

    output = encode_image_body_compact(image, gms_reader())
    output_path = staging / f"{target_id:08d}.img"
    atomic_write_bytes(output_path, output)
    return target_id, canvases, outlinks, len(output)


def tasks_for_catalog(source_hair: Path, catalog: dict, staging: Path):
    for target_base, source_base in catalog["target_to_source"].items():
        for color in range(8):
            yield (str(source_hair), source_base + color, target_base + color, str(staging))


def source_names(source_string: Path) -> dict[int, str]:
    image = load_image(source_string, BMS_KEY)
    hair = image.root.get("Eqp/Hair")
    if not isinstance(hair, WzSubProperty):
        raise RuntimeError("source String/Eqp.img has no Eqp/Hair")
    result: dict[int, str] = {}
    for node in hair.children():
        if not node.name.isdigit():
            continue
        name = node.child("name")
        if isinstance(name, WzStringProperty):
            result[int(node.name)] = str(name.value)
    return result


def final_names(catalog: dict, names: dict[int, str]) -> dict[int, str]:
    result: dict[int, str] = {}
    for target_base, source_base in catalog["target_to_source"].items():
        for color in range(8):
            target_id = target_base + color
            source_id = source_base + color
            result[target_id] = names.get(source_id, f"发型 {target_id}")
    return result


def write_reports(catalog: dict, names: dict[int, str]) -> None:
    MAPPING_CSV.parent.mkdir(parents=True, exist_ok=True)
    with MAPPING_CSV.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["target_base_id", "source_base_id", "status", "name"])
        for target, source in catalog["target_to_source"].items():
            status = "remapped" if target != source else "unchanged"
            writer.writerow([target, source, status, names.get(source, f"发型 {target}")])
    report = {
        "final_family_count": len(catalog["target_to_source"]),
        "final_img_count": len(catalog["target_to_source"]) * 8,
        "overflow_mapping": dict(zip(catalog["overflow"], catalog["targets"], strict=True)),
        "overwritten_complete_bases": catalog["overwritten"],
        "reused_incomplete_bases": catalog["reused_incomplete"],
        "dropped_incomplete_bases": catalog["dropped_incomplete"],
        "dropped_suffix_8_9_ids": catalog["suffix_8_9"],
    }
    atomic_write_text(REPORT_JSON, json.dumps(report, ensure_ascii=False, indent=2) + "\n")


def prepare(source: Path, staging: Path, workers: int, limit: int | None) -> None:
    source_hair = source / "Character/Hair"
    catalog = build_catalog(source_hair)
    names = source_names(source / "String/Eqp.img")
    write_reports(catalog, names)
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    tasks = list(tasks_for_catalog(source_hair, catalog, staging))
    if limit is not None:
        tasks = tasks[:limit]
    totals = {"canvases": 0, "outlinks": 0, "bytes": 0}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for index, (_target, canvases, outlinks, size) in enumerate(pool.map(materialize_one, tasks), 1):
            totals["canvases"] += canvases
            totals["outlinks"] += outlinks
            totals["bytes"] += size
            if index % 250 == 0 or index == len(tasks):
                print(f"prepared {index}/{len(tasks)} IMG", flush=True)
    print(json.dumps(totals, ensure_ascii=False), flush=True)


def verify_staging(source: Path, staging: Path, full: bool) -> dict:
    catalog = build_catalog(source / "Character/Hair")
    expected = {
        f"{base + color:08d}.img"
        for base in catalog["target_to_source"]
        for color in range(8)
    }
    actual = {path.name for path in staging.glob("*.img")}
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise RuntimeError(f"staging ID mismatch missing={missing[:10]} extra={extra[:10]}")
    paths = sorted(staging.glob("*.img"))
    if not full:
        paths = [paths[0], paths[8], paths[-1]]
    canvases = 0
    outlinks = 0
    for path in paths:
        image = load_image(path, GMS_KEY)
        for node in walk(image.root):
            if isinstance(node, WzCanvasProperty):
                canvases += 1
                outlinks += int(node.child("_outlink") is not None)
    if outlinks:
        raise RuntimeError(f"staging still contains {outlinks} outlinks")
    return {"files": len(actual), "verified_files": len(paths), "canvases": canvases, "outlinks": outlinks}


def replace_directory(current: Path, staged: Path, backup: Path) -> None:
    backup.parent.mkdir(parents=True, exist_ok=True)
    if backup.exists():
        shutil.rmtree(backup)
    if current.exists():
        current.replace(backup)
    staged.replace(current)


def direct_child(parent: ET.Element | None, name: str) -> ET.Element | None:
    if parent is None:
        return None
    return next((child for child in parent if child.get("name") == name), None)


def replace_server_strings(names: dict[int, str]) -> None:
    tree = ET.parse(SERVER_STRING)
    root = tree.getroot()
    hair = direct_child(direct_child(root, "Eqp"), "Hair")
    if hair is None:
        raise RuntimeError("server String.wz Eqp/Hair missing")
    hair[:] = []
    for hair_id, name in sorted(names.items()):
        node = ET.SubElement(hair, "imgdir", {"name": str(hair_id)})
        ET.SubElement(node, "string", {"name": "name", "value": name})
    ET.indent(tree, space="  ")
    data = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    data += ET.tostring(root, encoding="unicode") + "\n"
    atomic_write_text(SERVER_STRING, data)


def replace_client_strings(names: dict[int, str]) -> None:
    image = load_image(CLIENT_STRING, GMS_KEY)
    hair = image.root.get("Eqp/Hair")
    if not isinstance(hair, WzSubProperty):
        raise RuntimeError("client String Eqp/Hair missing")
    hair._children.clear()
    for hair_id, name in sorted(names.items()):
        node = WzSubProperty(str(hair_id), hair)
        node.add(WzStringProperty("name", name, node))
        hair.add(node)
    atomic_write_bytes(CLIENT_STRING, encode_image_body(image, gms_reader()))


def replace_int_children(parent: ET.Element, values: list[int]) -> None:
    parent[:] = []
    for index, value in enumerate(values):
        ET.SubElement(parent, "int", {"name": str(index), "value": str(value)})


def replace_string_children(parent: ET.Element, values: list[int], names: dict[int, str]) -> None:
    parent[:] = []
    for value in values:
        ET.SubElement(parent, "string", {"name": str(value), "value": names[value]})


def patch_server_make_char(names: dict[int, str]) -> None:
    for make_char_path in SERVER_MAKE_CHARS:
        if not make_char_path.exists():
            continue
        tree = ET.parse(make_char_path)
        root = tree.getroot()
        for group, values in (("CharMale", MALE_DEFAULTS), ("CharFemale", FEMALE_DEFAULTS)):
            for prefix in ("Info", "PremiumChar", "OrientChar"):
                group_name = group if prefix == "Info" else prefix + group.removeprefix("Char")
                node = direct_child(direct_child(root, prefix if prefix == "Info" else group_name), group if prefix == "Info" else "1")
                if prefix == "Info":
                    node = direct_child(node, "1")
                if node is not None:
                    replace_int_children(node, values)
            for name_group_name in (group, "Premium" + group, "Orient" + group):
                name_group = direct_child(direct_child(direct_child(root, "Name"), name_group_name), "1")
                if name_group is not None:
                    replace_string_children(name_group, values, names)
        ET.indent(tree, space="  ")
        data = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        data += ET.tostring(root, encoding="unicode") + "\n"
        atomic_write_text(make_char_path, data)


def patch_client_make_char(names: dict[int, str]) -> None:
    image = load_image(CLIENT_MAKE_CHAR, GMS_KEY)
    root = image.root
    groups = {
        "Info/CharMale/1": MALE_DEFAULTS,
        "Info/CharFemale/1": FEMALE_DEFAULTS,
        "PremiumCharMale/1": MALE_DEFAULTS,
        "PremiumCharFemale/1": FEMALE_DEFAULTS,
        "OrientCharMale/1": MALE_DEFAULTS,
        "OrientCharFemale/1": FEMALE_DEFAULTS,
    }
    for path, values in groups.items():
        node = root.get(path)
        if not isinstance(node, WzSubProperty):
            continue
        node._children.clear()
        for index, value in enumerate(values):
            node.add(WzIntProperty(str(index), value, node))
    name_groups = {
        "Name/CharMale/1": MALE_DEFAULTS,
        "Name/CharFemale/1": FEMALE_DEFAULTS,
        "Name/PremiumCharMale/1": MALE_DEFAULTS,
        "Name/PremiumCharFemale/1": FEMALE_DEFAULTS,
        "Name/OrientCharMale/1": MALE_DEFAULTS,
        "Name/OrientCharFemale/1": FEMALE_DEFAULTS,
    }
    for path, values in name_groups.items():
        node = root.get(path)
        if not isinstance(node, WzSubProperty):
            continue
        node._children.clear()
        for value in values:
            node.add(WzStringProperty(str(value), names[value], node))
    atomic_write_bytes(CLIENT_MAKE_CHAR, encode_image_body(image, gms_reader()))


def write_generated_files(catalog: dict, names: dict[int, str]) -> None:
    bases = sorted(catalog["target_to_source"])
    atomic_write_text(HAIR_BASE_RESOURCE, "".join(f"{base}\n" for base in bases))
    atomic_write_text(
        HANDBOOK,
        "".join(f"{hair_id} - {names[hair_id]} - (no description)\n" for hair_id in sorted(names)),
    )
    bases_sql = ", ".join(str(base) for base in bases)
    sql = f"""-- Keep persisted Hair IDs inside the complete old-client-safe catalog.

UPDATE `characters`
SET `hair` = (CASE WHEN `gender` = 1 THEN {FEMALE_DEFAULTS[0]} ELSE {MALE_DEFAULTS[0]} END)
    + CASE WHEN MOD(`hair`, 10) BETWEEN 0 AND 7 THEN MOD(`hair`, 10) ELSE 0 END
WHERE MOD(`hair`, 10) NOT BETWEEN 0 AND 7
   OR (`hair` - MOD(`hair`, 10)) NOT IN ({bases_sql});

UPDATE `playernpcs`
SET `hair` = (CASE WHEN `gender` = 1 THEN {FEMALE_DEFAULTS[0]} ELSE {MALE_DEFAULTS[0]} END)
    + CASE WHEN MOD(COALESCE(`hair`, 0), 10) BETWEEN 0 AND 7 THEN MOD(COALESCE(`hair`, 0), 10) ELSE 0 END
WHERE `hair` IS NULL
   OR MOD(`hair`, 10) NOT BETWEEN 0 AND 7
   OR (`hair` - MOD(`hair`, 10)) NOT IN ({bases_sql});
"""
    atomic_write_text(DB_MIGRATION, sql)


def nearest_valid_id(hair_id: int, bases: list[int], overflow_map: dict[int, int]) -> int:
    color = hair_id % 10
    if color < 0 or color > 7:
        color = 0
    base = hair_id - hair_id % 10
    if base in overflow_map:
        return overflow_map[base] + color
    if base in bases:
        return base + color
    nearest = min(bases, key=lambda value: (abs(value - base), value))
    return nearest + color


def patch_hair_scripts(catalog: dict) -> tuple[int, int]:
    bases = sorted(catalog["target_to_source"])
    overflow_map = dict(zip(catalog["overflow"], catalog["targets"], strict=True))
    changed_files = 0
    changed_ids = 0
    roots = [ROOT / "gms-server/scripts", ROOT / "gms-server/scripts-zh-CN"]
    for scripts_root in roots:
        for path in scripts_root.rglob("*.js"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if not re.search(r"setHair|getHair|hairnew|haircolor|mhair|fhair|newHairs|hairColors", text, re.I):
                continue
            output: list[str] = []
            for line in text.splitlines(keepends=True):
                if HAIR_CONTEXT_RE.search(line):
                    def replace(match: re.Match[str]) -> str:
                        nonlocal changed_ids
                        old = int(match.group())
                        new = nearest_valid_id(old, bases, overflow_map)
                        changed_ids += int(new != old)
                        return str(new)
                    line = HAIR_ID_RE.sub(replace, line)
                output.append(line)
            updated = "".join(output)

            def replace_invalid_id(match: re.Match[str]) -> str:
                nonlocal changed_ids
                old = int(match.group())
                color = old % 10
                base = old - color
                if color <= 7 and base in bases:
                    return match.group()
                new = SCRIPT_HAIR_ID_REMAP.get(old, nearest_valid_id(old, bases, overflow_map))
                changed_ids += int(new != old)
                return str(new)

            updated = HAIR_ID_RE.sub(replace_invalid_id, updated)
            if path.name == "Salon.js" and "var hairColors = {" in updated:
                entries = "\n".join(f"    {base}: [0, 1, 2, 3, 4, 5, 6, 7]," for base in bases)
                updated = re.sub(
                    r"var hairColors = \{.*?\n\};\n\nvar faceColors",
                    f"var hairColors = {{\n{entries}\n}};\n\nvar faceColors",
                    updated,
                    flags=re.S,
                )
            if updated != text:
                atomic_write_text(path, updated)
                changed_files += 1
    return changed_files, changed_ids


def apply(source: Path, staging: Path) -> None:
    verify_staging(source, staging, full=False)
    catalog = build_catalog(source / "Character/Hair")
    names = final_names(catalog, source_names(source / "String/Eqp.img"))
    write_reports(catalog, source_names(source / "String/Eqp.img"))

    replace_directory(CLIENT_HAIR, staging, BACKUP / "client-Hair")
    if SERVER_HAIR.exists():
        backup_server = BACKUP / "server-Hair"
        if backup_server.exists():
            shutil.rmtree(backup_server)
        SERVER_HAIR.replace(backup_server)
    SERVER_HAIR.mkdir(parents=True, exist_ok=True)

    replace_client_strings(names)
    replace_server_strings(names)
    patch_client_make_char(names)
    patch_server_make_char(names)
    write_generated_files(catalog, names)
    script_files, script_ids = patch_hair_scripts(catalog)
    print(f"applied client Hair files: {len(names)}")
    print(f"patched Hair scripts: {script_files}, remapped IDs: {script_ids}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "verify", "apply"))
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--staging", type=Path, default=STAGING)
    parser.add_argument("--workers", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.source, args.staging, args.workers, args.limit)
    elif args.command == "verify":
        print(json.dumps(verify_staging(args.source, args.staging, args.full), ensure_ascii=False))
    else:
        apply(args.source, args.staging)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
