from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
import xml.parsers.expat
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WZPY_ROOT = ROOT / "tool" / "wz-python"
if str(WZPY_ROOT) not in sys.path:
    sys.path.insert(0, str(WZPY_ROOT))

from flask import Flask, jsonify, render_template, request, send_file
from PIL import Image
from wzpy import WzImage, WzKey
from wzpy.canvas import decode_canvas
from wzpy.incremental_img import mutate_img, replace_img_record, scan_img
from wzpy.properties import (
    WzDoubleProperty,
    WzFloatProperty,
    WzIntProperty,
    WzLongProperty,
    WzNullProperty,
    WzShortProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)

QUEST_FILES = ("QuestInfo", "Check", "Act", "Say")
CLIENT_QUEST = ROOT / "clien" / "Data" / "Quest"
SERVER_QUEST = ROOT / "gms-server" / "wz" / "Quest.wz"
ZH_QUEST = ROOT / "gms-server" / "wz-zh-CN" / "Quest.wz"
SCRIPT_ROOTS = {
    "main": ROOT / "gms-server" / "scripts",
    "zh": ROOT / "gms-server" / "scripts-zh-CN",
}
BACKUP_ROOT = ROOT / ".workbuddy" / "resource-workbench-backups" / "quests"
ITEM_STRINGS = ROOT / "gms-server" / "wz-zh-CN" / "String.wz"
EQUIPMENT_CATALOG = ROOT / "gms-server" / "src" / "main" / "resources" / "equipment-catalog"
APPLICATION_CONFIG = ROOT / "gms-server" / "src" / "main" / "resources" / "application.yml"

REGION_NAMES = {
    "victoria": "金银岛", "ossyria": "神秘岛", "elin": "艾琳森林",
    "china": "东方神州", "jp": "日本", "thai": "泰国",
    "singapore": "新加坡·马来西亚", "maple": "彩虹岛",
    "MasteriaGL": "马斯特里亚", "weddingGL": "婚礼村",
    "HalloweenGL": "万圣节", "Episode1GL": "剧情活动",
    "event": "活动地图", "etc": "其他", "grandis": "格兰蒂斯",
    "unknown": "未定位",
}

app = Flask(__name__, template_folder=str(HERE / "templates"), static_folder=str(HERE / "static"))
_WRITE_LOCK = threading.Lock()


def _quest_xml_path(base: Path, name: str) -> Path:
    return base / f"{name}.img.xml"


def _child(parent: ET.Element | None, name: str) -> ET.Element | None:
    if parent is None:
        return None
    return next((node for node in parent if node.get("name") == name), None)


def _value(parent: ET.Element | None, name: str, default: Any = None) -> Any:
    node = _child(parent, name)
    if node is None:
        return default
    raw = node.get("value")
    if node.tag in ("int", "short", "long"):
        try:
            return int(raw or 0)
        except ValueError:
            return default
    return raw if raw is not None else default


def _dir(parent: ET.Element | None, name: str, create: bool = False) -> ET.Element | None:
    node = _child(parent, name)
    if node is None and create and parent is not None:
        node = ET.SubElement(parent, "imgdir", {"name": name})
    return node


def _set_scalar(parent: ET.Element, name: str, value: Any, kind: str = "string") -> None:
    node = _child(parent, name)
    if value is None or value == "":
        if node is not None:
            parent.remove(node)
        return
    if node is None:
        node = ET.SubElement(parent, kind, {"name": name})
    elif node.tag != kind:
        index = list(parent).index(node)
        parent.remove(node)
        node = ET.Element(kind, {"name": name})
        parent.insert(index, node)
    node.set("value", str(value))


def _load_roots(base: Path | None = None) -> dict[str, ET.Element]:
    base = SERVER_QUEST if base is None else base
    return {name: ET.parse(_quest_xml_path(base, name)).getroot() for name in QUEST_FILES}


def _quest_nodes(quest_id: str, base: Path | None = None) -> dict[str, ET.Element | None]:
    return {name: _child(root, quest_id) for name, root in _load_roots(base).items()}


def _validate_id(raw: Any, label: str = "ID") -> str:
    value = str(raw or "").strip()
    if not re.fullmatch(r"-?\d{1,9}", value):
        raise ValueError(f"{label} 必须是最多 9 位数字，可带负号")
    return value


def _node_fragment(node: ET.Element | None) -> str:
    if node is None:
        return ""
    clone = copy.deepcopy(node)
    clone.tail = None
    ET.indent(clone, space="  ")
    return ET.tostring(clone, encoding="unicode", short_empty_elements=True)


def _parse_fragment(raw: str, quest_id: str) -> ET.Element:
    node = ET.fromstring(raw)
    if node.tag != "imgdir" or node.get("name") != quest_id:
        raise ValueError(f"根节点必须是 <imgdir name=\"{quest_id}\">")
    return node


def _property_from_xml(node: ET.Element, parent=None):
    name = node.get("name", "")
    if node.tag == "imgdir":
        prop = WzSubProperty(name, parent)
        for child in node:
            prop.add(_property_from_xml(child, prop))
        return prop
    if node.tag == "null":
        return WzNullProperty(name, parent)
    if node.tag == "short":
        return WzShortProperty(name, int(node.get("value", "0")), parent)
    if node.tag == "int":
        return WzIntProperty(name, int(node.get("value", "0")), parent)
    if node.tag == "long":
        return WzLongProperty(name, int(node.get("value", "0")), parent)
    if node.tag == "float":
        return WzFloatProperty(name, float(node.get("value", "0")), parent)
    if node.tag == "double":
        return WzDoubleProperty(name, float(node.get("value", "0")), parent)
    if node.tag == "string":
        return WzStringProperty(name, node.get("value", ""), parent)
    if node.tag == "uol":
        return WzUolProperty(name, node.get("value", ""), parent)
    if node.tag == "vector":
        return WzVectorProperty(name, int(node.get("x", "0")), int(node.get("y", "0")), parent)
    raise ValueError(f"任务记录包含不支持的节点类型: {node.tag}/{name}")


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
    raise ValueError("XML 标签未闭合")


def _xml_spans(data: bytes) -> dict[str, XmlSpan]:
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


def _format_fragment(node: ET.Element) -> bytes:
    clone = copy.deepcopy(node)
    clone.tail = None
    ET.indent(clone, space="  ")
    text = ET.tostring(clone, encoding="unicode", short_empty_elements=True)
    return text.encode("utf-8")


def _replace_xml_record(data: bytes, quest_id: str, node: ET.Element | None) -> bytes:
    spans = _xml_spans(data)
    span = spans.get(quest_id)
    if node is None:
        if span is None:
            return data
        start = span.start
        if start > 0 and data[start - 1:start] == b"\n":
            start -= 1
        return data[:start] + data[span.end:]
    fragment = _format_fragment(node)
    if span is not None:
        return data[:span.start] + fragment + data[span.end:]
    closing = data.rfind(b"</imgdir>")
    if closing < 0:
        raise ValueError("XML 缺少根结束标签")
    prefix = b"" if data[:closing].endswith(b"\n") else b"\n"
    indented = b"  " + fragment.replace(b"\n", b"\n  ")
    return data[:closing] + prefix + indented + b"\n" + data[closing:]


def _replace_img_record(data: bytes, quest_id: str, node: ET.Element | None) -> bytes:
    exists = any(record.name == quest_id for record in scan_img(data, region="GMS").root.records)
    if node is None:
        return mutate_img(data, "remove", (quest_id,), region="GMS").data if exists else data
    if not exists:
        data = mutate_img(data, "add", (), name=quest_id, kind="SubProperty", region="GMS").data
    return replace_img_record(data, (quest_id,), _property_from_xml(node), region="GMS").data


def _validated_payloads(quest_id: str, nodes: dict[str, ET.Element | None]) -> dict[Path, bytes]:
    payloads: dict[Path, bytes] = {}
    for name in QUEST_FILES:
        client = CLIENT_QUEST / f"{name}.img"
        patched_img = _replace_img_record(client.read_bytes(), quest_id, nodes[name])
        image = WzImage.from_bytes(patched_img, key=WzKey.for_region("GMS"), name=client.name)
        image.parse()
        if image.truncated or image.parse_warnings:
            raise ValueError(f"{client.name} 增量结果解析失败")
        payloads[client] = patched_img
        for base in (SERVER_QUEST, ZH_QUEST):
            xml_path = _quest_xml_path(base, name)
            patched_xml = _replace_xml_record(xml_path.read_bytes(), quest_id, nodes[name])
            ET.fromstring(patched_xml)
            payloads[xml_path] = patched_xml
    return payloads


def _commit(payloads: dict[Path, bytes]) -> None:
    originals = {path: path.read_bytes() for path in payloads}
    temporaries: dict[Path, Path] = {}
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        for path, payload in payloads.items():
            relative = path.relative_to(ROOT)
            backup = BACKUP_ROOT / ("__".join(relative.parts) + ".bak")
            if not backup.exists():
                backup.write_bytes(originals[path])
            fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            temporaries[path] = Path(raw)
        replaced: list[Path] = []
        try:
            for path, temporary in temporaries.items():
                os.replace(temporary, path)
                replaced.append(path)
        except Exception:
            for path in replaced:
                path.write_bytes(originals[path])
            raise
    finally:
        for temporary in temporaries.values():
            temporary.unlink(missing_ok=True)


def _item_rows(node: ET.Element | None) -> list[dict[str, Any]]:
    container = _dir(node, "item")
    rows = []
    if container is not None:
        for item in container:
            values = {child.get("name", ""): _value(item, child.get("name", "")) for child in item}
            rows.append({"values": values})
    return rows


def _replace_items(parent: ET.Element, rows: list[dict[str, Any]]) -> None:
    old = _child(parent, "item")
    if old is not None:
        parent.remove(old)
    if not rows:
        return
    container = ET.SubElement(parent, "imgdir", {"name": "item"})
    for index, row in enumerate(rows):
        item = ET.SubElement(container, "imgdir", {"name": str(index)})
        for name, value in (row.get("values") or {}).items():
            if value is not None and value != "":
                ET.SubElement(item, "int", {"name": str(name), "value": str(int(value))})


def _mob_rows(node: ET.Element | None, names: dict[str, str] | None = None) -> list[dict[str, Any]]:
    container = _dir(node, "mob")
    result = []
    if container is None:
        return result
    for mob in container:
        mob_id = str(_value(mob, "id", ""))
        if mob_id:
            result.append({"id": mob_id, "count": int(_value(mob, "count", 1)),
                           "name": (names or {}).get(mob_id, mob_id)})
    return result


def _replace_mobs(parent: ET.Element, rows: list[dict[str, Any]]) -> None:
    old = _child(parent, "mob")
    index = list(parent).index(old) if old is not None else len(parent)
    if old is not None:
        parent.remove(old)
    if not rows:
        return
    container = ET.Element("imgdir", {"name": "mob"})
    for row_index, row in enumerate(rows):
        mob_id = str(row.get("id", "")).strip()
        count = int(row.get("count", 1))
        if not re.fullmatch(r"\d{1,9}", mob_id):
            raise ValueError("怪物 ID 必须是最多 9 位数字")
        if count < 1:
            raise ValueError("击杀数量必须大于 0")
        mob = ET.SubElement(container, "imgdir", {"name": str(row_index)})
        ET.SubElement(mob, "int", {"name": "count", "value": str(count)})
        ET.SubElement(mob, "int", {"name": "id", "value": mob_id})
    parent.insert(index, container)


def _quest_requirements(node: ET.Element | None, names: dict[str, str] | None = None) -> list[dict[str, Any]]:
    container = _dir(node, "quest")
    result = []
    if container is None:
        return result
    for requirement in container:
        quest_id = str(_value(requirement, "id", ""))
        if not quest_id:
            continue
        result.append({
            "id": quest_id, "state": int(_value(requirement, "state", 0)),
            "name": (names or {}).get(quest_id, quest_id),
        })
    return result


def _replace_quest_requirements(parent: ET.Element, rows: list[dict[str, Any]]) -> None:
    old = _child(parent, "quest")
    index = list(parent).index(old) if old is not None else len(parent)
    if old is not None:
        parent.remove(old)
    if not rows:
        return
    container = ET.Element("imgdir", {"name": "quest"})
    for row_index, row in enumerate(rows):
        quest_id = _validate_id(row.get("id"), "前置任务 ID")
        state = int(row.get("state", 2))
        if state not in (0, 1, 2):
            raise ValueError("前置任务状态只能是未开始、进行中或已完成")
        requirement = ET.SubElement(container, "imgdir", {"name": str(row_index)})
        ET.SubElement(requirement, "int", {"name": "id", "value": quest_id})
        ET.SubElement(requirement, "int", {"name": "state", "value": str(state)})
    parent.insert(index, container)


def _basic_payload(nodes: dict[str, ET.Element | None], body: dict[str, Any]) -> dict[str, ET.Element]:
    quest_id = _validate_id(body.get("questId"), "任务 ID")
    result = {name: copy.deepcopy(nodes[name]) if nodes[name] is not None else ET.Element("imgdir", {"name": quest_id}) for name in QUEST_FILES}
    info = result["QuestInfo"]
    for key in ("0", "1", "2", "name", "parent"):
        _set_scalar(info, key, body.get({"0": "contentStart", "1": "contentProgress", "2": "contentComplete"}.get(key, key)))
    for key in ("area", "order"):
        _set_scalar(info, key, body.get(key), "int")

    check = result["Check"]
    start = _dir(check, "0", True)
    finish = _dir(check, "1", True)
    assert start is not None and finish is not None
    _set_scalar(start, "npc", body.get("startNpc"), "int")
    _set_scalar(start, "lvmin", body.get("levelMin"), "int")
    _set_scalar(start, "lvmax", body.get("levelMax"), "int")
    _set_scalar(finish, "npc", body.get("endNpc"), "int")

    act = result["Act"]
    act_start = _dir(act, "0", True)
    act_finish = _dir(act, "1", True)
    assert act_start is not None and act_finish is not None
    _set_scalar(act_finish, "exp", body.get("rewardExp"), "int")
    _set_scalar(act_finish, "money", body.get("rewardMeso"), "int")
    _set_scalar(act_finish, "nextQuest", body.get("nextQuest"), "int")

    say = result["Say"]
    say_start = _dir(say, "0", True)
    say_finish = _dir(say, "1", True)
    assert say_start is not None and say_finish is not None
    _set_scalar(say_start, "0", body.get("dialogStart"))
    _set_scalar(say_finish, "0", body.get("dialogComplete"))

    items = body.get("items") or {}
    _replace_items(start, items.get("checkStart") or [])
    _replace_items(finish, items.get("checkComplete") or [])
    _replace_items(act_start, items.get("actStart") or [])
    _replace_items(act_finish, items.get("actComplete") or [])
    if "requirements" in body:
        _replace_quest_requirements(start, body.get("requirements") or [])
    if "mobs" in body:
        mobs = body.get("mobs") or {}
        _replace_mobs(start, mobs.get("checkStart") or [])
        _replace_mobs(finish, mobs.get("checkComplete") or [])
    return result


def _npc_names() -> dict[str, str]:
    path = ROOT / "gms-server" / "wz-zh-CN" / "String.wz" / "Npc.img.xml"
    root = ET.parse(path).getroot()
    return {node.get("name", ""): str(_value(node, "name", node.get("name", ""))) for node in root.iter("imgdir") if node.get("name", "").isdigit()}


def _normalize_map_id(raw: str) -> str | None:
    return str(int(raw)) if raw.isdigit() else None


@lru_cache(maxsize=1)
def _map_metadata() -> dict[str, tuple[str, str, str]]:
    result: dict[str, tuple[str, str, str]] = {}
    for base in (ROOT / "gms-server" / "wz" / "String.wz", ROOT / "gms-server" / "wz-zh-CN" / "String.wz"):
        path = base / "Map.img.xml"
        if not path.is_file():
            continue
        root = ET.parse(path).getroot()
        for region_node in root:
            region = region_node.get("name", "unknown")
            for node in region_node.iter("imgdir"):
                map_id = _normalize_map_id(node.get("name", ""))
                if map_id is None:
                    continue
                street = str(_value(node, "streetName", "(未知街道)"))
                map_name = str(_value(node, "mapName", "(未知地图)"))
                result[map_id] = (region, street, map_name)
    return result


def _section_end(data: bytes, start: int) -> int:
    token = re.compile(rb"<imgdir\b|</imgdir>")
    depth = 0
    for match in token.finditer(data, start):
        if match.group(0).startswith(b"<imgdir"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return match.end()
    return len(data)


@lru_cache(maxsize=1)
def _npc_map_ids() -> dict[str, list[str]]:
    candidates: dict[str, list[str]] = {}
    marker = b'<imgdir name="life">'
    entry_pattern = re.compile(rb'<imgdir name="[^"]+">(.*?)</imgdir>', re.S)
    type_pattern = re.compile(rb'<string name="type" value="([^"]*)"')
    id_pattern = re.compile(rb'<string name="id" value="([^"]*)"')
    map_root = ROOT / "gms-server" / "wz" / "Map.wz" / "Map"
    for path in map_root.glob("Map*/*.img.xml"):
        data = path.read_bytes()
        start = data.find(marker)
        if start < 0:
            continue
        map_id = _normalize_map_id(path.name.removesuffix(".img.xml"))
        if map_id is None:
            continue
        section = data[start:_section_end(data, start)]
        for match in entry_pattern.finditer(section):
            body = match.group(1)
            node_type = type_pattern.search(body)
            node_id = id_pattern.search(body)
            if node_type and node_id and node_type.group(1) == b"n":
                candidates.setdefault(node_id.group(1).decode("ascii"), []).append(map_id)
    return {npc: sorted(set(map_ids), key=int) for npc, map_ids in candidates.items()}


@lru_cache(maxsize=1)
def _npc_locations() -> dict[str, tuple[str, str]]:
    metadata = _map_metadata()
    result: dict[str, tuple[str, str]] = {}
    for npc, map_ids in _npc_map_ids().items():
        known = [map_id for map_id in map_ids if map_id in metadata]
        picked = min(known or map_ids, key=int)
        location = metadata.get(picked, ("unknown", "(未知街道)", "(未知地图)"))
        result[npc] = (location[0], location[1])
    return result


@lru_cache(maxsize=1)
def _npc_map_details() -> dict[str, list[dict[str, str]]]:
    metadata = _map_metadata()
    result: dict[str, list[dict[str, str]]] = {}
    for npc, map_ids in _npc_map_ids().items():
        result[npc] = [{
            "id": map_id, "region": location[0], "regionName": REGION_NAMES.get(location[0], location[0]),
            "street": location[1], "name": location[2],
        } for map_id in map_ids for location in [metadata.get(map_id, ("unknown", "(未知街道)", "(未知地图)"))]]
    return result


@lru_cache(maxsize=1)
def _catalog() -> dict[str, Any]:
    roots = _load_roots()
    names = _npc_names()
    locations = _npc_locations()
    quests = []
    npc_counts: dict[str, int] = {}
    region_counts: dict[str, int] = {}
    for info in roots["QuestInfo"]:
        quest_id = info.get("name", "")
        check = _child(roots["Check"], quest_id)
        start_npc = str(_value(_dir(check, "0"), "npc", ""))
        end_npc = str(_value(_dir(check, "1"), "npc", ""))
        area = str(_value(info, "area", "unknown"))
        parent = str(_value(info, "parent", ""))
        order = _value(info, "order")
        region, town = locations.get(start_npc, ("unknown", "(未知街道)"))
        for npc in {start_npc, end_npc} - {""}:
            npc_counts[npc] = npc_counts.get(npc, 0) + 1
        region_counts[region] = region_counts.get(region, 0) + 1
        quests.append({
            "id": quest_id, "name": _value(info, "name", "(未命名任务)"),
            "area": area, "region": region, "town": town, "startNpc": start_npc, "endNpc": end_npc,
            "parent": parent, "order": order,
            "requirements": _quest_requirements(_dir(check, "0")),
            "startNpcName": names.get(start_npc, start_npc), "endNpcName": names.get(end_npc, end_npc),
            "levelMin": _value(_dir(check, "0"), "lvmin"),
        })
    quest_names = {row["id"]: str(row["name"]) for row in quests}
    for row in quests:
        for requirement in row["requirements"]:
            requirement["name"] = quest_names.get(requirement["id"], requirement["id"])
    quests.sort(key=lambda row: int(row["id"]) if row["id"].isdigit() else 0)
    npcs = [{"id": npc, "name": names.get(npc, npc), "count": count} for npc, count in npc_counts.items()]
    npcs.sort(key=lambda row: (-row["count"], row["id"]))
    regions = [{"id": region, "name": REGION_NAMES.get(region, region), "count": count} for region, count in region_counts.items()]
    regions.sort(key=lambda row: (row["id"] == "unknown", row["name"]))
    return {"quests": quests, "npcs": npcs, "regions": regions}


def _script_payload(kind: str, entry_id: str) -> dict[str, Any]:
    if kind not in ("quest", "npc"):
        raise ValueError("脚本类型无效")
    entry_id = _validate_id(entry_id, "脚本 ID")
    result = {"kind": kind, "id": entry_id}
    for locale, root in SCRIPT_ROOTS.items():
        path = root / kind / f"{entry_id}.js"
        result[locale] = {"exists": path.is_file(), "content": path.read_text(encoding="utf-8") if path.is_file() else ""}
    return result


@lru_cache(maxsize=1)
def _item_catalog() -> list[dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for file_name in ("Cash", "Consume", "Eqp", "Etc", "Ins", "Pet"):
        path = ITEM_STRINGS / f"{file_name}.img.xml"
        if not path.is_file():
            continue
        root = ET.parse(path).getroot()
        for node in root.iter("imgdir"):
            item_id = node.get("name", "")
            name = _value(node, "name")
            if item_id.isdigit() and name:
                result[item_id] = {"id": item_id, "name": str(name), "category": file_name}
    return sorted(result.values(), key=lambda item: int(item["id"]))


@lru_cache(maxsize=1)
def _mob_names() -> dict[str, str]:
    path = ITEM_STRINGS / "Mob.img.xml"
    if not path.is_file():
        return {}
    root = ET.parse(path).getroot()
    return {node.get("name", ""): str(_value(node, "name", node.get("name", ""))) for node in root
            if node.get("name", "").isdigit()}


def _database_settings() -> dict[str, Any] | None:
    if not APPLICATION_CONFIG.is_file():
        return None
    content = APPLICATION_CONFIG.read_text(encoding="utf-8")
    url = re.search(r"jdbc:mysql://([^:/\s]+)(?::(\d+))?/([^?\s]+)", content)
    username = re.search(r"(?m)^\s*username:\s*([^#\r\n]+)", content)
    password = re.search(r"(?m)^\s*password:\s*([^#\r\n]*)", content)
    if not url or not username or not password:
        return None

    def scalar(match: re.Match[str], group: int = 1) -> str:
        return match.group(group).strip().strip('"\'')

    return {
        "host": scalar(url), "port": int(url.group(2) or 3306), "database": scalar(url, 3),
        "username": scalar(username), "password": scalar(password),
    }


def _item_drop_audit(item_ids: list[int], quest_id: str) -> dict[str, Any]:
    ids = sorted(set(item_ids))
    result = {str(item_id): {"status": "missing", "drops": []} for item_id in ids}
    if not ids:
        return {"available": True, "reason": "", "items": result}
    settings = _database_settings()
    executable = shutil.which("mysql")
    if settings is None or executable is None:
        return {"available": False, "reason": "未找到 MySQL 配置或客户端", "items": result}
    joined = ",".join(str(item_id) for item_id in ids)
    query = f"""
SELECT 'mob', dropperid, itemid, minimum_quantity, maximum_quantity, questid, chance
FROM drop_data WHERE chance > 0 AND itemid IN ({joined})
UNION ALL
SELECT 'global', continent, itemid, minimum_quantity, maximum_quantity, questid, chance
FROM drop_data_global WHERE chance > 0 AND itemid IN ({joined})
ORDER BY itemid, 1, 2
""".strip()
    environment = os.environ.copy()
    environment["MYSQL_PWD"] = settings["password"]
    command = [
        executable, f"--host={settings['host']}", f"--port={settings['port']}",
        f"--user={settings['username']}", f"--database={settings['database']}",
        "--batch", "--skip-column-names", "--raw", "--connect-timeout=2", "-e", query,
    ]
    try:
        completed = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=5, check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        reason = str(exc.stderr if isinstance(exc, subprocess.CalledProcessError) else exc).strip()
        return {"available": False, "reason": reason or "无法连接 MySQL", "items": result}

    names = _mob_names()
    selected_quest = int(quest_id)

    def runtime_quest_id(raw: int) -> int:
        return raw - 65536 if 32768 <= raw <= 65535 else raw

    for line in completed.stdout.splitlines():
        columns = line.split("\t")
        if len(columns) != 7:
            continue
        source, dropper, raw_item, minimum, maximum, raw_quest, chance = columns
        item_id = str(int(raw_item))
        if item_id not in result:
            continue
        database_quest = int(raw_quest)
        drop_quest = runtime_quest_id(database_quest)
        usable = drop_quest in (0, selected_quest)
        result[item_id]["drops"].append({
            "source": source, "dropperId": dropper,
            "dropperName": (names.get(dropper, dropper) if source == "mob"
                            else ("所有地区怪物" if dropper == "-1" else f"大陆 {dropper} 的怪物")),
            "minimum": int(minimum), "maximum": int(maximum), "questId": drop_quest,
            "databaseQuestId": database_quest,
            "chance": int(chance), "usable": usable,
        })
    for item in result.values():
        if any(drop["usable"] for drop in item["drops"]):
            item["status"] = "available"
        elif item["drops"]:
            item["status"] = "otherQuest"
    return {"available": True, "reason": "", "items": result}


@lru_cache(maxsize=1)
def _equipment_index() -> dict[int, dict[str, Any]]:
    path = EQUIPMENT_CATALOG / "catalog.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {int(item["id"]): {**item, "cellSize": int(data.get("cellSize", 48))} for item in data["items"] if item.get("icon")}


def _item_icon(item_id: int) -> Image.Image | None:
    equipment = _equipment_index().get(item_id)
    if equipment:
        atlas = Image.open(EQUIPMENT_CATALOG / "atlases" / f"{equipment['category']}.png")
        size = equipment["cellSize"]
        return atlas.crop((equipment["x"], equipment["y"], equipment["x"] + size, equipment["y"] + size)).convert("RGBA")
    padded = f"{item_id:08d}"
    first = str(item_id)[0]
    category = {"2": "Consume", "3": "Install", "4": "Etc"}.get(first)
    standalone = ROOT / "clien" / "Data" / "Item" / "Pet" / f"{item_id}.img"
    if first == "5" and standalone.is_file():
        path = standalone
        icon_paths = ("info/icon", "info/iconRaw")
    else:
        if first == "5":
            category = "Cash"
        if not category:
            return None
        path = ROOT / "clien" / "Data" / "Item" / category / f"{padded[:4]}.img"
        icon_paths = (f"{padded}/info/icon", f"{padded}/info/iconRaw")
    if not path.is_file():
        return None
    image = WzImage.from_file(str(path), key=WzKey.for_region("GMS"))
    image.parse()
    canvas = image.root.get(icon_paths[0]) or image.root.get(icon_paths[1])
    return decode_canvas(canvas, region="GMS") if canvas is not None else None


def _npc_preview(npc_id: int) -> Image.Image | None:
    npc_root = ROOT / "clien" / "Data" / "Npc"
    candidates = (npc_root / f"{npc_id}.img", npc_root / f"{npc_id:07d}.img")
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        return None
    image = WzImage.from_file(str(path), key=WzKey.for_region("GMS"))
    image.parse()
    for action in ("stand", "default", "move", "fly", "say"):
        canvas = image.root.get(f"{action}/0")
        if canvas is not None:
            return decode_canvas(canvas, region="GMS")
    return None


def _mob_preview(mob_id: int) -> Image.Image | None:
    mob_root = ROOT / "clien" / "Data" / "Mob"
    candidates = (mob_root / f"{mob_id}.img", mob_root / f"{mob_id:07d}.img")
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        return None
    image = WzImage.from_file(str(path), key=WzKey.for_region("GMS"))
    image.parse()
    for action in ("stand", "move", "fly", "hit1", "die1"):
        canvas = image.root.get(f"{action}/0")
        if canvas is not None:
            return decode_canvas(canvas, region="GMS")
    return None


def _detail(quest_id: str) -> dict[str, Any]:
    nodes = _quest_nodes(quest_id)
    if nodes["QuestInfo"] is None:
        raise KeyError(f"任务不存在: {quest_id}")
    info, check, act, say = (nodes[name] for name in QUEST_FILES)
    start_check, complete_check = _dir(check, "0"), _dir(check, "1")
    start_act, complete_act = _dir(act, "0"), _dir(act, "1")
    start_npc = str(_value(start_check, "npc", ""))
    end_npc = str(_value(complete_check, "npc", ""))
    names = _npc_names()
    npc_maps = _npc_map_details()
    mob_names = _mob_names()
    parent = _value(info, "parent", "")
    location = _npc_locations().get(start_npc, ("unknown", "(未知街道)"))
    catalog = _catalog()
    quest_names = {row["id"]: str(row["name"]) for row in catalog["quests"]}
    requirements = _quest_requirements(start_check, quest_names)
    chain = []
    if parent:
        chain = [{"id": row["id"], "name": row["name"], "order": row["order"], "town": row["town"],
                  "requirements": row["requirements"]}
                 for row in catalog["quests"] if row["parent"] == parent]
        chain.sort(key=lambda row: (row["order"] is None, row["order"] if row["order"] is not None else 0,
                                    int(row["id"]) if row["id"].lstrip("-").isdigit() else 0))
    return {
        "questId": quest_id, "name": _value(info, "name", ""), "area": _value(info, "area"),
        "contentStart": _value(info, "0", ""), "contentProgress": _value(info, "1", ""),
        "contentComplete": _value(info, "2", ""), "parent": parent,
        "order": _value(info, "order"), "startNpc": start_npc, "endNpc": end_npc,
        "startNpcName": names.get(start_npc, start_npc), "endNpcName": names.get(end_npc, end_npc),
        "startNpcMaps": npc_maps.get(start_npc, []), "endNpcMaps": npc_maps.get(end_npc, []),
        "region": location[0], "regionName": REGION_NAMES.get(location[0], location[0]), "town": location[1],
        "chain": chain, "requirements": requirements,
        "levelMin": _value(start_check, "lvmin"), "levelMax": _value(start_check, "lvmax"),
        "rewardExp": _value(complete_act, "exp"), "rewardMeso": _value(complete_act, "money"),
        "nextQuest": _value(complete_act, "nextQuest"),
        "dialogStart": _value(_dir(say, "0"), "0", ""), "dialogComplete": _value(_dir(say, "1"), "0", ""),
        "items": {"checkStart": _item_rows(start_check), "checkComplete": _item_rows(complete_check),
                  "actStart": _item_rows(start_act), "actComplete": _item_rows(complete_act)},
        "mobs": {"checkStart": _mob_rows(start_check, mob_names),
                 "checkComplete": _mob_rows(complete_check, mob_names)},
        "raw": {name: _node_fragment(nodes[name]) for name in QUEST_FILES},
        "questScript": _script_payload("quest", quest_id),
        "npcScripts": [_script_payload("npc", npc) for npc in dict.fromkeys((start_npc, end_npc)) if npc],
    }


def _ok(**payload):
    return jsonify({"ok": True, **payload})


@app.errorhandler(Exception)
def _error(exc: Exception):
    status = 404 if isinstance(exc, KeyError) else 400
    return jsonify({"ok": False, "reason": str(exc).strip("'")}), status


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/catalog")
def catalog():
    data = _catalog()
    query = request.args.get("q", "").strip().lower()
    region = request.args.get("region", "").strip()
    npc = request.args.get("npc", "").strip()
    rows = [row for row in data["quests"] if (not region or row["region"] == region)
            and (not npc or npc in (row["startNpc"], row["endNpc"]))
            and (not query or query in row["id"] or query in str(row["name"]).lower())]
    return _ok(quests=rows[:1000], regions=data["regions"], npcs=data["npcs"], total=len(rows))


@app.get("/api/quest/<quest_id>")
def detail(quest_id: str):
    return _ok(quest=_detail(_validate_id(quest_id, "任务 ID")))


@app.post("/api/quest/save")
def save_quest():
    body = request.get_json(silent=True) or {}
    quest_id = _validate_id(body.get("questId"), "任务 ID")
    with _WRITE_LOCK:
        nodes = _quest_nodes(quest_id)
        if nodes["QuestInfo"] is None:
            raise KeyError(f"任务不存在: {quest_id}")
        updated = _basic_payload(nodes, body)
        _commit(_validated_payloads(quest_id, updated))
        _catalog.cache_clear()
    return _ok(quest=_detail(quest_id))


@app.post("/api/quest/raw")
def save_raw():
    body = request.get_json(silent=True) or {}
    quest_id = _validate_id(body.get("questId"), "任务 ID")
    raw = body.get("raw") or {}
    nodes = {name: _parse_fragment(str(raw.get(name, "")), quest_id) for name in QUEST_FILES}
    with _WRITE_LOCK:
        _commit(_validated_payloads(quest_id, nodes))
        _catalog.cache_clear()
    return _ok(quest=_detail(quest_id))


@app.post("/api/quest/create")
def create_quest():
    body = request.get_json(silent=True) or {}
    quest_id = _validate_id(body.get("questId"), "任务 ID")
    with _WRITE_LOCK:
        nodes = _quest_nodes(quest_id)
        if nodes["QuestInfo"] is not None:
            raise ValueError(f"任务已存在: {quest_id}")
        created = _basic_payload(nodes, body)
        _commit(_validated_payloads(quest_id, created))
        _catalog.cache_clear()
    return _ok(quest=_detail(quest_id))


@app.post("/api/quest/delete")
def delete_quest():
    body = request.get_json(silent=True) or {}
    quest_id = _validate_id(body.get("questId"), "任务 ID")
    if body.get("confirm") != quest_id:
        raise ValueError("删除确认必须填写任务 ID")
    with _WRITE_LOCK:
        _commit(_validated_payloads(quest_id, {name: None for name in QUEST_FILES}))
        _catalog.cache_clear()
    return _ok(deleted=quest_id)


@app.post("/api/script")
def save_script():
    body = request.get_json(silent=True) or {}
    kind = str(body.get("kind", "quest"))
    entry_id = _validate_id(body.get("id"), "脚本 ID")
    locale = str(body.get("locale", "main"))
    if locale not in SCRIPT_ROOTS or kind not in ("quest", "npc"):
        raise ValueError("脚本范围无效")
    path = SCRIPT_ROOTS[locale] / kind / f"{entry_id}.js"
    with _WRITE_LOCK:
        backup = BACKUP_ROOT / ("__".join(path.relative_to(ROOT).parts) + ".bak")
        if path.exists() and not backup.exists():
            BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
        if body.get("delete"):
            if body.get("confirm") != entry_id:
                raise ValueError("删除脚本必须确认脚本 ID")
            path.unlink(missing_ok=True)
        else:
            content = str(body.get("content", ""))
            if len(content.encode("utf-8")) > 1024 * 1024:
                raise ValueError("脚本不能超过 1 MiB")
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.tmp")
            temporary.write_text(content, encoding="utf-8")
            os.replace(temporary, path)
    return _ok(script=_script_payload(kind, entry_id))


@app.get("/api/items")
def items():
    query = request.args.get("q", "").strip().lower()
    category = request.args.get("category", "").strip()
    rows = [item for item in _item_catalog() if (not category or item["category"] == category)
            and (not query or query in item["id"] or query in item["name"].lower())]
    return _ok(items=rows[:120], total=len(rows))


@app.get("/api/mobs")
def mobs():
    query = request.args.get("q", "").strip().lower()
    rows = [{"id": mob_id, "name": name} for mob_id, name in _mob_names().items()
            if not query or query in mob_id or query in name.lower()]
    rows.sort(key=lambda row: int(row["id"]))
    return _ok(mobs=rows[:120], total=len(rows))


@app.get("/api/item-drops")
def item_drops():
    quest_id = _validate_id(request.args.get("questId"), "任务 ID")
    raw_ids = [value.strip() for value in request.args.get("ids", "").split(",") if value.strip()]
    if len(raw_ids) > 100 or any(not re.fullmatch(r"\d{1,9}", value) for value in raw_ids):
        raise ValueError("物品 ID 列表无效或超过 100 个")
    return _ok(dropAudit=_item_drop_audit([int(value) for value in raw_ids], quest_id))


@app.get("/api/item/<int:item_id>/icon")
def item_icon(item_id: int):
    image = _item_icon(item_id)
    if image is None:
        return "", 404
    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return send_file(output, mimetype="image/png", max_age=3600)


@app.get("/api/npc/<int:npc_id>/preview")
def npc_preview(npc_id: int):
    image = _npc_preview(npc_id)
    if image is None:
        return "", 404
    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return send_file(output, mimetype="image/png", max_age=3600)


@app.get("/api/mob/<int:mob_id>/preview")
def mob_preview(mob_id: int):
    image = _mob_preview(mob_id)
    if image is None:
        return "", 404
    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return send_file(output, mimetype="image/png", max_age=3600)
