#!/usr/bin/env python3
"""Add the fifth-job goddess NPC and hero coin resources."""

from __future__ import annotations

import base64
import io
import re
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzKey,
    WzStringProperty,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


NPC_ID = "9900008"
SOURCE_NPC_ID = "2144020"
HERO_COIN_ID = "4310060"
HERO_COIN_NODE = "04310060"
TARGET_KEY = WzKey.for_region("GMS")

CLIENT_MAP = ROOT / "clien/Data/Map/Map/Map9/910000000.img"
CLIENT_STRING = ROOT / "clien/Data/String/Npc.img"
CLIENT_SOURCE_NPC = ROOT / f"clien/Data/Npc/{SOURCE_NPC_ID}.img"
CLIENT_TARGET_NPC = ROOT / f"clien/Data/Npc/{NPC_ID}.img"
SERVER_SOURCE_NPC = ROOT / f"gms-server/wz/Npc.wz/{SOURCE_NPC_ID}.img.xml"
SERVER_TARGET_NPC = ROOT / f"gms-server/wz/Npc.wz/{NPC_ID}.img.xml"
CLIENT_ITEM = ROOT / "clien/Data/Item/Etc/0431.img"
CLIENT_ITEM_STRING = ROOT / "clien/Data/String/Etc.img"
SERVER_ITEM = ROOT / "gms-server/wz/Item.wz/Etc/0431.img.xml"
SERVER_ITEM_STRING = ROOT / "gms-server/wz/String.wz/Etc.img.xml"

HERO_COIN_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAB4AAAAeCAYAAAA7MK6iAAAAAXNSR0IArs4c6QAAAARn"
    "QU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAALzSURBVEhLtZY7a1RhEIYf"
    "7wbFQkXRQgtRMYKiQRQVYicpvRRaiIhBiCm8NJH1ggjCFmIqW1sbf0k6f4F/QLZMe2S+"
    "nXd2zpeTzUbMB5Oz322emXnnHAKbH02Hbfloyljplcev5UdNs9rfUnhxXoCr/QD+WJiL"
    "+f/OfghsBkNb6RWImUFlCsT2/zWAlnYBdKcFoLW0/ml2JqrREcBEgURm4WQcNO0bvJz"
    "RXd2ZsAe8cQYjJyu9oZZVln9+LhYTyH5H5rrT1n/sGEH9Ug39/X2+WZw+UcxANlcQyrr"
    "cEXxU9rEjMmpdTpka0JwbyJ4GEzSb7k8CbgHUsaV8vm4AgaWhQLUULc03gEdjxevRDFo"
    "dW4OVrc62mq6CrwfuhGqtC56h0jgabhPwUVN5V5vlRrKy5yYyx4LnYMzsXg3vAkemBVx"
    "lqnXBI3sPVIHpnHSPzN2PvnAZHtq0Xp2soTeIAdbo6ev5XBe47FUfkxKJurgG15mEZv6"
    "ea57P1uAs19pyK2Np7B8LweQsNE6Z5XWz0DhXqkPjIdgzbcE98zDvYDujLOqS5pILWiq"
    "0DthGgAKuznQT9N7hqfJbZc372jObBGpjBOkooxxlZwF2aQQ2y52+EdhGwHMzZY0nAdt"
    "6Bm8EtRFQZa3SS8u64UojNYOoitZ1f2JwgeYO998Cr2k4nwuqLKV91yvUNYojZZw1D7i"
    "6ver6DJWV4EcfjW01LA8dKlZACiB3e2WCap7Km20PsKMOwCbbgd3APuAgcFyXskN94bL"
    "OglbAW8B1YAY45/72AzsFtz8WyRRwBDgDXAVuA/eBJ3ImgDLXswK+B94CS8Ar4BlwxwM"
    "46pkH2DI16AVgDngMvATeAZ+Br8C3kn36h16BOHAZ+AL0/c5H4A2wkMDGaIH3AseAyw"
    "5+CDwFFoHXHr1l8aFDO7MXwHNg3oN+ANx1XzeB8+7fZGyVehdwwHU47QcveiBXgGvADW"
    "DWtTNnpp9JYvuXvFrTwFngFHDS/R1ybVvN9Rc2wFVjzghWoQAAAABJRU5ErkJggg=="
)

SERVER_ITEM_BLOCK = '''  <imgdir name="04310060">
    <imgdir name="info">
      <canvas name="icon" width="30" height="30">
        <vector name="origin" x="-1" y="30"/>
      </canvas>
      <canvas name="iconRaw" width="30" height="30">
        <vector name="origin" x="-1" y="30"/>
      </canvas>
      <int name="notSale" value="1"/>
      <int name="price" value="1"/>
      <int name="slotMax" value="1000"/>
    </imgdir>
  </imgdir>'''

SERVER_STRING_BLOCK = (
    '<imgdir name="4310060"><string name="desc" value="没什么卵用的币，丢了吧。"/>'
    '<string name="name" value="英雄币"/></imgdir>'
)


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), TARGET_KEY)


def atomic_write(path: Path, data: bytes | str) -> None:
    mode = "w" if isinstance(data, str) else "wb"
    kwargs = {"encoding": "utf-8"} if isinstance(data, str) else {}
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode=mode,
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
        **kwargs,
    ) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def load_img(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"cannot safely rewrite {path}: {image.parse_warnings}")
    return image


def hero_coin_image() -> Image.Image:
    image = Image.open(io.BytesIO(base64.b64decode(HERO_COIN_PNG_BASE64))).convert("RGBA")
    if image.size != (30, 30):
        raise RuntimeError(f"unexpected hero coin icon size: {image.size}")
    return image


def make_hero_coin_canvas(name: str, parent: WzSubProperty, image: Image.Image) -> WzCanvasProperty:
    canvas = WzCanvasProperty(name, parent)
    canvas.width, canvas.height = image.size
    canvas.format = 2
    canvas.format2 = 0
    canvas._png_data = encode_canvas_payload(
        image, canvas.format, canvas.width, canvas.height, key=TARGET_KEY, listwz=False
    )
    canvas._png_length = len(canvas._png_data)
    canvas.add(WzVectorProperty("origin", -1, 30, canvas))
    return canvas


def hero_coin_item_is_current(image: WzImage, source: Image.Image) -> bool:
    node = image.get(HERO_COIN_NODE)
    info = node.child("info") if isinstance(node, WzSubProperty) else None
    if not isinstance(info, WzSubProperty):
        return False

    expected_ints = {"notSale": 1, "price": 1, "slotMax": 1000}
    for name, value in expected_ints.items():
        prop = info.child(name)
        if not isinstance(prop, WzIntProperty) or int(prop.value) != value:
            return False
    if info.child("tradeBlock") is not None:
        return False

    for name in ("icon", "iconRaw"):
        canvas = info.child(name)
        if not isinstance(canvas, WzCanvasProperty) or (canvas.width, canvas.height) != source.size:
            return False
        origin = canvas.child("origin")
        if not isinstance(origin, WzVectorProperty) or (origin.x, origin.y) != (-1, 30):
            return False
        try:
            decoded = decode_canvas(canvas, region="GMS").convert("RGBA")
        except Exception:
            return False
        if decoded.size != source.size or decoded.tobytes() != source.tobytes():
            return False
    return True


def patch_client_item() -> bool:
    image = load_img(CLIENT_ITEM)
    source = hero_coin_image()
    if hero_coin_item_is_current(image, source):
        return False

    node = WzSubProperty(HERO_COIN_NODE, image.root)
    info = WzSubProperty("info", node)
    info.add(make_hero_coin_canvas("icon", info, source))
    info.add(make_hero_coin_canvas("iconRaw", info, source))
    for name, value in (("notSale", 1), ("price", 1), ("slotMax", 1000)):
        info.add(WzIntProperty(name, value, info))
    node.add(info)
    image.root.add(node)
    atomic_write(CLIENT_ITEM, encode_image_body(image, gms_reader()))
    return True


def patch_client_item_string() -> bool:
    image = load_img(CLIENT_ITEM_STRING)
    etc = image.get("Etc")
    if not isinstance(etc, WzSubProperty):
        raise RuntimeError(f"{CLIENT_ITEM_STRING} has no Etc node")

    current = etc.child(HERO_COIN_ID)
    if isinstance(current, WzSubProperty):
        desc = current.child("desc")
        name = current.child("name")
        if (
            isinstance(desc, WzStringProperty)
            and desc.value == "没什么卵用的币，丢了吧。"
            and isinstance(name, WzStringProperty)
            and name.value == "英雄币"
        ):
            return False

    entry = WzSubProperty(HERO_COIN_ID, etc)
    entry.add(WzStringProperty("desc", "没什么卵用的币，丢了吧。", entry))
    entry.add(WzStringProperty("name", "英雄币", entry))
    etc.add(entry)
    atomic_write(CLIENT_ITEM_STRING, encode_image_body(image, gms_reader()))
    return True


def find_imgdir_block(text: str, node_name: str, start: int = 0) -> tuple[int, int]:
    pattern = re.compile(rf'<imgdir\b[^>]*\bname="{re.escape(node_name)}"[^>]*>')
    match = pattern.search(text, start)
    if match is None:
        raise RuntimeError(f"missing XML imgdir {node_name}")
    root_start = match.start()
    depth = 0
    for tag_match in re.finditer(r"</?imgdir\b[^>]*>", text[root_start:]):
        tag = tag_match.group(0)
        if tag.startswith("</"):
            depth -= 1
            if depth == 0:
                return root_start, root_start + tag_match.end()
        elif not tag.endswith("/>"):
            depth += 1
    raise RuntimeError(f"unterminated XML imgdir {node_name}")


def upsert_imgdir_child(text: str, parent_name: str, child_name: str, child_block: str) -> tuple[str, bool]:
    parent_start, parent_end = find_imgdir_block(text, parent_name)
    parent = text[parent_start:parent_end]
    try:
        child_start, child_end = find_imgdir_block(parent, child_name)
        if parent[child_start:child_end].strip() == child_block.strip():
            return text, False
        parent = parent[:child_start] + child_block + parent[child_end:]
    except RuntimeError:
        insert_at = parent.rfind("</imgdir>")
        if insert_at < 0:
            raise RuntimeError(f"cannot insert into XML imgdir {parent_name}")
        separator = "\n" if "\n" in parent else ""
        parent = parent[:insert_at] + separator + child_block + separator + parent[insert_at:]
    return text[:parent_start] + parent + text[parent_end:], True


def patch_server_item() -> bool:
    text = SERVER_ITEM.read_text(encoding="utf-8")
    updated, changed = upsert_imgdir_child(text, "0431.img", HERO_COIN_NODE, SERVER_ITEM_BLOCK)
    if changed:
        atomic_write(SERVER_ITEM, updated)
    return changed


def patch_server_item_string() -> bool:
    text = SERVER_ITEM_STRING.read_text(encoding="utf-8")
    updated, changed = upsert_imgdir_child(text, "Etc", HERO_COIN_ID, SERVER_STRING_BLOCK)
    if changed:
        atomic_write(SERVER_ITEM_STRING, updated)
    return changed


def patch_client_map() -> bool:
    image = load_img(CLIENT_MAP)
    life_root = image.get("life")
    if not isinstance(life_root, WzSubProperty):
        raise RuntimeError(f"{CLIENT_MAP} has no life node")
    for life in life_root.children():
        life_id = life.child("id") if isinstance(life, WzSubProperty) else None
        if isinstance(life_id, WzStringProperty) and str(life_id.value) == NPC_ID:
            return False

    numeric_names = [int(life.name) for life in life_root.children() if life.name.isdigit()]
    life = WzSubProperty(str(max(numeric_names, default=-1) + 1), life_root)
    life.add(WzStringProperty("type", "n", life))
    life.add(WzStringProperty("id", NPC_ID, life))
    for name, value in (
        ("mobTime", 0), ("f", 0), ("hide", 0),
        ("x", 580), ("y", 23), ("cy", 23), ("fh", 163),
        ("rx0", 530), ("rx1", 630),
    ):
        life.add(WzIntProperty(name, value, life))
    life_root.add(life)
    atomic_write(CLIENT_MAP, encode_image_body(image, gms_reader()))
    return True


def patch_client_string() -> bool:
    image = load_img(CLIENT_STRING)
    if image.get(NPC_ID) is not None:
        return False
    entry = WzSubProperty(NPC_ID, image.root)
    entry.add(WzStringProperty("name", "五转女神", entry))
    image.root.add(entry)
    atomic_write(CLIENT_STRING, encode_image_body(image, gms_reader()))
    return True


def clone_npc_appearance() -> list[Path]:
    written = []
    if not CLIENT_TARGET_NPC.exists():
        shutil.copy2(CLIENT_SOURCE_NPC, CLIENT_TARGET_NPC)
        written.append(CLIENT_TARGET_NPC)
    if not SERVER_TARGET_NPC.exists():
        text = SERVER_SOURCE_NPC.read_text(encoding="utf-8")
        source_root = f'<imgdir name="{SOURCE_NPC_ID}.img">'
        target_root = f'<imgdir name="{NPC_ID}.img">'
        if source_root not in text:
            raise RuntimeError(f"unexpected root in {SERVER_SOURCE_NPC}")
        atomic_write(SERVER_TARGET_NPC, text.replace(source_root, target_root, 1))
        written.append(SERVER_TARGET_NPC)
    return written


def main() -> None:
    written = clone_npc_appearance()
    if patch_client_map():
        written.append(CLIENT_MAP)
    if patch_client_string():
        written.append(CLIENT_STRING)
    if patch_client_item():
        written.append(CLIENT_ITEM)
    if patch_client_item_string():
        written.append(CLIENT_ITEM_STRING)
    if patch_server_item():
        written.append(SERVER_ITEM)
    if patch_server_item_string():
        written.append(SERVER_ITEM_STRING)
    if written:
        for path in written:
            print(path.relative_to(ROOT))
    else:
        print("already up to date")


if __name__ == "__main__":
    main()
