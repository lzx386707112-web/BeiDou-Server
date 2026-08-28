#!/usr/bin/env python3
"""Incrementally complete legacy-safe Lacheln client quest records."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import WzImage, WzIntProperty, WzStringProperty, WzSubProperty  # noqa: E402


QUEST_IDS = tuple(range(34300, 34333))
EXISTING_IDS = (34303, 34304, 34312, 34313, 34314, 34315)
INSERT_IDS = tuple(quest_id for quest_id in QUEST_IDS if quest_id not in EXISTING_IDS)
CLIENT_ROOT = ROOT / "clien/Data/Quest"
SERVER_ROOT = ROOT / "gms-server/wz/Quest.wz"
CLIENT_NAMES = ("Act", "Check", "QuestInfo", "Say")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_baseline(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def xml_property(element: ET.Element, parent=None, *, name: str | None = None):
    prop_name = element.get("name", "") if name is None else name
    if element.tag == "imgdir":
        output = WzSubProperty(prop_name, parent)
        for child in element:
            output.add(xml_property(child, output))
        return output
    if element.tag == "int":
        return WzIntProperty(prop_name, int(element.get("value", "0")), parent)
    if element.tag == "string":
        return WzStringProperty(prop_name, element.get("value", ""), parent)
    raise RuntimeError(f"unsupported quest property: {element.tag}/{prop_name}")


def property_signature(prop):
    children = tuple(prop.children()) if isinstance(prop, WzSubProperty) else ()
    value = None if children else getattr(prop, "value", None)
    return (
        type(prop).__name__,
        prop.name,
        value,
        tuple(property_signature(child) for child in children),
    )


def server_roots() -> dict[str, dict[str, ET.Element]]:
    return {
        name: {
            child.get("name", ""): child
            for child in ET.parse(SERVER_ROOT / f"{name}.img.xml").getroot()
        }
        for name in CLIENT_NAMES
    }


def positive_source(roots: dict[str, dict[str, ET.Element]], name: str, quest_id: int):
    try:
        return roots[name][str(quest_id)]
    except KeyError as exc:
        raise RuntimeError(f"missing legacy {name} source: {quest_id}") from exc


def say_source(roots: dict[str, dict[str, ET.Element]], quest_id: int):
    signed_id = str(quest_id - 65536)
    try:
        return roots["Say"][signed_id]
    except KeyError as exc:
        raise RuntimeError(f"missing signed Say source: {signed_id}") from exc


def validate_server_contract(roots: dict[str, dict[str, ET.Element]]) -> None:
    for name in CLIENT_NAMES:
        missing = [
            quest_id
            for quest_id in QUEST_IDS
            if str(quest_id - 65536) not in roots[name]
        ]
        if missing:
            raise RuntimeError(f"server {name} is missing signed Lacheln IDs: {missing}")
    for name in ("Act", "Check"):
        for quest_id in QUEST_IDS:
            positive_source(roots, name, quest_id)


def validate_legacy_analog(
    name: str,
    image: WzImage,
    roots: dict[str, dict[str, ET.Element]],
) -> None:
    for quest_id in EXISTING_IDS:
        actual = image.root.child(str(quest_id))
        source = roots[name].get(str(quest_id))
        if actual is None or source is None:
            raise RuntimeError(f"missing working {name} analogue: {quest_id}")
        expected = xml_property(source, name=str(quest_id))
        if property_signature(actual) != property_signature(expected):
            raise RuntimeError(f"working {name} analogue diverged: {quest_id}")


def validate_say_projection(node: WzSubProperty, quest_id: int) -> None:
    if tuple(child.name for child in node.children()) != ("0", "1"):
        raise RuntimeError(f"unsupported Say branches: {quest_id}")
    for branch in node.children():
        if tuple(child.name for child in branch.children()) != ("0", "yes", "no"):
            raise RuntimeError(f"unsupported Say dialogue shape: {quest_id}/{branch.name}")
        if not isinstance(branch.child("0"), WzStringProperty):
            raise RuntimeError(f"missing Say text: {quest_id}/{branch.name}/0")
        for choice in ("yes", "no"):
            choice_node = branch.child(choice)
            if not isinstance(choice_node, WzSubProperty) or not isinstance(
                choice_node.child("0"), WzStringProperty
            ):
                raise RuntimeError(f"missing Say choice: {quest_id}/{branch.name}/{choice}")


def insertion_anchor(quest_id: int) -> str:
    if quest_id < 34303:
        return "34303"
    if quest_id < 34312:
        return "34312"
    return "34474"


def validate_client_image(name: str, data: bytes, *, contiguous: bool) -> None:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=f"{name}.img")
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"malformed {name}.img: truncated={image.truncated} "
            f"warnings={image.parse_warnings}"
        )
    records, order = arc.raw_record_state(data)
    if any(root_name.startswith("-") for root_name in order[()]):
        raise RuntimeError(f"signed client quest root remains in {name}.img")
    missing = [quest_id for quest_id in QUEST_IDS if (str(quest_id),) not in records]
    if missing:
        raise RuntimeError(f"client {name} is missing Lacheln IDs: {missing}")
    if contiguous:
        start = order[()].index(str(QUEST_IDS[0]))
        if order[()][start:start + len(QUEST_IDS)] != tuple(map(str, QUEST_IDS)):
            raise RuntimeError(f"client {name} Lacheln order is not contiguous")


def validate_inserted_values(
    name: str,
    data: bytes,
    roots: dict[str, dict[str, ET.Element]],
) -> None:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=f"{name}.img")
    image.parse()
    for quest_id in INSERT_IDS:
        source = (
            positive_source(roots, name, quest_id)
            if name in ("Act", "Check")
            else say_source(roots, quest_id)
        )
        expected = xml_property(source, name=str(quest_id))
        actual = image.root.child(str(quest_id))
        if actual is None or property_signature(actual) != property_signature(expected):
            raise RuntimeError(f"client {name} value mismatch: {quest_id}")


def build_expected() -> dict[Path, tuple[bytes, bytes]]:
    roots = server_roots()
    validate_server_contract(roots)
    output: dict[Path, tuple[bytes, bytes]] = {}
    for name in CLIENT_NAMES:
        path = CLIENT_ROOT / f"{name}.img"
        baseline = git_baseline(path)
        image = WzImage.from_bytes(baseline, key=arc.GMS_KEY, name=path.name)
        image.parse()
        if image.truncated or image.parse_warnings:
            raise RuntimeError(f"HEAD baseline is malformed: {path}")

        if name == "QuestInfo":
            validate_client_image(name, baseline, contiguous=False)
            output[path] = (baseline, baseline)
            continue

        validate_legacy_analog(name, image, roots)
        data = baseline
        nodes_by_anchor: dict[str, list[WzSubProperty]] = {}
        for quest_id in INSERT_IDS:
            source = (
                positive_source(roots, name, quest_id)
                if name in ("Act", "Check")
                else say_source(roots, quest_id)
            )
            node = xml_property(source, name=str(quest_id))
            if name == "Say":
                validate_say_projection(node, quest_id)
            nodes_by_anchor.setdefault(insertion_anchor(quest_id), []).append(node)
        for anchor, nodes in nodes_by_anchor.items():
            data = arc.insert_property_records_before(
                data, (), nodes, anchor
            )

        approved = {(str(quest_id),) for quest_id in INSERT_IDS}
        arc.verify_raw_record_insert_scope(baseline, data, approved)
        validate_client_image(name, data, contiguous=True)
        validate_inserted_values(name, data, roots)
        output[path] = (baseline, data)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing")
    args = parser.parse_args()

    expected = build_expected()
    changed: list[Path] = []
    for path, (baseline, result) in expected.items():
        current = path.read_bytes()
        if current not in (baseline, result):
            raise RuntimeError(f"refusing unknown client quest state: {path}")
        if current == result:
            continue
        if args.check:
            raise SystemExit(f"{path.name} needs Lacheln quest repair")
        arc.atomic_write_bytes(path, result)
        changed.append(path)

    print(f"Lacheln client quests ok: changed={len(changed)} inserted={len(INSERT_IDS)}")
    for path, (_baseline, result) in expected.items():
        print(f"{path.relative_to(ROOT)} sha256={sha256(result)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
