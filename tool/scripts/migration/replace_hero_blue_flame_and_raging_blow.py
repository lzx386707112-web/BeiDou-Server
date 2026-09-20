#!/usr/bin/env python3
"""Replace Hero 1121013/1121014/1121015 with TMS 1120017 / 61141000 / 61141001.

Incremental only: materialize TMS Skill/_Canvas outlinks to GMS ARGB4444 and
replace_img_record those three client records. Does not full-serialize 112.img.
"""
from __future__ import annotations

import hashlib
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
sys.path.insert(0, str(ROOT / "tool" / "scripts" / "migration"))

from migrate_arcane_river_expansion import (  # noqa: E402
    CanvasMaterializer,
    atomic_write_bytes,
    atomic_write_text,
    clone_property,
    raw_record_state,
)
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.crypto import WzKey  # noqa: E402
from wzpy.incremental_img import replace_img_record  # noqa: E402
from wzpy.properties import (  # noqa: E402
    WzCanvasProperty,
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.wz_image import WzImage  # noqa: E402

TMS_SKILL_112 = Path("/Users/lizixian/Documents/mxd/TMS/ms-extract/Skill_00000/Skill_112.img")
TMS_SKILL_6114 = Path("/tmp/tms-6114/Skill_6114.img")
CLIENT_112 = ROOT / "clien" / "Data" / "Skill" / "112.img"
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
SERVER_112_XML = ROOT / "gms-server" / "wz" / "Skill.wz" / "112.img.xml"
STRING_XML = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"
STRING_COPY = {
    "1121013": ("狂暴攻击", "连续攻击前方的敌人。最后两次的攻击必为爆击。"),
    "1121014": ("蓝焰恐惧", "快速挥剑释放剑气攻击敌人。命中时使敌人缓速。"),
    "1121015": ("蓝焰恐惧：终极型态", "终极型态下的蓝焰恐惧隐藏攻击。"),
}
APPROVED = ("1121013", "1121014", "1121015")
LEVEL_FIELDS = (
    "attackCount",
    "cooltime",
    "damage",
    "hs",
    "lt",
    "mobCount",
    "mpCon",
    "rb",
    "x",
    "time",
    "prop",
)
SKIP_COMMON = {"maxLevel", "v", "w", "y", "z", "w2"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def eval_tms_formula(formula: str, x: int) -> int:
    text = str(formula).strip()
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    expr = text.replace("x", str(x))
    while True:
        match = re.search(r"([du])\(([^()]*)\)", expr)
        if not match:
            break
        inner = eval(match.group(2), {"__builtins__": {}}, {})
        value = math.floor(inner) if match.group(1) == "d" else math.ceil(inner)
        expr = expr[: match.start()] + str(int(value)) + expr[match.end() :]
    return int(eval(expr, {"__builtins__": {}}, {}))


def load_img(path: Path, region: str) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region(region))
    image.parse()
    if getattr(image, "truncated", False) or getattr(image, "parse_warnings", None):
        raise SystemExit(f"{path}: truncated={image.truncated} warnings={image.parse_warnings}")
    return image


def make_int(name: str, value: int, parent) -> WzIntProperty:
    return WzIntProperty(name, int(value), parent)


def make_string(name: str, value: str, parent) -> WzStringProperty:
    return WzStringProperty(name, value, parent)


def make_vector(name: str, x: int, y: int, parent) -> WzVectorProperty:
    return WzVectorProperty(name, int(x), int(y), parent)


def clone_visual(source, parent, dest_image: WzImage, dest_path: Path, materializer):
    return clone_property(source, parent, dest_image, dest_path, materializer)


def clone_hit0(source_hit, parent, dest_image, dest_path, materializer):
    hit = WzSubProperty("hit", parent)
    source_group = None if source_hit is None else source_hit.child("0")
    if source_group is None:
        return hit
    group = WzSubProperty("0", hit)
    for child in source_group.children():
        if not isinstance(child, WzCanvasProperty):
            continue
        group.add(clone_visual(child, group, dest_image, dest_path, materializer))
    hit.add(group)
    return hit


def clone_flat_effect(source_effect, name, parent, dest_image, dest_path, materializer):
    if source_effect is None:
        return None
    effect = WzSubProperty(name, parent)
    for child in source_effect.children():
        if not isinstance(child, WzCanvasProperty):
            continue
        effect.add(clone_visual(child, effect, dest_image, dest_path, materializer))
    return effect


def evaluated_level_values(common, skill_level: int) -> dict:
    values: dict = {"cooltime": 0, "hs": f"h{skill_level}"}
    for child in common.children():
        if child.name in SKIP_COMMON:
            continue
        if isinstance(child, WzVectorProperty):
            values[child.name] = (int(child.x), int(child.y))
        elif isinstance(child, WzStringProperty):
            try:
                values[child.name] = eval_tms_formula(str(child.value), skill_level)
            except Exception:
                continue
        elif isinstance(child, WzIntProperty) and child.name != "maxLevel":
            values[child.name] = int(child.value)
    return values


def build_levels(common, parent) -> WzSubProperty:
    levels = WzSubProperty("level", parent)
    for skill_level in range(1, 31):
        values = evaluated_level_values(common, skill_level)
        level = WzSubProperty(str(skill_level), levels)
        for name in LEVEL_FIELDS:
            if name not in values:
                continue
            value = values[name]
            if name == "hs":
                level.add(make_string(name, value, level))
            elif isinstance(value, tuple):
                level.add(make_vector(name, value[0], value[1], level))
            else:
                level.add(make_int(name, value, level))
        levels.add(level)
    return levels


def build_action(parent, repeats: int) -> WzSubProperty:
    action = WzSubProperty("action", parent)
    for index in range(repeats):
        action.add(make_string(str(index), "brandish1", action))
    return action


def build_skill_record(
    dest_id: str,
    source,
    dest_image: WzImage,
    dest_path: Path,
    materializer: CanvasMaterializer,
    action_repeats: int,
    include_effect0: bool,
) -> WzSubProperty:
    record = WzSubProperty(dest_id)
    for icon_name in ("icon", "iconMouseOver", "iconDisabled"):
        icon = source.child(icon_name)
        if icon is None:
            continue
        record.add(clone_visual(icon, record, dest_image, dest_path, materializer))
    effect = clone_flat_effect(
        source.child("effect"), "effect", record, dest_image, dest_path, materializer
    )
    if effect is not None:
        record.add(effect)
    if include_effect0:
        effect0 = clone_flat_effect(
            source.child("effect0"), "effect0", record, dest_image, dest_path, materializer
        )
        if effect0 is not None:
            record.add(effect0)
    record.add(clone_hit0(source.child("hit"), record, dest_image, dest_path, materializer))
    record.add(build_action(record, action_repeats))
    record.add(build_levels(source.child("common"), record))
    record.add(make_int("masterLevel", 30, record))
    record.add(make_int("invisible", 1, record))
    return record


def canvas_stats(node) -> tuple[int, int]:
    total = visible = 0
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, WzCanvasProperty):
            total += 1
            image = decode_canvas(current, region="GMS").convert("RGBA")
            if image.width > 1 and image.height > 1 and any(pixel[3] for pixel in image.getdata()):
                visible += 1
        if hasattr(current, "children"):
            stack.extend(current.children())
    return total, visible


def verify_scope(before: bytes, after: bytes, roots: set[tuple[str, ...]], order_parent: tuple[str, ...]) -> None:
    before_records, before_orders = raw_record_state(before)
    after_records, after_orders = raw_record_state(after)
    if before_orders[order_parent] != after_orders[order_parent]:
        raise SystemExit(f"sibling order changed at {order_parent}")
    for path, raw in before_records.items():
        affected = any(
            path[: len(root)] == root or root[: len(path)] == path for root in roots
        )
        if not affected and after_records.get(path) != raw:
            raise SystemExit(f"protected record changed: {'/'.join(path)}")


def xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def xml_skill_block(skill_id: str, common, action_repeats: int) -> str:
    lines = [f'  <imgdir name="{skill_id}">', '    <imgdir name="action">']
    for index in range(action_repeats):
        lines.append(f'      <string name="{index}" value="brandish1" />')
    lines.append("    </imgdir>")
    lines.append('    <imgdir name="level">')
    for skill_level in range(1, 31):
        values = evaluated_level_values(common, skill_level)
        lines.append(f'      <imgdir name="{skill_level}">')
        for name in LEVEL_FIELDS:
            if name not in values:
                continue
            value = values[name]
            if name == "hs":
                lines.append(f'        <string name="hs" value="{xml_escape(value)}" />')
            elif isinstance(value, tuple):
                lines.append(
                    f'        <vector name="{name}" x="{value[0]}" y="{value[1]}" />'
                )
            else:
                lines.append(f'        <int name="{name}" value="{int(value)}" />')
        lines.append("      </imgdir>")
    lines.append("    </imgdir>")
    lines.append('    <int name="masterLevel" value="30" />')
    lines.append('    <int name="invisible" value="1" />')
    lines.append("  </imgdir>")
    return "\n".join(lines)


def replace_xml_imgdir(text: str, skill_id: str, block: str) -> str:
    pattern = rf'  <imgdir name="{skill_id}">.*?\n  </imgdir>\n'
    updated, count = re.subn(pattern, block + "\n", text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"failed to replace server XML {skill_id}")
    return updated


def string_h_body(common, skill_level: int) -> str:
    values = evaluated_level_values(common, skill_level)
    return (
        f"消耗MP {values['mpCon']}，最多攻击{values['mobCount']}名敌人，"
        f"以{values['damage']}%伤害攻击{values['attackCount']}次                    "
    )


def string_h_lines(common) -> str:
    lines = []
    for skill_level in range(1, 31):
        body = string_h_body(common, skill_level)
        lines.append(f'  <string name="h{skill_level}" value="{xml_escape(body)}"/>')
    return "\n".join(lines)


def replace_string_block(text: str, skill_id: str, block: str) -> str:
    pattern = rf'<imgdir name="{skill_id}">.*?</imgdir>\n'
    updated, count = re.subn(pattern, block + "\n", text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"failed to replace string XML {skill_id}")
    return updated


def patch_client(materializer: CanvasMaterializer, sources: dict) -> bytes:
    before = CLIENT_112.read_bytes()
    dest_image = load_img(CLIENT_112, "GMS")
    specs = (
        ("1121013", sources["1120017"], 4, False),
        ("1121014", sources["61141000"], 1, True),
        ("1121015", sources["61141001"], 1, True),
    )
    updated = before
    for dest_id, source, repeats, include_effect0 in specs:
        record = build_skill_record(
            dest_id, source, dest_image, CLIENT_112, materializer, repeats, include_effect0
        )
        canvases, visible = canvas_stats(record)
        if canvases < 10 or visible < 8:
            raise SystemExit(f"{dest_id}: canvases={canvases} visible={visible}")
        result = replace_img_record(updated, ("skill", dest_id), record, region="GMS")
        updated = result.data
        print(f"{dest_id}: canvases={canvases} visible={visible} delta={result.byte_delta}")
    verify_scope(before, updated, {("skill", skill_id) for skill_id in APPROVED}, ("skill",))
    parsed = WzImage.from_bytes(updated, key=WzKey.for_region("GMS"))
    parsed.parse()
    if parsed.truncated or parsed.parse_warnings:
        raise SystemExit(f"parse failed: {parsed.parse_warnings}")
    for dest_id, _source, repeats, _include_effect0 in specs:
        node = parsed.root.get(f"skill/{dest_id}")
        if str(node.get("action/0").value) != "brandish1":
            raise SystemExit(f"{dest_id} action is not brandish1")
        if repeats > 1 and str(node.get(f"action/{repeats - 1}").value) != "brandish1":
            raise SystemExit(f"{dest_id} missing extra brandish1 actions")
        lv30 = node.get("level/30")
        for field in ("damage", "attackCount", "mobCount", "mpCon"):
            if lv30.child(field) is None:
                raise SystemExit(f"{dest_id} lv30 missing {field}")
        if node.child("summon") is not None:
            raise SystemExit(f"{dest_id} still has summon")
    return updated


def build_string_record(skill_id: str, common) -> WzSubProperty:
    name, desc = STRING_COPY[skill_id]
    record = WzSubProperty(skill_id)
    record.add(make_string("name", name, record))
    record.add(make_string("desc", desc, record))
    for skill_level in range(1, 31):
        record.add(
            make_string(f"h{skill_level}", string_h_body(common, skill_level), record)
        )
    return record


def patch_client_strings(sources: dict) -> bytes:
    before = CLIENT_STRING.read_bytes()
    commons = {
        "1121013": sources["1120017"].child("common"),
        "1121014": sources["61141000"].child("common"),
        "1121015": sources["61141001"].child("common"),
    }
    updated = before
    for skill_id in APPROVED:
        record = build_string_record(skill_id, commons[skill_id])
        result = replace_img_record(updated, (skill_id,), record, region="GMS")
        updated = result.data
        print(f"string {skill_id}: delta={result.byte_delta}")
    verify_scope(before, updated, {(skill_id,) for skill_id in APPROVED}, ())
    parsed = WzImage.from_bytes(updated, key=WzKey.for_region("GMS"))
    parsed.parse()
    if parsed.truncated or parsed.parse_warnings:
        raise SystemExit(f"string img parse failed: {parsed.parse_warnings}")
    for skill_id, (name, _desc) in STRING_COPY.items():
        node = parsed.root.get(skill_id)
        if str(node.child("name").value) != name:
            raise SystemExit(f"{skill_id} client string name mismatch")
        if node.child("h30") is None:
            raise SystemExit(f"{skill_id} missing h30")
    return updated


def patch_xml(sources: dict) -> None:
    xml_text = SERVER_112_XML.read_text(encoding="utf-8")
    xml_text = replace_xml_imgdir(
        xml_text, "1121013", xml_skill_block("1121013", sources["1120017"].child("common"), 4)
    )
    xml_text = replace_xml_imgdir(
        xml_text, "1121014", xml_skill_block("1121014", sources["61141000"].child("common"), 1)
    )
    xml_text = replace_xml_imgdir(
        xml_text, "1121015", xml_skill_block("1121015", sources["61141001"].child("common"), 1)
    )
    atomic_write_text(SERVER_112_XML, xml_text)

    raging = sources["1120017"].child("common")
    flame = sources["61141000"].child("common")
    hidden = sources["61141001"].child("common")
    string_text = STRING_XML.read_text(encoding="utf-8")
    string_text = replace_string_block(
        string_text,
        "1121013",
        "\n".join(
            [
                '<imgdir name="1121013">',
                '  <string name="name" value="狂暴攻击"/>',
                '  <string name="desc" value="连续攻击前方的敌人。最后两次的攻击必为爆击。"/>',
                string_h_lines(raging),
                "</imgdir>",
            ]
        ),
    )
    string_text = replace_string_block(
        string_text,
        "1121014",
        "\n".join(
            [
                '<imgdir name="1121014">',
                '  <string name="name" value="蓝焰恐惧"/>',
                '  <string name="desc" value="快速挥剑释放剑气攻击敌人。命中时使敌人缓速。"/>',
                string_h_lines(flame),
                "</imgdir>",
            ]
        ),
    )
    string_text = replace_string_block(
        string_text,
        "1121015",
        "\n".join(
            [
                '<imgdir name="1121015">',
                '  <string name="name" value="蓝焰恐惧：终极型态"/>',
                '  <string name="desc" value="终极型态下的蓝焰恐惧隐藏攻击。"/>',
                string_h_lines(hidden),
                "</imgdir>",
            ]
        ),
    )
    atomic_write_text(STRING_XML, string_text)


def main() -> int:
    if not TMS_SKILL_112.exists():
        raise SystemExit(f"missing {TMS_SKILL_112}")
    if not TMS_SKILL_6114.exists():
        raise SystemExit(f"missing {TMS_SKILL_6114}")
    tms_112 = load_img(TMS_SKILL_112, "BMS")
    tms_6114 = load_img(TMS_SKILL_6114, "BMS")
    sources = {
        "1120017": tms_112.root.get("skill/1120017"),
        "61141000": tms_6114.root.get("skill/61141000"),
        "61141001": tms_6114.root.get("skill/61141001"),
    }
    if any(value is None for value in sources.values()):
        raise SystemExit("missing TMS source skills")

    strings_only = "--strings-only" in sys.argv
    if not strings_only:
        first = patch_client(CanvasMaterializer(), sources)
        atomic_write_bytes(CLIENT_112, first)
        first_hash = hashlib.sha256(first).hexdigest()
        second = patch_client(CanvasMaterializer(), sources)
        if hashlib.sha256(second).hexdigest() != first_hash:
            raise SystemExit("generator not idempotent")
        atomic_write_bytes(CLIENT_112, second)
        print("client skill sha256", first_hash)
    first_strings = patch_client_strings(sources)
    atomic_write_bytes(CLIENT_STRING, first_strings)
    first_string_hash = hashlib.sha256(first_strings).hexdigest()
    second_strings = patch_client_strings(sources)
    if hashlib.sha256(second_strings).hexdigest() != first_string_hash:
        raise SystemExit("string generator not idempotent")
    atomic_write_bytes(CLIENT_STRING, second_strings)
    patch_xml(sources)
    print("client string sha256", first_string_hash)
    for label, common in (
        ("1121013", sources["1120017"].child("common")),
        ("1121014", sources["61141000"].child("common")),
        ("1121015", sources["61141001"].child("common")),
    ):
        values = evaluated_level_values(common, 30)
        print(
            f"lv30 {label} damage={values['damage']} ac={values['attackCount']} "
            f"mc={values['mobCount']} mp={values['mpCon']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
