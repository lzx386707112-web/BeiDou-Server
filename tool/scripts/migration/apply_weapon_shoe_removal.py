#!/usr/bin/env python3
"""Delete the 315 approved IDs, preserving the 39 user-retained IDs exactly."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import remove_weapon_shoe_resources as audit_tool  # noqa: E402
from remove_weapon_resources import (  # noqa: E402
    ROOT, CLIENT_EQP, SERVER_EQP, CATALOG, _find_record, _find_node,
    batch_remove_img, batch_remove_xml, scan_img, scan_xml, verify_img,
    WzImage, WzKey,
)

KEEP_IDS = frozenset((
    1302038, 1302039, 1302040, 1302041, 1302042, 1302043, 1302044,
    1302045, 1302047, 1302048, 1302050, 1302051, 1302052, 1302053,
    1302054, 1302180, 1302192, 1312098, 1322064, 1322138, 1332059,
    1332168, 1372117, 1382142, 1402129, 1412087, 1422033, 1422089,
    1432117, 1452147, 1462043, 1462136, 1462181, 1472159, 1482120,
    1492088, 1492119, 1702143, 1702217,
))
SQL = ROOT / "gms-server/src/main/resources/db/migration/V2.1.105__remove_unreferenced_weapon_shoe_ids.sql"
RESULT = ROOT / "docs/migrations/weapon-shoe-removal-result.json"
DELETE_MANIFEST = HERE / "removed-equipment-files.json"


def delete_ids():
    requested = set(audit_tool.load_ids()[0])
    frozen = json.loads(audit_tool.REPORT.with_suffix(".json").read_text(encoding="utf-8"))
    if len(requested) != 354 or set(map(int, frozen["referenced"])) != KEEP_IDS:
        raise ValueError("the approved request/keep list has changed")
    ids = requested - KEEP_IDS
    if len(ids) != 315 or ids != set(frozen["no_gameplay_reference_found"]):
        raise ValueError("the approved deletion list has changed")
    return ids


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_scope(before, after, removed, *, xml=False):
    old = scan_xml(before) if xml else scan_img(before, region="GMS").root
    new = scan_xml(after) if xml else scan_img(after, region="GMS").root
    removed = set(removed)
    def compare(previous, current, prefix=()):
        old_children = previous.children if xml else previous.records
        new_children = current.children if xml else current.records
        kept = [r for r in old_children if (*prefix, r.name) not in removed]
        if [r.name for r in kept] != [r.name for r in new_children]:
            raise ValueError(f"unexpected removal/reordering at {prefix}")
        for left, right in zip(kept, new_children):
            path = (*prefix, left.name)
            if any(target[:len(path)] == path for target in removed):
                compare(left if xml else left.children, right if xml else right.children, path)
            elif before[left.start:left.end] != after[right.start:right.end]:
                raise ValueError(f"protected raw record changed: {path}")
    compare(old, new)


def protected_files():
    files = [p for item_id in KEEP_IDS for p in audit_tool.equipment_paths(item_id)]
    for name in ("Act", "Check", "QuestInfo", "Say"):
        files.append(ROOT / "clien/Data/Quest" / f"{name}.img")
        files.extend(ROOT / "gms-server" / tree / "Quest.wz" / f"{name}.img.xml"
                     for tree in ("wz", "wz-zh-CN"))
    for name in ("NPT_exception", "Commodity"):
        files.append(ROOT / "clien/Data/Etc" / f"{name}.img")
        files.extend(ROOT / "gms-server" / tree / "Etc.wz" / f"{name}.img.xml"
                     for tree in ("wz", "wz-zh-CN"))
    files.extend(ROOT / path for path in (
        "clien/Data/String/Skill.img", "gms-server/scripts/npc/equipment_fusion.js",
        "gms-server/scripts-zh-CN/npc/9110016.js",
        "gms-server/src/main/java/org/gms/server/SetItemManager.java",
    ))
    return files


def validate_references(ids):
    current = audit_tool.audit()
    for item_id, entry in current["referenced"].items():
        if int(item_id) in ids:
            actual = [r for r in entry["references"] if r["source"].split(":")[0] != str(SQL.relative_to(ROOT))]
            if actual:
                raise ValueError(f"new reference to approved deletion ID {item_id}: {actual}")
    for name in ("Act", "Check", "QuestInfo", "Say", "NPT_exception", "Commodity"):
        directory = "Quest" if name in ("Act", "Check", "QuestInfo", "Say") else "Etc"
        image = WzImage.from_bytes((ROOT / "clien/Data" / directory / f"{name}.img").read_bytes(),
                                  key=WzKey.for_region("GMS"))
        def visit(node):
            matched = {int(v) for v in audit_tool.TOKEN.findall(str(node.value))} & ids
            if matched:
                raise ValueError(f"client reference in {name}/{node.name}: {matched}")
            for child in node.children():
                visit(child)
        visit(image.parse())
        if image.truncated or image.parse_warnings:
            raise ValueError(f"invalid client reference IMG: {name}")


def sql_text(ids):
    template = (ROOT / "gms-server/src/main/resources/db/migration/V2.1.101__remove_deleted_weapon_ids.sql").read_text(encoding="utf-8")
    start = template.index("INSERT INTO")
    end = template.index(";", start) + 1
    ordered = sorted(ids)
    rows = [", ".join(f"({i})" for i in ordered[offset:offset + 12]) for offset in range(0, len(ordered), 12)]
    insert = "INSERT INTO `_removed_weapon_ids` (`itemid`) VALUES\n" + ",\n".join(rows) + ";"
    text = (template[:start] + insert + template[end:]).replace("_removed_weapon_ids", "_removed_unreferenced_equipment_ids")
    return text.replace("-- Remove weapons that no longer exist in the client/server resource catalog.",
                        "-- Remove 315 approved weapons/shoes; preserve all 39 user-retained IDs.")


def plan(ids):
    writes, deletes, checks = {}, [], {}
    paths = [("Eqp", audit_tool.category(i), str(i)) for i in sorted(ids)]
    before = CLIENT_EQP.read_bytes()
    if scan_img(before, region="GMS").string_references:
        raise ValueError("Eqp acquired string references; exact raw-record verification needs review")
    after, count = batch_remove_img(before, paths)
    verify_scope(before, after, paths)
    verify_img(after, "GMS")
    writes[CLIENT_EQP] = after
    spans = []
    layout = scan_img(before, region="GMS")
    for path in paths:
        try:
            _parent, record, _ancestors = _find_record(layout.root, path)
        except KeyError:
            continue
        spans.append({"path": list(path), "start": record.start, "end": record.end,
                      "sha256": digest(before[record.start:record.end])})
    checks["client_name_records_removed"] = count
    checks["client_raw_spans"] = spans
    for path in SERVER_EQP:
        before_text = path.read_text(encoding="utf-8")
        after_text, count = batch_remove_xml(before_text, paths)
        verify_scope(before_text, after_text, paths, xml=True)
        writes[path] = after_text.encode("utf-8")
        checks[str(path.relative_to(ROOT))] = {"name_records_removed": count}

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    old_count = len(catalog["items"])
    catalog["items"] = [item for item in catalog["items"] if int(item["id"]) not in ids]
    for category in ("Weapon", "Shoes"):
        items = [item for item in catalog["items"] if item.get("category") == category]
        catalog["atlases"][category]["count"] = len(items)
        catalog["atlases"][category]["icons"] = sum(bool(item.get("icon")) for item in items)
    writes[CATALOG] = json.dumps(catalog, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    checks["catalog_records_removed"] = old_count - len(catalog["items"])
    for category in ("Weapon", "Shoes"):
        path = ROOT / "gms-server/handbook/Equip" / f"{category}.txt"
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        kept = [line for line in lines if not (line[:7].isdigit() and int(line[:7]) in ids)]
        writes[path] = "".join(kept).encode("utf-8")
        checks[f"{category}_handbook_lines_removed"] = len(lines) - len(kept)
    writes[SQL] = sql_text(ids).encode("utf-8")
    for item_id in sorted(ids):
        for path in audit_tool.equipment_paths(item_id):
            if path.exists():
                deletes.append(path)
    writes = {p: data for p, data in writes.items() if not p.exists() or p.read_bytes() != data}
    return writes, deletes, checks


def atomic_write(path, data):
    temporary = path.with_name(path.name + ".equipment-removal-tmp")
    if temporary.exists():
        raise ValueError(f"staging path already exists: {temporary}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_bytes(data)
    temporary.replace(path)


def apply(writes, deletes, checks, ids):
    protected = {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in protected_files()}
    removed = [{"path": str(p.relative_to(ROOT)), "sha256": digest(p.read_bytes())} for p in deletes]
    # These files were clean at the start; raw Git blobs provide a recoverable baseline.
    for path in [p for p in writes if p.exists()] + deletes:
        relative = str(path.relative_to(ROOT))
        baseline = subprocess.check_output(["rtk", "proxy", "git", "cat-file", "blob", f"HEAD:{relative}"], cwd=ROOT)
        if baseline != path.read_bytes() and not RESULT.exists():
            raise ValueError(f"target is no longer at its reviewed baseline: {relative}")
    record = {"delete_ids": sorted(ids), "keep_ids": sorted(KEEP_IDS), "checks": checks,
              "removed_files": removed, "protected_sha256": protected,
              "modified_files": {str(p.relative_to(ROOT)): {"before_sha256": digest(p.read_bytes()) if p.exists() else None,
                                                           "sha256": digest(data)} for p, data in writes.items()}}
    for path, data in writes.items():
        atomic_write(path, data)
    for path in deletes:
        path.unlink()
    for relative, expected in protected.items():
        if digest((ROOT / relative).read_bytes()) != expected:
            raise ValueError(f"protected file changed: {relative}")
    if not RESULT.exists():
        atomic_write(RESULT, (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        manifest = {"delete_ids": sorted(ids), "keep_ids": sorted(KEEP_IDS), "files": removed}
        atomic_write(DELETE_MANIFEST, (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    ids = delete_ids()
    validate_references(ids)
    writes, deletes, checks = plan(ids)
    print(json.dumps({"delete_ids": len(ids), "keep_ids": len(KEEP_IDS), "delete_files": len(deletes),
                      "write_files": [str(p.relative_to(ROOT)) for p in writes],
                      "checks": {k: v for k, v in checks.items() if k != "client_raw_spans"}}, indent=2))
    if args.apply:
        apply(writes, deletes, checks, ids)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
