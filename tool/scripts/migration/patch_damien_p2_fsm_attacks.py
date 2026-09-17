#!/usr/bin/env python3
"""Project TMS 8880101 onlyFsm attacks onto 8880111 using the phase-one pose.

TMS 8880101 attack2/5/6 are onlyFsm 1x1 stubs; attack4 already UOLs to stand.
The old client cannot play onlyFsm empty canvases. Phase one 8880110/attack2
stripped onlyFsm and replaced the pose with stand/0-7 UOLs. Do the same on
8880111 attack2/4/5/6. Do not spawn 8880101. Do not full-serialize 8880111.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_demian as demian  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzSubProperty, WzUolProperty  # noqa: E402
from wzpy.incremental_img import mutate_img, replace_img_record  # noqa: E402
from wzpy.incremental_xml import mutate_xml  # noqa: E402

MOB_ID = 8880111
ATTACKS = ("attack2", "attack4", "attack5", "attack6")
STAND_FRAMES = tuple(str(index) for index in range(8))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def client_path() -> Path:
    return demian.client_mob_path(MOB_ID)


def server_path() -> Path:
    return demian.server_mob_path(MOB_ID)


def load_gms(data: bytes, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{name} parse failed: {image.parse_warnings}")
    return image


def stand_uol(name: str) -> WzUolProperty:
    return WzUolProperty(name, f"../stand/{name}")


def verify_outside(before: bytes, after: bytes, allowed: set[tuple[str, ...]]) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)
    for path, raw in before_records.items():
        affected = any(path[: len(root)] == root or root[: len(path)] == path for root in allowed)
        if not affected and after_records.get(path) != raw:
            raise RuntimeError(f"protected record changed: {path}")
    for parent, names in before_orders.items():
        if any(parent[: len(root)] == root or root[: len(parent)] == parent for root in allowed):
            continue
        if after_orders.get(parent) != names:
            raise RuntimeError(f"protected sibling order changed: {parent}")


def pose_is_clean(action: WzSubProperty) -> bool:
    info = action.child("info")
    if info is not None and info.child("onlyFsm") is not None:
        return False
    frames = [child for child in action.children() if child.name.isdigit()]
    if [child.name for child in frames] != list(STAND_FRAMES):
        return False
    return all(
        isinstance(child, WzUolProperty) and str(child.value) == f"../stand/{child.name}"
        for child in frames
    )


def img_is_clean(data: bytes) -> bool:
    image = load_gms(data, f"{MOB_ID}.img")
    for name in ATTACKS:
        action = image.root.child(name)
        if not isinstance(action, WzSubProperty) or not pose_is_clean(action):
            return False
    return True


def xml_pose_is_clean(text: str, attack: str) -> bool:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(text)
    action = next((child for child in root if child.get("name") == attack), None)
    if action is None:
        return False
    info = next((child for child in action if child.get("name") == "info"), None)
    if info is not None and any(child.get("name") == "onlyFsm" for child in info):
        return False
    frames = [child for child in action if child.tag == "uol" and (child.get("name") or "").isdigit()]
    if [child.get("name") for child in frames] != list(STAND_FRAMES):
        return False
    return all(child.get("value") == f"../stand/{child.get('name')}" for child in frames)


def xml_is_clean(text: str) -> bool:
    return all(xml_pose_is_clean(text, name) for name in ATTACKS)


def strip_only_fsm(data: bytes, attack: str) -> bytes:
    path = (attack, "info", "onlyFsm")
    image = load_gms(data, f"{MOB_ID}.img")
    if image.root.get("/".join(path)) is None:
        return data
    patched = mutate_img(data, "remove", path, region="GMS").data
    verify_outside(data, patched, {path, (attack, "info"), (attack,)})
    return patched


def project_pose(data: bytes, attack: str) -> bytes:
    image = load_gms(data, f"{MOB_ID}.img")
    action = image.root.child(attack)
    if not isinstance(action, WzSubProperty):
        raise RuntimeError(f"missing {attack}")
    if pose_is_clean(action):
        return data
    existing = {child.name for child in action.children() if child.name.isdigit()}
    for name in sorted(existing, key=int, reverse=True):
        if name == "0":
            continue
        before = data
        data = mutate_img(data, "remove", (attack, name), region="GMS").data
        verify_outside(before, data, {(attack, name), (attack,)})
    image = load_gms(data, f"{MOB_ID}.img")
    frame0 = image.root.get(f"{attack}/0")
    if frame0 is None:
        before = data
        data = mutate_img(
            data,
            "add",
            (attack,),
            name="0",
            kind="UOL",
            values={"value": "../stand/0"},
            region="GMS",
        ).data
        verify_outside(before, data, {(attack, "0"), (attack,)})
    elif not (isinstance(frame0, WzUolProperty) and str(frame0.value) == "../stand/0"):
        before = data
        data = replace_img_record(data, (attack, "0"), stand_uol("0"), region="GMS").data
        verify_outside(before, data, {(attack, "0"), (attack,)})
    for name in STAND_FRAMES[1:]:
        image = load_gms(data, f"{MOB_ID}.img")
        if image.root.get(f"{attack}/{name}") is not None:
            continue
        before = data
        data = arc.append_property_record(data, (attack,), stand_uol(name))
        verify_outside(before, data, {(attack, name), (attack,)})
    return data


def patch_img(data: bytes) -> bytes:
    result = data
    for attack in ATTACKS:
        result = strip_only_fsm(result, attack)
        result = project_pose(result, attack)
    if not img_is_clean(result):
        raise RuntimeError("8880111 FSM poses were not projected onto stand UOLs")
    return result


def patch_xml(text: str) -> str:
    result = text
    for attack in ATTACKS:
        if xml_pose_is_clean(result, attack):
            continue
        try:
            result = mutate_xml(result, "remove", (attack, "info", "onlyFsm"))
        except Exception:
            pass
        for name in reversed(STAND_FRAMES):
            for kind in ("canvas", "uol"):
                try:
                    result = mutate_xml(result, "remove", (attack, name))
                    break
                except Exception:
                    continue
        for name in STAND_FRAMES:
            result = mutate_xml(
                result,
                "add",
                (attack,),
                name=name,
                kind="UOL",
                values={"value": f"../stand/{name}"},
            )
    if not xml_is_clean(result):
        raise RuntimeError("8880111 XML FSM poses were not projected onto stand UOLs")
    return result


def build_expected() -> dict[Path, bytes]:
    client = client_path()
    server = server_path()
    return {
        client: patch_img(client.read_bytes()),
        server: patch_xml(server.read_text(encoding="utf-8")).encode("utf-8"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = build_expected()
    if args.check:
        pending = [path for path, data in expected.items() if path.read_bytes() != data]
        if pending:
            raise SystemExit("needs P2 FSM pose patch: " + ", ".join(p.as_posix() for p in pending))
        print("8880111 FSM attacks already use stand UOLs")
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
        if path.read_bytes() != data or data != expected[path]:
            raise RuntimeError(f"generator not idempotent: {path}")
    print(f"8880111 FSM stand UOLs ok: changed={changed}")
    for path, data in expected.items():
        print(f"{path.relative_to(ROOT)} sha256={sha256(data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
