#!/usr/bin/env python3
"""Set Hero Brandish's hit count to four."""

from __future__ import annotations

import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import WzImage, WzIntProperty, WzKey, WzStringProperty  # noqa: E402
from wzpy.writer import encode_compressed_int, re_encrypt_string  # noqa: E402


CLIENT_PATH = ROOT / "clien/Data/Skill/112.img"
SERVER_PATH = ROOT / "gms-server/wz/Skill.wz/112.img.xml"
CLIENT_STRING_PATH = ROOT / "clien/Data/String/Skill.img"
SERVER_STRING_PATHS = (
    ROOT / "gms-server/wz/String.wz/Skill.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Skill.img.xml",
)
SKILL_ID = 1121008
LEVELS = tuple(range(1, 31))
TARGET_HITS = 4
OLD_DESCRIPTION = "连续攻击2次前面的敌人。"
NEW_DESCRIPTION = "连续攻击4次前面的敌人。"
KEY = WzKey.for_region("GMS")


def atomic_write(path: Path, data: bytes | str) -> None:
    binary = isinstance(data, bytes)
    kwargs = {} if binary else {"encoding": "utf-8"}
    mode = "wb" if binary else "w"
    with tempfile.NamedTemporaryFile(mode, dir=path.parent, delete=False, **kwargs) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def load_client() -> WzImage:
    image = WzImage.from_bytes(CLIENT_PATH.read_bytes(), key=KEY, name=CLIENT_PATH.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise ValueError(f"cannot safely patch {CLIENT_PATH}: {image.parse_warnings}")
    return image


def find_imgdir_block(text: str, node_name: str) -> tuple[int, int]:
    opening = re.compile(rf'<imgdir\b[^>]*\bname="{re.escape(node_name)}"[^>]*>')
    match = opening.search(text)
    if match is None:
        raise ValueError(f"missing XML imgdir {node_name}")
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
    raise ValueError(f"unterminated XML imgdir {node_name}")


def patch_client() -> int:
    image = load_client()
    data = bytearray(CLIENT_PATH.read_bytes())
    changed = 0
    encoded = encode_compressed_int(TARGET_HITS)
    for level in LEVELS:
        path = f"skill/{SKILL_ID}/level/{level}/attackCount"
        node = image.root.get(path)
        if not isinstance(node, WzIntProperty):
            raise ValueError(f"client is missing {path}")
        if int(node.value) not in (2, TARGET_HITS):
            raise ValueError(f"client {path} has unexpected value {node.value}")
        if node._value_offset is None or node._value_length != len(encoded):
            raise ValueError(f"client {path} cannot be patched in place")
        if int(node.value) != TARGET_HITS:
            start = int(node._value_offset)
            data[start:start + len(encoded)] = encoded
            changed += 1
    if changed:
        atomic_write(CLIENT_PATH, bytes(data))
    return changed


def patch_server() -> int:
    text = SERVER_PATH.read_text(encoding="utf-8")
    start, end = find_imgdir_block(text, str(SKILL_ID))
    block = text[start:end]
    pattern = re.compile(r'(<int name="attackCount" value=")(2|4)("\s*/>)')
    matches = list(pattern.finditer(block))
    if len(matches) != len(LEVELS):
        raise ValueError(
            f"server skill {SKILL_ID} expected {len(LEVELS)} attackCount nodes, got {len(matches)}"
        )
    changed = sum(match.group(2) != str(TARGET_HITS) for match in matches)
    block = pattern.sub(rf"\g<1>{TARGET_HITS}\g<3>", block)
    text = text[:start] + block + text[end:]
    ET.fromstring(text)
    if changed:
        atomic_write(SERVER_PATH, text)
    return changed


def patch_client_description() -> int:
    data = bytearray(CLIENT_STRING_PATH.read_bytes())
    image = WzImage.from_bytes(bytes(data), key=KEY, name=CLIENT_STRING_PATH.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise ValueError(f"cannot safely patch {CLIENT_STRING_PATH}: {image.parse_warnings}")
    node = image.root.get(f"{SKILL_ID}/desc")
    if not isinstance(node, WzStringProperty):
        raise ValueError(f"client is missing string {SKILL_ID}/desc")
    if str(node.value) not in (OLD_DESCRIPTION, NEW_DESCRIPTION):
        raise ValueError(f"client description has unexpected value {node.value!r}")
    if str(node.value) == NEW_DESCRIPTION:
        return 0
    if node._payload_offset is None or node._payload_length is None or node._encoding is None:
        raise ValueError("client description cannot be patched in place")
    encoded = re_encrypt_string(image.wz_file.reader, NEW_DESCRIPTION, node._encoding)
    if len(encoded) != node._payload_length:
        raise ValueError("client description replacement has a different encoded length")
    start = int(node._payload_offset)
    data[start:start + len(encoded)] = encoded
    atomic_write(CLIENT_STRING_PATH, bytes(data))
    return 1


def patch_server_descriptions() -> int:
    changed = 0
    for path in SERVER_STRING_PATHS:
        text = path.read_text(encoding="utf-8")
        start, end = find_imgdir_block(text, str(SKILL_ID))
        block = text[start:end]
        old = f'<string name="desc" value="{OLD_DESCRIPTION}"'
        new = f'<string name="desc" value="{NEW_DESCRIPTION}"'
        if old in block:
            block = block.replace(old, new, 1)
            text = text[:start] + block + text[end:]
            ET.fromstring(text)
            atomic_write(path, text)
            changed += 1
        elif new not in block:
            raise ValueError(f"server description has unexpected value in {path}")
    return changed


def verify() -> None:
    client = load_client()
    server = ET.parse(SERVER_PATH).getroot()
    server_skill = server.find(f'./imgdir[@name="skill"]/imgdir[@name="{SKILL_ID}"]')
    if server_skill is None:
        raise ValueError(f"server is missing skill {SKILL_ID}")
    for level in LEVELS:
        client_node = client.root.get(f"skill/{SKILL_ID}/level/{level}/attackCount")
        if not isinstance(client_node, WzIntProperty) or int(client_node.value) != TARGET_HITS:
            raise ValueError(f"client verification failed for {SKILL_ID}/{level}")
        server_node = server_skill.find(
            f'./imgdir[@name="level"]/imgdir[@name="{level}"]/int[@name="attackCount"]'
        )
        if server_node is None or int(server_node.get("value", "-1")) != TARGET_HITS:
            raise ValueError(f"server verification failed for {SKILL_ID}/{level}")
    client_string = WzImage.from_bytes(
        CLIENT_STRING_PATH.read_bytes(), key=KEY, name=CLIENT_STRING_PATH.name
    )
    client_string.parse()
    client_description = client_string.root.get(f"{SKILL_ID}/desc")
    if not isinstance(client_description, WzStringProperty):
        raise ValueError(f"client is missing string {SKILL_ID}/desc")
    if str(client_description.value) != NEW_DESCRIPTION:
        raise ValueError(f"client description verification failed for {SKILL_ID}")
    for path in SERVER_STRING_PATHS:
        description = ET.parse(path).getroot().find(
            f'./imgdir[@name="{SKILL_ID}"]/string[@name="desc"]'
        )
        if description is None or description.get("value") != NEW_DESCRIPTION:
            raise ValueError(f"server description verification failed in {path}")


def main() -> int:
    client_changed = patch_client()
    server_changed = patch_server()
    client_description_changed = patch_client_description()
    server_descriptions_changed = patch_server_descriptions()
    verify()
    print(
        "hero Brandish hit patch ok: "
        f"skill={SKILL_ID} levels={len(LEVELS)} hits={TARGET_HITS} "
        f"client_changed={client_changed} server_changed={server_changed} "
        f"client_description_changed={client_description_changed} "
        f"server_descriptions_changed={server_descriptions_changed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
