#!/usr/bin/env python3
"""Generate runtime series data from the reviewed Markdown table, not UI mocks."""
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "gms-server/src/main/resources/set-item/catalog.json"
MAPPING = {
    "攻击力/魔法攻击力": ["PAD", "MAD"], "物理/魔法防御力": ["PDD", "MDD"],
    "最大HP/最大MP": ["HP", "MP"], "所有属性": ["STR", "DEX", "INT", "LUK"],
    "力量": ["STR"], "敏捷": ["DEX"], "智力": ["INT"], "运气": ["LUK"],
    "攻击力": ["PAD"], "魔法攻击力": ["MAD"], "防御力": ["PDD", "MDD"],
    "命中值": ["ACC"], "回避值": ["EVA"], "最大HP": ["HP"], "最大MP": ["MP"],
    "移动速度": ["SPD"], "跳跃力": ["JMP"], "攻击首领怪时的伤害": ["BossDamage"],
    "首领怪物伤害": ["BossDamage"],
    "攻击普通怪物时，伤害": ["NormalDamage"],
    "伤害": ["Damage"],
}
EXCLUDED = {"被攻击后的无敌时间", "状态异常抗性", "爆击率", "无视怪物防御率"}


def generate():
    sys.path.insert(0, str(Path(__file__).parent))
    import migrate_arcane_river_expansion as arc
    source_sets = arc.load_image(arc.SOURCE / "Etc/SetItemInfo.img", arc.BMS_KEY)
    assert not source_sets.truncated and not source_sets.parse_warnings
    client_weapons = {int(path.stem) for path in (ROOT / "clien/Data/Character/Weapon").glob("*.img")
                      if path.stem.isdigit()}
    server_weapons = {int(path.name.split(".")[0]) for path in
                      (ROOT / "gms-server/wz/Character.wz/Weapon").glob("*.img.xml")
                      if path.name.split(".")[0].isdigit()}
    text = (ROOT / "docs/套装系列装备ID对照表.md").read_text()
    catalog = []
    for section in re.split(r"^## \d+-\d+\. ", text, flags=re.M)[1:]:
        name, _, body = section.partition("\n")
        slots, tiers = OrderedDict(), []
        for line in body.splitlines():
            if line.startswith(">") and "原表格未列武器" in line:
                ids = [int(i) for i in re.findall(r"`(\d{7})`", line)]
                slots.setdefault("武器", []).extend(ids)
            if not line.startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if re.fullmatch(r"\d+ 件", cells[0]):
                count = int(cells[0].split()[0])
                stats = {}
                for effect in cells[1].split(" · "):
                    match = re.fullmatch(r"(.+?)(?:：|\+)(?:\+)?(\d+)(%|秒)?", effect)
                    assert match, effect
                    if match[1] in EXCLUDED:
                        continue
                    assert match[1] in MAPPING, effect
                    label, value, unit = match.groups()
                    for key in MAPPING[label]:
                        if unit == "%" and key not in ("BossDamage", "NormalDamage", "Damage"):
                            key += "Pct"
                        stats[key] = stats.get(key, 0) + int(value)
                tiers.append({"requiredCount": count, "stats": stats})
                continue
            id_cell = 3 if cells[0].startswith("套装 ") else 2
            if len(cells) <= id_cell:
                continue
            ids = [int(i) for i in re.findall(r"`(\d{7})`", cells[id_cell])]
            if ids:
                slot = cells[1] if id_cell == 3 else cells[0]
                slots.setdefault(slot, []).extend(ids)
        if not tiers:
            continue
        # TMS Etc/SetItemInfo.img/543 includes this existing face accessory.
        if name == "冒险岛寻宝":
            slots["脸饰"] = [1012524]
        if max(t["requiredCount"] for t in tiers) > len(slots) and "武器" not in slots:
            hat = slots["帽子"][0]
            cap = ET.parse(ROOT / f"gms-server/wz/Character.wz/Cap/{hat:08d}.img.xml")
            set_id = cap.find(".//*[@name='setItemID']").attrib["value"]
            source = source_sets.root.get(f"{set_id}/ItemID")
            ids = [node.value for node in source.children() if hasattr(node, "value")
                   and 1300000 <= node.value < 1600000
                   and node.value in client_weapons and node.value in server_weapons]
            assert ids, name
            slots["武器"] = ids
        unique = [list(dict.fromkeys(ids)) for ids in slots.values()]
        assert all(unique) and len(unique) <= 20 and max(map(len, unique)) <= 50, name
        assert max(t["requiredCount"] for t in tiers) <= len(unique), name
        catalog.append({"id": 11000 + len(catalog), "jobIndex": -1, "name": name,
                        "slots": unique, "tiers": tiers})
    assert len(catalog) == 55, len(catalog)
    return (json.dumps(catalog, ensure_ascii=False, indent=2) + "\n").encode()


if __name__ == "__main__":
    payload = generate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if not OUTPUT.exists() or OUTPUT.read_bytes() != payload:
        OUTPUT.write_bytes(payload)
    print(f"55 runtime series: {OUTPUT}")
