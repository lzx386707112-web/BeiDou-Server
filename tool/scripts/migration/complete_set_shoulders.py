#!/usr/bin/env python3
"""Complete the reviewed set shoulders without rewriting existing equipment IMGs."""

from __future__ import annotations

import hashlib
import io
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

import migrate_arcane_river_expansion as arc

from wzpy import WzCanvasProperty, WzIntProperty, WzStringProperty, WzSubProperty
from wzpy.canvas import decode_canvas
from wzpy.writer import encode_image_body


ROOT = arc.ROOT
NAMES = {
    1152060: "冒险岛宝石肩膀", 1152061: "冒险岛铂金肩膀",
    1152118: "斯泰拉肩章", 1152187: "冒险岛寻宝肩章",
    1152068: "传说冒险岛护肩", 1152089: "专属紫金枫叶肩章",
    1152099: "风暴肩章", 1152119: "终极肩章",
    1152110: "龙尾法师护肩", 1152111: "鹰翼哨兵护肩",
    1152112: "渡鸦之魂猎人护肩", 1152113: "鲨齿船长护肩",
    1152094: "天照的肩章", 1152096: "天钿女命的肩章",
    1152095: "大山祇神的肩章", 1152097: "月夜见尊的肩章",
    1152098: "素盏呜尊的肩章",
    1152196: "神秘之影战士护肩", 1152197: "神秘之影法师护肩",
    1152198: "神秘之影弓箭手护肩", 1152199: "神秘之影飞侠护肩",
    1152200: "神秘之影海盗护肩",
}
NEW_IDS = set(range(1152196, 1152201))
STRING_PARENT = ("Eqp", "Accessory")
STRING_ANCHOR = "1152212"
STRINGS = [ROOT / "gms-server" / tree / "String.wz/Eqp.img.xml"
           for tree in ("wz", "wz-zh-CN")]
CATALOG_ROOT = ROOT / "gms-server/src/main/resources/equipment-catalog"


def load(data: bytes, name: str):
    from wzpy import WzImage
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"invalid {name}: {image.truncated}, {image.parse_warnings}")
    return image


def source(item_id: int):
    path = arc.SOURCE / "Character/Accessory" / f"{item_id:08d}.img"
    image = arc.load_image(path, arc.BMS_KEY)
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"invalid TMS source {path}")
    return path, image


def build_equipment(item_id: int) -> tuple[bytes, str]:
    path, image = source(item_id)
    materializer = arc.CanvasMaterializer()
    # These are the fields already used by the working 1152108 legacy shoulder.
    analogue = load((ROOT / "clien/Data/Character/Accessory/01152108.img").read_bytes(), "01152108.img")
    allowed = {node.name for node in analogue.root.child("info").children()}
    info = WzSubProperty("info")
    for node in image.root.child("info").children():
        if node.name in allowed:
            info.add(arc.clone_property(node, info, image, path, materializer))
    root = WzSubProperty(image.root.name)
    root.add(info)
    image._root = root
    image._parsed = True
    data = encode_image_body(image, arc.gms_reader())  # New standalone IMG only.
    parsed = load(data, path.name)
    if [node.name for node in parsed.root.children()] != ["info"]:
        raise RuntimeError("unexpected equipment roots")
    for icon_name in ("icon", "iconRaw"):
        icon = parsed.root.get(f"info/{icon_name}")
        if not isinstance(icon, WzCanvasProperty) or (icon.format, icon.format2) != (1, 0):
            raise RuntimeError(f"incompatible icon {item_id}/{icon_name}")
        bitmap = decode_canvas(icon, region="GMS")
        if min(bitmap.size) <= 1 or not bitmap.getbbox():
            raise RuntimeError(f"blank icon {item_id}/{icon_name}")
    xml = arc.image_to_xml(parsed, path.name)
    ET.fromstring(xml)
    return data, xml


def record(item_id: int):
    node = WzSubProperty(str(item_id))
    node.add(WzStringProperty("name", NAMES[item_id], node))
    return node


def stage_strings() -> dict[Path, bytes]:
    path = ROOT / "clien/Data/String/Eqp.img"
    before = path.read_bytes()
    image = load(before, path.name)
    after = before
    additions = set()
    for item_id, name in NAMES.items():
        node = image.root.get("/".join((*STRING_PARENT, str(item_id))))
        if node is not None:
            if getattr(node.child("name"), "value", None) != name:
                raise RuntimeError(f"conflicting client String {item_id}")
            continue
        after = arc.insert_property_record_before(after, STRING_PARENT, record(item_id), STRING_ANCHOR)
        additions.add((*STRING_PARENT, str(item_id)))
    if additions:
        arc.verify_raw_record_insert_scope(before, after, additions)
    load(after, path.name)
    staged = {path: after}
    for xml_path in STRINGS:
        text = xml_path.read_text(encoding="utf-8")
        root = ET.fromstring(text)
        parent = root.find('./imgdir[@name="Eqp"]/imgdir[@name="Accessory"]')
        if parent is None:
            raise RuntimeError(f"missing String parent {xml_path}")
        missing = []
        for item_id, name in NAMES.items():
            existing = parent.find(f'./imgdir[@name="{item_id}"]')
            if existing is None:
                missing.append(record(item_id))
            elif existing.find('./string[@name="name"]').get("value") != name:
                raise RuntimeError(f"conflicting server String {xml_path}/{item_id}")
        if missing:
            text = arc.insert_xml_properties_before(text, STRING_PARENT, missing, STRING_ANCHOR)
        ET.fromstring(text)
        staged[xml_path] = text.encode("utf-8")
    print(f"String: {len(additions)} additions; protected raw records and order unchanged")
    return staged


def stage_catalog(equipment: dict[int, bytes]) -> dict[Path, bytes]:
    path = CATALOG_ROOT / "catalog.json"
    before = json.loads(path.read_text(encoding="utf-8"))
    by_id = {entry["id"]: entry for entry in before["items"]}
    missing = [item_id for item_id in NAMES if item_id not in by_id]
    for item_id in NAMES:
        if item_id in by_id and by_id[item_id]["name"] != NAMES[item_id]:
            raise RuntimeError(f"conflicting catalog name {item_id}")
    if not missing:
        return {path: path.read_bytes()}
    atlas_path = CATALOG_ROOT / "atlases/Accessory.png"
    old = Image.open(atlas_path).convert("RGBA")
    size = before["cellSize"]
    columns = old.width // size
    rows = (len(missing) + columns - 1) // columns
    atlas = Image.new("RGBA", (old.width, old.height + rows * size))
    atlas.paste(old, (0, 0))
    for index, item_id in enumerate(missing):
        image = load(equipment[item_id], f"{item_id:08d}.img")
        info = image.root.child("info")
        icon = decode_canvas(info.child("icon"), region="GMS").convert("RGBA")
        if not icon.getbbox() or max(icon.size) > size:
            raise RuntimeError(f"invalid catalog icon {item_id}")
        x, y = index % columns * size, old.height + index // columns * size
        atlas.paste(icon, (x + (size - icon.width) // 2, y + (size - icon.height) // 2))
        stats = {node.name: int(node.value) for node in info.children()
                 if isinstance(node, WzIntProperty)}
        before["items"].append({"id": item_id, "name": NAMES[item_id], "desc": "",
                                "category": "Accessory", "stats": stats, "icon": True, "x": x, "y": y})
    meta = before["atlases"]["Accessory"]
    meta["count"] += len(missing)
    meta["icons"] += len(missing)
    meta["height"] = atlas.height
    if atlas.crop((0, 0, old.width, old.height)).tobytes() != old.tobytes():
        raise RuntimeError("existing atlas pixels changed")
    buffer = io.BytesIO()
    atlas.save(buffer, format="PNG")
    print(f"Catalog: {len(missing)} additions; existing entries and atlas pixels unchanged")
    return {path: json.dumps(before, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            atlas_path: buffer.getvalue()}


def main():
    staged = {}
    equipment = {}
    for item_id in NAMES:
        path, tms = source(item_id)
        client = ROOT / "clien/Data/Character/Accessory" / path.name
        server = ROOT / "gms-server/wz/Character.wz/Accessory" / (path.name + ".xml")
        if item_id in NEW_IDS:
            data, xml = build_equipment(item_id)
            for target, payload in ((client, data), (server, xml.encode("utf-8"))):
                if target.exists() and target.read_bytes() != payload:
                    raise RuntimeError(f"refusing to replace existing equipment {target}")
                staged[target] = payload
            equipment[item_id] = data
        else:
            equipment[item_id] = client.read_bytes()
            local = load(equipment[item_id], client.name)
            if local.root.get("info/setItemID").value != tms.root.get("info/setItemID").value:
                raise RuntimeError(f"set identity mismatch {item_id}")
            ET.parse(server)
    staged.update(stage_strings())
    staged.update(stage_catalog(equipment))
    for path, data in staged.items():
        if not path.exists() or path.read_bytes() != data:
            arc.atomic_write_bytes(path, data)
    print("Verified 22 TMS identities; created 5 standalone GMS shoulder IMGs and XMLs")
    for path, data in staged.items():
        print(hashlib.sha256(data).hexdigest(), path.relative_to(ROOT))


if __name__ == "__main__":
    main()
