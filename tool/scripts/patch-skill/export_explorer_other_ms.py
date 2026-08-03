#!/usr/bin/env python3
"""Export TMS MS metadata for the remaining supported Explorer V/VI attacks."""

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
DEFAULT_OUTPUT = TMS_ROOT / "MapleStory-MS-Export/ExplorerOther"

GROUPS = {
    "214": (PACK_ROOT / "Skill_00003.ms", "Skill/214.img"),
    "224": (PACK_ROOT / "Skill_00003.ms", "Skill/224.img"),
    "234": (PACK_ROOT / "Skill_00003.ms", "Skill/234.img"),
    "314": (PACK_ROOT / "Skill_00004.ms", "Skill/314.img"),
    "324": (PACK_ROOT / "Skill_00004.ms", "Skill/324.img"),
    "40002": (PACK_ROOT / "Skill_00005.ms", "Skill/40002.img"),
    "40003": (PACK_ROOT / "Skill_00005.ms", "Skill/40003.img"),
    "40004": (PACK_ROOT / "Skill_00005.ms", "Skill/40004.img"),
    "40005": (PACK_ROOT / "Skill_00005.ms", "Skill/40005.img"),
    "414": (PACK_ROOT / "Skill_00005.ms", "Skill/414.img"),
    "424": (PACK_ROOT / "Skill_00006.ms", "Skill/424.img"),
    "514": (PACK_ROOT / "Skill_00006.ms", "Skill/514.img"),
    "524": (PACK_ROOT / "Skill_00006.ms", "Skill/524.img"),
}

# Only the four class-specific V skill families are selected. Common V skills and
# the families belonging to non-Explorer jobs are deliberately excluded.
V_SKILL_IDS = {
    "40002": {
        400021001, 400021002, 400021028, 400021029, 400021030, 400021031, 400021032,
        400021033, 400021040, 400021066, 400021067, 400021070, 400021077,
        400021086, 400021094, 400021101, 400021102, 400021103, 400021112,
    },
    "40003": {
        400031002, 400031006, 400031010, 400031015, 400031016, 400031020,
        400031021, 400031025, 400031028, 400031029, 400031053, 400031054,
        400031055, 400031056,
    },
    "40004": {
        400041001, 400041002, 400041003, 400041004, 400041005, 400041020,
        400041025, 400041026, 400041027, 400041038, 400041039, 400041059,
        400041060, 400041069, 400041070, 400041071, 400041072, 400041073,
    },
    "40005": {
        400051002, 400051003, 400051006, 400051015, 400051021, 400051040,
        400051042, 400051049, 400051050, 400051070, 400051071, 400051073,
        400051081,
    },
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
        return ET.Element("vector", {"name": prop.name, "x": str(prop.x), "y": str(prop.y)})
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


def has_damage(skill: WzSubProperty) -> bool:
    return skill.get("common/damage") is not None


def selected_skills(group: str, root: WzSubProperty) -> list[WzSubProperty]:
    skills = root.get("skill")
    if not isinstance(skills, WzSubProperty):
        raise RuntimeError(f"missing skill root in {group}")
    if group in V_SKILL_IDS:
        selected = [skills.get(str(skill_id)) for skill_id in sorted(V_SKILL_IDS[group])]
        return [skill for skill in selected if isinstance(skill, WzSubProperty)]
    return [skill for skill in skills.children() if isinstance(skill, WzSubProperty) and has_damage(skill)]


def export_group(group: str, extracted: Path, output: Path) -> None:
    image = WzImage.from_bytes(
        extracted.read_bytes(), key=WzKey.for_region("BMS"), name=extracted.name
    )
    root = image.parse()
    for skill in selected_skills(group, root):
        element = ET.Element("skill", {"id": skill.name, "sourceGroup": group})
        for child in skill.children():
            element.append(serialize_property(child))
        ET.indent(element, space="  ")
        path = output / f"{skill.name}.xml"
        ET.ElementTree(element).write(path, encoding="utf-8", xml_declaration=True)
        print(f"exported: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--group", choices=("all", *GROUPS), default="all")
    args = parser.parse_args()
    if not MS_PROBE.is_file():
        raise RuntimeError(f"missing MSProbe: {MS_PROBE}")
    args.output.mkdir(parents=True, exist_ok=True)
    selected = GROUPS if args.group == "all" else {args.group: GROUPS[args.group]}
    with tempfile.TemporaryDirectory(prefix="explorer-other-ms-") as directory:
        temporary = Path(directory)
        for group, (pack, prefix) in selected.items():
            group_output = temporary / group
            subprocess.run(
                ["/opt/homebrew/bin/dotnet", str(MS_PROBE), str(pack), str(group_output), prefix],
                check=True,
            )
            extracted = group_output / f"Skill_{group}.img"
            if not extracted.is_file():
                raise RuntimeError(f"MSProbe did not extract {prefix}")
            export_group(group, extracted, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
