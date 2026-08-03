#!/usr/bin/env python3
"""Restore the old-client-compatible connect.img rope/59 subtree.

The Root Abyss migration used to re-encode all of connect.img while importing
rope/59 from a newer client.  This tool restores only that one extended block
from the repository's stable HEAD version.  The replacement remains exactly
the same length as the current block, so offsets used by every other property
stay unchanged.
"""

from __future__ import annotations

import hashlib
import io
import re
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzConvexProperty,
    WzImage,
    WzKey,
    WzSubProperty,
)
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import _encode_property_body  # noqa: E402


CLIENT_REL = Path("clien/Data/Map/Obj/connect.img")
SERVER_REL = Path("gms-server/wz/Map.wz/Obj/connect.img.xml")
BACKUP_ROOT = Path("/private/tmp/beidou-105200000-connect-repair")
TARGET_KEY = WzKey.for_region("GMS")
IMGDIR_TAG_RE = re.compile(r"</?imgdir\b[^>]*?/?>")
EXPECTED_CANVASES = {
    "0": (18, 41),
    "1": (17, 30),
    "2": (17, 39),
    "3": (26, 120),
}


@dataclass(frozen=True)
class ExtendedSpan:
    start: int
    size_offset: int
    body_start: int
    end: int
    block_size: int


def git_head_bytes(path: Path) -> bytes:
    return subprocess.check_output(
        ["git", "show", f"HEAD:{path.as_posix()}"], cwd=ROOT
    )


def atomic_write_bytes(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(
        "wb", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
    ) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def atomic_write_text(path: Path, text: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", prefix=f".{path.name}.", suffix=".tmp",
        dir=path.parent, delete=False,
    ) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def backup(path: Path) -> None:
    destination = BACKUP_ROOT / path.relative_to(ROOT)
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(path.read_bytes())


def skip_basic_property(reader: WzBinaryReader, base_offset: int, tag: int) -> None:
    if tag == 0:
        return
    if tag in (2, 11):
        reader.skip(2)
        return
    if tag in (3, 19):
        reader.read_compressed_int()
        return
    if tag == 20:
        reader.read_compressed_long()
        return
    if tag == 4:
        if reader.read_byte() == 0x80:
            reader.skip(4)
        return
    if tag == 5:
        reader.skip(8)
        return
    if tag == 8:
        reader.read_string_block(base_offset)
        return
    raise ValueError(f"unsupported property tag {tag} at 0x{reader.position - 1:X}")


def find_extended_child(
    reader: WzBinaryReader, base_offset: int, wanted: str
) -> ExtendedSpan:
    count = reader.read_compressed_int()
    for _ in range(count):
        start = reader.position
        name = reader.read_string_block(base_offset)
        tag = reader.read_byte()
        if tag != 9:
            skip_basic_property(reader, base_offset, tag)
            continue
        size_offset = reader.position
        block_size = reader.read_u32()
        body_start = reader.position
        end = body_start + block_size
        if end > len(reader._stream.getbuffer()):
            raise ValueError(f"extended property {name!r} exceeds the IMG boundary")
        if name == wanted:
            return ExtendedSpan(start, size_offset, body_start, end, block_size)
        reader.seek(end)
    raise KeyError(f"missing extended property {wanted!r}")


def locate_rope59(data: bytes) -> ExtendedSpan:
    reader = WzBinaryReader(io.BytesIO(data), TARGET_KEY)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise ValueError("connect.img does not have a Property image header")
    reader.skip(2)
    rope = find_extended_child(reader, 0, "rope")
    reader.seek(rope.body_start)
    if reader.read_string_block(0) != "Property":
        raise ValueError("connect.img/rope is not a Property block")
    reader.skip(2)
    rope59 = find_extended_child(reader, 0, "59")
    if rope59.end > rope.end:
        raise ValueError("connect.img/rope/59 exceeds its parent block")
    return rope59


def parse_rope59(data: bytes) -> WzSubProperty:
    image = WzImage.from_bytes(data, key=TARGET_KEY, name="connect.img")
    image.parse()
    prop = image.get("rope/59")
    if image.truncated or not isinstance(prop, WzSubProperty):
        raise ValueError("could not parse connect.img/rope/59")
    return prop


def canvas_digest(canvas: WzCanvasProperty) -> str:
    image = decode_canvas(canvas, region="GMS").convert("RGBA")
    return hashlib.sha256(image.tobytes()).hexdigest()


def rope59_signature(prop: WzSubProperty) -> tuple:
    canvases = []
    for name, dimensions in EXPECTED_CANVASES.items():
        branch = prop.child(name)
        canvas = branch.child("0") if isinstance(branch, WzSubProperty) else None
        if not isinstance(canvas, WzCanvasProperty):
            raise ValueError(f"rope/59/{name}/0 is not a canvas")
        actual_dimensions = (int(canvas.width), int(canvas.height))
        if actual_dimensions != dimensions or int(canvas.format) + int(canvas.format2) != 1:
            raise ValueError(
                f"rope/59/{name}/0 is {actual_dimensions} format "
                f"{int(canvas.format) + int(canvas.format2)}, expected {dimensions} format 1"
            )
        child_values = tuple((child.name, child.type_name, child.value) for child in canvas.children())
        convex = canvas.child("rope")
        if not isinstance(convex, WzConvexProperty) or len(convex.points) != 2:
            raise ValueError(f"rope/59/{name}/0/rope must be a two-point convex property")
        convex_values = tuple((point.name, point.x, point.y) for point in convex.points)
        canvases.append(
            (name, actual_dimensions, child_values, convex_values, canvas_digest(canvas))
        )
    return tuple(canvases)


def repair_binary(current: bytes, stable: bytes) -> bytes:
    current_span = locate_rope59(current)
    stable_prop = parse_rope59(stable)
    stable_body_with_size = _encode_property_body(
        stable_prop, WzBinaryReader(io.BytesIO(b""), TARGET_KEY)
    )
    stable_size = struct.unpack_from("<I", stable_body_with_size)[0]
    stable_body = stable_body_with_size[4:]
    if stable_size != len(stable_body):
        raise AssertionError("stable rope/59 encoder returned an invalid block size")
    if stable_size > current_span.block_size:
        raise ValueError(
            f"stable rope/59 needs {stable_size} bytes, current slot has only "
            f"{current_span.block_size}"
        )

    repaired = bytearray(current)
    repaired[current_span.body_start:current_span.end] = (
        stable_body + bytes(current_span.block_size - stable_size)
    )
    repaired_bytes = bytes(repaired)
    if len(repaired_bytes) != len(current):
        raise AssertionError("repair changed connect.img length")
    if repaired_bytes[:current_span.body_start] != current[:current_span.body_start]:
        raise AssertionError("repair changed bytes before rope/59 body")
    if repaired_bytes[current_span.end:] != current[current_span.end:]:
        raise AssertionError("repair changed bytes after rope/59 body")
    if rope59_signature(parse_rope59(repaired_bytes)) != rope59_signature(stable_prop):
        raise AssertionError("repaired rope/59 does not match the stable resource")
    return repaired_bytes


def find_imgdir_span(text: str, token: str, start: int = 0) -> tuple[int, int]:
    node_start = text.find(token, start)
    if node_start < 0:
        raise ValueError(f"missing XML node {token}")
    depth = 0
    for match in IMGDIR_TAG_RE.finditer(text, node_start):
        tag = match.group(0)
        if match.start() == node_start:
            if tag.endswith("/>"):
                return node_start, match.end()
            depth = 1
            continue
        if tag.startswith("</"):
            depth -= 1
            if depth == 0:
                return node_start, match.end()
        elif not tag.endswith("/>"):
            depth += 1
    raise ValueError(f"unclosed XML node {token}")


def rope59_xml_span(text: str) -> tuple[int, int]:
    rope_start, rope_end = find_imgdir_span(text, '<imgdir name="rope">')
    return find_imgdir_span(text, '<imgdir name="59"', rope_start)


def repair_xml(current: str, stable: str) -> str:
    current_start, current_end = rope59_xml_span(current)
    stable_start, stable_end = rope59_xml_span(stable)
    if current_end > find_imgdir_span(current, '<imgdir name="rope">')[1]:
        raise ValueError("server XML rope/59 is outside its rope parent")
    stable_node = stable[stable_start:stable_end].replace("\r\n", "\n")
    if current.count("\r\n") > current.count("\n") // 2:
        stable_node = stable_node.replace("\n", "\r\n")
    return current[:current_start] + stable_node + current[current_end:]


def main() -> int:
    client_path = ROOT / CLIENT_REL
    server_path = ROOT / SERVER_REL
    current_client = client_path.read_bytes()
    stable_client = git_head_bytes(CLIENT_REL)
    repaired_client = repair_binary(current_client, stable_client)

    # bytes.decode preserves the file's existing CRLF/LF convention. Path.read_text
    # uses universal newlines and would make an otherwise surgical XML edit noisy.
    current_server = server_path.read_bytes().decode("utf-8")
    stable_server = git_head_bytes(SERVER_REL).decode("utf-8")
    repaired_server = repair_xml(current_server, stable_server)

    backup(client_path)
    backup(server_path)
    atomic_write_bytes(client_path, repaired_client)
    atomic_write_text(server_path, repaired_server)

    print(f"repaired {CLIENT_REL} ({len(current_client)} bytes, offsets preserved)")
    print(f"repaired {SERVER_REL} (only rope/59 replaced)")
    print(f"backup: {BACKUP_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
