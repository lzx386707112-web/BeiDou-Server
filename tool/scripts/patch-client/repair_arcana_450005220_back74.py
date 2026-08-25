#!/usr/bin/env python3
"""Build a structurally valid A/B map without the back/74 candidate.

TMS ``back/18`` points at ``arcana2/back/74``.  The source resource is a
1x1 placeholder whose ``_outlink`` resolves to a 970x824 modern Canvas.  The
Arcane River migration materialized that Canvas directly, and this was the only
map in the region that referenced it.  That correlation is not proof of the
runtime crash cause.

This A/B repair removes only that background and renames the following
``back/19`` record to ``back/18`` so the numeric container remains dense.  It
uses record-level mutation; every untouched raw IMG record and every XML byte
outside the removed/renamed nodes must remain identical.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import WzImage, WzKey, WzSubProperty  # noqa: E402
from wzpy.incremental_img import mutate_img, scan_img  # noqa: E402
from wzpy.incremental_xml import mutate_xml  # noqa: E402


CLIENT = ROOT / "clien/Data/Map/Map/Map4/450005220.img"
SERVER = ROOT / "gms-server/wz/Map.wz/Map/Map4/450005220.img.xml"
BACKUP_ROOT = Path("/private/tmp/beidou-450005220-back74-backup")
TARGET_PATH = ("back", "18")
FOLLOWING_PATH = ("back", "19")
KEY = WzKey.for_region("GMS")
EXPECTED_BACK_NAMES = tuple(str(index) for index in range(20))
EXPECTED_TARGET = (
    ("bS", "String", "arcana2"),
    ("front", "Int", 0),
    ("ani", "Int", 0),
    ("no", "Int", 74),
    ("f", "Int", 0),
    ("x", "Int", -820),
    ("y", "Int", -343),
    ("rx", "Int", -100),
    ("ry", "Int", -100),
    ("type", "Int", 0),
    ("cx", "Int", 0),
    ("cy", "Int", 0),
    ("a", "Int", 255),
)
EXPECTED_FOLLOWING = (
    ("bS", "String", "arcana2"),
    ("front", "Int", 0),
    ("ani", "Int", 0),
    ("no", "Int", 17),
    ("f", "Int", 0),
    ("x", "Int", -1402),
    ("y", "Int", -270),
    ("rx", "Int", -95),
    ("ry", "Int", -95),
    ("type", "Int", 1),
    ("cx", "Int", 2200),
    ("cy", "Int", 0),
    ("a", "Int", 255),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes | str) -> None:
    binary = isinstance(data, bytes)
    kwargs = {} if binary else {"encoding": "utf-8"}
    with tempfile.NamedTemporaryFile(
        "wb" if binary else "w",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
        **kwargs,
    ) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def backup(path: Path) -> None:
    destination = BACKUP_ROOT / path.relative_to(ROOT)
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)


def load_client(data: bytes) -> WzImage:
    image = WzImage.from_bytes(data, key=KEY, name=CLIENT.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"malformed client IMG: truncated={image.truncated} "
            f"warnings={image.parse_warnings}"
        )
    return image


def property_signature(node: WzSubProperty) -> tuple[tuple[str, str, object], ...]:
    return tuple((child.name, child.type_name, child.value) for child in node.children())


def client_state(data: bytes) -> str:
    image = load_client(data)
    back = image.root.child("back")
    if not isinstance(back, WzSubProperty):
        raise RuntimeError("client map has no back container")
    names = tuple(child.name for child in back.children())
    references = [
        child.name
        for child in back.children()
        if isinstance(child, WzSubProperty)
        and getattr(child.child("bS"), "value", None) == "arcana2"
        and getattr(child.child("no"), "value", None) == 74
    ]
    if references:
        if names != EXPECTED_BACK_NAMES:
            raise RuntimeError(f"unexpected back order before repair: {names}")
        target = back.child("18")
        if not isinstance(target, WzSubProperty) or property_signature(target) != EXPECTED_TARGET:
            raise RuntimeError("back/18 no longer matches the reviewed crash record")
        if references != ["18"]:
            raise RuntimeError(f"unexpected arcana2/back/74 references: {references}")
        following = back.child("19")
        if not isinstance(following, WzSubProperty) or property_signature(following) != EXPECTED_FOLLOWING:
            raise RuntimeError("back/19 no longer matches the reviewed following record")
        return "original"
    gap_names = tuple(name for name in EXPECTED_BACK_NAMES if name != "18")
    if names == gap_names:
        following = back.child("19")
        if not isinstance(following, WzSubProperty) or property_signature(following) != EXPECTED_FOLLOWING:
            raise RuntimeError("gapped back/19 no longer matches the reviewed following record")
        return "gapped"
    dense_names = tuple(str(index) for index in range(19))
    if names == dense_names:
        following = back.child("18")
        if not isinstance(following, WzSubProperty) or property_signature(following) != EXPECTED_FOLLOWING:
            raise RuntimeError("renamed back/18 no longer matches the reviewed following record")
        return "repaired"
    raise RuntimeError(f"unexpected back order: {names}")


def xml_target(root: ET.Element) -> ET.Element | None:
    back = next((child for child in root if child.get("name") == "back"), None)
    if back is None:
        raise RuntimeError("server XML has no back container")
    return next((child for child in back if child.get("name") == "18"), None)


def server_state(text: str) -> str:
    root = ET.fromstring(text)
    target = xml_target(root)
    back = next(child for child in root if child.get("name") == "back")
    names = tuple(child.get("name") for child in back)

    def signature(node: ET.Element) -> tuple[tuple[str | None, str, object], ...]:
        return tuple(
        (
            child.get("name"),
            "String" if child.tag == "string" else "Int",
            child.get("value") if child.tag == "string" else int(child.get("value", "0")),
        )
            for child in node
        )

    if target is not None and signature(target) == EXPECTED_TARGET:
        if names != EXPECTED_BACK_NAMES:
            raise RuntimeError(f"unexpected server back order before repair: {names}")
        following = xml_target_by_name(back, "19")
        if following is None or signature(following) != EXPECTED_FOLLOWING:
            raise RuntimeError("server back/19 no longer matches the reviewed following record")
        return "original"
    gap_names = tuple(name for name in EXPECTED_BACK_NAMES if name != "18")
    if names == gap_names:
        following = xml_target_by_name(back, "19")
        if following is None or signature(following) != EXPECTED_FOLLOWING:
            raise RuntimeError("server gapped back/19 no longer matches the reviewed following record")
        return "gapped"
    dense_names = tuple(str(index) for index in range(19))
    if names == dense_names and target is not None and signature(target) == EXPECTED_FOLLOWING:
        return "repaired"
    raise RuntimeError(f"unexpected server back order: {names}")


def xml_target_by_name(back: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in back if child.get("name") == name), None)


def raw_records(data: bytes, parent: str | None = None) -> tuple[tuple[str, ...], dict[str, bytes]]:
    layout = scan_img(data, region="GMS")
    records = layout.root.records
    if parent is not None:
        record = next((item for item in records if item.name == parent), None)
        if record is None or record.children is None:
            raise RuntimeError(f"missing raw IMG container: {parent}")
        records = record.children.records
    names = tuple(record.name for record in records)
    return names, {record.name: data[record.start:record.end] for record in records}


def verify_raw_preservation(before: bytes, after: bytes, state: str) -> None:
    root_before_names, root_before = raw_records(before)
    root_after_names, root_after = raw_records(after)
    if root_before_names != root_after_names:
        raise RuntimeError("root IMG record order changed")
    for name in root_before_names:
        if name != "back" and root_before[name] != root_after[name]:
            raise RuntimeError(f"untouched root record changed: {name}")

    back_before_names, back_before = raw_records(before, "back")
    back_after_names, back_after = raw_records(after, "back")
    expected_names = tuple(str(index) for index in range(19))
    if back_after_names != expected_names:
        raise RuntimeError("back sibling order is not dense after repair")
    for name in tuple(str(index) for index in range(18)):
        if back_before[name] != back_after[name]:
            raise RuntimeError(f"untouched back record changed: {name}")
    following_before = "19"
    if following_before not in back_before:
        raise RuntimeError(f"missing following back record in {state} input")
    rename_input = (
        mutate_img(before, "remove", TARGET_PATH, region="GMS").data
        if state == "original" else before
    )
    expected_following = mutate_img(
        rename_input, "rename", ("back", following_before), name="18", region="GMS"
    ).data
    _, expected_records = raw_records(expected_following, "back")
    if expected_records["18"] != back_after["18"]:
        raise RuntimeError("following back record changed beyond its name")


def generate(client_before: bytes, server_before: str) -> tuple[bytes, str, str]:
    client_status = client_state(client_before)
    server_status = server_state(server_before)
    if client_status != server_status:
        raise RuntimeError(
            f"client/server repair state differs: {client_status}/{server_status}"
        )
    if client_status == "repaired":
        return client_before, server_before, "already-repaired"

    client_after = client_before
    server_after = server_before
    if client_status == "original":
        client_after = mutate_img(client_after, "remove", TARGET_PATH, region="GMS").data
        server_after = mutate_xml(server_after, "remove", TARGET_PATH)
    client_after = mutate_img(
        client_after, "rename", FOLLOWING_PATH, name="18", region="GMS"
    ).data
    server_after = mutate_xml(server_after, "rename", FOLLOWING_PATH, name="18")
    verify_raw_preservation(client_before, client_after, client_status)
    if client_state(client_after) != "repaired" or server_state(server_after) != "repaired":
        raise RuntimeError("post-repair contract verification failed")
    operation = "removed-candidate-and-densified" if client_status == "original" else "densified-existing-ab"
    return client_after, server_after, operation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true", help="validate and preview without writing files"
    )
    parser.add_argument(
        "--no-backup", action="store_true", help="do not create /private/tmp backups"
    )
    args = parser.parse_args()

    client_before = CLIENT.read_bytes()
    server_before = SERVER.read_text(encoding="utf-8")
    target_hash = None
    if client_state(client_before) == "original":
        _, records = raw_records(client_before, "back")
        target_hash = sha256(records["18"])

    client_after, server_after, operation = generate(client_before, server_before)
    if not args.check and (client_after != client_before or server_after != server_before):
        if not args.no_backup:
            backup(CLIENT)
            backup(SERVER)
        try:
            atomic_write(CLIENT, client_after)
            atomic_write(SERVER, server_after)
        except Exception:
            atomic_write(CLIENT, client_before)
            atomic_write(SERVER, server_before)
            raise

    print(f"operation={operation} check={args.check}")
    if target_hash:
        print(f"removed_record_sha256={target_hash}")
    print(f"client_sha256={sha256(client_after)} size={len(client_after)}")
    print(f"server_sha256={sha256(server_after.encode('utf-8'))} size={len(server_after.encode('utf-8'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
