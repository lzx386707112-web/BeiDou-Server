#!/usr/bin/env python3
"""Migrate v095 Cygnus/Future Gate resources into BeiDou.

This is intentionally narrow: it only touches the resource ids used by the
271xxxx Future Gate / Knight Stronghold maps and the Cygnus expedition.
"""

from __future__ import annotations

import io
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
SRC_SERVER = Path("/Users/lizixian/Documents/mxd/怀旧岛V095仿官版/怀旧岛V095服务端")
SRC_CLIENT = Path("/Users/lizixian/Documents/mxd/怀旧岛V095仿官版/怀旧岛V095客户端")
BACKUP_ROOT = Path("/private/tmp/cygnus-migration-backup")
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzConvexProperty,
    WzDoubleProperty,
    WzFile,
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
from wzpy.canvas import (  # noqa: E402
    _read_canvas_bytes,
    _zlib_lenient,
    decode_canvas,
    encode_canvas_payload,
)
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402

TARGET_KEY = WzKey.for_region("GMS")
TRANSPARENT_PIXEL = Image.new("RGBA", (1, 1), (0, 0, 0, 0))


MAP_IDS = [
    271000000, 271000100, 271000200, 271000210, 271000300,
    271010000, 271010001, 271010100, 271010200, 271010300,
    271010301, 271010400, 271010500, 271020000, 271020100,
    271030000, 271030010, 271030100, 271030101, 271030102,
    271030200, 271030201, 271030202, 271030203, 271030204,
    271030205, 271030300, 271030310, 271030320, 271030400,
    271030410, 271030411, 271030412, 271030413, 271030414,
    271030415, 271030416, 271030417, 271030418, 271030419,
    271030500, 271030510, 271030520, 271030530, 271030540,
    271030600, 271040000, 271040100, 271040110, 271040200,
    271040210,
]

MOB_IDS = list(range(8600000, 8600007)) + list(range(8610000, 8610023)) + list(range(8850000, 8850013))
NPC_IDS = list(range(2142000, 2142011)) + [2143000, 2143001, 2143003, 2143004]
QUEST_FILES = ["QuestInfo.img", "Check.img", "Act.img", "Say.img"]
MOB_SKILL_LEVELS = [
    (100, 25), (114, 42), (114, 43), (120, 19), (129, 13),
    (133, 8), (138, 1), (145, 9), (146, 1), (146, 2),
    (171, 1), (172, 1), (200, 221), (200, 222), (200, 223),
    (200, 224), (200, 228), (200, 229), (200, 230), (200, 231),
    (200, 232), (200, 233),
]
MOB_SKILL_LEVEL_OVERRIDES = {
    # v95 8600001 uses STUN 123/35, but this client only safely supports 123 up to 26.
    8600001: {"info/skill/0/level": 26},
}
CLIENT_MOBSKILL_BASELINE = BACKUP_ROOT / "clien/Data/Skill/MobSkill.img"


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


def backup(path: Path) -> None:
    if not path.exists():
        return
    rel = path.relative_to(ROOT)
    backup_path = BACKUP_ROOT / rel
    if backup_path.exists():
        return
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)


def copy_resource(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    backup(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), TARGET_KEY)


def reencode_canvas(prop, source_region: str) -> None:
    if isinstance(prop, WzCanvasProperty) and prop.has_pixels():
        try:
            if int(prop.width) <= 0 or int(prop.height) <= 0:
                raise ValueError(f"invalid canvas size {prop.width}x{prop.height}")
            image = decode_canvas(prop, region=source_region)
            width = int(prop.width)
            height = int(prop.height)
            fmt = int(prop.format) + int(prop.format2)
        except Exception:
            image = TRANSPARENT_PIXEL
            width = 1
            height = 1
            fmt = 2
            prop.width = width
            prop.height = height
            prop.format = 2
            prop.format2 = 0
        prop._png_data = encode_canvas_payload(
            image,
            fmt,
            width,
            height,
            key=TARGET_KEY,
            listwz=False,
        )
        prop._png_length = len(prop._png_data)

    if hasattr(prop, "children"):
        for child in prop.children():
            reencode_canvas(child, source_region)


def export_wz_image(wz: WzFile, entry: str, dst: Path) -> None:
    image = wz.root.get(entry)
    if not isinstance(image, WzImage):
        raise RuntimeError(f"missing WZ image entry: {entry}")
    image.parse()
    reencode_canvas(image.root, "EMS")
    backup(dst)
    atomic_write_bytes(dst, encode_image_body(image, gms_reader()))


def clone_property(prop, name: str | None = None, parent=None, source_region: str | None = None):
    new_name = prop.name if name is None else name
    if isinstance(prop, WzCanvasProperty):
        out = WzCanvasProperty(new_name, parent)
        out.width = prop.width
        out.height = prop.height
        out.format = prop.format
        out.format2 = prop.format2
        if source_region is None:
            out._png_offset = prop._png_offset
            out._png_length = prop._png_length
            out._png_data = prop._png_data
            out._wz_image = prop._wz_image
        elif prop.has_pixels():
            try:
                if int(prop.width) <= 0 or int(prop.height) <= 0:
                    raise ValueError(f"invalid canvas size {prop.width}x{prop.height}")
                image = decode_canvas(prop, region=source_region)
                width = int(prop.width)
                height = int(prop.height)
                fmt = int(prop.format) + int(prop.format2)
            except Exception:
                image = TRANSPARENT_PIXEL
                width = 1
                height = 1
                fmt = 2
                out.width = width
                out.height = height
                out.format = 2
                out.format2 = 0
            out._png_data = encode_canvas_payload(
                image,
                fmt,
                width,
                height,
                key=TARGET_KEY,
                listwz=False,
            )
            out._png_length = len(out._png_data)
        for child in prop.children():
            out.add(clone_property(child, parent=out, source_region=source_region))
        return out
    if isinstance(prop, WzSubProperty):
        out = WzSubProperty(new_name, parent)
        for child in prop.children():
            out.add(clone_property(child, parent=out, source_region=source_region))
        return out
    if isinstance(prop, WzVectorProperty):
        return WzVectorProperty(new_name, int(prop.x), int(prop.y), parent)
    if isinstance(prop, WzStringProperty):
        return WzStringProperty(new_name, str(prop.value), parent)
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
    if isinstance(prop, WzNullProperty):
        return WzNullProperty(new_name, parent)
    if isinstance(prop, WzUolProperty):
        return WzUolProperty(new_name, prop.value, parent)
    if isinstance(prop, WzConvexProperty):
        out = WzConvexProperty(new_name, parent)
        out.points = [clone_property(point, parent=out, source_region=source_region) for point in prop.points]
        return out
    if isinstance(prop, WzSoundProperty):
        out = WzSoundProperty(new_name, parent)
        out.length_ms = prop.length_ms
        out.header = prop.header
        out._data_offset = prop._data_offset
        out._data_length = prop._data_length
        out._wz_image = prop._wz_image
        out._data = prop._data
        return out
    raise TypeError(f"unsupported WZ property: {type(prop).__name__}")


def normalize_mobskill_level_xml(level_node: ET.Element) -> None:
    for child in level_node:
        if child.tag == "string" and (child.get("name") or "").isdigit() and (child.get("value") or "").isdigit():
            child.tag = "int"


def normalize_mobskill_level_property(level_node: WzSubProperty) -> None:
    for child in list(level_node.children()):
        if isinstance(child, WzStringProperty) and child.name.isdigit() and str(child.value).isdigit():
            level_node.add(WzIntProperty(child.name, int(child.value), level_node))


def client_mobskill_baseline(dst_path: Path) -> WzImage:
    baseline_path = CLIENT_MOBSKILL_BASELINE if CLIENT_MOBSKILL_BASELINE.exists() else dst_path
    baseline = WzImage.from_bytes(baseline_path.read_bytes(), key=TARGET_KEY, name="MobSkill.img")
    baseline.parse()
    return baseline


def supported_client_mobskill_ids(baseline: WzImage) -> set[str]:
    return {child.name for child in baseline.root.children() if child.name.isdigit()}


def compatible_client_level_fields(baseline: WzImage, skill_id: int) -> set[str]:
    level_root = baseline.get(f"{skill_id}/level")
    if level_root is None:
        return set()
    fields: set[str] = set()
    for level in level_root.children():
        if hasattr(level, "children"):
            fields.update(child.name for child in level.children())
    return fields


def prune_client_mobskill_level(level_node: WzSubProperty, allowed_fields: set[str]) -> None:
    if not allowed_fields:
        return
    for child in list(level_node.children()):
        if child.name not in allowed_fields:
            level_node._children.pop(child.name, None)


def baseline_client_mobskill_max_level(baseline: WzImage, skill_id: int) -> int:
    level_root = baseline.get(f"{skill_id}/level")
    if level_root is None:
        return 0
    levels = [int(child.name) for child in level_root.children() if child.name.isdigit()]
    return max(levels, default=0)


def client_mobskill_levels_to_patch(baseline: WzImage, supported_skill_ids: set[str]) -> list[tuple[int, int]]:
    max_requested: dict[int, int] = {}
    for skill_id, level in MOB_SKILL_LEVELS:
        if str(skill_id) not in supported_skill_ids:
            continue
        max_requested[skill_id] = max(max_requested.get(skill_id, 0), level)

    levels: list[tuple[int, int]] = []
    for skill_id, max_level in sorted(max_requested.items()):
        baseline_max = baseline_client_mobskill_max_level(baseline, skill_id)
        for level in range(baseline_max + 1, max_level + 1):
            levels.append((skill_id, level))
    return levels


def find_imgdir_block(text: str, node_name: str, start: int = 0) -> tuple[int, int]:
    token = f'<imgdir name="{node_name}">'
    root_start = text.find(token, start)
    if root_start < 0:
        raise RuntimeError(f"missing XML imgdir {node_name}")
    depth = 0
    for match in re.finditer(r"</?imgdir\b[^>]*>", text[root_start:]):
        tag = match.group(0)
        if tag.startswith("</"):
            depth -= 1
            if depth == 0:
                return root_start, root_start + match.end()
        elif not tag.endswith("/>"):
            depth += 1
    raise RuntimeError(f"unterminated XML imgdir {node_name}")


def insert_or_replace_child_block(text: str, parent_name: str, child_name: str, child_block: str) -> str:
    parent_start, parent_end = find_imgdir_block(text, parent_name)
    parent = text[parent_start:parent_end]
    try:
        child_start, child_end = find_imgdir_block(parent, child_name)
        parent = parent[:child_start] + parent[child_end:]
    except RuntimeError:
        pass
    insert_at = parent.rfind("</imgdir>")
    if insert_at < 0:
        raise RuntimeError(f"cannot insert into {parent_name}")
    parent = parent[:insert_at] + child_block + parent[insert_at:]
    return text[:parent_start] + parent + text[parent_end:]


def direct_imgdir(parent: ET.Element, name: str) -> ET.Element | None:
    for child in parent:
        if child.tag == "imgdir" and child.get("name") == name:
            return child
    return None


def direct_child(parent: ET.Element, name: str) -> ET.Element | None:
    for child in parent:
        if child.get("name") == name:
            return child
    return None


def mobskill_xml_text(root: ET.Element) -> str:
    body = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>{body}'


def patch_direct_string_xml(file_name: str, ids: list[int]) -> None:
    src_path = SRC_SERVER / "wz/String.wz" / file_name
    dst_path = ROOT / "gms-server/wz/String.wz" / file_name
    src_text = src_path.read_text(encoding="utf-8-sig")
    dst_text = dst_path.read_text(encoding="utf-8-sig")
    for item_id in ids:
        try:
            s, e = find_imgdir_block(src_text, str(item_id))
        except RuntimeError:
            continue
        block = src_text[s:e]
        try:
            ds, de = find_imgdir_block(dst_text, str(item_id))
            dst_text = dst_text[:ds] + dst_text[de:]
        except RuntimeError:
            pass
        insert_at = dst_text.rfind("</imgdir>")
        dst_text = dst_text[:insert_at] + block + dst_text[insert_at:]
    backup(dst_path)
    atomic_write_text(dst_path, dst_text)


def patch_map_string_xml() -> None:
    src_path = SRC_SERVER / "wz/String.wz/Map.img.xml"
    dst_path = ROOT / "gms-server/wz/String.wz/Map.img.xml"
    src_text = src_path.read_text(encoding="utf-8-sig")
    dst_text = dst_path.read_text(encoding="utf-8-sig")
    for map_id in MAP_IDS:
        try:
            s, e = find_imgdir_block(src_text, str(map_id))
        except RuntimeError:
            continue
        block = src_text[s:e]
        dst_text = insert_or_replace_child_block(dst_text, "ossyria", str(map_id), block)
    backup(dst_path)
    atomic_write_text(dst_path, dst_text)


def patch_mobskill_xml() -> None:
    src_path = SRC_SERVER / "wz/Skill.wz/MobSkill.img.xml"
    dst_path = ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml"
    src_root = ET.parse(src_path).getroot()
    dst_root = ET.parse(dst_path).getroot()
    for skill_id, level in MOB_SKILL_LEVELS:
        skill = str(skill_id)
        level_name = str(level)

        src_skill = direct_imgdir(src_root, skill)
        if src_skill is None:
            raise RuntimeError(f"missing source MobSkill {skill}")
        src_level_root = direct_imgdir(src_skill, "level")
        source_level = direct_imgdir(src_level_root, level_name) if src_level_root is not None else None
        if source_level is None:
            raise RuntimeError(f"missing source MobSkill level {skill}/{level_name}")

        dst_skill = direct_imgdir(dst_root, skill)
        if dst_skill is None:
            dst_skill = ET.Element("imgdir", {"name": skill})
            dst_root.append(dst_skill)
        dst_level_root = direct_imgdir(dst_skill, "level")
        if dst_level_root is None:
            dst_level_root = ET.Element("imgdir", {"name": "level"})
            dst_skill.append(dst_level_root)

        old_level = direct_imgdir(dst_level_root, level_name)
        if old_level is not None:
            dst_level_root.remove(old_level)
        new_level = deepcopy(source_level)
        normalize_mobskill_level_xml(new_level)
        dst_level_root.append(new_level)
    backup(dst_path)
    atomic_write_text(dst_path, mobskill_xml_text(dst_root))


def patch_client_string_images() -> None:
    with WzFile.open(str(SRC_CLIENT / "String.wz"), region="EMS", version=95) as src_wz:
        for img_name, ids in [("Mob.img", MOB_IDS + [8850013]), ("Npc.img", NPC_IDS)]:
            src_img = src_wz.root.get(img_name)
            dst_path = ROOT / "clien/Data/String" / img_name
            dst_img = WzImage.from_bytes(dst_path.read_bytes(), key=TARGET_KEY, name=img_name)
            src_img.parse()
            dst_img.parse()
            for item_id in ids:
                source = src_img.get(str(item_id))
                if source is not None:
                    dst_img.root.add(clone_property(source, str(item_id), dst_img.root, source_region="EMS"))
            backup(dst_path)
            atomic_write_bytes(dst_path, encode_image_body(dst_img, gms_reader()))


def patch_client_mobskill() -> None:
    with WzFile.open(str(SRC_CLIENT / "Skill.wz"), region="EMS", version=95) as src_wz:
        src_img = src_wz.root.get("MobSkill.img")
        src_img.parse()
        dst_path = ROOT / "clien/Data/Skill/MobSkill.img"
        dst_img = WzImage.from_bytes(dst_path.read_bytes(), key=TARGET_KEY, name="MobSkill.img")
        dst_img.parse()
        baseline = client_mobskill_baseline(dst_path)
        supported_skill_ids = supported_client_mobskill_ids(baseline)
        for skill in list(dst_img.root.children()):
            if skill.name.isdigit() and skill.name not in supported_skill_ids:
                dst_img.root._children.pop(skill.name, None)
        for skill_id, level in client_mobskill_levels_to_patch(baseline, supported_skill_ids):
            if dst_img.get(str(skill_id)) is None:
                source_skill = src_img.get(str(skill_id))
                if source_skill is None:
                    raise RuntimeError(f"missing source client MobSkill {skill_id}")
                dst_img.root.add(clone_property(source_skill, str(skill_id), dst_img.root, source_region="EMS"))
            parent = dst_img.get(f"{skill_id}/level")
            source = src_img.get(f"{skill_id}/level/{level}")
            if parent is None or source is None:
                raise RuntimeError(f"missing client MobSkill path {skill_id}/level/{level}")
            new_level = clone_property(source, str(level), parent, source_region="EMS")
            normalize_mobskill_level_property(new_level)
            prune_client_mobskill_level(new_level, compatible_client_level_fields(baseline, skill_id))
            parent.add(new_level)
        backup(dst_path)
        atomic_write_bytes(dst_path, encode_image_body(dst_img, gms_reader()))


def patch_server_mob_skill_overrides() -> None:
    for mob_id, overrides in MOB_SKILL_LEVEL_OVERRIDES.items():
        dst_path = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
        root = ET.parse(dst_path).getroot()
        changed = False
        for path, value in overrides.items():
            node = root
            for part in path.split("/"):
                node = direct_child(node, part) if node is not None else None
            if node is None or node.tag != "int":
                raise RuntimeError(f"missing server mob override path {mob_id}/{path}")
            if node.get("value") != str(value):
                node.set("value", str(value))
                changed = True
        if changed:
            backup(dst_path)
            atomic_write_text(dst_path, mobskill_xml_text(root))


def patch_client_mob_skill_overrides() -> None:
    for mob_id, overrides in MOB_SKILL_LEVEL_OVERRIDES.items():
        dst_path = ROOT / f"clien/Data/Mob/{mob_id}.img"
        dst_img = WzImage.from_bytes(dst_path.read_bytes(), key=TARGET_KEY, name=f"{mob_id}.img")
        dst_img.parse()
        changed = False
        for path, value in overrides.items():
            node = dst_img.get(path)
            if node is None or not isinstance(node, WzIntProperty):
                raise RuntimeError(f"missing client mob override path {mob_id}/{path}")
            if node.value != value:
                node._value = value
                changed = True
        if changed:
            backup(dst_path)
            atomic_write_bytes(dst_path, encode_image_body(dst_img, gms_reader()))


def patch_client_connect() -> None:
    def ensure_subproperty(root: WzSubProperty, path: str) -> WzSubProperty:
        node = root
        for part in path.split("/"):
            child = node.child(part)
            if child is None:
                child = WzSubProperty(part, node)
                node.add(child)
            if not isinstance(child, WzSubProperty):
                raise RuntimeError(f"connect/{path} crosses non-directory node {part}")
            node = child
        return node

    with WzFile.open(str(SRC_CLIENT / "Map.wz"), region="EMS", version=95) as src_wz:
        src_img = src_wz.root.get("Obj/connect.img")
        src_img.parse()
        dst_path = ROOT / "clien/Data/Map/Obj/connect.img"
        dst_img = WzImage.from_bytes(dst_path.read_bytes(), key=TARGET_KEY, name="connect.img")
        dst_img.parse()
        for path in [
            "ladder/71/0", "ladder/71/1", "ladder/71/2",
        ]:
            source = src_img.get(path)
            if source is None:
                raise RuntimeError(f"missing source connect/{path}")
            parent_path, name = path.rsplit("/", 1)
            parent = ensure_subproperty(dst_img.root, parent_path)
            parent.add(clone_property(source, name, parent, source_region="EMS"))
        for rope_id in ["14", "27"]:
            for frame in ["0", "1", "2", "3"]:
                source = dst_img.get(f"rope/0/{frame}")
                if source is None:
                    raise RuntimeError(f"missing compatible connect/rope/0/{frame}")
                parent = ensure_subproperty(dst_img.root, f"rope/{rope_id}")
                parent.add(clone_property(source, frame, parent, source_region="GMS"))
        backup(dst_path)
        atomic_write_bytes(dst_path, encode_image_body(dst_img, gms_reader()))


def patch_client_maphelper_marks() -> None:
    with WzFile.open(str(SRC_CLIENT / "Map.wz"), region="EMS", version=95) as src_wz:
        src_img = src_wz.root.get("MapHelper.img")
        if src_img is None:
            raise RuntimeError("missing source MapHelper.img")
        src_img.parse()
        dst_path = ROOT / "clien/Data/Map/MapHelper.img"
        dst_img = WzImage.from_bytes(dst_path.read_bytes(), key=TARGET_KEY, name="MapHelper.img")
        dst_img.parse()
        mark_root = dst_img.get("mark")
        if mark_root is None:
            raise RuntimeError("current MapHelper.img has no mark node")
        for mark in ["destructionTown", "darkEreb"]:
            source = src_img.get(f"mark/{mark}")
            if source is None:
                raise RuntimeError(f"missing source MapHelper mark/{mark}")
            mark_root.add(clone_property(source, mark, mark_root, source_region="EMS"))
        backup(dst_path)
        atomic_write_bytes(dst_path, encode_image_body(dst_img, gms_reader()))


def patch_client_dark_ereb_tile() -> None:
    # 095 maps reference Tile/darkEreb.img, but the 095 Map.wz does not
    # contain that image. Reuse the migrated 095 destructionField tile and add
    # the one required bsc/5 node from destructionTown2 instead of inventing
    # new tile child names.
    base_path = ROOT / "clien/Data/Map/Tile/destructionField.img"
    patch_path = ROOT / "clien/Data/Map/Tile/destructionTown2.img"
    dst_path = ROOT / "clien/Data/Map/Tile/darkEreb.img"
    base = WzImage.from_bytes(base_path.read_bytes(), key=TARGET_KEY, name=dst_path.name)
    patch = WzImage.from_bytes(patch_path.read_bytes(), key=TARGET_KEY, name=patch_path.name)
    base.parse()
    patch.parse()
    bsc = base.get("bsc")
    source = patch.get("bsc/5")
    if bsc is None or source is None:
        raise RuntimeError("cannot build Tile/darkEreb.img compatibility tile")
    bsc.add(clone_property(source, "5", bsc, source_region="GMS"))
    backup(dst_path)
    atomic_write_bytes(dst_path, encode_image_body(base, gms_reader()))


def decode_prefixed_argb4444_canvas(canvas: WzCanvasProperty, width: int, height: int) -> Image.Image:
    raw = _read_canvas_bytes(canvas)
    decoded = None
    for skip in range(0, 50):
        try:
            decoded = _zlib_lenient(raw[skip:])
        except Exception:
            continue
        if decoded:
            break
    if not decoded:
        raise RuntimeError(f"cannot decode prefixed ARGB4444 canvas {canvas.name}")
    if len(decoded) < width * height * 2:
        raise RuntimeError(f"decoded canvas {canvas.name} is too short: {len(decoded)}")

    out = bytearray(width * height * 4)
    for i in range(width * height):
        lo = decoded[i * 2]
        hi = decoded[i * 2 + 1]
        b = (lo & 0x0F) | ((lo & 0x0F) << 4)
        g = (lo & 0xF0) | ((lo & 0xF0) >> 4)
        r = (hi & 0x0F) | ((hi & 0x0F) << 4)
        a = (hi & 0xF0) | ((hi & 0xF0) >> 4)
        out[i * 4:i * 4 + 4] = bytes([r, g, b, a])
    return Image.frombytes("RGBA", (width, height), bytes(out))


def patch_client_wrapped_tile_canvases() -> None:
    repairs = {
        "destructionTown1": {
            "enH0/0": (90, 33), "enH0/1": (90, 33),
            "enH0/2": (90, 34), "enH0/3": (90, 33),
            "edU/0": (68, 28), "edU/1": (61, 34),
            "enV0/0": (28, 60), "enV1/0": (26, 60),
            "slLU/0": (91, 90), "slRU/0": (90, 90),
        },
        "destructionTown2": {
            "enH0/0": (90, 33), "enH0/1": (90, 34),
            "enH0/2": (90, 33), "enH0/3": (90, 33),
            "edU/0": (63, 34), "edU/1": (68, 28),
            "enV0/0": (28, 60), "enV1/0": (26, 60),
            "slLU/0": (91, 90), "slRU/0": (90, 90),
        },
        "destructionField": {
            "enH0/0": (90, 39), "enH0/1": (90, 40),
            "enH0/2": (90, 40), "enH0/3": (90, 39),
            "edU/0": (57, 38), "edU/1": (53, 37),
            "enV0/0": (29, 60), "enV0/1": (29, 60),
            "enV1/0": (29, 60), "enV1/1": (29, 60),
            "slLU/0": (90, 94), "slRU/0": (90, 94),
        },
    }

    with WzFile.open(str(SRC_CLIENT / "Map.wz"), region="EMS", version=95) as src_wz:
        for tile_name, paths in repairs.items():
            src_img = src_wz.root.get(f"Tile/{tile_name}.img")
            if src_img is None:
                raise RuntimeError(f"missing source Tile/{tile_name}.img")
            src_img.parse()
            dst_path = ROOT / f"clien/Data/Map/Tile/{tile_name}.img"
            dst_img = WzImage.from_bytes(dst_path.read_bytes(), key=TARGET_KEY, name=dst_path.name)
            dst_img.parse()
            for node_path, (width, height) in paths.items():
                source = src_img.get(node_path)
                target = dst_img.get(node_path)
                if not isinstance(source, WzCanvasProperty) or not isinstance(target, WzCanvasProperty):
                    raise RuntimeError(f"missing tile canvas {tile_name}/{node_path}")
                image = decode_prefixed_argb4444_canvas(source, width, height)
                target.width = width
                target.height = height
                target.format = 1
                target.format2 = 0
                target._png_data = encode_canvas_payload(
                    image,
                    1,
                    width,
                    height,
                    key=TARGET_KEY,
                    listwz=False,
                )
                target._png_length = len(target._png_data)
            backup(dst_path)
            atomic_write_bytes(dst_path, encode_image_body(dst_img, gms_reader()))


def patch_client_acc14_wrapped_canvases() -> None:
    repairs = {
        "darkErebKnights/cygnusGarden/1/0": (1827, 155),
        "darkErebKnights/cygnusGarden/2/0": (1192, 155),
    }

    with WzFile.open(str(SRC_CLIENT / "Map.wz"), region="EMS", version=95) as src_wz:
        src_img = src_wz.root.get("Obj/acc14.img")
        if src_img is None:
            raise RuntimeError("missing source Obj/acc14.img")
        src_img.parse()
        dst_path = ROOT / "clien/Data/Map/Obj/acc14.img"
        dst_img = WzImage.from_bytes(dst_path.read_bytes(), key=TARGET_KEY, name=dst_path.name)
        dst_img.parse()
        for node_path, (width, height) in repairs.items():
            source = src_img.get(node_path)
            target = dst_img.get(node_path)
            if not isinstance(source, WzCanvasProperty) or not isinstance(target, WzCanvasProperty):
                raise RuntimeError(f"missing acc14 canvas {node_path}")
            image = decode_prefixed_argb4444_canvas(source, width, height)
            target.width = width
            target.height = height
            target.format = 1
            target.format2 = 0
            target._png_data = encode_canvas_payload(
                image,
                1,
                width,
                height,
                key=TARGET_KEY,
                listwz=False,
            )
            target._png_length = len(target._png_data)
        backup(dst_path)
        atomic_write_bytes(dst_path, encode_image_body(dst_img, gms_reader()))


def patch_client_mob_8850009() -> None:
    path = ROOT / "clien/Data/Mob/8850009.img"
    img = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=path.name)
    img.parse()
    skill_root = img.get("info/skill")
    if skill_root is None:
        return
    changed = False
    for entry in skill_root.children():
        skill_node = entry.child("skill")
        level_node = entry.child("level")
        if isinstance(skill_node, WzIntProperty) and isinstance(level_node, WzIntProperty):
            if int(skill_node.value) == 128 and int(level_node.value) == 128:
                level_node._value = 8
                changed = True
    if changed:
        backup(path)
        atomic_write_bytes(path, encode_image_body(img, gms_reader()))


def patch_server_mob_8850009() -> None:
    path = ROOT / "gms-server/wz/Mob.wz/8850009.img.xml"
    text = path.read_text(encoding="utf-8-sig")
    text = text.replace('<int name="skill" value="128"/>\n        <int name="action" value="2"/>\n        <int name="level" value="128"/>',
                        '<int name="skill" value="128"/>\n        <int name="action" value="2"/>\n        <int name="level" value="8"/>')
    backup(path)
    atomic_write_text(path, text)


def cygnus_quest_ids() -> list[int]:
    root = ET.parse(SRC_SERVER / "wz/Quest.wz/QuestInfo.img.xml").getroot()
    return sorted(
        int(child.get("name"))
        for child in root.findall("imgdir")
        if (child.get("name") or "").isdigit() and 31100 <= int(child.get("name")) <= 31200
    )


def patch_server_quest_xml() -> None:
    quest_ids = {str(quest_id) for quest_id in cygnus_quest_ids()}
    for img_name in QUEST_FILES:
        file_name = f"{img_name}.xml"
        src_path = SRC_SERVER / "wz/Quest.wz" / file_name
        dst_path = ROOT / "gms-server/wz/Quest.wz" / file_name
        src_root = ET.parse(src_path).getroot()
        dst_root = ET.parse(dst_path).getroot()
        for quest_id in quest_ids:
            source = direct_imgdir(src_root, quest_id)
            if source is None:
                raise RuntimeError(f"missing source server quest {img_name}/{quest_id}")
            current = direct_imgdir(dst_root, quest_id)
            if current is not None:
                dst_root.remove(current)
            dst_root.append(deepcopy(source))
        backup(dst_path)
        atomic_write_text(dst_path, mobskill_xml_text(dst_root))


def patch_client_quest_images() -> None:
    quest_ids = {str(quest_id) for quest_id in cygnus_quest_ids()}
    with WzFile.open(str(SRC_CLIENT / "Quest.wz"), region="EMS", version=95) as src_wz:
        for img_name in QUEST_FILES:
            src_img = src_wz.root.get(img_name)
            if not isinstance(src_img, WzImage):
                raise RuntimeError(f"missing source client quest image {img_name}")
            src_img.parse()

            dst_path = ROOT / "clien/Data/Quest" / img_name
            dst_img = WzImage.from_bytes(dst_path.read_bytes(), key=TARGET_KEY, name=img_name)
            dst_img.parse()
            for quest_id in quest_ids:
                source = src_img.get(quest_id)
                if source is None:
                    raise RuntimeError(f"missing source client quest {img_name}/{quest_id}")
                dst_img.root.add(clone_property(source, quest_id, dst_img.root, source_region="EMS"))
            backup(dst_path)
            atomic_write_bytes(dst_path, encode_image_body(dst_img, gms_reader()))


def patch_quest_resources() -> None:
    patch_server_quest_xml()
    patch_client_quest_images()


def main() -> int:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    if "--quests-only" in sys.argv:
        patch_quest_resources()
        print(f"Cygnus quest resources migrated. Backups: {BACKUP_ROOT}")
        return 0

    for map_id in MAP_IDS:
        copy_resource(
            SRC_SERVER / f"wz/Map.wz/Map/Map2/{map_id}.img.xml",
            ROOT / f"gms-server/wz/Map.wz/Map/Map2/{map_id}.img.xml",
        )
    for mob_id in MOB_IDS:
        copy_resource(
            SRC_SERVER / f"wz/Mob.wz/{mob_id}.img.xml",
            ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml",
        )
    patch_server_mob_skill_overrides()
    for npc_id in NPC_IDS:
        copy_resource(
            SRC_SERVER / f"wz/Npc.wz/{npc_id}.img.xml",
            ROOT / f"gms-server/wz/Npc.wz/{npc_id}.img.xml",
        )

    with WzFile.open(str(SRC_CLIENT / "Map.wz"), region="EMS", version=95) as map_wz:
        for map_id in MAP_IDS:
            export_wz_image(map_wz, f"Map/Map2/{map_id}.img", ROOT / f"clien/Data/Map/Map/Map2/{map_id}.img")
        for entry, dst in [
            ("Back/darkEreb.img", ROOT / "clien/Data/Map/Back/darkEreb.img"),
            ("Back/destructionTown.img", ROOT / "clien/Data/Map/Back/destructionTown.img"),
            ("Back/fakeDoors.img", ROOT / "clien/Data/Map/Back/fakeDoors.img"),
            ("Obj/acc14.img", ROOT / "clien/Data/Map/Obj/acc14.img"),
            ("Tile/destructionField.img", ROOT / "clien/Data/Map/Tile/destructionField.img"),
            ("Tile/destructionTown1.img", ROOT / "clien/Data/Map/Tile/destructionTown1.img"),
            ("Tile/destructionTown2.img", ROOT / "clien/Data/Map/Tile/destructionTown2.img"),
        ]:
            export_wz_image(map_wz, entry, dst)

    patch_client_wrapped_tile_canvases()
    patch_client_acc14_wrapped_canvases()
    patch_client_dark_ereb_tile()
    patch_client_maphelper_marks()

    with WzFile.open(str(SRC_CLIENT / "Mob.wz"), region="EMS", version=95) as mob_wz:
        for mob_id in MOB_IDS:
            export_wz_image(mob_wz, f"{mob_id}.img", ROOT / f"clien/Data/Mob/{mob_id}.img")
    patch_client_mob_skill_overrides()

    with WzFile.open(str(SRC_CLIENT / "Npc.wz"), region="EMS", version=95) as npc_wz:
        for npc_id in NPC_IDS:
            export_wz_image(npc_wz, f"{npc_id}.img", ROOT / f"clien/Data/Npc/{npc_id}.img")

    patch_client_connect()
    patch_direct_string_xml("Mob.img.xml", MOB_IDS + [8850013])
    patch_direct_string_xml("Npc.img.xml", NPC_IDS)
    patch_map_string_xml()
    patch_mobskill_xml()
    patch_client_string_images()
    patch_client_mobskill()
    patch_client_mob_8850009()
    patch_server_mob_8850009()
    patch_quest_resources()

    print(f"Cygnus resources migrated. Backups: {BACKUP_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
