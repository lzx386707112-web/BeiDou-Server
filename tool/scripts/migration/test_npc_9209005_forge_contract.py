#!/usr/bin/env python3
"""Contract: NPC 9209005 forge menus and recipes."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "gms-server/scripts-zh-CN/npc/9209005.js"

GUEST_T1 = [
    1372074, 1302143, 1312058, 1322086, 1332116, 1402086, 1412058, 1422059,
    1432077, 1452102, 1462087, 1472113, 1482075, 1492075, 1382095,
]
GUEST_T2 = [
    1372075, 1302144, 1312059, 1322087, 1332117, 1402087, 1412059, 1422060,
    1432078, 1452103, 1462088, 1472114, 1482076, 1492076, 1382096,
]
GUEST_T3 = [
    1372076, 1302145, 1312060, 1322088, 1332118, 1402088, 1412060, 1422061,
    1432079, 1452104, 1462089, 1472115, 1482077, 1492077, 1382097,
]
GUEST_FINAL = [
    1372077, 1302146, 1312061, 1322089, 1332119, 1382098, 1402089, 1412061,
    1422062, 1432080, 1452105, 1462090, 1472116, 1482078, 1492078,
]
GUEST_SUPREME = [
    1372078, 1302147, 1312062, 1322090, 1332120, 1382099, 1402090, 1412062,
    1422063, 1432081, 1452106, 1462091, 1472117, 1482079, 1492079,
]
UTGARD = [
    1302315, 1312185, 1322236, 1332260, 1372207, 1382245, 1402236, 1412164,
    1422171, 1432200, 1442254, 1452238, 1462225, 1472247, 1482202, 1492212,
]


def ids_in(text: str, ids: list[int]) -> list[int]:
    return [item_id for item_id in ids if str(item_id) not in text]


def main() -> int:
    text = SCRIPT.read_text(encoding="utf-8")
    errors: list[str] = []
    for needle in (
        "欢迎来到锻造系统，我什么都能造！客官请选择你要锻造的装备",
        "不速之客系列",
        "乌特格鲁德系列",
        "法弗纳系列",
        "漩涡系列",
        "第一系列",
        "第二系列",
        "第三系列",
        "最终系列",
        "至尊系列",
        "还在筹备中",
    ):
        if needle not in text:
            errors.append(f"missing text: {needle}")
    for label, group in (
        ("guest t1", GUEST_T1),
        ("guest t2", GUEST_T2),
        ("guest t3", GUEST_T3),
        ("guest final", GUEST_FINAL),
        ("guest supreme", GUEST_SUPREME),
        ("utgard", UTGARD),
    ):
        missing = ids_in(text, group)
        if missing:
            errors.append(f"{label} missing {missing}")
    for mat in (
        4000117, 4000118, 4000119, 4000120, 4000121, 4000122, 4000695,
        4000125, 4000126, 4000111, 4000112, 4000115, 2388031, 4011006,
        4021000, 4021001, 4021002, 4021003, 4021004, 4021005, 4021006, 4021007,
        4011007, 4021009, 4000147, 4000148, 4000132, 4000133, 4000240, 2385021,
        4005000, 4005001, 4005002, 4005003, 4005004, 4031817, 4031818, 4031819,
        4031820, 4032028, 4000696, 4032056, 4000244, 4000245, 4000175, 1672008,
        4000151, 4000152, 4003002, 4003000, 4003001, 4031875, 4251200, 4031821,
        4001141,
    ):
        if str(mat) not in text:
            errors.append(f"missing material {mat}")
    if "4000696, 50" not in text and "4000696,50" not in re.sub(r"\s+", "", text):
        if "addMat(mats, matQty, 4000696, 50)" not in text:
            errors.append("supreme recipe must consume Boss币 4000696 x50")
    if text.count("4031817") != 1:
        errors.append("4031817 must only be red gummy, not Boss币")
    for cost in (1000, 2000, 5000, 8000, 15000, 5000000, 8000000, 50000000, 200000000, 500000000):
        if str(cost) not in text:
            errors.append(f"missing cost {cost}")
    if "findByType(GUEST[0]" not in text or "findByType(GUEST[1]" not in text:
        errors.append("tier 3 must consume matching t1 and t2 weapons")
    if "findByType(GUEST[2]" not in text or "findByType(GUEST[3]" not in text:
        errors.append("final/supreme must consume matching previous weapons")
    if "getManualID(item)" not in text or "getStimID(item)" not in text:
        errors.append("utgard must consume matching manual and stimulator")
    if errors:
        print("npc 9209005 forge contract failed:")
        for error in errors:
            print(f"  {error}")
        return 1
    print("npc 9209005 forge contract passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
