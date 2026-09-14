#!/usr/bin/env python3
"""Contract: 105300301 out00 光洞 warps to 105300303 sp."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import migrate_arcane_river_expansion as arc  # noqa: E402
from migrate_twilight_perion_monster_park import load_checked  # noqa: E402

CLIENT = ROOT / "clien/Data/Map/Map/Map1/105300301.img"
SERVER = ROOT / "gms-server/wz/Map.wz/Map/Map1/105300301.img.xml"
DEST_MAP = 105300303


def _client_out00():
    image = load_checked(CLIENT, arc.GMS_KEY)
    portal = image.root.child("portal")
    for entry in portal.children():
        if arc.child_value(entry, "pn") == "out00":
            return entry
    raise RuntimeError("client missing out00")


def main() -> int:
    errors: list[str] = []
    entry = _client_out00()
    if int(arc.child_value(entry, "pt") or 0) != 7:
        errors.append("client out00 pt != 7")
    if int(arc.child_value(entry, "tm") or 0) != DEST_MAP:
        errors.append("client out00 tm != 105300303")
    if str(arc.child_value(entry, "tn") or "") != "sp":
        errors.append("client out00 tn != sp")
    if str(arc.child_value(entry, "script") or "") != "fallenWT_gate":
        errors.append("client out00 missing fallenWT_gate")
    root = ET.parse(SERVER).getroot()
    portal = root.find("imgdir[@name='portal']")
    xml_hit = None
    for child in portal.findall("imgdir"):
        pn = child.find("string[@name='pn']")
        if pn is not None and pn.get("value") == "out00":
            xml_hit = child
            break
    if xml_hit is None:
        errors.append("xml missing out00")
    else:
        pt = xml_hit.find("int[@name='pt']")
        tm = xml_hit.find("int[@name='tm']")
        tn = xml_hit.find("string[@name='tn']")
        if pt is None or pt.get("value") != "7":
            errors.append("xml out00 pt != 7")
        if tm is None or tm.get("value") != str(DEST_MAP):
            errors.append("xml out00 tm != 105300303")
        if tn is None or tn.get("value") != "sp":
            errors.append("xml out00 tn != sp")
        script = xml_hit.find("string[@name='script']")
        if script is None or script.get("value") != "fallenWT_gate":
            errors.append("xml out00 missing fallenWT_gate")
    dest = ROOT / "gms-server/wz/Map.wz/Map/Map1/105300303.img.xml"
    dest_root = ET.parse(dest).getroot()
    dest_portal = dest_root.find("imgdir[@name='portal']")
    names = {
        child.find("string[@name='pn']").get("value")
        for child in dest_portal.findall("imgdir")
        if child.find("string[@name='pn']") is not None
    }
    if "sp" not in names:
        errors.append("105300303 missing spawn portal sp")
    if errors:
        print("FAIL")
        for error in errors:
            print(error)
        return 1
    print("ok 105300301 out00 -> 105300303/sp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
