#!/usr/bin/env python3
"""Replace Damien 1x1 skill/warning stubs with old-client UOLs.

TMS leaves logical 1x1 outlinks at the start of a folder. The old client draws
those at the feet (origin 0,0). Point them at the next real sibling / skill3
using ../folder/N — same-folder digit UOLs fall back to stand.

Do not full-serialize 8880110/8880111. Do not spawn 8880102.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzSubProperty, WzUolProperty  # noqa: E402
from wzpy.incremental_img import mutate_img, replace_img_record  # noqa: E402

P1 = ROOT / "clien/Data/Mob/8880110.img"
P1_XML = ROOT / "gms-server/wz/Mob.wz/8880110.img.xml"
P2 = ROOT / "clien/Data/Mob/8880111.img"
P2_XML = ROOT / "gms-server/wz/Mob.wz/8880111.img.xml"

P1_UOLS = (
    (("attack1", "info", "areaWarning", "0"), "../areaWarning/1"),
    (("attack3", "info", "areaWarning", "0"), "../areaWarning/1"),
)
P2_UOLS = (
    (("attack1", "info", "effect", "0"), "../effect/1"),
    (("skill2", "10"), "../skill3/10"),
    (("skill5", "10"), "../skill5/11"),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=arc.GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{path.name} parse failed: {image.parse_warnings}")
    return image


def replace_uol(data: bytes, path: tuple[str, ...], value: str) -> bytes:
    node = WzUolProperty(path[-1], value)
    return replace_img_record(data, path, node, region="GMS").data


def reorder_skill4(data: bytes) -> bytes:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name="8880110.img")
    image.parse()
    skill4 = image.root.child("skill4")
    if not isinstance(skill4, WzSubProperty):
        raise RuntimeError("missing skill4")
    names = [child.name for child in skill4.children() if child.name.isdigit() or True]
    if names[:2] == ["0", "1"]:
        return data
    zero = skill4.child("0")
    one = skill4.child("1")
    if not isinstance(zero, WzUolProperty) or not isinstance(one, WzUolProperty):
        raise RuntimeError("skill4/0 or skill4/1 is not a UOL")
    if str(zero.value) != "../skill3/0" or str(one.value) != "../skill3/1":
        raise RuntimeError(f"unexpected skill4 UOLs {zero.value} {one.value}")
    data = mutate_img(data, "remove", ("skill4", "0"), region="GMS").data
    data = mutate_img(data, "remove", ("skill4", "1"), region="GMS").data
    data = arc.insert_property_record_before(data, ("skill4",), WzUolProperty("0", "../skill3/0"), "2")
    data = arc.insert_property_record_before(data, ("skill4",), WzUolProperty("1", "../skill3/1"), "2")
    return data


def patch_client(path: Path, replacements: tuple[tuple[tuple[str, ...], str], ...], skill4: bool) -> bytes:
    original = path.read_bytes()
    data = original
    image = load(path)
    for record, value in replacements:
        node = image.root.get("/".join(record))
        if isinstance(node, WzUolProperty) and str(node.value) == value:
            continue
        if isinstance(node, WzCanvasProperty) and int(node.width) > 2:
            raise RuntimeError(f"{path.name} {'/'.join(record)} is not a 1x1 stub")
        data = replace_uol(data, record, value)
        image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=path.name)
        image.parse()
    if skill4:
        data = reorder_skill4(data)
    parsed = WzImage.from_bytes(data, key=arc.GMS_KEY, name=path.name)
    parsed.parse()
    if parsed.truncated or parsed.parse_warnings:
        raise RuntimeError(f"{path.name} patched parse failed: {parsed.parse_warnings}")
    before, before_orders = arc.raw_record_state(original)
    after, after_orders = arc.raw_record_state(data)
    allowed = {record for record, _ in replacements}
    if skill4:
        allowed.update({("skill4",), ("skill4", "0"), ("skill4", "1")})
    for rec_path, raw in before.items():
        affected = any(rec_path[: len(root)] == root or root[: len(rec_path)] == rec_path for root in allowed)
        if not affected and after.get(rec_path) != raw:
            raise RuntimeError(f"protected record changed: {rec_path}")
    if skill4 and tuple(after_orders.get(("skill4",), ())[:2]) != ("0", "1"):
        raise RuntimeError(f"skill4 order starts {after_orders.get(('skill4',), [])[:4]}")
    return data


def patch_p1_xml() -> None:
    text = P1_XML.read_text(encoding="utf-8")
    stub = (
        '        <canvas name="0" width="1" height="1" format="1">\n'
        '          <vector name="origin" x="0" y="0"/>\n'
        '          <int name="delay" value="90"/>\n'
        "        </canvas>\n"
    )
    uol = '        <uol name="0" value="../areaWarning/1"/>\n'
    if stub not in text:
        if uol not in text:
            raise RuntimeError("8880110 XML areaWarning/0 stub missing")
    else:
        text = text.replace(stub, uol)
    skill4 = '  <imgdir name="skill4">\n'
    head = (
        '  <imgdir name="skill4">\n'
        '    <uol name="0" value="../skill3/0"/>\n'
        '    <uol name="1" value="../skill3/1"/>\n'
    )
    if not text.startswith(head) and skill4 in text and not text.split(skill4, 1)[1].startswith('    <uol name="0"'):
        text = text.replace(skill4, head, 1)
        text = text.replace(
            '    <uol name="0" value="../skill3/0"/>\n'
            '    <uol name="1" value="../skill3/1"/>\n'
            '    <uol name="42" value="../skill2/87"/>\n',
            '    <uol name="42" value="../skill2/87"/>\n',
            1,
        )
    if text != P1_XML.read_text(encoding="utf-8"):
        arc.atomic_write_text(P1_XML, text)


def patch_p2_xml() -> None:
    text = P2_XML.read_text(encoding="utf-8")
    replacements = (
        (
            '        <canvas name="0" width="1" height="1" format="1">\n'
            '          <int name="delay" value="840"/>\n'
            "        </canvas>\n",
            '        <uol name="0" value="../effect/1"/>\n',
        ),
        (
            '    <canvas name="10" width="1" height="1" format="1">\n'
            '      <int name="delay" value="600"/>\n'
            '      <int name="hide" value="1"/>\n'
            "    </canvas>\n",
            '    <uol name="10" value="../skill3/10"/>\n',
        ),
    )
    # skill5/10 is the second hide 1x1; replace remaining stub after skill2 is gone.
    updated = text
    for old, new in replacements:
        if old not in updated:
            if new not in updated:
                raise RuntimeError(f"8880111 XML stub missing:\n{old}")
            continue
        updated = updated.replace(old, new, 1)
    skill5_stub = (
        '    <canvas name="10" width="1" height="1" format="1">\n'
        '      <int name="delay" value="180"/>\n'
        "    </canvas>\n"
    )
    skill5_uol = '    <uol name="10" value="../skill5/11"/>\n'
    if skill5_stub in updated:
        updated = updated.replace(skill5_stub, skill5_uol, 1)
    elif 'name="10" value="../skill5/11"' not in updated:
        raise RuntimeError("8880111 XML skill5/10 stub missing")
    if updated != text:
        arc.atomic_write_text(P2_XML, updated)


def verify_uol(image: WzImage, path: str, expected: str) -> None:
    node = image.root.get(path)
    if not isinstance(node, WzUolProperty) or str(node.value) != expected:
        raise RuntimeError(f"{image.name} {path} is {node}")


def main() -> int:
    first_p1 = patch_client(P1, P1_UOLS, True)
    first_p2 = patch_client(P2, P2_UOLS, False)
    arc.atomic_write_bytes(P1, first_p1)
    arc.atomic_write_bytes(P2, first_p2)
    patch_p1_xml()
    patch_p2_xml()
    second_p1 = patch_client(P1, P1_UOLS, True)
    second_p2 = patch_client(P2, P2_UOLS, False)
    if sha256(first_p1) != sha256(second_p1) or sha256(first_p2) != sha256(second_p2):
        raise RuntimeError("client patch not idempotent")
    p1 = load(P1)
    p2 = load(P2)
    verify_uol(p1, "attack1/info/areaWarning/0", "../areaWarning/1")
    verify_uol(p1, "attack3/info/areaWarning/0", "../areaWarning/1")
    names = [child.name for child in p1.root.child("skill4").children()]
    if names[:2] != ["0", "1"]:
        raise RuntimeError(f"skill4 still starts {names[:4]}")
    verify_uol(p2, "skill2/10", "../skill3/10")
    verify_uol(p2, "skill5/10", "../skill5/11")
    verify_uol(p2, "attack1/info/effect/0", "../effect/1")
    print("8880110.img sha256=" + sha256(P1.read_bytes()))
    print("8880111.img sha256=" + sha256(P2.read_bytes()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
