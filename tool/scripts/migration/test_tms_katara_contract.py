#!/usr/bin/env python3
"""Contract checks for the legacy-compatible TMS katara migration."""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import migrate_tms_kataras as migration  # noqa: E402
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


def weapon_records(data: bytes):
    image = migration.load_image_bytes(data, migration.CLIENT_STRING.name)
    _, _, names, spans = migration.locate_weapon_records(image, data)
    return names, {name: data[a:b] for name, (a, b) in zip(names, spans)}


def check_client_string_scope() -> None:
    old_names, old_records = weapon_records(git_blob(migration.CLIENT_STRING))
    new_names, new_records = weapon_records(migration.CLIENT_STRING.read_bytes())
    added = tuple(name for name in new_names if name not in old_names)
    katara_names = tuple(str(item_id) for item_id in migration.KATARA_IDS)
    require(all(name in added for name in katara_names), "client katara strings are missing")
    require(tuple(name for name in added if name in katara_names) == katara_names,
            "client katara string order changed")
    for name in old_names:
        require(old_records[name] == new_records[name], f"existing Weapon string changed: {name}")


def check_resources() -> None:
    migrated = set(migration.KATARA_IDS)
    source = {int(path.stem) for path in migration.TMS_WEAPON.glob("0134*.img")}
    legacy = {
        int(path.stem)
        for path in migration.CLIENT_WEAPON.glob("0134*.img")
        if int(path.stem) not in migrated
    }
    require(migrated == source - legacy, "fixed katara migration set no longer matches TMS delta")
    for item_id in migration.KATARA_IDS:
        file_name = f"{item_id:08d}.img"
        image = migration.load_image(migration.CLIENT_WEAPON / file_name, migration.GMS_KEY)
        info = image.root.child("info")
        require(info.child("islot").value == "Si", f"wrong islot: {item_id}")
        require(info.child("vslot").value == "Si", f"wrong vslot: {item_id}")
        require(migration.int_value(info, "reqJob") == 8, f"wrong reqJob: {item_id}")
        canvases = [node for node in migration.walk(image.root) if node.type_name == "Canvas"]
        require(canvases, f"missing Canvas: {item_id}")
        for canvas in canvases:
            require((canvas.format, canvas.format2) == (1, 0),
                    f"wrong Canvas format: {item_id}/{canvas.name}")
            pixels = decode_canvas(canvas, region="GMS").convert("RGBA")
            require(pixels.getchannel("A").getbbox() is not None,
                    f"transparent Canvas: {item_id}/{canvas.name}")
        ET.parse(migration.SERVER_WEAPON / f"{file_name}.xml")


def check_source_contract() -> None:
    item_constants = (
        ROOT / "gms-server/src/main/java/org/gms/constants/inventory/ItemConstants.java"
    ).read_text()
    equip_type = (
        ROOT / "gms-server/src/main/java/org/gms/constants/inventory/EquipType.java"
    ).read_text()
    provider = (
        ROOT / "gms-server/src/main/java/org/gms/server/ItemInformationProvider.java"
    ).read_text()
    dll = (
        ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp"
    ).read_text()
    character = (
        ROOT / "gms-server/src/main/java/org/gms/client/Character.java"
    ).read_text()
    require("if (isSecondaryWeapon(itemId))" in item_constants,
            "secondary-weapon slot priority is missing")
    require("return job.isA(Job.BANDIT);" in item_constants, "bandit restriction is missing")
    require("KATARA(1342)" in equip_type, "katara equipment type is missing")
    require("ItemConstants.canEquipSecondaryWeapon(item.getItemId(), chr.getJob())" in provider,
            "server equip guard is missing")
    require(provider.count("!ItemConstants.canEquipSecondaryWeapon") == 2,
            "katara restriction must cover login validation and equip actions")
    require("return eligibleItems;" in provider,
            "cached equipped-item validation can bypass the katara restriction")
    require("!ItemConstants.canEquipSecondaryWeapon(equip.getItemId(), job)" in character,
            "character stat aggregation can bypass the katara restriction")
    require(dll.count("itemId / 10000 == 134 || itemId / 10000 == 135") == 2,
            "client body-part hooks do not share the 134/135 secondary slot")
    require("SECONDARY_WEAPON(51)" in (
        ROOT / "gms-server/src/main/java/org/gms/client/inventory/BodyPart.java"
    ).read_text(), "server secondary-weapon body part is not 51")
    require(dll.count("bodyPart == 51") >= 1, "client katara body part is not 51")
    require("bodyParts[0] = 51" in dll, "client katara body-part lookup is not 51")
    require(dll.count('"cmp dword ptr [esp + 0x0C], 0x47\\n"') >= 2,
            "katara icon relocation is not guarded to the equipment window")


def main() -> None:
    check_client_string_scope()
    check_resources()
    check_source_contract()
    print(
        f"katara contract passed: {len(migration.KATARA_IDS)} TMS resources, "
        "append-only strings, body part 51, bandit-only server guard"
    )


if __name__ == "__main__":
    main()
