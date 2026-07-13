#!/usr/bin/env python3
"""Keep only hair assets that are new in a source folder.

The source folder is compared against the current client Character/Hair
directory. Files that already exist in the client are treated as overlap and
are not kept. The script then rewrites known server/client references to use
the remaining new hair ids.
"""

from __future__ import annotations

import argparse
import io
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import quoteattr


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.properties import (  # noqa: E402
    WzCanvasProperty,
    WzConvexProperty,
    WzDoubleProperty,
    WzFloatProperty,
    WzIntProperty,
    WzLongProperty,
    WzNullProperty,
    WzShortProperty,
    WzSoundProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


SOURCE_HAIR = Path("/Users/lizixian/Downloads/髮型")
CLIENT_HAIR = ROOT / "clien/Data/Character/Hair"
SERVER_HAIR = ROOT / "gms-server/wz/Character.wz/Hair"
CLIENT_MAKE_CHAR = ROOT / "clien/Data/Etc/MakeCharInfo.img"
SERVER_MAKE_CHAR = ROOT / "gms-server/wz/Etc.wz/MakeCharInfo.img.xml"
CLIENT_EQP_STRING = ROOT / "clien/Data/String/Eqp.img"
SERVER_EQP_STRING = ROOT / "gms-server/wz/String.wz/Eqp.img.xml"
HANDBOOK_HAIR = ROOT / "gms-server/handbook/Equip/Hair.txt"
ITEM_CONSTANTS = ROOT / "gms-server/src/main/java/org/gms/constants/inventory/ItemConstants.java"
NPC_DIR = ROOT / "gms-server/scripts/npc"
BACKUP_ROOT = Path("/private/tmp/beidou-hair-new-only-backup")
KEY = WzKey.for_region("GMS")
HAIR_BASE_ID_REMAP = {
    63110: 48700,
    63120: 48710,
    63130: 48720,
    63140: 48730,
    63160: 48740,
    64610: 48750,
    64650: 48760,
    64660: 48770,
    63150: 42200,
    63480: 42210,
    63490: 42220,
    64620: 42230,
    64630: 42240,
    64640: 42250,
    64910: 42260,
    64920: 42270,
}
HAIR_ID_REMAP = {
    old_base + color: new_base + color
    for old_base, new_base in HAIR_BASE_ID_REMAP.items()
    for color in range(8)
}
DEFAULT_MALE_BASES = [40070, 40080, 42100]
DEFAULT_FEMALE_BASES = [43270, 44440, 44450]
LEGACY_MALE_BASES = [30030, 30020, 30000]
LEGACY_FEMALE_BASES = [31000, 31040, 31050]

HAIR_ID_RE = re.compile(r"\b(?:3|4|6)\d{4}\b")
ARRAY_RE = re.compile(r"(hair\w*\s*=\s*Array\()([^)]+)(\))")
DEFAULT_HAIR_RE = re.compile(r"isNewCharDefaultHair\(int gender, int hairId\) \{\n.*?\n    \}", re.S)
MAKE_CHAR_NAME_RE = re.compile(r'<string name="(?:3|4|6)\d{4}" value="[^"]*"/>')


def atomic_write_bytes(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def atomic_write_text(path: Path, data: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    ) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def backup(path: Path) -> None:
    if not path.exists():
        return
    rel = path.relative_to(ROOT)
    dst = BACKUP_ROOT / rel
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), KEY)


def int_id(raw: str) -> int:
    return int(raw)


def remap_hair_id(hair_id: int) -> int:
    return HAIR_ID_REMAP.get(hair_id, hair_id)


def client_hair_ids() -> set[int]:
    return {int_id(p.stem) for p in CLIENT_HAIR.glob("*.img")}


def source_hair_files(source: Path) -> dict[int, Path]:
    files: dict[int, Path] = {}
    for path in source.glob("*.img"):
        source_id = int_id(path.stem)
        target_id = remap_hair_id(source_id)
        previous = files.get(target_id)
        if previous is not None:
            previous_id = int_id(previous.stem)
            previous_was_remapped = remap_hair_id(previous_id) != previous_id
            current_was_remapped = target_id != source_id
            if previous_was_remapped and not current_was_remapped:
                continue
            if current_was_remapped and not previous_was_remapped:
                files[target_id] = path
                continue
            raise RuntimeError(f"hair id remap collision: {previous.name} and {path.name} -> {target_id}")
        files[target_id] = path
    return files


def color_bucket(ids: Iterable[int], color: int) -> list[int]:
    return [hair_id for hair_id in ids if hair_id % 10 == color]


def choose_defaults(new_ids: list[int]) -> tuple[list[int], list[int]]:
    ids = set(new_ids)
    male = DEFAULT_MALE_BASES[:]
    female = DEFAULT_FEMALE_BASES[:]
    missing = [hair_id for hair_id in male + female if hair_id not in ids]
    if missing:
        raise RuntimeError(f"missing default character hair ids: {missing}")
    return male, female


def make_id_mapper(new_ids: list[int]):
    new_id_set = set(new_ids)
    by_color: dict[int, list[int]] = {}
    for color in range(10):
        vals = color_bucket(new_ids, color)
        if vals:
            by_color[color] = vals
    all_ids = new_ids[:]

    def map_id(old_id: int) -> int:
        if old_id in new_id_set:
            return old_id
        bucket = by_color.get(old_id % 10, all_ids)
        return bucket[old_id % len(bucket)]

    return map_id


def _xml_escape_attr(value: str) -> str:
    return quoteattr(value)


def property_to_xml(prop, indent: int = 1) -> str:
    pad = "  " * indent
    name_attr = f"name={_xml_escape_attr(prop.name)}"
    if isinstance(prop, WzNullProperty):
        return f"{pad}<null {name_attr}/>"
    if isinstance(prop, WzShortProperty):
        return f'{pad}<short {name_attr} value="{int(prop.value)}"/>'
    if isinstance(prop, WzIntProperty):
        return f'{pad}<int {name_attr} value="{int(prop.value)}"/>'
    if isinstance(prop, WzLongProperty):
        return f'{pad}<long {name_attr} value="{int(prop.value)}"/>'
    if isinstance(prop, WzFloatProperty):
        return f'{pad}<float {name_attr} value="{float(prop.value)}"/>'
    if isinstance(prop, WzDoubleProperty):
        return f'{pad}<double {name_attr} value="{float(prop.value)}"/>'
    if isinstance(prop, WzStringProperty):
        return f"{pad}<string {name_attr} value={_xml_escape_attr(str(prop.value))}/>"
    if isinstance(prop, WzUolProperty):
        return f"{pad}<uol {name_attr} value={_xml_escape_attr(str(prop.value))}/>"
    if isinstance(prop, WzVectorProperty):
        return f'{pad}<vector {name_attr} x="{int(prop.x)}" y="{int(prop.y)}"/>'
    if isinstance(prop, WzConvexProperty):
        body = "\n".join(property_to_xml(point, indent + 1) for point in prop.children())
        return f"{pad}<extended {name_attr}>\n{body}\n{pad}</extended>"
    if isinstance(prop, WzSoundProperty):
        return f'{pad}<sound {name_attr} length_ms="{int(prop.length_ms)}" bytes="{int(prop.value)}"/>'
    if isinstance(prop, WzCanvasProperty):
        attrs = f'{name_attr} width="{int(prop.width)}" height="{int(prop.height)}"'
        children = prop.children()
        if not children:
            return f"{pad}<canvas {attrs}/>"
        body = "\n".join(property_to_xml(child, indent + 1) for child in children)
        return f"{pad}<canvas {attrs}>\n{body}\n{pad}</canvas>"
    if isinstance(prop, WzSubProperty):
        children = prop.children()
        if not children:
            return f"{pad}<imgdir {name_attr}/>"
        body = "\n".join(property_to_xml(child, indent + 1) for child in children)
        return f"{pad}<imgdir {name_attr}>\n{body}\n{pad}</imgdir>"
    raise TypeError(f"unsupported WZ property: {type(prop).__name__}")


def strip_redundant_canvas_outlinks(node) -> tuple[int, int]:
    removed = 0
    missing_pixels = 0
    if isinstance(node, WzCanvasProperty):
        outlink = node.child("_outlink")
        if isinstance(outlink, WzStringProperty):
            if node.has_pixels():
                del node._children["_outlink"]
                removed += 1
            else:
                missing_pixels += 1
    if hasattr(node, "children"):
        for child in node.children():
            child_removed, child_missing = strip_redundant_canvas_outlinks(child)
            removed += child_removed
            missing_pixels += child_missing
    return removed, missing_pixels


def compatible_hair_image(img_path: Path) -> WzImage:
    image = WzImage.from_bytes(img_path.read_bytes(), key=KEY, name=img_path.name)
    root = image.parse()
    _, missing_pixels = strip_redundant_canvas_outlinks(root)
    if missing_pixels:
        raise RuntimeError(f"{img_path.name}: {missing_pixels} _outlink canvas nodes have no pixels")
    return image


def compatible_hair_bytes(img_path: Path) -> bytes:
    return encode_image_body(compatible_hair_image(img_path), gms_reader())


def image_to_xml(img_path: Path) -> str:
    image = compatible_hair_image(img_path)
    root = image.parse()
    body = "\n".join(property_to_xml(child, 1) for child in root.children())
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<imgdir name="{img_path.name}">\n{body}\n</imgdir>\n'


def patch_client_hair(source_files: dict[int, Path], new_ids: list[int], dry_run: bool) -> tuple[int, int]:
    keep = {f"{hair_id:08d}.img" for hair_id in new_ids}
    existing = [p for p in CLIENT_HAIR.glob("*.img") if p.is_file()]
    if {p.name for p in existing} == keep:
        return 0, len(keep)
    missing = [hair_id for hair_id in new_ids if hair_id not in source_files]
    if missing:
        raise FileNotFoundError(f"missing source hair files for target ids: {missing[:5]}")
    if dry_run:
        return len(existing), len(keep)
    CLIENT_HAIR.mkdir(parents=True, exist_ok=True)
    for path in existing:
        backup(path)
        path.unlink()
    for target_id in new_ids:
        src = source_files[target_id]
        atomic_write_bytes(CLIENT_HAIR / f"{target_id:08d}.img", compatible_hair_bytes(src))
    return len(existing), len(keep)


def patch_server_hair(source_files: dict[int, Path], new_ids: list[int], dry_run: bool) -> tuple[int, int]:
    keep = {f"{hair_id:08d}.img.xml" for hair_id in new_ids}
    existing = [p for p in SERVER_HAIR.glob("*.img.xml") if p.is_file()]
    if {p.name for p in existing} == keep:
        return 0, len(keep)
    missing = [hair_id for hair_id in new_ids if hair_id not in source_files]
    if missing:
        raise FileNotFoundError(f"missing source hair files for target ids: {missing[:5]}")
    if dry_run:
        return len(existing), len(keep)
    SERVER_HAIR.mkdir(parents=True, exist_ok=True)
    for path in existing:
        backup(path)
        path.unlink()
    for target_id in new_ids:
        src = source_files[target_id]
        atomic_write_text(SERVER_HAIR / f"{target_id:08d}.img.xml", image_to_xml(src))
    return len(existing), len(keep)


def patch_item_constants(male: list[int], female: list[int], dry_run: bool) -> bool:
    text = ITEM_CONSTANTS.read_text(encoding="utf-8")
    block = (
        "isNewCharDefaultHair(int gender, int hairId) {\n"
        "        return switch (gender) {\n"
        f"            case 0 -> hairId == {male[0]} || hairId == {male[1]} || hairId == {male[2]}\n"
        f"                    || hairId == {LEGACY_MALE_BASES[0]} || hairId == {LEGACY_MALE_BASES[1]} || hairId == {LEGACY_MALE_BASES[2]};\n"
        f"            case 1 -> hairId == {female[0]} || hairId == {female[1]} || hairId == {female[2]}\n"
        f"                    || hairId == {LEGACY_FEMALE_BASES[0]} || hairId == {LEGACY_FEMALE_BASES[1]} || hairId == {LEGACY_FEMALE_BASES[2]};\n"
        "            default -> false;\n"
        "        };\n"
        "    }"
    )
    updated = DEFAULT_HAIR_RE.sub(block, text)
    if updated == text:
        return False
    if not dry_run:
        backup(ITEM_CONSTANTS)
        atomic_write_text(ITEM_CONSTANTS, updated)
    return True


def direct_child(parent: ET.Element, name: str) -> ET.Element | None:
    for child in parent:
        if child.get("name") == name:
            return child
    return None


def hair_display_name(hair_id: int) -> str:
    return f"新发型 {hair_id}"


def replace_server_hair_strings(new_ids: list[int], dry_run: bool) -> bool:
    tree = ET.parse(SERVER_EQP_STRING)
    root = tree.getroot()
    eqp = direct_child(root, "Eqp")
    hair = direct_child(eqp, "Hair") if eqp is not None else None
    if hair is None:
        raise RuntimeError("missing String.wz Eqp/Hair node")
    old = [int(child.get("name", "0")) for child in hair if child.get("name", "").isdigit()]
    if old == new_ids:
        return False
    hair[:] = []
    for hair_id in new_ids:
        node = ET.SubElement(hair, "imgdir", {"name": str(hair_id)})
        ET.SubElement(node, "string", {"name": "name", "value": hair_display_name(hair_id)})
    ET.indent(tree, space="  ")
    if not dry_run:
        backup(SERVER_EQP_STRING)
        data = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        data += ET.tostring(root, encoding="unicode") + "\n"
        atomic_write_text(SERVER_EQP_STRING, data)
    return True


def replace_client_hair_strings(new_ids: list[int], dry_run: bool) -> bool:
    image = WzImage.from_bytes(CLIENT_EQP_STRING.read_bytes(), key=KEY, name=CLIENT_EQP_STRING.name)
    root = image.parse()
    hair = root.get("Eqp/Hair")
    if not isinstance(hair, WzSubProperty):
        raise RuntimeError("missing client String Eqp/Hair node")
    old = [int(child.name) for child in hair.children() if child.name.isdigit()]
    if old == new_ids:
        return False
    hair._children.clear()
    for hair_id in new_ids:
        node = WzSubProperty(str(hair_id), hair)
        node.add(WzStringProperty("name", hair_display_name(hair_id), node))
        hair.add(node)
    if not dry_run:
        backup(CLIENT_EQP_STRING)
        atomic_write_bytes(CLIENT_EQP_STRING, encode_image_body(image, gms_reader()))
    return True


def replace_hair_handbook(new_ids: list[int], dry_run: bool) -> bool:
    data = "".join(f"{hair_id} - {hair_display_name(hair_id)} - (no description)\n" for hair_id in new_ids)
    old = HANDBOOK_HAIR.read_text(encoding="utf-8", errors="ignore") if HANDBOOK_HAIR.exists() else ""
    if old == data:
        return False
    if not dry_run:
        backup(HANDBOOK_HAIR)
        atomic_write_text(HANDBOOK_HAIR, data)
    return True


def patch_gm_style_npc(new_ids: list[int], dry_run: bool) -> bool:
    base_hairs = color_bucket(new_ids, 0)
    replacement = ", ".join(str(hair_id) for hair_id in base_hairs)
    changed = False
    for path in [NPC_DIR / "9900000.js", ROOT / "gms-server/scripts-zh-CN/npc/9900000.js"]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        updated = re.sub(r"var fhair = \[[^\]]*\];", f"var fhair = [{replacement}];", text)
        updated = re.sub(r"var hair = \[[^\]]*\];", f"var hair = [{replacement}];", updated)
        if updated != text:
            changed = True
            if not dry_run:
                backup(path)
                atomic_write_text(path, updated)
    return changed


def replace_int_children(parent: ET.Element, values: list[int]) -> None:
    parent[:] = []
    for index, value in enumerate(values):
        ET.SubElement(parent, "int", {"name": str(index), "value": str(value)})


def replace_string_children(parent: ET.Element, values: list[int]) -> None:
    parent[:] = []
    for value in values:
        ET.SubElement(parent, "string", {"name": str(value), "value": hair_display_name(value)})


def patch_server_make_char(male: list[int], female: list[int], dry_run: bool) -> bool:
    tree = ET.parse(SERVER_MAKE_CHAR)
    root = tree.getroot()
    compatible_male = male + LEGACY_MALE_BASES
    compatible_female = female + LEGACY_FEMALE_BASES
    groups = {
        "Info/CharMale": compatible_male,
        "Info/CharFemale": compatible_female,
        "PremiumCharMale": compatible_male,
        "PremiumCharFemale": compatible_female,
        "OrientCharMale": compatible_male,
        "OrientCharFemale": compatible_female,
    }
    changed = False
    for path, values in groups.items():
        node = root
        for part in path.split("/"):
            node = direct_child(node, part) if node is not None else None
        if node is None:
            raise RuntimeError(f"missing MakeCharInfo path: {path}")
        hair_node = direct_child(node, "1")
        if hair_node is None:
            raise RuntimeError(f"missing hair node in MakeCharInfo path: {path}")
        old = [int(child.get("value", "0")) for child in hair_node]
        if old != values:
            replace_int_children(hair_node, values)
            changed = True
    name_groups = {
        "Name/CharMale": compatible_male,
        "Name/CharFemale": compatible_female,
    }
    for path, values in name_groups.items():
        node = root
        for part in path.split("/"):
            node = direct_child(node, part) if node is not None else None
        if node is None:
            continue
        hair_node = direct_child(node, "1")
        if hair_node is None:
            continue
        old = [int(child.get("name", "0")) for child in hair_node if child.get("name", "").isdigit()]
        if old != values:
            replace_string_children(hair_node, values)
            changed = True
    text = ET.tostring(root, encoding="unicode")
    text = MAKE_CHAR_NAME_RE.sub("", text)
    text = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + text + "\n"
    if not dry_run:
        backup(SERVER_MAKE_CHAR)
        atomic_write_text(SERVER_MAKE_CHAR, text)
    return changed


def patch_client_make_char(male: list[int], female: list[int], dry_run: bool) -> bool:
    image = WzImage.from_bytes(CLIENT_MAKE_CHAR.read_bytes(), key=KEY, name=CLIENT_MAKE_CHAR.name)
    root = image.parse()
    compatible_male = male + LEGACY_MALE_BASES
    compatible_female = female + LEGACY_FEMALE_BASES
    groups = {
        "Info/CharMale": compatible_male,
        "Info/CharFemale": compatible_female,
        "PremiumCharMale": compatible_male,
        "PremiumCharFemale": compatible_female,
        "OrientCharMale": compatible_male,
        "OrientCharFemale": compatible_female,
    }
    changed = False
    for path, values in groups.items():
        node = root.get(path)
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"missing client MakeCharInfo path: {path}")
        hair_node = node.child("1")
        if not isinstance(hair_node, WzSubProperty):
            raise RuntimeError(f"missing client MakeCharInfo hair node: {path}/1")
        old = [int(child.value) for child in hair_node.children() if isinstance(child, WzIntProperty)]
        if old != values:
            hair_node._children.clear()
            for index, value in enumerate(values):
                hair_node.add(WzIntProperty(str(index), value, hair_node))
            changed = True
    name_groups = {
        "Name/CharMale/1": compatible_male,
        "Name/CharFemale/1": compatible_female,
    }
    for path, values in name_groups.items():
        node = root.get(path)
        if not isinstance(node, WzSubProperty):
            continue
        old = [int(child.name) for child in node.children() if child.name.isdigit()]
        if old != values:
            node._children.clear()
            for value in values:
                node.add(WzStringProperty(str(value), hair_display_name(value), node))
            changed = True
    if changed and not dry_run:
        backup(CLIENT_MAKE_CHAR)
        atomic_write_bytes(CLIENT_MAKE_CHAR, encode_image_body(image, gms_reader()))
    return changed


def patch_npc_scripts(map_id, dry_run: bool) -> tuple[int, int]:
    changed_files = 0
    changed_ids = 0
    for path in sorted(NPC_DIR.glob("*.js")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not re.search(r"hair|sendStyle|setHair", text, re.I):
            continue

        def replace_id(match: re.Match[str]) -> str:
            nonlocal changed_ids
            old = int(match.group(0))
            new = map_id(old)
            changed_ids += int(new != old)
            return str(new)

        updated = HAIR_ID_RE.sub(replace_id, text)
        if updated != text:
            changed_files += 1
            if not dry_run:
                backup(path)
                atomic_write_text(path, updated)
    return changed_files, changed_ids


def validate_ids(new_ids: list[int]) -> None:
    if not new_ids:
        raise RuntimeError("no new-only hair ids found")
    if len(new_ids) < 6:
        raise RuntimeError("need at least 6 new-only hair ids")
    missing_colors = [color for color in range(8) if not color_bucket(new_ids, color)]
    if missing_colors:
        raise RuntimeError(f"missing hair colors needed by dye scripts: {missing_colors}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE_HAIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source = args.source
    before = client_hair_ids()
    source_files = source_hair_files(source)
    source_ids = set(source_files)
    if before and before <= source_ids:
        new_ids = sorted(before)
    else:
        new_ids = sorted(source_ids - before)
    validate_ids(new_ids)
    male, female = choose_defaults(new_ids)
    map_id = make_id_mapper(new_ids)

    removed_client, kept_client = patch_client_hair(source_files, new_ids, args.dry_run)
    removed_server, kept_server = patch_server_hair(source_files, new_ids, args.dry_run)
    item_constants_changed = patch_item_constants(male, female, args.dry_run)
    server_make_changed = patch_server_make_char(male, female, args.dry_run)
    client_make_changed = patch_client_make_char(male, female, args.dry_run)
    server_string_changed = replace_server_hair_strings(new_ids, args.dry_run)
    client_string_changed = replace_client_hair_strings(new_ids, args.dry_run)
    handbook_changed = replace_hair_handbook(new_ids, args.dry_run)
    gm_style_changed = patch_gm_style_npc(new_ids, args.dry_run)
    npc_files, npc_ids = patch_npc_scripts(map_id, args.dry_run)

    print(f"new-only hair ids: {len(new_ids)}")
    print(f"default male: {male}")
    print(f"default female: {female}")
    print(f"client Hair: remove {removed_client}, keep {kept_client}")
    print(f"server Hair XML: remove {removed_server}, keep {kept_server}")
    print(f"ItemConstants changed: {item_constants_changed}")
    print(f"server MakeCharInfo changed: {server_make_changed}")
    print(f"client MakeCharInfo changed: {client_make_changed}")
    print(f"server String Eqp/Hair changed: {server_string_changed}")
    print(f"client String Eqp/Hair changed: {client_string_changed}")
    print(f"handbook Hair changed: {handbook_changed}")
    print(f"GM style NPC changed: {gm_style_changed}")
    print(f"NPC scripts changed: {npc_files}, ids remapped: {npc_ids}")
    if args.dry_run:
        print("dry-run only; no files written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
