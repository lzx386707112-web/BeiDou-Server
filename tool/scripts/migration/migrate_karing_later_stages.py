#!/usr/bin/env python3
"""Migrate Karing P2/P3 maps and their shared legacy assets.

The four maps and three NPCs are new standalone artifacts. Existing shared
Back, Obj, and String IMG files are changed only by raw child-record insertion.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import struct
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
sys.path.insert(0, str(ROOT / "tool" / "scripts" / "migration"))

from wzpy import WzImage, WzKey, WzStringProperty, WzSubProperty  # noqa: E402
from wzpy.writer import _encode_property_list, encode_compressed_int  # noqa: E402

import migrate_karing_p1_maps as p1  # noqa: E402
from migrate_arcane_river_fields import property_to_xml  # noqa: E402


MAP_IDS = (410007240, 410007260, 410007280, 410007300)
FIGHT_MAP_IDS = {410007260, 410007300}
NPC_IDS = (9091032, 9091033, 9091035)
MAP_NAMES = {
    410007100: ("桃源境", "阻止侵略"),
    410007120: ("桃源境", "失去生气的春天"),
    410007140: ("桃源境", "失去生气的春天"),
    410007160: ("桃源境", "失去光明的夏天"),
    410007180: ("桃源境", "失去光明的夏天"),
    410007200: ("桃源境", "失去色彩的秋天"),
    410007220: ("桃源境", "失去色彩的秋天"),
    410007240: ("桃源境", "残酷的冬天"),
    410007260: ("桃源境", "残酷的冬天"),
    410007280: ("桃源境", "环绕死亡的四季"),
    410007300: ("桃源境", "环绕死亡的四季"),
}
LEGACY_FIGHT_FIELD_LIMIT = 1909496

# Animation and Spine-backed map layers are intentionally excluded. The
# corresponding full-screen stage effects are carried by the boss-scene MCV
# channel instead of becoming old-client WZ texture allocations.
ASSET_PATCH_NODES = {
    ("Back", "dowonkyungDark", "back"): {
        "94", "96", "97", "98", "99", "100", "101", "103", "104",
        "105", "106", "107", "108", "109", "110", "111", "112",
        "113", "114", "115", "116", "117", "118", "119", "120",
        "121", "122", "123", "124",
    },
    ("Back", "BossKaring", "back"): {
        "0", "2", "3", "4", "5", "6", "7", "8", "9", "11", "12",
        "16", "17", "18",
    },
    ("Obj", "dowonkyung", "foothold"): {
        "darkWinter", "upFootholdDarkWinter", "lightSpring",
    },
}
NEW_ASSET_BRANCHES = {
    ("Back", "dowonkyung"): {
        "back/3", "back/91", "back/113", "back/114", "back/115",
        "back/116", "back/117", "back/123", "back/124",
    },
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sanitize_map(root: WzSubProperty, map_id: int) -> None:
    p1.sanitize_map(root, map_id)

    if map_id in FIGHT_MAP_IDS:
        info = root.child("info")
        if isinstance(info, WzSubProperty):
            p1.set_int(info, "fieldLimit", LEGACY_FIGHT_FIELD_LIMIT)
        life = root.child("life")
        if isinstance(life, WzSubProperty):
            for child in list(life.children()):
                p1.remove_child(life, child.name)

    for layer in [child for child in root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        for entry in list(objects.children()):
            if p1.child_value(entry, "oS") == "BossKaring":
                p1.remove_child(objects, entry.name)

    back = root.child("back")
    if isinstance(back, WzSubProperty):
        for entry in list(back.children()):
            if int(p1.child_value(entry, "ani") or 0) != 0:
                p1.remove_child(back, entry.name)

    portal = root.child("portal")
    if isinstance(portal, WzSubProperty):
        for entry in portal.children():
            if p1.child_value(entry, "pn") == "ptKaringOut":
                p1.set_int(entry, "pt", 7)


def migrate_map(map_id: int) -> tuple[WzImage, p1.CanvasMaterializer]:
    source_path = p1.SOURCE / f"Map/Map/Map4/{map_id}.img"
    image, materializer = p1.clone_image(
        source_path,
        lambda root: sanitize_map(root, map_id),
    )
    p1.write_client(ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img", image)
    p1.write_server_map_xml(image, map_id)
    return image, materializer


def locate_records(
    image: WzImage,
    data: bytes,
    parent_path: tuple[str, ...],
) -> tuple[tuple[int, ...], int, int, tuple[str, ...], tuple[tuple[int, int], ...], int]:
    reader = image.wz_file.reader
    reader.seek(0)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError(f"{image.name}: unsupported standalone IMG header")
    reader.skip(2)

    def read_list(size_offsets: tuple[int, ...], block_end: int):
        count_offset = reader.position
        count = reader.read_compressed_int()
        count_end = reader.position
        names: list[str] = []
        spans: list[tuple[int, int]] = []
        for _ in range(count):
            start = reader.position
            name = reader.read_string_block(0)
            tag = reader.read_byte()
            if tag != 9:
                raise RuntimeError(f"{image.name}: unexpected property tag {name}/{tag}")
            size = reader.read_u32()
            reader.seek(reader.position + size)
            names.append(name)
            spans.append((start, reader.position))
        if reader.position != block_end:
            raise RuntimeError(f"{image.name}: property records do not fill parent block")
        return size_offsets, count_offset, count_end, tuple(names), tuple(spans), block_end

    if not parent_path:
        return read_list((), len(data))

    def descend(segments: tuple[str, ...], block_end: int, size_offsets: tuple[int, ...]):
        count = reader.read_compressed_int()
        for _ in range(count):
            name = reader.read_string_block(0)
            tag = reader.read_byte()
            if tag != 9:
                raise RuntimeError(f"{image.name}: unexpected ancestor tag {name}/{tag}")
            size_offset = reader.position
            block_size = reader.read_u32()
            child_start = reader.position
            child_end = child_start + block_size
            if name != segments[0]:
                reader.seek(child_end)
                continue
            reader.seek(child_start)
            if reader.read_string_block(0) != "Property":
                raise RuntimeError(f"{image.name}: {'/'.join(parent_path)} is not a Property")
            reader.skip(2)
            next_offsets = (*size_offsets, size_offset)
            if len(segments) == 1:
                return read_list(next_offsets, child_end)
            return descend(segments[1:], child_end, next_offsets)
        reader.seek(block_end)
        raise RuntimeError(f"{image.name}: missing parent {'/'.join(parent_path)}")

    return descend(parent_path, len(data), ())


def encode_record(node, image: WzImage) -> bytes:
    encoded = _encode_property_list((node,), image.wz_file.reader)
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError(f"{node.name}: unexpected property record encoding")
    return encoded[len(prefix):]


def insert_raw_record(
    path: Path,
    parent_path: tuple[str, ...],
    node,
) -> bool:
    original = path.read_bytes()
    image = WzImage.from_bytes(original, key=p1.GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{path}: malformed baseline {image.parse_warnings}")
    size_offsets, count_offset, count_end, names, spans, records_end = locate_records(
        image, original, parent_path
    )
    if node.name in names:
        return False

    raw_before = {
        name: original[start:end] for name, (start, end) in zip(names, spans)
    }
    record = encode_record(node, image)
    new_count = encode_compressed_int(len(names) + 1)
    if len(new_count) != count_end - count_offset:
        raise RuntimeError(f"{path}: child-count encoding size changed")
    updated = bytearray(original[:records_end] + record + original[records_end:])
    updated[count_offset:count_end] = new_count
    delta = len(record)
    for size_offset in size_offsets:
        old_size = struct.unpack_from("<I", original, size_offset)[0]
        struct.pack_into("<I", updated, size_offset, old_size + delta)

    verified_data = bytes(updated)
    verified = WzImage.from_bytes(verified_data, key=p1.GMS_KEY, name=path.name)
    verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise RuntimeError(f"{path}: incremental result malformed {verified.parse_warnings}")
    _, _, _, new_names, new_spans, _ = locate_records(verified, verified_data, parent_path)
    raw_after = {
        name: verified_data[start:end] for name, (start, end) in zip(new_names, new_spans)
    }
    if new_names != (*names, node.name):
        raise RuntimeError(f"{path}: child order changed during insertion")
    for name, record_before in raw_before.items():
        if raw_after.get(name) != record_before:
            raise RuntimeError(f"{path}: unchanged record changed: {name}")
    if raw_after[node.name] != record:
        raise RuntimeError(f"{path}: inserted record mismatch: {node.name}")
    p1.atomic_write_bytes(path, verified_data)
    return True


def remove_raw_record(
    path: Path,
    parent_path: tuple[str, ...],
    child_name: str,
) -> bool:
    original = path.read_bytes()
    image = WzImage.from_bytes(original, key=p1.GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{path}: malformed baseline {image.parse_warnings}")
    size_offsets, count_offset, count_end, names, spans, _ = locate_records(
        image, original, parent_path
    )
    if child_name not in names:
        return False

    index = names.index(child_name)
    start, end = spans[index]
    raw_before = {
        name: original[record_start:record_end]
        for name, (record_start, record_end) in zip(names, spans)
        if name != child_name
    }
    new_count = encode_compressed_int(len(names) - 1)
    if len(new_count) != count_end - count_offset:
        raise RuntimeError(f"{path}: child-count encoding size changed")
    updated = bytearray(original[:start] + original[end:])
    updated[count_offset:count_end] = new_count
    delta = end - start
    for size_offset in size_offsets:
        old_size = struct.unpack_from("<I", original, size_offset)[0]
        struct.pack_into("<I", updated, size_offset, old_size - delta)

    verified_data = bytes(updated)
    verified = WzImage.from_bytes(verified_data, key=p1.GMS_KEY, name=path.name)
    verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise RuntimeError(f"{path}: incremental result malformed {verified.parse_warnings}")
    _, _, _, new_names, new_spans, _ = locate_records(
        verified, verified_data, parent_path
    )
    expected_names = tuple(name for name in names if name != child_name)
    if new_names != expected_names:
        raise RuntimeError(f"{path}: child order changed during removal")
    raw_after = {
        name: verified_data[record_start:record_end]
        for name, (record_start, record_end) in zip(new_names, new_spans)
    }
    for name, record_before in raw_before.items():
        if raw_after.get(name) != record_before:
            raise RuntimeError(f"{path}: unchanged record changed: {name}")
    p1.atomic_write_bytes(path, verified_data)
    return True


def find_xml_parent_close(text: str, parent_path: tuple[str, ...]) -> int:
    stack: list[str] = []
    cursor = 0
    while cursor < len(text):
        opening = text.find("<imgdir ", cursor)
        closing = text.find("</imgdir>", cursor)
        if opening >= 0 and (closing < 0 or opening < closing):
            tag_end = text.find(">", opening)
            tag = text[opening : tag_end + 1]
            marker = 'name="'
            name_start = tag.find(marker)
            if name_start < 0:
                raise RuntimeError("imgdir without name")
            name_start += len(marker)
            name_end = tag.find('"', name_start)
            if tag.rstrip().endswith("/>"):
                cursor = tag_end + 1
                continue
            stack.append(tag[name_start:name_end])
            cursor = tag_end + 1
            continue
        if closing < 0:
            break
        relative = tuple(stack[1:])
        if relative == parent_path:
            return closing
        if not stack:
            raise RuntimeError("unbalanced XML imgdir close")
        stack.pop()
        cursor = closing + len("</imgdir>")
    raise RuntimeError(f"missing XML parent {'/'.join(parent_path)}")


def insert_xml_record(path: Path, parent_path: tuple[str, ...], node) -> bool:
    original = path.read_text(encoding="utf-8")
    root = ET.fromstring(original)
    parent = root
    for segment in parent_path:
        parent = next((child for child in parent if child.get("name") == segment), None)
        if parent is None:
            raise RuntimeError(f"{path}: missing XML parent {'/'.join(parent_path)}")
    if any(child.get("name") == node.name for child in parent):
        return False
    insertion = property_to_xml(node) + "\n"
    offset = find_xml_parent_close(original, parent_path)
    updated = original[:offset] + insertion + original[offset:]
    verified = ET.fromstring(updated)
    check = verified
    for segment in parent_path:
        check = next(child for child in check if child.get("name") == segment)
    if not any(child.get("name") == node.name for child in check):
        raise RuntimeError(f"{path}: inserted XML record not found: {node.name}")
    p1.atomic_write_text(path, updated)
    return True


def remove_xml_record(
    path: Path, parent_path: tuple[str, ...], child_name: str
) -> bool:
    original = path.read_text(encoding="utf-8")
    root = ET.fromstring(original)
    parent = root
    for segment in parent_path:
        parent = next((child for child in parent if child.get("name") == segment), None)
        if parent is None:
            raise RuntimeError(f"{path}: missing XML parent {'/'.join(parent_path)}")
    matches = [child for child in parent if child.get("name") == child_name]
    if not matches:
        return False
    if len(matches) != 1:
        raise RuntimeError(f"{path}: duplicate XML record {child_name}")

    token_pattern = re.compile(r'<imgdir\b[^>]*\bname="([^"]+)"[^>]*>|</imgdir>')
    stack: list[str] = []
    record_start = None
    record_end = None
    for match in token_pattern.finditer(original):
        if match.group(1) is not None:
            name = match.group(1)
            if match.group(0).rstrip().endswith("/>"):
                continue
            relative_parent = tuple(stack[1:])
            if relative_parent == parent_path and name == child_name:
                line_start = original.rfind("\n", 0, match.start()) + 1
                record_start = line_start if original[line_start:match.start()].isspace() else match.start()
            stack.append(name)
            continue
        if not stack:
            raise RuntimeError(f"{path}: unbalanced XML")
        closing_name = stack.pop()
        if closing_name == child_name and tuple(stack[1:]) == parent_path:
            end = match.end()
            record_end = end + 1 if end < len(original) and original[end] == "\n" else end
            break
    if record_start is None or record_end is None:
        raise RuntimeError(f"{path}: cannot locate XML record {child_name}")

    updated = original[:record_start] + original[record_end:]
    verified = ET.fromstring(updated)
    check = verified
    for segment in parent_path:
        check = next(child for child in check if child.get("name") == segment)
    if any(child.get("name") == child_name for child in check):
        raise RuntimeError(f"{path}: XML record removal did not persist: {child_name}")
    p1.atomic_write_text(path, updated)
    return True


def remove_reward_map_strings() -> dict[str, int]:
    client = ROOT / "clien/Data/String/Map.img"
    server_paths = (
        ROOT / "gms-server/wz/String.wz/Map.img.xml",
        ROOT / "gms-server/wz-zh-CN/String.wz/Map.img.xml",
    )
    return {
        "client": int(remove_raw_record(client, ("grandis",), "410007320")),
        "server": sum(
            int(remove_xml_record(path, ("grandis",), "410007320"))
            for path in server_paths
        ),
    }


def clone_asset_node(kind: str, name: str, parent_path: str, child_name: str):
    source_path = p1.SOURCE / f"Map/{kind}/{name}.img"
    source = p1.load_image(source_path, p1.BMS_KEY)
    source_node = source.root.get(f"{parent_path}/{child_name}")
    if source_node is None:
        raise RuntimeError(f"{source_path}: missing {parent_path}/{child_name}")
    holder = WzSubProperty(parent_path.rsplit("/", 1)[-1])
    materializer = p1.CanvasMaterializer()
    return p1.clone_property(
        source_node, holder, source, source_path, materializer, child_name
    )


def patch_existing_assets() -> dict[str, int]:
    stats = {"clientRecords": 0, "serverRecords": 0}
    for (kind, name, parent), children in sorted(ASSET_PATCH_NODES.items()):
        client = ROOT / f"clien/Data/Map/{kind}/{name}.img"
        server = ROOT / f"gms-server/wz/Map.wz/{kind}/{name}.img.xml"
        for child_name in sorted(children, key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value)):
            node = clone_asset_node(kind, name, parent, child_name)
            stats["clientRecords"] += int(
                insert_raw_record(client, tuple(parent.split("/")), node)
            )
            stats["serverRecords"] += int(
                insert_xml_record(server, tuple(parent.split("/")), node)
            )
    return stats


def build_new_asset(kind: str, name: str, branches: set[str]) -> None:
    source_path = p1.SOURCE / f"Map/{kind}/{name}.img"
    source = p1.load_image(source_path, p1.BMS_KEY)
    image = WzImage.from_bytes(b"", key=p1.GMS_KEY, name=source_path.name)
    image._root = WzSubProperty(source.root.name)
    image._parsed = True
    materializer = p1.CanvasMaterializer()
    for branch in sorted(branches):
        source_node = source.root.get(branch)
        if source_node is None:
            raise RuntimeError(f"{source_path}: missing {branch}")
        parent_path, _, leaf = branch.rpartition("/")
        parent = p1.ensure_path(image.root, parent_path)
        parent.add(
            p1.clone_property(source_node, parent, source, source_path, materializer, leaf)
        )
    client = ROOT / f"clien/Data/Map/{kind}/{name}.img"
    server = ROOT / f"gms-server/wz/Map.wz/{kind}/{name}.img.xml"
    p1.write_client(client, image)
    p1.write_server_xml(server, image, f"{name}.img")


def build_map_string_node(map_id: int) -> WzSubProperty:
    street, name = MAP_NAMES[map_id]
    node = WzSubProperty(str(map_id))
    node.add(WzStringProperty("streetName", street, node))
    node.add(WzStringProperty("mapName", name, node))
    return node


def patch_map_strings() -> dict[str, int]:
    stats = {"client": 0, "server": 0, "serverZhCN": 0}
    client = ROOT / "clien/Data/String/Map.img"
    server_paths = (
        ("server", ROOT / "gms-server/wz/String.wz/Map.img.xml"),
        ("serverZhCN", ROOT / "gms-server/wz-zh-CN/String.wz/Map.img.xml"),
    )
    for map_id in MAP_NAMES:
        node = build_map_string_node(map_id)
        stats["client"] += int(insert_raw_record(client, ("grandis",), node))
        for key, path in server_paths:
            stats[key] += int(insert_xml_record(path, ("grandis",), node))
    return stats


def verify_map(map_id: int) -> None:
    client = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
    image = WzImage.from_bytes(client.read_bytes(), key=p1.GMS_KEY, name=client.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{client}: malformed {image.parse_warnings}")
    if image.root.child("particle") is not None:
        raise RuntimeError(f"{client}: particle root remains")
    if map_id in FIGHT_MAP_IDS:
        info = image.root.child("info")
        if p1.child_value(info, "fieldLimit") != LEGACY_FIGHT_FIELD_LIMIT:
            raise RuntimeError(f"{client}: unsafe fieldLimit")
        life = image.root.child("life")
        if isinstance(life, WzSubProperty) and list(life.children()):
            raise RuntimeError(f"{client}: immediate life records remain")
    back = image.root.child("back")
    if isinstance(back, WzSubProperty):
        for entry in back.children():
            if int(p1.child_value(entry, "ani") or 0) != 0:
                raise RuntimeError(f"{client}: animated/Spine background remains")
    for layer in [child for child in image.root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        for entry in objects.children():
            if entry.child("spineAni") is not None:
                raise RuntimeError(f"{client}: Spine object remains")
            if p1.child_value(entry, "oS") == "BossKaring":
                raise RuntimeError(f"{client}: map-load BossKaring object remains")
    p1.verify_img(client, require_visible=False)
    ET.parse(ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml")


def verify_assets() -> None:
    expected: dict[tuple[str, str], set[str]] = defaultdict(set)
    for map_id in MAP_IDS:
        path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        image = WzImage.from_bytes(path.read_bytes(), key=p1.GMS_KEY, name=path.name)
        image.parse()
        dependencies = p1.collect_dependencies(image)
        for key, branches in dependencies["assets"].items():
            expected[key].update(branches)
    for (kind, name), branches in expected.items():
        path = ROOT / f"clien/Data/Map/{kind}/{name}.img"
        p1.verify_img(path, branches=branches)
        ET.parse(ROOT / f"gms-server/wz/Map.wz/{kind}/{name}.img.xml")


def verify_strings() -> None:
    path = ROOT / "clien/Data/String/Map.img"
    image = WzImage.from_bytes(path.read_bytes(), key=p1.GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{path}: malformed {image.parse_warnings}")
    for map_id, (street, name) in MAP_NAMES.items():
        node = image.root.get(f"grandis/{map_id}")
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"{path}: missing map name {map_id}")
        if p1.child_value(node, "streetName") != street or p1.child_value(node, "mapName") != name:
            raise RuntimeError(f"{path}: wrong map name {map_id}")


def verify() -> None:
    for map_id in MAP_IDS:
        verify_map(map_id)
    verify_assets()
    verify_strings()
    for npc_id in NPC_IDS:
        p1.verify_img(ROOT / f"clien/Data/Npc/{npc_id}.img")
        ET.parse(ROOT / f"gms-server/wz/Npc.wz/{npc_id}.img.xml")


def migrate() -> None:
    before = {
        path: sha256(path.read_bytes())
        for path in (
            ROOT / "clien/Data/Map/Back/BossKaring.img",
            ROOT / "clien/Data/Map/Back/dowonkyungDark.img",
            ROOT / "clien/Data/Map/Obj/dowonkyung.img",
            ROOT / "clien/Data/String/Map.img",
        )
    }
    totals = {"canvases": 0, "links": 0, "resized": 0}
    for map_id in MAP_IDS:
        _, materializer = migrate_map(map_id)
        totals["canvases"] += materializer.canvases
        totals["links"] += materializer.links
        totals["resized"] += materializer.resized
    asset_stats = patch_existing_assets()
    for (kind, name), branches in NEW_ASSET_BRANCHES.items():
        build_new_asset(kind, name, branches)
    for npc_id in NPC_IDS:
        p1.migrate_npc(npc_id)
    string_stats = patch_map_strings()
    verify()
    after = {path: sha256(path.read_bytes()) for path in before}
    print(f"maps={len(MAP_IDS)} {totals}")
    print(f"assets={asset_stats} strings={string_stats}")
    for path in before:
        print(f"{path}: {before[path]} -> {after[path]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--remove-reward-map", action="store_true")
    args = parser.parse_args()
    if args.remove_reward_map:
        print(f"rewardMapStrings={remove_reward_map_strings()}")
        return 0
    if args.verify_only:
        verify()
    else:
        migrate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
