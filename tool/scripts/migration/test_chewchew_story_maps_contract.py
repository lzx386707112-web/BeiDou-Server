#!/usr/bin/env python3
"""Contract checks for the three legacy-compatible ChewChew story maps."""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

from wzpy import WzCanvasProperty, WzImage, WzKey, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402

import migrate_arcane_river_fields as arcane  # noqa: E402
import migrate_chewchew_story_maps as migration  # noqa: E402
from migrate_karing_later_stages import locate_records  # noqa: E402


KEY = WzKey.for_region("GMS")
CLIENT = ROOT / "clien/Data"
MAP_IDS = migration.MAP_IDS
YUMYUM_MAP_IDS = tuple(range(450015020, 450015301, 10))
YUMYUM_NPC_IDS = tuple(
    value
    for value in (
        *range(3004700, 3004730),
        3004780,
        3004781,
    )
    if value != 3004726
)
EXPECTED_NPCS = {
    450002021: (3003156, 3003165),
    450002023: (3003151, 3003153, 3003154, 3003155, 3003166),
    450002025: (3004726,),
}
EXPECTED_PORTALS = {
    450002021: (("sp", 0, 999999999, ""),),
    450002023: (
        ("sp", 0, 999999999, ""),
        ("in00", 2, 450002000, "out02"),
        ("out00", 2, 450002021, "sp"),
    ),
    450002025: (
        ("sp", 0, 999999999, ""),
        ("in00", 2, 450002000, "out05"),
        ("out00", 2, 450015020, "west00"),
    ),
}
MAP_NAMES = {
    450002021: ("啾啾艾爾蘭", "武藤上鎖的地方"),
    450002023: ("啾啾艾爾蘭", "村莊孤寂處"),
    450002025: ("藍色鯨魚山", "鯨魚山後方"),
}


def load(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=KEY, name=path.name)
    image.parse()
    assert not image.truncated, path
    assert image.parse_warnings == [], (path, image.parse_warnings)
    return image


def git_baseline(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def xml_node_span(text: str, tag: str, name: str, start: int, limit: int) -> tuple[int, int]:
    marker = re.compile(rf'<{tag}\b[^>]*\bname="{re.escape(name)}"[^>]*>')
    match = marker.search(text, start, limit)
    assert match is not None, (tag, name)
    depth = 0
    token = re.compile(rf'</?{tag}\b[^>]*>')
    for candidate in token.finditer(text, match.start(), limit):
        value = candidate.group(0)
        if value.startswith("</"):
            depth -= 1
            if depth == 0:
                return match.start(), candidate.end()
        elif not value.endswith("/>"):
            depth += 1
    raise AssertionError((tag, name, "unterminated"))


def xml_records(path: Path, text: str, parent_path: tuple[str, ...]):
    parent = ET.fromstring(text)
    parent_start, parent_end = 0, len(text)
    for segment in parent_path:
        parent = xml_child(parent, segment)
        assert parent is not None, (path, parent_path)
        parent_start, parent_end = xml_node_span(
            text, "imgdir", segment, parent_start, parent_end
        )
    names = tuple(child.get("name") for child in parent)
    records = {}
    for child in parent:
        name = child.get("name")
        assert name is not None
        start, end = xml_node_span(text, child.tag, name, parent_start, parent_end)
        records[name] = text[start:end]
    return names, records


def assert_xml_insertions(
    path: Path, parent: tuple[str, ...], inserted: tuple[str, ...]
) -> None:
    before_names, before = xml_records(
        path, git_baseline(path).decode("utf-8"), parent
    )
    after_names, after = xml_records(path, path.read_text(encoding="utf-8"), parent)
    assert after_names == (*before_names, *inserted), (path, parent, after_names)
    for name, record in before.items():
        assert after[name] == record, (path, parent, name)


def assert_only_xml_children_changed(
    path: Path, parent: tuple[str, ...], changed: set[str]
) -> None:
    before_names, before = xml_records(
        path, git_baseline(path).decode("utf-8"), parent
    )
    after_names, after = xml_records(path, path.read_text(encoding="utf-8"), parent)
    assert after_names == before_names
    for name, record in before.items():
        if name not in changed:
            assert after[name] == record, (path, parent, name)


def raw_records(path: Path, data: bytes, parent: tuple[str, ...]):
    image = WzImage.from_bytes(data, key=KEY, name=path.name)
    image.parse()
    assert not image.truncated and image.parse_warnings == []
    _, _, _, names, spans, _ = locate_records(image, data, parent)
    return names, {
        name: data[start:end] for name, (start, end) in zip(names, spans, strict=True)
    }


def assert_raw_insertions(path: Path, parent: tuple[str, ...], inserted: tuple[str, ...]) -> None:
    before_names, before = raw_records(path, git_baseline(path), parent)
    after_names, after = raw_records(path, path.read_bytes(), parent)
    assert after_names == (*before_names, *inserted), (path, parent, after_names)
    for name, record in before.items():
        assert after[name] == record, (path, parent, name)


def assert_only_raw_child_changed(
    path: Path, parent: tuple[str, ...], changed: str
) -> None:
    assert_only_raw_children_changed(path, parent, {changed})


def assert_only_raw_children_changed(
    path: Path, parent: tuple[str, ...], changed: set[str]
) -> None:
    before_names, before = raw_records(path, git_baseline(path), parent)
    after_names, after = raw_records(path, path.read_bytes(), parent)
    assert after_names == before_names
    for name, record in before.items():
        if name not in changed:
            assert after[name] == record, (path, parent, name)


def direct_values(node: WzSubProperty) -> dict[str, object]:
    return {child.name: getattr(child, "value", None) for child in node.children()}


def xml_child(node: ET.Element | None, name: str) -> ET.Element | None:
    if node is None:
        return None
    return next((child for child in node if child.get("name") == name), None)


def check_canvas_tree(node, label: str) -> tuple[int, int]:
    count = 0
    visible = 0
    for child, path in arcane.walk(node):
        if not isinstance(child, WzCanvasProperty):
            continue
        count += 1
        assert (int(child.format), int(child.format2)) == (1, 0), (label, path)
        bitmap = decode_canvas(child, region="GMS")
        assert bitmap.size == (int(child.width), int(child.height)), (label, path)
        if bitmap.getbbox() is not None:
            visible += 1
    return count, visible


def test_maps_and_portals() -> None:
    village = load(CLIENT / "Map/Map/Map4/450002000.img")
    village_portals = {
        arcane.child_value(entry, "pn") for entry in village.root.get("portal").children()
    }
    assert {"out02", "out05"} <= village_portals

    for map_id in MAP_IDS:
        image = load(CLIENT / f"Map/Map/Map4/{map_id}.img")
        assert {child.name for child in image.root.children()} <= migration.MAP_ROOTS
        info = image.root.child("info")
        assert isinstance(info, WzSubProperty)
        for name in migration.MAP_INFO_UNSUPPORTED:
            assert info.child(name) is None, (map_id, name)

        portal = image.root.child("portal")
        assert isinstance(portal, WzSubProperty)
        actual = []
        for entry in portal.children():
            values = direct_values(entry)
            assert "script" not in values
            assert not (set(values) & migration.PORTAL_UNSUPPORTED)
            actual.append((values["pn"], values["pt"], values["tm"], values["tn"]))
        assert tuple(actual) == EXPECTED_PORTALS[map_id]

        life = image.root.child("life")
        assert isinstance(life, WzSubProperty)
        npc_ids = tuple(
            int(arcane.child_value(entry, "id"))
            for entry in life.children()
            if arcane.child_value(entry, "type") == "n"
        )
        assert npc_ids == EXPECTED_NPCS[map_id]

        for layer in [child for child in image.root.children() if child.name.isdigit()]:
            objects = layer.child("obj")
            if not isinstance(objects, WzSubProperty):
                continue
            connect_count = sum(
                arcane.child_value(entry, "oS") == "connect" for entry in objects.children()
            )
            assert all(
                arcane.child_value(entry, "oS") == "connect"
                for entry in list(objects.children())[:connect_count]
            )
            if connect_count:
                assert [entry.name for entry in objects.children()] == [
                    str(index) for index in range(len(objects.children()))
                ]
            for entry in objects.children():
                assert not (set(direct_values(entry)) & migration.OBJ_UNSUPPORTED)
                if arcane.child_value(entry, "oS") == "connect":
                    assert arcane.child_value(entry, "l1") == "0"

        canvas_count, visible = check_canvas_tree(image.root, f"Map/{map_id}")
        assert canvas_count > 0 and visible > 0

        xml = ET.parse(
            ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
        ).getroot()
        xml_portal = xml_child(xml, "portal")
        xml_actual = []
        for entry in xml_portal or ():
            values = {child.get("name"): child.get("value") for child in entry}
            xml_actual.append(
                (values["pn"], int(values["pt"]), int(values["tm"]), values["tn"])
            )
        assert tuple(xml_actual) == EXPECTED_PORTALS[map_id]


def test_dependency_closure_and_canvases() -> None:
    for map_id in MAP_IDS:
        dependencies = arcane.collect_dependencies(
            load(CLIENT / f"Map/Map/Map4/{map_id}.img")
        )
        for (kind, name), branches in dependencies["assets"].items():
            asset = load(CLIENT / f"Map/{kind}/{name}.img")
            for branch in branches:
                assert asset.root.get(branch) is not None, (map_id, kind, name, branch)
        for npc_id in dependencies["npcs"]:
            assert (CLIENT / f"Npc/{npc_id:07d}.img").exists()

    affected = [
        (load(CLIENT / "Map/Back/chewchewIsland.img").root.get("back/51"), "back/51", True),
        (load(CLIENT / "Map/Back/chewchewIsland.img").root.get("back/52"), "back/52", True),
        (
            load(CLIENT / "Map/Obj/chewchewIsland.img").root.get("MainField/muto/8"),
            "muto/8",
            True,
        ),
        (
            load(CLIENT / "Map/Obj/chewchewIsland.img").root.get("MainField/muto/9"),
            "muto/9",
            False,
        ),
        (load(CLIENT / "Map/Obj/YumYum.img").root, "YumYum", True),
    ]
    for node, label, expect_visible in affected:
        assert node is not None
        count, visible = check_canvas_tree(node, label)
        assert count > 0, label
        if expect_visible:
            assert visible > 0, label

    for npc_id in migration.NPC_IDS:
        image = load(CLIENT / f"Npc/{npc_id:07d}.img")
        count, visible = check_canvas_tree(image.root, f"Npc/{npc_id}")
        assert count > 0 and visible > 0
        ET.parse(ROOT / f"gms-server/wz/Npc.wz/{npc_id:07d}.img.xml")

    ET.parse(ROOT / "gms-server/wz/Map.wz/Obj/YumYum.img.xml")
    shared_xml = ET.parse(
        ROOT / "gms-server/wz/Map.wz/Obj/chewchewIsland.img.xml"
    ).getroot()
    assert xml_child(xml_child(xml_child(shared_xml, "MainField"), "muto"), "8") is not None
    assert xml_child(xml_child(xml_child(shared_xml, "MainField"), "muto"), "9") is not None


def test_strings() -> None:
    client_map = load(CLIENT / "String/Map.img")
    for map_id, expected in MAP_NAMES.items():
        node = client_map.root.get(f"grandis/{map_id}")
        assert isinstance(node, WzSubProperty)
        assert (arcane.child_value(node, "streetName"), arcane.child_value(node, "mapName")) == expected
        for tree in ("wz", "wz-zh-CN"):
            root = ET.parse(ROOT / f"gms-server/{tree}/String.wz/Map.img.xml").getroot()
            assert xml_child(xml_child(root, "grandis"), str(map_id)) is not None

    client_npc = load(CLIENT / "String/Npc.img")
    server_npc = ET.parse(ROOT / "gms-server/wz/String.wz/Npc.img.xml").getroot()
    for npc_id in migration.NPC_IDS:
        assert client_npc.root.get(str(npc_id)) is not None
        assert xml_child(server_npc, str(npc_id)) is not None


def test_existing_img_raw_records_are_preserved() -> None:
    background = CLIENT / "Map/Back/chewchewIsland.img"
    assert_only_raw_child_changed(background, (), "back")
    assert_only_raw_children_changed(background, ("back",), {"51", "52"})

    asset = CLIENT / "Map/Obj/chewchewIsland.img"
    assert_only_raw_child_changed(asset, (), "MainField")
    assert_only_raw_child_changed(asset, ("MainField",), "muto")
    assert_raw_insertions(asset, ("MainField", "muto"), ("8", "9"))

    map_string = CLIENT / "String/Map.img"
    assert_only_raw_child_changed(map_string, (), "grandis")
    assert_raw_insertions(
        map_string,
        ("grandis",),
        tuple(str(value) for value in (*MAP_IDS, *YUMYUM_MAP_IDS)),
    )
    assert_raw_insertions(
        CLIENT / "String/Npc.img",
        (),
        tuple(str(value) for value in (*migration.NPC_IDS, *YUMYUM_NPC_IDS)),
    )


def test_existing_xml_records_are_preserved() -> None:
    background = ROOT / "gms-server/wz/Map.wz/Back/chewchewIsland.img.xml"
    assert_only_xml_children_changed(background, (), {"back"})
    assert_only_xml_children_changed(background, ("back",), {"51", "52"})

    asset = ROOT / "gms-server/wz/Map.wz/Obj/chewchewIsland.img.xml"
    assert_only_xml_children_changed(asset, (), {"MainField"})
    assert_only_xml_children_changed(asset, ("MainField",), {"muto"})
    assert_xml_insertions(asset, ("MainField", "muto"), ("8", "9"))

    for tree in ("wz", "wz-zh-CN"):
        map_string = ROOT / f"gms-server/{tree}/String.wz/Map.img.xml"
        assert_only_xml_children_changed(map_string, (), {"grandis"})
        assert_xml_insertions(
            map_string,
            ("grandis",),
            tuple(str(value) for value in (*MAP_IDS, *YUMYUM_MAP_IDS)),
        )
    assert_xml_insertions(
        ROOT / "gms-server/wz/String.wz/Npc.img.xml",
        (),
        tuple(str(value) for value in (*migration.NPC_IDS, *YUMYUM_NPC_IDS)),
    )


def test_generator_uses_incremental_shared_img_edits() -> None:
    source = Path(migration.__file__).read_text(encoding="utf-8")
    assert "insert_raw_record" in source
    assert "save_as(" not in source
