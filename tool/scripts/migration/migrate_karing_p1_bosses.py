#!/usr/bin/env python3
"""Migrate Karing boss resources from TMS.

The default path creates standalone legacy-client Mob IMG files for the
approved Karing stages from TMS .ms metadata plus sibling _Canvas pixel data.
The explicit compatibility patch replaces or inserts only approved top-level
records in an existing generated IMG.
"""

from __future__ import annotations

import argparse
import io
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
TMS_ROOT = Path("/Users/lizixian/Documents/mxd/TMS")
PACK_ROOT = TMS_ROOT / "MapleStory/Data/Packs"
MS_PROBE = (
    TMS_ROOT
    / "black_mage_report_tools/ms_probe/bin/Debug/net8.0/MSProbe.dll"
)
SOURCE_CACHE = Path("/private/tmp/karing-mob-ms")

sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
sys.path.insert(0, str(ROOT / "tool" / "scripts" / "migration"))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzKey,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import _encode_property_list, encode_compressed_int, encode_image_body  # noqa: E402

from migrate_arcane_river_fields import (  # noqa: E402
    GMS_KEY,
    BMS_KEY,
    CanvasMaterializer,
    atomic_write_bytes,
    atomic_write_text,
    child_value,
    clone_property,
    decode_source_canvas,
    gms_reader,
    image_to_xml,
    load_image,
    property_to_xml,
    remove_child,
    set_int,
)


MOB_IDS = (8880830, 8880831, 8880832, 8880837, 8880842)
CLIENT_MAX_HP = 2_147_483_647
# TMS Mob IMG stores only the capped client value. These are the Normal-mode
# server HP values for the base level-285 monster IDs above.
TMS_NORMAL_HP = {
    8880830: 399_000_000_000_000,
    8880831: 399_000_000_000_000,
    8880832: 399_000_000_000_000,
    8880837: 468_000_000_000_000,
    8880842: 722_000_000_000_000,
}
MOB_NAMES = {
    8880830: "窮奇",
    8880831: "檮杌",
    8880832: "混沌",
    8880837: "咖凌",
    8880842: "暴走的咖凌",
}
MOB_STRING_INSERT_AFTER = {
    8880830: "8880803",
    8880831: "8880830",
    8880832: "8880831",
    8880837: "8880832",
    8880842: "8880837",
}
SOURCE_PACK = PACK_ROOT / "Mob_00000.ms"

# Keep combat and skill visuals while projecting modern FSM-only metadata onto
# contracts that the legacy client and server both understand.
LEGACY_ACTIONS_ALLOWED = {
    8880830: {
        "regen", "stand", "move", "hit1", "die1",
        "attack1", "attack2", "attack3", "attack4", "attack5",
        "skill1", "skillAfter1", "sleep", "skill2", "skillAfter2", "fly",
    },
    # Project TMS 274/3 below; MobSkill 273/4 and the remaining FSM-only
    # actions still have no proven v83 contract.
    8880837: {
        "regen", "stand", "move", "hit1", "die1",
        "attack1", "attack2", "attack3", "attack4", "attack5", "attack6",
        "skill1",
    },
    8880842: {
        "regen", "stand", "move", "hit1", "die1",
        "attack1", "attack2", "attack3", "attack4",
    },
}
LEGACY_FSM_ONLY_ACTIONS = {
    # Source facts used by the contract tests. These actions are projected
    # below instead of being removed merely because TMS marks them onlyFsm.
    8880830: {"attack4", "attack5"},
    8880832: {"attack3", "attack6"},
    8880837: {"attack3", "attack6"},
}
LEGACY_ACTION_FRAME_UOLS = {
    # Existing v83 Mob data uses the same attack -> skill-frame UOL contract.
    # TMS info/skill maps attack4 to skill1 and attack5 to skill2.
    8880830: {
        "attack4": ("skill1", None),
        "attack5": ("skill2", None),
    },
    # attack6 is an effect-only FSM attack: keep its own visible hit frames,
    # but show a stable body pose instead of its transparent 1x1 body frame.
    8880832: {
        "attack6": ("stand", ("0",)),
    },
    8880837: {
        "attack3": ("stand", ("0",)),
        "attack6": ("stand", ("0",)),
    },
}
LEGACY_EMPTY_HIT_ACTIONS = {8880830: {"attack4"}}
LEGACY_ACTION_INSERT_BEFORE = {
    8880830: {"skill1": ("attack4", "attack5")},
}
LEGACY_ACTION_RENAMES = {}
LEGACY_ACTIONS_BLOCKED = {
    8880830: {"flip"},
    8880831: {"flip"},
    8880832: {"flip"},
    8880837: {"flip"},
    8880842: {"flip", "attack5"},
}
LEGACY_ACTION_INFO_UNSUPPORTED = {"lockon"}
LEGACY_AREA_RANGES = {
    (8880830, "attack3"): ((-450, -429), (424, 11)),
    (8880832, "attack1"): ((-484, -255), (451, 3)),
}
LEGACY_CANVAS_SCALE = {
    8880830: 1.0,
    8880831: 1.0,
    8880832: 1.0,
    8880837: 1.0,
    8880842: 1.0,
}
LEGACY_MAX_CANVAS_EDGE = 2048
LEGACY_EVASION = 100
LEGACY_VIDEO_ACTIONS = {
    # Fixed-position spawn cinematics are safe to draw in the boss-scene MCV
    # channel. World-relative attacks and death actions deliberately stay WZ.
    8880837: {"regen": (13, 6660)},
    8880842: {"regen": (14, 8100)},
}
FULL_DEATH_ACTIONS = {
    8880837: (95, 8550),
    8880842: (134, 12060),
}
VIDEO_MARKER_WIDTH = 7
VIDEO_MARKER_HEIGHT = 5
# Preserve the original TMS metadata for remaining transparent timing frames.
LEGACY_MISSING_ORIGIN_PATHS = {
    8880830: {"regen/0"},
    8880831: {"regen/0"},
    8880832: {"regen/0"},
    8880837: set(),
    8880842: set(),
}
LEGACY_SYNTHESIZED_ORIGINS = {}

LEGACY_MOB_SKILLS = {
    8880830: ((128, 1, 1), (126, 7, 2)),
    8880831: ((123, 3, 1), (120, 5, 2)),
    8880832: ((132, 2, 1),),
    # TMS 274/3 drives skill1 and BossKaring/darkPulse. Reuse an existing
    # byte-sized legacy slot; the server suppresses its native disease.
    8880837: ((128, 2, 1),),
    8880842: (),
}

LEGACY_ATTACK_INFO_FIELDS = (
    "attackCount",
    "conMP",
    "electricCount",
    "fixDamR",
    "ignoreStance",
    "knockback",
    "magic",
    "notMissAttack",
    "rush",
)

LEGACY_ATTACK_DISEASES = {
    8880830: {1: (123, 3), 2: (123, 3), 3: (123, 3)},
    8880832: {1: (132, 2)},
}

KARING_INFO_UNSUPPORTED = {
    "attack",
    "category",
    "defaultHP",
    "defaultMP",
    "showNotRemoteDam",
    "isRemoteRange",
    "ignoreMoveImpact",
    "firstAttackRange",
    "delAtomOnDead",
    "ignoreFieldOut",
    "ex",
    "mobZone",
    "mobZoneType",
    "shieldEffectUOL",
    "shieldSoundUOL",
    "ignoreSlow",
    "ignoreSlowMsg",
    "moveAbility",
    "minimap",
}

OLD_SERVER_REQUIRED_FIELDS = {
    "PADamage": 22000,
    "PDDamage": 22000,
    "MADamage": 24000,
    "MDDamage": 24000,
    "level": 285,
    "maxMP": 100000,
}


class KaringCanvasMaterializer(CanvasMaterializer):
    def __init__(
        self, requested_scale: float = 1.0, synthesize_missing_origins: bool = False
    ) -> None:
        super().__init__()
        self.requested_scale = requested_scale
        self.synthesize_missing_origins = synthesize_missing_origins
        self.synthesized_origins = 0
        self.cropped = 0
        self.transparent = 0
        self.source_pixels = 0
        self.output_pixels = 0

    def materialize(
        self, source: WzCanvasProperty, parent, image: WzImage, image_path: Path
    ) -> WzCanvasProperty:
        pixel_source, pixel_image, pixel_path, pixel_property = self.resolve_canvas(
            source, image, image_path, set()
        )
        cache_key = (pixel_path.resolve(), pixel_property or f"@{id(pixel_source)}")
        decoded = self.decoded.get(cache_key)
        if decoded is None:
            decoded = decode_source_canvas(pixel_source)
            self.decoded[cache_key] = decoded

        bitmap = decoded.convert("RGBA")
        self.source_pixels += bitmap.width * bitmap.height
        crop_left = 0
        crop_top = 0
        bbox = bitmap.getchannel("A").getbbox()
        if bbox is None:
            bitmap = bitmap.crop((0, 0, 1, 1))
            self.transparent += 1
        else:
            crop_left, crop_top, crop_right, crop_bottom = bbox
            if bbox != (0, 0, bitmap.width, bitmap.height):
                bitmap = bitmap.crop(bbox)
                self.cropped += 1

        scale = min(
            self.requested_scale,
            LEGACY_MAX_CANVAS_EDGE / max(bitmap.width, bitmap.height),
        )
        if scale < 1.0:
            size = (
                max(1, round(bitmap.width * scale)),
                max(1, round(bitmap.height * scale)),
            )
            bitmap = bitmap.resize(size, resample=Image.Resampling.LANCZOS)
            self.resized += 1

        output = WzCanvasProperty(source.name, parent)
        output.width, output.height = bitmap.size
        output.format, output.format2 = 1, 0
        output._png_data = encode_canvas_payload(
            bitmap,
            1,
            bitmap.width,
            bitmap.height,
            key=GMS_KEY,
            listwz=False,
            zlib_level=6,
        )
        output._png_length = len(output._png_data)
        output._png_offset = 0

        metadata: dict[str, object] = {}
        for candidate in (pixel_source, source):
            for child in candidate.children():
                if child.name not in {"_outlink", "_inlink"}:
                    metadata[child.name] = child
        if self.synthesize_missing_origins and "origin" not in metadata:
            output.add(WzVectorProperty("origin", 0, 0, output))
            self.synthesized_origins += 1
        for child in metadata.values():
            output.add(clone_property(child, output, image, image_path, self))

        for node, _ in walk(output):
            if not isinstance(node, WzVectorProperty):
                continue
            if node.name == "origin":
                node.x -= crop_left
                node.y -= crop_top
            if scale < 1.0:
                node.x = round(int(node.x) * scale)
                node.y = round(int(node.y) * scale)

        self.output_pixels += bitmap.width * bitmap.height
        self.canvases += 1
        return output


def walk(node, path: str = ""):
    yield node, path
    if hasattr(node, "children"):
        for child in node.children():
            child_path = f"{path}/{child.name}" if path else child.name
            yield from walk(child, child_path)


def locate_root_records(
    data: bytes, path: Path
) -> tuple[int, int, tuple[str, ...], tuple[tuple[int, int], ...]]:
    reader = WzBinaryReader(io.BytesIO(data), GMS_KEY)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError(f"{path}: unsupported IMG header")
    reader.skip(2)
    count_offset = reader.position
    count = reader.read_compressed_int()
    count_end = reader.position

    names = []
    spans = []
    for _ in range(count):
        start = reader.position
        name = reader.read_string_block(0)
        tag = reader.read_byte()
        if tag != 9:
            raise RuntimeError(f"{path}: unexpected root record {name}/{tag}")
        size = reader.read_u32()
        reader.seek(reader.position + size)
        names.append(name)
        spans.append((start, reader.position))
    if reader.position != len(data):
        raise RuntimeError(f"{path}: root records do not fill IMG body")
    return count_offset, count_end, tuple(names), tuple(spans)


def encode_root_record(node) -> bytes:
    encoded = _encode_property_list((node,), gms_reader())
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError(f"{node.name}: unexpected encoded root record")
    return encoded[len(prefix):]


def patch_client_evasion_incrementally(path: Path) -> bool:
    original = path.read_bytes()
    image = WzImage.from_bytes(original, key=GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"{path}: truncated={image.truncated} warnings={image.parse_warnings}"
        )

    info = image.root.child("info")
    eva = info.child("eva") if isinstance(info, WzSubProperty) else None
    if not isinstance(eva, WzIntProperty):
        raise RuntimeError(f"{path}: missing info/eva integer")

    _, _, names, spans = locate_root_records(original, path)
    raw_records = {
        name: original[start:end] for name, (start, end) in zip(names, spans)
    }
    if encode_root_record(info) != raw_records["info"]:
        raise RuntimeError(f"{path}: info record is not reproducible")

    eva._value = LEGACY_EVASION
    encoded_info = encode_root_record(info)
    rebuilt = b"".join(
        encoded_info if name == "info" else raw_records[name]
        for name in names
    )
    records_start, records_end = spans[0][0], spans[-1][1]
    updated = original[:records_start] + rebuilt + original[records_end:]

    verified = WzImage.from_bytes(updated, key=GMS_KEY, name=path.name)
    verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise RuntimeError(
            f"{path}: evasion patch malformed: {verified.parse_warnings}"
        )
    if child_value(verified.root.child("info"), "eva") != LEGACY_EVASION:
        raise RuntimeError(f"{path}: evasion patch did not persist")

    _, _, verified_names, verified_spans = locate_root_records(updated, path)
    if verified_names != names:
        raise RuntimeError(f"{path}: root order changed during evasion patch")
    verified_raw = {
        name: updated[start:end]
        for name, (start, end) in zip(verified_names, verified_spans)
    }
    for name in names:
        expected = encoded_info if name == "info" else raw_records[name]
        if verified_raw[name] != expected:
            raise RuntimeError(f"{path}: unapproved root record changed: {name}")

    if updated != original:
        atomic_write_bytes(path, updated)
    return updated != original


def patch_server_evasion_incrementally(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    info_span = find_top_level_xml_imgdir(original, "info")
    if info_span is None:
        raise RuntimeError(f"{path}: missing info block")
    start, end = info_span
    info = original[start:end]
    marker = '<int name="eva" value="'
    value_start = info.find(marker)
    if value_start < 0 or info.find(marker, value_start + 1) >= 0:
        raise RuntimeError(f"{path}: missing or duplicate info/eva")
    value_start += len(marker)
    value_end = info.find('"/>', value_start)
    if value_end < 0:
        raise RuntimeError(f"{path}: malformed info/eva")
    patched_info = info[:value_start] + str(LEGACY_EVASION) + info[value_end:]
    updated = original[:start] + patched_info + original[end:]

    root = ET.fromstring(updated)
    parsed_info = next(child for child in root if child.get("name") == "info")
    parsed_eva = next(child for child in parsed_info if child.get("name") == "eva")
    if int(parsed_eva.get("value")) != LEGACY_EVASION:
        raise RuntimeError(f"{path}: server evasion patch did not persist")
    if updated[:start] != original[:start] or updated[start + len(patched_info):] != original[end:]:
        raise RuntimeError(f"{path}: bytes outside info changed")

    if updated != original:
        atomic_write_text(path, updated)
    return updated != original


def patch_evasion(mob_id: int) -> dict[str, bool]:
    return {
        "client": patch_client_evasion_incrementally(
            ROOT / f"clien/Data/Mob/{mob_id}.img"
        ),
        "server": patch_server_evasion_incrementally(
            ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
        ),
    }


def patch_client_hp_incrementally(path: Path) -> bool:
    original = path.read_bytes()
    image = WzImage.from_bytes(original, key=GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"{path}: truncated={image.truncated} warnings={image.parse_warnings}"
        )

    info = image.root.child("info")
    if not isinstance(info, WzSubProperty) or info.child("maxHP") is None:
        raise RuntimeError(f"{path}: missing info/maxHP")
    _, _, names, spans = locate_root_records(original, path)
    raw_records = {
        name: original[start:end] for name, (start, end) in zip(names, spans)
    }
    if encode_root_record(info) != raw_records["info"]:
        raise RuntimeError(f"{path}: info record is not reproducible")

    set_int(info, "maxHP", CLIENT_MAX_HP)
    encoded_info = encode_root_record(info)
    rebuilt = b"".join(
        encoded_info if name == "info" else raw_records[name]
        for name in names
    )
    records_start, records_end = spans[0][0], spans[-1][1]
    updated = original[:records_start] + rebuilt + original[records_end:]

    verified = WzImage.from_bytes(updated, key=GMS_KEY, name=path.name)
    verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise RuntimeError(f"{path}: HP patch malformed: {verified.parse_warnings}")
    if child_value(verified.root.child("info"), "maxHP") != CLIENT_MAX_HP:
        raise RuntimeError(f"{path}: HP patch did not persist")
    _, _, verified_names, verified_spans = locate_root_records(updated, path)
    if verified_names != names:
        raise RuntimeError(f"{path}: root order changed during HP patch")
    verified_raw = {
        name: updated[start:end]
        for name, (start, end) in zip(verified_names, verified_spans)
    }
    for name in names:
        expected = encoded_info if name == "info" else raw_records[name]
        if verified_raw[name] != expected:
            raise RuntimeError(f"{path}: unapproved root record changed: {name}")

    if updated != original:
        atomic_write_bytes(path, updated)
    return updated != original


def patch_server_hp_incrementally(path: Path, hp: int) -> bool:
    original = path.read_text(encoding="utf-8")
    info_span = find_top_level_xml_imgdir(original, "info")
    if info_span is None:
        raise RuntimeError(f"{path}: missing info block")
    start, end = info_span
    info = original[start:end]
    pattern = re.compile(r'<(?:int|long|string) name="maxHP" value="[^"]*"/>')
    patched_info, count = pattern.subn(
        f'<string name="maxHP" value="{hp}"/>', info
    )
    if count != 1:
        raise RuntimeError(f"{path}: missing or duplicate info/maxHP")
    updated = original[:start] + patched_info + original[end:]

    root = ET.fromstring(updated)
    parsed_info = next(child for child in root if child.get("name") == "info")
    parsed_hp = next(child for child in parsed_info if child.get("name") == "maxHP")
    if parsed_hp.tag != "string" or int(parsed_hp.get("value")) != hp:
        raise RuntimeError(f"{path}: server HP patch did not persist")
    if updated[:start] != original[:start] or updated[start + len(patched_info):] != original[end:]:
        raise RuntimeError(f"{path}: bytes outside info changed")

    if updated != original:
        atomic_write_text(path, updated)
    return updated != original


def patch_hp(mob_id: int) -> dict[str, bool]:
    return {
        "client": patch_client_hp_incrementally(
            ROOT / f"clien/Data/Mob/{mob_id}.img"
        ),
        "server": patch_server_hp_incrementally(
            ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml",
            TMS_NORMAL_HP[mob_id],
        ),
    }


def build_full_death_action_patch(path: Path, mob_id: int):
    original = path.read_bytes()
    image = WzImage.from_bytes(original, key=GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"{path}: truncated={image.truncated} warnings={image.parse_warnings}"
        )

    _, _, names, spans = locate_root_records(original, path)
    raw_records = {
        name: original[start:end] for name, (start, end) in zip(names, spans)
    }
    current_action = image.root.child("die1")
    if not isinstance(current_action, WzSubProperty) or "die1" not in raw_records:
        raise RuntimeError(f"{path}: missing die1 root record")
    if encode_root_record(current_action) != raw_records["die1"]:
        raise RuntimeError(f"{path}: die1 record is not reproducible")

    source_path = extract_source(mob_id)
    candidate, _ = build_client_image(source_path, mob_id)
    candidate_action = candidate.root.child("die1")
    if not isinstance(candidate_action, WzSubProperty):
        raise RuntimeError(f"{mob_id}: source projection is missing die1")

    before_xml = property_to_xml(current_action)
    encoded_action = encode_root_record(candidate_action)
    rebuilt = b"".join(
        encoded_action if name == "die1" else raw_records[name] for name in names
    )
    records_start, records_end = spans[0][0], spans[-1][1]
    updated = original[:records_start] + rebuilt + original[records_end:]

    verified = WzImage.from_bytes(updated, key=GMS_KEY, name=path.name)
    verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise RuntimeError(f"{path}: malformed full die1 {verified.parse_warnings}")
    _, _, verified_names, verified_spans = locate_root_records(updated, path)
    if verified_names != names:
        raise RuntimeError(f"{path}: root order changed during die1 restore")
    verified_raw = {
        name: updated[start:end]
        for name, (start, end) in zip(verified_names, verified_spans)
    }
    for name in names:
        expected = encoded_action if name == "die1" else raw_records[name]
        if verified_raw[name] != expected:
            raise RuntimeError(f"{path}: unapproved root record changed: {name}")

    verified_action = verified.root.child("die1")
    target_count, expected_duration = FULL_DEATH_ACTIONS[mob_id]
    verified_frames = sorted(
        (child for child in verified_action.children() if child.name.isdigit()),
        key=lambda child: int(child.name),
    )
    if len(verified_frames) != target_count:
        raise RuntimeError(f"{path}: full die1 frame count did not persist")
    duration = sum(action_frame_delay(verified_action, frame) for frame in verified_frames)
    if duration != expected_duration:
        raise RuntimeError(f"{path}: full die1 duration did not persist")
    texture_bytes = sum(
        next_power_of_two(frame.width) * next_power_of_two(frame.height) * 2
        for frame in verified_frames
        if isinstance(frame, WzCanvasProperty)
    )
    return {
        "changed": updated != original,
        "original": original,
        "updated": updated,
        "before_xml": before_xml,
        "after_xml": property_to_xml(candidate_action),
        "frames": len(verified_frames),
        "duration": duration,
        "textureMiB": round(texture_bytes / 1024 / 1024, 2),
    }


def restore_full_death_action(mob_id: int) -> dict[str, object]:
    client_path = ROOT / f"clien/Data/Mob/{mob_id}.img"
    server_path = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
    projection = build_full_death_action_patch(client_path, mob_id)

    server_original = server_path.read_text(encoding="utf-8")
    span = find_top_level_xml_imgdir(server_original, "die1")
    if span is None:
        raise RuntimeError(f"{server_path}: missing die1 block")
    start, end = span
    existing = server_original[start:end]
    before_block = projection["before_xml"] + "\n"
    after_block = projection["after_xml"] + "\n"
    if existing == after_block:
        server_updated = server_original
    elif existing == before_block:
        server_updated = server_original[:start] + after_block + server_original[end:]
    else:
        raise RuntimeError(f"{server_path}: die1 block diverged from client")
    ET.fromstring(server_updated)

    if projection["changed"]:
        atomic_write_bytes(client_path, projection["updated"])
    if server_updated != server_original:
        atomic_write_text(server_path, server_updated)
    return {
        "client": projection["changed"],
        "server": server_updated != server_original,
        "frames": projection["frames"],
        "duration": projection["duration"],
        "textureMiB": projection["textureMiB"],
    }


def build_missing_action_nodes(mob_id: int, names: set[str]) -> dict[str, WzSubProperty]:
    source_path = extract_source(mob_id)
    image = load_image(source_path, BMS_KEY)
    sanitize_mob(image.root, mob_id)
    project_legacy_action_metadata(image.root, mob_id)
    project_legacy_mob(image.root, mob_id)

    materializer = KaringCanvasMaterializer(LEGACY_CANVAS_SCALE.get(mob_id, 1.0), False)
    holder = WzSubProperty(image.root.name)
    result = {}
    for name in names:
        source = image.root.child(name)
        if not isinstance(source, WzSubProperty):
            raise RuntimeError(f"{mob_id}: missing source action {name}")
        cloned = clone_property(source, holder, image, source_path, materializer)
        if not isinstance(cloned, WzSubProperty):
            raise RuntimeError(f"{mob_id}: invalid projected action {name}")
        holder.add(cloned)
        result[name] = cloned
    return result


def insert_missing_action_nodes(
    root: WzSubProperty, mob_id: int, nodes: dict[str, WzSubProperty]
) -> dict[str, tuple[str, ...]]:
    if not nodes:
        return {}

    groups = LEGACY_ACTION_INSERT_BEFORE.get(mob_id, {})
    inserted = set()
    insert_before = {}
    ordered = {}
    for child in root.children():
        names = tuple(name for name in groups.get(child.name, ()) if name in nodes)
        if names:
            insert_before[child.name] = names
            for name in names:
                node = nodes[name]
                node.parent = root
                ordered[name] = node
                inserted.add(name)
        ordered[child.name] = child
    if inserted != set(nodes):
        raise RuntimeError(
            f"{mob_id}: no insertion anchor for {sorted(set(nodes) - inserted)}"
        )
    root._children.clear()
    root._children.update(ordered)
    return insert_before


def patch_client_compat_incrementally(path: Path, mob_id: int):
    original = path.read_bytes()
    image = WzImage.from_bytes(original, key=GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"{path}: truncated={image.truncated} warnings={image.parse_warnings}"
        )

    count_offset, count_end, names, spans = locate_root_records(original, path)
    raw_records = {
        name: original[start:end] for name, (start, end) in zip(names, spans)
    }
    source_name_by_id = {id(child): child.name for child in image.root.children()}
    before_xml = {
        child.name: property_to_xml(child)
        for child in image.root.children()
    }
    for child in image.root.children():
        encoded = encode_root_record(child)
        if encoded != raw_records[child.name]:
            raise RuntimeError(f"{path}: root record is not reproducible: {child.name}")

    required_actions = set(LEGACY_ACTION_FRAME_UOLS.get(mob_id, {}))
    missing_actions = required_actions - {
        child.name for child in image.root.children()
    }
    insert_before = insert_missing_action_nodes(
        image.root,
        mob_id,
        build_missing_action_nodes(mob_id, missing_actions),
    )
    project_legacy_action_metadata(image.root, mob_id)
    project_legacy_mob(image.root, mob_id)

    retained = []
    after_xml = {}
    source_to_target: dict[str, str | None] = {name: None for name in names}
    for child in image.root.children():
        source_name = source_name_by_id.get(id(child))
        encoded = encode_root_record(child)
        if source_name is not None and child.name == source_name and encoded == raw_records[source_name]:
            encoded = raw_records[source_name]
        retained.append((child.name, source_name, encoded))
        if source_name is not None:
            source_to_target[source_name] = child.name
        after_xml[child.name] = property_to_xml(child)

    retained_names = tuple(name for name, _, _ in retained)
    new_count = encode_compressed_int(len(retained))
    if len(new_count) != count_end - count_offset:
        raise RuntimeError(f"{path}: root count encoding size changed")

    records_start, records_end = spans[0][0], spans[-1][1]
    rebuilt = b"".join(encoded for _, _, encoded in retained)
    updated = (
        original[:count_offset]
        + new_count
        + original[count_end:records_start]
        + rebuilt
        + original[records_end:]
    )

    verified = WzImage.from_bytes(updated, key=GMS_KEY, name=path.name)
    verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise RuntimeError(
            f"{path}: incremental result malformed: {verified.parse_warnings}"
        )
    _, _, verified_names, verified_spans = locate_root_records(updated, path)
    if verified_names != retained_names:
        raise RuntimeError(f"{path}: root order changed during incremental removal")
    verified_raw = {
        name: updated[start:end]
        for name, (start, end) in zip(verified_names, verified_spans)
    }
    changed_sources = set()
    for target_name, source_name, encoded in retained:
        if verified_raw[target_name] != encoded:
            raise RuntimeError(f"{path}: projected root record mismatch: {target_name}")
        if source_name is not None and (
            target_name != source_name or encoded != raw_records[source_name]
        ):
            changed_sources.add(source_name)
    changed_sources.update(name for name, target in source_to_target.items() if target is None)
    for name in names:
        if name not in changed_sources and verified_raw[name] != raw_records[name]:
            raise RuntimeError(f"{path}: unapproved root record changed: {name}")

    if updated != original:
        atomic_write_bytes(path, updated)
    return {
        "changed": updated != original,
        "before_xml": before_xml,
        "after_xml": after_xml,
        "source_to_target": source_to_target,
        "changed_sources": changed_sources,
        "insert_before": insert_before,
        "actions": tuple(
            child.name for child in image.root.children()
            if child.name != "info" and isinstance(child, WzSubProperty)
        ),
    }


def find_top_level_xml_imgdir(text: str, name: str) -> tuple[int, int] | None:
    pos = 0
    depth = 0
    target_start = None
    target_depth = None
    while pos < len(text):
        next_open = text.find("<imgdir ", pos)
        next_close = text.find("</imgdir>", pos)
        if next_open >= 0 and (next_close < 0 or next_open < next_close):
            tag_end = text.find(">", next_open)
            if tag_end < 0:
                raise RuntimeError(f"{name}: unterminated XML opening tag")
            if depth == 1 and f'name="{name}"' in text[next_open : tag_end + 1]:
                line_start = text.rfind("\n", 0, next_open) + 1
                target_start = (
                    line_start
                    if text[line_start:next_open].strip() == ""
                    else next_open
                )
                target_depth = depth + 1
            depth += 1
            pos = tag_end + 1
        else:
            if next_close < 0:
                break
            depth -= 1
            pos = next_close + len("</imgdir>")
            if target_start is not None and depth < target_depth:
                if pos < len(text) and text[pos] == "\n":
                    pos += 1
                return target_start, pos
    if target_start is not None:
        raise RuntimeError(f"{name}: unterminated XML block")
    return None


def patch_server_actions_incrementally(path: Path, projection) -> bool:
    original = path.read_text(encoding="utf-8")
    changes = projection["changed_sources"]
    spans = {name: find_top_level_xml_imgdir(original, name) for name in changes}
    missing = {name for name, span in spans.items() if span is None}
    if missing:
        raise RuntimeError(f"{path}: missing source XML actions: {sorted(missing)}")

    replacements = {}
    for source_name in changes:
        start, end = spans[source_name]
        existing = original[start:end]
        expected_before = projection["before_xml"].get(source_name)
        if expected_before is None or existing != expected_before + "\n":
            raise RuntimeError(f"{path}: source XML block diverged: {source_name}")
        target_name = projection["source_to_target"][source_name]
        replacements[source_name] = (
            "" if target_name is None else projection["after_xml"][target_name] + "\n"
        )

    operations = [
        (spans[name][0], spans[name][1], replacements[name]) for name in changes
    ]
    for anchor, names in projection["insert_before"].items():
        anchor_span = find_top_level_xml_imgdir(original, anchor)
        if anchor_span is None:
            raise RuntimeError(f"{path}: missing XML insertion anchor {anchor}")
        if any(find_top_level_xml_imgdir(original, name) is not None for name in names):
            raise RuntimeError(f"{path}: projected XML action already exists before insertion")
        content = "".join(projection["after_xml"][name] + "\n" for name in names)
        operations.append((anchor_span[0], anchor_span[0], content))

    updated = original
    for start, end, replacement in sorted(operations, reverse=True):
        updated = updated[:start] + replacement + updated[end:]
    root = ET.fromstring(updated)
    actual_actions = tuple(child.get("name") for child in root if child.get("name") != "info")
    if actual_actions != projection["actions"]:
        raise RuntimeError(
            f"{path}: client/server action mismatch {actual_actions} != {projection['actions']}"
        )
    if updated != original:
        atomic_write_text(path, updated)
    return updated != original


def rescale_client_incrementally(path: Path, mob_id: int, write: bool = True):
    original = path.read_bytes()
    current = WzImage.from_bytes(original, key=GMS_KEY, name=path.name)
    current.parse()
    if current.truncated or current.parse_warnings:
        raise RuntimeError(
            f"{path}: truncated={current.truncated} warnings={current.parse_warnings}"
        )

    source = extract_source(mob_id)
    candidate_image, _ = build_client_image(source, mob_id)
    candidate = encode_image_body(candidate_image, gms_reader())
    candidate_check = WzImage.from_bytes(candidate, key=GMS_KEY, name=path.name)
    candidate_check.parse()
    if candidate_check.truncated or candidate_check.parse_warnings:
        raise RuntimeError(
            f"{path}: rescale candidate malformed: {candidate_check.parse_warnings}"
        )

    _, _, current_names, current_spans = locate_root_records(original, path)
    _, _, candidate_names, candidate_spans = locate_root_records(candidate, path)
    if current_names != candidate_names:
        raise RuntimeError(
            f"{path}: rescale candidate root order changed "
            f"{current_names} != {candidate_names}"
        )

    current_raw = {
        name: original[start:end]
        for name, (start, end) in zip(current_names, current_spans)
    }
    candidate_raw = {
        name: candidate[start:end]
        for name, (start, end) in zip(candidate_names, candidate_spans)
    }
    if current_raw["info"] != candidate_raw["info"]:
        raise RuntimeError(f"{path}: rescale candidate changed the info record")

    changed = tuple(
        name for name in current_names
        if current_raw[name] != candidate_raw[name]
    )
    allowed = {
        child.name
        for child in candidate_check.root.children()
        if child.name != "info"
        and any(
            isinstance(node, WzCanvasProperty)
            for node, _ in walk(child)
        )
    }
    if not set(changed) <= allowed:
        raise RuntimeError(
            f"{path}: rescale changed non-Canvas records "
            f"{sorted(set(changed) - allowed)}"
        )

    records_start, records_end = current_spans[0][0], current_spans[-1][1]
    rebuilt = b"".join(
        candidate_raw[name] if name in changed else current_raw[name]
        for name in current_names
    )
    updated = original[:records_start] + rebuilt + original[records_end:]
    verified = WzImage.from_bytes(updated, key=GMS_KEY, name=path.name)
    verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise RuntimeError(
            f"{path}: incremental rescale malformed: {verified.parse_warnings}"
        )
    _, _, verified_names, verified_spans = locate_root_records(updated, path)
    if verified_names != current_names:
        raise RuntimeError(f"{path}: root order changed during rescale")
    verified_raw = {
        name: updated[start:end]
        for name, (start, end) in zip(verified_names, verified_spans)
    }
    for name in current_names:
        expected = candidate_raw[name] if name in changed else current_raw[name]
        if verified_raw[name] != expected:
            raise RuntimeError(f"{path}: rescaled raw record mismatch: {name}")

    before_xml = {
        child.name: property_to_xml(child)
        for child in current.root.children()
        if child.name in changed
    }
    after_xml = {
        child.name: property_to_xml(child)
        for child in candidate_check.root.children()
        if child.name in changed
    }
    if write and updated != original:
        atomic_write_bytes(path, updated)
    return {
        "changed": updated != original,
        "records": changed,
        "before_xml": before_xml,
        "after_xml": after_xml,
        "updated": updated,
    }


def rescale_server_incrementally(path: Path, projection, write: bool = True):
    original = path.read_text(encoding="utf-8")
    operations = []
    for name in projection["records"]:
        span = find_top_level_xml_imgdir(original, name)
        if span is None:
            raise RuntimeError(f"{path}: missing server action {name}")
        start, end = span
        existing = original[start:end]
        expected = projection["before_xml"][name] + "\n"
        if existing != expected:
            raise RuntimeError(f"{path}: server action diverged before rescale: {name}")
        operations.append((start, end, projection["after_xml"][name] + "\n"))

    updated = original
    for start, end, replacement in sorted(operations, reverse=True):
        updated = updated[:start] + replacement + updated[end:]
    ET.fromstring(updated)
    if write and updated != original:
        atomic_write_text(path, updated)
    return {"changed": updated != original, "updated": updated}


def rescale_existing(mob_id: int) -> dict[str, object]:
    client_path = ROOT / f"clien/Data/Mob/{mob_id}.img"
    server_path = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
    projection = rescale_client_incrementally(client_path, mob_id, write=False)
    server = rescale_server_incrementally(server_path, projection, write=False)
    if projection["changed"]:
        atomic_write_bytes(client_path, projection["updated"])
    if server["changed"]:
        atomic_write_text(server_path, server["updated"])
    return {
        "client": projection["changed"],
        "server": server["changed"],
        "records": projection["records"],
    }


def build_mob_string_node(mob_id: int) -> WzSubProperty:
    node = WzSubProperty(str(mob_id))
    node.add(WzStringProperty("name", MOB_NAMES[mob_id], node))
    return node


def resolve_mob_string_anchor(existing_names: set[str], mob_id: int) -> str:
    anchor = MOB_STRING_INSERT_AFTER[mob_id]
    while anchor not in existing_names:
        try:
            anchor = MOB_STRING_INSERT_AFTER[int(anchor)]
        except (KeyError, ValueError) as exc:
            raise RuntimeError(f"{mob_id}: missing Mob string insertion anchor") from exc
    return anchor


def patch_client_mob_string_incrementally(mob_id: int) -> bool:
    path = ROOT / "clien/Data/String/Mob.img"
    original = path.read_bytes()
    image = WzImage.from_bytes(original, key=GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"{path}: truncated={image.truncated} warnings={image.parse_warnings}"
        )

    mob_name = MOB_NAMES[mob_id]
    existing = image.root.child(str(mob_id))
    if existing is not None:
        if not isinstance(existing, WzSubProperty) or child_value(existing, "name") != mob_name:
            raise RuntimeError(f"{path}: conflicting Mob string {mob_id}")
        return False

    count_offset, count_end, names, spans = locate_root_records(original, path)
    raw_records = {
        name: original[start:end] for name, (start, end) in zip(names, spans)
    }
    anchor = resolve_mob_string_anchor(set(names), mob_id)
    anchor_index = names.index(anchor)
    insert_offset = spans[anchor_index][1]
    record = encode_root_record(build_mob_string_node(mob_id))
    new_count = encode_compressed_int(len(names) + 1)
    if len(new_count) != count_end - count_offset:
        raise RuntimeError(f"{path}: root count encoding size changed")

    updated = (
        original[:count_offset]
        + new_count
        + original[count_end:insert_offset]
        + record
        + original[insert_offset:]
    )
    verified = WzImage.from_bytes(updated, key=GMS_KEY, name=path.name)
    verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise RuntimeError(
            f"{path}: incremental result malformed: {verified.parse_warnings}"
        )
    _, _, verified_names, verified_spans = locate_root_records(updated, path)
    expected_names = names[: anchor_index + 1] + (str(mob_id),) + names[anchor_index + 1 :]
    if verified_names != expected_names:
        raise RuntimeError(f"{path}: Mob string order mismatch")
    verified_raw = {
        name: updated[start:end]
        for name, (start, end) in zip(verified_names, verified_spans)
    }
    if verified_raw[str(mob_id)] != record:
        raise RuntimeError(f"{path}: inserted Mob string record mismatch")
    for name in names:
        if verified_raw[name] != raw_records[name]:
            raise RuntimeError(f"{path}: unapproved Mob string record changed: {name}")
    verified_node = verified.root.child(str(mob_id))
    if (
        not isinstance(verified_node, WzSubProperty)
        or child_value(verified_node, "name") != mob_name
    ):
        raise RuntimeError(f"{path}: inserted Mob string failed verification")

    atomic_write_bytes(path, updated)
    return True


def patch_server_mob_string_incrementally(path: Path, mob_id: int) -> bool:
    original = path.read_text(encoding="utf-8")
    mob_name = MOB_NAMES[mob_id]
    existing_span = find_top_level_xml_imgdir(original, str(mob_id))
    if existing_span is not None:
        root = ET.fromstring(original)
        existing = next(child for child in root if child.get("name") == str(mob_id))
        name_node = next((child for child in existing if child.get("name") == "name"), None)
        if name_node is None or name_node.get("value") != mob_name:
            raise RuntimeError(f"{path}: conflicting Mob string {mob_id}")
        return False

    root = ET.fromstring(original)
    existing_names = {child.get("name") for child in root}
    anchor = resolve_mob_string_anchor(existing_names, mob_id)
    anchor_span = find_top_level_xml_imgdir(original, anchor)
    if anchor_span is None:
        raise RuntimeError(f"{path}: missing Mob string insertion anchor {anchor}")
    block = property_to_xml(build_mob_string_node(mob_id)) + "\n"
    updated = original[: anchor_span[1]] + block + original[anchor_span[1] :]
    verified = ET.fromstring(updated)
    verified_node = next(
        (child for child in verified if child.get("name") == str(mob_id)), None
    )
    if verified_node is None:
        raise RuntimeError(f"{path}: inserted Mob string failed verification")
    name_node = next(
        (child for child in verified_node if child.get("name") == "name"), None
    )
    if name_node is None or name_node.get("value") != mob_name:
        raise RuntimeError(f"{path}: inserted Mob name failed verification")

    atomic_write_text(path, updated)
    return True


def patch_existing_compat(mob_id: int) -> dict[str, bool]:
    if mob_id not in MOB_IDS:
        raise RuntimeError(f"{mob_id}: no incremental compatibility patch defined")
    client_path = ROOT / f"clien/Data/Mob/{mob_id}.img"
    projection = patch_client_compat_incrementally(client_path, mob_id)
    return {
        "client": projection["changed"],
        "server": patch_server_actions_incrementally(
            ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml", projection
        ),
        "clientString": patch_client_mob_string_incrementally(mob_id),
        "serverString": patch_server_mob_string_incrementally(
            ROOT / "gms-server/wz/String.wz/Mob.img.xml", mob_id
        ),
        "serverStringZhCN": patch_server_mob_string_incrementally(
            ROOT / "gms-server/wz-zh-CN/String.wz/Mob.img.xml", mob_id
        ),
    }


def extract_source(mob_id: int) -> Path:
    SOURCE_CACHE.mkdir(parents=True, exist_ok=True)
    target = SOURCE_CACHE / f"Mob_{mob_id}.img"
    if target.exists():
        return target
    result = subprocess.run(
        [
            "dotnet",
            str(MS_PROBE),
            str(SOURCE_PACK),
            str(SOURCE_CACHE),
            f"Mob/{mob_id}.img",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not target.exists():
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return target


def sanitize_mob(root: WzSubProperty, mob_id: int) -> None:
    info = root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{root.name}: missing info")

    project_legacy_attack_contracts(root, info, mob_id)
    for name in KARING_INFO_UNSUPPORTED:
        remove_child(info, name)
    for name, value in OLD_SERVER_REQUIRED_FIELDS.items():
        if info.child(name) is None:
            set_int(info, name, value)

    # Old client/server code expects numeric mobType and old-scale evasion.
    remove_child(info, "mobType")
    set_int(info, "mobType", 1)
    set_int(info, "boss", 1)
    set_int(info, "hpTagColor", 1)
    set_int(info, "hpTagBgcolor", 5)
    set_int(info, "eva", LEGACY_EVASION)
    set_int(info, "maxHP", CLIENT_MAX_HP)
    project_legacy_skill_entries(root, info, mob_id)


def project_legacy_attack_contracts(
    root: WzSubProperty, info: WzSubProperty, mob_id: int
) -> None:
    attacks = info.child("attack")
    if not isinstance(attacks, WzSubProperty):
        return

    disease_projection = LEGACY_ATTACK_DISEASES.get(mob_id, {})
    for entry in attacks.children():
        if not entry.name.isdigit():
            continue
        attack_number = int(entry.name) + 1
        action_info = root.get(f"attack{attack_number}/info")
        if not isinstance(action_info, WzSubProperty):
            continue
        for name in LEGACY_ATTACK_INFO_FIELDS:
            value = child_value(entry, name)
            if value is not None:
                set_int(action_info, name, int(value))
        disease = disease_projection.get(attack_number)
        if disease is not None:
            set_int(action_info, "disease", disease[0])
            set_int(action_info, "level", disease[1])


def replace_child_in_order(
    parent: WzSubProperty, name: str, replacement: WzSubProperty | None
) -> None:
    ordered = {}
    for child in parent.children():
        if child.name == name:
            if replacement is not None:
                replacement.parent = parent
                ordered[replacement.name] = replacement
        else:
            ordered[child.name] = child
    parent._children.clear()
    parent._children.update(ordered)


def project_legacy_required_origins(root: WzSubProperty, mob_id: int) -> None:
    for path in LEGACY_MISSING_ORIGIN_PATHS.get(mob_id, set()):
        canvas = root.get(path)
        if not isinstance(canvas, WzCanvasProperty):
            raise RuntimeError(f"{mob_id}: missing required Canvas {path}")
        remove_child(canvas, "origin")

    for path, (x, y) in LEGACY_SYNTHESIZED_ORIGINS.get(mob_id, {}).items():
        canvas = root.get(path)
        if not isinstance(canvas, WzCanvasProperty):
            raise RuntimeError(f"{mob_id}: missing required Canvas {path}")
        origin = canvas.child("origin")
        if isinstance(origin, WzVectorProperty):
            if (int(origin.x), int(origin.y)) != (x, y):
                raise RuntimeError(f"{mob_id}: unexpected existing origin at {path}")
            continue
        if origin is not None:
            raise RuntimeError(f"{mob_id}: invalid existing origin at {path}")

        ordered = {"origin": WzVectorProperty("origin", x, y, canvas)}
        ordered.update((child.name, child) for child in canvas.children())
        canvas._children.clear()
        canvas._children.update(ordered)


def project_legacy_action_frames(root: WzSubProperty, mob_id: int) -> None:
    for action_name, (target_name, selected_frames) in LEGACY_ACTION_FRAME_UOLS.get(
        mob_id, {}
    ).items():
        action = root.child(action_name)
        target = root.child(target_name)
        if not isinstance(action, WzSubProperty) or not isinstance(target, WzSubProperty):
            raise RuntimeError(
                f"{mob_id}: missing {action_name} or UOL target {target_name}"
            )

        target_frames = tuple(
            child.name for child in target.children() if child.name.isdigit()
        )
        frame_names = target_frames if selected_frames is None else selected_frames
        if not frame_names or any(target.child(name) is None for name in frame_names):
            raise RuntimeError(
                f"{mob_id}: invalid frame projection {action_name} -> {target_name}"
            )
        expected = tuple(
            (str(index), f"../{target_name}/{frame_name}")
            for index, frame_name in enumerate(frame_names)
        )
        current = tuple(
            child for child in action.children() if child.name.isdigit()
        )
        if len(current) == len(expected) and all(
            isinstance(child, WzUolProperty)
            and child.name == name
            and str(child.value) == value
            for child, (name, value) in zip(current, expected)
        ):
            pass
        else:
            if len(current) != 1 or not isinstance(current[0], WzCanvasProperty):
                raise RuntimeError(
                    f"{mob_id}/{action_name}: unexpected source frames for UOL projection"
                )
            if int(current[0].width) != 1 or int(current[0].height) != 1:
                raise RuntimeError(
                    f"{mob_id}/{action_name}: refusing to replace a visible source frame"
                )
            ordered = {}
            inserted = False
            for child in action.children():
                if child.name.isdigit():
                    if not inserted:
                        for name, value in expected:
                            ordered[name] = WzUolProperty(name, value, action)
                        inserted = True
                    continue
                ordered[child.name] = child
            action._children.clear()
            action._children.update(ordered)

        if action_name in LEGACY_EMPTY_HIT_ACTIONS.get(mob_id, set()):
            info = action.child("info")
            if isinstance(info, WzSubProperty):
                remove_child(info, "hit")


def project_legacy_action_metadata(root: WzSubProperty, mob_id: int) -> None:
    project_legacy_required_origins(root, mob_id)
    project_legacy_action_frames(root, mob_id)
    for action in root.children():
        if not action.name.startswith("attack") or not isinstance(action, WzSubProperty):
            continue
        info = action.child("info")
        if not isinstance(info, WzSubProperty):
            continue

        area_attack = info.child("areaAttack")
        if isinstance(area_attack, WzSubProperty):
            bounds = []
            for entry in area_attack.children():
                lt = entry.child("lt")
                rb = entry.child("rb")
                if not isinstance(lt, WzVectorProperty) or not isinstance(rb, WzVectorProperty):
                    raise RuntimeError(f"{action.name}/info/areaAttack: invalid bounds")
                bounds.append((int(lt.x), int(lt.y), int(rb.x), int(rb.y)))
            if not bounds:
                raise RuntimeError(f"{action.name}/info/areaAttack: empty bounds")
            if info.child("range") is not None:
                raise RuntimeError(f"{action.name}/info: both range and areaAttack exist")
            legacy_range = WzSubProperty("range", info)
            legacy_range.add(WzVectorProperty(
                "lt", min(item[0] for item in bounds), min(item[1] for item in bounds), legacy_range
            ))
            legacy_range.add(WzVectorProperty(
                "rb", max(item[2] for item in bounds), max(item[3] for item in bounds), legacy_range
            ))
            replace_child_in_order(info, "areaAttack", legacy_range)

        for name in LEGACY_ACTION_INFO_UNSUPPORTED:
            remove_child(info, name)


def project_legacy_skill_entries(
    root: WzSubProperty, info: WzSubProperty, mob_id: int
) -> None:
    remove_child(info, "skill")
    projected = LEGACY_MOB_SKILLS.get(mob_id, ())
    if not projected:
        return

    skills = WzSubProperty("skill", info)
    for index, (skill_id, level, action) in enumerate(projected):
        if root.child(f"skill{action}") is None:
            raise RuntimeError(f"{root.name}: missing skill{action} for MobSkill {skill_id}/{level}")
        entry = WzSubProperty(str(index), skills)
        entry.add(WzIntProperty("skill", skill_id, entry))
        entry.add(WzIntProperty("level", level, entry))
        entry.add(WzIntProperty("action", action, entry))
        skills.add(entry)
    info.add(skills)


def project_legacy_mob(root: WzSubProperty, mob_id: int) -> None:
    allowed = LEGACY_ACTIONS_ALLOWED.get(mob_id)
    blocked = LEGACY_ACTIONS_BLOCKED.get(mob_id, set())

    for child in list(root.children()):
        if child.name == "info":
            continue
        if (allowed is not None and child.name not in allowed) or child.name in blocked:
            remove_child(root, child.name)

    renames = LEGACY_ACTION_RENAMES.get(mob_id, {})
    if renames:
        ordered = {}
        for child in root.children():
            target_name = renames.get(child.name, child.name)
            if target_name in ordered:
                raise RuntimeError(f"{root.name}: action rename collision at {target_name}")
            child.name = target_name
            ordered[target_name] = child
        root._children.clear()
        root._children.update(ordered)


def build_video_marker_frame(parent: WzSubProperty, marker_code: int, duration: int):
    pixels = [
        (34, 17, 68, 255),
        (68, 85, 119, 255),
        (153, 170, 187, 255),
        (204, 221, 221, 255),
        (marker_code * 17, 85, 187, 255),
    ] + [(0, 0, 0, 0)] * (VIDEO_MARKER_WIDTH * VIDEO_MARKER_HEIGHT - 5)
    bitmap = Image.new("RGBA", (VIDEO_MARKER_WIDTH, VIDEO_MARKER_HEIGHT))
    bitmap.putdata(pixels)
    frame = WzCanvasProperty("0", parent)
    frame.width = VIDEO_MARKER_WIDTH
    frame.height = VIDEO_MARKER_HEIGHT
    frame.format = 1
    frame.format2 = 0
    frame._png_data = encode_canvas_payload(
        bitmap,
        1,
        VIDEO_MARKER_WIDTH,
        VIDEO_MARKER_HEIGHT,
        key=GMS_KEY,
        listwz=False,
        zlib_level=9,
    )
    frame._png_length = len(frame._png_data)
    frame._png_offset = 0
    frame.add(WzVectorProperty(
        "origin", VIDEO_MARKER_WIDTH // 2, VIDEO_MARKER_HEIGHT // 2, frame
    ))
    frame.add(WzIntProperty("delay", duration, frame))
    frame.add(WzIntProperty("z", 0, frame))
    bitmap.close()
    return frame


def project_video_actions(root: WzSubProperty, mob_id: int) -> None:
    for action_name, (marker_code, duration) in LEGACY_VIDEO_ACTIONS.get(mob_id, {}).items():
        action = root.child(action_name)
        if not isinstance(action, WzSubProperty):
            raise RuntimeError(f"{mob_id}: missing MCV action {action_name}")
        ordered = {}
        inserted = False
        for child in action.children():
            if child.name.isdigit():
                if not inserted:
                    marker = build_video_marker_frame(action, marker_code, duration)
                    ordered[marker.name] = marker
                    inserted = True
                continue
            ordered[child.name] = child
        if not inserted:
            raise RuntimeError(f"{mob_id}: MCV action {action_name} has no source frames")
        action._children.clear()
        action._children.update(ordered)


def trim_video_actions_before_clone(root: WzSubProperty, mob_id: int) -> None:
    for action_name in LEGACY_VIDEO_ACTIONS.get(mob_id, {}):
        action = root.child(action_name)
        if not isinstance(action, WzSubProperty):
            raise RuntimeError(f"{mob_id}: missing MCV action {action_name}")
        numeric = [child for child in action.children() if child.name.isdigit()]
        if not numeric:
            raise RuntimeError(f"{mob_id}: MCV action {action_name} has no source frames")
        for child in numeric[1:]:
            remove_child(action, child.name)


def action_frame_delay(action: WzSubProperty, frame) -> int:
    resolved = frame
    seen = set()
    while isinstance(resolved, WzUolProperty):
        if id(resolved) in seen:
            raise RuntimeError(f"{action.name}: cyclic frame UOL {resolved.name}")
        seen.add(id(resolved))
        resolved = action.get(str(resolved.value))
    if not isinstance(resolved, WzCanvasProperty):
        raise RuntimeError(f"{action.name}: unresolved frame {frame.name}")
    delay = resolved.child("delay")
    return int(delay.value) if isinstance(delay, WzIntProperty) else 0


def action_frame_counts(image: WzImage) -> dict[str, int]:
    counts: dict[str, int] = {}
    for child in image.root.children():
        if child.name == "info" or not isinstance(child, WzSubProperty):
            continue
        count = sum(1 for entry in child.children() if entry.name.isdigit())
        counts[child.name] = count
    return counts


def projected_action_frame_counts(mob_id: int, counts: dict[str, int]) -> dict[str, int]:
    allowed = LEGACY_ACTIONS_ALLOWED.get(mob_id)
    blocked = LEGACY_ACTIONS_BLOCKED.get(mob_id, set())
    renames = LEGACY_ACTION_RENAMES.get(mob_id, {})
    projected = {}
    for name, count in counts.items():
        if (allowed is not None and name not in allowed) or name in blocked:
            continue
        target_name = renames.get(name, name)
        if target_name in projected:
            raise RuntimeError(f"{mob_id}: projected action collision at {target_name}")
        projected[target_name] = count
    for action_name, (target_name, selected_frames) in LEGACY_ACTION_FRAME_UOLS.get(
        mob_id, {}
    ).items():
        if target_name not in counts:
            raise RuntimeError(f"{mob_id}: missing projected frame source {target_name}")
        projected[action_name] = (
            counts[target_name] if selected_frames is None else len(selected_frames)
        )
    for action_name in LEGACY_VIDEO_ACTIONS.get(mob_id, {}):
        projected[action_name] = 1
    return projected


def build_client_image(source_path: Path, mob_id: int) -> tuple[WzImage, KaringCanvasMaterializer]:
    image = load_image(source_path, BMS_KEY)
    sanitize_mob(image.root, mob_id)
    project_legacy_action_metadata(image.root, mob_id)
    project_legacy_mob(image.root, mob_id)
    trim_video_actions_before_clone(image.root, mob_id)
    materializer = KaringCanvasMaterializer(
        LEGACY_CANVAS_SCALE.get(mob_id, 1.0),
        False,
    )
    root = WzSubProperty(image.root.name)
    for child in image.root.children():
        root.add(clone_property(child, root, image, source_path, materializer))
    image._root = root
    image._parsed = True
    project_video_actions(image.root, mob_id)
    return image, materializer


def next_power_of_two(value: int) -> int:
    return 1 << (max(1, value) - 1).bit_length()


def verify_client_image(
    mob_id: int, path: Path, expected_actions: dict[str, int]
) -> dict[str, int | float]:
    image = WzImage.from_bytes(path.read_bytes(), key=GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"{path}: truncated={image.truncated} warnings={image.parse_warnings}"
        )

    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{path}: missing info")
    if child_value(info, "eva") != LEGACY_EVASION:
        raise RuntimeError(f"{path}: info/eva is not {LEGACY_EVASION}")
    for name in KARING_INFO_UNSUPPORTED:
        if info.child(name) is not None:
            raise RuntimeError(f"{path}: unsupported info/{name} remains")

    actual_actions = action_frame_counts(image)
    if actual_actions != expected_actions:
        raise RuntimeError(
            f"{path}: action frame mismatch expected={expected_actions} actual={actual_actions}"
        )
    attack_numbers = sorted(
        int(name.removeprefix("attack"))
        for name in actual_actions
        if name.startswith("attack") and name.removeprefix("attack").isdigit()
    )
    if attack_numbers != list(range(1, len(attack_numbers) + 1)):
        raise RuntimeError(f"{path}: non-contiguous attacks {attack_numbers}")
    for action_name in (name for name in actual_actions if name.startswith("attack")):
        action_info = image.root.get(f"{action_name}/info")
        if isinstance(action_info, WzSubProperty) and (
            action_info.child("areaAttack") is not None
            or any(
                action_info.child(name) is not None
                for name in LEGACY_ACTION_INFO_UNSUPPORTED
            )
        ):
            raise RuntimeError(f"{path}: unsupported metadata remains in {action_name}")

    for (range_mob_id, action_name), (expected_lt, expected_rb) in LEGACY_AREA_RANGES.items():
        if range_mob_id != mob_id:
            continue
        action_info = image.root.get(f"{action_name}/info")
        legacy_range = action_info.child("range") if isinstance(action_info, WzSubProperty) else None
        if not isinstance(legacy_range, WzSubProperty):
            raise RuntimeError(f"{path}: missing {action_name}/info/range projection")
        lt = legacy_range.child("lt")
        rb = legacy_range.child("rb")
        if not isinstance(lt, WzVectorProperty) or not isinstance(rb, WzVectorProperty):
            raise RuntimeError(f"{path}: invalid {action_name}/info/range projection")
        if (int(lt.x), int(lt.y)) != expected_lt or (int(rb.x), int(rb.y)) != expected_rb:
            raise RuntimeError(f"{path}: changed {action_name}/info/range bounds")

    for action_name, (target_name, selected_frames) in LEGACY_ACTION_FRAME_UOLS.get(
        mob_id, {}
    ).items():
        action = image.root.child(action_name)
        target = image.root.child(target_name)
        if not isinstance(action, WzSubProperty) or not isinstance(target, WzSubProperty):
            raise RuntimeError(f"{path}: missing projected UOL action {action_name}")
        target_frames = tuple(
            child.name for child in target.children() if child.name.isdigit()
        )
        frame_names = target_frames if selected_frames is None else selected_frames
        frames = tuple(child for child in action.children() if child.name.isdigit())
        expected_uols = tuple(
            f"../{target_name}/{frame_name}" for frame_name in frame_names
        )
        if len(frames) != len(expected_uols) or any(
            not isinstance(frame, WzUolProperty)
            or str(frame.value) != expected_uol
            for frame, expected_uol in zip(frames, expected_uols)
        ):
            raise RuntimeError(f"{path}: invalid {action_name} UOL frame projection")
        resolved = [frame.parent.get(str(frame.value)) for frame in frames]
        if not all(isinstance(frame, WzCanvasProperty) for frame in resolved):
            raise RuntimeError(f"{path}: unresolved {action_name} UOL frame")
        if not any(
            decode_canvas(frame, region="GMS").convert("RGBA").getbbox() is not None
            for frame in resolved
        ):
            raise RuntimeError(f"{path}: {action_name} UOL frames are all transparent")

    for action_name, (marker_code, duration) in LEGACY_VIDEO_ACTIONS.get(mob_id, {}).items():
        action = image.root.child(action_name)
        frames = tuple(
            child for child in action.children()
            if child.name.isdigit()
        ) if isinstance(action, WzSubProperty) else ()
        if len(frames) != 1 or not isinstance(frames[0], WzCanvasProperty):
            raise RuntimeError(f"{path}: invalid MCV marker action {action_name}")
        frame = frames[0]
        if int(frame.width) != VIDEO_MARKER_WIDTH or int(frame.height) != VIDEO_MARKER_HEIGHT:
            raise RuntimeError(f"{path}: invalid MCV marker size {action_name}")
        delay = frame.child("delay")
        if not isinstance(delay, WzIntProperty) or int(delay.value) != duration:
            raise RuntimeError(f"{path}: invalid MCV marker duration {action_name}")
        bitmap = decode_canvas(frame, region="GMS").convert("RGBA")
        expected_code = marker_code * 17
        if list(bitmap.getdata())[4] != (expected_code, 85, 187, 255):
            raise RuntimeError(f"{path}: invalid MCV marker code {action_name}")
        bitmap.close()

    skill_root = info.child("skill")
    actual_skills = []
    if isinstance(skill_root, WzSubProperty):
        actual_skills = [
            (
                int(child_value(entry, "skill")),
                int(child_value(entry, "level")),
                int(child_value(entry, "action")),
            )
            for entry in skill_root.children()
        ]
    if actual_skills != list(LEGACY_MOB_SKILLS.get(mob_id, ())):
        raise RuntimeError(
            f"{path}: MobSkill mismatch expected={LEGACY_MOB_SKILLS.get(mob_id, ())} "
            f"actual={actual_skills}"
        )

    canvases = 0
    visible = 0
    resized = 0
    texture_bytes = 0
    missing_origins = set()
    for node, prop_path in walk(image.root):
        if not isinstance(node, WzCanvasProperty):
            continue
        canvases += 1
        if int(node.format) != 1 or int(node.format2) != 0:
            raise RuntimeError(f"{path}:{prop_path}: not ARGB4444 GMS Canvas")
        if (
            int(node.width) > LEGACY_MAX_CANVAS_EDGE
            or int(node.height) > LEGACY_MAX_CANVAS_EDGE
        ):
            raise RuntimeError(f"{path}:{prop_path}: oversized {node.width}x{node.height}")
        if node.child("origin") is None:
            missing_origins.add(prop_path)
        texture_bytes += (
            next_power_of_two(int(node.width))
            * next_power_of_two(int(node.height))
            * 2
        )
        bitmap = decode_canvas(node, region="GMS").convert("RGBA")
        if bitmap.getbbox() is not None:
            visible += 1
        if int(node.width) == 2048 or int(node.height) == 2048:
            resized += 1

    if canvases == 0 or visible == 0:
        raise RuntimeError(f"{path}: no visible Canvas payloads decoded")
    expected_missing_origins = LEGACY_MISSING_ORIGIN_PATHS.get(mob_id, set())
    if missing_origins != expected_missing_origins:
        raise RuntimeError(
            f"{path}: missing-origin paths changed "
            f"expected={sorted(expected_missing_origins)} actual={sorted(missing_origins)}"
        )
    return {
        "canvases": canvases,
        "visible": visible,
        "edge2048": resized,
        "textureMiB": round(texture_bytes / 1024 / 1024, 2),
    }


def migrate_one(mob_id: int) -> dict[str, int | float]:
    source = extract_source(mob_id)
    raw_source = WzImage.from_bytes(source.read_bytes(), key=WzKey.for_region("BMS"), name=source.name)
    raw_source.parse()
    if raw_source.truncated or raw_source.parse_warnings:
        raise RuntimeError(
            f"{source}: truncated={raw_source.truncated} warnings={raw_source.parse_warnings}"
        )
    expected_actions = projected_action_frame_counts(mob_id, action_frame_counts(raw_source))

    image, materializer = build_client_image(source, mob_id)
    client_path = ROOT / f"clien/Data/Mob/{mob_id}.img"
    server_path = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"

    atomic_write_bytes(client_path, encode_image_body(image, gms_reader()))
    atomic_write_text(server_path, image_to_xml(image, f"{mob_id}.img"))
    patch_client_mob_string_incrementally(mob_id)
    patch_server_mob_string_incrementally(
        ROOT / "gms-server/wz/String.wz/Mob.img.xml", mob_id
    )
    patch_server_mob_string_incrementally(
        ROOT / "gms-server/wz-zh-CN/String.wz/Mob.img.xml", mob_id
    )
    verified = verify_client_image(mob_id, client_path, expected_actions)
    return {
        "canvases": verified["canvases"],
        "visible": verified["visible"],
        "edge2048": verified["edge2048"],
        "textureMiB": verified["textureMiB"],
        "synthesizedOrigins": materializer.synthesized_origins,
        "links": materializer.links,
        "cropped": materializer.cropped,
        "resized": materializer.resized,
        "sourceMiPx": round(materializer.source_pixels / 1024 / 1024, 2),
        "outputMiPx": round(materializer.output_pixels / 1024 / 1024, 2),
        "bytes": client_path.stat().st_size,
    }


def verify_existing() -> dict[int, dict[str, int | float]]:
    results = {}
    for mob_id in MOB_IDS:
        source = extract_source(mob_id)
        raw_source = WzImage.from_bytes(source.read_bytes(), key=WzKey.for_region("BMS"), name=source.name)
        raw_source.parse()
        results[mob_id] = verify_client_image(
            mob_id,
            ROOT / f"clien/Data/Mob/{mob_id}.img",
            projected_action_frame_counts(mob_id, action_frame_counts(raw_source)),
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--patch-existing-compat", action="store_true")
    parser.add_argument("--patch-evasion", action="store_true")
    parser.add_argument("--patch-hp", action="store_true")
    parser.add_argument("--restore-full-death-action", action="store_true")
    parser.add_argument("--rescale-existing", action="store_true")
    parser.add_argument("--mob-id", type=int, choices=MOB_IDS)
    args = parser.parse_args()

    if not SOURCE_PACK.exists() or not MS_PROBE.exists():
        raise SystemExit("missing TMS Mob_00000.ms or MSProbe")

    if args.patch_existing_compat:
        if args.mob_id is None:
            raise SystemExit("--patch-existing-compat requires --mob-id")
        print(f"{args.mob_id}: incremental {patch_existing_compat(args.mob_id)}")
        return 0

    if args.patch_evasion:
        ids = (args.mob_id,) if args.mob_id else MOB_IDS
        for mob_id in ids:
            print(f"{mob_id}: evasion {patch_evasion(mob_id)}")
        return 0

    if args.patch_hp:
        ids = (args.mob_id,) if args.mob_id else MOB_IDS
        for mob_id in ids:
            print(f"{mob_id}: hp {patch_hp(mob_id)}")
        return 0

    if args.restore_full_death_action:
        ids = (args.mob_id,) if args.mob_id else tuple(FULL_DEATH_ACTIONS)
        unsupported = set(ids) - set(FULL_DEATH_ACTIONS)
        if unsupported:
            raise SystemExit(
                f"no full death action for {sorted(unsupported)}"
            )
        for mob_id in ids:
            print(f"{mob_id}: die1 {restore_full_death_action(mob_id)}")
        return 0

    if args.rescale_existing:
        if args.mob_id is None:
            raise SystemExit("--rescale-existing requires --mob-id")
        print(f"{args.mob_id}: rescale {rescale_existing(args.mob_id)}")
        return 0

    if args.verify_only:
        ids = (args.mob_id,) if args.mob_id else MOB_IDS
        for mob_id in ids:
            source = extract_source(mob_id)
            raw_source = WzImage.from_bytes(
                source.read_bytes(), key=WzKey.for_region("BMS"), name=source.name
            )
            raw_source.parse()
            stats = verify_client_image(
                mob_id,
                ROOT / f"clien/Data/Mob/{mob_id}.img",
                projected_action_frame_counts(mob_id, action_frame_counts(raw_source)),
            )
            print(f"{mob_id}: verify {stats}", flush=True)
        return 0

    ids = (args.mob_id,) if args.mob_id else MOB_IDS
    for mob_id in ids:
        stats = migrate_one(mob_id)
        print(f"{mob_id}: {stats}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
