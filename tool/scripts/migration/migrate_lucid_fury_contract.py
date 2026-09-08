#!/usr/bin/env python3
"""Install the legacy-safe TMS Lucid Fury success and failure contract."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ARC_SCRIPT = Path(__file__).with_name("migrate_arcane_river_expansion.py")
SPEC = importlib.util.spec_from_file_location("arcane_river_expansion", ARC_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {ARC_SCRIPT}")
arc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(arc)

sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
from wzpy import WzCanvasProperty, WzIntProperty, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.incremental_img import mutate_img  # noqa: E402


P2_ID = 8880141
LEGACY_P3_ID = 8880142
FURY_ID = 8880152
FURY_SUCCESS_ID = 8880153
FURY_FAIL_ID = 8880154
FURY_IDS = (FURY_ID, FURY_SUCCESS_ID, FURY_FAIL_ID)
MOB_NAME = "梦中的路西德"
CLIENT_MAX_HP = 2_000_000_000
SERVER_MAX_HP = "5000000000"
FIXED_DAMAGE = {
    FURY_ID: 1,
    FURY_SUCCESS_ID: 30,
    FURY_FAIL_ID: 100,
}
SOURCE_DIR = Path(
    "/Users/lizixian/Library/Caches/BeiDouMapMobWorkbench/ms/Mob_00000"
)
SOURCE_MOBS = {
    mob_id: SOURCE_DIR / f"Mob_{mob_id}.img"
    for mob_id in FURY_IDS
}
SOURCE_SHA256 = {
    FURY_ID: "9e2f6d9fbf8593ae573a9db5c55bef00040bfe3055baba05ae41c31b26db9174",
    FURY_SUCCESS_ID: "2938caa33c87201f0f4ebe06cc6e7b76f519d9d9e52171a7b59dbd74c8e813ac",
    FURY_FAIL_ID: "ef1e688a54f4528740d4efdff69260e52e0095747e94c2c0f2e512e8d08dd6e3",
}
EXPECTED_ROOTS = {
    FURY_ID: ("info", "stand", "hit1", "die1", "attack1"),
    FURY_SUCCESS_ID: (
        "info", "stand", "hit1", "attack1", "die1", "skill1", "die2",
    ),
    FURY_FAIL_ID: ("info", "hit1", "die1", "stand", "attack1"),
}
CLIENT_P2 = ROOT / f"clien/Data/Mob/{P2_ID}.img"
SERVER_P2 = ROOT / f"gms-server/wz/Mob.wz/{P2_ID}.img.xml"
CLIENT_STRING = ROOT / "clien/Data/String/Mob.img"
SERVER_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Mob.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Mob.img.xml",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_sources() -> None:
    for mob_id, path in SOURCE_MOBS.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256(path)
        if actual != SOURCE_SHA256[mob_id]:
            raise RuntimeError(f"Lucid Fury source changed: {path} {actual}")


def add_int(parent: WzSubProperty, name: str, value: int) -> None:
    current = parent.child(name)
    if current is None:
        parent.add(WzIntProperty(name, value, parent))
    elif isinstance(current, WzIntProperty):
        current._value = value
    else:
        arc.remove_child(parent, name)
        parent.add(WzIntProperty(name, value, parent))


def sanitize_fury_mob(root: WzSubProperty, mob_id: int) -> None:
    source_info = root.child("info")
    if not isinstance(source_info, WzSubProperty):
        raise RuntimeError(f"{mob_id}: missing source mob info")
    arc.set_int(source_info, "maxHP", CLIENT_MAX_HP)
    arc.sanitize_mob(root, mob_id)
    info = root.child("info")
    attack_info = root.get("attack1/info")
    if not isinstance(info, WzSubProperty) or not isinstance(attack_info, WzSubProperty):
        raise RuntimeError(f"{mob_id}: missing legacy mob or attack info")

    # TMS field logic owns these zero-delay transitions. The legacy server
    # would otherwise self-destruct the Fury mob immediately after spawning.
    arc.remove_child(info, "selfDestruction")
    add_int(info, "maxHP", CLIENT_MAX_HP)
    add_int(info, "PDRate", 50)
    add_int(info, "MDRate", 50)
    add_int(attack_info, "fixDamR", FIXED_DAMAGE[mob_id])

    if mob_id == FURY_ID:
        revive = WzSubProperty("revive", info)
        revive.add(WzIntProperty("0", FURY_SUCCESS_ID, revive))
        info.add(revive)


def generated_mob(mob_id: int) -> tuple[bytes, str, int]:
    image, materializer = arc.clone_image(
        SOURCE_MOBS[mob_id],
        lambda root: sanitize_fury_mob(root, mob_id),
    )
    data = arc.encode_image_body(image, arc.gms_reader())
    arc.verified_image_bytes(data, f"{mob_id}.img")

    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{mob_id}: missing generated info")
    arc.set_string(info, "maxHP", SERVER_MAX_HP)
    xml = arc.image_to_xml(image, f"{mob_id}.img")
    ET.fromstring(xml)
    return data, xml, materializer.canvases


def install_mobs(generated: dict[int, tuple[bytes, str, int]]) -> None:
    for mob_id, (data, xml, _) in generated.items():
        client = ROOT / f"clien/Data/Mob/{mob_id}.img"
        server = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
        if client.exists() and client.read_bytes() != data:
            raise RuntimeError(f"existing Lucid Fury client differs: {client}")
        if server.exists() and server.read_text(encoding="utf-8") != xml:
            raise RuntimeError(f"existing Lucid Fury server XML differs: {server}")
        if not client.exists():
            arc.atomic_write_bytes(client, data)
        if not server.exists():
            arc.atomic_write_text(server, xml)


def patch_p2_revive() -> None:
    original = CLIENT_P2.read_bytes()
    image = arc.load_image(CLIENT_P2, arc.GMS_KEY)
    revive = image.root.get("info/revive/0")
    if not isinstance(revive, WzIntProperty):
        raise RuntimeError("Lucid P2 client revive is missing or not an int")
    if int(revive.value) not in (LEGACY_P3_ID, FURY_ID):
        raise RuntimeError(f"unexpected Lucid P2 revive target: {revive.value}")
    updated = original
    if int(revive.value) == LEGACY_P3_ID:
        updated = mutate_img(
            original,
            "edit",
            ("info", "revive", "0"),
            values={"value": FURY_ID},
            region="GMS",
        ).data
        arc.verify_raw_record_scope(
            original,
            updated,
            {("info", "revive", "0")},
            allow_additions=False,
        )
        arc.atomic_write_bytes(CLIENT_P2, updated)

    text = SERVER_P2.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    server_revive = root.find(
        './imgdir[@name="info"]/imgdir[@name="revive"]/int[@name="0"]'
    )
    if server_revive is None or server_revive.get("value") not in {
        str(LEGACY_P3_ID), str(FURY_ID),
    }:
        raise RuntimeError("unexpected Lucid P2 server revive target")
    if server_revive.get("value") == str(LEGACY_P3_ID):
        old = f'<int name="0" value="{LEGACY_P3_ID}"/>'
        new = f'<int name="0" value="{FURY_ID}"/>'
        if text.count(old) != 1:
            raise RuntimeError("Lucid P2 server revive record is not unique")
        text = text.replace(old, new, 1)
        ET.fromstring(text)
        arc.atomic_write_text(SERVER_P2, text)


def string_record(mob_id: int) -> WzSubProperty:
    record = WzSubProperty(str(mob_id))
    record.add(arc.WzStringProperty("name", MOB_NAME, record))
    return record


def install_strings() -> None:
    data = CLIENT_STRING.read_bytes()
    image = arc.load_image(CLIENT_STRING, arc.GMS_KEY)
    for mob_id in FURY_IDS:
        current = image.root.get(f"{mob_id}/name")
        if current is not None and current.value != MOB_NAME:
            raise RuntimeError(f"unexpected client String/Mob name for {mob_id}")
        if current is None:
            updated = arc.append_property_record(data, (), string_record(mob_id))
            arc.verify_raw_record_insert_scope(data, updated, {(str(mob_id),)})
            data = updated
            image = arc.WzImage.from_bytes(
                data, key=arc.GMS_KEY, name=CLIENT_STRING.name
            )
            image.parse()
    if data != CLIENT_STRING.read_bytes():
        arc.atomic_write_bytes(CLIENT_STRING, data)

    for path in SERVER_STRINGS:
        text = path.read_text(encoding="utf-8")
        root = ET.fromstring(text)
        for mob_id in FURY_IDS:
            current = root.find(f'./imgdir[@name="{mob_id}"]/string[@name="name"]')
            if current is not None and current.get("value") != MOB_NAME:
                raise RuntimeError(f"unexpected server String/Mob name for {mob_id}: {path}")
            if current is None:
                text = arc.append_xml_properties(text, (), [string_record(mob_id)])
                root = ET.fromstring(text)
        if text != path.read_text(encoding="utf-8"):
            arc.atomic_write_text(path, text)


def verify_installed(generated: dict[int, tuple[bytes, str, int]]) -> None:
    client_p2 = arc.load_image(CLIENT_P2, arc.GMS_KEY)
    if int(client_p2.root.get("info/revive/0").value) != FURY_ID:
        raise RuntimeError("Lucid P2 client does not revive into Fury")
    server_p2 = ET.parse(SERVER_P2).getroot()
    server_revive = server_p2.find(
        './imgdir[@name="info"]/imgdir[@name="revive"]/int[@name="0"]'
    )
    if server_revive is None or server_revive.get("value") != str(FURY_ID):
        raise RuntimeError("Lucid P2 server does not revive into Fury")

    for mob_id, (expected_data, expected_xml, expected_canvases) in generated.items():
        client = ROOT / f"clien/Data/Mob/{mob_id}.img"
        server = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
        if client.read_bytes() != expected_data:
            raise RuntimeError(f"Lucid Fury client is not deterministic: {mob_id}")
        if server.read_text(encoding="utf-8") != expected_xml:
            raise RuntimeError(f"Lucid Fury server XML is not deterministic: {mob_id}")
        image = arc.load_image(client, arc.GMS_KEY)
        if image.truncated or image.parse_warnings:
            raise RuntimeError(f"Lucid Fury IMG did not parse cleanly: {mob_id}")
        if tuple(child.name for child in image.root.children()) != EXPECTED_ROOTS[mob_id]:
            raise RuntimeError(f"unexpected Lucid Fury root order: {mob_id}")
        if image.root.get("info/selfDestruction") is not None:
            raise RuntimeError(f"legacy server would immediately remove Fury mob: {mob_id}")
        revive = image.root.get("info/revive/0")
        if mob_id == FURY_ID:
            if revive is None or int(revive.value) != FURY_SUCCESS_ID:
                raise RuntimeError("Fury success revive is missing")
        elif revive is not None:
            raise RuntimeError(f"transition mob unexpectedly revives: {mob_id}")
        fix_damage = image.root.get("attack1/info/fixDamR")
        if fix_damage is None or int(fix_damage.value) != FIXED_DAMAGE[mob_id]:
            raise RuntimeError(f"Fury fixed damage mismatch: {mob_id}")

        canvases = 0
        visible = 0
        for node, node_path in arc.walk(image.root):
            if not isinstance(node, WzCanvasProperty):
                continue
            canvases += 1
            if (int(node.format), int(node.format2)) != (1, 0):
                raise RuntimeError(f"non-ARGB4444 Fury Canvas: {mob_id}/{node_path}")
            decoded = decode_canvas(node, region="GMS").convert("RGBA")
            visible += decoded.getbbox() is not None
            decoded.close()
        if canvases != expected_canvases or visible == 0:
            raise RuntimeError(
                f"Fury Canvas mismatch: {mob_id} total={canvases} "
                f"expected={expected_canvases} visible={visible}"
            )

        xml_root = ET.parse(server).getroot()
        max_hp = xml_root.find('./imgdir[@name="info"]/string[@name="maxHP"]')
        if max_hp is None or max_hp.get("value") != SERVER_MAX_HP:
            raise RuntimeError(f"Fury server maxHP mismatch: {mob_id}")
        if xml_root.find('./imgdir[@name="info"]/imgdir[@name="selfDestruction"]') is not None:
            raise RuntimeError(f"Fury server selfDestruction was not removed: {mob_id}")

    strings = arc.load_image(CLIENT_STRING, arc.GMS_KEY)
    for mob_id in FURY_IDS:
        name = strings.root.get(f"{mob_id}/name")
        if name is None or name.value != MOB_NAME:
            raise RuntimeError(f"missing client String/Mob name: {mob_id}")
    for path in SERVER_STRINGS:
        root = ET.parse(path).getroot()
        for mob_id in FURY_IDS:
            name = root.find(f'./imgdir[@name="{mob_id}"]/string[@name="name"]')
            if name is None or name.get("value") != MOB_NAME:
                raise RuntimeError(f"missing server String/Mob name: {path} {mob_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    verify_sources()
    generated = {mob_id: generated_mob(mob_id) for mob_id in FURY_IDS}
    if not args.verify_only:
        install_mobs(generated)
        patch_p2_revive()
        install_strings()
    verify_installed(generated)
    print(
        "Lucid Fury contract ok: "
        f"mobs={len(FURY_IDS)} canvases={sum(item[2] for item in generated.values())} "
        f"p2_revive={FURY_ID}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
