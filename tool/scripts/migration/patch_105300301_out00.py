#!/usr/bin/env python3
"""Point 105300301 portal out00 (portal 4 光洞) at 105300303 spawn."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import migrate_arcane_river_expansion as arc  # noqa: E402
from migrate_twilight_perion_monster_park import load_checked  # noqa: E402
from wzpy import WzImage  # noqa: E402

DEST_MAP = 105300303
PORTAL_NAME = "out00"
CLIENT = ROOT / "clien/Data/Map/Map/Map1/105300301.img"
SERVER = ROOT / "gms-server/wz/Map.wz/Map/Map1/105300301.img.xml"


def _portal_entry(image):
    portal = image.root.child("portal")
    for entry in portal.children():
        if arc.child_value(entry, "pn") == PORTAL_NAME:
            return entry
    raise RuntimeError(f"105300301 missing portal {PORTAL_NAME}")


def _xml_portal_name(text: str) -> str:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(text)
    portal = root.find("imgdir[@name='portal']")
    if portal is None:
        raise RuntimeError("105300301 XML missing portal")
    for entry in portal.findall("imgdir"):
        pn = entry.find("string[@name='pn']")
        if pn is not None and pn.get("value") == PORTAL_NAME:
            return entry.get("name") or ""
    raise RuntimeError(f"105300301 XML missing portal {PORTAL_NAME}")


def patch_client() -> bytes:
    original = CLIENT.read_bytes()
    image = load_checked(CLIENT, arc.GMS_KEY)
    entry = _portal_entry(image)
    name = entry.name
    current_tm = int(arc.child_value(entry, "tm") or 0)
    current_tn = str(arc.child_value(entry, "tn") or "")
    if current_tm == DEST_MAP and current_tn == "sp":
        return original
    patched = original
    if current_tm != DEST_MAP:
        patched = arc.mutate_img(
            original,
            "edit",
            ("portal", name, "tm"),
            values={"value": DEST_MAP},
            region="GMS",
        ).data
        arc.verify_raw_record_scope(
            original, patched, {("portal", name, "tm")}, allow_additions=False
        )
    if current_tn != "sp":
        before_tn = patched
        patched = arc.mutate_img(
            patched,
            "edit",
            ("portal", name, "tn"),
            values={"value": "sp"},
            region="GMS",
        ).data
        arc.verify_raw_record_scope(
            before_tn, patched, {("portal", name, "tn")}, allow_additions=False
        )
    checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=CLIENT.name)
    checked.parse()
    if checked.truncated or checked.parse_warnings:
        raise RuntimeError(
            f"105300301 parse failed after out00 patch: truncated={checked.truncated} warnings={checked.parse_warnings}"
        )
    entry = _portal_entry(checked)
    if int(arc.child_value(entry, "tm") or 0) != DEST_MAP:
        raise RuntimeError("client tm not patched")
    if str(arc.child_value(entry, "tn") or "") != "sp":
        raise RuntimeError("client tn not patched")
    if int(arc.child_value(entry, "pt") or 0) != 7:
        raise RuntimeError("client pt should stay 7 for 光洞")
    arc.atomic_write_bytes(CLIENT, patched)
    return patched


def patch_server() -> None:
    text = SERVER.read_text(encoding="utf-8")
    name = _xml_portal_name(text)
    tm_path = ("portal", name, "tm")
    tn_path = ("portal", name, "tn")
    updated = text
    if f'<imgdir name="{name}">' not in text:
        raise RuntimeError(f"XML portal {name} missing")
    # Edit only if needed; mutate_xml is in-place on the value attribute.
    import xml.etree.ElementTree as ET

    root = ET.fromstring(text)
    portal = root.find("imgdir[@name='portal']")
    entry = next(
        child
        for child in portal.findall("imgdir")
        if child.get("name") == name
    )
    tm = entry.find("int[@name='tm']")
    tn = entry.find("string[@name='tn']")
    pt = entry.find("int[@name='pt']")
    if tm is None or tn is None or pt is None:
        raise RuntimeError("XML portal 4 missing tm/tn/pt")
    if pt.get("value") != "7":
        raise RuntimeError("XML pt should stay 7 for 光洞")
    if tm.get("value") != str(DEST_MAP):
        updated = arc.mutate_xml(
            updated, "edit", tm_path, kind="Int", values={"value": DEST_MAP}
        )
    if tn.get("value") != "sp":
        updated = arc.mutate_xml(
            updated, "edit", tn_path, kind="String", values={"value": "sp"}
        )
    if updated != text:
        SERVER.write_text(updated, encoding="utf-8")


def main() -> None:
    first = hashlib.sha256(CLIENT.read_bytes()).hexdigest()
    xml_first = hashlib.sha256(SERVER.read_bytes()).hexdigest()
    patch_client()
    patch_server()
    second_before = hashlib.sha256(CLIENT.read_bytes()).hexdigest()
    xml_second_before = hashlib.sha256(SERVER.read_bytes()).hexdigest()
    patch_client()
    patch_server()
    second_after = hashlib.sha256(CLIENT.read_bytes()).hexdigest()
    xml_second_after = hashlib.sha256(SERVER.read_bytes()).hexdigest()
    if second_before != second_after:
        raise RuntimeError("client patch is not idempotent")
    if xml_second_before != xml_second_after:
        raise RuntimeError("server XML patch is not idempotent")
    print(f"client {first} -> {second_after}")
    print(f"xml {xml_first} -> {xml_second_after}")


if __name__ == "__main__":
    main()
