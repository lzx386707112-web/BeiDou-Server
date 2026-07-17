#!/usr/bin/env python3
"""Migrate a Boss-only three-stage Lucid chain from 神说 into BeiDou."""

from __future__ import annotations

import io
import re
import struct
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import quoteattr


ROOT = Path(__file__).resolve().parents[3]
SRC = Path("/Users/lizixian/Documents/mxd/神说/Data")
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzConvexProperty,
    WzDoubleProperty,
    WzFloatProperty,
    WzImage,
    WzIntProperty,
    WzKey,
    WzLongProperty,
    WzNullProperty,
    WzShortProperty,
    WzSoundProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import (  # noqa: E402
    _encode_property_body,
    _tag_for,
    encode_compressed_int,
    encode_image_body,
    encode_string_block,
)


SOURCE_REGION = "EMS"
TARGET_KEY = WzKey.for_region("GMS")
MAIN_IDS = (8880140, 8880141, 8880142)
SUPPORT_IDS = (8880161, 8880165, 8880171, 8880175)
LUCID_IDS = MAIN_IDS + SUPPORT_IDS
SERVER_STAGE_HP = 5_000_000_000
CLIENT_STAGE_HP = 2_000_000_000
SUPPORTED_SKILLS = {
    8880140: ((145, 2, 2), (128, 16, 3), (131, 13, 4)),
    8880141: ((145, 5, 1), (145, 2, 2), (128, 16, 3), (125, 9, 4)),
    8880142: ((145, 2, 1), (126, 2, 2), (128, 10, 3)),
}
LUCID_NAMES = {
    8880140: "梦中的路西德",
    8880141: "梦中的路西德",
    8880142: "梦中的路西德",
    8880161: "噩梦石人",
    8880165: "噩梦蝴蝶",
    8880171: "噩梦石人",
    8880175: "噩梦蝴蝶",
}


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def atomic_write_text(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), TARGET_KEY)


def source_img(path: Path) -> WzImage:
    img = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region(SOURCE_REGION), name=path.name)
    img.parse()
    return img


def client_img(path: Path) -> WzImage:
    img = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=path.name)
    img.parse()
    return img


def replace_child(parent: WzSubProperty, node) -> None:
    node.parent = parent
    parent._children[node.name] = node


def remove_child(parent: WzSubProperty, name: str) -> None:
    parent._children.pop(name, None)


def set_int(parent: WzSubProperty, name: str, value: int) -> None:
    node = parent.child(name)
    if node is None:
        parent.add(WzIntProperty(name, value, parent))
    elif isinstance(node, WzIntProperty):
        node._value = value
    else:
        replace_child(parent, WzIntProperty(name, value, parent))


def set_string(parent: WzSubProperty, name: str, value: str) -> None:
    replace_child(parent, WzStringProperty(name, value, parent))


def set_revive(info: WzSubProperty, target: int | None) -> None:
    if target is None:
        remove_child(info, "revive")
        return
    revive = WzSubProperty("revive", info)
    revive.add(WzIntProperty("0", target, revive))
    replace_child(info, revive)


def set_skills(root: WzSubProperty, mob_id: int) -> None:
    info = root.child("info")
    if info is None:
        raise ValueError(f"{mob_id}: missing info")
    remove_child(info, "skill")
    skills = SUPPORTED_SKILLS.get(mob_id)
    if not skills:
        return
    skill_root = WzSubProperty("skill", info)
    for index, (skill_id, level, action) in enumerate(skills):
        ensure_action(root, action)
        entry = WzSubProperty(str(index), skill_root)
        entry.add(WzIntProperty("skill", skill_id, entry))
        entry.add(WzIntProperty("level", level, entry))
        entry.add(WzIntProperty("action", action, entry))
        skill_root.add(entry)
    replace_child(info, skill_root)


def ensure_action(root: WzSubProperty, action: int) -> None:
    target_name = f"skill{action}"
    if root.child(target_name) is not None:
        return
    for source_name in (f"attack{action}", "skill2", "attack2", "skill1", "attack1", "stand", "fly"):
        source = root.child(source_name)
        if source is not None:
            replace_child(root, clone_property(source, target_name, root))
            return
    raise ValueError(f"{root.name}: cannot build {target_name}")


def sanitize_lucid_root(root: WzSubProperty, mob_id: int, server: bool) -> None:
    info = root.child("info")
    if info is None:
        raise ValueError(f"{mob_id}: missing info")
    if mob_id in MAIN_IDS:
        if server:
            set_string(info, "maxHP", str(SERVER_STAGE_HP))
        else:
            set_int(info, "maxHP", CLIENT_STAGE_HP)
        set_revive(info, {8880140: 8880141, 8880141: 8880142}.get(mob_id))
        set_int(info, "PDRate", 50)
        set_int(info, "MDRate", 50)
    set_skills(root, mob_id)


def patch_client_ui() -> None:
    path = ROOT / "clien/Data/UI/UIWindow.img"
    image = client_img(path)
    mob_gauge = image.root.get("MobGage/Mob")
    if mob_gauge is None:
        raise ValueError("UIWindow.img: missing MobGage/Mob")

    if mob_gauge.child("8880140") is None:
        raise ValueError("UIWindow.img: missing Lucid phase 1 icon")
    mob_gauge._children["8880141"] = WzUolProperty("8880141", "8880140", mob_gauge)
    mob_gauge._children["8880142"] = WzUolProperty("8880142", "8880140", mob_gauge)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))


def reencode_canvas_tree(prop) -> None:
    if isinstance(prop, WzCanvasProperty) and prop.has_pixels():
        image = decode_canvas(prop, region=SOURCE_REGION)
        prop.format = 1
        prop.format2 = 0
        prop._png_data = encode_canvas_payload(
            image,
            1,
            int(prop.width),
            int(prop.height),
            key=TARGET_KEY,
            listwz=False,
        )
        prop._png_length = len(prop._png_data)
    if hasattr(prop, "children"):
        for child in prop.children():
            reencode_canvas_tree(child)


def clone_property(prop, name: str | None = None, parent=None):
    new_name = prop.name if name is None else name
    if isinstance(prop, WzCanvasProperty):
        out = WzCanvasProperty(new_name, parent)
        out.width = prop.width
        out.height = prop.height
        out.format = prop.format
        out.format2 = prop.format2
        if prop.has_pixels():
            image = decode_canvas(prop, region=SOURCE_REGION)
            out._png_data = encode_canvas_payload(
                image,
                1,
                int(prop.width),
                int(prop.height),
                key=TARGET_KEY,
                listwz=False,
            )
            out._png_length = len(out._png_data)
        out.format = 1
        out.format2 = 0
        for child in prop.children():
            out.add(clone_property(child, parent=out))
        return out
    if isinstance(prop, WzVectorProperty):
        return WzVectorProperty(new_name, prop.x, prop.y, parent)
    if isinstance(prop, WzIntProperty):
        return WzIntProperty(new_name, int(prop.value), parent)
    if isinstance(prop, WzShortProperty):
        return WzShortProperty(new_name, int(prop.value), parent)
    if isinstance(prop, WzLongProperty):
        return WzLongProperty(new_name, int(prop.value), parent)
    if isinstance(prop, WzFloatProperty):
        return WzFloatProperty(new_name, float(prop.value), parent)
    if isinstance(prop, WzDoubleProperty):
        return WzDoubleProperty(new_name, float(prop.value), parent)
    if isinstance(prop, WzStringProperty):
        return WzStringProperty(new_name, str(prop.value), parent)
    if isinstance(prop, WzUolProperty):
        return WzUolProperty(new_name, str(prop.value), parent)
    if isinstance(prop, WzNullProperty):
        return WzNullProperty(new_name, parent)
    if isinstance(prop, WzConvexProperty):
        out = WzConvexProperty(new_name, parent)
        for point in prop.points:
            out.points.append(clone_property(point, parent=out))
        return out
    if isinstance(prop, WzSubProperty):
        out = WzSubProperty(new_name, parent)
        for child in prop.children():
            out.add(clone_property(child, parent=out))
        return out
    if isinstance(prop, WzSoundProperty):
        raise TypeError("Lucid Mob resources should not contain sound nodes")
    raise TypeError(f"unsupported property: {type(prop).__name__}")


def xml_escape_attr(value: str) -> str:
    return quoteattr(value)


def property_to_xml(prop, indent: int = 1) -> str:
    pad = "  " * indent
    name_attr = f"name={xml_escape_attr(prop.name)}"
    if isinstance(prop, WzNullProperty):
        return f"{pad}<null {name_attr}/>"
    if isinstance(prop, WzVectorProperty):
        return f'{pad}<vector {name_attr} x="{prop.x}" y="{prop.y}"/>'
    if isinstance(prop, WzCanvasProperty):
        attrs = f'{name_attr} width="{prop.width}" height="{prop.height}"'
        if int(prop.format) + int(prop.format2) != 0:
            attrs += f' format="{int(prop.format) + int(prop.format2)}"'
        children = list(prop.children())
        if not children:
            return f"{pad}<canvas {attrs}/>"
        body = "\n".join(property_to_xml(child, indent + 1) for child in children)
        return f"{pad}<canvas {attrs}>\n{body}\n{pad}</canvas>"
    if isinstance(prop, WzSoundProperty):
        return f'{pad}<sound {name_attr} length_ms="{prop.length_ms}" bytes="{prop.value}"/>'
    if isinstance(prop, WzConvexProperty):
        body = "\n".join(f'{pad}  <vector name="{point.name}" x="{point.x}" y="{point.y}"/>' for point in prop.points)
        return f"{pad}<extended {name_attr}>\n{body}\n{pad}</extended>"
    if isinstance(prop, WzUolProperty):
        return f"{pad}<uol {name_attr} value={xml_escape_attr(str(prop.value))}/>"
    if isinstance(prop, WzSubProperty):
        children = list(prop.children())
        if not children:
            return f"{pad}<imgdir {name_attr}/>"
        body = "\n".join(property_to_xml(child, indent + 1) for child in children)
        return f"{pad}<imgdir {name_attr}>\n{body}\n{pad}</imgdir>"
    if isinstance(prop, WzShortProperty):
        tag = "short"
    elif isinstance(prop, WzIntProperty):
        tag = "int"
    elif isinstance(prop, WzLongProperty):
        tag = "long"
    elif isinstance(prop, WzFloatProperty):
        tag = "float"
    elif isinstance(prop, WzDoubleProperty):
        tag = "double"
    elif isinstance(prop, WzStringProperty):
        tag = "string"
    else:
        tag = "string"
    return f"{pad}<{tag} {name_attr} value={xml_escape_attr(str(prop.value))}/>"


def img_to_xml(img: WzImage, root_name: str | None = None) -> str:
    body = "\n".join(property_to_xml(child, 1) for child in img.root.children())
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<imgdir name="{root_name or img.name}">\n{body}\n</imgdir>\n'


def patch_client_mob(mob_id: int) -> None:
    img = source_img(SRC / f"Mob/{mob_id}.img")
    sanitize_lucid_root(img.root, mob_id, server=False)
    reencode_canvas_tree(img.root)
    atomic_write_bytes(ROOT / f"clien/Data/Mob/{mob_id}.img", encode_image_body(img, gms_reader()))


def patch_server_mob(mob_id: int) -> None:
    img = source_img(SRC / f"Mob/{mob_id}.img")
    sanitize_lucid_root(img.root, mob_id, server=True)
    atomic_write_text(ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml", img_to_xml(img, root_name=f"{mob_id}.img"))


def patch_client_strings() -> None:
    path = ROOT / "clien/Data/String/Mob.img"
    data = path.read_bytes()
    img = WzImage.from_bytes(data, key=TARGET_KEY, name=path.name)
    img.parse()
    missing = [(mob_id, name) for mob_id, name in LUCID_NAMES.items() if img.root.get(f"{mob_id}/name") is None]
    if not missing:
        return

    reader = WzBinaryReader(io.BytesIO(data), TARGET_KEY)
    reader.seek(0)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise ValueError(f"{path}: unexpected String/Mob.img header")
    reader.skip(2)
    count_offset = reader.position
    first = data[count_offset]
    if first == 0x80:
        count_len = 5
        count = struct.unpack("<i", data[count_offset + 1:count_offset + 5])[0]
    else:
        count_len = 1
        count = struct.unpack("<b", data[count_offset:count_offset + 1])[0]
    count_bytes = encode_compressed_int(count + len(missing))
    if len(count_bytes) != count_len:
        raise ValueError(f"{path}: root count width would change")

    encoder = gms_reader()
    append = bytearray()
    for mob_id, name in missing:
        entry = WzSubProperty(str(mob_id))
        entry.add(WzStringProperty("name", name, entry))
        append += encode_string_block(encoder, entry.name)
        append += bytes([_tag_for(entry)])
        append += _encode_property_body(entry, encoder)

    patched = bytearray(data)
    patched[count_offset:count_offset + count_len] = count_bytes
    patched += append
    atomic_write_bytes(path, bytes(patched))


def patch_server_strings(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for mob_id, name in LUCID_NAMES.items():
        replacement = f'<imgdir name="{mob_id}"><string name="name" value="{name}"/></imgdir>'
        pattern = rf'<imgdir name="{mob_id}">.*?</imgdir>'
        if re.search(pattern, text, flags=re.DOTALL):
            text = re.sub(pattern, replacement, text, count=1, flags=re.DOTALL)
        else:
            root_close = text.rfind("</imgdir>")
            if root_close < 0:
                raise ValueError(f"{path}: missing root closing imgdir")
            text = text[:root_close] + replacement + text[root_close:]
    atomic_write_text(path, text)


def main() -> int:
    for mob_id in LUCID_IDS:
        patch_client_mob(mob_id)
        patch_server_mob(mob_id)
    patch_client_ui()
    patch_client_strings()
    patch_server_strings(ROOT / "gms-server/wz/String.wz/Mob.img.xml")
    patch_server_strings(ROOT / "gms-server/wz-zh-CN/String.wz/Mob.img.xml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
