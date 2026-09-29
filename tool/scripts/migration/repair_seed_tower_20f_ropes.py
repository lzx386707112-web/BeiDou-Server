#!/usr/bin/env python3
"""Align the Seed Tower 1-20F rope/ladder ``connect`` nodes with the TMS source.

Root cause
----------
``migrate_seed_tower_20f.sanitize_map()`` flattened every ``oS=connect`` node::

    if str(a.child_value(c, "l1")) not in {"0", "1", "2", "3", "4"}:
        a.set_string(c, "l1", "0")
    a.set_string(c, "l2", str(max(0, min(4, int(a.child_value(c, "l2") or 0)))))

The BeiDou client keeps the complete style table in
``clien/Data/Map/Obj/connect.img`` (rope styles ``0``-``82``, ladder styles
``0``-``87``), and untouched town maps in this repository already use ``l1``
values up to ``43`` (rope) and ``67`` (ladder) -- for example ``196000000``
renders ``rope/8`` with zero uncovered pixels.  The blanket remap therefore did
not make ropes disappear; it swapped each rope's real style for the generic
style ``0`` while keeping the TMS piece indices ``l2``.

Style ``0`` pieces are 49/30/30/120/49 px tall, while TMS chose its ``l2``
indices against the piece heights of the style the map actually uses (``8``,
``22``, ``45``, ``60``, ``65``, ``73`` in these maps).  Mismatched piece heights
leave gaps, which is what the player sees as "断断续续的绳子".  Measured
uncovered pixels on ``992002000``: 639 before, 0 after.

What this script does
---------------------
Restores the TMS ``l1``/``l2`` values, but only where the target style and piece
index exist in the client's ``connect.img`` (that is the real compatibility
gate -- a missing style/piece is what makes a rope vanish).  Objects are matched
to TMS by physical placement ``(layer, x, y, z, l0)``: the client's object
*indices* differ from TMS's, so index-based matching is wrong.

Binary safety (AGENTS.md)
-------------------------
* The client IMG is patched with :func:`wzpy.incremental_img.mutate_img`, one
  scalar at a time.  Same-length values stay a pure in-place payload patch;
  ``0`` -> ``22`` grows the record by one byte and is handled by the record/size
  rebasing path.  No full writer, no re-serialisation.
* The server ``.img.xml`` mirror is patched with
  :func:`wzpy.incremental_xml.mutate_xml`, which replaces only the ``value``
  attribute token.
* Every patched IMG is re-scanned (``scan_img`` must land exactly on EOF), parsed
  with no warnings, tree-diffed against the source, and re-decoded canvas by
  canvas, so a broken payload offset cannot pass silently.
* Re-running the script is a no-op: the plan becomes empty once aligned.

Usage
-----
    python3 tool/scripts/migration/repair_seed_tower_20f_ropes.py --check
    python3 tool/scripts/migration/repair_seed_tower_20f_ropes.py --write
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy.crypto import WzKey, detect_region_from_img  # noqa: E402
from wzpy.wz_image import WzImage  # noqa: E402
from wzpy.properties import WzSubProperty  # noqa: E402
from wzpy.incremental_img import mutate_img, scan_img  # noqa: E402
from wzpy.incremental_xml import mutate_xml, scan_xml  # noqa: E402

TMS_DATA = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")

CLIENT_MAP_DIR = ROOT / "clien/Data/Map/Map/Map9"
SERVER_MAP_DIR = ROOT / "gms-server/wz/Map.wz/Map/Map9"
CONNECT_IMG = ROOT / "clien/Data/Map/Obj/connect.img"
REPORT_PATH = ROOT / "docs/migrations/seed-tower-20f-rope-align.json"

# The whole 1-20F tower; the lobby 992000000 has no connect nodes at all.
SEED_MAPS = ["992%03d000" % i for i in range(21)]

SCALAR_TYPES = {
    "WzStringProperty", "WzIntProperty", "WzShortProperty", "WzLongProperty",
    "WzFloatProperty", "WzDoubleProperty", "WzVectorProperty", "WzUolProperty",
    "WzNullProperty", "WzCanvasProperty", "WzSoundProperty", "WzConvexProperty",
    "WzRawDataProperty", "WzVideoProperty",
}


# --------------------------------------------------------------------------- #
# reading helpers
# --------------------------------------------------------------------------- #
def load_image(data: bytes) -> WzImage:
    image = WzImage.from_bytes(data, key=WzKey.for_region(detect_region_from_img(data)))
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError("source IMG is not clean: %s" % (image.parse_warnings or "truncated"))
    return image


def child_value(node: Any, name: str) -> Any:
    child = node.child(name) if hasattr(node, "child") else None
    return getattr(child, "value", None) if child is not None else None


def read_connects(image: WzImage) -> List[Dict[str, Any]]:
    """Every ``oS=connect`` object with its physical placement and style."""
    found: List[Dict[str, Any]] = []
    for layer in image.root.children():
        if not layer.name.isdigit():
            continue
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        for entry in objects.children():
            if not hasattr(entry, "child") or child_value(entry, "oS") != "connect":
                continue
            found.append({
                "layer": layer.name,
                "index": entry.name,
                "l0": str(child_value(entry, "l0")),
                "l1": str(child_value(entry, "l1")),
                "l2": str(child_value(entry, "l2")),
                "x": child_value(entry, "x"),
                "y": child_value(entry, "y"),
                "z": child_value(entry, "z"),
            })
    return found


def placement_key(record: Dict[str, Any]) -> Tuple[Any, ...]:
    """Client and TMS index their ``obj`` children differently, so match on
    physical placement instead of on the numeric child name."""
    return (record["layer"], record["x"], record["y"], record["z"], record["l0"])


def style_table(connect_image: WzImage) -> Dict[Tuple[str, str], int]:
    """``(l0, l1) -> piece count`` for the client's ``connect.img``."""
    table: Dict[Tuple[str, str], int] = {}
    for kind in connect_image.root.children():
        if not hasattr(kind, "children"):
            continue
        for style in kind.children():
            table[(kind.name, style.name)] = len(style.children())
    return table


def piece_box(connect_image: WzImage, l0: str, l1: str, l2: str) -> Optional[Tuple[int, int]]:
    """``(height, origin_y)`` of one rope/ladder piece, or ``None`` if absent."""
    kind = connect_image.root.child(l0)
    style = kind.child(l1) if kind is not None else None
    piece = style.child(l2) if style is not None else None
    if piece is None or not piece.children():
        return None
    canvas = piece.children()[0]
    if not hasattr(canvas, "height"):
        return None
    origin_y = canvas.height // 2
    origin = canvas.child("origin")
    if origin is not None and isinstance(origin.value, (tuple, list)) and len(origin.value) == 2:
        origin_y = origin.value[1]
    return (canvas.height, origin_y)


def uncovered_pixels(connect_image: WzImage, rows: Sequence[Dict[str, Any]]) -> int:
    """Vertical pixels of each rope/ladder chain that no piece covers.

    Chains are grouped by ``(layer, l0, x)`` and walked top-down by ``y``.  A
    rope that should be one continuous run reports ``0``; a rope whose pieces use
    the wrong style reports the sum of its holes.
    """
    chains: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        chains[(row["layer"], row["l0"], row["x"])].append(row)

    total = 0
    for items in chains.values():
        items.sort(key=lambda row: -row["y"])
        spans: List[Tuple[int, int]] = []
        for row in items:
            box = piece_box(connect_image, row["l0"], row["l1"], row["l2"])
            if box is None:
                continue
            height, origin_y = box
            spans.append((row["y"] - origin_y, row["y"] - origin_y + height))
        if not spans:
            continue
        spans.sort()
        cursor = spans[0][1]
        for start, end in spans[1:]:
            if start > cursor:
                total += start - cursor
            cursor = max(cursor, end)
    return total


# --------------------------------------------------------------------------- #
# planning
# --------------------------------------------------------------------------- #
def plan_map(
    client_rows: Sequence[Dict[str, Any]],
    tms_rows: Sequence[Dict[str, Any]],
    table: Dict[Tuple[str, str], int],
) -> Tuple[List[Tuple[str, str, str, str, str]], List[Tuple[str, str, str]]]:
    """Return ``(edits, skipped)``.

    ``edits`` are ``(layer, index, field, old, new)`` applied to the client IMG.
    ``skipped`` records TMS values we deliberately did not adopt because the
    client's ``connect.img`` has no such style or piece.
    """
    tms_by_placement = {placement_key(row): row for row in tms_rows}
    edits: List[Tuple[str, str, str, str, str]] = []
    skipped: List[Tuple[str, str, str]] = []

    for row in client_rows:
        source = tms_by_placement.get(placement_key(row))
        if source is None:
            skipped.append((row["layer"], row["index"], "no TMS object at this placement"))
            continue

        pieces = table.get((source["l0"], source["l1"]))
        style_ok = pieces is not None
        for field in ("l1", "l2"):
            target = source[field]
            if target == row[field]:
                continue
            if field == "l1":
                if not style_ok:
                    skipped.append((row["layer"], row["index"],
                                    "style %s/%s absent in connect.img" % (source["l0"], target)))
                    break
                edits.append((row["layer"], row["index"], field, row[field], target))
                continue
            # l2 depends on the style that will actually be used; validate it
            # against whichever l1 the client will end up with.
            effective_l1 = source["l1"] if style_ok else row["l1"]
            piece_count = table.get((source["l0"], effective_l1))
            if piece_count is None or not target.isdigit() or int(target) >= piece_count:
                skipped.append((row["layer"], row["index"],
                                "piece %s missing in %s/%s" % (target, source["l0"], effective_l1)))
                continue
            edits.append((row["layer"], row["index"], field, row[field], target))
    return edits, skipped


def projected_rows(rows: Sequence[Dict[str, Any]],
                   edits: Sequence[Tuple[str, str, str, str, str]]) -> List[Dict[str, Any]]:
    patch = {(layer, index, field): new for layer, index, field, _, new in edits}
    out = []
    for row in rows:
        updated = dict(row)
        for field in ("l1", "l2"):
            key = (row["layer"], row["index"], field)
            if key in patch:
                updated[field] = patch[key]
        out.append(updated)
    return out


# --------------------------------------------------------------------------- #
# tree comparison
# --------------------------------------------------------------------------- #
def image_tree(image: WzImage) -> Dict[str, Tuple[str, Any]]:
    tree: Dict[str, Tuple[str, Any]] = {}

    def walk(node: Any, path: str) -> None:
        type_name = type(node).__name__
        if isinstance(node, WzSubProperty) or type_name not in SCALAR_TYPES:
            children = node.children()
            tree[path] = ("<container:%s>" % type_name, tuple(child.name for child in children))
            for child in children:
                walk(child, path + "/" + child.name)
            return
        value = getattr(node, "value", None)
        if type_name in ("WzCanvasProperty", "WzSoundProperty", "WzVideoProperty"):
            value = "%sx%s" % (getattr(node, "width", "?"), getattr(node, "height", "?"))
        tree[path] = (type_name, value)

    for child in image.root.children():
        walk(child, child.name)
    return tree


def canvas_digest(image: WzImage) -> Dict[str, str]:
    """Hash every canvas payload key so a shifted offset cannot go unnoticed."""
    try:
        from wzpy.canvas import decode_canvas
    except ImportError:  # pragma: no cover - API fallback
        from wzpy import decode_canvas  # type: ignore

    digests: Dict[str, str] = {}

    def walk(node: Any, path: str) -> None:
        type_name = type(node).__name__
        if type_name == "WzCanvasProperty":
            try:
                rendered = decode_canvas(node, region="GMS")
                digests[path] = "%sx%s:%s" % (
                    rendered.width, rendered.height,
                    hashlib.sha256(rendered.tobytes()).hexdigest()[:16])
            except Exception as error:  # pragma: no cover - defensive
                digests[path] = "DECODE-FAIL:%s" % error
            return
        if isinstance(node, WzSubProperty) or type_name not in SCALAR_TYPES:
            for child in node.children():
                walk(child, path + "/" + child.name)

    for child in image.root.children():
        walk(child, child.name)
    return digests


def raw_record_order(data: bytes) -> Dict[Tuple[str, ...], Tuple[str, ...]]:
    orders: Dict[Tuple[str, ...], Tuple[str, ...]] = {}

    def visit(prop_list: Any, parent: Tuple[str, ...] = ()) -> None:
        orders[parent] = tuple(record.name for record in prop_list.records)
        for record in prop_list.records:
            if record.children is not None:
                visit(record.children, parent + (record.name,))

    visit(scan_img(data, region="GMS").root)
    return orders


# --------------------------------------------------------------------------- #
# applying
# --------------------------------------------------------------------------- #
def apply_image_edits(data: bytes, edits: Iterable[Tuple[str, str, str, str, str]]) -> bytes:
    current = data
    for layer, index, field, old, new in edits:
        result = mutate_img(current, "edit", (layer, "obj", index, field),
                            values={"value": new}, region="GMS")
        current = result.data
    return current


def xml_tree(text: str) -> Dict[str, Tuple[str, Any]]:
    root = scan_xml(text)
    tree: Dict[str, Tuple[str, Any]] = {}
    container_tags = {"imgdir", "canvas"}
    stack: List[Tuple[str, Any]] = [(root.name, root)]

    def walk(node: Any, path: str) -> None:
        if node.tag in container_tags and node.children:
            tree[path] = ("<%s>" % node.tag, tuple(child.name for child in node.children))
            for child in node.children:
                walk(child, path + "/" + (child.name or "?"))
            return
        attrs = {}
        import re
        for key, value in re.findall(r"(\w+)\s*=\s*\"([^\"]*)\"", text[node.start:node.start_end]):
            attrs[key] = value
        tree[path] = (node.tag, attrs.get("value"))

    for child in root.children:
        walk(child, child.name or "?")
    return tree


def apply_xml_edits(text: str, edits: Iterable[Tuple[str, str, str, str, str]], map_id: str) -> str:
    """``mutate_xml`` resolves a path relative to the root element's children, so
    the ``<imgdir name="<map>.img">`` wrapper is not part of the path."""
    current = text
    for layer, index, field, _old, new in edits:
        current = mutate_xml(current, "edit", (layer, "obj", index, field),
                             kind="String", values={"value": new})
    return current


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp-rope")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="apply the alignment")
    parser.add_argument("--check", action="store_true", help="report planned edits only")
    parser.add_argument("--maps", nargs="*", default=None, help="override the map list")
    parser.add_argument("--source-dir", default=None, metavar="DIR",
                        help="plan against a baseline snapshot instead of the working tree "
                             "(check only; used to regenerate the audit record)")
    args = parser.parse_args()
    if not args.write and not args.check:
        args.check = True
    if args.source_dir and args.write:
        parser.error("--source-dir is only meaningful together with --check")
    source_root = Path(args.source_dir) if args.source_dir else ROOT

    connect_raw = CONNECT_IMG.read_bytes()
    connect_image = load_image(connect_raw)
    table = style_table(connect_image)

    report: Dict[str, Any] = {"style_table": {("%s/%s" % k): v for k, v in sorted(table.items())},
                              "maps": {}}
    changed_files: List[str] = []

    for map_id in (args.maps or SEED_MAPS):
        client_path = source_root / CLIENT_MAP_DIR.relative_to(ROOT) / ("%s.img" % map_id)
        server_path = source_root / SERVER_MAP_DIR.relative_to(ROOT) / ("%s.img.xml" % map_id)
        tms_path = TMS_DATA / "Map/Map/Map9" / ("%s.img" % map_id)
        entry: Dict[str, Any] = {"client": str(client_path.relative_to(source_root))}

        if not client_path.exists():
            entry["status"] = "client map missing"
            report["maps"][map_id] = entry
            continue
        if not tms_path.exists():
            entry["status"] = "TMS source missing"
            report["maps"][map_id] = entry
            continue

        original = client_path.read_bytes()
        client_image = load_image(original)
        tms_raw = tms_path.read_bytes()
        tms_image = WzImage.from_bytes(tms_raw, key=WzKey.for_region("BMS"))
        tms_image.parse()

        client_rows = read_connects(client_image)
        tms_rows = read_connects(tms_image)

        client_placements = {placement_key(row) for row in client_rows}
        tms_placements = {placement_key(row) for row in tms_rows}
        entry["connect_objects_client"] = len(client_rows)
        entry["connect_objects_tms"] = len(tms_rows)
        entry["placement_sets_identical"] = client_placements == tms_placements

        edits, skipped = plan_map(client_rows, tms_rows, table)
        entry["edits"] = [list(item) for item in edits]
        entry["skipped"] = [list(item) for item in skipped]
        entry["uncovered_px_before"] = uncovered_pixels(connect_image, client_rows)
        entry["uncovered_px_after"] = uncovered_pixels(
            connect_image, projected_rows(client_rows, edits))

        if not edits:
            entry["status"] = "already aligned"
            report["maps"][map_id] = entry
            print("%-11s %-16s gap=%d" % (map_id, "already aligned", entry["uncovered_px_before"]))
            continue

        patched = apply_image_edits(original, edits)

        # --- verification ------------------------------------------------- #
        scan_img(patched, region="GMS")           # must land exactly on EOF
        patched_image = load_image(patched)       # must parse with no warnings
        before_tree = image_tree(client_image)
        after_tree = image_tree(patched_image)
        if set(before_tree) != set(after_tree):
            raise RuntimeError("%s: property set changed (%s / %s)" % (
                map_id, sorted(set(before_tree) - set(after_tree))[:5],
                sorted(set(after_tree) - set(before_tree))[:5]))
        expected = {"%s/obj/%s/%s" % (layer, index, field) for layer, index, field, _, _ in edits}
        touched = {path for path in before_tree if before_tree[path] != after_tree[path]}
        if touched != expected:
            raise RuntimeError("%s: unexpected tree delta %s / missing %s" % (
                map_id, sorted(touched - expected)[:6], sorted(expected - touched)[:6]))
        if raw_record_order(original) != raw_record_order(patched):
            raise RuntimeError("%s: sibling order changed" % map_id)
        before_canvas = canvas_digest(client_image)
        after_canvas = canvas_digest(patched_image)
        if before_canvas != after_canvas:
            broken = [k for k in before_canvas if before_canvas[k] != after_canvas.get(k)]
            raise RuntimeError("%s: canvas payloads changed: %s" % (map_id, broken[:5]))

        aligned_rows = read_connects(patched_image)
        aligned_placements = {placement_key(row) for row in aligned_rows}
        if aligned_placements != tms_placements:
            raise RuntimeError("%s: placement set diverged after patch" % map_id)
        tms_by_placement = {placement_key(row): row for row in tms_rows}
        for row in aligned_rows:
            source = tms_by_placement[placement_key(row)]
            # the style must now match TMS wherever the client can express it
            pieces = table.get((source["l0"], source["l1"]))
            if pieces is not None and int(source["l2"]) < pieces:
                if (row["l1"], row["l2"]) != (source["l1"], source["l2"]):
                    raise RuntimeError("%s: connect %s/%s not aligned to TMS (%s,%s vs %s,%s)" % (
                        map_id, row["layer"], row["index"], row["l1"], row["l2"],
                        source["l1"], source["l2"]))

        entry["client_sha256_before"] = sha256(original)
        entry["client_sha256_after"] = sha256(patched)
        entry["client_byte_delta"] = len(patched) - len(original)

        # --- server XML mirror -------------------------------------------- #
        xml_before = None
        if server_path.exists():
            xml_before = server_path.read_text(encoding="utf-8")
            xml_after = apply_xml_edits(xml_before, edits, map_id)
            scan_xml(xml_after)
            xml_tree_before = xml_tree(xml_before)
            xml_tree_after = xml_tree(xml_after)
            xml_expected = {"%s/obj/%s/%s" % (layer, index, field)
                            for layer, index, field, _, _ in edits}
            xml_touched = {k for k in xml_tree_before if xml_tree_before[k] != xml_tree_after.get(k)}
            if set(xml_tree_before) != set(xml_tree_after):
                raise RuntimeError("%s: XML property set changed" % map_id)
            if xml_touched != xml_expected:
                raise RuntimeError("%s: XML delta mismatch %s / %s" % (
                    map_id, sorted(xml_touched - xml_expected)[:6],
                    sorted(xml_expected - xml_touched)[:6]))
            entry["server_xml_sha256_before"] = sha256(xml_before.encode("utf-8"))
            entry["server_xml_sha256_after"] = sha256(xml_after.encode("utf-8"))

        entry["status"] = "aligned"
        report["maps"][map_id] = entry
        print("%-11s %-16s edits=%-4d gap %d -> %d  bytes %+d" % (
            map_id, "aligned", len(edits), entry["uncovered_px_before"],
            entry["uncovered_px_after"], entry["client_byte_delta"]))

        if args.write:
            atomic_write(client_path, patched)
            changed_files.append(str(client_path.relative_to(ROOT)))
            if xml_before is not None:
                atomic_write(server_path, xml_after.encode("utf-8"))
                changed_files.append(str(server_path.relative_to(ROOT)))

    total_edits = sum(len(entry.get("edits", [])) for entry in report["maps"].values())
    report["total_edits"] = total_edits
    report["changed_files"] = changed_files
    report["mode"] = "write" if args.write else "check"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
    print("\ntotal edits: %d" % total_edits)
    print("report: %s" % REPORT_PATH.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
