#!/usr/bin/env python3
"""Independent source coverage, equipment existence, and repeat-generation checks."""
import json
import hashlib
from pathlib import Path

import generate_runtime_set_catalog as generator

ROOT = generator.ROOT
data = generator.OUTPUT.read_bytes()
assert data == generator.generate() == generator.generate()
catalog = json.loads(data)
assert len(catalog) == len({series["name"] for series in catalog}) == 55
client = {int(path.stem) for path in (ROOT / "clien/Data/Character").glob("*/*.img")
          if path.stem.isdigit()}
server = {int(path.name.split(".")[0]) for path in (ROOT / "gms-server/wz/Character.wz").glob("*/*.img.xml")
          if path.name.split(".")[0].isdigit()}
preview = {item["id"] for item in json.loads(
    (ROOT / "gms-server/src/main/resources/equipment-catalog/catalog.json").read_bytes())["items"]}
missing = []
for series in catalog:
    assert "pendingEffects" not in series
    ids = [item for slot in series["slots"] for item in slot]
    assert len(ids) == len(set(ids)), series["name"]
    assert len(series["tiers"]) <= 8
    for item in ids:
        if item not in client or item not in server or item not in preview:
            missing.append((series["name"], item, item in client, item in server, item in preview))
    for tier in series["tiers"]:
        assert tier["requiredCount"] <= len(series["slots"])
        assert len(tier["stats"]) <= 24
        assert not {"FinalDamage", "StatusRes", "BuffDuration", "CriticalRate", "IgnoreDefense"}.intersection(tier["stats"])
assert not missing, missing
black = next(series for series in catalog if series["name"] == "黑门")
assert [tier["requiredCount"] for tier in black["tiers"]] == [3, 5]
assert black["tiers"][1]["stats"]["HPPct"] == black["tiers"][1]["stats"]["MPPct"] == 2
treasure = next(series for series in catalog if series["name"] == "冒险岛寻宝")
assert next(tier for tier in treasure["tiers"] if tier["requiredCount"] == 6)["stats"]["Damage"] == 9
print("55 runtime series, all client/server/catalog equipment present, idempotent", hashlib.sha256(data).hexdigest())
