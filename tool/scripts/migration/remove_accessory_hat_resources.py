#!/usr/bin/env python3
"""Incrementally remove the requested accessory and hat equipment resources."""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from remove_weapon_resources import (  # noqa: E402
    apply_img,
    apply_text,
    batch_remove_img,
    batch_remove_xml,
    batch_rename_img,
    batch_rename_xml,
    quest_item_mutations,
    say_edits,
    value_parent_paths,
    value_record_paths,
)


ID_FILE = Path(__file__).with_name("remove_accessory_hat_ids.txt")
CLIENT_CHARACTER = ROOT / "clien" / "Data" / "Character"
SERVER_CHARACTER = ROOT / "gms-server" / "wz" / "Character.wz"
CLIENT_EQP = ROOT / "clien" / "Data" / "String" / "Eqp.img"
SERVER_EQP = (
    ROOT / "gms-server" / "wz" / "String.wz" / "Eqp.img.xml",
    ROOT / "gms-server" / "wz-zh-CN" / "String.wz" / "Eqp.img.xml",
)
CLIENT_ACT = ROOT / "clien" / "Data" / "Quest" / "Act.img"
SERVER_ACT = (
    ROOT / "gms-server" / "wz" / "Quest.wz" / "Act.img.xml",
    ROOT / "gms-server" / "wz-zh-CN" / "Quest.wz" / "Act.img.xml",
)
CLIENT_SAY = ROOT / "clien" / "Data" / "Quest" / "Say.img"
SERVER_SAY = (
    ROOT / "gms-server" / "wz" / "Quest.wz" / "Say.img.xml",
    ROOT / "gms-server" / "wz-zh-CN" / "Quest.wz" / "Say.img.xml",
)
CLIENT_NPT = ROOT / "clien" / "Data" / "Etc" / "NPT_exception.img"
SERVER_NPT = (
    ROOT / "gms-server" / "wz" / "Etc.wz" / "NPT_exception.img.xml",
    ROOT / "gms-server" / "wz-zh-CN" / "Etc.wz" / "NPT_exception.img.xml",
)
CLIENT_COMMODITY = ROOT / "clien" / "Data" / "Etc" / "Commodity.img"
SERVER_COMMODITY = (
    ROOT / "gms-server" / "wz" / "Etc.wz" / "Commodity.img.xml",
    ROOT / "gms-server" / "wz-zh-CN" / "Etc.wz" / "Commodity.img.xml",
)
CATALOG = ROOT / "gms-server" / "src" / "main" / "resources" / "equipment-catalog" / "catalog.json"
HANDBOOKS = {
    "Cap": ROOT / "gms-server" / "handbook" / "Equip" / "Cap.txt",
    "Accessory": ROOT / "gms-server" / "handbook" / "Equip" / "Accessory.txt",
}
GACHAPON_SCRIPT = ROOT / "gms-server" / "scripts-zh-CN" / "npc" / "9110016.js"


def load_ids() -> tuple[int, ...]:
    text = re.sub(r"#.*", "", ID_FILE.read_text(encoding="utf-8"))
    ids: list[int] = []
    for token in text.split():
        if re.fullmatch(r"\d{7}", token):
            ids.append(int(token))
            continue
        match = re.fullmatch(r"(\d{7})-(\d{7})", token)
        if not match:
            raise ValueError(f"invalid manifest token: {token}")
        start, end = map(int, match.groups())
        if end < start:
            raise ValueError(f"descending manifest range: {token}")
        ids.extend(range(start, end + 1))
    if len(ids) != 276 or len(set(ids)) != 276:
        raise ValueError(f"expected 276 unique IDs, got {len(ids)} / {len(set(ids))}")
    if any(str(item_id)[:3] not in {"100", "103", "112", "113"} for item_id in ids):
        raise ValueError("manifest contains an unsupported equipment category")
    return tuple(sorted(ids))


def resource_category(item_id: int) -> str:
    return "Cap" if item_id // 10000 == 100 else "Accessory"


def string_category(item_id: int) -> str:
    return "Cap" if item_id // 10000 == 100 else "Accessory"


def walk_elements(root: ET.Element):
    def visit(node: ET.Element, path: tuple[str, ...]):
        for child in list(node):
            name = child.attrib.get("name")
            child_path = (*path, name) if name is not None else path
            yield child, child_path
            yield from visit(child, child_path)

    yield from visit(root, ())


def outlink_references(xml_text: str, ids: set[int]) -> list[tuple[tuple[str, ...], str]]:
    target = re.compile(r"^Character/(?:Cap|Accessory)/0(\d{7})\.img/")
    refs = []
    for node, path in walk_elements(ET.fromstring(xml_text)):
        if node.tag != "string" or node.attrib.get("name") != "_outlink":
            continue
        value = node.attrib.get("value", "")
        match = target.match(value)
        if match and int(match.group(1)) in ids:
            refs.append((path, value))
    return refs


def remove_gachapon_rewards(text: str, ids: set[int]) -> tuple[str, int]:
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    removed = 0
    index = 0
    while index < len(lines):
        if re.match(r"^\s*else if \(itemchance == \d+\) \{", lines[index]):
            end = index + 1
            while end < len(lines) and not re.match(r"^\s*}\s*$", lines[end]):
                end += 1
            if end >= len(lines):
                raise ValueError("unterminated gachapon reward branch")
            block = "".join(lines[index:end + 1])
            matches = {int(value) for value in re.findall(r"cm\.gainItem\(\s*(\d{7})", block)}
            if matches & ids:
                if not matches <= ids:
                    raise ValueError(f"mixed deleted/retained reward branch: {sorted(matches)}")
                removed += 1
                index = end + 1
                continue
        result.append(lines[index])
        index += 1
    return "".join(result), removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    ids = load_ids()
    id_set = set(ids)
    mode = "apply" if args.apply else "check"
    print(f"mode={mode} ids={len(ids)}")

    client_files = {
        item_id: CLIENT_CHARACTER / resource_category(item_id) / f"0{item_id}.img"
        for item_id in ids
    }
    server_files = {
        item_id: SERVER_CHARACTER / resource_category(item_id) / f"0{item_id}.img.xml"
        for item_id in ids
    }
    mismatched = [
        item_id for item_id in ids
        if client_files[item_id].exists() != server_files[item_id].exists()
    ]
    if mismatched:
        raise ValueError(f"client/server equipment file mismatch: {mismatched}")

    for category in ("Cap", "Accessory"):
        for path in sorted((SERVER_CHARACTER / category).glob("*.img.xml")):
            item_id = int(path.name[1:8]) if re.fullmatch(r"0\d{7}\.img\.xml", path.name) else None
            if item_id in id_set:
                continue
            refs = outlink_references(path.read_text(encoding="utf-8"), id_set)
            if refs:
                detail = ", ".join(f"{'/'.join(p)}={v}" for p, v in refs[:5])
                raise ValueError(f"remaining resource depends on deleted IMG: {path}: {detail}")

    existing = [item_id for item_id in ids if client_files[item_id].exists()]
    removed_file_bytes = sum(
        client_files[item_id].stat().st_size + server_files[item_id].stat().st_size
        for item_id in existing
    )
    if args.apply:
        for item_id in existing:
            client_files[item_id].unlink()
            server_files[item_id].unlink()
    print(f"equipment_files={len(existing)} bytes={removed_file_bytes}")

    eqp_paths = [("Eqp", string_category(item_id), str(item_id)) for item_id in ids]
    eqp_data, eqp_count = batch_remove_img(CLIENT_EQP.read_bytes(), eqp_paths)
    eqp_saved = apply_img(CLIENT_EQP, eqp_data, args.apply)
    print(f"client_eqp_records={eqp_count} bytes={eqp_saved}")
    for path in SERVER_EQP:
        text, count = batch_remove_xml(path.read_text(encoding="utf-8"), eqp_paths)
        saved = apply_text(path, text, args.apply)
        print(f"server_eqp={path.relative_to(ROOT)} records={count} bytes={saved}")

    canonical_npt = SERVER_NPT[0].read_text(encoding="utf-8")
    npt_paths = value_record_paths(canonical_npt, id_set)
    npt_data, npt_count = batch_remove_img(CLIENT_NPT.read_bytes(), npt_paths)
    npt_saved = apply_img(CLIENT_NPT, npt_data, args.apply)
    print(f"client_npt_records={npt_count} bytes={npt_saved}")
    for path in SERVER_NPT:
        text, count = batch_remove_xml(path.read_text(encoding="utf-8"), npt_paths)
        saved = apply_text(path, text, args.apply)
        print(f"server_npt={path.relative_to(ROOT)} records={count} bytes={saved}")

    canonical_commodity = SERVER_COMMODITY[0].read_text(encoding="utf-8")
    commodity_paths = value_parent_paths(canonical_commodity, "ItemId", id_set)
    commodity_data, commodity_count = batch_remove_img(CLIENT_COMMODITY.read_bytes(), commodity_paths)
    commodity_saved = apply_img(CLIENT_COMMODITY, commodity_data, args.apply)
    print(f"client_commodity_records={commodity_count} bytes={commodity_saved}")
    for path in SERVER_COMMODITY:
        text, count = batch_remove_xml(path.read_text(encoding="utf-8"), commodity_paths)
        saved = apply_text(path, text, args.apply)
        print(f"server_commodity={path.relative_to(ROOT)} records={count} bytes={saved}")

    canonical_act = SERVER_ACT[0].read_text(encoding="utf-8")
    act_remove, act_renames = quest_item_mutations(canonical_act, id_set)
    act_data, act_remove_count = batch_remove_img(CLIENT_ACT.read_bytes(), act_remove)
    act_data, act_rename_count = batch_rename_img(act_data, act_renames)
    act_saved = apply_img(CLIENT_ACT, act_data, args.apply)
    print(f"client_act_removed={act_remove_count} renamed={act_rename_count} bytes={act_saved}")
    for path in SERVER_ACT:
        text, remove_count = batch_remove_xml(path.read_text(encoding="utf-8"), act_remove)
        text, rename_count = batch_rename_xml(text, act_renames)
        saved = apply_text(path, text, args.apply)
        print(f"server_act={path.relative_to(ROOT)} removed={remove_count} renamed={rename_count} bytes={saved}")

    canonical_say = SERVER_SAY[0].read_text(encoding="utf-8")
    replacements = say_edits(canonical_say, id_set)
    say_data = CLIENT_SAY.read_bytes()
    client_say_count = 0
    from remove_weapon_resources import mutate_img, mutate_xml
    for path, value in replacements.items():
        try:
            say_data = mutate_img(say_data, "edit", path, values={"value": value}).data
        except KeyError:
            continue
        client_say_count += 1
    say_saved = apply_img(CLIENT_SAY, say_data, args.apply)
    print(f"client_say_strings={client_say_count} bytes={say_saved}")
    for path in SERVER_SAY:
        text = path.read_text(encoding="utf-8")
        count = 0
        for record_path, value in replacements.items():
            try:
                text = mutate_xml(text, "edit", record_path, values={"value": value})
            except KeyError:
                continue
            count += 1
        saved = apply_text(path, text, args.apply)
        print(f"server_say={path.relative_to(ROOT)} strings={count} bytes={saved}")

    gachapon_text, gachapon_count = remove_gachapon_rewards(
        GACHAPON_SCRIPT.read_text(encoding="utf-8"), id_set
    )
    gachapon_saved = apply_text(GACHAPON_SCRIPT, gachapon_text, args.apply)
    print(f"gachapon_rewards={gachapon_count} bytes={gachapon_saved}")

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    before_items = catalog["items"]
    catalog["items"] = [item for item in before_items if int(item["id"]) not in id_set]
    removed_catalog = len(before_items) - len(catalog["items"])
    for category in ("Cap", "Accessory"):
        remaining = [item for item in catalog["items"] if item.get("category") == category]
        catalog["atlases"][category]["count"] = len(remaining)
        catalog["atlases"][category]["icons"] = sum(bool(item.get("icon")) for item in remaining)
    new_catalog_text = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
    catalog_saved = apply_text(CATALOG, new_catalog_text, args.apply)
    print(f"catalog_items={removed_catalog} bytes={catalog_saved}")

    for category, path in HANDBOOKS.items():
        category_ids = {item_id for item_id in ids if resource_category(item_id) == category}
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        kept = [line for line in lines if not (line[:7].isdigit() and int(line[:7]) in category_ids)]
        saved = apply_text(path, "".join(kept), args.apply)
        print(f"handbook={category} lines={len(lines) - len(kept)} bytes={saved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
