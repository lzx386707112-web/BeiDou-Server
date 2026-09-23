#!/usr/bin/env python3
"""Project Vellum's last two attacks into visual-only legacy skill slots."""

from __future__ import annotations

import hashlib
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CLIENT = ROOT / "clien/Data/Mob/8930000.img"
SERVER = ROOT / "gms-server/wz/Mob.wz/8930000.img.xml"
RENAMES = (("attack9", "skill2"), ("attack10", "skill3"))
ATTACKS = tuple(f"attack{i}" for i in range(1, 9))

sys.path.insert(0, str(ROOT / "tool/resource-workbench"))

from map_mob import app  # noqa: E402
from wzpy import WzCanvasProperty, WzSubProperty, WzUolProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.incremental_img import mutate_img  # noqa: E402


def action_names(image) -> tuple[str, ...]:
    return tuple(
        child.name for child in image.root.children()
        if re.fullmatch(r"attack\d+", child.name)
    )


def validate_img(data: bytes) -> None:
    image = app._verified_img_from_bytes(CLIENT, data)
    if action_names(image) != ATTACKS:
        raise RuntimeError(f"unexpected Vellum attacks: {action_names(image)}")
    for name in ("skill1", "skill2", "skill3"):
        if not isinstance(image.root.get(name), WzSubProperty):
            raise RuntimeError(f"missing Vellum {name}")

    def visit(node: WzSubProperty, path: tuple[str, ...] = ()) -> None:
        for child in node.children():
            child_path = (*path, child.name)
            if isinstance(child, WzUolProperty):
                target = app.resolve_uol_absolute("/".join(child_path), str(child.value))
                if image.root.get(target) is None:
                    raise RuntimeError(f"broken UOL: {'/'.join(child_path)} -> {target}")
            if isinstance(child, WzCanvasProperty) and path[:1] in (("skill2",), ("skill3",)):
                if (child.format, child.format2) != (1, 0):
                    raise RuntimeError(f"unexpected Canvas format: {'/'.join(child_path)}")
                pixels = decode_canvas(child, region="GMS").convert("RGBA")
                if pixels.getbbox() is None and (child.width, child.height) != (1, 1):
                    raise RuntimeError(f"blank Canvas: {'/'.join(child_path)}")
            if isinstance(child, WzSubProperty):
                visit(child, child_path)

    visit(image.root)


def project_img(data: bytes) -> bytes:
    image = app._verified_img_from_bytes(CLIENT, data)
    if action_names(image) == ATTACKS:
        validate_img(data)
        return data
    if action_names(image) != (*ATTACKS, "attack9", "attack10"):
        raise RuntimeError(f"unexpected starting Vellum attacks: {action_names(image)}")
    if any(image.root.get(new) is not None for _, new in RENAMES):
        raise RuntimeError("skill2/3 already occupied")

    before_records, before_orders = app.arc.raw_record_state(data)
    output = data
    for old, new in RENAMES:
        output = mutate_img(output, "rename", (old,), name=new, region="GMS").data
    validate_img(output)
    after_records, after_orders = app.arc.raw_record_state(output)
    renamed = dict(RENAMES)
    for path, raw in before_records.items():
        if len(path) == 1 and path[0] in renamed:
            continue  # The top-level name is the only intended record edit.
        mapped = (renamed.get(path[0], path[0]), *path[1:]) if path else path
        if after_records.get(mapped) != raw:
            raise RuntimeError(f"unintended raw record change: {'/'.join(path)}")
    for parent, names in before_orders.items():
        mapped_parent = (renamed.get(parent[0], parent[0]), *parent[1:]) if parent else parent
        expected = tuple(renamed.get(name, name) if not parent else name for name in names)
        if after_orders.get(mapped_parent) != expected:
            raise RuntimeError(f"sibling order changed: {'/'.join(parent)}")
    return output


def xml_roots(data: bytes) -> dict[str, bytes]:
    return {
        path: data[span.start:span.end]
        for path, span in app.index_xml(data).items() if path and "/" not in path
    }


def validate_xml(data: bytes) -> None:
    root = ET.fromstring(data)
    attacks = tuple(
        node.get("name") for node in root
        if node.tag == "imgdir" and re.fullmatch(r"attack\d+", node.get("name", ""))
    )
    if attacks != ATTACKS:
        raise RuntimeError(f"unexpected server attacks: {attacks}")
    if any(root.find(f'./imgdir[@name="{name}"]') is None for name in ("skill1", "skill2", "skill3")):
        raise RuntimeError("missing server skill animation")


def project_xml(data: bytes) -> bytes:
    root = ET.fromstring(data)
    if root.find('./imgdir[@name="skill2"]') is not None:
        validate_xml(data)
        return data
    before = xml_roots(data)
    output = data
    for old, new in RENAMES:
        span = app.index_xml(output).get(old)
        if span is None or new in app.index_xml(output):
            raise RuntimeError(f"cannot rename server action {old}")
        opening = output[span.start:span.open_end]
        old_name = f'name="{old}"'.encode("ascii")
        if opening.count(old_name) != 1:
            raise RuntimeError(f"cannot locate server action name {old}")
        output = output[:span.start] + opening.replace(old_name, f'name="{new}"'.encode("ascii"), 1) + output[span.open_end:]
    validate_xml(output)
    after = xml_roots(output)
    for name, raw in before.items():
        if name not in dict(RENAMES) and after.get(name) != raw:
            raise RuntimeError(f"unintended server XML change: {name}")
    return output


def migrate() -> dict[str, str | bool]:
    original_client = CLIENT.read_bytes()
    original_server = SERVER.read_bytes()
    client = project_img(original_client)
    server = project_xml(original_server)
    if project_img(client) != client or project_xml(server) != server:
        raise RuntimeError("Vellum skill projection is not idempotent")

    written: list[tuple[Path, bytes]] = []
    try:
        for path, before, after in ((CLIENT, original_client, client), (SERVER, original_server, server)):
            if before != after:
                app.atomic_write(path, after, backup=False)
                written.append((path, before))
        app._load_image_cached.cache_clear()
        validate_img(CLIENT.read_bytes())
        validate_xml(SERVER.read_bytes())
    except Exception:
        for path, before in reversed(written):
            app.atomic_write(path, before, backup=False)
        app._load_image_cached.cache_clear()
        raise
    return {
        "clientChanged": client != original_client,
        "serverChanged": server != original_server,
        "clientSha256": hashlib.sha256(client).hexdigest(),
        "serverSha256": hashlib.sha256(server).hexdigest(),
    }


if __name__ == "__main__":
    print(migrate())
