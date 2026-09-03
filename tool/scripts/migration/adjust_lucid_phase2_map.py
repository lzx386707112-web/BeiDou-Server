#!/usr/bin/env python3
"""Restore Lucid P2's TMS fall portal and disable legacy swim physics."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CLIENT = ROOT / "clien/Data/Map/Map/Map4/450004250.img"
SERVER = ROOT / "gms-server/wz/Map.wz/Map/Map4/450004250.img.xml"
SOURCE = Path(
    "/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data/Map/Map/Map4/450004250.img"
)
SOURCE_SHA256 = "32c32cae338f4c26b6927836a4ad691c677d39203e78dab31a646921e1e32054"

sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import WzImage, WzIntProperty, WzKey, WzStringProperty, WzSubProperty  # noqa: E402
from wzpy.incremental_img import replace_img_record, scan_img  # noqa: E402


ARC_PATH = Path(__file__).with_name("migrate_arcane_river_expansion.py")
ARC_SPEC = importlib.util.spec_from_file_location("arcane_river_expansion", ARC_PATH)
if ARC_SPEC is None or ARC_SPEC.loader is None:
    raise RuntimeError(f"cannot import {ARC_PATH}")
arc = importlib.util.module_from_spec(ARC_SPEC)
ARC_SPEC.loader.exec_module(arc)

SOURCE_PORTAL_FIELDS = (
    ("pn", "pt00"),
    ("pt", 9),
    ("x", 652),
    ("y", 320),
    ("tm", 999999999),
    ("tn", ""),
    ("delay", 1000),
    ("horizontalImpact", 0),
    ("script", "pt00_450004250"),
    ("hRange", 1600),
    ("vRange", 200),
    ("hideTooltip", 0),
    ("onlyOnce", 0),
)

# Preserve the old client's existing child order, then append only the fields
# needed by TMS's automatic portal range contract.
PORTAL_FIELDS = (
    ("pn", "pt00"),
    ("x", 652),
    ("y", 320),
    ("pt", 9),
    ("tm", 999999999),
    ("tn", ""),
    ("script", "pt00_450004250"),
    ("delay", 1000),
    ("horizontalImpact", 0),
    ("hRange", 1600),
    ("vRange", 200),
    ("hideTooltip", 0),
    ("onlyOnce", 0),
)

OLD_PORTAL_XML = """    <imgdir name="11">
      <string name="pn" value="pt00"/>
      <int name="x" value="652"/>
      <int name="y" value="320"/>
      <int name="pt" value="7"/>
      <int name="tm" value="999999999"/>
      <string name="tn" value=""/>
      <string name="script" value="lucid_exit"/>
    </imgdir>"""

NEW_PORTAL_XML = """    <imgdir name="11">
      <string name="pn" value="pt00"/>
      <int name="x" value="652"/>
      <int name="y" value="320"/>
      <int name="pt" value="9"/>
      <int name="tm" value="999999999"/>
      <string name="tn" value=""/>
      <string name="script" value="pt00_450004250"/>
      <int name="delay" value="1000"/>
      <int name="horizontalImpact" value="0"/>
      <int name="hRange" value="1600"/>
      <int name="vRange" value="200"/>
      <int name="hideTooltip" value="0"/>
      <int name="onlyOnce" value="0"/>
    </imgdir>"""


def load_image(path: Path, region: str) -> WzImage:
    image = WzImage.from_bytes(
        path.read_bytes(), key=WzKey.for_region(region), name=path.name
    )
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"invalid {path}: truncated={image.truncated} "
            f"warnings={image.parse_warnings}"
        )
    return image


def child_values(node: WzSubProperty) -> tuple[tuple[str, object], ...]:
    return tuple((child.name, child.value) for child in node.children())


def source_portal() -> WzSubProperty:
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise RuntimeError(f"TMS source changed: {SOURCE}")
    source = load_image(SOURCE, "BMS").root.get("portal/11")
    if not isinstance(source, WzSubProperty):
        raise RuntimeError("TMS map is missing portal/11")
    if child_values(source) != SOURCE_PORTAL_FIELDS:
        raise RuntimeError("TMS portal/11 contract changed")
    portal = WzSubProperty("11")
    for name, value in PORTAL_FIELDS:
        child = (
            WzStringProperty(name, value, portal)
            if isinstance(value, str)
            else WzIntProperty(name, value, portal)
        )
        portal.add(child)
    return portal


def patch_client() -> None:
    original = CLIENT.read_bytes()
    image = load_image(CLIENT, "GMS")
    swim = image.root.get("info/swim")
    portal = image.root.get("portal/11")
    if not isinstance(swim, WzIntProperty) or int(swim.value) not in (0, 1):
        raise RuntimeError("unexpected client info/swim contract")
    if not isinstance(portal, WzSubProperty):
        raise RuntimeError("client map is missing portal/11")

    result = original
    if int(swim.value) == 1:
        layout = scan_img(result, region="GMS")
        info_record = next(record for record in layout.root.records if record.name == "info")
        swim_record = next(
            record for record in info_record.children.records if record.name == "swim"
        )
        if swim_record.tag != 3 or swim_record.end - swim_record.body_start != 1:
            raise RuntimeError("info/swim is not a one-byte compressed int")
        updated = bytearray(result)
        if updated[swim_record.body_start] != 1:
            raise RuntimeError("unexpected encoded info/swim value")
        updated[swim_record.body_start] = 0
        result = bytes(updated)

    image = WzImage.from_bytes(
        result, key=WzKey.for_region("GMS"), name=CLIENT.name
    )
    image.parse()
    current_portal = image.root.get("portal/11")
    if not isinstance(current_portal, WzSubProperty):
        raise RuntimeError("client map lost portal/11")
    if child_values(current_portal) != PORTAL_FIELDS:
        result = replace_img_record(
            result, ("portal", "11"), source_portal(), region="GMS"
        ).data

    arc.verify_raw_record_scope(
        original, result, {("info", "swim"), ("portal", "11")},
        allow_additions=True,
    )
    verified = WzImage.from_bytes(
        result, key=WzKey.for_region("GMS"), name=CLIENT.name
    )
    verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise RuntimeError(f"patched map is malformed: {verified.parse_warnings}")
    if int(verified.root.get("info/swim").value) != 0:
        raise RuntimeError("client swim flag was not disabled")
    if child_values(verified.root.get("portal/11")) != PORTAL_FIELDS:
        raise RuntimeError("client fall portal verification failed")
    if result != original:
        arc.atomic_write_bytes(CLIENT, result)


def patch_server() -> None:
    text = SERVER.read_text(encoding="utf-8")
    if '<int name="swim" value="1"/>' in text:
        text = text.replace(
            '<int name="swim" value="1"/>', '<int name="swim" value="0"/>', 1
        )
    elif '<int name="swim" value="0"/>' not in text:
        raise RuntimeError("unexpected server info/swim contract")
    if OLD_PORTAL_XML in text:
        text = text.replace(OLD_PORTAL_XML, NEW_PORTAL_XML, 1)
    elif NEW_PORTAL_XML not in text:
        raise RuntimeError("unexpected server portal/11 contract")
    root = ET.fromstring(text)
    info = root.find('./imgdir[@name="info"]')
    portal = root.find('./imgdir[@name="portal"]/imgdir[@name="11"]')
    if info is None or info.find('./int[@name="swim"]').get("value") != "0":
        raise RuntimeError("server swim flag was not disabled")
    actual = tuple(
        (child.get("name"), child.get("value")) for child in portal
    ) if portal is not None else ()
    expected = tuple((name, str(value)) for name, value in PORTAL_FIELDS)
    if actual != expected:
        raise RuntimeError("server fall portal verification failed")
    if text != SERVER.read_text(encoding="utf-8"):
        arc.atomic_write_text(SERVER, text)


def main() -> int:
    patch_client()
    patch_server()
    print(
        "Lucid P2 map adjusted: client_paths=info/swim,portal/11 "
        "server_paths=info/swim,portal/11"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
