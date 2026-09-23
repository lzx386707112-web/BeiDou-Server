#!/usr/bin/env python3
"""Compact Vellum's legacy client action table from 14 actions to 10."""

from __future__ import annotations

import hashlib
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CLIENT = ROOT / "clien/Data/Mob/8930000.img"
SERVER = ROOT / "gms-server/wz/Mob.wz/8930000.img.xml"

sys.path.insert(0, str(ROOT / "tool/resource-workbench"))

from map_mob import app  # noqa: E402
from wzpy import WzSubProperty, WzUolProperty  # noqa: E402
from wzpy.incremental_img import mutate_img  # noqa: E402


REMOVED_ACTIONS = {"attack2", "attack6", "attack12", "attack13"}
DELETE_ORDER = ("attack2", "attack12", "attack13", "attack6")
RENAMES = {
    "attack3": "attack2",
    "attack4": "attack3",
    "attack5": "attack4",
    "attack7": "attack5",
    "attack8": "attack6",
    "attack9": "attack7",
    "attack10": "attack8",
    "attack11": "attack9",
    "attack14": "attack10",
}
OLD_ACTIONS = {f"attack{index}" for index in range(1, 15)}
FINAL_ACTIONS = tuple(f"attack{index}" for index in range(1, 11))
UOL_PATTERN = re.compile(rb'(<uol\b[^>]*\bvalue=")([^"]*)(")')


def action_names(image) -> tuple[str, ...]:
    return tuple(
        child.name for child in image.root.children()
        if re.fullmatch(r"attack\d+", child.name)
    )


def remap_uol(value: str) -> str:
    separator = "\\" if "\\" in value and "/" not in value else "/"
    parts = value.replace("\\", "/").split("/")
    mapped = "/".join(RENAMES.get(part, part) for part in parts)
    return mapped.replace("/", separator)


def iter_uols(node: WzSubProperty, path: tuple[str, ...] = ()):
    for child in node.children():
        child_path = (*path, child.name)
        if isinstance(child, WzUolProperty):
            yield child_path, str(child.value)
        if isinstance(child, WzSubProperty):
            yield from iter_uols(child, child_path)


def validate_final_img(data: bytes) -> None:
    image = app._verified_img_from_bytes(CLIENT, data)
    if action_names(image) != FINAL_ACTIONS:
        raise RuntimeError(f"Vellum action order mismatch: {action_names(image)}")
    for path, value in iter_uols(image.root):
        target = app.resolve_uol_absolute("/".join(path), value)
        if image.root.get(target) is None:
            raise RuntimeError(f"broken Vellum UOL: {'/'.join(path)} -> {value} ({target})")


def compact_img(data: bytes) -> bytes:
    image = app._verified_img_from_bytes(CLIENT, data)
    current_actions = action_names(image)
    if current_actions == FINAL_ACTIONS[:8]:
        if any(image.root.get(name) is None for name in ("skill2", "skill3")):
            raise RuntimeError("missing projected Vellum skill animations")
        return data
    if current_actions == FINAL_ACTIONS:
        validate_final_img(data)
        return data
    if set(current_actions) != OLD_ACTIONS or len(current_actions) != len(OLD_ACTIONS):
        raise RuntimeError(f"unexpected Vellum action table: {current_actions}")

    for action_name in REMOVED_ACTIONS:
        action = image.root.get(action_name)
        if not isinstance(action, WzSubProperty):
            raise RuntimeError(f"missing removable action: {action_name}")
        frames = [child for child in action.children() if child.name.isdigit()]
        if not frames or any(not isinstance(frame, WzUolProperty) for frame in frames):
            raise RuntimeError(f"refusing to remove non-UOL action: {action_name}")

    before_records, _ = app.arc.raw_record_state(data)
    non_action_roots = {
        path: raw for path, raw in before_records.items()
        if len(path) == 1 and not re.fullmatch(r"attack\d+", path[0])
    }

    # Retained UOL records may use string-block references whose payload lives
    # inside one of the four records being removed. Re-encoding their values
    # first makes every retained UOL self-contained before the deletion.
    uol_edits = [
        (path, remap_uol(value))
        for path, value in iter_uols(image.root)
        if path[0] not in REMOVED_ACTIONS
    ]
    output = data
    for path, value in uol_edits:
        output = mutate_img(
            output, "edit", path, values={"value": value}, region="GMS",
        ).data
    for action_name in DELETE_ORDER:
        output = mutate_img(output, "remove", (action_name,), region="GMS").data
    for old_name, new_name in RENAMES.items():
        output = mutate_img(
            output, "rename", (old_name,), name=new_name, region="GMS",
        ).data

    validate_final_img(output)
    after_records, _ = app.arc.raw_record_state(output)
    for path, raw in non_action_roots.items():
        if after_records.get(path) != raw:
            raise RuntimeError(f"non-action client record changed: {'/'.join(path)}")
    return output


def top_level_xml_records(data: bytes) -> dict[str, bytes]:
    spans = app.index_xml(data)
    return {
        path: data[span.start:span.end]
        for path, span in spans.items() if path and "/" not in path
    }


def delete_xml_action(data: bytes, action_name: str) -> bytes:
    span = app.index_xml(data).get(action_name)
    if span is None:
        raise RuntimeError(f"server action missing: {action_name}")
    start = data.rfind(b"\n", 0, span.start) + 1
    if data[start:span.start].strip():
        start = span.start
    end = span.end
    if end < len(data) and data[end:end + 1] == b"\n":
        end += 1
    output = data[:start] + data[end:]
    ET.fromstring(output)
    return output


def rewrite_xml_uols(data: bytes, action_name: str) -> bytes:
    span = app.index_xml(data).get(action_name)
    if span is None:
        raise RuntimeError(f"server action missing: {action_name}")
    block = data[span.start:span.end]

    def replace(match: re.Match[bytes]) -> bytes:
        value = match.group(2).decode("ascii")
        mapped = remap_uol(value).encode("ascii")
        return match.group(1) + mapped + match.group(3)

    replacement = UOL_PATTERN.sub(replace, block)
    return data[:span.start] + replacement + data[span.end:]


def rename_xml_action(data: bytes, old_name: str, new_name: str) -> bytes:
    spans = app.index_xml(data)
    if new_name in spans:
        raise RuntimeError(f"server rename target already exists: {new_name}")
    span = spans.get(old_name)
    if span is None:
        raise RuntimeError(f"server action missing: {old_name}")
    opening = data[span.start:span.open_end]
    old = f'name="{old_name}"'.encode("ascii")
    new = f'name="{new_name}"'.encode("ascii")
    if opening.count(old) != 1:
        raise RuntimeError(f"cannot locate server action name: {old_name}")
    replacement = opening.replace(old, new, 1)
    return data[:span.start] + replacement + data[span.open_end:]


def validate_final_xml(data: bytes) -> None:
    root = ET.fromstring(data)
    names = tuple(
        child.get("name") for child in root
        if child.tag == "imgdir" and re.fullmatch(r"attack\d+", child.get("name", ""))
    )
    if names != FINAL_ACTIONS:
        raise RuntimeError(f"server Vellum action order mismatch: {names}")
    paths: set[str] = set()
    uols: list[tuple[str, str]] = []

    def visit(node: ET.Element, parent: tuple[str, ...] = ()) -> None:
        for child in node:
            child_path = (*parent, child.get("name", ""))
            path_text = "/".join(child_path)
            paths.add(path_text)
            if child.tag == "uol":
                uols.append((path_text, child.get("value", "")))
            visit(child, child_path)

    visit(root)
    for path, value in uols:
        target = app.resolve_uol_absolute(path, value)
        if target not in paths:
            raise RuntimeError(f"broken server Vellum UOL: {path} -> {value} ({target})")


def compact_xml(data: bytes) -> bytes:
    root = ET.fromstring(data)
    current_actions = tuple(
        child.get("name") for child in root
        if child.tag == "imgdir" and re.fullmatch(r"attack\d+", child.get("name", ""))
    )
    if current_actions == FINAL_ACTIONS[:8]:
        if any(root.find(f'./imgdir[@name="{name}"]') is None for name in ("skill2", "skill3")):
            raise RuntimeError("missing projected server Vellum skill animations")
        return data
    if current_actions == FINAL_ACTIONS:
        validate_final_xml(data)
        return data
    if set(current_actions) != OLD_ACTIONS or len(current_actions) != len(OLD_ACTIONS):
        raise RuntimeError(f"unexpected server Vellum action table: {current_actions}")

    before_roots = top_level_xml_records(data)
    protected = {
        name: raw for name, raw in before_roots.items()
        if not re.fullmatch(r"attack\d+", name)
    }
    output = data
    for action_name in DELETE_ORDER:
        output = delete_xml_action(output, action_name)
    for action_name in RENAMES:
        output = rewrite_xml_uols(output, action_name)
    for old_name, new_name in RENAMES.items():
        output = rename_xml_action(output, old_name, new_name)

    validate_final_xml(output)
    after_roots = top_level_xml_records(output)
    for name, raw in protected.items():
        if after_roots.get(name) != raw:
            raise RuntimeError(f"non-action server record changed: {name}")
    return output


def migrate() -> dict[str, object]:
    original_client = CLIENT.read_bytes()
    original_server = SERVER.read_bytes()
    client_data = compact_img(original_client)
    server_data = compact_xml(original_server)
    if compact_img(client_data) != client_data or compact_xml(server_data) != server_data:
        raise RuntimeError("Vellum compaction is not idempotent")

    written: list[tuple[Path, bytes]] = []
    try:
        if client_data != original_client:
            app.atomic_write(CLIENT, client_data, backup=False)
            written.append((CLIENT, original_client))
        if server_data != original_server:
            app.atomic_write(SERVER, server_data, backup=False)
            written.append((SERVER, original_server))
        app._load_image_cached.cache_clear()
        validate_final_img(CLIENT.read_bytes())
        validate_final_xml(SERVER.read_bytes())
    except Exception:
        for path, data in reversed(written):
            app.atomic_write(path, data, backup=False)
        app._load_image_cached.cache_clear()
        raise

    return {
        "clientChanged": client_data != original_client,
        "serverChanged": server_data != original_server,
        "clientSha256": hashlib.sha256(client_data).hexdigest(),
        "serverSha256": hashlib.sha256(server_data).hexdigest(),
    }


def main() -> None:
    result = migrate()
    print(
        f"clientChanged={result['clientChanged']} "
        f"serverChanged={result['serverChanged']} "
        f"client={result['clientSha256']} server={result['serverSha256']}"
    )


if __name__ == "__main__":
    main()
