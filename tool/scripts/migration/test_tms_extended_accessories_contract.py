#!/usr/bin/env python3
"""Contract checks for badge, emblem, and robot-heart compatibility migration."""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import migrate_tms_extended_accessories as migration  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def git_blob(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def tracked_paths() -> set[str]:
    output = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD", "clien/Data/Character"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout
    return set(output.splitlines())


def category_records(data: bytes, category: str):
    image = migration.load_image_bytes(data, migration.CLIENT_STRING.name)
    _, _, names, spans = migration.locate_category_records(image, data, category)
    return names, {name: data[a:b] for name, (a, b) in zip(names, spans)}


def check_fixed_catalogs() -> None:
    for catalog in migration.CATALOGS:
        source_dir = migration.TMS_DATA / "Character" / catalog.resource_category
        source = {
            int(path.stem)
            for path in source_dir.glob(f"0{catalog.ids[0] // 10000}*.img")
        }
        require(set(catalog.ids) == source, f"fixed {catalog.name} catalog differs from TMS")
        require(len(catalog.ids) == len(set(catalog.ids)), f"duplicate {catalog.name} ID")


def check_existing_resource_scope() -> None:
    tracked = tracked_paths()
    patched = set()
    for catalog in migration.CATALOGS:
        for item_id in catalog.ids:
            path = migration.CLIENT_CHARACTER / catalog.client_resource_category / f"{item_id:08d}.img"
            relative = path.relative_to(ROOT).as_posix()
            if relative in tracked:
                baseline = git_blob(path)
                current = path.read_bytes()
                if current == baseline:
                    continue
                require(item_id in migration.EXISTING_SLOT_PATCH_IDS,
                        f"unapproved existing resource changed: {item_id}")
                old_image = migration.load_image_bytes(baseline, path.name)
                new_image = migration.load_image_bytes(current, path.name)
                old_info = old_image.root.child("info")
                new_info = new_image.root.child("info")
                allowed = set()
                for name in ("islot", "vslot"):
                    old_prop = old_info.child(name)
                    new_prop = new_info.child(name)
                    require(new_prop.value == catalog.target_slot,
                            f"wrong patched {name}: {item_id}")
                    require(old_prop._payload_offset == new_prop._payload_offset,
                            f"shifted {name} payload: {item_id}")
                    require(old_prop._payload_length == new_prop._payload_length,
                            f"resized {name} payload: {item_id}")
                    allowed.update(range(
                        old_prop._payload_offset,
                        old_prop._payload_offset + old_prop._payload_length,
                    ))
                changed = {index for index, pair in enumerate(zip(baseline, current))
                           if pair[0] != pair[1]}
                require(len(current) == len(baseline), f"IMG size changed: {item_id}")
                require(changed and changed <= allowed,
                        f"bytes outside slot payload changed: {item_id}")
                patched.add(item_id)
    require(patched == set(migration.EXISTING_SLOT_PATCH_IDS),
            f"unexpected existing slot patch set: {sorted(patched)}")


def check_client_string_scope() -> None:
    baseline = git_blob(migration.CLIENT_STRING)
    current = migration.CLIENT_STRING.read_bytes()
    old_image = migration.load_image_bytes(baseline, migration.CLIENT_STRING.name)
    new_image = migration.load_image_bytes(current, migration.CLIENT_STRING.name)
    old_reader = old_image.wz_file.reader
    new_reader = new_image.wz_file.reader
    old_reader.seek(0)
    new_reader.seek(0)
    old_eqp = migration.read_property_list(old_reader, baseline, ("Eqp",))
    new_eqp = migration.read_property_list(new_reader, current, ("Eqp",))
    old_names, old_spans = old_eqp[3], old_eqp[4]
    new_names, new_spans = new_eqp[3], new_eqp[4]
    require(old_names == new_names, "Eqp string category order changed")
    for name, old_span, new_span in zip(old_names, old_spans, new_spans):
        if name not in {"Accessory", "Weapon"}:
            require(
                baseline[slice(*old_span)] == current[slice(*new_span)],
                f"unapproved Eqp string category changed: {name}",
            )
    for category in {catalog.target_string_category for catalog in migration.CATALOGS}:
        old_names, old_records = category_records(baseline, category)
        new_names, new_records = category_records(current, category)
        require(new_names[:len(old_names)] == old_names, f"{category} strings are not append-only")
        for name in old_names:
            require(old_records[name] == new_records[name], f"existing {category} string changed: {name}")
    strings = migration.load_image(migration.CLIENT_STRING, migration.GMS_KEY)
    for catalog in migration.CATALOGS:
        for item_id in catalog.ids:
            require(
                strings.root.get(f"Eqp/{catalog.target_string_category}/{item_id}/name") is not None,
                f"missing client string: {item_id}",
            )


def check_generated_resources() -> int:
    tracked = tracked_paths()
    added = 0
    for catalog in migration.CATALOGS:
        for item_id in catalog.ids:
            file_name = f"{item_id:08d}.img"
            client_path = migration.CLIENT_CHARACTER / catalog.client_resource_category / file_name
            server_path = migration.SERVER_CHARACTER / catalog.resource_category / f"{file_name}.xml"
            require(client_path.is_file(), f"missing client resource: {item_id}")
            require(server_path.is_file(), f"missing server resource: {item_id}")
            ET.parse(server_path)
            if client_path.relative_to(ROOT).as_posix() in tracked:
                continue
            added += 1
            image = migration.load_image(client_path, migration.GMS_KEY)
            info = image.root.child("info")
            require(info.child("islot").value == catalog.target_slot, f"wrong islot: {item_id}")
            require(info.child("vslot").value == catalog.target_slot, f"wrong vslot: {item_id}")
            canvases = [node for node in migration.walk(image.root) if node.type_name == "Canvas"]
            require(canvases, f"missing Canvas: {item_id}")
            for canvas in canvases:
                require((canvas.format, canvas.format2) == (1, 0),
                        f"wrong Canvas format: {item_id}/{canvas.name}")
                pixels = decode_canvas(canvas, region="GMS").convert("RGBA")
                require(pixels.getchannel("A").getbbox() is not None,
                        f"transparent Canvas: {item_id}/{canvas.name}")
    return added


def check_source_contract() -> None:
    body_part = (ROOT / "gms-server/src/main/java/org/gms/client/inventory/BodyPart.java").read_text()
    slots = (ROOT / "gms-server/src/main/java/org/gms/constants/inventory/EquipSlot.java").read_text()
    constants = (ROOT / "gms-server/src/main/java/org/gms/constants/inventory/ItemConstants.java").read_text()
    provider = (ROOT / "gms-server/src/main/java/org/gms/server/ItemInformationProvider.java").read_text()
    dll = (ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp").read_text()
    for name, body, token, slot, prefix in (
        ("robot heart", 54, "Ht", -54, 167),
        ("badge", 55, "Ba", -55, 118),
        ("emblem", 56, "Em", -56, 119),
    ):
        enum_name = name.upper().replace(" ", "_")
        require(f"{enum_name}({body})" in body_part, f"wrong {name} body part")
        require(f'{enum_name}("{token}", {slot})' in slots, f"wrong {name} slot")
        require(f"case {prefix} -> BodyPart.{enum_name}.getValue()" in constants,
                f"missing {name} server mapping")
        require(dll.count(f"itemId / 10000 == {prefix}") == 2,
                f"{name} client mapping is not guarded")
        require(f"bodyPart == {body}" in dll, f"missing {name} body-part validation")
        require(f"bodyParts[0] = {body}" in dll, f"missing {name} body-part lookup")
    require('cat = "Eqp/Accessory"' in provider, "robot-heart string projection is missing")
    require("Eqp/Android" not in provider, "server still depends on Android string category")
    require('"cmp eax, 118\\n"' in dll and '"cmp eax, 119\\n"' in dll and
            '"cmp eax, 167\\n"' in dll,
            "extended accessory client data-path classifier is incomplete")
    require('"push 0x005C97A9\\n"' in dll,
            "extended accessories are not routed to the proven Accessory branch")


def main() -> None:
    check_fixed_catalogs()
    check_existing_resource_scope()
    check_client_string_scope()
    added = check_generated_resources()
    check_source_contract()
    print(
        "extended accessory contract passed: "
        f"326 fixed IDs, {added} resources outside the Git baseline, slots 54/55/56"
    )


if __name__ == "__main__":
    main()
