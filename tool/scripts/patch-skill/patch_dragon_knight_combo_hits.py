#!/usr/bin/env python3
"""Set Dragon Knight spear/pole-arm crusher hit counts to six."""

from __future__ import annotations

import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import WzImage, WzIntProperty, WzKey  # noqa: E402
from wzpy.writer import encode_compressed_int  # noqa: E402


CLIENT_PATH = ROOT / "clien/Data/Skill/131.img"
SERVER_PATH = ROOT / "gms-server/wz/Skill.wz/131.img.xml"
SKILL_IDS = (1311001, 1311002)
LEVELS = tuple(range(1, 31))
TARGET_HITS = 6
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


def find_imgdir_block(text: str, node_name: str, start: int = 0) -> tuple[int, int]:
    opening = re.compile(rf'<imgdir\b[^>]*\bname="{re.escape(node_name)}"[^>]*>')
    match = opening.search(text, start)
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
    for skill_id in SKILL_IDS:
        for level in LEVELS:
            path = f"skill/{skill_id}/level/{level}/attackCount"
            node = image.root.get(path)
            if not isinstance(node, WzIntProperty):
                raise ValueError(f"client is missing {path}")
            if int(node.value) not in (3, TARGET_HITS):
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
    changed = 0
    for skill_id in SKILL_IDS:
        start, end = find_imgdir_block(text, str(skill_id))
        block = text[start:end]
        pattern = re.compile(r'(<int name="attackCount" value=")(3|6)("/>)')
        matches = list(pattern.finditer(block))
        if len(matches) != len(LEVELS):
            raise ValueError(
                f"server skill {skill_id} expected {len(LEVELS)} attackCount nodes, got {len(matches)}"
            )
        changed += sum(match.group(2) != str(TARGET_HITS) for match in matches)
        block = pattern.sub(rf"\g<1>{TARGET_HITS}\g<3>", block)
        text = text[:start] + block + text[end:]
    ET.fromstring(text)
    if changed:
        atomic_write(SERVER_PATH, text)
    return changed


def verify() -> None:
    client = load_client()
    server = ET.parse(SERVER_PATH).getroot()
    for skill_id in SKILL_IDS:
        server_skill = server.find(f'./imgdir[@name="skill"]/imgdir[@name="{skill_id}"]')
        if server_skill is None:
            raise ValueError(f"server is missing skill {skill_id}")
        for level in LEVELS:
            client_node = client.root.get(f"skill/{skill_id}/level/{level}/attackCount")
            if not isinstance(client_node, WzIntProperty) or int(client_node.value) != TARGET_HITS:
                raise ValueError(f"client verification failed for {skill_id}/{level}")
            server_node = server_skill.find(
                f'./imgdir[@name="level"]/imgdir[@name="{level}"]/int[@name="attackCount"]'
            )
            if server_node is None or int(server_node.get("value", "-1")) != TARGET_HITS:
                raise ValueError(f"server verification failed for {skill_id}/{level}")


def main() -> int:
    client_changed = patch_client()
    server_changed = patch_server()
    verify()
    print(
        "dragon knight combo hit patch ok: "
        f"skills={len(SKILL_IDS)} levels={len(LEVELS)} hits={TARGET_HITS} "
        f"client_changed={client_changed} server_changed={server_changed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
