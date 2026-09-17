#!/usr/bin/env python3
"""Remove the Damien map-back lava that was projected onto v83 Back layers.

Those orange mountains were a mistaken map Back. The screenshot band is the
skill2 scene effect `customBossDemian/groundBurst`. This restores
Back/BossDemian.img from HEAD (unused 13-15 plus leftover 17-19) and deletes
map back 9-11 from 350160240/280. It does not rewrite those map IMGs and does
not restore info/boss or info/shadowzone. Do not restore spine.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzSubProperty  # noqa: E402
from wzpy.incremental_img import mutate_img  # noqa: E402
from wzpy.incremental_xml import mutate_xml  # noqa: E402

CLIENT_BACK = ROOT / "clien/Data/Map/Back/BossDemian.img"
HEAD_BACK = "clien/Data/Map/Back/BossDemian.img"
MAP_IDS = (350160240, 350160280)
LAVA_MAP_BACKS = ("11", "10", "9")
HEAD_BACK_SIZES = {
    "13": (837, 245),
    "14": (1260, 309),
    "15": (742, 573),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def client_map_path(map_id: int) -> Path:
    return ROOT / f"clien/Data/Map/Map/Map{str(map_id)[0]}/{map_id}.img"


def server_map_path(map_id: int) -> Path:
    return ROOT / f"gms-server/wz/Map.wz/Map/Map{str(map_id)[0]}/{map_id}.img.xml"


def load_gms(data: bytes, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{name} parse failed: truncated={image.truncated} {image.parse_warnings}")
    return image


def head_blob(rel: str) -> bytes:
    return subprocess.check_output(["git", "cat-file", "blob", f"HEAD:{rel}"], cwd=ROOT)


def back_names(image: WzImage) -> list[str]:
    folder = image.root.child("back")
    if not isinstance(folder, WzSubProperty):
        raise RuntimeError(f"{image.name} missing back")
    return [child.name for child in folder.children()]


def back_is_clean(data: bytes) -> bool:
    image = load_gms(data, CLIENT_BACK.name)
    if image.root.child("spine") is not None:
        raise RuntimeError("BossDemian still has spine")
    names = back_names(image)
    if names != [str(index) for index in range(17)]:
        return False
    folder = image.root.child("back")
    for name, size in HEAD_BACK_SIZES.items():
        canvas = folder.child(name)
        if not isinstance(canvas, WzCanvasProperty):
            return False
        if (int(canvas.width), int(canvas.height)) != size:
            return False
        if (int(canvas.format), int(canvas.format2)) != (1, 0):
            raise RuntimeError(f"back/{name} is not ARGB4444")
    return True


def map_lava_names(data: bytes, name: str) -> set[str]:
    image = load_gms(data, name)
    folder = image.root.child("back")
    if not isinstance(folder, WzSubProperty):
        raise RuntimeError(f"{name} missing back")
    found = set()
    for child in folder.children():
        if child.name in {"9", "10", "11"}:
            found.add(child.name)
            continue
        no = int(arc.child_value(child, "no") or -1)
        if no in {13, 14, 15}:
            found.add(child.name)
    names = {child.name for child in folder.children() if child.name.isdigit()}
    max_name = max(int(name) for name in names)
    missing = [index for index in range(max_name + 1) if str(index) not in names]
    if missing:
        raise RuntimeError(f"{name} back gaps {missing}")
    return found


def map_is_clean(data: bytes, name: str) -> bool:
    return not map_lava_names(data, name)


def xml_lava_names(text: str, name: str) -> set[str]:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(text)
    back = next((child for child in root if child.get("name") == "back"), None)
    if back is None:
        raise RuntimeError(f"{name} XML missing back")
    found = set()
    for child in back:
        child_name = child.get("name", "")
        values = {item.get("name"): item.get("value") for item in child}
        if child_name in {"9", "10", "11"}:
            found.add(child_name)
        elif int(values.get("no", "-1")) in {13, 14, 15}:
            found.add(child_name)
    return found


def xml_is_clean(text: str, name: str) -> bool:
    return not xml_lava_names(text, name)


def verify_remove_scope(before: bytes, after: bytes, removed: tuple[str, ...]) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)
    root = ("back", *removed)
    gone = {path for path in before_records if path[: len(root)] == root}
    extra = set(after_records) - set(before_records)
    missing = set(before_records) - set(after_records)
    if extra:
        raise RuntimeError(f"lava removal added records: {sorted(extra)}")
    if missing != gone:
        raise RuntimeError(f"lava removal changed unexpected records: {sorted(missing ^ gone)}")
    parent = ("back",)
    for container, names in before_orders.items():
        if container[: len(root)] == root:
            continue
        current = after_orders.get(container)
        if container == parent:
            expected = tuple(name for name in names if name != removed[0])
            if current != expected:
                raise RuntimeError(f"lava removal reordered back siblings: {current}")
            continue
        if current != names:
            raise RuntimeError(f"lava removal reordered {container}")
    for path, raw in before_records.items():
        if path in gone or path == parent:
            continue
        if after_records[path] != raw:
            raise RuntimeError(f"lava removal changed protected record: {path}")


def patch_back(data: bytes) -> bytes:
    expected = head_blob(HEAD_BACK)
    load_gms(expected, CLIENT_BACK.name)
    if not back_is_clean(expected):
        raise RuntimeError("HEAD BossDemian is not the pre-lava back tree")
    if data == expected:
        return data
    return expected


def patch_map_img(data: bytes, name: str) -> bytes:
    result = data
    for child in LAVA_MAP_BACKS:
        if load_gms(result, name).root.get(f"back/{child}") is None:
            continue
        before = result
        result = mutate_img(result, "remove", ("back", child), region="GMS").data
        verify_remove_scope(before, result, (child,))
    if not map_is_clean(result, name):
        raise RuntimeError(f"{name} still has lava back entries")
    return result


def patch_map_xml(text: str, name: str) -> str:
    result = text
    for child in LAVA_MAP_BACKS:
        if child not in xml_lava_names(result, name):
            continue
        result = mutate_xml(result, "remove", ("back", child))
    if not xml_is_clean(result, name):
        raise RuntimeError(f"{name} XML still has lava back entries")
    return result


def build_expected() -> dict[Path, bytes]:
    expected: dict[Path, bytes] = {CLIENT_BACK: patch_back(CLIENT_BACK.read_bytes())}
    for map_id in MAP_IDS:
        client = client_map_path(map_id)
        server = server_map_path(map_id)
        expected[client] = patch_map_img(client.read_bytes(), client.name)
        expected[server] = patch_map_xml(server.read_text(encoding="utf-8"), server.name).encode("utf-8")
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = build_expected()
    if args.check:
        pending = [path for path, data in expected.items() if path.read_bytes() != data]
        if pending:
            raise SystemExit("needs lava removal: " + ", ".join(p.as_posix() for p in pending))
        print("Damien map lava already removed")
        return 0
    changed = 0
    for path, data in expected.items():
        if path.read_bytes() == data:
            continue
        if path.suffix == ".xml":
            arc.atomic_write_text(path, data.decode("utf-8"))
        else:
            arc.atomic_write_bytes(path, data)
        changed += 1
    second = build_expected()
    for path, data in second.items():
        if path.read_bytes() != data:
            raise RuntimeError(f"generator not idempotent: {path}")
        if data != expected[path]:
            raise RuntimeError(f"second pass hash drift: {path}")
    print(f"Damien map lava removed: changed={changed}")
    for path, data in expected.items():
        print(f"{path.relative_to(ROOT)} sha256={sha256(data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
