#!/usr/bin/env python3
"""Read-only reference audit for the user's weapon/shoe removal request.

No deletion/apply mode: referenced IDs must await the user's decision.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from remove_weapon_resources import walk_elements  # noqa: E402

ID_FILE = Path(__file__).with_name("remove_weapon_shoe_ids.txt")
REPORT = ROOT / "docs/migrations/weapon-shoe-reference-audit.md"
TOKEN = re.compile(r"(?<!\d)0?(\d{7})(?!\d)")


def load_ids():
    text = re.sub(r"#.*", "", ID_FILE.read_text(encoding="utf-8"))
    tokens = text.split()
    if any(not re.fullmatch(r"\d{7}", token) for token in tokens):
        raise ValueError("invalid equipment ID")
    return tuple(sorted({int(token) for token in tokens})), len(tokens)


def category(item_id):
    return "Shoes" if item_id // 10000 == 107 else "Weapon"


def equipment_paths(item_id):
    relative = Path(category(item_id)) / f"0{item_id}.img"
    return (ROOT / "clien/Data/Character" / relative,
            ROOT / "gms-server/wz/Character.wz" / (str(relative) + ".xml"))


def audit():
    ids, count = load_ids()
    requested = set(ids)
    references = defaultdict(list)
    names = {}
    for node, path, _parent, _parent_path in walk_elements(
            ET.parse(ROOT / "gms-server/wz-zh-CN/String.wz/Eqp.img.xml").getroot()):
        if node.attrib.get("name") == "name" and len(path) >= 2 and path[-2].isdigit():
            names[int(path[-2])] = node.attrib.get("value", "")

    def add(item_id, kind, source, detail):
        references[item_id].append({"kind": kind, "source": str(source), "detail": detail})

    for item_id in ids:
        client, server = equipment_paths(item_id)
        if client.exists() != server.exists():
            raise ValueError(f"client/server mismatch: {item_id}")
        if server.exists():
            info = ET.parse(server).getroot().find("imgdir[@name='info']")
            for node in info if info is not None else ():
                if "quest" in node.attrib.get("name", "").lower() and node.attrib.get("value", "0") != "0":
                    add(item_id, "任务标记", server.relative_to(ROOT),
                        f"info/{node.attrib['name']}={node.attrib.get('value')}")

    for base in ("wz", "wz-zh-CN"):
        for path in sorted((ROOT / "gms-server" / base / "Quest.wz").glob("*.xml")):
            for node, record_path, _parent, _parent_path in walk_elements(ET.parse(path).getroot()):
                for token in TOKEN.findall(node.attrib.get("value", "")):
                    if int(token) in requested:
                        kind = "任务引用"
                        quantity = _parent.find("int[@name='count']")
                        if path.name == "Act.img.xml" and node.attrib.get("name") == "id" and quantity is not None:
                            kind = "任务奖励" if int(quantity.attrib["value"]) > 0 else "任务消耗"
                        add(int(token), kind, path.relative_to(ROOT), "/".join(record_path))
        for name, kind in (("NPT_exception", "NPT例外"), ("Commodity", "商城商品")):
            path = ROOT / "gms-server" / base / "Etc.wz" / f"{name}.img.xml"
            for node, record_path, _parent, _parent_path in walk_elements(ET.parse(path).getroot()):
                value = node.attrib.get("value", "")
                if value.isdigit() and int(value) in requested:
                    add(int(value), kind, path.relative_to(ROOT), "/".join(record_path))

    pattern = r"(^|[^0-9])0?(" + "|".join(map(str, ids)) + r")([^0-9]|$)"
    process = subprocess.run(["rtk", "proxy", "rg", "-n", pattern,
                              "gms-server/scripts", "gms-server/scripts-zh-CN",
                              "gms-server/src/main/java", "gms-server/src/main/resources/db/migration",
                              "gms-server/wz/Character.wz"],
                             cwd=ROOT, capture_output=True, text=True)
    if process.returncode not in (0, 1):
        raise ValueError(process.stderr)
    range_endpoints = []
    definitions = {str(equipment_paths(i)[1].relative_to(ROOT)) for i in ids}
    for line in process.stdout.splitlines():
        source, number, text = line.split(":", 2)
        matched = requested & {int(token) for token in TOKEN.findall(text)}
        if "weaponTypeRanges.put(" in text or "EQUIP_RANGES.put(" in text:
            range_endpoints.append({"source": f"{source}:{number}", "text": text.strip()})
            continue
        if "/Character.wz/" in source:
            if source in definitions or 'name="_hash"' in text:
                continue
            kind = "其他装备资源引用"
        elif "/db/migration/" in source:
            kind = "掉落SQL（未核实数据库）"
        elif source.endswith("equipment_fusion.js"):
            recipe = re.search(r"\[(\d+),\s*(\d{7}),\s*\[", text)
            if not recipe:
                raise ValueError(f"unclassified fusion reference: {line}")
            for item_id in matched:
                role = "融合产物" if item_id == int(recipe[2]) else "融合材料"
                add(item_id, role, f"{source}:{number}", text.strip())
            continue
        elif source.endswith("SetItemManager.java"):
            kind = "套装武器"
        elif source.endswith("9110016.js"):
            kind = "百宝箱奖励"
        else:
            kind = "脚本或服务端代码引用"
        for item_id in matched:
            add(item_id, kind, f"{source}:{number}", text.strip())

    return {"input_count": count, "unique_count": len(ids), "duplicate_count": count - len(ids),
            "referenced": {str(i): {"name": names.get(i, ""), "references": references[i]} for i in sorted(references)},
            "no_gameplay_reference_found": sorted(requested - references.keys()),
            "range_endpoints_not_item_dependencies": range_endpoints}


def render(result):
    referenced = result["referenced"]
    lines = ["# 武器和鞋子删除前引用清单", "",
             "尚未删除或修改任何客户端资源、服务端 XML、脚本、Java 或数据库。全部等待用户决定。", "",
             f"输入 {result['input_count']} 次，去重后 {result['unique_count']} 个 ID，重复 {result['duplicate_count']} 次。",
             f"发现 {len(referenced)} 个有任务标记或实际功能引用的 ID；其余 {len(result['no_gameplay_reference_found'])} 个未发现这类仓库引用。", "",
             "名称表、装备资源本体、管理目录、手册、历史说明文档不计入实际功能依赖。",
             "SQL 只证明历史迁移有配置，未连接运行数据库，不能证明当前掉落或玩家库存现状。",
             "客户端 Quest 已核查；任务保留项没有删除实验。商城商品有记录不等于当前商城开放。", "",
             "## 有引用的装备", "", "| ID | 名称 | 引用类型 |", "| --- | --- | --- |"]
    for item_id, entry in referenced.items():
        kinds = "、".join(sorted({ref["kind"] for ref in entry["references"]}))
        lines.append(f"| {item_id} | {entry['name']} | {kinds} |")
    lines += ["", "## 引用位置与内容", ""]
    for item_id, entry in referenced.items():
        lines += [f"### {item_id} {entry['name']}", ""]
        for ref in entry["references"]:
            path, _, number = ref["source"].partition(":")
            target = str(ROOT / path) + (":" + number if number else "")
            lines.append(f"- {ref['kind']}：[来源]({target})，`{ref['detail']}`")
        lines.append("")
    lines += ["## 数字范围边界（不是装备引用）", "",
              "1312046、1322074、1422047 还作为装备类型识别的数字区间上界。删除资源不要求删除这些区间定义。", ""]
    for ref in result["range_endpoints_not_item_dependencies"]:
        lines.append(f"- `{ref['source']}`：`{ref['text']}`")
    lines += ["", "## 未发现功能引用的 ID", "",
              "仅指仓库静态扫描结果，不包含运行数据库和动态配置。没有执行删除。", ""]
    ids = result["no_gameplay_reference_found"]
    lines += [", ".join(map(str, ids[start:start + 12])) for start in range(0, len(ids), 12)]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="write audit reports only; never mutate runtime files")
    args = parser.parse_args()
    result = audit()
    if args.report:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(render(result), encoding="utf-8")
        REPORT.with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output = result if not args.report else {
        "unique_count": result["unique_count"], "referenced_count": len(result["referenced"]),
        "no_gameplay_reference_found": len(result["no_gameplay_reference_found"]), "report": str(REPORT)}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
