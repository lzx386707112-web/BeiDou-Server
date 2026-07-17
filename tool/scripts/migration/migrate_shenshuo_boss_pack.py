#!/usr/bin/env python3
"""Migrate the requested Shenshuo bosses and visually complete arena maps."""

from __future__ import annotations

import io
import argparse
import re
import struct
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT.parent / "神说" / "Data"
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
sys.path.insert(0, str(ROOT / "tool" / "scripts" / "patch-boss"))

from wzpy import WzCanvasProperty, WzImage, WzIntProperty, WzKey, WzStringProperty, WzSubProperty, WzUolProperty  # noqa: E402
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import _encode_property_body, _tag_for, encode_compressed_int, encode_image_body, encode_string_block  # noqa: E402
from patch_lucid_boss_compat import (  # noqa: E402
    atomic_write_bytes,
    atomic_write_text,
    clone_property,
    gms_reader,
    img_to_xml,
    remove_child,
    replace_child,
    set_int,
    set_string,
    source_img,
)


TARGET_KEY = WzKey.for_region("GMS")
CLIENT_HP = 2_000_000_000
SERVER_HP = 30_000_000_000
SERVER_EVA_CAP = 200

MAIN_MOBS = {
    8870000: "希拉",
    8870200: "希拉（白发模式）",
    8880200: "卡翁",
    8880400: "觉醒希拉",
    8645009: "亲卫队长敦凯尔",
    8880700: "守护天使绿水灵",
    8880803: "监视者卡洛斯",
    8880820: "沦陷的监视者卡洛斯",
}

SUPPORT_MOBS = {
    8870004: "血牙",
    8870201: "希拉技能专用",
    8880401: "黑掌",
    8880403: "死灵斯乌",
    8880404: "死灵戴米安",
    8645010: "神秘原子集合",
    8645012: "超越三角锥",
    8645014: "上升菱锥",
}

MOB_NAMES = MAIN_MOBS | SUPPORT_MOBS

SAFE_SKILLS = {
    8870000: ((120, 8, 3), (121, 4, 3), (128, 1, 4), (110, 5, 2), (131, 12, 4), (132, 2, 3), (134, 2, 1), (145, 2, 2)),
    8870200: ((145, 2, 2), (128, 1, 3), (133, 1, 4), (114, 37, 5), (127, 2, 6), (132, 2, 7), (126, 1, 8), (120, 5, 1)),
    8880200: ((127, 1, 1), (126, 1, 2), (140, 5, 3), (114, 4, 4), (141, 4, 1)),
    8880400: ((128, 1, 1), (132, 2, 2), (145, 2, 3), (127, 2, 4), (140, 5, 5)),
    8645009: ((141, 4, 3), (145, 2, 2), (140, 5, 1)),
    8880700: ((120, 5, 3), (128, 1, 3), (127, 2, 2), (140, 5, 4), (141, 4, 4), (145, 2, 2), (133, 1, 3)),
}

# These are the best complete visual arenas actually present in the commercial
# client. Some are compatibility arenas because the official map id is absent.
MAPS = {
    262030300: "希拉之塔",
    262031300: "白发希拉之塔",
    450010100: "觉醒希拉·欲望祭坛",
    221040001: "卡翁·地球防御本部",
    450009400: "敦凯尔·泰涅布利斯",
    900000207: "守护天使绿水灵领地",
    410002060: "监视者卡洛斯战场",
    410002061: "沦陷卡洛斯战场",
}
MAP_SOURCES = {410002061: 410002060}
RELATED_MAPS = (262000000, 262030000, 262030310, 262031310, 450011990)
SAFE_MAP_ALIASES = {}
RETRY_MAPS = {}
SAME_FIELD_RETRY_MAPS = {
    262030300: (8870000, 1092, 196, "out00", 1000, 166, -700, 166),
    262031300: (8870200, 1092, 196, "out00", 1000, 166, -700, 166),
    450010100: (8880400, 855, 266, "pt_out", 780, 236, -700, 236),
    221040001: (8880200, -1215, 866, "out00", -1300, 836, -2250, 836),
    450009400: (8645009, -1, -157, "out00", -1, -187, -620, -187),
    900000207: (8880700, 703, -1394, "portal", 703, -1404, -8, -1130),
    410002060: (8880803, 900, 325, "out001", 700, 295, -673, 297),
    410002061: (8880820, 900, 325, "out001", 700, 295, -673, 297),
}
MAP_RETURN_OVERRIDES = {
    262030300: 262030300,
    262031300: 262031300,
    450010100: 450010100,
    221040001: 221040001,
    450009400: 450009400,
    900000207: 900000207,
    410002060: 410002060,
    410002061: 410002061,
    450009301: 910000000,
    900000206: 910000000,
}
MAP_BOSSES = {
    262030300: 8870000,
    262031300: 8870200,
    450010100: 8880400,
    221040001: 8880200,
    450009400: 8645009,
    900000207: 8880700,
    410002060: 8880803,
    410002061: 8880820,
}

MAP_UNSUPPORTED_ROOTS = ("particle", "mobTeleport", "userSit", "clock", "area")
INFO_UNSUPPORTED = (
    "finalmaxHP", "ignoreFieldOut", "HPgaugeHide", "category", "ignoreMoveImpact",
    "wp", "skillAfter", "attack", "buff", "phase", "setItemDropBlock",
)
MAP_INFO_UNSUPPORTED = (
    "AmbientBGM", "AmbientBGMv", "ReviveCurFieldOfNoTransfer",
    "ReviveCurFieldOfNoTransferNotDamaged", "ReviveCurFieldOfNoTransferPoint",
    "barrierArc", "barrierAut", "consumeItemCoolTime", "fieldLimit2", "fieldType",
    "largeSplit", "limitUpgradeItem", "limitUseShop", "lvLimit", "mode", "noChair",
    "noHekatonEffect", "qrLimit", "quarterView", "remoteEffect", "reviveCurField",
    "specialSound",
)


def walk(node, path: str = ""):
    yield node, path
    if hasattr(node, "children"):
        for child in node.children():
            child_path = f"{path}/{child.name}" if path else child.name
            yield from walk(child, child_path)


def reencode_argb4444(node) -> None:
    if isinstance(node, WzCanvasProperty) and node.has_pixels():
        try:
            image = decode_canvas(node, region="EMS")
        except Exception:
            # Commercial packs occasionally contain deliberately empty/broken
            # decorative canvases. Preserve the node shape with a transparent
            # pixel so the old client does not abort the whole IMG load.
            image = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            node.width = 1
            node.height = 1
        node.format = 1
        node.format2 = 0
        node._png_data = encode_canvas_payload(
            image, 1, int(node.width), int(node.height), key=TARGET_KEY, listwz=False
        )
        node._png_length = len(node._png_data)
    if hasattr(node, "children"):
        for child in node.children():
            reencode_argb4444(child)


def ensure_action(root: WzSubProperty, action: int) -> None:
    name = f"skill{action}"
    if root.child(name) is not None:
        return
    for candidate in (f"attack{action}", "attack1", "skill1", "stand", "move"):
        source = root.child(candidate)
        if source is not None:
            replace_child(root, clone_property(source, name, root))
            return
    raise ValueError(f"{root.name}: no visual source for {name}")


def set_skills(root: WzSubProperty, mob_id: int) -> None:
    info = root.child("info")
    remove_child(info, "skill")
    specs = SAFE_SKILLS.get(mob_id, ())
    if not specs:
        return
    skills = WzSubProperty("skill", info)
    for index, (skill_id, level, action) in enumerate(specs):
        ensure_action(root, action)
        entry = WzSubProperty(str(index), skills)
        entry.add(WzIntProperty("skill", skill_id, entry))
        entry.add(WzIntProperty("level", level, entry))
        entry.add(WzIntProperty("action", action, entry))
        skills.add(entry)
    replace_child(info, skills)


def repair_source_links(img: WzImage, mob_id: int) -> None:
    if mob_id == 8880700:
        broken = img.root.get("skill1/0/_inlink")
        if broken is not None and img.root.get(str(broken.value)) is None:
            broken._value = "attack3/0"

    if mob_id != 8880820:
        return
    ordinary = source_img(SRC / "Mob/8880803.img")
    for node, path in list(walk(img.root)):
        if not isinstance(node, WzUolProperty) or node.name != "_outlink":
            continue
        value = str(node.value)
        if not value.startswith(("Mob/8880800.img/", "Mob/8880801.img/")):
            continue
        parent = node.parent
        target_path = None
        if "/attack3/info/hit/" in value:
            index = int(value.rsplit("/", 1)[-1])
            target_path = f"attack3/info/hit/{min(index, 7)}"
        elif "/attack2/info/hit/" in value:
            index = int(value.rsplit("/", 1)[-1])
            target_path = f"attack2/info/hit/{index % 8}"
        if target_path is None:
            parent._children.pop(node.name, None)
            continue
        target = ordinary.root.get(target_path)
        if target is None:
            parent._children.pop(node.name, None)
            continue
        parent._children.pop(node.name, None)
        if isinstance(target, WzCanvasProperty):
            replacement = clone_property(target, parent.name, parent.parent)
            parent.parent._children[parent.name] = replacement


def sanitize_mob(img: WzImage, mob_id: int, server: bool) -> None:
    repair_source_links(img, mob_id)
    info = img.root.child("info")
    if info is None:
        raise ValueError(f"{mob_id}: missing info")
    for name in INFO_UNSUPPORTED:
        remove_child(info, name)
    remove_child(info, "revive")
    if mob_id in MAIN_MOBS:
        set_string(info, "maxHP", str(SERVER_HP)) if server else set_int(info, "maxHP", CLIENT_HP)
        if server and info.child("eva") is not None and int(info.child("eva").value) > SERVER_EVA_CAP:
            set_int(info, "eva", SERVER_EVA_CAP)
        set_int(info, "boss", 1)
        set_int(info, "PDRate", 50)
        set_int(info, "MDRate", 50)
    for defense, attack in (("PDDamage", "PADamage"), ("MDDamage", "MADamage")):
        if info.child(defense) is None:
            attack_node = info.child(attack)
            set_int(info, defense, int(attack_node.value) if attack_node is not None else 1000)
    set_skills(img.root, mob_id)


def migrate_mob(mob_id: int) -> None:
    source = SRC / f"Mob/{mob_id}.img"
    client = source_img(source)
    sanitize_mob(client, mob_id, server=False)
    reencode_argb4444(client.root)
    atomic_write_bytes(ROOT / f"clien/Data/Mob/{mob_id}.img", encode_image_body(client, gms_reader()))

    server = source_img(source)
    sanitize_mob(server, mob_id, server=True)
    atomic_write_text(
        ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml",
        img_to_xml(server, root_name=f"{mob_id}.img"),
    )


def sanitize_map(img: WzImage, map_id: int | None = None) -> None:
    for name in MAP_UNSUPPORTED_ROOTS:
        remove_child(img.root, name)
    info = img.root.child("info")
    if info is not None:
        for name in ("fieldScript", "onFirstUserEnter", "onUserEnter", "standAlone", "partyStandAlone", "noMapCmd"):
            remove_child(info, name)
        for name in MAP_INFO_UNSUPPORTED:
            remove_child(info, name)
        if map_id in MAP_RETURN_OVERRIDES:
            target = MAP_RETURN_OVERRIDES[map_id]
            set_int(info, "returnMap", target)
            set_int(info, "forcedReturn", target)
    portal = img.root.child("portal")
    if portal is not None:
        for entry in portal.children():
            for name in ("delay", "hideTooltip", "onlyOnce"):
                remove_child(entry, name)
            for name in ("hRange", "horizontalImpact", "vRange"):
                remove_child(entry, name)
            script = entry.child("script")
            if script is not None and (map_id in MAPS or str(script.value) == ""):
                remove_child(entry, "script")
            portal_name = entry.child("pn")
            portal_name = "" if portal_name is None else str(portal_name.value)
            if map_id == 450009301 and portal_name == "down00":
                remove_child(entry, "script")
                set_int(entry, "tm", 910000000)
                set_string(entry, "tn", "sp")
            elif map_id == 262030310 and portal_name == "in00":
                remove_child(entry, "script")
                set_int(entry, "tm", 262030300)
                set_string(entry, "tn", "sp")
            elif map_id == 262031310 and portal_name == "in00":
                remove_child(entry, "script")
                set_int(entry, "tm", 262031300)
                set_string(entry, "tn", "sp")
            elif map_id == 262000000 and portal_name == "out00":
                remove_child(entry, "script")
                set_int(entry, "tm", 910000000)
                set_string(entry, "tn", "sp")
            elif map_id == 262000000 and portal_name == "UIOpen":
                remove_child(entry, "script")
        if map_id in SAME_FIELD_RETRY_MAPS:
            _, _, _, retry_portal_name, retry_x, retry_y, rest_x, rest_y = SAME_FIELD_RETRY_MAPS[map_id]
            rest_portal = portal.child("0")
            if rest_portal is None:
                raise ValueError(f"{map_id}: missing portal 0")
            set_int(rest_portal, "x", rest_x)
            set_int(rest_portal, "y", rest_y)

            retry_portal = next(
                (
                    entry for entry in portal.children()
                    if entry.child("pn") is not None and str(entry.child("pn").value) == retry_portal_name
                ),
                None,
            )
            if retry_portal is None:
                raise ValueError(f"{map_id}: missing retry portal {retry_portal_name}")
            set_int(retry_portal, "tm", 999999999)
            set_string(retry_portal, "tn", "")
            set_string(retry_portal, "script", "shenshuoBossRetry")

            retry_spawn = next(
                (
                    entry for entry in portal.children()
                    if entry.child("pn") is not None and str(entry.child("pn").value) == "bossRetry"
                ),
                None,
            )
            if retry_spawn is None:
                numeric = [int(entry.name) for entry in portal.children() if entry.name.isdigit()]
                retry_spawn = WzSubProperty(str(max(numeric, default=-1) + 1), portal)
                retry_spawn.add(WzIntProperty("x", retry_x, retry_spawn))
                retry_spawn.add(WzIntProperty("y", retry_y, retry_spawn))
                retry_spawn.add(WzIntProperty("pt", 8, retry_spawn))
                retry_spawn.add(WzIntProperty("tm", 999999999, retry_spawn))
                retry_spawn.add(WzStringProperty("tn", "", retry_spawn))
                retry_spawn.add(WzStringProperty("pn", "bossRetry", retry_spawn))
                portal.add(retry_spawn)
            else:
                set_int(retry_spawn, "x", retry_x)
                set_int(retry_spawn, "y", retry_y)
                set_int(retry_spawn, "pt", 8)
    remove_child(img.root, "noSkill")
    for layer in [node for node in img.root.children() if node.name.isdigit()]:
        objects = layer.child("obj")
        if objects is None:
            continue
        for entry in objects.children():
            for name in ("SN0", "SN_count", "dynamic", "move", "name", "piece", "spineAni"):
                remove_child(entry, name)
    back = img.root.child("back")
    if back is not None:
        for entry in back.children():
            for name in ("backTags", "w", "wx", "wy"):
                remove_child(entry, name)


def map_dependencies(img: WzImage) -> set[tuple[str, str]]:
    found = set()
    for node, _ in walk(img.root):
        value = getattr(node, "value", None)
        if value is None or value == "":
            continue
        if node.name == "bS":
            found.add(("Back", str(value)))
        elif node.name == "oS":
            found.add(("Obj", str(value)))
        elif node.name == "tS":
            found.add(("Tile", str(value)))
    return found


def migrate_visual_img(source: Path, client_path: Path) -> None:
    img = source_img(source)
    reencode_argb4444(img.root)
    atomic_write_bytes(client_path, encode_image_body(img, gms_reader()))


def migrate_map(map_id: int) -> None:
    source_id = MAP_SOURCES.get(map_id, map_id)
    source = SRC / f"Map/Map/Map{str(source_id)[0]}/{source_id}.img"
    if not source.exists():
        raise FileNotFoundError(source)
    client = source_img(source)
    deps = map_dependencies(client)
    sanitize_map(client, map_id)
    reencode_argb4444(client.root)
    client_path = ROOT / f"clien/Data/Map/Map/Map{str(map_id)[0]}/{map_id}.img"
    atomic_write_bytes(client_path, encode_image_body(client, gms_reader()))

    server = source_img(source)
    sanitize_map(server, map_id)
    add_server_boss_spawn(server.root, MAP_BOSSES[map_id])
    atomic_write_text(
        ROOT / f"gms-server/wz/Map.wz/Map/Map{str(map_id)[0]}/{map_id}.img.xml",
        img_to_xml(server, root_name=f"{map_id}.img"),
    )

    for kind, name in sorted(deps):
        dep = SRC / f"Map/{kind}/{name}.img"
        if dep.exists():
            migrate_visual_img(dep, ROOT / f"clien/Data/Map/{kind}/{name}.img")


def migrate_related_map(map_id: int) -> None:
    if map_id in SAFE_MAP_ALIASES:
        build_safe_map_alias(map_id, SAFE_MAP_ALIASES[map_id])
        return
    source = SRC / f"Map/Map/Map{str(map_id)[0]}/{map_id}.img"
    client = source_img(source)
    deps = map_dependencies(client)
    sanitize_map(client, map_id)
    reencode_argb4444(client.root)
    atomic_write_bytes(
        ROOT / f"clien/Data/Map/Map/Map{str(map_id)[0]}/{map_id}.img",
        encode_image_body(client, gms_reader()),
    )
    server = source_img(source)
    sanitize_map(server, map_id)
    if map_id == 450009301:
        # The server only needs collision and portals. Keeping modern visual
        # layers here makes the old map loader parse nodes the client alone uses.
        for child in list(server.root.children()):
            if child.name.isdigit() or child.name == "miniMap":
                remove_child(server.root, child.name)
        back = server.root.child("back")
        if back is not None:
            prune_children(back, set())
    atomic_write_text(
        ROOT / f"gms-server/wz/Map.wz/Map/Map{str(map_id)[0]}/{map_id}.img.xml",
        img_to_xml(server, root_name=f"{map_id}.img"),
    )
    for kind, name in sorted(deps):
        dep = SRC / f"Map/{kind}/{name}.img"
        target = ROOT / f"clien/Data/Map/{kind}/{name}.img"
        if dep.exists() and not target.exists():
            migrate_visual_img(dep, target)


def configure_retry_map(root: WzSubProperty, map_id: int) -> None:
    _, _, _, _, _, retry_portal_name = RETRY_MAPS[map_id]

    # Rest maps must never load modern or missing life resources. Their client
    # visuals remain intact; the server only needs collision and portals.
    remove_child(root, "life")
    root.add(WzSubProperty("life", root))

    # The old client supports map layers 0-7. Preserve any layer-8 objects by
    # merging them into layer 7, then remove the unsupported extra layer.
    extra_layer = root.child("8")
    if extra_layer is not None:
        target_layer = root.child("7")
        source_objects = extra_layer.child("obj")
        target_objects = target_layer.child("obj") if target_layer is not None else None
        if source_objects is not None and target_objects is not None:
            numeric = [int(node.name) for node in target_objects.children() if node.name.isdigit()]
            next_name = max(numeric, default=-1) + 1
            for entry in list(source_objects.children()):
                source_objects._children.pop(entry.name, None)
                entry.name = str(next_name)
                target_objects.add(entry)
                next_name += 1
        remove_child(root, "8")

    portals = root.child("portal")
    retry_portal = next(
        (
            entry for entry in portals.children()
            if entry.child("pn") is not None and str(entry.child("pn").value) == retry_portal_name
        ),
        None,
    ) if portals is not None else None
    if retry_portal is None:
        raise ValueError(f"{map_id}: missing retry portal {retry_portal_name}")
    set_int(retry_portal, "tm", 999999999)
    set_string(retry_portal, "tn", "")
    set_string(retry_portal, "script", "shenshuoBossRetry")


def migrate_retry_map(map_id: int) -> None:
    source_id, _, _, _, _, _ = RETRY_MAPS[map_id]
    source = SRC / f"Map/Map/Map{str(source_id)[0]}/{source_id}.img"

    client = source_img(source)
    deps = map_dependencies(client)
    sanitize_map(client, map_id)
    configure_retry_map(client.root, map_id)
    reencode_argb4444(client.root)
    atomic_write_bytes(
        ROOT / f"clien/Data/Map/Map/Map{str(map_id)[0]}/{map_id}.img",
        encode_image_body(client, gms_reader()),
    )

    server = source_img(source)
    sanitize_map(server, map_id)
    configure_retry_map(server.root, map_id)
    for child in list(server.root.children()):
        if child.name.isdigit() or child.name == "miniMap":
            remove_child(server.root, child.name)
    back = server.root.child("back")
    if back is not None:
        prune_children(back, set())
    atomic_write_text(
        ROOT / f"gms-server/wz/Map.wz/Map/Map{str(map_id)[0]}/{map_id}.img.xml",
        img_to_xml(server, root_name=f"{map_id}.img"),
    )

    for kind, name in sorted(deps):
        dep = SRC / f"Map/{kind}/{name}.img"
        target = ROOT / f"clien/Data/Map/{kind}/{name}.img"
        if dep.exists() and not target.exists():
            migrate_visual_img(dep, target)


def build_safe_map_alias(map_id: int, template_id: int) -> None:
    template_client = ROOT / f"clien/Data/Map/Map/Map{str(template_id)[0]}/{template_id}.img"
    atomic_write_bytes(
        ROOT / f"clien/Data/Map/Map/Map{str(map_id)[0]}/{map_id}.img",
        template_client.read_bytes(),
    )
    template_server = ROOT / f"gms-server/wz/Map.wz/Map/Map{str(template_id)[0]}/{template_id}.img.xml"
    text = template_server.read_text(encoding="utf-8")
    text = text.replace(f'<imgdir name="{template_id}.img">', f'<imgdir name="{map_id}.img">', 1)
    atomic_write_text(
        ROOT / f"gms-server/wz/Map.wz/Map/Map{str(map_id)[0]}/{map_id}.img.xml",
        text,
    )


def prune_children(node, allowed: set[str]) -> None:
    for name in list(node._children):
        if name not in allowed:
            node._children.pop(name, None)


def build_dunkel_visual_pack() -> None:
    specs = (
        ("Obj", "BM1", "DunkelBM1", {
            "1-3": {"handrail": {"0", "1"}},
            "foothold": {"1-3_base": {str(i) for i in range(8)}},
            "boss": {"spine": {"0"}},
        }),
        ("Obj", "event", "DunkelEvent", {
            "2013newyear": {"block": {"0"}},
        }),
        ("Back", "BM1_2", "DunkelBM1_2", {
            "back": {str(i) for i in (0, 1, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 25)},
            "ani": {str(i) for i in (0, 1, 2, 3)},
        }),
        ("Back", "BM1_3", "DunkelBM1_3", {
            "back": {str(i) for i in range(12)},
            "ani": {str(i) for i in (0, 1, 4, 11)},
        }),
    )
    for kind, source_name, target_name, tree in specs:
        source_path = ROOT / f"clien/Data/Map/{kind}/{source_name}.img"
        img = WzImage.from_bytes(source_path.read_bytes(), key=TARGET_KEY, name=source_path.name)
        img.parse()
        prune_children(img.root, set(tree))
        for level0, level1_spec in tree.items():
            node0 = img.root.child(level0)
            if isinstance(level1_spec, set):
                prune_children(node0, level1_spec)
                continue
            prune_children(node0, set(level1_spec))
            for level1, level2_names in level1_spec.items():
                prune_children(node0.child(level1), level2_names)
        atomic_write_bytes(
            ROOT / f"clien/Data/Map/{kind}/{target_name}.img",
            encode_image_body(img, img.wz_file.reader),
        )

    replacements = {
        "BM1": "DunkelBM1",
        "event": "DunkelEvent",
        "BM1_2": "DunkelBM1_2",
        "BM1_3": "DunkelBM1_3",
    }
    for map_id in (450009301, 450009400):
        client_path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        client = WzImage.from_bytes(client_path.read_bytes(), key=TARGET_KEY, name=client_path.name)
        client.parse()
        for node, _ in walk(client.root):
            if node.name in ("oS", "bS") and str(getattr(node, "value", "")) in replacements:
                node._value = replacements[str(node.value)]
        atomic_write_bytes(client_path, encode_image_body(client, client.wz_file.reader))

        server_path = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
        text = server_path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(f'value="{old}"', f'value="{new}"')
        atomic_write_text(server_path, text)


def patch_existing_map_return(map_id: int, target_map: int) -> None:
    client_path = ROOT / f"clien/Data/Map/Map/Map{str(map_id)[0]}/{map_id}.img"
    client = WzImage.from_bytes(client_path.read_bytes(), key=TARGET_KEY, name=client_path.name)
    client.parse()
    info = client.root.child("info")
    set_int(info, "returnMap", target_map)
    set_int(info, "forcedReturn", target_map)
    atomic_write_bytes(client_path, encode_image_body(client, client.wz_file.reader))

    server_path = ROOT / f"gms-server/wz/Map.wz/Map/Map{str(map_id)[0]}/{map_id}.img.xml"
    text = server_path.read_text(encoding="utf-8")
    for name in ("returnMap", "forcedReturn"):
        pattern = rf'<int name="{name}" value="[^"]*"/>'
        replacement = f'<int name="{name}" value="{target_map}"/>'
        text, count = re.subn(pattern, replacement, text, count=1)
        if count != 1:
            raise ValueError(f"{map_id}: missing info/{name}")
    atomic_write_text(server_path, text)


def patch_existing_map_compat(map_id: int) -> None:
    client_path = ROOT / f"clien/Data/Map/Map/Map{str(map_id)[0]}/{map_id}.img"
    client = WzImage.from_bytes(client_path.read_bytes(), key=TARGET_KEY, name=client_path.name)
    client.parse()
    sanitize_map(client, map_id)
    atomic_write_bytes(client_path, encode_image_body(client, client.wz_file.reader))

    source_id = MAP_SOURCES.get(map_id, map_id)
    source = SRC / f"Map/Map/Map{str(source_id)[0]}/{source_id}.img"
    server = source_img(source)
    sanitize_map(server, map_id)
    add_server_boss_spawn(server.root, MAP_BOSSES[map_id])
    atomic_write_text(
        ROOT / f"gms-server/wz/Map.wz/Map/Map{str(map_id)[0]}/{map_id}.img.xml",
        img_to_xml(server, root_name=f"{map_id}.img"),
    )


def add_server_boss_spawn(root: WzSubProperty, mob_id: int) -> None:
    footholds = []
    fh_root = root.child("foothold")
    if fh_root is not None:
        for node, _ in walk(fh_root):
            if not hasattr(node, "child"):
                continue
            values = [node.child(name) for name in ("x1", "y1", "x2", "y2")]
            if any(value is None for value in values):
                continue
            x1, y1, x2, y2 = (int(value.value) for value in values)
            footholds.append((max(y1, y2), (x1 + x2) // 2, int(node.name) if node.name.isdigit() else 0))
    if mob_id == 8880700:
        # The modern "base" platform sits outside the old client's camera
        # bounds. Spawn beside the visible "sp" portal instead.
        x, y, fh = 703, -1394, 28
    else:
        y, x, fh = max(footholds, default=(0, 0, 0))
    life = root.child("life")
    if life is None:
        life = WzSubProperty("life", root)
        root.add(life)
    for existing in list(life.children()):
        node_id = existing.child("id")
        if node_id is not None and str(node_id.value) == str(mob_id):
            life._children.pop(existing.name, None)
    numeric = [int(node.name) for node in life.children() if node.name.isdigit()]
    entry = WzSubProperty(str(max(numeric, default=-1) + 1), life)
    for name, value in (("type", "m"), ("id", str(mob_id))):
        entry.add(WzStringProperty(name, value, entry))
    for name, value in (("x", x), ("y", y), ("mobTime", -1), ("f", 0), ("hide", 0), ("fh", fh), ("cy", y), ("rx0", x - 500), ("rx1", x + 500)):
        entry.add(WzIntProperty(name, value, entry))
    life.add(entry)


def append_client_strings() -> None:
    path = ROOT / "clien/Data/String/Mob.img"
    data = path.read_bytes()
    img = WzImage.from_bytes(data, key=TARGET_KEY, name=path.name)
    img.parse()
    missing = [(mob_id, name) for mob_id, name in MOB_NAMES.items() if img.root.get(f"{mob_id}/name") is None]
    if not missing:
        return
    reader = WzBinaryReader(io.BytesIO(data), TARGET_KEY)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise ValueError("unexpected String/Mob header")
    reader.skip(2)
    offset = reader.position
    if data[offset] == 0x80:
        width, count = 5, struct.unpack("<i", data[offset + 1:offset + 5])[0]
    else:
        width, count = 1, struct.unpack("<b", data[offset:offset + 1])[0]
    count_data = encode_compressed_int(count + len(missing))
    if len(count_data) != width:
        raise ValueError("String/Mob root count width changed")
    encoder = gms_reader()
    append = bytearray()
    for mob_id, name in missing:
        entry = WzSubProperty(str(mob_id))
        entry.add(WzStringProperty("name", name, entry))
        append += encode_string_block(encoder, entry.name)
        append += bytes([_tag_for(entry)])
        append += _encode_property_body(entry, encoder)
    patched = bytearray(data)
    patched[offset:offset + width] = count_data
    patched += append
    atomic_write_bytes(path, bytes(patched))


def patch_server_strings(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for mob_id, name in MOB_NAMES.items():
        replacement = f'<imgdir name="{mob_id}"><string name="name" value="{name}"/></imgdir>'
        pattern = rf'<imgdir name="{mob_id}">.*?</imgdir>'
        if re.search(pattern, text, flags=re.DOTALL):
            text = re.sub(pattern, replacement, text, count=1, flags=re.DOTALL)
        else:
            pos = text.rfind("</imgdir>")
            text = text[:pos] + replacement + text[pos:]
    atomic_write_text(path, text)


def patch_client_ui() -> None:
    path = ROOT / "clien/Data/UI/UIWindow.img"
    target = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=path.name)
    target.parse()
    mob_root = target.root.get("MobGage/Mob")
    aliases = {8870200: "8870000", 8880700: "8870000", 8880803: "8870000", 8880820: "8870000"}
    for mob_id, alias in aliases.items():
        template = mob_root.child(alias)
        if not isinstance(template, WzCanvasProperty):
            raise ValueError(f"UIWindow.img: invalid boss gauge template {alias}")
        replace_child(mob_root, clone_property(template, str(mob_id), mob_root))
    atomic_write_bytes(path, encode_image_body(target, target.wz_file.reader))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume-mob", type=int)
    parser.add_argument("--maps-only", action="store_true")
    parser.add_argument("--resume-map", type=int)
    args = parser.parse_args()
    started = args.resume_mob is None
    if not args.maps_only:
        for mob_id in MOB_NAMES:
            if not started:
                started = mob_id == args.resume_mob
            if not started:
                continue
            migrate_mob(mob_id)
            print(f"mob {mob_id}: migrated")
    map_started = args.resume_map is None
    for map_id in MAPS:
        if not map_started:
            map_started = map_id == args.resume_map
        if not map_started:
            continue
        migrate_map(map_id)
        print(f"map {map_id}: migrated")
    for map_id in RELATED_MAPS:
        migrate_related_map(map_id)
        print(f"related map {map_id}: migrated")
    for map_id in RETRY_MAPS:
        migrate_retry_map(map_id)
        print(f"retry map {map_id}: migrated")
    build_dunkel_visual_pack()
    append_client_strings()
    patch_client_ui()
    patch_server_strings(ROOT / "gms-server/wz/String.wz/Mob.img.xml")
    patch_server_strings(ROOT / "gms-server/wz-zh-CN/String.wz/Mob.img.xml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
