#!/usr/bin/env python3
"""Static contract checks for per-character damage-cap breakthrough stones."""

from __future__ import annotations

import configparser
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_damage_cap_breakthrough as migration  # noqa: E402
from wzpy import WzCanvasProperty  # noqa: E402
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


def semantic_element(node: ET.Element):
    return (
        node.tag,
        tuple(sorted(node.attrib.items())),
        (node.text or "").strip(),
        tuple(semantic_element(child) for child in node),
    )


def direct_imgdirs(root: ET.Element) -> list[ET.Element]:
    return [child for child in root if child.tag == "imgdir"]


def named_child(parent: ET.Element, tag: str, name: str) -> ET.Element:
    child = parent.find(f"./{tag}[@name='{name}']")
    if child is None:
        raise AssertionError(f"missing {tag} {name}")
    return child


def check_client_insert_scope(path: Path, targets: set[tuple[str, ...]], anchor: str) -> None:
    baseline = git_blob(path)
    current = path.read_bytes()
    migration.arc.verify_raw_record_insert_scope(baseline, current, targets)
    _, before_order = migration.arc.raw_record_state(baseline)
    _, after_order = migration.arc.raw_record_state(current)
    names = tuple(root[0] for root in targets)
    anchor_index = after_order[()].index(anchor)
    require(
        set(after_order[()][anchor_index - len(names):anchor_index]) == set(names),
        f"new records are not directly before {anchor} in {path}",
    )
    require(
        before_order[()] == tuple(name for name in after_order[()] if (name,) not in targets),
        f"legacy root order changed in {path}",
    )


def check_client_items() -> None:
    check_client_insert_scope(
        migration.CLIENT_ITEM,
        {(spec.item_node,) for spec in migration.STONES},
        migration.ITEM_ANCHOR,
    )
    check_client_insert_scope(
        migration.CLIENT_STRING,
        {(str(spec.item_id),) for spec in migration.STONES},
        migration.STRING_ANCHOR,
    )

    item = migration.load_client(migration.CLIENT_ITEM)
    strings = migration.load_client(migration.CLIENT_STRING)
    for spec in migration.STONES:
        require(
            strings.get(f"{spec.item_id}/name").value == spec.name,
            f"wrong client name for {spec.item_id}",
        )
        require(
            strings.get(f"{spec.item_id}/desc").value == migration.ITEM_DESCRIPTION,
            f"wrong client description for {spec.item_id}",
        )
        require(
            item.get(f"{spec.item_node}/info/tradeBlock").value == 1,
            f"tradeBlock missing for {spec.item_id}",
        )
        require(
            item.get(f"{spec.item_node}/spec/script").value == migration.SCRIPT_NAME,
            f"wrong client script for {spec.item_id}",
        )
        for canvas_name in ("icon", "iconRaw"):
            canvas = item.get(f"{spec.item_node}/info/{canvas_name}")
            require(isinstance(canvas, WzCanvasProperty),
                    f"missing client Canvas {spec.item_id}/{canvas_name}")
            require(
                (canvas.width, canvas.height, canvas.format, canvas.format2) == (32, 32, 1, 0),
                f"incompatible client Canvas {spec.item_id}/{canvas_name}",
            )
            pixels = decode_canvas(canvas, region="GMS").convert("RGBA")
            require(pixels.getchannel("A").getbbox() is not None,
                    f"transparent client Canvas {spec.item_id}/{canvas_name}")


def check_xml_insert_scope(path: Path, target_names: set[str]) -> ET.Element:
    before = ET.fromstring(git_blob(path))
    after = ET.parse(path).getroot()
    before_nodes = direct_imgdirs(before)
    after_nodes = direct_imgdirs(after)
    require(
        [node.get("name") for node in before_nodes]
        == [node.get("name") for node in after_nodes if node.get("name") not in target_names],
        f"legacy XML root order changed in {path}",
    )
    before_by_name = {node.get("name"): node for node in before_nodes}
    after_by_name = {node.get("name"): node for node in after_nodes}
    require(target_names == set(after_by_name) - set(before_by_name),
            f"unexpected XML root changes in {path}")
    for name, node in before_by_name.items():
        require(semantic_element(node) == semantic_element(after_by_name[name]),
                f"legacy XML record changed in {path}: {name}")
    return after


def check_server_items() -> None:
    item_targets = {spec.item_node for spec in migration.STONES}
    string_targets = {str(spec.item_id) for spec in migration.STONES}
    item_root = check_xml_insert_scope(migration.SERVER_ITEM, item_targets)
    string_roots = [check_xml_insert_scope(path, string_targets) for path in migration.SERVER_STRINGS]

    for spec in migration.STONES:
        item = named_child(item_root, "imgdir", spec.item_node)
        info = named_child(item, "imgdir", "info")
        item_spec = named_child(item, "imgdir", "spec")
        require(named_child(info, "int", "tradeBlock").get("value") == "1",
                f"server tradeBlock missing for {spec.item_id}")
        require(named_child(item_spec, "string", "script").get("value") == migration.SCRIPT_NAME,
                f"wrong server script for {spec.item_id}")
        for root in string_roots:
            node = named_child(root, "imgdir", str(spec.item_id))
            require(named_child(node, "string", "name").get("value") == spec.name,
                    f"wrong server name for {spec.item_id}")
            require(named_child(node, "string", "desc").get("value") == migration.ITEM_DESCRIPTION,
                    f"wrong server description for {spec.item_id}")


def check_dll_and_config() -> None:
    baseline = git_blob(migration.CLIENT_DLL)
    current = migration.CLIENT_DLL.read_bytes()
    require(len(current) == len(baseline), "ijl15.dll size changed")
    patches = {
        0x3416C: (struct.pack("<i", 19_999_999), struct.pack("<i", 2_147_483_647)),
        0x34170: (struct.pack("<i", 19_999_999), struct.pack("<i", 2_147_483_647)),
        0x34180: (struct.pack("<d", 19_999_999.0), struct.pack("<d", 2_147_483_647.0)),
    }
    allowed = set()
    for offset, (old, new) in patches.items():
        require(baseline[offset:offset + len(old)] == old, f"unexpected DLL baseline at {offset:#x}")
        require(current[offset:offset + len(new)] == new, f"wrong DLL patch at {offset:#x}")
        allowed.update(range(offset, offset + len(new)))
    changed = {index for index, pair in enumerate(zip(baseline, current)) if pair[0] != pair[1]}
    require(changed and changed <= allowed, "DLL bytes changed outside approved cap constants")

    config = configparser.ConfigParser()
    config.optionxform = str
    config.read(ROOT / "clien/config.ini", encoding="utf-8")
    for key in ("setDamageCap", "setMAtkCap", "setAtkOutCap"):
        require(config["optional"].get(key) == "2147483647", f"wrong client config {key}")


def check_source_contract() -> None:
    generator = Path(migration.__file__).read_text(encoding="utf-8")
    require("encode_image_body" not in generator, "generator uses forbidden full IMG writer")
    require("save_as(" not in generator, "generator uses forbidden full IMG writer")
    require("verify_raw_record_insert_scope" in generator,
            "generator does not verify incremental IMG scope")

    service = (ROOT / "gms-server/src/main/java/org/gms/server/DamageCapService.java").read_text()
    character = (ROOT / "gms-server/src/main/java/org/gms/client/Character.java").read_text()
    conversation = (
        ROOT / "gms-server/src/main/java/org/gms/scripting/npc/NPCConversationManager.java"
    ).read_text()
    script = (ROOT / "gms-server/scripts/item/damage_cap_breakthrough.js").read_text()
    migration_sql = (
        ROOT / "gms-server/src/main/resources/db/migration/V2.1.68__add_character_damage_cap.sql"
    ).read_text()
    require("INITIAL_CAP = 19_999_999" in service, "wrong initial server cap")
    require("MAX_CAP = Integer.MAX_VALUE" in service, "wrong technical server cap")
    require("Randomizer.nextBoolean()" in service, "breakthrough chance is not 50 percent")
    for spec in migration.STONES:
        require(str(spec.item_id) in service and f"{spec.increment:_}" in service,
                f"server stone mapping missing: {spec.item_id}")
    require("gainItem(stoneId, (short) -1, false)" in conversation,
            "stone is not consumed after an attempt")
    require("saveCharToDB(false)" in conversation, "new cap is not saved immediately")
    require("useDamageCapBreakthroughStone" in script, "item script does not invoke breakthrough")
    require("damageCap = ?" in character and "setDamageCap(charactersDO.getDamageCap())" in character,
            "character damage cap is not loaded and saved")
    require("DEFAULT 19999999" in migration_sql, "database default is not 19,999,999")


def main() -> None:
    check_client_items()
    check_server_items()
    check_dll_and_config()
    check_source_contract()
    migration.verify_resources()
    print("damage-cap breakthrough contract passed: 6 stones, exact item/string IMG scope")


if __name__ == "__main__":
    main()
