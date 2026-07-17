#!/usr/bin/env python3
"""Replace the fashion-shop weapon set with selected cash weapons."""

from __future__ import annotations

import io
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import quoteattr


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.properties import (  # noqa: E402
    WzCanvasProperty,
    WzConvexProperty,
    WzDoubleProperty,
    WzFloatProperty,
    WzIntProperty,
    WzLongProperty,
    WzNullProperty,
    WzShortProperty,
    WzSoundProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


SOURCE = Path("/Users/lizixian/Downloads/自用商城整理/商城整理")
SHEN_SOURCE = Path("/Users/lizixian/Documents/mxd/神说/Data")
BACKUP = Path("/Users/lizixian/Downloads/整合")
CLIENT_WEAPON = ROOT / "clien/Data/Character/Weapon"
SERVER_WEAPON = ROOT / "gms-server/wz/Character.wz/Weapon"
CLIENT_EQP = ROOT / "clien/Data/String/Eqp.img"
SERVER_EQPS = [
    ROOT / "gms-server/wz/String.wz/Eqp.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Eqp.img.xml",
]
SHOP_SCRIPT = ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/时尚点装.js"
KEY = WzKey.for_region("GMS")
SHEN_KEY = WzKey.for_region("EMS")

NEW_IDS = [
    1702974, 1702987, 1703011, 1703014, 1703024, 1703027, 1703032, 1703042,
    1703067, 1703076, 1703077, 1703089, 1703091, 1703093, 1703102, 1703138,
    1703139, 1703147, 1703164, 1703171, 1703177, 1703185, 1703193, 1703204,
    1703229, 1703240, 1703243, 1703253, 1703255, 1703259, 1703304, 1703311,
    1703326, 1703398, 1703402, 1703451, 1703473, 1703504, 1703520, 1703565,
    1703578, 1703580, 1703582, 1703620, 1703650, 1703668, 1703683, 1703753,
    1703816, 1703852, 1702825, 1703178, 1703373,
]
SHEN_IDS = {1702825, 1703178, 1703373}


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(data)
        temp = Path(handle.name)
    temp.replace(path)


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), KEY)


def source_client(item_id: int) -> Path:
    if item_id in SHEN_IDS:
        return SHEN_SOURCE / f"Character/Weapon/{item_id:08d}.img"
    return SOURCE / f"客户端/Data/Character/Weapon/{item_id:08d}.img"


def source_server_eqp() -> Path:
    return SOURCE / "服务端/wz/String.wz/Eqp.img.xml"


def strip_canvas_outlinks(node) -> tuple[int, int]:
    removed = 0
    missing_pixels = 0
    if isinstance(node, WzCanvasProperty):
        outlink = node.child("_outlink")
        if isinstance(outlink, WzStringProperty):
            if node.has_pixels():
                del node._children["_outlink"]
                removed += 1
            else:
                missing_pixels += 1
    if hasattr(node, "children"):
        for child in node.children():
            child_removed, child_missing = strip_canvas_outlinks(child)
            removed += child_removed
            missing_pixels += child_missing
    return removed, missing_pixels


def compatible_image(item_id: int) -> WzImage:
    path = source_client(item_id)
    source_key = SHEN_KEY if item_id in SHEN_IDS else KEY
    image = WzImage.from_bytes(path.read_bytes(), key=source_key, name=path.name)
    _, missing_pixels = strip_canvas_outlinks(image.parse())
    if missing_pixels:
        raise RuntimeError(f"{path.name}: {missing_pixels} canvas outlinks have no embedded pixels")
    return image


def property_to_xml(prop, indent: int = 1) -> str:
    pad = "  " * indent
    name = f"name={quoteattr(prop.name)}"
    if isinstance(prop, WzNullProperty):
        return f"{pad}<null {name}/>"
    if isinstance(prop, WzShortProperty):
        return f'{pad}<short {name} value="{int(prop.value)}"/>'
    if isinstance(prop, WzIntProperty):
        return f'{pad}<int {name} value="{int(prop.value)}"/>'
    if isinstance(prop, WzLongProperty):
        return f'{pad}<long {name} value="{int(prop.value)}"/>'
    if isinstance(prop, WzFloatProperty):
        return f'{pad}<float {name} value="{float(prop.value)}"/>'
    if isinstance(prop, WzDoubleProperty):
        return f'{pad}<double {name} value="{float(prop.value)}"/>'
    if isinstance(prop, WzStringProperty):
        return f"{pad}<string {name} value={quoteattr(str(prop.value))}/>"
    if isinstance(prop, WzUolProperty):
        return f"{pad}<uol {name} value={quoteattr(str(prop.value))}/>"
    if isinstance(prop, WzVectorProperty):
        return f'{pad}<vector {name} x="{int(prop.x)}" y="{int(prop.y)}"/>'
    if isinstance(prop, WzConvexProperty):
        body = "\n".join(property_to_xml(child, indent + 1) for child in prop.children())
        return f"{pad}<extended {name}>\n{body}\n{pad}</extended>"
    if isinstance(prop, WzSoundProperty):
        return f'{pad}<sound {name} length_ms="{int(prop.length_ms)}" bytes="{int(prop.value)}"/>'
    if isinstance(prop, WzCanvasProperty):
        attrs = f'{name} width="{int(prop.width)}" height="{int(prop.height)}"'
        children = prop.children()
        if not children:
            return f"{pad}<canvas {attrs}/>"
        body = "\n".join(property_to_xml(child, indent + 1) for child in children)
        return f"{pad}<canvas {attrs}>\n{body}\n{pad}</canvas>"
    if isinstance(prop, WzSubProperty):
        children = prop.children()
        if not children:
            return f"{pad}<imgdir {name}/>"
        body = "\n".join(property_to_xml(child, indent + 1) for child in children)
        return f"{pad}<imgdir {name}>\n{body}\n{pad}</imgdir>"
    raise TypeError(f"unsupported WZ node: {type(prop).__name__}")


def image_xml(image: WzImage) -> bytes:
    body = "\n".join(property_to_xml(child) for child in image.parse().children())
    text = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<imgdir name="{image.name}">\n{body}\n</imgdir>\n'
    )
    return text.encode("utf-8")


def direct_child(parent: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in parent if child.get("name") == name), None)


def source_names() -> dict[int, list[tuple[str, str]]]:
    root = ET.parse(source_server_eqp()).getroot()
    eqp = direct_child(root, "Eqp")
    weapon = direct_child(eqp, "Weapon") if eqp is not None else None
    if weapon is None:
        raise RuntimeError("source String.wz is missing Eqp/Weapon")
    result = {}
    for item_id in NEW_IDS:
        if item_id in SHEN_IDS:
            continue
        node = direct_child(weapon, str(item_id))
        if node is None:
            raise RuntimeError(f"source String.wz is missing weapon {item_id}")
        result[item_id] = [(child.get("name", ""), child.get("value", "")) for child in node]
    shen_eqp_path = SHEN_SOURCE / "String/Eqp.img"
    shen_eqp = WzImage.from_bytes(shen_eqp_path.read_bytes(), key=SHEN_KEY, name=shen_eqp_path.name)
    shen_weapon = shen_eqp.parse().get("Eqp/Weapon")
    if not isinstance(shen_weapon, WzSubProperty):
        raise RuntimeError("Shen String/Eqp.img is missing Eqp/Weapon")
    for item_id in SHEN_IDS:
        node = shen_weapon.child(str(item_id))
        if isinstance(node, WzSubProperty):
            result[item_id] = [(child.name, str(child.value)) for child in node.children() if isinstance(child, WzStringProperty)]
            continue
        fallback = direct_child(weapon, str(item_id))
        if fallback is None:
            raise RuntimeError(f"no String.wz name entry found for Shen weapon {item_id}")
        result[item_id] = [(child.get("name", ""), child.get("value", "")) for child in fallback]
    return result


def old_ids_from_shop() -> list[int]:
    text = SHOP_SCRIPT.read_text(encoding="utf-8")
    match = re.search(r"var wq = Array\((.*?)\n\);", text, re.S)
    if not match:
        raise RuntimeError("fashion shop weapon array was not found")
    return [int(value) for value in re.findall(r"Array\((\d+),\s*6000\)", match.group(1))]


def patch_shop() -> None:
    text = SHOP_SCRIPT.read_text(encoding="utf-8")
    rows = [f"Array({item_id},6000)" for item_id in NEW_IDS]
    rows[0] += ",                     //武器（物品代码，价格）"
    for index in range(1, len(rows) - 1):
        rows[index] += ","
    block = "var wq = Array(\n" + "\n".join(rows) + "\n);"
    updated, count = re.subn(r"var wq = Array\(.*?\n\);", block, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("fashion shop weapon array replacement failed")
    atomic_write(SHOP_SCRIPT, updated.encode("utf-8"))


def patch_server_strings(path: Path, old_ids: set[int], names: dict[int, list[tuple[str, str]]]) -> None:
    original = path.read_text(encoding="utf-8")
    compact_empty_tags = original.count("/>") > original.count(" />") * 2
    tree = ET.parse(path)
    root = tree.getroot()
    eqp = direct_child(root, "Eqp")
    weapon = direct_child(eqp, "Weapon") if eqp is not None else None
    if weapon is None:
        raise RuntimeError(f"{path}: missing Eqp/Weapon")
    for node in list(weapon):
        if node.get("name", "").isdigit() and int(node.get("name")) in old_ids | set(NEW_IDS):
            weapon.remove(node)
    for item_id in NEW_IDS:
        node = ET.SubElement(weapon, "imgdir", {"name": str(item_id)})
        for key, value in names[item_id]:
            ET.SubElement(node, "string", {"name": key, "value": value})
    ET.indent(tree, space="  ")
    data = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    data += ET.tostring(root, encoding="unicode") + "\n"
    if compact_empty_tags:
        data = data.replace(" />", "/>")
    atomic_write(path, data.encode("utf-8"))


def patch_client_strings(old_ids: set[int], names: dict[int, list[tuple[str, str]]]) -> None:
    image = WzImage.from_bytes(CLIENT_EQP.read_bytes(), key=KEY, name=CLIENT_EQP.name)
    weapon = image.parse().get("Eqp/Weapon")
    if not isinstance(weapon, WzSubProperty):
        raise RuntimeError("client String/Eqp.img is missing Eqp/Weapon")
    for child in list(weapon.children()):
        if child.name.isdigit() and int(child.name) in old_ids | set(NEW_IDS):
            del weapon._children[child.name]
    for item_id in NEW_IDS:
        node = WzSubProperty(str(item_id), weapon)
        for key, value in names[item_id]:
            node.add(WzStringProperty(key, value, node))
        weapon.add(node)
    atomic_write(CLIENT_EQP, encode_image_body(image, gms_reader()))


def copy_backup() -> None:
    BACKUP.mkdir(parents=True, exist_ok=True)
    paths = [CLIENT_EQP, SHOP_SCRIPT, *SERVER_EQPS]
    paths += [CLIENT_WEAPON / f"{item_id:08d}.img" for item_id in NEW_IDS]
    paths += [SERVER_WEAPON / f"{item_id:08d}.img.xml" for item_id in NEW_IDS]
    for path in paths:
        destination = BACKUP / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def verify(old_ids: set[int]) -> None:
    shop_ids = old_ids_from_shop()
    if shop_ids != NEW_IDS:
        raise RuntimeError("fashion shop IDs do not match requested order")
    for item_id in NEW_IDS:
        client = CLIENT_WEAPON / f"{item_id:08d}.img"
        server = SERVER_WEAPON / f"{item_id:08d}.img.xml"
        if not client.is_file() or not server.is_file():
            raise RuntimeError(f"missing migrated weapon {item_id}")
        written = WzImage.from_bytes(client.read_bytes(), key=KEY, name=client.name)
        written.parse()
        ET.parse(server)
    stale = [item_id for item_id in old_ids - set(NEW_IDS) if (CLIENT_WEAPON / f"{item_id:08d}.img").exists() or (SERVER_WEAPON / f"{item_id:08d}.img.xml").exists()]
    if stale:
        raise RuntimeError(f"old fashion weapon files remain: {stale}")
    expected_backup_files = len(NEW_IDS) * 2 + 4
    if sum(1 for path in BACKUP.rglob("*") if path.is_file()) != expected_backup_files:
        raise RuntimeError(f"integration backup file count is not {expected_backup_files}")


def main() -> int:
    old_ids = set(old_ids_from_shop())
    names = source_names()
    images = {item_id: compatible_image(item_id) for item_id in NEW_IDS}

    for item_id in old_ids - set(NEW_IDS):
        (CLIENT_WEAPON / f"{item_id:08d}.img").unlink(missing_ok=True)
        (SERVER_WEAPON / f"{item_id:08d}.img.xml").unlink(missing_ok=True)
    for item_id, image in images.items():
        atomic_write(CLIENT_WEAPON / f"{item_id:08d}.img", encode_image_body(image, gms_reader()))
        atomic_write(SERVER_WEAPON / f"{item_id:08d}.img.xml", image_xml(image))

    patch_shop()
    patch_client_strings(old_ids, names)
    for path in SERVER_EQPS:
        patch_server_strings(path, old_ids, names)
    copy_backup()
    verify(old_ids)
    print(f"replaced {len(old_ids)} old weapons with {len(NEW_IDS)} requested weapons")
    print(f"integration backup: {BACKUP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
