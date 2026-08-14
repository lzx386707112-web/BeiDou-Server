#!/usr/bin/env python3
"""Hide Explorer V/VI attacks from the legacy skill window incrementally."""

from __future__ import annotations

import struct
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import WzImage, WzIntProperty, WzKey, WzSubProperty  # noqa: E402
from wzpy.writer import _encode_property_list, encode_compressed_int  # noqa: E402


KEY = WzKey.for_region("GMS")
SKILLS = {
    112: (1121020, 1121012, 1121013, 1121014, 1121023, 1121025, 1121030),
    122: (1221015, 1221016, 1221020, 1221027, 1221030),
    132: (1321011, 1321015, 1321018, 1321020, 1321022, 1321025),
    212: (2121012, 2121017, 2121020, 2121022, 2121028, 2121032, 2121035),
    222: (2221009, 2221010, 2221014, 2221017, 2221020, 2221027, 2221030),
    232: (2321020, 2321024, 2321031, 2321032, 2321033, 2321035, 2321037, 2321042),
    312: (3121010, 3121022, 3121025, 3121026, 3121028, 3121029, 3121031),
    322: (3221009, 3221013, 3221029, 3221030, 3221031, 3221032, 3221034),
    412: (4121011, 4121016, 4121019, 4121022, 4121023, 4121026, 4121028),
    422: (4221009, 4221010, 4221011, 4221018, 4221019, 4221020, 4221022, 4221023, 4221027),
    512: (5121014, 5121015, 5121017, 5121024, 5121025, 5121028, 5121029, 5121035),
    522: (5221011, 5221012, 5221013, 5221022, 5221024, 5221030, 5221032, 5221034),
}


def atomic_write(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def load(path: Path, data: bytes) -> WzImage:
    image = WzImage.from_bytes(data, key=KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"unsafe IMG {path}: {image.parse_warnings}")
    return image


def skill_layout(image: WzImage, path: Path):
    reader = image.wz_file.reader
    reader.seek(0)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError(f"unsupported IMG header: {path}")
    reader.skip(2)
    for _ in range(reader.read_compressed_int()):
        name = reader.read_string_block(0)
        tag = reader.read_byte()
        if tag != 9:
            raise RuntimeError(f"unexpected root tag {name}/{tag}: {path}")
        size_offset = reader.position
        size = reader.read_u32()
        block_start = reader.position
        block_end = block_start + size
        if name != "skill":
            reader.seek(block_end)
            continue
        if reader.read_string_block(0) != "Property":
            raise RuntimeError(f"skill root is not Property: {path}")
        reader.skip(2)
        count = reader.read_compressed_int()
        names, spans = [], []
        for _ in range(count):
            start = reader.position
            child_name = reader.read_string_block(0)
            child_tag = reader.read_byte()
            if child_tag != 9:
                raise RuntimeError(f"unexpected skill tag {child_name}/{child_tag}: {path}")
            child_size = reader.read_u32()
            reader.seek(reader.position + child_size)
            names.append(child_name)
            spans.append((start, reader.position))
        if reader.position > block_end:
            raise RuntimeError(f"skill records exceed block: {path}")
        return size_offset, tuple(names), tuple(spans)
    raise RuntimeError(f"missing skill root: {path}")


def encode_record(node: WzSubProperty, image: WzImage) -> bytes:
    encoded = _encode_property_list((node,), image.wz_file.reader)
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError("unexpected property record prefix")
    return encoded[len(prefix):]


def patch_client(book: int, skill_ids: tuple[int, ...]) -> None:
    path = ROOT / f"clien/Data/Skill/{book}.img"
    original = path.read_bytes()
    image = load(path, original)
    root = image.root
    size_offset, names, spans = skill_layout(image, path)
    records = {name: original[start:end] for name, (start, end) in zip(names, spans)}
    replacements = {}
    for skill_id in skill_ids:
        name = str(skill_id)
        node = root.get(f"skill/{name}")
        if not isinstance(node, WzSubProperty) or name not in records:
            raise RuntimeError(f"missing approved skill {skill_id}: {path}")
        invisible = node.child("invisible")
        if invisible is not None:
            if int(invisible.value) != 1:
                raise RuntimeError(f"invalid invisible value on {skill_id}")
            continue
        node.add(WzIntProperty("invisible", 1, node))
        replacements[name] = encode_record(node, image)
    if not replacements:
        return
    rebuilt = b"".join(replacements.get(name, records[name]) for name in names)
    records_start, records_end = spans[0][0], spans[-1][1]
    updated = bytearray(original[:records_start] + rebuilt + original[records_end:])
    delta = len(rebuilt) - (records_end - records_start)
    struct.pack_into("<I", updated, size_offset, struct.unpack_from("<I", original, size_offset)[0] + delta)
    verified = load(path, bytes(updated))
    _, new_names, new_spans = skill_layout(verified, path)
    if new_names != names:
        raise RuntimeError(f"skill order changed: {path}")
    for name, old_span, new_span in zip(names, spans, new_spans):
        if name not in replacements and original[slice(*old_span)] != bytes(updated)[slice(*new_span)]:
            raise RuntimeError(f"unapproved skill record changed: {book}/{name}")
    for skill_id in skill_ids:
        prop = verified.root.get(f"skill/{skill_id}/invisible")
        if prop is None or int(prop.value) != 1:
            raise RuntimeError(f"hidden flag validation failed: {skill_id}")
    atomic_write(path, bytes(updated))


def find_imgdir_end(text: str, start: int) -> int:
    depth = 0
    pos = start
    while True:
        opening = text.find("<imgdir ", pos)
        closing = text.find("</imgdir>", pos)
        if closing < 0:
            raise RuntimeError("unterminated imgdir")
        if 0 <= opening < closing:
            depth += 1
            pos = opening + 8
        else:
            depth -= 1
            pos = closing + len("</imgdir>")
            if depth == 0:
                return pos


def patch_server(book: int, skill_ids: tuple[int, ...]) -> None:
    path = ROOT / f"gms-server/wz/Skill.wz/{book}.img.xml"
    text = path.read_text(encoding="utf-8")
    updated = text
    for skill_id in skill_ids:
        token = f'<imgdir name="{skill_id}">'
        start = updated.find(token)
        if start < 0:
            raise RuntimeError(f"missing server skill {skill_id}: {path}")
        end = find_imgdir_end(updated, start)
        block = updated[start:end]
        if '<int name="invisible" value="1"/>' in block:
            if block.endswith("\n</imgdir>"):
                block = block[:-len("\n</imgdir>")] + "\n  </imgdir>"
                updated = updated[:start] + block + updated[end:]
            continue
        closing = block.rfind("</imgdir>")
        line_start = block.rfind("\n", 0, closing) + 1
        indent = block[line_start:closing]
        block = (block[:line_start] + indent + '  <int name="invisible" value="1"/>\n'
                 + block[line_start:])
        updated = updated[:start] + block + updated[end:]
    if updated != text:
        atomic_write(path, updated.encode("utf-8"))


def main() -> None:
    for book, skill_ids in SKILLS.items():
        patch_client(book, skill_ids)
        patch_server(book, skill_ids)
    print(f"hidden Explorer V/VI skills: {sum(map(len, SKILLS.values()))}")


if __name__ == "__main__":
    main()
