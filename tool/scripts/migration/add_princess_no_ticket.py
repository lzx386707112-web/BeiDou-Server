#!/usr/bin/env python3
"""Add the Princess No ticket and make the Maple Hill daily reward selectable."""

from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

spec = importlib.util.spec_from_file_location(
    "arcane_migration",
    ROOT / "tool/scripts/migration/migrate_arcane_river_expansion.py",
)
arc = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = arc
spec.loader.exec_module(arc)

from wzpy import WzImage, WzStringProperty, WzSubProperty  # noqa: E402
from wzpy.incremental_img import mutate_img  # noqa: E402
from wzpy.incremental_xml import mutate_xml  # noqa: E402


SOURCE_TICKET = 4000697
TARGET_TICKET = 4000699
SOURCE_ITEM_RECORD = f"0{SOURCE_TICKET}"
TARGET_ITEM_RECORD = f"0{TARGET_TICKET}"
ITEM_ANCHOR = "04000828"
STRING_ANCHOR = "4000828"
QUEST_ID = "57481"
SERVER_QUEST_ID = "-8055"

TICKET_NAME = "浓姬挑战门票"
TICKET_DESC = "可进入浓姬所在地的免费门票，使用1次即作废。"
QUEST_COMPLETE_TEXT = "完成了枫叶丘陵田野清剿，获得了选择的挑战门票。"
QUEST_OFFER_TEXT = (
    "枫叶丘陵田野的织田残党太多了。去击杀#b#o9421511#、#o9421512#、"
    "#o9421513#、#o9421514##k各200只。完成后可在#b#t4000697##k和"
    "#b#t4000699##k中选择一张。"
)
QUEST_FINISH_TEXT = "干得漂亮。请选择一张挑战门票，前往对应的讨伐入口。"


def load_client(path: Path):
    image = arc.load_image(path, arc.GMS_KEY)
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"malformed {path}: truncated={image.truncated}, warnings={image.parse_warnings}"
        )
    return image


def verify_scoped_mutation(
    before: bytes,
    after: bytes,
    approved_roots: set[tuple[str, ...]],
) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)

    def affected(path: tuple[str, ...]) -> bool:
        return any(
            path[:len(root)] == root or root[:len(path)] == path
            for root in approved_roots
        )

    for path in set(before_records) - set(after_records):
        if not affected(path):
            raise RuntimeError(f"removed protected IMG record: {path}")
    for path in set(after_records) - set(before_records):
        if not affected(path):
            raise RuntimeError(f"added unapproved IMG record: {path}")
    for path in set(before_records) & set(after_records):
        if not affected(path) and before_records[path] != after_records[path]:
            raise RuntimeError(f"changed protected IMG record: {path}")
    for parent, names in before_orders.items():
        current = after_orders.get(parent)
        if current is None:
            if not affected(parent):
                raise RuntimeError(f"removed protected IMG container: {parent}")
            continue
        common = set(names) & set(current)
        if tuple(name for name in names if name in common) != tuple(
            name for name in current if name in common
        ):
            raise RuntimeError(f"reordered IMG siblings at {parent}")


def make_string_record() -> WzSubProperty:
    record = WzSubProperty(str(TARGET_TICKET))
    record.add(WzStringProperty("desc", TICKET_DESC, record))
    record.add(WzStringProperty("name", TICKET_NAME, record))
    return record


def stage_item(client_outputs: dict[Path, bytes], xml_outputs: dict[Path, str]) -> None:
    client = ROOT / "clien/Data/Item/Etc/0400.img"
    before = client.read_bytes()
    image = load_client(client)
    source = image.root.child(SOURCE_ITEM_RECORD)
    if not isinstance(source, WzSubProperty):
        raise RuntimeError(f"missing source item {SOURCE_ITEM_RECORD}")
    after = before
    if image.root.child(TARGET_ITEM_RECORD) is None:
        old_name = source.name
        source.name = TARGET_ITEM_RECORD
        try:
            after = arc.insert_property_record_before(after, (), source, ITEM_ANCHOR)
        finally:
            source.name = old_name
        arc.verify_raw_record_insert_scope(before, after, {(TARGET_ITEM_RECORD,)})
    client_outputs[client] = after

    server = ROOT / "gms-server/wz/Item.wz/Etc/0400.img.xml"
    text = server.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    if root.find(f'./imgdir[@name="{TARGET_ITEM_RECORD}"]') is None:
        old_name = source.name
        source.name = TARGET_ITEM_RECORD
        try:
            text = arc.insert_xml_properties_before(text, (), [source], ITEM_ANCHOR)
        finally:
            source.name = old_name
    ET.fromstring(text)
    xml_outputs[server] = text


def stage_strings(client_outputs: dict[Path, bytes], xml_outputs: dict[Path, str]) -> None:
    record = make_string_record()
    client = ROOT / "clien/Data/String/Etc.img"
    before = client.read_bytes()
    image = load_client(client)
    after = before
    if image.root.get(f"Etc/{TARGET_TICKET}") is None:
        after = arc.insert_property_record_before(before, ("Etc",), record, STRING_ANCHOR)
        arc.verify_raw_record_insert_scope(before, after, {("Etc", str(TARGET_TICKET))})
    client_outputs[client] = after

    for tree in ("wz", "wz-zh-CN"):
        server = ROOT / f"gms-server/{tree}/String.wz/Etc.img.xml"
        text = server.read_text(encoding="utf-8")
        root = ET.fromstring(text)
        parent = root.find('./imgdir[@name="Etc"]')
        if parent is None:
            raise RuntimeError(f"missing Etc string parent in {server}")
        if parent.find(f'./imgdir[@name="{TARGET_TICKET}"]') is None:
            text = arc.insert_xml_properties_before(text, ("Etc",), [record], STRING_ANCHOR)
        ET.fromstring(text)
        xml_outputs[server] = text


def stage_client_quest(client_outputs: dict[Path, bytes]) -> None:
    specs = {
        "Act": ((QUEST_ID, "1", "item"), None),
        "QuestInfo": ((QUEST_ID, "2"), QUEST_COMPLETE_TEXT),
        "Say": ((QUEST_ID, "0", "0"), QUEST_OFFER_TEXT),
    }
    for part, (path, value) in specs.items():
        client = ROOT / f"clien/Data/Quest/{part}.img"
        before = client.read_bytes()
        image = load_client(client)
        node = image.root.get("/".join(path))
        after = before
        if value is None:
            if node is not None:
                after = mutate_img(before, "remove", path, region="GMS").data
        elif getattr(node, "value", None) != value:
            after = mutate_img(
                before, "edit", path, values={"value": value}, region="GMS"
            ).data
        verify_scoped_mutation(before, after, {path})
        client_outputs[client] = after

    client = ROOT / "clien/Data/Quest/Say.img"
    before = client_outputs[client]
    image = WzImage.from_bytes(before, key=arc.GMS_KEY, name=client.name)
    image.parse()
    path = (QUEST_ID, "1", "0")
    if getattr(image.root.get("/".join(path)), "value", None) != QUEST_FINISH_TEXT:
        after = mutate_img(
            before, "edit", path, values={"value": QUEST_FINISH_TEXT}, region="GMS"
        ).data
        verify_scoped_mutation(before, after, {path})
        client_outputs[client] = after


def stage_server_quest(xml_outputs: dict[Path, str]) -> None:
    specs = {
        "Act": ((SERVER_QUEST_ID, "1", "item"), None),
        "QuestInfo": ((SERVER_QUEST_ID, "2"), QUEST_COMPLETE_TEXT),
        "Say": ((SERVER_QUEST_ID, "0", "0"), QUEST_OFFER_TEXT),
    }
    for tree in ("wz", "wz-zh-CN"):
        for part, (path, value) in specs.items():
            server = ROOT / f"gms-server/{tree}/Quest.wz/{part}.img.xml"
            text = server.read_text(encoding="utf-8")
            root = ET.fromstring(text)
            xpath = "." + "".join(f'/imgdir[@name="{name}"]' for name in path)
            node = root.find(xpath)
            if value is None:
                if node is not None:
                    text = mutate_xml(text, "remove", path)
            elif node is None or node.get("value") != value:
                text = mutate_xml(text, "edit", path, kind="String", values={"value": value})
            if part == "Say":
                root = ET.fromstring(text)
                finish_path = (SERVER_QUEST_ID, "1", "0")
                finish_xpath = "." + "".join(
                    f'/imgdir[@name="{name}"]' for name in finish_path
                )
                finish = root.find(finish_xpath)
                if finish is None or finish.get("value") != QUEST_FINISH_TEXT:
                    text = mutate_xml(
                        text, "edit", finish_path, kind="String",
                        values={"value": QUEST_FINISH_TEXT},
                    )
            ET.fromstring(text)
            xml_outputs[server] = text


def validate_staged(client_outputs: dict[Path, bytes], xml_outputs: dict[Path, str]) -> None:
    for path, data in client_outputs.items():
        image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=path.name)
        image.parse()
        if image.truncated or image.parse_warnings:
            raise RuntimeError(f"staged IMG failed to parse: {path}")
    for path, text in xml_outputs.items():
        ET.fromstring(text)


def main() -> int:
    client_outputs: dict[Path, bytes] = {}
    xml_outputs: dict[Path, str] = {}
    stage_item(client_outputs, xml_outputs)
    stage_strings(client_outputs, xml_outputs)
    stage_client_quest(client_outputs)
    stage_server_quest(xml_outputs)
    validate_staged(client_outputs, xml_outputs)

    changed = 0
    for path, data in client_outputs.items():
        if data != path.read_bytes():
            arc.atomic_write_bytes(path, data)
            changed += 1
    for path, text in xml_outputs.items():
        if text != path.read_text(encoding="utf-8"):
            arc.atomic_write_text(path, text)
            changed += 1
    print(f"Princess No ticket migration complete: {changed} files changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
