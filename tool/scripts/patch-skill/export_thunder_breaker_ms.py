#!/usr/bin/env python3
"""Export the TMS Thunder Breaker MS skill metadata used by the migrator."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.properties import (  # noqa: E402
    WzCanvasProperty,
    WzDoubleProperty,
    WzFloatProperty,
    WzIntProperty,
    WzLongProperty,
    WzShortProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
    WzVideoProperty,
)


TMS_ROOT = Path("/Users/lizixian/Documents/mxd/TMS")
MS_PROBE = TMS_ROOT / "black_mage_report_tools/ms_probe/bin/Debug/net8.0/MSProbe.dll"
PACK_ROOT = TMS_ROOT / "MapleStory/Data/Packs"
DEFAULT_OUTPUT = TMS_ROOT / "MapleStory-MS-Export/ThunderBreaker"
GROUPS = {
    "1514": (PACK_ROOT / "Skill_00001.ms", "Skill/1514.img"),
    "40005": (PACK_ROOT / "Skill_00005.ms", "Skill/40005.img"),
}
SKILL_IDS = {
    "1514": (
        15141000, 15141003, 15141004, 15141006, 15141007,
        15141500, 15141501, 15141502, 15141503,
    ),
    "40005": (
        400051015, 400051016, 400051058, 400051059, 400051060,
        400051061, 400051062, 400051063, 400051064, 400051065,
        400051066, 400051067,
    ),
}


def scalar_element(tag: str, prop) -> ET.Element:
    return ET.Element(tag, {"name": prop.name, "value": str(prop.value)})


def serialize_property(prop) -> ET.Element:
    if isinstance(prop, WzCanvasProperty):
        element = ET.Element("canvas", {
            "name": prop.name,
            "width": str(prop.width),
            "height": str(prop.height),
            "format": str(prop.format),
            "scale": str(prop.format2),
        })
        for child in prop.children():
            element.append(serialize_property(child))
        return element
    if isinstance(prop, WzVideoProperty):
        element = ET.Element("video", {
            "name": prop.name,
            "videoType": str(prop.video_type),
            "bytes": str(prop._data_length),
        })
        for child in prop.children():
            element.append(serialize_property(child))
        return element
    if isinstance(prop, WzSubProperty):
        element = ET.Element("imgdir", {"name": prop.name, "javaType": "WzListProperty"})
        for child in prop.children():
            element.append(serialize_property(child))
        return element
    if isinstance(prop, WzVectorProperty):
        return ET.Element("vector", {
            "name": prop.name,
            "x": str(prop.x),
            "y": str(prop.y),
        })
    if isinstance(prop, WzUolProperty):
        return scalar_element("uol", prop)
    if isinstance(prop, WzStringProperty):
        return scalar_element("string", prop)
    if isinstance(prop, WzIntProperty):
        return scalar_element("int", prop)
    if isinstance(prop, WzShortProperty):
        return scalar_element("short", prop)
    if isinstance(prop, WzLongProperty):
        return scalar_element("long", prop)
    if isinstance(prop, WzFloatProperty):
        return scalar_element("float", prop)
    if isinstance(prop, WzDoubleProperty):
        return scalar_element("double", prop)
    raise RuntimeError(f"unsupported MS property: {prop.name} ({type(prop).__name__})")


def export_group(group: str, extracted: Path, output: Path) -> None:
    image = WzImage.from_bytes(
        extracted.read_bytes(), key=WzKey.for_region("BMS"), name=extracted.name
    )
    root = image.parse()
    for skill_id in SKILL_IDS[group]:
        skill = root.get(f"skill/{skill_id}")
        if not isinstance(skill, WzSubProperty):
            raise RuntimeError(f"missing MS skill {skill_id} in {extracted}")
        element = ET.Element("skill", {"id": str(skill_id)})
        for child in skill.children():
            element.append(serialize_property(child))
        ET.indent(element, space="  ")
        path = output / f"{skill_id}.xml"
        ET.ElementTree(element).write(path, encoding="utf-8", xml_declaration=True)
        print(f"exported: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not MS_PROBE.is_file():
        raise RuntimeError(f"missing MSProbe: {MS_PROBE}")
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="thunder-breaker-ms-") as directory:
        temporary = Path(directory)
        for group, (pack, prefix) in GROUPS.items():
            subprocess.run(
                ["/opt/homebrew/bin/dotnet", str(MS_PROBE), str(pack), str(temporary), prefix],
                check=True,
            )
            extracted = temporary / f"Skill_{group}.img"
            if not extracted.is_file():
                raise RuntimeError(f"MSProbe did not extract {prefix}")
            export_group(group, extracted, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
