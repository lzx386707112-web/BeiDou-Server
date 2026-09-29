#!/usr/bin/env python3
"""Import the missing 黃昏的勇士之村 / 未來之門 quest records from TMS.

Follows the convention already used for the 37 imported quests in the repo:

  * QuestInfo: name / area / 0 / 1 / 2 only  (category, recommend, rewardSummary,
    reqType are dropped - the legacy client does not read them).
  * Check: lvmin / npc / quest prereqs on branch 0, order / npc / mob / item on
    branch 1.  ``startscript`` and ``endscript`` are stripped:  BeiDou runs the
    dungeon data-only and QuestActionHandler falls back to the plain quest flow.
  * Act: exp plus item rewards (``potentialGrade`` dropped).
  * Say: empty branches, matching every existing 黃昏的勇士之村 quest.

NPC 1105001 (赫麗娜 / 聯盟會議場) is remapped to 1022000 (武術教練, 102000003)
exactly like the already imported 31900-31903, because the repo has no 聯盟會議場.

Chapter-one quests (31091, 31103-31160) are deliberately NOT imported: their
NPCs (2142001-2142009, 1101002) spawn in no repo map and 186 of their 2710
instance maps are missing, so the records would be dead weight in the journal.

Run:  /opt/homebrew/bin/python3 tool/scripts/migration/import_twilight_perion_quest_chain.py
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

from wzpy import (  # noqa: E402
    WzImage,
    WzIntProperty,
    WzKey,
    WzStringProperty,
    WzSubProperty,
    detect_region_from_img,
)
from wzpy.incremental_img import (  # noqa: E402
    _apply_edits,
    _find_list,
    _record_bytes,
    _reference_edits,
    _size_edits,
    scan_img,
)
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_compressed_int  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "arc", ROOT / "tool/scripts/migration/migrate_arcane_river_expansion.py"
)
arc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(arc)

TMS = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data/Quest/QuestData")
BACKUP_ROOT = Path("/private/tmp/twilight-perion-quest-import-backup")

NPC_REMAP = {"1105001": "1022000"}

# 主題副本入口 + 未來之門日常（31916-31944）。第一章不入。
QUEST_IDS = ["1345"] + [str(i) for i in range(31916, 31945)]


# --------------------------------------------------------------------------- #
# TMS -> plain python
# --------------------------------------------------------------------------- #
def load_tms(qid: str):
    path = TMS / f"{qid}.img"
    data = path.read_bytes()
    image = WzImage.from_bytes(data, key=arc.BMS_KEY)
    return image.parse()


def to_dict(node):
    if node is None:
        return None
    if node.children():
        return {child.name: to_dict(child) for child in node.children()}
    return node.value


def leaf(node, key):
    child = node.get(key) if isinstance(node, dict) else None
    return child


# --------------------------------------------------------------------------- #
# normalized record spec
# --------------------------------------------------------------------------- #
def build_spec(qid: str) -> dict:
    root = load_tms(qid)
    tree = {child.name: to_dict(child) for child in root.children()}

    qi = tree.get("QuestInfo") or {}
    ck = tree.get("Check") or {}
    ac = tree.get("Act") or {}

    quest_info = {"name": qi.get("name"), "area": qi.get("area")}
    for index in ("0", "1", "2"):
        if qi.get(index) is not None:
            quest_info[index] = qi[index]

    check = {"0": {}, "1": {}}
    start = ck.get("0") or {}
    if start.get("lvmin") is not None:
        check["0"]["lvmin"] = int(start["lvmin"])
    npc = start.get("npc")
    if npc is not None:
        check["0"]["npc"] = int(NPC_REMAP.get(str(npc), str(npc)))
    prereqs = start.get("quest") or {}
    if isinstance(prereqs, dict) and prereqs:
        entries = []
        for key in sorted(prereqs, key=lambda k: int(k)) if all(
            k.isdigit() for k in prereqs
        ) else prereqs:
            item = prereqs[key]
            if isinstance(item, dict) and item.get("id") is not None:
                entries.append(
                    {
                        "id": int(item["id"]),
                        "state": int(item.get("state", 2)),
                        "order": int(item.get("order", 1)),
                    }
                )
        if entries:
            check["0"]["quest"] = entries

    done = ck.get("1") or {}
    if done.get("order") is not None:
        check["1"]["order"] = int(done["order"])
    npc = done.get("npc")
    if npc is not None:
        check["1"]["npc"] = int(NPC_REMAP.get(str(npc), str(npc)))
    for kind in ("mob", "item"):
        block = done.get(kind) or {}
        if isinstance(block, dict) and block:
            entries = []
            for key in sorted(block, key=lambda k: int(k)) if all(
                k.isdigit() for k in block
            ) else block:
                item = block[key]
                if isinstance(item, dict) and item.get("id") is not None:
                    entries.append(
                        {
                            "id": int(item["id"]),
                            "count": int(item["count"]),
                            "order": int(item.get("order", 1)),
                        }
                    )
            if entries:
                check["1"][kind] = entries

    act = {"0": {}, "1": {}}
    reward = ac.get("1") or {}
    if reward.get("exp") is not None:
        act["1"]["exp"] = int(reward["exp"])
    items = reward.get("item") or {}
    if isinstance(items, dict) and items:
        entries = []
        for key in sorted(items, key=lambda k: int(k)) if all(
            k.isdigit() for k in items
        ) else items:
            item = items[key]
            if isinstance(item, dict) and item.get("id") is not None:
                entries.append({"id": int(item["id"]), "count": int(item.get("count", 1))})
        if entries:
            act["1"]["item"] = entries

    return {"quest_info": quest_info, "check": check, "act": act}


# --------------------------------------------------------------------------- #
# server XML
# --------------------------------------------------------------------------- #
def xml_value(value) -> str:
    if isinstance(value, int):
        return f"<int name={quoteattr(str(value))} value=\"{value}\"/>"
    raise AssertionError(value)


def xml_int(name: str, value: int, indent: int) -> str:
    pad = "  " * indent
    return f"{pad}<int name={quoteattr(name)} value=\"{value}\"/>"


def xml_string(name: str, value, indent: int) -> str:
    pad = "  " * indent
    return f"{pad}<string name={quoteattr(name)} value={quoteattr(str(value))}/>"


def render_quest_info(spec: dict, qid: str) -> str:
    lines = [f'  <imgdir name="{qid}">']
    qi = spec["quest_info"]
    if qi.get("name") is not None:
        lines.append(xml_string("name", qi["name"], 2))
    if qi.get("area") is not None:
        lines.append(xml_int("area", qi["area"], 2))
    for index in ("0", "1", "2"):
        if qi.get(index) is not None:
            lines.append(xml_string(index, qi[index], 2))
    lines.append("  </imgdir>")
    return "\n".join(lines)


def render_entries(name: str, entries: list, indent: int) -> list:
    lines = [f'{"  " * indent}<imgdir name="{name}">']
    for index, entry in enumerate(entries):
        pad = "  " * (indent + 1)
        lines.append(f'{pad}<imgdir name="{index}">')
        lines.append(xml_int("id", entry["id"], indent + 2))
        lines.append(xml_int("count", entry["count"], indent + 2))
        if "order" in entry:
            lines.append(xml_int("order", entry["order"], indent + 2))
        lines.append(f'{pad}</imgdir>')
    lines.append(f'{"  " * indent}</imgdir>')
    return lines


def render_check(spec: dict, qid: str) -> str:
    lines = [f'  <imgdir name="{qid}">']
    for branch in ("0", "1"):
        pad = "    "
        lines.append(f'{pad}<imgdir name="{branch}">')
        data = spec["check"].get(branch) or {}
        if branch == "0":
            if data.get("lvmin") is not None:
                lines.append(xml_int("lvmin", data["lvmin"], 3))
            if data.get("npc") is not None:
                lines.append(xml_int("npc", data["npc"], 3))
            if data.get("quest"):
                lines.append('      <imgdir name="quest">')
                for index, entry in enumerate(data["quest"]):
                    lines.append(f'        <imgdir name="{index}">')
                    lines.append(xml_int("id", entry["id"], 5))
                    lines.append(xml_int("state", entry["state"], 5))
                    lines.append(xml_int("order", entry["order"], 5))
                    lines.append('        </imgdir>')
                lines.append('      </imgdir>')
        else:
            if data.get("order") is not None:
                lines.append(xml_int("order", data["order"], 3))
            if data.get("npc") is not None:
                lines.append(xml_int("npc", data["npc"], 3))
            for kind in ("mob", "item"):
                if data.get(kind):
                    lines.extend(render_entries(kind, data[kind], 3))
        lines.append(f'{pad}</imgdir>')
    lines.append("  </imgdir>")
    return "\n".join(lines)


def render_act(spec: dict, qid: str) -> str:
    lines = [f'  <imgdir name="{qid}">', '    <imgdir name="0"></imgdir>', '    <imgdir name="1">']
    data = spec["act"].get("1") or {}
    if data.get("exp") is not None:
        lines.append(xml_int("exp", data["exp"], 3))
    if data.get("item"):
        lines.extend(render_entries("item", data["item"], 3))
    lines.append('    </imgdir>')
    lines.append("  </imgdir>")
    return "\n".join(lines)


def render_say(qid: str) -> str:
    return (
        f'  <imgdir name="{qid}">\n'
        '    <imgdir name="0"></imgdir>\n'
        '    <imgdir name="1"></imgdir>\n'
        '  </imgdir>'
    )


def backup(path: Path) -> None:
    target = BACKUP_ROOT / path.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(path, target)


def insert_xml(path: Path, qid: str, block: str) -> None:
    text = path.read_text(encoding="utf-8")
    if f'<imgdir name="{qid}">' in text:
        print(f"    {path.name}: {qid} already present, skip")
        return
    positions = [
        (int(match.group(1)), match.start())
        for match in re.finditer(r'^  <imgdir name="(\d+)">', text, re.M)
    ]
    target = None
    for value, offset in positions:
        if value > int(qid):
            target = offset
            break
    if target is None:
        target = text.rfind("</imgdir>")
        # keep the root closing tag on its own line
        insertion = block + "\n"
    else:
        insertion = block + "\n"
    result = text[:target] + insertion + text[target:]
    ET.fromstring(result)
    backup(path)
    path.write_text(result, encoding="utf-8")


# --------------------------------------------------------------------------- #
# client IMG
# --------------------------------------------------------------------------- #
def build_prop(name, spec):
    if isinstance(spec, dict):
        node = WzSubProperty(str(name))
        for key, value in spec.items():
            node.add(build_prop(key, value))
        return node
    if isinstance(spec, list):
        node = WzSubProperty(str(name))
        for index, entry in enumerate(spec):
            node.add(build_prop(str(index), entry))
        return node
    if isinstance(spec, int):
        return WzIntProperty(str(name), spec)
    return WzStringProperty(str(name), str(spec))


def build_quest_prop(qid: str, spec: dict, section: str):
    node = WzSubProperty(qid)
    if section == "quest_info":
        for key in ("name", "area", "0", "1", "2"):
            if spec["quest_info"].get(key) is not None:
                node.add(build_prop(key, spec["quest_info"][key]))
    elif section == "check":
        for branch in ("0", "1"):
            child = WzSubProperty(branch)
            data = spec["check"].get(branch) or {}
            if branch == "0":
                for key in ("lvmin", "npc", "quest"):
                    if data.get(key) is not None:
                        child.add(build_prop(key, data[key]))
            else:
                for key in ("order", "npc", "mob", "item"):
                    if data.get(key) is not None:
                        child.add(build_prop(key, data[key]))
            node.add(child)
    elif section == "act":
        node.add(WzSubProperty("0"))
        one = WzSubProperty("1")
        data = spec["act"].get("1") or {}
        for key in ("exp", "item"):
            if data.get(key) is not None:
                one.add(build_prop(key, data[key]))
        node.add(one)
    else:
        node.add(WzSubProperty("0"))
        node.add(WzSubProperty("1"))
    return node


def insert_img(path: Path, qid: str, prop) -> None:
    data = path.read_bytes()
    layout = scan_img(data, region="GMS")
    if any(record.name == qid for record in layout.root.records):
        print(f"    {path.name}: {qid} already present, skip")
        return
    reader = WzBinaryReader(io_bytes(data), WzKey.for_region("GMS"))
    payload = _record_bytes(prop, reader)
    count_bytes = encode_compressed_int(layout.root.count + 1)
    count_delta = len(count_bytes) - (layout.root.count_end - layout.root.count_offset)
    delta = len(payload) + count_delta
    edits = [
        (layout.root.end, layout.root.end, payload),
        (layout.root.count_offset, layout.root.count_end, count_bytes),
        *_size_edits([], delta),
    ]
    edits.extend(_reference_edits(layout, edits))
    patched = _apply_edits(data, edits)
    image = WzImage.from_bytes(patched, key=WzKey.for_region("GMS"))
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"{path.name}: patched IMG invalid: {image.parse_warnings or image.truncated}"
        )
    backup(path)
    path.write_bytes(patched)


def io_bytes(data: bytes):
    import io

    return io.BytesIO(data)


# --------------------------------------------------------------------------- #
def main() -> int:
    server = ROOT / "gms-server/wz-zh-CN/Quest.wz"
    client = ROOT / "clien/Data/Quest"
    for qid in QUEST_IDS:
        spec = build_spec(qid)
        print(f"  {qid}: {spec['quest_info'].get('name')}")
        insert_xml(server / "QuestInfo.img.xml", qid, render_quest_info(spec, qid))
        insert_xml(server / "Check.img.xml", qid, render_check(spec, qid))
        insert_xml(server / "Act.img.xml", qid, render_act(spec, qid))
        insert_xml(server / "Say.img.xml", qid, render_say(qid))
        insert_img(client / "QuestInfo.img", qid, build_quest_prop(qid, spec, "quest_info"))
        insert_img(client / "Check.img", qid, build_quest_prop(qid, spec, "check"))
        insert_img(client / "Act.img", qid, build_quest_prop(qid, spec, "act"))
        insert_img(client / "Say.img", qid, build_quest_prop(qid, spec, "say"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
