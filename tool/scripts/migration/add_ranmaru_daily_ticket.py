#!/usr/bin/env python3
"""Install daily Momijigaoka kill quest 57481 / server signed -8055."""

from __future__ import annotations

import hashlib
import sys
import xml.etree.ElementTree as ET
import xml.parsers.expat
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(ROOT / "tool/scripts/migration")]

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_ranmaru as ranmaru  # noqa: E402
from migrate_twilight_perion_monster_park import (  # noqa: E402
    add_int,
    add_string,
    add_sub,
    append_named_records,
)
from wzpy import WzImage, WzSubProperty  # noqa: E402
from wzpy.incremental_img import replace_img_record  # noqa: E402


CLIENT_QUEST_ID = 57481
SERVER_QUEST_ID = CLIENT_QUEST_ID - 65536
CLIENT_QUEST_NAME = str(CLIENT_QUEST_ID)
SERVER_QUEST_NAME = str(SERVER_QUEST_ID)
QUEST_NPC_ID = 9130000
TICKET_ID = 4000697
KILL_COUNT = 200
QUEST_NAMES = ("Act", "Check", "QuestInfo", "Say")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_quest_image(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=arc.GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"unsafe quest IMG {path}: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    return image


def reject_alias_collision(path: Path) -> None:
    image = load_quest_image(path)
    names = {child.name for child in image.root.children()}
    if SERVER_QUEST_NAME in names and CLIENT_QUEST_NAME in names:
        raise RuntimeError(
            f"alias collision in {path.name}: {CLIENT_QUEST_NAME} and {SERVER_QUEST_NAME}"
        )
    if SERVER_QUEST_NAME in names:
        raise RuntimeError(f"signed alias {SERVER_QUEST_NAME} exists in client {path.name}")


def progress_line() -> str:
    lines = [
        "在枫叶丘陵田野击杀以下怪物各200只：",
        "",
    ]
    for index, mob_id in enumerate(ranmaru.FIELD_MOBS, start=1):
        lines.append(f"#o{mob_id}# #r#a{CLIENT_QUEST_ID}{index}##k")
    return "\n".join(lines)


def build_quest_node(record_name: str, kind: str) -> WzSubProperty:
    node = WzSubProperty(record_name)
    if kind == "QuestInfo":
        add_string(node, "0", "去枫叶丘陵找#b#p9130000##k，听取田野清剿委托。")
        add_string(node, "1", progress_line())
        add_string(node, "2", "完成了枫叶丘陵田野清剿，获得了#b#t4000697##k。")
        add_int(node, "area", 56)
        add_string(node, "name", "[每日] 枫叶丘陵的清剿")
        return node
    if kind == "Check":
        start = add_sub(node, "0")
        add_int(start, "interval", 1440)
        add_int(start, "lvmin", 120)
        add_int(start, "npc", QUEST_NPC_ID)
        end = add_sub(node, "1")
        add_int(end, "npc", QUEST_NPC_ID)
        add_int(end, "order", 1)
        mobs = add_sub(end, "mob")
        for index, mob_id in enumerate(ranmaru.FIELD_MOBS):
            entry = add_sub(mobs, str(index))
            add_int(entry, "id", mob_id)
            add_int(entry, "count", KILL_COUNT)
        return node
    if kind == "Act":
        add_sub(node, "0")
        act_end = add_sub(node, "1")
        items = add_sub(act_end, "item")
        reward = add_sub(items, "0")
        add_int(reward, "id", TICKET_ID)
        add_int(reward, "count", 1)
        return node
    if kind == "Say":
        start_say = add_sub(node, "0")
        add_string(
            start_say,
            "0",
            "枫叶丘陵田野的织田残党太多了。去击杀#b#o9421511#、#o9421512#、#o9421513#、#o9421514##k各200只。完成后给你#b#t4000697##k。",
        )
        no = add_sub(start_say, "no")
        add_string(no, "0", "准备好再来找我。")
        yes = add_sub(start_say, "yes")
        add_string(yes, "0", "去田野清剿那些残党，打完回来。")
        end_say = add_sub(node, "1")
        add_string(end_say, "0", "干得漂亮。拿好门票，去秘密祭坛的光洞进入森兰丸地盘。")
        return node
    raise RuntimeError(f"unknown quest file {kind}")


@dataclass
class XmlSpan:
    path: str
    start: int
    end: int = -1
    self_closing: bool = False


def _tag_end(data: bytes, start: int) -> int:
    quote = 0
    for index in range(start, len(data)):
        byte = data[index]
        if quote:
            if byte == quote:
                quote = 0
        elif byte in (34, 39):
            quote = byte
        elif byte == 62:
            return index + 1
    raise RuntimeError("XML tag was not closed")


def xml_spans(data: bytes) -> dict[str, XmlSpan]:
    result: dict[str, XmlSpan] = {}
    stack: list[XmlSpan] = []
    parser = xml.parsers.expat.ParserCreate()

    def start(_tag: str, attrs: dict[str, str]) -> None:
        name = attrs.get("name", "")
        path = f"{stack[-1].path}/{name}".strip("/") if stack else ""
        offset = parser.CurrentByteIndex
        open_end = _tag_end(data, offset)
        span = XmlSpan(path, offset, self_closing=data[offset:open_end].rstrip().endswith(b"/>"))
        result[path] = span
        stack.append(span)

    def end(_tag: str) -> None:
        span = stack.pop()
        span.end = _tag_end(data, parser.CurrentByteIndex) if not span.self_closing else _tag_end(data, span.start)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.Parse(data, True)
    return result


def replace_xml_span(original: str, target: str, fragment: str) -> str:
    data = original.encode("utf-8")
    spans = xml_spans(data)
    span = spans.get(target)
    if span is None:
        raise RuntimeError(f"missing XML record {target}")
    start = span.start
    if start > 0 and data[start - 1:start] == b"\n":
        start -= 1
        fragment_bytes = b"\n" + fragment.encode("utf-8")
    else:
        fragment_bytes = fragment.encode("utf-8")
    updated = data[:start] + fragment_bytes + data[span.end:]
    ET.fromstring(updated)
    return updated.decode("utf-8")


def upsert_client_record(path: Path, node: WzSubProperty) -> None:
    reject_alias_collision(path)
    original = path.read_bytes()
    records, _ = arc.raw_record_state(original)
    if (node.name,) in records:
        updated = replace_img_record(original, (node.name,), node, region="GMS").data
        arc.verify_raw_record_scope(original, updated, {(node.name,)}, allow_additions=False)
        parsed = WzImage.from_bytes(updated, key=arc.GMS_KEY, name=path.name)
        parsed.parse()
        if parsed.truncated or parsed.parse_warnings:
            raise RuntimeError(f"replaced quest IMG failed validation: {path}")
        if updated != original:
            arc.atomic_write_bytes(path, updated)
        return
    append_named_records(path, (), [node])


def upsert_server_record(path: Path, node: WzSubProperty, kind: str) -> None:
    if not path.exists():
        return
    original = path.read_text(encoding="utf-8")
    fragment = arc.property_to_xml(node, indent=1)
    spans = xml_spans(original.encode("utf-8"))
    if CLIENT_QUEST_NAME in spans and SERVER_QUEST_NAME in spans:
        raise RuntimeError(f"server XML has both {CLIENT_QUEST_NAME} and {SERVER_QUEST_NAME} in {path}")
    if SERVER_QUEST_NAME in spans:
        span = spans[SERVER_QUEST_NAME]
        body = original.encode("utf-8")[span.start:span.end]
        if kind == "QuestInfo" and b"#a574811#" not in body:
            updated = replace_xml_span(original, SERVER_QUEST_NAME, fragment)
        else:
            return
    elif CLIENT_QUEST_NAME in spans:
        updated = replace_xml_span(original, CLIENT_QUEST_NAME, fragment)
    else:
        updated = arc.append_xml_properties(original, (), [node])
        ET.fromstring(updated)
    if updated != original:
        arc.atomic_write_text(path, updated)


def migrate_daily_quest() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name in QUEST_NAMES:
        client_node = build_quest_node(CLIENT_QUEST_NAME, name)
        server_node = build_quest_node(SERVER_QUEST_NAME, name)
        client = ROOT / f"clien/Data/Quest/{name}.img"
        if name == "QuestInfo":
            upsert_client_record(client, client_node)
        else:
            reject_alias_collision(client)
            append_named_records(client, (), [client_node])
        hashes[str(client.relative_to(ROOT))] = sha256_file(client)
        for tree in ("wz", "wz-zh-CN"):
            server = ROOT / f"gms-server/{tree}/Quest.wz/{name}.img.xml"
            upsert_server_record(server, server_node, name)
            if server.exists():
                hashes[str(server.relative_to(ROOT))] = sha256_file(server)
    return hashes


def main() -> int:
    first = migrate_daily_quest()
    second = migrate_daily_quest()
    if first != second:
        raise RuntimeError(f"daily quest upsert is not idempotent: {first} vs {second}")
    print("daily quest 57481 / -8055 ok")
    for path, digest in first.items():
        print(f"{path} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
