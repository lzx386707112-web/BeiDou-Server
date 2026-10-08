#!/usr/bin/env python3
"""Independent baseline, XML, icon and idempotence checks for the shoulder delta."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

import complete_set_shoulders as migration


def baseline(path):
    return subprocess.check_output([
        "rtk", "proxy", "git", "cat-file", "blob", f"HEAD:{path.relative_to(migration.ROOT)}"
    ], cwd=migration.ROOT)


def xml_state(data):
    result = {}

    def visit(node, path=()):
        current = (*path, node.get("name", node.tag))
        result[current] = (node.tag, dict(node.attrib), node.text if node.text and node.text.strip() else None)
        for child in node:
            visit(child, current)

    visit(ET.fromstring(data))
    return result


def check():
    root = migration.ROOT
    string = root / "clien/Data/String/Eqp.img"
    added = {(*migration.STRING_PARENT, str(item_id)) for item_id in migration.NAMES}
    migration.arc.verify_raw_record_insert_scope(baseline(string), string.read_bytes(), added)
    image = migration.load(string.read_bytes(), string.name)
    for item_id, name in migration.NAMES.items():
        assert image.root.get(f"Eqp/Accessory/{item_id}/name").value == name
    for path in migration.STRINGS:
        before, after = xml_state(baseline(path)), xml_state(path.read_bytes())
        assert not set(before) - set(after)
        assert all(after[key] == value for key, value in before.items())
        assert len(set(after) - set(before)) == 44
        for item_id, name in migration.NAMES.items():
            key = ("Eqp.img", "Eqp", "Accessory", str(item_id), "name")
            assert after[key][1]["value"] == name
    catalog_path = migration.CATALOG_ROOT / "catalog.json"
    old_catalog = json.loads(baseline(catalog_path))
    catalog = json.loads(catalog_path.read_bytes())
    assert catalog["items"][:len(old_catalog["items"])] == old_catalog["items"]
    assert len(catalog["items"]) - len(old_catalog["items"]) == 22
    atlas_path = migration.CATALOG_ROOT / "atlases/Accessory.png"
    import io
    old_atlas = Image.open(io.BytesIO(baseline(atlas_path))).convert("RGBA")
    atlas = Image.open(atlas_path).convert("RGBA")
    assert atlas.crop((0, 0, old_atlas.width, old_atlas.height)).tobytes() == old_atlas.tobytes()
    for item_id in migration.NAMES:
        client = root / "clien/Data/Character/Accessory" / f"{item_id:08d}.img"
        image = migration.load(client.read_bytes(), client.name)
        if item_id not in migration.NEW_IDS:
            assert client.read_bytes() == baseline(client)
        for icon_name in ("icon", "iconRaw"):
            icon = image.root.get(f"info/{icon_name}")
            bitmap = migration.decode_canvas(icon, region="GMS")
            assert bitmap.getbbox() and min(bitmap.size) > 1
            if item_id in migration.NEW_IDS:
                assert (icon.format, icon.format2) == (1, 0)
        xml = ET.parse(root / "gms-server/wz/Character.wz/Accessory" / (client.name + ".xml"))
        info = xml.getroot().find('./imgdir[@name="info"]')
        for node in image.root.child("info").children():
            if isinstance(node, migration.WzIntProperty):
                assert int(info.find(f'./int[@name="{node.name}"]').get("value")) == node.value
    paths = [string, *migration.STRINGS, catalog_path, atlas_path]
    paths += [root / "clien/Data/Character/Accessory" / f"{item_id:08d}.img" for item_id in migration.NEW_IDS]
    paths += [root / "gms-server/wz/Character.wz/Accessory" / f"{item_id:08d}.img.xml" for item_id in migration.NEW_IDS]
    hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    subprocess.run(["rtk", "proxy", "python3", str(Path(migration.__file__))], check=True, stdout=subprocess.DEVNULL)
    assert hashes == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    print("PASS: 22 String insertions only, 17 equipment baselines exact, 44 visible icons, 5 ARGB4444 equipment pairs, protected XML/catalog/atlas unchanged, 15-file idempotence")


if __name__ == "__main__":
    check()
