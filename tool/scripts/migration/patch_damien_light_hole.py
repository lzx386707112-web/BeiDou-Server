#!/usr/bin/env python3
"""Make Damien light-hole portals actually fire on the old client."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
from migrate_twilight_perion_monster_park import load_checked  # noqa: E402
from wzpy import WzImage, WzIntProperty, WzStringProperty, WzSubProperty  # noqa: E402

GATE_MAP = ROOT / "clien/Data/Map/Map/Map1/105300301.img"
GATE_XML = ROOT / "gms-server/wz/Map.wz/Map/Map1/105300301.img.xml"
ENTRY_MAP = ROOT / "clien/Data/Map/Map/Map1/105300303.img"
ENTRY_XML = ROOT / "gms-server/wz/Map.wz/Map/Map1/105300303.img.xml"
GATE_SCRIPT = "fallenWT_gate"
NPC_ID = "1540895"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_entry_npc() -> WzSubProperty:
    node = WzSubProperty("0")
    node.add(WzStringProperty("type", "n", node))
    node.add(WzStringProperty("id", NPC_ID, node))
    node.add(WzIntProperty("x", 430, node))
    node.add(WzIntProperty("y", -585, node))
    node.add(WzIntProperty("mobTime", 0, node))
    node.add(WzIntProperty("f", 0, node))
    node.add(WzIntProperty("hide", 0, node))
    node.add(WzIntProperty("fh", 9, node))
    node.add(WzIntProperty("cy", -579, node))
    node.add(WzIntProperty("rx0", 380, node))
    node.add(WzIntProperty("rx1", 480, node))
    return node


def patch_gate_script() -> None:
    original = GATE_MAP.read_bytes()
    image = load_checked(GATE_MAP, arc.GMS_KEY)
    entry = None
    for child in image.root.child("portal").children():
        if arc.child_value(child, "pn") == "out00":
            entry = child
            break
    if entry is None:
        raise RuntimeError("105300301 missing out00")
    current = str(arc.child_value(entry, "script") or "")
    if current != GATE_SCRIPT:
        script_node = entry.child("script")
        if script_node is None:
            patched = arc.mutate_img(
                original,
                "add",
                ("portal", entry.name),
                name="script",
                kind="String",
                values={"value": GATE_SCRIPT},
                region="GMS",
            ).data
            arc.verify_raw_record_insert_scope(original, patched, {("portal", entry.name, "script")})
        else:
            patched = arc.mutate_img(
                original,
                "edit",
                ("portal", entry.name, "script"),
                values={"value": GATE_SCRIPT},
                region="GMS",
            ).data
            arc.verify_raw_record_scope(original, patched, {("portal", entry.name, "script")})
        checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=GATE_MAP.name)
        checked.parse()
        if checked.truncated or checked.parse_warnings:
            raise RuntimeError("105300301 parse failed after out00 script")
        arc.atomic_write_bytes(GATE_MAP, patched)
    text = GATE_XML.read_text(encoding="utf-8")
    start = text.find('<string name="pn" value="out00"/>')
    if start < 0:
        raise RuntimeError("105300301 XML missing out00")
    chunk_end = text.find("</imgdir>", start)
    chunk = text[start:chunk_end]
    if f'name="script" value="{GATE_SCRIPT}"' not in chunk:
        if 'name="script"' in chunk:
            raise RuntimeError("105300301 XML out00 has unexpected script")
        updated = text[:chunk_end] + f'      <string name="script" value="{GATE_SCRIPT}"/>\n    ' + text[chunk_end:]
        arc.atomic_write_text(GATE_XML, updated)


def patch_entry_npc() -> None:
    original = ENTRY_MAP.read_bytes()
    image = load_checked(ENTRY_MAP, arc.GMS_KEY)
    life = image.root.child("life")
    existing = []
    if life is not None:
        for child in life.children():
            if str(arc.child_value(child, "id") or "") == NPC_ID:
                existing.append(child)
    if not existing:
        node = make_entry_npc()
        patched = arc.append_property_record(original, ("life",), node)
        arc.verify_raw_record_insert_scope(original, patched, {("life", "0")})
        checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=ENTRY_MAP.name)
        checked.parse()
        if checked.truncated or checked.parse_warnings:
            raise RuntimeError("105300303 parse failed after NPC insert")
        ids = [
            str(arc.child_value(child, "id") or "")
            for child in checked.root.child("life").children()
        ]
        if NPC_ID not in ids:
            raise RuntimeError("105300303 missing NPC after insert")
        arc.atomic_write_bytes(ENTRY_MAP, patched)
    text = ENTRY_XML.read_text(encoding="utf-8")
    if f'<string name="id" value="{NPC_ID}"/>' not in text:
        node = make_entry_npc()
        updated = arc.append_xml_properties(text, ("life",), [node])
        arc.atomic_write_text(ENTRY_XML, updated)


def main() -> int:
    targets = (GATE_MAP, GATE_XML, ENTRY_MAP, ENTRY_XML)
    patch_gate_script()
    patch_entry_npc()
    first = {str(path): sha256_file(path) for path in targets}
    patch_gate_script()
    patch_entry_npc()
    second = {str(path): sha256_file(path) for path in targets}
    if first != second:
        raise RuntimeError(f"light-hole patcher is not idempotent: {first} vs {second}")
    print("damien light-hole patch ok")
    for path, digest in first.items():
        print(f"{Path(path).relative_to(ROOT)} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
